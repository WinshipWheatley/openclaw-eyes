"""Interpreter-LM Unit 2 — bridge + end-to-end integration proof.

Proves:
- fact_selection flows from the interpreter result THROUGH the real responder
  call chain (answer_frontdoor_chat → _answer_with_maestro_brain →
  build_maestro_context_packet), not only as a direct test parameter.
- Selected facts are ELEVATED; non-selected facts are NOT dropped/hidden/rewritten.
- Flag OFF: the session hint is ignored; behaviour is byte-identical.
- Flag ON, high-confidence BRAIN: a workflow-tagged operator message that the
  DETERMINISTIC gate would send to the workflow consumer ("saved for review")
  instead reaches the brain path — the synthetic starvation-bug fix.
- Flag ON, WORKFLOW route / low confidence / malformed / exception: safe fallback
  to the deterministic workflow path (divert returns None).
- Authority flags stay locked (no send, no ledger mutation, no external action).
- Machine proof records route, confidence, reason, fact selection, flag state,
  and whether an interpreter divert occurred.

ALL SYNTHETIC. NO real LM/token/network/action call. protected_generate is
always an injected mock or monkeypatched.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import interpreter_lm
import maestro_cassandra_responder as maestro
import maestro_context_packet as packet_mod
import openclaw_request_processor as processor
import operator_truth_store
from openclaw_request_processor import RequestClassification


@pytest.fixture(autouse=True)
def _clear_interpreter_cache():
    """The processor memoizes the interpreter result per-request (one LM call
    shared across the BRAIN and ACTION/BLOCKED diverts). Clear it before each
    test so a mocked classification never leaks across tests."""
    processor._INTERPRETER_RESULT_CACHE.clear()
    yield
    processor._INTERPRETER_RESULT_CACHE.clear()


def _workflow_classification() -> RequestClassification:
    """A minimal valid WORKFLOW_PACKAGE_REQUEST classification for the divert helper."""
    return RequestClassification(
        classification_id="interp_integration_classification",
        source_request_filename="req.json",
        request_family="WORKFLOW_PACKAGE_REQUEST",
        selected_rail="WORKFLOW_PACKAGE_REQUEST_CONSUMER",
        classification_reason="synthetic_integration_test",
        future_supported=True,
        next_safe_move="Review staged package.",
    )


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

# Read-models that build_maestro_context_packet looks for (need >= 2 present).
_PACKET_READ_MODELS = (
    "agent_presence.json",
    "work_board.json",
    "chief_status_rail.json",
)


def _seed_packet_read_models(tmp_path: Path) -> Path:
    """Copy a couple of real read-models so build_maestro_context_packet has
    >= 2 read-model refs and does not raise the require_real_truth guard."""
    root = tmp_path / "read_models"
    root.mkdir(parents=True, exist_ok=True)
    for name in _PACKET_READ_MODELS:
        src = ROOT / "generated/read_models" / name
        if src.exists():
            (root / name).write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    return root


def _seed_operator_truth(tmp_path: Path, monkeypatch) -> Path:
    store_path = tmp_path / "operator_truth_store.json"
    monkeypatch.setenv("OPENCLAW_OPERATOR_TRUTH_TEST_STORE", str(store_path))
    operator_truth_store.upsert_operator_truth(
        "capital_hilton",
        "Capital Hilton invoice was submitted and payment received for $2000.",
        source_surface="test",
        path=store_path,
    )
    return store_path


def _stub_protected_generate(text: str, *, context_packet: Any = None, **kwargs: Any):
    """Injected protected_generate stub — NO real LM. Returns a fixed answer
    plus a receipt with no external/model execution claimed."""
    class _Outcome:
        def __init__(self) -> None:
            self.text = "Synthetic grounded answer."
            self.receipt = {
                "receipt_id": "synthetic_receipt",
                "decision": "INJECTED_STUB",
                "external_llm_invoked": False,
                "local_model_invoked": False,
                "model_call_performed": False,
            }

    return _Outcome()


# ---------------------------------------------------------------------------
# 1. Bridge: fact_selection reaches build_maestro_context_packet through the
#    REAL responder call chain.
# ---------------------------------------------------------------------------

class TestFactSelectionBridge:
    def test_fact_selection_reaches_packet_builder_flag_on(self, tmp_path, monkeypatch):
        """Flag ON + interpreter_fact_selection in session → build_maestro_context_packet
        receives fact_selection through the real answer_frontdoor_chat chain."""
        monkeypatch.setenv("OPENCLAW_INTERPRETER_LM", "1")
        monkeypatch.setenv("OPENCLAW_TEST_MODE", "1")
        read_model_root = _seed_packet_read_models(tmp_path)
        truth_path = _seed_operator_truth(tmp_path, monkeypatch)

        captured: dict[str, Any] = {}
        real_build = packet_mod.build_maestro_context_packet

        def _spy_build(**kwargs):
            captured["fact_selection"] = kwargs.get("fact_selection")
            return real_build(**kwargs)

        monkeypatch.setattr(maestro, "build_maestro_context_packet", _spy_build, raising=False)
        # _answer_with_maestro_brain imports build_maestro_context_packet locally,
        # so patch the source module too.
        monkeypatch.setattr(packet_mod, "build_maestro_context_packet", _spy_build)

        session = {
            "read_model_root": read_model_root.as_posix(),
            "operator_truth_store_path": truth_path.as_posix(),
            "interpreter_fact_selection": ["work_board.json"],
        }
        result = maestro.answer_frontdoor_chat(
            "how are things looking across the board right now?",
            session=session,
            source_surface="operator_maestro_chat",
            protected_generate_fn=_stub_protected_generate,
        )

        assert result.status == "ANSWER_READY"
        assert result.intent_class == "maestro_brain_freeform"
        # The bridge forwarded the selection into the REAL packet builder:
        assert captured.get("fact_selection") == ["work_board.json"]
        # Traceability:
        assert result.machine_proof["interpreter_fact_selection_used"] is True
        assert result.machine_proof["interpreter_fact_selection_applied"] == ["work_board.json"]

    def test_fact_selection_ignored_when_flag_off(self, tmp_path, monkeypatch):
        """Flag OFF: same session hint is ignored → fact_selection is None,
        traceability records not-used. Byte-identical to pre-bridge behaviour."""
        monkeypatch.setenv("OPENCLAW_INTERPRETER_LM", "0")
        monkeypatch.setenv("OPENCLAW_TEST_MODE", "1")
        read_model_root = _seed_packet_read_models(tmp_path)
        truth_path = _seed_operator_truth(tmp_path, monkeypatch)

        captured: dict[str, Any] = {}
        real_build = packet_mod.build_maestro_context_packet

        def _spy_build(**kwargs):
            captured["fact_selection"] = kwargs.get("fact_selection")
            return real_build(**kwargs)

        monkeypatch.setattr(packet_mod, "build_maestro_context_packet", _spy_build)

        session = {
            "read_model_root": read_model_root.as_posix(),
            "operator_truth_store_path": truth_path.as_posix(),
            "interpreter_fact_selection": ["work_board.json"],
        }
        result = maestro.answer_frontdoor_chat(
            "how are things looking across the board right now?",
            session=session,
            source_surface="operator_maestro_chat",
            protected_generate_fn=_stub_protected_generate,
        )

        assert result.status == "ANSWER_READY"
        # Flag off → bridge never reads the hint → None passed to builder.
        assert captured.get("fact_selection") is None
        assert result.machine_proof["interpreter_fact_selection_used"] is False
        assert result.machine_proof["interpreter_fact_selection_applied"] == []


# ---------------------------------------------------------------------------
# 2. Elevation without deletion (real packet builder)
# ---------------------------------------------------------------------------

class TestElevationNotDeletion:
    def test_selected_fact_elevated_others_retained(self, tmp_path, monkeypatch):
        """fact_selection elevates the selected read-model's facts to the front
        but does NOT drop the non-selected facts."""
        monkeypatch.setenv("OPENCLAW_INTERPRETER_LM", "1")
        monkeypatch.setenv("OPENCLAW_TEST_MODE", "1")
        read_model_root = _seed_packet_read_models(tmp_path)
        truth_path = _seed_operator_truth(tmp_path, monkeypatch)

        # Baseline (no selection)
        baseline = packet_mod.build_maestro_context_packet(
            question="status across the board",
            read_model_root=read_model_root,
            operator_truth_store_path=truth_path,
            require_real_truth=True,
            fact_selection=None,
        )
        baseline_ids = {f["fact_id"] for f in baseline["facts"]}

        # With selection of work_board.json
        selected = packet_mod.build_maestro_context_packet(
            question="status across the board",
            read_model_root=read_model_root,
            operator_truth_store_path=truth_path,
            require_real_truth=True,
            fact_selection=["work_board.json"],
        )
        selected_ids = {f["fact_id"] for f in selected["facts"]}

        # No fact deleted — same set of facts, just reordered.
        assert baseline_ids == selected_ids, "fact selection must not drop facts"
        # work_board fact (if present) is now elevated toward the front.
        work_board_facts = [
            i for i, f in enumerate(selected["facts"])
            if "work_board.json" in (f.get("source_ref") or "")
        ]
        if work_board_facts:
            # the selected fact's index should be at or near the front
            assert min(work_board_facts) < len(selected["facts"]) // 2 or len(selected["facts"]) <= 2

    def test_selection_does_not_rewrite_fact_values(self, tmp_path, monkeypatch):
        """Selected facts keep their exact value/label — only order changes."""
        monkeypatch.setenv("OPENCLAW_INTERPRETER_LM", "1")
        monkeypatch.setenv("OPENCLAW_TEST_MODE", "1")
        read_model_root = _seed_packet_read_models(tmp_path)
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
            assert fact["value"] == base["value"], "fact value must not be rewritten"
            assert fact["label"] == base["label"], "fact label must not be rewritten"

    def test_operator_truth_stays_ahead_of_elevated_read_model(self, tmp_path, monkeypatch):
        """Elevation must NOT demote operator-truth facts below a selected
        read-model fact. operator_truth topic facts keep their precedence."""
        monkeypatch.setenv("OPENCLAW_INTERPRETER_LM", "1")
        monkeypatch.setenv("OPENCLAW_TEST_MODE", "1")
        read_model_root = _seed_packet_read_models(tmp_path)
        truth_path = _seed_operator_truth(tmp_path, monkeypatch)

        selected = packet_mod.build_maestro_context_packet(
            question="status across the board",
            read_model_root=read_model_root,
            operator_truth_store_path=truth_path,
            require_real_truth=True,
            fact_selection=["work_board.json"],
        )
        facts = selected["facts"]
        truth_indices = [i for i, f in enumerate(facts) if str(f.get("topic")) == "operator_truth"]
        rm_indices = [
            i for i, f in enumerate(facts)
            if str(f.get("provenance")) == "generated_read_model"
        ]
        if truth_indices and rm_indices:
            # Every operator-truth fact ranks ahead of every read-model fact,
            # including the elevated one. The precedence invariant holds.
            assert max(truth_indices) < min(rm_indices), (
                "operator-truth facts must stay ahead of elevated read-model facts"
            )


# ---------------------------------------------------------------------------
# 3. End-to-end starvation-bug fix via the processor divert
# ---------------------------------------------------------------------------

def _starved_workflow_request() -> dict[str, Any]:
    """A request that DETERMINISTICALLY fails _is_maestro_frontdoor_operator_instruction
    (no authority_boundary mapping) so it would fall through to the workflow
    consumer → 'saved for review'. This is the starvation case."""
    return {
        "request_id": "interp_integration_starved_001",
        "source_request_id": "interp_integration_starved_001",
        "request_type": "WORKFLOW_PACKAGE_REQUEST_V0",
        "kind": "OPERATOR_INSTRUCTION_PACKAGE_REQUEST",
        "active_surface_ref": "operator_maestro_chat",
        "operator_text": "how's the system feeling today, are we on track?",
        "world_ref": "general",
        "current_world_ref": "general",
        "thread_ref": "operator_maestro_chat",
        "current_thread_ref": "operator_maestro_chat",
        # NOTE: deliberately NO authority_boundary → deterministic gate fails.
    }


class TestStarvationBugFixedSynthetically:
    def test_deterministic_gate_fails_starved_request(self):
        """Sanity: the starved request fails the deterministic frontdoor gate."""
        req = _starved_workflow_request()
        assert processor._is_maestro_frontdoor_operator_instruction(req) is False

    def test_flag_on_brain_divert_reaches_brain_not_workflow(self, tmp_path, monkeypatch):
        """Flag ON + interpreter mocked BRAIN high-conf → the starved message is
        diverted to the brain (CHAT response), NOT the workflow consumer."""
        monkeypatch.setenv("OPENCLAW_INTERPRETER_LM", "1")
        monkeypatch.setenv("OPENCLAW_TEST_MODE", "1")

        # Mock the interpreter so NO real LM runs.
        def _mock_interpret(text, *, session=None, protected_generate_fn=None):
            return interpreter_lm.InterpretResult(
                route=interpreter_lm.ROUTE_BRAIN,
                fact_selection=["work_board.json"],
                confidence=0.95,
                reason="conversational status check",
            )

        monkeypatch.setattr(interpreter_lm, "interpret_operator_message", _mock_interpret)

        # Stub answer_frontdoor_chat so it returns an ANSWER_READY brain result
        # without a real LM/packet build (we're proving ROUTING here).
        def _stub_answer(text, *, session=None, source_surface="operator_maestro_chat", _capsule=None, **kw):
            # The divert injects interpreter_fact_selection into session — assert it arrived.
            assert isinstance(session, dict)
            assert session.get("interpreter_fact_selection") == ["work_board.json"]
            return maestro.MaestroCassandraResult(
                status="ANSWER_READY",
                intent_class="maestro_brain_freeform",
                allowed_to_call_handle=False,
                one_line_answer="On track.",
                plain_summary="On track.",
                machine_proof={"text_response_only": True, "email_send_performed": False},
            )

        monkeypatch.setattr(maestro, "answer_frontdoor_chat", _stub_answer)

        req = _starved_workflow_request()
        request_path = tmp_path / "req.json"
        request_path.write_text(json.dumps(req), encoding="utf-8")

        classification = _workflow_classification()

        response = processor._try_interpreter_brain_divert(
            request_path,
            req,
            classification=classification,
            route_decision={},
            _capsule=None,
        )

        # The divert fired → we reached the brain (CHAT response), not workflow.
        assert response is not None, "interpreter should divert the starved message to the brain"
        assert response.request_type == "CHAT"
        assert response.internal_status == "RESPONSE_READY"
        # Traceability:
        detail = response.detail_disclosure
        assert detail["maestro_frontdoor_routing"]["interpreter_lm_divert"] is True
        proof = detail["dynamic_card_response"]["proof"]["machine_proof"]
        assert proof["interpreter_lm_divert"] is True
        assert proof["interpreter_route"] == "BRAIN"
        assert proof["interpreter_confidence"] == 0.95
        assert proof["interpreter_reason"] == "conversational status check"
        assert proof["interpreter_fact_selection"] == ["work_board.json"]
        # Authority stays locked:
        assert detail["email_send_performed"] is False
        assert detail["gmail_access_performed"] is False
        assert detail["telegram_send_triggered"] is False
        assert detail["ledger_mutation_performed"] is False
        assert detail["workbook_mutation_performed"] is False
        assert detail["paid_marking_performed"] is False
        assert detail["business_action_performed"] is False
        assert detail["external_actions_locked"] is True

    def test_flag_off_no_divert_starved_request(self, tmp_path, monkeypatch):
        """Flag OFF → _try_interpreter_brain_divert returns None (deterministic
        workflow path preserved). Interpreter must NOT be called."""
        monkeypatch.setenv("OPENCLAW_INTERPRETER_LM", "0")

        called = {"interpret": False}

        def _tripwire(*a, **k):
            called["interpret"] = True
            raise AssertionError("interpreter must not be consulted when flag is off")

        monkeypatch.setattr(interpreter_lm, "interpret_operator_message", _tripwire)

        req = _starved_workflow_request()
        request_path = tmp_path / "req.json"
        request_path.write_text(json.dumps(req), encoding="utf-8")

        classification = _workflow_classification()

        response = processor._try_interpreter_brain_divert(
            request_path,
            req,
            classification=classification,
            route_decision={},
            _capsule=None,
        )

        assert response is None
        assert called["interpret"] is False

    def test_single_lm_call_shared_across_both_diverts(self, tmp_path, monkeypatch):
        """When the BRAIN divert declines and the ACTION/BLOCKED divert runs, the
        interpreter must be called EXACTLY ONCE for the request (memoized), not
        twice — otherwise two stochastic LM calls could disagree."""
        monkeypatch.setenv("OPENCLAW_INTERPRETER_LM", "1")

        calls = {"n": 0}

        def _counting_interpret(text, *, session=None, protected_generate_fn=None):
            calls["n"] += 1
            # WORKFLOW route → neither BRAIN nor ACTION/BLOCKED diverts fire,
            # so BOTH diverts are exercised end-to-end on the same request.
            return interpreter_lm.InterpretResult(
                route=interpreter_lm.ROUTE_WORKFLOW, fact_selection=[], confidence=0.99, reason="workflow",
            )

        monkeypatch.setattr(interpreter_lm, "interpret_operator_message", _counting_interpret)

        req = _starved_workflow_request()
        request_path = tmp_path / "req.json"
        request_path.write_text(json.dumps(req), encoding="utf-8")
        classification = _workflow_classification()

        brain = processor._try_interpreter_brain_divert(
            request_path, req, classification=classification, route_decision={}, _capsule=None,
        )
        action = processor._try_interpreter_action_blocked_divert(
            request_path, req, classification=classification, route_decision={}, _capsule=None,
        )

        assert brain is None
        assert action is None
        assert calls["n"] == 1, f"interpreter must be called exactly once, got {calls['n']}"


# ---------------------------------------------------------------------------
# 4. Flag ON: real workflow/package request still routes workflow
# ---------------------------------------------------------------------------

class TestWorkflowStillRoutesWorkflow:
    def test_workflow_route_no_divert(self, tmp_path, monkeypatch):
        """Interpreter mocked WORKFLOW → divert returns None → deterministic path."""
        monkeypatch.setenv("OPENCLAW_INTERPRETER_LM", "1")

        def _mock_interpret(text, *, session=None, protected_generate_fn=None):
            return interpreter_lm.InterpretResult(
                route=interpreter_lm.ROUTE_WORKFLOW,
                fact_selection=[],
                confidence=0.98,
                reason="explicit action request",
            )

        monkeypatch.setattr(interpreter_lm, "interpret_operator_message", _mock_interpret)

        req = _starved_workflow_request()
        req["operator_text"] = "submit the Capital Hilton invoice via Coupa now"
        request_path = tmp_path / "req.json"
        request_path.write_text(json.dumps(req), encoding="utf-8")

        classification = _workflow_classification()

        response = processor._try_interpreter_brain_divert(
            request_path, req, classification=classification, route_decision={}, _capsule=None,
        )
        assert response is None, "WORKFLOW route must NOT divert to the brain"


# ---------------------------------------------------------------------------
# 4b. Flag ON: ACTION route surfaces the gate verdict but locks all execution
# ---------------------------------------------------------------------------

class TestActionRouteAdvisoryOnly:
    def test_action_route_surfaces_gate_but_locks_all_actions(self, tmp_path, monkeypatch):
        """ACTION route → CHAT response that consults the authority gate for a
        verdict (gate decides, NOT the interpreter) and locks ALL execution flags
        — including telegram_send_triggered — to False. No executor is called."""
        monkeypatch.setenv("OPENCLAW_INTERPRETER_LM", "1")

        def _mock_interpret(text, *, session=None, protected_generate_fn=None):
            return interpreter_lm.InterpretResult(
                route=interpreter_lm.ROUTE_ACTION, fact_selection=[], confidence=0.95,
                reason="action proposal",
            )

        monkeypatch.setattr(interpreter_lm, "interpret_operator_message", _mock_interpret)

        req = _starved_workflow_request()
        req["operator_text"] = "mark the Capital Hilton invoice as paid"
        request_path = tmp_path / "req.json"
        request_path.write_text(json.dumps(req), encoding="utf-8")
        classification = _workflow_classification()

        response = processor._try_interpreter_action_blocked_divert(
            request_path, req, classification=classification, route_decision={}, _capsule=None,
        )

        assert response is not None, "ACTION route should produce an advisory response"
        assert response.request_type == "CHAT"
        detail = response.detail_disclosure
        # The interpreter only flags ACTION; the GATE decided the verdict.
        proposal = detail["interpreter_action_proposal"]
        assert proposal["authority_gate_consulted"] is True
        assert proposal["action_executed"] is False
        assert proposal["no_executor_called"] is True
        # The interpreter did NOT decide authority — its verdict came from the gate.
        # Whatever the gate returned, NO execution occurred and ALL flags are locked.
        for locked in (
            "email_send_performed",
            "gmail_access_performed",
            "telegram_send_triggered",
            "business_action_performed",
            "ledger_mutation_performed",
            "workbook_mutation_performed",
            "paid_marking_performed",
            "external_actions_locked",
        ):
            if locked == "external_actions_locked":
                assert detail[locked] is True
            else:
                assert detail[locked] is False, f"{locked} must be locked False in ACTION divert"

    def test_blocked_route_surfaces_block_locks_actions(self, tmp_path, monkeypatch):
        """BLOCKED route → CHAT response that surfaces the block and locks all
        execution flags (including telegram_send_triggered) to False."""
        monkeypatch.setenv("OPENCLAW_INTERPRETER_LM", "1")

        def _mock_interpret(text, *, session=None, protected_generate_fn=None):
            return interpreter_lm.InterpretResult(
                route=interpreter_lm.ROUTE_BLOCKED, fact_selection=[], confidence=0.95,
                reason="needs approval",
            )

        monkeypatch.setattr(interpreter_lm, "interpret_operator_message", _mock_interpret)

        req = _starved_workflow_request()
        request_path = tmp_path / "req.json"
        request_path.write_text(json.dumps(req), encoding="utf-8")
        classification = _workflow_classification()

        response = processor._try_interpreter_action_blocked_divert(
            request_path, req, classification=classification, route_decision={}, _capsule=None,
        )
        assert response is not None
        assert response.request_type == "CHAT"
        detail = response.detail_disclosure
        assert detail["telegram_send_triggered"] is False
        assert detail["email_send_performed"] is False
        assert detail["ledger_mutation_performed"] is False
        assert detail["external_actions_locked"] is True


# ---------------------------------------------------------------------------
# 5. Flag ON: low-confidence / malformed / exception fall back safely
# ---------------------------------------------------------------------------

class TestSafeFallbacks:
    def test_low_confidence_no_divert(self, tmp_path, monkeypatch):
        monkeypatch.setenv("OPENCLAW_INTERPRETER_LM", "1")

        def _mock_interpret(text, *, session=None, protected_generate_fn=None):
            return interpreter_lm.InterpretResult(
                route=interpreter_lm.ROUTE_BRAIN, fact_selection=[], confidence=0.50, reason="unsure",
            )

        monkeypatch.setattr(interpreter_lm, "interpret_operator_message", _mock_interpret)
        response = self._run_divert(tmp_path)
        assert response is None, "low-confidence BRAIN must fall back to deterministic path"

    def test_uncertain_no_divert(self, tmp_path, monkeypatch):
        monkeypatch.setenv("OPENCLAW_INTERPRETER_LM", "1")

        def _mock_interpret(text, *, session=None, protected_generate_fn=None):
            return interpreter_lm.InterpretResult(
                route=interpreter_lm.ROUTE_UNCERTAIN, fact_selection=[], confidence=0.99, reason="ambiguous",
            )

        monkeypatch.setattr(interpreter_lm, "interpret_operator_message", _mock_interpret)
        response = self._run_divert(tmp_path)
        assert response is None

    def test_interpreter_exception_no_divert(self, tmp_path, monkeypatch):
        monkeypatch.setenv("OPENCLAW_INTERPRETER_LM", "1")

        def _mock_interpret(text, *, session=None, protected_generate_fn=None):
            raise RuntimeError("simulated interpreter crash")

        monkeypatch.setattr(interpreter_lm, "interpret_operator_message", _mock_interpret)
        response = self._run_divert(tmp_path)
        assert response is None, "interpreter exception must fall back to deterministic path"

    def test_malformed_interpreter_result_no_divert(self, tmp_path, monkeypatch):
        """interpret_operator_message returns UNCERTAIN for malformed LM output
        (proven via the real parser with a garbage mock fn)."""
        monkeypatch.setenv("OPENCLAW_INTERPRETER_LM", "1")

        # Use the REAL interpret_operator_message but with a garbage-producing mock fn.
        def _garbage_fn(prompt, **kw):
            return "this is not json"

        def _real_interpret_with_garbage(text, *, session=None, protected_generate_fn=None):
            return interpreter_lm.interpret_operator_message(text, protected_generate_fn=_garbage_fn)

        monkeypatch.setattr(interpreter_lm, "interpret_operator_message", _real_interpret_with_garbage)
        response = self._run_divert(tmp_path)
        assert response is None, "malformed LM output → UNCERTAIN → no divert"

    def test_brain_says_not_answer_ready_no_divert(self, tmp_path, monkeypatch):
        """Interpreter says BRAIN, but answer_frontdoor_chat returns non-ANSWER_READY
        → divert returns None (fall through to workflow)."""
        monkeypatch.setenv("OPENCLAW_INTERPRETER_LM", "1")

        def _mock_interpret(text, *, session=None, protected_generate_fn=None):
            return interpreter_lm.InterpretResult(
                route=interpreter_lm.ROUTE_BRAIN, fact_selection=[], confidence=0.95, reason="conversational",
            )

        def _stub_answer(text, *, session=None, source_surface="operator_maestro_chat", _capsule=None, **kw):
            return maestro.MaestroCassandraResult(
                status="ROUTE_TO_STAGING",
                intent_class="send_reply_email_action",
                allowed_to_call_handle=False,
                route_to_staging_reason="action_intent_routes_to_staging",
            )

        monkeypatch.setattr(interpreter_lm, "interpret_operator_message", _mock_interpret)
        monkeypatch.setattr(maestro, "answer_frontdoor_chat", _stub_answer)
        response = self._run_divert(tmp_path)
        assert response is None, "brain non-ANSWER_READY → fall through to workflow"

    def _run_divert(self, tmp_path: Path):
        req = _starved_workflow_request()
        request_path = tmp_path / "req.json"
        request_path.write_text(json.dumps(req), encoding="utf-8")
        classification = _workflow_classification()
        return processor._try_interpreter_brain_divert(
            request_path, req, classification=classification, route_decision={}, _capsule=None,
        )


# ---------------------------------------------------------------------------
# 6. Authority stays locked through the real brain bridge
# ---------------------------------------------------------------------------

class TestAuthorityLockedThroughBridge:
    def test_brain_bridge_proof_locks_all_actions(self, tmp_path, monkeypatch):
        """The real brain bridge (with fact_selection) records all action flags
        as False and adds NO send/ledger/external-execution permission."""
        monkeypatch.setenv("OPENCLAW_INTERPRETER_LM", "1")
        monkeypatch.setenv("OPENCLAW_TEST_MODE", "1")
        read_model_root = _seed_packet_read_models(tmp_path)
        truth_path = _seed_operator_truth(tmp_path, monkeypatch)

        session = {
            "read_model_root": read_model_root.as_posix(),
            "operator_truth_store_path": truth_path.as_posix(),
            "interpreter_fact_selection": ["work_board.json"],
        }
        result = maestro.answer_frontdoor_chat(
            "how are things looking right now?",
            session=session,
            source_surface="operator_maestro_chat",
            protected_generate_fn=_stub_protected_generate,
        )
        proof = result.machine_proof
        for locked in (
            "email_send_performed",
            "telegram_send_triggered",
            "ledger_mutation_performed",
            "workbook_mutation_performed",
            "paid_marking_performed",
            "browser_access_performed",
            "coupa_access_performed",
            "runtime_execution_triggered",
            "send_authority_added",
            "agent_dispatch_performed",
            "worker_dispatch_performed",
        ):
            assert proof.get(locked) is False, f"{locked} must remain False through the bridge"
        assert proof.get("text_response_only") is True

    def test_authority_gate_not_consulted_by_interpreter(self):
        """Read-only assertion: interpreter_lm does not reference the authority gate;
        InterpretResult carries no authority field."""
        import dataclasses

        field_names = {f.name for f in dataclasses.fields(interpreter_lm.InterpretResult)}
        assert field_names == {"route", "fact_selection", "confidence", "reason"}
        # No authority-adjacent attribute exists on a constructed result.
        result = interpreter_lm.InterpretResult(route="BRAIN", confidence=1.0, reason="x")
        for forbidden in ("authority", "allow", "send", "action", "deny", "authorize"):
            assert not hasattr(result, forbidden)
