"""Model Selection Policy Contract v0 for OpenClaw.

This read-model defines deterministic model-selection policy metadata before
any actor/package can route to a real model. It recommends model classes and
blocking posture only. It does not call models, activate agents, run tools,
open network surfaces, handle credentials, mutate accounts, or create runtime
authority.
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

SCHEMA_VERSION = "model_selection_policy_contract_v0"
JSON_EXPORT_NAME = "model_selection_policy_contract.json"
OPERATOR_EXPORT_NAME = "model_selection_policy_contract_OPERATOR.md"

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

ACTOR_IDS = (
    "operator_winship",
    "chief",
    "guardian",
    "cassandra",
    "hermes",
    "niles",
    "codex",
    "gemini_antigravity",
)

PACKAGE_TYPES = (
    "code_implementation",
    "test_authoring",
    "architecture_review",
    "doctrine_review",
    "safety_review",
    "protected_access_review",
    "communications_review",
    "finance_ap_review",
    "music_creative_review",
    "struna_development",
    "mission_control_ux",
    "client_system_build",
    "legal_sensitive_review",
    "credential_or_oauth_related",
    "browser_or_portal_related",
)

SENSITIVITY_LEVELS = (
    "public_or_repo_safe",
    "internal_operator_safe",
    "sensitive_private",
    "client_or_legal_sensitive",
    "finance_or_ap_sensitive",
    "protected_access_metadata",
    "credential_or_oauth_related",
    "unknown_fail_closed",
)

NO_AUTHORITY_FLAGS = {
    "runtime_authority": False,
    "model_call_authority": False,
    "external_model_authority": False,
    "local_model_authority": False,
    "tool_execution_authority": False,
    "credential_authority": False,
    "routing_execution_authority": False,
    "operator_final_authority": True,
    "browser_oauth_account_access_enabled": False,
    "gmail_calendar_coupa_telegram_enabled": False,
    "send_submit_approval_enabled": False,
    "network_execution_enabled": False,
    "runtime_daemon_enabled": False,
    "autonomous_routing_enabled": False,
    "hidden_memory_capture_enabled": False,
    "background_surveillance_enabled": False,
    "pc_c_drive_artifact_write_allowed": False,
    "mission_control_app_authority_added": False,
}

BLOCKED_MODEL_USES = (
    (
        "email_send",
        "Sending email is blocked; Cassandra communication work remains review/visibility until a later gate.",
    ),
    (
        "calendar_mutation",
        "Calendar mutation is blocked; calendar work may be reviewed only through approved metadata.",
    ),
    (
        "browser_coupa_portal_use",
        "Browser, Coupa, portal, and account flows are blocked before explicit protected-access gates.",
    ),
    (
        "credential_or_oauth_handling",
        "Credentials, OAuth tokens, secrets, and account setup cannot be handled by model selection.",
    ),
    (
        "protected_file_access_without_gate",
        "Protected files or private bodies cannot be exposed without Guardian/protected-context proof.",
    ),
    (
        "broad_filesystem_indexing",
        "Broad filesystem indexing is blocked; source inventories must stay bounded and approved.",
    ),
    (
        "hidden_memory_capture",
        "Hidden memory capture is blocked; memory surfaces must be explicit and receipt-backed.",
    ),
    (
        "surveillance_background_monitoring",
        "Background surveillance or always-on monitoring is not authorized by this contract.",
    ),
    (
        "autonomous_tool_execution",
        "Autonomous tool execution is blocked; model selection is metadata-only.",
    ),
    (
        "self_authorized_routing",
        "No model or actor may choose its own authority, clearance, workspace, or tool set.",
    ),
    (
        "external_model_sensitive_data_without_gate",
        "External model use on sensitive/private/protected data is blocked without explicit Operator and Guardian gates.",
    ),
)


@dataclass(frozen=True)
class EvidenceSource:
    source_id: str
    path: str
    role: str


@dataclass(frozen=True)
class ModelClassPolicy:
    model_class_id: str
    display_name: str
    intended_use: str
    suitable_package_types: tuple[str, ...]
    unsuitable_package_types: tuple[str, ...]
    sensitivity_allowed: tuple[str, ...]
    current_authority: str
    future_eligibility: str
    required_gates: tuple[str, ...]
    blocked_uses: tuple[str, ...]
    notes_for_mission_control: str


@dataclass(frozen=True)
class ActorModelPolicy:
    actor_id: str
    preferred_model_classes: tuple[str, ...]
    allowed_current_model_classes: tuple[str, ...]
    future_eligible_model_classes: tuple[str, ...]
    blocked_model_classes: tuple[str, ...]
    reason: str
    requires_operator_preview: bool
    requires_guardian_gate: bool


@dataclass(frozen=True)
class PackageTypeModelPolicy:
    package_type: str
    preferred_model_classes: tuple[str, ...]
    allowed_current_model_classes: tuple[str, ...]
    future_eligible_model_classes: tuple[str, ...]
    blocked_model_classes: tuple[str, ...]
    sensitivity_default: str
    required_inputs: tuple[str, ...]
    requires_operator_preview: bool
    requires_guardian_gate: bool
    safe_default_result: str
    reason: str


@dataclass(frozen=True)
class RecommendedLane:
    lane_id: str
    title: str
    priority: str
    why_next: str
    hard_boundary: str


@dataclass(frozen=True)
class ModelSelectionPolicyExportResult:
    schema_version: str
    json_path: str
    operator_path: str
    model_class_count: int
    actor_policy_count: int
    package_type_policy_count: int
    runtime_authority_added: bool
    model_call_authority_added: bool


EVIDENCE_SOURCES = (
    EvidenceSource(
        "agent_platform_alignment",
        "generated/read_models/agent_platform_alignment.json",
        "platform primitive/gap map that identified model-selection policy as a missing prerequisite",
    ),
    EvidenceSource(
        "agent_identity_actor_router_contract",
        "generated/read_models/agent_identity_actor_router_contract.json",
        "known actor identities, routing modes, package preview requirements, and actor authority boundaries",
    ),
    EvidenceSource(
        "package_compiler_contract",
        "generated/read_models/package_compiler_contract.json",
        "package schema, deterministic boundary validation, clearance, capability, and receipt requirements",
    ),
    EvidenceSource(
        "operator_workbench_actor_host_registry",
        "generated/read_models/operator_workbench_actor_host_registry.json",
        "workbench/actor host metadata and conservative autonomy levels",
    ),
    EvidenceSource(
        "capability_skill_registry_metadata_delta",
        "generated/read_models/capability_skill_registry_metadata_delta.json",
        "capability/skill metadata; descriptive only, not execution authority",
    ),
    EvidenceSource(
        "guardian_protected_access_gate_spec",
        "generated/read_models/guardian_protected_access_gate_spec.json",
        "protected access and authority gate posture",
    ),
    EvidenceSource(
        "protected_evidence_reference_receipt",
        "generated/read_models/protected_evidence_reference_receipt.json",
        "protected proof can be referenced by receipt without exposing private bodies",
    ),
    EvidenceSource(
        "cassandra_email_calendar_delta_detangle",
        "generated/read_models/cassandra_email_calendar_delta_detangle.json",
        "Cassandra email/calendar visibility and mutation boundary",
    ),
)

MODEL_CLASS_POLICIES = (
    ModelClassPolicy(
        "local_small_fast",
        "Local Small Fast",
        "Fast local/private triage, summarization, low-risk classification, and draft wording.",
        (
            "test_authoring",
            "doctrine_review",
            "music_creative_review",
            "mission_control_ux",
        ),
        (
            "legal_sensitive_review",
            "credential_or_oauth_related",
            "protected_access_review",
        ),
        ("public_or_repo_safe", "internal_operator_safe"),
        "recommendation_only_no_local_model_call",
        "future_eligible_after_local_model_inventory_and_receipts",
        (
            "model inventory receipt",
            "package preview",
            "sensitivity classification",
            "result receipt",
        ),
        ("credential_or_oauth_handling", "autonomous_tool_execution", "hidden_memory_capture"),
        "Use as a future low-latency local/private candidate; do not imply it is installed or callable now.",
    ),
    ModelClassPolicy(
        "local_reasoning",
        "Local Reasoning",
        "Private deeper reasoning on internal OpenClaw context when external exposure is not justified.",
        (
            "architecture_review",
            "doctrine_review",
            "safety_review",
            "client_system_build",
        ),
        ("credential_or_oauth_related", "browser_or_portal_related"),
        ("public_or_repo_safe", "internal_operator_safe", "sensitive_private"),
        "recommendation_only_no_local_model_call",
        "future_eligible_after_local_model_inventory_benchmark_and_receipts",
        (
            "local model inventory receipt",
            "sensitivity classification",
            "package preview",
            "Operator preview receipt",
        ),
        ("credential_or_oauth_handling", "browser_coupa_portal_use", "autonomous_tool_execution"),
        "Prefer for sensitive internal reasoning once local model capability is proven.",
    ),
    ModelClassPolicy(
        "local_sensitive",
        "Local Sensitive",
        "Private/offline handling posture for sensitive, finance, client, legal, and protected metadata work.",
        (
            "safety_review",
            "protected_access_review",
            "finance_ap_review",
            "legal_sensitive_review",
        ),
        ("browser_or_portal_related", "credential_or_oauth_related"),
        (
            "internal_operator_safe",
            "sensitive_private",
            "client_or_legal_sensitive",
            "finance_or_ap_sensitive",
            "protected_access_metadata",
        ),
        "recommendation_only_no_local_model_call",
        "future_eligible_after_security_audit_and_private_model_receipts",
        (
            "security audit",
            "Guardian gate",
            "sensitivity classification receipt",
            "memory scope receipt",
            "result receipt",
        ),
        (
            "credential_or_oauth_handling",
            "protected_file_access_without_gate",
            "surveillance_background_monitoring",
        ),
        "Shows that local/private is the default posture for sensitive material; it still grants no access now.",
    ),
    ModelClassPolicy(
        "external_fast_worker",
        "External Fast Worker",
        "Future fast external review for low-sensitivity, bounded packages with explicit preview and receipts.",
        ("test_authoring", "doctrine_review", "mission_control_ux"),
        (
            "protected_access_review",
            "finance_ap_review",
            "legal_sensitive_review",
            "credential_or_oauth_related",
        ),
        ("public_or_repo_safe",),
        "blocked_no_external_model_call",
        "future_eligible_only_after_operator_and_guardian_gates",
        (
            "package preview",
            "sensitivity classification",
            "Operator approval receipt",
            "external model use receipt",
        ),
        (
            "external_model_sensitive_data_without_gate",
            "credential_or_oauth_handling",
            "browser_coupa_portal_use",
        ),
        "May be useful later for speed, but never receives sensitive/protected context by default.",
    ),
    ModelClassPolicy(
        "external_deep_reasoner",
        "External Deep Reasoner",
        "Future high-depth external reasoning for non-sensitive architecture, doctrine, and synthesis.",
        ("architecture_review", "doctrine_review", "client_system_build"),
        (
            "finance_ap_review",
            "legal_sensitive_review",
            "protected_access_review",
            "credential_or_oauth_related",
        ),
        ("public_or_repo_safe",),
        "blocked_no_external_model_call",
        "future_eligible_only_after_operator_and_guardian_gates",
        (
            "package preview",
            "sensitivity classification",
            "Operator approval receipt",
            "Guardian external-model gate receipt",
        ),
        (
            "external_model_sensitive_data_without_gate",
            "protected_file_access_without_gate",
            "hidden_memory_capture",
        ),
        "Appropriate only for sanitized/non-sensitive packets once external model policy exists.",
    ),
    ModelClassPolicy(
        "external_code_worker",
        "External Code Worker",
        "Future scoped code/test worker for repo-safe implementation packages.",
        ("code_implementation", "test_authoring", "mission_control_ux"),
        (
            "credential_or_oauth_related",
            "protected_access_review",
            "legal_sensitive_review",
        ),
        ("public_or_repo_safe", "internal_operator_safe"),
        "blocked_no_external_model_call",
        "future_eligible_after_package_compiler_scope_and_operator_gate",
        (
            "allowed workspace roots",
            "forbidden paths",
            "package boundary validation",
            "Operator preview receipt",
            "result receipt",
        ),
        ("broad_filesystem_indexing", "credential_or_oauth_handling", "autonomous_tool_execution"),
        "Codex/Gemini-style workers can be routed later only through scoped package boundaries.",
    ),
    ModelClassPolicy(
        "external_multimodal",
        "External Multimodal",
        "Future visual/audio/document interpretation for sanitized media or UI proof packages.",
        ("mission_control_ux", "music_creative_review", "struna_development"),
        (
            "legal_sensitive_review",
            "finance_ap_review",
            "credential_or_oauth_related",
        ),
        ("public_or_repo_safe",),
        "blocked_no_external_model_call",
        "future_eligible_after_media_source_policy_and_operator_gate",
        (
            "media source classification",
            "package preview",
            "Operator approval receipt",
            "result receipt",
        ),
        (
            "external_model_sensitive_data_without_gate",
            "protected_file_access_without_gate",
            "hidden_memory_capture",
        ),
        "Do not imply media or screenshots are automatically safe to send externally.",
    ),
    ModelClassPolicy(
        "human_operator",
        "Human Operator",
        "Final human authority, taste judgment, approval/denial, and memory comparison.",
        tuple(PACKAGE_TYPES),
        (),
        tuple(SENSITIVITY_LEVELS),
        "human_decision_authority_only",
        "already_available_as_operator_review_not_model_execution",
        ("clear package preview", "proof/detail available for inspection"),
        ("autonomous_tool_execution", "hidden_memory_capture"),
        "Operator / Winship is not a model. This class means route the decision back to the human.",
    ),
    ModelClassPolicy(
        "blocked_no_model",
        "Blocked / No Model",
        "Safe fail-closed result when sensitivity, missing package fields, missing gates, or unclear authority blocks model choice.",
        tuple(PACKAGE_TYPES),
        (),
        tuple(SENSITIVITY_LEVELS),
        "active_safe_default",
        "always_valid_when_model_selection_is_unsafe_or_incomplete",
        (),
        tuple(item[0] for item in BLOCKED_MODEL_USES),
        "A blocked result is a valid model-selection outcome and should be shown plainly when it affects the next move.",
    ),
)

ACTOR_MODEL_POLICIES = (
    ActorModelPolicy(
        "operator_winship",
        ("human_operator",),
        ("human_operator",),
        ("human_operator",),
        tuple(model for model in MODEL_CLASSES if model not in {"human_operator"}),
        "Final authority remains human and cannot be replaced by model selection.",
        False,
        False,
    ),
    ActorModelPolicy(
        "chief",
        ("local_reasoning", "external_deep_reasoner", "local_small_fast"),
        ("blocked_no_model",),
        ("local_reasoning", "external_deep_reasoner", "local_small_fast"),
        ("external_multimodal",),
        "Chief needs coordination, work-board, check-engine, and deterministic synthesis support.",
        True,
        False,
    ),
    ActorModelPolicy(
        "guardian",
        ("local_sensitive", "local_reasoning", "human_operator"),
        ("blocked_no_model",),
        ("local_sensitive", "local_reasoning"),
        ("external_fast_worker", "external_code_worker", "external_multimodal"),
        "Guardian handles safety/security/protected-access ambiguity and should default local/private or block.",
        True,
        True,
    ),
    ActorModelPolicy(
        "cassandra",
        ("local_sensitive", "local_reasoning", "external_deep_reasoner"),
        ("blocked_no_model",),
        ("local_sensitive", "local_reasoning", "external_deep_reasoner"),
        ("external_fast_worker", "external_multimodal"),
        "Cassandra may review communications and finance/AP metadata; approval-adjacent or private content needs gates.",
        True,
        True,
    ),
    ActorModelPolicy(
        "hermes",
        ("local_reasoning", "external_deep_reasoner", "local_small_fast"),
        ("blocked_no_model",),
        ("local_reasoning", "external_deep_reasoner", "local_small_fast"),
        (),
        "Hermes is useful for architecture, doctrine, coherence, and horizon checks.",
        True,
        False,
    ),
    ActorModelPolicy(
        "niles",
        ("local_small_fast", "external_multimodal", "external_deep_reasoner"),
        ("blocked_no_model",),
        ("local_small_fast", "external_multimodal", "external_deep_reasoner"),
        ("local_sensitive",),
        "Niles supports music/art/creative production and should avoid sensitive business authority.",
        True,
        False,
    ),
    ActorModelPolicy(
        "codex",
        ("external_code_worker", "local_reasoning"),
        ("blocked_no_model",),
        ("external_code_worker", "local_reasoning"),
        ("external_multimodal", "local_sensitive"),
        "Codex is a scoped implementation worker for file edits, tests, and builds under package boundaries.",
        True,
        False,
    ),
    ActorModelPolicy(
        "gemini_antigravity",
        ("external_fast_worker", "external_code_worker", "external_deep_reasoner"),
        ("blocked_no_model",),
        ("external_fast_worker", "external_code_worker", "external_deep_reasoner"),
        ("local_sensitive",),
        "Gemini/Antigravity can be a fast planner/verifier/worker later, bounded by the same compiler gates.",
        True,
        False,
    ),
)

PACKAGE_TYPE_POLICIES = (
    PackageTypeModelPolicy(
        "code_implementation",
        ("external_code_worker", "local_reasoning"),
        ("blocked_no_model",),
        ("external_code_worker", "local_reasoning"),
        ("external_multimodal",),
        "public_or_repo_safe",
        ("package_type", "actor_id", "allowed_workspace_roots", "forbidden_paths", "proof_requirements"),
        True,
        False,
        "blocked_no_model_until_package_preview_and_boundary_validation_exist",
        "Code work may later use Codex/Gemini-style workers only through scoped package compiler boundaries.",
    ),
    PackageTypeModelPolicy(
        "test_authoring",
        ("local_small_fast", "external_code_worker"),
        ("blocked_no_model",),
        ("local_small_fast", "external_code_worker"),
        (),
        "public_or_repo_safe",
        ("package_type", "actor_id", "test_scope", "expected_outputs", "receipt_requirements"),
        True,
        False,
        "blocked_no_model_until_package_preview_exists",
        "Tests are safe only when scope and receipts are explicit.",
    ),
    PackageTypeModelPolicy(
        "architecture_review",
        ("local_reasoning", "external_deep_reasoner"),
        ("blocked_no_model",),
        ("local_reasoning", "external_deep_reasoner"),
        (),
        "internal_operator_safe",
        ("package_type", "actor_id", "context_included", "context_excluded", "sensitivity"),
        True,
        False,
        "blocked_no_model_if_context_sensitivity_unknown",
        "Architecture review can be external later only if the packet is sanitized and approved.",
    ),
    PackageTypeModelPolicy(
        "doctrine_review",
        ("local_reasoning", "external_deep_reasoner", "local_small_fast"),
        ("blocked_no_model",),
        ("local_reasoning", "external_deep_reasoner", "local_small_fast"),
        (),
        "internal_operator_safe",
        ("package_type", "actor_id", "source_refs", "operator_memory_status"),
        True,
        False,
        "blocked_no_model_if_source_refs_missing",
        "Doctrine must distinguish operator memory, proof, and future-gated claims.",
    ),
    PackageTypeModelPolicy(
        "safety_review",
        ("local_sensitive", "local_reasoning", "human_operator"),
        ("blocked_no_model",),
        ("local_sensitive", "local_reasoning"),
        ("external_fast_worker", "external_code_worker", "external_multimodal"),
        "sensitive_private",
        ("package_type", "actor_id", "Guardian gate", "authority_boundary", "blocked_actions"),
        True,
        True,
        "blocked_no_model_until_guardian_gate_exists",
        "Safety review defaults local/private or human until gates are explicit.",
    ),
    PackageTypeModelPolicy(
        "protected_access_review",
        ("local_sensitive", "human_operator"),
        ("blocked_no_model",),
        ("local_sensitive",),
        ("external_fast_worker", "external_deep_reasoner", "external_code_worker", "external_multimodal"),
        "protected_access_metadata",
        ("package_type", "actor_id", "protected_evidence_receipt", "Guardian gate", "no_private_bodies"),
        True,
        True,
        "blocked_no_model_until_protected_access_receipts_exist",
        "Protected access cannot route to external models by default.",
    ),
    PackageTypeModelPolicy(
        "communications_review",
        ("local_sensitive", "local_reasoning"),
        ("blocked_no_model",),
        ("local_sensitive", "local_reasoning", "external_deep_reasoner"),
        ("external_fast_worker",),
        "sensitive_private",
        ("package_type", "actor_id", "Cassandra boundary", "send_blocked", "sensitivity"),
        True,
        True,
        "blocked_no_model_for_private_body_or_send_authority",
        "Email/calendar work is review-only and never send/mutate authority from model selection.",
    ),
    PackageTypeModelPolicy(
        "finance_ap_review",
        ("local_sensitive", "local_reasoning"),
        ("blocked_no_model",),
        ("local_sensitive", "local_reasoning"),
        ("external_fast_worker", "external_deep_reasoner", "external_code_worker", "external_multimodal"),
        "finance_or_ap_sensitive",
        ("package_type", "actor_id", "proof_receipts", "approval_blocked", "Coupa_blocked"),
        True,
        True,
        "blocked_no_model_until_finance_proof_and_security_gate_exist",
        "Finance/AP defaults local/private or blocked; Coupa and approvals remain unavailable.",
    ),
    PackageTypeModelPolicy(
        "music_creative_review",
        ("local_small_fast", "external_multimodal", "external_deep_reasoner"),
        ("blocked_no_model",),
        ("local_small_fast", "external_multimodal", "external_deep_reasoner"),
        ("local_sensitive",),
        "public_or_repo_safe",
        ("package_type", "actor_id", "rights/sensitivity check", "context_refs"),
        True,
        False,
        "blocked_no_model_if_rights_or_source_sensitivity_unknown",
        "Creative review can use Niles-like routing once source rights and sensitivity are clear.",
    ),
    PackageTypeModelPolicy(
        "struna_development",
        ("local_reasoning", "external_code_worker", "external_multimodal"),
        ("blocked_no_model",),
        ("local_reasoning", "external_code_worker", "external_multimodal"),
        ("local_sensitive",),
        "internal_operator_safe",
        ("package_type", "actor_id", "workspace_scope", "asset_sensitivity", "proof_requirements"),
        True,
        False,
        "blocked_no_model_until_workspace_and_asset_scope_defined",
        "Struna can combine creative and implementation routing only after workspace and asset gates.",
    ),
    PackageTypeModelPolicy(
        "mission_control_ux",
        ("external_code_worker", "external_multimodal", "local_reasoning"),
        ("blocked_no_model",),
        ("external_code_worker", "external_multimodal", "local_reasoning"),
        (),
        "public_or_repo_safe",
        ("package_type", "actor_id", "Mac app boundary", "proof/screenshot scope", "no_app_authority_without_lane"),
        True,
        False,
        "blocked_no_model_until_ui_lane_scope_and_proof_are_defined",
        "UX work may use code/multimodal review later, but the Mac app remains a separate lane.",
    ),
    PackageTypeModelPolicy(
        "client_system_build",
        ("local_reasoning", "external_deep_reasoner"),
        ("blocked_no_model",),
        ("local_reasoning", "external_deep_reasoner"),
        ("external_fast_worker", "external_multimodal"),
        "client_or_legal_sensitive",
        ("package_type", "actor_id", "client sensitivity", "context_excluded", "Guardian gate"),
        True,
        True,
        "blocked_no_model_for_unclassified_client_context",
        "Client system work must be classified before any external model is considered.",
    ),
    PackageTypeModelPolicy(
        "legal_sensitive_review",
        ("local_sensitive", "human_operator"),
        ("blocked_no_model",),
        ("local_sensitive",),
        ("external_fast_worker", "external_deep_reasoner", "external_code_worker", "external_multimodal"),
        "client_or_legal_sensitive",
        ("package_type", "actor_id", "legal sensitivity", "Guardian gate", "operator confirmation"),
        True,
        True,
        "blocked_no_model_until_legal_sensitive_gate_exists",
        "Legal/sensitive review must stay local/private or blocked unless a later explicit gate exists.",
    ),
    PackageTypeModelPolicy(
        "credential_or_oauth_related",
        ("blocked_no_model", "human_operator"),
        ("blocked_no_model",),
        ("blocked_no_model",),
        tuple(model for model in MODEL_CLASSES if model not in {"blocked_no_model", "human_operator"}),
        "credential_or_oauth_related",
        ("package_type", "actor_id", "credential_policy", "no_secret_material"),
        True,
        True,
        "blocked_no_model",
        "Credential/OAuth work is not model-routable by this contract.",
    ),
    PackageTypeModelPolicy(
        "browser_or_portal_related",
        ("blocked_no_model", "human_operator"),
        ("blocked_no_model",),
        ("blocked_no_model",),
        tuple(model for model in MODEL_CLASSES if model not in {"blocked_no_model", "human_operator"}),
        "protected_access_metadata",
        ("package_type", "actor_id", "portal_policy", "no_account_flow", "Guardian gate"),
        True,
        True,
        "blocked_no_model",
        "Browser/Coupa/portal workflows remain blocked until a later protected-access adapter lane.",
    ),
)

RECOMMENDED_NEXT_LANES = (
    RecommendedLane(
        "agent_package_preview_contract_v0",
        "Agent Package Preview Contract v0",
        "P1",
        "Model policy now needs a stable package preview decision record that Mission Control can inspect before any future dispatch.",
        "preview-only; no launch, send, submit, model call, or tool execution",
    ),
    RecommendedLane(
        "agent_memory_scope_contract_v0",
        "Agent Memory Scope Contract v0",
        "P1",
        "Model selection must know which memory/read-model surfaces are allowed per actor before execution can be audited.",
        "metadata-only; no hidden memory capture or broad indexing",
    ),
    RecommendedLane(
        "tool_protocol_adapter_registry_v0",
        "Tool Protocol Adapter Registry v0",
        "P2",
        "Tools/protocols need an adapter registry before any workbench or model can request capability grants.",
        "descriptive only; no plugin/tool activation",
    ),
    RecommendedLane(
        "mission_control_actor_routing_surface_v0",
        "Mission Control Actor Routing Surface v0",
        "P2",
        "The Mac helm can later render who should inspect a lane and why without implying live agents.",
        "UI/read-only lane; no backend command authority",
    ),
    RecommendedLane(
        "model_selection_receipt_v0",
        "Model Selection Receipt v0",
        "P3",
        "Future model-selection decisions need immutable receipts before routing becomes executable.",
        "receipt schema only; no model call",
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


def _model_class_record(policy: ModelClassPolicy) -> dict[str, Any]:
    return {
        "model_class_id": policy.model_class_id,
        "display_name": policy.display_name,
        "intended_use": policy.intended_use,
        "suitable_package_types": list(policy.suitable_package_types),
        "unsuitable_package_types": list(policy.unsuitable_package_types),
        "sensitivity_allowed": list(policy.sensitivity_allowed),
        "current_authority": policy.current_authority,
        "future_eligibility": policy.future_eligibility,
        "required_gates": list(policy.required_gates),
        "blocked_uses": list(policy.blocked_uses),
        "notes_for_mission_control": policy.notes_for_mission_control,
        "model_callable_now": False,
        "may_self_select": False,
    }


def _actor_model_record(policy: ActorModelPolicy) -> dict[str, Any]:
    return {
        "actor_id": policy.actor_id,
        "preferred_model_classes": list(policy.preferred_model_classes),
        "allowed_current_model_classes": list(policy.allowed_current_model_classes),
        "future_eligible_model_classes": list(policy.future_eligible_model_classes),
        "blocked_model_classes": list(policy.blocked_model_classes),
        "reason": policy.reason,
        "requires_operator_preview": policy.requires_operator_preview,
        "requires_guardian_gate": policy.requires_guardian_gate,
        "can_self_select_model": False,
        "can_upgrade_model_class": False,
        "routing_execution_allowed_now": False,
    }


def _package_type_record(policy: PackageTypeModelPolicy) -> dict[str, Any]:
    return {
        "package_type": policy.package_type,
        "preferred_model_classes": list(policy.preferred_model_classes),
        "allowed_current_model_classes": list(policy.allowed_current_model_classes),
        "future_eligible_model_classes": list(policy.future_eligible_model_classes),
        "blocked_model_classes": list(policy.blocked_model_classes),
        "sensitivity_default": policy.sensitivity_default,
        "required_inputs": list(policy.required_inputs),
        "requires_operator_preview": policy.requires_operator_preview,
        "requires_guardian_gate": policy.requires_guardian_gate,
        "safe_default_result": policy.safe_default_result,
        "reason": policy.reason,
        "future_execution_allowed_now": False,
    }


def _recommended_lane_record(lane: RecommendedLane) -> dict[str, Any]:
    return {
        "lane_id": lane.lane_id,
        "title": lane.title,
        "priority": lane.priority,
        "why_next": lane.why_next,
        "hard_boundary": lane.hard_boundary,
    }


def build_model_selection_policy_contract(
    *,
    repo_root: str | Path = ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    evidence_sources = [_source_record(source, repo_root=repo_root) for source in EVIDENCE_SOURCES]
    model_classes = [_model_class_record(policy) for policy in MODEL_CLASS_POLICIES]
    actor_policies = [_actor_model_record(policy) for policy in ACTOR_MODEL_POLICIES]
    package_policies = [_package_type_record(policy) for policy in PACKAGE_TYPE_POLICIES]
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": "model_selection_policy_contract",
        "generated_at": generated_at,
        **NO_AUTHORITY_FLAGS,
        "contract_status": "deterministic_model_selection_policy_metadata_only",
        "operator_summary": (
            "OpenClaw now has a deterministic model-selection policy. It can say which model class would be "
            "appropriate, future-eligible, or blocked for an actor/package, but it cannot call any model. "
            "The safest valid answer remains blocked_no_model."
        ),
        "core_doctrine": {
            "model_is_actor_host_or_actor_class": "The model class is a future execution substrate, not the agent identity.",
            "agent_is_character": "Chief, Guardian, Cassandra, Hermes, Niles, Codex, and Gemini/Antigravity remain governed actor/agent roles.",
            "package_decides_context_authority_and_gates": True,
            "model_may_not_decide_own_authority": True,
            "model_choice_is_recommendation_not_command": True,
        },
        "evidence_sources": evidence_sources,
        "model_classes": model_classes,
        "selection_inputs_required": {
            "required_before_model_selection_is_valid": [
                "package_id",
                "package_type",
                "actor_id",
                "agent_character",
                "source_lane_id",
                "context_included",
                "context_excluded",
                "data_sensitivity",
                "clearance_level",
                "authority_boundary",
                "allowed_workspace_roots",
                "forbidden_paths",
                "allowed_capabilities",
                "forbidden_capabilities",
                "proof_requirements",
                "receipt_requirements",
                "operator_preview_required",
                "guardian_gate_required_if_sensitive_or_protected",
            ],
            "invalid_if_missing": True,
            "unknown_sensitivity_result": "blocked_no_model",
            "unknown_actor_result": "blocked_no_model",
            "unknown_package_type_result": "blocked_no_model",
        },
        "sensitivity_policy": {
            "sensitivity_levels": list(SENSITIVITY_LEVELS),
            "default_for_unknown": "unknown_fail_closed",
            "sensitive_private_defaults_to": "local_sensitive_or_blocked_no_model",
            "client_legal_finance_defaults_to": "local_sensitive_or_blocked_no_model",
            "credential_or_oauth_related_defaults_to": "blocked_no_model",
            "external_model_future_eligible_only_when": [
                "package preview is complete",
                "sensitivity classification is explicit",
                "context excluded is explicit",
                "Operator preview/approval receipt exists",
                "Guardian gate exists for sensitive/protected/approval-adjacent work",
                "result receipt requirement exists",
            ],
            "external_model_blocked_for": [
                "credential_or_oauth_related",
                "protected private bodies",
                "legal/client sensitive material without gate",
                "finance/AP sensitive material without gate",
                "unknown sensitivity",
            ],
        },
        "actor_model_policy": actor_policies,
        "package_type_model_policy": package_policies,
        "blocked_model_uses": [
            {"blocked_use_id": blocked_use_id, "description": description}
            for blocked_use_id, description in BLOCKED_MODEL_USES
        ],
        "confidence_policy": {
            "show_confidence_only_when": "uncertainty changes the operator's next safe move",
            "hide_when": "model posture is deterministic/high trust and no dispatch is happening",
            "unknown_or_missing_context": "UNKNOWN_FAIL_CLOSED",
            "blocked_no_model_is_valid_result": True,
            "do_not_display_fake_availability": True,
            "deterministic_success_requires": [
                "valid package inputs",
                "sensitivity classification",
                "actor policy match",
                "authority boundary match",
                "required receipts/proof",
            ],
        },
        "mission_control_surface_guidance": {
            "top_layer": "Recommended model posture",
            "middle_layer": "Why this model class fits, why other classes are blocked, and what gates are missing.",
            "lower_layer": "Package sensitivity, actor fit, proof refs, Guardian/Operator gates, and receipt requirements.",
            "full_inspection": "Complete model-selection decision record.",
            "do_not_present_as": [
                "live model availability",
                "running agent presence",
                "vendor scoreboard",
                "generic backend table",
                "confidence theater",
                "action launcher",
            ],
            "show_blocked_no_model_as": "safe fail-closed model posture when routing is unsafe or incomplete",
        },
        "future_receipt_requirements": {
            "required_before_future_model_execution": [
                "model selection decision receipt",
                "package compiler boundary validation receipt",
                "sensitivity classification receipt",
                "Operator preview/approval receipt when external or action-capable",
                "Guardian gate receipt for sensitive/protected/approval-adjacent work",
                "memory scope receipt",
                "tool adapter receipt if any capability is requested",
                "post-result receipt",
            ],
            "receipt_must_record": [
                "actor_id",
                "package_id",
                "package_type",
                "model_class_id",
                "sensitivity",
                "context_included_hash_or_refs",
                "context_excluded",
                "gates_present",
                "blocked_authorities",
                "operator_confirmation_if_any",
            ],
            "natural_language_claims_count_as_proof": False,
        },
        "recommended_next_lanes": [_recommended_lane_record(lane) for lane in RECOMMENDED_NEXT_LANES],
        "machine_proof": {
            "source_read_models_present": {source["source_id"]: source["present"] for source in evidence_sources},
            "model_class_ids": [item["model_class_id"] for item in model_classes],
            "actor_ids": [item["actor_id"] for item in actor_policies],
            "package_types": [item["package_type"] for item in package_policies],
            "raw_private_bodies_included": False,
            "credentials_or_secrets_included": False,
            "runtime_activation_added": False,
            "model_calls_added": False,
            "tool_execution_added": False,
            "content_hash": None,
        },
    }
    payload["machine_proof"]["content_hash"] = _content_hash(payload)
    return payload


def format_model_selection_policy_contract(payload: dict[str, Any]) -> str:
    lines = [
        "# Model Selection Policy Contract v0",
        "",
        "## Operator Summary",
        payload["operator_summary"],
        "",
        "## Model Classes",
    ]
    for item in payload["model_classes"]:
        lines.append(
            f"- `{item['model_class_id']}`: {item['display_name']} — {item['intended_use']} "
            f"(current authority: `{item['current_authority']}`)."
        )
    lines.extend(["", "## Actor / Model Rules"])
    for item in payload["actor_model_policy"]:
        future = ", ".join(f"`{model}`" for model in item["future_eligible_model_classes"])
        lines.append(
            f"- `{item['actor_id']}`: current `{', '.join(item['allowed_current_model_classes'])}`; "
            f"future-eligible {future}; Guardian gate `{str(item['requires_guardian_gate']).lower()}`."
        )
    lines.extend(["", "## Sensitivity Boundaries"])
    sensitivity = payload["sensitivity_policy"]
    lines.append(f"- Unknown sensitivity defaults to `{sensitivity['default_for_unknown']}`.")
    lines.append(f"- Credentials/OAuth defaults to `{sensitivity['credential_or_oauth_related_defaults_to']}`.")
    lines.append("- External model use is future-eligible only after explicit preview, classification, gates, and receipts.")
    lines.extend(["", "## Blocked Model Uses"])
    for item in payload["blocked_model_uses"]:
        lines.append(f"- `{item['blocked_use_id']}`: {item['description']}")
    lines.extend(["", "## Mission Control Guidance"])
    guidance = payload["mission_control_surface_guidance"]
    lines.append(f"- Top layer: {guidance['top_layer']}")
    lines.append(f"- Middle layer: {guidance['middle_layer']}")
    lines.append(f"- Lower layer: {guidance['lower_layer']}")
    lines.append("- Do not imply models are currently callable.")
    lines.append("- Show `blocked_no_model` as a safe, valid result.")
    lines.extend(["", "## Next Lanes"])
    for lane in payload["recommended_next_lanes"]:
        lines.append(f"- `{lane['lane_id']}` ({lane['priority']}): {lane['title']}")
    lines.extend(["", "## Authority Boundary"])
    for key, value in NO_AUTHORITY_FLAGS.items():
        lines.append(f"- `{key}`: `{str(value).lower()}`")
    return "\n".join(lines).rstrip() + "\n"


def export_model_selection_policy_contract(
    *,
    repo_root: str | Path = ROOT,
    export_root: str | Path = DEFAULT_EXPORT_ROOT,
    generated_at: str | None = None,
) -> ModelSelectionPolicyExportResult:
    payload = build_model_selection_policy_contract(repo_root=repo_root, generated_at=generated_at)
    root = Path(export_root)
    if not root.is_absolute():
        root = Path(repo_root) / root
    root.mkdir(parents=True, exist_ok=True)
    json_path = root / JSON_EXPORT_NAME
    operator_path = root / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(format_model_selection_policy_contract(payload), encoding="utf-8")
    return ModelSelectionPolicyExportResult(
        schema_version=payload["schema_version"],
        json_path=json_path.as_posix(),
        operator_path=operator_path.as_posix(),
        model_class_count=len(payload["model_classes"]),
        actor_policy_count=len(payload["actor_model_policy"]),
        package_type_policy_count=len(payload["package_type_model_policy"]),
        runtime_authority_added=bool(payload["runtime_authority"]),
        model_call_authority_added=bool(payload["model_call_authority"]),
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export Model Selection Policy Contract read-model.")
    parser.add_argument("--repo-root", default=ROOT.as_posix())
    parser.add_argument("--export-root", default=DEFAULT_EXPORT_ROOT.as_posix())
    parser.add_argument("--format", choices=("summary", "json", "operator"), default="summary")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    result = export_model_selection_policy_contract(
        repo_root=args.repo_root,
        export_root=args.export_root,
    )
    if args.format == "json":
        print(stable_json(build_model_selection_policy_contract(repo_root=args.repo_root)), end="")
    elif args.format == "operator":
        payload = build_model_selection_policy_contract(repo_root=args.repo_root)
        print(format_model_selection_policy_contract(payload), end="")
    else:
        print(
            stable_json(
                {
                    "schema_version": result.schema_version,
                    "json_path": result.json_path,
                    "operator_path": result.operator_path,
                    "model_class_count": result.model_class_count,
                    "actor_policy_count": result.actor_policy_count,
                    "package_type_policy_count": result.package_type_policy_count,
                    "runtime_authority_added": result.runtime_authority_added,
                    "model_call_authority_added": result.model_call_authority_added,
                }
            ),
            end="",
        )
    return 0


__all__ = [
    "ACTOR_IDS",
    "JSON_EXPORT_NAME",
    "MODEL_CLASSES",
    "NO_AUTHORITY_FLAGS",
    "OPERATOR_EXPORT_NAME",
    "PACKAGE_TYPES",
    "SCHEMA_VERSION",
    "SENSITIVITY_LEVELS",
    "build_model_selection_policy_contract",
    "export_model_selection_policy_contract",
    "format_model_selection_policy_contract",
    "main",
    "stable_json",
]


if __name__ == "__main__":
    raise SystemExit(main())
