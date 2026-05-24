"""Conversational Workflow Memory Contract v0.

This deterministic read-model defines how OpenClaw can turn operator
conversation into reviewable procedure memory and future governed run plans.
It is generic: Capital Hilton is included only as the first proof example.

No live chat parser, model call, procedure memory write, workflow run, agent
dispatch, Cassandra draft, Guardian approval, email draft/send, Coupa access or
submit, invoice generation, attachment, payment tracking write, credential
handling, raw-body ingestion, network access, or external action occurs here.
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

SCHEMA_VERSION = "conversational_workflow_memory_contract_v0"
READ_MODEL_ID = "conversational_workflow_memory_contract"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
OPERATOR_EXPORT_NAME = f"{READ_MODEL_ID}_OPERATOR.md"
CONTRACT_STATUS = "DETERMINISTIC_NON_EXECUTING_CONVERSATIONAL_WORKFLOW_MEMORY_CONTRACT"

RUN_STATES = (
    "DRAFT_PROPOSED",
    "OPERATOR_REVIEW_REQUIRED",
    "STORED_PROCEDURE_READY",
    "RUN_REQUESTED",
    "PREPARE_ARTIFACTS",
    "DRAFT_READY_FOR_REVIEW",
    "GUARDIAN_APPROVAL_REQUIRED",
    "OPERATOR_APPROVAL_REQUIRED",
    "SEND_OR_SUBMIT_GATED",
    "COMPLETION_PROOF_REQUIRED",
    "COMPLETION_CONFIRMED",
    "BLOCKED_NEEDS_PROOF",
    "BLOCKED_EXTERNAL_AUTHORITY",
    "UNKNOWN_FAIL_CLOSED",
)

GENERIC_REQUIRED_ROLES = (
    "operator",
    "drafting_agent",
    "validation_agent",
    "protected_evidence_agent",
    "approval_agent",
    "artifact_generation_agent",
    "post_office_handoff",
    "final_readback_agent",
)

CAPITAL_HILTON_BLOCK_LABELS = (
    "Confirm performance dates",
    "Confirm rate",
    "Generate/update Excel-branded companion invoice PDF",
    "Confirm PO/Coupa payment rail",
    "Confirm Coupa supplier-portal invoice from PO",
    "Confirm invoice destination/contact: Annette candidate",
    "Prepare email draft to Annette",
    "Attach Excel-generated PDF invoice",
    "Guardian approval request",
    "Operator approval",
    "Send email",
    "Submit/verify Coupa invoice if required and gated",
    "Save dated invoice artifact",
    "Record sent/payment tracking state",
    "Completion proof readback",
)

CAPITAL_HILTON_DATES = ("2026-05-08", "2026-05-15", "2026-05-22", "2026-05-29")
CAPITAL_HILTON_RATE = {"amount": 400, "currency": "USD", "unit": "show", "display": "$400/show"}
CAPITAL_HILTON_SUBTOTAL = {"amount": 1600, "currency": "USD", "calculation": "4 shows x $400/show"}
CAPITAL_HILTON_PREVIEW_HASH = (
    "sha256:a135264f8df31f762170ea53f50d74d44d08cfe1ee95dfc8fd318fad178970fc"
)

REQUIRED_INTAKE_FIELDS = (
    "intake_id",
    "workflow_ref",
    "workflow_type",
    "client_ref",
    "tenant_ref",
    "world_ref",
    "lane_ref",
    "operator_narrative",
    "narrative_privacy_class",
    "raw_narrative_allowed_in_normal_read_model",
    "sanitized_summary",
    "parsed_candidate_status",
    "operator_review_required",
    "proposed_chain_ref",
    "next_safe_move",
)

REQUIRED_PROPOSAL_FIELDS = (
    "proposal_id",
    "source_intake_ref",
    "workflow_type",
    "proposed_blocks",
    "proposed_sequence",
    "non_serial_blocks",
    "dependencies",
    "gates",
    "unknowns",
    "proof_requirements",
    "operator_questions",
    "reusable_fact_candidates",
    "protected_value_candidates",
    "review_status",
    "elioperator_summary",
    "next_safe_move",
)

REQUIRED_PROCEDURE_FIELDS = (
    "procedure_id",
    "procedure_name",
    "workflow_type",
    "client_ref",
    "tenant_ref",
    "trigger_phrases",
    "stored_workflow_summary",
    "stored_blocks",
    "reusable_facts",
    "required_inputs",
    "required_artifacts",
    "required_gates",
    "agent_roles",
    "authority_boundaries",
    "proof_requirements",
    "privacy_boundaries",
    "update_policy",
    "last_run_ref",
    "last_successful_completion_ref",
    "next_safe_move",
)

REQUIRED_RUN_PLAN_FIELDS = (
    "run_id",
    "procedure_ref",
    "requested_by",
    "run_goal",
    "current_state",
    "run_blocks",
    "dependencies",
    "gates",
    "runnable_now",
    "blocked_now",
    "required_operator_confirmations",
    "required_guardian_approvals",
    "required_artifacts",
    "required_external_adapters",
    "readback_plan",
    "completion_condition",
    "next_safe_move",
)

REQUIRED_ROLE_ROUTING_FIELDS = (
    "routing_id",
    "workflow_run_ref",
    "roles",
    "actor_candidates",
    "role_boundaries",
    "package_requirements",
    "handoff_requirements",
    "review_requirements",
    "no_hardcoded_persona_requirement",
    "next_safe_move",
)

REQUIRED_ARTIFACT_PROOF_FIELDS = (
    "plan_id",
    "workflow_run_ref",
    "required_artifacts",
    "optional_artifacts",
    "proof_bullets",
    "missing_proofs",
    "protected_refs",
    "artifact_hash_requirements",
    "completion_proof_requirements",
    "next_safe_move",
)

REQUIRED_COMPLETION_FIELDS = (
    "completion_id",
    "workflow_run_ref",
    "status_label",
    "headline",
    "proof_bullets",
    "unresolved_items",
    "state_updates",
    "next_run_memory_update",
    "safe_display_summary",
    "elioperator_summary",
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

REQUIRED_ELIOPERATOR_FIELDS = (
    "report_id",
    "plain_summary",
    "what_this_enables",
    "what_this_does_not_do_yet",
    "why_chat_drives_workflow",
    "how_operator_review_works",
    "how_procedure_memory_works",
    "how_governed_run_works",
    "why_external_actions_remain_gated",
    "next_safe_move",
)

BUILDER_BLOCKER_TYPES = (
    "NARRATIVE_TREATED_AS_TRUTH",
    "PROCEDURE_MEMORY_USED_AS_AUTHORITY",
    "RUN_WITHOUT_OPERATOR_REVIEW",
    "EXTERNAL_ACTION_WITHOUT_GATE",
    "SEND_WITHOUT_GUARDIAN_APPROVAL",
    "SUBMIT_WITHOUT_PROOF",
    "ATTACHMENT_WITHOUT_ARTIFACT_HASH",
    "COMPLETION_WITHOUT_RECEIPTS",
    "RAW_PII_IN_NORMAL_READMODEL",
    "AGENT_PERSONA_HARDCODED_IN_CORE",
    "MACHINE_CONTRACT_VISIBLE_TO_OPERATOR",
    "UNKNOWN_FAIL_CLOSED",
)

LIVE_AUTHORITY_BOUNDARY = {
    "live_chat_parser_allowed": False,
    "live_model_call_allowed": False,
    "live_procedure_memory_write_allowed": False,
    "live_workflow_run_allowed": False,
    "live_agent_dispatch_allowed": False,
    "live_cassandra_draft_allowed": False,
    "live_guardian_approval_allowed": False,
    "live_email_draft_allowed": False,
    "live_email_send_allowed": False,
    "live_coupa_access_allowed": False,
    "live_coupa_submit_allowed": False,
    "live_invoice_generation_allowed": False,
    "live_attachment_allowed": False,
    "live_payment_tracking_write_allowed": False,
    "live_external_action_allowed": False,
    "credential_handling_allowed": False,
    "raw_body_ingestion_allowed": False,
    "browser_automation_allowed": False,
    "gmail_access_allowed": False,
    "telegram_send_allowed": False,
    "approval_submission_allowed": False,
    "network_operation_allowed": False,
    "mission_control_swift_change_allowed": False,
    "mac_sync_import_allowed": False,
    "git_push_pull_fetch_allowed": False,
    "file_cleanup_archive_allowed": False,
    "model_call_allowed": False,
    "agent_activation_allowed": False,
    "tool_execution_allowed": False,
    "queue_execution_allowed": False,
    "runtime_dispatch_allowed": False,
}

RELATIONSHIP_CANDIDATES = (
    "workflow_block_intent_live_draft_contract.py",
    "operator_question_assist_scope_expansion_contract.py",
    "cross_surface_artifact_handoff_registry_contract.py",
    "cross_surface_handoff_registry_metadata_alignment.py",
    "cross_lane_reusable_block_registry_contract.py",
    "agent_conversation_handoff_step_packet_contract.py",
    "agent_execution_packet_compiler_contract.py",
    "bridge_routing_operator_attention_contract.py",
    "capital_hilton_delivery_facts_capture_writer.py",
    "capital_hilton_delivery_facts_capture_bridge.py",
    "capital_hilton_invoice_artifact_generator.py",
    "guardian_protected_access_gate_spec.py",
    "protected_evidence_reference_receipt.py",
    "capital_hilton_guardian_review_packet.py",
    "openclaw_sensitive_policy.py",
    "business_ops_ledger.py",
)


@dataclass(frozen=True)
class ConversationalWorkflowIntake:
    intake_id: str
    workflow_ref: str
    workflow_type: str
    client_ref: str
    tenant_ref: str
    world_ref: str
    lane_ref: str
    operator_narrative: str
    narrative_privacy_class: str
    raw_narrative_allowed_in_normal_read_model: bool
    sanitized_summary: str
    parsed_candidate_status: str
    operator_review_required: bool
    proposed_chain_ref: str
    next_safe_move: str


@dataclass(frozen=True)
class WorkflowBlockChainProposal:
    proposal_id: str
    source_intake_ref: str
    workflow_type: str
    proposed_blocks: tuple[dict[str, Any], ...]
    proposed_sequence: tuple[str, ...]
    non_serial_blocks: tuple[str, ...]
    dependencies: tuple[dict[str, Any], ...]
    gates: tuple[dict[str, Any], ...]
    unknowns: tuple[str, ...]
    proof_requirements: tuple[str, ...]
    operator_questions: tuple[str, ...]
    reusable_fact_candidates: tuple[dict[str, Any], ...]
    protected_value_candidates: tuple[dict[str, Any], ...]
    review_status: str
    elioperator_summary: str
    next_safe_move: str


@dataclass(frozen=True)
class StoredWorkflowProcedure:
    procedure_id: str
    procedure_name: str
    workflow_type: str
    client_ref: str
    tenant_ref: str
    trigger_phrases: tuple[str, ...]
    stored_workflow_summary: str
    stored_blocks: tuple[str, ...]
    reusable_facts: tuple[dict[str, Any], ...]
    required_inputs: tuple[str, ...]
    required_artifacts: tuple[str, ...]
    required_gates: tuple[str, ...]
    agent_roles: dict[str, Any]
    authority_boundaries: dict[str, Any]
    proof_requirements: tuple[str, ...]
    privacy_boundaries: dict[str, Any]
    update_policy: str
    last_run_ref: str | None
    last_successful_completion_ref: str | None
    next_safe_move: str


@dataclass(frozen=True)
class GovernedWorkflowRunPlan:
    run_id: str
    procedure_ref: str
    requested_by: str
    run_goal: str
    current_state: str
    run_blocks: tuple[str, ...]
    dependencies: tuple[dict[str, Any], ...]
    gates: tuple[dict[str, Any], ...]
    runnable_now: tuple[str, ...]
    blocked_now: tuple[str, ...]
    required_operator_confirmations: tuple[str, ...]
    required_guardian_approvals: tuple[str, ...]
    required_artifacts: tuple[str, ...]
    required_external_adapters: tuple[str, ...]
    readback_plan: tuple[str, ...]
    completion_condition: str
    next_safe_move: str


@dataclass(frozen=True)
class WorkflowRoleRoutingPlan:
    routing_id: str
    workflow_run_ref: str
    roles: tuple[dict[str, Any], ...]
    actor_candidates: dict[str, Any]
    role_boundaries: dict[str, Any]
    package_requirements: tuple[str, ...]
    handoff_requirements: tuple[str, ...]
    review_requirements: tuple[str, ...]
    no_hardcoded_persona_requirement: bool
    next_safe_move: str


@dataclass(frozen=True)
class ArtifactAndProofPlan:
    plan_id: str
    workflow_run_ref: str
    required_artifacts: tuple[dict[str, Any], ...]
    optional_artifacts: tuple[dict[str, Any], ...]
    proof_bullets: tuple[str, ...]
    missing_proofs: tuple[str, ...]
    protected_refs: tuple[dict[str, Any], ...]
    artifact_hash_requirements: tuple[str, ...]
    completion_proof_requirements: tuple[str, ...]
    next_safe_move: str


@dataclass(frozen=True)
class CompletionReadbackContract:
    completion_id: str
    workflow_run_ref: str
    status_label: str
    headline: str
    proof_bullets: tuple[str, ...]
    unresolved_items: tuple[str, ...]
    state_updates: tuple[dict[str, Any], ...]
    next_run_memory_update: str
    safe_display_summary: str
    elioperator_summary: str
    next_safe_move: str


@dataclass(frozen=True)
class ConversationalWorkflowBuilderBlocker:
    blocker_id: str
    blocker_type: str
    condition: str
    severity: str
    elioperator_warning: str
    builder_action_required: str
    fail_closed: bool
    next_safe_move: str


@dataclass(frozen=True)
class ConversationalWorkflowElioperatorReport:
    report_id: str
    plain_summary: str
    what_this_enables: str
    what_this_does_not_do_yet: str
    why_chat_drives_workflow: str
    how_operator_review_works: str
    how_procedure_memory_works: str
    how_governed_run_works: str
    why_external_actions_remain_gated: str
    next_safe_move: str


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def _sha256_payload(payload: Any) -> str:
    return "sha256:" + hashlib.sha256(stable_json(payload).encode("utf-8")).hexdigest()


def _content_hash(payload: dict[str, Any]) -> str:
    clone = json.loads(stable_json(payload))
    clone.get("machine_proof", {}).pop("content_hash", None)
    return _sha256_payload(clone)


def _model_schemas() -> dict[str, Any]:
    return {
        "conversational_workflow_intake": {"required_fields": list(REQUIRED_INTAKE_FIELDS)},
        "workflow_block_chain_proposal": {"required_fields": list(REQUIRED_PROPOSAL_FIELDS)},
        "stored_workflow_procedure": {"required_fields": list(REQUIRED_PROCEDURE_FIELDS)},
        "governed_workflow_run_plan": {"required_fields": list(REQUIRED_RUN_PLAN_FIELDS)},
        "workflow_role_routing_plan": {"required_fields": list(REQUIRED_ROLE_ROUTING_FIELDS)},
        "artifact_and_proof_plan": {"required_fields": list(REQUIRED_ARTIFACT_PROOF_FIELDS)},
        "completion_readback_contract": {"required_fields": list(REQUIRED_COMPLETION_FIELDS)},
        "conversational_workflow_builder_blocker": {"required_fields": list(REQUIRED_BUILDER_BLOCKER_FIELDS)},
        "conversational_workflow_elioperator_report": {"required_fields": list(REQUIRED_ELIOPERATOR_FIELDS)},
    }


def _relationship_inventory() -> dict[str, Any]:
    notes = {
        "workflow_block_intent_live_draft_contract": "draft-intent substrate for conversational proposals before capture",
        "operator_question_assist_scope_expansion_contract": "plain-language question and discovery support",
        "cross_surface_artifact_handoff_registry_contract": "post-office metadata for typed handoffs",
        "cross_surface_handoff_registry_metadata_alignment": "additive metadata shape for future package compatibility",
        "cross_lane_reusable_block_registry_contract": "reusable facts and tokenized protected value compatibility",
        "agent_conversation_handoff_step_packet_contract": "agent handoff packets and status visibility",
        "agent_execution_packet_compiler_contract": "packet shape for future role work without live execution",
        "bridge_routing_operator_attention_contract": "operator attention routing for questions, proof, and blockers",
        "capital_hilton_delivery_facts_capture_writer": "Capital Hilton proof example for local receipt/readback capture",
        "capital_hilton_delivery_facts_capture_bridge": "Capital Hilton delivery-facts question/capture bridge",
        "capital_hilton_invoice_artifact_generator": "Capital Hilton local invoice preview metadata",
        "guardian_protected_access_gate_spec": "protected evidence and Guardian gate posture",
        "protected_evidence_reference_receipt": "metadata-only protected evidence receipt compatibility",
        "capital_hilton_guardian_review_packet": "Capital Hilton Guardian review packet reference",
        "openclaw_sensitive_policy": "sensitive material boundary",
        "business_ops_ledger": "receipt/state substrate referenced but not mutated here",
    }
    return {
        Path(path).stem: {
            "path": path,
            "present": (ROOT / path).exists()
            or (ROOT / "generated/read_models" / path.replace(".py", ".json")).exists(),
            "relationship": notes.get(Path(path).stem, "related contract if present"),
        }
        for path in RELATIONSHIP_CANDIDATES
    }


def build_generic_intake() -> ConversationalWorkflowIntake:
    return ConversationalWorkflowIntake(
        intake_id="generic_conversational_workflow_intake_v0",
        workflow_ref="future_workflow_ref",
        workflow_type="generic_repeatable_workflow",
        client_ref="scope_defined_by_operator",
        tenant_ref="local_operator_tenant",
        world_ref="operator_selected_world",
        lane_ref="operator_selected_lane",
        operator_narrative=(
            "Sanitized narrative placeholder: the operator explains a repeatable workflow, expected outputs, "
            "roles, unknowns, and proof requirements."
        ),
        narrative_privacy_class="sanitized_operator_workflow_summary",
        raw_narrative_allowed_in_normal_read_model=False,
        sanitized_summary=(
            "A human explanation becomes candidate structure. Review and receipts decide what becomes durable."
        ),
        parsed_candidate_status="CANDIDATE_MEANING_OPERATOR_REVIEW_REQUIRED",
        operator_review_required=True,
        proposed_chain_ref="generic_workflow_block_chain_proposal_v0",
        next_safe_move="Propose a block chain and ask the operator to confirm or correct it.",
    )


def build_generic_proposal(intake: ConversationalWorkflowIntake) -> WorkflowBlockChainProposal:
    return WorkflowBlockChainProposal(
        proposal_id="generic_workflow_block_chain_proposal_v0",
        source_intake_ref=intake.intake_id,
        workflow_type=intake.workflow_type,
        proposed_blocks=(
            {"block_id": "capture_goal", "label": "Capture the goal", "status": "OPERATOR_REVIEW_REQUIRED"},
            {"block_id": "identify_inputs", "label": "Identify inputs and unknowns", "status": "FILLABLE_NOW"},
            {"block_id": "prepare_artifacts", "label": "Prepare required artifacts", "status": "GATED"},
            {"block_id": "review_outputs", "label": "Review drafts or outputs", "status": "GATED"},
            {"block_id": "approval_gate", "label": "Approval gate", "status": "GATED"},
            {"block_id": "external_action", "label": "External action if explicitly approved", "status": "BLOCKED"},
            {"block_id": "completion_readback", "label": "Proof-backed completion readback", "status": "BLOCKED"},
        ),
        proposed_sequence=(
            "capture_goal",
            "identify_inputs",
            "prepare_artifacts",
            "review_outputs",
            "approval_gate",
            "external_action",
            "completion_readback",
        ),
        non_serial_blocks=("identify_inputs", "prepare_artifacts", "proof_lookup"),
        dependencies=(
            {"block": "external_action", "depends_on": ("review_outputs", "approval_gate")},
            {"block": "completion_readback", "depends_on": ("external_action", "proof_receipts")},
        ),
        gates=(
            {"gate_id": "operator_review_gate", "authority_granted": False},
            {"gate_id": "artifact_hash_gate", "authority_granted": False},
            {"gate_id": "approval_gate", "authority_granted": False},
            {"gate_id": "external_adapter_gate", "authority_granted": False},
        ),
        unknowns=("which facts need proof", "which artifacts are required", "which adapters are required"),
        proof_requirements=(
            "artifact file/hash where an artifact is required",
            "approval receipt before gated external action",
            "external action result receipt before completion label",
        ),
        operator_questions=(
            "Is this the right block chain?",
            "Which blocks can be answered now?",
            "Which facts require proof or protected evidence?",
        ),
        reusable_fact_candidates=(
            {"fact_kind": "operator_confirmed_procedure", "raw_value_allowed": False},
            {"fact_kind": "safe_non_sensitive_workflow_fact", "raw_value_allowed": True},
        ),
        protected_value_candidates=(
            {"value_kind": "contact_or_payment_reference", "normal_read_model_body_allowed": False},
            {"value_kind": "protected_evidence_ref", "normal_read_model_body_allowed": False},
        ),
        review_status="OPERATOR_REVIEW_REQUIRED",
        elioperator_summary=(
            "ELIOPERATOR: This is the proposed shape of the workflow, not permission to run it."
        ),
        next_safe_move="Show the proposal in plain language and wait for operator review.",
    )


def build_generic_procedure(proposal: WorkflowBlockChainProposal) -> StoredWorkflowProcedure:
    return StoredWorkflowProcedure(
        procedure_id="generic_stored_workflow_procedure_candidate_v0",
        procedure_name="Reviewed repeatable workflow procedure",
        workflow_type=proposal.workflow_type,
        client_ref="scope_defined_by_operator",
        tenant_ref="local_operator_tenant",
        trigger_phrases=("do it", "run this workflow", "use the stored procedure"),
        stored_workflow_summary=(
            "A reviewed procedure stores trigger phrases, blocks, gates, roles, artifacts, proof needs, "
            "privacy boundaries, and update policy."
        ),
        stored_blocks=proposal.proposed_sequence,
        reusable_facts=proposal.reusable_fact_candidates,
        required_inputs=("operator-reviewed procedure", "current run-specific facts", "proof refs where needed"),
        required_artifacts=("artifact path/hash when artifacts are part of completion",),
        required_gates=("operator review", "proof gate", "approval gate", "external adapter gate"),
        agent_roles={role: "role candidate only; no live dispatch" for role in GENERIC_REQUIRED_ROLES},
        authority_boundaries={
            "stored_procedure_is_external_authority": False,
            "stored_procedure_can_send_or_submit": False,
            "stored_procedure_can_browse_or_log_in": False,
            "stored_procedure_can_approve": False,
            "stored_procedure_creates_governed_run_plan": True,
        },
        proof_requirements=proposal.proof_requirements,
        privacy_boundaries={
            "raw_narrative_in_normal_read_model": False,
            "protected_values_require_token_or_ref": True,
            "raw_private_body_allowed": False,
        },
        update_policy="Procedure edits require operator review and deterministic receipt before they replace prior memory.",
        last_run_ref=None,
        last_successful_completion_ref=None,
        next_safe_move="A future writer may persist the reviewed procedure; this contract does not write it.",
    )


def build_generic_run_plan(procedure: StoredWorkflowProcedure) -> GovernedWorkflowRunPlan:
    return GovernedWorkflowRunPlan(
        run_id="generic_governed_workflow_run_plan_v0",
        procedure_ref=procedure.procedure_id,
        requested_by="future_operator_do_it_request",
        run_goal="Create a governed plan from reviewed procedure memory.",
        current_state="OPERATOR_REVIEW_REQUIRED",
        run_blocks=procedure.stored_blocks,
        dependencies=(
            {"block": "external_action", "requires": ("approval receipt", "adapter authority")},
            {"block": "completion_readback", "requires": ("proof receipts",)},
        ),
        gates=(
            {"gate": "operator review", "current_status": "NOT_GRANTED"},
            {"gate": "Guardian/protected evidence review if needed", "current_status": "NOT_GRANTED"},
            {"gate": "external adapter", "current_status": "NOT_GRANTED"},
        ),
        runnable_now=("render plan", "ask missing questions", "collect safe local metadata"),
        blocked_now=("live workflow run", "agent dispatch", "external adapter action", "completion label"),
        required_operator_confirmations=("confirm run request", "approve exact action packet later"),
        required_guardian_approvals=("required only if protected evidence, send, submit, or approval scope appears"),
        required_artifacts=("artifact path/hash when required", "approval packet when required"),
        required_external_adapters=("future gated adapter only",),
        readback_plan=("show progress by state", "show blockers", "show completion only with proof receipts"),
        completion_condition="Completion requires proof receipts for the declared outcome.",
        next_safe_move="Keep the run proposed until review/proof/approval gates exist.",
    )


def build_generic_role_routing(run_plan: GovernedWorkflowRunPlan) -> WorkflowRoleRoutingPlan:
    return WorkflowRoleRoutingPlan(
        routing_id="generic_workflow_role_routing_plan_v0",
        workflow_run_ref=run_plan.run_id,
        roles=tuple(
            {"role": role, "responsibility": _role_responsibility(role), "live_dispatch_allowed": False}
            for role in GENERIC_REQUIRED_ROLES
        ),
        actor_candidates={
            "Cassandra": "example candidate for drafting_agent or validation_agent; not hardcoded",
            "Guardian": "example candidate for approval_agent or protected_evidence_agent; not live approval",
            "Mission Control": "example rendering surface; no Swift change here",
        },
        role_boundaries={
            "roles_are_generic": True,
            "agent_names_are_configured_candidates": True,
            "backend_receipts_own_truth": True,
            "no_agent_has_external_authority_from_this_contract": True,
        },
        package_requirements=(
            "workflow_session_ref",
            "role assignment",
            "authority boundary",
            "privacy boundary",
            "expected return shape",
        ),
        handoff_requirements=(
            "visual-agnostic post-office metadata",
            "idempotency key where a future write happens",
            "payload hash where a future write happens",
        ),
        review_requirements=(
            "operator review before storage",
            "draft/output review before approval",
            "approval receipt before external action",
        ),
        no_hardcoded_persona_requirement=True,
        next_safe_move="Map actors at the edge; keep core workflow memory role-based.",
    )


def _role_responsibility(role: str) -> str:
    return {
        "operator": "reviews, corrects, and approves exact gated action packets",
        "drafting_agent": "prepares drafts or text candidates for review only",
        "validation_agent": "checks shape, prerequisites, and blockers",
        "protected_evidence_agent": "handles protected evidence metadata and Guardian posture",
        "approval_agent": "prepares or reviews approval packet boundaries",
        "artifact_generation_agent": "prepares local artifact candidates under artifact policy",
        "post_office_handoff": "packages typed handoff metadata",
        "final_readback_agent": "produces proof-backed completion readback",
    }[role]


def build_generic_artifact_proof_plan(run_plan: GovernedWorkflowRunPlan) -> ArtifactAndProofPlan:
    return ArtifactAndProofPlan(
        plan_id="generic_artifact_and_proof_plan_v0",
        workflow_run_ref=run_plan.run_id,
        required_artifacts=(
            {
                "artifact_kind": "workflow_output_artifact",
                "file_hash_required": True,
                "receipt_required": True,
                "ready_now": False,
            },
            {
                "artifact_kind": "approval_or_review_packet",
                "file_hash_required": False,
                "receipt_required": True,
                "ready_now": False,
            },
        ),
        optional_artifacts=(
            {"artifact_kind": "operator_preview", "hash_required_if_file": True, "ready_now": False},
        ),
        proof_bullets=(
            "Required artifacts exist and hashes match.",
            "Protected references stay metadata-only unless separately authorized.",
            "Approval receipts bind the exact action packet.",
            "External result receipts exist before final completion.",
        ),
        missing_proofs=(
            "operator-reviewed procedure receipt",
            "artifact hash receipts",
            "approval receipts",
            "external action result receipts",
        ),
        protected_refs=(
            {"ref_kind": "protected_evidence_ref", "normal_read_model_body_allowed": False},
            {"ref_kind": "tokenized_sensitive_value_ref", "normal_read_model_body_allowed": False},
        ),
        artifact_hash_requirements=(
            "No file artifact can be called ready without a real path and hash.",
            "Hashes identify artifacts; they do not authorize sending or submitting.",
        ),
        completion_proof_requirements=(
            "Completion labels must cite proof receipts.",
            "Calculated status must derive from receipts, not copied narrative.",
        ),
        next_safe_move="Use the proof plan to block fake readiness and fake completion.",
    )


def build_generic_completion(run_plan: GovernedWorkflowRunPlan) -> CompletionReadbackContract:
    return CompletionReadbackContract(
        completion_id="generic_completion_readback_contract_v0",
        workflow_run_ref=run_plan.run_id,
        status_label="FUTURE_TARGET_NOT_CURRENT_FACT",
        headline="COMPLETION CONFIRMED (future target; not current)",
        proof_bullets=(
            "The declared outcome happened through gated authority.",
            "Required artifacts and hashes are present.",
            "External action receipts exist if external action was part of completion.",
            "State updates are receipt-backed.",
        ),
        unresolved_items=("No live run exists.", "No approval or external result receipts exist."),
        state_updates=(
            {"state_update": "last_successful_completion_ref", "write_allowed_now": False},
            {"state_update": "next_run_memory_update", "write_allowed_now": False},
        ),
        next_run_memory_update="Future receipt-backed completion may update procedure memory.",
        safe_display_summary="Completion labels are future targets until proof receipts exist.",
        elioperator_summary=(
            "ELIOPERATOR: A completion label is a receipt-backed outcome, not a hopeful message."
        ),
        next_safe_move="Block fake completion and keep unresolved items visible.",
    )


def build_capital_hilton_example() -> dict[str, Any]:
    intake = ConversationalWorkflowIntake(
        intake_id="capital_hilton_conversational_intake_annette_coupa_excel_v0",
        workflow_ref="capital_hilton_invoice_payment_workflow",
        workflow_type="finance_invoice_delivery",
        client_ref="capital_hilton",
        tenant_ref="openclaw_repo_a_local",
        world_ref="Finance",
        lane_ref="Capital Hilton",
        operator_narrative=(
            "Sanitized narrative: email the companion Excel-generated invoice PDF to Annette candidate "
            "for local records and payment help; official payment belongs in Coupa from the Coupa PO; "
            "PO/Coupa reference and payment-contact correctness still need confirmation."
        ),
        narrative_privacy_class="client_business_context_sanitized",
        raw_narrative_allowed_in_normal_read_model=False,
        sanitized_summary=(
            "Capital Hilton payment workflow candidate: companion Excel PDF goes to Annette candidate, "
            "official payment rail is Coupa from PO, and OpenClaw must confirm PO/Coupa reference plus "
            "payment contact before delivery readiness."
        ),
        parsed_candidate_status="CANDIDATE_MEANING_OPERATOR_REVIEW_REQUIRED",
        operator_review_required=True,
        proposed_chain_ref="capital_hilton_invoice_payment_block_chain_proposal_v0",
        next_safe_move="Show the Capital Hilton block chain for operator review; do not store or run it live.",
    )
    blocks = tuple(
        {
            "block_id": _slug(label),
            "label": label,
            "status": _capital_block_status(label),
            "external_action_allowed_now": False,
        }
        for label in CAPITAL_HILTON_BLOCK_LABELS
    )
    proposal = WorkflowBlockChainProposal(
        proposal_id="capital_hilton_invoice_payment_block_chain_proposal_v0",
        source_intake_ref=intake.intake_id,
        workflow_type="finance_invoice_delivery",
        proposed_blocks=blocks,
        proposed_sequence=tuple(block["block_id"] for block in blocks),
        non_serial_blocks=(
            "confirm_po_coupa_payment_rail",
            "confirm_invoice_destination_contact_annette_candidate",
            "generate_update_excel_branded_companion_invoice_pdf",
        ),
        dependencies=(
            {
                "block": "send_email",
                "depends_on": (
                    "prepare_email_draft_to_annette",
                    "attach_excel_generated_pdf_invoice",
                    "guardian_approval_request",
                    "operator_approval",
                ),
            },
            {
                "block": "submit_verify_coupa_invoice_if_required_and_gated",
                "depends_on": (
                    "confirm_po_coupa_payment_rail",
                    "confirm_coupa_supplier_portal_invoice_from_po",
                    "operator_approval",
                ),
            },
        ),
        gates=(
            {"gate_id": "po_coupa_proof_gate", "authority_granted": False},
            {"gate_id": "annette_contact_confirmation_gate", "authority_granted": False},
            {"gate_id": "excel_pdf_artifact_hash_gate", "authority_granted": False},
            {"gate_id": "guardian_operator_send_submit_gate", "authority_granted": False},
        ),
        unknowns=(
            "PO/Coupa reference or explicit no-PO posture is unresolved.",
            "Annette candidate is not yet confirmed as payment contact.",
            "Coupa submission requirement remains unresolved.",
            "Final Excel PDF artifact is not generated in this contract.",
        ),
        proof_requirements=(
            "Coupa invoice generated/submitted from PO, if required and proven.",
            "Email sent to Annette with attached Winship-branded Excel PDF invoice.",
            "Winship-branded Excel PDF invoice saved with date.",
            "Last invoice sent date recorded for future invoice-range calculation.",
            "External send/submit proof receipts attached.",
            "Payment tracking state updated.",
        ),
        operator_questions=(
            "Is Annette the correct payment contact for the companion PDF?",
            "What is the PO/Coupa/payment reference, or should the posture remain needs-discovery?",
            "Is Coupa submission required for this invoice?",
        ),
        reusable_fact_candidates=(
            {
                "fact_kind": "performance_dates",
                "safe_display_label": "4 captured dates",
                "value": CAPITAL_HILTON_DATES,
                "raw_value_allowed": True,
            },
            {
                "fact_kind": "rate_amount",
                "safe_display_label": "$400/show",
                "value": CAPITAL_HILTON_RATE,
                "raw_value_allowed": True,
            },
            {
                "fact_kind": "calculated_state",
                "safe_display_label": "$1,600 subtotal derived from dates and rate",
                "copy_as_truth_allowed": False,
            },
        ),
        protected_value_candidates=(
            {"value_kind": "ap_email_route", "safe_display_label": "Annette candidate", "raw_value_allowed": False},
            {"value_kind": "po_reference", "safe_display_label": "PO/Coupa reference pending", "raw_value_allowed": False},
        ),
        review_status="OPERATOR_REVIEW_REQUIRED",
        elioperator_summary=(
            "ELIOPERATOR: Capital Hilton can be remembered as a procedure after review, but nothing is sent "
            "or submitted from memory alone."
        ),
        next_safe_move="Ask the operator to confirm the proposed Capital Hilton procedure and missing facts.",
    )
    procedure = StoredWorkflowProcedure(
        procedure_id="capital_hilton_invoice_payment_procedure_candidate_v0",
        procedure_name="How Capital Hilton invoices get paid",
        workflow_type="finance_invoice_delivery",
        client_ref="capital_hilton",
        tenant_ref="openclaw_repo_a_local",
        trigger_phrases=(
            "do the Capital Hilton invoice",
            "send Capital Hilton invoice",
            "invoice Capital Hilton",
            "now do it",
            "run the Hilton invoice workflow",
        ),
        stored_workflow_summary=(
            "Candidate procedure: companion Excel PDF goes to Annette candidate for local records, official "
            "payment rail is Coupa from PO when required, and send/submit only happens after proof and approval."
        ),
        stored_blocks=proposal.proposed_sequence,
        reusable_facts=proposal.reusable_fact_candidates,
        required_inputs=(
            "operator-confirmed procedure review",
            "PO/Coupa/payment reference or explicit no-PO posture",
            "payment contact confirmation",
        ),
        required_artifacts=(
            "Winship-branded Excel PDF with real path/hash",
            "reviewed email draft packet",
            "Coupa proof or not-required proof",
            "approval and send/submit receipts",
        ),
        required_gates=(
            "operator procedure review",
            "artifact hash gate",
            "Guardian approval gate",
            "operator approval gate",
            "external adapter gate",
        ),
        agent_roles={
            "drafting_agent": "Cassandra may be configured later for draft packet prep",
            "approval_agent": "Guardian may be configured later for gated approval packet review",
            "final_readback_agent": "receipt-backed closeout only",
        },
        authority_boundaries={
            "stored_procedure_is_external_authority": False,
            "stored_procedure_can_send_or_submit": False,
            "stored_procedure_can_browse_or_log_in": False,
            "stored_procedure_can_approve": False,
            "stored_procedure_creates_governed_run_plan": True,
        },
        proof_requirements=proposal.proof_requirements,
        privacy_boundaries={
            "raw_contact_value_in_normal_read_model": False,
            "raw_po_reference_in_normal_read_model": False,
            "protected_evidence_body_allowed": False,
        },
        update_policy="Operator-reviewed receipt required before replacing the stored procedure.",
        last_run_ref=None,
        last_successful_completion_ref=None,
        next_safe_move="Future writer may persist this only after operator review.",
    )
    run = GovernedWorkflowRunPlan(
        run_id="capital_hilton_now_do_it_governed_run_plan_v0",
        procedure_ref=procedure.procedure_id,
        requested_by="operator_future_now_do_it_utterance",
        run_goal="Prepare Capital Hilton invoice delivery under proof and approval gates.",
        current_state="OPERATOR_REVIEW_REQUIRED",
        run_blocks=procedure.stored_blocks,
        dependencies=proposal.dependencies,
        gates=proposal.gates,
        runnable_now=("review proposed procedure", "ask PO/Coupa and payment-contact questions", "read local preview metadata"),
        blocked_now=(
            "Cassandra draft creation",
            "Guardian approval request",
            "email draft or send",
            "Coupa access or submit",
            "invoice generation",
            "attachment",
            "payment tracking write",
            "INVOICE SENT completion readback",
        ),
        required_operator_confirmations=("confirm Annette candidate", "confirm PO/Coupa posture", "approve exact action later"),
        required_guardian_approvals=("exact draft and attachment approval", "Coupa submit scope approval if required"),
        required_artifacts=("final Excel PDF hash", "draft packet", "approval packet", "send/submit receipts"),
        required_external_adapters=("future gated email adapter", "future gated Coupa adapter"),
        readback_plan=("show blockers now", "show draft ready later", "show INVOICE SENT only with proof receipts"),
        completion_condition="INVOICE SENT requires email send proof and Coupa submit/not-required proof.",
        next_safe_move="Collect missing delivery facts before any future draft/send/submit lane.",
    )
    role_routing = WorkflowRoleRoutingPlan(
        routing_id="capital_hilton_role_routing_example_v0",
        workflow_run_ref=run.run_id,
        roles=tuple(
            {"role": role, "responsibility": _role_responsibility(role), "live_dispatch_allowed": False}
            for role in GENERIC_REQUIRED_ROLES
        ),
        actor_candidates={
            "Cassandra": "future drafting or finance-delivery role; no draft created here",
            "Guardian": "future approval or protected-evidence role; no approval requested here",
        },
        role_boundaries={"role_based_not_persona_hardcoded": True, "external_authority_from_contract": False},
        package_requirements=("post-office metadata", "authority boundary", "proof refs", "safe display summary"),
        handoff_requirements=("visual-agnostic workflow/block grammar", "readback required"),
        review_requirements=("operator review", "draft review", "Guardian/operator approval later"),
        no_hardcoded_persona_requirement=True,
        next_safe_move="Keep actor mappings configurable and gated.",
    )
    proof_plan = ArtifactAndProofPlan(
        plan_id="capital_hilton_artifact_and_proof_plan_example_v0",
        workflow_run_ref=run.run_id,
        required_artifacts=(
            {
                "artifact_kind": "Winship-branded Excel PDF invoice",
                "preview_hash_available": CAPITAL_HILTON_PREVIEW_HASH,
                "final_pdf_exists_now": False,
                "hash_required": True,
            },
            {"artifact_kind": "reviewed email draft", "exists_now": False, "receipt_required": True},
            {"artifact_kind": "Coupa proof or not-required proof", "exists_now": False, "protected_ref_allowed": True},
        ),
        optional_artifacts=({"artifact_kind": "operator preview", "hash_required_if_file": True},),
        proof_bullets=proposal.proof_requirements,
        missing_proofs=(
            "confirmed PO/Coupa reference or no-PO proof",
            "confirmed payment contact",
            "final Excel PDF path/hash",
            "reviewed email draft",
            "Guardian/operator approval receipts",
            "email send receipt",
            "Coupa submit/not-required receipt",
            "payment tracking receipt",
        ),
        protected_refs=(
            {"ref_kind": "COUPA_PO_SCREEN_REFERENCE", "normal_read_model_body_allowed": False},
            {"ref_kind": "AP_EMAIL_ROUTE_REFERENCE", "normal_read_model_body_allowed": False},
        ),
        artifact_hash_requirements=("No attachment readiness without real final PDF hash.",),
        completion_proof_requirements=("No INVOICE SENT without send/submit receipts.",),
        next_safe_move="Resolve PO/Coupa and contact facts, then build final artifact/draft lanes.",
    )
    completion = CompletionReadbackContract(
        completion_id="capital_hilton_invoice_sent_completion_target_v0",
        workflow_run_ref=run.run_id,
        status_label="FUTURE_TARGET_NOT_CURRENT_FACT",
        headline="INVOICE SENT (future target; not current)",
        proof_bullets=proposal.proof_requirements,
        unresolved_items=proof_plan.missing_proofs,
        state_updates=(
            {"state_update": "last_invoice_sent_date_ref", "write_allowed_now": False},
            {"state_update": "payment_tracking_state", "write_allowed_now": False},
        ),
        next_run_memory_update="Record last invoice sent date only after proof-backed completion.",
        safe_display_summary="INVOICE SENT is modeled as the future closeout, not current truth.",
        elioperator_summary="ELIOPERATOR: Do not show INVOICE SENT until receipts prove delivery.",
        next_safe_move="Block fake completion and keep unresolved proof visible.",
    )
    return {
        "narrative_intake": asdict(intake),
        "proposed_block_chain": asdict(proposal),
        "stored_procedure": asdict(procedure),
        "now_do_it_run_plan": asdict(run),
        "role_routing": asdict(role_routing),
        "artifact_proof_plan": asdict(proof_plan),
        "invoice_sent_completion_target": asdict(completion),
        "cassandra_draft_stage": {
            "role": "drafting_agent",
            "actor_candidate": "Cassandra",
            "draft_allowed_now": False,
            "future_packet_required": "reviewed email draft packet",
        },
        "guardian_approval_stage": {
            "role": "approval_agent",
            "actor_candidate": "Guardian",
            "approval_allowed_now": False,
            "future_receipt_required": "approval over exact draft, attachment, and Coupa scope",
        },
        "fake_completion_blocker": {
            "blocker_type": "COMPLETION_WITHOUT_RECEIPTS",
            "decision": "BLOCKED_FAIL_CLOSED",
            "elioperator_warning": "ELIOPERATOR: INVOICE SENT requires proof receipts first.",
        },
    }


def _slug(label: str) -> str:
    return (
        label.lower()
        .replace("/", "_")
        .replace("-", "_")
        .replace(":", "")
        .replace("$", "")
        .replace(" ", "_")
    )


def _capital_block_status(label: str) -> str:
    if label in {"Confirm performance dates", "Confirm rate"}:
        return "KNOWN_FROM_LOCAL_RECEIPTS"
    if "PO/Coupa" in label or "Annette" in label or "Coupa supplier" in label:
        return "NEEDS_OPERATOR_CONFIRMATION_OR_PROOF"
    if "Send email" in label or "Submit/verify" in label:
        return "BLOCKED_EXTERNAL_AUTHORITY"
    if "Completion" in label:
        return "FUTURE_TARGET_ONLY"
    return "FUTURE_GATED_STEP"


def build_builder_blockers() -> tuple[ConversationalWorkflowBuilderBlocker, ...]:
    blocker_data = (
        ("NARRATIVE_TREATED_AS_TRUTH", "Narrative is stored as canonical truth without review.", "Require review receipt."),
        ("PROCEDURE_MEMORY_USED_AS_AUTHORITY", "Procedure memory is used as send/submit approval.", "Separate memory from authority."),
        ("RUN_WITHOUT_OPERATOR_REVIEW", "A governed run starts from an unreviewed procedure.", "Require operator review first."),
        ("EXTERNAL_ACTION_WITHOUT_GATE", "External adapter action is attempted without explicit gate.", "Fail closed."),
        ("SEND_WITHOUT_GUARDIAN_APPROVAL", "Send happens before Guardian/operator approval.", "Require approval receipts."),
        ("SUBMIT_WITHOUT_PROOF", "Submit happens before proof or protected access posture.", "Require proof receipts."),
        ("ATTACHMENT_WITHOUT_ARTIFACT_HASH", "Attachment is claimed ready without file/hash.", "Require real artifact hash."),
        ("COMPLETION_WITHOUT_RECEIPTS", "Completion label appears without proof receipts.", "Block fake completion."),
        ("RAW_PII_IN_NORMAL_READMODEL", "Raw private value appears in normal read-model.", "Use safe label or protected ref."),
        ("AGENT_PERSONA_HARDCODED_IN_CORE", "Core logic depends on a named agent persona.", "Keep roles generic."),
        ("MACHINE_CONTRACT_VISIBLE_TO_OPERATOR", "UI shows machine schema instead of plain work state.", "Render plain ELIOPERATOR text."),
        ("UNKNOWN_FAIL_CLOSED", "Workflow shape, proof, or authority is ambiguous.", "Ask the next safe question."),
    )
    return tuple(
        ConversationalWorkflowBuilderBlocker(
            blocker_id=f"blocker_{blocker_type.lower()}",
            blocker_type=blocker_type,
            condition=condition,
            severity="BLOCKS_SAFE_RUN" if blocker_type != "MACHINE_CONTRACT_VISIBLE_TO_OPERATOR" else "SHOULD_PATCH",
            elioperator_warning=f"ELIOPERATOR: {condition}",
            builder_action_required=action,
            fail_closed=True,
            next_safe_move="Do not execute externally; resolve review, proof, or authority first.",
        )
        for blocker_type, condition, action in blocker_data
    )


def build_elioperator_report() -> ConversationalWorkflowElioperatorReport:
    return ConversationalWorkflowElioperatorReport(
        report_id="conversational_workflow_memory_elioperator_report_v0",
        plain_summary=(
            "Conversational workflow memory makes chat the input layer for repeatable workflows while "
            "keeping truth, authority, and completion receipt-backed."
        ),
        what_this_enables=(
            "The operator can describe a workflow once; OpenClaw proposes blocks, questions, roles, gates, "
            "artifacts, and proof requirements."
        ),
        what_this_does_not_do_yet=(
            "It does not parse live chat, write procedure memory, start runs, dispatch agents, create drafts, "
            "ask approvals, send, submit, browse, log in, generate invoices, or update payment tracking."
        ),
        why_chat_drives_workflow=(
            "Human explanation is the easiest way to name the real-world process. OpenClaw turns it into "
            "candidate structure that the operator can correct."
        ),
        how_operator_review_works="The block chain remains a proposal until the operator confirms or edits it.",
        how_procedure_memory_works=(
            "A reviewed procedure stores reusable shape and trigger phrases. It cannot grant external authority."
        ),
        how_governed_run_works=(
            "A future 'do it' request creates a run plan with runnable local steps, blocked external steps, "
            "role packets, proof requirements, and approval gates."
        ),
        why_external_actions_remain_gated=(
            "External actions require exact artifacts, approvals, adapter authority, and result receipts."
        ),
        next_safe_move="Use this read-model as the generic contract; build a future reviewed procedure writer separately.",
    )


def _examples(
    generic_intake: ConversationalWorkflowIntake,
    generic_proposal: WorkflowBlockChainProposal,
    generic_procedure: StoredWorkflowProcedure,
    generic_run: GovernedWorkflowRunPlan,
    generic_roles: WorkflowRoleRoutingPlan,
    generic_completion: CompletionReadbackContract,
    capital_hilton: dict[str, Any],
) -> dict[str, Any]:
    return {
        "generic_workflow_intake": {
            "intake_ref": generic_intake.intake_id,
            "operator_review_required": True,
            "narrative_treated_as_truth": False,
            "proposed_chain_ref": generic_intake.proposed_chain_ref,
        },
        "generic_stored_procedure": {
            "procedure_ref": generic_procedure.procedure_id,
            "reusable_not_authority": True,
            "stored_blocks": generic_procedure.stored_blocks,
        },
        "generic_do_it_run_request": {
            "run_ref": generic_run.run_id,
            "external_action_performed": False,
            "current_state": generic_run.current_state,
        },
        "generic_role_routing": {
            "routing_ref": generic_roles.routing_id,
            "roles": tuple(role["role"] for role in generic_roles.roles),
            "hardcoded_personas": False,
        },
        "generic_completion_readback": {
            "completion_ref": generic_completion.completion_id,
            "current_fact": False,
            "proof_required": True,
        },
        "generic_fake_completion_blocker": {
            "blocker_type": "COMPLETION_WITHOUT_RECEIPTS",
            "decision": "BLOCKED_FAIL_CLOSED",
        },
        "capital_hilton": capital_hilton,
    }


def _machine_proof(payload: dict[str, Any]) -> dict[str, Any]:
    capital = payload["capital_hilton_example"]
    block_labels = {block["label"] for block in capital["proposed_block_chain"]["proposed_blocks"]}
    blocker_types = {blocker["blocker_type"] for blocker in payload["builder_blockers_by_id"].values()}
    role_names = {role["role"] for role in payload["workflow_role_routing_plan"]["roles"]}
    return {
        "conversational_workflow_intake_model_present": True,
        "workflow_block_chain_proposal_model_present": True,
        "stored_workflow_procedure_model_present": True,
        "governed_workflow_run_plan_model_present": True,
        "workflow_role_routing_plan_model_present": True,
        "artifact_and_proof_plan_model_present": True,
        "completion_readback_contract_model_present": True,
        "builder_blockers_model_present": True,
        "elioperator_report_model_present": True,
        "all_generic_roles_present": all(role in role_names for role in GENERIC_REQUIRED_ROLES),
        "generic_workflow_example_present": "generic_workflow_intake" in payload["examples"],
        "generic_stored_procedure_example_present": "generic_stored_procedure" in payload["examples"],
        "generic_governed_run_example_present": "generic_do_it_run_request" in payload["examples"],
        "capital_hilton_narrative_intake_exists": True,
        "capital_hilton_block_chain_proposal_exists": True,
        "capital_hilton_stored_procedure_exists": True,
        "capital_hilton_governed_run_plan_exists": True,
        "capital_hilton_all_required_blocks_present": all(
            label in block_labels for label in CAPITAL_HILTON_BLOCK_LABELS
        ),
        "invoice_sent_target_exists": True,
        "invoice_sent_is_not_current_fact": True,
        "narrative_is_not_treated_as_truth": True,
        "procedure_memory_is_not_authority": True,
        "fake_completion_blocked": "COMPLETION_WITHOUT_RECEIPTS" in blocker_types,
        "persona_hardcoding_blocked": "AGENT_PERSONA_HARDCODED_IN_CORE" in blocker_types,
        "machine_contract_ui_leakage_blocked": "MACHINE_CONTRACT_VISIBLE_TO_OPERATOR" in blocker_types,
        "all_live_authority_flags_false": all(value is False for value in LIVE_AUTHORITY_BOUNDARY.values()),
        "credentials_or_secrets_included": False,
        "raw_private_bodies_included": False,
        "raw_sensitive_fixture_values_included": False,
        "network_used": False,
        "external_action_performed": False,
        "mission_control_swift_changed": False,
        "mac_sync_import_run": False,
        "git_push_pull_fetch_run": False,
        "content_hash": None,
    }


def build_conversational_workflow_memory_contract(*, generated_at: str | None = None) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    generic_intake = build_generic_intake()
    generic_proposal = build_generic_proposal(generic_intake)
    generic_procedure = build_generic_procedure(generic_proposal)
    generic_run = build_generic_run_plan(generic_procedure)
    generic_roles = build_generic_role_routing(generic_run)
    generic_proof = build_generic_artifact_proof_plan(generic_run)
    generic_completion = build_generic_completion(generic_run)
    blockers = build_builder_blockers()
    report = build_elioperator_report()
    capital_hilton = build_capital_hilton_example()

    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "contract_status": CONTRACT_STATUS,
        "generated_at": generated_at,
        "operator_markdown_mode": "ELIOPERATOR",
        "doctrine": {
            "operator_speaks_human": True,
            "openclaw_proposes_structure": True,
            "operator_confirms_or_corrects": True,
            "stored_procedure_memory_is_not_external_authority": True,
            "governed_runs_do_not_bypass_gates": True,
            "receipts_readbacks_decide_truth": True,
        },
        "run_states": RUN_STATES,
        "model_schemas": _model_schemas(),
        "conversational_workflow_intake": asdict(generic_intake),
        "workflow_block_chain_proposal": asdict(generic_proposal),
        "stored_workflow_procedure": asdict(generic_procedure),
        "governed_workflow_run_plan": asdict(generic_run),
        "workflow_role_routing_plan": asdict(generic_roles),
        "artifact_and_proof_plan": asdict(generic_proof),
        "completion_readback_contract": asdict(generic_completion),
        "builder_blockers_by_id": {blocker.blocker_id: asdict(blocker) for blocker in blockers},
        "elioperator_report": asdict(report),
        "capital_hilton_example": capital_hilton,
        "examples": _examples(
            generic_intake,
            generic_proposal,
            generic_procedure,
            generic_run,
            generic_roles,
            generic_completion,
            capital_hilton,
        ),
        "relationship_inventory": _relationship_inventory(),
        "allowed_contract_scope": (
            "deterministic read-model generation",
            "tests",
            "metadata-only examples",
            "future target modeling",
            "ELIOPERATOR report",
        ),
        "authority_boundary": LIVE_AUTHORITY_BOUNDARY,
    }
    payload["machine_proof"] = _machine_proof(payload)
    payload["machine_proof"]["content_hash"] = _content_hash(payload)
    return payload


def format_operator_markdown(payload: dict[str, Any]) -> str:
    proposal = payload["workflow_block_chain_proposal"]
    report = payload["elioperator_report"]
    capital = payload["capital_hilton_example"]
    cap_blocks = "\n".join(
        f"- {block['label']}: `{block['status']}`"
        for block in capital["proposed_block_chain"]["proposed_blocks"]
    )
    generic_blocks = "\n".join(
        f"- {block['label']}: `{block['status']}`"
        for block in proposal["proposed_blocks"]
    )
    return "\n".join(
        [
            "# Conversational Workflow Memory Contract v0",
            "",
            "ELIOPERATOR: Chat can be the input layer for repeatable workflows. OpenClaw proposes the structure, the operator reviews it, and receipts decide what becomes true.",
            "",
            "## What This Enables",
            "",
            report["what_this_enables"],
            "",
            "## Generic Pattern",
            "",
            "- Operator explains the workflow.",
            "- OpenClaw proposes blocks, questions, gates, roles, artifacts, and proof requirements.",
            "- Operator confirms or corrects the chain before it becomes procedure memory.",
            "- A later do-it request creates a governed run plan, not instant external action.",
            "- Agents operate through roles, packages, permissions, and gates.",
            "- Completion requires proof receipts.",
            "",
            "## Generic Blocks",
            "",
            generic_blocks,
            "",
            "## Capital Hilton Proof Example",
            "",
            "- Procedure: `How Capital Hilton invoices get paid`.",
            "- The Annette / Excel PDF / Coupa PO explanation becomes a candidate chain, not authority.",
            "- Proposed blocks:",
            cap_blocks,
            "",
            "## Future Completion Target",
            "",
            "- Headline: `INVOICE SENT`.",
            "- Status now: future target, not current fact.",
            "- Required proof: email send receipt, Coupa submit or not-required proof, final PDF hash, approval receipts, and payment tracking receipt.",
            "",
            "## Boundary",
            "",
            "- No live chat parser, model call, procedure write, workflow run, or agent dispatch was added.",
            "- No Cassandra draft or Guardian approval was created.",
            "- No email draft/send, Coupa access/submit, invoice generation, attachment, or payment tracking write occurred.",
            "- No credentials, private bodies, browser, Gmail, Telegram, Mac sync/import, Swift change, network, or push occurred.",
            "",
            f"Next safe move: {report['next_safe_move']}",
            "",
        ]
    )


def write_exports(payload: dict[str, Any], export_root: Path) -> tuple[Path, Path]:
    export_root.mkdir(parents=True, exist_ok=True)
    json_path = export_root / JSON_EXPORT_NAME
    operator_path = export_root / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(format_operator_markdown(payload), encoding="utf-8")
    return json_path, operator_path


def build_summary(payload: dict[str, Any], json_path: Path | None, operator_path: Path | None) -> dict[str, Any]:
    capital_completion = payload["capital_hilton_example"]["invoice_sent_completion_target"]
    return {
        "schema_version": payload["schema_version"],
        "read_model_id": payload["read_model_id"],
        "contract_status": payload["contract_status"],
        "json_path": str(json_path) if json_path else None,
        "operator_path": str(operator_path) if operator_path else None,
        "generic_run_state": payload["governed_workflow_run_plan"]["current_state"],
        "capital_hilton_procedure": payload["capital_hilton_example"]["stored_procedure"]["procedure_name"],
        "capital_hilton_completion_headline": capital_completion["headline"],
        "invoice_sent_current_fact": not payload["machine_proof"]["invoice_sent_is_not_current_fact"],
        "all_live_authority_flags_false": payload["machine_proof"]["all_live_authority_flags_false"],
        "external_action_performed": payload["machine_proof"]["external_action_performed"],
        "content_hash": payload["machine_proof"]["content_hash"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export the conversational workflow memory contract read-model.")
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT))
    parser.add_argument("--format", choices=("summary", "json"), default="json")
    parser.add_argument("--generated-at", default=None)
    args = parser.parse_args(argv)

    payload = build_conversational_workflow_memory_contract(generated_at=args.generated_at)
    json_path, operator_path = write_exports(payload, Path(args.export_root))
    summary = build_summary(payload, json_path, operator_path)
    if args.format == "summary":
        print(stable_json(summary), end="")
    else:
        print(stable_json(payload), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
