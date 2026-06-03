"""Chief Build Backlog V0.

Publishes bounded future PC_CODEX and MAC_CODEX work packets for Chief without
spawning workers, executing tools, or granting business authority.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parent
DEFAULT_READ_MODEL_ROOT = Path("generated/read_models")
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_BRIDGE_EXPORT_ROOT = Path("/mnt/e/openclaw/generated/read_models")
DEFAULT_WIKI_PATH = Path("generated/wiki/openclaw/Chief Build Backlog.md")

SCHEMA_VERSION = "chief_build_backlog_v0"
READ_MODEL_ID = "chief_build_backlog"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
STATUS_READY = "CHIEF_BUILD_BACKLOG_READY"
STATUS_NOT_READY = "CHIEF_BUILD_BACKLOG_NOT_READY"

PRECONDITIONS = {
    "worker_package_staging": {
        "filename": "worker_package_staging_status.json",
        "accepted_statuses": ["WORKER_PACKAGE_STAGING_READY"],
    },
    "overnight_workboard": {
        "filename": "overnight_workboard.json",
        "accepted_statuses": ["OVERNIGHT_WORKBOARD_READY", "READY_FOR_OPERATOR_REVIEW"],
    },
    "openclaw_workroom_registry": {
        "filename": "openclaw_workroom_registry.json",
        "accepted_statuses": ["OPENCLAW_WORKROOM_REGISTRY_READY"],
    },
}

AUTHORITY_BOUNDARY = {
    "email_send_allowed": False,
    "ledger_posting_allowed": False,
    "ledger_mutation_allowed": False,
    "browser_access_allowed": False,
    "gmail_allowed": False,
    "coupa_allowed": False,
    "portal_submit_allowed": False,
    "workbook_mutation_allowed": False,
    "pdf_export_allowed": False,
    "paid_marking_allowed": False,
    "worker_spawn_allowed": False,
    "worker_execution_allowed": False,
    "tool_execution_allowed": False,
    "external_llm_allowed": False,
    "local_model_runtime_allowed": False,
    "agent_loop_allowed": False,
    "git_push_allowed": False,
    "business_action_allowed": False,
    "sent": False,
    "paid": False,
}

BLOCKED_ACTIONS = [
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
    "spawn_worker",
    "run_worker",
    "run_child_agent",
    "launch_agent_loop",
    "call_external_llm",
    "connect_local_model_runtime",
    "run_live_provider",
    "grant_business_authority",
]


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _rooted(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def _load_json(path: Path) -> dict[str, Any]:
    path = _rooted(path)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(stable_json(payload), encoding="utf-8")


def _preconditions(read_model_root: Path) -> list[dict[str, Any]]:
    root = _rooted(read_model_root)
    rows: list[dict[str, Any]] = []
    for ref, contract in PRECONDITIONS.items():
        payload = _load_json(root / str(contract["filename"]))
        observed = str(payload.get("status") or payload.get("contract_status") or "")
        accepted = [str(item) for item in contract["accepted_statuses"]]
        rows.append(
            {
                "precondition_ref": ref,
                "observed_status": observed,
                "accepted_statuses": accepted,
                "ready": observed in accepted,
                "source_ref": f"generated/read_models/{contract['filename']}",
            }
        )
    return rows


def _item(
    *,
    packet_ref: str,
    recommended_worker: str,
    channel_ref: str,
    goal: str,
    why_it_matters: str,
    dependencies: list[str],
    next_safe_action: str,
    allowed_actions: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "packet_ref": packet_ref,
        "owner_agent": "chief",
        "recommended_worker": recommended_worker,
        "channel_ref": channel_ref,
        "goal": goal,
        "why_it_matters": why_it_matters,
        "allowed_actions": allowed_actions
        or [
            "read local generated read models",
            "write focused tests",
            "write generated read models or wiki docs",
            "return result receipt",
        ],
        "blocked_actions": list(BLOCKED_ACTIONS),
        "dependencies": dependencies,
        "operator_approval_required": True,
        "next_safe_action": next_safe_action,
        "business_action_allowed": False,
        "worker_spawn_performed": False,
        "worker_execution_performed": False,
        "tool_execution_performed": False,
        "business_action_performed": False,
        "proof_refs_collapsed": True,
    }


def _backlog_items() -> list[dict[str, Any]]:
    return [
        _item(
            packet_ref="chief_backlog:mac_helm_action_desk_hierarchy",
            recommended_worker="mac_codex",
            channel_ref="build_mission_control_mac",
            goal="Improve Helm action desk hierarchy so resolved, current, and future actions are visually distinct.",
            why_it_matters="Helm should show one clear desk instead of competing cards.",
            dependencies=[
                "generated/read_models/helm_actionability_surface.json",
                "generated/read_models/helm_action_lifecycle_status.json",
            ],
            next_safe_action="Stage a Mac UI packet after operator approval.",
        ),
        _item(
            packet_ref="chief_backlog:mac_workroom_review_decision_controls",
            recommended_worker="mac_codex",
            channel_ref="build_mission_control_mac",
            goal="Render Workroom review controls for approve-for-record, request-rework, and informational-close decisions.",
            why_it_matters="The operator needs visible controls for review packet decisions without merge or push authority.",
            dependencies=[
                "generated/read_models/workroom_review_decision_contract.json",
                "generated/read_models/workroom_review_packet_index.json",
            ],
            next_safe_action="Stage a Mac UI packet with screenshot proof requirements.",
        ),
        _item(
            packet_ref="chief_backlog:pc_sqlite_unknown_classification_packets",
            recommended_worker="pc_codex",
            channel_ref="build_openclaw_backend",
            goal="Create bounded packets for SQLite unknown classification without consolidating or moving databases.",
            why_it_matters="Unknown database concepts are the next governance risk after package-event indexing.",
            dependencies=[
                "generated/read_models/sqlite_consolidation_plan.json",
                "generated/read_models/canonical_state_map.json",
            ],
            next_safe_action="Prepare a local classification packet; no migration.",
        ),
        _item(
            packet_ref="chief_backlog:pc_workroom_system_questions",
            recommended_worker="pc_codex",
            channel_ref="build_openclaw_backend",
            goal="Expand system question answers for Workrooms, handoffs, worker packages, and review packets.",
            why_it_matters="Mission Control and Helm need plain answers about where the team is working.",
            dependencies=[
                "generated/read_models/system_question_answer_contract.json",
                "generated/read_models/openclaw_workroom_activity_feed.json",
            ],
            next_safe_action="Implement local-only system question coverage.",
        ),
        _item(
            packet_ref="chief_backlog:pc_telegram_dry_run_workroom_integration",
            recommended_worker="pc_codex",
            channel_ref="build_openclaw_backend",
            goal="Plan and test Telegram dry-run intake to Workroom routing without connecting Telegram live.",
            why_it_matters="Future mobile capture needs a safe dry-run path before any live provider is considered.",
            dependencies=[
                "generated/read_models/openclaw_workroom_registry.json",
                "generated/read_models/package_event_index.json",
            ],
            next_safe_action="Create dry-run fixtures only.",
        ),
        _item(
            packet_ref="chief_backlog:pc_tts_profile_smoke_harness",
            recommended_worker="pc_codex",
            channel_ref="build_openclaw_backend",
            goal="Create a TTS profile smoke harness that validates text shape without using live TTS.",
            why_it_matters="Cassandra brief previews need TTS-safe text before audio is enabled.",
            dependencies=[
                "generated/read_models/homecoming_brief.json",
                "generated/read_models/agent_voice_profiles.json",
            ],
            next_safe_action="Build local text validation only.",
        ),
        _item(
            packet_ref="chief_backlog:mac_homecoming_brief_tts_preview",
            recommended_worker="mac_codex",
            channel_ref="build_mission_control_mac",
            goal="Preview the Homecoming Brief in Mac UI with no live TTS.",
            why_it_matters="Winship should be able to inspect Cassandra-led brief text before any audio path exists.",
            dependencies=[
                "generated/read_models/homecoming_brief.json",
                "generated/read_models/brief_automation_plan.json",
            ],
            next_safe_action="Stage a Mac UI preview packet with no TTS call.",
        ),
    ]


def build_read_model(
    *,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    preconditions = _preconditions(read_model_root)
    preconditions_ready = all(item["ready"] for item in preconditions)
    items = _backlog_items()
    return {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "generated_at": generated_at,
        "status": STATUS_READY if preconditions_ready else STATUS_NOT_READY,
        "speaker_ref": "chief",
        "voice_profile_ref": "agent_voice_profile:chief",
        "purpose": "Chief-owned bounded backlog for future PC_CODEX and MAC_CODEX packages.",
        "mode": "planning_only_no_worker_spawn",
        "preconditions": preconditions,
        "backlog_count": len(items),
        "backlog_items": items,
        "source_refs": [
            "generated/read_models/overnight_workboard.json",
            "generated/read_models/package_event_index.json",
            "generated/read_models/workroom_review_packet_index.json",
            "generated/read_models/worker_package_staging_status.json",
            "generated/read_models/helm_actionability_surface.json",
            "generated/read_models/sqlite_consolidation_plan.json",
            "generated/read_models/canonical_state_map.json",
        ],
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "machine_proof": {
            "local_only": True,
            "planning_only": True,
            "preconditions_ready": preconditions_ready,
            "worker_spawn_performed": False,
            "worker_execution_performed": False,
            "child_agent_run_performed": False,
            "tool_execution_performed": False,
            "external_llm_called": False,
            "local_model_runtime_connected": False,
            "business_action_performed": False,
            "business_state_mutation_performed": False,
            "email_send_performed": False,
            "browser_access_performed": False,
            "gmail_access_performed": False,
            "coupa_access_performed": False,
            "ledger_mutation_performed": False,
            "workbook_mutation_performed": False,
            "pdf_export_performed": False,
            "paid_marking_performed": False,
            "submit_performed": False,
            "git_push_performed": False,
            "unsafe_true_grants_absent": all(value is False for value in AUTHORITY_BOUNDARY.values()),
        },
    }


def build_wiki(read_model: Mapping[str, Any]) -> str:
    lines = [
        "# Chief Build Backlog",
        "",
        f"Status: `{read_model['status']}`",
        "",
        "Planning only. Chief owns this backlog and uses it to stage future bounded worker packets.",
        "",
        f"Backlog count: `{read_model['backlog_count']}`",
        "",
        "## Boundary",
        "",
        "- No worker is spawned or run.",
        "- No child agents, live providers, external LLMs, or model runtimes.",
        "- No email, Gmail, browser, Coupa, ledger, workbook, PDF, submit, mark-paid, or push.",
        "- Operator approval is required before any future worker packet.",
    ]
    return "\n".join(lines) + "\n"


def export_chief_build_backlog(
    *,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
    export_root: Path = DEFAULT_EXPORT_ROOT,
    bridge_export_root: Path | None = DEFAULT_BRIDGE_EXPORT_ROOT,
    wiki_path: Path = DEFAULT_WIKI_PATH,
    generated_at: str | None = None,
) -> dict[str, str]:
    read_model = build_read_model(read_model_root=read_model_root, generated_at=generated_at)
    export_root = _rooted(export_root)
    read_model_path = export_root / JSON_EXPORT_NAME
    _write_json(read_model_path, read_model)

    bridge_path = ""
    if bridge_export_root is not None:
        bridge_export_root.mkdir(parents=True, exist_ok=True)
        bridge = bridge_export_root / JSON_EXPORT_NAME
        _write_json(bridge, read_model)
        bridge_path = bridge.as_posix()

    wiki_path = _rooted(wiki_path)
    wiki_path.parent.mkdir(parents=True, exist_ok=True)
    wiki_path.write_text(build_wiki(read_model), encoding="utf-8")
    return {
        "status": str(read_model["status"]),
        "read_model_path": read_model_path.as_posix(),
        "bridge_read_model_path": bridge_path,
        "wiki_path": wiki_path.as_posix(),
        "backlog_count": str(read_model["backlog_count"]),
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Export Chief Build Backlog V0.")
    parser.add_argument("--read-model-root", default=str(DEFAULT_READ_MODEL_ROOT))
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT))
    parser.add_argument("--bridge-export-root", default=str(DEFAULT_BRIDGE_EXPORT_ROOT))
    parser.add_argument("--wiki-path", default=str(DEFAULT_WIKI_PATH))
    parser.add_argument("--generated-at")
    parser.add_argument("--no-bridge", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    result = export_chief_build_backlog(
        read_model_root=Path(args.read_model_root),
        export_root=Path(args.export_root),
        bridge_export_root=None if args.no_bridge else Path(args.bridge_export_root),
        wiki_path=Path(args.wiki_path),
        generated_at=args.generated_at,
    )
    print(stable_json(result), end="")
    return 0 if result["status"] == STATUS_READY else 2


if __name__ == "__main__":
    raise SystemExit(main())
