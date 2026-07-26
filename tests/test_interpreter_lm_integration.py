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
import workflow_package_queue as queue
import workflow_package_request_consumer as consumer
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
            "what needs the most attention on the reynolds gig prep?",
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
            "what needs the most attention on the reynolds gig prep?",
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


def _valid_workflow_request_for_text(text: str) -> dict[str, Any]:
    protected_hash = queue.protected_text_hash(text)
    return {
        "request_id": "shared_lm1_workflow_001",
        "source_request_id": "shared_lm1_workflow_001",
        "request_type": consumer.REQUEST_TYPE,
        "kind": consumer.REQUEST_KIND,
        "source_surface": "mission_control",
        "source_channel": "mission_control_chat",
        "requested_mode": "operator",
        "result_receipt_required": True,
        "world": "finance",
        "world_ref": "finance",
        "thread_ref": "st_annes",
        "active_surface_ref": "operator_maestro_chat",
        "operator_text": text,
        "source_text": text,
        "operator_message": text,
        "source_text_ref": "protected_text_hash:" + protected_hash,
        "protected_text_hash": protected_hash,
        "privacy_impact": "pending",
        "idempotency_key": "workflow_package_request:shared_lm1_workflow_001",
        "created_at": "2026-07-06T12:00:00+00:00",
        "authority_boundary": {key: False for key in consumer.AUTHORITY_FALSE_FIELDS},
        "mac_wrote_request_only": True,
        "no_external_action": True,
    }


class TestSharedLm1Seam:
    def test_interpreter_packet_minimizer_excludes_private_facts_and_rich_packet_text(self):
        packet = {
            "schema_version": "maestro_context_packet_v1",
            "packet_id": "packet:test",
            "source_surface": "operator_maestro_chat",
            "packet_text": "PRIVATE BODY MUST NOT CROSS THE ROUTER",
            "facts": [
                {
                    "fact_id": "public:1",
                    "topic": "system_status",
                    "label": "Public status",
                    "value": "The bounded service is online.",
                    "source_ref": "generated/read_models/agent_presence.json",
                    "provenance": "business_ledger_read_model",
                    "pii_tier": "PUBLIC",
                },
                {
                    "fact_id": "private:1",
                    "topic": "private_contact",
                    "label": "Private contact",
                    "value": "PRIVATE VALUE MUST NOT CROSS THE ROUTER",
                    "source_ref": "operator_truth/private.json",
                    "provenance": "business_ledger",
                    "pii_tier": "HIGH",
                },
            ],
            "source_refs": [
                "generated/read_models/agent_presence.json",
                "operator_truth/private.json",
            ],
        }

        minimized = processor._lm1_interpreter_context_packet(packet)

        serialized = json.dumps(minimized)
        assert minimized["source_packet_id"] == "packet:test"
        assert minimized["package_minimized"] is True
        assert minimized["facts"][0]["fact_id"] == "public:1"
        assert "The bounded service is online." in serialized
        assert "PRIVATE VALUE" not in serialized
        assert "PRIVATE BODY" not in serialized
        assert "operator_truth/private.json" not in serialized

    def test_shared_lm1_interpreter_receives_raw_message_and_preliminary_packet(
        self, tmp_path, monkeypatch
    ):
        monkeypatch.setenv("OPENCLAW_LM1_SHARED_SEAM", "1")
        monkeypatch.setenv("OPENCLAW_INTERPRETER_LM", "1")
        monkeypatch.setenv("OPENCLAW_TEST_MODE", "1")
        read_model_root = _seed_packet_read_models(tmp_path)
        truth_path = _seed_operator_truth(tmp_path, monkeypatch)
        monkeypatch.setattr(
            maestro,
            "session_from_request",
            lambda _r: {
                "read_model_root": read_model_root.as_posix(),
                "operator_truth_store_path": truth_path.as_posix(),
            },
        )
        observed: dict[str, Any] = {}

        def _mock_interpret(text, *, session=None, context_packet=None, **_kwargs):
            observed["text"] = text
            observed["packet"] = context_packet
            observed["session"] = dict(session or {})
            return interpreter_lm.InterpretResult(
                route=interpreter_lm.ROUTE_BRAIN,
                fact_selection=["agent_presence.json"],
                confidence=0.96,
                reason="agent status question",
            )

        monkeypatch.setattr(interpreter_lm, "interpret_operator_message", _mock_interpret)
        raw_message = "Niles: What are you doing with my exact mix note?!"

        seam = processor._build_lm1_shared_request_seam(
            _valid_workflow_request_for_text(raw_message),
            generated_at="2026-07-18T14:30:00+00:00",
        )

        assert observed["text"] == raw_message
        assert observed["packet"]["packet_id"]
        assert observed["packet"]["packet_text"]
        assert observed["packet"]["package_minimized"] is True
        assert observed["session"]["addressed_agent"] == "niles"
        assert "capital hilton" not in observed["packet"]["packet_text"].lower()
        assert "invoice" not in observed["packet"]["packet_text"].lower()
        assert observed["packet"]["machine_proof"]["source_question_relevance_scope"] in {
            "operator_specific",
            "relevance_unavailable",
        }
        assert seam["machine_proof"]["raw_operator_message_forwarded_verbatim"] is True
        assert seam["machine_proof"]["packet_aid_non_gating"] is True

    def test_shared_lm1_brain_route_scopes_general_guidance_at_packet_forge(
        self, tmp_path, monkeypatch
    ):
        monkeypatch.setenv("OPENCLAW_LM1_SHARED_SEAM", "1")
        monkeypatch.setenv("OPENCLAW_INTERPRETER_LM", "1")
        monkeypatch.setenv("OPENCLAW_TEST_MODE", "1")
        read_model_root = _seed_packet_read_models(tmp_path)
        truth_path = _seed_operator_truth(tmp_path, monkeypatch)
        monkeypatch.setattr(
            maestro,
            "session_from_request",
            lambda _r: {
                "read_model_root": read_model_root.as_posix(),
                "operator_truth_store_path": truth_path.as_posix(),
            },
        )

        monkeypatch.setattr(
            interpreter_lm,
            "interpret_operator_message",
            lambda *_args, **_kwargs: interpreter_lm.InterpretResult(
                route=interpreter_lm.ROUTE_BRAIN,
                fact_selection=[],
                confidence=0.99,
                reason="general resilience guidance",
            ),
        )

        question = "What are three practical ways to make a long-running workflow resilient?"
        seam = processor._build_lm1_shared_request_seam(
            _valid_workflow_request_for_text(question),
            generated_at="2026-07-15T23:59:00+00:00",
        )

        packet = seam["rich_context_packet"]
        assert seam["interpretation"]["route"] == "BRAIN"
        assert packet["machine_proof"]["question_relevance_scope"] == "general_guidance"
        assert {fact["topic"] for fact in packet["facts"]} == {"answer_scope"}
        assert "Capital Hilton" not in packet["packet_text"]

    def test_shared_lm1_seam_feeds_workflow_and_reuses_rich_brain_packet(
        self, tmp_path, monkeypatch
    ):
        """Fuzzy workflow text is interpreted once at the shared seam. The same
        rich packet is reused by the brain path, while workflow gets only the
        bounded authority-filtered packet and interpreted intent."""
        monkeypatch.setenv("OPENCLAW_LM1_SHARED_SEAM", "1")
        monkeypatch.setenv("OPENCLAW_INTERPRETER_LM", "1")
        monkeypatch.setenv("OPENCLAW_TEST_MODE", "1")
        read_model_root = _seed_packet_read_models(tmp_path)
        truth_path = _seed_operator_truth(tmp_path, monkeypatch)
        monkeypatch.setattr(
            maestro,
            "session_from_request",
            lambda _r: {
                "read_model_root": read_model_root.as_posix(),
                "operator_truth_store_path": truth_path.as_posix(),
            },
        )

        calls = {"interpret": 0, "read_models": 0}

        def _mock_interpret(
            text,
            *,
            session=None,
            context_packet=None,
            protected_generate_fn=None,
        ):
            calls["interpret"] += 1
            return interpreter_lm.InterpretResult(
                route=interpreter_lm.ROUTE_WORKFLOW,
                fact_selection=["work_board.json"],
                confidence=0.95,
                reason="fuzzy St Anne's invoice request",
                intent=interpreter_lm.INVOICE_SEND_INTENT,
                client="st-annes",
            )

        real_read_model_facts = packet_mod._read_model_facts

        def _spy_read_model_facts(root):
            calls["read_models"] += 1
            return real_read_model_facts(root)

        monkeypatch.setattr(interpreter_lm, "interpret_operator_message", _mock_interpret)
        monkeypatch.setattr(packet_mod, "_read_model_facts", _spy_read_model_facts)

        req = _valid_workflow_request_for_text("please handle that Draper treasurer invoice thread")
        seam = processor._build_lm1_shared_request_seam(req, generated_at="2026-07-06T12:01:00+00:00")

        assert seam["status"] == "READY"
        assert calls["interpret"] == 1
        assert calls["read_models"] == 2
        assert seam["interpretation"]["route"] == "WORKFLOW"
        assert seam["interpretation"]["intent"] == "invoice_send"
        assert seam["interpretation"]["client"] == "st-annes"
        assert seam["rich_context_packet"]["packet_id"]
        assert "packet_text" in seam["rich_context_packet"]
        assert "packet_text" not in seam["workflow_context_packet"]
        assert seam["workflow_context_packet"]["packet_id"] == seam["rich_context_packet"]["packet_id"]
        assert all(value is False for value in seam["workflow_context_packet"]["authority_boundary"].values())

        result = consumer.consume_workflow_package_request(
            req,
            source_request_filename="mission_control_operator_instruction_request_shared_lm1.json",
            generated_at="2026-07-06T12:02:00+00:00",
            sqlite_path=tmp_path / "workflow.sqlite",
            lm1_shared_seam=seam,
        )
        assert result.package is not None
        assert result.package["workflow_ref"] == "st_annes_monthly_invoice_rollup"
        assert result.package["intent_classification_result"]["intent_source"] == "lm1_shared_interpreter"
        assert result.package["lm1_shared_packet"]["authority_boundary"]["email_send_allowed"] is False
        assert result.receipt["machine_proof"]["lm1_shared_seam_used"] is True

        captured: dict[str, Any] = {}

        def _answer_stub(text, *, context_packet=None, **kwargs):
            captured["packet_id"] = (context_packet or {}).get("packet_id")
            return _stub_protected_generate(text, context_packet=context_packet, **kwargs)

        brain_session = {
            "read_model_root": read_model_root.as_posix(),
            "operator_truth_store_path": truth_path.as_posix(),
            "interpreter_fact_selection": ["work_board.json"],
            "lm1_shared_rich_context_packet": seam["rich_context_packet"],
        }
        brain = maestro.answer_frontdoor_chat(
            "where are we on that?",
            session=brain_session,
            source_surface="operator_maestro_chat",
            protected_generate_fn=_answer_stub,
        )
        assert brain.status == "ANSWER_READY"
        assert captured["packet_id"] == seam["rich_context_packet"]["packet_id"]
        assert calls["read_models"] == 2, "brain must reuse the seam packet, not rebuild it"

    def test_shared_lm1_seam_keeps_known_workflow_phrase_deterministic(self, tmp_path, monkeypatch):
        """Known phrases stay on the deterministic fast path. The shared seam may
        expose the deterministic interpretation, but it must not call interpreter_lm."""
        monkeypatch.setenv("OPENCLAW_LM1_SHARED_SEAM", "1")
        monkeypatch.setenv("OPENCLAW_INTERPRETER_LM", "1")
        monkeypatch.setenv("OPENCLAW_TEST_MODE", "1")
        read_model_root = _seed_packet_read_models(tmp_path)
        truth_path = _seed_operator_truth(tmp_path, monkeypatch)
        monkeypatch.setattr(
            maestro,
            "session_from_request",
            lambda _r: {
                "read_model_root": read_model_root.as_posix(),
                "operator_truth_store_path": truth_path.as_posix(),
            },
        )

        def _tripwire(*args, **kwargs):
            raise AssertionError("known workflow phrases must not call interpreter_lm")

        monkeypatch.setattr(interpreter_lm, "interpret_operator_message", _tripwire)

        seam = processor._build_lm1_shared_request_seam(
            _valid_workflow_request_for_text("Send St. Anne's invoice."),
            generated_at="2026-07-06T12:03:00+00:00",
        )

        assert seam["status"] == "READY"
        assert seam["interpretation"]["source"] == "deterministic_workflow_classifier"
        assert seam["interpretation"]["workflow_ref"] == "st_annes_monthly_invoice_rollup"
        assert seam["machine_proof"]["interpreter_lm_called"] is False


class TestStarvationBugFixedSynthetically:
    def test_deterministic_gate_fails_starved_request(self):
        """Sanity: the starved request fails the deterministic frontdoor gate."""
        req = _starved_workflow_request()
        assert processor._is_maestro_frontdoor_operator_instruction(req) is False

    def test_frontdoor_operator_instruction_threads_agent_to_brain(self, tmp_path, monkeypatch):
        """The deterministic front-door processor must preserve the requested agent
        persona instead of letting answer_frontdoor_chat default to Maestro."""
        captured: dict[str, Any] = {}

        def _stub_answer(text, *, session=None, source_surface="operator_maestro_chat", _capsule=None, agent="maestro", **kw):
            captured["agent"] = agent
            return maestro.MaestroCassandraResult(
                status="ANSWER_READY",
                intent_class="maestro_brain_freeform",
                allowed_to_call_handle=False,
                one_line_answer="Niles answer.",
                plain_summary="Niles answer.",
                machine_proof={"text_response_only": True, "email_send_performed": False},
            )

        monkeypatch.setattr(maestro, "answer_frontdoor_chat", _stub_answer)
        req = _starved_workflow_request()
        req["authority_boundary"] = {
            "email_send_allowed": False,
            "gmail_read_allowed": False,
            "browser_allowed": False,
            "coupa_allowed": False,
            "submit_allowed": False,
            "ledger_mutation_allowed": False,
            "payment_allowed": False,
            "merge_allowed": False,
            "push_allowed": False,
            "worker_execution_allowed": False,
        }
        req["agent_id"] = "niles"
        request_path = tmp_path / "req.json"
        request_path.write_text(json.dumps(req), encoding="utf-8")

        response = processor._process_maestro_frontdoor_operator_instruction(
            request_path,
            req,
            classification=_workflow_classification(),
            route_decision={},
            _capsule=None,
        )

        assert response is not None
        assert response.request_type == "CHAT"
        assert captured["agent"] == "niles"

    def test_flag_on_brain_divert_reaches_brain_not_workflow(self, tmp_path, monkeypatch):
        """Flag ON + interpreter mocked BRAIN high-conf → the starved message is
        diverted to the brain (CHAT response), NOT the workflow consumer."""
        monkeypatch.setenv("OPENCLAW_INTERPRETER_LM", "1")
        monkeypatch.setenv("OPENCLAW_TEST_MODE", "1")

        # Mock the interpreter so NO real LM runs.
        def _mock_interpret(text, *, session=None, context_packet=None, protected_generate_fn=None):
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

    def test_interpreter_brain_divert_threads_agent_to_brain(self, tmp_path, monkeypatch):
        """The interpreter divert is also a live brain route and must forward
        agent identity into the persona renderer."""
        monkeypatch.setenv("OPENCLAW_INTERPRETER_LM", "1")

        def _mock_interpret(text, *, session=None, context_packet=None, protected_generate_fn=None):
            return interpreter_lm.InterpretResult(
                route=interpreter_lm.ROUTE_BRAIN,
                fact_selection=[],
                confidence=0.95,
                reason="guardian advisory",
            )

        captured: dict[str, Any] = {}

        def _stub_answer(text, *, session=None, source_surface="operator_maestro_chat", _capsule=None, agent="maestro", **kw):
            captured["agent"] = agent
            return maestro.MaestroCassandraResult(
                status="ANSWER_READY",
                intent_class="maestro_brain_freeform",
                allowed_to_call_handle=False,
                one_line_answer="Guardian answer.",
                plain_summary="Guardian answer.",
                machine_proof={"text_response_only": True, "email_send_performed": False},
            )

        monkeypatch.setattr(interpreter_lm, "interpret_operator_message", _mock_interpret)
        monkeypatch.setattr(maestro, "answer_frontdoor_chat", _stub_answer)

        req = _starved_workflow_request()
        req["target_agent"] = "guardian"
        request_path = tmp_path / "req.json"
        request_path.write_text(json.dumps(req), encoding="utf-8")

        response = processor._try_interpreter_brain_divert(
            request_path,
            req,
            classification=_workflow_classification(),
            route_decision={},
            _capsule=None,
        )

        assert response is not None
        assert captured["agent"] == "guardian"

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

        def _counting_interpret(text, *, session=None, context_packet=None, protected_generate_fn=None):
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

        def _mock_interpret(text, *, session=None, context_packet=None, protected_generate_fn=None):
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

        def _mock_interpret(text, *, session=None, context_packet=None, protected_generate_fn=None):
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

        def _mock_interpret(text, *, session=None, context_packet=None, protected_generate_fn=None):
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

        def _mock_interpret(text, *, session=None, context_packet=None, protected_generate_fn=None):
            return interpreter_lm.InterpretResult(
                route=interpreter_lm.ROUTE_BRAIN, fact_selection=[], confidence=0.50, reason="unsure",
            )

        monkeypatch.setattr(interpreter_lm, "interpret_operator_message", _mock_interpret)
        response = self._run_divert(tmp_path)
        assert response is None, "low-confidence BRAIN must fall back to deterministic path"

    def test_uncertain_no_divert(self, tmp_path, monkeypatch):
        monkeypatch.setenv("OPENCLAW_INTERPRETER_LM", "1")

        def _mock_interpret(text, *, session=None, context_packet=None, protected_generate_fn=None):
            return interpreter_lm.InterpretResult(
                route=interpreter_lm.ROUTE_UNCERTAIN, fact_selection=[], confidence=0.99, reason="ambiguous",
            )

        monkeypatch.setattr(interpreter_lm, "interpret_operator_message", _mock_interpret)
        response = self._run_divert(tmp_path)
        assert response is None

    def test_interpreter_exception_no_divert(self, tmp_path, monkeypatch):
        monkeypatch.setenv("OPENCLAW_INTERPRETER_LM", "1")

        def _mock_interpret(text, *, session=None, context_packet=None, protected_generate_fn=None):
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

        def _real_interpret_with_garbage(text, *, session=None, context_packet=None, protected_generate_fn=None):
            return interpreter_lm.interpret_operator_message(text, protected_generate_fn=_garbage_fn)

        monkeypatch.setattr(interpreter_lm, "interpret_operator_message", _real_interpret_with_garbage)
        response = self._run_divert(tmp_path)
        assert response is None, "malformed LM output → UNCERTAIN → no divert"

    def test_brain_says_not_answer_ready_no_divert(self, tmp_path, monkeypatch):
        """Interpreter says BRAIN, but answer_frontdoor_chat returns non-ANSWER_READY
        → divert returns None (fall through to workflow)."""
        monkeypatch.setenv("OPENCLAW_INTERPRETER_LM", "1")

        def _mock_interpret(text, *, session=None, context_packet=None, protected_generate_fn=None):
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
        assert field_names == {
            "route",
            "fact_selection",
            "confidence",
            "reason",
            "intent",
            "client",
            "contact",
            "description",
            "date",
            "as_of",
            "scope",
            "partial",
            "needs_clarification",
            "what",
            "requesting_agent",
        }
        # No authority-adjacent attribute exists on a constructed result.
        result = interpreter_lm.InterpretResult(route="BRAIN", confidence=1.0, reason="x")
        for forbidden in ("authority", "allow", "send", "action", "deny", "authorize"):
            assert not hasattr(result, forbidden)


# ---------------------------------------------------------------------------
# 7. Messy-human canary — realistic rambling operator text through the REAL
#    dispatch → REAL answer_frontdoor_chat brain path → REAL context-packet build.
#
# This is the end-to-end proof the prior tests deliberately did NOT give:
#   - TestStarvationBugFixedSynthetically STUBS answer_frontdoor_chat, so it proves
#     ROUTING but never exercises the real brain / packet build.
#   - This class exercises the REAL brain path (build_maestro_context_packet runs on
#     seeded read-models + operator truth), mocking ONLY the two LM boundaries:
#       * the interpreter LM (classification JSON) — no real tokens
#       * the answering LM (protected_generate) — no real tokens / no model call
#   - It proves messy conversational text that the deterministic gate DECLINES (the
#     starvation case) reaches the brain as a CHAT response, fact-selection rides
#     along into the real packet, and ALL authority/send/ledger/action flags stay False.
# ---------------------------------------------------------------------------

# Controlled messy-human messages: lowercase, rambling, no clean punctuation — the
# kind that today get tagged WORKFLOW_PACKAGE_REQUEST_V0 and "saved for review".
_MESSY_HUMAN_MESSAGES = (
    "hey so uhh whats actually going on with everything right now are we good or is stuff on fire",
    "ok real talk where are we at with the board today what should i even be looking at",
)


def _messy_starved_request(text: str) -> dict:
    """Request shaped like the real listener's WORKFLOW_PACKAGE_REQUEST_V0 with NO
    authority_boundary → fails the deterministic frontdoor gate (the starvation case)."""
    return {
        "request_id": f"canary_{abs(hash(text)) % 10_000_000}",
        "source_request_id": f"canary_{abs(hash(text)) % 10_000_000}",
        "request_type": "WORKFLOW_PACKAGE_REQUEST_V0",
        "kind": "OPERATOR_INSTRUCTION_PACKAGE_REQUEST",
        "active_surface_ref": "operator_maestro_chat",
        "operator_text": text,
        "world_ref": "general",
        "current_world_ref": "general",
        "thread_ref": "operator_maestro_chat",
        "current_thread_ref": "operator_maestro_chat",
        # deliberately NO authority_boundary → deterministic gate declines
    }


def _answering_lm_stub(text, *, context_packet=None, **kwargs):
    """Stub for the ANSWERING LM (the SECOND LM). Returns a natural, conversational
    answer shape and records which packet topics it was handed — NO real model call.
    The wording-quality of a natural-vs-recited answer is the answering-LM's job and
    requires a live model to judge; this canary proves ROUTING + FACT RELEVANCE, which
    is what the interpreter controls."""
    facts = (context_packet or {}).get("facts", []) if isinstance(context_packet, dict) else []
    top_topics = [str(f.get("topic")) for f in facts[:6]]

    class _Outcome:
        def __init__(self):
            self.text = "Yeah we're good — nothing on fire. Here's the quick read."
            self.receipt = {
                "receipt_id": "canary_receipt",
                "decision": "INJECTED_CANARY_STUB",
                "external_llm_invoked": False,
                "local_model_invoked": False,
                "model_call_performed": False,
                "canary_packet_top_topics": top_topics,
            }

    return _Outcome()


class TestMessyHumanCanary:
    @pytest.mark.parametrize("messy_text", _MESSY_HUMAN_MESSAGES)
    def test_messy_human_reaches_brain_through_real_packet_path(
        self, messy_text, tmp_path, monkeypatch
    ):
        """Messy-human operator text (flag ON): deterministic gate declines →
        interpreter returns high-confidence BRAIN → real divert → REAL
        answer_frontdoor_chat → REAL build_maestro_context_packet → CHAT response,
        fact-selection carried, all authority/send/ledger/action flags False."""
        monkeypatch.setenv("OPENCLAW_INTERPRETER_LM", "1")
        monkeypatch.setenv("OPENCLAW_TEST_MODE", "1")  # blocks any accidental live model
        read_model_root = _seed_packet_read_models(tmp_path)
        truth_path = _seed_operator_truth(tmp_path, monkeypatch)

        # 1) The deterministic gate DECLINES this (the starvation case today).
        req = _messy_starved_request(messy_text)
        assert processor._is_maestro_frontdoor_operator_instruction(req) is False

        # 2) Mock ONLY the interpreter LM: classify the messy message as BRAIN.
        def _interpreter_stub(text, *, session=None, context_packet=None, protected_generate_fn=None):
            return interpreter_lm.InterpretResult(
                route=interpreter_lm.ROUTE_BRAIN,
                fact_selection=["work_board.json", "agent_presence.json"],
                confidence=0.93,
                reason="conversational status check, no action requested",
            )

        monkeypatch.setattr(interpreter_lm, "interpret_operator_message", _interpreter_stub)

        # The divert builds its session via session_from_request(req); seed it so the
        # REAL packet build finds the read-models + operator truth.
        seeded_session = {
            "read_model_root": read_model_root.as_posix(),
            "operator_truth_store_path": truth_path.as_posix(),
        }
        monkeypatch.setattr(
            maestro, "session_from_request", lambda _r: dict(seeded_session)
        )

        # 3) Wrap answer_frontdoor_chat to inject the answering-LM stub while keeping
        # the REAL routing + REAL packet build path intact (no real tokens).
        real_answer = maestro.answer_frontdoor_chat

        def _answer_with_stub(t, **kw):
            kw["protected_generate_fn"] = _answering_lm_stub
            return real_answer(t, **kw)

        monkeypatch.setattr(maestro, "answer_frontdoor_chat", _answer_with_stub)

        # 4) Drive the REAL divert.
        request_path = tmp_path / "req.json"
        request_path.write_text(json.dumps(req), encoding="utf-8")
        response = processor._try_interpreter_brain_divert(
            request_path, req, classification=_workflow_classification(),
            route_decision={}, _capsule=None,
        )

        # 5) Reached the brain as a CHAT response (NOT the workflow consumer).
        assert response is not None, "messy-human message must be diverted to the brain"
        assert response.request_type == "CHAT"
        assert response.internal_status == "RESPONSE_READY"
        # A conversational answer shell came back (not a save-for-review receipt).
        assert response.operator_headline
        assert "Saved for" not in (response.operator_message or "")

        detail = response.detail_disclosure
        # Interpreter routing recorded in the proof.
        proof = detail["dynamic_card_response"]["proof"]["machine_proof"]
        assert proof["interpreter_lm_divert"] is True
        assert proof["interpreter_route"] == "BRAIN"
        assert proof["interpreter_confidence"] == 0.93

        # The REAL brain path ran build_maestro_context_packet and carried fact selection.
        responder = detail["maestro_cassandra_responder"]
        brain_proof = responder["machine_proof"]
        assert brain_proof["maestro_context_packet_used"] is True
        assert brain_proof["interpreter_fact_selection_used"] is True
        assert brain_proof["interpreter_fact_selection_applied"] == [
            "work_board.json", "agent_presence.json"
        ]
        # The answering LM was the mock (no real/external model).
        assert brain_proof["external_llm_invoked"] is False

        # 6) Authority / send / ledger / action ALL locked False end-to-end.
        for locked in (
            "email_send_performed",
            "gmail_access_performed",
            "telegram_send_triggered",
            "business_action_performed",
            "ledger_mutation_performed",
            "workbook_mutation_performed",
            "paid_marking_performed",
        ):
            assert detail[locked] is False, f"{locked} must remain False"
        assert detail["external_actions_locked"] is True

    def test_messy_human_starved_today_without_flag(self, tmp_path, monkeypatch):
        """Sanity / no-regression: with the flag OFF, the SAME messy message is NOT
        diverted (returns None → falls through to the deterministic workflow path).
        Proves the canary behavior is strictly flag-gated."""
        monkeypatch.setenv("OPENCLAW_INTERPRETER_LM", "0")

        tripwire = {"interpret_called": False}

        def _tripwire(*a, **k):
            tripwire["interpret_called"] = True
            raise AssertionError("interpreter must not run when flag is off")

        monkeypatch.setattr(interpreter_lm, "interpret_operator_message", _tripwire)

        req = _messy_starved_request(_MESSY_HUMAN_MESSAGES[0])
        request_path = tmp_path / "req.json"
        request_path.write_text(json.dumps(req), encoding="utf-8")
        response = processor._try_interpreter_brain_divert(
            request_path, req, classification=_workflow_classification(),
            route_decision={}, _capsule=None,
        )
        assert response is None
        assert tripwire["interpret_called"] is False
