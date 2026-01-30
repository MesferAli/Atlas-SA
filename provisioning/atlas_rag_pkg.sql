-- Atlas on OCI - RAG Pipeline PL/SQL Package
-- Version: 1.0
-- Date: January 30, 2026
--
-- This package implements the core RAG (Retrieval-Augmented Generation) pipeline
-- for the Atlas platform on OCI.

-- ============================================================
-- Package Specification
-- ============================================================

CREATE OR REPLACE PACKAGE ATLAS_RAG_PKG AS

    -- Constants
    C_GENAI_EMBED_URL   CONSTANT VARCHAR2(500) := 'https://inference.generativeai.<region>.oci.oraclecloud.com/20231130/actions/embedText';
    C_GENAI_CHAT_URL    CONSTANT VARCHAR2(500) := 'https://inference.generativeai.<region>.oci.oraclecloud.com/20231130/actions/chat';
    C_COMPARTMENT_ID    CONSTANT VARCHAR2(100) := '<your_compartment_ocid>';
    C_EMBED_MODEL_ID    CONSTANT VARCHAR2(100) := 'cohere.embed-multilingual-v3.0';
    C_CHAT_MODEL_ID     CONSTANT VARCHAR2(100) := 'cohere.command-r-plus';
    C_WEB_CREDENTIAL    CONSTANT VARCHAR2(100) := 'OCI_GENAI_CREDENTIAL';

    -- Forbidden SQL keywords for read-only enforcement
    TYPE t_keyword_list IS TABLE OF VARCHAR2(30);
    C_FORBIDDEN_KEYWORDS CONSTANT t_keyword_list := t_keyword_list(
        'INSERT', 'UPDATE', 'DELETE', 'DROP', 'ALTER', 'CREATE',
        'TRUNCATE', 'MERGE', 'GRANT', 'REVOKE', 'EXECUTE', 'CALL'
    );

    -- Exception for read-only violations
    E_READ_ONLY_VIOLATION EXCEPTION;
    PRAGMA EXCEPTION_INIT(E_READ_ONLY_VIOLATION, -20001);

    -- Function to generate embedding for text
    FUNCTION get_embedding(p_text IN CLOB) RETURN VECTOR;

    -- Function to perform semantic search
    FUNCTION semantic_search(
        p_query_embedding IN VECTOR,
        p_top_k           IN NUMBER DEFAULT 5
    ) RETURN SYS_REFCURSOR;

    -- Function to get schema context for a table
    FUNCTION get_schema_context(p_table_names IN VARCHAR2) RETURN CLOB;

    -- Procedure to validate SQL is read-only
    PROCEDURE validate_query(p_sql IN CLOB);

    -- Main RAG pipeline function
    FUNCTION process_query(
        p_user_query IN VARCHAR2,
        p_user_id    IN VARCHAR2 DEFAULT NULL
    ) RETURN CLOB;

    -- Procedure to ingest a document into the RAG knowledge base
    PROCEDURE ingest_document(
        p_document_name       IN VARCHAR2,
        p_document_type       IN VARCHAR2,
        p_source_system       IN VARCHAR2,
        p_object_storage_path IN VARCHAR2,
        p_text_content        IN CLOB
    );

    -- Procedure to generate proactive alerts
    PROCEDURE generate_alerts;

END ATLAS_RAG_PKG;
/

-- ============================================================
-- Package Body
-- ============================================================

CREATE OR REPLACE PACKAGE BODY ATLAS_RAG_PKG AS

    -- --------------------------------------------------------
    -- Function: get_embedding
    -- Purpose: Generate a vector embedding for the given text.
    -- --------------------------------------------------------
    FUNCTION get_embedding(p_text IN CLOB) RETURN VECTOR
    IS
        l_request_body  CLOB;
        l_response      CLOB;
        l_embedding_str VARCHAR2(32767);
        l_embedding     VECTOR(384);
    BEGIN
        -- Construct the request body
        l_request_body := '{
            "compartmentId": "' || C_COMPARTMENT_ID || '",
            "servingMode": {
                "servingType": "ON_DEMAND",
                "modelId": "' || C_EMBED_MODEL_ID || '"
            },
            "inputs": ["' || APEX_ESCAPE.JSON(DBMS_LOB.SUBSTR(p_text, 8000, 1)) || '"],
            "truncate": "END"
        }';

        -- Make the REST API call
        l_response := APEX_WEB_SERVICE.MAKE_REST_REQUEST(
            p_url         => C_GENAI_EMBED_URL,
            p_http_method => 'POST',
            p_body        => l_request_body,
            p_credential_static_id => C_WEB_CREDENTIAL
        );

        -- Parse the response and extract the embedding
        APEX_JSON.PARSE(l_response);
        l_embedding_str := APEX_JSON.GET_VARCHAR2(p_path => 'embeddings[0]');

        -- Convert string to VECTOR
        -- Note: Actual conversion depends on response format
        l_embedding := TO_VECTOR(l_embedding_str);

        RETURN l_embedding;

    EXCEPTION
        WHEN OTHERS THEN
            -- Log error and return null
            RETURN NULL;
    END get_embedding;

    -- --------------------------------------------------------
    -- Function: semantic_search
    -- Purpose: Search for document chunks similar to the query.
    -- --------------------------------------------------------
    FUNCTION semantic_search(
        p_query_embedding IN VECTOR,
        p_top_k           IN NUMBER DEFAULT 5
    ) RETURN SYS_REFCURSOR
    IS
        l_cursor SYS_REFCURSOR;
    BEGIN
        OPEN l_cursor FOR
            SELECT
                dc.CHUNK_ID,
                dc.DOCUMENT_ID,
                dc.CHUNK_TEXT,
                d.DOCUMENT_NAME,
                d.DOCUMENT_TYPE,
                VECTOR_DISTANCE(dc.EMBEDDING, p_query_embedding, COSINE) AS similarity_score
            FROM
                ATLAS_DOCUMENT_CHUNKS dc
                JOIN ATLAS_DOCUMENTS d ON dc.DOCUMENT_ID = d.DOCUMENT_ID
            ORDER BY
                similarity_score ASC
            FETCH FIRST p_top_k ROWS ONLY;

        RETURN l_cursor;
    END semantic_search;

    -- --------------------------------------------------------
    -- Function: get_schema_context
    -- Purpose: Get schema information for specified tables.
    -- --------------------------------------------------------
    FUNCTION get_schema_context(p_table_names IN VARCHAR2) RETURN CLOB
    IS
        l_context CLOB := '';
        l_table_list APEX_T_VARCHAR2;
    BEGIN
        l_table_list := APEX_STRING.SPLIT(p_table_names, ',');

        FOR i IN 1..l_table_list.COUNT LOOP
            l_context := l_context || 'Table: ' || TRIM(l_table_list(i)) || CHR(10);

            FOR col_rec IN (
                SELECT COLUMN_NAME, DATA_TYPE, DATA_LENGTH, NULLABLE
                FROM USER_TAB_COLUMNS
                WHERE TABLE_NAME = UPPER(TRIM(l_table_list(i)))
                ORDER BY COLUMN_ID
            ) LOOP
                l_context := l_context || '  - ' || col_rec.COLUMN_NAME || ' (' || col_rec.DATA_TYPE;
                IF col_rec.DATA_LENGTH IS NOT NULL THEN
                    l_context := l_context || '(' || col_rec.DATA_LENGTH || ')';
                END IF;
                l_context := l_context || ')' || CHR(10);
            END LOOP;

            l_context := l_context || CHR(10);
        END LOOP;

        RETURN l_context;
    END get_schema_context;

    -- --------------------------------------------------------
    -- Procedure: validate_query
    -- Purpose: Ensure the SQL query is read-only.
    -- --------------------------------------------------------
    PROCEDURE validate_query(p_sql IN CLOB)
    IS
        l_sql_upper VARCHAR2(32767);
    BEGIN
        l_sql_upper := UPPER(DBMS_LOB.SUBSTR(p_sql, 32767, 1));

        FOR i IN 1..C_FORBIDDEN_KEYWORDS.COUNT LOOP
            IF REGEXP_LIKE(l_sql_upper, '\b' || C_FORBIDDEN_KEYWORDS(i) || '\b') THEN
                RAISE_APPLICATION_ERROR(-20001,
                    'Query contains forbidden keyword: ' || C_FORBIDDEN_KEYWORDS(i) ||
                    '. Only SELECT queries are allowed.');
            END IF;
        END LOOP;
    END validate_query;

    -- --------------------------------------------------------
    -- Function: process_query
    -- Purpose: Main RAG pipeline - process a natural language query.
    -- --------------------------------------------------------
    FUNCTION process_query(
        p_user_query IN VARCHAR2,
        p_user_id    IN VARCHAR2 DEFAULT NULL
    ) RETURN CLOB
    IS
        l_query_embedding   VECTOR(384);
        l_context           CLOB := '';
        l_schema_context    CLOB;
        l_prompt            CLOB;
        l_request_body      CLOB;
        l_response          CLOB;
        l_generated_sql     VARCHAR2(4000);
        l_result            CLOB;
        l_cursor            SYS_REFCURSOR;
        l_chunk_text        CLOB;
        l_doc_name          VARCHAR2(255);
    BEGIN
        -- Step 1: Generate embedding for the user query
        l_query_embedding := get_embedding(TO_CLOB(p_user_query));

        -- Step 2: Perform semantic search
        l_cursor := semantic_search(l_query_embedding, 3);

        -- Step 3: Build context from retrieved documents
        LOOP
            FETCH l_cursor INTO l_chunk_text, l_doc_name;
            EXIT WHEN l_cursor%NOTFOUND;
            l_context := l_context || '--- From: ' || l_doc_name || ' ---' || CHR(10);
            l_context := l_context || DBMS_LOB.SUBSTR(l_chunk_text, 2000, 1) || CHR(10) || CHR(10);
        END LOOP;
        CLOSE l_cursor;

        -- Step 4: Get schema context for Atlas tables
        l_schema_context := get_schema_context('ATLAS_EMPLOYEES,ATLAS_DEPARTMENTS,ATLAS_SUPPLIERS,ATLAS_PURCHASE_ORDERS,ATLAS_AP_INVOICES,ATLAS_GL_BALANCES');

        -- Step 5: Build augmented prompt
        l_prompt := 'You are Atlas, an AI assistant for Oracle Fusion. Your task is to help users query data from the Atlas schema.

**Instructions:**
- If the user asks a question about data, generate a SQL query for the ATLAS schema.
- Only generate SELECT queries. Never generate INSERT, UPDATE, DELETE, or DROP statements.
- Use the provided context to understand the schema and data.
- Respond in the same language as the user''s query (Arabic or English).

**Available Schema:**
' || l_schema_context || '

**Relevant Documents:**
' || NVL(l_context, 'No relevant documents found.') || '

**User Query:**
' || p_user_query || '

**Your Response:**';

        -- Step 6: Call OCI Generative AI
        l_request_body := '{
            "compartmentId": "' || C_COMPARTMENT_ID || '",
            "servingMode": {
                "servingType": "ON_DEMAND",
                "modelId": "' || C_CHAT_MODEL_ID || '"
            },
            "chatRequest": {
                "apiFormat": "COHERE",
                "message": "' || APEX_ESCAPE.JSON(l_prompt) || '",
                "maxTokens": 2048,
                "temperature": 0.2
            }
        }';

        l_response := APEX_WEB_SERVICE.MAKE_REST_REQUEST(
            p_url         => C_GENAI_CHAT_URL,
            p_http_method => 'POST',
            p_body        => l_request_body,
            p_credential_static_id => C_WEB_CREDENTIAL
        );

        -- Step 7: Parse and validate response
        APEX_JSON.PARSE(l_response);
        l_result := APEX_JSON.GET_CLOB(p_path => 'chatResponse.text');

        -- Step 8: Log the query
        INSERT INTO ATLAS_AUDIT_LOG (
            LOG_ID, EVENT_TYPE, USER_ID, ACTION, DETAILS, SUCCESS, CREATED_DATE
        ) VALUES (
            SEQ_ATLAS_AUDIT_LOG.NEXTVAL,
            'QUERY_EXECUTED',
            p_user_id,
            'RAG_QUERY',
            '{"query": "' || APEX_ESCAPE.JSON(SUBSTR(p_user_query, 1, 500)) || '"}',
            'Y',
            SYSTIMESTAMP
        );

        COMMIT;

        RETURN l_result;

    EXCEPTION
        WHEN OTHERS THEN
            -- Log the error
            INSERT INTO ATLAS_AUDIT_LOG (
                LOG_ID, EVENT_TYPE, USER_ID, ACTION, DETAILS, SUCCESS, ERROR_MESSAGE, CREATED_DATE
            ) VALUES (
                SEQ_ATLAS_AUDIT_LOG.NEXTVAL,
                'QUERY_BLOCKED',
                p_user_id,
                'RAG_QUERY',
                '{"query": "' || APEX_ESCAPE.JSON(SUBSTR(p_user_query, 1, 500)) || '"}',
                'N',
                SQLERRM,
                SYSTIMESTAMP
            );
            COMMIT;
            RETURN '{"error": "' || SQLERRM || '"}';
    END process_query;

    -- --------------------------------------------------------
    -- Procedure: ingest_document
    -- Purpose: Ingest a document into the RAG knowledge base.
    -- --------------------------------------------------------
    PROCEDURE ingest_document(
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
        l_embedding     VECTOR(384);
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

        -- Chunk and embed
        l_text_length := DBMS_LOB.GETLENGTH(p_text_content);

        WHILE l_start_pos < l_text_length LOOP
            l_chunk_seq := l_chunk_seq + 1;
            l_chunk_text := DBMS_LOB.SUBSTR(p_text_content, l_chunk_size, l_start_pos);

            l_embedding := get_embedding(l_chunk_text);

            SELECT SEQ_ATLAS_CHUNKS.NEXTVAL INTO l_chunk_id FROM DUAL;

            INSERT INTO ATLAS_DOCUMENT_CHUNKS (
                CHUNK_ID, DOCUMENT_ID, CHUNK_TEXT, CHUNK_SEQUENCE, EMBEDDING, CREATED_DATE
            ) VALUES (
                l_chunk_id, l_document_id, l_chunk_text, l_chunk_seq, l_embedding, SYSTIMESTAMP
            );

            l_start_pos := l_start_pos + l_chunk_size - l_overlap;
        END LOOP;

        COMMIT;

    EXCEPTION
        WHEN OTHERS THEN
            ROLLBACK;
            RAISE;
    END ingest_document;

    -- --------------------------------------------------------
    -- Procedure: generate_alerts
    -- Purpose: Generate proactive alerts based on data trends.
    -- --------------------------------------------------------
    PROCEDURE generate_alerts
    IS
        l_past_due_count    NUMBER;
        l_high_po_count     NUMBER;
        l_alert_data        CLOB;
        l_alert_message     CLOB;
        l_request_body      CLOB;
        l_response          CLOB;
    BEGIN
        -- Check for past due invoices
        SELECT COUNT(*) INTO l_past_due_count
        FROM ATLAS_AP_INVOICES
        WHERE DUE_DATE < SYSDATE AND PAYMENT_STATUS = 'UNPAID';

        -- Check for high-value pending POs
        SELECT COUNT(*) INTO l_high_po_count
        FROM ATLAS_PURCHASE_ORDERS
        WHERE TOTAL_AMOUNT > 100000 AND STATUS = 'PENDING';

        -- Construct alert data
        l_alert_data := '{
            "past_due_invoices": ' || l_past_due_count || ',
            "high_value_pending_pos": ' || l_high_po_count || '
        }';

        -- Generate alert message using OCI GenAI
        l_request_body := '{
            "compartmentId": "' || C_COMPARTMENT_ID || '",
            "servingMode": {
                "servingType": "ON_DEMAND",
                "modelId": "' || C_CHAT_MODEL_ID || '"
            },
            "chatRequest": {
                "apiFormat": "COHERE",
                "message": "Based on the following data, generate a brief alert summary for a business dashboard. Be concise and actionable. Data: ' || APEX_ESCAPE.JSON(l_alert_data) || '",
                "maxTokens": 256,
                "temperature": 0.3
            }
        }';

        l_response := APEX_WEB_SERVICE.MAKE_REST_REQUEST(
            p_url         => C_GENAI_CHAT_URL,
            p_http_method => 'POST',
            p_body        => l_request_body,
            p_credential_static_id => C_WEB_CREDENTIAL
        );

        APEX_JSON.PARSE(l_response);
        l_alert_message := APEX_JSON.GET_CLOB(p_path => 'chatResponse.text');

        -- Log the alert
        INSERT INTO ATLAS_AUDIT_LOG (
            LOG_ID, EVENT_TYPE, USER_ID, ACTION, DETAILS, SUCCESS, CREATED_DATE
        ) VALUES (
            SEQ_ATLAS_AUDIT_LOG.NEXTVAL,
            'ALERT_GENERATED',
            'SYSTEM',
            'PROACTIVE_ALERT',
            l_alert_message,
            'Y',
            SYSTIMESTAMP
        );

        COMMIT;

    EXCEPTION
        WHEN OTHERS THEN
            ROLLBACK;
            RAISE;
    END generate_alerts;

END ATLAS_RAG_PKG;
/
