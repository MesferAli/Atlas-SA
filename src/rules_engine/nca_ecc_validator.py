"""NCA-ECC rule pack — Essential Cybersecurity Controls.

Implements a subset of the Saudi **National Cybersecurity Authority
Essential Cybersecurity Controls** (ECC-1:2018) that can be enforced at
request-interception time without talking to any external system.

The controls implemented here correspond to:

* **ECC-1-5** *Data and Information Protection* — data classification
  must be explicit, and a caller may not request data above their own
  cleared ceiling.
* **ECC-2-1** *Asset Management* — every request must identify the
  target system and the calling agent.
* **ECC-2-3** *Identity and Access Management* — human-on-behalf-of is
  mandatory for CONFIDENTIAL data.
* **ECC-4-1** *Cybersecurity Resilience* — cross-border routing is
  forbidden. The middleware only operates inside ``me-riyadh-1``.
* **ECC-5-2** *Third-Party Cybersecurity* — only whitelisted target
  systems are allowed.

Every violation either drops the compliance score or (for hard
boundary breaches) flips the decision to ``BLOCK``.
"""

from __future__ import annotations

from . import Decision, Request, RuleResult

PACK = "NCA_ECC"

#: The only OCI region the PoC recognises as "sovereign".
SOVEREIGN_REGION = "me-riyadh-1"

#: Classification hierarchy (low → high). A caller cleared for
#: ``INTERNAL`` may not ask for ``CONFIDENTIAL``.
CLASSIFICATION_ORDER: dict[str, int] = {
    "PUBLIC": 0,
    "INTERNAL": 1,
    "CONFIDENTIAL": 2,
    "RESTRICTED": 3,
}

#: Target systems that Atlas is allowed to proxy to. Anything else is
#: considered a third-party risk (ECC-5-2).
ALLOWED_TARGET_SYSTEMS: frozenset[str] = frozenset(
    {"ORACLE_FUSION", "ATLAS_CACHE", "ATLAS_RAG"}
)

#: Fields whose presence requires a ``human_on_behalf_of`` identity
#: (ECC-2-3). AI agents cannot ask for these on their own authority.
HUMAN_REQUIRED_FIELDS: frozenset[str] = frozenset(
    {
        "NationalId",
        "Iqama",
        "IBAN",
        "BankAccountNumber",
        "MedicalRecord",
        "Passport",
    }
)

#: Fields that require a CONFIDENTIAL clearance on the caller (ECC-1-5).
#: ``BaseSalary`` intentionally lives outside this set — high-level
#: payroll summaries are served at INTERNAL classification; only the
#: identity / banking / medical fields cross the CONFIDENTIAL line.
CONFIDENTIAL_FIELDS: frozenset[str] = frozenset(
    {
        "NationalId",
        "Iqama",
        "IBAN",
        "BankAccountNumber",
        "MedicalRecord",
        "Passport",
    }
)


def _classification_rank(name: str) -> int:
    return CLASSIFICATION_ORDER.get(name.upper(), -1)


def evaluate(request: Request) -> RuleResult:
    """Run the NCA-ECC rule pack against a :class:`Request`."""

    fired: list[dict[str, object]] = []
    score = 100
    decision = Decision.ALLOW

    # ECC-4-1 — cross-border routing.
    if request.sovereign_region != SOVEREIGN_REGION:
        fired.append(
            {
                "rule": "NCA_ECC.4_1_CROSS_BORDER",
                "detail": (
                    f"request sovereign_region={request.sovereign_region!r} "
                    f"but Atlas only operates inside {SOVEREIGN_REGION!r}"
                ),
                "action": "BLOCK",
            }
        )
        score -= 80
        decision = Decision.BLOCK

    # ECC-5-2 — third-party system whitelist.
    target_system = request.payload.get("target_system") or request.payload.get(
        "system"
    )
    if target_system is None:
        # Not fatal — many requests are routed before ``target_system``
        # is populated by the gateway. Just nudge the score.
        score -= 5
    elif str(target_system).upper() not in ALLOWED_TARGET_SYSTEMS:
        fired.append(
            {
                "rule": "NCA_ECC.5_2_UNTRUSTED_TARGET",
                "detail": f"target_system={target_system!r} is not in allow-list",
                "action": "BLOCK",
            }
        )
        score -= 60
        decision = Decision.BLOCK

    # ECC-1-5 — classification ceiling.
    caller_rank = _classification_rank(request.data_classification)
    if caller_rank < 0:
        fired.append(
            {
                "rule": "NCA_ECC.1_5_UNKNOWN_CLASSIFICATION",
                "detail": f"{request.data_classification!r} is not a recognised class",
                "action": "DEGRADE",
            }
        )
        score -= 15

    # ECC-2-3 — human-on-behalf-of required for sensitive fields.
    sensitive_hits = request.field_set() & HUMAN_REQUIRED_FIELDS
    if sensitive_hits and not request.human_on_behalf_of:
        fired.append(
            {
                "rule": "NCA_ECC.2_3_HUMAN_IDENTITY_REQUIRED",
                "detail": (
                    "fields "
                    f"{sorted(sensitive_hits)} require a human-on-behalf-of "
                    "principal, but none was provided"
                ),
                "action": "BLOCK",
            }
        )
        score -= 50
        if decision != Decision.BLOCK:
            decision = Decision.BLOCK

    # ECC-1-5 — CONFIDENTIAL data requires CONFIDENTIAL clearance.
    confidential_hits = request.field_set() & CONFIDENTIAL_FIELDS
    if confidential_hits and caller_rank < CLASSIFICATION_ORDER["CONFIDENTIAL"]:
        fired.append(
            {
                "rule": "NCA_ECC.1_5_CLASSIFICATION_CEILING",
                "detail": (
                    f"caller clearance={request.data_classification!r} is "
                    "below CONFIDENTIAL but is asking for "
                    f"{sorted(confidential_hits)}"
                ),
                "action": "BLOCK",
            }
        )
        score -= 40
        decision = Decision.BLOCK

    # ECC-2-1 — caller must have a non-empty agent id.
    if not request.agent_id:
        fired.append(
            {
                "rule": "NCA_ECC.2_1_UNKNOWN_ASSET",
                "detail": "request has no agent_id — cannot trace asset",
                "action": "BLOCK",
            }
        )
        score -= 30
        decision = Decision.BLOCK

    score = max(score, 0)
    return RuleResult(
        pack=PACK,
        score=score,
        decision=decision,
        fired=fired,
        notes=(
            f"cross_border={request.sovereign_region != SOVEREIGN_REGION}, "
            f"sensitive_hits={sorted(sensitive_hits)}"
        ),
    )


__all__ = [
    "PACK",
    "SOVEREIGN_REGION",
    "CLASSIFICATION_ORDER",
    "ALLOWED_TARGET_SYSTEMS",
    "HUMAN_REQUIRED_FIELDS",
    "CONFIDENTIAL_FIELDS",
    "evaluate",
]
