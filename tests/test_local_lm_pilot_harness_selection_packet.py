import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import local_lm_pilot_harness_selection_packet as packet
import proof_to_response_runtime


FIXED_NOW = "2026-06-07T05:25:00+00:00"


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _fixture_root(tmp_path: Path) -> Path:
    root = tmp_path / "generated" / "read_models"
    _write_json(
        root / "local_lm_proof_response_pilot_approval_brief.json",
        {
            "status": "LOCAL_LM_PROOF_RESPONSE_PILOT_APPROVAL_BRIEF_READY",
            "candidate_harness_ref": "local_llm_shadow_mode",
            "candidate_model_ref": "",
            "candidate_source_mode": "local_lm_shadow_mode_once_pending_operator_approval",
            "brief_answers": {
                "proof_bundle_model_would_see": {
                    "allowed_fields": [
                        "world_ref",
                        "thread_ref",
                        "objective_ref",
                        "redacted_known_facts",
                        "proof_meter_labels",
                        "receipt_refs",
                        "gate_labels",
                        "missing_input",
                        "allowed_controls",
                        "blocked_action_summaries",
                        "human_safe_summaries",
                        "agent_voice_mode",
                    ]
                },
                "what_model_would_not_see": [
                    "raw_bank_details",
                    "credentials_or_tokens",
                    "operator_device_session_verification_secrets",
                    "raw_prompt_dumps",
                    "raw_artifact_ocr_text",
                    "source_workbook_bodies",
                    "raw_email_bodies_unapproved",
                    "raw_ledger_rows_unapproved",
                ],
            },
        },
    )
    _write_json(
        root / "local_lm_harness_inventory_receipts.json",
        {
            "status": "LOCAL_LM_HARNESS_INVENTORY_RECEIPTS_READY",
            "harness_candidates": [
                {
                    "harness_ref": "local_llm_shadow_mode",
                    "present": "unknown",
                    "invocation_allowed": False,
                    "proof_to_response_allowed": False,
                    "live_invocation_ready": False,
                    "data_classes_allowed": ["bounded_proof_bundle_refs", "receipt_refs"],
                    "data_classes_forbidden": [
                        "raw_sensitive_details",
                        "operator_envelope_secret_material",
                        "device_verification_material",
                        "credentials_or_tokens",
                        "raw_bank_details_unredacted",
                        "raw_prompt_dumps",
                        "source_workbook_bodies",
                        "tool_authority",
                    ],
                    "missing_receipts": [
                        "proof_bundle_redaction_receipt",
                        "model_invocation_boundary_receipt",
                        "no_external_provider_receipt",
                        "no_tool_authority_receipt",
                        "no_memory_promotion_receipt",
                        "verifier_pass_fail_receipt",
                        "published_response_hash_receipt",
                        "operator_approval_receipt",
                    ],
                    "required_operator_approval": "explicit_operator_approval_required",
                    "required_verifier": "proof_to_response_verifier",
                    "required_redaction": True,
                    "reason_not_live": "shadow_mode_inventory_only_no_runtime_boundary_receipt",
                }
            ],
        },
    )
    _write_json(root / "local_lm_proof_to_response_readiness_gate.json", {"status": "LOCAL_LM_PROOF_RESPONSE_READINESS_GATE_READY"})
    _write_json(root / "proof_bundle_redaction_policy.json", {"status": "PROOF_BUNDLE_REDACTION_HARDENING_READY"})
    _write_json(
        root / proof_to_response_runtime.STATUS_JSON_EXPORT_NAME,
        {
            "status": proof_to_response_runtime.READY_STATUS,
            "active_candidate_source": proof_to_response_runtime.CANDIDATE_SOURCE_SHADOW_PILOT,
        },
    )
    _write_json(
        root / "local_lm_proof_response_pilot_approval_packet.json",
        {
            "status": "LOCAL_LM_PROOF_RESPONSE_PILOT_APPROVAL_PACKET_READY",
            "approval_packet": {
                "proof_bundle_summary": {
                    "proof_bundle_ref": "redacted_proof_bundle:finance_capital_hilton_payment_watch"
                },
                "redaction_policy_ref": "generated/read_models/proof_bundle_redaction_policy.json",
                "verifier_ref": "proof_to_response_verifier.py#proof_to_response_verifier_v0",
                "forbidden_lm_inputs": [
                    "raw_bank_details",
                    "credentials_or_tokens",
                    "operator_device_session_verification_secrets",
                    "raw_prompt_dumps",
                    "raw_artifact_ocr_text",
                    "source_workbook_bodies",
                    "raw_email_bodies_unapproved",
                    "raw_ledger_rows_unapproved",
                ],
            },
        },
    )
    return root


def _read_model(tmp_path: Path) -> dict:
    return packet.build_read_model(read_model_root=_fixture_root(tmp_path), generated_at=FIXED_NOW)


def _selection(read_model: dict) -> dict:
    return read_model["selection_packet"]


def test_packet_is_pending_review_not_approved(tmp_path):
    read_model = _read_model(tmp_path)
    selection = _selection(read_model)

    assert read_model["status"] == packet.READY_STATUS
    assert selection["status"] == "pending_operator_review"
    assert read_model["machine_proof"]["approved"] is False
    assert read_model["machine_proof"]["packet_pending_operator_review"] is True


def test_invocation_allowed_false(tmp_path):
    selection = _selection(_read_model(tmp_path))

    assert selection["invocation_allowed"] is False
    assert selection["authority_boundary"]["invocation_allowed"] is False
    assert selection["implementation_boundary"]["model_invoked"] is False


def test_external_provider_used_false(tmp_path):
    selection = _selection(_read_model(tmp_path))

    assert selection["external_provider_used"] is False
    assert selection["authority_boundary"]["external_provider_connect_allowed"] is False
    assert selection["implementation_boundary"]["external_provider_connected"] is False


def test_tool_access_false(tmp_path):
    selection = _selection(_read_model(tmp_path))

    assert selection["tool_access"] is False
    assert selection["authority_boundary"]["tool_authority_allowed"] is False
    assert selection["authority_boundary"]["tool_execution_allowed"] is False


def test_memory_write_access_false(tmp_path):
    selection = _selection(_read_model(tmp_path))

    assert selection["memory_write_access"] is False
    assert selection["authority_boundary"]["memory_write_access"] is False
    assert selection["authority_boundary"]["memory_promotion_allowed"] is False


def test_business_action_authority_false(tmp_path):
    selection = _selection(_read_model(tmp_path))

    assert selection["business_action_authority"] is False
    assert selection["authority_boundary"]["business_action_allowed"] is False
    assert selection["implementation_boundary"]["business_action_performed"] is False


def test_missing_receipts_are_listed(tmp_path):
    selection = _selection(_read_model(tmp_path))

    assert "operator_approval_receipt" in selection["missing_receipts"]
    assert "model_invocation_boundary_receipt" in selection["missing_receipts"]
    assert "no_external_provider_receipt" in selection["missing_receipts"]
    assert "no_tool_authority_receipt" in selection["missing_receipts"]
    assert "verifier_pass_fail_receipt" in selection["missing_receipts"]


def test_selection_answers_required_questions(tmp_path):
    selection = _selection(_read_model(tmp_path))
    answers = selection["answers"]

    assert selection["selected_harness_ref"] == "local_llm_shadow_mode"
    assert selection["selected_model_ref"] == "not_selected_pending_operator_review"
    assert selection["local_only"] is True
    assert selection["runtime_present"] == "unknown"
    assert selection["proof_bundle_ref"] == "redacted_proof_bundle:finance_capital_hilton_payment_watch"
    assert selection["redaction_policy_ref"] == "generated/read_models/proof_bundle_redaction_policy.json"
    assert selection["verifier_ref"] == "proof_to_response_verifier.py#proof_to_response_verifier_v0"
    assert answers["what_tool_access_model_has"] == "none"
    assert answers["what_memory_write_access_model_has"] == "none"


def test_forbidden_inputs_include_private_material(tmp_path):
    selection = _selection(_read_model(tmp_path))
    forbidden = set(selection["forbidden_inputs"])

    assert "raw_bank_details" in forbidden
    assert "credentials_or_tokens" in forbidden
    assert "operator_device_session_verification_secrets" in forbidden
    assert "raw_prompt_dumps" in forbidden
    assert "raw_artifact_ocr_text" in forbidden
    assert "source_workbook_bodies" in forbidden
    assert "raw_email_bodies_unapproved" in forbidden
    assert "raw_ledger_rows_unapproved" in forbidden


def test_unsafe_true_grant_scan_clean(tmp_path):
    read_model = _read_model(tmp_path)

    assert packet.unsafe_true_grants(read_model) == []
    assert read_model["unsafe_true_grants"] == []
    assert read_model["machine_proof"]["unsafe_true_grants_absent"] is True


def test_export_json_bridge_equality_and_wiki(tmp_path):
    result = packet.export_local_lm_pilot_harness_selection_packet(
        read_model_root=_fixture_root(tmp_path),
        export_root=tmp_path / "read_models",
        bridge_root=tmp_path / "bridge",
        wiki_path=tmp_path / "Local LM Pilot Harness Selection Packet.md",
        generated_at=FIXED_NOW,
    )
    local = json.loads(Path(result["read_model_path"]).read_text(encoding="utf-8"))
    bridge = json.loads(Path(result["bridge_read_model_path"]).read_text(encoding="utf-8"))
    wiki = Path(result["wiki_path"]).read_text(encoding="utf-8")

    assert result["status"] == packet.READY_STATUS
    assert result["packet_status"] == "pending_operator_review"
    assert local == bridge
    assert packet.unsafe_true_grants(local) == []
    assert wiki.startswith("# Local LM Pilot Harness Selection Packet")
