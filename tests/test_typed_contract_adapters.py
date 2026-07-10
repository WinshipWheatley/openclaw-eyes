from __future__ import annotations

import asyncio
import importlib
import json
import sys
import types
from pathlib import Path

import pytest

import typed_contract_decision as contract


class _MustNotReach(Exception):
    pass


def _fresh_chief_session() -> dict:
    from clarify_session_contract import stamp_clarify_session

    workflow_state = {
        "active": True,
        "mode": "INVOICE",
        "step": 2,
        "answers": {},
        "last_field": "client_name",
    }
    stamp_clarify_session(workflow_state, surface="chief")
    return {
        "status": "active",
        "active_workflow": "billing",
        "step": 2,
        "workflow_state": workflow_state,
    }


def _fresh_cockpit_text(**extra) -> str:
    from clarify_session_contract import stamp_clarify_session

    session = {"state": "AWAITING_CLIENT", "client": None, "step": 2, **extra}
    stamp_clarify_session(session, surface="cassandra_telegram")
    return json.dumps(session, separators=(",", ":"), sort_keys=True) + "\n"


def test_maestro_humanized_chief_status_uses_typed_contract(monkeypatch):
    import maestro_cassandra_responder as maestro

    monkeypatch.setattr(
        maestro,
        "_answer_with_maestro_brain",
        lambda *a, **k: (_ for _ in ()).throw(_MustNotReach("model answer path ran")),
    )
    result = maestro.answer_frontdoor_chat("Hey Chief, what's your status right now?")
    assert result.status == "ANSWER_READY"
    assert result.intent_class == "maestro_bare_status_readback"
    assert result.machine_proof["typed_contract_decision"]["label"] == "status"
    assert result.machine_proof["typed_contract_decision"]["model_called"] is False


def test_maestro_live_arts_stages_real_queue_record_once(tmp_path, monkeypatch):
    import maestro_cassandra_responder as maestro

    sqlite_path = tmp_path / "queue.sqlite"
    session = {
        "workflow_package_sqlite_path": str(sqlite_path),
        "contract_created_at": "2026-07-10T03:00:00+00:00",
    }
    result = maestro.answer_frontdoor_chat(
        "The Live Arts PA rental invoice needs to be sent out—can you route it to whoever should handle it?",
        session=session,
    )
    assert result.status == "ANSWER_READY"
    assert result.intent_class == "live_arts_invoice_handoff"
    assert "Cassandra" in result.plain_summary
    assert "has not claimed" in result.plain_summary
    assert "Nothing was sent" in result.plain_summary
    assert result.machine_proof["typed_contract_decision"]["label"] == "route_instruction"
    assert sqlite_path.is_file()

    import sqlite3

    with sqlite3.connect(sqlite_path) as conn:
        assert conn.execute("select count(*) from packages").fetchone()[0] == 1
        assert conn.execute("select assigned from worker_assignments").fetchone()[0] == 0


def test_maestro_verbatim_gibberish_wrapper_never_reaches_digest(monkeypatch):
    import maestro_cassandra_responder as maestro

    monkeypatch.setattr(
        maestro,
        "classify_frontdoor_intent",
        lambda *_: (_ for _ in ()).throw(_MustNotReach("legacy classifier ran")),
    )
    result = maestro.answer_frontdoor_chat('What do you make of "blorp fizzle invoice quantum"?')
    assert result.status == "ANSWER_READY"
    assert result.intent_class == "gibberish_low_coherence"
    assert "client" not in result.plain_summary.lower()
    assert "money" not in result.plain_summary.lower()


def test_maestro_active_session_contract_exception_fails_closed(monkeypatch):
    import maestro_cassandra_responder as maestro

    session = {"status": "active", "active_workflow": "clarify", "pending_field": "client"}
    before = json.dumps(session, sort_keys=True)
    monkeypatch.setattr(contract, "decide_contract", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    monkeypatch.setattr(
        maestro,
        "classify_frontdoor_intent",
        lambda *_: (_ for _ in ()).throw(_MustNotReach("legacy classifier ran")),
    )
    result = maestro.answer_frontdoor_chat("maybe that other thing", session=session)
    assert result.intent_class == "typed_contract_session_preserved"
    assert result.machine_proof["typed_contract_decision"]["source"] == "adapter_error"
    assert "Receipt: contract:" in result.plain_summary
    assert json.dumps(session, sort_keys=True) == before


@pytest.mark.parametrize("renderer_mode", ("raises", "empty"))
def test_maestro_active_status_renderer_failure_never_reopens_legacy_session(
    renderer_mode, monkeypatch
):
    import maestro_cassandra_responder as maestro

    monkeypatch.delenv("OPENCLAW_CONTRACT_VOTE_ADAPTERS", raising=False)
    session = {"status": "active", "active_workflow": "billing", "pending_field": "client"}
    before = json.dumps(session, sort_keys=True)
    if renderer_mode == "raises":
        monkeypatch.setattr(
            maestro,
            "build_maestro_bare_status_answer",
            lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("status unavailable")),
        )
    else:
        monkeypatch.setattr(
            maestro,
            "build_maestro_bare_status_answer",
            lambda **_kwargs: {"plain_summary": ""},
        )
    monkeypatch.setattr(
        maestro,
        "classify_frontdoor_intent",
        lambda *_: (_ for _ in ()).throw(_MustNotReach("legacy session classifier ran")),
    )
    result = maestro.answer_frontdoor_chat("what's your status?", session=session)
    assert result.intent_class == "chief_bare_status_readback" or result.intent_class == "maestro_bare_status_readback"
    assert result.machine_proof["typed_contract_decision"]["action"] == "preserve_session"
    assert result.machine_proof["typed_contract_decision"]["session_preserved"] is True
    assert "Receipt: contract:" in result.plain_summary
    assert json.dumps(session, sort_keys=True) == before


def _processor_classification(processor, filename="request.json"):
    return processor.RequestClassification(
        classification_id="test-classification",
        source_request_filename=filename,
        request_family="WORKFLOW_PACKAGE_REQUEST",
        selected_rail="workflow_package_request_consumer",
        classification_reason="test",
        future_supported=False,
        next_safe_move="test",
    )


def _maestro_raw_request(text: str, **extra) -> dict:
    return {
        "request_id": "request:test-maestro-contract",
        "kind": "OPERATOR_INSTRUCTION_PACKAGE_REQUEST",
        "active_surface_ref": "operator_maestro_chat",
        "operator_text": text,
        "authority_boundary": {
            "email_send_allowed": False,
            "ledger_posting_allowed": False,
            "money_movement_allowed": False,
        },
        **extra,
    }


def test_request_processor_passes_bounded_safe_session_scalars_to_maestro(monkeypatch, tmp_path):
    import openclaw_request_processor as processor

    captured = {}

    def capture(_text, *, session, **_kwargs):
        captured.update(session)
        raise _MustNotReach("captured before response assembly")

    raw = _maestro_raw_request(
        "maybe that other thing",
        session={
            "source_message_id": "telegram-1042",
            "status": "active",
            "active_workflow": "billing",
            "pending_field": "client_name",
            "current_question_id": "q-7",
            "context_type": "clarify_session",
            "untrusted": "must-not-cross",
        },
        context={"status": "active\nINJECT", "pending_field": {"nested": "reject"}},
    )
    monkeypatch.setattr(processor.maestro_cassandra_responder, "answer_frontdoor_chat", capture)
    with pytest.raises(_MustNotReach, match="captured"):
        processor._process_maestro_frontdoor_operator_instruction(
            tmp_path / "request.json",
            raw,
            classification=_processor_classification(processor),
            route_decision={},
        )
    assert captured == {
        "source_message_id": "telegram-1042",
        "status": "active",
        "active_workflow": "billing",
        "pending_field": "client_name",
        "current_question_id": "q-7",
        "context_type": "clarify_session",
    }


def test_exact_maestro_money_nudge_compound_assembles_both_and_one_unclaimed_package(
    monkeypatch, tmp_path
):
    import money_truth
    import openclaw_request_processor as processor
    import sqlite3
    import workflow_package_queue as queue

    prompt = "who owes me money right now, and draft the nudge for whichever one's biggest?"
    sqlite_path = tmp_path / "queue.sqlite"
    monkeypatch.setattr(queue, "DEFAULT_SQLITE_PATH", sqlite_path)
    monkeypatch.setattr(money_truth, "render_money_answer", lambda *a, **k: "MONEY-HALF-GROUNDED")
    response = processor._process_maestro_frontdoor_operator_instruction(
        tmp_path / "compound.json",
        _maestro_raw_request(prompt),
        classification=_processor_classification(processor, "compound.json"),
        route_decision={"selected_rail": "workflow_package_request_consumer"},
    )
    assert response is not None
    assert response.internal_status == "RESPONSE_READY"
    assert "MONEY-HALF-GROUNDED" in response.operator_message
    assert "Cassandra" in response.operator_message
    assert "has not claimed" in response.operator_message
    detail = response.detail_disclosure
    responder = detail["maestro_cassandra_responder"]
    assert responder["intent_class"] == "cassandra_receivables_nudge_handoff"
    assert responder["machine_proof"]["typed_contract_handoff_workflow_ref"] == (
        "cassandra_receivables_nudge_handoff"
    )
    assert responder["machine_proof"]["typed_contract_matches"] == [
        "money_read",
        "route_instruction",
    ]
    assert detail["workflow_package_staged"] is True
    assert response.what_happened[1] == (
        "The typed Maestro contract staged one bounded, unclaimed workflow package and returned its receipt."
    )
    assert response.what_happened[2] == "No worker claimed or executed the staged package."
    with sqlite3.connect(sqlite_path) as conn:
        assert conn.execute("select count(*) from packages").fetchone()[0] == 1
        assert conn.execute("select workflow_ref from packages").fetchone()[0] == (
            "cassandra_receivables_nudge_handoff"
        )
        assert conn.execute("select worker_ref, assigned from worker_assignments").fetchone() == (
            "cassandra_receivables_lane",
            0,
        )


def test_chief_contract_runs_before_history_or_session_capture(monkeypatch):
    import chief_router

    session = _fresh_chief_session()
    before = json.dumps(session, sort_keys=True)
    monkeypatch.delenv("OPENCLAW_CONTRACT_VOTE_ADAPTERS", raising=False)
    monkeypatch.setattr(chief_router, "load_session", lambda: session)
    monkeypatch.setattr(
        contract,
        "_call_semantic_vote",
        lambda *a, **k: (None, "timeout_or_invalid"),
    )
    monkeypatch.setattr(
        chief_router,
        "append_history",
        lambda *a, **k: (_ for _ in ()).throw(_MustNotReach("history mutated")),
    )
    result = chief_router._route_message_inner("maybe that other thing")
    assert result["intent"] == "typed_contract_session_preserved"
    assert "left the open billing step unchanged" in result["reply"]
    assert result["contract_decision"]["receipt_pointer"] in result["reply"]
    assert json.dumps(session, sort_keys=True) == before


def test_chief_authority_code_bypasses_semantic_vote(monkeypatch):
    import chief_router

    monkeypatch.setenv("OPENCLAW_CONTRACT_VOTE_ADAPTERS", "chief")
    monkeypatch.setattr(contract, "_call_semantic_vote", lambda *a, **k: pytest.fail("vote ran"))
    monkeypatch.setattr(chief_router, "has_pending_approval", lambda: False)
    result = chief_router._route_message_inner("A3F2 1")
    assert result["intent"] == "approval_response"
    assert "No approval was applied" in result["reply"]


def test_chief_humanized_status_avoids_fallback_model(monkeypatch):
    import chief_router

    monkeypatch.setattr(chief_router, "load_session", lambda: {})
    monkeypatch.setattr(
        chief_router,
        "_chief_fallback_reply",
        lambda *_: (_ for _ in ()).throw(_MustNotReach("fallback model ran")),
    )
    result = chief_router._route_message_inner("Hey Chief, what's your status right now?")
    assert result["intent"] == "chief_bare_status_readback"
    assert result["contract_decision"]["label"] == "status"


def test_chief_active_session_contract_exception_fails_closed(monkeypatch):
    import chief_router

    session = _fresh_chief_session()
    before = json.dumps(session, sort_keys=True)
    monkeypatch.setattr(chief_router, "load_session", lambda: session)
    monkeypatch.setattr(contract, "decide_contract", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    monkeypatch.setattr(
        chief_router,
        "append_history",
        lambda *a, **k: (_ for _ in ()).throw(_MustNotReach("history mutated")),
    )
    result = chief_router._route_message_inner("maybe that other thing")
    assert result["intent"] == "typed_contract_session_preserved"
    assert result["contract_decision"]["source"] == "adapter_error"
    assert json.dumps(session, sort_keys=True) == before


def test_chief_explicit_vote_off_preserves_unknown_without_legacy_mutation(monkeypatch):
    import chief_router

    session = _fresh_chief_session()
    before = json.dumps(session, sort_keys=True)
    monkeypatch.setenv("OPENCLAW_CONTRACT_VOTE_ADAPTERS", "off")
    monkeypatch.setattr(chief_router, "load_session", lambda: session)
    monkeypatch.setattr(
        chief_router,
        "append_history",
        lambda *a, **k: (_ for _ in ()).throw(_MustNotReach("legacy history mutated")),
    )
    monkeypatch.setattr(
        contract,
        "_call_semantic_vote",
        lambda *a, **k: (_ for _ in ()).throw(_MustNotReach("disabled vote ran")),
    )
    result = chief_router._route_message_inner("maybe that other thing")
    assert result["intent"] == "typed_contract_session_preserved"
    assert result["contract_decision"]["semantic_vote_status"] == "disabled"
    assert "Receipt: contract:" in result["reply"]
    assert json.dumps(session, sort_keys=True) == before


def test_chief_stale_billing_session_reaches_existing_expiry_owner_without_vote(monkeypatch):
    import chief_router

    stale = _fresh_chief_session()
    stale["workflow_state"]["clarify_contract"]["touched_at_epoch"] = 1.0
    calls = []
    monkeypatch.delenv("OPENCLAW_CONTRACT_VOTE_ADAPTERS", raising=False)
    monkeypatch.setattr(chief_router, "load_session", lambda: stale)
    monkeypatch.setattr(
        contract,
        "_call_semantic_vote",
        lambda *a, **k: (_ for _ in ()).throw(_MustNotReach("typed vote ran for stale session")),
    )
    monkeypatch.setattr(chief_router, "billing_handle", lambda text: calls.append(text) or [])
    monkeypatch.setattr(chief_router, "append_history", lambda *a, **k: None)
    monkeypatch.setattr(chief_router, "email_intent", lambda text: True)
    monkeypatch.setattr(chief_router, "email_handle", lambda text: ["LEGACY-EXPIRY-OWNER-RAN"])
    result = chief_router._route_message_inner("email Alice about tomorrow")
    assert calls == ["email Alice about tomorrow"]
    assert result == {"intent": "email_draft", "replies": ["LEGACY-EXPIRY-OWNER-RAN"]}


class _FakeFilter:
    def __and__(self, _other):
        return self

    def __invert__(self):
        return self


def _install_telegram_stubs(monkeypatch, *, guardian: bool = False):
    telegram = types.ModuleType("telegram")
    telegram.Update = object
    telegram.InlineKeyboardMarkup = object
    error = types.ModuleType("telegram.error")
    error.BadRequest = Exception
    error.Forbidden = Exception

    class _ApplicationBuilder:
        def token(self, _token):
            return self

        def build(self):
            return types.SimpleNamespace(add_handler=lambda *a, **k: None, run_polling=lambda: None)

    ext = types.ModuleType("telegram.ext")
    ext.ApplicationBuilder = _ApplicationBuilder
    ext.CallbackQueryHandler = lambda *a, **k: None
    ext.MessageHandler = lambda *a, **k: None
    ext.filters = types.SimpleNamespace(
        TEXT=_FakeFilter(), COMMAND=_FakeFilter(), VOICE=_FakeFilter()
    )
    ext.ContextTypes = types.SimpleNamespace(DEFAULT_TYPE=object)
    monkeypatch.setitem(sys.modules, "telegram", telegram)
    monkeypatch.setitem(sys.modules, "telegram.error", error)
    monkeypatch.setitem(sys.modules, "telegram.ext", ext)


def _load_cassandra_listener(monkeypatch):
    monkeypatch.setenv("CASSANDRA_BOT_TOKEN", "test-token")
    monkeypatch.setenv("TELEGRAM_AUTHORIZED_USER_ID", "123")
    _install_telegram_stubs(monkeypatch)
    sys.modules.pop("cassandra_listener", None)
    module = importlib.import_module("cassandra_listener")
    return importlib.reload(module)


def test_cassandra_listener_contract_precedes_cockpit_and_brain(monkeypatch):
    listener = _load_cassandra_listener(monkeypatch)
    monkeypatch.setattr(
        listener,
        "_try_invoice_cockpit",
        lambda *a, **k: (_ for _ in ()).throw(_MustNotReach("cockpit ran")),
    )
    monkeypatch.setattr(
        listener,
        "cassandra_handle",
        lambda *a, **k: (_ for _ in ()).throw(_MustNotReach("brain ran")),
    )
    replies = asyncio.run(
        listener._run_cassandra_handle_async(
            "Could you explain the safeguards when Clara sends an invoice?",
            {"surface": "cassandra_telegram", "source_user_label": "operator"},
        )
    )
    assert len(replies) == 1
    assert "up-front Guardian approval" in replies[0]
    assert "dispatch-time SEND_HOLD" in replies[0]


def test_cassandra_finalized_review_delegates_to_existing_cockpit(monkeypatch):
    listener = _load_cassandra_listener(monkeypatch)
    calls = []

    def cockpit(text, meta):
        calls.append((text, meta))
        return ["COCKPIT-OWNS-FINALIZED-ARTIFACT"]

    monkeypatch.setattr(listener, "_try_invoice_cockpit", cockpit)
    replies = asyncio.run(
        listener._run_cassandra_handle_async(
            "prep the St Anne's July invoice so I can look it over",
            {"surface": "cassandra_telegram", "source_user_label": "operator"},
        )
    )
    assert replies == ["COCKPIT-OWNS-FINALIZED-ARTIFACT"]
    assert len(calls) == 1


def test_cassandra_compound_money_then_finalized_review_sequences_both_once(monkeypatch):
    listener = _load_cassandra_listener(monkeypatch)
    import cassandra_brain

    monkeypatch.setattr(
        cassandra_brain,
        "_handle_payment_verification_request",
        lambda text: "PAYMENT-HALF-GROUNDED",
    )
    calls = []

    def cockpit(text, meta):
        calls.append((text, meta))
        return ["FINALIZED-REVIEW-HALF"]

    monkeypatch.setattr(listener, "_try_invoice_cockpit", cockpit)
    prompt = (
        "did St Anne's pay us, and if not can you get their invoice ready for my review "
        "while you're at it?"
    )
    replies = asyncio.run(
        listener._run_cassandra_handle_async(
            prompt,
            {"surface": "cassandra_telegram", "source_user_label": "operator"},
        )
    )
    assert replies == ["PAYMENT-HALF-GROUNDED", "FINALIZED-REVIEW-HALF"]
    assert len(calls) == 1


def test_cassandra_active_cockpit_timeout_preserves_file_byte_for_byte(tmp_path, monkeypatch):
    listener = _load_cassandra_listener(monkeypatch)
    session_path = tmp_path / "cockpit-session.json"
    original = _fresh_cockpit_text()
    session_path.write_text(original, encoding="utf-8")
    monkeypatch.delenv("OPENCLAW_CONTRACT_VOTE_ADAPTERS", raising=False)
    monkeypatch.setattr(contract, "_call_semantic_vote", lambda *a, **k: (None, "timeout_or_invalid"))
    monkeypatch.setattr(
        listener,
        "_try_invoice_cockpit",
        lambda *a, **k: (_ for _ in ()).throw(_MustNotReach("cockpit advanced")),
    )
    replies = asyncio.run(
        listener._run_cassandra_handle_async(
            "maybe that other thing",
            {
                "surface": "cassandra_telegram",
                "source_user_label": "operator",
                "invoice_cockpit_session_path": str(session_path),
            },
        )
    )
    assert "left the open invoice cockpit step unchanged" in replies[0]
    assert "Receipt: contract:" in replies[0]
    assert session_path.read_text(encoding="utf-8") == original


def test_cassandra_active_cockpit_contract_exception_fails_closed(tmp_path, monkeypatch):
    listener = _load_cassandra_listener(monkeypatch)
    session_path = tmp_path / "cockpit-session.json"
    original = _fresh_cockpit_text()
    session_path.write_text(original, encoding="utf-8")
    monkeypatch.setattr(contract, "decide_contract", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    monkeypatch.setattr(
        listener,
        "_try_invoice_cockpit",
        lambda *a, **k: (_ for _ in ()).throw(_MustNotReach("cockpit advanced")),
    )
    replies = asyncio.run(
        listener._run_cassandra_handle_async(
            "maybe that other thing",
            {
                "surface": "cassandra_telegram",
                "source_user_label": "operator",
                "invoice_cockpit_session_path": str(session_path),
            },
        )
    )
    assert "Receipt: contract:" in replies[0]
    assert session_path.read_text(encoding="utf-8") == original


def test_cassandra_stale_cockpit_falls_through_to_existing_expiry_owner(tmp_path, monkeypatch):
    listener = _load_cassandra_listener(monkeypatch)
    from clarify_session_contract import stamp_clarify_session

    session = {"state": "AWAITING_CLIENT", "step": 2}
    stamp_clarify_session(session, surface="cassandra_telegram", now=1.0)
    session_path = tmp_path / "stale-cockpit.json"
    session_path.write_text(json.dumps(session), encoding="utf-8")
    calls = []
    monkeypatch.delenv("OPENCLAW_CONTRACT_VOTE_ADAPTERS", raising=False)
    monkeypatch.setattr(
        contract,
        "_call_semantic_vote",
        lambda *a, **k: (_ for _ in ()).throw(_MustNotReach("typed vote ran for stale cockpit")),
    )
    monkeypatch.setattr(listener, "_try_invoice_cockpit", lambda *a, **k: calls.append("cockpit") or None)
    monkeypatch.setattr(listener, "cassandra_handle", lambda *a, **k: ["NORMAL-ROUTER"])
    replies = asyncio.run(
        listener._run_cassandra_handle_async(
            "looks good",
            {
                "surface": "cassandra_telegram",
                "source_user_label": "operator",
                "invoice_cockpit_session_path": str(session_path),
            },
        )
    )
    assert calls == ["cockpit"]
    assert replies == ["NORMAL-ROUTER"]


def test_cassandra_cross_surface_guided_session_does_not_intercept_or_vote(tmp_path, monkeypatch):
    listener = _load_cassandra_listener(monkeypatch)
    import cassandra_guided_review as guided

    now = guided.utc_now()
    session = _minimal_guided_session(guided, now)
    session["surface"] = "maestro"
    path = guided._session_path(tmp_path, session["review_session_id"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(session, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    before = path.read_bytes()
    monkeypatch.delenv("OPENCLAW_CONTRACT_VOTE_ADAPTERS", raising=False)
    monkeypatch.setattr(
        contract,
        "_call_semantic_vote",
        lambda *a, **k: (_ for _ in ()).throw(_MustNotReach("cross-surface typed vote ran")),
    )
    monkeypatch.setattr(listener, "_try_invoice_cockpit", lambda *a, **k: None)
    monkeypatch.setattr(listener, "cassandra_handle", lambda *a, **k: ["NORMAL-ROUTER"])
    replies = asyncio.run(
        listener._run_cassandra_handle_async(
            "maybe that other thing",
            {
                "surface": "cassandra_telegram",
                "source_user_label": "operator",
                "guided_review_root": str(tmp_path),
                "invoice_cockpit_session_path": str(tmp_path / "no-cockpit.json"),
            },
        )
    )
    assert replies == ["NORMAL-ROUTER"]
    assert path.read_bytes() == before


def test_cassandra_guided_telegram_alias_is_same_active_surface(tmp_path, monkeypatch):
    listener = _load_cassandra_listener(monkeypatch)
    import cassandra_guided_review as guided

    now = guided.utc_now()
    session = _minimal_guided_session(guided, now)
    session["surface"] = "telegram"
    path = guided._session_path(tmp_path, session["review_session_id"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(session, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    before = path.read_bytes()
    monkeypatch.delenv("OPENCLAW_CONTRACT_VOTE_ADAPTERS", raising=False)
    monkeypatch.setattr(contract, "_call_semantic_vote", lambda *a, **k: (None, "timeout_or_invalid"))
    monkeypatch.setattr(
        listener,
        "_try_invoice_cockpit",
        lambda *a, **k: (_ for _ in ()).throw(_MustNotReach("cockpit ran")),
    )
    monkeypatch.setattr(
        listener,
        "cassandra_handle",
        lambda *a, **k: (_ for _ in ()).throw(_MustNotReach("brain ran")),
    )
    replies = asyncio.run(
        listener._run_cassandra_handle_async(
            "maybe that other thing",
            {
                "surface": "cassandra_telegram",
                "source_user_label": "operator",
                "guided_review_root": str(tmp_path),
                "invoice_cockpit_session_path": str(tmp_path / "no-cockpit.json"),
            },
        )
    )
    assert "left the open guided review step unchanged" in replies[0]
    assert "Receipt: contract:" in replies[0]
    assert path.read_bytes() == before


def test_cassandra_brain_direct_entry_uses_contract_before_packet_or_model(monkeypatch):
    import cassandra_brain

    monkeypatch.setattr(
        cassandra_brain,
        "assemble_business_ops_packet",
        lambda *a, **k: (_ for _ in ()).throw(_MustNotReach("packet assembly ran")),
    )
    replies = cassandra_brain.handle('What do you make of "blorp fizzle invoice quantum"?')
    assert len(replies) == 1
    assert "client" not in replies[0].lower()


def _minimal_guided_session(module, now: str) -> dict:
    return {
        "schema_version": module.SESSION_SCHEMA_VERSION,
        "review_session_id": "data_room_review:test",
        "topic": module.TOPIC_DATA_ROOM,
        "topic_display_name": "Data Room",
        "created_at_utc": now,
        "updated_at_utc": now,
        "operator": "Winship",
        "surface": "telegram",
        "status": "active",
        "question_queue": [{"question_id": "q1", "status": "pending", "prompt": "Client?"}],
        "current_question_id": "q1",
        "answered_questions": [],
        "skipped_questions": [],
        "deferred_questions": [],
        "unresolved_questions": [],
        "answer_records": [],
        "generated_prompt_refs": [],
        "receipt_refs": [],
        "watch_desk_refs": [],
        "authoritative": False,
        "runtime_policy_changed": False,
    }


def test_guided_review_uncertain_vote_preserves_session_file_byte_for_byte(tmp_path, monkeypatch):
    import cassandra_guided_review as guided

    now = "2026-07-10T03:00:00+00:00"
    session = _minimal_guided_session(guided, now)
    path = guided._session_path(tmp_path, session["review_session_id"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(session, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    before = path.read_bytes()
    # Task 157 intent evolution: this is a vote-path test.  Fable's hermetic
    # pytest default correctly disables live semantic votes unless the adapter
    # opts in explicitly, so the fixture must name the seam it is exercising.
    monkeypatch.setenv(contract.SEMANTIC_VOTE_ENV, "cassandra_guided_review")
    monkeypatch.setattr(contract, "_call_semantic_vote", lambda *a, **k: (None, "timeout_or_invalid"))

    result = guided.process_guided_review_message(
        "maybe that other thing",
        review_root=tmp_path,
        read_model_root=tmp_path / "read-models",
        generated_at_utc=now,
    )
    assert result["handled"] is True
    assert "left the open guided review step unchanged" in result["reply_text"]
    assert result["typed_contract_decision"]["model_called"] is True
    assert result["typed_contract_decision"]["semantic_vote_status"] == "timeout_or_invalid"
    assert path.read_bytes() == before


def test_guided_review_semantic_route_without_stager_preserves_and_never_advances(tmp_path, monkeypatch):
    import cassandra_guided_review as guided

    now = "2026-07-10T03:00:00+00:00"
    session = _minimal_guided_session(guided, now)
    path = guided._session_path(tmp_path, session["review_session_id"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(session, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    before = path.read_bytes()
    # Task 157 intent evolution: explicitly opt into the mocked semantic vote;
    # absence of the env now deliberately means hermetic owner passthrough.
    monkeypatch.setenv(contract.SEMANTIC_VOTE_ENV, "cassandra_guided_review")
    monkeypatch.setattr(
        contract,
        "_call_semantic_vote",
        lambda *a, **k: ((contract.ContractLabel.ROUTE_INSTRUCTION, 0.93, False), "accepted"),
    )
    result = guided.process_guided_review_message(
        "please move this to the right specialist",
        review_root=tmp_path,
        read_model_root=tmp_path / "read-models",
        generated_at_utc=now,
    )
    assert result["typed_contract_decision"]["action"] == "preserve_session"
    assert result["typed_contract_decision"]["model_called"] is True
    assert result["typed_contract_decision"]["semantic_vote_status"] == "accepted"
    assert "Receipt: contract:" in result["reply_text"]
    assert path.read_bytes() == before


def test_guided_review_contract_exception_fails_closed_without_persistence(tmp_path, monkeypatch):
    import cassandra_guided_review as guided

    now = "2026-07-10T03:00:00+00:00"
    session = _minimal_guided_session(guided, now)
    path = guided._session_path(tmp_path, session["review_session_id"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(session, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    before = path.read_bytes()
    monkeypatch.setattr(contract, "decide_contract", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    result = guided.process_guided_review_message(
        "maybe that other thing",
        review_root=tmp_path,
        read_model_root=tmp_path / "read-models",
        generated_at_utc=now,
    )
    assert "Receipt: contract:" in result["reply_text"]
    assert path.read_bytes() == before


def test_guardian_nonapproval_gate_narration_uses_typed_renderer():
    import chief_nonapproval_responder as responder

    result = responder.nonapproval_response_for_text(
        "walk me through what happens when Cassandra wants to send an invoice",
        surface="guardian",
    )
    assert result.intent == "guardian_gate_narration"
    assert "up-front Guardian approval" in result.reply
    assert result.receipt["label"] == "guardian_gate_narration"


class _FakeMessage:
    def __init__(self, text: str):
        self.text = text
        self.replies = []

    async def reply_text(self, text: str, **_kwargs):
        self.replies.append(text)


def _load_guardian_listener(monkeypatch):
    monkeypatch.setenv("GUARDIAN_BOT_TOKEN", "test-token")
    monkeypatch.setenv("TELEGRAM_AUTHORIZED_USER_ID", "123")
    _install_telegram_stubs(monkeypatch, guardian=True)
    sys.modules.pop("chief_guardian_listener", None)
    module = importlib.import_module("chief_guardian_listener")
    module = importlib.reload(module)
    monkeypatch.setattr(module, "record_telegram_listener_update_safe", lambda **kwargs: None)
    monkeypatch.setattr(module, "claim_listener_update", lambda *args, **kwargs: True)
    return module


def test_guardian_pending_safe_contract_precedes_eli5_model(monkeypatch):
    listener = _load_guardian_listener(monkeypatch)
    import chief_approval_brain
    import hitl_notification_service

    monkeypatch.setattr(hitl_notification_service, "handle_typed_reply", lambda *a, **k: {"handled": False})
    monkeypatch.setattr(chief_approval_brain, "has_pending_approval", lambda: True)
    monkeypatch.setattr(
        chief_approval_brain,
        "_load_pending",
        lambda: {"id": "A3F2", "options": 2, "action": "send invoice", "requester": "cassandra"},
    )
    monkeypatch.setattr(chief_approval_brain, "parse_reply_code", lambda *a, **k: ("", "Use A3F2 1 or A3F2 2"))
    monkeypatch.setitem(
        sys.modules,
        "guardian_eli5",
        types.SimpleNamespace(
            answer_question=lambda *a, **k: (_ for _ in ()).throw(_MustNotReach("ELI5 model ran"))
        ),
    )

    update = types.SimpleNamespace(
        update_id=1,
        effective_user=types.SimpleNamespace(id=123),
        effective_chat=types.SimpleNamespace(id=42),
        message=_FakeMessage("walk me through what happens when Cassandra wants to send an invoice"),
    )
    asyncio.run(listener.handle_message(update, types.SimpleNamespace()))
    assert len(update.message.replies) == 1
    assert "dispatch-time SEND_HOLD" in update.message.replies[0]


def test_guardian_pending_contract_exception_preserves_before_eli5(monkeypatch):
    listener = _load_guardian_listener(monkeypatch)
    import chief_approval_brain
    import hitl_notification_service

    monkeypatch.setattr(hitl_notification_service, "handle_typed_reply", lambda *a, **k: {"handled": False})
    monkeypatch.setattr(chief_approval_brain, "has_pending_approval", lambda: True)
    monkeypatch.setattr(
        chief_approval_brain,
        "_load_pending",
        lambda: {"id": "A3F2", "options": 2, "action": "send invoice", "requester": "cassandra"},
    )
    monkeypatch.setattr(chief_approval_brain, "parse_reply_code", lambda *a, **k: ("", "Use A3F2 1 or A3F2 2"))
    monkeypatch.setattr(contract, "decide_contract", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    monkeypatch.setitem(
        sys.modules,
        "guardian_eli5",
        types.SimpleNamespace(answer_question=lambda *a, **k: (_ for _ in ()).throw(_MustNotReach("ELI5 ran"))),
    )
    update = types.SimpleNamespace(
        update_id=1,
        effective_user=types.SimpleNamespace(id=123),
        effective_chat=types.SimpleNamespace(id=42),
        message=_FakeMessage("maybe that other thing"),
    )
    asyncio.run(listener.handle_message(update, types.SimpleNamespace()))
    assert "left the open guardian pending approval step unchanged" in update.message.replies[0]
    assert "Receipt: contract:" in update.message.replies[0]


def test_guardian_pending_vote_timeout_preserves_with_visible_receipt(monkeypatch):
    listener = _load_guardian_listener(monkeypatch)
    import chief_approval_brain
    import hitl_notification_service

    monkeypatch.delenv("OPENCLAW_CONTRACT_VOTE_ADAPTERS", raising=False)
    monkeypatch.setattr(contract, "_call_semantic_vote", lambda *a, **k: (None, "timeout_or_invalid"))
    monkeypatch.setattr(hitl_notification_service, "handle_typed_reply", lambda *a, **k: {"handled": False})
    monkeypatch.setattr(chief_approval_brain, "has_pending_approval", lambda: True)
    monkeypatch.setattr(
        chief_approval_brain,
        "_load_pending",
        lambda: {"id": "A3F2", "options": 2, "action": "send invoice", "requester": "cassandra"},
    )
    monkeypatch.setattr(chief_approval_brain, "parse_reply_code", lambda *a, **k: ("", "Use A3F2 1 or A3F2 2"))
    monkeypatch.setitem(
        sys.modules,
        "guardian_eli5",
        types.SimpleNamespace(answer_question=lambda *a, **k: (_ for _ in ()).throw(_MustNotReach("ELI5 ran"))),
    )
    update = types.SimpleNamespace(
        update_id=1,
        effective_user=types.SimpleNamespace(id=123),
        effective_chat=types.SimpleNamespace(id=42),
        message=_FakeMessage("maybe that other thing"),
    )
    asyncio.run(listener.handle_message(update, types.SimpleNamespace()))
    assert "left the open guardian pending approval step unchanged" in update.message.replies[0]
    assert "Receipt: contract:" in update.message.replies[0]


def test_guardian_pending_semantic_route_without_stager_never_reaches_eli5(monkeypatch):
    listener = _load_guardian_listener(monkeypatch)
    import chief_approval_brain
    import hitl_notification_service

    monkeypatch.delenv("OPENCLAW_CONTRACT_VOTE_ADAPTERS", raising=False)
    monkeypatch.setattr(
        contract,
        "_call_semantic_vote",
        lambda *a, **k: ((contract.ContractLabel.ROUTE_INSTRUCTION, 0.94, False), "accepted"),
    )
    monkeypatch.setattr(hitl_notification_service, "handle_typed_reply", lambda *a, **k: {"handled": False})
    monkeypatch.setattr(chief_approval_brain, "has_pending_approval", lambda: True)
    monkeypatch.setattr(
        chief_approval_brain,
        "_load_pending",
        lambda: {"id": "A3F2", "options": 2, "action": "send invoice", "requester": "cassandra"},
    )
    monkeypatch.setattr(chief_approval_brain, "parse_reply_code", lambda *a, **k: ("", "Use A3F2 1 or A3F2 2"))
    monkeypatch.setitem(
        sys.modules,
        "guardian_eli5",
        types.SimpleNamespace(answer_question=lambda *a, **k: (_ for _ in ()).throw(_MustNotReach("ELI5 ran"))),
    )
    update = types.SimpleNamespace(
        update_id=1,
        effective_user=types.SimpleNamespace(id=123),
        effective_chat=types.SimpleNamespace(id=42),
        message=_FakeMessage("please move this to the right specialist"),
    )
    asyncio.run(listener.handle_message(update, types.SimpleNamespace()))
    assert "left the open guardian pending approval step unchanged" in update.message.replies[0]
    assert "Receipt: contract:" in update.message.replies[0]


def _load_niles_listener(monkeypatch):
    monkeypatch.setenv("PRODUCER_BOT_TOKEN", "test-token")
    monkeypatch.setenv("PRODUCER_AUTHORIZED_USER_ID", "123")
    # Listener adapters prefer the fleet-wide canonical authorization variable
    # when a prior adapter test left it set; pin both names to the same user so
    # test order cannot make Niles silently reject the fixture update.
    monkeypatch.setenv("TELEGRAM_AUTHORIZED_USER_ID", "123")
    _install_telegram_stubs(monkeypatch)
    sys.modules.pop("producer_listener", None)
    module = importlib.import_module("producer_listener")
    module = importlib.reload(module)
    monkeypatch.setattr(module, "record_telegram_listener_update_safe", lambda **kwargs: None)
    monkeypatch.setattr(module, "claim_listener_update", lambda *args, **kwargs: True)
    monkeypatch.setattr(module, "_fire_agent_voice", lambda *a, **k: None)
    return module


def test_niles_contract_precedes_memory_and_subprocess(monkeypatch):
    listener = _load_niles_listener(monkeypatch)
    monkeypatch.setattr(listener, "_queue_for_memory", lambda *_: (_ for _ in ()).throw(_MustNotReach("memory queued")))

    async def forbidden(*_args):
        raise _MustNotReach("producer subprocess ran")

    monkeypatch.setattr(listener, "_run_producer_intake", forbidden)
    update = types.SimpleNamespace(
        update_id=2,
        effective_user=types.SimpleNamespace(id=123),
        effective_chat=types.SimpleNamespace(id=42),
        message=_FakeMessage('What do you make of "blorp fizzle invoice quantum"?'),
    )
    asyncio.run(listener.handle_message(update, types.SimpleNamespace(bot=types.SimpleNamespace())))
    assert len(update.message.replies) == 1
    assert "client" not in update.message.replies[0].lower()


def test_niles_subprocess_mirror_handles_humanized_identity_without_legacy_response():
    from scripts import producer_intake

    reply = producer_intake._typed_contract_reply("in plain English, what your role is")
    assert "Niles" in reply
    assert "groove, melody, or arrangement" not in reply


def test_niles_subprocess_refusal_survives_typed_contract_failure(monkeypatch, capsys):
    from scripts import producer_intake

    monkeypatch.setattr(producer_intake, "_typed_contract_reply", lambda *_: None)
    monkeypatch.setattr(
        producer_intake,
        "build_producer_input",
        lambda *_: (_ for _ in ()).throw(_MustNotReach("legacy path ran")),
    )
    monkeypatch.setattr(sys, "argv", ["producer_intake.py", "--text", "wipe the X32 and reset all scenes", "--human-only"])
    producer_intake.main()
    output = capsys.readouterr().out
    assert "Guardian" in output
    assert "Nothing" in output or "nothing" in output


def test_hermes_status_is_deterministic_before_worker(monkeypatch):
    import openclaw_hermes_gateway_policy as policy

    result = policy.truthful_reply_for_text("status?")
    assert result is not None
    assert "Hermes" in result
    assert "model" not in result.lower() or "no model" in result.lower()


def test_hermes_status_uses_fresh_presence_only(tmp_path):
    from agent_contract_renderers import render_hermes_status

    (tmp_path / "agent_presence.json").write_text(
        json.dumps(
            {
                "generated_at": "2026-07-09T22:00:00+00:00",
                "agents": [{"agent_id": "hermes", "actual_state": "online", "observed_at": "2026-07-09T21:59:00+00:00"}],
            }
        ),
        encoding="utf-8",
    )
    fresh = render_hermes_status(read_model_root=tmp_path)
    assert "Hermes runtime: online" in fresh


def test_hermes_status_excludes_stale_or_undated_presence(tmp_path):
    from agent_contract_renderers import render_hermes_status

    for index, payload in enumerate(
        (
            {"generated_at": "2025-01-01T00:00:00+00:00", "agents": [{"agent_id": "hermes", "actual_state": "online"}]},
            {"agents": [{"agent_id": "hermes", "actual_state": "online"}]},
        )
    ):
        root = tmp_path / str(index)
        root.mkdir()
        (root / "agent_presence.json").write_text(json.dumps(payload), encoding="utf-8")
        answer = render_hermes_status(read_model_root=root)
        assert "stale or undated" in answer
        assert "runtime: online" not in answer
