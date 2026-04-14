"""Rules-engine entry point that runs all rule packs in one shot.

This is the function the middleware, the dashboard and the CLI demo
all call. It is intentionally small: load the packs, run them, combine
the results. Adding a new pack in the future means appending it to
``DEFAULT_PACKS`` — nothing else needs to change.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Callable

from . import Decision, Request, RuleResult, combine
from . import intent_monitor, nca_ecc_validator, pdpl_rules

#: A pack is a ``(name, callable)`` pair where the callable takes a
#: :class:`Request` and returns a :class:`RuleResult`.
Pack = tuple[str, Callable[[Request], RuleResult]]

DEFAULT_PACKS: list[Pack] = [
    ("PDPL", pdpl_rules.evaluate),
    ("NCA_ECC", nca_ecc_validator.evaluate),
    ("INTENT_OVERSIGHT", intent_monitor.evaluate),
]


def sovereign_proof(request_id: str, region: str) -> str:
    """Deterministic, tenant-independent sovereignty proof.

    In production the hash is signed with the tenant's OCI KMS key. In
    the PoC a plain SHA-256 is enough to demonstrate the concept.
    """

    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    payload = f"{region}|{request_id}|{timestamp}".encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def run(request: Request, packs: list[Pack] | None = None) -> dict[str, object]:
    """Run every pack against ``request`` and return the audit envelope.

    The envelope contains everything the API layer needs to produce a
    ``POST /intercept`` response: the decision, the combined compliance
    score, every rule that fired, the per-pack breakdown, and a
    sovereignty proof for the audit trail.
    """

    packs = packs or DEFAULT_PACKS
    results: list[RuleResult] = [fn(request) for _, fn in packs]
    decision, score, _ = combine(results)

    return {
        "request_id": request.request_id,
        "agent_id": request.agent_id,
        "declared_intent": request.declared_intent,
        "decision": decision.value,
        "compliance_score": score,
        "sovereign_proof": sovereign_proof(
            request.request_id, request.sovereign_region
        ),
        "per_pack": [
            {
                "pack": r.pack,
                "score": r.score,
                "decision": r.decision.value,
                "fired": r.fired,
                "redactions": r.redactions,
                "notes": r.notes,
            }
            for r in results
        ],
        "intent_analysis": intent_monitor.analyse(request),
    }


__all__ = ["DEFAULT_PACKS", "Pack", "run", "sovereign_proof"]
