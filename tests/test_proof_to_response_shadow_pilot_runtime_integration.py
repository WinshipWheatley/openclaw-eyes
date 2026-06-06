import json
import shutil
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import first_class_operator_envelope as operator_authority
import operator_controller_event_router as router
import proof_to_response_lm_shadow_pilot as pilot
import proof_to_response_runtime as runtime


FIXED_NOW = "2026-06-06T23:30:00+00:00"

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
    selected_card_id: str,
    operator_text: str = "",
) -> dict:
    request = {
        "request_id": f"shadow_pilot_runtime_{suffix}",
        "request_type": router.REQUEST_TYPE,
        "source_surface": "mission_control",
        "controller_event_type": event_type,
        "controller_action_type": event_type,
        "current_world_ref": world,
        "current_thread_ref": thread,
        "active_entity_ref": selected_card_id,
        "selected_card_id": selected_card_id,
        "selected_action_id": "",
        "operator_text": operator_text,
        "authority_requested": [],
        "authority_boundary": dict(router.AUTHORITY_BOUNDARY),
    }
    request["operator_envelope"] = {
        "envelope_id": f"operator_envelope:shadow_pilot_runtime:{suffix}",
        "operator_ref": "operator:winship",
        "app_instance_ref": "mission_control:mac",
        "device_ref": "device:macbook",
        "device_class": "mac",
        "session_ref": f"session:shadow-pilot-runtime:{suffix}",
        "request_hash": "",
        "created_at": FIXED_NOW,
        "source_surface": "card",
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


def _route(tmp_path: Path, request: dict) -> tuple[dict, dict]:
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
    return receipt, latest


def _shadow_candidate(scenario_id: str, **overrides) -> dict:
    bundle = runtime.build_or_load_proof_bundle(scenario_id)
    candidate = pilot.mock_lm_style_candidate_response(bundle)
    candidate.update(overrides)
    return candidate


def test_runtime_uses_shadow_pilot_candidate_source(tmp_path):
    result = runtime.publish_response(
        "finance_capital_hilton_payment_watch",
        candidate_source=runtime.CANDIDATE_SOURCE_SHADOW_PILOT,
        generated_at=FIXED_NOW,
        sqlite_path=tmp_path / "proof_to_response_runtime.sqlite",
    )

    assert result["candidate_source"] == runtime.CANDIDATE_SOURCE_SHADOW_PILOT
    assert result["published_response"]["candidate_source"] == runtime.CANDIDATE_SOURCE_SHADOW_PILOT
    assert result["verifier_result"]["publishable"] is True


def test_capital_hilton_shadow_candidate_publishes_after_verifier_pass(tmp_path):
    receipt, latest = _route(
        tmp_path,
        _controller_event_request(
            event_type="ask_why",
            world="finance",
            thread="capital_hilton",
            suffix="finance_capital_hilton",
            selected_card_id="dynamic_card.finance.capital_hilton.payment_watch",
            operator_text="Why am I here?",
        ),
    )

    primary = receipt["proof_to_response"]
    assert receipt["proof_to_response_candidate_source"] == runtime.CANDIDATE_SOURCE_SHADOW_PILOT
    assert primary["candidate_source"] == runtime.CANDIDATE_SOURCE_SHADOW_PILOT
    assert primary["headline"] == "Payment evidence needed"
    assert "payment evidence is attached" in primary["body"]
    assert "ledger stays untouched" in primary["body"]
    assert primary["next_step"] == "Attach payment evidence."
    assert latest["candidate_source"] == runtime.CANDIDATE_SOURCE_SHADOW_PILOT


def test_business_development_shadow_candidate_publishes_after_verifier_pass(tmp_path):
    receipt, latest = _route(
        tmp_path,
        _controller_event_request(
            event_type="advance_objective",
            world="business_development",
            thread="capital_hilton",
            suffix="business_development_capital_hilton",
            selected_card_id="dynamic_card.business_development.capital_hilton.proposal",
            operator_text="Advance this objective.",
        ),
    )

    primary = receipt["proof_to_response"]
    assert primary["candidate_source"] == runtime.CANDIDATE_SOURCE_SHADOW_PILOT
    assert primary["headline"] == "Follow-up can be staged"
    assert "stage a follow-up draft" in primary["body"]
    assert "will not send it" in primary["body"]
    assert latest["latest_response"]["candidate_source"] == runtime.CANDIDATE_SOURCE_SHADOW_PILOT


def test_bad_paid_claim_falls_back_safely(tmp_path):
    candidate = _shadow_candidate(
        "finance_capital_hilton_payment_watch",
        draft_body="Payment evidence is missing. The invoice has been paid. The ledger stays untouched.",
    )
    result = runtime.publish_response(
        "finance_capital_hilton_payment_watch",
        candidate_source=runtime.CANDIDATE_SOURCE_SHADOW_PILOT,
        candidate_response=candidate,
        generated_at=FIXED_NOW,
        sqlite_path=tmp_path / "proof_to_response_runtime.sqlite",
    )

    assert result["published_response"]["verification_status"] == "fallback"
    assert result["published_response"]["candidate_source"] == runtime.CANDIDATE_SOURCE_SHADOW_PILOT
    assert "unsupported_completion_claim" in result["published_response"]["fallback_reason"]
    assert "has been paid" not in result["published_response"]["body"].lower()


def test_bad_coupa_submit_promise_falls_back_safely(tmp_path):
    candidate = _shadow_candidate(
        "protected_coupa_ledger_email_request",
        draft_headline="Submit in Coupa",
        draft_body="Protected action is blocked until proof and approval, but I will submit this in Coupa.",
        draft_next_step="Submit in Coupa",
        claimed_facts=["protected_action_blocked", "proof_and_approval_required"],
        implied_actions=["coupa_submit"],
        requested_controls=["Submit in Coupa"],
    )
    result = runtime.publish_response(
        "protected_coupa_ledger_email_request",
        candidate_source=runtime.CANDIDATE_SOURCE_SHADOW_PILOT,
        candidate_response=candidate,
        generated_at=FIXED_NOW,
        sqlite_path=tmp_path / "proof_to_response_runtime.sqlite",
    )

    assert result["published_response"]["verification_status"] == "fallback"
    assert "protected_action_promise:coupa_submit" in result["published_response"]["fallback_reason"]
    assert "will submit" not in result["published_response"]["body"].lower()


def test_bad_sent_jargon_and_overlong_candidates_fail(tmp_path):
    sent = _shadow_candidate(
        "business_development_capital_hilton_followup",
        draft_headline="Follow-up sent",
        draft_body="I sent the follow-up email.",
        draft_next_step="Stage follow-up",
        claimed_facts=["followup_stageable"],
        implied_actions=["email_send"],
        requested_controls=["Stage follow-up"],
    )
    jargon = _shadow_candidate(
        "finance_capital_hilton_payment_watch",
        draft_body="The generated/read_models source_request_id says payment evidence is missing and the ledger stays untouched.",
    )
    overlong = _shadow_candidate(
        "finance_capital_hilton_payment_watch",
        draft_body="Payment evidence is missing. The ledger stays untouched. " + ("Extra detail. " * 40),
    )

    sent_result = runtime.publish_response(
        "business_development_capital_hilton_followup",
        candidate_source=runtime.CANDIDATE_SOURCE_SHADOW_PILOT,
        candidate_response=sent,
        generated_at=FIXED_NOW,
        sqlite_path=tmp_path / "sent.sqlite",
    )
    jargon_result = runtime.publish_response(
        "finance_capital_hilton_payment_watch",
        candidate_source=runtime.CANDIDATE_SOURCE_SHADOW_PILOT,
        candidate_response=jargon,
        generated_at=FIXED_NOW,
        sqlite_path=tmp_path / "jargon.sqlite",
    )
    overlong_result = runtime.publish_response(
        "finance_capital_hilton_payment_watch",
        candidate_source=runtime.CANDIDATE_SOURCE_SHADOW_PILOT,
        candidate_response=overlong,
        generated_at=FIXED_NOW,
        sqlite_path=tmp_path / "overlong.sqlite",
    )

    assert "protected_action_promise:email_send" in sent_result["published_response"]["fallback_reason"]
    assert "machine_contract_jargon" in jargon_result["published_response"]["fallback_reason"]
    assert "response_not_concise" in overlong_result["published_response"]["fallback_reason"]


def test_candidate_source_recorded_in_status_and_latest(tmp_path):
    read_model_root = _seed_read_models(tmp_path)
    result = runtime.publish_response(
        "business_development_capital_hilton_followup",
        candidate_source=runtime.CANDIDATE_SOURCE_SHADOW_PILOT,
        generated_at=FIXED_NOW,
        sqlite_path=tmp_path / "proof_to_response_runtime.sqlite",
        read_model_root=read_model_root,
    )
    export = runtime.export_controller_integration_response(
        result,
        read_model_root=read_model_root,
        export_root=read_model_root,
        bridge_export_root=tmp_path / "bridge",
        wiki_path=tmp_path / "wiki" / "Proof To Response Runtime.md",
        sqlite_path=tmp_path / "proof_to_response_runtime.sqlite",
        generated_at=FIXED_NOW,
    )
    status = json.loads(Path(export["status_path"]).read_text(encoding="utf-8"))
    latest = json.loads(Path(export["latest_path"]).read_text(encoding="utf-8"))

    assert status["active_candidate_source"] == runtime.CANDIDATE_SOURCE_SHADOW_PILOT
    assert status["runtime_runs"][0]["candidate_source"] == runtime.CANDIDATE_SOURCE_SHADOW_PILOT
    assert latest["candidate_source"] == runtime.CANDIDATE_SOURCE_SHADOW_PILOT
    assert latest["latest_response"]["candidate_source"] == runtime.CANDIDATE_SOURCE_SHADOW_PILOT


def test_no_live_model_provider_call_and_unsafe_scan_clean(tmp_path):
    receipt, latest = _route(
        tmp_path,
        _controller_event_request(
            event_type="do_it",
            world="finance",
            thread="capital_hilton",
            suffix="protected_request",
            selected_card_id="dynamic_card.finance.capital_hilton.payment_watch",
            operator_text="Submit this in Coupa and email it.",
        ),
    )

    assert receipt["proof_to_response"]["speaker_ref"] == "guardian"
    assert receipt["proof_to_response"]["candidate_source"] == runtime.CANDIDATE_SOURCE_SHADOW_PILOT
    assert receipt["machine_proof"]["live_lm_invoked"] is False
    assert receipt["machine_proof"]["local_model_runtime_connected"] is False
    assert receipt["machine_proof"].get("external_provider_connected", False) is False
    assert router.unsafe_true_grants(receipt) == []
    assert runtime.unsafe_true_grants(latest) == []
