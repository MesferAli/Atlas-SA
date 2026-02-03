-- ============================================================
-- Atlas on OCI - Intelligence Layer Package
-- Purpose: Analyze Fusion data and generate proactive alerts
-- ============================================================



CREATE OR REPLACE PACKAGE ATLAS_INTELLIGENCE_PKG AS
    -- Main procedure to run all intelligence checks
    PROCEDURE GENERATE_PROACTIVE_ALERTS;
    
    -- Specific check procedures
    PROCEDURE CHECK_OVERDUE_INVOICES;
    PROCEDURE CHECK_PO_STAGNATION;
    PROCEDURE CHECK_HR_TRENDS;
    
    -- Utility to clear old resolved alerts
    PROCEDURE PURGE_OLD_ALERTS(p_days_to_keep IN NUMBER DEFAULT 30);
END ATLAS_INTELLIGENCE_PKG;
/

CREATE OR REPLACE PACKAGE BODY ATLAS_INTELLIGENCE_PKG AS

    -- ---------------------------------------------------------
    -- Procedure: GENERATE_PROACTIVE_ALERTS
    -- ---------------------------------------------------------
    PROCEDURE GENERATE_PROACTIVE_ALERTS IS
    BEGIN
        ATLAS_AUDIT_LOG_PKG.LOG_EVENT(
            p_event_type    => 'INTEL_RUN_START',
            p_resource_type => 'INTELLIGENCE',
            p_action        => 'GENERATE_ALERTS',
            p_details       => '{"status":"started"}'
        );

        CHECK_OVERDUE_INVOICES;
        CHECK_PO_STAGNATION;
        CHECK_HR_TRENDS;

        ATLAS_AUDIT_LOG_PKG.LOG_EVENT(
            p_event_type    => 'INTEL_RUN_COMPLETE',
            p_resource_type => 'INTELLIGENCE',
            p_action        => 'GENERATE_ALERTS',
            p_details       => '{"status":"completed"}'
        );
    EXCEPTION
        WHEN OTHERS THEN
            ATLAS_AUDIT_LOG_PKG.LOG_EVENT(
                p_event_type    => 'INTEL_RUN_ERROR',
                p_resource_type => 'INTELLIGENCE',
                p_action        => 'GENERATE_ALERTS',
                p_success       => 'N',
                p_error_message => SQLERRM
            );
    END GENERATE_PROACTIVE_ALERTS;

    -- ---------------------------------------------------------
    -- Procedure: CHECK_OVERDUE_INVOICES
    -- ---------------------------------------------------------
    PROCEDURE CHECK_OVERDUE_INVOICES IS
        l_count NUMBER;
        l_amount NUMBER;
    BEGIN
        SELECT COUNT(*), SUM(INVOICE_AMOUNT)
        INTO l_count, l_amount
        FROM ATLAS_AP_INVOICES
        WHERE PAYMENT_STATUS = 'UNPAID'
          AND DUE_DATE < SYSDATE;

        IF l_count > 0 THEN
            INSERT INTO ATLAS_ALERTS (ALERT_ID, ALERT_TYPE, ALERT_MESSAGE, SEVERITY_LEVEL)
            VALUES (SEQ_ATLAS_ALERTS.NEXTVAL, 
                'FINANCIAL',
                'Detected ' || l_count || ' overdue invoices totaling ' || TO_CHAR(l_amount, '999,999,999.99') || ' SAR. Action required for cash flow management.',
                CASE WHEN l_amount > TO_NUMBER(ATLAS_CONFIG_PKG.GET_CRITICAL_INVOICE_THRESHOLD) THEN 'CRITICAL' ELSE 'WARNING' END
            );
        END IF;
    END CHECK_OVERDUE_INVOICES;

    -- ---------------------------------------------------------
    -- Procedure: CHECK_PO_STAGNATION
    -- ---------------------------------------------------------
    PROCEDURE CHECK_PO_STAGNATION IS
        l_count NUMBER;
    BEGIN
        SELECT COUNT(*)
        INTO l_count
        FROM ATLAS_PURCHASE_ORDERS
        WHERE STATUS = 'OPEN'
          AND LAST_SYNC_DATE < SYSTIMESTAMP - INTERVAL '7' DAY;

        IF l_count > 0 THEN
            INSERT INTO ATLAS_ALERTS (ALERT_ID, ALERT_TYPE, ALERT_MESSAGE, SEVERITY_LEVEL)
            VALUES (SEQ_ATLAS_ALERTS.NEXTVAL, 
                'OPERATIONAL',
                l_count || ' Purchase Orders have been stagnant for over ' || ATLAS_CONFIG_PKG.GET_PO_STAGNANT_DAYS || ' days. Review supplier fulfillment status.',
                'WARNING'
            );
        END IF;
    END CHECK_PO_STAGNATION;

    -- ---------------------------------------------------------
    -- Procedure: CHECK_HR_TRENDS
    -- ---------------------------------------------------------
    PROCEDURE CHECK_HR_TRENDS IS
        l_count NUMBER;
    BEGIN
        -- Check for high volume of pending assignments or status changes
        SELECT COUNT(*)
        INTO l_count
        FROM ATLAS_EMPLOYEES
        WHERE ASSIGNMENT_STATUS = 'PENDING';

        IF l_count > TO_NUMBER(ATLAS_CONFIG_PKG.GET_HR_PENDING_THRESHOLD) THEN
            INSERT INTO ATLAS_ALERTS (ALERT_ID, ALERT_TYPE, ALERT_MESSAGE, SEVERITY_LEVEL)
            VALUES (SEQ_ATLAS_ALERTS.NEXTVAL, 
                'HR',
                'High volume of pending employee assignments (' || l_count || '). Potential onboarding bottleneck detected.',
                'INFO'
            );
        END IF;
    END CHECK_HR_TRENDS;

    -- ---------------------------------------------------------
    -- Procedure: PURGE_OLD_ALERTS
    -- ---------------------------------------------------------
    PROCEDURE PURGE_OLD_ALERTS(p_days_to_keep IN NUMBER DEFAULT 30) IS
    BEGIN
        DELETE FROM ATLAS_ALERTS
        WHERE ALERT_STATUS = 'RESOLVED'
          AND RESOLVED_DATE < SYSTIMESTAMP - TO_NUMBER(ATLAS_CONFIG_PKG.GET_DAYS_TO_KEEP_RESOLVED_ALERTS);
        COMMIT;
    END PURGE_OLD_ALERTS;

END ATLAS_INTELLIGENCE_PKG;
/

-- Grant execute permission
GRANT EXECUTE ON ATLAS_INTELLIGENCE_PKG TO PUBLIC;

-- Create a scheduled job to run intelligence checks every hour
BEGIN
    DBMS_SCHEDULER.CREATE_JOB(
        job_name        => 'ATLAS_GENERATE_ALERTS_JOB',
        job_type        => 'STORED_PROCEDURE',
        job_action      => 'ATLAS_INTELLIGENCE_PKG.GENERATE_PROACTIVE_ALERTS',
        start_date      => SYSTIMESTAMP,
        repeat_interval => 'FREQ=HOURLY;INTERVAL=1',
        enabled         => TRUE,
        comments        => 'Run Atlas proactive intelligence checks every hour'
    );
END;
/
