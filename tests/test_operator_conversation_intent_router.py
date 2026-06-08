import json
import shutil
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import first_class_operator_envelope as operator_authority
import operator_controller_event_router as controller_router
import operator_conversation_router as router
import proof_to_response_runtime as proof_runtime


FIXED_NOW = "2026-06-08T12:00:00+00:00"

FIXTURE_READ_MODELS = {
    "agent_response_voice_modes.json",
    "agentic_response_repair_gate_integration_plan.json",
    "capital_hilton_invoice_operator_run_status.json",
    "context_compaction_preview_policy.json",
    "context_freshness_decision_trace_gate.json",
    "dynamic_card_lifecycle_policy.json",
    "dynamic_card_packet_latest.json",
    "evidence_confidence_scoring.json",
    "evidence_intake_status.json",
    "first_class_operator_envelope_status.json",
    "gate_decision_ledger.json",
    "goldilocks_gate_calibration.json",
    "lm2_live_worker_pilot_boundary_packet.json",
    "lm2_room_backed_worker_structured_output_retry.json",
    "objective_advancement_protocol.json",
    "operator_action_payloads.json",
    "operator_controller_event_router_status.json",
    "operator_controller_protocol.json",
    "operator_session_timeline.json",
    "project_room_package_compiler_integration.json",
    "proof_bundle_freshness_trace_status.json",
    "proof_meter_normalization.json",
    "proof_to_response_lm_shadow_contract.json",
    "proof_to_response_lm_shadow_pilot.json",
    "proof_to_response_lm_shadow_status.json",
    "proof_to_response_runtime_status.json",
    "proof_to_response_tdd_spec.json",
    "retrospective_harness_learning_seed.json",
    "self_heal_repair_doctrine.json",
    "system_question_answer_contract.json",
    "universal_receipt_envelope_status.json",
    "workroom_review_decision_status.json",
}


def _seed_read_models(tmp_path: Path, *, include_lm2_retry: bool = False) -> Path:
    read_model_root = tmp_path / "read_models"
    read_model_root.mkdir(parents=True, exist_ok=True)
    for filename in sorted(FIXTURE_READ_MODELS):
        source = ROOT / "generated" / "read_models" / filename
        if source.exists():
            shutil.copy2(source, read_model_root / filename)
    if not include_lm2_retry:
        (read_model_root / "lm2_room_backed_worker_structured_output_retry.json").unlink(missing_ok=True)
    return read_model_root


def _request(text: str, **extra) -> dict:
    request = {
        "request_id": "operator_conversation_intent_router_test",
        "request_type": router.REQUEST_TYPE,
        "controller_event_type": "chat_goal",
        "operator_text": text,
        "current_world_ref": "finance",
        "current_thread_ref": "capital_hilton",
        "selected_card_id": "dynamic_card.finance.capital_hilton.payment_watch",
        "selected_action_id": "",
        "authority_boundary": dict(router.AUTHORITY_BOUNDARY),
        "authority_requested": [],
    }
    request.update(extra)
    return request


def _controller_request(text: str, *, suffix: str) -> dict:
    request = {
        "request_id": f"operator_conversation_intent_router_{suffix}",
        "request_type": controller_router.REQUEST_TYPE,
        "controller_event_type": "chat_goal",
        "controller_action_type": "chat_goal",
        "operator_text": text,
        "current_world_ref": "finance",
        "current_thread_ref": "capital_hilton",
        "selected_card_id": "dynamic_card.finance.capital_hilton.payment_watch",
        "selected_action_id": "",
        "active_entity_ref": "dynamic_card.finance.capital_hilton.payment_watch",
        "authority_boundary": dict(controller_router.AUTHORITY_BOUNDARY),
        "authority_requested": [],
    }
    return operator_authority.attach_verified_authority_envelope(
        request,
        operator_ref="operator:winship",
        app_instance_ref="mission_control:mac",
        device_ref="device:macbook",
        device_class="mac",
        session_ref=f"session:operator-conversation-intent-router:{suffix}",
        source_surface="card",
        current_world_ref="finance",
        current_thread_ref="capital_hilton",
        active_entity_ref="dynamic_card.finance.capital_hilton.payment_watch",
        controller_action_type="chat_goal",
        authority_requested=[],
        proof_refs=["controller_surface:mission_control", "test:operator_conversation_intent_router"],
        created_at=FIXED_NOW,
    )


def _route_text(tmp_path: Path, text: str) -> dict:
    return router.route_conversation_text(
        _request(text),
        read_model_root=_seed_read_models(tmp_path),
        sqlite_path=tmp_path / "proof_to_response.sqlite",
        generated_at=FIXED_NOW,
    )


def _route_controller(tmp_path: Path, text: str, *, include_lm2_retry: bool = False, suffix: str = "case") -> dict:
    return controller_router.route_controller_event(
        _controller_request(text, suffix=suffix),
        read_model_root=_seed_read_models(tmp_path, include_lm2_retry=include_lm2_retry),
        export_root=tmp_path / "read_models",
        bridge_root=tmp_path / "bridge",
        wiki_path=tmp_path / "wiki" / "Operator Controller Event Router.md",
        sqlite_path=tmp_path / "system_knowledge" / "operator_controller_event_router.sqlite",
        evidence_sqlite_path=tmp_path / "system_knowledge" / "evidence_intake.sqlite",
        artifact_lineage_sqlite_path=tmp_path / "system_knowledge" / "artifact_lineage_registry.sqlite",
        proof_to_response_sqlite_path=tmp_path / "system_knowledge" / "proof_to_response_runtime.sqlite",
        generated_at=FIXED_NOW,
    )


def _unsafe_true_grants(payload) -> list[str]:
    unsafe = set(router.UNSAFE_TRUE_KEYS) | set(controller_router.UNSAFE_TRUE_KEYS) | set(proof_runtime.UNSAFE_TRUE_KEYS)
    found: list[str] = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            if key in unsafe and value is True:
                found.append(key)
            found.extend(_unsafe_true_grants(value))
    elif isinstance(payload, list):
        for value in payload:
            found.extend(_unsafe_true_grants(value))
    return found


def test_payment_watch_next_step_returns_payment_watch_answer(tmp_path):
    result = _route_text(tmp_path, "What should I do here?")

    assert result["conversation_intent_class"] == "payment_watch_next_step"
    assert result["proof_to_response_scenario_id"] == "finance_capital_hilton_payment_watch"
    assert result["operator_display"]["headline"] == "Payment evidence needed"
    assert "ledger stays untouched" in result["operator_display"]["plain_summary"]
    assert result["operator_display"]["next_safe_action"] == "Attach payment evidence."


def test_paid_or_ledger_blocker_returns_blocker_explanation(tmp_path):
    result = _route_text(tmp_path, "Why can't this be marked paid?")
    text = json.dumps(result).lower()

    assert result["conversation_intent_class"] == "paid_or_ledger_blocker"
    assert "payment evidence" in text
    assert "mark this paid" in text
    assert "ledger" in text
    assert result["workflow_package_staged"] is False


def test_attach_proof_hypothetical_returns_proof_can_be_recorded(tmp_path):
    result = _route_text(tmp_path, "What happens if I attach proof?")
    display = result["operator_display"]

    assert result["conversation_intent_class"] == "attach_proof_hypothetical"
    assert result["proof_to_response_scenario_id"] == "finance_capital_hilton_attach_proof_explanation"
    assert display["headline"] == "Proof can be recorded"
    assert "candidate/payment-processing evidence" in display["plain_summary"]
    assert "will not mark this paid" in display["plain_summary"]
    assert "touch the ledger" in display["plain_summary"]


def test_handle_it_boundary_explains_safe_and_blocked_scope(tmp_path):
    result = _route_text(tmp_path, "Can you just handle it?")
    text = result["operator_display"]["plain_summary"].lower()

    assert result["conversation_intent_class"] == "handle_it_or_continue_boundary"
    assert "explain the status" in text
    assert "accept candidate payment evidence" in text
    assert "cannot mark paid" in text
    assert "submit" in text
    assert result["operator_display"]["next_safe_action"] == "Attach payment evidence."


def test_package_context_question_gets_human_package_explanation_not_generic_payment_watch(tmp_path):
    result = _route_text(tmp_path, "What package would LM2 get for this?")
    display = result["operator_display"]

    assert result["conversation_intent_class"] == "package_context_explanation"
    assert display["headline"] == "LM2 would get bounded context"
    assert "room-backed package" in display["plain_summary"]
    assert "redacted facts" in display["plain_summary"]
    assert "bank info" in display["plain_summary"]
    assert "Payment evidence needed" not in json.dumps(result)


def test_allowed_scope_question_gets_allowed_scope_answer(tmp_path):
    result = _route_text(tmp_path, "What are you allowed to do?")
    text = result["operator_display"]["plain_summary"].lower()

    assert result["conversation_intent_class"] == "allowed_scope_explanation"
    assert result["operator_display"]["headline"] == "Allowed: explain and collect proof"
    assert "explain" in text
    assert "accept candidate payment evidence" in text
    assert "does not grant protected action authority" in text


def test_forbidden_scope_question_gets_forbidden_scope_answer(tmp_path):
    result = _route_text(tmp_path, "What are you not allowed to do?")
    text = result["operator_display"]["plain_summary"].lower()

    assert result["conversation_intent_class"] == "forbidden_scope_explanation"
    assert result["operator_display"]["headline"] == "Protected actions stay blocked"
    assert "mark paid" in text
    assert "mutate the ledger" in text
    assert "open coupa/browser/gmail" in text
    assert "spawn a worker" in text


def test_freshness_question_gets_uncertainty_answer(tmp_path):
    result = _route_text(tmp_path, "What context is stale or uncertain?")
    text = result["operator_display"]["plain_summary"].lower()

    assert result["conversation_intent_class"] == "freshness_uncertainty_explanation"
    assert result["operator_display"]["headline"] == "Evidence is the uncertainty"
    assert "payment evidence is missing" in text
    assert "candidate evidence stays candidate" in text
    assert "stale context needs verification" in text


def test_decision_trace_question_gets_trace_answer(tmp_path):
    result = _route_text(tmp_path, "What has already been tried or decided here?")
    text = result["operator_display"]["plain_summary"].lower()

    assert result["conversation_intent_class"] == "decision_trace_explanation"
    assert result["operator_display"]["headline"] == "Payment watch is still active"
    assert "paid remains false" in text
    assert "ledger stays untouched" in text
    assert "fresh and scoped" in text


def test_controller_route_embeds_distinct_proof_response_for_package_question(tmp_path):
    receipt = _route_controller(
        tmp_path,
        "What package would LM2 get for this?",
        include_lm2_retry=True,
        suffix="package_context",
    )
    primary = receipt["proof_to_response"]

    assert receipt["route_result"]["conversation_intent_class"] == "package_context_explanation"
    assert primary["headline"] == "LM2 would get bounded context"
    assert "room-backed package" in primary["body"]
    assert primary["candidate_source"] != proof_runtime.CANDIDATE_SOURCE_LM2_ROOM_BACKED_STRUCTURED_RETRY
    assert receipt["machine_proof"]["lm2_proof_response_reused"] is False
    assert "WORKFLOW_PACKAGE_REQUEST_V0" not in json.dumps(receipt)


def test_controller_route_reuses_lm2_only_for_next_step_when_scoped(tmp_path):
    receipt = _route_controller(
        tmp_path,
        "What should I do here?",
        include_lm2_retry=True,
        suffix="next_step_lm2",
    )

    assert receipt["route_result"]["conversation_intent_class"] == "payment_watch_next_step"
    assert receipt["proof_to_response"]["headline"] == "Payment evidence needed"
    assert receipt["proof_to_response"]["candidate_source"] == proof_runtime.CANDIDATE_SOURCE_LM2_ROOM_BACKED_STRUCTURED_RETRY
    assert receipt["machine_proof"]["lm2_proof_response_reused"] is True
    assert receipt["machine_proof"]["model_invoked"] is False


def test_intent_router_status_exports_bridge_equality_and_no_grants(tmp_path):
    result = router.export_operator_conversation_intent_router(
        read_model_root=_seed_read_models(tmp_path),
        export_root=tmp_path / "read_models",
        bridge_root=tmp_path / "bridge",
        wiki_path=tmp_path / "wiki" / "Operator Conversation Intent Router.md",
        sqlite_path=tmp_path / "proof_to_response.sqlite",
        generated_at=FIXED_NOW,
    )

    assert result["status"] == router.INTENT_READY_STATUS
    local = json.loads(Path(result["status_path"]).read_text(encoding="utf-8"))
    bridge = json.loads(Path(result["bridge_status_path"]).read_text(encoding="utf-8"))
    assert local == bridge
    assert local["intent_classes"] == list(router.INTENT_CLASSES)
    assert local["machine_proof"]["workflow_package_request_v0_emitted"] is False
    assert not _unsafe_true_grants(local)


def test_unsafe_true_grant_scan_clean(tmp_path):
    samples = [
        _route_text(tmp_path, "What are you allowed to do?"),
        _route_text(tmp_path, "What are you not allowed to do?"),
        _route_controller(tmp_path, "What context is stale or uncertain?", suffix="freshness"),
        router.build_intent_router_status_read_model(
            read_model_root=_seed_read_models(tmp_path),
            sqlite_path=tmp_path / "proof_to_response.sqlite",
            generated_at=FIXED_NOW,
        ),
    ]

    for sample in samples:
        assert not _unsafe_true_grants(sample)
