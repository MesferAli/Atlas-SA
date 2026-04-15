"""Interactive CLI demo for the Atlas Sovereign Oversight PoC.

This is the piece a board member can run on a laptop during the pitch.
It exposes four subcommands:

* ``scenario`` — run one of the pre-baked scenarios (``payroll``,
  ``deception``, ``cross-border``, ``invoice``) and print a clean,
  colour-coded verdict.
* ``intercept`` — ad-hoc evaluation from the command line. Pass the
  intent and the requested fields as arguments to craft a custom
  request on the fly.
* ``status`` — prints the current Trust Dashboard metrics as JSON.
* ``repl`` — drop into an interactive prompt where each line is a new
  intercept. Useful for a "live" demo.

The CLI has zero external dependencies (standard library only) and
does not require a network: every decision is computed locally by the
rules engine. A real Atlas deployment would instead call the OCI API
Gateway endpoints defined in ``docs/API_SPEC.md``.

Examples
--------
Run the "hidden deception" scenario::

    python -m src.demo.cli scenario deception

Craft a custom request::

    python -m src.demo.cli intercept \
        --agent agent://hr-copilot/v2 \
        --intent READ_PAYROLL_SUMMARY \
        --fields PersonNumber,DisplayName,NationalId,IBAN \
        --human user_14923

Show the dashboard metrics::

    python -m src.demo.cli status
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from typing import Callable

from ..dashboard.mockup_api import get_store
from ..rules_engine import Request


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------

_ANSI = {
    "reset": "\033[0m",
    "bold": "\033[1m",
    "dim": "\033[2m",
    "red": "\033[31m",
    "green": "\033[32m",
    "yellow": "\033[33m",
    "blue": "\033[34m",
    "magenta": "\033[35m",
    "cyan": "\033[36m",
}


def _color(text: str, color: str, *, use_colour: bool) -> str:
    if not use_colour:
        return text
    return f"{_ANSI.get(color, '')}{text}{_ANSI['reset']}"


def _decision_colour(decision: str) -> str:
    return {
        "ALLOW": "green",
        "REDACT": "yellow",
        "BLOCK": "red",
    }.get(decision, "cyan")


def _print_envelope(envelope: dict[str, object], *, use_colour: bool) -> None:
    decision = str(envelope["decision"])
    score = envelope["compliance_score"]

    bar = "=" * 64
    print(_color(bar, "dim", use_colour=use_colour))
    print(
        _color("  Atlas Sovereign Oversight — Decision", "bold", use_colour=use_colour)
    )
    print(_color(bar, "dim", use_colour=use_colour))
    print(f"  Request ID       : {envelope['request_id']}")
    print(f"  Agent            : {envelope['agent_id']}")
    print(f"  Declared intent  : {envelope['declared_intent']}")
    intent_analysis = envelope.get("intent_analysis", {})
    if isinstance(intent_analysis, dict):
        print(
            f"  Observed intent  : {intent_analysis.get('observed_intent')}"
            f"   (skepticism={intent_analysis.get('skepticism_score')})"
        )
    print(
        "  Decision         : "
        + _color(
            decision,
            _decision_colour(decision),
            use_colour=use_colour,
        )
    )
    print(
        "  Compliance score : "
        + _color(f"{score}/100", "cyan", use_colour=use_colour)
    )
    print(f"  Sovereign proof  : {envelope['sovereign_proof']}")
    print(_color(bar, "dim", use_colour=use_colour))

    per_pack = envelope.get("per_pack", [])
    if isinstance(per_pack, list):
        for pack in per_pack:
            pack_decision = str(pack["decision"])
            tag = _color(
                f"[{pack['pack']}]",
                _decision_colour(pack_decision),
                use_colour=use_colour,
            )
            print(
                f"  {tag} score={pack['score']} decision={pack_decision}"
            )
            for rule in pack.get("fired", []) or []:
                rule_line = f"     - {rule.get('rule')}: {rule.get('detail', rule)}"
                print(_color(rule_line, "dim", use_colour=use_colour))
    print(_color(bar, "dim", use_colour=use_colour))


# ---------------------------------------------------------------------------
# Scenarios
# ---------------------------------------------------------------------------


@dataclass
class Scenario:
    name: str
    description: str
    request: Request
    expected_decision: str


SCENARIOS: dict[str, Scenario] = {
    "payroll": Scenario(
        name="payroll",
        description=(
            "Legitimate payroll summary by the HR copilot — should be ALLOWED."
        ),
        request=Request(
            request_id="req_demo_payroll",
            agent_id="agent://hr-copilot/v2",
            declared_intent="READ_PAYROLL_SUMMARY",
            fields_requested=["PersonNumber", "DisplayName", "BaseSalary"],
            data_classification="INTERNAL",
            human_on_behalf_of="user_14923",
        ),
        expected_decision="ALLOW",
    ),
    "deception": Scenario(
        name="deception",
        description=(
            "Rogue agent declares a harmless payroll summary but pulls "
            "NationalId, IBAN and home address — the Intent Monitor "
            "should BLOCK it."
        ),
        request=Request(
            request_id="req_demo_deception",
            agent_id="agent://rogue-assistant/x",
            declared_intent="READ_PAYROLL_SUMMARY",
            fields_requested=[
                "PersonNumber",
                "DisplayName",
                "NationalId",
                "IBAN",
                "HomeAddress",
                "BaseSalary",
            ],
            data_classification="CONFIDENTIAL",
            human_on_behalf_of="user_99999",
        ),
        expected_decision="BLOCK",
    ),
    "cross-border": Scenario(
        name="cross-border",
        description=(
            "A request that tries to route through eu-frankfurt-1 — "
            "NCA-ECC 4-1 should BLOCK it immediately."
        ),
        request=Request(
            request_id="req_demo_crossborder",
            agent_id="agent://hr-copilot/v2",
            declared_intent="READ_HEADCOUNT",
            fields_requested=["Department", "PersonCount"],
            data_classification="INTERNAL",
            sovereign_region="eu-frankfurt-1",
        ),
        expected_decision="BLOCK",
    ),
    "invoice": Scenario(
        name="invoice",
        description="ZATCA-compliant invoice generation — should be ALLOWED.",
        request=Request(
            request_id="req_demo_invoice",
            agent_id="agent://finance-copilot/v1",
            declared_intent="GENERATE_INVOICE",
            fields_requested=[
                "InvoiceNumber",
                "CustomerName",
                "VATNumber",
                "TotalAmount",
                "Currency",
            ],
            data_classification="INTERNAL",
            human_on_behalf_of="user_44110",
        ),
        expected_decision="ALLOW",
    ),
}


# ---------------------------------------------------------------------------
# Subcommand handlers
# ---------------------------------------------------------------------------


def _run_and_print(request: Request, *, use_colour: bool) -> dict[str, object]:
    envelope = get_store().intercept(request)
    _print_envelope(envelope, use_colour=use_colour)
    return envelope


def cmd_scenario(args: argparse.Namespace) -> int:
    name = args.name
    if name == "list":
        print("Available scenarios:")
        for scenario in SCENARIOS.values():
            print(f"  {scenario.name:<14} {scenario.description}")
        return 0
    scenario = SCENARIOS.get(name)
    if scenario is None:
        print(
            f"unknown scenario {name!r}. Run `scenario list` to see the available ones.",
            file=sys.stderr,
        )
        return 2
    use_colour = sys.stdout.isatty() and not args.no_colour
    print(
        _color(
            f"[atlas] scenario: {scenario.name} — {scenario.description}",
            "magenta",
            use_colour=use_colour,
        )
    )
    envelope = _run_and_print(scenario.request, use_colour=use_colour)
    match = envelope["decision"] == scenario.expected_decision
    marker = "OK" if match else "MISMATCH"
    print(
        _color(
            f"[atlas] expected={scenario.expected_decision} got={envelope['decision']} [{marker}]",
            "green" if match else "red",
            use_colour=use_colour,
        )
    )
    return 0 if match else 1


def cmd_intercept(args: argparse.Namespace) -> int:
    fields = [f.strip() for f in args.fields.split(",") if f.strip()]
    request = Request(
        request_id=args.request_id,
        agent_id=args.agent,
        declared_intent=args.intent,
        fields_requested=fields,
        data_classification=args.classification,
        sovereign_region=args.region,
        human_on_behalf_of=args.human,
    )
    use_colour = sys.stdout.isatty() and not args.no_colour
    envelope = _run_and_print(request, use_colour=use_colour)
    if args.json:
        print(json.dumps(envelope, indent=2, default=str))
    return 0 if envelope["decision"] != "BLOCK" else 3


def cmd_status(args: argparse.Namespace) -> int:
    metrics = get_store().metrics()
    print(json.dumps(metrics, indent=2, default=str))
    return 0


def cmd_repl(args: argparse.Namespace) -> int:
    use_colour = sys.stdout.isatty() and not args.no_colour
    print(
        _color(
            "Atlas Sovereign Oversight — interactive demo",
            "bold",
            use_colour=use_colour,
        )
    )
    print(
        _color(
            "Type a declared intent, then comma-separated fields, then Enter. "
            "Ctrl-D to exit.",
            "dim",
            use_colour=use_colour,
        )
    )
    counter = 0
    while True:
        try:
            intent = input(_color("intent> ", "cyan", use_colour=use_colour)).strip()
            if not intent:
                continue
            fields_raw = input(
                _color("fields> ", "cyan", use_colour=use_colour)
            ).strip()
        except EOFError:
            print()
            return 0
        fields = [f.strip() for f in fields_raw.split(",") if f.strip()]
        counter += 1
        request = Request(
            request_id=f"req_repl_{counter:04d}",
            agent_id="agent://demo-repl/v1",
            declared_intent=intent,
            fields_requested=fields,
            data_classification="INTERNAL",
            human_on_behalf_of="user_demo",
        )
        _run_and_print(request, use_colour=use_colour)


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="atlas-demo",
        description="Interactive CLI demo for the Atlas Sovereign Oversight PoC",
    )
    parser.add_argument(
        "--no-colour", action="store_true", help="disable ANSI colour output"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    scen = sub.add_parser("scenario", help="run a pre-baked demo scenario")
    scen.add_argument(
        "name",
        help="scenario name (run `scenario list` to see the available ones)",
    )
    scen.set_defaults(func=cmd_scenario)

    inter = sub.add_parser("intercept", help="evaluate a custom request")
    inter.add_argument("--request-id", default="req_cli_ad_hoc")
    inter.add_argument("--agent", required=True)
    inter.add_argument("--intent", required=True)
    inter.add_argument("--fields", required=True, help="comma-separated field list")
    inter.add_argument("--classification", default="INTERNAL")
    inter.add_argument("--region", default="me-riyadh-1")
    inter.add_argument("--human", default=None, help="human-on-behalf-of user id")
    inter.add_argument("--json", action="store_true", help="also print JSON envelope")
    inter.set_defaults(func=cmd_intercept)

    status = sub.add_parser("status", help="print the Trust Dashboard JSON metrics")
    status.set_defaults(func=cmd_status)

    repl = sub.add_parser("repl", help="interactive prompt (intent + fields per line)")
    repl.set_defaults(func=cmd_repl)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
