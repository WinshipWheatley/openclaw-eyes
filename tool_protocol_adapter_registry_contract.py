"""Tool Protocol Adapter Registry Contract v0 for OpenClaw.

This read-model defines tool/protocol adapter capability metadata before any
runtime wiring exists. It is deterministic contract data only. It does not
activate tools, models, agents, browser/OAuth/account access, Gmail, calendar,
Coupa, Telegram, planner/builder loops, queue/autonomy, credentials, runtime
daemons, network calls, broad file indexing, raw private body ingestion, or PC
system-drive writes.
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

SCHEMA_VERSION = "tool_protocol_adapter_registry_contract_v0"
JSON_EXPORT_NAME = "tool_protocol_adapter_registry_contract.json"
OPERATOR_EXPORT_NAME = "tool_protocol_adapter_registry_contract_OPERATOR.md"

NO_AUTHORITY_FLAGS = {
    "runtime_authority": False,
    "tool_execution_authority": False,
    "external_tool_authority": False,
    "model_call_authority": False,
    "agent_call_authority": False,
    "browser_oauth_account_access_enabled": False,
    "gmail_calendar_coupa_telegram_enabled": False,
    "credential_authority": False,
    "send_submit_approval_enabled": False,
    "network_execution_enabled": False,
    "runtime_daemon_enabled": False,
    "planner_builder_execution_enabled": False,
    "queue_autonomy_execution_enabled": False,
    "raw_private_body_ingestion_enabled": False,
    "vector_memory_expansion_enabled": False,
    "external_retained_memory_enabled": False,
    "broad_filesystem_indexing_enabled": False,
    "repo_b_mutation_enabled": False,
    "mission_control_app_authority_added": False,
    "mac_sync_or_import_triggered": False,
    "pc_c_drive_artifact_write_allowed": False,
    "adapter_self_authority_allowed": False,
    "actor_self_tool_grant_allowed": False,
    "operator_final_authority": True,
}

ADAPTER_CATEGORIES = (
    "read_model_stable_map",
    "local_code_workspace",
    "package_compiler",
    "domain_workflow",
    "external_account_browser_api",
    "runtime_agent",
    "safety_security",
)

ADAPTER_STATES = (
    "ACTIVE_READ_ONLY",
    "ACTIVE_PREVIEW_ONLY",
    "RECEIPT_ONLY",
    "CANDIDATE_UNMAPPED",
    "FUTURE_GATED",
    "BLOCKED_SENSITIVE",
    "BLOCKED_NO_AUTHORITY",
    "BLOCKED_NO_RECEIPT",
    "BLOCKED_NO_GUARDIAN_GATE",
    "BLOCKED_NO_OPERATOR_APPROVAL",
    "QUARANTINED",
    "RETIRED",
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

MODEL_CLASSES = (
    "human_operator",
    "blocked_no_model",
    "local_small_fast",
    "local_reasoning",
    "local_sensitive",
    "external_fast_worker",
    "external_deep_reasoner",
    "external_code_worker",
    "external_multimodal",
)

PACKAGE_TYPES = (
    "check_light_diagnostic_package",
    "helm_lane_awareness_package",
    "world_lane_work_package",
    "design_memory_discovery_package",
    "bridge_sync_diagnostic_package",
    "workbench_actor_review_package",
    "code_implementation_package",
    "verification_review_package",
    "tell_system_whats_missing_package",
    "confidence_detour_package",
    "finance_ap_review",
    "protected_access_review",
    "music_creative_review",
    "communications_review",
    "architecture_review",
    "mission_control_ux",
    "client_system_build",
    "browser_or_portal_related",
    "credential_or_oauth_related",
)

PACKAGE_TOOL_BLOCK_STATUSES = (
    "TOOL_NOT_MAPPED",
    "TOOL_BLOCKED_BY_MEMORY_SCOPE",
    "TOOL_BLOCKED_BY_SENSITIVITY",
    "TOOL_BLOCKED_BY_GUARDIAN_GATE",
    "TOOL_BLOCKED_BY_OPERATOR_APPROVAL",
    "TOOL_BLOCKED_BY_RECEIPT_REQUIREMENT",
    "TOOL_UNKNOWN_FAIL_CLOSED",
)


@dataclass(frozen=True)
class EvidenceSource:
    source_id: str
    path: str
    role: str


@dataclass(frozen=True)
class AdapterStateDefinition:
    state_id: str
    meaning: str
    promotion_rule: str
    demotion_rule: str
    current_execution_allowed: bool


@dataclass(frozen=True)
class CapabilityClassPolicy:
    capability_class: str
    current_authority_status: str
    future_gate_requirement: str
    receipt_requirement: str
    guardian_requirement: bool
    operator_approval_requirement: bool
    blocked_conditions: tuple[str, ...]


@dataclass(frozen=True)
class AdapterRecord:
    adapter_id: str
    display_name: str
    category: str
    adapter_state: str
    capability_classes: tuple[str, ...]
    current_allowed_actions: tuple[str, ...]
    current_blocked_actions: tuple[str, ...]
    future_eligible_actions: tuple[str, ...]
    actor_eligibility: tuple[str, ...]
    model_class_eligibility: tuple[str, ...]
    package_types_allowed: tuple[str, ...]
    package_types_blocked: tuple[str, ...]
    memory_scope_requirements: tuple[str, ...]
    sensitivity_ceiling: str
    required_gates: tuple[str, ...]
    required_operator_approval: bool
    required_guardian_review: bool
    required_receipts: tuple[str, ...]
    stop_conditions: tuple[str, ...]
    proof_inputs: tuple[str, ...]
    output_receipt_shape: tuple[str, ...]
    failure_modes: tuple[str, ...]
    quarantine_conditions: tuple[str, ...]
    revocation_conditions: tuple[str, ...]
    mission_control_display_guidance: str
    what_makes_adapter_available: str
    what_keeps_adapter_blocked: str


@dataclass(frozen=True)
class ActorAdapterRule:
    actor_id: str
    current_adapter_eligibility: tuple[str, ...]
    blocked_adapter_classes: tuple[str, ...]
    future_eligible_adapter_classes: tuple[str, ...]
    required_boundary: str
    notes_for_mission_control: str


@dataclass(frozen=True)
class RecommendedLane:
    lane_id: str
    title: str
    priority: str
    why_next: str
    hard_boundary: str


@dataclass(frozen=True)
class ToolProtocolAdapterRegistryExportResult:
    schema_version: str
    json_path: str
    operator_path: str
    adapter_count: int
    active_read_only_count: int
    blocked_or_future_gated_count: int
    runtime_authority_added: bool
    tool_execution_authority_added: bool


EVIDENCE_SOURCES = (
    EvidenceSource(
        "agent_platform_alignment",
        "generated/read_models/agent_platform_alignment.json",
        "platform primitive map and missing tool-protocol primitive",
    ),
    EvidenceSource(
        "agent_identity_actor_router_contract",
        "generated/read_models/agent_identity_actor_router_contract.json",
        "actor identities and routing boundaries",
    ),
    EvidenceSource(
        "model_selection_policy_contract",
        "generated/read_models/model_selection_policy_contract.json",
        "model-class and sensitivity policy",
    ),
    EvidenceSource(
        "agent_package_preview_contract",
        "generated/read_models/agent_package_preview_contract.json",
        "package preview fields, inactive tool protocol policy, and gates",
    ),
    EvidenceSource(
        "agent_memory_scope_contract",
        "generated/read_models/agent_memory_scope_contract.json",
        "memory/context inclusion and exclusion boundaries",
    ),
    EvidenceSource(
        "package_compiler_contract",
        "generated/read_models/package_compiler_contract.json",
        "package boundary validation and receipt requirements",
    ),
    EvidenceSource(
        "capability_skill_registry_metadata_delta",
        "generated/read_models/capability_skill_registry_metadata_delta.json",
        "existing capability/skill metadata map",
    ),
    EvidenceSource(
        "guardian_protected_access_gate_spec",
        "generated/read_models/guardian_protected_access_gate_spec.json",
        "Guardian gate and protected-access posture",
    ),
    EvidenceSource(
        "protected_evidence_reference_receipt",
        "generated/read_models/protected_evidence_reference_receipt.json",
        "metadata-only protected evidence reference receipt shape",
    ),
    EvidenceSource(
        "stable_map_bundle_contract",
        "generated/read_models/operator_map_bundle_contract.json",
        "stable map bundle transport contract when present",
    ),
)

ADAPTER_STATE_DEFINITIONS = (
    AdapterStateDefinition(
        "ACTIVE_READ_ONLY",
        "Adapter may inspect deterministic metadata/proof refs in bounded scope.",
        "Requires explicit contract, safe input shape, no private raw bodies, and deterministic receipt/proof posture.",
        "Demote if it requests write, account, network, credential, or raw private access.",
        False,
    ),
    AdapterStateDefinition(
        "ACTIVE_PREVIEW_ONLY",
        "Adapter may produce preview metadata or draft-only package content.",
        "Requires package preview contract, bounded context refs, and no dispatch path.",
        "Demote if preview output becomes executable, sent, submitted, or mutating.",
        False,
    ),
    AdapterStateDefinition(
        "RECEIPT_ONLY",
        "Adapter may define or validate metadata receipts without executing the underlying action.",
        "Requires deterministic receipt schema and proof/hash inputs.",
        "Demote if receipt claims unproven execution or hides missing proof.",
        False,
    ),
    AdapterStateDefinition(
        "CANDIDATE_UNMAPPED",
        "Adapter is named as possible future terrain but lacks sufficient mapping.",
        "Promote only after discovery/classification, gates, proof, and receipt contract exist.",
        "Demote to unknown fail-closed if ambiguity creates operator risk.",
        False,
    ),
    AdapterStateDefinition(
        "FUTURE_GATED",
        "Adapter may be useful later but needs security, operator, Guardian, and receipt gates.",
        "Promote only after explicit future lane grants narrow authority.",
        "Demote if requested as active before gates exist.",
        False,
    ),
    AdapterStateDefinition(
        "BLOCKED_SENSITIVE",
        "Adapter touches sensitive/protected/account material and is blocked now.",
        "Promote only with security audit, sensitivity handling, Guardian gate, and operator approval.",
        "Demote or quarantine on raw private, credential, or account/session exposure.",
        False,
    ),
    AdapterStateDefinition(
        "BLOCKED_NO_AUTHORITY",
        "No current authority exists for this adapter class.",
        "Promote only through a future explicit authority-granting contract and receipt system.",
        "Quarantine if any actor tries to use it anyway.",
        False,
    ),
    AdapterStateDefinition(
        "BLOCKED_NO_RECEIPT",
        "Adapter lacks required receipt shape.",
        "Promote only after deterministic receipt requirements exist.",
        "Stay blocked while result proof is natural-language-only.",
        False,
    ),
    AdapterStateDefinition(
        "BLOCKED_NO_GUARDIAN_GATE",
        "Adapter needs Guardian protected-access review before future use.",
        "Promote only with Guardian gate and protected reference receipt.",
        "Stay blocked when protected/sensitive input has no gate.",
        False,
    ),
    AdapterStateDefinition(
        "BLOCKED_NO_OPERATOR_APPROVAL",
        "Adapter needs explicit operator approval before future use.",
        "Promote only with operator approval receipt.",
        "Stay blocked when approval is absent or ambiguous.",
        False,
    ),
    AdapterStateDefinition(
        "QUARANTINED",
        "Adapter is isolated due to contradiction, leakage, authority drift, or malformed proof.",
        "Promote only after root-cause review, corrected receipts, and operator/Guardian clearance.",
        "Remain quarantined while suspicion remains unresolved.",
        False,
    ),
    AdapterStateDefinition(
        "RETIRED",
        "Adapter is intentionally inactive and should not be offered.",
        "Promote only with a new contract replacing the retired path.",
        "Remain hidden unless historical proof/detail is requested.",
        False,
    ),
    AdapterStateDefinition(
        "UNKNOWN_FAIL_CLOSED",
        "Adapter status cannot be trusted.",
        "Promote only after classification proves state, gates, and receipts.",
        "Default state for missing or ambiguous adapters.",
        False,
    ),
)


def _capability_policy() -> tuple[CapabilityClassPolicy, ...]:
    blocked_sensitive = (
        "unknown sensitivity",
        "missing Guardian gate",
        "missing operator approval",
        "missing receipt",
    )
    return (
        CapabilityClassPolicy(
            "READ_METADATA",
            "allowed_for_deterministic_refs_only",
            "none for repo-safe metadata; protected metadata still needs source gate",
            "metadata/proof reference receipt when used in future package execution",
            False,
            False,
            ("raw private body requested", "credential/session material requested"),
        ),
        CapabilityClassPolicy(
            "READ_REDACTED_CONTENT",
            "future_gated_metadata_only_now",
            "Guardian redaction gate and operator-visible context packet",
            "redaction receipt and source reference receipt",
            True,
            True,
            blocked_sensitive,
        ),
        CapabilityClassPolicy(
            "READ_RAW_CONTENT",
            "blocked_now",
            "security audit, Guardian gate, operator approval, no-go data review",
            "protected access receipt with raw-content justification",
            True,
            True,
            ("raw private body", "client/legal/finance material", "credentials/tokens", "unknown source"),
        ),
        CapabilityClassPolicy(
            "WRITE_DRAFT",
            "preview_only_now",
            "package preview and receipt logging",
            "draft preview receipt",
            False,
            True,
            ("send/submit implied", "account mutation implied", "missing operator preview"),
        ),
        CapabilityClassPolicy(
            "WRITE_LOCAL_FILE",
            "bounded_worker_task_only_not_runtime_adapter",
            "package boundary, allowed workspace roots, validation, receipts",
            "file-change receipt and diff/test receipt",
            False,
            True,
            ("outside allowed roots", "PC C-drive artifact write", "private raw content write"),
        ),
        CapabilityClassPolicy(
            "RUN_TEST",
            "bounded_worker_task_only_not_runtime_adapter",
            "explicit package or operator-scoped validation lane",
            "test command and result receipt",
            False,
            False,
            ("unbounded script", "network test", "credential-dependent test", "destructive test"),
        ),
        CapabilityClassPolicy(
            "RUN_BUILD",
            "bounded_worker_task_only_not_runtime_adapter",
            "explicit package or operator-scoped validation lane",
            "build command and result receipt",
            False,
            False,
            ("credential-dependent build", "network build without gate", "outside workspace"),
        ),
        CapabilityClassPolicy(
            "RUN_SCRIPT",
            "blocked_as_runtime_adapter",
            "future security review plus explicit script allowlist",
            "script command, inputs, outputs, and exit-code receipt",
            True,
            True,
            ("arbitrary shell execution", "repair/remount/delete", "network or credential path"),
        ),
        CapabilityClassPolicy(
            "SEND_MESSAGE",
            "blocked_now",
            "operator approval, Guardian gate where sensitive, account adapter security",
            "send receipt with recipient/content refs and approval id",
            True,
            True,
            ("email/Telegram send", "hidden send", "missing approval"),
        ),
        CapabilityClassPolicy(
            "SUBMIT_FORM",
            "blocked_now",
            "security audit, protected-access gate, operator approval",
            "submit receipt with form refs and approval id",
            True,
            True,
            ("Coupa/browser/account form", "credential/session needed", "approval missing"),
        ),
        CapabilityClassPolicy(
            "APPROVE_ACTION",
            "blocked_now",
            "operator final authority plus Guardian gate",
            "approval receipt",
            True,
            True,
            ("approval self-assigned", "financial/legal/client action", "operator absent"),
        ),
        CapabilityClassPolicy(
            "MUTATE_ACCOUNT",
            "blocked_now",
            "security audit, account adapter contract, operator approval",
            "account mutation receipt",
            True,
            True,
            ("OAuth/session/credential needed", "external account", "operator absent"),
        ),
        CapabilityClassPolicy(
            "BROWSER_SESSION",
            "blocked_now",
            "future browser/OAuth security lane",
            "browser session receipt",
            True,
            True,
            ("browser session requested", "cookies/session data", "portal access"),
        ),
        CapabilityClassPolicy(
            "NETWORK_API",
            "blocked_now",
            "future network/API adapter security lane",
            "network call receipt",
            True,
            True,
            ("external API call", "credential/token needed", "unknown endpoint"),
        ),
        CapabilityClassPolicy(
            "MODEL_CALL",
            "blocked_now",
            "model selection receipt, package preview, operator gate",
            "model selection and model-call receipt",
            True,
            True,
            ("model self-selection", "external sensitive data", "missing package preview"),
        ),
        CapabilityClassPolicy(
            "AGENT_LAUNCH",
            "blocked_now",
            "agent identity, package preview, model policy, security audit",
            "agent launch receipt",
            True,
            True,
            ("agent self-launch", "runtime daemon", "package missing"),
        ),
        CapabilityClassPolicy(
            "QUEUE_EXECUTION",
            "post_security_future_gated",
            "post-threshold security audit and queue lifecycle receipts",
            "queue lifecycle receipt",
            True,
            True,
            ("planner/builder loop", "autonomy queue", "hidden background run"),
        ),
        CapabilityClassPolicy(
            "RECEIPT_WRITE",
            "metadata_only_allowed_when_schema_exists",
            "deterministic receipt schema and no execution claim",
            "receipt hash and schema validation",
            False,
            False,
            ("receipt claims unrun execution", "missing hash", "malformed receipt"),
        ),
        CapabilityClassPolicy(
            "MEMORY_CANDIDATE_WRITE",
            "metadata_only_future_candidate",
            "memory candidate receipt and operator promotion path",
            "memory candidate receipt",
            True,
            True,
            ("hidden memory", "canonical write", "raw private body"),
        ),
        CapabilityClassPolicy(
            "CANONICAL_MEMORY_PROMOTION",
            "blocked_now",
            "operator promotion receipt; Guardian review for protected/sensitive",
            "operator promotion receipt and source proof",
            True,
            True,
            ("model/actor direct promotion", "unverified claim", "operator absent"),
        ),
    )


def _adapter_specs() -> tuple[AdapterRecord, ...]:
    metadata_receipt_shape = (
        "receipt_id",
        "adapter_id",
        "package_id",
        "actor",
        "input_refs",
        "output_refs",
        "success_or_failure_state",
        "receipt_hash",
    )
    execution_receipt_shape = (
        "receipt_id",
        "adapter_id",
        "package_id",
        "actor",
        "model_class",
        "capability_class_used",
        "input_refs",
        "output_refs",
        "redaction_status",
        "sensitivity",
        "gates_checked",
        "operator_approval_id_if_required",
        "guardian_gate_id_if_required",
        "started_at",
        "completed_at",
        "success_or_failure_state",
        "stop_condition_triggered",
        "files_changed_if_any",
        "commands_run_if_any",
        "network_used",
        "account_accessed",
        "send_submit_approve_performed",
        "receipt_hash",
        "revocation_or_quarantine_status",
    )
    return (
        AdapterRecord(
            "generated_read_model_reader",
            "Generated Read-Model Reader",
            "read_model_stable_map",
            "ACTIVE_READ_ONLY",
            ("READ_METADATA",),
            ("read safe generated read-model metadata", "inspect schema/proof refs"),
            ("write read-models", "execute scripts", "read no-go generated files"),
            ("read protected metadata refs after gate",),
            KNOWN_ACTOR_IDS,
            ("human_operator", "blocked_no_model", "local_small_fast", "local_reasoning"),
            ("helm_lane_awareness_package", "check_light_diagnostic_package", "verification_review_package"),
            ("finance_ap_review", "protected_access_review"),
            ("deterministic read-model refs only", "no raw private bodies"),
            "internal_operator_safe",
            ("source_context_gates",),
            False,
            False,
            ("read-model proof reference receipt for future execution",),
            ("missing file", "schema parse failure", "no-go filename detected"),
            ("generated/read_models/*.json", "generated/read_models/*_OPERATOR.md"),
            metadata_receipt_shape,
            ("missing schema", "hash mismatch", "unsafe filename excluded"),
            ("read forbidden filename", "claims execution authority", "imports raw private body"),
            ("no-go match", "malformed read-model", "source conflict"),
            "Show as proof/detail reader, not as a live tool.",
            "Safe top-level generated file, parseable schema, no no-go path.",
            "No-go path, malformed file, private/raw body request, or missing proof.",
        ),
        AdapterRecord(
            "stable_map_bundle_reader",
            "Stable Map Bundle Reader",
            "read_model_stable_map",
            "ACTIVE_READ_ONLY",
            ("READ_METADATA",),
            ("read stable map snapshot/manifest/operator digest", "surface app-visible map status"),
            ("mutate Mac mirror", "trigger sync", "write map receipt"),
            ("validate app-visible map receipt after future import",),
            KNOWN_ACTOR_IDS,
            ("human_operator", "blocked_no_model", "local_small_fast", "local_reasoning"),
            ("helm_lane_awareness_package", "bridge_sync_diagnostic_package", "check_light_diagnostic_package"),
            ("world_lane_work_package", "finance_ap_review"),
            ("stable map snapshot refs", "stable map manifest hash", "no raw terrain bodies"),
            "internal_operator_safe",
            ("map_bundle_contract",),
            False,
            False,
            ("map manifest hash receipt", "Mac import receipt for future transport proof"),
            ("bundle missing", "manifest hash mismatch", "Mac receipt missing when current proof required"),
            ("openclaw_map_snapshot.json", "openclaw_map_manifest.json", "openclaw_map_OPERATOR.md"),
            metadata_receipt_shape,
            ("bundle hash mismatch", "snapshot parse failure", "receipt stale"),
            ("claims Mac import without receipt", "sync trigger attempted", "private raw body in snapshot"),
            ("stale generation", "malformed manifest", "unproven app-visible state"),
            "Show the stable map as Mission Control's primary app-facing contract.",
            "Snapshot, manifest, and operator digest parse and match expected bundle hash.",
            "Missing bundle, mismatched hash, missing receipt when current proof is required.",
        ),
        AdapterRecord(
            "receipt_reader",
            "Receipt Reader",
            "read_model_stable_map",
            "ACTIVE_READ_ONLY",
            ("READ_METADATA",),
            ("read deterministic receipt metadata", "compare receipt hash/schema"),
            ("create execution receipts", "claim unobserved execution"),
            ("read future adapter execution receipts after gates exist",),
            ("operator_winship", "chief", "guardian", "codex"),
            ("human_operator", "blocked_no_model", "local_reasoning"),
            ("verification_review_package", "check_light_diagnostic_package", "bridge_sync_diagnostic_package"),
            ("finance_ap_review",),
            ("receipt IDs and hashes only",),
            "internal_operator_safe",
            ("receipt_schema",),
            False,
            False,
            ("receipt parse receipt",),
            ("receipt missing", "receipt malformed", "hash mismatch"),
            ("receipt JSON", "receipt hash", "source refs"),
            metadata_receipt_shape,
            ("malformed receipt", "missing hash", "stale receipt"),
            ("receipt claims forbidden action", "receipt lacks gates", "receipt contradicts proof"),
            ("malformed receipt", "impossible action claim", "missing approval id"),
            "Show receipts under proof/detail and link them to package previews.",
            "Receipt schema exists, hash validates, and referenced proof exists.",
            "Missing, malformed, stale, or authority-expanding receipt.",
        ),
        AdapterRecord(
            "proof_reference_reader",
            "Proof Reference Reader",
            "read_model_stable_map",
            "ACTIVE_READ_ONLY",
            ("READ_METADATA",),
            ("read proof/source refs", "distinguish proof from operator memory"),
            ("read private source bodies", "bypass protected reference policy"),
            ("read protected reference metadata after Guardian gate",),
            ("operator_winship", "chief", "guardian", "hermes", "codex"),
            ("human_operator", "blocked_no_model", "local_reasoning", "local_sensitive"),
            ("verification_review_package", "protected_access_review", "helm_lane_awareness_package"),
            ("world_lane_work_package",),
            ("metadata-only source refs", "protected refs require gate"),
            "protected_reference_only",
            ("source_context_gates", "guardian_protected_access_gate_when_sensitive"),
            False,
            True,
            ("proof reference receipt",),
            ("missing proof ref", "protected ref without gate", "operator memory presented as proof"),
            ("source card refs", "receipt refs", "hash refs"),
            metadata_receipt_shape,
            ("proof ref missing", "operator memory conflated with proof", "private body requested"),
            ("protected material exposed", "gate bypass attempt", "source contradiction"),
            ("proof conflict", "sensitivity ceiling exceeded", "missing gate"),
            "Show proof refs below operator orientation; never render raw protected bodies by default.",
            "Proof ref is metadata-only and allowed by memory scope.",
            "Raw body, missing source, protected ref without gate, or source/proof conflict.",
        ),
        AdapterRecord(
            "scoped_repo_file_reader",
            "Scoped Repo File Reader",
            "local_code_workspace",
            "ACTIVE_READ_ONLY",
            ("READ_METADATA",),
            ("read scoped repo files in explicit worker lanes", "inspect diffs/status"),
            ("broad filesystem indexing", "read credentials", "read PC C-drive artifacts"),
            ("read protected repo refs after explicit package gate",),
            ("operator_winship", "codex", "chief", "guardian", "hermes"),
            ("human_operator", "blocked_no_model", "local_reasoning", "external_code_worker"),
            ("code_implementation_package", "verification_review_package", "architecture_review"),
            ("finance_ap_review", "protected_access_review"),
            ("allowed workspace roots", "no secrets/no-go paths", "package scope"),
            "internal_operator_safe",
            ("package_compiler_contract", "memory_scope_contract"),
            False,
            False,
            ("file-read proof receipt for future runtime use",),
            ("path outside allowed roots", "credential/no-go path", "scope drift"),
            ("git status", "git diff", "allowed file refs"),
            metadata_receipt_shape,
            ("path scope failure", "no-go path", "private body request"),
            ("credential path access", "broad filesystem scan", "scope expansion"),
            ("unexpected no-go match", "operator stops lane", "path ambiguity"),
            "Show as scoped code context only inside implementation package details.",
            "Package defines allowed roots and file refs are inside them.",
            "Missing package scope, no-go path, broad scan, or C-drive artifact request.",
        ),
        AdapterRecord(
            "scoped_code_patch_proposal",
            "Scoped Code Patch Proposal",
            "local_code_workspace",
            "ACTIVE_PREVIEW_ONLY",
            ("WRITE_DRAFT", "WRITE_LOCAL_FILE"),
            ("prepare bounded patch proposal in an explicit worker lane", "show diff/proof before commit"),
            ("runtime patching", "hidden broad writes", "writes outside package scope"),
            ("future package-bound implementation with file-change receipt",),
            ("codex", "operator_winship"),
            ("human_operator", "blocked_no_model", "external_code_worker", "local_reasoning"),
            ("code_implementation_package",),
            ("finance_ap_review", "protected_access_review"),
            ("allowed workspace roots", "package validation requirements", "no secret/private writes"),
            "internal_operator_safe",
            ("package_compiler_contract", "operator_approval_for_commit_when_needed"),
            True,
            False,
            ("file-change receipt", "test/diff receipt"),
            ("path outside scope", "test failure", "unexpected authority-expanding file"),
            ("scoped source refs", "test refs", "diff refs"),
            execution_receipt_shape,
            ("test failure", "diff check failure", "authority boundary violation"),
            ("writes C-drive artifacts", "touches secrets", "adds runtime authority"),
            ("operator stops lane", "unsafe diff", "validation failure"),
            "Show as implementation preview/worker package, not a live app button.",
            "Explicit package scope, allowed roots, validation, and receipts exist.",
            "Scope ambiguity, secret/no-go writes, missing tests, or authority expansion.",
        ),
        AdapterRecord(
            "focused_test_runner",
            "Focused Test Runner",
            "local_code_workspace",
            "ACTIVE_PREVIEW_ONLY",
            ("RUN_TEST",),
            ("run focused tests in bounded worker tasks", "record command/result proof"),
            ("unbounded test suites requiring credentials/network", "repair scripts"),
            ("future package-bound test execution receipt",),
            ("codex", "operator_winship"),
            ("human_operator", "blocked_no_model", "external_code_worker", "local_reasoning"),
            ("code_implementation_package", "verification_review_package"),
            ("browser_or_portal_related", "finance_ap_review"),
            ("explicit test command", "no network/credential dependency", "workspace-local output"),
            "internal_operator_safe",
            ("package_compiler_contract",),
            False,
            False,
            ("test result receipt",),
            ("test command broad/ambiguous", "credential prompt", "network dependency"),
            ("pytest command", "exit code", "stdout summary"),
            execution_receipt_shape,
            ("nonzero exit", "interactive prompt", "credential/network attempt"),
            ("arbitrary shell expansion", "destructive command", "hidden background process"),
            ("interactive prompt", "operator stops lane", "unexpected external dependency"),
            "Show command/result proof in package validation detail.",
            "Command is explicit, local, focused, and non-destructive.",
            "Broad script, network/credential path, destructive behavior, or missing receipt.",
        ),
        AdapterRecord(
            "bounded_build_verifier",
            "Bounded Build Verifier",
            "local_code_workspace",
            "ACTIVE_PREVIEW_ONLY",
            ("RUN_BUILD",),
            ("run bounded build validation when explicitly scoped", "record result proof"),
            ("launch external services", "credentialed builds", "runtime daemon activation"),
            ("future package-bound build execution receipt",),
            ("codex", "operator_winship"),
            ("human_operator", "blocked_no_model", "external_code_worker", "local_reasoning"),
            ("code_implementation_package", "verification_review_package", "mission_control_ux"),
            ("finance_ap_review", "protected_access_review"),
            ("explicit build command", "no credential/network dependency unless future-gated"),
            "internal_operator_safe",
            ("package_compiler_contract",),
            False,
            False,
            ("build result receipt",),
            ("build command broad/ambiguous", "credential prompt", "runtime activation"),
            ("build command", "exit code", "artifact refs"),
            execution_receipt_shape,
            ("nonzero exit", "launch required", "external dependency"),
            ("daemon activation", "credential request", "network install"),
            ("interactive prompt", "operator stops lane", "unexpected external dependency"),
            "Show build proof under validation; do not imply always-on runtime.",
            "Command is explicit, local, bounded, and non-destructive.",
            "Runtime launch, credentials, broad repair, or missing receipt.",
        ),
        AdapterRecord(
            "package_compiler",
            "Package Compiler",
            "package_compiler",
            "ACTIVE_PREVIEW_ONLY",
            ("READ_METADATA", "WRITE_DRAFT"),
            ("compile deterministic package previews", "enforce package boundary fields"),
            ("dispatch package", "call model", "activate agent/tool"),
            ("future copy/export package after approval",),
            ("operator_winship", "chief", "guardian", "codex", "hermes"),
            ("human_operator", "blocked_no_model", "local_reasoning"),
            PACKAGE_TYPES,
            (),
            ("package compiler contract", "actor/model/memory/tool registry refs"),
            "internal_operator_safe",
            ("package_compiler_contract", "agent_package_preview_contract"),
            False,
            False,
            ("package preview receipt when implemented",),
            ("required field missing", "authority drift", "unknown actor/model/tool"),
            ("package contract refs", "actor/router refs", "model policy refs"),
            metadata_receipt_shape,
            ("compile-time blocker", "schema failure", "forbidden authority request"),
            ("generates live dispatch path", "lets model self-authorize", "adds tool execution"),
            ("missing required registry", "unknown sensitivity", "forbidden action"),
            "Show complete package preview, not an execute path.",
            "Required fields, gates, proof refs, and blocked authority are explicit.",
            "Missing registry, unknown sensitivity, active authority, or missing receipt requirements.",
        ),
        AdapterRecord(
            "package_preview_exporter",
            "Package Preview Exporter",
            "package_compiler",
            "ACTIVE_PREVIEW_ONLY",
            ("WRITE_DRAFT", "READ_METADATA"),
            ("export inspectable package metadata", "render operator package preview"),
            ("send package", "open live chat", "trigger workbench"),
            ("future copy/open package after explicit gate",),
            ("operator_winship", "chief", "guardian", "codex", "hermes"),
            ("human_operator", "blocked_no_model", "local_reasoning"),
            PACKAGE_TYPES,
            (),
            ("deterministic refs only", "no raw private bodies"),
            "internal_operator_safe",
            ("agent_package_preview_contract",),
            False,
            False,
            ("package preview receipt when implemented",),
            ("package missing fields", "raw private context included", "dispatch implied"),
            ("package preview payload", "operator digest"),
            metadata_receipt_shape,
            ("schema failure", "private raw body included", "authority mismatch"),
            ("live dispatch added", "credential requested", "model call implied"),
            ("malformed package", "missing gate", "operator stops lane"),
            "Show what would be sent, to whom, and why.",
            "Preview payload is complete, parseable, and non-executing.",
            "Missing gate/receipt, active launch path, or raw/sensitive body inclusion.",
        ),
        AdapterRecord(
            "package_receipt_validator",
            "Package Receipt Validator",
            "package_compiler",
            "RECEIPT_ONLY",
            ("RECEIPT_WRITE", "READ_METADATA"),
            ("validate receipt schemas and hashes", "flag malformed receipts"),
            ("invent execution proof", "mark future action complete"),
            ("future action receipt validation after gates exist",),
            ("operator_winship", "chief", "guardian", "codex"),
            ("human_operator", "blocked_no_model", "local_reasoning"),
            ("verification_review_package", "check_light_diagnostic_package"),
            (),
            ("receipt refs", "schema version", "hash refs"),
            "internal_operator_safe",
            ("receipt_schema",),
            False,
            False,
            ("receipt validation receipt",),
            ("receipt missing", "hash mismatch", "action claim unsupported"),
            ("receipt JSON", "schema refs", "hash refs"),
            metadata_receipt_shape,
            ("malformed receipt", "missing hash", "unsupported action claim"),
            ("claims forbidden send/submit/approve", "network/account action without gate"),
            ("receipt conflict", "operator stops lane", "schema unknown"),
            "Show receipt validity under proof/detail.",
            "Receipt schema/hash match and action claims stay within granted authority.",
            "Missing hash, malformed schema, forbidden action claim, or missing gates.",
        ),
        AdapterRecord(
            "memory_candidate_receipt_generator",
            "Memory Candidate Receipt Generator",
            "package_compiler",
            "RECEIPT_ONLY",
            ("MEMORY_CANDIDATE_WRITE", "RECEIPT_WRITE"),
            ("define metadata-only memory candidate receipt", "record candidate requirements"),
            ("write canonical memory", "retain model memory", "ingest raw chat"),
            ("future memory candidate write after promotion lane exists",),
            ("operator_winship", "chief", "guardian", "cassandra", "hermes", "niles", "codex", "gemini_antigravity"),
            ("human_operator", "blocked_no_model", "local_reasoning"),
            ("tell_system_whats_missing_package", "design_memory_discovery_package", "verification_review_package"),
            (),
            ("source refs", "sensitivity classification", "operator promotion required"),
            "operator_memory_candidate",
            ("agent_memory_scope_contract",),
            True,
            True,
            ("memory candidate receipt",),
            ("raw private body present", "source refs missing", "operator promotion bypassed"),
            ("memory candidate fields", "source refs", "sensitivity refs"),
            metadata_receipt_shape,
            ("candidate missing source", "hidden memory claim", "sensitivity unknown"),
            ("canonical memory written directly", "hidden retention", "raw private body included"),
            ("missing operator promotion", "Guardian missing for sensitive", "candidate expired"),
            "Show candidate memory as non-authoritative until promoted.",
            "Candidate includes source refs, sensitivity, and promotion requirement.",
            "Raw private body, hidden retention, missing source, or direct canonical write.",
        ),
        AdapterRecord(
            "model_selection_receipt_generator",
            "Model Selection Receipt Generator",
            "package_compiler",
            "RECEIPT_ONLY",
            ("RECEIPT_WRITE", "READ_METADATA"),
            ("define model-selection decision receipt", "show blocked_no_model as valid result"),
            ("call model", "mark model available", "select by prompt text"),
            ("future model selection receipt after package preview",),
            ("operator_winship", "chief", "guardian", "codex", "hermes"),
            ("human_operator", "blocked_no_model", "local_reasoning"),
            ("verification_review_package", "code_implementation_package", "architecture_review"),
            (),
            ("model selection policy refs", "package sensitivity refs", "actor refs"),
            "internal_operator_safe",
            ("model_selection_policy_contract",),
            False,
            False,
            ("model selection receipt",),
            ("unknown actor/model", "sensitivity unknown", "external model requested without gate"),
            ("model policy refs", "package refs", "actor refs"),
            metadata_receipt_shape,
            ("model self-selected", "unknown sensitivity", "missing operator preview"),
            ("model call made", "external sensitive data routed", "authority escalated"),
            ("policy conflict", "Guardian gate missing", "operator stops lane"),
            "Show recommended or blocked model posture, not live availability.",
            "Actor, package type, sensitivity, gates, and receipt requirements are explicit.",
            "Unknown sensitivity, external model gate missing, or model call requested.",
        ),
        AdapterRecord(
            "finance_invoice_proof_metadata_adapter",
            "Finance Invoice Proof Metadata Adapter",
            "domain_workflow",
            "FUTURE_GATED",
            ("READ_METADATA", "READ_REDACTED_CONTENT"),
            ("represent invoice proof metadata refs",),
            ("read Coupa", "read raw Excel/PDF bodies", "submit/approve invoice"),
            ("future metadata-only proof adapter after security audit",),
            ("cassandra", "guardian", "operator_winship"),
            ("human_operator", "blocked_no_model", "local_sensitive"),
            ("finance_ap_review", "protected_access_review"),
            ("code_implementation_package", "world_lane_work_package"),
            ("protected evidence refs", "finance/AP sensitivity classification", "Guardian gate"),
            "finance_or_ap_sensitive",
            ("guardian_protected_access_gate", "operator_approval", "protected_evidence_reference_receipt"),
            True,
            True,
            ("finance invoice metadata receipt", "protected evidence reference receipt"),
            ("Coupa/Excel raw access requested", "approval/submit requested", "proof missing"),
            ("Capital Hilton threshold refs", "protected proof refs"),
            metadata_receipt_shape,
            ("proof missing", "raw body requested", "security gate missing"),
            ("Coupa credential requested", "submit/approve attempted", "raw finance body exposed"),
            ("sensitivity ceiling exceeded", "operator approval absent", "Guardian block"),
            "Show invoice proof metadata as future-gated Finance World context.",
            "Security audit, Guardian gate, metadata refs, and operator approval exist.",
            "No security gate, no protected refs, Coupa/Excel raw access, or approval flow requested.",
        ),
        AdapterRecord(
            "cassandra_capital_hilton_invoice_proof_adapter",
            "Cassandra Capital Hilton Invoice Proof Adapter",
            "domain_workflow",
            "FUTURE_GATED",
            ("READ_METADATA", "READ_REDACTED_CONTENT"),
            ("preview Capital Hilton invoice proof requirements",),
            ("access Coupa", "handle credentials", "send/submit/approve"),
            ("future protected metadata review after Guardian/security gates",),
            ("cassandra", "guardian", "operator_winship"),
            ("human_operator", "blocked_no_model", "local_sensitive"),
            ("finance_ap_review",),
            ("world_lane_work_package", "code_implementation_package"),
            ("Capital Hilton threshold map refs", "protected finance proof metadata refs"),
            "finance_or_ap_sensitive",
            ("guardian_protected_access_gate", "operator_approval", "security_audit"),
            True,
            True,
            ("capital_hilton_invoice_proof_metadata_receipt",),
            ("Coupa access requested", "raw proof body included", "submission requested"),
            ("operator_threshold_map_contract", "protected_evidence_reference_receipt"),
            metadata_receipt_shape,
            ("missing protected proof", "operator confirmation missing", "approval boundary ambiguous"),
            ("Coupa session requested", "credential requested", "submit/approve attempted"),
            ("Guardian block", "operator approval absent", "proof mismatch"),
            "Show as not executable; it is Finance World future work after threshold/security.",
            "Protected metadata proof, security audit, Guardian gate, and operator approval exist.",
            "Pre-security, no protected proof refs, or any Coupa/send/submit/credential request.",
        ),
        AdapterRecord(
            "excel_workbook_proof_adapter_candidate",
            "Excel/Workbook Proof Adapter Candidate",
            "domain_workflow",
            "FUTURE_GATED",
            ("READ_METADATA", "READ_REDACTED_CONTENT"),
            ("classify workbook proof metadata needs",),
            ("read raw spreadsheets", "index cells", "mutate workbook"),
            ("future metadata-only workbook proof extraction after security gate",),
            ("cassandra", "guardian", "operator_winship"),
            ("human_operator", "blocked_no_model", "local_sensitive"),
            ("finance_ap_review", "protected_access_review"),
            ("code_implementation_package",),
            ("spreadsheet metadata refs", "protected reference receipt", "no cell body ingestion"),
            "finance_or_ap_sensitive",
            ("guardian_protected_access_gate", "operator_approval", "security_audit"),
            True,
            True,
            ("workbook proof metadata receipt",),
            ("cell body requested", "file path no-go", "proof sensitivity unknown"),
            ("workbook metadata refs", "hash refs"),
            metadata_receipt_shape,
            ("sensitivity unknown", "raw cells requested", "hash missing"),
            ("broad spreadsheet indexing", "bank/remit/check data exposure", "credential path"),
            ("Guardian block", "operator stops lane", "protected ref missing"),
            "Show workbook proof as metadata-only candidate.",
            "Security gate, metadata refs, and redaction receipt exist.",
            "Raw cell/body access, sensitive finance data, or missing gate.",
        ),
        AdapterRecord(
            "communications_email_metadata_adapter_candidate",
            "Communications Email Metadata Adapter Candidate",
            "domain_workflow",
            "FUTURE_GATED",
            ("READ_METADATA", "READ_REDACTED_CONTENT"),
            ("preview email metadata/context refs",),
            ("read raw Gmail bodies", "send email", "mutate labels/account"),
            ("future metadata-only communications review after gates",),
            ("cassandra", "guardian", "operator_winship"),
            ("human_operator", "blocked_no_model", "local_sensitive"),
            ("communications_review", "protected_access_review"),
            ("code_implementation_package",),
            ("email metadata refs", "no raw body by default", "Guardian gate if sensitive"),
            "sensitive_private",
            ("guardian_protected_access_gate", "operator_approval", "security_audit"),
            True,
            True,
            ("communications metadata receipt",),
            ("raw body requested", "send/mutate requested", "OAuth/session requested"),
            ("email metadata refs", "Cassandra detangle refs"),
            metadata_receipt_shape,
            ("raw body present", "send authority requested", "OAuth requested"),
            ("Gmail access attempted", "email sent", "hidden account mutation"),
            ("Guardian block", "operator approval absent", "sensitivity unknown"),
            "Show as future-gated metadata review; never as live inbox control.",
            "Security audit, metadata refs, operator approval, and receipts exist.",
            "OAuth/Gmail/raw body/send/mutation requested or gates missing.",
        ),
        AdapterRecord(
            "calendar_metadata_adapter_candidate",
            "Calendar Metadata Adapter Candidate",
            "domain_workflow",
            "FUTURE_GATED",
            ("READ_METADATA", "READ_REDACTED_CONTENT"),
            ("preview calendar metadata/context refs",),
            ("read raw calendar bodies", "mutate calendar", "send invites"),
            ("future metadata-only schedule review after gates",),
            ("cassandra", "guardian", "operator_winship"),
            ("human_operator", "blocked_no_model", "local_sensitive"),
            ("communications_review", "protected_access_review"),
            ("code_implementation_package",),
            ("calendar metadata refs", "no raw body by default", "Guardian gate if sensitive"),
            "sensitive_private",
            ("guardian_protected_access_gate", "operator_approval", "security_audit"),
            True,
            True,
            ("calendar metadata receipt",),
            ("raw event body requested", "calendar mutation requested", "OAuth/session requested"),
            ("calendar metadata refs", "Cassandra detangle refs"),
            metadata_receipt_shape,
            ("raw body present", "mutation requested", "OAuth requested"),
            ("calendar mutation attempted", "invite sent", "hidden account mutation"),
            ("Guardian block", "operator approval absent", "sensitivity unknown"),
            "Show as future-gated metadata review; never as live calendar control.",
            "Security audit, metadata refs, operator approval, and receipts exist.",
            "OAuth/calendar raw body/mutation requested or gates missing.",
        ),
        AdapterRecord(
            "music_art_metadata_adapter",
            "Music/Art Metadata Adapter",
            "domain_workflow",
            "ACTIVE_PREVIEW_ONLY",
            ("READ_METADATA",),
            ("read project capsule/music metadata refs", "preview Niles/Struna context"),
            ("ingest unrelated private libraries", "release/upload/publish", "account action"),
            ("future scoped creative metadata package after rights/sensitivity gate",),
            ("niles", "operator_winship", "codex"),
            ("human_operator", "blocked_no_model", "local_reasoning", "external_multimodal"),
            ("music_creative_review", "world_lane_work_package"),
            ("finance_ap_review", "protected_access_review"),
            ("project capsule refs", "rights/sensitivity metadata", "no unrelated private material"),
            "internal_operator_safe",
            ("agent_memory_scope_contract", "source_context_gates"),
            False,
            False,
            ("creative metadata receipt when promoted",),
            ("rights sensitivity unknown", "raw private library requested", "account action requested"),
            ("Struna project capsule refs", "music/art metadata refs"),
            metadata_receipt_shape,
            ("missing project capsule", "rights unknown", "private material mixed in"),
            ("distribution account action", "unrelated private media ingestion", "rights leak"),
            ("rights conflict", "operator stops lane", "sensitivity unknown"),
            "Show as Niles/Struna preview context, not release tooling.",
            "Scoped capsule refs and rights/sensitivity metadata exist.",
            "Unrelated private material, account action, or rights/sensitivity unknown.",
        ),
        AdapterRecord(
            "browser_oauth_adapter",
            "Browser/OAuth Adapter",
            "external_account_browser_api",
            "BLOCKED_NO_AUTHORITY",
            ("BROWSER_SESSION", "NETWORK_API", "MUTATE_ACCOUNT"),
            (),
            ("browser control", "OAuth", "credential/token/session handling", "account mutation"),
            ("future security-audited browser/OAuth bridge if explicitly authorized",),
            ("operator_winship", "guardian"),
            ("human_operator", "blocked_no_model"),
            ("protected_access_review",),
            PACKAGE_TYPES,
            ("no credentials/tokens/cookies", "future protected reference only"),
            "credential_or_token",
            ("security_audit", "guardian_protected_access_gate", "operator_approval"),
            True,
            True,
            ("browser/OAuth session receipt if ever authorized",),
            ("credential requested", "session/cookie requested", "browser action requested"),
            ("none now",),
            execution_receipt_shape,
            ("credential prompt", "session access", "network call"),
            ("OAuth/token access", "browser launched", "account mutated"),
            ("any current use request", "operator approval missing", "Guardian block"),
            "Show as blocked/future-gated; do not render launch controls.",
            "Only after explicit security lane, gates, and receipts.",
            "All current browser/OAuth/account requests.",
        ),
        AdapterRecord(
            "gmail_calendar_adapter",
            "Gmail/Calendar Adapter",
            "external_account_browser_api",
            "BLOCKED_NO_AUTHORITY",
            ("NETWORK_API", "READ_RAW_CONTENT", "SEND_MESSAGE", "MUTATE_ACCOUNT"),
            (),
            ("Gmail access", "calendar access", "raw bodies", "send/mutate"),
            ("future metadata-only account adapter after security audit",),
            ("cassandra", "guardian", "operator_winship"),
            ("human_operator", "blocked_no_model", "local_sensitive"),
            ("communications_review", "protected_access_review"),
            PACKAGE_TYPES,
            ("metadata refs only until future gates", "no OAuth/session"),
            "sensitive_private",
            ("security_audit", "guardian_protected_access_gate", "operator_approval"),
            True,
            True,
            ("gmail/calendar adapter receipt if ever authorized",),
            ("OAuth requested", "raw body requested", "send/mutate requested"),
            ("none now",),
            execution_receipt_shape,
            ("raw body access", "send requested", "calendar mutation"),
            ("email sent", "calendar mutated", "OAuth token handled"),
            ("any current use request", "operator approval missing", "Guardian block"),
            "Show as blocked/future-gated; metadata refs may be shown through Cassandra contracts only.",
            "Security audit, operator approval, Guardian gate, metadata-only receipts.",
            "Gmail/calendar access, send/mutate, OAuth/session, or raw bodies.",
        ),
        AdapterRecord(
            "coupa_adapter",
            "Coupa Adapter",
            "external_account_browser_api",
            "BLOCKED_SENSITIVE",
            ("BROWSER_SESSION", "SUBMIT_FORM", "APPROVE_ACTION", "MUTATE_ACCOUNT"),
            (),
            ("Coupa access", "credentials", "submit invoice", "approve action"),
            ("future protected finance portal adapter after security audit",),
            ("cassandra", "guardian", "operator_winship"),
            ("human_operator", "blocked_no_model", "local_sensitive"),
            ("finance_ap_review", "protected_access_review"),
            PACKAGE_TYPES,
            ("protected finance metadata refs only", "no portal/session/credential material"),
            "finance_or_ap_sensitive",
            ("security_audit", "guardian_protected_access_gate", "operator_approval"),
            True,
            True,
            ("Coupa action receipt if ever authorized",),
            ("credential requested", "submit/approve requested", "portal action requested"),
            ("none now",),
            execution_receipt_shape,
            ("credential prompt", "portal session", "submit/approve request"),
            ("Coupa accessed", "invoice submitted", "approval performed"),
            ("any current use request", "operator approval missing", "Guardian block"),
            "Show as blocked Finance World future adapter.",
            "Only after security audit, Guardian gate, operator approval, and receipts.",
            "All current Coupa/credential/submit/approve requests.",
        ),
        AdapterRecord(
            "telegram_adapter",
            "Telegram Adapter",
            "external_account_browser_api",
            "BLOCKED_NO_AUTHORITY",
            ("SEND_MESSAGE", "NETWORK_API"),
            (),
            ("Telegram send", "runtime listener activation", "token handling"),
            ("future notification adapter if explicitly authorized",),
            ("cassandra", "chief", "guardian", "operator_winship"),
            ("human_operator", "blocked_no_model"),
            ("communications_review", "check_light_diagnostic_package"),
            PACKAGE_TYPES,
            ("metadata-only refs", "no token/chat body material"),
            "sensitive_private",
            ("security_audit", "operator_approval", "guardian_protected_access_gate_when_sensitive"),
            True,
            True,
            ("Telegram send/notification receipt if ever authorized",),
            ("token requested", "send requested", "runtime listener requested"),
            ("none now",),
            execution_receipt_shape,
            ("send requested", "token material", "runtime activation"),
            ("message sent", "token accessed", "listener started"),
            ("any current use request", "operator approval missing", "Guardian block"),
            "Show as blocked/future-gated; no live notification control.",
            "Only after explicit security and operator approval lanes.",
            "Token, send, runtime listener, or network request.",
        ),
        AdapterRecord(
            "web_api_adapter_candidate",
            "Web/API Adapter Candidate",
            "external_account_browser_api",
            "CANDIDATE_UNMAPPED",
            ("NETWORK_API", "READ_METADATA"),
            (),
            ("network API call", "external endpoint", "credentialed API"),
            ("future API adapter after endpoint, credential, and receipt contracts exist",),
            ("guardian", "operator_winship", "codex", "hermes"),
            ("human_operator", "blocked_no_model"),
            ("verification_review_package", "architecture_review"),
            PACKAGE_TYPES,
            ("no network now", "endpoint metadata only"),
            "unknown_fail_closed",
            ("security_audit", "operator_approval", "api_adapter_contract"),
            True,
            True,
            ("network call receipt if ever authorized",),
            ("endpoint unknown", "credential needed", "network call requested"),
            ("API spec refs only",),
            execution_receipt_shape,
            ("endpoint unknown", "network call attempted", "credential prompt"),
            ("network used", "credential requested", "unreceipted output"),
            ("unknown endpoint", "operator stops lane", "Guardian block"),
            "Show as candidate terrain; do not render API controls.",
            "Endpoint contract, security review, gates, and receipts exist.",
            "Any current network call or credential path.",
        ),
        AdapterRecord(
            "planner_adapter_candidate",
            "Planner Adapter Candidate",
            "runtime_agent",
            "FUTURE_GATED",
            ("AGENT_LAUNCH", "QUEUE_EXECUTION"),
            (),
            ("planner launch", "autonomy loop", "runtime agent"),
            ("post-security planner if threshold, queue receipts, and kill switch exist",),
            ("chief", "guardian", "operator_winship"),
            ("human_operator", "blocked_no_model", "local_reasoning"),
            ("confidence_detour_package", "helm_lane_awareness_package"),
            PACKAGE_TYPES,
            ("package refs only", "no runtime queue"),
            "internal_operator_safe",
            ("security_audit", "operator_approval", "queue_lifecycle_receipts"),
            True,
            True,
            ("planner lifecycle receipt if ever authorized",),
            ("queue requested", "planner loop requested", "kill switch missing"),
            ("future queue contract refs",),
            execution_receipt_shape,
            ("planner self-launch", "missing receipt", "scope drift"),
            ("planner/builder execution", "hidden background work", "self-authorized tools"),
            ("security audit absent", "kill switch absent", "operator stops lane"),
            "Show as post-security autonomy candidate only.",
            "Security audit, queue lifecycle, revocation, and receipts exist.",
            "Pre-security or any live planner/queue request.",
        ),
        AdapterRecord(
            "builder_adapter_candidate",
            "Builder Adapter Candidate",
            "runtime_agent",
            "FUTURE_GATED",
            ("AGENT_LAUNCH", "QUEUE_EXECUTION", "WRITE_LOCAL_FILE", "RUN_TEST"),
            (),
            ("builder launch", "autonomous code mutation", "runtime agent"),
            ("post-security bounded builder after queue/receipt/kill-switch contracts",),
            ("chief", "codex", "guardian", "operator_winship"),
            ("human_operator", "blocked_no_model", "external_code_worker"),
            ("code_implementation_package", "verification_review_package"),
            PACKAGE_TYPES,
            ("package-bound refs only", "no autonomous mutation"),
            "internal_operator_safe",
            ("security_audit", "operator_approval", "queue_lifecycle_receipts"),
            True,
            True,
            ("builder lifecycle receipt if ever authorized",),
            ("autonomous mutation requested", "kill switch missing", "scope ambiguous"),
            ("future queue contract refs", "package refs"),
            execution_receipt_shape,
            ("builder self-launch", "missing receipt", "scope drift"),
            ("autonomous write", "hidden background work", "self-authorized tools"),
            ("security audit absent", "kill switch absent", "operator stops lane"),
            "Show as post-security autonomy candidate only.",
            "Security audit, package scope, queue lifecycle, revocation, and receipts exist.",
            "Pre-security or any live builder/queue request.",
        ),
        AdapterRecord(
            "chief_test_harness_adapter",
            "Chief Test Harness Adapter",
            "runtime_agent",
            "FUTURE_GATED",
            ("RUN_TEST", "RECEIPT_WRITE", "READ_METADATA"),
            ("preview test harness expectations",),
            ("self-authorize fixes", "execute repairs", "runtime loop"),
            ("future receipt/result verification harness after security gate",),
            ("chief", "guardian", "codex", "operator_winship"),
            ("human_operator", "blocked_no_model", "local_reasoning"),
            ("check_light_diagnostic_package", "verification_review_package"),
            PACKAGE_TYPES,
            ("receipt/result refs", "bounded test refs", "no repair authority"),
            "internal_operator_safe",
            ("security_audit", "package_compiler_contract", "operator_approval"),
            True,
            True,
            ("test harness receipt if ever authorized",),
            ("fix execution requested", "repair/remount/delete requested", "receipt missing"),
            ("test result refs", "receipt refs"),
            execution_receipt_shape,
            ("test failure", "receipt missing", "harness scope drift"),
            ("repair attempted", "self-authorized pass", "hidden runtime"),
            ("operator stops lane", "Guardian block", "scope ambiguity"),
            "Show as future Chief verification harness, not an auto-fix button.",
            "Security gate, explicit tests, receipts, and no repair authority exist.",
            "Any repair/fix/remount/delete or self-authorization request.",
        ),
        AdapterRecord(
            "repo_b_planner_builder_adapter",
            "Repo B Planner/Builder Adapter",
            "runtime_agent",
            "CANDIDATE_UNMAPPED",
            ("AGENT_LAUNCH", "QUEUE_EXECUTION", "RUN_SCRIPT"),
            (),
            ("Repo B execution", "planner/builder loop", "broad Repo B inspection"),
            ("future discovery/classification only after explicit lane",),
            ("chief", "guardian", "operator_winship"),
            ("human_operator", "blocked_no_model"),
            ("helm_lane_awareness_package",),
            PACKAGE_TYPES,
            ("Repo A read-model refs only", "no Repo B mutation/inspection now"),
            "unknown_fail_closed",
            ("discovery_classification_lane", "security_audit", "operator_approval"),
            True,
            True,
            ("Repo B classification receipt if ever authorized",),
            ("Repo B code execution requested", "broad private inspection requested", "planner loop requested"),
            ("Repo A Repo B delta read-model refs only",),
            execution_receipt_shape,
            ("unknown code path", "planner execution", "Repo B mutation"),
            ("Repo B mutated", "planner/builder run", "broad private inspection"),
            ("classification absent", "operator stops lane", "Guardian block"),
            "Show as candidate unmapped future terrain.",
            "Explicit Repo B discovery/classification lane and security gate exist.",
            "Any current Repo B execution, mutation, broad inspection, or planner/builder loop.",
        ),
        AdapterRecord(
            "guardian_protected_access_gate",
            "Guardian Protected Access Gate",
            "safety_security",
            "RECEIPT_ONLY",
            ("READ_METADATA", "RECEIPT_WRITE"),
            ("evaluate metadata-only gate posture", "recommend approve/block/redact/quarantine"),
            ("self-authorize protected access", "execute approval", "read raw secrets"),
            ("future gate receipts after protected access flow exists",),
            ("guardian", "operator_winship", "chief", "cassandra"),
            ("human_operator", "blocked_no_model", "local_sensitive", "local_reasoning"),
            ("protected_access_review", "finance_ap_review", "communications_review"),
            ("code_implementation_package",),
            ("protected metadata refs", "sensitivity classification", "operator final authority"),
            "protected_reference_only",
            ("guardian_protected_access_gate_spec", "operator_approval_when_required"),
            True,
            True,
            ("Guardian gate receipt", "protected evidence reference receipt"),
            ("protected ref missing", "operator approval missing", "raw body requested"),
            ("protected evidence metadata refs", "gate request refs"),
            metadata_receipt_shape,
            ("missing protected ref", "operator approval absent", "sensitivity unknown"),
            ("Guardian self-authorizes", "raw protected file exposed", "approval executed"),
            ("gate failed", "proof conflict", "operator stops lane"),
            "Show Guardian's recommendation and required human gate, not a bypass.",
            "Protected metadata, gate request, and operator approval posture are explicit.",
            "Raw protected content, self-authorization, missing proof, or missing operator gate.",
        ),
        AdapterRecord(
            "redaction_adapter",
            "Redaction Adapter",
            "safety_security",
            "ACTIVE_PREVIEW_ONLY",
            ("READ_METADATA", "WRITE_DRAFT"),
            ("define redaction plan and excluded fields", "preview sanitized context refs"),
            ("silently transform private raw bodies", "claim redaction without receipt"),
            ("future redacted content production after Guardian gate",),
            ("guardian", "chief", "cassandra", "hermes", "codex", "operator_winship"),
            ("human_operator", "blocked_no_model", "local_sensitive", "local_reasoning"),
            ("protected_access_review", "verification_review_package", "finance_ap_review"),
            (),
            ("source refs", "redaction policy refs", "no raw body by default"),
            "protected_reference_only",
            ("guardian_protected_access_gate_when_sensitive", "redaction_receipt"),
            True,
            True,
            ("redaction plan receipt",),
            ("raw body requested", "sensitivity unknown", "redaction receipt missing"),
            ("redaction policy refs", "source card refs"),
            metadata_receipt_shape,
            ("redaction unverifiable", "sensitive data included", "source missing"),
            ("sensitive data leaked", "claims proof without source", "gate bypass"),
            ("redaction conflict", "Guardian block", "operator stops lane"),
            "Show exclusions and redaction plan before any protected context is used.",
            "Source refs, sensitivity, and redaction receipt are available.",
            "Raw private body, missing sensitivity, missing receipt, or gate bypass.",
        ),
        AdapterRecord(
            "secret_scanner",
            "Secret/Forbidden Authority Scanner",
            "safety_security",
            "ACTIVE_READ_ONLY",
            ("READ_METADATA",),
            ("scan intended source/contract text for forbidden imports/authority strings",),
            ("read credential files", "open secret stores", "repair leaked secrets"),
            ("future structured scan receipt after policy lane",),
            ("guardian", "codex", "chief", "operator_winship"),
            ("human_operator", "blocked_no_model", "local_reasoning", "external_code_worker"),
            ("verification_review_package", "code_implementation_package", "protected_access_review"),
            (),
            ("allowed workspace source refs", "no credential file reads", "static text only"),
            "internal_operator_safe",
            ("openclaw_sensitive_policy", "package_compiler_contract"),
            False,
            False,
            ("forbidden-authority scan receipt",),
            ("no-go path", "credential file", "broad private scan"),
            ("source file refs", "forbidden token list"),
            metadata_receipt_shape,
            ("no-go path skipped", "forbidden token found", "scan scope ambiguous"),
            ("credential file read", "broad private scan", "secret body exposed"),
            ("forbidden token hit", "scope ambiguity", "operator stops lane"),
            "Show static scan result as validation proof.",
            "Scan scope is source/test/generated contract files only and no secret bodies.",
            "No-go path, credential file, broad private scan, or leaked secret content.",
        ),
        AdapterRecord(
            "authority_revocation_kill_switch_adapter_candidate",
            "Authority Revocation / Kill-Switch Adapter Candidate",
            "safety_security",
            "CANDIDATE_UNMAPPED",
            ("RECEIPT_WRITE", "QUEUE_EXECUTION"),
            (),
            ("runtime kill switch", "daemon control", "hidden monitoring"),
            ("future revocation contract after runtime lanes exist",),
            ("guardian", "chief", "operator_winship"),
            ("human_operator", "blocked_no_model"),
            ("protected_access_review", "check_light_diagnostic_package"),
            PACKAGE_TYPES,
            ("no runtime now", "revocation receipt shape only"),
            "internal_operator_safe",
            ("security_audit", "operator_approval", "runtime_authority_contract"),
            True,
            True,
            ("revocation receipt if ever authorized",),
            ("runtime not mapped", "kill-switch target unknown", "receipt missing"),
            ("future runtime adapter refs only",),
            execution_receipt_shape,
            ("target unknown", "runtime absent", "receipt missing"),
            ("hidden monitoring", "daemon mutation", "self-authorized shutdown"),
            ("runtime absent", "operator stops lane", "Guardian block"),
            "Show as future safety primitive, not current runtime control.",
            "Runtime authority exists, targets are mapped, and receipts are defined.",
            "No runtime contract, no target map, or any hidden daemon/control request.",
        ),
        AdapterRecord(
            "suspicious_output_quarantine_adapter_candidate",
            "Suspicious Output Quarantine Adapter Candidate",
            "safety_security",
            "CANDIDATE_UNMAPPED",
            ("RECEIPT_WRITE", "READ_METADATA"),
            ("define suspicious-output quarantine criteria",),
            ("delete files", "silently suppress evidence", "mutate canonical memory"),
            ("future quarantine receipt after receipt/memory lanes exist",),
            ("guardian", "chief", "operator_winship"),
            ("human_operator", "blocked_no_model", "local_reasoning"),
            ("verification_review_package", "protected_access_review", "check_light_diagnostic_package"),
            (),
            ("output refs", "proof refs", "no destructive mutation"),
            "internal_operator_safe",
            ("guardian_protected_access_gate", "memory_candidate_receipt"),
            True,
            True,
            ("quarantine receipt if ever authorized",),
            ("output contradicts proof", "sensitive leak suspected", "malformed receipt"),
            ("output refs", "proof refs"),
            metadata_receipt_shape,
            ("proof contradiction", "sensitivity leak", "missing receipt"),
            ("deletes evidence", "hides proof", "canonical memory mutation"),
            ("operator review required", "Guardian block", "source conflict"),
            "Show quarantined items in proof/detail, not as deleted or forgotten.",
            "Quarantine criteria, receipts, and non-destructive handling exist.",
            "Destructive handling, hidden suppression, or missing receipt/proof.",
        ),
    )


ACTOR_ADAPTER_RULES = (
    ActorAdapterRule(
        "operator_winship",
        (
            "final approval/rejection of gates",
            "read all adapter summaries",
            "request package preview or proof detail",
        ),
        ("operator_is_not_a_tool_adapter",),
        ("may approve future gates after security review",),
        "Final human authority; may request context or approve gates, but does not become an adapter.",
        "Show operator decision points, not fake automation.",
    ),
    ActorAdapterRule(
        "chief",
        (
            "diagnostic/readback adapters",
            "health/proof/read-model receipt inspection",
            "check-engine package previews",
        ),
        ("repair", "remount", "cleanup/delete", "send/account access", "self-authorized tools"),
        ("Chief test harness after security/receipt lanes",),
        "Chief can inspect and diagnose; no repair or execution authority is granted.",
        "Route Check Engine and workbench reliability proof to Chief.",
    ),
    ActorAdapterRule(
        "guardian",
        (
            "safety/security/protected-access gate adapters",
            "redaction/quarantine/revocation recommendations",
            "receipt validation",
        ),
        ("self-authorization", "execution bypass", "raw secret storage", "approval execution"),
        ("future revocation/kill-switch after runtime contract exists",),
        "Guardian recommends block/redact/quarantine/revoke and validates gates; it cannot bypass Operator.",
        "Route protected access ambiguity and authority questions to Guardian first.",
    ),
    ActorAdapterRule(
        "cassandra",
        (
            "finance/comms metadata preview adapters",
            "Capital Hilton proof metadata package previews",
            "Cassandra detangle refs",
        ),
        ("Coupa access", "Gmail/calendar raw bodies", "send/submit/approve", "OAuth/session handling"),
        ("future communications/finance metadata adapters after security gates",),
        "Cassandra handles review posture only until account/protected gates exist.",
        "Route finance/AP/comms package previews to Cassandra, with Guardian for protected/approval-adjacent work.",
    ),
    ActorAdapterRule(
        "hermes",
        (
            "architecture/doctrine/system-coherence adapters",
            "contract/read-model review",
            "source-conflict review",
        ),
        ("runtime execution", "private raw body ingestion", "account/tool activation"),
        ("future architecture review package receipts",),
        "Hermes reviews systems/doctrine coherence, not live runtime tools.",
        "Route big-picture contract and architecture coherence to Hermes.",
    ),
    ActorAdapterRule(
        "niles",
        (
            "music/art metadata adapters",
            "Struna/project capsule context refs",
            "creative package previews",
        ),
        ("broad private library ingestion", "release/upload/account action", "unrelated private/client context"),
        ("future creative metadata adapters after rights/sensitivity gates",),
        "Niles receives scoped creative refs only.",
        "Route music/art and Struna context previews to Niles.",
    ),
    ActorAdapterRule(
        "codex",
        (
            "scoped repo file reader",
            "scoped code patch proposal",
            "focused test/build verification in package-bound worker lanes",
        ),
        ("credentials", "network", "arbitrary execution", "hidden memory", "scope expansion", "PC C-drive writes"),
        ("future package-bound implementation receipts",),
        "Codex may do scoped implementation work when explicitly prompted; this registry adds no runtime authority.",
        "Route code/test/build lanes to Codex only through package boundaries.",
    ),
    ActorAdapterRule(
        "gemini_antigravity",
        (
            "scoped proof/refactor package previews",
            "external worker candidate context refs",
        ),
        ("retained memory", "broad context", "direct canonical writes", "raw protected material"),
        ("future external worker/refactor adapter after package and receipt gates",),
        "Gemini/Antigravity remains package-bounded and cannot write canonical state directly.",
        "Use for scoped proof/refactor/review only after package preview and sensitivity policy.",
    ),
)

RECOMMENDED_NEXT_LANES = (
    RecommendedLane(
        "memory_candidate_receipt_v0",
        "Memory Candidate Receipt v0",
        "P1",
        "Tool adapters can propose memory candidates only if candidate receipts exist.",
        "receipt metadata only; no canonical memory write",
    ),
    RecommendedLane(
        "model_selection_receipt_v0",
        "Model Selection Receipt v0",
        "P1",
        "Model posture needs a deterministic decision receipt before any future model routing.",
        "receipt metadata only; no model call",
    ),
    RecommendedLane(
        "package_preview_receipt_v0",
        "Package Preview Receipt v0",
        "P1",
        "Package previews need receipts before any future copy/open/launch path is allowed.",
        "receipt metadata only; no dispatch",
    ),
    RecommendedLane(
        "mission_control_package_preview_actor_routing_surface_v0",
        "Mission Control Package Preview / Actor Routing Surface v0",
        "P2",
        "Mission Control can render tool inclusion/exclusion and actor routing without executing tools.",
        "Mac read-only UI; no backend command authority",
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


def _state_definition_record(state: AdapterStateDefinition) -> dict[str, Any]:
    return {
        "state_id": state.state_id,
        "meaning": state.meaning,
        "promotion_rule": state.promotion_rule,
        "demotion_rule": state.demotion_rule,
        "current_execution_allowed": state.current_execution_allowed,
    }


def _capability_record(policy: CapabilityClassPolicy) -> dict[str, Any]:
    return {
        "capability_class": policy.capability_class,
        "current_authority_status": policy.current_authority_status,
        "future_gate_requirement": policy.future_gate_requirement,
        "receipt_requirement": policy.receipt_requirement,
        "guardian_requirement": policy.guardian_requirement,
        "operator_approval_requirement": policy.operator_approval_requirement,
        "blocked_conditions": list(policy.blocked_conditions),
    }


def _adapter_record(adapter: AdapterRecord) -> dict[str, Any]:
    return {
        "adapter_id": adapter.adapter_id,
        "display_name": adapter.display_name,
        "category": adapter.category,
        "adapter_state": adapter.adapter_state,
        "capability_classes": list(adapter.capability_classes),
        "current_allowed_actions": list(adapter.current_allowed_actions),
        "current_blocked_actions": list(adapter.current_blocked_actions),
        "future_eligible_actions": list(adapter.future_eligible_actions),
        "actor_eligibility": list(adapter.actor_eligibility),
        "model_class_eligibility": list(adapter.model_class_eligibility),
        "package_types_allowed": list(adapter.package_types_allowed),
        "package_types_blocked": list(adapter.package_types_blocked),
        "memory_scope_requirements": list(adapter.memory_scope_requirements),
        "sensitivity_ceiling": adapter.sensitivity_ceiling,
        "required_gates": list(adapter.required_gates),
        "required_operator_approval": adapter.required_operator_approval,
        "required_guardian_review": adapter.required_guardian_review,
        "required_receipts": list(adapter.required_receipts),
        "stop_conditions": list(adapter.stop_conditions),
        "proof_inputs": list(adapter.proof_inputs),
        "output_receipt_shape": list(adapter.output_receipt_shape),
        "failure_modes": list(adapter.failure_modes),
        "quarantine_conditions": list(adapter.quarantine_conditions),
        "revocation_conditions": list(adapter.revocation_conditions),
        "mission_control_display_guidance": adapter.mission_control_display_guidance,
        "what_makes_adapter_available": adapter.what_makes_adapter_available,
        "what_keeps_adapter_blocked": adapter.what_keeps_adapter_blocked,
        "adapter_may_self_authorize": False,
        "live_execution_enabled_now": False,
    }


def _actor_rule_record(rule: ActorAdapterRule) -> dict[str, Any]:
    return {
        "actor_id": rule.actor_id,
        "current_adapter_eligibility": list(rule.current_adapter_eligibility),
        "blocked_adapter_classes": list(rule.blocked_adapter_classes),
        "future_eligible_adapter_classes": list(rule.future_eligible_adapter_classes),
        "required_boundary": rule.required_boundary,
        "notes_for_mission_control": rule.notes_for_mission_control,
        "can_self_grant_tool": False,
    }


def _recommended_lane_record(lane: RecommendedLane) -> dict[str, Any]:
    return {
        "lane_id": lane.lane_id,
        "title": lane.title,
        "priority": lane.priority,
        "why_next": lane.why_next,
        "hard_boundary": lane.hard_boundary,
    }


def build_tool_protocol_adapter_registry_contract(
    *,
    repo_root: str | Path = ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    evidence_sources = [_source_record(source, repo_root=repo_root) for source in EVIDENCE_SOURCES]
    capability_policies = [_capability_record(policy) for policy in _capability_policy()]
    adapters = [_adapter_record(adapter) for adapter in _adapter_specs()]
    active_states = {"ACTIVE_READ_ONLY", "ACTIVE_PREVIEW_ONLY", "RECEIPT_ONLY"}
    active_count = sum(1 for adapter in adapters if adapter["adapter_state"] == "ACTIVE_READ_ONLY")
    blocked_or_future_count = sum(1 for adapter in adapters if adapter["adapter_state"] not in active_states)
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": "tool_protocol_adapter_registry_contract",
        "generated_at": generated_at,
        **NO_AUTHORITY_FLAGS,
        "contract_status": "deterministic_tool_protocol_adapter_registry_metadata_only",
        "operator_summary": (
            "OpenClaw now has a deterministic tool/protocol adapter registry. It lists which adapters are read-only, "
            "preview-only, receipt-only, candidate, future-gated, blocked, or quarantined before any runtime wiring. "
            "Tools are not authority by themselves; packages must satisfy actor, model, memory, Guardian, Operator, "
            "and receipt gates before future use."
        ),
        "operator_field_notes": [
            {
                "note_id": "powershell_window_did_not_close",
                "source_type": "operator_reported_context",
                "summary": (
                    "Operator observed a PowerShell window did not close; treat as bridge/process lifecycle evidence "
                    "for future Check Transmission or Chief diagnostics, not as repair authority."
                ),
                "action_taken_now": "none",
                "safe_next_move": "If bridge symptoms recur, inspect process/marker lifecycle through a bounded diagnostic lane.",
                "authority_added": False,
            }
        ],
        "evidence_sources": evidence_sources,
        "adapter_categories": [
            {
                "category_id": category,
                "meaning": _category_meaning(category),
            }
            for category in ADAPTER_CATEGORIES
        ],
        "adapter_state_model": {
            "allowed_states": list(ADAPTER_STATES),
            "state_definitions": [_state_definition_record(state) for state in ADAPTER_STATE_DEFINITIONS],
            "unknown_adapter_result": "UNKNOWN_FAIL_CLOSED",
            "adapter_may_self_authorize": False,
            "actor_may_self_grant_tool": False,
        },
        "capability_classes": capability_policies,
        "current_authority_matrix": {
            "allowed_now": [
                "read-model inspection",
                "stable map inspection",
                "deterministic package preview",
                "contract export",
                "focused test/build verification in bounded worker tasks",
                "receipt-only metadata generation",
                "static validation",
                "forbidden-authority scans",
                "proof/reference display",
            ],
            "blocked_now": [
                "live browser/OAuth/account flows",
                "Gmail/calendar/Coupa/Telegram access",
                "credentials/tokens/cookies",
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
                "PC C-drive artifact writes",
                "file delete/move authority",
                "broad repair/remount authority",
            ],
        },
        "adapters": adapters,
        "actor_to_adapter_rules": [_actor_rule_record(rule) for rule in ACTOR_ADAPTER_RULES],
        "package_binding_rule": {
            "package_may_reference_adapter_only_if": [
                "adapter exists in registry",
                "adapter state allows package use",
                "package type is allowed",
                "actor is eligible",
                "model class is eligible",
                "memory scope permits the context",
                "sensitivity ceiling is not exceeded",
                "Guardian gate passes if required",
                "Operator approval exists if required",
                "receipt requirements are defined",
                "stop conditions are explicit",
            ],
            "blocked_statuses": list(PACKAGE_TOOL_BLOCK_STATUSES),
            "natural_language_permission_counts_as_authority": False,
            "unknown_adapter_result": "TOOL_UNKNOWN_FAIL_CLOSED",
        },
        "protocol_adapter_doctrine": {
            "definition": "A deterministic wrapper/interface contract, not a live integration.",
            "may_define": [
                "intended protocol",
                "input shape",
                "output shape",
                "receipt shape",
                "gates",
                "safety limits",
                "stop conditions",
                "failure handling",
            ],
            "must_not_define": [
                "live credentials",
                "tokens",
                "account sessions",
                "browser control",
                "hidden network calls",
                "unbounded command execution",
            ],
        },
        "tool_receipt_requirements": {
            "future_execution_receipts_required": True,
            "current_execution_receipts_future_gated": True,
            "metadata_receipts_allowed_now_when_schema_exists": True,
            "required_fields": [
                "receipt_id",
                "adapter_id",
                "package_id",
                "actor",
                "model_class",
                "capability_class_used",
                "input_refs",
                "output_refs",
                "redaction_status",
                "sensitivity",
                "gates_checked",
                "operator_approval_id_if_required",
                "guardian_gate_id_if_required",
                "started_at",
                "completed_at",
                "success_or_failure_state",
                "stop_condition_triggered",
                "files_changed_if_any",
                "commands_run_if_any",
                "network_used",
                "account_accessed",
                "send_submit_approve_performed",
                "receipt_hash",
                "revocation_or_quarantine_status",
            ],
            "receipt_cannot_claim_unobserved_execution": True,
        },
        "failure_quarantine_policy": {
            "quarantine_when": [
                "output contradicts proof",
                "adapter claims authority it does not have",
                "tries to access forbidden memory",
                "tries to use credentials/account/browser",
                "tries to broaden scope",
                "unexpected network attempt",
                "missing receipt",
                "malformed receipt",
                "sensitive data leak",
                "raw private body exposure",
                "fails Guardian gate",
                "fails Operator gate",
                "fails test harness",
                "repeated stale or conflicting output",
            ],
            "revocation_conditions": [
                "authority boundary conflict",
                "receipt mismatch",
                "operator revocation",
                "Guardian block",
                "sensitivity ceiling exceeded",
                "scope drift",
            ],
            "quarantine_is_non_destructive": True,
        },
        "mission_control_surface_guidance": {
            "adapter_registry_overview": [
                "active read-only adapters",
                "preview-only adapters",
                "future-gated adapters",
                "blocked sensitive adapters",
                "quarantined adapters",
                "next required gate",
            ],
            "package_preview_tool_section": [
                "tools included",
                "tools excluded",
                "why excluded",
                "required gates",
                "receipt requirements",
                "stop conditions",
            ],
            "actor_detail": [
                "what adapters this actor can use now",
                "what adapters are blocked",
                "what adapters are future-eligible",
                "what needs Guardian or Operator review",
            ],
            "do_not_show": [
                "live execute buttons",
                "credential prompts",
                "browser/OAuth launch controls",
                "Gmail/calendar/Coupa/Telegram live controls",
                "queue/autonomy run controls",
                "fake adapter confidence percentages",
                "raw private content as tool context",
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
                "contract_id": "tool_protocol_adapter_registry_contract",
                "active_preview_or_read_only_adapters_count": sum(
                    1 for adapter in adapters if adapter["adapter_state"] in {"ACTIVE_READ_ONLY", "ACTIVE_PREVIEW_ONLY"}
                ),
                "blocked_or_future_gated_adapters_count": blocked_or_future_count,
                "highest_risk_blocked_adapters": [
                    "browser_oauth_adapter",
                    "gmail_calendar_adapter",
                    "coupa_adapter",
                    "telegram_adapter",
                    "repo_b_planner_builder_adapter",
                ],
                "next_recommended_lane": "memory_candidate_receipt_v0",
            },
            "next_map_bundle_refresh_requirement": "Include this summary in the next stable map bundle refresh after this contract lands.",
        },
        "recommended_next_lanes": [_recommended_lane_record(lane) for lane in RECOMMENDED_NEXT_LANES],
        "machine_proof": {
            "source_read_models_present": {source["source_id"]: source["present"] for source in evidence_sources},
            "adapter_count": len(adapters),
            "active_read_only_count": active_count,
            "blocked_or_future_gated_count": blocked_or_future_count,
            "adapter_ids": [adapter["adapter_id"] for adapter in adapters],
            "capability_classes": [policy["capability_class"] for policy in capability_policies],
            "live_tool_execution_added": False,
            "model_api_calls_added": False,
            "browser_oauth_account_access_added": False,
            "gmail_calendar_coupa_telegram_access_added": False,
            "credential_or_token_access_added": False,
            "runtime_activation_added": False,
            "repo_b_mutation_added": False,
            "pc_c_drive_artifact_write_added": False,
            "content_hash": None,
        },
    }
    payload["machine_proof"]["content_hash"] = _content_hash(payload)
    return payload


def _category_meaning(category: str) -> str:
    meanings = {
        "read_model_stable_map": "Reads generated read-model, stable map, receipt, and proof reference metadata.",
        "local_code_workspace": "Handles scoped workspace/file/test/build verification in bounded worker tasks.",
        "package_compiler": "Compiles, previews, exports, or validates package/receipt metadata.",
        "domain_workflow": "Represents domain workflow metadata such as finance, comms, calendar, or music/art refs.",
        "external_account_browser_api": "Represents account/browser/API adapters; blocked or future-gated now.",
        "runtime_agent": "Represents planner/builder/orchestrator/queue/test-harness candidates; future-gated now.",
        "safety_security": "Represents Guardian, redaction, secret scan, quarantine, and revocation posture.",
    }
    return meanings[category]


def format_tool_protocol_adapter_registry_contract(payload: dict[str, Any]) -> str:
    lines = [
        "# Tool Protocol Adapter Registry Contract v0",
        "",
        "## Operator Summary",
        payload["operator_summary"],
        "",
        "## Adapter States",
    ]
    for state in payload["adapter_state_model"]["state_definitions"]:
        lines.append(f"- `{state['state_id']}`: {state['meaning']}")
    lines.extend(["", "## Current Authority Matrix", "### Allowed Now"])
    for item in payload["current_authority_matrix"]["allowed_now"]:
        lines.append(f"- {item}")
    lines.extend(["", "### Blocked Now"])
    for item in payload["current_authority_matrix"]["blocked_now"]:
        lines.append(f"- {item}")
    lines.extend(["", "## Adapter Examples"])
    for adapter in payload["adapters"]:
        lines.append(
            f"- `{adapter['adapter_id']}`: `{adapter['adapter_state']}`; "
            f"category `{adapter['category']}`; sensitivity `{adapter['sensitivity_ceiling']}`."
        )
    lines.extend(["", "## Actor / Adapter Rules"])
    for rule in payload["actor_to_adapter_rules"]:
        lines.append(
            f"- `{rule['actor_id']}`: {rule['required_boundary']} "
            f"Blocked: {', '.join(rule['blocked_adapter_classes'])}."
        )
    lines.extend(["", "## Package Binding Rule"])
    for item in payload["package_binding_rule"]["package_may_reference_adapter_only_if"]:
        lines.append(f"- {item}")
    lines.append("")
    lines.append("If any requirement fails, package binding fails closed with one of:")
    for status in payload["package_binding_rule"]["blocked_statuses"]:
        lines.append(f"- `{status}`")
    lines.extend(["", "## Receipt / Quarantine"])
    lines.append("- Every future adapter execution must return a receipt.")
    lines.append("- Metadata-only receipt definitions are allowed only when they do not claim execution.")
    lines.append("- Quarantine is non-destructive and proof-preserving.")
    lines.extend(["", "## Mission Control Guidance"])
    guidance = payload["mission_control_surface_guidance"]
    lines.append("- Show adapter overview by active, preview-only, future-gated, blocked, and quarantined state.")
    lines.append("- In package preview, show tools included/excluded, gates, receipts, and stop conditions.")
    lines.append("- Do not show live execute buttons, credential prompts, or account launch controls.")
    lines.extend(["", "## Stable Map Integration"])
    stable = payload["stable_map_integration"]
    lines.append(f"- Summary included in stable map now: `{str(stable['summary_included_in_stable_map_bundle_now']).lower()}`")
    lines.append(f"- Next requirement: {stable['next_map_bundle_refresh_requirement']}")
    lines.extend(["", "## Operator Field Notes"])
    for note in payload["operator_field_notes"]:
        lines.append(f"- `{note['note_id']}`: {note['summary']} Action now: {note['action_taken_now']}.")
    lines.extend(["", "## Authority Boundary"])
    for key, value in NO_AUTHORITY_FLAGS.items():
        lines.append(f"- `{key}`: `{str(value).lower()}`")
    lines.extend(["", "## Next Lanes"])
    for lane in payload["recommended_next_lanes"]:
        lines.append(f"- `{lane['lane_id']}` ({lane['priority']}): {lane['title']}")
    return "\n".join(lines).rstrip() + "\n"


def export_tool_protocol_adapter_registry_contract(
    *,
    repo_root: str | Path = ROOT,
    export_root: str | Path = DEFAULT_EXPORT_ROOT,
    generated_at: str | None = None,
) -> ToolProtocolAdapterRegistryExportResult:
    payload = build_tool_protocol_adapter_registry_contract(repo_root=repo_root, generated_at=generated_at)
    root = Path(export_root)
    if not root.is_absolute():
        root = Path(repo_root) / root
    root.mkdir(parents=True, exist_ok=True)
    json_path = root / JSON_EXPORT_NAME
    operator_path = root / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(format_tool_protocol_adapter_registry_contract(payload), encoding="utf-8")
    return ToolProtocolAdapterRegistryExportResult(
        schema_version=payload["schema_version"],
        json_path=json_path.as_posix(),
        operator_path=operator_path.as_posix(),
        adapter_count=len(payload["adapters"]),
        active_read_only_count=payload["machine_proof"]["active_read_only_count"],
        blocked_or_future_gated_count=payload["machine_proof"]["blocked_or_future_gated_count"],
        runtime_authority_added=bool(payload["runtime_authority"]),
        tool_execution_authority_added=bool(payload["tool_execution_authority"]),
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export Tool Protocol Adapter Registry Contract read-model.")
    parser.add_argument("--repo-root", default=ROOT.as_posix())
    parser.add_argument("--export-root", default=DEFAULT_EXPORT_ROOT.as_posix())
    parser.add_argument("--format", choices=("summary", "json", "operator"), default="summary")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    result = export_tool_protocol_adapter_registry_contract(
        repo_root=args.repo_root,
        export_root=args.export_root,
    )
    if args.format == "json":
        print(stable_json(build_tool_protocol_adapter_registry_contract(repo_root=args.repo_root)), end="")
    elif args.format == "operator":
        payload = build_tool_protocol_adapter_registry_contract(repo_root=args.repo_root)
        print(format_tool_protocol_adapter_registry_contract(payload), end="")
    else:
        print(
            stable_json(
                {
                    "schema_version": result.schema_version,
                    "json_path": result.json_path,
                    "operator_path": result.operator_path,
                    "adapter_count": result.adapter_count,
                    "active_read_only_count": result.active_read_only_count,
                    "blocked_or_future_gated_count": result.blocked_or_future_gated_count,
                    "runtime_authority_added": result.runtime_authority_added,
                    "tool_execution_authority_added": result.tool_execution_authority_added,
                }
            ),
            end="",
        )
    return 0


__all__ = [
    "ADAPTER_CATEGORIES",
    "ADAPTER_STATES",
    "CAPABILITY_CLASSES",
    "JSON_EXPORT_NAME",
    "KNOWN_ACTOR_IDS",
    "NO_AUTHORITY_FLAGS",
    "OPERATOR_EXPORT_NAME",
    "PACKAGE_TOOL_BLOCK_STATUSES",
    "SCHEMA_VERSION",
    "build_tool_protocol_adapter_registry_contract",
    "export_tool_protocol_adapter_registry_contract",
    "format_tool_protocol_adapter_registry_contract",
    "main",
    "stable_json",
]


if __name__ == "__main__":
    raise SystemExit(main())
