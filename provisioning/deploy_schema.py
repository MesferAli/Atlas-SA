#!/usr/bin/env python3
"""
Atlas on OCI - Schema Deployment Script
Deploys the simplified schema to the Autonomous Database (ATP)
"""

import oracledb
import os
import sys

# Database connection parameters
DB_USER = "ADMIN"
DB_PASSWORD = "AtlasMZX#2026Secure!"
DB_DSN = "atlasdb_high"
WALLET_DIR = os.path.expanduser("~/atlas_wallet")

# DDL statements - split into individual statements for execution
DDL_STATEMENTS = [
    # HR Module Tables
    """CREATE TABLE ATLAS_LOCATIONS (
        LOCATION_ID             NUMBER          PRIMARY KEY,
        LOCATION_NAME           VARCHAR2(60)    NOT NULL,
        ADDRESS_LINE_1          VARCHAR2(240),
        CITY                    VARCHAR2(60),
        REGION                  VARCHAR2(60),
        COUNTRY                 VARCHAR2(60),
        DATA_CLASSIFICATION     VARCHAR2(20)    DEFAULT 'PUBLIC',
        LAST_SYNC_DATE          TIMESTAMP       NOT NULL
    )""",
    "CREATE INDEX IDX_LOCATIONS_NAME ON ATLAS_LOCATIONS(LOCATION_NAME)",
    
    """CREATE TABLE ATLAS_DEPARTMENTS (
        DEPARTMENT_ID           NUMBER          PRIMARY KEY,
        DEPARTMENT_NAME         VARCHAR2(240)   NOT NULL,
        PARENT_DEPARTMENT_ID    NUMBER          REFERENCES ATLAS_DEPARTMENTS(DEPARTMENT_ID),
        MANAGER_ID              NUMBER,
        DATA_CLASSIFICATION     VARCHAR2(20)    DEFAULT 'INTERNAL',
        LAST_SYNC_DATE          TIMESTAMP       NOT NULL
    )""",
    "CREATE INDEX IDX_DEPARTMENTS_NAME ON ATLAS_DEPARTMENTS(DEPARTMENT_NAME)",
    "CREATE INDEX IDX_DEPARTMENTS_PARENT ON ATLAS_DEPARTMENTS(PARENT_DEPARTMENT_ID)",
    
    """CREATE TABLE ATLAS_EMPLOYEES (
        EMPLOYEE_ID             NUMBER          PRIMARY KEY,
        EMPLOYEE_NUMBER         VARCHAR2(30)    NOT NULL UNIQUE,
        FULL_NAME               VARCHAR2(240)   NOT NULL,
        JOB_TITLE               VARCHAR2(120),
        DEPARTMENT_ID           NUMBER          REFERENCES ATLAS_DEPARTMENTS(DEPARTMENT_ID),
        LOCATION_ID             NUMBER          REFERENCES ATLAS_LOCATIONS(LOCATION_ID),
        HIRE_DATE               DATE,
        ASSIGNMENT_STATUS       VARCHAR2(30),
        MANAGER_ID              NUMBER          REFERENCES ATLAS_EMPLOYEES(EMPLOYEE_ID),
        DATA_CLASSIFICATION     VARCHAR2(20)    DEFAULT 'INTERNAL',
        LAST_SYNC_DATE          TIMESTAMP       NOT NULL
    )""",
    "CREATE INDEX IDX_EMPLOYEES_NAME ON ATLAS_EMPLOYEES(FULL_NAME)",
    "CREATE INDEX IDX_EMPLOYEES_DEPT ON ATLAS_EMPLOYEES(DEPARTMENT_ID)",
    "CREATE INDEX IDX_EMPLOYEES_LOC ON ATLAS_EMPLOYEES(LOCATION_ID)",
    "CREATE INDEX IDX_EMPLOYEES_MANAGER ON ATLAS_EMPLOYEES(MANAGER_ID)",
    "CREATE INDEX IDX_EMPLOYEES_STATUS ON ATLAS_EMPLOYEES(ASSIGNMENT_STATUS)",
    
    # Finance Module Tables
    """CREATE TABLE ATLAS_SUPPLIERS (
        SUPPLIER_ID             NUMBER          PRIMARY KEY,
        SUPPLIER_NAME           VARCHAR2(360)   NOT NULL,
        SUPPLIER_NUMBER         VARCHAR2(30)    UNIQUE,
        SUPPLIER_TYPE           VARCHAR2(30),
        TAX_REGISTRATION_NUMBER VARCHAR2(50),
        STATUS                  VARCHAR2(30),
        DATA_CLASSIFICATION     VARCHAR2(20)    DEFAULT 'INTERNAL',
        LAST_SYNC_DATE          TIMESTAMP       NOT NULL
    )""",
    "CREATE INDEX IDX_SUPPLIERS_NAME ON ATLAS_SUPPLIERS(SUPPLIER_NAME)",
    "CREATE INDEX IDX_SUPPLIERS_STATUS ON ATLAS_SUPPLIERS(STATUS)",
    
    """CREATE TABLE ATLAS_PURCHASE_ORDERS (
        PO_ID                   NUMBER          PRIMARY KEY,
        PO_NUMBER               VARCHAR2(20)    NOT NULL UNIQUE,
        SUPPLIER_ID             NUMBER          REFERENCES ATLAS_SUPPLIERS(SUPPLIER_ID),
        CURRENCY_CODE           VARCHAR2(15),
        TOTAL_AMOUNT            NUMBER,
        STATUS                  VARCHAR2(30),
        APPROVED_DATE           DATE,
        CREATED_BY              VARCHAR2(100),
        CREATION_DATE           DATE,
        DATA_CLASSIFICATION     VARCHAR2(20)    DEFAULT 'RESTRICTED',
        LAST_SYNC_DATE          TIMESTAMP       NOT NULL
    )""",
    "CREATE INDEX IDX_PO_SUPPLIER ON ATLAS_PURCHASE_ORDERS(SUPPLIER_ID)",
    "CREATE INDEX IDX_PO_STATUS ON ATLAS_PURCHASE_ORDERS(STATUS)",
    "CREATE INDEX IDX_PO_DATE ON ATLAS_PURCHASE_ORDERS(CREATION_DATE)",
    
    """CREATE TABLE ATLAS_AP_INVOICES (
        INVOICE_ID              NUMBER          PRIMARY KEY,
        INVOICE_NUMBER          VARCHAR2(50)    NOT NULL,
        SUPPLIER_ID             NUMBER          REFERENCES ATLAS_SUPPLIERS(SUPPLIER_ID),
        INVOICE_DATE            DATE,
        INVOICE_AMOUNT          NUMBER,
        AMOUNT_PAID             NUMBER,
        PAYMENT_STATUS          VARCHAR2(30),
        CURRENCY_CODE           VARCHAR2(15),
        DUE_DATE                DATE,
        DATA_CLASSIFICATION     VARCHAR2(20)    DEFAULT 'RESTRICTED',
        LAST_SYNC_DATE          TIMESTAMP       NOT NULL
    )""",
    "CREATE INDEX IDX_AP_INV_SUPPLIER ON ATLAS_AP_INVOICES(SUPPLIER_ID)",
    "CREATE INDEX IDX_AP_INV_STATUS ON ATLAS_AP_INVOICES(PAYMENT_STATUS)",
    "CREATE INDEX IDX_AP_INV_DATE ON ATLAS_AP_INVOICES(INVOICE_DATE)",
    "CREATE INDEX IDX_AP_INV_DUE ON ATLAS_AP_INVOICES(DUE_DATE)",
    
    """CREATE TABLE ATLAS_GL_BALANCES (
        BALANCE_ID              NUMBER          PRIMARY KEY,
        LEDGER_ID               NUMBER          NOT NULL,
        ACCOUNT_CODE            VARCHAR2(100)   NOT NULL,
        ACCOUNT_DESCRIPTION     VARCHAR2(240),
        PERIOD_NAME             VARCHAR2(15)    NOT NULL,
        CURRENCY_CODE           VARCHAR2(15),
        PERIOD_NET_DR           NUMBER,
        PERIOD_NET_CR           NUMBER,
        BEGIN_BALANCE_DR        NUMBER,
        BEGIN_BALANCE_CR        NUMBER,
        DATA_CLASSIFICATION     VARCHAR2(20)    DEFAULT 'RESTRICTED',
        LAST_SYNC_DATE          TIMESTAMP       NOT NULL
    )""",
    "CREATE INDEX IDX_GL_BAL_LEDGER ON ATLAS_GL_BALANCES(LEDGER_ID)",
    "CREATE INDEX IDX_GL_BAL_ACCOUNT ON ATLAS_GL_BALANCES(ACCOUNT_CODE)",
    "CREATE INDEX IDX_GL_BAL_PERIOD ON ATLAS_GL_BALANCES(PERIOD_NAME)",
    
    # AI Vector Search Support Tables
    """CREATE TABLE ATLAS_DOCUMENTS (
        DOCUMENT_ID             NUMBER          PRIMARY KEY,
        DOCUMENT_NAME           VARCHAR2(255)   NOT NULL,
        DOCUMENT_TYPE           VARCHAR2(50),
        SOURCE_SYSTEM           VARCHAR2(50),
        OBJECT_STORAGE_PATH     VARCHAR2(500),
        CREATED_DATE            TIMESTAMP       NOT NULL,
        LAST_UPDATED_DATE       TIMESTAMP
    )""",
    "CREATE INDEX IDX_DOCS_TYPE ON ATLAS_DOCUMENTS(DOCUMENT_TYPE)",
    "CREATE INDEX IDX_DOCS_SOURCE ON ATLAS_DOCUMENTS(SOURCE_SYSTEM)",
    
    # Note: VECTOR type requires Oracle 23ai - using BLOB for 19c compatibility
    """CREATE TABLE ATLAS_DOCUMENT_CHUNKS (
        CHUNK_ID                NUMBER          PRIMARY KEY,
        DOCUMENT_ID             NUMBER          NOT NULL REFERENCES ATLAS_DOCUMENTS(DOCUMENT_ID),
        CHUNK_TEXT              CLOB            NOT NULL,
        CHUNK_SEQUENCE          NUMBER          NOT NULL,
        EMBEDDING               BLOB,
        CREATED_DATE            TIMESTAMP       NOT NULL
    )""",
    "CREATE INDEX IDX_CHUNKS_DOC ON ATLAS_DOCUMENT_CHUNKS(DOCUMENT_ID)",
    
    # Audit and Logging Table
    """CREATE TABLE ATLAS_AUDIT_LOG (
        LOG_ID                  NUMBER          PRIMARY KEY,
        EVENT_TYPE              VARCHAR2(50)    NOT NULL,
        USER_ID                 VARCHAR2(100),
        CLIENT_IP               VARCHAR2(50),
        RESOURCE_TYPE           VARCHAR2(50),
        ACTION                  VARCHAR2(100),
        DETAILS                 CLOB,
        SUCCESS                 VARCHAR2(1)     DEFAULT 'Y',
        ERROR_MESSAGE           VARCHAR2(4000),
        CREATED_DATE            TIMESTAMP       NOT NULL
    )""",
    "CREATE INDEX IDX_AUDIT_EVENT ON ATLAS_AUDIT_LOG(EVENT_TYPE)",
    "CREATE INDEX IDX_AUDIT_USER ON ATLAS_AUDIT_LOG(USER_ID)",
    "CREATE INDEX IDX_AUDIT_DATE ON ATLAS_AUDIT_LOG(CREATED_DATE)",
    
    # Sequences
    "CREATE SEQUENCE SEQ_ATLAS_DOCUMENTS START WITH 1 INCREMENT BY 1",
    "CREATE SEQUENCE SEQ_ATLAS_CHUNKS START WITH 1 INCREMENT BY 1",
    "CREATE SEQUENCE SEQ_ATLAS_AUDIT_LOG START WITH 1 INCREMENT BY 1",
    "CREATE SEQUENCE SEQ_ATLAS_GL_BALANCES START WITH 1 INCREMENT BY 1",
    
    # Comments
    "COMMENT ON TABLE ATLAS_EMPLOYEES IS 'Simplified employee records from Oracle Fusion HCM'",
    "COMMENT ON TABLE ATLAS_DEPARTMENTS IS 'Organizational unit information from Oracle Fusion HCM'",
    "COMMENT ON TABLE ATLAS_LOCATIONS IS 'Work location information from Oracle Fusion HCM'",
    "COMMENT ON TABLE ATLAS_SUPPLIERS IS 'Supplier/Vendor master data from Oracle Fusion Procurement'",
    "COMMENT ON TABLE ATLAS_PURCHASE_ORDERS IS 'Purchase order headers from Oracle Fusion Procurement'",
    "COMMENT ON TABLE ATLAS_AP_INVOICES IS 'Accounts Payable invoices from Oracle Fusion Financials'",
    "COMMENT ON TABLE ATLAS_GL_BALANCES IS 'General Ledger account balances from Oracle Fusion Financials'",
    "COMMENT ON TABLE ATLAS_DOCUMENTS IS 'Document metadata for RAG knowledge base'",
    "COMMENT ON TABLE ATLAS_DOCUMENT_CHUNKS IS 'Chunked document text with vector embeddings for semantic search'",
    "COMMENT ON TABLE ATLAS_AUDIT_LOG IS 'Audit trail for all Atlas operations'",
]

def main():
    print("=" * 60)
    print("Atlas on OCI - Schema Deployment")
    print("=" * 60)
    
    # Configure wallet location
    print(f"\nConfiguring wallet from: {WALLET_DIR}")
    
    try:
        # Connect to the database using wallet
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
        
        # Execute each DDL statement
        success_count = 0
        error_count = 0
        
        for i, stmt in enumerate(DDL_STATEMENTS, 1):
            stmt_type = stmt.split()[0].upper()
            if stmt_type == "CREATE":
                obj_type = stmt.split()[1].upper()
                if obj_type == "TABLE":
                    obj_name = stmt.split()[2].split("(")[0]
                elif obj_type == "INDEX":
                    obj_name = stmt.split()[2]
                elif obj_type == "SEQUENCE":
                    obj_name = stmt.split()[2]
                else:
                    obj_name = "UNKNOWN"
            elif stmt_type == "COMMENT":
                obj_name = stmt.split("TABLE")[1].split()[0] if "TABLE" in stmt else "UNKNOWN"
            else:
                obj_name = "UNKNOWN"
            
            try:
                cursor.execute(stmt)
                connection.commit()
                print(f"  [{i:02d}] ✅ {stmt_type} {obj_name}")
                success_count += 1
            except oracledb.DatabaseError as e:
                error = e.args[0]
                if "ORA-00955" in str(error):  # Object already exists
                    print(f"  [{i:02d}] ⚠️  {stmt_type} {obj_name} (already exists)")
                    success_count += 1
                else:
                    print(f"  [{i:02d}] ❌ {stmt_type} {obj_name}: {error}")
                    error_count += 1
        
        # Verify tables created
        print("\n" + "=" * 60)
        print("Verifying Schema Objects")
        print("=" * 60)
        
        cursor.execute("""
            SELECT table_name FROM user_tables 
            WHERE table_name LIKE 'ATLAS%' 
            ORDER BY table_name
        """)
        tables = cursor.fetchall()
        print(f"\nTables created: {len(tables)}")
        for table in tables:
            cursor.execute(f"SELECT COUNT(*) FROM {table[0]}")
            count = cursor.fetchone()[0]
            print(f"  - {table[0]} ({count} rows)")
        
        cursor.execute("""
            SELECT sequence_name FROM user_sequences 
            WHERE sequence_name LIKE 'SEQ_ATLAS%' 
            ORDER BY sequence_name
        """)
        sequences = cursor.fetchall()
        print(f"\nSequences created: {len(sequences)}")
        for seq in sequences:
            print(f"  - {seq[0]}")
        
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
