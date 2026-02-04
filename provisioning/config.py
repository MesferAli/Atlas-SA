import os

class Config:
    # OCI Database Connection
    DB_USER = os.getenv("DB_USER", "ADMIN")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "AtlasMZX#2026Secure!")
    
    # mTLS Connection (Requires Wallet)
    DB_DSN_MTLS = os.getenv("DB_DSN_MTLS", "atlasdb_high")
    
    # Walletless TLS Connection (Recommended by Oracle)
    DB_DSN_TLS = os.getenv("DB_DSN_TLS", "(description= (retry_count=20)(retry_delay=3)(address=(protocol=tcps)(port=1522)(host=adb.me-riyadh-1.oraclecloud.com))(connect_data=(service_name=g05fa28d854c5e8_atlasdb_high.adb.oraclecloud.com))(security=(ssl_server_dn_match=yes)))")
    
    # Default connection to use (Switch to DB_DSN_MTLS if wallet is required)
    DB_DSN = os.getenv("DB_DSN", DB_DSN_TLS)
    
    DB_WALLET_PATH = os.getenv("DB_WALLET_PATH", "/home/ubuntu/atlas_wallet")
    USE_WALLET = os.getenv("USE_WALLET", "False").lower() == "true"

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
