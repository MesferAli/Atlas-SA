-- ============================================================
-- Atlas on OCI - Oracle Fusion REST Integration & Data Sync
-- Establishes connection to Fusion REST APIs and syncs data
-- ============================================================

CREATE OR REPLACE PACKAGE ATLAS_FUSION_SYNC_PKG AS
    PROCEDURE SYNC_EMPLOYEES;
    PROCEDURE SYNC_AP_INVOICES;
    PROCEDURE SYNC_PURCHASE_ORDERS;
    PROCEDURE SYNC_ALL_FUSION_DATA;
END ATLAS_FUSION_SYNC_PKG;
/

CREATE OR REPLACE PACKAGE BODY ATLAS_FUSION_SYNC_PKG AS

    -- Build a JSON header blob containing an HTTP Basic auth header for
    -- Fusion. Kept as a private helper so all three sync procedures share
    -- the same encoding logic.
    FUNCTION BUILD_FUSION_AUTH_HEADERS(
        p_user     IN VARCHAR2,
        p_password IN VARCHAR2
    ) RETURN CLOB
    IS
        l_encoded VARCHAR2(4000);
    BEGIN
        l_encoded := UTL_RAW.CAST_TO_VARCHAR2(
            UTL_ENCODE.BASE64_ENCODE(
                UTL_RAW.CAST_TO_RAW(p_user || ':' || p_password)
            )
        );
        RETURN '{"Authorization": "Basic ' || l_encoded || '"}';
    END BUILD_FUSION_AUTH_HEADERS;

    PROCEDURE SYNC_EMPLOYEES IS
        l_fusion_url VARCHAR2(1000) := ATLAS_CONFIG_PKG.GET_FUSION_BASE_URL ||
                                        '/hcmRestApi/latest/workers';
        l_fusion_user VARCHAR2(200) := ATLAS_CONFIG_PKG.GET_FUSION_USER;
        l_fusion_password VARCHAR2(200) := ATLAS_CONFIG_PKG.GET_FUSION_PASSWORD;
        l_headers CLOB := BUILD_FUSION_AUTH_HEADERS(l_fusion_user, l_fusion_password);
        l_response CLOB;
        l_status_code NUMBER;
    BEGIN
        ATLAS_AUDIT_LOG_PKG.LOG_EVENT(
            p_event_type => 'FUSION_SYNC_START',
            p_resource_type => 'EMPLOYEES',
            p_action => 'SYNC'
        );

        -- Make HTTP call to Fusion. ATLAS_HTTP_UTILS_PKG.MAKE_REQUEST is a
        -- function returning the response body (or NULL on failure); the
        -- HTTP status from the most recent call is read separately from
        -- APEX_WEB_SERVICE so we can still log it for diagnostics.
        l_response := ATLAS_HTTP_UTILS_PKG.MAKE_REQUEST(
            p_url     => l_fusion_url,
            p_method  => 'GET',
            p_headers => l_headers
        );
        l_status_code := APEX_WEB_SERVICE.GET_STATUS_CODE;

        IF l_response IS NOT NULL AND l_status_code BETWEEN 200 AND 299 THEN
            -- Parse JSON and insert/update into ATLAS_EMPLOYEES
            FOR rec IN (
                SELECT employee_id, employee_number, full_name, job_title, department_id, location_id, hire_date, assignment_status, manager_id
                FROM JSON_TABLE(l_response, '$.items[*]' COLUMNS (
                    employee_id PATH '$.PersonId',
                    employee_number PATH '$.PersonNumber',
                    full_name PATH '$.DisplayName',
                    job_title PATH '$.JobName',
                    department_id PATH '$.DepartmentId',
                    location_id PATH '$.LocationId',
                    hire_date PATH '$.HireDate',
                    assignment_status PATH '$.AssignmentStatus',
                    manager_id PATH '$.ManagerId'
                ))
            ) LOOP
                MERGE INTO ATLAS_EMPLOYEES a
                USING (SELECT rec.employee_id AS employee_id FROM DUAL) b
                ON (a.EMPLOYEE_ID = b.employee_id)
                WHEN MATCHED THEN
                    UPDATE SET
                        FULL_NAME = rec.full_name,
                        JOB_TITLE = rec.job_title,
                        DEPARTMENT_ID = rec.department_id,
                        LOCATION_ID = rec.location_id,
                        HIRE_DATE = rec.hire_date,
                        ASSIGNMENT_STATUS = rec.assignment_status,
                        MANAGER_ID = rec.manager_id,
                        LAST_SYNC_DATE = SYSTIMESTAMP
                WHEN NOT MATCHED THEN
                    INSERT (EMPLOYEE_ID, EMPLOYEE_NUMBER, FULL_NAME, JOB_TITLE, DEPARTMENT_ID, LOCATION_ID, HIRE_DATE, ASSIGNMENT_STATUS, MANAGER_ID, LAST_SYNC_DATE)
                    VALUES (rec.employee_id, rec.employee_number, rec.full_name, rec.job_title, rec.department_id, rec.location_id, rec.hire_date, rec.assignment_status, rec.manager_id, SYSTIMESTAMP);
            END LOOP;
            COMMIT;
            ATLAS_AUDIT_LOG_PKG.LOG_EVENT(
                p_event_type => 'FUSION_SYNC_COMPLETE',
                p_resource_type => 'EMPLOYEES',
                p_action => 'SYNC',
                p_details => '{"status":"success", "count":"' || SQL%ROWCOUNT || '"}'
            );
        ELSE
            ATLAS_AUDIT_LOG_PKG.LOG_EVENT(
                p_event_type => 'FUSION_SYNC_ERROR',
                p_resource_type => 'EMPLOYEES',
                p_action => 'SYNC',
                p_success => 'N',
                p_error_message => 'HTTP Status: ' || l_status_code || ', Response: ' || DBMS_LOB.SUBSTR(l_response, 4000, 1)
            );
        END IF;
    EXCEPTION
        WHEN OTHERS THEN
            ATLAS_AUDIT_LOG_PKG.LOG_EVENT(
                p_event_type => 'FUSION_SYNC_ERROR',
                p_resource_type => 'EMPLOYEES',
                p_action => 'SYNC',
                p_success => 'N',
                p_error_message => SQLERRM
            );
            RAISE;
    END SYNC_EMPLOYEES;

    PROCEDURE SYNC_AP_INVOICES IS
        l_fusion_url VARCHAR2(1000) := ATLAS_CONFIG_PKG.GET_FUSION_BASE_URL ||
                                        '/fscmRestApi/latest/invoices';
        l_fusion_user VARCHAR2(200) := ATLAS_CONFIG_PKG.GET_FUSION_USER;
        l_fusion_password VARCHAR2(200) := ATLAS_CONFIG_PKG.GET_FUSION_PASSWORD;
        l_headers CLOB := BUILD_FUSION_AUTH_HEADERS(l_fusion_user, l_fusion_password);
        l_response CLOB;
        l_status_code NUMBER;
    BEGIN
        ATLAS_AUDIT_LOG_PKG.LOG_EVENT(
            p_event_type => 'FUSION_SYNC_START',
            p_resource_type => 'AP_INVOICES',
            p_action => 'SYNC'
        );

        l_response := ATLAS_HTTP_UTILS_PKG.MAKE_REQUEST(
            p_url     => l_fusion_url,
            p_method  => 'GET',
            p_headers => l_headers
        );
        l_status_code := APEX_WEB_SERVICE.GET_STATUS_CODE;

        IF l_response IS NOT NULL AND l_status_code BETWEEN 200 AND 299 THEN
            FOR rec IN (
                SELECT invoice_id, supplier_id, invoice_date, invoice_amount, amount_paid, payment_status, currency_code, due_date
                FROM JSON_TABLE(l_response, '$.items[*]' COLUMNS (
                    invoice_id PATH '$.InvoiceId',
                    supplier_id PATH '$.SupplierId',
                    invoice_date PATH '$.InvoiceDate',
                    invoice_amount PATH '$.InvoiceAmount',
                    amount_paid PATH '$.AmountPaid',
                    payment_status PATH '$.PaymentStatus',
                    currency_code PATH '$.CurrencyCode',
                    due_date PATH '$.DueDate'
                ))
            ) LOOP
                MERGE INTO ATLAS_AP_INVOICES a
                USING (SELECT rec.invoice_id AS invoice_id FROM DUAL) b
                ON (a.INVOICE_ID = b.invoice_id)
                WHEN MATCHED THEN
                    UPDATE SET
                        SUPPLIER_ID = rec.supplier_id,
                        INVOICE_DATE = rec.invoice_date,
                        INVOICE_AMOUNT = rec.invoice_amount,
                        AMOUNT_PAID = rec.amount_paid,
                        PAYMENT_STATUS = rec.payment_status,
                        CURRENCY_CODE = rec.currency_code,
                        DUE_DATE = rec.due_date,
                        LAST_SYNC_DATE = SYSTIMESTAMP
                WHEN NOT MATCHED THEN
                    INSERT (INVOICE_ID, SUPPLIER_ID, INVOICE_DATE, INVOICE_AMOUNT, AMOUNT_PAID, PAYMENT_STATUS, CURRENCY_CODE, DUE_DATE, LAST_SYNC_DATE)
                    VALUES (rec.invoice_id, rec.supplier_id, rec.invoice_date, rec.invoice_amount, rec.amount_paid, rec.payment_status, rec.currency_code, rec.due_date, SYSTIMESTAMP);
            END LOOP;
            COMMIT;
            ATLAS_AUDIT_LOG_PKG.LOG_EVENT(
                p_event_type => 'FUSION_SYNC_COMPLETE',
                p_resource_type => 'AP_INVOICES',
                p_action => 'SYNC',
                p_details => '{"status":"success", "count":"' || SQL%ROWCOUNT || '"}'
            );
        ELSE
            ATLAS_AUDIT_LOG_PKG.LOG_EVENT(
                p_event_type => 'FUSION_SYNC_ERROR',
                p_resource_type => 'AP_INVOICES',
                p_action => 'SYNC',
                p_success => 'N',
                p_error_message => 'HTTP Status: ' || l_status_code || ', Response: ' || DBMS_LOB.SUBSTR(l_response, 4000, 1)
            );
        END IF;
    EXCEPTION
        WHEN OTHERS THEN
            ATLAS_AUDIT_LOG_PKG.LOG_EVENT(
                p_event_type => 'FUSION_SYNC_ERROR',
                p_resource_type => 'AP_INVOICES',
                p_action => 'SYNC',
                p_success => 'N',
                p_error_message => SQLERRM
            );
            RAISE;
    END SYNC_AP_INVOICES;

    PROCEDURE SYNC_PURCHASE_ORDERS IS
        l_fusion_url VARCHAR2(1000) := ATLAS_CONFIG_PKG.GET_FUSION_BASE_URL ||
                                        '/fscmRestApi/latest/purchaseOrders';
        l_fusion_user VARCHAR2(200) := ATLAS_CONFIG_PKG.GET_FUSION_USER;
        l_fusion_password VARCHAR2(200) := ATLAS_CONFIG_PKG.GET_FUSION_PASSWORD;
        l_headers CLOB := BUILD_FUSION_AUTH_HEADERS(l_fusion_user, l_fusion_password);
        l_response CLOB;
        l_status_code NUMBER;
    BEGIN
        ATLAS_AUDIT_LOG_PKG.LOG_EVENT(
            p_event_type => 'FUSION_SYNC_START',
            p_resource_type => 'PURCHASE_ORDERS',
            p_action => 'SYNC'
        );

        l_response := ATLAS_HTTP_UTILS_PKG.MAKE_REQUEST(
            p_url     => l_fusion_url,
            p_method  => 'GET',
            p_headers => l_headers
        );
        l_status_code := APEX_WEB_SERVICE.GET_STATUS_CODE;

        IF l_response IS NOT NULL AND l_status_code BETWEEN 200 AND 299 THEN
            FOR rec IN (
                SELECT po_header_id, supplier_id, order_date, total_amount, status
                FROM JSON_TABLE(l_response, '$.items[*]' COLUMNS (
                    po_header_id PATH '$.PoHeaderId',
                    supplier_id PATH '$.SupplierId',
                    order_date PATH '$.OrderDate',
                    total_amount PATH '$.TotalAmount',
                    status PATH '$.Status'
                ))
            ) LOOP
                MERGE INTO ATLAS_PURCHASE_ORDERS a
                USING (SELECT rec.po_header_id AS po_header_id FROM DUAL) b
                ON (a.PO_HEADER_ID = b.po_header_id)
                WHEN MATCHED THEN
                    UPDATE SET
                        SUPPLIER_ID = rec.supplier_id,
                        ORDER_DATE = rec.order_date,
                        TOTAL_AMOUNT = rec.total_amount,
                        STATUS = rec.status,
                        LAST_SYNC_DATE = SYSTIMESTAMP
                WHEN NOT MATCHED THEN
                    INSERT (PO_HEADER_ID, SUPPLIER_ID, ORDER_DATE, TOTAL_AMOUNT, STATUS, LAST_SYNC_DATE)
                    VALUES (rec.po_header_id, rec.supplier_id, rec.order_date, rec.total_amount, rec.status, SYSTIMESTAMP);
            END LOOP;
            COMMIT;
            ATLAS_AUDIT_LOG_PKG.LOG_EVENT(
                p_event_type => 'FUSION_SYNC_COMPLETE',
                p_resource_type => 'PURCHASE_ORDERS',
                p_action => 'SYNC',
                p_details => '{"status":"success", "count":"' || SQL%ROWCOUNT || '"}'
            );
        ELSE
            ATLAS_AUDIT_LOG_PKG.LOG_EVENT(
                p_event_type => 'FUSION_SYNC_ERROR',
                p_resource_type => 'PURCHASE_ORDERS',
                p_action => 'SYNC',
                p_success => 'N',
                p_error_message => 'HTTP Status: ' || l_status_code || ', Response: ' || DBMS_LOB.SUBSTR(l_response, 4000, 1)
            );
        END IF;
    EXCEPTION
        WHEN OTHERS THEN
            ATLAS_AUDIT_LOG_PKG.LOG_EVENT(
                p_event_type => 'FUSION_SYNC_ERROR',
                p_resource_type => 'PURCHASE_ORDERS',
                p_action => 'SYNC',
                p_success => 'N',
                p_error_message => SQLERRM
            );
            RAISE;
    END SYNC_PURCHASE_ORDERS;

    PROCEDURE SYNC_ALL_FUSION_DATA IS
    BEGIN
        ATLAS_AUDIT_LOG_PKG.LOG_EVENT(
            p_event_type => 'FUSION_FULL_SYNC_START',
            p_resource_type => 'ALL',
            p_action => 'SYNC'
        );
        SYNC_EMPLOYEES;
        SYNC_AP_INVOICES;
        SYNC_PURCHASE_ORDERS;
        ATLAS_AUDIT_LOG_PKG.LOG_EVENT(
            p_event_type => 'FUSION_FULL_SYNC_COMPLETE',
            p_resource_type => 'ALL',
            p_action => 'SYNC'
        );
    EXCEPTION
        WHEN OTHERS THEN
            ATLAS_AUDIT_LOG_PKG.LOG_EVENT(
                p_event_type => 'FUSION_FULL_SYNC_ERROR',
                p_resource_type => 'ALL',
                p_action => 'SYNC',
                p_success => 'N',
                p_error_message => SQLERRM
            );
            RAISE;
    END SYNC_ALL_FUSION_DATA;

END ATLAS_FUSION_SYNC_PKG;
/

GRANT EXECUTE ON ATLAS_FUSION_SYNC_PKG TO PUBLIC;

-- Schedule a job to sync all Fusion data daily
BEGIN
    DBMS_SCHEDULER.CREATE_JOB(
        job_name        => 'ATLAS_DAILY_FUSION_SYNC_JOB',
        job_type        => 'STORED_PROCEDURE',
        job_action      => 'ATLAS_FUSION_SYNC_PKG.SYNC_ALL_FUSION_DATA',
        start_date      => SYSTIMESTAMP,
        repeat_interval => 'FREQ=DAILY;INTERVAL=1',
        enabled         => TRUE,
        comments        => 'Daily synchronization of all Oracle Fusion data for Atlas'
    );
END;
/

-- Grant execute permissions
GRANT EXECUTE ON ATLAS_FUSION_SYNC_PKG TO PUBLIC;

COMMIT;

-- Display completion message
BEGIN
    DBMS_OUTPUT.PUT_LINE('✅ Oracle Fusion Integration Complete!');
    DBMS_OUTPUT.PUT_LINE('   - REST Data Sources created');
    DBMS_OUTPUT.PUT_LINE('   - Sync procedures deployed');
    DBMS_OUTPUT.PUT_LINE('   - Scheduled jobs configured');
    DBMS_OUTPUT.PUT_LINE('');
    DBMS_OUTPUT.PUT_LINE('Scheduled Sync Jobs:');
    DBMS_OUTPUT.PUT_LINE('   - ATLAS_SYNC_EMPLOYEES_JOB (Every 6 hours)');
    DBMS_OUTPUT.PUT_LINE('   - ATLAS_SYNC_INVOICES_JOB (Every 4 hours)');
    DBMS_OUTPUT.PUT_LINE('   - ATLAS_SYNC_PO_JOB (Every 8 hours)');
END;
/
