"""Parity test for the read-only SQL guard.

CLAUDE.md §5 pins a canonical list of forbidden keywords that the RAG
pipeline must block:

    INSERT, UPDATE, DELETE, DROP, ALTER, CREATE,
    TRUNCATE, MERGE, GRANT, REVOKE, EXECUTE, CALL

That list is enforced in two places:

1. ``provisioning/atlas_rag_pkg.sql`` — ``ATLAS_RAG_PKG.C_FORBIDDEN_KEYWORDS``
   constant used by the PL/SQL validator at runtime.
2. ``provisioning/deploy_rag_pipeline.py`` — the embedded
   ``ATLAS_VALIDATE_QUERY`` function DDL that gets deployed to ATP as
   the standalone validator.

If those two lists drift apart, one entry point blocks a keyword and
the other silently lets it through — exactly the class of bug that
would survive a review because each file looks fine in isolation.

This test extracts both lists via source-text regex and asserts that
the canonical CLAUDE.md set is a subset of both. The Python-side list
is allowed to be a *superset* (it currently also blocks ``DBMS_``,
``UTL_``, ``EXEC``, ``COMMIT``, ``ROLLBACK``) because defence in depth
is fine; what must not happen is a canonical keyword going missing.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

PROVISIONING_DIR = Path(__file__).resolve().parent.parent

CANONICAL_FORBIDDEN_KEYWORDS = frozenset({
    "INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE",
    "TRUNCATE", "MERGE", "GRANT", "REVOKE", "EXECUTE", "CALL",
})


def _extract_keyword_list(source: str, anchor: str) -> set[str]:
    """Pull quoted keywords out of a constructor-style list.

    ``anchor`` is a literal substring guaranteed to appear immediately
    before the list (e.g. ``C_FORBIDDEN_KEYWORDS`` or
    ``l_forbidden_keywords``). We take the text from the anchor through
    the next closing parenthesis and collect every single-quoted token.
    """
    idx = source.find(anchor)
    if idx == -1:
        pytest.fail(f"anchor {anchor!r} not found in source")
    # Find the first ``(`` after the anchor and the matching ``)``.
    open_paren = source.find("(", idx)
    close_paren = source.find(")", open_paren)
    assert open_paren != -1 and close_paren != -1, (
        f"could not find parenthesised list after {anchor!r}"
    )
    body = source[open_paren + 1 : close_paren]
    return set(re.findall(r"'([A-Za-z_]+)'", body))


def test_pl_sql_rag_package_contains_canonical_keywords():
    """``atlas_rag_pkg.sql`` must enforce the full canonical list."""
    sql_path = PROVISIONING_DIR / "atlas_rag_pkg.sql"
    source = sql_path.read_text()
    keywords = _extract_keyword_list(source, "C_FORBIDDEN_KEYWORDS CONSTANT")
    missing = CANONICAL_FORBIDDEN_KEYWORDS - keywords
    assert not missing, (
        f"atlas_rag_pkg.sql C_FORBIDDEN_KEYWORDS is missing canonical "
        f"keywords from CLAUDE.md §5: {sorted(missing)}"
    )


def test_python_deploy_validator_contains_canonical_keywords():
    """``deploy_rag_pipeline.py`` ATLAS_VALIDATE_QUERY must enforce the full list."""
    py_path = PROVISIONING_DIR / "deploy_rag_pipeline.py"
    source = py_path.read_text()
    keywords = _extract_keyword_list(source, "l_forbidden_keywords SYS.ODCIVARCHAR2LIST")
    missing = CANONICAL_FORBIDDEN_KEYWORDS - keywords
    assert not missing, (
        f"deploy_rag_pipeline.py ATLAS_VALIDATE_QUERY is missing "
        f"canonical keywords from CLAUDE.md §5: {sorted(missing)}"
    )


def test_python_and_plsql_lists_agree_on_canonical_core():
    """The intersection of both lists must equal the canonical set.

    This is the tighter parity check: whatever each side chooses to
    additionally block (defence in depth is fine), they must at minimum
    agree on the canonical 12. If one side drops ``CALL`` and the other
    keeps it, the intersection shrinks and this test fails.
    """
    rag_src = (PROVISIONING_DIR / "atlas_rag_pkg.sql").read_text()
    py_src = (PROVISIONING_DIR / "deploy_rag_pipeline.py").read_text()

    rag_keywords = _extract_keyword_list(rag_src, "C_FORBIDDEN_KEYWORDS CONSTANT")
    py_keywords = _extract_keyword_list(py_src, "l_forbidden_keywords SYS.ODCIVARCHAR2LIST")

    assert CANONICAL_FORBIDDEN_KEYWORDS <= (rag_keywords & py_keywords), (
        f"canonical keywords missing from the intersection of "
        f"atlas_rag_pkg.sql and deploy_rag_pipeline.py validators. "
        f"atlas_rag_pkg.sql: {sorted(rag_keywords)}; "
        f"deploy_rag_pipeline.py: {sorted(py_keywords)}"
    )
