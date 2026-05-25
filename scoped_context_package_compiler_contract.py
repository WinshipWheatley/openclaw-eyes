"""Scoped Context Package Compiler Contract v0.

This deterministic read-model defines role-specific context packages for
OpenClaw agents and workers. Packages are compiled from graph coordinates,
topic slices, source refs, artifacts, procedures, receipts, and readbacks. They
do not dispatch agents, call models, run retrieval, ingest raw transcripts or
file bodies, reveal secrets, execute workflows, access external systems, mutate
Mission Control Swift, run Mac sync/import, or push.
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
DEFAULT_GENERATED_AT = "2026-05-25T00:00:00+00:00"

SCHEMA_VERSION = "scoped_context_package_compiler_contract_v0"
READ_MODEL_ID = "scoped_context_package_compiler_contract"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
OPERATOR_EXPORT_NAME = f"{READ_MODEL_ID}_OPERATOR.md"
CONTRACT_STATUS = "DETERMINISTIC_NON_DISPATCHING_SCOPED_CONTEXT_PACKAGE_COMPILER_CONTRACT"

TARGET_AGENT_ROLES = (
    "MAC_CODEX",
    "PC_CODEX",
    "GEMINI_AGY",
    "CASSANDRA",
    "GUARDIAN",
    "NILES",
    "LOCAL_OLLAMA",
    "VISUAL_RENDER_AGENT",
    "UNKNOWN_NEEDS_ROUTING",
)

SOURCE_REF_TYPES = (
    "TOPIC_SLICE",
    "CHAT_THREAD_SUMMARY",
    "SOURCE_FILE_REF",
    "ARTIFACT_REF",
    "PROCEDURE_REF",
    "RECEIPT_REF",
    "READBACK_REF",
    "REUSABLE_FACT_REF",
    "PROTECTED_SECRET_REF",
    "UNKNOWN",
)

EXCLUSION_REASONS = (
    "RAW_TRANSCRIPT_EXCLUDED",
    "RAW_FILE_BODY_EXCLUDED",
    "SECRET_VALUE_EXCLUDED",
    "CROSS_CLIENT_SCOPE_EXCLUDED",
    "LOW_RELEVANCE_EXCLUDED",
    "TOKEN_BUDGET_EXCLUDED",
    "PRIVACY_BOUNDARY_EXCLUDED",
    "UNKNOWN_EXCLUDED",
)

BLOCKER_TYPES = (
    "RAW_TRANSCRIPT_INCLUDED",
    "RAW_FILE_BODY_INCLUDED",
    "RAW_SECRET_INCLUDED",
    "CROSS_CLIENT_LEAK",
    "CROSS_TENANT_LEAK",
    "CONTEXT_TOO_BROAD",
    "MISSING_COORDINATES",
    "AMBIGUOUS_SCOPE",
    "AGENT_NOT_PERMITTED",
    "UNSAFE_ACTION_INCLUDED",
    "STALE_CONTEXT",
    "VISUAL_ARTIFACT_WITHOUT_TRUTH_REFS",
    "CONTEXT_PACKAGE_MISSING_EXCLUSIONS",
    "CONTEXT_PACKAGE_OVERFILLED_WITH_UNRELATED_THREAD",
    "AMBIGUOUS_SCOPE_NOT_FLAGGED",
    "UNKNOWN_FAIL_CLOSED",
)

AUTHORITY_BOUNDARY = {
    "live_context_package_dispatch_allowed": False,
    "live_agent_dispatch_allowed": False,
    "live_model_call_allowed": False,
    "live_workflow_run_allowed": False,
    "live_memory_retrieval_allowed": False,
    "live_raw_transcript_ingestion_allowed": False,
    "live_raw_file_body_ingestion_allowed": False,
    "live_secret_reveal_allowed": False,
    "live_visual_artifact_spawn_allowed": False,
    "live_external_action_allowed": False,
    "credential_handling_allowed": False,
    "raw_body_ingestion_allowed": False,
    "network_allowed": False,
    "mission_control_swift_change_allowed": False,
    "mac_sync_import_allowed": False,
    "git_push_pull_fetch_allowed": False,
}

COMMON_EXCLUSIONS = (
    "raw chat transcript",
    "raw file bodies",
    "raw secret values",
    "credentials",
    "cookies",
    "external account contents",
    "unrelated project history",
)


@dataclass(frozen=True)
class ScopedContextPackageCompilerContract:
    contract_id: str
    doctrine: tuple[str, ...]
    source_graph_policy: tuple[str, ...]
    topic_slice_policy: tuple[str, ...]
    source_ref_policy: tuple[str, ...]
    receipt_readback_policy: tuple[str, ...]
    role_specific_packaging_policy: tuple[str, ...]
    exclusion_policy: tuple[str, ...]
    tokenization_policy: tuple[str, ...]
    privacy_boundary: tuple[str, ...]
    authority_boundary: dict[str, bool]
    next_safe_move: str


@dataclass(frozen=True)
class ScopedContextPackage:
    context_package_id: str
    source_chat_ref: str
    target_agent_role: str
    target_worker_type: str
    target_machine: str
    world_ref: str
    folder_ref: str
    folder_path: str
    thread_ref: str
    topic_slice_refs: tuple[str, ...]
    included_context: tuple[str, ...]
    excluded_context: tuple[str, ...]
    source_refs: tuple[str, ...]
    artifact_refs: tuple[str, ...]
    procedure_refs: tuple[str, ...]
    receipt_refs: tuple[str, ...]
    readback_refs: tuple[str, ...]
    known_facts: tuple[str, ...]
    missing_items: tuple[str, ...]
    blocked_items: tuple[str, ...]
    allowed_actions: tuple[str, ...]
    forbidden_actions: tuple[str, ...]
    validation_expectations: tuple[str, ...]
    privacy_class: str
    sensitivity_class: str
    token_budget_hint: str
    truth_boundary: str
    visual_artifact_needed: bool
    visual_render_context_ref: str
    next_safe_move: str


@dataclass(frozen=True)
class ContextPackageCoordinate:
    coordinate_id: str
    world_ref: str
    folder_ref: str
    folder_path: str
    thread_ref: str
    topic_slice_ref: str
    client_ref: str
    tenant_ref: str
    coordinate_confidence: str
    ambiguity_status: str
    next_safe_move: str


@dataclass(frozen=True)
class ContextHighlight:
    highlight_id: str
    source_ref_type: str
    source_ref: str
    summary: str
    relevance_reason: str
    confidence: str
    freshness_status: str
    proof_status: str
    privacy_class: str
    next_safe_move: str


@dataclass(frozen=True)
class ContextExclusion:
    exclusion_id: str
    excluded_item_type: str
    excluded_ref: str
    reason: str
    sensitivity_class: str
    operator_visible: bool
    next_safe_move: str


@dataclass(frozen=True)
class RoleContextPolicy:
    policy_id: str
    target_agent_role: str
    allowed_context_types: tuple[str, ...]
    forbidden_context_types: tuple[str, ...]
    allowed_actions: tuple[str, ...]
    forbidden_actions: tuple[str, ...]
    proof_requirements: tuple[str, ...]
    approval_requirements: tuple[str, ...]
    default_token_budget_hint: str
    next_safe_move: str


@dataclass(frozen=True)
class ContextPackageVisualArtifactNeed:
    visual_need_id: str
    context_package_ref: str
    needed: bool
    reason: str
    visual_artifact_type: str
    source_truth_refs: tuple[str, ...]
    source_context_refs: tuple[str, ...]
    target_surface: str
    renderer_route_hint: str
    detail_priority: str
    style_priority: str
    next_safe_move: str


@dataclass(frozen=True)
class ContextPackageBlocker:
    blocker_id: str
    blocker_type: str
    condition: str
    severity: str
    elioperator_warning: str
    fail_closed: bool
    next_safe_move: str


@dataclass(frozen=True)
class ScopedContextPackageElioperatorReport:
    report_id: str
    plain_summary: str
    what_this_enables: str
    what_this_does_not_do_yet: str
    how_context_packages_work: str
    how_agents_get_context: str
    how_raw_threads_are_avoided: str
    how_files_and_secrets_are_protected: str
    how_truth_is_preserved: str
    next_safe_move: str


REQUIRED_CONTRACT_FIELDS = tuple(ScopedContextPackageCompilerContract.__dataclass_fields__.keys())
REQUIRED_PACKAGE_FIELDS = tuple(ScopedContextPackage.__dataclass_fields__.keys())
REQUIRED_COORDINATE_FIELDS = tuple(ContextPackageCoordinate.__dataclass_fields__.keys())
REQUIRED_HIGHLIGHT_FIELDS = tuple(ContextHighlight.__dataclass_fields__.keys())
REQUIRED_EXCLUSION_FIELDS = tuple(ContextExclusion.__dataclass_fields__.keys())
REQUIRED_ROLE_POLICY_FIELDS = tuple(RoleContextPolicy.__dataclass_fields__.keys())
REQUIRED_VISUAL_NEED_FIELDS = tuple(ContextPackageVisualArtifactNeed.__dataclass_fields__.keys())
REQUIRED_BLOCKER_FIELDS = tuple(ContextPackageBlocker.__dataclass_fields__.keys())
REQUIRED_REPORT_FIELDS = tuple(ScopedContextPackageElioperatorReport.__dataclass_fields__.keys())


def stable_json(data: Any) -> str:
    return json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _content_hash(payload: dict[str, Any]) -> str:
    clean = json.loads(stable_json(payload))
    clean.get("machine_proof", {}).pop("content_hash", None)
    return hashlib.sha256(stable_json(clean).encode("utf-8")).hexdigest()


def _model_schemas() -> dict[str, Any]:
    return {
        "scoped_context_package_compiler_contract": {"required_fields": list(REQUIRED_CONTRACT_FIELDS)},
        "scoped_context_package": {"required_fields": list(REQUIRED_PACKAGE_FIELDS)},
        "context_package_coordinate": {"required_fields": list(REQUIRED_COORDINATE_FIELDS)},
        "context_highlight": {"required_fields": list(REQUIRED_HIGHLIGHT_FIELDS)},
        "context_exclusion": {"required_fields": list(REQUIRED_EXCLUSION_FIELDS)},
        "role_context_policy": {"required_fields": list(REQUIRED_ROLE_POLICY_FIELDS)},
        "context_package_visual_artifact_need": {"required_fields": list(REQUIRED_VISUAL_NEED_FIELDS)},
        "context_package_blocker": {"required_fields": list(REQUIRED_BLOCKER_FIELDS)},
        "scoped_context_package_elioperator_report": {"required_fields": list(REQUIRED_REPORT_FIELDS)},
    }


def build_contract() -> ScopedContextPackageCompilerContract:
    return ScopedContextPackageCompilerContract(
        contract_id="scoped_context_package_compiler_contract_v0",
        doctrine=(
            "Agents receive scoped context packages, not vague memory.",
            "Packages are generated from graph/projection coordinates, not guessed folder names alone.",
            "Packages include relevant topic slice summaries and refs only.",
            "Ambiguous scope is flagged instead of overfilling context.",
            "Truth comes from receipts and readbacks, not summaries.",
            "Raw transcripts, raw file bodies, and raw secret values stay below deck.",
        ),
        source_graph_policy=(
            "Use world_project_memory_graph_projection coordinates as the primary source of scope.",
            "Folder names alone are not enough to compile a package.",
            "Cross-client ambiguity fails closed.",
        ),
        topic_slice_policy=(
            "When topic slices exist, include only the relevant slice summaries and refs.",
            "Prior relevant threads appear as compact highlights with source/thread refs.",
            "Do not include whole raw threads.",
        ),
        source_ref_policy=(
            "Source files are represented by safe source refs and metadata only.",
            "Raw file body extraction requires a future governed rail.",
            "Protected sources remain protected refs.",
        ),
        receipt_readback_policy=(
            "Known facts must point to receipt or readback refs where available.",
            "Missing pieces and blockers stay explicit.",
            "Stale context must be flagged.",
        ),
        role_specific_packaging_policy=(
            "Mac Codex receives Mac app/UI validation expectations.",
            "PC Codex receives pytest/export/read-model validation expectations.",
            "Gemini/Agy receives read-only audit scope with no edit or commit authority.",
            "Cassandra, Guardian, Niles, and visual/render agents receive role-specific context only.",
        ),
        exclusion_policy=(
            "Every package lists what is included and excluded.",
            "Every exclusion includes why it was excluded.",
            "Packages must state what remains unknown.",
        ),
        tokenization_policy=(
            "Secrets are token refs only.",
            "Raw secret reveal is forbidden in context packages.",
            "Protected values use reusable-block or protected-secret refs.",
        ),
        privacy_boundary=(
            "No raw transcripts by default.",
            "No raw private file bodies.",
            "No raw secret values.",
            "No unrelated client-private project history.",
        ),
        authority_boundary=AUTHORITY_BOUNDARY,
        next_safe_move="Export package examples and keep them ready-not-dispatched until a future approved agent rail exists.",
    )


def _coordinate(
    coordinate_id: str,
    world_ref: str,
    folder_ref: str,
    folder_path: str,
    thread_ref: str,
    topic_slice_ref: str,
    client_ref: str,
    *,
    coordinate_confidence: str = "HIGH",
    ambiguity_status: str = "UNAMBIGUOUS",
) -> ContextPackageCoordinate:
    return ContextPackageCoordinate(
        coordinate_id=coordinate_id,
        world_ref=world_ref,
        folder_ref=folder_ref,
        folder_path=folder_path,
        thread_ref=thread_ref,
        topic_slice_ref=topic_slice_ref,
        client_ref=client_ref,
        tenant_ref="openclaw_local_operator",
        coordinate_confidence=coordinate_confidence,
        ambiguity_status=ambiguity_status,
        next_safe_move="Use graph/projection coordinate plus topic slice ref; do not infer scope from folder name alone.",
    )


def build_coordinates() -> tuple[ContextPackageCoordinate, ...]:
    return (
        _coordinate("coord_mac_chat_surface", "build", "mission_control_chat_surface", "build/mission_control/chat_surface", "thread_ref_build_chat_surface", "topic_slice_chat_surface_ui", "openclaw"),
        _coordinate("coord_pc_chat_processor", "build", "openclaw_backend_chat_router", "build/openclaw/backend/chat_router", "thread_ref_pc_chat_processor", "topic_slice_bounded_processor", "openclaw"),
        _coordinate("coord_gemini_card_contract_audit", "build", "mission_control_chat_surface", "build/mission_control/chat_surface", "thread_ref_chat_first_pivot_audit", "topic_slice_card_contract_reuse_audit", "openclaw"),
        _coordinate("coord_niles_x32_routing", "music", "x32_routing", "music/live_music/x32/routing", "thread_ref_x32_fader_replacement", "topic_slice_x32_fader_replacement", "local_operator", coordinate_confidence="MEDIUM"),
        _coordinate("coord_cassandra_capital_hilton_invoice", "finance", "capital_hilton_invoices", "finance/capital_hilton/invoices", "thread_ref_finance_misfiled_invoice_architecture", "topic_slice_capital_hilton_invoice_specific", "capital_hilton"),
        _coordinate("coord_guardian_capital_hilton_approval", "finance", "capital_hilton_invoices", "finance/capital_hilton/invoices", "thread_ref_finance_misfiled_invoice_architecture", "topic_slice_capital_hilton_invoice_specific", "capital_hilton"),
        _coordinate("coord_visual_invoice_workflow", "finance", "capital_hilton_invoices", "finance/capital_hilton/invoices", "thread_ref_finance_misfiled_invoice_architecture", "topic_slice_capital_hilton_invoice_specific", "capital_hilton"),
        _coordinate("coord_ambiguous_keep_going", "unknown", "unknown", "unknown", "thread_ref_unknown_keep_going", "unknown", "unknown", coordinate_confidence="LOW", ambiguity_status="AMBIGUOUS_NEEDS_CLARIFICATION"),
    )


def _highlight(
    highlight_id: str,
    source_ref_type: str,
    source_ref: str,
    summary: str,
    relevance_reason: str,
    *,
    confidence: str = "MEDIUM",
    freshness_status: str = "CURRENT",
    proof_status: str = "READBACK_OR_REF_ONLY",
    privacy_class: str = "internal",
) -> ContextHighlight:
    return ContextHighlight(
        highlight_id=highlight_id,
        source_ref_type=source_ref_type,
        source_ref=source_ref,
        summary=summary,
        relevance_reason=relevance_reason,
        confidence=confidence,
        freshness_status=freshness_status,
        proof_status=proof_status,
        privacy_class=privacy_class,
        next_safe_move="Use this compact highlight with its source ref; do not expand into raw body context.",
    )


def build_highlights() -> tuple[ContextHighlight, ...]:
    return (
        _highlight("highlight_mac_chat_surface_task", "TOPIC_SLICE", "topic_slice_chat_surface_ui", "Mission Control chat surface work: cards render in chat, composer bottom anchored, Mac validation expected.", "Needed for Mac Codex app/UI continuation.", confidence="HIGH"),
        _highlight("highlight_mac_recent_readback_cards", "READBACK_REF", "world_project_memory_graph_projection", "Readback cards and sidebar projection are available as safe generated read-model refs.", "Gives Mac Codex current app-facing context."),
        _highlight("highlight_pc_chat_processor_requirements", "PROCEDURE_REF", "openclaw_chat_request_processor", "Bounded request processor should turn Mac request files into operator-readable chat responses.", "Needed for PC Codex backend work.", confidence="HIGH"),
        _highlight("highlight_pc_router_intake_refs", "READBACK_REF", "conversational_workflow_router_readback", "Router intake and card mirrors provide deterministic readbacks for Mac.", "Source rail for backend request processing."),
        _highlight("highlight_gemini_card_contracts", "PROCEDURE_REF", "operator_card_render_packet_contract", "Card contracts can be audited for reuse in the chat-first pivot.", "Gives Gemini/Agy read-only audit targets."),
        _highlight("highlight_niles_x32_slice", "TOPIC_SLICE", "topic_slice_x32_fader_replacement", "X32 fader replacement/routing context is a candidate topic slice under live music X32.", "Needed for scoped music production context.", privacy_class="internal"),
        _highlight("highlight_niles_x32_source_refs", "SOURCE_FILE_REF", "source_ref_x32_maintenance_summary", "X32 maintenance source refs are metadata-only.", "Provides source material without raw show-file body."),
        _highlight("highlight_cassandra_capital_hilton", "TOPIC_SLICE", "topic_slice_capital_hilton_invoice_specific", "Capital Hilton invoice draft context includes companion invoice, recipient candidate, and approval boundary.", "Needed for communication draft context.", privacy_class="finance_boundary"),
        _highlight("highlight_guardian_approval_boundary", "RECEIPT_REF", "guardian_draft_approval_request_contract", "Guardian package needs requested action, risk, proof refs, protected refs, and missing approvals.", "Needed for approval boundary review.", privacy_class="finance_boundary"),
        _highlight("highlight_visual_invoice_truth", "READBACK_REF", "workflow_execution_package_compiler", "Invoice workflow picture should show known facts, missing pieces, locked actions, and future completion target.", "Needed for future visual render package.", privacy_class="finance_boundary", proof_status="TRUTH_BACKED_BY_READMODEL"),
        _highlight("highlight_prior_thread_compact", "CHAT_THREAD_SUMMARY", "thread_ref_music_live_multitopic_setlist", "Prior live music thread has compact topic links for setlists, X32, songwriting, and bookings.", "Relevant prior thread included as summary/ref only."),
        _highlight("highlight_secret_token_only", "PROTECTED_SECRET_REF", "secret_ref_future_coupa_task_scoped", "A future protected secret may be referenced only by token ref; raw value excluded.", "Models token-only package posture.", privacy_class="protected"),
    )


def _exclusion(
    exclusion_id: str,
    excluded_item_type: str,
    excluded_ref: str,
    reason: str,
    *,
    sensitivity_class: str = "private",
    operator_visible: bool = True,
) -> ContextExclusion:
    return ContextExclusion(
        exclusion_id=exclusion_id,
        excluded_item_type=excluded_item_type,
        excluded_ref=excluded_ref,
        reason=reason,
        sensitivity_class=sensitivity_class,
        operator_visible=operator_visible,
        next_safe_move="Keep this exclusion visible enough for the agent/operator to know what was not provided.",
    )


def build_exclusions() -> tuple[ContextExclusion, ...]:
    return (
        _exclusion("exclusion_raw_transcript_all_packages", "CHAT_TRANSCRIPT_BODY", "all_source_threads", "RAW_TRANSCRIPT_EXCLUDED"),
        _exclusion("exclusion_raw_file_body_all_packages", "FILE_BODY", "all_source_file_refs", "RAW_FILE_BODY_EXCLUDED"),
        _exclusion("exclusion_secret_values_all_packages", "SECRET_VALUE", "all_protected_secret_refs", "SECRET_VALUE_EXCLUDED", sensitivity_class="credential_boundary"),
        _exclusion("exclusion_cross_client_finance_for_niles", "CLIENT_PRIVATE_SCOPE", "finance/capital_hilton", "CROSS_CLIENT_SCOPE_EXCLUDED", sensitivity_class="finance_boundary"),
        _exclusion("exclusion_repo_a_write_for_mac", "AUTHORITY", "repo_a_backend_mutation", "PRIVACY_BOUNDARY_EXCLUDED"),
        _exclusion("exclusion_mac_swift_for_pc", "AUTHORITY", "mission_control_swift_edits", "PRIVACY_BOUNDARY_EXCLUDED"),
        _exclusion("exclusion_write_authority_for_gemini", "AUTHORITY", "file_edits_commits_execution", "PRIVACY_BOUNDARY_EXCLUDED"),
        _exclusion("exclusion_unrelated_thread_history", "CHAT_THREAD_SUMMARY", "unrelated_project_history", "LOW_RELEVANCE_EXCLUDED"),
        _exclusion("exclusion_extra_context_budget", "LOW_RELEVANCE_CONTEXT", "non_current_threads", "TOKEN_BUDGET_EXCLUDED"),
    )


def build_role_policies() -> tuple[RoleContextPolicy, ...]:
    return (
        RoleContextPolicy(
            "role_policy_mac_codex",
            "MAC_CODEX",
            ("Mac UI/app context", "Mac package refs", "screenshot refs", "visual workspace requests", "Mac validation expectations"),
            ("Repo A canonical mutation authority", "raw secrets", "Gmail/Coupa/browser actions", "raw private bodies"),
            ("Swift/Mac app implementation context only", "Xcode build/run validation", "screenshot validation"),
            ("Repo A backend mutation", "external account access", "credential handling", "live send/submit"),
            ("Mac build/run result", "screenshot/readback when UI changes"),
            ("operator approval for any future external app automation",),
            "focused Mac UI package",
            "Package Mac context only and keep backend authority excluded.",
        ),
        RoleContextPolicy(
            "role_policy_pc_codex",
            "PC_CODEX",
            ("backend read-model refs", "Python modules", "export scripts", "pytest requirements", "generated read-model refs"),
            ("Mac Swift editing unless routed", "external account/action context", "raw private bodies", "raw secrets"),
            ("Repo A backend implementation context", "pytest", "export/read-model validation", "authority scans"),
            ("Mac app UI changes", "external actions", "credential handling"),
            ("focused pytest", "export command", "JSON parse", "secret/PII scan", "authority scan"),
            ("operator approval for destructive or external actions",),
            "focused backend package",
            "Package backend context with validation expectations.",
        ),
        RoleContextPolicy(
            "role_policy_gemini_agy",
            "GEMINI_AGY",
            ("read-only summaries", "contract refs", "audit questions", "design/taste targets"),
            ("secrets", "raw bodies", "write authority", "commit authority", "execution authority"),
            ("read-only audit", "prompt shaping", "strategy critique"),
            ("file edits", "commits", "tool execution", "external action"),
            ("written audit findings only",),
            ("operator approval before any implementation prompt is sent to another worker",),
            "read-only audit package",
            "Keep Gemini/Agy package read-only with explicit no edit/commit boundary.",
        ),
        RoleContextPolicy(
            "role_policy_cassandra",
            "CASSANDRA",
            ("communication context", "draft scope", "recipient candidate", "approval boundary", "artifact refs"),
            ("send authority", "raw credentials", "raw private evidence bodies", "unrelated ledger history"),
            ("draft language for review", "surface missing inputs"),
            ("send", "create live email draft", "attach file", "approval bypass"),
            ("draft review packet", "artifact/ref proof", "approval posture"),
            ("Guardian approval before external send/submit"),
            "drafting package",
            "Package communications context only and keep send authority excluded.",
        ),
        RoleContextPolicy(
            "role_policy_guardian",
            "GUARDIAN",
            ("requested action", "risk", "proof refs", "protected refs", "missing approvals", "authority boundary"),
            ("raw secret reveal", "irrelevant chat history", "unscoped private bodies"),
            ("approval boundary review", "risk assessment", "fail-closed blocker review"),
            ("secret reveal", "external action execution", "approval bypass"),
            ("proof refs", "risk refs", "operator intent summary"),
            ("explicit approval rail required before external action"),
            "approval review package",
            "Reference protected refs but do not reveal protected values.",
        ),
        RoleContextPolicy(
            "role_policy_niles",
            "NILES",
            ("music/creative context", "X32 topic slices", "show-file source refs", "production notes summaries"),
            ("finance/client ledgers unless explicitly allowed", "raw secrets", "unrelated private data"),
            ("music context review", "production-oriented suggestions", "resume scoped thread later"),
            ("finance/client action", "credential handling", "external send/submit"),
            ("source/thread refs for any claim",),
            ("operator approval for DAW/media-app mutation in future lanes"),
            "music production package",
            "Keep Niles inside music/creative scope unless operator expands it.",
        ),
        RoleContextPolicy(
            "role_policy_visual_render_agent",
            "VISUAL_RENDER_AGENT",
            ("truth payload", "source refs", "layout/device hints", "missing/locked facts", "proof refs"),
            ("raw private bodies", "secrets", "unverified completion claims", "style-only prompts"),
            ("prepare future visual card/spec context", "prioritize factual detail"),
            ("live render spawn", "model/image generation", "external action"),
            ("source truth refs", "readback refs"),
            ("operator approval for any future live render/generation rail"),
            "visual truth package",
            "Detail/factual priority outranks style priority.",
        ),
    )


def _package(
    context_package_id: str,
    source_chat_ref: str,
    target_agent_role: str,
    target_worker_type: str,
    target_machine: str,
    world_ref: str,
    folder_ref: str,
    folder_path: str,
    thread_ref: str,
    topic_slice_refs: tuple[str, ...],
    *,
    included_context: tuple[str, ...],
    excluded_context: tuple[str, ...],
    source_refs: tuple[str, ...] = (),
    artifact_refs: tuple[str, ...] = (),
    procedure_refs: tuple[str, ...] = (),
    receipt_refs: tuple[str, ...] = (),
    readback_refs: tuple[str, ...] = (),
    known_facts: tuple[str, ...] = (),
    missing_items: tuple[str, ...] = (),
    blocked_items: tuple[str, ...] = (),
    allowed_actions: tuple[str, ...] = (),
    forbidden_actions: tuple[str, ...] = (),
    validation_expectations: tuple[str, ...] = (),
    privacy_class: str = "internal",
    sensitivity_class: str = "metadata_only",
    token_budget_hint: str = "focused",
    visual_artifact_needed: bool = False,
    visual_render_context_ref: str = "none",
    next_safe_move: str = "Show package to operator; do not dispatch.",
) -> ScopedContextPackage:
    return ScopedContextPackage(
        context_package_id=context_package_id,
        source_chat_ref=source_chat_ref,
        target_agent_role=target_agent_role,
        target_worker_type=target_worker_type,
        target_machine=target_machine,
        world_ref=world_ref,
        folder_ref=folder_ref,
        folder_path=folder_path,
        thread_ref=thread_ref,
        topic_slice_refs=topic_slice_refs,
        included_context=included_context,
        excluded_context=excluded_context,
        source_refs=source_refs,
        artifact_refs=artifact_refs,
        procedure_refs=procedure_refs,
        receipt_refs=receipt_refs,
        readback_refs=readback_refs,
        known_facts=known_facts,
        missing_items=missing_items,
        blocked_items=blocked_items,
        allowed_actions=allowed_actions,
        forbidden_actions=forbidden_actions,
        validation_expectations=validation_expectations,
        privacy_class=privacy_class,
        sensitivity_class=sensitivity_class,
        token_budget_hint=token_budget_hint,
        truth_boundary="Truth comes from cited receipts/readbacks and source refs, not from summary text.",
        visual_artifact_needed=visual_artifact_needed,
        visual_render_context_ref=visual_render_context_ref,
        next_safe_move=next_safe_move,
    )


def build_packages() -> tuple[ScopedContextPackage, ...]:
    return (
        _package(
            "context_package_mac_codex_chat_surface",
            "chat_ref_continue_chat_surface_work",
            "MAC_CODEX",
            "MAC_CODEX",
            "MAC",
            "build",
            "mission_control_chat_surface",
            "build/mission_control/chat_surface",
            "thread_ref_build_chat_surface",
            ("topic_slice_chat_surface_ui",),
            included_context=("SwiftUI task highlights", "screenshot refs", "Mac validation requirements", "recent app commits/readbacks"),
            excluded_context=("Repo A write authority", "Gmail/Coupa/browser actions", "raw secrets", "raw transcripts", "raw file bodies"),
            source_refs=("source_ref_mac_codex_prompts", "source_ref_screenshots_metadata"),
            artifact_refs=("artifact_ref_readback_cards",),
            receipt_refs=("receipt_swiftui_task_history",),
            readback_refs=("world_project_memory_graph_projection", "conversation_topic_slicer_contract"),
            known_facts=("Mission Control chat surface is Mac-side work.", "Cards and composer behavior belong to Mac Codex."),
            missing_items=("current Mac build result", "current screenshot proof after UI changes"),
            blocked_items=("Repo A backend mutation", "external account action"),
            allowed_actions=("Mac UI implementation context", "Xcode build/run validation", "screenshot validation"),
            forbidden_actions=("Repo A backend mutation", "credential handling", "external send/submit"),
            validation_expectations=("Xcode build/run validation", "screenshot validation", "Mac-local UI inspection if approved"),
            visual_artifact_needed=True,
            visual_render_context_ref="visual_need_mac_chat_surface_review",
            next_safe_move="Send only as a future Mac Codex package; do not dispatch here.",
        ),
        _package(
            "context_package_pc_codex_chat_request_processor",
            "chat_ref_build_bounded_chat_request_processor",
            "PC_CODEX",
            "PC_CODEX",
            "PC_WSL",
            "build",
            "openclaw_backend_chat_router",
            "build/openclaw/backend/chat_router",
            "thread_ref_pc_chat_processor",
            ("topic_slice_bounded_processor",),
            included_context=("router intake refs", "readback refs", "processor requirements", "focused tests", "generated read-model refs"),
            excluded_context=("Mac Swift edits", "external actions", "raw transcripts", "raw file bodies", "raw secrets"),
            source_refs=("conversational_workflow_router_intake", "openclaw_chat_request_processor"),
            procedure_refs=("workflow_execution_package_compiler",),
            receipt_refs=("receipt_router_readback_capital_hilton",),
            readback_refs=("conversational_workflow_router_readback", "chat_readback_card_mirror"),
            known_facts=("PC Codex owns Repo A backend/read-model work.", "Processor output must be operator-readable."),
            missing_items=("latest fixture or request file when running live later",),
            blocked_items=("Mac Swift edits", "external actions", "model/tool execution unless future approved"),
            allowed_actions=("Python/read-model implementation context", "export command validation", "focused pytest"),
            forbidden_actions=("Mac Swift changes", "email/Coupa/browser actions", "credential handling"),
            validation_expectations=("pytest", "export summary", "JSON parse", "secret/PII scan", "authority scan", "git diff checks"),
            next_safe_move="Use as PC Codex package context only; no live dispatch.",
        ),
        _package(
            "context_package_gemini_agy_card_contract_audit",
            "chat_ref_audit_card_contract_reuse",
            "GEMINI_AGY",
            "GEMINI_AGY",
            "EXTERNAL_MODEL",
            "build",
            "mission_control_chat_surface",
            "build/mission_control/chat_surface",
            "thread_ref_chat_first_pivot_audit",
            ("topic_slice_card_contract_reuse_audit",),
            included_context=("contract summaries to inspect", "audit questions", "read-only target list"),
            excluded_context=("write authority", "commits", "execution", "secrets", "raw bodies"),
            source_refs=("operator_card_render_packet_contract", "chat_readback_card_mirror", "conversation_topic_slicer_contract"),
            readback_refs=("workflow_readback_concierge_contract",),
            known_facts=("Gemini/Agy is read-only scout/audit/prompt shaping.",),
            missing_items=("operator decision on whether to implement audit findings",),
            blocked_items=("file edits", "commits", "live execution"),
            allowed_actions=("read-only audit", "strategy critique", "prompt shaping"),
            forbidden_actions=("file edits", "commits", "tool execution", "external action"),
            validation_expectations=("written audit only", "no edit/commit boundary repeated"),
            token_budget_hint="read-only audit package",
            next_safe_move="Ask for audit output only; do not grant write authority.",
        ),
        _package(
            "context_package_niles_x32_routing",
            "chat_ref_niles_pull_x32_routing",
            "NILES",
            "LOCAL_OLLAMA",
            "LOCAL_ONLY",
            "music",
            "x32_routing",
            "music/live_music/x32/routing",
            "thread_ref_x32_fader_replacement",
            ("topic_slice_x32_fader_replacement",),
            included_context=("X32 topic slice summaries", "source refs", "show-file refs if present", "prior thread compact highlight"),
            excluded_context=("finance/client/private unrelated data", "raw show-file bodies", "raw transcripts", "raw secrets"),
            source_refs=("source_ref_x32_maintenance_summary", "source_ref_behringer_x32_notes"),
            receipt_refs=("receipt_x32_show_setup_readback",),
            readback_refs=("conversation_topic_slicer_contract",),
            known_facts=("X32 routing context belongs to music/live_music/x32/routing.", "Prior thread is included as compact highlight only."),
            missing_items=("current hardware/session proof", "operator-specific objective for the next X32 action"),
            blocked_items=("DAW/media-app mutation", "finance/client data"),
            allowed_actions=("music context review", "production-oriented suggestions"),
            forbidden_actions=("finance/client ledger access", "external action", "credential handling"),
            validation_expectations=("source/thread refs for any claim",),
            token_budget_hint="music production package",
            next_safe_move="Ask Niles to work from scoped music context only when a future responder rail exists.",
        ),
        _package(
            "context_package_cassandra_capital_hilton_invoice",
            "chat_ref_capital_hilton_invoice_draft",
            "CASSANDRA",
            "CASSANDRA",
            "LOCAL_ONLY",
            "finance",
            "capital_hilton_invoices",
            "finance/capital_hilton/invoices",
            "thread_ref_finance_misfiled_invoice_architecture",
            ("topic_slice_capital_hilton_invoice_specific",),
            included_context=("delivery workflow summary", "invoice artifact refs", "recipient candidate", "approval boundary", "missing proof list"),
            excluded_context=("raw credentials", "send authority", "raw private evidence bodies", "unrelated chat history"),
            source_refs=("source_ref_capital_hilton_invoice_preview",),
            artifact_refs=("artifact_ref_capital_hilton_invoice_pdf_future",),
            procedure_refs=("procedure_ref_capital_hilton_invoice_workflow",),
            receipt_refs=("receipt_capital_hilton_delivery_facts",),
            readback_refs=("workflow_execution_package_compiler", "conversational_workflow_router_readback"),
            known_facts=("Companion invoice and Coupa/PO payment rail are draft workflow context.", "Annette is a recipient candidate, not confirmed truth."),
            missing_items=("confirmed recipient", "final artifact hash", "Guardian approval", "send/submit receipts"),
            blocked_items=("send authority", "live email draft", "attachment", "Coupa access/submit"),
            allowed_actions=("draft language for review", "surface missing inputs"),
            forbidden_actions=("send", "create live email draft", "attach file", "approval bypass"),
            validation_expectations=("draft review packet", "approval boundary preserved", "no external action scan"),
            privacy_class="finance_boundary",
            sensitivity_class="finance_boundary",
            token_budget_hint="drafting package",
            visual_artifact_needed=True,
            visual_render_context_ref="visual_need_capital_hilton_invoice_workflow",
            next_safe_move="Use as future Cassandra draft package only after missing context is reviewed.",
        ),
        _package(
            "context_package_guardian_approval_boundary",
            "chat_ref_guardian_capital_hilton_approval",
            "GUARDIAN",
            "GUARDIAN",
            "LOCAL_ONLY",
            "finance",
            "capital_hilton_invoices",
            "finance/capital_hilton/invoices",
            "thread_ref_finance_misfiled_invoice_architecture",
            ("topic_slice_capital_hilton_invoice_specific",),
            included_context=("requested action", "risk", "proof refs", "protected refs", "missing approvals", "authority boundary"),
            excluded_context=("irrelevant chat history", "raw secret reveal", "raw private file bodies"),
            source_refs=("source_ref_capital_hilton_invoice_preview", "protected_ref_capital_hilton_evidence_future"),
            artifact_refs=("artifact_ref_capital_hilton_invoice_pdf_future",),
            receipt_refs=("receipt_capital_hilton_delivery_facts", "receipt_guardian_approval_missing"),
            readback_refs=("workflow_execution_package_compiler",),
            known_facts=("External send/submit requires approval.", "Proof refs are not completion receipts."),
            missing_items=("Guardian approval receipt", "operator approval receipt", "artifact hash", "send/submit receipts"),
            blocked_items=("email send", "Coupa submit", "secret reveal"),
            allowed_actions=("approval boundary review", "risk assessment", "fail-closed blocker review"),
            forbidden_actions=("secret reveal", "external action execution", "approval bypass"),
            validation_expectations=("proof refs present", "authority boundary false", "approval missing status visible"),
            privacy_class="finance_boundary",
            sensitivity_class="protected_reference_only",
            token_budget_hint="approval review package",
            next_safe_move="Use as a future Guardian review package; no approval request is made here.",
        ),
        _package(
            "context_package_visual_invoice_workflow",
            "chat_ref_visual_invoice_workflow_picture",
            "VISUAL_RENDER_AGENT",
            "VISUAL_RENDER_AGENT",
            "LOCAL_ONLY",
            "finance",
            "capital_hilton_invoices",
            "finance/capital_hilton/invoices",
            "thread_ref_finance_misfiled_invoice_architecture",
            ("topic_slice_capital_hilton_invoice_specific",),
            included_context=("truth-backed facts", "missing items", "locked actions", "device/layout hints", "source refs"),
            excluded_context=("raw transcript", "raw file bodies", "secrets", "unverified completion claims"),
            source_refs=("source_ref_capital_hilton_invoice_preview",),
            artifact_refs=("artifact_ref_capital_hilton_invoice_pdf_future",),
            receipt_refs=("receipt_capital_hilton_delivery_facts",),
            readback_refs=("workflow_execution_package_compiler", "chat_workflow_run_state_visual_feed"),
            known_facts=("Visual should show workflow status, not claim invoice sent.",),
            missing_items=("proof receipts", "final artifact hash", "approval receipt"),
            blocked_items=("live render spawn", "model/image generation", "external action"),
            allowed_actions=("prepare future visual card/spec context", "prioritize factual detail"),
            forbidden_actions=("live render spawn", "style-only prompt", "completion claim without proof"),
            validation_expectations=("source truth refs present", "detail priority outranks style priority"),
            privacy_class="finance_boundary",
            sensitivity_class="metadata_only",
            token_budget_hint="visual truth package",
            visual_artifact_needed=True,
            visual_render_context_ref="visual_need_capital_hilton_invoice_workflow",
            next_safe_move="Use as future visual render context only; no renderer is spawned here.",
        ),
        _package(
            "context_package_ambiguous_keep_going",
            "chat_ref_keep_going_with_that_thing",
            "UNKNOWN_NEEDS_ROUTING",
            "UNKNOWN_NEEDS_ROUTING",
            "UNKNOWN",
            "unknown",
            "unknown",
            "unknown",
            "thread_ref_unknown_keep_going",
            (),
            included_context=("operator phrase only",),
            excluded_context=("all prior thread bodies", "all unrelated scopes", "raw transcripts", "raw file bodies", "raw secrets"),
            known_facts=("Operator request is ambiguous.",),
            missing_items=("which thread to resume", "which world/folder to use", "whether to start new work"),
            blocked_items=("agent dispatch", "broad context stuffing", "cross-scope query"),
            allowed_actions=("ask clarification", "offer likely resume options from safe refs later"),
            forbidden_actions=("stuff all recent threads into context", "dispatch worker", "guess scope"),
            validation_expectations=("ambiguity visible", "how-to-clarify next question"),
            token_budget_hint="blocked until scoped",
            next_safe_move="Ask whether to resume an existing thread or start a new one.",
        ),
    )


def build_visual_artifact_needs() -> tuple[ContextPackageVisualArtifactNeed, ...]:
    return (
        ContextPackageVisualArtifactNeed(
            visual_need_id="visual_need_mac_chat_surface_review",
            context_package_ref="context_package_mac_codex_chat_surface",
            needed=True,
            reason="Mac UI work benefits from screenshot/readback proof after implementation.",
            visual_artifact_type="UI_REVIEW_SCREENSHOT_OR_CARD",
            source_truth_refs=("receipt_swiftui_task_history", "source_ref_screenshots_metadata"),
            source_context_refs=("context_package_mac_codex_chat_surface",),
            target_surface="mac_chat",
            renderer_route_hint="MAC_CODEX screenshot validation later",
            detail_priority="HIGH",
            style_priority="MEDIUM",
            next_safe_move="Request visual proof only after future Mac worker produces a safe screenshot/readback.",
        ),
        ContextPackageVisualArtifactNeed(
            visual_need_id="visual_need_capital_hilton_invoice_workflow",
            context_package_ref="context_package_visual_invoice_workflow",
            needed=True,
            reason="Operator should see a truth-backed workflow picture with known, missing, and locked items.",
            visual_artifact_type="WORKFLOW_STATUS_CARD",
            source_truth_refs=("workflow_execution_package_compiler", "receipt_capital_hilton_delivery_facts"),
            source_context_refs=("context_package_visual_invoice_workflow", "topic_slice_capital_hilton_invoice_specific"),
            target_surface="mac_chat",
            renderer_route_hint="VISUAL_RENDER_AGENT future gated package",
            detail_priority="HIGH",
            style_priority="LOW",
            next_safe_move="Do not spawn renderer; keep visual context ready for future gated lane.",
        ),
        ContextPackageVisualArtifactNeed(
            visual_need_id="visual_need_none_gemini_audit",
            context_package_ref="context_package_gemini_agy_card_contract_audit",
            needed=False,
            reason="Read-only audit can return text findings without a visual artifact.",
            visual_artifact_type="NONE",
            source_truth_refs=("operator_card_render_packet_contract",),
            source_context_refs=("context_package_gemini_agy_card_contract_audit",),
            target_surface="mac_chat",
            renderer_route_hint="none",
            detail_priority="MEDIUM",
            style_priority="LOW",
            next_safe_move="No visual renderer needed for this package.",
        ),
    )


def build_blockers() -> tuple[ContextPackageBlocker, ...]:
    details = {
        "RAW_TRANSCRIPT_INCLUDED": ("A package includes raw chat transcript text.", "Remove the transcript body and use topic summaries plus message refs."),
        "RAW_FILE_BODY_INCLUDED": ("A package includes raw file body content.", "Use source refs and safe metadata only."),
        "RAW_SECRET_INCLUDED": ("A package includes a raw secret value.", "Use protected token refs only."),
        "CROSS_CLIENT_LEAK": ("A package mixes client-private scopes.", "Fail closed and ask for scope review."),
        "CROSS_TENANT_LEAK": ("A package crosses tenant boundary.", "Fail closed."),
        "CONTEXT_TOO_BROAD": ("A package contains unrelated project history or whole-thread sludge.", "Narrow to relevant graph coordinates and topic slices."),
        "MISSING_COORDINATES": ("A package lacks graph/projection coordinates.", "Ask for world/folder/thread scope before packaging."),
        "AMBIGUOUS_SCOPE": ("The request has multiple possible scopes.", "Ask a clarifying question instead of stuffing everything into context."),
        "AGENT_NOT_PERMITTED": ("The target role is not permitted for the context.", "Route to UNKNOWN_NEEDS_ROUTING or a permitted role."),
        "UNSAFE_ACTION_INCLUDED": ("The package grants forbidden action authority.", "Strip the action and preserve authority boundary."),
        "STALE_CONTEXT": ("A context ref is stale or not tied to current readback.", "Mark stale and ask for regeneration."),
        "VISUAL_ARTIFACT_WITHOUT_TRUTH_REFS": ("A visual artifact is requested without source truth refs.", "Block visual need until truth/readback refs exist."),
        "CONTEXT_PACKAGE_MISSING_EXCLUSIONS": ("A package does not list exclusions.", "Fail closed until exclusions and reasons are visible."),
        "CONTEXT_PACKAGE_OVERFILLED_WITH_UNRELATED_THREAD": ("A package includes unrelated prior thread history.", "Replace with compact highlights and refs."),
        "AMBIGUOUS_SCOPE_NOT_FLAGGED": ("Ambiguity exists but the package presents a single scope as certain.", "Flag ambiguity and ask for clarification."),
        "UNKNOWN_FAIL_CLOSED": ("The compiler cannot classify package safety.", "Fail closed and ask for scope clarification."),
    }
    blockers = []
    for blocker_type, (condition, warning) in details.items():
        blockers.append(
            ContextPackageBlocker(
                blocker_id=f"context_package_blocker_{blocker_type.lower()}",
                blocker_type=blocker_type,
                condition=condition,
                severity="CRITICAL" if blocker_type in {"RAW_SECRET_INCLUDED", "CROSS_CLIENT_LEAK", "CROSS_TENANT_LEAK", "UNKNOWN_FAIL_CLOSED"} else "HIGH",
                elioperator_warning=warning,
                fail_closed=True,
                next_safe_move="Return a blocked package readback and do not dispatch.",
            )
        )
    return tuple(blockers)


def build_report() -> ScopedContextPackageElioperatorReport:
    return ScopedContextPackageElioperatorReport(
        report_id="scoped_context_package_elioperator_report_v0",
        plain_summary="OpenClaw can package scoped context for a target agent without dumping whole threads or raw files.",
        what_this_enables="Each worker gets current coordinates, relevant slice summaries, refs, known/missing/blocked items, authority boundaries, and exclusions.",
        what_this_does_not_do_yet="It does not dispatch agents, call models, run retrieval, ingest transcripts/files, reveal secrets, or execute workflows.",
        how_context_packages_work="The compiler starts from graph/projection coordinates, narrows to relevant topic slices, and adds source/artifact/procedure/receipt/readback refs.",
        how_agents_get_context="Future agents receive role-specific packages; Mac Codex, PC Codex, Gemini/Agy, Cassandra, Guardian, Niles, and visual agents get different scopes.",
        how_raw_threads_are_avoided="Prior threads are compact highlights with source/thread refs, not full transcripts.",
        how_files_and_secrets_are_protected="Source files are safe refs/metadata only, and secrets are token refs only.",
        how_truth_is_preserved="Known facts cite source refs, receipts, or readbacks, while summaries remain non-truth context.",
        next_safe_move="Use the read-model as a package shape; add future dispatch only behind approved rails.",
    )


def build_examples() -> dict[str, Any]:
    return {
        "mac_codex_chat_surface": {
            "operator_message": "Continue the chat surface work.",
            "package_ref": "context_package_mac_codex_chat_surface",
            "expected_target": "MAC_CODEX",
            "expected_scope": "build/mission_control/chat_surface",
            "includes": ("SwiftUI task highlights", "screenshot refs", "Mac validation requirements", "recent app commits/readbacks"),
            "excludes": ("Repo A write authority", "Gmail/Coupa", "raw secrets"),
        },
        "pc_codex_chat_request_processor": {
            "operator_message": "Build the bounded chat request processor.",
            "package_ref": "context_package_pc_codex_chat_request_processor",
            "expected_target": "PC_CODEX",
            "expected_scope": "build/openclaw/backend/chat_router",
            "includes": ("router intake refs", "readback refs", "processor requirements", "tests"),
            "excludes": ("Mac Swift edits", "external actions"),
        },
        "gemini_agy_audit": {
            "operator_message": "Audit whether the chat-first pivot should reuse existing card contracts.",
            "package_ref": "context_package_gemini_agy_card_contract_audit",
            "expected_target": "GEMINI_AGY",
            "read_only": True,
            "forbidden": ("write authority", "commits", "secrets"),
        },
        "niles_x32": {
            "operator_message": "Niles, pull up the X32 routing context.",
            "package_ref": "context_package_niles_x32_routing",
            "expected_target": "NILES",
            "expected_scope": "music/live_music/x32/routing",
            "excludes": ("finance/client/private unrelated data",),
        },
        "cassandra_capital_hilton": {
            "package_ref": "context_package_cassandra_capital_hilton_invoice",
            "expected_target": "CASSANDRA",
            "expected_scope": "finance/capital_hilton/invoices",
            "includes": ("delivery workflow summary", "invoice artifact refs", "recipient candidate", "approval boundary"),
            "excludes": ("raw credentials", "send authority", "raw private evidence bodies"),
        },
        "guardian_approval": {
            "package_ref": "context_package_guardian_approval_boundary",
            "expected_target": "GUARDIAN",
            "includes": ("requested action", "risk", "proof refs", "protected refs", "missing approvals"),
            "excludes": ("irrelevant chat history",),
        },
        "visual_render_invoice_workflow": {
            "package_ref": "context_package_visual_invoice_workflow",
            "expected_target": "VISUAL_RENDER_AGENT",
            "visual_need_ref": "visual_need_capital_hilton_invoice_workflow",
            "includes": ("truth-backed facts", "missing/locked items", "device/layout hints"),
            "excludes": ("raw transcript", "raw file bodies", "secrets"),
        },
        "ambiguous_keep_going_blocked": {
            "operator_message": "Keep going with that thing.",
            "package_ref": "context_package_ambiguous_keep_going",
            "expected_target": "UNKNOWN_NEEDS_ROUTING",
            "active_blockers": ("MISSING_COORDINATES", "AMBIGUOUS_SCOPE", "AMBIGUOUS_SCOPE_NOT_FLAGGED"),
            "next_safe_move": "Ask whether to resume existing thread or start new one.",
        },
    }


def _all_authority_flags_false(payload: dict[str, Any]) -> bool:
    return not any(payload["authority_boundary"].values()) and not any(
        payload["scoped_context_package_compiler_contract"]["authority_boundary"].values()
    )


def _machine_proof(payload: dict[str, Any]) -> dict[str, Any]:
    packages = payload["scoped_context_packages_by_id"]
    package_values = packages.values()
    coordinates = payload["context_package_coordinates_by_id"].values()
    exclusions = payload["context_exclusions_by_id"].values()
    visual_needs = payload["context_package_visual_artifact_needs_by_id"].values()
    blockers = payload["context_package_blockers_by_id"].values()
    blocker_types = {blocker["blocker_type"] for blocker in blockers}
    examples = payload["examples"]
    return {
        "scoped_context_package_compiler_contract_model_present": True,
        "scoped_context_package_model_present": True,
        "context_package_coordinate_model_present": True,
        "context_highlight_model_present": True,
        "context_exclusion_model_present": True,
        "role_context_policy_model_present": True,
        "context_package_visual_artifact_need_model_present": True,
        "context_package_blocker_model_present": True,
        "scoped_context_package_elioperator_report_model_present": True,
        "target_agent_roles_present": set(TARGET_AGENT_ROLES).issubset(payload["target_agent_roles"]),
        "source_ref_types_present": set(SOURCE_REF_TYPES).issubset(payload["source_ref_types"]),
        "exclusion_reasons_present": set(EXCLUSION_REASONS).issubset(payload["exclusion_reasons"]),
        "packages_have_coordinates": all(package["world_ref"] and package["folder_ref"] and package["thread_ref"] for package in package_values),
        "packages_from_graph_projection_coordinates_not_folder_guess": all(coord["coordinate_confidence"] for coord in coordinates),
        "topic_slices_narrowed_when_present": all(
            package["topic_slice_refs"] or package["target_agent_role"] == "UNKNOWN_NEEDS_ROUTING"
            for package in package_values
        ),
        "ambiguous_scope_blocks_or_asks_clarification": packages["context_package_ambiguous_keep_going"]["target_agent_role"] == "UNKNOWN_NEEDS_ROUTING"
        and "which thread to resume" in packages["context_package_ambiguous_keep_going"]["missing_items"],
        "all_packages_list_exclusions": all(package["excluded_context"] for package in package_values),
        "exclusions_have_reasons": all(exclusion["reason"] in EXCLUSION_REASONS for exclusion in exclusions),
        "raw_transcript_excluded": any(exclusion["reason"] == "RAW_TRANSCRIPT_EXCLUDED" for exclusion in exclusions),
        "raw_file_body_excluded": any(exclusion["reason"] == "RAW_FILE_BODY_EXCLUDED" for exclusion in exclusions),
        "raw_secret_excluded": any(exclusion["reason"] == "SECRET_VALUE_EXCLUDED" for exclusion in exclusions),
        "visual_artifact_needs_have_truth_refs": all(
            (not need["needed"]) or bool(need["source_truth_refs"])
            for need in visual_needs
        ),
        "visual_artifact_detail_priority_outranks_style": payload["context_package_visual_artifact_needs_by_id"]["visual_need_capital_hilton_invoice_workflow"]["detail_priority"] == "HIGH"
        and payload["context_package_visual_artifact_needs_by_id"]["visual_need_capital_hilton_invoice_workflow"]["style_priority"] == "LOW",
        "mac_codex_example_exists": "mac_codex_chat_surface" in examples,
        "pc_codex_example_exists": "pc_codex_chat_request_processor" in examples,
        "gemini_agy_example_exists": "gemini_agy_audit" in examples,
        "niles_x32_example_exists": "niles_x32" in examples,
        "cassandra_capital_hilton_example_exists": "cassandra_capital_hilton" in examples,
        "guardian_example_exists": "guardian_approval" in examples,
        "visual_render_example_exists": "visual_render_invoice_workflow" in examples,
        "ambiguous_package_blocked_example_exists": "ambiguous_keep_going_blocked" in examples,
        "mac_codex_validation_expectations_present": "screenshot validation" in packages["context_package_mac_codex_chat_surface"]["validation_expectations"],
        "pc_codex_validation_expectations_present": "pytest" in packages["context_package_pc_codex_chat_request_processor"]["validation_expectations"],
        "gemini_agy_read_only": "file edits" in packages["context_package_gemini_agy_card_contract_audit"]["forbidden_actions"]
        and "read-only audit" in packages["context_package_gemini_agy_card_contract_audit"]["allowed_actions"],
        "cross_client_leak_blocked": "CROSS_CLIENT_LEAK" in blocker_types,
        "context_too_broad_blocked": "CONTEXT_TOO_BROAD" in blocker_types,
        "visual_artifact_without_truth_refs_blocked": "VISUAL_ARTIFACT_WITHOUT_TRUTH_REFS" in blocker_types,
        "package_missing_exclusions_blocked": "CONTEXT_PACKAGE_MISSING_EXCLUSIONS" in blocker_types,
        "overfilled_unrelated_thread_blocked": "CONTEXT_PACKAGE_OVERFILLED_WITH_UNRELATED_THREAD" in blocker_types,
        "ambiguous_scope_not_flagged_blocked": "AMBIGUOUS_SCOPE_NOT_FLAGGED" in blocker_types,
        "blockers_present": set(BLOCKER_TYPES).issubset(blocker_types),
        "all_live_authority_flags_false": _all_authority_flags_false(payload),
        "context_package_dispatch_performed": False,
        "agent_dispatch_performed": False,
        "model_call_performed": False,
        "workflow_run_performed": False,
        "memory_retrieval_performed": False,
        "raw_transcript_ingested": False,
        "raw_file_body_ingested": False,
        "secret_revealed": False,
        "visual_artifact_spawned": False,
        "external_action_performed": False,
        "credentials_or_secrets_included": False,
        "raw_private_bodies_included": False,
        "mission_control_swift_changed": False,
        "mac_sync_import_run": False,
        "git_push_pull_fetch_run": False,
        "content_hash": None,
    }


def build_scoped_context_package_compiler_contract(*, generated_at: str | None = None) -> dict[str, Any]:
    generated_at = generated_at or DEFAULT_GENERATED_AT
    contract = build_contract()
    coordinates = build_coordinates()
    highlights = build_highlights()
    exclusions = build_exclusions()
    policies = build_role_policies()
    packages = build_packages()
    visual_needs = build_visual_artifact_needs()
    blockers = build_blockers()
    report = build_report()
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "contract_status": CONTRACT_STATUS,
        "generated_at": generated_at,
        "operator_markdown_mode": "ELIOPERATOR",
        "target_agent_roles": TARGET_AGENT_ROLES,
        "source_ref_types": SOURCE_REF_TYPES,
        "exclusion_reasons": EXCLUSION_REASONS,
        "blocker_types": BLOCKER_TYPES,
        "model_schemas": _model_schemas(),
        "scoped_context_package_compiler_contract": asdict(contract),
        "context_package_coordinates_by_id": {coord.coordinate_id: asdict(coord) for coord in coordinates},
        "context_highlights_by_id": {highlight.highlight_id: asdict(highlight) for highlight in highlights},
        "context_exclusions_by_id": {exclusion.exclusion_id: asdict(exclusion) for exclusion in exclusions},
        "role_context_policies_by_id": {policy.policy_id: asdict(policy) for policy in policies},
        "scoped_context_packages_by_id": {package.context_package_id: asdict(package) for package in packages},
        "context_package_visual_artifact_needs_by_id": {need.visual_need_id: asdict(need) for need in visual_needs},
        "context_package_blockers_by_id": {blocker.blocker_id: asdict(blocker) for blocker in blockers},
        "scoped_context_package_elioperator_report": asdict(report),
        "examples": build_examples(),
        "relationship_refs": {
            "world_project_memory_graph_projection": "graph/projection coordinates and folder paths",
            "conversation_topic_slicer_contract": "topic slice refs and message pointer ranges",
            "worker_routing_intelligence": "target worker/role routing",
            "operator_file_metadata_intake": "safe source refs and metadata-only file posture",
            "operator_file_intake_visual_workspace_contract": "visual workspace and source-ref posture",
            "workflow_execution_package_compiler": "known/missing/blocked workflow context",
            "protected_secret_intake_contract": "secret_ref token-only posture",
            "cross_lane_reusable_block_registry_contract": "reusable fact/tokenized protected values",
            "cross_surface_artifact_handoff_registry_contract": "readback/artifact handoff refs",
            "openclaw_sensitive_policy": "private/sensitive path boundary",
        },
        "allowed_contract_scope": (
            "deterministic contract/read-model generation",
            "examples",
            "tests",
            "ELIOPERATOR report",
        ),
        "authority_boundary": AUTHORITY_BOUNDARY,
    }
    payload["machine_proof"] = _machine_proof(payload)
    payload["machine_proof"]["content_hash"] = _content_hash(payload)
    return payload


def format_operator_markdown(payload: dict[str, Any]) -> str:
    report = payload["scoped_context_package_elioperator_report"]
    packages = payload["scoped_context_packages_by_id"]
    package_lines = "\n".join(
        f"- {package['context_package_id']}: {package['target_agent_role']} at {package['folder_path']}"
        for package in packages.values()
    )
    exclusion_lines = "\n".join(
        f"- {exclusion['excluded_item_type']}: {exclusion['reason']}"
        for exclusion in payload["context_exclusions_by_id"].values()
    )
    visual_lines = "\n".join(
        f"- {need['visual_need_id']}: needed={need['needed']} truth_refs={len(need['source_truth_refs'])}"
        for need in payload["context_package_visual_artifact_needs_by_id"].values()
    )
    return "\n".join(
        [
            "# Scoped Context Package Compiler Contract v0",
            "",
            "ELIOPERATOR: Agents get scoped packages, not raw thread sludge.",
            "",
            "## What This Enables",
            "",
            report["what_this_enables"],
            "",
            "## What This Does Not Do Yet",
            "",
            report["what_this_does_not_do_yet"],
            "",
            "## Packages",
            "",
            package_lines,
            "",
            "## Exclusions",
            "",
            exclusion_lines,
            "",
            "## Visual Artifact Needs",
            "",
            visual_lines,
            "",
            "## Boundary",
            "",
            "No live context package dispatch, agent dispatch, model call, workflow run, live memory retrieval, raw transcript ingestion, raw file body ingestion, secret reveal, visual artifact spawn, external action, credential handling, raw-body ingestion, Mac sync/import, Swift change, or push was added.",
            "",
            f"Next safe move: {payload['scoped_context_package_compiler_contract']['next_safe_move']}",
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
    return {
        "schema_version": payload["schema_version"],
        "read_model_id": payload["read_model_id"],
        "contract_status": payload["contract_status"],
        "json_path": str(json_path) if json_path else None,
        "operator_path": str(operator_path) if operator_path else None,
        "package_count": len(payload["scoped_context_packages_by_id"]),
        "coordinate_count": len(payload["context_package_coordinates_by_id"]),
        "highlight_count": len(payload["context_highlights_by_id"]),
        "exclusion_count": len(payload["context_exclusions_by_id"]),
        "visual_need_count": len(payload["context_package_visual_artifact_needs_by_id"]),
        "mac_codex_example_exists": proof["mac_codex_example_exists"],
        "pc_codex_example_exists": proof["pc_codex_example_exists"],
        "gemini_agy_example_exists": proof["gemini_agy_example_exists"],
        "ambiguous_package_blocked_example_exists": proof["ambiguous_package_blocked_example_exists"],
        "visual_artifact_needs_have_truth_refs": proof["visual_artifact_needs_have_truth_refs"],
        "all_live_authority_flags_false": proof["all_live_authority_flags_false"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export the scoped context package compiler contract read-model.")
    parser.add_argument("--export-root", type=Path, default=DEFAULT_EXPORT_ROOT)
    parser.add_argument("--format", choices=("summary", "json"), default="json")
    args = parser.parse_args(argv)

    payload = build_scoped_context_package_compiler_contract()
    json_path, operator_path = write_exports(payload, args.export_root)
    output = payload if args.format == "json" else build_summary(payload, json_path, operator_path)
    sys.stdout.write(stable_json(output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
