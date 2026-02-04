#!/usr/bin/env python3
"""
Atlas on OCI - Database Schema Deployment Script
Supports both mTLS (Wallet) and TLS (Walletless) connections
"""

import oracledb
import os
import sys
from config import Config

def main():
    print("=" * 60)
    print("Atlas on OCI - Schema Deployment")
    print("=" * 60)
    
    # Load DDL from schema_ddl.sql
    ddl_path = os.path.join(os.path.dirname(__file__), "schema_ddl.sql")
    if not os.path.exists(ddl_path):
        print(f"❌ Error: {ddl_path} not found")
        return 1
        
    with open(ddl_path, "r") as f:
        schema_ddl_content = f.read()

    # Split DDL statements by ";" and filter out empty strings
    DDL_STATEMENTS = [stmt.strip() for stmt in schema_ddl_content.split(";") if stmt.strip()]
    
    try:
        # Connect to the database
        print(f"\nConnecting to ATP database...")
        
        if Config.USE_WALLET:
            wallet_dir = os.path.expanduser(Config.DB_WALLET_PATH)
            print(f"Using mTLS (Wallet) connection from: {wallet_dir}")
            connection = oracledb.connect(
                user=Config.DB_USER,
                password=Config.DB_PASSWORD,
                dsn=Config.DB_DSN,
                config_dir=wallet_dir,
                wallet_location=wallet_dir,
                wallet_password=Config.DB_PASSWORD # Assuming wallet password is same as DB password
            )
        else:
            print(f"Using Walletless TLS connection...")
            connection = oracledb.connect(
                user=Config.DB_USER,
                password=Config.DB_PASSWORD,
                dsn=Config.DB_DSN
            )
            
        print("✅ Connected successfully!")
        
        cursor = connection.cursor()
        
        # Execute each DDL statement
        success_count = 0
        error_count = 0
        
        for i, stmt in enumerate(DDL_STATEMENTS, 1):
            if not stmt.strip():
                continue

            stmt_type = stmt.split()[0].upper()
            obj_name = "UNKNOWN"

            if stmt_type == "CREATE":
                if "TABLE" in stmt:
                    obj_name = stmt.split("TABLE")[1].split("(")[0].strip()
                elif "INDEX" in stmt:
                    obj_name = stmt.split("INDEX")[1].split("ON")[0].strip()
                elif "SEQUENCE" in stmt:
                    obj_name = stmt.split("SEQUENCE")[1].split("START")[0].strip()
                elif "PACKAGE" in stmt:
                    obj_name = stmt.split("PACKAGE")[1].split("AS")[0].strip()
                elif "FUNCTION" in stmt:
                    obj_name = stmt.split("FUNCTION")[1].split("(")[0].strip()
                elif "PROCEDURE" in stmt:
                    obj_name = stmt.split("PROCEDURE")[1].split("(")[0].strip()
            elif stmt_type == "COMMENT":
                obj_name = stmt.split("TABLE")[1].split()[0] if "TABLE" in stmt else "UNKNOWN"
            elif stmt_type == "GRANT":
                obj_name = stmt.split("ON")[1].split()[0].strip()
            elif stmt_type == "BEGIN": # For anonymous PL/SQL blocks
                obj_name = "PL/SQL Block"

            try:
                cursor.execute(stmt)
                connection.commit()
                print(f"  [{i:02d}] ✅ {stmt_type} {obj_name}")
                success_count += 1
            except oracledb.DatabaseError as e:
                error = e.args[0]
                if "ORA-00955" in str(error) or "ORA-02262" in str(error) or "ORA-00942" in str(error):
                    print(f"  [{i:02d}] ⚠️  {stmt_type} {obj_name} (already exists or dependency issue)")
                    success_count += 1
                else:
                    print(f"  [{i:02d}] ❌ {stmt_type} {obj_name}: {error}")
                    error_count += 1
        
        # Verify tables created
        print("\n" + "=" * 60)
        print("Verifying Schema Objects")
        print("=" * 60)
        
        cursor.execute("""
            SELECT object_name, object_type FROM user_objects 
            WHERE object_name LIKE 'ATLAS%' OR object_name LIKE 'SEQ_ATLAS%' 
            ORDER BY object_type, object_name
        """)
        objects = cursor.fetchall()
        print(f"\nObjects created/verified: {len(objects)}")
        for obj in objects:
            print(f"  - {obj[0]} ({obj[1]})")
        
        cursor.close()
        connection.close()
        
        print("\n" + "=" * 60)
        print(f"Schema Deployment Complete")
        print(f"  Success: {success_count}")
        print(f"  Errors:  {error_count}")
        print("=" * 60)
        
        return 0 if error_count == 0 else 1
        
    except oracledb.Error as e:
        print(f"\n❌ Database connection error: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
