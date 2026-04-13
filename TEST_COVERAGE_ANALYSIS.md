# Test Coverage Analysis - Atlas-OCI

## Executive Summary

The Atlas-OCI project has **critically low test coverage**. The codebase contains approximately 16,000 Python source files (mostly in the OCI Python SDK) and 6 custom provisioning scripts plus 8 SQL packages, yet only **7 actual test files** exist — all within the SDK. The custom Atlas provisioning and deployment code has **zero automated test coverage**.

---

## Current Test Inventory

| Test File | Category | What It Tests | Lines |
|-----------|----------|---------------|-------|
| `tests/unit/test_basic_api_calls.py` | Unit | Identity, VCN, Compute list operations (4 tests) | 42 |
| `tests/unit/test_response.py` | Unit | `oci.Response` object construction and header parsing (3 tests) | 54 |
| `tests/unit/test_waiters.py` | Unit/Integ | `oci.wait_until` behavior: basic wait, multiple states, invalid ops, timeouts, callbacks, 401 retry (10 tests) | 442 |
| `tests/autogentest/test_model.py` | Unit | Model instantiation, equality, serialization, enums, subclass dispatch (15 tests) | 152 |
| `tests/test_util.py` | Unit | `enum_to_snake` utility function (10 parametrized cases) | 24 |
| `tests/test_config_container.py` | Infra | VCR test configuration helpers (not actual test assertions) | 52 |
| `tests/integ/test_launch_instance_tutorial.py` | Integration | Full lifecycle: VCN → Subnet → Gateway → Instance → Volume (1 end-to-end test) | 324 |

**Total: ~42 individual test cases across 7 files (~1,090 lines of test code)**

---

## Coverage Gaps by Area

### 1. CRITICAL: Provisioning Scripts — Zero Coverage

All six Python deployment scripts have no tests at all:

| File | Purpose | Risk |
|------|---------|------|
| `provisioning/config.py` | Centralized configuration from env vars | Misconfiguration silently breaks all deployments |
| `provisioning/deploy_schema.py` | Deploys DDL to Oracle ATP | Schema drift, silent failures on existing objects |
| `provisioning/deploy_fusion_integration.py` | Deploys Fusion integration SQL | References non-existent config properties (`DB_WALLET_DIR`, `DB_WALLET_PASSWORD`) |
| `provisioning/deploy_rag_pipeline.py` | Deploys RAG PL/SQL objects | Contains inline validation tests but no automated coverage |
| `provisioning/setup_apex.py` | Sets up APEX workspace and application | References non-existent config properties (`DB_WALLET_DIR`, `OCI_REGION`) |
| `provisioning/security_verification.py` | Runs security mandate checks | Verification script that is itself unverified |

**Specific bugs found during this analysis (all fixed in this PR):**
- `deploy_fusion_integration.py`, `deploy_rag_pipeline.py`, and `setup_apex.py` all referenced `config.DB_WALLET_DIR`, `config.DB_WALLET_PASSWORD`, and (in one case) `config.OCI_REGION`, none of which existed in `config.py`. Any invocation raised `AttributeError` at import time. The attributes are now defined on `Config` and a regression test in `provisioning/tests/test_config.py` AST-scans every sibling script and asserts that referenced attributes exist.
- `fusion_sync_integration.sql` called `ATLAS_HTTP_UTILS_PKG.MAKE_REQUEST` with `p_username`, `p_password`, `p_response`, `p_status_code` — none of which match the real signature. The package would have failed to compile. All three call sites now use the actual signature (URL/method/headers, function return value, `APEX_WEB_SERVICE.GET_STATUS_CODE` for status), and a shared `BUILD_FUSION_AUTH_HEADERS` helper builds the Basic auth header.

### 2. CRITICAL: SQL Packages — Zero Coverage

Eight SQL packages define the core business logic with no automated testing:

| Package | Purpose | Risk |
|---------|---------|------|
| `atlas_config.sql` | Configuration getters/setters | No validation of config values |
| `atlas_http_utils.sql` | REST API calls with retry | Retry logic untested; error handling untested |
| `atlas_intelligence_pkg.sql` | Proactive business alerts | Alert thresholds and detection logic untested |
| `atlas_nl_to_sql.sql` | Natural language → SQL conversion | SQL injection via GenAI response untested |
| `atlas_rag_pkg.sql` | RAG pipeline (embed, search, query) | Document chunking and vector search untested |
| `atlas_vector_utils.sql` | Vector embeddings and similarity search | `SEARCH_SIMILAR_DOCUMENTS` is now implemented but cosine scoring and top-K selection have no fixture-based tests |
| `fusion_sync_integration.sql` | Fusion data sync (HR, AP, PO) | Sync MERGE logic and JSON parsing are untested; previous `MAKE_REQUEST` signature mismatch was fixed in this PR |
| `schema_ddl.sql` | Table/index/sequence DDL | No validation that schema matches code expectations |

### 3. HIGH: SDK Core Infrastructure — Minimal Coverage

These foundational SDK modules have little to no test coverage:

| Module | What It Does | Current Coverage |
|--------|-------------|-----------------|
| `config.py` | Load/validate OCI config files | **None** — `from_file()`, `validate_config()` untested |
| `signer.py` | Request signing (SHA256, RSA) | **None** — signing logic, key loading untested |
| `base_client.py` | HTTP request dispatch, serialization | **None** — the most critical SDK class is untested |
| `exceptions.py` | 15+ exception classes | **None** — only `ServiceError` and `MaximumWaitTimeExceeded` exercised indirectly |
| `regions.py` | Region lookup and endpoint resolution | **None** |
| `fips.py` | FIPS mode support | **None** |
| `alloy.py` | Alloy provider mode | **None** |
| `decorators.py` | `@init_model_state_from_kwargs` | **None** |
| `auth/` (22 files) | Instance principals, resource principals, federation, token exchange | **None** — zero auth signer tests |
| `retry/` (4 files) | Retry strategies, backoff, jitter, checkers | **None** — retry logic untested |
| `encryption/` (4+ files) | Encrypt/decrypt with KMS | **None** |
| `pagination/` (2 files) | `list_call_get_all_results`, generators | **None** |
| `circuit_breaker/` (2 files) | Circuit breaker pattern | **None** |

### 4. MEDIUM: Existing Tests Are Mostly Integration Tests

The current waiter tests and basic API call tests require live OCI infrastructure or VCR cassettes. There are almost no **pure unit tests** that can run without any external dependencies:
- `test_response.py` — pure unit test (good)
- `test_model.py` — pure unit test (good)
- `test_util.py` — pure unit test (good)
- `test_401_retry_on_waiters` in `test_waiters.py` — uses mock objects (good)
- Everything else requires OCI config and either a live tenancy or VCR cassettes

---

## Recommended Test Improvements

### Priority 1 — Fix Broken Code Discovered During Analysis

These are not test improvements but bugs found because of missing tests. Items 1 and 2 were addressed in the same PR that introduced this analysis:

1. ~~**Fix `config.py` missing attributes**: Add `DB_WALLET_DIR`, `DB_WALLET_PASSWORD`, and `OCI_REGION` properties or fix the scripts that reference them~~ — **done**, with a regression test in `provisioning/tests/test_config.py`
2. ~~**Fix `fusion_sync_integration.sql`**: The `MAKE_REQUEST` call uses parameters (`p_username`, `p_password`, `p_response`, `p_status_code`) that don't match `ATLAS_HTTP_UTILS_PKG.MAKE_REQUEST()`~~ — **done**, all three call sites now use the real signature
3. ~~**Implement `atlas_vector_utils.sql` `SEARCH_SIMILAR_DOCUMENTS`**: Currently a placeholder returning empty results~~ — already implemented; needs fixture-based tests for cosine scoring and top-K selection

### Priority 2 — Provisioning Script Unit Tests

Add a `provisioning/tests/` directory with pytest-based tests:

- **`test_config.py`**: Validate that all expected config properties exist, defaults are correct, and environment variable overrides work
- **`test_deploy_schema.py`**: Test DDL statement parsing and splitting logic (mock `oracledb`). Verify that error categorization (ORA-00955 vs others) works correctly
- **`test_deploy_rag_pipeline.py`**: Test the SQL validation logic (the 13 forbidden keyword checks). Extract and unit-test the query validator independently
- **`test_deploy_fusion_integration.py`**: Test SQL statement splitting by "/" delimiter. Verify connection parameter assembly
- **`test_setup_apex.py`**: Test APEX setup statement generation with mocked database
- **`test_security_verification.py`**: Test result aggregation logic and JSON report generation with mock data

### Priority 3 — SDK Core Unit Tests

Add pure unit tests (no OCI config required) for core SDK infrastructure:

- **`test_config.py`**: Test `from_file()` with valid/invalid/missing config files, `validate_config()` with various inputs, profile selection, passphrase handling
- **`test_signer.py`**: Test request signing with known key pairs, header injection, `load_private_key()` with valid/invalid PEM data
- **`test_base_client.py`**: Test request construction, user-agent building, header sanitization, response deserialization with mocked HTTP
- **`test_exceptions.py`**: Test exception hierarchy, `ServiceError` message formatting, error code handling
- **`test_regions.py`**: Test region lookup, short name mapping, endpoint resolution, unknown region handling
- **`test_retry.py`**: Test `RetryStrategyBuilder`, backoff calculations, jitter ranges, retry checkers (time-exceeded, limit-based), `NoneRetryStrategy`
- **`test_pagination.py`**: Test `list_call_get_all_results()` and generators with mock responses containing `opc-next-page` headers
- **`test_circuit_breaker.py`**: Test `CircuitBreakerStrategy` state transitions (closed → open → half-open)
- **`test_encryption.py`**: Test encrypt/decrypt round-trip with mock KMS provider

### Priority 4 — Authentication Module Tests

The `auth/` directory contains 22 files covering multiple authentication strategies with zero coverage:

- **`test_security_token_signer.py`**: Test token refresh lifecycle, expiry detection
- **`test_instance_principals.py`**: Test IMDS metadata retrieval with mocked HTTP, certificate parsing
- **`test_resource_principals.py`**: Test environment variable reading for RP v1.1, v2.1, v2.2 flows
- **`test_federation_client.py`**: Test X509 federation token exchange with mocked service
- **`test_certificate_retriever.py`**: Test URL-based, PEM-string, and file-based certificate loading

### Priority 5 — SQL Package Functional Tests

Create a test harness that validates PL/SQL logic with a test database:

- **Query validation tests**: Exhaustively test `ATLAS_VALIDATE_QUERY` and `ATLAS_RAG_PKG.validate_query()` with SQL injection patterns, edge cases (comments, quoted strings, CTEs)
- **Document chunking tests**: Test `ATLAS_INGEST_DOCUMENT` / `ATLAS_RAG_PKG.ingest_document()` with known documents, verify chunk boundaries and overlap
- **Alert generation tests**: Test `ATLAS_INTELLIGENCE_PKG` procedures with seed data, verify correct alert types and severities
- **Fusion sync tests**: Test `ATLAS_FUSION_SYNC_PKG` MERGE logic with sample JSON payloads
- **NL-to-SQL tests**: Test `ATLAS_GENAI_NL_TO_SQL` response parsing with sample GenAI outputs, verify SQL extraction from `<sql>` tags

---

## Coverage Metrics Summary

| Area | Source Files | Test Files | Coverage |
|------|-------------|------------|----------|
| SDK Core Infrastructure | ~55 | 0 | **0%** |
| SDK Service Modules | ~16,000 | 3 (basic API + waiter + model) | **<0.1%** |
| Provisioning Python | 6 | 0 | **0%** |
| Provisioning SQL | 8 | 0 | **0%** |
| APEX Pages | 4 | 0 | **0%** |

The highest-impact improvements would be in **Priority 1** (fixing discovered bugs), **Priority 2** (provisioning tests), and **Priority 3** (SDK core tests), as these cover custom code unique to this project where defects cannot be caught by upstream testing.
