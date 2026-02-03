CREATE OR REPLACE PACKAGE ATLAS_HTTP_UTILS_PKG AS
    FUNCTION MAKE_REQUEST(
        p_url           IN VARCHAR2,
        p_method        IN VARCHAR2 DEFAULT 'GET',
        p_body          IN CLOB DEFAULT NULL,
        p_headers       IN CLOB DEFAULT NULL,
        p_credential_name IN VARCHAR2 DEFAULT NULL,
        p_max_retries   IN NUMBER DEFAULT 3,
        p_retry_delay_sec IN NUMBER DEFAULT 5
    ) RETURN CLOB;

    PROCEDURE LOG_HTTP_ERROR(
        p_url           IN VARCHAR2,
        p_status_code   IN NUMBER,
        p_response_body IN CLOB,
        p_error_message IN VARCHAR2
    );
END ATLAS_HTTP_UTILS_PKG;
/

CREATE OR REPLACE PACKAGE BODY ATLAS_HTTP_UTILS_PKG AS

    FUNCTION MAKE_REQUEST(
        p_url           IN VARCHAR2,
        p_method        IN VARCHAR2 DEFAULT 'GET',
        p_body          IN CLOB DEFAULT NULL,
        p_headers       IN CLOB DEFAULT NULL,
        p_credential_name IN VARCHAR2 DEFAULT NULL,
        p_max_retries   IN NUMBER DEFAULT 3,
        p_retry_delay_sec IN NUMBER DEFAULT 5
    ) RETURN CLOB
    IS
        l_response_clob CLOB;
        l_http_code     NUMBER;
        l_retry_count   NUMBER := 0;
        l_headers       APEX_WEB_SERVICE.VC_ARR;
        l_header_name   VARCHAR2(4000);
        l_header_value  VARCHAR2(4000);
        l_json_headers  APEX_JSON.T_VALUES;
    BEGIN
        -- Parse headers if provided
        IF p_headers IS NOT NULL THEN
            APEX_JSON.PARSE(l_json_headers, p_headers);
            FOR i IN 1 .. APEX_JSON.GET_COUNT(l_json_headers) LOOP
                l_header_name := APEX_JSON.GET_KEY_NAME(l_json_headers, i);
                l_header_value := APEX_JSON.GET_VARCHAR2(l_json_headers, l_header_name);
                APEX_WEB_SERVICE.G_REQUEST_HEADERS(l_headers.COUNT+1).NAME := l_header_name;
                APEX_WEB_SERVICE.G_REQUEST_HEADERS(l_headers.COUNT).VALUE := l_header_value;
            END LOOP;
        END IF;

        LOOP
            BEGIN
                IF p_method = 'POST' THEN
                    l_response_clob := APEX_WEB_SERVICE.MAKE_REST_REQUEST(
                        p_url           => p_url,
                        p_http_method   => p_method,
                        p_body          => p_body,
                        p_credential_static_id => p_credential_name
                    );
                ELSE -- GET, PUT, DELETE etc.
                    l_response_clob := APEX_WEB_SERVICE.MAKE_REST_REQUEST(
                        p_url           => p_url,
                        p_http_method   => p_method,
                        p_credential_static_id => p_credential_name
                    );
                END IF;

                l_http_code := APEX_WEB_SERVICE.GET_STATUS_CODE;

                IF l_http_code BETWEEN 200 AND 299 THEN
                    RETURN l_response_clob;
                ELSIF l_http_code BETWEEN 500 AND 599 AND l_retry_count < p_max_retries THEN
                    l_retry_count := l_retry_count + 1;
                    DBMS_LOCK.SLEEP(p_retry_delay_sec);
                    ATLAS_AUDIT_LOG_PKG.LOG_EVENT(
                        p_event_type => 'HTTP_RETRY',
                        p_resource_type => 'EXTERNAL_API',
                        p_action => 'RETRY_REQUEST',
                        p_details => 'URL: ' || p_url || ', Method: ' || p_method || ', Status: ' || l_http_code || ', Retry Count: ' || l_retry_count
                    );
                ELSE
                    LOG_HTTP_ERROR(p_url, l_http_code, l_response_clob, 'HTTP Request Failed');
                    RETURN NULL;
                END IF;
            EXCEPTION
                WHEN OTHERS THEN
                    IF l_retry_count < p_max_retries THEN
                        l_retry_count := l_retry_count + 1;
                        DBMS_LOCK.SLEEP(p_retry_delay_sec);
                        ATLAS_AUDIT_LOG_PKG.LOG_EVENT(
                            p_event_type => 'HTTP_RETRY',
                            p_resource_type => 'EXTERNAL_API',
                            p_action => 'RETRY_EXCEPTION',
                            p_details => 'URL: ' || p_url || ', Method: ' || p_method || ', Error: ' || SQLERRM || ', Retry Count: ' || l_retry_count
                        );
                    ELSE
                        LOG_HTTP_ERROR(p_url, NULL, NULL, SQLERRM);
                        RETURN NULL;
                    END IF;
            END;
        END LOOP;
    END MAKE_REQUEST;

    PROCEDURE LOG_HTTP_ERROR(
        p_url           IN VARCHAR2,
        p_status_code   IN NUMBER,
        p_response_body IN CLOB,
        p_error_message IN VARCHAR2
    )
    IS
        l_details CLOB;
    BEGIN
        l_details := 'URL: ' || p_url || ', Status Code: ' || NVL(TO_CHAR(p_status_code), 'N/A') || ', Error: ' || p_error_message;
        IF p_response_body IS NOT NULL THEN
            l_details := l_details || ', Response Body: ' || DBMS_LOB.SUBSTR(p_response_body, 2000, 1);
        END IF;

        ATLAS_AUDIT_LOG_PKG.LOG_EVENT(
            p_event_type => 'HTTP_ERROR',
            p_resource_type => 'EXTERNAL_API',
            p_action => 'REQUEST_FAILED',
            p_details => l_details
        );
    END LOG_HTTP_ERROR;

END ATLAS_HTTP_UTILS_PKG;
/
