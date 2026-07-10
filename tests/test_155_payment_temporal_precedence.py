from __future__ import annotations

import asyncio
import json

import pytest


PAYMENT_SENTINELS = (
    "did the Capital Hilton check arrive?",
    "Do you know whether the check from the Capital Hilton has come in yet?",
    "has the Capital Hilton check cleared yet?",
    "what's the status of the Hilton check?",
    "what's the status of the Hilton payment?",
)


TEMPORAL_PAYLOAD = {
    "generated_at": "2026-07-09T23:15:00+00:00",
    "read_model_id": "receivables_month_bounded",
    "rows": [
        {
            "client_display_name": "St. Anne's",
            "client_ref": "st_annes",
            "currency_iso": "USD",
            "month": "2025-05",
            "amount_known": True,
            "open_minor_units": 50000,
            "paid_minor_units": 0,
            "payment_status": "open",
            "needs_reconcile": False,
            "settled_past_no_compound": False,
        },
        {
            "client_display_name": "St. Anne's",
            "client_ref": "st_annes",
            "currency_iso": "USD",
            "month": "2025-07",
            "amount_known": True,
            "open_minor_units": 70000,
            "paid_minor_units": 0,
            "payment_status": "open",
            "needs_reconcile": False,
            "settled_past_no_compound": False,
        },
        {
            "client_display_name": "St. Anne's",
            "client_ref": "st_annes",
            "currency_iso": "USD",
            "month": "2026-05",
            "amount_known": True,
            "open_minor_units": 0,
            "paid_minor_units": 62500,
            "payment_status": "settled",
            "needs_reconcile": False,
            "settled_past_no_compound": True,
        },
        {
            "client_display_name": "St. Anne's",
            "client_ref": "st_annes",
            "currency_iso": "USD",
            "month": "2026-07",
            "amount_known": False,
            "open_minor_units": None,
            "paid_minor_units": None,
            "payment_status": "expected_uninvoiced",
            "needs_reconcile": False,
            "settled_past_no_compound": False,
        },
        {
            "client_display_name": "Capital Hilton",
            "client_ref": "capital_hilton",
            "currency_iso": "USD",
            "month": "2026-06",
            "amount_known": False,
            "open_minor_units": None,
            "paid_minor_units": None,
            "payment_status": "open_amount_unknown",
            "needs_reconcile": True,
            "settled_past_no_compound": False,
        },
    ],
}


@pytest.fixture
def temporal_money_fixture(tmp_path, monkeypatch):
    import money_truth

    path = tmp_path / "receivables_month_bounded.json"
    path.write_text(json.dumps(TEMPORAL_PAYLOAD), encoding="utf-8")
    monkeypatch.setattr(money_truth, "DEFAULT_READ_MODEL_PATH", path)
    return path


@pytest.mark.parametrize("text", PAYMENT_SENTINELS)
def test_payment_sentinels_share_one_precedence_classifier(text):
    import cassandra_brain
    from business_ops_intent import classify_business_ops_intent
    from money_truth import classify_money_question

    assert classify_money_question(text) == "payment_arrival_verify"
    assert classify_business_ops_intent(text).intent_name == "payment_verify"
    decision = cassandra_brain.decide_gmail_intent(text)
    assert decision.category == "payment_verify"
    assert cassandra_brain._looks_like_payment_verify_query(text) is True


@pytest.mark.parametrize("text", PAYMENT_SENTINELS)
def test_active_session_typed_contract_never_votes_or_captures_payment(text):
    import typed_contract_decision as contract

    decision = contract.decide_contract(
        text,
        context=contract.ContractContext(
            agent="cassandra",
            surface="cassandra_telegram",
            active_session=True,
            session_kind="invoice_cockpit",
            session_field="client",
        ),
        semantic_vote_enabled=True,
        adaptive_call_fn=lambda *_args, **_kwargs: pytest.fail(
            "semantic vote ran before deterministic payment precedence"
        ),
    )
    assert decision.label is contract.ContractLabel.PAYMENT_ARRIVAL
    assert decision.action is contract.DecisionAction.PASS_THROUGH
    assert decision.receipt.model_called is False
    assert decision.receipt.session_preserved is False


def test_from_is_word_bounded_and_never_steals_payment_precedence():
    from business_ops_intent import classify_business_ops_intent

    payment = classify_business_ops_intent(
        "Do you know whether the check from the Capital Hilton has come in yet?"
    )
    assert payment.intent_name == "payment_verify"
    assert payment.trigger != "from"

    assert classify_business_ops_intent("is the fromage platter ready?").intent_name == "none"
    assert classify_business_ops_intent("show email from Dane").intent_name == "email_search"
    assert (
        classify_business_ops_intent("find the email about who owes me").intent_name
        == "email_search"
    )


def test_arrival_declaration_remains_an_operator_event_not_a_verify_question():
    from money_truth import classify_money_question

    assert classify_money_question("Capital Hilton check has arrived") is None


@pytest.mark.parametrize(
    "text",
    (
        "status check",
        "system status check?",
        "health check status?",
        "what is the deployment check status?",
        "what is the status of the health check?",
        "what is the status of the deployment check?",
        "what is the status of my background check?",
        "did the background check clear?",
        "has the health check cleared?",
        "did the deployment check come through?",
        "did Capital Hilton's background check clear?",
    ),
)
def test_generic_status_checks_never_become_payment_questions(text):
    import cassandra_brain
    from business_ops_intent import classify_business_ops_intent
    from money_truth import classify_money_question

    assert classify_money_question(text) is None
    assert classify_business_ops_intent(text).intent_name != "payment_verify"
    assert cassandra_brain.decide_gmail_intent(text).category != "payment_verify"


def test_may_2026_renders_only_settled_past(temporal_money_fixture):
    from money_truth import render_money_answer

    answer = render_money_answer(
        "cassandra", question="what did St Anne's owe us back in May 2026?"
    )
    assert "May 2026" in answer
    assert "settled" in answer
    assert "paid; don't chase" in answer
    assert "July 2026" not in answer
    assert "$500" not in answer
    assert "ready to send" not in answer


def test_verbatim_no_year_may_uses_read_model_as_of_year_and_stays_settled(
    temporal_money_fixture,
):
    from money_truth import render_money_answer

    answer = render_money_answer("maestro", question="what did St Anne's owe us back in May?")
    assert "May 2026" in answer
    assert "settled" in answer
    assert "$500" not in answer
    assert "May 2025" not in answer


@pytest.mark.parametrize(
    "question",
    (
        "may I ask who owes me money right now?",
        "which clients may still owe me?",
    ),
)
def test_modal_may_never_temporally_scopes_money_truth(question, temporal_money_fixture):
    from money_truth import render_money_answer

    answer = render_money_answer("maestro", question=question)
    assert "Capital Hilton" in answer
    assert "July 2026" in answer
    assert "$500" in answer


@pytest.mark.parametrize(
    "question",
    (
        "who owes me $2025 right now?",
        "who owes me 2025 dollars right now?",
    ),
)
def test_amount_that_looks_like_year_never_temporally_scopes(question, temporal_money_fixture):
    from money_truth import render_money_answer

    answer = render_money_answer("maestro", question=question)
    assert "Capital Hilton" in answer
    assert "July 2026" in answer
    assert "$500" in answer


def test_temporal_year_only_phrase_scopes_rows(temporal_money_fixture):
    from money_truth import render_money_answer

    answer = render_money_answer("maestro", question="what did they owe in 2025?")
    assert "May 2025" in answer
    assert "July 2025" in answer
    assert "May 2026" not in answer
    assert "July 2026" not in answer


def test_july_2026_does_not_reopen_may_or_blend_prior_year(temporal_money_fixture):
    from money_truth import render_money_answer

    answer = render_money_answer(
        "cassandra", question="what is the status of St Anne's July 2026 invoice?"
    )
    assert "July 2026" in answer
    assert "ready to send" in answer
    assert "May 2026" not in answer
    assert "$500" not in answer
    assert "settled" not in answer


def test_may_vs_july_2026_renders_two_periods_without_2025_contamination(
    temporal_money_fixture,
):
    from money_truth import render_money_answer

    answer = render_money_answer(
        "cassandra",
        question="what's the status of St Anne's July 2026 invoice compared to what they owed in May?",
    )
    assert "May 2026" in answer
    assert "settled" in answer
    assert "July 2026" in answer
    assert "ready to send" in answer
    assert "$500" not in answer


def test_explicit_period_pairs_never_form_a_cartesian_filter(temporal_money_fixture):
    from money_truth import render_money_answer

    answer = render_money_answer(
        "cassandra", question="compare St Anne's May 2025 with July 2026"
    )
    assert "May 2025" in answer
    assert "$500" in answer
    assert "July 2026" in answer
    assert "May 2026" not in answer
    assert "July 2025" not in answer
    assert "$700" not in answer


def test_temporal_scoped_miss_is_not_false_global_empty_claim(temporal_money_fixture):
    from money_truth import render_money_answer

    answer = render_money_answer(
        "cassandra", question="what did St Anne's owe us in August 2026?"
    )
    assert "No receivable row matches August 2026" in answer
    assert "scoped data gap" in answer
    assert "ledger read-model has no rows" not in answer
    assert "as of 2026-07-09" in answer


def test_payment_ledger_render_always_names_authority_and_as_of(temporal_money_fixture):
    from money_truth import render_payment_verification_ledger

    answer = render_payment_verification_ledger("did the Capital Hilton check arrive?")
    assert "receivables_month_bounded" in answer
    assert "as of 2026-07-09" in answer
    assert "Capital Hilton" in answer


def _isolate_payment_handle(monkeypatch, tmp_path):
    import cassandra_brain

    logged = []
    monkeypatch.setattr(cassandra_brain, "process_pending_followups", lambda: [])
    monkeypatch.setattr(cassandra_brain, "load_state", lambda: dict(cassandra_brain._DEFAULT_STATE))
    monkeypatch.setattr(cassandra_brain, "save_state", lambda _state: None)
    monkeypatch.setattr(
        cassandra_brain,
        "_log_conversation",
        lambda text, replies, route="llm", metadata=None, **kwargs: logged.append(
            {"text": text, "replies": replies, "route": route, "metadata": metadata or {}}
        ),
    )
    monkeypatch.setenv("OPENCLAW_CONTRACT_RECEIPT_DB", str(tmp_path / "receipts.sqlite3"))
    return cassandra_brain, logged


@pytest.mark.parametrize("text", PAYMENT_SENTINELS)
def test_real_handle_routes_payment_before_email_finance_packet_or_model(
    text, temporal_money_fixture, monkeypatch, tmp_path
):
    cassandra_brain, logged = _isolate_payment_handle(monkeypatch, tmp_path)
    monkeypatch.setattr(
        cassandra_brain,
        "_fetch_payment_verify_context",
        lambda *_args, **_kwargs: "[VERIFIED PAYMENT DATA — no recent Gmail notifications found]",
    )
    monkeypatch.setattr(
        cassandra_brain,
        "_known_payment_status_reply",
        lambda *_args, **_kwargs: pytest.fail("legacy finance/reality source ran"),
    )
    monkeypatch.setattr(
        cassandra_brain,
        "assemble_business_ops_packet",
        lambda *_args, **_kwargs: pytest.fail("ops packet assembled before payment"),
    )
    monkeypatch.setattr(
        cassandra_brain,
        "record_cassandra_packet_event",
        lambda *_args, **_kwargs: pytest.fail("ops packet event ran before payment"),
    )
    monkeypatch.setattr(
        cassandra_brain,
        "_handle_finance_status_request",
        lambda *_args, **_kwargs: pytest.fail("finance status ran before payment"),
    )
    monkeypatch.setattr(
        cassandra_brain,
        "_call",
        lambda *_args, **_kwargs: pytest.fail("model ran for deterministic payment verification"),
    )

    replies = cassandra_brain.handle(text)

    assert len(replies) == 1
    assert "receivables_month_bounded" in replies[0]
    assert "as of 2026-07-09" in replies[0]
    assert "Capital Hilton" in replies[0]
    assert logged[-1]["route"] == "payment_verify"
    assert logged[-1]["metadata"]["model_called"] is False


def test_correlated_gmail_metadata_is_evidence_not_bank_settlement(
    temporal_money_fixture, monkeypatch
):
    import cassandra_brain

    monkeypatch.setattr(
        cassandra_brain,
        "_fetch_payment_verify_context",
        lambda *_args, **_kwargs: (
            "[VERIFIED GMAIL NOTIFICATIONS — recent payment-related emails]\n"
            "From: Capital Hilton Accounts Payable\n"
            "Subject: Payment issued — check is on the way\n"
            "Snippet: Your payment has been processed\n"
            "Date: 2026-07-09"
        ),
    )

    reply = cassandra_brain._handle_payment_verification_request(
        "did the Capital Hilton check arrive?"
    )

    assert reply is not None
    assert "notification metadata does not prove bank settlement" in reply.lower()
    assert "receivables_month_bounded" in reply
    assert "as of 2026-07-09" in reply
    assert "verified a matching payment" not in reply.lower()


@pytest.mark.parametrize(
    "context",
    (
        "[VERIFIED PAYMENT DATA — Gmail unreachable]",
        (
            "[VERIFIED GMAIL NOTIFICATIONS — recent payment-related emails]\n"
            "From: Annapolis Parks & Rec\n"
            "Subject: July newsletter and payment plans\n"
            "Snippet: Pool passes are on sale\n"
            "Date: 2026-07-09"
        ),
    ),
)
def test_unreachable_or_irrelevant_metadata_keeps_bounded_ledger_and_as_of(
    context, temporal_money_fixture, monkeypatch
):
    import cassandra_brain

    monkeypatch.setattr(
        cassandra_brain, "_fetch_payment_verify_context", lambda *_args, **_kwargs: context
    )
    reply = cassandra_brain._handle_payment_verification_request(
        "did the Capital Hilton check arrive?"
    )
    assert reply is not None
    assert "receivables_month_bounded" in reply
    assert "as of 2026-07-09" in reply
    assert "Capital Hilton" in reply
    assert "bank-settlement" in reply or "no arrival evidence" in reply


def test_explicit_no_gmail_payment_question_is_ledger_only(
    temporal_money_fixture, monkeypatch
):
    import cassandra_brain

    monkeypatch.setattr(
        cassandra_brain,
        "_fetch_payment_verify_context",
        lambda *_args, **_kwargs: pytest.fail("explicit no-Gmail request polled metadata"),
    )
    reply = cassandra_brain._handle_payment_verification_request(
        "without Gmail, what's the status of the Hilton check?"
    )
    assert reply is not None
    assert "did not check Gmail" in reply
    assert "receivables_month_bounded" in reply
    assert "as of 2026-07-09" in reply


def test_listener_compound_runs_payment_verifier_then_cockpit_exactly_once(
    monkeypatch, tmp_path
):
    import cassandra_brain
    monkeypatch.setenv("CASSANDRA_BOT_TOKEN", "test-token")
    monkeypatch.setenv("TELEGRAM_AUTHORIZED_USER_ID", "12345")
    import cassandra_listener
    import invoice_cockpit_ops
    import money_truth

    calls = []
    monkeypatch.setenv("OPENCLAW_CONTRACT_RECEIPT_DB", str(tmp_path / "receipts.sqlite3"))
    monkeypatch.setattr(invoice_cockpit_ops.JsonSessionStore, "load", lambda _self: None)
    monkeypatch.setattr(
        cassandra_brain,
        "_handle_payment_verification_request",
        lambda text: calls.append(("payment", text)) or "PAYMENT EVIDENCE + BOUNDED LEDGER",
    )
    monkeypatch.setattr(
        money_truth,
        "render_money_answer",
        lambda *_args, **_kwargs: pytest.fail("generic money renderer replaced payment verifier"),
    )
    monkeypatch.setattr(
        cassandra_listener,
        "_try_invoice_cockpit",
        lambda text, meta: calls.append(("cockpit", text)) or ["WL-2026-0009.pdf"],
    )
    monkeypatch.setattr(
        cassandra_listener,
        "cassandra_handle",
        lambda *_args, **_kwargs: pytest.fail("compound fell through to brain/model"),
    )

    text = (
        "did St Anne's pay us, and if not can you get their invoice ready "
        "for my review while you're at it?"
    )
    replies = asyncio.run(
        cassandra_listener._run_cassandra_handle_async(
            text,
            {
                "surface": "cassandra_telegram",
                "source_message_id": "task155-compound",
                "invoice_cockpit_session_path": tmp_path / "cockpit.json",
            },
        )
    )

    assert replies == ["PAYMENT EVIDENCE + BOUNDED LEDGER", "WL-2026-0009.pdf"]
    assert calls == [("payment", text), ("cockpit", text)]


def test_active_cockpit_cannot_capture_operator_corrected_money_read(
    monkeypatch, tmp_path
):
    import cassandra_brain
    import invoice_cockpit_ops
    from clarify_session_contract import stamp_clarify_session

    monkeypatch.setenv("CASSANDRA_BOT_TOKEN", "test-token")
    monkeypatch.setenv("TELEGRAM_AUTHORIZED_USER_ID", "12345")
    monkeypatch.setenv("OPENCLAW_CONTRACT_RECEIPT_DB", str(tmp_path / "receipts.sqlite3"))
    import cassandra_listener

    cockpit_session = {"state": "AWAITING_CLIENT", "client": None, "step": 2}
    stamp_clarify_session(cockpit_session, surface="cassandra_telegram")
    monkeypatch.setattr(
        invoice_cockpit_ops.JsonSessionStore,
        "load",
        lambda _self: dict(cockpit_session),
    )
    monkeypatch.setattr(
        cassandra_listener,
        "_try_invoice_cockpit",
        lambda *_args, **_kwargs: pytest.fail("active cockpit captured a money read"),
    )
    monkeypatch.setattr(cassandra_listener, "cassandra_handle", cassandra_brain.handle)

    state = dict(cassandra_brain._DEFAULT_STATE)
    state["session_fact_overrides"] = {
        "live_arts_md": {
            "label": "Live Arts MD",
            "summary": "Live Arts MD is fully reconciled as of this afternoon.",
        }
    }
    monkeypatch.setattr(cassandra_brain, "load_state", lambda: state)
    monkeypatch.setattr(
        cassandra_brain,
        "_get_session_fact_override",
        lambda query, _state: (
            "live_arts_md",
            state["session_fact_overrides"]["live_arts_md"],
        )
        if "live arts" in query.lower()
        else None,
    )
    monkeypatch.setattr(
        cassandra_brain,
        "_call",
        lambda *_args, **_kwargs: pytest.fail("model ran for corrected money read"),
    )
    logged = []
    monkeypatch.setattr(
        cassandra_brain,
        "_log_conversation",
        lambda text, replies, route="llm", metadata=None, **kwargs: logged.append(route),
    )

    replies = asyncio.run(
        cassandra_listener._run_cassandra_handle_async(
            "does Live Arts owe me money?",
            {
                "surface": "cassandra_telegram",
                "source_message_id": "task155-correction",
                "invoice_cockpit_session_path": tmp_path / "cockpit.json",
            },
        )
    )

    assert replies == ["Live Arts MD is fully reconciled as of this afternoon."]
    assert logged[-1] == "money_truth"
