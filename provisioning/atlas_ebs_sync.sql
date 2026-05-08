-- ============================================================
-- Atlas on OCI - Oracle E-Business Suite Integration & Data Sync
--
-- Pulls data from an EBS R12 instance into the ATLAS_* cache tables.
-- Default mode is DBLINK against the APPS schema; an ISG (Integrated
-- SOA Gateway) REST mode is provided for environments that prefer
-- HTTPS over a database link.
--
-- DB link name and schema come from ATLAS_CONFIG_PKG at runtime, so
-- the package can be deployed once and re-pointed across DEV/TEST/PROD
-- by updating config values rather than the package source.
-- ============================================================

CREATE OR REPLACE PACKAGE ATLAS_EBS_SYNC_PKG AS
    PROCEDURE SYNC_LOCATIONS;
    PROCEDURE SYNC_DEPARTMENTS;
    PROCEDURE SYNC_EMPLOYEES;
    PROCEDURE SYNC_SUPPLIERS;
    PROCEDURE SYNC_PURCHASE_ORDERS;
    PROCEDURE SYNC_AP_INVOICES;
    PROCEDURE SYNC_GL_BALANCES;
    PROCEDURE SYNC_ALL_EBS_DATA;
END ATLAS_EBS_SYNC_PKG;
/

CREATE OR REPLACE PACKAGE BODY ATLAS_EBS_SYNC_PKG AS

    -- ----------------------------------------------------------
    -- Helpers
    -- ----------------------------------------------------------

    -- DBMS_ASSERT.QUALIFIED_SQL_NAME accepts dot-qualified identifiers
    -- (e.g. EBS_PROD.WORLD), which is exactly what an Oracle DB link
    -- name can look like. Wrapping the config getter through it ensures
    -- a malicious config value can't smuggle SQL into the dynamic
    -- statements built below.
    FUNCTION SAFE_LINK RETURN VARCHAR2 IS
    BEGIN
        RETURN DBMS_ASSERT.QUALIFIED_SQL_NAME(ATLAS_CONFIG_PKG.GET_EBS_DB_LINK);
    END SAFE_LINK;

    FUNCTION SAFE_SCHEMA RETURN VARCHAR2 IS
    BEGIN
        RETURN DBMS_ASSERT.SIMPLE_SQL_NAME(ATLAS_CONFIG_PKG.GET_EBS_APPS_SCHEMA);
    END SAFE_SCHEMA;

    -- Convenience: "<schema>.<table>@<dblink>" as a single token.
    FUNCTION REMOTE_REF(p_table IN VARCHAR2) RETURN VARCHAR2 IS
    BEGIN
        RETURN SAFE_SCHEMA || '.' || DBMS_ASSERT.SIMPLE_SQL_NAME(p_table)
               || '@' || SAFE_LINK;
    END REMOTE_REF;

    -- Fail fast if the package is invoked while Atlas is configured to
    -- pull from Fusion. Operators can still call individual procedures
    -- manually for backfills if they want; this guard only blocks the
    -- scheduled SYNC_ALL_EBS_DATA flow.
    PROCEDURE ASSERT_EBS_SOURCE IS
        l_source VARCHAR2(20) := UPPER(ATLAS_CONFIG_PKG.GET_ATLAS_SOURCE_SYSTEM);
    BEGIN
        IF l_source <> 'EBS' THEN
            RAISE_APPLICATION_ERROR(
                -20801,
                'ATLAS_SOURCE_SYSTEM is "' || l_source ||
                '"; refusing to run EBS sync. Set it to "EBS" via ATLAS_CONFIG_PKG.SET_CONFIG_VALUE.'
            );
        END IF;
    END ASSERT_EBS_SOURCE;

    -- ----------------------------------------------------------
    -- SYNC_LOCATIONS — HR_LOCATIONS_ALL
    -- ----------------------------------------------------------
    PROCEDURE SYNC_LOCATIONS IS
        l_sql CLOB;
        l_rows NUMBER;
    BEGIN
        ATLAS_AUDIT_LOG_PKG.LOG_EVENT(
            p_event_type => 'EBS_SYNC_START',
            p_resource_type => 'LOCATIONS',
            p_action => 'SYNC'
        );

        l_sql :=
            'MERGE INTO ATLAS_LOCATIONS a USING ('               || CHR(10) ||
            '    SELECT LOCATION_ID, LOCATION_CODE, ADDRESS_LINE_1,' || CHR(10) ||
            '           TOWN_OR_CITY, REGION_2, COUNTRY'         || CHR(10) ||
            '    FROM '   || REMOTE_REF('HR_LOCATIONS_ALL')      || CHR(10) ||
            ') s ON (a.LOCATION_ID = s.LOCATION_ID)'             || CHR(10) ||
            'WHEN MATCHED THEN UPDATE SET'                       || CHR(10) ||
            '    LOCATION_NAME   = s.LOCATION_CODE,'             || CHR(10) ||
            '    ADDRESS_LINE_1  = s.ADDRESS_LINE_1,'            || CHR(10) ||
            '    CITY            = s.TOWN_OR_CITY,'              || CHR(10) ||
            '    REGION          = s.REGION_2,'                  || CHR(10) ||
            '    COUNTRY         = s.COUNTRY,'                   || CHR(10) ||
            '    LAST_SYNC_DATE  = SYSTIMESTAMP'                 || CHR(10) ||
            'WHEN NOT MATCHED THEN INSERT ('                     || CHR(10) ||
            '    LOCATION_ID, LOCATION_NAME, ADDRESS_LINE_1, CITY, REGION, COUNTRY, LAST_SYNC_DATE'
                                                                 || CHR(10) ||
            ') VALUES ('                                         || CHR(10) ||
            '    s.LOCATION_ID, s.LOCATION_CODE, s.ADDRESS_LINE_1, s.TOWN_OR_CITY, s.REGION_2, s.COUNTRY, SYSTIMESTAMP)';

        EXECUTE IMMEDIATE l_sql;
        l_rows := SQL%ROWCOUNT;
        COMMIT;

        ATLAS_AUDIT_LOG_PKG.LOG_EVENT(
            p_event_type => 'EBS_SYNC_COMPLETE',
            p_resource_type => 'LOCATIONS',
            p_action => 'SYNC',
            p_details => '{"status":"success","count":"' || l_rows || '"}'
        );
    EXCEPTION
        WHEN OTHERS THEN
            ATLAS_AUDIT_LOG_PKG.LOG_EVENT(
                p_event_type => 'EBS_SYNC_ERROR',
                p_resource_type => 'LOCATIONS',
                p_action => 'SYNC',
                p_success => 'N',
                p_error_message => SQLERRM
            );
            RAISE;
    END SYNC_LOCATIONS;

    -- ----------------------------------------------------------
    -- SYNC_DEPARTMENTS — HR_ALL_ORGANIZATION_UNITS (+ _TL for name)
    -- ----------------------------------------------------------
    PROCEDURE SYNC_DEPARTMENTS IS
        l_sql CLOB;
        l_rows NUMBER;
        l_bg VARCHAR2(50) := ATLAS_CONFIG_PKG.GET_EBS_BUSINESS_GROUP_ID;
    BEGIN
        ATLAS_AUDIT_LOG_PKG.LOG_EVENT(
            p_event_type => 'EBS_SYNC_START',
            p_resource_type => 'DEPARTMENTS',
            p_action => 'SYNC'
        );

        l_sql :=
            'MERGE INTO ATLAS_DEPARTMENTS a USING ('             || CHR(10) ||
            '    SELECT o.ORGANIZATION_ID AS DEPARTMENT_ID,'     || CHR(10) ||
            '           tl.NAME           AS DEPARTMENT_NAME'    || CHR(10) ||
            '    FROM '   || REMOTE_REF('HR_ALL_ORGANIZATION_UNITS') || ' o' || CHR(10) ||
            '    JOIN '   || REMOTE_REF('HR_ALL_ORGANIZATION_UNITS_TL') || ' tl' || CHR(10) ||
            '      ON tl.ORGANIZATION_ID = o.ORGANIZATION_ID'    || CHR(10) ||
            '     AND tl.LANGUAGE = USERENV(''LANG'')'           || CHR(10) ||
            '    WHERE (:p_bg = ''0'' OR o.BUSINESS_GROUP_ID = TO_NUMBER(:p_bg))' || CHR(10) ||
            ') s ON (a.DEPARTMENT_ID = s.DEPARTMENT_ID)'         || CHR(10) ||
            'WHEN MATCHED THEN UPDATE SET'                       || CHR(10) ||
            '    DEPARTMENT_NAME = s.DEPARTMENT_NAME,'           || CHR(10) ||
            '    LAST_SYNC_DATE  = SYSTIMESTAMP'                 || CHR(10) ||
            'WHEN NOT MATCHED THEN INSERT ('                     || CHR(10) ||
            '    DEPARTMENT_ID, DEPARTMENT_NAME, LAST_SYNC_DATE' || CHR(10) ||
            ') VALUES ('                                         || CHR(10) ||
            '    s.DEPARTMENT_ID, s.DEPARTMENT_NAME, SYSTIMESTAMP)';

        EXECUTE IMMEDIATE l_sql USING l_bg, l_bg;
        l_rows := SQL%ROWCOUNT;
        COMMIT;

        ATLAS_AUDIT_LOG_PKG.LOG_EVENT(
            p_event_type => 'EBS_SYNC_COMPLETE',
            p_resource_type => 'DEPARTMENTS',
            p_action => 'SYNC',
            p_details => '{"status":"success","count":"' || l_rows || '"}'
        );
    EXCEPTION
        WHEN OTHERS THEN
            ATLAS_AUDIT_LOG_PKG.LOG_EVENT(
                p_event_type => 'EBS_SYNC_ERROR',
                p_resource_type => 'DEPARTMENTS',
                p_action => 'SYNC',
                p_success => 'N',
                p_error_message => SQLERRM
            );
            RAISE;
    END SYNC_DEPARTMENTS;

    -- ----------------------------------------------------------
    -- SYNC_EMPLOYEES — PER_ALL_PEOPLE_F + PER_ALL_ASSIGNMENTS_F
    --
    -- Both are date-tracked tables. We pick the row effective today
    -- and the primary assignment.
    -- ----------------------------------------------------------
    PROCEDURE SYNC_EMPLOYEES IS
        l_sql CLOB;
        l_rows NUMBER;
        l_bg VARCHAR2(50) := ATLAS_CONFIG_PKG.GET_EBS_BUSINESS_GROUP_ID;
    BEGIN
        ATLAS_AUDIT_LOG_PKG.LOG_EVENT(
            p_event_type => 'EBS_SYNC_START',
            p_resource_type => 'EMPLOYEES',
            p_action => 'SYNC'
        );

        l_sql :=
            'MERGE INTO ATLAS_EMPLOYEES a USING ('               || CHR(10) ||
            '    SELECT papf.PERSON_ID                AS EMPLOYEE_ID,' || CHR(10) ||
            '           papf.EMPLOYEE_NUMBER          AS EMPLOYEE_NUMBER,' || CHR(10) ||
            '           papf.FULL_NAME                AS FULL_NAME,' || CHR(10) ||
            '           pj.NAME                       AS JOB_TITLE,' || CHR(10) ||
            '           paaf.ORGANIZATION_ID          AS DEPARTMENT_ID,' || CHR(10) ||
            '           paaf.LOCATION_ID              AS LOCATION_ID,' || CHR(10) ||
            '           papf.ORIGINAL_DATE_OF_HIRE    AS HIRE_DATE,' || CHR(10) ||
            '           paaf.ASSIGNMENT_STATUS_TYPE_ID AS ASSIGNMENT_STATUS_ID,' || CHR(10) ||
            '           paaf.SUPERVISOR_ID            AS MANAGER_ID' || CHR(10) ||
            '    FROM '   || REMOTE_REF('PER_ALL_PEOPLE_F')      || ' papf' || CHR(10) ||
            '    LEFT JOIN ' || REMOTE_REF('PER_ALL_ASSIGNMENTS_F') || ' paaf' || CHR(10) ||
            '      ON paaf.PERSON_ID = papf.PERSON_ID'           || CHR(10) ||
            '     AND TRUNC(SYSDATE) BETWEEN paaf.EFFECTIVE_START_DATE AND paaf.EFFECTIVE_END_DATE' || CHR(10) ||
            '     AND paaf.PRIMARY_FLAG = ''Y'''                 || CHR(10) ||
            '    LEFT JOIN ' || REMOTE_REF('PER_JOBS')           || ' pj' || CHR(10) ||
            '      ON pj.JOB_ID = paaf.JOB_ID'                   || CHR(10) ||
            '    WHERE TRUNC(SYSDATE) BETWEEN papf.EFFECTIVE_START_DATE AND papf.EFFECTIVE_END_DATE' || CHR(10) ||
            '      AND papf.CURRENT_EMPLOYEE_FLAG = ''Y'''       || CHR(10) ||
            '      AND (:p_bg = ''0'' OR papf.BUSINESS_GROUP_ID = TO_NUMBER(:p_bg))' || CHR(10) ||
            ') s ON (a.EMPLOYEE_ID = s.EMPLOYEE_ID)'             || CHR(10) ||
            'WHEN MATCHED THEN UPDATE SET'                       || CHR(10) ||
            '    FULL_NAME         = s.FULL_NAME,'               || CHR(10) ||
            '    JOB_TITLE         = s.JOB_TITLE,'               || CHR(10) ||
            '    DEPARTMENT_ID     = s.DEPARTMENT_ID,'           || CHR(10) ||
            '    LOCATION_ID       = s.LOCATION_ID,'             || CHR(10) ||
            '    HIRE_DATE         = s.HIRE_DATE,'               || CHR(10) ||
            '    ASSIGNMENT_STATUS = TO_CHAR(s.ASSIGNMENT_STATUS_ID),' || CHR(10) ||
            '    MANAGER_ID        = s.MANAGER_ID,'              || CHR(10) ||
            '    LAST_SYNC_DATE    = SYSTIMESTAMP'               || CHR(10) ||
            'WHEN NOT MATCHED THEN INSERT ('                     || CHR(10) ||
            '    EMPLOYEE_ID, EMPLOYEE_NUMBER, FULL_NAME, JOB_TITLE,' || CHR(10) ||
            '    DEPARTMENT_ID, LOCATION_ID, HIRE_DATE, ASSIGNMENT_STATUS,' || CHR(10) ||
            '    MANAGER_ID, LAST_SYNC_DATE'                     || CHR(10) ||
            ') VALUES ('                                         || CHR(10) ||
            '    s.EMPLOYEE_ID, s.EMPLOYEE_NUMBER, s.FULL_NAME, s.JOB_TITLE,' || CHR(10) ||
            '    s.DEPARTMENT_ID, s.LOCATION_ID, s.HIRE_DATE, TO_CHAR(s.ASSIGNMENT_STATUS_ID),' || CHR(10) ||
            '    s.MANAGER_ID, SYSTIMESTAMP)';

        EXECUTE IMMEDIATE l_sql USING l_bg, l_bg;
        l_rows := SQL%ROWCOUNT;
        COMMIT;

        ATLAS_AUDIT_LOG_PKG.LOG_EVENT(
            p_event_type => 'EBS_SYNC_COMPLETE',
            p_resource_type => 'EMPLOYEES',
            p_action => 'SYNC',
            p_details => '{"status":"success","count":"' || l_rows || '"}'
        );
    EXCEPTION
        WHEN OTHERS THEN
            ATLAS_AUDIT_LOG_PKG.LOG_EVENT(
                p_event_type => 'EBS_SYNC_ERROR',
                p_resource_type => 'EMPLOYEES',
                p_action => 'SYNC',
                p_success => 'N',
                p_error_message => SQLERRM
            );
            RAISE;
    END SYNC_EMPLOYEES;

    -- ----------------------------------------------------------
    -- SYNC_SUPPLIERS — AP_SUPPLIERS (R12+)
    -- ----------------------------------------------------------
    PROCEDURE SYNC_SUPPLIERS IS
        l_sql CLOB;
        l_rows NUMBER;
    BEGIN
        ATLAS_AUDIT_LOG_PKG.LOG_EVENT(
            p_event_type => 'EBS_SYNC_START',
            p_resource_type => 'SUPPLIERS',
            p_action => 'SYNC'
        );

        l_sql :=
            'MERGE INTO ATLAS_SUPPLIERS a USING ('               || CHR(10) ||
            '    SELECT VENDOR_ID         AS SUPPLIER_ID,'       || CHR(10) ||
            '           VENDOR_NAME       AS SUPPLIER_NAME,'     || CHR(10) ||
            '           SEGMENT1          AS SUPPLIER_NUMBER,'   || CHR(10) ||
            '           VENDOR_TYPE_LOOKUP_CODE AS SUPPLIER_TYPE,' || CHR(10) ||
            '           NUM_1099          AS TAX_REG_NUMBER,'    || CHR(10) ||
            '           NVL2(END_DATE_ACTIVE, ''INACTIVE'', ''ACTIVE'') AS STATUS' || CHR(10) ||
            '    FROM '   || REMOTE_REF('AP_SUPPLIERS')          || CHR(10) ||
            ') s ON (a.SUPPLIER_ID = s.SUPPLIER_ID)'             || CHR(10) ||
            'WHEN MATCHED THEN UPDATE SET'                       || CHR(10) ||
            '    SUPPLIER_NAME           = s.SUPPLIER_NAME,'     || CHR(10) ||
            '    SUPPLIER_NUMBER         = s.SUPPLIER_NUMBER,'   || CHR(10) ||
            '    SUPPLIER_TYPE           = s.SUPPLIER_TYPE,'     || CHR(10) ||
            '    TAX_REGISTRATION_NUMBER = s.TAX_REG_NUMBER,'    || CHR(10) ||
            '    STATUS                  = s.STATUS,'            || CHR(10) ||
            '    LAST_SYNC_DATE          = SYSTIMESTAMP'         || CHR(10) ||
            'WHEN NOT MATCHED THEN INSERT ('                     || CHR(10) ||
            '    SUPPLIER_ID, SUPPLIER_NAME, SUPPLIER_NUMBER, SUPPLIER_TYPE,' || CHR(10) ||
            '    TAX_REGISTRATION_NUMBER, STATUS, LAST_SYNC_DATE' || CHR(10) ||
            ') VALUES ('                                         || CHR(10) ||
            '    s.SUPPLIER_ID, s.SUPPLIER_NAME, s.SUPPLIER_NUMBER, s.SUPPLIER_TYPE,' || CHR(10) ||
            '    s.TAX_REG_NUMBER, s.STATUS, SYSTIMESTAMP)';

        EXECUTE IMMEDIATE l_sql;
        l_rows := SQL%ROWCOUNT;
        COMMIT;

        ATLAS_AUDIT_LOG_PKG.LOG_EVENT(
            p_event_type => 'EBS_SYNC_COMPLETE',
            p_resource_type => 'SUPPLIERS',
            p_action => 'SYNC',
            p_details => '{"status":"success","count":"' || l_rows || '"}'
        );
    EXCEPTION
        WHEN OTHERS THEN
            ATLAS_AUDIT_LOG_PKG.LOG_EVENT(
                p_event_type => 'EBS_SYNC_ERROR',
                p_resource_type => 'SUPPLIERS',
                p_action => 'SYNC',
                p_success => 'N',
                p_error_message => SQLERRM
            );
            RAISE;
    END SYNC_SUPPLIERS;

    -- ----------------------------------------------------------
    -- SYNC_PURCHASE_ORDERS — PO_HEADERS_ALL
    -- ----------------------------------------------------------
    PROCEDURE SYNC_PURCHASE_ORDERS IS
        l_sql CLOB;
        l_rows NUMBER;
        l_org VARCHAR2(50) := ATLAS_CONFIG_PKG.GET_EBS_ORG_ID;
    BEGIN
        ATLAS_AUDIT_LOG_PKG.LOG_EVENT(
            p_event_type => 'EBS_SYNC_START',
            p_resource_type => 'PURCHASE_ORDERS',
            p_action => 'SYNC'
        );

        l_sql :=
            'MERGE INTO ATLAS_PURCHASE_ORDERS a USING ('         || CHR(10) ||
            '    SELECT PO_HEADER_ID       AS PO_ID,'            || CHR(10) ||
            '           SEGMENT1           AS PO_NUMBER,'        || CHR(10) ||
            '           VENDOR_ID          AS SUPPLIER_ID,'      || CHR(10) ||
            '           CURRENCY_CODE      AS CURRENCY_CODE,'    || CHR(10) ||
            '           NVL(BLANKET_TOTAL_AMOUNT, 0) AS TOTAL_AMOUNT,' || CHR(10) ||
            '           AUTHORIZATION_STATUS AS STATUS,'         || CHR(10) ||
            '           APPROVED_DATE      AS APPROVED_DATE,'    || CHR(10) ||
            '           CREATED_BY         AS CREATED_BY,'       || CHR(10) ||
            '           CREATION_DATE      AS CREATION_DATE'     || CHR(10) ||
            '    FROM '   || REMOTE_REF('PO_HEADERS_ALL')        || CHR(10) ||
            '    WHERE (:p_org = ''0'' OR ORG_ID = TO_NUMBER(:p_org))' || CHR(10) ||
            ') s ON (a.PO_ID = s.PO_ID)'                         || CHR(10) ||
            'WHEN MATCHED THEN UPDATE SET'                       || CHR(10) ||
            '    PO_NUMBER       = s.PO_NUMBER,'                 || CHR(10) ||
            '    SUPPLIER_ID     = s.SUPPLIER_ID,'               || CHR(10) ||
            '    CURRENCY_CODE   = s.CURRENCY_CODE,'             || CHR(10) ||
            '    TOTAL_AMOUNT    = s.TOTAL_AMOUNT,'              || CHR(10) ||
            '    STATUS          = s.STATUS,'                    || CHR(10) ||
            '    APPROVED_DATE   = s.APPROVED_DATE,'             || CHR(10) ||
            '    CREATED_BY      = TO_CHAR(s.CREATED_BY),'       || CHR(10) ||
            '    CREATION_DATE   = s.CREATION_DATE,'             || CHR(10) ||
            '    LAST_SYNC_DATE  = SYSTIMESTAMP'                 || CHR(10) ||
            'WHEN NOT MATCHED THEN INSERT ('                     || CHR(10) ||
            '    PO_ID, PO_NUMBER, SUPPLIER_ID, CURRENCY_CODE, TOTAL_AMOUNT,' || CHR(10) ||
            '    STATUS, APPROVED_DATE, CREATED_BY, CREATION_DATE, LAST_SYNC_DATE' || CHR(10) ||
            ') VALUES ('                                         || CHR(10) ||
            '    s.PO_ID, s.PO_NUMBER, s.SUPPLIER_ID, s.CURRENCY_CODE, s.TOTAL_AMOUNT,' || CHR(10) ||
            '    s.STATUS, s.APPROVED_DATE, TO_CHAR(s.CREATED_BY), s.CREATION_DATE, SYSTIMESTAMP)';

        EXECUTE IMMEDIATE l_sql USING l_org, l_org;
        l_rows := SQL%ROWCOUNT;
        COMMIT;

        ATLAS_AUDIT_LOG_PKG.LOG_EVENT(
            p_event_type => 'EBS_SYNC_COMPLETE',
            p_resource_type => 'PURCHASE_ORDERS',
            p_action => 'SYNC',
            p_details => '{"status":"success","count":"' || l_rows || '"}'
        );
    EXCEPTION
        WHEN OTHERS THEN
            ATLAS_AUDIT_LOG_PKG.LOG_EVENT(
                p_event_type => 'EBS_SYNC_ERROR',
                p_resource_type => 'PURCHASE_ORDERS',
                p_action => 'SYNC',
                p_success => 'N',
                p_error_message => SQLERRM
            );
            RAISE;
    END SYNC_PURCHASE_ORDERS;

    -- ----------------------------------------------------------
    -- SYNC_AP_INVOICES — AP_INVOICES_ALL
    --
    -- EBS uses PAYMENT_STATUS_FLAG ('Y' fully paid, 'P' partial, 'N' unpaid).
    -- We map it to a human-readable code so the dashboard reads naturally.
    -- ----------------------------------------------------------
    PROCEDURE SYNC_AP_INVOICES IS
        l_sql CLOB;
        l_rows NUMBER;
        l_org VARCHAR2(50) := ATLAS_CONFIG_PKG.GET_EBS_ORG_ID;
    BEGIN
        ATLAS_AUDIT_LOG_PKG.LOG_EVENT(
            p_event_type => 'EBS_SYNC_START',
            p_resource_type => 'AP_INVOICES',
            p_action => 'SYNC'
        );

        l_sql :=
            'MERGE INTO ATLAS_AP_INVOICES a USING ('             || CHR(10) ||
            '    SELECT INVOICE_ID        AS INVOICE_ID,'        || CHR(10) ||
            '           INVOICE_NUM       AS INVOICE_NUMBER,'    || CHR(10) ||
            '           VENDOR_ID         AS SUPPLIER_ID,'       || CHR(10) ||
            '           INVOICE_DATE      AS INVOICE_DATE,'      || CHR(10) ||
            '           INVOICE_AMOUNT    AS INVOICE_AMOUNT,'    || CHR(10) ||
            '           AMOUNT_PAID       AS AMOUNT_PAID,'       || CHR(10) ||
            '           CASE PAYMENT_STATUS_FLAG'                || CHR(10) ||
            '             WHEN ''Y'' THEN ''PAID'''              || CHR(10) ||
            '             WHEN ''P'' THEN ''PARTIAL'''           || CHR(10) ||
            '             WHEN ''N'' THEN ''UNPAID'''            || CHR(10) ||
            '             ELSE PAYMENT_STATUS_FLAG END           AS PAYMENT_STATUS,' || CHR(10) ||
            '           INVOICE_CURRENCY_CODE AS CURRENCY_CODE,' || CHR(10) ||
            '           NVL(TERMS_DATE, INVOICE_DATE)            AS DUE_DATE' || CHR(10) ||
            '    FROM '   || REMOTE_REF('AP_INVOICES_ALL')       || CHR(10) ||
            '    WHERE (:p_org = ''0'' OR ORG_ID = TO_NUMBER(:p_org))' || CHR(10) ||
            ') s ON (a.INVOICE_ID = s.INVOICE_ID)'               || CHR(10) ||
            'WHEN MATCHED THEN UPDATE SET'                       || CHR(10) ||
            '    INVOICE_NUMBER  = s.INVOICE_NUMBER,'            || CHR(10) ||
            '    SUPPLIER_ID     = s.SUPPLIER_ID,'               || CHR(10) ||
            '    INVOICE_DATE    = s.INVOICE_DATE,'              || CHR(10) ||
            '    INVOICE_AMOUNT  = s.INVOICE_AMOUNT,'            || CHR(10) ||
            '    AMOUNT_PAID     = s.AMOUNT_PAID,'               || CHR(10) ||
            '    PAYMENT_STATUS  = s.PAYMENT_STATUS,'            || CHR(10) ||
            '    CURRENCY_CODE   = s.CURRENCY_CODE,'             || CHR(10) ||
            '    DUE_DATE        = s.DUE_DATE,'                  || CHR(10) ||
            '    LAST_SYNC_DATE  = SYSTIMESTAMP'                 || CHR(10) ||
            'WHEN NOT MATCHED THEN INSERT ('                     || CHR(10) ||
            '    INVOICE_ID, INVOICE_NUMBER, SUPPLIER_ID, INVOICE_DATE,' || CHR(10) ||
            '    INVOICE_AMOUNT, AMOUNT_PAID, PAYMENT_STATUS, CURRENCY_CODE,' || CHR(10) ||
            '    DUE_DATE, LAST_SYNC_DATE'                       || CHR(10) ||
            ') VALUES ('                                         || CHR(10) ||
            '    s.INVOICE_ID, s.INVOICE_NUMBER, s.SUPPLIER_ID, s.INVOICE_DATE,' || CHR(10) ||
            '    s.INVOICE_AMOUNT, s.AMOUNT_PAID, s.PAYMENT_STATUS, s.CURRENCY_CODE,' || CHR(10) ||
            '    s.DUE_DATE, SYSTIMESTAMP)';

        EXECUTE IMMEDIATE l_sql USING l_org, l_org;
        l_rows := SQL%ROWCOUNT;
        COMMIT;

        ATLAS_AUDIT_LOG_PKG.LOG_EVENT(
            p_event_type => 'EBS_SYNC_COMPLETE',
            p_resource_type => 'AP_INVOICES',
            p_action => 'SYNC',
            p_details => '{"status":"success","count":"' || l_rows || '"}'
        );
    EXCEPTION
        WHEN OTHERS THEN
            ATLAS_AUDIT_LOG_PKG.LOG_EVENT(
                p_event_type => 'EBS_SYNC_ERROR',
                p_resource_type => 'AP_INVOICES',
                p_action => 'SYNC',
                p_success => 'N',
                p_error_message => SQLERRM
            );
            RAISE;
    END SYNC_AP_INVOICES;

    -- ----------------------------------------------------------
    -- SYNC_GL_BALANCES — GL_BALANCES + GL_CODE_COMBINATIONS
    -- ----------------------------------------------------------
    PROCEDURE SYNC_GL_BALANCES IS
        l_sql CLOB;
        l_rows NUMBER;
        l_ledger VARCHAR2(50) := ATLAS_CONFIG_PKG.GET_EBS_LEDGER_ID;
    BEGIN
        ATLAS_AUDIT_LOG_PKG.LOG_EVENT(
            p_event_type => 'EBS_SYNC_START',
            p_resource_type => 'GL_BALANCES',
            p_action => 'SYNC'
        );

        -- BALANCE_ID is local-only; allocate from the existing sequence.
        -- We delete + insert per (ledger, period) range to keep the merge
        -- key simple, but for a first pass we use MERGE on a synthetic key.
        l_sql :=
            'MERGE INTO ATLAS_GL_BALANCES a USING ('             || CHR(10) ||
            '    SELECT b.LEDGER_ID,'                            || CHR(10) ||
            '           b.CODE_COMBINATION_ID,'                  || CHR(10) ||
            '           cc.SEGMENT1 || ''.'' || cc.SEGMENT2 || ''.'' || cc.SEGMENT3 AS ACCOUNT_CODE,' || CHR(10) ||
            '           cc.DESCRIPTION   AS ACCOUNT_DESCRIPTION,' || CHR(10) ||
            '           b.PERIOD_NAME    AS PERIOD_NAME,'        || CHR(10) ||
            '           b.CURRENCY_CODE  AS CURRENCY_CODE,'      || CHR(10) ||
            '           b.PERIOD_NET_DR  AS PERIOD_NET_DR,'      || CHR(10) ||
            '           b.PERIOD_NET_CR  AS PERIOD_NET_CR,'      || CHR(10) ||
            '           b.BEGIN_BALANCE_DR AS BEGIN_BALANCE_DR,' || CHR(10) ||
            '           b.BEGIN_BALANCE_CR AS BEGIN_BALANCE_CR'  || CHR(10) ||
            '    FROM '   || REMOTE_REF('GL_BALANCES')           || ' b' || CHR(10) ||
            '    JOIN '   || REMOTE_REF('GL_CODE_COMBINATIONS')  || ' cc' || CHR(10) ||
            '      ON cc.CODE_COMBINATION_ID = b.CODE_COMBINATION_ID' || CHR(10) ||
            '    WHERE (:p_ledger = ''0'' OR b.LEDGER_ID = TO_NUMBER(:p_ledger))' || CHR(10) ||
            ') s ON ('                                           || CHR(10) ||
            '    a.LEDGER_ID = s.LEDGER_ID'                      || CHR(10) ||
            '    AND a.ACCOUNT_CODE = s.ACCOUNT_CODE'            || CHR(10) ||
            '    AND a.PERIOD_NAME = s.PERIOD_NAME'              || CHR(10) ||
            '    AND NVL(a.CURRENCY_CODE, ''X'') = NVL(s.CURRENCY_CODE, ''X'')' || CHR(10) ||
            ')'                                                  || CHR(10) ||
            'WHEN MATCHED THEN UPDATE SET'                       || CHR(10) ||
            '    ACCOUNT_DESCRIPTION = s.ACCOUNT_DESCRIPTION,'   || CHR(10) ||
            '    PERIOD_NET_DR       = s.PERIOD_NET_DR,'         || CHR(10) ||
            '    PERIOD_NET_CR       = s.PERIOD_NET_CR,'         || CHR(10) ||
            '    BEGIN_BALANCE_DR    = s.BEGIN_BALANCE_DR,'      || CHR(10) ||
            '    BEGIN_BALANCE_CR    = s.BEGIN_BALANCE_CR,'      || CHR(10) ||
            '    LAST_SYNC_DATE      = SYSTIMESTAMP'             || CHR(10) ||
            'WHEN NOT MATCHED THEN INSERT ('                     || CHR(10) ||
            '    BALANCE_ID, LEDGER_ID, ACCOUNT_CODE, ACCOUNT_DESCRIPTION,' || CHR(10) ||
            '    PERIOD_NAME, CURRENCY_CODE, PERIOD_NET_DR, PERIOD_NET_CR,' || CHR(10) ||
            '    BEGIN_BALANCE_DR, BEGIN_BALANCE_CR, LAST_SYNC_DATE' || CHR(10) ||
            ') VALUES ('                                         || CHR(10) ||
            '    SEQ_ATLAS_GL_BALANCES.NEXTVAL, s.LEDGER_ID, s.ACCOUNT_CODE, s.ACCOUNT_DESCRIPTION,' || CHR(10) ||
            '    s.PERIOD_NAME, s.CURRENCY_CODE, s.PERIOD_NET_DR, s.PERIOD_NET_CR,' || CHR(10) ||
            '    s.BEGIN_BALANCE_DR, s.BEGIN_BALANCE_CR, SYSTIMESTAMP)';

        EXECUTE IMMEDIATE l_sql USING l_ledger, l_ledger;
        l_rows := SQL%ROWCOUNT;
        COMMIT;

        ATLAS_AUDIT_LOG_PKG.LOG_EVENT(
            p_event_type => 'EBS_SYNC_COMPLETE',
            p_resource_type => 'GL_BALANCES',
            p_action => 'SYNC',
            p_details => '{"status":"success","count":"' || l_rows || '"}'
        );
    EXCEPTION
        WHEN OTHERS THEN
            ATLAS_AUDIT_LOG_PKG.LOG_EVENT(
                p_event_type => 'EBS_SYNC_ERROR',
                p_resource_type => 'GL_BALANCES',
                p_action => 'SYNC',
                p_success => 'N',
                p_error_message => SQLERRM
            );
            RAISE;
    END SYNC_GL_BALANCES;

    -- ----------------------------------------------------------
    -- SYNC_ALL_EBS_DATA — orchestrator for the scheduled job
    --
    -- Order matters: locations & departments first so the FK targets
    -- on ATLAS_EMPLOYEES exist; suppliers before POs and invoices.
    -- ----------------------------------------------------------
    PROCEDURE SYNC_ALL_EBS_DATA IS
    BEGIN
        ASSERT_EBS_SOURCE;

        ATLAS_AUDIT_LOG_PKG.LOG_EVENT(
            p_event_type => 'EBS_FULL_SYNC_START',
            p_resource_type => 'ALL',
            p_action => 'SYNC'
        );
        SYNC_LOCATIONS;
        SYNC_DEPARTMENTS;
        SYNC_EMPLOYEES;
        SYNC_SUPPLIERS;
        SYNC_PURCHASE_ORDERS;
        SYNC_AP_INVOICES;
        SYNC_GL_BALANCES;
        ATLAS_AUDIT_LOG_PKG.LOG_EVENT(
            p_event_type => 'EBS_FULL_SYNC_COMPLETE',
            p_resource_type => 'ALL',
            p_action => 'SYNC'
        );
    EXCEPTION
        WHEN OTHERS THEN
            ATLAS_AUDIT_LOG_PKG.LOG_EVENT(
                p_event_type => 'EBS_FULL_SYNC_ERROR',
                p_resource_type => 'ALL',
                p_action => 'SYNC',
                p_success => 'N',
                p_error_message => SQLERRM
            );
            RAISE;
    END SYNC_ALL_EBS_DATA;

END ATLAS_EBS_SYNC_PKG;
/

GRANT EXECUTE ON ATLAS_EBS_SYNC_PKG TO PUBLIC;

-- Schedule a daily EBS sync. Disabled by default — operators flip
-- ATLAS_SOURCE_SYSTEM to "EBS" and then enable the job, so the Fusion
-- and EBS scheduled jobs never both fire on the same instance.
DECLARE
    l_exists NUMBER;
BEGIN
    SELECT COUNT(*) INTO l_exists
    FROM USER_SCHEDULER_JOBS
    WHERE JOB_NAME = 'ATLAS_DAILY_EBS_SYNC_JOB';

    IF l_exists = 0 THEN
        DBMS_SCHEDULER.CREATE_JOB(
            job_name        => 'ATLAS_DAILY_EBS_SYNC_JOB',
            job_type        => 'STORED_PROCEDURE',
            job_action      => 'ATLAS_EBS_SYNC_PKG.SYNC_ALL_EBS_DATA',
            start_date      => SYSTIMESTAMP,
            repeat_interval => 'FREQ=DAILY;INTERVAL=1',
            enabled         => FALSE,
            comments        => 'Daily synchronization of all Oracle EBS data for Atlas (disabled until ATLAS_SOURCE_SYSTEM=EBS).'
        );
    END IF;
END;
/

COMMIT;

BEGIN
    DBMS_OUTPUT.PUT_LINE('Oracle EBS Integration Deployed');
    DBMS_OUTPUT.PUT_LINE('   - ATLAS_EBS_SYNC_PKG installed');
    DBMS_OUTPUT.PUT_LINE('   - ATLAS_DAILY_EBS_SYNC_JOB created (disabled)');
    DBMS_OUTPUT.PUT_LINE('');
    DBMS_OUTPUT.PUT_LINE('Next steps:');
    DBMS_OUTPUT.PUT_LINE('   1. Create the EBS DB link (default name: EBS_PROD).');
    DBMS_OUTPUT.PUT_LINE('   2. ATLAS_CONFIG_PKG.SET_CONFIG_VALUE(''ATLAS_SOURCE_SYSTEM'', ''EBS'');');
    DBMS_OUTPUT.PUT_LINE('   3. EXEC DBMS_SCHEDULER.ENABLE(''ATLAS_DAILY_EBS_SYNC_JOB'');');
END;
/
