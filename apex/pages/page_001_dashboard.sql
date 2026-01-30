-- ============================================================
-- Atlas on OCI - APEX Dashboard Page (Page 1)
-- Execute this in APEX SQL Workshop
-- ============================================================

-- Create Page 1: Dashboard
BEGIN
    APEX_PAGE.CREATE_PAGE(
        p_flow_id           => 100,
        p_page_id           => 1,
        p_page_name         => 'Dashboard',
        p_page_title        => 'Atlas Dashboard',
        p_page_mode         => 'NORMAL',
        p_page_template_id  => 1,
        p_auth_required     => 'Y'
    );
END;
/

-- Add Page Title Region
BEGIN
    APEX_REGION.CREATE_REGION(
        p_flow_id           => 100,
        p_page_id           => 1,
        p_region_name       => 'Page Title',
        p_region_type       => 'STATIC_CONTENT',
        p_display_sequence  => 10,
        p_source            => '<h1>Atlas Dashboard</h1><p>Real-time operational intelligence for Oracle Fusion</p>'
    );
END;
/

-- Add KPI Cards Region
BEGIN
    APEX_REGION.CREATE_REGION(
        p_flow_id           => 100,
        p_page_id           => 1,
        p_region_name       => 'Key Performance Indicators',
        p_region_type       => 'CLASSIC_REPORT',
        p_display_sequence  => 20,
        p_source            => 'SELECT 
            (SELECT COUNT(*) FROM ATLAS_EMPLOYEES WHERE ASSIGNMENT_STATUS = ''ACTIVE'') AS TOTAL_EMPLOYEES,
            (SELECT COUNT(*) FROM ATLAS_PURCHASE_ORDERS WHERE STATUS = ''OPEN'') AS ACTIVE_POS,
            (SELECT COUNT(*) FROM ATLAS_AP_INVOICES WHERE PAYMENT_STATUS = ''UNPAID'' AND DUE_DATE < SYSDATE) AS OVERDUE_INVOICES,
            (SELECT SUM(INVOICE_AMOUNT) FROM ATLAS_AP_INVOICES WHERE PAYMENT_STATUS = ''UNPAID'' AND DUE_DATE < SYSDATE) AS OVERDUE_AMOUNT
        FROM DUAL'
    );
END;
/

-- Add Alerts Region
BEGIN
    APEX_REGION.CREATE_REGION(
        p_flow_id           => 100,
        p_page_id           => 1,
        p_region_name       => 'System Alerts',
        p_region_type       => 'CLASSIC_REPORT',
        p_display_sequence  => 30,
        p_source            => 'SELECT 
            ALERT_ID,
            ALERT_TYPE,
            ALERT_MESSAGE,
            SEVERITY_LEVEL,
            CREATED_DATE
        FROM ATLAS_ALERTS
        WHERE ALERT_STATUS = ''ACTIVE''
        ORDER BY SEVERITY_LEVEL DESC, CREATED_DATE DESC
        FETCH FIRST 10 ROWS ONLY'
    );
END;
/

-- Add Recent Transactions Region
BEGIN
    APEX_REGION.CREATE_REGION(
        p_flow_id           => 100,
        p_page_id           => 1,
        p_region_name       => 'Recent Transactions',
        p_region_type       => 'CLASSIC_REPORT',
        p_display_sequence  => 40,
        p_source            => 'SELECT 
            ''Employee'' AS RECORD_TYPE,
            FULL_NAME AS RECORD_NAME,
            LAST_SYNC_DATE AS LAST_UPDATED
        FROM ATLAS_EMPLOYEES
        UNION ALL
        SELECT 
            ''Invoice'' AS RECORD_TYPE,
            INVOICE_NUMBER AS RECORD_NAME,
            LAST_SYNC_DATE AS LAST_UPDATED
        FROM ATLAS_AP_INVOICES
        UNION ALL
        SELECT 
            ''PO'' AS RECORD_TYPE,
            PO_NUMBER AS RECORD_NAME,
            LAST_SYNC_DATE AS LAST_UPDATED
        FROM ATLAS_PURCHASE_ORDERS
        ORDER BY LAST_UPDATED DESC
        FETCH FIRST 20 ROWS ONLY'
    );
END;
/

-- Add Navigation Button to Command Bar
BEGIN
    APEX_BUTTON.CREATE_BUTTON(
        p_flow_id           => 100,
        p_page_id           => 1,
        p_button_name       => 'GO_TO_COMMAND_BAR',
        p_button_label      => 'Go to Command Bar',
        p_button_position   => 'BOTTOM',
        p_button_action     => 'REDIRECT_PAGE',
        p_button_target     => 'f?p=100:2:&SESSION.'
    );
END;
/

COMMIT;
