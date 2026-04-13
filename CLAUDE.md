# CLAUDE.md

Guidance for AI assistants (Claude Code and similar) working on the **Atlas on OCI** repository.

## 1. What this project is

**Atlas** is a simplified, AI-driven interface over **Oracle Fusion** built on **Oracle Cloud Infrastructure (OCI)**. It combines:

- **Oracle APEX** — the user-facing application (dashboard + natural-language command bar).
- **Oracle Autonomous Database (ATP)** — a "simplified" cache of Fusion data (`ATLAS_*` tables) plus all business logic implemented as PL/SQL packages.
- **OCI Generative AI** (`cohere.command-r-plus`, `cohere.embed-multilingual-v3.0`) — powers the RAG pipeline and natural-language-to-SQL.
- **OCI API Gateway** — fronts REST endpoints.
- **Oracle Fusion REST APIs** — source-of-truth, synced into the ATLAS cache.

This repo is **design + deployment artifacts**, not a running application. Most code is SQL/PL-SQL; the Python in `provisioning/` exists solely to deploy those SQL artifacts into an ATP instance and to set up APEX.

## 2. Repository layout

```
Atlas-SA/
├── README.md                       Top-level overview
├── LICENSE                         MIT
├── .env.example                    Template for deployment env vars
├── .gitignore                      __pycache__, .pytest_cache
├── TEST_COVERAGE_ANALYSIS.md       Audit of (mostly missing) test coverage
├── deployment_report.md            Record of a past deployment run
├── security_verification_report.json  Output of security_verification.py
├── oci_resource_ocids.md           OCIDs referenced during provisioning
├── linkedin_post.md                Marketing copy (not code)
│
├── docs/                           All design documentation
│   ├── implementation_guide.md         Step-by-step deploy instructions
│   ├── oci_architecture.md / .mmd      OCI infra design
│   ├── database_schema.md              ATLAS_* schema description
│   ├── erd.mmd / erd.png               Entity-relationship diagram
│   ├── apex_application.md             APEX app structure
│   ├── apex_ui_specification.md        UI spec
│   ├── ai_rag_implementation.md        RAG design
│   ├── fusion_activation_guide.md      How to light up Fusion REST APIs
│   └── next_steps_roadmap.md
│
├── provisioning/                   Deployment code (Python + SQL)
│   ├── config.py                       Centralised env-var config (Config class)
│   ├── provision_oci.sh                Creates compartment, ATP, API Gateway, bucket
│   ├── deploy_schema.py                Runs schema_ddl.sql against ATP
│   ├── schema_ddl.sql                  Creates ATLAS_* tables, indexes, sequences
│   ├── atlas_config.sql                ATLAS_CONFIG_PKG (config getters/setters)
│   ├── atlas_http_utils.sql            ATLAS_HTTP_UTILS_PKG (REST client + retry)
│   ├── atlas_rag_pkg.sql               ATLAS_RAG_PKG (embed/search/query, read-only guard)
│   ├── atlas_vector_utils.sql          ATLAS_VECTOR_UTILS_PKG (cosine similarity, top-K)
│   ├── atlas_nl_to_sql.sql             NL → SQL conversion via GenAI
│   ├── atlas_intelligence_pkg.sql      ATLAS_INTELLIGENCE_PKG (proactive alerts)
│   ├── fusion_sync_integration.sql     ATLAS_FUSION_SYNC_PKG (HR/AP/PO sync from Fusion)
│   ├── deploy_fusion_integration.py    Deploys fusion_sync_integration.sql
│   ├── deploy_rag_pipeline.py          Deploys RAG packages
│   ├── setup_apex.py                   Creates APEX workspace + app via ORDS
│   ├── security_verification.py        Runs security mandate checks
│   ├── api_gateway_config.json         API Gateway deployment spec
│   ├── api_deployment.json
│   └── tests/
│       ├── __init__.py
│       └── test_config.py              Drift test: AST-scans scripts for Config refs
│
├── apex/                           APEX component definitions (declarative SQL)
│   ├── pages/
│   │   ├── page_001_dashboard.sql
│   │   ├── page_002_command_bar.sql
│   │   └── page_002_command_bar_full.sql
│   └── rest_data_sources/
│       └── fusion_hcm_workers.sql
│
└── oci-python-sdk/                 Vendored Oracle OCI Python SDK (upstream)
```

### The `oci-python-sdk/` directory is vendored upstream code

It is the full Oracle OCI Python SDK checked in for reference / offline access. **Do not modify files under `oci-python-sdk/`** unless the user explicitly asks for it. When searching the codebase, you almost always want to exclude it (`provisioning/` and `apex/` are where Atlas-specific code lives). The ~16,000 Python files there will otherwise swamp any grep.

## 3. Configuration model (critical)

All Python deployment scripts import a single `Config` class from `provisioning/config.py`. Every attribute is read from an environment variable with a default fallback. The canonical attributes are:

| Attribute | Purpose |
|---|---|
| `DB_USER`, `DB_PASSWORD` | ATP credentials |
| `DB_DSN_MTLS` | mTLS (wallet) connect string |
| `DB_DSN_TLS` | Walletless TLS connect string (**default**) |
| `DB_DSN` | Active DSN (defaults to `DB_DSN_TLS`) |
| `DB_WALLET_PATH` / `DB_WALLET_DIR` | Wallet directory (both names must stay in sync — older scripts use `_PATH`, newer use `_DIR`) |
| `DB_WALLET_PASSWORD` | Wallet password (may differ from DB password) |
| `USE_WALLET` | `"true"`/`"false"` string, coerced to bool |
| `OCI_REGION` | e.g. `me-riyadh-1` — used to build ORDS/APEX URLs |
| `OCI_GENAI_ENDPOINT`, `OCI_GENAI_COMPARTMENT_ID`, `OCI_GENAI_MODEL_ID` | OCI Generative AI |
| `FUSION_BASE_URL`, `FUSION_USER`, `FUSION_PASSWORD` | Oracle Fusion REST |
| `API_GATEWAY_ENDPOINT` | OCI API Gateway base |
| `LOG_LEVEL` |  |

### Drift-detection test — `provisioning/tests/test_config.py`

This test exists because past PRs shipped provisioning scripts that referenced `Config` attributes which did not exist, causing `AttributeError` **at import time** before any useful error could surface. The test:

1. AST-walks every sibling `.py` under `provisioning/` (excluding `config.py` itself).
2. Collects every attribute access of the form `config.X` / `Config.X` / aliased variants.
3. Asserts `hasattr(Config, X)` for every one of them.

**Rule for AI assistants:** if you add any `config.FOO` / `Config.FOO` reference to a provisioning script, you MUST also add `FOO` to `provisioning/config.py`. If you add a new Python file under `provisioning/`, the drift test will automatically pick it up — do not special-case it. Run `pytest provisioning/tests/` locally to verify.

## 4. Running things

### Install Python dependencies

There is no `requirements.txt` at the repo root. The provisioning scripts rely on:

- `oracledb` (Python driver for Oracle DB)
- `pytest` (for the config drift test)
- Optionally OCI SDK tools for `provision_oci.sh` (uses the `oci` CLI, not the Python SDK).

### Provision OCI infrastructure

```bash
cd provisioning
# Edit provision_oci.sh to set COMPARTMENT_ID, admin password, subnet OCID
bash provision_oci.sh
```

### Deploy database schema + PL/SQL packages

```bash
cd provisioning
# Ensure .env is populated (copy from .env.example)
python deploy_schema.py              # Creates ATLAS_* tables/indexes/sequences
python deploy_fusion_integration.py  # Creates ATLAS_FUSION_SYNC_PKG
python deploy_rag_pipeline.py        # Creates RAG / vector / NL-to-SQL packages
python setup_apex.py                 # Creates workspace and Atlas application
python security_verification.py      # Runs security mandate checks
```

All of these call the same `Config` object and support both wallet (mTLS) and walletless TLS connections.

### Run tests

```bash
pytest provisioning/tests/ -v
```

Only `test_config.py` exists in-repo as an Atlas-level test. There is **no coverage** for the PL/SQL packages or for deployment scripts beyond config-attribute drift. See `TEST_COVERAGE_ANALYSIS.md` for the full audit.

## 5. Conventions and invariants

### SQL / PL-SQL

- **Schema prefix:** every Atlas table is `ATLAS_*`, every sequence is `SEQ_ATLAS_*`, every package is `ATLAS_*_PKG`.
- **Idempotent DDL:** `deploy_schema.py` tolerates `ORA-00955` (name already in use), `ORA-02262`, and `ORA-00942`. When adding DDL, prefer statements that either succeed cleanly on fresh runs or produce one of those codes on re-runs. Do not use `DROP ... IF EXISTS` style constructs unless explicitly asked.
- **HTTP signature:** `ATLAS_HTTP_UTILS_PKG.MAKE_REQUEST` is a **function** that takes `(URL, method, headers, body)` and returns the response body. Status code is read separately via `APEX_WEB_SERVICE.GET_STATUS_CODE`. Do not reintroduce the old `p_username/p_password/p_response/p_status_code` parameter style — `fusion_sync_integration.sql` was previously broken on exactly this mismatch and it is the reason `BUILD_FUSION_AUTH_HEADERS` exists as a shared helper.
- **Read-only guard:** `ATLAS_RAG_PKG` enforces `C_FORBIDDEN_KEYWORDS` (`INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`, `CREATE`, `TRUNCATE`, `MERGE`, `GRANT`, `REVOKE`, `EXECUTE`, `CALL`) against NL-to-SQL output. Do not weaken this guard.
- **Vectors:** embeddings are stored as JSON CLOBs (`[0.12, -0.34, ...]`), not as `VECTOR` columns. `ATLAS_VECTOR_UTILS_PKG.COSINE_SIMILARITY` parses via `APEX_JSON` and returns 0 on mismatch/invalid input.
- **Data classification:** every ATLAS_* table has a `DATA_CLASSIFICATION` column (`PUBLIC` / `INTERNAL` / `CONFIDENTIAL`) and a `LAST_SYNC_DATE` column. New tables should follow the same pattern.

### Python

- Scripts are standalone, each with `main()` + `if __name__ == "__main__": sys.exit(main())`. No shared framework beyond `Config`.
- Exit code `0` on success, `1` on error; helpful human-readable output with ✅/❌/⚠️ markers is the existing style — keep it if you modify existing scripts, do not introduce logging frameworks for small edits.
- Secrets **must** come from env vars with `Config`; the defaults baked into `.env.example` and `config.py` are for local dev only and should never be replaced by hard-coded credentials.

### APEX

- Pages are defined via `APEX_PAGE.CREATE_PAGE` / `APEX_REGION.CREATE_REGION` declarative blocks. They are **not** full exported applications — they are snippets meant to be run in SQL Workshop against an already-created workspace/application.
- The application ID is `100`. Dashboard is page `1`, Command Bar is page `2`.

## 6. Git and branch workflow

- Default branch: `master`.
- Feature work lands via PRs (`claude/<slug>-<shortid>` branches from prior Claude sessions). Squash merges are the norm — see `git log --oneline`.
- **Never force-push master.** Never skip hooks. Never commit `.env`, wallets, or OCIDs of live tenancies — the defaults in `.env.example` and `config.py` are sensitive enough; do not add more.
- When making commits, create new commits rather than amending, and only commit files the user asked you to touch.

## 7. Gotchas and landmines

1. **The `oci-python-sdk/` tree is huge.** `grep`/`find` across the whole repo without excluding it will waste context. Use `Grep` with `path: "provisioning"` or `path: "apex"` for Atlas-specific searches.
2. **Config attribute drift** is the single most common cause of deployment failures in this repo's history. Any new `config.FOO` needs a corresponding `Config.FOO` — the test enforces this but only if you remember to run it.
3. **Two wallet-path aliases** (`DB_WALLET_PATH`, `DB_WALLET_DIR`) exist because older and newer scripts use different names. `DB_WALLET_DIR` defaults to `DB_WALLET_PATH`. Do not consolidate them without also updating every reference across `provisioning/*.py`.
4. **Walletless TLS is the default** (`USE_WALLET=False`). Do not assume a wallet file is present; gate any wallet-specific code behind `Config.USE_WALLET`.
5. **SQL files contain placeholders** like `<region>`, `<your_compartment_ocid>`, `<your_public_subnet_ocid>` that are intended to be substituted at deploy time (historically by hand or by the deployment scripts). Do not interpret them as bugs and do not commit real values into these files.
6. **No CI configuration** lives in this repo — there is no `.github/workflows/`, `tox.ini` for Atlas (the one under `oci-python-sdk/` belongs to the vendored SDK), or pre-commit config. Tests must be run manually.
7. **Zero PL/SQL test coverage.** If you change a `.sql` package, the only feedback loop is deploying it to ATP. Read `TEST_COVERAGE_ANALYSIS.md` before arguing about what is "safe" to change.
8. **Dates in file headers are aspirational** (January/February 2026). Do not treat them as an authoritative timeline; use `git log` for real history.

## 8. When asked to...

- **"Deploy the project"** → point the user at `docs/implementation_guide.md` and walk through `provision_oci.sh` → `deploy_schema.py` → `deploy_fusion_integration.py` → `deploy_rag_pipeline.py` → `setup_apex.py`. Do not run destructive commands yourself without confirmation.
- **"Add a new config value"** → edit `provisioning/config.py`, `.env.example`, and any referencing script, then run `pytest provisioning/tests/`.
- **"Add a new ATLAS table"** → extend `schema_ddl.sql` (keep `DATA_CLASSIFICATION` + `LAST_SYNC_DATE`), update `docs/database_schema.md`, and if it needs to sync from Fusion, extend `ATLAS_FUSION_SYNC_PKG` in `fusion_sync_integration.sql` following the existing `SYNC_EMPLOYEES` template (reuse `BUILD_FUSION_AUTH_HEADERS`).
- **"Extend the RAG pipeline"** → work in `atlas_rag_pkg.sql` and `atlas_vector_utils.sql`. Preserve the read-only keyword guard and the JSON-CLOB vector format.
- **"Change Fusion integration"** → remember `MAKE_REQUEST` is a function returning the body and that the status code comes from `APEX_WEB_SERVICE.GET_STATUS_CODE`. Do not reintroduce the old signature.
- **"Add tests"** → prefer extending `provisioning/tests/test_config.py` or adding sibling `test_*.py` files under `provisioning/tests/`. Target deployment-script logic (AST scans, env-var overrides, idempotent DDL parsing) rather than live DB calls.
- **"Clean up the repo"** → do not touch `oci-python-sdk/`. Do not bulk-reformat SQL. Do not delete the `*.md` marketing/report files without checking with the user; they are project deliverables.
