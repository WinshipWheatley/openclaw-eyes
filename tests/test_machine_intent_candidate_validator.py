import json
import re
import sys
from dataclasses import fields
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import machine_intent_candidate_validator as intent
from scripts.export_machine_intent_candidate_validator import main as export_main


FIXED_NOW = "2026-05-25T23:59:00+00:00"


def test_required_models_exist_with_required_fields():
    expected = {
        "MachineIntentCandidate": (
            "intent_id",
            "source_request_id",
            "original_operator_text",
            "inferred_intent_type",
            "target_world_ref",
            "target_folder_ref",
            "target_thread_ref",
            "target_workflow_ref",
            "target_agent_role",
            "target_worker_type",
            "requested_action",
            "referenced_next_action",
            "confidence",
            "ambiguity_status",
            "required_clarification",
            "evidence_refs_used",
            "context_refs_used",
            "source_refs_used",
            "missing_requirements",
            "forbidden_assumptions",
            "authority_requested",
            "authority_granted",
            "validation_required",
            "next_safe_move",
        ),
        "MissingRequirementCandidate": (
            "missing_requirement_id",
            "source_intent_ref",
            "requirement_type",
            "requirement_label",
            "target_workflow_ref",
            "target_world_ref",
            "why_needed",
            "acceptable_inputs",
            "source_ref_allowed",
            "operator_input_allowed",
            "authority_boundary",
            "next_safe_move",
        ),
        "BuildCueCandidate": (
            "build_cue_id",
            "source_intent_ref",
            "missing_capability",
            "affected_workflow_ref",
            "suggested_rail",
            "suggested_worker",
            "why_needed",
            "risk_level",
            "execution_authority",
            "validation_required",
            "next_safe_move",
        ),
        "ContextGapCandidate": (
            "context_gap_id",
            "source_intent_ref",
            "missing_context_type",
            "affected_world_ref",
            "affected_folder_ref",
            "affected_thread_ref",
            "gap_summary",
            "suggested_resolution",
            "validation_required",
            "next_safe_move",
        ),
        "DeterministicIntentValidator": (
            "validator_id",
            "doctrine",
            "validation_policy",
            "confidence_policy",
            "ambiguity_policy",
            "authority_policy",
            "cross_scope_policy",
            "candidate_promotion_policy",
            "fail_closed_policy",
            "authority_boundary",
            "next_safe_move",
        ),
        "IntentValidationResult": (
            "validation_result_id",
            "source_intent_ref",
            "verdict",
            "confidence",
            "ambiguity_status",
            "validated_intent_type",
            "resolved_workflow_ref",
            "resolved_next_action",
            "blocked_reasons",
            "clarification_question",
            "created_candidates",
            "authority_granted",
            "capability_index_used",
            "matched_capabilities",
            "missing_capabilities",
            "rejected_capabilities",
            "authority_profile_checked",
            "tenant_scope_checked",
            "fixture_scope_checked",
            "next_safe_move",
        ),
        "IntentValidationBlocker": (
            "blocker_id",
            "blocker_type",
            "condition",
            "severity",
            "elioperator_warning",
            "fail_closed",
            "next_safe_move",
        ),
        "CapabilityLookupContext": (
            "capability_index_used",
            "matched_capabilities",
            "matched_workflow_bindings",
            "missing_capabilities",
            "rejected_capabilities",
            "authority_profile_checked",
            "tenant_scope_checked",
            "fixture_scope_checked",
            "tenant_scope",
            "invalid_tenant_scope",
            "required_missing_inputs",
            "blockers",
        ),
    }
    classes = {
        "MachineIntentCandidate": intent.MachineIntentCandidate,
        "MissingRequirementCandidate": intent.MissingRequirementCandidate,
        "BuildCueCandidate": intent.BuildCueCandidate,
        "ContextGapCandidate": intent.ContextGapCandidate,
        "DeterministicIntentValidator": intent.DeterministicIntentValidator,
        "IntentValidationResult": intent.IntentValidationResult,
        "IntentValidationBlocker": intent.IntentValidationBlocker,
        "CapabilityLookupContext": intent.CapabilityLookupContext,
    }
    for name, required_fields in expected.items():
        assert tuple(field.name for field in fields(classes[name])) == required_fields


def test_payload_contains_models_blockers_and_authority_boundary():
    payload = intent.build_payload(generated_at=FIXED_NOW)

    assert payload["machine_proof"]["machine_intent_candidate_model_present"] is True
    assert payload["machine_proof"]["missing_requirement_candidate_model_present"] is True
    assert payload["machine_proof"]["build_cue_candidate_model_present"] is True
    assert payload["machine_proof"]["context_gap_candidate_model_present"] is True
    assert payload["machine_proof"]["deterministic_intent_validator_model_present"] is True
    assert payload["machine_proof"]["intent_validation_result_model_present"] is True
    assert payload["machine_proof"]["blockers_present"] is True
    assert {blocker["blocker_type"] for blocker in payload["standard_blockers"]} == set(intent.BLOCKER_TYPES)
    assert payload["machine_proof"]["capability_index_used"] is True
    for value in payload["authority_boundary"].values():
        assert value is False
    assert payload["machine_proof"]["all_live_authority_false"] is True


def test_capital_hilton_next_validates_as_missing_po_intake():
    example = intent.build_examples()["capital_hilton_next"]

    assert example["candidate"]["inferred_intent_type"] in {"CONTINUE_CURRENT_WORKFLOW", "CAPTURE_MISSING_INPUT"}
    assert example["validation_result"]["verdict"] == "VALIDATED_INTENT"
    assert example["validation_result"]["validated_intent_type"] == "CAPTURE_MISSING_INPUT"
    assert example["validation_result"]["resolved_workflow_ref"] == "capital_hilton_invoice_workflow"
    assert example["validation_result"]["capability_index_used"] is True
    assert "status_readback" in example["validation_result"]["matched_capabilities"]
    assert any(ref.startswith("binding:fixture:capital_hilton") for ref in example["validation_result"]["matched_capabilities"])
    assert any(item["requirement_type"] == "MISSING_PO_REFERENCE" for item in example["missing_requirements"])
    assert "Coupa PO/reference" in example["validation_result"]["next_safe_move"]
    assert not any(example["validation_result"]["authority_granted"].values())


def test_go_ahead_does_not_grant_approval_or_external_authority():
    example = intent.build_examples()["capital_hilton_go_ahead"]

    assert example["validation_result"]["verdict"] == "BLOCKED_BY_AUTHORITY"
    assert any(blocker["blocker_type"] == "EXACT_APPROVAL_REQUIRED" for blocker in example["blockers"])
    assert any(blocker["blocker_type"] == "EXTERNAL_ACTION_REQUESTED" for blocker in example["blockers"])
    assert not any(example["validation_result"]["authority_granted"].values())
    assert intent.build_payload(generated_at=FIXED_NOW)["machine_proof"]["go_ahead_grants_approval"] is False


def test_ambiguous_next_asks_clarification():
    example = intent.build_examples()["ambiguous_next"]

    assert example["validation_result"]["verdict"] == "CLARIFICATION_REQUIRED"
    assert "Which workflow" in example["validation_result"]["clarification_question"]
    assert any(blocker["blocker_type"] == "AMBIGUOUS_CONTEXT" for blocker in example["blockers"])
    assert any(blocker["blocker_type"] == "MISSING_WORKFLOW_CONTEXT" for blocker in example["blockers"])


def test_cassandra_draft_route_has_no_send_authority():
    example = intent.build_examples()["cassandra_draft"]

    assert example["candidate"]["target_agent_role"] == "CASSANDRA"
    assert example["candidate"]["inferred_intent_type"] in {"PREPARE_DRAFT", "ROUTE_TO_AGENT"}
    assert example["validation_result"]["verdict"] == "VALIDATED_INTENT"
    assert "outbound_message_draft" in example["validation_result"]["matched_capabilities"]
    assert not any(example["candidate"]["authority_granted"].values())
    assert not any(example["validation_result"]["authority_granted"].values())


def test_niles_x32_route_has_no_daw_or_file_mutation_authority():
    example = intent.build_examples()["niles_x32"]

    assert example["candidate"]["target_agent_role"] == "NILES"
    assert example["validation_result"]["verdict"] == "CONTEXT_GAP_CREATED"
    assert example["context_gaps"]
    assert "X32" in example["context_gaps"][0]["gap_summary"]
    assert example["candidate"]["authority_granted"]["file_mutation"] is False
    assert not any(example["validation_result"]["authority_granted"].values())


def test_prompt_injection_blocks_authority_and_completion_claim():
    example = intent.build_examples()["prompt_injection"]
    blocker_types = {blocker["blocker_type"] for blocker in example["blockers"]}

    assert example["validation_result"]["verdict"] == "BLOCKED_BY_AUTHORITY"
    assert "EXTERNAL_ACTION_REQUESTED" in blocker_types
    assert "EXACT_APPROVAL_REQUIRED" in blocker_types
    assert "LM_CANDIDATE_REQUESTS_EXECUTION" in blocker_types
    assert not any(example["validation_result"]["authority_granted"].values())


def test_hallucinated_rail_blocks_and_creates_build_cue():
    example = intent.build_examples()["hallucinated_rail"]

    assert example["validation_result"]["verdict"] == "BLOCKED_BY_MISSING_CAPABILITY"
    assert any(blocker["blocker_type"] == "LM_CANDIDATE_HALLUCINATES_RAIL" for blocker in example["blockers"])
    assert example["build_cues"]
    assert example["build_cues"][0]["missing_capability"] == "live_coupa_auto_submit"
    assert example["build_cues"][0]["execution_authority"] is False


def test_send_it_uses_send_gate_but_does_not_grant_send_authority():
    example = intent.build_examples()["send_it"]
    blocker_types = {blocker["blocker_type"] for blocker in example["blockers"]}

    assert example["validation_result"]["verdict"] == "BLOCKED_BY_AUTHORITY"
    assert "outbound_message_send_gate" in example["validation_result"]["matched_capabilities"]
    assert "portal_transaction_submit_gate" in example["validation_result"]["matched_capabilities"]
    assert "CAPABILITY_AUTHORITY_FALSE" in blocker_types
    assert "EXACT_APPROVAL_REQUIRED" in blocker_types
    assert not any(example["validation_result"]["authority_granted"].values())


def test_make_video_validates_visual_package_but_no_provider_call():
    example = intent.build_examples()["make_video"]

    assert example["validation_result"]["verdict"] == "VALIDATED_INTENT"
    assert "visual_event_compilation" in example["validation_result"]["matched_capabilities"]
    assert "live_visual_video_generation_provider" in example["validation_result"]["missing_capabilities"]
    assert "live_visual_video_generation_provider" in example["validation_result"]["rejected_capabilities"]
    assert example["build_cues"]
    assert all(cue["execution_authority"] is False for cue in example["build_cues"])
    assert not any(example["validation_result"]["authority_granted"].values())


def test_proposed_capability_cannot_be_used_live():
    example = intent.build_examples()["proposed_capability_misuse"]
    blocker_types = {blocker["blocker_type"] for blocker in example["blockers"]}

    assert example["validation_result"]["verdict"] == "BLOCKED_BY_MISSING_CAPABILITY"
    assert "PROPOSED_CANDIDATE_USED_AS_LIVE_CAPABILITY" in blocker_types
    assert "proposal:client_cockpit_visual_event_renderer" in example["validation_result"]["rejected_capabilities"]
    assert not any(example["validation_result"]["authority_granted"].values())


def test_invalid_tenant_scope_blocks_workflow_binding_use():
    candidate = intent._candidate(
        intent_id="intent_candidate:invalid_tenant_scope",
        source_request_id="fixture:invalid_tenant_scope",
        original_operator_text="next",
        inferred_intent_type="CONTINUE_CURRENT_WORKFLOW",
        requested_action="continue current workflow",
        target_workflow_ref="capital_hilton_invoice_workflow",
        target_world_ref="tenant_scope:not_valid",
        confidence="HIGH",
        missing_requirements=("MISSING_PO_REFERENCE",),
    )
    result, _missing, _build_cues, _context_gaps, blockers = intent.validate_machine_intent_candidate(candidate)

    assert result.verdict == "BLOCKED_BY_MISSING_CONTEXT"
    assert result.tenant_scope_checked is True
    assert result.fixture_scope_checked is True
    assert any(blocker.blocker_type == "INVALID_TENANT_SCOPE" for blocker in blockers)


def test_export_writes_json_and_operator_markdown(tmp_path, capsys):
    assert export_main(["--export-root", str(tmp_path), "--generated-at", FIXED_NOW, "--format", "summary"]) == 0
    summary = json.loads(capsys.readouterr().out)
    payload = json.loads((tmp_path / intent.JSON_EXPORT_NAME).read_text(encoding="utf-8"))
    operator = (tmp_path / intent.OPERATOR_EXPORT_NAME).read_text(encoding="utf-8")

    assert summary["read_model_id"] == intent.READ_MODEL_ID
    assert summary["capital_hilton_next_verdict"] == "VALIDATED_INTENT"
    assert summary["go_ahead_verdict"] == "BLOCKED_BY_AUTHORITY"
    assert summary["all_live_authority_false"] is True
    assert payload["examples"]["capital_hilton_next"]["validation_result"]["verdict"] == "VALIDATED_INTENT"
    assert "Machine Intent Candidate Validator" in operator
    assert "No live LM interpreter" in operator


def test_generated_outputs_have_no_credentials_secrets_or_private_bodies(tmp_path):
    payload = intent.build_payload(generated_at=FIXED_NOW)
    intent.write_exports(payload, tmp_path)
    text = "\n".join(path.read_text(encoding="utf-8") for path in tmp_path.iterdir())
    lowered = text.lower()

    forbidden_literals = (
        "actual secret",
        "credential value",
        "password value",
        "token value",
        "raw private body value",
        "private key value",
    )
    for literal in forbidden_literals:
        assert literal not in lowered
    assert not re.search(r"AKIA[0-9A-Z]{16}", text)
    assert not re.search(r"-----BEGIN [A-Z ]*PRIVATE KEY-----", text)
    assert not re.search(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b", text)


def test_machine_proof_records_no_live_execution_or_calls():
    payload = intent.build_payload(generated_at=FIXED_NOW)
    proof = payload["machine_proof"]

    assert proof["lm_interpreter_called"] is False
    assert proof["model_call_performed"] is False
    assert proof["agent_dispatch_performed"] is False
    assert proof["workflow_run_performed"] is False
    assert proof["external_action_performed"] is False
    assert proof["send_submit_performed"] is False
    assert proof["approval_execution_performed"] is False
    assert proof["candidate_self_promotion_performed"] is False
    assert proof["credential_handling_performed"] is False
    assert proof["raw_body_ingestion_performed"] is False
