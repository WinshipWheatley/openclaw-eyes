"""Conversational Workflow Router Contract v0.

This deterministic read-model defines the generic backend router shape for a
chat-first OpenClaw surface. A chat message can become human-facing cards and
backend-facing package targets, but not truth, execution, procedure memory, live
agent dispatch, model parsing, approval, send, submit, browser/Coupa/Gmail
access, invoice generation, credential handling, raw-body ingestion, or any
external action.
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

SCHEMA_VERSION = "conversational_workflow_router_contract_v0"
READ_MODEL_ID = "conversational_workflow_router_contract"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
OPERATOR_EXPORT_NAME = f"{READ_MODEL_ID}_OPERATOR.md"
CONTRACT_STATUS = "DETERMINISTIC_NON_EXECUTING_CONVERSATIONAL_WORKFLOW_ROUTER_CONTRACT"

WORKFLOW_TYPES = (
    "invoice_delivery_workflow",
    "contract_review_workflow",
    "creative_release_workflow",
    "client_delivery_workflow",
    "system_debug_workflow",
    "finance_tracking_workflow",
    "unknown_needs_framing",
)

REQUIRED_ROLES = (
    "drafting_agent",
    "validation_agent",
    "finance_delivery_agent",
    "protected_evidence_agent",
    "approval_agent",
    "artifact_generation_agent",
    "post_office_handoff",
    "final_readback_agent",
)

CARD_TYPES = (
    "OPENCLAW_UNDERSTOOD",
    "PROPOSED_WORKFLOW",
    "MISSING_INFO",
    "APPROVAL_NEEDED",
    "PROOF_OR_READBACK",
    "BLOCKED",
    "COMPLETION_TARGET",
)

PACKAGE_TYPES = (
    "WORKFLOW_MEMORY_PROPOSAL",
    "GOVERNED_RUN_PLAN",
    "DRAFT_REVIEW_PACKET",
    "APPROVAL_REQUEST_PACKET",
    "PROTECTED_EVIDENCE_PACKET",
    "ARTIFACT_GENERATION_PACKET",
    "POST_OFFICE_HANDOFF_PACKET",
    "UNKNOWN_NEEDS_FRAMING",
)

BLOCKER_TYPES = (
    "MESSAGE_TREATED_AS_TRUTH",
    "MODEL_PARSER_CLAIMED_BUT_NOT_AVAILABLE",
    "AGENT_DISPATCH_ATTEMPTED",
    "PROCEDURE_MEMORY_WRITE_ATTEMPTED",
    "WORKFLOW_RUN_ATTEMPTED",
    "EXTERNAL_ACTION_ATTEMPTED",
    "RAW_PII_IN_NORMAL_READMODEL",
    "MACHINE_CONTRACT_VISIBLE_TO_OPERATOR",
    "UNSUPPORTED_WORKFLOW_TYPE",
    "UNKNOWN_FAIL_CLOSED",
)

REQUIRED_ROUTER_FIELDS = (
    "router_id",
    "doctrine",
    "supported_input_surfaces",
    "supported_workflow_domains",
    "routing_policy",
    "parser_policy",
    "model_call_policy",
    "role_package_policy",
    "human_readback_policy",
    "backend_package_policy",
    "authority_boundary",
    "privacy_boundary",
    "current_live_authority",
    "next_safe_move",
)

REQUIRED_MESSAGE_FIELDS = (
    "message_id",
    "origin_surface",
    "source_channel",
    "operator_ref",
    "tenant_ref",
    "client_ref",
    "world_ref",
    "lane_ref",
    "raw_message_allowed_in_normal_read_model",
    "sanitized_message_summary",
    "privacy_class",
    "possible_sensitive_content",
    "received_at_policy",
    "next_safe_move",
)

REQUIRED_INTENT_FIELDS = (
    "intent_id",
    "source_message_ref",
    "workflow_type",
    "domain_ref",
    "client_ref",
    "tenant_ref",
    "intent_summary",
    "confidence",
    "candidate_goal",
    "candidate_entities",
    "candidate_unknowns",
    "candidate_risks",
    "operator_review_required",
    "parser_mode",
    "model_parser_available",
    "next_safe_move",
)

REQUIRED_TARGET_FIELDS = (
    "target_id",
    "routed_intent_ref",
    "required_roles",
    "candidate_agents",
    "package_type",
    "package_context_requirements",
    "excluded_context",
    "sensitivity_policy",
    "authority_gates",
    "proof_requirements",
    "approval_requirements",
    "can_dispatch_now",
    "dispatch_block_reason",
    "next_safe_move",
)

REQUIRED_CARD_READBACK_FIELDS = (
    "readback_id",
    "routed_intent_ref",
    "cards",
    "default_card_order",
    "operator_choices",
    "hidden_diagnostics_available",
    "machine_contract_visible",
    "safe_display_summary",
    "next_safe_move",
)

REQUIRED_PACKAGE_REQUEST_FIELDS = (
    "package_request_id",
    "routed_intent_ref",
    "package_type",
    "workflow_type",
    "role_targets",
    "required_inputs",
    "required_artifacts",
    "required_proofs",
    "required_gates",
    "blocked_actions",
    "ready_actions",
    "output_readback_target",
    "can_create_now",
    "create_block_reason",
    "next_safe_move",
)

REQUIRED_BLOCKER_FIELDS = (
    "blocker_id",
    "blocker_type",
    "condition",
    "severity",
    "elioperator_warning",
    "fail_closed",
    "next_safe_move",
)

REQUIRED_REPORT_FIELDS = (
    "report_id",
    "plain_summary",
    "what_this_enables",
    "what_this_does_not_do_yet",
    "how_chat_routes_to_packages",
    "how_cards_help_the_operator",
    "how_backend_packages_remain_gated",
    "how_truth_is_confirmed",
    "next_safe_move",
)

LIVE_AUTHORITY_BOUNDARY = {
    "live_chat_parser_allowed": False,
    "live_model_call_allowed": False,
    "live_router_dispatch_allowed": False,
    "live_package_creation_allowed": False,
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
    "model_call_allowed": False,
    "agent_activation_allowed": False,
    "tool_execution_allowed": False,
    "queue_execution_allowed": False,
    "runtime_dispatch_allowed": False,
}

RELATIONSHIP_CANDIDATES = (
    "conversational_workflow_memory_contract.py",
    "cross_surface_artifact_handoff_registry_contract.py",
    "cross_surface_handoff_registry_metadata_alignment.py",
    "cross_lane_reusable_block_registry_contract.py",
    "workflow_block_intent_live_draft_contract.py",
    "operator_question_assist_scope_expansion_contract.py",
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
class ConversationalWorkflowRouter:
    router_id: str
    doctrine: dict[str, Any]
    supported_input_surfaces: tuple[str, ...]
    supported_workflow_domains: tuple[str, ...]
    routing_policy: dict[str, Any]
    parser_policy: dict[str, Any]
    model_call_policy: dict[str, Any]
    role_package_policy: dict[str, Any]
    human_readback_policy: dict[str, Any]
    backend_package_policy: dict[str, Any]
    authority_boundary: dict[str, Any]
    privacy_boundary: dict[str, Any]
    current_live_authority: dict[str, Any]
    next_safe_move: str


@dataclass(frozen=True)
class ChatWorkflowMessage:
    message_id: str
    origin_surface: str
    source_channel: str
    operator_ref: str
    tenant_ref: str
    client_ref: str
    world_ref: str
    lane_ref: str
    raw_message_allowed_in_normal_read_model: bool
    sanitized_message_summary: str
    privacy_class: str
    possible_sensitive_content: tuple[str, ...]
    received_at_policy: str
    next_safe_move: str


@dataclass(frozen=True)
class RoutedWorkflowIntent:
    intent_id: str
    source_message_ref: str
    workflow_type: str
    domain_ref: str
    client_ref: str
    tenant_ref: str
    intent_summary: str
    confidence: str
    candidate_goal: str
    candidate_entities: dict[str, Any]
    candidate_unknowns: tuple[str, ...]
    candidate_risks: tuple[str, ...]
    operator_review_required: bool
    parser_mode: str
    model_parser_available: bool
    next_safe_move: str


@dataclass(frozen=True)
class ModelOrRolePackageTarget:
    target_id: str
    routed_intent_ref: str
    required_roles: tuple[str, ...]
    candidate_agents: dict[str, Any]
    package_type: str
    package_context_requirements: tuple[str, ...]
    excluded_context: tuple[str, ...]
    sensitivity_policy: dict[str, Any]
    authority_gates: tuple[dict[str, Any], ...]
    proof_requirements: tuple[str, ...]
    approval_requirements: tuple[str, ...]
    can_dispatch_now: bool
    dispatch_block_reason: str
    next_safe_move: str


@dataclass(frozen=True)
class HumanCardReadback:
    readback_id: str
    routed_intent_ref: str
    cards: tuple[dict[str, Any], ...]
    default_card_order: tuple[str, ...]
    operator_choices: tuple[str, ...]
    hidden_diagnostics_available: bool
    machine_contract_visible: bool
    safe_display_summary: str
    next_safe_move: str


@dataclass(frozen=True)
class BackendPackageRequest:
    package_request_id: str
    routed_intent_ref: str
    package_type: str
    workflow_type: str
    role_targets: tuple[str, ...]
    required_inputs: tuple[str, ...]
    required_artifacts: tuple[str, ...]
    required_proofs: tuple[str, ...]
    required_gates: tuple[str, ...]
    blocked_actions: tuple[str, ...]
    ready_actions: tuple[str, ...]
    output_readback_target: str
    can_create_now: bool
    create_block_reason: str
    next_safe_move: str


@dataclass(frozen=True)
class RouterBlocker:
    blocker_id: str
    blocker_type: str
    condition: str
    severity: str
    elioperator_warning: str
    fail_closed: bool
    next_safe_move: str


@dataclass(frozen=True)
class RouterElioperatorReport:
    report_id: str
    plain_summary: str
    what_this_enables: str
    what_this_does_not_do_yet: str
    how_chat_routes_to_packages: str
    how_cards_help_the_operator: str
    how_backend_packages_remain_gated: str
    how_truth_is_confirmed: str
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


def build_router() -> ConversationalWorkflowRouter:
    return ConversationalWorkflowRouter(
        router_id="conversational_workflow_router_v0",
        doctrine={
            "chat_is_input_not_truth": True,
            "human_cards_explain_work": True,
            "backend_packages_prepare_context": True,
            "receipts_and_readbacks_decide_truth": True,
            "external_actions_remain_gated": True,
        },
        supported_input_surfaces=(
            "Mission Control chat",
            "Telegram or Cassandra fronting surface",
            "CLI/operator text",
            "future mobile or voice surface",
        ),
        supported_workflow_domains=(
            "finance",
            "client delivery",
            "creative release",
            "contract review",
            "system debug",
            "unknown needs framing",
        ),
        routing_policy={
            "deterministic_draft_router_first": True,
            "operator_review_required": True,
            "unsupported_workflows_fail_closed": True,
            "capital_hilton_is_example_not_special_core": True,
        },
        parser_policy={
            "parser_mode": "deterministic_draft_router",
            "raw_message_is_not_canonical_truth": True,
            "structured_output_is_candidate": True,
        },
        model_call_policy={
            "live_model_call_allowed": False,
            "model_parser_available": False,
            "future_model_parser_requires_approved_rail": True,
        },
        role_package_policy={
            "roles_are_generic": True,
            "candidate_agents_are_examples": True,
            "live_agent_dispatch_allowed": False,
        },
        human_readback_policy={
            "cards_use_plain_language": True,
            "machine_contract_visible": False,
            "cards_do_not_claim_truth_changed": True,
        },
        backend_package_policy={
            "package_targets_are_metadata_only": True,
            "live_package_creation_allowed": False,
            "future_package_creation_requires_safe_path": True,
        },
        authority_boundary=LIVE_AUTHORITY_BOUNDARY,
        privacy_boundary={
            "raw_message_allowed_in_normal_read_model": False,
            "safe_summary_required": True,
            "raw_pii_forbidden": True,
            "protected_values_require_reference_or_token": True,
        },
        current_live_authority=LIVE_AUTHORITY_BOUNDARY,
        next_safe_move="Use deterministic routing to produce human cards and backend package targets for review.",
    )


def _model_schemas() -> dict[str, Any]:
    return {
        "conversational_workflow_router": {"required_fields": list(REQUIRED_ROUTER_FIELDS)},
        "chat_workflow_message": {"required_fields": list(REQUIRED_MESSAGE_FIELDS)},
        "routed_workflow_intent": {"required_fields": list(REQUIRED_INTENT_FIELDS)},
        "model_or_role_package_target": {"required_fields": list(REQUIRED_TARGET_FIELDS)},
        "human_card_readback": {"required_fields": list(REQUIRED_CARD_READBACK_FIELDS)},
        "backend_package_request": {"required_fields": list(REQUIRED_PACKAGE_REQUEST_FIELDS)},
        "router_blocker": {"required_fields": list(REQUIRED_BLOCKER_FIELDS)},
        "router_elioperator_report": {"required_fields": list(REQUIRED_REPORT_FIELDS)},
    }


def _relationship_inventory() -> dict[str, Any]:
    return {
        Path(path).stem: {
            "path": path,
            "present": (ROOT / path).exists()
            or (ROOT / "generated/read_models" / path.replace(".py", ".json")).exists(),
            "relationship": _relationship_note(Path(path).stem),
        }
        for path in RELATIONSHIP_CANDIDATES
    }


def _relationship_note(stem: str) -> str:
    notes = {
        "conversational_workflow_memory_contract": "router hands off to workflow-memory proposal shape",
        "cross_surface_artifact_handoff_registry_contract": "post-office metadata for future typed handoffs",
        "cross_surface_handoff_registry_metadata_alignment": "additive metadata compatibility for packages",
        "cross_lane_reusable_block_registry_contract": "safe reusable facts and tokenized protected values",
        "workflow_block_intent_live_draft_contract": "draft intent substrate for candidate work",
        "operator_question_assist_scope_expansion_contract": "plain-language questions for missing info",
        "agent_conversation_handoff_step_packet_contract": "future role packet exchange shape",
        "agent_execution_packet_compiler_contract": "future package target shape without execution",
        "bridge_routing_operator_attention_contract": "human attention/readback routing",
        "capital_hilton_delivery_facts_capture_writer": "Capital Hilton local receipt/write proof example",
        "capital_hilton_delivery_facts_capture_bridge": "Capital Hilton missing fact/capture readiness",
        "capital_hilton_invoice_artifact_generator": "Capital Hilton local artifact preview readback",
        "guardian_protected_access_gate_spec": "protected evidence and approval posture",
        "openclaw_sensitive_policy": "privacy and sensitive-material boundary",
        "business_ops_ledger": "receipt/state substrate referenced but not mutated",
    }
    return notes.get(stem, "related router dependency if present")


def build_capital_hilton_message() -> ChatWorkflowMessage:
    return ChatWorkflowMessage(
        message_id="chat_message_capital_hilton_annette_excel_coupa_v0",
        origin_surface="Mission Control chat",
        source_channel="operator_chat",
        operator_ref="local_operator",
        tenant_ref="openclaw_repo_a_local",
        client_ref="Capital Hilton",
        world_ref="finance",
        lane_ref="Capital Hilton",
        raw_message_allowed_in_normal_read_model=False,
        sanitized_message_summary=(
            "Prepare Capital Hilton invoice delivery: companion Excel/Winship PDF for Annette candidate, "
            "official payment rail is Coupa from PO, and PO/Coupa plus contact confirmation are still needed."
        ),
        privacy_class="sanitized_client_business_context",
        possible_sensitive_content=("contact role", "payment reference", "protected Coupa proof"),
        received_at_policy="not recorded as live receipt in this contract",
        next_safe_move="Route to invoice delivery workflow as candidate understanding for operator review.",
    )


def build_capital_hilton_intent(message: ChatWorkflowMessage) -> RoutedWorkflowIntent:
    return RoutedWorkflowIntent(
        intent_id="routed_intent_capital_hilton_invoice_delivery_v0",
        source_message_ref=message.message_id,
        workflow_type="invoice_delivery_workflow",
        domain_ref="finance",
        client_ref="Capital Hilton",
        tenant_ref=message.tenant_ref,
        intent_summary="Prepare and review Capital Hilton invoice delivery workflow.",
        confidence="deterministic_high_for_capital_hilton_invoice_keywords",
        candidate_goal="prepare/review invoice delivery workflow",
        candidate_entities={
            "client": "Capital Hilton",
            "destination_contact_candidate": "Annette",
            "companion_invoice": "Excel-generated / Winship-branded PDF invoice",
            "official_payment_rail": "Coupa supplier portal / PO",
            "known_local_state": {
                "performance_dates": ("2026-05-08", "2026-05-15", "2026-05-22", "2026-05-29"),
                "rate": "$400/show",
                "subtotal": "$1,600",
            },
        },
        candidate_unknowns=(
            "confirmed PO/Coupa reference",
            "confirmed recipient/contact",
            "final artifact path and hash",
            "Guardian/operator approval receipt",
            "send/submit result receipts",
        ),
        candidate_risks=(
            "narrative cannot be treated as stored procedure truth",
            "contact and payment references may be sensitive",
            "external actions must remain locked",
        ),
        operator_review_required=True,
        parser_mode="deterministic_draft_router",
        model_parser_available=False,
        next_safe_move="Produce draft understanding and proposed workflow cards for operator review.",
    )


def build_capital_hilton_target(intent: RoutedWorkflowIntent) -> ModelOrRolePackageTarget:
    return ModelOrRolePackageTarget(
        target_id="package_target_capital_hilton_invoice_delivery_v0",
        routed_intent_ref=intent.intent_id,
        required_roles=REQUIRED_ROLES,
        candidate_agents={
            "Cassandra": "candidate drafting or finance-delivery role only; no dispatch",
            "Guardian": "candidate approval or protected-evidence role only; no approval request",
        },
        package_type="WORKFLOW_MEMORY_PROPOSAL",
        package_context_requirements=(
            "sanitized chat summary",
            "Capital Hilton workflow memory example",
            "invoice artifact preview readback",
            "delivery facts capture bridge/readback",
            "authority and proof gates",
        ),
        excluded_context=(
            "raw email bodies",
            "raw screenshots",
            "credentials",
            "browser session state",
            "private payment identifiers",
        ),
        sensitivity_policy={
            "raw_contact_value_allowed": False,
            "raw_payment_reference_allowed": False,
            "protected_evidence_body_allowed": False,
            "safe_labels_allowed": True,
        },
        authority_gates=(
            {"gate": "operator workflow review", "granted": False},
            {"gate": "artifact hash proof", "granted": False},
            {"gate": "Guardian/operator approval", "granted": False},
            {"gate": "email adapter", "granted": False},
            {"gate": "Coupa adapter", "granted": False},
        ),
        proof_requirements=(
            "confirmed PO/Coupa reference or explicit no-PO posture",
            "confirmed payment contact",
            "final invoice artifact path/hash",
            "Guardian/operator approval receipt",
            "send/submit proof receipts before completion",
        ),
        approval_requirements=(
            "operator review of workflow understanding",
            "Guardian/operator approval over exact draft, attachment, and Coupa scope",
        ),
        can_dispatch_now=False,
        dispatch_block_reason="Router contract has no live agent dispatch or package execution authority.",
        next_safe_move="Prepare readback cards and park backend package target for future gated worker.",
    )


def build_capital_hilton_cards(intent: RoutedWorkflowIntent) -> HumanCardReadback:
    cards = (
        {
            "card_id": "capital_hilton_openclaw_understood",
            "card_type": "OPENCLAW_UNDERSTOOD",
            "title": "OpenClaw understood",
            "bullets": (
                "Goal: prepare Capital Hilton invoice workflow.",
                "Destination/contact: Annette appears to be the payment follow-up contact candidate.",
                "Companion invoice: Excel-generated / Winship-branded PDF invoice.",
                "Official payment rail: Coupa supplier portal / PO.",
                "Proof/source: Excel PDF plus Coupa/PO proof or reference.",
                "Still missing: confirmed PO/Coupa reference, confirmed recipient/contact, final artifact, Guardian approval.",
                "External actions: locked.",
            ),
        },
        {
            "card_id": "capital_hilton_proposed_workflow",
            "card_type": "PROPOSED_WORKFLOW",
            "title": "Proposed workflow",
            "bullets": (
                "Confirm dates and rate.",
                "Prepare invoice artifact.",
                "Confirm PO/Coupa.",
                "Confirm contact.",
                "Prepare draft.",
                "Request approval.",
                "Send or submit only through gates.",
                "Read back proof.",
            ),
        },
        {
            "card_id": "capital_hilton_not_happening",
            "card_type": "BLOCKED",
            "title": "What is not happening",
            "bullets": (
                "No email sent.",
                "No Coupa access.",
                "No browser opened.",
                "No approval requested.",
                "No invoice submitted.",
            ),
        },
    )
    return HumanCardReadback(
        readback_id="human_card_readback_capital_hilton_invoice_delivery_v0",
        routed_intent_ref=intent.intent_id,
        cards=cards,
        default_card_order=tuple(card["card_id"] for card in cards),
        operator_choices=("Looks right", "Edit understanding", "Prepare package later", "Cancel"),
        hidden_diagnostics_available=True,
        machine_contract_visible=False,
        safe_display_summary=(
            "OpenClaw can show a draft understanding and proposed workflow; nothing external happened."
        ),
        next_safe_move="Ask the operator whether the understanding looks right.",
    )


def build_capital_hilton_package_request(intent: RoutedWorkflowIntent) -> BackendPackageRequest:
    return BackendPackageRequest(
        package_request_id="backend_package_request_capital_hilton_workflow_memory_proposal_v0",
        routed_intent_ref=intent.intent_id,
        package_type="WORKFLOW_MEMORY_PROPOSAL",
        workflow_type="invoice_delivery_workflow",
        role_targets=(
            "drafting_agent",
            "finance_delivery_agent",
            "protected_evidence_agent",
            "approval_agent",
            "artifact_generation_agent",
            "post_office_handoff",
            "final_readback_agent",
        ),
        required_inputs=(
            "operator-reviewed understanding",
            "confirmed PO/Coupa reference or no-PO posture",
            "confirmed recipient/contact",
        ),
        required_artifacts=("final invoice artifact path/hash", "reviewed draft packet", "approval packet"),
        required_proofs=(
            "Coupa proof or not-required proof",
            "Guardian/operator approval receipt",
            "send/submit result receipts before completion",
        ),
        required_gates=(
            "operator review gate",
            "artifact hash gate",
            "protected evidence gate",
            "Guardian/operator approval gate",
            "external adapter gate",
        ),
        blocked_actions=(
            "email draft/send",
            "Coupa access/submit",
            "browser automation",
            "approval request",
            "invoice generation",
            "attachment",
            "payment tracking write",
        ),
        ready_actions=("show draft understanding", "show proposed workflow", "ask next missing fact question"),
        output_readback_target="human cards plus future workflow memory proposal readback",
        can_create_now=False,
        create_block_reason=(
            "No live package creation path is enabled in this router contract; output is deterministic read-model only."
        ),
        next_safe_move="Use cards for operator review; build a future safe package writer separately.",
    )


def build_blockers() -> tuple[RouterBlocker, ...]:
    conditions = {
        "MESSAGE_TREATED_AS_TRUTH": "A chat message is treated as canonical fact or stored procedure without review.",
        "MODEL_PARSER_CLAIMED_BUT_NOT_AVAILABLE": "Router claims a live model parser exists without approved evidence.",
        "AGENT_DISPATCH_ATTEMPTED": "Router dispatches an agent instead of producing a target package.",
        "PROCEDURE_MEMORY_WRITE_ATTEMPTED": "Router writes procedure memory without a future receipt writer.",
        "WORKFLOW_RUN_ATTEMPTED": "Router starts a workflow run from a chat message.",
        "EXTERNAL_ACTION_ATTEMPTED": "Router attempts email, Coupa, browser, submit, send, or other external action.",
        "RAW_PII_IN_NORMAL_READMODEL": "Router places raw sensitive values in normal read-models or cards.",
        "MACHINE_CONTRACT_VISIBLE_TO_OPERATOR": "Normal human cards expose schema, handler, package IDs, or manifests.",
        "UNSUPPORTED_WORKFLOW_TYPE": "Message cannot be safely routed to a supported workflow type.",
        "UNKNOWN_FAIL_CLOSED": "Routing, proof, privacy, or authority posture is ambiguous.",
    }
    return tuple(
        RouterBlocker(
            blocker_id=f"router_blocker_{blocker_type.lower()}",
            blocker_type=blocker_type,
            condition=condition,
            severity="BLOCKS_SAFE_ROUTING",
            elioperator_warning=f"ELIOPERATOR: {condition}",
            fail_closed=True,
            next_safe_move="Fail closed into operator review or clarifying question.",
        )
        for blocker_type, condition in conditions.items()
    )


def build_report() -> RouterElioperatorReport:
    return RouterElioperatorReport(
        report_id="conversational_workflow_router_elioperator_report_v0",
        plain_summary=(
            "The router turns a chat message into human-readable cards and backend package targets."
        ),
        what_this_enables=(
            "A chat-first app can show what OpenClaw understood, what workflow is proposed, what is missing, "
            "what is blocked, and which future package/role lane is needed."
        ),
        what_this_does_not_do_yet=(
            "It does not parse with a live model, dispatch agents, write procedure memory, start a workflow, "
            "create packages, draft, approve, send, submit, browse, access Coupa/Gmail, or mutate external state."
        ),
        how_chat_routes_to_packages=(
            "The sanitized message becomes a candidate workflow intent, then a role/package target and package request."
        ),
        how_cards_help_the_operator=(
            "Cards explain the goal, proposed workflow, missing facts, approval/proof needs, and blocked actions."
        ),
        how_backend_packages_remain_gated=(
            "Package requests list roles, inputs, artifacts, proofs, and gates but cannot create or dispatch now."
        ),
        how_truth_is_confirmed=(
            "Receipts and readbacks confirm truth; the routed message is candidate meaning only."
        ),
        next_safe_move="Surface this read-model to Mac or build a future deterministic package writer.",
    )


def build_generic_examples() -> dict[str, Any]:
    return {
        "generic_invoice_message": {
            "message_summary": "Operator asks to prepare an invoice delivery.",
            "workflow_type": "invoice_delivery_workflow",
            "domain_ref": "finance",
            "operator_review_required": True,
            "external_action_allowed": False,
        },
        "generic_system_debug_message": {
            "message_summary": "Operator reports that a local workflow or app behavior is broken.",
            "workflow_type": "system_debug_workflow",
            "domain_ref": "engineering",
            "operator_review_required": True,
            "external_action_allowed": False,
        },
        "generic_creative_release_message": {
            "message_summary": "Operator wants help preparing a creative release package.",
            "workflow_type": "creative_release_workflow",
            "domain_ref": "creative",
            "operator_review_required": True,
            "external_action_allowed": False,
        },
        "unknown_message": {
            "message_summary": "Operator request is too ambiguous to route safely.",
            "workflow_type": "unknown_needs_framing",
            "next_question": "What outcome do you want OpenClaw to prepare?",
            "external_action_allowed": False,
        },
    }


def build_capital_hilton_example() -> dict[str, Any]:
    message = build_capital_hilton_message()
    intent = build_capital_hilton_intent(message)
    target = build_capital_hilton_target(intent)
    cards = build_capital_hilton_cards(intent)
    package_request = build_capital_hilton_package_request(intent)
    return {
        "input_summary": message.sanitized_message_summary,
        "chat_message": asdict(message),
        "routed_intent": asdict(intent),
        "role_package_target": asdict(target),
        "human_card_readback": asdict(cards),
        "backend_package_request": asdict(package_request),
        "external_locks": {
            "email": "locked",
            "Coupa": "locked",
            "browser": "locked",
            "approval": "locked",
            "invoice_submit": "locked",
        },
        "next_safe_move": "Show cards and ask whether the understanding looks right.",
    }


def _machine_proof(payload: dict[str, Any]) -> dict[str, Any]:
    capital = payload["capital_hilton_example"]
    intent = capital["routed_intent"]
    target = capital["role_package_target"]
    readback = capital["human_card_readback"]
    package = capital["backend_package_request"]
    blocker_types = {item["blocker_type"] for item in payload["router_blockers_by_id"].values()}
    example_keys = set(payload["generic_examples"])
    normal_card_text = stable_json(readback["cards"]).lower()
    machine_terms_in_cards = any(
        token in normal_card_text
        for token in ("schema", "handler", "manifest", "package_request_id", "payload_hash")
    )
    return {
        "conversational_workflow_router_model_present": True,
        "chat_workflow_message_model_present": True,
        "routed_workflow_intent_model_present": True,
        "model_or_role_package_target_model_present": True,
        "human_card_readback_model_present": True,
        "backend_package_request_model_present": True,
        "router_blockers_model_present": True,
        "router_elioperator_report_model_present": True,
        "generic_invoice_example_present": "generic_invoice_message" in example_keys,
        "generic_debug_example_present": "generic_system_debug_message" in example_keys,
        "generic_creative_example_present": "generic_creative_release_message" in example_keys,
        "generic_unknown_example_present": "unknown_message" in example_keys,
        "capital_hilton_routes_to_invoice_delivery": intent["workflow_type"] == "invoice_delivery_workflow",
        "capital_hilton_routes_to_finance": intent["domain_ref"] == "finance",
        "capital_hilton_client_ref_present": intent["client_ref"] == "Capital Hilton",
        "capital_hilton_operator_review_required": intent["operator_review_required"] is True,
        "capital_hilton_model_parser_available": intent["model_parser_available"],
        "capital_hilton_cards_have_expected_understanding": any(
            card["card_type"] == "OPENCLAW_UNDERSTOOD" and "External actions: locked." in card["bullets"]
            for card in readback["cards"]
        ),
        "backend_package_external_actions_locked": package["can_create_now"] is False
        and target["can_dispatch_now"] is False,
        "message_is_not_treated_as_truth": "MESSAGE_TREATED_AS_TRUTH" in blocker_types
        and payload["chat_workflow_message"]["raw_message_allowed_in_normal_read_model"] is False,
        "no_live_model_call": payload["authority_boundary"]["live_model_call_allowed"] is False,
        "no_live_agent_dispatch": payload["authority_boundary"]["live_agent_dispatch_allowed"] is False,
        "no_live_workflow_run": payload["authority_boundary"]["live_workflow_run_allowed"] is False,
        "no_live_external_action": payload["authority_boundary"]["live_external_action_allowed"] is False,
        "machine_contract_visible_false": readback["machine_contract_visible"] is False,
        "machine_terms_absent_from_normal_cards": not machine_terms_in_cards,
        "all_required_roles_present": all(role in target["required_roles"] for role in REQUIRED_ROLES),
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


def build_conversational_workflow_router_contract(*, generated_at: str | None = None) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    router = build_router()
    capital = build_capital_hilton_example()
    generic_examples = build_generic_examples()
    blockers = build_blockers()
    report = build_report()
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "contract_status": CONTRACT_STATUS,
        "generated_at": generated_at,
        "operator_markdown_mode": "ELIOPERATOR",
        "workflow_types": WORKFLOW_TYPES,
        "card_types": CARD_TYPES,
        "package_types": PACKAGE_TYPES,
        "model_schemas": _model_schemas(),
        "conversational_workflow_router": asdict(router),
        "chat_workflow_message": capital["chat_message"],
        "routed_workflow_intent": capital["routed_intent"],
        "model_or_role_package_target": capital["role_package_target"],
        "human_card_readback": capital["human_card_readback"],
        "backend_package_request": capital["backend_package_request"],
        "router_blockers_by_id": {blocker.blocker_id: asdict(blocker) for blocker in blockers},
        "router_elioperator_report": asdict(report),
        "generic_examples": generic_examples,
        "capital_hilton_example": capital,
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
    report = payload["router_elioperator_report"]
    cards = payload["capital_hilton_example"]["human_card_readback"]["cards"]
    card_text = []
    for card in cards:
        card_text.append(f"### {card['title']}")
        card_text.extend(f"- {bullet}" for bullet in card["bullets"])
        card_text.append("")
    return "\n".join(
        [
            "# Conversational Workflow Router Contract v0",
            "",
            "ELIOPERATOR: Chat is the operator surface. The router decides what kind of work the message implies, then prepares human cards and backend package targets. Nothing executes just because a message was routed.",
            "",
            "## What This Enables",
            "",
            report["what_this_enables"],
            "",
            "## How It Works",
            "",
            "- A sanitized chat message becomes candidate intent.",
            "- The router creates plain-language cards for the app.",
            "- The router also identifies future role/package targets below deck.",
            "- Receipts and readbacks decide truth.",
            "- External actions remain gated.",
            "",
            "## Capital Hilton Example Cards",
            "",
            *card_text,
            "## Boundary",
            "",
            "- No live chat parser or model call was used.",
            "- No router dispatch, agent dispatch, procedure write, or workflow run occurred.",
            "- No Cassandra draft or Guardian approval was created.",
            "- No email draft/send, Coupa access/submit, invoice generation, attachment, payment tracking write, credential handling, or external action occurred.",
            "- No Mac sync/import, Swift change, network, or push occurred.",
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
    intent = payload["capital_hilton_example"]["routed_intent"]
    package = payload["capital_hilton_example"]["backend_package_request"]
    return {
        "schema_version": payload["schema_version"],
        "read_model_id": payload["read_model_id"],
        "contract_status": payload["contract_status"],
        "json_path": str(json_path) if json_path else None,
        "operator_path": str(operator_path) if operator_path else None,
        "capital_hilton_workflow_type": intent["workflow_type"],
        "capital_hilton_domain": intent["domain_ref"],
        "capital_hilton_package_type": package["package_type"],
        "can_create_package_now": package["can_create_now"],
        "all_live_authority_flags_false": payload["machine_proof"]["all_live_authority_flags_false"],
        "external_action_performed": payload["machine_proof"]["external_action_performed"],
        "content_hash": payload["machine_proof"]["content_hash"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export the conversational workflow router contract read-model.")
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT))
    parser.add_argument("--format", choices=("summary", "json"), default="json")
    parser.add_argument("--generated-at", default=None)
    args = parser.parse_args(argv)

    payload = build_conversational_workflow_router_contract(generated_at=args.generated_at)
    json_path, operator_path = write_exports(payload, Path(args.export_root))
    summary = build_summary(payload, json_path, operator_path)
    if args.format == "summary":
        print(stable_json(summary), end="")
    else:
        print(stable_json(payload), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
