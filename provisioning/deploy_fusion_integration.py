import oracledb
import os
import sys
import config

def main():
    print("=" * 60)
    print("Atlas on OCI - Fusion Integration Deployment")
    print("=" * 60)
    
    # Configure wallet location
    wallet_dir = os.path.expanduser(config.DB_WALLET_DIR)
    print(f"\nConfiguring wallet from: {wallet_dir}")
    
    try:
        # Connect to the database using wallet
        print(f"\nConnecting to ATP database...")
        connection = oracledb.connect(
            user=config.DB_USER,
            password=config.DB_PASSWORD,
            dsn=config.DB_DSN,
            config_dir=wallet_dir,
            wallet_location=wallet_dir,
            wallet_password=config.DB_WALLET_PASSWORD
        )
        print("✅ Connected successfully!")
        
        cursor = connection.cursor()
        
        # Read and execute fusion_sync_integration.sql
        with open(os.path.join(os.path.dirname(__file__), "fusion_sync_integration.sql"), "r") as f:
            fusion_integration_sql = f.read()
        
        # Split SQL statements by ";" and filter out empty strings
        sql_statements = [stmt.strip() for stmt in fusion_integration_sql.split("/") if stmt.strip()]
        
        success_count = 0
        error_count = 0
        
        for i, stmt in enumerate(sql_statements, 1):
            if not stmt.strip():
                continue
            try:
                cursor.execute(stmt)
                connection.commit()
                print(f"  [{i:02d}] ✅ Executed statement")
                success_count += 1
            except oracledb.DatabaseError as e:
                error = e.args[0]
                print(f"  [{i:02d}] ❌ Error executing statement: {error}")
                error_count += 1
        
        cursor.close()
        connection.close()
        
        print("\n" + "=" * 60)
        print(f"Fusion Integration Deployment Complete")
        print(f"  Success: {success_count}")
        print(f"  Errors:  {error_count}")
        print("=" * 60)
        
        return 0 if error_count == 0 else 1
        
    except oracledb.Error as e:
        print(f"\n❌ Database connection error: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
