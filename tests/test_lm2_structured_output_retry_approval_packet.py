import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import lm2_structured_output_retry_approval_packet as packet
import lm2_room_backed_worker_one_time_pilot as one_time_pilot
import lm2_room_backed_worker_pilot_postmortem as postmortem
import proof_bundle_builder as bundles
import proof_to_response_schema_adapter as schema_adapter


FIXED_NOW = "2026-06-08T15:00:00+00:00"


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _fixture_root(tmp_path: Path) -> Path:
    root = tmp_path / "generated" / "read_models"
    _write_json(
        root / one_time_pilot.JSON_EXPORT_NAME,
        {
            "status": one_time_pilot.READY_STATUS,
            "publication_decision": "safe_fallback_published",
            "pilot_scope": {"model_name": "qwen3:8b-q4_K_M", "runtime_ref": "ollama"},
        },
    )
    _write_json(
        root / postmortem.JSON_EXPORT_NAME,
        {
            "status": postmortem.READY_STATUS,
            "postmortem": {
                "failure_class": "non_json_model_output",
                "secondary_failure_class": "structured_output_boundary_failure",
                "safety_wrapper_passed": True,
                "room_backed_package_passed": True,
                "fallback_passed": True,
                "receipts_complete": True,
                "question_answers": {
                    "did_model_attempt_protected_action": False,
                    "what_failed": "The local Ollama CLI attempt returned output that was not valid JSON.",
                },
            },
        },
    )
    _write_json(root / schema_adapter.STATUS_JSON_EXPORT_NAME, {"status": schema_adapter.READY_STATUS})
    _write_json(root / "project_room_package_compiler_integration.json", {"status": "PROJECT_ROOM_PACKAGE_COMPILER_INTEGRATION_READY"})
    _write_json(root / "lm2_room_backed_worker_pilot_boundary.json", {"status": "LM2_ROOM_BACKED_WORKER_PILOT_BOUNDARY_READY"})
    _write_json(root / "local_model_selection_for_proof_response.json", {"status": "LOCAL_MODEL_SELECTION_FOR_PROOF_RESPONSE_READY"})
    _write_json(root / bundles.FRESHNESS_TRACE_STATUS_JSON_EXPORT_NAME, {"status": bundles.FRESHNESS_TRACE_READY_STATUS})
    _write_json(root / bundles.REDACTION_STATUS_JSON_EXPORT_NAME, {"status": bundles.REDACTION_READY_STATUS})
    return root


def _read_model(tmp_path: Path) -> dict:
    return packet.build_read_model(read_model_root=_fixture_root(tmp_path), generated_at=FIXED_NOW)


def test_packet_is_pending_operator_review(tmp_path):
    read_model = _read_model(tmp_path)
    approval = read_model["approval_packet"]

    assert read_model["status"] == packet.READY_STATUS
    assert read_model["packet_status"] == "pending_operator_review"
    assert approval["status"] == "pending_operator_review"
    assert approval["approval_packet_id"] == packet.APPROVAL_PACKET_ID
    assert "This packet is not approval." in approval["rules"]
    assert "This packet does not run LM2." in approval["rules"]


def test_prior_failure_class_is_non_json(tmp_path):
    approval = _read_model(tmp_path)["approval_packet"]

    assert approval["prior_failure_class"] == "non_json_model_output"
    assert approval["prior_result"]["prior_failure_class"] == "non_json_model_output"
    assert approval["prior_result"]["prior_secondary_failure_class"] == "structured_output_boundary_failure"
    assert approval["retry_reason"] == "structured_output_required"


def test_structured_output_required(tmp_path):
    approval = _read_model(tmp_path)["approval_packet"]

    assert approval["structured_output_required"] is True
    assert "JSON-only response" in approval["structured_output_retry_requirements"]
    assert "no markdown" in approval["structured_output_retry_requirements"]
    assert "no code fences" in approval["structured_output_retry_requirements"]
    assert "no prose outside JSON" in approval["structured_output_retry_requirements"]
    assert approval["required_schema_fields"] == list(packet.REQUIRED_SCHEMA_FIELDS)
    assert approval["strict_response_json_schema"] == schema_adapter.strict_json_draft_schema()


def test_invocation_worker_spawn_and_proof_bundle_false(tmp_path):
    read_model = _read_model(tmp_path)
    approval = read_model["approval_packet"]

    assert approval["invocation_allowed"] is False
    assert approval["worker_spawn_allowed"] is False
    assert approval["proof_bundle_allowed"] is False
    assert read_model["machine_proof"]["invocation_disallowed"] is True
    assert read_model["machine_proof"]["worker_spawn_disallowed"] is True
    assert read_model["machine_proof"]["proof_bundle_disallowed"] is True


def test_schema_adapter_and_verifier_are_mandatory(tmp_path):
    read_model = _read_model(tmp_path)
    approval = read_model["approval_packet"]

    assert approval["schema_adapter_required"] is True
    assert approval["verifier_required"] is True
    assert approval["fallback_required"] is True
    assert "schema adapter runs before verifier" in approval["structured_output_retry_requirements"]
    assert "verifier remains the publish gate" in approval["structured_output_retry_requirements"]
    assert read_model["machine_proof"]["schema_adapter_and_verifier_mandatory"] is True


def test_stop_conditions_include_required_blocks(tmp_path):
    stop_conditions = set(_read_model(tmp_path)["approval_packet"]["stop_conditions"])

    assert "model_returns_non_json" in stop_conditions
    assert "model_returns_markdown_code_fences_or_prose_outside_json" in stop_conditions
    assert "schema_adapter_fails" in stop_conditions
    assert "model_claims_paid_sent_submitted_or_executed" in stop_conditions
    assert "model_promises_protected_action" in stop_conditions
    assert "model_attempts_tool_use" in stop_conditions
    assert "model_exceeds_one_attempt" in stop_conditions
    assert "verifier_fails" in stop_conditions


def test_protected_actions_remain_forbidden(tmp_path):
    read_model = _read_model(tmp_path)
    approval = read_model["approval_packet"]
    forbidden = set(approval["protected_actions_forbidden"])

    assert "repeated_invocations" in forbidden
    assert "external_provider" in forbidden
    assert "tool_use" in forbidden
    assert "browser_gmail_coupa" in forbidden
    assert "ledger_mutation" in forbidden
    assert "workbook_mutation" in forbidden
    assert "pdf_export" in forbidden
    assert "paid_marking" in forbidden
    assert "worker_spawning_beyond_the_one_future_retry" in forbidden
    assert "raw_finance_private_proof" in forbidden
    assert "operator_device_session_secrets" in forbidden
    assert "missing_context_as_permission_to_invent" in forbidden
    assert approval["authority_boundary"]["business_action_authority"] is False
    assert approval["authority_boundary"]["tool_authority"] is False
    assert read_model["machine_proof"]["protected_actions_remain_forbidden"] is True


def test_operator_decision_options_are_review_only(tmp_path):
    options = _read_model(tmp_path)["approval_packet"]["operator_decision_options"]

    assert options == list(packet.OPERATOR_DECISION_OPTIONS)
    assert "approve_one_time_room_backed_lm2_structured_output_retry" in options
    assert "request_more_detail" in options
    assert "choose_different_model" in options
    assert "reject_for_now" in options
    assert "invoke_lm2" not in options


def test_expected_output_target_matches_contract(tmp_path):
    expected = _read_model(tmp_path)["approval_packet"]["expected_output_target"]

    assert expected == packet.EXPECTED_OUTPUT_TARGET
    assert expected["headline"] == "Payment evidence needed"
    assert "paid_false" in expected["claimed_facts"]
    assert expected["requested_controls"] == ["attach_proof"]


def test_unsafe_true_grant_scan_clean(tmp_path):
    read_model = _read_model(tmp_path)

    assert packet.unsafe_true_grants(read_model) == []
    assert read_model["unsafe_true_grants"] == []
    assert read_model["machine_proof"]["unsafe_true_grants_absent"] is True


def test_export_json_bridge_equality_and_wiki(tmp_path):
    result = packet.export_lm2_structured_output_retry_approval_packet(
        read_model_root=_fixture_root(tmp_path),
        export_root=tmp_path / "read_models",
        bridge_root=tmp_path / "bridge",
        wiki_path=tmp_path / "LM2 Structured Output Retry Approval Packet.md",
        generated_at=FIXED_NOW,
    )
    local = json.loads(Path(result["read_model_path"]).read_text(encoding="utf-8"))
    bridge = json.loads(Path(result["bridge_read_model_path"]).read_text(encoding="utf-8"))
    wiki = Path(result["wiki_path"]).read_text(encoding="utf-8")

    assert result["status"] == packet.READY_STATUS
    assert local == bridge
    assert packet.unsafe_true_grants(local) == []
    assert wiki.startswith("# LM2 Structured Output Retry Approval Packet")
