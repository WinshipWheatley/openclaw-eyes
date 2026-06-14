import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import local_lm_proof_response_pilot_approval_packet as packet
import proof_bundle_redaction_policy as redaction_policy
import proof_to_response_runtime


FIXED_NOW = "2026-06-07T04:40:00+00:00"


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _fixture_root(tmp_path: Path) -> Path:
    root = tmp_path / "generated" / "read_models"
    _write_json(root / "local_lm_proof_to_response_pilot_plan.json", {"status": "LOCAL_LM_PROOF_RESPONSE_PILOT_PLAN_READY"})
    _write_json(root / "local_lm_harness_inventory_receipts.json", {"status": "LOCAL_LM_HARNESS_INVENTORY_RECEIPTS_READY"})
    _write_json(root / "proof_bundle_redaction_policy.json", {"status": "PROOF_BUNDLE_REDACTION_HARDENING_READY"})
    _write_json(root / "proof_bundle_builder_redaction_status.json", {"status": "PROOF_BUNDLE_BUILDER_REDACTION_INTEGRATION_READY"})
    _write_json(root / "agent_response_voice_modes.json", {"status": "AGENT_RESPONSE_VOICE_MODES_READY"})
    _write_json(
        root / proof_to_response_runtime.STATUS_JSON_EXPORT_NAME,
        {
            "status": proof_to_response_runtime.READY_STATUS,
            "active_candidate_source": proof_to_response_runtime.CANDIDATE_SOURCE_SHADOW_PILOT,
            "source_request_id": "finance_payment_watch_controller_map_advance_objective_smoke",
            "world_ref": "finance",
            "thread_ref": "capital_hilton",
        },
    )
    _write_json(
        root / proof_to_response_runtime.LATEST_JSON_EXPORT_NAME,
        {
            "status": proof_to_response_runtime.READY_STATUS,
            "candidate_source": proof_to_response_runtime.CANDIDATE_SOURCE_SHADOW_PILOT,
            "stale_if_context_mismatch": True,
            "source_request_id": "business_development_advance_objective_smoke",
            "world_ref": "business_development",
            "thread_ref": "capital_hilton",
            "latest_response": {
                "source_request_id": "business_development_advance_objective_smoke",
                "world_ref": "business_development",
                "thread_ref": "capital_hilton",
                "headline": "Follow-up can be staged",
                "body": "I can stage a follow-up draft. I will not send it.",
                "next_step": "Stage follow-up.",
            },
        },
    )
    _write_json(
        root / "dynamic_card_packet_latest.json",
        {
            "status": "DYNAMIC_CARD_PACKET_READY",
            "cards": [
                {
                    "card_id": "dynamic_card.finance.capital_hilton.payment_watch",
                    "action_slots": {
                        "primary": {
                            "controller_event_type": "ask_why",
                            "enabled": True,
                            "control_scope": "lane",
                            "text_response_preferred": True,
                        },
                        "secondary": {
                            "controller_event_type": "advance_objective",
                            "enabled": True,
                            "control_scope": "lane",
                            "text_response_preferred": True,
                        },
                        "detail": {
                            "controller_event_type": "attach_proof",
                            "enabled": True,
                            "control_scope": "lane",
                            "text_response_preferred": True,
                        },
                    },
                }
            ],
        },
    )
    _write_json(
        root / "operator_action_payloads.json",
        {
            "status": "OPERATOR_ACTION_PAYLOADS_READY",
            "action_payloads": [
                {"action_id": "capital_hilton.payment.record_proof"},
                {"action_id": "capital_hilton.payment.open_finance"},
            ],
        },
    )
    return root


def _read_model(tmp_path: Path) -> dict:
    return packet.build_read_model(read_model_root=_fixture_root(tmp_path), generated_at=FIXED_NOW)


def _approval(read_model: dict) -> dict:
    return read_model["approval_packet"]


def test_approval_packet_is_pending_review_not_approved(tmp_path):
    read_model = _read_model(tmp_path)
    approval = _approval(read_model)

    assert read_model["status"] == packet.READY_STATUS
    assert approval["status"] == "pending_operator_review"
    assert approval["approval_packet_id"].startswith("approval_packet:local_lm_proof_response")
    assert read_model["machine_proof"]["operator_approval_recorded"] is False
    assert read_model["machine_proof"]["packet_is_pending_review_not_approved"] is True
    assert approval["authority_boundary"]["live_lm_invocation_allowed"] is False


def test_pilot_lane_is_finance_capital_hilton(tmp_path):
    approval = _approval(_read_model(tmp_path))

    assert approval["selected_lane"] == "finance/capital_hilton"
    assert approval["pilot_question"] == "What should I do here?"
    assert approval["intended_response_type"] == "proof_to_response"
    assert approval["proof_bundle_summary"]["world_ref"] == "finance"
    assert approval["proof_bundle_summary"]["thread_ref"] == "capital_hilton"


def test_payment_watch_readiness_does_not_depend_on_latest_lane(tmp_path):
    read_model = _read_model(tmp_path)
    rows = {row["precondition_ref"]: row for row in read_model["preconditions"]}

    assert rows["proof_to_response_scoped_responses"]["ready"] is True
    assert rows["finance_payment_watch_proof_response"]["ready"] is True
    assert rows["finance_payment_watch_proof_response"]["source_ref"] == (
        "proof_to_response_runtime.py#finance_capital_hilton_payment_watch"
    )
    assert rows["finance_payment_watch_proof_response"]["verification_status"] == "VERIFIED_FOR_SHADOW_PUBLISH"


def test_proof_bundle_allowed_fields_match_redaction_policy(tmp_path):
    approval = _approval(_read_model(tmp_path))

    assert [row["field_ref"] for row in approval["allowed_lm_inputs"]] == list(redaction_policy.ALLOWED_FIELD_REASONS)
    assert all(row["reason"] for row in approval["allowed_lm_inputs"])


def test_forbidden_fields_exclude_secret_financial_prompt_ocr_workbook_email_ledger_bodies(tmp_path):
    approval = _approval(_read_model(tmp_path))
    forbidden = set(approval["forbidden_lm_inputs"])

    assert "raw_financial_details" in forbidden
    assert "bank_account_numbers" in forbidden
    assert "credentials_tokens" in forbidden
    assert "operator_device_session_verification_secrets" in forbidden
    assert "raw_prompt_dumps" in forbidden
    assert "raw_artifact_ocr_text" in forbidden
    assert "full_artifact_text_or_ocr" in forbidden
    assert "source_workbook_bodies" in forbidden
    assert "raw_email_bodies_unapproved" in forbidden
    assert "raw_ledger_rows_unapproved" in forbidden


def test_no_external_provider_allowed(tmp_path):
    approval = _approval(_read_model(tmp_path))

    assert approval["authority_boundary"]["external_llm_allowed"] is False
    assert approval["authority_boundary"]["external_provider_connect_allowed"] is False
    assert "external_llm_call" in approval["forbidden_actions"]
    assert "external_provider_path_appears" in approval["stop_conditions"]
    assert approval["safety_requirements"]["no_external_llm"] is True


def test_no_tool_authority_granted(tmp_path):
    approval = _approval(_read_model(tmp_path))

    assert approval["authority_boundary"]["tool_authority_allowed"] is False
    assert approval["authority_boundary"]["tool_execution_allowed"] is False
    assert "tool_use" in approval["forbidden_actions"]
    assert approval["safety_requirements"]["no_tool_use"] is True


def test_verifier_is_mandatory(tmp_path):
    approval = _approval(_read_model(tmp_path))

    assert approval["verifier_ref"] == "proof_to_response_verifier.py#proof_to_response_verifier_v0"
    assert "verifier_pass_fail_receipt" in approval["receipts_required"]
    assert approval["safety_requirements"]["verifier_must_gate_publish"] is True
    assert approval["safety_requirements"]["failed_verifier_returns_safe_fallback"] is True


def test_stop_conditions_include_unsafe_claims_and_protected_actions(tmp_path):
    approval = _approval(_read_model(tmp_path))
    stop_conditions = set(approval["stop_conditions"])

    assert "model_claims_paid_sent_submitted" in stop_conditions
    assert "model_proposes_protected_action" in stop_conditions
    assert "verifier_fails" in stop_conditions
    assert "proof_bundle_contains_secret_or_raw_financial_detail" in stop_conditions


def test_operator_decision_options_are_review_only(tmp_path):
    approval = _approval(_read_model(tmp_path))
    options = {row["option_ref"]: row for row in approval["operator_decision_options"]}

    assert set(options) == set(packet.OPERATOR_DECISION_OPTION_REFS)
    for row in options.values():
        assert row["review_only"] is True
        assert row["grants_live_invocation_now"] is False


def test_unsafe_true_grant_scan_clean(tmp_path):
    read_model = _read_model(tmp_path)

    assert packet.unsafe_true_grants(read_model) == []
    assert read_model["machine_proof"]["unsafe_true_grants_absent"] is True
    assert read_model["implementation_boundary"]["model_invoked"] is False
    assert read_model["implementation_boundary"]["worker_spawn_performed"] is False


def test_export_json_bridge_equality_and_wiki(tmp_path):
    result = packet.export_local_lm_proof_response_pilot_approval_packet(
        read_model_root=_fixture_root(tmp_path),
        export_root=tmp_path / "read_models",
        bridge_root=tmp_path / "bridge",
        wiki_path=tmp_path / "Local LM Proof Response Pilot Approval Packet.md",
        generated_at=FIXED_NOW,
    )
    local = json.loads(Path(result["read_model_path"]).read_text(encoding="utf-8"))
    bridge = json.loads(Path(result["bridge_read_model_path"]).read_text(encoding="utf-8"))
    wiki = Path(result["wiki_path"]).read_text(encoding="utf-8")

    assert result["status"] == packet.READY_STATUS
    assert result["approval_packet_status"] == "pending_operator_review"
    assert local == bridge
    assert packet.unsafe_true_grants(local) == []
    assert wiki.startswith("# Local LM Proof Response Pilot Approval Packet")
