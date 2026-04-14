# Atlas on OCI — Sovereign AI Middleware for Oracle Fusion

Atlas is a simplified, AI-driven interface over **Oracle Fusion** built on
**Oracle Cloud Infrastructure** in the Kingdom of Saudi Arabia. It pairs
an **Oracle APEX** front-end with an OCI-native RAG pipeline and a
lightweight PL/SQL cache (`ATLAS_*`) to give enterprise users a
natural-language command bar over their Fusion tenant — without
touching the Fusion database.

> **Sovereign Context Middleware — Patent SA 1020259266.**
> Atlas is more than a front-end: it is the *Sovereign Oversight
> Layer* that sits between every AI agent and Oracle Fusion, keeps
> every byte of personal data inside `me-riyadh-1`, and refuses any
> request that cannot justify its own intent under PDPL, NCA-ECC and
> ZATCA.

---

## 1. Project structure

```
Atlas-SA/
├── README.md                       This file
├── LICENSE                         MIT
├── CLAUDE.md                       AI-assistant guidance
├── docs/                           Design & implementation docs
│   ├── API_SPEC.md                 ** Atlas Sovereign Oversight API **
│   ├── oci_architecture.md
│   ├── database_schema.md
│   ├── apex_application.md
│   ├── ai_rag_implementation.md
│   └── implementation_guide.md
├── provisioning/                   Deploy scripts (Python + SQL)
│   ├── provision_oci.sh
│   ├── schema_ddl.sql
│   ├── atlas_*.sql                 PL/SQL packages (RAG, vector, NL→SQL, …)
│   ├── deploy_*.py
│   └── tests/                      Config-drift + SQL invariant tests
├── apex/                           APEX component definitions
│   ├── pages/
│   └── rest_data_sources/
├── src/                            ** Sovereign Oversight PoC (Python) **
│   ├── rules_engine/
│   │   ├── pdpl_rules.py           PDPL PII classification & redaction
│   │   ├── nca_ecc_validator.py    NCA-ECC classification + cross-border
│   │   ├── intent_monitor.py       Intent Oversight / Shadow Auditor
│   │   └── engine.py               Aggregated "run everything" entry point
│   ├── dashboard/
│   │   └── mockup_api.py           Trust Dashboard JSON API (stdlib HTTP)
│   ├── demo/
│   │   └── cli.py                  Interactive CLI demo
│   └── tests/                      Unit tests for rules engine + CLI
└── oci-python-sdk/                 Vendored Oracle OCI SDK (read-only)
```

## 2. The Sovereign Context Middleware (PoC)

The `src/` tree is a **zero-touch Python PoC** of the Atlas Sovereign
Oversight Layer. It runs on a developer laptop or inside an OCI
Function; it never talks to Fusion directly and needs no database.
Its job is to prove three things in front of a board of directors:

1. **Every request is intercepted.** The rules engine is called on
   every `POST /intercept` before the middleware forwards anything to
   Oracle Fusion.
2. **Intent is audited, not just access.** The *Intent Oversight*
   pack (the "Shadow Auditor") compares the declared intent of the AI
   agent with the fields it is actually asking for, and blocks hidden
   deception — even when the agent is technically authorised.
3. **Compliance is automatic.** Three rule packs — PDPL, NCA-ECC and
   an Intent Oversight engine — run on every request and produce a
   single "ALLOW / REDACT / BLOCK" verdict plus a *sovereign proof*
   hash that the customer can show to a regulator.

### Architecture

```
   ┌────────────┐        ┌────────────────────────────────┐        ┌────────────────┐
   │ AI Agent   │ ────▶  │ Atlas Sovereign Oversight      │ ────▶  │ Oracle Fusion  │
   │ (LLM app)  │        │    /intercept                  │        │ (HCM / AP / …) │
   └────────────┘        │    ├─ PDPL rules               │        └────────────────┘
                         │    ├─ NCA-ECC validator        │
                         │    ├─ Intent Monitor           │
                         │    └─ Sovereign Proof (KMS)    │
                         └────────────────────────────────┘
                                         │
                                         ▼
                                ┌────────────────────┐
                                │ Trust Dashboard    │  (JSON API + APEX UI)
                                │ /dashboard         │
                                └────────────────────┘
```

* **No Fusion database writes.** The middleware is strictly a proxy;
  the `ATLAS_*` tables are a read-only cache synced by
  `fusion_sync_integration.sql`.
* **14-day deployment.** The middleware is modular — a new rule pack
  is one Python file plus one entry in `engine.DEFAULT_PACKS`.
* **Saudi-first.** The only region recognised as sovereign is
  `me-riyadh-1`. Cross-border routing is rejected with `HTTP 451` and
  logged to the dashboard.

### The three rule packs

| Pack | File | What it enforces |
|---|---|---|
| **PDPL** | `src/rules_engine/pdpl_rules.py` | Saudi National-ID / Iqama / IBAN / mobile detection and masking, purpose-limitation per intent, "fishing expedition" escalation. |
| **NCA-ECC** | `src/rules_engine/nca_ecc_validator.py` | ECC-1-5 classification ceiling, ECC-2-1 asset identity, ECC-2-3 human-on-behalf-of, ECC-4-1 cross-border block, ECC-5-2 third-party allow-list. |
| **Intent Oversight** | `src/rules_engine/intent_monitor.py` | Compares declared intent with observed fields, escalates excess PDPL fields to `BLOCK`, flags unknown intents. |

Full request/response schema for the three endpoints is in
[`docs/API_SPEC.md`](docs/API_SPEC.md).

---

## 3. Live demo in 60 seconds

All commands below run with **zero external dependencies** — only
Python's standard library and `pytest`.

### 3.1 Run the unit tests

```bash
pytest src/tests/ -v
```

Expected: 25 tests pass in well under a second.

### 3.2 Run a pre-baked scenario

Atlas ships four demo scenarios so that a board member can see each
rule pack in action:

| Scenario | Command | Expected verdict |
|---|---|---|
| Legitimate payroll summary | `python -m src.demo.cli scenario payroll` | `ALLOW` |
| **Hidden deception** (rogue agent) | `python -m src.demo.cli scenario deception` | `BLOCK` |
| Cross-border routing | `python -m src.demo.cli scenario cross-border` | `BLOCK` |
| ZATCA-compliant invoice | `python -m src.demo.cli scenario invoice` | `ALLOW` |

The "hidden deception" scenario is the one to run for the investor
pitch. It walks through this narrative:

> An AI agent declares its intent as `READ_PAYROLL_SUMMARY` — a
> harmless-sounding read — but the request body asks for
> `NationalId`, `IBAN`, `HomeAddress` and `BaseSalary`. A traditional
> RBAC proxy would let it through because the agent *is* cleared at
> `CONFIDENTIAL`. Atlas's Intent Monitor flags the gap between the
> declared intent and the observed fields, blocks the request, and
> records the deception in the trust dashboard with a sovereign proof
> the customer can show to the regulator.

Output looks like this:

```
================================================================
  Atlas Sovereign Oversight — Decision
================================================================
  Request ID       : req_demo_deception
  Agent            : agent://rogue-assistant/x
  Declared intent  : READ_PAYROLL_SUMMARY
  Observed intent  : PAYROLL_DISBURSE   (skepticism=0.3)
  Decision         : BLOCK
  Compliance score : 46/100
  Sovereign proof  : sha256:…
================================================================
  [PDPL]             score=43  decision=REDACT
     - PDPL.NATIONALID_PURPOSE_LIMIT
     - PDPL.IBAN_PURPOSE_LIMIT
     - PDPL.HOMEADDRESS_PURPOSE_LIMIT
  [NCA_ECC]          score=95  decision=ALLOW
  [INTENT_OVERSIGHT] score=0   decision=BLOCK
     - INTENT.DECEPTION_DETECTED: declared intent 'READ_PAYROLL_SUMMARY'
       does not justify personal-data fields
       ['HomeAddress', 'IBAN', 'NationalId'];
       observed intent looks more like 'PAYROLL_DISBURSE'
================================================================
```

### 3.3 Craft an ad-hoc request

```bash
python -m src.demo.cli intercept \
    --agent agent://hr-copilot/v2 \
    --intent READ_PAYROLL_SUMMARY \
    --fields PersonNumber,DisplayName,BaseSalary \
    --human user_14923
```

Exit codes:

* `0` — decision was `ALLOW` or `REDACT`
* `3` — decision was `BLOCK`
* `2` — bad arguments or unknown scenario

### 3.4 Interactive REPL

```bash
python -m src.demo.cli repl
```

Type a declared intent, then a comma-separated list of fields, and see
the middleware decide live. Useful for an interactive "try to break
it" session during the board pitch.

### 3.5 Trust Dashboard JSON API

Start the HTTP server (stdlib only, no Flask) in one terminal:

```bash
python -m src.dashboard.mockup_api --seed --port 8088
```

And in another terminal:

```bash
curl -s http://localhost:8088/dashboard | python -m json.tool
```

You'll get a JSON document with `Compliance_Score`,
`Blocked_Intent_Attacks`, `Active_Sovereign_Logs`, a per-decision
histogram, and the last 20 events — exactly what the APEX "Trust
Dashboard" page renders for the customer.

Every response carries an `X-Sovereign-Region: me-riyadh-1` header so
the UI can render a "Data stays inside the Kingdom" badge without
having to parse the body.

---

## 4. Deploying the full stack onto OCI

The PoC under `src/` is self-contained, but the full Atlas deployment
still uses the PL/SQL + APEX stack in `provisioning/`. Follow
[`docs/implementation_guide.md`](docs/implementation_guide.md) or run
the following end-to-end:

```bash
# 1. Provision OCI infrastructure (compartment, ATP, API Gateway, bucket).
cd provisioning
bash provision_oci.sh

# 2. Copy the template env file and fill in real values.
cp ../.env.example .env
vi .env

# 3. Deploy database + PL/SQL packages.
python deploy_schema.py              # ATLAS_* tables, indexes, sequences
python deploy_fusion_integration.py  # ATLAS_FUSION_SYNC_PKG
python deploy_rag_pipeline.py        # RAG / vector / NL→SQL packages
python setup_apex.py                 # APEX workspace + Atlas application
python security_verification.py      # Security mandate checks
```

All the Python scripts share a single `Config` class
(`provisioning/config.py`) and support both wallet (mTLS) and
walletless TLS connections to ATP. See `CLAUDE.md` for the full list
of environment variables.

---

## 5. Documentation map

| Document | Covers |
|---|---|
| [`docs/API_SPEC.md`](docs/API_SPEC.md) | **Atlas Sovereign Oversight API** — endpoints, headers, error model, compliance mapping. |
| [`docs/oci_architecture.md`](docs/oci_architecture.md) | OCI infrastructure design. |
| [`docs/database_schema.md`](docs/database_schema.md) | `ATLAS_*` schema description + ERD. |
| [`docs/apex_application.md`](docs/apex_application.md) | APEX app structure. |
| [`docs/apex_ui_specification.md`](docs/apex_ui_specification.md) | UI spec. |
| [`docs/ai_rag_implementation.md`](docs/ai_rag_implementation.md) | RAG pipeline design. |
| [`docs/fusion_activation_guide.md`](docs/fusion_activation_guide.md) | Fusion REST activation. |
| [`docs/implementation_guide.md`](docs/implementation_guide.md) | Step-by-step deploy instructions. |
| [`docs/next_steps_roadmap.md`](docs/next_steps_roadmap.md) | Roadmap. |
| [`TEST_COVERAGE_ANALYSIS.md`](TEST_COVERAGE_ANALYSIS.md) | Audit of existing test coverage. |

---

## 6. License

MIT — see [`LICENSE`](LICENSE). The vendored `oci-python-sdk/` tree is
redistributed under its own upstream license.
