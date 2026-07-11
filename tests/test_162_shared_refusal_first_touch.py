from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import sqlite3
import sys
import types
from pathlib import Path

import pytest

import first_touch_decision as first_touch
import openclaw_request_processor as processor
import operator_refusal_guard as guard
import typed_contract_decision as typed_contract
import workflow_package_queue as queue
import workflow_package_request_consumer as consumer


FIXED_NOW = "2026-07-11T22:30:00+00:00"


class _MustNotReach(AssertionError):
    pass


def _request_payload(*, request_id: str, text: str, agent: str) -> dict:
    protected_hash = queue.protected_text_hash(text)
    payload = {
        "schema_version": "operator_instruction_writer_v0",
        "request_id": request_id,
        "source_request_id": request_id,
        "request_type": consumer.REQUEST_TYPE,
        "kind": consumer.REQUEST_KIND,
        "active_surface_ref": "operator_maestro_chat",
        "target_agent": agent,
        "source_surface": "mission_control",
        "source_channel": "mission_control_chat",
        "requested_mode": "operator",
        "result_receipt_required": True,
        "world": "operations",
        "world_ref": "operations",
        "thread_ref": f"operator_{agent}_chat",
        "source_text": text,
        "operator_text": text,
        "operator_message": text,
        "source_text_ref": "protected_text_hash:" + protected_hash,
        "protected_text_hash": protected_hash,
        "privacy_impact": "pending",
        "idempotency_key": f"workflow_package_request:{request_id}",
        "created_at": FIXED_NOW,
        "authority_boundary": {key: False for key in consumer.AUTHORITY_FALSE_FIELDS},
        "mac_wrote_request_only": True,
        "no_external_action": True,
    }
    payload["payload_hash"] = "sha256:" + processor._short_hash(payload)
    return payload


def _write_request(tmp_path: Path, *, request_id: str, text: str, agent: str) -> Path:
    path = tmp_path / f"mission_control_operator_instruction_request_{request_id}.json"
    path.write_text(
        json.dumps(_request_payload(request_id=request_id, text=text, agent=agent), indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )
    return path


def _seed_empty_queue(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as connection:
        connection.executescript(queue.sqlite_schema_sql())


def _queue_counts(path: Path) -> dict[str, int]:
    with sqlite3.connect(path) as connection:
        tables = [
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
            )
        ]
        return {
            table: int(connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0])
            for table in tables
        }


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _forbid_downstream(monkeypatch) -> None:
    def _boom(*_args, **_kwargs):
        raise _MustNotReach("downstream admission, model, interpreter, or workflow save ran")

    for name in (
        "_process_maestro_frontdoor_operator_instruction",
        "_build_lm1_shared_request_seam",
        "_try_interpreter_brain_divert",
        "_try_interpreter_action_blocked_divert",
    ):
        monkeypatch.setattr(processor, name, _boom)
    monkeypatch.setattr(
        processor.workflow_package_request_consumer,
        "consume_workflow_package_request",
        _boom,
    )
    monkeypatch.setattr(queue, "create_package", _boom)
    monkeypatch.setattr(queue, "record_package", _boom)


def _run_refusal(
    tmp_path: Path,
    monkeypatch,
    *,
    request_id: str,
    text: str,
    agent: str,
):
    queue_path = tmp_path / "workflow-package-queue.sqlite"
    receipt_path = tmp_path / "operator-refusal-receipts.jsonl"
    _seed_empty_queue(queue_path)
    before_hash = _sha256(queue_path)
    before_counts = _queue_counts(queue_path)
    request_path = _write_request(
        tmp_path,
        request_id=request_id,
        text=text,
        agent=agent,
    )
    monkeypatch.setenv(consumer.SQLITE_PATH_ENV, str(queue_path))
    monkeypatch.setenv(guard.RECEIPT_PATH_ENV, str(receipt_path))
    monkeypatch.setenv("OPENCLAW_INTERPRETER_LM", "1")
    monkeypatch.setenv("OPENCLAW_LM1_SHARED_SEAM", "1")
    monkeypatch.setenv("OPENCLAW_CONTINUITY_CAPSULE", "0")
    _forbid_downstream(monkeypatch)
    real_decide_first_touch = first_touch.attempt_first_touch
    first_touch_calls = 0

    def _counted_first_touch(*args, **kwargs):
        nonlocal first_touch_calls
        first_touch_calls += 1
        return real_decide_first_touch(*args, **kwargs)

    monkeypatch.setattr(
        processor.first_touch_decision,
        "attempt_first_touch",
        _counted_first_touch,
    )

    response = processor.process_request_path(
        request_path,
        export_root=tmp_path / "read-models",
        generated_at=FIXED_NOW,
        duplicate_check=False,
    )

    assert first_touch_calls == 1
    assert _sha256(queue_path) == before_hash
    assert _queue_counts(queue_path) == before_counts
    assert response.request_type == "CHAT"
    assert response.internal_status == "RESPONSE_READY"
    assert response.detail_disclosure["first_touch_decision"]["handled"] is True
    first_touch_receipt = response.detail_disclosure["first_touch_decision"]
    typed_receipt = response.detail_disclosure["typed_contract_decision"]
    assert typed_receipt["label"] == "refusal"
    assert typed_receipt["source"] == "first_touch"
    assert typed_receipt["receipt_pointer"] == first_touch_receipt["decision_id"]
    assert response.proof_to_response["typed_contract_decision"] == typed_receipt
    assert response.proof_to_response["first_touch_decision"] == first_touch_receipt
    assert first_touch_receipt["queue_sqlite_mutated"] is False
    assert first_touch_receipt["business_or_domain_store_write_performed"] is False
    assert first_touch_receipt["session_state_mutated"] is False
    assert first_touch_receipt["model_call_performed"] is False
    assert first_touch_receipt["worker_dispatch_performed"] is False
    assert first_touch_receipt["external_action_performed"] is False
    assert first_touch_receipt["refusal_receipt_append_performed"] is True
    assert first_touch_receipt["file_mutation_performed"] is True
    assert text not in json.dumps(first_touch_receipt, sort_keys=True)

    logged = [
        json.loads(line)
        for line in receipt_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert logged == [first_touch_receipt["guard_receipt"]]
    assert text not in receipt_path.read_text(encoding="utf-8")

    final_payload, _ = processor.build_payloads(response, generated_at=FIXED_NOW)
    assert final_payload["response_author"] == agent.upper()
    assert final_payload["agent_role"] == agent.upper()
    assert final_payload["high_risk_override_applied"] is False
    assert final_payload["operator_message"] == response.operator_message
    assert final_payload["guardian_output_gate"]["validation_result"]["output_publish_allowed"] is True
    assert final_payload["proof_to_response"]["first_touch_decision"] == first_touch_receipt
    assert final_payload["detail_disclosure"]["first_touch_decision"] == first_touch_receipt
    assert final_payload["proof_to_response"]["typed_contract_decision"] == typed_receipt
    assert final_payload["detail_disclosure"]["typed_contract_decision"] == typed_receipt
    assert final_payload["machine_proof"]["file_mutation_performed"] is True
    assert final_payload["machine_proof"]["business_state_mutation_performed"] is False
    return response, final_payload


@pytest.mark.parametrize(
    ("agent", "text", "must_contain"),
    (
        ("chief", "clear out all the old logs and branches, do it now", "Nothing was deleted"),
        ("niles", "factory reset the X32 and dump every scene", "Nothing was wiped"),
        ("chief", "delete the old logs and branches right now", "Nothing was deleted"),
        ("niles", "wipe the X32 and reset all the scenes", "Nothing was wiped"),
        (
            "chief",
            "clear out all the old logs and branches, then prepare the St Anne's invoice for my review",
            "Nothing was deleted",
        ),
    ),
)
def test_first_touch_refuses_before_every_downstream_and_preserves_owner(
    tmp_path, monkeypatch, agent, text, must_contain
):
    response, _ = _run_refusal(
        tmp_path,
        monkeypatch,
        request_id=f"first_touch_{agent}",
        text=text,
        agent=agent,
    )
    assert agent.capitalize() in response.operator_message
    assert "SEND_HOLD" in response.operator_message
    assert "deletion gate" in response.operator_message
    assert must_contain in response.operator_message


@pytest.mark.parametrize(
    "text",
    (
        "clear out all the old logs and branches, do it now",
        "please clear out every stale git branch now",
        "clear out the old log files",
        "clean out all stale logs and branches",
        "clearing out every branch and log right now",
        "clear all the old logs and branches out now",
        "clean every stale log file out before the next run",
        "purge the repository logs and old branches",
    ),
)
def test_clear_out_paraphrases_require_destructive_gate(text):
    decision = guard.evaluate_operator_refusal(text, agent="chief")
    assert decision is not None
    assert decision.reason_class == guard.REASON_DESTRUCTIVE
    if text.startswith(("clear all", "clean every")):
        assert decision.matched[0] in {"clear … out", "clean … out"}
        assert "logs" not in decision.matched[0]
        assert "branches" not in decision.matched[0]


@pytest.mark.parametrize(
    ("agent", "text"),
    (
        ("chief", "clear out that unsent draft"),
        ("chief", "clear out my unsent message draft"),
        ("chief", "clean my pending email draft out"),
        ("niles", "clean out the X32 scene"),
        ("chief", "clear out this test session"),
        ("niles", "factory reset the X32 scene"),
        ("chief", "can you clear up what the logs mean?"),
        ("chief", "show me the old logs and branches"),
        ("cassandra", "prepare the St Anne's invoice for my review"),
        (
            "maestro",
            "The file I just gave you is the actual workbook OpenClaw should use. Delete the other one from OpenClaw Capital Hilton invoice workflow request",
        ),
    ),
)
def test_clear_out_harmless_near_misses_remain_live(agent, text):
    assert guard.evaluate_operator_refusal(text, agent=agent) is None


@pytest.mark.parametrize(
    "text",
    (
        "clear out all messages now",
        "clean every email out before the next run",
        "clear what the logs mean and point out the important line",
    ),
)
def test_clear_out_bounds_do_not_hide_real_scope_or_capture_explanation(text):
    decision = guard.evaluate_operator_refusal(text, agent="chief")
    if "what the logs mean" in text:
        assert decision is None
    else:
        assert decision is not None
        assert decision.reason_class == guard.REASON_DESTRUCTIVE


def test_separated_clear_out_receipt_does_not_store_object_bearing_phrase(tmp_path, monkeypatch):
    receipt_path = tmp_path / "refusal-receipts.jsonl"
    monkeypatch.setenv(guard.RECEIPT_PATH_ENV, str(receipt_path))
    text = "clear all the old logs and branches out now"

    decision = first_touch.decide_first_touch(
        text,
        agent="chief",
        surface="chief_listener",
    )

    assert decision is not None
    logged = receipt_path.read_text(encoding="utf-8")
    assert "clear all the old logs and branches out" not in logged
    assert decision.receipt["guard_receipt"]["matched"] == [
        "clear … out",
        "logs",
    ]


def test_refusal_still_holds_and_reports_failed_audit_append(monkeypatch):
    monkeypatch.setattr(
        guard,
        "log_refusal_receipt",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("private path")),
    )

    decision = first_touch.decide_first_touch(
        "delete the old logs and branches right now",
        agent="chief",
        surface="mission_control",
    )

    assert decision is not None
    assert decision.handled is True
    assert decision.receipt["refusal_receipt_append_performed"] is False
    assert decision.receipt["refusal_receipt_persistence_status"] == "append_failed"
    assert "private path" not in json.dumps(decision.receipt, sort_keys=True)


def test_local_workbook_reference_retirement_does_not_mask_second_destructive_ask():
    decision = guard.evaluate_operator_refusal(
        "Use this workbook, delete the other one from OpenClaw, then wipe the invoice database",
        agent="maestro",
    )
    assert decision is not None
    assert decision.reason_class == guard.REASON_DESTRUCTIVE

    shared_verb = guard.evaluate_operator_refusal(
        "Use this workbook, delete the other one from OpenClaw and the invoice database",
        agent="maestro",
    )
    assert shared_verb is not None
    assert shared_verb.reason_class == guard.REASON_DESTRUCTIVE


def test_legitimate_workflow_reaches_normal_admission(tmp_path, monkeypatch):
    request_path = _write_request(
        tmp_path,
        request_id="legitimate_workflow",
        text="prepare the St Anne's invoice for my review",
        agent="cassandra",
    )
    monkeypatch.setenv("OPENCLAW_CONTINUITY_CAPSULE", "0")

    def _normal_admission(*_args, **_kwargs):
        raise _MustNotReach("normal admission reached")

    monkeypatch.setattr(processor, "_process_maestro_frontdoor_operator_instruction", _normal_admission)
    with pytest.raises(_MustNotReach, match="normal admission reached"):
        processor.process_request_path(
            request_path,
            export_root=tmp_path / "read-models",
            generated_at=FIXED_NOW,
            duplicate_check=False,
        )


@dataclass(frozen=True)
class _FakeCapsule:
    recent_messages: tuple = ()
    last_interaction_at: str = ""


def _first_touch_response() -> processor.OpenClawResponseForMac:
    receipt = {"handled": True, "label": "refusal", "action": "refuse"}
    classification = processor.RequestClassification(
        classification_id="first-touch-test",
        source_request_filename="request.json",
        request_family="WORKFLOW_PACKAGE_REQUEST",
        selected_rail="workflow_package_request_consumer",
        classification_reason="test",
        future_supported=False,
        next_safe_move="test",
    )
    return processor.OpenClawResponseForMac(
        source_request_id="request:first-touch",
        source_request_filename="request.json",
        workflow_ref="first_touch_refusal",
        request_type="CHAT",
        internal_status="RESPONSE_READY",
        operator_headline="Chief held the request",
        operator_message="Chief refused safely. Nothing was deleted. SEND_HOLD remains in force.",
        what_happened=("First touch refused the request.",),
        why_it_happened="Guardian deletion gate",
        how_to_fix="Use the reviewed deletion path.",
        visible_cards=({"title": "Refused", "bullets": ("Nothing changed.",)},),
        cards_available=True,
        card_mirror_refs=(),
        file_readback_refs=(),
        worker_route_refs=(),
        context_package_refs=(),
        blocked_reason=None,
        detail_disclosure={
            "first_touch_decision": receipt,
            "request_classification": {
                field: getattr(classification, field)
                for field in classification.__dataclass_fields__
            },
        },
        readback_files=(),
        next_safe_move="Use the reviewed deletion path.",
        proof_to_response={"first_touch_decision": receipt},
    )


def test_first_touch_refusal_skips_continuity_store_write(tmp_path, monkeypatch):
    request_path = tmp_path / "request.json"
    request_path.write_text(
        json.dumps(
            {
                "request_id": "request:first-touch",
                "conversation_id": "conversation:first-touch",
                "source_channel": "mission_control_chat",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    calls = {"loads": 0, "writes": 0}

    class _Store:
        def __init__(self, _root):
            pass

        def load(self, *_args):
            calls["loads"] += 1
            return _FakeCapsule()

        def write(self, *_args):
            calls["writes"] += 1

    fake_module = types.SimpleNamespace(
        ConversationCapsuleStore=_Store,
        Capsule=types.SimpleNamespace(cold_start=lambda **_kwargs: _FakeCapsule()),
    )
    monkeypatch.setitem(sys.modules, "conversation_capsule", fake_module)
    monkeypatch.setattr(processor, "_continuity_enabled", lambda: True)
    monkeypatch.setattr(processor, "_process_request_path_core", lambda *_args, **_kwargs: _first_touch_response())
    monkeypatch.setattr(processor, "_enrich_operator_surface", lambda response, *_args: response)

    response = processor.process_request_path(request_path, export_root=tmp_path / "read-models")

    assert response.detail_disclosure["first_touch_decision"]["handled"] is True
    assert calls == {"loads": 1, "writes": 0}


def test_pass_through_is_an_explicit_cached_outcome():
    outcome = first_touch.attempt_first_touch(
        "what is your status?",
        agent="chief",
        surface="chief_listener",
    )

    assert outcome is not None
    assert outcome.handled is False
    assert outcome.receipt["action"] == "continue"
    assert outcome.receipt["attempted"] is True
    assert outcome.receipt["handled"] is False
    assert outcome.receipt["guard_evaluation_status"] == "evaluated"
    assert outcome.receipt["file_mutation_performed"] is False


def test_typed_contract_reuses_cached_first_touch_without_second_refusal_tap(monkeypatch):
    outcome = first_touch.attempt_first_touch(
        "what is your status?",
        agent="chief",
        surface="chief_listener",
    )
    monkeypatch.setattr(
        typed_contract,
        "_refusal_reply",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            _MustNotReach("second refusal tap")
        ),
    )

    decision = typed_contract.decide_contract(
        "what is your status?",
        context=typed_contract.ContractContext(
            agent="chief",
            surface="chief_listener",
        ),
        status_renderer=lambda: "Chief status is ready.",
        first_touch_receipt=outcome.receipt,
    )

    assert decision.handled is True
    assert decision.label is typed_contract.ContractLabel.STATUS


def test_failed_first_touch_attempt_cannot_suppress_downstream_safety_retry(monkeypatch):
    monkeypatch.setattr(
        guard,
        "evaluate_operator_refusal",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("guard unavailable")),
    )
    outcome = first_touch.attempt_first_touch(
        "what is your status?",
        agent="chief",
        surface="chief_listener",
    )
    calls = 0

    def _retry(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        return None

    monkeypatch.setattr(typed_contract, "_refusal_reply", _retry)
    typed_contract.decide_contract(
        "what is your status?",
        context=typed_contract.ContractContext(agent="chief", surface="chief_router"),
        status_renderer=lambda: "Chief status is ready.",
        first_touch_receipt=outcome.receipt,
    )

    assert outcome.attempted is False
    assert outcome.receipt["guard_evaluation_status"] == "classification_error_fail_open"
    assert calls == 1


def test_address_prefix_rebind_preserves_one_evaluation_without_weakening_hash(monkeypatch):
    source = "Cassandra, what is your status?"
    target = "what is your status?"
    outcome = first_touch.attempt_first_touch(
        source,
        agent="cassandra",
        surface="cassandra_listener",
    )
    rebound = first_touch.rebind_pass_through_marker(
        outcome.receipt,
        source_text=source,
        target_text=target,
        agent="cassandra",
        surface="cassandra_brain.handle",
    )
    monkeypatch.setattr(
        typed_contract,
        "_refusal_reply",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            _MustNotReach("addressed text caused a second refusal tap")
        ),
    )

    decision = typed_contract.decide_contract(
        target,
        context=typed_contract.ContractContext(
            agent="cassandra",
            surface="cassandra_brain.handle",
        ),
        status_renderer=lambda: "Cassandra status is ready.",
        first_touch_receipt=rebound,
    )

    assert decision.label is typed_contract.ContractLabel.STATUS
    assert rebound is not None
    assert rebound["derived_from_decision_id"] == outcome.receipt["decision_id"]
    assert first_touch.rebind_pass_through_marker(
        outcome.receipt,
        source_text="forged different source",
        target_text=target,
        agent="cassandra",
        surface="cassandra_brain.handle",
    ) is None
