"""Mission Control Design Memory Inventory v0.

This read-model captures source-backed Mission Control design doctrine, taste
constraints, known unknowns, and safe next source requests. It is deterministic
metadata only. It does not implement UI, ingest broad private chat history,
call models, activate agents, access browser/account surfaces, mutate Mac app
files, grant runtime authority, or write OpenClaw artifacts to the PC C-drive.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from business_ops_ledger import DEFAULT_DB_PATH, init_business_ops_ledger, record_receipt


ROOT = Path(__file__).resolve().parent
DEFAULT_EXPORT_ROOT = Path("generated/read_models")

SCHEMA_VERSION = "mission_control_design_memory_inventory_v0"
JSON_EXPORT_NAME = "mission_control_design_memory_inventory.json"
OPERATOR_EXPORT_NAME = "mission_control_design_memory_inventory_OPERATOR.md"

CLASSIFICATIONS = (
    "known_and_tracked",
    "partly_known",
    "known_unknown",
    "not_yet_discovered",
    "needs_winship_memory_comparison",
    "candidate_future_sqlite_promotion",
    "blocked_or_not_authorized",
    "safe_next_source_to_inspect",
)

AFFECTS_KEYS = (
    "helm_front_door",
    "worlds",
    "check_lights",
    "steel_thread",
    "package_compiler",
    "actor_router",
    "visual_design",
    "operator_controls",
)

CONFIDENCE_STATES = (
    "FULL_TRUST_DISPLAY_QUIET",
    "HIGH_TRUST_SOURCE_BACKED",
    "MEDIUM_TRUST_PARTLY_SOURCE_BACKED",
    "LOW_TRUST_SOURCE_MISSING",
    "UNKNOWN_FAIL_CLOSED",
)

NO_AUTHORITY_FLAGS = {
    "read_model_only": True,
    "metadata_only": True,
    "inventory_only": True,
    "sqlite_receipt_metadata_only": True,
    "sqlite_schema_changed": False,
    "model_calls_made": False,
    "lm_called": False,
    "external_model_apis_called": False,
    "agents_activated": False,
    "agent_launch_authority_added": False,
    "tools_enabled": False,
    "plugins_wired": False,
    "browser_oauth_or_account_access_enabled": False,
    "browser_accessed": False,
    "oauth_or_credentials_accessed": False,
    "credentials_stored": False,
    "gmail_calendar_coupa_accessed": False,
    "telegram_send_triggered": False,
    "email_send_triggered": False,
    "send_or_submit_authority_added": False,
    "approval_authority_added": False,
    "execution_authority_added": False,
    "runtime_authority_added": False,
    "live_launch_buttons_created": False,
    "mission_control_app_changed": False,
    "mac_app_files_mutated": False,
    "mac_commands_run_from_pc": False,
    "delete_authority_added": False,
    "cleanup_authority_added": False,
    "remount_authority_added": False,
    "credential_handling_added": False,
    "c_drive_write_allowed": False,
    "c_drive_artifact_written": False,
    "repo_b_filesystem_inspected": False,
    "repo_b_code_executed": False,
    "raw_private_content_inspected": False,
    "broad_private_chat_ingested": False,
    "chatgpt_history_ingested": False,
    "raw_private_file_bodies_stored": False,
    "raw_logs_stored": False,
    "broad_file_dump_stored": False,
}

FORBIDDEN_ACTIONS = (
    "call external model APIs",
    "run Codex, Antigravity, VS Code agent, browser, or other live sessions",
    "mutate Mission Control app files",
    "create live launch buttons",
    "create runtime execution authority",
    "create browser, OAuth, Gmail, calendar, Coupa, Telegram, send, submit, or approval authority",
    "write OpenClaw artifacts to the PC system drive",
    "delete, cleanup, remount, or handle credentials",
    "ingest broad private chat history or raw private file bodies",
)


@dataclass(frozen=True)
class SourceDoc:
    key: str
    path: str
    role: str


@dataclass(frozen=True)
class SourceReadModel:
    key: str
    path: str
    role: str


@dataclass(frozen=True)
class ThemeSpec:
    theme_id: str
    title: str
    classification: str
    summary: str
    source_refs: tuple[str, ...]
    confidence: str
    why_it_matters: str
    affects: tuple[str, ...]
    current_gap: str
    safe_next_move: str
    what_not_to_build_from_this_yet: str


@dataclass(frozen=True)
class MissionControlDesignMemoryInventoryExportResult:
    schema_version: str
    json_path: str
    operator_path: str
    theme_count: int
    sqlite_receipt_supported: bool
    broad_private_chat_ingested: bool
    c_drive_artifact_written: bool
    runtime_authority_added: bool


SOURCE_DOCS = (
    SourceDoc(
        "operator_north_star_and_taste",
        "Operator/01_NORTH_STAR_AND_TASTE.md",
        "operator-level taste, authority, and local-first doctrine",
    ),
    SourceDoc(
        "operator_orientation_contract",
        "Operator/05_ORIENTATION_CONTRACT.md",
        "operator orientation and anti-dashboard boundary",
    ),
    SourceDoc(
        "generated_current_state",
        "Operator/GENERATED_CURRENT_STATE.md",
        "current generated state and world registry posture",
    ),
    SourceDoc(
        "mission_control_fixture_contract",
        "docs/planning/launch_ladder/12_MAC_DESKTOP_MISSION_CONTROL_FIXTURE_CONTRACT.md",
        "read-only fixture state and proof semantics",
    ),
    SourceDoc(
        "first_screen_composition_spec",
        "docs/planning/launch_ladder/13_MAC_DESKTOP_FIRST_SCREEN_COMPOSITION_SPEC.md",
        "first-screen composition, calm cockpit, and proof drawer doctrine",
    ),
    SourceDoc(
        "taste_and_atmosphere_spec",
        "docs/planning/launch_ladder/14_MAC_DESKTOP_TASTE_AND_ATMOSPHERE_SPEC.md",
        "Mission Control taste vocabulary, vibe tests, and anti-vibe tests",
    ),
    SourceDoc(
        "sound_haptics_quiet_feedback_addendum",
        "docs/planning/launch_ladder/15_MAC_DESKTOP_SOUND_HAPTICS_QUIET_FEEDBACK_ADDENDUM.md",
        "future quiet feedback posture and forbidden sound/haptic patterns",
    ),
)

SOURCE_READ_MODELS = (
    SourceReadModel(
        "operator_mission_priority_helm_declutter",
        "generated/read_models/operator_mission_priority_helm_declutter.json",
        "mission priority, helm/check-light/world/proof-detail classification",
    ),
    SourceReadModel(
        "steel_thread_lane_template_registry",
        "generated/read_models/steel_thread_lane_template_registry.json",
        "reusable steel-thread lane templates",
    ),
    SourceReadModel(
        "package_compiler_contract",
        "generated/read_models/package_compiler_contract.json",
        "package compiler skeleton and preview-only authority boundary",
    ),
    SourceReadModel(
        "operator_workbench_actor_host_registry",
        "generated/read_models/operator_workbench_actor_host_registry.json",
        "Operator System workbench and actor-host registry",
    ),
    SourceReadModel(
        "system_health_lights_taxonomy",
        "generated/read_models/system_health_lights_taxonomy.json",
        "health light taxonomy and current light posture",
    ),
    SourceReadModel(
        "operator_nested_lane_mission_package_spine",
        "generated/read_models/operator_nested_lane_mission_package_spine.json",
        "nested lane model and mission package doctrine",
    ),
    SourceReadModel(
        "operator_awareness_agent_package_spine",
        "generated/read_models/operator_awareness_agent_package_spine.json",
        "awareness gaps, confidence repair, and package preview spine",
    ),
    SourceReadModel(
        "world_domain_registry",
        "generated/read_models/world_domain_registry.json",
        "world/domain registry and teleport target vocabulary",
    ),
)

DOCTRINE_SOURCE_LABELS = (
    "operator_prompt: Mission Control Design Memory Inventory v0",
    "repo_a_source: Operator/01_NORTH_STAR_AND_TASTE.md",
    "repo_a_source: Operator/05_ORIENTATION_CONTRACT.md",
    "repo_a_source: docs/planning/launch_ladder/12_MAC_DESKTOP_MISSION_CONTROL_FIXTURE_CONTRACT.md",
    "repo_a_source: docs/planning/launch_ladder/13_MAC_DESKTOP_FIRST_SCREEN_COMPOSITION_SPEC.md",
    "repo_a_source: docs/planning/launch_ladder/14_MAC_DESKTOP_TASTE_AND_ATMOSPHERE_SPEC.md",
    "repo_a_source: docs/planning/launch_ladder/15_MAC_DESKTOP_SOUND_HAPTICS_QUIET_FEEDBACK_ADDENDUM.md",
    "existing_read_model: Operator Mission Priority / Helm Declutter Taxonomy v0",
    "existing_read_model: Steel Thread Lane Template Registry v0",
    "existing_read_model: Package Compiler Contract v0",
    "existing_read_model: Operator Workbench / Actor Host Registry v0",
    "existing_read_model: System Health Lights Taxonomy v0",
    "existing_read_model: World Domain Registry",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _rooted(path: str | Path, *, repo_root: str | Path = ROOT) -> Path:
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    return Path(repo_root) / candidate


def _display_path(path: str | Path) -> str:
    candidate = Path(path)
    try:
        return candidate.resolve().relative_to(ROOT.resolve()).as_posix()
    except (OSError, ValueError):
        return candidate.as_posix()


def _sha256_file(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def _hash_payload(payload: Any) -> str:
    digest = hashlib.sha256(stable_json(payload).encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def _read_json_if_present(path: str | Path, *, repo_root: str | Path = ROOT) -> dict[str, Any]:
    target = _rooted(path, repo_root=repo_root)
    if not target.exists() or target.suffix.lower() != ".json":
        return {}
    payload = json.loads(target.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _read_text_if_present(path: str | Path, *, repo_root: str | Path = ROOT) -> str:
    target = _rooted(path, repo_root=repo_root)
    if not target.exists() or not target.is_file():
        return ""
    return target.read_text(encoding="utf-8")


def _source_doc_record(source: SourceDoc, *, repo_root: str | Path) -> dict[str, Any]:
    target = _rooted(source.path, repo_root=repo_root)
    return {
        "key": source.key,
        "path": source.path,
        "present": target.exists(),
        "sha256": _sha256_file(target),
        "role": source.role,
        "approved_repo_a_source": True,
        "source_kind": "bounded_design_doctrine_source",
        "raw_private_content_read": False,
        "raw_body_exported": False,
        "broad_private_chat_ingested": False,
    }


def _source_read_model_record(
    source: SourceReadModel,
    *,
    repo_root: str | Path,
    payload: dict[str, Any],
) -> dict[str, Any]:
    target = _rooted(source.path, repo_root=repo_root)
    return {
        "key": source.key,
        "path": source.path,
        "present": target.exists(),
        "schema_version": payload.get("schema_version") or payload.get("read_model_version"),
        "role": source.role,
        "source_kind": "generated_read_model_reference",
        "raw_body_exported": False,
        "executed_or_dispatched": False,
        "runtime_authority_added": False,
    }


def _combined_source_text(*, repo_root: str | Path) -> str:
    texts = [_read_text_if_present(source.path, repo_root=repo_root) for source in SOURCE_DOCS]
    return "\n".join(texts).lower()


def _source_terms_present(source_text: str) -> dict[str, bool]:
    return {
        "mission_control": "mission control" in source_text,
        "helm": "helm" in source_text,
        "cockpit": "cockpit" in source_text,
        "studio_console": "studio console" in source_text,
        "spaceship": "spaceship" in source_text,
        "doom": "doom" in source_text,
        "space_station": "space station" in source_text,
        "teleport": "teleport" in source_text,
        "worlds": "worlds" in source_text,
        "chatbot": "chatbot" in source_text,
        "saas": "saas" in source_text,
        "rag_search": "rag search" in source_text or "rag search box" in source_text,
        "check_engine": "check engine" in source_text,
        "check_transmission": "check transmission" in source_text,
        "software_likes": "software likes" in source_text,
        "software_dislikes": "software dislikes" in source_text,
        "video_game": "video game" in source_text,
    }


def _affects(*keys: str) -> tuple[str, ...]:
    invalid = sorted(set(keys) - set(AFFECTS_KEYS))
    if invalid:
        raise ValueError(f"unknown affects keys: {invalid}")
    return tuple(keys)


def _theme_specs() -> tuple[ThemeSpec, ...]:
    return (
        ThemeSpec(
            "mission_control_as_helm_not_chatbot_dashboard",
            "Mission Control is a helm, not a chatbot or backend dashboard",
            "known_and_tracked",
            "Mission Control should be an operator-first command surface with calm orientation, exact state, proof below the surface, and no generic dashboard or chatbot posture.",
            (
                "Operator/01_NORTH_STAR_AND_TASTE.md",
                "Operator/05_ORIENTATION_CONTRACT.md",
                "docs/planning/launch_ladder/13_MAC_DESKTOP_FIRST_SCREEN_COMPOSITION_SPEC.md",
                "docs/planning/launch_ladder/14_MAC_DESKTOP_TASTE_AND_ATMOSPHERE_SPEC.md",
                "generated/read_models/operator_mission_priority_helm_declutter.json",
            ),
            "HIGH_TRUST_SOURCE_BACKED",
            "This prevents Mission Control from becoming a backend table browser or generic assistant panel while the helm is being finished.",
            _affects("helm_front_door", "visual_design", "operator_controls", "steel_thread"),
            "The Mac UI still needs a finish pass that renders this calmly rather than exposing every read-model equally.",
            "Use this inventory with the helm declutter taxonomy before the next Mac UI finish lane.",
            "Do not turn this theme into UI code, branding, mascots, or a new app name in this lane.",
        ),
        ThemeSpec(
            "operator_system_above_workbenches",
            "OpenClaw is the Operator System above workbenches",
            "known_and_tracked",
            "OpenClaw should sit above macOS, Windows, WSL, VS Code, Codex, Antigravity, Xcode, Terminal, files, apps, and future tools as a deterministic operator system.",
            (
                "generated/read_models/operator_workbench_actor_host_registry.json",
                "generated/read_models/package_compiler_contract.json",
                "generated/read_models/operator_mission_priority_helm_declutter.json",
                "Operator/01_NORTH_STAR_AND_TASTE.md",
            ),
            "HIGH_TRUST_SOURCE_BACKED",
            "The operator should not need to manually understand every developer tool to route work safely.",
            _affects("helm_front_door", "actor_router", "package_compiler", "operator_controls"),
            "Future launch and monitoring authority remains gated; the current truth is registry/package metadata only.",
            "Keep workbench routing metadata visible in package previews and keep launch authority future-gated.",
            "Do not wire live Codex, Antigravity, VS Code, terminal, browser, or account sessions from this inventory.",
        ),
        ThemeSpec(
            "calm_command_surface_studio_console_cockpit",
            "Calm command surface, studio console, and cockpit taste",
            "known_and_tracked",
            "Approved Repo A sources describe a calm cockpit, personal command desk, trusted command surface, studio console, chart table, and evidence drawer.",
            (
                "docs/planning/launch_ladder/13_MAC_DESKTOP_FIRST_SCREEN_COMPOSITION_SPEC.md",
                "docs/planning/launch_ladder/14_MAC_DESKTOP_TASTE_AND_ATMOSPHERE_SPEC.md",
                "Operator/01_NORTH_STAR_AND_TASTE.md",
            ),
            "HIGH_TRUST_SOURCE_BACKED",
            "This is the strongest source-backed taste constraint for the Mac UI finish sprint.",
            _affects("helm_front_door", "visual_design", "operator_controls"),
            "The more specific Doom Eternal or space-station metaphor is not yet sourced in approved Repo A docs.",
            "Use source-backed cockpit/studio-console language now and ask Winship for the missing metaphor source if needed.",
            "Do not literalize knobs, faders, spaceship panels, or game UI chrome without a later UI design lane.",
        ),
        ThemeSpec(
            "developer_mode_to_quiet_operational_helm",
            "Developer Mode now, quiet operational helm later",
            "known_and_tracked",
            "Current Mission Control is in Developer Mode / Build Mode while OpenClaw is being assembled; the target is a quieter operational helm.",
            (
                "generated/read_models/operator_mission_priority_helm_declutter.json",
                "generated/read_models/operator_nested_lane_mission_package_spine.json",
            ),
            "HIGH_TRUST_SOURCE_BACKED",
            "This explains why the helm is noisy now and what should make it quiet later.",
            _affects("helm_front_door", "check_lights", "steel_thread", "operator_controls"),
            "Quiet-mode switching is not a UI implementation yet.",
            "Use mission priority and steel-thread registries to collapse backend detail before adding more cards.",
            "Do not hide check-engine or transmission proof while they still affect operator trust.",
        ),
        ThemeSpec(
            "worlds_are_domain_destinations",
            "Worlds are domain destinations, not helm clutter",
            "known_and_tracked",
            "Music/Art, Finance, Operations, Security, Build, Research, Communications, and Business Development are tracked as worlds that the operator can enter after the helm is calm.",
            (
                "generated/read_models/world_domain_registry.json",
                "Operator/GENERATED_CURRENT_STATE.md",
                "generated/read_models/operator_mission_priority_helm_declutter.json",
            ),
            "HIGH_TRUST_SOURCE_BACKED",
            "This keeps normal domain work from cluttering the front-door helm unless it affects the current mission or needs attention.",
            _affects("worlds", "helm_front_door", "operator_controls"),
            "Future worlds such as Gardening are operator-mentioned but not yet tracked in the world registry.",
            "Promote future worlds through the world/domain registry only after a bounded source-backed lane.",
            "Do not render all domain detail as equal helm cards.",
        ),
        ThemeSpec(
            "check_lights_are_distinct_from_lanes",
            "Check lights are distinct from normal lanes",
            "known_and_tracked",
            "System health lights are for system/workbench/tooling/resource/authority/confidence conditions, not ordinary domain attention.",
            (
                "generated/read_models/system_health_lights_taxonomy.json",
                "generated/read_models/operator_mission_priority_helm_declutter.json",
            ),
            "HIGH_TRUST_SOURCE_BACKED",
            "This prevents resource, bridge, and authority posture from being confused with normal world/domain work.",
            _affects("check_lights", "helm_front_door", "steel_thread", "operator_controls"),
            "Mac UI should still decide visual hierarchy, but backend taxonomy is in place.",
            "Keep check lights semantically separate and open the steel-thread lane when inspected.",
            "Do not create a permanent status wall or dramatic alarm cluster.",
        ),
        ThemeSpec(
            "steel_thread_everywhere",
            "Steel thread everywhere: orient, prove, package",
            "known_and_tracked",
            "Every lane, check light, and world should follow operator orientation, machine contract/proof, and package/detour/fix path.",
            (
                "generated/read_models/steel_thread_lane_template_registry.json",
                "generated/read_models/package_compiler_contract.json",
                "generated/read_models/operator_awareness_agent_package_spine.json",
                "generated/read_models/operator_nested_lane_mission_package_spine.json",
            ),
            "HIGH_TRUST_SOURCE_BACKED",
            "The Mac app can render one reusable workflow pattern instead of inventing a separate pattern per lane.",
            _affects("steel_thread", "package_compiler", "operator_controls", "helm_front_door"),
            "Implementation of the Mac steel-thread surface remains a later app lane.",
            "Use the template registry and package compiler contract as source truth for future surface work.",
            "Do not add live execution or state mutation buttons under the steel-thread labels.",
        ),
        ThemeSpec(
            "confidence_detour_quiets_when_deterministic",
            "Confidence and detour UI quiets when proof is deterministic",
            "known_and_tracked",
            "Confidence is visible when proof/context is missing and quiet when deterministic trust is reached; failure reopens detours.",
            (
                "generated/read_models/steel_thread_lane_template_registry.json",
                "generated/read_models/package_compiler_contract.json",
                "generated/read_models/operator_awareness_agent_package_spine.json",
            ),
            "HIGH_TRUST_SOURCE_BACKED",
            "This avoids confidence theater and keeps the helm calm when nothing needs operator attention.",
            _affects("steel_thread", "package_compiler", "operator_controls", "helm_front_door"),
            "The UI still needs to apply this rule without hiding real gaps.",
            "Render missing inputs and detours only when they materially affect action.",
            "Do not show fake numeric certainty or dramatize deterministic proof.",
        ),
        ThemeSpec(
            "proof_below_operator_layer",
            "Proof belongs under operator orientation",
            "known_and_tracked",
            "Machine proof, receipts, manifests, markers, long paths, and raw generated detail should sit in drawers or drill-downs below the human orientation layer.",
            (
                "docs/planning/launch_ladder/13_MAC_DESKTOP_FIRST_SCREEN_COMPOSITION_SPEC.md",
                "docs/planning/launch_ladder/14_MAC_DESKTOP_TASTE_AND_ATMOSPHERE_SPEC.md",
                "generated/read_models/operator_mission_priority_helm_declutter.json",
                "generated/read_models/steel_thread_lane_template_registry.json",
            ),
            "HIGH_TRUST_SOURCE_BACKED",
            "This preserves trust without making the front door feel like a backend inventory.",
            _affects("helm_front_door", "visual_design", "steel_thread", "operator_controls"),
            "The exact Mac proof drawer design remains a UI lane.",
            "Keep proof visible on demand and summarize proof status above the fold.",
            "Do not hide proof so deeply that status claims become unverifiable.",
        ),
        ThemeSpec(
            "operator_controls_preview_before_authority",
            "Controls explain, inspect, preview, park, or route before authority exists",
            "known_and_tracked",
            "Current controls should orient the operator, show proof, preview packages, collect missing-memory posture, raise confidence, or keep work parked; live launch remains future-gated.",
            (
                "generated/read_models/steel_thread_lane_template_registry.json",
                "generated/read_models/package_compiler_contract.json",
                "docs/planning/launch_ladder/12_MAC_DESKTOP_MISSION_CONTROL_FIXTURE_CONTRACT.md",
            ),
            "HIGH_TRUST_SOURCE_BACKED",
            "Buttons must not smuggle execution, send, approval, account access, or model/tool calls into a display surface.",
            _affects("operator_controls", "package_compiler", "steel_thread", "helm_front_door"),
            "Future write/capture behavior needs explicit receipt and authority gates.",
            "Render preview-only controls and future targets without dispatch.",
            "Do not build live launch buttons from this inventory.",
        ),
        ThemeSpec(
            "taste_quality_anti_slop",
            "Taste quality and anti-slop rules are tracked",
            "known_and_tracked",
            "Repo A sources define local-first durable quality, human feeling, daily-use calm, and anti-vibe tests against Jira cosplay, AI orb centerpiece, startup dashboard, wall of chips, and agent theater.",
            (
                "Operator/01_NORTH_STAR_AND_TASTE.md",
                "docs/planning/launch_ladder/14_MAC_DESKTOP_TASTE_AND_ATMOSPHERE_SPEC.md",
            ),
            "HIGH_TRUST_SOURCE_BACKED",
            "This gives future Mac implementation lanes a taste guardrail beyond correctness.",
            _affects("visual_design", "helm_front_door", "operator_controls"),
            "Taste tests are source-backed, but there is not yet a final visual system implementation.",
            "Use vibe and anti-vibe tests as static review criteria for the Mac finish sprint.",
            "Do not create branding, mascot, slogan, logo, or fake product-name energy.",
        ),
        ThemeSpec(
            "quiet_feedback_sound_haptics_future_only",
            "Sound and haptics are quiet, optional, and future-only",
            "known_and_tracked",
            "Sound should be off by default, optional, tied to visible state transitions, and never used as hidden-agent or urgency theater.",
            (
                "docs/planning/launch_ladder/15_MAC_DESKTOP_SOUND_HAPTICS_QUIET_FEEDBACK_ADDENDUM.md",
            ),
            "HIGH_TRUST_SOURCE_BACKED",
            "This prevents atmosphere work from becoming notification spam or fake AI activity.",
            _affects("visual_design", "operator_controls"),
            "No sound assets, haptics, settings UI, or app code are authorized here.",
            "Carry this as future design guidance only.",
            "Do not build sound, haptics, notification behavior, or audio assets from this inventory.",
        ),
        ThemeSpec(
            "spaceship_doom_space_station_reference_needs_source",
            "Spaceship helm / Doom Eternal space-station reference needs source comparison",
            "needs_winship_memory_comparison",
            "The current operator prompt mentions spaceship helm and Doom Eternal-style space station, while approved Repo A sources found in this lane show cockpit, command desk, studio console, chart table, and evidence drawer.",
            (
                "operator_prompt: Mission Control Design Memory Inventory v0",
                "docs/planning/launch_ladder/13_MAC_DESKTOP_FIRST_SCREEN_COMPOSITION_SPEC.md",
                "docs/planning/launch_ladder/14_MAC_DESKTOP_TASTE_AND_ATMOSPHERE_SPEC.md",
            ),
            "MEDIUM_TRUST_PARTLY_SOURCE_BACKED",
            "This may be important for the visual finish sprint, but the exact game/base metaphor should not be overfit without the source artifact.",
            _affects("visual_design", "helm_front_door", "worlds"),
            "No approved Repo A source found for Doom, Doom Eternal, or space station wording in the narrow search set.",
            "Ask Winship to point to the source chat/file or promote a bounded source-backed design note.",
            "Do not build a game-like or sci-fi visual system solely from memory of the phrase.",
        ),
        ThemeSpec(
            "software_likes_dislikes_inventory_missing",
            "Specific software likes/dislikes inventory is missing",
            "needs_winship_memory_comparison",
            "Repo A contains taste and anti-vibe tests, but this lane did not find a specific inventory of Winship's software likes, dislikes, or video-game reference discussions.",
            (
                "operator_prompt: Mission Control Design Memory Inventory v0",
                "docs/planning/launch_ladder/14_MAC_DESKTOP_TASTE_AND_ATMOSPHERE_SPEC.md",
            ),
            "LOW_TRUST_SOURCE_MISSING",
            "Specific taste references could sharpen the Mac finish pass, but they need bounded source evidence.",
            _affects("visual_design", "operator_controls", "helm_front_door"),
            "The approved source set does not contain a dedicated software-likes/dislikes record.",
            "Winship can point OpenClaw at an approved artifact or request a small capture lane.",
            "Do not infer personal taste from broad private history or unsourced memory.",
        ),
        ThemeSpec(
            "gardening_future_world_not_registered",
            "Gardening future world is not registered yet",
            "known_unknown",
            "The current operator prompt mentions possible future domains like Gardening, but the current world registry tracks eight worlds and does not include Gardening.",
            (
                "operator_prompt: Mission Control Design Memory Inventory v0",
                "generated/read_models/world_domain_registry.json",
                "Operator/GENERATED_CURRENT_STATE.md",
            ),
            "MEDIUM_TRUST_PARTLY_SOURCE_BACKED",
            "Future worlds should be promoted deliberately so the helm does not become cluttered.",
            _affects("worlds", "helm_front_door"),
            "Gardening is operator-mentioned but not a current registered world.",
            "Treat Gardening as a future domain candidate until a world/domain registry lane promotes it.",
            "Do not add new world UI entries without a registry update and source-backed purpose.",
        ),
        ThemeSpec(
            "strategic_gravity_glow_heat_partly_tracked",
            "Strategic gravity, glow, heat, and flags are partly tracked",
            "partly_known",
            "The world registry includes signal vocabulary such as quiet, flagged, glowing, hot, and critical consequence, but dynamic world status and strategic gravity are not implemented.",
            (
                "generated/read_models/world_domain_registry.json",
                "Operator/GENERATED_CURRENT_STATE.md",
            ),
            "MEDIUM_TRUST_PARTLY_SOURCE_BACKED",
            "This affects how worlds can show attention without cluttering the helm.",
            _affects("worlds", "helm_front_door", "visual_design"),
            "Dynamic world status, strategic gravity, agent presence, and live attention are explicitly not implemented yet.",
            "Create a later deterministic world-status/evidence-freshness lane before dynamic visual heat.",
            "Do not fake live world heat, glow, or attention signals.",
        ),
        ThemeSpec(
            "visual_reference_board_not_yet_discovered",
            "Concrete visual reference board is not yet discovered",
            "not_yet_discovered",
            "Repo A has strong taste vocabulary and anti-vibe tests, but this lane did not find a bounded visual reference board, selected screenshots, or approved artifact set for the final spaceship/studio-console/world-map feel.",
            (
                "operator_prompt: Mission Control Design Memory Inventory v0",
                "docs/planning/launch_ladder/14_MAC_DESKTOP_TASTE_AND_ATMOSPHERE_SPEC.md",
            ),
            "LOW_TRUST_SOURCE_MISSING",
            "A bounded reference board could help the Mac finish sprint avoid generic cards while still staying calm and operator-first.",
            _affects("visual_design", "helm_front_door", "worlds"),
            "No approved Repo A artifact found for concrete visual references beyond prose taste constraints.",
            "Ask Winship for a small approved reference artifact or create a source-backed design-memory capture packet later.",
            "Do not scrape images, browse, ingest screenshots, or build a visual system from unsourced memories in this lane.",
        ),
        ThemeSpec(
            "design_memory_future_sqlite_promotion",
            "Design doctrine should be promoted into SQLite/read-model tracking carefully",
            "candidate_future_sqlite_promotion",
            "This inventory identifies bounded design doctrine summaries and source refs that could later be promoted as metadata-only SQLite facts or receipts.",
            (
                "business_ops_ledger.py",
                "operator_prompt: Mission Control Design Memory Inventory v0",
            ),
            "MEDIUM_TRUST_PARTLY_SOURCE_BACKED",
            "Durable tracking lets future app lanes use design doctrine without re-reading broad old conversations.",
            _affects("helm_front_door", "visual_design", "operator_controls", "steel_thread"),
            "Only a metadata receipt is safe in this lane; a canonical design-memory fact schema remains future work.",
            "Use existing metadata-only receipt pattern now and design a narrow promotion lane later if needed.",
            "Do not store raw private chat bodies, broad file dumps, or unsourced claims as canonical facts.",
        ),
        ThemeSpec(
            "broad_private_design_archive_ingestion_blocked",
            "Broad private design archive ingestion is blocked",
            "blocked_or_not_authorized",
            "This lane may search only narrow approved Repo A sources; broad chat history, raw private files, credentials, logs, and unapproved archives are not authorized.",
            (
                "operator_prompt: Mission Control Design Memory Inventory v0",
                "OPENCLAW_RUNTIME.md",
            ),
            "FULL_TRUST_DISPLAY_QUIET",
            "This protects privacy and prevents the design inventory from becoming an uncontrolled ingestion lane.",
            _affects("operator_controls", "steel_thread", "package_compiler"),
            "Missing memories must be represented as missing until Winship provides an approved source.",
            "Keep missing design memories as operator memory comparison needs.",
            "Do not scan broad private locations, ChatGPT history, browser data, account surfaces, or raw business archives.",
        ),
        ThemeSpec(
            "next_safe_sources_for_design_memory",
            "Safe next sources to inspect are bounded and operator-approved",
            "safe_next_source_to_inspect",
            "The next safe source lane should ask for specific approved artifacts, such as a design note, a selected prior chat export placed in Repo A, or a narrow world/taste source file.",
            (
                "operator_prompt: Mission Control Design Memory Inventory v0",
                "generated/read_models/package_compiler_contract.json",
            ),
            "MEDIUM_TRUST_PARTLY_SOURCE_BACKED",
            "This gives OpenClaw a way to raise design confidence without broad private ingestion.",
            _affects("package_compiler", "steel_thread", "operator_controls", "visual_design"),
            "The actual missing artifacts have not been supplied in this lane.",
            "Prepare a Design Memory Source Capture Packet that is preview-only and metadata-first.",
            "Do not create a generic RAG search box or chat-with-files ingestion path.",
        ),
    )


def _theme_record(spec: ThemeSpec) -> dict[str, Any]:
    return {
        "theme_id": spec.theme_id,
        "title": spec.title,
        "classification": spec.classification,
        "summary": spec.summary,
        "source_refs": list(spec.source_refs),
        "confidence": spec.confidence,
        "why_it_matters": spec.why_it_matters,
        "affects": {key: key in spec.affects for key in AFFECTS_KEYS},
        "current_gap": spec.current_gap,
        "safe_next_move": spec.safe_next_move,
        "what_not_to_build_from_this_yet": spec.what_not_to_build_from_this_yet,
        "operator_memory_is_not_treated_as_fact": spec.classification
        in {"needs_winship_memory_comparison", "known_unknown", "partly_known"},
        "raw_private_content_required": False,
        "runtime_authority_added": False,
    }


def _theme_records() -> list[dict[str, Any]]:
    return [_theme_record(spec) for spec in _theme_specs()]


def _classifications_summary(themes: list[dict[str, Any]]) -> dict[str, list[str]]:
    summary: dict[str, list[str]] = {classification: [] for classification in CLASSIFICATIONS}
    for theme in themes:
        summary.setdefault(theme["classification"], []).append(theme["theme_id"])
    return summary


def _source_state_summary(read_models: dict[str, dict[str, Any]], source_text: str) -> dict[str, Any]:
    terms = _source_terms_present(source_text)
    worlds = read_models.get("world_domain_registry", {})
    world_ids = [
        item.get("world_id")
        for item in worlds.get("worlds", [])
        if isinstance(item, dict) and item.get("world_id")
    ]
    return {
        "source_terms_present_in_bounded_docs": terms,
        "doom_or_space_station_reference_found": bool(terms["doom"] or terms["space_station"]),
        "software_likes_dislikes_reference_found": bool(terms["software_likes"] or terms["software_dislikes"]),
        "registered_world_ids": world_ids,
        "gardening_registered": "gardening" in world_ids,
        "read_model_availability": {
            key: bool(value)
            for key, value in read_models.items()
        },
    }


def _operator_memory_policy() -> dict[str, Any]:
    return {
        "winship_memory_can_flag_missing_design_doctrine": True,
        "operator_memory_is_not_canonical_truth_by_itself": True,
        "missing_memory_classification": "needs_winship_memory_comparison",
        "safe_capture_path": "bounded approved source artifact or metadata-only capture packet",
        "do_not_mark_unfound_sources_false": True,
        "do_not_infer_taste_from_broad_private_history": True,
    }


def _recommended_mac_ui_guidance() -> list[dict[str, Any]]:
    return [
        {
            "guidance_id": "front_door_operator_first",
            "summary": "Render mode, system health, active mission, active parent lane, immediate focus, next safe move, and blocked/future-gated posture before raw proof.",
            "source_refs": [
                "generated/read_models/operator_mission_priority_helm_declutter.json",
                "docs/planning/launch_ladder/13_MAC_DESKTOP_FIRST_SCREEN_COMPOSITION_SPEC.md",
            ],
        },
        {
            "guidance_id": "proof_drawers_not_card_wall",
            "summary": "Keep manifests, receipts, long paths, and nested read-model detail in proof/detail drawers.",
            "source_refs": [
                "docs/planning/launch_ladder/13_MAC_DESKTOP_FIRST_SCREEN_COMPOSITION_SPEC.md",
                "generated/read_models/steel_thread_lane_template_registry.json",
            ],
        },
        {
            "guidance_id": "worlds_as_teleport_targets",
            "summary": "Show worlds as destinations with attention state, not as deep domain trees on the helm.",
            "source_refs": [
                "generated/read_models/world_domain_registry.json",
                "generated/read_models/operator_mission_priority_helm_declutter.json",
            ],
        },
        {
            "guidance_id": "check_lights_are_not_lanes",
            "summary": "Show check lights only when they matter; opening one should reveal the standard steel-thread lane.",
            "source_refs": [
                "generated/read_models/system_health_lights_taxonomy.json",
                "generated/read_models/steel_thread_lane_template_registry.json",
            ],
        },
        {
            "guidance_id": "source_missing_is_not_false",
            "summary": "When a remembered design discussion is not found, show a Winship memory comparison need rather than silently dropping or inventing it.",
            "source_refs": [
                "operator_prompt: Mission Control Design Memory Inventory v0",
            ],
        },
    ]


def _sqlite_receipt_contract(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "supported_by_existing_pattern": _rooted("business_ops_ledger.py", repo_root=ROOT).exists(),
        "pattern": "business_ops_ledger.record_receipt",
        "receipt_type": "generated_status",
        "sqlite_meaning": "receipt_record_only",
        "metadata_only": True,
        "stores_secrets": False,
        "stores_credentials": False,
        "stores_raw_private_file_bodies": False,
        "stores_raw_private_chat_bodies": False,
        "stores_raw_logs": False,
        "stores_broad_file_dumps": False,
        "stores_runtime_activation": False,
        "receipt_writer_function": "record_mission_control_design_memory_inventory_receipt",
        "inventory_hash": payload["inventory_hash"],
    }


def build_mission_control_design_memory_inventory(
    *,
    repo_root: str | Path = ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    read_models = {
        source.key: _read_json_if_present(source.path, repo_root=repo_root)
        for source in SOURCE_READ_MODELS
    }
    source_text = _combined_source_text(repo_root=repo_root)
    themes = _theme_records()
    inventory_hash = _hash_payload(
        {
            "schema_version": SCHEMA_VERSION,
            "themes": [
                {
                    "theme_id": theme["theme_id"],
                    "classification": theme["classification"],
                    "source_refs": theme["source_refs"],
                    "confidence": theme["confidence"],
                }
                for theme in themes
            ],
        }
    )
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": "mission_control_design_memory_inventory",
        "generated_by": "codex",
        "generated_at": generated_at or utc_now(),
        "lane": "Mission Control Design Memory Inventory v0",
        "contract_status": "deterministic_metadata_only_design_memory_inventory",
        "purpose": "Classify source-backed Mission Control design doctrine, taste constraints, known unknowns, missing source artifacts, and safe next memory-comparison moves.",
        "inventory_scope": {
            "approved_source_scope": "narrow Repo A source docs and existing generated read-models only",
            "broad_private_chat_ingested": False,
            "chatgpt_history_ingested": False,
            "raw_private_file_bodies_stored": False,
            "source_bodies_exported": False,
            "operator_memory_comparison_supported": True,
            "operator_memory_treated_as_truth": False,
        },
        "classification_vocab": list(CLASSIFICATIONS),
        "affects_vocab": list(AFFECTS_KEYS),
        "confidence_vocab": list(CONFIDENCE_STATES),
        "themes": themes,
        "theme_count": len(themes),
        "classifications_summary": _classifications_summary(themes),
        "operator_memory_policy": _operator_memory_policy(),
        "source_state_summary": _source_state_summary(read_models, source_text),
        "source_refs": {
            "source_docs": [
                _source_doc_record(source, repo_root=repo_root)
                for source in SOURCE_DOCS
            ],
            "source_read_models": [
                _source_read_model_record(source, repo_root=repo_root, payload=read_models[source.key])
                for source in SOURCE_READ_MODELS
            ],
            "doctrine_source_labels": list(DOCTRINE_SOURCE_LABELS),
        },
        "candidate_future_sqlite_promotions": [
            {
                "promotion_id": "mission_control_design_doctrine_fact_set",
                "summary": "Promote bounded design doctrine summaries and source refs into canonical facts after a dedicated schema lane.",
                "allowed_payload": "metadata, summaries, source paths, hashes, classification, confidence posture",
                "forbidden_payload": "raw private chat bodies, raw private files, credentials, broad logs, unsourced claims",
                "status": "future_gated",
            },
            {
                "promotion_id": "winship_taste_reference_index",
                "summary": "Capture a small operator-approved index of software/game/taste references if Winship supplies source artifacts.",
                "allowed_payload": "reference labels, source refs, operator-visible summaries, missing-source flags",
                "forbidden_payload": "raw broad chat exports, private account data, raw history ingestion",
                "status": "needs_winship_memory_comparison",
            },
        ],
        "recommended_mac_ui_guidance": _recommended_mac_ui_guidance(),
        "what_should_guide_next_mac_ui_finish_pass": [
            "helm not dashboard/chatbot/backend inventory",
            "current mission and system health first",
            "active parent lane, immediate focus, and next safe move above proof",
            "worlds as destinations, not deep helm clutter",
            "check lights distinct from normal lanes",
            "steel-thread drill-in everywhere",
            "proof/package/confidence lower than operator orientation",
            "no confidence theater when deterministic",
            "source-missing memories become comparison needs, not facts",
        ],
        "what_should_not_be_built_yet": [
            "live UI controls from this backend inventory",
            "brand, mascot, app name, or slogan",
            "generic RAG search or chat-with-files default",
            "broad private design archive ingestion",
            "sound/haptics/assets/notifications",
            "live workbench, model, agent, browser, account, send, submit, approval, or runtime integration",
            "fake live world heat, glow, strategic gravity, or attention signals",
        ],
        "safe_next_lane": {
            "lane_id": "mission_control_design_memory_source_capture_packet",
            "title": "Mission Control Design Memory Source Capture Packet",
            "purpose": "Ask Winship for a bounded approved source artifact for missing Doom/software/video-game/taste references, then classify it without broad ingestion.",
            "current_availability": "preview_only_future_gated",
            "allowed_now": "operator guidance and metadata-only package preview",
            "not_allowed_now": list(FORBIDDEN_ACTIONS),
        },
        "machine_proof": {
            "generated_outputs": [
                f"generated/read_models/{JSON_EXPORT_NAME}",
                f"generated/read_models/{OPERATOR_EXPORT_NAME}",
            ],
            "source_docs_present": {
                source.key: _rooted(source.path, repo_root=repo_root).exists()
                for source in SOURCE_DOCS
            },
            "source_read_models_present": {
                key: bool(value)
                for key, value in read_models.items()
            },
            "ledger_pattern_present": _rooted("business_ops_ledger.py", repo_root=repo_root).exists(),
            "runtime_or_live_authority_added": False,
        },
        "inventory_hash": inventory_hash,
        "sqlite_ledger_receipt_contract": {},
        "no_live_authority_statement": "This inventory records design doctrine metadata and gaps only; it does not implement UI, ingest broad private archives, call models, launch agents, mutate Mac app files, run workbenches, or grant runtime authority.",
        "no_authority_flags": dict(NO_AUTHORITY_FLAGS),
        **NO_AUTHORITY_FLAGS,
    }
    payload["sqlite_ledger_receipt_contract"] = _sqlite_receipt_contract(payload)
    return payload


def format_mission_control_design_memory_inventory(payload: dict[str, Any]) -> str:
    summary = payload["classifications_summary"]
    source_state = payload["source_state_summary"]
    lines = [
        "# Mission Control Design Memory Inventory v0",
        "",
        "Status:",
        "- Deterministic metadata-only design memory inventory.",
        "- Narrow approved Repo A sources only; no broad private chat ingestion or UI implementation.",
        "",
        "## Already Captured",
    ]
    for theme_id in summary["known_and_tracked"]:
        theme = next(item for item in payload["themes"] if item["theme_id"] == theme_id)
        lines.append(f"- `{theme_id}`: {theme['title']}.")
    lines.extend(
        [
            "",
            "## Partly Captured",
        ]
    )
    for bucket in ("partly_known", "known_unknown", "needs_winship_memory_comparison"):
        for theme_id in summary[bucket]:
            theme = next(item for item in payload["themes"] if item["theme_id"] == theme_id)
            lines.append(f"- `{theme_id}` ({bucket}): {theme['current_gap']}")
    lines.extend(
        [
            "",
            "## Missing / Memory Comparison",
            f"- Doom or space-station source found in bounded docs: `{str(source_state['doom_or_space_station_reference_found']).lower()}`.",
            f"- Software likes/dislikes source found in bounded docs: `{str(source_state['software_likes_dislikes_reference_found']).lower()}`.",
            f"- Gardening registered as a current world: `{str(source_state['gardening_registered']).lower()}`.",
            "- Missing memories should become Winship memory comparison needs, not facts.",
            "",
            "## Future SQLite Promotions",
        ]
    )
    for promotion in payload["candidate_future_sqlite_promotions"]:
        lines.append(f"- `{promotion['promotion_id']}`: {promotion['summary']} Status: `{promotion['status']}`.")
    lines.extend(
        [
            "",
            "## Mac UI Finish Guidance",
        ]
    )
    for item in payload["recommended_mac_ui_guidance"]:
        lines.append(f"- `{item['guidance_id']}`: {item['summary']}")
    lines.extend(
        [
            "",
            "## What Should Not Be Built Yet",
        ]
    )
    for item in payload["what_should_not_be_built_yet"]:
        lines.append(f"- {item}.")
    lines.extend(
        [
            "",
            "## Source Bounds",
            "- Approved source scope: narrow Repo A source docs and existing generated read-models.",
            "- Raw source bodies exported: `false`.",
            "- Broad private chat ingested: `false`.",
            "- Operator memory treated as canonical truth: `false`.",
            "",
            "## Next Safe Lane",
            f"- `{payload['safe_next_lane']['lane_id']}`: {payload['safe_next_lane']['purpose']}",
            "",
        ]
    )
    return "\n".join(lines)


def export_mission_control_design_memory_inventory(
    *,
    repo_root: str | Path = ROOT,
    export_root: str | Path = DEFAULT_EXPORT_ROOT,
    generated_at: str | None = None,
) -> MissionControlDesignMemoryInventoryExportResult:
    root = Path(repo_root)
    out_dir = _rooted(export_root, repo_root=root)
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = build_mission_control_design_memory_inventory(repo_root=root, generated_at=generated_at)
    json_path = out_dir / JSON_EXPORT_NAME
    operator_path = out_dir / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(format_mission_control_design_memory_inventory(payload), encoding="utf-8")
    return MissionControlDesignMemoryInventoryExportResult(
        schema_version=SCHEMA_VERSION,
        json_path=_display_path(json_path),
        operator_path=_display_path(operator_path),
        theme_count=payload["theme_count"],
        sqlite_receipt_supported=payload["sqlite_ledger_receipt_contract"]["supported_by_existing_pattern"],
        broad_private_chat_ingested=payload["broad_private_chat_ingested"],
        c_drive_artifact_written=payload["c_drive_artifact_written"],
        runtime_authority_added=payload["runtime_authority_added"],
    )


def _load_existing_receipt_payloads(db_path: str | Path | None = None) -> list[dict[str, Any]]:
    path = Path(db_path or DEFAULT_DB_PATH)
    if not path.exists():
        return []
    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        try:
            rows = conn.execute(
                """
SELECT e.ts, p.packet_json_safe
FROM events e
JOIN packets p ON p.event_id = e.event_id
WHERE e.event_type = 'generated_status'
ORDER BY e.ts DESC
LIMIT 500
""".strip()
            ).fetchall()
        finally:
            conn.close()
    except sqlite3.Error:
        return []
    payloads: list[dict[str, Any]] = []
    for ts, packet_json_safe in rows:
        try:
            packet = json.loads(packet_json_safe or "{}")
        except json.JSONDecodeError:
            continue
        packet["_event_ts"] = ts
        payloads.append(packet)
    return payloads


def _find_existing_mission_control_design_memory_inventory_receipt(
    *,
    inventory_hash: str,
    commit_hash: str | None,
    db_path: str | Path | None = None,
) -> dict[str, Any] | None:
    for packet in _load_existing_receipt_payloads(db_path):
        payload_json = packet.get("payload_json")
        if not isinstance(payload_json, dict):
            continue
        if payload_json.get("contract_id") != SCHEMA_VERSION:
            continue
        if payload_json.get("inventory_hash") != inventory_hash:
            continue
        if commit_hash and packet.get("commit_hash") != commit_hash:
            continue
        return packet
    return None


def record_mission_control_design_memory_inventory_receipt(
    *,
    repo_root: str | Path = ROOT,
    db_path: str | Path | None = None,
    commit_hash: str | None = None,
    generated_at: str | None = None,
    ensure: bool = True,
) -> str:
    payload = build_mission_control_design_memory_inventory(repo_root=repo_root, generated_at=generated_at)
    inventory_hash = payload["inventory_hash"]
    if ensure:
        existing = _find_existing_mission_control_design_memory_inventory_receipt(
            inventory_hash=inventory_hash,
            commit_hash=commit_hash,
            db_path=db_path,
        )
        if existing:
            return str(existing.get("receipt_id") or existing.get("packet_id") or "")

    init_business_ops_ledger(str(db_path) if db_path else None)
    receipt_payload = {
        "contract_id": SCHEMA_VERSION,
        "inventory_hash": inventory_hash,
        "generated_read_model_paths": [
            f"generated/read_models/{JSON_EXPORT_NAME}",
            f"generated/read_models/{OPERATOR_EXPORT_NAME}",
        ],
        "theme_count": payload["theme_count"],
        "classification_vocab": list(CLASSIFICATIONS),
        "source_doc_keys": [source.key for source in SOURCE_DOCS],
        "source_read_model_keys": [source.key for source in SOURCE_READ_MODELS],
        "doctrine_source_labels": list(DOCTRINE_SOURCE_LABELS),
        "metadata_only": True,
        "source_bodies_stored": False,
        "raw_private_chat_bodies_stored": False,
        "raw_private_file_bodies_stored": False,
        "raw_logs_stored": False,
        "broad_file_dumps_stored": False,
        "credentials_stored": False,
        "secrets_stored": False,
        "c_drive_artifact_written": False,
        "runtime_activation": False,
        "authority_flags": dict(NO_AUTHORITY_FLAGS),
    }
    return record_receipt(
        receipt_type="generated_status",
        payload=receipt_payload,
        commit_hash=commit_hash,
        artifact_type="mission_control_design_memory_inventory",
        artifact_status="captured_metadata_only",
        authority_status="generated_status_only",
        runtime_activation=False,
        sqlite_meaning="receipt_record_only",
        source_basis=list(DOCTRINE_SOURCE_LABELS),
        actor="mission_control_design_memory_inventory_v0",
        created_at=generated_at,
        db_path=str(db_path) if db_path else None,
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export Mission Control Design Memory Inventory read-model.")
    parser.add_argument("--repo-root", default=str(ROOT), help="Repo A root.")
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT), help="Generated read-model export root.")
    parser.add_argument("--format", choices=("json", "operator", "summary"), default="summary")
    parser.add_argument(
        "--record-receipt",
        action="store_true",
        help="Also record a metadata-only generated_status receipt in the existing ledger.",
    )
    parser.add_argument("--db", help="SQLite ledger path. Defaults to the Business Ops ledger.")
    parser.add_argument("--commit-hash", help="Optional commit hash to bind to the metadata receipt.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    result = export_mission_control_design_memory_inventory(
        repo_root=args.repo_root,
        export_root=args.export_root,
    )
    receipt_id = ""
    if args.record_receipt:
        receipt_id = record_mission_control_design_memory_inventory_receipt(
            repo_root=args.repo_root,
            db_path=args.db,
            commit_hash=args.commit_hash,
            ensure=True,
        )

    root = _rooted(args.export_root, repo_root=args.repo_root)
    if args.format == "json":
        print((root / JSON_EXPORT_NAME).read_text(encoding="utf-8"), end="")
    elif args.format == "operator":
        print((root / OPERATOR_EXPORT_NAME).read_text(encoding="utf-8"), end="")
    else:
        summary = result.__dict__.copy()
        if args.record_receipt:
            summary["sqlite_receipt_id"] = receipt_id
            summary["sqlite_receipt_recorded"] = bool(receipt_id)
        print(stable_json(summary), end="")
    return 0 if result.schema_version == SCHEMA_VERSION and (not args.record_receipt or receipt_id) else 1


__all__ = [
    "AFFECTS_KEYS",
    "CLASSIFICATIONS",
    "CONFIDENCE_STATES",
    "JSON_EXPORT_NAME",
    "NO_AUTHORITY_FLAGS",
    "OPERATOR_EXPORT_NAME",
    "SCHEMA_VERSION",
    "build_mission_control_design_memory_inventory",
    "export_mission_control_design_memory_inventory",
    "format_mission_control_design_memory_inventory",
    "record_mission_control_design_memory_inventory_receipt",
    "stable_json",
]


if __name__ == "__main__":
    raise SystemExit(main())
