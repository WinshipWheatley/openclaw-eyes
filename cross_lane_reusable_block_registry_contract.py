"""Cross-Lane Reusable Block Registry / Protected Value Tokenization Contract v0.

This deterministic read-model defines how future workflow facts can be reused
across lanes without leaking sensitive values or granting live authority. It is
contract/read-model only: no PII vault write, de-tokenization, live reuse,
agent/tool/model execution, external access, or workflow mutation occurs here.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
DEFAULT_EXPORT_ROOT = Path("generated/read_models")

SCHEMA_VERSION = "cross_lane_reusable_block_registry_contract_v0"
READ_MODEL_ID = "cross_lane_reusable_block_registry_contract"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
OPERATOR_EXPORT_NAME = f"{READ_MODEL_ID}_OPERATOR.md"
CONTRACT_STATUS = "DETERMINISTIC_NON_EXECUTING_REUSABLE_FACT_TOKENIZATION_CONTRACT"

VALUE_POSTURES = (
    "SAFE_NON_SENSITIVE_VALUE",
    "TOKENIZED_PROTECTED_VALUE",
    "PROTECTED_REFERENCE_ONLY",
    "PROOF_REQUIRED",
    "REDACTED",
    "UNKNOWN_FAIL_CLOSED",
)

VALUE_KINDS = (
    "rate_amount",
    "performance_date",
    "ap_email_route",
    "po_reference",
    "payment_reference",
    "phone_number",
    "protected_evidence_ref",
    "private_note",
    "document_reference",
    "calculated_state",
    "credential_forbidden",
    "unknown",
)

REUSE_POLICIES = (
    "AUTO_APPLY_EXACT_SCOPE",
    "SUGGEST_APPLY_COMPATIBLE_SCOPE",
    "INFORM_ONLY_HISTORICAL_CONTEXT",
    "REQUIRE_OPERATOR_CONFIRMATION",
    "REQUIRE_PROOF_OR_GUARDIAN_REVIEW",
    "BLOCK_CROSS_TENANT",
    "BLOCK_SENSITIVE_RAW_VALUE",
    "UNKNOWN_FAIL_CLOSED",
)

REUSE_DECISIONS = (
    "AUTO_APPLY",
    "SUGGEST_APPLY",
    "INFORM_ONLY",
    "NEEDS_OPERATOR_CONFIRMATION",
    "NEEDS_PROOF",
    "NEEDS_GUARDIAN_REVIEW",
    "BLOCKED_SCOPE_MISMATCH",
    "BLOCKED_PRIVACY_BOUNDARY",
    "BLOCKED_CROSS_TENANT",
    "BLOCKED_CALCULATED_STATE_COPY",
    "UNKNOWN_FAIL_CLOSED",
)

CONFLICT_TYPES = (
    "VALUE_MISMATCH",
    "SCOPE_MISMATCH",
    "STALE_FACT",
    "PROOF_RANK_CONFLICT",
    "TOKENIZED_VALUE_MISMATCH",
    "PRIVACY_BOUNDARY_CONFLICT",
    "UNKNOWN_FAIL_CLOSED",
)

WORKBENCH_BUCKETS = (
    "LOW_HANGING_FRUIT",
    "HIGH_LEVERAGE",
    "NEEDS_PROOF",
    "NEEDS_PROTECTED_EVIDENCE",
    "PARKED_FOR_LATER",
    "CONFLICTS_AND_STALE",
    "BLOCKED_BY_AUTHORITY",
    "NEXT_SAFE_MOVE",
)

REQUIRED_REUSABLE_FACT_FIELDS = (
    "fact_id",
    "fact_type",
    "safe_display_label",
    "value_posture",
    "value_kind",
    "raw_value_allowed_in_read_model",
    "tokenized_value_ref",
    "protected_store_ref",
    "value_match_ref",
    "value_match_ref_policy",
    "privacy_class",
    "sensitivity_class",
    "source_receipt_ref",
    "source_capture_ref",
    "source_workflow_session_ref",
    "source_block_id",
    "tenant_ref",
    "client_ref",
    "world_ref",
    "lane_ref",
    "validity_scope",
    "proof_status",
    "reuse_policy",
    "conflict_policy",
    "stale_policy",
    "authority_boundary",
    "central_sync_allowed",
    "allowed_surfaces",
    "allowed_roles",
    "next_safe_move",
)

REQUIRED_SCOPE_FIELDS = (
    "scope_id",
    "tenant_ref",
    "client_ref",
    "world_ref",
    "lane_ref",
    "workflow_session_ref",
    "service_context",
    "contract_context",
    "fiscal_or_date_period",
    "geographic_or_business_unit_scope",
    "validity_start",
    "validity_end",
    "exact_match_required_fields",
    "suggest_match_allowed_fields",
    "cross_tenant_reuse_allowed",
    "next_safe_move",
)

REQUIRED_POLICY_FIELDS = (
    "policy_id",
    "fact_type",
    "privacy_class",
    "proof_required_for_auto_apply",
    "proof_required_for_suggest_apply",
    "auto_apply_allowed",
    "suggest_apply_allowed",
    "inform_only_allowed",
    "operator_confirmation_required",
    "guardian_review_required",
    "de_tokenization_allowed",
    "de_tokenization_authority",
    "central_sync_allowed",
    "next_safe_move",
)

REQUIRED_TOKENIZATION_POLICY_FIELDS = (
    "policy_id",
    "token_format",
    "protected_store_policy",
    "raw_value_allowed_in_read_model",
    "public_hash_allowed",
    "value_match_strategy",
    "token_rotation_policy",
    "token_version",
    "redaction_required",
    "de_tokenization_authority",
    "allowed_surfaces_for_safe_label",
    "allowed_surfaces_for_raw_value",
    "forbidden_material",
    "next_safe_move",
)

REQUIRED_DECISION_FIELDS = (
    "decision_id",
    "candidate_fact_ref",
    "target_block_ref",
    "target_workflow_session_ref",
    "target_scope_ref",
    "decision",
    "reason",
    "required_operator_action",
    "required_proof_action",
    "privacy_boundary",
    "conflict_ref",
    "stale_ref",
    "readback_message",
    "elioperator_message",
    "next_safe_move",
)

REQUIRED_CONFLICT_FIELDS = (
    "conflict_id",
    "fact_type",
    "active_fact_ref",
    "candidate_fact_ref",
    "conflict_type",
    "scope_comparison",
    "proof_rank_comparison",
    "stale_status",
    "safe_display_summary",
    "raw_value_exposed",
    "operator_resolution_options",
    "next_safe_move",
)

REQUIRED_IMPACT_FIELDS = (
    "impact_preview_id",
    "reusable_fact_ref",
    "affected_workflows",
    "affected_blocks",
    "auto_apply_count",
    "suggest_apply_count",
    "inform_only_count",
    "blocked_count",
    "privacy_blocked_count",
    "proof_required_count",
    "operator_summary",
    "elioperator_summary",
    "next_safe_move",
)

REQUIRED_WORKBENCH_FIELDS = (
    "concept_id",
    "lanes",
    "buckets",
    "sorting_policy",
    "operator_bandwidth_policy",
    "low_hanging_fruit_policy",
    "high_leverage_policy",
    "proof_bearing_policy",
    "protected_value_policy",
    "conflict_policy",
    "parking_policy",
    "next_safe_move_policy",
)

REQUIRED_HANDOFF_FIELDS = (
    "compatibility_id",
    "artifact_type",
    "schema_ref",
    "cross_surface_registry_ref",
    "reusable_fact_schema_ref",
    "origin_surface",
    "source_channel",
    "target_handler",
    "workflow_session_ref_required",
    "idempotency_key_required",
    "payload_hash_required",
    "tokenized_value_ref_allowed",
    "raw_value_forbidden",
    "readback_required",
    "elioperator_required",
    "next_safe_move",
)

FORBIDDEN_MATERIAL = (
    "credentials",
    "OAuth tokens",
    "browser cookies/session state",
    "API keys",
    "private keys",
    "W-9/tax/bank/remit values in normal read-models",
    "raw email bodies",
    "raw screenshots",
    "raw client private documents",
    "raw phone/email/PO/payment references in normal read-models",
)

AUTHORITY_BOUNDARY = {
    "live_reusable_fact_write_allowed": False,
    "live_pii_vault_write_allowed": False,
    "live_de_tokenization_allowed": False,
    "live_cross_lane_auto_apply_allowed": False,
    "live_operator_workbench_ui_allowed": False,
    "model_call_allowed": False,
    "agent_activation_allowed": False,
    "tool_execution_allowed": False,
    "queue_execution_allowed": False,
    "runtime_dispatch_allowed": False,
    "browser_automation_allowed": False,
    "coupa_access_allowed": False,
    "gmail_access_allowed": False,
    "telegram_send_allowed": False,
    "email_send_allowed": False,
    "credential_handling_allowed": False,
    "raw_body_ingestion_allowed": False,
    "mission_control_swift_change_allowed": False,
    "mac_sync_import_allowed": False,
    "git_push_pull_fetch_allowed": False,
    "network_operation_allowed": False,
    "file_cleanup_archive_promotion_allowed": False,
}

RELATIONSHIP_REF_PATHS = {
    "workflow_block_intent_live_draft_contract": "generated/read_models/workflow_block_intent_live_draft_contract.json",
    "mission_control_capture_request_intake": "generated/read_models/mission_control_capture_request_intake.json",
    "capital_hilton_delivery_facts_capture_writer": "generated/read_models/capital_hilton_delivery_facts_capture_writer.json",
    "operator_question_assist_scope_expansion_contract": "generated/read_models/operator_question_assist_scope_expansion_contract.json",
    "entry_agnostic_workflow_block_chain_routing_contract": (
        "generated/read_models/entry_agnostic_workflow_block_chain_routing_contract.json"
    ),
    "agent_conversation_handoff_step_packet_contract": (
        "generated/read_models/agent_conversation_handoff_step_packet_contract.json"
    ),
    "agent_execution_packet_compiler_contract": "generated/read_models/agent_execution_packet_compiler_contract.json",
    "bridge_routing_operator_attention_contract": "generated/read_models/bridge_routing_operator_attention_contract.json",
    "openclaw_sensitive_policy": "openclaw_sensitive_policy.py",
    "pii_vault": "pii_vault.py",
    "cassandra_pii_hooks": "cassandra_pii_hooks.py",
    "business_ops_ledger": "business_ops_ledger.py",
    "CrossSurfaceArtifactHandoffRegistry": "generated/read_models/cross_surface_artifact_handoff_registry.json",
}


@dataclass(frozen=True)
class CrossLaneReusableFactBlock:
    fact_id: str
    fact_type: str
    safe_display_label: str
    value_posture: str
    value_kind: str
    raw_value_allowed_in_read_model: bool
    tokenized_value_ref: str | None
    protected_store_ref: str | None
    value_match_ref: str | None
    value_match_ref_policy: str
    privacy_class: str
    sensitivity_class: str
    source_receipt_ref: str
    source_capture_ref: str
    source_workflow_session_ref: str
    source_block_id: str
    tenant_ref: str
    client_ref: str
    world_ref: str
    lane_ref: str
    validity_scope: dict[str, Any]
    proof_status: str
    reuse_policy: str
    conflict_policy: str
    stale_policy: str
    authority_boundary: dict[str, bool]
    central_sync_allowed: bool
    allowed_surfaces: tuple[str, ...]
    allowed_roles: tuple[str, ...]
    next_safe_move: str


@dataclass(frozen=True)
class ReusableFactScope:
    scope_id: str
    tenant_ref: str
    client_ref: str
    world_ref: str
    lane_ref: str
    workflow_session_ref: str
    service_context: str
    contract_context: str
    fiscal_or_date_period: str
    geographic_or_business_unit_scope: str
    validity_start: str
    validity_end: str | None
    exact_match_required_fields: tuple[str, ...]
    suggest_match_allowed_fields: tuple[str, ...]
    cross_tenant_reuse_allowed: bool
    next_safe_move: str


@dataclass(frozen=True)
class ReusableFactPolicy:
    policy_id: str
    fact_type: str
    privacy_class: str
    proof_required_for_auto_apply: bool
    proof_required_for_suggest_apply: bool
    auto_apply_allowed: bool
    suggest_apply_allowed: bool
    inform_only_allowed: bool
    operator_confirmation_required: bool
    guardian_review_required: bool
    de_tokenization_allowed: bool
    de_tokenization_authority: str
    central_sync_allowed: bool
    next_safe_move: str


@dataclass(frozen=True)
class ProtectedValueTokenizationPolicy:
    policy_id: str
    token_format: str
    protected_store_policy: str
    raw_value_allowed_in_read_model: bool
    public_hash_allowed: bool
    value_match_strategy: str
    token_rotation_policy: str
    token_version: str
    redaction_required: bool
    de_tokenization_authority: str
    allowed_surfaces_for_safe_label: tuple[str, ...]
    allowed_surfaces_for_raw_value: tuple[str, ...]
    forbidden_material: tuple[str, ...]
    next_safe_move: str


@dataclass(frozen=True)
class ReusableFactReuseDecision:
    decision_id: str
    candidate_fact_ref: str
    target_block_ref: str
    target_workflow_session_ref: str
    target_scope_ref: str
    decision: str
    reason: str
    required_operator_action: str
    required_proof_action: str
    privacy_boundary: str
    conflict_ref: str | None
    stale_ref: str | None
    readback_message: str
    elioperator_message: str
    next_safe_move: str


@dataclass(frozen=True)
class ReusableFactConflict:
    conflict_id: str
    fact_type: str
    active_fact_ref: str
    candidate_fact_ref: str
    conflict_type: str
    scope_comparison: str
    proof_rank_comparison: str
    stale_status: str
    safe_display_summary: str
    raw_value_exposed: bool
    operator_resolution_options: tuple[str, ...]
    next_safe_move: str


@dataclass(frozen=True)
class ReusableFactImpactPreview:
    impact_preview_id: str
    reusable_fact_ref: str
    affected_workflows: tuple[str, ...]
    affected_blocks: tuple[str, ...]
    auto_apply_count: int
    suggest_apply_count: int
    inform_only_count: int
    blocked_count: int
    privacy_blocked_count: int
    proof_required_count: int
    operator_summary: str
    elioperator_summary: str
    next_safe_move: str


@dataclass(frozen=True)
class CrossLaneOperatorWorkbenchConcept:
    concept_id: str
    lanes: tuple[str, ...]
    buckets: tuple[str, ...]
    sorting_policy: str
    operator_bandwidth_policy: str
    low_hanging_fruit_policy: str
    high_leverage_policy: str
    proof_bearing_policy: str
    protected_value_policy: str
    conflict_policy: str
    parking_policy: str
    next_safe_move_policy: str


@dataclass(frozen=True)
class ReusableFactHandoffCompatibility:
    compatibility_id: str
    artifact_type: str
    schema_ref: str
    cross_surface_registry_ref: str
    reusable_fact_schema_ref: str
    origin_surface: str
    source_channel: str
    target_handler: str
    workflow_session_ref_required: bool
    idempotency_key_required: bool
    payload_hash_required: bool
    tokenized_value_ref_allowed: bool
    raw_value_forbidden: bool
    readback_required: bool
    elioperator_required: bool
    next_safe_move: str


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def _sha256(payload: Any) -> str:
    return "sha256:" + hashlib.sha256(stable_json(payload).encode("utf-8")).hexdigest()


def _content_hash(payload: dict[str, Any]) -> str:
    clone = json.loads(stable_json(payload))
    clone.get("machine_proof", {}).pop("content_hash", None)
    return _sha256(clone)


def _relationship_inventory() -> dict[str, dict[str, Any]]:
    return {
        name: {
            "ref": name,
            "path": path,
            "present": (ROOT / path).exists(),
            "used_as": "relationship_reference_only_no_content_duplication",
        }
        for name, path in RELATIONSHIP_REF_PATHS.items()
    }


def _scope() -> ReusableFactScope:
    return ReusableFactScope(
        scope_id="scope_capital_hilton_2026_invoice_music_service",
        tenant_ref="openclaw_local",
        client_ref="capital_hilton",
        world_ref="finance",
        lane_ref="capital_hilton_invoice",
        workflow_session_ref="capital_hilton_invoice_workflow_session",
        service_context="music_performance_invoice",
        contract_context="capital_hilton_2026_service_context",
        fiscal_or_date_period="2026-05",
        geographic_or_business_unit_scope="client_local_context",
        validity_start="2026-05-01",
        validity_end="2026-05-31",
        exact_match_required_fields=("tenant_ref", "client_ref", "service_context", "fiscal_or_date_period"),
        suggest_match_allowed_fields=("client_ref", "service_context", "nearby_date_period"),
        cross_tenant_reuse_allowed=False,
        next_safe_move="Use exact scope for auto-apply; otherwise suggest only and ask the operator.",
    )


def _fact_blocks() -> tuple[CrossLaneReusableFactBlock, ...]:
    scope = asdict(_scope())
    return (
        CrossLaneReusableFactBlock(
            fact_id="fact_capital_hilton_rate_400_show_may_2026",
            fact_type="rate_confirmation",
            safe_display_label="Capital Hilton rate confirmed for the May 2026 invoice context",
            value_posture="SAFE_NON_SENSITIVE_VALUE",
            value_kind="rate_amount",
            raw_value_allowed_in_read_model=True,
            tokenized_value_ref=None,
            protected_store_ref=None,
            value_match_ref="non_sensitive_exact_value:rate_amount:400_usd_show",
            value_match_ref_policy="non_sensitive_exact_value_ok; subtotal must derive from rate and dates",
            privacy_class="non_sensitive_operational",
            sensitivity_class="low",
            source_receipt_ref="mc_receipt_rate_confirmation_local",
            source_capture_ref="mission_control_rate_confirmation_capture",
            source_workflow_session_ref="capital_hilton_invoice_workflow_session",
            source_block_id="rate_confirmation",
            tenant_ref="openclaw_local",
            client_ref="capital_hilton",
            world_ref="finance",
            lane_ref="capital_hilton_invoice",
            validity_scope=scope,
            proof_status="receipt_backed_operator_confirmation_proof_may_still_be_requested",
            reuse_policy="SUGGEST_APPLY_COMPATIBLE_SCOPE",
            conflict_policy="no_silent_overwrite_on_rate_mismatch",
            stale_policy="prior_year_rate_inform_only",
            authority_boundary=AUTHORITY_BOUNDARY,
            central_sync_allowed=True,
            allowed_surfaces=("Mission Control", "Telegram future surface", "agent handoff packet"),
            allowed_roles=("validation_role", "drafting_role", "delivery_readiness_role"),
            next_safe_move="Suggest compatible rate reuse; derive subtotal from dates x rate.",
        ),
        CrossLaneReusableFactBlock(
            fact_id="fact_capital_hilton_ap_route_token_v1",
            fact_type="ap_email_route",
            safe_display_label="AP route confirmed",
            value_posture="TOKENIZED_PROTECTED_VALUE",
            value_kind="ap_email_route",
            raw_value_allowed_in_read_model=False,
            tokenized_value_ref="tokref:local-only:capital_hilton:ap_route:v1",
            protected_store_ref="pii_vault_ref:local-only:ap_route:capital_hilton:v1",
            value_match_ref="matchref:scoped-keyed-local-hmac:tenant-client-route:v1",
            value_match_ref_policy="No public hash. Compare only inside protected local authority using scoped/keyed reference.",
            privacy_class="protected_contact_route",
            sensitivity_class="protected",
            source_receipt_ref="future_ap_route_confirmation_receipt",
            source_capture_ref="future_delivery_fact_capture_ap_route",
            source_workflow_session_ref="capital_hilton_invoice_workflow_session",
            source_block_id="ap_email_route",
            tenant_ref="openclaw_local",
            client_ref="capital_hilton",
            world_ref="finance",
            lane_ref="capital_hilton_invoice",
            validity_scope=scope,
            proof_status="operator_confirmed_route_proof_may_still_be_required",
            reuse_policy="REQUIRE_OPERATOR_CONFIRMATION",
            conflict_policy="tokenized_value_mismatch_shows_safe_summary_only",
            stale_policy="route_confirmation_stales_when client/contact context changes",
            authority_boundary=AUTHORITY_BOUNDARY,
            central_sync_allowed=False,
            allowed_surfaces=("Mission Control", "Telegram future surface", "agent handoff packet"),
            allowed_roles=("delivery_readiness_role", "validation_role", "security_gate_role"),
            next_safe_move="Use safe label to unlock route-aware blocks; never expose raw route in normal read-models.",
        ),
        CrossLaneReusableFactBlock(
            fact_id="fact_capital_hilton_po_reference_token_v1",
            fact_type="po_reference",
            safe_display_label="PO/payment reference captured",
            value_posture="TOKENIZED_PROTECTED_VALUE",
            value_kind="po_reference",
            raw_value_allowed_in_read_model=False,
            tokenized_value_ref="tokref:local-only:capital_hilton:po_reference:v1",
            protected_store_ref="pii_vault_ref:local-only:po_reference:capital_hilton:v1",
            value_match_ref="matchref:scoped-keyed-local-hmac:tenant-client-po:v1",
            value_match_ref_policy="No public raw digest. Same-client suggestion only after protected local comparison.",
            privacy_class="protected_payment_reference",
            sensitivity_class="protected",
            source_receipt_ref="future_po_reference_capture_receipt",
            source_capture_ref="future_delivery_fact_capture_po_reference",
            source_workflow_session_ref="capital_hilton_invoice_workflow_session",
            source_block_id="proof_po_reference",
            tenant_ref="openclaw_local",
            client_ref="capital_hilton",
            world_ref="finance",
            lane_ref="capital_hilton_invoice",
            validity_scope=scope,
            proof_status="proof_required_before_external_send_or_submit",
            reuse_policy="BLOCK_CROSS_TENANT",
            conflict_policy="privacy_boundary_conflict_blocks_raw_display",
            stale_policy="reference_stales_outside_invoice_or_payment_period",
            authority_boundary=AUTHORITY_BOUNDARY,
            central_sync_allowed=False,
            allowed_surfaces=("Mission Control", "agent handoff packet"),
            allowed_roles=("validation_role", "delivery_readiness_role", "security_gate_role"),
            next_safe_move="Suggest only inside same client/scope; require proof or operator confirmation.",
        ),
        CrossLaneReusableFactBlock(
            fact_id="fact_invoice_subtotal_calculated_state_blocked_copy",
            fact_type="invoice_subtotal",
            safe_display_label="Subtotal is derived from captured dates and rate",
            value_posture="SAFE_NON_SENSITIVE_VALUE",
            value_kind="calculated_state",
            raw_value_allowed_in_read_model=True,
            tokenized_value_ref=None,
            protected_store_ref=None,
            value_match_ref=None,
            value_match_ref_policy="Calculated state must derive from source facts; do not copy as reusable truth.",
            privacy_class="derived_operational",
            sensitivity_class="low",
            source_receipt_ref="derived_from_rate_and_date_receipts",
            source_capture_ref="derived_state_not_capture_source",
            source_workflow_session_ref="capital_hilton_invoice_workflow_session",
            source_block_id="invoice_packet",
            tenant_ref="openclaw_local",
            client_ref="capital_hilton",
            world_ref="finance",
            lane_ref="capital_hilton_invoice",
            validity_scope=scope,
            proof_status="derived_not_proof",
            reuse_policy="UNKNOWN_FAIL_CLOSED",
            conflict_policy="BLOCKED_CALCULATED_STATE_COPY",
            stale_policy="recompute_when_source_dates_or_rate_change",
            authority_boundary=AUTHORITY_BOUNDARY,
            central_sync_allowed=True,
            allowed_surfaces=("Mission Control", "agent handoff packet"),
            allowed_roles=("drafting_role", "delivery_readiness_role"),
            next_safe_move="Recompute subtotal from source facts; never reuse copied subtotal as truth.",
        ),
        CrossLaneReusableFactBlock(
            fact_id="fact_protected_evidence_ref_metadata_only_v1",
            fact_type="protected_evidence_reference",
            safe_display_label="Protected proof pointer attached",
            value_posture="PROTECTED_REFERENCE_ONLY",
            value_kind="protected_evidence_ref",
            raw_value_allowed_in_read_model=False,
            tokenized_value_ref="tokref:local-only:protected-evidence-ref:v1",
            protected_store_ref="protected_store_ref:local-only:evidence-metadata:v1",
            value_match_ref="matchref:local-protected-reference-comparison-only:v1",
            value_match_ref_policy="Metadata-only comparison; raw proof body cannot enter normal read-models.",
            privacy_class="protected_evidence_metadata",
            sensitivity_class="protected",
            source_receipt_ref="future_protected_reference_receipt",
            source_capture_ref="future_protected_evidence_capture",
            source_workflow_session_ref="capital_hilton_invoice_workflow_session",
            source_block_id="protected_evidence_reference",
            tenant_ref="openclaw_local",
            client_ref="capital_hilton",
            world_ref="finance",
            lane_ref="capital_hilton_invoice",
            validity_scope=scope,
            proof_status="protected_pointer_not_raw_proof",
            reuse_policy="REQUIRE_PROOF_OR_GUARDIAN_REVIEW",
            conflict_policy="privacy_boundary_conflict",
            stale_policy="protected_reference_stales_when source artifact rotates",
            authority_boundary=AUTHORITY_BOUNDARY,
            central_sync_allowed=False,
            allowed_surfaces=("Mission Control", "Guardian review", "agent handoff packet"),
            allowed_roles=("security_gate_role", "validation_role"),
            next_safe_move="Require Guardian/protected-evidence posture before any proof-bearing reuse.",
        ),
    )


def _policies() -> tuple[ReusableFactPolicy, ...]:
    return (
        ReusableFactPolicy(
            policy_id="policy_rate_amount_same_scope",
            fact_type="rate_amount",
            privacy_class="non_sensitive_operational",
            proof_required_for_auto_apply=True,
            proof_required_for_suggest_apply=False,
            auto_apply_allowed=False,
            suggest_apply_allowed=True,
            inform_only_allowed=True,
            operator_confirmation_required=True,
            guardian_review_required=False,
            de_tokenization_allowed=False,
            de_tokenization_authority="not_applicable_non_sensitive",
            central_sync_allowed=True,
            next_safe_move="Suggest rate reuse; auto-apply only in a future exact-scope/proof-backed lane.",
        ),
        ReusableFactPolicy(
            policy_id="policy_protected_contact_or_reference",
            fact_type="protected_route_or_reference",
            privacy_class="protected",
            proof_required_for_auto_apply=True,
            proof_required_for_suggest_apply=True,
            auto_apply_allowed=False,
            suggest_apply_allowed=True,
            inform_only_allowed=True,
            operator_confirmation_required=True,
            guardian_review_required=True,
            de_tokenization_allowed=False,
            de_tokenization_authority="explicit_protected_local_authority_required_future",
            central_sync_allowed=False,
            next_safe_move="Carry token refs and safe labels only; require local protected comparison for equivalence.",
        ),
        ReusableFactPolicy(
            policy_id="policy_calculated_state_no_copy",
            fact_type="calculated_state",
            privacy_class="derived_operational",
            proof_required_for_auto_apply=True,
            proof_required_for_suggest_apply=True,
            auto_apply_allowed=False,
            suggest_apply_allowed=False,
            inform_only_allowed=True,
            operator_confirmation_required=False,
            guardian_review_required=False,
            de_tokenization_allowed=False,
            de_tokenization_authority="not_applicable",
            central_sync_allowed=True,
            next_safe_move="Derive calculated state from source facts each time.",
        ),
    )


def _tokenization_policy() -> ProtectedValueTokenizationPolicy:
    return ProtectedValueTokenizationPolicy(
        policy_id="policy_protected_value_tokenization_scoped_keyed_v0",
        token_format="tokref:<local-only>:<tenant>:<fact-kind>:<version>",
        protected_store_policy="Raw value remains in explicit protected local store only; normal read-models carry refs.",
        raw_value_allowed_in_read_model=False,
        public_hash_allowed=False,
        value_match_strategy="scoped/keyed local HMAC-style comparison reference; no public raw SHA-256 of PII/protected values",
        token_rotation_policy="rotate token refs when protected store scope or local key changes",
        token_version="v1",
        redaction_required=True,
        de_tokenization_authority="none in this contract; future protected local authority required",
        allowed_surfaces_for_safe_label=("Mission Control", "Telegram future surface", "agent handoff packet"),
        allowed_surfaces_for_raw_value=(),
        forbidden_material=FORBIDDEN_MATERIAL,
        next_safe_move="Store safe labels and token refs only; block raw value display and public hash export.",
    )


def _decisions() -> tuple[ReusableFactReuseDecision, ...]:
    return (
        ReusableFactReuseDecision(
            decision_id="decision_rate_suggest_apply_same_client",
            candidate_fact_ref="fact_capital_hilton_rate_400_show_may_2026",
            target_block_ref="future_invoice_rate_confirmation",
            target_workflow_session_ref="future_capital_hilton_invoice_session",
            target_scope_ref="scope_capital_hilton_2026_invoice_music_service",
            decision="SUGGEST_APPLY",
            reason="Same client/service context can suggest rate reuse, but operator/proof gate still applies.",
            required_operator_action="Confirm whether this rate still applies.",
            required_proof_action="Attach or request proof if final send/submission depends on it.",
            privacy_boundary="non_sensitive_rate_no_protected_value",
            conflict_ref=None,
            stale_ref=None,
            readback_message="Prior Capital Hilton rate is available as a suggestion; subtotal will derive after dates are known.",
            elioperator_message="OpenClaw can remember the useful rate, but it still asks before treating it as current.",
            next_safe_move="Show as low-hanging-fruit confirmation.",
        ),
        ReusableFactReuseDecision(
            decision_id="decision_ap_route_token_needs_confirmation",
            candidate_fact_ref="fact_capital_hilton_ap_route_token_v1",
            target_block_ref="future_ap_email_route_block",
            target_workflow_session_ref="future_capital_hilton_invoice_session",
            target_scope_ref="scope_capital_hilton_2026_invoice_music_service",
            decision="NEEDS_OPERATOR_CONFIRMATION",
            reason="Protected route token can unlock a candidate block but cannot reveal or silently apply raw value.",
            required_operator_action="Confirm safe AP route label or request protected local display later.",
            required_proof_action="Protected local comparison only if needed.",
            privacy_boundary="raw route forbidden in normal read-model",
            conflict_ref=None,
            stale_ref=None,
            readback_message="AP route token exists; raw route is not shown.",
            elioperator_message="OpenClaw can know it has an AP route without printing the route everywhere.",
            next_safe_move="Render safe label and ask for confirmation.",
        ),
        ReusableFactReuseDecision(
            decision_id="decision_cross_tenant_po_blocked",
            candidate_fact_ref="fact_capital_hilton_po_reference_token_v1",
            target_block_ref="other_client_po_reference_block",
            target_workflow_session_ref="other_client_invoice_session",
            target_scope_ref="scope_other_client_invoice",
            decision="BLOCKED_CROSS_TENANT",
            reason="Protected payment references cannot cross tenant/client scope.",
            required_operator_action="Capture a scoped fact for the target client instead.",
            required_proof_action="None; reuse is blocked before proof consideration.",
            privacy_boundary="cross-tenant reuse fail-closed",
            conflict_ref=None,
            stale_ref=None,
            readback_message="Payment reference token blocked by tenant/client scope.",
            elioperator_message="OpenClaw will not let one client's payment reference bleed into another client's work.",
            next_safe_move="Fail closed and ask for target-scope capture.",
        ),
        ReusableFactReuseDecision(
            decision_id="decision_subtotal_copy_blocked",
            candidate_fact_ref="fact_invoice_subtotal_calculated_state_blocked_copy",
            target_block_ref="future_invoice_subtotal",
            target_workflow_session_ref="future_capital_hilton_invoice_session",
            target_scope_ref="scope_capital_hilton_2026_invoice_music_service",
            decision="BLOCKED_CALCULATED_STATE_COPY",
            reason="Subtotal is calculated state; it must derive from performance dates and rate.",
            required_operator_action="Confirm source facts if needed.",
            required_proof_action="Use date and rate receipts.",
            privacy_boundary="calculated_state_not_reusable_truth",
            conflict_ref=None,
            stale_ref=None,
            readback_message="Subtotal copy is blocked; recompute from source facts.",
            elioperator_message="OpenClaw does the math again instead of copying an old total.",
            next_safe_move="Derive from captured facts.",
        ),
        ReusableFactReuseDecision(
            decision_id="decision_prior_year_rate_inform_only",
            candidate_fact_ref="fact_prior_year_rate_stale",
            target_block_ref="future_rate_confirmation",
            target_workflow_session_ref="future_capital_hilton_invoice_session",
            target_scope_ref="scope_capital_hilton_2026_invoice_music_service",
            decision="INFORM_ONLY",
            reason="Prior-year fact is stale for the current invoice period.",
            required_operator_action="Re-confirm current rate.",
            required_proof_action="Find current rate proof if final send depends on it.",
            privacy_boundary="non_sensitive_rate",
            conflict_ref=None,
            stale_ref="stale_prior_year_rate_2025",
            readback_message="Prior-year rate is context only.",
            elioperator_message="Useful clue, not truth for this invoice.",
            next_safe_move="Ask for current confirmation.",
        ),
    )


def _conflicts() -> tuple[ReusableFactConflict, ...]:
    return (
        ReusableFactConflict(
            conflict_id="conflict_rate_400_vs_450",
            fact_type="rate_amount",
            active_fact_ref="fact_capital_hilton_rate_400_show_may_2026",
            candidate_fact_ref="fact_rate_candidate_450_show",
            conflict_type="VALUE_MISMATCH",
            scope_comparison="same client/service, candidate value differs",
            proof_rank_comparison="active operator receipt vs candidate unproven",
            stale_status="not_stale_but_conflicting",
            safe_display_summary="Active rate and candidate rate disagree; no silent overwrite.",
            raw_value_exposed=False,
            operator_resolution_options=("keep active rate", "accept candidate after confirmation", "park and request proof"),
            next_safe_move="Show conflict row with ELIOPERATOR explanation.",
        ),
        ReusableFactConflict(
            conflict_id="conflict_two_ap_route_tokens_disagree",
            fact_type="ap_email_route",
            active_fact_ref="fact_capital_hilton_ap_route_token_v1",
            candidate_fact_ref="fact_capital_hilton_ap_route_token_candidate_v2",
            conflict_type="TOKENIZED_VALUE_MISMATCH",
            scope_comparison="same client, protected route tokens do not match under local comparison",
            proof_rank_comparison="both require operator/Guardian review",
            stale_status="unknown_until_review",
            safe_display_summary="Two AP route tokens disagree.",
            raw_value_exposed=False,
            operator_resolution_options=("choose confirmed safe label", "request protected local review", "park route block"),
            next_safe_move="Do not expose raw route; ask for protected resolution.",
        ),
    )


def _impact_preview() -> ReusableFactImpactPreview:
    return ReusableFactImpactPreview(
        impact_preview_id="impact_preview_capital_hilton_low_hanging_fruit",
        reusable_fact_ref="fact_capital_hilton_rate_400_show_may_2026",
        affected_workflows=("capital_hilton_invoice_current", "future_capital_hilton_invoice_session"),
        affected_blocks=("rate_confirmation", "invoice_packet_subtotal_derivation", "delivery_readiness_context"),
        auto_apply_count=0,
        suggest_apply_count=2,
        inform_only_count=1,
        blocked_count=2,
        privacy_blocked_count=1,
        proof_required_count=2,
        operator_summary="One rate confirmation can help more than one Capital Hilton workflow block, but protected routes stay tokenized.",
        elioperator_summary="This is the workbench idea: answer low-hanging fruit once, reuse it carefully, and flag what still needs proof.",
        next_safe_move="Show safe impact preview; do not auto-apply live.",
    )


def _workbench_concept() -> CrossLaneOperatorWorkbenchConcept:
    return CrossLaneOperatorWorkbenchConcept(
        concept_id="cross_lane_operator_workbench_concept_v0",
        lanes=("Finance", "Mission Control", "future Telegram/Cassandra entry", "agent handoff packets"),
        buckets=WORKBENCH_BUCKETS,
        sorting_policy="low effort + high unlock value first; protected/proof-heavy blocks parked unless urgent",
        operator_bandwidth_policy="let operator answer known blocks out of order without forcing a serial wizard",
        low_hanging_fruit_policy="prefer non-sensitive receipt-backed confirmations like rate or dates",
        high_leverage_policy="surface facts that unlock several blocks, but require scope/proof checks",
        proof_bearing_policy="proof-heavy facts stay guided and do not expose raw bodies",
        protected_value_policy="token refs and safe labels only in normal read-models",
        conflict_policy="show conflicts and stale status instead of silent overwrite",
        parking_policy="park heavy/protected blocks with clear next safe move",
        next_safe_move_policy="recommend the next safe answerable block without making it a lockout",
    )


def _handoff_compatibility() -> ReusableFactHandoffCompatibility:
    return ReusableFactHandoffCompatibility(
        compatibility_id="reusable_fact_handoff_compatibility_v0",
        artifact_type="REUSABLE_FACT",
        schema_ref="cross_lane_reusable_block_registry_contract.CrossLaneReusableFactBlock",
        cross_surface_registry_ref="future_cross_surface_artifact_handoff_registry",
        reusable_fact_schema_ref="cross_lane_reusable_block_registry_contract_v0",
        origin_surface="Mission Control or Telegram future surface",
        source_channel="visual_agnostic_capture_or_agent_handoff",
        target_handler="future_reusable_fact_registry_handler",
        workflow_session_ref_required=True,
        idempotency_key_required=True,
        payload_hash_required=True,
        tokenized_value_ref_allowed=True,
        raw_value_forbidden=True,
        readback_required=True,
        elioperator_required=True,
        next_safe_move="Carry token refs, safe labels, and scope metadata only.",
    )


def _telegram_example() -> dict[str, Any]:
    return {
        "example_id": "telegram_cassandra_reusable_fact_entry_example",
        "addressed_actor": "Cassandra",
        "assigned_role": "validation_role",
        "origin_surface": "Telegram future surface",
        "source_channel": "conversational_capture_preview",
        "truth_owner": "receipt_backed_backend_state_not_telegram",
        "safe_payload_shape": {
            "workflow_session_ref": "capital_hilton_invoice_workflow_session",
            "block_id": "ap_email_route",
            "safe_display_label": "AP route confirmed",
            "tokenized_value_ref": "tokref:local-only:capital_hilton:ap_route:v1",
            "raw_value": "FORBIDDEN",
        },
        "next_safe_move": "Cassandra may explain or hand off; it may not reveal raw protected values or commit truth.",
    }


def build_cross_lane_reusable_block_registry_contract(
    *,
    generated_at: str | None = None,
) -> dict[str, Any]:
    scope = _scope()
    facts = _fact_blocks()
    policies = _policies()
    tokenization = _tokenization_policy()
    decisions = _decisions()
    conflicts = _conflicts()
    impact = _impact_preview()
    workbench = _workbench_concept()
    handoff = _handoff_compatibility()
    relationship_inventory = _relationship_inventory()

    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "contract_status": CONTRACT_STATUS,
        "generated_at": generated_at or utc_now(),
        "purpose": (
            "Define a future reusable-fact registry and protected value tokenization contract "
            "without live writes, raw protected values, or cross-lane auto-apply."
        ),
        "doctrine": {
            "reusable_fact_does_not_mean_raw_value": True,
            "tokenized_value_does_not_mean_proof": True,
            "hash_match_does_not_mean_permission_to_reveal": True,
            "calculated_state_must_derive_not_copy": True,
            "cross_tenant_reuse_defaults_false": True,
        },
        "model_schemas": {
            "cross_lane_reusable_fact_block": {
                "model_name": "CrossLaneReusableFactBlock",
                "required_fields": list(REQUIRED_REUSABLE_FACT_FIELDS),
                "value_postures": list(VALUE_POSTURES),
                "value_kinds": list(VALUE_KINDS),
            },
            "reusable_fact_scope": {
                "model_name": "ReusableFactScope",
                "required_fields": list(REQUIRED_SCOPE_FIELDS),
            },
            "reusable_fact_policy": {
                "model_name": "ReusableFactPolicy",
                "required_fields": list(REQUIRED_POLICY_FIELDS),
                "reuse_policies": list(REUSE_POLICIES),
            },
            "protected_value_tokenization_policy": {
                "model_name": "ProtectedValueTokenizationPolicy",
                "required_fields": list(REQUIRED_TOKENIZATION_POLICY_FIELDS),
            },
            "reusable_fact_reuse_decision": {
                "model_name": "ReusableFactReuseDecision",
                "required_fields": list(REQUIRED_DECISION_FIELDS),
                "decision_values": list(REUSE_DECISIONS),
            },
            "reusable_fact_conflict": {
                "model_name": "ReusableFactConflict",
                "required_fields": list(REQUIRED_CONFLICT_FIELDS),
                "conflict_types": list(CONFLICT_TYPES),
            },
            "reusable_fact_impact_preview": {
                "model_name": "ReusableFactImpactPreview",
                "required_fields": list(REQUIRED_IMPACT_FIELDS),
            },
            "cross_lane_operator_workbench_concept": {
                "model_name": "CrossLaneOperatorWorkbenchConcept",
                "required_fields": list(REQUIRED_WORKBENCH_FIELDS),
                "buckets": list(WORKBENCH_BUCKETS),
            },
            "reusable_fact_handoff_compatibility": {
                "model_name": "ReusableFactHandoffCompatibility",
                "required_fields": list(REQUIRED_HANDOFF_FIELDS),
            },
        },
        "reusable_fact_scope": asdict(scope),
        "reusable_fact_policies": [asdict(item) for item in policies],
        "protected_value_tokenization_policy": asdict(tokenization),
        "reusable_fact_blocks": [asdict(item) for item in facts],
        "reusable_fact_blocks_by_id": {item.fact_id: asdict(item) for item in facts},
        "reuse_decisions": [asdict(item) for item in decisions],
        "reuse_decisions_by_id": {item.decision_id: asdict(item) for item in decisions},
        "conflicts": [asdict(item) for item in conflicts],
        "conflicts_by_id": {item.conflict_id: asdict(item) for item in conflicts},
        "impact_preview": asdict(impact),
        "workbench_concept": asdict(workbench),
        "handoff_compatibility": asdict(handoff),
        "examples": {
            "safe_non_sensitive_rate_reuse": asdict(facts[0]),
            "protected_ap_email_route_token": asdict(facts[1]),
            "po_payment_reference_token": asdict(facts[2]),
            "conflict_rate_400_vs_450": asdict(conflicts[0]),
            "stale_prior_year_rate": asdict(decisions[4]),
            "protected_evidence_reference": asdict(facts[4]),
            "telegram_cassandra_entry": _telegram_example(),
        },
        "relationship_inventory": relationship_inventory,
        "verified_existing_pii_substrate": {
            "pii_vault": relationship_inventory["pii_vault"]["present"],
            "cassandra_pii_hooks": relationship_inventory["cassandra_pii_hooks"]["present"],
            "business_ops_ledger": relationship_inventory["business_ops_ledger"]["present"],
            "openclaw_sensitive_policy": relationship_inventory["openclaw_sensitive_policy"]["present"],
            "invoked_or_mutated_by_this_contract": False,
        },
        "security_privacy_requirements": {
            "no_raw_pii_in_generated_read_models": True,
            "no_raw_protected_values_in_operator_markdown": True,
            "public_raw_sha256_hashes_of_sensitive_values_allowed": False,
            "scoped_keyed_local_only_matching_refs_required": True,
            "tokenized_refs_are_not_proof": True,
            "de_tokenization_authority_must_be_explicit": True,
            "central_sync_false_for_protected_raw_values": True,
            "cross_tenant_reuse_fail_closed": True,
            "credentials_tokens_cookies_private_keys_forbidden": True,
        },
        "authority_boundary": AUTHORITY_BOUNDARY,
        "machine_proof": {
            "cross_lane_reusable_fact_block_model_present": True,
            "reusable_fact_scope_model_present": True,
            "reusable_fact_policy_model_present": True,
            "protected_value_tokenization_policy_model_present": True,
            "reusable_fact_reuse_decision_model_present": True,
            "reusable_fact_conflict_model_present": True,
            "reusable_fact_impact_preview_model_present": True,
            "operator_workbench_concept_model_present": True,
            "handoff_compatibility_model_present": True,
            "rate_reuse_non_sensitive": facts[0].value_posture == "SAFE_NON_SENSITIVE_VALUE",
            "rate_reuse_does_not_copy_subtotal": facts[3].conflict_policy == "BLOCKED_CALCULATED_STATE_COPY",
            "ap_route_uses_tokenized_value_ref": bool(facts[1].tokenized_value_ref)
            and facts[1].raw_value_allowed_in_read_model is False,
            "po_reference_uses_tokenized_value_ref": bool(facts[2].tokenized_value_ref)
            and facts[2].raw_value_allowed_in_read_model is False,
            "protected_evidence_raw_body_forbidden": facts[4].raw_value_allowed_in_read_model is False,
            "public_hash_allowed_false_for_sensitive_values": tokenization.public_hash_allowed is False,
            "cross_tenant_reuse_blocked": decisions[2].decision == "BLOCKED_CROSS_TENANT",
            "calculated_state_copy_blocked": decisions[3].decision == "BLOCKED_CALCULATED_STATE_COPY",
            "conflict_example_raw_value_exposed_false": all(item.raw_value_exposed is False for item in conflicts),
            "stale_example_inform_only": decisions[4].decision == "INFORM_ONLY",
            "handoff_forbids_raw_values": handoff.raw_value_forbidden is True,
            "elioperator_messages_present": all(item.elioperator_message for item in decisions),
            "all_live_authority_flags_false": all(value is False for value in AUTHORITY_BOUNDARY.values()),
            "credentials_or_secrets_included": False,
            "raw_private_bodies_included": False,
            "raw_sensitive_fixture_values_included": False,
            "content_hash": None,
        },
    }
    payload["machine_proof"]["content_hash"] = _content_hash(payload)
    return payload


def format_cross_lane_reusable_block_registry_contract(payload: dict[str, Any]) -> str:
    policy = payload["protected_value_tokenization_policy"]
    workbench = payload["workbench_concept"]
    lines = [
        "# Cross-Lane Reusable Block Registry / Tokenization Contract v0",
        "",
        "## ELIOPERATOR Summary",
        "",
        (
            "Reusable blocks let one safe answer help multiple workflows, but sensitive values stay protected. "
            "A reusable fact can carry a safe label or token reference without exposing the raw value."
        ),
        "",
        "This is not live reuse yet. It does not write the PII vault, de-tokenize, auto-apply facts, run agents, or touch external systems.",
        "",
        "## Why It Exists",
        "",
        "- Answer low-hanging-fruit blocks out of order.",
        "- Reuse high-leverage facts only inside the right tenant/client/scope.",
        "- Show conflicts and stale facts instead of silently overwriting.",
        "- Keep proof-heavy and protected blocks parked until a safe path exists.",
        "- Derive calculated values like subtotal instead of copying them as truth.",
        "",
        "## Protected Values",
        "",
        f"- Raw values allowed in normal read-models: `{str(policy['raw_value_allowed_in_read_model']).lower()}`",
        f"- Public hash allowed for protected values: `{str(policy['public_hash_allowed']).lower()}`",
        f"- Matching strategy: {policy['value_match_strategy']}",
        f"- De-tokenization authority: `{policy['de_tokenization_authority']}`",
        "",
        "## Workbench Buckets",
        "",
    ]
    lines.extend(f"- `{bucket}`" for bucket in workbench["buckets"])
    lines.extend(
        [
            "",
            "## Examples",
            "",
            "- Rate can be suggested as a non-sensitive reusable fact; subtotal still derives from source facts.",
            "- AP route and PO/payment references use token refs and safe labels, not raw values.",
            "- Protected evidence references point to protected material without placing raw bodies in read-models.",
            "- Telegram/Cassandra may front a request later, but receipt-backed backend state remains truth.",
            "",
            "## Authority",
            "",
        ]
    )
    for key, value in payload["authority_boundary"].items():
        lines.append(f"- {key}: `{str(value).lower()}`")
    lines.extend(
        [
            "",
            "## Next Safe Move",
            "",
            "Review the contract, then build a Cross-Surface Artifact Handoff Registry before any live reusable-fact write path.",
            "",
        ]
    )
    return "\n".join(lines)


@dataclass(frozen=True)
class ExportResult:
    schema_version: str
    json_path: str
    operator_path: str
    fact_count: int
    all_live_authority_flags_false: bool


def export_cross_lane_reusable_block_registry_contract(
    *,
    export_root: str | Path = DEFAULT_EXPORT_ROOT,
    generated_at: str | None = None,
) -> ExportResult:
    payload = build_cross_lane_reusable_block_registry_contract(generated_at=generated_at)
    root = Path(export_root)
    if not root.is_absolute():
        root = ROOT / root
    root.mkdir(parents=True, exist_ok=True)
    json_path = root / JSON_EXPORT_NAME
    operator_path = root / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(format_cross_lane_reusable_block_registry_contract(payload), encoding="utf-8")
    return ExportResult(
        schema_version=SCHEMA_VERSION,
        json_path=json_path.as_posix(),
        operator_path=operator_path.as_posix(),
        fact_count=len(payload["reusable_fact_blocks"]),
        all_live_authority_flags_false=payload["machine_proof"]["all_live_authority_flags_false"],
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export Cross-Lane Reusable Block Registry Contract.")
    parser.add_argument("--export-root", default=DEFAULT_EXPORT_ROOT.as_posix())
    parser.add_argument("--format", choices=("summary", "json", "operator"), default="operator")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    result = export_cross_lane_reusable_block_registry_contract(export_root=args.export_root)
    if args.format == "summary":
        print(stable_json(asdict(result)), end="")
    elif args.format == "json":
        payload = build_cross_lane_reusable_block_registry_contract()
        print(stable_json(payload), end="")
    else:
        payload = build_cross_lane_reusable_block_registry_contract()
        print(format_cross_lane_reusable_block_registry_contract(payload), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
