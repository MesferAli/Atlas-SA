# Atlas on OCI - AI/RAG Intelligence Layer Design

**Version:** 1.0
**Date:** January 30, 2026
**Author:** Manus AI

## 1. Introduction

This document details the design and implementation of the Intelligence Layer for the Atlas platform on OCI. This layer is responsible for powering the natural language "Command Bar" interface and the "Proactive Alert" system. The core of this layer is a Retrieval-Augmented Generation (RAG) pipeline that combines the power of OCI Generative AI with semantic search capabilities provided by AI Vector Search within the Autonomous Database.

## 2. Architecture Overview

The Intelligence Layer consists of the following key components:

1.  **OCI Generative AI Service**: Provides the large language model (LLM) for natural language understanding, SQL generation, and response synthesis.
2.  **AI Vector Search (in Autonomous Database)**: Enables semantic search over Fusion documentation and internal records to provide relevant context to the LLM.
3.  **RAG Pipeline**: Orchestrates the flow from user query to AI-generated response, incorporating retrieved context.
4.  **Proactive Alert Engine**: Analyzes data trends and generates actionable insights for the dashboard.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         Intelligence Layer                              │
│                                                                         │
│  ┌─────────────┐     ┌─────────────────┐     ┌─────────────────────┐   │
│  │ User Query  │────▶│  RAG Pipeline   │────▶│ AI-Generated Response│   │
│  └─────────────┘     │                 │     └─────────────────────┘   │
│                      │  ┌───────────┐  │                               │
│                      │  │ Retrieval │  │                               │
│                      │  │ (Vector   │  │                               │
│                      │  │  Search)  │  │                               │
│                      │  └─────┬─────┘  │                               │
│                      │        │        │                               │
│                      │  ┌─────▼─────┐  │                               │
│                      │  │ Augmented │  │                               │
│                      │  │  Prompt   │  │                               │
│                      │  └─────┬─────┘  │                               │
│                      │        │        │                               │
│                      │  ┌─────▼─────┐  │                               │
│                      │  │ Generation│  │                               │
│                      │  │ (OCI      │  │                               │
│                      │  │  GenAI)   │  │                               │
│                      │  └───────────┘  │                               │
│                      └─────────────────┘                               │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                   Proactive Alert Engine                        │   │
│  │  ┌───────────┐     ┌───────────┐     ┌───────────────────────┐  │   │
│  │  │ Data Trend│────▶│ Analysis  │────▶│ Alert Generation      │  │   │
│  │  │ Monitoring│     │ (SQL +    │     │ (OCI GenAI)           │  │   │
│  │  │           │     │  Rules)   │     │                       │  │   │
│  │  └───────────┘     └───────────┘     └───────────────────────┘  │   │
│  └─────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
```

## 3. RAG Pipeline Implementation

The RAG pipeline follows a standard Retrieval-Augmented Generation pattern, adapted for the Atlas use case.

### 3.1. Pipeline Steps

| Step | Description | OCI Component |
|---|---|---|
| 1. Query Embedding | Convert the user's natural language query into a vector embedding. | OCI Generative AI (Embedding Model) |
| 2. Semantic Search | Search the `ATLAS_DOCUMENT_CHUNKS` table for chunks with embeddings similar to the query embedding. | AI Vector Search (Autonomous Database) |
| 3. Context Retrieval | Retrieve the top-k most relevant document chunks and any relevant schema metadata. | Autonomous Database |
| 4. Prompt Augmentation | Construct a prompt for the LLM that includes the user's query, the retrieved context, and system instructions. | PL/SQL / APEX |
| 5. LLM Generation | Send the augmented prompt to OCI Generative AI to generate a response (e.g., SQL query, natural language answer). | OCI Generative AI (Chat Model) |
| 6. Response Validation | Validate the generated response (e.g., ensure SQL is read-only). | PL/SQL / APEX |
| 7. Response Delivery | Return the validated response to the user. | APEX |

### 3.2. Embedding Generation

User queries and document chunks are converted into vector embeddings using an embedding model from OCI Generative AI.

**PL/SQL Function for Embedding Generation:**

```sql
CREATE OR REPLACE FUNCTION ATLAS_GET_EMBEDDING(p_text IN CLOB)
RETURN VECTOR
IS
    l_request_body  CLOB;
    l_response      CLOB;
    l_embedding     VECTOR(384); -- Adjust dimension based on model
    l_url           VARCHAR2(500) := 'https://inference.generativeai.<region>.oci.oraclecloud.com/20231130/actions/embedText';
    l_compartment_id VARCHAR2(100) := '<your_compartment_ocid>';
    l_model_id      VARCHAR2(100) := 'cohere.embed-multilingual-v3.0'; -- Or your preferred embedding model
BEGIN
    -- Construct the request body
    l_request_body := '{
        "compartmentId": "' || l_compartment_id || '",
        "servingMode": {
            "servingType": "ON_DEMAND",
            "modelId": "' || l_model_id || '"
        },
        "inputs": ["' || APEX_ESCAPE.JSON(p_text) || '"],
        "truncate": "END"
    }';

    -- Make the REST API call
    l_response := APEX_WEB_SERVICE.MAKE_REST_REQUEST(
        p_url         => l_url,
        p_http_method => 'POST',
        p_body        => l_request_body,
        p_credential_static_id => 'OCI_GENAI_CREDENTIAL'
    );

    -- Parse the response and extract the embedding
    -- Note: The actual parsing depends on the response structure.
    -- This is a simplified example.
    l_embedding := VECTOR(APEX_JSON.GET_VARCHAR2(p_path => 'embeddings[0]', p_source => l_response));

    RETURN l_embedding;

EXCEPTION
    WHEN OTHERS THEN
        -- Log error and return null
        RETURN NULL;
END ATLAS_GET_EMBEDDING;
/
```

### 3.3. Semantic Search with AI Vector Search

The `ATLAS_DOCUMENT_CHUNKS` table stores document chunks along with their vector embeddings. AI Vector Search enables efficient similarity search.

**SQL Query for Semantic Search:**

```sql
SELECT
    dc.CHUNK_ID,
    dc.DOCUMENT_ID,
    dc.CHUNK_TEXT,
    d.DOCUMENT_NAME,
    VECTOR_DISTANCE(dc.EMBEDDING, :query_embedding, COSINE) AS similarity_score
FROM
    ATLAS_DOCUMENT_CHUNKS dc
    JOIN ATLAS_DOCUMENTS d ON dc.DOCUMENT_ID = d.DOCUMENT_ID
ORDER BY
    similarity_score ASC -- Lower distance = higher similarity
FETCH FIRST 5 ROWS ONLY;
```

### 3.4. Prompt Augmentation

The retrieved context is combined with the user's query to create an augmented prompt for the LLM.

**Prompt Template:**

```
You are Atlas, an AI assistant for Oracle Fusion. Your task is to help users query data from the Atlas schema.

**Instructions:**
- If the user asks a question about data, generate a SQL query for the ATLAS schema.
- Only generate SELECT queries. Never generate INSERT, UPDATE, DELETE, or DROP statements.
- Use the provided context to understand the schema and data.
- Respond in the same language as the user's query (Arabic or English).

**Available Schema:**
{schema_context}

**Relevant Documents:**
{retrieved_documents}

**User Query:**
{user_query}

**Your Response:**
```

### 3.5. LLM Generation

The augmented prompt is sent to OCI Generative AI for response generation.

**PL/SQL Procedure for LLM Call:**

```sql
CREATE OR REPLACE PROCEDURE ATLAS_GENERATE_RESPONSE(
    p_prompt    IN CLOB,
    p_response  OUT CLOB
)
IS
    l_request_body  CLOB;
    l_url           VARCHAR2(500) := 'https://inference.generativeai.<region>.oci.oraclecloud.com/20231130/actions/chat';
    l_compartment_id VARCHAR2(100) := '<your_compartment_ocid>';
    l_model_id      VARCHAR2(100) := 'cohere.command-r-plus';
BEGIN
    l_request_body := '{
        "compartmentId": "' || l_compartment_id || '",
        "servingMode": {
            "servingType": "ON_DEMAND",
            "modelId": "' || l_model_id || '"
        },
        "chatRequest": {
            "apiFormat": "COHERE",
            "message": "' || APEX_ESCAPE.JSON(p_prompt) || '",
            "maxTokens": 2048,
            "temperature": 0.2
        }
    }';

    p_response := APEX_WEB_SERVICE.MAKE_REST_REQUEST(
        p_url         => l_url,
        p_http_method => 'POST',
        p_body        => l_request_body,
        p_credential_static_id => 'OCI_GENAI_CREDENTIAL'
    );

EXCEPTION
    WHEN OTHERS THEN
        p_response := '{"error": "' || SQLERRM || '"}';
END ATLAS_GENERATE_RESPONSE;
/
```

## 4. Document Ingestion for RAG

To populate the `ATLAS_DOCUMENTS` and `ATLAS_DOCUMENT_CHUNKS` tables, a document ingestion process is required.

### 4.1. Ingestion Steps

1.  **Upload Document**: Upload the document (PDF, DOCX, TXT) to OCI Object Storage.
2.  **Extract Text**: Use OCI Document Understanding or a text extraction library to extract text from the document.
3.  **Chunk Text**: Split the extracted text into smaller chunks (e.g., 500-1000 tokens each) with overlap.
4.  **Generate Embeddings**: For each chunk, generate a vector embedding using `ATLAS_GET_EMBEDDING`.
5.  **Store in Database**: Insert the document metadata into `ATLAS_DOCUMENTS` and the chunks with embeddings into `ATLAS_DOCUMENT_CHUNKS`.

### 4.2. PL/SQL Procedure for Document Ingestion

```sql
CREATE OR REPLACE PROCEDURE ATLAS_INGEST_DOCUMENT(
    p_document_name     IN VARCHAR2,
    p_document_type     IN VARCHAR2,
    p_source_system     IN VARCHAR2,
    p_object_storage_path IN VARCHAR2,
    p_text_content      IN CLOB
)
IS
    l_document_id   NUMBER;
    l_chunk_id      NUMBER;
    l_chunk_text    CLOB;
    l_chunk_seq     NUMBER := 0;
    l_embedding     VECTOR(384);
    l_chunk_size    NUMBER := 1000; -- Characters per chunk
    l_overlap       NUMBER := 100;  -- Overlap between chunks
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

    -- Chunk the text and insert with embeddings
    l_text_length := DBMS_LOB.GETLENGTH(p_text_content);

    WHILE l_start_pos < l_text_length LOOP
        l_chunk_seq := l_chunk_seq + 1;
        l_chunk_text := DBMS_LOB.SUBSTR(p_text_content, l_chunk_size, l_start_pos);

        -- Generate embedding for the chunk
        l_embedding := ATLAS_GET_EMBEDDING(l_chunk_text);

        -- Insert chunk
        SELECT SEQ_ATLAS_CHUNKS.NEXTVAL INTO l_chunk_id FROM DUAL;

        INSERT INTO ATLAS_DOCUMENT_CHUNKS (
            CHUNK_ID, DOCUMENT_ID, CHUNK_TEXT, CHUNK_SEQUENCE, EMBEDDING, CREATED_DATE
        ) VALUES (
            l_chunk_id, l_document_id, l_chunk_text, l_chunk_seq, l_embedding, SYSTIMESTAMP
        );

        -- Move to next chunk with overlap
        l_start_pos := l_start_pos + l_chunk_size - l_overlap;
    END LOOP;

    COMMIT;

EXCEPTION
    WHEN OTHERS THEN
        ROLLBACK;
        RAISE;
END ATLAS_INGEST_DOCUMENT;
/
```

## 5. Proactive Alert Engine

The Proactive Alert Engine analyzes data trends in the `ATLAS_*` tables and generates actionable insights.

### 5.1. Alert Rules

Alerts are generated based on predefined rules that query the data.

| Alert Type | Rule | SQL Query |
|---|---|---|
| Past Due Invoices | Invoices past their due date | `SELECT COUNT(*) FROM ATLAS_AP_INVOICES WHERE DUE_DATE < SYSDATE AND PAYMENT_STATUS = 'UNPAID'` |
| High-Value POs Pending | POs over a threshold amount pending approval | `SELECT COUNT(*) FROM ATLAS_PURCHASE_ORDERS WHERE TOTAL_AMOUNT > 100000 AND STATUS = 'PENDING'` |
| Employee Anniversaries | Employees with upcoming work anniversaries | `SELECT COUNT(*) FROM ATLAS_EMPLOYEES WHERE TO_CHAR(HIRE_DATE, 'MM-DD') = TO_CHAR(SYSDATE + 7, 'MM-DD')` |

### 5.2. Alert Generation Process

1.  **Run Alert Rules**: A scheduled job runs the SQL queries for each alert rule.
2.  **Identify Anomalies**: If a rule's result exceeds a threshold, an alert is triggered.
3.  **Generate Alert Message**: The alert data is sent to OCI Generative AI to generate a human-readable alert message.
4.  **Display on Dashboard**: The alert message is displayed in the "Proactive Alerts" region on the dashboard.

### 5.3. PL/SQL Procedure for Alert Generation

```sql
CREATE OR REPLACE PROCEDURE ATLAS_GENERATE_ALERTS
IS
    l_past_due_count    NUMBER;
    l_high_po_count     NUMBER;
    l_alert_data        CLOB;
    l_alert_message     CLOB;
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
    ATLAS_GENERATE_RESPONSE(
        p_prompt => 'Based on the following data, generate a brief alert summary for a business dashboard. Data: ' || l_alert_data,
        p_response => l_alert_message
    );

    -- Store the alert (or update a dashboard item)
    -- This could be stored in a table or set as an APEX application item.
    -- For simplicity, we log it here.
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
END ATLAS_GENERATE_ALERTS;
/
```

## 6. Security Considerations

*   **Read-Only SQL**: The RAG pipeline must validate that any generated SQL is read-only before execution. The `ATLAS_VALIDATE_QUERY` function (similar to the one in the original Atlas codebase) should be used.
*   **Data Classification**: The RAG pipeline should respect data classification. Context retrieved from SECRET or TOP_SECRET documents should only be used for users with appropriate roles.
*   **Prompt Injection**: Input sanitization must be applied to user queries to prevent prompt injection attacks.
*   **Audit Logging**: All interactions with the Intelligence Layer should be logged to `ATLAS_AUDIT_LOG`.
