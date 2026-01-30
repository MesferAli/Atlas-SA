-- ============================================================
-- Atlas on OCI - APEX Command Bar Page (Page 2)
-- Full Implementation with OCI GenAI Integration
-- Execute this in APEX SQL Workshop
-- ============================================================

-- Create Page 2: Command Bar
BEGIN
    APEX_PAGE.CREATE_PAGE(
        p_flow_id           => 100,
        p_page_id           => 2,
        p_page_name         => 'Command Bar',
        p_page_title        => 'Atlas Command Bar',
        p_page_mode         => 'NORMAL',
        p_page_template_id  => 1,
        p_auth_required     => 'Y'
    );
END;
/

-- Create Page Items
BEGIN
    -- Command Input Item
    APEX_ITEM.CREATE_PAGE_ITEM(
        p_flow_id           => 100,
        p_page_id           => 2,
        p_item_name         => 'P2_COMMAND',
        p_item_type         => 'TEXTAREA',
        p_item_label        => 'Enter your command (English or Arabic):',
        p_item_display_length => 1000,
        p_item_height       => 5,
        p_item_required     => 'Y',
        p_item_display_sequence => 10
    );
    
    -- Response Item (Hidden)
    APEX_ITEM.CREATE_PAGE_ITEM(
        p_flow_id           => 100,
        p_page_id           => 2,
        p_item_name         => 'P2_RESPONSE',
        p_item_type         => 'HIDDEN',
        p_item_display_sequence => 20
    );
    
    -- Processing Flag Item
    APEX_ITEM.CREATE_PAGE_ITEM(
        p_flow_id           => 100,
        p_page_id           => 2,
        p_item_name         => 'P2_PROCESSING',
        p_item_type         => 'HIDDEN',
        p_item_display_sequence => 30
    );
    
    -- Language Toggle Item
    APEX_ITEM.CREATE_PAGE_ITEM(
        p_flow_id           => 100,
        p_page_id           => 2,
        p_item_name         => 'P2_LANGUAGE',
        p_item_type         => 'SELECT_LIST',
        p_item_label        => 'Language:',
        p_item_display_sequence => 5,
        p_list_of_values    => 'STATIC:English,EN;العربية,AR'
    );
    
END;
/

-- Add Command Input Region
BEGIN
    APEX_REGION.CREATE_REGION(
        p_flow_id           => 100,
        p_page_id           => 2,
        p_region_name       => 'Command Input',
        p_region_type       => 'FORM',
        p_display_sequence  => 10,
        p_source            => 'SELECT 
            P2_COMMAND,
            P2_LANGUAGE
        FROM DUAL'
    );
END;
/

-- Add Processing Status Region
BEGIN
    APEX_REGION.CREATE_REGION(
        p_flow_id           => 100,
        p_page_id           => 2,
        p_region_name       => 'Processing Status',
        p_region_type       => 'STATIC_CONTENT',
        p_display_sequence  => 20,
        p_source            => '<div id="processing-status" style="display:none;">
            <p><strong>Processing your command...</strong></p>
            <p>Please wait while the system processes your request.</p>
        </div>'
    );
END;
/

-- Add Results Region
BEGIN
    APEX_REGION.CREATE_REGION(
        p_flow_id           => 100,
        p_page_id           => 2,
        p_region_name       => 'Query Results',
        p_region_type       => 'CLASSIC_REPORT',
        p_display_sequence  => 30,
        p_source            => 'SELECT * FROM ATLAS_COMMAND_HISTORY WHERE USER_ID = :APP_USER ORDER BY CREATED_DATE DESC FETCH FIRST 1 ROW ONLY'
    );
END;
/

-- Add Command History Region
BEGIN
    APEX_REGION.CREATE_REGION(
        p_flow_id           => 100,
        p_page_id           => 2,
        p_region_name       => 'Command History',
        p_region_type       => 'CLASSIC_REPORT',
        p_display_sequence  => 40,
        p_source            => 'SELECT 
            COMMAND_ID,
            COMMAND_TEXT,
            CREATED_DATE,
            EXECUTION_TIME
        FROM ATLAS_COMMAND_HISTORY
        WHERE USER_ID = :APP_USER
        ORDER BY CREATED_DATE DESC
        FETCH FIRST 50 ROWS ONLY'
    );
END;
/

-- Create Submit Button
BEGIN
    APEX_BUTTON.CREATE_BUTTON(
        p_flow_id           => 100,
        p_page_id           => 2,
        p_button_name       => 'SUBMIT_COMMAND',
        p_button_label      => 'Submit',
        p_button_position   => 'BOTTOM',
        p_button_action     => 'SUBMIT',
        p_button_request    => 'PROCESS_COMMAND'
    );
END;
/

-- Create Clear Button
BEGIN
    APEX_BUTTON.CREATE_BUTTON(
        p_flow_id           => 100,
        p_page_id           => 2,
        p_button_name       => 'CLEAR_COMMAND',
        p_button_label      => 'Clear',
        p_button_position   => 'BOTTOM',
        p_button_action     => 'REDIRECT_PAGE',
        p_button_target     => 'f?p=100:2:&SESSION.:RESET'
    );
END;
/

-- Create Help Button
BEGIN
    APEX_BUTTON.CREATE_BUTTON(
        p_flow_id           => 100,
        p_page_id           => 2,
        p_button_name       => 'HELP_COMMAND',
        p_button_label      => 'Help',
        p_button_position   => 'BOTTOM',
        p_button_action     => 'REDIRECT_PAGE',
        p_button_target     => 'javascript:alert("Available commands:\n\n1. Show all employees\n2. List departments\n3. Show unpaid invoices\n4. List suppliers\n5. Show alerts\n\nArabic examples:\nكم عدد الموظفين؟\nعرض الفواتير المتأخرة")'
    );
END;
/

-- Create Back Button
BEGIN
    APEX_BUTTON.CREATE_BUTTON(
        p_flow_id           => 100,
        p_page_id           => 2,
        p_button_name       => 'BACK_TO_DASHBOARD',
        p_button_label      => 'Back to Dashboard',
        p_button_position   => 'BOTTOM',
        p_button_action     => 'REDIRECT_PAGE',
        p_button_target     => 'f?p=100:1:&SESSION.'
    );
END;
/

-- Create Process: PROCESS_COMMAND
BEGIN
    APEX_PROCESS.CREATE_PROCESS(
        p_flow_id           => 100,
        p_page_id           => 2,
        p_process_name      => 'PROCESS_COMMAND',
        p_process_type      => 'PLSQL',
        p_process_sequence  => 10,
        p_process_source    => 'DECLARE
            l_response      CLOB;
            l_command       VARCHAR2(1000) := :P2_COMMAND;
            l_user_id       VARCHAR2(100) := :APP_USER;
            l_start_time    TIMESTAMP := SYSTIMESTAMP;
            l_end_time      TIMESTAMP;
            l_execution_time NUMBER;
        BEGIN
            -- Mark as processing
            :P2_PROCESSING := ''Y'';
            
            -- Call the command processor function with OCI GenAI enabled
            l_response := ATLAS_PROCESS_COMMAND_V2(
                p_command   => l_command,
                p_user_id   => l_user_id,
                p_use_genai => ''Y''
            );
            
            -- Calculate execution time
            l_end_time := SYSTIMESTAMP;
            l_execution_time := (l_end_time - l_start_time) * 86400;
            
            -- Store the response in a page item for display
            :P2_RESPONSE := l_response;
            
            -- Log the command in history
            INSERT INTO ATLAS_COMMAND_HISTORY (
                COMMAND_ID, 
                USER_ID, 
                COMMAND_TEXT, 
                RESPONSE_TEXT, 
                EXECUTION_TIME,
                CREATED_DATE
            ) VALUES (
                SEQ_ATLAS_COMMANDS.NEXTVAL,
                l_user_id,
                l_command,
                l_response,
                l_execution_time,
                SYSTIMESTAMP
            );
            COMMIT;
            
            -- Clear processing flag
            :P2_PROCESSING := ''N'';
            
        EXCEPTION
            WHEN OTHERS THEN
                :P2_RESPONSE := ''{"type":"error","message":"'' || SQLERRM || ''","error_code":"'' || SQLCODE || ''}'';
                :P2_PROCESSING := ''N'';
                ROLLBACK;
        END;',
        p_process_when_button_id => 'SUBMIT_COMMAND'
    );
END;
/

-- Create Dynamic Action: Show Processing Message
BEGIN
    APEX_DYNAMIC_ACTION.CREATE_DYNAMIC_ACTION(
        p_flow_id           => 100,
        p_page_id           => 2,
        p_action_name       => 'Show Processing',
        p_event             => 'click',
        p_event_element     => 'SUBMIT_COMMAND',
        p_action_type       => 'SHOW',
        p_action_target     => 'processing-status'
    );
END;
/

-- Create Dynamic Action: Hide Processing Message
BEGIN
    APEX_DYNAMIC_ACTION.CREATE_DYNAMIC_ACTION(
        p_flow_id           => 100,
        p_page_id           => 2,
        p_action_name       => 'Hide Processing',
        p_event             => 'apexafterclosedialog',
        p_action_type       => 'HIDE',
        p_action_target     => 'processing-status'
    );
END;
/

COMMIT;

-- Display completion message
BEGIN
    DBMS_OUTPUT.PUT_LINE('✅ Command Bar Page (Page 2) created successfully!');
    DBMS_OUTPUT.PUT_LINE('   - Command Input Region');
    DBMS_OUTPUT.PUT_LINE('   - Processing Status Region');
    DBMS_OUTPUT.PUT_LINE('   - Query Results Region');
    DBMS_OUTPUT.PUT_LINE('   - Command History Region');
    DBMS_OUTPUT.PUT_LINE('   - Submit, Clear, Help, and Back Buttons');
    DBMS_OUTPUT.PUT_LINE('   - PROCESS_COMMAND Process with OCI GenAI Integration');
END;
/
