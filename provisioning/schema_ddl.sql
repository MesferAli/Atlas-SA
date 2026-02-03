-- Atlas on OCI - Simplified Schema DDL
-- Version: 1.1
-- Date: February 03, 2026
--
-- This script creates the simplified schema for the Atlas platform
-- in the OCI Autonomous Database (ATP).
--
-- IMPORTANT: Run this script as the ATLAS_ADMIN user or a user with
-- CREATE TABLE, CREATE SEQUENCE, and CREATE INDEX privileges.

-- ============================================================
-- 1. Human Resources (HR) Module Tables
-- ============================================================

-- ATLAS_LOCATIONS: Work location information
CREATE TABLE ATLAS_LOCATIONS (
    LOCATION_ID             NUMBER          PRIMARY KEY,
    LOCATION_NAME           VARCHAR2(60)    NOT NULL,
    ADDRESS_LINE_1          VARCHAR2(240),
    CITY                    VARCHAR2(60),
    REGION                  VARCHAR2(60),
    COUNTRY                 VARCHAR2(60),
    DATA_CLASSIFICATION     VARCHAR2(20)    DEFAULT 'PUBLIC',
    LAST_SYNC_DATE          TIMESTAMP       NOT NULL
);

CREATE INDEX IDX_LOCATIONS_NAME ON ATLAS_LOCATIONS(LOCATION_NAME);

-- ATLAS_DEPARTMENTS: Organizational unit information
CREATE TABLE ATLAS_DEPARTMENTS (
    DEPARTMENT_ID           NUMBER          PRIMARY KEY,
    DEPARTMENT_NAME         VARCHAR2(240)   NOT NULL,
    PARENT_DEPARTMENT_ID    NUMBER          REFERENCES ATLAS_DEPARTMENTS(DEPARTMENT_ID),
    MANAGER_ID              NUMBER,
    DATA_CLASSIFICATION     VARCHAR2(20)    DEFAULT 'INTERNAL',
    LAST_SYNC_DATE          TIMESTAMP       NOT NULL
);

CREATE INDEX IDX_DEPARTMENTS_NAME ON ATLAS_DEPARTMENTS(DEPARTMENT_NAME);
CREATE INDEX IDX_DEPARTMENTS_PARENT ON ATLAS_DEPARTMENTS(PARENT_DEPARTMENT_ID);

-- ATLAS_EMPLOYEES: Employee records
CREATE TABLE ATLAS_EMPLOYEES (
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
);

CREATE INDEX IDX_EMPLOYEES_NAME ON ATLAS_EMPLOYEES(FULL_NAME);
CREATE INDEX IDX_EMPLOYEES_DEPT ON ATLAS_EMPLOYEES(DEPARTMENT_ID);
CREATE INDEX IDX_EMPLOYEES_LOC ON ATLAS_EMPLOYEES(LOCATION_ID);
CREATE INDEX IDX_EMPLOYEES_MANAGER ON ATLAS_EMPLOYEES(MANAGER_ID);
CREATE INDEX IDX_EMPLOYEES_STATUS ON ATLAS_EMPLOYEES(ASSIGNMENT_STATUS);

-- ============================================================
-- 2. Finance Module Tables
-- ============================================================

-- ATLAS_SUPPLIERS: Supplier/Vendor master data
CREATE TABLE ATLAS_SUPPLIERS (
    SUPPLIER_ID             NUMBER          PRIMARY KEY,
    SUPPLIER_NAME           VARCHAR2(360)   NOT NULL,
    SUPPLIER_NUMBER         VARCHAR2(30)    UNIQUE,
    SUPPLIER_TYPE           VARCHAR2(30),
    TAX_REGISTRATION_NUMBER VARCHAR2(50),
    STATUS                  VARCHAR2(30),
    DATA_CLASSIFICATION     VARCHAR2(20)    DEFAULT 'INTERNAL',
    LAST_SYNC_DATE          TIMESTAMP       NOT NULL
);

CREATE INDEX IDX_SUPPLIERS_NAME ON ATLAS_SUPPLIERS(SUPPLIER_NAME);
CREATE INDEX IDX_SUPPLIERS_STATUS ON ATLAS_SUPPLIERS(STATUS);

-- ATLAS_PURCHASE_ORDERS: Purchase order headers
CREATE TABLE ATLAS_PURCHASE_ORDERS (
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
);

CREATE INDEX IDX_PO_SUPPLIER ON ATLAS_PURCHASE_ORDERS(SUPPLIER_ID);
CREATE INDEX IDX_PO_STATUS ON ATLAS_PURCHASE_ORDERS(STATUS);
CREATE INDEX IDX_PO_DATE ON ATLAS_PURCHASE_ORDERS(CREATION_DATE);

-- ATLAS_AP_INVOICES: Accounts Payable invoices
CREATE TABLE ATLAS_AP_INVOICES (
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
);

CREATE INDEX IDX_AP_INV_SUPPLIER ON ATLAS_AP_INVOICES(SUPPLIER_ID);
CREATE INDEX IDX_AP_INV_STATUS ON ATLAS_AP_INVOICES(PAYMENT_STATUS);
CREATE INDEX IDX_AP_INV_DATE ON ATLAS_AP_INVOICES(INVOICE_DATE);
CREATE INDEX IDX_AP_INV_DUE ON ATLAS_AP_INVOICES(DUE_DATE);

-- ATLAS_GL_BALANCES: General Ledger account balances
CREATE TABLE ATLAS_GL_BALANCES (
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
);

CREATE INDEX IDX_GL_BAL_LEDGER ON ATLAS_GL_BALANCES(LEDGER_ID);
CREATE INDEX IDX_GL_BAL_ACCOUNT ON ATLAS_GL_BALANCES(ACCOUNT_CODE);
CREATE INDEX IDX_GL_BAL_PERIOD ON ATLAS_GL_BALANCES(PERIOD_NAME);

-- ============================================================
-- 3. AI Vector Search Support Tables
-- ============================================================

-- ATLAS_DOCUMENTS: Document metadata for RAG knowledge base
CREATE TABLE ATLAS_DOCUMENTS (
    DOCUMENT_ID             NUMBER          PRIMARY KEY,
    DOCUMENT_NAME           VARCHAR2(255)   NOT NULL,
    DOCUMENT_TYPE           VARCHAR2(50),
    SOURCE_SYSTEM           VARCHAR2(50),
    OBJECT_STORAGE_PATH     VARCHAR2(500),
    CREATED_DATE            TIMESTAMP       NOT NULL,
    LAST_UPDATED_DATE       TIMESTAMP
);

CREATE INDEX IDX_DOCS_TYPE ON ATLAS_DOCUMENTS(DOCUMENT_TYPE);
CREATE INDEX IDX_DOCS_SOURCE ON ATLAS_DOCUMENTS(SOURCE_SYSTEM);

-- ATLAS_DOCUMENT_CHUNKS: Chunked text with vector embeddings
CREATE TABLE ATLAS_DOCUMENT_CHUNKS (
    CHUNK_ID                NUMBER          PRIMARY KEY,
    DOCUMENT_ID             NUMBER          NOT NULL REFERENCES ATLAS_DOCUMENTS(DOCUMENT_ID),
    CHUNK_TEXT              CLOB            NOT NULL,
    CHUNK_SEQUENCE          NUMBER          NOT NULL,
    EMBEDDING               CLOB,           -- Storing embeddings as JSON string in CLOB for broader compatibility
    CREATED_DATE            TIMESTAMP       NOT NULL
);

CREATE INDEX IDX_CHUNKS_DOC ON ATLAS_DOCUMENT_CHUNKS(DOCUMENT_ID);

-- ============================================================
-- 4. Audit and Logging Table
-- ============================================================

-- ATLAS_AUDIT_LOG: Audit trail for all operations
CREATE TABLE ATLAS_AUDIT_LOG (
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
);

CREATE INDEX IDX_AUDIT_EVENT ON ATLAS_AUDIT_LOG(EVENT_TYPE);
CREATE INDEX IDX_AUDIT_USER ON ATLAS_AUDIT_LOG(USER_ID);
CREATE INDEX IDX_AUDIT_DATE ON ATLAS_AUDIT_LOG(CREATED_DATE);

-- ============================================================
-- 5. Sequences for Primary Keys
-- ============================================================

CREATE SEQUENCE SEQ_ATLAS_DOCUMENTS START WITH 1 INCREMENT BY 1;
CREATE SEQUENCE SEQ_ATLAS_CHUNKS START WITH 1 INCREMENT BY 1;
CREATE SEQUENCE SEQ_ATLAS_AUDIT_LOG START WITH 1 INCREMENT BY 1;
CREATE SEQUENCE SEQ_ATLAS_GL_BALANCES START WITH 1 INCREMENT BY 1;

-- ============================================================
-- 6. Comments on Tables
-- ============================================================

COMMENT ON TABLE ATLAS_EMPLOYEES IS 'Simplified employee records from Oracle Fusion HCM';
COMMENT ON TABLE ATLAS_DEPARTMENTS IS 'Organizational unit information from Oracle Fusion HCM';
COMMENT ON TABLE ATLAS_LOCATIONS IS 'Work location information from Oracle Fusion HCM';
COMMENT ON TABLE ATLAS_SUPPLIERS IS 'Supplier/Vendor master data from Oracle Fusion Procurement';
COMMENT ON TABLE ATLAS_PURCHASE_ORDERS IS 'Purchase order headers from Oracle Fusion Procurement';
COMMENT ON TABLE ATLAS_AP_INVOICES IS 'Accounts Payable invoices from Oracle Fusion Financials';
COMMENT ON TABLE ATLAS_GL_BALANCES IS 'General Ledger account balances from Oracle Fusion Financials';
COMMENT ON TABLE ATLAS_DOCUMENTS IS 'Document metadata for RAG knowledge base';
COMMENT ON TABLE ATLAS_DOCUMENT_CHUNKS IS 'Chunked document text with vector embeddings for semantic search';
COMMENT ON TABLE ATLAS_AUDIT_LOG IS 'Audit trail for all Atlas operations';

-- ============================================================
-- End of DDL Script
-- ============================================================
