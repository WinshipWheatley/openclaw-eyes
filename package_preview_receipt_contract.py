"""Package Preview Receipt Contract v0 for OpenClaw.

This read-model defines deterministic receipts for compiled mission package
previews. It is metadata only: no package dispatch, model call, agent
activation, tool execution, queue/autonomy, account/browser/API access,
send/submit/approval, credential handling, raw private body ingestion, Repo B
execution, Mac sync/import, or PC system-drive writes are created.
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

SCHEMA_VERSION = "package_preview_receipt_contract_v0"
JSON_EXPORT_NAME = "package_preview_receipt_contract.json"
OPERATOR_EXPORT_NAME = "package_preview_receipt_contract_OPERATOR.md"

NO_AUTHORITY_FLAGS = {
    "runtime_authority": False,
    "live_dispatch_authority": False,
    "model_call_authority": False,
    "model_api_execution_authority": False,
    "model_router_runtime_authority": False,
    "actor_agent_activation_authority": False,
    "tool_execution_authority": False,
    "queue_autonomy_execution_authority": False,
    "planner_builder_execution_authority": False,
    "browser_oauth_account_access_enabled": False,
    "gmail_calendar_coupa_telegram_enabled": False,
    "credential_authority": False,
    "send_submit_approval_enabled": False,
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
    "network_operation_enabled": False,
    "pc_c_drive_artifact_write_allowed": False,
    "operator_final_authority": True,
}

RECEIPT_TYPES = (
    "PACKAGE_PREVIEW_COMPILED",
    "PACKAGE_PREVIEW_BLOCKED",
    "PACKAGE_PREVIEW_INCOMPLETE",
    "PACKAGE_PREVIEW_NEEDS_CONTEXT",
    "PACKAGE_PREVIEW_NEEDS_PROOF",
    "PACKAGE_PREVIEW_NEEDS_MEMORY_REVIEW",
    "PACKAGE_PREVIEW_NEEDS_MODEL_SELECTION",
    "PACKAGE_PREVIEW_NEEDS_TOOL_GATE",
    "PACKAGE_PREVIEW_NEEDS_GUARDIAN_GATE",
    "PACKAGE_PREVIEW_NEEDS_OPERATOR_APPROVAL",
    "PACKAGE_PREVIEW_FUTURE_GATED",
    "PACKAGE_PREVIEW_REVOKED",
    "PACKAGE_PREVIEW_QUARANTINED",
    "PACKAGE_PREVIEW_UNKNOWN_FAIL_CLOSED",
)

PREVIEW_STATES = (
    "PREVIEW_REQUESTED",
    "SOURCE_SURFACES_COLLECTED",
    "PACKAGE_FIELDS_CHECKED",
    "CONTEXT_SCOPE_CHECKED",
    "MEMORY_SCOPE_CHECKED",
    "MEMORY_CANDIDATES_CHECKED",
    "MODEL_SELECTION_CHECKED",
    "TOOL_ADAPTERS_CHECKED",
    "SENSITIVITY_CLASSIFIED",
    "AUTHORITY_BOUNDARY_CHECKED",
    "GATES_IDENTIFIED",
    "STOP_CONDITIONS_CHECKED",
    "RECEIPT_REQUIREMENTS_CHECKED",
    "PREVIEW_READY",
    "PREVIEW_BLOCKED",
    "PREVIEW_FUTURE_GATED",
    "PREVIEW_REVOKED",
    "PREVIEW_QUARANTINED",
    "UNKNOWN_FAIL_CLOSED",
)

RECEIPT_FIELDS = (
    "package_preview_receipt_id",
    "package_id",
    "package_type",
    "package_title",
    "package_version",
    "source_contracts",
    "source_read_models",
    "source_receipts",
    "source_stable_map_generation_id",
    "source_bundle_hash",
    "actor_id",
    "agent_character",
    "actor_router_reference",
    "model_selection_receipt_reference",
    "requested_model_class",
    "selected_or_blocked_model_class",
    "tool_adapter_registry_reference",
    "requested_tool_adapters",
    "allowed_tool_adapters",
    "blocked_tool_adapters",
    "memory_scope_reference",
    "memory_candidate_receipt_refs",
    "context_included_refs",
    "context_excluded_refs",
    "raw_body_included",
    "redaction_status",
    "sensitivity",
    "mission",
    "why_it_matters",
    "steps_preview",
    "stop_conditions",
    "proof_refs",
    "missing_proof",
    "authority_level_required",
    "authority_level_granted",
    "runtime_dispatch_allowed",
    "model_call_allowed",
    "tool_execution_allowed",
    "agent_activation_allowed",
    "queue_execution_allowed",
    "account_access_allowed",
    "send_submit_approval_allowed",
    "operator_gate_status",
    "guardian_gate_status",
    "receipt_requirements",
    "preview_status",
    "blocked_reasons",
    "future_gated_reasons",
    "what_would_make_dispatchable",
    "what_makes_safe_to_display",
    "what_makes_quiet",
    "created_at",
    "expires_or_review_after",
    "revocation_status",
    "quarantine_status",
    "receipt_hash",
)

DISPLAY_REQUIRED_FIELDS = (
    "package_id",
    "package_type",
    "mission",
    "actor_id",
    "agent_character",
    "context_included_refs",
    "context_excluded_refs",
    "authority_level_granted",
    "stop_conditions",
    "proof_refs",
    "missing_proof",
    "receipt_requirements",
    "blocked_reasons",
)

FUTURE_DISPATCH_REQUIRED_FIELDS = (
    "model_selection_receipt_reference",
    "tool_adapter_receipt_refs",
    "memory_candidate_approval_receipts",
    "guardian_gate_receipt_if_sensitive",
    "operator_approval_receipt_if_required",
    "rollback_or_requeue_rule",
    "completion_receipt_shape",
    "test_harness_or_verification_requirement",
    "security_audit_gate",
)

BLOCKED_AUTHORITIES = (
    "live model calls",
    "actor/agent activation",
    "tool execution",
    "queue/autonomy execution",
    "planner/builder execution",
    "browser/OAuth/account access",
    "Gmail/calendar/Coupa/Telegram access",
    "credentials/tokens/cookies/API keys",
    "send/submit/approval",
    "raw private body ingestion",
    "external retained memory",
    "hidden model routing",
    "hidden memory",
    "file delete/move authority",
    "cleanup/remount/repair authority",
    "C-drive artifact writes",
)

QUARANTINE_TRIGGERS = (
    "package claims live authority",
    "package includes raw private bodies without gate",
    "package includes credentials/secrets/account/session data",
    "package references unknown actor/model/tool",
    "package skips memory scope",
    "package skips model selection",
    "package skips tool adapter gates",
    "package uses external model with protected context",
    "package lacks stop conditions",
    "package lacks receipt requirements",
    "package tries to self-authorize",
    "package contradicts canonical proof",
    "package includes revoked/stale memory candidates",
    "malformed receipt",
    "missing receipt hash",
)

REVOCATION_TRIGGERS = (
    "source contract changes",
    "stable map generation replaced",
    "model policy changed",
    "memory candidate revoked",
    "tool adapter quarantined",
    "Guardian gate revoked",
    "Operator approval revoked",
    "package output conflicts with proof",
    "security audit blocks lane",
)


@dataclass(frozen=True)
class EvidenceSource:
    source_id: str
    path: str
    role: str


@dataclass(frozen=True)
class PackagePreviewExample:
    example_id: str
    package_id: str
    package_type: str
    package_title: str
    actor_id: str
    agent_character: str
    requested_model_class: str
    selected_or_blocked_model_class: str
    sensitivity: str
    mission: str
    why_it_matters: str
    steps_preview: tuple[str, ...]
    proof_refs: tuple[str, ...]
    missing_proof: tuple[str, ...]
    requested_tool_adapters: tuple[str, ...]
    allowed_tool_adapters: tuple[str, ...]
    blocked_tool_adapters: tuple[str, ...]
    context_included_refs: tuple[str, ...]
    context_excluded_refs: tuple[str, ...]
    operator_gate_status: str
    guardian_gate_status: str
    preview_status: str
    blocked_reasons: tuple[str, ...]
    future_gated_reasons: tuple[str, ...]
    what_would_make_dispatchable: str
    what_makes_safe_to_display: str
    what_makes_quiet: str
    target_world: str | None = None


@dataclass(frozen=True)
class RecommendedLane:
    lane_id: str
    title: str
    priority: str
    why_next: str
    hard_boundary: str


@dataclass(frozen=True)
class PackagePreviewReceiptExportResult:
    schema_version: str
    json_path: str
    operator_path: str
    receipt_type_count: int
    preview_state_count: int
    example_count: int
    runtime_dispatch_authority_added: bool
    model_call_authority_added: bool
    tool_execution_authority_added: bool


EVIDENCE_SOURCES = (
    EvidenceSource("agent_platform_alignment", "generated/read_models/agent_platform_alignment.json", "agent-platform primitive map"),
    EvidenceSource("agent_identity_actor_router_contract", "generated/read_models/agent_identity_actor_router_contract.json", "actor identity and routing boundaries"),
    EvidenceSource("model_selection_policy_contract", "generated/read_models/model_selection_policy_contract.json", "model class policy"),
    EvidenceSource("model_selection_receipt_contract", "generated/read_models/model_selection_receipt_contract.json", "model selection receipt grammar"),
    EvidenceSource("agent_package_preview_contract", "generated/read_models/agent_package_preview_contract.json", "package preview schema"),
    EvidenceSource("agent_memory_scope_contract", "generated/read_models/agent_memory_scope_contract.json", "context/memory scope policy"),
    EvidenceSource("memory_candidate_receipt_contract", "generated/read_models/memory_candidate_receipt_contract.json", "memory candidate receipt grammar"),
    EvidenceSource("tool_protocol_adapter_registry_contract", "generated/read_models/tool_protocol_adapter_registry_contract.json", "tool adapter eligibility"),
    EvidenceSource("agent_terrain_awareness_readback_contract", "generated/read_models/agent_terrain_awareness_readback_contract.json", "agent/persona terrain and dossier cards"),
    EvidenceSource("stable_map_bundle", "generated/read_models/openclaw_map_manifest.json", "app-facing stable map generation"),
    EvidenceSource("operator_threshold_map_contract", "generated/read_models/operator_threshold_map_contract.json", "threshold and lane destiny"),
)

EXAMPLE_PREVIEWS = (
    PackagePreviewExample(
        "cassandra_capital_hilton_invoice_review",
        "package_cassandra_capital_hilton_invoice_review",
        "finance_ap_review",
        "Cassandra Capital Hilton Invoice Review",
        "cassandra",
        "Cassandra",
        "local_sensitive",
        "blocked_no_model",
        "FINANCE_PROTECTED",
        "Preview a protected Capital Hilton invoice review packet for future Finance World handling.",
        "Capital Hilton is the hard finance steel thread; it must be understandable before account action exists.",
        ("orient on invoice lane", "show proof gaps", "identify protected metadata needed", "hold execution blocked"),
        ("generated/read_models/operator_threshold_map_contract.json", "generated/read_models/agent_terrain_awareness_readback_contract.json"),
        ("Coupa protected proof metadata", "Excel/workbook proof metadata", "invoice source card"),
        ("cassandra_capital_hilton_invoice_proof_adapter", "coupa_adapter", "excel_workbook_proof_adapter"),
        ("stable_map_bundle_reader", "package_preview_exporter"),
        ("coupa_adapter", "gmail_calendar_adapter", "browser_oauth_adapter", "send_submit_approval"),
        ("stable_map:capital_hilton", "agent_council:cassandra"),
        ("raw Coupa body", "raw Excel workbook", "Gmail/calendar bodies", "credentials", "account sessions"),
        "future_operator_approval_required",
        "guardian_gate_required_before_protected_context",
        "PACKAGE_PREVIEW_NEEDS_PROOF",
        ("GUARDIAN_GATE_REQUIRED", "OPERATOR_APPROVAL_REQUIRED", "PROTECTED_PROOF_MISSING", "ACCOUNT_ACCESS_BLOCKED"),
        ("security audit", "protected proof metadata", "future Finance World package"),
        "Guardian-approved protected metadata, operator approval, tool receipts, model selection receipt, and security audit.",
        "Only metadata refs and missing-proof labels are included; no raw finance body or account authority.",
        "Protected proof metadata exists and the package remains preview-only until security.",
        "Finance",
    ),
    PackagePreviewExample(
        "chief_check_engine_diagnostic",
        "package_chief_check_engine_diagnostic",
        "check_light_diagnostic_package",
        "Chief Check Engine Diagnostic",
        "chief",
        "Chief",
        "local_reasoning",
        "blocked_no_model",
        "INTERNAL_SYSTEM",
        "Preview Chief diagnostic/readback package for system health posture.",
        "Chief should explain system health proof without repairing or self-authorizing.",
        ("read sync and health posture", "list current causes", "route bridge issues to Check Transmission", "define proof needed"),
        ("generated/read_models/sync_health.json", "generated/read_models/system_health_lights_taxonomy.json"),
        ("current resource remeasurement", "test-harness receipt"),
        ("stable_map_bundle_reader", "receipt_reader"),
        ("stable_map_bundle_reader", "receipt_reader"),
        ("remount", "cleanup_delete", "repair_runner"),
        ("sync_health", "system_health_lights_taxonomy"),
        ("raw logs", "repair commands", "credentials"),
        "not_required_for_preview",
        "not_required_unless_protected_context",
        "PACKAGE_PREVIEW_COMPILED",
        ("RUNTIME_REPAIR_BLOCKED",),
        ("future Chief test harness receipt",),
        "Approved test harness and repair authority after security, if ever granted.",
        "Readback refs only; all repair/remount/cleanup actions are blocked.",
        "Current causes are measured or parked with proof.",
    ),
    PackagePreviewExample(
        "guardian_protected_evidence_review",
        "package_guardian_protected_evidence_review",
        "protected_access_review",
        "Guardian Protected Evidence Review",
        "guardian",
        "Guardian",
        "local_sensitive",
        "blocked_no_model",
        "LEGAL_OR_COMPLIANCE",
        "Preview Guardian gate, redaction, quarantine, and revocation package.",
        "Protected evidence needs a visible safety gate before any package can use it.",
        ("classify sensitivity", "recommend allow/block/redact/quarantine", "list required receipts"),
        ("generated/read_models/agent_memory_scope_contract.json", "generated/read_models/memory_candidate_receipt_contract.json"),
        ("approved protected metadata ref", "Guardian gate receipt"),
        ("guardian_protected_access_gate", "redaction_adapter"),
        ("receipt_reader", "proof_reference_reader"),
        ("raw_private_body_reader", "account_access", "self_authorization"),
        ("memory_candidate_receipt_refs", "protected_metadata_refs"),
        ("raw private bodies", "credentials", "browser sessions"),
        "operator_approval_required_for_future_sensitive_action",
        "guardian_review_required_but_not_self_authorizing",
        "PACKAGE_PREVIEW_NEEDS_GUARDIAN_GATE",
        ("RAW_PRIVATE_CONTEXT_BLOCKED", "GUARDIAN_GATE_REQUIRED"),
        ("protected reference receipt", "operator approval for future use"),
        "Protected metadata receipt and non-self-authorizing Guardian decision receipt.",
        "Shows gate requirements without revealing raw protected content.",
        "Gate decision is receipted and protected content remains reference-only.",
    ),
    PackagePreviewExample(
        "niles_struna_creative_metadata_review",
        "package_niles_struna_creative_metadata_review",
        "music_creative_review",
        "Niles / Struna Creative Metadata Review",
        "niles",
        "Niles",
        "external_multimodal",
        "blocked_no_model",
        "CREATIVE_PRIVATE",
        "Preview a Music / Art package for Struna/Niles metadata and creative context.",
        "Creative preferences can guide work, but real album/project metadata still needs proof.",
        ("show project capsule refs", "separate preference from proof", "list missing metadata", "block release/platform action"),
        ("generated/read_models/agent_terrain_awareness_readback_contract.json",),
        ("real album metadata", "approved Struna project proof"),
        ("music_art_metadata_adapter", "niles_struna_context_adapter"),
        ("stable_map_bundle_reader", "package_preview_exporter"),
        ("broad_archive_ingestion", "release_platform_action", "account_access"),
        ("agent_council:niles", "agent_council:struna"),
        ("broad private archive", "unrelated private/client material", "release account sessions"),
        "operator_approval_required_for_future_external_or_release_action",
        "not_required_for_low_risk_metadata_preview",
        "PACKAGE_PREVIEW_NEEDS_PROOF",
        ("MISSING_PROJECT_PROOF", "BROAD_ARCHIVE_INGESTION_BLOCKED"),
        ("scoped project capsule", "rights/sensitivity review"),
        "Scoped project capsule, metadata proof, and future action receipts.",
        "Context is reference-only and no account/release action is available.",
        "Music/art metadata is classified and proof gaps are parked.",
        "Music / Art",
    ),
    PackagePreviewExample(
        "hermes_architecture_doctrine_review",
        "package_hermes_architecture_doctrine_review",
        "architecture_review",
        "Hermes Architecture Doctrine Review",
        "hermes",
        "Hermes",
        "external_deep_reasoner",
        "blocked_no_model",
        "INTERNAL_SYSTEM",
        "Preview architecture/doctrine coherence package.",
        "Hermes can compare doctrine and contracts without runtime authority.",
        ("summarize contracts", "identify doctrine conflicts", "propose memory candidates", "keep output non-canonical until promoted"),
        ("generated/read_models/agent_platform_alignment.json", "generated/read_models/agent_terrain_awareness_readback_contract.json"),
        ("accepted doctrine promotion receipt",),
        ("stable_map_bundle_reader", "memory_candidate_receipt_generator"),
        ("stable_map_bundle_reader", "package_preview_exporter"),
        ("runtime_activation", "canonical_memory_promotion"),
        ("read_model_refs", "stable_map_refs"),
        ("raw private bodies", "hidden memory", "credentials"),
        "operator_review_required_for_doctrine_promotion",
        "not_required_unless_sensitive_context",
        "PACKAGE_PREVIEW_COMPILED",
        ("CANONICAL_MEMORY_PROMOTION_BLOCKED",),
        ("memory candidate receipt", "operator promotion decision"),
        "Accepted memory candidate/promotion receipt and explicit operator decision.",
        "Uses contract refs only and cannot promote memory by itself.",
        "Doctrine candidate is accepted, rejected, or parked with receipt.",
    ),
    PackagePreviewExample(
        "codex_backend_contract_implementation",
        "package_codex_backend_contract_implementation",
        "code_implementation",
        "Codex Backend Contract Implementation",
        "codex",
        "external_code_worker",
        "external_code_worker",
        "blocked_no_model",
        "INTERNAL_SYSTEM",
        "Preview a scoped backend implementation package for a manual worker lane.",
        "Codex can implement bounded code/test changes, but OpenClaw runtime dispatch remains false.",
        ("define write scope", "define allowed tests", "define stop conditions", "require result receipt"),
        ("generated/read_models/package_compiler_contract.json", "generated/read_models/agent_package_preview_contract.json"),
        ("allowed root manifest", "test command receipt"),
        ("scoped_repo_file_reader", "scoped_code_patch_proposal", "test_runner"),
        ("package_preview_exporter", "receipt_reader"),
        ("network", "credentials", "broad_repo_scan", "delete_move_cleanup"),
        ("scoped file refs", "test refs", "package compiler refs"),
        ("secrets", "no-go paths", "broad private files", "network-dependent context"),
        "operator_preview_required",
        "required_if_sensitive_or_protected_files",
        "PACKAGE_PREVIEW_FUTURE_GATED",
        ("OPENCLAW_RUNTIME_DISPATCH_BLOCKED", "NETWORK_CREDENTIAL_SCOPE_BLOCKED"),
        ("package preview receipt", "test/build receipt", "security gate for runtime dispatch"),
        "Future runtime gate, tool adapter receipt, scoped write receipt, and test result receipt.",
        "This is a manual/package preview; no OpenClaw model/router dispatch occurs.",
        "Implementation result has deterministic test/build receipt or is requeued.",
    ),
    PackagePreviewExample(
        "gemini_antigravity_visual_polish",
        "package_gemini_antigravity_visual_polish",
        "mission_control_ux",
        "Gemini / Antigravity Visual Polish Package",
        "gemini_antigravity",
        "Gemini / Antigravity",
        "external_multimodal",
        "blocked_no_model",
        "PUBLIC_OR_LOW",
        "Preview a sanitized visual polish/refactor package for an external worker candidate.",
        "External workers may help with bounded visual proof, but they cannot retain memory or write canonical state.",
        ("show sanitized screenshots or refs", "list excluded private context", "require output as receipt candidate"),
        ("generated/read_models/agent_package_preview_contract.json",),
        ("sanitized visual refs", "no-retention receipt"),
        ("visual_proof_adapter_candidate",),
        ("package_preview_exporter",),
        ("raw_private_media", "external_retained_memory", "canonical_write"),
        ("sanitized UI proof refs",),
        ("raw private media", "credentials", "client/private docs", "retained memory"),
        "operator_approval_required_for_external_worker",
        "required_if_any_sensitivity_above_public_low",
        "PACKAGE_PREVIEW_FUTURE_GATED",
        ("EXTERNAL_RETENTION_BLOCKED", "OPERATOR_APPROVAL_REQUIRED"),
        ("no-retention proof", "sanitized context packet", "result receipt"),
        "Operator approval, sanitized context packet, no-retention receipt, and result receipt.",
        "No live external model call is made and all context is reference-only.",
        "Worker output is accepted, rejected, or converted to a memory candidate receipt.",
    ),
    PackagePreviewExample(
        "agentic_loop_classification",
        "package_agentic_loop_classification",
        "terrain_discovery_classification",
        "Agentic Loop Classification Package",
        "chief",
        "Chief / Hermes",
        "local_reasoning",
        "blocked_no_model",
        "INTERNAL_SYSTEM",
        "Preview a classification packet for Repo B planner/builder/cue parser terrain.",
        "The agentic loop is operator-reported and important, but it needs classification before autonomy.",
        ("list operator-reported components", "define proof needed", "park premature autonomy", "block execution"),
        ("generated/read_models/agent_terrain_awareness_readback_contract.json",),
        ("approved Repo B metadata", "component manifest", "queue lifecycle receipt"),
        ("repo_b_planner_builder_adapter", "cue_parser_adapter_candidate"),
        ("stable_map_bundle_reader", "package_preview_exporter"),
        ("repo_b_execution", "broad_repo_b_body_inspection", "queue_autonomy_execution"),
        ("agentic_loop terrain refs", "operator memory questions"),
        ("Repo B bodies", "planner/builder runtime outputs", "unbounded queue data"),
        "operator_clarification_required",
        "security_gate_required_before_any_autonomy",
        "PACKAGE_PREVIEW_NEEDS_CONTEXT",
        ("REPO_B_DISCOVERY_NEEDED", "AUTONOMY_BLOCKED", "NO_EXECUTION_AUTHORITY"),
        ("approved metadata-only discovery", "security audit", "tool adapter receipts"),
        "Metadata-only discovery receipts, security audit, and future queue/tool receipts.",
        "Only classification questions and proof gaps are included; no Repo B execution or body inspection.",
        "Loop components are classified, parked, or promoted to a future-gated plan.",
    ),
)

RECOMMENDED_NEXT_LANES = (
    RecommendedLane(
        "tool_adapter_receipt_v0",
        "Tool Adapter Receipt v0",
        "P1",
        "Package previews reference adapters; future adapter use needs deterministic execution/result receipts.",
        "receipt metadata only; no live tool execution",
    ),
    RecommendedLane(
        "package_preview_surface_mission_control_integration_v0",
        "Package Preview Surface / Mission Control Integration v0",
        "P1",
        "Mission Control can render package preview receipts read-only after this grammar exists.",
        "Mac read-only UI; no dispatch controls",
    ),
    RecommendedLane(
        "memory_review_promotion_surface_v0",
        "Memory Review / Promotion Surface v0",
        "P2",
        "Package previews need reviewed memory candidates before canonical memory promotion lanes.",
        "read-only review; no direct canonical memory mutation",
    ),
    RecommendedLane(
        "model_router_implementation_plan_v0",
        "Model Router Implementation Plan v0",
        "P3",
        "A model router plan can remain preview-only until gates and receipts are complete.",
        "plan only; no model router runtime",
    ),
    RecommendedLane(
        "capital_hilton_proof_metadata_packet_v0",
        "Capital Hilton Proof Metadata Packet v0",
        "P2",
        "Capital Hilton needs protected proof metadata before Finance World action can be considered.",
        "metadata-only protected proof; no Coupa/account action",
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
    return {
        "PACKAGE_PREVIEW_COMPILED": "all display-required fields are present and the preview can be shown",
        "PACKAGE_PREVIEW_BLOCKED": "preview is blocked by missing policy, sensitivity, source, gate, or authority proof",
        "PACKAGE_PREVIEW_INCOMPLETE": "display-required fields are missing",
        "PACKAGE_PREVIEW_NEEDS_CONTEXT": "bounded context refs are missing or unclassified",
        "PACKAGE_PREVIEW_NEEDS_PROOF": "machine proof or approved metadata refs are missing",
        "PACKAGE_PREVIEW_NEEDS_MEMORY_REVIEW": "memory candidates require review before package use",
        "PACKAGE_PREVIEW_NEEDS_MODEL_SELECTION": "model selection receipt is missing or blocked",
        "PACKAGE_PREVIEW_NEEDS_TOOL_GATE": "tool adapter gate or receipt is missing",
        "PACKAGE_PREVIEW_NEEDS_GUARDIAN_GATE": "sensitive/protected context requires Guardian review",
        "PACKAGE_PREVIEW_NEEDS_OPERATOR_APPROVAL": "future action requires explicit operator approval",
        "PACKAGE_PREVIEW_FUTURE_GATED": "displayable but cannot be dispatched before future gates",
        "PACKAGE_PREVIEW_REVOKED": "source or approval changed and the preview must not be used",
        "PACKAGE_PREVIEW_QUARANTINED": "unsafe or malformed package preview is quarantined",
        "PACKAGE_PREVIEW_UNKNOWN_FAIL_CLOSED": "insufficient certainty; fail closed",
    }[receipt_type]


def _preview_state_description(state: str) -> str:
    return state.lower().replace("_", " ")


def _example_record(example: PackagePreviewExample) -> dict[str, Any]:
    hard_defaults = {
        "runtime_dispatch_allowed": False,
        "model_call_allowed": False,
        "tool_execution_allowed": False,
        "agent_activation_allowed": False,
        "queue_execution_allowed": False,
        "account_access_allowed": False,
        "send_submit_approval_allowed": False,
        "raw_body_included": False,
    }
    receipt = {
        "package_preview_receipt_id": f"package_preview_receipt_{example.example_id}",
        "example_id": example.example_id,
        "package_id": example.package_id,
        "package_type": example.package_type,
        "package_title": example.package_title,
        "package_version": "example_v0",
        "source_contracts": [source.source_id for source in EVIDENCE_SOURCES],
        "source_read_models": [source.path for source in EVIDENCE_SOURCES],
        "source_receipts": ["example_source_receipts_only"],
        "source_stable_map_generation_id": "stable_map_generation_ref_if_available",
        "source_bundle_hash": "stable_map_bundle_hash_ref_if_available",
        "actor_id": example.actor_id,
        "agent_character": example.agent_character,
        "actor_router_reference": "generated/read_models/agent_identity_actor_router_contract.json",
        "model_selection_receipt_reference": "generated/read_models/model_selection_receipt_contract.json",
        "requested_model_class": example.requested_model_class,
        "selected_or_blocked_model_class": example.selected_or_blocked_model_class,
        "tool_adapter_registry_reference": "generated/read_models/tool_protocol_adapter_registry_contract.json",
        "requested_tool_adapters": list(example.requested_tool_adapters),
        "allowed_tool_adapters": list(example.allowed_tool_adapters),
        "blocked_tool_adapters": list(example.blocked_tool_adapters),
        "memory_scope_reference": "generated/read_models/agent_memory_scope_contract.json",
        "memory_candidate_receipt_refs": [],
        "context_included_refs": list(example.context_included_refs),
        "context_excluded_refs": list(example.context_excluded_refs),
        "redaction_status": "reference_only_no_raw_body",
        "sensitivity": example.sensitivity,
        "mission": example.mission,
        "why_it_matters": example.why_it_matters,
        "steps_preview": list(example.steps_preview),
        "stop_conditions": [
            "required display field missing",
            "raw private body included",
            "credential/account material included",
            "unknown actor/model/tool referenced",
            "authority requested beyond preview",
            "receipt requirements missing",
        ],
        "proof_refs": list(example.proof_refs),
        "missing_proof": list(example.missing_proof),
        "authority_level_required": "preview_only_current_future_gate_for_dispatch",
        "authority_level_granted": "preview_only",
        **hard_defaults,
        "operator_gate_status": example.operator_gate_status,
        "guardian_gate_status": example.guardian_gate_status,
        "receipt_requirements": [
            "package preview receipt",
            "model selection receipt",
            "tool adapter receipt before any future tool use",
            "memory candidate receipt when candidate context is used",
            "future action receipt if security ever grants execution",
        ],
        "preview_status": example.preview_status,
        "blocked_reasons": list(example.blocked_reasons),
        "future_gated_reasons": list(example.future_gated_reasons),
        "what_would_make_dispatchable": example.what_would_make_dispatchable,
        "what_makes_safe_to_display": example.what_makes_safe_to_display,
        "what_makes_quiet": example.what_makes_quiet,
        "created_at": "example_static_timestamp",
        "expires_or_review_after": "review_before_future_dispatch_or_source_change",
        "revocation_status": "not_revoked",
        "quarantine_status": "not_quarantined",
        "receipt_hash": "example_hash_computed_in_real_receipt",
        "target_world": example.target_world,
        "dispatch_is_allowed": False,
        "preview_ready_means_displayable_not_executable": True,
    }
    return receipt


def _recommended_lane_record(lane: RecommendedLane) -> dict[str, Any]:
    return {
        "lane_id": lane.lane_id,
        "title": lane.title,
        "priority": lane.priority,
        "why_next": lane.why_next,
        "hard_boundary": lane.hard_boundary,
    }


def build_package_preview_receipt_contract(
    *,
    repo_root: str | Path = ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    evidence_sources = [_source_record(source, repo_root=repo_root) for source in EVIDENCE_SOURCES]
    examples = [_example_record(example) for example in EXAMPLE_PREVIEWS]
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": "package_preview_receipt_contract",
        "generated_at": generated_at,
        **NO_AUTHORITY_FLAGS,
        "contract_status": "deterministic_package_preview_receipt_metadata_only",
        "operator_summary": (
            "OpenClaw now has a deterministic receipt grammar proving that a mission package was compiled, "
            "bounded, checked, and displayable without dispatching it."
        ),
        "core_doctrine": {
            "model_is_actor": True,
            "agent_is_character": True,
            "package_is_deterministic_mission_payload": True,
            "package_preview_is_not_dispatch": True,
            "package_preview_is_not_approval": True,
            "package_preview_is_not_execution": True,
            "package_preview_does_not_grant_tools": True,
            "package_preview_does_not_grant_model_access": True,
            "package_preview_does_not_write_canonical_memory": True,
            "package_preview_does_not_authorize_account_or_send_submit_approval": True,
        },
        "evidence_sources": evidence_sources,
        "receipt_types": [
            {
                "receipt_type": receipt_type,
                "description": _receipt_type_description(receipt_type),
                "runtime_dispatch_allowed": False,
            }
            for receipt_type in RECEIPT_TYPES
        ],
        "preview_states": [
            {
                "preview_state": state,
                "description": _preview_state_description(state),
                "preview_ready_means_displayable_not_executable": state == "PREVIEW_READY",
                "runtime_dispatch_allowed": False,
            }
            for state in PREVIEW_STATES
        ],
        "package_preview_receipt_schema": {
            "required_fields": list(RECEIPT_FIELDS),
            "hard_defaults": {
                "runtime_dispatch_allowed": False,
                "model_call_allowed": False,
                "tool_execution_allowed": False,
                "agent_activation_allowed": False,
                "queue_execution_allowed": False,
                "account_access_allowed": False,
                "send_submit_approval_allowed": False,
                "raw_body_included": False,
                "authority_level_granted": "preview_only",
            },
            "natural_language_claim_counts_as_proof": False,
            "missing_required_display_field_result": "PACKAGE_PREVIEW_INCOMPLETE",
            "unsafe_or_unknown_result": "PACKAGE_PREVIEW_UNKNOWN_FAIL_CLOSED",
        },
        "package_field_completeness_model": {
            "required_for_display": list(DISPLAY_REQUIRED_FIELDS),
            "required_for_future_dispatch": list(FUTURE_DISPATCH_REQUIRED_FIELDS),
            "display_missing_result": "fail_closed_or_render_incomplete",
            "dispatch_missing_result": "preview_may_render_but_dispatch_blocked_future_gated",
            "preview_ready_means_displayable_not_executable": True,
        },
        "required_source_checks": {
            "source_contracts": [source.source_id for source in EVIDENCE_SOURCES],
            "reference_by_id_or_path_only": True,
            "broad_raw_body_import_allowed": False,
        },
        "context_inclusion_exclusion_policy": {
            "included_context_must_be_reference_based": True,
            "raw_private_bodies_blocked_by_default": True,
            "credential_account_session_data_always_blocked": True,
            "external_model_context_must_be_redacted_and_gated": True,
            "operator_memory_is_candidate_context_not_proof": True,
            "worker_output_is_receipt_candidate_not_truth": True,
            "stale_or_revoked_candidates_are_excluded": True,
            "context_exclusions_must_be_visible_in_receipt": True,
            "blocked_context": [
                "raw private bodies",
                "credentials/tokens/cookies/API keys",
                "browser sessions",
                "account portals",
                "raw Gmail/calendar/Coupa/Telegram bodies",
                "unredacted client/legal/finance/private documents",
                "external retained memory",
                "hidden memory",
            ],
        },
        "authority_boundary_policy": {
            "blocked_now": list(BLOCKED_AUTHORITIES),
            "all_examples_grant_preview_only": True,
            "package_or_actor_self_authorization_allowed": False,
            "operator_final_authority": True,
        },
        "example_package_preview_receipts": examples,
        "revocation_quarantine_policy": {
            "quarantine_triggers": list(QUARANTINE_TRIGGERS),
            "revocation_triggers": list(REVOCATION_TRIGGERS),
            "missing_or_malformed_receipt_result": "PACKAGE_PREVIEW_QUARANTINED",
            "quarantine_is_non_destructive": True,
            "revocation_blocks_future_dispatch": True,
        },
        "mission_control_surface_guidance": {
            "package_preview_card": [
                "mission",
                "actor/agent",
                "package type",
                "preview status",
                "authority boundary",
                "included context count",
                "excluded context count",
                "missing proof",
                "gates",
                "stop conditions",
                "receipt requirements",
            ],
            "package_detail_layers": [
                "Layer 1: operator orientation",
                "Layer 2: machine contract/proof",
                "Layer 3: package/detour/future action path",
            ],
            "dossier_integration": [
                "package types supported",
                "package preview available",
                "required gates",
                "required receipts",
                "future-gated package target",
            ],
            "world_integration": [
                "package previews ready for that world",
                "blocked action boundaries",
                "what proof moves a helm lane into a world lane",
            ],
            "hide_or_block": [
                "live dispatch buttons",
                "model launch controls",
                "tool execution controls",
                "browser/OAuth/account prompts",
                "Gmail/calendar/Coupa/Telegram controls",
                "send/submit/approval controls",
                "raw private context",
                "credentials/tokens",
                "fake confidence percentages",
                "agent chose its own package claims",
            ],
        },
        "stable_map_integration": {
            "contract_generated_as_read_model": True,
            "summary_included_in_stable_map_bundle_now": False,
            "reason_not_included_now": "avoid reopening stable-map/sync residue in this contract lane",
            "safe_summary_to_include_next": {
                "contract_id": "package_preview_receipt_contract",
                "receipt_types_count": len(RECEIPT_TYPES),
                "example_package_previews_count": len(EXAMPLE_PREVIEWS),
                "preview_ready_vs_future_gated_count": {
                    "preview_ready_or_compiled": sum(1 for example in examples if example["preview_status"] == "PACKAGE_PREVIEW_COMPILED"),
                    "future_gated_or_blocked": sum(1 for example in examples if example["preview_status"] != "PACKAGE_PREVIEW_COMPILED"),
                },
                "current_dispatch_authority": False,
                "next_recommended_lane": "tool_adapter_receipt_v0",
            },
        },
        "recommended_next_lanes": [_recommended_lane_record(lane) for lane in RECOMMENDED_NEXT_LANES],
        "machine_proof": {
            "schema_fields_count": len(RECEIPT_FIELDS),
            "receipt_types_count": len(RECEIPT_TYPES),
            "preview_states_count": len(PREVIEW_STATES),
            "example_count": len(EXAMPLE_PREVIEWS),
            "all_examples_preview_only": all(example["runtime_dispatch_allowed"] is False for example in examples),
            "all_examples_no_raw_body": all(example["raw_body_included"] is False for example in examples),
            "all_examples_no_model_call": all(example["model_call_allowed"] is False for example in examples),
            "all_examples_no_tool_execution": all(example["tool_execution_allowed"] is False for example in examples),
            "content_hash": None,
        },
    }
    payload["machine_proof"]["content_hash"] = _content_hash(payload)
    return payload


def format_operator_markdown(payload: dict[str, Any]) -> str:
    examples = payload["example_package_preview_receipts"]
    lines = [
        "# Package Preview Receipt Contract v0",
        "",
        "## Summary",
        "",
        payload["operator_summary"],
        "",
        "## Receipt Grammar",
        "",
        f"- Receipt types: `{len(payload['receipt_types'])}`",
        f"- Preview states: `{len(payload['preview_states'])}`",
        f"- Required fields: `{len(payload['package_preview_receipt_schema']['required_fields'])}`",
        "- `PREVIEW_READY` means displayable, not executable.",
        "- Runtime dispatch, model calls, tool execution, agent activation, queue execution, account access, and send/submit/approval all default to `false`.",
        "",
        "## Example Package Previews",
        "",
    ]
    for example in examples:
        lines.extend(
            [
                f"- `{example['example_id']}`: {example['package_title']} -> `{example['preview_status']}`",
                f"  - actor: `{example['actor_id']}` / model posture: `{example['selected_or_blocked_model_class']}`",
                f"  - blocked: `{', '.join(example['blocked_reasons'])}`",
            ]
        )
    lines.extend(
        [
            "",
            "## Mission Control Guidance",
            "",
            "- Show mission, actor, package type, preview status, authority boundary, included/excluded context counts, missing proof, gates, stop conditions, and receipt requirements.",
            "- Route full inspection into operator orientation, machine proof, and future action path layers.",
            "- Hide live dispatch, model launch, tool execution, browser/OAuth/account prompts, Gmail/calendar/Coupa/Telegram controls, send/submit/approval, raw private context, credentials, fake confidence percentages, and self-authorized package claims.",
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


def export_package_preview_receipt_contract(
    *,
    repo_root: str | Path = ROOT,
    export_root: str | Path = DEFAULT_EXPORT_ROOT,
    generated_at: str | None = None,
) -> PackagePreviewReceiptExportResult:
    payload = build_package_preview_receipt_contract(repo_root=repo_root, generated_at=generated_at)
    root = Path(export_root)
    if not root.is_absolute():
        root = Path(repo_root) / root
    root.mkdir(parents=True, exist_ok=True)
    json_path = root / JSON_EXPORT_NAME
    operator_path = root / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(format_operator_markdown(payload), encoding="utf-8")
    return PackagePreviewReceiptExportResult(
        schema_version=SCHEMA_VERSION,
        json_path=json_path.as_posix(),
        operator_path=operator_path.as_posix(),
        receipt_type_count=len(RECEIPT_TYPES),
        preview_state_count=len(PREVIEW_STATES),
        example_count=len(EXAMPLE_PREVIEWS),
        runtime_dispatch_authority_added=False,
        model_call_authority_added=False,
        tool_execution_authority_added=False,
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export the Package Preview Receipt Contract read-model.")
    parser.add_argument("--repo-root", default=ROOT.as_posix())
    parser.add_argument("--export-root", default=DEFAULT_EXPORT_ROOT.as_posix())
    parser.add_argument("--format", choices=("summary", "json", "operator"), default="operator")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    result = export_package_preview_receipt_contract(
        repo_root=args.repo_root,
        export_root=args.export_root,
    )
    summary = {
        "schema_version": result.schema_version,
        "json_path": result.json_path,
        "operator_path": result.operator_path,
        "receipt_type_count": result.receipt_type_count,
        "preview_state_count": result.preview_state_count,
        "example_count": result.example_count,
        "runtime_dispatch_authority_added": result.runtime_dispatch_authority_added,
        "model_call_authority_added": result.model_call_authority_added,
        "tool_execution_authority_added": result.tool_execution_authority_added,
    }
    if args.format in {"summary", "json"}:
        print(stable_json(summary), end="")
    else:
        print(f"Package Preview Receipt Contract: `{result.schema_version}`")
        print(f"- JSON: `{result.json_path}`")
        print(f"- Operator: `{result.operator_path}`")
    return 0


__all__ = [
    "DISPLAY_REQUIRED_FIELDS",
    "FUTURE_DISPATCH_REQUIRED_FIELDS",
    "JSON_EXPORT_NAME",
    "NO_AUTHORITY_FLAGS",
    "OPERATOR_EXPORT_NAME",
    "PREVIEW_STATES",
    "RECEIPT_FIELDS",
    "RECEIPT_TYPES",
    "SCHEMA_VERSION",
    "build_package_preview_receipt_contract",
    "export_package_preview_receipt_contract",
    "format_operator_markdown",
    "stable_json",
]


if __name__ == "__main__":
    raise SystemExit(main())
