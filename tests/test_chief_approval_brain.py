import json
import os
import sys
from datetime import datetime, timedelta


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
