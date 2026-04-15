"""PDPL rule pack — Personal Data Protection Law (Kingdom of Saudi Arabia).

The Personal Data Protection Law (Royal Decree M/19, 1443H) regulates
how personal data of Saudi residents may be collected, processed and
transferred. Atlas enforces the subset of the law that is deterministic
enough to be checked at request time:

1. **PII identification.** Any field whose *value* matches a Saudi
   National ID, an Iqama number, a Saudi IBAN, or a Saudi mobile number
   is classified as personal data.
2. **Field-name identification.** Any field whose *name* is on the
   ``SENSITIVE_FIELD_NAMES`` list (``NationalId``, ``Iqama``, ``IBAN``,
   ``Salary``, ``HomeAddress``…) is classified as personal data even if
   the value itself is empty or masked.
3. **Purpose limitation.** Personal data may only be returned if the
   declared intent is in ``ALLOWED_INTENTS_PER_FIELD``. If it is not,
   the field is automatically redacted (``REDACT`` decision) so that the
   underlying request can still be served with the remaining fields.
4. **Data minimisation.** If *more than half* the requested fields are
   personal data, the score is penalised — the rule pack treats that
   as a "fishing expedition" even if each individual field is allowed.

The module is intentionally standalone: no regex libraries, no external
dependencies, just deterministic rules that can be reviewed by a legal
team without a Python runtime.
"""

from __future__ import annotations

import re

from . import Decision, Request, RuleResult

# ---------------------------------------------------------------------------
# Regular expressions
# ---------------------------------------------------------------------------

# Saudi National ID / Iqama: exactly 10 digits. National IDs start with 1,
# Iqamas start with 2. We do not validate the check digit here — the rule
# pack is conservative and flags every 10-digit token.
_SA_ID_RE = re.compile(r"(?<!\d)[12]\d{9}(?!\d)")

# Saudi IBAN: "SA" + 2 check digits + 20 BBAN digits = 24 chars total.
_SA_IBAN_RE = re.compile(r"(?<![A-Z0-9])SA\d{22}(?![A-Z0-9])", re.IGNORECASE)

# Saudi mobile number: +9665XXXXXXXX or 9665XXXXXXXX or 05XXXXXXXX.
_SA_MOBILE_RE = re.compile(
    r"(?<!\d)(?:\+?966|0)5\d{8}(?!\d)",
)

# ---------------------------------------------------------------------------
# Field-level metadata
# ---------------------------------------------------------------------------

#: Field names whose mere presence counts as "personal data" under PDPL.
SENSITIVE_FIELD_NAMES: frozenset[str] = frozenset(
    {
        "NationalId",
        "National_Id",
        "Iqama",
        "IqamaNumber",
        "IBAN",
        "BankAccount",
        "BankAccountNumber",
        "HomeAddress",
        "PersonalEmail",
        "PersonalPhone",
        "MobileNumber",
        "DateOfBirth",
        "BaseSalary",
        "Salary",
        "PayRate",
        "MedicalRecord",
        "Passport",
        "PassportNumber",
    }
)

#: Which declared intents are allowed to see which sensitive fields.
#: Any field not covered by the active intent is redacted. This is the
#: "purpose limitation" article of the PDPL expressed as a lookup table.
ALLOWED_INTENTS_PER_FIELD: dict[str, frozenset[str]] = {
    "NationalId": frozenset({"KYC_VERIFY", "PAYROLL_DISBURSE", "REGULATOR_EXPORT"}),
    "National_Id": frozenset({"KYC_VERIFY", "PAYROLL_DISBURSE", "REGULATOR_EXPORT"}),
    "Iqama": frozenset({"KYC_VERIFY", "VISA_RENEWAL", "REGULATOR_EXPORT"}),
    "IqamaNumber": frozenset({"KYC_VERIFY", "VISA_RENEWAL", "REGULATOR_EXPORT"}),
    "IBAN": frozenset({"PAYROLL_DISBURSE", "AP_PAYMENT_RUN"}),
    "BankAccount": frozenset({"PAYROLL_DISBURSE", "AP_PAYMENT_RUN"}),
    "BankAccountNumber": frozenset({"PAYROLL_DISBURSE", "AP_PAYMENT_RUN"}),
    "BaseSalary": frozenset(
        {"PAYROLL_DISBURSE", "COMPENSATION_REVIEW", "READ_PAYROLL_SUMMARY"}
    ),
    "Salary": frozenset(
        {"PAYROLL_DISBURSE", "COMPENSATION_REVIEW", "READ_PAYROLL_SUMMARY"}
    ),
    "PayRate": frozenset(
        {"PAYROLL_DISBURSE", "COMPENSATION_REVIEW", "READ_PAYROLL_SUMMARY"}
    ),
    "HomeAddress": frozenset({"DELIVERY", "REGULATOR_EXPORT"}),
    "PersonalEmail": frozenset({"ACCOUNT_RECOVERY", "DIRECT_COMMS"}),
    "PersonalPhone": frozenset({"ACCOUNT_RECOVERY", "DIRECT_COMMS"}),
    "MobileNumber": frozenset({"ACCOUNT_RECOVERY", "DIRECT_COMMS"}),
    "DateOfBirth": frozenset({"KYC_VERIFY", "PAYROLL_DISBURSE"}),
    "Passport": frozenset({"KYC_VERIFY", "VISA_RENEWAL", "REGULATOR_EXPORT"}),
    "PassportNumber": frozenset({"KYC_VERIFY", "VISA_RENEWAL", "REGULATOR_EXPORT"}),
    "MedicalRecord": frozenset({"MEDICAL_CARE"}),
}


# ---------------------------------------------------------------------------
# Value-level detection
# ---------------------------------------------------------------------------


def detect_pii(value: str) -> list[str]:
    """Return a list of PII categories detected in ``value``.

    Examples
    --------
    >>> detect_pii("employee id 1098765432")
    ['SA_ID']
    >>> detect_pii("IBAN SA0380000000608010167519")
    ['SA_IBAN']
    >>> detect_pii("please call +966512345678")
    ['SA_MOBILE']
    >>> detect_pii("no personal data here")
    []
    """

    hits: list[str] = []
    if not isinstance(value, str):
        return hits
    if _SA_ID_RE.search(value):
        hits.append("SA_ID")
    if _SA_IBAN_RE.search(value):
        hits.append("SA_IBAN")
    if _SA_MOBILE_RE.search(value):
        hits.append("SA_MOBILE")
    return hits


def mask_sa_id(raw: str) -> str:
    """Mask a Saudi National ID, keeping only the last four digits."""

    def _repl(match: re.Match[str]) -> str:
        digits = match.group(0)
        return "*" * 6 + digits[-4:]

    return _SA_ID_RE.sub(_repl, raw)


def mask_sa_iban(raw: str) -> str:
    """Mask a Saudi IBAN, keeping only the country code and last four digits."""

    def _repl(match: re.Match[str]) -> str:
        iban = match.group(0)
        return iban[:4] + "*" * (len(iban) - 8) + iban[-4:]

    return _SA_IBAN_RE.sub(_repl, raw)


def mask_sa_mobile(raw: str) -> str:
    """Mask a Saudi mobile number, keeping only the last three digits."""

    def _repl(match: re.Match[str]) -> str:
        number = match.group(0)
        return "*" * (len(number) - 3) + number[-3:]

    return _SA_MOBILE_RE.sub(_repl, raw)


def redact(value: str) -> str:
    """Apply every mask to ``value`` in sequence."""

    if not isinstance(value, str):
        return value
    out = mask_sa_id(value)
    out = mask_sa_iban(out)
    out = mask_sa_mobile(out)
    return out


# ---------------------------------------------------------------------------
# Rule pack entry point
# ---------------------------------------------------------------------------

#: Name of the rule pack, used in audit trails.
PACK = "PDPL"


def evaluate(request: Request) -> RuleResult:
    """Run the PDPL rule pack against a :class:`Request`.

    The function never raises: even malformed input is mapped to a
    deterministic :class:`RuleResult`. Returning an explicit
    ``BLOCK`` / ``REDACT`` object makes the audit trail reviewable by a
    compliance officer without needing to read Python tracebacks.
    """

    fired: list[dict[str, object]] = []
    redactions: dict[str, str] = {}

    sensitive_fields = [
        f for f in request.field_set() if f in SENSITIVE_FIELD_NAMES
    ]

    # Purpose limitation: every sensitive field whose intent allow-list
    # does not contain ``declared_intent`` gets redacted.
    for field_name in sensitive_fields:
        allowed = ALLOWED_INTENTS_PER_FIELD.get(field_name, frozenset())
        if request.declared_intent not in allowed:
            rule_name = f"PDPL.{field_name.upper()}_PURPOSE_LIMIT"
            fired.append(
                {
                    "rule": rule_name,
                    "field": field_name,
                    "action": "REDACT",
                    "allowed_intents": sorted(allowed),
                    "declared_intent": request.declared_intent,
                }
            )
            redactions[field_name] = "REDACTED_BY_PDPL"

    # Value-level detection inside free-form payload values.
    for key, value in request.payload.items():
        if isinstance(value, str):
            for category in detect_pii(value):
                rule_name = f"PDPL.{category}_VALUE_DETECTED"
                fired.append(
                    {
                        "rule": rule_name,
                        "field": key,
                        "action": "MASK",
                        "category": category,
                    }
                )
                redactions[key] = redact(value)

    # Data minimisation score penalty.
    total_fields = len(request.field_set()) or 1
    sensitive_ratio = len(sensitive_fields) / total_fields
    minimisation_penalty = int(round(sensitive_ratio * 40))  # up to -40

    # Score: start at 100, subtract 10 per redaction, subtract the
    # minimisation penalty, floor at 0.
    score = 100 - 10 * len(redactions) - minimisation_penalty
    score = max(score, 0)

    if redactions:
        decision = Decision.REDACT
    else:
        decision = Decision.ALLOW

    # A full-on fishing expedition (every field is sensitive, no intent
    # covers them) is escalated to BLOCK so the middleware refuses to
    # serve it at all.
    if sensitive_ratio == 1.0 and len(redactions) == len(sensitive_fields):
        decision = Decision.BLOCK
        fired.append(
            {
                "rule": "PDPL.FISHING_EXPEDITION",
                "detail": "every requested field is personal data and no "
                "declared intent covers any of them",
            }
        )

    return RuleResult(
        pack=PACK,
        score=score,
        decision=decision,
        fired=fired,
        redactions=redactions,
        notes=(
            f"{len(sensitive_fields)} sensitive fields, "
            f"{len(redactions)} redactions, ratio={sensitive_ratio:.2f}"
        ),
    )


__all__ = [
    "PACK",
    "SENSITIVE_FIELD_NAMES",
    "ALLOWED_INTENTS_PER_FIELD",
    "detect_pii",
    "mask_sa_id",
    "mask_sa_iban",
    "mask_sa_mobile",
    "redact",
    "evaluate",
]
