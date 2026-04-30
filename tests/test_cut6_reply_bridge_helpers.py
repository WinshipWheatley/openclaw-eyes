"""
test_cut6_reply_bridge_helpers.py

Focused tests for Cut 6: reply-bridge orchestration helpers moved to
cassandra_outreach.py, plus thin-wrapper smoke tests in cassandra_brain.py.
"""

import json
import sys
import os
from datetime import datetime

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ── _detect_inner_circle_email_reply_intent ──────────────────────────────────

class TestDetectInnerCircleEmailReplyIntent:
    def test_matches_check_inner_circle(self):
        from cassandra_outreach import _detect_inner_circle_email_reply_intent
        assert _detect_inner_circle_email_reply_intent("check inner circle email replies") is True

    def test_matches_hyphenated(self):
        from cassandra_outreach import _detect_inner_circle_email_reply_intent
        assert _detect_inner_circle_email_reply_intent("show inner-circle email replies") is True

    def test_matches_check_email_replies_from(self):
        from cassandra_outreach import _detect_inner_circle_email_reply_intent
        assert _detect_inner_circle_email_reply_intent("check email replies from Dad") is True

    def test_case_insensitive(self):
        from cassandra_outreach import _detect_inner_circle_email_reply_intent
        assert _detect_inner_circle_email_reply_intent("CHECK INNER CIRCLE EMAIL REPLIES") is True

    def test_no_match(self):
        from cassandra_outreach import _detect_inner_circle_email_reply_intent
        assert _detect_inner_circle_email_reply_intent("send an email to Bob") is False

    def test_empty(self):
        from cassandra_outreach import _detect_inner_circle_email_reply_intent
        assert _detect_inner_circle_email_reply_intent("") is False


# ── _email_bridge_message_seen ───────────────────────────────────────────────

class TestEmailBridgeMessageSeen:
    def test_missing_log_returns_false(self, tmp_path, monkeypatch):
        import cassandra_outreach as outreach
        monkeypatch.setattr(outreach, "_EMAIL_BRIDGE_LOG", tmp_path / "nope.jsonl")
        assert outreach._email_bridge_message_seen("m1") is False

    def test_empty_message_id_returns_false(self, tmp_path, monkeypatch):
        import cassandra_outreach as outreach
        monkeypatch.setattr(outreach, "_EMAIL_BRIDGE_LOG", tmp_path / "nope.jsonl")
        assert outreach._email_bridge_message_seen("") is False

    def test_found_returns_true(self, tmp_path, monkeypatch):
        import cassandra_outreach as outreach
        log = tmp_path / "bridge.jsonl"
        log.write_text(json.dumps({"message_id": "m1"}) + "\n", encoding="utf-8")
        monkeypatch.setattr(outreach, "_EMAIL_BRIDGE_LOG", log)
        assert outreach._email_bridge_message_seen("m1") is True

    def test_not_found_returns_false(self, tmp_path, monkeypatch):
        import cassandra_outreach as outreach
        log = tmp_path / "bridge.jsonl"
        log.write_text(json.dumps({"message_id": "m1"}) + "\n", encoding="utf-8")
        monkeypatch.setattr(outreach, "_EMAIL_BRIDGE_LOG", log)
        assert outreach._email_bridge_message_seen("m999") is False


# ── _log_email_bridge_event ──────────────────────────────────────────────────

class TestLogEmailBridgeEvent:
    def _call_log(self, outreach, **overrides):
        defaults = dict(
            message_id="m1",
            thread_id="t1",
            nickname="dad",
            contact_name="Dad",
            sender_email="dad@example.com",
            subject="Hello",
            preview="Preview text here",
            lane="allowed",
            status="processed",
            unread=True,
        )
        defaults.update(overrides)
        outreach._log_email_bridge_event(**defaults)

    def test_writes_entry(self, tmp_path, monkeypatch):
        import cassandra_outreach as outreach
        log = tmp_path / "bridge.jsonl"
        monkeypatch.setattr(outreach, "_EMAIL_BRIDGE_LOG", log)
        self._call_log(outreach)
        lines = log.read_text().strip().splitlines()
        assert len(lines) == 1
        entry = json.loads(lines[0])
        assert entry["message_id"] == "m1"
        assert entry["nickname"] == "dad"
        assert entry["route"] == "inner_circle_email_reply"

    def test_dedupe_skips_seen(self, tmp_path, monkeypatch):
        import cassandra_outreach as outreach
        log = tmp_path / "bridge.jsonl"
        monkeypatch.setattr(outreach, "_EMAIL_BRIDGE_LOG", log)
        self._call_log(outreach, message_id="m1")
        self._call_log(outreach, message_id="m1")
        lines = log.read_text().strip().splitlines()
        assert len(lines) == 1

    def test_dedupe_false_allows_duplicate(self, tmp_path, monkeypatch):
        import cassandra_outreach as outreach
        log = tmp_path / "bridge.jsonl"
        monkeypatch.setattr(outreach, "_EMAIL_BRIDGE_LOG", log)
        self._call_log(outreach, message_id="m1")
        self._call_log(outreach, message_id="m1", dedupe=False)
        lines = log.read_text().strip().splitlines()
        assert len(lines) == 2


# ── Known-contact watch event contract ──────────────────────────────────────

class TestKnownContactWatchEvent:
    def _base_operator_action_kwargs(self):
        return {
            "message_id": "m-known",
            "thread_id": "t-known",
            "sender_email": "CLIENT@Example.com",
            "contact_nickname": "client_a",
            "contact_tier": "client",
            "matched_reason": "pinned email matched active payment lane",
            "created_at": "2026-04-29 09:30:00",
        }

    def _patch_operator_action_side_effects_to_fail(self, monkeypatch):
        import cassandra_brain
        import cassandra_outreach as outreach

        def fail_side_effect(*args, **kwargs):
            raise AssertionError("known-contact operator-action reducer must not call side-effect services")

        monkeypatch.setattr(outreach, "create_gmail_draft", fail_side_effect)
        monkeypatch.setattr(
            cassandra_brain,
            "_start_email_send_after_draft",
            fail_side_effect,
            raising=False,
        )
        try:
            import chief_approval_brain
            monkeypatch.setattr(chief_approval_brain, "request_approval", fail_side_effect, raising=False)
        except Exception:
            pass

    def test_records_required_fields(self, tmp_path, monkeypatch):
        import cassandra_outreach as outreach

        log = tmp_path / "known_contact_watch.jsonl"
        monkeypatch.setattr(outreach, "_KNOWN_CONTACT_WATCH_LOG", log)

        entry = outreach.record_known_contact_watch_event(
            message_id="m-known",
            thread_id="t-known",
            sender_email="CLIENT@Example.com",
            contact_nickname="client_a",
            contact_tier="client",
            watch_state=outreach.KNOWN_CONTACT_WATCH_NOTIFICATION,
            ownership_state=outreach.UNASSIGNED_KNOWN_CONTACT_THREAD,
            matched_reason="pinned email matched active payment lane",
            operator_action="notify_only",
            draft_id="draft-should-stay-data-only",
            approval_id="approval-should-stay-data-only",
            created_at="2026-04-29 09:00:00",
        )

        assert entry == {
            "message_id": "m-known",
            "thread_id": "t-known",
            "sender_email": "client@example.com",
            "contact_nickname": "client_a",
            "contact_tier": "client",
            "watch_state": "known_contact_watch_notification",
            "ownership_state": "unassigned_known_contact_thread",
            "matched_reason": "pinned email matched active payment lane",
            "operator_action": "notify_only",
            "draft_id": "draft-should-stay-data-only",
            "approval_id": "approval-should-stay-data-only",
            "created_at": "2026-04-29 09:00:00",
        }
        saved = json.loads(log.read_text(encoding="utf-8").strip())
        assert saved == entry

    def test_missing_optional_fields_default_safely(self, tmp_path, monkeypatch):
        import cassandra_outreach as outreach

        log = tmp_path / "known_contact_watch.jsonl"
        monkeypatch.setattr(outreach, "_KNOWN_CONTACT_WATCH_LOG", log)

        entry = outreach.record_known_contact_watch_event(
            message_id="m-known",
            thread_id="t-known",
            sender_email="client@example.com",
            contact_nickname="client_a",
            contact_tier="client",
        )

        assert entry["watch_state"] == "known_contact_watch_notification"
        assert entry["ownership_state"] == "unassigned_known_contact_thread"
        assert entry["operator_action"] == "pending"
        assert entry["draft_id"] == ""
        assert entry["approval_id"] == ""
        assert entry["created_at"]

    def test_operator_watch_action_records_user_assignment(self, tmp_path, monkeypatch):
        import cassandra_outreach as outreach

        log = tmp_path / "known_contact_watch.jsonl"
        monkeypatch.setattr(outreach, "_KNOWN_CONTACT_WATCH_LOG", log)
        self._patch_operator_action_side_effects_to_fail(monkeypatch)

        entry = outreach.record_known_contact_operator_action(
            **self._base_operator_action_kwargs(),
            operator_action="watch_thread",
        )

        assert entry["watch_state"] == outreach.APPROVED_FOR_FOLLOW_UP_LANE
        assert entry["ownership_state"] == outreach.USER_ASSIGNED_THREAD
        assert entry["operator_action"] == "watch_thread"
        assert json.loads(log.read_text(encoding="utf-8").strip()) == entry

    def test_operator_ignore_action_records_not_in_scope(self, tmp_path, monkeypatch):
        import cassandra_outreach as outreach

        log = tmp_path / "known_contact_watch.jsonl"
        monkeypatch.setattr(outreach, "_KNOWN_CONTACT_WATCH_LOG", log)
        self._patch_operator_action_side_effects_to_fail(monkeypatch)

        entry = outreach.record_known_contact_operator_action(
            **self._base_operator_action_kwargs(),
            operator_action="ignore_thread",
        )

        assert entry["watch_state"] == outreach.IGNORED_NOT_IN_SCOPE_THREAD
        assert entry["operator_action"] == "ignore_thread"
        assert json.loads(log.read_text(encoding="utf-8").strip()) == entry

    def test_operator_revise_action_records_request_without_side_effects(self, tmp_path, monkeypatch):
        import cassandra_outreach as outreach

        log = tmp_path / "known_contact_watch.jsonl"
        monkeypatch.setattr(outreach, "_KNOWN_CONTACT_WATCH_LOG", log)
        self._patch_operator_action_side_effects_to_fail(monkeypatch)

        entry = outreach.record_known_contact_operator_action(
            **self._base_operator_action_kwargs(),
            operator_action="revise_response",
            revision_request="Make it shorter and warmer.",
            response_preview="Thanks - I can confirm the invoice and timing.",
        )

        assert entry["operator_action"] == "revise_response"
        assert entry["revision_request"] == "Make it shorter and warmer."
        assert entry["suggested_response_preview"] == "Thanks - I can confirm the invoice and timing."
        assert "draft_intent" not in entry
        assert "approval_intent" not in entry
        assert json.loads(log.read_text(encoding="utf-8").strip()) == entry

    def test_operator_create_gmail_draft_records_intent_without_execution(self, tmp_path, monkeypatch):
        import cassandra_outreach as outreach

        log = tmp_path / "known_contact_watch.jsonl"
        monkeypatch.setattr(outreach, "_KNOWN_CONTACT_WATCH_LOG", log)
        self._patch_operator_action_side_effects_to_fail(monkeypatch)

        entry = outreach.record_known_contact_operator_action(
            **self._base_operator_action_kwargs(),
            operator_action="create_gmail_draft",
            draft_id="mock-draft-id",
            response_preview="Draft this as a concise payment follow-up.",
        )

        assert entry["operator_action"] == "create_gmail_draft"
        assert entry["draft_intent"] == "requested"
        assert entry["draft_id"] == "mock-draft-id"
        assert "approval_intent" not in entry
        assert json.loads(log.read_text(encoding="utf-8").strip()) == entry

    def test_operator_send_approval_requires_draft_or_preview_or_body(self, tmp_path, monkeypatch):
        import cassandra_outreach as outreach

        log = tmp_path / "known_contact_watch.jsonl"
        monkeypatch.setattr(outreach, "_KNOWN_CONTACT_WATCH_LOG", log)
        self._patch_operator_action_side_effects_to_fail(monkeypatch)

        with pytest.raises(ValueError, match="requires draft_id or explicit preview/body text"):
            outreach.record_known_contact_operator_action(
                **self._base_operator_action_kwargs(),
                operator_action="ask_guardian_send_approval",
            )

        assert not log.exists()

    @pytest.mark.parametrize(
        ("field", "value", "approval_source"),
        [
            ("draft_id", "mock-draft-id", "draft_id"),
            ("response_preview", "Please approve this preview.", "preview_or_body"),
            ("body_text", "Please approve this body.", "preview_or_body"),
        ],
    )
    def test_operator_send_approval_records_intent_only(self, tmp_path, monkeypatch, field, value, approval_source):
        import cassandra_outreach as outreach

        log = tmp_path / "known_contact_watch.jsonl"
        monkeypatch.setattr(outreach, "_KNOWN_CONTACT_WATCH_LOG", log)
        self._patch_operator_action_side_effects_to_fail(monkeypatch)

        entry = outreach.record_known_contact_operator_action(
            **self._base_operator_action_kwargs(),
            operator_action="ask_guardian_send_approval",
            **{field: value},
        )

        assert entry["operator_action"] == "ask_guardian_send_approval"
        assert entry["approval_intent"] == "requested"
        assert entry["approval_source"] == approval_source
        if field == "draft_id":
            assert entry["draft_id"] == value
        if field == "response_preview":
            assert entry["suggested_response_preview"] == value
        if field == "body_text":
            assert entry["body_preview"] == value
        assert json.loads(log.read_text(encoding="utf-8").strip()) == entry

    def test_operator_invalid_action_raises(self, tmp_path, monkeypatch):
        import cassandra_outreach as outreach

        log = tmp_path / "known_contact_watch.jsonl"
        monkeypatch.setattr(outreach, "_KNOWN_CONTACT_WATCH_LOG", log)

        with pytest.raises(ValueError, match="invalid operator_action"):
            outreach.record_known_contact_operator_action(
                **self._base_operator_action_kwargs(),
                operator_action="send_now",
            )

        assert not log.exists()

    @pytest.mark.parametrize(
        "field",
        ["message_id", "thread_id", "sender_email", "contact_nickname", "contact_tier"],
    )
    def test_operator_action_validates_required_identity_fields(self, tmp_path, monkeypatch, field):
        import cassandra_outreach as outreach

        log = tmp_path / "known_contact_watch.jsonl"
        monkeypatch.setattr(outreach, "_KNOWN_CONTACT_WATCH_LOG", log)
        kwargs = self._base_operator_action_kwargs()
        kwargs[field] = ""

        with pytest.raises(ValueError, match=f"{field} is required"):
            outreach.record_known_contact_operator_action(
                **kwargs,
                operator_action="watch_thread",
            )

        assert not log.exists()

    def test_build_known_contact_watch_notification_text_includes_context_and_options(self):
        import cassandra_outreach as outreach

        event = {
            "message_id": "m-known",
            "thread_id": "t-known",
            "sender_email": "client@example.com",
            "contact_nickname": "client_a",
            "contact_tier": "client",
            "watch_state": outreach.KNOWN_CONTACT_WATCH_NOTIFICATION,
            "ownership_state": outreach.UNASSIGNED_KNOWN_CONTACT_THREAD,
            "matched_reason": "pinned email matched active payment lane",
        }

        text = outreach.build_known_contact_watch_notification_text(
            event,
            sender_display_name="Client A",
            subject="Payment timing",
            lane_label="A/V payment lane",
            grounded_status="invoice still open",
            safe_summary="asking when payment will be remitted",
            suggested_response_preview="Thanks - I can confirm the invoice and timing.",
        )

        assert "Heads up — new email from Client A." in text
        assert "pinned email matched active payment lane" in text
        assert "A/V payment lane" in text
        assert "Payment timing" in text
        assert "invoice still open" in text
        assert "Thanks - I can confirm the invoice and timing." in text
        assert "1. Watch this thread" in text
        assert "2. Revise the response" in text
        assert "3. Create a Gmail draft" in text
        assert "4. Ask Guardian for send approval" in text
        assert "5. Ignore this thread" in text

    def test_send_known_contact_watch_notification_uses_injected_send_fn_once(self):
        import cassandra_outreach as outreach

        sent = []
        event = {
            "message_id": "m-known",
            "thread_id": "t-known",
            "sender_email": "client@example.com",
            "contact_nickname": "client_a",
            "contact_tier": "client",
            "watch_state": outreach.KNOWN_CONTACT_WATCH_NOTIFICATION,
            "ownership_state": outreach.UNASSIGNED_KNOWN_CONTACT_THREAD,
            "matched_reason": "pinned email matched active payment lane",
        }

        result = outreach.send_known_contact_watch_notification(
            event,
            sender_display_name="Client A",
            lane_label="A/V payment lane",
            grounded_status="invoice still open",
            suggested_response_preview="Draft preview only.",
            send_fn=sent.append,
        )

        assert result["notified"] is True
        assert result["message_id"] == "m-known"
        assert result["thread_id"] == "t-known"
        assert sent == [result["notification_text"]]
        assert "Draft preview only." in sent[0]

    def test_ignored_known_contact_watch_state_does_not_notify(self):
        import cassandra_outreach as outreach

        sent = []
        event = {
            "message_id": "m-known",
            "thread_id": "t-known",
            "sender_email": "client@example.com",
            "contact_nickname": "client_a",
            "contact_tier": "client",
            "watch_state": outreach.IGNORED_NOT_IN_SCOPE_THREAD,
            "ownership_state": outreach.UNASSIGNED_KNOWN_CONTACT_THREAD,
        }

        result = outreach.send_known_contact_watch_notification(event, send_fn=sent.append)

        assert result == {
            "notified": False,
            "reason": "watch_state is not known_contact_watch_notification",
            "message_id": "m-known",
            "thread_id": "t-known",
        }
        assert sent == []

    def test_notification_dispatcher_does_not_create_draft_request_approval_or_call_broker(
        self,
        monkeypatch,
    ):
        import cassandra_brain
        import cassandra_outreach as outreach

        def fail_side_effect(*args, **kwargs):
            raise AssertionError("notification dispatcher must not call side-effect services")

        monkeypatch.setattr(outreach, "create_gmail_draft", fail_side_effect)
        monkeypatch.setattr(outreach, "broker_call", fail_side_effect)
        monkeypatch.setattr(
            cassandra_brain,
            "_start_email_send_after_draft",
            fail_side_effect,
            raising=False,
        )
        sent = []
        event = {
            "message_id": "m-known",
            "thread_id": "t-known",
            "sender_email": "client@example.com",
            "contact_nickname": "client_a",
            "contact_tier": "client",
            "watch_state": outreach.KNOWN_CONTACT_WATCH_NOTIFICATION,
            "ownership_state": outreach.UNASSIGNED_KNOWN_CONTACT_THREAD,
            "matched_reason": "pinned email matched active payment lane",
        }

        result = outreach.send_known_contact_watch_notification(event, send_fn=sent.append)

        assert result["notified"] is True
        assert len(sent) == 1

    def test_notification_only_state_does_not_create_gmail_draft(self, tmp_path, monkeypatch):
        import cassandra_outreach as outreach

        log = tmp_path / "known_contact_watch.jsonl"
        draft_calls = []
        monkeypatch.setattr(outreach, "_KNOWN_CONTACT_WATCH_LOG", log)
        monkeypatch.setattr(
            outreach,
            "create_gmail_draft",
            lambda *args, **kwargs: draft_calls.append((args, kwargs)),
        )

        outreach.record_known_contact_watch_event(
            message_id="m-known",
            thread_id="t-known",
            sender_email="client@example.com",
            contact_nickname="client_a",
            contact_tier="client",
            watch_state=outreach.KNOWN_CONTACT_WATCH_NOTIFICATION,
        )

        assert draft_calls == []
        assert log.exists()

    def test_notification_only_state_does_not_request_send_approval(self, tmp_path, monkeypatch):
        import cassandra_brain
        import cassandra_outreach as outreach

        log = tmp_path / "known_contact_watch.jsonl"
        approval_calls = []
        monkeypatch.setattr(outreach, "_KNOWN_CONTACT_WATCH_LOG", log)
        monkeypatch.setattr(
            cassandra_brain,
            "_start_email_send_after_draft",
            lambda **kwargs: approval_calls.append(kwargs),
            raising=False,
        )

        outreach.record_known_contact_watch_event(
            message_id="m-known",
            thread_id="t-known",
            sender_email="client@example.com",
            contact_nickname="client_a",
            contact_tier="client",
            watch_state=outreach.KNOWN_CONTACT_WATCH_NOTIFICATION,
        )

        assert approval_calls == []
        assert log.exists()

    def test_helper_does_not_change_linked_cassandra_started_thread_matching(self, tmp_path, monkeypatch):
        import cassandra_outreach as outreach

        watch_log = tmp_path / "known_contact_watch.jsonl"
        correspondence_log = tmp_path / "cassandra_correspondence.jsonl"
        outreach_log = tmp_path / "cassandra_outreach.jsonl"
        monkeypatch.setattr(outreach, "_KNOWN_CONTACT_WATCH_LOG", watch_log)
        monkeypatch.setattr(outreach, "_CORRESPONDENCE_LOG", correspondence_log)
        monkeypatch.setattr(outreach, "_OUTREACH_LOG", outreach_log)

        correspondence_log.write_text(
            json.dumps(
                {
                    "ts": "2026-04-29 09:00:00",
                    "recipient": "Client A",
                    "recipient_email": "client@example.com",
                    "state": "sent_confirmed",
                    "subject": "Payment follow-up",
                    "thread_id": "t-started",
                    "route": "email_send",
                }
            )
            + "\n",
            encoding="utf-8",
        )
        outreach.record_known_contact_watch_event(
            message_id="m-watch",
            thread_id="t-watch",
            sender_email="client@example.com",
            contact_nickname="client_a",
            contact_tier="client",
            watch_state=outreach.KNOWN_CONTACT_WATCH_NOTIFICATION,
        )

        match = outreach._match_outbound_email_record(
            {
                "message_id": "m-reply",
                "thread_id": "t-started",
                "from_email": "client@example.com",
                "subject": "Re: Payment follow-up",
            },
            "client@example.com",
        )

        assert match is not None
        assert match["source"] == "correspondence"
        assert match["matched_via"] == "thread_id"
        assert match["thread_id"] == "t-started"


# ── _predict_likely_next_questions ───────────────────────────────────────────

class TestPredictLikelyNextQuestions:
    def test_no_finance_bundles_returns_empty(self, monkeypatch):
        import cassandra_outreach as outreach
        bundles = [{"question": "What color is the sky?", "bundle_id": "q1"}]
        assert outreach._predict_likely_next_questions(bundles) == []

    def test_finance_bundle_with_next_step(self, monkeypatch):
        import cassandra_outreach as outreach
        monkeypatch.setattr(outreach, "get_finance_status_answer",
                            lambda q: "Payment received. Next: Send invoice to client.")
        bundles = [{"question": "Did the payment clear?", "bundle_id": "q1"}]
        result = outreach._predict_likely_next_questions(bundles)
        assert len(result) == 1
        assert result[0]["question"] == "What needs to happen next?"
        assert "Send invoice" in result[0]["because"]
        assert result[0]["bundle_id"] == "q1"

    def test_finance_bundle_no_next_returns_empty(self, monkeypatch):
        import cassandra_outreach as outreach
        monkeypatch.setattr(outreach, "get_finance_status_answer",
                            lambda q: "Payment received. All done.")
        bundles = [{"question": "Did the deposit land?", "bundle_id": "q1"}]
        assert outreach._predict_likely_next_questions(bundles) == []

    def test_empty_bundles(self):
        from cassandra_outreach import _predict_likely_next_questions
        assert _predict_likely_next_questions([]) == []


# ── Brain thin-wrapper smoke tests ──────────────────────────────────────────

class TestBrainCut6WrapperSmoke:
    def test_brain_detect_inner_circle_email_reply_intent(self):
        import cassandra_brain as brain
        assert brain._detect_inner_circle_email_reply_intent("check inner circle email replies") is True
        assert brain._detect_inner_circle_email_reply_intent("unrelated text") is False

    def test_brain_log_email_bridge_event(self, tmp_path, monkeypatch):
        import cassandra_outreach as outreach
        import cassandra_brain as brain
        log = tmp_path / "bridge.jsonl"
        monkeypatch.setattr(outreach, "_EMAIL_BRIDGE_LOG", log)
        brain._log_email_bridge_event(
            message_id="m1",
            thread_id="t1",
            nickname="dad",
            contact_name="Dad",
            sender_email="dad@example.com",
            subject="Hello",
            preview="Preview",
            lane="allowed",
            status="processed",
            unread=True,
        )
        assert log.exists()
        entry = json.loads(log.read_text().strip())
        assert entry["message_id"] == "m1"

    def test_brain_predict_likely_next_questions(self, monkeypatch):
        import cassandra_brain as brain
        monkeypatch.setattr(brain, "get_finance_status_answer",
                            lambda q: "Deposit posted. Next: Confirm with client.")
        bundles = [{"question": "Did the deposit arrive?", "bundle_id": "q1"}]
        result = brain._predict_likely_next_questions(bundles)
        assert len(result) == 1
        assert result[0]["question"] == "What needs to happen next?"
