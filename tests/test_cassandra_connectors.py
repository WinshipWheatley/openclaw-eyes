"""
tests/test_cassandra_connectors.py

Verifies that every enabled Cassandra capability flag in cassandra_capability.py
has a working underlying connector. Tests check local prerequisites only —
imports, file existence, env vars — and make NO external API calls.
"""

import importlib
import json
import os
import sys
from pathlib import Path

import pytest

# Ensure /home/openclaw is on sys.path so broker/sender modules resolve
sys.path.insert(0, "/home/openclaw")

TOKEN_FILE = Path("/home/openclaw/.google-secrets/token.json")
EXPENSE_LOG = Path("/mnt/c/OpenClaw/logs/expense_log.json")
TOOLS_ROOT = Path("/home/openclaw/tools")


# ── Helpers ────────────────────────────────────────────────────────────────────

def _import(module_name: str):
    """Import a module by name; raises ImportError on failure."""
    spec = importlib.util.find_spec(module_name)
    assert spec is not None, f"Module not found: {module_name}"
    return importlib.import_module(module_name)


def _env_var_present(var_name: str) -> bool:
    if os.environ.get(var_name):
        return True
    env_file = Path("/home/openclaw/.chief.env")
    if not env_file.exists():
        return False
    try:
        return any(
            line.strip().startswith(f"{var_name}=")
            for line in env_file.read_text(encoding="utf-8").splitlines()
        )
    except Exception:
        return False


# ── Capability: CALENDAR_CONNECTED ─────────────────────────────────────────────

def test_calendar_broker_importable():
    """google_access_broker must be importable."""
    _import("google_access_broker")


def test_calendar_token_file_exists():
    """Token file must exist at ~/.google-secrets/token.json."""
    assert TOKEN_FILE.exists(), f"Missing token file: {TOKEN_FILE}"


def test_calendar_token_file_valid_json():
    """Token file must contain valid JSON."""
    assert TOKEN_FILE.exists(), f"Missing token file: {TOKEN_FILE}"
    raw = TOKEN_FILE.read_text(encoding="utf-8")
    data = json.loads(raw)  # raises if invalid
    assert isinstance(data, dict), "token.json must be a JSON object"


# ── Capability: EMAIL_SEND_CONNECTED ──────────────────────────────────────────

def test_email_send_broker_importable():
    """google_access_broker must be importable for email send."""
    _import("google_access_broker")


def test_email_send_function_callable():
    """google_access_broker._exec_gmail_send must be callable."""
    mod = _import("google_access_broker")
    assert callable(getattr(mod, "_exec_gmail_send", None)), (
        "google_access_broker._exec_gmail_send is not callable"
    )


# ── Capability: GMAIL_METADATA_CONNECTED ──────────────────────────────────────

def test_gmail_metadata_function_callable():
    """google_access_broker._exec_gmail_read_metadata must be callable."""
    mod = _import("google_access_broker")
    assert callable(getattr(mod, "_exec_gmail_read_metadata", None)), (
        "google_access_broker._exec_gmail_read_metadata is not callable"
    )


# ── Capability: GMAIL_UNREAD_COUNT — policy + executor integrity ──────────────

def test_google_access_policy_importable():
    """google_access_policy must be importable without SyntaxError."""
    _import("google_access_policy")


def test_gmail_unread_count_in_policy():
    """google.gmail.unread_count must be present and permitted for cassandra."""
    mod = _import("google_access_policy")
    assert mod.allowed("cassandra", "google.gmail.unread_count"), (
        "google.gmail.unread_count is not permitted for cassandra in _POLICY — "
        "unread count queries will silently fall through to 'inbox unreachable' fallback"
    )
    assert mod.get_class("cassandra", "google.gmail.unread_count") == "A", (
        "google.gmail.unread_count must be CLASS_A (safe read) for cassandra"
    )


def test_gmail_unread_count_function_callable():
    """google_access_broker._exec_gmail_unread_count must be callable."""
    mod = _import("google_access_broker")
    assert callable(getattr(mod, "_exec_gmail_unread_count", None)), (
        "google_access_broker._exec_gmail_unread_count is not callable"
    )


def test_gmail_read_metadata_in_policy():
    """google.gmail.read.metadata must be present and permitted for cassandra."""
    mod = _import("google_access_policy")
    assert mod.allowed("cassandra", "google.gmail.read.metadata"), (
        "google.gmail.read.metadata not permitted for cassandra — list path broken"
    )


def test_broker_call_passes_policy_for_unread_count():
    """
    broker.call('cassandra', 'google.gmail.unread_count') must not fail at the
    policy check step. It may fail at credentials, but must NOT return
    'policy module unavailable' or 'not permitted'.
    """
    mod = _import("google_access_broker")
    result = mod.call("cassandra", "google.gmail.unread_count", {})
    assert result.get("error") != "policy module unavailable", (
        "Policy module failed to import — unread count blocked at policy check"
    )
    assert "not permitted" not in (result.get("error") or ""), (
        f"cassandra denied for google.gmail.unread_count by policy: {result['error']}"
    )
    # Allowed to fail at credentials/network — only policy step must pass


def test_broker_call_passes_policy_for_read_metadata():
    """
    broker.call('cassandra', 'google.gmail.read.metadata') must not fail at the
    policy check step.
    """
    mod = _import("google_access_broker")
    result = mod.call("cassandra", "google.gmail.read.metadata", {})
    assert result.get("error") != "policy module unavailable", (
        "Policy module failed to import — read.metadata blocked at policy check"
    )
    assert "not permitted" not in (result.get("error") or ""), (
        f"cassandra denied for google.gmail.read.metadata by policy: {result['error']}"
    )


# ── Capability: CONTACTS_CONNECTED ────────────────────────────────────────────

def test_contacts_function_callable():
    """google_access_broker._exec_contacts_read must be callable."""
    mod = _import("google_access_broker")
    assert callable(getattr(mod, "_exec_contacts_read", None)), (
        "google_access_broker._exec_contacts_read is not callable"
    )


# ── Capability: FINANCIAL_LOG_CONNECTED ───────────────────────────────────────

def test_financial_log_file_exists():
    """expense_log.json must exist at /mnt/c/OpenClaw/logs/expense_log.json."""
    assert EXPENSE_LOG.exists(), (
        f"FINANCIAL_LOG_CONNECTED is True but log file is missing: {EXPENSE_LOG}"
    )


def test_financial_log_valid_json():
    """expense_log.json must contain valid JSON (list or object)."""
    assert EXPENSE_LOG.exists(), f"Missing expense log: {EXPENSE_LOG}"
    raw = EXPENSE_LOG.read_text(encoding="utf-8").strip()
    if not raw:
        pytest.skip("expense_log.json is empty — skipping JSON validity check")
    data = json.loads(raw)  # raises if invalid
    assert isinstance(data, (list, dict)), "expense_log.json must be a JSON list or object"


# ── Capability: INVOICE_PDF_CONNECTED ─────────────────────────────────────────

def test_invoice_pdf_reportlab_importable():
    """reportlab must be importable for PDF invoice generation."""
    _import("reportlab")


# ── Capability: VOICE_NOTE_CONNECTED ──────────────────────────────────────────

def test_voice_note_sender_importable():
    """cassandra_sender must be importable."""
    _import("cassandra_sender")


def test_voice_note_send_function_callable():
    """cassandra_sender.send_voice_note must be callable."""
    mod = _import("cassandra_sender")
    assert callable(getattr(mod, "send_voice_note", None)), (
        "cassandra_sender.send_voice_note is not callable"
    )


# ── Capability: PII_VAULT_CONNECTED ───────────────────────────────────────────

def test_pii_vault_cryptography_importable():
    """cryptography module must be importable for PII vault."""
    _import("cryptography")


def test_pii_vault_key_env_var_present():
    """PII_VAULT_KEY must be set in environment or .chief.env."""
    assert _env_var_present("PII_VAULT_KEY"), (
        "PII_VAULT_CONNECTED is True but PII_VAULT_KEY is not set in env or .chief.env"
    )


# ── Capability: FUTURE_ACTION_CONNECTED ───────────────────────────────────────

def test_future_action_tool_file_exists():
    """tools/future_action_queue.py must exist."""
    path = TOOLS_ROOT / "future_action_queue.py"
    assert path.exists(), f"Missing tool file: {path}"


def test_future_action_tool_importable():
    """tools/future_action_queue.py must be importable."""
    sys.path.insert(0, str(TOOLS_ROOT.parent))
    mod = importlib.import_module("tools.future_action_queue")
    assert mod is not None


# ── Capability: FILE_VERIFY_CONNECTED ─────────────────────────────────────────

def test_file_verify_tool_file_exists():
    """tools/file_verify.py must exist."""
    path = TOOLS_ROOT / "file_verify.py"
    assert path.exists(), f"Missing tool file: {path}"


def test_file_verify_tool_importable():
    """tools/file_verify.py must be importable."""
    sys.path.insert(0, str(TOOLS_ROOT.parent))
    mod = importlib.import_module("tools.file_verify")
    assert mod is not None
