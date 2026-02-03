CREATE OR REPLACE PACKAGE ATLAS_CONFIG_PKG AS
    -- OCI Generative AI Configuration
    FUNCTION GET_GENAI_ENDPOINT RETURN VARCHAR2;
    FUNCTION GET_GENAI_COMPARTMENT_ID RETURN VARCHAR2;
    FUNCTION GET_GENAI_MODEL_ID RETURN VARCHAR2;

    -- Oracle Fusion Integration Configuration
    FUNCTION GET_FUSION_BASE_URL RETURN VARCHAR2;
    FUNCTION GET_FUSION_USER RETURN VARCHAR2;

    -- OCI API Gateway Configuration
    FUNCTION GET_API_GATEWAY_ENDPOINT RETURN VARCHAR2;

    -- Other Settings
    FUNCTION GET_LOG_LEVEL RETURN VARCHAR2;

    -- Intelligence Package Configuration
    FUNCTION GET_CRITICAL_INVOICE_THRESHOLD RETURN VARCHAR2;
    FUNCTION GET_PO_STAGNANT_DAYS RETURN VARCHAR2;
    FUNCTION GET_HR_PENDING_THRESHOLD RETURN VARCHAR2;
    FUNCTION GET_DAYS_TO_KEEP_RESOLVED_ALERTS RETURN VARCHAR2;

    -- Procedure to set configuration values (for dynamic updates if needed)
    PROCEDURE SET_CONFIG_VALUE(p_key IN VARCHAR2, p_value IN VARCHAR2);

END ATLAS_CONFIG_PKG;
/

CREATE OR REPLACE PACKAGE BODY ATLAS_CONFIG_PKG AS
    -- Private variables to hold configuration values
    pv_genai_endpoint VARCHAR2(500) := 'https://inference.generativeai.me-riyadh-1.oci.oraclecloud.com';
    pv_genai_compartment_id VARCHAR2(200) := 'ocid1.compartment.oc1..aaaaaaaaxpz4hdeamim7eu4aqeqqgm5napbf7higzo3xdlovx3q5djrqu2tq';
    pv_genai_model_id VARCHAR2(100) := 'cohere.command-r-plus';

    pv_fusion_base_url VARCHAR2(500) := 'https://fa-etid-saasfaprod1.fa.ocs.oraclecloud.com';
    pv_fusion_user VARCHAR2(200) := 'mesfer@xcyrcle.co';

    pv_api_gateway_endpoint VARCHAR2(500) := 'https://jpopcryemdv3rdlu4j63tmd5cm.apigateway.me-riyadh-1.oci.customer-oci.com/atlas/v1';

    pv_log_level VARCHAR2(20) := 'INFO';

    pv_critical_invoice_threshold VARCHAR2(100) := '100000';
    pv_po_stagnant_days VARCHAR2(100) := '7';
    pv_hr_pending_threshold VARCHAR2(100) := '5';
    pv_days_to_keep_resolved_alerts VARCHAR2(100) := '30';

    FUNCTION GET_GENAI_ENDPOINT RETURN VARCHAR2 IS BEGIN RETURN pv_genai_endpoint; END;
    FUNCTION GET_GENAI_COMPARTMENT_ID RETURN VARCHAR2 IS BEGIN RETURN pv_genai_compartment_id; END;
    FUNCTION GET_GENAI_MODEL_ID RETURN VARCHAR2 IS BEGIN RETURN pv_genai_model_id; END;

    FUNCTION GET_FUSION_BASE_URL RETURN VARCHAR2 IS BEGIN RETURN pv_fusion_base_url; END;
    FUNCTION GET_FUSION_USER RETURN VARCHAR2 IS BEGIN RETURN pv_fusion_user; END;

    FUNCTION GET_API_GATEWAY_ENDPOINT RETURN VARCHAR2 IS BEGIN RETURN pv_api_gateway_endpoint; END;

    FUNCTION GET_LOG_LEVEL RETURN VARCHAR2 IS BEGIN RETURN pv_log_level; END;

    FUNCTION GET_CRITICAL_INVOICE_THRESHOLD RETURN VARCHAR2 IS BEGIN RETURN pv_critical_invoice_threshold; END;
    FUNCTION GET_PO_STAGNANT_DAYS RETURN VARCHAR2 IS BEGIN RETURN pv_po_stagnant_days; END;
    FUNCTION GET_HR_PENDING_THRESHOLD RETURN VARCHAR2 IS BEGIN RETURN pv_hr_pending_threshold; END;
    FUNCTION GET_DAYS_TO_KEEP_RESOLVED_ALERTS RETURN VARCHAR2 IS BEGIN RETURN pv_days_to_keep_resolved_alerts; END;

    PROCEDURE SET_CONFIG_VALUE(p_key IN VARCHAR2, p_value IN VARCHAR2) IS
    BEGIN
        CASE p_key
            WHEN 'GENAI_ENDPOINT' THEN pv_genai_endpoint := p_value;
            WHEN 'GENAI_COMPARTMENT_ID' THEN pv_genai_compartment_id := p_value;
            WHEN 'GENAI_MODEL_ID' THEN pv_genai_model_id := p_value;
            WHEN 'FUSION_BASE_URL' THEN pv_fusion_base_url := p_value;
            WHEN 'FUSION_USER' THEN pv_fusion_user := p_value;
            WHEN 'API_GATEWAY_ENDPOINT' THEN pv_api_gateway_endpoint := p_value;
            WHEN 'LOG_LEVEL' THEN pv_log_level := p_value;
            WHEN 'CRITICAL_INVOICE_THRESHOLD' THEN pv_critical_invoice_threshold := p_value;
            WHEN 'PO_STAGNANT_DAYS' THEN pv_po_stagnant_days := p_value;
            WHEN 'HR_PENDING_THRESHOLD' THEN pv_hr_pending_threshold := p_value;
            WHEN 'DAYS_TO_KEEP_RESOLVED_ALERTS' THEN pv_days_to_keep_resolved_alerts := p_value;
            ELSE NULL; -- Log warning for unknown key
        END CASE;
    END;

END ATLAS_CONFIG_PKG;
/
