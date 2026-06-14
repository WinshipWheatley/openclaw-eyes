import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import cassandra_draft_worker_wrapper as wrapper
from scripts.run_cassandra_draft_worker_wrapper import main as run_main


FIXED_NOW = "2026-05-25T20:00:00+00:00"


def test_capital_hilton_fixture_generates_candidate_draft(tmp_path, capsys):
    assert run_main(
        [
            "--fixture",
            "capital_hilton",
            "--export-root",
            str(tmp_path),
            "--generated-at",
            FIXED_NOW,
            "--format",
            "json",
        ]
    ) == 0
    payload = json.loads(capsys.readouterr().out)
    candidate = payload["draft_candidate"]

    assert payload["readback"]["status"] == "DRAFT_READY_FOR_REVIEW"
    assert candidate["draft_subject"] == "Capital Hilton Invoice Follow-Up"
    assert "Coupa supplier portal / PO process" in candidate["draft_body"]
    assert candidate["recipient_display_ref"] == "contact_ref_annette_candidate_tokenized"
    assert candidate["attachment_display_refs"] == ["artifact_ref_winship_invoice_excel_pdf_candidate"]
    assert payload["machine_proof"]["email_sent"] is False
    assert payload["machine_proof"]["repo_b_cassandra_called"] is False


def test_send_attempt_is_blocked():
    request = wrapper.make_capital_hilton_fixture_request(generated_at=FIXED_NOW)
    request = request.__class__(**{**request.__dict__, "send_authority": True})
    context = wrapper.build_context_package(request)
    status, blockers = wrapper.validate_request(request, context)

    assert status == "UNKNOWN_FAIL_CLOSED"
    assert any(blocker.blocker_type == "SEND_ATTEMPTED" for blocker in blockers)


def test_live_gmail_and_mail_access_are_blocked():
    request = wrapper.make_capital_hilton_fixture_request(generated_at=FIXED_NOW)
    boundary = dict(request.authority_boundary)
    boundary["live_gmail_access_allowed"] = True
    boundary["live_mail_access_allowed"] = True
    request = request.__class__(**{**request.__dict__, "authority_boundary": boundary})
    context = wrapper.build_context_package(request)
    _status, blockers = wrapper.validate_request(request, context)
    blocker_types = {blocker.blocker_type for blocker in blockers}

    assert "LIVE_GMAIL_ACCESS_ATTEMPTED" in blocker_types
    assert "LIVE_MAIL_ACCESS_ATTEMPTED" in blocker_types


def test_credential_raw_email_and_raw_attachment_inclusion_are_blocked():
    request = wrapper.make_capital_hilton_fixture_request(generated_at=FIXED_NOW)
    context = wrapper.build_context_package(request)
    status, blockers = wrapper.validate_request(
        request,
        context,
        extra_payload={
            "credentials": "[REDACTED_CREDENTIAL_VALUE]",
            "raw_email_body": "full message body placeholder",
            "raw_attachment_body": "full attachment body placeholder",
        },
    )
    blocker_types = {blocker.blocker_type for blocker in blockers}

    assert status == "BLOCKED_PRIVACY_BOUNDARY"
    assert "CREDENTIAL_INCLUDED" in blocker_types
    assert "RAW_EMAIL_BODY_INCLUDED" in blocker_types
    assert "RAW_ATTACHMENT_BODY_INCLUDED" in blocker_types


def test_recipient_missing_returns_missing_input_readback():
    request = wrapper.make_capital_hilton_fixture_request(generated_at=FIXED_NOW)
    request = request.__class__(**{**request.__dict__, "target_recipient_ref": ""})
    payload = wrapper.build_readback(request, generated_at=FIXED_NOW)

    assert payload["readback"]["status"] == "BLOCKED_NO_RECIPIENT"
    assert "recipient" in payload["readback"]["operator_message"].lower()
    assert payload["draft_candidate"] is None


def test_attachment_missing_returns_missing_inputs():
    request = wrapper.make_capital_hilton_fixture_request(generated_at=FIXED_NOW)
    request = request.__class__(**{**request.__dict__, "attachment_refs": ()})
    payload = wrapper.build_readback(request, generated_at=FIXED_NOW)

    assert payload["readback"]["status"] == "MISSING_INPUTS"
    assert any(item["blocker_type"] == "ATTACHMENT_REF_MISSING" for item in payload["active_blockers"])


def test_approval_boundary_appears_in_readback_and_candidate():
    payload = wrapper.build_from_fixture("capital_hilton", generated_at=FIXED_NOW)

    assert payload["readback"]["approval_required"] is True
    assert "approval" in payload["draft_candidate"]["approval_boundary_notice"].lower()
    assert "Nothing has been sent" in payload["draft_candidate"]["send_blocked_notice"]


def test_operator_markdown_is_safe_and_readable(tmp_path):
    payload = wrapper.build_from_fixture("capital_hilton", generated_at=FIXED_NOW)
    _json_path, operator_path = wrapper.write_exports(payload, tmp_path)
    text = operator_path.read_text(encoding="utf-8")

    assert "Cassandra draft ready for review" in text
    assert "No email was sent" in text
    assert "Gmail/Mail draft" in text
    assert "@example" not in text
    assert "full attachment body placeholder" not in text


def test_no_external_authority_true_except_draft_allowed(tmp_path):
    payload = wrapper.build_from_fixture("capital_hilton", generated_at=FIXED_NOW)
    wrapper.write_exports(payload, tmp_path)
    data = json.loads((tmp_path / wrapper.JSON_EXPORT_NAME).read_text(encoding="utf-8"))

    assert data["authority_boundary"]["draft_allowed"] is True
    for key, value in data["authority_boundary"].items():
        if key == "draft_allowed":
            continue
        assert value is False, key
    proof = data["machine_proof"]
    assert proof["email_sent"] is False
    assert proof["gmail_or_mail_accessed"] is False
    assert proof["gmail_or_mail_draft_created"] is False
    assert proof["telegram_output_sent"] is False
    assert proof["workflow_execution_performed"] is False
    assert proof["agent_dispatch_performed"] is False


def test_generated_outputs_have_no_raw_private_addresses_or_tokens(tmp_path):
    payload = wrapper.build_from_fixture("capital_hilton", generated_at=FIXED_NOW)
    wrapper.write_exports(payload, tmp_path)
    output_text = "\n".join(path.read_text(encoding="utf-8") for path in tmp_path.iterdir())

    assert not __import__("re").search(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b", output_text)
    assert "GMAIL_APP_PASSWORD" not in output_text
    assert "SMTP_PASSWORD" not in output_text
    assert "OPENCLAW_SEND_ALLOWED=1" not in output_text


def test_wrapper_does_not_import_or_call_live_repo_b_services():
    source = Path("cassandra_draft_worker_wrapper.py").read_text(encoding="utf-8").lower()
    forbidden = [
        "from chief_email_brain",
        "import chief_email_brain",
        "from cassandra_brain",
        "import cassandra_brain",
        "google.gmail.send",
        "smtplib",
        "imaplib",
        "poplib",
        "requests.",
        "httpx.",
        "urllib.request",
        "webbrowser",
        "selenium",
        "playwright",
        "send_message(",
        "request_approval(",
    ]
    for token in forbidden:
        assert token not in source
