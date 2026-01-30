# Atlas on OCI

This project contains the design and implementation artifacts for deploying the Atlas project on Oracle Cloud Infrastructure (OCI). Atlas is a simplified, AI-driven interface for Oracle Fusion, built with Oracle APEX and OCI-native services.

## Project Structure

- `docs/`: Contains all design and implementation documentation.
  - `oci_architecture.md`: OCI infrastructure architecture design.
  - `database_schema.md`: Simplified database schema design for data caching.
  - `apex_application.md`: APEX application structure and component design.
  - `ai_rag_implementation.md`: AI/RAG intelligence layer design.
  - `oci_architecture.png`: OCI architecture diagram.
  - `erd.png`: Entity-Relationship Diagram for the simplified schema.
- `provisioning/`: Contains scripts for provisioning OCI resources and the database schema.
  - `provision_oci.sh`: Shell script to automate OCI resource creation.
  - `schema_ddl.sql`: SQL DDL script to create the simplified database schema.
  - `api_gateway_config.json`: Configuration for the OCI API Gateway.
  - `atlas_rag_pkg.sql`: PL/SQL package for the RAG pipeline.
- `apex/`: Contains conceptual definitions for the APEX application components.
  - `pages/`: Page definitions.
  - `rest_data_sources/`: REST Data Source definitions.

## Implementation Guide

For a complete guide to implementing the Atlas on OCI project, please refer to the `implementation_guide.md` in the `docs` directory.
