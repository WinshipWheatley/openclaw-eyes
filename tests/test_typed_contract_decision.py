from __future__ import annotations

import json
import sqlite3
import threading
import time
from dataclasses import replace

import pytest

import typed_contract_decision as contract


def _ctx(**changes):
    base = contract.ContractContext(agent="maestro", surface="operator_maestro_chat")
    return replace(base, **changes)


@pytest.mark.parametrize(
    ("text", "label"),
    [
        ("send $500 to Draper right now", contract.ContractLabel.REFUSAL),
        ("A3F2 1", contract.ContractLabel.AUTHORITY_TOKEN),
        ("did the Capital Hilton check arrive?", contract.ContractLabel.PAYMENT_ARRIVAL),
        ("what is the status of the Hilton payment?", contract.ContractLabel.PAYMENT_ARRIVAL),
        ("who owes me money right now?", contract.ContractLabel.MONEY_READ),
        ("prep the St Anne's July invoice so I can look it over", contract.ContractLabel.FINALIZED_INVOICE_REVIEW),
        ("Hey Chief, what's your status right now?", contract.ContractLabel.STATUS),
        ("in plain English, what your role is", contract.ContractLabel.IDENTITY),
        ('What do you make of "blorp fizzle invoice quantum"?', contract.ContractLabel.LOW_COHERENCE),
        (
            "Can you please hand the Live Arts PA rental invoice to Cassandra so she can get it out the door?",
            contract.ContractLabel.ROUTE_INSTRUCTION,
        ),
        (
            "The Live Arts PA rental invoice needs to be sent out—can you route it to whoever should handle it?",
            contract.ContractLabel.ROUTE_INSTRUCTION,
        ),
        (
            "walk me through what happens when Cassandra wants to send an invoice",
            contract.ContractLabel.GUARDIAN_GATE_NARRATION,
        ),
    ],
)
def test_deterministic_precedence_labels(text, label):
    decision = contract.decide_contract(text, context=_ctx(), semantic_vote_enabled=False)
    assert decision.label is label
    assert decision.receipt.source == "deterministic"
    assert decision.receipt.authority_granted is False
    assert decision.receipt.model_called is False


def test_payment_status_beats_generic_status():
    decision = contract.decide_contract(
        "Could you tell me the current status of the Capital Hilton check payment?",
        context=_ctx(),
        semantic_vote_enabled=False,
    )
    assert decision.label is contract.ContractLabel.PAYMENT_ARRIVAL
    assert decision.action is contract.DecisionAction.PASS_THROUGH


@pytest.mark.parametrize(
    "text",
    (
        "What state is the St Anne’s July invoice in?",
        "update the invoice status to paid",
    ),
)
def test_invoice_state_never_calls_generic_status_renderer(text):
    decision = contract.decide_contract(
        text,
        context=_ctx(),
        status_renderer=lambda: pytest.fail("generic status renderer ran"),
        semantic_vote_enabled=False,
    )
    assert decision.label is contract.ContractLabel.PAYMENT_ARRIVAL
    assert decision.action is contract.DecisionAction.PASS_THROUGH
    assert contract.ContractLabel.STATUS not in decision.matches


def test_refusal_is_direct_and_never_calls_vote():
    calls = []

    def forbidden(*args, **kwargs):
        calls.append((args, kwargs))
        raise AssertionError("semantic vote must not run")

    decision = contract.decide_contract(
        "delete all my invoices",
        context=_ctx(),
        semantic_vote_enabled=True,
        adaptive_call_fn=forbidden,
    )
    assert decision.label is contract.ContractLabel.REFUSAL
    assert decision.action is contract.DecisionAction.DIRECT_ANSWER
    assert "Nothing" in decision.reply or "nothing" in decision.reply
    assert calls == []


def test_authority_token_is_never_interpreted_or_authorized():
    decision = contract.decide_contract(
        "A3F2 APPROVE",
        context=_ctx(active_session=True, session_kind="billing"),
        semantic_vote_enabled=True,
        adaptive_call_fn=lambda *a, **k: pytest.fail("vote ran"),
    )
    assert decision.label is contract.ContractLabel.AUTHORITY_TOKEN
    assert decision.action is contract.DecisionAction.PASS_THROUGH
    assert decision.reply is None
    assert decision.receipt.authority_granted is False


def test_money_read_renders_directly_without_second_model(monkeypatch):
    monkeypatch.setattr(contract, "_render_money_read", lambda agent, text: "ONE MONEY TRUTH")
    decision = contract.decide_contract(
        "exactly how much is outstanding on my invoices?",
        context=_ctx(),
        semantic_vote_enabled=True,
        adaptive_call_fn=lambda *a, **k: pytest.fail("vote ran"),
    )
    assert decision.action is contract.DecisionAction.DIRECT_ANSWER
    assert decision.reply == "ONE MONEY TRUTH"
    assert decision.receipt.model_called is False


def test_status_renderer_returns_direct_answer_without_model():
    decision = contract.decide_contract(
        "how are things looking on your end right now?",
        context=_ctx(agent="chief", surface="chief_router"),
        status_renderer=lambda: "Services: 6/6 agents online.",
        semantic_vote_enabled=True,
        adaptive_call_fn=lambda *a, **k: pytest.fail("vote ran"),
    )
    assert decision.label is contract.ContractLabel.STATUS
    assert decision.action is contract.DecisionAction.DIRECT_ANSWER
    assert decision.reply == "Services: 6/6 agents online."


def test_guardian_gate_narration_names_both_real_layers():
    decision = contract.decide_contract(
        "Could you explain the safeguards when Clara sends an invoice?",
        context=_ctx(agent="guardian", surface="guardian_listener"),
    )
    assert decision.label is contract.ContractLabel.GUARDIAN_GATE_NARRATION
    assert "up-front Guardian approval" in decision.reply
    assert "dispatch-time SEND_HOLD" in decision.reply
    assert "recipient lock" in decision.reply
    assert "Nothing was sent" in decision.reply


@pytest.mark.parametrize(
    "text",
    [
        "Can you please hand the Live Arts PA rental invoice to Cassandra so she can get it out the door?",
        "The Live Arts PA rental invoice needs to be handled. Which agent are you routing it to, and can you stage that handoff now?",
        "The Live Arts PA rental invoice needs to be sent out—can you route it to whoever should handle it?",
        "the PA rental invoice for Live Arts needs to go out — get it to the right agent",
        "Please stage a dry-run handoff of Live Arts' rental bill to the agent who handles invoices.",
    ],
)
def test_live_arts_route_instruction_calls_bounded_stager_once(text):
    calls = []

    def stage(raw_text, context):
        calls.append((raw_text, context))
        return contract.HandoffResult(
            reply="Cassandra handoff staged. Receipt: workflow_package:abc.",
            receipt_pointer="workflow_package:abc",
            package_id="workflow_package:abc",
        )

    decision = contract.decide_contract(text, context=_ctx(), handoff_stager=stage)
    assert decision.label is contract.ContractLabel.ROUTE_INSTRUCTION
    assert decision.action is contract.DecisionAction.STAGE_HANDOFF
    assert "Cassandra" in decision.reply
    assert len(calls) == 1
    assert decision.receipt.receipt_pointer == "workflow_package:abc"
    assert decision.receipt.authority_granted is False


@pytest.mark.parametrize(
    "near_miss",
    [
        "What is Live Arts' invoice balance?",
        "What do you think of the Live Arts PA rental rates?",
        "Review my Live Arts client rates.",
        "Cassandra sent me the Live Arts invoice yesterday.",
        "Should I send the Live Arts invoice?",
        "Can you get me the Live Arts invoice balance?",
    ],
)
def test_live_arts_near_misses_do_not_stage(near_miss):
    decision = contract.decide_contract(
        near_miss,
        context=_ctx(),
        handoff_stager=lambda *_: pytest.fail("handoff staged"),
        semantic_vote_enabled=False,
    )
    assert decision.action is not contract.DecisionAction.STAGE_HANDOFF


def test_semantic_vote_uses_strict_safe_label_and_cannot_authorize():
    seen = {}

    def fake_call(prompt, **kwargs):
        seen["prompt"] = prompt
        seen["kwargs"] = kwargs
        return json.dumps({"label": "status", "confidence": 0.94, "session_relevant": False})

    decision = contract.decide_contract(
        "give me a plain-language readback of your side of the house",
        context=_ctx(),
        status_renderer=lambda: "Current and terse.",
        semantic_vote_enabled=True,
        adaptive_call_fn=fake_call,
        semantic_timeout_seconds=3.0,
    )
    assert decision.label is contract.ContractLabel.STATUS
    assert decision.reply == "Current and terse."
    assert decision.receipt.source == "semantic_vote"
    assert decision.receipt.model_called is True
    assert decision.receipt.authority_granted is False
    assert seen["kwargs"]["task_class"] == "contract_semantic_vote"
    assert seen["kwargs"]["timeout"] == pytest.approx(1.8)
    assert seen["kwargs"]["model_slot_max_wait_seconds"] == pytest.approx(1.2)
    assert seen["kwargs"]["retry"] is False
    assert "primary_model" not in seen["kwargs"]
    assert "AUTHORITY" not in seen["prompt"]


def test_adapter_vote_default_is_real_without_env_and_explicit_off_is_safe():
    assert contract.semantic_vote_enabled_for_adapter("chief", default=True, environ={}) is True
    assert contract.semantic_vote_enabled_for_adapter("chief", default=False, environ={}) is False
    assert (
        contract.semantic_vote_enabled_for_adapter(
            "chief",
            default=True,
            environ={contract.SEMANTIC_VOTE_ENV: "off"},
        )
        is False
    )


def test_compound_safe_clauses_return_ordered_matches_and_handle_both(monkeypatch):
    monkeypatch.setattr(contract, "_render_money_read", lambda agent, text: "Ledger: Live Arts $1,095 open.")
    calls = []

    def stage(text, context):
        calls.append(text)
        return contract.HandoffResult(
            reply="Cassandra dry-run handoff staged. Receipt: workflow_package:compound.",
            receipt_pointer="workflow_package:compound",
            package_id="workflow_package:compound",
        )

    prompt = "Who owes me money, and can you stage the Live Arts PA rental invoice handoff to Cassandra?"
    decision = contract.decide_contract(prompt, context=_ctx(), handoff_stager=stage)
    assert decision.matches == (
        contract.ContractLabel.MONEY_READ,
        contract.ContractLabel.ROUTE_INSTRUCTION,
    )
    assert decision.action is contract.DecisionAction.STAGE_HANDOFF
    assert "Ledger: Live Arts $1,095 open." in decision.reply
    assert "Cassandra dry-run handoff staged" in decision.reply
    assert calls == [prompt]


def test_compound_status_and_identity_render_both_clauses():
    decision = contract.decide_contract(
        "What's your status right now, and in plain English what is your role?",
        context=_ctx(agent="chief", surface="chief_router"),
        status_renderer=lambda: "Services: 6/6 online.",
    )
    assert decision.matches == (contract.ContractLabel.STATUS, contract.ContractLabel.IDENTITY)
    assert "Services: 6/6 online." in decision.reply
    assert "Chief" in decision.reply


@pytest.mark.parametrize(
    "bad_output",
    [
        "status",
        '{"label":"approve","confidence":1,"session_relevant":false}',
        '{"label":"status","confidence":2,"session_relevant":false}',
        '{"label":"status","confidence":0.9,"session_relevant":false,"decision":"approve"}',
        '{"label":["status","approve"],"confidence":1,"session_relevant":false}',
        "",
    ],
)
def test_semantic_vote_rejects_untyped_or_authority_output(bad_output):
    decision = contract.decide_contract(
        "ambiguous words here",
        context=_ctx(),
        semantic_vote_enabled=True,
        adaptive_call_fn=lambda *_a, **_k: bad_output,
    )
    assert decision.label is contract.ContractLabel.UNRESOLVED
    assert decision.action is contract.DecisionAction.PASS_THROUGH
    assert decision.receipt.authority_granted is False


def test_active_session_uncertain_preserves_without_advancing():
    session = {"status": "active", "active_workflow": "billing", "step": 2}
    before = dict(session)
    decision = contract.decide_contract(
        "maybe that other thing",
        context=_ctx(active_session=True, session_kind="billing", session_snapshot=session),
        semantic_vote_enabled=True,
        adaptive_call_fn=lambda *_a, **_k: "",
    )
    assert decision.label is contract.ContractLabel.UNRESOLVED
    assert decision.action is contract.DecisionAction.PRESERVE_SESSION
    assert decision.receipt.session_preserved is True
    assert "left the open billing step unchanged" in decision.reply
    assert decision.receipt.receipt_pointer.startswith("contract:")
    assert decision.receipt.receipt_pointer in decision.reply
    assert session == before


@pytest.mark.parametrize("renderer_mode", ("raises", "empty", "missing"))
def test_active_status_renderer_failure_preserves_with_receipt(renderer_mode):
    def renderer():
        if renderer_mode == "raises":
            raise RuntimeError("read model unavailable")
        return ""

    decision = contract.decide_contract(
        "what's your status?",
        context=_ctx(active_session=True, session_kind="billing"),
        status_renderer=None if renderer_mode == "missing" else renderer,
        semantic_vote_enabled=True,
        adaptive_call_fn=lambda *a, **k: pytest.fail("semantic vote ran"),
    )
    assert decision.action is contract.DecisionAction.PRESERVE_SESSION
    assert decision.receipt.session_preserved is True
    assert decision.receipt.receipt_pointer in decision.reply


@pytest.mark.parametrize("stager_mode", ("raises", "missing"))
def test_active_route_stager_failure_preserves_with_receipt(stager_mode):
    def stager(*_args):
        raise RuntimeError("queue unavailable")

    decision = contract.decide_contract(
        "stage the Live Arts invoice handoff to Cassandra",
        context=_ctx(active_session=True, session_kind="guided_review"),
        handoff_stager=None if stager_mode == "missing" else stager,
        semantic_vote_enabled=True,
        adaptive_call_fn=lambda *a, **k: pytest.fail("semantic vote ran"),
    )
    assert decision.action is contract.DecisionAction.PRESERVE_SESSION
    assert decision.receipt.session_preserved is True
    assert decision.receipt.receipt_pointer in decision.reply


def test_explicitly_disabled_vote_preserves_active_unknown_without_model():
    decision = contract.decide_contract(
        "maybe that other thing",
        context=_ctx(active_session=True, session_kind="billing"),
        semantic_vote_enabled=False,
        adaptive_call_fn=lambda *a, **k: pytest.fail("semantic vote ran"),
    )
    assert decision.action is contract.DecisionAction.PRESERVE_SESSION
    assert decision.receipt.semantic_vote_status == "disabled"
    assert decision.receipt.session_preserved is True
    assert decision.receipt.receipt_pointer in decision.reply


def test_active_session_explicit_unresolved_vote_preserves():
    decision = contract.decide_contract(
        "ambiguous words here",
        context=_ctx(active_session=True, session_kind="guided_review"),
        semantic_vote_enabled=True,
        adaptive_call_fn=lambda *_a, **_k: json.dumps(
            {"label": "unresolved", "confidence": 0.99, "session_relevant": False}
        ),
    )
    assert decision.action is contract.DecisionAction.PRESERVE_SESSION
    assert decision.receipt.semantic_vote_status == "accepted_unresolved"
    assert decision.receipt.receipt_pointer in decision.reply


def test_temporal_invoice_status_is_not_generic_fleet_status():
    decision = contract.decide_contract(
        "what's the status of St Anne's July invoice compared to what they owed in May?",
        context=_ctx(),
        status_renderer=lambda: pytest.fail("generic status renderer ran"),
    )
    assert decision.label is contract.ContractLabel.PAYMENT_ARRIVAL
    assert decision.action is contract.DecisionAction.PASS_THROUGH
    assert contract.ContractLabel.STATUS not in decision.matches


def test_named_business_status_is_not_generic_fleet_status():
    decision = contract.decide_contract(
        "what's Winship's day / Capital Hilton status?",
        context=_ctx(),
        status_renderer=lambda: pytest.fail("generic fleet status renderer ran"),
        semantic_vote_enabled=False,
    )
    assert decision.label is contract.ContractLabel.UNRESOLVED
    assert decision.action is contract.DecisionAction.PASS_THROUGH
    assert contract.ContractLabel.STATUS not in decision.matches


def test_active_session_relevant_vote_captures_but_never_mutates():
    session = {"status": "active", "active_workflow": "billing", "step": 2}
    before = dict(session)
    decision = contract.decide_contract(
        "June 14",
        context=_ctx(active_session=True, session_kind="billing", session_snapshot=session),
        semantic_vote_enabled=True,
        adaptive_call_fn=lambda *_a, **_k: json.dumps(
            {"label": "session_relevant", "confidence": 0.91, "session_relevant": True}
        ),
    )
    assert decision.label is contract.ContractLabel.SESSION_RELEVANT
    assert decision.action is contract.DecisionAction.CAPTURE_SESSION
    assert session == before


def test_outside_session_timeout_fails_open_to_current_routing():
    decision = contract.decide_contract(
        "ambiguous words here",
        context=_ctx(active_session=False),
        semantic_vote_enabled=True,
        adaptive_call_fn=lambda *_a, **_k: "",
    )
    assert decision.action is contract.DecisionAction.PASS_THROUGH
    assert decision.receipt.session_preserved is False


def test_session_answer_predicate_precedes_vote():
    decision = contract.decide_contract(
        "June 14",
        context=_ctx(active_session=True, session_kind="billing"),
        session_answer_predicate=lambda text: text == "June 14",
        semantic_vote_enabled=True,
        adaptive_call_fn=lambda *_a, **_k: pytest.fail("vote ran"),
    )
    assert decision.label is contract.ContractLabel.SESSION_RELEVANT
    assert decision.action is contract.DecisionAction.CAPTURE_SESSION
    assert decision.receipt.source == "deterministic"


def test_short_grammatical_policy_answer_is_not_gibberish():
    decision = contract.decide_contract(
        "Direct deposit stays manual approval only.",
        context=_ctx(active_session=True, session_kind="guided_review"),
        session_answer_predicate=lambda _text: True,
        semantic_vote_enabled=True,
        adaptive_call_fn=lambda *a, **k: pytest.fail("vote ran"),
    )
    assert decision.label is contract.ContractLabel.SESSION_RELEVANT
    assert decision.action is contract.DecisionAction.CAPTURE_SESSION


def test_contract_context_and_receipt_are_explicit_serializable_types():
    decision = contract.decide_contract("status?", context=_ctx(), status_renderer=lambda: "OK")
    payload = decision.to_dict()
    assert payload["context"]["agent"] == "maestro"
    assert payload["label"] == "status"
    assert payload["action"] == "direct_answer"
    assert payload["receipt"]["schema_version"] == "typed_contract_decision_v1"
    assert payload["receipt"]["decision_id"].startswith("contract:")
    json.dumps(payload)


def test_warm_deterministic_sentinel_is_bounded_and_never_calls_adaptive():
    # Prime lazy imports so this is genuinely a warm-path measurement.  The
    # fleet can be CPU-contended; import time is not contract latency.
    contract.decide_contract(
        "Hey Chief, what's your status right now?",
        context=_ctx(agent="chief", surface="chief_router"),
        status_renderer=lambda: "Services: 6/6 online.",
        semantic_vote_enabled=False,
    )
    started = time.monotonic()
    decision = contract.decide_contract(
        "Hey Chief, what's your status right now?",
        context=_ctx(agent="chief", surface="chief_router"),
        status_renderer=lambda: "Services: 6/6 online.",
        semantic_vote_enabled=True,
        adaptive_call_fn=lambda *a, **k: pytest.fail("adaptive path ran"),
    )
    elapsed = time.monotonic() - started
    assert decision.reply == "Services: 6/6 online."
    assert elapsed < 0.25


def test_simulated_slot_contention_error_preserves_inside_total_budget():
    session = {"status": "active", "active_workflow": "billing", "step": 4}
    before = json.dumps(session, sort_keys=True)

    def contended(*_args, **_kwargs):
        time.sleep(0.02)
        raise RuntimeError("simulated slot contention")

    started = time.monotonic()
    decision = contract.decide_contract(
        "maybe the other one",
        context=_ctx(active_session=True, session_kind="billing", session_snapshot=session),
        semantic_vote_enabled=True,
        adaptive_call_fn=contended,
        semantic_timeout_seconds=0.05,
    )
    elapsed = time.monotonic() - started
    assert decision.action is contract.DecisionAction.PRESERVE_SESSION
    assert decision.receipt.semantic_vote_status == "error:RuntimeError"
    assert elapsed <= 0.5
    assert json.dumps(session, sort_keys=True) == before


def test_forced_timeout_preserves_no_retry_with_end_to_end_budget():
    session = {"status": "active", "active_workflow": "guided_review", "step": 1}
    seen = {}

    def forced_timeout(_prompt, **kwargs):
        seen.update(kwargs)
        time.sleep(kwargs["timeout"] + kwargs["model_slot_max_wait_seconds"])
        return ""

    started = time.monotonic()
    decision = contract.decide_contract(
        "maybe that other thing",
        context=_ctx(active_session=True, session_kind="guided_review", session_snapshot=session),
        semantic_vote_enabled=True,
        adaptive_call_fn=forced_timeout,
        semantic_timeout_seconds=0.05,
    )
    elapsed = time.monotonic() - started
    assert seen["retry"] is False
    assert seen["attempts"] == 1
    assert seen["timeout"] + seen["model_slot_max_wait_seconds"] == pytest.approx(0.05)
    assert decision.action is contract.DecisionAction.PRESERVE_SESSION
    assert decision.receipt.session_preserved is True
    assert elapsed <= 0.5


def test_semantic_vote_overrun_hits_real_wall_and_cannot_block_caller(monkeypatch, tmp_path):
    db_path = tmp_path / "receipts.sqlite3"
    monkeypatch.setenv(contract.CONTRACT_RECEIPT_DB_ENV, str(db_path))
    seen = {}
    entered = threading.Event()

    def ignores_provider_timeout(_prompt, **kwargs):
        seen.update(kwargs)
        entered.set()
        time.sleep(0.5)
        return json.dumps({"label": "session_relevant", "confidence": 0.99, "session_relevant": True})

    started = time.monotonic()
    decision = contract.decide_contract(
        "maybe that other thing",
        context=_ctx(active_session=True, session_kind="guided_review"),
        semantic_vote_enabled=True,
        adaptive_call_fn=ignores_provider_timeout,
        semantic_timeout_seconds=0.04,
    )
    elapsed = time.monotonic() - started

    assert entered.wait(0.5)
    assert seen["retry"] is False
    assert seen["attempts"] == 1
    assert seen["timeout"] + seen["model_slot_max_wait_seconds"] == pytest.approx(0.04)
    assert decision.action is contract.DecisionAction.PRESERVE_SESSION
    assert decision.receipt.semantic_vote_status == "deadline_exceeded"
    assert decision.receipt.receipt_persisted is True
    assert elapsed < 0.2


def test_preserve_receipt_sink_is_idempotent_resolvable_and_payload_free(monkeypatch, tmp_path):
    db_path = tmp_path / "generated" / "receipts" / "contract.sqlite3"
    monkeypatch.setenv(contract.CONTRACT_RECEIPT_DB_ENV, str(db_path))
    raw_marker = "RAW-MESSAGE-MUST-NOT-BE-STORED-49D2"
    session_marker = "SESSION-DRAFT-MUST-NOT-BE-STORED-A86C"

    direct = contract.decide_contract(
        "what's your status?",
        context=_ctx(),
        status_renderer=lambda: "Services: 6/6 online.",
    )
    assert direct.action is contract.DecisionAction.DIRECT_ANSWER
    assert direct.receipt.receipt_persistence_status == "not_applicable"
    assert not db_path.exists()

    context = _ctx(
        active_session=True,
        session_kind="guided_review",
        session_snapshot={"status": "active", "draft": session_marker},
    )
    first = contract.decide_contract(
        raw_marker,
        context=context,
        semantic_vote_enabled=False,
    )
    second = contract.decide_contract(
        raw_marker,
        context=context,
        semantic_vote_enabled=False,
    )

    assert first.receipt.decision_id == first.receipt.receipt_pointer
    assert first.receipt.receipt_persisted is True
    assert first.receipt.receipt_persistence_status == "inserted"
    assert second.receipt.decision_id == first.receipt.decision_id
    assert second.receipt.receipt_persisted is True
    assert second.receipt.receipt_persistence_status == "already_present"

    with sqlite3.connect(db_path) as connection:
        rows = connection.execute("SELECT * FROM contract_preserve_receipts").fetchall()
    assert len(rows) == 1
    assert rows[0][0] == first.receipt.decision_id
    assert rows[0][3] == contract.DecisionAction.PRESERVE_SESSION.value

    resolved = contract.resolve_contract_receipt(first.receipt.receipt_pointer, path=db_path)
    assert resolved is not None
    assert resolved["decision_id"] == first.receipt.decision_id
    assert resolved["action"] == contract.DecisionAction.PRESERVE_SESSION.value
    database_bytes = db_path.read_bytes()
    assert raw_marker.encode() not in database_bytes
    assert session_marker.encode() not in database_bytes


def test_preserve_receipt_sink_prunes_oldest_rows_to_fixed_bound(monkeypatch, tmp_path):
    db_path = tmp_path / "bounded.sqlite3"
    monkeypatch.setenv(contract.CONTRACT_RECEIPT_DB_ENV, str(db_path))
    monkeypatch.setattr(contract, "MAX_CONTRACT_PRESERVE_RECEIPTS", 2)
    decisions = [
        contract.decide_contract(
            f"ambiguous preserve answer {index}",
            context=_ctx(active_session=True, session_kind="billing"),
            semantic_vote_enabled=False,
        )
        for index in range(3)
    ]

    with sqlite3.connect(db_path) as connection:
        durable_ids = {
            row[0]
            for row in connection.execute(
                "SELECT decision_id FROM contract_preserve_receipts ORDER BY rowid"
            ).fetchall()
        }
    assert len(durable_ids) == 2
    assert decisions[0].receipt.decision_id not in durable_ids
    assert decisions[1].receipt.decision_id in durable_ids
    assert decisions[2].receipt.decision_id in durable_ids


# ── Fable review additions (2026-07-10): live-composition vote fixes ──────────
# The live qwen3 model narrates prose around its JSON even with think=False and
# once emitted the PROMPT'S OWN template object. These lock in the extraction
# parser, the identity slang widening, and the env kill-switch semantics.


def test_parse_semantic_vote_extracts_json_after_prose_preamble():
    from typed_contract_decision import ContractLabel, _parse_semantic_vote

    raw = (
        "We are classifying the message. Steps: think carefully.\n"
        '{"label":"status","confidence":0.9,"session_relevant":false} done.'
    )
    parsed = _parse_semantic_vote(raw)
    assert parsed is not None
    assert parsed[0] is ContractLabel.STATUS


def test_parse_semantic_vote_rejects_prose_only_and_template_object():
    from typed_contract_decision import _parse_semantic_vote

    assert _parse_semantic_vote("We are to return exactly one JSON object.") is None
    # The model once echoed the prompt's template — must stay invalid.
    assert _parse_semantic_vote('{"label":"<label>","confidence":0.0,"session_relevant":false}') is None


def test_identity_matcher_covers_slang_and_handle_phrasings():
    from typed_contract_decision import _is_identity

    assert _is_identity("wait so whats ur whole job exactly lol")
    assert _is_identity("remind me what it is you actually handle around here?")


def test_slangy_identity_ask_is_identity_not_low_coherence():
    from typed_contract_decision import ContractContext, ContractLabel, decide_contract

    ctx = ContractContext(
        agent="maestro",
        surface="operator_maestro_chat",
        source_message_id="t",
        active_session=False,
        session_kind="",
        session_field="",
        session_snapshot={},
    )
    decision = decide_contract(
        "wait so whats ur whole job exactly lol",
        context=ctx,
        semantic_vote_enabled=False,
    )
    assert ContractLabel(str(decision.receipt.label)) is ContractLabel.IDENTITY


def test_vote_env_kill_switch_overrides_default_true():
    from typed_contract_decision import semantic_vote_enabled_for_adapter

    assert semantic_vote_enabled_for_adapter("maestro", default=True, environ={}) is True
    assert (
        semantic_vote_enabled_for_adapter(
            "maestro", default=True, environ={"OPENCLAW_CONTRACT_VOTE_ADAPTERS": "off"}
        )
        is False
    )
