import importlib
import inspect
import sqlite3
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _clear_send_mode(monkeypatch):
    monkeypatch.delenv("CASSANDRA_NO_SEND_RELOAD_GUARD", raising=False)
    monkeypatch.delenv("OPENCLAW_CASSANDRA_NO_SEND_RELOAD_GUARD", raising=False)
    monkeypatch.delenv("CASSANDRA_INTERNAL_BRIEF_CARVEOUT", raising=False)
    monkeypatch.delenv("OPENCLAW_CASSANDRA_INTERNAL_BRIEF_CARVEOUT", raising=False)
    monkeypatch.delenv("CASSANDRA_SEND_CAPABLE_MODE", raising=False)
    monkeypatch.delenv("OPENCLAW_CASSANDRA_SEND_CAPABLE_MODE", raising=False)


def _enable_guard_and_carveout(monkeypatch):
    _clear_send_mode(monkeypatch)
    monkeypatch.setenv("OPENCLAW_TEST_MODE", "1")
    monkeypatch.setenv("OPENCLAW_SEND_HOLD", "1")
    monkeypatch.setenv("CASSANDRA_NO_SEND_RELOAD_GUARD", "1")
    monkeypatch.setenv("CASSANDRA_SEND_CAPABLE_MODE", "live")
    monkeypatch.setenv("CASSANDRA_INTERNAL_BRIEF_CARVEOUT", "1")


def test_brief_blocked_under_guard_by_default(monkeypatch):
    import cassandra_no_send_reload_guard as guard

    _clear_send_mode(monkeypatch)
    monkeypatch.setenv(guard.ENV_VAR, "1")

    assert guard.should_quiesce_send_capable_service() is True
    assert guard.outbound_delivery_blocked() is True
    assert guard.is_internal_brief_carveout_enabled() is False
    assert guard.briefing_delivery_blocked() is True


def test_brief_permitted_when_carveout_enabled(monkeypatch):
    import cassandra_no_send_reload_guard as guard

    _enable_guard_and_carveout(monkeypatch)

    assert guard.should_quiesce_send_capable_service() is True
    assert guard.outbound_delivery_blocked() is True
    assert guard.is_internal_brief_carveout_enabled() is True
    assert guard.briefing_delivery_blocked() is False


def test_carveout_never_active_in_status_dry_run(monkeypatch):
    import cassandra_no_send_reload_guard as guard

    _enable_guard_and_carveout(monkeypatch)
    monkeypatch.setenv(guard.MODE_ENV_VAR, guard.STATUS_DRY_RUN_MODE)

    assert guard.is_status_dry_run_enabled() is True
    assert guard.is_internal_brief_carveout_enabled() is False
    assert guard.outbound_delivery_blocked() is True
    assert guard.briefing_delivery_blocked() is True


def test_carveout_default_off_when_no_guard(monkeypatch):
    import cassandra_no_send_reload_guard as guard

    _clear_send_mode(monkeypatch)

    assert guard.is_internal_brief_carveout_enabled() is False
    assert guard.briefing_delivery_blocked() is False


def test_internal_brief_delivers_under_guard_to_operator_only(monkeypatch):
    _enable_guard_and_carveout(monkeypatch)
    import cassandra_briefing_scheduler as scheduler
    import cassandra_sender

    importlib.reload(scheduler)
    sent: list[tuple[str, str | int | None]] = []
    spoken: list[str] = []
    marked: list[tuple[str, str]] = []

    monkeypatch.setattr(cassandra_sender, "_chat_id", lambda: "OPERATOR_ID")
    monkeypatch.setattr(
        cassandra_sender,
        "send_message",
        lambda text, chat_id=None: sent.append((text, chat_id)),
    )
    monkeypatch.setattr(scheduler, "split_briefing_messages", lambda entry: ["chunk one", "chunk two"])
    monkeypatch.setattr(scheduler, "briefing_voice_text", lambda entry: "compressed voice")
    monkeypatch.setattr(
        scheduler,
        "speak_and_send_operator_brief_voice",
        lambda text: spoken.append(text),
    )
    monkeypatch.setattr(scheduler, "mark_delivered", lambda date, slot: marked.append((date, slot)))

    scheduler._deliver({"slot": "afternoon", "date": "2026-06-16", "text": "full text"})

    assert sent == [("chunk one", "OPERATOR_ID"), ("chunk two", "OPERATOR_ID")]
    assert {chat_id for _, chat_id in sent} == {"OPERATOR_ID"}
    assert spoken == ["compressed voice"]
    assert marked == [("2026-06-16", "afternoon")]


def test_send_operator_brief_cannot_address_non_operator(monkeypatch):
    import cassandra_sender

    assert set(inspect.signature(cassandra_sender.send_operator_brief).parameters) == {"text"}
    assert set(inspect.signature(cassandra_sender.send_operator_brief_voice).parameters) == {"audio_path"}

    sent: list[tuple[str, str | int | None]] = []
    voices: list[tuple[str, str | int | None]] = []
    monkeypatch.setattr(cassandra_sender, "_chat_id", lambda: "OPERATOR_ID")
    monkeypatch.setattr(
        cassandra_sender,
        "send_message",
        lambda text, chat_id=None: sent.append((text, chat_id)),
    )
    monkeypatch.setattr(
        cassandra_sender,
        "send_voice_note",
        lambda audio_path, chat_id=None: voices.append((audio_path, chat_id)),
    )

    cassandra_sender.send_operator_brief("hi")
    cassandra_sender.send_operator_brief_voice("/tmp/operator-brief.ogg")

    assert sent == [("hi", "OPERATOR_ID")]
    assert voices == [("/tmp/operator-brief.ogg", "OPERATOR_ID")]

    resolved_ids = iter(["OPERATOR_ID", "CLIENT_ID"])
    monkeypatch.setattr(cassandra_sender, "_chat_id", lambda: next(resolved_ids))

    with pytest.raises(RuntimeError, match="not the verified operator id"):
        cassandra_sender.send_operator_brief("must refuse")


def test_brief_delivery_triggers_no_external_collaborator(monkeypatch):
    _enable_guard_and_carveout(monkeypatch)
    import cassandra_briefing_scheduler as scheduler
    import cassandra_sender
    import email_send_executor
    import gated_email_send_adapter
    import invoice_send_executor

    importlib.reload(scheduler)
    sent: list[tuple[str, str | int | None]] = []
    spoken: list[str] = []
    external_calls: list[str] = []

    monkeypatch.setattr(cassandra_sender, "_chat_id", lambda: "OPERATOR_ID")
    monkeypatch.setattr(
        cassandra_sender,
        "send_message",
        lambda text, chat_id=None: sent.append((text, chat_id)),
    )
    monkeypatch.setattr(
        cassandra_sender,
        "send_document",
        lambda *args, **kwargs: external_calls.append("telegram_document"),
    )
    monkeypatch.setattr(
        email_send_executor,
        "execute_email_send_packet",
        lambda *args, **kwargs: external_calls.append("email_send"),
    )
    monkeypatch.setattr(
        invoice_send_executor,
        "execute_invoice_send_packet",
        lambda *args, **kwargs: external_calls.append("invoice_send"),
    )
    monkeypatch.setattr(gated_email_send_adapter, "main", lambda *args, **kwargs: external_calls.append("gated_email"))

    monkeypatch.setattr(scheduler, "_restart_if_sources_changed", lambda: None)
    monkeypatch.setattr(scheduler, "due_slots", lambda: ["afternoon"])
    monkeypatch.setattr(scheduler, "generate_briefing", lambda slot: "internal operator brief")
    monkeypatch.setattr(scheduler, "protected_reason", lambda slot=None: None)
    monkeypatch.setattr(
        scheduler,
        "save_briefing",
        lambda slot, text, pending_reason=None: {"slot": slot, "date": "2026-06-16", "text": text},
    )
    monkeypatch.setattr(scheduler, "pending_briefings", lambda: [])
    monkeypatch.setattr(scheduler, "split_briefing_messages", lambda entry: [entry["text"]])
    monkeypatch.setattr(scheduler, "briefing_voice_text", lambda entry: "operator voice summary")
    monkeypatch.setattr(scheduler, "speak_and_send_operator_brief_voice", lambda text: spoken.append(text))

    scheduler._tick()

    assert sent == [("internal operator brief", "OPERATOR_ID")]
    assert spoken == ["operator voice summary"]
    assert external_calls == []


def test_external_email_send_refuses_under_guard(monkeypatch, tmp_path):
    _enable_guard_and_carveout(monkeypatch)
    import cassandra_no_send_reload_guard as guard
    from correspondence_watcher import plan_reynolds_correspondence_reply
    from email_send_executor import execute_email_send_packet

    db_path = str(tmp_path / "email.sqlite")
    send_hold = tmp_path / "SEND_HOLD.md"
    send_hold.write_text("active\n", encoding="utf-8")
    plan = plan_reynolds_correspondence_reply(
        thread_id="thread_internal_brief_carveout_email",
        sender_name="Sally",
        body_summary="Sally confirmed the Reynolds date.",
        db_path=db_path,
    )
    sender_calls: list[dict] = []

    receipt = execute_email_send_packet(
        packet_id=plan.packet_id or "",
        db_path=db_path,
        send_hold_path=send_hold,
        email_sender=lambda **kwargs: sender_calls.append(kwargs),
    )

    assert guard.should_quiesce_send_capable_service() is True
    assert guard.outbound_delivery_blocked() is True
    assert receipt.ok is False
    assert "SEND_HOLD is active" in receipt.detail
    assert receipt.meta["email_send_performed"] is False
    assert receipt.meta["gmail_api_called"] is False
    assert receipt.meta["external_send_performed"] is False
    assert sender_calls == []


def test_external_invoice_send_refuses_under_guard(monkeypatch, tmp_path):
    _enable_guard_and_carveout(monkeypatch)
    import cassandra_no_send_reload_guard as guard
    from chief_compose import compose
    from invoice_send_executor import INVOICE_SEND_SURFACE, execute_invoice_send_packet

    db_path = str(tmp_path / "invoice.sqlite")
    send_hold = tmp_path / "SEND_HOLD.md"
    send_hold.write_text("active\n", encoding="utf-8")
    result = compose(
        "send the Reynolds Tavern invoice for 250 dollars through Square sandbox",
        source_kind="mission_control",
        source_channel="internal_brief_carveout_test",
        requested_by="winship",
        db_path=db_path,
    )
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "UPDATE agent_work_packets SET execution_allowed = 1, status = 'proposed' WHERE packet_id = ?",
            (result.packet_id,),
        )
        conn.commit()

    receipt = execute_invoice_send_packet(
        packet_id=result.packet_id or "",
        db_path=db_path,
        send_hold_path=send_hold,
    )

    assert result.intent == INVOICE_SEND_SURFACE
    assert guard.should_quiesce_send_capable_service() is True
    assert guard.outbound_delivery_blocked() is True
    assert receipt.ok is False
    assert "SEND_HOLD is active" in receipt.detail
    assert receipt.meta["send_hold_active"] is True
    assert receipt.meta["square_api_called"] is False
    assert receipt.meta["external_send_performed"] is False


def test_watcher_outbound_paths_blocked_under_guard(monkeypatch, tmp_path):
    _enable_guard_and_carveout(monkeypatch)
    import cassandra_send_status_dry_run as dry_run

    status = dry_run.build_watcher_status(
        followup_path=tmp_path / "missing_followups.jsonl",
        future_action_db_path=tmp_path / "missing_future_actions.db",
        generated_at="2026-06-16T12:00:00+00:00",
    )

    assert status["outbound_delivery_blocked"] is True
    assert status["blocked_outbound_paths"]
    assert "pending_followup_email_draft" in status["blocked_outbound_paths"]
    assert "future_action_telegram_reminder" in status["blocked_outbound_paths"]


def test_status_read_model_reports_carveout_blocked_in_dry_run(monkeypatch):
    import cassandra_no_send_reload_guard as guard
    import cassandra_send_status_dry_run as dry_run

    _enable_guard_and_carveout(monkeypatch)
    monkeypatch.setenv(guard.MODE_ENV_VAR, guard.STATUS_DRY_RUN_MODE)
    monkeypatch.setattr(
        dry_run,
        "inspect_briefing_scheduler",
        lambda: {
            "due_slots": ["morning"],
            "due_count": 1,
            "pending_count": 0,
            "pending_slots": [],
            "telegram_delivery_blocked": True,
            "voice_delivery_blocked": True,
            "raw_briefing_text_returned": False,
        },
    )

    status = dry_run.build_briefing_scheduler_status(generated_at="2026-06-16T12:00:00+00:00")
    carveout = status["internal_brief_carveout"]

    assert carveout == {
        "enabled": False,
        "delivery_blocked": True,
        "target": "winship_operator_telegram_chat_id_only",
        "external_client_send_allowed": False,
        "send_hold_touched": False,
        "external_paths_still_blocked": True,
    }
