"""Operator Work Mode Schema / Bandwidth Policy v0.

This read-model defines app-wide work modes, operator bandwidth defaults,
issue classifications, helm declutter policy, and the boundary between
machine substrate and human solve paths. It is deterministic metadata only:
no Mission Control Swift changes, stable-map refresh, workflow execution,
operator input persistence, browser/account access, model/tool/agent/runtime
activation, invoice generation, email dispatch, ledger write, or authority
grant is created here.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from openclaw_substrate_utils import stable_json, utc_now


ROOT = Path(__file__).resolve().parent
DEFAULT_EXPORT_ROOT = Path("generated/read_models")

SCHEMA_VERSION = "operator_work_mode_schema_bandwidth_policy_v0"
READ_MODEL_ID = "operator_work_mode_schema_bandwidth_policy"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
OPERATOR_EXPORT_NAME = f"{READ_MODEL_ID}_OPERATOR.md"

CONTRACT_STATUS = "DETERMINISTIC_NON_EXECUTING_READ_MODEL_CONTRACT"
HELM_DEFAULT_BANDWIDTH_MODE = "LOW_BANDWIDTH"

BANDWIDTH_MODE_IDS = (
    "LOW_BANDWIDTH",
    "NORMAL_BANDWIDTH",
    "HIGH_BANDWIDTH",
    "DEBUG_MODE",
)

WORK_MODE_TYPE_IDS = (
    "PROOF_WORK_MODE",
    "DECISION_WORK_MODE",
    "ARTIFACT_WORK_MODE",
    "APPROVAL_WORK_MODE",
    "REPAIR_DIAGNOSTIC_WORK_MODE",
    "TERRAIN_RECONCILIATION_WORK_MODE",
    "DRAFT_COMMUNICATION_WORK_MODE",
    "AUTOMATION_CANDIDATE_WORK_MODE",
    "CREATIVE_PROJECT_WORK_MODE",
    "UNKNOWN_FAIL_CLOSED",
)

ISSUE_TYPES = (
    "FINANCE_WORKFLOW",
    "DEVELOPER_SYSTEM_REPAIR",
    "SECURITY_GUARDIAN_REVIEW",
    "PROOF_REFERENCE_COLLECTION",
    "CONCEPT_TERRAIN_RECONCILIATION",
    "CREATIVE_MUSIC_PROJECT",
    "CLIENT_PROJECT_DELIVERY",
    "COMMUNICATION_DRAFT_SEND_WORKFLOW",
    "AUTOMATION_CANDIDATE",
    "APP_HELM_OVERLOAD",
    "UNKNOWN_FAIL_CLOSED",
)

REQUIRED_BANDWIDTH_MODE_FIELDS = (
    "bandwidth_id",
    "display_name",
    "human_description",
    "default_for_helm",
    "visible_content_policy",
    "hidden_content_policy",
    "choice_complexity",
    "proof_detail_policy",
    "machine_contract_policy",
    "best_for_operator_state",
    "next_safe_move",
)

REQUIRED_WORK_MODE_TYPE_FIELDS = (
    "work_mode_type_id",
    "display_name",
    "human_purpose",
    "machine_purpose",
    "best_for_issue_types",
    "default_bandwidth_mode",
    "default_visible_sections",
    "default_hidden_sections",
    "allowed_operator_inputs",
    "blocked_actions",
    "completion_condition",
    "proof_depth_policy",
    "next_safe_move",
)

REQUIRED_ISSUE_CLASSIFICATION_FIELDS = (
    "issue_id",
    "display_name",
    "issue_type",
    "world",
    "lane",
    "actor",
    "source_refs",
    "machine_state_refs",
    "proof_refs",
    "blockers",
    "operator_needed_for",
    "recommended_work_modes",
    "primary_work_mode",
    "secondary_work_modes",
    "operator_bandwidth_default",
    "human_summary_required",
    "lm_translation_allowed",
    "authority_granted",
    "next_safe_move",
)

REQUIRED_WORK_MODE_INSTANCE_FIELDS = (
    "work_mode_instance_id",
    "display_title",
    "world",
    "lane",
    "issue_classification_ref",
    "primary_work_mode_type",
    "active_step_id",
    "operator_bandwidth_default",
    "low_bandwidth_summary",
    "normal_bandwidth_summary",
    "high_bandwidth_details",
    "debug_detail_refs",
    "one_next_human_move",
    "plain_language_choices",
    "steps",
    "visible_context",
    "hidden_context",
    "proof_drawer_refs",
    "operator_inputs_available",
    "operator_inputs_active",
    "automation_candidates",
    "approval_refs",
    "channel_projection_refs",
    "quieted_step_refs",
    "blocked_actions",
    "completion_condition",
    "reopen_condition",
    "next_safe_move",
)

AUTHORITY_BOUNDARY = {
    "workflow_execution_allowed": False,
    "operator_input_persistence_allowed": False,
    "automation_execution_allowed": False,
    "approval_submission_allowed": False,
    "invoice_generation_allowed": False,
    "email_send_allowed": False,
    "telegram_send_allowed": False,
    "browser_automation_allowed": False,
    "credential_handling_allowed": False,
    "live_model_calls_allowed": False,
    "auto_promotion_allowed": False,
    "unsupervised_browser_execution_allowed": False,
    "direct_credential_store_reads_allowed": False,
    "automatic_ledger_writes_allowed": False,
    "email_dispatch_without_operator_signature_allowed": False,
    "file_move_delete_cleanup_allowed": False,
    "model_call_allowed": False,
    "agent_activation_allowed": False,
    "tool_execution_allowed": False,
    "queue_execution_allowed": False,
    "runtime_dispatch_allowed": False,
    "network_operation_allowed": False,
    "mission_control_swift_change_allowed": False,
    "mac_sync_import_allowed": False,
    "stable_map_refresh_allowed": False,
    "git_push_pull_fetch_allowed": False,
    "raw_private_body_ingestion_allowed": False,
    "raw_body_ingestion_allowed": False,
    "hidden_memory_creation_allowed": False,
}

COMMON_BLOCKED_ACTIONS = (
    "workflow execution",
    "operator input persistence",
    "automation execution",
    "approval submission",
    "invoice generation",
    "email or Telegram send",
    "browser/account/Coupa/Gmail/calendar access",
    "credential handling",
    "model/tool/agent/runtime/queue execution",
    "ledger writes",
    "file move/delete/cleanup",
)


@dataclass(frozen=True)
class OperatorBandwidthMode:
    bandwidth_id: str
    display_name: str
    human_description: str
    default_for_helm: bool
    visible_content_policy: tuple[str, ...]
    hidden_content_policy: tuple[str, ...]
    choice_complexity: str
    proof_detail_policy: str
    machine_contract_policy: str
    best_for_operator_state: str
    next_safe_move: str


@dataclass(frozen=True)
class OperatorWorkModeType:
    work_mode_type_id: str
    display_name: str
    human_purpose: str
    machine_purpose: str
    best_for_issue_types: tuple[str, ...]
    default_bandwidth_mode: str
    default_visible_sections: tuple[str, ...]
    default_hidden_sections: tuple[str, ...]
    allowed_operator_inputs: tuple[str, ...]
    blocked_actions: tuple[str, ...]
    completion_condition: str
    proof_depth_policy: str
    next_safe_move: str
    progress_condition: str


@dataclass(frozen=True)
class OperatorWorkIssueClassification:
    issue_id: str
    display_name: str
    issue_type: str
    world: str
    lane: str
    actor: str
    source_refs: tuple[str, ...]
    machine_state_refs: tuple[str, ...]
    proof_refs: tuple[str, ...]
    blockers: tuple[str, ...]
    operator_needed_for: tuple[str, ...]
    recommended_work_modes: tuple[str, ...]
    primary_work_mode: str
    secondary_work_modes: tuple[str, ...]
    operator_bandwidth_default: str
    human_summary_required: bool
    lm_translation_allowed: bool
    authority_granted: bool
    next_safe_move: str


@dataclass(frozen=True)
class OperatorWorkModeInstance:
    work_mode_instance_id: str
    display_title: str
    world: str
    lane: str
    issue_classification_ref: str
    primary_work_mode_type: str
    active_step_id: str
    operator_bandwidth_default: str
    low_bandwidth_summary: str
    normal_bandwidth_summary: str
    high_bandwidth_details: tuple[str, ...]
    debug_detail_refs: tuple[str, ...]
    one_next_human_move: str
    plain_language_choices: tuple[str, ...]
    steps: tuple[dict[str, Any], ...]
    visible_context: dict[str, Any]
    hidden_context: dict[str, Any]
    proof_drawer_refs: tuple[str, ...]
    operator_inputs_available: tuple[str, ...]
    operator_inputs_active: bool
    automation_candidates: tuple[str, ...]
    approval_refs: tuple[str, ...]
    channel_projection_refs: tuple[str, ...]
    quieted_step_refs: tuple[str, ...]
    blocked_actions: tuple[str, ...]
    completion_condition: str
    reopen_condition: str
    next_safe_move: str
    secondary_work_mode_types: tuple[str, ...]
    current_action_status: str
    authority_granted: bool


@dataclass(frozen=True)
class OperatorHumanTranslationPolicy:
    translation_source: str
    deterministic_inputs_required: tuple[str, ...]
    lm_render_allowed: bool
    lm_render_role: str
    lm_render_output_status: str
    lm_can_decide_authority: bool
    lm_can_mark_proof_complete: bool
    lm_can_approve_action: bool
    lm_can_create_hidden_memory: bool
    receipt_required_before_display: bool
    next_safe_move: str
    deterministic_choice_source: str
    dynamic_hallucinated_buttons_allowed: bool


@dataclass(frozen=True)
class HelmDeclutterPolicy:
    helm_should_show: tuple[str, ...]
    helm_should_hide: tuple[str, ...]
    proof_should_live: str
    machine_contract_visibility: str
    operator_attention_rule: str
    focus_mode_entry_rule: str
    focus_mode_exit_rule: str
    quieting_rule: str
    reopen_rule: str


@dataclass(frozen=True)
class OperatorWorkModeStableMapExposurePolicy:
    stable_map_should_expose: tuple[str, ...]
    stable_map_should_not_expose: tuple[str, ...]
    mac_should_render: tuple[str, ...]
    mac_should_hide: tuple[str, ...]
    proof_detail_policy: str
    debug_detail_policy: str


@dataclass(frozen=True)
class WorkModeExportResult:
    schema_version: str
    json_path: str
    operator_path: str
    bandwidth_mode_count: int
    work_mode_type_count: int
    issue_classification_count: int
    work_mode_instance_count: int
    helm_default_bandwidth_mode: str
    action_authority_granted: bool


def _content_hash(payload: dict[str, Any]) -> str:
    clone = json.loads(stable_json(payload))
    clone.get("machine_proof", {}).pop("content_hash", None)
    return "sha256:" + hashlib.sha256(stable_json(clone).encode("utf-8")).hexdigest()


def _generated_at(value: str | None) -> str:
    return value or utc_now()


def _all_authority_flags_false() -> bool:
    return all(value is False for value in AUTHORITY_BOUNDARY.values())


def default_bandwidth_modes() -> tuple[OperatorBandwidthMode, ...]:
    return (
        OperatorBandwidthMode(
            bandwidth_id="LOW_BANDWIDTH",
            display_name="Low Bandwidth",
            human_description=(
                "Winship may be tired, overloaded, not in developer mode, or low on get-it-done energy."
            ),
            default_for_helm=True,
            visible_content_policy=(
                "show one next human move",
                "use plain language",
                "use short choices",
                "avoid dense panels",
            ),
            hidden_content_policy=(
                "hide proof and machine detail unless opened",
                "hide machine-contract terms by default",
                "collapse repeated proof rows",
            ),
            choice_complexity="one move with short obvious choices",
            proof_detail_policy="proof summary only; proof drawer one level down",
            machine_contract_policy="inspectable but not default app surface",
            best_for_operator_state="tired, overloaded, low context, not in developer mode",
            next_safe_move="Show the smallest truthful next human move.",
        ),
        OperatorBandwidthMode(
            bandwidth_id="NORMAL_BANDWIDTH",
            display_name="Normal Bandwidth",
            human_description="Winship can read a short explanation and choose the next step.",
            default_for_helm=False,
            visible_content_policy=(
                "short explanation",
                "why it matters",
                "next step",
                "available choices",
                "proof summary",
            ),
            hidden_content_policy=(
                "raw contracts and logs remain behind inspect",
                "debug fields stay collapsed",
            ),
            choice_complexity="several named choices with one recommendation",
            proof_detail_policy="proof summary visible; detailed refs one level down",
            machine_contract_policy="summarized as human state, inspectable on demand",
            best_for_operator_state="ordinary work mode with enough attention for context",
            next_safe_move="Show why this matters and the next safe step.",
        ),
        OperatorBandwidthMode(
            bandwidth_id="HIGH_BANDWIDTH",
            display_name="High Bandwidth",
            human_description="Winship is ready to inspect blockers, refs, gates, and workflow relationships.",
            default_for_helm=False,
            visible_content_policy=(
                "blockers",
                "proof refs",
                "receipt refs",
                "authority gates",
                "relationship to workflow",
            ),
            hidden_content_policy=("raw diagnostics stay debug-only unless needed",),
            choice_complexity="workflow-level choices with proof and blocker context",
            proof_detail_policy="proof refs and receipt refs may be visible",
            machine_contract_policy="contract names may appear as supporting context",
            best_for_operator_state="active review, audit, or planning with enough focus",
            next_safe_move="Show blockers and proof refs without granting action authority.",
        ),
        OperatorBandwidthMode(
            bandwidth_id="DEBUG_MODE",
            display_name="Debug Mode",
            human_description="Developer inspection mode for contracts, generated read-models, and diagnostics.",
            default_for_helm=False,
            visible_content_policy=(
                "contracts",
                "generated read-models",
                "raw status fields",
                "proof shelves",
                "developer diagnostics",
            ),
            hidden_content_policy=("nothing promoted to operator default just because debug can inspect it",),
            choice_complexity="developer diagnostic surface",
            proof_detail_policy="raw proof shelves and diagnostic refs allowed",
            machine_contract_policy="machine contracts visible by explicit debug choice only",
            best_for_operator_state="developer mode, contract audit, or diagnostic investigation",
            next_safe_move="Inspect substrate without letting debug mode become the helm default.",
        ),
    )


def default_work_mode_types() -> tuple[OperatorWorkModeType, ...]:
    return (
        OperatorWorkModeType(
            work_mode_type_id="PROOF_WORK_MODE",
            display_name="Proof Work Mode",
            human_purpose="Help Winship decide what is true, missing, or needs a protected proof ref.",
            machine_purpose="Coordinate proof refs, blockers, receipts, and quieting candidates without marking proof complete.",
            best_for_issue_types=("FINANCE_WORKFLOW", "PROOF_REFERENCE_COLLECTION"),
            default_bandwidth_mode="LOW_BANDWIDTH",
            default_visible_sections=("one proof question", "plain choices", "proof summary"),
            default_hidden_sections=("raw protected content", "proof shelves", "machine receipts", "contract internals"),
            allowed_operator_inputs=("pick_known_truth", "say_i_do_not_know", "point_to_proof_ref_later"),
            blocked_actions=("mark proof complete", "ingest raw private body", "generate invoice") + COMMON_BLOCKED_ACTIONS,
            completion_condition="Progress means proof status is classified; completion requires deterministic proof receipt later.",
            proof_depth_policy="show only proof summary by default; drawer has refs and receipts",
            next_safe_move="Ask the smallest true proof question.",
            progress_condition="A proof gap becomes known, parked, rejected, or ready for protected evidence path.",
        ),
        OperatorWorkModeType(
            work_mode_type_id="DECISION_WORK_MODE",
            display_name="Decision Work Mode",
            human_purpose="Help Winship choose the safe direction when a workflow needs judgment.",
            machine_purpose="Present deterministic options and blockers without deciding authority.",
            best_for_issue_types=("SECURITY_GUARDIAN_REVIEW", "APP_HELM_OVERLOAD", "UNKNOWN_FAIL_CLOSED"),
            default_bandwidth_mode="LOW_BANDWIDTH",
            default_visible_sections=("decision prompt", "recommended safe move", "plain choices"),
            default_hidden_sections=("raw contracts", "long proof chains", "diagnostic fields"),
            allowed_operator_inputs=("choose_option", "park", "needs_more_context", "fail_closed"),
            blocked_actions=("approve action", "submit action", "grant authority") + COMMON_BLOCKED_ACTIONS,
            completion_condition="Progress means the decision state is classified; action still requires later approval rails.",
            proof_depth_policy="show proof summary only when it explains the decision",
            next_safe_move="Show the decision and the safest non-executing choice.",
            progress_condition="A blocked decision becomes decided, parked, or routed to review.",
        ),
        OperatorWorkModeType(
            work_mode_type_id="ARTIFACT_WORK_MODE",
            display_name="Artifact Work Mode",
            human_purpose="Help Winship review or assemble an artifact path without creating protected output.",
            machine_purpose="Track artifact refs, inputs, and readiness while generation stays blocked.",
            best_for_issue_types=("FINANCE_WORKFLOW", "CLIENT_PROJECT_DELIVERY", "CREATIVE_MUSIC_PROJECT"),
            default_bandwidth_mode="NORMAL_BANDWIDTH",
            default_visible_sections=("artifact purpose", "missing inputs", "next review step"),
            default_hidden_sections=("raw source bodies", "full generated payloads", "machine JSON"),
            allowed_operator_inputs=("review_readiness", "label_missing_input", "park_artifact"),
            blocked_actions=("invoice/excel/pdf generation", "file rewrite", "submission") + COMMON_BLOCKED_ACTIONS,
            completion_condition="Progress means artifact readiness is classified; production happens only in later authorized lanes.",
            proof_depth_policy="show refs only when artifact readiness depends on proof",
            next_safe_move="Name the artifact and what is still missing.",
            progress_condition="Artifact state becomes ready-for-draft, missing-input, parked, or blocked.",
        ),
        OperatorWorkModeType(
            work_mode_type_id="APPROVAL_WORK_MODE",
            display_name="Approval Work Mode",
            human_purpose="Help Winship review an approval packet before any action can happen.",
            machine_purpose="Bind approval refs, blockers, and authority gates without submitting approval.",
            best_for_issue_types=("FINANCE_WORKFLOW", "SECURITY_GUARDIAN_REVIEW", "COMMUNICATION_DRAFT_SEND_WORKFLOW"),
            default_bandwidth_mode="LOW_BANDWIDTH",
            default_visible_sections=("approval question", "risk summary", "blocked actions"),
            default_hidden_sections=("raw payloads", "credentials", "full contract internals"),
            allowed_operator_inputs=("approve_later_candidate", "reject_candidate", "needs_review"),
            blocked_actions=("approval submission", "send/submit", "authority grant") + COMMON_BLOCKED_ACTIONS,
            completion_condition="Progress means approval need is classified; submission is still blocked.",
            proof_depth_policy="proof visible only as approval summary unless opened",
            next_safe_move="Show what would need approval and keep submission locked.",
            progress_condition="Approval state becomes blocked, needs-review, rejected, or future-ready.",
        ),
        OperatorWorkModeType(
            work_mode_type_id="REPAIR_DIAGNOSTIC_WORK_MODE",
            display_name="Repair Diagnostic Work Mode",
            human_purpose="Help Winship see what is actually broken before repair work starts.",
            machine_purpose="Show diagnostic evidence, health state, and next safe check without running repairs.",
            best_for_issue_types=("DEVELOPER_SYSTEM_REPAIR", "APP_HELM_OVERLOAD"),
            default_bandwidth_mode="NORMAL_BANDWIDTH",
            default_visible_sections=("symptom", "actual blocker", "next safe check"),
            default_hidden_sections=("raw logs", "stack traces", "generated diagnostics", "contract internals"),
            allowed_operator_inputs=("confirm_symptom", "park", "request_repair_lane_later"),
            blocked_actions=("repair execution", "runtime dispatch", "tool execution") + COMMON_BLOCKED_ACTIONS,
            completion_condition="Progress means the broken/not-broken state is classified with evidence.",
            proof_depth_policy="diagnostic proof is visible at high bandwidth or in drawer",
            next_safe_move="Check the evidence before attempting repair.",
            progress_condition="Diagnostic state becomes known, false alarm, parked, or ready for a future repair lane.",
        ),
        OperatorWorkModeType(
            work_mode_type_id="TERRAIN_RECONCILIATION_WORK_MODE",
            display_name="Terrain Reconciliation Work Mode",
            human_purpose="Help Winship sort current, stale, duplicate, overlapping, and source-gap terrain.",
            machine_purpose="Coordinate terrain refs and reconciliation candidates without rewriting files or memory.",
            best_for_issue_types=("CONCEPT_TERRAIN_RECONCILIATION", "APP_HELM_OVERLOAD"),
            default_bandwidth_mode="NORMAL_BANDWIDTH",
            default_visible_sections=("terrain question", "candidate status", "next reconciliation choice"),
            default_hidden_sections=("raw notes", "broad body excerpts", "machine classifier detail"),
            allowed_operator_inputs=("mark_current_candidate", "mark_stale_candidate", "needs_source", "park"),
            blocked_actions=("archive", "rewrite", "delete", "auto-stable-map promotion") + COMMON_BLOCKED_ACTIONS,
            completion_condition="Progress means terrain item is classified; source mutation remains blocked.",
            proof_depth_policy="show source labels; deeper refs stay inspectable",
            next_safe_move="Review what should stay current.",
            progress_condition="Terrain item becomes current, stale, overlap, source-gap, or parked candidate.",
        ),
        OperatorWorkModeType(
            work_mode_type_id="DRAFT_COMMUNICATION_WORK_MODE",
            display_name="Draft Communication Work Mode",
            human_purpose="Help Winship review a communication before any send path exists.",
            machine_purpose="Track draft status, review blockers, and later approval refs without dispatch.",
            best_for_issue_types=("COMMUNICATION_DRAFT_SEND_WORKFLOW", "CLIENT_PROJECT_DELIVERY"),
            default_bandwidth_mode="LOW_BANDWIDTH",
            default_visible_sections=("draft purpose", "review prompt", "send blocked label"),
            default_hidden_sections=("raw email bodies", "recipient payloads", "dispatch internals"),
            allowed_operator_inputs=("review_draft_candidate", "request_revision_later", "park"),
            blocked_actions=("email send", "Telegram send", "email dispatch without operator signature") + COMMON_BLOCKED_ACTIONS,
            completion_condition="Progress means the draft is reviewed or routed; dispatch remains blocked.",
            proof_depth_policy="show source/ref summary only; private bodies stay hidden",
            next_safe_move="Review the draft before anything sends.",
            progress_condition="Draft becomes reviewed, revision-needed, rejected, parked, or approval-needed.",
        ),
        OperatorWorkModeType(
            work_mode_type_id="AUTOMATION_CANDIDATE_WORK_MODE",
            display_name="Automation Candidate Work Mode",
            human_purpose="Help Winship see whether a repeated task might later be automated safely.",
            machine_purpose="Classify feasibility, gates, receipts, and blocked authority without running automation.",
            best_for_issue_types=("AUTOMATION_CANDIDATE", "FINANCE_WORKFLOW"),
            default_bandwidth_mode="NORMAL_BANDWIDTH",
            default_visible_sections=("automation goal", "current manual fallback", "blocked gates"),
            default_hidden_sections=("portal details", "credentials", "raw logs", "execution contracts"),
            allowed_operator_inputs=("keep_manual", "evaluate_later", "needs_security_delta", "reject"),
            blocked_actions=("automation execution", "browser automation", "credential handling") + COMMON_BLOCKED_ACTIONS,
            completion_condition="Progress means feasibility is classified; execution remains blocked.",
            proof_depth_policy="show feasibility refs; protected details stay in proof drawer",
            next_safe_move="Classify feasibility without running it.",
            progress_condition="Automation candidate becomes manual-only, future-gated, rejected, or security-review-needed.",
        ),
        OperatorWorkModeType(
            work_mode_type_id="CREATIVE_PROJECT_WORK_MODE",
            display_name="Creative Project Work Mode",
            human_purpose="Help Winship resume creative or client work without losing context.",
            machine_purpose="Summarize project state, next thread, and refs without publishing or sending.",
            best_for_issue_types=("CREATIVE_MUSIC_PROJECT", "CLIENT_PROJECT_DELIVERY"),
            default_bandwidth_mode="LOW_BANDWIDTH",
            default_visible_sections=("where you left off", "one next creative move", "context summary"),
            default_hidden_sections=("raw project files", "long proof shelves", "machine routing detail"),
            allowed_operator_inputs=("pick_up_thread", "park", "mark_context_gap"),
            blocked_actions=("publish", "send", "external account access", "file rewrite") + COMMON_BLOCKED_ACTIONS,
            completion_condition="Progress means the next creative thread is selected or parked.",
            proof_depth_policy="proof appears only when creative/client state depends on source refs",
            next_safe_move="Pick up where you left off.",
            progress_condition="Project lane becomes resumed, parked, source-needed, or ready for a future artifact lane.",
        ),
        OperatorWorkModeType(
            work_mode_type_id="UNKNOWN_FAIL_CLOSED",
            display_name="Unknown / Fail Closed",
            human_purpose="Keep unclear work from becoming a noisy or unsafe action.",
            machine_purpose="Contain unknown issue shape until deterministic classification exists.",
            best_for_issue_types=("UNKNOWN_FAIL_CLOSED",),
            default_bandwidth_mode="LOW_BANDWIDTH",
            default_visible_sections=("unknown state", "blocked label", "safe next check"),
            default_hidden_sections=("untrusted raw input", "unclassified machine detail"),
            allowed_operator_inputs=("park", "request_classification", "fail_closed"),
            blocked_actions=COMMON_BLOCKED_ACTIONS,
            completion_condition="Progress means the issue is classified or remains fail-closed.",
            proof_depth_policy="no proof claims until deterministic refs exist",
            next_safe_move="Fail closed and ask for classification.",
            progress_condition="Unknown item becomes classified or remains blocked.",
        ),
    )


def _issue(
    issue_id: str,
    *,
    display_name: str,
    issue_type: str,
    world: str,
    lane: str,
    actor: str,
    source_refs: tuple[str, ...],
    machine_state_refs: tuple[str, ...],
    proof_refs: tuple[str, ...],
    blockers: tuple[str, ...],
    operator_needed_for: tuple[str, ...],
    recommended_work_modes: tuple[str, ...],
    primary_work_mode: str,
    secondary_work_modes: tuple[str, ...] = (),
    operator_bandwidth_default: str = "LOW_BANDWIDTH",
    human_summary_required: bool = True,
    lm_translation_allowed: bool = True,
    authority_granted: bool = False,
    next_safe_move: str = "Show the next safe non-executing move.",
) -> OperatorWorkIssueClassification:
    return OperatorWorkIssueClassification(
        issue_id=issue_id,
        display_name=display_name,
        issue_type=issue_type,
        world=world,
        lane=lane,
        actor=actor,
        source_refs=source_refs,
        machine_state_refs=machine_state_refs,
        proof_refs=proof_refs,
        blockers=blockers,
        operator_needed_for=operator_needed_for,
        recommended_work_modes=recommended_work_modes,
        primary_work_mode=primary_work_mode,
        secondary_work_modes=secondary_work_modes,
        operator_bandwidth_default=operator_bandwidth_default,
        human_summary_required=human_summary_required,
        lm_translation_allowed=lm_translation_allowed,
        authority_granted=authority_granted,
        next_safe_move=next_safe_move,
    )


def default_issue_classifications() -> tuple[OperatorWorkIssueClassification, ...]:
    return (
        _issue(
            "capital_hilton_invoice_issue",
            display_name="Capital Hilton Invoice Proof Issue",
            issue_type="FINANCE_WORKFLOW",
            world="Finance",
            lane="capital_hilton",
            actor="Cassandra",
            source_refs=("Capital Hilton proof intake/resolution rails",),
            machine_state_refs=(
                "generated/read_models/capital_hilton_protected_proof_intake.json",
                "generated/read_models/capital_hilton_proof_resolution_batch_manifest.json",
                "generated/read_models/capital_hilton_proof_quieting_progress_state.json",
            ),
            proof_refs=("protected finance proof metadata refs only",),
            blockers=("missing proof", "protected proof required", "current action locked"),
            operator_needed_for=("classify invoice truth", "point to proof later", "decide what is unknown"),
            recommended_work_modes=(
                "PROOF_WORK_MODE",
                "ARTIFACT_WORK_MODE",
                "APPROVAL_WORK_MODE",
                "AUTOMATION_CANDIDATE_WORK_MODE",
            ),
            primary_work_mode="PROOF_WORK_MODE",
            secondary_work_modes=("ARTIFACT_WORK_MODE", "APPROVAL_WORK_MODE", "AUTOMATION_CANDIDATE_WORK_MODE"),
            next_safe_move="Pick what is true about the invoice.",
        ),
        _issue(
            "developer_system_repair_issue",
            display_name="Developer/System Repair Issue",
            issue_type="DEVELOPER_SYSTEM_REPAIR",
            world="System",
            lane="check_engine",
            actor="Chief",
            source_refs=("Chief Test Harness / Cross-Off", "Check Engine diagnostic package"),
            machine_state_refs=(
                "generated/read_models/chief_check_engine_diagnostic_package.json",
                "generated/read_models/chief_test_harness_cross_off_receipt_contract.json",
            ),
            proof_refs=("diagnostic receipt refs",),
            blockers=("repair execution blocked", "runtime/tool execution blocked"),
            operator_needed_for=("confirm what is broken", "choose repair lane later"),
            recommended_work_modes=("REPAIR_DIAGNOSTIC_WORK_MODE", "PROOF_WORK_MODE"),
            primary_work_mode="REPAIR_DIAGNOSTIC_WORK_MODE",
            secondary_work_modes=("PROOF_WORK_MODE",),
            operator_bandwidth_default="NORMAL_BANDWIDTH",
            next_safe_move="Check what is actually broken.",
        ),
        _issue(
            "security_delta_review_issue",
            display_name="Security / Guardian Review Issue",
            issue_type="SECURITY_GUARDIAN_REVIEW",
            world="System",
            lane="security_delta",
            actor="Guardian",
            source_refs=("Security Pass", "Security Delta Review"),
            machine_state_refs=(
                "generated/read_models/security_pass_contract.json",
                "generated/read_models/security_delta_review_contract.json",
            ),
            proof_refs=("security pass summary refs",),
            blockers=("new authority fails closed", "approval submission blocked"),
            operator_needed_for=("decide if security review is needed", "keep new authority blocked"),
            recommended_work_modes=("DECISION_WORK_MODE", "APPROVAL_WORK_MODE"),
            primary_work_mode="DECISION_WORK_MODE",
            secondary_work_modes=("APPROVAL_WORK_MODE",),
            next_safe_move="Decide if this needs security review.",
        ),
        _issue(
            "proof_reference_collection_issue",
            display_name="Proof / Reference Collection Issue",
            issue_type="PROOF_REFERENCE_COLLECTION",
            world="Proof",
            lane="reference_collection",
            actor="Guardian",
            source_refs=("protected evidence reference receipts",),
            machine_state_refs=("generated/read_models/protected_evidence_reference_receipt.json",),
            proof_refs=("proof drawer refs",),
            blockers=("raw protected content hidden", "proof completion blocked"),
            operator_needed_for=("point to source", "classify missing proof"),
            recommended_work_modes=("PROOF_WORK_MODE",),
            primary_work_mode="PROOF_WORK_MODE",
            next_safe_move="Point to the safest proof reference label.",
        ),
        _issue(
            "terrain_reconciliation_issue",
            display_name="Concept / Terrain Reconciliation Issue",
            issue_type="CONCEPT_TERRAIN_RECONCILIATION",
            world="System",
            lane="work_terrain",
            actor="Chief",
            source_refs=("Work Terrain reconciliation",),
            machine_state_refs=(
                "generated/read_models/openclaw_work_terrain_gap_detector.json",
                "generated/read_models/openclaw_work_terrain_reconciliation_batch_manifest.json",
            ),
            proof_refs=("terrain source refs",),
            blockers=("source mutation blocked", "stable-map refresh deferred"),
            operator_needed_for=("decide current/stale/overlap/source gap",),
            recommended_work_modes=("TERRAIN_RECONCILIATION_WORK_MODE", "DECISION_WORK_MODE"),
            primary_work_mode="TERRAIN_RECONCILIATION_WORK_MODE",
            secondary_work_modes=("DECISION_WORK_MODE",),
            operator_bandwidth_default="NORMAL_BANDWIDTH",
            next_safe_move="Review what should stay current.",
        ),
        _issue(
            "creative_music_project_issue",
            display_name="Creative / Music Project Issue",
            issue_type="CREATIVE_MUSIC_PROJECT",
            world="Creative",
            lane="niles_struna",
            actor="Niles",
            source_refs=("Niles / Struna project capsules",),
            machine_state_refs=(
                "generated/read_models/struna_obscura_project_capsule_OPERATOR.md",
                "generated/read_models/niles_album_review_packet.json",
            ),
            proof_refs=("project context refs",),
            blockers=("external publish/send blocked", "file rewrite blocked"),
            operator_needed_for=("resume the right creative thread", "mark context gap"),
            recommended_work_modes=("CREATIVE_PROJECT_WORK_MODE", "ARTIFACT_WORK_MODE"),
            primary_work_mode="CREATIVE_PROJECT_WORK_MODE",
            secondary_work_modes=("ARTIFACT_WORK_MODE",),
            next_safe_move="Pick up where you left off.",
        ),
        _issue(
            "client_project_delivery_issue",
            display_name="Client / Project Delivery Issue",
            issue_type="CLIENT_PROJECT_DELIVERY",
            world="Delivery",
            lane="client_project_delivery",
            actor="Cassandra",
            source_refs=("project delivery refs",),
            machine_state_refs=("generated/read_models/project_capsules.json",),
            proof_refs=("client/project receipt refs",),
            blockers=("send/submit blocked", "artifact generation blocked"),
            operator_needed_for=("choose next deliverable state", "review proof or draft later"),
            recommended_work_modes=("ARTIFACT_WORK_MODE", "DRAFT_COMMUNICATION_WORK_MODE"),
            primary_work_mode="ARTIFACT_WORK_MODE",
            secondary_work_modes=("DRAFT_COMMUNICATION_WORK_MODE",),
            operator_bandwidth_default="NORMAL_BANDWIDTH",
            next_safe_move="Name the deliverable and the next review step.",
        ),
        _issue(
            "communication_draft_send_issue",
            display_name="Communication Draft / Send Workflow Issue",
            issue_type="COMMUNICATION_DRAFT_SEND_WORKFLOW",
            world="Communications",
            lane="cassandra_clara",
            actor="Cassandra",
            source_refs=("Cassandra / Clara draft review packet",),
            machine_state_refs=("generated/read_models/cassandra_draft_review_packet.json",),
            proof_refs=("draft source refs only",),
            blockers=("email dispatch blocked", "approval submission blocked", "raw private bodies hidden"),
            operator_needed_for=("review draft", "decide if send path should remain blocked"),
            recommended_work_modes=("DRAFT_COMMUNICATION_WORK_MODE", "APPROVAL_WORK_MODE"),
            primary_work_mode="DRAFT_COMMUNICATION_WORK_MODE",
            secondary_work_modes=("APPROVAL_WORK_MODE",),
            next_safe_move="Review the draft before anything sends.",
        ),
        _issue(
            "automation_candidate_issue",
            display_name="Automation Candidate Issue",
            issue_type="AUTOMATION_CANDIDATE",
            world="System",
            lane="automation_candidate",
            actor="Chief",
            source_refs=("Coupa/PO automation candidate", "Tool Adapter Receipt"),
            machine_state_refs=(
                "generated/read_models/capital_hilton_coupa_po_retrieval_automation_candidate.json",
                "generated/read_models/tool_adapter_receipt_contract.json",
            ),
            proof_refs=("automation readiness refs",),
            blockers=("automation execution blocked", "security delta required for new authority"),
            operator_needed_for=("decide manual/future-gated/reject",),
            recommended_work_modes=("AUTOMATION_CANDIDATE_WORK_MODE", "DECISION_WORK_MODE"),
            primary_work_mode="AUTOMATION_CANDIDATE_WORK_MODE",
            secondary_work_modes=("DECISION_WORK_MODE",),
            operator_bandwidth_default="NORMAL_BANDWIDTH",
            next_safe_move="Classify feasibility without running it.",
        ),
        _issue(
            "app_helm_overload_issue",
            display_name="App Helm Overload Issue",
            issue_type="APP_HELM_OVERLOAD",
            world="Mission Control",
            lane="helm_declutter",
            actor="Chief",
            source_refs=("Operator Attention Promotion", "Operator Mission Priority / Helm Declutter"),
            machine_state_refs=(
                "generated/read_models/operator_attention_promotion_contract.json",
                "generated/read_models/operator_mission_priority_helm_declutter.json",
            ),
            proof_refs=("helm declutter proof/detail refs",),
            blockers=("machine contracts too visible", "stable-map refresh deferred"),
            operator_needed_for=("choose focus", "ignore proof noise until needed"),
            recommended_work_modes=("DECISION_WORK_MODE", "REPAIR_DIAGNOSTIC_WORK_MODE"),
            primary_work_mode="DECISION_WORK_MODE",
            secondary_work_modes=("REPAIR_DIAGNOSTIC_WORK_MODE",),
            next_safe_move="Show one next human move, not a contract wall.",
        ),
        _issue(
            "unknown_fail_closed_issue",
            display_name="Unknown Fail Closed Issue",
            issue_type="UNKNOWN_FAIL_CLOSED",
            world="Unknown",
            lane="unknown",
            actor="none",
            source_refs=("unclassified input",),
            machine_state_refs=(),
            proof_refs=(),
            blockers=("issue shape unknown", "authority blocked"),
            operator_needed_for=("classify or park",),
            recommended_work_modes=("UNKNOWN_FAIL_CLOSED",),
            primary_work_mode="UNKNOWN_FAIL_CLOSED",
            lm_translation_allowed=False,
            next_safe_move="Fail closed until classified.",
        ),
    )


def _step(step_id: str, title: str, status: str = "AVAILABLE_LOCKED") -> dict[str, Any]:
    return {
        "step_id": step_id,
        "title": title,
        "status": status,
        "operator_input_active": False,
        "executes": False,
        "quieted": False,
    }


def default_work_mode_instances() -> tuple[OperatorWorkModeInstance, ...]:
    return (
        OperatorWorkModeInstance(
            work_mode_instance_id="capital_hilton_invoice_work_mode",
            display_title="Capital Hilton Invoice Proof Work Mode",
            world="Finance",
            lane="capital_hilton",
            issue_classification_ref="capital_hilton_invoice_issue",
            primary_work_mode_type="PROOF_WORK_MODE",
            active_step_id="pick_invoice_truth",
            operator_bandwidth_default="LOW_BANDWIDTH",
            low_bandwidth_summary="Pick what is true about the invoice.",
            normal_bandwidth_summary="Capital Hilton needs a human-usable proof path. The current action is locked until proof and approval rails exist.",
            high_bandwidth_details=(
                "Finance workflow issue",
                "Proof refs remain protected and one level down",
                "Artifact, approval, and automation candidate modes are secondary only",
            ),
            debug_detail_refs=(
                "generated/read_models/capital_hilton_proof_resolution_batch_manifest.json",
                "generated/read_models/capital_hilton_proof_quieting_progress_state.json",
                "generated/read_models/capital_hilton_coupa_po_retrieval_automation_candidate.json",
            ),
            one_next_human_move="Pick what is true about the invoice.",
            plain_language_choices=("It is true and I know why", "I need to find proof", "I do not know yet"),
            steps=(
                _step("pick_invoice_truth", "Pick what is true about the invoice."),
                _step("point_to_proof_ref_later", "Point to protected proof later."),
                _step("keep_action_locked", "Keep invoice action locked.", "LOCKED"),
            ),
            visible_context={
                "purpose": "make invoice proof path human-usable",
                "current_action": "locked",
                "simple_default": True,
            },
            hidden_context={
                "machine_contracts": (
                    "capital_hilton_protected_proof_intake",
                    "capital_hilton_proof_quieting_progress_state",
                    "capital_hilton_coupa_po_retrieval_automation_candidate",
                ),
                "raw_private_bodies": "hidden",
            },
            proof_drawer_refs=(
                "generated/read_models/capital_hilton_protected_proof_intake.json",
                "generated/read_models/capital_hilton_proof_quieting_progress_state.json",
            ),
            operator_inputs_available=("choose_truth_state", "park", "needs_proof"),
            operator_inputs_active=False,
            automation_candidates=("capital_hilton_coupa_po_retrieval_automation_candidate",),
            approval_refs=("capital_hilton_send_approval_gate",),
            channel_projection_refs=(),
            quieted_step_refs=(),
            blocked_actions=("invoice_generation", "approval_submission", "Coupa/browser access") + COMMON_BLOCKED_ACTIONS,
            completion_condition="Classify invoice truth or proof gap; proof completion and actions remain locked.",
            reopen_condition="Reopen when proof status changes, approval path appears, or operator asks to inspect.",
            next_safe_move="Show the invoice truth choice without executing anything.",
            secondary_work_mode_types=("ARTIFACT_WORK_MODE", "APPROVAL_WORK_MODE", "AUTOMATION_CANDIDATE_WORK_MODE"),
            current_action_status="LOCKED",
            authority_granted=False,
        ),
        OperatorWorkModeInstance(
            work_mode_instance_id="chief_terrain_reconciliation_work_mode",
            display_title="Chief Terrain Reconciliation Work Mode",
            world="System",
            lane="work_terrain",
            issue_classification_ref="terrain_reconciliation_issue",
            primary_work_mode_type="TERRAIN_RECONCILIATION_WORK_MODE",
            active_step_id="review_currentness",
            operator_bandwidth_default="NORMAL_BANDWIDTH",
            low_bandwidth_summary="Review what should stay current.",
            normal_bandwidth_summary="Sort terrain into current, stale, overlap, or source-gap without rewriting files.",
            high_bandwidth_details=("Work Terrain refs", "gap detector refs", "stable-map visibility gaps"),
            debug_detail_refs=(
                "generated/read_models/openclaw_work_terrain_gap_detector.json",
                "generated/read_models/openclaw_work_terrain_reconciliation_batch_manifest.json",
            ),
            one_next_human_move="Review what should stay current.",
            plain_language_choices=("Keep current", "Looks stale", "Overlaps something else", "Needs source"),
            steps=(
                _step("review_currentness", "Review current/stale/overlap/source gap."),
                _step("keep_source_locked", "Keep source files untouched.", "LOCKED"),
            ),
            visible_context={"purpose": "find current/stale/overlap/source gaps"},
            hidden_context={"machine_contracts": ("openclaw_work_terrain_gap_detector",)},
            proof_drawer_refs=("generated/read_models/openclaw_work_terrain_gap_detector.json",),
            operator_inputs_available=("classify_currentness", "park", "needs_source"),
            operator_inputs_active=False,
            automation_candidates=(),
            approval_refs=(),
            channel_projection_refs=(),
            quieted_step_refs=(),
            blocked_actions=("file_move", "file_delete", "source_rewrite", "stable_map_refresh") + COMMON_BLOCKED_ACTIONS,
            completion_condition="Classify terrain item; mutation and stable-map refresh remain blocked.",
            reopen_condition="Reopen when new source refs, overlap, or stale evidence appears.",
            next_safe_move="Show the terrain status choice only.",
            secondary_work_mode_types=("DECISION_WORK_MODE",),
            current_action_status="LOCKED",
            authority_granted=False,
        ),
        OperatorWorkModeInstance(
            work_mode_instance_id="check_engine_diagnostic_work_mode",
            display_title="Check Engine Diagnostic Work Mode",
            world="System",
            lane="check_engine",
            issue_classification_ref="developer_system_repair_issue",
            primary_work_mode_type="REPAIR_DIAGNOSTIC_WORK_MODE",
            active_step_id="check_actual_breakage",
            operator_bandwidth_default="NORMAL_BANDWIDTH",
            low_bandwidth_summary="Check what is actually broken.",
            normal_bandwidth_summary="Show diagnostic evidence and the next safe check before any repair path exists.",
            high_bandwidth_details=("diagnostic evidence", "test harness refs", "cross-off remains candidate only"),
            debug_detail_refs=(
                "generated/read_models/chief_check_engine_diagnostic_package.json",
                "generated/read_models/chief_test_harness_cross_off_receipt_contract.json",
            ),
            one_next_human_move="Check what is actually broken.",
            plain_language_choices=("This is broken", "This is only noisy", "Needs another check"),
            steps=(
                _step("check_actual_breakage", "Check evidence before repair."),
                _step("keep_repair_locked", "Keep repair execution locked.", "LOCKED"),
            ),
            visible_context={"purpose": "show diagnostic evidence and next safe check"},
            hidden_context={"diagnostic_detail": "debug drawer only"},
            proof_drawer_refs=("generated/read_models/chief_check_engine_diagnostic_package.json",),
            operator_inputs_available=("confirm_broken", "false_alarm", "needs_more_evidence"),
            operator_inputs_active=False,
            automation_candidates=(),
            approval_refs=(),
            channel_projection_refs=(),
            quieted_step_refs=(),
            blocked_actions=("repair_execution", "runtime_dispatch", "tool_execution") + COMMON_BLOCKED_ACTIONS,
            completion_condition="Diagnostic status is classified; repair remains a future authorized lane.",
            reopen_condition="Reopen when health state changes or a new diagnostic ref appears.",
            next_safe_move="Show the evidence summary, not a repair button.",
            secondary_work_mode_types=("PROOF_WORK_MODE",),
            current_action_status="LOCKED",
            authority_granted=False,
        ),
        OperatorWorkModeInstance(
            work_mode_instance_id="security_delta_review_work_mode",
            display_title="Security Delta Review Work Mode",
            world="System",
            lane="security_delta",
            issue_classification_ref="security_delta_review_issue",
            primary_work_mode_type="DECISION_WORK_MODE",
            active_step_id="decide_security_review_needed",
            operator_bandwidth_default="LOW_BANDWIDTH",
            low_bandwidth_summary="Decide if this needs security review.",
            normal_bandwidth_summary="Classify whether new authority needs Security Delta or repass. Authority remains blocked.",
            high_bandwidth_details=("security pass refs", "delta classes", "Guardian gates", "approval remains blocked"),
            debug_detail_refs=(
                "generated/read_models/security_pass_contract.json",
                "generated/read_models/security_delta_review_contract.json",
            ),
            one_next_human_move="Decide if this needs security review.",
            plain_language_choices=("Needs security review", "No new authority", "Fail closed"),
            steps=(
                _step("decide_security_review_needed", "Classify security review need."),
                _step("keep_authority_blocked", "Keep authority blocked.", "LOCKED"),
            ),
            visible_context={"purpose": "classify whether new authority needs security delta/repass"},
            hidden_context={"machine_contracts": ("security_pass_contract", "security_delta_review_contract")},
            proof_drawer_refs=("generated/read_models/security_pass_contract.json",),
            operator_inputs_available=("needs_security_review", "no_delta_required", "fail_closed"),
            operator_inputs_active=False,
            automation_candidates=(),
            approval_refs=("guardian_draft_approval_request_contract",),
            channel_projection_refs=(),
            quieted_step_refs=(),
            blocked_actions=("authority_grant", "approval_submission", "runtime_execution") + COMMON_BLOCKED_ACTIONS,
            completion_condition="Security review need is classified; no authority is granted.",
            reopen_condition="Reopen when a new authority request appears.",
            next_safe_move="Show review classification only.",
            secondary_work_mode_types=("APPROVAL_WORK_MODE",),
            current_action_status="LOCKED",
            authority_granted=False,
        ),
        OperatorWorkModeInstance(
            work_mode_instance_id="niles_struna_project_work_mode",
            display_title="Niles / Struna Creative Project Work Mode",
            world="Creative",
            lane="niles_struna",
            issue_classification_ref="creative_music_project_issue",
            primary_work_mode_type="CREATIVE_PROJECT_WORK_MODE",
            active_step_id="resume_creative_thread",
            operator_bandwidth_default="LOW_BANDWIDTH",
            low_bandwidth_summary="Pick up where you left off.",
            normal_bandwidth_summary="Continue the creative/client/software lane with context, without publishing, sending, or rewriting files.",
            high_bandwidth_details=("project capsule refs", "album review refs", "client/software context"),
            debug_detail_refs=(
                "generated/read_models/struna_obscura_project_capsule_OPERATOR.md",
                "generated/read_models/niles_album_review_packet.json",
            ),
            one_next_human_move="Pick up where you left off.",
            plain_language_choices=("Continue this thread", "Need context", "Park it"),
            steps=(
                _step("resume_creative_thread", "Pick the creative thread to resume."),
                _step("keep_external_actions_locked", "Keep publish/send locked.", "LOCKED"),
            ),
            visible_context={"purpose": "continue creative/client/software lane without losing context"},
            hidden_context={"raw_project_files": "not loaded by this read-model"},
            proof_drawer_refs=("generated/read_models/niles_album_review_packet.json",),
            operator_inputs_available=("resume_thread", "needs_context", "park"),
            operator_inputs_active=False,
            automation_candidates=(),
            approval_refs=(),
            channel_projection_refs=(),
            quieted_step_refs=(),
            blocked_actions=("publish", "send", "file_rewrite", "external_account_access") + COMMON_BLOCKED_ACTIONS,
            completion_condition="Next creative thread is selected or parked; external action remains blocked.",
            reopen_condition="Reopen when project state, source refs, or operator focus changes.",
            next_safe_move="Show the last known project thread in plain language.",
            secondary_work_mode_types=(),
            current_action_status="LOCKED",
            authority_granted=False,
        ),
        OperatorWorkModeInstance(
            work_mode_instance_id="cassandra_clara_draft_work_mode",
            display_title="Cassandra / Clara Draft Work Mode",
            world="Communications",
            lane="cassandra_clara",
            issue_classification_ref="communication_draft_send_issue",
            primary_work_mode_type="DRAFT_COMMUNICATION_WORK_MODE",
            active_step_id="review_draft_before_send",
            operator_bandwidth_default="LOW_BANDWIDTH",
            low_bandwidth_summary="Review the draft before anything sends.",
            normal_bandwidth_summary="A future draft review/send path can be human-readable, but dispatch remains blocked.",
            high_bandwidth_details=("draft review packet refs", "approval refs", "send gates remain false"),
            debug_detail_refs=("generated/read_models/cassandra_draft_review_packet.json",),
            one_next_human_move="Review the draft before anything sends.",
            plain_language_choices=("Looks okay as a draft", "Needs changes", "Do not send"),
            steps=(
                _step("review_draft_before_send", "Review draft candidate."),
                _step("keep_send_locked", "Keep send path locked.", "LOCKED"),
            ),
            visible_context={"purpose": "draft review/send path later"},
            hidden_context={"raw_email_bodies": "hidden", "recipient_payloads": "hidden"},
            proof_drawer_refs=("generated/read_models/cassandra_draft_review_packet.json",),
            operator_inputs_available=("review_draft", "needs_revision", "reject"),
            operator_inputs_active=False,
            automation_candidates=(),
            approval_refs=("guardian_draft_approval_request_contract",),
            channel_projection_refs=("future_workflow_session_channel_projection",),
            quieted_step_refs=(),
            blocked_actions=("email_send", "telegram_send", "approval_submission") + COMMON_BLOCKED_ACTIONS,
            completion_condition="Draft review state is classified; no message is dispatched.",
            reopen_condition="Reopen when draft text, recipient status, or approval refs change.",
            next_safe_move="Show draft review state without a send action.",
            secondary_work_mode_types=("APPROVAL_WORK_MODE",),
            current_action_status="LOCKED",
            authority_granted=False,
        ),
    )


def human_translation_policy() -> OperatorHumanTranslationPolicy:
    return OperatorHumanTranslationPolicy(
        translation_source="deterministic_work_mode_packet",
        deterministic_inputs_required=(
            "issue classification",
            "work mode type",
            "bandwidth mode",
            "truth/blocker state",
            "authority flags",
            "proof refs",
            "available deterministic choices",
        ),
        lm_render_allowed=True,
        lm_render_role="plain-language renderer of deterministic solve-path packet only",
        lm_render_output_status="read-model or preview packet before app display when possible",
        lm_can_decide_authority=False,
        lm_can_mark_proof_complete=False,
        lm_can_approve_action=False,
        lm_can_create_hidden_memory=False,
        receipt_required_before_display=True,
        next_safe_move="Render human wording from deterministic state; never invent action buttons.",
        deterministic_choice_source="choices come from work-mode contract, issue classification, or decision-node contract later",
        dynamic_hallucinated_buttons_allowed=False,
    )


def helm_declutter_policy() -> HelmDeclutterPolicy:
    return HelmDeclutterPolicy(
        helm_should_show=(
            "urgent operator decisions",
            "blocked workflows needing human action",
            "high-level health/authority state",
            "next safe move cards",
        ),
        helm_should_hide=(
            "raw machine contracts",
            "long proof shelves",
            "generated read-model details",
            "completed or quieted steps",
            "duplicate proof rows",
        ),
        proof_should_live="one level down, inspectable, not default visual noise",
        machine_contract_visibility="hidden by default; inspectable in high bandwidth or debug",
        operator_attention_rule="show the few things that need Winship and the cleanest path through each one",
        focus_mode_entry_rule="enter focus when one work mode needs a human move or proof/decision review",
        focus_mode_exit_rule="exit after the move is classified, parked, quieted, or routed; no action executes",
        quieting_rule="quiet completed, duplicated, parked, or non-actionable steps with proof refs still traceable",
        reopen_rule="reopen when blocker, proof, authority, staleness, or operator request changes the state",
    )


def stable_map_exposure_policy() -> OperatorWorkModeStableMapExposurePolicy:
    return OperatorWorkModeStableMapExposurePolicy(
        stable_map_should_expose=(
            "active workflow sessions",
            "current work mode",
            "unresolved attention tickets",
            "automation readiness status",
            "one next human move",
            "low/normal/high bandwidth summaries",
            "proof summary refs",
        ),
        stable_map_should_not_expose=(
            "raw screenshots",
            "diagnostic logs",
            "transitional machine JSON",
            "draft email payloads",
            "raw protected content",
            "full contract internals",
        ),
        mac_should_render=(
            "current work mode card",
            "one next human move",
            "plain choices from deterministic packet",
            "proof summary link",
            "authority/blocker labels",
        ),
        mac_should_hide=(
            "raw protected content",
            "debug-only generated read-model body",
            "private draft payloads",
            "machine contract wall",
        ),
        proof_detail_policy="proof summary visible; detail drawer inspectable; raw protected content hidden",
        debug_detail_policy="debug may inspect refs and generated packets, but debug is never helm default",
    )


def relationship_to_existing_rails() -> list[dict[str, Any]]:
    return [
        {
            "rail_id": "capital_hilton_proof_intake_resolution",
            "display_name": "Capital Hilton proof intake/resolution",
            "read_model_refs": (
                "generated/read_models/capital_hilton_protected_proof_intake.json",
                "generated/read_models/capital_hilton_proof_resolution_batch_manifest.json",
                "generated/read_models/capital_hilton_proof_quieting_progress_state.json",
            ),
            "relationship": "substrate for Finance proof work mode; not duplicated",
        },
        {
            "rail_id": "coupa_po_automation_candidate",
            "display_name": "Coupa/PO automation candidate",
            "read_model_refs": ("generated/read_models/capital_hilton_coupa_po_retrieval_automation_candidate.json",),
            "relationship": "future-gated automation feasibility substrate; execution remains blocked",
        },
        {
            "rail_id": "work_terrain_reconciliation",
            "display_name": "Work Terrain reconciliation",
            "read_model_refs": (
                "generated/read_models/openclaw_work_terrain_gap_detector.json",
                "generated/read_models/openclaw_work_terrain_reconciliation_batch_manifest.json",
            ),
            "relationship": "terrain reconciliation substrate; no source rewrite or stable-map refresh",
        },
        {
            "rail_id": "security_pass",
            "display_name": "Security Pass",
            "read_model_refs": (
                "generated/read_models/security_pass_contract.json",
                "generated/read_models/security_delta_review_contract.json",
            ),
            "relationship": "authority and delta-review substrate; work mode cannot grant authority",
        },
        {
            "rail_id": "operator_attention_promotion",
            "display_name": "Operator Attention Promotion",
            "read_model_refs": ("generated/read_models/operator_attention_promotion_contract.json",),
            "relationship": "attention routing substrate; work mode renders human solve posture",
        },
        {
            "rail_id": "chief_test_harness_cross_off",
            "display_name": "Chief Test Harness / Cross-Off",
            "read_model_refs": ("generated/read_models/chief_test_harness_cross_off_receipt_contract.json",),
            "relationship": "diagnostic and completion-candidate substrate; no automatic cross-off",
        },
        {
            "rail_id": "governance_batch",
            "display_name": "Governance batch",
            "read_model_refs": ("generated/read_models/post_security_governance_batch_manifest.json",),
            "relationship": "governance substrate; no new control layer",
        },
        {
            "rail_id": "agent_council",
            "display_name": "Agent Council",
            "read_model_refs": (
                "generated/read_models/agent_package_preview_contract.json",
                "generated/read_models/agent_presence.json",
                "generated/read_models/agent_lanes.json",
            ),
            "relationship": "actor/package substrate; no agent activation",
        },
        {
            "rail_id": "package_preview",
            "display_name": "Package Preview",
            "read_model_refs": ("generated/read_models/package_preview_receipt_contract.json",),
            "relationship": "preview substrate; no submit/send/launch action",
        },
        {
            "rail_id": "tool_adapter_receipt",
            "display_name": "Tool Adapter Receipt",
            "read_model_refs": ("generated/read_models/tool_adapter_receipt_contract.json",),
            "relationship": "adapter receipt substrate; no tool execution",
        },
    ]


def build_operator_work_mode_schema_bandwidth_policy(
    *,
    repo_root: str | Path = ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    del repo_root
    bandwidth_modes = [asdict(item) for item in default_bandwidth_modes()]
    work_mode_types = [asdict(item) for item in default_work_mode_types()]
    issue_classifications = [asdict(item) for item in default_issue_classifications()]
    work_mode_instances = [asdict(item) for item in default_work_mode_instances()]
    human_policy = asdict(human_translation_policy())
    declutter = asdict(helm_declutter_policy())
    exposure = asdict(stable_map_exposure_policy())
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "contract_id": f"{READ_MODEL_ID}_v0",
        "generated_at": _generated_at(generated_at),
        "contract_status": CONTRACT_STATUS,
        "north_star": "Here are the few things that need Winship, and here is the cleanest path through each one.",
        "core_doctrine": {
            "simple_is_not_dumbed_down": True,
            "simple_is_distilled": True,
            "lowest_useful_cognitive_load_default": True,
            "one_next_human_move_default": True,
            "proof_details_one_level_down": True,
            "machine_contracts_are_substrate": True,
            "visible_app_renders_human_solve_paths": True,
            "machine_contracts_remain_inspectable": True,
            "capital_hilton_is_first_example_not_special_case": True,
        },
        "helm_default_bandwidth_mode": HELM_DEFAULT_BANDWIDTH_MODE,
        "bandwidth_mode_ids": list(BANDWIDTH_MODE_IDS),
        "work_mode_type_ids": list(WORK_MODE_TYPE_IDS),
        "issue_types": list(ISSUE_TYPES),
        "operator_bandwidth_mode_schema": {
            "structure": "OperatorBandwidthMode",
            "required_fields": list(REQUIRED_BANDWIDTH_MODE_FIELDS),
            "unknown_or_missing_result": "LOW_BANDWIDTH",
        },
        "operator_work_mode_type_schema": {
            "structure": "OperatorWorkModeType",
            "required_fields": list(REQUIRED_WORK_MODE_TYPE_FIELDS),
            "unknown_or_missing_result": "UNKNOWN_FAIL_CLOSED",
        },
        "operator_work_issue_classification_schema": {
            "structure": "OperatorWorkIssueClassification",
            "required_fields": list(REQUIRED_ISSUE_CLASSIFICATION_FIELDS),
            "unknown_or_missing_result": "UNKNOWN_FAIL_CLOSED",
        },
        "operator_work_mode_instance_schema": {
            "structure": "OperatorWorkModeInstance",
            "required_fields": list(REQUIRED_WORK_MODE_INSTANCE_FIELDS),
            "defaults": {
                "operator_inputs_active": False,
                "authority_granted": False,
                "live_execution": False,
            },
        },
        "bandwidth_modes": bandwidth_modes,
        "bandwidth_modes_by_id": {item["bandwidth_id"]: item for item in bandwidth_modes},
        "work_mode_types": work_mode_types,
        "work_mode_types_by_id": {item["work_mode_type_id"]: item for item in work_mode_types},
        "issue_classifications": issue_classifications,
        "issue_classifications_by_id": {item["issue_id"]: item for item in issue_classifications},
        "work_mode_instances": work_mode_instances,
        "work_mode_instances_by_id": {item["work_mode_instance_id"]: item for item in work_mode_instances},
        "human_translation_policy": human_policy,
        "helm_declutter_policy": declutter,
        "stable_map_exposure_policy": exposure,
        "relationship_to_existing_rails": relationship_to_existing_rails(),
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "hard_rule": {
            "read_model_only": True,
            "does_not_implement_solve_paths_yet": True,
            "does_not_implement_decision_nodes_yet": True,
            "does_not_implement_guided_capture_yet": True,
            "does_not_implement_approval_bus_yet": True,
            "does_not_implement_automation_feasibility_yet": True,
            "does_not_implement_mac_ui": True,
            "does_not_refresh_stable_map": True,
            "may_execute": False,
            "may_persist_operator_input": False,
            "may_grant_authority": False,
        },
        "machine_proof": {
            "bandwidth_mode_count": len(bandwidth_modes),
            "work_mode_type_count": len(work_mode_types),
            "issue_classification_count": len(issue_classifications),
            "work_mode_instance_count": len(work_mode_instances),
            "all_bandwidth_modes_present": set(BANDWIDTH_MODE_IDS)
            == {item["bandwidth_id"] for item in bandwidth_modes},
            "all_work_mode_types_present": set(WORK_MODE_TYPE_IDS)
            == {item["work_mode_type_id"] for item in work_mode_types},
            "all_issue_types_present": set(ISSUE_TYPES)
            == {item["issue_type"] for item in issue_classifications},
            "helm_default_is_low_or_normal": HELM_DEFAULT_BANDWIDTH_MODE in {"LOW_BANDWIDTH", "NORMAL_BANDWIDTH"},
            "debug_mode_is_not_default": HELM_DEFAULT_BANDWIDTH_MODE != "DEBUG_MODE",
            "high_bandwidth_is_not_default": HELM_DEFAULT_BANDWIDTH_MODE != "HIGH_BANDWIDTH",
            "operator_inputs_active_default_false": all(
                item["operator_inputs_active"] is False for item in work_mode_instances
            ),
            "authority_granted_default_false": all(
                item["authority_granted"] is False for item in issue_classifications + work_mode_instances
            ),
            "lm_cannot_decide_authority": human_policy["lm_can_decide_authority"] is False,
            "lm_cannot_mark_proof_complete": human_policy["lm_can_mark_proof_complete"] is False,
            "lm_cannot_approve_action": human_policy["lm_can_approve_action"] is False,
            "machine_contracts_not_default_app_surface": (
                declutter["machine_contract_visibility"] == "hidden by default; inspectable in high bandwidth or debug"
            ),
            "human_translation_policy_present": True,
            "helm_declutter_policy_present": True,
            "stable_map_exposure_policy_present": True,
            "relationship_to_existing_rails_count": len(relationship_to_existing_rails()),
            "all_authority_flags_false": _all_authority_flags_false(),
            "action_authority_granted": False,
            "credentials_or_secrets_included": False,
            "raw_private_bodies_included": False,
            "content_hash": None,
        },
    }
    payload["machine_proof"]["content_hash"] = _content_hash(payload)
    return payload


def format_operator_work_mode_markdown(payload: dict[str, Any]) -> str:
    proof = payload["machine_proof"]
    lines = [
        "# Operator Work Mode Schema / Bandwidth Policy v0",
        "",
        "## ELIWINSHIP Summary",
        "",
        "The helm feels overloaded when it shows the system's internal contracts as if they are Winship's job. Work Mode changes the default shape: show the few things that need Winship, say the next human move in plain language, and keep proof/details one level down.",
        "",
        "Simple is not less powerful here. Simple means the system already did the sorting. The raw contracts, receipts, proof shelves, and generated read-models still exist, but they become substrate instead of the front door.",
        "",
        "This prompt does not build UI or enable actions. It defines the read-model shape that a later app surface can use to render human solve paths.",
        "",
        "## Bandwidth Defaults",
        "",
        f"- Helm default: `{payload['helm_default_bandwidth_mode']}`.",
        "- Low bandwidth: one next move, plain language, short choices, details hidden unless opened.",
        "- Normal bandwidth: short explanation, why it matters, next step, choices, proof summary.",
        "- High bandwidth: blockers, proof refs, receipt refs, authority gates, workflow relationship.",
        "- Debug mode: contracts, generated read-models, raw fields, proof shelves, diagnostics. Never default.",
        "",
        "## Work Modes",
        "",
    ]
    for item in payload["work_mode_types"]:
        lines.append(f"- `{item['work_mode_type_id']}`: {item['human_purpose']}")
    lines.extend(
        [
            "",
            "## App-Wide Examples",
            "",
        ]
    )
    for item in payload["work_mode_instances"]:
        lines.append(
            f"- `{item['work_mode_instance_id']}`: {item['one_next_human_move']} "
            f"Purpose: {item['visible_context'].get('purpose', 'classified work mode')}."
        )
    lines.extend(
        [
            "",
            "Capital Hilton is only the first major example. The same schema also covers terrain reconciliation, developer/system diagnostics, security review, creative/music work, communication drafts, client/project delivery, proof/reference work, and automation candidates.",
            "",
            "## Human Translation",
            "",
            "- Deterministic state decides truth, blockers, authority, and proof status.",
            "- The LM may render plain language from a deterministic packet.",
            "- The LM cannot decide authority, mark proof complete, approve an action, create hidden memory, or invent dynamic buttons.",
            "- Output should become a read-model or preview packet before app display when possible.",
            "",
            "## Helm Declutter",
            "",
            "- Helm should show urgent decisions, blocked workflows needing human action, high-level health/authority state, and next safe move cards.",
            "- Helm should hide raw machine contracts, long proof shelves, generated read-model details, completed/quieted steps, and duplicate proof rows.",
            "- Proof stays one level down: inspectable, but not default visual noise.",
            "",
            "## Stable Map / App Exposure",
            "",
            "- Eventually expose active workflow sessions, current work mode, unresolved attention tickets, automation readiness, one next human move, bandwidth summaries, and proof summary refs.",
            "- Keep raw screenshots, logs, transitional machine JSON, draft email payloads, raw protected content, and full contract internals out of the default surface.",
            "",
            "## Still Blocked",
            "",
            "- No live workflow execution, input persistence, automation execution, approval submission, invoice generation, email/Telegram send, browser/account/Coupa/Gmail/calendar access, credential handling, model/tool/agent/runtime/queue execution, ledger write, file cleanup, stable-map refresh, Mac UI implementation, or Mission Control Swift change.",
            "",
            "## Prompt 2",
            "",
            "- Prompt 2 should add the Operator Solve Path and Decision Node Contract. That is where explicit solve-path steps and decision nodes become deterministic packets. This prompt only defines the app-wide mode and bandwidth schema.",
            "",
            "## Machine Proof Summary",
            "",
            f"- Bandwidth modes: `{proof['bandwidth_mode_count']}`.",
            f"- Work mode types: `{proof['work_mode_type_count']}`.",
            f"- Issue classifications: `{proof['issue_classification_count']}`.",
            f"- Work mode instances: `{proof['work_mode_instance_count']}`.",
            f"- All authority flags false: `{str(proof['all_authority_flags_false']).lower()}`.",
            f"- Machine contracts are not default app surface: `{str(proof['machine_contracts_not_default_app_surface']).lower()}`.",
            f"- Content hash: `{proof['content_hash']}`.",
        ]
    )
    return "\n".join(lines) + "\n"


def export_operator_work_mode_schema_bandwidth_policy(
    *,
    repo_root: str | Path = ROOT,
    export_root: str | Path = DEFAULT_EXPORT_ROOT,
    generated_at: str | None = None,
) -> WorkModeExportResult:
    payload = build_operator_work_mode_schema_bandwidth_policy(repo_root=repo_root, generated_at=generated_at)
    root = Path(export_root)
    if not root.is_absolute():
        root = Path(repo_root) / root
    root.mkdir(parents=True, exist_ok=True)
    json_path = root / JSON_EXPORT_NAME
    operator_path = root / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(format_operator_work_mode_markdown(payload), encoding="utf-8")
    return WorkModeExportResult(
        schema_version=SCHEMA_VERSION,
        json_path=json_path.as_posix(),
        operator_path=operator_path.as_posix(),
        bandwidth_mode_count=len(payload["bandwidth_modes"]),
        work_mode_type_count=len(payload["work_mode_types"]),
        issue_classification_count=len(payload["issue_classifications"]),
        work_mode_instance_count=len(payload["work_mode_instances"]),
        helm_default_bandwidth_mode=payload["helm_default_bandwidth_mode"],
        action_authority_granted=False,
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export Operator Work Mode Schema / Bandwidth Policy.")
    parser.add_argument("--repo-root", default=ROOT.as_posix())
    parser.add_argument("--export-root", default=DEFAULT_EXPORT_ROOT.as_posix())
    parser.add_argument("--format", choices=("summary", "json", "operator"), default="operator")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    result = export_operator_work_mode_schema_bandwidth_policy(
        repo_root=args.repo_root,
        export_root=args.export_root,
    )
    summary = {
        "schema_version": result.schema_version,
        "json_path": result.json_path,
        "operator_path": result.operator_path,
        "bandwidth_mode_count": result.bandwidth_mode_count,
        "work_mode_type_count": result.work_mode_type_count,
        "issue_classification_count": result.issue_classification_count,
        "work_mode_instance_count": result.work_mode_instance_count,
        "helm_default_bandwidth_mode": result.helm_default_bandwidth_mode,
        "action_authority_granted": result.action_authority_granted,
    }
    if args.format in {"summary", "json"}:
        print(stable_json(summary), end="")
    else:
        print("Operator Work Mode Schema / Bandwidth Policy exported")
        print(f"- JSON: `{result.json_path}`")
        print(f"- Operator: `{result.operator_path}`")
    return 0


__all__ = [
    "AUTHORITY_BOUNDARY",
    "BANDWIDTH_MODE_IDS",
    "HELM_DEFAULT_BANDWIDTH_MODE",
    "ISSUE_TYPES",
    "JSON_EXPORT_NAME",
    "OPERATOR_EXPORT_NAME",
    "READ_MODEL_ID",
    "REQUIRED_BANDWIDTH_MODE_FIELDS",
    "REQUIRED_ISSUE_CLASSIFICATION_FIELDS",
    "REQUIRED_WORK_MODE_INSTANCE_FIELDS",
    "REQUIRED_WORK_MODE_TYPE_FIELDS",
    "SCHEMA_VERSION",
    "WORK_MODE_TYPE_IDS",
    "build_operator_work_mode_schema_bandwidth_policy",
    "default_bandwidth_modes",
    "default_issue_classifications",
    "default_work_mode_instances",
    "default_work_mode_types",
    "export_operator_work_mode_schema_bandwidth_policy",
    "format_operator_work_mode_markdown",
    "helm_declutter_policy",
    "human_translation_policy",
    "relationship_to_existing_rails",
    "stable_json",
    "stable_map_exposure_policy",
]
