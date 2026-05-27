"""LM Readiness Dashboard v0.

Canonical integration read-model for the seeded LM readiness lanes. It builds a
representative non-live thread proof and summarizes what is ready, what is
blocked, and where the next floor-raising work should go.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping

import gate_chain_harness
import gate1_operational_snapshot
import gate1_privacy_request_readiness
import guardian_output_gate
import guardian_trust_ramp_simulator
import intent_ingest_gate
import live_lm_readiness_gate
import live_lm_activation_requirements
import live_lm_shadow_trial
import lm_intent_proposal_contract
import model_router_policy
import private_mode_policy_readiness
import provider_policy_registry
import read_model_mirror_visibility
import request_response_bridge_readiness
import role_package_gate
import shadow_lm_mode
import token_vault
import universal_intake_contract
from machine_intent_candidate_validator import MachineIntentCandidate


DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_GENERATED_AT = "2026-05-26T00:00:00+00:00"

SCHEMA_VERSION = "lm_readiness_dashboard_v1"
READ_MODEL_ID = "lm_readiness_dashboard"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
OPERATOR_EXPORT_NAME = f"{READ_MODEL_ID}_OPERATOR.md"
CONTRACT_STATUS = "LM_READINESS_INTEGRATION_V2_NO_LIVE_LM"

AUTHORITY_BOUNDARY = {
    "live_lm_call_allowed": False,
    "model_api_integration_allowed": False,
    "network_allowed": False,
    "provider_key_material_access_allowed": False,
    "agent_dispatch_allowed": False,
    "worker_dispatch_allowed": False,
    "tool_execution_allowed": False,
    "workflow_execution_allowed": False,
    "external_action_allowed": False,
    "send_submit_allowed": False,
    "approval_execution_allowed": False,
    "ledger_posting_allowed": False,
    "production_state_mutation_allowed": False,
    "workbook_body_read_allowed": False,
    "spreadsheet_cell_read_allowed": False,
    "ocr_allowed": False,
    "pdf_generation_allowed": False,
}


@dataclass(frozen=True)
class LM1ThreadContextPackage:
    package_id: str
    source_request_id: str
    gate1_operational_snapshot_ref: str
    gate1_safe_to_package_for_lm1: bool
    gate1_privacy_flags: dict[str, Any]
    source_device_ref: str
    user_message: str
    current_world_ref: str
    current_thread_ref: str
    universal_intake_inference: dict[str, Any]
    privacy_classification: str
    tokenization_required: bool
    tokenization_policy: dict[str, Any]
    privacy: dict[str, Any]
    model_router_result: dict[str, Any]
    allowed_context_classes: tuple[str, ...]
    forbidden_context_classes: tuple[str, ...]
    output_schema: tuple[str, ...]
    raw_values_included: bool
    tools_allowed: tuple[str, ...]
    authority_granted: dict[str, bool]
    next_safe_move: str


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _short_hash(*parts: object) -> str:
    return hashlib.sha256("\0".join(str(part) for part in parts).encode("utf-8")).hexdigest()[:16]


def _content_hash(payload: dict[str, Any]) -> str:
    clone = json.loads(stable_json(payload))
    clone.get("machine_proof", {}).pop("content_hash", None)
    return "sha256:" + hashlib.sha256(stable_json(clone).encode("utf-8")).hexdigest()


def private_mode_readiness_stub() -> dict[str, Any]:
    privacy = token_vault.privacy_readiness_status()
    return {
        "private_mode_available": True,
        "private_mode_active": False,
        "strict_private_mode_available": True,
        "strict_private_mode_active": False,
        "minimum_privacy_level_when_active": "CLIENT_FINANCE_FILE_METADATA",
        "cloud_lm_allowed_when_private": False,
        "local_only_required_when_strict": True,
        "live_lm_exposure_allowed": False,
        "privacy_readiness_status": privacy["privacy_readiness_status"],
        "production_token_vault_ready": privacy["production_token_vault_ready"],
        "operator_summary": privacy["operator_summary"],
        "next_safe_move": "Mission Control may expose this later as a local setting; backend defaults remain inactive.",
    }


def build_lm1_thread_context_package(
    *,
    source_request_id: str = "lm_readiness_capital_hilton_fixture",
    user_message: str = "these are the invoice workbooks for the clients named in the files, handle them how you're supposed to",
    file_display_name: str = "Invoice Capitol Hilton Running.xlsx",
    world_ref: str = "finance",
) -> dict[str, Any]:
    gate1_snapshot = gate1_operational_snapshot.build_gate1_operational_snapshot(
        {
            "source_request_id": source_request_id,
            "source_device_ref": "mission_control_mac",
            "thread_ref": "thread_ref:finance_capital_hilton",
            "user_message": user_message,
            "file_display_name": file_display_name,
            "file_extension": Path(file_display_name).suffix or ".xlsx",
            "file_type": "spreadsheet",
            "world_ref": world_ref,
        }
    )
    intake = gate1_snapshot["universal_intake_inference"]
    token_scope = "scope:finance:capital_hilton:lm_readiness_fixture"
    token_policy = gate1_snapshot["tokenization_policy"]
    privacy = token_vault.role_package_tokenization_declaration(token_scope)
    privacy = {
        **privacy,
        "privacy_level": token_policy["privacy_level"],
        "tokenization_required": token_policy["tokenization_required"],
        "model_may_see_raw_values": token_policy["model_may_see_raw_values"],
        "detokenization_allowed": token_policy["detokenization_allowed"],
        "local_only_required": token_policy["local_only_required"],
        "reason_codes": token_policy["reason_codes"],
        "token_vault_ref": "generated/read_models/token_vault_status.json",
    }
    package = LM1ThreadContextPackage(
        package_id=f"lm1_thread_context_package:{_short_hash(source_request_id, intake.get('candidate_id'))}",
        source_request_id=source_request_id,
        gate1_operational_snapshot_ref=gate1_snapshot["snapshot_id"],
        gate1_safe_to_package_for_lm1=bool(gate1_snapshot["safe_to_package_for_lm1"]),
        gate1_privacy_flags={
            "privacy_class": gate1_snapshot["privacy_class"],
            "tokenization_required": gate1_snapshot["tokenization_required"],
            "private_mode_active": gate1_snapshot["private_mode_effect"]["active"],
            "strict_private_mode_active": gate1_snapshot["strict_private_mode_effect"]["active"],
            "raw_values_included": gate1_snapshot["raw_values_included"],
            "safe_to_package_for_lm1": gate1_snapshot["safe_to_package_for_lm1"],
            "unsafe_reason": gate1_snapshot["unsafe_reason"],
        },
        source_device_ref=str(gate1_snapshot["source_device_ref"]),
        user_message=str(gate1_snapshot["user_message"]),
        current_world_ref=str(gate1_snapshot["world_ref"]),
        current_thread_ref=str(gate1_snapshot["thread_ref"]),
        universal_intake_inference=intake,
        privacy_classification=str(gate1_snapshot["privacy_class"]),
        tokenization_required=bool(token_policy["tokenization_required"]),
        tokenization_policy=token_policy,
        privacy=privacy,
        model_router_result={},
        allowed_context_classes=tuple(gate1_snapshot["allowed_context_classes"]),
        forbidden_context_classes=tuple(gate1_snapshot["forbidden_context_classes"]),
        output_schema=tuple(MachineIntentCandidate.__dataclass_fields__),
        raw_values_included=False,
        tools_allowed=(),
        authority_granted={
            "model_call": False,
            "tool_execution": False,
            "external_action": False,
            "send_submit": False,
            "workflow_execution": False,
        },
        next_safe_move="A future LM1 may propose MachineIntentCandidate JSON only; Gate 2 decides ingestion.",
    )
    package_dict = asdict(package)
    package_dict["gate1_operational_snapshot"] = gate1_snapshot
    package_dict["universal_intake_chain_contract"] = intake.get("chain_contract", {})
    package_dict["model_router_result"] = model_router_policy.select_for_lm1_thread_package(package_dict)
    return package_dict


def _candidate_from_lm1_package(package: Mapping[str, Any]) -> MachineIntentCandidate:
    intake = package.get("universal_intake_inference") if isinstance(package.get("universal_intake_inference"), Mapping) else {}
    operator_text = str(package.get("user_message") or "")
    wants_status = "what" in operator_text.lower() and ("next" in operator_text.lower() or "status" in operator_text.lower())
    return MachineIntentCandidate(
        intent_id=f"lm_readiness_candidate:{_short_hash(package.get('source_request_id'), intake.get('candidate_id'))}",
        source_request_id=str(package.get("source_request_id") or "lm_readiness_fixture"),
        original_operator_text=operator_text,
        inferred_intent_type="ANSWER_STATUS" if wants_status else "ATTACH_SOURCE_REF",
        target_world_ref=str(intake.get("world_ref") or "finance"),
        target_folder_ref=str(intake.get("client_ref") or "capital_hilton"),
        target_thread_ref=str(package.get("current_thread_ref") or "thread_ref:finance_capital_hilton"),
        target_workflow_ref=str(intake.get("workflow_ref") or "capital_hilton_invoice_workflow"),
        target_agent_role="CHIEF" if wants_status else "OPENCLAW_SYSTEM",
        target_worker_type="PC_CODEX",
        requested_action=(
            "Answer the next safe move for the Capital Hilton invoice from safe read-models."
            if wants_status
            else "Attach the running draft invoice workbook reference as metadata-only source context."
        ),
        referenced_next_action=(
            "Next: describe the next safe invoice step; do not send, submit, post, or mark final."
            if wants_status
            else "Next: register/resolve the workbook artifact through governed intake only."
        ),
        confidence="HIGH",
        ambiguity_status="UNAMBIGUOUS",
        required_clarification="",
        evidence_refs_used=(str(intake.get("candidate_id") or "universal_intake_candidate"),),
        context_refs_used=("tenant_scope:fixture_business_ops", str((package.get("privacy") or {}).get("token_scope") or "")),
        source_refs_used=(f"universal_intake:{intake.get('candidate_id')}",),
        missing_requirements=(),
        forbidden_assumptions=(),
        authority_requested={"send_submit": False, "external_action": False, "workflow_execution": False},
        authority_granted={"send_submit": False, "external_action": False, "workflow_execution": False},
        validation_required=True,
        next_safe_move="Run Gate 2 ingest; do not execute.",
    )


def build_representative_flow(*, generated_at: str = DEFAULT_GENERATED_AT) -> dict[str, Any]:
    lm1_package = build_lm1_thread_context_package(
        source_request_id="lm_readiness_capital_hilton_next_step_fixture",
        user_message="what's next for the Capital Hilton invoice?",
    )
    lm1_model_decision = lm1_package["model_router_result"]
    candidate = _candidate_from_lm1_package(lm1_package)
    package_payload = lm_intent_proposal_contract.build_payload(
        {
            "request_id": candidate.source_request_id,
            "operator_message": lm1_package["user_message"],
            "world_ref": candidate.target_world_ref,
            "client_ref": lm1_package["universal_intake_inference"]["client_ref"],
            "workflow_ref": candidate.target_workflow_ref,
        },
        generated_at=generated_at,
    )
    gate2_result = intent_ingest_gate.ingest_intent_proposal(candidate, package_payload=package_payload)
    gate2_readback = intent_ingest_gate.build_intent_ingest_readback(gate2_result, candidate)
    gate3_result = role_package_gate.compile_role_package(gate2_result)
    gate3_readback = role_package_gate.build_package_readback(gate3_result)
    role_package = gate3_result.get("role_execution_package") or {}
    lm2_model_decision = model_router_policy.select_for_lm2_role_package(role_package)
    lm2_response_candidate = {
        "source_request_id": candidate.source_request_id,
        "workflow_ref": candidate.target_workflow_ref,
        "client_ref": lm1_package["universal_intake_inference"]["client_ref"],
        "response_author": role_package.get("role_identity") or "OPENCLAW_SYSTEM",
        "selected_model_backend": "LM2_STUB_ONLY",
        "allowed_tools_plugins": (),
        "headline": "Capital Hilton next step",
        "one_line_answer": "OpenClaw can prepare a bounded next-step readback for the Capital Hilton invoice.",
        "eliwinship": "OpenClaw can review the safe invoice state and tell you the next move. This package only prepares a readback for Mission Control.",
        "next_action": "Next: keep the workbook as draft/source material, then use the whitelisted audit path after the operator chooses it.",
        "readback_files": ("generated/read_models/lm_readiness_dashboard.json",),
    }
    gate4_result = guardian_output_gate.validate_response_payload(lm2_response_candidate)
    return {
        "gate1_operational_snapshot": lm1_package["gate1_operational_snapshot"],
        "lm1_thread_context_package": lm1_package,
        "lm1_model_decision": lm1_model_decision,
        "lm1_fixture_candidate": asdict(candidate),
        "gate2_result": gate2_result,
        "gate2_readback": gate2_readback,
        "gate3_result": gate3_result,
        "gate3_readback": gate3_readback,
        "gate3_tokenization": {
            "tokenization_applied": bool(role_package.get("tokenization_applied")),
            "token_scope": role_package.get("token_scope"),
            "raw_values_included": bool(role_package.get("raw_values_included")),
            "token_vault_ref": role_package.get("token_vault_ref"),
            "detokenization_policy_ref": role_package.get("detokenization_policy_ref"),
            "privacy_level": role_package.get("privacy_level"),
            "model_may_see_raw_values": bool(role_package.get("model_may_see_raw_values")),
        },
        "lm2_model_decision": lm2_model_decision,
        "private_mode": private_mode_readiness_stub(),
        "lm2_response_candidate": lm2_response_candidate,
        "gate4_result": gate4_result,
    }


def build_payload(*, generated_at: str | None = None) -> dict[str, Any]:
    generated_at = generated_at or DEFAULT_GENERATED_AT
    representative = build_representative_flow(generated_at=generated_at)
    gate_chain = gate_chain_harness.run_harness(generated_at=generated_at, persist=True)
    trust_ramp = guardian_trust_ramp_simulator.run_trust_ramp(generated_at=generated_at, persist=True)
    shadow = shadow_lm_mode.build_payload(generated_at=generated_at, persist=True)
    provider_registry = provider_policy_registry.build_payload(generated_at=generated_at)
    model_router = model_router_policy.build_payload(generated_at=generated_at)
    readiness = live_lm_readiness_gate.build_payload(generated_at=generated_at)
    live_shadow_trial = live_lm_shadow_trial.latest_or_ready_payload(generated_at=generated_at)
    token_status = token_vault.build_payload(generated_at=generated_at)
    universal = universal_intake_contract.build_payload(generated_at=generated_at)
    gate1_snapshot_payload = gate1_operational_snapshot.build_payload(generated_at=generated_at)
    gate1_privacy = gate1_privacy_request_readiness.build_payload(generated_at=generated_at)
    bridge_readiness = request_response_bridge_readiness.build_payload(generated_at=generated_at)
    activation_requirements = live_lm_activation_requirements.build_payload(
        generated_at=generated_at,
        live_shadow_payload=live_shadow_trial,
    )
    private_policy = private_mode_policy_readiness.build_payload(generated_at=generated_at)
    mirror_visibility = read_model_mirror_visibility.build_payload(generated_at=generated_at)
    privacy_readiness = token_status["privacy_readiness"]
    universal_batch = universal["batch_examples"]["running_invoice_workbooks"]
    role_package = representative["gate3_result"].get("role_execution_package") or {}
    dashboard_summary = {
        "lm1_shadow": "READY" if readiness["machine_proof"]["lm1_shadow_ready"] else "NOT_READY",
        "lm1_shadow_comparison": "READY" if shadow["machine_proof"]["shadow_comparison_failed_count"] == 0 else "NOT_READY",
        "can_lm1_shadow_test": shadow["machine_proof"]["lm1_expected_actual_compared"],
        "lm1_live": "NOT_ACTIVE",
        "lm2_package_shadow": "READY" if readiness["machine_proof"]["lm2_shadow_ready"] else "NOT_READY",
        "lm2_shadow_comparison": "READY" if shadow["machine_proof"]["shadow_comparison_failed_count"] == 0 else "NOT_READY",
        "can_lm2_shadow_test": shadow["machine_proof"]["lm2_expected_actual_compared"],
        "lm2_live": "NOT_ACTIVE",
        "tokenization": "LOCAL_PRODUCTION_SUBSTRATE_READY_NO_REAL_DATA"
        if privacy_readiness["production_token_vault_ready"]
        else "SEEDED_NOT_PRODUCTION",
        "tokenization_policy": representative["lm1_thread_context_package"]["tokenization_policy"]["privacy_level"],
        "privacy_readiness_status": privacy_readiness["privacy_readiness_status"],
        "production_token_vault_ready": privacy_readiness["production_token_vault_ready"],
        "universal_intake": "SEEDED",
        "universal_intake_batch": "READY" if universal["machine_proof"]["batch_fixture_all_high_confidence"] else "NEEDS_CLARIFICATION",
        "model_router": "SEEDED",
        "provider_policy_registry": "SEEDED",
        "gate1_operational_snapshot": "EXPORTED_CONNECTED",
        "gate1_privacy_request": "EXPORTED",
        "lm1_thread_context_package": "CONNECTED_TO_GATE1",
        "request_response_bridge": bridge_readiness["readiness_status"],
        "production_live_blockers": "EXPLICIT",
        "production_activation_beams": "EXPLICIT_SEVEN_BEAMS",
        "provider_activation_receipts": activation_requirements["provider_activation_status"],
        "live_lm_shadow_trial": live_shadow_trial["trial_status"],
        "live_shadow_receipt": "PRESENT" if live_shadow_trial["machine_proof"]["live_shadow_receipt_valid"] else "MISSING",
        "private_mode_policy": private_policy["contract_status"],
        "read_model_mirror_visibility": mirror_visibility["contract_status"],
        "gate2_ingest": representative["gate2_result"].get("outcome"),
        "gate2_readback": "OPERATOR_VISIBLE",
        "gate3_package": representative["gate3_result"].get("package_status"),
        "gate3_package_readback": "OPERATOR_VISIBLE",
        "gate4_guardian": (representative["gate4_result"].get("validation_result") or {}).get("verdict"),
        "trust_ramp_candidate_level": trust_ramp["score"]["candidate_trust_level"],
        "trust_ramp_active_level": trust_ramp["score"]["active_trust_level"],
        "lm1_selected_provider": representative["lm1_model_decision"].get("selected_provider_ref"),
        "lm2_selected_provider": representative["lm2_model_decision"].get("selected_provider_ref"),
        "next_blockers": (
            *activation_requirements["hard_blockers"],
            "private/strict-private mode product switch",
        ),
        "next_safe_move": "Keep running fixture/shadow comparisons and wire product confirmation surfaces only where the gates ask for missing privacy, scope, or approval.",
    }
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "contract_status": CONTRACT_STATUS,
        "generated_at": generated_at,
        "dashboard_summary": dashboard_summary,
        "representative_request": {
            "filename": "Invoice Capitol Hilton Running.xlsx",
            "user_note": "what's next for the Capital Hilton invoice?",
            "world_ref": "finance",
            "source_request_id": representative["lm1_thread_context_package"]["source_request_id"],
        },
        "representative_flow": {
            "universal_intake_inference": representative["lm1_thread_context_package"]["universal_intake_inference"],
            "privacy": representative["lm1_thread_context_package"]["privacy"],
            "tokenization_policy_result": representative["lm1_thread_context_package"]["tokenization_policy"],
            "privacy_readiness_result": privacy_readiness,
            "private_mode_readiness": representative["private_mode"],
            "private_mode_policy_readiness": {
                "read_model_ref": "generated/read_models/private_mode_policy_readiness.json",
                "contract_status": private_policy["contract_status"],
                "active_state": private_policy["active_state"],
                "package_effect_summary": private_policy["package_effect_summary"],
            },
            "live_lm_activation_requirements": {
                "read_model_ref": "generated/read_models/live_lm_activation_requirements.json",
                "contract_status": activation_requirements["contract_status"],
                "live_lm1_activation_status": activation_requirements["live_lm1_activation_status"],
                "live_lm2_activation_status": activation_requirements["live_lm2_activation_status"],
                "provider_activation_status": activation_requirements["provider_activation_status"],
                "missing_receipts": activation_requirements["missing_receipts"],
                "production_activation_beams": activation_requirements["production_activation_beams"],
                "activation_receipt_substrate": activation_requirements["activation_receipt_substrate"],
                "activation_receipt_contracts": activation_requirements["activation_receipt_contracts"],
                "activation_receipt_fixture_results": activation_requirements["activation_receipt_fixture_results"],
                "live_shadow_receipt": activation_requirements["live_shadow_receipt"],
                "shadow_test_receipts": activation_requirements["shadow_test_receipts"],
            },
            "live_lm_shadow_trial": {
                "read_model_ref": "generated/read_models/live_lm_shadow_trial.json",
                "trial_status": live_shadow_trial["trial_status"],
                "provider_class": live_shadow_trial["machine_proof"]["provider_class"],
                "model_ref": live_shadow_trial["machine_proof"]["model_ref"],
                "live_model_call_performed": live_shadow_trial["machine_proof"]["live_model_call_performed"],
                "live_shadow_receipt_valid": live_shadow_trial["machine_proof"]["live_shadow_receipt_valid"],
            },
            "read_model_mirror_visibility": {
                "read_model_ref": "generated/read_models/read_model_mirror_visibility.json",
                "contract_status": mirror_visibility["contract_status"],
                "mirror_policy": mirror_visibility["mirror_policy"],
            },
            "gate1_privacy_request_readiness": {
                "read_model_ref": "generated/read_models/gate1_privacy_request_readiness.json",
                "contract_status": gate1_privacy["contract_status"],
                "chain_contract": gate1_privacy["chain_contract"],
                "operator_summary": gate1_privacy["operator_summary"],
            },
            "gate1_operational_snapshot": {
                "read_model_ref": "generated/read_models/gate1_operational_snapshot.json",
                "contract_status": gate1_snapshot_payload["contract_status"],
                "chain_contract": gate1_snapshot_payload["chain_contract"],
                "snapshot_id": representative["gate1_operational_snapshot"]["snapshot_id"],
                "safe_to_package_for_lm1": representative["gate1_operational_snapshot"]["safe_to_package_for_lm1"],
            },
            "request_response_bridge_readiness": {
                "read_model_ref": "generated/read_models/request_response_bridge_readiness.json",
                "readiness_status": bridge_readiness["readiness_status"],
                "bridge_contract": bridge_readiness["bridge_contract"],
                "safe_delivery_policy": bridge_readiness["safe_delivery_policy"],
            },
            "universal_intake_batch_fixture": universal_batch,
            "lm1_thread_context_package": representative["lm1_thread_context_package"],
            "lm1_model_decision": representative["lm1_model_decision"],
            "gate2_result_summary": {
                "outcome": representative["gate2_result"].get("outcome"),
                "accepted_intent": representative["gate2_result"].get("accepted_intent"),
                "blocker_reasons": representative["gate2_result"].get("blocker_reasons"),
                "operator_readback": representative["gate2_readback"],
            },
            "gate3_package_summary": {
                "package_status": representative["gate3_result"].get("package_status"),
                "package_id": role_package.get("package_id"),
                "role_identity": role_package.get("role_identity"),
                "operator_readback": representative["gate3_readback"],
                "tokenization_applied": role_package.get("tokenization_applied"),
                "token_scope": role_package.get("token_scope"),
                "raw_values_included": role_package.get("raw_values_included"),
                "token_vault_ref": role_package.get("token_vault_ref"),
                "detokenization_policy_ref": role_package.get("detokenization_policy_ref"),
                "privacy_level": role_package.get("privacy_level"),
                "model_may_see_raw_values": role_package.get("model_may_see_raw_values"),
                "allowed_tools": (role_package.get("tool_policy") or {}).get("allowed_tools", ()),
                "forbidden_tools": (role_package.get("tool_policy") or {}).get("forbidden_tools", ()),
            },
            "lm2_model_decision": representative["lm2_model_decision"],
            "provider_policy_decisions": {
                "lm1": provider_policy_registry.select_provider_candidate(
                    {
                        "request_id": "dashboard_lm1_provider_policy",
                        "chain_lane": "LM1_INTENT_PROPOSAL",
                        "desired_model_class": representative["lm1_model_decision"]["selected_model_class"],
                        "privacy_level": representative["lm1_thread_context_package"]["privacy_classification"],
                        "context_classes": (representative["lm1_thread_context_package"]["privacy_classification"],),
                        "tokenization_applied": True,
                        "raw_values_included": False,
                        "local_only_required": True,
                        "requires_structured_output": True,
                    }
                ),
                "lm2": provider_policy_registry.select_provider_candidate(
                    {
                        "request_id": "dashboard_lm2_provider_policy",
                        "chain_lane": "LM2_ROLE_RESPONSE",
                        "desired_model_class": representative["lm2_model_decision"]["selected_model_class"],
                        "privacy_level": role_package.get("privacy_level") or "TOKENIZED_METADATA",
                        "context_classes": ("TOKENIZED_METADATA",),
                        "tokenization_applied": True,
                        "raw_values_included": False,
                        "local_only_required": False,
                        "requires_structured_output": True,
                    }
                ),
            },
            "what_would_be_sent_to_lm1": {
                "package_id": representative["lm1_thread_context_package"]["package_id"],
                "source_request_id": representative["lm1_thread_context_package"]["source_request_id"],
                "gate1_operational_snapshot_ref": representative["lm1_thread_context_package"][
                    "gate1_operational_snapshot_ref"
                ],
                "gate1_privacy_flags": representative["lm1_thread_context_package"]["gate1_privacy_flags"],
                "user_message": representative["lm1_thread_context_package"]["user_message"],
                "universal_intake_inference": representative["lm1_thread_context_package"]["universal_intake_inference"],
                "universal_intake_chain_contract": representative["lm1_thread_context_package"].get("universal_intake_chain_contract", {}),
                "privacy": representative["lm1_thread_context_package"]["privacy"],
                "allowed_context_classes": representative["lm1_thread_context_package"]["allowed_context_classes"],
                "forbidden_context_classes": representative["lm1_thread_context_package"]["forbidden_context_classes"],
                "output_schema": representative["lm1_thread_context_package"]["output_schema"],
                "tools_allowed": representative["lm1_thread_context_package"]["tools_allowed"],
                "authority_granted": representative["lm1_thread_context_package"]["authority_granted"],
            },
            "what_would_be_sent_to_lm2": {
                "role_package_summary": {
                    "package_id": role_package.get("package_id"),
                    "role_identity": role_package.get("role_identity"),
                    "task": role_package.get("task"),
                    "context_packet": role_package.get("context_packet"),
                    "tool_policy": role_package.get("tool_policy"),
                    "authority_policy": role_package.get("authority_policy"),
                    "tokenization_applied": role_package.get("tokenization_applied"),
                    "privacy_level": role_package.get("privacy_level"),
                    "raw_values_included": role_package.get("raw_values_included"),
                    "model_may_see_raw_values": role_package.get("model_may_see_raw_values"),
                }
            },
            "gate4_result_summary": representative["gate4_result"].get("validation_result"),
            "shadow_comparison_summary": shadow["shadow_run"]["shadow_comparison_summary"],
        },
        "aggregated_lanes": {
            "gate_chain_harness": {
                "read_model_id": gate_chain_harness.READ_MODEL_ID,
                "summary": gate_chain.get("summary", {}),
            },
            "guardian_trust_ramp_simulator": {
                "read_model_id": guardian_trust_ramp_simulator.READ_MODEL_ID,
                "score": trust_ramp.get("score", {}),
            },
            "model_router_policy": {
                "read_model_id": model_router_policy.READ_MODEL_ID,
                "machine_proof": model_router.get("machine_proof", {}),
            },
            "provider_policy_registry": {
                "read_model_id": provider_policy_registry.READ_MODEL_ID,
                "machine_proof": provider_registry.get("machine_proof", {}),
            },
            "live_lm_readiness_gate": {
                "read_model_id": live_lm_readiness_gate.READ_MODEL_ID,
                "machine_proof": readiness.get("machine_proof", {}),
            },
            "shadow_lm_mode": {
                "read_model_id": shadow_lm_mode.READ_MODEL_ID,
                "machine_proof": shadow.get("machine_proof", {}),
            },
            "token_vault_status": {
                "read_model_id": token_vault.READ_MODEL_ID,
                "machine_proof": token_status.get("machine_proof", {}),
            },
            "universal_intake_contract": {
                "read_model_id": universal_intake_contract.READ_MODEL_ID,
                "machine_proof": universal.get("machine_proof", {}),
            },
            "live_lm_activation_requirements": {
                "read_model_id": live_lm_activation_requirements.READ_MODEL_ID,
                "machine_proof": activation_requirements.get("machine_proof", {}),
            },
            "live_lm_shadow_trial": {
                "read_model_id": live_lm_shadow_trial.READ_MODEL_ID,
                "machine_proof": live_shadow_trial.get("machine_proof", {}),
            },
            "private_mode_policy_readiness": {
                "read_model_id": private_mode_policy_readiness.READ_MODEL_ID,
                "machine_proof": private_policy.get("machine_proof", {}),
            },
            "read_model_mirror_visibility": {
                "read_model_id": read_model_mirror_visibility.READ_MODEL_ID,
                "machine_proof": mirror_visibility.get("machine_proof", {}),
            },
            "gate1_privacy_request_readiness": {
                "read_model_id": gate1_privacy_request_readiness.READ_MODEL_ID,
                "machine_proof": gate1_privacy.get("machine_proof", {}),
            },
            "gate1_operational_snapshot": {
                "read_model_id": gate1_operational_snapshot.READ_MODEL_ID,
                "machine_proof": gate1_snapshot_payload.get("machine_proof", {}),
            },
            "request_response_bridge_readiness": {
                "read_model_id": request_response_bridge_readiness.READ_MODEL_ID,
                "machine_proof": bridge_readiness.get("machine_proof", {}),
            },
        },
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "machine_proof": {
            "dashboard_aggregates_seeded_lanes": True,
            "lm1_package_built": True,
            "lm1_package_raw_values_included": representative["lm1_thread_context_package"]["raw_values_included"],
            "lm1_package_tokenization_required": representative["lm1_thread_context_package"]["tokenization_required"],
            "tokenization_policy_blocks_raw_model_visibility": representative["lm1_thread_context_package"]["tokenization_policy"][
                "model_may_see_raw_values"
            ]
            is False,
            "private_mode_fields_present": True,
            "live_activation_requirements_aggregated": True,
            "production_activation_beams_explicit": activation_requirements["machine_proof"][
                "production_activation_beams_explicit"
            ],
            "production_activation_beam_count": activation_requirements["machine_proof"]["production_activation_beam_count"],
            "activation_receipt_contract_count": activation_requirements["machine_proof"]["activation_receipt_contract_count"],
            "activation_receipt_contracts_ready": activation_requirements["machine_proof"]["activation_receipt_contracts_ready"],
            "activation_receipt_fixtures_valid": activation_requirements["machine_proof"]["activation_receipt_fixtures_valid"],
            "activation_receipt_fixtures_satisfy_production": activation_requirements["machine_proof"][
                "activation_receipt_fixtures_satisfy_production"
            ],
            "activation_receipt_substrate_contracts_backed": activation_requirements["machine_proof"][
                "activation_receipt_substrate_contracts_backed"
            ],
            "activation_receipt_substrate_fixtures_backed": activation_requirements["machine_proof"][
                "activation_receipt_substrate_fixtures_backed"
            ],
            "activation_receipt_substrate_satisfies_production": activation_requirements["machine_proof"][
                "activation_receipt_substrate_satisfies_production"
            ],
            "live_lm_shadow_trial_aggregated": True,
            "live_shadow_trial_status": live_shadow_trial["trial_status"],
            "live_shadow_model_call_recorded": live_shadow_trial["machine_proof"]["live_model_call_performed"],
            "live_shadow_receipt_valid": live_shadow_trial["machine_proof"]["live_shadow_receipt_valid"],
            "shadow_provider_policy_receipt_present": activation_requirements["machine_proof"][
                "shadow_provider_policy_receipt_present"
            ],
            "shadow_model_selection_receipt_present": activation_requirements["machine_proof"][
                "shadow_model_selection_receipt_present"
            ],
            "provider_activation_receipts_required": activation_requirements["machine_proof"]["provider_activation_receipts_required"],
            "provider_activation_receipts_present": activation_requirements["machine_proof"]["provider_activation_receipts_present"],
            "private_mode_policy_readiness_aggregated": True,
            "private_mode_policy_active": private_policy["private_mode_active"],
            "strict_private_mode_policy_active": private_policy["strict_private_mode_active"],
            "read_model_mirror_visibility_aggregated": True,
            "read_model_mirror_visibility_mac_visible_guaranteed": mirror_visibility["machine_proof"]["mac_visible_guaranteed"],
            "gate1_privacy_request_readiness_aggregated": True,
            "gate1_operational_snapshot_aggregated": True,
            "gate1_snapshot_connected_to_lm1_package": representative["lm1_thread_context_package"][
                "gate1_operational_snapshot_ref"
            ]
            == representative["gate1_operational_snapshot"]["snapshot_id"],
            "lm1_package_connected_to_gate1": representative["lm1_thread_context_package"]["gate1_safe_to_package_for_lm1"],
            "gate2_readback_operator_visible": bool(representative["gate2_readback"]["plain_language_meaning"]),
            "gate3_readback_operator_visible": bool(representative["gate3_readback"]["operator_message"]),
            "end_to_end_non_live_chain_passed": representative["gate2_result"].get("outcome") == intent_ingest_gate.ACCEPTED_INTENT
            and representative["gate3_result"].get("package_status") == role_package_gate.PACKAGE_COMPILED
            and (representative["gate4_result"].get("validation_result") or {}).get("verdict") == guardian_output_gate.VALIDATED,
            "request_response_bridge_readiness_aggregated": True,
            "request_response_bridge_ready_for_live_review": bridge_readiness["bridge_contract"]["ready_for_live_review"],
            "private_mode_active": representative["private_mode"]["private_mode_active"],
            "strict_private_mode_active": representative["private_mode"]["strict_private_mode_active"],
            "cloud_lm_allowed_when_private": representative["private_mode"]["cloud_lm_allowed_when_private"],
            "production_token_vault_ready": privacy_readiness["production_token_vault_ready"],
            "synthetic_tokenization_ready": privacy_readiness["synthetic_tokenization_ready"],
            "provider_policy_registry_aggregated": True,
            "provider_policy_lm1_selected": bool(representative["lm1_model_decision"].get("selected_provider_ref")),
            "provider_policy_lm2_selected": bool(representative["lm2_model_decision"].get("selected_provider_ref")),
            "shadow_comparison_failed_count": shadow["machine_proof"]["shadow_comparison_failed_count"],
            "universal_intake_batch_count": len(universal_batch["candidates"]),
            "universal_intake_batch_draft_source_only": universal["machine_proof"]["batch_fixture_all_draft_source_only"],
            "gate3_tokenization_fields_present": bool(role_package.get("token_vault_ref")),
            "gate3_model_may_see_raw_values": bool(role_package.get("model_may_see_raw_values")),
            "lm1_model_class_selected": representative["lm1_model_decision"]["selected_model_class"],
            "lm2_model_class_selected": representative["lm2_model_decision"]["selected_model_class"],
            "live_lm_status": "NOT_ACTIVE",
            "workbook_body_read_performed": False,
            "spreadsheet_cell_read_performed": False,
            "model_call_performed": False,
            "network_performed": False,
            "tool_execution_performed": False,
            "external_action_performed": False,
            "production_state_mutation_performed": False,
            "all_live_authority_false": all(value is False for value in AUTHORITY_BOUNDARY.values()),
            "content_hash": "",
        },
    }
    payload["machine_proof"]["content_hash"] = _content_hash(payload)
    return payload


def write_exports(payload: Mapping[str, Any], export_root: Path = DEFAULT_EXPORT_ROOT) -> tuple[Path, Path]:
    export_root.mkdir(parents=True, exist_ok=True)
    json_path = export_root / JSON_EXPORT_NAME
    operator_path = export_root / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    summary = payload.get("dashboard_summary", {})
    lines = [
        "# LM Readiness Dashboard",
        "",
        f"Status: {CONTRACT_STATUS}",
        f"LM1 shadow: {summary.get('lm1_shadow')}",
        f"LM1 shadow comparison: {summary.get('lm1_shadow_comparison')}",
        f"LM1 live: {summary.get('lm1_live')}",
        f"LM2 package shadow: {summary.get('lm2_package_shadow')}",
        f"LM2 shadow comparison: {summary.get('lm2_shadow_comparison')}",
        f"LM2 live: {summary.get('lm2_live')}",
        f"Tokenization: {summary.get('tokenization')}",
        f"Privacy readiness: {summary.get('privacy_readiness_status')}",
        f"Provider policy registry: {summary.get('provider_policy_registry')}",
        f"Gate 1 operational snapshot: {summary.get('gate1_operational_snapshot')}",
        f"Gate 1 privacy request: {summary.get('gate1_privacy_request')}",
        f"LM1 thread package: {summary.get('lm1_thread_context_package')}",
        f"Request-response bridge: {summary.get('request_response_bridge')}",
        f"Production/live blockers: {summary.get('production_live_blockers')}",
        f"Provider activation receipts: {summary.get('provider_activation_receipts')}",
        f"Live shadow trial: {summary.get('live_lm_shadow_trial')}",
        f"Live shadow receipt: {summary.get('live_shadow_receipt')}",
        f"Private Mode policy: {summary.get('private_mode_policy')}",
        f"Read-model visibility: {summary.get('read_model_mirror_visibility')}",
        f"Universal intake batch: {summary.get('universal_intake_batch')}",
        f"Gate 2: {summary.get('gate2_ingest')}",
        f"Gate 2 readback: {summary.get('gate2_readback')}",
        f"Gate 3: {summary.get('gate3_package')}",
        f"Gate 3 readback: {summary.get('gate3_package_readback')}",
        f"Gate 4: {summary.get('gate4_guardian')}",
        "",
        "Private Mode backend policy exists, but production token vault is not active yet.",
        "This dashboard integrates readiness contracts only. Live LM calls remain off.",
    ]
    operator_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return json_path, operator_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export LM readiness dashboard read-model.")
    parser.add_argument("--export-root", type=Path, default=DEFAULT_EXPORT_ROOT)
    parser.add_argument("--generated-at", default=DEFAULT_GENERATED_AT)
    parser.add_argument("--format", choices=("summary", "json"), default="summary")
    args = parser.parse_args(argv)

    payload = build_payload(generated_at=args.generated_at)
    json_path, operator_path = write_exports(payload, args.export_root)
    if args.format == "json":
        print(stable_json(payload), end="")
    else:
        print(
            stable_json(
                {
                    "read_model_id": READ_MODEL_ID,
                    "json_path": json_path.as_posix(),
                    "operator_path": operator_path.as_posix(),
                    **payload["dashboard_summary"],
                    "lm1_model_class": payload["machine_proof"]["lm1_model_class_selected"],
                    "lm2_model_class": payload["machine_proof"]["lm2_model_class_selected"],
                }
            ),
            end="",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
