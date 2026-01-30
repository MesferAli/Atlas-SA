# Atlas on OCI - APEX Application Design

**Version:** 1.0
**Date:** January 30, 2026
**Author:** Manus AI

## 1. Introduction

This document describes the design and structure of the Oracle APEX application that serves as the user interface for the Atlas platform. The application is designed to be minimalist and high-performance, adhering to the project's core principles of avoiding over-engineering and leveraging native OCI/APEX features.

The APEX application provides the "Atlas Interface," which includes a dashboard for operational intelligence and a "Command Bar" for natural language interaction with Oracle Fusion data.

## 2. Application Overview

| Property | Value |
|---|---|
| **Application Name** | Atlas |
| **Application Alias** | ATLAS |
| **Theme** | Universal Theme (Theme 42) |
| **Authentication Scheme** | Oracle APEX Accounts (or OCI IAM Integration) |
| **Authorization Scheme** | Role-Based Access Control (RBAC) |
| **Language** | English (with Arabic support for bilingual UI) |

## 3. Page Structure

The application consists of the following pages, designed to provide a clean and intuitive user experience.

| Page ID | Page Name | Description | Access Level |
|---|---|---|---|
| 1 | Home (Dashboard) | Main dashboard with KPIs, status cards, and quick links. | All authenticated users |
| 2 | Command Bar | Natural language query interface powered by OCI Generative AI. | ANALYST, ADMIN |
| 10 | Employees | Interactive report on employee data from `ATLAS_EMPLOYEES`. | ANALYST, ADMIN |
| 11 | Departments | Interactive report on department data from `ATLAS_DEPARTMENTS`. | ANALYST, ADMIN |
| 20 | Suppliers | Interactive report on supplier data from `ATLAS_SUPPLIERS`. | ANALYST, ADMIN |
| 21 | Purchase Orders | Interactive report on PO data from `ATLAS_PURCHASE_ORDERS`. | ANALYST, ADMIN |
| 22 | AP Invoices | Interactive report on invoice data from `ATLAS_AP_INVOICES`. | ANALYST, ADMIN |
| 30 | GL Balances | Interactive report on GL balances from `ATLAS_GL_BALANCES`. | ADMIN |
| 100 | Audit Log | Interactive report on audit events from `ATLAS_AUDIT_LOG`. | ADMIN |
| 101 | Settings | Application settings and configuration. | ADMIN |
| 9999 | Login | Login page. | Public |

## 4. Page Designs

### 4.1. Page 1: Home (Dashboard)

The dashboard is the primary landing page for users. It provides a high-level overview of key metrics and system status.

**Regions:**

1.  **Welcome Banner**: A static content region displaying a welcome message and the current date/time.
2.  **KPI Cards**: A cards region displaying key performance indicators:
    *   Total Employees (from `ATLAS_EMPLOYEES`)
    *   Active Purchase Orders (from `ATLAS_PURCHASE_ORDERS`)
    *   Unpaid Invoices (from `ATLAS_AP_INVOICES`)
    *   Data Sync Status (last sync timestamp)
3.  **Quick Links**: A list region with links to common tasks (e.g., "Run a Query," "View Employees").
4.  **Proactive Alerts**: A region displaying AI-generated alerts based on data trends (e.g., "5 invoices are past due").

### 4.2. Page 2: Command Bar

This page hosts the core AI-powered natural language interface.

**Regions:**

1.  **Command Input**: A form region containing:
    *   `P2_COMMAND`: A text area for the user to enter their natural language query.
    *   `P2_SUBMIT`: A button to submit the query.
2.  **Response Display**: A rich text region to display the AI-generated response, including:
    *   The interpreted intent.
    *   The generated SQL query (if applicable).
    *   The results in a formatted table or chart.
3.  **Query History**: A classic report region showing the user's recent queries.

**Processes:**

1.  **Process Command**: An AJAX callback process that:
    *   Takes the user's input from `P2_COMMAND`.
    *   Calls the OCI Generative AI service via a REST API.
    *   Parses the response and populates the display regions.

### 4.3. Data Report Pages (10, 11, 20, 21, 22, 30)

These pages follow a consistent pattern for displaying data from the simplified schema.

**Regions:**

1.  **Interactive Report**: An interactive report based on the corresponding `ATLAS_*` table. Features include:
    *   Filtering and sorting.
    *   Column selection.
    *   Export to CSV/Excel.
    *   Highlighting for specific data classifications.

### 4.4. Page 100: Audit Log

This page provides administrators with access to the audit trail.

**Regions:**

1.  **Audit Log Report**: An interactive report on `ATLAS_AUDIT_LOG` with filters for:
    *   Event Type
    *   User ID
    *   Date Range
    *   Success/Failure

## 5. REST Data Sources

The application uses REST Data Sources to connect to Oracle Fusion and OCI services. The following data sources are configured.

### 5.1. Oracle Fusion REST APIs

These data sources connect to Oracle Fusion Cloud to retrieve data for caching.

| Data Source Name | Base URL | Authentication | Description |
|---|---|---|---|
| `FUSION_HCM_WORKERS` | `https://<fusion_host>/hcmRestApi/resources/11.13.18.05/workers` | OAuth 2.0 | Retrieves worker (employee) data. |
| `FUSION_HCM_DEPARTMENTS` | `https://<fusion_host>/hcmRestApi/resources/11.13.18.05/departments` | OAuth 2.0 | Retrieves department data. |
| `FUSION_PROCUREMENT_POS` | `https://<fusion_host>/fscmRestApi/resources/11.13.18.05/purchaseOrders` | OAuth 2.0 | Retrieves purchase order data. |
| `FUSION_FINANCIALS_INVOICES` | `https://<fusion_host>/fscmRestApi/resources/11.13.18.05/invoices` | OAuth 2.0 | Retrieves AP invoice data. |
| `FUSION_FINANCIALS_SUPPLIERS` | `https://<fusion_host>/fscmRestApi/resources/11.13.18.05/suppliers` | OAuth 2.0 | Retrieves supplier data. |

### 5.2. OCI Services

These data sources connect to OCI services for AI and other platform capabilities.

| Data Source Name | Base URL | Authentication | Description |
|---|---|---|---|
| `OCI_GENAI_CHAT` | `https://inference.generativeai.<region>.oci.oraclecloud.com/20231130/actions/chat` | OCI Signature | Calls the OCI Generative AI chat endpoint. |

## 6. Shared Components

### 6.1. Application Items

| Item Name | Scope | Description |
|---|---|---|
| `G_USER_ROLE` | Application | Stores the current user's RBAC role (e.g., ADMIN, ANALYST). |
| `G_LAST_SYNC_DATE` | Application | Stores the timestamp of the last data synchronization. |

### 6.2. Application Processes

| Process Name | Point | Description |
|---|---|---|
| `Set User Role` | After Authentication | Queries the user's role and sets `G_USER_ROLE`. |

### 6.3. Authorization Schemes

| Scheme Name | Type | Expression | Description |
|---|---|---|---|
| `IS_ADMIN` | PL/SQL Function | `RETURN :G_USER_ROLE = 'ADMIN';` | Grants access to admin-only features. |
| `IS_ANALYST_OR_ADMIN` | PL/SQL Function | `RETURN :G_USER_ROLE IN ('ADMIN', 'ANALYST');` | Grants access to analyst and admin features. |

### 6.4. Templates and Styling

The application uses the Universal Theme with custom CSS for branding.

*   **Logo**: Atlas logo displayed in the navigation bar.
*   **Color Scheme**: A professional color palette aligned with the organization's branding.
*   **RTL Support**: CSS rules for right-to-left layout when Arabic is selected.

## 7. Data Synchronization

Data is synchronized from Oracle Fusion to the local `ATLAS_*` tables using scheduled APEX Automations or OCI Integration Cloud flows.

### 7.1. Synchronization Strategy

1.  **Full Sync**: A complete refresh of all data, typically run during off-peak hours (e.g., nightly).
2.  **Incremental Sync**: A delta sync that retrieves only records modified since the last sync, run more frequently (e.g., hourly).

### 7.2. Synchronization Process

1.  **Fetch Data**: Call the Fusion REST API via the configured REST Data Source.
2.  **Transform Data**: Map the Fusion data structure to the simplified schema.
3.  **Load Data**: Use `MERGE` statements to upsert data into the `ATLAS_*` tables.
4.  **Update Timestamp**: Update the `LAST_SYNC_DATE` column for all affected records.
5.  **Log Event**: Write a record to `ATLAS_AUDIT_LOG` for the sync operation.

## 8. Security Considerations

*   **Authentication**: All users must authenticate before accessing the application. OCI IAM integration is recommended for enterprise deployments.
*   **Authorization**: Page and component access is controlled by Authorization Schemes based on user roles.
*   **Data Classification**: Reports highlight data based on its `DATA_CLASSIFICATION` column, and access to SECRET data is restricted to authorized roles.
*   **Session Management**: APEX session state is protected, and session timeout is configured appropriately.
*   **Input Validation**: All user inputs are validated to prevent SQL injection and XSS attacks.
