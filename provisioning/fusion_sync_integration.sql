-- ============================================================
-- Atlas on OCI - Oracle Fusion REST Integration & Data Sync
-- Establishes connection to Fusion REST APIs and syncs data
-- ============================================================

-- ============================================================
-- PART 1: Create REST Data Sources for Oracle Fusion APIs
-- ============================================================

-- 1.1 Create Web Credential for Fusion Authentication
BEGIN
    APEX_WEB_SERVICE.CREATE_WEB_CREDENTIALS(
        p_credential_name        => 'FUSION_REST_CREDENTIAL',
        p_static_id              => 'FUSION_REST_CREDENTIAL',
        p_auth_type              => 'BASIC_AUTH',
        p_username               => 'fusion_integration_user',
        p_password               => 'YourFusionPassword123!',
        p_prompt_on_install      => 'Y'
    );
END;
/

-- 1.2 Create REST Data Source for HCM Workers API
BEGIN
    APEX_REST_SOURCE.CREATE_REST_SOURCE(
        p_module_name            => 'FUSION_HCM_WORKERS',
        p_module_static_id       => 'FUSION_HCM_WORKERS',
        p_base_url               => 'https://your-fusion-instance.oracle.com/hcmRestApi/latest/workers',
        p_credential_static_id   => 'FUSION_REST_CREDENTIAL',
        p_auth_type              => 'OAUTH2',
        p_remote_server          => 'https://your-fusion-instance.oracle.com'
    );
END;
/

-- 1.3 Create REST Data Source for Financials API (Invoices)
BEGIN
    APEX_REST_SOURCE.CREATE_REST_SOURCE(
        p_module_name            => 'FUSION_FINANCIALS_INVOICES',
        p_module_static_id       => 'FUSION_FINANCIALS_INVOICES',
        p_base_url               => 'https://your-fusion-instance.oracle.com/fscmRestApi/latest/invoices',
        p_credential_static_id   => 'FUSION_REST_CREDENTIAL',
        p_auth_type              => 'OAUTH2'
    );
END;
/

-- 1.4 Create REST Data Source for Procurement API (Purchase Orders)
BEGIN
    APEX_REST_SOURCE.CREATE_REST_SOURCE(
        p_module_name            => 'FUSION_PROCUREMENT_PO',
        p_module_static_id       => 'FUSION_PROCUREMENT_PO',
        p_base_url               => 'https://your-fusion-instance.oracle.com/fscmRestApi/latest/purchaseOrders',
        p_credential_static_id   => 'FUSION_REST_CREDENTIAL',
        p_auth_type              => 'OAUTH2'
    );
END;
/

-- ============================================================
-- PART 2: Create Synchronization Procedures
-- ============================================================

-- 2.1 Sync Employees from Fusion HCM
CREATE OR REPLACE PROCEDURE ATLAS_SYNC_EMPLOYEES
IS
    l_response          CLOB;
    l_employee_count    NUMBER := 0;
    l_sync_start_time   TIMESTAMP := SYSTIMESTAMP;
    l_sync_end_time     TIMESTAMP;
BEGIN
    ATLAS_LOG_EVENT(
        p_event_type    => 'SYNC_START',
        p_resource_type => 'EMPLOYEES',
        p_action        => 'SYNC',
        p_details       => '{"source":"FUSION_HCM"}'
    );
    
    BEGIN
        -- Call Fusion REST API to get employees
        l_response := APEX_WEB_SERVICE.MAKE_REST_REQUEST(
            p_url                    => 'https://your-fusion-instance.oracle.com/hcmRestApi/latest/workers?limit=1000',
            p_http_method            => 'GET',
            p_credential_static_id   => 'FUSION_REST_CREDENTIAL'
        );
        
        -- Parse JSON response and insert/update employees
        FOR employee_rec IN (
            SELECT 
                JSON_VALUE(l_response, '$.items[*].id') AS employee_id,
                JSON_VALUE(l_response, '$.items[*].personNumber') AS employee_number,
                JSON_VALUE(l_response, '$.items[*].personFullName') AS full_name,
                JSON_VALUE(l_response, '$.items[*].jobTitle') AS job_title,
                JSON_VALUE(l_response, '$.items[*].departmentId') AS department_id,
                JSON_VALUE(l_response, '$.items[*].locationId') AS location_id,
                TO_DATE(JSON_VALUE(l_response, '$.items[*].hireDate'), 'YYYY-MM-DD') AS hire_date,
                JSON_VALUE(l_response, '$.items[*].assignmentStatus') AS assignment_status,
                JSON_VALUE(l_response, '$.items[*].managerId') AS manager_id
            FROM DUAL
        ) LOOP
            MERGE INTO ATLAS_EMPLOYEES ae
            USING DUAL
            ON (ae.EMPLOYEE_ID = employee_rec.employee_id)
            WHEN MATCHED THEN
                UPDATE SET
                    ae.FULL_NAME = employee_rec.full_name,
                    ae.JOB_TITLE = employee_rec.job_title,
                    ae.DEPARTMENT_ID = employee_rec.department_id,
                    ae.LOCATION_ID = employee_rec.location_id,
                    ae.ASSIGNMENT_STATUS = employee_rec.assignment_status,
                    ae.MANAGER_ID = employee_rec.manager_id,
                    ae.LAST_SYNC_DATE = SYSTIMESTAMP
            WHEN NOT MATCHED THEN
                INSERT (
                    EMPLOYEE_ID, EMPLOYEE_NUMBER, FULL_NAME, JOB_TITLE,
                    DEPARTMENT_ID, LOCATION_ID, HIRE_DATE, ASSIGNMENT_STATUS,
                    MANAGER_ID, LAST_SYNC_DATE, DATA_CLASSIFICATION
                ) VALUES (
                    employee_rec.employee_id,
                    employee_rec.employee_number,
                    employee_rec.full_name,
                    employee_rec.job_title,
                    employee_rec.department_id,
                    employee_rec.location_id,
                    employee_rec.hire_date,
                    employee_rec.assignment_status,
                    employee_rec.manager_id,
                    SYSTIMESTAMP,
                    'CONFIDENTIAL'
                );
            
            l_employee_count := l_employee_count + 1;
        END LOOP;
        
        COMMIT;
        
        l_sync_end_time := SYSTIMESTAMP;
        
        ATLAS_LOG_EVENT(
            p_event_type    => 'SYNC_COMPLETE',
            p_resource_type => 'EMPLOYEES',
            p_action        => 'SYNC',
            p_details       => '{"records_synced":' || l_employee_count || ',"duration_seconds":' || 
                               ROUND((l_sync_end_time - l_sync_start_time) * 86400) || '}'
        );
        
    EXCEPTION
        WHEN OTHERS THEN
            ATLAS_LOG_EVENT(
                p_event_type    => 'SYNC_ERROR',
                p_resource_type => 'EMPLOYEES',
                p_action        => 'SYNC',
                p_success       => 'N',
                p_error_message => SQLERRM
            );
            RAISE;
    END;
    
END ATLAS_SYNC_EMPLOYEES;
/

-- 2.2 Sync Invoices from Fusion Financials
CREATE OR REPLACE PROCEDURE ATLAS_SYNC_INVOICES
IS
    l_response          CLOB;
    l_invoice_count     NUMBER := 0;
    l_sync_start_time   TIMESTAMP := SYSTIMESTAMP;
    l_sync_end_time     TIMESTAMP;
BEGIN
    ATLAS_LOG_EVENT(
        p_event_type    => 'SYNC_START',
        p_resource_type => 'INVOICES',
        p_action        => 'SYNC',
        p_details       => '{"source":"FUSION_FINANCIALS"}'
    );
    
    BEGIN
        -- Call Fusion REST API to get invoices
        l_response := APEX_WEB_SERVICE.MAKE_REST_REQUEST(
            p_url                    => 'https://your-fusion-instance.oracle.com/fscmRestApi/latest/invoices?limit=1000&status=UNPAID',
            p_http_method            => 'GET',
            p_credential_static_id   => 'FUSION_REST_CREDENTIAL'
        );
        
        -- Parse JSON response and insert/update invoices
        FOR invoice_rec IN (
            SELECT 
                JSON_VALUE(l_response, '$.items[*].invoiceId') AS invoice_id,
                JSON_VALUE(l_response, '$.items[*].invoiceNumber') AS invoice_number,
                JSON_VALUE(l_response, '$.items[*].supplierId') AS supplier_id,
                TO_DATE(JSON_VALUE(l_response, '$.items[*].invoiceDate'), 'YYYY-MM-DD') AS invoice_date,
                JSON_VALUE(l_response, '$.items[*].invoiceAmount') AS invoice_amount,
                JSON_VALUE(l_response, '$.items[*].amountPaid') AS amount_paid,
                JSON_VALUE(l_response, '$.items[*].paymentStatus') AS payment_status,
                JSON_VALUE(l_response, '$.items[*].currencyCode') AS currency_code,
                TO_DATE(JSON_VALUE(l_response, '$.items[*].dueDate'), 'YYYY-MM-DD') AS due_date
            FROM DUAL
        ) LOOP
            MERGE INTO ATLAS_AP_INVOICES ai
            USING DUAL
            ON (ai.INVOICE_ID = invoice_rec.invoice_id)
            WHEN MATCHED THEN
                UPDATE SET
                    ai.INVOICE_NUMBER = invoice_rec.invoice_number,
                    ai.SUPPLIER_ID = invoice_rec.supplier_id,
                    ai.INVOICE_AMOUNT = invoice_rec.invoice_amount,
                    ai.AMOUNT_PAID = invoice_rec.amount_paid,
                    ai.PAYMENT_STATUS = invoice_rec.payment_status,
                    ai.LAST_SYNC_DATE = SYSTIMESTAMP
            WHEN NOT MATCHED THEN
                INSERT (
                    INVOICE_ID, INVOICE_NUMBER, SUPPLIER_ID, INVOICE_DATE,
                    INVOICE_AMOUNT, AMOUNT_PAID, PAYMENT_STATUS, CURRENCY_CODE,
                    DUE_DATE, LAST_SYNC_DATE, DATA_CLASSIFICATION
                ) VALUES (
                    invoice_rec.invoice_id,
                    invoice_rec.invoice_number,
                    invoice_rec.supplier_id,
                    invoice_rec.invoice_date,
                    invoice_rec.invoice_amount,
                    invoice_rec.amount_paid,
                    invoice_rec.payment_status,
                    invoice_rec.currency_code,
                    invoice_rec.due_date,
                    SYSTIMESTAMP,
                    'RESTRICTED'
                );
            
            l_invoice_count := l_invoice_count + 1;
        END LOOP;
        
        COMMIT;
        
        l_sync_end_time := SYSTIMESTAMP;
        
        ATLAS_LOG_EVENT(
            p_event_type    => 'SYNC_COMPLETE',
            p_resource_type => 'INVOICES',
            p_action        => 'SYNC',
            p_details       => '{"records_synced":' || l_invoice_count || ',"duration_seconds":' || 
                               ROUND((l_sync_end_time - l_sync_start_time) * 86400) || '}'
        );
        
    EXCEPTION
        WHEN OTHERS THEN
            ATLAS_LOG_EVENT(
                p_event_type    => 'SYNC_ERROR',
                p_resource_type => 'INVOICES',
                p_action        => 'SYNC',
                p_success       => 'N',
                p_error_message => SQLERRM
            );
            RAISE;
    END;
    
END ATLAS_SYNC_INVOICES;
/

-- 2.3 Sync Purchase Orders from Fusion Procurement
CREATE OR REPLACE PROCEDURE ATLAS_SYNC_PURCHASE_ORDERS
IS
    l_response          CLOB;
    l_po_count          NUMBER := 0;
    l_sync_start_time   TIMESTAMP := SYSTIMESTAMP;
    l_sync_end_time     TIMESTAMP;
BEGIN
    ATLAS_LOG_EVENT(
        p_event_type    => 'SYNC_START',
        p_resource_type => 'PURCHASE_ORDERS',
        p_action        => 'SYNC',
        p_details       => '{"source":"FUSION_PROCUREMENT"}'
    );
    
    BEGIN
        -- Call Fusion REST API to get purchase orders
        l_response := APEX_WEB_SERVICE.MAKE_REST_REQUEST(
            p_url                    => 'https://your-fusion-instance.oracle.com/fscmRestApi/latest/purchaseOrders?limit=1000&status=OPEN',
            p_http_method            => 'GET',
            p_credential_static_id   => 'FUSION_REST_CREDENTIAL'
        );
        
        -- Parse JSON response and insert/update purchase orders
        FOR po_rec IN (
            SELECT 
                JSON_VALUE(l_response, '$.items[*].poId') AS po_id,
                JSON_VALUE(l_response, '$.items[*].poNumber') AS po_number,
                JSON_VALUE(l_response, '$.items[*].supplierId') AS supplier_id,
                JSON_VALUE(l_response, '$.items[*].totalAmount') AS total_amount,
                JSON_VALUE(l_response, '$.items[*].status') AS status,
                TO_DATE(JSON_VALUE(l_response, '$.items[*].creationDate'), 'YYYY-MM-DD') AS creation_date
            FROM DUAL
        ) LOOP
            MERGE INTO ATLAS_PURCHASE_ORDERS apo
            USING DUAL
            ON (apo.PO_ID = po_rec.po_id)
            WHEN MATCHED THEN
                UPDATE SET
                    apo.PO_NUMBER = po_rec.po_number,
                    apo.SUPPLIER_ID = po_rec.supplier_id,
                    apo.TOTAL_AMOUNT = po_rec.total_amount,
                    apo.STATUS = po_rec.status,
                    apo.LAST_SYNC_DATE = SYSTIMESTAMP
            WHEN NOT MATCHED THEN
                INSERT (
                    PO_ID, PO_NUMBER, SUPPLIER_ID, TOTAL_AMOUNT,
                    STATUS, CREATION_DATE, LAST_SYNC_DATE, DATA_CLASSIFICATION
                ) VALUES (
                    po_rec.po_id,
                    po_rec.po_number,
                    po_rec.supplier_id,
                    po_rec.total_amount,
                    po_rec.status,
                    po_rec.creation_date,
                    SYSTIMESTAMP,
                    'RESTRICTED'
                );
            
            l_po_count := l_po_count + 1;
        END LOOP;
        
        COMMIT;
        
        l_sync_end_time := SYSTIMESTAMP;
        
        ATLAS_LOG_EVENT(
            p_event_type    => 'SYNC_COMPLETE',
            p_resource_type => 'PURCHASE_ORDERS',
            p_action        => 'SYNC',
            p_details       => '{"records_synced":' || l_po_count || ',"duration_seconds":' || 
                               ROUND((l_sync_end_time - l_sync_start_time) * 86400) || '}'
        );
        
    EXCEPTION
        WHEN OTHERS THEN
            ATLAS_LOG_EVENT(
                p_event_type    => 'SYNC_ERROR',
                p_resource_type => 'PURCHASE_ORDERS',
                p_action        => 'SYNC',
                p_success       => 'N',
                p_error_message => SQLERRM
            );
            RAISE;
    END;
    
END ATLAS_SYNC_PURCHASE_ORDERS;
/

-- ============================================================
-- PART 3: Create Scheduled Jobs for Automatic Synchronization
-- ============================================================

-- 3.1 Create Job for Employee Sync (Every 6 hours)
BEGIN
    DBMS_SCHEDULER.CREATE_JOB(
        job_name        => 'ATLAS_SYNC_EMPLOYEES_JOB',
        job_type        => 'STORED_PROCEDURE',
        job_action      => 'ATLAS_SYNC_EMPLOYEES',
        start_date      => SYSTIMESTAMP,
        repeat_interval => 'FREQ=HOURLY;INTERVAL=6',
        enabled         => TRUE,
        comments        => 'Sync employees from Oracle Fusion HCM every 6 hours'
    );
END;
/

-- 3.2 Create Job for Invoice Sync (Every 4 hours)
BEGIN
    DBMS_SCHEDULER.CREATE_JOB(
        job_name        => 'ATLAS_SYNC_INVOICES_JOB',
        job_type        => 'STORED_PROCEDURE',
        job_action      => 'ATLAS_SYNC_INVOICES',
        start_date      => SYSTIMESTAMP,
        repeat_interval => 'FREQ=HOURLY;INTERVAL=4',
        enabled         => TRUE,
        comments        => 'Sync invoices from Oracle Fusion Financials every 4 hours'
    );
END;
/

-- 3.3 Create Job for Purchase Order Sync (Every 8 hours)
BEGIN
    DBMS_SCHEDULER.CREATE_JOB(
        job_name        => 'ATLAS_SYNC_PO_JOB',
        job_type        => 'STORED_PROCEDURE',
        job_action      => 'ATLAS_SYNC_PURCHASE_ORDERS',
        start_date      => SYSTIMESTAMP,
        repeat_interval => 'FREQ=HOURLY;INTERVAL=8',
        enabled         => TRUE,
        comments        => 'Sync purchase orders from Oracle Fusion Procurement every 8 hours'
    );
END;
/

-- Grant execute permissions
GRANT EXECUTE ON ATLAS_SYNC_EMPLOYEES TO PUBLIC;
GRANT EXECUTE ON ATLAS_SYNC_INVOICES TO PUBLIC;
GRANT EXECUTE ON ATLAS_SYNC_PURCHASE_ORDERS TO PUBLIC;

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
