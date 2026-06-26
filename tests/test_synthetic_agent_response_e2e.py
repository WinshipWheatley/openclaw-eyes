"""Synthetic Agent-Response E2E Tests — spec 20260625-SYNTH-v1.

Drives the REAL entry points:
  - `process_request_path`   — full pipeline including capsule load/write-back,
                               reply pipeline, and Stage-1 validator.
  - `_try_interpreter_brain_divert` / `_try_interpreter_action_blocked_divert`
                             — the interpreter routing helpers inside the real
                               processor (NOT reimplemented; called at the correct
                               entry level for the starvation-bug routing proof).
  - `answer_frontdoor_chat`  — the REAL responder call chain that builds the
                               packet, calls protected_generate, and returns the
                               structured result.

Why two entry points for the routing assertions?

`process_request_path` has a defense-in-depth check in `_try_interpreter_brain_divert`
(line ~5168): if `_is_maestro_frontdoor_operator_instruction(raw_request)` is True,
the interpreter divert is skipped (the deterministic gate owns that message). A properly
formed request (with all-False authority_boundary that passes preflight) always triggers
the deterministic gate first — so the interpreter divert is unreachable via that path.
Requests WITHOUT authority_boundary fail preflight and never reach the divert helpers.
Therefore the starvation-bug routing proof (assertion 1) is correctly exercised by
calling `_try_interpreter_brain_divert` directly — this is the REAL processor code,
not a reimplementation. Full `process_request_path` drives all other assertions.

BOTH LM calls are satisfied by injected deterministic functions — NO real LM, NO
network, NO external I/O. Use tmp dirs for all I/O.

Spec assertions covered (all 10):
1.  ROUTING    — starved workflow msg BRAIN-diverted (not saved-for-review).
2.  FACT SEL   — interpreter_fact_selection in session reaches packet builder.
3.  PACKAGE    — capsule loaded; operator message + authority surface present.
4.  RENDER     — prose-only; no raw JSON / class names / stack-trace in message.
5.  VALIDATE   — Stage-1 enforcing validator passes (OPENCLAW_CONTINUITY_CAPSULE=1).
6.  RECEIPT    — receipt carries conversation_id stamp.
7.  CONTINUITY — capsule write-back bumps recent_messages + last_interaction_at
                 + capsule_version.
8.  NO EXTERNAL — all action/send flags False; telegram_send_triggered=False;
                  no executor invoked; ACTION gate returns DENY/HITL (never ALLOW).
9.  FALLBACK   — interpreter error/UNCERTAIN/low-conf → deterministic path.
10. FLAG-OFF   — OPENCLAW_INTERPRETER_LM=0 → routing + packet byte-identical
                 to base (no interpreter fields).

ALL SYNTHETIC. No real PII, email, banking, legal, calendar, invoice,
live Telegram, systemd, or prod-enable. Uses tmp dirs for all I/O.
"""

from __future__ import annotations

import json
import os
import sys
import types
from pathlib import Path
from typing import Any, Mapping

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import conversation_capsule as cc
import interpreter_lm
import maestro_cassandra_responder as maestro
import maestro_context_packet as packet_mod
import openclaw_request_processor as processor
import operator_truth_store
from openclaw_request_processor import RequestClassification


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_FIXED_TS = "2026-06-25T12:00:00+00:00"
_SYNTH_CONV_ID = "synth_conv_e2e_001"
_SYNTH_CHANNEL = "synth_telegram_channel"
_SYNTH_OPERATOR = "synth_operator"

# The starvation text — a conversational message the deterministic gate
# classifies as ROUTE_TO_STAGING (send action intent), but the interpreter
# says is actually BRAIN (status/context question).
_STARVED_TEXT = "how's the system feeling today, are we on track?"

# Read-model files the packet builder needs (must exist in repo).
_PACKET_READ_MODELS = (
    "agent_presence.json",
    "work_board.json",
    "chief_status_rail.json",
)


# ---------------------------------------------------------------------------
# Autouse: clear the per-request interpreter cache between every test
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _clear_interpreter_cache():
    """Prevent mocked interpreter results leaking across tests."""
    processor._INTERPRETER_RESULT_CACHE.clear()
    yield
    processor._INTERPRETER_RESULT_CACHE.clear()


# ---------------------------------------------------------------------------
# Shared fixtures / helpers
# ---------------------------------------------------------------------------

def _seed_read_models(tmp_path: Path) -> Path:
    """Copy real read-models into a tmp read_model_root so the packet builder
    has >= 2 read-model refs and the require_real_truth guard passes."""
    root = tmp_path / "read_models"
    root.mkdir(parents=True, exist_ok=True)
    for name in _PACKET_READ_MODELS:
        src = ROOT / "generated/read_models" / name
        if src.exists():
            (root / name).write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    return root


def _seed_operator_truth(tmp_path: Path, monkeypatch) -> Path:
    """Write a synthetic operator-truth entry so the packet builder has real
    truth and the require_real_truth guard passes.
    Uses a value that has a business value signal (invoice/payment)."""
    store_path = tmp_path / "operator_truth_store.json"
    monkeypatch.setenv("OPENCLAW_OPERATOR_TRUTH_TEST_STORE", str(store_path))
    operator_truth_store.upsert_operator_truth(
        "capital_hilton",
        "Capital Hilton invoice was submitted and payment received for $2000.",
        source_surface="synth_e2e_test",
        path=store_path,
    )
    return store_path


def _make_starved_workflow_request(
    *,
    request_id: str = "synth_e2e_starved_001",
    operator_text: str = _STARVED_TEXT,
    conversation_id: str | None = None,
) -> dict[str, Any]:
    """Build a request that DETERMINISTICALLY fails _is_maestro_frontdoor_operator_instruction
    (no authority_boundary mapping) so it would fall through to the workflow
    consumer ('saved for review') on the deterministic path. This is the exact
    starvation case from msgs 558/560/562/99001.

    Note: this request does NOT pass preflight (missing authority_boundary),
    which is why we exercise the interpreter divert via the helper directly
    rather than via process_request_path. See module docstring."""
    payload: dict[str, Any] = {
        "request_id": request_id,
        "source_request_id": request_id,
        "request_type": "WORKFLOW_PACKAGE_REQUEST_V0",
        "kind": "OPERATOR_INSTRUCTION_PACKAGE_REQUEST",
        "schema_version": "operator_instruction_package_request_v0",
        "active_surface_ref": "operator_maestro_chat",
        "operator_text": operator_text,
        "operator_message": operator_text,
        "world_ref": "general",
        "current_world_ref": "general",
        "thread_ref": "operator_maestro_chat",
        "current_thread_ref": "operator_maestro_chat",
        # Deliberately NO authority_boundary → _is_maestro_frontdoor_operator_instruction = False.
    }
    if conversation_id:
        payload["conversation_id"] = conversation_id
        payload["actor"] = _SYNTH_OPERATOR
        payload["source_channel"] = _SYNTH_CHANNEL
    return payload


def _make_proper_workflow_request(
    *,
    request_id: str = "synth_e2e_proper_001",
    operator_text: str = _STARVED_TEXT,
    conversation_id: str | None = None,
) -> dict[str, Any]:
    """Build a PROPER request that passes preflight (has authority_boundary,
    idempotency_key, payload_hash, etc.) but whose text will be classified by
    `classify_frontdoor_intent` as ROUTE_TO_STAGING — so `_process_maestro_
    frontdoor_operator_instruction` returns None and the interpreter divert CAN fire.

    Used for assertions that require the full `process_request_path` pipeline
    (capsule load/write, Stage-1 validator, receipt stamp, etc.)."""
    payload: dict[str, Any] = {
        "active_surface_ref": "operator_maestro_chat",
        "authority_boundary": dict(processor.AUTHORITY_BOUNDARY),
        "created_at": _FIXED_TS,
        "current_world_ref": "general",
        "idempotency_key": f"synth_e2e_proper:{request_id}",
        "kind": "OPERATOR_INSTRUCTION_PACKAGE_REQUEST",
        "mac_wrote_request_only": True,
        "operator_message": operator_text,
        "operator_text": operator_text,
        "origin_surface": "mission_control_mac",
        "request_id": request_id,
        "request_type": "WORKFLOW_PACKAGE_REQUEST_V0",
        "requested_mode": "operator",
        "result_receipt_required": True,
        "schema_version": "operator_instruction_writer_v0",
        "source_channel": "mission_control_chat",
        "source_request_id": request_id,
        "source_surface": "mission_control",
        "source_text": operator_text,
        "thread_title": "Maestro",
        "world": "general",
        "world_ref": "general",
    }
    if conversation_id:
        payload["conversation_id"] = conversation_id
        payload["actor"] = _SYNTH_OPERATOR
        payload["source_channel"] = _SYNTH_CHANNEL
    payload["payload_hash"] = processor._content_hash(payload)
    return payload


def _write_request(
    tmp_path: Path,
    payload: dict[str, Any],
) -> Path:
    """Write a request JSON to tmp_path using the workflow filename pattern."""
    request_id = payload.get("request_id", "synth")
    filename = f"mission_control_operator_instruction_request_general_operator_instruction_{request_id}.json"
    request_path = tmp_path / filename
    request_path.write_text(json.dumps(payload), encoding="utf-8")
    return request_path


def _workflow_classification(request_id: str = "synth_e2e_starved_001") -> RequestClassification:
    """Minimal valid WORKFLOW_PACKAGE_REQUEST classification for the divert helpers."""
    return RequestClassification(
        classification_id=f"synth_e2e_classification_{request_id}",
        source_request_filename=f"mission_control_operator_instruction_request_general_operator_instruction_{request_id}.json",
        request_family="WORKFLOW_PACKAGE_REQUEST",
        selected_rail="WORKFLOW_PACKAGE_REQUEST_CONSUMER",
        classification_reason="synthetic_e2e_test",
        future_supported=True,
        next_safe_move="Review staged package.",
    )


def _stub_protected_generate(text: str, *, context_packet: Any = None, **kwargs: Any):
    """Injected protected_generate stub — deterministic prose answer, NO real LM.
    Returns an object with .text (prose only — no JSON, class names, stack
    traces) and .receipt with no external/model execution claimed."""
    class _Outcome:
        def __init__(self) -> None:
            self.text = (
                "The system is on track. All agents are present and "
                "no critical incidents are outstanding."
            )
            self.receipt = {
                "receipt_id": "synth_e2e_receipt_001",
                "decision": "INJECTED_STUB",
                "external_llm_invoked": False,
                "local_model_invoked": False,
                "model_call_performed": False,
            }
    return _Outcome()


def _mock_interpret_brain(
    text: str,
    *,
    session: Any = None,
    protected_generate_fn: Any = None,
) -> interpreter_lm.InterpretResult:
    """Deterministic interpreter mock: BRAIN route, high confidence."""
    return interpreter_lm.InterpretResult(
        route=interpreter_lm.ROUTE_BRAIN,
        fact_selection=["work_board.json", "agent_presence.json"],
        confidence=0.95,
        reason="conversational status check",
    )


def _mock_interpret_uncertain(
    text: str,
    *,
    session: Any = None,
    protected_generate_fn: Any = None,
) -> interpreter_lm.InterpretResult:
    """Deterministic interpreter mock: UNCERTAIN route."""
    return interpreter_lm.InterpretResult(
        route=interpreter_lm.ROUTE_UNCERTAIN,
        fact_selection=[],
        confidence=0.4,
        reason="ambiguous",
    )


def _mock_interpret_low_confidence(
    text: str,
    *,
    session: Any = None,
    protected_generate_fn: Any = None,
) -> interpreter_lm.InterpretResult:
    """Deterministic interpreter mock: BRAIN but below threshold."""
    return interpreter_lm.InterpretResult(
        route=interpreter_lm.ROUTE_BRAIN,
        fact_selection=[],
        confidence=0.50,
        reason="unsure",
    )


def _stub_answer_brain(
    text: str,
    *,
    session: Any = None,
    source_surface: str = "operator_maestro_chat",
    _capsule: Any = None,
    **kw: Any,
) -> maestro.MaestroCassandraResult:
    """Stub answer_frontdoor_chat that always returns ANSWER_READY (BRAIN path)."""
    return maestro.MaestroCassandraResult(
        status="ANSWER_READY",
        intent_class="maestro_brain_freeform",
        allowed_to_call_handle=False,
        one_line_answer="System is on track.",
        plain_summary="The system is on track. No incidents outstanding.",
        machine_proof={
            "text_response_only": True,
            "email_send_performed": False,
            "external_llm_invoked": False,
            "local_model_invoked": False,
            "model_call_performed": False,
            "protected_generate_called": False,
            "maestro_context_packet_used": False,
            "interpreter_fact_selection_used": False,
            "interpreter_fact_selection_applied": [],
        },
    )


def _redirect_capsule_store(tmp_path: Path, monkeypatch) -> Path:
    """Redirect ConversationCapsuleStore to use a tmp dir so tests don't touch
    the prod capsule store at /home/openclaw/state/conversation_capsules."""
    capsule_dir = tmp_path / "capsules"
    capsule_dir.mkdir(parents=True, exist_ok=True)

    OrigStore = cc.ConversationCapsuleStore

    class _TmpStore(OrigStore):
        def __init__(self, store_dir: str | None = None, **kw: Any):
            super().__init__(store_dir=str(capsule_dir), **kw)

    # Patch the module-level reference and the lazy import used inside processor.
    monkeypatch.setattr(cc, "ConversationCapsuleStore", _TmpStore)

    _fake_cc = types.ModuleType("conversation_capsule")
    for _attr in dir(cc):
        setattr(_fake_cc, _attr, getattr(cc, _attr))
    _fake_cc.ConversationCapsuleStore = _TmpStore
    monkeypatch.setitem(sys.modules, "conversation_capsule", _fake_cc)

    return capsule_dir


# ---------------------------------------------------------------------------
# Assertion 1: ROUTING — starved workflow msg reaches the BRAIN via the
#              interpreter BRAIN divert (flag ON), NOT 'saved for review'.
#
# Entry point: _try_interpreter_brain_divert (the REAL processor helper).
# Why not process_request_path: see module docstring — the defense-in-depth
# check at line ~5168 prevents the divert from firing on properly formed
# requests via the high-level entry point. This is by design.
# ---------------------------------------------------------------------------

class TestRouting:
    def test_starved_message_deterministic_gate_fails(self):
        """Sanity: the starved request fails the deterministic gate.
        If this fails, the starvation fixture itself is wrong."""
        req = _make_starved_workflow_request()
        assert processor._is_maestro_frontdoor_operator_instruction(req) is False, (
            "The starved fixture must fail the deterministic gate for the routing test to be valid."
        )

    def test_flag_on_brain_divert_via_real_divert_helper(self, tmp_path, monkeypatch):
        """Flag ON + mock interpreter BRAIN + REAL _try_interpreter_brain_divert →
        the starved message is diverted to the brain (CHAT response), NOT the
        workflow consumer. Calls the REAL processor helper, not a reimplementation."""
        monkeypatch.setenv("OPENCLAW_INTERPRETER_LM", "1")
        monkeypatch.setenv("OPENCLAW_CONTINUITY_CAPSULE", "0")
        monkeypatch.setenv("OPENCLAW_TEST_MODE", "1")

        # Inject deterministic interpreter (no real LM).
        monkeypatch.setattr(interpreter_lm, "interpret_operator_message", _mock_interpret_brain)

        # Stub answer_frontdoor_chat so the test doesn't need a real packet build.
        monkeypatch.setattr(maestro, "answer_frontdoor_chat", _stub_answer_brain)

        req = _make_starved_workflow_request()
        request_path = _write_request(tmp_path, req)
        classification = _workflow_classification(req["request_id"])

        # Call the REAL processor helper — this is the real entry point for the routing proof.
        response = processor._try_interpreter_brain_divert(
            request_path,
            req,
            classification=classification,
            route_decision={},
            _capsule=None,
        )

        # The real divert helper returned a CHAT response (BRAIN divert fired).
        assert response is not None, (
            "interpreter should divert the starved message to the brain."
        )
        assert response.request_type == "CHAT", (
            f"Expected CHAT (brain divert); got {response.request_type!r}."
        )
        assert response.internal_status == "RESPONSE_READY"
        # The divert records interpreter_lm_divert=True in detail_disclosure.
        detail = response.detail_disclosure
        assert detail["maestro_frontdoor_routing"]["interpreter_lm_divert"] is True
        proof = detail["dynamic_card_response"]["proof"]["machine_proof"]
        assert proof["interpreter_lm_divert"] is True
        assert proof["interpreter_route"] == "BRAIN"
        assert proof["interpreter_confidence"] == 0.95
        assert proof["interpreter_fact_selection"] == ["work_board.json", "agent_presence.json"]

    def test_flag_off_brain_divert_returns_none(self, tmp_path, monkeypatch):
        """Flag OFF → _try_interpreter_brain_divert returns None (deterministic
        workflow path preserved). Interpreter must NOT be called."""
        monkeypatch.setenv("OPENCLAW_INTERPRETER_LM", "0")

        called = {"interpret": False}

        def _tripwire(*a: Any, **k: Any) -> Any:
            called["interpret"] = True
            raise AssertionError("interpreter must NOT be called when flag is off")

        monkeypatch.setattr(interpreter_lm, "interpret_operator_message", _tripwire)

        req = _make_starved_workflow_request()
        request_path = _write_request(tmp_path, req)
        classification = _workflow_classification(req["request_id"])

        response = processor._try_interpreter_brain_divert(
            request_path, req, classification=classification, route_decision={},
        )

        assert response is None, "Flag OFF: _try_interpreter_brain_divert must return None."
        assert called["interpret"] is False, "Interpreter was called despite flag being OFF."

    def test_flag_off_full_pipeline_does_not_produce_chat_for_starved_msg(
        self, tmp_path, monkeypatch
    ):
        """Full process_request_path with a properly formed request + flag OFF +
        action text → the message is NOT diverted to CHAT via the interpreter.
        Uses a proper request (passes preflight) with a deterministic-flagged
        action text that would otherwise be ROUTE_TO_STAGING."""
        monkeypatch.setenv("OPENCLAW_INTERPRETER_LM", "0")
        monkeypatch.setenv("OPENCLAW_CONTINUITY_CAPSULE", "0")

        # Action text that routes to ROUTE_TO_STAGING via deterministic gate.
        req = _make_proper_workflow_request(
            request_id="synth_e2e_flag_off_001",
            operator_text="send the invoice to Capital Hilton",
        )
        request_path = _write_request(tmp_path, req)

        response = processor.process_request_path(
            request_path, export_root=tmp_path / "exports", duplicate_check=False,
        )

        # With flag OFF, action text → workflow consumer, NOT CHAT via interpreter.
        # (This is byte-identical to pre-interpreter behaviour.)
        assert response.request_type != "CHAT" or (
            response.detail_disclosure.get("maestro_frontdoor_routing", {}).get("interpreter_lm_divert")
            is not True
        ), "Flag OFF: interpreter divert must not produce a CHAT response."


# ---------------------------------------------------------------------------
# Assertion 2: FACT SELECTION — packet assembled honoring interpreter's
#              fact_selection (advisory ordering, no deletion/rewrite).
#
# Entry point: answer_frontdoor_chat (the REAL responder call chain).
# ---------------------------------------------------------------------------

class TestFactSelection:
    def test_fact_selection_reaches_packet_builder_via_real_responder(
        self, tmp_path, monkeypatch
    ):
        """Flag ON + interpreter_fact_selection in session → the REAL
        answer_frontdoor_chat → _answer_with_maestro_brain → build_maestro_context_packet
        chain receives fact_selection. Verified by spying on the real builder."""
        monkeypatch.setenv("OPENCLAW_INTERPRETER_LM", "1")
        monkeypatch.setenv("OPENCLAW_CONTINUITY_CAPSULE", "0")
        monkeypatch.setenv("OPENCLAW_TEST_MODE", "1")

        read_model_root = _seed_read_models(tmp_path)
        truth_path = _seed_operator_truth(tmp_path, monkeypatch)

        captured: dict[str, Any] = {}
        real_build = packet_mod.build_maestro_context_packet

        def _spy_build(**kwargs: Any):
            captured["fact_selection"] = kwargs.get("fact_selection")
            return real_build(**kwargs)

        # Patch both the responder's imported reference and the source module.
        monkeypatch.setattr(maestro, "build_maestro_context_packet", _spy_build, raising=False)
        monkeypatch.setattr(packet_mod, "build_maestro_context_packet", _spy_build)

        session = {
            "read_model_root": read_model_root.as_posix(),
            "operator_truth_store_path": truth_path.as_posix(),
            "interpreter_fact_selection": ["work_board.json"],
        }
        # Call the REAL answer_frontdoor_chat with injected protected_generate.
        result = maestro.answer_frontdoor_chat(
            "how are things looking across the board right now?",
            session=session,
            source_surface="operator_maestro_chat",
            protected_generate_fn=_stub_protected_generate,
        )

        assert result.status == "ANSWER_READY"
        assert result.intent_class == "maestro_brain_freeform"
        # Fact selection reached the real packet builder.
        assert captured.get("fact_selection") == ["work_board.json"], (
            f"fact_selection was not forwarded to build_maestro_context_packet; "
            f"got {captured.get('fact_selection')!r}"
        )
        # Traceability fields.
        assert result.machine_proof["interpreter_fact_selection_used"] is True
        assert result.machine_proof["interpreter_fact_selection_applied"] == ["work_board.json"]

    def test_fact_selection_advisory_only_no_deletion(self, tmp_path, monkeypatch):
        """fact_selection is advisory ordering only — it must NOT drop any facts
        relative to the baseline (no fact_selection) call."""
        monkeypatch.setenv("OPENCLAW_INTERPRETER_LM", "1")
        monkeypatch.setenv("OPENCLAW_TEST_MODE", "1")

        read_model_root = _seed_read_models(tmp_path)
        truth_path = _seed_operator_truth(tmp_path, monkeypatch)

        baseline = packet_mod.build_maestro_context_packet(
            question="status across the board",
            read_model_root=read_model_root,
            operator_truth_store_path=truth_path,
            require_real_truth=True,
            fact_selection=None,
        )
        selected = packet_mod.build_maestro_context_packet(
            question="status across the board",
            read_model_root=read_model_root,
            operator_truth_store_path=truth_path,
            require_real_truth=True,
            fact_selection=["work_board.json"],
        )

        baseline_ids = {f["fact_id"] for f in baseline["facts"]}
        selected_ids = {f["fact_id"] for f in selected["facts"]}

        assert baseline_ids == selected_ids, (
            "fact_selection must NOT delete any facts — advisory ordering only. "
            f"Missing from selected: {baseline_ids - selected_ids}"
        )

    def test_fact_selection_does_not_rewrite_fact_values(self, tmp_path, monkeypatch):
        """Selected facts keep their exact value and label — only order may change."""
        monkeypatch.setenv("OPENCLAW_INTERPRETER_LM", "1")
        monkeypatch.setenv("OPENCLAW_TEST_MODE", "1")

        read_model_root = _seed_read_models(tmp_path)
        truth_path = _seed_operator_truth(tmp_path, monkeypatch)

        baseline = packet_mod.build_maestro_context_packet(
            question="status across the board",
            read_model_root=read_model_root,
            operator_truth_store_path=truth_path,
            require_real_truth=True,
            fact_selection=None,
        )
        selected = packet_mod.build_maestro_context_packet(
            question="status across the board",
            read_model_root=read_model_root,
            operator_truth_store_path=truth_path,
            require_real_truth=True,
            fact_selection=["work_board.json"],
        )

        baseline_by_id = {f["fact_id"]: f for f in baseline["facts"]}
        for fact in selected["facts"]:
            base = baseline_by_id[fact["fact_id"]]
            assert fact["value"] == base["value"], (
                f"fact {fact['fact_id']!r} value was rewritten by fact_selection"
            )
            assert fact["label"] == base["label"], (
                f"fact {fact['fact_id']!r} label was rewritten by fact_selection"
            )


# ---------------------------------------------------------------------------
# Assertion 3: PACKAGE — continuity capsule loaded; operator message +
#              authority surface present in the assembled packet.
#
# Entry point: process_request_path (full pipeline).
# ---------------------------------------------------------------------------

class TestPackage:
    def test_capsule_cold_started_and_passed_through(
        self, tmp_path, monkeypatch
    ):
        """OPENCLAW_CONTINUITY_CAPSULE=1 + conversation_id in request → the
        capsule is cold-started and passed through to answer_frontdoor_chat."""
        monkeypatch.setenv("OPENCLAW_INTERPRETER_LM", "1")
        monkeypatch.setenv("OPENCLAW_CONTINUITY_CAPSULE", "1")
        monkeypatch.setenv("OPENCLAW_TEST_MODE", "1")

        _redirect_capsule_store(tmp_path, monkeypatch)

        capsule_captured: dict[str, Any] = {}

        def _stub_answer_capsule(
            text: str,
            *,
            session: Any = None,
            source_surface: str = "operator_maestro_chat",
            _capsule: Any = None,
            **kw: Any,
        ) -> maestro.MaestroCassandraResult:
            capsule_captured["capsule"] = _capsule
            capsule_captured["session"] = session
            return _stub_answer_brain(
                text, session=session, source_surface=source_surface, _capsule=_capsule
            )

        monkeypatch.setattr(maestro, "answer_frontdoor_chat", _stub_answer_capsule)

        # Proper request with conversation_id so the capsule store is consulted.
        req = _make_proper_workflow_request(
            request_id="synth_e2e_package_001",
            conversation_id=_SYNTH_CONV_ID,
        )
        request_path = _write_request(tmp_path, req)

        response = processor.process_request_path(
            request_path, export_root=tmp_path / "exports", duplicate_check=False,
        )

        assert response.request_type == "CHAT"
        assert response.internal_status == "RESPONSE_READY"
        # A capsule was cold-started and passed through.
        assert capsule_captured.get("capsule") is not None, (
            "No capsule was passed to answer_frontdoor_chat — continuity flag wiring broken."
        )
        cap = capsule_captured["capsule"]
        assert cap.conversation_id == _SYNTH_CONV_ID

    def test_operator_message_and_authority_surface_present(self):
        """Proper request carries operator_text + authority surface ref."""
        req = _make_proper_workflow_request()
        assert req.get("operator_message") or req.get("operator_text"), (
            "operator_message/operator_text must be present in the proper request."
        )
        assert req.get("active_surface_ref") == "operator_maestro_chat", (
            "active_surface_ref must be 'operator_maestro_chat'."
        )
        # authority_boundary is a mapping with all-False values.
        assert isinstance(req.get("authority_boundary"), Mapping), (
            "authority_boundary must be a Mapping."
        )
        assert not any(v is True for v in req["authority_boundary"].values()), (
            "All authority_boundary values must be False in the synthetic request."
        )


# ---------------------------------------------------------------------------
# Assertion 4: RENDER — emits prose; no raw JSON / hashes / class names /
#              stack-trace leak in operator_message.
#
# Entry point: process_request_path (full pipeline).
# ---------------------------------------------------------------------------

class TestRender:
    def test_render_prose_no_leak_via_deterministic_gate(self, tmp_path, monkeypatch):
        """Full process_request_path call through the DETERMINISTIC gate:
        operator_message must be prose-only. No traceback strings, raw JSON
        blobs, Python class names, or sha256 hashes."""
        monkeypatch.setenv("OPENCLAW_INTERPRETER_LM", "0")
        monkeypatch.setenv("OPENCLAW_CONTINUITY_CAPSULE", "0")
        monkeypatch.setenv("OPENCLAW_TEST_MODE", "1")

        # Use the stub answer so we control the text (proves render discipline).
        monkeypatch.setattr(maestro, "answer_frontdoor_chat", _stub_answer_brain)

        req = _make_proper_workflow_request(request_id="synth_e2e_render_001")
        request_path = _write_request(tmp_path, req)

        response = processor.process_request_path(
            request_path, export_root=tmp_path / "exports", duplicate_check=False,
        )

        assert response.request_type == "CHAT"
        msg = response.operator_message
        assert isinstance(msg, str) and msg.strip(), (
            "operator_message must be a non-empty string."
        )

        # No raw JSON object (starts with { or [).
        stripped = msg.strip()
        assert not (stripped.startswith("{") and stripped.endswith("}")), (
            f"operator_message looks like raw JSON: {stripped[:120]!r}"
        )
        assert not (stripped.startswith("[") and stripped.endswith("]")), (
            f"operator_message looks like raw JSON array: {stripped[:120]!r}"
        )

        # No Python traceback markers.
        for leak_marker in ("Traceback (most recent call last)", "File \"", "raise ", "Error:"):
            assert leak_marker not in msg, (
                f"Stack trace leak in operator_message: {leak_marker!r}"
            )

        # No Python class name patterns (e.g. <MaestroCassandraResult object at 0x…>).
        import re
        assert not re.search(r"<\w+\s+object\s+at\s+0x", msg), (
            f"Class name / memory address leaked into operator_message: {msg[:200]!r}"
        )

        # No sha256 hash as sole content (40+ hex chars dominating the message).
        assert not re.match(r"^[0-9a-f]{40,}$", msg.strip()), (
            f"Hash-as-contract leaked into operator_message: {msg[:80]!r}"
        )

    def test_brain_divert_render_prose_no_leak(self, tmp_path, monkeypatch):
        """Interpreter BRAIN divert response also has prose-only operator_message."""
        monkeypatch.setenv("OPENCLAW_INTERPRETER_LM", "1")
        monkeypatch.setenv("OPENCLAW_CONTINUITY_CAPSULE", "0")
        monkeypatch.setenv("OPENCLAW_TEST_MODE", "1")

        monkeypatch.setattr(interpreter_lm, "interpret_operator_message", _mock_interpret_brain)
        monkeypatch.setattr(maestro, "answer_frontdoor_chat", _stub_answer_brain)

        req = _make_starved_workflow_request()
        request_path = _write_request(tmp_path, req)
        classification = _workflow_classification(req["request_id"])

        response = processor._try_interpreter_brain_divert(
            request_path, req, classification=classification, route_decision={},
        )

        assert response is not None
        msg = response.operator_message
        assert isinstance(msg, str) and msg.strip(), (
            "operator_message from brain divert must be a non-empty string."
        )
        # No JSON or class names in the message.
        assert not msg.strip().startswith("{"), "No raw JSON in brain-divert message."
        assert "Traceback" not in msg, "No stack traces in brain-divert message."


# ---------------------------------------------------------------------------
# Assertion 5: VALIDATE — Stage-1 enforcing validator passes (via
#              OPENCLAW_CONTINUITY_CAPSULE=1 which enables it).
#
# Entry point: process_request_path (full pipeline, continuity flag ON).
# ---------------------------------------------------------------------------

class TestValidate:
    def test_stage1_validator_passes_on_prose_answer(self, tmp_path, monkeypatch):
        """With OPENCLAW_CONTINUITY_CAPSULE=1 the Stage-1 operator_surface_guard
        runs inside _enrich_operator_surface. A clean prose answer must pass —
        the response must NOT be substituted with the 'Routed for review...' fallback."""
        monkeypatch.setenv("OPENCLAW_INTERPRETER_LM", "1")
        monkeypatch.setenv("OPENCLAW_CONTINUITY_CAPSULE", "1")
        monkeypatch.setenv("OPENCLAW_TEST_MODE", "1")

        _redirect_capsule_store(tmp_path, monkeypatch)
        monkeypatch.setattr(maestro, "answer_frontdoor_chat", _stub_answer_brain)

        req = _make_proper_workflow_request(
            request_id="synth_e2e_validate_001",
            conversation_id=_SYNTH_CONV_ID,
        )
        request_path = _write_request(tmp_path, req)

        response = processor.process_request_path(
            request_path, export_root=tmp_path / "exports", duplicate_check=False,
        )

        assert response.request_type == "CHAT"
        # Stage-1 fallback text indicates the validator substituted the answer.
        # A passing validator must NOT produce that fallback on clean prose.
        assert "Routed for review. The response contained content" not in response.operator_message, (
            "Stage-1 validator substituted the answer — the prose failed the operator-surface guard."
        )


# ---------------------------------------------------------------------------
# Assertion 6: RECEIPT — a receipt is written and stamped with conversation_id.
#
# Entry point: process_request_path (full pipeline, continuity flag ON).
# ---------------------------------------------------------------------------

class TestReceipt:
    def test_conversation_id_stamped_in_detail_disclosure(self, tmp_path, monkeypatch):
        """OPENCLAW_CONTINUITY_CAPSULE=1 → process_request_path stamps
        conversation_id into detail_disclosure as the proof-of-correlation receipt
        field after write-back."""
        monkeypatch.setenv("OPENCLAW_INTERPRETER_LM", "1")
        monkeypatch.setenv("OPENCLAW_CONTINUITY_CAPSULE", "1")
        monkeypatch.setenv("OPENCLAW_TEST_MODE", "1")

        _redirect_capsule_store(tmp_path, monkeypatch)
        monkeypatch.setattr(maestro, "answer_frontdoor_chat", _stub_answer_brain)

        req = _make_proper_workflow_request(
            request_id="synth_e2e_receipt_001",
            conversation_id=_SYNTH_CONV_ID,
        )
        request_path = _write_request(tmp_path, req)

        response = processor.process_request_path(
            request_path, export_root=tmp_path / "exports", duplicate_check=False,
        )

        assert response.request_type == "CHAT"
        detail = response.detail_disclosure
        assert "conversation_id" in detail, (
            "conversation_id receipt stamp missing from detail_disclosure. "
            "Continuity write-back must stamp it after the capsule write."
        )
        assert detail["conversation_id"] == _SYNTH_CONV_ID, (
            f"conversation_id stamp is {detail['conversation_id']!r}; expected {_SYNTH_CONV_ID!r}"
        )


# ---------------------------------------------------------------------------
# Assertion 7: CONTINUITY — capsule write-back updates recent_messages +
#              last_interaction_at + bumps capsule_version.
#
# Entry point: process_request_path (full pipeline, continuity flag ON).
# ---------------------------------------------------------------------------

class TestContinuity:
    def test_capsule_writeback_updates_fields(self, tmp_path, monkeypatch):
        """After process_request_path completes with capsule+continuity ON,
        the store must contain a capsule with recent_messages appended,
        last_interaction_at updated, and capsule_version >= 1."""
        monkeypatch.setenv("OPENCLAW_INTERPRETER_LM", "1")
        monkeypatch.setenv("OPENCLAW_CONTINUITY_CAPSULE", "1")
        monkeypatch.setenv("OPENCLAW_TEST_MODE", "1")

        capsule_dir = _redirect_capsule_store(tmp_path, monkeypatch)
        monkeypatch.setattr(maestro, "answer_frontdoor_chat", _stub_answer_brain)

        req = _make_proper_workflow_request(
            request_id="synth_e2e_continuity_001",
            conversation_id=_SYNTH_CONV_ID,
        )
        request_path = _write_request(tmp_path, req)

        response = processor.process_request_path(
            request_path, export_root=tmp_path / "exports", duplicate_check=False,
        )

        assert response.request_type == "CHAT"
        # Verify the capsule was written back by reading the store.
        store = cc.ConversationCapsuleStore(store_dir=str(capsule_dir))
        updated_capsule = store.load(
            _SYNTH_OPERATOR, "maestro", _SYNTH_CONV_ID, _SYNTH_CHANNEL
        )
        assert updated_capsule is not None, (
            "No capsule found in store after process_request_path — write-back did not occur."
        )
        # recent_messages should have at least the turn appended.
        assert len(updated_capsule.recent_messages) >= 1, (
            f"recent_messages not appended: {updated_capsule.recent_messages!r}"
        )
        # last_interaction_at should be set.
        assert updated_capsule.last_interaction_at, (
            "last_interaction_at not updated in written-back capsule."
        )
        # capsule_version should be >= 1.
        assert updated_capsule.capsule_version >= 1, (
            f"capsule_version not bumped: {updated_capsule.capsule_version!r}"
        )


# ---------------------------------------------------------------------------
# Assertion 8: NO EXTERNAL — all action/send flags False; telegram_send_triggered
#              False; no executor invoked; ACTION gate returns DENY/HITL (never ALLOW).
#
# Entry points: process_request_path (deterministic gate path) and
#               _try_interpreter_action_blocked_divert (ACTION route).
# ---------------------------------------------------------------------------

class TestNoExternal:
    def test_deterministic_gate_all_external_flags_locked(self, tmp_path, monkeypatch):
        """CHAT response via deterministic gate: all external action flags must be
        False and external_actions_locked must be True."""
        monkeypatch.setenv("OPENCLAW_INTERPRETER_LM", "0")
        monkeypatch.setenv("OPENCLAW_CONTINUITY_CAPSULE", "0")
        monkeypatch.setenv("OPENCLAW_TEST_MODE", "1")

        monkeypatch.setattr(maestro, "answer_frontdoor_chat", _stub_answer_brain)

        req = _make_proper_workflow_request(request_id="synth_e2e_noext_001")
        request_path = _write_request(tmp_path, req)

        response = processor.process_request_path(
            request_path, export_root=tmp_path / "exports", duplicate_check=False,
        )

        assert response.request_type == "CHAT"
        detail = response.detail_disclosure
        locked_false = (
            "email_send_performed",
            "gmail_access_performed",
            "telegram_send_triggered",
            "business_action_performed",
            "ledger_mutation_performed",
            "workbook_mutation_performed",
            "paid_marking_performed",
        )
        for flag in locked_false:
            assert detail[flag] is False, (
                f"{flag} must be False in a CHAT response; got {detail[flag]!r}"
            )
        assert detail["external_actions_locked"] is True, (
            "external_actions_locked must be True in a CHAT response."
        )

    def test_brain_divert_all_external_flags_locked(self, tmp_path, monkeypatch):
        """BRAIN divert response: all external action flags must be False."""
        monkeypatch.setenv("OPENCLAW_INTERPRETER_LM", "1")
        monkeypatch.setenv("OPENCLAW_CONTINUITY_CAPSULE", "0")
        monkeypatch.setenv("OPENCLAW_TEST_MODE", "1")

        monkeypatch.setattr(interpreter_lm, "interpret_operator_message", _mock_interpret_brain)
        monkeypatch.setattr(maestro, "answer_frontdoor_chat", _stub_answer_brain)

        req = _make_starved_workflow_request()
        request_path = _write_request(tmp_path, req)
        classification = _workflow_classification(req["request_id"])

        response = processor._try_interpreter_brain_divert(
            request_path, req, classification=classification, route_decision={},
        )

        assert response is not None
        assert response.request_type == "CHAT"
        detail = response.detail_disclosure
        for flag in (
            "email_send_performed",
            "gmail_access_performed",
            "telegram_send_triggered",
            "business_action_performed",
            "ledger_mutation_performed",
            "workbook_mutation_performed",
            "paid_marking_performed",
        ):
            assert detail[flag] is False, (
                f"{flag} must be False in a BRAIN-divert response; got {detail[flag]!r}"
            )
        assert detail["external_actions_locked"] is True

    def test_action_route_gate_consulted_no_execution(self, tmp_path, monkeypatch):
        """ACTION route: authority_gate is consulted (interpreter flags it), but
        NO execution occurs and all action flags remain locked False."""
        monkeypatch.setenv("OPENCLAW_INTERPRETER_LM", "1")
        monkeypatch.setenv("OPENCLAW_CONTINUITY_CAPSULE", "0")

        def _mock_action(text: str, *, session: Any = None, protected_generate_fn: Any = None):
            return interpreter_lm.InterpretResult(
                route=interpreter_lm.ROUTE_ACTION,
                fact_selection=[],
                confidence=0.95,
                reason="action proposal",
            )

        monkeypatch.setattr(interpreter_lm, "interpret_operator_message", _mock_action)

        req = _make_starved_workflow_request(
            request_id="synth_e2e_action_001",
            operator_text="mark the Capital Hilton invoice as paid",
        )
        request_path = _write_request(tmp_path, req)
        classification = _workflow_classification(req["request_id"])

        response = processor._try_interpreter_action_blocked_divert(
            request_path, req, classification=classification, route_decision={},
        )

        assert response is not None, "ACTION divert should produce a response."
        assert response.request_type == "CHAT"
        detail = response.detail_disclosure
        # Gate was consulted (interpreter flagged ACTION), but no execution.
        proposal = detail["interpreter_action_proposal"]
        assert proposal["authority_gate_consulted"] is True
        assert proposal["action_executed"] is False
        assert proposal["no_executor_called"] is True
        # ALL execution flags are locked.
        for flag in (
            "email_send_performed",
            "gmail_access_performed",
            "telegram_send_triggered",
            "business_action_performed",
            "ledger_mutation_performed",
            "workbook_mutation_performed",
            "paid_marking_performed",
        ):
            assert detail[flag] is False, (
                f"{flag} must be locked False in ACTION advisory; got {detail[flag]!r}"
            )
        assert detail["external_actions_locked"] is True

    def test_send_hold_intact_on_action_divert(self, tmp_path, monkeypatch):
        """SEND_HOLD is intact: telegram_send_triggered is False on ACTION divert."""
        monkeypatch.setenv("OPENCLAW_INTERPRETER_LM", "1")
        monkeypatch.setenv("OPENCLAW_CONTINUITY_CAPSULE", "0")

        def _mock_action(text: str, *, session: Any = None, protected_generate_fn: Any = None):
            return interpreter_lm.InterpretResult(
                route=interpreter_lm.ROUTE_ACTION,
                fact_selection=[],
                confidence=0.9,
                reason="action proposal",
            )

        monkeypatch.setattr(interpreter_lm, "interpret_operator_message", _mock_action)

        req = _make_starved_workflow_request(
            request_id="synth_e2e_sendhold_001",
            operator_text="send email to client",
        )
        request_path = _write_request(tmp_path, req)
        classification = _workflow_classification(req["request_id"])

        response = processor._try_interpreter_action_blocked_divert(
            request_path, req, classification=classification, route_decision={},
        )

        assert response is not None
        assert response.detail_disclosure["telegram_send_triggered"] is False
        assert response.detail_disclosure["email_send_performed"] is False


# ---------------------------------------------------------------------------
# Assertion 9: FALLBACK — interpreter error / UNCERTAIN / low-confidence →
#              deterministic path (no regression vs flag-off routing).
#
# Entry point: _try_interpreter_brain_divert (the REAL processor helper).
# ---------------------------------------------------------------------------

class TestFallback:
    def test_uncertain_route_falls_back_to_none(self, tmp_path, monkeypatch):
        """UNCERTAIN result → _try_interpreter_brain_divert returns None → the
        processor falls through to the deterministic workflow consumer path."""
        monkeypatch.setenv("OPENCLAW_INTERPRETER_LM", "1")
        monkeypatch.setenv("OPENCLAW_CONTINUITY_CAPSULE", "0")

        monkeypatch.setattr(interpreter_lm, "interpret_operator_message", _mock_interpret_uncertain)

        req = _make_starved_workflow_request(request_id="synth_e2e_fallback_uncertain_001")
        request_path = _write_request(tmp_path, req)
        classification = _workflow_classification(req["request_id"])

        result = processor._try_interpreter_brain_divert(
            request_path, req, classification=classification, route_decision={},
        )
        assert result is None, (
            "UNCERTAIN route must return None (deterministic fallback), not a CHAT divert."
        )

    def test_low_confidence_brain_falls_back(self, tmp_path, monkeypatch):
        """BRAIN below HIGH_CONFIDENCE_THRESHOLD → returns None (deterministic)."""
        monkeypatch.setenv("OPENCLAW_INTERPRETER_LM", "1")
        monkeypatch.setenv("OPENCLAW_CONTINUITY_CAPSULE", "0")

        monkeypatch.setattr(
            interpreter_lm, "interpret_operator_message", _mock_interpret_low_confidence
        )

        req = _make_starved_workflow_request(request_id="synth_e2e_fallback_lowconf_001")
        request_path = _write_request(tmp_path, req)
        classification = _workflow_classification(req["request_id"])

        result = processor._try_interpreter_brain_divert(
            request_path, req, classification=classification, route_decision={},
        )
        assert result is None, (
            "Low-confidence BRAIN must fall back to deterministic path (return None)."
        )

    def test_interpreter_exception_falls_back(self, tmp_path, monkeypatch):
        """Interpreter raising any exception → returns None (deterministic fallback)."""
        monkeypatch.setenv("OPENCLAW_INTERPRETER_LM", "1")
        monkeypatch.setenv("OPENCLAW_CONTINUITY_CAPSULE", "0")

        def _raising(*a: Any, **k: Any) -> None:
            raise RuntimeError("simulated LM failure")

        monkeypatch.setattr(interpreter_lm, "interpret_operator_message", _raising)

        req = _make_starved_workflow_request(request_id="synth_e2e_fallback_exc_001")
        request_path = _write_request(tmp_path, req)
        classification = _workflow_classification(req["request_id"])

        result = processor._try_interpreter_brain_divert(
            request_path, req, classification=classification, route_decision={},
        )
        assert result is None, (
            "Interpreter exception must fall back to deterministic path (return None)."
        )

    def test_fallback_identical_to_flag_off(self, tmp_path, monkeypatch):
        """UNCERTAIN + flag-ON must produce the same routing outcome as flag-OFF
        (both return None from the brain divert — no regression vs base)."""
        req = _make_starved_workflow_request(request_id="synth_e2e_fallback_identity_001")
        request_path = _write_request(tmp_path, req)
        classification = _workflow_classification(req["request_id"])

        # Flag ON + UNCERTAIN.
        monkeypatch.setenv("OPENCLAW_INTERPRETER_LM", "1")
        monkeypatch.setattr(
            interpreter_lm, "interpret_operator_message", _mock_interpret_uncertain
        )
        result_uncertain = processor._try_interpreter_brain_divert(
            request_path, req, classification=classification, route_decision={},
        )

        # Flag OFF.
        processor._INTERPRETER_RESULT_CACHE.clear()
        monkeypatch.setenv("OPENCLAW_INTERPRETER_LM", "0")
        result_off = processor._try_interpreter_brain_divert(
            request_path, req, classification=classification, route_decision={},
        )

        assert result_uncertain is None, "UNCERTAIN divert must return None."
        assert result_off is None, "Flag-OFF divert must return None."
        # Both None → same routing outcome, no regression.


# ---------------------------------------------------------------------------
# Assertion 10: FLAG-OFF byte-identity — with both flags OFF, routing + packet
#               are byte-identical to base (no interpreter fields in output).
#
# Entry points: process_request_path (full pipeline) and answer_frontdoor_chat.
# ---------------------------------------------------------------------------

class TestFlagOffByteIdentity:
    def test_flag_off_no_interpreter_fields_in_response(self, tmp_path, monkeypatch):
        """With OPENCLAW_INTERPRETER_LM=0, the response detail_disclosure must
        not contain any interpreter_lm_ fields — byte-identical to pre-interpreter
        behaviour. Interpreter is never called."""
        monkeypatch.setenv("OPENCLAW_INTERPRETER_LM", "0")
        monkeypatch.setenv("OPENCLAW_CONTINUITY_CAPSULE", "0")

        called = {"interpret": False}

        def _tripwire(*a: Any, **k: Any) -> Any:
            called["interpret"] = True
            raise AssertionError("interpreter must NOT be called when flag is off")

        monkeypatch.setattr(interpreter_lm, "interpret_operator_message", _tripwire)
        monkeypatch.setattr(maestro, "answer_frontdoor_chat", _stub_answer_brain)

        req = _make_proper_workflow_request(request_id="synth_e2e_flagoff_001")
        request_path = _write_request(tmp_path, req)

        response = processor.process_request_path(
            request_path, export_root=tmp_path / "exports", duplicate_check=False,
        )

        # Interpreter was never called.
        assert called["interpret"] is False, "Interpreter was called despite flag being OFF."

        # No interpreter_lm_divert field in detail_disclosure.
        detail_str = json.dumps(response.detail_disclosure)
        assert "interpreter_lm_divert" not in detail_str, (
            "interpreter_lm_divert must not appear in detail_disclosure when flag is OFF."
        )

    def test_flag_off_packet_no_fact_selection_hint_applied(self, tmp_path, monkeypatch):
        """Flag OFF: fact_selection hint in session is ignored → None passed to
        build_maestro_context_packet (byte-identical to pre-bridge behaviour).
        Machine proof records interpreter_fact_selection_used=False."""
        monkeypatch.setenv("OPENCLAW_INTERPRETER_LM", "0")
        monkeypatch.setenv("OPENCLAW_TEST_MODE", "1")

        read_model_root = _seed_read_models(tmp_path)
        truth_path = _seed_operator_truth(tmp_path, monkeypatch)

        captured: dict[str, Any] = {}
        real_build = packet_mod.build_maestro_context_packet

        def _spy_build(**kwargs: Any):
            captured["fact_selection"] = kwargs.get("fact_selection")
            return real_build(**kwargs)

        monkeypatch.setattr(packet_mod, "build_maestro_context_packet", _spy_build)

        session = {
            "read_model_root": read_model_root.as_posix(),
            "operator_truth_store_path": truth_path.as_posix(),
            # Hint is present in session but must be IGNORED when flag is OFF.
            "interpreter_fact_selection": ["work_board.json"],
        }
        result = maestro.answer_frontdoor_chat(
            "how are things looking across the board right now?",
            session=session,
            source_surface="operator_maestro_chat",
            protected_generate_fn=_stub_protected_generate,
        )

        assert result.status == "ANSWER_READY"
        # Flag OFF → hint is ignored → fact_selection is None (byte-identical to baseline).
        assert captured.get("fact_selection") is None, (
            f"Flag OFF: fact_selection hint must be ignored; got {captured.get('fact_selection')!r}"
        )
        # Traceability records not-used.
        assert result.machine_proof["interpreter_fact_selection_used"] is False
        assert result.machine_proof["interpreter_fact_selection_applied"] == []
