"""Workflow Execution Package Compiler v0.

This deterministic read-model turns a reviewed workflow intent into scoped
worker package plans. It is a compiler contract, not an execution lane: it does
not dispatch agents, call tools, run workflows, generate invoices, access
external systems, request approvals, send messages, handle credentials, ingest
private bodies, mutate Mission Control, run Mac sync/import, or push.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_GENERATED_AT = "2026-05-24T00:00:00+00:00"

SCHEMA_VERSION = "workflow_execution_package_compiler_v0"
READ_MODEL_ID = "workflow_execution_package_compiler"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
OPERATOR_EXPORT_NAME = f"{READ_MODEL_ID}_OPERATOR.md"
CONTRACT_STATUS = "DETERMINISTIC_NON_EXECUTING_WORKFLOW_EXECUTION_PACKAGE_COMPILER"

SUPPORTED_WORKFLOW_TYPES = (
    "invoice_delivery_workflow",
    "contract_review_workflow",
    "creative_release_workflow",
    "client_delivery_workflow",
    "system_debug_workflow",
    "finance_tracking_workflow",
    "unknown_needs_framing",
)

READINESS_STATUSES = (
    "NOT_READY_MISSING_INPUTS",
    "READY_TO_COMPILE_PACKAGES",
    "PACKAGES_COMPILED_NOT_EXECUTABLE",
    "APPROVAL_REQUIRED",
    "EXECUTION_GATED",
    "COMPLETION_BLOCKED_MISSING_PROOF",
    "UNKNOWN_FAIL_CLOSED",
)

PACKAGE_TYPES = (
    "MAC_ARTIFACT_PREP_PACKAGE",
    "PC_BACKEND_VALIDATION_PACKAGE",
    "DRAFTING_AGENT_PACKAGE",
    "GUARDIAN_APPROVAL_PACKAGE",
    "PROTECTED_EVIDENCE_PACKAGE",
    "POST_OFFICE_HANDOFF_PACKAGE",
    "FINAL_READBACK_PACKAGE",
    "UNKNOWN_NEEDS_ROUTING",
)

PACKAGE_STATUSES = (
    "PACKAGE_PLAN_READY_NOT_EXECUTABLE",
    "BLOCKED_MISSING_INPUT",
    "BLOCKED_PENDING_APPROVAL",
    "BLOCKED_PENDING_PROOF",
    "FUTURE_TARGET_ONLY",
    "UNKNOWN_FAIL_CLOSED",
)

BLOCKER_TYPES = (
    "PACKAGE_CREATED_WITHOUT_REQUIRED_INPUT",
    "PACKAGE_EXECUTES_WITHOUT_APPROVAL",
    "EMAIL_SEND_WITHOUT_GUARDIAN_APPROVAL",
    "COUPA_SUBMIT_WITHOUT_PO_PROOF",
    "INVOICE_GENERATION_WITHOUT_ARTIFACT_CONTEXT",
    "ATTACHMENT_WITHOUT_HASH",
    "COMPLETION_WITHOUT_PROOF",
    "AGENT_DISPATCH_ATTEMPTED",
    "EXTERNAL_ACTION_ATTEMPTED",
    "RAW_PII_IN_PACKAGE",
    "CREDENTIAL_IN_PACKAGE",
    "UNKNOWN_FAIL_CLOSED",
)

LIVE_AUTHORITY_BOUNDARY = {
    "live_package_execution_allowed": False,
    "live_agent_dispatch_allowed": False,
    "live_tool_execution_allowed": False,
    "live_workflow_run_allowed": False,
    "live_email_draft_allowed": False,
    "live_email_send_allowed": False,
    "live_coupa_access_allowed": False,
    "live_coupa_submit_allowed": False,
    "live_browser_allowed": False,
    "live_invoice_generation_allowed": False,
    "live_attachment_allowed": False,
    "live_approval_request_allowed": False,
    "live_payment_tracking_write_allowed": False,
    "live_external_action_allowed": False,
    "credential_handling_allowed": False,
    "raw_body_ingestion_allowed": False,
    "live_model_call_allowed": False,
    "live_cross_machine_send_allowed": False,
    "mac_sync_import_allowed": False,
    "mission_control_swift_change_allowed": False,
    "git_push_pull_fetch_allowed": False,
    "network_allowed": False,
}

COMMON_PACKAGE_AUTHORITY_BOUNDARY = {
    "live_package_execution_allowed": False,
    "live_agent_dispatch_allowed": False,
    "live_tool_execution_allowed": False,
    "live_workflow_run_allowed": False,
    "live_external_action_allowed": False,
    "credential_handling_allowed": False,
    "raw_body_ingestion_allowed": False,
    "network_allowed": False,
}

EXPECTED_RETURN_FORMAT = (
    "STATUS",
    "SUMMARY",
    "RESULT",
    "VALIDATION",
    "READBACK",
    "BOUNDARY CHECK",
)

COMMON_EXCLUDED_CONTEXT = (
    "credentials",
    "tokens",
    "cookies",
    "raw message bodies",
    "private document bodies",
    "protected evidence bodies",
    "external account data",
)


@dataclass(frozen=True)
class WorkflowExecutionPackageCompiler:
    compiler_id: str
    doctrine: tuple[str, ...]
    supported_workflow_types: tuple[str, ...]
    source_intent_refs: tuple[str, ...]
    source_procedure_refs: tuple[str, ...]
    source_readback_refs: tuple[str, ...]
    package_compilation_policy: tuple[str, ...]
    missing_input_policy: tuple[str, ...]
    approval_gate_policy: tuple[str, ...]
    proof_policy: tuple[str, ...]
    role_dispatch_policy: tuple[str, ...]
    authority_boundary: dict[str, bool]
    next_safe_move: str


@dataclass(frozen=True)
class WorkflowExecutionReadiness:
    readiness_id: str
    workflow_ref: str
    workflow_type: str
    client_ref: str
    tenant_ref: str
    known_facts: tuple[str, ...]
    missing_inputs: tuple[str, ...]
    blocked_items: tuple[str, ...]
    ready_items: tuple[str, ...]
    required_artifacts: tuple[str, ...]
    required_proofs: tuple[str, ...]
    required_approvals: tuple[str, ...]
    readiness_status: str
    elioperator_summary: str
    next_safe_move: str


@dataclass(frozen=True)
class WorkerExecutionPackagePlan:
    package_plan_id: str
    workflow_ref: str
    package_type: str
    target_worker_type: str
    target_machine: str
    target_role: str
    package_goal: str
    included_context_refs: tuple[str, ...]
    excluded_context: tuple[str, ...]
    required_inputs: tuple[str, ...]
    allowed_actions: tuple[str, ...]
    forbidden_actions: tuple[str, ...]
    authority_boundary: dict[str, bool]
    proof_requirements: tuple[str, ...]
    validation_requirements: tuple[str, ...]
    expected_return_format: tuple[str, ...]
    readback_target: str
    package_status: str
    next_safe_move: str


@dataclass(frozen=True)
class WorkflowExecutionPackageChain:
    chain_id: str
    workflow_ref: str
    packages: tuple[str, ...]
    package_order: tuple[str, ...]
    parallelizable_packages: tuple[tuple[str, ...], ...]
    dependencies: tuple[dict[str, Any], ...]
    gates: tuple[str, ...]
    non_serial_work: tuple[str, ...]
    final_completion_condition: str
    proof_readback_plan: tuple[str, ...]
    next_safe_move: str


@dataclass(frozen=True)
class WorkflowMissingPieceNavigator:
    navigator_id: str
    workflow_ref: str
    missing_piece: str
    why_it_matters: str
    how_operator_can_answer: str
    who_or_what_can_help: tuple[str, ...]
    can_be_discovered_by_agent: bool
    required_proof: str
    next_question: str
    next_safe_move: str


@dataclass(frozen=True)
class WorkflowExecutionPackageBlocker:
    blocker_id: str
    blocker_type: str
    condition: str
    severity: str
    elioperator_warning: str
    fail_closed: bool
    next_safe_move: str


@dataclass(frozen=True)
class WorkflowExecutionPackageElioperatorReport:
    report_id: str
    plain_summary: str
    what_this_enables: str
    what_this_does_not_do_yet: str
    how_make_it_happen_works: str
    what_packages_are_needed: tuple[str, ...]
    what_is_missing_now: tuple[str, ...]
    what_gets_gated: tuple[str, ...]
    how_completion_is_proven: str
    next_safe_move: str


REQUIRED_COMPILER_FIELDS = tuple(WorkflowExecutionPackageCompiler.__dataclass_fields__.keys())
REQUIRED_READINESS_FIELDS = tuple(WorkflowExecutionReadiness.__dataclass_fields__.keys())
REQUIRED_PACKAGE_PLAN_FIELDS = tuple(WorkerExecutionPackagePlan.__dataclass_fields__.keys())
REQUIRED_CHAIN_FIELDS = tuple(WorkflowExecutionPackageChain.__dataclass_fields__.keys())
REQUIRED_NAVIGATOR_FIELDS = tuple(WorkflowMissingPieceNavigator.__dataclass_fields__.keys())
REQUIRED_BLOCKER_FIELDS = tuple(WorkflowExecutionPackageBlocker.__dataclass_fields__.keys())
REQUIRED_REPORT_FIELDS = tuple(WorkflowExecutionPackageElioperatorReport.__dataclass_fields__.keys())


def stable_json(data: Any) -> str:
    return json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _content_hash(payload: dict[str, Any]) -> str:
    clean = json.loads(stable_json(payload))
    clean.get("machine_proof", {}).pop("content_hash", None)
    return hashlib.sha256(stable_json(clean).encode("utf-8")).hexdigest()


def _model_schemas() -> dict[str, Any]:
    return {
        "workflow_execution_package_compiler": {"required_fields": list(REQUIRED_COMPILER_FIELDS)},
        "workflow_execution_readiness": {"required_fields": list(REQUIRED_READINESS_FIELDS)},
        "worker_execution_package_plan": {"required_fields": list(REQUIRED_PACKAGE_PLAN_FIELDS)},
        "workflow_execution_package_chain": {"required_fields": list(REQUIRED_CHAIN_FIELDS)},
        "workflow_missing_piece_navigator": {"required_fields": list(REQUIRED_NAVIGATOR_FIELDS)},
        "workflow_execution_package_blocker": {"required_fields": list(REQUIRED_BLOCKER_FIELDS)},
        "workflow_execution_package_elioperator_report": {"required_fields": list(REQUIRED_REPORT_FIELDS)},
    }


def build_compiler() -> WorkflowExecutionPackageCompiler:
    return WorkflowExecutionPackageCompiler(
        compiler_id="workflow_execution_package_compiler_v0",
        doctrine=(
            "Chat is the operator surface.",
            "Router and workflow memory determine the workflow type.",
            "The compiler creates scoped worker package plans only.",
            "Workers act only inside their allowed lane after a future gated send.",
            "External actions remain gated.",
            "Receipts and readbacks decide truth.",
            "Completion requires proof.",
        ),
        supported_workflow_types=SUPPORTED_WORKFLOW_TYPES,
        source_intent_refs=(
            "conversational_workflow_router_contract",
            "conversational_workflow_router_readback",
            "chat_readback_card_mirror",
        ),
        source_procedure_refs=(
            "conversational_workflow_memory_contract",
            "capital_hilton_invoice_workflow_draft",
        ),
        source_readback_refs=(
            "capital_hilton_delivery_facts_capture_writer",
            "capital_hilton_invoice_artifact_generator",
            "guardian_draft_approval_request_contract",
            "cross_surface_artifact_handoff_registry_contract",
            "cross_machine_worker_dispatch_package",
        ),
        package_compilation_policy=(
            "Compile package plans from reviewed intent, known facts, missing inputs, gates, and proof requirements.",
            "Do not execute a package from this compiler.",
            "Do not dispatch an agent from this compiler.",
            "Do not send, submit, browse, approve, attach, generate invoices, or update payment state.",
            "Use package plans to show what worker lanes would be needed and what remains blocked.",
        ),
        missing_input_policy=(
            "Missing inputs remain explicit and operator-readable.",
            "A missing input can create a navigator question but not a fake fact.",
            "Unknowns fail closed until operator answer, protected proof, or future approved discovery rail exists.",
        ),
        approval_gate_policy=(
            "External-facing draft, send, submit, and approval actions remain gated.",
            "Guardian approval packages are plans only in this contract.",
            "No approval is requested or granted by this compiler.",
        ),
        proof_policy=(
            "Completion labels require proof receipts.",
            "Artifact attachment requires an artifact hash.",
            "Coupa submit requires PO/reference proof or a not-required proof.",
            "Final readback must list missing receipts instead of claiming success.",
        ),
        role_dispatch_policy=(
            "Roles are package targets, not live dispatches.",
            "Cassandra and Guardian may be candidate roles only.",
            "Cross-machine worker packages remain ready-not-sent unless a future approved handoff rail is used.",
        ),
        authority_boundary=LIVE_AUTHORITY_BOUNDARY,
        next_safe_move="Show readiness, missing pieces, and package plan chain to the operator before any future package send.",
    )


def build_capital_hilton_readiness() -> WorkflowExecutionReadiness:
    return WorkflowExecutionReadiness(
        readiness_id="readiness_capital_hilton_make_it_happen",
        workflow_ref="capital_hilton_invoice_workflow",
        workflow_type="invoice_delivery_workflow",
        client_ref="Capital Hilton",
        tenant_ref="openclaw_local_operator",
        known_facts=(
            "4 performance dates captured",
            "$400/show",
            "$1,600 basis",
            "invoice preview exists",
            "Capital Hilton invoice workflow draft understood",
            "Excel/PDF companion invoice desired",
            "Annette contact candidate",
            "Coupa/PO payment rail candidate",
            "invoice should be saved for records",
        ),
        missing_inputs=(
            "exact Coupa PO/reference",
            "confirmation Annette is correct contact",
            "final Winship-branded Excel/PDF artifact/hash",
            "Guardian approval",
            "send/submit receipts",
        ),
        blocked_items=(
            "email send",
            "Coupa access/submit",
            "browser automation",
            "approval request",
            "invoice generation if artifact rail not ready",
            "attachment if artifact hash missing",
            "payment tracking update",
        ),
        ready_items=(
            "package plan compilation",
            "missing-piece questions",
            "metadata-only proof requirements",
            "operator-readable readiness readback",
        ),
        required_artifacts=(
            "Winship-branded Excel/PDF invoice artifact",
            "artifact hash",
            "draft email packet",
            "Guardian approval receipt",
            "Coupa/PO proof or not-required proof",
            "send/submit receipts",
        ),
        required_proofs=(
            "current dates/rate/subtotal readback",
            "Coupa PO/reference proof or explicit not-required posture",
            "artifact hash proof",
            "Guardian approval proof",
            "external send receipt",
            "Coupa submit receipt if required",
            "payment tracking update receipt",
        ),
        required_approvals=(
            "operator review of package chain",
            "Guardian approval before external send/submit",
            "operator approval before any future external action adapter runs",
        ),
        readiness_status="NOT_READY_MISSING_INPUTS",
        elioperator_summary=(
            "I can plan the Capital Hilton invoice workflow, but it is not runnable yet. "
            "The PO/reference, contact confirmation, artifact hash, approval, and receipts are still missing."
        ),
        next_safe_move="Ask for the PO/reference and contact confirmation, then compile ready-not-sent worker package plans.",
    )


def _package_plan(
    *,
    package_plan_id: str,
    package_type: str,
    target_worker_type: str,
    target_machine: str,
    target_role: str,
    package_goal: str,
    included_context_refs: tuple[str, ...],
    required_inputs: tuple[str, ...],
    allowed_actions: tuple[str, ...],
    forbidden_actions: tuple[str, ...],
    proof_requirements: tuple[str, ...],
    validation_requirements: tuple[str, ...],
    readback_target: str,
    package_status: str,
    next_safe_move: str,
) -> WorkerExecutionPackagePlan:
    return WorkerExecutionPackagePlan(
        package_plan_id=package_plan_id,
        workflow_ref="capital_hilton_invoice_workflow",
        package_type=package_type,
        target_worker_type=target_worker_type,
        target_machine=target_machine,
        target_role=target_role,
        package_goal=package_goal,
        included_context_refs=included_context_refs,
        excluded_context=COMMON_EXCLUDED_CONTEXT,
        required_inputs=required_inputs,
        allowed_actions=allowed_actions,
        forbidden_actions=forbidden_actions,
        authority_boundary=COMMON_PACKAGE_AUTHORITY_BOUNDARY,
        proof_requirements=proof_requirements,
        validation_requirements=validation_requirements,
        expected_return_format=EXPECTED_RETURN_FORMAT,
        readback_target=readback_target,
        package_status=package_status,
        next_safe_move=next_safe_move,
    )


def build_capital_hilton_package_plans() -> tuple[WorkerExecutionPackagePlan, ...]:
    return (
        _package_plan(
            package_plan_id="package_plan_capital_hilton_pc_backend_validation",
            package_type="PC_BACKEND_VALIDATION_PACKAGE",
            target_worker_type="PC_CODEX",
            target_machine="PC_WSL",
            target_role="validation_agent",
            package_goal="Confirm current dates/rate/subtotal and missing delivery facts from deterministic read-models.",
            included_context_refs=(
                "capital_hilton_delivery_facts_capture_writer",
                "capital_hilton_invoice_artifact_generator",
                "conversational_workflow_router_readback",
            ),
            required_inputs=("existing generated read-models",),
            allowed_actions=("read generated read-models", "run focused validation", "return missing-fact readback"),
            forbidden_actions=("Coupa access", "browser automation", "email draft/send", "approval request", "state mutation beyond generated read-model"),
            proof_requirements=("dates/rate/subtotal readback", "missing fact list", "no external authority proof"),
            validation_requirements=("focused pytest", "JSON parse", "authority scan"),
            readback_target="Capital Hilton readiness card",
            package_status="PACKAGE_PLAN_READY_NOT_EXECUTABLE",
            next_safe_move="Use this plan to verify backend facts before any future artifact or draft package.",
        ),
        _package_plan(
            package_plan_id="package_plan_capital_hilton_mac_artifact_prep",
            package_type="MAC_ARTIFACT_PREP_PACKAGE",
            target_worker_type="MAC_CODEX",
            target_machine="MAC",
            target_role="artifact_generation_agent",
            package_goal="Prepare or verify the Winship-branded Excel/PDF invoice artifact when an approved Mac artifact rail exists.",
            included_context_refs=(
                "capital_hilton_invoice_artifact_generator",
                "cross_machine_worker_dispatch_package",
            ),
            required_inputs=("confirmed dates/rate/subtotal", "artifact template or existing preview posture", "Mac-side file boundary approval"),
            allowed_actions=("prepare artifact package instructions", "verify expected artifact hash requirements", "return Mac-side artifact readiness readback"),
            forbidden_actions=("send email", "mutate external systems", "Coupa access", "browser automation", "destructive file operations"),
            proof_requirements=("artifact path posture", "artifact hash", "no external action proof"),
            validation_requirements=("Mac-local validation in future worker lane", "artifact hash check if artifact exists"),
            readback_target="artifact readiness card",
            package_status="BLOCKED_MISSING_INPUT",
            next_safe_move="Keep this as a package plan until artifact rail and hash are available.",
        ),
        _package_plan(
            package_plan_id="package_plan_capital_hilton_protected_evidence",
            package_type="PROTECTED_EVIDENCE_PACKAGE",
            target_worker_type="PC_CODEX",
            target_machine="PC_WSL",
            target_role="protected_evidence_agent",
            package_goal="Reference proof/source metadata without exposing private bodies.",
            included_context_refs=(
                "cross_surface_artifact_handoff_registry_contract",
                "openclaw_sensitive_policy",
                "capital_hilton_delivery_facts_capture_writer",
            ),
            required_inputs=("metadata-only proof refs", "protected boundary posture"),
            allowed_actions=("compile proof reference checklist", "return protected-ref requirements"),
            forbidden_actions=("open protected bodies", "include credentials", "copy private documents", "external account access"),
            proof_requirements=("metadata-only proof refs", "private body exclusion proof"),
            validation_requirements=("PII/private-body scan", "authority scan"),
            readback_target="protected proof checklist",
            package_status="PACKAGE_PLAN_READY_NOT_EXECUTABLE",
            next_safe_move="Use metadata refs only; ask Guardian if a protected source must be reviewed later.",
        ),
        _package_plan(
            package_plan_id="package_plan_capital_hilton_drafting_agent",
            package_type="DRAFTING_AGENT_PACKAGE",
            target_worker_type="CASSANDRA",
            target_machine="LOCAL_ONLY",
            target_role="drafting_agent",
            package_goal="Prepare future email draft language to Annette with an artifact reference.",
            included_context_refs=(
                "conversational_workflow_memory_contract",
                "cassandra_draft_review_packet",
                "capital_hilton_delivery_facts_capture_writer",
            ),
            required_inputs=("confirmed contact", "artifact hash/reference", "draft scope"),
            allowed_actions=("draft text for review", "surface missing inputs", "return draft readback"),
            forbidden_actions=("send", "create live email draft", "attach file", "request approval automatically"),
            proof_requirements=("draft review packet", "artifact reference", "contact confirmation"),
            validation_requirements=("machine-language scan", "no external action scan"),
            readback_target="draft ready for review card",
            package_status="BLOCKED_MISSING_INPUT",
            next_safe_move="Do not draft as complete until contact and artifact hash exist.",
        ),
        _package_plan(
            package_plan_id="package_plan_capital_hilton_guardian_approval",
            package_type="GUARDIAN_APPROVAL_PACKAGE",
            target_worker_type="GUARDIAN",
            target_machine="LOCAL_ONLY",
            target_role="approval_agent",
            package_goal="Request approval before any future external send or submit adapter runs.",
            included_context_refs=(
                "guardian_draft_approval_request_contract",
                "capital_hilton_send_approval_gate",
            ),
            required_inputs=("draft packet", "artifact hash", "recipient/contact confirmation", "Coupa/PO posture"),
            allowed_actions=("prepare approval request package", "list approval prerequisites"),
            forbidden_actions=("request live approval now", "send", "submit", "override operator approval"),
            proof_requirements=("Guardian approval receipt", "operator approval receipt"),
            validation_requirements=("approval-boundary scan", "authority scan"),
            readback_target="approval needed card",
            package_status="BLOCKED_PENDING_APPROVAL",
            next_safe_move="Wait for complete draft/artifact/proof context before any approval request package is actionable.",
        ),
        _package_plan(
            package_plan_id="package_plan_capital_hilton_post_office_handoff",
            package_type="POST_OFFICE_HANDOFF_PACKAGE",
            target_worker_type="PC_CODEX",
            target_machine="PC_WSL",
            target_role="post_office_handoff",
            package_goal="Route package/readback metadata through the cross-surface handoff registry when future handoff is approved.",
            included_context_refs=(
                "cross_surface_artifact_handoff_registry_contract",
                "cross_surface_handoff_registry_metadata_alignment",
                "cross_machine_worker_dispatch_package",
            ),
            required_inputs=("compiled package refs", "safe readback refs", "target surface"),
            allowed_actions=("compile handoff metadata plan", "return Mac-readable readback target"),
            forbidden_actions=("cross-machine send", "Mac sync/import", "watcher/daemon creation", "external action"),
            proof_requirements=("handoff metadata manifest if created later", "source hash if package later exists"),
            validation_requirements=("JSON parse", "manifest hash validation if future manifest exists"),
            readback_target="same-chat package status card",
            package_status="PACKAGE_PLAN_READY_NOT_EXECUTABLE",
            next_safe_move="Keep handoff as metadata plan until a future approved shuttle step is requested.",
        ),
        _package_plan(
            package_plan_id="package_plan_capital_hilton_final_readback",
            package_type="FINAL_READBACK_PACKAGE",
            target_worker_type="PC_CODEX",
            target_machine="PC_WSL",
            target_role="final_readback_agent",
            package_goal="Produce the completion proof card only after required receipts exist.",
            included_context_refs=(
                "workflow_readback_concierge_contract",
                "chat_workflow_run_state_visual_feed",
                "capital_hilton_delivery_facts_capture_writer",
            ),
            required_inputs=("send receipt", "submit receipt if required", "artifact hash", "payment tracking receipt"),
            allowed_actions=("compile final readback plan", "list missing receipts", "block fake completion"),
            forbidden_actions=("show INVOICE SENT without proof", "write payment tracking state", "send or submit"),
            proof_requirements=("send/submit receipts", "saved artifact proof", "last invoice date update proof", "payment tracking update proof"),
            validation_requirements=("completion proof scan", "authority scan"),
            readback_target="INVOICE SENT future completion card",
            package_status="BLOCKED_PENDING_PROOF",
            next_safe_move="Keep completion blocked until proof receipts exist.",
        ),
    )


def build_capital_hilton_package_chain(plans: tuple[WorkerExecutionPackagePlan, ...]) -> WorkflowExecutionPackageChain:
    ids = tuple(plan.package_plan_id for plan in plans)
    return WorkflowExecutionPackageChain(
        chain_id="package_chain_capital_hilton_make_it_happen",
        workflow_ref="capital_hilton_invoice_workflow",
        packages=ids,
        package_order=ids,
        parallelizable_packages=(
            (
                "package_plan_capital_hilton_pc_backend_validation",
                "package_plan_capital_hilton_protected_evidence",
            ),
            (
                "package_plan_capital_hilton_post_office_handoff",
                "package_plan_capital_hilton_final_readback",
            ),
        ),
        dependencies=(
            {
                "package": "package_plan_capital_hilton_mac_artifact_prep",
                "depends_on": ("package_plan_capital_hilton_pc_backend_validation",),
                "reason": "Artifact package needs confirmed invoice basis.",
            },
            {
                "package": "package_plan_capital_hilton_drafting_agent",
                "depends_on": ("package_plan_capital_hilton_mac_artifact_prep",),
                "reason": "Draft needs artifact reference/hash and confirmed contact.",
            },
            {
                "package": "package_plan_capital_hilton_guardian_approval",
                "depends_on": ("package_plan_capital_hilton_drafting_agent",),
                "reason": "Guardian approval package needs draft, recipient/contact posture, and artifact proof.",
            },
            {
                "package": "package_plan_capital_hilton_final_readback",
                "depends_on": ("future_external_receipts",),
                "reason": "Completion is blocked until send/submit/payment receipts exist.",
            },
        ),
        gates=(
            "operator confirms missing facts",
            "artifact hash exists before attachment",
            "Guardian approval before external send/submit",
            "Coupa PO/reference proof before Coupa submit",
            "send/submit receipts before completion",
        ),
        non_serial_work=(
            "Ask missing-piece questions while package plans are visible.",
            "Backend validation and protected proof checklist can be planned in parallel.",
            "Post-office metadata planning can wait until package refs exist.",
        ),
        final_completion_condition="INVOICE SENT can appear only after required send/submit/artifact/payment receipts exist.",
        proof_readback_plan=(
            "List known facts and missing proofs before execution.",
            "Show approval needed before any external adapter.",
            "Show completion blocked if receipts are missing.",
            "Show INVOICE SENT only with proof bullets.",
        ),
        next_safe_move="Present this package chain as ready-not-executable and ask the operator for the PO/reference or contact confirmation.",
    )


def build_missing_piece_navigators() -> tuple[WorkflowMissingPieceNavigator, ...]:
    return (
        WorkflowMissingPieceNavigator(
            navigator_id="navigator_capital_hilton_coupa_po_reference",
            workflow_ref="capital_hilton_invoice_workflow",
            missing_piece="exact Coupa PO/reference",
            why_it_matters="Coupa submit cannot be planned as complete without proof of the official payment rail reference.",
            how_operator_can_answer="Provide the PO/reference, say it is unknown and should remain open, or provide an approved protected proof ref later.",
            who_or_what_can_help=("operator", "future protected evidence review", "future governed Coupa adapter"),
            can_be_discovered_by_agent=False,
            required_proof="Coupa PO/reference proof or explicit not-required posture.",
            next_question="What Coupa PO/reference should this invoice use, or should OpenClaw keep that as an open discovery item?",
            next_safe_move="Ask for PO/reference before any Coupa package claims readiness.",
        ),
        WorkflowMissingPieceNavigator(
            navigator_id="navigator_capital_hilton_contact_confirmation",
            workflow_ref="capital_hilton_invoice_workflow",
            missing_piece="confirmation Annette is correct contact",
            why_it_matters="A draft or send package should not treat a contact candidate as confirmed truth.",
            how_operator_can_answer="Confirm Annette, name a different contact, or keep contact confirmation open.",
            who_or_what_can_help=("operator", "future Cassandra draft review", "protected contact proof if needed"),
            can_be_discovered_by_agent=False,
            required_proof="operator confirmation or safe contact proof ref.",
            next_question="Is Annette the right contact for the companion invoice email?",
            next_safe_move="Keep the contact as candidate until operator confirmation exists.",
        ),
        WorkflowMissingPieceNavigator(
            navigator_id="navigator_capital_hilton_artifact_hash",
            workflow_ref="capital_hilton_invoice_workflow",
            missing_piece="final Winship-branded Excel/PDF artifact/hash",
            why_it_matters="Attachment and final readback require a concrete artifact proof.",
            how_operator_can_answer="Point to an approved artifact proof or ask for a future Mac artifact package.",
            who_or_what_can_help=("Mac Codex artifact prep package", "PC backend validation package"),
            can_be_discovered_by_agent=False,
            required_proof="artifact hash and safe artifact reference.",
            next_question="Should OpenClaw prepare a Mac artifact package later, or do you already have the final artifact proof?",
            next_safe_move="Do not attach or claim artifact readiness until a hash exists.",
        ),
        WorkflowMissingPieceNavigator(
            navigator_id="navigator_capital_hilton_guardian_approval",
            workflow_ref="capital_hilton_invoice_workflow",
            missing_piece="Guardian approval",
            why_it_matters="External send/submit actions require approval before any future adapter can run.",
            how_operator_can_answer="Review the completed draft/artifact/proof package and approve through the future Guardian rail.",
            who_or_what_can_help=("Guardian approval package", "operator"),
            can_be_discovered_by_agent=False,
            required_proof="Guardian approval receipt and operator approval receipt.",
            next_question="After draft and artifact proof exist, should Guardian review this for send/submit approval?",
            next_safe_move="Keep send/submit locked until approval receipts exist.",
        ),
        WorkflowMissingPieceNavigator(
            navigator_id="navigator_capital_hilton_send_submit_receipts",
            workflow_ref="capital_hilton_invoice_workflow",
            missing_piece="send/submit receipts",
            why_it_matters="Completion cannot say INVOICE SENT without proof receipts.",
            how_operator_can_answer="Use future governed adapters and return receipts, or keep completion pending.",
            who_or_what_can_help=("future email adapter", "future Coupa adapter", "final readback agent"),
            can_be_discovered_by_agent=False,
            required_proof="email send receipt and Coupa submit receipt if required.",
            next_question="Do you want this to remain a ready package plan until the future send/submit rails exist?",
            next_safe_move="Show completion as blocked missing proof.",
        ),
    )


def build_blockers() -> tuple[WorkflowExecutionPackageBlocker, ...]:
    details = {
        "PACKAGE_CREATED_WITHOUT_REQUIRED_INPUT": (
            "A package claims readiness while a required input is absent.",
            "This package is missing a required piece. Keep it as a plan and ask for the missing input.",
        ),
        "PACKAGE_EXECUTES_WITHOUT_APPROVAL": (
            "A package attempts execution without approval.",
            "Package planning is allowed; execution is not allowed from this lane.",
        ),
        "EMAIL_SEND_WITHOUT_GUARDIAN_APPROVAL": (
            "Email send is attempted before Guardian approval.",
            "Send remains locked until Guardian and operator approvals exist.",
        ),
        "COUPA_SUBMIT_WITHOUT_PO_PROOF": (
            "Coupa submit is attempted without PO/reference proof.",
            "Coupa submit remains locked until the payment rail reference is proven or explicitly parked.",
        ),
        "INVOICE_GENERATION_WITHOUT_ARTIFACT_CONTEXT": (
            "Invoice generation is attempted without artifact context.",
            "Prepare artifact context and hash requirements before any invoice artifact rail runs.",
        ),
        "ATTACHMENT_WITHOUT_HASH": (
            "Attachment is attempted without artifact hash.",
            "Do not attach or claim attachment readiness until artifact hash proof exists.",
        ),
        "COMPLETION_WITHOUT_PROOF": (
            "Completion is claimed without required proof receipts.",
            "Do not show completion. List the missing receipts instead.",
        ),
        "AGENT_DISPATCH_ATTEMPTED": (
            "An agent is dispatched from the compiler.",
            "This compiler creates package plans only; dispatch must use a future gated rail.",
        ),
        "EXTERNAL_ACTION_ATTEMPTED": (
            "A package tries to send, submit, browse, approve, attach, or update payment state.",
            "Strip the external action and show the gate that would be required later.",
        ),
        "RAW_PII_IN_PACKAGE": (
            "A package includes raw private identifiers or private bodies.",
            "Use sanitized summaries and metadata-only refs.",
        ),
        "CREDENTIAL_IN_PACKAGE": (
            "A package includes credentials or credential-like material.",
            "Remove credentials and fail closed.",
        ),
        "UNKNOWN_FAIL_CLOSED": (
            "The compiler cannot classify the package state.",
            "Fail closed and ask for clarification.",
        ),
    }
    blockers = []
    for blocker_type, (condition, warning) in details.items():
        blockers.append(
            WorkflowExecutionPackageBlocker(
                blocker_id=f"workflow_execution_package_blocker_{blocker_type.lower()}",
                blocker_type=blocker_type,
                condition=condition,
                severity="HIGH" if blocker_type != "UNKNOWN_FAIL_CLOSED" else "CRITICAL",
                elioperator_warning=warning,
                fail_closed=True,
                next_safe_move="Keep the package as a non-executing plan and return an operator-readable blocker.",
            )
        )
    return tuple(blockers)


def build_elioperator_report(readiness: WorkflowExecutionReadiness) -> WorkflowExecutionPackageElioperatorReport:
    return WorkflowExecutionPackageElioperatorReport(
        report_id="workflow_execution_package_elioperator_report_v0",
        plain_summary="This turns 'make it happen' into a governed package plan, not execution.",
        what_this_enables=(
            "OpenClaw can show what is known, what is missing, which worker packages are needed, "
            "and what proof is required before completion."
        ),
        what_this_does_not_do_yet=(
            "It does not run packages, dispatch agents, send email, access Coupa, open a browser, "
            "generate invoices, request approvals, attach files, or update payment tracking."
        ),
        how_make_it_happen_works=(
            "The compiler reads the reviewed workflow intent/readback, builds readiness, splits work into scoped package plans, "
            "and returns missing-piece questions plus proof gates."
        ),
        what_packages_are_needed=PACKAGE_TYPES[:-1],
        what_is_missing_now=readiness.missing_inputs,
        what_gets_gated=(
            "email send",
            "Coupa submit",
            "browser access",
            "approval request",
            "invoice generation",
            "attachment",
            "payment tracking update",
        ),
        how_completion_is_proven=(
            "Completion requires receipts: artifact hash, approval, send/submit proofs, saved invoice proof, "
            "last invoice date update proof, and payment tracking receipt."
        ),
        next_safe_move="Ask for the PO/reference or contact confirmation, then keep package plans visible but not executable.",
    )


def build_future_completion_target() -> dict[str, Any]:
    return {
        "completion_label": "INVOICE SENT",
        "headline": "INVOICE SENT",
        "completion_allowed": False,
        "blocked_reason": "Proof receipts do not exist yet.",
        "future_target_only": True,
        "proof_bullets": (
            "Coupa invoice generated/submitted from PO, if required and proven.",
            "Email sent to Annette with Winship-branded Excel/PDF invoice attached.",
            "Invoice artifact saved with today's date.",
            "Last invoice date recorded for future invoice range.",
            "Send/submit receipts attached.",
            "Payment tracking state updated.",
        ),
        "next_safe_move": "Keep completion blocked until receipts prove each bullet.",
    }


def build_capital_hilton_example() -> dict[str, Any]:
    readiness = build_capital_hilton_readiness()
    package_plans = build_capital_hilton_package_plans()
    chain = build_capital_hilton_package_chain(package_plans)
    navigators = build_missing_piece_navigators()
    return {
        "source_operator_command": "Make the Capital Hilton invoice workflow happen.",
        "workflow_execution_readiness": asdict(readiness),
        "worker_execution_package_plans": {
            plan.package_plan_id: asdict(plan)
            for plan in package_plans
        },
        "workflow_execution_package_chain": asdict(chain),
        "workflow_missing_piece_navigators": {
            navigator.navigator_id: asdict(navigator)
            for navigator in navigators
        },
        "future_completion_target": build_future_completion_target(),
        "operator_readback": {
            "what_is_known": readiness.known_facts,
            "what_is_missing": readiness.missing_inputs,
            "what_is_blocked": readiness.blocked_items,
            "what_can_be_prepared_now": readiness.ready_items,
            "what_requires_approval": readiness.required_approvals,
            "what_proves_completion": readiness.required_proofs,
        },
    }


def _all_authority_flags_false(payload: dict[str, Any]) -> bool:
    if any(payload["authority_boundary"].values()):
        return False
    plans = payload["capital_hilton_example"]["worker_execution_package_plans"].values()
    return all(not any(plan["authority_boundary"].values()) for plan in plans)


def _no_external_action_performed(payload: dict[str, Any]) -> bool:
    completion = payload["capital_hilton_example"]["future_completion_target"]
    plans = payload["capital_hilton_example"]["worker_execution_package_plans"].values()
    return (
        completion["completion_allowed"] is False
        and all(plan["package_status"] != "EXECUTED" for plan in plans)
    )


def _machine_proof(payload: dict[str, Any]) -> dict[str, Any]:
    example = payload["capital_hilton_example"]
    plans = example["worker_execution_package_plans"]
    plan_types = {plan["package_type"] for plan in plans.values()}
    blockers = payload["workflow_execution_package_blockers_by_id"].values()
    blocker_types = {blocker["blocker_type"] for blocker in blockers}
    readiness = example["workflow_execution_readiness"]
    return {
        "workflow_execution_package_compiler_model_present": True,
        "workflow_execution_readiness_model_present": True,
        "worker_execution_package_plan_model_present": True,
        "workflow_execution_package_chain_model_present": True,
        "workflow_missing_piece_navigator_model_present": True,
        "workflow_execution_package_blocker_model_present": True,
        "workflow_execution_package_elioperator_report_model_present": True,
        "supported_workflow_types_present": set(SUPPORTED_WORKFLOW_TYPES).issubset(payload["supported_workflow_types"]),
        "readiness_statuses_present": set(READINESS_STATUSES).issubset(payload["readiness_statuses"]),
        "package_types_present": set(PACKAGE_TYPES).issubset(payload["package_types"]),
        "capital_hilton_readiness_example_exists": readiness["workflow_type"] == "invoice_delivery_workflow",
        "capital_hilton_known_items_modeled": all(
            item in readiness["known_facts"]
            for item in ("4 performance dates captured", "$400/show", "$1,600 basis", "invoice preview exists")
        ),
        "capital_hilton_missing_items_modeled": all(
            item in readiness["missing_inputs"]
            for item in ("exact Coupa PO/reference", "confirmation Annette is correct contact", "Guardian approval")
        ),
        "capital_hilton_blocked_items_modeled": all(
            item in readiness["blocked_items"]
            for item in ("email send", "Coupa access/submit", "browser automation")
        ),
        "expected_package_types_exist": set(PACKAGE_TYPES[:-1]).issubset(plan_types),
        "package_chain_exists": bool(example["workflow_execution_package_chain"]["packages"]),
        "missing_piece_navigator_exists": bool(example["workflow_missing_piece_navigators"]),
        "completion_target_blocked_without_proof": example["future_completion_target"]["completion_allowed"] is False,
        "blockers_present": set(BLOCKER_TYPES).issubset(blocker_types),
        "all_live_authority_flags_false": _all_authority_flags_false(payload),
        "external_action_performed": not _no_external_action_performed(payload),
        "agent_dispatch_performed": False,
        "workflow_run_performed": False,
        "tool_execution_performed": False,
        "email_draft_or_send_performed": False,
        "coupa_access_or_submit_performed": False,
        "browser_access_performed": False,
        "invoice_generation_performed": False,
        "approval_request_performed": False,
        "payment_tracking_write_performed": False,
        "credentials_or_secrets_included": False,
        "raw_private_bodies_included": False,
        "raw_pii_in_packages": False,
        "network_used": False,
        "mac_sync_import_run": False,
        "mission_control_swift_changed": False,
        "git_push_pull_fetch_run": False,
        "content_hash": None,
    }


def build_workflow_execution_package_compiler(*, generated_at: str | None = None) -> dict[str, Any]:
    generated_at = generated_at or DEFAULT_GENERATED_AT
    compiler = build_compiler()
    example = build_capital_hilton_example()
    readiness = WorkflowExecutionReadiness(**example["workflow_execution_readiness"])
    blockers = build_blockers()
    report = build_elioperator_report(readiness)
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "contract_status": CONTRACT_STATUS,
        "generated_at": generated_at,
        "operator_markdown_mode": "ELIOPERATOR",
        "supported_workflow_types": SUPPORTED_WORKFLOW_TYPES,
        "readiness_statuses": READINESS_STATUSES,
        "package_types": PACKAGE_TYPES,
        "package_statuses": PACKAGE_STATUSES,
        "model_schemas": _model_schemas(),
        "workflow_execution_package_compiler": asdict(compiler),
        "workflow_execution_readiness": example["workflow_execution_readiness"],
        "worker_execution_package_plans_by_id": example["worker_execution_package_plans"],
        "workflow_execution_package_chain": example["workflow_execution_package_chain"],
        "workflow_missing_piece_navigators_by_id": example["workflow_missing_piece_navigators"],
        "workflow_execution_package_blockers_by_id": {
            blocker.blocker_id: asdict(blocker)
            for blocker in blockers
        },
        "workflow_execution_package_elioperator_report": asdict(report),
        "capital_hilton_example": example,
        "relationship_refs": {
            "conversational_workflow_memory_contract": "procedure and governed run pattern",
            "conversational_workflow_router_contract": "workflow/domain classification",
            "conversational_workflow_router_intake": "Mac chat request intake and routed intent readback",
            "chat_readback_card_mirror": "operator-visible card source",
            "workflow_readback_concierge_contract": "same-chat readback navigation",
            "cross_machine_worker_dispatch_package": "worker/machine routing boundary",
            "package_compiler_contract": "package schema and preview-only doctrine",
            "agent_execution_packet_compiler_contract": "agent package authority filtering",
            "guardian_draft_approval_request_contract": "approval gate posture",
            "cross_surface_artifact_handoff_registry_contract": "post-office handoff posture",
            "capital_hilton_delivery_facts_capture_writer": "known/missing delivery fact posture",
            "capital_hilton_invoice_artifact_generator": "artifact preview/readiness posture",
        },
        "allowed_contract_scope": (
            "deterministic package plan generation",
            "read-model generation",
            "tests",
            "ELIOPERATOR report",
        ),
        "authority_boundary": LIVE_AUTHORITY_BOUNDARY,
    }
    payload["machine_proof"] = _machine_proof(payload)
    payload["machine_proof"]["content_hash"] = _content_hash(payload)
    return payload


def format_operator_markdown(payload: dict[str, Any]) -> str:
    report = payload["workflow_execution_package_elioperator_report"]
    readiness = payload["workflow_execution_readiness"]
    chain = payload["workflow_execution_package_chain"]
    completion = payload["capital_hilton_example"]["future_completion_target"]
    package_lines = "\n".join(
        f"- {plan['package_type']}: {plan['package_goal']} (`{plan['package_status']}`)"
        for plan in payload["worker_execution_package_plans_by_id"].values()
    )
    missing_lines = "\n".join(f"- {item}" for item in readiness["missing_inputs"])
    blocked_lines = "\n".join(f"- {item}" for item in readiness["blocked_items"])
    proof_lines = "\n".join(f"- {item}" for item in completion["proof_bullets"])
    return "\n".join(
        [
            "# Workflow Execution Package Compiler v0",
            "",
            "ELIOPERATOR: This turns 'make it happen' into a governed package plan. It does not execute anything.",
            "",
            "## What This Enables",
            "",
            report["what_this_enables"],
            "",
            "## What This Does Not Do Yet",
            "",
            report["what_this_does_not_do_yet"],
            "",
            "## Capital Hilton Readiness",
            "",
            readiness["elioperator_summary"],
            "",
            "## Missing Now",
            "",
            missing_lines,
            "",
            "## Blocked",
            "",
            blocked_lines,
            "",
            "## Package Chain",
            "",
            package_lines,
            "",
            "## Gates",
            "",
            "\n".join(f"- {gate}" for gate in chain["gates"]),
            "",
            "## Future Completion Target",
            "",
            f"- Headline: {completion['headline']}",
            f"- Completion allowed now: `{completion['completion_allowed']}`",
            f"- Blocked reason: {completion['blocked_reason']}",
            "",
            "Proof required before completion:",
            "",
            proof_lines,
            "",
            "## Boundary",
            "",
            "No package execution, agent dispatch, tool execution, workflow run, email draft/send, Coupa access/submit, browser, invoice generation, attachment, approval request, payment tracking write, external action, credential handling, raw-body ingestion, Mac sync/import, Swift change, or push was added.",
            "",
            f"Next safe move: {payload['workflow_execution_package_compiler']['next_safe_move']}",
            "",
        ]
    )


def write_exports(payload: dict[str, Any], export_root: Path = DEFAULT_EXPORT_ROOT) -> tuple[Path, Path]:
    export_root.mkdir(parents=True, exist_ok=True)
    json_path = export_root / JSON_EXPORT_NAME
    operator_path = export_root / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(format_operator_markdown(payload), encoding="utf-8")
    return json_path, operator_path


def build_summary(payload: dict[str, Any], json_path: Path | None, operator_path: Path | None) -> dict[str, Any]:
    proof = payload["machine_proof"]
    readiness = payload["workflow_execution_readiness"]
    return {
        "schema_version": payload["schema_version"],
        "read_model_id": payload["read_model_id"],
        "contract_status": payload["contract_status"],
        "json_path": str(json_path) if json_path else None,
        "operator_path": str(operator_path) if operator_path else None,
        "workflow_type": readiness["workflow_type"],
        "readiness_status": readiness["readiness_status"],
        "package_count": len(payload["worker_execution_package_plans_by_id"]),
        "missing_count": len(readiness["missing_inputs"]),
        "blocked_count": len(readiness["blocked_items"]),
        "expected_package_types_exist": proof["expected_package_types_exist"],
        "package_chain_exists": proof["package_chain_exists"],
        "completion_target_blocked_without_proof": proof["completion_target_blocked_without_proof"],
        "all_live_authority_flags_false": proof["all_live_authority_flags_false"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export the workflow execution package compiler read-model.")
    parser.add_argument("--export-root", type=Path, default=DEFAULT_EXPORT_ROOT)
    parser.add_argument("--format", choices=("summary", "json"), default="json")
    args = parser.parse_args(argv)

    payload = build_workflow_execution_package_compiler()
    json_path, operator_path = write_exports(payload, args.export_root)
    output = payload if args.format == "json" else build_summary(payload, json_path, operator_path)
    sys.stdout.write(stable_json(output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
