"""Agent Memory Scope Contract v0 for OpenClaw.

This read-model defines what memory means before any actor/model/tool system
can use it. It is deterministic metadata only. It does not create model memory,
hidden memory capture, autonomous personalization, raw chat ingestion, vector
memory, runtime activation, external tool memory, credential memory, or package
execution authority.
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

SCHEMA_VERSION = "agent_memory_scope_contract_v0"
JSON_EXPORT_NAME = "agent_memory_scope_contract.json"
OPERATOR_EXPORT_NAME = "agent_memory_scope_contract_OPERATOR.md"

NO_AUTHORITY_FLAGS = {
    "runtime_authority": False,
    "model_memory_authority": False,
    "hidden_memory_authority": False,
    "autonomous_memory_capture": False,
    "raw_chat_ingestion_authority": False,
    "vector_memory_authority": False,
    "external_tool_memory_authority": False,
    "credential_memory_authority": False,
    "operator_final_authority": True,
    "model_call_authority": False,
    "agent_call_authority": False,
    "tool_execution_authority": False,
    "routing_execution_authority": False,
    "browser_oauth_account_access_enabled": False,
    "gmail_calendar_coupa_telegram_enabled": False,
    "send_submit_approval_enabled": False,
    "network_execution_enabled": False,
    "runtime_daemon_enabled": False,
    "background_surveillance_enabled": False,
    "pc_c_drive_artifact_write_allowed": False,
}

MEMORY_SURFACE_TYPES = (
    "canonical_promoted_memory",
    "deterministic_read_model",
    "receipt_backed_fact",
    "source_card",
    "accepted_context_packet",
    "operator_handoff",
    "project_capsule",
    "local_workspace_residue",
    "session_transcript_residue",
    "assistant_checkpoint_residue",
    "copilot_workspace_residue",
    "external_model_context",
    "raw_private_body",
    "credential_or_token",
    "browser_session_material",
    "protected_reference_only_material",
)

CANONICAL_MEMORY_SURFACES = (
    "vault",
    "handoff",
    "mac_eyes",
    "polish_loop",
    "CLAUDE.md",
)

NONCANONICAL_RESIDUE_SURFACES = (
    "session-local memory",
    "workspace artifacts",
    "assistant checkpoint files",
    "Copilot workspace memory",
    "temporary scratch files",
    "unpromoted chat summaries",
    "unreceipted worker notes",
    "unverified generated artifacts",
)

BLOCKED_MEMORY_SURFACES = (
    "credentials",
    "OAuth tokens",
    "browser cookies/session data",
    "raw bank/remit/check/home-address material",
    "raw client/legal/finance/private documents unless protected reference only",
    "raw Gmail/calendar bodies unless specifically gated",
    "surveillance/background observation",
    "hidden personalization capture",
    "broad filesystem memory capture",
    "external model retained memory",
    "unverified claims treated as facts",
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

SENSITIVITY_CLASSES = (
    "public_or_repo_safe",
    "internal_operator_safe",
    "operator_memory_candidate",
    "sensitive_private",
    "finance_or_ap_sensitive",
    "protected_reference_only",
    "client_or_legal_sensitive",
    "credential_or_token",
    "unknown_fail_closed",
)


@dataclass(frozen=True)
class EvidenceSource:
    source_id: str
    path: str
    role: str


@dataclass(frozen=True)
class MemorySurface:
    surface_id: str
    surface_type: str
    canonical_status: str
    allowed_use: str
    requires_operator_promotion: bool
    requires_guardian_review: bool
    notes: str


@dataclass(frozen=True)
class ActorMemoryScope:
    actor_id: str
    display_name: str
    readable_context_allowed: tuple[str, ...]
    readable_context_blocked: tuple[str, ...]
    writable_memory_candidates: tuple[str, ...]
    writeback_blocked: tuple[str, ...]
    requires_operator_promotion: bool
    requires_guardian_review: bool
    retention_posture: str
    sensitive_context_posture: str
    notes_for_mission_control: str


@dataclass(frozen=True)
class ExampleMemoryScopeDecision:
    decision_id: str
    actor_id: str
    title: str
    readable_context_allowed: tuple[str, ...]
    readable_context_blocked: tuple[str, ...]
    writable_memory_candidate: str
    promotion_required: bool
    guardian_review_required: bool
    mission_control_summary: str


@dataclass(frozen=True)
class RecommendedLane:
    lane_id: str
    title: str
    priority: str
    why_next: str
    hard_boundary: str


@dataclass(frozen=True)
class AgentMemoryScopeExportResult:
    schema_version: str
    json_path: str
    operator_path: str
    actor_scope_count: int
    canonical_surface_count: int
    example_count: int
    runtime_authority_added: bool
    hidden_memory_authority_added: bool


EVIDENCE_SOURCES = (
    EvidenceSource(
        "openclaw_runtime_law",
        "OPENCLAW_RUNTIME.md",
        "runtime law: source of authority boundaries and no shadow systems",
    ),
    EvidenceSource(
        "operator_preferences",
        "USER.md",
        "operator identity and communication preferences",
    ),
    EvidenceSource(
        "agent_platform_alignment",
        "generated/read_models/agent_platform_alignment.json",
        "agent-platform primitive map and missing memory-scope primitive",
    ),
    EvidenceSource(
        "agent_identity_actor_router_contract",
        "generated/read_models/agent_identity_actor_router_contract.json",
        "actor identities and routing boundaries",
    ),
    EvidenceSource(
        "model_selection_policy_contract",
        "generated/read_models/model_selection_policy_contract.json",
        "model class and sensitivity policy",
    ),
    EvidenceSource(
        "agent_package_preview_contract",
        "generated/read_models/agent_package_preview_contract.json",
        "package preview context inclusion/exclusion policy",
    ),
    EvidenceSource(
        "package_compiler_contract",
        "generated/read_models/package_compiler_contract.json",
        "package boundary validation, receipts, and context fields",
    ),
    EvidenceSource(
        "protected_evidence_reference_receipt",
        "generated/read_models/protected_evidence_reference_receipt.json",
        "metadata-only protected evidence reference posture",
    ),
    EvidenceSource(
        "guardian_protected_access_gate_spec",
        "generated/read_models/guardian_protected_access_gate_spec.json",
        "Guardian protected-access gate posture",
    ),
)

MEMORY_SURFACES = (
    MemorySurface(
        "vault",
        "canonical_promoted_memory",
        "canonical_surface",
        "durable promoted memory surface after operator promotion and receipts",
        True,
        True,
        "Canonical only when promoted; sensitive/protected entries require Guardian review.",
    ),
    MemorySurface(
        "handoff",
        "operator_handoff",
        "canonical_surface",
        "bounded operator handoff surface for current work context",
        True,
        False,
        "Can orient future workers but does not override proof/read-models.",
    ),
    MemorySurface(
        "mac_eyes",
        "canonical_promoted_memory",
        "canonical_surface",
        "operator-facing watch/visibility surface when explicitly governed",
        True,
        True,
        "Historically sensitive; treat visible material as context refs, not raw ingestion authority.",
    ),
    MemorySurface(
        "polish_loop",
        "canonical_promoted_memory",
        "canonical_surface",
        "bounded build-loop/handoff surface when explicitly governed",
        True,
        False,
        "Loop artifacts are not autonomous truth unless promoted into canonical read-models/receipts.",
    ),
    MemorySurface(
        "CLAUDE.md",
        "operator_handoff",
        "canonical_surface",
        "tool-adapter instruction surface when present and explicitly maintained",
        True,
        False,
        "Does not fork OpenClaw runtime law; runtime law remains source of authority.",
    ),
    MemorySurface(
        "generated_read_models",
        "deterministic_read_model",
        "canonical_read_model",
        "deterministic backend state exported for Mission Control and package previews",
        False,
        False,
        "Read-models are authoritative within their contract scope.",
    ),
    MemorySurface(
        "receipt_backed_facts",
        "receipt_backed_fact",
        "canonical_proof_when_valid",
        "facts backed by explicit receipts, hashes, manifests, or source refs",
        False,
        False,
        "Receipt presence proves metadata/proof posture, not new action authority.",
    ),
    MemorySurface(
        "source_cards",
        "source_card",
        "candidate_context",
        "bounded source summaries/cards eligible for package context",
        True,
        True,
        "Source cards are context candidates until promoted or selected by a package gate.",
    ),
    MemorySurface(
        "accepted_context_packets",
        "accepted_context_packet",
        "bounded_context",
        "explicitly selected context packets for package previews",
        True,
        False,
        "Allowed as refs; raw private bodies remain excluded.",
    ),
    MemorySurface(
        "project_capsules",
        "project_capsule",
        "bounded_context",
        "project/domain capsule refs for worlds and packages",
        True,
        True,
        "Domain-sensitive capsules still need sensitivity classification.",
    ),
)

ACTOR_MEMORY_SCOPES = (
    ActorMemoryScope(
        "operator_winship",
        "Operator / Winship",
        (
            "all generated read-model summaries",
            "proof/detail refs",
            "memory candidates awaiting promotion",
            "canonical surfaces",
            "non-canonical residue labels",
        ),
        ("hidden background capture", "model-retained memory claims", "credential/token storage"),
        ("operator promotion decisions", "memory correction requests", "revocation decisions"),
        ("silent memory writes", "unreceipted canonical mutation"),
        False,
        False,
        "final human authority; can promote, reject, correct, or revoke memory through explicit receipts",
        "may review sensitive memory but still requires safe handling and Guardian gate for protected access workflows",
        "Mission Control should show what is memory, what is candidate, and what is not proof.",
    ),
    ActorMemoryScope(
        "chief",
        "Chief",
        (
            "work-board read-model refs",
            "check-engine posture refs",
            "sync/system health refs",
            "package preview refs",
        ),
        ("session-local residue as truth", "private raw bodies", "credentials", "broad filesystem memory"),
        ("work-board posture candidate", "system health memory candidate", "lane quieting candidate"),
        ("canonical memory promotion", "private raw memory writes", "hidden monitoring"),
        True,
        False,
        "may propose system/workbench memory candidates but cannot make residue canonical",
        "sensitive context must be referenced by metadata only unless a Guardian gate exists",
        "Chief sees system posture refs, not broad personal memory.",
    ),
    ActorMemoryScope(
        "guardian",
        "Guardian",
        (
            "protected evidence metadata refs",
            "authority boundary refs",
            "sensitivity classifications",
            "blocked action receipts",
        ),
        ("raw protected files without gate", "credentials/tokens", "browser/session material"),
        ("safety/security memory candidate", "protected-access classification candidate", "revocation recommendation"),
        ("self-promotion into canonical memory", "secret storage", "approval execution"),
        True,
        False,
        "reviews and proposes safety/protected-access memory candidates; cannot self-promote",
        "may inspect metadata/proof refs; raw protected context remains fail-closed until gated",
        "Guardian can recommend what should be remembered or forgotten, with receipts.",
    ),
    ActorMemoryScope(
        "cassandra",
        "Cassandra",
        (
            "governed communications refs",
            "finance/AP metadata refs",
            "Capital Hilton protected proof metadata refs",
            "Cassandra detangle read-model refs",
        ),
        ("raw Gmail bodies without gate", "raw calendar bodies without gate", "Coupa/browser sessions", "bank/remit/check raw data"),
        ("communication workflow candidate", "finance/AP metadata memory candidate", "draft identity reference candidate"),
        ("email send memory", "calendar mutation memory", "credential/account memory", "raw private body memory"),
        True,
        True,
        "may propose communications/finance memory candidates but cannot ingest raw bodies or send/mutate",
        "finance/AP and private communications default protected or metadata-only",
        "Cassandra receives refs and summaries, not account/session material.",
    ),
    ActorMemoryScope(
        "hermes",
        "Hermes",
        (
            "architecture doctrine refs",
            "system coherence read-model refs",
            "operator doctrine candidates",
            "design memory inventory refs",
        ),
        ("private raw chat bodies", "credentials", "client/legal/finance private documents"),
        ("architecture doctrine candidate", "coherence finding candidate", "source-conflict candidate"),
        ("canonical doctrine promotion", "private body ingestion", "external retained memory"),
        True,
        False,
        "may propose doctrine/system memory candidates from sanitized refs",
        "private or client-sensitive material must be excluded or metadata-only",
        "Hermes gets architecture packets, not unbounded history.",
    ),
    ActorMemoryScope(
        "niles",
        "Niles",
        (
            "music/art project capsule refs",
            "Struna metadata refs",
            "creative workflow read-model refs",
            "rights/sensitivity metadata refs",
        ),
        ("unrelated private/client material", "credentials", "distribution account sessions", "legal/finance raw documents"),
        ("music/art memory candidate", "Struna metadata candidate", "creative workflow candidate"),
        ("publishing account memory", "credential memory", "unapproved raw media retention"),
        True,
        False,
        "may propose music/art/Struna memory candidates without business/account authority",
        "creative assets require rights/sensitivity classification before inclusion",
        "Niles sees creative refs, not unrelated private context.",
    ),
    ActorMemoryScope(
        "codex",
        "Codex",
        (
            "scoped implementation package refs",
            "file/path refs inside allowed workspace",
            "test/build output refs",
            "read-model contract refs",
        ),
        ("broad memory", "secrets", "credentials", "private raw bodies", "out-of-scope file trees"),
        ("implementation finding candidate", "test result memory candidate", "read-model contract delta candidate"),
        ("canonical memory writes", "secret storage", "broad indexing", "workspace residue as truth"),
        True,
        False,
        "receives scoped package context only; cannot treat workspace residue as memory",
        "private/protected data must be excluded unless represented by approved metadata refs",
        "Codex memory is package-scoped and receipt-backed.",
    ),
    ActorMemoryScope(
        "gemini_antigravity",
        "Gemini / Antigravity",
        (
            "scoped package previews",
            "sanitized proof/refactor refs",
            "explicit context packets",
            "test/proof refs",
        ),
        ("durable retained memory", "raw protected material", "secrets", "unbounded workspace context", "external model retained memory"),
        ("proof/refactor finding candidate", "verification note candidate"),
        ("canonical memory writes", "external retained memory", "secret/private retention"),
        True,
        True,
        "may receive scoped package previews only; no durable retained memory or raw protected material",
        "external/sensitive use requires explicit Operator and Guardian gates",
        "Gemini/Antigravity is bounded to package refs and receipts.",
    ),
)

EXAMPLE_MEMORY_SCOPE_DECISIONS = (
    ExampleMemoryScopeDecision(
        "codex_backend_refs_no_secrets",
        "codex",
        "Codex receives backend implementation refs but no secrets",
        ("package preview refs", "allowed workspace file refs", "test refs", "read-model refs"),
        ("credentials", "private raw bodies", "broad filesystem memory", "PC system-drive artifacts"),
        "implementation finding candidate",
        True,
        False,
        "Show Codex the bounded implementation packet, not broad memory or secrets.",
    ),
    ExampleMemoryScopeDecision(
        "cassandra_capital_hilton_refs_no_raw_bodies",
        "cassandra",
        "Cassandra receives Capital Hilton invoice context refs but not raw Gmail bodies",
        ("Capital Hilton metadata refs", "protected evidence receipt refs", "finance/AP read-model refs"),
        ("raw Gmail bodies", "raw calendar bodies", "Coupa portal/session data", "bank/remit/check raw data"),
        "finance/AP metadata memory candidate",
        True,
        True,
        "Show Cassandra metadata/proof refs only until Guardian and operator gates exist.",
    ),
    ExampleMemoryScopeDecision(
        "niles_struna_project_capsule_refs",
        "niles",
        "Niles receives Struna project capsule refs",
        ("Struna project capsule refs", "music/art metadata refs", "creative workflow refs"),
        ("unrelated client/private material", "distribution account sessions", "credentials"),
        "Struna creative metadata candidate",
        True,
        False,
        "Show Niles creative/project refs with rights/sensitivity posture.",
    ),
    ExampleMemoryScopeDecision(
        "guardian_protected_evidence_candidate",
        "guardian",
        "Guardian reviews a protected evidence memory candidate",
        ("protected evidence reference receipts", "sensitivity classification refs", "blocked authority refs"),
        ("raw protected files", "credentials", "browser/session material"),
        "protected-access classification candidate",
        True,
        False,
        "Guardian can review protected metadata and recommend promote/block/revoke.",
    ),
    ExampleMemoryScopeDecision(
        "chief_check_engine_posture_refs",
        "chief",
        "Chief receives check-engine posture refs",
        ("Chief diagnostic package refs", "system health lights refs", "sync health refs"),
        ("cleanup/delete authority", "raw trace bodies", "credentials", "remount/session material"),
        "system health posture memory candidate",
        True,
        False,
        "Chief gets inspect-only system/workbench memory refs.",
    ),
    ExampleMemoryScopeDecision(
        "hermes_architecture_doctrine_refs",
        "hermes",
        "Hermes receives architecture doctrine refs",
        ("architecture read-model refs", "design doctrine refs", "source-conflict refs"),
        ("raw private chat history", "credentials", "client/legal/finance raw docs"),
        "architecture doctrine candidate",
        True,
        False,
        "Hermes gets sanitized doctrine/system coherence packets.",
    ),
    ExampleMemoryScopeDecision(
        "gemini_antigravity_scoped_refactor_no_retention",
        "gemini_antigravity",
        "Gemini/Antigravity receives scoped proof/refactor package with no retained memory",
        ("scoped package preview", "sanitized file refs", "test/proof refs"),
        ("durable retained memory", "raw protected material", "secrets", "unbounded workspace context"),
        "verification note candidate",
        True,
        True,
        "External worker receives only the scoped packet and returns receipt-backed candidates.",
    ),
)

RECOMMENDED_NEXT_LANES = (
    RecommendedLane(
        "tool_protocol_adapter_registry_v0",
        "Tool Protocol Adapter Registry v0",
        "P1",
        "Memory scope clarifies context; tools now need a denied-by-default adapter registry before any future capability grant.",
        "descriptive only; no plugin/tool activation",
    ),
    RecommendedLane(
        "memory_candidate_receipt_v0",
        "Memory Candidate Receipt v0",
        "P1",
        "Actors may only propose memory candidates, so promotion/rejection needs a receipt schema.",
        "receipt metadata only; no canonical writes",
    ),
    RecommendedLane(
        "mission_control_package_preview_surface_v0",
        "Mission Control Package Preview Surface v0",
        "P2",
        "Mission Control can render package previews with memory scope before any future action.",
        "read-only UI lane; no backend command authority",
    ),
    RecommendedLane(
        "mission_control_actor_routing_surface_v0",
        "Mission Control Actor Routing Surface v0",
        "P2",
        "Actor routing can show memory scope and package context without implying live agents.",
        "read-only UI lane; no model/agent launch",
    ),
    RecommendedLane(
        "model_selection_receipt_v0",
        "Model Selection Receipt v0",
        "P3",
        "Future model-selection decisions need receipts that include memory scope and sensitivity.",
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


def _surface_record(surface: MemorySurface) -> dict[str, Any]:
    return {
        "surface_id": surface.surface_id,
        "surface_type": surface.surface_type,
        "canonical_status": surface.canonical_status,
        "allowed_use": surface.allowed_use,
        "requires_operator_promotion": surface.requires_operator_promotion,
        "requires_guardian_review": surface.requires_guardian_review,
        "notes": surface.notes,
    }


def _actor_scope_record(scope: ActorMemoryScope) -> dict[str, Any]:
    return {
        "actor_id": scope.actor_id,
        "display_name": scope.display_name,
        "readable_context_allowed": list(scope.readable_context_allowed),
        "readable_context_blocked": list(scope.readable_context_blocked),
        "writable_memory_candidates": list(scope.writable_memory_candidates),
        "writeback_blocked": list(scope.writeback_blocked),
        "requires_operator_promotion": scope.requires_operator_promotion,
        "requires_guardian_review": scope.requires_guardian_review,
        "retention_posture": scope.retention_posture,
        "sensitive_context_posture": scope.sensitive_context_posture,
        "notes_for_mission_control": scope.notes_for_mission_control,
        "can_write_canonical_memory_directly": False,
        "can_silently_retain_memory": False,
    }


def _example_record(example: ExampleMemoryScopeDecision) -> dict[str, Any]:
    return {
        "decision_id": example.decision_id,
        "actor_id": example.actor_id,
        "title": example.title,
        "readable_context_allowed": list(example.readable_context_allowed),
        "readable_context_blocked": list(example.readable_context_blocked),
        "writable_memory_candidate": example.writable_memory_candidate,
        "promotion_required": example.promotion_required,
        "guardian_review_required": example.guardian_review_required,
        "mission_control_summary": example.mission_control_summary,
        "canonical_memory_written_now": False,
        "model_memory_created_now": False,
    }


def _recommended_lane_record(lane: RecommendedLane) -> dict[str, Any]:
    return {
        "lane_id": lane.lane_id,
        "title": lane.title,
        "priority": lane.priority,
        "why_next": lane.why_next,
        "hard_boundary": lane.hard_boundary,
    }


def build_agent_memory_scope_contract(
    *,
    repo_root: str | Path = ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    evidence_sources = [_source_record(source, repo_root=repo_root) for source in EVIDENCE_SOURCES]
    memory_surfaces = [_surface_record(surface) for surface in MEMORY_SURFACES]
    actor_scopes = [_actor_scope_record(scope) for scope in ACTOR_MEMORY_SCOPES]
    examples = [_example_record(example) for example in EXAMPLE_MEMORY_SCOPE_DECISIONS]
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": "agent_memory_scope_contract",
        "generated_at": generated_at,
        **NO_AUTHORITY_FLAGS,
        "contract_status": "deterministic_memory_scope_metadata_only",
        "operator_summary": (
            "OpenClaw now has a deterministic memory-scope contract. It says what memory surfaces are canonical, "
            "what is only residue, what actors may read as context, what they may propose as memory candidates, "
            "and what requires operator promotion or Guardian review. It does not create model memory or ingest raw chat."
        ),
        "evidence_sources": evidence_sources,
        "memory_surface_taxonomy": {
            "surface_types": list(MEMORY_SURFACE_TYPES),
            "memory_surfaces": memory_surfaces,
            "session_local_workspace_assistant_and_copilot_memory_have_zero_authority": True,
            "noncanonical_residue_must_be_labelled": True,
        },
        "canonical_memory_surfaces": [
            {
                "surface_id": surface_id,
                "canonical_rule": "canonical only when explicitly promoted into this surface with proof/receipt",
                "does_not_override_read_model_proof": True,
            }
            for surface_id in CANONICAL_MEMORY_SURFACES
        ],
        "noncanonical_residue_surfaces": [
            {
                "surface_id": surface_id,
                "canonical_status": "non_authoritative_residue",
                "promotion_required_before_use_as_memory": True,
            }
            for surface_id in NONCANONICAL_RESIDUE_SURFACES
        ],
        "blocked_memory_surfaces": [
            {
                "surface_id": surface_id,
                "memory_result": "blocked",
                "may_be_used_as_package_context_now": False,
            }
            for surface_id in BLOCKED_MEMORY_SURFACES
        ],
        "actor_memory_scopes": actor_scopes,
        "context_read_policy": {
            "allowed_context_forms": [
                "deterministic read-model refs",
                "receipt IDs",
                "source cards",
                "accepted context packets",
                "project capsule refs",
                "operator handoff refs",
                "metadata-only protected references after Guardian gate",
            ],
            "raw_private_bodies_allowed_by_default": False,
            "protected_material_policy": "metadata-only reference unless future Guardian gate and receipt allow otherwise",
            "session_residue_policy": "non-authoritative until promoted",
            "unknown_context_result": "UNKNOWN_FAIL_CLOSED",
        },
        "memory_writeback_policy": {
            "actors_may_only_propose_candidates": True,
            "actors_may_directly_write_canonical_memory": False,
            "models_may_silently_retain_or_promote_memory": False,
            "candidate_required_fields": [
                "source_refs",
                "claim_type",
                "sensitivity_classification",
                "proposed_canonical_surface",
                "why_it_matters",
                "expiration_or_review_posture",
                "operator_promotion_requirement",
                "receipt_requirement",
            ],
            "writeback_blocked": [
                "canonical memory mutation",
                "hidden memory writes",
                "credential/token storage",
                "external retained memory",
                "unreceipted worker note promotion",
            ],
        },
        "memory_candidate_policy": {
            "candidate_statuses": [
                "captured_candidate",
                "needs_operator_promotion",
                "needs_guardian_review",
                "rejected",
                "expired",
                "promoted_with_receipt",
                "revoked",
            ],
            "operator_memory_can": [
                "identify missing terrain",
                "label a gap",
                "propose a direction",
                "clarify intent",
                "classify a lane as worth mapping",
            ],
            "operator_memory_may_not": [
                "become proof by itself",
                "authorize execution",
                "replace machine contract",
                "bypass security audit",
                "imply private data ingestion",
            ],
        },
        "promotion_policy": {
            "promotion_requires_operator": True,
            "promotion_requires_receipt_or_proof": True,
            "sensitive_or_protected_requires_guardian_review": True,
            "noncanonical_residue_remains_non_authoritative_until_promoted": True,
            "unverified_claims_are_not_facts": True,
        },
        "redaction_and_reference_policy": {
            "prefer_refs_over_bodies": True,
            "must_redact_or_exclude": list(BLOCKED_MEMORY_SURFACES),
            "protected_reference_only_requires": [
                "protected evidence reference receipt",
                "Guardian gate",
                "metadata-only reference",
                "no raw private body",
            ],
            "package_context_must_show_exclusions": True,
        },
        "forgetting_and_revocation_policy": {
            "future_safe_operations": [
                "revoke promoted memory",
                "mark memory stale",
                "replace incorrect memory",
                "suppress sensitive memory from packages",
                "prove memory candidate was rejected",
                "prove memory candidate expired",
            ],
            "revocation_requires_receipt": True,
            "stale_memory_must_not_drive_packages_without_review": True,
            "rejected_memory_must_not_reappear_as_fact": True,
        },
        "sensitivity_policy": {
            "sensitivity_classes": list(SENSITIVITY_CLASSES),
            "unknown_defaults_to": "unknown_fail_closed",
            "credential_or_token_result": "blocked",
            "finance_client_legal_private_defaults_to": "protected_reference_or_blocked",
            "external_model_memory_default": "blocked",
            "guardian_review_required_for": [
                "protected_reference_only",
                "finance_or_ap_sensitive",
                "client_or_legal_sensitive",
                "credential_or_token",
            ],
        },
        "receipt_requirements": {
            "required_for_future_memory_promotion": [
                "memory candidate receipt",
                "source refs/proof receipt",
                "sensitivity classification receipt",
                "operator promotion receipt",
                "Guardian review receipt when sensitive/protected",
            ],
            "required_for_future_memory_revocation": [
                "revocation receipt",
                "replacement receipt if corrected",
                "stale/expired marker receipt",
            ],
            "natural_language_claims_count_as_proof": False,
        },
        "mission_control_surface_guidance": {
            "top_layer": "what memory would this actor see?",
            "middle_layer": "what is excluded and why?",
            "lower_layer": "promotion, sensitivity, proof, receipts",
            "full_inspection": "complete memory scope decision",
            "do_not_present_as": [
                "fake model memory",
                "hidden personalization",
                "raw chat dump",
                "generic backend table",
                "confidence theater",
                "live memory writer",
            ],
            "show_noncanonical_residue_as": "non-authoritative until promoted",
        },
        "example_memory_scope_decisions": examples,
        "blocked_memory_states": [
            {
                "state_id": state_id,
                "memory_result": "blocked",
                "canonical_memory_written_now": False,
            }
            for state_id in (
                "credential_or_token_present",
                "browser_session_material_present",
                "raw_private_body_present_without_gate",
                "raw_chat_dump_requested",
                "hidden_memory_capture_requested",
                "broad_filesystem_memory_requested",
                "external_model_retained_memory_requested",
                "operator_promotion_missing",
                "guardian_review_missing_for_sensitive",
                "unverified_claim_treated_as_fact",
            )
        ],
        "recommended_next_lanes": [_recommended_lane_record(lane) for lane in RECOMMENDED_NEXT_LANES],
        "machine_proof": {
            "source_read_models_present": {source["source_id"]: source["present"] for source in evidence_sources},
            "canonical_memory_surface_ids": list(CANONICAL_MEMORY_SURFACES),
            "known_actor_ids": list(KNOWN_ACTOR_IDS),
            "example_decision_ids": [item["decision_id"] for item in examples],
            "raw_private_bodies_included": False,
            "credentials_or_secrets_included": False,
            "raw_chat_ingested": False,
            "hidden_memory_authority_added": False,
            "vector_memory_added": False,
            "runtime_activation_added": False,
            "content_hash": None,
        },
    }
    payload["machine_proof"]["content_hash"] = _content_hash(payload)
    return payload


def format_agent_memory_scope_contract(payload: dict[str, Any]) -> str:
    lines = [
        "# Agent Memory Scope Contract v0",
        "",
        "## Operator Summary",
        payload["operator_summary"],
        "",
        "## Canonical Memory Surfaces",
    ]
    for surface in payload["canonical_memory_surfaces"]:
        lines.append(f"- `{surface['surface_id']}`: {surface['canonical_rule']}")
    lines.extend(["", "## Non-Canonical Residue"])
    for surface in payload["noncanonical_residue_surfaces"]:
        lines.append(f"- `{surface['surface_id']}`: `{surface['canonical_status']}`")
    lines.extend(["", "## Actor Memory Scopes"])
    for scope in payload["actor_memory_scopes"]:
        lines.append(
            f"- `{scope['actor_id']}`: reads {len(scope['readable_context_allowed'])} allowed context groups, "
            f"blocks {len(scope['readable_context_blocked'])}, promotion required `{str(scope['requires_operator_promotion']).lower()}`."
        )
    lines.extend(["", "## Context / Sensitivity Boundary"])
    lines.append("- Allowed context is refs, receipts, source cards, accepted packets, project capsules, and operator handoffs.")
    lines.append("- Raw private bodies are blocked by default.")
    lines.append("- Protected material uses metadata-only references unless a future Guardian gate and receipt allow otherwise.")
    lines.extend(["", "## Mission Control Guidance"])
    guidance = payload["mission_control_surface_guidance"]
    lines.append(f"- Top layer: {guidance['top_layer']}")
    lines.append(f"- Middle layer: {guidance['middle_layer']}")
    lines.append(f"- Lower layer: {guidance['lower_layer']}")
    lines.append(f"- Full inspection: {guidance['full_inspection']}")
    lines.append("- Show non-canonical residue as non-authoritative.")
    lines.extend(["", "## Authority Boundary"])
    for key, value in NO_AUTHORITY_FLAGS.items():
        lines.append(f"- `{key}`: `{str(value).lower()}`")
    lines.extend(["", "## Next Lanes"])
    for lane in payload["recommended_next_lanes"]:
        lines.append(f"- `{lane['lane_id']}` ({lane['priority']}): {lane['title']}")
    return "\n".join(lines).rstrip() + "\n"


def export_agent_memory_scope_contract(
    *,
    repo_root: str | Path = ROOT,
    export_root: str | Path = DEFAULT_EXPORT_ROOT,
    generated_at: str | None = None,
) -> AgentMemoryScopeExportResult:
    payload = build_agent_memory_scope_contract(repo_root=repo_root, generated_at=generated_at)
    root = Path(export_root)
    if not root.is_absolute():
        root = Path(repo_root) / root
    root.mkdir(parents=True, exist_ok=True)
    json_path = root / JSON_EXPORT_NAME
    operator_path = root / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(format_agent_memory_scope_contract(payload), encoding="utf-8")
    return AgentMemoryScopeExportResult(
        schema_version=payload["schema_version"],
        json_path=json_path.as_posix(),
        operator_path=operator_path.as_posix(),
        actor_scope_count=len(payload["actor_memory_scopes"]),
        canonical_surface_count=len(payload["canonical_memory_surfaces"]),
        example_count=len(payload["example_memory_scope_decisions"]),
        runtime_authority_added=bool(payload["runtime_authority"]),
        hidden_memory_authority_added=bool(payload["hidden_memory_authority"]),
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export Agent Memory Scope Contract read-model.")
    parser.add_argument("--repo-root", default=ROOT.as_posix())
    parser.add_argument("--export-root", default=DEFAULT_EXPORT_ROOT.as_posix())
    parser.add_argument("--format", choices=("summary", "json", "operator"), default="summary")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    result = export_agent_memory_scope_contract(
        repo_root=args.repo_root,
        export_root=args.export_root,
    )
    if args.format == "json":
        print(stable_json(build_agent_memory_scope_contract(repo_root=args.repo_root)), end="")
    elif args.format == "operator":
        payload = build_agent_memory_scope_contract(repo_root=args.repo_root)
        print(format_agent_memory_scope_contract(payload), end="")
    else:
        print(
            stable_json(
                {
                    "schema_version": result.schema_version,
                    "json_path": result.json_path,
                    "operator_path": result.operator_path,
                    "actor_scope_count": result.actor_scope_count,
                    "canonical_surface_count": result.canonical_surface_count,
                    "example_count": result.example_count,
                    "runtime_authority_added": result.runtime_authority_added,
                    "hidden_memory_authority_added": result.hidden_memory_authority_added,
                }
            ),
            end="",
        )
    return 0


__all__ = [
    "CANONICAL_MEMORY_SURFACES",
    "JSON_EXPORT_NAME",
    "KNOWN_ACTOR_IDS",
    "MEMORY_SURFACE_TYPES",
    "NO_AUTHORITY_FLAGS",
    "NONCANONICAL_RESIDUE_SURFACES",
    "OPERATOR_EXPORT_NAME",
    "SCHEMA_VERSION",
    "SENSITIVITY_CLASSES",
    "build_agent_memory_scope_contract",
    "export_agent_memory_scope_contract",
    "format_agent_memory_scope_contract",
    "main",
    "stable_json",
]


if __name__ == "__main__":
    raise SystemExit(main())
