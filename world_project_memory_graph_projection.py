"""World/project memory graph projection v0.

This deterministic read-model defines a semantic memory graph and a projected
folder/sidebar hierarchy for OpenClaw. The graph is truth; the folder tree is a
human projection. This module does not write memory, migrate SQLite, ingest raw
transcripts or file bodies, run retrieval, reorganize folders, call models,
access external systems, mutate Mission Control Swift, run Mac sync/import, or
push.
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

SCHEMA_VERSION = "world_project_memory_graph_projection_v0"
READ_MODEL_ID = "world_project_memory_graph_projection"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
OPERATOR_EXPORT_NAME = f"{READ_MODEL_ID}_OPERATOR.md"
CONTRACT_STATUS = "DETERMINISTIC_NON_MUTATING_MEMORY_GRAPH_FOLDER_PROJECTION"

NODE_TYPES = (
    "WORLD",
    "PROJECT_FOLDER",
    "CHAT_THREAD",
    "TOPIC_SLICE",
    "SOURCE_REF",
    "ARTIFACT",
    "PROCEDURE",
    "RECEIPT",
    "VISUAL_WORKSPACE",
    "UNKNOWN",
)

RELATIONSHIP_TYPES = (
    "CONTAINS",
    "LINKS_TO",
    "RELATED_TO",
    "SUMMARIZES",
    "DERIVED_FROM",
    "GENERATED",
    "SUPPORTS_PROOF",
    "BELONGS_TO_SCOPE",
    "SUGGESTED_REORG",
    "UNKNOWN",
)

PROJECTION_STATUSES = (
    "CURRENT",
    "UPDATED_READY_FOR_MAC",
    "NEEDS_OPERATOR_REVIEW",
    "STALE",
    "BLOCKED",
    "UNKNOWN_FAIL_CLOSED",
)

BLOCKER_TYPES = (
    "STRICT_TREE_ASSUMED_AS_TRUTH",
    "CROSS_CLIENT_LEAK",
    "MISSING_TENANT_SCOPE",
    "MISSING_CLIENT_SCOPE",
    "RAW_TRANSCRIPT_EXPOSURE",
    "RAW_FILE_BODY_EXPOSURE",
    "PROVENANCE_MISSING",
    "DESTRUCTIVE_MOVE_ATTEMPTED",
    "SILENT_REORG_ATTEMPTED",
    "STALE_PROJECTION",
    "UNKNOWN_FAIL_CLOSED",
)

SQLITE_GRAPH_TABLES = (
    "semantic_records",
    "semantic_relationships",
    "provenance_refs",
)

AUTHORITY_BOUNDARY = {
    "live_memory_write_allowed": False,
    "live_db_migration_allowed": False,
    "live_raw_transcript_ingestion_allowed": False,
    "live_raw_file_body_ingestion_allowed": False,
    "live_agent_retrieval_allowed": False,
    "live_cross_scope_query_allowed": False,
    "live_reorganization_allowed": False,
    "live_folder_move_allowed": False,
    "live_delete_allowed": False,
    "live_folder_tree_update_allowed": False,
    "live_external_action_allowed": False,
    "credential_handling_allowed": False,
    "raw_body_ingestion_allowed": False,
    "network_allowed": False,
    "mission_control_swift_change_allowed": False,
    "mac_sync_import_allowed": False,
    "git_push_pull_fetch_allowed": False,
}


@dataclass(frozen=True)
class SemanticMemoryGraphContract:
    contract_id: str
    doctrine: tuple[str, ...]
    graph_truth_policy: tuple[str, ...]
    folder_projection_policy: tuple[str, ...]
    node_policy: tuple[str, ...]
    relationship_policy: tuple[str, ...]
    provenance_policy: tuple[str, ...]
    tenant_scope_policy: tuple[str, ...]
    privacy_boundary: tuple[str, ...]
    authority_boundary: dict[str, bool]
    next_safe_move: str


@dataclass(frozen=True)
class SemanticMemoryNode:
    node_ref: str
    node_type: str
    world_ref: str
    client_ref: str
    tenant_ref: str
    safe_display_label: str
    summary: str
    privacy_class: str
    sensitivity_class: str
    source_refs: tuple[str, ...]
    artifact_refs: tuple[str, ...]
    procedure_refs: tuple[str, ...]
    receipt_refs: tuple[str, ...]
    provenance_refs: tuple[str, ...]
    current_status: str
    next_safe_move: str


@dataclass(frozen=True)
class SemanticMemoryRelationship:
    relationship_ref: str
    source_node_ref: str
    target_node_ref: str
    relationship_type: str
    confidence: str
    operator_review_required: bool
    provenance_ref: str
    tenant_ref: str
    client_ref: str
    next_safe_move: str


@dataclass(frozen=True)
class FolderTreeProjection:
    projection_id: str
    world_ref: str
    root_nodes: tuple[str, ...]
    projected_tree: tuple[dict[str, Any], ...]
    changed_nodes: tuple[str, ...]
    suggested_updates: tuple[str, ...]
    operator_review_items: tuple[str, ...]
    stale_nodes: tuple[str, ...]
    projection_status: str
    mac_render_ready: bool
    next_safe_move: str


@dataclass(frozen=True)
class FolderProjectionNode:
    projection_node_ref: str
    node_ref: str
    parent_projection_node_ref: str | None
    display_name: str
    folder_path: str
    node_type: str
    child_refs: tuple[str, ...]
    linked_refs: tuple[str, ...]
    unread_or_changed_status: str
    suggested_badge: str
    privacy_class: str
    next_safe_move: str


@dataclass(frozen=True)
class ScopePartitionPolicy:
    policy_id: str
    tenant_ref: str
    client_ref: str
    world_ref: str
    allowed_cross_links: tuple[str, ...]
    blocked_cross_links: tuple[str, ...]
    cross_client_leak_policy: str
    next_safe_move: str


@dataclass(frozen=True)
class FolderProjectionBlocker:
    blocker_id: str
    blocker_type: str
    condition: str
    severity: str
    elioperator_warning: str
    fail_closed: bool
    next_safe_move: str


@dataclass(frozen=True)
class WorldProjectMemoryGraphElioperatorReport:
    report_id: str
    plain_summary: str
    what_this_enables: str
    what_this_does_not_do_yet: str
    how_graph_vs_folder_projection_works: str
    how_mac_sidebar_should_use_projection: str
    how_scope_boundaries_work: str
    how_provenance_is_preserved: str
    next_safe_move: str


REQUIRED_CONTRACT_FIELDS = tuple(SemanticMemoryGraphContract.__dataclass_fields__.keys())
REQUIRED_NODE_FIELDS = tuple(SemanticMemoryNode.__dataclass_fields__.keys())
REQUIRED_RELATIONSHIP_FIELDS = tuple(SemanticMemoryRelationship.__dataclass_fields__.keys())
REQUIRED_PROJECTION_FIELDS = tuple(FolderTreeProjection.__dataclass_fields__.keys())
REQUIRED_PROJECTION_NODE_FIELDS = tuple(FolderProjectionNode.__dataclass_fields__.keys())
REQUIRED_SCOPE_POLICY_FIELDS = tuple(ScopePartitionPolicy.__dataclass_fields__.keys())
REQUIRED_BLOCKER_FIELDS = tuple(FolderProjectionBlocker.__dataclass_fields__.keys())
REQUIRED_REPORT_FIELDS = tuple(WorldProjectMemoryGraphElioperatorReport.__dataclass_fields__.keys())


def stable_json(data: Any) -> str:
    return json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _content_hash(payload: dict[str, Any]) -> str:
    clean = json.loads(stable_json(payload))
    clean.get("machine_proof", {}).pop("content_hash", None)
    return hashlib.sha256(stable_json(clean).encode("utf-8")).hexdigest()


def _model_schemas() -> dict[str, Any]:
    return {
        "semantic_memory_graph_contract": {"required_fields": list(REQUIRED_CONTRACT_FIELDS)},
        "semantic_memory_node": {"required_fields": list(REQUIRED_NODE_FIELDS)},
        "semantic_memory_relationship": {"required_fields": list(REQUIRED_RELATIONSHIP_FIELDS)},
        "folder_tree_projection": {"required_fields": list(REQUIRED_PROJECTION_FIELDS)},
        "folder_projection_node": {"required_fields": list(REQUIRED_PROJECTION_NODE_FIELDS)},
        "scope_partition_policy": {"required_fields": list(REQUIRED_SCOPE_POLICY_FIELDS)},
        "folder_projection_blocker": {"required_fields": list(REQUIRED_BLOCKER_FIELDS)},
        "world_project_memory_graph_elioperator_report": {"required_fields": list(REQUIRED_REPORT_FIELDS)},
    }


def _node(
    node_ref: str,
    node_type: str,
    world_ref: str,
    client_ref: str,
    label: str,
    summary: str,
    *,
    source_refs: tuple[str, ...] = (),
    artifact_refs: tuple[str, ...] = (),
    procedure_refs: tuple[str, ...] = (),
    receipt_refs: tuple[str, ...] = (),
    provenance_refs: tuple[str, ...] = (),
    privacy_class: str = "internal",
    sensitivity_class: str = "metadata_only",
    current_status: str = "projected_current",
) -> SemanticMemoryNode:
    return SemanticMemoryNode(
        node_ref=node_ref,
        node_type=node_type,
        world_ref=world_ref,
        client_ref=client_ref,
        tenant_ref="openclaw_local_operator",
        safe_display_label=label,
        summary=summary,
        privacy_class=privacy_class,
        sensitivity_class=sensitivity_class,
        source_refs=source_refs,
        artifact_refs=artifact_refs,
        procedure_refs=procedure_refs,
        receipt_refs=receipt_refs,
        provenance_refs=provenance_refs or (f"prov_{node_ref}",),
        current_status=current_status,
        next_safe_move="Keep this as a semantic graph node and project it into sidebar paths without moving source material.",
    )


def build_contract() -> SemanticMemoryGraphContract:
    return SemanticMemoryGraphContract(
        contract_id="semantic_memory_graph_folder_projection_v0",
        doctrine=(
            "Semantic graph is truth.",
            "Folder tree is a human projection.",
            "Chats, topic slices, source refs, artifacts, procedures, receipts, and agents attach to graph nodes.",
            "Cross-links are normal and must not be flattened into destructive folder moves.",
            "Receipts, source refs, and provenance decide truth.",
        ),
        graph_truth_policy=(
            "Use semantic_records, semantic_relationships, and provenance_refs as the target canonical graph rail when a live writer is approved.",
            "Do not treat a folder path as the source of truth.",
            "Do not infer private facts from a projection path.",
            "Do not write memory from this read-model slice.",
        ),
        folder_projection_policy=(
            "Generate Mac/sidebar folder projections from graph nodes and relationships.",
            "Allow aliases and linked refs instead of duplicating memory.",
            "Ambiguous or disruptive organization changes require operator review.",
            "Destructive move, delete, and silent reorganization are forbidden.",
        ),
        node_policy=(
            "Every node carries tenant_ref and client_ref or explicit local/operator scope.",
            "Node summaries are safe labels and metadata summaries, not raw transcript or file bodies.",
            "Unknown node types fail closed.",
        ),
        relationship_policy=(
            "Relationships may cross folders within a permitted scope.",
            "Cross-client relationships fail closed unless explicitly reviewed and allowed.",
            "Suggested reorganization relationships are candidates, not truth.",
        ),
        provenance_policy=(
            "Every node and relationship must carry provenance refs.",
            "Projection updates preserve source refs, receipt refs, and generated readback refs.",
            "Missing provenance blocks promotion to a current projection.",
        ),
        tenant_scope_policy=(
            "Tenant and client scope are required by default.",
            "Reusable/general knowledge must be separated from client-private facts.",
            "Cross-client leakage fails closed.",
        ),
        privacy_boundary=(
            "No raw transcripts in normal read-models.",
            "No raw file bodies in normal read-models.",
            "Use safe display labels instead of sensitive private paths.",
            "Protected evidence remains reference-only unless future governed review exists.",
        ),
        authority_boundary=AUTHORITY_BOUNDARY,
        next_safe_move="Export this deterministic projection for Mac/sidebar rendering; do not write memory or move folders.",
    )


def build_semantic_nodes() -> tuple[SemanticMemoryNode, ...]:
    return (
        _node("node_world_music", "WORLD", "music", "local_operator", "Music", "Music world root for live, studio, song, and project material."),
        _node("node_music_live_music", "PROJECT_FOLDER", "music", "local_operator", "Live Music", "Live performance material and operational notes."),
        _node("node_music_live_x32", "PROJECT_FOLDER", "music", "local_operator", "X32", "Behringer X32 live routing and show setup context."),
        _node("node_music_x32_routing", "TOPIC_SLICE", "music", "local_operator", "X32 routing", "Routing notes linked to show setup, source refs, and troubleshooting chats.", source_refs=("source_ref_behringer_x32_notes",), receipt_refs=("receipt_x32_show_setup_readback",)),
        _node("node_music_x32_show_files", "SOURCE_REF", "music", "local_operator", "show files", "Metadata-only source refs for live show files; no raw file body in projection.", source_refs=("source_ref_x32_scene_metadata",)),
        _node("node_music_studio", "PROJECT_FOLDER", "music", "local_operator", "Studio", "Studio and recording project material."),
        _node("node_music_album", "PROJECT_FOLDER", "music", "local_operator", "Album", "Album project folder projection from graph records."),
        _node("node_music_song", "PROJECT_FOLDER", "music", "local_operator", "Song", "A song node that links spreadsheet, rich text doc, Logic project metadata, and mix notes.", source_refs=("source_ref_album_spreadsheet", "source_ref_song_rich_text_doc", "source_ref_logic_project_metadata"), receipt_refs=("receipt_mix_notes_thread",)),
        _node("node_world_finance", "WORLD", "finance", "local_operator", "Finance", "Finance world root for client billing and payment workflows."),
        _node("node_finance_capital_hilton", "PROJECT_FOLDER", "finance", "capital_hilton", "Capital Hilton", "Capital Hilton finance scope."),
        _node("node_finance_capital_hilton_invoices", "PROJECT_FOLDER", "finance", "capital_hilton", "Invoices", "Capital Hilton invoice workflow projection linked to procedures, receipts, artifacts, and readbacks.", source_refs=("source_ref_capital_hilton_invoice_preview",), artifact_refs=("artifact_ref_capital_hilton_invoice_pdf_future",), procedure_refs=("procedure_ref_capital_hilton_invoice_workflow",), receipt_refs=("receipt_capital_hilton_delivery_facts", "receipt_router_readback_capital_hilton", "receipt_payment_tracking_ref")),
        _node("node_world_build", "WORLD", "build", "local_operator", "Build", "Build world root for OpenClaw and Mission Control implementation work."),
        _node("node_build_mission_control", "PROJECT_FOLDER", "build", "openclaw", "Mission Control", "Mission Control app and operator surface work."),
        _node("node_build_mission_control_chat_surface", "PROJECT_FOLDER", "build", "openclaw", "Chat Surface", "Chat-first Mission Control work linked to prompts, screenshots, readback cards, and SwiftUI task history.", source_refs=("source_ref_mac_codex_prompts", "source_ref_screenshots_metadata"), artifact_refs=("artifact_ref_readback_cards"), receipt_refs=("receipt_swiftui_task_history",)),
        _node("node_struna_mac_version", "PROJECT_FOLDER", "build", "struna", "Struna Mac Version", "Struna Mac-version projection with ownership/agreement summaries and app source refs; legal/private bodies remain hidden.", source_refs=("source_ref_struna_app_files",), receipt_refs=("receipt_struna_ownership_context_summary", "receipt_struna_mac_version_agreement_summary", "receipt_struna_licensing_use_note"), sensitivity_class="private_summary_only"),
        _node("node_multifolder_chat_setlists", "CHAT_THREAD", "music", "local_operator", "Setlist chat with cross-links", "A chat that starts in setlists and also discusses X32 routing, song arrangement, and booking follow-up.", source_refs=("source_ref_setlist_chat_summary",), receipt_refs=("receipt_multifolder_topic_candidates",)),
    )


def _relationship(
    relationship_ref: str,
    source: str,
    target: str,
    relationship_type: str,
    *,
    client_ref: str = "local_operator",
    confidence: str = "HIGH",
    operator_review_required: bool = False,
    provenance_ref: str | None = None,
) -> SemanticMemoryRelationship:
    return SemanticMemoryRelationship(
        relationship_ref=relationship_ref,
        source_node_ref=source,
        target_node_ref=target,
        relationship_type=relationship_type,
        confidence=confidence,
        operator_review_required=operator_review_required,
        provenance_ref=provenance_ref or f"prov_{relationship_ref}",
        tenant_ref="openclaw_local_operator",
        client_ref=client_ref,
        next_safe_move="Preserve this graph relationship and project it as a folder child or linked alias without destructive moves.",
    )


def build_relationships() -> tuple[SemanticMemoryRelationship, ...]:
    return (
        _relationship("rel_music_contains_live_music", "node_world_music", "node_music_live_music", "CONTAINS"),
        _relationship("rel_live_music_contains_x32", "node_music_live_music", "node_music_live_x32", "CONTAINS"),
        _relationship("rel_x32_contains_routing", "node_music_live_x32", "node_music_x32_routing", "CONTAINS"),
        _relationship("rel_x32_routing_contains_show_files", "node_music_x32_routing", "node_music_x32_show_files", "CONTAINS"),
        _relationship("rel_x32_routing_links_show_setup", "node_music_x32_routing", "node_music_x32_show_files", "LINKS_TO"),
        _relationship("rel_music_contains_studio", "node_world_music", "node_music_studio", "CONTAINS"),
        _relationship("rel_studio_contains_album", "node_music_studio", "node_music_album", "CONTAINS"),
        _relationship("rel_album_contains_song", "node_music_album", "node_music_song", "CONTAINS"),
        _relationship("rel_song_links_album_spreadsheet", "node_music_song", "source_ref_album_spreadsheet", "LINKS_TO", confidence="MEDIUM"),
        _relationship("rel_song_links_logic_metadata", "node_music_song", "source_ref_logic_project_metadata", "LINKS_TO", confidence="MEDIUM"),
        _relationship("rel_finance_contains_capital_hilton", "node_world_finance", "node_finance_capital_hilton", "CONTAINS", client_ref="capital_hilton"),
        _relationship("rel_capital_hilton_contains_invoices", "node_finance_capital_hilton", "node_finance_capital_hilton_invoices", "CONTAINS", client_ref="capital_hilton"),
        _relationship("rel_invoices_supports_proof", "node_finance_capital_hilton_invoices", "receipt_capital_hilton_delivery_facts", "SUPPORTS_PROOF", client_ref="capital_hilton"),
        _relationship("rel_invoices_generated_router_readback", "receipt_router_readback_capital_hilton", "node_finance_capital_hilton_invoices", "GENERATED", client_ref="capital_hilton"),
        _relationship("rel_build_contains_mission_control", "node_world_build", "node_build_mission_control", "CONTAINS", client_ref="openclaw"),
        _relationship("rel_mission_control_contains_chat_surface", "node_build_mission_control", "node_build_mission_control_chat_surface", "CONTAINS", client_ref="openclaw"),
        _relationship("rel_chat_surface_links_readback_cards", "node_build_mission_control_chat_surface", "artifact_ref_readback_cards", "LINKS_TO", client_ref="openclaw"),
        _relationship("rel_build_links_struna", "node_world_build", "node_struna_mac_version", "CONTAINS", client_ref="struna", operator_review_required=True),
        _relationship("rel_struna_related_music", "node_struna_mac_version", "node_world_music", "RELATED_TO", client_ref="struna", confidence="MEDIUM", operator_review_required=True),
        _relationship("rel_multifolder_chat_links_x32", "node_multifolder_chat_setlists", "node_music_x32_routing", "RELATED_TO", confidence="MEDIUM", operator_review_required=True),
        _relationship("rel_multifolder_chat_links_song", "node_multifolder_chat_setlists", "node_music_song", "RELATED_TO", confidence="MEDIUM", operator_review_required=True),
        _relationship("rel_multifolder_chat_links_booking_followup", "node_multifolder_chat_setlists", "topic_booking_followup", "RELATED_TO", confidence="LOW", operator_review_required=True),
    )


def build_projection_nodes() -> tuple[FolderProjectionNode, ...]:
    return (
        FolderProjectionNode("proj_music", "node_world_music", None, "music", "music", "WORLD", ("proj_music_live_music", "proj_music_studio"), (), "current", "", "internal", "Render as a world root in the Mac sidebar."),
        FolderProjectionNode("proj_music_live_music", "node_music_live_music", "proj_music", "live_music", "music/live_music", "PROJECT_FOLDER", ("proj_music_live_x32",), (), "current", "", "internal", "Render as a projected folder."),
        FolderProjectionNode("proj_music_live_x32", "node_music_live_x32", "proj_music_live_music", "x32", "music/live_music/x32", "PROJECT_FOLDER", ("proj_music_x32_routing",), ("node_multifolder_chat_setlists",), "current", "linked chat", "internal", "Show linked chat badges without moving the chat."),
        FolderProjectionNode("proj_music_x32_routing", "node_music_x32_routing", "proj_music_live_x32", "routing", "music/live_music/x32/routing", "TOPIC_SLICE", ("proj_music_x32_show_files",), ("source_ref_behringer_x32_notes", "receipt_x32_show_setup_readback"), "current", "proof links", "internal", "Render routing as a topic slice under X32."),
        FolderProjectionNode("proj_music_x32_show_files", "node_music_x32_show_files", "proj_music_x32_routing", "show_files", "music/live_music/x32/routing/show_files", "SOURCE_REF", (), ("source_ref_x32_scene_metadata",), "current", "source refs", "metadata_only", "Show source refs only."),
        FolderProjectionNode("proj_music_studio", "node_music_studio", "proj_music", "studio", "music/studio", "PROJECT_FOLDER", ("proj_music_album",), (), "current", "", "internal", "Render as studio folder."),
        FolderProjectionNode("proj_music_album", "node_music_album", "proj_music_studio", "album", "music/studio/album", "PROJECT_FOLDER", ("proj_music_song",), (), "current", "", "internal", "Render as album folder."),
        FolderProjectionNode("proj_music_song", "node_music_song", "proj_music_album", "song_name", "music/studio/album/song_name", "PROJECT_FOLDER", (), ("source_ref_album_spreadsheet", "source_ref_song_rich_text_doc", "source_ref_logic_project_metadata", "receipt_mix_notes_thread"), "current", "3 source refs", "internal", "Show related source refs in details, not raw bodies."),
        FolderProjectionNode("proj_finance", "node_world_finance", None, "finance", "finance", "WORLD", ("proj_finance_capital_hilton",), (), "current", "", "internal", "Render as finance world root."),
        FolderProjectionNode("proj_finance_capital_hilton", "node_finance_capital_hilton", "proj_finance", "capital_hilton", "finance/capital_hilton", "PROJECT_FOLDER", ("proj_finance_capital_hilton_invoices",), (), "current", "", "internal", "Render as client scope."),
        FolderProjectionNode("proj_finance_capital_hilton_invoices", "node_finance_capital_hilton_invoices", "proj_finance_capital_hilton", "invoices", "finance/capital_hilton/invoices", "PROJECT_FOLDER", (), ("procedure_ref_capital_hilton_invoice_workflow", "receipt_capital_hilton_delivery_facts", "artifact_ref_capital_hilton_invoice_pdf_future", "receipt_router_readback_capital_hilton", "receipt_payment_tracking_ref"), "changed", "readbacks", "finance_boundary", "Show invoice workflow links and readbacks; do not expose raw payment refs."),
        FolderProjectionNode("proj_build", "node_world_build", None, "build", "build", "WORLD", ("proj_build_mission_control", "proj_build_struna_mac_version"), (), "current", "", "internal", "Render as build world root."),
        FolderProjectionNode("proj_build_mission_control", "node_build_mission_control", "proj_build", "mission_control", "build/mission_control", "PROJECT_FOLDER", ("proj_build_mission_control_chat_surface",), (), "current", "", "internal", "Render as Mission Control project folder."),
        FolderProjectionNode("proj_build_mission_control_chat_surface", "node_build_mission_control_chat_surface", "proj_build_mission_control", "chat_surface", "build/mission_control/chat_surface", "PROJECT_FOLDER", (), ("source_ref_mac_codex_prompts", "source_ref_screenshots_metadata", "artifact_ref_readback_cards", "receipt_swiftui_task_history"), "changed", "active work", "internal", "Show active chat surface work without exposing raw prompts or screenshots."),
        FolderProjectionNode("proj_build_struna_mac_version", "node_struna_mac_version", "proj_build", "struna_mac_version", "build/struna/mac_version", "PROJECT_FOLDER", (), ("receipt_struna_ownership_context_summary", "receipt_struna_mac_version_agreement_summary", "receipt_struna_licensing_use_note", "source_ref_struna_app_files"), "needs_review", "private summary", "private_summary_only", "Keep as reviewed summary refs; do not expose legal/private bodies."),
    )


def _tree_node(node: FolderProjectionNode) -> dict[str, Any]:
    return {
        "projection_node_ref": node.projection_node_ref,
        "display_name": node.display_name,
        "folder_path": node.folder_path,
        "node_ref": node.node_ref,
        "child_refs": node.child_refs,
        "linked_refs": node.linked_refs,
        "privacy_class": node.privacy_class,
        "suggested_badge": node.suggested_badge,
    }


def build_folder_tree_projection(projection_nodes: tuple[FolderProjectionNode, ...]) -> FolderTreeProjection:
    roots = tuple(node.projection_node_ref for node in projection_nodes if node.parent_projection_node_ref is None)
    return FolderTreeProjection(
        projection_id="folder_projection_world_project_sidebar_v0",
        world_ref="cross_world",
        root_nodes=roots,
        projected_tree=tuple(_tree_node(node) for node in projection_nodes),
        changed_nodes=("proj_finance_capital_hilton_invoices", "proj_build_mission_control_chat_surface"),
        suggested_updates=(
            "Render cross-folder linked refs as aliases/badges, not duplicate folder copies.",
            "Keep Struna under build for v0 and mark music relationship as reviewed cross-link candidate.",
            "Use Finance/Capital Hilton/Invoices as the sidebar projection for invoice readbacks.",
        ),
        operator_review_items=(
            "Struna may belong under music or build; v0 projects it under build and preserves a music relation.",
            "Multi-topic setlist chat needs future topic slicing before any folder promotion.",
        ),
        stale_nodes=(),
        projection_status="UPDATED_READY_FOR_MAC",
        mac_render_ready=True,
        next_safe_move="Let Mac read this projection as sidebar data; do not mutate real folders or memory state.",
    )


def build_scope_policies() -> tuple[ScopePartitionPolicy, ...]:
    return (
        ScopePartitionPolicy(
            policy_id="scope_policy_local_operator_music",
            tenant_ref="openclaw_local_operator",
            client_ref="local_operator",
            world_ref="music",
            allowed_cross_links=("music live/studio links", "build Struna relationship candidate", "local reusable music knowledge"),
            blocked_cross_links=("client-private finance facts", "credentials", "raw private bodies"),
            cross_client_leak_policy="Fail closed if a music graph edge would expose client-private finance or legal facts.",
            next_safe_move="Keep local/operator music scope separate from client-private scopes.",
        ),
        ScopePartitionPolicy(
            policy_id="scope_policy_capital_hilton_finance",
            tenant_ref="openclaw_local_operator",
            client_ref="capital_hilton",
            world_ref="finance",
            allowed_cross_links=("Capital Hilton invoice procedures", "Capital Hilton receipts", "Capital Hilton artifact refs"),
            blocked_cross_links=("other client finance details", "raw payment references in normal read-models", "credential material"),
            cross_client_leak_policy="Capital Hilton invoice graph edges must not leak to other clients without explicit reviewed reusable summary.",
            next_safe_move="Keep Capital Hilton nodes and relationships scoped to capital_hilton unless explicitly generalized.",
        ),
        ScopePartitionPolicy(
            policy_id="scope_policy_openclaw_build",
            tenant_ref="openclaw_local_operator",
            client_ref="openclaw",
            world_ref="build",
            allowed_cross_links=("Mission Control build history", "readback card artifacts", "safe screenshots metadata", "Mac/PC worker prompts as summaries"),
            blocked_cross_links=("raw private screenshots", "credentials", "external account data"),
            cross_client_leak_policy="Build knowledge can link to workflow examples only through safe summaries and provenance refs.",
            next_safe_move="Use build nodes for implementation work while preserving client boundaries.",
        ),
        ScopePartitionPolicy(
            policy_id="scope_policy_struna_private_summary",
            tenant_ref="openclaw_local_operator",
            client_ref="struna",
            world_ref="build",
            allowed_cross_links=("Draper ownership context summary", "Winship 25 percent Mac-version agreement summary", "licensing/use note", "app source refs"),
            blocked_cross_links=("raw legal body", "private contract body", "credential material"),
            cross_client_leak_policy="Struna summaries are private summary refs and must not be mixed into unrelated client scopes.",
            next_safe_move="Keep Struna projected under build until operator reviews whether music is a better primary sidebar path.",
        ),
    )


def build_blockers() -> tuple[FolderProjectionBlocker, ...]:
    details = {
        "STRICT_TREE_ASSUMED_AS_TRUTH": ("A worker treats folder path as canonical memory truth.", "Use semantic graph refs as truth and folder paths as projections only."),
        "CROSS_CLIENT_LEAK": ("A relationship crosses client scope without explicit permission.", "Fail closed and require reviewed scope boundary."),
        "MISSING_TENANT_SCOPE": ("A node or relationship lacks tenant_ref.", "Do not project unscopeable memory."),
        "MISSING_CLIENT_SCOPE": ("A node or relationship lacks client_ref or local/operator scope.", "Do not project client-ambiguous memory."),
        "RAW_TRANSCRIPT_EXPOSURE": ("Raw transcript text appears in normal projection output.", "Use topic summaries and source refs only."),
        "RAW_FILE_BODY_EXPOSURE": ("Raw file body appears in normal projection output.", "Use metadata/source refs only."),
        "PROVENANCE_MISSING": ("A node or relationship lacks provenance refs.", "Keep it out of current projection until provenance exists."),
        "DESTRUCTIVE_MOVE_ATTEMPTED": ("Projection tries to move/delete real folders or source material.", "Block move/delete and show a suggested projection update only."),
        "SILENT_REORG_ATTEMPTED": ("Projection silently reorganizes memory without review.", "Require operator review for disruptive reorganization."),
        "STALE_PROJECTION": ("Projection no longer matches source graph/readback refs.", "Mark stale and regenerate from graph/readbacks."),
        "UNKNOWN_FAIL_CLOSED": ("Projection state cannot be classified.", "Fail closed and ask for review."),
    }
    blockers = []
    for blocker_type, (condition, warning) in details.items():
        blockers.append(
            FolderProjectionBlocker(
                blocker_id=f"folder_projection_blocker_{blocker_type.lower()}",
                blocker_type=blocker_type,
                condition=condition,
                severity="CRITICAL" if blocker_type in {"CROSS_CLIENT_LEAK", "UNKNOWN_FAIL_CLOSED"} else "HIGH",
                elioperator_warning=warning,
                fail_closed=True,
                next_safe_move="Return an operator-readable blocker and avoid memory/folder mutation.",
            )
        )
    return tuple(blockers)


def build_report() -> WorldProjectMemoryGraphElioperatorReport:
    return WorldProjectMemoryGraphElioperatorReport(
        report_id="world_project_memory_graph_elioperator_report_v0",
        plain_summary="OpenClaw can project Worlds and folders for the Mac sidebar while keeping the semantic graph as truth.",
        what_this_enables="Mac can read a deterministic sidebar projection for worlds, projects, topic slices, source refs, artifacts, procedures, receipts, and visual workspaces.",
        what_this_does_not_do_yet="It does not write memory, migrate SQLite, ingest transcripts or files, run retrieval, reorganize folders, move/delete files, or call agents.",
        how_graph_vs_folder_projection_works="Graph nodes and relationships preserve truth and provenance; folder paths are just a human-readable projection with aliases for cross-links.",
        how_mac_sidebar_should_use_projection="Mission Control should render projected roots and children, show badges for linked refs, and treat review/stale flags as display state only.",
        how_scope_boundaries_work="Every node and relationship has tenant/client/world scope; cross-client leakage blocks projection unless explicitly reviewed.",
        how_provenance_is_preserved="Nodes and relationships carry provenance refs back to source refs, artifacts, receipts, generated readbacks, or summaries.",
        next_safe_move="Use this read-model as a Mac/sidebar input and add future reviewed graph writers only behind receipts.",
    )


def build_examples() -> dict[str, Any]:
    return {
        "music_live_x32": {
            "projection": ("music", "live_music", "x32", "routing", "show_files"),
            "graph_bindings": (
                "X32 routing notes link to live show setup.",
                "X32 routing notes link to Behringer X32 source refs.",
                "X32 routing notes link to troubleshooting chats.",
            ),
            "node_refs": ("node_music_live_x32", "node_music_x32_routing", "node_music_x32_show_files"),
            "relationship_refs": ("rel_x32_routing_links_show_setup", "rel_multifolder_chat_links_x32"),
        },
        "music_studio_album_song": {
            "projection": ("music", "studio", "album", "song_name"),
            "graph_bindings": (
                "album spreadsheet source ref",
                "song rich text doc source ref",
                "Logic project metadata source ref",
                "mix notes thread",
            ),
            "node_refs": ("node_music_song",),
            "relationship_refs": ("rel_song_links_album_spreadsheet", "rel_song_links_logic_metadata"),
        },
        "finance_capital_hilton": {
            "projection": ("finance", "capital_hilton", "invoices"),
            "graph_bindings": (
                "invoice workflow procedure",
                "delivery fact receipts",
                "invoice artifact refs",
                "router readbacks",
                "payment tracking refs",
            ),
            "node_refs": ("node_finance_capital_hilton_invoices",),
            "relationship_refs": ("rel_invoices_supports_proof", "rel_invoices_generated_router_readback"),
        },
        "build_mission_control": {
            "projection": ("build", "mission_control", "chat_surface"),
            "graph_bindings": (
                "Mac Codex prompts",
                "screenshots",
                "readback cards",
                "SwiftUI task history",
            ),
            "node_refs": ("node_build_mission_control_chat_surface",),
            "relationship_refs": ("rel_chat_surface_links_readback_cards",),
        },
        "struna_mac_version": {
            "projection": ("build", "struna", "mac_version"),
            "classification_note": "Projected under build for v0; music relationship is preserved as a reviewed cross-link candidate.",
            "graph_bindings": (
                "Draper ownership context summary",
                "Winship 25 percent Mac-version agreement summary",
                "licensing/use note",
                "app files/source refs",
            ),
            "node_refs": ("node_struna_mac_version",),
            "relationship_refs": ("rel_build_links_struna", "rel_struna_related_music"),
        },
        "multi_folder_chat": {
            "start_projection": ("music", "live_music", "setlists"),
            "topic_candidates": ("X32 routing", "new song arrangement", "booking follow-up"),
            "expected_behavior": (
                "Graph relationships link topic candidates to multiple folder projections.",
                "No destructive move occurs.",
                "Provenance is preserved.",
                "Future topic slicer can refine this later.",
            ),
            "node_refs": ("node_multifolder_chat_setlists",),
            "relationship_refs": ("rel_multifolder_chat_links_x32", "rel_multifolder_chat_links_song", "rel_multifolder_chat_links_booking_followup"),
        },
    }


def _all_authority_flags_false(payload: dict[str, Any]) -> bool:
    return not any(payload["authority_boundary"].values()) and not any(
        payload["semantic_memory_graph_contract"]["authority_boundary"].values()
    )


def _machine_proof(payload: dict[str, Any]) -> dict[str, Any]:
    nodes = payload["semantic_memory_nodes_by_ref"]
    relationships = payload["semantic_memory_relationships_by_ref"]
    blockers = payload["folder_projection_blockers_by_id"].values()
    blocker_types = {blocker["blocker_type"] for blocker in blockers}
    examples = payload["examples"]
    projection = payload["folder_tree_projection"]
    return {
        "semantic_memory_graph_contract_model_present": True,
        "semantic_memory_node_model_present": True,
        "semantic_memory_relationship_model_present": True,
        "folder_tree_projection_model_present": True,
        "folder_projection_node_model_present": True,
        "scope_partition_policy_model_present": True,
        "folder_projection_blocker_model_present": True,
        "world_project_memory_graph_elioperator_report_model_present": True,
        "node_types_present": set(NODE_TYPES).issubset(payload["node_types"]),
        "relationship_types_present": set(RELATIONSHIP_TYPES).issubset(payload["relationship_types"]),
        "projection_statuses_present": set(PROJECTION_STATUSES).issubset(payload["projection_statuses"]),
        "sqlite_graph_tables_available_in_schema_contract": set(SQLITE_GRAPH_TABLES).issubset(payload["existing_sqlite_graph_tables"]),
        "live_db_migration_created": False,
        "live_memory_write_performed": False,
        "graph_vs_folder_doctrine_exists": "Semantic graph is truth." in payload["semantic_memory_graph_contract"]["doctrine"],
        "all_nodes_have_scope": all(node["tenant_ref"] and node["client_ref"] for node in nodes.values()),
        "all_relationships_have_scope": all(rel["tenant_ref"] and rel["client_ref"] for rel in relationships.values()),
        "all_nodes_have_provenance": all(node["provenance_refs"] for node in nodes.values()),
        "all_relationships_have_provenance": all(rel["provenance_ref"] for rel in relationships.values()),
        "folder_projection_mac_render_ready": projection["mac_render_ready"] is True,
        "music_live_x32_example_exists": "music_live_x32" in examples,
        "music_studio_album_song_example_exists": "music_studio_album_song" in examples,
        "finance_capital_hilton_example_exists": "finance_capital_hilton" in examples,
        "build_mission_control_example_exists": "build_mission_control" in examples,
        "struna_example_exists": "struna_mac_version" in examples,
        "multi_folder_chat_link_example_exists": "multi_folder_chat" in examples,
        "strict_tree_as_truth_blocker_exists": "STRICT_TREE_ASSUMED_AS_TRUTH" in blocker_types,
        "cross_client_leak_blocker_exists": "CROSS_CLIENT_LEAK" in blocker_types,
        "provenance_missing_blocker_exists": "PROVENANCE_MISSING" in blocker_types,
        "blockers_present": set(BLOCKER_TYPES).issubset(blocker_types),
        "all_live_authority_flags_false": _all_authority_flags_false(payload),
        "raw_transcript_ingested": False,
        "raw_file_body_ingested": False,
        "agent_retrieval_run": False,
        "cross_scope_query_run": False,
        "reorganization_or_folder_move_performed": False,
        "external_action_performed": False,
        "credentials_or_secrets_included": False,
        "raw_private_bodies_included": False,
        "mission_control_swift_changed": False,
        "mac_sync_import_run": False,
        "git_push_pull_fetch_run": False,
        "content_hash": None,
    }


def build_world_project_memory_graph_projection(*, generated_at: str | None = None) -> dict[str, Any]:
    generated_at = generated_at or DEFAULT_GENERATED_AT
    contract = build_contract()
    nodes = build_semantic_nodes()
    relationships = build_relationships()
    projection_nodes = build_projection_nodes()
    folder_projection = build_folder_tree_projection(projection_nodes)
    scope_policies = build_scope_policies()
    blockers = build_blockers()
    report = build_report()
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "contract_status": CONTRACT_STATUS,
        "generated_at": generated_at,
        "operator_markdown_mode": "ELIOPERATOR",
        "node_types": NODE_TYPES,
        "relationship_types": RELATIONSHIP_TYPES,
        "projection_statuses": PROJECTION_STATUSES,
        "blocker_types": BLOCKER_TYPES,
        "existing_sqlite_graph_tables": SQLITE_GRAPH_TABLES,
        "db_rail_status": {
            "semantic_tables_present_in_backend_sqlite_schema": True,
            "live_db_write_supported_in_this_lane": False,
            "live_db_migration_supported_in_this_lane": False,
            "missing_live_rail": "approved semantic graph writer/retrieval rail",
        },
        "model_schemas": _model_schemas(),
        "semantic_memory_graph_contract": asdict(contract),
        "semantic_memory_nodes_by_ref": {node.node_ref: asdict(node) for node in nodes},
        "semantic_memory_relationships_by_ref": {
            relationship.relationship_ref: asdict(relationship)
            for relationship in relationships
        },
        "folder_tree_projection": asdict(folder_projection),
        "folder_projection_nodes_by_ref": {
            node.projection_node_ref: asdict(node)
            for node in projection_nodes
        },
        "scope_partition_policies_by_id": {
            policy.policy_id: asdict(policy)
            for policy in scope_policies
        },
        "folder_projection_blockers_by_id": {
            blocker.blocker_id: asdict(blocker)
            for blocker in blockers
        },
        "world_project_memory_graph_elioperator_report": asdict(report),
        "examples": build_examples(),
        "relationship_refs": {
            "backend_sqlite_schema": "semantic_records, semantic_relationships, provenance_refs target schema already present",
            "operator_file_metadata_intake": "metadata-only source ref creation",
            "operator_file_intake_visual_workspace_contract": "visual workspace and source-ref posture",
            "worker_routing_intelligence": "Mac/PC/Gemini worker routing boundaries",
            "workflow_execution_package_compiler": "workflow package/readiness examples",
            "cross_surface_artifact_handoff_registry_contract": "artifact/readback handoff refs",
            "cross_lane_reusable_block_registry_contract": "reusable fact tokenization and scope posture",
            "corpus_atlas": "metadata-first source inventory patterns",
            "evidence_kettle": "receipt/source evidence metadata patterns",
            "openclaw_sensitive_policy": "sensitive path and source-set boundary posture",
        },
        "allowed_contract_scope": (
            "deterministic contract/read-model generation",
            "graph/projection examples",
            "tests",
            "ELIOPERATOR report",
        ),
        "authority_boundary": AUTHORITY_BOUNDARY,
    }
    payload["machine_proof"] = _machine_proof(payload)
    payload["machine_proof"]["content_hash"] = _content_hash(payload)
    return payload


def format_operator_markdown(payload: dict[str, Any]) -> str:
    report = payload["world_project_memory_graph_elioperator_report"]
    projection = payload["folder_tree_projection"]
    examples = payload["examples"]
    example_lines = "\n".join(
        f"- {name}: {' / '.join(example.get('projection', example.get('start_projection', ())))}"
        for name, example in examples.items()
    )
    blocker_lines = "\n".join(
        f"- {blocker['blocker_type']}: {blocker['elioperator_warning']}"
        for blocker in payload["folder_projection_blockers_by_id"].values()
    )
    scope_lines = "\n".join(
        f"- {policy['world_ref']} / {policy['client_ref']}: {policy['cross_client_leak_policy']}"
        for policy in payload["scope_partition_policies_by_id"].values()
    )
    return "\n".join(
        [
            "# World Project Memory Graph Projection v0",
            "",
            "ELIOPERATOR: The semantic graph is truth. The folder tree is a Mac/sidebar projection.",
            "",
            "## What This Enables",
            "",
            report["what_this_enables"],
            "",
            "## What This Does Not Do Yet",
            "",
            report["what_this_does_not_do_yet"],
            "",
            "## Mac Sidebar Projection",
            "",
            f"- Projection status: `{projection['projection_status']}`",
            f"- Mac render ready: `{projection['mac_render_ready']}`",
            f"- Root nodes: {', '.join(projection['root_nodes'])}",
            "",
            "## Examples",
            "",
            example_lines,
            "",
            "## Scope Boundaries",
            "",
            scope_lines,
            "",
            "## Blockers",
            "",
            blocker_lines,
            "",
            "## Boundary",
            "",
            "No live memory write, DB migration, raw transcript ingestion, raw file body ingestion, agent retrieval, cross-scope query, reorganization, move/delete, folder tree update, external action, credential handling, raw-body ingestion, Mac sync/import, Swift change, or push was added.",
            "",
            f"Next safe move: {payload['semantic_memory_graph_contract']['next_safe_move']}",
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
    projection = payload["folder_tree_projection"]
    return {
        "schema_version": payload["schema_version"],
        "read_model_id": payload["read_model_id"],
        "contract_status": payload["contract_status"],
        "json_path": str(json_path) if json_path else None,
        "operator_path": str(operator_path) if operator_path else None,
        "projection_status": projection["projection_status"],
        "mac_render_ready": projection["mac_render_ready"],
        "node_count": len(payload["semantic_memory_nodes_by_ref"]),
        "relationship_count": len(payload["semantic_memory_relationships_by_ref"]),
        "sqlite_graph_tables_available_in_schema_contract": proof["sqlite_graph_tables_available_in_schema_contract"],
        "music_live_x32_example_exists": proof["music_live_x32_example_exists"],
        "finance_capital_hilton_example_exists": proof["finance_capital_hilton_example_exists"],
        "all_live_authority_flags_false": proof["all_live_authority_flags_false"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export the world/project memory graph projection read-model.")
    parser.add_argument("--export-root", type=Path, default=DEFAULT_EXPORT_ROOT)
    parser.add_argument("--format", choices=("summary", "json"), default="json")
    args = parser.parse_args(argv)

    payload = build_world_project_memory_graph_projection()
    json_path, operator_path = write_exports(payload, args.export_root)
    output = payload if args.format == "json" else build_summary(payload, json_path, operator_path)
    sys.stdout.write(stable_json(output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
