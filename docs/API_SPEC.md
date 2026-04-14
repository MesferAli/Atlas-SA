# Atlas Sovereign Oversight API Specification

> **Atlas Sovereign Context Middleware** — Patent SA 1020259266
>
> This document is the canonical API specification for the Atlas PoC
> ("Sovereign Oversight Layer"). It defines the three endpoints that sit
> between an AI agent and Oracle Fusion, and the compliance headers that
> every request must carry to satisfy Saudi regulatory requirements.

---

## 1. Design goals

Atlas is a **zero-touch middleware**: it does not modify Oracle Fusion, it
does not require a new database schema on the Fusion side, and it can be
deployed in 14 days onto Oracle Cloud Infrastructure inside the Saudi
`me-riyadh-1` region. Every request handled by the middleware is:

1. **Intercepted** before it reaches Fusion (`/intercept`).
2. **Audited** against a declared "intent" and compared with the data
   actually requested (`/audit`).
3. **Compliance-checked** against PDPL, ZATCA, and NCA-ECC rule packs
   (`/compliance-check`).

Every response is tagged with a **Sovereignty Proof** so that customers
(and regulators) can prove that the data never left the Kingdom.

---

## 2. Base URL

```
https://atlas.{customer}.me-riyadh-1.oci.customer-oci.com/v1
```

All traffic terminates inside the OCI Saudi Arabia (Riyadh) region. Cross-
region routing is explicitly rejected by the middleware (see
`nca_ecc_validator.py`).

---

## 3. Required headers

Every request MUST carry the following headers. The middleware rejects
any request that is missing a required header with `HTTP 428 Precondition
Required`.

| Header | Example | Purpose |
|---|---|---|
| `X-Sovereign-Region` | `me-riyadh-1` | Declares the sovereign region the request is bound to. Any value other than `me-riyadh-1` is rejected. |
| `X-Agent-Id` | `agent://hr-copilot/v2` | Stable identifier of the calling AI agent. Used for audit trails. |
| `X-Agent-Intent` | `READ_PAYROLL_SUMMARY` | Short machine-readable declaration of *why* the agent is calling. Compared with the actual fields requested by `intent_monitor.py`. |
| `X-Classification` | `CONFIDENTIAL` | Highest data classification the caller expects to handle (`PUBLIC`, `INTERNAL`, `CONFIDENTIAL`). |
| `X-Request-Id` | `req_01HTX…` | Idempotency / correlation id. Echoed back on every response. |
| `Authorization` | `Bearer …` | OAuth2 token issued by the tenant's IdP (NCA-ECC mandates MFA-backed tokens). |

On every response the middleware adds:

| Response header | Meaning |
|---|---|
| `X-Sovereign-Proof` | SHA-256 of `region + request-id + timestamp`, signed with the tenant's KMS key. Used to prove the request was handled inside the Kingdom. |
| `X-Atlas-Decision` | One of `ALLOW`, `REDACT`, `BLOCK`. |
| `X-Compliance-Score` | Integer 0–100, the score produced by the rules engine. |

---

## 4. Endpoints

### 4.1 `POST /intercept`

Intercepts an outbound Fusion REST call initiated by an AI agent. The
middleware runs the request through the PDPL, NCA-ECC and intent rules
before letting it through.

#### Request body

```json
{
  "target": {
    "system": "ORACLE_FUSION",
    "path": "/hcmRestApi/resources/11.13.18.05/workers",
    "method": "GET",
    "query": { "q": "PersonNumber=955210" }
  },
  "declared_intent": "READ_PAYROLL_SUMMARY",
  "fields_requested": [
    "PersonNumber",
    "DisplayName",
    "NationalId",
    "BaseSalary",
    "IBAN"
  ],
  "actor": {
    "agent_id": "agent://hr-copilot/v2",
    "human_on_behalf_of": "user_14923",
    "data_classification": "CONFIDENTIAL"
  }
}
```

#### Response — allow

```json
{
  "decision": "ALLOW",
  "compliance_score": 97,
  "sovereign_proof": "sha256:5c3f…",
  "rules_fired": [],
  "forwarded_to_fusion": true
}
```

#### Response — redact (PDPL PII mask)

```json
{
  "decision": "REDACT",
  "compliance_score": 82,
  "sovereign_proof": "sha256:71ae…",
  "rules_fired": [
    { "rule": "PDPL.SA_ID_REDACT", "field": "NationalId", "action": "MASK_LAST_4" },
    { "rule": "PDPL.SA_IBAN_REDACT", "field": "IBAN", "action": "MASK_MIDDLE" }
  ],
  "forwarded_to_fusion": true
}
```

#### Response — block (intent mismatch)

```json
{
  "decision": "BLOCK",
  "compliance_score": 14,
  "sovereign_proof": "sha256:aa02…",
  "rules_fired": [
    {
      "rule": "INTENT.DECEPTION_DETECTED",
      "detail": "declared intent READ_PAYROLL_SUMMARY does not justify access to IBAN, NationalId"
    }
  ],
  "forwarded_to_fusion": false
}
```

### 4.2 `POST /audit`

Returns an explainable audit trail for a single request id. Designed for
"Trust Dashboard" drill-downs and for regulator exports.

#### Request

```json
{ "request_id": "req_01HTX…" }
```

#### Response

```json
{
  "request_id": "req_01HTX…",
  "timestamp": "2026-04-14T09:11:33Z",
  "agent_id": "agent://hr-copilot/v2",
  "declared_intent": "READ_PAYROLL_SUMMARY",
  "observed_intent": "EXFILTRATE_BANKING_INFO",
  "skepticism_score": 0.91,
  "decision": "BLOCK",
  "rules_fired": [ /* … */ ],
  "sovereign_proof": "sha256:aa02…"
}
```

The `observed_intent` field is produced by `intent_monitor.py`: it is the
intent that best explains the *fields actually requested*, and the
skepticism score is `1 - cosine(declared, observed)`.

### 4.3 `POST /compliance-check`

Runs the rule packs in read-only mode without forwarding the underlying
request to Fusion. Used by dashboards, CI pipelines, and regulator drills.

#### Request

```json
{
  "rule_packs": ["PDPL", "ZATCA", "NCA_ECC"],
  "payload": {
    "fields_requested": ["NationalId", "IBAN", "VATNumber"],
    "declared_intent": "GENERATE_INVOICE",
    "data_classification": "CONFIDENTIAL"
  }
}
```

#### Response

```json
{
  "compliance_score": 74,
  "results": [
    { "pack": "PDPL", "score": 60, "fired": ["SA_ID_REDACT", "SA_IBAN_REDACT"] },
    { "pack": "ZATCA", "score": 95, "fired": [] },
    { "pack": "NCA_ECC", "score": 88, "fired": ["CLASSIFICATION_CEILING"] }
  ]
}
```

---

## 5. Error model

| HTTP | Code | Meaning |
|---|---|---|
| `400` | `ATLAS_MALFORMED` | Body failed schema validation. |
| `401` | `ATLAS_UNAUTHENTICATED` | Missing or invalid bearer token. |
| `403` | `ATLAS_BLOCKED` | Rules engine returned `BLOCK`. |
| `409` | `ATLAS_INTENT_MISMATCH` | Declared intent and observed intent diverged above threshold. |
| `428` | `ATLAS_MISSING_SOVEREIGN_HEADER` | One of the mandatory `X-Sovereign-*` headers is absent. |
| `451` | `ATLAS_CROSS_BORDER` | Request would have routed data outside `me-riyadh-1`. |
| `500` | `ATLAS_INTERNAL` | Unhandled server error (never contains payload data). |

Error bodies always follow RFC 7807:

```json
{
  "type": "https://atlas.sa/errors/ATLAS_BLOCKED",
  "title": "Request blocked by PDPL rule SA_ID_EXFILTRATION",
  "status": 403,
  "request_id": "req_01HTX…",
  "sovereign_proof": "sha256:aa02…"
}
```

---

## 6. Compliance mapping

| Rule pack | Source of truth | Enforced by |
|---|---|---|
| **PDPL** | Saudi Personal Data Protection Law (Royal Decree M/19) | `src/rules_engine/pdpl_rules.py` |
| **NCA-ECC** | NCA Essential Cybersecurity Controls (ECC-1:2018) | `src/rules_engine/nca_ecc_validator.py` |
| **ZATCA** | ZATCA E-Invoicing Phase 2 technical rules | `src/rules_engine/zatca_rules.py` *(stub — grows in Sprint 2)* |
| **Intent Oversight** | XCircle Alignment Architecture (internal) | `src/rules_engine/intent_monitor.py` |

All four packs are hot-reloadable: the middleware reads them at startup
and on `SIGHUP`, so a compliance officer can roll out a new rule without
redeploying Atlas itself.
