"""
Drift-detection tests for ``provisioning.config.Config``.

These tests exist because every Atlas provisioning script imports the
``Config`` class and reads attributes off it at module import time. If a
script references a property that ``Config`` does not define, the import
itself raises ``AttributeError`` and the deployment fails before the user
ever sees a useful error.

Strategy
--------
Rather than hand-listing every expected attribute, we statically parse all
sibling ``provisioning/*.py`` files with ``ast`` and collect every
attribute access of the form ``config.X`` or ``Config.X``. We then assert
that ``Config`` actually exposes each of those names. This keeps the tests
in sync automatically: any future script that references a new config
attribute is checked the moment it lands.

We also exercise the env-var override path to make sure ``os.getenv``
defaults can be replaced at runtime.
"""

import ast
import importlib
import os
import sys
from pathlib import Path

import pytest

PROVISIONING_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = PROVISIONING_DIR.parent

# Make ``import config`` resolve to provisioning/config.py regardless of
# how pytest is invoked.
if str(PROVISIONING_DIR) not in sys.path:
    sys.path.insert(0, str(PROVISIONING_DIR))


def _load_config_module():
    """Import (or re-import) provisioning/config.py as a fresh module."""
    if "config" in sys.modules:
        del sys.modules["config"]
    return importlib.import_module("config")


def _collect_config_attribute_references(py_file: Path) -> set[str]:
    """Return the set of attribute names accessed on ``config`` / ``Config``.

    Picks up patterns like ``config.DB_USER``, ``Config.DB_USER`` and
    ``cfg.DB_USER`` when ``cfg`` is a known alias for the config module.
    """
    source = py_file.read_text()
    tree = ast.parse(source, filename=str(py_file))

    # Find local aliases for the config module: ``import config as cfg``
    # or ``from provisioning import config as cfg``. We always treat the
    # bare names ``config`` and ``Config`` as roots too.
    aliases: set[str] = {"config", "Config"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.endswith("config") and alias.asname:
                    aliases.add(alias.asname)
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name == "config" or alias.name == "Config":
                    aliases.add(alias.asname or alias.name)

    refs: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            if node.value.id in aliases:
                refs.add(node.attr)
    return refs


def _provisioning_python_files() -> list[Path]:
    return sorted(
        p for p in PROVISIONING_DIR.glob("*.py") if p.name != "config.py"
    )


def test_config_module_imports_cleanly():
    """Importing ``config`` must not raise."""
    mod = _load_config_module()
    assert hasattr(mod, "Config")


@pytest.mark.parametrize(
    "script_path",
    _provisioning_python_files(),
    ids=lambda p: p.name,
)
def test_sibling_scripts_only_reference_existing_config_attributes(script_path):
    """Every ``config.X`` referenced by a provisioning script must exist.

    This is the regression test for the bugs surfaced by the test-coverage
    analysis: ``deploy_fusion_integration.py``, ``deploy_rag_pipeline.py``
    and ``setup_apex.py`` all referenced ``DB_WALLET_DIR``,
    ``DB_WALLET_PASSWORD`` and (in one case) ``OCI_REGION``, none of which
    were defined on ``Config``.
    """
    mod = _load_config_module()
    referenced = _collect_config_attribute_references(script_path)

    missing = sorted(name for name in referenced if not hasattr(mod.Config, name))
    assert not missing, (
        f"{script_path.name} references config attributes that do not exist "
        f"on provisioning.config.Config: {missing}"
    )


def test_env_var_override_is_picked_up(monkeypatch):
    """``os.getenv`` defaults must be overridable at process start."""
    monkeypatch.setenv("DB_USER", "CUSTOM_USER")
    monkeypatch.setenv("OCI_REGION", "us-ashburn-1")
    monkeypatch.setenv("DB_WALLET_DIR", "/tmp/custom_wallet")

    mod = _load_config_module()
    assert mod.Config.DB_USER == "CUSTOM_USER"
    assert mod.Config.OCI_REGION == "us-ashburn-1"
    assert mod.Config.DB_WALLET_DIR == "/tmp/custom_wallet"


def test_wallet_dir_defaults_to_wallet_path(monkeypatch):
    """``DB_WALLET_DIR`` should fall back to ``DB_WALLET_PATH`` when unset.

    The two attribute names exist for historical reasons: newer scripts
    use ``DB_WALLET_DIR``, older code uses ``DB_WALLET_PATH``. Keeping them
    in sync prevents a deployment from connecting with one path while
    looking up the wallet at another.
    """
    monkeypatch.delenv("DB_WALLET_DIR", raising=False)
    monkeypatch.setenv("DB_WALLET_PATH", "/var/atlas/wallet")

    mod = _load_config_module()
    assert mod.Config.DB_WALLET_PATH == "/var/atlas/wallet"
    assert mod.Config.DB_WALLET_DIR == "/var/atlas/wallet"


def test_use_wallet_is_boolean_coerced(monkeypatch):
    """``USE_WALLET`` is a string env var; the class must coerce to bool."""
    monkeypatch.setenv("USE_WALLET", "True")
    assert _load_config_module().Config.USE_WALLET is True

    monkeypatch.setenv("USE_WALLET", "false")
    assert _load_config_module().Config.USE_WALLET is False
