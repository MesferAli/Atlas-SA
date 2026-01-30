-- Atlas APEX Application - REST Data Source: FUSION_HCM_WORKERS
-- This script defines the REST Data Source for fetching worker data from Oracle Fusion HCM.
--
-- Note: This is a conceptual definition. REST Data Sources are typically
-- configured through the APEX Application Builder.

-- ============================================================
-- REST Data Source Definition
-- ============================================================

/*
Name: FUSION_HCM_WORKERS
Type: REST Data Source
Static ID: FUSION_HCM_WORKERS

Remote Server:
  Name: Oracle Fusion HCM
  Base URL: https://<your_fusion_host>/hcmRestApi/resources/11.13.18.05
  Authentication Type: OAuth2 - Client Credentials

Service:
  URL Pattern: /workers
  HTTP Method: GET
  Pagination Type: Offset-Fetch (Oracle REST Standard)
  Pagination Size: 100

Operations:
  - GET Collection (fetch all workers)
  - GET Single (fetch a single worker by PersonId)

Parameters:
  - q (Query): Used for filtering (e.g., q=PersonNumber='EMP001')
  - expand (Expand): Used to include related resources (e.g., expand=assignments)
  - fields (Fields): Used to select specific fields
  - limit (Limit): Number of records per page
  - offset (Offset): Starting record for pagination

Response Mapping (Data Profile):
  - PERSON_ID: PersonId (NUMBER)
  - PERSON_NUMBER: PersonNumber (VARCHAR2)
  - FULL_NAME: DisplayName (VARCHAR2)
  - HIRE_DATE: OriginalDateOfHire (DATE)
  - ... (other fields as needed)
*/

-- ============================================================
-- Web Credentials for OAuth2
-- ============================================================

/*
Credential Name: FUSION_HCM_OAUTH
Authentication Type: OAuth2 Client Credentials
Client ID: <your_client_id>
Client Secret: <your_client_secret>
Token URL: https://<your_fusion_host>/oauth2/v1/token
Scope: (leave blank or as required by Fusion)
*/

-- ============================================================
-- Synchronization PL/SQL Block
-- ============================================================

-- This PL/SQL block can be used in an APEX Automation or scheduled job
-- to synchronize data from Fusion to the local ATLAS_EMPLOYEES table.

DECLARE
    l_context       APEX_EXEC.T_CONTEXT;
    l_person_id     NUMBER;
    l_person_number VARCHAR2(30);
    l_full_name     VARCHAR2(240);
    l_hire_date     DATE;
    l_sync_count    NUMBER := 0;
BEGIN
    -- Open the REST Data Source
    l_context := APEX_EXEC.OPEN_REST_SOURCE_QUERY(
        p_static_id         => 'FUSION_HCM_WORKERS',
        p_max_rows          => 10000 -- Adjust as needed
    );

    -- Loop through the results
    WHILE APEX_EXEC.NEXT_ROW(l_context) LOOP
        l_person_id     := APEX_EXEC.GET_NUMBER(l_context, 'PERSON_ID');
        l_person_number := APEX_EXEC.GET_VARCHAR2(l_context, 'PERSON_NUMBER');
        l_full_name     := APEX_EXEC.GET_VARCHAR2(l_context, 'FULL_NAME');
        l_hire_date     := APEX_EXEC.GET_DATE(l_context, 'HIRE_DATE');

        -- Upsert into ATLAS_EMPLOYEES
        MERGE INTO ATLAS_EMPLOYEES tgt
        USING (SELECT l_person_id AS EMPLOYEE_ID FROM DUAL) src
        ON (tgt.EMPLOYEE_ID = src.EMPLOYEE_ID)
        WHEN MATCHED THEN
            UPDATE SET
                tgt.EMPLOYEE_NUMBER = l_person_number,
                tgt.FULL_NAME = l_full_name,
                tgt.HIRE_DATE = l_hire_date,
                tgt.LAST_SYNC_DATE = SYSTIMESTAMP
        WHEN NOT MATCHED THEN
            INSERT (EMPLOYEE_ID, EMPLOYEE_NUMBER, FULL_NAME, HIRE_DATE, LAST_SYNC_DATE)
            VALUES (l_person_id, l_person_number, l_full_name, l_hire_date, SYSTIMESTAMP);

        l_sync_count := l_sync_count + 1;
    END LOOP;

    -- Close the context
    APEX_EXEC.CLOSE(l_context);

    -- Log the sync operation
    INSERT INTO ATLAS_AUDIT_LOG (
        LOG_ID, EVENT_TYPE, USER_ID, ACTION, DETAILS, SUCCESS, CREATED_DATE
    ) VALUES (
        SEQ_ATLAS_AUDIT_LOG.NEXTVAL,
        'DATA_SYNC',
        'SYSTEM',
        'SYNC_EMPLOYEES',
        '{"records_synced": ' || l_sync_count || '}',
        'Y',
        SYSTIMESTAMP
    );

    COMMIT;

EXCEPTION
    WHEN OTHERS THEN
        APEX_EXEC.CLOSE(l_context);
        -- Log the error
        INSERT INTO ATLAS_AUDIT_LOG (
            LOG_ID, EVENT_TYPE, USER_ID, ACTION, DETAILS, SUCCESS, ERROR_MESSAGE, CREATED_DATE
        ) VALUES (
            SEQ_ATLAS_AUDIT_LOG.NEXTVAL,
            'DATA_SYNC',
            'SYSTEM',
            'SYNC_EMPLOYEES',
            '{}',
            'N',
            SQLERRM,
            SYSTIMESTAMP
        );
        COMMIT;
        RAISE;
END;
/
