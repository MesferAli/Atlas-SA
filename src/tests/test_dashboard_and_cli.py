"""Tests for the Trust Dashboard store and the interactive CLI demo."""

from __future__ import annotations

import io
import json
from contextlib import redirect_stdout

import pytest

from src.dashboard.mockup_api import TrustStore, get_store
from src.demo.cli import SCENARIOS, main as cli_main
from src.rules_engine import Request


# ---------------------------------------------------------------------------
# Trust store
# ---------------------------------------------------------------------------


def _fresh_store() -> TrustStore:
    return TrustStore(capacity=16)


def test_trust_store_records_and_counts() -> None:
    store = _fresh_store()
    store.intercept(
        Request(
            request_id="s1",
            agent_id="agent://t/1",
            declared_intent="READ_PAYROLL_SUMMARY",
            fields_requested=["PersonNumber", "BaseSalary", "DisplayName"],
            human_on_behalf_of="user_1",
        )
    )
    store.intercept(
        Request(
            request_id="s2",
            agent_id="agent://rogue/x",
            declared_intent="READ_PAYROLL_SUMMARY",
            fields_requested=["NationalId", "IBAN", "HomeAddress"],
            data_classification="CONFIDENTIAL",
            human_on_behalf_of="user_2",
        )
    )
    metrics = store.metrics()
    assert metrics["Total_Requests"] == 2
    assert metrics["Blocked_Intent_Attacks"] >= 1
    assert metrics["Compliance_Score"] <= 100
    assert metrics["Decisions"]["BLOCK"] >= 1
    assert len(metrics["Recent_Events"]) == 2


def test_trust_store_ring_buffer_capacity() -> None:
    store = TrustStore(capacity=3)
    for i in range(5):
        store.intercept(
            Request(
                request_id=f"r{i}",
                agent_id="agent://t/1",
                declared_intent="READ_HEADCOUNT",
                fields_requested=["Department", "PersonCount"],
            )
        )
    assert store.metrics()["Total_Requests"] == 3


def test_empty_store_has_safe_defaults() -> None:
    metrics = _fresh_store().metrics()
    assert metrics["Compliance_Score"] == 100
    assert metrics["Blocked_Intent_Attacks"] == 0
    assert metrics["Recent_Events"] == []


# ---------------------------------------------------------------------------
# CLI scenarios
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "scenario_name, expected_decision",
    [(s.name, s.expected_decision) for s in SCENARIOS.values()],
)
def test_cli_scenario_matches_expected_decision(
    scenario_name: str, expected_decision: str
) -> None:
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = cli_main(["--no-colour", "scenario", scenario_name])
    output = buf.getvalue()
    assert expected_decision in output
    # Exit code: 0 if the scenario's expected decision matched.
    assert rc == 0


def test_cli_status_returns_valid_json() -> None:
    # Prime the global store with one intercept so the output is non-empty.
    get_store().intercept(
        Request(
            request_id="cli_prime",
            agent_id="agent://t/1",
            declared_intent="READ_HEADCOUNT",
            fields_requested=["Department", "PersonCount"],
        )
    )
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = cli_main(["--no-colour", "status"])
    assert rc == 0
    parsed = json.loads(buf.getvalue())
    assert "Compliance_Score" in parsed
    assert "Blocked_Intent_Attacks" in parsed
    assert "Active_Sovereign_Logs" in parsed


def test_cli_intercept_ad_hoc_block_returns_exit_code_3() -> None:
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = cli_main(
            [
                "--no-colour",
                "intercept",
                "--agent",
                "agent://rogue/x",
                "--intent",
                "READ_PAYROLL_SUMMARY",
                "--fields",
                "PersonNumber,NationalId,IBAN,HomeAddress,BaseSalary",
                "--classification",
                "CONFIDENTIAL",
                "--human",
                "user_1",
            ]
        )
    assert rc == 3
    assert "BLOCK" in buf.getvalue()
