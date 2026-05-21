"""Memory Candidate Receipt Contract v0 for OpenClaw.

This read-model defines the receipt grammar for proposed memory candidates
before anything can be promoted into canonical OpenClaw memory. It is metadata
only: no model memory, hidden memory capture, autonomous memory capture, raw
chat ingestion, vector memory, canonical promotion authority, runtime
activation, tool execution, account access, network calls, or PC system-drive
writes are created.
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

SCHEMA_VERSION = "memory_candidate_receipt_contract_v0"
JSON_EXPORT_NAME = "memory_candidate_receipt_contract.json"
OPERATOR_EXPORT_NAME = "memory_candidate_receipt_contract_OPERATOR.md"

NO_AUTHORITY_FLAGS = {
    "runtime_authority": False,
    "model_memory_authority": False,
    "hidden_memory_authority": False,
    "autonomous_memory_capture": False,
    "raw_chat_ingestion_authority": False,
    "vector_memory_authority": False,
    "external_retained_memory_authority": False,
    "canonical_memory_promotion_authority": False,
    "tool_execution_authority": False,
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
    "broad_filesystem_indexing_enabled": False,
    "repo_b_mutation_enabled": False,
    "mission_control_app_authority_added": False,
    "mac_sync_or_import_triggered": False,
    "pc_c_drive_artifact_write_allowed": False,
    "operator_final_authority": True,
}

MEMORY_CANDIDATE_TYPES = (
    "OPERATOR_CONTEXT_CANDIDATE",
    "OPERATOR_CORRECTION_CANDIDATE",
    "OPERATOR_PREFERENCE_CANDIDATE",
    "PROJECT_FACT_CANDIDATE",
    "LANE_STATUS_CANDIDATE",
    "PROOF_GAP_CANDIDATE",
    "ARCHITECTURE_DOCTRINE_CANDIDATE",
    "ACTOR_ROUTING_CANDIDATE",
    "MODEL_POLICY_CANDIDATE",
    "TOOL_ADAPTER_CANDIDATE",
    "PACKAGE_TEMPLATE_CANDIDATE",
    "SAFETY_BOUNDARY_CANDIDATE",
    "WORKER_RESULT_CANDIDATE",
    "BUILD_VERIFICATION_CANDIDATE",
    "HOLDING_CELL_CANDIDATE",
    "WORLD_WORKFLOW_CANDIDATE",
    "CREATIVE_CONTEXT_CANDIDATE",
    "FINANCE_PROTECTED_CONTEXT_CANDIDATE",
    "BLOCKED_MEMORY_CANDIDATE",
)

CANDIDATE_STATES = (
    "OBSERVED_CONTEXT",
    "CANDIDATE_CAPTURED",
    "CANDIDATE_CLASSIFIED",
    "NEEDS_SOURCE_REFERENCE",
    "NEEDS_REDACTION",
    "NEEDS_OPERATOR_REVIEW",
    "NEEDS_GUARDIAN_REVIEW",
    "NEEDS_PROOF",
    "RECEIPT_READY",
    "APPROVED_FOR_PROMOTION",
    "PROMOTED_CANONICAL",
    "REJECTED",
    "STALE",
    "REVOKED",
    "QUARANTINED",
    "UNKNOWN_FAIL_CLOSED",
)

ALLOWED_SOURCE_CLASSES = (
    "operator_provided_statement",
    "read_model_summary",
    "stable_map_reference",
    "package_preview_reference",
    "receipt_reference",
    "redacted_source_card",
    "scoped_worker_report",
    "build_test_output_receipt",
    "screenshot_with_provenance",
    "canonical_surface_reference",
    "guardian_approved_protected_metadata",
)

BLOCKED_SOURCE_CLASSES = (
    "raw_chat_history_without_receipt",
    "hidden_model_memory",
    "assistant_scratchpad",
    "copilot_workspace_memory",
    "terminal_scrollback_without_receipt",
    "unbounded_repo_scan",
    "raw_private_file_body",
    "raw_gmail_calendar_coupa_telegram_body",
    "credentials_tokens_cookies",
    "browser_session_state",
    "broad_filesystem_index",
    "external_retained_memory",
    "stale_archive_without_review",
    "unknown_source",
)

CANDIDATE_RECEIPT_FIELDS = (
    "candidate_id",
    "receipt_id",
    "candidate_type",
    "candidate_state",
    "source_actor",
    "source_surface",
    "source_reference",
    "source_class",
    "captured_at",
    "captured_by",
    "package_id",
    "actor_id",
    "model_class",
    "tool_adapter_id",
    "source_excerpt_policy",
    "raw_body_included",
    "redaction_status",
    "sensitivity",
    "proof_status",
    "operator_gate_status",
    "guardian_gate_status",
    "destination_canonical_surface",
    "promotion_allowed",
    "promotion_blockers",
    "review_required_by",
    "expires_or_review_after",
    "staleness_rule",
    "revocation_status",
    "quarantine_status",
    "receipt_hash",
    "what_this_would_change",
    "why_it_matters",
    "what_would_make_it_canonical",
)

PROOF_STATUSES = (
    "NOT_PROOF_CONTEXT_ONLY",
    "PROOF_REFERENCE_PRESENT",
    "PROOF_METADATA_PRESENT",
    "PROOF_RECEIPT_PRESENT",
    "PROOF_CONFLICTED",
    "PROOF_MISSING",
    "PROOF_BLOCKED_PROTECTED",
    "PROOF_UNKNOWN_FAIL_CLOSED",
)

REDACTION_STATUSES = (
    "NO_REDACTION_NEEDED",
    "REDACTED_REFERENCE_ONLY",
    "REDACTED_EXCERPT_ALLOWED",
    "REDACTION_REQUIRED",
    "RAW_BODY_BLOCKED",
    "CREDENTIAL_SECRET_BLOCKED",
    "UNKNOWN_SENSITIVE_FAIL_CLOSED",
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

CANONICAL_MEMORY_SURFACES = (
    "vault",
    "handoff",
    "mac_eyes",
    "polish_loop",
    "CLAUDE.md",
    "generated_read_models",
    "stable_map_bundle",
    "approved_receipts_package_previews",
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
class CandidateStateDefinition:
    state_id: str
    meaning: str
    promotion_authority_created: bool
    package_use_allowed: bool


@dataclass(frozen=True)
class SourceClassPolicy:
    source_class: str
    status: str
    allowed_for_candidate: bool
    proof_posture: str
    required_gate: str


@dataclass(frozen=True)
class SensitivityPolicy:
    sensitivity: str
    allowed_source_classes: tuple[str, ...]
    allowed_actor_visibility: tuple[str, ...]
    required_redaction: str
    requires_guardian_gate: bool
    requires_operator_approval: bool
    external_model_eligibility: str
    promotion_rule: str


@dataclass(frozen=True)
class ActorCandidateRule:
    actor_id: str
    may_propose_candidate_types: tuple[str, ...]
    allowed_source_classes: tuple[str, ...]
    blocked_source_material: tuple[str, ...]
    review_required: tuple[str, ...]
    cannot_do: tuple[str, ...]
    mission_control_guidance: str


@dataclass(frozen=True)
class ExampleCandidateReceipt:
    example_id: str
    title: str
    candidate_type: str
    candidate_state: str
    source_actor: str
    source_class: str
    proof_status: str
    redaction_status: str
    sensitivity: str
    destination_canonical_surface: str
    promotion_allowed: bool
    promotion_blockers: tuple[str, ...]
    review_required_by: tuple[str, ...]
    what_this_would_change: str
    why_it_matters: str
    what_would_make_it_canonical: str


@dataclass(frozen=True)
class RecommendedLane:
    lane_id: str
    title: str
    priority: str
    why_next: str
    hard_boundary: str


@dataclass(frozen=True)
class MemoryCandidateReceiptExportResult:
    schema_version: str
    json_path: str
    operator_path: str
    candidate_type_count: int
    candidate_state_count: int
    example_count: int
    canonical_memory_promotion_authority_added: bool
    hidden_memory_authority_added: bool


EVIDENCE_SOURCES = (
    EvidenceSource(
        "agent_platform_alignment",
        "generated/read_models/agent_platform_alignment.json",
        "agent-platform primitive map",
    ),
    EvidenceSource(
        "agent_identity_actor_router_contract",
        "generated/read_models/agent_identity_actor_router_contract.json",
        "actor identities and routing boundaries",
    ),
    EvidenceSource(
        "model_selection_policy_contract",
        "generated/read_models/model_selection_policy_contract.json",
        "model and sensitivity policy",
    ),
    EvidenceSource(
        "agent_package_preview_contract",
        "generated/read_models/agent_package_preview_contract.json",
        "package preview context and gate policy",
    ),
    EvidenceSource(
        "agent_memory_scope_contract",
        "generated/read_models/agent_memory_scope_contract.json",
        "canonical/non-canonical memory scope doctrine",
    ),
    EvidenceSource(
        "tool_protocol_adapter_registry_contract",
        "generated/read_models/tool_protocol_adapter_registry_contract.json",
        "adapter receipt and candidate producer boundaries",
    ),
    EvidenceSource(
        "package_compiler_contract",
        "generated/read_models/package_compiler_contract.json",
        "package boundary validation and receipt requirements",
    ),
    EvidenceSource(
        "guardian_protected_access_gate_spec",
        "generated/read_models/guardian_protected_access_gate_spec.json",
        "Guardian protected-access gate posture",
    ),
    EvidenceSource(
        "protected_evidence_reference_receipt",
        "generated/read_models/protected_evidence_reference_receipt.json",
        "metadata-only protected evidence reference receipt posture",
    ),
    EvidenceSource(
        "stable_map_bundle_contract",
        "generated/read_models/operator_map_bundle_contract.json",
        "stable map bundle contract when present",
    ),
    EvidenceSource(
        "threshold_map_contract",
        "generated/read_models/operator_threshold_map_contract.json",
        "threshold and lane destiny contract",
    ),
)

STATE_DEFINITIONS = (
    CandidateStateDefinition("OBSERVED_CONTEXT", "Context was observed but is not yet a candidate receipt.", False, False),
    CandidateStateDefinition("CANDIDATE_CAPTURED", "A bounded candidate has been captured with required receipt fields started.", False, False),
    CandidateStateDefinition("CANDIDATE_CLASSIFIED", "Candidate type, source class, sensitivity, and destination have been classified.", False, False),
    CandidateStateDefinition("NEEDS_SOURCE_REFERENCE", "Candidate lacks a valid source reference.", False, False),
    CandidateStateDefinition("NEEDS_REDACTION", "Candidate needs redaction or reference-only handling before review.", False, False),
    CandidateStateDefinition("NEEDS_OPERATOR_REVIEW", "Candidate needs operator review before promotion can be considered.", False, False),
    CandidateStateDefinition("NEEDS_GUARDIAN_REVIEW", "Candidate needs Guardian review before promotion can be considered.", False, False),
    CandidateStateDefinition("NEEDS_PROOF", "Candidate needs machine proof or approved metadata before promotion.", False, False),
    CandidateStateDefinition("RECEIPT_READY", "Receipt has the required fields and can enter review.", False, True),
    CandidateStateDefinition("APPROVED_FOR_PROMOTION", "Review has approved future promotion; promotion execution is still outside this contract.", False, True),
    CandidateStateDefinition("PROMOTED_CANONICAL", "Possible future state after a separate promotion lane writes canonical memory.", False, True),
    CandidateStateDefinition("REJECTED", "Candidate has been rejected and must not drive packages as memory.", False, False),
    CandidateStateDefinition("STALE", "Candidate must be re-reviewed before use.", False, False),
    CandidateStateDefinition("REVOKED", "Candidate or promoted memory has been revoked and blocked downstream.", False, False),
    CandidateStateDefinition("QUARANTINED", "Candidate is isolated due to risk, contradiction, leakage, or malformed proof.", False, False),
    CandidateStateDefinition("UNKNOWN_FAIL_CLOSED", "Candidate cannot be trusted and fails closed.", False, False),
)

SOURCE_CLASS_POLICIES = tuple(
    SourceClassPolicy(source_class, "allowed_bounded", True, "context_or_metadata_reference", "none_or_context_gate")
    for source_class in ALLOWED_SOURCE_CLASSES
) + tuple(
    SourceClassPolicy(source_class, "blocked_or_non_authoritative", False, "not_proof", "operator_or_guardian_reclassification_required")
    for source_class in BLOCKED_SOURCE_CLASSES
)

SENSITIVITY_POLICIES = (
    SensitivityPolicy(
        "PUBLIC_OR_LOW",
        ("operator_provided_statement", "read_model_summary", "stable_map_reference", "receipt_reference"),
        ("operator_winship", "chief", "guardian", "hermes", "codex", "gemini_antigravity"),
        "NO_REDACTION_NEEDED",
        False,
        False,
        "future_eligible_after_package_preview",
        "may promote after valid source/reference receipt and operator review if needed",
    ),
    SensitivityPolicy(
        "INTERNAL_SYSTEM",
        ("read_model_summary", "stable_map_reference", "package_preview_reference", "receipt_reference", "scoped_worker_report"),
        ("operator_winship", "chief", "guardian", "hermes", "codex"),
        "REDACTED_REFERENCE_ONLY",
        False,
        True,
        "future_eligible_after_package_preview_and_no_private_context",
        "requires receipt and operator promotion into approved surface",
    ),
    SensitivityPolicy(
        "CREATIVE_PRIVATE",
        ("operator_provided_statement", "redacted_source_card", "canonical_surface_reference", "scoped_worker_report"),
        ("operator_winship", "niles", "guardian", "codex"),
        "REDACTED_REFERENCE_ONLY",
        False,
        True,
        "blocked_until_context_packet_and_operator_gate",
        "requires project capsule/source refs and operator promotion",
    ),
    SensitivityPolicy(
        "CLIENT_PRIVATE",
        ("redacted_source_card", "receipt_reference", "guardian_approved_protected_metadata"),
        ("operator_winship", "guardian"),
        "REDACTION_REQUIRED",
        True,
        True,
        "blocked",
        "requires Guardian review, operator approval, and protected metadata only",
    ),
    SensitivityPolicy(
        "FINANCE_PROTECTED",
        ("receipt_reference", "redacted_source_card", "guardian_approved_protected_metadata"),
        ("operator_winship", "guardian", "cassandra"),
        "REDACTED_REFERENCE_ONLY",
        True,
        True,
        "blocked",
        "requires protected proof metadata, Guardian review, and operator approval",
    ),
    SensitivityPolicy(
        "CREDENTIAL_OR_SECRET",
        (),
        ("operator_winship", "guardian"),
        "CREDENTIAL_SECRET_BLOCKED",
        True,
        True,
        "blocked",
        "must never be promoted; quarantine and revoke any candidate containing it",
    ),
    SensitivityPolicy(
        "ACCOUNT_ACCESS",
        (),
        ("operator_winship", "guardian"),
        "RAW_BODY_BLOCKED",
        True,
        True,
        "blocked",
        "must not be stored as memory; use future protected access receipts only",
    ),
    SensitivityPolicy(
        "LEGAL_OR_COMPLIANCE",
        ("receipt_reference", "redacted_source_card", "guardian_approved_protected_metadata"),
        ("operator_winship", "guardian"),
        "REDACTION_REQUIRED",
        True,
        True,
        "blocked",
        "requires protected metadata, Guardian review, operator approval, and compliance posture",
    ),
    SensitivityPolicy(
        "UNKNOWN_SENSITIVE_FAIL_CLOSED",
        (),
        ("operator_winship", "guardian"),
        "UNKNOWN_SENSITIVE_FAIL_CLOSED",
        True,
        True,
        "blocked",
        "cannot promote until sensitivity is classified",
    ),
)

ACTOR_CANDIDATE_RULES = (
    ActorCandidateRule(
        "operator_winship",
        (
            "OPERATOR_CONTEXT_CANDIDATE",
            "OPERATOR_CORRECTION_CANDIDATE",
            "OPERATOR_PREFERENCE_CANDIDATE",
            "PROJECT_FACT_CANDIDATE",
            "CREATIVE_CONTEXT_CANDIDATE",
            "WORLD_WORKFLOW_CANDIDATE",
            "HOLDING_CELL_CANDIDATE",
            "PROOF_GAP_CANDIDATE",
        ),
        ("operator_provided_statement", "canonical_surface_reference", "stable_map_reference", "receipt_reference"),
        ("credentials/tokens/cookies", "raw protected bodies without gate", "hidden memory dumps"),
        ("operator review when promotion changes canonical memory", "Guardian review when sensitive/protected"),
        ("make a fact machine-proof by statement alone", "authorize execution by memory statement", "bypass security audit"),
        "Show operator memory as context/candidate until proof or promotion receipts exist.",
    ),
    ActorCandidateRule(
        "chief",
        ("LANE_STATUS_CANDIDATE", "PROOF_GAP_CANDIDATE", "BUILD_VERIFICATION_CANDIDATE", "WORKER_RESULT_CANDIDATE"),
        ("read_model_summary", "stable_map_reference", "receipt_reference", "build_test_output_receipt", "scoped_worker_report"),
        ("private raw bodies", "credentials", "repair/remount/delete claims"),
        ("operator review for promotion",),
        ("self-promote", "self-authorize repairs", "treat missing proof as proof"),
        "Chief may propose diagnostic posture, lane status, proof gaps, and source conflicts.",
    ),
    ActorCandidateRule(
        "guardian",
        ("SAFETY_BOUNDARY_CANDIDATE", "PROOF_GAP_CANDIDATE", "BLOCKED_MEMORY_CANDIDATE"),
        ("receipt_reference", "guardian_approved_protected_metadata", "read_model_summary", "redacted_source_card"),
        ("raw secrets", "credential storage", "approval execution"),
        ("operator review for promotion", "Guardian review record for sensitive/protected posture"),
        ("self-authorize execution", "bypass operator", "store raw secrets"),
        "Guardian may propose safety boundaries, redaction requirements, quarantine, revocation, and protected-access posture.",
    ),
    ActorCandidateRule(
        "cassandra",
        ("FINANCE_PROTECTED_CONTEXT_CANDIDATE", "PROJECT_FACT_CANDIDATE", "WORLD_WORKFLOW_CANDIDATE", "PROOF_GAP_CANDIDATE"),
        ("receipt_reference", "redacted_source_card", "guardian_approved_protected_metadata", "read_model_summary"),
        ("raw Coupa/Gmail/calendar bodies", "credentials", "send/submit/approval claims"),
        ("Guardian review for finance/comms protected context", "operator review for promotion"),
        ("send", "submit", "approve", "access accounts", "self-promote finance facts"),
        "Cassandra may propose finance/comms candidates from approved metadata/proof refs only.",
    ),
    ActorCandidateRule(
        "hermes",
        ("ARCHITECTURE_DOCTRINE_CANDIDATE", "PROJECT_FACT_CANDIDATE", "HOLDING_CELL_CANDIDATE"),
        ("read_model_summary", "stable_map_reference", "package_preview_reference", "receipt_reference", "redacted_source_card"),
        ("private raw chat bodies", "client/legal/finance raw docs", "credentials"),
        ("operator review for doctrine promotion",),
        ("promote doctrine unilaterally", "ingest broad history", "claim authority from prose"),
        "Hermes may propose architecture/doctrine/system-coherence candidates with receipt/promotion review.",
    ),
    ActorCandidateRule(
        "niles",
        ("CREATIVE_CONTEXT_CANDIDATE", "WORLD_WORKFLOW_CANDIDATE", "PROJECT_FACT_CANDIDATE"),
        ("operator_provided_statement", "canonical_surface_reference", "redacted_source_card", "scoped_worker_report"),
        ("unrelated private/client material", "account sessions", "credentials"),
        ("operator review for promotion", "Guardian review if rights/sensitivity is protected"),
        ("treat creative preference as machine proof", "publish/release/account action", "self-promote"),
        "Niles may propose creative/music/art context candidates; preference guides scoped work but is not proof.",
    ),
    ActorCandidateRule(
        "codex",
        ("BUILD_VERIFICATION_CANDIDATE", "WORKER_RESULT_CANDIDATE", "PROJECT_FACT_CANDIDATE", "PROOF_GAP_CANDIDATE"),
        ("scoped_worker_report", "build_test_output_receipt", "receipt_reference", "read_model_summary", "package_preview_reference"),
        ("hidden IDE/Copilot memory", "assistant scratchpad", "credentials", "broad filesystem scan"),
        ("operator review for promotion", "Guardian review when sensitive/protected"),
        ("use hidden IDE memory as proof", "self-promote", "expand scope", "write canonical memory"),
        "Codex candidates need scoped file refs, command/test output refs, and package boundary refs.",
    ),
    ActorCandidateRule(
        "gemini_antigravity",
        ("WORKER_RESULT_CANDIDATE", "BUILD_VERIFICATION_CANDIDATE", "PROJECT_FACT_CANDIDATE"),
        ("scoped_worker_report", "package_preview_reference", "receipt_reference", "redacted_source_card"),
        ("external retained memory", "raw protected material", "broad context", "direct canonical writes"),
        ("operator review for promotion", "Guardian review for external/sensitive posture"),
        ("retain memory", "write canonical surfaces", "treat output as truth without receipt"),
        "Gemini/Antigravity output is a package-bounded receipt candidate, not canonical truth.",
    ),
)

EXAMPLE_CANDIDATES = (
    ExampleCandidateReceipt(
        "operator_capital_hilton_coupa_excel",
        "Operator says Capital Hilton uses Coupa and Excel",
        "OPERATOR_CONTEXT_CANDIDATE",
        "NEEDS_PROOF",
        "operator_winship",
        "operator_provided_statement",
        "NOT_PROOF_CONTEXT_ONLY",
        "REDACTED_REFERENCE_ONLY",
        "FINANCE_PROTECTED",
        "vault",
        False,
        ("protected proof metadata missing", "Guardian review required", "operator statement is context not proof"),
        ("operator_winship", "guardian"),
        "Would label Capital Hilton invoice workflow terrain for future Finance World package context.",
        "It points OpenClaw toward the right proof lane without accessing Coupa or Excel.",
        "Protected proof metadata, Guardian review, operator approval, and a promotion receipt.",
    ),
    ExampleCandidateReceipt(
        "codex_build_succeeded",
        "Codex reports build succeeded",
        "BUILD_VERIFICATION_CANDIDATE",
        "RECEIPT_READY",
        "codex",
        "build_test_output_receipt",
        "PROOF_RECEIPT_PRESENT",
        "NO_REDACTION_NEEDED",
        "INTERNAL_SYSTEM",
        "approved_receipts_package_previews",
        False,
        ("promotion authority is outside this contract",),
        ("operator_winship",),
        "Would add a build/test proof candidate tied to a package lane.",
        "It can support package validation only when command/output/file-change refs exist.",
        "Command, output, file-change refs, package boundary refs, and operator promotion if canonicalized.",
    ),
    ExampleCandidateReceipt(
        "gpt_doctrine_correction",
        "GPT-5.5 suggests doctrine correction",
        "ARCHITECTURE_DOCTRINE_CANDIDATE",
        "NEEDS_OPERATOR_REVIEW",
        "hermes",
        "scoped_worker_report",
        "NOT_PROOF_CONTEXT_ONLY",
        "NO_REDACTION_NEEDED",
        "INTERNAL_SYSTEM",
        "handoff",
        False,
        ("operator approval required", "canonical destination review required"),
        ("operator_winship",),
        "Would refine doctrine only after operator/orchestrator approval and canonical promotion.",
        "Doctrine corrections can improve future packages but must not become truth automatically.",
        "Operator approval, source refs, destination surface, and promotion receipt.",
    ),
    ExampleCandidateReceipt(
        "gemini_visual_polish_notes",
        "Gemini/Antigravity visual polish notes",
        "WORKER_RESULT_CANDIDATE",
        "CANDIDATE_CAPTURED",
        "gemini_antigravity",
        "scoped_worker_report",
        "NOT_PROOF_CONTEXT_ONLY",
        "NO_REDACTION_NEEDED",
        "INTERNAL_SYSTEM",
        "polish_loop",
        False,
        ("operator acceptance missing", "no canonical promotion receipt"),
        ("operator_winship",),
        "Would provide a review candidate for UI polish lanes.",
        "Worker notes may guide design work but are not canonical unless accepted/promoted.",
        "Operator acceptance, source refs, and promotion receipt.",
    ),
    ExampleCandidateReceipt(
        "copilot_old_project_note",
        "Copilot workspace memory has old project note",
        "BLOCKED_MEMORY_CANDIDATE",
        "NEEDS_SOURCE_REFERENCE",
        "codex",
        "copilot_workspace_memory",
        "PROOF_MISSING",
        "UNKNOWN_SENSITIVE_FAIL_CLOSED",
        "UNKNOWN_SENSITIVE_FAIL_CLOSED",
        "handoff",
        False,
        ("non-canonical residue", "source reference missing", "sensitivity unknown"),
        ("operator_winship", "guardian"),
        "Would not change canonical memory until re-referenced from an approved source.",
        "Old workspace residue can be useful as a pointer but cannot be truth.",
        "Approved source reference, sensitivity classification, and operator promotion.",
    ),
    ExampleCandidateReceipt(
        "private_email_body_mentioned",
        "Private email body mentioned",
        "BLOCKED_MEMORY_CANDIDATE",
        "NEEDS_REDACTION",
        "cassandra",
        "raw_gmail_calendar_coupa_telegram_body",
        "PROOF_BLOCKED_PROTECTED",
        "RAW_BODY_BLOCKED",
        "CLIENT_PRIVATE",
        "vault",
        False,
        ("raw body blocked", "Guardian review required", "redacted source card missing"),
        ("operator_winship", "guardian"),
        "Would be blocked until a redacted source-card candidate exists.",
        "Private email bodies must not become hidden memory or package context by default.",
        "Guardian-approved redacted source card, protected metadata receipt, and operator approval.",
    ),
    ExampleCandidateReceipt(
        "niles_creative_preference",
        "Niles creative preference from Operator",
        "CREATIVE_CONTEXT_CANDIDATE",
        "CANDIDATE_CAPTURED",
        "operator_winship",
        "operator_provided_statement",
        "NOT_PROOF_CONTEXT_ONLY",
        "REDACTED_REFERENCE_ONLY",
        "CREATIVE_PRIVATE",
        "vault",
        False,
        ("operator promotion receipt missing",),
        ("operator_winship",),
        "Would guide scoped Niles creative work.",
        "Creative preference is valid context but not machine proof.",
        "Project capsule reference, operator promotion, and review/staleness policy.",
    ),
    ExampleCandidateReceipt(
        "coupa_future_gated_tool_adapter",
        "Tool adapter registry says Coupa is future-gated",
        "SAFETY_BOUNDARY_CANDIDATE",
        "RECEIPT_READY",
        "guardian",
        "read_model_summary",
        "PROOF_REFERENCE_PRESENT",
        "NO_REDACTION_NEEDED",
        "FINANCE_PROTECTED",
        "generated_read_models",
        False,
        ("promotion authority is outside this contract", "Finance security gate still required"),
        ("operator_winship", "guardian"),
        "Would preserve Coupa as blocked/future-gated adapter posture.",
        "It prevents package previews from implying Coupa access before security audit.",
        "Reference to tool adapter registry, Guardian review, and promotion receipt.",
    ),
)

RECOMMENDED_NEXT_LANES = (
    RecommendedLane(
        "model_selection_receipt_v0",
        "Model Selection Receipt v0",
        "P1",
        "Model posture needs a deterministic decision receipt before future model routing.",
        "receipt metadata only; no model call",
    ),
    RecommendedLane(
        "package_preview_receipt_v0",
        "Package Preview Receipt v0",
        "P1",
        "Package previews need receipts before any future copy/open/launch path exists.",
        "receipt metadata only; no dispatch",
    ),
    RecommendedLane(
        "mission_control_package_preview_actor_routing_surface_v0",
        "Mission Control Package Preview / Actor Routing Surface v0",
        "P2",
        "Mission Control can show candidate context in package preview without executing tools.",
        "Mac read-only UI; no backend command authority",
    ),
    RecommendedLane(
        "tool_adapter_receipt_v0",
        "Tool Adapter Receipt v0",
        "P2",
        "Future tool adapter attempts need a receipt grammar tied to this candidate contract.",
        "receipt metadata only; no live tool execution",
    ),
    RecommendedLane(
        "memory_review_promotion_surface_v0",
        "Memory Review / Promotion Surface v0",
        "P3",
        "Memory candidates need a read-only operator review surface before any promotion lane.",
        "read-only UI/contract lane; no canonical mutation",
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


def _state_definition_record(state: CandidateStateDefinition) -> dict[str, Any]:
    return {
        "state_id": state.state_id,
        "meaning": state.meaning,
        "promotion_authority_created": state.promotion_authority_created,
        "package_use_allowed": state.package_use_allowed,
    }


def _source_class_record(policy: SourceClassPolicy) -> dict[str, Any]:
    return {
        "source_class": policy.source_class,
        "status": policy.status,
        "allowed_for_candidate": policy.allowed_for_candidate,
        "proof_posture": policy.proof_posture,
        "required_gate": policy.required_gate,
    }


def _sensitivity_record(policy: SensitivityPolicy) -> dict[str, Any]:
    return {
        "sensitivity": policy.sensitivity,
        "allowed_source_classes": list(policy.allowed_source_classes),
        "allowed_actor_visibility": list(policy.allowed_actor_visibility),
        "required_redaction": policy.required_redaction,
        "requires_guardian_gate": policy.requires_guardian_gate,
        "requires_operator_approval": policy.requires_operator_approval,
        "external_model_eligibility": policy.external_model_eligibility,
        "promotion_rule": policy.promotion_rule,
    }


def _actor_rule_record(rule: ActorCandidateRule) -> dict[str, Any]:
    return {
        "actor_id": rule.actor_id,
        "may_propose_candidate_types": list(rule.may_propose_candidate_types),
        "allowed_source_classes": list(rule.allowed_source_classes),
        "blocked_source_material": list(rule.blocked_source_material),
        "review_required": list(rule.review_required),
        "cannot_do": list(rule.cannot_do),
        "mission_control_guidance": rule.mission_control_guidance,
        "can_write_canonical_memory_directly": False,
        "can_self_promote": False,
    }


def _example_record(example: ExampleCandidateReceipt) -> dict[str, Any]:
    return {
        "candidate_id": example.example_id,
        "receipt_id": f"receipt_{example.example_id}",
        "example_id": example.example_id,
        "title": example.title,
        "candidate_type": example.candidate_type,
        "candidate_state": example.candidate_state,
        "source_actor": example.source_actor,
        "source_surface": "operator_provided_context_or_contract_ref",
        "source_reference": f"example://{example.example_id}",
        "source_class": example.source_class,
        "captured_at": "example_static_timestamp",
        "captured_by": "memory_candidate_receipt_contract_v0",
        "package_id": None,
        "actor_id": example.source_actor,
        "model_class": "blocked_no_model",
        "tool_adapter_id": None,
        "source_excerpt_policy": "reference_or_redacted_excerpt_only",
        "raw_body_included": False,
        "redaction_status": example.redaction_status,
        "sensitivity": example.sensitivity,
        "proof_status": example.proof_status,
        "operator_gate_status": "required_if_promotion_requested",
        "guardian_gate_status": "required_if_sensitive_or_protected",
        "destination_canonical_surface": example.destination_canonical_surface,
        "promotion_allowed": example.promotion_allowed,
        "promotion_blockers": list(example.promotion_blockers),
        "review_required_by": list(example.review_required_by),
        "expires_or_review_after": "requires_review_before_package_use",
        "staleness_rule": "stale_if_source_or_operator_intent_changes",
        "revocation_status": "not_revoked",
        "quarantine_status": "not_quarantined",
        "receipt_hash": "example_hash_computed_in_real_receipt",
        "what_this_would_change": example.what_this_would_change,
        "why_it_matters": example.why_it_matters,
        "what_would_make_it_canonical": example.what_would_make_it_canonical,
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


def build_memory_candidate_receipt_contract(
    *,
    repo_root: str | Path = ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    evidence_sources = [_source_record(source, repo_root=repo_root) for source in EVIDENCE_SOURCES]
    examples = [_example_record(example) for example in EXAMPLE_CANDIDATES]
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": "memory_candidate_receipt_contract",
        "generated_at": generated_at,
        **NO_AUTHORITY_FLAGS,
        "contract_status": "deterministic_memory_candidate_receipt_metadata_only",
        "operator_summary": (
            "OpenClaw now has a deterministic receipt grammar for proposed memory candidates. A candidate can be "
            "captured, classified, reviewed, rejected, stale, revoked, or quarantined, but it is not canonical memory "
            "until a separate future promotion lane approves it into an allowed surface with proof and receipts."
        ),
        "evidence_sources": evidence_sources,
        "memory_candidate_definition": {
            "what_is_a_memory_candidate": "A bounded proposed memory item with source refs, sensitivity, proof, redaction, review, destination, and receipt posture.",
            "candidate_is_canonical_memory": False,
            "worker_output_is_truth": False,
            "operator_memory_is_machine_proof": False,
            "promotion_execution_authority_created": False,
            "canonical_surfaces": list(CANONICAL_MEMORY_SURFACES),
            "noncanonical_residue_rule": "non-canonical residue remains non-authoritative unless re-referenced, reviewed, and promoted with receipts",
        },
        "candidate_types": [
            {
                "candidate_type": candidate_type,
                "description": _candidate_type_description(candidate_type),
            }
            for candidate_type in MEMORY_CANDIDATE_TYPES
        ],
        "candidate_states": [_state_definition_record(state) for state in STATE_DEFINITIONS],
        "source_class_policy": {
            "allowed_source_classes": list(ALLOWED_SOURCE_CLASSES),
            "blocked_or_non_authoritative_source_classes": list(BLOCKED_SOURCE_CLASSES),
            "source_classes": [_source_class_record(policy) for policy in SOURCE_CLASS_POLICIES],
            "unknown_source_result": "UNKNOWN_FAIL_CLOSED",
        },
        "candidate_receipt_schema": {
            "required_fields": list(CANDIDATE_RECEIPT_FIELDS),
            "raw_body_included_must_default_false": True,
            "receipt_hash_required": True,
            "natural_language_claim_counts_as_proof": False,
            "missing_required_field_result": "UNKNOWN_FAIL_CLOSED",
        },
        "proof_status_model": {
            "proof_statuses": list(PROOF_STATUSES),
            "rules": [
                "Operator statement may be context but not machine proof.",
                "Worker output may be receipt candidate but not proof without command/output/file-change evidence.",
                "Protected finance/client/account context requires metadata/proof references, not raw bodies.",
                "Conflicting proof blocks promotion.",
            ],
            "promotion_blocked_by": ["PROOF_CONFLICTED", "PROOF_MISSING", "PROOF_BLOCKED_PROTECTED", "PROOF_UNKNOWN_FAIL_CLOSED"],
        },
        "redaction_policy": {
            "redaction_statuses": list(REDACTION_STATUSES),
            "rules": [
                "References are preferred over raw bodies.",
                "Hashes and receipts are preferred over full content.",
                "Raw private bodies are blocked by default.",
                "Credentials, tokens, cookies, OAuth state, browser sessions, and account secrets must never be candidates.",
                "Finance/client/legal/protected material requires Guardian review and redaction.",
            ],
            "blocked_redaction_statuses": ["RAW_BODY_BLOCKED", "CREDENTIAL_SECRET_BLOCKED", "UNKNOWN_SENSITIVE_FAIL_CLOSED"],
        },
        "sensitivity_policy": {
            "sensitivity_classes": list(SENSITIVITY_CLASSES),
            "classes": [_sensitivity_record(policy) for policy in SENSITIVITY_POLICIES],
            "unknown_sensitivity_result": "UNKNOWN_SENSITIVE_FAIL_CLOSED",
            "external_model_default": "blocked unless package, model policy, operator, Guardian, and receipt gates permit",
        },
        "promotion_gate_policy": {
            "promotion_requires": [
                "valid source reference",
                "candidate classification",
                "sensitivity classification",
                "redaction status",
                "proof status",
                "destination canonical surface",
                "Operator approval where required",
                "Guardian approval where required",
                "receipt hash",
                "staleness/review policy",
                "no blocked source material",
                "no unresolved proof conflict",
            ],
            "promotion_blocked_if": [
                "source unknown",
                "raw private body included without gate",
                "credential/secret material present",
                "sensitivity unknown",
                "proof missing where proof required",
                "candidate contradicts existing canonical proof",
                "Guardian gate fails",
                "Operator approval required but absent",
                "external retained memory is involved",
                "candidate attempts to authorize runtime/tool/model/account access",
            ],
            "this_contract_promotes_memory": False,
            "PROMOTED_CANONICAL_is_future_state_only": True,
        },
        "revocation_staleness_quarantine_policy": {
            "who_can_request_revocation": ["operator_winship", "guardian", "chief when proof conflict is detected"],
            "what_can_be_revoked": ["candidate receipt", "promotion decision", "package use of candidate context", "future promoted memory reference"],
            "stale_when": ["source changed", "operator intent changed", "proof expired", "review date passed", "conflict detected"],
            "downstream_package_rule": "revoked, stale, or quarantined candidates must not be used as package context without re-review",
            "quarantine_triggers": [
                "credential/secret exposure",
                "raw private body exposure",
                "source cannot be verified",
                "worker claims authority it did not have",
                "model claims hidden memory",
                "contradiction with canonical proof",
                "sensitivity misclassification",
                "malformed receipt",
                "missing receipt hash",
                "failed Guardian review",
                "failed Operator review",
                "suspicious broad capture",
            ],
            "quarantine_is_non_destructive": True,
        },
        "actor_candidate_rules": [_actor_rule_record(rule) for rule in ACTOR_CANDIDATE_RULES],
        "example_candidate_receipts": examples,
        "relationship_to_existing_contracts": {
            "agent_platform_alignment": "defines the agent-platform primitive landscape",
            "agent_identity_actor_router_contract": "defines who may propose candidates and routing posture",
            "model_selection_policy_contract": "defines model-class sensitivity eligibility before candidate context is exposed",
            "agent_package_preview_contract": "defines how candidate context appears before action",
            "agent_memory_scope_contract": "defines what may be seen or remembered",
            "tool_protocol_adapter_registry_contract": "defines which adapters may produce receipt candidates",
            "stable_map_bundle": "may carry a summary of candidate receipt posture in a later refresh",
            "threshold_map_contract": "can reference memory candidates for missing terrain without treating memory as proof",
            "guardian_protected_access_gate_spec": "gates sensitive/protected candidates",
        },
        "mission_control_surface_guidance": {
            "memory_candidate_inbox": [
                "pending candidates",
                "candidate type",
                "source actor",
                "sensitivity",
                "proof status",
                "redaction status",
                "required review",
                "destination surface",
                "promotion blockers",
            ],
            "candidate_detail": [
                "what this would change",
                "why it matters",
                "source reference",
                "proof vs context distinction",
                "required gates",
                "staleness/revocation status",
                "quarantine status",
            ],
            "package_preview_memory_section": [
                "candidate context included",
                "candidate context excluded",
                "blocked memory surfaces",
                "redactions",
                "sensitivity",
                "Guardian/Operator review needs",
            ],
            "hide_or_block": [
                "raw private bodies",
                "credentials/secrets/tokens",
                "raw chat archives",
                "hidden memory dumps",
                "broad filesystem indexes",
                "raw Gmail/calendar/Coupa/Telegram bodies",
                "fake confidence percentages",
                "direct promote memory controls without gates",
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
                "contract_id": "memory_candidate_receipt_contract",
                "candidate_types_count": len(MEMORY_CANDIDATE_TYPES),
                "candidate_states": list(CANDIDATE_STATES),
                "blocked_candidate_states": ["REJECTED", "STALE", "REVOKED", "QUARANTINED", "UNKNOWN_FAIL_CLOSED"],
                "next_recommended_lane": "model_selection_receipt_v0",
            },
            "next_map_bundle_refresh_requirement": "Include this summary in the next stable map bundle refresh after this contract lands.",
        },
        "recommended_next_lanes": [_recommended_lane_record(lane) for lane in RECOMMENDED_NEXT_LANES],
        "machine_proof": {
            "source_read_models_present": {source["source_id"]: source["present"] for source in evidence_sources},
            "candidate_type_count": len(MEMORY_CANDIDATE_TYPES),
            "candidate_state_count": len(CANDIDATE_STATES),
            "receipt_required_field_count": len(CANDIDATE_RECEIPT_FIELDS),
            "example_candidate_ids": [example["candidate_id"] for example in examples],
            "canonical_memory_written_now": False,
            "canonical_memory_promotion_authority_added": False,
            "model_memory_created_now": False,
            "hidden_memory_capture_added": False,
            "raw_chat_ingested": False,
            "vector_memory_added": False,
            "external_retained_memory_added": False,
            "runtime_activation_added": False,
            "content_hash": None,
        },
    }
    payload["machine_proof"]["content_hash"] = _content_hash(payload)
    return payload


def _candidate_type_description(candidate_type: str) -> str:
    descriptions = {
        "OPERATOR_CONTEXT_CANDIDATE": "Operator-provided context that may guide later work but is not proof.",
        "OPERATOR_CORRECTION_CANDIDATE": "Operator correction to a label, framing, status, or doctrine.",
        "OPERATOR_PREFERENCE_CANDIDATE": "Operator taste or workflow preference eligible for review.",
        "PROJECT_FACT_CANDIDATE": "Project fact candidate requiring source/proof before canonical use.",
        "LANE_STATUS_CANDIDATE": "Lane state or readiness candidate.",
        "PROOF_GAP_CANDIDATE": "Known missing proof or source gap.",
        "ARCHITECTURE_DOCTRINE_CANDIDATE": "Architecture or doctrine rule candidate.",
        "ACTOR_ROUTING_CANDIDATE": "Actor/routing rule candidate.",
        "MODEL_POLICY_CANDIDATE": "Model-selection policy candidate.",
        "TOOL_ADAPTER_CANDIDATE": "Tool adapter state or capability candidate.",
        "PACKAGE_TEMPLATE_CANDIDATE": "Package template or field candidate.",
        "SAFETY_BOUNDARY_CANDIDATE": "Safety, authority, redaction, or protected-access boundary candidate.",
        "WORKER_RESULT_CANDIDATE": "Worker result candidate requiring source/receipt review.",
        "BUILD_VERIFICATION_CANDIDATE": "Build/test verification candidate requiring command/output receipt.",
        "HOLDING_CELL_CANDIDATE": "Premature but valid idea or lane parked for later review.",
        "WORLD_WORKFLOW_CANDIDATE": "Domain/world workflow memory candidate.",
        "CREATIVE_CONTEXT_CANDIDATE": "Music/art/creative context candidate.",
        "FINANCE_PROTECTED_CONTEXT_CANDIDATE": "Finance/AP/protected context candidate requiring Guardian review.",
        "BLOCKED_MEMORY_CANDIDATE": "Blocked or unsafe memory candidate that must not drive packages.",
    }
    return descriptions[candidate_type]


def format_memory_candidate_receipt_contract(payload: dict[str, Any]) -> str:
    lines = [
        "# Memory Candidate Receipt Contract v0",
        "",
        "## Operator Summary",
        payload["operator_summary"],
        "",
        "## Candidate Types",
    ]
    for item in payload["candidate_types"]:
        lines.append(f"- `{item['candidate_type']}`: {item['description']}")
    lines.extend(["", "## Candidate States"])
    for state in payload["candidate_states"]:
        lines.append(f"- `{state['state_id']}`: {state['meaning']}")
    lines.extend(["", "## Receipt Fields"])
    for field in payload["candidate_receipt_schema"]["required_fields"]:
        lines.append(f"- `{field}`")
    lines.extend(["", "## Proof / Redaction"])
    lines.append("- Operator statements are context, not machine proof.")
    lines.append("- Worker output requires command/output/file-change evidence before it can serve as proof.")
    lines.append("- Raw private bodies and credentials/secrets are blocked by default.")
    lines.extend(["", "## Promotion / Review"])
    for item in payload["promotion_gate_policy"]["promotion_requires"]:
        lines.append(f"- Requires: {item}")
    lines.append("- This contract does not promote memory.")
    lines.extend(["", "## Actor Candidate Rules"])
    for rule in payload["actor_candidate_rules"]:
        lines.append(
            f"- `{rule['actor_id']}`: may propose {len(rule['may_propose_candidate_types'])} candidate types; "
            f"cannot {', '.join(rule['cannot_do'])}."
        )
    lines.extend(["", "## Mission Control Guidance"])
    lines.append("- Show candidate inbox, proof/context distinction, gates, blockers, staleness, revocation, and quarantine.")
    lines.append("- Hide raw private bodies, credentials, raw chat archives, hidden memory dumps, broad indexes, and direct ungated promotion controls.")
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


def export_memory_candidate_receipt_contract(
    *,
    repo_root: str | Path = ROOT,
    export_root: str | Path = DEFAULT_EXPORT_ROOT,
    generated_at: str | None = None,
) -> MemoryCandidateReceiptExportResult:
    payload = build_memory_candidate_receipt_contract(repo_root=repo_root, generated_at=generated_at)
    root = Path(export_root)
    if not root.is_absolute():
        root = Path(repo_root) / root
    root.mkdir(parents=True, exist_ok=True)
    json_path = root / JSON_EXPORT_NAME
    operator_path = root / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(format_memory_candidate_receipt_contract(payload), encoding="utf-8")
    return MemoryCandidateReceiptExportResult(
        schema_version=payload["schema_version"],
        json_path=json_path.as_posix(),
        operator_path=operator_path.as_posix(),
        candidate_type_count=len(payload["candidate_types"]),
        candidate_state_count=len(payload["candidate_states"]),
        example_count=len(payload["example_candidate_receipts"]),
        canonical_memory_promotion_authority_added=bool(payload["canonical_memory_promotion_authority"]),
        hidden_memory_authority_added=bool(payload["hidden_memory_authority"]),
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export Memory Candidate Receipt Contract read-model.")
    parser.add_argument("--repo-root", default=ROOT.as_posix())
    parser.add_argument("--export-root", default=DEFAULT_EXPORT_ROOT.as_posix())
    parser.add_argument("--format", choices=("summary", "json", "operator"), default="summary")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    result = export_memory_candidate_receipt_contract(repo_root=args.repo_root, export_root=args.export_root)
    if args.format == "json":
        print(stable_json(build_memory_candidate_receipt_contract(repo_root=args.repo_root)), end="")
    elif args.format == "operator":
        payload = build_memory_candidate_receipt_contract(repo_root=args.repo_root)
        print(format_memory_candidate_receipt_contract(payload), end="")
    else:
        print(
            stable_json(
                {
                    "schema_version": result.schema_version,
                    "json_path": result.json_path,
                    "operator_path": result.operator_path,
                    "candidate_type_count": result.candidate_type_count,
                    "candidate_state_count": result.candidate_state_count,
                    "example_count": result.example_count,
                    "canonical_memory_promotion_authority_added": result.canonical_memory_promotion_authority_added,
                    "hidden_memory_authority_added": result.hidden_memory_authority_added,
                }
            ),
            end="",
        )
    return 0


__all__ = [
    "ALLOWED_SOURCE_CLASSES",
    "BLOCKED_SOURCE_CLASSES",
    "CANONICAL_MEMORY_SURFACES",
    "CANDIDATE_RECEIPT_FIELDS",
    "CANDIDATE_STATES",
    "JSON_EXPORT_NAME",
    "KNOWN_ACTOR_IDS",
    "MEMORY_CANDIDATE_TYPES",
    "NO_AUTHORITY_FLAGS",
    "OPERATOR_EXPORT_NAME",
    "PROOF_STATUSES",
    "REDACTION_STATUSES",
    "SCHEMA_VERSION",
    "SENSITIVITY_CLASSES",
    "build_memory_candidate_receipt_contract",
    "export_memory_candidate_receipt_contract",
    "format_memory_candidate_receipt_contract",
    "main",
    "stable_json",
]


if __name__ == "__main__":
    raise SystemExit(main())
