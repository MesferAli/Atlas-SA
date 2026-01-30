# Atlas on OCI - Implementation Guide

**Version:** 1.0
**Date:** January 30, 2026
**Author:** Manus AI

## 1. Introduction

This guide provides step-by-step instructions for deploying and configuring the Atlas project on Oracle Cloud Infrastructure (OCI). By following these steps, you will provision the necessary infrastructure, set up the database schema, configure the APEX application, and deploy the AI/RAG intelligence layer.

## 2. Prerequisites

Before you begin, ensure you have the following:

*   An OCI account with appropriate permissions to create and manage resources.
*   The OCI CLI installed and configured on your local machine.
*   Access to an Oracle Fusion instance with REST API enabled.
*   A user account in the Oracle Fusion instance with the necessary roles to access the required data.
*   The compartment OCID where you will deploy the Atlas resources.
*   A public subnet OCID for the API Gateway.

## 3. Step-by-Step Implementation

### 3.1. OCI Infrastructure Provisioning

1.  **Navigate to the `provisioning` directory:**

    ```bash
    cd /home/ubuntu/atlas_oci/provisioning
    ```

2.  **Edit the `provision_oci.sh` script:**

    *   Replace `<your_compartment_ocid>` with your OCI compartment OCID.
    *   Replace `<YourSecurePassword123>` with a strong password for the Autonomous Database admin user.
    *   Replace `<your_public_subnet_ocid>` with the OCID of your public subnet.

3.  **Run the provisioning script:**

    ```bash
    bash provision_oci.sh
    ```

    This script will create the following resources:

    *   A dedicated compartment for the Atlas project.
    *   An Autonomous Database (ATP) instance.
    *   An API Gateway.
    *   An Object Storage bucket.

### 3.2. Database Schema Setup

1.  **Connect to the Autonomous Database:**

    *   Use a SQL client (e.g., SQL Developer, SQLcl) to connect to the ATP instance you created. You will need the database credentials and wallet file.

2.  **Run the DDL script:**

    *   Execute the `schema_ddl.sql` script to create the simplified schema, tables, indexes, and sequences.

    ```sql
    -- Connect as the ATLAS_ADMIN user or a user with appropriate privileges
    @schema_ddl.sql
    ```

### 3.3. APEX Application Setup

1.  **Create an APEX Workspace:**

    *   Navigate to the APEX instance associated with your ATP.
    *   Create a new workspace named `ATLAS` and associate it with the database schema you created.

2.  **Create the APEX Application:**

    *   Create a new application named `Atlas`.
    *   Follow the design outlined in `apex_application.md` to create the pages, regions, items, and processes.

3.  **Configure REST Data Sources:**

    *   In the APEX Application Builder, navigate to **Shared Components > REST Data Sources**.
    *   Create the REST Data Sources for Oracle Fusion and OCI Generative AI as defined in `apex_application.md` and `fusion_hcm_workers.sql`.
    *   Configure the authentication for each data source (OAuth2 for Fusion, OCI Signature for OCI services).

### 3.4. OCI API Gateway Configuration

1.  **Deploy the API Gateway Configuration:**

    *   Use the OCI CLI to deploy the API Gateway configuration from `api_gateway_config.json`.

    ```bash
    oci api-gateway deployment create --gateway-id <your_api_gateway_id> --specification file://api_gateway_config.json
    ```

    *   Replace `<your_api_gateway_id>` with the OCID of the API Gateway you created.

### 3.5. RAG Pipeline Setup

1.  **Deploy the RAG PL/SQL Package:**

    *   Connect to the ATP and execute the `atlas_rag_pkg.sql` script to create the RAG pipeline package.

    ```sql
    @atlas_rag_pkg.sql
    ```

2.  **Configure Web Credentials:**

    *   In APEX, create a Web Credential named `OCI_GENAI_CREDENTIAL` for OCI Signature authentication, providing the necessary OCI user and key information.

3.  **Ingest Documents:**

    *   To populate the RAG knowledge base, use the `ATLAS_RAG_PKG.ingest_document` procedure. You will need to first upload your documents to OCI Object Storage and extract their text content.

### 3.6. Data Synchronization

1.  **Schedule Synchronization Jobs:**

    *   Use APEX Automations or OCI Integration Cloud to schedule the data synchronization process.
    *   The PL/SQL block in `fusion_hcm_workers.sql` provides a template for synchronizing employee data. Create similar processes for other data entities.

## 4. Conclusion

Once you have completed these steps, the Atlas on OCI platform will be fully deployed and configured. You can now access the APEX application and begin using the Command Bar to interact with your Oracle Fusion data.
