import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import google_access_broker as broker


EMAIL_BODY = (
    "Hi Annette,\n\n"
    "I wanted to follow up on the Winship invoice for Capital Hilton and see "
    "whether there is any update on payment status.\n\n"
    "Thank you,\n"
    "Winship"
)


def _gmail_send_token(
    *,
    request_id: str,
    payload_hash: str,
    authority_refs: list[str] | None = None,
    credential_lease_refs: list[str] | None = None,
) -> dict:
    return broker.mint_send_hold_gated_broker_capability_token(
        agent="cassandra",
        capability="google.gmail.send",
        issuer="test_google_access_broker_audit_redaction",
        request_id=request_id,
        idempotency_key=request_id,
        payload_hash=payload_hash,
        authority_refs=authority_refs or [],
        credential_lease_refs=credential_lease_refs or [],
        send_hold_checked=True,
        send_hold_active=False,
        send_hold_ref="pytest",
    )


def _audit_entry(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8").splitlines()[-1])


def test_broker_audit_redacts_gmail_send_body_param(tmp_path, monkeypatch):
    audit_path = tmp_path / "google_access_audit.jsonl"
    monkeypatch.setattr(broker, "_AUDIT_LOG", audit_path)

    broker._audit(
        "cassandra",
        "google.gmail.send",
        {
            "to": "Annette.Sunga@hilton.com",
            "subject": "Follow-up on Winship invoice",
            "body": EMAIL_BODY,
            "approval_context": {
                "request_id": "exact_send_authority_request:fixture",
                "idempotency_key": "exact_send_authority_request:fixture",
                "objective_id": "cassandra_operator_objective:fixture",
                "payload_hash": "sha256:" + ("a" * 64),
                "authority_refs": ["authority_envelope:fixture"],
                "credential_lease_refs": ["credential_lease:fixture"],
                "body": EMAIL_BODY,
                "operator_text": EMAIL_BODY,
            },
        },
        False,
        "fixture refusal",
    )

    raw_audit = audit_path.read_text(encoding="utf-8")
    entry = _audit_entry(audit_path)
    params = entry["params"]

    assert EMAIL_BODY not in raw_audit
    assert entry["agent"] == "cassandra"
    assert entry["capability"] == "google.gmail.send"
    assert params["to"] == "Annette.Sunga@hilton.com"
    assert params["subject"] == "Follow-up on Winship invoice"
    assert "body" not in params
    assert params["approval_context_redacted"] is True
    assert params["approval_context"]["request_id"] == "exact_send_authority_request:fixture"
    assert params["approval_context"]["idempotency_key"] == "exact_send_authority_request:fixture"
    assert params["approval_context"]["payload_hash"].startswith("sha256:")
    assert params["approval_context"]["authority_refs"] == ["authority_envelope:fixture"]
    assert params["approval_context"]["credential_lease_refs"] == ["credential_lease:fixture"]
    assert "body" not in params["approval_context"]
    assert "operator_text" not in params["approval_context"]


def test_broker_audit_redacts_body_text_and_message_body(tmp_path, monkeypatch):
    audit_path = tmp_path / "google_access_audit.jsonl"
    monkeypatch.setattr(broker, "_AUDIT_LOG", audit_path)

    broker._audit(
        "cassandra",
        "google.gmail.send",
        {
            "to": "Annette.Sunga@hilton.com",
            "subject": "Follow-up on Winship invoice",
            "body_text": EMAIL_BODY,
            "message_body": {"raw": EMAIL_BODY},
            "metadata": {"message_body": EMAIL_BODY, "payload_hash": "sha256:" + ("b" * 64)},
        },
        False,
        "fixture refusal",
    )

    raw_audit = audit_path.read_text(encoding="utf-8")
    params = _audit_entry(audit_path)["params"]

    assert EMAIL_BODY not in raw_audit
    assert "body_text" not in params
    assert "message_body" not in params
    assert "message_body" not in params["metadata"]
    assert params["metadata"]["payload_hash"].startswith("sha256:")


def test_exact_send_gate_context_skips_second_broker_approval_prompt(monkeypatch):
    calls = []
    request_id = "exact_send_authority_request:fixture"
    payload_hash = "sha256:" + ("a" * 64)
    authority_refs = ["authority_envelope:fixture"]
    credential_lease_refs = ["credential_lease:fixture"]
    approval_context = {
        "exact_send_gate": True,
        "request_id": request_id,
        "idempotency_key": request_id,
        "objective_id": "cassandra_operator_objective:fixture",
        "payload_hash": payload_hash,
        "authority_refs": authority_refs,
        "credential_lease_refs": credential_lease_refs,
    }

    def approval_prompt(*args, **kwargs):
        calls.append((args, kwargs))
        raise AssertionError("broker should not request a second approval for exact-send gate context")

    monkeypatch.setattr(broker, "_request_approval", approval_prompt)
    monkeypatch.setattr(broker, "_is_configured", lambda: False)
    monkeypatch.setattr(broker, "check_gmail_broker_runtime_dependencies", lambda: {"ok": True, "missing": []})

    result = broker.call(
        "cassandra",
        "google.gmail.send",
        {
            "to": "annette@example.com",
            "subject": "Fixture",
            "body": "Fixture body",
            "idempotency_key": request_id,
            "exact_send_request_id": request_id,
            "approval_context": approval_context,
            "broker_capability_token": _gmail_send_token(
                request_id=request_id,
                payload_hash=payload_hash,
                authority_refs=authority_refs,
                credential_lease_refs=credential_lease_refs,
            ),
        },
    )

    assert calls == []
    assert result["ok"] is False
    assert "credentials not configured" in result["error"].lower()


def test_gmail_broker_runtime_dependency_preflight_imports_without_credentials(monkeypatch):
    imported_modules = []

    def fake_import(module_name):
        imported_modules.append(module_name)
        return object()

    monkeypatch.setattr(broker, "_import_runtime_dependency", fake_import)

    readiness = broker.check_gmail_broker_runtime_dependencies()

    assert readiness["ok"] is True
    assert "googleapiclient.discovery" in readiness["checked_modules"]
    assert imported_modules == readiness["checked_modules"]
    assert readiness["credentials_read"] is False
    assert readiness["google_api_called"] is False


def test_gmail_broker_readiness_reports_missing_dependency_before_approval_or_credentials(monkeypatch):
    approval_calls = []
    configured_calls = []
    request_id = "exact_send_authority_request:fixture"
    payload_hash = "sha256:" + ("a" * 64)
    authority_refs = ["authority_envelope:fixture"]
    credential_lease_refs = ["credential_lease:fixture"]
    approval_context = {
        "exact_send_gate": True,
        "request_id": request_id,
        "idempotency_key": request_id,
        "objective_id": "cassandra_operator_objective:fixture",
        "payload_hash": payload_hash,
        "authority_refs": authority_refs,
        "credential_lease_refs": credential_lease_refs,
    }

    def fake_import(module_name):
        if module_name == "googleapiclient.discovery":
            raise ModuleNotFoundError("No module named 'googleapiclient'")
        return object()

    def approval_prompt(*args, **kwargs):
        approval_calls.append((args, kwargs))
        return False

    def configured():
        configured_calls.append(True)
        return False

    monkeypatch.setattr(broker, "_import_runtime_dependency", fake_import)
    monkeypatch.setattr(broker, "_request_approval", approval_prompt)
    monkeypatch.setattr(broker, "_is_configured", configured)

    result = broker.call(
        "cassandra",
        "google.gmail.send",
        {
            "to": "annette@example.com",
            "subject": "Fixture",
            "body": "Fixture body",
            "idempotency_key": request_id,
            "exact_send_request_id": request_id,
            "approval_context": approval_context,
            "broker_capability_token": _gmail_send_token(
                request_id=request_id,
                payload_hash=payload_hash,
                authority_refs=authority_refs,
                credential_lease_refs=credential_lease_refs,
            ),
        },
    )

    assert result["ok"] is False
    assert "missing gmail broker runtime dependencies" in result["error"].lower()
    assert result["data"]["missing"][0]["module"] == "googleapiclient.discovery"
    assert result["data"]["credentials_read"] is False
    assert result["data"]["google_api_called"] is False
    assert approval_calls == []
    assert configured_calls == []
