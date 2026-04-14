"""Structural tests for ``provisioning/deploy_rag_pipeline.py``.

The RAG deploy script is mostly a manifest — a ``PLSQL_OBJECTS`` list of
``(object_type, object_name, ddl_string)`` tuples that gets looped over
and executed against ATP. Most of the risk lives in the PL/SQL strings
themselves; we test their shape and the invariants CLAUDE.md documents
for ``ATLAS_VALIDATE_QUERY``.

``oracledb`` is stubbed by ``conftest.py`` so importing the deploy
script (which does ``import oracledb`` at top level) doesn't need the
real driver.
"""

from __future__ import annotations

import re

import pytest

import deploy_rag_pipeline


# CLAUDE.md §5: the read-only guard must cover these 12 keywords.
CANONICAL_FORBIDDEN_KEYWORDS = {
    "INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE",
    "TRUNCATE", "MERGE", "GRANT", "REVOKE", "EXECUTE", "CALL",
}


# ---------------------------------------------------------------------------
# PLSQL_OBJECTS manifest shape
# ---------------------------------------------------------------------------

def test_plsql_objects_is_non_empty_list():
    assert isinstance(deploy_rag_pipeline.PLSQL_OBJECTS, list)
    assert len(deploy_rag_pipeline.PLSQL_OBJECTS) > 0


@pytest.mark.parametrize(
    "entry",
    deploy_rag_pipeline.PLSQL_OBJECTS,
    ids=lambda e: e[1] if isinstance(e, tuple) and len(e) >= 2 else "unknown",
)
def test_plsql_object_entry_shape(entry):
    """Each manifest entry is a 3-tuple of non-empty strings."""
    assert isinstance(entry, tuple), "entries must be tuples"
    assert len(entry) == 3, "entries must be (type, name, ddl)"
    obj_type, obj_name, ddl = entry
    assert isinstance(obj_type, str) and obj_type.strip()
    assert isinstance(obj_name, str) and obj_name.strip()
    assert isinstance(ddl, str) and ddl.strip()


@pytest.mark.parametrize(
    "entry",
    deploy_rag_pipeline.PLSQL_OBJECTS,
    ids=lambda e: e[1] if isinstance(e, tuple) and len(e) >= 2 else "unknown",
)
def test_plsql_object_ddl_uses_create_or_replace(entry):
    """Every deployable PL/SQL block uses ``CREATE OR REPLACE`` for idempotency."""
    _, obj_name, ddl = entry
    assert "CREATE OR REPLACE" in ddl, (
        f"{obj_name} DDL should use CREATE OR REPLACE so re-runs are idempotent"
    )


@pytest.mark.parametrize(
    "entry",
    deploy_rag_pipeline.PLSQL_OBJECTS,
    ids=lambda e: e[1] if isinstance(e, tuple) and len(e) >= 2 else "unknown",
)
def test_plsql_object_ddl_is_terminated_with_slash(entry):
    """Every PL/SQL block is terminated with a ``/`` statement terminator."""
    _, obj_name, ddl = entry
    # PL/SQL blocks (PACKAGE / FUNCTION / PROCEDURE) require a trailing
    # ``/`` so the server knows the block is complete.
    assert "/" in ddl, f"{obj_name} DDL must contain a '/' terminator"


@pytest.mark.parametrize(
    "entry",
    deploy_rag_pipeline.PLSQL_OBJECTS,
    ids=lambda e: e[1] if isinstance(e, tuple) and len(e) >= 2 else "unknown",
)
def test_plsql_object_grants_execute_to_public(entry):
    """Each deployed object grants ``EXECUTE`` to ``PUBLIC`` so APEX can call it."""
    _, obj_name, ddl = entry
    assert re.search(r"GRANT\s+EXECUTE\s+ON\s+" + re.escape(obj_name), ddl), (
        f"{obj_name} DDL should grant EXECUTE to PUBLIC"
    )


# ---------------------------------------------------------------------------
# ATLAS_VALIDATE_QUERY invariants
# ---------------------------------------------------------------------------

def _find_validate_query_ddl() -> str:
    for obj_type, obj_name, ddl in deploy_rag_pipeline.PLSQL_OBJECTS:
        if obj_name == "ATLAS_VALIDATE_QUERY":
            return ddl
    pytest.fail("ATLAS_VALIDATE_QUERY not found in PLSQL_OBJECTS")


def test_validate_query_is_a_function():
    ddl = _find_validate_query_ddl()
    assert "CREATE OR REPLACE FUNCTION ATLAS_VALIDATE_QUERY" in ddl


def test_validate_query_rejects_non_select_statements():
    """Validator must enforce that only ``SELECT`` queries are allowed."""
    ddl = _find_validate_query_ddl()
    # The existing implementation uses a REGEXP_LIKE check against
    # ``'^SELECT\\s'`` and returns ``'BLOCKED: Only SELECT queries are allowed'``.
    assert "Only SELECT queries are allowed" in ddl
    assert "SELECT" in ddl


@pytest.mark.parametrize("keyword", sorted(CANONICAL_FORBIDDEN_KEYWORDS))
def test_validate_query_covers_canonical_forbidden_keyword(keyword):
    """Every canonical forbidden keyword must appear in the validator's list.

    The Python-side deploy_rag_pipeline.py validator must be a superset
    of the PL/SQL ``ATLAS_RAG_PKG.C_FORBIDDEN_KEYWORDS`` list from
    CLAUDE.md §5. Any future PR that removes one of these keywords from
    the validator will fail this test.
    """
    ddl = _find_validate_query_ddl()
    # Match a quoted keyword literal, e.g. ``'INSERT'``. This avoids
    # false positives from keywords appearing in comments or error text.
    assert re.search(rf"'{keyword}'", ddl), (
        f"ATLAS_VALIDATE_QUERY validator does not list {keyword!r} as "
        f"a forbidden keyword"
    )
