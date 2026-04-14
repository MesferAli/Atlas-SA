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
that the attribute actually exists on the right target:

* If a script does ``from config import Config`` and then writes
  ``Config.DB_USER``, the attribute must live on the ``Config`` class.
* If a script does ``import config`` and then writes ``config.DB_USER``,
  the attribute must live on the ``config`` module itself. This
  distinction matters because past PRs shipped scripts using the bare
  ``import config`` form against attributes that only existed on the
  class, producing an ``AttributeError`` at import time.

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


def _collect_config_attribute_references(
    py_file: Path,
) -> tuple[set[str], set[str]]:
    """Return ``(module_refs, class_refs)`` for a provisioning script.

    * ``module_refs`` — names accessed on the ``config`` module itself
      (either via ``import config`` or an aliased module import). These
      must exist as module-level attributes.
    * ``class_refs`` — names accessed on the ``Config`` class (either via
      ``from config import Config`` or an alias). These must exist as
      class attributes.

    The two sets are kept separate so a script that writes
    ``config.DB_USER`` (module access) is not silently approved just
    because ``Config.DB_USER`` exists as a class attribute.
    """
    source = py_file.read_text()
    tree = ast.parse(source, filename=str(py_file))

    module_aliases: set[str] = set()
    class_aliases: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                # ``import config`` or ``import config as cfg``
                if alias.name == "config" or alias.name.endswith(".config"):
                    module_aliases.add(alias.asname or "config")
        elif isinstance(node, ast.ImportFrom):
            if node.module == "config":
                for alias in node.names:
                    # ``from config import Config`` → class alias
                    if alias.name == "Config":
                        class_aliases.add(alias.asname or "Config")
                    # ``from config import DB_USER`` — direct name import,
                    # not an attribute access, so it does not contribute
                    # to either set. It will fail at import time on its
                    # own if the name is missing.

    module_refs: set[str] = set()
    class_refs: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            base = node.value.id
            if base in module_aliases:
                module_refs.add(node.attr)
            elif base in class_aliases:
                class_refs.add(node.attr)
    return module_refs, class_refs


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
    """Every ``config.X`` / ``Config.X`` reference must exist on the right target.

    Regression test for two bug classes:

    1. *Class-attribute drift* — scripts that do
       ``from config import Config`` and then read
       ``Config.DB_WALLET_DIR`` / ``Config.DB_WALLET_PASSWORD`` /
       ``Config.OCI_REGION`` when those attributes don't exist on
       ``Config``. This was the original failure mode.

    2. *Module-vs-class confusion* — scripts that do
       ``import config`` and then read ``config.DB_USER`` as a module
       attribute. ``config.py`` only defines the ``Config`` class, so
       ``config.DB_USER`` raises ``AttributeError`` at import time. This
       test previously approved these scripts incorrectly because it
       conflated module access with class access.
    """
    mod = _load_config_module()
    module_refs, class_refs = _collect_config_attribute_references(script_path)

    missing_class = sorted(n for n in class_refs if not hasattr(mod.Config, n))
    assert not missing_class, (
        f"{script_path.name} references Config.X attributes that do not "
        f"exist on provisioning.config.Config: {missing_class}"
    )

    missing_module = sorted(n for n in module_refs if not hasattr(mod, n))
    assert not missing_module, (
        f"{script_path.name} references config.X as module-level "
        f"attributes that do not exist on provisioning.config: "
        f"{missing_module}. Either switch to 'from config import Config' "
        f"+ 'Config.{missing_module[0]}' or add a module-level alias."
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
