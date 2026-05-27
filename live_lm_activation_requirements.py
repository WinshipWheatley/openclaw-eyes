"""Live LM activation requirements v0.

Read-only blocker/receipt contract for future LM1/LM2 activation. It makes the
remaining live-model blockers explicit without enabling models, providers,
tools, or production actions.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping

import live_lm_shadow_trial
import token_vault


DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_GENERATED_AT = "2026-05-26T00:00:00+00:00"

SCHEMA_VERSION = "live_lm_activation_requirements_v0"
READ_MODEL_ID = "live_lm_activation_requirements"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
OPERATOR_EXPORT_NAME = f"{READ_MODEL_ID}_OPERATOR.md"
CONTRACT_STATUS = "LIVE_LM_ACTIVATION_BLOCKED_REQUIREMENTS_MISSING"

AUTHORITY_BOUNDARY = {
    "live_lm_call_allowed": False,
    "model_api_integration_allowed": False,
    "provider_key_material_access_allowed": False,
    "network_allowed": False,
    "tool_execution_allowed": False,
    "agent_dispatch_allowed": False,
    "worker_dispatch_allowed": False,
    "workflow_execution_allowed": False,
    "external_action_allowed": False,
    "send_submit_allowed": False,
    "approval_execution_allowed": False,
    "ledger_posting_allowed": False,
    "production_state_mutation_allowed": False,
}


@dataclass(frozen=True)
class ActivationReceiptRequirement:
    receipt_id: str
    receipt_type: str
    human_label: str
    required_for_lanes: tuple[str, ...]
    present: bool
    blocks_live_lm1: bool
    blocks_live_lm2: bool
    blocks_provider_activation: bool
    operator_copy: str
    next_safe_move: str


@dataclass(frozen=True)
class ActivationReceiptContract:
    receipt_type: str
    beam_id: str
    human_label: str
    receipt_contract_status: str
    can_be_collected_without_live_authority: bool
    required_true_controls: tuple[str, ...]
    required_false_controls: tuple[str, ...]
    production_receipt_required: bool
    operator_approval_required: bool
    governed_review_required: bool
    fixture_validation_allowed: bool
    blocks_live_lm1: bool
    blocks_live_lm2: bool
    authority_boundary: dict[str, bool]
    operator_copy: str
    next_safe_move: str


@dataclass(frozen=True)
class ActivationReceiptValidationResult:
    receipt_type: str
    validation_status: str
    valid_for_contract: bool
    valid_as_test_fixture: bool
    satisfies_production_activation: bool
    missing_true_controls: tuple[str, ...]
    unsafe_true_controls: tuple[str, ...]
    production_receipt_present: bool
    operator_approved: bool
    governed_review_source: bool
    authority_boundary: dict[str, bool]
    next_safe_move: str


PRODUCTION_ACTIVATION_BEAM_SPECS: tuple[dict[str, Any], ...] = (
    {
        "beam_id": "production_token_vault",
        "human_label": "Production token vault",
        "receipt_types": ("production_token_vault_ready_receipt",),
        "status": "MISSING",
        "operator_copy": "OpenClaw needs the production token vault to be ready before live model lanes can review sensitive work.",
    },
    {
        "beam_id": "provider_model_receipts",
        "human_label": "Provider/model receipts",
        "receipt_types": ("provider_policy_receipt", "model_selection_policy_receipt"),
        "status": "MISSING",
        "operator_copy": "OpenClaw needs recorded provider and model-selection receipts for each live lane.",
    },
    {
        "beam_id": "live_enablement_receipt",
        "human_label": "Live enablement receipt",
        "receipt_types": ("live_model_enablement_receipt",),
        "status": "MISSING",
        "operator_copy": "OpenClaw needs an explicit live enablement receipt before LM1 or LM2 can leave shadow mode.",
    },
    {
        "beam_id": "privacy_receipt",
        "human_label": "Privacy receipt",
        "receipt_types": ("privacy_policy_receipt",),
        "status": "MISSING",
        "operator_copy": "OpenClaw needs a production privacy receipt before live model-shaped packages can be used.",
    },
    {
        "beam_id": "rollback_disable_receipt",
        "human_label": "Rollback/disable receipt",
        "receipt_types": ("rollback_disable_receipt",),
        "status": "MISSING",
        "operator_copy": "OpenClaw needs a proven way to disable live model lanes before activation review.",
    },
    {
        "beam_id": "device_trust_live_activation",
        "human_label": "Device trust / live activation",
        "receipt_types": ("device_trust_live_activation_receipt",),
        "status": "MISSING",
        "operator_copy": "OpenClaw needs trusted-device and live-activation proof for Mission Control traffic before it can feed live model lanes.",
    },
    {
        "beam_id": "real_lm_production_policy",
        "human_label": "Real LM1/LM2 production policy",
        "receipt_types": ("real_lm1_production_policy_receipt", "real_lm2_production_policy_receipt"),
        "status": "MISSING",
        "operator_copy": "OpenClaw needs a real LM1/LM2 production policy for routing, privacy, fallback, and rollback before live activation review.",
    },
)


REMAINING_RECEIPT_CONTRACT_SPECS: tuple[dict[str, Any], ...] = (
    {
        "receipt_type": "provider_policy_receipt",
        "beam_id": "provider_model_receipts",
        "human_label": "Provider policy receipt",
        "blocks": ("LM1", "LM2"),
        "required_true_controls": (
            "provider_policy_defined",
            "allowed_context_classes_declared",
            "forbidden_context_classes_declared",
            "provider_key_access_denied",
            "network_authority_denied",
        ),
        "required_false_controls": (
            "provider_key_material_included",
            "provider_api_call_enabled",
            "live_lm_call_enabled",
            "network_enabled",
        ),
        "operator_copy": "Provider policy can be reviewed without activating any provider or API key.",
    },
    {
        "receipt_type": "model_selection_policy_receipt",
        "beam_id": "provider_model_receipts",
        "human_label": "Model selection policy receipt",
        "blocks": ("LM1", "LM2"),
        "required_true_controls": (
            "lm1_model_class_policy_defined",
            "lm2_model_class_policy_defined",
            "fallback_model_class_defined",
            "model_self_selection_denied",
            "structured_output_requirement_defined",
        ),
        "required_false_controls": (
            "model_call_performed",
            "runtime_model_router_enabled",
            "provider_api_call_enabled",
            "live_lm_call_enabled",
        ),
        "operator_copy": "Model-selection policy can be checked as metadata without calling a model.",
    },
    {
        "receipt_type": "live_model_enablement_receipt",
        "beam_id": "live_enablement_receipt",
        "human_label": "Live enablement receipt",
        "blocks": ("LM1", "LM2"),
        "required_true_controls": (
            "explicit_operator_enablement_required",
            "default_state_not_active",
            "all_other_receipts_required_first",
            "operator_visible_status_required",
        ),
        "required_false_controls": (
            "live_lm_enabled_by_receipt_shape",
            "provider_api_call_enabled",
            "tool_execution_enabled",
            "production_state_mutation_enabled",
        ),
        "operator_copy": "Live enablement has a receipt shape, but the shape itself cannot enable live models.",
    },
    {
        "receipt_type": "rollback_disable_receipt",
        "beam_id": "rollback_disable_receipt",
        "human_label": "Rollback/disable receipt",
        "blocks": ("LM1", "LM2"),
        "required_true_controls": (
            "disable_switch_defined",
            "rollback_path_defined",
            "operator_visible_disable_defined",
            "audit_log_required",
            "default_disable_available",
        ),
        "required_false_controls": (
            "rollback_requires_provider_access",
            "disable_depends_on_network",
            "production_state_mutation_enabled",
            "live_lm_call_enabled",
        ),
        "operator_copy": "Rollback and disable controls can be reviewed before any live model activation.",
    },
    {
        "receipt_type": "device_trust_live_activation_receipt",
        "beam_id": "device_trust_live_activation",
        "human_label": "Device trust / live activation receipt",
        "blocks": ("Gate 1", "LM1", "LM2"),
        "required_true_controls": (
            "trusted_device_registry_required",
            "source_device_binding_required",
            "thread_scope_binding_required",
            "request_replay_protection_required",
            "scoped_response_route_required",
        ),
        "required_false_controls": (
            "untrusted_device_activation_allowed",
            "arbitrary_destination_allowed",
            "lm_inferred_routing_allowed",
            "live_lm_call_enabled",
        ),
        "operator_copy": "Device trust can be shaped as a receipt without granting live activation.",
    },
    {
        "receipt_type": "real_lm1_production_policy_receipt",
        "beam_id": "real_lm_production_policy",
        "human_label": "Real LM1 production policy receipt",
        "blocks": ("LM1",),
        "required_true_controls": (
            "lm1_intent_only_policy_defined",
            "machine_intent_candidate_schema_required",
            "gate2_ingest_required",
            "privacy_minimization_required",
            "lm1_no_tool_authority_defined",
        ),
        "required_false_controls": (
            "lm1_can_execute_tools",
            "lm1_can_grant_authority",
            "lm1_can_dispatch_workers",
            "raw_sensitive_values_allowed",
        ),
        "operator_copy": "LM1 production policy can be reviewed as intent-proposal-only, with no tool or authority path.",
    },
    {
        "receipt_type": "real_lm2_production_policy_receipt",
        "beam_id": "real_lm_production_policy",
        "human_label": "Real LM2 production policy receipt",
        "blocks": ("LM2",),
        "required_true_controls": (
            "lm2_role_package_policy_defined",
            "gate3_package_required",
            "guardian_gate_required",
            "forbidden_tools_explicit",
            "no_send_submit_without_receipts",
        ),
        "required_false_controls": (
            "lm2_can_bypass_guardian",
            "lm2_can_send_submit_without_receipt",
            "lm2_can_post_ledger",
            "raw_sensitive_values_allowed",
        ),
        "operator_copy": "LM2 production policy can be reviewed as package-bound role response, with Guardian still behind it.",
    },
)


def production_activation_beams(
    *,
    token_vault_receipt_present: bool = False,
    privacy_policy_receipt_present: bool = False,
    receipt_contracts_ready: bool = False,
) -> tuple[dict[str, Any], ...]:
    statuses = {
        "production_token_vault": "PRESENT" if token_vault_receipt_present else "MISSING",
        "privacy_receipt": "PRESENT" if privacy_policy_receipt_present else "MISSING",
    }
    if receipt_contracts_ready:
        for beam_id in (
            "provider_model_receipts",
            "live_enablement_receipt",
            "rollback_disable_receipt",
            "device_trust_live_activation",
            "real_lm_production_policy",
        ):
            statuses[beam_id] = "RECEIPT_CONTRACT_READY_PRODUCTION_RECEIPT_MISSING"
    return tuple({**item, "status": statuses.get(str(item["beam_id"]), item["status"])} for item in PRODUCTION_ACTIVATION_BEAM_SPECS)


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _short_hash(*parts: object) -> str:
    return hashlib.sha256("\0".join(str(part) for part in parts).encode("utf-8")).hexdigest()[:16]


def _content_hash(payload: dict[str, Any]) -> str:
    clone = json.loads(stable_json(payload))
    clone.get("machine_proof", {}).pop("content_hash", None)
    return "sha256:" + hashlib.sha256(stable_json(clone).encode("utf-8")).hexdigest()


def activation_receipt_contracts() -> tuple[dict[str, Any], ...]:
    contracts: list[dict[str, Any]] = []
    for spec in REMAINING_RECEIPT_CONTRACT_SPECS:
        blocks = tuple(spec["blocks"])
        contracts.append(
            asdict(
                ActivationReceiptContract(
                    receipt_type=str(spec["receipt_type"]),
                    beam_id=str(spec["beam_id"]),
                    human_label=str(spec["human_label"]),
                    receipt_contract_status="RECEIPT_CONTRACT_READY_PRODUCTION_RECEIPT_MISSING",
                    can_be_collected_without_live_authority=True,
                    required_true_controls=tuple(spec["required_true_controls"]),
                    required_false_controls=tuple(spec["required_false_controls"]),
                    production_receipt_required=True,
                    operator_approval_required=True,
                    governed_review_required=True,
                    fixture_validation_allowed=True,
                    blocks_live_lm1="LM1" in blocks,
                    blocks_live_lm2="LM2" in blocks,
                    authority_boundary=dict(AUTHORITY_BOUNDARY),
                    operator_copy=str(spec["operator_copy"]),
                    next_safe_move="Use this contract for review/test receipts only; do not mark production-present without governed approval.",
                )
            )
        )
    return tuple(contracts)


def activation_receipt_contract_by_type(receipt_type: str) -> dict[str, Any]:
    for contract in activation_receipt_contracts():
        if contract["receipt_type"] == receipt_type:
            return contract
    raise ValueError(f"unknown activation receipt type: {receipt_type}")


def _fixture_candidate_for_contract(contract: Mapping[str, Any]) -> dict[str, Any]:
    candidate = {
        "receipt_type": contract["receipt_type"],
        "test_fixture": True,
        "production_receipt": False,
        "operator_approved": False,
        "receipt_source": "test_fixture",
    }
    candidate.update({name: True for name in contract["required_true_controls"]})
    candidate.update({name: False for name in contract["required_false_controls"]})
    return candidate


def validate_activation_receipt_candidate(receipt_type: str, candidate: Mapping[str, Any]) -> dict[str, Any]:
    contract = activation_receipt_contract_by_type(receipt_type)
    missing_true = tuple(name for name in contract["required_true_controls"] if bool(candidate.get(name, False)) is not True)
    unsafe_true = tuple(name for name in contract["required_false_controls"] if bool(candidate.get(name, False)) is not False)
    valid_for_contract = not missing_true and not unsafe_true
    test_fixture = bool(candidate.get("test_fixture", False))
    production_receipt = bool(candidate.get("production_receipt", False))
    operator_approved = bool(candidate.get("operator_approved", False))
    governed_review_source = str(candidate.get("receipt_source") or "") == "governed_production_review"
    satisfies_production = valid_for_contract and production_receipt and operator_approved and governed_review_source
    result = ActivationReceiptValidationResult(
        receipt_type=receipt_type,
        validation_status=(
            "VALID_TEST_FIXTURE_ONLY"
            if valid_for_contract and test_fixture and not satisfies_production
            else "VALID_PRODUCTION_RECEIPT"
            if satisfies_production
            else "INVALID_RECEIPT_CANDIDATE"
        ),
        valid_for_contract=valid_for_contract,
        valid_as_test_fixture=valid_for_contract and test_fixture,
        satisfies_production_activation=satisfies_production,
        missing_true_controls=missing_true,
        unsafe_true_controls=unsafe_true,
        production_receipt_present=production_receipt,
        operator_approved=operator_approved,
        governed_review_source=governed_review_source,
        authority_boundary=dict(AUTHORITY_BOUNDARY),
        next_safe_move=(
            "Treat this as fixture proof only; collect a governed production receipt before activation."
            if valid_for_contract and not satisfies_production
            else "Keep live models off until every activation receipt is present."
            if satisfies_production
            else "Repair missing or unsafe controls before this receipt can be considered."
        ),
    )
    return asdict(result)


def activation_receipt_contract_fixture_results() -> tuple[dict[str, Any], ...]:
    return tuple(
        validate_activation_receipt_candidate(contract["receipt_type"], _fixture_candidate_for_contract(contract))
        for contract in activation_receipt_contracts()
    )


def required_receipts(
    *,
    live_shadow_receipt_present: bool = False,
    production_token_vault_receipt_present: bool = False,
    privacy_policy_receipt_present: bool = False,
) -> tuple[dict[str, Any], ...]:
    specs = (
        (
            "live_model_enablement_receipt",
            "Operator enablement",
            ("LM1", "LM2"),
            "OpenClaw needs an explicit operator enablement receipt before live models can turn on.",
        ),
        (
            "provider_policy_receipt",
            "Provider policy",
            ("LM1", "LM2"),
            "OpenClaw needs a recorded provider policy choice before any provider can be used.",
        ),
        (
            "model_selection_policy_receipt",
            "Model selection policy",
            ("LM1", "LM2"),
            "OpenClaw needs a model-selection receipt that matches the lane, privacy class, and risk.",
        ),
        (
            "privacy_policy_receipt",
            "Privacy policy",
            ("LM1", "LM2"),
            "OpenClaw needs the production privacy policy receipt before live model-shaped packages can leave shadow mode.",
        ),
        (
            "production_token_vault_ready_receipt",
            "Production token vault",
            ("LM1", "LM2"),
            "OpenClaw needs production token-vault readiness before sensitive live model packages are allowed.",
        ),
        (
            "shadow_comparison_live_run_receipt",
            "Live-shadow comparison",
            ("LM1", "LM2"),
            "OpenClaw needs successful real shadow comparison receipts beyond fixtures.",
        ),
        (
            "rollback_disable_receipt",
            "Rollback switch",
            ("LM1", "LM2"),
            "OpenClaw needs a rollback or disable receipt before any future live model lane can be reviewed.",
        ),
        (
            "device_trust_live_activation_receipt",
            "Device trust / live activation",
            ("Gate 1", "LM1", "LM2"),
            "OpenClaw needs a trusted-device and live-activation receipt before real Mission Control traffic can feed live model lanes.",
        ),
        (
            "real_lm1_production_policy_receipt",
            "Real LM1 production policy",
            ("LM1",),
            "OpenClaw needs a real LM1 production policy before the intent-proposal lane can be reviewed.",
        ),
        (
            "real_lm2_production_policy_receipt",
            "Real LM2 production policy",
            ("LM2",),
            "OpenClaw needs a real LM2 production policy before the role-response lane can be reviewed.",
        ),
    )
    return tuple(
        asdict(
            ActivationReceiptRequirement(
                receipt_id=f"activation_receipt:{_short_hash(receipt_type)}",
                receipt_type=receipt_type,
                human_label=human_label,
                required_for_lanes=lanes,
                present=(
                    (receipt_type == "shadow_comparison_live_run_receipt" and live_shadow_receipt_present)
                    or (receipt_type == "production_token_vault_ready_receipt" and production_token_vault_receipt_present)
                    or (receipt_type == "privacy_policy_receipt" and privacy_policy_receipt_present)
                ),
                blocks_live_lm1="LM1" in lanes,
                blocks_live_lm2="LM2" in lanes,
                blocks_provider_activation=receipt_type in {"provider_policy_receipt", "model_selection_policy_receipt"},
                operator_copy=operator_copy,
                next_safe_move="Keep live models off; collect this receipt through a future governed review lane.",
            )
        )
        for receipt_type, human_label, lanes, operator_copy in specs
    )


def build_payload(*, generated_at: str | None = None, live_shadow_payload: Mapping[str, Any] | None = None) -> dict[str, Any]:
    generated_at = generated_at or DEFAULT_GENERATED_AT
    live_shadow = dict(live_shadow_payload or live_lm_shadow_trial.latest_or_ready_payload(generated_at=generated_at))
    live_shadow_valid = bool((live_shadow.get("machine_proof") or {}).get("live_shadow_receipt_valid"))
    token_receipts = token_vault.production_activation_receipt_statuses()
    token_vault_receipt_present = bool(token_receipts["production_token_vault_ready_receipt"]["present"])
    privacy_policy_receipt_present = bool(token_receipts["privacy_policy_receipt"]["present"])
    receipt_contracts = activation_receipt_contracts()
    receipt_fixture_results = activation_receipt_contract_fixture_results()
    receipts = required_receipts(
        live_shadow_receipt_present=live_shadow_valid,
        production_token_vault_receipt_present=token_vault_receipt_present,
        privacy_policy_receipt_present=privacy_policy_receipt_present,
    )
    missing = tuple(item["receipt_type"] for item in receipts if item["present"] is False)
    hard_blockers = []
    if not token_vault_receipt_present:
        hard_blockers.append("production_token_vault_inactive")
    hard_blockers.extend(("provider_activation_receipts_missing", "live_model_enablement_receipt_missing"))
    if not privacy_policy_receipt_present:
        hard_blockers.append("production_privacy_policy_receipt_missing")
    hard_blockers.extend(
        (
            "rollback_disable_receipt_missing",
            "device_trust_live_activation_receipt_missing",
            "real_lm1_production_policy_receipt_missing",
            "real_lm2_production_policy_receipt_missing",
        )
    )
    if not live_shadow_valid:
        hard_blockers.insert(4, "live_shadow_comparison_receipt_missing")
    beams = production_activation_beams(
        token_vault_receipt_present=token_vault_receipt_present,
        privacy_policy_receipt_present=privacy_policy_receipt_present,
        receipt_contracts_ready=all(
            contract["receipt_contract_status"] == "RECEIPT_CONTRACT_READY_PRODUCTION_RECEIPT_MISSING"
            for contract in receipt_contracts
        ),
    )
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "contract_status": CONTRACT_STATUS,
        "generated_at": generated_at,
        "operator_summary": (
            "Live models are still off.",
            "OpenClaw now has an explicit checklist for what must exist before live LM1 or LM2 can be reviewed.",
            "No provider, model, tool, or action is activated by this checklist.",
        ),
        "live_lm1_activation_status": "NOT_READY",
        "live_lm2_activation_status": "NOT_READY",
        "provider_activation_status": "RECEIPTS_REQUIRED_NOT_PRESENT",
        "activation_receipt_requirements": receipts,
        "production_activation_beams": beams,
        "activation_receipt_contracts": receipt_contracts,
        "activation_receipt_fixture_results": receipt_fixture_results,
        "missing_receipts": missing,
        "live_shadow_receipt": {
            "read_model_ref": "generated/read_models/live_lm_shadow_trial.json",
            "status": live_shadow.get("trial_status"),
            "present": live_shadow_valid,
            "provider_class": (live_shadow.get("machine_proof") or {}).get("provider_class"),
            "model_ref": (live_shadow.get("machine_proof") or {}).get("model_ref"),
        },
        "shadow_test_receipts": {
            "provider_policy_receipt": {
                "present": live_shadow_valid,
                "scope": "shadow_test_only",
                "satisfies_production_activation": False,
                "provider_class": (live_shadow.get("machine_proof") or {}).get("provider_class"),
            },
            "model_selection_policy_receipt": {
                "present": live_shadow_valid,
                "scope": "shadow_test_only",
                "satisfies_production_activation": False,
                "model_ref": (live_shadow.get("machine_proof") or {}).get("model_ref"),
            },
        },
        "production_privacy_receipts": token_receipts,
        "hard_blockers": tuple(hard_blockers),
        "next_safe_move": "Keep using fixture/shadow mode until these receipts exist.",
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "machine_proof": {
            "receipt_requirement_count": len(receipts),
            "missing_receipt_count": len(missing),
            "production_activation_beam_count": len(beams),
            "production_activation_beams_explicit": tuple(item["beam_id"] for item in beams)
            == (
                "production_token_vault",
                "provider_model_receipts",
                "live_enablement_receipt",
                "privacy_receipt",
                "rollback_disable_receipt",
                "device_trust_live_activation",
                "real_lm_production_policy",
            ),
            "provider_activation_receipts_required": True,
            "provider_activation_receipts_present": False,
            "production_token_vault_ready_receipt_present": token_vault_receipt_present,
            "live_model_enablement_receipt_present": False,
            "privacy_policy_receipt_present": privacy_policy_receipt_present,
            "rollback_disable_receipt_present": False,
            "device_trust_live_activation_receipt_present": False,
            "real_lm1_production_policy_receipt_present": False,
            "real_lm2_production_policy_receipt_present": False,
            "activation_receipt_contract_count": len(receipt_contracts),
            "activation_receipt_contracts_ready": all(
                contract["receipt_contract_status"] == "RECEIPT_CONTRACT_READY_PRODUCTION_RECEIPT_MISSING"
                for contract in receipt_contracts
            ),
            "activation_receipt_fixture_count": len(receipt_fixture_results),
            "activation_receipt_fixtures_valid": all(result["valid_as_test_fixture"] for result in receipt_fixture_results),
            "activation_receipt_fixtures_satisfy_production": any(
                result["satisfies_production_activation"] for result in receipt_fixture_results
            ),
            "live_shadow_comparison_receipt_present": live_shadow_valid,
            "live_shadow_model_call_recorded": bool((live_shadow.get("machine_proof") or {}).get("live_model_call_performed")),
            "shadow_provider_policy_receipt_present": live_shadow_valid,
            "shadow_model_selection_receipt_present": live_shadow_valid,
            "shadow_receipts_satisfy_production_activation": False,
            "live_lm1_ready": False,
            "live_lm2_ready": False,
            "live_lm_status": "NOT_ACTIVE",
            "live_model_call_performed": False,
            "model_api_call_performed": False,
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
    lines = [
        "# Live LM Activation Requirements",
        "",
        f"Status: {CONTRACT_STATUS}",
        f"LM1 live: {payload['live_lm1_activation_status']}",
        f"LM2 live: {payload['live_lm2_activation_status']}",
        f"Missing receipts: {payload['machine_proof']['missing_receipt_count']}",
        f"Receipt contracts ready: {payload['machine_proof']['activation_receipt_contract_count']}",
        "",
        "Still blocked:",
        *[f"- {item}" for item in payload["hard_blockers"]],
        "",
        "No production model, provider, tool, or action is enabled.",
    ]
    operator_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return json_path, operator_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export live LM activation requirements read-model.")
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
                    "missing_receipt_count": payload["machine_proof"]["missing_receipt_count"],
                    "live_lm_status": payload["machine_proof"]["live_lm_status"],
                    "all_live_authority_false": payload["machine_proof"]["all_live_authority_false"],
                }
            ),
            end="",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
