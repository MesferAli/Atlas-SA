#!/bin/bash

# Atlas on OCI - Provisioning Script
#
# This script automates the provisioning of the required OCI resources for the Atlas project.
#
# Prerequisites:
# - OCI CLI installed and configured with appropriate credentials.
# - A compartment OCID to deploy the resources into.

set -e

echo "Starting Atlas on OCI provisioning..."

# --- Configuration ---
# Replace with your Compartment OCID
COMPARTMENT_ID="<your_compartment_ocid>"

# --- Resource Naming ---
PREFIX="Atlas"

# --- Compartment ---
echo "Creating dedicated compartment for Atlas..."
ATLAS_COMPARTMENT_ID=$(oci iam compartment create \
  --name "${PREFIX}Compartment" \
  --description "Compartment for the Atlas project" \
  --compartment-id $COMPARTMENT_ID \
  --query "data.id" --raw-output)

echo "Compartment created with OCID: $ATLAS_COMPARTMENT_ID"

# --- Autonomous Database (ATP) ---
echo "Provisioning Autonomous Database (ATP)..."
ATP_ID=$(oci db autonomous-database create \
  --compartment-id $ATLAS_COMPARTMENT_ID \
  --display-name "${PREFIX}ATP" \
  --db-name "${PREFIX}DB" \
  --admin-password "<YourSecurePassword123>" \
  --db-workload "OLTP" \
  --cpu-core-count 1 \
  --data-storage-size-in-tbs 1 \
  --is-auto-scaling-enabled true \
  --is-free-tier false \
  --query "data.id" --raw-output)

echo "Autonomous Database created with OCID: $ATP_ID"

# --- API Gateway ---
echo "Creating API Gateway..."
API_GATEWAY_ID=$(oci api-gateway gateway create \
  --compartment-id $ATLAS_COMPARTMENT_ID \
  --display-name "${PREFIX}APIGateway" \
  --endpoint-type "PUBLIC" \
  --subnet-id "<your_public_subnet_ocid>" \
  --query "data.id" --raw-output)

echo "API Gateway created with OCID: $API_GATEWAY_ID"

# --- Object Storage ---
echo "Creating Object Storage bucket for documents and logs..."
OBJECT_STORAGE_NAMESPACE=$(oci os ns get --query "data" --raw-output)
oci os bucket create \
  --namespace $OBJECT_STORAGE_NAMESPACE \
  --name "${PREFIX}Documents" \
  --compartment-id $ATLAS_COMPARTMENT_ID

echo "Object Storage bucket '${PREFIX}Documents' created."

echo "Provisioning complete!"
