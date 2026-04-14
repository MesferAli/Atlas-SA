"""Unit tests for ``provisioning/deploy_schema.py``.

These tests exercise the parts of ``deploy_schema.main`` that don't need a
real Oracle Autonomous Database:

* DDL statement splitting and whitespace handling.
* Idempotency: ``ORA-00955`` / ``ORA-02262`` / ``ORA-00942`` are treated
  as success so the script can be re-run against an existing schema.
* Non-idempotent ``DatabaseError`` returns exit code 1.
* ``Config.USE_WALLET`` controls whether wallet kwargs are passed to
  ``oracledb.connect``.

``oracledb`` is stubbed by ``conftest.py`` so no real driver is needed.
File I/O is patched with ``mock_open`` so the synthetic DDL is fed
straight into the script without touching disk.
"""

from __future__ import annotations

from unittest.mock import MagicMock, call, mock_open, patch

import oracledb  # stubbed by conftest.py
import pytest

import deploy_schema


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_cursor(execute_side_effect=None, fetchall_result=None):
    cursor = MagicMock(name="cursor")
    if execute_side_effect is not None:
        cursor.execute.side_effect = execute_side_effect
    cursor.fetchall.return_value = fetchall_result or []
    return cursor


def _make_connection(cursor):
    conn = MagicMock(name="connection")
    conn.cursor.return_value = cursor
    return conn


def _patch_connect(monkeypatch, connection):
    connect_mock = MagicMock(return_value=connection)
    monkeypatch.setattr(deploy_schema.oracledb, "connect", connect_mock)
    return connect_mock


def _run_main_with_ddl(monkeypatch, ddl: str, cursor, *, use_wallet: bool = False):
    """Invoke ``deploy_schema.main`` with synthetic DDL content."""
    monkeypatch.setattr(deploy_schema.Config, "USE_WALLET", use_wallet, raising=False)
    conn = _make_connection(cursor)
    connect_mock = _patch_connect(monkeypatch, conn)
    with patch("builtins.open", mock_open(read_data=ddl)):
        rc = deploy_schema.main()
    return rc, connect_mock


# ---------------------------------------------------------------------------
# DDL splitting
# ---------------------------------------------------------------------------

def test_ddl_splitting_strips_whitespace_and_drops_empty(monkeypatch):
    """Statements split on ``;``; empty / whitespace-only fragments drop.

    Input has three real statements, one trailing empty fragment after
    the final ``;``, and a blank-line gap between statements. The script
    should execute exactly three DDL statements plus the final
    ``user_objects`` verification query.
    """
    ddl = (
        "CREATE TABLE ATLAS_FOO (ID NUMBER);\n"
        "\n"
        "   CREATE INDEX IDX_FOO ON ATLAS_FOO(ID)   ;\n"
        "CREATE SEQUENCE SEQ_ATLAS_FOO START WITH 1;\n"
    )
    cursor = _make_cursor()

    rc, _ = _run_main_with_ddl(monkeypatch, ddl, cursor)

    assert rc == 0
    executed = [c.args[0] for c in cursor.execute.call_args_list]

    # Three DDL statements + one SELECT verification query.
    ddl_stmts = [s for s in executed if "ATLAS_FOO" in s]
    assert len(ddl_stmts) == 3
    # Whitespace is trimmed by .strip() in the script.
    assert all(s == s.strip() for s in ddl_stmts)
    # Final verification query is issued exactly once.
    assert sum(1 for s in executed if "user_objects" in s) == 1


def test_empty_ddl_file_executes_no_statements(monkeypatch):
    """An empty DDL file still runs the verification query and returns 0."""
    cursor = _make_cursor()

    rc, _ = _run_main_with_ddl(monkeypatch, "", cursor)

    assert rc == 0
    executed = [c.args[0] for c in cursor.execute.call_args_list]
    # Only the verification SELECT.
    assert len(executed) == 1
    assert "user_objects" in executed[0]


# ---------------------------------------------------------------------------
# Error classification
# ---------------------------------------------------------------------------

_IDEMPOTENT_CODES = ["ORA-00955", "ORA-02262", "ORA-00942"]


@pytest.mark.parametrize("ora_code", _IDEMPOTENT_CODES)
def test_idempotent_errors_are_tolerated(monkeypatch, ora_code):
    """DDL that fails with an idempotency code must not fail the run."""
    ddl = "CREATE TABLE ATLAS_FOO (ID NUMBER);"

    def execute(stmt, *args, **kwargs):
        if "ATLAS_FOO" in stmt:
            raise oracledb.DatabaseError(f"{ora_code}: already used")
        # verification SELECT succeeds
        return None

    cursor = _make_cursor(execute_side_effect=execute)

    rc, _ = _run_main_with_ddl(monkeypatch, ddl, cursor)

    assert rc == 0, f"{ora_code} should be treated as success"


def test_non_idempotent_database_error_fails_the_run(monkeypatch):
    """Any ``DatabaseError`` outside the idempotent set must fail."""
    ddl = "CREATE TABLE ATLAS_FOO (ID NUMBER);"

    def execute(stmt, *args, **kwargs):
        if "ATLAS_FOO" in stmt:
            raise oracledb.DatabaseError("ORA-00001: unique constraint violated")
        return None

    cursor = _make_cursor(execute_side_effect=execute)

    rc, _ = _run_main_with_ddl(monkeypatch, ddl, cursor)

    assert rc == 1


def test_mixed_success_and_idempotent_error_still_returns_zero(monkeypatch):
    """One clean CREATE + one ``ORA-00955`` must report zero errors."""
    ddl = (
        "CREATE TABLE ATLAS_FOO (ID NUMBER);\n"
        "CREATE TABLE ATLAS_BAR (ID NUMBER);\n"
    )

    def execute(stmt, *args, **kwargs):
        if "ATLAS_BAR" in stmt:
            raise oracledb.DatabaseError("ORA-00955: name already used")
        return None

    cursor = _make_cursor(execute_side_effect=execute)

    rc, _ = _run_main_with_ddl(monkeypatch, ddl, cursor)

    assert rc == 0


# ---------------------------------------------------------------------------
# Connection kwargs (wallet vs walletless)
# ---------------------------------------------------------------------------

def test_use_wallet_true_passes_wallet_kwargs(monkeypatch):
    """``USE_WALLET=True`` must pass ``config_dir`` / ``wallet_location``."""
    cursor = _make_cursor()
    monkeypatch.setattr(deploy_schema.Config, "DB_WALLET_PATH", "/tmp/atlas_wallet", raising=False)

    _, connect_mock = _run_main_with_ddl(monkeypatch, "", cursor, use_wallet=True)

    connect_mock.assert_called_once()
    kwargs = connect_mock.call_args.kwargs
    assert kwargs.get("config_dir") == "/tmp/atlas_wallet"
    assert kwargs.get("wallet_location") == "/tmp/atlas_wallet"
    assert "wallet_password" in kwargs


def test_use_wallet_false_omits_wallet_kwargs(monkeypatch):
    """Walletless TLS must not pass wallet-specific kwargs to ``connect``."""
    cursor = _make_cursor()

    _, connect_mock = _run_main_with_ddl(monkeypatch, "", cursor, use_wallet=False)

    connect_mock.assert_called_once()
    kwargs = connect_mock.call_args.kwargs
    assert "config_dir" not in kwargs
    assert "wallet_location" not in kwargs
    assert "wallet_password" not in kwargs
    # But the core connection parameters must still be present.
    assert "user" in kwargs
    assert "password" in kwargs
    assert "dsn" in kwargs


# ---------------------------------------------------------------------------
# Real schema_ddl.sql smoke test
# ---------------------------------------------------------------------------

def test_real_schema_ddl_parses_into_multiple_statements(monkeypatch):
    """The committed ``schema_ddl.sql`` parses into >10 executable statements.

    This catches the case where a future edit corrupts the DDL file or
    produces a file with no ``;`` terminators at all.
    """
    from pathlib import Path

    ddl_path = Path(deploy_schema.__file__).resolve().parent / "schema_ddl.sql"
    assert ddl_path.exists(), f"schema_ddl.sql missing at {ddl_path}"

    ddl_content = ddl_path.read_text()
    stmts = [s.strip() for s in ddl_content.split(";") if s.strip()]
    assert len(stmts) > 10, (
        f"schema_ddl.sql parsed into only {len(stmts)} statements; "
        "expected at least 10 (tables, indexes, sequences, comments)."
    )
    # Every parsed statement should start with a DDL keyword.
    ddl_keywords = ("CREATE", "COMMENT", "GRANT", "ALTER", "INSERT", "--")
    for stmt in stmts:
        first_word = stmt.lstrip().split(None, 1)[0].upper()
        assert first_word.startswith(ddl_keywords) or first_word.startswith("--"), (
            f"Unexpected statement prefix: {first_word!r}"
        )
