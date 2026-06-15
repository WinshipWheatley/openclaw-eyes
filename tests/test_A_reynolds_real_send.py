import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from agent_work_packet import AGENT_WORK_PACKET_VERSION, init_agent_work_packet_schema
from email_send_executor import (
    build_reynolds_email_payload,
    execute_email_send_packet,
    preview_email_send_payload,
)
from invoice_send_executor import (
    INVOICE_DELIVERY_MODE_BRANDED_PDF_VIA_SQUARE,
    execute_invoice_send_packet,
)


def _seed_agent_work_packet(
    db_path: Path,
    *,
    packet_id: str,
    surface: str,
    execution_allowed: bool,
) -> None:
    init_agent_work_packet_schema(db_path)
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    run_id = f"run_{packet_id}"
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            """
INSERT INTO agent_work_packet_runs (
  run_id, packet_version, created_at, completed_at, packet_count,
  execution_allowed, agent_activation_allowed, model_call_allowed,
  tool_execution_allowed, network_authority, approval_bypass_allowed,
  action_created, file_move_allowed, file_delete_allowed, notes
) VALUES (?, ?, ?, ?, 1, ?, 0, 0, 0, 0, 0, 0, 0, 0, ?)
""".strip(),
            (
                run_id,
                AGENT_WORK_PACKET_VERSION,
                now,
                now,
                1 if execution_allowed else 0,
                "Lane A Reynolds send test packet.",
            ),
        )
        conn.execute(
            """
INSERT INTO agent_work_packets (
  packet_id, run_id, source_intent_id, source_intent_preview,
  routed_agent_id, routed_lane_id, world_hint, intent_category, goal,
  status, approval_required, execution_allowed, action_created,
  candidate_action_type, rollback_required_for_future_action,
  exact_next_prompt_text, prompt_char_count, raw_private_content_included,
  no_go_raw_access_allowed, file_move_allowed, file_delete_allowed, created_at
) VALUES (?, ?, NULL, ?, 'chief', 'outbound', 'music', ?, ?, ?, 1, ?, 0, ?, 1, ?, ?, 0, 0, 0, 0, ?)
""".strip(),
            (
                packet_id,
                run_id,
                "Reynolds Tavern send packet",
                surface,
                "Send Reynolds Tavern outbound packet after final approval.",
                "approved" if execution_allowed else "draft",
                1 if execution_allowed else 0,
                surface,
                "Final-send approval was granted for this test packet.",
                len("Final-send approval was granted for this test packet."),
                now,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def _email_payload() -> dict[str, object]:
    return {
        "to": "Sally <reservations@reynoldstavern.com>",
        "subject": "June 27 music at Reynolds Tavern",
        "body": "Hi Sally,\n\nApproved preview body.",
        "attachment_path": None,
    }


def test_send_hold_present_blocks_before_gmail_call(tmp_path):
    db_path = tmp_path / "ledger.sqlite"
    hold_path = tmp_path / "SEND_HOLD.md"
    hold_path.write_text("absolute hold\n", encoding="utf-8")
    _seed_agent_work_packet(
        db_path,
        packet_id="reynolds-email-approved-held",
        surface="email_send",
        execution_allowed=True,
    )
    calls = []

    def sender(**kwargs):
        calls.append(kwargs)
        return {"ok": True, "data": {"message_id": "gmail-should-not-run"}, "error": ""}

    receipt = execute_email_send_packet(
        packet_id="reynolds-email-approved-held",
        db_path=str(db_path),
        send_hold_path=hold_path,
        outbound_payload=_email_payload(),
        email_sender=sender,
    )

    assert receipt.ok is False
    assert calls == []
    assert receipt.meta["send_hold_active"] is True
    assert receipt.meta["gmail_api_called"] is False
    assert receipt.meta["external_send_performed"] is False


def test_approved_no_hold_invokes_gmail_broker_sender(tmp_path):
    db_path = tmp_path / "ledger.sqlite"
    hold_path = tmp_path / "missing_SEND_HOLD.md"
    _seed_agent_work_packet(
        db_path,
        packet_id="reynolds-email-approved-live",
        surface="email_send",
        execution_allowed=True,
    )
    calls = []
    payload = _email_payload()

    def sender(**kwargs):
        calls.append(kwargs)
        return {"ok": True, "data": {"message_id": "gmail-mock-1"}, "error": ""}

    receipt = execute_email_send_packet(
        packet_id="reynolds-email-approved-live",
        db_path=str(db_path),
        send_hold_path=hold_path,
        outbound_payload=payload,
        email_sender=sender,
    )

    assert receipt.ok is True
    assert receipt.meta["email_send_performed"] is True
    assert receipt.meta["gmail_api_called"] is True
    assert receipt.meta["external_send_performed"] is True
    assert receipt.meta["outbound_payload"] == payload
    assert len(calls) == 1
    assert {key: calls[0][key] for key in payload} == payload
    assert calls[0]["packet_id"] == "reynolds-email-approved-live"


def test_email_preview_returns_exact_outbound_payload(tmp_path):
    payload = _email_payload() | {
        "attachment_path": "artifacts/reynolds/Winship_Wheatley_Reynolds_Tavern_2026-06-27_invoice.pdf"
    }

    receipt = preview_email_send_payload(
        payload,
        packet_id="reynolds-email-preview",
        db_path=str(tmp_path / "ledger.sqlite"),
    )

    assert receipt.ok is True
    assert receipt.meta["preview_only"] is True
    assert receipt.meta["outbound_payload"] == payload
    assert receipt.meta["gmail_api_called"] is False
    assert receipt.meta["external_send_performed"] is False


def test_build_reynolds_email_payload_from_approved_draft(tmp_path):
    draft_path = tmp_path / "intro_email_draft.md"
    draft_path.write_text(
        """# Draft

Status: draft only
To: Sally <reservations@reynoldstavern.com>
From: Winship Wheatley <winshiplive@gmail.com>
Subject: June 27 music at Reynolds Tavern

Hi Sally,

Mike Heuer asked me to cover his Reynolds Tavern date.

Best,
Winship Wheatley

## Approval Notes

- Nothing sent.
""",
        encoding="utf-8",
    )

    payload = build_reynolds_email_payload(draft_path=draft_path)

    assert payload == {
        "to": "Sally <reservations@reynoldstavern.com>",
        "subject": "June 27 music at Reynolds Tavern",
        "body": "Hi Sally,\n\nMike Heuer asked me to cover his Reynolds Tavern date.\n\nBest,\nWinship Wheatley",
        "attachment_path": None,
    }


def test_invoice_preview_accepts_rendered_pdf_path_for_branded_square(tmp_path):
    pdf_path = "artifacts/reynolds/Winship_Wheatley_Reynolds_Tavern_2026-06-27_invoice.pdf"

    receipt = execute_invoice_send_packet(
        packet_id="reynolds-invoice-preview",
        db_path=str(tmp_path / "ledger.sqlite"),
        preview_only=True,
        rendered_pdf_path=pdf_path,
    )

    assert receipt.ok is True
    assert receipt.meta["preview_only"] is True
    assert receipt.meta["delivery_mode"] == INVOICE_DELIVERY_MODE_BRANDED_PDF_VIA_SQUARE
    assert receipt.meta["outbound_payload"]["attachment_path"] == pdf_path
    assert receipt.meta["square_api_called"] is False
    assert receipt.meta["external_send_performed"] is False


def test_approved_invoice_branded_square_invokes_injected_sender(tmp_path):
    db_path = tmp_path / "ledger.sqlite"
    hold_path = tmp_path / "missing_SEND_HOLD.md"
    pdf_path = "artifacts/reynolds/Winship_Wheatley_Reynolds_Tavern_2026-06-27_invoice.pdf"
    _seed_agent_work_packet(
        db_path,
        packet_id="reynolds-invoice-approved",
        surface="invoice_send",
        execution_allowed=True,
    )
    calls = []

    def square_sender(**kwargs):
        calls.append(kwargs)
        return {"ok": True, "data": {"invoice_id": "square-invoice-mock-1"}, "error": ""}

    receipt = execute_invoice_send_packet(
        packet_id="reynolds-invoice-approved",
        db_path=str(db_path),
        send_hold_path=hold_path,
        delivery_mode=INVOICE_DELIVERY_MODE_BRANDED_PDF_VIA_SQUARE,
        rendered_pdf_path=pdf_path,
        square_sender=square_sender,
    )

    assert receipt.ok is True
    assert receipt.meta["delivery_mode"] == INVOICE_DELIVERY_MODE_BRANDED_PDF_VIA_SQUARE
    assert receipt.meta["outbound_payload"]["attachment_path"] == pdf_path
    assert receipt.meta["square_api_called"] is True
    assert receipt.meta["external_send_performed"] is True
    assert len(calls) == 1
    assert calls[0]["attachment_path"] == pdf_path
