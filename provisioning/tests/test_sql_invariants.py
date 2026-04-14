"""Static invariants for the Atlas SQL source tree.

CLAUDE.md §5 lists a handful of rules about the shape of the SQL
packages and schema DDL. Those rules are currently enforced only by
human review. These tests encode them as grep-and-parse assertions so
any PR that breaks one of them fails in CI instead of at deploy time.

Covered invariants
------------------
1. Prefix conventions
   * Every ``CREATE TABLE`` in ``schema_ddl.sql`` names an ``ATLAS_*`` table.
   * Every ``CREATE SEQUENCE`` starts with ``SEQ_ATLAS_``.
   * Every ``CREATE OR REPLACE PACKAGE`` / ``PACKAGE BODY`` in the
     Atlas ``*.sql`` files names an ``ATLAS_*_PKG`` package.

2. Classification columns (CLAUDE.md §5)
   * Every Fusion-sync-backed table (HR and Finance modules) has both
     ``DATA_CLASSIFICATION`` and ``LAST_SYNC_DATE`` columns.

3. ``ATLAS_HTTP_UTILS_PKG.MAKE_REQUEST`` signature
   * ``fusion_sync_integration.sql`` must not reintroduce the old
     ``p_username`` / ``p_password`` / ``p_response`` / ``p_status_code``
     parameter style that caused the package to fail to compile in the
     past. This is pinned in CLAUDE.md §5 and §8.
   * The status code is read separately via
     ``APEX_WEB_SERVICE.GET_STATUS_CODE`` in the same file.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

PROVISIONING_DIR = Path(__file__).resolve().parent.parent
SCHEMA_DDL = PROVISIONING_DIR / "schema_ddl.sql"
FUSION_SYNC = PROVISIONING_DIR / "fusion_sync_integration.sql"

# CLAUDE.md §5: tables that mirror Oracle Fusion must carry both columns.
FUSION_SYNCED_TABLES = frozenset({
    "ATLAS_EMPLOYEES",
    "ATLAS_DEPARTMENTS",
    "ATLAS_LOCATIONS",
    "ATLAS_SUPPLIERS",
    "ATLAS_PURCHASE_ORDERS",
    "ATLAS_AP_INVOICES",
    "ATLAS_GL_BALANCES",
})

REQUIRED_CLASSIFICATION_COLUMNS = frozenset({
    "DATA_CLASSIFICATION",
    "LAST_SYNC_DATE",
})


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

def _parse_create_tables(sql: str) -> dict[str, list[str]]:
    """Return ``{table_name: [column_name, ...]}`` for every ``CREATE TABLE``.

    Non-greedy match from ``CREATE TABLE <name> (`` to the closing
    ``);``. This is safe for the schema DDL because no inner ``)`` is
    followed by a ``;`` — the only ``);`` in the file is the table
    terminator.
    """
    tables: dict[str, list[str]] = {}
    for match in re.finditer(
        r"CREATE\s+TABLE\s+(\w+)\s*\((.*?)\)\s*;",
        sql,
        re.DOTALL | re.IGNORECASE,
    ):
        name = match.group(1).upper()
        body = match.group(2)
        tables[name] = _parse_column_names(body)
    return tables


def _parse_column_names(body: str) -> list[str]:
    """Extract column names from a ``CREATE TABLE`` column list.

    Walks the body character by character so that commas inside
    type declarations like ``NUMBER(10,2)`` don't split a column.
    """
    # Strip inline ``--`` comments before parsing — they are line-scoped.
    cleaned = re.sub(r"--[^\n]*", "", body)

    columns: list[str] = []
    depth = 0
    current: list[str] = []
    for ch in cleaned:
        if ch == "(":
            depth += 1
            current.append(ch)
        elif ch == ")":
            depth -= 1
            current.append(ch)
        elif ch == "," and depth == 0:
            columns.append("".join(current).strip())
            current = []
        else:
            current.append(ch)
    tail = "".join(current).strip()
    if tail:
        columns.append(tail)

    names: list[str] = []
    for col in columns:
        token = col.lstrip().split(None, 1)
        if not token:
            continue
        first = token[0].upper()
        # Skip table-level constraints like ``CONSTRAINT`` / ``PRIMARY KEY``
        # that happen to appear as their own list entries.
        if first in {"CONSTRAINT", "PRIMARY", "FOREIGN", "UNIQUE", "CHECK"}:
            continue
        names.append(first)
    return names


# ---------------------------------------------------------------------------
# 1. Prefix conventions
# ---------------------------------------------------------------------------

def test_all_tables_have_atlas_prefix():
    sql = SCHEMA_DDL.read_text()
    tables = _parse_create_tables(sql)
    assert tables, "parser found no tables in schema_ddl.sql"
    bad = [name for name in tables if not name.startswith("ATLAS_")]
    assert not bad, (
        f"tables without the ATLAS_ prefix (CLAUDE.md §5): {bad}"
    )


def test_all_sequences_have_seq_atlas_prefix():
    sql = SCHEMA_DDL.read_text()
    names = re.findall(
        r"CREATE\s+SEQUENCE\s+(\w+)", sql, re.IGNORECASE
    )
    assert names, "parser found no sequences in schema_ddl.sql"
    bad = [n for n in names if not n.upper().startswith("SEQ_ATLAS_")]
    assert not bad, (
        f"sequences without the SEQ_ATLAS_ prefix (CLAUDE.md §5): {bad}"
    )


def test_all_packages_end_with_pkg_suffix():
    """Every ``CREATE OR REPLACE PACKAGE`` in Atlas SQL ends in ``_PKG``."""
    offenders: list[tuple[str, str]] = []
    for sql_path in sorted(PROVISIONING_DIR.glob("*.sql")):
        text = sql_path.read_text()
        for match in re.finditer(
            r"CREATE\s+OR\s+REPLACE\s+PACKAGE(?:\s+BODY)?\s+(\w+)",
            text,
            re.IGNORECASE,
        ):
            name = match.group(1).upper()
            if not name.endswith("_PKG"):
                offenders.append((sql_path.name, name))
    assert not offenders, (
        f"packages without the _PKG suffix (CLAUDE.md §5): {offenders}"
    )


# ---------------------------------------------------------------------------
# 2. Classification columns
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("table_name", sorted(FUSION_SYNCED_TABLES))
def test_fusion_synced_tables_have_classification_columns(table_name):
    """Every Fusion-backed table carries ``DATA_CLASSIFICATION`` + ``LAST_SYNC_DATE``.

    CLAUDE.md §5 says every ``ATLAS_*`` table should follow this
    pattern. In practice the invariant is enforced for Fusion-mirror
    tables; internal tables (``ATLAS_DOCUMENTS``, ``ATLAS_AUDIT_LOG``,
    ``ATLAS_DOCUMENT_CHUNKS``) don't have ``LAST_SYNC_DATE`` because
    they're not synced from an external source-of-truth. Parametrising
    on the Fusion-synced set keeps the invariant honest without
    flagging the internal tables.
    """
    sql = SCHEMA_DDL.read_text()
    tables = _parse_create_tables(sql)
    assert table_name in tables, (
        f"expected ``{table_name}`` in schema_ddl.sql; found {sorted(tables)}"
    )
    columns = set(tables[table_name])
    missing = REQUIRED_CLASSIFICATION_COLUMNS - columns
    assert not missing, (
        f"{table_name} is missing required columns from CLAUDE.md §5: "
        f"{sorted(missing)}"
    )


# ---------------------------------------------------------------------------
# 3. ATLAS_HTTP_UTILS_PKG.MAKE_REQUEST signature
# ---------------------------------------------------------------------------

_OLD_MAKE_REQUEST_PARAMS = ("p_username", "p_password", "p_response", "p_status_code")


def _strip_sql_line_comments(sql: str) -> str:
    """Remove ``--`` line comments so they don't pollute static checks.

    CLAUDE.md's MAKE_REQUEST invariant is about the actual call sites;
    the explanatory ``-- MAKE_REQUEST is a function ...`` comment inside
    ``fusion_sync_integration.sql`` would otherwise be a false positive
    for any regex counting ``MAKE_REQUEST`` occurrences.
    """
    return re.sub(r"--[^\n]*", "", sql)


def _find_make_request_call_bodies(sql: str) -> list[str]:
    """Return the parenthesised body of each ``MAKE_REQUEST`` invocation.

    Comments are stripped first so references in prose don't count.
    Walks characters to do balanced-paren matching — safer than a
    non-greedy regex when argument expressions themselves contain
    parens (function calls, type casts, etc.).
    """
    cleaned = _strip_sql_line_comments(sql)
    bodies: list[str] = []
    pattern = re.compile(r"ATLAS_HTTP_UTILS_PKG\.MAKE_REQUEST\s*\(")
    for match in pattern.finditer(cleaned):
        start = match.end()  # position just after the opening ``(``
        depth = 1
        i = start
        while i < len(cleaned) and depth > 0:
            ch = cleaned[i]
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
            i += 1
        if depth == 0:
            bodies.append(cleaned[start : i - 1])
    return bodies


def test_fusion_sync_does_not_use_old_make_request_signature():
    """Regression guard for the MAKE_REQUEST signature mismatch.

    ``fusion_sync_integration.sql`` previously called
    ``ATLAS_HTTP_UTILS_PKG.MAKE_REQUEST`` with ``p_username`` /
    ``p_password`` / ``p_response`` / ``p_status_code`` arguments that
    do not exist on the package. The package would fail to compile.
    This test inspects each ``MAKE_REQUEST`` call body (not the whole
    file — ``p_password`` is also a legitimate parameter name on the
    ``BUILD_FUSION_AUTH_HEADERS`` helper) and fails if any of those old
    named parameters reappears at an actual call site.
    """
    sql = FUSION_SYNC.read_text()
    bodies = _find_make_request_call_bodies(sql)
    assert bodies, "no MAKE_REQUEST call sites found in fusion_sync_integration.sql"

    offenders: list[tuple[int, str]] = []
    for idx, body in enumerate(bodies):
        for param in _OLD_MAKE_REQUEST_PARAMS:
            # Word-boundary match so ``p_password`` isn't flagged by a
            # variable named ``l_fusion_password``.
            if re.search(rf"\b{param}\b", body):
                offenders.append((idx, param))
    assert not offenders, (
        f"fusion_sync_integration.sql MAKE_REQUEST call sites reference "
        f"old parameters: {offenders}. See CLAUDE.md §5 — MAKE_REQUEST "
        f"is a function taking (p_url, p_method, p_headers, p_body); the "
        f"status code is read separately via APEX_WEB_SERVICE.GET_STATUS_CODE."
    )


def test_fusion_sync_make_request_uses_current_param_names():
    """Every ``MAKE_REQUEST`` call site uses the current parameter names.

    The current package signature is ``(p_url, p_method, p_headers, p_body)``.
    Every call in ``fusion_sync_integration.sql`` uses named-argument
    form so at least ``p_url`` and ``p_method`` should be present.
    """
    sql = FUSION_SYNC.read_text()
    bodies = _find_make_request_call_bodies(sql)
    assert bodies, "no MAKE_REQUEST call sites found"
    for idx, body in enumerate(bodies):
        assert "p_url" in body, f"MAKE_REQUEST call #{idx} missing p_url: {body!r}"
        assert "p_method" in body, f"MAKE_REQUEST call #{idx} missing p_method: {body!r}"


def test_fusion_sync_reads_status_via_apex_web_service():
    """Every sync procedure reads the HTTP status via APEX_WEB_SERVICE."""
    sql = FUSION_SYNC.read_text()
    assert "APEX_WEB_SERVICE.GET_STATUS_CODE" in sql, (
        "fusion_sync_integration.sql should read the HTTP status via "
        "APEX_WEB_SERVICE.GET_STATUS_CODE (CLAUDE.md §5)."
    )


def test_fusion_sync_make_request_calls_use_function_assignment():
    """Every ``MAKE_REQUEST`` call is assigned into a variable.

    ``MAKE_REQUEST`` is a function returning the response body, not a
    procedure. Any call site should therefore appear on the right-hand
    side of a ``:=`` assignment. This catches the case where someone
    re-uses the call as a standalone procedure invocation.

    Line comments are stripped first so the explanatory comment in
    ``fusion_sync_integration.sql`` that mentions ``MAKE_REQUEST`` in
    prose isn't counted as a call site.
    """
    sql = _strip_sql_line_comments(FUSION_SYNC.read_text())
    total = len(re.findall(r"ATLAS_HTTP_UTILS_PKG\.MAKE_REQUEST", sql))
    assigned = len(
        re.findall(
            r":=\s*ATLAS_HTTP_UTILS_PKG\.MAKE_REQUEST",
            sql,
            re.DOTALL,
        )
    )
    assert total > 0, "no MAKE_REQUEST calls found in fusion_sync_integration.sql"
    assert total == assigned, (
        f"{total - assigned} MAKE_REQUEST call(s) are not assigned to a "
        f"variable. MAKE_REQUEST is a function returning the response "
        f"body; every call site must be ``l_response := "
        f"ATLAS_HTTP_UTILS_PKG.MAKE_REQUEST(...)``."
    )
