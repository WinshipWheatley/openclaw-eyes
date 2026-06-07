import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import local_lm_proof_response_invocation_boundary_packet as boundary
import proof_to_response_runtime


FIXED_NOW = "2026-06-07T12:30:00+00:00"


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _fixture_root(tmp_path: Path) -> Path:
    root = tmp_path / "generated" / "read_models"
    _write_json(
        root / "local_model_selection_for_proof_response.json",
        {
            "status": "LOCAL_MODEL_SELECTION_FOR_PROOF_RESPONSE_READY",
            "selection_packet": {
                "recommended_runtime_ref": "ollama",
                "recommended_model_ref": "local_model:ollama:qwen3_8b-q4_k_m",
                "recommended_model_name": "qwen3:8b-q4_K_M",
                "ready_for_invocation": False,
                "proof_bundle_allowed": False,
            },
        },
    )
    _write_json(
        root / "local_model_list_inventory.json",
        {
            "status": "LOCAL_MODEL_LIST_INVENTORY_READY",
            "discovered_models": [
                {
                    "model_ref": "local_model:ollama:qwen3_8b-q4_k_m",
                    "runtime_ref": "ollama",
                    "model_name": "qwen3:8b-q4_K_M",
                    "present": True,
                    "local_only": True,
                    "invocation_allowed": False,
                    "proof_bundle_allowed": False,
                }
            ],
        },
    )
    _write_json(root / "local_lm_proof_response_preflight_receipts.json", {"status": "LOCAL_LM_PROOF_RESPONSE_PREFLIGHT_RECEIPTS_READY"})
    _write_json(root / "local_lm_proof_to_response_pilot_plan.json", {"status": "LOCAL_LM_PROOF_RESPONSE_PILOT_PLAN_READY"})
    _write_json(root / "proof_bundle_freshness_trace_status.json", {"status": "PROOF_BUNDLE_FRESHNESS_TRACE_INTEGRATION_READY"})
    _write_json(root / "proof_bundle_builder_redaction_status.json", {"status": "PROOF_BUNDLE_BUILDER_REDACTION_INTEGRATION_READY"})
    _write_json(root / "proof_bundle_redaction_policy.json", {"status": "PROOF_BUNDLE_REDACTION_HARDENING_READY"})
    _write_json(
        root / proof_to_response_runtime.STATUS_JSON_EXPORT_NAME,
        {
            "status": proof_to_response_runtime.READY_STATUS,
            "active_candidate_source": proof_to_response_runtime.CANDIDATE_SOURCE_SHADOW_PILOT,
        },
    )
    _write_json(root / "context_freshness_decision_trace_gate.json", {"status": "CONTEXT_FRESHNESS_DECISION_TRACE_GATE_READY"})
    return root


def _read_model(tmp_path: Path) -> dict:
    return boundary.build_read_model(read_model_root=_fixture_root(tmp_path), generated_at=FIXED_NOW)


def _packet(read_model: dict) -> dict:
    return read_model["invocation_boundary_packet"]


def test_invocation_allowed_false(tmp_path):
    read_model = _read_model(tmp_path)
    packet = _packet(read_model)

    assert read_model["status"] == boundary.READY_STATUS
    assert packet["status"] == "pending_operator_review"
    assert packet["invocation_allowed"] is False
    assert read_model["invocation_allowed"] is False
    assert packet["authority_boundary"]["model_invocation_allowed"] is False
    assert packet["runtime_contact_method"]["runtime_contact_allowed_now"] is False


def test_proof_bundle_allowed_false(tmp_path):
    packet = _packet(_read_model(tmp_path))

    assert packet["proof_bundle_allowed"] is False
    assert packet["authority_boundary"]["proof_bundle_allowed"] is False
    assert packet["runtime_contact_method"]["proof_bundle_sent"] is False
    assert packet["review_only_assertions"]["proof_bundle_not_sent"] is True


def test_selected_model_is_qwen3_8b_q4_k_m(tmp_path):
    read_model = _read_model(tmp_path)
    packet = _packet(read_model)

    assert packet["selected_runtime_ref"] == "ollama"
    assert packet["selected_model_ref"] == "local_model:ollama:qwen3_8b-q4_k_m"
    assert packet["selected_model_name"] == "qwen3:8b-q4_K_M"
    assert read_model["machine_proof"]["selected_model_present"] is True
    assert read_model["machine_proof"]["selection_matches_required_model"] is True


def test_pilot_lane_is_finance_capital_hilton(tmp_path):
    packet = _packet(_read_model(tmp_path))

    assert packet["pilot_lane"] == "finance/capital_hilton"
    assert packet["pilot_question"] == "What should I do here?"
    assert packet["pilot_context"]["world_ref"] == "finance"
    assert packet["pilot_context"]["thread_ref"] == "capital_hilton"


def test_no_external_provider_allowed(tmp_path):
    packet = _packet(_read_model(tmp_path))

    assert packet["exact_boundary"]["no_external_provider"] is True
    assert packet["authority_boundary"]["external_provider_connect_allowed"] is False
    assert packet["implementation_boundary"]["external_provider_used"] is False
    assert "external_provider_call" in packet["forbidden_actions"]


def test_no_tool_authority_allowed(tmp_path):
    packet = _packet(_read_model(tmp_path))

    assert packet["exact_boundary"]["no_tools"] is True
    assert packet["authority_boundary"]["tool_authority"] is False
    assert packet["authority_boundary"]["tool_execution_allowed"] is False
    assert packet["implementation_boundary"]["tool_execution_performed"] is False
    assert "tool_use" in packet["forbidden_actions"]


def test_forbidden_inputs_include_sensitive_bodies_and_secrets(tmp_path):
    packet = _packet(_read_model(tmp_path))
    forbidden = set(packet["forbidden_inputs"])

    assert "raw_bank_or_account_details" in forbidden
    assert "credentials_or_tokens" in forbidden
    assert "operator_device_session_verification_secrets" in forbidden
    assert "raw_artifact_or_ocr_text" in forbidden
    assert "full_workbook_contents" in forbidden
    assert "source_workbook_bodies" in forbidden
    assert "raw_email_bodies" in forbidden
    assert "raw_ledger_rows" in forbidden
    assert "incoming_authority_granted_fields" in forbidden


def test_stop_conditions_include_stale_context_and_verifier_failure(tmp_path):
    packet = _packet(_read_model(tmp_path))
    stops = set(packet["stop_conditions"])

    assert "context_freshness_is_stale_superseded_or_unknown" in stops
    assert "verifier_fails" in stops
    assert "proof_bundle_contains_forbidden_field" in stops
    assert "model_claims_paid_sent_submitted_or_executed" in stops
    assert "tool_call_attempt_appears" in stops


def test_operator_decision_options_are_review_only(tmp_path):
    packet = _packet(_read_model(tmp_path))

    assert packet["operator_decision_options"] == [
        "approve_one_time_local_lm_invocation_for_finance_payment_watch",
        "request_more_detail",
        "choose_different_model",
        "reject_for_now",
    ]
    assert packet["review_only_assertions"]["this_packet_is_not_approval"] is True
    assert packet["review_only_assertions"]["model_not_invoked"] is True


def test_allowed_inputs_are_redacted_freshness_gated_fields(tmp_path):
    packet = _packet(_read_model(tmp_path))
    allowed = set(packet["allowed_inputs"])

    assert set(boundary.ALLOWED_INPUTS) == allowed
    assert "freshness_state" in allowed
    assert "confidence_class" in allowed
    assert "decision_trace_summary" in allowed
    assert "raw_ledger_rows" not in allowed
    assert "authority_granted" not in allowed


def test_runtime_contact_method_is_described_but_not_executed(tmp_path):
    contact = _packet(_read_model(tmp_path))["runtime_contact_method"]

    assert contact["recommended_method_ref"] == "ollama_cli_one_shot_stdin_after_operator_approval"
    assert contact["command_template_review_only_not_executed"] == "ollama run qwen3:8b-q4_K_M"
    assert contact["runtime_contact_allowed_now"] is False
    assert contact["runtime_connected"] is False
    assert contact["prompt_sent"] is False


def test_unsafe_true_grant_scan_clean(tmp_path):
    read_model = _read_model(tmp_path)

    assert boundary.unsafe_true_grants(read_model) == []
    assert read_model["unsafe_true_grants"] == []
    assert read_model["machine_proof"]["unsafe_true_grants_absent"] is True


def test_export_json_bridge_equality_and_wiki(tmp_path):
    result = boundary.export_local_lm_proof_response_invocation_boundary_packet(
        read_model_root=_fixture_root(tmp_path),
        export_root=tmp_path / "read_models",
        bridge_root=tmp_path / "bridge",
        wiki_path=tmp_path / "Local LM Proof Response Invocation Boundary Packet.md",
        generated_at=FIXED_NOW,
    )
    local = json.loads(Path(result["read_model_path"]).read_text(encoding="utf-8"))
    bridge = json.loads(Path(result["bridge_read_model_path"]).read_text(encoding="utf-8"))
    wiki = Path(result["wiki_path"]).read_text(encoding="utf-8")

    assert result["status"] == boundary.READY_STATUS
    assert result["selected_model_ref"] == "local_model:ollama:qwen3_8b-q4_k_m"
    assert result["invocation_allowed"] == "false"
    assert result["proof_bundle_allowed"] == "false"
    assert local == bridge
    assert boundary.unsafe_true_grants(local) == []
    assert wiki.startswith("# Local LM Proof Response Invocation Boundary Packet")
