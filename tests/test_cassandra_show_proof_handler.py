import json
from pathlib import Path

import cassandra_show_proof_handler as handler
import cassandra_telegram_delivery as delivery


def _draft(path: Path) -> Path:
    path.write_text(
        """# Reynolds Tavern Intro Email Draft

Status: draft only; not sent
To: Sally <reservations@reynoldstavern.com>
From: Winship Wheatley <winshiplive@gmail.com>
Subject: June 27 music at Reynolds Tavern

Hi Sally,

Mike Heuer asked me to cover his Reynolds Tavern date on Friday, June 27, from 7-10pm.

Best,

Winship Wheatley

## Approval Notes

- Draft only. Nothing has been sent.
""",
        encoding="utf-8",
    )
    return path


def test_show_proof_intent_matches_operator_phrases():
    assert handler.is_show_proof_intent("show me the proof")
    assert handler.is_show_proof_intent("show the Reynolds package")
    assert handler.is_show_proof_intent("show me the invoice")
    assert handler.is_show_proof_intent("can I see the reynolds invoice?")
    assert not handler.is_show_proof_intent("send the invoice")


def test_show_proof_response_carries_draft_and_quicklook_artifact_and_dry_runs_telegram(tmp_path):
    draft_path = _draft(tmp_path / "intro_email_draft.md")
    app_pdf_path = "/Volumes/openclaw_e/orchestration/artifacts/reynolds/Winship_Wheatley_Reynolds_Tavern_2026-06-27_invoice.pdf"
    telegram_pdf_path = tmp_path / "Winship_Wheatley_Reynolds_Tavern_2026-06-27_invoice.pdf"
    telegram_pdf_path.write_bytes(b"%PDF-1.4 fixture\n")
    log_path = tmp_path / "telegram_dryrun.jsonl"

    response = handler.handle_show_proof_intent(
        "show me the Reynolds invoice",
        draft_path=draft_path,
        app_invoice_pdf_path=app_pdf_path,
        telegram_invoice_pdf_path=telegram_pdf_path,
        env={},
        toggle_path=tmp_path / "missing_toggle.flag",
        dry_run_log_path=log_path,
    )

    assert response.status == "reynolds_proof_ready_for_review"
    assert response.intent_matched is True
    assert "To: Sally <reservations@reynoldstavern.com>" in response.draft_email_text
    assert "Subject: June 27 music at Reynolds Tavern" in response.draft_email_text
    assert "Mike Heuer asked me" in response.draft_email_text
    assert "Approval Notes" not in response.draft_email_text
    assert response.client_send_performed is False
    assert response.external_client_send_performed is False
    assert response.email_send_performed is False
    assert response.send_hold_touched is False

    artifact = response.proof_artifacts[0]
    assert artifact["artifact_type"] == "proof_pdf"
    assert artifact["role"] == "invoice_pdf"
    assert artifact["path"] == app_pdf_path
    assert artifact["telegram_document_path"] == str(telegram_pdf_path)
    assert artifact["presentation"] == {
        "presenter": "ProofPresenter",
        "mode": "quicklook",
        "should_open": True,
    }
    assert artifact["review_only"] is True
    assert artifact["client_send_allowed"] is False

    assert response.telegram_text_receipt["status"] == "dry_run_logged_toggle_off"
    assert response.telegram_text_receipt["sent"] is False
    assert response.telegram_text_receipt["telegram_send_attempted"] is False
    assert response.telegram_document_receipt["status"] == "dry_run_logged_toggle_off"
    assert response.telegram_document_receipt["sent"] is False
    assert response.telegram_document_receipt["telegram_send_attempted"] is False
    assert response.telegram_document_receipt["document_exists"] is True

    log_lines = log_path.read_text(encoding="utf-8").splitlines()
    assert len(log_lines) == 2
    logged = [json.loads(line) for line in log_lines]
    assert {item["delivery_kind"] for item in logged} == {
        "reynolds_show_proof_draft_text",
        "reynolds_show_proof_invoice_document",
    }
    assert all(item["external_client_send_performed"] is False for item in logged)
    assert all(item["send_hold_touched"] is False for item in logged)


def test_show_proof_telegram_sends_text_and_document_when_toggle_enabled(tmp_path):
    draft_path = _draft(tmp_path / "intro_email_draft.md")
    pdf_path = tmp_path / "invoice.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 fixture\n")
    toggle_path = tmp_path / "telegram_enabled.flag"
    toggle_path.write_text("enabled\n", encoding="utf-8")
    text_calls = []
    document_calls = []

    def fake_text_sender(text, *, chat_id):
        text_calls.append({"text": text, "chat_id": chat_id})

    def fake_document_sender(document_path, *, chat_id, caption):
        document_calls.append({"document_path": document_path, "chat_id": chat_id, "caption": caption})

    response = handler.handle_show_proof_intent(
        "show me the proof",
        draft_path=draft_path,
        app_invoice_pdf_path="/Volumes/openclaw_e/orchestration/artifacts/reynolds/invoice.pdf",
        telegram_invoice_pdf_path=pdf_path,
        env={delivery.AUTHORIZED_USER_ID_ENV_VAR: "123456"},
        toggle_path=toggle_path,
        dry_run_log_path=tmp_path / "telegram_dryrun.jsonl",
        telegram_sender=fake_text_sender,
        telegram_document_sender=fake_document_sender,
    )

    assert response.telegram_text_receipt["status"] == "sent_to_authorized_telegram"
    assert response.telegram_text_receipt["sent"] is True
    assert response.telegram_document_receipt["status"] == "sent_document_to_authorized_telegram"
    assert response.telegram_document_receipt["sent"] is True
    assert text_calls == [{"text": response.draft_email_text, "chat_id": "123456"}]
    assert document_calls == [
        {
            "document_path": str(pdf_path),
            "chat_id": "123456",
            "caption": "Reynolds Tavern invoice proof for review only. No client send.",
        }
    ]
    assert "123456" not in json.dumps(response.to_dict(), sort_keys=True)
    assert response.external_client_send_performed is False
    assert response.send_hold_touched is False


def test_non_show_proof_intent_does_not_trigger_telegram(tmp_path):
    calls = []

    def fake_sender(text, *, chat_id):
        calls.append((text, chat_id))

    response = handler.handle_show_proof_intent(
        "what changed in the lane?",
        draft_path=tmp_path / "missing.md",
        env={delivery.AUTHORIZED_USER_ID_ENV_VAR: "123456"},
        telegram_sender=fake_sender,
    )

    assert response.status == "not_show_proof_intent"
    assert response.intent_matched is False
    assert response.proof_artifacts == ()
    assert response.telegram_text_receipt is None
    assert response.telegram_document_receipt is None
    assert calls == []
