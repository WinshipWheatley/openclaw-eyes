import json
import shutil
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import first_class_operator_envelope as operator_authority
import openclaw_request_processor as processor
import operator_controller_event_router as router
import proof_to_response_runtime as runtime


FIXED_NOW = "2026-06-06T20:00:00+00:00"

FIXTURE_READ_MODELS = {
    "agentic_response_repair_gate_integration_plan.json",
    "capital_hilton_business_development_proposal.json",
    "capital_hilton_invoice_operator_run_status.json",
    "controller_knob_mode_filters.json",
    "dynamic_card_lifecycle_policy.json",
    "dynamic_card_packet_latest.json",
    "evidence_intake_status.json",
    "first_class_operator_envelope_status.json",
    "gate_decision_ledger.json",
    "goldilocks_gate_calibration.json",
    "mac_thinning_readiness_map.json",
    "objective_advancement_protocol.json",
    "operator_action_payloads.json",
    "operator_controller_event_router_status.json",
    "operator_controller_protocol.json",
    "operator_session_timeline.json",
    "proof_meter_normalization.json",
    "proof_to_response_lm_shadow_contract.json",
    "proof_to_response_lm_shadow_pilot.json",
    "proof_to_response_lm_shadow_status.json",
    "proof_to_response_tdd_spec.json",
    "self_heal_repair_doctrine.json",
    "system_question_answer_contract.json",
    "universal_receipt_envelope_status.json",
    "workflow_package_request_consumer_status.json",
    "workroom_review_decision_status.json",
}


def _seed_read_models(tmp_path: Path) -> Path:
    root = tmp_path / "read_models"
    root.mkdir(parents=True, exist_ok=True)
    for filename in sorted(FIXTURE_READ_MODELS):
        shutil.copy2(ROOT / "generated" / "read_models" / filename, root / filename)
    return root


def _controller_event_request(
    *,
    event_type: str,
    world: str,
    thread: str,
    suffix: str,
    selected_card_id: str = "",
    selected_action_id: str = "",
    operator_text: str = "",
    artifact_ref: str = "",
    candidate: dict | None = None,
) -> dict:
    request = {
        "request_id": f"proof_to_response_controller_{suffix}",
        "request_type": router.REQUEST_TYPE,
        "source_surface": "mission_control",
        "controller_event_type": event_type,
        "controller_action_type": event_type,
        "current_world_ref": world,
        "current_thread_ref": thread,
        "active_entity_ref": selected_card_id,
        "selected_card_id": selected_card_id,
        "selected_action_id": selected_action_id,
        "operator_text": operator_text,
        "artifact_ref": artifact_ref,
        "authority_requested": [],
        "authority_boundary": dict(router.AUTHORITY_BOUNDARY),
    }
    if candidate is not None:
        request["proof_to_response_candidate"] = candidate
    request["operator_envelope"] = {
        "envelope_id": f"operator_envelope:proof_to_response:{suffix}",
        "operator_ref": "operator:winship",
        "app_instance_ref": "mission_control:mac",
        "device_ref": "device:macbook",
        "device_class": "mac",
        "session_ref": f"session:proof-to-response-controller:{suffix}",
        "request_hash": "",
        "created_at": FIXED_NOW,
        "source_surface": "dropzone" if event_type == "attach_proof" else "card",
        "current_world_ref": world,
        "current_thread_ref": thread,
        "active_entity_ref": selected_card_id,
        "controller_action_type": event_type,
        "authority_requested": [],
        "operator_verified": True,
        "app_instance_verified": True,
        "device_verified": True,
        "session_verified": True,
        "verification_status": operator_authority.VERIFICATION_STATUS_VERIFIED,
        "proof_refs": ["controller_surface:mission_control", "test:first_class_operator_envelope"],
    }
    request["operator_envelope"]["request_hash"] = operator_authority.compute_request_hash(request)
    return request


def _route(tmp_path: Path, request: dict) -> tuple[dict, dict, dict]:
    read_model_root = _seed_read_models(tmp_path)
    receipt = router.route_controller_event(
        request,
        source_request_filename=f"{request['request_id']}.json",
        read_model_root=read_model_root,
        export_root=read_model_root,
        bridge_root=tmp_path / "bridge",
        wiki_path=tmp_path / "wiki" / "Operator Controller Event Router.md",
        workroom_wiki_path=tmp_path / "wiki" / "Workroom Review Decision Consumer.md",
        sqlite_path=tmp_path / "system_knowledge" / "operator_controller_event_router.sqlite",
        evidence_sqlite_path=tmp_path / "system_knowledge" / "evidence_intake.sqlite",
        artifact_lineage_sqlite_path=tmp_path / "system_knowledge" / "artifact_lineage_registry.sqlite",
        proof_to_response_sqlite_path=tmp_path / "system_knowledge" / "proof_to_response_runtime.sqlite",
        generated_at=FIXED_NOW,
    )
    latest = json.loads((read_model_root / runtime.LATEST_JSON_EXPORT_NAME).read_text(encoding="utf-8"))
    bridge_latest = json.loads((tmp_path / "bridge" / runtime.LATEST_JSON_EXPORT_NAME).read_text(encoding="utf-8"))
    return receipt, latest, bridge_latest


def _candidate(read_model_root: Path, scenario_id: str, **overrides) -> dict:
    bundle = runtime.build_or_load_proof_bundle(scenario_id, read_model_root=read_model_root)
    candidate = runtime.fixture_candidate_response(bundle)
    candidate.update(overrides)
    return candidate


def _assert_primary_shape(response: dict) -> None:
    for field in (
        "response_id",
        "source_request_id",
        "controller_event_type",
        "world_ref",
        "thread_ref",
        "speaker_ref",
        "voice_mode",
        "headline",
        "body",
        "next_step",
        "missing_input",
        "can_do_now",
        "cannot_do_yet",
        "controls",
        "proof_meters",
        "proof_refs",
        "receipt_refs",
        "verification_status",
        "authority_boundary",
    ):
        assert field in response
    assert response["details_collapsed"] is True
    assert response["authority_boundary"]["protected_actions_allowed"] is False


def test_capital_hilton_ask_why_updates_proof_to_response_latest(tmp_path):
    receipt, latest, bridge_latest = _route(
        tmp_path,
        _controller_event_request(
            event_type="ask_why",
            world="finance",
            thread="capital_hilton",
            suffix="capital_hilton_ask_why",
            selected_card_id="dynamic_card.finance.capital_hilton.payment_watch",
            operator_text="Why am I here?",
        ),
    )

    primary = receipt["proof_to_response"]
    _assert_primary_shape(primary)
    assert latest == bridge_latest
    assert latest["source_request_id"] == receipt["request_id"]
    assert latest["world_ref"] == "finance"
    assert latest["thread_ref"] == "capital_hilton"
    assert latest["selected_card_id"] == "dynamic_card.finance.capital_hilton.payment_watch"
    assert latest["stale_if_context_mismatch"] is True
    assert latest["candidate_source"] == runtime.CANDIDATE_SOURCE_SHADOW_PILOT
    assert primary["candidate_source"] == runtime.CANDIDATE_SOURCE_SHADOW_PILOT
    assert latest["latest_response"]["headline"] == "Payment evidence needed"
    assert "payment evidence" in primary["body"].lower()
    assert "ledger stays untouched" in primary["body"].lower()
    assert primary["next_step"] == "Attach payment evidence."
    assert receipt["dynamic_card_role"] == "support_display"
    assert receipt["dynamic_card_response"]


def test_capital_hilton_ask_why_payment_watch_context_overrides_coupa_action_metadata(tmp_path):
    receipt, latest, _bridge_latest = _route(
        tmp_path,
        _controller_event_request(
            event_type="ask_why",
            world="finance",
            thread="capital_hilton",
            suffix="capital_hilton_lane_question_with_gate_metadata",
            selected_card_id="dynamic_card.finance.capital_hilton.payment_watch",
            selected_action_id="guardian_gate.coupa_submit.open",
            operator_text="Why did Submit Capital Hilton invoice block?",
        ),
    )

    primary = receipt["proof_to_response"]
    assert receipt["proof_to_response_scenario_id"] == "finance_capital_hilton_payment_watch"
    assert primary["headline"] == "Payment evidence needed"
    assert "Coupa is processing" in primary["body"]
    assert "payment evidence is attached" in primary["body"]
    assert primary["next_step"] == "Attach payment evidence."
    assert "Blocked until proof and approval" not in primary["headline"]
    assert latest["world_ref"] == "finance"
    assert latest["thread_ref"] == "capital_hilton"
    assert latest["latest_response"]["headline"] == "Payment evidence needed"


def test_capital_hilton_coupa_gate_ask_why_still_uses_gate_specific_response(tmp_path):
    receipt, latest, _bridge_latest = _route(
        tmp_path,
        _controller_event_request(
            event_type="ask_why",
            world="finance",
            thread="capital_hilton",
            suffix="capital_hilton_gate_question",
            selected_card_id="dynamic_card.finance.capital_hilton.approval_request.coupa_submit",
            selected_action_id="guardian_gate.coupa_submit.explain",
            operator_text="Why is this Coupa submit gate blocked?",
        ),
    )

    primary = receipt["proof_to_response"]
    assert receipt["proof_to_response_scenario_id"] == "protected_coupa_ledger_email_request"
    assert primary["speaker_ref"] == "guardian"
    assert primary["headline"] == "Blocked until proof and approval"
    assert latest["latest_response"]["headline"] == "Blocked until proof and approval"


def test_capital_hilton_advance_objective_updates_proof_to_response_latest(tmp_path):
    receipt, latest, _bridge_latest = _route(
        tmp_path,
        _controller_event_request(
            event_type="advance_objective",
            world="finance",
            thread="capital_hilton",
            suffix="capital_hilton_advance_objective",
            selected_card_id="dynamic_card.finance.capital_hilton.payment_watch",
            operator_text="Advance this.",
        ),
    )

    assert receipt["backend_route"] == "objective_advancement_protocol.advance_objective"
    assert receipt["route_status"] == "NEEDS_PROOF"
    assert receipt["proof_to_response"]["headline"] == "Payment evidence needed"
    assert latest["latest_response"]["headline"] == "Payment evidence needed"


def test_business_development_advance_objective_updates_proof_to_response_latest(tmp_path):
    receipt, latest, _bridge_latest = _route(
        tmp_path,
        _controller_event_request(
            event_type="advance_objective",
            world="business_development",
            thread="capital_hilton",
            suffix="business_development_advance",
            selected_card_id="dynamic_card.business_development.capital_hilton.proposal",
            operator_text="Advance the follow-up.",
        ),
    )

    primary = receipt["proof_to_response"]
    assert primary["headline"] == "Follow-up can be staged"
    assert "stage a follow-up draft" in primary["body"]
    assert "not send" in primary["body"]
    assert latest["world_ref"] == "business_development"
    assert latest["thread_ref"] == "capital_hilton"
    assert latest["source_request_id"] == receipt["request_id"]
    assert latest["latest_response"]["headline"] == "Follow-up can be staged"


def test_latest_moves_from_finance_to_business_development(tmp_path):
    finance_receipt, finance_latest, _finance_bridge = _route(
        tmp_path,
        _controller_event_request(
            event_type="ask_why",
            world="finance",
            thread="capital_hilton",
            suffix="sequential_finance",
            selected_card_id="dynamic_card.finance.capital_hilton.payment_watch",
            operator_text="Why am I here?",
        ),
    )
    business_receipt, business_latest, _business_bridge = _route(
        tmp_path,
        _controller_event_request(
            event_type="advance_objective",
            world="business_development",
            thread="capital_hilton",
            suffix="sequential_business_development",
            selected_card_id="dynamic_card.business_development.capital_hilton.proposal",
            operator_text="Advance the follow-up.",
        ),
    )

    assert finance_latest["world_ref"] == "finance"
    assert finance_latest["source_request_id"] == finance_receipt["request_id"]
    assert business_latest["world_ref"] == "business_development"
    assert business_latest["thread_ref"] == "capital_hilton"
    assert business_latest["source_request_id"] == business_receipt["request_id"]
    assert business_latest["latest_response"]["headline"] == "Follow-up can be staged"
    assert business_latest["latest_response"]["world_ref"] == "business_development"


def test_live_arts_evidence_intake_updates_candidate_not_paid_response(tmp_path):
    receipt, latest, _bridge_latest = _route(
        tmp_path,
        _controller_event_request(
            event_type="attach_proof",
            world="finance",
            thread="live_arts_md",
            suffix="live_arts_attach_proof",
            selected_card_id="dynamic_card.finance.live_arts_md.evidence_intake.payment_processing",
            operator_text="Payment processing screenshot.",
            artifact_ref="mission_control_drop:live_arts_md_payment_processing_screenshot",
        ),
    )

    primary = receipt["proof_to_response"]
    assert primary["headline"] == "Evidence recorded"
    assert "candidate payment-processing evidence" in primary["body"]
    assert "does not mark the invoice paid" in primary["body"]
    assert receipt["route_result"]["payment"]["paid"] is False
    assert latest["world_ref"] == "finance"
    assert latest["thread_ref"] == "live_arts_md"
    assert latest["latest_response"]["headline"] == "Evidence recorded"


def test_protected_coupa_ledger_email_request_gets_guardian_block(tmp_path):
    receipt, latest, _bridge_latest = _route(
        tmp_path,
        _controller_event_request(
            event_type="do_it",
            world="finance",
            thread="capital_hilton",
            suffix="protected_coupa",
            selected_card_id="dynamic_card.finance.capital_hilton.payment_watch",
            operator_text="Submit this in Coupa and email the update.",
        ),
    )

    primary = receipt["proof_to_response"]
    assert primary["speaker_ref"] == "guardian"
    assert primary["headline"] == "Blocked until proof and approval"
    assert "blocked until proof and approval" in primary["body"]
    assert primary["verification_status"] == "publishable"
    assert receipt["route_status"] == "PROTECTED_ACTION_STAGED_OR_BLOCKED"
    assert latest["latest_response"]["headline"] == "Blocked until proof and approval"
    assert receipt["machine_proof"]["coupa_access_performed"] is False
    assert receipt["machine_proof"]["submit_performed"] is False


def test_bad_candidate_response_claiming_paid_fails_verification(tmp_path):
    read_model_root = _seed_read_models(tmp_path)
    candidate = _candidate(
        read_model_root,
        "finance_capital_hilton_payment_watch",
        draft_body="Payment evidence is missing. The invoice has been paid. The ledger stays untouched.",
    )
    receipt, latest, _bridge_latest = _route(
        tmp_path,
        _controller_event_request(
            event_type="ask_why",
            world="finance",
            thread="capital_hilton",
            suffix="bad_paid_candidate",
            selected_card_id="dynamic_card.finance.capital_hilton.payment_watch",
            operator_text="Why am I here?",
            candidate=candidate,
        ),
    )

    primary = receipt["proof_to_response"]
    assert primary["verification_status"] == "fallback"
    assert "unsupported_completion_claim" in primary["fallback_reason"]
    assert latest["latest_response"]["verification_status"] == "fallback"
    assert "has been paid" not in primary["body"].lower()


def test_machine_contract_jargon_fails(tmp_path):
    read_model_root = _seed_read_models(tmp_path)
    candidate = _candidate(
        read_model_root,
        "finance_capital_hilton_payment_watch",
        draft_body="The dynamic card read model says payment evidence is missing and the ledger stays untouched.",
    )
    receipt, _latest, _bridge_latest = _route(
        tmp_path,
        _controller_event_request(
            event_type="ask_why",
            world="finance",
            thread="capital_hilton",
            suffix="jargon_candidate",
            selected_card_id="dynamic_card.finance.capital_hilton.payment_watch",
            operator_text="Why am I here?",
            candidate=candidate,
        ),
    )

    assert receipt["proof_to_response"]["verification_status"] == "fallback"
    assert "machine_contract_jargon" in receipt["proof_to_response"]["fallback_reason"]


def test_fallback_response_is_safe_and_concise(tmp_path):
    read_model_root = _seed_read_models(tmp_path)
    candidate = _candidate(
        read_model_root,
        "protected_coupa_ledger_email_request",
        draft_headline="Submit in Coupa",
        draft_body="Protected action is blocked until proof and approval, but I will submit this in Coupa.",
        draft_next_step="Submit in Coupa",
        claimed_facts=["protected_action_blocked"],
        implied_actions=["coupa_submit"],
        requested_controls=["Submit in Coupa"],
    )
    receipt, _latest, _bridge_latest = _route(
        tmp_path,
        _controller_event_request(
            event_type="do_it",
            world="finance",
            thread="capital_hilton",
            suffix="protected_bad_candidate",
            selected_card_id="dynamic_card.finance.capital_hilton.payment_watch",
            operator_text="Submit this in Coupa.",
            candidate=candidate,
        ),
    )

    primary = receipt["proof_to_response"]
    assert primary["verification_status"] == "fallback"
    assert len(primary["headline"]) <= 90
    assert len(primary["body"]) <= 280
    assert "will submit" not in primary["body"].lower()
    assert "coupa/browser action" in [item.lower() for item in primary["cannot_do_yet"]]
    assert primary["authority_boundary"]["protected_actions_allowed"] is False


def test_dynamic_card_remains_available_as_support(tmp_path):
    receipt, _latest, _bridge_latest = _route(
        tmp_path,
        _controller_event_request(
            event_type="advance_objective",
            world="finance",
            thread="capital_hilton",
            suffix="support_card",
            selected_card_id="dynamic_card.finance.capital_hilton.payment_watch",
            operator_text="Advance this.",
        ),
    )

    assert receipt["primary_response_kind"] == "proof_to_response"
    assert receipt["dynamic_card_role"] == "support_display"
    assert receipt["dynamic_card_response"]["proof"]["collapsed_by_default"] is True
    assert receipt["details_collapsed"] is True


def test_processor_response_embeds_request_scoped_proof_to_response(tmp_path):
    read_model_root = _seed_read_models(tmp_path)
    request = _controller_event_request(
        event_type="advance_objective",
        world="business_development",
        thread="capital_hilton",
        suffix="processor_business_development",
        selected_card_id="dynamic_card.business_development.capital_hilton.proposal",
        operator_text="Advance the follow-up.",
    )
    request_path = tmp_path / "mission_control_controller_event_request_processor_business.json"
    request_path.write_text(json.dumps(request, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    classification = processor.RequestClassification(
        classification_id="test:proof_to_response_controller",
        source_request_filename=request_path.name,
        request_family="OPERATOR_CONTROLLER_EVENT_REQUEST",
        selected_rail="operator_controller_event_router",
        classification_reason="test",
        future_supported=False,
        next_safe_move="route controller event",
    )
    response = processor._process_operator_controller_event_request(
        request_path,
        request,
        export_root=read_model_root,
        generated_at=FIXED_NOW,
        classification=classification,
        route_decision={"selected_rail": "operator_controller_event_router"},
    )

    assert response.proof_to_response_status == "publishable"
    assert response.proof_to_response["source_request_id"] == request["request_id"]
    assert response.proof_to_response["world_ref"] == "business_development"
    assert response.proof_to_response["thread_ref"] == "capital_hilton"
    assert response.operator_headline == "Follow-up can be staged"
    assert response.visible_cards

    response_path = "/mnt/e/openclaw/mission_control_responses/to_mac/openclaw_response_for_mac_processor_business.json"
    response_payload, _status_payload = processor.build_payloads(response, generated_at=FIXED_NOW)
    stamped = processor.stamp_proof_to_response_source_response_path(
        response_payload,
        source_response_path=response_path,
    )
    assert stamped["proof_to_response"]["source_response_path"] == response_path
    assert (
        stamped["detail_disclosure"]["proof_to_response"]["source_response_path"]
        == response_path
    )
    runtime.restamp_latest_source_response_path(
        source_request_id=request["request_id"],
        source_response_path=response_path,
        export_root=read_model_root,
        bridge_export_root=tmp_path / "bridge",
        wiki_path=tmp_path / "wiki" / "Proof To Response Runtime.md",
        generated_at=FIXED_NOW,
    )
    latest = json.loads((read_model_root / runtime.LATEST_JSON_EXPORT_NAME).read_text(encoding="utf-8"))
    bridge_latest = json.loads((tmp_path / "bridge" / runtime.LATEST_JSON_EXPORT_NAME).read_text(encoding="utf-8"))
    assert latest == bridge_latest
    assert latest["source_response_path"] == response_path
    assert latest["latest_response"]["source_response_path"] == response_path


def test_unsafe_true_grant_scan_clean(tmp_path):
    receipt, latest, bridge_latest = _route(
        tmp_path,
        _controller_event_request(
            event_type="ask_why",
            world="finance",
            thread="capital_hilton",
            suffix="unsafe_scan",
            selected_card_id="dynamic_card.finance.capital_hilton.payment_watch",
            operator_text="Why am I here?",
        ),
    )

    assert router.unsafe_true_grants(receipt) == []
    assert runtime.unsafe_true_grants(latest) == []
    assert runtime.unsafe_true_grants(bridge_latest) == []
    conn = sqlite3.connect(tmp_path / "system_knowledge" / "proof_to_response_runtime.sqlite")
    try:
        row_count = conn.execute("select count(*) from proof_to_response_receipts").fetchone()[0]
    finally:
        conn.close()
    assert row_count == 1
