from __future__ import annotations

from pathlib import Path

import chief_llm
import cassandra_briefing_scheduler as scheduler
import chief_album_brain
import interpreter_lm
import local_model_governance as governance
import maestro_cassandra_responder as maestro
import openclaw_request_processor as processor
import protected_generate
from polish_loop.gpu_arbiter import GPUArbiter


def test_request_binding_is_once_only_and_fixed_to_operator_8b() -> None:
    first = governance.bind_interactive_model(
        {"source_message_id": "1553"}, request_key="request-1553"
    )
    second = governance.bind_interactive_model(first, request_key="different")

    assert first[governance.BINDING_SESSION_KEY] == second[governance.BINDING_SESSION_KEY]
    binding = second[governance.BINDING_SESSION_KEY]
    assert binding["model"] == "qwen3:8b-q4_K_M"
    assert binding["keep_alive"] == "10m"
    assert binding["num_ctx"] == 2048
    assert binding["num_gpu"] == 999
    assert binding["num_batch"] == 128


def test_incomplete_or_mismatched_runner_binding_is_rebuilt() -> None:
    stale = {
        governance.BINDING_SESSION_KEY: {
            "schema_version": "local_model_binding_v1",
            "binding_id": "legacy-runner-shape",
            "model": governance.INTERACTIVE_MODEL,
            "keep_alive": governance.INTERACTIVE_KEEP_ALIVE,
            "num_ctx": 2048,
        }
    }

    binding = governance.binding_from_session(stale)

    assert binding["binding_id"] != "legacy-runner-shape"
    assert binding["num_ctx"] == governance.INTERACTIVE_NUM_CTX
    assert binding["num_gpu"] == governance.INTERACTIVE_NUM_GPU
    assert binding["num_batch"] == governance.INTERACTIVE_NUM_BATCH


def test_interpreter_request_body_consumes_bound_model() -> None:
    session = governance.bind_interactive_model({}, request_key="same-message")
    body = interpreter_lm._fast_interpreter_request_body(
        "classify this", {}, session=session
    )

    assert body["model"] == "qwen3:8b-q4_K_M"
    assert body["keep_alive"] == "10m"
    assert body["options"]["num_ctx"] == session[governance.BINDING_SESSION_KEY]["num_ctx"]
    assert body["options"]["num_gpu"] == session[governance.BINDING_SESSION_KEY]["num_gpu"]
    assert body["options"]["num_batch"] == session[governance.BINDING_SESSION_KEY]["num_batch"]


def test_chief_album_calls_share_the_resident_interactive_8b() -> None:
    captured: dict = {}

    def fake_call(prompt, **kwargs):
        captured["prompt"] = prompt
        captured["kwargs"] = kwargs
        return "{}"

    result = chief_album_brain._call_album_model(
        "extract this update",
        adaptive_call_fn=fake_call,
    )

    assert result == "{}"
    assert captured["kwargs"]["model"] == governance.INTERACTIVE_MODEL
    assert captured["kwargs"]["keep_alive"] == governance.INTERACTIVE_KEEP_ALIVE
    assert captured["kwargs"]["options"]["num_ctx"] == governance.INTERACTIVE_NUM_CTX
    assert captured["kwargs"]["options"]["num_gpu"] == governance.INTERACTIVE_NUM_GPU
    assert captured["kwargs"]["options"]["num_batch"] == governance.INTERACTIVE_NUM_BATCH
    assert captured["kwargs"]["retry"] is False


def test_request_processor_passes_binding_into_interpreter(monkeypatch) -> None:
    session = governance.bind_interactive_model({}, request_key="same-message")
    captured: dict = {}

    def fake_interpret(text, *, session=None, **_kwargs):
        captured["text"] = text
        captured["session"] = session
        return interpreter_lm.InterpretResult(
            route=interpreter_lm.ROUTE_UNCERTAIN,
            reason="test",
        )

    monkeypatch.setattr(interpreter_lm, "interpret_operator_message", fake_interpret)
    processor._INTERPRETER_RESULT_CACHE.clear()
    processor._interpret_for_request("same operator message", session=session)

    assert captured["text"] == "same operator message"
    assert governance.interactive_model_from_session(captured["session"]) == governance.INTERACTIVE_MODEL


def test_responder_passes_bound_model_to_protected_generate(monkeypatch) -> None:
    session = governance.bind_interactive_model({}, request_key="same-message")
    captured: dict = {}

    monkeypatch.setattr(
        maestro,
        "build_truthful_status_capability_answer",
        lambda **_kwargs: {
            "plain_summary": "Current and grounded.",
            "one_line_answer": "Current and grounded.",
            "machine_proof": {"source_truth_refs": ()},
        },
    )

    def fake_generate(text, **kwargs):
        captured.update(kwargs)
        return protected_generate.ProtectedGenerateOutcome(
            status="ANSWER_READY",
            text="Current and grounded.",
            receipt={
                "status": "ANSWER_READY",
                "decision": "ALLOW_LOCAL_MODEL",
                "model_call_performed": True,
                "local_model_invoked": True,
                "external_llm_invoked": False,
                "model_selected": kwargs.get("model_selected"),
            },
        )

    monkeypatch.setattr(protected_generate, "protected_generate_with_receipt", fake_generate)
    maestro._answer_status_capability_with_brain(
        "give me a grounded system readback",
        session=session,
        source_surface="operator_maestro_chat",
        forwarded_session={},
        protected_generate_fn=None,
        agent="maestro",
    )

    assert captured["model_selected"] == governance.INTERACTIVE_MODEL


def test_async_model_call_defers_while_interactive_8b_is_resident(
    tmp_path: Path,
) -> None:
    called = False

    def call_model() -> str:
        nonlocal called
        called = True
        return "should not run"

    outcome = governance.run_async_model_call(
        call_model,
        task_class="cassandra_morning_brief",
        holder_id="brief:morning",
        gpu_lease_db=tmp_path / "gpu.sqlite",
        model_slot_path=tmp_path / "slot.lock",
        resident_models_fn=lambda: {governance.INTERACTIVE_MODEL},
    )

    assert outcome.status == "deferred"
    assert outcome.reason == "interactive_model_resident"
    assert outcome.value is None
    assert called is False


def test_async_model_call_holds_build_lease_and_releases_it(
    tmp_path: Path,
) -> None:
    lease_db = tmp_path / "gpu.sqlite"
    observed: dict = {}

    def call_model() -> str:
        observed["lease"] = GPUArbiter(lease_db).current()
        return "brief ready"

    outcome = governance.run_async_model_call(
        call_model,
        task_class="cassandra_morning_brief",
        holder_id="brief:morning",
        gpu_lease_db=lease_db,
        model_slot_path=tmp_path / "slot.lock",
        resident_models_fn=set,
    )

    assert outcome.status == "completed"
    assert outcome.value == "brief ready"
    assert observed["lease"]["holder_type"] == "build"
    assert GPUArbiter(lease_db).current() is None


def test_briefing_scheduler_retries_instead_of_generating_under_interactive_residency(
    monkeypatch,
) -> None:
    generated: list[str] = []
    monkeypatch.setattr(scheduler, "_refresh_presence_read_model", lambda: None)
    monkeypatch.setattr(scheduler, "is_status_dry_run_enabled", lambda: False)
    monkeypatch.setattr(scheduler, "should_quiesce_send_capable_service", lambda: False)
    monkeypatch.setattr(scheduler, "_restart_if_sources_changed", lambda: None)
    monkeypatch.setattr(scheduler, "due_slots", lambda: ["morning"])
    monkeypatch.setattr(scheduler, "pending_briefings", lambda: [])
    monkeypatch.setattr(scheduler, "_deliver", lambda _entry: None)
    monkeypatch.setattr(
        scheduler,
        "async_model_admission_reason",
        lambda: "interactive_model_resident",
        raising=False,
    )
    monkeypatch.setattr(
        scheduler,
        "generate_briefing",
        lambda slot: generated.append(slot) or "must not generate",
    )

    scheduler._tick()

    assert generated == []


def test_chief_async_boundary_forces_heavy_model_unload(monkeypatch) -> None:
    captured: dict = {}

    def fake_governed(call_model, **kwargs):
        captured.update(kwargs)
        return governance.GovernedCallOutcome(
            status="completed", reason="build_window_acquired", value=call_model()
        )

    monkeypatch.setattr(governance, "run_async_model_call", fake_governed)
    monkeypatch.setattr(
        chief_llm,
        "_ollama_installed_models",
        lambda: {"magistral:latest"},
    )
    monkeypatch.setattr(
        chief_llm,
        "_ollama_model_sizes",
        lambda *a, **k: {"magistral:latest": 14.0},
    )

    request_bodies: list[dict] = []

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return b'{"response":"ready","done_reason":"stop"}'

    def fake_urlopen(request, timeout):
        import json

        request_bodies.append(json.loads(request.data.decode("utf-8")))
        return Response()

    monkeypatch.setattr(chief_llm.urllib.request, "urlopen", fake_urlopen)
    result = chief_llm.ollama_call(
        "build the brief",
        timeout=5,
        model="magistral:latest",
        task_class="cassandra_morning_brief",
        attempts=1,
        keep_alive="10m",
    )

    assert result == "ready"
    assert request_bodies[0]["keep_alive"] == "0"
    assert captured["task_class"] == "cassandra_morning_brief"
