"""Unit tests for the Atlas rules engine.

These tests focus on the deterministic logic: PII detection, masking,
intent oversight, NCA-ECC classification ceilings, and the aggregated
decision produced by :func:`src.rules_engine.engine.run`. They run
without a database, without a network, and without any external
packages — ``pytest`` is enough.
"""

from __future__ import annotations

from src.rules_engine import Decision, Request, combine
from src.rules_engine import intent_monitor, nca_ecc_validator, pdpl_rules
from src.rules_engine.engine import run as run_rules


# ---------------------------------------------------------------------------
# PDPL
# ---------------------------------------------------------------------------


def test_detect_pii_national_id() -> None:
    assert pdpl_rules.detect_pii("id=1098765432") == ["SA_ID"]
    assert pdpl_rules.detect_pii("no digits here") == []
    # 10 digits starting with 3 should NOT match (neither national nor iqama).
    assert pdpl_rules.detect_pii("3098765432") == []


def test_detect_pii_iban_and_mobile() -> None:
    assert "SA_IBAN" in pdpl_rules.detect_pii("IBAN SA0380000000608010167519")
    assert "SA_MOBILE" in pdpl_rules.detect_pii("call +966512345678")


def test_mask_sa_id_keeps_last_four() -> None:
    out = pdpl_rules.mask_sa_id("id=1098765432 other text")
    assert out == "id=******5432 other text"


def test_mask_sa_iban_keeps_country_and_tail() -> None:
    out = pdpl_rules.mask_sa_iban("IBAN SA0380000000608010167519 !")
    assert out.startswith("IBAN SA03")
    assert out.endswith("7519 !")
    assert "*" in out


def test_pdpl_evaluate_purpose_limitation_redacts() -> None:
    req = Request(
        request_id="t1",
        agent_id="agent://test/1",
        declared_intent="READ_PAYROLL_SUMMARY",
        fields_requested=["PersonNumber", "BaseSalary", "IBAN"],
    )
    result = pdpl_rules.evaluate(req)
    # IBAN is not allowed under READ_PAYROLL_SUMMARY → redaction.
    assert result.decision == Decision.REDACT
    assert "IBAN" in result.redactions
    assert any("IBAN" in rule.get("rule", "") for rule in result.fired)


def test_pdpl_evaluate_allows_legit_payroll_disburse() -> None:
    req = Request(
        request_id="t2",
        agent_id="agent://test/2",
        declared_intent="PAYROLL_DISBURSE",
        fields_requested=["PersonNumber", "BaseSalary", "IBAN"],
    )
    result = pdpl_rules.evaluate(req)
    # BaseSalary + IBAN are both in the allow-list for PAYROLL_DISBURSE.
    assert result.decision == Decision.ALLOW
    assert result.redactions == {}


def test_pdpl_evaluate_fishing_expedition_blocks() -> None:
    # All fields are sensitive AND none of them is allowed under the
    # declared intent → escalate to BLOCK.
    req = Request(
        request_id="t3",
        agent_id="agent://test/3",
        declared_intent="READ_HEADCOUNT",
        fields_requested=["NationalId", "IBAN", "BaseSalary"],
    )
    result = pdpl_rules.evaluate(req)
    assert result.decision == Decision.BLOCK
    assert any(rule["rule"] == "PDPL.FISHING_EXPEDITION" for rule in result.fired)


# ---------------------------------------------------------------------------
# NCA-ECC
# ---------------------------------------------------------------------------


def test_nca_ecc_blocks_cross_border() -> None:
    req = Request(
        request_id="t4",
        agent_id="agent://test/4",
        declared_intent="READ_HEADCOUNT",
        fields_requested=["Department", "PersonCount"],
        sovereign_region="eu-frankfurt-1",
    )
    result = nca_ecc_validator.evaluate(req)
    assert result.decision == Decision.BLOCK
    assert any("CROSS_BORDER" in rule["rule"] for rule in result.fired)


def test_nca_ecc_requires_human_on_behalf_of() -> None:
    req = Request(
        request_id="t5",
        agent_id="agent://test/5",
        declared_intent="PAYROLL_DISBURSE",
        fields_requested=["IBAN", "BaseSalary"],
        data_classification="CONFIDENTIAL",
    )
    result = nca_ecc_validator.evaluate(req)
    assert result.decision == Decision.BLOCK
    assert any(
        "2_3_HUMAN_IDENTITY_REQUIRED" in rule["rule"] for rule in result.fired
    )


def test_nca_ecc_classification_ceiling() -> None:
    req = Request(
        request_id="t6",
        agent_id="agent://test/6",
        declared_intent="PAYROLL_DISBURSE",
        fields_requested=["IBAN"],
        data_classification="PUBLIC",
        human_on_behalf_of="user_1",
    )
    result = nca_ecc_validator.evaluate(req)
    assert result.decision == Decision.BLOCK
    assert any(
        "CLASSIFICATION_CEILING" in rule["rule"] for rule in result.fired
    )


# ---------------------------------------------------------------------------
# Intent oversight
# ---------------------------------------------------------------------------


def test_intent_monitor_blocks_hidden_deception() -> None:
    req = Request(
        request_id="t7",
        agent_id="agent://rogue/x",
        declared_intent="READ_PAYROLL_SUMMARY",
        fields_requested=[
            "PersonNumber",
            "DisplayName",
            "NationalId",
            "IBAN",
            "HomeAddress",
        ],
    )
    result = intent_monitor.evaluate(req)
    assert result.decision == Decision.BLOCK
    assert any(
        rule["rule"] == "INTENT.DECEPTION_DETECTED" for rule in result.fired
    )


def test_intent_monitor_allows_clean_request() -> None:
    req = Request(
        request_id="t8",
        agent_id="agent://hr/1",
        declared_intent="READ_PAYROLL_SUMMARY",
        fields_requested=["PersonNumber", "DisplayName", "BaseSalary"],
    )
    result = intent_monitor.evaluate(req)
    assert result.decision == Decision.ALLOW


def test_intent_monitor_unknown_intent_blocks() -> None:
    req = Request(
        request_id="t9",
        agent_id="agent://mystery/1",
        declared_intent="DO_SOMETHING_FUN",
        fields_requested=["PersonNumber"],
    )
    result = intent_monitor.evaluate(req)
    assert result.decision == Decision.BLOCK
    assert any(rule["rule"] == "INTENT.UNKNOWN_INTENT" for rule in result.fired)


# ---------------------------------------------------------------------------
# Combined engine
# ---------------------------------------------------------------------------


def test_combine_picks_worst_decision() -> None:
    from src.rules_engine import RuleResult

    results = [
        RuleResult(pack="A", score=95, decision=Decision.ALLOW),
        RuleResult(pack="B", score=55, decision=Decision.REDACT),
        RuleResult(pack="C", score=10, decision=Decision.BLOCK),
    ]
    decision, score, _ = combine(results)
    assert decision == Decision.BLOCK
    # Mean of 95/55/10 = 53.33 → rounds to 53.
    assert score == 53


def test_engine_run_envelope_shape() -> None:
    req = Request(
        request_id="t10",
        agent_id="agent://hr/1",
        declared_intent="READ_PAYROLL_SUMMARY",
        fields_requested=["PersonNumber", "DisplayName", "BaseSalary"],
        human_on_behalf_of="user_1",
    )
    envelope = run_rules(req)
    assert envelope["decision"] == "ALLOW"
    assert envelope["request_id"] == "t10"
    assert envelope["sovereign_proof"].startswith("sha256:")
    assert {p["pack"] for p in envelope["per_pack"]} == {
        "PDPL",
        "NCA_ECC",
        "INTENT_OVERSIGHT",
    }
    assert envelope["intent_analysis"]["observed_intent"] == "READ_PAYROLL_SUMMARY"


def test_engine_run_blocks_deception() -> None:
    req = Request(
        request_id="t11",
        agent_id="agent://rogue/x",
        declared_intent="READ_PAYROLL_SUMMARY",
        fields_requested=[
            "PersonNumber",
            "NationalId",
            "IBAN",
            "HomeAddress",
            "BaseSalary",
        ],
        data_classification="CONFIDENTIAL",
        human_on_behalf_of="user_x",
    )
    envelope = run_rules(req)
    assert envelope["decision"] == "BLOCK"
    assert envelope["compliance_score"] < 60
