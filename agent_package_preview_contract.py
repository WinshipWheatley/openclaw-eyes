"""Agent Package Preview Contract v0 for OpenClaw.

This read-model defines the complete inspectable package Mission Control can
show before any future agent/model/tool action. It is metadata only: no models,
agents, tools, network calls, browser/OAuth/account surfaces, credentials,
runtime execution, send/submit/approval flows, autonomous routing, or PC
system-drive writes are activated.
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

SCHEMA_VERSION = "agent_package_preview_contract_v0"
JSON_EXPORT_NAME = "agent_package_preview_contract.json"
OPERATOR_EXPORT_NAME = "agent_package_preview_contract_OPERATOR.md"

NO_AUTHORITY_FLAGS = {
    "runtime_authority": False,
    "model_call_authority": False,
    "agent_call_authority": False,
    "tool_execution_authority": False,
    "external_tool_authority": False,
    "credential_authority": False,
    "routing_execution_authority": False,
    "package_send_authority": False,
    "operator_final_authority": True,
    "browser_oauth_account_access_enabled": False,
    "gmail_calendar_coupa_telegram_enabled": False,
    "send_submit_approval_enabled": False,
    "network_execution_enabled": False,
    "runtime_daemon_enabled": False,
    "autonomous_routing_enabled": False,
    "raw_private_body_ingestion_enabled": False,
    "hidden_memory_capture_enabled": False,
    "background_surveillance_enabled": False,
    "pc_c_drive_artifact_write_allowed": False,
    "mission_control_app_authority_added": False,
}

REQUIRED_PACKAGE_FIELDS = (
    "package_id",
    "package_type",
    "proposed_actor_id",
    "proposed_actor_role",
    "proposed_model_class",
    "model_selection_status",
    "task_summary",
    "operator_intent",
    "evidence_sources",
    "included_context_refs",
    "excluded_context_refs",
    "sensitivity_classification",
    "clearance_level",
    "requested_authority",
    "blocked_authority",
    "required_gates",
    "relevant_capabilities",
    "inactive_tool_protocols",
    "expected_outputs",
    "stop_conditions",
    "validation_requirements",
    "future_pre_action_receipts",
    "future_post_action_receipts",
    "mission_control_display_layers",
)

PACKAGE_SECTIONS = (
    "identity_and_routing",
    "task_and_intent",
    "evidence_and_context",
    "sensitivity_and_clearance",
    "authority_and_gates",
    "tools_and_protocols",
    "expected_output_contract",
    "validation_and_stop_conditions",
    "receipts_and_audit",
    "mission_control_display",
)

CURRENT_AUTHORITY_STATES = ("review_only", "inspect_only", "blocked")

MODEL_SELECTION_STATUSES = (
    "recommended_future_eligible",
    "blocked_no_model",
    "human_operator_only",
    "unknown_fail_closed",
)

SENSITIVITY_CLASSES = (
    "public_or_repo_safe",
    "internal_operator_safe",
    "sensitive_private",
    "finance_or_ap_sensitive",
    "protected_access_metadata",
    "client_or_legal_sensitive",
    "credential_or_oauth_related",
    "unknown_fail_closed",
)

BLOCKED_CONTEXT_CATEGORIES = (
    "hidden_memory",
    "broad_filesystem_indexing",
    "private_raw_body_ingestion",
    "credential_or_token_inclusion",
    "browser_or_session_cookies",
    "unredacted_client_legal_finance_private_documents",
    "home_bank_check_remit_sensitive_raw_data",
    "email_calendar_raw_bodies_without_gate",
    "tool_outputs_without_receipts",
)

BLOCKED_ACTIVE_AUTHORITIES = (
    "model_call",
    "agent_activation",
    "tool_execution",
    "browser_or_portal_use",
    "oauth_or_credential_handling",
    "gmail_email_send",
    "calendar_mutation",
    "coupa_submit_or_approval",
    "telegram_send",
    "network_runtime_execution",
    "autonomous_queue_or_planner_builder",
    "package_dispatch",
)

GATE_REQUIREMENTS = (
    "guardian_protected_access_gate",
    "model_selection_policy",
    "agent_identity_actor_router_contract",
    "package_compiler_contract",
    "capability_skill_registry",
    "source_context_gates",
    "operator_approval",
    "future_receipt_logging",
)


@dataclass(frozen=True)
class EvidenceSource:
    source_id: str
    path: str
    role: str


@dataclass(frozen=True)
class PackageSection:
    section_id: str
    purpose: str
    required_fields: tuple[str, ...]
    mission_control_layer: str


@dataclass(frozen=True)
class ExamplePackagePreview:
    package_id: str
    title: str
    proposed_actor_id: str
    proposed_actor_role: str
    package_type: str
    proposed_model_class: str
    model_selection_status: str
    task_summary: str
    operator_intent: str
    included_context_refs: tuple[str, ...]
    excluded_context_refs: tuple[str, ...]
    sensitivity_classification: str
    clearance_level: str
    current_authority: str
    requested_authority: str
    blocked_authority: tuple[str, ...]
    required_gates: tuple[str, ...]
    relevant_capabilities: tuple[str, ...]
    inactive_tool_protocols: tuple[str, ...]
    expected_outputs: tuple[str, ...]
    stop_conditions: tuple[str, ...]


@dataclass(frozen=True)
class RecommendedLane:
    lane_id: str
    title: str
    priority: str
    why_next: str
    hard_boundary: str


@dataclass(frozen=True)
class AgentPackagePreviewExportResult:
    schema_version: str
    json_path: str
    operator_path: str
    package_field_count: int
    package_section_count: int
    example_count: int
    runtime_authority_added: bool
    package_send_authority_added: bool


EVIDENCE_SOURCES = (
    EvidenceSource(
        "agent_platform_alignment",
        "generated/read_models/agent_platform_alignment.json",
        "agent-platform primitive and missing-prerequisite map",
    ),
    EvidenceSource(
        "agent_identity_actor_router_contract",
        "generated/read_models/agent_identity_actor_router_contract.json",
        "actor identities, routing modes, and actor authority boundaries",
    ),
    EvidenceSource(
        "model_selection_policy_contract",
        "generated/read_models/model_selection_policy_contract.json",
        "model class policy, sensitivity defaults, and blocked model uses",
    ),
    EvidenceSource(
        "package_compiler_contract",
        "generated/read_models/package_compiler_contract.json",
        "package schema, boundary validation, receipt, clearance, and capability fields",
    ),
    EvidenceSource(
        "capability_skill_registry_metadata_delta",
        "generated/read_models/capability_skill_registry_metadata_delta.json",
        "capability and skill metadata without execution authority",
    ),
    EvidenceSource(
        "guardian_protected_access_gate_spec",
        "generated/read_models/guardian_protected_access_gate_spec.json",
        "Guardian protected-access and approval boundary posture",
    ),
    EvidenceSource(
        "protected_evidence_reference_receipt",
        "generated/read_models/protected_evidence_reference_receipt.json",
        "protected evidence can be referenced by metadata receipt without exposing private bodies",
    ),
    EvidenceSource(
        "cassandra_email_calendar_delta_detangle",
        "generated/read_models/cassandra_email_calendar_delta_detangle.json",
        "communications/calendar visibility boundary; no send or mutation authority",
    ),
    EvidenceSource(
        "operator_awareness_agent_package_spine",
        "generated/read_models/operator_awareness_agent_package_spine.json",
        "awareness/package preview spine and confidence/detour posture",
    ),
    EvidenceSource(
        "chief_check_engine_diagnostic_package",
        "generated/read_models/chief_check_engine_diagnostic_package.json",
        "Chief check-engine diagnostic package posture",
    ),
)

PACKAGE_SECTION_DEFINITIONS = (
    PackageSection(
        "identity_and_routing",
        "Names the actor, role, model posture, package type, and routing status.",
        ("package_id", "package_type", "proposed_actor_id", "proposed_actor_role", "proposed_model_class", "model_selection_status"),
        "top",
    ),
    PackageSection(
        "task_and_intent",
        "States the operator intent, task summary, why it matters, and non-live boundary.",
        ("task_summary", "operator_intent"),
        "top",
    ),
    PackageSection(
        "evidence_and_context",
        "Shows deterministic references included and excluded without raw private bodies.",
        ("evidence_sources", "included_context_refs", "excluded_context_refs"),
        "middle",
    ),
    PackageSection(
        "sensitivity_and_clearance",
        "Classifies sensitivity, clearance, and fail-closed posture.",
        ("sensitivity_classification", "clearance_level"),
        "middle",
    ),
    PackageSection(
        "authority_and_gates",
        "Separates requested future authority from currently blocked authority and required gates.",
        ("requested_authority", "blocked_authority", "required_gates"),
        "lower",
    ),
    PackageSection(
        "tools_and_protocols",
        "Lists relevant capabilities and protocols as inactive preview metadata only.",
        ("relevant_capabilities", "inactive_tool_protocols"),
        "lower",
    ),
    PackageSection(
        "expected_output_contract",
        "Defines what the actor would eventually return if a later gate allowed action.",
        ("expected_outputs",),
        "lower",
    ),
    PackageSection(
        "validation_and_stop_conditions",
        "Defines deterministic validation requirements and stop conditions.",
        ("validation_requirements", "stop_conditions"),
        "lower",
    ),
    PackageSection(
        "receipts_and_audit",
        "Defines future receipts required before and after any action-capable route.",
        ("future_pre_action_receipts", "future_post_action_receipts"),
        "lower",
    ),
    PackageSection(
        "mission_control_display",
        "Defines top/middle/lower/full inspection layers for the Mac helm.",
        ("mission_control_display_layers",),
        "display",
    ),
)

EXAMPLE_PACKAGE_PREVIEWS = (
    ExamplePackagePreview(
        "example_codex_backend_read_model_implementation",
        "Codex backend read-model implementation package",
        "codex",
        "scoped implementation worker",
        "code_implementation",
        "external_code_worker",
        "recommended_future_eligible",
        "Implement a bounded Repo A read-model contract with tests and generated output.",
        "Add deterministic backend contract code without touching runtime systems.",
        (
            "generated/read_models/package_compiler_contract.json",
            "generated/read_models/model_selection_policy_contract.json",
            "source refs for target files in Repo A",
        ),
        (
            "credentials/OAuth tokens",
            "Mac Mission Control Swift files unless explicitly in lane",
            "private raw data",
            "PC C: drive paths",
        ),
        "public_or_repo_safe",
        "internal_operator_safe",
        "inspect_only",
        "future_gated_scoped_write",
        ("model_call", "agent_activation", "network_runtime_execution", "pc_c_drive_artifact_write"),
        ("package_compiler_contract", "model_selection_policy", "operator_approval", "future_receipt_logging"),
        ("file_read", "file_write_scoped", "test_run", "git_commit"),
        ("model_api", "browser", "oauth", "gmail", "calendar", "coupa", "telegram"),
        ("patch summary", "tests run", "generated JSON/operator output", "commit hash if later allowed"),
        ("stop if scope expands", "stop if credentials/private data appear", "stop if validation fails with design ambiguity"),
    ),
    ExamplePackagePreview(
        "example_gemini_antigravity_refactor_proof",
        "Gemini/Antigravity refactor/proof package",
        "gemini_antigravity",
        "scoped refactor/proof worker",
        "test_authoring",
        "external_fast_worker",
        "recommended_future_eligible",
        "Review or refactor a bounded module and return proof/test feedback.",
        "Use a fast worker only when the package is explicit and low-sensitivity.",
        (
            "target module refs",
            "test refs",
            "package compiler boundary validation refs",
        ),
        (
            "unbounded shell access",
            "out-of-workspace state transfer",
            "credentials/secrets",
            "private raw files",
        ),
        "public_or_repo_safe",
        "internal_operator_safe",
        "review_only",
        "future_gated_scoped_write",
        ("autonomous_tool_execution", "credential_or_oauth_handling", "browser_or_portal_use"),
        ("model_selection_policy", "package_compiler_contract", "operator_approval", "future_receipt_logging"),
        ("file_read", "test_run", "diff_review"),
        ("oauth", "browser", "network_runtime", "send_submit_approval"),
        ("review findings", "bounded patch proposal", "test evidence"),
        ("stop if file boundary is unclear", "stop if task becomes infrastructure administration"),
    ),
    ExamplePackagePreview(
        "example_cassandra_capital_hilton_invoice_review",
        "Cassandra Capital Hilton invoice review package",
        "cassandra",
        "communications and finance/AP review actor",
        "finance_ap_review",
        "local_sensitive",
        "blocked_no_model",
        "Prepare a protected, metadata-only invoice review path for Capital Hilton.",
        "Represent the AP workflow without accessing Coupa, credentials, or private proof bodies.",
        (
            "generated/read_models/operator_threshold_map_contract.json",
            "generated/read_models/protected_evidence_reference_receipt.json",
            "Capital Hilton metadata refs only",
        ),
        (
            "Coupa portal access",
            "raw Excel/PDF proof bodies",
            "bank/check/remit data",
            "credentials/OAuth tokens",
            "approval or submit authority",
        ),
        "finance_or_ap_sensitive",
        "protected_context_required_future_gate",
        "blocked",
        "future_gated_protected_review",
        ("coupa_submit_or_approval", "browser_or_portal_use", "credential_or_oauth_handling", "email_send"),
        (
            "guardian_protected_access_gate",
            "protected_evidence_reference_receipt",
            "model_selection_policy",
            "operator_approval",
            "future_receipt_logging",
        ),
        ("metadata_review", "proof_reference_review"),
        ("coupa", "browser", "oauth", "gmail", "calendar"),
        ("missing proof list", "protected metadata checklist", "safe next non-executing step"),
        ("stop if raw proof body is needed", "stop if approval/submission is requested"),
    ),
    ExamplePackagePreview(
        "example_guardian_protected_evidence_review",
        "Guardian protected evidence review package",
        "guardian",
        "safety/security/protected access actor",
        "protected_access_review",
        "local_sensitive",
        "blocked_no_model",
        "Inspect whether a protected evidence reference is safe to use as metadata.",
        "Keep protected evidence fail-closed until receipts and gates are explicit.",
        (
            "generated/read_models/guardian_protected_access_gate_spec.json",
            "generated/read_models/protected_evidence_reference_receipt.json",
        ),
        (
            "protected raw files",
            "credentials",
            "private body text",
            "browser/session material",
        ),
        "protected_access_metadata",
        "protected_context_required_future_gate",
        "inspect_only",
        "future_gated_protected_context_review",
        ("protected_file_access_without_gate", "credential_or_oauth_handling", "hidden_memory_capture"),
        ("guardian_protected_access_gate", "source_context_gates", "future_receipt_logging"),
        ("metadata_inspection", "gate_review"),
        ("oauth", "browser", "filesystem_broad_index", "network_runtime"),
        ("gate finding", "allowed metadata refs", "blocked private refs"),
        ("stop if raw protected content is required", "stop if gate status is unknown"),
    ),
    ExamplePackagePreview(
        "example_niles_struna_tracking_creative",
        "Niles Struna tracking/creative package",
        "niles",
        "music/art/producer actor",
        "struna_development",
        "external_multimodal",
        "recommended_future_eligible",
        "Organize Struna creative/workflow tracking without business authority.",
        "Let Niles reason about music/art context while preserving implementation boundaries.",
        (
            "generated/read_models/operator_nested_lane_mission_package_spine.json",
            "generated/read_models/cross_repo_awareness_matrix.json",
            "Struna metadata refs",
        ),
        (
            "raw unreleased audio unless explicitly approved",
            "legal/finance documents",
            "credentials",
            "distribution or publishing account access",
        ),
        "internal_operator_safe",
        "internal_operator_safe",
        "review_only",
        "future_gated_creative_review",
        ("account_access", "publishing_or_distribution_action", "credential_or_oauth_handling"),
        ("model_selection_policy", "source_context_gates", "operator_approval"),
        ("creative_review", "metadata_classification"),
        ("browser", "oauth", "distribution_portal", "network_runtime"),
        ("creative tracking recommendations", "missing metadata list", "safe next lane"),
        ("stop if rights/source sensitivity is unclear", "stop if execution or account access is requested"),
    ),
    ExamplePackagePreview(
        "example_hermes_architecture_review",
        "Hermes architecture review package",
        "hermes",
        "architecture/doctrine/systems review actor",
        "architecture_review",
        "external_deep_reasoner",
        "recommended_future_eligible",
        "Review system coherence across Operator System contracts.",
        "Use Hermes for big-picture doctrine and system map coherence after packet sanitization.",
        (
            "generated/read_models/agent_platform_alignment.json",
            "generated/read_models/operator_mission_priority_helm_declutter.json",
            "generated/read_models/steel_thread_lane_template_registry.json",
        ),
        (
            "raw private chat history",
            "credentials",
            "client/legal/finance private bodies",
        ),
        "internal_operator_safe",
        "internal_operator_safe",
        "review_only",
        "future_gated_architecture_review",
        ("hidden_memory_capture", "network_runtime_execution", "self_authorized_routing"),
        ("model_selection_policy", "package_compiler_contract", "operator_approval"),
        ("doctrine_review", "architecture_review"),
        ("browser", "oauth", "gmail", "calendar", "coupa", "telegram"),
        ("coherence findings", "risks", "next contract recommendations"),
        ("stop if private raw sources are required", "stop if package tries to add authority"),
    ),
    ExamplePackagePreview(
        "example_chief_check_engine_diagnostic",
        "Chief check-engine diagnostic package",
        "chief",
        "coordination and system/workbench diagnostic actor",
        "safety_review",
        "local_reasoning",
        "recommended_future_eligible",
        "Diagnose current Check Engine posture from bounded read-model proof.",
        "Chief gets an inspect-only package for system/workbench reliability, not repair authority.",
        (
            "generated/read_models/chief_check_engine_diagnostic_package.json",
            "generated/read_models/system_health_lights_taxonomy.json",
            "generated/read_models/sync_health.json",
        ),
        (
            "delete/cleanup authority",
            "remount credentials",
            "raw logs unless approved",
            "PC C: drive writes",
        ),
        "internal_operator_safe",
        "internal_operator_safe",
        "inspect_only",
        "future_gated_diagnostic_review",
        ("cleanup_delete", "remount", "credential_or_oauth_handling", "runtime_repair"),
        ("package_compiler_contract", "model_selection_policy", "operator_approval", "future_receipt_logging"),
        ("read_model_inspection", "diagnostic_summary"),
        ("shell_repair", "remount", "credential_store", "network_runtime"),
        ("diagnosis", "safe next step", "operator action required or not"),
        ("stop if repair is requested", "stop if raw logs or credentials are required"),
    ),
)

RECOMMENDED_NEXT_LANES = (
    RecommendedLane(
        "agent_memory_scope_contract_v0",
        "Agent Memory Scope Contract v0",
        "P1",
        "Package previews need a deterministic policy for which memory/read-model surfaces each actor may receive.",
        "metadata only; no hidden memory capture or broad indexing",
    ),
    RecommendedLane(
        "tool_protocol_adapter_registry_v0",
        "Tool Protocol Adapter Registry v0",
        "P1",
        "Relevant capabilities are now previewed but need an adapter registry before any future tool gate can exist.",
        "descriptive only; no plugin/tool activation",
    ),
    RecommendedLane(
        "model_selection_receipt_v0",
        "Model Selection Receipt v0",
        "P2",
        "Future package previews need immutable records of model posture decisions.",
        "receipt schema only; no model call",
    ),
    RecommendedLane(
        "mission_control_actor_routing_surface_v0",
        "Mission Control Actor Routing Surface v0",
        "P2",
        "The Mac helm can render package preview layers once the contract is available in the stable map.",
        "read-only UI lane; no backend command authority",
    ),
    RecommendedLane(
        "package_preview_receipt_v0",
        "Package Preview Receipt v0",
        "P3",
        "Preview inspection and future package export need receipts before any action-capable route.",
        "receipt metadata only; no dispatch",
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


def _read_json_if_present(repo_root: str | Path, relative_path: str) -> dict[str, Any] | None:
    path = Path(repo_root) / relative_path
    if not path.is_file():
        return None
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    if isinstance(loaded, dict):
        return loaded
    return None


def _source_record(source: EvidenceSource, *, repo_root: str | Path) -> dict[str, Any]:
    payload = _read_json_if_present(repo_root, source.path)
    return {
        "source_id": source.source_id,
        "path": source.path,
        "role": source.role,
        "present": payload is not None,
        "schema_version": payload.get("schema_version") if payload else None,
        "raw_private_body_imported": False,
        "credentials_or_secrets_imported": False,
        "authority_granted_by_source_presence": False,
    }


def _section_record(section: PackageSection) -> dict[str, Any]:
    return {
        "section_id": section.section_id,
        "purpose": section.purpose,
        "required_fields": list(section.required_fields),
        "mission_control_layer": section.mission_control_layer,
    }


def _example_record(example: ExamplePackagePreview) -> dict[str, Any]:
    return {
        "package_id": example.package_id,
        "title": example.title,
        "package_type": example.package_type,
        "proposed_actor_id": example.proposed_actor_id,
        "proposed_actor_role": example.proposed_actor_role,
        "proposed_model_class": example.proposed_model_class,
        "model_selection_status": example.model_selection_status,
        "task_summary": example.task_summary,
        "operator_intent": example.operator_intent,
        "evidence_sources": list(example.included_context_refs),
        "included_context_refs": list(example.included_context_refs),
        "excluded_context_refs": list(example.excluded_context_refs),
        "sensitivity_classification": example.sensitivity_classification,
        "clearance_level": example.clearance_level,
        "current_authority": example.current_authority,
        "requested_authority": example.requested_authority,
        "blocked_authority": list(example.blocked_authority),
        "required_gates": list(example.required_gates),
        "relevant_capabilities": list(example.relevant_capabilities),
        "inactive_tool_protocols": list(example.inactive_tool_protocols),
        "expected_outputs": list(example.expected_outputs),
        "stop_conditions": list(example.stop_conditions),
        "validation_requirements": [
            "package schema validates",
            "all context refs are deterministic refs or receipts",
            "sensitivity classification is explicit",
            "blocked authority remains inactive",
            "required gates are listed before future action",
        ],
        "future_pre_action_receipts": [
            "package preview receipt",
            "model selection receipt",
            "actor/router receipt",
            "Guardian gate receipt if required",
            "operator approval receipt if action-capable",
        ],
        "future_post_action_receipts": [
            "result receipt",
            "validation receipt",
            "artifact manifest receipt",
            "blocked/failed stop-condition receipt if incomplete",
        ],
        "mission_control_display_layers": {
            "top": "what would be sent, to whom, and why",
            "middle": "what context/evidence is included and excluded",
            "lower": "gates, authority, proof, and receipts",
            "full_inspection": "complete package preview payload",
        },
        "live_dispatch_allowed": False,
        "model_call_allowed": False,
        "agent_activation_allowed": False,
        "tool_execution_allowed": False,
    }


def _recommended_lane_record(lane: RecommendedLane) -> dict[str, Any]:
    return {
        "lane_id": lane.lane_id,
        "title": lane.title,
        "priority": lane.priority,
        "why_next": lane.why_next,
        "hard_boundary": lane.hard_boundary,
    }


def build_agent_package_preview_contract(
    *,
    repo_root: str | Path = ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    evidence_sources = [_source_record(source, repo_root=repo_root) for source in EVIDENCE_SOURCES]
    sections = [_section_record(section) for section in PACKAGE_SECTION_DEFINITIONS]
    examples = [_example_record(example) for example in EXAMPLE_PACKAGE_PREVIEWS]
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": "agent_package_preview_contract",
        "generated_at": generated_at,
        **NO_AUTHORITY_FLAGS,
        "contract_status": "deterministic_package_preview_metadata_only",
        "operator_summary": (
            "OpenClaw now has a deterministic package-preview contract. Mission Control can show what would be "
            "sent, to whom, why, which context is included/excluded, what gates are required, and what remains "
            "blocked before any future model, agent, tool, or runtime action."
        ),
        "evidence_sources": evidence_sources,
        "package_preview_schema": {
            "schema_name": "AgentPackagePreview",
            "required_fields": list(REQUIRED_PACKAGE_FIELDS),
            "sections": list(PACKAGE_SECTIONS),
            "current_authority_states_allowed": list(CURRENT_AUTHORITY_STATES),
            "model_selection_statuses": list(MODEL_SELECTION_STATUSES),
            "unknown_required_field_fails_closed": True,
            "raw_private_bodies_allowed_by_default": False,
            "package_preview_is_dispatch": False,
        },
        "required_package_fields": list(REQUIRED_PACKAGE_FIELDS),
        "package_sections": sections,
        "actor_binding_policy": {
            "source_contract": "agent_identity_actor_router_contract",
            "proposed_actor_id_required": True,
            "proposed_actor_role_required": True,
            "unknown_actor_result": "blocked",
            "actor_may_not_self_assign_authority": True,
            "operator_final_authority": True,
        },
        "model_binding_policy": {
            "source_contract": "model_selection_policy_contract",
            "proposed_model_class_required": True,
            "model_selection_status_required": True,
            "unknown_model_class_result": "blocked_no_model",
            "model_may_not_self_select": True,
            "model_call_allowed_now": False,
            "blocked_no_model_is_valid": True,
        },
        "context_inclusion_policy": {
            "allowed_context_forms": [
                "deterministic read-model refs",
                "receipt IDs",
                "source cards",
                "context packet refs",
                "metadata-only protected evidence refs after gate",
            ],
            "raw_private_bodies_allowed_by_default": False,
            "must_include_context_excluded_list": True,
            "must_use_refs_not_secret_payloads": True,
        },
        "context_exclusion_policy": {
            "blocked_categories": list(BLOCKED_CONTEXT_CATEGORIES),
            "protected_metadata_exception_requires": [
                "protected evidence reference receipt",
                "Guardian gate",
                "metadata-only reference",
                "no raw private body",
            ],
        },
        "sensitivity_classification_policy": {
            "sensitivity_classes": list(SENSITIVITY_CLASSES),
            "default_for_unknown": "unknown_fail_closed",
            "sensitive_private_defaults_to": "blocked_or_local_private_future_gate",
            "finance_ap_defaults_to": "blocked_until_proof_and_guardian_gate",
            "credential_or_oauth_defaults_to": "blocked",
            "classification_required_before_future_action": True,
        },
        "authority_request_policy": {
            "valid_current_authority": list(CURRENT_AUTHORITY_STATES),
            "requested_future_authority_must_be_inactive": True,
            "blocked_authority_must_be_explicit": True,
            "active_authority_never_from_prompt_text": True,
            "blocked_active_authorities": list(BLOCKED_ACTIVE_AUTHORITIES),
        },
        "gate_requirements": {
            "known_gate_ids": list(GATE_REQUIREMENTS),
            "gate_map": {
                "guardian_protected_access_gate": "required for protected/sensitive/approval-adjacent packages",
                "model_selection_policy": "required for proposed model class and blocked_no_model posture",
                "agent_identity_actor_router_contract": "required for proposed actor identity and routing mode",
                "package_compiler_contract": "required for schema, boundary, and validation requirements",
                "capability_skill_registry": "required before capability/tool metadata can be trusted",
                "source_context_gates": "required before context refs can be included",
                "operator_approval": "required before any future action-capable package",
                "future_receipt_logging": "required before and after any future action",
            },
        },
        "tool_protocol_preview_policy": {
            "capabilities_may_be_listed": True,
            "all_tools_inactive_by_default": True,
            "tool_protocols_are_metadata_only": True,
            "must_not_imply": [
                "browser authority",
                "OAuth authority",
                "Gmail authority",
                "calendar mutation authority",
                "Coupa authority",
                "Telegram authority",
                "network/runtime authority",
            ],
        },
        "receipt_requirements": {
            "future_pre_action_receipts": [
                "package preview receipt",
                "actor/router decision receipt",
                "model selection receipt",
                "sensitivity classification receipt",
                "context inclusion/exclusion receipt",
                "Guardian gate receipt when applicable",
                "capability/tool adapter receipt when applicable",
                "operator approval receipt for action-capable packages",
            ],
            "future_post_action_receipts": [
                "result receipt",
                "validation receipt",
                "artifact manifest/hash receipt",
                "blocked/failed stop-condition receipt",
            ],
            "natural_language_success_claim_counts_as_proof": False,
        },
        "confidence_policy": {
            "show_confidence_only_when": "uncertainty changes the operator's next safe move",
            "hide_when": "preview is deterministic and no action is being dispatched",
            "unknown_context": "UNKNOWN_FAIL_CLOSED",
            "missing_gate": "blocked_or_detour_required",
            "do_not_display_fake_model_availability": True,
        },
        "mission_control_surface_guidance": {
            "top_layer": "what would be sent, to whom, and why",
            "middle_layer": "what context/evidence is included and excluded",
            "lower_layer": "gates, authority, proof, and receipts",
            "full_inspection": "complete package preview payload",
            "do_not_present_as": [
                "live agent presence",
                "fake model availability",
                "execution button",
                "command path",
                "generic backend table",
                "confidence theater",
            ],
        },
        "example_package_previews": examples,
        "blocked_package_states": [
            {
                "state_id": state_id,
                "current_result": "blocked",
                "live_dispatch_allowed": False,
            }
            for state_id in (
                "missing_required_package_field",
                "unknown_actor",
                "unknown_model_class",
                "unknown_sensitivity",
                "raw_private_body_included",
                "credential_or_token_requested",
                "active_tool_protocol_requested",
                "future_authority_marked_active",
                "missing_required_gate",
                "missing_required_receipt",
                "operator_approval_required_but_absent",
            )
        ],
        "recommended_next_lanes": [_recommended_lane_record(lane) for lane in RECOMMENDED_NEXT_LANES],
        "machine_proof": {
            "source_read_models_present": {source["source_id"]: source["present"] for source in evidence_sources},
            "required_package_fields": list(REQUIRED_PACKAGE_FIELDS),
            "package_sections": list(PACKAGE_SECTIONS),
            "example_package_ids": [item["package_id"] for item in examples],
            "raw_private_bodies_included": False,
            "credentials_or_secrets_included": False,
            "runtime_activation_added": False,
            "model_calls_added": False,
            "agent_activation_added": False,
            "tool_execution_added": False,
            "content_hash": None,
        },
    }
    payload["machine_proof"]["content_hash"] = _content_hash(payload)
    return payload


def format_agent_package_preview_contract(payload: dict[str, Any]) -> str:
    lines = [
        "# Agent Package Preview Contract v0",
        "",
        "## Operator Summary",
        payload["operator_summary"],
        "",
        "## Package Preview Layers",
    ]
    guidance = payload["mission_control_surface_guidance"]
    lines.append(f"- Top layer: {guidance['top_layer']}")
    lines.append(f"- Middle layer: {guidance['middle_layer']}")
    lines.append(f"- Lower layer: {guidance['lower_layer']}")
    lines.append(f"- Full inspection: {guidance['full_inspection']}")
    lines.extend(["", "## Required Package Fields"])
    for field in payload["required_package_fields"]:
        lines.append(f"- `{field}`")
    lines.extend(["", "## Example Package Previews"])
    for example in payload["example_package_previews"]:
        lines.append(
            f"- `{example['package_id']}`: {example['title']} -> actor `{example['proposed_actor_id']}`, "
            f"model `{example['proposed_model_class']}`, authority `{example['current_authority']}`."
        )
    lines.extend(["", "## Context And Sensitivity Boundary"])
    lines.append("- Include refs, receipts, source cards, and context packet refs; do not include raw private bodies by default.")
    for category in payload["context_exclusion_policy"]["blocked_categories"]:
        lines.append(f"- Block `{category}`.")
    lines.extend(["", "## Authority Boundary"])
    for key, value in NO_AUTHORITY_FLAGS.items():
        lines.append(f"- `{key}`: `{str(value).lower()}`")
    lines.extend(["", "## Next Lanes"])
    for lane in payload["recommended_next_lanes"]:
        lines.append(f"- `{lane['lane_id']}` ({lane['priority']}): {lane['title']}")
    return "\n".join(lines).rstrip() + "\n"


def export_agent_package_preview_contract(
    *,
    repo_root: str | Path = ROOT,
    export_root: str | Path = DEFAULT_EXPORT_ROOT,
    generated_at: str | None = None,
) -> AgentPackagePreviewExportResult:
    payload = build_agent_package_preview_contract(repo_root=repo_root, generated_at=generated_at)
    root = Path(export_root)
    if not root.is_absolute():
        root = Path(repo_root) / root
    root.mkdir(parents=True, exist_ok=True)
    json_path = root / JSON_EXPORT_NAME
    operator_path = root / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(format_agent_package_preview_contract(payload), encoding="utf-8")
    return AgentPackagePreviewExportResult(
        schema_version=payload["schema_version"],
        json_path=json_path.as_posix(),
        operator_path=operator_path.as_posix(),
        package_field_count=len(payload["required_package_fields"]),
        package_section_count=len(payload["package_sections"]),
        example_count=len(payload["example_package_previews"]),
        runtime_authority_added=bool(payload["runtime_authority"]),
        package_send_authority_added=bool(payload["package_send_authority"]),
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export Agent Package Preview Contract read-model.")
    parser.add_argument("--repo-root", default=ROOT.as_posix())
    parser.add_argument("--export-root", default=DEFAULT_EXPORT_ROOT.as_posix())
    parser.add_argument("--format", choices=("summary", "json", "operator"), default="summary")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    result = export_agent_package_preview_contract(
        repo_root=args.repo_root,
        export_root=args.export_root,
    )
    if args.format == "json":
        print(stable_json(build_agent_package_preview_contract(repo_root=args.repo_root)), end="")
    elif args.format == "operator":
        payload = build_agent_package_preview_contract(repo_root=args.repo_root)
        print(format_agent_package_preview_contract(payload), end="")
    else:
        print(
            stable_json(
                {
                    "schema_version": result.schema_version,
                    "json_path": result.json_path,
                    "operator_path": result.operator_path,
                    "package_field_count": result.package_field_count,
                    "package_section_count": result.package_section_count,
                    "example_count": result.example_count,
                    "runtime_authority_added": result.runtime_authority_added,
                    "package_send_authority_added": result.package_send_authority_added,
                }
            ),
            end="",
        )
    return 0


__all__ = [
    "CURRENT_AUTHORITY_STATES",
    "JSON_EXPORT_NAME",
    "NO_AUTHORITY_FLAGS",
    "OPERATOR_EXPORT_NAME",
    "PACKAGE_SECTIONS",
    "REQUIRED_PACKAGE_FIELDS",
    "SCHEMA_VERSION",
    "SENSITIVITY_CLASSES",
    "build_agent_package_preview_contract",
    "export_agent_package_preview_contract",
    "format_agent_package_preview_contract",
    "main",
    "stable_json",
]


if __name__ == "__main__":
    raise SystemExit(main())
