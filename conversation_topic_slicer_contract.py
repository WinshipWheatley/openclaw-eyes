"""Conversation Topic Slicer Contract v0.

This deterministic read-model defines non-destructive topic slices for chat
threads that drift across worlds and folders. It does not perform live topic
slicing, ingest or copy raw transcripts, write graph links, reorganize folders,
split threads, delete anything, run retrieval, call models, access external
systems, mutate Mission Control Swift, run Mac sync/import, or push.
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

SCHEMA_VERSION = "conversation_topic_slicer_contract_v0"
READ_MODEL_ID = "conversation_topic_slicer_contract"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
OPERATOR_EXPORT_NAME = f"{READ_MODEL_ID}_OPERATOR.md"
CONTRACT_STATUS = "DETERMINISTIC_NON_DESTRUCTIVE_CONVERSATION_TOPIC_SLICER_CONTRACT"

SUGGESTED_ACTIONS = (
    "KEEP_IN_PLACE",
    "LINK_TO_FOLDER",
    "COPY_SUMMARY_TO_FOLDER",
    "MOVE_SLICE_TO_FOLDER",
    "SPLIT_INTO_NEW_THREAD",
    "CREATE_NEW_FOLDER",
    "NEEDS_OPERATOR_REVIEW",
    "UNKNOWN_FAIL_CLOSED",
)

GRAPH_LINK_RELATIONSHIP_TYPES = (
    "RELATED_TO",
    "BELONGS_TO_SCOPE",
    "SUPPORTS_PROCEDURE",
    "SUPPORTS_ARTIFACT",
    "SUPPORTS_PROOF",
    "SUGGESTED_FOLDER_LINK",
    "UNKNOWN",
)

DISRUPTION_LEVELS = (
    "SILENT_LOW_RISK_LINK_CANDIDATE",
    "NON_DISRUPTIVE_SUGGESTION",
    "REVIEW_REQUIRED_MOVE",
    "REVIEW_REQUIRED_SPLIT",
    "BLOCKED_DESTRUCTIVE",
)

RECEIPT_ACTIONS = (
    "SLICE_LINK_PROPOSED",
    "LINK_CREATED",
    "SUMMARY_COPIED",
    "SLICE_MOVED",
    "THREAD_SPLIT",
    "NEW_FOLDER_SUGGESTED",
    "PROPOSAL_REJECTED",
    "PROPOSAL_PARKED",
)

BLOCKER_TYPES = (
    "RAW_TRANSCRIPT_COPIED",
    "RAW_TRANSCRIPT_EXPOSED",
    "SOURCE_PROVENANCE_MISSING",
    "CROSS_CLIENT_LEAK",
    "CROSS_TENANT_LEAK",
    "SILENT_DESTRUCTIVE_REORGANIZATION",
    "AUTO_MOVE_TOO_DISRUPTIVE",
    "MESSAGE_POINTER_MISSING",
    "UNKNOWN_FOLDER",
    "AMBIGUOUS_TOPIC",
    "UNKNOWN_FAIL_CLOSED",
)

AUTHORITY_BOUNDARY = {
    "live_topic_slicing_allowed": False,
    "live_raw_transcript_ingestion_allowed": False,
    "live_raw_transcript_copy_allowed": False,
    "live_graph_link_write_allowed": False,
    "live_reorganization_allowed": False,
    "live_folder_move_allowed": False,
    "live_thread_split_allowed": False,
    "live_delete_allowed": False,
    "live_agent_retrieval_allowed": False,
    "live_cross_scope_query_allowed": False,
    "live_external_action_allowed": False,
    "credential_handling_allowed": False,
    "raw_body_ingestion_allowed": False,
    "network_allowed": False,
    "mission_control_swift_change_allowed": False,
    "mac_sync_import_allowed": False,
    "git_push_pull_fetch_allowed": False,
}


@dataclass(frozen=True)
class ConversationTopicSlicerContract:
    contract_id: str
    doctrine: tuple[str, ...]
    source_thread_policy: tuple[str, ...]
    topic_slice_policy: tuple[str, ...]
    message_pointer_policy: tuple[str, ...]
    graph_link_policy: tuple[str, ...]
    folder_projection_policy: tuple[str, ...]
    reorganization_proposal_policy: tuple[str, ...]
    provenance_policy: tuple[str, ...]
    privacy_boundary: tuple[str, ...]
    authority_boundary: dict[str, bool]
    next_safe_move: str


@dataclass(frozen=True)
class SourceChatThreadRef:
    thread_ref: str
    initial_world_ref: str
    initial_folder_ref: str
    current_primary_world_ref: str
    current_primary_folder_ref: str
    thread_title: str
    safe_summary: str
    message_count_policy: str
    raw_transcript_available_policy: str
    raw_transcript_allowed_in_read_model: bool
    topic_slice_refs: tuple[str, ...]
    source_refs: tuple[str, ...]
    artifact_refs: tuple[str, ...]
    receipt_refs: tuple[str, ...]
    privacy_class: str
    sensitivity_class: str
    next_safe_move: str


@dataclass(frozen=True)
class TopicSlice:
    topic_slice_ref: str
    source_thread_ref: str
    inferred_topic: str
    slice_summary: str
    message_range_policy: str
    message_start_ref: str
    message_end_ref: str
    world_ref: str
    folder_ref: str
    candidate_graph_node_refs: tuple[str, ...]
    candidate_relationship_refs: tuple[str, ...]
    relevant_source_refs: tuple[str, ...]
    relevant_artifact_refs: tuple[str, ...]
    relevant_procedure_refs: tuple[str, ...]
    confidence: str
    operator_review_required: bool
    suggested_action: str
    next_safe_move: str


@dataclass(frozen=True)
class TopicSliceGraphLink:
    link_ref: str
    topic_slice_ref: str
    source_thread_ref: str
    target_node_ref: str
    target_world_ref: str
    target_folder_ref: str
    relationship_type: str
    confidence: str
    operator_review_required: bool
    provenance_ref: str
    privacy_class: str
    next_safe_move: str


@dataclass(frozen=True)
class TopicSliceReorganizationProposal:
    proposal_id: str
    source_thread_ref: str
    topic_slice_refs: tuple[str, ...]
    proposed_links: tuple[str, ...]
    proposed_moves: tuple[str, ...]
    proposed_new_folders: tuple[str, ...]
    proposed_thread_splits: tuple[str, ...]
    reason: str
    confidence: str
    disruption_level: str
    operator_review_required: bool
    provenance_preserved: bool
    deletion_allowed: bool
    approval_status: str
    next_safe_move: str


@dataclass(frozen=True)
class TopicSliceReceipt:
    receipt_id: str
    proposal_ref: str
    action: str
    affected_thread_ref: str
    affected_topic_slice_refs: tuple[str, ...]
    source_folder_refs: tuple[str, ...]
    target_folder_refs: tuple[str, ...]
    provenance_preserved: bool
    raw_body_moved: bool
    raw_body_copied: bool
    operator_approved: bool
    created_at_policy: str
    next_safe_move: str


@dataclass(frozen=True)
class TopicSliceBlocker:
    blocker_id: str
    blocker_type: str
    condition: str
    severity: str
    elioperator_warning: str
    fail_closed: bool
    next_safe_move: str


@dataclass(frozen=True)
class ConversationTopicSlicerElioperatorReport:
    report_id: str
    plain_summary: str
    what_this_enables: str
    what_this_does_not_do_yet: str
    how_topic_slices_work: str
    how_provenance_is_preserved: str
    how_reorganization_suggestions_work: str
    how_graph_links_work: str
    next_safe_move: str


REQUIRED_CONTRACT_FIELDS = tuple(ConversationTopicSlicerContract.__dataclass_fields__.keys())
REQUIRED_THREAD_FIELDS = tuple(SourceChatThreadRef.__dataclass_fields__.keys())
REQUIRED_TOPIC_SLICE_FIELDS = tuple(TopicSlice.__dataclass_fields__.keys())
REQUIRED_GRAPH_LINK_FIELDS = tuple(TopicSliceGraphLink.__dataclass_fields__.keys())
REQUIRED_PROPOSAL_FIELDS = tuple(TopicSliceReorganizationProposal.__dataclass_fields__.keys())
REQUIRED_RECEIPT_FIELDS = tuple(TopicSliceReceipt.__dataclass_fields__.keys())
REQUIRED_BLOCKER_FIELDS = tuple(TopicSliceBlocker.__dataclass_fields__.keys())
REQUIRED_REPORT_FIELDS = tuple(ConversationTopicSlicerElioperatorReport.__dataclass_fields__.keys())


def stable_json(data: Any) -> str:
    return json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _content_hash(payload: dict[str, Any]) -> str:
    clean = json.loads(stable_json(payload))
    clean.get("machine_proof", {}).pop("content_hash", None)
    return hashlib.sha256(stable_json(clean).encode("utf-8")).hexdigest()


def _model_schemas() -> dict[str, Any]:
    return {
        "conversation_topic_slicer_contract": {"required_fields": list(REQUIRED_CONTRACT_FIELDS)},
        "source_chat_thread_ref": {"required_fields": list(REQUIRED_THREAD_FIELDS)},
        "topic_slice": {"required_fields": list(REQUIRED_TOPIC_SLICE_FIELDS)},
        "topic_slice_graph_link": {"required_fields": list(REQUIRED_GRAPH_LINK_FIELDS)},
        "topic_slice_reorganization_proposal": {"required_fields": list(REQUIRED_PROPOSAL_FIELDS)},
        "topic_slice_receipt": {"required_fields": list(REQUIRED_RECEIPT_FIELDS)},
        "topic_slice_blocker": {"required_fields": list(REQUIRED_BLOCKER_FIELDS)},
        "conversation_topic_slicer_elioperator_report": {"required_fields": list(REQUIRED_REPORT_FIELDS)},
    }


def build_contract() -> ConversationTopicSlicerContract:
    return ConversationTopicSlicerContract(
        contract_id="conversation_topic_slicer_contract_v0",
        doctrine=(
            "Original chat thread remains intact.",
            "Topic slices are pointer/index records, not copied raw transcript bodies.",
            "Topic slices can link one chat to multiple worlds and folders.",
            "Reorganization proposals are suggestions, not silent truth.",
            "Operator review is required for disruptive move or split actions.",
            "Agents receive scoped topic/context packages later, not whole raw threads.",
        ),
        source_thread_policy=(
            "Thread refs keep the original world/folder context and current primary projection.",
            "Thread summaries are safe display summaries.",
            "Raw transcript text is not allowed in normal read-models.",
            "Message ranges may be referenced by pointer only.",
        ),
        topic_slice_policy=(
            "Slices describe a bounded topic with message pointer range, candidate graph targets, and safe summary.",
            "Slices do not claim final truth.",
            "Slices do not move, delete, truncate, or rewrite the source thread.",
            "Cross-world links can be proposed when provenance and scope are preserved.",
        ),
        message_pointer_policy=(
            "Use stable pointer-like message refs such as msg_0001.",
            "Store start/end refs and range policy, not raw message bodies.",
            "Missing message pointers fail closed.",
        ),
        graph_link_policy=(
            "Graph links point to semantic nodes and folder projections from the memory graph read-model.",
            "Low-risk links can be candidates for future auto-application only when no privacy or cross-client risk exists.",
            "Cross-client or cross-tenant linking fails closed unless explicitly allowed.",
        ),
        folder_projection_policy=(
            "Folder links are projections and aliases, not memory truth.",
            "A topic may appear in multiple projected folders through links.",
            "Folder mutation is not allowed in v0.",
        ),
        reorganization_proposal_policy=(
            "Non-disruptive link suggestions can be parked or shown to the operator.",
            "Move and split proposals require operator review.",
            "Destructive delete is never allowed in v0.",
            "Ignored suggestions may fade into chat history without blocking work.",
        ),
        provenance_policy=(
            "Every slice must preserve source thread and message range provenance.",
            "Every graph link carries a provenance ref.",
            "Every proposal records whether provenance is preserved.",
        ),
        privacy_boundary=(
            "No raw transcript in normal read-models.",
            "No private raw body copied into topic slices.",
            "Protected/legal/private details remain summary or reference only.",
            "Cross-client leakage fails closed.",
        ),
        authority_boundary=AUTHORITY_BOUNDARY,
        next_safe_move="Export non-destructive topic slice examples and wait for a future approved slicer/runtime before writing links.",
    )


def _thread(
    thread_ref: str,
    initial_world_ref: str,
    initial_folder_ref: str,
    title: str,
    safe_summary: str,
    topic_slice_refs: tuple[str, ...],
    *,
    current_primary_world_ref: str | None = None,
    current_primary_folder_ref: str | None = None,
    source_refs: tuple[str, ...] = (),
    artifact_refs: tuple[str, ...] = (),
    receipt_refs: tuple[str, ...] = (),
    privacy_class: str = "internal",
    sensitivity_class: str = "metadata_only",
) -> SourceChatThreadRef:
    return SourceChatThreadRef(
        thread_ref=thread_ref,
        initial_world_ref=initial_world_ref,
        initial_folder_ref=initial_folder_ref,
        current_primary_world_ref=current_primary_world_ref or initial_world_ref,
        current_primary_folder_ref=current_primary_folder_ref or initial_folder_ref,
        thread_title=title,
        safe_summary=safe_summary,
        message_count_policy="count may be stored as metadata; raw messages remain outside normal read-model",
        raw_transcript_available_policy="future gated source only; not copied here",
        raw_transcript_allowed_in_read_model=False,
        topic_slice_refs=topic_slice_refs,
        source_refs=source_refs,
        artifact_refs=artifact_refs,
        receipt_refs=receipt_refs,
        privacy_class=privacy_class,
        sensitivity_class=sensitivity_class,
        next_safe_move="Keep original thread intact and show topic links as non-destructive pointers.",
    )


def _slice(
    topic_slice_ref: str,
    source_thread_ref: str,
    inferred_topic: str,
    slice_summary: str,
    message_start_ref: str,
    message_end_ref: str,
    world_ref: str,
    folder_ref: str,
    *,
    candidate_graph_node_refs: tuple[str, ...],
    candidate_relationship_refs: tuple[str, ...] = (),
    relevant_source_refs: tuple[str, ...] = (),
    relevant_artifact_refs: tuple[str, ...] = (),
    relevant_procedure_refs: tuple[str, ...] = (),
    confidence: str = "MEDIUM",
    operator_review_required: bool = False,
    suggested_action: str = "LINK_TO_FOLDER",
) -> TopicSlice:
    return TopicSlice(
        topic_slice_ref=topic_slice_ref,
        source_thread_ref=source_thread_ref,
        inferred_topic=inferred_topic,
        slice_summary=slice_summary,
        message_range_policy="pointer_range_only_no_raw_body",
        message_start_ref=message_start_ref,
        message_end_ref=message_end_ref,
        world_ref=world_ref,
        folder_ref=folder_ref,
        candidate_graph_node_refs=candidate_graph_node_refs,
        candidate_relationship_refs=candidate_relationship_refs,
        relevant_source_refs=relevant_source_refs,
        relevant_artifact_refs=relevant_artifact_refs,
        relevant_procedure_refs=relevant_procedure_refs,
        confidence=confidence,
        operator_review_required=operator_review_required,
        suggested_action=suggested_action,
        next_safe_move="Use this as a proposed graph/folder link; do not copy transcript body or move the source thread.",
    )


def build_source_threads() -> tuple[SourceChatThreadRef, ...]:
    return (
        _thread(
            "thread_ref_music_live_multitopic_setlist",
            "music",
            "music/live_music",
            "Live music thread with setlists, X32, songwriting, and bookings",
            "Chat starts with setlist ideas, then branches into X32 routing, a song arrangement, and booking follow-up.",
            (
                "topic_slice_setlist_ideas",
                "topic_slice_x32_routing_issue",
                "topic_slice_new_song_arrangement",
                "topic_slice_booking_followup",
            ),
            source_refs=("source_ref_setlist_chat_summary",),
            receipt_refs=("receipt_multifolder_topic_candidates",),
        ),
        _thread(
            "thread_ref_finance_misfiled_invoice_architecture",
            "finance",
            "finance/capital_hilton",
            "Capital Hilton invoice thread with architecture drift",
            "Chat begins with Capital Hilton invoice context, then turns into general invoice automation architecture.",
            ("topic_slice_capital_hilton_invoice_specific", "topic_slice_invoice_automation_architecture"),
            current_primary_folder_ref="finance/capital_hilton/invoices",
            source_refs=("source_ref_capital_hilton_invoice_preview",),
            receipt_refs=("receipt_router_readback_capital_hilton",),
            privacy_class="finance_boundary",
        ),
        _thread(
            "thread_ref_x32_fader_replacement",
            "music",
            "music/live_music/x32",
            "X32 fader replacement follow-up",
            "Operator asks to resume an X32 fader replacement thread; this contract models candidate links only.",
            ("topic_slice_x32_fader_replacement",),
            source_refs=("source_ref_x32_maintenance_summary",),
        ),
        _thread(
            "thread_ref_struna_creative_build_licensing",
            "music",
            "music/studio",
            "Struna creative chat with build and licensing drift",
            "Creative/music discussion also touches Mac app build posture and licensing summaries.",
            ("topic_slice_struna_creative", "topic_slice_struna_mac_build", "topic_slice_struna_licensing_summary"),
            source_refs=("source_ref_struna_app_files",),
            receipt_refs=("receipt_struna_ownership_context_summary", "receipt_struna_licensing_use_note"),
            privacy_class="private_summary_only",
            sensitivity_class="private_summary_only",
        ),
    )


def build_topic_slices() -> tuple[TopicSlice, ...]:
    return (
        _slice(
            "topic_slice_setlist_ideas",
            "thread_ref_music_live_multitopic_setlist",
            "setlist ideas",
            "Setlist ideas belong with the original live music context.",
            "msg_0001",
            "msg_0008",
            "music",
            "music/live_music/setlists",
            candidate_graph_node_refs=("node_multifolder_chat_setlists",),
            confidence="HIGH",
            suggested_action="KEEP_IN_PLACE",
        ),
        _slice(
            "topic_slice_x32_routing_issue",
            "thread_ref_music_live_multitopic_setlist",
            "X32 routing issue",
            "Routing troubleshooting should link to the X32 routing projection without moving the original chat.",
            "msg_0009",
            "msg_0018",
            "music",
            "music/live_music/x32/routing",
            candidate_graph_node_refs=("node_music_x32_routing",),
            candidate_relationship_refs=("rel_multifolder_chat_links_x32",),
            relevant_source_refs=("source_ref_behringer_x32_notes",),
            confidence="HIGH",
            suggested_action="LINK_TO_FOLDER",
        ),
        _slice(
            "topic_slice_new_song_arrangement",
            "thread_ref_music_live_multitopic_setlist",
            "new song arrangement",
            "Song arrangement material should link into studio songwriting or the album song area.",
            "msg_0019",
            "msg_0029",
            "music",
            "music/studio/album/songwriting",
            candidate_graph_node_refs=("node_music_song",),
            candidate_relationship_refs=("rel_multifolder_chat_links_song",),
            relevant_source_refs=("source_ref_song_rich_text_doc",),
            confidence="MEDIUM",
            operator_review_required=True,
            suggested_action="LINK_TO_FOLDER",
        ),
        _slice(
            "topic_slice_booking_followup",
            "thread_ref_music_live_multitopic_setlist",
            "booking and client follow-up",
            "Booking follow-up is a cross-world candidate for communications or operations.",
            "msg_0030",
            "msg_0038",
            "communications",
            "communications/bookings",
            candidate_graph_node_refs=("topic_booking_followup",),
            candidate_relationship_refs=("rel_multifolder_chat_links_booking_followup",),
            confidence="LOW",
            operator_review_required=True,
            suggested_action="NEEDS_OPERATOR_REVIEW",
        ),
        _slice(
            "topic_slice_capital_hilton_invoice_specific",
            "thread_ref_finance_misfiled_invoice_architecture",
            "Capital Hilton invoice details",
            "Capital Hilton-specific invoice facts remain scoped to the Finance Capital Hilton invoice folder.",
            "msg_0001",
            "msg_0011",
            "finance",
            "finance/capital_hilton/invoices",
            candidate_graph_node_refs=("node_finance_capital_hilton_invoices",),
            relevant_source_refs=("source_ref_capital_hilton_invoice_preview",),
            relevant_procedure_refs=("procedure_ref_capital_hilton_invoice_workflow",),
            confidence="HIGH",
            suggested_action="KEEP_IN_PLACE",
        ),
        _slice(
            "topic_slice_invoice_automation_architecture",
            "thread_ref_finance_misfiled_invoice_architecture",
            "general invoice automation architecture",
            "Architecture notes should link to OpenClaw build work rather than be trapped under one client.",
            "msg_0012",
            "msg_0027",
            "build",
            "build/openclaw/invoice_workflows",
            candidate_graph_node_refs=("node_build_mission_control_chat_surface",),
            relevant_procedure_refs=("workflow_execution_package_compiler", "conversational_workflow_router_contract"),
            confidence="MEDIUM",
            operator_review_required=True,
            suggested_action="LINK_TO_FOLDER",
        ),
        _slice(
            "topic_slice_x32_fader_replacement",
            "thread_ref_x32_fader_replacement",
            "X32 fader replacement",
            "Candidate maintenance topic for future resume/retrieval flow; this contract only models the pointer/link.",
            "msg_0001",
            "msg_0006",
            "music",
            "music/live_music/x32/maintenance",
            candidate_graph_node_refs=("node_music_live_x32", "node_music_x32_routing"),
            relevant_source_refs=("source_ref_x32_maintenance_summary",),
            confidence="MEDIUM",
            operator_review_required=True,
            suggested_action="LINK_TO_FOLDER",
        ),
        _slice(
            "topic_slice_struna_creative",
            "thread_ref_struna_creative_build_licensing",
            "Struna creative/music direction",
            "Creative Struna discussion can remain in music as a safe summary slice.",
            "msg_0001",
            "msg_0010",
            "music",
            "music/studio/struna",
            candidate_graph_node_refs=("node_world_music",),
            confidence="MEDIUM",
            suggested_action="LINK_TO_FOLDER",
        ),
        _slice(
            "topic_slice_struna_mac_build",
            "thread_ref_struna_creative_build_licensing",
            "Struna Mac app build",
            "Mac app build material should link to the Struna Mac Version build projection.",
            "msg_0011",
            "msg_0021",
            "build",
            "build/struna/mac_version",
            candidate_graph_node_refs=("node_struna_mac_version",),
            candidate_relationship_refs=("rel_build_links_struna",),
            relevant_source_refs=("source_ref_struna_app_files",),
            confidence="HIGH",
            operator_review_required=True,
            suggested_action="LINK_TO_FOLDER",
        ),
        _slice(
            "topic_slice_struna_licensing_summary",
            "thread_ref_struna_creative_build_licensing",
            "Struna licensing summary",
            "Licensing material is summary-only and requires review before cross-world linking.",
            "msg_0022",
            "msg_0032",
            "build",
            "build/struna/licensing",
            candidate_graph_node_refs=("node_struna_mac_version",),
            relevant_source_refs=("source_ref_struna_app_files",),
            confidence="MEDIUM",
            operator_review_required=True,
            suggested_action="NEEDS_OPERATOR_REVIEW",
        ),
    )


def _link(
    link_ref: str,
    topic_slice_ref: str,
    source_thread_ref: str,
    target_node_ref: str,
    target_world_ref: str,
    target_folder_ref: str,
    relationship_type: str,
    *,
    confidence: str = "MEDIUM",
    operator_review_required: bool = False,
    privacy_class: str = "internal",
) -> TopicSliceGraphLink:
    return TopicSliceGraphLink(
        link_ref=link_ref,
        topic_slice_ref=topic_slice_ref,
        source_thread_ref=source_thread_ref,
        target_node_ref=target_node_ref,
        target_world_ref=target_world_ref,
        target_folder_ref=target_folder_ref,
        relationship_type=relationship_type,
        confidence=confidence,
        operator_review_required=operator_review_required,
        provenance_ref=f"prov_{link_ref}",
        privacy_class=privacy_class,
        next_safe_move="Keep this as a proposed semantic/folder link until a future approved graph writer exists.",
    )


def build_graph_links() -> tuple[TopicSliceGraphLink, ...]:
    return (
        _link("topic_link_setlist_to_live_music", "topic_slice_setlist_ideas", "thread_ref_music_live_multitopic_setlist", "node_multifolder_chat_setlists", "music", "music/live_music/setlists", "BELONGS_TO_SCOPE", confidence="HIGH"),
        _link("topic_link_x32_to_routing", "topic_slice_x32_routing_issue", "thread_ref_music_live_multitopic_setlist", "node_music_x32_routing", "music", "music/live_music/x32/routing", "RELATED_TO", confidence="HIGH"),
        _link("topic_link_song_to_album", "topic_slice_new_song_arrangement", "thread_ref_music_live_multitopic_setlist", "node_music_song", "music", "music/studio/album/songwriting", "SUGGESTED_FOLDER_LINK", operator_review_required=True),
        _link("topic_link_booking_to_comms", "topic_slice_booking_followup", "thread_ref_music_live_multitopic_setlist", "topic_booking_followup", "communications", "communications/bookings", "SUGGESTED_FOLDER_LINK", confidence="LOW", operator_review_required=True),
        _link("topic_link_capital_hilton_invoice", "topic_slice_capital_hilton_invoice_specific", "thread_ref_finance_misfiled_invoice_architecture", "node_finance_capital_hilton_invoices", "finance", "finance/capital_hilton/invoices", "BELONGS_TO_SCOPE", confidence="HIGH", privacy_class="finance_boundary"),
        _link("topic_link_invoice_architecture_build", "topic_slice_invoice_automation_architecture", "thread_ref_finance_misfiled_invoice_architecture", "node_build_mission_control_chat_surface", "build", "build/openclaw/invoice_workflows", "RELATED_TO", operator_review_required=True),
        _link("topic_link_x32_fader_maintenance", "topic_slice_x32_fader_replacement", "thread_ref_x32_fader_replacement", "node_music_live_x32", "music", "music/live_music/x32/maintenance", "SUGGESTED_FOLDER_LINK", operator_review_required=True),
        _link("topic_link_struna_creative_music", "topic_slice_struna_creative", "thread_ref_struna_creative_build_licensing", "node_world_music", "music", "music/studio/struna", "RELATED_TO", operator_review_required=True, privacy_class="private_summary_only"),
        _link("topic_link_struna_build", "topic_slice_struna_mac_build", "thread_ref_struna_creative_build_licensing", "node_struna_mac_version", "build", "build/struna/mac_version", "RELATED_TO", confidence="HIGH", operator_review_required=True, privacy_class="private_summary_only"),
        _link("topic_link_struna_licensing", "topic_slice_struna_licensing_summary", "thread_ref_struna_creative_build_licensing", "node_struna_mac_version", "build", "build/struna/licensing", "SUGGESTED_FOLDER_LINK", operator_review_required=True, privacy_class="private_summary_only"),
    )


def _proposal(
    proposal_id: str,
    source_thread_ref: str,
    topic_slice_refs: tuple[str, ...],
    proposed_links: tuple[str, ...],
    reason: str,
    *,
    proposed_moves: tuple[str, ...] = (),
    proposed_new_folders: tuple[str, ...] = (),
    proposed_thread_splits: tuple[str, ...] = (),
    confidence: str = "MEDIUM",
    disruption_level: str = "NON_DISRUPTIVE_SUGGESTION",
    operator_review_required: bool = True,
    approval_status: str = "NOT_REQUESTED",
) -> TopicSliceReorganizationProposal:
    return TopicSliceReorganizationProposal(
        proposal_id=proposal_id,
        source_thread_ref=source_thread_ref,
        topic_slice_refs=topic_slice_refs,
        proposed_links=proposed_links,
        proposed_moves=proposed_moves,
        proposed_new_folders=proposed_new_folders,
        proposed_thread_splits=proposed_thread_splits,
        reason=reason,
        confidence=confidence,
        disruption_level=disruption_level,
        operator_review_required=operator_review_required,
        provenance_preserved=True,
        deletion_allowed=False,
        approval_status=approval_status,
        next_safe_move="Show as a suggestion; do not mutate folders, split threads, or delete anything from this contract.",
    )


def build_reorganization_proposals() -> tuple[TopicSliceReorganizationProposal, ...]:
    return (
        _proposal(
            "proposal_multitopic_live_music_links",
            "thread_ref_music_live_multitopic_setlist",
            ("topic_slice_x32_routing_issue", "topic_slice_new_song_arrangement", "topic_slice_booking_followup"),
            ("topic_link_x32_to_routing", "topic_link_song_to_album", "topic_link_booking_to_comms"),
            "One live music thread drifted into X32, songwriting, and booking topics; preserve original thread and add graph links.",
            proposed_new_folders=("communications/bookings",),
            confidence="MEDIUM",
            disruption_level="NON_DISRUPTIVE_SUGGESTION",
        ),
        _proposal(
            "proposal_misfiled_invoice_architecture_link",
            "thread_ref_finance_misfiled_invoice_architecture",
            ("topic_slice_capital_hilton_invoice_specific", "topic_slice_invoice_automation_architecture"),
            ("topic_link_capital_hilton_invoice", "topic_link_invoice_architecture_build"),
            "Capital Hilton slice stays in Finance while general architecture links to Build.",
            confidence="MEDIUM",
            disruption_level="NON_DISRUPTIVE_SUGGESTION",
        ),
        _proposal(
            "proposal_x32_fader_resume_candidate",
            "thread_ref_x32_fader_replacement",
            ("topic_slice_x32_fader_replacement",),
            ("topic_link_x32_fader_maintenance",),
            "Future resume flow can look up this maintenance slice, but no retrieval runs here.",
            proposed_new_folders=("music/live_music/x32/maintenance",),
            confidence="MEDIUM",
            disruption_level="NON_DISRUPTIVE_SUGGESTION",
        ),
        _proposal(
            "proposal_struna_cross_world_review",
            "thread_ref_struna_creative_build_licensing",
            ("topic_slice_struna_creative", "topic_slice_struna_mac_build", "topic_slice_struna_licensing_summary"),
            ("topic_link_struna_creative_music", "topic_link_struna_build", "topic_link_struna_licensing"),
            "Struna creative, build, and licensing summaries cross worlds and require review.",
            proposed_new_folders=("music/studio/struna", "build/struna/licensing"),
            confidence="MEDIUM",
            disruption_level="REVIEW_REQUIRED_MOVE",
            operator_review_required=True,
        ),
    )


def build_receipts() -> tuple[TopicSliceReceipt, ...]:
    return (
        TopicSliceReceipt(
            receipt_id="receipt_multitopic_link_proposed",
            proposal_ref="proposal_multitopic_live_music_links",
            action="SLICE_LINK_PROPOSED",
            affected_thread_ref="thread_ref_music_live_multitopic_setlist",
            affected_topic_slice_refs=("topic_slice_x32_routing_issue", "topic_slice_new_song_arrangement", "topic_slice_booking_followup"),
            source_folder_refs=("music/live_music",),
            target_folder_refs=("music/live_music/x32/routing", "music/studio/album/songwriting", "communications/bookings"),
            provenance_preserved=True,
            raw_body_moved=False,
            raw_body_copied=False,
            operator_approved=False,
            created_at_policy="deterministic_contract_example_no_clock_truth",
            next_safe_move="Show proposal and wait for a future approved link writer.",
        ),
        TopicSliceReceipt(
            receipt_id="receipt_misfiled_invoice_proposal_parked",
            proposal_ref="proposal_misfiled_invoice_architecture_link",
            action="PROPOSAL_PARKED",
            affected_thread_ref="thread_ref_finance_misfiled_invoice_architecture",
            affected_topic_slice_refs=("topic_slice_invoice_automation_architecture",),
            source_folder_refs=("finance/capital_hilton/invoices",),
            target_folder_refs=("build/openclaw/invoice_workflows",),
            provenance_preserved=True,
            raw_body_moved=False,
            raw_body_copied=False,
            operator_approved=False,
            created_at_policy="deterministic_contract_example_no_clock_truth",
            next_safe_move="Keep original finance thread intact and expose build link as a suggestion.",
        ),
        TopicSliceReceipt(
            receipt_id="receipt_struna_cross_world_review_required",
            proposal_ref="proposal_struna_cross_world_review",
            action="NEW_FOLDER_SUGGESTED",
            affected_thread_ref="thread_ref_struna_creative_build_licensing",
            affected_topic_slice_refs=("topic_slice_struna_mac_build", "topic_slice_struna_licensing_summary"),
            source_folder_refs=("music/studio",),
            target_folder_refs=("build/struna/mac_version", "build/struna/licensing"),
            provenance_preserved=True,
            raw_body_moved=False,
            raw_body_copied=False,
            operator_approved=False,
            created_at_policy="deterministic_contract_example_no_clock_truth",
            next_safe_move="Require operator review before any future cross-world promotion.",
        ),
    )


def build_blockers() -> tuple[TopicSliceBlocker, ...]:
    details = {
        "RAW_TRANSCRIPT_COPIED": ("A full raw transcript is copied into a topic slice or generated read-model.", "Block the copy and store pointer ranges plus safe summaries only."),
        "RAW_TRANSCRIPT_EXPOSED": ("Raw transcript text is exposed to normal operator cards or model context.", "Use safe summaries and source refs; keep raw bodies gated."),
        "SOURCE_PROVENANCE_MISSING": ("A slice lacks source thread or message range provenance.", "Fail closed until pointer refs exist."),
        "CROSS_CLIENT_LEAK": ("A slice links client-private facts into another client scope.", "Block cross-client link unless explicit reviewed permission exists."),
        "CROSS_TENANT_LEAK": ("A slice crosses tenant boundary.", "Block cross-tenant link."),
        "SILENT_DESTRUCTIVE_REORGANIZATION": ("A proposal deletes, truncates, rewrites, or silently moves chat material.", "Do not reorganize destructively; show a reviewable proposal."),
        "AUTO_MOVE_TOO_DISRUPTIVE": ("A move or split is attempted without operator review.", "Move and split actions require operator approval."),
        "MESSAGE_POINTER_MISSING": ("A topic slice lacks start/end message refs.", "Do not create the slice until pointer range is available."),
        "UNKNOWN_FOLDER": ("A target folder cannot be resolved in the projection.", "Ask for a folder choice or create a reviewable folder suggestion."),
        "AMBIGUOUS_TOPIC": ("The topic cannot be safely framed.", "Ask a clarifying question before linking."),
        "UNKNOWN_FAIL_CLOSED": ("The slicer cannot classify the slice/proposal safely.", "Fail closed and preserve the original thread."),
    }
    blockers = []
    for blocker_type, (condition, warning) in details.items():
        blockers.append(
            TopicSliceBlocker(
                blocker_id=f"topic_slice_blocker_{blocker_type.lower()}",
                blocker_type=blocker_type,
                condition=condition,
                severity="CRITICAL" if blocker_type in {"CROSS_CLIENT_LEAK", "CROSS_TENANT_LEAK", "UNKNOWN_FAIL_CLOSED"} else "HIGH",
                elioperator_warning=warning,
                fail_closed=True,
                next_safe_move="Keep the original thread intact and return an operator-readable blocker.",
            )
        )
    return tuple(blockers)


def build_report() -> ConversationTopicSlicerElioperatorReport:
    return ConversationTopicSlicerElioperatorReport(
        report_id="conversation_topic_slicer_elioperator_report_v0",
        plain_summary="OpenClaw can model topic slices from a drifting chat without moving or copying the original conversation.",
        what_this_enables="One chat can point into several worlds/folders through safe topic slices and graph links.",
        what_this_does_not_do_yet="It does not run live slicing, ingest transcripts, write graph links, move folders, split threads, retrieve agents, or execute external actions.",
        how_topic_slices_work="A slice stores inferred topic, safe summary, source thread ref, message pointer range, and candidate graph/folder targets.",
        how_provenance_is_preserved="Every slice keeps source thread plus start/end message refs; every graph link carries a provenance ref.",
        how_reorganization_suggestions_work="Links can be suggested; moves and splits require operator review; delete is not allowed.",
        how_graph_links_work="Slice links target semantic graph nodes and projected folders while preserving scope and privacy boundaries.",
        next_safe_move="Use this contract as the shape for future topic slicer output; do not write links until an approved rail exists.",
    )


def build_examples() -> dict[str, Any]:
    return {
        "one_chat_three_topics": {
            "initial_folder": "music/live_music",
            "topics": ("setlist ideas", "X32 routing issue", "new song arrangement", "booking and client follow-up"),
            "expected_target_folders": (
                "music/live_music/setlists",
                "music/live_music/x32/routing",
                "music/studio/album/songwriting",
                "communications/bookings",
            ),
            "thread_ref": "thread_ref_music_live_multitopic_setlist",
            "topic_slice_refs": ("topic_slice_setlist_ideas", "topic_slice_x32_routing_issue", "topic_slice_new_song_arrangement", "topic_slice_booking_followup"),
            "proposal_ref": "proposal_multitopic_live_music_links",
            "expected_behavior": (
                "original thread remains in music/live_music",
                "topic slices reference message ranges",
                "links proposed to target folders",
                "no destructive move",
                "provenance preserved",
                "disruptive moves require operator review",
            ),
        },
        "misfiled_chat": {
            "initial_folder": "finance/capital_hilton",
            "expected_behavior": (
                "Capital Hilton-specific slice remains linked to finance/capital_hilton/invoices",
                "general architecture slice proposes link to build/openclaw/invoice_workflows",
                "no silent destructive move",
                "provenance preserved",
            ),
            "thread_ref": "thread_ref_finance_misfiled_invoice_architecture",
            "topic_slice_refs": ("topic_slice_capital_hilton_invoice_specific", "topic_slice_invoice_automation_architecture"),
            "proposal_ref": "proposal_misfiled_invoice_architecture_link",
        },
        "x32_fader_replacement": {
            "operator_resume_phrase": "Pick up the X32 fader replacement thread.",
            "expected_target": "music/live_music/x32/maintenance",
            "future_recommendation": "RESUME_EXISTING_THREAD candidate only; no live retrieval in this contract.",
            "thread_ref": "thread_ref_x32_fader_replacement",
            "topic_slice_ref": "topic_slice_x32_fader_replacement",
            "proposal_ref": "proposal_x32_fader_resume_candidate",
        },
        "struna_drift": {
            "initial_context": "creative/music discussion",
            "topic_slices": ("creative/music slice", "build/Mac app slice", "legal/licensing summary slice"),
            "privacy_note": "raw legal/private details are not exposed",
            "operator_review_required": True,
            "thread_ref": "thread_ref_struna_creative_build_licensing",
            "proposal_ref": "proposal_struna_cross_world_review",
        },
        "raw_transcript_copy_blocker": {
            "attempt": "copy full source transcript into generated topic slice read-model",
            "blocker_type": "RAW_TRANSCRIPT_COPIED",
            "expected_behavior": "blocked; use message pointer refs and safe summary only",
        },
    }


def _all_authority_flags_false(payload: dict[str, Any]) -> bool:
    return not any(payload["authority_boundary"].values()) and not any(
        payload["conversation_topic_slicer_contract"]["authority_boundary"].values()
    )


def _machine_proof(payload: dict[str, Any]) -> dict[str, Any]:
    threads = payload["source_chat_threads_by_ref"].values()
    slices = payload["topic_slices_by_ref"].values()
    links = payload["topic_slice_graph_links_by_ref"].values()
    proposals = payload["topic_slice_reorganization_proposals_by_id"].values()
    receipts = payload["topic_slice_receipts_by_id"].values()
    blocker_types = {blocker["blocker_type"] for blocker in payload["topic_slice_blockers_by_id"].values()}
    examples = payload["examples"]
    return {
        "conversation_topic_slicer_contract_model_present": True,
        "source_chat_thread_ref_model_present": True,
        "topic_slice_model_present": True,
        "topic_slice_graph_link_model_present": True,
        "topic_slice_reorganization_proposal_model_present": True,
        "topic_slice_receipt_model_present": True,
        "topic_slice_blocker_model_present": True,
        "conversation_topic_slicer_elioperator_report_model_present": True,
        "suggested_actions_present": set(SUGGESTED_ACTIONS).issubset(payload["suggested_actions"]),
        "relationship_types_present": set(GRAPH_LINK_RELATIONSHIP_TYPES).issubset(payload["graph_link_relationship_types"]),
        "disruption_levels_present": set(DISRUPTION_LEVELS).issubset(payload["disruption_levels"]),
        "receipt_actions_present": set(RECEIPT_ACTIONS).issubset(payload["receipt_actions"]),
        "message_pointer_policy_exists": "message_pointer_policy" in payload["conversation_topic_slicer_contract"],
        "raw_transcript_disallowed_in_threads": all(thread["raw_transcript_allowed_in_read_model"] is False for thread in threads),
        "all_slices_have_message_pointers": all(slice_["message_start_ref"] and slice_["message_end_ref"] for slice_ in slices),
        "all_links_have_provenance": all(link["provenance_ref"] for link in links),
        "all_proposals_preserve_provenance": all(proposal["provenance_preserved"] is True for proposal in proposals),
        "all_proposals_disallow_deletion": all(proposal["deletion_allowed"] is False for proposal in proposals),
        "all_receipts_preserve_provenance": all(receipt["provenance_preserved"] is True for receipt in receipts),
        "all_receipts_do_not_move_or_copy_raw_body": all(
            receipt["raw_body_moved"] is False and receipt["raw_body_copied"] is False
            for receipt in receipts
        ),
        "one_chat_three_topics_example_exists": "one_chat_three_topics" in examples,
        "misfiled_chat_example_exists": "misfiled_chat" in examples,
        "x32_fader_replacement_example_exists": "x32_fader_replacement" in examples,
        "struna_drift_example_exists": "struna_drift" in examples,
        "raw_transcript_copy_blocker_exists": "RAW_TRANSCRIPT_COPIED" in blocker_types,
        "cross_client_leak_blocked": "CROSS_CLIENT_LEAK" in blocker_types,
        "silent_destructive_reorganization_blocked": "SILENT_DESTRUCTIVE_REORGANIZATION" in blocker_types,
        "blockers_present": set(BLOCKER_TYPES).issubset(blocker_types),
        "all_live_authority_flags_false": _all_authority_flags_false(payload),
        "live_topic_slicing_performed": False,
        "raw_transcript_ingested": False,
        "raw_transcript_copied": False,
        "graph_link_write_performed": False,
        "reorganization_move_split_delete_performed": False,
        "agent_retrieval_run": False,
        "cross_scope_query_run": False,
        "external_action_performed": False,
        "credentials_or_secrets_included": False,
        "raw_private_bodies_included": False,
        "mission_control_swift_changed": False,
        "mac_sync_import_run": False,
        "git_push_pull_fetch_run": False,
        "content_hash": None,
    }


def build_conversation_topic_slicer_contract(*, generated_at: str | None = None) -> dict[str, Any]:
    generated_at = generated_at or DEFAULT_GENERATED_AT
    contract = build_contract()
    threads = build_source_threads()
    slices = build_topic_slices()
    links = build_graph_links()
    proposals = build_reorganization_proposals()
    receipts = build_receipts()
    blockers = build_blockers()
    report = build_report()
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "contract_status": CONTRACT_STATUS,
        "generated_at": generated_at,
        "operator_markdown_mode": "ELIOPERATOR",
        "suggested_actions": SUGGESTED_ACTIONS,
        "graph_link_relationship_types": GRAPH_LINK_RELATIONSHIP_TYPES,
        "disruption_levels": DISRUPTION_LEVELS,
        "receipt_actions": RECEIPT_ACTIONS,
        "blocker_types": BLOCKER_TYPES,
        "model_schemas": _model_schemas(),
        "conversation_topic_slicer_contract": asdict(contract),
        "source_chat_threads_by_ref": {thread.thread_ref: asdict(thread) for thread in threads},
        "topic_slices_by_ref": {topic.topic_slice_ref: asdict(topic) for topic in slices},
        "topic_slice_graph_links_by_ref": {link.link_ref: asdict(link) for link in links},
        "topic_slice_reorganization_proposals_by_id": {
            proposal.proposal_id: asdict(proposal)
            for proposal in proposals
        },
        "topic_slice_receipts_by_id": {receipt.receipt_id: asdict(receipt) for receipt in receipts},
        "topic_slice_blockers_by_id": {
            blocker.blocker_id: asdict(blocker)
            for blocker in blockers
        },
        "conversation_topic_slicer_elioperator_report": asdict(report),
        "examples": build_examples(),
        "relationship_refs": {
            "world_project_memory_graph_projection": "semantic graph nodes and folder projection targets",
            "conversational_workflow_router_contract": "chat-derived workflow intent boundary",
            "conversational_workflow_router_intake": "Mac chat request/readback source posture",
            "operator_file_metadata_intake": "source refs and metadata-only file intake",
            "operator_file_intake_visual_workspace_contract": "visual workspace source refs and display posture",
            "worker_routing_intelligence": "worker routing for future topic/package handling",
            "workflow_execution_package_compiler": "workflow/package target examples",
            "cross_surface_artifact_handoff_registry_contract": "readback/artifact handoff refs",
            "cross_lane_reusable_block_registry_contract": "scope and protected value posture",
            "openclaw_work_terrain_relationship_index": "metadata-only relationship indexing pattern",
            "work_terrain_build_cue_reconciliation_queue": "build cue planning boundary",
            "openclaw_sensitive_policy": "private/sensitive path and raw-body boundary",
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
    report = payload["conversation_topic_slicer_elioperator_report"]
    examples = payload["examples"]
    def _example_slice_refs(example: dict[str, Any]) -> tuple[str, ...]:
        if "topic_slice_refs" in example:
            return tuple(example["topic_slice_refs"])
        if "topic_slice_ref" in example:
            return (example["topic_slice_ref"],)
        return ()

    example_lines = "\n".join(
        f"- {name}: {', '.join(_example_slice_refs(example)) or '(none)'}"
        for name, example in examples.items()
    )
    blocker_lines = "\n".join(
        f"- {blocker['blocker_type']}: {blocker['elioperator_warning']}"
        for blocker in payload["topic_slice_blockers_by_id"].values()
    )
    proposal_lines = "\n".join(
        f"- {proposal['proposal_id']}: {proposal['disruption_level']} / review={proposal['operator_review_required']}"
        for proposal in payload["topic_slice_reorganization_proposals_by_id"].values()
    )
    return "\n".join(
        [
            "# Conversation Topic Slicer Contract v0",
            "",
            "ELIOPERATOR: Topic slices are non-destructive pointers. The original chat remains intact.",
            "",
            "## What This Enables",
            "",
            report["what_this_enables"],
            "",
            "## What This Does Not Do Yet",
            "",
            report["what_this_does_not_do_yet"],
            "",
            "## How Slices Work",
            "",
            report["how_topic_slices_work"],
            "",
            "## Examples",
            "",
            example_lines,
            "",
            "## Reorganization Proposals",
            "",
            proposal_lines,
            "",
            "## Blockers",
            "",
            blocker_lines,
            "",
            "## Boundary",
            "",
            "No live topic slicing, raw transcript ingestion/copy, graph link write, reorganization, folder move, thread split, delete, agent retrieval, cross-scope query, external action, credential handling, raw-body ingestion, Mac sync/import, Swift change, or push was added.",
            "",
            f"Next safe move: {payload['conversation_topic_slicer_contract']['next_safe_move']}",
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
        "thread_count": len(payload["source_chat_threads_by_ref"]),
        "topic_slice_count": len(payload["topic_slices_by_ref"]),
        "graph_link_count": len(payload["topic_slice_graph_links_by_ref"]),
        "proposal_count": len(payload["topic_slice_reorganization_proposals_by_id"]),
        "one_chat_three_topics_example_exists": proof["one_chat_three_topics_example_exists"],
        "misfiled_chat_example_exists": proof["misfiled_chat_example_exists"],
        "x32_fader_replacement_example_exists": proof["x32_fader_replacement_example_exists"],
        "struna_drift_example_exists": proof["struna_drift_example_exists"],
        "raw_transcript_copy_blocker_exists": proof["raw_transcript_copy_blocker_exists"],
        "all_live_authority_flags_false": proof["all_live_authority_flags_false"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export the conversation topic slicer contract read-model.")
    parser.add_argument("--export-root", type=Path, default=DEFAULT_EXPORT_ROOT)
    parser.add_argument("--format", choices=("summary", "json"), default="json")
    args = parser.parse_args(argv)

    payload = build_conversation_topic_slicer_contract()
    json_path, operator_path = write_exports(payload, args.export_root)
    output = payload if args.format == "json" else build_summary(payload, json_path, operator_path)
    sys.stdout.write(stable_json(output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
