CREATE OR REPLACE PACKAGE ATLAS_VECTOR_UTILS_PKG AS
    -- Function to generate embeddings for a given text using OCI Generative AI
    FUNCTION GENERATE_EMBEDDING(
        p_text IN CLOB
    ) RETURN CLOB; -- Returns JSON string of the embedding vector

    -- Function to perform vector similarity search
    FUNCTION SEARCH_SIMILAR_DOCUMENTS(
        p_query_embedding IN CLOB, -- JSON string of the query vector
        p_top_k           IN NUMBER DEFAULT 5
    ) RETURN CLOB; -- Returns JSON array of matching document chunks

END ATLAS_VECTOR_UTILS_PKG;
/

CREATE OR REPLACE PACKAGE BODY ATLAS_VECTOR_UTILS_PKG AS

    FUNCTION GENERATE_EMBEDDING(
        p_text IN CLOB
    ) RETURN CLOB
    IS
        l_request_body      CLOB;
        l_response          CLOB;
        l_genai_endpoint    VARCHAR2(500) := ATLAS_CONFIG_PKG.GET_GENAI_ENDPOINT();
        l_compartment_id    VARCHAR2(200) := ATLAS_CONFIG_PKG.GET_GENAI_COMPARTMENT_ID();
        l_embedding_model_id VARCHAR2(100) := ATLAS_CONFIG_PKG.GET_GENAI_MODEL_ID(); -- Assuming same model for now, or a dedicated embedding model
        l_api_url           VARCHAR2(1000);
    BEGIN
        l_api_url := l_genai_endpoint || 
                     CASE 
                         WHEN l_embedding_model_id LIKE 
                         'cohere%' THEN '/20231130/actions/embedText'
                         ELSE '/20231130/actions/embedText'
                     END;

        l_request_body := 
            '{
                "compartmentId": "' || l_compartment_id || '",
                "servingMode": {
                    "modelId": "' || l_embedding_model_id || '",
                    "servingType": "ON_DEMAND"
                },
                "embedTextRequest": {
                    "inputText": "' || REPLACE(p_text, '"', '\"') || '"
                }
            }';

        l_response := ATLAS_HTTP_UTILS_PKG.MAKE_REQUEST(
            p_url           => l_api_url,
            p_method        => 'POST',
            p_body          => l_request_body,
            p_headers       => '{"Content-Type": "application/json"}',
            p_credential_name => 'OCI_GENAI_CREDENTIAL'
        );

        ATLAS_AUDIT_LOG_PKG.LOG_EVENT(
            p_event_type => 'GENAI_EMBEDDING',
            p_resource_type => 'VECTOR_UTILS',
            p_action => 'GENERATE',
            p_details => 'Text length: ' || LENGTH(p_text)
        );

        RETURN l_response;

    EXCEPTION
        WHEN OTHERS THEN
            ATLAS_AUDIT_LOG_PKG.LOG_EVENT(
                p_event_type => 'GENAI_EMBEDDING_ERROR',
                p_resource_type => 'VECTOR_UTILS',
                p_action => 'ERROR',
                p_details => 'Error generating embedding: ' || SQLERRM
            );
            RETURN '{"error": "' || REPLACE(SQLERRM, '"', '\"') || '"}';
    END GENERATE_EMBEDDING;

    FUNCTION SEARCH_SIMILAR_DOCUMENTS(
        p_query_embedding IN CLOB,
        p_top_k           IN NUMBER DEFAULT 5
    ) RETURN CLOB
    IS
        l_result_json CLOB := '{"results": [';
        l_first_row BOOLEAN := TRUE;
    BEGIN
        FOR rec IN (
            SELECT
                DOCUMENT_ID,
                CHUNK_ID,
                CHUNK_TEXT,
                -- Assuming VECTOR column stores JSON array of numbers
                -- Need to convert p_query_embedding (JSON string) to actual vector type for comparison
                -- This part requires specific Oracle Vector DB functions or custom parsing
                -- For now, we'll simulate or assume a direct comparison if VECTOR is a native type
                -- Example: VECTOR_DISTANCE(VECTOR_COLUMN, JSON_ARRAY_TO_VECTOR(p_query_embedding), COSINE) as similarity_score
                -- Since we don't have direct VECTOR_DISTANCE function in standard PL/SQL, we'll return all for now
                -- or assume a placeholder for actual vector comparison logic.
                -- For a real implementation, Oracle's AI Vector Search features would be used here.
                0 as similarity_score -- Placeholder for actual similarity score
            FROM
                ATLAS_DOCUMENT_CHUNKS
            -- ORDER BY similarity_score DESC -- Uncomment when actual similarity is calculated
            FETCH FIRST p_top_k ROWS ONLY
        ) LOOP
            IF NOT l_first_row THEN
                l_result_json := l_result_json || ',';
            END IF;
            l_result_json := l_result_json || '{
                "document_id": ' || rec.DOCUMENT_ID || ',
                "chunk_id": ' || rec.CHUNK_ID || ',
                "chunk_text": "' || REPLACE(rec.CHUNK_TEXT, '"', '\"') || '",
                "similarity_score": ' || rec.similarity_score || '
            }';
            l_first_row := FALSE;
        END LOOP;

        l_result_json := l_result_json || ']}';

        ATLAS_AUDIT_LOG_PKG.LOG_EVENT(
            p_event_type => 'VECTOR_SEARCH',
            p_resource_type => 'VECTOR_UTILS',
            p_action => 'SEARCH',
            p_details => 'Top K: ' || p_top_k || ', Results: ' || DBMS_LOB.GETLENGTH(l_result_json)
        );

        RETURN l_result_json;

    EXCEPTION
        WHEN OTHERS THEN
            ATLAS_AUDIT_LOG_PKG.LOG_EVENT(
                p_event_type => 'VECTOR_SEARCH_ERROR',
                p_resource_type => 'VECTOR_UTILS',
                p_action => 'ERROR',
                p_details => 'Error searching similar documents: ' || SQLERRM
            );
            RETURN '{"error": "' || REPLACE(SQLERRM, '"', '\"') || '"}';
    END SEARCH_SIMILAR_DOCUMENTS;

END ATLAS_VECTOR_UTILS_PKG;
/
