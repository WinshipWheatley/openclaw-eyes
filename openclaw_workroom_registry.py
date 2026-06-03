"""OpenClaw Workroom Registry V0.

Defines local Slack-like workroom channel metadata for OpenClaw agents. This is
read-model and contract work only: it does not connect Slack or Telegram, send
messages, call live providers, mutate business state, export PDFs, submit
anything, mark paid, or push git state.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parent
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_BRIDGE_EXPORT_ROOT = Path("/mnt/e/openclaw/generated/read_models")
DEFAULT_WIKI_PATH = Path("generated/wiki/openclaw/OpenClaw Workroom Registry.md")

SCHEMA_VERSION = "openclaw_workroom_registry_v0"
READ_MODEL_ID = "openclaw_workroom_registry"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
REGISTRY_STATUS = "OPENCLAW_WORKROOM_REGISTRY_READY"

REQUIRED_CHANNEL_REFS = (
    "helm_daily_desk",
    "finance_st_annes",
    "finance_capital_hilton",
    "finance_live_arts_md",
    "business_development_capital_hilton",
    "build_mission_control_mac",
    "build_openclaw_backend",
    "creative_niles_studio",
    "security_guardian_gates",
    "architecture_hermes",
    "operations_chief_workboard",
)

COMMON_BLOCKED_ACTIONS = (
    "connect_slack_live",
    "connect_telegram_live",
    "send_slack_message",
    "send_telegram_message",
    "send_email",
    "open_gmail",
    "open_browser",
    "open_coupa",
    "mutate_ledger",
    "mutate_workbook",
    "export_pdf",
    "mark_paid",
    "submit_portal",
    "push_git",
    "run_live_provider",
    "call_external_llm",
    "launch_agent_loop",
    "spawn_worker_from_registry",
)

AUTHORITY_BOUNDARY = {
    "slack_connect_allowed": False,
    "telegram_live_connect_allowed": False,
    "message_send_allowed": False,
    "email_send_allowed": False,
    "gmail_allowed": False,
    "browser_access_allowed": False,
    "coupa_allowed": False,
    "portal_submit_allowed": False,
    "ledger_posting_allowed": False,
    "ledger_mutation_allowed": False,
    "workbook_mutation_allowed": False,
    "pdf_export_allowed": False,
    "paid_marking_allowed": False,
    "live_provider_allowed": False,
    "external_llm_allowed": False,
    "agent_loop_allowed": False,
    "git_push_allowed": False,
    "sent": False,
    "paid": False,
}

AGENT_MAPPING = (
    {
        "agent_ref": "cassandra",
        "display_name": "Cassandra",
        "scope": "finance work logs, correspondence, follow-ups",
        "allowed_output_scope": "internal finance status, work-log intake, correspondence preparation, follow-up staging",
        "blocked_output_scope": "send, submit, ledger mutation, paid marking, live provider access",
    },
    {
        "agent_ref": "chief",
        "display_name": "Chief",
        "scope": "diagnostics, build packets, provider gates",
        "allowed_output_scope": "diagnostics, package status, provider gate readbacks, build review packets",
        "blocked_output_scope": "repair execution without package gate, provider login, submit, send",
    },
    {
        "agent_ref": "hermes",
        "display_name": "Hermes",
        "scope": "architecture recommendations",
        "allowed_output_scope": "architecture recommendations, sequencing, tradeoff notes",
        "blocked_output_scope": "execution, approval, protected access, migration",
    },
    {
        "agent_ref": "guardian",
        "display_name": "Guardian",
        "scope": "protected action gates",
        "allowed_output_scope": "authority blocks, missing-proof readbacks, protected-store risk notes",
        "blocked_output_scope": "granting authority, using credentials, submitting, sending, ledger mutation",
    },
    {
        "agent_ref": "niles",
        "display_name": "Niles",
        "scope": "creative work",
        "allowed_output_scope": "creative review, studio notes, art/music direction, metadata review",
        "blocked_output_scope": "publishing, file mutation, finance or protected-action decisions",
    },
    {
        "agent_ref": "clara",
        "display_name": "Clara",
        "scope": "external draft artifacts only",
        "allowed_output_scope": "operator-reviewed client-facing draft artifacts",
        "blocked_output_scope": "sending drafts, exposing internal agent names, internal proof diagnostics",
    },
    {
        "agent_ref": "openclaw",
        "display_name": "OpenClaw",
        "scope": "neutral system status",
        "allowed_output_scope": "neutral cockpit status, read-model refs, plain status summaries",
        "blocked_output_scope": "speaker-specific diagnostics when another speaker owns the lane",
    },
    {
        "agent_ref": "pc_codex",
        "display_name": "PC_CODEX",
        "scope": "spawned worker outputs only",
        "allowed_output_scope": "local implementation or validation output packets already produced on PC",
        "blocked_output_scope": "spawning workers, live loops, external provider calls, direct business actions",
    },
    {
        "agent_ref": "mac_codex",
        "display_name": "MAC_CODEX",
        "scope": "spawned worker outputs only",
        "allowed_output_scope": "local implementation or validation output packets already produced on Mac",
        "blocked_output_scope": "spawning workers, live loops, external provider calls, direct business actions",
    },
)


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _rooted(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def _history_policy(channel_ref: str) -> dict[str, Any]:
    return {
        "mode": "local_read_model_thread_refs_only",
        "thread_storage_ref": f"future:generated/read_models/openclaw_workroom_threads/{channel_ref}.json",
        "raw_body_policy": "summaries_packet_ids_and_proof_refs_only",
        "proof_policy": "collapsed_by_default",
        "slack_import_allowed": False,
        "telegram_live_import_allowed": False,
        "retention_policy": "append_only_after_future_event_journal_contract_exists",
    }


def _operator_next_action_policy(channel_ref: str) -> dict[str, Any]:
    return {
        "mode": "operator_review_required",
        "channel_ref": channel_ref,
        "allowed_next_actions": [
            "read_status",
            "open_collapsed_proof",
            "request_local_package_review",
            "request_speaker_shaped_summary",
        ],
        "blocked_next_actions": list(COMMON_BLOCKED_ACTIONS),
        "approval_note": "This registry may describe workroom routing only. It cannot authorize execution or sends.",
    }


def _channel(
    *,
    channel_ref: str,
    display_name: str,
    world_ref: str,
    primary_agent: str,
    allowed_speakers: tuple[str, ...],
    allowed_package_types: tuple[str, ...],
    extra_blocked_actions: tuple[str, ...] = (),
) -> dict[str, Any]:
    blocked_actions = tuple(dict.fromkeys((*COMMON_BLOCKED_ACTIONS, *extra_blocked_actions)))
    return {
        "channel_ref": channel_ref,
        "display_name": display_name,
        "world_ref": world_ref,
        "thread_ref": f"workroom:{channel_ref}:main",
        "primary_agent": primary_agent,
        "allowed_speakers": list(allowed_speakers),
        "allowed_package_types": list(allowed_package_types),
        "blocked_actions": list(blocked_actions),
        "proof_collapsed_by_default": True,
        "history_policy": _history_policy(channel_ref),
        "operator_next_action_policy": _operator_next_action_policy(channel_ref),
    }


def build_channels() -> list[dict[str, Any]]:
    worker_speakers = ("pc_codex", "mac_codex")
    return [
        _channel(
            channel_ref="helm_daily_desk",
            display_name="Helm Daily Desk",
            world_ref="helm",
            primary_agent="openclaw",
            allowed_speakers=("openclaw", "chief", "cassandra", "hermes", "guardian", "niles", *worker_speakers),
            allowed_package_types=(
                "status_packet",
                "handoff_packet",
                "review_packet",
                "daily_desk_packet",
                "spawned_worker_output_packet",
            ),
        ),
        _channel(
            channel_ref="finance_st_annes",
            display_name="Finance - St. Anne's",
            world_ref="finance",
            primary_agent="cassandra",
            allowed_speakers=("cassandra", "chief", "guardian", "openclaw", *worker_speakers),
            allowed_package_types=(
                "work_log_status_packet",
                "correspondence_draft_packet",
                "finance_handoff_packet",
                "invoice_review_packet",
                "spawned_worker_output_packet",
            ),
            extra_blocked_actions=("mutate_st_annes_workbook", "create_invoice_from_workroom"),
        ),
        _channel(
            channel_ref="finance_capital_hilton",
            display_name="Finance - Capital Hilton",
            world_ref="finance",
            primary_agent="chief",
            allowed_speakers=("chief", "cassandra", "guardian", "openclaw", *worker_speakers),
            allowed_package_types=(
                "invoice_status_packet",
                "provider_gate_diagnostic_packet",
                "finance_handoff_packet",
                "review_packet",
                "spawned_worker_output_packet",
            ),
            extra_blocked_actions=("coupa_submit_from_workroom", "infer_paid_from_submit"),
        ),
        _channel(
            channel_ref="finance_live_arts_md",
            display_name="Finance - Live Arts MD",
            world_ref="finance",
            primary_agent="cassandra",
            allowed_speakers=("cassandra", "chief", "guardian", "openclaw", *worker_speakers),
            allowed_package_types=(
                "work_log_status_packet",
                "correspondence_draft_packet",
                "finance_handoff_packet",
                "review_packet",
                "spawned_worker_output_packet",
            ),
        ),
        _channel(
            channel_ref="business_development_capital_hilton",
            display_name="Business Development - Capital Hilton",
            world_ref="business_development",
            primary_agent="clara",
            allowed_speakers=("clara", "cassandra", "hermes", "guardian", "openclaw", *worker_speakers),
            allowed_package_types=(
                "proposal_status_packet",
                "external_draft_artifact_packet",
                "follow_up_draft_packet",
                "architecture_note_packet",
                "spawned_worker_output_packet",
            ),
            extra_blocked_actions=("send_client_draft", "claim_proposal_acceptance"),
        ),
        _channel(
            channel_ref="build_mission_control_mac",
            display_name="Build - Mission Control Mac",
            world_ref="build",
            primary_agent="chief",
            allowed_speakers=("chief", "hermes", "guardian", "openclaw", *worker_speakers),
            allowed_package_types=(
                "build_status_packet",
                "build_review_packet",
                "handoff_packet",
                "architecture_note_packet",
                "spawned_worker_output_packet",
            ),
        ),
        _channel(
            channel_ref="build_openclaw_backend",
            display_name="Build - OpenClaw Backend",
            world_ref="build",
            primary_agent="chief",
            allowed_speakers=("chief", "hermes", "guardian", "openclaw", *worker_speakers),
            allowed_package_types=(
                "build_status_packet",
                "build_review_packet",
                "diagnostic_packet",
                "architecture_note_packet",
                "spawned_worker_output_packet",
            ),
        ),
        _channel(
            channel_ref="creative_niles_studio",
            display_name="Creative - Niles Studio",
            world_ref="creative",
            primary_agent="niles",
            allowed_speakers=("niles", "openclaw", *worker_speakers),
            allowed_package_types=(
                "creative_review_packet",
                "studio_status_packet",
                "metadata_review_packet",
                "spawned_worker_output_packet",
            ),
            extra_blocked_actions=("publish_artifact", "mutate_creative_source_file"),
        ),
        _channel(
            channel_ref="security_guardian_gates",
            display_name="Security - Guardian Gates",
            world_ref="security",
            primary_agent="guardian",
            allowed_speakers=("guardian", "chief", "hermes", "openclaw", *worker_speakers),
            allowed_package_types=(
                "protected_gate_packet",
                "authority_review_packet",
                "risk_note_packet",
                "proof_review_packet",
                "spawned_worker_output_packet",
            ),
            extra_blocked_actions=("grant_authority_from_workroom", "read_secret_from_workroom"),
        ),
        _channel(
            channel_ref="architecture_hermes",
            display_name="Architecture - Hermes",
            world_ref="architecture",
            primary_agent="hermes",
            allowed_speakers=("hermes", "chief", "guardian", "openclaw", *worker_speakers),
            allowed_package_types=(
                "architecture_recommendation_packet",
                "doctrine_packet",
                "tradeoff_packet",
                "build_handoff_packet",
                "spawned_worker_output_packet",
            ),
            extra_blocked_actions=("migrate_from_workroom", "activate_runtime_from_workroom"),
        ),
        _channel(
            channel_ref="operations_chief_workboard",
            display_name="Operations - Chief Workboard",
            world_ref="operations",
            primary_agent="chief",
            allowed_speakers=("chief", "cassandra", "hermes", "guardian", "openclaw", *worker_speakers),
            allowed_package_types=(
                "operations_workboard_packet",
                "diagnostic_packet",
                "handoff_packet",
                "review_packet",
                "spawned_worker_output_packet",
            ),
        ),
    ]


def _speaker_package_matrix(channels: list[Mapping[str, Any]]) -> dict[str, dict[str, list[str]]]:
    matrix: dict[str, dict[str, set[str]]] = {}
    for channel in channels:
        for speaker in channel["allowed_speakers"]:
            entry = matrix.setdefault(str(speaker), {"channels": set(), "package_types": set()})
            entry["channels"].add(str(channel["channel_ref"]))
            entry["package_types"].update(str(item) for item in channel["allowed_package_types"])
    return {
        speaker: {
            "channels": sorted(values["channels"]),
            "package_types": sorted(values["package_types"]),
        }
        for speaker, values in sorted(matrix.items())
    }


def build_read_model(*, generated_at: str | None = None) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    channels = build_channels()
    channel_refs = tuple(channel["channel_ref"] for channel in channels)
    all_required_channels_present = set(channel_refs) == set(REQUIRED_CHANNEL_REFS)
    all_proof_collapsed = all(channel["proof_collapsed_by_default"] is True for channel in channels)
    all_block_live_surfaces = all(
        "connect_slack_live" in channel["blocked_actions"]
        and "connect_telegram_live" in channel["blocked_actions"]
        and "send_slack_message" in channel["blocked_actions"]
        and "send_telegram_message" in channel["blocked_actions"]
        for channel in channels
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "generated_at": generated_at,
        "status": REGISTRY_STATUS,
        "purpose": "Local channel-like workroom registry for agent status, handoffs, and review packets.",
        "mode": "local_read_model_contract_only_no_live_slack",
        "channel_count": len(channels),
        "required_channel_refs": list(REQUIRED_CHANNEL_REFS),
        "channels": channels,
        "agent_mapping": list(AGENT_MAPPING),
        "speaker_package_matrix": _speaker_package_matrix(channels),
        "operator_display_defaults": {
            "proof_collapsed_by_default": True,
            "plain_summary_first": True,
            "show_machine_details_by_default": False,
            "raw_rows_by_default": False,
        },
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "source_refs": [
            "agent_voice_profiles.py",
            "agent_voice_router.py",
            "workflow_package_queue.py",
            "generated/read_models/agent_voice_profiles.json",
            "generated/read_models/agent_voice_routing_contract.json",
            "generated/read_models/workflow_package_queue_contract.json",
        ],
        "machine_proof": {
            "local_only": True,
            "read_model_contract_only": True,
            "all_required_channels_present": all_required_channels_present,
            "all_channels_proof_collapsed_by_default": all_proof_collapsed,
            "all_channels_block_live_slack_and_telegram": all_block_live_surfaces,
            "slack_connected": False,
            "telegram_live_connected": False,
            "message_send_performed": False,
            "email_send_performed": False,
            "gmail_access_performed": False,
            "browser_access_performed": False,
            "coupa_access_performed": False,
            "ledger_mutation_performed": False,
            "workbook_mutation_performed": False,
            "pdf_export_performed": False,
            "paid_marking_performed": False,
            "submit_performed": False,
            "git_push_performed": False,
            "live_provider_call_performed": False,
            "agent_loop_launched": False,
            "unsafe_true_grants_absent": all(value is False for value in AUTHORITY_BOUNDARY.values()),
        },
    }


def build_wiki(read_model: Mapping[str, Any]) -> str:
    lines = [
        "# OpenClaw Workroom Registry",
        "",
        f"Status: `{read_model['status']}`",
        "",
        "This registry defines local channel-like workrooms for agent status, handoffs, and review packets. It does not connect Slack or Telegram and does not send messages.",
        "",
        f"Channels: `{read_model['channel_count']}`",
        "",
        "## Channels",
        "",
    ]
    for channel in read_model["channels"]:
        lines.extend(
            [
                f"### `{channel['channel_ref']}`",
                "",
                f"- Display: {channel['display_name']}",
                f"- World: `{channel['world_ref']}`",
                f"- Thread: `{channel['thread_ref']}`",
                f"- Primary agent: `{channel['primary_agent']}`",
                f"- Allowed speakers: {', '.join(f'`{speaker}`' for speaker in channel['allowed_speakers'])}",
                f"- Allowed package types: {', '.join(f'`{item}`' for item in channel['allowed_package_types'])}",
                "- Proof: collapsed by default",
                "",
            ]
        )
    lines.extend(
        [
            "## Agent Mapping",
            "",
        ]
    )
    for agent in read_model["agent_mapping"]:
        lines.append(f"- `{agent['display_name']}`: {agent['scope']}")
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            "- No Slack connection.",
            "- No Telegram live connection.",
            "- No message send.",
            "- No email send.",
            "- No Gmail/browser/Coupa access.",
            "- No workbook mutation or PDF export.",
            "- No ledger mutation.",
            "- No paid marking or portal submit.",
            "- No git push.",
            "- Spawned worker entries are output packets only; this registry cannot spawn workers.",
        ]
    )
    return "\n".join(lines) + "\n"


def export_openclaw_workroom_registry(
    *,
    export_root: Path = DEFAULT_EXPORT_ROOT,
    bridge_export_root: Path | None = DEFAULT_BRIDGE_EXPORT_ROOT,
    wiki_path: Path = DEFAULT_WIKI_PATH,
    generated_at: str | None = None,
) -> dict[str, str]:
    read_model = build_read_model(generated_at=generated_at)
    export_root = _rooted(export_root)
    export_root.mkdir(parents=True, exist_ok=True)
    read_model_path = export_root / JSON_EXPORT_NAME
    read_model_path.write_text(stable_json(read_model), encoding="utf-8")

    bridge_path = ""
    if bridge_export_root is not None:
        bridge_export_root.mkdir(parents=True, exist_ok=True)
        bridge_file = bridge_export_root / JSON_EXPORT_NAME
        bridge_file.write_text(stable_json(read_model), encoding="utf-8")
        bridge_path = bridge_file.as_posix()

    wiki_path = _rooted(wiki_path)
    wiki_path.parent.mkdir(parents=True, exist_ok=True)
    wiki_path.write_text(build_wiki(read_model), encoding="utf-8")
    return {
        "status": str(read_model["status"]),
        "read_model_path": read_model_path.as_posix(),
        "bridge_read_model_path": bridge_path,
        "wiki_path": wiki_path.as_posix(),
        "channel_count": str(read_model["channel_count"]),
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Export OpenClaw Workroom Registry V0.")
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT))
    parser.add_argument("--bridge-export-root", default=str(DEFAULT_BRIDGE_EXPORT_ROOT))
    parser.add_argument("--wiki-path", default=str(DEFAULT_WIKI_PATH))
    parser.add_argument("--generated-at")
    parser.add_argument("--no-bridge", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    result = export_openclaw_workroom_registry(
        export_root=Path(args.export_root),
        bridge_export_root=None if args.no_bridge else Path(args.bridge_export_root),
        wiki_path=Path(args.wiki_path),
        generated_at=args.generated_at,
    )
    print(stable_json(result), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
