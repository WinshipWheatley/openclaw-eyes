"""Repository-level pytest collection and isolation rules."""

from __future__ import annotations

from pathlib import Path

from openclaw_pytest_sandbox import install_pytest_sandbox

# Archived planning docs contain copied historical test files with names that
# collide with canonical tests under ./tests. Keep full-suite collection on live
# tests and ignore docs as artifacts.
collect_ignore = ["test_effect_adapters.py"]
collect_ignore_glob = ["docs/**"]


_REPO_ROOT = Path(__file__).resolve().parent
PYTEST_SANDBOX = install_pytest_sandbox(_REPO_ROOT)


def pytest_pycollect_makemodule(module_path, parent):
    PYTEST_SANDBOX.enforce_import_path()
    return None


def pytest_runtest_setup(item):
    PYTEST_SANDBOX.enforce_import_path()
