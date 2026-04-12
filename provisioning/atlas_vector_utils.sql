CREATE OR REPLACE PACKAGE ATLAS_VECTOR_UTILS_PKG AS
    -- Function to generate embeddings for a given text using OCI Generative AI
    FUNCTION GENERATE_EMBEDDING(
        p_text IN CLOB
    ) RETURN CLOB; -- Returns JSON string of the embedding vector

    -- Function to compute cosine similarity between two JSON-array embeddings.
    -- Returns a NUMBER in the range [-1, 1]; returns 0 for invalid / mismatched vectors.
    FUNCTION COSINE_SIMILARITY(
        p_vec1 IN CLOB,
        p_vec2 IN CLOB
    ) RETURN NUMBER;

    -- Function to perform vector similarity search
    FUNCTION SEARCH_SIMILAR_DOCUMENTS(
        p_query_embedding IN CLOB, -- JSON string of the query vector
        p_top_k           IN NUMBER DEFAULT 5
    ) RETURN CLOB; -- Returns JSON array of matching document chunks

END ATLAS_VECTOR_UTILS_PKG;
/

CREATE OR REPLACE PACKAGE BODY ATLAS_VECTOR_UTILS_PKG AS

    -- Private type: dense numeric vector, 1-indexed.
    TYPE t_number_list IS TABLE OF NUMBER INDEX BY PLS_INTEGER;

    -- --------------------------------------------------------
    -- Private: parse a JSON array of numbers into a numeric collection.
    -- Accepts CLOBs like "[0.12, -0.34, 0.56, ...]".
    -- Leaves p_out empty on parse failure.
    -- --------------------------------------------------------
    PROCEDURE PARSE_VECTOR(
        p_json_vector IN  CLOB,
        p_out         OUT NOCOPY t_number_list
    )
    IS
        l_values APEX_JSON.t_values;
        l_count  PLS_INTEGER;
    BEGIN
        p_out.DELETE;

        IF p_json_vector IS NULL OR DBMS_LOB.GETLENGTH(p_json_vector) = 0 THEN
            RETURN;
        END IF;

        APEX_JSON.PARSE(p_values => l_values, p_source => p_json_vector);
        l_count := APEX_JSON.GET_COUNT(p_values => l_values, p_path => '.');

        IF l_count IS NULL OR l_count = 0 THEN
            RETURN;
        END IF;

        FOR i IN 1 .. l_count LOOP
            p_out(i) := APEX_JSON.GET_NUMBER(
                            p_values => l_values,
                            p_path   => '[%d]',
                            p0       => i);
        END LOOP;
    EXCEPTION
        WHEN OTHERS THEN
            p_out.DELETE;
    END PARSE_VECTOR;

    -- --------------------------------------------------------
    -- Private: compute cosine similarity between two parsed numeric vectors.
    -- Returns 0 when either vector is empty, dimensions mismatch,
    -- or when a vector has zero magnitude.
    -- --------------------------------------------------------
    FUNCTION COMPUTE_COSINE(
        p_vec1 IN t_number_list,
        p_vec2 IN t_number_list
    ) RETURN NUMBER
    IS
        l_dot     NUMBER := 0;
        l_mag1_sq NUMBER := 0;
        l_mag2_sq NUMBER := 0;
        l_denom   NUMBER;
        l_v1      NUMBER;
        l_v2      NUMBER;
    BEGIN
        IF p_vec1.COUNT = 0
           OR p_vec2.COUNT = 0
           OR p_vec1.COUNT <> p_vec2.COUNT THEN
            RETURN 0;
        END IF;

        FOR i IN 1 .. p_vec1.COUNT LOOP
            l_v1 := NVL(p_vec1(i), 0);
            l_v2 := NVL(p_vec2(i), 0);
            l_dot     := l_dot     + (l_v1 * l_v2);
            l_mag1_sq := l_mag1_sq + (l_v1 * l_v1);
            l_mag2_sq := l_mag2_sq + (l_v2 * l_v2);
        END LOOP;

        l_denom := SQRT(l_mag1_sq) * SQRT(l_mag2_sq);

        IF l_denom = 0 THEN
            RETURN 0;
        END IF;

        RETURN l_dot / l_denom;
    END COMPUTE_COSINE;

    -- --------------------------------------------------------
    -- Public: compute cosine similarity between two JSON-array embeddings.
    -- --------------------------------------------------------
    FUNCTION COSINE_SIMILARITY(
        p_vec1 IN CLOB,
        p_vec2 IN CLOB
    ) RETURN NUMBER
    IS
        l_v1 t_number_list;
        l_v2 t_number_list;
    BEGIN
        PARSE_VECTOR(p_vec1, l_v1);
        PARSE_VECTOR(p_vec2, l_v2);
        RETURN COMPUTE_COSINE(l_v1, l_v2);
    EXCEPTION
        WHEN OTHERS THEN
            RETURN 0;
    END COSINE_SIMILARITY;

    -- --------------------------------------------------------
    -- Private: format a NUMBER as a locale-safe JSON numeric literal.
    -- --------------------------------------------------------
    FUNCTION JSON_NUM(p_value IN NUMBER) RETURN VARCHAR2
    IS
    BEGIN
        IF p_value IS NULL THEN
            RETURN 'null';
        END IF;
        RETURN TRIM(TO_CHAR(
                       p_value,
                       'FM99990.0999999999',
                       'NLS_NUMERIC_CHARACTERS=''.,'''));
    END JSON_NUM;

    -- --------------------------------------------------------
    -- Private: minimal JSON string escaping for chunk text output.
    -- --------------------------------------------------------
    FUNCTION JSON_ESCAPE(p_text IN VARCHAR2) RETURN VARCHAR2
    IS
        l_out VARCHAR2(32767);
    BEGIN
        IF p_text IS NULL THEN
            RETURN '';
        END IF;
        l_out := REPLACE(p_text,    '\',     '\\');
        l_out := REPLACE(l_out,     '"',     '\"');
        l_out := REPLACE(l_out,     CHR(13), '\r');
        l_out := REPLACE(l_out,     CHR(10), '\n');
        l_out := REPLACE(l_out,     CHR(9),  '\t');
        RETURN l_out;
    END JSON_ESCAPE;

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
        TYPE t_result_rec IS RECORD (
            document_id      NUMBER,
            chunk_id         NUMBER,
            chunk_text       CLOB,
            similarity_score NUMBER
        );
        TYPE t_result_tab IS TABLE OF t_result_rec INDEX BY PLS_INTEGER;

        l_query_vec    t_number_list;
        l_chunk_vec    t_number_list;
        l_all_results  t_result_tab;
        l_idx          PLS_INTEGER := 0;
        l_top_k        PLS_INTEGER := GREATEST(NVL(p_top_k, 5), 1);

        l_result_json  CLOB := '{"results": [';
        l_first_row    BOOLEAN := TRUE;
        l_out_count    PLS_INTEGER := 0;
        l_max_idx      PLS_INTEGER;
        l_max_score    NUMBER;
    BEGIN
        -- Parse the query embedding once.
        PARSE_VECTOR(p_query_embedding, l_query_vec);

        IF l_query_vec.COUNT = 0 THEN
            ATLAS_AUDIT_LOG_PKG.LOG_EVENT(
                p_event_type    => 'VECTOR_SEARCH_ERROR',
                p_resource_type => 'VECTOR_UTILS',
                p_action        => 'SEARCH',
                p_details       => 'Invalid or empty query embedding'
            );
            RETURN '{"results": [], "error": "Invalid query embedding"}';
        END IF;

        -- Score every chunk that has a stored embedding.
        FOR rec IN (
            SELECT DOCUMENT_ID, CHUNK_ID, CHUNK_TEXT, EMBEDDING
            FROM   ATLAS_DOCUMENT_CHUNKS
            WHERE  EMBEDDING IS NOT NULL
              AND  DBMS_LOB.GETLENGTH(EMBEDDING) > 0
        ) LOOP
            PARSE_VECTOR(rec.EMBEDDING, l_chunk_vec);

            l_idx := l_idx + 1;
            l_all_results(l_idx).document_id      := rec.DOCUMENT_ID;
            l_all_results(l_idx).chunk_id         := rec.CHUNK_ID;
            l_all_results(l_idx).chunk_text       := rec.CHUNK_TEXT;
            l_all_results(l_idx).similarity_score := COMPUTE_COSINE(l_query_vec, l_chunk_vec);

            l_chunk_vec.DELETE;
        END LOOP;

        -- Selection-pass to pull the top-K by similarity DESC.
        -- We mark consumed rows by setting similarity_score to NULL.
        WHILE l_out_count < LEAST(l_top_k, l_all_results.COUNT) LOOP
            l_max_idx   := NULL;
            l_max_score := NULL;

            FOR i IN 1 .. l_all_results.COUNT LOOP
                IF l_all_results(i).similarity_score IS NOT NULL THEN
                    IF l_max_idx IS NULL
                       OR l_all_results(i).similarity_score > l_max_score THEN
                        l_max_idx   := i;
                        l_max_score := l_all_results(i).similarity_score;
                    END IF;
                END IF;
            END LOOP;

            EXIT WHEN l_max_idx IS NULL;

            IF NOT l_first_row THEN
                l_result_json := l_result_json || ',';
            END IF;

            l_result_json := l_result_json
                || '{"document_id": '     || l_all_results(l_max_idx).document_id
                || ', "chunk_id": '       || l_all_results(l_max_idx).chunk_id
                || ', "chunk_text": "'
                   || JSON_ESCAPE(DBMS_LOB.SUBSTR(l_all_results(l_max_idx).chunk_text, 4000, 1))
                   || '"'
                || ', "similarity_score": ' || JSON_NUM(l_all_results(l_max_idx).similarity_score)
                || '}';

            l_first_row := FALSE;
            l_all_results(l_max_idx).similarity_score := NULL;
            l_out_count := l_out_count + 1;
        END LOOP;

        l_result_json := l_result_json || ']}';

        ATLAS_AUDIT_LOG_PKG.LOG_EVENT(
            p_event_type    => 'VECTOR_SEARCH',
            p_resource_type => 'VECTOR_UTILS',
            p_action        => 'SEARCH',
            p_details       => 'Top K: '     || l_top_k
                            || ', Scanned: ' || l_all_results.COUNT
                            || ', Returned: '|| l_out_count
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
