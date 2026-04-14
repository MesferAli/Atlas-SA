"""Atlas rules engine.

The rules engine is the heart of the Atlas Sovereign Oversight
Middleware. It is built as a collection of small, independent rule packs
that can each answer one question:

* :mod:`pdpl_rules` — "Does this request expose personal data protected
  by the Saudi Personal Data Protection Law, and if so, how do we
  redact it?"
* :mod:`nca_ecc_validator` — "Does this request try to bypass a security
  boundary mandated by the NCA Essential Cybersecurity Controls?"
* :mod:`intent_monitor` — "Does the declared intent actually justify the
  fields being requested, or are we looking at hidden deception /
  sandbagging by an AI agent?"

Every rule pack exposes a function that takes a :class:`Request` and
returns a :class:`RuleResult`. The middleware aggregates those results
into a single :class:`Decision` ("ALLOW" / "REDACT" / "BLOCK") and a
compliance score between 0 and 100.

The packs are intentionally dependency-free (Python standard library
only) so that the PoC can run on any developer laptop, in any CI
pipeline, and inside an OCI Function without packaging pain.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Decision(str, Enum):
    """Final decision produced by the rules engine."""

    ALLOW = "ALLOW"
    REDACT = "REDACT"
    BLOCK = "BLOCK"


@dataclass
class Request:
    """Normalised view of an intercepted request.

    The middleware converts every incoming ``POST /intercept`` body into
    an instance of this class before running the rule packs.
    """

    request_id: str
    agent_id: str
    declared_intent: str
    fields_requested: list[str]
    data_classification: str = "INTERNAL"
    sovereign_region: str = "me-riyadh-1"
    payload: dict[str, Any] = field(default_factory=dict)
    human_on_behalf_of: str | None = None

    def field_set(self) -> set[str]:
        return {f.strip() for f in self.fields_requested}


@dataclass
class RuleResult:
    """Result of running a single rule pack against a :class:`Request`."""

    pack: str
    score: int  # 0..100
    decision: Decision
    fired: list[dict[str, Any]] = field(default_factory=list)
    redactions: dict[str, str] = field(default_factory=dict)
    notes: str = ""


def combine(results: list[RuleResult]) -> tuple[Decision, int, list[RuleResult]]:
    """Combine several :class:`RuleResult` objects into a final verdict.

    Rules of combination:

    * If any pack returns ``BLOCK`` the final decision is ``BLOCK``.
    * Otherwise, if any pack returns ``REDACT`` the final decision is
      ``REDACT``.
    * Otherwise the decision is ``ALLOW``.
    * The compliance score is the (integer) mean of the individual
      scores, so a single heavily-penalised pack drags the overall
      score down proportionally.
    """

    if not results:
        return Decision.ALLOW, 100, []
    worst = Decision.ALLOW
    for r in results:
        if r.decision == Decision.BLOCK:
            worst = Decision.BLOCK
            break
        if r.decision == Decision.REDACT and worst != Decision.BLOCK:
            worst = Decision.REDACT
    score = int(round(sum(r.score for r in results) / len(results)))
    return worst, score, results


__all__ = ["Decision", "Request", "RuleResult", "combine"]
