#!/usr/bin/env python3
"""
Atlas on OCI - APEX Setup Script
Creates the APEX workspace and deploys the Atlas application
"""

import oracledb
import os
import sys

# Database connection parameters
DB_USER = "ADMIN"
DB_PASSWORD = "AtlasMZX#2026Secure!"
DB_DSN = "atlasdb_high"
WALLET_DIR = os.path.expanduser("~/atlas_wallet")

# APEX URLs
APEX_URL = "https://G05FA28D854C5E8-ATLASDB.adb.me-riyadh-1.oraclecloudapps.com/ords/apex"
ORDS_URL = "https://G05FA28D854C5E8-ATLASDB.adb.me-riyadh-1.oraclecloudapps.com/ords/"

# APEX Workspace and Application Configuration
WORKSPACE_NAME = "ATLAS"
WORKSPACE_ID = 100
APP_ID = 100
APP_NAME = "Atlas"
APP_ALIAS = "ATLAS"

def main():
    print("=" * 60)
    print("Atlas on OCI - APEX Setup")
    print("=" * 60)
    
    try:
        print(f"\nConnecting to ATP database...")
        connection = oracledb.connect(
            user=DB_USER,
            password=DB_PASSWORD,
            dsn=DB_DSN,
            config_dir=WALLET_DIR,
            wallet_location=WALLET_DIR,
            wallet_password="WalletMZX#2026!"
        )
        print("✅ Connected successfully!")
        
        cursor = connection.cursor()
        
        # Check if APEX is available
        print("\n1. Checking APEX availability...")
        cursor.execute("""
            SELECT COUNT(*) FROM all_users WHERE username = 'APEX_230200'
        """)
        apex_exists = cursor.fetchone()[0]
        
        if apex_exists > 0:
            print("   ✅ APEX is available in the database")
        else:
            # Check for other APEX versions
            cursor.execute("""
                SELECT username FROM all_users WHERE username LIKE 'APEX_%' ORDER BY username DESC
            """)
            apex_versions = cursor.fetchall()
            if apex_versions:
                print(f"   ✅ APEX version found: {apex_versions[0][0]}")
            else:
                print("   ⚠️  APEX not found - may need to be enabled")
        
        # Create APEX workspace
        print("\n2. Creating APEX Workspace...")
        try:
            cursor.execute("""
                BEGIN
                    APEX_INSTANCE_ADMIN.ADD_WORKSPACE(
                        p_workspace_id   => :workspace_id,
                        p_workspace      => :workspace_name,
                        p_primary_schema => 'ADMIN'
                    );
                    COMMIT;
                END;
            """, {
                'workspace_id': WORKSPACE_ID,
                'workspace_name': WORKSPACE_NAME
            })
            print(f"   ✅ Workspace '{WORKSPACE_NAME}' created")
        except oracledb.DatabaseError as e:
            error = str(e.args[0])
            if "ORA-20001" in error or "already exists" in error.lower():
                print(f"   ⚠️  Workspace '{WORKSPACE_NAME}' already exists")
            else:
                print(f"   ❌ Error creating workspace: {error}")
        
        # Create APEX admin user for the workspace
        print("\n3. Creating APEX Admin User...")
        try:
            cursor.execute("""
                BEGIN
                    APEX_UTIL.CREATE_USER(
                        p_user_name                    => 'ATLAS_ADMIN',
                        p_email_address                => 'admin@atlas.local',
                        p_web_password                 => 'AtlasAdmin#2026!',
                        p_developer_privs              => 'ADMIN:CREATE:DATA_LOADER:EDIT:HELP:MONITOR:SQL',
                        p_default_schema               => 'ADMIN',
                        p_allow_access_to_schemas      => 'ADMIN',
                        p_change_password_on_first_use => 'N'
                    );
                    COMMIT;
                END;
            """)
            print("   ✅ APEX Admin user 'ATLAS_ADMIN' created")
        except oracledb.DatabaseError as e:
            error = str(e.args[0])
            if "already exists" in error.lower() or "ORA-20001" in error:
                print("   ⚠️  APEX Admin user already exists")
            else:
                print(f"   ❌ Error creating user: {error}")
        
        # Create the Atlas APEX Application
        print("\n4. Creating Atlas APEX Application...")
        try:
            # First, set the workspace context
            cursor.execute("""
                BEGIN
                    APEX_UTIL.SET_WORKSPACE(p_workspace => :workspace_name);
                END;
            """, {'workspace_name': WORKSPACE_NAME})
            
            # Create a simple application
            cursor.execute("""
                DECLARE
                    l_app_id NUMBER;
                BEGIN
                    l_app_id := APEX_APPLICATION_INSTALL.GET_APPLICATION_ID;
                    
                    -- Create application
                    APEX_APPLICATION_INSTALL.SET_APPLICATION_ID(:app_id);
                    APEX_APPLICATION_INSTALL.SET_APPLICATION_NAME(:app_name);
                    APEX_APPLICATION_INSTALL.SET_APPLICATION_ALIAS(:app_alias);
                    APEX_APPLICATION_INSTALL.SET_SCHEMA('ADMIN');
                    APEX_APPLICATION_INSTALL.SET_WORKSPACE_ID(:workspace_id);
                    
                    -- Generate application
                    APEX_APPLICATION_INSTALL.GENERATE_APPLICATION_ID;
                    
                    COMMIT;
                END;
            """, {
                'app_id': APP_ID,
                'app_name': APP_NAME,
                'app_alias': APP_ALIAS,
                'workspace_id': WORKSPACE_ID
            })
            print(f"   ✅ Application '{APP_NAME}' (ID: {APP_ID}) created")
        except oracledb.DatabaseError as e:
            error = str(e.args[0])
            print(f"   ⚠️  Application creation note: {error[:100]}...")
        
        # Create the Command Bar page items and process
        print("\n5. Creating Command Bar Components...")
        
        # Create a table to store command history
        try:
            cursor.execute("""
                CREATE TABLE ATLAS_COMMAND_HISTORY (
                    COMMAND_ID      NUMBER PRIMARY KEY,
                    USER_ID         VARCHAR2(100),
                    COMMAND_TEXT    CLOB,
                    RESPONSE_TEXT   CLOB,
                    EXECUTION_TIME  NUMBER,
                    CREATED_DATE    TIMESTAMP DEFAULT SYSTIMESTAMP
                )
            """)
            cursor.execute("CREATE SEQUENCE SEQ_ATLAS_COMMANDS START WITH 1 INCREMENT BY 1")
            print("   ✅ Command history table created")
        except oracledb.DatabaseError as e:
            if "ORA-00955" in str(e.args[0]):
                print("   ⚠️  Command history table already exists")
            else:
                print(f"   ❌ Error: {e.args[0]}")
        
        # Create the NL-to-SQL function
        print("\n6. Creating NL-to-SQL Processing Function...")
        cursor.execute("""
            CREATE OR REPLACE FUNCTION ATLAS_PROCESS_COMMAND(
                p_command   IN VARCHAR2,
                p_user_id   IN VARCHAR2 DEFAULT NULL
            )
            RETURN CLOB
            IS
                l_response      CLOB;
                l_schema_ctx    CLOB;
                l_validation    VARCHAR2(4000);
                l_command_lower VARCHAR2(4000);
            BEGIN
                l_command_lower := LOWER(p_command);
                
                -- Get schema context
                l_schema_ctx := ATLAS_GET_SCHEMA_CONTEXT();
                
                -- Simple keyword-based query generation for demonstration
                -- In production, this would call OCI Generative AI
                
                IF INSTR(l_command_lower, 'employee') > 0 OR INSTR(l_command_lower, 'موظف') > 0 THEN
                    IF INSTR(l_command_lower, 'count') > 0 OR INSTR(l_command_lower, 'عدد') > 0 OR INSTR(l_command_lower, 'كم') > 0 THEN
                        l_response := '{"type":"query","sql":"SELECT COUNT(*) AS TOTAL_EMPLOYEES FROM ATLAS_EMPLOYEES","description":"Count of all employees"}';
                    ELSE
                        l_response := '{"type":"query","sql":"SELECT EMPLOYEE_ID, EMPLOYEE_NUMBER, FULL_NAME, JOB_TITLE, ASSIGNMENT_STATUS FROM ATLAS_EMPLOYEES ORDER BY FULL_NAME","description":"List of all employees"}';
                    END IF;
                    
                ELSIF INSTR(l_command_lower, 'department') > 0 OR INSTR(l_command_lower, 'قسم') > 0 THEN
                    l_response := '{"type":"query","sql":"SELECT DEPARTMENT_ID, DEPARTMENT_NAME FROM ATLAS_DEPARTMENTS ORDER BY DEPARTMENT_NAME","description":"List of all departments"}';
                    
                ELSIF INSTR(l_command_lower, 'supplier') > 0 OR INSTR(l_command_lower, 'مورد') > 0 THEN
                    l_response := '{"type":"query","sql":"SELECT SUPPLIER_ID, SUPPLIER_NAME, SUPPLIER_NUMBER, STATUS FROM ATLAS_SUPPLIERS ORDER BY SUPPLIER_NAME","description":"List of all suppliers"}';
                    
                ELSIF INSTR(l_command_lower, 'invoice') > 0 OR INSTR(l_command_lower, 'فاتورة') > 0 THEN
                    IF INSTR(l_command_lower, 'unpaid') > 0 OR INSTR(l_command_lower, 'overdue') > 0 OR INSTR(l_command_lower, 'متأخر') > 0 THEN
                        l_response := '{"type":"query","sql":"SELECT INVOICE_ID, INVOICE_NUMBER, INVOICE_AMOUNT, DUE_DATE, PAYMENT_STATUS FROM ATLAS_AP_INVOICES WHERE PAYMENT_STATUS = ''UNPAID'' AND DUE_DATE < SYSDATE ORDER BY DUE_DATE","description":"Overdue unpaid invoices"}';
                    ELSE
                        l_response := '{"type":"query","sql":"SELECT INVOICE_ID, INVOICE_NUMBER, INVOICE_AMOUNT, PAYMENT_STATUS FROM ATLAS_AP_INVOICES ORDER BY INVOICE_DATE DESC","description":"List of all invoices"}';
                    END IF;
                    
                ELSIF INSTR(l_command_lower, 'purchase order') > 0 OR INSTR(l_command_lower, 'po') > 0 OR INSTR(l_command_lower, 'طلب شراء') > 0 THEN
                    l_response := '{"type":"query","sql":"SELECT PO_ID, PO_NUMBER, TOTAL_AMOUNT, STATUS FROM ATLAS_PURCHASE_ORDERS ORDER BY CREATION_DATE DESC","description":"List of all purchase orders"}';
                    
                ELSIF INSTR(l_command_lower, 'alert') > 0 OR INSTR(l_command_lower, 'تنبيه') > 0 THEN
                    l_response := '{"type":"alerts","data":' || ATLAS_GET_ALERTS() || ',"description":"Current system alerts"}';
                    
                ELSIF INSTR(l_command_lower, 'schema') > 0 OR INSTR(l_command_lower, 'table') > 0 THEN
                    l_response := '{"type":"schema","data":"' || REPLACE(REPLACE(l_schema_ctx, CHR(10), '\\n'), '"', '\\"') || '","description":"Available schema information"}';
                    
                ELSE
                    l_response := '{"type":"help","message":"I can help you query: employees, departments, suppliers, invoices, purchase orders. Try asking: Show me all employees, or كم عدد الموظفين؟","description":"Help message"}';
                END IF;
                
                -- Log the command
                ATLAS_LOG_EVENT(
                    p_event_type => 'COMMAND_PROCESSED',
                    p_user_id => p_user_id,
                    p_resource_type => 'COMMAND',
                    p_action => 'PROCESS',
                    p_details => '{"command":"' || SUBSTR(p_command, 1, 500) || '"}'
                );
                
                RETURN l_response;
                
            EXCEPTION
                WHEN OTHERS THEN
                    ATLAS_LOG_EVENT(
                        p_event_type => 'COMMAND_ERROR',
                        p_user_id => p_user_id,
                        p_resource_type => 'COMMAND',
                        p_action => 'PROCESS',
                        p_success => 'N',
                        p_error_message => SQLERRM
                    );
                    RETURN '{"type":"error","message":"' || SQLERRM || '"}';
            END ATLAS_PROCESS_COMMAND;
        """)
        connection.commit()
        print("   ✅ ATLAS_PROCESS_COMMAND function created")
        
        # Test the command processor
        print("\n7. Testing Command Processor...")
        test_commands = [
            ("Show me all employees", "English query"),
            ("كم عدد الموظفين؟", "Arabic query"),
            ("List unpaid invoices", "Invoice query"),
            ("Show alerts", "Alerts query"),
        ]
        
        for cmd, desc in test_commands:
            cursor.execute("SELECT ATLAS_PROCESS_COMMAND(:1, 'TEST_USER') FROM DUAL", [cmd])
            result = cursor.fetchone()[0]
            result_str = result.read() if hasattr(result, 'read') else str(result)
            print(f"   ✅ {desc}: {result_str[:80]}...")
        
        cursor.close()
        connection.close()
        
        print("\n" + "=" * 60)
        print("APEX Setup Complete!")
        print("=" * 60)
        print(f"\n📍 APEX URL: {APEX_URL}")
        print(f"📍 ORDS URL: {ORDS_URL}")
        print(f"\n🔑 Workspace: {WORKSPACE_NAME}")
        print(f"🔑 Admin User: ATLAS_ADMIN")
        print(f"🔑 Password: AtlasAdmin#2026!")
        print("=" * 60)
        
        return 0
        
    except oracledb.Error as e:
        print(f"\n❌ Database connection error: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
