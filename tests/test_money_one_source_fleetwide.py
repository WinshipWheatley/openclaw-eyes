"""Task 140 — ONE money truth, bound into every agent.

Acceptance battery: "who owes me money right now?" to every agent returns the
same three facts ($1,095 Live Arts needs-reconcile / Capital Hilton
check-expected-unverified / St Anne's pending-send) or a one-line route+answer;
Chief's empty-data case says "not tracked yet" (never "Outstanding — none");
the newsletter fixture can never be a "verified" payment match; an active
money-movement ask never receives a read-only ledger answer (141 guard-rail).
"""
import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

MONEY_QUESTION = "who owes me money right now?"

# Live receivables_month_bounded.json snapshot (2026-07-08) — the one truth fixture.
LIVE_PAYLOAD = {
    "generated_at": "2026-07-08T01:24:07+00:00",
    "read_model_id": "receivables_month_bounded",
    "schema_version": "receivables_month_bounded_v1",
    "doctrine": {
        "money_answers_source": "receivables_month_bounded rows only; do not infer totals from narrative.",
        "settle_past_no_compound": "Rows with payment_status=settled force open_minor_units=0 and do not resurface as owed.",
    },
    "rows": [
        {
            "amount_known": False,
            "client_display_name": "Capital Hilton",
            "client_ref": "capital_hilton",
            "currency_iso": "USD",
            "invoiced_minor_units": None,
            "month": "2026-06",
            "needs_reconcile": True,
            "notes": ["check_unverified: check expected per operator; amount not yet evidenced."],
            "open_minor_units": None,
            "paid_minor_units": None,
            "payment_status": "open_amount_unknown",
            "settled_past_no_compound": False,
            "structured_fact": True,
        },
        {
            "amount_known": True,
            "client_display_name": "Live Arts MD",
            "client_ref": "live_arts_md",
            "currency_iso": "USD",
            "invoiced_minor_units": 199500,
            "month": "2026-06",
            "needs_reconcile": True,
            "notes": ["$900 paid; $1,095 remains open pending operator reconciliation."],
            "open_minor_units": 109500,
            "paid_minor_units": 90000,
            "payment_status": "needs_reconcile",
            "settled_past_no_compound": False,
            "structured_fact": True,
        },
        {
            "amount_known": True,
            "client_display_name": "St. Anne's",
            "client_ref": "st_annes",
            "currency_iso": "USD",
            "invoiced_minor_units": 62500,
            "month": "2026-04",
            "needs_reconcile": False,
            "open_minor_units": 0,
            "paid_minor_units": 62500,
            "payment_status": "settled",
            "settled_past_no_compound": True,
            "structured_fact": True,
        },
        {
            "amount_known": True,
            "client_display_name": "St. Anne's",
            "client_ref": "st_annes",
            "currency_iso": "USD",
            "invoiced_minor_units": 62500,
            "month": "2026-05",
            "needs_reconcile": False,
            "open_minor_units": 0,
            "paid_minor_units": 62500,
            "payment_status": "settled",
            "settled_past_no_compound": True,
            "structured_fact": True,
        },
        {
            "amount_known": False,
            "client_display_name": "St. Anne's",
            "client_ref": "st_annes",
            "currency_iso": "USD",
            "invoiced_minor_units": None,
            "month": "2026-07",
            "needs_reconcile": False,
            "notes": ["Current invoice ready to send once the copy is fixed; not yet invoiced, not settled."],
            "open_minor_units": None,
            "paid_minor_units": None,
            "payment_status": "expected_uninvoiced",
            "settled_past_no_compound": False,
            "structured_fact": True,
        },
    ],
    "source_refs": [
        "canonical_business_fact:capital_hilton:2026-06:check_unverified",
        "canonical_business_fact:live_arts_md:2026-06:1095_open_900_paid",
        "canonical_business_fact:st_annes:2026-04:apr_may_paid",
        "canonical_business_fact:st_annes:2026-05:apr_may_paid",
        "canonical_business_fact:st_annes_current_open:2026-07:expected_uninvoiced",
    ],
}


def _write_fixture(tmp_path, payload=LIVE_PAYLOAD, name="receivables_month_bounded.json"):
    path = tmp_path / name
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


@pytest.fixture
def money_fixture(tmp_path, monkeypatch):
    """Point the shared helper at the live-snapshot fixture."""
    import money_truth

    path = _write_fixture(tmp_path)
    monkeypatch.setattr(money_truth, "DEFAULT_READ_MODEL_PATH", path, raising=True)
    return path


@pytest.fixture
def empty_money_fixture(tmp_path, monkeypatch):
    import money_truth

    path = _write_fixture(tmp_path, payload={"generated_at": "2026-07-08T01:24:07+00:00", "rows": []})
    monkeypatch.setattr(money_truth, "DEFAULT_READ_MODEL_PATH", path, raising=True)
    return path


def assert_three_money_facts(text: str) -> None:
    """The SAME three facts every agent must produce."""
    assert "$1,095" in text, text
    assert "Live Arts MD" in text, text
    assert "needs your reconcile" in text, text
    assert "Capital Hilton" in text, text
    assert "check expected, amount not yet confirmed" in text, text
    assert "St. Anne" in text, text
    assert "ready to send" in text, text


# ---------------------------------------------------------------------------
# Shared helper
# ---------------------------------------------------------------------------

def test_money_truth_renders_three_shared_facts(money_fixture):
    from money_truth import render_money_answer

    answer = render_money_answer("maestro")
    assert_three_money_facts(answer)
    assert "as of 2026-07-08" in answer
    # Settled past never resurfaces as owed, but is named honestly.
    assert "settled" in answer
    assert "Outstanding — none" not in answer


def test_money_truth_empty_data_is_not_tracked_never_none(empty_money_fixture):
    from money_truth import NOT_TRACKED_LINE, render_money_answer

    answer = render_money_answer("chief")
    assert answer == NOT_TRACKED_LINE
    assert "not tracked yet" in answer
    assert "none" not in answer.lower().replace("not a zero balance", "")
    assert "$0" not in answer


def test_money_truth_missing_file_is_not_tracked(tmp_path, monkeypatch):
    import money_truth

    monkeypatch.setattr(money_truth, "DEFAULT_READ_MODEL_PATH", tmp_path / "absent.json", raising=True)
    assert money_truth.render_money_answer("guardian") == money_truth.NOT_TRACKED_LINE


def test_money_truth_question_filter_scopes_to_named_client(money_fixture):
    from money_truth import render_money_answer

    answer = render_money_answer("cassandra", question="did St Anne's pay us?")
    assert "St. Anne" in answer
    assert "settled" in answer  # Apr/May paid
    assert "ready to send" in answer  # July pending-send
    assert "Live Arts MD" not in answer
    assert "Capital Hilton" not in answer


def test_classifier_movement_never_reads_ledger():
    from money_truth import classify_money_question

    # 141 guard-rail: active movement always defers to the refusal gates.
    for prompt in (
        "pay Sarah $500 now",
        "send $500 to Sarah",
        "wire $2,000 to the venue",
        "transfer $75 to checking",
        "zelle the drummer his cut",
        "send 500 dollars to the venue",
    ):
        assert classify_money_question(prompt) == "money_movement", prompt


def test_classifier_read_arrival_and_action_split():
    from money_truth import classify_money_question

    assert classify_money_question(MONEY_QUESTION) == "money_read"
    assert classify_money_question("what's outstanding?") == "money_read"
    assert classify_money_question("did St Anne's pay us?") == "money_read"
    assert classify_money_question("Did the Hilton payment come through?") == "payment_arrival_verify"
    assert classify_money_question("did the check clear?") == "payment_arrival_verify"
    assert classify_money_question("create an invoice for St Anne's") is None
    assert classify_money_question("how's the album coming?") is None


# ---------------------------------------------------------------------------
# CHIEF — financial brain rebuilt FROM the one truth
# ---------------------------------------------------------------------------

@pytest.fixture
def chief_brain(tmp_path, monkeypatch, money_fixture):
    import chief_financial_brain as cfb

    monkeypatch.setattr(cfb, "FINANCIAL_MD", tmp_path / "Financial Report.md", raising=True)
    monkeypatch.setattr(cfb, "_build_narrative", lambda report: "", raising=True)
    return cfb


def test_chief_financial_report_binds_to_money_truth(chief_brain):
    replies = chief_brain.handle(MONEY_QUESTION)
    text = "\n".join(replies)
    assert_three_money_facts(text)
    assert "Outstanding — none" not in text
    assert "receivables_month_bounded" in text  # provenance named


def test_chief_financial_report_empty_data_says_not_tracked(tmp_path, monkeypatch, empty_money_fixture):
    import chief_financial_brain as cfb

    monkeypatch.setattr(cfb, "FINANCIAL_MD", tmp_path / "Financial Report.md", raising=True)
    monkeypatch.setattr(cfb, "_build_narrative", lambda report: "", raising=True)

    replies = cfb.handle("financial report")
    text = "\n".join(replies)
    assert "not tracked yet" in text
    assert "Outstanding — none" not in text
    assert "$0.00" not in text  # no invented certainty from empty data


def test_chief_financial_brain_toy_exports_retired():
    import chief_financial_brain as cfb

    assert not hasattr(cfb, "BILLING_JSONL")
    assert not hasattr(cfb, "BILLING_CSV")
    source = Path(cfb.__file__).read_text(encoding="utf-8")
    assert "OpenClaw/exports/billing_records" not in source


def test_chief_cpa_income_derived_from_money_truth(money_fixture):
    import chief_cpa_brain as cpa

    assert not hasattr(cpa, "BILLING_CSV")
    records = cpa._load_billing_income()
    payments = [r for r in records if r["type"] == "payment"]
    assert round(sum(r["amount"] for r in payments), 2) == 2150.0  # $900 + $625 + $625
    invoices = [r for r in records if r["type"] == "invoice"]
    assert any(r["client"] == "Live Arts MD" and r["amount"] == 1995.0 for r in invoices)


# ---------------------------------------------------------------------------
# CASSANDRA — money-class questions answer from money_truth; payment_verify
# keeps only genuine arrival verification and gains a relevance threshold
# ---------------------------------------------------------------------------

def _empty_finance_fixtures(tmp_path, monkeypatch):
    import cassandra_brain
    import finance_state

    finance_path = tmp_path / "finance_state.json"
    finance_path.write_text(json.dumps({"accounts": {}}), encoding="utf-8")
    reality_path = tmp_path / "cassandra_reality_notes.json"
    reality_path.write_text(json.dumps({}), encoding="utf-8")
    monkeypatch.setattr(finance_state, "FINANCE_STATE_PATH", finance_path, raising=False)
    monkeypatch.setattr(cassandra_brain, "_REALITY_NOTES", reality_path, raising=False)


def _stub_cassandra(monkeypatch, logged):
    import cassandra_brain

    monkeypatch.setattr(cassandra_brain, "load_state", lambda: dict(cassandra_brain._DEFAULT_STATE), raising=False)
    monkeypatch.setattr(cassandra_brain, "save_state", lambda state: None, raising=False)
    monkeypatch.setattr(cassandra_brain, "process_pending_followups", lambda: [], raising=False)
    monkeypatch.setattr(
        cassandra_brain,
        "_log_conversation",
        lambda user_text, replies, route="llm", **kwargs: logged.append({"route": route, "replies": replies}),
        raising=False,
    )


def test_cassandra_gmail_intent_money_read_is_not_payment_verify(money_fixture):
    import cassandra_brain

    decision = cassandra_brain.decide_gmail_intent(MONEY_QUESTION)
    assert decision.category == "money_truth"
    assert decision.allowed is False

    arrival = cassandra_brain.decide_gmail_intent("Did the Hilton payment come through?")
    assert arrival.category == "payment_verify"


def test_cassandra_money_question_answers_from_money_truth(tmp_path, monkeypatch, money_fixture):
    import cassandra_brain

    logged = []
    _empty_finance_fixtures(tmp_path, monkeypatch)
    _stub_cassandra(monkeypatch, logged)

    replies = cassandra_brain.handle(MONEY_QUESTION)

    assert logged[-1]["route"] == "money_truth"
    assert_three_money_facts(replies[0])


def test_cassandra_did_st_annes_pay_us_is_money_class(tmp_path, monkeypatch, money_fixture):
    import cassandra_brain

    logged = []
    _empty_finance_fixtures(tmp_path, monkeypatch)
    _stub_cassandra(monkeypatch, logged)

    replies = cassandra_brain.handle("did St Anne's pay us?")

    assert logged[-1]["route"] == "money_truth"
    assert "St. Anne" in replies[0]
    assert "settled" in replies[0]
    assert "ready to send" in replies[0]


def test_cassandra_session_override_outranks_money_truth(tmp_path, monkeypatch, money_fixture):
    """Operator-corrected session truth still wins over the read-model snapshot."""
    import cassandra_brain

    logged = []
    _empty_finance_fixtures(tmp_path, monkeypatch)
    _stub_cassandra(monkeypatch, logged)
    state = dict(cassandra_brain._DEFAULT_STATE)
    state["session_fact_overrides"] = {
        "live_arts_md": {
            "label": "Live Arts MD",
            "summary": "Live Arts MD is fully reconciled as of this afternoon.",
            "at": "2026-07-08 09:00:00",
        }
    }
    monkeypatch.setattr(cassandra_brain, "load_state", lambda: state, raising=False)
    monkeypatch.setattr(
        cassandra_brain,
        "_get_session_fact_override",
        lambda query, st: ("live_arts_md", st["session_fact_overrides"]["live_arts_md"])
        if "live arts" in query.lower()
        else None,
        raising=False,
    )

    replies = cassandra_brain.handle("does Live Arts owe me money?")

    assert "fully reconciled" in replies[0]
    assert "$1,095" not in replies[0]  # snapshot does not override the operator's correction


def test_cassandra_newsletter_can_never_verify(tmp_path, monkeypatch, money_fixture):
    import cassandra_brain

    _empty_finance_fixtures(tmp_path, monkeypatch)
    monkeypatch.setattr(cassandra_brain, "_detect_payment_verify_intent", lambda text: True, raising=False)

    def fake_broker(agent, capability, params):
        return {
            "ok": True,
            "data": [
                {
                    "from_name": "Annapolis Parks & Rec",
                    "subject": "July newsletter: pool passes and payment plans",
                    "snippet": "Summer programs, payment plans available, sign up today",
                    "date_raw": "2026-07-07 09:00",
                }
            ],
            "error": "",
        }

    monkeypatch.setattr("google_access_broker.call", fake_broker)

    reply = cassandra_brain._handle_payment_verification_request("Did the Hilton payment come through?")

    assert reply is not None
    assert "I've verified" not in reply
    assert "verified a matching notification" not in reply
    assert "Capital Hilton" in reply  # ledger truth included instead
    assert "check expected" in reply


def test_cassandra_correlated_payment_notification_still_verifies(tmp_path, monkeypatch, money_fixture):
    import cassandra_brain

    _empty_finance_fixtures(tmp_path, monkeypatch)
    monkeypatch.setattr(cassandra_brain, "_detect_payment_verify_intent", lambda text: True, raising=False)

    def fake_broker(agent, capability, params):
        return {
            "ok": True,
            "data": [
                {
                    "from_name": "Capital Hilton Accounts Payable",
                    "subject": "Payment issued — check is on the way",
                    "snippet": "Your payment has been processed",
                    "date_raw": "2026-07-07 09:00",
                }
            ],
            "error": "",
        }

    monkeypatch.setattr("google_access_broker.call", fake_broker)

    reply = cassandra_brain._handle_payment_verification_request("Did the Hilton payment come through?")

    assert reply is not None
    assert "I've verified a matching payment notification" in reply
    assert "Capital Hilton" in reply


def test_cassandra_no_notifications_falls_back_to_ledger_not_toy_log(tmp_path, monkeypatch, money_fixture):
    import cassandra_brain

    _empty_finance_fixtures(tmp_path, monkeypatch)
    monkeypatch.setattr(cassandra_brain, "_detect_payment_verify_intent", lambda text: True, raising=False)
    monkeypatch.setattr(
        cassandra_brain,
        "_fetch_payment_verify_context",
        lambda text, **kwargs: "[VERIFIED PAYMENT DATA — no recent Gmail notifications found]",
        raising=False,
    )

    reply = cassandra_brain._handle_payment_verification_request("Did the Hilton payment come through?")

    assert reply is not None
    assert "Capital Hilton" in reply
    assert "check expected" in reply


def test_finance_state_marked_deprecated_for_money_claims():
    import finance_state

    assert getattr(finance_state, "MONEY_CLAIMS_DEPRECATED", False) is True


# ---------------------------------------------------------------------------
# NILES — money-class branch before the catch-all: route + answer
# ---------------------------------------------------------------------------

def test_niles_money_question_routes_with_answer(money_fixture):
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
    import producer_intake

    reply = producer_intake.get_niles_response(MONEY_QUESTION, {})
    assert reply.startswith("Money's Maestro's desk — here's the picture:")
    assert_three_money_facts(reply)


def test_niles_production_questions_keep_the_rig_lane(money_fixture):
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
    import producer_intake

    reply = producer_intake.get_niles_response("the chorus is boring but I want it spacious", {})
    assert "arrival point" in reply
    assert "$1,095" not in reply


# ---------------------------------------------------------------------------
# GUARDIAN — nonapproval responder + context packet finance topic
# ---------------------------------------------------------------------------

def test_guardian_read_only_money_question_answers_from_ledger(money_fixture):
    from chief_nonapproval_responder import nonapproval_response_for_text

    result = nonapproval_response_for_text(MONEY_QUESTION, surface="guardian")

    assert result is not None
    assert result.intent == "money_status"
    assert result.send_performed is False
    assert_three_money_facts(result.reply)
    assert "I cannot tell what you want me to protect" not in result.reply


def test_guardian_outstanding_question_not_catchall(money_fixture):
    from chief_nonapproval_responder import guardian_no_pending_reply

    reply = guardian_no_pending_reply("what's outstanding?")
    assert "I cannot tell what you want me to protect" not in reply
    assert "$1,095" in reply


def test_guardian_movement_still_blocks_not_answers(money_fixture):
    from chief_nonapproval_responder import classify_nonapproval_prompt, nonapproval_response_for_text

    # 141 guard-rail: movement stays money_block; no ledger answer.
    assert classify_nonapproval_prompt("pay Sarah $500 now") == "money_block"
    assert classify_nonapproval_prompt("send $500 to Sarah") == "money_block"
    blocked = nonapproval_response_for_text("pay Sarah $500 now", surface="guardian")
    assert "No money moved" in blocked.reply
    assert "$1,095" not in blocked.reply


def test_guardian_empty_ledger_money_question_says_not_tracked(empty_money_fixture):
    from chief_nonapproval_responder import nonapproval_response_for_text

    result = nonapproval_response_for_text(MONEY_QUESTION, surface="guardian")
    assert result.intent == "money_status"
    assert "not tracked yet" in result.reply
    assert "Outstanding — none" not in result.reply


def test_guardian_context_packet_gains_finance_topic(tmp_path, money_fixture):
    from guardian_context_packet import build_guardian_context_packet

    root = tmp_path / "read_models"
    root.mkdir()
    _write_fixture(root)

    pkt = build_guardian_context_packet(
        question=MONEY_QUESTION, read_model_root=root, require_posture_read_model=False
    )
    finance_facts = [f for f in pkt["facts"] if f["topic"] == "finance_invoice_reconciliation"]
    assert len(finance_facts) == 1
    assert_three_money_facts(finance_facts[0]["value"])
    assert finance_facts[0]["source_ref"]


def test_guardian_context_packet_flags_money_gap_when_absent(tmp_path, money_fixture):
    from guardian_context_packet import build_guardian_context_packet

    root = tmp_path / "read_models"
    root.mkdir()

    pkt = build_guardian_context_packet(
        question=MONEY_QUESTION, read_model_root=root, require_posture_read_model=False
    )
    finance_facts = [f for f in pkt["facts"] if f["topic"] == "finance_invoice_reconciliation"]
    assert len(finance_facts) == 1
    assert "not tracked yet" in finance_facts[0]["value"]


# ---------------------------------------------------------------------------
# Fleet parity — every agent surface produces the SAME three facts
# ---------------------------------------------------------------------------

def test_fleet_parity_same_three_facts_everywhere(tmp_path, monkeypatch, money_fixture):
    import chief_financial_brain as cfb
    import cassandra_brain
    from chief_nonapproval_responder import nonapproval_response_for_text
    from guardian_context_packet import build_guardian_context_packet

    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
    import producer_intake

    surfaces = {}

    # Chief (vault Financial Report pipeline)
    monkeypatch.setattr(cfb, "FINANCIAL_MD", tmp_path / "Financial Report.md", raising=True)
    monkeypatch.setattr(cfb, "_build_narrative", lambda report: "", raising=True)
    surfaces["chief"] = "\n".join(cfb.handle(MONEY_QUESTION))

    # Cassandra
    logged = []
    _empty_finance_fixtures(tmp_path, monkeypatch)
    _stub_cassandra(monkeypatch, logged)
    surfaces["cassandra"] = cassandra_brain.handle(MONEY_QUESTION)[0]

    # Niles
    surfaces["niles"] = producer_intake.get_niles_response(MONEY_QUESTION, {})

    # Guardian (responder + packet)
    surfaces["guardian"] = nonapproval_response_for_text(MONEY_QUESTION, surface="guardian").reply
    root = tmp_path / "read_models"
    root.mkdir(exist_ok=True)
    _write_fixture(root)
    pkt = build_guardian_context_packet(question=MONEY_QUESTION, read_model_root=root, require_posture_read_model=False)
    surfaces["guardian_packet"] = [
        f for f in pkt["facts"] if f["topic"] == "finance_invoice_reconciliation"
    ][0]["value"]

    for name, text in surfaces.items():
        assert_three_money_facts(text)
