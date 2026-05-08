# Oracle E-Business Suite (EBS) Integration Guide

Atlas was originally designed to ingest from **Oracle Fusion** REST APIs.
This guide documents how to point the same Atlas cache at an **Oracle
E-Business Suite (R12)** source instead.

The architecture above the sync layer (ATP cache, RAG pipeline, APEX,
OCI GenAI) is unchanged — only the `ATLAS_FUSION_SYNC_PKG` step is
swapped for `ATLAS_EBS_SYNC_PKG`.

---

## 1. Integration modes

| Mode | When to pick it | Notes |
|---|---|---|
| **DBLINK** *(default)* | EBS is reachable on the network (e.g. via FastConnect or VPN to on-prem). | Fastest, simplest. Atlas reads directly from the APPS schema. |
| **ISG** *(Integrated SOA Gateway REST)* | Network policy disallows DB-level connectivity, but HTTPS to the EBS application tier is fine. | Slower, requires the relevant ISG services to be deployed in EBS. |

Switch via `EBS_INTEGRATION_MODE` in `.env` (or the `EBS_INTEGRATION_MODE`
config getter).

---

## 2. Prerequisites

1. **EBS instance** at R12.1 or R12.2, with the APPS schema accessible to
   a read-only DB user (recommended: clone APPS to a dedicated reporting
   user with `SELECT` grants on the views below).
2. **Network path** from ATP to EBS:
   - DBLINK mode: TCPS/TCP from ATP → EBS DB tier.
   - ISG mode: HTTPS from ATP → EBS apps tier.
3. **Database link** in ATP whose name matches `EBS_DB_LINK`
   (default `EBS_PROD`):

   ```sql
   CREATE DATABASE LINK EBS_PROD
     CONNECT TO atlas_reader IDENTIFIED BY "<password>"
     USING '(DESCRIPTION=(ADDRESS=(PROTOCOL=TCP)(HOST=ebs-db.internal)(PORT=1521))(CONNECT_DATA=(SERVICE_NAME=PROD)))';
   ```

   Atlas does **not** create this link itself — by design, since the
   credential lives only in the DB and never in the repo.

---

## 3. Configuration

Add the following to `.env` (see `.env.example` for the full template):

```bash
ATLAS_SOURCE_SYSTEM="EBS"        # Tells the orchestrator which sync to run
EBS_INTEGRATION_MODE="DBLINK"    # DBLINK | ISG
EBS_DB_LINK="EBS_PROD"           # Must match the link name created above
EBS_APPS_SCHEMA="APPS"           # Almost always APPS in R12
EBS_BUSINESS_GROUP_ID="0"        # 0 = no filter; otherwise the per_all_people_f.business_group_id you want
EBS_LEDGER_ID="0"                # 0 = all ledgers
EBS_ORG_ID="0"                   # 0 = all operating units
```

These flow into the database via `ATLAS_CONFIG_PKG`. To change them at
runtime without redeploying, call:

```sql
EXEC ATLAS_CONFIG_PKG.SET_CONFIG_VALUE('ATLAS_SOURCE_SYSTEM', 'EBS');
EXEC ATLAS_CONFIG_PKG.SET_CONFIG_VALUE('EBS_DB_LINK',         'EBS_TEST');
```

---

## 4. EBS source objects

`ATLAS_EBS_SYNC_PKG` reads the following EBS views/tables and merges
them into the corresponding `ATLAS_*` tables.

| Atlas table | EBS source | Notes |
|---|---|---|
| `ATLAS_LOCATIONS` | `HR_LOCATIONS_ALL` | `LOCATION_CODE` → `LOCATION_NAME`. |
| `ATLAS_DEPARTMENTS` | `HR_ALL_ORGANIZATION_UNITS` + `_TL` | Filters by `BUSINESS_GROUP_ID` if set. |
| `ATLAS_EMPLOYEES` | `PER_ALL_PEOPLE_F` + `PER_ALL_ASSIGNMENTS_F` + `PER_JOBS` | Date-tracked; picks the row effective today and `PRIMARY_FLAG='Y'`. |
| `ATLAS_SUPPLIERS` | `AP_SUPPLIERS` | `END_DATE_ACTIVE IS NOT NULL` → `INACTIVE`. |
| `ATLAS_PURCHASE_ORDERS` | `PO_HEADERS_ALL` | Filtered by `ORG_ID` if set; `SEGMENT1` is the PO number. |
| `ATLAS_AP_INVOICES` | `AP_INVOICES_ALL` | `PAYMENT_STATUS_FLAG` mapped Y→`PAID`, P→`PARTIAL`, N→`UNPAID`. |
| `ATLAS_GL_BALANCES` | `GL_BALANCES` + `GL_CODE_COMBINATIONS` | Merges on `(LEDGER_ID, ACCOUNT_CODE, PERIOD_NAME, CURRENCY_CODE)`. |

The package never writes back to EBS — it is strictly a one-way pull.

---

## 5. Deployment

```bash
cd provisioning
python deploy_schema.py              # ATLAS_* tables (unchanged)
python deploy_fusion_integration.py  # Optional; safe to skip on EBS-only sites
python deploy_ebs_integration.py     # Installs ATLAS_EBS_SYNC_PKG + (disabled) job
python deploy_rag_pipeline.py        # RAG packages (unchanged)
python setup_apex.py                 # APEX app (unchanged)
```

The deploy script is idempotent. ORA-00955 / ORA-02262 / ORA-00942 are
treated as benign on re-runs, matching the convention in
`deploy_schema.py`.

---

## 6. Cutting over from Fusion to EBS

```sql
-- 1. Stop the Fusion sync.
EXEC DBMS_SCHEDULER.DISABLE('ATLAS_DAILY_FUSION_SYNC_JOB');

-- 2. Tell Atlas where to look.
EXEC ATLAS_CONFIG_PKG.SET_CONFIG_VALUE('ATLAS_SOURCE_SYSTEM', 'EBS');

-- 3. Backfill once on demand.
EXEC ATLAS_EBS_SYNC_PKG.SYNC_ALL_EBS_DATA;

-- 4. Enable the daily EBS sync.
EXEC DBMS_SCHEDULER.ENABLE('ATLAS_DAILY_EBS_SYNC_JOB');
```

`ATLAS_EBS_SYNC_PKG.SYNC_ALL_EBS_DATA` calls `ASSERT_EBS_SOURCE` first
and refuses to run when `ATLAS_SOURCE_SYSTEM` is not `EBS`. This is the
guardrail that prevents both jobs from firing on the same instance.

---

## 7. Verifying a sync

```sql
-- Per-entity success count from the audit log.
SELECT EVENT_TYPE, RESOURCE_TYPE, COUNT(*) AS RUNS, MAX(CREATED_DATE) AS LAST_RUN
FROM ATLAS_AUDIT_LOG
WHERE EVENT_TYPE LIKE 'EBS_%'
GROUP BY EVENT_TYPE, RESOURCE_TYPE
ORDER BY RESOURCE_TYPE;

-- Sanity check on a single table.
SELECT COUNT(*), MAX(LAST_SYNC_DATE) FROM ATLAS_EMPLOYEES;
```

---

## 8. Known limitations

1. **Date-tracked HR rows.** Atlas pulls the row effective on `SYSDATE`.
   Future-dated changes (terminations, transfers) are not visible until
   the day they take effect.
2. **GL balances grow without bound.** `ATLAS_GL_BALANCES` is keyed on
   `(LEDGER_ID, ACCOUNT_CODE, PERIOD_NAME, CURRENCY_CODE)`. There is no
   purge step yet — for large ledgers, schedule a periodic `DELETE` of
   closed periods older than your retention policy.
3. **ISG mode is stubbed.** The config keys exist but the REST client
   path is not implemented in this release. DBLINK is the supported mode.
4. **No PL/SQL tests.** The package was validated by deployment-script
   parsing and config drift, not by integration tests against a live
   EBS instance. See `TEST_COVERAGE_ANALYSIS.md`.
