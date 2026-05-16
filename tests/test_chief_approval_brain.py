import json
import os
import sys
import types
from datetime import datetime, timedelta

import pytest


sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def _write_pending(path, *, status="pending", requested_at=None, approval_id="ABCD", options=2):
    if requested_at is None:
        requested_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    path.write_text(
        json.dumps(
            {
                "status": status,
                "requested_at": requested_at,
                "id": approval_id,
                "options": options,
            }
        ),
        encoding="utf-8",
    )


def _write_full_pending(path, *, approval_id="ABCD1234", options=2):
    requested_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    path.write_text(
        json.dumps(
            {
                "id": approval_id,
                "action": "Synthetic approval action that must stay out of SQLite rows",
                "requester": "unit_test",
                "requested_at": requested_at,
                "status": "pending",
                "decision": None,
                "options": options,
                "tier": 2,
                "hash": "HASH1234",
                "approval_context": {
                    "raw_command_text": "rm -rf /",
                    "action_label": "synthetic label",
                },
            }
        ),
        encoding="utf-8",
    )


class TestPendingApprovalState:
    def test_non_pending_reports_no_active_approval(self, monkeypatch, tmp_path):
        import chief_approval_brain as approval_brain

        pending_path = tmp_path / "approval_pending.json"
        monkeypatch.setattr(approval_brain, "PENDING_FILE", pending_path, raising=False)
        _write_pending(pending_path, status="decided")

        assert approval_brain.has_pending_approval() is False
        assert approval_brain.get_pending_id() == ""
        assert approval_brain.get_pending_info() == ("", 2)

    def test_stale_pending_is_cleared_for_all_read_helpers(self, monkeypatch, tmp_path):
        import chief_approval_brain as approval_brain

        pending_path = tmp_path / "approval_pending.json"
        monkeypatch.setattr(approval_brain, "PENDING_FILE", pending_path, raising=False)
        stale_requested_at = (datetime.now() - timedelta(seconds=approval_brain.TIMEOUT + 60)).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        _write_pending(pending_path, requested_at=stale_requested_at, approval_id="WXYZ", options=3)

        assert approval_brain.has_pending_approval() is False
        assert approval_brain.get_pending_id() == ""
        assert approval_brain.get_pending_info() == ("", 2)
        assert json.loads(pending_path.read_text(encoding="utf-8")) == {}

    def test_fresh_pending_returns_active_approval_data(self, monkeypatch, tmp_path):
        import chief_approval_brain as approval_brain

        pending_path = tmp_path / "approval_pending.json"
        monkeypatch.setattr(approval_brain, "PENDING_FILE", pending_path, raising=False)
        _write_pending(pending_path, approval_id="LIVE", options=3)

        assert approval_brain.has_pending_approval() is True
        assert approval_brain.get_pending_id() == "LIVE"
        assert approval_brain.get_pending_info() == ("LIVE", 3)


class TestGuardianApprovalCards:
    def test_generic_non_email_approval_renders_as_before(self):
        import chief_approval_brain as approval_brain

        message = approval_brain._build_l2_message(
            "Google broker: chief → google.calendar.write",
            "ABCD1234",
            "HASH1234",
            2,
        )

        assert "Action: Google broker: chief → google.calendar.write" in message
        assert "Mode:" not in message
        assert "Thread synopsis:" not in message
        assert "Draft preview:" not in message
        assert "Reply code: ABCD" in message

    def test_cassandra_email_send_approval_renders_enriched_card(self):
        import chief_approval_brain as approval_brain

        message = approval_brain._build_l2_message(
            "Google broker: cassandra → google.gmail.send",
            "ABCD1234",
            "HASH1234",
            2,
            approval_context={
                "action_label": "send email",
                "mode": "reply in thread",
                "to": "Winship <winshipwheatley@gmail.com>",
                "cc": "winshiplive@gmail.com",
                "subject": "Re: Cassandra smoke test",
                "thread_synopsis": "Latest inbound email from Winship: he says he's proud of my progress.",
                "proposed_send": "Reply in-thread to Winship about \"Re: Cassandra smoke test\" saying thanks and I'll let him know on Telegram.",
                "draft_preview": "Thanks for saying that — it means a lot. I'll let Winship know on Telegram that he's proud of my progress.",
            },
        )

        assert "Action: send email" in message
        assert "Action: Google broker: cassandra → google.gmail.send" not in message
        assert "Mode: reply in thread" in message
        assert "To: Winship <winshipwheatley@gmail.com>" in message
        assert "CC: winshiplive@gmail.com" in message
        assert "Subject: Re: Cassandra smoke test" in message
        assert "Thread synopsis:" in message
        assert "Proposed send:" in message
        assert "Draft preview:" in message
        assert "Reply code: ABCD" in message


class TestGuardianSenderPolicy:
    def test_button_send_uses_guardian_token_when_present(self, monkeypatch):
        import chief_guardian_sender as sender

        posted = []

        class Response:
            def raise_for_status(self):
                return None

        def fake_post(url, json=None, timeout=None):
            posted.append((url, json, timeout))
            return Response()

        monkeypatch.setattr(sender.chief_env, "load_env", lambda: None)
        monkeypatch.setenv("GUARDIAN_BOT_TOKEN", "guardian-token")
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "chief-token")
        monkeypatch.setenv("TELEGRAM_AUTHORIZED_USER_ID", "42")
        monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
        monkeypatch.setattr(sender.requests, "post", fake_post)

        keyboard = {"inline_keyboard": [[{"text": "Approve", "callback_data": "YES:ABCD1234"}]]}
        sender.send_approval("Approve this", reply_markup=keyboard)

        assert len(posted) == 1
        url, payload, timeout = posted[0]
        assert url == "https://api.telegram.org/botguardian-token/sendMessage"
        assert payload == {"chat_id": "42", "text": "Approve this", "reply_markup": keyboard}
        assert timeout == 15

    def test_button_send_requires_guardian_token(self, monkeypatch):
        import chief_guardian_sender as sender

        monkeypatch.setattr(sender.chief_env, "load_env", lambda: None)
        monkeypatch.delenv("GUARDIAN_BOT_TOKEN", raising=False)
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "chief-token")
        monkeypatch.setenv("TELEGRAM_AUTHORIZED_USER_ID", "42")
        monkeypatch.setattr(
            sender.requests,
            "post",
            lambda *args, **kwargs: pytest.fail("button send fell back to Telegram bot"),
        )

        keyboard = {"inline_keyboard": [[{"text": "Approve", "callback_data": "YES:ABCD1234"}]]}
        with pytest.raises(sender.GuardianConfigurationError, match="GUARDIAN_BOT_TOKEN is required"):
            sender.send_approval("Approve this", reply_markup=keyboard)

    def test_plain_send_keeps_chief_fallback_when_guardian_missing(self, monkeypatch):
        import chief_guardian_sender as sender

        posted = []

        class Response:
            def raise_for_status(self):
                return None

        def fake_post(url, json=None, timeout=None):
            posted.append((url, json, timeout))
            return Response()

        monkeypatch.setattr(sender.chief_env, "load_env", lambda: None)
        monkeypatch.delenv("GUARDIAN_BOT_TOKEN", raising=False)
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "chief-token")
        monkeypatch.setenv("TELEGRAM_AUTHORIZED_USER_ID", "42")
        monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
        monkeypatch.setattr(sender.requests, "post", fake_post)

        sender.send_approval("No pending approval requests.")

        assert len(posted) == 1
        url, payload, timeout = posted[0]
        assert url == "https://api.telegram.org/botchief-token/sendMessage"
        assert payload == {"chat_id": "42", "text": "No pending approval requests."}
        assert timeout == 15

    def test_approval_brain_button_failure_does_not_fallback_to_chief(self, monkeypatch):
        import chief_approval_brain as approval_brain
        import chief_guardian_sender as sender

        chief_messages = []

        def fail_send(*args, **kwargs):
            raise sender.GuardianConfigurationError("missing Guardian token")

        monkeypatch.setattr(approval_brain.chief_env, "load_env", lambda: None)
        monkeypatch.setattr(sender, "send_approval", fail_send)
        monkeypatch.setattr(approval_brain, "_send_chief", lambda message: chief_messages.append(message))

        ok = approval_brain._send_via_guardian(
            "APPROVAL REQUIRED",
            keyboard={"inline_keyboard": [[{"text": "Approve", "callback_data": "YES:ABCD1234"}]]},
        )

        assert ok is False
        assert chief_messages == []


class TestApprovalReplyRouting:
    def test_unknown_approval_code_does_not_fall_through_to_billing(self, monkeypatch):
        from chief_router import route_message

        monkeypatch.setitem(route_message.__globals__, "_log_route", lambda *args, **kwargs: None)
        monkeypatch.setitem(route_message.__globals__, "has_pending_approval", lambda: False)

        def fail_if_called(*args, **kwargs):
            raise AssertionError("stale approval reply fell through to normal routing")

        monkeypatch.setitem(route_message.__globals__, "append_history", fail_if_called)
        monkeypatch.setitem(route_message.__globals__, "load_session", fail_if_called)
        monkeypatch.setitem(route_message.__globals__, "billing_handle", fail_if_called)

        result = route_message("0F37 1 - Approve")

        assert result["intent"] == "approval_response"
        assert result["reply"] == (
            "Expired or unknown approval code. No approval was applied. Request a fresh approval."
        )


class TestChiefApprovalDualWrite:
    def _patch_tier2_runtime(self, approval_brain, monkeypatch, pending_path):
        monkeypatch.setattr(approval_brain, "PENDING_FILE", pending_path, raising=False)
        monkeypatch.setattr(approval_brain, "_is_hard_t2", lambda action: False)
        monkeypatch.setattr(approval_brain, "_acquire_slot_lock", lambda: None)
        monkeypatch.setattr(approval_brain, "_release_slot_lock", lambda lock: None)
        monkeypatch.setattr(approval_brain, "_append_log", lambda *args, **kwargs: None)
        monkeypatch.setitem(
            sys.modules,
            "chief_session_manager",
            types.SimpleNamespace(load_session=lambda: {}),
        )
        monkeypatch.setitem(
            sys.modules,
            "chief_assist",
            types.SimpleNamespace(
                escalate_to_operator=lambda **kwargs: (_ for _ in ()).throw(RuntimeError("disabled"))
            ),
        )

    def test_dual_write_not_called_when_guardian_send_fails(self, monkeypatch, tmp_path):
        import chief_approval_brain as approval_brain

        pending_path = tmp_path / "approval_pending.json"
        calls = []
        self._patch_tier2_runtime(approval_brain, monkeypatch, pending_path)
        monkeypatch.setattr(approval_brain, "_send_via_guardian", lambda *args, **kwargs: False)
        monkeypatch.setattr(
            approval_brain,
            "_dual_write_chief_approval_request",
            lambda pending: calls.append(dict(pending)),
        )

        ok = approval_brain.request_approval(
            "Synthetic approval request",
            explicit_tier=2,
        )

        assert ok is False
        assert calls == []
        assert json.loads(pending_path.read_text(encoding="utf-8")) == {}

    def test_dual_write_not_called_when_legacy_json_write_fails(self, monkeypatch, tmp_path):
        import chief_approval_brain as approval_brain

        pending_path = tmp_path / "approval_pending.json"
        calls = []
        self._patch_tier2_runtime(approval_brain, monkeypatch, pending_path)
        monkeypatch.setattr(approval_brain, "_send_via_guardian", lambda *args, **kwargs: True)

        def fail_save(data):
            raise OSError("synthetic legacy write failure")

        monkeypatch.setattr(approval_brain, "_save_pending", fail_save)
        monkeypatch.setattr(
            approval_brain,
            "_dual_write_chief_approval_request",
            lambda pending: calls.append(dict(pending)),
        )

        with pytest.raises(OSError, match="synthetic legacy write failure"):
            approval_brain.request_approval(
                "Synthetic approval request",
                explicit_tier=2,
            )

        assert calls == []

    def test_dual_write_adapter_failure_does_not_block_legacy_approval(self, monkeypatch, tmp_path):
        import chief_approval_brain as approval_brain
        import guardian_hitl_dual_write_compatibility as dual_write

        pending_path = tmp_path / "approval_pending.json"
        self._patch_tier2_runtime(approval_brain, monkeypatch, pending_path)
        monkeypatch.setattr(approval_brain, "_send_via_guardian", lambda *args, **kwargs: True)
        monkeypatch.setattr(approval_brain, "send_no_pending_confirmation", lambda: None)

        def fail_mirror(*args, **kwargs):
            raise RuntimeError("synthetic sqlite mirror failure")

        def approve_on_poll(_seconds):
            data = json.loads(pending_path.read_text(encoding="utf-8"))
            data["status"] = "decided"
            data["decision"] = "YES"
            pending_path.write_text(json.dumps(data), encoding="utf-8")

        monkeypatch.setattr(dual_write, "mirror_chief_approval_request_fail_open", fail_mirror)
        monkeypatch.setattr(approval_brain.time, "sleep", approve_on_poll)

        ok = approval_brain.request_approval(
            "Synthetic approval request",
            explicit_tier=2,
        )

        assert ok is True
        assert json.loads(pending_path.read_text(encoding="utf-8")) == {}

    def test_record_decision_writes_observational_decision_after_legacy_save(self, monkeypatch, tmp_path):
        import chief_approval_brain as approval_brain

        pending_path = tmp_path / "approval_pending.json"
        _write_full_pending(pending_path, approval_id="LIVE1234")
        calls = []
        monkeypatch.setattr(approval_brain, "PENDING_FILE", pending_path, raising=False)
        monkeypatch.setattr(
            approval_brain,
            "_dual_write_chief_approval_decision",
            lambda pending, decision: calls.append((dict(pending), decision)),
        )

        reply = approval_brain.record_decision("1", expected_id="LIVE1234")

        assert reply == "Approved."
        saved = json.loads(pending_path.read_text(encoding="utf-8"))
        assert saved["status"] == "decided"
        assert saved["decision"] == "YES"
        assert calls == [(saved, "YES")]

    def test_record_decision_id_mismatch_does_not_mirror_or_approve(self, monkeypatch, tmp_path):
        import chief_approval_brain as approval_brain

        pending_path = tmp_path / "approval_pending.json"
        _write_full_pending(pending_path, approval_id="LIVE1234")
        calls = []
        monkeypatch.setattr(approval_brain, "PENDING_FILE", pending_path, raising=False)
        monkeypatch.setattr(
            approval_brain,
            "_dual_write_chief_approval_decision",
            lambda pending, decision: calls.append((dict(pending), decision)),
        )

        reply = approval_brain.record_decision("1", expected_id="STALE999")

        assert reply == "Approval ID mismatch — reply not applied."
        saved = json.loads(pending_path.read_text(encoding="utf-8"))
        assert saved["status"] == "pending"
        assert saved["decision"] is None
        assert calls == []

    def test_decision_adapter_failure_does_not_block_record_decision(self, monkeypatch, tmp_path):
        import chief_approval_brain as approval_brain
        import guardian_hitl_dual_write_compatibility as dual_write

        pending_path = tmp_path / "approval_pending.json"
        _write_full_pending(pending_path, approval_id="LIVE1234")
        monkeypatch.setattr(approval_brain, "PENDING_FILE", pending_path, raising=False)

        def fail_mirror(*args, **kwargs):
            raise RuntimeError("synthetic decision mirror failure")

        monkeypatch.setattr(dual_write, "mirror_chief_approval_decision_fail_open", fail_mirror)

        reply = approval_brain.record_decision("2", expected_id="LIVE1234")

        assert reply == "Denied."
        saved = json.loads(pending_path.read_text(encoding="utf-8"))
        assert saved["status"] == "decided"
        assert saved["decision"] == "NO"

    def test_timeout_path_attempts_observational_expiry_receipt_only(self, monkeypatch, tmp_path):
        import chief_approval_brain as approval_brain

        pending_path = tmp_path / "approval_pending.json"
        calls = []
        self._patch_tier2_runtime(approval_brain, monkeypatch, pending_path)
        monkeypatch.setattr(approval_brain, "TIMEOUT", 0)
        monkeypatch.setattr(approval_brain, "_send_via_guardian", lambda *args, **kwargs: True)
        monkeypatch.setattr(approval_brain, "_dual_write_chief_approval_request", lambda pending: None)
        monkeypatch.setattr(approval_brain, "send_no_pending_confirmation", lambda: None)
        monkeypatch.setattr(
            approval_brain,
            "_dual_write_chief_approval_decision",
            lambda pending, decision: calls.append((dict(pending), decision)),
        )

        ok = approval_brain.request_approval(
            "Synthetic timeout approval request",
            explicit_tier=2,
        )

        assert ok is False
        assert len(calls) == 1
        assert calls[0][1] == "TIMEOUT"
        assert calls[0][0]["status"] == "pending"
        assert json.loads(pending_path.read_text(encoding="utf-8")) == {}
