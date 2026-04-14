"""Shared test fixtures for ``provisioning/tests``.

Responsibilities
----------------
1. Register ``provisioning/`` on ``sys.path`` so every ``import config``
   / ``import deploy_schema`` etc. resolves to the sibling scripts
   regardless of how pytest is invoked.

2. Install a lightweight stub for the ``oracledb`` driver. The real
   driver is a C-extension package that this repo doesn't ship and
   pytest doesn't need to run. Every deploy script does
   ``import oracledb`` at module top level, so without a stub the test
   collection fails immediately with ``ModuleNotFoundError``.

   The stub is just enough to satisfy attribute access — ``DatabaseError``
   and ``Error`` are real exception classes so ``except oracledb.*``
   blocks behave correctly, and ``connect`` is a ``MagicMock`` each test
   can replace per-case via ``monkeypatch``.
"""

from __future__ import annotations

import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

PROVISIONING_DIR = Path(__file__).resolve().parent.parent

if str(PROVISIONING_DIR) not in sys.path:
    sys.path.insert(0, str(PROVISIONING_DIR))


def _install_oracledb_stub() -> None:
    if "oracledb" in sys.modules:
        return

    stub = types.ModuleType("oracledb")

    class DatabaseError(Exception):
        """Stand-in for ``oracledb.DatabaseError``."""

    class Error(Exception):
        """Stand-in for ``oracledb.Error``."""

    stub.DatabaseError = DatabaseError
    stub.Error = Error
    stub.connect = MagicMock(name="oracledb.connect")
    sys.modules["oracledb"] = stub


_install_oracledb_stub()
