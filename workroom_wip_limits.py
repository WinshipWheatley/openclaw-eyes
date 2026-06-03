"""Workroom WIP Limits V0.

Publishes per-channel work-in-progress limits and bottleneck detection for
OpenClaw Workrooms. This is read-model work only: it does not run workers,
spawn agents, send email, open providers, mutate ledgers/workbooks, or push.
"""

from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parent
DEFAULT_READ_MODEL_ROOT = Path("generated/read_models")
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_BRIDGE_ROOT = Path("/mnt/e/openclaw/generated/read_models")
DEFAULT_WIKI_PATH = Path("generated/wiki/openclaw/Workroom WIP Limits.md")

SCHEMA_VERSION = "workroom_wip_limits_v0"
READ_MODEL_ID = "workroom_wip_limits"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
READY_STATUS = "WORKROOM_WIP_LIMITS_READY"
NOT_READY_STATUS = "WORKROOM_WIP_LIMITS_NOT_READY"

MAX_ACTIVE_REVIEW_PACKETS_PER_CHANNEL = 1
MAX_PENDING_APPROVALS_PER_CHANNEL = 0
MAX_DEAD_LETTERS_PER_CHANNEL = 2

PRECONDITIONS = {
    "openclaw_workroom_activity_feed": {
        "filename": "openclaw_workroom_activity_feed.json",
        "required_status": "OPENCLAW_WORKROOM_ACTIVITY_FEED_READY",
        "status_source": "top_level",
    },
    "workroom_review_packet_index": {
        "filename": "workroom_review_packet_index.json",
        "required_status": "WORKROOM_REVIEW_PACKET_INDEX_READY",
        "status_source": "top_level",
    },
    "approval_request_queue": {
        "filename": "approval_request_queue.json",
        "required_status": "APPROVAL_REQUEST_QUEUE_READY",
        "status_source": "top_level",
    },
    "dead_letter_queue": {
        "filename": "dead_letter_queue.json",
        "required_status": "DEAD_LETTER_QUEUE_READY",
        "status_source": "top_level",
    },
    "operator_next_decision_workrooms": {
        "filename": "track_a_workroom_backbone_status.json",
        "required_status": "OPERATOR_NEXT_DECISION_WORKROOMS_READY",
        "status_source": "phase",
        "phase": "operator_next_decision_workrooms",
    },
}

TERMINAL_REVIEW_STATUSES = {
    "OPERATOR_REVIEW_RECORDED",
    "INFORMATIONAL_REVIEW_CLOSED",
    "REWORK_REQUEST_RECORDED",
    "REVIEW_PACKET_CANCELLED",
    "COMPLETED",
}

PENDING_APPROVAL_STATUSES = {"pending", "waiting", "needs_operator", "requested"}

PROTECTED_GATE_TERMS = (
    "send",
    "email",
    "gmail",
    "browser",
    "coupa",
    "submit",
    "ledger",
    "workbook",
    "excel",
    "pdf",
    "paid",
    "payment",
    "credential",
    "provider",
    "permission",
    "authority",
)

AUTHORITY_BOUNDARY = {
    "email_send_allowed": False,
    "gmail_allowed": False,
    "browser_access_allowed": False,
    "coupa_allowed": False,
    "portal_submit_allowed": False,
    "ledger_posting_allowed": False,
    "ledger_mutation_allowed": False,
    "workbook_open_allowed": False,
    "workbook_body_read_allowed": False,
    "spreadsheet_cell_read_allowed": False,
    "workbook_mutation_allowed": False,
    "excel_automation_allowed": False,
    "pdf_export_allowed": False,
    "paid_marking_allowed": False,
    "business_action_allowed": False,
    "authority_grant_allowed": False,
    "worker_spawn_allowed": False,
    "worker_execution_allowed": False,
    "child_agent_run_allowed": False,
    "agent_loop_allowed": False,
    "external_llm_allowed": False,
    "tool_execution_allowed": False,
    "git_push_allowed": False,
    "push_allowed": False,
    "sent": False,
    "paid": False,
}

UNSAFE_TRUE_KEYS = set(AUTHORITY_BOUNDARY) | {
    "email_send_performed",
    "gmail_access_performed",
    "browser_access_performed",
    "coupa_access_performed",
    "submit_performed",
    "ledger_mutation_performed",
    "workbook_mutation_performed",
    "excel_automation_performed",
    "pdf_export_performed",
    "paid_marking_performed",
    "business_action_performed",
    "worker_spawn_performed",
    "worker_execution_performed",
    "child_agent_run_performed",
    "agent_loop_started",
    "external_llm_called",
    "git_push_performed",
}


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


def _observed_status(payload: Mapping[str, Any], spec: Mapping[str, Any]) -> str:
    if spec.get("status_source") == "phase":
        phase_ref = str(spec.get("phase") or "")
        for phase in payload.get("phases") or []:
            if isinstance(phase, Mapping) and str(phase.get("phase") or "") == phase_ref:
                return str(phase.get("status") or "")
        return ""
    return str(payload.get("status") or payload.get("contract_status") or "")


def _preconditions(read_model_root: Path) -> list[dict[str, Any]]:
    root = _rooted(read_model_root)
    rows: list[dict[str, Any]] = []
    for ref, spec in PRECONDITIONS.items():
        payload = _load_json(root / str(spec["filename"]))
        observed = _observed_status(payload, spec)
        required = str(spec["required_status"])
        source_ref = f"generated/read_models/{spec['filename']}"
        if spec.get("status_source") == "phase":
            source_ref += f"#phases.{spec.get('phase')}"
        rows.append(
            {
                "precondition_ref": ref,
                "required_status": required,
                "observed_status": observed,
                "ready": observed == required,
                "source_ref": source_ref,
            }
        )
    return rows


def _channel_ref(row: Mapping[str, Any], fallback: str = "unassigned") -> str:
    if row.get("channel_ref"):
        return str(row["channel_ref"])
    world = str(row.get("target_world_ref") or "").strip()
    thread = str(row.get("target_thread_ref") or "").strip()
    if world and thread:
        return f"{world}_{thread}"
    if thread:
        return thread
    if world:
        return world
    return fallback


def _is_active_review_packet(packet: Mapping[str, Any]) -> bool:
    status = str(packet.get("status") or packet.get("review_decision_status") or "").upper()
    if packet.get("completed") is True:
        return False
    if status in TERMINAL_REVIEW_STATUSES:
        return False
    return packet.get("operator_decision_required") is True or status in {
        "REVIEW_PACKET_READY",
        "READY_FOR_OPERATOR_REVIEW",
        "WAITING_FOR_OPERATOR_REVIEW",
    }


def _pending_approvals(approval_queue: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in approval_queue.get("approval_requests") or []:
        if not isinstance(item, Mapping):
            continue
        status = str(item.get("status") or "").strip().lower()
        if status in PENDING_APPROVAL_STATUSES:
            rows.append(dict(item))
    return rows


def _is_protected_gate(approval: Mapping[str, Any]) -> bool:
    parts: list[str] = []
    for key in (
        "gate_ref",
        "requested_action",
        "plain_summary",
        "risk_summary",
        "target_world_ref",
        "target_thread_ref",
    ):
        parts.append(str(approval.get(key) or ""))
    for key in ("forbidden_options", "safe_options"):
        value = approval.get(key)
        if isinstance(value, list):
            parts.extend(str(item) for item in value)
    text = " ".join(parts).lower()
    return any(term in text for term in PROTECTED_GATE_TERMS)


def _dead_letters(dead_letter_queue: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [dict(item) for item in dead_letter_queue.get("dead_letters") or [] if isinstance(item, Mapping)]


def _review_packets(packet_index: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [dict(item) for item in packet_index.get("packets") or [] if isinstance(item, Mapping)]


def _walk_values(payload: Any):
    if isinstance(payload, Mapping):
        for key, value in payload.items():
            yield str(key), value
            yield from _walk_values(value)
    elif isinstance(payload, list):
        for value in payload:
            yield from _walk_values(value)


def _unsafe_true_grants(payload: Mapping[str, Any]) -> list[str]:
    return sorted({key for key, value in _walk_values(payload) if key in UNSAFE_TRUE_KEYS and value is True})


def _status_for_counts(
    *,
    active_packet_count: int,
    pending_approval_count: int,
    dead_letter_count: int,
    protected_gate_count: int,
) -> str:
    if protected_gate_count > 0:
        return "blocked"
    if (
        active_packet_count > MAX_ACTIVE_REVIEW_PACKETS_PER_CHANNEL
        or pending_approval_count > MAX_PENDING_APPROVALS_PER_CHANNEL
        or dead_letter_count > MAX_DEAD_LETTERS_PER_CHANNEL
    ):
        return "pileup_risk"
    if active_packet_count or pending_approval_count or dead_letter_count:
        return "watch"
    return "clear"


def _recommended_action(status: str, *, active: int, approvals: int, dead_letters: int, protected: int) -> str:
    if status == "blocked":
        return (
            "Do not stage new work. Resolve the protected Guardian gate before escalating or creating more packets."
            if protected
            else "Do not stage new work until the blocking condition is cleared."
        )
    if status == "pileup_risk":
        return "Chief recommends finishing review and clearing pending approvals or dead letters before creating new packets."
    if status == "watch":
        if active:
            return "Finish the active review packet before staging optional new work."
        if approvals:
            return "Clear pending approval requests before staging optional new work."
        if dead_letters:
            return "Inspect the dead-letter backlog before staging optional new work."
    return "Channel is clear; new staging may be considered only after explicit operator approval."


def build_read_model(
    *,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    root = _rooted(read_model_root)
    preconditions = _preconditions(root)
    preconditions_ready = all(row["ready"] for row in preconditions)

    packet_index = _load_json(root / "workroom_review_packet_index.json")
    approval_queue = _load_json(root / "approval_request_queue.json")
    dead_letter_queue = _load_json(root / "dead_letter_queue.json")

    review_packets = _review_packets(packet_index)
    active_packets = [packet for packet in review_packets if _is_active_review_packet(packet)]
    pending_approvals = _pending_approvals(approval_queue)
    dead_letters = _dead_letters(dead_letter_queue)

    channels: set[str] = set()
    channels.update(_channel_ref(packet, "workroom_review") for packet in review_packets)
    channels.update(_channel_ref(approval, "approval_queue") for approval in pending_approvals)
    channels.update(_channel_ref(dead_letter, "dead_letter_queue") for dead_letter in dead_letters)

    rows: list[dict[str, Any]] = []
    for channel_ref in sorted(channels):
        channel_review_packets = [packet for packet in review_packets if _channel_ref(packet, "workroom_review") == channel_ref]
        channel_active_packets = [packet for packet in active_packets if _channel_ref(packet, "workroom_review") == channel_ref]
        channel_pending_approvals = [
            approval for approval in pending_approvals if _channel_ref(approval, "approval_queue") == channel_ref
        ]
        channel_dead_letters = [
            dead_letter for dead_letter in dead_letters if _channel_ref(dead_letter, "dead_letter_queue") == channel_ref
        ]
        protected_gate_refs = [
            str(approval.get("gate_ref") or approval.get("approval_request_id") or "")
            for approval in channel_pending_approvals
            if _is_protected_gate(approval)
        ]
        status = _status_for_counts(
            active_packet_count=len(channel_active_packets),
            pending_approval_count=len(channel_pending_approvals),
            dead_letter_count=len(channel_dead_letters),
            protected_gate_count=len(protected_gate_refs),
        )
        rows.append(
            {
                "channel_ref": channel_ref,
                "active_packet_count": len(channel_active_packets),
                "review_packet_count": len(channel_review_packets),
                "pending_approval_count": len(channel_pending_approvals),
                "dead_letter_count": len(channel_dead_letters),
                "protected_gate_count": len(protected_gate_refs),
                "protected_gate_refs": [ref for ref in protected_gate_refs if ref],
                "wip_status": status,
                "recommended_action": _recommended_action(
                    status,
                    active=len(channel_active_packets),
                    approvals=len(channel_pending_approvals),
                    dead_letters=len(channel_dead_letters),
                    protected=len(protected_gate_refs),
                ),
                "stage_new_work_allowed": status == "clear",
                "limit_policy": {
                    "max_active_review_packets_per_channel": MAX_ACTIVE_REVIEW_PACKETS_PER_CHANNEL,
                    "max_pending_approvals_per_channel": MAX_PENDING_APPROVALS_PER_CHANNEL,
                    "max_dead_letters_per_channel": MAX_DEAD_LETTERS_PER_CHANNEL,
                },
                "review_packet_refs": [
                    str(packet.get("review_packet_id") or packet.get("package_id") or "")
                    for packet in channel_review_packets
                    if packet.get("review_packet_id") or packet.get("package_id")
                ],
                "pending_approval_refs": [
                    str(approval.get("approval_request_id") or approval.get("gate_ref") or "")
                    for approval in channel_pending_approvals
                    if approval.get("approval_request_id") or approval.get("gate_ref")
                ],
                "dead_letter_refs": [
                    str(dead_letter.get("dead_letter_id") or dead_letter.get("failure_kind") or "")
                    for dead_letter in channel_dead_letters
                    if dead_letter.get("dead_letter_id") or dead_letter.get("failure_kind")
                ],
            }
        )

    overloaded = [row for row in rows if row["wip_status"] in {"pileup_risk", "blocked"}]
    watch = [row for row in rows if row["wip_status"] == "watch"]
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "status": READY_STATUS if preconditions_ready else NOT_READY_STATUS,
        "generated_at": generated_at,
        "purpose": "Per-channel WIP limits and bottleneck detection so Workrooms do not create more review work than the operator can process.",
        "preconditions": preconditions,
        "limits": {
            "max_active_review_packets_per_channel": MAX_ACTIVE_REVIEW_PACKETS_PER_CHANNEL,
            "max_pending_approvals_per_channel": MAX_PENDING_APPROVALS_PER_CHANNEL,
            "max_dead_letters_per_channel": MAX_DEAD_LETTERS_PER_CHANNEL,
        },
        "channels": rows,
        "channel_count": len(rows),
        "overloaded_channel_count": len(overloaded),
        "watch_channel_count": len(watch),
        "stage_new_work_allowed_globally": not overloaded and not watch,
        "chief_recommendation": (
            "Finish review and clear bottlenecks before creating new packets."
            if overloaded or watch
            else "No current WIP bottleneck is visible; new staging still requires operator approval."
        ),
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "source_refs": [
            "generated/read_models/openclaw_workroom_activity_feed.json",
            "generated/read_models/workroom_review_packet_index.json",
            "generated/read_models/approval_request_queue.json",
            "generated/read_models/dead_letter_queue.json",
            "generated/read_models/track_a_workroom_backbone_status.json#phases.operator_next_decision_workrooms",
        ],
        "machine_proof": {
            "preconditions_ready": preconditions_ready,
            "read_model_only": True,
            "stage_new_work_false_when_overloaded": all(row["stage_new_work_allowed"] is False for row in overloaded),
            "protected_gates_block_escalation": all(
                row["wip_status"] == "blocked" for row in rows if row["protected_gate_count"] > 0
            ),
            "chief_recommends_finishing_review_before_new_packets": bool(overloaded or watch),
            "email_send_performed": False,
            "gmail_access_performed": False,
            "browser_access_performed": False,
            "coupa_access_performed": False,
            "ledger_mutation_performed": False,
            "workbook_mutation_performed": False,
            "pdf_export_performed": False,
            "paid_marking_performed": False,
            "submit_performed": False,
            "business_action_performed": False,
            "worker_spawn_performed": False,
            "worker_execution_performed": False,
            "child_agent_run_performed": False,
            "agent_loop_started": False,
            "external_llm_called": False,
            "git_push_performed": False,
            "unsafe_true_grants": [],
            "unsafe_true_grants_absent": True,
        },
    }
    unsafe = _unsafe_true_grants(payload)
    payload["machine_proof"]["unsafe_true_grants"] = unsafe
    payload["machine_proof"]["unsafe_true_grants_absent"] = not unsafe
    return payload


def build_wiki(payload: Mapping[str, Any]) -> str:
    lines = [
        "# Workroom WIP Limits",
        "",
        f"Status: `{payload.get('status', NOT_READY_STATUS)}`",
        "",
        "This read-model limits active Workroom review load and highlights bottlenecks before agents create more review work.",
        "",
        "## Limits",
        "",
    ]
    limits = payload.get("limits") if isinstance(payload.get("limits"), Mapping) else {}
    for key, value in limits.items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Channels", ""])
    for row in payload.get("channels") or []:
        if not isinstance(row, Mapping):
            continue
        lines.extend(
            [
                f"### `{row.get('channel_ref')}`",
                "",
                f"- WIP status: `{row.get('wip_status')}`",
                f"- Active packets: `{row.get('active_packet_count')}`",
                f"- Review packets: `{row.get('review_packet_count')}`",
                f"- Pending approvals: `{row.get('pending_approval_count')}`",
                f"- Dead letters: `{row.get('dead_letter_count')}`",
                f"- Stage new work allowed: `{str(row.get('stage_new_work_allowed')).lower()}`",
                f"- Recommended action: {row.get('recommended_action')}",
                "",
            ]
        )
    lines.extend(
        [
            "## Boundary",
            "",
            "- Read-model only.",
            "- No workers or agents are run.",
            "- No email, Gmail, browser, Coupa, ledger, workbook, PDF, mark-paid, submit, or git push authority.",
            "- Chief recommends finishing review before creating new packets when any channel is not clear.",
        ]
    )
    return "\n".join(lines) + "\n"


def export_workroom_wip_limits(
    *,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
    export_root: Path = DEFAULT_EXPORT_ROOT,
    bridge_root: Path | None = DEFAULT_BRIDGE_ROOT,
    wiki_path: Path = DEFAULT_WIKI_PATH,
    generated_at: str | None = None,
) -> dict[str, str]:
    payload = build_read_model(read_model_root=read_model_root, generated_at=generated_at)
    export_root = _rooted(export_root)
    export_root.mkdir(parents=True, exist_ok=True)
    json_path = export_root / JSON_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")

    bridge_path = ""
    if bridge_root is not None:
        bridge_root.mkdir(parents=True, exist_ok=True)
        bridge_file = bridge_root / JSON_EXPORT_NAME
        shutil.copy2(json_path, bridge_file)
        bridge_path = bridge_file.as_posix()

    wiki_path = _rooted(wiki_path)
    wiki_path.parent.mkdir(parents=True, exist_ok=True)
    wiki_path.write_text(build_wiki(payload), encoding="utf-8")

    return {
        "status": str(payload["status"]),
        "read_model_path": json_path.as_posix(),
        "bridge_read_model_path": bridge_path,
        "wiki_path": wiki_path.as_posix(),
        "channel_count": str(payload["channel_count"]),
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Publish Workroom WIP Limits V0.")
    parser.add_argument("--read-model-root", default=str(DEFAULT_READ_MODEL_ROOT))
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT))
    parser.add_argument("--bridge-root", default=str(DEFAULT_BRIDGE_ROOT))
    parser.add_argument("--wiki-path", default=str(DEFAULT_WIKI_PATH))
    parser.add_argument("--generated-at")
    parser.add_argument("--no-bridge", action="store_true")
    parser.add_argument("--format", choices=("summary", "json"), default="summary")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    result = export_workroom_wip_limits(
        read_model_root=Path(args.read_model_root),
        export_root=Path(args.export_root),
        bridge_root=None if args.no_bridge else Path(args.bridge_root),
        wiki_path=Path(args.wiki_path),
        generated_at=args.generated_at,
    )
    if args.format == "json":
        print(stable_json(result), end="")
    else:
        print(f"{result['status']}: {result['channel_count']} channels")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
