import copy
import os
import sys
import json
from datetime import datetime, timedelta


sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def _stub_llm_path(monkeypatch, cassandra_brain, llm_reply: str):
    monkeypatch.setattr(cassandra_brain, "load_state", lambda: dict(cassandra_brain._DEFAULT_STATE), raising=False)
    monkeypatch.setattr(cassandra_brain, "save_state", lambda state: None, raising=False)
    monkeypatch.setattr(cassandra_brain, "process_pending_followups", lambda: [], raising=False)
    monkeypatch.setattr(cassandra_brain, "build_context_snapshot", lambda state=None: "", raising=False)
    monkeypatch.setattr(cassandra_brain, "_fetch_calendar_context", lambda query, **kwargs: "", raising=False)
    monkeypatch.setattr(cassandra_brain, "_fetch_gmail_context", lambda query, **kwargs: "", raising=False)
    monkeypatch.setattr(cassandra_brain, "_fetch_contacts_context", lambda query, **kwargs: "", raising=False)
    monkeypatch.setattr(cassandra_brain, "_fetch_payment_verify_context", lambda query, **kwargs: "", raising=False)
    monkeypatch.setattr(cassandra_brain, "registry_context_for_query", lambda query: None, raising=False)
    monkeypatch.setattr(cassandra_brain, "_should_use_deep", lambda query: False, raising=False)
    monkeypatch.setattr(cassandra_brain, "_call", lambda prompt, *args, **kwargs: llm_reply, raising=False)
    monkeypatch.setattr(cassandra_brain, "_pii_tokenize", lambda prompt: (prompt, None), raising=False)
    monkeypatch.setattr(cassandra_brain, "_pii_rehydrate_reply", lambda reply, ctx: reply, raising=False)
    monkeypatch.setattr(cassandra_brain, "_cassandra_context_clean", lambda *args, **kwargs: False, raising=False)


def test_hilton_payment_question_routes_directly(monkeypatch):
    import cassandra_brain

    logged = []
    monkeypatch.setattr(cassandra_brain, "load_state", lambda: dict(cassandra_brain._DEFAULT_STATE), raising=False)
    monkeypatch.setattr(cassandra_brain, "save_state", lambda state: None, raising=False)
    monkeypatch.setattr(cassandra_brain, "process_pending_followups", lambda: [], raising=False)
    monkeypatch.setattr(
        cassandra_brain,
        "_handle_payment_verification_request",
        lambda text: "I checked the Hilton payment directly.",
        raising=False,
    )
    monkeypatch.setattr(
        cassandra_brain,
        "_log_conversation",
        lambda user_text, replies, route="llm", **kwargs: logged.append({"route": route, "replies": replies}),
        raising=False,
    )
    replies = cassandra_brain.handle("Did the Hilton payment come through?")

    assert replies == ["I checked the Hilton payment directly."]
    assert logged[-1]["route"] == "payment_verify"


def test_payment_question_rescues_file_style_llm_fallback(monkeypatch):
    import cassandra_brain

    logged = []
    _stub_llm_path(
        monkeypatch,
        cassandra_brain,
        "I can't verify that path from here. Direct check on your end.",
    )
    monkeypatch.setattr(cassandra_brain, "_detect_payment_verify_intent", lambda text: False, raising=False)
    monkeypatch.setattr(
        cassandra_brain,
        "_handle_payment_verification_request",
        lambda text: "I checked your recent Gmail notifications but didn't see any matching that payment yet.",
        raising=False,
    )
    monkeypatch.setattr(
        cassandra_brain,
        "_log_conversation",
        lambda user_text, replies, route="llm", **kwargs: logged.append({"route": route, "replies": replies}),
        raising=False,
    )
    replies = cassandra_brain.handle("Did the Hilton payment come through?")

    assert replies == ["I checked your recent Gmail notifications but didn't see any matching that payment yet."]
    assert "path" not in replies[0].lower()
    assert logged[-1]["route"] == "payment_verify_rescue"


def test_payment_question_rescues_generic_payment_limit_reply(monkeypatch):
    import cassandra_brain

    logged = []
    _stub_llm_path(
        monkeypatch,
        cassandra_brain,
        "I can't verify deposit or payment status — no external access. "
        "What I have is the log entry. The account is the source of truth.",
    )
    monkeypatch.setattr(cassandra_brain, "_detect_payment_verify_intent", lambda text: False, raising=False)
    monkeypatch.setattr(
        cassandra_brain,
        "_handle_payment_verification_request",
        lambda text: "I tried to check your Gmail for payment notifications but the service is unreachable right now.",
        raising=False,
    )
    monkeypatch.setattr(
        cassandra_brain,
        "_log_conversation",
        lambda user_text, replies, route="llm", **kwargs: logged.append({"route": route, "replies": replies}),
        raising=False,
    )
    replies = cassandra_brain.handle("Did the Hilton payment come through?")

    assert replies == ["I tried to check your Gmail for payment notifications but the service is unreachable right now."]
    assert "account is the source of truth" not in replies[0].lower()
    assert logged[-1]["route"] == "payment_verify_rescue"


def test_hilton_payment_question_prefers_canonical_reality(tmp_path, monkeypatch):
    import cassandra_brain
    import finance_state

    reality_path = tmp_path / "cassandra_reality_notes.json"
    finance_path = tmp_path / "finance_state.json"
    finance_path.write_text(json.dumps({"accounts": {}}), encoding="utf-8")
    reality_path.write_text(
        json.dumps(
            {
                "capital_hilton": {
                    "label": "Capital Hilton",
                    "aliases": ["capital hilton", "hilton", "smartspend"],
                    "payment_answer": "Capital Hilton already paid 400 dollars for the first gig via Venmo. The next payment is not confirmed yet.",
                }
            }
        ),
        encoding="utf-8",
    )

    logged = []
    monkeypatch.setattr(cassandra_brain, "_REALITY_NOTES", reality_path, raising=False)
    monkeypatch.setattr(finance_state, "FINANCE_STATE_PATH", finance_path, raising=False)
    monkeypatch.setattr(cassandra_brain, "load_state", lambda: dict(cassandra_brain._DEFAULT_STATE), raising=False)
    monkeypatch.setattr(cassandra_brain, "save_state", lambda state: None, raising=False)
    monkeypatch.setattr(cassandra_brain, "process_pending_followups", lambda: [], raising=False)
    monkeypatch.setattr(
        cassandra_brain,
        "_log_conversation",
        lambda user_text, replies, route="llm", **kwargs: logged.append({"route": route, "replies": replies}),
        raising=False,
    )

    monkeypatch.setattr(
        cassandra_brain,
        "_fetch_payment_verify_context",
        lambda query: (_ for _ in ()).throw(AssertionError("canonical Hilton answer should short-circuit Gmail lookup")),
        raising=False,
    )

    replies = cassandra_brain.handle("Did the Hilton payment come through?")

    assert replies == ["Capital Hilton already paid 400 dollars for the first gig via Venmo. The next payment is not confirmed yet."]
    assert logged[-1]["route"] == "payment_verify"


def test_payment_verify_context_filters_to_matching_entity(tmp_path, monkeypatch):
    import cassandra_brain
    import finance_state

    reality_path = tmp_path / "cassandra_reality_notes.json"
    reality_path.write_text(
        json.dumps({}),
        encoding="utf-8",
    )
    finance_path = tmp_path / "finance_state.json"
    finance_path.write_text(
        json.dumps(
            {
                "accounts": {
                    "capital_hilton": {
                        "label": "Capital Hilton",
                        "aliases": ["capital hilton", "hilton", "smartspend"],
                        "payment_summary": "Capital Hilton payment state is tracked here."
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(cassandra_brain, "_REALITY_NOTES", reality_path, raising=False)
    monkeypatch.setattr(finance_state, "FINANCE_STATE_PATH", finance_path, raising=False)

    def fake_broker(agent, capability, params):
        assert capability == "google.gmail.read.metadata"
        return {
            "ok": True,
            "data": [
                {
                    "from_name": "Anthropic, PBC",
                    "subject": "$20.60 payment to Anthropic, PBC was unsuccessful",
                    "snippet": "Your card was declined",
                    "date_raw": "2026-04-05 07:30",
                },
                {
                    "from_name": "Capital Hilton",
                    "subject": "SmartSpend invoice received",
                    "snippet": "Capital Hilton invoice is in review",
                    "date_raw": "2026-04-05 07:31",
                },
            ],
            "error": "",
        }

    monkeypatch.setattr("google_access_broker.call", fake_broker)

    ctx = cassandra_brain._fetch_payment_verify_context("Did the Hilton payment come through?")

    assert "Capital Hilton" in ctx
    assert "Anthropic" not in ctx


def test_hilton_status_question_routes_directly_from_finance_state(tmp_path, monkeypatch):
    import cassandra_brain
    import finance_state

    finance_path = tmp_path / "finance_state.json"
    finance_path.write_text(
        json.dumps(
            {
                "accounts": {
                    "capital_hilton": {
                        "label": "Capital Hilton",
                        "aliases": ["capital hilton", "hilton", "smartspend"],
                        "workflow_summary": "Two Capital Hilton gigs already happened. The first gig is fully settled. The later gig still needs a new invoice uploaded through SmartSpend before payment can start.",
                        "payment_summary": "The first Capital Hilton gig was paid in full: 400 dollars via Venmo. The later-gig payment is not in motion yet because the new invoice has not been uploaded to SmartSpend.",
                        "invoice_summary": "Capital Hilton already received one invoice. The next invoice still needs to be created for the later gig and uploaded into SmartSpend.",
                        "next_actions": [
                            {
                                "status": "open",
                                "action": "Create the new invoice for the later gig and upload it into SmartSpend."
                            }
                        ]
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    logged = []
    monkeypatch.setattr(finance_state, "FINANCE_STATE_PATH", finance_path, raising=False)
    monkeypatch.setattr(cassandra_brain, "load_state", lambda: dict(cassandra_brain._DEFAULT_STATE), raising=False)
    monkeypatch.setattr(cassandra_brain, "save_state", lambda state: None, raising=False)
    monkeypatch.setattr(cassandra_brain, "process_pending_followups", lambda: [], raising=False)
    monkeypatch.setattr(
        cassandra_brain,
        "_log_conversation",
        lambda user_text, replies, route="llm", **kwargs: logged.append({"route": route, "replies": replies}),
        raising=False,
    )
    replies = cassandra_brain.handle("Where are we with Capital Hilton?")

    assert replies == [
        "Stored finance read-model says (not live-confirmed): Two Capital Hilton gigs already happened. The first gig is fully settled. The later gig still needs a new invoice uploaded through SmartSpend before payment can start. The first Capital Hilton gig was paid in full: 400 dollars via Venmo. The later-gig payment is not in motion yet because the new invoice has not been uploaded to SmartSpend. Next: Create the new invoice for the later gig and upload it into SmartSpend. If that's stale, tell me what to change."
    ]
    assert logged[-1]["route"] == "finance_status"


def test_prefixed_hilton_status_question_bypasses_universal_intake(tmp_path, monkeypatch):
    import cassandra_brain
    import finance_state

    finance_path = tmp_path / "finance_state.json"
    finance_path.write_text(
        json.dumps(
            {
                "accounts": {
                    "capital_hilton": {
                        "label": "Capital Hilton",
                        "aliases": ["capital hilton", "hilton", "smartspend"],
                        "workflow_summary": "Capital Hilton status is stale unless corrected by Winship.",
                        "payment_summary": "Waiting on Coupa verification.",
                        "next_actions": [
                            {
                                "status": "open",
                                "action": "Ask Winship what the current Capital Hilton truth should be."
                            }
                        ]
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    logged = []
    monkeypatch.setattr(finance_state, "FINANCE_STATE_PATH", finance_path, raising=False)
    monkeypatch.setattr(cassandra_brain, "load_state", lambda: dict(cassandra_brain._DEFAULT_STATE), raising=False)
    monkeypatch.setattr(cassandra_brain, "save_state", lambda state: None, raising=False)
    monkeypatch.setattr(cassandra_brain, "process_pending_followups", lambda: [], raising=False)
    monkeypatch.setattr(cassandra_brain, "_handle_operator_objective", lambda *args, **kwargs: None, raising=False)
    monkeypatch.setattr(cassandra_brain, "_process_guided_review_message", lambda *args, **kwargs: None, raising=False)
    monkeypatch.setattr(
        cassandra_brain,
        "_try_universal_operator_intake",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("universal intake should not steal finance status")),
        raising=False,
    )
    monkeypatch.setattr(
        cassandra_brain,
        "_log_conversation",
        lambda user_text, replies, route="llm", **kwargs: logged.append({"route": route, "replies": replies}),
        raising=False,
    )

    replies = cassandra_brain.handle("Cassandra test, draft a text-only answer: Capital Hilton status?")

    assert replies[0].startswith("Stored finance read-model says (not live-confirmed):")
    assert "Capital Hilton status is stale unless corrected by Winship." in replies[0]
    assert "If that's stale, tell me what to change." in replies[0]
    assert logged[-1]["route"] == "finance_status"


def test_session_fact_correction_overrides_stale_finance_status_in_followup(tmp_path, monkeypatch):
    import cassandra_brain
    import finance_state

    finance_path = tmp_path / "finance_state.json"
    finance_path.write_text(
        json.dumps(
            {
                "accounts": {
                    "capital_hilton": {
                        "label": "Capital Hilton",
                        "aliases": ["capital hilton", "hilton", "smartspend"],
                        "workflow_summary": "Will is talking to Chyna on Monday about Capital Hilton.",
                        "payment_summary": "Capital Hilton status still depends on the Monday Chyna handoff.",
                        "invoice_summary": "Old invoice path still references the Monday step.",
                        "next_actions": [
                            {
                                "status": "open",
                                "action": "Talk to Chyna on Monday."
                            }
                        ],
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    shared_state = copy.deepcopy(cassandra_brain._DEFAULT_STATE)
    logged = []

    monkeypatch.setattr(finance_state, "FINANCE_STATE_PATH", finance_path, raising=False)
    monkeypatch.setattr(cassandra_brain, "load_state", lambda: shared_state, raising=False)
    monkeypatch.setattr(cassandra_brain, "save_state", lambda state: shared_state.update(state), raising=False)
    monkeypatch.setattr(cassandra_brain, "process_pending_followups", lambda: [], raising=False)
    monkeypatch.setattr(cassandra_brain, "_fetch_calendar_context", lambda query, **kwargs: "", raising=False)
    monkeypatch.setattr(cassandra_brain, "_fetch_gmail_context", lambda query, **kwargs: "", raising=False)
    monkeypatch.setattr(cassandra_brain, "_fetch_contacts_context", lambda query, **kwargs: "", raising=False)
    monkeypatch.setattr(cassandra_brain, "_fetch_payment_verify_context", lambda query, **kwargs: "", raising=False)
    monkeypatch.setattr(cassandra_brain, "build_context_snapshot", lambda state=None: "", raising=False)
    monkeypatch.setattr(cassandra_brain, "registry_context_for_query", lambda query: None, raising=False)
    monkeypatch.setattr(cassandra_brain, "_should_use_deep", lambda query: False, raising=False)
    monkeypatch.setattr(cassandra_brain, "_cassandra_context_clean", lambda *args, **kwargs: False, raising=False)
    monkeypatch.setattr(cassandra_brain, "_pii_tokenize", lambda prompt: (prompt, None), raising=False)
    monkeypatch.setattr(cassandra_brain, "_pii_rehydrate_reply", lambda reply, ctx: reply, raising=False)
    monkeypatch.setattr(
        cassandra_brain,
        "_call",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("session fact correction should bypass LLM")),
        raising=False,
    )
    monkeypatch.setattr(
        cassandra_brain,
        "_log_conversation",
        lambda user_text, replies, route="llm", **kwargs: logged.append({"route": route, "replies": replies}),
        raising=False,
    )
    correction = cassandra_brain.handle(
        "Capital Hilton update: Will is not talking to Chyna on Monday anymore. "
        "That step has been consumed and is stale. Current truth is only: waiting for Coupa to verify me, then PO orders can come through."
    )

    assert correction == [
        "Got it — for Capital Hilton, the current truth now is: Waiting for Coupa to verify me, then PO orders can come through."
    ]
    assert shared_state["session_fact_overrides"]["capital_hilton"]["summary"] == (
        "Waiting for Coupa to verify me, then PO orders can come through"
    )
    assert logged[-1]["route"] == "session_fact_correction"

    followup = cassandra_brain.handle("What is the current Capital Hilton status now?")

    assert followup == ["Waiting for Coupa to verify me, then PO orders can come through."]
    assert "Chyna" not in followup[0]
    assert logged[-1]["route"] == "finance_status"


def test_fact_correction_summary_accepts_colon_current_truth():
    import cassandra_brain

    summary = cassandra_brain._extract_fact_correction_summary(
        "Capital Hilton current truth: everything is checked off except them sending me the actual check; "
        "they are going to send the actual check on July 1, 2026."
    )

    assert summary == (
        "Everything is checked off except them sending me the actual check; "
        "they are going to send the actual check on July 1, 2026"
    )


def test_implicit_same_session_correction_uses_last_finance_entity(tmp_path, monkeypatch):
    import cassandra_brain
    import finance_state

    finance_path = tmp_path / "finance_state.json"
    finance_path.write_text(
        json.dumps(
            {
                "accounts": {
                    "capital_hilton": {
                        "label": "Capital Hilton",
                        "aliases": ["capital hilton", "hilton", "smartspend", "coupa"],
                        "workflow_summary": "Will is talking to Chyna on Monday about Capital Hilton.",
                        "payment_summary": "Capital Hilton status still depends on the Monday Chyna handoff.",
                        "invoice_summary": "Old invoice path still references the Monday step.",
                        "next_actions": [
                            {"status": "open", "action": "Talk to Chyna on Monday."}
                        ],
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    shared_state = copy.deepcopy(cassandra_brain._DEFAULT_STATE)
    logged = []

    monkeypatch.setattr(finance_state, "FINANCE_STATE_PATH", finance_path, raising=False)
    monkeypatch.setattr(cassandra_brain, "load_state", lambda: shared_state, raising=False)
    monkeypatch.setattr(cassandra_brain, "save_state", lambda state: shared_state.update(state), raising=False)
    monkeypatch.setattr(cassandra_brain, "process_pending_followups", lambda: [], raising=False)
    monkeypatch.setattr(cassandra_brain, "_fetch_calendar_context", lambda query, **kwargs: "", raising=False)
    monkeypatch.setattr(cassandra_brain, "_fetch_gmail_context", lambda query, **kwargs: "", raising=False)
    monkeypatch.setattr(cassandra_brain, "_fetch_contacts_context", lambda query, **kwargs: "", raising=False)
    monkeypatch.setattr(cassandra_brain, "_fetch_payment_verify_context", lambda query, **kwargs: "", raising=False)
    monkeypatch.setattr(cassandra_brain, "build_context_snapshot", lambda state=None: "", raising=False)
    monkeypatch.setattr(cassandra_brain, "registry_context_for_query", lambda query: None, raising=False)
    monkeypatch.setattr(cassandra_brain, "_should_use_deep", lambda query: False, raising=False)
    monkeypatch.setattr(cassandra_brain, "_cassandra_context_clean", lambda *args, **kwargs: False, raising=False)
    monkeypatch.setattr(cassandra_brain, "_pii_tokenize", lambda prompt: (prompt, None), raising=False)
    monkeypatch.setattr(cassandra_brain, "_pii_rehydrate_reply", lambda reply, ctx: reply, raising=False)
    monkeypatch.setattr(
        cassandra_brain,
        "_call",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("implicit session correction should bypass LLM")),
        raising=False,
    )
    monkeypatch.setattr(
        cassandra_brain,
        "_log_conversation",
        lambda user_text, replies, route="llm", **kwargs: logged.append({"route": route, "replies": replies}),
        raising=False,
    )
    baseline = cassandra_brain.handle("Where are we with Capital Hilton?")
    assert "Chyna" in baseline[0]
    assert shared_state["last_finance_entity"]["key"] == "capital_hilton"

    correction = cassandra_brain.handle(
        "No. Will is not talking to Chyna on Monday anymore. "
        "That step has been consumed and is stale. We are only waiting for Coupa to verify me, then PO orders can come through."
    )

    assert correction == [
        "Got it — for Capital Hilton, the current truth now is: Waiting for Coupa to verify me, then PO orders can come through."
    ]
    assert shared_state["session_fact_overrides"]["capital_hilton"]["summary"] == (
        "Waiting for Coupa to verify me, then PO orders can come through"
    )

    followup = cassandra_brain.handle("what is the current capital hilton status now?")

    assert followup == ["Waiting for Coupa to verify me, then PO orders can come through."]
    assert logged[-1]["route"] == "finance_status"


def test_stale_callout_without_replacement_starts_two_turn_correction(tmp_path, monkeypatch):
    import cassandra_brain
    import finance_state

    finance_path = tmp_path / "finance_state.json"
    finance_path.write_text(
        json.dumps(
            {
                "accounts": {
                    "capital_hilton": {
                        "label": "Capital Hilton",
                        "aliases": ["capital hilton", "hilton", "coupa"],
                        "workflow_summary": "Will is talking to Chyna on Monday about Capital Hilton.",
                        "payment_summary": "Capital Hilton status still depends on the Monday Chyna handoff.",
                        "next_actions": [
                            {"status": "open", "action": "Talk to Chyna on Monday."}
                        ],
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    shared_state = copy.deepcopy(cassandra_brain._DEFAULT_STATE)
    logged = []

    monkeypatch.setattr(finance_state, "FINANCE_STATE_PATH", finance_path, raising=False)
    monkeypatch.setattr(cassandra_brain, "load_state", lambda: shared_state, raising=False)
    monkeypatch.setattr(cassandra_brain, "save_state", lambda state: shared_state.update(state), raising=False)
    monkeypatch.setattr(cassandra_brain, "process_pending_followups", lambda: [], raising=False)
    monkeypatch.setattr(
        cassandra_brain,
        "_call",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("two-turn correction should bypass LLM")),
        raising=False,
    )
    monkeypatch.setattr(
        cassandra_brain,
        "_log_conversation",
        lambda user_text, replies, route="llm", **kwargs: logged.append({"route": route, "replies": replies}),
        raising=False,
    )

    baseline = cassandra_brain.handle("Where are we with Capital Hilton?")
    assert "Stored finance read-model says (not live-confirmed)" in baseline[0]
    assert shared_state["last_finance_entity"]["key"] == "capital_hilton"

    stale_callout = cassandra_brain.handle("hey that's old and stale")

    assert stale_callout == [
        "You're right — I may be looking at stale context for Capital Hilton. What should I change it to?"
    ]
    assert shared_state["pending_session_fact_correction"]["account_key"] == "capital_hilton"

    replacement = cassandra_brain.handle("we are waiting for Coupa verification; Will already did his part.")

    assert replacement == [
        "Got it — for Capital Hilton, the current truth now is: We are waiting for Coupa verification; Will already did his part."
    ]
    assert shared_state["session_fact_overrides"]["capital_hilton"]["summary"] == (
        "We are waiting for Coupa verification; Will already did his part"
    )
    assert shared_state["pending_session_fact_correction"] is None
    assert logged[-1]["route"] == "session_fact_correction"


def test_pending_stale_correction_does_not_consume_unrelated_question():
    import cassandra_brain

    state = {
        "pending_session_fact_correction": {
            "account_key": "capital_hilton",
            "label": "Capital Hilton",
            "at": "2026-06-19 00:00:00",
            "source_text": "that Capital Hilton thing is stale",
        },
        "session_fact_overrides": {},
    }

    reply = cassandra_brain._handle_pending_session_fact_correction(
        "which agents are telegram ready?",
        state,
    )

    assert reply is None
    assert state["pending_session_fact_correction"] is None
    assert state["session_fact_overrides"] == {}


def test_st_annes_january_23_status_stays_specific(tmp_path, monkeypatch):
    import cassandra_brain
    import finance_state

    finance_path = tmp_path / "finance_state.json"
    finance_path.write_text(
        json.dumps(
            {
                "accounts": {
                    "st_annes_the_studio_2026_01_23": {
                        "label": "St. Anne's at The Studio 2026-01-23",
                        "aliases": ["st. annes at the studio", "january 23", "1/23", "st. annes"],
                        "workflow_summary": "The 2026-01-23 St. Anne's at The Studio tech payment is still unpaid.",
                        "payment_summary": "Tech payment for St. Anne's at The Studio on 2026-01-23 is still outstanding. Music pay is uncertain.",
                        "next_actions": [
                            {
                                "status": "open",
                                "action": "Ask Draper and Ernie for a payment update on the unpaid 2026-01-23 tech work."
                            }
                        ],
                    },
                    "iranian_band_tech": {
                        "label": "Iranian band tech work",
                        "aliases": ["iranian band"],
                        "workflow_summary": "The Iranian band tech work is still unpaid."
                    },
                }
            }
        ),
        encoding="utf-8",
    )

    logged = []
    monkeypatch.setattr(finance_state, "FINANCE_STATE_PATH", finance_path, raising=False)
    monkeypatch.setattr(cassandra_brain, "load_state", lambda: dict(cassandra_brain._DEFAULT_STATE), raising=False)
    monkeypatch.setattr(cassandra_brain, "save_state", lambda state: None, raising=False)
    monkeypatch.setattr(cassandra_brain, "process_pending_followups", lambda: [], raising=False)
    monkeypatch.setattr(
        cassandra_brain,
        "_log_conversation",
        lambda user_text, replies, route="llm", **kwargs: logged.append({"route": route, "replies": replies}),
        raising=False,
    )
    replies = cassandra_brain.handle("What is the update on St. Anne's at The Studio on January 23?")

    assert "2026-01-23" in replies[0]
    assert "Draper and Ernie" in replies[0]
    assert "Iranian band" not in replies[0]
    assert logged[-1]["route"] == "finance_status"


def test_iranian_band_status_stays_specific(tmp_path, monkeypatch):
    import cassandra_brain
    import finance_state

    finance_path = tmp_path / "finance_state.json"
    finance_path.write_text(
        json.dumps(
            {
                "accounts": {
                    "st_annes_the_studio_2026_01_23": {
                        "label": "St. Anne's at The Studio 2026-01-23",
                        "aliases": ["st. annes at the studio", "1/23"],
                        "workflow_summary": "The 2026-01-23 St. Anne's at The Studio tech payment is still unpaid."
                    },
                    "iranian_band_tech": {
                        "label": "Iranian band tech work",
                        "aliases": ["iranian band", "iranian band tech"],
                        "workflow_summary": "The Iranian band tech work is still unpaid and needs payer, amount, and billing-path reconciliation.",
                        "payment_summary": "Payment for the Iranian band tech work is still outstanding.",
                        "next_actions": [
                            {
                                "status": "open",
                                "action": "Clarify payer, amount, and billing path for the unpaid Iranian band tech work."
                            }
                        ],
                    },
                    "talent_machine_tech": {
                        "label": "Talent Machine tech job",
                        "aliases": ["talent machine"],
                        "workflow_summary": "The Talent Machine tech job is still unpaid."
                    },
                }
            }
        ),
        encoding="utf-8",
    )

    logged = []
    monkeypatch.setattr(finance_state, "FINANCE_STATE_PATH", finance_path, raising=False)
    monkeypatch.setattr(cassandra_brain, "load_state", lambda: dict(cassandra_brain._DEFAULT_STATE), raising=False)
    monkeypatch.setattr(cassandra_brain, "save_state", lambda state: None, raising=False)
    monkeypatch.setattr(cassandra_brain, "process_pending_followups", lambda: [], raising=False)
    monkeypatch.setattr(
        cassandra_brain,
        "_log_conversation",
        lambda user_text, replies, route="llm", **kwargs: logged.append({"route": route, "replies": replies}),
        raising=False,
    )
    replies = cassandra_brain.handle("What is the update on the Iranian band tech payment?")

    assert "Iranian band tech work" in replies[0]
    assert "Talent Machine" not in replies[0]
    assert "St. Anne's at The Studio" not in replies[0]
    assert logged[-1]["route"] == "finance_status"


def test_st_annes_general_status_uses_recurring_lane(tmp_path, monkeypatch):
    import cassandra_brain
    import finance_state

    finance_path = tmp_path / "finance_state.json"
    finance_path.write_text(
        json.dumps(
            {
                "accounts": {
                    "st_annes_the_studio_2026_01_23": {
                        "label": "St. Anne's at The Studio 2026-01-23",
                        "aliases": ["st. annes at the studio", "january 23", "1/23"],
                        "workflow_summary": "The 2026-01-23 St. Anne's at The Studio tech payment is still unpaid."
                    },
                    "st_annes_recurring": {
                        "label": "St. Anne's recurring workstream",
                        "aliases": ["st. annes", "st annes", "st. anne's", "st anne's", "parish"],
                        "workflow_summary": "St. Anne's is a recurring Sunday-services and parish-tech lane. Treat it as separate from Live Arts Maryland.",
                        "payment_summary": "The currently grounded St. Anne's-specific open receivable is the unpaid 2026-01-23 tech work.",
                        "next_actions": [
                            {
                                "status": "open",
                                "action": "Keep St. Anne's payment tracking separate from Live Arts Maryland."
                            }
                        ],
                    },
                }
            }
        ),
        encoding="utf-8",
    )

    logged = []
    monkeypatch.setattr(finance_state, "FINANCE_STATE_PATH", finance_path, raising=False)
    monkeypatch.setattr(cassandra_brain, "load_state", lambda: dict(cassandra_brain._DEFAULT_STATE), raising=False)
    monkeypatch.setattr(cassandra_brain, "save_state", lambda state: None, raising=False)
    monkeypatch.setattr(cassandra_brain, "process_pending_followups", lambda: [], raising=False)
    monkeypatch.setattr(
        cassandra_brain,
        "_log_conversation",
        lambda user_text, replies, route="llm", **kwargs: logged.append({"route": route, "replies": replies}),
        raising=False,
    )
    replies = cassandra_brain.handle("Where are we with St. Anne's?")

    assert "recurring Sunday-services and parish-tech lane" in replies[0]
    assert "Live Arts Maryland" in replies[0]
    assert logged[-1]["route"] == "finance_status"


def test_live_arts_general_status_uses_recurring_lane(tmp_path, monkeypatch):
    import cassandra_brain
    import finance_state

    finance_path = tmp_path / "finance_state.json"
    finance_path.write_text(
        json.dumps(
            {
                "accounts": {
                    "papa_rapper": {
                        "label": "Papa Rapper",
                        "aliases": ["papa rapper"],
                        "workflow_summary": "Papa Rapper payment is still outstanding."
                    },
                    "live_arts_maryland_recurring": {
                        "label": "Live Arts Maryland recurring workstream",
                        "aliases": ["live arts maryland", "live arts"],
                        "workflow_summary": "Live Arts Maryland is a separate event-based and rental-based lane.",
                        "payment_summary": "Current grounded open items include Papa Rapper and Annapolis Choral reconciliation.",
                        "next_actions": [
                            {
                                "status": "open",
                                "action": "Keep Live Arts tracking separate from St. Anne's."
                            }
                        ],
                    },
                }
            }
        ),
        encoding="utf-8",
    )

    logged = []
    monkeypatch.setattr(finance_state, "FINANCE_STATE_PATH", finance_path, raising=False)
    monkeypatch.setattr(cassandra_brain, "load_state", lambda: dict(cassandra_brain._DEFAULT_STATE), raising=False)
    monkeypatch.setattr(cassandra_brain, "save_state", lambda state: None, raising=False)
    monkeypatch.setattr(cassandra_brain, "process_pending_followups", lambda: [], raising=False)
    monkeypatch.setattr(
        cassandra_brain,
        "_log_conversation",
        lambda user_text, replies, route="llm", **kwargs: logged.append({"route": route, "replies": replies}),
        raising=False,
    )
    replies = cassandra_brain.handle("Where are we with Live Arts Maryland?")

    assert "event-based and rental-based lane" in replies[0]
    assert "Papa Rapper" in replies[0]
    assert logged[-1]["route"] == "finance_status"


def test_build_context_snapshot_ignores_stale_relative_day_noise(tmp_path, monkeypatch):
    import cassandra_brain
    import chief_cpa_brain

    old_stamp = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")
    recent_stamp = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
    actions_path = tmp_path / "Ops Actions.md"
    payments_path = tmp_path / "Ops Payment Follow-ups.md"
    actions_path.write_text(
        "\n".join(
            [
                "# Ops Actions",
                "type: ops-log",
                f"- [{old_stamp}] golf with dad tomorrow, pickup 8:15",
                f"- [{recent_stamp}] tomorrow cleaning company at 9:30",
            ]
        ),
        encoding="utf-8",
    )
    payments_path.write_text(
        "\n".join(
            [
                "# Ops Payment",
                f"- [{recent_stamp}] sent follow-up email to Capital Hilton, deposit not received",
            ]
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(cassandra_brain, "_OPS_ACTIONS", actions_path, raising=False)
    monkeypatch.setattr(cassandra_brain, "_OPS_PAYMENT", payments_path, raising=False)
    monkeypatch.setattr(chief_cpa_brain, "get_recent_income", lambda days=2: [], raising=False)

    snapshot = cassandra_brain.build_context_snapshot(dict(cassandra_brain._DEFAULT_STATE))

    assert "Time:" in snapshot
    assert "Context invariants:" in snapshot
    assert "Relative date anchors:" in snapshot
    assert "yesterday is" in snapshot
    assert "tomorrow is" in snapshot
    assert f"[{old_stamp}] golf with dad tomorrow, pickup 8:15" not in snapshot.lower()
    assert "one-off historical event" in snapshot.lower()
    assert "type: ops-log" not in snapshot.lower()
    assert "No income logged in last 48 hours." not in snapshot
    assert "the next day cleaning company at 9:30" in snapshot


def test_build_context_snapshot_includes_canonical_reality_summary(tmp_path, monkeypatch):
    import cassandra_brain
    import finance_state
    import chief_cpa_brain

    reality_path = tmp_path / "cassandra_reality_notes.json"
    workstreams_path = tmp_path / "Ops Workstreams.md"
    reality_path.write_text(
        json.dumps(
            {
                "capital_hilton": {
                    "label": "Capital Hilton",
                    "status_summary": "The first gig is already settled. The next open item is the later invoice and SmartSpend upload.",
                },
                "march_gigs": {
                    "label": "March gigs",
                    "status_summary": "March 27 already happened. March 28 was canceled.",
                },
            }
        ),
        encoding="utf-8",
    )

    actions_path = tmp_path / "Ops Actions.md"
    payments_path = tmp_path / "Ops Payment Follow-ups.md"
    finance_path = tmp_path / "finance_state.json"
    workstreams_path.write_text(
        "\n".join(
            [
                "# Ops Workstreams",
                "- St. Anne's is a recurring Sunday-services lane.",
                "- Live Arts Maryland is a separate event-based lane.",
            ]
        ),
        encoding="utf-8",
    )
    finance_path.write_text(
        json.dumps(
            {
                "accounts": {
                    "capital_hilton": {
                        "label": "Capital Hilton",
                        "aliases": ["capital hilton", "hilton", "smartspend"],
                        "workflow_summary": "The first gig is settled. The later SmartSpend invoice is still open."
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    actions_path.write_text("# Ops Actions\n", encoding="utf-8")
    payments_path.write_text("# Ops Payment\n", encoding="utf-8")

    monkeypatch.setattr(cassandra_brain, "_REALITY_NOTES", reality_path, raising=False)
    monkeypatch.setattr(cassandra_brain, "_OPS_ACTIONS", actions_path, raising=False)
    monkeypatch.setattr(cassandra_brain, "_OPS_PAYMENT", payments_path, raising=False)
    monkeypatch.setattr(cassandra_brain, "_OPS_WORKSTREAMS", workstreams_path, raising=False)
    monkeypatch.setattr(finance_state, "FINANCE_STATE_PATH", finance_path, raising=False)
    monkeypatch.setattr(chief_cpa_brain, "get_recent_income", lambda days=2: [], raising=False)

    snapshot = cassandra_brain.build_context_snapshot(dict(cassandra_brain._DEFAULT_STATE))

    assert "[FINANCE STATE SNAPSHOT]" in snapshot
    assert "Capital Hilton: The first gig is settled. The later SmartSpend invoice is still open." in snapshot
    assert "[CANONICAL REALITY SNAPSHOT]" in snapshot
    assert "Capital Hilton: The first gig is already settled." in snapshot
    assert "March gigs: March 27 already happened. March 28 was canceled." in snapshot
    assert "Active workstreams:" in snapshot
    assert "St. Anne's is a recurring Sunday-services lane." in snapshot


def test_afternoon_briefing_uses_operator_truth_before_stale_finance(
    tmp_path,
    monkeypatch,
):
    import cassandra_brain
    import cassandra_briefing_brain as briefing
    import finance_state
    import chief_cpa_brain

    stale_handoff = "Will Valcovic to Chyna on Monday"
    finance_path = tmp_path / "finance_state.json"
    reality_path = tmp_path / "cassandra_reality_notes.json"
    actions_path = tmp_path / "Ops Actions.md"
    payments_path = tmp_path / "Ops Payment Follow-ups.md"
    workstreams_path = tmp_path / "Ops Workstreams.md"

    finance_path.write_text(
        json.dumps(
            {
                "accounts": {
                    "capital_hilton": {
                        "label": "Capital Hilton",
                        "aliases": ["capital hilton", "hilton", "smartspend"],
                        "workflow_summary": f"{stale_handoff} for POs.",
                        "next_actions": [{"status": "open", "action": f"{stale_handoff}."}],
                    },
                    "live_arts": {
                        "label": "Live Arts Maryland",
                        "aliases": ["live arts"],
                        "workflow_summary": "Canonical second-entity fact still active.",
                        "next_actions": [{"status": "open", "action": "Keep the rental invoice lane moving."}],
                    },
                }
            }
        ),
        encoding="utf-8",
    )
    reality_path.write_text(
        json.dumps(
            {
                "capital_hilton": {
                    "label": "Capital Hilton",
                    "status_summary": f"Reality note still says {stale_handoff}.",
                },
                "live_arts": {
                    "label": "Live Arts Maryland",
                    "status_summary": "Canonical reality for the second entity is still safe to brief.",
                },
            }
        ),
        encoding="utf-8",
    )
    actions_path.write_text("# Ops Actions\n", encoding="utf-8")
    payments_path.write_text("# Ops Payment\n", encoding="utf-8")
    workstreams_path.write_text("# Ops Workstreams\n", encoding="utf-8")

    state = dict(cassandra_brain._DEFAULT_STATE)
    state["session_fact_overrides"] = {
        "capital_hilton": {
            "summary": "everything checked off except the actual check; July 1 2026 is the actual-check date",
            "at": "2026-06-19T09:30:00",
            "source_text": "operator correction",
        }
    }
    captured: dict[str, str] = {}

    monkeypatch.setattr(finance_state, "FINANCE_STATE_PATH", finance_path, raising=False)
    monkeypatch.setattr(cassandra_brain, "_REALITY_NOTES", reality_path, raising=False)
    monkeypatch.setattr(cassandra_brain, "_OPS_ACTIONS", actions_path, raising=False)
    monkeypatch.setattr(cassandra_brain, "_OPS_PAYMENT", payments_path, raising=False)
    monkeypatch.setattr(cassandra_brain, "_OPS_WORKSTREAMS", workstreams_path, raising=False)
    monkeypatch.setattr(cassandra_brain, "load_state", lambda: state, raising=False)
    monkeypatch.setattr(chief_cpa_brain, "get_recent_income", lambda days=2: [], raising=False)
    monkeypatch.setattr(
        briefing,
        "resolve_local_model",
        lambda prompt, task_class: ("test-model", "test-lane"),
        raising=False,
    )

    def fake_ollama_call(prompt, **kwargs):
        captured["prompt"] = prompt
        return "Capital Hilton: July 1 2026 actual-check date. Live Arts Maryland remains active."

    monkeypatch.setattr(briefing, "ollama_call", fake_ollama_call, raising=False)

    output = briefing.generate_briefing("afternoon")
    prompt = captured["prompt"]

    assert stale_handoff not in prompt
    assert stale_handoff not in output
    assert "July 1 2026" in prompt
    assert "July 1 2026" in output
    assert "provenance: operator_corrected" in prompt
    assert "provenance: stale/superseded" in prompt
    assert "Live Arts Maryland: Canonical second-entity fact still active." in prompt
    assert "Canonical reality for the second entity is still safe to brief." in prompt


def test_morning_financial_snapshot_includes_structured_finance_state(tmp_path, monkeypatch):
    import cassandra_briefing_morning_context
    import finance_state
    import chief_cpa_brain

    finance_path = tmp_path / "finance_state.json"
    finance_path.write_text(
        json.dumps(
            {
                "accounts": {
                    "capital_hilton": {
                        "label": "Capital Hilton",
                        "workflow_summary": "The first gig is fully settled. The later SmartSpend invoice is still open."
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    payments_path = tmp_path / "Ops Payment Follow-ups.md"
    payments_path.write_text("# Ops Payment\n", encoding="utf-8")

    monkeypatch.setattr(finance_state, "FINANCE_STATE_PATH", finance_path, raising=False)
    monkeypatch.setattr(cassandra_briefing_morning_context, "_OPS_PAYMENT", payments_path, raising=False)
    monkeypatch.setattr(chief_cpa_brain, "get_recent_income", lambda days=2: [], raising=False)

    snapshot = cassandra_briefing_morning_context._financial_snapshot()

    assert "Structured finance state:" in snapshot
    assert "Capital Hilton: The first gig is fully settled. The later SmartSpend invoice is still open." in snapshot

def test_calendar_context_supports_work_on_phrase(monkeypatch):
    import cassandra_brain

    def fake_broker(agent, capability, params):
        assert capability == "google.calendar.read"
        return {"ok": True, "data": [], "error": ""}

    monkeypatch.setattr("google_access_broker.call", fake_broker)

    ctx = cassandra_brain._fetch_calendar_context("What do you show for work on March 27?")

    assert ctx.startswith("[CALENDAR DATA")
