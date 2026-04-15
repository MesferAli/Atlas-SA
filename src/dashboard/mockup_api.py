"""Trust Dashboard — JSON mockup API.

Exposes a tiny HTTP server (stdlib only — no Flask, no FastAPI) that
serves a single ``GET /dashboard`` endpoint returning the metrics that
feed the Atlas "Trust Dashboard":

* ``Compliance_Score``        — weighted mean score of the last N requests.
* ``Blocked_Intent_Attacks``  — count of requests blocked by the intent monitor.
* ``Active_Sovereign_Logs``   — count of audit entries currently tagged as
  sovereign (i.e. ``X-Sovereign-Region == me-riyadh-1``).
* ``Recent_Events``           — the last 20 audit envelopes, so that the UI can
  display a live event feed.

Usage
-----
Run the server::

    python -m src.dashboard.mockup_api --port 8088

Then open ``http://localhost:8088/dashboard`` or invoke it
programmatically from :mod:`src.dashboard.store` in unit tests.

The store is deliberately an in-memory ring buffer — the PoC is meant
to run for the duration of a board demo, not to survive restarts.
"""

from __future__ import annotations

import argparse
import json
import threading
from collections import deque
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Deque

from ..rules_engine import Request
from ..rules_engine.engine import run as run_rules


class TrustStore:
    """In-memory ring buffer of audit envelopes.

    The store is the single source of truth for the dashboard and for
    the CLI demo's ``status`` command. It is fully thread-safe so the
    HTTP handler and the CLI can share a process.
    """

    def __init__(self, capacity: int = 256) -> None:
        self._events: Deque[dict[str, Any]] = deque(maxlen=capacity)
        self._lock = threading.Lock()

    def record(self, envelope: dict[str, Any]) -> None:
        with self._lock:
            self._events.append(envelope)

    def snapshot(self) -> list[dict[str, Any]]:
        with self._lock:
            return list(self._events)

    def intercept(self, request: Request) -> dict[str, Any]:
        """Run the rules engine on ``request`` and record the envelope."""

        envelope = run_rules(request)
        self.record(envelope)
        return envelope

    def metrics(self) -> dict[str, Any]:
        events = self.snapshot()
        total = len(events)
        if total == 0:
            return {
                "Compliance_Score": 100,
                "Blocked_Intent_Attacks": 0,
                "Active_Sovereign_Logs": 0,
                "Total_Requests": 0,
                "Decisions": {"ALLOW": 0, "REDACT": 0, "BLOCK": 0},
                "Recent_Events": [],
            }

        compliance = round(sum(e["compliance_score"] for e in events) / total)

        blocked_intent = 0
        for e in events:
            for pack in e.get("per_pack", []):
                if pack["pack"] == "INTENT_OVERSIGHT" and pack["decision"] == "BLOCK":
                    blocked_intent += 1
                    break

        sovereign_logs = sum(
            1 for e in events if e.get("sovereign_proof", "").startswith("sha256:")
        )

        decisions = {"ALLOW": 0, "REDACT": 0, "BLOCK": 0}
        for e in events:
            decisions[e["decision"]] = decisions.get(e["decision"], 0) + 1

        return {
            "Compliance_Score": compliance,
            "Blocked_Intent_Attacks": blocked_intent,
            "Active_Sovereign_Logs": sovereign_logs,
            "Total_Requests": total,
            "Decisions": decisions,
            "Recent_Events": [
                {
                    "request_id": e["request_id"],
                    "agent_id": e["agent_id"],
                    "decision": e["decision"],
                    "compliance_score": e["compliance_score"],
                    "declared_intent": e["declared_intent"],
                    "observed_intent": e.get("intent_analysis", {}).get(
                        "observed_intent"
                    ),
                }
                for e in list(reversed(events))[:20]
            ],
        }


# Global store used by the HTTP handler. The CLI demo reaches in via
# :func:`get_store` so every audit envelope the demo generates shows up
# in ``GET /dashboard``.
_STORE = TrustStore()


def get_store() -> TrustStore:
    return _STORE


class _DashboardHandler(BaseHTTPRequestHandler):
    def _send_json(self, status: int, body: dict[str, Any]) -> None:
        payload = json.dumps(body, indent=2, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        # Advertise the sovereign region on every response so the
        # dashboard UI can render the "Data stays inside the Kingdom"
        # badge without having to inspect the body.
        self.send_header("X-Sovereign-Region", "me-riyadh-1")
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self) -> None:  # noqa: N802 — stdlib API
        if self.path.rstrip("/") == "/dashboard":
            self._send_json(200, _STORE.metrics())
            return
        if self.path.rstrip("/") == "/events":
            self._send_json(200, {"events": _STORE.snapshot()})
            return
        self._send_json(
            404,
            {
                "error": "not_found",
                "path": self.path,
                "available": ["/dashboard", "/events"],
            },
        )

    # Keep logs quiet during the demo.
    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        return


def serve(host: str = "127.0.0.1", port: int = 8088) -> HTTPServer:
    """Start the HTTP server and return the :class:`HTTPServer` instance.

    Synchronous — the caller is responsible for running
    :meth:`HTTPServer.serve_forever` on its own thread if desired.
    """

    server = HTTPServer((host, port), _DashboardHandler)
    return server


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="atlas-dashboard",
        description="Atlas Trust Dashboard JSON API (PoC)",
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8088)
    parser.add_argument(
        "--seed",
        action="store_true",
        help="Pre-populate the store with representative demo events so "
        "the dashboard is not empty on first load.",
    )
    return parser.parse_args(argv)


def _seed_demo_events(store: TrustStore) -> None:
    """Populate the store with a realistic mix of events for the demo."""

    samples = [
        Request(
            request_id="req_seed_001",
            agent_id="agent://hr-copilot/v2",
            declared_intent="READ_PAYROLL_SUMMARY",
            fields_requested=["PersonNumber", "DisplayName", "BaseSalary"],
            data_classification="INTERNAL",
            human_on_behalf_of="user_14923",
        ),
        Request(
            request_id="req_seed_002",
            agent_id="agent://finance-copilot/v1",
            declared_intent="GENERATE_INVOICE",
            fields_requested=["InvoiceNumber", "CustomerName", "VATNumber", "TotalAmount"],
            data_classification="INTERNAL",
            human_on_behalf_of="user_44110",
        ),
        Request(
            request_id="req_seed_003",
            agent_id="agent://rogue-assistant/x",
            declared_intent="READ_PAYROLL_SUMMARY",
            fields_requested=[
                "PersonNumber",
                "NationalId",
                "IBAN",
                "BaseSalary",
                "HomeAddress",
            ],
            data_classification="INTERNAL",
            human_on_behalf_of=None,
        ),
        Request(
            request_id="req_seed_004",
            agent_id="agent://hr-copilot/v2",
            declared_intent="READ_HEADCOUNT",
            fields_requested=["Department", "PersonCount"],
            data_classification="PUBLIC",
        ),
    ]
    for sample in samples:
        store.intercept(sample)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    if args.seed:
        _seed_demo_events(_STORE)
    server = serve(args.host, args.port)
    print(
        f"[atlas] trust dashboard listening on http://{args.host}:{args.port}"
        f"/dashboard  (region=me-riyadh-1)"
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[atlas] shutting down")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
