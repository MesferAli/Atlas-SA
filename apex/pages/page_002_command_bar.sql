-- Atlas APEX Application - Page 2: Command Bar
-- This script defines the Command Bar page for natural language queries.
--
-- Note: This is a conceptual definition. In practice, pages are created
-- through the APEX Application Builder or exported as part of an application.

-- ============================================================
-- Page Definition
-- ============================================================
/*
Page Number: 2
Page Name: Command Bar
Page Mode: Normal
Page Template: Standard

Regions:
  1. Command Input (Form)
     - P2_COMMAND (Text Area)
     - P2_SUBMIT (Button)
  2. Response Display (Rich Text)
     - P2_RESPONSE (Display Only)
  3. Query History (Classic Report)
*/

-- ============================================================
-- Page Items
-- ============================================================

-- P2_COMMAND: Text area for user input
/*
Item Name: P2_COMMAND
Item Type: Textarea
Label: Enter your command or question
Placeholder: e.g., "Show me all employees in the Sales department" or "كم عدد الموظفين النشطين؟"
Height: 3 rows
Width: 80 characters
*/

-- P2_RESPONSE: Display area for AI response
/*
Item Name: P2_RESPONSE
Item Type: Display Only
Label: Response
Settings:
  - Show as: HTML
  - Escape Special Characters: No
*/

-- ============================================================
-- Buttons
-- ============================================================

-- P2_SUBMIT: Button to submit the command
/*
Button Name: P2_SUBMIT
Label: Submit
Action: Submit Page
Hot: Yes
Position: Below Region
*/

-- ============================================================
-- Processes
-- ============================================================

-- Process: Call OCI Generative AI
/*
Process Name: Process_Command
Type: PL/SQL Code
Point: Processing
Condition: Request = 'SUBMIT'

PL/SQL Code:
*/

DECLARE
    l_request_body  CLOB;
    l_response      CLOB;
    l_url           VARCHAR2(500) := 'https://inference.generativeai.<region>.oci.oraclecloud.com/20231130/actions/chat';
    l_compartment_id VARCHAR2(100) := '<your_compartment_ocid>';
    l_model_id      VARCHAR2(100) := 'cohere.command-r-plus'; -- Or your preferred model
    l_user_command  VARCHAR2(4000) := :P2_COMMAND;
BEGIN
    -- Construct the request body for OCI Generative AI
    l_request_body := '{
        "compartmentId": "' || l_compartment_id || '",
        "servingMode": {
            "servingType": "ON_DEMAND",
            "modelId": "' || l_model_id || '"
        },
        "chatRequest": {
            "apiFormat": "COHERE",
            "message": "' || APEX_ESCAPE.JSON(l_user_command) || '",
            "preambleOverride": "You are Atlas, an AI assistant for Oracle Fusion. Your task is to help users query data. If the user asks a question about data, generate a SQL query for the ATLAS schema. Always respond in the same language as the user query.",
            "maxTokens": 1024,
            "temperature": 0.3
        }
    }';

    -- Make the REST API call using APEX_WEB_SERVICE
    -- Note: OCI Signature authentication must be configured in the Web Credentials.
    l_response := APEX_WEB_SERVICE.MAKE_REST_REQUEST(
        p_url         => l_url,
        p_http_method => 'POST',
        p_body        => l_request_body,
        p_credential_static_id => 'OCI_GENAI_CREDENTIAL' -- Web Credential for OCI Signature
    );

    -- Parse the response and extract the AI's message
    -- The actual parsing logic depends on the response structure.
    :P2_RESPONSE := APEX_JSON.GET_CLOB(
        p_path => 'chatResponse.text',
        p_source => l_response
    );

    -- Log the query to the audit log
    INSERT INTO ATLAS_AUDIT_LOG (
        LOG_ID, EVENT_TYPE, USER_ID, ACTION, DETAILS, SUCCESS, CREATED_DATE
    ) VALUES (
        SEQ_ATLAS_AUDIT_LOG.NEXTVAL,
        'QUERY_EXECUTED',
        :APP_USER,
        'NL_TO_SQL',
        '{"command": "' || APEX_ESCAPE.JSON(l_user_command) || '"}',
        'Y',
        SYSTIMESTAMP
    );

EXCEPTION
    WHEN OTHERS THEN
        :P2_RESPONSE := 'An error occurred: ' || SQLERRM;
        -- Log the error
        INSERT INTO ATLAS_AUDIT_LOG (
            LOG_ID, EVENT_TYPE, USER_ID, ACTION, DETAILS, SUCCESS, ERROR_MESSAGE, CREATED_DATE
        ) VALUES (
            SEQ_ATLAS_AUDIT_LOG.NEXTVAL,
            'QUERY_BLOCKED',
            :APP_USER,
            'NL_TO_SQL',
            '{"command": "' || APEX_ESCAPE.JSON(l_user_command) || '"}',
            'N',
            SQLERRM,
            SYSTIMESTAMP
        );
END;

-- ============================================================
-- Dynamic Actions
-- ============================================================

-- Dynamic Action: Clear Response on Command Change
/*
Name: Clear Response
Event: Change
Selection Type: Item(s)
Item(s): P2_COMMAND
True Action:
  - Action: Set Value
  - Set Type: Static Assignment
  - Value: (empty)
  - Affected Elements: P2_RESPONSE
*/

-- ============================================================
-- Authorization
-- ============================================================

/*
Authorization Scheme: IS_ANALYST_OR_ADMIN
*/
