"""Model Selection Receipt Contract v0 for OpenClaw.

This read-model defines deterministic proof for actor/model choice. It records
why a package selected, blocked, deferred, escalated, or required human review
for a model class. It is metadata only: no model calls, model router runtime,
agent activation, tool execution, external API access, memory expansion,
browser/OAuth/account access, credentials, send/submit/approval, or PC
system-drive writes are created.
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

SCHEMA_VERSION = "model_selection_receipt_contract_v0"
JSON_EXPORT_NAME = "model_selection_receipt_contract.json"
OPERATOR_EXPORT_NAME = "model_selection_receipt_contract_OPERATOR.md"

NO_AUTHORITY_FLAGS = {
    "runtime_authority": False,
    "model_call_authority": False,
    "model_api_execution_authority": False,
    "model_router_runtime_authority": False,
    "agent_activation_authority": False,
    "tool_execution_authority": False,
    "external_api_access_authority": False,
    "browser_oauth_account_access_enabled": False,
    "gmail_calendar_coupa_telegram_enabled": False,
    "credential_authority": False,
    "send_submit_approval_enabled": False,
    "network_execution_enabled": False,
    "runtime_daemon_enabled": False,
    "planner_builder_execution_enabled": False,
    "queue_autonomy_execution_enabled": False,
    "hidden_model_routing_enabled": False,
    "hidden_memory_capture_enabled": False,
    "external_retained_memory_enabled": False,
    "raw_private_body_ingestion_enabled": False,
    "vector_memory_expansion_enabled": False,
    "broad_filesystem_indexing_enabled": False,
    "repo_b_mutation_enabled": False,
    "mission_control_app_authority_added": False,
    "mac_sync_or_import_triggered": False,
    "pc_c_drive_artifact_write_allowed": False,
    "operator_final_authority": True,
}

DECISION_TYPES = (
    "MODEL_SELECTED",
    "MODEL_BLOCKED",
    "MODEL_DEFERRED",
    "MODEL_ESCALATED_TO_OPERATOR",
    "MODEL_ESCALATED_TO_GUARDIAN",
    "MODEL_REQUIRES_REDACTION",
    "MODEL_REQUIRES_LOCAL_ONLY",
    "MODEL_REQUIRES_PACKAGE_RECOMPILE",
    "MODEL_REQUIRES_MEMORY_SCOPE_REVIEW",
    "MODEL_REQUIRES_TOOL_GATE_REVIEW",
    "MODEL_POLICY_CONFLICT",
    "MODEL_UNKNOWN_FAIL_CLOSED",
)

SELECTION_STATES = (
    "SELECTION_REQUESTED",
    "POLICY_INPUTS_COLLECTED",
    "SENSITIVITY_CLASSIFIED",
    "MEMORY_SCOPE_CHECKED",
    "TOOL_ADAPTERS_CHECKED",
    "ACTOR_ELIGIBILITY_CHECKED",
    "MODEL_CLASS_EVALUATED",
    "GATES_IDENTIFIED",
    "RECEIPT_READY",
    "SELECTION_ALLOWED_PREVIEW_ONLY",
    "SELECTION_BLOCKED",
    "SELECTION_DEFERRED",
    "SELECTION_ESCALATED",
    "SELECTION_REVOKED",
    "SELECTION_QUARANTINED",
    "UNKNOWN_FAIL_CLOSED",
)

MODEL_CLASSES = (
    "local_small_fast",
    "local_reasoning",
    "local_sensitive",
    "external_fast_worker",
    "external_deep_reasoner",
    "external_code_worker",
    "external_multimodal",
    "human_operator",
    "blocked_no_model",
)

SENSITIVITY_CLASSES = (
    "PUBLIC_OR_LOW",
    "INTERNAL_SYSTEM",
    "CREATIVE_PRIVATE",
    "CLIENT_PRIVATE",
    "FINANCE_PROTECTED",
    "CREDENTIAL_OR_SECRET",
    "ACCOUNT_ACCESS",
    "LEGAL_OR_COMPLIANCE",
    "UNKNOWN_SENSITIVE_FAIL_CLOSED",
)

RECEIPT_FIELDS = (
    "model_selection_receipt_id",
    "package_id",
    "package_type",
    "actor_id",
    "agent_character",
    "requested_model_class",
    "selected_model_class",
    "decision_type",
    "selection_state",
    "selection_reason",
    "policy_version",
    "actor_router_reference",
    "model_policy_reference",
    "package_preview_reference",
    "memory_scope_reference",
    "memory_candidate_receipt_refs",
    "tool_adapter_registry_reference",
    "requested_tool_adapters",
    "allowed_tool_adapters",
    "blocked_tool_adapters",
    "sensitivity",
    "context_included_refs",
    "context_excluded_refs",
    "redaction_status",
    "operator_gate_status",
    "guardian_gate_status",
    "external_model_allowed",
    "local_model_required",
    "retention_policy",
    "authority_level_required",
    "authority_level_granted",
    "runtime_dispatch_allowed",
    "model_call_performed",
    "blocked_reasons",
    "stop_conditions",
    "receipt_requirements",
    "created_at",
    "expires_or_review_after",
    "revocation_status",
    "quarantine_status",
    "receipt_hash",
    "what_would_make_selection_valid",
    "what_keeps_selection_blocked",
)

POLICY_INPUTS_REQUIRED = (
    "package_type",
    "actor_agent_identity",
    "task_domain",
    "task_risk",
    "sensitivity_class",
    "memory_scope",
    "context_refs",
    "context_exclusions",
    "requested_tools_adapters",
    "output_type",
    "proof_requirements",
    "receipt_requirements",
    "external_retention_posture",
    "operator_approval_requirement",
    "guardian_gate_requirement",
    "local_private_requirement",
    "stop_conditions",
)

FAIL_CLOSED_REASONS = (
    "UNKNOWN_ACTOR",
    "UNKNOWN_MODEL_CLASS",
    "UNKNOWN_PACKAGE_TYPE",
    "MISSING_PACKAGE_PREVIEW",
    "MISSING_MEMORY_SCOPE",
    "SENSITIVITY_UNKNOWN",
    "SENSITIVITY_BLOCKED",
    "TOOL_ADAPTER_UNKNOWN",
    "TOOL_ADAPTER_BLOCKED",
    "GUARDIAN_GATE_REQUIRED",
    "OPERATOR_APPROVAL_REQUIRED",
    "EXTERNAL_RETENTION_BLOCKED",
    "RAW_PRIVATE_CONTEXT_BLOCKED",
    "CREDENTIAL_CONTEXT_BLOCKED",
    "AUTHORITY_NOT_GRANTED",
    "RECEIPT_REQUIREMENT_MISSING",
)

KNOWN_ACTOR_IDS = (
    "operator_winship",
    "chief",
    "guardian",
    "cassandra",
    "hermes",
    "niles",
    "codex",
    "gemini_antigravity",
)


@dataclass(frozen=True)
class EvidenceSource:
    source_id: str
    path: str
    role: str


@dataclass(frozen=True)
class ModelClassReceiptPolicy:
    model_class_id: str
    current_authority_posture: str
    future_eligibility: str
    sensitivity_ceiling: str
    allowed_context_types: tuple[str, ...]
    blocked_context_types: tuple[str, ...]
    required_memory_scope: str
    required_tool_adapter_posture: str
    required_guardian_gate: bool
    required_operator_approval: bool
    receipt_requirement: str
    external_retention_rule: str
    what_blocks_selection: tuple[str, ...]


@dataclass(frozen=True)
class ActorModelSelectionRule:
    actor_id: str
    agent_character: str
    current_live_model_class: str
    future_eligible_model_classes: tuple[str, ...]
    sensitivity_posture: str
    required_gates: tuple[str, ...]
    blocked_authority: tuple[str, ...]
    selection_guidance: str


@dataclass(frozen=True)
class SensitivityRoutingRule:
    sensitivity: str
    default_result: str
    local_private_requirement: str
    external_model_rule: str
    guardian_gate_required: bool
    operator_approval_required: bool
    blocked_contexts: tuple[str, ...]


@dataclass(frozen=True)
class ExampleModelSelectionReceipt:
    example_id: str
    title: str
    package_id: str
    package_type: str
    actor_id: str
    agent_character: str
    requested_model_class: str
    selected_model_class: str
    decision_type: str
    selection_state: str
    selection_reason: str
    sensitivity: str
    external_model_allowed: bool
    local_model_required: bool
    blocked_reasons: tuple[str, ...]
    what_would_make_selection_valid: str
    what_keeps_selection_blocked: str


@dataclass(frozen=True)
class RecommendedLane:
    lane_id: str
    title: str
    priority: str
    why_next: str
    hard_boundary: str


@dataclass(frozen=True)
class ModelSelectionReceiptExportResult:
    schema_version: str
    json_path: str
    operator_path: str
    decision_type_count: int
    model_class_count: int
    example_count: int
    model_call_authority_added: bool
    model_router_runtime_authority_added: bool


EVIDENCE_SOURCES = (
    EvidenceSource("agent_platform_alignment", "generated/read_models/agent_platform_alignment.json", "agent-platform primitive map"),
    EvidenceSource("agent_identity_actor_router_contract", "generated/read_models/agent_identity_actor_router_contract.json", "actor/agent identities and routing boundaries"),
    EvidenceSource("model_selection_policy_contract", "generated/read_models/model_selection_policy_contract.json", "source policy for model classes and sensitivity posture"),
    EvidenceSource("agent_package_preview_contract", "generated/read_models/agent_package_preview_contract.json", "package preview mission/context/authority boundaries"),
    EvidenceSource("agent_memory_scope_contract", "generated/read_models/agent_memory_scope_contract.json", "memory/context inclusion and exclusion policy"),
    EvidenceSource("tool_protocol_adapter_registry_contract", "generated/read_models/tool_protocol_adapter_registry_contract.json", "tool adapter eligibility and blocked/future-gated posture"),
    EvidenceSource("memory_candidate_receipt_contract", "generated/read_models/memory_candidate_receipt_contract.json", "reviewed candidate context receipt posture"),
    EvidenceSource("package_compiler_contract", "generated/read_models/package_compiler_contract.json", "deterministic package boundary validation"),
    EvidenceSource("guardian_protected_access_gate_spec", "generated/read_models/guardian_protected_access_gate_spec.json", "Guardian protected-access gate posture"),
    EvidenceSource("stable_map_bundle_contract", "generated/read_models/operator_map_bundle_contract.json", "stable map contract when present"),
    EvidenceSource("threshold_map_contract", "generated/read_models/operator_threshold_map_contract.json", "threshold/lane destiny contract"),
)


MODEL_CLASS_POLICIES = (
    ModelClassReceiptPolicy(
        "local_small_fast",
        "metadata_only_future_eligible_no_local_call",
        "future low-risk local triage after local inventory and receipts",
        "INTERNAL_SYSTEM",
        ("read_model_summary", "stable_map_reference", "operator_low_risk_context"),
        ("credentials", "account_access", "raw_private_body", "finance_protected_raw_context"),
        "memory_scope_checked",
        "read_only_or_preview_only_adapters",
        False,
        True,
        "model selection receipt and post-result receipt",
        "no external retention",
        ("missing local model inventory", "sensitivity exceeds internal", "package preview missing"),
    ),
    ModelClassReceiptPolicy(
        "local_reasoning",
        "metadata_only_future_eligible_no_local_call",
        "future private/internal reasoning after local capability proof",
        "CREATIVE_PRIVATE",
        ("read_model_summary", "stable_map_reference", "package_preview_reference", "memory_candidate_refs"),
        ("credentials", "account_access", "raw_private_body", "protected_finance_raw_context"),
        "memory_scope_checked",
        "known_adapters_only_no_execution",
        False,
        True,
        "model selection receipt, local model inventory receipt, result receipt",
        "no external retention",
        ("local model proof missing", "unknown sensitivity", "tool adapter unknown"),
    ),
    ModelClassReceiptPolicy(
        "local_sensitive",
        "metadata_only_future_eligible_no_local_call",
        "future private/offline sensitive handling after security audit",
        "LEGAL_OR_COMPLIANCE",
        ("protected_metadata_refs", "guardian_approved_protected_metadata", "redacted_source_cards"),
        ("credentials", "account_access", "raw_private_body_without_gate", "browser_session_material"),
        "protected_memory_scope_checked",
        "Guardian-gated read-only metadata adapters",
        True,
        True,
        "Guardian gate receipt, model selection receipt, sensitivity receipt, result receipt",
        "no external retention",
        ("security audit missing", "Guardian gate missing", "raw private body included", "credential context"),
    ),
    ModelClassReceiptPolicy(
        "external_fast_worker",
        "blocked_no_external_model_call",
        "future low-sensitivity external review after gates",
        "PUBLIC_OR_LOW",
        ("public_or_repo_safe_refs", "sanitized_package_preview"),
        ("client_private", "finance_protected", "credentials", "account_access", "raw_private_body"),
        "memory_scope_checked_and_sanitized",
        "preview-only adapters",
        False,
        True,
        "Operator approval receipt and external model use receipt",
        "external retention blocked; no retained memory allowed",
        ("non-public sensitivity", "operator approval missing", "external retention possible"),
    ),
    ModelClassReceiptPolicy(
        "external_deep_reasoner",
        "blocked_no_external_model_call",
        "future sanitized architecture/doctrine reasoning after gates",
        "PUBLIC_OR_LOW",
        ("public_or_repo_safe_refs", "sanitized_architecture_packet"),
        ("internal_private_unredacted", "client_private", "finance_protected", "credentials", "account_access"),
        "memory_scope_checked_and_sanitized",
        "preview-only adapters",
        True,
        True,
        "Operator approval receipt, Guardian external-model gate receipt, result receipt",
        "external retention blocked; no retained memory allowed",
        ("sensitive/private context", "Guardian gate missing", "operator approval missing", "package unsanitized"),
    ),
    ModelClassReceiptPolicy(
        "external_code_worker",
        "blocked_no_external_model_call",
        "future scoped code/test worker after package boundaries",
        "INTERNAL_SYSTEM",
        ("repo_safe_file_refs", "scoped_diff_refs", "test_refs", "package_preview_reference"),
        ("credentials", "no_go_paths", "raw_private_body", "broad_repo_context", "protected_context"),
        "scoped_workspace_memory_scope_checked",
        "scoped code/test adapters only; no network/credentials",
        False,
        True,
        "package boundary receipt, operator preview receipt, result receipt",
        "external retention blocked; no durable retained memory",
        ("allowed roots missing", "forbidden path requested", "network/credential path", "broad context"),
    ),
    ModelClassReceiptPolicy(
        "external_multimodal",
        "blocked_no_external_model_call",
        "future sanitized visual/audio/document review after media policy",
        "PUBLIC_OR_LOW",
        ("sanitized_screenshot_refs", "public_media_refs", "ui_proof_refs"),
        ("private_media", "client_private", "finance_protected", "credentials", "account_access"),
        "media_context_scope_checked",
        "preview-only media/proof adapters",
        True,
        True,
        "media source receipt, operator approval receipt, Guardian gate when sensitive",
        "external retention blocked; no retained media memory",
        ("media sensitivity unknown", "operator approval missing", "private media", "Guardian gate missing"),
    ),
    ModelClassReceiptPolicy(
        "human_operator",
        "human_decision_authority_only",
        "available for operator review and final action authority",
        "UNKNOWN_SENSITIVE_FAIL_CLOSED",
        ("all summarized refs visible to operator", "proof detail refs"),
        ("hidden model memory", "unreviewed secret material surfaced as package context"),
        "operator review surface",
        "none; human is not a tool adapter",
        False,
        False,
        "operator decision receipt when needed",
        "not a model; no external retention",
        ("operator absent when approval required", "proof/detail unavailable", "unsafe raw secret display"),
    ),
    ModelClassReceiptPolicy(
        "blocked_no_model",
        "active_safe_default",
        "always valid when model selection is unsafe, incomplete, or pre-runtime",
        "UNKNOWN_SENSITIVE_FAIL_CLOSED",
        ("package metadata refs", "blocked reason refs"),
        (),
        "none required to block",
        "none required to block",
        False,
        False,
        "blocked model selection receipt",
        "no retention",
        (),
    ),
)


ACTOR_RULES = (
    ActorModelSelectionRule(
        "operator_winship",
        "Operator / Winship",
        "human_operator",
        ("human_operator",),
        "final human authority; operator statements are context, not machine proof",
        ("clear package preview", "proof/detail available"),
        ("model worker replacement", "machine proof by statement alone"),
        "Route final sensitive approval and unclear tradeoffs to the human operator.",
    ),
    ActorModelSelectionRule(
        "chief",
        "Chief",
        "blocked_no_model",
        ("local_reasoning", "external_deep_reasoner"),
        "diagnostic/readback only; no repairs or self-authorization",
        ("package preview", "operator approval for future execution", "receipts"),
        ("repair execution", "remount", "cleanup/delete", "self-authorized tools"),
        "Chief may get future reasoning support for diagnostics only through package preview and gates.",
    ),
    ActorModelSelectionRule(
        "guardian",
        "Guardian",
        "blocked_no_model",
        ("local_sensitive", "local_reasoning"),
        "safety/protected-access defaults local/private or blocked",
        ("Guardian gate", "operator approval", "sensitivity receipt"),
        ("self-authorization", "external sensitive use without gate", "approval execution"),
        "Guardian model selection is strict and cannot bypass operator authority.",
    ),
    ActorModelSelectionRule(
        "cassandra",
        "Cassandra",
        "blocked_no_model",
        ("local_sensitive", "local_reasoning"),
        "finance/comms protected contexts default local/private or blocked",
        ("Guardian gate for protected context", "operator approval", "redaction receipt"),
        ("Gmail/Coupa/calendar raw bodies", "send/submit/approval", "account access"),
        "Cassandra finance/comms packages require protected metadata and gates before any future model use.",
    ),
    ActorModelSelectionRule(
        "hermes",
        "Hermes",
        "blocked_no_model",
        ("local_reasoning", "external_deep_reasoner"),
        "architecture/doctrine can be future external only when sanitized and non-sensitive",
        ("package preview", "sensitivity classification", "operator approval for external use"),
        ("runtime execution", "private raw body ingestion", "hidden routing"),
        "Hermes may later use reasoning classes for non-sensitive architecture packages.",
    ),
    ActorModelSelectionRule(
        "niles",
        "Niles",
        "blocked_no_model",
        ("local_reasoning", "external_multimodal", "external_deep_reasoner"),
        "creative/music/art context must be scoped; broad private archive ingestion is blocked",
        ("project capsule refs", "rights/sensitivity review", "operator approval"),
        ("broad private archive ingestion", "release/upload/account action", "unrelated private context"),
        "Niles model choice can be creative only when context is scoped and safe.",
    ),
    ActorModelSelectionRule(
        "codex",
        "Codex",
        "blocked_no_model",
        ("external_code_worker", "local_reasoning"),
        "implementation worker outside OpenClaw runtime; future routing only through scoped code packages",
        ("package boundary receipt", "allowed roots", "operator preview", "test/result receipts"),
        ("network", "credentials", "broad repo expansion", "hidden memory", "canonical writes"),
        "Codex remains manual/scoped worker until future runtime gates exist.",
    ),
    ActorModelSelectionRule(
        "gemini_antigravity",
        "Gemini / Antigravity",
        "blocked_no_model",
        ("external_fast_worker", "external_code_worker", "external_deep_reasoner", "external_multimodal"),
        "external worker candidate only through package-bounded sanitized context",
        ("package preview", "sensitivity classification", "operator approval", "no-retention receipt"),
        ("retained memory", "canonical writes", "raw protected material", "broad context"),
        "Gemini/Antigravity can be future-eligible only with package-bounded context and no retention.",
    ),
)


SENSITIVITY_RULES = (
    SensitivityRoutingRule(
        "PUBLIC_OR_LOW",
        "external_or_local_future_eligible_after_preview",
        "not required unless package says so",
        "external may be future-eligible with operator approval and no retention",
        False,
        True,
        ("credentials", "account access", "raw private body"),
    ),
    SensitivityRoutingRule(
        "INTERNAL_SYSTEM",
        "local_private_or_blocked_by_default",
        "preferred for internal OpenClaw context",
        "external only after sanitization, operator approval, and no-retention receipt",
        False,
        True,
        ("credentials", "account access", "no-go paths", "raw private body"),
    ),
    SensitivityRoutingRule(
        "CREATIVE_PRIVATE",
        "local_private_or_blocked_by_default",
        "required unless scoped creative context is explicitly approved",
        "external only with scoped creative packet, rights/sensitivity review, and no retention",
        False,
        True,
        ("unrelated private archive", "account sessions", "client/legal/finance material"),
    ),
    SensitivityRoutingRule(
        "CLIENT_PRIVATE",
        "blocked_no_model_or_local_sensitive_future",
        "required",
        "external blocked unless a later explicit protected gate allows sanitized metadata",
        True,
        True,
        ("raw client documents", "unredacted private body", "external retention"),
    ),
    SensitivityRoutingRule(
        "FINANCE_PROTECTED",
        "blocked_no_model_or_local_sensitive_future",
        "required",
        "external blocked for raw/protected finance context",
        True,
        True,
        ("Coupa/Excel raw bodies", "bank/remit/check data", "account access", "submit/approval"),
    ),
    SensitivityRoutingRule(
        "CREDENTIAL_OR_SECRET",
        "blocked_no_model",
        "not applicable; credentials must not be context",
        "external blocked",
        True,
        True,
        ("credentials", "tokens", "cookies", "OAuth state", "secrets"),
    ),
    SensitivityRoutingRule(
        "ACCOUNT_ACCESS",
        "blocked_no_model",
        "not applicable; account access must not be model context",
        "external blocked",
        True,
        True,
        ("browser session", "portal access", "OAuth", "account mutation"),
    ),
    SensitivityRoutingRule(
        "LEGAL_OR_COMPLIANCE",
        "blocked_no_model_or_local_sensitive_future",
        "required",
        "external blocked unless later compliance/security gate explicitly allows sanitized metadata",
        True,
        True,
        ("raw legal/client material", "unredacted compliance documents", "external retention"),
    ),
    SensitivityRoutingRule(
        "UNKNOWN_SENSITIVE_FAIL_CLOSED",
        "blocked_no_model",
        "required after classification",
        "external blocked",
        True,
        True,
        ("unknown source", "unknown sensitivity", "missing memory scope"),
    ),
)


EXAMPLE_RECEIPTS = (
    ExampleModelSelectionReceipt(
        "chief_check_engine_diagnostic_package",
        "Chief Check Engine Diagnostic Package",
        "package_chief_check_engine_diagnostic",
        "check_light_diagnostic_package",
        "chief",
        "Chief",
        "external_deep_reasoner",
        "blocked_no_model",
        "MODEL_BLOCKED",
        "SELECTION_BLOCKED",
        "Chief diagnostics may be previewed, but OpenClaw has no live model dispatch authority.",
        "INTERNAL_SYSTEM",
        False,
        True,
        ("AUTHORITY_NOT_GRANTED", "MISSING_PACKAGE_PREVIEW"),
        "Package preview, model policy receipt, operator approval, and future runtime gate.",
        "No live dispatch authority and package/runtime gates are not active.",
    ),
    ExampleModelSelectionReceipt(
        "cassandra_capital_hilton_invoice_review",
        "Cassandra Capital Hilton Invoice Review",
        "package_cassandra_capital_hilton_invoice_review",
        "finance_ap_review",
        "cassandra",
        "Cassandra",
        "local_sensitive",
        "blocked_no_model",
        "MODEL_DEFERRED",
        "SELECTION_DEFERRED",
        "Finance protected context needs proof metadata, Guardian gate, and no account access.",
        "FINANCE_PROTECTED",
        False,
        True,
        ("GUARDIAN_GATE_REQUIRED", "SENSITIVITY_BLOCKED", "TOOL_ADAPTER_BLOCKED", "AUTHORITY_NOT_GRANTED"),
        "Protected proof metadata, Guardian review, operator approval, and local/private model receipt after security.",
        "Coupa/Excel proof is missing or protected, account access is blocked, and no runtime authority exists.",
    ),
    ExampleModelSelectionReceipt(
        "codex_backend_contract_implementation",
        "Codex Backend Contract Implementation",
        "package_codex_backend_contract_implementation",
        "code_implementation",
        "codex",
        "Codex",
        "external_code_worker",
        "blocked_no_model",
        "MODEL_DEFERRED",
        "SELECTION_ALLOWED_PREVIEW_ONLY",
        "Manual Codex worker lanes may operate by prompt, but OpenClaw runtime has no model dispatch authority.",
        "INTERNAL_SYSTEM",
        False,
        False,
        ("AUTHORITY_NOT_GRANTED",),
        "Scoped package, allowed roots, receipt requirements, and future runtime gate.",
        "No OpenClaw runtime model authority; manual worker use remains outside model router execution.",
    ),
    ExampleModelSelectionReceipt(
        "niles_creative_metadata_review",
        "Niles Creative Metadata Review",
        "package_niles_creative_metadata_review",
        "music_creative_review",
        "niles",
        "Niles",
        "external_multimodal",
        "blocked_no_model",
        "MODEL_DEFERRED",
        "SELECTION_DEFERRED",
        "Creative review may be future-eligible with scoped context, but broad private archive ingestion is blocked.",
        "CREATIVE_PRIVATE",
        False,
        True,
        ("OPERATOR_APPROVAL_REQUIRED", "MISSING_MEMORY_SCOPE"),
        "Scoped project capsule, rights/sensitivity review, operator approval, and no-retention receipt.",
        "Creative context is not yet scoped and external retention remains blocked.",
    ),
    ExampleModelSelectionReceipt(
        "guardian_protected_evidence_review",
        "Guardian Protected Evidence Review",
        "package_guardian_protected_evidence_review",
        "protected_access_review",
        "guardian",
        "Guardian",
        "local_sensitive",
        "blocked_no_model",
        "MODEL_BLOCKED",
        "SELECTION_BLOCKED",
        "Protected evidence review is metadata-only and cannot expose raw private bodies.",
        "LEGAL_OR_COMPLIANCE",
        False,
        True,
        ("GUARDIAN_GATE_REQUIRED", "RAW_PRIVATE_CONTEXT_BLOCKED", "AUTHORITY_NOT_GRANTED"),
        "Protected metadata refs, Guardian gate receipt, operator approval, and local sensitive model proof.",
        "Raw protected context is blocked and no live model route exists.",
    ),
    ExampleModelSelectionReceipt(
        "gemini_antigravity_visual_polish",
        "Gemini/Antigravity Visual Polish",
        "package_gemini_antigravity_visual_polish",
        "mission_control_ux",
        "gemini_antigravity",
        "Gemini / Antigravity",
        "external_multimodal",
        "blocked_no_model",
        "MODEL_DEFERRED",
        "SELECTION_DEFERRED",
        "External visual worker is only a package-bounded candidate; no memory retention or canonical writes.",
        "PUBLIC_OR_LOW",
        False,
        False,
        ("OPERATOR_APPROVAL_REQUIRED", "EXTERNAL_RETENTION_BLOCKED"),
        "Sanitized visual refs, operator approval, external use receipt, and no-retention proof.",
        "External model authority and no-retention receipts are not active.",
    ),
    ExampleModelSelectionReceipt(
        "unknown_tool_memory_package",
        "Unknown Tool/Memory Package",
        "package_unknown_tool_memory",
        "unknown_package_type",
        "unknown_actor",
        "Unknown",
        "external_deep_reasoner",
        "blocked_no_model",
        "MODEL_UNKNOWN_FAIL_CLOSED",
        "UNKNOWN_FAIL_CLOSED",
        "Missing actor, memory scope, tool adapter, and sensitivity classification.",
        "UNKNOWN_SENSITIVE_FAIL_CLOSED",
        False,
        True,
        ("UNKNOWN_ACTOR", "UNKNOWN_PACKAGE_TYPE", "MISSING_MEMORY_SCOPE", "TOOL_ADAPTER_UNKNOWN", "SENSITIVITY_UNKNOWN"),
        "Known actor, known package type, memory scope, tool adapter registry match, and sensitivity classification.",
        "Unknown inputs fail closed.",
    ),
)


RECOMMENDED_NEXT_LANES = (
    RecommendedLane(
        "package_preview_receipt_v0",
        "Package Preview Receipt v0",
        "P1",
        "Model selection receipts depend on package previews; package previews now need their own receipt grammar.",
        "receipt metadata only; no dispatch",
    ),
    RecommendedLane(
        "tool_adapter_receipt_v0",
        "Tool Adapter Receipt v0",
        "P1",
        "Tool adapter references in model receipts need a receipt grammar before future use.",
        "receipt metadata only; no live tool execution",
    ),
    RecommendedLane(
        "memory_review_promotion_surface_v0",
        "Memory Review / Promotion Surface v0",
        "P2",
        "Reviewed memory candidates need a read-only operator surface before any promotion lane.",
        "read-only UI/contract lane; no canonical memory mutation",
    ),
    RecommendedLane(
        "mission_control_package_preview_actor_routing_surface_v0",
        "Mission Control Package Preview / Actor Routing Surface v0",
        "P2",
        "Mission Control can render actor/model/tool/memory receipts in package preview.",
        "Mac read-only UI; no backend command authority",
    ),
    RecommendedLane(
        "model_router_implementation_plan_v0",
        "Model Router Implementation Plan v0",
        "P3",
        "A future router plan can remain preview-only until security gates and receipts are complete.",
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


def _model_class_record(policy: ModelClassReceiptPolicy) -> dict[str, Any]:
    return {
        "model_class_id": policy.model_class_id,
        "current_authority_posture": policy.current_authority_posture,
        "future_eligibility": policy.future_eligibility,
        "sensitivity_ceiling": policy.sensitivity_ceiling,
        "allowed_context_types": list(policy.allowed_context_types),
        "blocked_context_types": list(policy.blocked_context_types),
        "required_memory_scope": policy.required_memory_scope,
        "required_tool_adapter_posture": policy.required_tool_adapter_posture,
        "required_guardian_gate": policy.required_guardian_gate,
        "required_operator_approval": policy.required_operator_approval,
        "receipt_requirement": policy.receipt_requirement,
        "external_retention_rule": policy.external_retention_rule,
        "what_blocks_selection": list(policy.what_blocks_selection),
        "model_callable_now": False,
        "may_self_select": False,
    }


def _actor_rule_record(rule: ActorModelSelectionRule) -> dict[str, Any]:
    return {
        "actor_id": rule.actor_id,
        "agent_character": rule.agent_character,
        "current_live_model_class": rule.current_live_model_class,
        "future_eligible_model_classes": list(rule.future_eligible_model_classes),
        "sensitivity_posture": rule.sensitivity_posture,
        "required_gates": list(rule.required_gates),
        "blocked_authority": list(rule.blocked_authority),
        "selection_guidance": rule.selection_guidance,
        "can_self_select_model": False,
        "can_upgrade_model_class": False,
        "runtime_dispatch_allowed_now": False,
    }


def _sensitivity_rule_record(rule: SensitivityRoutingRule) -> dict[str, Any]:
    return {
        "sensitivity": rule.sensitivity,
        "default_result": rule.default_result,
        "local_private_requirement": rule.local_private_requirement,
        "external_model_rule": rule.external_model_rule,
        "guardian_gate_required": rule.guardian_gate_required,
        "operator_approval_required": rule.operator_approval_required,
        "blocked_contexts": list(rule.blocked_contexts),
    }


def _example_record(example: ExampleModelSelectionReceipt) -> dict[str, Any]:
    return {
        "model_selection_receipt_id": f"model_selection_receipt_{example.example_id}",
        "example_id": example.example_id,
        "title": example.title,
        "package_id": example.package_id,
        "package_type": example.package_type,
        "actor_id": example.actor_id,
        "agent_character": example.agent_character,
        "requested_model_class": example.requested_model_class,
        "selected_model_class": example.selected_model_class,
        "decision_type": example.decision_type,
        "selection_state": example.selection_state,
        "selection_reason": example.selection_reason,
        "policy_version": SCHEMA_VERSION,
        "actor_router_reference": "generated/read_models/agent_identity_actor_router_contract.json",
        "model_policy_reference": "generated/read_models/model_selection_policy_contract.json",
        "package_preview_reference": "generated/read_models/agent_package_preview_contract.json",
        "memory_scope_reference": "generated/read_models/agent_memory_scope_contract.json",
        "memory_candidate_receipt_refs": [],
        "tool_adapter_registry_reference": "generated/read_models/tool_protocol_adapter_registry_contract.json",
        "requested_tool_adapters": [],
        "allowed_tool_adapters": [],
        "blocked_tool_adapters": [],
        "sensitivity": example.sensitivity,
        "context_included_refs": ["example_context_refs_only"],
        "context_excluded_refs": ["raw_private_bodies", "credentials", "account_sessions"],
        "redaction_status": "reference_only_or_not_required",
        "operator_gate_status": "required_if_future_execution_requested",
        "guardian_gate_status": "required_if_sensitive_or_protected",
        "external_model_allowed": example.external_model_allowed,
        "local_model_required": example.local_model_required,
        "retention_policy": "no_external_retained_memory",
        "authority_level_required": "future_gate_required",
        "authority_level_granted": "preview_only",
        "runtime_dispatch_allowed": False,
        "model_call_performed": False,
        "blocked_reasons": list(example.blocked_reasons),
        "stop_conditions": ["missing required gate", "unknown sensitivity", "authority not granted", "receipt malformed"],
        "receipt_requirements": ["model selection receipt", "package preview receipt", "result receipt if future action"],
        "created_at": "example_static_timestamp",
        "expires_or_review_after": "requires_review_before_future_dispatch",
        "revocation_status": "not_revoked",
        "quarantine_status": "not_quarantined",
        "receipt_hash": "example_hash_computed_in_real_receipt",
        "what_would_make_selection_valid": example.what_would_make_selection_valid,
        "what_keeps_selection_blocked": example.what_keeps_selection_blocked,
    }


def _recommended_lane_record(lane: RecommendedLane) -> dict[str, Any]:
    return {
        "lane_id": lane.lane_id,
        "title": lane.title,
        "priority": lane.priority,
        "why_next": lane.why_next,
        "hard_boundary": lane.hard_boundary,
    }


def build_model_selection_receipt_contract(
    *,
    repo_root: str | Path = ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    evidence_sources = [_source_record(source, repo_root=repo_root) for source in EVIDENCE_SOURCES]
    examples = [_example_record(example) for example in EXAMPLE_RECEIPTS]
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": "model_selection_receipt_contract",
        "generated_at": generated_at,
        **NO_AUTHORITY_FLAGS,
        "contract_status": "deterministic_model_selection_receipt_metadata_only",
        "operator_summary": (
            "OpenClaw now has a deterministic receipt grammar for actor/model choice. It proves why a package "
            "selected, blocked, deferred, escalated, or failed closed for a model class. It does not call models, "
            "activate agents, or grant dispatch authority."
        ),
        "core_doctrine": {
            "model_is_actor": True,
            "agent_is_character": True,
            "package_is_deterministic_mission_payload": True,
            "model_cannot_choose_itself": True,
            "agent_cannot_choose_its_own_model": True,
            "package_cannot_override_model_policy": True,
            "worker_cannot_upgrade_itself": True,
            "sensitive_context_external_routing_requires_policy_gates_redaction_and_receipts": True,
        },
        "evidence_sources": evidence_sources,
        "decision_types": [
            {
                "decision_type": decision_type,
                "description": _decision_type_description(decision_type),
                "creates_live_model_call_authority": False,
            }
            for decision_type in DECISION_TYPES
        ],
        "selection_states": [
            {
                "selection_state": state,
                "description": _selection_state_description(state),
                "runtime_dispatch_allowed": False,
            }
            for state in SELECTION_STATES
        ],
        "model_classes": [_model_class_record(policy) for policy in MODEL_CLASS_POLICIES],
        "selection_receipt_schema": {
            "required_fields": list(RECEIPT_FIELDS),
            "hard_defaults": {
                "runtime_dispatch_allowed": False,
                "model_call_performed": False,
                "authority_level_granted": "preview_only",
            },
            "missing_required_field_result": "MODEL_UNKNOWN_FAIL_CLOSED",
            "natural_language_claim_counts_as_proof": False,
        },
        "policy_input_model": {
            "required_policy_inputs": list(POLICY_INPUTS_REQUIRED),
            "missing_input_result": "MODEL_UNKNOWN_FAIL_CLOSED",
            "missing_package_detail_result": "MODEL_REQUIRES_PACKAGE_RECOMPILE",
            "fail_closed_reasons": list(FAIL_CLOSED_REASONS),
        },
        "sensitivity_routing_rules": [_sensitivity_rule_record(rule) for rule in SENSITIVITY_RULES],
        "actor_model_selection_rules": [_actor_rule_record(rule) for rule in ACTOR_RULES],
        "package_binding_rule": {
            "package_may_receive_model_selection_receipt_only_if": [
                "package preview exists",
                "actor/agent is known",
                "model policy exists",
                "memory scope permits included context",
                "sensitivity is classified",
                "requested tools/adapters are known and allowed or explicitly blocked",
                "Guardian/Operator gates are identified",
                "receipt requirements exist",
                "stop conditions exist",
                "runtime authority is explicit and currently false unless future-approved",
            ],
            "fail_closed_reasons": list(FAIL_CLOSED_REASONS),
            "unknown_package_result": "MODEL_UNKNOWN_FAIL_CLOSED",
            "model_or_actor_self_selection_allowed": False,
        },
        "receipt_revocation_quarantine_policy": {
            "quarantine_triggers": [
                "model selected without policy reference",
                "model selected without package preview",
                "model selected with unknown sensitivity",
                "external model selected with private/protected context",
                "credential/account context included",
                "memory scope violation",
                "tool adapter violation",
                "Guardian gate missing",
                "Operator approval missing",
                "actor self-selected model",
                "model call occurred without receipt",
                "external retained memory detected",
                "receipt malformed",
                "receipt hash missing",
                "output claims authority not granted",
            ],
            "revocation_triggers": [
                "policy changed",
                "sensitivity classification changed",
                "memory candidate revoked",
                "package preview revoked",
                "tool adapter quarantined",
                "Guardian gate revoked",
                "Operator approval revoked",
                "model provider no longer eligible",
                "receipt conflict discovered",
            ],
            "missing_or_malformed_receipt_result": "SELECTION_QUARANTINED",
            "quarantine_is_non_destructive": True,
        },
        "example_model_selection_receipts": examples,
        "relationship_to_existing_contracts": {
            "agent_platform_alignment": "defines the platform primitive map",
            "agent_identity_actor_router_contract": "says which actor/agent should handle the package",
            "model_selection_policy_contract": "says what model classes are eligible",
            "agent_package_preview_contract": "defines mission, context, and boundaries",
            "agent_memory_scope_contract": "says what context may be included",
            "tool_protocol_adapter_registry_contract": "says what adapters may be referenced",
            "memory_candidate_receipt_contract": "supplies reviewed context candidates",
            "stable_map_bundle": "may carry a summary in a later refresh",
            "threshold_map_contract": "can route threshold lanes without granting execution",
            "guardian_protected_access_gate_spec": "gates sensitive/protected eligibility",
        },
        "mission_control_surface_guidance": {
            "model_selection_preview": [
                "requested model class",
                "selected or blocked model class",
                "decision type",
                "actor/agent",
                "sensitivity",
                "memory scope status",
                "tool adapter status",
                "Guardian/Operator gates",
                "external model allowed yes/no",
                "runtime dispatch allowed yes/no",
                "blocked reasons",
                "what would make selection valid",
            ],
            "actor_detail": [
                "current live model: blocked/no model unless explicitly future-gated",
                "future eligible model classes",
                "sensitivity ceiling",
                "external model restrictions",
                "local/private requirement",
            ],
            "package_preview_model_section": [
                "actor/model binding",
                "model policy references",
                "model selection receipt",
                "context included/excluded",
                "stop conditions",
                "receipt requirements",
            ],
            "hide_or_block": [
                "model launch controls",
                "provider credential prompts",
                "browser/OAuth prompts",
                "fake confidence percentages",
                "hidden routing",
                "external retained-memory assumptions",
                "agent chose its own model claims",
            ],
        },
        "stable_map_integration": {
            "registry_generated_as_read_model": True,
            "summary_included_in_stable_map_bundle_now": False,
            "reason_not_included_now": (
                "Stable-map/sync files are separate dirty lane residue in this worktree; this contract does not reopen "
                "bridge churn or mutate the stable map bundle."
            ),
            "safe_summary_to_include_next": {
                "contract_id": "model_selection_receipt_contract",
                "model_classes_count": len(MODEL_CLASSES),
                "decision_types_count": len(DECISION_TYPES),
                "blocked_states": ["SELECTION_BLOCKED", "SELECTION_REVOKED", "SELECTION_QUARANTINED", "UNKNOWN_FAIL_CLOSED"],
                "current_default_live_model_posture": "blocked_no_model except operator_winship uses human_operator",
                "next_recommended_lane": "package_preview_receipt_v0",
            },
            "next_map_bundle_refresh_requirement": "Include this summary in the next stable map bundle refresh after this contract lands.",
        },
        "recommended_next_lanes": [_recommended_lane_record(lane) for lane in RECOMMENDED_NEXT_LANES],
        "machine_proof": {
            "source_read_models_present": {source["source_id"]: source["present"] for source in evidence_sources},
            "decision_type_count": len(DECISION_TYPES),
            "selection_state_count": len(SELECTION_STATES),
            "model_class_count": len(MODEL_CLASSES),
            "receipt_required_field_count": len(RECEIPT_FIELDS),
            "example_receipt_ids": [example["model_selection_receipt_id"] for example in examples],
            "model_call_performed": False,
            "runtime_dispatch_allowed": False,
            "model_router_runtime_added": False,
            "agent_activation_added": False,
            "tool_execution_added": False,
            "external_api_access_added": False,
            "hidden_model_routing_added": False,
            "external_retained_memory_added": False,
            "pc_c_drive_artifact_write_added": False,
            "content_hash": None,
        },
    }
    payload["machine_proof"]["content_hash"] = _content_hash(payload)
    return payload


def _decision_type_description(decision_type: str) -> str:
    descriptions = {
        "MODEL_SELECTED": "Future state: a model class is selected by policy and receipts, without implying a current call.",
        "MODEL_BLOCKED": "Policy blocks model selection.",
        "MODEL_DEFERRED": "Model selection is plausible later but prerequisites are missing.",
        "MODEL_ESCALATED_TO_OPERATOR": "Human operator must decide or approve.",
        "MODEL_ESCALATED_TO_GUARDIAN": "Guardian gate must review sensitive/protected posture.",
        "MODEL_REQUIRES_REDACTION": "Context must be redacted/reference-only before selection.",
        "MODEL_REQUIRES_LOCAL_ONLY": "Context requires local/private handling or blocking.",
        "MODEL_REQUIRES_PACKAGE_RECOMPILE": "Package lacks required model-selection inputs.",
        "MODEL_REQUIRES_MEMORY_SCOPE_REVIEW": "Memory/context scope must be reviewed first.",
        "MODEL_REQUIRES_TOOL_GATE_REVIEW": "Requested adapters need registry/gate review first.",
        "MODEL_POLICY_CONFLICT": "Inputs conflict with model policy.",
        "MODEL_UNKNOWN_FAIL_CLOSED": "Unknown or incomplete inputs fail closed.",
    }
    return descriptions[decision_type]


def _selection_state_description(state: str) -> str:
    descriptions = {
        "SELECTION_REQUESTED": "A package requested a model-selection decision.",
        "POLICY_INPUTS_COLLECTED": "Required policy inputs have been collected.",
        "SENSITIVITY_CLASSIFIED": "Sensitivity has been classified.",
        "MEMORY_SCOPE_CHECKED": "Memory scope has been checked.",
        "TOOL_ADAPTERS_CHECKED": "Tool adapter posture has been checked.",
        "ACTOR_ELIGIBILITY_CHECKED": "Actor eligibility has been checked.",
        "MODEL_CLASS_EVALUATED": "Requested model class has been evaluated.",
        "GATES_IDENTIFIED": "Operator/Guardian/tool/memory gates have been identified.",
        "RECEIPT_READY": "Receipt has enough fields for review.",
        "SELECTION_ALLOWED_PREVIEW_ONLY": "Selection may be shown as preview only; no dispatch.",
        "SELECTION_BLOCKED": "Selection is blocked.",
        "SELECTION_DEFERRED": "Selection is deferred until future gates/proof exist.",
        "SELECTION_ESCALATED": "Selection is escalated to operator or Guardian.",
        "SELECTION_REVOKED": "Selection receipt has been revoked.",
        "SELECTION_QUARANTINED": "Selection receipt is quarantined.",
        "UNKNOWN_FAIL_CLOSED": "Selection cannot be trusted and fails closed.",
    }
    return descriptions[state]


def format_model_selection_receipt_contract(payload: dict[str, Any]) -> str:
    lines = [
        "# Model Selection Receipt Contract v0",
        "",
        "## Operator Summary",
        payload["operator_summary"],
        "",
        "## Decision Types",
    ]
    for item in payload["decision_types"]:
        lines.append(f"- `{item['decision_type']}`: {item['description']}")
    lines.extend(["", "## Selection States"])
    for item in payload["selection_states"]:
        lines.append(f"- `{item['selection_state']}`: {item['description']}")
    lines.extend(["", "## Model Classes"])
    for item in payload["model_classes"]:
        lines.append(
            f"- `{item['model_class_id']}`: `{item['current_authority_posture']}`; "
            f"ceiling `{item['sensitivity_ceiling']}`."
        )
    lines.extend(["", "## Receipt Fields"])
    for field in payload["selection_receipt_schema"]["required_fields"]:
        lines.append(f"- `{field}`")
    lines.extend(["", "## Actor Model Posture"])
    for rule in payload["actor_model_selection_rules"]:
        lines.append(
            f"- `{rule['actor_id']}` as {rule['agent_character']}: current live model `{rule['current_live_model_class']}`; "
            f"future eligible {', '.join(rule['future_eligible_model_classes'])}."
        )
    lines.extend(["", "## Package Binding"])
    for item in payload["package_binding_rule"]["package_may_receive_model_selection_receipt_only_if"]:
        lines.append(f"- {item}")
    lines.extend(["", "## Mission Control Guidance"])
    lines.append("- Show requested/selected-or-blocked model class, actor, sensitivity, gates, blocked reasons, and what would make selection valid.")
    lines.append("- Hide model launch controls, provider credential prompts, browser/OAuth prompts, hidden routing, and agent-self-selected claims.")
    lines.extend(["", "## Stable Map Integration"])
    stable = payload["stable_map_integration"]
    lines.append(f"- Summary included in stable map now: `{str(stable['summary_included_in_stable_map_bundle_now']).lower()}`")
    lines.append(f"- Next requirement: {stable['next_map_bundle_refresh_requirement']}")
    lines.extend(["", "## Authority Boundary"])
    for key, value in NO_AUTHORITY_FLAGS.items():
        lines.append(f"- `{key}`: `{str(value).lower()}`")
    lines.extend(["", "## Next Lanes"])
    for lane in payload["recommended_next_lanes"]:
        lines.append(f"- `{lane['lane_id']}` ({lane['priority']}): {lane['title']}")
    return "\n".join(lines).rstrip() + "\n"


def export_model_selection_receipt_contract(
    *,
    repo_root: str | Path = ROOT,
    export_root: str | Path = DEFAULT_EXPORT_ROOT,
    generated_at: str | None = None,
) -> ModelSelectionReceiptExportResult:
    payload = build_model_selection_receipt_contract(repo_root=repo_root, generated_at=generated_at)
    root = Path(export_root)
    if not root.is_absolute():
        root = Path(repo_root) / root
    root.mkdir(parents=True, exist_ok=True)
    json_path = root / JSON_EXPORT_NAME
    operator_path = root / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(format_model_selection_receipt_contract(payload), encoding="utf-8")
    return ModelSelectionReceiptExportResult(
        schema_version=payload["schema_version"],
        json_path=json_path.as_posix(),
        operator_path=operator_path.as_posix(),
        decision_type_count=len(payload["decision_types"]),
        model_class_count=len(payload["model_classes"]),
        example_count=len(payload["example_model_selection_receipts"]),
        model_call_authority_added=bool(payload["model_call_authority"]),
        model_router_runtime_authority_added=bool(payload["model_router_runtime_authority"]),
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export Model Selection Receipt Contract read-model.")
    parser.add_argument("--repo-root", default=ROOT.as_posix())
    parser.add_argument("--export-root", default=DEFAULT_EXPORT_ROOT.as_posix())
    parser.add_argument("--format", choices=("summary", "json", "operator"), default="summary")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    result = export_model_selection_receipt_contract(repo_root=args.repo_root, export_root=args.export_root)
    if args.format == "json":
        print(stable_json(build_model_selection_receipt_contract(repo_root=args.repo_root)), end="")
    elif args.format == "operator":
        payload = build_model_selection_receipt_contract(repo_root=args.repo_root)
        print(format_model_selection_receipt_contract(payload), end="")
    else:
        print(
            stable_json(
                {
                    "schema_version": result.schema_version,
                    "json_path": result.json_path,
                    "operator_path": result.operator_path,
                    "decision_type_count": result.decision_type_count,
                    "model_class_count": result.model_class_count,
                    "example_count": result.example_count,
                    "model_call_authority_added": result.model_call_authority_added,
                    "model_router_runtime_authority_added": result.model_router_runtime_authority_added,
                }
            ),
            end="",
        )
    return 0


__all__ = [
    "DECISION_TYPES",
    "FAIL_CLOSED_REASONS",
    "JSON_EXPORT_NAME",
    "KNOWN_ACTOR_IDS",
    "MODEL_CLASSES",
    "NO_AUTHORITY_FLAGS",
    "OPERATOR_EXPORT_NAME",
    "POLICY_INPUTS_REQUIRED",
    "RECEIPT_FIELDS",
    "SCHEMA_VERSION",
    "SELECTION_STATES",
    "SENSITIVITY_CLASSES",
    "build_model_selection_receipt_contract",
    "export_model_selection_receipt_contract",
    "format_model_selection_receipt_contract",
    "main",
    "stable_json",
]


if __name__ == "__main__":
    raise SystemExit(main())
