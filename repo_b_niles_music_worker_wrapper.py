"""Repo B Niles / Music Creative Worker Wrapper v0.

This deterministic Repo A read-model evaluates Repo B album/music logic and
wraps only the safe Niles-style creative planning surface. Repo B contains
useful album topic taxonomy, mix-readiness shapes, project status language,
and work-log concepts, but its album runtime also performs local LLM calls,
CSV/markdown/vault writes, Obsidian sync, marketing handoff, and legacy queue
polling. This wrapper does not import or execute Repo B code.

It does not control DAWs, mutate Logic/Ableton/Final Cut/DaVinci projects,
read audio/video/project files, render/export/publish/upload media, ingest raw
creative bodies, access external systems, handle credentials, dispatch agents,
call models, mutate Mission Control Swift, sync/import Mac files, or push.
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
REPO_B_ROOT = Path("/home/openclaw_external/openclaw-runtime")

SCHEMA_VERSION = "repo_b_niles_music_worker_wrapper_v0"
READ_MODEL_ID = "repo_b_niles_music_worker_wrapper"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
OPERATOR_EXPORT_NAME = f"{READ_MODEL_ID}_OPERATOR.md"
CONTRACT_STATUS = "DETERMINISTIC_BOUNDED_NILES_MUSIC_CREATIVE_WORKER_WRAPPER"

POSTURES = (
    "WRAP_AS_WORKER",
    "PROMOTE_SELECTED_MODULE",
    "REBUILD_SMALL_SUBSET_IN_REPO_A",
    "REFERENCE_ONLY",
    "UNSAFE_DO_NOT_CONNECT",
    "ALREADY_SUPERSEDED",
    "UNKNOWN_NEEDS_DEEPER_REVIEW",
)

CAPABILITY_TYPES = (
    "SETLIST_PLANNING",
    "ALBUM_TASK_TRACKING",
    "SONG_METADATA_ORGANIZATION",
    "MIX_NOTE_SUMMARY",
    "ARRANGEMENT_IDEA",
    "LIVE_SHOW_PLANNING",
    "CREATIVE_PROJECT_STATUS",
    "WORK_LOG_READBACK",
    "SOURCE_REF_NAVIGATION",
    "UNKNOWN",
)

READBACK_STATUSES = (
    "CREATIVE_READBACK_READY",
    "FIXTURE_READBACK_READY",
    "MISSING_INPUTS",
    "BLOCKED_PRIVACY_BOUNDARY",
    "BLOCKED_FILE_MUTATION",
    "WORKER_UNAVAILABLE",
    "UNKNOWN_FAIL_CLOSED",
)

BLOCKER_TYPES = (
    "DAW_MUTATION_ATTEMPTED",
    "AUDIO_FILE_MUTATION_ATTEMPTED",
    "VIDEO_FILE_MUTATION_ATTEMPTED",
    "EXPORT_OR_PUBLISH_ATTEMPTED",
    "BROAD_MUSIC_FOLDER_SCAN",
    "RAW_LYRIC_OR_NOTE_BODY_EXPOSED",
    "RAW_PROJECT_FILE_INGESTION",
    "EXTERNAL_ACTION_ATTEMPTED",
    "CREDENTIAL_REQUIRED",
    "UNKNOWN_FAIL_CLOSED",
)

AUTHORITY_BOUNDARY = {
    "live_daw_control_allowed": False,
    "live_audio_file_mutation_allowed": False,
    "live_video_file_mutation_allowed": False,
    "live_project_file_mutation_allowed": False,
    "live_export_allowed": False,
    "live_publish_allowed": False,
    "live_upload_allowed": False,
    "live_external_action_allowed": False,
    "live_agent_dispatch_allowed": False,
    "live_model_call_allowed": False,
    "credential_handling_allowed": False,
    "raw_body_ingestion_allowed": False,
    "network_allowed": False,
    "repo_b_runtime_execution_allowed": False,
    "repo_b_service_start_allowed": False,
    "file_body_read_allowed": False,
    "mac_sync_import_allowed": False,
    "mission_control_swift_change_allowed": False,
    "git_push_pull_fetch_allowed": False,
}

COMMON_BLOCKED_ACTIONS = (
    "control Logic Pro, Ableton, Final Cut, DaVinci, or other creative apps",
    "mutate DAW/audio/video/project files",
    "render, export, publish, or upload media",
    "scan broad music folders",
    "copy raw lyrics, notes, or project bodies into read-models",
    "start Repo B queue/listener/polling runtime",
    "call local/cloud models",
    "perform external actions",
)


@dataclass(frozen=True)
class RepoBNilesMusicWorkerDecision:
    decision_id: str
    source_module: str
    source_path: str
    apparent_value: str
    dependencies: tuple[str, ...]
    recommended_posture: str
    wrapper_scope: tuple[str, ...]
    promotion_scope: tuple[str, ...]
    blocked_items: tuple[str, ...]
    privacy_boundary: str
    next_safe_move: str


@dataclass(frozen=True)
class NilesCreativeCapability:
    capability_id: str
    source_module_ref: str
    capability_type: str
    description: str
    inputs_required: tuple[str, ...]
    outputs_produced: tuple[str, ...]
    deterministic: bool
    external_authority: bool
    file_mutation_required: bool
    raw_private_data_required: bool
    wrapper_allowed: bool
    next_safe_move: str


@dataclass(frozen=True)
class NilesCreativeWorkerRequest:
    request_id: str
    source_chat_request_ref: str
    world_ref: str
    folder_ref: str
    project_ref: str
    creative_goal: str
    requested_capability: str
    source_refs: tuple[str, ...]
    artifact_refs: tuple[str, ...]
    topic_slice_refs: tuple[str, ...]
    style_or_persona_hint: str
    privacy_class: str
    authority_boundary: dict[str, bool]
    created_at: str


@dataclass(frozen=True)
class NilesCreativeWorkerReadback:
    readback_id: str
    request_ref: str
    status: str
    safe_summary: str
    creative_output: tuple[str, ...]
    source_refs_used: tuple[str, ...]
    missing_inputs: tuple[str, ...]
    blocked_actions: tuple[str, ...]
    next_safe_move: str


@dataclass(frozen=True)
class NilesCreativeWorkerBlocker:
    blocker_id: str
    blocker_type: str
    condition: str
    severity: str
    elioperator_warning: str
    fail_closed: bool
    next_safe_move: str


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _stable_id(prefix: str, *parts: object) -> str:
    digest = hashlib.sha256("\0".join(str(part) for part in parts).encode("utf-8")).hexdigest()
    return f"{prefix}_{digest[:16]}"


def _repo_b_path(filename: str) -> str:
    return str(REPO_B_ROOT / filename)


def _status_line(text: str) -> str:
    return " ".join(text.strip().split())


def build_decisions() -> tuple[RepoBNilesMusicWorkerDecision, ...]:
    return (
        RepoBNilesMusicWorkerDecision(
            decision_id="repo_b_niles_decision_chief_album_brain",
            source_module="chief_album_brain.py",
            source_path=_repo_b_path("chief_album_brain.py"),
            apparent_value="Album topic taxonomy, song/session conversation shape, arrangement/mix readiness prompts, and album arc summary posture.",
            dependencies=(
                "chief_session_manager.py",
                "chief_album_io.py",
                "local Ollama HTTP call",
                "CSV/markdown/vault writes",
                "Obsidian sync",
                "legacy queue polling",
            ),
            recommended_posture="WRAP_AS_WORKER",
            wrapper_scope=(
                "fixture-only Niles creative readbacks",
                "source-ref based topic/status summaries",
                "no direct Repo B import or runtime execution",
            ),
            promotion_scope=(
                "topic labels",
                "safe prompt categories",
                "album/session status vocabulary",
                "completion-blocker language",
            ),
            blocked_items=(
                "local LLM extraction",
                "session state writes",
                "CSV/markdown/vault writes",
                "Obsidian sync",
                "chief_sender legacy polling",
                "raw lyric/note body ingestion",
            ),
            privacy_boundary="Niles receives safe summaries and source refs only; raw lyrics, notes, and session bodies remain excluded.",
            next_safe_move="Use the Repo A fixture/source-ref wrapper now; later add governed extraction if the operator approves a specific source.",
        ),
        RepoBNilesMusicWorkerDecision(
            decision_id="repo_b_niles_decision_chief_album_mixer",
            source_module="chief_album_mixer.py",
            source_path=_repo_b_path("chief_album_mixer.py"),
            apparent_value="Mix-readiness lines, pass/gap status shape, vocal archetype context, and mix session brief structure.",
            dependencies=(
                "chief_llm.py",
                "album_work_log.csv",
                "fundo_sessions.json",
                "Mix Briefs vault directory",
                "content_log.json marketing handoff",
            ),
            recommended_posture="REBUILD_SMALL_SUBSET_IN_REPO_A",
            wrapper_scope=(
                "safe mix-note summary from already-approved summaries",
                "read-only fixture examples",
            ),
            promotion_scope=(
                "pass/gap labels",
                "mix-readiness readback format",
                "start-here session prompt shape",
            ),
            blocked_items=(
                "LLM mix brief generation",
                "vault mix brief writes",
                "content pipeline mutation",
                "album CSV row reads with private notes",
            ),
            privacy_boundary="Generated read-models do not expose raw mix notes, song lyrics, session JSON, or vault bodies.",
            next_safe_move="Rebuild the safe summary shape in Repo A and keep live mix brief generation gated for a future lane.",
        ),
        RepoBNilesMusicWorkerDecision(
            decision_id="repo_b_niles_decision_chief_album_io",
            source_module="chief_album_io.py",
            source_path=_repo_b_path("chief_album_io.py"),
            apparent_value="Album work-log schema, song markdown section list, completion scoring, and batch-day derivation.",
            dependencies=(
                "/mnt/c/OpenClawShared/album",
                "openclaw-vault Album/Songs",
                "CSV and markdown file reads/writes",
            ),
            recommended_posture="PROMOTE_SELECTED_MODULE",
            wrapper_scope=(
                "metadata-only source refs",
                "fixture completion/status calculations",
                "no filesystem read/write in this wrapper",
            ),
            promotion_scope=(
                "BASE_CSV_FIELDS vocabulary",
                "MD_SECTIONS labels",
                "completion score concept",
                "batch-day label concept",
            ),
            blocked_items=(
                "ensure_csv/create/backup",
                "upsert_csv_row",
                "save_song_md",
                "checkpoint_song_md",
                "append_session_history",
                "save_arc_md",
                "raw markdown body loading",
            ),
            privacy_boundary="Only schema labels and deterministic status vocabulary are mirrored; source file bodies are not loaded.",
            next_safe_move="Promote small pure labels/calculation ideas only after tests prove no file IO path is copied.",
        ),
        RepoBNilesMusicWorkerDecision(
            decision_id="repo_b_niles_decision_album_work_log",
            source_module="album_work_log.csv",
            source_path=_repo_b_path("album_work_log.csv"),
            apparent_value="Potential album task/status work log for project readbacks.",
            dependencies=("CSV header/rows if present",),
            recommended_posture="REFERENCE_ONLY",
            wrapper_scope=("metadata/header-only audit when a safe file exists",),
            promotion_scope=("work-log readback shape", "source-ref navigation target"),
            blocked_items=("row/body ingestion", "private song status dump", "direct CSV mutation"),
            privacy_boundary="The requested Repo B root did not expose an album_work_log.csv during this lane; no rows were read.",
            next_safe_move="Use operator-provided file metadata/source refs when a current work log should be attached.",
        ),
    )


def build_capabilities() -> tuple[NilesCreativeCapability, ...]:
    rows: list[NilesCreativeCapability] = [
        NilesCreativeCapability(
            capability_id="niles_capability_setlist_planning",
            source_module_ref="repo_b_niles_decision_chief_album_brain",
            capability_type="SETLIST_PLANNING",
            description="Create a safe setlist arc from operator goals and source refs without touching files or apps.",
            inputs_required=("show_goal", "set_length_hint", "must_play_refs", "energy_profile"),
            outputs_produced=("setlist_arc", "missing_inputs", "next_rehearsal_questions"),
            deterministic=True,
            external_authority=False,
            file_mutation_required=False,
            raw_private_data_required=False,
            wrapper_allowed=True,
            next_safe_move="Ask for venue length, band format, and must-play refs before finalizing.",
        ),
        NilesCreativeCapability(
            capability_id="niles_capability_album_task_tracking",
            source_module_ref="repo_b_niles_decision_chief_album_io",
            capability_type="ALBUM_TASK_TRACKING",
            description="Summarize album task status from safe work-log/source-ref metadata.",
            inputs_required=("album_work_log_source_ref", "topic_slice_refs"),
            outputs_produced=("task_status_summary", "missing_work_log_refs"),
            deterministic=True,
            external_authority=False,
            file_mutation_required=False,
            raw_private_data_required=False,
            wrapper_allowed=True,
            next_safe_move="Attach or reference the current work log as metadata before deeper status readback.",
        ),
        NilesCreativeCapability(
            capability_id="niles_capability_song_metadata_organization",
            source_module_ref="repo_b_niles_decision_chief_album_io",
            capability_type="SONG_METADATA_ORGANIZATION",
            description="Organize song status labels, section refs, and album placement without copying raw song bodies.",
            inputs_required=("song_metadata_ref", "album_plan_ref"),
            outputs_produced=("song_position_summary", "related_source_refs"),
            deterministic=True,
            external_authority=False,
            file_mutation_required=False,
            raw_private_data_required=False,
            wrapper_allowed=True,
            next_safe_move="Keep song lyrics and private notes below deck unless a governed extract is approved.",
        ),
        NilesCreativeCapability(
            capability_id="niles_capability_mix_note_summary",
            source_module_ref="repo_b_niles_decision_chief_album_mixer",
            capability_type="MIX_NOTE_SUMMARY",
            description="Summarize already-safe mix-note highlights and pass/gap status.",
            inputs_required=("safe_mix_note_summary_refs", "mix_status_metadata_refs"),
            outputs_produced=("mix_focus_summary", "blocked_raw_note_warning"),
            deterministic=True,
            external_authority=False,
            file_mutation_required=False,
            raw_private_data_required=False,
            wrapper_allowed=True,
            next_safe_move="Provide a safe summary or source ref; do not paste full raw notes into the wrapper.",
        ),
        NilesCreativeCapability(
            capability_id="niles_capability_arrangement_idea",
            source_module_ref="repo_b_niles_decision_chief_album_brain",
            capability_type="ARRANGEMENT_IDEA",
            description="Suggest arrangement next moves from topic slices and safe song summaries.",
            inputs_required=("song_context_summary", "arrangement_goal"),
            outputs_produced=("arrangement_options", "questions_for_operator"),
            deterministic=True,
            external_authority=False,
            file_mutation_required=False,
            raw_private_data_required=False,
            wrapper_allowed=True,
            next_safe_move="Return candidate ideas only; route DAW edits to a future gated Mac lane.",
        ),
        NilesCreativeCapability(
            capability_id="niles_capability_live_show_planning",
            source_module_ref="repo_b_niles_decision_chief_album_brain",
            capability_type="LIVE_SHOW_PLANNING",
            description="Plan rehearsal/show context and needed source refs for live music work.",
            inputs_required=("show_context_ref", "venue_or_set_length_hint", "live_rig_refs"),
            outputs_produced=("planning_summary", "missing_source_refs"),
            deterministic=True,
            external_authority=False,
            file_mutation_required=False,
            raw_private_data_required=False,
            wrapper_allowed=True,
            next_safe_move="Bind X32/show-file refs through file metadata intake before any visual workspace or app handoff.",
        ),
        NilesCreativeCapability(
            capability_id="niles_capability_creative_project_status",
            source_module_ref="repo_b_niles_decision_chief_album_io",
            capability_type="CREATIVE_PROJECT_STATUS",
            description="Produce a project status readback from safe album/song metadata refs.",
            inputs_required=("project_ref", "topic_slice_refs", "source_refs"),
            outputs_produced=("project_status_readback", "unknowns"),
            deterministic=True,
            external_authority=False,
            file_mutation_required=False,
            raw_private_data_required=False,
            wrapper_allowed=True,
            next_safe_move="Use graph/folder coordinates and source refs, not a guessed folder name alone.",
        ),
        NilesCreativeCapability(
            capability_id="niles_capability_work_log_readback",
            source_module_ref="repo_b_niles_decision_album_work_log",
            capability_type="WORK_LOG_READBACK",
            description="Create a safe work-log readback when a metadata/source-ref rail exists.",
            inputs_required=("work_log_source_ref", "approved_safe_extract_ref"),
            outputs_produced=("work_log_status_summary", "blocked_body_notice"),
            deterministic=True,
            external_authority=False,
            file_mutation_required=False,
            raw_private_data_required=False,
            wrapper_allowed=True,
            next_safe_move="If only a file ref exists, report that body extraction is still gated.",
        ),
        NilesCreativeCapability(
            capability_id="niles_capability_source_ref_navigation",
            source_module_ref="repo_a_file_metadata_and_memory_graph",
            capability_type="SOURCE_REF_NAVIGATION",
            description="Help the operator locate relevant music source refs without scanning folders or opening project files.",
            inputs_required=("world_ref", "folder_ref", "source_ref_labels"),
            outputs_produced=("navigation_hint", "missing_source_ref_questions"),
            deterministic=True,
            external_authority=False,
            file_mutation_required=False,
            raw_private_data_required=False,
            wrapper_allowed=True,
            next_safe_move="Ask for or create metadata-only source refs for the files the operator wants to use.",
        ),
    ]
    return tuple(rows)


def build_request(fixture: str, generated_at: str = DEFAULT_GENERATED_AT) -> NilesCreativeWorkerRequest:
    fixtures = {
        "setlist": {
            "goal": "Niles, help me build a setlist for tonight.",
            "capability": "SETLIST_PLANNING",
            "world_ref": "music",
            "folder_ref": "music/live_music/setlists",
            "project_ref": "live_show_fixture",
            "source_refs": ("source_ref:setlist_pool_metadata",),
            "topic_slice_refs": ("topic_slice:live_show_setlist_safe_summary",),
            "persona": "Niles live show planner",
        },
        "x32": {
            "goal": "Niles, pull up the X32 show-file context.",
            "capability": "SOURCE_REF_NAVIGATION",
            "world_ref": "music",
            "folder_ref": "music/live_music/x32",
            "project_ref": "x32_live_rig",
            "source_refs": (),
            "topic_slice_refs": ("topic_slice:x32_routing_safe_summary",),
            "persona": "Niles live rig navigator",
        },
        "album_song": {
            "goal": "Show me where this song is in the album plan.",
            "capability": "CREATIVE_PROJECT_STATUS",
            "world_ref": "music",
            "folder_ref": "music/studio/album/song",
            "project_ref": "album_plan",
            "source_refs": ("source_ref:album_plan_metadata", "source_ref:song_status_metadata"),
            "topic_slice_refs": ("topic_slice:album_song_status_safe_summary",),
            "persona": "Niles album project navigator",
        },
        "mix_notes": {
            "goal": "Summarize the current safe mix-note highlights.",
            "capability": "MIX_NOTE_SUMMARY",
            "world_ref": "music",
            "folder_ref": "music/studio/album/mix_notes",
            "project_ref": "mix_notes",
            "source_refs": ("source_ref:mix_notes_safe_summary",),
            "topic_slice_refs": ("topic_slice:mix_focus_safe_summary",),
            "persona": "Niles mix-note summarizer",
        },
        "struna": {
            "goal": "Niles, let's work on Struna.",
            "capability": "CREATIVE_PROJECT_STATUS",
            "world_ref": "music",
            "folder_ref": "music/struna",
            "project_ref": "struna",
            "source_refs": ("source_ref:struna_project_metadata",),
            "topic_slice_refs": ("topic_slice:struna_creative_build_safe_summary",),
            "persona": "Niles creative/build bridge",
        },
        "daw_mutation": {
            "goal": "Open Logic and change the mix.",
            "capability": "UNKNOWN",
            "world_ref": "music",
            "folder_ref": "music/studio/logic",
            "project_ref": "logic_project",
            "source_refs": ("source_ref:logic_project_metadata",),
            "topic_slice_refs": (),
            "persona": "Niles blocked DAW mutation reviewer",
        },
    }
    if fixture not in fixtures:
        raise ValueError(f"Unsupported fixture: {fixture}")
    item = fixtures[fixture]
    return NilesCreativeWorkerRequest(
        request_id=f"niles_music_request_{fixture}_v0",
        source_chat_request_ref=f"fixture_chat:{fixture}",
        world_ref=item["world_ref"],
        folder_ref=item["folder_ref"],
        project_ref=item["project_ref"],
        creative_goal=item["goal"],
        requested_capability=item["capability"],
        source_refs=tuple(item["source_refs"]),
        artifact_refs=(),
        topic_slice_refs=tuple(item["topic_slice_refs"]),
        style_or_persona_hint=item["persona"],
        privacy_class="operator_local_private",
        authority_boundary=dict(AUTHORITY_BOUNDARY),
        created_at=generated_at,
    )


def build_fixture_readback(request: NilesCreativeWorkerRequest) -> NilesCreativeWorkerReadback:
    capability = request.requested_capability
    if request.request_id.endswith("_daw_mutation_v0"):
        return NilesCreativeWorkerReadback(
            readback_id="niles_music_readback_daw_mutation_blocked_v0",
            request_ref=request.request_id,
            status="BLOCKED_FILE_MUTATION",
            safe_summary="This request asks Niles to change a Logic mix, which is DAW/project mutation and is outside this wrapper.",
            creative_output=(
                "No DAW was opened.",
                "No mix, session, audio, or project file was changed.",
                "A future Mac Codex/app-automation lane would need explicit approval, backup posture, and receipts before any mutation.",
            ),
            source_refs_used=request.source_refs,
            missing_inputs=("approved Mac app automation package", "backup/receipt posture", "operator mutation approval"),
            blocked_actions=("DAW control", "project file mutation", "audio file mutation"),
            next_safe_move="Route this as a future MAC_CODEX/Mac automation boundary review if the operator wants to prepare a gated package.",
        )

    if capability == "SETLIST_PLANNING":
        return NilesCreativeWorkerReadback(
            readback_id="niles_music_readback_setlist_fixture_v0",
            request_ref=request.request_id,
            status="FIXTURE_READBACK_READY",
            safe_summary="Niles can draft a setlist arc from safe show goals and setlist source refs without touching files or apps.",
            creative_output=(
                "Start with a confident opener, then place one familiar anchor early so the room locks in.",
                "Use the middle third for contrast: one groove-forward lift, one slower reset, then the strongest transition song.",
                "Close with the song that leaves the clearest identity stamp; keep one encore candidate separate until set length is confirmed.",
                "Needed before final set order: venue length, band format, must-play songs, and any songs to avoid tonight.",
            ),
            source_refs_used=request.source_refs,
            missing_inputs=("venue length", "band format", "must-play source refs", "songs to avoid"),
            blocked_actions=("external posting", "file mutation", "DAW access"),
            next_safe_move="Ask the operator for set length and must-play refs, then return a second setlist card.",
        )

    if capability == "SOURCE_REF_NAVIGATION":
        return NilesCreativeWorkerReadback(
            readback_id="niles_music_readback_x32_fixture_v0",
            request_ref=request.request_id,
            status="MISSING_INPUTS",
            safe_summary="Niles can point to X32 routing context, but no current show-file source ref is attached in this fixture.",
            creative_output=(
                "Expected folder scope: music/live_music/x32.",
                "Use a metadata-only source ref for the X32 show file, routing notes, or troubleshooting chat.",
                "No show-file body was read and no mixer state was changed.",
            ),
            source_refs_used=request.source_refs,
            missing_inputs=("X32 show-file metadata source ref", "routing notes source ref if available"),
            blocked_actions=("mixer mutation", "project file ingestion", "broad music folder scan"),
            next_safe_move="Attach or reference the X32 file through file metadata intake, then reopen the visual/source-ref workspace.",
        )

    if capability == "MIX_NOTE_SUMMARY":
        return NilesCreativeWorkerReadback(
            readback_id="niles_music_readback_mix_notes_fixture_v0",
            request_ref=request.request_id,
            status="FIXTURE_READBACK_READY",
            safe_summary="Niles can summarize safe mix-note highlights while excluding private raw notes and session bodies.",
            creative_output=(
                "Mix focus: preserve the strongest hook element, confirm the vocal sits clearly, and identify one low-end or transition issue before opening a session.",
                "This is a planning brief, not a mix instruction executed in a DAW.",
                "Raw note bodies remain excluded; only safe source refs and summaries were used.",
            ),
            source_refs_used=request.source_refs,
            missing_inputs=("approved safe extract if deeper note detail is needed",),
            blocked_actions=("raw note body exposure", "DAW control", "audio file mutation"),
            next_safe_move="If the operator wants detail, request a governed extract from the specific mix-note source ref.",
        )

    if request.project_ref == "struna":
        return NilesCreativeWorkerReadback(
            readback_id="niles_music_readback_struna_fixture_v0",
            request_ref=request.request_id,
            status="FIXTURE_READBACK_READY",
            safe_summary="Niles can bridge Struna creative and build context using scoped metadata, not legal truth or source mutation.",
            creative_output=(
                "Treat Struna as a scoped creative/build project with music identity, Mac app surface, and agreement-summary metadata.",
                "Draper/Winship ownership context is a remembered summary for routing only, not legal advice or proof.",
                "Next useful split: creative direction, Mac build surface, and licensing/agreement review each get their own scoped context package.",
            ),
            source_refs_used=request.source_refs,
            missing_inputs=("current Struna source refs if the operator wants artifact-specific work",),
            blocked_actions=("legal truth claim", "source mutation", "external publishing"),
            next_safe_move="Ask whether the next Struna move is creative planning, Mac build work, or agreement review.",
        )

    return NilesCreativeWorkerReadback(
        readback_id="niles_music_readback_album_song_fixture_v0",
        request_ref=request.request_id,
        status="FIXTURE_READBACK_READY",
        safe_summary="Niles can show where a song sits in the album plan using source refs and topic slices only.",
        creative_output=(
            "Song workspace view: album plan ref, song status ref, and relevant topic slice summaries are enough for a first status card.",
            "No lyrics, raw notes, DAW sessions, or project files are included by default.",
            "Useful next question: are we checking placement, readiness, mix focus, or arrangement direction?",
        ),
        source_refs_used=request.source_refs,
        missing_inputs=("specific song ref or title", "desired status question"),
        blocked_actions=("raw lyric body exposure", "project file ingestion", "file mutation"),
        next_safe_move="Ask which song and which album-plan question the operator wants answered.",
    )


def build_blockers() -> tuple[NilesCreativeWorkerBlocker, ...]:
    messages = {
        "DAW_MUTATION_ATTEMPTED": ("Open Logic and change the mix.", "DAW/project mutation is not allowed in the Niles wrapper."),
        "AUDIO_FILE_MUTATION_ATTEMPTED": ("Render or edit an audio file.", "Audio file mutation is outside this lane."),
        "VIDEO_FILE_MUTATION_ATTEMPTED": ("Render or edit a video project.", "Video project mutation is outside this lane."),
        "EXPORT_OR_PUBLISH_ATTEMPTED": ("Export, publish, or upload media.", "Publishing/exporting requires a separate gated adapter."),
        "BROAD_MUSIC_FOLDER_SCAN": ("Scan the whole music folder.", "Broad music folder scanning is blocked."),
        "RAW_LYRIC_OR_NOTE_BODY_EXPOSED": ("Put full lyrics or private notes in the read-model.", "Raw creative bodies stay below deck."),
        "RAW_PROJECT_FILE_INGESTION": ("Parse a Logic/Ableton/project file body.", "Project file ingestion is blocked."),
        "EXTERNAL_ACTION_ATTEMPTED": ("Post, send, publish, or call an external system.", "External action is blocked."),
        "CREDENTIAL_REQUIRED": ("Use credentials for a music service.", "Credentials are not handled here."),
        "UNKNOWN_FAIL_CLOSED": ("Unknown music worker action.", "Unknown actions fail closed."),
    }
    rows = []
    for blocker_type, (condition, warning) in messages.items():
        rows.append(
            NilesCreativeWorkerBlocker(
                blocker_id=f"niles_music_blocker_{blocker_type.lower()}",
                blocker_type=blocker_type,
                condition=condition,
                severity="critical" if blocker_type != "UNKNOWN_FAIL_CLOSED" else "high",
                elioperator_warning=warning,
                fail_closed=True,
                next_safe_move="Keep Niles to source-ref creative planning or route to a separately gated worker lane.",
            )
        )
    return tuple(rows)


def build_examples(generated_at: str = DEFAULT_GENERATED_AT) -> dict[str, Any]:
    fixture_names = ("setlist", "x32", "album_song", "mix_notes", "daw_mutation", "struna")
    examples: dict[str, Any] = {}
    for name in fixture_names:
        request = build_request(name, generated_at)
        readback = build_fixture_readback(request)
        examples[name] = {
            "operator_input": request.creative_goal,
            "request": asdict(request),
            "readback": asdict(readback),
        }
    return {
        "setlist_planning": examples["setlist"],
        "x32_live_show_context": examples["x32"],
        "album_song_workspace": examples["album_song"],
        "mix_notes_summary": examples["mix_notes"],
        "daw_mutation_blocker": examples["daw_mutation"],
        "struna_creative_build_bridge": examples["struna"],
    }


def build_payload(
    *,
    generated_at: str = DEFAULT_GENERATED_AT,
    selected_fixture: str | None = None,
) -> dict[str, Any]:
    decisions = build_decisions()
    capabilities = build_capabilities()
    blockers = build_blockers()
    examples = build_examples(generated_at)
    selected_request = build_request(selected_fixture, generated_at) if selected_fixture else None
    selected_readback = build_fixture_readback(selected_request) if selected_request else None
    safe_capability_ids = tuple(cap.capability_id for cap in capabilities if cap.wrapper_allowed)
    blocked_capabilities = tuple(blocker.blocker_type for blocker in blockers if blocker.blocker_type != "UNKNOWN_FAIL_CLOSED")
    return {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "contract_status": CONTRACT_STATUS,
        "generated_at": generated_at,
        "repo_b_root": str(REPO_B_ROOT),
        "postures": POSTURES,
        "capability_types": CAPABILITY_TYPES,
        "readback_statuses": READBACK_STATUSES,
        "blocker_types": BLOCKER_TYPES,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "niles_worker_decisions": [asdict(row) for row in decisions],
        "creative_capabilities": [asdict(row) for row in capabilities],
        "niles_worker_blockers": [asdict(row) for row in blockers],
        "wrapper_plan": {
            "posture": "WRAP_AS_WORKER_WITH_PROMOTED_DETERMINISTIC_SUBSET",
            "safe_capabilities": safe_capability_ids,
            "blocked_capabilities": blocked_capabilities,
            "repo_b_invocation": "none in v0",
            "fixture_mode": True,
            "source_ref_mode": True,
            "promotion_scope": (
                "topic/category labels",
                "status/readiness shape",
                "safe work-log/source-ref navigation shape",
                "fixture-based setlist and project status readbacks",
            ),
            "excluded_scope": COMMON_BLOCKED_ACTIONS,
            "next_safe_move": "Wire Niles as a deterministic/source-ref creative worker target before any live Repo B invocation.",
        },
        "examples": examples,
        "selected_fixture": selected_fixture,
        "selected_request": asdict(selected_request) if selected_request else None,
        "selected_readback": asdict(selected_readback) if selected_readback else None,
        "machine_proof": {
            "all_live_authority_false": all(value is False for value in AUTHORITY_BOUNDARY.values()),
            "repo_b_code_imported": False,
            "repo_b_runtime_executed": False,
            "daw_control_performed": False,
            "audio_file_mutation_performed": False,
            "video_file_mutation_performed": False,
            "project_file_mutation_performed": False,
            "export_publish_upload_performed": False,
            "external_action_performed": False,
            "credential_handling_performed": False,
            "raw_private_body_exposure": False,
            "mac_sync_import_performed": False,
            "swift_change_performed": False,
            "git_push_performed": False,
        },
        "operator_summary": (
            "Repo B music logic is useful as a Niles creative planning/reference surface, "
            "but v0 keeps it fixture/source-ref based and blocks DAW, media, file-body, model, and publishing authority."
        ),
        "next_safe_move": "Use Niles for safe creative planning cards, then route visual/app or DAW work to future gated Mac lanes only when explicitly approved.",
    }


def format_operator_markdown(payload: dict[str, Any]) -> str:
    selected = payload.get("selected_readback") or payload["examples"]["setlist_planning"]["readback"]
    lines = [
        "# Repo B Niles Music Worker Wrapper",
        "",
        "## Summary",
        payload["operator_summary"],
        "",
        "## Posture",
        f"- Wrapper posture: {payload['wrapper_plan']['posture']}",
        "- Repo B invocation: none in v0",
        "- Source mode: metadata/source refs and safe summaries only",
        "",
        "## Safe Capabilities",
    ]
    for capability in payload["creative_capabilities"]:
        lines.append(f"- {capability['capability_type']}: {capability['description']}")
    lines += [
        "",
        "## Blocked Capabilities",
    ]
    for blocker in payload["niles_worker_blockers"]:
        lines.append(f"- {blocker['blocker_type']}: {blocker['elioperator_warning']}")
    lines += [
        "",
        "## Example Readback",
        f"- Status: {selected['status']}",
        f"- Summary: {_status_line(selected['safe_summary'])}",
        f"- Next safe move: {selected['next_safe_move']}",
        "",
        "## Boundary",
        "No DAW control, no audio/video/project mutation, no export/publish/upload, no external action, no credentials, no raw private body exposure.",
    ]
    return "\n".join(lines) + "\n"


def write_exports(payload: dict[str, Any], export_root: Path = DEFAULT_EXPORT_ROOT) -> tuple[Path, Path]:
    export_root.mkdir(parents=True, exist_ok=True)
    json_path = export_root / JSON_EXPORT_NAME
    operator_path = export_root / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(format_operator_markdown(payload), encoding="utf-8")
    return json_path, operator_path


def _summary(payload: dict[str, Any]) -> dict[str, Any]:
    selected = payload.get("selected_readback")
    return {
        "read_model_id": payload["read_model_id"],
        "posture": payload["wrapper_plan"]["posture"],
        "selected_fixture": payload.get("selected_fixture"),
        "selected_status": selected["status"] if selected else None,
        "safe_capabilities": len(payload["wrapper_plan"]["safe_capabilities"]),
        "blocked_capabilities": len(payload["wrapper_plan"]["blocked_capabilities"]),
        "all_live_authority_false": payload["machine_proof"]["all_live_authority_false"],
        "json_export": str(DEFAULT_EXPORT_ROOT / JSON_EXPORT_NAME),
        "operator_export": str(DEFAULT_EXPORT_ROOT / OPERATOR_EXPORT_NAME),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export Repo B Niles music worker wrapper read-model.")
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT))
    parser.add_argument("--generated-at", default=DEFAULT_GENERATED_AT)
    parser.add_argument(
        "--fixture",
        choices=("setlist", "x32", "album_song", "mix_notes", "daw_mutation", "struna"),
        default=None,
        help="Include a selected fixture request/readback for run mode.",
    )
    parser.add_argument("--format", choices=("json", "summary"), default="summary")
    args = parser.parse_args(argv)

    payload = build_payload(generated_at=args.generated_at, selected_fixture=args.fixture)
    write_exports(payload, Path(args.export_root))
    if args.format == "json":
        print(stable_json(payload), end="")
    else:
        print(stable_json(_summary(payload)), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
