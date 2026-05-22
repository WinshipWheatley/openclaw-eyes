"""Tool Adapter Receipt Contract v0 for OpenClaw.

This read-model defines deterministic receipts for tool/protocol adapter
lookup, allow, block, quarantine, and future-gate decisions. It is metadata
only: no live tool execution, model calls, agent activation, browser/OAuth or
account access, Gmail/calendar/Coupa/Telegram authority, send/submit/approval,
queue/autonomy, runtime daemon, file mutation authority, network operation,
Repo B execution, Mac sync/import, or PC system-drive writes are created.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
DEFAULT_EXPORT_ROOT = Path("generated/read_models")

SCHEMA_VERSION = "tool_adapter_receipt_contract_v0"
JSON_EXPORT_NAME = "tool_adapter_receipt_contract.json"
OPERATOR_EXPORT_NAME = "tool_adapter_receipt_contract_OPERATOR.md"

NO_AUTHORITY_FLAGS = {
    "runtime_authority": False,
    "tool_execution_authority": False,
    "live_tool_execution": False,
    "model_call_authority": False,
    "model_api_execution_authority": False,
    "model_router_runtime_authority": False,
    "actor_agent_activation_authority": False,
    "browser_oauth_account_access_enabled": False,
    "gmail_calendar_coupa_telegram_enabled": False,
    "credential_authority": False,
    "send_submit_approval_enabled": False,
    "queue_autonomy_execution_enabled": False,
    "planner_builder_execution_enabled": False,
    "runtime_daemon_enabled": False,
    "arbitrary_command_execution_enabled": False,
    "network_operation_enabled": False,
    "file_mutation_authority": False,
    "raw_private_body_ingestion_enabled": False,
    "external_retained_memory_enabled": False,
    "hidden_model_routing_enabled": False,
    "hidden_memory_capture_enabled": False,
    "vector_memory_expansion_enabled": False,
    "broad_filesystem_indexing_enabled": False,
    "repo_b_mutation_enabled": False,
    "repo_b_body_inspection_enabled": False,
    "mission_control_app_authority_added": False,
    "mac_sync_or_import_triggered": False,
    "pc_c_drive_artifact_write_allowed": False,
    "adapter_self_authority_allowed": False,
    "operator_final_authority": True,
}

RECEIPT_TYPES = (
    "ADAPTER_LOOKUP_RECEIPT",
    "ADAPTER_ALLOWED_READ_ONLY_RECEIPT",
    "ADAPTER_ALLOWED_PREVIEW_ONLY_RECEIPT",
    "ADAPTER_RECEIPT_ONLY_RECEIPT",
    "ADAPTER_BLOCKED_RECEIPT",
    "ADAPTER_FUTURE_GATED_RECEIPT",
    "ADAPTER_NEEDS_GUARDIAN_GATE_RECEIPT",
    "ADAPTER_NEEDS_OPERATOR_APPROVAL_RECEIPT",
    "ADAPTER_NEEDS_SECURITY_AUDIT_RECEIPT",
    "ADAPTER_NEEDS_MEMORY_SCOPE_REVIEW_RECEIPT",
    "ADAPTER_NEEDS_MODEL_SELECTION_RECEIPT",
    "ADAPTER_NEEDS_PACKAGE_PREVIEW_RECEIPT",
    "ADAPTER_QUARANTINED_RECEIPT",
    "ADAPTER_REVOKED_RECEIPT",
    "ADAPTER_UNKNOWN_FAIL_CLOSED_RECEIPT",
)

RECEIPT_STATES = (
    "ADAPTER_REQUESTED",
    "REGISTRY_LOOKUP_COMPLETE",
    "ADAPTER_KNOWN",
    "ADAPTER_UNKNOWN",
    "CAPABILITY_CLASSIFIED",
    "PACKAGE_BOUNDARY_CHECKED",
    "MEMORY_SCOPE_CHECKED",
    "MODEL_SELECTION_CHECKED",
    "SENSITIVITY_CLASSIFIED",
    "GATES_IDENTIFIED",
    "INPUT_REFS_CHECKED",
    "OUTPUT_RECEIPT_SHAPE_CHECKED",
    "STOP_CONDITIONS_CHECKED",
    "ADAPTER_PREVIEW_READY",
    "ADAPTER_ALLOWED_READ_ONLY",
    "ADAPTER_BLOCKED",
    "ADAPTER_FUTURE_GATED",
    "ADAPTER_QUARANTINED",
    "ADAPTER_REVOKED",
    "UNKNOWN_FAIL_CLOSED",
)

CAPABILITY_CLASSES = (
    "READ_METADATA",
    "READ_REDACTED_CONTENT",
    "READ_RAW_CONTENT",
    "WRITE_DRAFT",
    "WRITE_LOCAL_FILE",
    "RUN_TEST",
    "RUN_BUILD",
    "RUN_SCRIPT",
    "SEND_MESSAGE",
    "SUBMIT_FORM",
    "APPROVE_ACTION",
    "MUTATE_ACCOUNT",
    "BROWSER_SESSION",
    "NETWORK_API",
    "MODEL_CALL",
    "AGENT_LAUNCH",
    "QUEUE_EXECUTION",
    "RECEIPT_WRITE",
    "MEMORY_CANDIDATE_WRITE",
    "CANONICAL_MEMORY_PROMOTION",
)

RECEIPT_FIELDS = (
    "tool_adapter_receipt_id",
    "adapter_id",
    "adapter_display_name",
    "adapter_category",
    "adapter_registry_reference",
    "adapter_registry_version",
    "adapter_state",
    "receipt_type",
    "receipt_state",
    "package_id",
    "package_type",
    "package_preview_receipt_reference",
    "actor_id",
    "agent_character",
    "actor_router_reference",
    "model_selection_receipt_reference",
    "requested_model_class",
    "selected_or_blocked_model_class",
    "memory_scope_reference",
    "memory_candidate_receipt_refs",
    "sensitivity",
    "capability_class_requested",
    "capability_class_granted",
    "capability_class_blocked",
    "current_allowed_actions",
    "current_blocked_actions",
    "future_eligible_actions",
    "input_refs_requested",
    "input_refs_allowed",
    "input_refs_blocked",
    "output_refs_expected",
    "output_receipt_shape",
    "raw_body_included",
    "credential_material_present",
    "account_access_requested",
    "account_access_allowed",
    "network_requested",
    "network_allowed",
    "browser_session_requested",
    "browser_session_allowed",
    "send_submit_approval_requested",
    "send_submit_approval_allowed",
    "file_write_requested",
    "file_write_allowed",
    "command_execution_requested",
    "command_execution_allowed",
    "runtime_dispatch_allowed",
    "tool_execution_performed",
    "model_call_performed",
    "agent_activation_performed",
    "queue_execution_performed",
    "gates_required",
    "operator_gate_status",
    "guardian_gate_status",
    "security_audit_status",
    "stop_conditions",
    "blocked_reasons",
    "future_gated_reasons",
    "quarantine_status",
    "revocation_status",
    "what_would_make_adapter_available",
    "what_keeps_adapter_blocked",
    "created_at",
    "expires_or_review_after",
    "receipt_hash",
)

BINDING_FAIL_CLOSED_REASONS = (
    "UNKNOWN_ADAPTER",
    "UNKNOWN_CAPABILITY_CLASS",
    "MISSING_PACKAGE_PREVIEW_RECEIPT",
    "MISSING_MODEL_SELECTION_RECEIPT",
    "MISSING_MEMORY_SCOPE",
    "SENSITIVITY_UNKNOWN",
    "GUARDIAN_GATE_REQUIRED",
    "OPERATOR_APPROVAL_REQUIRED",
    "SECURITY_AUDIT_REQUIRED",
    "RAW_PRIVATE_BODY_BLOCKED",
    "CREDENTIAL_MATERIAL_BLOCKED",
    "ACCOUNT_ACCESS_BLOCKED",
    "NETWORK_BLOCKED",
    "BROWSER_SESSION_BLOCKED",
    "SEND_SUBMIT_APPROVAL_BLOCKED",
    "COMMAND_EXECUTION_BLOCKED",
    "RUNTIME_AUTHORITY_BLOCKED",
    "RECEIPT_SHAPE_MISSING",
    "UNKNOWN_FAIL_CLOSED",
)

ALLOWED_NOW = (
    "stable map bundle readback",
    "generated read-model inspection",
    "deterministic contract export metadata",
    "package preview display",
    "receipt metadata generation",
    "focused test/build verification only inside bounded worker prompts, not OpenClaw runtime",
    "static validation",
    "forbidden-authority scans",
    "proof/reference display",
)

BLOCKED_NOW = (
    "live browser/OAuth/account flows",
    "Gmail/calendar/Coupa/Telegram access",
    "credentials/tokens/cookies/API keys",
    "autonomous sends/submits/approvals",
    "live model calls from OpenClaw runtime",
    "agent launch/runtime daemon",
    "planner/builder execution",
    "queue/autonomy execution",
    "arbitrary shell execution",
    "broad filesystem indexing",
    "raw private body ingestion",
    "external retained memory",
    "hidden monitoring",
    "C-drive artifact writes",
    "file delete/move authority",
    "broad repair/remount authority",
)

QUARANTINE_TRIGGERS = (
    "adapter claims authority it does not have",
    "adapter references unknown registry entry",
    "adapter skips package preview receipt",
    "adapter skips model selection receipt",
    "adapter skips memory scope",
    "adapter includes raw private body",
    "adapter includes credentials/secrets/tokens/cookies",
    "adapter attempts browser/account/network access without gate",
    "adapter attempts send/submit/approval",
    "adapter attempts command execution or runtime activation",
    "adapter output contradicts proof",
    "adapter receipt malformed",
    "receipt hash missing",
    "sensitive data leak",
    "failed Guardian gate",
    "failed Operator gate",
    "external retained memory detected",
    "broad filesystem indexing attempted",
)

REVOCATION_TRIGGERS = (
    "adapter registry state changed",
    "tool adapter quarantined",
    "package preview revoked",
    "model selection revoked",
    "memory candidate revoked",
    "Guardian gate revoked",
    "Operator approval revoked",
    "security audit blocks adapter",
    "receipt conflict discovered",
    "provider/tool route becomes unavailable",
)


@dataclass(frozen=True)
class EvidenceSource:
    source_id: str
    path: str
    role: str


@dataclass(frozen=True)
class AdapterReceiptExample:
    example_id: str
    adapter_id: str
    adapter_display_name: str
    adapter_category: str
    adapter_state: str
    receipt_type: str
    receipt_state: str
    package_id: str
    package_type: str
    actor_id: str
    agent_character: str
    capability_class_requested: str
    capability_class_granted: str | None
    capability_class_blocked: str | None
    sensitivity: str
    current_allowed_actions: tuple[str, ...]
    current_blocked_actions: tuple[str, ...]
    future_eligible_actions: tuple[str, ...]
    input_refs_requested: tuple[str, ...]
    input_refs_allowed: tuple[str, ...]
    input_refs_blocked: tuple[str, ...]
    output_refs_expected: tuple[str, ...]
    output_receipt_shape: tuple[str, ...]
    gates_required: tuple[str, ...]
    blocked_reasons: tuple[str, ...]
    future_gated_reasons: tuple[str, ...]
    operator_gate_status: str
    guardian_gate_status: str
    security_audit_status: str
    what_would_make_adapter_available: str
    what_keeps_adapter_blocked: str
    network_requested: bool = False
    browser_session_requested: bool = False
    account_access_requested: bool = False
    send_submit_approval_requested: bool = False
    file_write_requested: bool = False
    command_execution_requested: bool = False


@dataclass(frozen=True)
class RecommendedLane:
    lane_id: str
    title: str
    priority: str
    why_next: str
    hard_boundary: str


@dataclass(frozen=True)
class ToolAdapterReceiptExportResult:
    schema_version: str
    json_path: str
    operator_path: str
    receipt_type_count: int
    receipt_state_count: int
    capability_class_count: int
    example_count: int
    live_tool_execution_added: bool


EVIDENCE_SOURCES = (
    EvidenceSource("agent_platform_alignment", "generated/read_models/agent_platform_alignment.json", "agent-platform primitive map"),
    EvidenceSource("agent_identity_actor_router_contract", "generated/read_models/agent_identity_actor_router_contract.json", "actor identity and routing boundaries"),
    EvidenceSource("model_selection_policy_contract", "generated/read_models/model_selection_policy_contract.json", "model class policy"),
    EvidenceSource("model_selection_receipt_contract", "generated/read_models/model_selection_receipt_contract.json", "model selection receipt grammar"),
    EvidenceSource("agent_package_preview_contract", "generated/read_models/agent_package_preview_contract.json", "package preview contract"),
    EvidenceSource("package_preview_receipt_contract", "generated/read_models/package_preview_receipt_contract.json", "package preview receipt grammar"),
    EvidenceSource("agent_memory_scope_contract", "generated/read_models/agent_memory_scope_contract.json", "memory/context scope policy"),
    EvidenceSource("memory_candidate_receipt_contract", "generated/read_models/memory_candidate_receipt_contract.json", "memory candidate receipt grammar"),
    EvidenceSource("tool_protocol_adapter_registry_contract", "generated/read_models/tool_protocol_adapter_registry_contract.json", "source registry for adapter states and capabilities"),
    EvidenceSource("agent_terrain_awareness_readback_contract", "generated/read_models/agent_terrain_awareness_readback_contract.json", "agent/persona terrain and dossier cards"),
    EvidenceSource("stable_map_bundle", "generated/read_models/openclaw_map_manifest.json", "app-facing stable map generation"),
    EvidenceSource("operator_threshold_map_contract", "generated/read_models/operator_threshold_map_contract.json", "threshold and lane destiny"),
)

EXAMPLE_RECEIPTS = (
    AdapterReceiptExample(
        "stable_map_bundle_reader",
        "stable_map_bundle_reader",
        "Stable Map Bundle Reader",
        "read_model_stable_map",
        "ACTIVE_READ_ONLY",
        "ADAPTER_ALLOWED_READ_ONLY_RECEIPT",
        "ADAPTER_ALLOWED_READ_ONLY",
        "package_stable_map_readback",
        "read_model_readback",
        "chief",
        "Chief",
        "READ_METADATA",
        "READ_METADATA",
        None,
        "INTERNAL_SYSTEM",
        ("read stable map metadata", "read stable manifest hash", "display proof refs"),
        ("write map files", "network access", "account access", "tool execution"),
        (),
        ("generated/read_models/openclaw_map_snapshot.json", "generated/read_models/openclaw_map_manifest.json"),
        ("stable map metadata refs", "manifest hash refs"),
        ("raw private bodies", "credentials", "account sessions"),
        ("map proof receipt",),
        ("receipt_id", "adapter_id", "map_generation_id", "bundle_hash", "parse_passed", "receipt_hash"),
        ("package preview receipt if package-bound",),
        (),
        (),
        "not_required_for_read_only_metadata",
        "not_required_for_read_only_metadata",
        "not_required_for_read_only_metadata",
        "Stable map parse/hash receipt and current package preview when package-bound.",
        "Any request for write/network/account/tool execution keeps it blocked.",
    ),
    AdapterReceiptExample(
        "package_preview_exporter",
        "package_preview_exporter",
        "Package Preview Exporter",
        "package_compiler",
        "ACTIVE_PREVIEW_ONLY",
        "ADAPTER_ALLOWED_PREVIEW_ONLY_RECEIPT",
        "ADAPTER_PREVIEW_READY",
        "package_preview_receipt_contract",
        "package_preview_export",
        "codex",
        "Codex",
        "RECEIPT_WRITE",
        "RECEIPT_WRITE",
        None,
        "INTERNAL_SYSTEM",
        ("export inspectable package metadata", "write deterministic receipt metadata"),
        ("dispatch package", "launch model", "activate agent", "execute tool"),
        ("future receipt ledger row after approved pattern",),
        ("package preview contract refs",),
        ("generated package preview metadata",),
        ("raw private body", "credentials", "runtime command"),
        ("package preview receipt read-model",),
        ("package_id", "actor_id", "authority_boundary", "receipt_hash"),
        ("package preview contract", "model selection receipt"),
        (),
        ("future receipt ledger integration",),
        "operator_preview_required",
        "required_if_sensitive",
        "not_started",
        "Existing deterministic export lane and package preview receipt grammar.",
        "Any dispatch/model/tool launch request keeps it blocked.",
    ),
    AdapterReceiptExample(
        "codex_scoped_build_verifier",
        "codex_scoped_build_verifier",
        "Codex Scoped Build Verifier",
        "local_code_workspace",
        "FUTURE_GATED",
        "ADAPTER_FUTURE_GATED_RECEIPT",
        "ADAPTER_FUTURE_GATED",
        "package_codex_backend_contract_implementation",
        "code_implementation",
        "codex",
        "Codex",
        "RUN_TEST",
        None,
        "RUN_TEST",
        "INTERNAL_SYSTEM",
        ("record test/build proof refs from bounded worker prompt",),
        ("OpenClaw runtime command execution", "network", "credentials", "broad repo expansion"),
        ("future scoped test/build verifier after security",),
        ("scoped package refs", "test command refs"),
        ("test output receipt refs",),
        ("secrets", "network outputs", "broad workspace scan"),
        ("build/test verification receipt",),
        ("commands_run", "exit_code", "files_changed", "network_used", "receipt_hash"),
        ("package preview receipt", "operator preview", "allowed roots"),
        ("COMMAND_EXECUTION_BLOCKED", "RUNTIME_AUTHORITY_BLOCKED"),
        ("security audit", "tool adapter receipt", "allowed roots"),
        "operator_preview_required",
        "required_if_sensitive_paths",
        "required_before_runtime_verifier",
        "Security-reviewed scoped command class and result receipt.",
        "No OpenClaw runtime command authority exists.",
        command_execution_requested=True,
    ),
    AdapterReceiptExample(
        "cassandra_capital_hilton_invoice_proof_adapter",
        "cassandra_capital_hilton_invoice_proof_adapter",
        "Cassandra Capital Hilton Invoice Proof Adapter",
        "domain_workflow",
        "FUTURE_GATED",
        "ADAPTER_NEEDS_GUARDIAN_GATE_RECEIPT",
        "ADAPTER_FUTURE_GATED",
        "package_cassandra_capital_hilton_invoice_review",
        "finance_ap_review",
        "cassandra",
        "Cassandra",
        "READ_REDACTED_CONTENT",
        None,
        "READ_REDACTED_CONTENT",
        "FINANCE_PROTECTED",
        ("show missing protected proof metadata",),
        ("Coupa access", "Excel raw body", "credentials", "submit/approval"),
        ("future protected metadata proof read after Guardian gate",),
        ("Capital Hilton source refs",),
        ("protected metadata refs after gate",),
        ("raw Coupa body", "raw workbook", "credentials", "account session"),
        ("protected proof metadata receipt",),
        ("source_card_id", "redaction_status", "guardian_gate_id", "receipt_hash"),
        ("Guardian protected-access gate", "Operator approval", "security audit"),
        ("GUARDIAN_GATE_REQUIRED", "ACCOUNT_ACCESS_BLOCKED", "CREDENTIAL_MATERIAL_BLOCKED"),
        ("protected metadata packet", "security audit", "Guardian gate receipt"),
        "future_operator_approval_required",
        "required",
        "required_before_protected_finance_adapter",
        "Protected proof metadata and Guardian/Operator receipts.",
        "Finance protected context and account access remain blocked.",
        account_access_requested=True,
    ),
    AdapterReceiptExample(
        "guardian_protected_access_gate",
        "guardian_protected_access_gate",
        "Guardian Protected Access Gate",
        "safety_security",
        "ACTIVE_PREVIEW_ONLY",
        "ADAPTER_ALLOWED_PREVIEW_ONLY_RECEIPT",
        "ADAPTER_PREVIEW_READY",
        "package_guardian_protected_evidence_review",
        "protected_access_review",
        "guardian",
        "Guardian",
        "READ_METADATA",
        "READ_METADATA",
        None,
        "LEGAL_OR_COMPLIANCE",
        ("recommend allow/block/redact/quarantine/revoke",),
        ("self-authorization", "raw private body access", "execution"),
        ("future gate receipt after security audit",),
        ("protected metadata refs",),
        ("metadata-only protected refs",),
        ("raw private bodies", "credentials", "browser sessions"),
        ("Guardian recommendation receipt",),
        ("gate_id", "decision", "redaction_status", "operator_required", "receipt_hash"),
        ("package preview receipt", "memory scope"),
        (),
        ("security-audited gate integration",),
        "operator_required_for_future_sensitive_action",
        "Guardian_is_gate_not_self_authorizer",
        "not_started",
        "Gate decision receipt and operator approval where required.",
        "Guardian cannot grant itself execution or bypass Operator.",
    ),
    AdapterReceiptExample(
        "chief_test_harness_adapter",
        "chief_test_harness_adapter",
        "Chief Test Harness Adapter",
        "runtime_agent",
        "FUTURE_GATED",
        "ADAPTER_FUTURE_GATED_RECEIPT",
        "ADAPTER_FUTURE_GATED",
        "package_chief_check_engine_diagnostic",
        "check_light_diagnostic_package",
        "chief",
        "Chief",
        "RUN_TEST",
        None,
        "RUN_TEST",
        "INTERNAL_SYSTEM",
        ("preview expected verification receipt shape",),
        ("execute repairs", "remount", "cleanup", "self-authorize success"),
        ("future receipt/result verifier after security",),
        ("system health refs", "result receipt refs"),
        ("verification receipt refs",),
        ("repair commands", "raw logs", "credentials"),
        ("test harness verification receipt",),
        ("test_id", "inputs", "outputs", "success_state", "receipt_hash"),
        ("security audit", "operator approval for future harness"),
        ("COMMAND_EXECUTION_BLOCKED", "RUNTIME_AUTHORITY_BLOCKED"),
        ("security audit", "bounded harness contract"),
        "operator_approval_required_for_future_runtime",
        "required_if_sensitive",
        "required_before_runtime_harness",
        "Bounded test-harness contract and receipts.",
        "Chief cannot self-authorize or execute fixes.",
        command_execution_requested=True,
    ),
    AdapterReceiptExample(
        "browser_oauth_adapter",
        "browser_oauth_adapter",
        "Browser / OAuth Adapter",
        "external_account_browser_api",
        "BLOCKED_NO_AUTHORITY",
        "ADAPTER_NEEDS_SECURITY_AUDIT_RECEIPT",
        "ADAPTER_BLOCKED",
        "package_browser_portal_candidate",
        "browser_or_portal_related",
        "guardian",
        "Guardian",
        "BROWSER_SESSION",
        None,
        "BROWSER_SESSION",
        "ACCOUNT_ACCESS",
        (),
        ("browser launch", "OAuth", "cookies/session", "account mutation"),
        ("future security-audited account adapter if ever approved",),
        ("portal metadata refs",),
        (),
        ("credentials", "cookies", "OAuth state", "account session"),
        ("account access receipt if ever authorized",),
        ("account_accessed", "network_used", "operator_approval_id", "receipt_hash"),
        ("security audit", "Operator approval", "Guardian gate"),
        ("BROWSER_SESSION_BLOCKED", "ACCOUNT_ACCESS_BLOCKED", "SECURITY_AUDIT_REQUIRED"),
        ("security audit", "credential policy", "account-action receipt"),
        "operator_approval_required",
        "required",
        "required",
        "Explicit security audit and account-access gate.",
        "No browser/OAuth/account authority exists.",
        network_requested=True,
        browser_session_requested=True,
        account_access_requested=True,
    ),
    AdapterReceiptExample(
        "gmail_calendar_adapter",
        "gmail_calendar_adapter",
        "Gmail / Calendar Adapter",
        "external_account_browser_api",
        "BLOCKED_NO_AUTHORITY",
        "ADAPTER_NEEDS_SECURITY_AUDIT_RECEIPT",
        "ADAPTER_BLOCKED",
        "package_cassandra_comms_review",
        "communications_review",
        "cassandra",
        "Cassandra",
        "MUTATE_ACCOUNT",
        None,
        "MUTATE_ACCOUNT",
        "ACCOUNT_ACCESS",
        (),
        ("raw bodies", "send", "calendar mutation", "account access"),
        ("future metadata-only review after gates",),
        ("email/calendar metadata refs",),
        (),
        ("raw email bodies", "calendar body", "OAuth tokens", "send/mutate requests"),
        ("communications metadata receipt",),
        ("message_ids", "redaction_status", "send_performed_false", "receipt_hash"),
        ("security audit", "Operator approval", "Guardian gate"),
        ("ACCOUNT_ACCESS_BLOCKED", "SEND_SUBMIT_APPROVAL_BLOCKED", "RAW_PRIVATE_BODY_BLOCKED"),
        ("metadata-only connector gate", "no-send receipt", "operator approval"),
        "operator_approval_required",
        "required_if_private",
        "required",
        "Security-audited metadata gate and explicit no-send receipt.",
        "No Gmail/calendar/account authority exists.",
        network_requested=True,
        account_access_requested=True,
        send_submit_approval_requested=True,
    ),
    AdapterReceiptExample(
        "coupa_adapter",
        "coupa_adapter",
        "Coupa Adapter",
        "domain_workflow",
        "BLOCKED_NO_AUTHORITY",
        "ADAPTER_NEEDS_SECURITY_AUDIT_RECEIPT",
        "ADAPTER_BLOCKED",
        "package_cassandra_capital_hilton_invoice_review",
        "finance_ap_review",
        "cassandra",
        "Cassandra",
        "MUTATE_ACCOUNT",
        None,
        "MUTATE_ACCOUNT",
        "FINANCE_PROTECTED",
        (),
        ("Coupa login", "credentials", "browser session", "submit/approve"),
        ("future protected metadata only after security",),
        ("Coupa proof metadata refs",),
        (),
        ("credentials", "Coupa session", "submit/approve action", "raw invoice body"),
        ("finance portal adapter receipt if ever authorized",),
        ("account_accessed", "submit_performed_false", "approval_performed_false", "receipt_hash"),
        ("security audit", "Guardian gate", "Operator approval"),
        ("ACCOUNT_ACCESS_BLOCKED", "CREDENTIAL_MATERIAL_BLOCKED", "SEND_SUBMIT_APPROVAL_BLOCKED"),
        ("security audit", "protected proof packet", "operator approval"),
        "operator_approval_required",
        "required",
        "required",
        "Protected proof metadata packet and future account-action gate.",
        "No Coupa/account/credential/submit authority exists.",
        network_requested=True,
        browser_session_requested=True,
        account_access_requested=True,
        send_submit_approval_requested=True,
    ),
    AdapterReceiptExample(
        "telegram_adapter",
        "telegram_adapter",
        "Telegram Adapter",
        "external_account_browser_api",
        "BLOCKED_NO_AUTHORITY",
        "ADAPTER_BLOCKED_RECEIPT",
        "ADAPTER_BLOCKED",
        "package_comms_send_candidate",
        "communications_review",
        "cassandra",
        "Cassandra",
        "SEND_MESSAGE",
        None,
        "SEND_MESSAGE",
        "ACCOUNT_ACCESS",
        (),
        ("send message", "account access", "runtime send authority"),
        ("future communications metadata review if ever gated",),
        ("telegram metadata refs",),
        (),
        ("message body", "account session", "send action"),
        ("messaging action receipt if ever authorized",),
        ("send_performed", "operator_approval_id", "receipt_hash"),
        ("security audit", "Operator approval"),
        ("SEND_SUBMIT_APPROVAL_BLOCKED", "ACCOUNT_ACCESS_BLOCKED"),
        ("security audit", "operator send approval", "message receipt"),
        "operator_approval_required",
        "required_if_private",
        "required",
        "Explicit send approval and account/security gate.",
        "No Telegram send/runtime authority exists.",
        network_requested=True,
        account_access_requested=True,
        send_submit_approval_requested=True,
    ),
    AdapterReceiptExample(
        "repo_b_planner_builder_adapter",
        "repo_b_planner_builder_adapter",
        "Repo B Planner / Builder Adapter",
        "runtime_agent",
        "CANDIDATE_UNMAPPED",
        "ADAPTER_FUTURE_GATED_RECEIPT",
        "ADAPTER_FUTURE_GATED",
        "package_agentic_loop_classification",
        "terrain_discovery_classification",
        "chief",
        "Chief / Hermes",
        "QUEUE_EXECUTION",
        None,
        "QUEUE_EXECUTION",
        "INTERNAL_SYSTEM",
        ("display operator-reported loop classification gaps",),
        ("Repo B execution", "planner/builder runtime", "queue/autonomy"),
        ("future classified cue/autonomy spine after security",),
        ("agentic loop metadata refs",),
        ("approved component manifest refs",),
        ("Repo B bodies", "runtime queue data", "planner/builder outputs"),
        ("planner/builder classification receipt",),
        ("component_id", "status", "execution_performed_false", "receipt_hash"),
        ("discovery classification", "security audit", "operator approval"),
        ("UNKNOWN_ADAPTER", "RUNTIME_AUTHORITY_BLOCKED", "COMMAND_EXECUTION_BLOCKED"),
        ("approved metadata-only discovery", "security audit", "queue lifecycle receipts"),
        "operator_clarification_required",
        "not_required_until_sensitive_context",
        "required_before_any_autonomy",
        "Approved metadata-only discovery and security audit.",
        "Repo B execution and queue/autonomy are blocked.",
        command_execution_requested=True,
    ),
    AdapterReceiptExample(
        "memory_candidate_receipt_writer",
        "memory_candidate_receipt_writer",
        "Memory Candidate Receipt Writer",
        "package_compiler",
        "RECEIPT_ONLY",
        "ADAPTER_RECEIPT_ONLY_RECEIPT",
        "ADAPTER_PREVIEW_READY",
        "package_memory_candidate_capture",
        "memory_candidate_review",
        "guardian",
        "Guardian",
        "MEMORY_CANDIDATE_WRITE",
        "MEMORY_CANDIDATE_WRITE",
        None,
        "INTERNAL_SYSTEM",
        ("write candidate metadata receipt", "mark candidate non-canonical"),
        ("canonical memory promotion", "hidden memory", "raw private body capture"),
        ("future memory review surface",),
        ("operator statement refs", "source card refs"),
        ("memory candidate metadata refs",),
        ("credentials", "raw private bodies", "hidden model memory"),
        ("memory candidate receipt",),
        ("candidate_id", "source_ref", "sensitivity", "operator_review_required", "receipt_hash"),
        ("memory scope contract", "operator promotion for canonical memory"),
        (),
        ("memory review/promotion surface",),
        "operator_review_required_for_promotion",
        "required_if_sensitive",
        "not_required_for_candidate_only",
        "Candidate receipt and later operator promotion receipt.",
        "Canonical promotion is blocked; candidate metadata only.",
    ),
)

RECOMMENDED_NEXT_LANES = (
    RecommendedLane(
        "package_preview_surface_mission_control_integration_v0",
        "Package Preview Surface / Mission Control Integration v0",
        "P1",
        "Mission Control can render package and tool receipt posture read-only.",
        "Mac read-only UI; no dispatch controls",
    ),
    RecommendedLane(
        "memory_review_promotion_surface_v0",
        "Memory Review / Promotion Surface v0",
        "P1",
        "Memory candidate receipts need a governed review surface before promotion lanes.",
        "read-only review; no direct canonical memory mutation",
    ),
    RecommendedLane(
        "capital_hilton_proof_metadata_packet_v0",
        "Capital Hilton Proof Metadata Packet v0",
        "P2",
        "Capital Hilton needs protected metadata proof before Finance World action.",
        "metadata only; no Coupa/account access",
    ),
    RecommendedLane(
        "tool_adapter_receipt_surface_v0",
        "Tool Adapter Receipt Surface v0",
        "P2",
        "Tool receipt cards can expose allowed/blocked/future-gated adapters.",
        "read-only UI; no live tools",
    ),
    RecommendedLane(
        "model_router_implementation_plan_v0",
        "Model Router Implementation Plan v0",
        "P3",
        "Model routing can remain preview-only until all gates and receipts are complete.",
        "plan only; no model router runtime",
    ),
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _content_hash(payload: dict[str, Any]) -> str:
    clone = json.loads(stable_json(payload))
    clone.get("machine_proof", {}).pop("content_hash", None)
    return "sha256:" + hashlib.sha256(stable_json(clone).encode("utf-8")).hexdigest()


def _source_present(repo_root: str | Path, relative_path: str) -> tuple[bool, str | None]:
    path = Path(repo_root) / relative_path
    if not path.is_file():
        return False, None
    if path.suffix.lower() != ".json":
        return True, None
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return True, None
    if isinstance(loaded, dict):
        return True, loaded.get("schema_version")
    return True, None


def _source_record(source: EvidenceSource, *, repo_root: str | Path) -> dict[str, Any]:
    present, schema_version = _source_present(repo_root, source.path)
    return {
        "source_id": source.source_id,
        "path": source.path,
        "role": source.role,
        "present": present,
        "schema_version": schema_version,
        "raw_private_body_imported": False,
        "credentials_or_secrets_imported": False,
        "authority_granted_by_source_presence": False,
    }


def _receipt_type_description(receipt_type: str) -> str:
    return receipt_type.lower().replace("_", " ")


def _receipt_state_description(state: str) -> str:
    return state.lower().replace("_", " ")


def _capability_policy(capability: str) -> dict[str, Any]:
    if capability == "READ_METADATA":
        status = "allowed_for_deterministic_metadata_readback"
        blocked_now = False
        future_gated = False
        guardian = False
        operator = False
        security = False
        blocks = ("raw private body requested", "credential/account material requested")
        later = "already available for deterministic read-model/stable-map references"
    elif capability == "RECEIPT_WRITE":
        status = "allowed_for_deterministic_metadata_receipts"
        blocked_now = False
        future_gated = False
        guardian = False
        operator = False
        security = False
        blocks = ("attempts canonical memory promotion", "attempts runtime/action receipt without gate")
        later = "already available for bounded metadata receipt generation"
    elif capability == "MEMORY_CANDIDATE_WRITE":
        status = "candidate_only_not_canonical"
        blocked_now = False
        future_gated = True
        guardian = True
        operator = True
        security = False
        blocks = ("canonical promotion requested", "hidden memory capture", "raw private body included")
        later = "memory review/promotion surface and operator promotion receipt"
    else:
        status = "blocked_or_future_gated"
        blocked_now = True
        future_gated = True
        guardian = capability in {
            "READ_REDACTED_CONTENT",
            "READ_RAW_CONTENT",
            "MUTATE_ACCOUNT",
            "BROWSER_SESSION",
            "NETWORK_API",
            "CANONICAL_MEMORY_PROMOTION",
        }
        operator = capability not in {"READ_METADATA", "RECEIPT_WRITE"}
        security = capability in {
            "READ_RAW_CONTENT",
            "WRITE_LOCAL_FILE",
            "RUN_TEST",
            "RUN_BUILD",
            "RUN_SCRIPT",
            "SEND_MESSAGE",
            "SUBMIT_FORM",
            "APPROVE_ACTION",
            "MUTATE_ACCOUNT",
            "BROWSER_SESSION",
            "NETWORK_API",
            "MODEL_CALL",
            "AGENT_LAUNCH",
            "QUEUE_EXECUTION",
            "CANONICAL_MEMORY_PROMOTION",
        }
        blocks = (
            "no current runtime authority",
            "missing security audit",
            "missing operator approval",
            "missing receipt/gate",
        )
        later = "security audit, package preview receipt, adapter receipt, and explicit gate"
    return {
        "capability_class": capability,
        "current_authority_posture": status,
        "blocked_now": blocked_now,
        "future_gated": future_gated,
        "guardian_gate_required": guardian,
        "operator_approval_required": operator,
        "security_audit_required": security,
        "receipt_required": True,
        "what_blocks_it": list(blocks),
        "what_would_make_it_available_later": later,
    }


def _example_record(example: AdapterReceiptExample) -> dict[str, Any]:
    hard_defaults = {
        "raw_body_included": False,
        "credential_material_present": False,
        "account_access_allowed": False,
        "network_allowed": False,
        "browser_session_allowed": False,
        "send_submit_approval_allowed": False,
        "file_write_allowed": False,
        "command_execution_allowed": False,
        "runtime_dispatch_allowed": False,
        "tool_execution_performed": False,
        "model_call_performed": False,
        "agent_activation_performed": False,
        "queue_execution_performed": False,
    }
    return {
        "tool_adapter_receipt_id": f"tool_adapter_receipt_{example.example_id}",
        "example_id": example.example_id,
        "adapter_id": example.adapter_id,
        "adapter_display_name": example.adapter_display_name,
        "adapter_category": example.adapter_category,
        "adapter_registry_reference": "generated/read_models/tool_protocol_adapter_registry_contract.json",
        "adapter_registry_version": "tool_protocol_adapter_registry_contract_v0",
        "adapter_state": example.adapter_state,
        "receipt_type": example.receipt_type,
        "receipt_state": example.receipt_state,
        "package_id": example.package_id,
        "package_type": example.package_type,
        "package_preview_receipt_reference": "generated/read_models/package_preview_receipt_contract.json",
        "actor_id": example.actor_id,
        "agent_character": example.agent_character,
        "actor_router_reference": "generated/read_models/agent_identity_actor_router_contract.json",
        "model_selection_receipt_reference": "generated/read_models/model_selection_receipt_contract.json",
        "requested_model_class": "blocked_no_model",
        "selected_or_blocked_model_class": "blocked_no_model",
        "memory_scope_reference": "generated/read_models/agent_memory_scope_contract.json",
        "memory_candidate_receipt_refs": [],
        "sensitivity": example.sensitivity,
        "capability_class_requested": example.capability_class_requested,
        "capability_class_granted": example.capability_class_granted,
        "capability_class_blocked": example.capability_class_blocked,
        "current_allowed_actions": list(example.current_allowed_actions),
        "current_blocked_actions": list(example.current_blocked_actions),
        "future_eligible_actions": list(example.future_eligible_actions),
        "input_refs_requested": list(example.input_refs_requested),
        "input_refs_allowed": list(example.input_refs_allowed),
        "input_refs_blocked": list(example.input_refs_blocked),
        "output_refs_expected": list(example.output_refs_expected),
        "output_receipt_shape": list(example.output_receipt_shape),
        **hard_defaults,
        "account_access_requested": example.account_access_requested,
        "network_requested": example.network_requested,
        "browser_session_requested": example.browser_session_requested,
        "send_submit_approval_requested": example.send_submit_approval_requested,
        "file_write_requested": example.file_write_requested,
        "command_execution_requested": example.command_execution_requested,
        "gates_required": list(example.gates_required),
        "operator_gate_status": example.operator_gate_status,
        "guardian_gate_status": example.guardian_gate_status,
        "security_audit_status": example.security_audit_status,
        "stop_conditions": [
            "adapter unknown",
            "capability unknown",
            "package preview receipt missing",
            "model selection receipt missing",
            "memory scope missing",
            "sensitivity unknown",
            "authority requested beyond receipt",
            "output receipt shape missing",
        ],
        "blocked_reasons": list(example.blocked_reasons),
        "future_gated_reasons": list(example.future_gated_reasons),
        "quarantine_status": "not_quarantined",
        "revocation_status": "not_revoked",
        "what_would_make_adapter_available": example.what_would_make_adapter_available,
        "what_keeps_adapter_blocked": example.what_keeps_adapter_blocked,
        "created_at": "example_static_timestamp",
        "expires_or_review_after": "review_before_future_adapter_use_or_source_change",
        "receipt_hash": "example_hash_computed_in_real_receipt",
        "tool_or_protocol_execution_authorized": False,
    }


def _recommended_lane_record(lane: RecommendedLane) -> dict[str, Any]:
    return {
        "lane_id": lane.lane_id,
        "title": lane.title,
        "priority": lane.priority,
        "why_next": lane.why_next,
        "hard_boundary": lane.hard_boundary,
    }


def build_tool_adapter_receipt_contract(
    *,
    repo_root: str | Path = ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    evidence_sources = [_source_record(source, repo_root=repo_root) for source in EVIDENCE_SOURCES]
    examples = [_example_record(example) for example in EXAMPLE_RECEIPTS]
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": "tool_adapter_receipt_contract",
        "generated_at": generated_at,
        **NO_AUTHORITY_FLAGS,
        "contract_status": "deterministic_tool_adapter_receipt_metadata_only",
        "operator_summary": (
            "OpenClaw now has a deterministic receipt grammar for tool/protocol adapter lookup, allow, block, "
            "quarantine, and future-gate decisions. It proves adapter posture without executing tools."
        ),
        "core_doctrine": {
            "tools_protocol_adapters_are_not_authority_by_themselves": True,
            "adapter_may_not_self_authorize": True,
            "actor_may_not_grant_itself_tool": True,
            "package_preview_is_required_before_future_adapter_use": True,
            "tool_adapter_receipt_does_not_perform_tool_execution": True,
        },
        "evidence_sources": evidence_sources,
        "receipt_types": [
            {
                "receipt_type": receipt_type,
                "description": _receipt_type_description(receipt_type),
                "tool_execution_allowed": False,
            }
            for receipt_type in RECEIPT_TYPES
        ],
        "receipt_states": [
            {
                "receipt_state": state,
                "description": _receipt_state_description(state),
                "runtime_execution_allowed": False,
                "read_only_state": state == "ADAPTER_ALLOWED_READ_ONLY",
            }
            for state in RECEIPT_STATES
        ],
        "capability_classes": [_capability_policy(capability) for capability in CAPABILITY_CLASSES],
        "tool_adapter_receipt_schema": {
            "required_fields": list(RECEIPT_FIELDS),
            "hard_defaults": {
                "raw_body_included": False,
                "credential_material_present": False,
                "account_access_allowed": False,
                "network_allowed": False,
                "browser_session_allowed": False,
                "send_submit_approval_allowed": False,
                "file_write_allowed": False,
                "command_execution_allowed": False,
                "runtime_dispatch_allowed": False,
                "tool_execution_performed": False,
                "model_call_performed": False,
                "agent_activation_performed": False,
                "queue_execution_performed": False,
            },
            "natural_language_claim_counts_as_authority": False,
            "missing_or_unknown_result": "ADAPTER_UNKNOWN_FAIL_CLOSED_RECEIPT",
        },
        "adapter_binding_requirements": {
            "valid_only_if": [
                "adapter exists in Tool Protocol Adapter Registry",
                "package preview receipt exists or package preview is explicitly marked missing",
                "actor/agent is known",
                "model selection is checked",
                "memory scope is checked",
                "sensitivity is classified",
                "requested capability class is known",
                "required gates are identified",
                "blocked actions are explicit",
                "stop conditions exist",
                "output receipt shape exists",
                "no high-risk authority is implied without future gates",
            ],
            "fail_closed_reasons": list(BINDING_FAIL_CLOSED_REASONS),
            "unknown_adapter_result": "ADAPTER_UNKNOWN_FAIL_CLOSED_RECEIPT",
            "adapter_self_authorization_allowed": False,
        },
        "current_authority_matrix": {
            "allowed_now": list(ALLOWED_NOW),
            "blocked_now": list(BLOCKED_NOW),
            "focused_test_build_verification_note": "bounded worker prompt proof may be recorded; OpenClaw runtime command execution remains false",
        },
        "example_tool_adapter_receipts": examples,
        "receipt_quarantine_revocation_policy": {
            "quarantine_triggers": list(QUARANTINE_TRIGGERS),
            "revocation_triggers": list(REVOCATION_TRIGGERS),
            "missing_or_malformed_receipt_result": "ADAPTER_QUARANTINED_RECEIPT",
            "quarantine_is_non_destructive": True,
            "revocation_blocks_future_adapter_use": True,
        },
        "relationship_to_existing_contracts": {
            "agent_platform_alignment": "defines the platform primitive map",
            "agent_identity_actor_router_contract": "defines actor/agent identity and routing",
            "model_selection_policy_contract": "defines model class policy",
            "model_selection_receipt_contract": "proves model selection allow/block posture",
            "agent_package_preview_contract": "defines package preview schema",
            "package_preview_receipt_contract": "proves package can display without dispatch",
            "agent_memory_scope_contract": "governs context/memory scope",
            "memory_candidate_receipt_contract": "governs candidate memory inputs",
            "tool_protocol_adapter_registry_contract": "source registry for adapter states and capabilities",
            "agent_terrain_awareness_readback_contract": "agent/persona terrain and dossier context",
            "stable_map_bundle": "app-facing map proof/detail source",
            "threshold_map_contract": "threshold and lane destiny",
        },
        "mission_control_surface_guidance": {
            "tool_adapter_receipt_card": [
                "adapter name",
                "adapter state",
                "package",
                "actor/agent",
                "capability requested",
                "capability granted/blocked",
                "preview-only/future-gated status",
                "required gates",
                "blocked reasons",
                "output receipt shape",
                "what would make available later",
            ],
            "package_preview_tool_section": [
                "requested adapters",
                "allowed adapters",
                "blocked adapters",
                "future-gated adapters",
                "required receipts",
                "stop conditions",
            ],
            "agent_dossier_integration": [
                "tool adapter summary",
                "allowed/blocked/future-gated tools",
                "required gates",
                "required receipts",
            ],
            "hide_or_block": [
                "live tool execution controls",
                "browser/OAuth launch controls",
                "Gmail/calendar/Coupa/Telegram controls",
                "credential prompts",
                "account controls",
                "send/submit/approval controls",
                "arbitrary command execution controls",
                "fake confidence percentages",
                "raw private context",
                "hidden routing",
                "adapter authorized itself claims",
            ],
        },
        "stable_map_integration": {
            "contract_generated_as_read_model": True,
            "summary_included_in_stable_map_bundle_now": False,
            "reason_not_included_now": "avoid reopening stable-map/sync residue in this contract lane",
            "safe_summary_to_include_next": {
                "contract_id": "tool_adapter_receipt_contract",
                "receipt_types_count": len(RECEIPT_TYPES),
                "adapter_examples_count": len(EXAMPLE_RECEIPTS),
                "current_allowed_read_only_preview_only_count": sum(
                    1 for example in examples if example["receipt_type"] in {"ADAPTER_ALLOWED_READ_ONLY_RECEIPT", "ADAPTER_ALLOWED_PREVIEW_ONLY_RECEIPT", "ADAPTER_RECEIPT_ONLY_RECEIPT"}
                ),
                "blocked_future_gated_adapter_count": sum(
                    1 for example in examples if example["receipt_type"] not in {"ADAPTER_ALLOWED_READ_ONLY_RECEIPT", "ADAPTER_ALLOWED_PREVIEW_ONLY_RECEIPT", "ADAPTER_RECEIPT_ONLY_RECEIPT"}
                ),
                "live_execution_authority": False,
                "next_recommended_lane": "package_preview_surface_mission_control_integration_v0",
            },
        },
        "recommended_next_lanes": [_recommended_lane_record(lane) for lane in RECOMMENDED_NEXT_LANES],
        "machine_proof": {
            "receipt_types_count": len(RECEIPT_TYPES),
            "receipt_states_count": len(RECEIPT_STATES),
            "capability_classes_count": len(CAPABILITY_CLASSES),
            "example_count": len(EXAMPLE_RECEIPTS),
            "all_examples_no_tool_execution": all(example["tool_execution_performed"] is False for example in examples),
            "all_examples_no_model_call": all(example["model_call_performed"] is False for example in examples),
            "all_examples_no_agent_activation": all(example["agent_activation_performed"] is False for example in examples),
            "all_examples_no_queue_execution": all(example["queue_execution_performed"] is False for example in examples),
            "all_examples_no_credentials": all(example["credential_material_present"] is False for example in examples),
            "content_hash": None,
        },
    }
    payload["machine_proof"]["content_hash"] = _content_hash(payload)
    return payload


def format_operator_markdown(payload: dict[str, Any]) -> str:
    examples = payload["example_tool_adapter_receipts"]
    lines = [
        "# Tool Adapter Receipt Contract v0",
        "",
        "## Summary",
        "",
        payload["operator_summary"],
        "",
        "## Receipt Grammar",
        "",
        f"- Receipt types: `{len(payload['receipt_types'])}`",
        f"- Receipt states: `{len(payload['receipt_states'])}`",
        f"- Capability classes: `{len(payload['capability_classes'])}`",
        f"- Required fields: `{len(payload['tool_adapter_receipt_schema']['required_fields'])}`",
        "- `ADAPTER_ALLOWED_READ_ONLY` means deterministic readback/static metadata only, not runtime execution.",
        "- Tool execution, network/account/browser access, send/submit/approval, command execution, model calls, agent activation, and queue execution default to `false`.",
        "",
        "## Example Adapter Receipts",
        "",
    ]
    for example in examples:
        lines.extend(
            [
                f"- `{example['example_id']}`: {example['adapter_display_name']} -> `{example['receipt_type']}`",
                f"  - capability: `{example['capability_class_requested']}` / granted: `{example['capability_class_granted']}` / blocked: `{example['capability_class_blocked']}`",
                f"  - blocked reasons: `{', '.join(example['blocked_reasons'])}`",
            ]
        )
    lines.extend(
        [
            "",
            "## Mission Control Guidance",
            "",
            "- Show adapter name, package, actor, capability requested/granted/blocked, gates, blocked reasons, output receipt shape, and what would make it available later.",
            "- In package preview, group requested, allowed, blocked, and future-gated adapters with required receipts and stop conditions.",
            "- Hide live tool execution, browser/OAuth launch, Gmail/calendar/Coupa/Telegram controls, credential/account prompts, send/submit/approval, arbitrary commands, raw private context, and self-authorized adapter claims.",
            "",
            "## Stable Map",
            "",
            f"- Summary included now: `{str(payload['stable_map_integration']['summary_included_in_stable_map_bundle_now']).lower()}`",
            f"- Next stable-map refresh should include `{payload['stable_map_integration']['safe_summary_to_include_next']['contract_id']}` summary.",
            "",
            "## Boundary",
            "",
        ]
    )
    for key, value in NO_AUTHORITY_FLAGS.items():
        lines.append(f"- `{key}` = `{value}`")
    return "\n".join(lines) + "\n"


def export_tool_adapter_receipt_contract(
    *,
    repo_root: str | Path = ROOT,
    export_root: str | Path = DEFAULT_EXPORT_ROOT,
    generated_at: str | None = None,
) -> ToolAdapterReceiptExportResult:
    payload = build_tool_adapter_receipt_contract(repo_root=repo_root, generated_at=generated_at)
    root = Path(export_root)
    if not root.is_absolute():
        root = Path(repo_root) / root
    root.mkdir(parents=True, exist_ok=True)
    json_path = root / JSON_EXPORT_NAME
    operator_path = root / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(format_operator_markdown(payload), encoding="utf-8")
    return ToolAdapterReceiptExportResult(
        schema_version=SCHEMA_VERSION,
        json_path=json_path.as_posix(),
        operator_path=operator_path.as_posix(),
        receipt_type_count=len(RECEIPT_TYPES),
        receipt_state_count=len(RECEIPT_STATES),
        capability_class_count=len(CAPABILITY_CLASSES),
        example_count=len(EXAMPLE_RECEIPTS),
        live_tool_execution_added=False,
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export the Tool Adapter Receipt Contract read-model.")
    parser.add_argument("--repo-root", default=ROOT.as_posix())
    parser.add_argument("--export-root", default=DEFAULT_EXPORT_ROOT.as_posix())
    parser.add_argument("--format", choices=("summary", "json", "operator"), default="operator")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    result = export_tool_adapter_receipt_contract(
        repo_root=args.repo_root,
        export_root=args.export_root,
    )
    summary = {
        "schema_version": result.schema_version,
        "json_path": result.json_path,
        "operator_path": result.operator_path,
        "receipt_type_count": result.receipt_type_count,
        "receipt_state_count": result.receipt_state_count,
        "capability_class_count": result.capability_class_count,
        "example_count": result.example_count,
        "live_tool_execution_added": result.live_tool_execution_added,
    }
    if args.format in {"summary", "json"}:
        print(stable_json(summary), end="")
    else:
        print(f"Tool Adapter Receipt Contract: `{result.schema_version}`")
        print(f"- JSON: `{result.json_path}`")
        print(f"- Operator: `{result.operator_path}`")
    return 0


__all__ = [
    "BINDING_FAIL_CLOSED_REASONS",
    "CAPABILITY_CLASSES",
    "JSON_EXPORT_NAME",
    "NO_AUTHORITY_FLAGS",
    "OPERATOR_EXPORT_NAME",
    "RECEIPT_FIELDS",
    "RECEIPT_STATES",
    "RECEIPT_TYPES",
    "SCHEMA_VERSION",
    "build_tool_adapter_receipt_contract",
    "export_tool_adapter_receipt_contract",
    "format_operator_markdown",
    "stable_json",
]


if __name__ == "__main__":
    raise SystemExit(main())
