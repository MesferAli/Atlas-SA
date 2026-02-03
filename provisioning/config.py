import os

class Config:
    # OCI Database Connection
    DB_USER = os.getenv("DB_USER", "ADMIN")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "AtlasMZX#2026Secure!")
    DB_DSN = os.getenv("DB_DSN", "atlasdb_high")
    DB_WALLET_PATH = os.getenv("DB_WALLET_PATH", "/home/ubuntu/atlas_wallet")

    # OCI Generative AI
    OCI_GENAI_ENDPOINT = os.getenv("OCI_GENAI_ENDPOINT", "https://inference.generativeai.me-riyadh-1.oci.oraclecloud.com")
    OCI_GENAI_COMPARTMENT_ID = os.getenv("OCI_GENAI_COMPARTMENT_ID", "ocid1.compartment.oc1..aaaaaaaaxpz4hdeamim7eu4aqeqqgm5napbf7higzo3xdlovx3q5djrqu2tq")
    OCI_GENAI_MODEL_ID = os.getenv("OCI_GENAI_MODEL_ID", "cohere.command-r-plus")

    # Oracle Fusion Integration
    FUSION_BASE_URL = os.getenv("FUSION_BASE_URL", "https://fa-etid-saasfaprod1.fa.ocs.oraclecloud.com")
    FUSION_USER = os.getenv("FUSION_USER", "mesfer@xcyrcle.co")
    FUSION_PASSWORD = os.getenv("FUSION_PASSWORD", "AtlasMZX#2026Secure!")

    # OCI API Gateway
    API_GATEWAY_ENDPOINT = os.getenv("API_GATEWAY_ENDPOINT", "https://jpopcryemdv3rdlu4j63tmd5cm.apigateway.me-riyadh-1.oci.customer-oci.com/atlas/v1")

    # Other Settings
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
