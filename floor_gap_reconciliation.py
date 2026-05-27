"""Floor Gap Reconciliation v0.

Audits the OpenClaw LM-readiness floor across the Gate 1 -> LM1 -> Gate 2 ->
Gate 3 -> LM2 -> Gate 4 chain. The goal is to show which lanes are tested,
connected, exported, and visible, and to document the small floor raises made in
this pass. This module does not call models, run tools, read files/workbooks, or
mutate production state.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping

import gate1_privacy_request_readiness
import gate1_operational_snapshot
import gate_chain_harness
import guardian_output_gate
import guardian_trust_ramp_simulator
import intent_ingest_gate
import live_lm_activation_requirements
import live_lm_shadow_trial
import lm1_thread_context_package
import lm_readiness_dashboard
import model_router_policy
import operator_readiness_surface
import private_mode_policy_readiness
import provider_policy_registry
import read_model_mirror_visibility
import request_response_bridge_readiness
import role_package_gate
import shadow_lm_mode
import token_vault
import universal_intake_contract


DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_GENERATED_AT = "2026-05-26T00:00:00+00:00"

SCHEMA_VERSION = "floor_gap_reconciliation_v0"
READ_MODEL_ID = "floor_gap_reconciliation"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
OPERATOR_EXPORT_NAME = f"{READ_MODEL_ID}_OPERATOR.md"
CONTRACT_STATUS = "FLOOR_GAP_RECONCILIATION_NO_LIVE_ACTIONS"

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

MATRIX_FIELDS = (
    "CONTRACT_ONLY",
    "TESTED",
    "EXPORTED",
    "DASHBOARD_VISIBLE",
    "CONNECTED_TO_CHAIN",
    "HAS_FIXTURE",
    "HAS_SQLITE_PROOF",
    "HAS_OPERATOR_COPY",
    "READY_FOR_SHADOW",
    "READY_FOR_LIVE_REVIEW",
)


@dataclass(frozen=True)
class FloorLaneAssessment:
    lane_id: str
    lane_name: str
    contract_only: bool
    tested: bool
    exported: bool
    dashboard_visible: bool
    connected_to_chain: bool
    has_fixture: bool
    has_sqlite_proof: bool
    has_operator_copy: bool
    ready_for_shadow: bool
    ready_for_live_review: bool
    maturity_score: int
    maturity_label: str
    not_ready_reason: str
    raised_this_pass: bool


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _short_hash(*parts: object) -> str:
    return hashlib.sha256("\0".join(str(part) for part in parts).encode("utf-8")).hexdigest()[:16]


def _content_hash(payload: dict[str, Any]) -> str:
    clone = json.loads(stable_json(payload))
    clone.get("machine_proof", {}).pop("content_hash", None)
    return "sha256:" + hashlib.sha256(stable_json(clone).encode("utf-8")).hexdigest()


def classify_gate1_privacy_trigger(input_class: str) -> dict[str, Any]:
    return gate1_privacy_request_readiness.classify_gate1_privacy_request(input_class)


def gate1_privacy_trigger_fixtures() -> tuple[dict[str, Any], ...]:
    return gate1_privacy_request_readiness.gate1_privacy_trigger_fixtures()


def _score(flags: Mapping[str, bool]) -> int:
    return sum(1 for value in flags.values() if value)


def _label(score: int) -> str:
    if score >= 8:
        return "SHADOW_READY"
    if score >= 6:
        return "CONNECTED"
    if score >= 4:
        return "TESTED_PARTIAL"
    return "CONTRACT_ONLY"


def _assessment(
    lane_id: str,
    lane_name: str,
    *,
    not_ready_reason: str = "",
    raised_this_pass: bool = False,
    **flags: bool,
) -> dict[str, Any]:
    normalized = {field: bool(flags.get(field.lower(), False)) for field in MATRIX_FIELDS}
    score = _score(normalized)
    item = FloorLaneAssessment(
        lane_id=lane_id,
        lane_name=lane_name,
        contract_only=normalized["CONTRACT_ONLY"],
        tested=normalized["TESTED"],
        exported=normalized["EXPORTED"],
        dashboard_visible=normalized["DASHBOARD_VISIBLE"],
        connected_to_chain=normalized["CONNECTED_TO_CHAIN"],
        has_fixture=normalized["HAS_FIXTURE"],
        has_sqlite_proof=normalized["HAS_SQLITE_PROOF"],
        has_operator_copy=normalized["HAS_OPERATOR_COPY"],
        ready_for_shadow=normalized["READY_FOR_SHADOW"],
        ready_for_live_review=normalized["READY_FOR_LIVE_REVIEW"],
        maturity_score=score,
        maturity_label=_label(score),
        not_ready_reason=not_ready_reason,
        raised_this_pass=raised_this_pass,
    )
    return asdict(item)


def build_floor_matrix(*, generated_at: str = DEFAULT_GENERATED_AT) -> tuple[dict[str, Any], ...]:
    dashboard = lm_readiness_dashboard.build_payload(generated_at=generated_at)
    live_shadow_payload = live_lm_shadow_trial.latest_or_ready_payload(generated_at=generated_at)
    live_shadow_valid = bool((live_shadow_payload.get("machine_proof") or {}).get("live_shadow_receipt_valid"))
    bridge_readiness = request_response_bridge_readiness.build_payload(generated_at=generated_at)
    activation_requirements = live_lm_activation_requirements.build_payload(generated_at=generated_at)
    private_policy = private_mode_policy_readiness.build_payload(generated_at=generated_at)
    mirror_visibility = read_model_mirror_visibility.build_payload(generated_at=generated_at)
    readiness_summary = dashboard["dashboard_summary"]
    lm1_payload = lm1_thread_context_package.build_payload(generated_at=generated_at)
    return (
        _assessment(
            "gate1_ingress_privacy_request",
            "Gate 1 ingress/privacy/request readiness",
            tested=True,
            exported=True,
            dashboard_visible=True,
            connected_to_chain=True,
            has_fixture=True,
            has_operator_copy=True,
            ready_for_shadow=True,
            ready_for_live_review=True,
            not_ready_reason="Needs live device trust registry integration before live LM activation.",
        ),
        _assessment(
            "gate1_operational_snapshot",
            "Gate 1 operational request snapshot",
            tested=True,
            exported=True,
            dashboard_visible=True,
            connected_to_chain=True,
            has_fixture=True,
            has_operator_copy=True,
            ready_for_shadow=True,
            ready_for_live_review=True,
            raised_this_pass=True,
            not_ready_reason="Snapshot is fixture-only; live LM activation still needs provider/privacy receipts.",
        ),
        _assessment(
            "universal_intake",
            "Universal intake",
            tested=True,
            exported=True,
            dashboard_visible=True,
            connected_to_chain=True,
            has_fixture=True,
            has_operator_copy=True,
            ready_for_shadow=True,
            ready_for_live_review=True,
            raised_this_pass=True,
            not_ready_reason="Still metadata-only; no production broad file classification.",
        ),
        _assessment(
            "lm1_thread_context_package",
            "LM1 thread-context package",
            tested=True,
            exported=True,
            dashboard_visible=True,
            connected_to_chain=True,
            has_fixture=True,
            has_operator_copy=True,
            ready_for_shadow=readiness_summary["lm1_shadow"] == "READY",
            ready_for_live_review=lm1_payload["machine_proof"]["ready_for_shadow"],
            not_ready_reason="Standalone package is exported; live LM1 remains blocked until explicit activation and production privacy receipts.",
        ),
        _assessment(
            "model_router_provider_policy",
            "Model router/provider policy",
            tested=True,
            exported=True,
            dashboard_visible=True,
            connected_to_chain=True,
            has_fixture=True,
            has_operator_copy=True,
            ready_for_shadow=True,
            ready_for_live_review=True,
            not_ready_reason="No live provider activation receipt.",
        ),
        _assessment(
            "token_vault_privacy_policy",
            "Token vault/privacy policy",
            tested=True,
            exported=True,
            dashboard_visible=True,
            connected_to_chain=True,
            has_fixture=True,
            has_operator_copy=True,
            ready_for_shadow=True,
            ready_for_live_review=True,
            not_ready_reason="Production token vault is not active.",
        ),
        _assessment(
            "gate2_intent_ingest",
            "Gate 2 intent ingest",
            tested=True,
            exported=True,
            dashboard_visible=True,
            connected_to_chain=True,
            has_fixture=True,
            has_operator_copy=True,
            ready_for_shadow=True,
            ready_for_live_review=True,
            not_ready_reason="Operator-facing visibility improved; live LM1 proposals still require explicit activation.",
        ),
        _assessment(
            "gate3_role_package",
            "Gate 3 role package",
            tested=True,
            exported=True,
            dashboard_visible=True,
            connected_to_chain=True,
            has_fixture=True,
            has_operator_copy=True,
            ready_for_shadow=True,
            ready_for_live_review=True,
            not_ready_reason="Package compiler is shadow-ready; live LM2 use still needs activation and production privacy receipts.",
        ),
        _assessment(
            "lm2_package_shadow",
            "LM2 package shadow",
            tested=True,
            exported=True,
            dashboard_visible=True,
            connected_to_chain=True,
            has_fixture=True,
            has_sqlite_proof=True,
            has_operator_copy=True,
            ready_for_shadow=readiness_summary["lm2_package_shadow"] == "READY",
            not_ready_reason="Negative fixtures added; still no live LM2 calls.",
        ),
        _assessment(
            "gate4_guardian_output",
            "Gate 4 Guardian output",
            tested=True,
            exported=True,
            dashboard_visible=True,
            connected_to_chain=True,
            has_fixture=True,
            has_operator_copy=True,
            ready_for_shadow=True,
            ready_for_live_review=True,
            not_ready_reason="Guardian output gate is ready for shadow/later live validation; no production action authority is enabled.",
        ),
        _assessment(
            "trust_ramp",
            "Trust ramp",
            tested=True,
            exported=True,
            dashboard_visible=True,
            connected_to_chain=True,
            has_fixture=True,
            has_sqlite_proof=True,
            has_operator_copy=True,
            ready_for_shadow=True,
            not_ready_reason="Candidate trust is simulation-only; active trust needs live receipts.",
        ),
        _assessment(
            "readiness_dashboard",
            "Readiness dashboard",
            tested=True,
            exported=True,
            dashboard_visible=True,
            connected_to_chain=True,
            has_fixture=True,
            has_operator_copy=True,
            ready_for_shadow=True,
            ready_for_live_review=True,
        ),
        _assessment(
            "operator_readiness_surface",
            "Operator readiness surface",
            tested=True,
            exported=True,
            dashboard_visible=True,
            connected_to_chain=True,
            has_fixture=True,
            has_operator_copy=True,
            ready_for_shadow=True,
            ready_for_live_review=True,
        ),
        _assessment(
            "request_response_bridge",
            "Request-response bridge",
            tested=True,
            exported=True,
            dashboard_visible=True,
            connected_to_chain=bridge_readiness["bridge_contract"]["service_template_present"],
            has_fixture=True,
            has_operator_copy=True,
            ready_for_shadow=True,
            ready_for_live_review=bridge_readiness["bridge_contract"]["ready_for_live_review"],
            not_ready_reason="Readiness visibility exists; live service state is still checked outside this read-model.",
        ),
        _assessment(
            "invoice_fixture_integration",
            "Invoice fixture integration",
            tested=True,
            exported=True,
            dashboard_visible=True,
            connected_to_chain=True,
            has_fixture=True,
            has_operator_copy=True,
            ready_for_shadow=True,
            ready_for_live_review=True,
            not_ready_reason="Fixture-proven only; running workbooks are not submitted/paid/final truth.",
        ),
        _assessment(
            "private_mode_readiness",
            "Private Mode readiness",
            tested=True,
            exported=True,
            dashboard_visible=True,
            connected_to_chain=True,
            has_fixture=True,
            has_operator_copy=True,
            ready_for_shadow=True,
            ready_for_live_review=private_policy["machine_proof"]["private_mode_policy_exported"],
            raised_this_pass=True,
            not_ready_reason="Backend policy is exported and inactive; product switch and production token vault are still inactive.",
        ),
        _assessment(
            "provider_activation_receipts",
            "Provider activation receipts",
            tested=True,
            exported=True,
            dashboard_visible=True,
            connected_to_chain=True,
            has_fixture=True,
            has_sqlite_proof=live_shadow_valid,
            has_operator_copy=True,
            ready_for_shadow=live_shadow_valid,
            ready_for_live_review=False,
            raised_this_pass=True,
            not_ready_reason=(
                "Shadow provider/model receipts exist; production provider activation receipts are still missing."
                if live_shadow_valid
                else "Provider activation requires missing receipts; no provider is active."
            ),
        ),
        _assessment(
            "live_lm_shadow_trial",
            "Live LM shadow trial",
            tested=True,
            exported=True,
            dashboard_visible=True,
            connected_to_chain=True,
            has_fixture=True,
            has_sqlite_proof=True,
            has_operator_copy=True,
            ready_for_shadow=True,
            ready_for_live_review=True,
            raised_this_pass=True,
            not_ready_reason="Local-only shadow proof exists; production live models still need provider/privacy/rollback receipts.",
        ),
        _assessment(
            "shadow_comparison",
            "Shadow comparison",
            tested=True,
            exported=True,
            dashboard_visible=True,
            connected_to_chain=True,
            has_fixture=True,
            has_sqlite_proof=True,
            has_operator_copy=True,
            ready_for_shadow=True,
            not_ready_reason="Fixture comparisons pass; live-shadow receipt is still missing.",
        ),
        _assessment(
            "tokenized_package_readiness",
            "Tokenized package readiness",
            tested=True,
            exported=True,
            dashboard_visible=True,
            connected_to_chain=True,
            has_fixture=True,
            has_operator_copy=True,
            ready_for_shadow=True,
            ready_for_live_review=True,
            not_ready_reason="Synthetic tokenization is proven; production token vault is still inactive.",
        ),
        _assessment(
            "read_model_mirror_visibility",
            "Read-model/mirror visibility",
            tested=True,
            exported=True,
            dashboard_visible=True,
            connected_to_chain=True,
            has_fixture=True,
            has_operator_copy=True,
            ready_for_shadow=True,
            ready_for_live_review=mirror_visibility["machine_proof"]["all_known_readiness_refs_recorded"],
            raised_this_pass=True,
            not_ready_reason="Visibility proof exists; this does not create a Mac sync system.",
        ),
        _assessment(
            "production_live_blockers",
            "Production/live blockers",
            tested=True,
            exported=True,
            dashboard_visible=True,
            connected_to_chain=True,
            has_fixture=True,
            has_operator_copy=True,
            ready_for_shadow=False,
            raised_this_pass=True,
            not_ready_reason=", ".join(activation_requirements["hard_blockers"]),
        ),
    )


def weakest_lanes(matrix: tuple[dict[str, Any], ...], limit: int = 5) -> tuple[dict[str, Any], ...]:
    return tuple(sorted(matrix, key=lambda item: (item["maturity_score"], item["lane_id"]))[:limit])


def strongest_lanes(matrix: tuple[dict[str, Any], ...], limit: int = 5) -> tuple[dict[str, Any], ...]:
    return tuple(sorted(matrix, key=lambda item: (-item["maturity_score"], item["lane_id"]))[:limit])


def build_payload(*, generated_at: str | None = None) -> dict[str, Any]:
    generated_at = generated_at or DEFAULT_GENERATED_AT
    matrix = build_floor_matrix(generated_at=generated_at)
    gate1_fixtures = gate1_privacy_trigger_fixtures()
    gate1_payload = gate1_privacy_request_readiness.build_payload(generated_at=generated_at)
    gate1_snapshot_payload = gate1_operational_snapshot.build_payload(generated_at=generated_at)
    universal_payload = universal_intake_contract.build_payload(generated_at=generated_at)
    lm1_payload = lm1_thread_context_package.build_payload(generated_at=generated_at)
    lm1_package = lm1_payload["lm1_thread_context_package"]
    token_payload = token_vault.build_payload(generated_at=generated_at)
    shadow_payload = shadow_lm_mode.build_payload(generated_at=generated_at, persist=True)
    dashboard_payload = lm_readiness_dashboard.build_payload(generated_at=generated_at)
    live_shadow_payload = live_lm_shadow_trial.latest_or_ready_payload(generated_at=generated_at)
    bridge_payload = request_response_bridge_readiness.build_payload(generated_at=generated_at)
    activation_payload = live_lm_activation_requirements.build_payload(
        generated_at=generated_at,
        live_shadow_payload=live_shadow_payload,
    )
    private_policy_payload = private_mode_policy_readiness.build_payload(generated_at=generated_at)
    mirror_payload = read_model_mirror_visibility.build_payload(generated_at=generated_at)
    gate2_result = dashboard_payload["representative_flow"]["gate2_result_summary"]
    raised = tuple(item for item in matrix if item["raised_this_pass"])
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "contract_status": CONTRACT_STATUS,
        "generated_at": generated_at,
        "floor_matrix": matrix,
        "strongest_lanes": strongest_lanes(matrix),
        "weakest_lanes": weakest_lanes(matrix),
        "raised_this_pass": raised,
        "gate1_privacy_trigger_fixtures": gate1_fixtures,
        "gate1_privacy_request_readiness_ref": {
            "read_model_ref": "generated/read_models/gate1_privacy_request_readiness.json",
            "contract_status": gate1_payload["contract_status"],
            "gate_1_output_can_feed_lm1_package": gate1_payload["chain_contract"]["gate_1_output_can_feed_lm1_package"],
            "lm1_may_receive_raw_values": gate1_payload["chain_contract"]["lm1_may_receive_raw_values"],
        },
        "gate1_operational_snapshot_ref": {
            "read_model_ref": "generated/read_models/gate1_operational_snapshot.json",
            "contract_status": gate1_snapshot_payload["contract_status"],
            "capital_hilton_snapshot_safe_for_lm1": gate1_snapshot_payload["machine_proof"][
                "capital_hilton_snapshot_safe_for_lm1"
            ],
            "privacy_policy_missing_blocks_lm1": gate1_snapshot_payload["machine_proof"][
                "privacy_policy_missing_blocks_lm1"
            ],
            "output_to": gate1_snapshot_payload["chain_contract"]["output_to"],
        },
        "universal_intake_chain_candidate": universal_payload["examples"]["capital_hilton_running_workbook"],
        "lm1_thread_context_package_ref": {
            "read_model_ref": "generated/read_models/lm1_thread_context_package.json",
            "package_id": lm1_package["package_id"],
            "gate1_operational_snapshot_ref": lm1_package["gate1_operational_snapshot_ref"],
            "gate1_safe_to_package_for_lm1": lm1_package["gate1_safe_to_package_for_lm1"],
            "privacy_classification": lm1_package["privacy_classification"],
            "tokenization_required": lm1_package["tokenization_required"],
            "universal_intake_chain_contract": lm1_package.get("universal_intake_chain_contract", {}),
            "raw_values_included": lm1_package["raw_values_included"],
            "tools_allowed": lm1_package["tools_allowed"],
            "ready_for_shadow": lm1_payload["machine_proof"]["ready_for_shadow"],
        },
        "gate2_visibility_summary": {
            "read_model_ref": "generated/read_models/intent_ingest_gate.json",
            "representative_outcome": gate2_result.get("outcome"),
            "operator_readback": gate2_result.get("operator_readback"),
            "operator_copy": (
                "Gate 2 can accept a safe intent proposal, ask for clarification, or block authority before anything executes."
            ),
            "live_lm_ingest_allowed": False,
            "tool_execution_allowed": False,
        },
        "request_response_bridge_readiness_ref": {
            "read_model_ref": "generated/read_models/request_response_bridge_readiness.json",
            "readiness_status": bridge_payload["readiness_status"],
            "approved_inbox_ref": bridge_payload["bridge_contract"]["approved_inbox_ref"],
            "response_output_ref": bridge_payload["bridge_contract"]["response_output_ref"],
            "scoped_response_filename_contract": bridge_payload["bridge_contract"]["scoped_response_filename_contract"],
            "ready_for_live_review": bridge_payload["bridge_contract"]["ready_for_live_review"],
        },
        "live_lm_activation_requirements_ref": {
            "read_model_ref": "generated/read_models/live_lm_activation_requirements.json",
            "contract_status": activation_payload["contract_status"],
            "live_lm1_activation_status": activation_payload["live_lm1_activation_status"],
            "live_lm2_activation_status": activation_payload["live_lm2_activation_status"],
            "provider_activation_status": activation_payload["provider_activation_status"],
            "missing_receipts": activation_payload["missing_receipts"],
            "live_shadow_receipt": activation_payload["live_shadow_receipt"],
            "shadow_test_receipts": activation_payload["shadow_test_receipts"],
        },
        "live_lm_shadow_trial_ref": {
            "read_model_ref": "generated/read_models/live_lm_shadow_trial.json",
            "trial_status": live_shadow_payload["trial_status"],
            "provider_class": live_shadow_payload["machine_proof"]["provider_class"],
            "model_ref": live_shadow_payload["machine_proof"]["model_ref"],
            "live_model_call_performed": live_shadow_payload["machine_proof"]["live_model_call_performed"],
            "live_shadow_receipt_valid": live_shadow_payload["machine_proof"]["live_shadow_receipt_valid"],
        },
        "private_mode_policy_readiness_ref": {
            "read_model_ref": "generated/read_models/private_mode_policy_readiness.json",
            "contract_status": private_policy_payload["contract_status"],
            "private_mode_active": private_policy_payload["private_mode_active"],
            "strict_private_mode_active": private_policy_payload["strict_private_mode_active"],
            "package_effect_summary": private_policy_payload["package_effect_summary"],
        },
        "read_model_mirror_visibility_ref": {
            "read_model_ref": "generated/read_models/read_model_mirror_visibility.json",
            "contract_status": mirror_payload["contract_status"],
            "mac_visible_guaranteed": mirror_payload["machine_proof"]["mac_visible_guaranteed"],
            "new_sync_system_created": mirror_payload["machine_proof"]["new_sync_system_created"],
        },
        "tokenization_proof": {
            "raw_values_exported": token_payload["machine_proof"]["raw_values_exported"],
            "stable_within_scope": token_payload["machine_proof"]["stable_within_scope"],
            "different_scope_token_differs": token_payload["machine_proof"]["different_scope_token_differs"],
            "production_token_vault_ready": token_payload["privacy_readiness"]["production_token_vault_ready"],
        },
        "shadow_negative_case_summary": {
            "negative_case_count": shadow_payload["machine_proof"]["shadow_negative_case_count"],
            "negative_cases_passed": shadow_payload["machine_proof"]["shadow_negative_cases_passed"],
            "shadow_comparison_failed_count": shadow_payload["machine_proof"]["shadow_comparison_failed_count"],
        },
        "dashboard_honesty": {
            "lm1_live": dashboard_payload["dashboard_summary"]["lm1_live"],
            "lm2_live": dashboard_payload["dashboard_summary"]["lm2_live"],
            "tokenization": dashboard_payload["dashboard_summary"]["tokenization"],
            "privacy_readiness_status": dashboard_payload["dashboard_summary"]["privacy_readiness_status"],
            "next_blockers": dashboard_payload["dashboard_summary"]["next_blockers"],
        },
        "next_floor_raise_recommendations": (
            "Collect real shadow-comparison receipts before any live LM review.",
            "Turn Private Mode into an operator-controlled product setting only after production token-vault readiness.",
            "Keep universal intake broadening with more metadata-only ambiguous fixtures.",
            "Use existing scoped response/read-model surfaces for visibility; do not add a second sync plane.",
        ),
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "machine_proof": {
            "floor_matrix_lane_count": len(matrix),
            "all_required_lanes_classified": len(matrix) == 22,
            "weak_lanes_identified": bool(weakest_lanes(matrix)),
            "raised_lane_count": len(raised),
            "floor_was_uneven": weakest_lanes(matrix)[0]["maturity_score"] < strongest_lanes(matrix)[-1]["maturity_score"],
            "gate1_privacy_trigger_fixture_exists": len(gate1_fixtures) == 5,
            "gate1_privacy_readiness_exported": True,
            "gate1_operational_snapshot_exported": True,
            "gate1_operational_snapshot_connected": gate1_snapshot_payload["chain_contract"]["safe_snapshot_can_feed_lm1_package"],
            "lm1_thread_context_package_exported": True,
            "request_response_bridge_dashboard_visible": True,
            "request_response_bridge_ready_for_live_review": bridge_payload["bridge_contract"]["ready_for_live_review"],
            "production_live_blockers_explicit": activation_payload["machine_proof"]["missing_receipt_count"] >= 5,
            "live_lm_shadow_trial_exported": True,
            "live_lm_shadow_trial_recorded": live_shadow_payload["machine_proof"]["live_model_call_performed"],
            "live_shadow_receipt_valid": live_shadow_payload["machine_proof"]["live_shadow_receipt_valid"],
            "provider_activation_receipts_required": activation_payload["machine_proof"]["provider_activation_receipts_required"],
            "shadow_provider_policy_receipt_present": activation_payload["machine_proof"][
                "shadow_provider_policy_receipt_present"
            ],
            "shadow_model_selection_receipt_present": activation_payload["machine_proof"][
                "shadow_model_selection_receipt_present"
            ],
            "shadow_receipts_satisfy_production_activation": activation_payload["machine_proof"][
                "shadow_receipts_satisfy_production_activation"
            ],
            "private_mode_policy_exported": private_policy_payload["machine_proof"]["private_mode_policy_exported"],
            "private_mode_policy_inactive": private_policy_payload["private_mode_active"] is False
            and private_policy_payload["strict_private_mode_active"] is False,
            "read_model_mirror_visibility_exported": True,
            "read_model_mirror_visibility_no_sync_created": mirror_payload["machine_proof"]["new_sync_system_created"] is False,
            "gate2_visibility_polished": gate2_result.get("outcome") == intent_ingest_gate.ACCEPTED_INTENT,
            "gate2_operator_readback_visible": bool((gate2_result.get("operator_readback") or {}).get("plain_language_meaning")),
            "gate3_operator_readback_visible": bool(
                (dashboard_payload["representative_flow"]["gate3_package_summary"].get("operator_readback") or {}).get(
                    "operator_message"
                )
            ),
            "universal_intake_chain_compatible": universal_payload["examples"]["capital_hilton_running_workbook"]["lm1_chain_ready"] is True,
            "universal_intake_unknown_artifact_fixture_exists": universal_payload["machine_proof"]["unknown_artifact_asks_clarification"],
            "invoice_fixtures_draft_source_only": universal_payload["machine_proof"]["batch_fixture_all_draft_source_only"],
            "lm1_package_consumes_intake_and_privacy": bool(lm1_package.get("universal_intake_chain_contract"))
            and lm1_package["tokenization_required"] is True,
            "tokenization_raw_values_exported": token_payload["machine_proof"]["raw_values_exported"],
            "negative_shadow_cases_passed": shadow_payload["machine_proof"]["shadow_negative_cases_passed"],
            "dashboard_live_lm_not_active": dashboard_payload["dashboard_summary"]["lm1_live"] == "NOT_ACTIVE"
            and dashboard_payload["dashboard_summary"]["lm2_live"] == "NOT_ACTIVE",
            "live_model_call_performed": False,
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
        "# Floor Gap Reconciliation",
        "",
        f"Status: {CONTRACT_STATUS}",
        f"Lanes classified: {payload['machine_proof']['floor_matrix_lane_count']}",
        f"Lanes raised this pass: {payload['machine_proof']['raised_lane_count']}",
        "",
        "Raised this pass:",
        *[f"- {item['lane_name']}" for item in payload["raised_this_pass"]],
        "",
        "Weakest remaining lanes:",
        *[
            f"- {item['lane_name']}: {item['not_ready_reason']}" if item["not_ready_reason"] else f"- {item['lane_name']}"
            for item in payload["weakest_lanes"]
        ],
        "",
        "No live model, tool, workflow, or production action is enabled.",
    ]
    operator_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return json_path, operator_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export floor gap reconciliation read-model.")
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
                    "lane_count": payload["machine_proof"]["floor_matrix_lane_count"],
                    "raised_lane_count": payload["machine_proof"]["raised_lane_count"],
                    "weakest_lanes": tuple(item["lane_id"] for item in payload["weakest_lanes"]),
                    "negative_shadow_cases_passed": payload["machine_proof"]["negative_shadow_cases_passed"],
                    "all_live_authority_false": payload["machine_proof"]["all_live_authority_false"],
                }
            ),
            end="",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
