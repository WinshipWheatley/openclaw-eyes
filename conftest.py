"""Repository-level pytest collection and isolation rules."""

from __future__ import annotations

from pathlib import Path
import importlib.util
import sys
import types

from openclaw_pytest_sandbox import install_pytest_sandbox

# Archived planning docs contain copied historical test files with names that
# collide with canonical tests under ./tests. Keep full-suite collection on live
# tests and ignore docs as artifacts.
collect_ignore = ["test_effect_adapters.py"]
collect_ignore_glob = ["docs/**"]


_REPO_ROOT = Path(__file__).resolve().parent
PYTEST_SANDBOX = install_pytest_sandbox(_REPO_ROOT)


def _install_capital_hilton_agency_status_test_stub() -> None:
    """Keep clean-room pytest collection free of untracked finance/client data.

    The live module exists on the host but contains client invoice/payment-watch
    details that must not be copied into feature branches just to satisfy test
    imports. Runtime checkouts should provide the real module; tests get this
    redacted no-action stub.
    """

    if "capital_hilton_agency_status" in sys.modules:
        return
    if importlib.util.find_spec("capital_hilton_agency_status") is not None:
        return
    module = types.ModuleType("capital_hilton_agency_status")

    def _redacted_answer(query: str) -> str | None:
        text = str(query or "").lower()
        agency_terms = (
            "capital hilton agency status",
            "capital hilton openclaw status",
            "openclaw autonomously completing the capital hilton",
        )
        if not any(term in text for term in agency_terms):
            return None
        return (
            "Capital Hilton agency status is redacted in clean-room tests. "
            "No payment, ledger, send, or external-action claim is made by this stub."
        )

    module.format_capital_hilton_agency_answer = _redacted_answer
    module.format_capital_hilton_openclaw_status_answer = _redacted_answer
    sys.modules[module.__name__] = module


_install_capital_hilton_agency_status_test_stub()


def _install_reynolds_gig_setup_status_test_stub() -> None:
    """Redacted clean-room substitute for the untracked Reynolds gig module."""

    if "reynolds_gig_setup_status" in sys.modules:
        return
    module = types.ModuleType("reynolds_gig_setup_status")

    def _is_query(query: str) -> bool:
        text = str(query or "").lower()
        return "reynolds" in text and any(term in text for term in ("setup status", "gig setup", "all set"))

    def _answer(query: str) -> str | None:
        if not _is_query(query):
            return None
        return (
            "Reynolds gig setup status is redacted in clean-room tests. "
            "No email, invoice, payment, calendar, contact, ledger, or external-action claim is made by this stub."
        )

    module.is_reynolds_gig_setup_query = _is_query
    module.format_reynolds_gig_setup_answer = _answer
    sys.modules[module.__name__] = module


_install_reynolds_gig_setup_status_test_stub()


def pytest_pycollect_makemodule(module_path, parent):
    PYTEST_SANDBOX.enforce_import_path()
    return None


def pytest_runtest_setup(item):
    PYTEST_SANDBOX.enforce_import_path()
