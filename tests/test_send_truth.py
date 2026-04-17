"""
test_send_truth.py

Unit tests for send-state truth policy in cassandra_brain.py:
  - _handle_send_email() wording
  - _handle_outreach_email_request() wording
  - _log_correspondence_state() log output
"""

import json
import sys
import os
import base64

import pytest

# Ensure project root is on the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ── Helpers ────────────────────────────────────────────────────────────────────

def _make_fake_result(ok: bool, error: str = "") -> dict:
    if ok:
        return {"ok": True}
    return {"ok": False, "error": error}


# ── _handle_send_email() wording tests ────────────────────────────────────────

class TestHandleSendEmailWording:
    def test_brain_wrapper_delegates_to_outreach(self, monkeypatch):
        import cassandra_brain
        import cassandra_outreach

        # Patch outreach resolver to simulate a successful lookup
        monkeypatch.setattr(cassandra_outreach, "_resolve_contact_email", lambda name: ("delegated@example.com", "Delegated User"))
        monkeypatch.setattr(cassandra_brain, "_review_grounded_email_draft", lambda **kwargs: {"status": "allowed", "subject": kwargs["draft_subject"], "body": kwargs["draft_body"], "detail": "", "queued_task_name": None, "user_reply": ""}, raising=False)
        monkeypatch.setattr(cassandra_brain, "_log_correspondence_state", lambda *a, **kw: None, raising=False)
        monkeypatch.setattr(cassandra_brain, "_log_conversation", lambda *a, **kw: None, raising=False)
        monkeypatch.setattr(cassandra_brain, "_start_email_send_after_draft", lambda **kwargs: None, raising=False)
        monkeypatch.setattr("google_access_broker.call", lambda *a, **kw: {"ok": True}, raising=False)

        reply = cassandra_brain._handle_send_email("send email to Test subject: Hi body: Test message")
        assert "Drafted." in reply
        assert "Delegated User" in reply

        # Patch outreach resolver to simulate a failure (no email)
        def raise_runtime(name):
            raise RuntimeError("Contact found for Test but no email address is available.")
        monkeypatch.setattr(cassandra_outreach, "_resolve_contact_email", raise_runtime)
        reply = cassandra_brain._handle_send_email("send email to Test subject: Hi body: Test message")
        assert "no email address" in reply
    """Verify reply strings from _handle_send_email() match draft-state truth policy."""

    def _call(self, monkeypatch, broker_result=None, broker_raises=None,
              text="send email to Dad subject: Hello body: World"):
        import cassandra_brain

        monkeypatch.setattr(cassandra_brain, "load_state", lambda: dict(cassandra_brain._DEFAULT_STATE), raising=False)
        monkeypatch.setattr(cassandra_brain, "save_state", lambda s: None, raising=False)
        monkeypatch.setattr(cassandra_brain, "_log_correspondence_state", lambda *a, **kw: None)
        monkeypatch.setattr(cassandra_brain, "_log_conversation", lambda *a, **kw: None)
        monkeypatch.setattr(cassandra_brain, "_start_email_send_after_draft", lambda **kwargs: None, raising=False)

        # Patch _resolve_recipient_email to return a known address
        monkeypatch.setattr(cassandra_brain, "_resolve_recipient_email",
                            lambda name: ("dad@example.com", "Dad"))
        monkeypatch.setattr(
            cassandra_brain,
            "_review_grounded_email_draft",
            lambda **kwargs: {
                "status": "allowed",
                "subject": kwargs["draft_subject"],
                "body": kwargs["draft_body"],
                "detail": "",
                "queued_task_name": None,
                "user_reply": "",
            },
            raising=False,
        )

        if broker_raises is not None:
            def fake_broker(*args, **kwargs):
                raise broker_raises
            monkeypatch.setattr("google_access_broker.call", fake_broker)
            monkeypatch.setattr(cassandra_brain, "broker_call", fake_broker)
        elif broker_result is not None:
            monkeypatch.setattr("google_access_broker.call", lambda *a, **kw: broker_result)
            monkeypatch.setattr(cassandra_brain, "broker_call", lambda *a, **kw: broker_result)

        return cassandra_brain._handle_send_email(text)

    def test_success_says_drafted(self, monkeypatch):
        reply = self._call(monkeypatch, broker_result=_make_fake_result(True))
        assert reply is not None
        assert "Drafted." in reply
        assert "review" in reply.lower()
        assert "sending" not in reply.lower()
        assert "will send" not in reply.lower()

    def test_denied_says_denied_and_no_draft_created(self, monkeypatch):
        reply = self._call(monkeypatch,
                           broker_result=_make_fake_result(False, "denied at L1 approval gate"))
        assert reply is not None
        assert "denied" in reply.lower()
        assert "No draft was created" in reply
        assert "Drafted." not in reply

    def test_broker_unreachable_says_not_reachable_no_draft_created(self, monkeypatch):
        reply = self._call(monkeypatch, broker_raises=ConnectionError("timeout"))
        assert reply is not None
        assert "isn't reachable" in reply
        assert "No draft was created" in reply
        assert "Drafted." not in reply

    def test_missing_subject_body_says_draft_not_sending(self, monkeypatch):
        reply = self._call(monkeypatch, text="send email to Dad")
        assert reply is not None
        assert "draft" in reply.lower()
        assert "sending" not in reply.lower()
        assert "Sent." not in reply

    def test_generic_error_says_didnt_go_through(self, monkeypatch):
        reply = self._call(monkeypatch,
                           broker_result=_make_fake_result(False, "internal server error"))
        assert reply is not None
        assert "draft didn't go through" in reply
        assert "Drafted." not in reply

    def test_multiline_direct_email_address_triggers_draft_flow(self, monkeypatch):
        import cassandra_brain

        monkeypatch.setattr(cassandra_brain, "load_state", lambda: dict(cassandra_brain._DEFAULT_STATE), raising=False)
        monkeypatch.setattr(cassandra_brain, "save_state", lambda s: None, raising=False)
        monkeypatch.setattr(cassandra_brain, "_log_correspondence_state", lambda *a, **kw: None)
        monkeypatch.setattr(cassandra_brain, "_log_conversation", lambda *a, **kw: None)
        monkeypatch.setattr(cassandra_brain, "_start_email_send_after_draft", lambda **kwargs: None, raising=False)
        monkeypatch.setattr(
            cassandra_brain,
            "_review_grounded_email_draft",
            lambda **kwargs: {
                "status": "allowed",
                "subject": kwargs["draft_subject"],
                "body": kwargs["draft_body"],
                "detail": "",
                "queued_task_name": None,
                "user_reply": "",
            },
            raising=False,
        )
        monkeypatch.setattr("google_access_broker.call", lambda *a, **kw: _make_fake_result(True))
        monkeypatch.setattr(cassandra_brain, "broker_call", lambda *a, **kw: _make_fake_result(True))

        msg = (
            "Send an email to winshipwheatley@gmail.com\n\n"
            "Subject: Cassandra smoke test\n\n"
            "Body:\n"
            "Hi Winship — this is a live reply-bridge smoke test. "
            "Please reply with a short answer so I can verify the email thread handling path end to end."
        )
        reply = cassandra_brain._handle_send_email(msg)
        assert reply is not None
        assert "Drafted." in reply
        assert "winshipwheatley@gmail.com" in reply


class TestParseEmailRequest:
    def test_accepts_multiline_direct_email_recipient(self):
        import cassandra_brain

        msg = (
            "Send an email to winshipwheatley@gmail.com\n\n"
            "Subject: Cassandra smoke test\n\n"
            "Body:\n"
            "Hi Winship"
        )

        parsed = cassandra_brain._parse_email_request(msg)
        assert parsed == {
            "to_name": "winshipwheatley@gmail.com",
            "subject": "Cassandra smoke test",
            "body": "Hi Winship",
        }

    @pytest.mark.parametrize(
        ("text", "expected_name"),
        [
            ("Send Winship a new email", "Winship"),
            ("Send Will a new email", "Will"),
            ("Send my mom a new email", "my mom"),
            ("Send Mr. Wheatley a new email", "Mr. Wheatley"),
            ("Send Mrs. Whealley a new email", "Mrs. Whealley"),
            ("Send an email to Winship", "Winship"),
            ("Send a new email to winshipwheatley@gmail.com", "winshipwheatley@gmail.com"),
        ],
    )
    def test_accepts_recipient_first_email_phrasing(self, text, expected_name):
        import cassandra_brain

        parsed = cassandra_brain._parse_email_request(text)
        assert parsed is not None
        assert parsed["to_name"] == expected_name

    @pytest.mark.parametrize(
        ("text", "expected_name", "expected_body"),
        [
            ("Can you email Winship and ask if thread test 3 is working?", "Winship", "thread test 3 is working?"),
            ("Please send Will a note about tomorrow", "Will", "tomorrow"),
            ("Tell my mom by email that I'll call later", "my mom", "I'll call later"),
            ("I need Draper to know the draft is ready", "Draper", "the draft is ready"),
            ("Could you email Mr. Wheatley and say I'm on the way?", "Mr. Wheatley", "I'm on the way?"),
            ("Send Mrs. Whealley a quick note saying thanks", "Mrs. Whealley", "thanks"),
        ],
    )
    def test_accepts_natural_outbound_email_phrasing(self, text, expected_name, expected_body):
        import cassandra_brain

        parsed = cassandra_brain._parse_email_request(text)
        assert parsed is not None
        assert parsed["to_name"] == expected_name
        assert parsed["subject"] == "Quick note"
        assert parsed["body"] == expected_body


class TestRecipientFirstEmailHandling:
    def test_fully_specified_recipient_first_command_goes_to_draft_flow(self, monkeypatch, tmp_path):
        import cassandra_brain

        nicknames_path = tmp_path / "contact_nicknames.json"
        nicknames_path.write_text(
            json.dumps(
                {
                    "winship": {
                        "name": "Winship Wheatley",
                        "aliases": ["Will"],
                        "tier": "inner_circle",
                        "pinned_email": "winshipwheatley@gmail.com",
                    }
                }
            ),
            encoding="utf-8",
        )

        scheduled = {}
        broker_calls = []

        monkeypatch.setattr(cassandra_brain, "_NICKNAMES_PATH", nicknames_path, raising=False)
        monkeypatch.setattr(cassandra_brain, "load_state", lambda: dict(cassandra_brain._DEFAULT_STATE), raising=False)
        monkeypatch.setattr(cassandra_brain, "save_state", lambda s: None, raising=False)
        monkeypatch.setattr(cassandra_brain, "_log_correspondence_state", lambda *a, **kw: None, raising=False)
        monkeypatch.setattr(cassandra_brain, "_log_conversation", lambda *a, **kw: None, raising=False)
        monkeypatch.setattr(
            cassandra_brain,
            "_review_grounded_email_draft",
            lambda **kwargs: {
                "status": "allowed",
                "subject": kwargs["draft_subject"],
                "body": kwargs["draft_body"],
                "detail": "",
                "queued_task_name": None,
                "user_reply": "",
            },
            raising=False,
        )
        monkeypatch.setattr(
            cassandra_brain,
            "_start_email_send_after_draft",
            lambda **kwargs: scheduled.update(kwargs),
            raising=False,
        )

        def fake_broker(*args, **kwargs):
            params = args[2] if len(args) > 2 else kwargs.get("params")
            broker_calls.append(params)
            return {
                "ok": True,
                "data": {"draft_id": "draft-1", "message_id": "msg-1", "thread_id": "thr-1"},
                "error": "",
            }

        monkeypatch.setattr("google_access_broker.call", fake_broker)
        monkeypatch.setattr(cassandra_brain, "broker_call", fake_broker, raising=False)

        reply = cassandra_brain._handle_send_email(
            "Send Winship a new email subject: Cassandra smoke test body: Hi Winship"
        )

        assert "Drafted." in reply
        assert scheduled["recipient_name"] == "Winship Wheatley"
        assert scheduled["recipient_email"] == "winshipwheatley@gmail.com"
        assert broker_calls[0]["to"] == "winshipwheatley@gmail.com"

    @pytest.mark.parametrize(
        ("text", "expected_email"),
        [
            ("Can you email Winship and ask if thread test 3 is working?", "winshipwheatley@gmail.com"),
            ("Please send Will a note about tomorrow", "winshipwheatley@gmail.com"),
            ("Tell my mom by email that I'll call later", "mom@example.com"),
            ("I need Draper to know the draft is ready", "draper@example.com"),
            ("Could you email Mr. Wheatley and say I'm on the way?", "dad@example.com"),
            ("Send Mrs. Whealley a quick note saying thanks", "mom@example.com"),
        ],
    )
    def test_natural_outbound_email_phrasing_goes_to_draft_flow(self, monkeypatch, tmp_path, text, expected_email):
        import cassandra_brain

        nicknames_path = tmp_path / "contact_nicknames.json"
        nicknames_path.write_text(
            json.dumps(
                {
                    "winship": {
                        "name": "Winship Wheatley",
                        "aliases": ["Will"],
                        "tier": "inner_circle",
                        "pinned_email": "winshipwheatley@gmail.com",
                    },
                    "mom": {
                        "name": "Susan Elizabeth Wheatley",
                        "tier": "inner_circle",
                        "pinned_email": "mom@example.com",
                    },
                    "dad": {
                        "name": "Henry Winship Wheatley III",
                        "tier": "inner_circle",
                        "pinned_email": "dad@example.com",
                    },
                    "draper": {
                        "name": "Draper Carter",
                        "tier": "inner_circle",
                        "pinned_email": "draper@example.com",
                    },
                }
            ),
            encoding="utf-8",
        )

        scheduled = {}
        broker_calls = []

        monkeypatch.setattr(cassandra_brain, "_NICKNAMES_PATH", nicknames_path, raising=False)
        monkeypatch.setattr(cassandra_brain, "load_state", lambda: dict(cassandra_brain._DEFAULT_STATE), raising=False)
        monkeypatch.setattr(cassandra_brain, "save_state", lambda s: None, raising=False)
        monkeypatch.setattr(cassandra_brain, "_log_correspondence_state", lambda *a, **kw: None, raising=False)
        monkeypatch.setattr(cassandra_brain, "_log_conversation", lambda *a, **kw: None, raising=False)
        monkeypatch.setattr(
            cassandra_brain,
            "_review_grounded_email_draft",
            lambda **kwargs: {
                "status": "allowed",
                "subject": kwargs["draft_subject"],
                "body": kwargs["draft_body"],
                "detail": "",
                "queued_task_name": None,
                "user_reply": "",
            },
            raising=False,
        )
        monkeypatch.setattr(
            cassandra_brain,
            "_start_email_send_after_draft",
            lambda **kwargs: scheduled.update(kwargs),
            raising=False,
        )

        def fake_broker(*args, **kwargs):
            params = args[2] if len(args) > 2 else kwargs.get("params")
            broker_calls.append(params)
            return {
                "ok": True,
                "data": {"draft_id": "draft-1", "message_id": "msg-1", "thread_id": "thr-1"},
                "error": "",
            }

        monkeypatch.setattr("google_access_broker.call", fake_broker)
        monkeypatch.setattr(cassandra_brain, "broker_call", fake_broker, raising=False)

        reply = cassandra_brain._handle_send_email(text)

        assert "Drafted." in reply
        assert scheduled["recipient_email"] == expected_email
        assert broker_calls[0]["to"] == expected_email


class TestOutboundContactResolutionHardening:
    def _call(self, monkeypatch, tmp_path, *, text: str, nicknames: dict):
        import cassandra_brain

        nicknames_path = tmp_path / "contact_nicknames.json"
        nicknames_path.write_text(json.dumps(nicknames), encoding="utf-8")

        broker_calls = []
        scheduled = {}

        monkeypatch.setattr(cassandra_brain, "_NICKNAMES_PATH", nicknames_path, raising=False)
        monkeypatch.setattr(cassandra_brain, "load_state", lambda: dict(cassandra_brain._DEFAULT_STATE), raising=False)
        monkeypatch.setattr(cassandra_brain, "save_state", lambda s: None, raising=False)
        monkeypatch.setattr(cassandra_brain, "_log_correspondence_state", lambda *a, **kw: None, raising=False)
        monkeypatch.setattr(cassandra_brain, "_log_conversation", lambda *a, **kw: None, raising=False)
        monkeypatch.setattr(
            cassandra_brain,
            "_review_grounded_email_draft",
            lambda **kwargs: {
                "status": "allowed",
                "subject": kwargs["draft_subject"],
                "body": kwargs["draft_body"],
                "detail": "",
                "queued_task_name": None,
                "user_reply": "",
            },
            raising=False,
        )
        monkeypatch.setattr(
            cassandra_brain,
            "_start_email_send_after_draft",
            lambda **kwargs: scheduled.update(kwargs),
            raising=False,
        )

        def fake_broker(*args, **kwargs):
            params = args[2] if len(args) > 2 else kwargs.get("params")
            broker_calls.append(params)
            return {
                "ok": True,
                "data": {"draft_id": "draft-1", "message_id": "msg-1", "thread_id": "thr-1"},
                "error": "",
            }

        monkeypatch.setattr("google_access_broker.call", fake_broker)
        monkeypatch.setattr(cassandra_brain, "broker_call", fake_broker, raising=False)

        reply = cassandra_brain._handle_send_email(text)
        return reply, broker_calls, scheduled

    def test_exact_alias_match_drafts_immediately(self, monkeypatch, tmp_path):
        reply, broker_calls, scheduled = self._call(
            monkeypatch,
            tmp_path,
            text="send Will subject: Hi body: Checking in.",
            nicknames={
                "winship": {
                    "name": "Winship Wheatley",
                    "aliases": ["Will"],
                    "tier": "inner_circle",
                    "pinned_email": "winship@example.com",
                }
            },
        )

        assert "Drafted." in reply
        assert scheduled["recipient_name"] == "Winship Wheatley"
        assert scheduled["recipient_email"] == "winship@example.com"
        assert broker_calls[0]["to"] == "winship@example.com"

    def test_my_mom_and_my_dad_resolve_locally(self, monkeypatch, tmp_path):
        nicknames = {
            "mom": {
                "name": "Susan Wheatley",
                "tier": "inner_circle",
                "pinned_email": "mom@example.com",
            },
            "dad": {
                "name": "Henry Wheatley",
                "tier": "inner_circle",
                "pinned_email": "dad@example.com",
            },
        }

        mom_reply, mom_calls, _ = self._call(
            monkeypatch,
            tmp_path,
            text="send my mom subject: Hi body: Love you.",
            nicknames=nicknames,
        )
        dad_reply, dad_calls, _ = self._call(
            monkeypatch,
            tmp_path,
            text="send my dad subject: Hi body: Love you.",
            nicknames=nicknames,
        )

        assert "Susan Wheatley" in mom_reply
        assert mom_calls[0]["to"] == "mom@example.com"
        assert "Henry Wheatley" in dad_reply
        assert dad_calls[0]["to"] == "dad@example.com"

    def test_mr_and_mrs_wheatley_resolve_exactly(self, monkeypatch, tmp_path):
        nicknames = {
            "mom": {
                "name": "Susan Elizabeth Wheatley",
                "tier": "inner_circle",
                "pinned_email": "mom@example.com",
            },
            "dad": {
                "name": "Henry Winship Wheatley III",
                "tier": "inner_circle",
                "pinned_email": "dad@example.com",
            },
        }

        mrs_reply, mrs_calls, _ = self._call(
            monkeypatch,
            tmp_path,
            text="send Mrs. Wheatley subject: Hi body: Checking in.",
            nicknames=nicknames,
        )
        mr_reply, mr_calls, _ = self._call(
            monkeypatch,
            tmp_path,
            text="send Mr. Wheatley subject: Hi body: Checking in.",
            nicknames=nicknames,
        )

        assert "Susan Elizabeth Wheatley" in mrs_reply
        assert mrs_calls[0]["to"] == "mom@example.com"
        assert "Henry Winship Wheatley III" in mr_reply
        assert mr_calls[0]["to"] == "dad@example.com"

    def test_likely_misspelling_resolves_with_confirmation_note(self, monkeypatch, tmp_path):
        reply, broker_calls, scheduled = self._call(
            monkeypatch,
            tmp_path,
            text="send Mrs. Whealley subject: Hi body: Checking in.",
            nicknames={
                "mom": {
                    "name": "Susan Elizabeth Wheatley",
                    "tier": "inner_circle",
                    "pinned_email": "mom@example.com",
                }
            },
        )

        assert "Drafted." in reply
        assert "I drafted this to Mrs. Wheatley. If you meant someone else, tell me before approval." in reply
        assert scheduled["recipient_name"] == "Susan Elizabeth Wheatley"
        assert broker_calls[0]["to"] == "mom@example.com"

    def test_ambiguous_match_requires_clarification(self, monkeypatch, tmp_path):
        reply, broker_calls, scheduled = self._call(
            monkeypatch,
            tmp_path,
            text="send Wheatley subject: Hi body: Checking in.",
            nicknames={
                "mom": {
                    "name": "Susan Elizabeth Wheatley",
                    "tier": "inner_circle",
                    "pinned_email": "mom@example.com",
                },
                "dad": {
                    "name": "Henry Winship Wheatley III",
                    "tier": "inner_circle",
                    "pinned_email": "dad@example.com",
                },
            },
        )

        assert "multiple plausible contacts" in reply
        assert "Henry Winship Wheatley III" in reply
        assert "Susan Elizabeth Wheatley" in reply
        assert broker_calls == []
        assert scheduled == {}


class TestGroundedEmailReviewGate:
    """Verify the grounded review gate runs inside Cassandra's email draft flow."""

    def _call(
        self,
        monkeypatch,
        tmp_path,
        *,
        text: str,
        contact_nickname: str,
        contact_name: str,
        contact_email: str,
        payment_ctx: str = "",
    ):
        import cassandra_brain

        nicknames_path = tmp_path / "contact_nicknames.json"
        nicknames_path.write_text(
            json.dumps(
                {
                    contact_nickname: {
                        "name": contact_name,
                        "tier": "inner_circle",
                        "pinned_email": contact_email,
                    }
                }
            ),
            encoding="utf-8",
        )

        broker_calls = []

        monkeypatch.setattr(cassandra_brain, "load_state", lambda: dict(cassandra_brain._DEFAULT_STATE), raising=False)
        monkeypatch.setattr(cassandra_brain, "save_state", lambda s: None, raising=False)
        monkeypatch.setattr(cassandra_brain, "_log_correspondence_state", lambda *a, **kw: None, raising=False)
        monkeypatch.setattr(cassandra_brain, "_log_conversation", lambda *a, **kw: None, raising=False)
        monkeypatch.setattr(cassandra_brain, "_start_email_send_after_draft", lambda **kwargs: None, raising=False)
        monkeypatch.setattr(cassandra_brain, "_NICKNAMES_PATH", nicknames_path, raising=False)
        monkeypatch.setattr(
            cassandra_brain,
            "_resolve_recipient_email",
            lambda name: (contact_email, contact_name),
            raising=False,
        )
        monkeypatch.setattr(cassandra_brain, "_fetch_payment_verify_context", lambda query: payment_ctx, raising=False)
        monkeypatch.setattr(cassandra_brain, "_fetch_calendar_context", lambda query: "", raising=False)

        def fake_broker(*args, **kwargs):
            params = args[2] if len(args) > 2 else kwargs.get("params")
            broker_calls.append(params)
            return {"ok": True, "data": {"draft_id": "draft-1"}, "error": ""}

        monkeypatch.setattr("google_access_broker.call", fake_broker)
        monkeypatch.setattr(cassandra_brain, "broker_call", fake_broker, raising=False)

        reply = cassandra_brain._handle_send_email(text)
        return reply, broker_calls

    def test_grounded_answer_allowed(self, monkeypatch, tmp_path):
        reply, broker_calls = self._call(
            monkeypatch,
            tmp_path,
            text="send email to Dad subject: Hilton update body: I checked and the Hilton payment came through.",
            contact_nickname="dad",
            contact_name="Dad",
            contact_email="dad@example.com",
            payment_ctx="[VERIFIED GMAIL NOTIFICATIONS — recent payment-related emails]\nFrom: Capital Hilton",
        )

        assert "Drafted." in reply
        assert len(broker_calls) == 1
        assert broker_calls[0]["body"] == "I checked and the Hilton payment came through."

    def test_draft_success_launches_background_send_flow(self, monkeypatch, tmp_path):
        import cassandra_brain

        monkeypatch.setattr(cassandra_brain, "load_state", lambda: dict(cassandra_brain._DEFAULT_STATE), raising=False)
        monkeypatch.setattr(cassandra_brain, "save_state", lambda s: None, raising=False)
        monkeypatch.setattr(cassandra_brain, "_log_correspondence_state", lambda *a, **kw: None, raising=False)
        monkeypatch.setattr(cassandra_brain, "_log_conversation", lambda *a, **kw: None, raising=False)
        tmp_nicknames = tmp_path / "contact_nicknames.json"
        tmp_nicknames.write_text(
            json.dumps(
                {
                    "dad": {
                        "name": "Henry Winship Wheatley III",
                        "tier": "inner_circle",
                        "pinned_email": "dad@example.com",
                    }
                }
            ),
            encoding="utf-8",
        )
        monkeypatch.setattr(cassandra_brain, "_NICKNAMES_PATH", tmp_nicknames, raising=False)
        monkeypatch.setattr(
            cassandra_brain,
            "_review_grounded_email_draft",
            lambda **kwargs: {
                "status": "allowed",
                "subject": kwargs["draft_subject"],
                "body": kwargs["draft_body"],
                "detail": "",
                "queued_task_name": None,
                "user_reply": "",
            },
            raising=False,
        )

        scheduled = {}

        monkeypatch.setattr("google_access_broker.call", lambda *a, **kw: {"ok": True, "data": {"draft_id": "draft-1", "message_id": "msg-1", "thread_id": "thr-1"}, "error": ""})
        monkeypatch.setattr(cassandra_brain, "broker_call", lambda *a, **kw: {"ok": True, "data": {"draft_id": "draft-1", "message_id": "msg-1", "thread_id": "thr-1"}, "error": ""}, raising=False)
        monkeypatch.setattr(
            cassandra_brain,
            "_start_email_send_after_draft",
            lambda **kwargs: scheduled.update(kwargs),
            raising=False,
        )

        reply = cassandra_brain._handle_send_email("send email to Dad subject: Hi body: Test message")

        assert "Drafted." in reply
        assert scheduled["recipient_name"] == "Henry Winship Wheatley III"
        assert scheduled["recipient_email"] == "dad@example.com"
        assert scheduled["subject"] == "Hi"
        assert scheduled["body"] == "Test message"
        assert scheduled["draft_id"] == "draft-1"

    def test_background_send_flow_logs_approval_then_sent(self, monkeypatch, tmp_path):
        import cassandra_brain

        events = []
        broker_calls = []

        monkeypatch.setattr(
            cassandra_brain,
            "_log_correspondence_state",
            lambda recipient, state, detail="", route="", metadata=None: events.append(
                {
                    "recipient": recipient,
                    "state": state,
                    "detail": detail,
                    "route": route,
                    "metadata": metadata or {},
                }
            ),
            raising=False,
        )
        monkeypatch.setattr(
            cassandra_brain,
            "broker_call",
            lambda agent, capability, params: broker_calls.append((agent, capability, params)) or {
                "ok": True,
                "data": {"message_id": "sent-1", "thread_id": "thread-1"},
                "error": "",
            },
            raising=False,
        )

        cassandra_brain._run_email_send_after_draft(
            recipient_name="Dad",
            recipient_email="dad@example.com",
            subject="Hi",
            body="Test message",
            review_inbox="winshiplive@gmail.com",
            draft_id="draft-1",
            draft_message_id="draft-msg-1",
            draft_thread_id="draft-thread-1",
            reply_thread_id="source-thread-1",
            reply_in_reply_to="<source-msg-0@example.com>",
            reply_references="<source-msg-0@example.com>",
        )

        assert [event["state"] for event in events] == [
            cassandra_brain._SS_AWAITING_APPROVAL,
            cassandra_brain._SS_SENT_CONFIRMED,
        ]
        assert events[0]["metadata"]["draft_id"] == "draft-1"
        assert events[0]["metadata"]["reply_thread_id"] == "source-thread-1"
        assert events[1]["metadata"]["message_id"] == "sent-1"
        assert broker_calls[0][1] == "google.gmail.send"
        assert broker_calls[0][2]["thread_id"] == "source-thread-1"
        assert broker_calls[0][2]["in_reply_to"] == "<source-msg-0@example.com>"
        assert broker_calls[0][2]["references"] == "<source-msg-0@example.com>"

    def test_lane_violation_blocked(self, monkeypatch, tmp_path):
        reply, broker_calls = self._call(
            monkeypatch,
            tmp_path,
            text="send email to Draper subject: Revenue body: The total revenue is $100,000.",
            contact_nickname="draper",
            contact_name="Draper",
            contact_email="draper@example.com",
        )

        assert "trust lane" in reply.lower()
        assert broker_calls == []

    def test_uncertainty_is_rewritten(self, monkeypatch, tmp_path):
        reply, broker_calls = self._call(
            monkeypatch,
            tmp_path,
            text="send email to Dad subject: Hilton update body: I confirmed the Hilton payment came through.",
            contact_nickname="dad",
            contact_name="Dad",
            contact_email="dad@example.com",
            payment_ctx="[VERIFIED PAYMENT DATA — no recent Gmail notifications found]",
        )

        assert "Drafted." in reply
        assert "tightened the wording" in reply
        assert len(broker_calls) == 1
        assert broker_calls[0]["body"].startswith("I don't want to overstate what I can confirm.")
        assert "don't have confirmation" in broker_calls[0]["body"]

    def test_capability_gap_is_queued(self, monkeypatch, tmp_path):
        import cassandra_brain

        tasks_dir = tmp_path / "tasks"
        archive_dir = tmp_path / "archive"
        tasks_dir.mkdir()
        archive_dir.mkdir()

        monkeypatch.setattr(cassandra_brain, "_POLISH_TASKS_DIR", tasks_dir, raising=False)
        monkeypatch.setattr(cassandra_brain, "_POLISH_ARCHIVE", archive_dir, raising=False)
        monkeypatch.setattr(cassandra_brain, "_POLISH_STATUS", tmp_path / "status.json", raising=False)
        monkeypatch.setattr(cassandra_brain, "_POLISH_TASK_FILE", tmp_path / "task.md", raising=False)

        reply, broker_calls = self._call(
            monkeypatch,
            tmp_path,
            text="send email to Dad subject: Contract body: I can send that directly from here.",
            contact_nickname="dad",
            contact_name="Dad",
            contact_email="dad@example.com",
        )

        assert "capability" in reply.lower()
        assert broker_calls == []
        task_files = list(tasks_dir.glob("cas-upgrade-email_send-*.md"))
        assert len(task_files) == 1
        task_text = task_files[0].read_text(encoding="utf-8")
        assert "execution mode: human-supervised" in task_text

    def test_smoke_test_body_does_not_false_positive_email_send_gap(self, monkeypatch, tmp_path):
        reply, broker_calls = self._call(
            monkeypatch,
            tmp_path,
            text=(
                "Send an email to winshipwheatley@gmail.com\n\n"
                "Subject: Cassandra smoke test\n\n"
                "Body:\n"
                "Hi Winship — this is a live reply-bridge smoke test. "
                "Please reply with a short answer so I can verify the email thread handling path end to end."
            ),
            contact_nickname="dad",
            contact_name="Dad",
            contact_email="dad@example.com",
        )

        assert "capability" not in reply.lower()
        assert "Drafted." in reply
        assert len(broker_calls) == 1


# ── _handle_outreach_email_request() wording tests ───────────────────────────

class TestHandleOutreachEmailWording:
    """Verify reply strings from _handle_outreach_email_request() match policy."""

    def _call(self, monkeypatch, outreach_results):
        import cassandra_brain

        monkeypatch.setattr(cassandra_brain, "load_state", lambda: dict(cassandra_brain._DEFAULT_STATE), raising=False)
        monkeypatch.setattr(cassandra_brain, "save_state", lambda s: None, raising=False)
        monkeypatch.setattr(cassandra_brain, "_log_correspondence_state", lambda *a, **kw: None)
        monkeypatch.setattr(cassandra_brain, "_log_conversation", lambda *a, **kw: None)
        monkeypatch.setattr("cassandra_outreach.run_outreach", lambda dry_run=False, mode="draft": outreach_results)

        return cassandra_brain._handle_outreach_email_request("send the intro emails")

    def test_all_drafted_reply(self, monkeypatch):
        reply = self._call(monkeypatch, [
            {"nickname": "draper", "display_name": "Draper", "status": "draft"},
            {"nickname": "dad", "display_name": "Dad", "status": "draft"},
        ])
        assert reply is not None
        assert "draft" in reply.lower()
        assert "Draper" in reply
        assert "Dad" in reply

    def test_partial_says_drafted_and_didnt_go_through(self, monkeypatch):
        reply = self._call(monkeypatch, [
            {"nickname": "draper", "display_name": "Draper", "status": "draft"},
            {"nickname": "dad", "display_name": "Dad", "status": "send_failed"},
        ])
        assert reply is not None
        assert "Drafted for" in reply
        assert "didn't go through" in reply
        assert "need attention" not in reply

    def test_all_failed_says_no_drafts_created(self, monkeypatch):
        reply = self._call(monkeypatch, [
            {"nickname": "draper", "display_name": "Draper", "status": "send_failed"},
        ])
        assert reply is not None
        assert "didn't go through" in reply
        assert "No drafts were created" in reply
        assert "Drafted" not in reply

    def test_exception_says_nothing_sent(self, monkeypatch):
        import cassandra_brain
        monkeypatch.setattr(cassandra_brain, "load_state", lambda: dict(cassandra_brain._DEFAULT_STATE), raising=False)
        monkeypatch.setattr(cassandra_brain, "save_state", lambda s: None, raising=False)
        monkeypatch.setattr(cassandra_brain, "_log_correspondence_state", lambda *a, **kw: None)
        monkeypatch.setattr(cassandra_brain, "_log_conversation", lambda *a, **kw: None)
        monkeypatch.setattr("cassandra_outreach.run_outreach",
                            lambda dry_run=False, mode="draft": (_ for _ in ()).throw(RuntimeError("broker down")))
        reply = cassandra_brain._handle_outreach_email_request("send the intro emails")
        assert reply is not None
        assert "No drafts were created" in reply
        assert "Drafted" not in reply


# ── _log_correspondence_state() log output tests ──────────────────────────────

class TestLogCorrespondenceState:
    """Verify _log_correspondence_state() writes valid JSONL entries."""

    def test_writes_valid_json_line(self, tmp_path, monkeypatch):
        import cassandra_brain
        log_path = tmp_path / "cassandra_correspondence.jsonl"
        monkeypatch.setattr(cassandra_brain, "_CORRESPONDENCE_LOG", log_path)

        cassandra_brain._log_correspondence_state("Dad", "sent_confirmed", "subject=test")

        lines = log_path.read_text().splitlines()
        assert len(lines) == 1
        entry = json.loads(lines[0])
        assert entry["recipient"] == "Dad"
        assert entry["state"] == "sent_confirmed"
        assert entry["detail"] == "subject=test"
        assert "ts" in entry

    def test_sent_confirmed_state(self, tmp_path, monkeypatch):
        import cassandra_brain
        log_path = tmp_path / "cassandra_correspondence.jsonl"
        monkeypatch.setattr(cassandra_brain, "_CORRESPONDENCE_LOG", log_path)

        cassandra_brain._log_correspondence_state("Dad", cassandra_brain._SS_SENT_CONFIRMED)

        entry = json.loads(log_path.read_text().strip())
        assert entry["state"] == "sent_confirmed"

    def test_blocked_state(self, tmp_path, monkeypatch):
        import cassandra_brain
        log_path = tmp_path / "cassandra_correspondence.jsonl"
        monkeypatch.setattr(cassandra_brain, "_CORRESPONDENCE_LOG", log_path)

        cassandra_brain._log_correspondence_state("Dad", cassandra_brain._SS_BLOCKED, "denied at approval gate")

        entry = json.loads(log_path.read_text().strip())
        assert entry["state"] == "blocked"
        assert "denied" in entry["detail"]

    def test_send_failed_state(self, tmp_path, monkeypatch):
        import cassandra_brain
        log_path = tmp_path / "cassandra_correspondence.jsonl"
        monkeypatch.setattr(cassandra_brain, "_CORRESPONDENCE_LOG", log_path)

        cassandra_brain._log_correspondence_state("Dad", cassandra_brain._SS_SEND_FAILED, "smtp error")

        entry = json.loads(log_path.read_text().strip())
        assert entry["state"] == "send_failed"


def _decode_raw_message(raw: str) -> str:
    padding = "=" * (-len(raw) % 4)
    return base64.urlsafe_b64decode(raw + padding).decode("utf-8", errors="ignore")


class TestGoogleBrokerReplyThreadBinding:
    def test_gmail_draft_create_binds_thread_and_reply_headers(self, monkeypatch):
        import google_access_broker as broker

        captured = {}

        class FakeDraftCreateCall:
            def execute(self):
                return {"id": "draft-1", "message": {"id": "msg-1", "threadId": "thread-123"}}

        class FakeDrafts:
            def create(self, userId, body):
                captured["userId"] = userId
                captured["body"] = body
                return FakeDraftCreateCall()

        class FakeUsers:
            def drafts(self):
                return FakeDrafts()

        class FakeService:
            def users(self):
                return FakeUsers()

        monkeypatch.setitem(
            sys.modules,
            "googleapiclient.discovery",
            type("DiscoveryModule", (), {"build": lambda *args, **kwargs: FakeService()})(),
        )

        result = broker._exec_gmail_draft_create(
            object(),
            {
                "to": "winshipwheatley@gmail.com",
                "cc": "winshiplive@gmail.com",
                "subject": "Re: Cassandra smoke test",
                "body": "Thanks for the note.",
                "thread_id": "thread-123",
                "in_reply_to": "<source@example.com>",
                "references": "<source@example.com>",
            },
        )

        assert result["ok"] is True
        assert captured["body"]["message"]["threadId"] == "thread-123"
        raw = _decode_raw_message(captured["body"]["message"]["raw"])
        assert "In-Reply-To: <source@example.com>" in raw
        assert "References: <source@example.com>" in raw

    def test_gmail_send_binds_thread_and_reply_headers(self, monkeypatch):
        import google_access_broker as broker

        captured = {}

        class FakeSendCall:
            def execute(self):
                return {"id": "sent-1", "threadId": "thread-123"}

        class FakeMessages:
            def send(self, userId, body):
                captured["userId"] = userId
                captured["body"] = body
                return FakeSendCall()

        class FakeUsers:
            def messages(self):
                return FakeMessages()

        class FakeService:
            def users(self):
                return FakeUsers()

        monkeypatch.setitem(
            sys.modules,
            "googleapiclient.discovery",
            type("DiscoveryModule", (), {"build": lambda *args, **kwargs: FakeService()})(),
        )

        result = broker._exec_gmail_send(
            object(),
            {
                "to": "winshipwheatley@gmail.com",
                "cc": "winshiplive@gmail.com",
                "subject": "Re: Cassandra smoke test",
                "body": "Thanks for the note.",
                "thread_id": "thread-123",
                "in_reply_to": "<source@example.com>",
                "references": "<source@example.com>",
            },
        )

        assert result["ok"] is True
        assert captured["body"]["threadId"] == "thread-123"
        raw = _decode_raw_message(captured["body"]["raw"])
        assert "In-Reply-To: <source@example.com>" in raw
        assert "References: <source@example.com>" in raw

    def test_after_successful_send_log_contains_draft(self, tmp_path, monkeypatch):
        import cassandra_brain
        log_path = tmp_path / "cassandra_correspondence.jsonl"
        monkeypatch.setattr(cassandra_brain, "_CORRESPONDENCE_LOG", log_path)
        monkeypatch.setattr(cassandra_brain, "_resolve_recipient_email",
                            lambda name: ("dad@example.com", "Dad"))
        monkeypatch.setattr(
            cassandra_brain,
            "_review_grounded_email_draft",
            lambda **kwargs: {
                "status": "allowed",
                "subject": kwargs["draft_subject"],
                "body": kwargs["draft_body"],
                "detail": "",
                "queued_task_name": None,
                "user_reply": "",
            },
            raising=False,
        )
        monkeypatch.setattr("google_access_broker.call", lambda *a, **kw: {"ok": True})
        monkeypatch.setattr(cassandra_brain, "broker_call", lambda *a, **kw: {"ok": True})
        monkeypatch.setattr(cassandra_brain, "_log_conversation", lambda *a, **kw: None)

        cassandra_brain._handle_send_email("send email to Dad subject: Hi body: Test message")

        lines = [json.loads(l) for l in log_path.read_text().splitlines()]
        states = [l["state"] for l in lines]
        assert "draft" in states

    def test_after_denied_send_log_contains_blocked(self, tmp_path, monkeypatch):
        import cassandra_brain
        log_path = tmp_path / "cassandra_correspondence.jsonl"
        monkeypatch.setattr(cassandra_brain, "_CORRESPONDENCE_LOG", log_path)
        monkeypatch.setattr(cassandra_brain, "_resolve_recipient_email",
                            lambda name: ("dad@example.com", "Dad"))
        monkeypatch.setattr(
            cassandra_brain,
            "_review_grounded_email_draft",
            lambda **kwargs: {
                "status": "allowed",
                "subject": kwargs["draft_subject"],
                "body": kwargs["draft_body"],
                "detail": "",
                "queued_task_name": None,
                "user_reply": "",
            },
            raising=False,
        )
        monkeypatch.setattr("google_access_broker.call",
                            lambda *a, **kw: {"ok": False, "error": "denied at L1 approval gate"})
        monkeypatch.setattr(cassandra_brain, "broker_call",
                            lambda *a, **kw: {"ok": False, "error": "denied at L1 approval gate"})
        monkeypatch.setattr(cassandra_brain, "_log_conversation", lambda *a, **kw: None)

        cassandra_brain._handle_send_email("send email to Dad subject: Hi body: Test message")

        lines = [json.loads(l) for l in log_path.read_text().splitlines()]
        states = [l["state"] for l in lines]
        assert "blocked" in states

    def test_after_failed_send_log_contains_send_failed(self, tmp_path, monkeypatch):
        import cassandra_brain
        log_path = tmp_path / "cassandra_correspondence.jsonl"
        monkeypatch.setattr(cassandra_brain, "_CORRESPONDENCE_LOG", log_path)
        monkeypatch.setattr(cassandra_brain, "_resolve_recipient_email",
                            lambda name: ("dad@example.com", "Dad"))
        monkeypatch.setattr(
            cassandra_brain,
            "_review_grounded_email_draft",
            lambda **kwargs: {
                "status": "allowed",
                "subject": kwargs["draft_subject"],
                "body": kwargs["draft_body"],
                "detail": "",
                "queued_task_name": None,
                "user_reply": "",
            },
            raising=False,
        )
        monkeypatch.setattr("google_access_broker.call",
                            lambda *a, **kw: {"ok": False, "error": "smtp error"})
        monkeypatch.setattr(cassandra_brain, "broker_call",
                            lambda *a, **kw: {"ok": False, "error": "smtp error"})
        monkeypatch.setattr(cassandra_brain, "_log_conversation", lambda *a, **kw: None)

        cassandra_brain._handle_send_email("send email to Dad subject: Hi body: Test message")

        lines = [json.loads(l) for l in log_path.read_text().splitlines()]
        states = [l["state"] for l in lines]
        assert "send_failed" in states


# ── No false-positive "Drafted" claims ────────────────────────────────────────

class TestNoFalsePositiveSentClaims:
    """Grep-level check: 'Drafted.' appears only on the ok=True path."""

    def test_drafted_only_on_ok_path(self):
        src_path = os.path.join(os.path.dirname(__file__), "..", "cassandra_brain.py")
        with open(src_path) as f:
            src = f.read()

        # Extract _handle_send_email body
        start = src.index("def _handle_send_email")
        end = src.index("\ndef ", start + 1)
        body = src[start:end]

        # "Drafted." (sentence start) must appear exactly once — on the ok branch
        count = body.count('"Drafted.')
        assert count <= 1, (
            f"Found {count} occurrences of 'Drafted.' in _handle_send_email — "
            "should be exactly 1 (ok path only)"
        )

    def test_need_attention_removed(self):
        src_path = os.path.join(os.path.dirname(__file__), "..", "cassandra_brain.py")
        with open(src_path) as f:
            src = f.read()
        assert "need attention" not in src, (
            "'need attention' wording found in cassandra_brain.py — should be removed"
        )
