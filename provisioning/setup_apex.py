#!/usr/bin/env python3
"""
Atlas on OCI - APEX Setup Script
Creates the APEX workspace and deploys the Atlas application
"""

import oracledb
import os
import sys
import config

# Database connection parameters from config.py
DB_USER = config.DB_USER
DB_PASSWORD = config.DB_PASSWORD
DB_DSN = config.DB_DSN
WALLET_DIR = os.path.expanduser(config.DB_WALLET_DIR)
WALLET_PASSWORD = config.DB_WALLET_PASSWORD

# APEX URLs
APEX_URL = f"https://{config.DB_DSN.upper()}.adb.{config.OCI_REGION}.oraclecloudapps.com/ords/apex"
ORDS_URL = f"https://{config.DB_DSN.upper()}.adb.{config.OCI_REGION}.oraclecloudapps.com/ords/"

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
            wallet_password=WALLET_PASSWORD
        )
        print("✅ Connected successfully!")
        
        cursor = connection.cursor()
        
        # Create APEX workspace
        print("\n1. Creating APEX Workspace...")
        try:
            cursor.execute("""
                BEGIN
                    APEX_INSTANCE_ADMIN.ADD_WORKSPACE(
                        p_workspace_id   => :workspace_id,
                        p_workspace      => :workspace_name,
                        p_primary_schema => :db_user
                    );
                    COMMIT;
                END;
            """, {
                'workspace_id': WORKSPACE_ID,
                'workspace_name': WORKSPACE_NAME,
                'db_user': DB_USER
            })
            print(f"   ✅ Workspace '{WORKSPACE_NAME}' created")
        except oracledb.DatabaseError as e:
            error = str(e.args[0])
            if "ORA-20001" in error or "already exists" in error.lower():
                print(f"   ⚠️  Workspace '{WORKSPACE_NAME}' already exists")
            else:
                print(f"   ❌ Error creating workspace: {error}")
        
        # Create APEX admin user for the workspace
        print("\n2. Creating APEX Admin User...")
        try:
            cursor.execute("""
                BEGIN
                    APEX_UTIL.CREATE_USER(
                        p_user_name                    => 'ATLAS_ADMIN',
                        p_email_address                => 'admin@atlas.local',
                        p_web_password                 => 'AtlasAdmin#2026!',
                        p_developer_privs              => 'ADMIN:CREATE:DATA_LOADER:EDIT:HELP:MONITOR:SQL',
                        p_default_schema               => :db_user,
                        p_allow_access_to_schemas      => :db_user,
                        p_change_password_on_first_use => 'N'
                    );
                    COMMIT;
                END;
            """, {'db_user': DB_USER})
            print("   ✅ APEX Admin user 'ATLAS_ADMIN' created")
        except oracledb.DatabaseError as e:
            error = str(e.args[0])
            if "already exists" in error.lower() or "ORA-20001" in error:
                print("   ⚠️  APEX Admin user already exists")
            else:
                print(f"   ❌ Error creating user: {error}")
        
        # Create the Atlas APEX Application
        print("\n3. Creating Atlas APEX Application...")
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
                    -- Create application
                    APEX_APPLICATION_INSTALL.SET_APPLICATION_ID(:app_id);
                    APEX_APPLICATION_INSTALL.SET_APPLICATION_NAME(:app_name);
                    APEX_APPLICATION_INSTALL.SET_APPLICATION_ALIAS(:app_alias);
                    APEX_APPLICATION_INSTALL.SET_SCHEMA(:db_user);
                    APEX_APPLICATION_INSTALL.SET_WORKSPACE_ID(:workspace_id);
                    
                    -- Generate application
                    APEX_APPLICATION_INSTALL.GENERATE_APPLICATION_ID;
                    
                    COMMIT;
                END;
            """, {
                'app_id': APP_ID,
                'app_name': APP_NAME,
                'app_alias': APP_ALIAS,
                'workspace_id': WORKSPACE_ID,
                'db_user': DB_USER
            })
            print(f"   ✅ Application '{APP_NAME}' (ID: {APP_ID}) created")
        except oracledb.DatabaseError as e:
            error = str(e.args[0])
            print(f"   ⚠️  Application creation note: {error[:100]}...")
        
        # Create a table to store command history
        print("\n4. Creating Command History Table...")
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
        print("\n5. Creating NL-to-SQL Processing Function...")
        # Read the content of atlas_nl_to_sql.sql
        with open(os.path.join(os.path.dirname(__file__), "atlas_nl_to_sql.sql"), "r") as f:
            nl_to_sql_content = f.read()
            
        # Split by '/' and execute
        for stmt in nl_to_sql_content.split('/'):
            if stmt.strip():
                try:
                    cursor.execute(stmt)
                    connection.commit()
                except oracledb.DatabaseError as e:
                    print(f"   ❌ Error executing NL-to-SQL statement: {e.args[0]}")
        
        print("   ✅ ATLAS_PROCESS_COMMAND_V2 function created")
        
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
