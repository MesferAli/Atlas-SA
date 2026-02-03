CREATE OR REPLACE FUNCTION ATLAS_GENAI_NL_TO_SQL(
    p_natural_language  IN VARCHAR2,
    p_user_id           IN VARCHAR2 DEFAULT NULL
)
RETURN CLOB
IS
    l_request_body      CLOB;
    l_response          CLOB;
    l_schema_context    CLOB;
    l_genai_endpoint    VARCHAR2(500) := ATLAS_CONFIG_PKG.GET_GENAI_ENDPOINT();
    l_compartment_id    VARCHAR2(200) := ATLAS_CONFIG_PKG.GET_GENAI_COMPARTMENT_ID();
    l_model_id          VARCHAR2(100) := ATLAS_CONFIG_PKG.GET_GENAI_MODEL_ID();
    l_api_url           VARCHAR2(1000);
BEGIN
    l_schema_context := ATLAS_GET_SCHEMA_CONTEXT();
    
    l_api_url := l_genai_endpoint || 
                 CASE 
                     WHEN l_model_id LIKE 
                     'cohere%' THEN '/20231130/actions/chat'
                     ELSE '/20231130/actions/generateText'
                 END;

    -- Build the request payload for OCI Generative AI
    l_request_body := 
        '{
            "compartmentId": "' || l_compartment_id || '",
            "servingMode": {
                "modelId": "' || l_model_id || '",
                "servingType": "ON_DEMAND"
            },
            "chatRequest": {
                "messages": [
                    {
                        "role": "system",
                        "content": "You are a helpful SQL assistant. Your task is to convert natural language questions into SQL queries for an Oracle database. Only use the tables and columns provided in the schema context. Do not make up tables or columns. If the question cannot be answered from the provided schema, respond with \"I cannot answer this question based on the available data.\". Always provide the SQL query within <sql> and </sql> tags. \n\nSchema Context:\n' || l_schema_context || '"
                    },
                    {
                        "role": "user",
                        "content": "' || REPLACE(p_natural_language, '"', '\"') || '"
                    }
                ],
                "temperature": 0.1,
                "topP": 0.9,
                "maxTokens": 500
            }
        }';

    -- Make the request to OCI Generative AI
    l_response := ATLAS_HTTP_UTILS_PKG.MAKE_REQUEST(
        p_url           => l_api_url,
        p_method        => 'POST',
        p_body          => l_request_body,
        p_headers       => '{"Content-Type": "application/json"}',
        p_credential_name => 'OCI_GENAI_CREDENTIAL' -- This credential must be set up in APEX
    );

    -- Log the interaction
    ATLAS_AUDIT_LOG_PKG.LOG_EVENT(
        p_event_type => 'GENAI_CALL',
        p_resource_type => 'NL_TO_SQL',
        p_action => 'REQUEST',
        p_details => 'User: ' || NVL(p_user_id, 'ANONYMOUS') || ', Prompt: ' || p_natural_language
    );

    RETURN l_response;

EXCEPTION
    WHEN OTHERS THEN
        ATLAS_AUDIT_LOG_PKG.LOG_EVENT(
            p_event_type => 'GENAI_ERROR',
            p_resource_type => 'NL_TO_SQL',
            p_action => 'ERROR',
            p_details => 'User: ' || NVL(p_user_id, 'ANONYMOUS') || ', Error: ' || SQLERRM
        );
        RETURN '{"error": "' || REPLACE(SQLERRM, '"', '\"') || '"}';
END ATLAS_GENAI_NL_TO_SQL;
/

-- Update ATLAS_PROCESS_COMMAND_V2 to use the new NL_TO_SQL function
CREATE OR REPLACE FUNCTION ATLAS_PROCESS_COMMAND_V2(
    p_command   IN VARCHAR2,
    p_user_id   IN VARCHAR2 DEFAULT NULL,
    p_use_genai IN VARCHAR2 DEFAULT 'Y'
)
RETURN CLOB
IS
    l_response CLOB;
    l_sql_query VARCHAR2(4000);
    l_genai_raw_response CLOB;
    l_json_response APEX_JSON.T_VALUES;
BEGIN
    -- Try OCI Generative AI first if enabled
    IF p_use_genai = 'Y' THEN
        BEGIN
            l_genai_raw_response := ATLAS_GENAI_NL_TO_SQL(p_command, p_user_id);
            
            -- Parse the JSON response from GenAI
            APEX_JSON.PARSE(l_json_response, l_genai_raw_response);
            
            -- Extract the SQL query from the GenAI response
            l_sql_query := APEX_JSON.GET_VARCHAR2(l_json_response, 'choices[1].message.content'); -- Adjust path based on actual GenAI response structure
            
            -- Extract content between <sql> and </sql> tags
            IF INSTR(l_sql_query, '<sql>') > 0 AND INSTR(l_sql_query, '</sql>') > 0 THEN
                l_sql_query := SUBSTR(l_sql_query, INSTR(l_sql_query, '<sql>') + 5, INSTR(l_sql_query, '</sql>') - (INSTR(l_sql_query, '<sql>') + 5));
            END IF;

            IF l_sql_query IS NOT NULL AND LENGTH(TRIM(l_sql_query)) > 0 THEN
                -- Validate and execute the generated SQL
                l_response := ATLAS_EXECUTE_SAFE_QUERY(l_sql_query);
                RETURN l_response;
            END IF;
        EXCEPTION
            WHEN OTHERS THEN
                -- Log GenAI error and fall back to rule-based processing
                ATLAS_AUDIT_LOG_PKG.LOG_EVENT(
                    p_event_type => 'GENAI_FALLBACK',
                    p_resource_type => 'NL_TO_SQL',
                    p_action => 'ERROR_FALLBACK',
                    p_details => 'User: ' || NVL(p_user_id, 'ANONYMOUS') || ', GenAI Error: ' || SQLERRM || ', Command: ' || p_command
                );
        END;
    END IF;
    
    -- Fall back to rule-based processing if GenAI fails or is disabled
    RETURN ATLAS_PROCESS_COMMAND(p_command, p_user_id);
END ATLAS_PROCESS_COMMAND_V2;
/

GRANT EXECUTE ON ATLAS_GENAI_NL_TO_SQL TO PUBLIC;
GRANT EXECUTE ON ATLAS_PROCESS_COMMAND_V2 TO PUBLIC;
