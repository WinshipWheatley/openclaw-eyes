"""Operator Solve Path / Decision Node Contract v0.

This read-model defines how deterministic machine state becomes a
human-readable solve path with clear choices, branch outcomes, and canonical
receipt targets. It models what a future system would do after an operator
choice, but it does not persist answers, write receipts, create UI buttons,
refresh the stable map, execute workflows, call models/tools/agents/runtimes,
access external accounts, generate invoices, send messages, submit approvals,
write ledgers, or grant authority.
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

SCHEMA_VERSION = "operator_solve_path_decision_node_contract_v0"
READ_MODEL_ID = "operator_solve_path_decision_node_contract"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
OPERATOR_EXPORT_NAME = f"{READ_MODEL_ID}_OPERATOR.md"
CONTRACT_STATUS = "DETERMINISTIC_NON_EXECUTING_SOLVE_PATH_CONTRACT"

PROMPT_1_READ_MODEL_REF = "generated/read_models/operator_work_mode_schema_bandwidth_policy.json"
PROMPT_1_OPERATOR_REF = "generated/read_models/operator_work_mode_schema_bandwidth_policy_OPERATOR.md"

DECISION_NODE_STATUSES = (
    "NOT_STARTED",
    "ACTIVE",
    "ANSWER_PREVIEW_ONLY",
    "ANSWER_READY_TO_CAPTURE",
    "ANSWER_CAPTURED",
    "NEEDS_FOLLOWUP_CHOICE",
    "NEEDS_EVIDENCE",
    "NEEDS_GUIDED_CAPTURE",
    "NEEDS_DISCOVERY",
    "PARKED",
    "REJECTED",
    "BLOCKED",
    "UNKNOWN_FAIL_CLOSED",
)

CHOICE_TYPES = (
    "CONFIRM_TRUE",
    "CORRECT_VALUE",
    "ADD_VALUE",
    "REMOVE_VALUE",
    "I_DONT_KNOW",
    "NEEDS_DISCOVERY",
    "POINT_TO_PROOF",
    "START_GUIDED_CAPTURE",
    "PARK_THIS",
    "REJECT_THIS",
    "REQUEST_HELP",
    "UNKNOWN_FAIL_CLOSED",
)

RECEIPT_TYPES = (
    "OPERATOR_CONFIRMATION_RECEIPT",
    "OPERATOR_CORRECTION_RECEIPT",
    "OPERATOR_MEMORY_CANDIDATE_RECEIPT",
    "PROOF_POINTER_RECEIPT",
    "DISCOVERY_SUBSTEP_RECEIPT",
    "GUIDED_CAPTURE_PATH_RECEIPT",
    "PARKED_STEP_RECEIPT",
    "REJECTION_RECEIPT",
    "AUTOMATION_CANDIDATE_RECEIPT",
    "UNKNOWN_FAIL_CLOSED",
)

REQUIRED_SOLVE_PATH_FIELDS = (
    "solve_path_id",
    "display_title",
    "world",
    "lane",
    "actor",
    "work_mode_type",
    "issue_classification_ref",
    "source_machine_state_refs",
    "deterministic_context_refs",
    "operator_bandwidth_default",
    "low_bandwidth_move",
    "normal_bandwidth_explanation",
    "high_bandwidth_proof_refs",
    "debug_detail_refs",
    "current_decision_node_id",
    "visible_steps",
    "quieted_steps",
    "blocked_steps",
    "proof_detail_refs",
    "automation_candidate_refs",
    "approval_refs",
    "next_safe_move",
)

REQUIRED_DECISION_NODE_FIELDS = (
    "decision_node_id",
    "display_title",
    "plain_language_prompt",
    "what_system_thinks",
    "why_this_matters",
    "operator_needed_for",
    "choices",
    "optional_freeform_allowed",
    "freeform_purpose",
    "canonical_receipt_target",
    "current_status",
    "after_answer_state",
    "blocked_actions",
    "next_safe_move",
)

REQUIRED_DECISION_CHOICE_FIELDS = (
    "choice_id",
    "label",
    "human_meaning",
    "choice_type",
    "requires_followup",
    "followup_node_id",
    "receipt_effect",
    "proof_effect",
    "workflow_state_effect",
    "quieting_effect",
    "surface_update_effect",
    "creates_discovery_substep",
    "creates_guided_capture_path",
    "creates_automation_candidate",
    "authority_granted",
    "blocked_actions",
    "next_safe_move",
)

REQUIRED_RECEIPT_TARGET_FIELDS = (
    "receipt_target_id",
    "receipt_type",
    "would_write_to",
    "canonical_session_ref",
    "affected_proof_item_refs",
    "affected_step_refs",
    "affected_surfaces",
    "state_change_summary",
    "requires_sqlite_writer",
    "requires_guardian_review",
    "requires_operator_final_authority",
    "would_quiet_step",
    "would_create_discovery_substep",
    "would_create_guided_capture_path",
    "would_create_automation_candidate",
    "current_write_authority_granted",
    "next_safe_move",
)

AUTHORITY_BOUNDARY = {
    "workflow_execution_allowed": False,
    "operator_input_persistence_allowed": False,
    "sqlite_answer_write_allowed": False,
    "receipt_write_allowed": False,
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
    "SQLite answer write",
    "receipt write",
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
class OperatorDecisionChoice:
    choice_id: str
    label: str
    human_meaning: str
    choice_type: str
    requires_followup: bool
    followup_node_id: str
    receipt_effect: str
    proof_effect: str
    workflow_state_effect: str
    quieting_effect: str
    surface_update_effect: str
    creates_discovery_substep: bool
    creates_guided_capture_path: bool
    creates_automation_candidate: bool
    authority_granted: bool
    blocked_actions: tuple[str, ...]
    next_safe_move: str


@dataclass(frozen=True)
class OperatorDecisionNode:
    decision_node_id: str
    display_title: str
    plain_language_prompt: str
    what_system_thinks: tuple[str, ...]
    why_this_matters: str
    operator_needed_for: str
    choices: tuple[OperatorDecisionChoice, ...]
    optional_freeform_allowed: bool
    freeform_purpose: str
    canonical_receipt_target: str
    current_status: str
    after_answer_state: str
    blocked_actions: tuple[str, ...]
    next_safe_move: str


@dataclass(frozen=True)
class OperatorChoiceReceiptTarget:
    receipt_target_id: str
    receipt_type: str
    would_write_to: str
    canonical_session_ref: str
    affected_proof_item_refs: tuple[str, ...]
    affected_step_refs: tuple[str, ...]
    affected_surfaces: tuple[str, ...]
    state_change_summary: str
    requires_sqlite_writer: bool
    requires_guardian_review: bool
    requires_operator_final_authority: bool
    would_quiet_step: bool
    would_create_discovery_substep: bool
    would_create_guided_capture_path: bool
    would_create_automation_candidate: bool
    current_write_authority_granted: bool
    next_safe_move: str


@dataclass(frozen=True)
class OperatorSolvePath:
    solve_path_id: str
    display_title: str
    world: str
    lane: str
    actor: str
    work_mode_type: str
    issue_classification_ref: str
    source_machine_state_refs: tuple[str, ...]
    deterministic_context_refs: tuple[str, ...]
    operator_bandwidth_default: str
    low_bandwidth_move: str
    normal_bandwidth_explanation: str
    high_bandwidth_proof_refs: tuple[str, ...]
    debug_detail_refs: tuple[str, ...]
    current_decision_node_id: str
    visible_steps: tuple[str, ...]
    quieted_steps: tuple[str, ...]
    blocked_steps: tuple[str, ...]
    proof_detail_refs: tuple[str, ...]
    automation_candidate_refs: tuple[str, ...]
    approval_refs: tuple[str, ...]
    next_safe_move: str


@dataclass(frozen=True)
class SolvePathLMRenderingBoundary:
    lm_may_rephrase: bool
    lm_may_generate_plain_language: bool
    lm_may_create_new_choices: bool
    lm_may_decide_authority: bool
    lm_may_mark_proof_complete: bool
    lm_may_approve_action: bool
    lm_may_hide_blockers: bool
    deterministic_choice_source_required: bool
    rendered_output_status: str


@dataclass(frozen=True)
class SolvePathExportResult:
    schema_version: str
    json_path: str
    operator_path: str
    solve_path_count: int
    decision_node_count: int
    receipt_target_count: int
    action_authority_granted: bool


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _content_hash(payload: dict[str, Any]) -> str:
    clone = json.loads(stable_json(payload))
    clone.get("machine_proof", {}).pop("content_hash", None)
    return "sha256:" + hashlib.sha256(stable_json(clone).encode("utf-8")).hexdigest()


def _generated_at(value: str | None) -> str:
    return value or datetime.now(timezone.utc).isoformat(timespec="seconds")


def _all_authority_flags_false() -> bool:
    return all(value is False for value in AUTHORITY_BOUNDARY.values())


def _choice(
    choice_id: str,
    *,
    label: str,
    human_meaning: str,
    choice_type: str,
    receipt_effect: str,
    proof_effect: str,
    workflow_state_effect: str,
    quieting_effect: str,
    surface_update_effect: str,
    next_safe_move: str,
    requires_followup: bool = False,
    followup_node_id: str = "none",
    creates_discovery_substep: bool = False,
    creates_guided_capture_path: bool = False,
    creates_automation_candidate: bool = False,
    authority_granted: bool = False,
    blocked_actions: tuple[str, ...] = COMMON_BLOCKED_ACTIONS,
) -> OperatorDecisionChoice:
    return OperatorDecisionChoice(
        choice_id=choice_id,
        label=label,
        human_meaning=human_meaning,
        choice_type=choice_type,
        requires_followup=requires_followup,
        followup_node_id=followup_node_id,
        receipt_effect=receipt_effect,
        proof_effect=proof_effect,
        workflow_state_effect=workflow_state_effect,
        quieting_effect=quieting_effect,
        surface_update_effect=surface_update_effect,
        creates_discovery_substep=creates_discovery_substep,
        creates_guided_capture_path=creates_guided_capture_path,
        creates_automation_candidate=creates_automation_candidate,
        authority_granted=authority_granted,
        blocked_actions=blocked_actions,
        next_safe_move=next_safe_move,
    )


def _node(
    decision_node_id: str,
    *,
    display_title: str,
    plain_language_prompt: str,
    what_system_thinks: tuple[str, ...],
    why_this_matters: str,
    operator_needed_for: str,
    choices: tuple[OperatorDecisionChoice, ...],
    canonical_receipt_target: str,
    current_status: str = "ACTIVE",
    after_answer_state: str = "preview_only_until_receipt_writer_exists",
    optional_freeform_allowed: bool = False,
    freeform_purpose: str = "not_allowed_for_this_node",
    blocked_actions: tuple[str, ...] = COMMON_BLOCKED_ACTIONS,
    next_safe_move: str = "Pick what is true; no live action runs.",
) -> OperatorDecisionNode:
    return OperatorDecisionNode(
        decision_node_id=decision_node_id,
        display_title=display_title,
        plain_language_prompt=plain_language_prompt,
        what_system_thinks=what_system_thinks,
        why_this_matters=why_this_matters,
        operator_needed_for=operator_needed_for,
        choices=choices,
        optional_freeform_allowed=optional_freeform_allowed,
        freeform_purpose=freeform_purpose,
        canonical_receipt_target=canonical_receipt_target,
        current_status=current_status,
        after_answer_state=after_answer_state,
        blocked_actions=blocked_actions,
        next_safe_move=next_safe_move,
    )


def default_decision_nodes() -> tuple[OperatorDecisionNode, ...]:
    return (
        _node(
            "confirm_performance_dates",
            display_title="Confirm Performance Dates",
            plain_language_prompt="OpenClaw thinks these were the Capital Hilton performance dates. What is true?",
            what_system_thinks=("May 8, 2026", "May 15, 2026"),
            why_this_matters=(
                "The invoice path needs operator-confirmed dates before it can move to rate confirmation."
            ),
            operator_needed_for="pick the true date state",
            canonical_receipt_target="capital_hilton_performance_dates_confirmation_target",
            choices=(
                _choice(
                    "both_dates_are_right",
                    label="Both are right",
                    human_meaning="The two listed performance dates match what Winship knows.",
                    choice_type="CONFIRM_TRUE",
                    receipt_effect="creates operator confirmation receipt target",
                    proof_effect=(
                        "dates become operator-confirmed, not externally proven; proof may still be needed before final send"
                    ),
                    workflow_state_effect="moves workflow to confirm_rate",
                    quieting_effect="would quiet confirm_performance_dates only after a future receipt is written",
                    surface_update_effect="solve path would advance from dates to rate confirmation",
                    next_safe_move="Preview the confirmation target; do not write it yet.",
                ),
                _choice(
                    "one_date_is_wrong",
                    label="One is wrong",
                    human_meaning="At least one listed performance date needs correction.",
                    choice_type="CORRECT_VALUE",
                    requires_followup=True,
                    followup_node_id="correct_performance_date",
                    receipt_effect="creates operator correction receipt target after follow-up",
                    proof_effect="no external proof claim; correction remains operator-supplied until proven",
                    workflow_state_effect="opens follow-up node correct_performance_date with no dead end",
                    quieting_effect="does not quiet date step until correction is classified",
                    surface_update_effect="focus moves to the correction node",
                    next_safe_move="Ask which date is wrong and what it should be.",
                ),
                _choice(
                    "add_another_date",
                    label="Add another date",
                    human_meaning="The invoice may need an additional performance date.",
                    choice_type="ADD_VALUE",
                    requires_followup=True,
                    followup_node_id="add_performance_date",
                    receipt_effect="creates operator correction/addition receipt target after follow-up",
                    proof_effect="added date is operator-supplied until proof exists",
                    workflow_state_effect="opens add_performance_date; recalculation may be needed later",
                    quieting_effect="keeps date step active until added date is classified",
                    surface_update_effect="focus moves to add date node",
                    next_safe_move="Ask for the additional date in a follow-up node.",
                ),
                _choice(
                    "i_dont_know_dates",
                    label="I don't know",
                    human_meaning="Winship cannot confirm the dates right now.",
                    choice_type="I_DONT_KNOW",
                    receipt_effect="creates discovery substep receipt target",
                    proof_effect="no proof claim; date truth remains unresolved",
                    workflow_state_effect="keeps workflow alive and may move focus to next answerable step",
                    quieting_effect="date step stays unresolved but can be quieted behind discovery focus",
                    surface_update_effect="shows discovery-needed state instead of a dead end",
                    creates_discovery_substep=True,
                    next_safe_move="Create a discovery substep target and keep the path alive.",
                ),
                _choice(
                    "needs_discovery_dates",
                    label="Needs discovery",
                    human_meaning="The system should later help search for proof/date evidence.",
                    choice_type="NEEDS_DISCOVERY",
                    receipt_effect="creates discovery substep for proof/date search",
                    proof_effect="proof still missing; no external truth claim",
                    workflow_state_effect="routes to Cassandra/Chief later when active; no action authority",
                    quieting_effect="can quiet the decision into a discovery lane after future receipt",
                    surface_update_effect="shows proof/date discovery state",
                    creates_discovery_substep=True,
                    next_safe_move="Model the discovery target; do not run search.",
                ),
                _choice(
                    "date_set_is_wrong",
                    label="This date set is wrong",
                    human_meaning="The listed date set should not be treated as the right set.",
                    choice_type="REJECT_THIS",
                    requires_followup=True,
                    followup_node_id="date_discovery_needed",
                    receipt_effect="creates rejection/correction receipt target after reason",
                    proof_effect="rejects current candidate only; does not prove replacement dates",
                    workflow_state_effect="opens correction/rejection path and requires reason before quieting",
                    quieting_effect="cannot quiet until reason is captured by future receipt writer",
                    surface_update_effect="shows date set rejected or needs correction",
                    next_safe_move="Ask for the rejection reason before any quieting.",
                ),
            ),
        ),
        _node(
            "correct_performance_date",
            display_title="Correct Performance Date",
            plain_language_prompt="Which date is wrong, and what should it be?",
            what_system_thinks=("May 8, 2026", "May 15, 2026"),
            why_this_matters="A corrected date can keep the invoice path alive without pretending proof is complete.",
            operator_needed_for="provide a corrected date candidate",
            canonical_receipt_target="capital_hilton_performance_date_correction_target",
            current_status="NOT_STARTED",
            optional_freeform_allowed=True,
            freeform_purpose="capture corrected date text later through guided capture",
            choices=(
                _choice(
                    "correct_date_value_later",
                    label="Correct the date",
                    human_meaning="Provide the replacement date later through a capture path.",
                    choice_type="CORRECT_VALUE",
                    receipt_effect="creates correction receipt target",
                    proof_effect="corrected date is operator-supplied, not externally proven",
                    workflow_state_effect="keeps date step in correction state",
                    quieting_effect="does not quiet until correction receipt exists",
                    surface_update_effect="shows corrected-date preview state",
                    next_safe_move="Model correction target only.",
                ),
            ),
        ),
        _node(
            "add_performance_date",
            display_title="Add Performance Date",
            plain_language_prompt="What additional performance date should be added?",
            what_system_thinks=("May 8, 2026", "May 15, 2026"),
            why_this_matters="Adding a date may affect later invoice math and proof requirements.",
            operator_needed_for="provide an additional date candidate",
            canonical_receipt_target="capital_hilton_performance_date_addition_target",
            current_status="NOT_STARTED",
            optional_freeform_allowed=True,
            freeform_purpose="capture added date text later through guided capture",
            choices=(
                _choice(
                    "add_date_value_later",
                    label="Add a date",
                    human_meaning="Provide another performance date later through a capture path.",
                    choice_type="ADD_VALUE",
                    receipt_effect="creates add-value receipt target",
                    proof_effect="added date is operator-supplied, not externally proven",
                    workflow_state_effect="keeps date step in add-date state; recalculation may be needed later",
                    quieting_effect="does not quiet until add-date receipt exists",
                    surface_update_effect="shows added-date preview state",
                    next_safe_move="Model add-date target only.",
                ),
            ),
        ),
        _node(
            "date_discovery_needed",
            display_title="Date Discovery Needed",
            plain_language_prompt="What should OpenClaw look for later to resolve the performance dates?",
            what_system_thinks=("date proof is unresolved",),
            why_this_matters="Discovery keeps the workflow alive when Winship cannot confirm truth immediately.",
            operator_needed_for="classify the discovery need",
            canonical_receipt_target="capital_hilton_date_discovery_substep_target",
            current_status="NOT_STARTED",
            optional_freeform_allowed=True,
            freeform_purpose="describe the likely proof source later without opening accounts or files now",
            choices=(
                _choice(
                    "start_date_discovery_later",
                    label="Create discovery step",
                    human_meaning="A later worker should search for date proof under proper authority.",
                    choice_type="NEEDS_DISCOVERY",
                    receipt_effect="creates discovery substep receipt target",
                    proof_effect="proof remains missing until a later evidence path resolves it",
                    workflow_state_effect="moves date decision into discovery-needed state",
                    quieting_effect="can quiet the prompt into a discovery substep after future receipt",
                    surface_update_effect="shows discovery needed",
                    creates_discovery_substep=True,
                    next_safe_move="Model discovery target only.",
                ),
            ),
        ),
        _node(
            "check_engine_actual_breakage",
            display_title="Check Engine Actual Breakage",
            plain_language_prompt="What is actually broken?",
            what_system_thinks=("diagnostic evidence exists", "repair execution is locked"),
            why_this_matters="Winship should see evidence before any repair lane is selected.",
            operator_needed_for="classify broken, noisy, or needs another check",
            canonical_receipt_target="check_engine_diagnostic_classification_target",
            choices=(
                _choice(
                    "diagnostic_is_broken",
                    label="This is broken",
                    human_meaning="The diagnostic evidence points to a real issue.",
                    choice_type="CONFIRM_TRUE",
                    receipt_effect="creates diagnostic classification receipt target",
                    proof_effect="diagnostic is classified, not repaired",
                    workflow_state_effect="would route to a future repair lane",
                    quieting_effect="keeps repair locked until authorized",
                    surface_update_effect="shows repair lane candidate",
                    next_safe_move="Classify broken state only.",
                ),
                _choice(
                    "diagnostic_is_noise",
                    label="This is only noisy",
                    human_meaning="The diagnostic should not be treated as an active break.",
                    choice_type="REJECT_THIS",
                    receipt_effect="creates rejection receipt target",
                    proof_effect="diagnostic is rejected as active proof",
                    workflow_state_effect="parks or quiets the diagnostic after future receipt",
                    quieting_effect="would quiet diagnostic after receipt writer exists",
                    surface_update_effect="shows quiet-with-proof candidate",
                    next_safe_move="Model rejection target only.",
                ),
                _choice(
                    "diagnostic_needs_more_checking",
                    label="Needs another check",
                    human_meaning="More diagnostic evidence is needed.",
                    choice_type="NEEDS_DISCOVERY",
                    receipt_effect="creates discovery substep target",
                    proof_effect="evidence remains incomplete",
                    workflow_state_effect="keeps diagnostic path alive",
                    quieting_effect="can quiet current prompt into discovery",
                    surface_update_effect="shows diagnostic discovery needed",
                    creates_discovery_substep=True,
                    next_safe_move="Model diagnostic discovery target only.",
                ),
            ),
        ),
        _node(
            "chief_terrain_currentness",
            display_title="Chief Terrain Currentness",
            plain_language_prompt="What should stay current?",
            what_system_thinks=("terrain item may be current, stale, overlapping, or missing source",),
            why_this_matters="Terrain reconciliation should reduce noise without rewriting files.",
            operator_needed_for="classify currentness",
            canonical_receipt_target="chief_terrain_reconciliation_target",
            choices=(
                _choice(
                    "terrain_stays_current",
                    label="Keep current",
                    human_meaning="This terrain should remain visible as current.",
                    choice_type="CONFIRM_TRUE",
                    receipt_effect="creates terrain confirmation receipt target",
                    proof_effect="operator confirms currentness, not source truth",
                    workflow_state_effect="would keep terrain visible",
                    quieting_effect="can quiet duplicate review prompt later",
                    surface_update_effect="shows current terrain candidate",
                    next_safe_move="Model currentness target only.",
                ),
                _choice(
                    "terrain_is_stale",
                    label="Looks stale",
                    human_meaning="This terrain may be outdated.",
                    choice_type="CORRECT_VALUE",
                    requires_followup=True,
                    followup_node_id="terrain_staleness_reason",
                    receipt_effect="creates terrain correction receipt target after reason",
                    proof_effect="staleness remains candidate until source refs support it",
                    workflow_state_effect="opens staleness reason follow-up",
                    quieting_effect="does not quiet until classified",
                    surface_update_effect="shows stale candidate",
                    next_safe_move="Ask why it is stale later.",
                ),
                _choice(
                    "terrain_needs_source",
                    label="Needs source",
                    human_meaning="The system needs a source before deciding.",
                    choice_type="NEEDS_DISCOVERY",
                    receipt_effect="creates source discovery substep target",
                    proof_effect="source proof remains missing",
                    workflow_state_effect="keeps terrain path alive",
                    quieting_effect="moves noisy item into source discovery later",
                    surface_update_effect="shows source-needed state",
                    creates_discovery_substep=True,
                    next_safe_move="Model source discovery target only.",
                ),
            ),
        ),
        _node(
            "security_delta_review_needed",
            display_title="Security Delta Needed",
            plain_language_prompt="Does this need security review?",
            what_system_thinks=("new authority may be requested", "fail closed unless classified"),
            why_this_matters="New authority must not sneak into the app as a normal choice.",
            operator_needed_for="classify security review need",
            canonical_receipt_target="security_delta_review_classification_target",
            choices=(
                _choice(
                    "needs_security_review",
                    label="Needs security review",
                    human_meaning="This should route to Security Delta before anything runs.",
                    choice_type="CONFIRM_TRUE",
                    receipt_effect="creates security delta classification receipt target",
                    proof_effect="security review needed is classified, not approved",
                    workflow_state_effect="routes to security delta lane later",
                    quieting_effect="keeps action blocked",
                    surface_update_effect="shows security review needed",
                    next_safe_move="Model security review target only.",
                ),
                _choice(
                    "no_new_authority",
                    label="No new authority",
                    human_meaning="This appears to be read-only or metadata-only.",
                    choice_type="CONFIRM_TRUE",
                    receipt_effect="creates no-delta classification target",
                    proof_effect="classification only; does not approve action",
                    workflow_state_effect="may keep item in read-only preview lane",
                    quieting_effect="can quiet security prompt after receipt writer exists",
                    surface_update_effect="shows no-new-authority candidate",
                    next_safe_move="Model no-delta target only.",
                ),
                _choice(
                    "security_fail_closed",
                    label="Fail closed",
                    human_meaning="Do not proceed until reviewed.",
                    choice_type="UNKNOWN_FAIL_CLOSED",
                    receipt_effect="creates fail-closed receipt target",
                    proof_effect="no proof or authority claim",
                    workflow_state_effect="blocks the path",
                    quieting_effect="keeps visible as blocked or quiet-with-proof later",
                    surface_update_effect="shows fail-closed state",
                    next_safe_move="Keep authority blocked.",
                ),
            ),
        ),
        _node(
            "coupa_po_manual_or_automation",
            display_title="Coupa / PO Manual Or Automation Path",
            plain_language_prompt="Choose manual capture now or build the automation path.",
            what_system_thinks=("manual fallback exists", "automation is future-gated"),
            why_this_matters="Automation can reduce repeated work later, but it cannot run without security and authority.",
            operator_needed_for="choose manual/future-gated/reject",
            canonical_receipt_target="coupa_po_automation_candidate_choice_target",
            choices=(
                _choice(
                    "manual_capture_now",
                    label="Manual capture later",
                    human_meaning="Keep this manual until an authorized capture path exists.",
                    choice_type="START_GUIDED_CAPTURE",
                    receipt_effect="creates guided capture path receipt target",
                    proof_effect="proof still requires protected evidence path",
                    workflow_state_effect="routes to guided capture candidate later",
                    quieting_effect="automation prompt can quiet behind manual path later",
                    surface_update_effect="shows guided capture candidate",
                    creates_guided_capture_path=True,
                    next_safe_move="Model manual capture path target only.",
                ),
                _choice(
                    "build_automation_path",
                    label="Build automation path later",
                    human_meaning="Treat Coupa/PO lookup as a future automation candidate.",
                    choice_type="START_GUIDED_CAPTURE",
                    receipt_effect="creates automation candidate receipt target",
                    proof_effect="no portal proof is read or claimed",
                    workflow_state_effect="routes to future-gated automation feasibility lane",
                    quieting_effect="keeps execution blocked while feasibility is modeled",
                    surface_update_effect="shows automation candidate state",
                    creates_automation_candidate=True,
                    next_safe_move="Model automation candidate only; do not access Coupa.",
                ),
                _choice(
                    "reject_automation_path",
                    label="Keep it manual",
                    human_meaning="Do not pursue automation for this path.",
                    choice_type="REJECT_THIS",
                    receipt_effect="creates rejection receipt target",
                    proof_effect="automation candidate rejected, not proof changed",
                    workflow_state_effect="keeps manual fallback",
                    quieting_effect="can quiet automation candidate after receipt writer exists",
                    surface_update_effect="shows manual-only state",
                    next_safe_move="Model rejection target only.",
                ),
            ),
        ),
    )


def default_solve_paths() -> tuple[OperatorSolvePath, ...]:
    return (
        OperatorSolvePath(
            solve_path_id="capital_hilton_invoice_solve_path",
            display_title="Capital Hilton Invoice Solve Path",
            world="Finance",
            lane="capital_hilton",
            actor="Cassandra",
            work_mode_type="PROOF_WORK_MODE",
            issue_classification_ref="capital_hilton_invoice_issue",
            source_machine_state_refs=(
                "generated/read_models/operator_work_mode_schema_bandwidth_policy.json",
                "generated/read_models/capital_hilton_answer_candidate_receipt.json",
                "generated/read_models/capital_hilton_proof_quieting_progress_state.json",
            ),
            deterministic_context_refs=(PROMPT_1_READ_MODEL_REF, "capital_hilton_invoice_work_mode"),
            operator_bandwidth_default="LOW_BANDWIDTH",
            low_bandwidth_move="Pick what is true about the invoice.",
            normal_bandwidth_explanation=(
                "OpenClaw has candidate invoice facts. Your choices tell the system what to treat as "
                "operator-confirmed, what needs proof, and what should happen next."
            ),
            high_bandwidth_proof_refs=(
                "generated/read_models/capital_hilton_answer_candidate_receipt.json",
                "generated/read_models/capital_hilton_proof_quieting_progress_state.json",
            ),
            debug_detail_refs=(
                "operator_work_mode_schema_bandwidth_policy",
                "generated/read_models/operator_work_mode_schema_bandwidth_policy.json",
                "generated/read_models/operator_work_mode_schema_bandwidth_policy_OPERATOR.md",
            ),
            current_decision_node_id="confirm_performance_dates",
            visible_steps=("confirm_performance_dates", "confirm_rate", "confirm_invoice_ready_later"),
            quieted_steps=(),
            blocked_steps=("invoice_generation", "approval_submission", "email_send", "Coupa/browser access"),
            proof_detail_refs=("protected finance proof metadata refs only",),
            automation_candidate_refs=("capital_hilton_coupa_po_retrieval_automation_candidate",),
            approval_refs=("capital_hilton_send_approval_gate",),
            next_safe_move="Show the performance-date decision node without writing an answer.",
        ),
        OperatorSolvePath(
            solve_path_id="check_engine_diagnostic_solve_path",
            display_title="Check Engine Diagnostic Solve Path",
            world="System",
            lane="check_engine",
            actor="Chief",
            work_mode_type="REPAIR_DIAGNOSTIC_WORK_MODE",
            issue_classification_ref="developer_system_repair_issue",
            source_machine_state_refs=("generated/read_models/chief_check_engine_diagnostic_package.json",),
            deterministic_context_refs=(PROMPT_1_READ_MODEL_REF, "check_engine_diagnostic_work_mode"),
            operator_bandwidth_default="NORMAL_BANDWIDTH",
            low_bandwidth_move="Check what is actually broken.",
            normal_bandwidth_explanation="The diagnostic path should show evidence before any repair path exists.",
            high_bandwidth_proof_refs=("generated/read_models/chief_check_engine_diagnostic_package.json",),
            debug_detail_refs=("generated/read_models/chief_test_harness_cross_off_receipt_contract.json",),
            current_decision_node_id="check_engine_actual_breakage",
            visible_steps=("check_engine_actual_breakage",),
            quieted_steps=(),
            blocked_steps=("repair_execution", "runtime_dispatch", "tool_execution"),
            proof_detail_refs=("diagnostic receipt refs",),
            automation_candidate_refs=(),
            approval_refs=(),
            next_safe_move="Classify broken/noisy/needs-check without running repair.",
        ),
        OperatorSolvePath(
            solve_path_id="chief_terrain_reconciliation_solve_path",
            display_title="Chief Terrain Reconciliation Solve Path",
            world="System",
            lane="work_terrain",
            actor="Chief",
            work_mode_type="TERRAIN_RECONCILIATION_WORK_MODE",
            issue_classification_ref="terrain_reconciliation_issue",
            source_machine_state_refs=("generated/read_models/openclaw_work_terrain_gap_detector.json",),
            deterministic_context_refs=(PROMPT_1_READ_MODEL_REF, "chief_terrain_reconciliation_work_mode"),
            operator_bandwidth_default="NORMAL_BANDWIDTH",
            low_bandwidth_move="Pick what should stay current.",
            normal_bandwidth_explanation="Terrain decisions should classify current, stale, overlap, or source gap without rewriting files.",
            high_bandwidth_proof_refs=("generated/read_models/openclaw_work_terrain_gap_detector.json",),
            debug_detail_refs=("generated/read_models/openclaw_work_terrain_reconciliation_batch_manifest.json",),
            current_decision_node_id="chief_terrain_currentness",
            visible_steps=("chief_terrain_currentness",),
            quieted_steps=(),
            blocked_steps=("file_move", "file_delete", "source_rewrite", "stable_map_refresh"),
            proof_detail_refs=("terrain source refs",),
            automation_candidate_refs=(),
            approval_refs=(),
            next_safe_move="Classify currentness without mutating sources.",
        ),
        OperatorSolvePath(
            solve_path_id="security_delta_solve_path",
            display_title="Security Delta Solve Path",
            world="System",
            lane="security_delta",
            actor="Guardian",
            work_mode_type="DECISION_WORK_MODE",
            issue_classification_ref="security_delta_review_issue",
            source_machine_state_refs=("generated/read_models/security_delta_review_contract.json",),
            deterministic_context_refs=(PROMPT_1_READ_MODEL_REF, "security_delta_review_work_mode"),
            operator_bandwidth_default="LOW_BANDWIDTH",
            low_bandwidth_move="Decide if this needs security review.",
            normal_bandwidth_explanation="Security choices classify review need while keeping all new authority blocked.",
            high_bandwidth_proof_refs=("generated/read_models/security_pass_contract.json",),
            debug_detail_refs=("generated/read_models/security_delta_review_contract.json",),
            current_decision_node_id="security_delta_review_needed",
            visible_steps=("security_delta_review_needed",),
            quieted_steps=(),
            blocked_steps=("authority_grant", "approval_submission", "runtime_execution"),
            proof_detail_refs=("security pass summary refs",),
            automation_candidate_refs=(),
            approval_refs=("guardian_draft_approval_request_contract",),
            next_safe_move="Classify security review need without granting authority.",
        ),
        OperatorSolvePath(
            solve_path_id="coupa_po_automation_candidate_solve_path",
            display_title="Coupa / PO Automation Candidate Solve Path",
            world="Finance",
            lane="capital_hilton",
            actor="Chief",
            work_mode_type="AUTOMATION_CANDIDATE_WORK_MODE",
            issue_classification_ref="automation_candidate_issue",
            source_machine_state_refs=(
                "generated/read_models/capital_hilton_coupa_po_retrieval_automation_candidate.json",
            ),
            deterministic_context_refs=(PROMPT_1_READ_MODEL_REF, "automation_candidate_issue"),
            operator_bandwidth_default="NORMAL_BANDWIDTH",
            low_bandwidth_move="Choose manual capture now or build the automation path.",
            normal_bandwidth_explanation="The Coupa/PO path can be manual now or future-gated automation later; neither runs here.",
            high_bandwidth_proof_refs=("generated/read_models/capital_hilton_coupa_po_retrieval_automation_candidate.json",),
            debug_detail_refs=("generated/read_models/tool_adapter_receipt_contract.json",),
            current_decision_node_id="coupa_po_manual_or_automation",
            visible_steps=("coupa_po_manual_or_automation",),
            quieted_steps=(),
            blocked_steps=("Coupa access", "browser automation", "credential handling", "automation execution"),
            proof_detail_refs=("automation readiness refs",),
            automation_candidate_refs=("capital_hilton_coupa_po_retrieval_automation_candidate",),
            approval_refs=(),
            next_safe_move="Classify manual versus future automation without accessing Coupa.",
        ),
    )


def default_receipt_targets() -> tuple[OperatorChoiceReceiptTarget, ...]:
    return (
        OperatorChoiceReceiptTarget(
            receipt_target_id="capital_hilton_performance_dates_confirmation_target",
            receipt_type="OPERATOR_CONFIRMATION_RECEIPT",
            would_write_to="future_sqlite_receipt_writer",
            canonical_session_ref="capital_hilton_invoice_solve_path",
            affected_proof_item_refs=("performance_dates",),
            affected_step_refs=("confirm_performance_dates", "confirm_rate"),
            affected_surfaces=("capital_hilton_invoice_solve_path", "future_workflow_session_projection"),
            state_change_summary=(
                "Would mark dates operator-confirmed and move to confirm_rate, without proving external truth."
            ),
            requires_sqlite_writer=True,
            requires_guardian_review=False,
            requires_operator_final_authority=True,
            would_quiet_step=True,
            would_create_discovery_substep=False,
            would_create_guided_capture_path=False,
            would_create_automation_candidate=False,
            current_write_authority_granted=False,
            next_safe_move="Preview receipt target only; no write.",
        ),
        OperatorChoiceReceiptTarget(
            receipt_target_id="capital_hilton_performance_date_correction_target",
            receipt_type="OPERATOR_CORRECTION_RECEIPT",
            would_write_to="future_sqlite_receipt_writer",
            canonical_session_ref="capital_hilton_invoice_solve_path",
            affected_proof_item_refs=("performance_dates",),
            affected_step_refs=("confirm_performance_dates", "correct_performance_date"),
            affected_surfaces=("capital_hilton_invoice_solve_path",),
            state_change_summary="Would record corrected date candidate after follow-up.",
            requires_sqlite_writer=True,
            requires_guardian_review=False,
            requires_operator_final_authority=True,
            would_quiet_step=False,
            would_create_discovery_substep=False,
            would_create_guided_capture_path=True,
            would_create_automation_candidate=False,
            current_write_authority_granted=False,
            next_safe_move="Open correction follow-up only.",
        ),
        OperatorChoiceReceiptTarget(
            receipt_target_id="capital_hilton_performance_date_addition_target",
            receipt_type="OPERATOR_CORRECTION_RECEIPT",
            would_write_to="future_sqlite_receipt_writer",
            canonical_session_ref="capital_hilton_invoice_solve_path",
            affected_proof_item_refs=("performance_dates",),
            affected_step_refs=("confirm_performance_dates", "add_performance_date"),
            affected_surfaces=("capital_hilton_invoice_solve_path",),
            state_change_summary="Would record added date candidate and mark recalculation possibly needed later.",
            requires_sqlite_writer=True,
            requires_guardian_review=False,
            requires_operator_final_authority=True,
            would_quiet_step=False,
            would_create_discovery_substep=False,
            would_create_guided_capture_path=True,
            would_create_automation_candidate=False,
            current_write_authority_granted=False,
            next_safe_move="Open add-date follow-up only.",
        ),
        OperatorChoiceReceiptTarget(
            receipt_target_id="capital_hilton_date_discovery_substep_target",
            receipt_type="DISCOVERY_SUBSTEP_RECEIPT",
            would_write_to="future_sqlite_receipt_writer",
            canonical_session_ref="capital_hilton_invoice_solve_path",
            affected_proof_item_refs=("performance_dates",),
            affected_step_refs=("confirm_performance_dates", "date_discovery_needed"),
            affected_surfaces=("capital_hilton_invoice_solve_path", "future_discovery_lane"),
            state_change_summary="Would create a date discovery substep and keep workflow alive.",
            requires_sqlite_writer=True,
            requires_guardian_review=False,
            requires_operator_final_authority=True,
            would_quiet_step=False,
            would_create_discovery_substep=True,
            would_create_guided_capture_path=False,
            would_create_automation_candidate=False,
            current_write_authority_granted=False,
            next_safe_move="Model discovery target only.",
        ),
        OperatorChoiceReceiptTarget(
            receipt_target_id="check_engine_diagnostic_classification_target",
            receipt_type="OPERATOR_CONFIRMATION_RECEIPT",
            would_write_to="future_sqlite_receipt_writer",
            canonical_session_ref="check_engine_diagnostic_solve_path",
            affected_proof_item_refs=("diagnostic_evidence",),
            affected_step_refs=("check_engine_actual_breakage",),
            affected_surfaces=("check_engine_diagnostic_solve_path",),
            state_change_summary="Would classify diagnostic state without executing repair.",
            requires_sqlite_writer=True,
            requires_guardian_review=False,
            requires_operator_final_authority=True,
            would_quiet_step=False,
            would_create_discovery_substep=False,
            would_create_guided_capture_path=False,
            would_create_automation_candidate=False,
            current_write_authority_granted=False,
            next_safe_move="Model diagnostic classification target only.",
        ),
        OperatorChoiceReceiptTarget(
            receipt_target_id="chief_terrain_reconciliation_target",
            receipt_type="OPERATOR_MEMORY_CANDIDATE_RECEIPT",
            would_write_to="future_sqlite_receipt_writer",
            canonical_session_ref="chief_terrain_reconciliation_solve_path",
            affected_proof_item_refs=("terrain_source_refs",),
            affected_step_refs=("chief_terrain_currentness",),
            affected_surfaces=("chief_terrain_reconciliation_solve_path",),
            state_change_summary="Would classify terrain currentness without rewriting source files.",
            requires_sqlite_writer=True,
            requires_guardian_review=False,
            requires_operator_final_authority=True,
            would_quiet_step=False,
            would_create_discovery_substep=False,
            would_create_guided_capture_path=False,
            would_create_automation_candidate=False,
            current_write_authority_granted=False,
            next_safe_move="Model terrain classification target only.",
        ),
        OperatorChoiceReceiptTarget(
            receipt_target_id="security_delta_review_classification_target",
            receipt_type="OPERATOR_CONFIRMATION_RECEIPT",
            would_write_to="future_sqlite_receipt_writer",
            canonical_session_ref="security_delta_solve_path",
            affected_proof_item_refs=("security_delta_review",),
            affected_step_refs=("security_delta_review_needed",),
            affected_surfaces=("security_delta_solve_path", "future_security_delta_lane"),
            state_change_summary="Would classify security-review need without approving any authority.",
            requires_sqlite_writer=True,
            requires_guardian_review=True,
            requires_operator_final_authority=True,
            would_quiet_step=False,
            would_create_discovery_substep=False,
            would_create_guided_capture_path=False,
            would_create_automation_candidate=False,
            current_write_authority_granted=False,
            next_safe_move="Model security review target only.",
        ),
        OperatorChoiceReceiptTarget(
            receipt_target_id="coupa_po_automation_candidate_choice_target",
            receipt_type="AUTOMATION_CANDIDATE_RECEIPT",
            would_write_to="future_sqlite_receipt_writer",
            canonical_session_ref="coupa_po_automation_candidate_solve_path",
            affected_proof_item_refs=("coupa_po_payment_reference_metadata",),
            affected_step_refs=("coupa_po_manual_or_automation",),
            affected_surfaces=("coupa_po_automation_candidate_solve_path", "future_automation_readiness_lane"),
            state_change_summary="Would classify manual capture versus future-gated automation without accessing Coupa.",
            requires_sqlite_writer=True,
            requires_guardian_review=True,
            requires_operator_final_authority=True,
            would_quiet_step=False,
            would_create_discovery_substep=False,
            would_create_guided_capture_path=True,
            would_create_automation_candidate=True,
            current_write_authority_granted=False,
            next_safe_move="Model automation candidate target only.",
        ),
        OperatorChoiceReceiptTarget(
            receipt_target_id="unknown_fail_closed_receipt_target",
            receipt_type="UNKNOWN_FAIL_CLOSED",
            would_write_to="none_currently",
            canonical_session_ref="unknown",
            affected_proof_item_refs=(),
            affected_step_refs=("unknown",),
            affected_surfaces=("operator_attention",),
            state_change_summary="Unknown choice shapes remain blocked until classified.",
            requires_sqlite_writer=True,
            requires_guardian_review=True,
            requires_operator_final_authority=True,
            would_quiet_step=False,
            would_create_discovery_substep=False,
            would_create_guided_capture_path=False,
            would_create_automation_candidate=False,
            current_write_authority_granted=False,
            next_safe_move="Fail closed.",
        ),
    )


def lm_rendering_boundary() -> SolvePathLMRenderingBoundary:
    return SolvePathLMRenderingBoundary(
        lm_may_rephrase=True,
        lm_may_generate_plain_language=True,
        lm_may_create_new_choices=False,
        lm_may_decide_authority=False,
        lm_may_mark_proof_complete=False,
        lm_may_approve_action=False,
        lm_may_hide_blockers=False,
        deterministic_choice_source_required=True,
        rendered_output_status="read_model_or_preview_packet_before_app_display",
    )


def build_operator_solve_path_decision_node_contract(
    *,
    repo_root: str | Path = ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    del repo_root
    solve_paths = [asdict(item) for item in default_solve_paths()]
    decision_nodes = [asdict(item) for item in default_decision_nodes()]
    receipt_targets = [asdict(item) for item in default_receipt_targets()]
    boundary = asdict(lm_rendering_boundary())
    all_choices = [choice for node in decision_nodes for choice in node["choices"]]
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "contract_id": f"{READ_MODEL_ID}_v0",
        "generated_at": _generated_at(generated_at),
        "contract_status": CONTRACT_STATUS,
        "core_doctrine": {
            "operator_doctrine": "Pick what is true. OpenClaw handles the consequences.",
            "operator_should_not_manage_database_paths_state_or_cleanup": True,
            "operator_makes_next_true_choice": True,
            "system_models_receipt_step_surface_and_blocker_effects": True,
            "machine_contracts_are_not_default_operator_surface": True,
            "proof_and_debug_refs_are_secondary": True,
            "low_bandwidth_one_next_move_default": True,
        },
        "relationship_to_prompt_1": {
            "extends_read_model_id": "operator_work_mode_schema_bandwidth_policy",
            "read_model_ref": PROMPT_1_READ_MODEL_REF,
            "operator_markdown_ref": PROMPT_1_OPERATOR_REF,
            "does_not_duplicate_prompt_1": True,
        },
        "operator_solve_path_schema": {
            "structure": "OperatorSolvePath",
            "required_fields": list(REQUIRED_SOLVE_PATH_FIELDS),
            "unknown_or_missing_result": "UNKNOWN_FAIL_CLOSED",
        },
        "operator_decision_node_schema": {
            "structure": "OperatorDecisionNode",
            "required_fields": list(REQUIRED_DECISION_NODE_FIELDS),
            "statuses": list(DECISION_NODE_STATUSES),
            "unknown_or_missing_result": "UNKNOWN_FAIL_CLOSED",
        },
        "operator_decision_choice_schema": {
            "structure": "OperatorDecisionChoice",
            "required_fields": list(REQUIRED_DECISION_CHOICE_FIELDS),
            "choice_types": list(CHOICE_TYPES),
            "unknown_or_missing_result": "UNKNOWN_FAIL_CLOSED",
        },
        "operator_choice_receipt_target_schema": {
            "structure": "OperatorChoiceReceiptTarget",
            "required_fields": list(REQUIRED_RECEIPT_TARGET_FIELDS),
            "receipt_types": list(RECEIPT_TYPES),
            "models_receipt_targets_only": True,
            "writes_receipts_now": False,
        },
        "decision_node_statuses": list(DECISION_NODE_STATUSES),
        "choice_types": list(CHOICE_TYPES),
        "receipt_types": list(RECEIPT_TYPES),
        "solve_paths": solve_paths,
        "solve_paths_by_id": {item["solve_path_id"]: item for item in solve_paths},
        "decision_nodes": decision_nodes,
        "decision_nodes_by_id": {item["decision_node_id"]: item for item in decision_nodes},
        "decision_choices": all_choices,
        "decision_choices_by_id": {item["choice_id"]: item for item in all_choices},
        "receipt_targets": receipt_targets,
        "receipt_targets_by_id": {item["receipt_target_id"]: item for item in receipt_targets},
        "lm_rendering_boundary": boundary,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "hard_rule": {
            "read_model_only": True,
            "does_not_implement_live_ui": True,
            "does_not_implement_persistence": True,
            "does_not_write_actual_answers": True,
            "does_not_create_mac_buttons": True,
            "does_not_refresh_stable_map": True,
            "may_write_receipts_now": False,
            "may_execute": False,
            "may_grant_authority": False,
        },
        "machine_proof": {
            "solve_path_model_present": True,
            "decision_node_model_present": True,
            "decision_choice_model_present": True,
            "receipt_target_model_present": True,
            "solve_path_count": len(solve_paths),
            "decision_node_count": len(decision_nodes),
            "decision_choice_count": len(all_choices),
            "receipt_target_count": len(receipt_targets),
            "capital_hilton_example_present": any(
                item["solve_path_id"] == "capital_hilton_invoice_solve_path" for item in solve_paths
            ),
            "confirm_performance_dates_node_present": any(
                item["decision_node_id"] == "confirm_performance_dates" for item in decision_nodes
            ),
            "all_decision_node_statuses_present": len(DECISION_NODE_STATUSES) == 13,
            "all_choice_types_present": len(CHOICE_TYPES) == 12,
            "all_receipt_types_present": len(RECEIPT_TYPES) == 10,
            "low_bandwidth_moves_present": all(item["low_bandwidth_move"] for item in solve_paths),
            "machine_contracts_not_default_surface": True,
            "receipt_targets_modeled_not_written": all(
                item["current_write_authority_granted"] is False for item in receipt_targets
            ),
            "current_write_authority_false": True,
            "lm_cannot_create_choices": boundary["lm_may_create_new_choices"] is False,
            "lm_cannot_decide_authority": boundary["lm_may_decide_authority"] is False,
            "lm_cannot_mark_proof_complete": boundary["lm_may_mark_proof_complete"] is False,
            "lm_cannot_approve_action": boundary["lm_may_approve_action"] is False,
            "lm_cannot_hide_blockers": boundary["lm_may_hide_blockers"] is False,
            "all_authority_flags_false": _all_authority_flags_false(),
            "action_authority_granted": False,
            "credentials_or_secrets_included": False,
            "raw_private_bodies_included": False,
            "content_hash": None,
        },
    }
    payload["machine_proof"]["content_hash"] = _content_hash(payload)
    return payload


def format_operator_solve_path_markdown(payload: dict[str, Any]) -> str:
    proof = payload["machine_proof"]
    capital = payload["decision_nodes_by_id"]["confirm_performance_dates"]
    lines = [
        "# Operator Solve Path / Decision Node Contract v0",
        "",
        "## ELIWINSHIP Summary",
        "",
        "A solve path is the plain-language route through a piece of work. It does not ask Winship to manage the database, file paths, state propagation, or cleanup. It asks for the next true choice.",
        "",
        "A decision node is one step in that route. It says what OpenClaw thinks, why it matters, what Winship can choose, and what would happen after each choice. The doctrine is simple: pick what is true; OpenClaw handles the consequences.",
        "",
        "This prompt still does not build UI, persist answers, write receipts, or enable actions. It only models the deterministic packets a later app surface and writer lane can use.",
        "",
        "## Why This Makes The App Easier",
        "",
        "- Winship sees one human move instead of proof slots and machine-contract walls.",
        "- Each choice has a known consequence before anything is written.",
        "- I don't know is not a dead end; it creates a discovery substep target and keeps the workflow alive.",
        "- Correction opens a follow-up node instead of making Winship solve state routing manually.",
        "- Receipt targets are modeled now, but no receipt is written yet.",
        "",
        "## Solve Paths",
        "",
    ]
    for path in payload["solve_paths"]:
        lines.append(f"- `{path['solve_path_id']}`: {path['low_bandwidth_move']}")
    lines.extend(
        [
            "",
            "## Capital Hilton Date Node",
            "",
            f"- Prompt: {capital['plain_language_prompt']}",
            f"- System thinks: {', '.join(capital['what_system_thinks'])}.",
            "- Choices:",
        ]
    )
    for choice in capital["choices"]:
        lines.append(f"  - `{choice['choice_id']}`: {choice['label']} -> {choice['workflow_state_effect']}")
    lines.extend(
        [
            "",
            "Both dates are right would create an operator confirmation receipt target and move the workflow toward rate confirmation. It does not prove external truth, and final send proof may still be needed.",
            "",
            "One date is wrong and add another date open follow-up nodes. I don't know and needs discovery create discovery substep targets. This date set is wrong opens a correction/rejection path and requires a reason before quieting.",
            "",
            "## LM Boundary",
            "",
            "- LM may rephrase and generate plain language from deterministic packets.",
            "- LM may not create choices, decide authority, mark proof complete, approve action, or hide blockers.",
            "- Choices must come from deterministic contract state.",
            "",
            "## Still Blocked",
            "",
            "- No answer persistence, SQLite answer writes, receipt writes, workflow execution, automation execution, approval submission, invoice generation, email/Telegram send, browser/account/Coupa/Gmail/calendar access, credential handling, model/tool/agent/runtime/queue execution, ledger writes, file cleanup, stable-map refresh, Mac UI implementation, or authority grant.",
            "",
            "## Machine Proof Summary",
            "",
            f"- Solve paths: `{proof['solve_path_count']}`.",
            f"- Decision nodes: `{proof['decision_node_count']}`.",
            f"- Decision choices: `{proof['decision_choice_count']}`.",
            f"- Receipt targets: `{proof['receipt_target_count']}`.",
            f"- Receipt targets modeled, not written: `{str(proof['receipt_targets_modeled_not_written']).lower()}`.",
            f"- All authority flags false: `{str(proof['all_authority_flags_false']).lower()}`.",
            f"- Content hash: `{proof['content_hash']}`.",
        ]
    )
    return "\n".join(lines) + "\n"


def export_operator_solve_path_decision_node_contract(
    *,
    repo_root: str | Path = ROOT,
    export_root: str | Path = DEFAULT_EXPORT_ROOT,
    generated_at: str | None = None,
) -> SolvePathExportResult:
    payload = build_operator_solve_path_decision_node_contract(repo_root=repo_root, generated_at=generated_at)
    root = Path(export_root)
    if not root.is_absolute():
        root = Path(repo_root) / root
    root.mkdir(parents=True, exist_ok=True)
    json_path = root / JSON_EXPORT_NAME
    operator_path = root / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(format_operator_solve_path_markdown(payload), encoding="utf-8")
    return SolvePathExportResult(
        schema_version=SCHEMA_VERSION,
        json_path=json_path.as_posix(),
        operator_path=operator_path.as_posix(),
        solve_path_count=len(payload["solve_paths"]),
        decision_node_count=len(payload["decision_nodes"]),
        receipt_target_count=len(payload["receipt_targets"]),
        action_authority_granted=False,
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export Operator Solve Path / Decision Node Contract.")
    parser.add_argument("--repo-root", default=ROOT.as_posix())
    parser.add_argument("--export-root", default=DEFAULT_EXPORT_ROOT.as_posix())
    parser.add_argument("--format", choices=("summary", "json", "operator"), default="operator")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    result = export_operator_solve_path_decision_node_contract(
        repo_root=args.repo_root,
        export_root=args.export_root,
    )
    summary = {
        "schema_version": result.schema_version,
        "json_path": result.json_path,
        "operator_path": result.operator_path,
        "solve_path_count": result.solve_path_count,
        "decision_node_count": result.decision_node_count,
        "receipt_target_count": result.receipt_target_count,
        "action_authority_granted": result.action_authority_granted,
    }
    if args.format in {"summary", "json"}:
        print(stable_json(summary), end="")
    else:
        print("Operator Solve Path / Decision Node Contract exported")
        print(f"- JSON: `{result.json_path}`")
        print(f"- Operator: `{result.operator_path}`")
    return 0


__all__ = [
    "AUTHORITY_BOUNDARY",
    "CHOICE_TYPES",
    "DECISION_NODE_STATUSES",
    "JSON_EXPORT_NAME",
    "OPERATOR_EXPORT_NAME",
    "READ_MODEL_ID",
    "RECEIPT_TYPES",
    "REQUIRED_DECISION_CHOICE_FIELDS",
    "REQUIRED_DECISION_NODE_FIELDS",
    "REQUIRED_RECEIPT_TARGET_FIELDS",
    "REQUIRED_SOLVE_PATH_FIELDS",
    "SCHEMA_VERSION",
    "build_operator_solve_path_decision_node_contract",
    "default_decision_nodes",
    "default_receipt_targets",
    "default_solve_paths",
    "export_operator_solve_path_decision_node_contract",
    "format_operator_solve_path_markdown",
    "lm_rendering_boundary",
    "stable_json",
]
