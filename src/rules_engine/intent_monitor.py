"""Intent Oversight rule pack — the "Shadow Auditor".

The intent monitor is the piece of Atlas that corresponds most directly
to XCircle's **Alignment Architecture** work. Its job is not to check
whether a request is legal under PDPL or NCA-ECC (the other two packs
already do that); its job is to check whether the *declared intent* of
the AI agent actually justifies the fields it is asking for.

In alignment-research terminology, this is a basic defence against:

* **Hidden deception** — an agent says "I need a payroll summary" but
  pulls IBANs, passport numbers and salary history.
* **Sandbagging** — an agent declares a low-privilege intent to fly
  under the radar of simpler rule-based filters.
* **Goal misgeneralisation** — an agent's declared task is legitimate
  but it asks for wildly more context than the task requires.

Implementation
--------------
The module defines a small *intent catalogue*: for each known intent we
list the fields that a legitimate request "should" touch (``expected``)
and a larger list of fields that it "may" touch (``allowed``). The
monitor then computes three numbers:

* ``coverage`` — how much of the declared intent's expected fields the
  request actually asks for. Low coverage means the agent isn't really
  doing what it claims.
* ``excess`` — how many requested fields fall outside the ``allowed``
  set of the declared intent. High excess means the agent is asking
  for things the declared intent cannot justify.
* ``skepticism_score`` — ``excess / (excess + coverage + 1)`` in [0, 1].
  We also derive an ``observed_intent`` by picking the catalogue entry
  that best matches the fields actually requested (maximum Jaccard
  similarity over ``allowed``).

A declared intent that diverges from the observed intent above a
configurable threshold flips the decision to ``BLOCK`` and the audit
trail records both intents side-by-side, so a compliance officer can
see the deception plainly in the dashboard.
"""

from __future__ import annotations

from dataclasses import dataclass

from . import Decision, Request, RuleResult
from . import pdpl_rules

PACK = "INTENT_OVERSIGHT"

#: Skepticism above this score is treated as hidden deception.
BLOCK_THRESHOLD = 0.60

#: Skepticism above this score (but below ``BLOCK_THRESHOLD``) only
#: degrades the compliance score without blocking.
WARN_THRESHOLD = 0.30


@dataclass(frozen=True)
class IntentProfile:
    """A declarative profile of what an intent is allowed to touch."""

    name: str
    expected: frozenset[str]
    allowed: frozenset[str]
    description: str = ""


#: The intent catalogue. In production this is a table inside the ATLAS
#: schema, hot-reloaded on SIGHUP. For the PoC we hard-code a
#: representative set.
INTENT_CATALOGUE: dict[str, IntentProfile] = {
    "READ_PAYROLL_SUMMARY": IntentProfile(
        name="READ_PAYROLL_SUMMARY",
        expected=frozenset({"PersonNumber", "DisplayName", "BaseSalary"}),
        allowed=frozenset(
            {
                "PersonNumber",
                "DisplayName",
                "BaseSalary",
                "Department",
                "Grade",
                "Currency",
            }
        ),
        description="High-level payroll summary: who gets paid how much.",
    ),
    "PAYROLL_DISBURSE": IntentProfile(
        name="PAYROLL_DISBURSE",
        expected=frozenset({"PersonNumber", "BaseSalary", "IBAN"}),
        allowed=frozenset(
            {
                "PersonNumber",
                "DisplayName",
                "BaseSalary",
                "IBAN",
                "BankName",
                "Currency",
                "NationalId",
            }
        ),
        description="Actual salary run — requires banking details.",
    ),
    "KYC_VERIFY": IntentProfile(
        name="KYC_VERIFY",
        expected=frozenset({"NationalId", "DateOfBirth"}),
        allowed=frozenset(
            {
                "NationalId",
                "Iqama",
                "Passport",
                "DateOfBirth",
                "DisplayName",
                "Nationality",
            }
        ),
        description="Know-Your-Customer verification for an individual.",
    ),
    "READ_HEADCOUNT": IntentProfile(
        name="READ_HEADCOUNT",
        expected=frozenset({"Department", "PersonCount"}),
        allowed=frozenset(
            {
                "Department",
                "PersonCount",
                "Location",
                "Grade",
                "Role",
            }
        ),
        description="Aggregate headcount reporting, no personal data.",
    ),
    "GENERATE_INVOICE": IntentProfile(
        name="GENERATE_INVOICE",
        expected=frozenset({"InvoiceNumber", "CustomerName", "VATNumber"}),
        allowed=frozenset(
            {
                "InvoiceNumber",
                "CustomerName",
                "VATNumber",
                "InvoiceLines",
                "TotalAmount",
                "Currency",
                "IssueDate",
            }
        ),
        description="ZATCA-compliant e-invoice generation.",
    ),
    "AP_PAYMENT_RUN": IntentProfile(
        name="AP_PAYMENT_RUN",
        expected=frozenset({"SupplierId", "IBAN", "Amount"}),
        allowed=frozenset(
            {
                "SupplierId",
                "SupplierName",
                "IBAN",
                "Amount",
                "Currency",
                "InvoiceNumber",
            }
        ),
        description="Accounts-payable payment run to suppliers.",
    ),
    "REGULATOR_EXPORT": IntentProfile(
        name="REGULATOR_EXPORT",
        expected=frozenset({"ReportId", "PeriodStart", "PeriodEnd"}),
        allowed=frozenset(
            {
                "ReportId",
                "PeriodStart",
                "PeriodEnd",
                "NationalId",
                "Iqama",
                "Passport",
                "BaseSalary",
                "IBAN",
            }
        ),
        description="Exports to ZATCA / GOSI / MHRSD under legal mandate.",
    ),
}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 1.0
    union = a | b
    if not union:
        return 0.0
    return len(a & b) / len(union)


def _best_observed_intent(fields: set[str]) -> tuple[str, float]:
    """Return the catalogue entry that best explains ``fields``."""

    best_name = "UNKNOWN"
    best_score = 0.0
    for profile in INTENT_CATALOGUE.values():
        score = _jaccard(fields, set(profile.allowed))
        if score > best_score:
            best_score = score
            best_name = profile.name
    return best_name, best_score


def analyse(request: Request) -> dict[str, object]:
    """Return the raw numbers used by :func:`evaluate`.

    Exposed as a public function so that dashboards and audit reports
    can display the diagnostic fields without re-running a full rule
    evaluation.
    """

    fields = request.field_set()
    profile = INTENT_CATALOGUE.get(request.declared_intent)

    if profile is None:
        # Declared intent is not even in the catalogue — maximum
        # skepticism.
        observed_name, observed_score = _best_observed_intent(fields)
        return {
            "known_intent": False,
            "declared_intent": request.declared_intent,
            "observed_intent": observed_name,
            "observed_match": observed_score,
            "coverage": 0.0,
            "excess": float(len(fields)),
            "skepticism_score": 1.0,
            "excess_fields": sorted(fields),
            "missing_expected": [],
        }

    expected_hits = fields & profile.expected
    excess_fields = fields - profile.allowed
    coverage = (
        len(expected_hits) / len(profile.expected) if profile.expected else 1.0
    )
    excess = len(excess_fields)

    # Normalise excess to [0, 1] against the total number of requested
    # fields so that "1 extra out of 10" scores very differently from
    # "5 extra out of 6".
    excess_ratio = excess / max(len(fields), 1)
    skepticism = (1 - coverage) * 0.4 + excess_ratio * 0.6

    observed_name, observed_score = _best_observed_intent(fields)

    return {
        "known_intent": True,
        "declared_intent": profile.name,
        "observed_intent": observed_name,
        "observed_match": observed_score,
        "coverage": coverage,
        "excess": float(excess),
        "skepticism_score": round(skepticism, 3),
        "excess_fields": sorted(excess_fields),
        "missing_expected": sorted(profile.expected - fields),
    }


def evaluate(request: Request) -> RuleResult:
    """Run the intent-oversight pack against a :class:`Request`."""

    diag = analyse(request)
    skepticism = float(diag["skepticism_score"])
    score = int(round(max(0.0, 1.0 - skepticism) * 100))

    fired: list[dict[str, object]] = []
    decision = Decision.ALLOW
    # Baseline; may be forced to 0 below if we detect hidden deception.
    forced_score: int | None = None

    excess_fields = set(diag.get("excess_fields") or [])
    pdpl_excess = excess_fields & pdpl_rules.SENSITIVE_FIELD_NAMES

    if not diag["known_intent"]:
        fired.append(
            {
                "rule": "INTENT.UNKNOWN_INTENT",
                "detail": f"declared intent {request.declared_intent!r} is not in the catalogue",
                "observed_intent": diag["observed_intent"],
            }
        )
        decision = Decision.BLOCK
        forced_score = 0
    elif pdpl_excess:
        # The excess set contains personal data the declared intent
        # cannot justify. This is the textbook "hidden deception"
        # pattern and is always escalated to BLOCK, no matter what
        # the numerical skepticism score says.
        fired.append(
            {
                "rule": "INTENT.DECEPTION_DETECTED",
                "detail": (
                    f"declared intent {diag['declared_intent']!r} does not "
                    f"justify personal-data fields {sorted(pdpl_excess)}; "
                    f"observed intent looks more like {diag['observed_intent']!r}"
                ),
                "skepticism_score": skepticism,
                "excess_pdpl_fields": sorted(pdpl_excess),
            }
        )
        decision = Decision.BLOCK
        forced_score = 0
    elif skepticism >= BLOCK_THRESHOLD:
        fired.append(
            {
                "rule": "INTENT.DECEPTION_DETECTED",
                "detail": (
                    f"declared intent {diag['declared_intent']!r} does not "
                    f"justify fields {diag['excess_fields']}; observed "
                    f"intent looks more like {diag['observed_intent']!r}"
                ),
                "skepticism_score": skepticism,
            }
        )
        decision = Decision.BLOCK
        forced_score = 0
    elif skepticism >= WARN_THRESHOLD:
        fired.append(
            {
                "rule": "INTENT.EXCESS_CONTEXT",
                "detail": (
                    f"declared intent {diag['declared_intent']!r} asks for "
                    f"{diag['excess_fields']} outside its allowed set"
                ),
                "skepticism_score": skepticism,
            }
        )
        decision = Decision.REDACT

    if forced_score is not None:
        score = forced_score

    return RuleResult(
        pack=PACK,
        score=score,
        decision=decision,
        fired=fired,
        notes=(
            f"declared={diag['declared_intent']}, "
            f"observed={diag['observed_intent']}, "
            f"skepticism={skepticism:.2f}"
        ),
    )


__all__ = [
    "PACK",
    "BLOCK_THRESHOLD",
    "WARN_THRESHOLD",
    "IntentProfile",
    "INTENT_CATALOGUE",
    "analyse",
    "evaluate",
]
