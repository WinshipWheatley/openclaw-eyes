"""Meaningful Work Gravity Contract / Opt-In Compute Commons Scout v0.

This deterministic read-model defines Meaningful Work Gravity as an
operator-sovereign compass. It is contract/read-model only: no live scoring,
task rerouting, scope expansion, Build Cue write, device enrollment, idle
compute, remote workload, model/tool/agent/runtime execution, network access,
or external action occurs here.
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

SCHEMA_VERSION = "meaningful_work_gravity_contract_v0"
READ_MODEL_ID = "meaningful_work_gravity_contract"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
OPERATOR_EXPORT_NAME = f"{READ_MODEL_ID}_OPERATOR.md"
CONTRACT_STATUS = "DETERMINISTIC_NON_EXECUTING_MEANINGFUL_WORK_GRAVITY_CONTRACT"

WORK_CATEGORIES = (
    "immediate_operator_need",
    "reusable_system_rail",
    "safety_privacy_improvement",
    "efficiency_waste_reduction",
    "client_productizable_pattern",
    "creative_artistic_value",
    "learning_onboarding_value",
    "public_good_or_community_usefulness",
    "low_compounding_sludge",
    "harmful_refuse",
    "unknown_needs_framing",
)

MEANINGFUL_WORK_SIGNAL_TYPES = (
    "meaningful_work_signal",
    "compounding_opportunity",
    "anti_sludge_warning",
    "reusable_rail_candidate",
    "operator_sovereignty_check",
    "compute_commons_candidate",
    "consent_required",
    "unknown_fail_closed",
)

RECOMMENDED_HANDLINGS = (
    "COMPLETE_DIRECTLY_ONLY",
    "COMPLETE_AND_NOTE_BUILD_CUE",
    "COMPLETE_AND_ADD_TINY_GUARDRAIL",
    "ASK_OPERATOR_TO_PRESERVE_PATH",
    "DEFER_TO_WORK_TERRAIN",
    "REFUSE_FOR_SAFETY",
    "UNKNOWN_NEEDS_FRAMING",
)

COMPUTE_COMMONS_ELIGIBILITY_STATUSES = (
    "ELIGIBLE_FOR_OPERATOR_REVIEW",
    "NEEDS_MORE_DETAIL",
    "BLOCKED_PRIVACY_RISK",
    "BLOCKED_RESOURCE_RISK",
    "BLOCKED_HARMFUL_USE",
    "BLOCKED_LEGAL_OR_SAFETY_BOUNDARY",
    "OPT_IN_DISABLED",
    "UNKNOWN_FAIL_CLOSED",
)

BUILDER_BLOCKER_TYPES = (
    "MORALIZING_LANGUAGE",
    "HIDDEN_SCOPE_EXPANSION",
    "TASK_HIJACK",
    "VISIBLE_IMPACT_SCORE",
    "FAKE_EFFICIENCY_CLAIM",
    "REPEATED_CONTEXT_REDISCOVERY",
    "ONE_OFF_GLUE_WHERE_REGISTRY_EXISTS",
    "RAW_PII_IN_NORMAL_READMODEL",
    "UNBOUNDED_COMPUTE_COMMONS",
    "OPT_IN_BYPASS",
    "HARMFUL_WORKLOAD",
    "UNKNOWN_FAIL_CLOSED",
)

FORBIDDEN_COMPUTE_COMMONS_USES = (
    "hidden compute use",
    "private local data access",
    "credential access",
    "crypto mining",
    "spam or fraud",
    "surveillance",
    "malware",
    "weaponization or autonomy-sensitive compute without strict refusal or review",
    "unbounded thermal, battery, network, disk, or user-activity impact",
    "legal or safety boundary bypass",
)

REQUIRED_CONTRACT_FIELDS = (
    "contract_id",
    "doctrine",
    "immediate_task_policy",
    "compounding_opportunity_policy",
    "anti_sludge_policy",
    "operator_sovereignty_policy",
    "privacy_policy",
    "compute_efficiency_policy",
    "build_cue_integration_policy",
    "opt_in_compute_commons_policy",
    "non_goals",
    "authority_boundary",
    "next_safe_move",
)

REQUIRED_SIGNAL_FIELDS = (
    "signal_id",
    "work_item_ref",
    "work_category",
    "meaningful_work_signal_type",
    "immediate_operator_value",
    "compounding_value",
    "reusable_rail_potential",
    "safety_privacy_potential",
    "energy_compute_efficiency_potential",
    "public_good_or_community_potential",
    "client_productizable_pattern_potential",
    "sludge_risk",
    "harmful_risk",
    "suggested_operator_nudge",
    "build_cue_candidate_ref",
    "next_safe_move",
)

REQUIRED_SOVEREIGNTY_FIELDS = (
    "guardrail_id",
    "immediate_task_first",
    "optional_expansion_only",
    "no_moralizing",
    "no_hidden_scope_expansion",
    "no_gamified_score",
    "no_social_scoring",
    "no_shame_language",
    "no_task_hijack",
    "operator_override_allowed",
    "refusal_only_for_hard_safety_boundary",
    "elioperator_required",
    "next_safe_move",
)

REQUIRED_ANTI_SLUDGE_FIELDS = (
    "policy_id",
    "sludge_patterns",
    "retry_loop_patterns",
    "context_rediscovery_patterns",
    "fake_progress_patterns",
    "excessive_model_call_patterns",
    "one_off_prompt_glue_patterns",
    "hardcoded_path_patterns",
    "raw_pii_risk_patterns",
    "deterministic_alternative_hint",
    "build_cue_routing",
    "next_safe_move",
)

REQUIRED_OPPORTUNITY_FIELDS = (
    "opportunity_id",
    "immediate_task_ref",
    "direct_solution",
    "compounding_path",
    "reusable_rail_candidate",
    "privacy_or_security_improvement",
    "deterministic_substrate_opportunity",
    "future_client_ship_reuse",
    "public_good_potential",
    "cost_to_preserve_path",
    "risk_of_scope_creep",
    "operator_choice",
    "recommended_handling",
    "next_safe_move",
)

REQUIRED_NUDGE_FIELDS = (
    "nudge_id",
    "trigger_ref",
    "nudge_type",
    "operator_text",
    "why_it_matters",
    "immediate_task_impact",
    "optional_path",
    "no_action_option",
    "anti_manipulation_check",
    "next_safe_move",
)

REQUIRED_COMPUTE_EFFICIENCY_FIELDS = (
    "signal_id",
    "work_item_ref",
    "waste_type",
    "deterministic_alternative",
    "estimated_context_reduction",
    "retry_reduction_potential",
    "local_first_substitution",
    "meaningful_work_per_watt_note",
    "guardrail",
    "next_safe_move",
)

REQUIRED_COMPUTE_COMMONS_CONCEPT_FIELDS = (
    "concept_id",
    "description",
    "eligibility_policy",
    "consent_policy",
    "resource_boundary",
    "privacy_boundary",
    "workload_safety_policy",
    "mission_alignment_policy",
    "operator_visibility",
    "opt_in_status",
    "opt_out_policy",
    "audit_receipts_required",
    "forbidden_uses",
    "non_goals",
    "next_safe_move",
)

REQUIRED_COMPUTE_COMMONS_CANDIDATE_FIELDS = (
    "candidate_id",
    "workload_summary",
    "mission_alignment_summary",
    "resource_request_summary",
    "privacy_class",
    "data_access_required",
    "can_run_without_private_data",
    "operator_benefit",
    "public_good_potential",
    "safety_review_required",
    "consent_required",
    "local_resource_caps",
    "eligibility_status",
    "rejection_reasons",
    "elioperator_prompt",
    "next_safe_move",
)

REQUIRED_BUILDER_BLOCKER_FIELDS = (
    "blocker_id",
    "blocker_type",
    "condition",
    "severity",
    "elioperator_warning",
    "builder_action_required",
    "fail_closed",
    "next_safe_move",
)

AUTHORITY_BOUNDARY = {
    "live_meaningful_work_scoring_allowed": False,
    "live_task_rerouting_allowed": False,
    "live_scope_expansion_allowed": False,
    "live_build_cue_write_allowed": False,
    "live_compute_commons_allowed": False,
    "live_idle_compute_allowed": False,
    "live_device_enrollment_allowed": False,
    "live_remote_workload_allowed": False,
    "live_agent_nudging_allowed": False,
    "live_model_call_allowed": False,
    "live_tool_execution_allowed": False,
    "live_runtime_dispatch_allowed": False,
    "live_network_allowed": False,
    "live_external_action_allowed": False,
    "credential_handling_allowed": False,
    "raw_body_ingestion_allowed": False,
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
    "approval_submission_allowed": False,
    "mission_control_swift_change_allowed": False,
    "mac_sync_import_allowed": False,
    "git_push_pull_fetch_allowed": False,
    "backend_state_mutation_allowed": False,
}

RELATIONSHIP_REF_PATHS = {
    "work_terrain_surface_map_build_cue_scout": "generated/read_models/work_terrain_surface_map_build_cue_scout.json",
    "work_terrain_build_cue_reconciliation_queue": (
        "generated/read_models/work_terrain_build_cue_reconciliation_queue.json"
    ),
    "make_winship_life_easier_batch_manifest": "generated/read_models/make_winship_life_easier_batch_manifest.json",
    "operator_question_assist_scope_expansion_contract": (
        "generated/read_models/operator_question_assist_scope_expansion_contract.json"
    ),
    "bridge_routing_operator_attention_contract": (
        "generated/read_models/bridge_routing_operator_attention_contract.json"
    ),
    "agent_conversation_handoff_step_packet_contract": (
        "generated/read_models/agent_conversation_handoff_step_packet_contract.json"
    ),
    "agent_execution_packet_compiler_contract": (
        "generated/read_models/agent_execution_packet_compiler_contract.json"
    ),
    "cross_lane_reusable_block_registry_contract": (
        "generated/read_models/cross_lane_reusable_block_registry_contract.json"
    ),
    "cross_surface_artifact_handoff_registry_contract": (
        "generated/read_models/cross_surface_artifact_handoff_registry_contract.json"
    ),
    "cross_surface_handoff_registry_metadata_alignment": (
        "generated/read_models/cross_surface_handoff_registry_metadata_alignment.json"
    ),
    "openclaw_sensitive_policy": "openclaw_sensitive_policy.py",
    "guided_capture_protected_evidence_path_contract": (
        "generated/read_models/guided_capture_protected_evidence_path_contract.json"
    ),
    "guardian_protected_access_gate_spec": (
        "generated/read_models/guardian_protected_access_gate_spec.json"
    ),
}


@dataclass(frozen=True)
class MeaningfulWorkGravityContract:
    contract_id: str
    doctrine: tuple[str, ...]
    immediate_task_policy: str
    compounding_opportunity_policy: str
    anti_sludge_policy: str
    operator_sovereignty_policy: str
    privacy_policy: str
    compute_efficiency_policy: str
    build_cue_integration_policy: str
    opt_in_compute_commons_policy: str
    non_goals: tuple[str, ...]
    authority_boundary: dict[str, bool]
    next_safe_move: str


@dataclass(frozen=True)
class MeaningfulWorkSignal:
    signal_id: str
    work_item_ref: str
    work_category: str
    meaningful_work_signal_type: str
    immediate_operator_value: str
    compounding_value: str
    reusable_rail_potential: str
    safety_privacy_potential: str
    energy_compute_efficiency_potential: str
    public_good_or_community_potential: str
    client_productizable_pattern_potential: str
    sludge_risk: str
    harmful_risk: str
    suggested_operator_nudge: str
    build_cue_candidate_ref: str | None
    next_safe_move: str


@dataclass(frozen=True)
class OperatorSovereigntyGuardrail:
    guardrail_id: str
    immediate_task_first: bool
    optional_expansion_only: bool
    no_moralizing: bool
    no_hidden_scope_expansion: bool
    no_gamified_score: bool
    no_social_scoring: bool
    no_shame_language: bool
    no_task_hijack: bool
    operator_override_allowed: bool
    refusal_only_for_hard_safety_boundary: bool
    elioperator_required: bool
    next_safe_move: str


@dataclass(frozen=True)
class AntiSludgeDetectionPolicy:
    policy_id: str
    sludge_patterns: tuple[str, ...]
    retry_loop_patterns: tuple[str, ...]
    context_rediscovery_patterns: tuple[str, ...]
    fake_progress_patterns: tuple[str, ...]
    excessive_model_call_patterns: tuple[str, ...]
    one_off_prompt_glue_patterns: tuple[str, ...]
    hardcoded_path_patterns: tuple[str, ...]
    raw_pii_risk_patterns: tuple[str, ...]
    deterministic_alternative_hint: str
    build_cue_routing: str
    next_safe_move: str


@dataclass(frozen=True)
class CompoundingOpportunity:
    opportunity_id: str
    immediate_task_ref: str
    direct_solution: str
    compounding_path: str
    reusable_rail_candidate: str
    privacy_or_security_improvement: str
    deterministic_substrate_opportunity: str
    future_client_ship_reuse: str
    public_good_potential: str
    cost_to_preserve_path: str
    risk_of_scope_creep: str
    operator_choice: str
    recommended_handling: str
    next_safe_move: str


@dataclass(frozen=True)
class ELIOperatorNudge:
    nudge_id: str
    trigger_ref: str
    nudge_type: str
    operator_text: str
    why_it_matters: str
    immediate_task_impact: str
    optional_path: str
    no_action_option: str
    anti_manipulation_check: str
    next_safe_move: str


@dataclass(frozen=True)
class ComputeEfficiencySignal:
    signal_id: str
    work_item_ref: str
    waste_type: str
    deterministic_alternative: str
    estimated_context_reduction: str
    retry_reduction_potential: str
    local_first_substitution: str
    meaningful_work_per_watt_note: str
    guardrail: str
    next_safe_move: str


@dataclass(frozen=True)
class OptInComputeCommonsConcept:
    concept_id: str
    description: str
    eligibility_policy: str
    consent_policy: str
    resource_boundary: str
    privacy_boundary: str
    workload_safety_policy: str
    mission_alignment_policy: str
    operator_visibility: str
    opt_in_status: str
    opt_out_policy: str
    audit_receipts_required: bool
    forbidden_uses: tuple[str, ...]
    non_goals: tuple[str, ...]
    next_safe_move: str


@dataclass(frozen=True)
class ComputeCommonsCandidate:
    candidate_id: str
    workload_summary: str
    mission_alignment_summary: str
    resource_request_summary: str
    privacy_class: str
    data_access_required: str
    can_run_without_private_data: bool
    operator_benefit: str
    public_good_potential: str
    safety_review_required: bool
    consent_required: bool
    local_resource_caps: tuple[str, ...]
    eligibility_status: str
    rejection_reasons: tuple[str, ...]
    elioperator_prompt: str
    next_safe_move: str


@dataclass(frozen=True)
class MeaningfulWorkBuilderBlocker:
    blocker_id: str
    blocker_type: str
    condition: str
    severity: str
    elioperator_warning: str
    builder_action_required: str
    fail_closed: bool
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


def _gravity_contract() -> MeaningfulWorkGravityContract:
    return MeaningfulWorkGravityContract(
        contract_id="meaningful_work_gravity_contract_v0",
        doctrine=(
            "Complete the immediate operator task first.",
            "Do not hijack, moralize, shame, rank, or manipulate.",
            "When a useful reusable rail is cheap and safe, preserve it or park a Build Cue candidate.",
            "Prefer deterministic local rails over repeated model churn.",
            "Convert future opportunities into optional Build Cue or Work Terrain candidates, not active scope creep.",
            "Compute Commons is future opt-in only and default off.",
        ),
        immediate_task_policy="The current operator task remains the lane unless the operator changes it or a hard safety boundary blocks it.",
        compounding_opportunity_policy=(
            "Compounding paths may be noted, guarded, or parked only when they are cheap, bounded, and do not slow the direct task."
        ),
        anti_sludge_policy=(
            "Detect retry loops, fake progress, one-off prompt glue, broad rediscovery, and hardcoded rails; route durable fixes to Build Cue."
        ),
        operator_sovereignty_policy=(
            "The operator can keep a task one-off. Suggestions must be optional and written in plain ELIOPERATOR language."
        ),
        privacy_policy=(
            "Protected values remain tokenized or referenced. Raw private bodies, credentials, and protected material stay out of normal read-models."
        ),
        compute_efficiency_policy=(
            "Use qualitative work-per-watt posture unless measured; avoid fake numeric energy claims."
        ),
        build_cue_integration_policy=(
            "Future work should land as Build Cue or Work Terrain candidates, not hidden live scope expansion."
        ),
        opt_in_compute_commons_policy=(
            "Future idle compute assistance is default off, consent-gated, resource-capped, private-data-free, and audit-receipted."
        ),
        non_goals=(
            "no live scoring system",
            "no distributed compute system",
            "no task scheduler",
            "no device agent",
            "no network lane",
            "no runtime, queue, or tool execution",
            "no moral ranking engine",
            "no productization",
        ),
        authority_boundary=AUTHORITY_BOUNDARY,
        next_safe_move="Review the contract, then wire future Build Cue integration only after an explicit lane asks for it.",
    )


def _sovereignty_guardrail() -> OperatorSovereigntyGuardrail:
    return OperatorSovereigntyGuardrail(
        guardrail_id="operator_sovereignty_guardrail_v0",
        immediate_task_first=True,
        optional_expansion_only=True,
        no_moralizing=True,
        no_hidden_scope_expansion=True,
        no_gamified_score=True,
        no_social_scoring=True,
        no_shame_language=True,
        no_task_hijack=True,
        operator_override_allowed=True,
        refusal_only_for_hard_safety_boundary=True,
        elioperator_required=True,
        next_safe_move="Use the gravity signal as a compass, never as a command over the operator.",
    )


def _anti_sludge_policy() -> AntiSludgeDetectionPolicy:
    return AntiSludgeDetectionPolicy(
        policy_id="anti_sludge_detection_policy_v0",
        sludge_patterns=(
            "repeated context rediscovery",
            "looping agent retries",
            "fake readback without state",
            "UI success without backend proof",
            "repeated bespoke shuttle prompts where a registry can help",
            "one-off hardcoded rails where a reusable contract is cheap",
            "broad scans instead of bounded read-model use",
            "moralizing audit bloat",
            "compute-saving analysis that itself burns unnecessary compute",
        ),
        retry_loop_patterns=(
            "same missing fact requested repeatedly without durable capture",
            "same validation failure retried without narrowing input",
            "agent handoff restarts from scratch instead of using a context packet",
        ),
        context_rediscovery_patterns=(
            "large repo scans when generated read-models answer the question",
            "re-reading stale prompts instead of current contract/readback state",
            "manual Mac/PC relay prompts repeated without post-office metadata",
        ),
        fake_progress_patterns=(
            "readiness report that does not name a receipt, state row, artifact, or blocker",
            "screen closeout that does not reflect backend readback",
            "claimed generated artifact without file path and hash",
        ),
        excessive_model_call_patterns=(
            "model retries replacing deterministic parser or validator",
            "new agent packet where a local fixture test would prove the boundary",
            "summarization churn without a saved read-model",
        ),
        one_off_prompt_glue_patterns=(
            "bespoke shuttle instructions repeated after a registry exists",
            "custom capture packet with UI-only fields",
            "hardcoded client route leaking into generic framework code",
        ),
        hardcoded_path_patterns=(
            "Mac-only path embedded in backend contract",
            "client-specific Coupa or AP assumption in reusable layer",
            "C-drive artifact writes from WSL backend",
        ),
        raw_pii_risk_patterns=(
            "raw private body in generated JSON",
            "public raw hash of sensitive value",
            "credential, cookie, token, bank, tax, or remit data in normal read-model",
        ),
        deterministic_alternative_hint=(
            "Prefer receipt/readback, schema validation, token refs, and generated read-models before model retries."
        ),
        build_cue_routing=(
            "If the durable fix is out of lane, finish the direct task and park a Build Cue candidate."
        ),
        next_safe_move="Use this policy in reviews and future Work Terrain cues; do not activate a live detector here.",
    )


def _signals() -> tuple[MeaningfulWorkSignal, ...]:
    return (
        MeaningfulWorkSignal(
            signal_id="signal_capital_hilton_steel_thread",
            work_item_ref="capital_hilton_invoice_steel_thread",
            work_category="immediate_operator_need",
            meaningful_work_signal_type="compounding_opportunity",
            immediate_operator_value="Move a real invoice closer to payment.",
            compounding_value="Leaves visual-agnostic capture, receipt/readback, artifact preview, and delivery-facts rails behind.",
            reusable_rail_potential="high",
            safety_privacy_potential="high",
            energy_compute_efficiency_potential="less repeated context and fewer bespoke handoff prompts",
            public_good_or_community_potential="indirect, through safer reusable operator systems",
            client_productizable_pattern_potential="strong pattern for future client ships",
            sludge_risk="medium if every handoff remains bespoke",
            harmful_risk="low when external send/Coupa gates stay closed",
            suggested_operator_nudge="Finish invoice lane first; preserve reusable rails only when they are already in hand.",
            build_cue_candidate_ref="post_office_metadata_alignment_followup",
            next_safe_move="Use existing readbacks and keep external authority gated.",
        ),
        MeaningfulWorkSignal(
            signal_id="signal_low_stakes_one_off",
            work_item_ref="low_stakes_one_off_task",
            work_category="low_compounding_sludge",
            meaningful_work_signal_type="operator_sovereignty_check",
            immediate_operator_value="Solve a small operator request quickly.",
            compounding_value="none required",
            reusable_rail_potential="low",
            safety_privacy_potential="low",
            energy_compute_efficiency_potential="best handled directly without extra contract work",
            public_good_or_community_potential="not applicable",
            client_productizable_pattern_potential="low",
            sludge_risk="low if completed directly; high if over-governed",
            harmful_risk="low",
            suggested_operator_nudge="No need to expand this lane.",
            build_cue_candidate_ref=None,
            next_safe_move="Complete directly and stop.",
        ),
        MeaningfulWorkSignal(
            signal_id="signal_repeated_handoff_churn",
            work_item_ref="manual_mac_pc_readback_shuttle",
            work_category="efficiency_waste_reduction",
            meaningful_work_signal_type="anti_sludge_warning",
            immediate_operator_value="Keep current handoff working.",
            compounding_value="Post-office metadata can reduce repeated relay instructions later.",
            reusable_rail_potential="high",
            safety_privacy_potential="medium",
            energy_compute_efficiency_potential="fewer repeated scans and prompt rewrites",
            public_good_or_community_potential="indirect, through calmer operator workflows",
            client_productizable_pattern_potential="high",
            sludge_risk="high if each package remains custom",
            harmful_risk="low if metadata stays additive",
            suggested_operator_nudge="Finish the current package and park the registry alignment path.",
            build_cue_candidate_ref="cross_surface_handoff_registry_metadata_alignment",
            next_safe_move="Use metadata-only alignment; do not replace working rails.",
        ),
        MeaningfulWorkSignal(
            signal_id="signal_privacy_tokenization",
            work_item_ref="cross_lane_reusable_block_registry_contract",
            work_category="safety_privacy_improvement",
            meaningful_work_signal_type="reusable_rail_candidate",
            immediate_operator_value="Protect reusable facts from leaking raw sensitive values.",
            compounding_value="Future workflows can reuse safe labels and token refs without exposing raw values.",
            reusable_rail_potential="high",
            safety_privacy_potential="high",
            energy_compute_efficiency_potential="less repeated private-data handling",
            public_good_or_community_potential="safer reusable software pattern",
            client_productizable_pattern_potential="high",
            sludge_risk="medium if privacy is handled ad hoc each time",
            harmful_risk="medium if raw protected values leak",
            suggested_operator_nudge="Keep this as a contract until a protected local handler exists.",
            build_cue_candidate_ref="future_protected_value_handler",
            next_safe_move="Preserve tokenization rules; do not mutate a live vault here.",
        ),
        MeaningfulWorkSignal(
            signal_id="signal_compute_commons_public_good_candidate",
            work_item_ref="future_idle_validation_batch",
            work_category="public_good_or_community_usefulness",
            meaningful_work_signal_type="compute_commons_candidate",
            immediate_operator_value="No immediate execution; concept only.",
            compounding_value="Future opted-in ships might help validation workloads without private data.",
            reusable_rail_potential="medium",
            safety_privacy_potential="high if strict consent and caps exist",
            energy_compute_efficiency_potential="idle compute may be useful only when explicitly consented and bounded",
            public_good_or_community_potential="possible, after review",
            client_productizable_pattern_potential="medium",
            sludge_risk="high if it becomes hidden background work",
            harmful_risk="high without consent, privacy, and workload safety review",
            suggested_operator_nudge="Keep default off; require explicit opt-in and resource caps.",
            build_cue_candidate_ref="future_compute_commons_review_lane",
            next_safe_move="Do not run anything; model candidate eligibility only.",
        ),
    )


def _opportunities() -> tuple[CompoundingOpportunity, ...]:
    return (
        CompoundingOpportunity(
            opportunity_id="opportunity_capital_hilton_invoice_rails",
            immediate_task_ref="capital_hilton_invoice_delivery",
            direct_solution="Capture real invoice facts, generate/read back local state, and prepare artifact/readiness rails.",
            compounding_path="Preserve visual-agnostic capture, post-office metadata, and reusable-fact privacy contracts.",
            reusable_rail_candidate="capture_request_to_receipt_readback_to_closeout",
            privacy_or_security_improvement="protected evidence references and tokenization contract",
            deterministic_substrate_opportunity="SQLite receipt/readback plus generated read-models",
            future_client_ship_reuse="invoice capture and delivery facts pattern can be specialized per client later",
            public_good_potential="low direct, high process safety",
            cost_to_preserve_path="low when added as contract/read-model during the lane",
            risk_of_scope_creep="medium if rails replace invoice progress",
            operator_choice="Operator may keep this as the Capital Hilton lane or ask for reusable build-out later.",
            recommended_handling="COMPLETE_AND_NOTE_BUILD_CUE",
            next_safe_move="Keep solving the invoice; park larger reuse as Work Terrain.",
        ),
        CompoundingOpportunity(
            opportunity_id="opportunity_low_stakes_one_off",
            immediate_task_ref="small_local_answer_or_file_check",
            direct_solution="Answer or check directly.",
            compounding_path="No durable rail needed.",
            reusable_rail_candidate="none",
            privacy_or_security_improvement="none",
            deterministic_substrate_opportunity="none beyond ordinary tests if code changes",
            future_client_ship_reuse="low",
            public_good_potential="low",
            cost_to_preserve_path="not worth extra ceremony",
            risk_of_scope_creep="high if over-modeled",
            operator_choice="Complete directly.",
            recommended_handling="COMPLETE_DIRECTLY_ONLY",
            next_safe_move="Do the small task and stop.",
        ),
        CompoundingOpportunity(
            opportunity_id="opportunity_compute_commons_scout",
            immediate_task_ref="future_public_good_validation_workload",
            direct_solution="Do not execute. Capture only a concept and eligibility checklist.",
            compounding_path="Opt-in compute commons candidate model with consent, caps, safety, and receipts.",
            reusable_rail_candidate="compute_commons_candidate_review_packet",
            privacy_or_security_improvement="default-off consent and no-private-data policy",
            deterministic_substrate_opportunity="eligibility read-model before any runtime design",
            future_client_ship_reuse="possible only after explicit opt-in program exists",
            public_good_potential="possible for safe validation batches",
            cost_to_preserve_path="low as a contract",
            risk_of_scope_creep="high if interpreted as device enrollment",
            operator_choice="Review later; no live compute here.",
            recommended_handling="DEFER_TO_WORK_TERRAIN",
            next_safe_move="Keep concept-only and block all live compute authority.",
        ),
    )


def _nudges() -> tuple[ELIOperatorNudge, ...]:
    return (
        ELIOperatorNudge(
            nudge_id="nudge_preserve_reusable_rail",
            trigger_ref="opportunity_capital_hilton_invoice_rails",
            nudge_type="optional_reusable_rail",
            operator_text="This can stay a one-off fix, or we can preserve the reusable rail cheaply while we are already here.",
            why_it_matters="A tiny durable rail can reduce future relay churn.",
            immediate_task_impact="Must not slow or replace the direct task.",
            optional_path="Park a Build Cue or add a narrow contract when already in scope.",
            no_action_option="Complete the current task and leave reuse alone.",
            anti_manipulation_check="No score, shame, urgency trick, or hidden reroute.",
            next_safe_move="Ask only if preserving the path would expand the lane.",
        ),
        ELIOperatorNudge(
            nudge_id="nudge_handoff_churn",
            trigger_ref="signal_repeated_handoff_churn",
            nudge_type="anti_sludge_warning",
            operator_text=(
                "This looks like a repeated handoff pattern. I will finish the current task and park a Build Cue "
                "so we can reduce relay churn later."
            ),
            why_it_matters="Repeated manual relay burns context and attention.",
            immediate_task_impact="Current handoff still completes.",
            optional_path="Use post-office metadata later.",
            no_action_option="Keep the manual package path for now.",
            anti_manipulation_check="No live automation and no claim that migration already happened.",
            next_safe_move="Record the candidate; do not replace the working rail.",
        ),
        ELIOperatorNudge(
            nudge_id="nudge_lane_expansion_stop",
            trigger_ref="operator_sovereignty_guardrail_v0",
            nudge_type="scope_boundary",
            operator_text="This would expand the lane. I am not doing that unless you ask.",
            why_it_matters="Operator sovereignty beats clever scope expansion.",
            immediate_task_impact="Keeps the current task bounded.",
            optional_path="Ask for a follow-up lane if the expansion is useful.",
            no_action_option="Proceed with the original task only.",
            anti_manipulation_check="Plain statement, no pressure.",
            next_safe_move="Stay inside the requested lane.",
        ),
        ELIOperatorNudge(
            nudge_id="nudge_visible_score_blocked",
            trigger_ref="blocker_visible_impact_score",
            nudge_type="builder_warning",
            operator_text=(
                "This turns the compass into a scoreboard. Use an internal signal and operator-readable option instead."
            ),
            why_it_matters="Visible scores can manipulate behavior and invite ranking.",
            immediate_task_impact="Blocks score UI, not useful direct work.",
            optional_path="Use qualitative signal labels and ELIOPERATOR choices.",
            no_action_option="Remove scoring language entirely.",
            anti_manipulation_check="Blocks gamification and shame framing.",
            next_safe_move="Keep signal internal and non-numeric.",
        ),
    )


def _compute_efficiency_signals() -> tuple[ComputeEfficiencySignal, ...]:
    return (
        ComputeEfficiencySignal(
            signal_id="compute_signal_post_office_metadata",
            work_item_ref="manual_mac_pc_handoff_churn",
            waste_type="repeated bespoke relay prompts",
            deterministic_alternative="typed post-office metadata and readback contracts",
            estimated_context_reduction="qualitative reduction from less rediscovery",
            retry_reduction_potential="fewer repeated package-shape fixes once fields are standardized",
            local_first_substitution="generated read-model and local tests before model retries",
            meaningful_work_per_watt_note="Prefer durable local contracts over repeated model churn when the pattern is known.",
            guardrail="No fake numeric energy savings; only qualitative posture unless measured.",
            next_safe_move="Use this as a Build Cue signal, not a live optimizer.",
        ),
        ComputeEfficiencySignal(
            signal_id="compute_signal_capture_readback_proof",
            work_item_ref="capital_hilton_capture_loop",
            waste_type="UI success without backend proof",
            deterministic_alternative="receipt/state/readback and closeout",
            estimated_context_reduction="qualitative reduction from proof replacing repeated explanation",
            retry_reduction_potential="lower when idempotency and duplicate no-op are explicit",
            local_first_substitution="SQLite readback and JSON parse before any new model pass",
            meaningful_work_per_watt_note="Use the cheapest deterministic proof that answers the operator question.",
            guardrail="Do not turn efficiency into a moral score.",
            next_safe_move="Keep receipts and readbacks as the proof layer.",
        ),
    )


def _compute_commons_concept() -> OptInComputeCommonsConcept:
    return OptInComputeCommonsConcept(
        concept_id="opt_in_compute_commons_concept_v0",
        description=(
            "Future ships or devices may voluntarily offer bounded idle compute for mission-aligned workloads after explicit review."
        ),
        eligibility_policy=(
            "Candidate must be safe, described plainly, able to run without private local data, and reviewed before any execution design."
        ),
        consent_policy=(
            "Explicit opt-in required for the program and for workload class; operator can decline, pause, or stop."
        ),
        resource_boundary=(
            "Resource caps, thermal limits, battery limits, user-activity limits, disk limits, and network limits are mandatory before runtime exists."
        ),
        privacy_boundary=(
            "Default no access to private local data, credentials, cookies, tokens, private documents, or protected stores."
        ),
        workload_safety_policy=(
            "No hidden compute, mining, spam, fraud, surveillance, malware, or autonomy-sensitive work without strict refusal or review."
        ),
        mission_alignment_policy="Workload must have a clear operator-approved mission or public-good purpose.",
        operator_visibility="Operator must see what would run, why, under what caps, and how to stop it.",
        opt_in_status="DEFAULT_OFF_CONCEPT_ONLY",
        opt_out_policy="Operator can opt out or pause any future commons participation at any time.",
        audit_receipts_required=True,
        forbidden_uses=FORBIDDEN_COMPUTE_COMMONS_USES,
        non_goals=(
            "no live compute-sharing behavior",
            "no device enrollment",
            "no scheduler",
            "no background jobs",
            "no daemon",
            "no watcher",
            "no network workload",
        ),
        next_safe_move="Keep this as a scout contract until a future explicit design lane exists.",
    )


def _compute_commons_candidates() -> tuple[ComputeCommonsCandidate, ...]:
    return (
        ComputeCommonsCandidate(
            candidate_id="candidate_public_good_validation_batch",
            workload_summary="Idle local machine could help run a public-good test suite or validation batch.",
            mission_alignment_summary="Potentially useful if the workload is safe, transparent, and operator-approved.",
            resource_request_summary="Bounded local batch with explicit caps, no background daemon, and no private-data access.",
            privacy_class="sanitized_public_or_project_test_data_only",
            data_access_required="no private local data",
            can_run_without_private_data=True,
            operator_benefit="Can contribute useful validation without distracting from operator tasks, if opted in.",
            public_good_potential="possible after review",
            safety_review_required=True,
            consent_required=True,
            local_resource_caps=(
                "operator-approved time window",
                "thermal cap required",
                "battery and user-activity pause required",
                "disk and network caps required before runtime",
            ),
            eligibility_status="ELIGIBLE_FOR_OPERATOR_REVIEW",
            rejection_reasons=(),
            elioperator_prompt=(
                "This is eligible only for review. Nothing runs unless you explicitly opt in and approve the workload boundary."
            ),
            next_safe_move="Park as future review candidate; do not execute.",
        ),
        ComputeCommonsCandidate(
            candidate_id="candidate_unknown_external_gpu_file_access",
            workload_summary="Unknown external workload requests compute time and file access.",
            mission_alignment_summary="Unknown and not safely bounded.",
            resource_request_summary="Unbounded compute with file access requested.",
            privacy_class="unknown_fail_closed",
            data_access_required="private local file access requested",
            can_run_without_private_data=False,
            operator_benefit="not established",
            public_good_potential="unknown",
            safety_review_required=True,
            consent_required=True,
            local_resource_caps=(),
            eligibility_status="BLOCKED_PRIVACY_RISK",
            rejection_reasons=(
                "private local data access requested",
                "workload purpose unknown",
                "resource boundary missing",
                "safety review missing",
            ),
            elioperator_prompt="Blocked. Unknown external compute with file access is not eligible for commons review.",
            next_safe_move="Reject until workload, data boundary, and safety posture are explicit.",
        ),
        ComputeCommonsCandidate(
            candidate_id="candidate_opt_in_disabled_default",
            workload_summary="Any commons workload before operator opt-in exists.",
            mission_alignment_summary="Default-off policy blocks it.",
            resource_request_summary="No resource use allowed.",
            privacy_class="not_applicable_default_off",
            data_access_required="none allowed",
            can_run_without_private_data=False,
            operator_benefit="not available until opt-in",
            public_good_potential="not evaluated",
            safety_review_required=True,
            consent_required=True,
            local_resource_caps=(),
            eligibility_status="OPT_IN_DISABLED",
            rejection_reasons=("Compute Commons is concept-only and default off.",),
            elioperator_prompt="Nothing can run. Compute Commons is a future opt-in idea, not a live system.",
            next_safe_move="Do not build runtime behavior in this lane.",
        ),
    )


def _builder_blockers() -> tuple[MeaningfulWorkBuilderBlocker, ...]:
    return (
        MeaningfulWorkBuilderBlocker(
            blocker_id="blocker_moralizing_language",
            blocker_type="MORALIZING_LANGUAGE",
            condition="Builder text ranks or shames the operator instead of offering a bounded option.",
            severity="BLOCKS_SAFE_MIGRATION",
            elioperator_warning="ELIOPERATOR: This sounds like a judgment. Say the tradeoff plainly and leave the choice with the operator.",
            builder_action_required="Replace moral language with optional, task-first guidance.",
            fail_closed=True,
            next_safe_move="Keep the compass non-coercive.",
        ),
        MeaningfulWorkBuilderBlocker(
            blocker_id="blocker_hidden_scope_expansion",
            blocker_type="HIDDEN_SCOPE_EXPANSION",
            condition="The system starts a reusable rail, Build Cue write, runtime action, or commons work without explicit scope.",
            severity="BLOCKS_SAFE_MIGRATION",
            elioperator_warning="ELIOPERATOR: This expands the lane. Do not do it unless Winship asks.",
            builder_action_required="Finish the immediate task and park the optional path.",
            fail_closed=True,
            next_safe_move="Route to Work Terrain only as a candidate.",
        ),
        MeaningfulWorkBuilderBlocker(
            blocker_id="blocker_task_hijack",
            blocker_type="TASK_HIJACK",
            condition="Compounding work replaces the requested concrete task.",
            severity="BLOCKS_SAFE_MIGRATION",
            elioperator_warning="ELIOPERATOR: The direct task comes first. Do not turn the compass into a detour.",
            builder_action_required="Return to the direct task and preserve only cheap guardrails.",
            fail_closed=True,
            next_safe_move="Complete the immediate operator task.",
        ),
        MeaningfulWorkBuilderBlocker(
            blocker_id="blocker_visible_impact_score",
            blocker_type="VISIBLE_IMPACT_SCORE",
            condition="A UI or readback exposes a gamified impact score or moral ranking.",
            severity="BLOCKS_SAFE_MIGRATION",
            elioperator_warning=(
                "ELIOPERATOR: This turns the compass into a scoreboard. Use an internal signal and operator-readable option instead."
            ),
            builder_action_required="Remove score/ranking fields from visible surfaces.",
            fail_closed=True,
            next_safe_move="Use qualitative signal labels only.",
        ),
        MeaningfulWorkBuilderBlocker(
            blocker_id="blocker_fake_efficiency_claim",
            blocker_type="FAKE_EFFICIENCY_CLAIM",
            condition="The contract claims numeric energy or token savings without measurement.",
            severity="MUST_PATCH_BEFORE_MIGRATION",
            elioperator_warning="ELIOPERATOR: Do not invent savings. Say the efficiency posture is qualitative unless measured.",
            builder_action_required="Remove numeric claims or cite a measured receipt.",
            fail_closed=True,
            next_safe_move="Use qualitative work-per-watt language.",
        ),
        MeaningfulWorkBuilderBlocker(
            blocker_id="blocker_repeated_context_rediscovery",
            blocker_type="REPEATED_CONTEXT_REDISCOVERY",
            condition="A worker repeats broad scans after a generated read-model or receipt can answer the narrow question.",
            severity="SHOULD_PATCH",
            elioperator_warning="ELIOPERATOR: Use the proof layer before burning context again.",
            builder_action_required="Prefer generated read-models, manifests, and receipt refs.",
            fail_closed=False,
            next_safe_move="Route durable fix to Build Cue if repeated.",
        ),
        MeaningfulWorkBuilderBlocker(
            blocker_id="blocker_one_off_glue_where_registry_exists",
            blocker_type="ONE_OFF_GLUE_WHERE_REGISTRY_EXISTS",
            condition="A bespoke handoff package is repeated after post-office metadata exists.",
            severity="SHOULD_PATCH",
            elioperator_warning="ELIOPERATOR: Finish the current handoff, then park the registry-shaped version.",
            builder_action_required="Do not rewrite working rail; add future metadata alignment.",
            fail_closed=False,
            next_safe_move="Use compatibility audit before migration.",
        ),
        MeaningfulWorkBuilderBlocker(
            blocker_id="blocker_raw_pii_in_normal_readmodel",
            blocker_type="RAW_PII_IN_NORMAL_READMODEL",
            condition="Normal generated JSON or operator markdown includes raw protected material.",
            severity="BLOCKS_SAFE_MIGRATION",
            elioperator_warning="ELIOPERATOR: Protected values need token refs or protected evidence posture, not raw read-model text.",
            builder_action_required="Redact raw value and use tokenized/protected reference posture.",
            fail_closed=True,
            next_safe_move="Apply sensitive policy and rerun scans.",
        ),
        MeaningfulWorkBuilderBlocker(
            blocker_id="blocker_unbounded_compute_commons",
            blocker_type="UNBOUNDED_COMPUTE_COMMONS",
            condition="Commons workload lacks consent, visibility, resource caps, audit receipts, or safety review.",
            severity="BLOCKS_SAFE_MIGRATION",
            elioperator_warning="ELIOPERATOR: No hidden compute. Commons is opt-in, visible, capped, and stoppable or it does not exist.",
            builder_action_required="Keep candidate blocked until explicit policy exists.",
            fail_closed=True,
            next_safe_move="Do not create runtime or enrollment behavior.",
        ),
        MeaningfulWorkBuilderBlocker(
            blocker_id="blocker_opt_in_bypass",
            blocker_type="OPT_IN_BYPASS",
            condition="A workload runs or enrolls a device before explicit opt-in.",
            severity="BLOCKS_SAFE_MIGRATION",
            elioperator_warning="ELIOPERATOR: Consent is required. Default off means no work runs.",
            builder_action_required="Block execution and require operator consent design.",
            fail_closed=True,
            next_safe_move="Keep compute commons inactive.",
        ),
        MeaningfulWorkBuilderBlocker(
            blocker_id="blocker_harmful_workload",
            blocker_type="HARMFUL_WORKLOAD",
            condition="Workload asks for spam, fraud, surveillance, malware, mining, or unsafe autonomy-sensitive compute.",
            severity="BLOCKS_SAFE_MIGRATION",
            elioperator_warning="ELIOPERATOR: This workload is outside the safety boundary.",
            builder_action_required="Refuse and record no execution path.",
            fail_closed=True,
            next_safe_move="Do not route to commons.",
        ),
    )


def _model_schemas() -> dict[str, dict[str, Any]]:
    return {
        "meaningful_work_gravity_contract": {
            "model_name": "MeaningfulWorkGravityContract",
            "required_fields": list(REQUIRED_CONTRACT_FIELDS),
        },
        "meaningful_work_signal": {
            "model_name": "MeaningfulWorkSignal",
            "required_fields": list(REQUIRED_SIGNAL_FIELDS),
            "work_categories": list(WORK_CATEGORIES),
            "signal_types": list(MEANINGFUL_WORK_SIGNAL_TYPES),
        },
        "operator_sovereignty_guardrail": {
            "model_name": "OperatorSovereigntyGuardrail",
            "required_fields": list(REQUIRED_SOVEREIGNTY_FIELDS),
        },
        "anti_sludge_detection_policy": {
            "model_name": "AntiSludgeDetectionPolicy",
            "required_fields": list(REQUIRED_ANTI_SLUDGE_FIELDS),
        },
        "compounding_opportunity": {
            "model_name": "CompoundingOpportunity",
            "required_fields": list(REQUIRED_OPPORTUNITY_FIELDS),
            "recommended_handlings": list(RECOMMENDED_HANDLINGS),
        },
        "elioperator_nudge": {
            "model_name": "ELIOperatorNudge",
            "required_fields": list(REQUIRED_NUDGE_FIELDS),
        },
        "compute_efficiency_signal": {
            "model_name": "ComputeEfficiencySignal",
            "required_fields": list(REQUIRED_COMPUTE_EFFICIENCY_FIELDS),
        },
        "opt_in_compute_commons_concept": {
            "model_name": "OptInComputeCommonsConcept",
            "required_fields": list(REQUIRED_COMPUTE_COMMONS_CONCEPT_FIELDS),
        },
        "compute_commons_candidate": {
            "model_name": "ComputeCommonsCandidate",
            "required_fields": list(REQUIRED_COMPUTE_COMMONS_CANDIDATE_FIELDS),
            "eligibility_statuses": list(COMPUTE_COMMONS_ELIGIBILITY_STATUSES),
        },
        "meaningful_work_builder_blocker": {
            "model_name": "MeaningfulWorkBuilderBlocker",
            "required_fields": list(REQUIRED_BUILDER_BLOCKER_FIELDS),
            "blocker_types": list(BUILDER_BLOCKER_TYPES),
        },
    }


def build_meaningful_work_gravity_contract(*, generated_at: str | None = None) -> dict[str, Any]:
    contract = _gravity_contract()
    guardrail = _sovereignty_guardrail()
    anti_sludge = _anti_sludge_policy()
    signals = _signals()
    opportunities = _opportunities()
    nudges = _nudges()
    efficiency_signals = _compute_efficiency_signals()
    commons_concept = _compute_commons_concept()
    commons_candidates = _compute_commons_candidates()
    blockers = _builder_blockers()

    signals_by_id = {signal.signal_id: asdict(signal) for signal in signals}
    opportunities_by_id = {opportunity.opportunity_id: asdict(opportunity) for opportunity in opportunities}
    nudges_by_id = {nudge.nudge_id: asdict(nudge) for nudge in nudges}
    efficiency_by_id = {signal.signal_id: asdict(signal) for signal in efficiency_signals}
    candidates_by_id = {candidate.candidate_id: asdict(candidate) for candidate in commons_candidates}
    blockers_by_id = {blocker.blocker_id: asdict(blocker) for blocker in blockers}

    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "contract_status": CONTRACT_STATUS,
        "generated_at": generated_at or utc_now(),
        "purpose": (
            "Define Meaningful Work Gravity as a bounded compass and model a future opt-in Compute Commons scout."
        ),
        "work_categories": list(WORK_CATEGORIES),
        "meaningful_work_signal_types": list(MEANINGFUL_WORK_SIGNAL_TYPES),
        "recommended_handlings": list(RECOMMENDED_HANDLINGS),
        "compute_commons_eligibility_statuses": list(COMPUTE_COMMONS_ELIGIBILITY_STATUSES),
        "builder_blocker_types": list(BUILDER_BLOCKER_TYPES),
        "model_schemas": _model_schemas(),
        "gravity_contract": asdict(contract),
        "operator_sovereignty_guardrail": asdict(guardrail),
        "anti_sludge_detection_policy": asdict(anti_sludge),
        "meaningful_work_signals_by_id": signals_by_id,
        "compounding_opportunities_by_id": opportunities_by_id,
        "elioperator_nudges_by_id": nudges_by_id,
        "compute_efficiency_signals_by_id": efficiency_by_id,
        "opt_in_compute_commons_concept": asdict(commons_concept),
        "compute_commons_candidates_by_id": candidates_by_id,
        "builder_blockers_by_id": blockers_by_id,
        "examples": {
            "capital_hilton": {
                "signal_ref": "signal_capital_hilton_steel_thread",
                "opportunity_ref": "opportunity_capital_hilton_invoice_rails",
                "handling": "COMPLETE_AND_NOTE_BUILD_CUE",
                "summary": (
                    "Immediate invoice work produced capture/readback, post-office, reusable facts, and tokenization rails."
                ),
            },
            "low_stakes_one_off": {
                "signal_ref": "signal_low_stakes_one_off",
                "opportunity_ref": "opportunity_low_stakes_one_off",
                "handling": "COMPLETE_DIRECTLY_ONLY",
                "summary": "Small tasks may remain small; no moralizing and no extra rail.",
            },
            "handoff_churn": {
                "signal_ref": "signal_repeated_handoff_churn",
                "nudge_ref": "nudge_handoff_churn",
                "handling": "COMPLETE_AND_NOTE_BUILD_CUE",
                "summary": "Finish current handoff and park post-office metadata/registry candidate.",
            },
            "privacy_improvement": {
                "signal_ref": "signal_privacy_tokenization",
                "handling": "COMPLETE_AND_ADD_TINY_GUARDRAIL",
                "summary": "Tokenization is a safety rail; no live protected-store mutation in this contract.",
            },
            "compute_commons_candidate": {
                "candidate_ref": "candidate_public_good_validation_batch",
                "eligibility_status": "ELIGIBLE_FOR_OPERATOR_REVIEW",
                "summary": "Safe public-good validation may be reviewed later; opt-in and caps required.",
            },
            "blocked_compute_workload": {
                "candidate_ref": "candidate_unknown_external_gpu_file_access",
                "eligibility_status": "BLOCKED_PRIVACY_RISK",
                "summary": "Unknown external compute with file access is blocked.",
            },
            "agent_nudge": {
                "nudge_ref": "nudge_preserve_reusable_rail",
                "summary": "A future agent may note a reusable rail, but it must finish the immediate task first.",
            },
            "elioperator_warning": {
                "blocker_ref": "blocker_visible_impact_score",
                "nudge_ref": "nudge_visible_score_blocked",
                "summary": "Visible impact score is blocked; use qualitative signal language instead.",
            },
        },
        "relationship_inventory": _relationship_inventory(),
        "security_privacy_rules": {
            "no_raw_pii_in_generated_read_models": True,
            "no_raw_protected_values_in_operator_markdown": True,
            "no_raw_private_bodies": True,
            "credentials_tokens_cookies_private_keys_forbidden": True,
            "compute_commons_default_off": True,
            "tokenization_contract_referenced_not_invoked": True,
        },
        "authority_boundary": AUTHORITY_BOUNDARY,
    }

    payload["machine_proof"] = {
        "meaningful_work_gravity_contract_model_present": True,
        "meaningful_work_signal_model_present": True,
        "operator_sovereignty_guardrail_model_present": True,
        "anti_sludge_detection_policy_model_present": True,
        "compounding_opportunity_model_present": True,
        "elioperator_nudge_model_present": True,
        "compute_efficiency_signal_model_present": True,
        "opt_in_compute_commons_concept_model_present": True,
        "compute_commons_candidate_model_present": True,
        "meaningful_work_builder_blocker_model_present": True,
        "all_work_categories_present": set(WORK_CATEGORIES)
        == set(payload["model_schemas"]["meaningful_work_signal"]["work_categories"]),
        "operator_sovereignty_guardrails_present": (
            guardrail.immediate_task_first
            and guardrail.optional_expansion_only
            and guardrail.no_moralizing
            and guardrail.no_gamified_score
            and guardrail.no_task_hijack
        ),
        "anti_sludge_policy_present": bool(anti_sludge.sludge_patterns),
        "compounding_opportunity_examples_present": all(
            key in opportunities_by_id
            for key in (
                "opportunity_capital_hilton_invoice_rails",
                "opportunity_low_stakes_one_off",
                "opportunity_compute_commons_scout",
            )
        ),
        "elioperator_nudges_present": all(nudge.operator_text for nudge in nudges),
        "compute_efficiency_avoids_fake_numeric_claims": all(
            "qualitative" in signal.estimated_context_reduction
            or "qualitative" in signal.meaningful_work_per_watt_note
            for signal in efficiency_signals
        ),
        "compute_commons_default_off": commons_concept.opt_in_status == "DEFAULT_OFF_CONCEPT_ONLY",
        "compute_commons_opt_in_required": all(candidate.consent_required for candidate in commons_candidates),
        "compute_commons_forbidden_uses_present": set(FORBIDDEN_COMPUTE_COMMONS_USES).issubset(
            set(commons_concept.forbidden_uses)
        ),
        "builder_blockers_present": set(BUILDER_BLOCKER_TYPES).issubset(
            {blocker.blocker_type for blocker in blockers}
        ),
        "visible_score_gamification_blocked": "blocker_visible_impact_score" in blockers_by_id,
        "moralizing_language_blocked": "blocker_moralizing_language" in blockers_by_id,
        "hidden_scope_expansion_blocked": "blocker_hidden_scope_expansion" in blockers_by_id,
        "capital_hilton_example_present": "capital_hilton" in payload["examples"],
        "low_stakes_one_off_example_present": "low_stakes_one_off" in payload["examples"],
        "handoff_churn_example_present": "handoff_churn" in payload["examples"],
        "privacy_improvement_example_present": "privacy_improvement" in payload["examples"],
        "compute_commons_candidate_example_present": "compute_commons_candidate" in payload["examples"],
        "blocked_compute_workload_example_present": "blocked_compute_workload" in payload["examples"],
        "agent_nudge_example_present": "agent_nudge" in payload["examples"],
        "all_live_authority_flags_false": all(value is False for value in AUTHORITY_BOUNDARY.values()),
        "credentials_or_secrets_included": False,
        "raw_private_bodies_included": False,
        "raw_sensitive_fixture_values_included": False,
        "live_compute_commons_activation_added": False,
        "content_hash": None,
    }
    payload["machine_proof"]["content_hash"] = _content_hash(payload)
    return payload


def format_operator_markdown(payload: dict[str, Any]) -> str:
    contract = payload["gravity_contract"]
    guardrail = payload["operator_sovereignty_guardrail"]
    commons = payload["opt_in_compute_commons_concept"]
    proof = payload["machine_proof"]
    lines = [
        "# Meaningful Work Gravity Contract",
        "",
        "## ELIOPERATOR",
        "",
        (
            "Meaningful Work Gravity is a compass, not a judge. The immediate task still comes first. "
            "When a task reveals a cheap, safe reusable rail, OpenClaw can preserve or park it without hijacking the lane."
        ),
        "",
        "There is no visible score, no moral ranking, no shame language, and no hidden rerouting.",
        "",
        "## Doctrine",
        "",
    ]
    lines.extend(f"- {item}" for item in contract["doctrine"])
    lines.extend(
        [
            "",
            "## Operator Sovereignty",
            "",
            f"- Immediate task first: `{str(guardrail['immediate_task_first']).lower()}`",
            f"- Optional expansion only: `{str(guardrail['optional_expansion_only']).lower()}`",
            f"- No moralizing: `{str(guardrail['no_moralizing']).lower()}`",
            f"- No gamified score: `{str(guardrail['no_gamified_score']).lower()}`",
            f"- Operator override allowed: `{str(guardrail['operator_override_allowed']).lower()}`",
            "",
            "## Anti-Sludge",
            "",
            "- Repeated context rediscovery wastes attention.",
            "- Fake readback without state is not progress.",
            "- Repeated bespoke shuttle prompts should become a Build Cue when the current handoff is done.",
            "- Compute-saving work should not itself burn unnecessary compute.",
            "",
            "## Compute Commons",
            "",
            "Compute Commons is future opt-in only and default off. No device is enrolled, no idle compute is used, and no workload runs here.",
            "",
            f"- Opt-in status: `{commons['opt_in_status']}`",
            f"- Audit receipts required: `{str(commons['audit_receipts_required']).lower()}`",
            "- Consent, privacy boundaries, resource caps, safety review, and operator visibility are required before any future runtime design.",
            "",
            "## Forbidden Commons Uses",
            "",
        ]
    )
    lines.extend(f"- {item}" for item in commons["forbidden_uses"])
    lines.extend(
        [
            "",
            "## What This Does Not Do",
            "",
            "- No live meaningful-work scoring.",
            "- No task rerouting.",
            "- No scope expansion.",
            "- No Build Cue write.",
            "- No compute sharing.",
            "- No model, agent, tool, runtime, network, or external action.",
            "",
            "## Machine Proof",
            "",
            f"- All live authority flags false: `{str(proof['all_live_authority_flags_false']).lower()}`",
            f"- Compute Commons default off: `{str(proof['compute_commons_default_off']).lower()}`",
            f"- Visible score blocked: `{str(proof['visible_score_gamification_blocked']).lower()}`",
            f"- Moralizing language blocked: `{str(proof['moralizing_language_blocked']).lower()}`",
            f"- Hidden scope expansion blocked: `{str(proof['hidden_scope_expansion_blocked']).lower()}`",
            f"- Raw private bodies included: `{str(proof['raw_private_bodies_included']).lower()}`",
            f"- Content hash: `{proof['content_hash']}`",
            "",
            "## Next Safe Move",
            "",
            "Review this as a compass contract. Build Cue integration and Compute Commons remain future explicit lanes.",
            "",
        ]
    )
    return "\n".join(lines)


def write_exports(payload: dict[str, Any], export_root: Path) -> tuple[Path, Path]:
    export_root.mkdir(parents=True, exist_ok=True)
    json_path = export_root / JSON_EXPORT_NAME
    operator_path = export_root / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(format_operator_markdown(payload), encoding="utf-8")
    return json_path, operator_path


def build_summary(payload: dict[str, Any], json_path: Path | None, operator_path: Path | None) -> dict[str, Any]:
    return {
        "read_model_id": payload["read_model_id"],
        "schema_version": payload["schema_version"],
        "contract_status": payload["contract_status"],
        "json_path": str(json_path) if json_path else None,
        "operator_path": str(operator_path) if operator_path else None,
        "signal_count": len(payload["meaningful_work_signals_by_id"]),
        "compute_commons_candidate_count": len(payload["compute_commons_candidates_by_id"]),
        "all_live_authority_flags_false": payload["machine_proof"]["all_live_authority_flags_false"],
        "compute_commons_default_off": payload["machine_proof"]["compute_commons_default_off"],
        "content_hash": payload["machine_proof"]["content_hash"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT), help="Directory for generated read-models.")
    parser.add_argument("--format", choices=("summary", "json", "operator"), default="summary")
    parser.add_argument("--no-write", action="store_true", help="Build output without writing generated files.")
    args = parser.parse_args(argv)

    payload = build_meaningful_work_gravity_contract()
    json_path: Path | None = None
    operator_path: Path | None = None
    if not args.no_write:
        json_path, operator_path = write_exports(payload, Path(args.export_root))

    if args.format == "json":
        sys.stdout.write(stable_json(payload))
    elif args.format == "operator":
        sys.stdout.write(format_operator_markdown(payload))
    else:
        sys.stdout.write(stable_json(build_summary(payload, json_path, operator_path)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
