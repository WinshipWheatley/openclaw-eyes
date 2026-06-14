import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import local_lm_model_selection_review_packet as packet
import proof_to_response_runtime


FIXED_NOW = "2026-06-07T07:10:00+00:00"


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _candidate(
    candidate_ref: str,
    *,
    name: str,
    locality: str,
    present=True,
    configured=True,
    running="unknown",
    privacy_risk="privacy boundary blocked until receipts exist",
    missing_receipts=None,
) -> dict:
    return {
        "candidate_ref": candidate_ref,
        "model_or_harness_name": name,
        "locality": locality,
        "present": present,
        "configured": configured,
        "running": running,
        "invocation_allowed": False,
        "proof_bundle_allowed": False,
        "external_provider_used": False,
        "tool_authority": False,
        "memory_write_authority": False,
        "business_action_authority": False,
        "privacy_risk": privacy_risk,
        "missing_receipts": missing_receipts
        or [
            "operator_approval_receipt",
            "model_invocation_boundary_receipt",
            "verifier_pass_fail_receipt",
            "published_response_hash_receipt",
        ],
    }


def _fixture_root(tmp_path: Path) -> Path:
    root = tmp_path / "generated" / "read_models"
    _write_json(
        root / "model_catalog_inventory.json",
        {
            "status": "MODEL_CATALOG_INVENTORY_READY",
            "model_candidates": [
                _candidate(
                    "model_candidate:sidecar:local_llm_shadow_mode",
                    name="local_llm_shadow_mode",
                    locality="sidecar",
                    privacy_risk="fixture/mock-only harness; no live proof bundle invocation authority",
                ),
                _candidate(
                    "model_candidate:local_runtime:ollama",
                    name="Ollama",
                    locality="local",
                    running=True,
                    privacy_risk="local runtime present but model boundary missing",
                ),
                _candidate(
                    "model_candidate:sidecar:hermes_sidecar",
                    name="Hermes sidecar candidate",
                    locality="sidecar",
                    running=False,
                    privacy_risk="blocked unless separately registered and receipted",
                    missing_receipts=[
                        "operator_approval_receipt",
                        "model_invocation_boundary_receipt",
                        "explicit_hermes_proof_to_response_registration_receipt",
                    ],
                ),
                _candidate(
                    "model_candidate:operator_assist:codex_desktop_operator_assist",
                    name="Codex Desktop operator assist",
                    locality="operator_assist",
                    privacy_risk="operator assist requires separate scope gate",
                    missing_receipts=[
                        "operator_approval_receipt",
                        "model_invocation_boundary_receipt",
                        "operator_assist_scope_receipt",
                    ],
                ),
                _candidate(
                    "model_candidate:external_provider:openai",
                    name="OpenAI",
                    locality="external",
                    present="unknown",
                    configured=True,
                    privacy_risk="External providers are blocked by default for private proof.",
                    missing_receipts=[
                        "operator_approval_receipt",
                        "model_invocation_boundary_receipt",
                        "external_provider_exception_gate_receipt",
                        "provider_privacy_policy_receipt",
                    ],
                ),
            ],
        },
    )
    _write_json(root / "local_lm_runtime_discovery.json", {"status": "LOCAL_LM_RUNTIME_DISCOVERY_READY"})
    _write_json(
        root / "local_lm_proof_response_preflight_receipts.json",
        {
            "status": "LOCAL_LM_PROOF_RESPONSE_PREFLIGHT_RECEIPTS_READY",
            "selected_harness_ref": "local_llm_shadow_mode",
            "selected_runtime_ref": "none_connected_review_only",
            "selected_model_ref": None,
            "pilot_lane": "finance/capital_hilton",
            "pilot_question": "What should I do here?",
            "receipts_missing": [
                {"receipt_ref": "operator_approval_receipt", "receipt_status": "missing"},
                {"receipt_ref": "model_invocation_boundary_receipt", "receipt_status": "missing"},
                {"receipt_ref": "verifier_pass_fail_receipt", "receipt_status": "missing"},
                {"receipt_ref": "published_response_hash_receipt", "receipt_status": "missing"},
            ],
        },
    )
    _write_json(
        root / "local_lm_proof_to_response_pilot_plan.json",
        {
            "status": "LOCAL_LM_PROOF_RESPONSE_PILOT_PLAN_READY",
            "first_pilot_lane": {"lane_ref": "finance/capital_hilton"},
        },
    )
    _write_json(
        root / "local_lm_pilot_harness_selection_packet.json",
        {
            "status": "LOCAL_LM_PILOT_HARNESS_SELECTION_PACKET_READY",
            "selection_packet": {
                "selected_harness_ref": "local_llm_shadow_mode",
                "selected_runtime_ref": "none_connected_review_only",
                "selected_model_ref": "not_selected_pending_operator_review",
                "invocation_allowed": False,
                "proof_bundle_allowed": False,
            },
        },
    )
    _write_json(root / "local_lm_proof_to_response_readiness_gate.json", {"status": "LOCAL_LM_PROOF_RESPONSE_READINESS_GATE_READY"})
    _write_json(
        root / "proof_bundle_redaction_policy.json",
        {
            "status": "PROOF_BUNDLE_REDACTION_HARDENING_READY",
            "allowed_lm_input_fields": [
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
            ],
            "forbidden_material_policy": {
                "raw_finance_details": {"forbidden": True},
                "bank_account_numbers": {"forbidden": True},
                "credentials_or_tokens": {"forbidden": True},
                "operator_device_session_verification_secrets": {"forbidden": True},
                "raw_prompt_dumps": {"forbidden": True},
                "raw_artifact_ocr_text": {"forbidden": True},
                "workbook_email_ledger_bodies": {"forbidden": True},
                "hidden_machine_contracts": {"forbidden": True},
                "authority_granted_fields": {"forbidden": True},
            },
        },
    )
    _write_json(root / "proof_bundle_builder_redaction_status.json", {"status": "PROOF_BUNDLE_BUILDER_REDACTION_INTEGRATION_READY"})
    _write_json(root / proof_to_response_runtime.STATUS_JSON_EXPORT_NAME, {"status": proof_to_response_runtime.READY_STATUS})
    return root


def _read_model(tmp_path: Path) -> dict:
    return packet.build_read_model(read_model_root=_fixture_root(tmp_path), generated_at=FIXED_NOW)


def _review_packet(read_model: dict) -> dict:
    return read_model["review_packet"]


def test_packet_recommends_one_candidate(tmp_path):
    read_model = _read_model(tmp_path)
    review = _review_packet(read_model)

    assert read_model["status"] == packet.READY_STATUS
    assert review["status"] == "pending_operator_review"
    assert review["recommended_candidate_ref"] == "model_candidate:sidecar:local_llm_shadow_mode"
    assert review["recommended_harness_ref"] == "local_llm_shadow_mode"
    assert review["recommended_model_ref"] is None
    assert review["selected_for_review"] is True


def test_invocation_allowed_false(tmp_path):
    review = _review_packet(_read_model(tmp_path))

    assert review["invocation_allowed"] is False
    assert review["authority_boundary"]["invocation_allowed"] is False
    assert review["implementation_boundary"]["model_invoked"] is False
    assert all(row["invocation_allowed"] is False for row in review["candidate_considered"])


def test_proof_bundle_allowed_false(tmp_path):
    review = _review_packet(_read_model(tmp_path))

    assert review["proof_bundle_allowed"] is False
    assert review["authority_boundary"]["proof_bundle_allowed"] is False
    assert review["implementation_boundary"]["proof_bundle_sent"] is False
    assert all(row["proof_bundle_allowed"] is False for row in review["candidate_considered"])


def test_external_providers_remain_blocked(tmp_path):
    review = _review_packet(_read_model(tmp_path))
    external = [row for row in review["candidate_considered"] if row["locality"] == "external"]

    assert external
    for row in external:
        assert row["invocation_allowed"] is False
        assert row["proof_bundle_allowed"] is False
        assert "external_provider" in row["reason_selected_or_rejected"]
        assert "external_provider_exception_gate_receipt" in row["missing_receipts"]
    assert review["authority_boundary"]["external_provider_connect_allowed"] is False


def test_selected_candidate_requires_operator_approval_before_invocation(tmp_path):
    review = _review_packet(_read_model(tmp_path))
    selected = next(row for row in review["candidate_considered"] if row["candidate_ref"] == review["recommended_candidate_ref"])

    assert review["required_operator_decision"] == "approve_model_selection_for_one_time_pilot"
    assert "operator_approval_receipt" in review["required_receipts_before_invocation"]
    assert "operator_approval_receipt" in selected["missing_receipts"]
    assert "approve_model_selection_for_one_time_pilot" in review["decision_options"]


def test_selected_candidate_has_verifier_mandatory(tmp_path):
    review = _review_packet(_read_model(tmp_path))
    selected = next(row for row in review["candidate_considered"] if row["candidate_ref"] == review["recommended_candidate_ref"])

    assert review["selection_criteria"]["verifier_mandatory"] is True
    assert selected["verifier_mandatory"] is True
    assert "verifier_pass_fail_receipt" in review["required_receipts_before_invocation"]
    assert review["verifier_ref"] == packet.DEFAULT_VERIFIER_REF


def test_first_pilot_scope_is_finance_capital_hilton(tmp_path):
    review = _review_packet(_read_model(tmp_path))
    scope = review["first_pilot_scope"]

    assert scope["lane"] == "finance/capital_hilton"
    assert scope["world_ref"] == "finance"
    assert scope["thread_ref"] == "capital_hilton"
    assert scope["question"] == "What should I do here?"
    assert review["expected_response"]["headline"] == "Payment evidence needed"
    assert review["expected_response"]["next_step"] == "Attach payment evidence."


def test_no_tool_memory_business_authority(tmp_path):
    read_model = _read_model(tmp_path)
    review = _review_packet(read_model)

    assert read_model["machine_proof"]["tool_access"] is False
    assert read_model["machine_proof"]["memory_write_access"] is False
    assert read_model["machine_proof"]["business_action_authority"] is False
    assert review["authority_boundary"]["tool_authority"] is False
    assert review["authority_boundary"]["memory_write_authority"] is False
    assert review["authority_boundary"]["business_action_authority"] is False
    for row in review["candidate_considered"]:
        assert row["tool_authority"] is False
        assert row["memory_write_authority"] is False
        assert row["business_action_authority"] is False


def test_proof_bundle_boundaries_are_redacted(tmp_path):
    review = _review_packet(_read_model(tmp_path))

    assert "redacted_known_facts" in review["allowed_proof_bundle_fields"]
    assert "agent_voice_mode" in review["allowed_proof_bundle_fields"]
    assert "raw_finance_details" in review["forbidden_proof_bundle_fields"]
    assert "bank_account_numbers" in review["forbidden_proof_bundle_fields"]
    assert "operator_device_session_verification_secrets" in review["forbidden_proof_bundle_fields"]
    assert review["first_pilot_scope"]["raw_financial_private_proof_allowed"] is False
    assert review["first_pilot_scope"]["operator_device_session_verification_material_allowed"] is False


def test_unsafe_true_grant_scan_clean(tmp_path):
    read_model = _read_model(tmp_path)

    assert packet.unsafe_true_grants(read_model) == []
    assert read_model["unsafe_true_grants"] == []
    assert read_model["machine_proof"]["unsafe_true_grants_absent"] is True


def test_export_json_bridge_equality_and_wiki(tmp_path):
    result = packet.export_local_lm_model_selection_review_packet(
        read_model_root=_fixture_root(tmp_path),
        export_root=tmp_path / "read_models",
        bridge_root=tmp_path / "bridge",
        wiki_path=tmp_path / "Local LM Model Selection Review Packet.md",
        generated_at=FIXED_NOW,
    )
    local = json.loads(Path(result["read_model_path"]).read_text(encoding="utf-8"))
    bridge = json.loads(Path(result["bridge_read_model_path"]).read_text(encoding="utf-8"))
    wiki = Path(result["wiki_path"]).read_text(encoding="utf-8")

    assert result["status"] == packet.READY_STATUS
    assert result["packet_status"] == "pending_operator_review"
    assert result["recommended_candidate_ref"] == "model_candidate:sidecar:local_llm_shadow_mode"
    assert result["invocation_allowed"] == "false"
    assert result["proof_bundle_allowed"] == "false"
    assert local == bridge
    assert packet.unsafe_true_grants(local) == []
    assert wiki.startswith("# Local LM Model Selection Review Packet")
