import oracledb
import os
import sys
from config import Config

# Database connection parameters from config.py
DB_USER = Config.DB_USER
DB_PASSWORD = Config.DB_PASSWORD
DB_DSN = Config.DB_DSN
WALLET_DIR = os.path.expanduser(Config.DB_WALLET_DIR)
WALLET_PASSWORD = Config.DB_WALLET_PASSWORD

# PL/SQL objects for the RAG pipeline and audit logging
PLSQL_OBJECTS = [
    # 1. ATLAS_AUDIT_LOG_PKG (Audit Logging Package)
    ("PACKAGE", "ATLAS_AUDIT_LOG_PKG", """
CREATE OR REPLACE PACKAGE ATLAS_AUDIT_LOG_PKG AS
    PRAGMA AUTONOMOUS_TRANSACTION;
    PROCEDURE LOG_EVENT(
        p_event_type    IN VARCHAR2,
        p_user_id       IN VARCHAR2 DEFAULT NULL,
        p_client_ip     IN VARCHAR2 DEFAULT NULL,
        p_resource_type IN VARCHAR2 DEFAULT NULL,
        p_action        IN VARCHAR2 DEFAULT NULL,
        p_details       IN CLOB DEFAULT NULL,
        p_success       IN VARCHAR2 DEFAULT 'Y',
        p_error_message IN VARCHAR2 DEFAULT NULL
    );
END ATLAS_AUDIT_LOG_PKG;
/

CREATE OR REPLACE PACKAGE BODY ATLAS_AUDIT_LOG_PKG AS
    PROCEDURE LOG_EVENT(
        p_event_type    IN VARCHAR2,
        p_user_id       IN VARCHAR2 DEFAULT NULL,
        p_client_ip     IN VARCHAR2 DEFAULT NULL,
        p_resource_type IN VARCHAR2 DEFAULT NULL,
        p_action        IN VARCHAR2 DEFAULT NULL,
        p_details       IN CLOB DEFAULT NULL,
        p_success       IN VARCHAR2 DEFAULT 'Y',
        p_error_message IN VARCHAR2 DEFAULT NULL
    )
    IS
    BEGIN
        INSERT INTO ATLAS_AUDIT_LOG (
            LOG_ID, EVENT_TYPE, USER_ID, CLIENT_IP, RESOURCE_TYPE,
            ACTION, DETAILS, SUCCESS, ERROR_MESSAGE, CREATED_DATE
        ) VALUES (
            SEQ_ATLAS_AUDIT_LOG.NEXTVAL, p_event_type, p_user_id, p_client_ip,
            p_resource_type, p_action, p_details, p_success, p_error_message, SYSTIMESTAMP
        );
        COMMIT;
    EXCEPTION
        WHEN OTHERS THEN
            ROLLBACK;
            RAISE;
    END LOG_EVENT;
END ATLAS_AUDIT_LOG_PKG;
/

GRANT EXECUTE ON ATLAS_AUDIT_LOG_PKG TO PUBLIC;
"""),

    # 2. ATLAS_VALIDATE_QUERY (Query Validation Function - MZX Security Mandate)
    ("FUNCTION", "ATLAS_VALIDATE_QUERY", """
CREATE OR REPLACE FUNCTION ATLAS_VALIDATE_QUERY(p_sql IN CLOB)
RETURN VARCHAR2
IS
    l_sql_upper VARCHAR2(32767);
    l_forbidden_keywords SYS.ODCIVARCHAR2LIST := SYS.ODCIVARCHAR2LIST(
        'INSERT', 'UPDATE', 'DELETE', 'DROP', 'ALTER', 'CREATE',
        'TRUNCATE', 'MERGE', 'GRANT', 'REVOKE', 'EXECUTE', 'CALL',
        'DBMS_', 'UTL_', 'EXEC', 'COMMIT', 'ROLLBACK'
    );
BEGIN
    l_sql_upper := UPPER(DBMS_LOB.SUBSTR(p_sql, 32767, 1));
    
    -- Check for forbidden keywords
    FOR i IN 1..l_forbidden_keywords.COUNT LOOP
        IF REGEXP_LIKE(l_sql_upper, '(^|\\s|\\()'||l_forbidden_keywords(i)||'(\\s|\\(|$)' ) THEN
            RETURN 'BLOCKED: Query contains forbidden keyword: ' || l_forbidden_keywords(i);
        END IF;
    END LOOP;
    
    -- Ensure query starts with SELECT
    IF NOT REGEXP_LIKE(TRIM(l_sql_upper), '^SELECT\\s') THEN
        RETURN 'BLOCKED: Only SELECT queries are allowed';
    END IF;
    
    RETURN 'VALID';
END ATLAS_VALIDATE_QUERY;
/
GRANT EXECUTE ON ATLAS_VALIDATE_QUERY TO PUBLIC;
"""),

    # 3. ATLAS_GET_SCHEMA_CONTEXT (Schema Context Function for RAG)
    ("FUNCTION", "ATLAS_GET_SCHEMA_CONTEXT", """
CREATE OR REPLACE FUNCTION ATLAS_GET_SCHEMA_CONTEXT
RETURN CLOB
IS
    l_context CLOB := '';
BEGIN
    l_context := 'Available Tables in Atlas Schema:' || CHR(10) || CHR(10);
    
    FOR tbl IN (
        SELECT table_name, comments 
        FROM user_tab_comments 
        WHERE table_name LIKE 'ATLAS%'
        ORDER BY table_name
    ) LOOP
        l_context := l_context || 'Table: ' || tbl.table_name;
        IF tbl.comments IS NOT NULL THEN
            l_context := l_context || ' - ' || tbl.comments;
        END IF;
        l_context := l_context || CHR(10);
        
        FOR col IN (
            SELECT column_name, data_type, data_length, nullable
            FROM user_tab_columns
            WHERE table_name = tbl.table_name
            ORDER BY column_id
        ) LOOP
            l_context := l_context || '  - ' || col.column_name || ' (' || col.data_type;
            IF col.data_length IS NOT NULL AND col.data_type IN ('VARCHAR2', 'CHAR', 'NVARCHAR2') THEN
                l_context := l_context || '(' || col.data_length || ')';
            END IF;
            l_context := l_context || ')' || CHR(10);
        END LOOP;
        l_context := l_context || CHR(10);
    END LOOP;
    
    RETURN l_context;
END ATLAS_GET_SCHEMA_CONTEXT;
/
GRANT EXECUTE ON ATLAS_GET_SCHEMA_CONTEXT TO PUBLIC;
"""),

    # 4. ATLAS_INGEST_DOCUMENT (Document Ingestion Procedure)
    ("PROCEDURE", "ATLAS_INGEST_DOCUMENT", """
CREATE OR REPLACE PROCEDURE ATLAS_INGEST_DOCUMENT(
    p_document_name       IN VARCHAR2,
    p_document_type       IN VARCHAR2,
    p_source_system       IN VARCHAR2,
    p_object_storage_path IN VARCHAR2,
    p_text_content        IN CLOB
)
IS
    l_document_id   NUMBER;
    l_chunk_id      NUMBER;
    l_chunk_text    CLOB;
    l_chunk_seq     NUMBER := 0;
    l_chunk_size    NUMBER := 1000;
    l_overlap       NUMBER := 100;
    l_start_pos     NUMBER := 1;
    l_text_length   NUMBER;
BEGIN
    -- Insert document metadata
    SELECT SEQ_ATLAS_DOCUMENTS.NEXTVAL INTO l_document_id FROM DUAL;

    INSERT INTO ATLAS_DOCUMENTS (
        DOCUMENT_ID, DOCUMENT_NAME, DOCUMENT_TYPE, SOURCE_SYSTEM,
        OBJECT_STORAGE_PATH, CREATED_DATE
    ) VALUES (
        l_document_id, p_document_name, p_document_type, p_source_system,
        p_object_storage_path, SYSTIMESTAMP
    );

    -- Chunk the text
    l_text_length := NVL(DBMS_LOB.GETLENGTH(p_text_content), 0);

    WHILE l_start_pos < l_text_length LOOP
        l_chunk_seq := l_chunk_seq + 1;
        l_chunk_text := DBMS_LOB.SUBSTR(p_text_content, l_chunk_size, l_start_pos);

        SELECT SEQ_ATLAS_CHUNKS.NEXTVAL INTO l_chunk_id FROM DUAL;

        INSERT INTO ATLAS_DOCUMENT_CHUNKS (
            CHUNK_ID, DOCUMENT_ID, CHUNK_TEXT, CHUNK_SEQUENCE, CREATED_DATE
        ) VALUES (
            l_chunk_id, l_document_id, l_chunk_text, l_chunk_seq, SYSTIMESTAMP
        );

        l_start_pos := l_start_pos + l_chunk_size - l_overlap;
    END LOOP;

    -- Log the ingestion
    ATLAS_AUDIT_LOG_PKG.LOG_EVENT(
        p_event_type => 'DOCUMENT_INGESTED',
        p_user_id => USER,
        p_resource_type => 'DOCUMENT',
        p_action => 'INGEST',
        p_details => '{"document_id": ' || l_document_id || ', "chunks": ' || l_chunk_seq || '}'
    );

    COMMIT;

EXCEPTION
    WHEN OTHERS THEN
        ROLLBACK;
        ATLAS_AUDIT_LOG_PKG.LOG_EVENT(
            p_event_type => 'DOCUMENT_INGESTION_FAILED',
            p_user_id => USER,
            p_resource_type => 'DOCUMENT',
            p_action => 'INGEST',
            p_success => 'N',
            p_error_message => SQLERRM
        );
        RAISE;
END ATLAS_INGEST_DOCUMENT;
/
GRANT EXECUTE ON ATLAS_INGEST_DOCUMENT TO PUBLIC;
"""),

    # 5. ATLAS_EXECUTE_SAFE_QUERY (Safe Query Execution Function)
    ("FUNCTION", "ATLAS_EXECUTE_SAFE_QUERY", """
CREATE OR REPLACE FUNCTION ATLAS_EXECUTE_SAFE_QUERY(
    p_sql     IN CLOB,
    p_user_id IN VARCHAR2 DEFAULT NULL
)
RETURN SYS_REFCURSOR
IS
    l_validation VARCHAR2(4000);
    l_cursor     SYS_REFCURSOR;
BEGIN
    -- Validate the query first
    l_validation := ATLAS_VALIDATE_QUERY(p_sql);
    
    IF l_validation != 'VALID' THEN
        -- Log blocked query
        ATLAS_AUDIT_LOG_PKG.LOG_EVENT(
            p_event_type => 'QUERY_BLOCKED',
            p_user_id => p_user_id,
            p_resource_type => 'QUERY',
            p_action => 'EXECUTE',
            p_details => DBMS_LOB.SUBSTR(p_sql, 4000, 1),
            p_success => 'N',
            p_error_message => l_validation
        );
        RAISE_APPLICATION_ERROR(-20001, l_validation);
    END IF;
    
    -- Execute the validated query
    OPEN l_cursor FOR p_sql;
    
    -- Log successful execution
    ATLAS_AUDIT_LOG_PKG.LOG_EVENT(
        p_event_type => 'QUERY_EXECUTED',
        p_user_id => p_user_id,
        p_resource_type => 'QUERY',
        p_action => 'EXECUTE',
        p_details => DBMS_LOB.SUBSTR(p_sql, 4000, 1)
    );
    
    RETURN l_cursor;
    
EXCEPTION
    WHEN OTHERS THEN
        IF l_validation = 'VALID' THEN
            ATLAS_AUDIT_LOG_PKG.LOG_EVENT(
                p_event_type => 'QUERY_ERROR',
                p_user_id => p_user_id,
                p_resource_type => 'QUERY',
                p_action => 'EXECUTE',
                p_details => DBMS_LOB.SUBSTR(p_sql, 4000, 1),
                p_success => 'N',
                p_error_message => SQLERRM
            );
        END IF;
        RAISE;
END ATLAS_EXECUTE_SAFE_QUERY;
/
GRANT EXECUTE ON ATLAS_EXECUTE_SAFE_QUERY TO PUBLIC;
"""),

    # 6. ATLAS_GET_ALERTS (Proactive Alerts Function)
    ("FUNCTION", "ATLAS_GET_ALERTS", """
CREATE OR REPLACE FUNCTION ATLAS_GET_ALERTS
RETURN CLOB
IS
    l_alerts CLOB := '[]';
    l_past_due_count NUMBER := 0;
    l_high_po_count NUMBER := 0;
    l_pending_invoices NUMBER := 0;
BEGIN
    -- Check for past due invoices
    BEGIN
        SELECT COUNT(*) INTO l_past_due_count
        FROM ATLAS_AP_INVOICES
        WHERE DUE_DATE < SYSDATE AND PAYMENT_STATUS = 'UNPAID';
    EXCEPTION
        WHEN OTHERS THEN l_past_due_count := 0;
    END;

    -- Check for high-value pending POs
    BEGIN
        SELECT COUNT(*) INTO l_high_po_count
        FROM ATLAS_PURCHASE_ORDERS
        WHERE TOTAL_AMOUNT > 100000 AND STATUS = 'PENDING';
    EXCEPTION
        WHEN OTHERS THEN l_high_po_count := 0;
    END;
    
    -- Check for pending invoices
    BEGIN
        SELECT COUNT(*) INTO l_pending_invoices
        FROM ATLAS_AP_INVOICES
        WHERE PAYMENT_STATUS = 'PENDING';
    EXCEPTION
        WHEN OTHERS THEN l_pending_invoices := 0;
    END;

    -- Build JSON array of alerts
    l_alerts := '[';
    
    IF l_past_due_count > 0 THEN
        l_alerts := l_alerts || '{"type":"warning","message":"' || l_past_due_count || ' invoices are past due","count":' || l_past_due_count || '}';
    END IF;
    
    IF l_high_po_count > 0 THEN
        IF LENGTH(l_alerts) > 1 THEN l_alerts := l_alerts || ','; END IF;
        l_alerts := l_alerts || '{"type":"info","message":"' || l_high_po_count || ' high-value POs pending approval","count":' || l_high_po_count || '}';
    END IF;
    
    IF l_pending_invoices > 0 THEN
        IF LENGTH(l_alerts) > 1 THEN l_alerts := l_alerts || ','; END IF;
        l_alerts := l_alerts || '{"type":"info","message":"' || l_pending_invoices || ' invoices pending processing","count":' || l_pending_invoices || '}';
    END IF;
    
    l_alerts := l_alerts || ']';
    
    RETURN l_alerts;
END ATLAS_GET_ALERTS;
/
GRANT EXECUTE ON ATLAS_GET_ALERTS TO PUBLIC;
"""),
]

def main():
    print("=" * 60)
    print("Atlas on OCI - RAG Pipeline Deployment")
    print("=" * 60)
    
    try:
        print(f"\nConnecting to ATP database...")
        connection = oracledb.connect(
            user=DB_USER,
            password=DB_PASSWORD,
            dsn=DB_DSN,
            config_dir=WALLET_DIR,
            wallet_location=WALLET_DIR,
            wallet_password=WALLET_PASSWORD
        )
        print("✅ Connected successfully!")
        
        cursor = connection.cursor()
        
        success_count = 0
        error_count = 0
        
        for obj_type, obj_name, ddl in PLSQL_OBJECTS:
            try:
                cursor.execute(ddl)
                connection.commit()
                print(f"  ✅ {obj_type} {obj_name} created")
                success_count += 1
            except oracledb.DatabaseError as e:
                error = e.args[0]
                print(f"  ❌ {obj_type} {obj_name}: {error}")
                error_count += 1
        
        # Verify the validate_query function works
        print("\n" + "=" * 60)
        print("Testing ATLAS_VALIDATE_QUERY (MZX Security Mandate)")
        print("=" * 60)
        
        test_queries = [
            ("SELECT * FROM ATLAS_EMPLOYEES", "VALID"),
            ("SELECT COUNT(*) FROM ATLAS_DEPARTMENTS WHERE DEPARTMENT_ID = 1", "VALID"),
            ("INSERT INTO ATLAS_EMPLOYEES VALUES (1, 'TEST', 'Test', NULL, NULL, NULL, NULL, NULL, NULL, NULL, SYSTIMESTAMP)", "BLOCKED"),
            ("DELETE FROM ATLAS_EMPLOYEES", "BLOCKED"),
            ("DROP TABLE ATLAS_EMPLOYEES", "BLOCKED"),
            ("UPDATE ATLAS_EMPLOYEES SET FULL_NAME = 'Hacked'", "BLOCKED"),
            ("EXEC DBMS_OUTPUT.PUT_LINE('test')", "BLOCKED"),
        ]
        
        for query, expected in test_queries:
            cursor.execute("SELECT ATLAS_VALIDATE_QUERY(:1) FROM DUAL", [query])
            result = cursor.fetchone()[0]
            status = "✅" if (expected == "VALID" and result == "VALID") or (expected == "BLOCKED" and "BLOCKED" in result) else "❌"
            print(f"  {status} {expected}: {query[:50]}...")
        
        cursor.close()
        connection.close()
        
        print("\n" + "=" * 60)
        print(f"RAG Pipeline Deployment Complete")
        print(f"  Success: {success_count}")
        print(f"  Errors:  {error_count}")
        print("=" * 60)
        
        return 0 if error_count == 0 else 1
        
    except oracledb.Error as e:
        print(f"\n❌ Database connection error: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
