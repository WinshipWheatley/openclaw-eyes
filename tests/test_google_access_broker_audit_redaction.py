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
