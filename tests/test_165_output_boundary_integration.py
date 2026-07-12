from __future__ import annotations

import asyncio
import importlib
import json
import sys
import types
from pathlib import Path

import pytest

from final_output_boundary import OutputBoundaryContext


CT2_REQUEST = "any sign of the hilton payment landing yet?"
CT2_LEAK = "CASS-DEEP-07 compact recovery check: answer one sentence only."
HT2_REQUEST = "hey hermes, hows the system looking from your seat?"
HT2_LEAK = """Hermes could not produce a fresh answer before the local model stream limit.
The upstream local model returned no usable chunks, so stale partial output was discarded.
No requested send, agent dispatch, route receipt, or money action occurred.
Ask Fable or the operator to check Hermes gateway health and Ollama contention before retrying."""


def test_typed_contract_carries_pre_filter_context_and_machine_receipt() -> None:
    import typed_contract_decision as typed

    decision = typed.decide_contract(
        "status?",
        context=typed.ContractContext(agent="chief", surface="chief_router"),
        status_renderer=lambda: f"Chief is online. {CT2_LEAK}",
        semantic_vote_enabled=False,
    )

    assert "Chief is online." in str(decision.reply)
    assert "CASS-DEEP" not in str(decision.reply)
    boundary_receipt = decision.receipt.output_boundary_receipt
    assert boundary_receipt["replaced_fragment_count"] == 1
    assert boundary_receipt["technical_intent"] is False
    assert CT2_LEAK not in json.dumps(boundary_receipt, sort_keys=True)


def test_processor_first_touch_publishes_the_bounded_typed_reply_everywhere(
    monkeypatch,
) -> None:
    import first_touch_decision as first_touch
    import openclaw_request_processor as processor

    receipt = {
        "schema_version": first_touch.SCHEMA_VERSION,
        "receipt_type": first_touch.RECEIPT_TYPE,
        "decision_id": "first_touch:test-165-boundary",
        "attempted": True,
        "handled": True,
        "label": "refusal",
        "action": "refuse",
        "agent": "chief",
        "surface": "mission_control",
        "gate": "deletion gate",
        "guard_receipt": {},
        "refusal_receipt_append_performed": False,
        "file_mutation_performed": False,
    }
    decision = first_touch.FirstTouchDecision(
        handled=True,
        label="refusal",
        action="refuse",
        reply=CT2_LEAK,
        agent="chief",
        surface="mission_control",
        receipt=receipt,
    )
    outcome = first_touch.FirstTouchOutcome(
        attempted=True,
        handled=True,
        decision=decision,
        receipt=receipt,
        status="handled",
    )
    monkeypatch.setattr(
        processor.first_touch_decision,
        "attempt_first_touch",
        lambda *_args, **_kwargs: outcome,
    )
    classification = processor.classify_request_filename(
        "mission_control_operator_instruction_request_task_165.json"
    )

    _outcome, response = processor._process_first_touch_decision(
        Path("mission_control_operator_instruction_request_task_165.json"),
        {
            "request_id": "request:task-165-first-touch",
            "operator_message": CT2_REQUEST,
            "active_surface_ref": "mission_control",
        },
        classification=classification,
        route_decision={},
    )

    assert response is not None
    assert "CASS-DEEP" not in response.operator_message
    assert response.visible_cards[0]["summary"] == response.operator_message
    typed_receipt = response.detail_disclosure["typed_contract_decision"]
    assert typed_receipt["output_boundary_receipt"]["replaced_fragment_count"] == 1
    assert response.typed_contract_trace["typed_contract_decision"] == typed_receipt


def test_typed_contract_carries_conditional_runtime_context_before_filtering() -> None:
    import typed_contract_decision as typed

    diagnostic = "The upstream local model returned no usable chunks."
    nontechnical = typed.decide_contract(
        "status?",
        context=typed.ContractContext(agent="chief", surface="chief_router"),
        status_renderer=lambda: diagnostic,
        semantic_vote_enabled=False,
    )
    technical_answer = "Ollama contention can trigger the local model stream limit."
    technical = typed.decide_contract(
        "Explain your gateway status diagnostics and local model stream limit.",
        context=typed.ContractContext(agent="chief", surface="chief_router"),
        status_renderer=lambda: technical_answer,
        semantic_vote_enabled=False,
    )

    assert "no usable chunks" not in str(nontechnical.reply).lower()
    assert nontechnical.receipt.output_boundary_receipt["technical_intent"] is False
    assert technical.reply == technical_answer
    assert technical.receipt.output_boundary_receipt["technical_intent"] is True


def test_origin_bound_output_filters_at_visible_text_boundary_and_exposes_receipt() -> None:
    from origin_bound_output import OPERATOR_AUDIENCE, OriginBoundOutput, OutputOrigin

    output = OriginBoundOutput.guarded_text(
        origin=OutputOrigin(
            surface="cassandra_telegram",
            bot_identity="cassandra",
            chat_id="42",
            source_message_id="100",
            audience=OPERATOR_AUDIENCE,
        ),
        delivery_id="delivery-1",
        receipt_pointer="machine-pointer",
        operator_text=f"Capital Hilton payment remains unconfirmed. {CT2_LEAK}",
        source_request=CT2_REQUEST,
    )

    assert "Capital Hilton payment remains unconfirmed." in output.visible_text()
    assert "CASS-DEEP" not in output.visible_text()
    receipt = output.output_boundary_receipt()
    assert receipt["replaced_fragment_count"] == 1
    assert CT2_LEAK not in json.dumps(receipt, sort_keys=True)


def test_origin_bound_output_carries_conditional_runtime_context() -> None:
    from origin_bound_output import OPERATOR_AUDIENCE, OriginBoundOutput, OutputOrigin

    origin = OutputOrigin(
        surface="cassandra_telegram",
        bot_identity="cassandra",
        chat_id="42",
        source_message_id="101",
        audience=OPERATOR_AUDIENCE,
    )
    nontechnical = OriginBoundOutput.guarded_text(
        origin=origin,
        delivery_id="delivery-nontechnical",
        receipt_pointer="machine-pointer-1",
        operator_text=HT2_LEAK,
        source_request=HT2_REQUEST,
    )
    technical_answer = "Ollama contention can cause the local model stream limit to expire."
    technical = OriginBoundOutput.guarded_text(
        origin=origin,
        delivery_id="delivery-technical",
        receipt_pointer="machine-pointer-2",
        operator_text=technical_answer,
        source_request="Explain how Ollama contention affects the local model stream limit.",
    )

    assert "no usable chunks" not in nontechnical.visible_text().lower()
    assert nontechnical.output_boundary_receipt()["technical_intent"] is False
    assert technical.visible_text() == technical_answer
    assert technical.output_boundary_receipt()["technical_intent"] is True


def test_cassandra_and_chief_outer_wrappers_keep_safe_facts_on_control_leak(
    monkeypatch,
) -> None:
    import cassandra_brain
    import chief_router

    monkeypatch.setattr(
        cassandra_brain,
        "_handle_unguarded",
        lambda _text, _session=None: [f"Payment remains unconfirmed. {CT2_LEAK}"],
    )
    cassandra_reply = cassandra_brain.handle(CT2_REQUEST)[0]
    chief_result = chief_router._guard_route_result(
        {"intent": "generic", "reply": f"Payment remains unconfirmed. {CT2_LEAK}"},
        source_request=CT2_REQUEST,
    )

    assert "Payment remains unconfirmed." in cassandra_reply
    assert "CASS-DEEP" not in cassandra_reply
    assert "Payment remains unconfirmed." in chief_result["reply"]
    assert "CASS-DEEP" not in chief_result["reply"]


def test_hermes_gateway_humanizes_exact_ht2_and_retains_no_action_line() -> None:
    import openclaw_hermes_gateway_policy as policy

    visible = policy.sanitize_gateway_response(
        HT2_LEAK,
        source_request=HT2_REQUEST,
    )

    assert "model stream limit" not in visible.lower()
    assert "no usable chunks" not in visible.lower()
    assert "gateway health" not in visible.lower()
    assert "No requested send, agent dispatch, route receipt, or money action occurred." in visible
    receipt = policy.current_gateway_output_boundary_receipt()
    assert receipt is not None
    assert receipt["replaced_fragment_count"] == 3


def _response(processor, message: str):
    return processor.OpenClawResponseForMac(
        source_request_id="request:test-165",
        source_request_filename="request.json",
        workflow_ref="chat",
        request_type="CHAT",
        internal_status="RESPONSE_READY",
        operator_headline="Answer",
        operator_message=message,
        what_happened=(),
        why_it_happened="",
        how_to_fix="",
        visible_cards=(),
        cards_available=False,
        card_mirror_refs=(),
        file_readback_refs=(),
        worker_route_refs=(),
        context_package_refs=(),
        blocked_reason=None,
        detail_disclosure={},
        readback_files=(),
        next_safe_move="",
    )


def test_mac_final_pipeline_filters_after_decoration_and_persists_machine_receipt(
    tmp_path: Path,
    monkeypatch,
) -> None:
    import openclaw_request_processor as processor
    import reply_pipeline

    request_path = tmp_path / "request.json"
    request_path.write_text(json.dumps({"message": HT2_REQUEST}), encoding="utf-8")
    monkeypatch.setattr(
        reply_pipeline,
        "apply_reply_pipeline",
        lambda message, *_args, **_kwargs: message,
    )

    result = processor._enrich_operator_surface(
        _response(processor, HT2_LEAK),
        request_path,
        tmp_path,
    )

    assert "no usable chunks" not in result.operator_message.lower()
    assert "No requested send, agent dispatch, route receipt, or money action occurred." in result.operator_message
    receipt = result.detail_disclosure["output_boundary_receipt"]
    assert receipt["replaced_fragment_count"] == 3
    assert HT2_LEAK not in json.dumps(receipt, sort_keys=True)


def test_unprompted_delivery_context_is_explicitly_nontechnical() -> None:
    context = OutputBoundaryContext.from_source_request("", technical_intent=False)

    assert context.technical_intent is False
    assert context.technical_intent_reason == "explicit_adapter_override"


class _FakeFilter:
    def __and__(self, _other):
        return self

    def __invert__(self):
        return self


def _install_listener_stubs(monkeypatch) -> None:
    monkeypatch.setenv("TELEGRAM_AUTHORIZED_USER_ID", "123")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "123")
    monkeypatch.setenv("CASSANDRA_BOT_TOKEN", "test-cassandra-token")
    monkeypatch.setenv("CHIEF_BOT_TOKEN", "test-chief-token")
    monkeypatch.setenv("GUARDIAN_BOT_TOKEN", "test-guardian-token")
    monkeypatch.setenv("NILES_BOT_TOKEN", "test-niles-token")
    monkeypatch.setenv("PRODUCER_BOT_TOKEN", "test-niles-token")
    monkeypatch.setenv("PRODUCER_AUTHORIZED_USER_ID", "123")

    telegram = types.ModuleType("telegram")
    telegram.Update = object
    telegram.InlineKeyboardMarkup = object
    error = types.ModuleType("telegram.error")
    error.BadRequest = Exception
    error.Forbidden = Exception
    ext = types.ModuleType("telegram.ext")
    ext.ApplicationBuilder = type("ApplicationBuilder", (), {})
    ext.CallbackQueryHandler = lambda *args, **kwargs: None
    ext.MessageHandler = lambda *args, **kwargs: None
    ext.filters = types.SimpleNamespace(
        TEXT=_FakeFilter(),
        COMMAND=_FakeFilter(),
        VOICE=_FakeFilter(),
    )
    ext.ContextTypes = types.SimpleNamespace(DEFAULT_TYPE=object)
    monkeypatch.setitem(sys.modules, "telegram", telegram)
    monkeypatch.setitem(sys.modules, "telegram.error", error)
    monkeypatch.setitem(sys.modules, "telegram.ext", ext)


@pytest.mark.parametrize(
    ("module_name", "adapter_name"),
    (
        ("cassandra_listener", "_final_operator_reply"),
        ("chief_listener", "_final_operator_text"),
        ("chief_guardian_listener", "guardian_resilient_reply"),
        ("producer_listener", "_final_operator_reply"),
        ("maestro_listener", "_final_operator_reply"),
    ),
)
def test_each_interactive_listener_final_adapter_filters_ct2_and_carries_context(
    module_name: str,
    adapter_name: str,
    monkeypatch,
) -> None:
    _install_listener_stubs(monkeypatch)
    sys.modules.pop(module_name, None)
    module = importlib.import_module(module_name)
    adapter = getattr(module, adapter_name)

    visible = adapter(CT2_LEAK, source_request=CT2_REQUEST)

    assert "CASS-DEEP" not in visible
    receipt = module.current_output_boundary_receipt()
    assert receipt is not None
    assert receipt["replaced_fragment_count"] == 1
    assert receipt["technical_intent"] is False
    assert receipt["raw_control_text_included"] is False
    assert CT2_LEAK not in json.dumps(receipt, sort_keys=True)

    nontechnical = adapter(HT2_LEAK, source_request=HT2_REQUEST)
    assert "no usable chunks" not in nontechnical.lower()
    assert "gateway health" not in nontechnical.lower()
    nontechnical_receipt = module.current_output_boundary_receipt()
    assert nontechnical_receipt is not None
    assert nontechnical_receipt["technical_intent"] is False

    technical_answer = (
        "Ollama contention can cause the local model stream limit to expire."
    )
    technical = adapter(
        technical_answer,
        source_request=(
            "Explain how Ollama contention affects the local model stream limit."
        ),
    )
    assert technical == technical_answer
    technical_receipt = module.current_output_boundary_receipt()
    assert technical_receipt is not None
    assert technical_receipt["technical_intent"] is True

    quoted = adapter(
        "The upstream local model returned no usable chunks.",
        source_request=(
            'Repeat exactly: "The upstream local model returned no usable chunks."'
        ),
    )
    assert "no usable chunks" not in quoted.lower()


def test_chief_text_and_voice_share_the_same_filtered_final_output(monkeypatch) -> None:
    _install_listener_stubs(monkeypatch)
    sys.modules.pop("chief_listener", None)
    listener = importlib.import_module("chief_listener")
    text_replies: list[str] = []
    voice_replies: list[str] = []

    class Message:
        text = CT2_REQUEST
        chat_id = 123

        async def reply_text(self, text: str) -> None:
            text_replies.append(text)

    update = types.SimpleNamespace(message=Message())
    monkeypatch.setattr(
        listener,
        "_fire_agent_voice",
        lambda _agent, text, _update: voice_replies.append(text),
    )

    asyncio.run(
        listener._send_reply(
            update,
            f"Capital Hilton payment remains unconfirmed. {CT2_LEAK}",
            source_request=CT2_REQUEST,
        )
    )

    assert text_replies == voice_replies
    assert "Capital Hilton payment remains unconfirmed." in text_replies[0]
    assert "CASS-DEEP" not in text_replies[0]


@pytest.mark.parametrize(
    "module_name",
    (
        "cassandra_listener",
        "chief_listener",
        "chief_guardian_listener",
        "maestro_listener",
    ),
)
def test_first_touch_handled_reply_uses_listener_final_boundary(
    module_name: str,
    monkeypatch,
) -> None:
    _install_listener_stubs(monkeypatch)
    sys.modules.pop(module_name, None)
    listener = importlib.import_module(module_name)
    replies: list[str] = []
    voice_replies: list[str] = []

    class Message:
        text = CT2_REQUEST
        chat_id = 123

        async def reply_text(self, text: str) -> None:
            replies.append(text)

    update = types.SimpleNamespace(
        update_id=165,
        effective_user=types.SimpleNamespace(
            id=123,
            full_name="Operator",
        ),
        effective_chat=types.SimpleNamespace(id=123),
        message=Message(),
    )
    first_touch = types.SimpleNamespace(
        attempted=True,
        handled=True,
        decision=types.SimpleNamespace(
            reply=f"Capital Hilton remains unconfirmed. {CT2_LEAK}",
        ),
        receipt={"attempted": True, "handled": True},
    )
    monkeypatch.setattr(listener, "claim_listener_update", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(
        listener.first_touch_decision,
        "attempt_first_touch",
        lambda *_args, **_kwargs: first_touch,
    )
    if hasattr(listener, "_fire_agent_voice"):
        monkeypatch.setattr(
            listener,
            "_fire_agent_voice",
            lambda _agent, text, _update: voice_replies.append(text),
        )

    async def run_first_touch() -> dict | None:
        await listener.handle_message(update, types.SimpleNamespace())
        return listener.current_output_boundary_receipt()

    receipt = asyncio.run(run_first_touch())

    assert len(replies) == 1
    assert "Capital Hilton remains unconfirmed." in replies[0]
    assert "CASS-DEEP" not in replies[0]
    assert receipt is not None
    assert receipt["replaced_fragment_count"] == 1
    assert receipt["technical_intent"] is False
    if module_name == "chief_listener":
        # Task 162's first-touch short circuit forbids optional TTS/voice work.
        assert voice_replies == []


def test_interactive_adapter_receipts_are_task_local_and_source_correlated(
    monkeypatch,
) -> None:
    _install_listener_stubs(monkeypatch)
    sys.modules.pop("maestro_listener", None)
    listener = importlib.import_module("maestro_listener")

    async def render_and_yield(source_request: str, reply: str) -> tuple[str, dict]:
        visible = listener._final_operator_reply(
            reply,
            source_request=source_request,
        )
        await asyncio.sleep(0)
        receipt = listener.current_output_boundary_receipt()
        assert receipt is not None
        return visible, receipt

    async def run_both():
        return await asyncio.gather(
            render_and_yield(HT2_REQUEST, "The upstream local model returned no usable chunks."),
            render_and_yield(
                "Explain how the local model stream limit works.",
                "The local model stream limit bounds a technical request.",
            ),
        )

    ordinary, technical = asyncio.run(run_both())

    assert "no usable chunks" not in ordinary[0].lower()
    assert ordinary[1]["technical_intent"] is False
    assert technical[1]["technical_intent"] is True
    assert ordinary[1]["source_request_sha256"] != technical[1]["source_request_sha256"]


def test_unprompted_telegram_sender_filters_before_send_and_receipts_the_boundary(
    tmp_path: Path,
) -> None:
    import cassandra_telegram_delivery as delivery

    toggle = tmp_path / "enabled.flag"
    toggle.write_text("enabled\n", encoding="utf-8")
    sent: list[str] = []

    receipt = delivery.deliver_to_authorized_telegram(
        message_text=f"Payment remains unconfirmed. {CT2_LEAK}",
        delivery_kind="task_165_unprompted_test",
        env={delivery.AUTHORIZED_USER_ID_ENV_VAR: "123"},
        toggle_path=toggle,
        dry_run_log_path=tmp_path / "delivery.jsonl",
        telegram_sender=lambda text, *, chat_id: sent.append(text),
    )

    assert receipt.sent is True
    assert sent == [receipt.message_text]
    assert "Payment remains unconfirmed." in receipt.message_text
    assert "CASS-DEEP" not in receipt.message_text
    assert receipt.output_boundary_receipt["replaced_fragment_count"] == 1
    assert CT2_LEAK not in json.dumps(receipt.to_dict(), sort_keys=True)


def test_scheduled_briefing_text_and_voice_are_filtered_at_the_unprompted_boundary(
    monkeypatch,
) -> None:
    import cassandra_briefing_scheduler as scheduler

    sent_text: list[str] = []
    sent_voice: list[str] = []
    raw = f"Capital Hilton payment remains unconfirmed. {CT2_LEAK}"
    entry = {"slot": "afternoon", "date": "2026-07-11", "text": raw}
    monkeypatch.setattr(scheduler, "briefing_delivery_blocked", lambda: False)
    monkeypatch.setattr(scheduler, "split_briefing_messages", lambda _entry: [raw])
    monkeypatch.setattr(scheduler, "briefing_voice_text", lambda _entry: raw)
    monkeypatch.setattr(scheduler, "send_operator_brief", sent_text.append)
    monkeypatch.setattr(
        scheduler,
        "speak_and_send_operator_brief_voice",
        sent_voice.append,
    )
    monkeypatch.setattr(scheduler, "mark_delivered", lambda *_args: None)

    scheduler._deliver(entry)

    assert sent_text == sent_voice
    assert "Capital Hilton payment remains unconfirmed." in sent_text[0]
    assert "CASS-DEEP" not in sent_text[0]


def test_guardian_approval_board_send_and_edit_filter_dynamic_action_text(
    monkeypatch,
) -> None:
    import guardian_telegram_ops as telegram_ops

    payloads: list[dict] = []

    class Response:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {"result": {"message_id": 42}}

    fake_requests = types.SimpleNamespace(
        post=lambda _url, *, json, timeout: payloads.append(json) or Response()
    )
    monkeypatch.setattr(telegram_ops, "requests", fake_requests)
    monkeypatch.setattr(telegram_ops, "_api", lambda method: f"https://test/{method}")
    monkeypatch.setattr(telegram_ops, "_chat", lambda: "123")
    ops = telegram_ops.GuardianTelegramOps()

    message_id = ops.send(f"Approval remains pending. {CT2_LEAK}")
    ops.edit(message_id, f"Approval remains pending. {CT2_LEAK}")

    assert message_id == 42
    assert len(payloads) == 2
    assert all("Approval remains pending." in payload["text"] for payload in payloads)
    assert all("CASS-DEEP" not in payload["text"] for payload in payloads)
    receipt = ops.output_boundary_receipt_for(42)
    assert receipt is not None
    assert receipt["replaced_fragment_count"] == 1


def test_guardian_failed_edit_does_not_claim_an_output_boundary_receipt(
    monkeypatch,
) -> None:
    import guardian_telegram_ops as telegram_ops

    class FailedResponse:
        def raise_for_status(self) -> None:
            raise RuntimeError("telegram rejected edit")

    fake_requests = types.SimpleNamespace(
        post=lambda _url, *, json, timeout: FailedResponse()
    )
    monkeypatch.setattr(telegram_ops, "requests", fake_requests)
    monkeypatch.setattr(telegram_ops, "_api", lambda method: f"https://test/{method}")
    monkeypatch.setattr(telegram_ops, "_chat", lambda: "123")
    ops = telegram_ops.GuardianTelegramOps()

    ops.edit(42, f"Approval remains pending. {CT2_LEAK}")

    assert ops.output_boundary_receipt_for(42) is None


def test_cassandra_voice_rejection_never_echoes_dynamic_relay_reason(
    monkeypatch,
) -> None:
    _install_listener_stubs(monkeypatch)
    sys.modules.pop("cassandra_listener", None)
    listener = importlib.import_module("cassandra_listener")
    replies: list[str] = []

    class VoiceFile:
        async def download_to_drive(self, _path: str) -> None:
            return None

    class Voice:
        async def get_file(self) -> VoiceFile:
            return VoiceFile()

    class Message:
        voice = Voice()

        async def reply_text(self, text: str) -> None:
            replies.append(text)

    update = types.SimpleNamespace(
        effective_user=types.SimpleNamespace(id=123),
        effective_chat=types.SimpleNamespace(id=123),
        message=Message(),
    )
    monkeypatch.setattr(listener, "_FFMPEG_AVAILABLE", True)
    monkeypatch.setattr(listener, "claim_listener_update", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(listener, "transcribe_audio", lambda _path: (CT2_REQUEST, 0.9))
    monkeypatch.setattr(
        listener,
        "relay_transcript",
        lambda *_args, **_kwargs: {
            "status": "rejected",
            "reply": [],
            "reason": f"cassandra_handle_error: {CT2_LEAK}",
        },
    )

    async def run_voice_rejection() -> dict | None:
        await listener.handle_voice(update, types.SimpleNamespace())
        return listener.current_output_boundary_receipt()

    receipt = asyncio.run(run_voice_rejection())

    assert replies == [
        "Could not safely process that voice input. Please resend or type it."
    ]
    assert "CASS-DEEP" not in replies[0]
    assert receipt is not None
    assert receipt["source_request_sha256"].startswith("sha256:")


def test_cassandra_voice_first_touch_refusal_uses_final_boundary(
    monkeypatch,
) -> None:
    _install_listener_stubs(monkeypatch)
    sys.modules.pop("cassandra_listener", None)
    listener = importlib.import_module("cassandra_listener")
    replies: list[str] = []

    class VoiceFile:
        async def download_to_drive(self, _path: str) -> None:
            return None

    class Voice:
        async def get_file(self) -> VoiceFile:
            return VoiceFile()

    class Message:
        voice = Voice()

        async def reply_text(self, text: str) -> None:
            replies.append(text)

    update = types.SimpleNamespace(
        effective_user=types.SimpleNamespace(id=123),
        effective_chat=types.SimpleNamespace(id=123),
        message=Message(),
    )
    monkeypatch.setattr(listener, "_FFMPEG_AVAILABLE", True)
    monkeypatch.setattr(listener, "claim_listener_update", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(listener, "transcribe_audio", lambda _path: (CT2_REQUEST, 0.9))
    monkeypatch.setattr(
        listener,
        "relay_transcript",
        lambda *_args, **_kwargs: {
            "status": "refused",
            "reply": [f"Capital Hilton remains unconfirmed. {CT2_LEAK}"],
            "reason": "first_touch_refusal",
            "confidence": 0.9,
        },
    )

    async def run_voice_refusal() -> dict | None:
        await listener.handle_voice(update, types.SimpleNamespace())
        return listener.current_output_boundary_receipt()

    receipt = asyncio.run(run_voice_refusal())

    assert len(replies) == 1
    assert "Capital Hilton remains unconfirmed." in replies[0]
    assert "CASS-DEEP" not in replies[0]
    assert receipt is not None
    assert receipt["replaced_fragment_count"] == 1
    assert receipt["technical_intent"] is False
