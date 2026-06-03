"""Workroom Review Packet Index V0.

Indexes spawned worker review packets across OpenClaw workrooms, similar to a
PR queue. This is local read-model generation only. It does not spawn workers,
run child agents, push git state, send email, open browser/Gmail/Coupa, mutate
ledgers or workbooks, export PDFs, submit portals, or grant authority.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parent
DEFAULT_READ_MODEL_ROOT = Path("generated/read_models")
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_BRIDGE_EXPORT_ROOT = Path("/mnt/e/openclaw/generated/read_models")
DEFAULT_WIKI_PATH = Path("generated/wiki/openclaw/Workroom Review Packet Index.md")

SCHEMA_VERSION = "workroom_review_packet_index_v0"
READ_MODEL_ID = "workroom_review_packet_index"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
INDEX_STATUS = "WORKROOM_REVIEW_PACKET_INDEX_READY"
INDEX_NOT_READY_STATUS = "WORKROOM_REVIEW_PACKET_INDEX_NOT_READY"

PRECONDITION_FILES = {
    "spawned_worker_package_lifecycle": "spawned_worker_package_lifecycle.json",
    "openclaw_workroom_activity_feed": "openclaw_workroom_activity_feed.json",
    "package_event_index": "package_event_index.json",
}

PRECONDITION_STATUSES = {
    "spawned_worker_package_lifecycle": "SPAWNED_WORKER_PACKAGE_LIFECYCLE_READY",
    "openclaw_workroom_activity_feed": "OPENCLAW_WORKROOM_ACTIVITY_FEED_READY",
    "package_event_index": "PACKAGE_EVENT_INDEX_READY",
}

REVIEW_PACKET_FIELDS = (
    "review_packet_id",
    "package_id",
    "worker_ref",
    "channel_ref",
    "status",
    "human_summary",
    "files_changed",
    "tests_run",
    "receipts",
    "screenshots",
    "unsafe_scan_result",
    "proof_refs",
    "next_safe_action",
    "operator_decision_required",
)

REVIEW_READY_STATES = {
    "REVIEW_PACKET_READY",
    "REWORK_REQUIRED",
    "BLOCKED_BY_GATE",
}

AUTHORITY_BOUNDARY = {
    "worker_spawn_allowed": False,
    "child_agent_run_allowed": False,
    "agent_loop_allowed": False,
    "external_llm_allowed": False,
    "external_tool_connect_allowed": False,
    "git_push_allowed": False,
    "merge_allowed": False,
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
    "speaker_tool_grant_allowed": False,
    "business_action_allowed": False,
    "sent": False,
    "paid": False,
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


def _preconditions(read_model_root: Path) -> list[dict[str, Any]]:
    root = _rooted(read_model_root)
    rows: list[dict[str, Any]] = []
    for ref, filename in PRECONDITION_FILES.items():
        payload = _load_json(root / filename)
        observed = str(payload.get("status") or payload.get("contract_status") or "")
        required = PRECONDITION_STATUSES[ref]
        rows.append(
            {
                "precondition_ref": ref,
                "required_status": required,
                "observed_status": observed,
                "ready": observed == required,
                "source_ref": f"generated/read_models/{filename}",
            }
        )
    return rows


def _source_payloads(read_model_root: Path) -> dict[str, dict[str, Any]]:
    root = _rooted(read_model_root)
    return {
        ref: _load_json(root / filename)
        for ref, filename in PRECONDITION_FILES.items()
    }


def _short_hash(parts: list[str]) -> str:
    return hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()[:16]


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _strings(value: Any) -> list[str]:
    return [str(item) for item in _list(value) if str(item)]


def _proof_ref_value(item: Any) -> str:
    if isinstance(item, Mapping):
        return str(item.get("ref") or item.get("path") or item.get("source_ref") or "")
    return str(item or "")


def _proof_refs(*groups: Any, limit: int = 12) -> list[str]:
    refs: list[str] = []
    for group in groups:
        if isinstance(group, list):
            for item in group:
                value = _proof_ref_value(item)
                if value:
                    refs.append(value)
        else:
            value = _proof_ref_value(group)
            if value:
                refs.append(value)
    return list(dict.fromkeys(refs))[:limit]


def _status_from_state_path(state_path: Any) -> str:
    states = _strings(state_path)
    return states[-1] if states else "REVIEW_PACKET_READY"


def _activity_review_posts(activity_feed: Mapping[str, Any]) -> dict[str, list[dict[str, Any]]]:
    rows: dict[str, list[dict[str, Any]]] = {}
    for post in _list(activity_feed.get("posts")):
        if not isinstance(post, Mapping):
            continue
        if post.get("post_type") != "review_packet":
            continue
        package_id = str(post.get("package_id") or "")
        if not package_id:
            continue
        rows.setdefault(package_id, []).append(dict(post))
    return rows


def _lifecycle_packet(
    example: Mapping[str, Any],
    *,
    matching_activity_posts: list[dict[str, Any]],
) -> dict[str, Any]:
    package_id = str(example.get("package_id") or "")
    worker_ref = str(example.get("worker_ref") or "")
    channel_ref = str(example.get("channel_ref") or "")
    example_ref = str(example.get("example_ref") or package_id or worker_ref)
    review = example.get("review_packet_summary") if isinstance(example.get("review_packet_summary"), Mapping) else {}
    state_path = _strings(example.get("state_path"))
    status = _status_from_state_path(state_path)
    activity_refs = [str(post.get("post_id")) for post in matching_activity_posts if post.get("post_id")]
    activity_proof_refs: list[str] = []
    for post in matching_activity_posts:
        activity_proof_refs.extend(_strings(post.get("proof_refs")))
    receipts = _strings(review.get("receipts"))
    screenshots = _strings(review.get("screenshots"))
    unsafe_scan_result = review.get("unsafe_scan_result")
    if not isinstance(unsafe_scan_result, Mapping):
        unsafe_scan_result = {"status": "UNKNOWN", "unsafe_true_grants": []}
    proof_refs = _proof_refs(
        review.get("proof_refs"),
        receipts,
        screenshots,
        activity_proof_refs,
        f"generated/read_models/spawned_worker_package_lifecycle.json#{example_ref}",
    )
    return {
        "review_packet_id": f"review_packet:{_short_hash([example_ref, package_id, worker_ref, channel_ref])}",
        "package_id": package_id,
        "worker_ref": worker_ref,
        "channel_ref": channel_ref,
        "status": status,
        "human_summary": str(review.get("human_summary") or example.get("authority_note") or "Worker review output is ready."),
        "files_changed": _strings(review.get("files_changed")),
        "tests_run": _strings(review.get("tests_run")),
        "receipts": receipts,
        "screenshots": screenshots,
        "unsafe_scan_result": dict(unsafe_scan_result),
        "proof_refs": proof_refs,
        "next_safe_action": str(review.get("next_safe_action") or "Review the packet and approve, request rework, or block by gate."),
        "operator_decision_required": status in REVIEW_READY_STATES,
        "state_path": state_path,
        "activity_post_refs": activity_refs,
        "proof_collapsed_by_default": True,
        "operator_approval_required_before_merge_or_record": True,
        "worker_inherits_speaker_authority": False,
        "merge_allowed": False,
        "push_allowed": False,
        "business_action_performed": False,
        "review_packet_only": True,
    }


def _activity_only_packet(post: Mapping[str, Any]) -> dict[str, Any]:
    package_id = str(post.get("package_id") or "")
    worker_ref = str(post.get("speaker_ref") or "")
    channel_ref = str(post.get("channel_ref") or "")
    post_id = str(post.get("post_id") or package_id)
    return {
        "review_packet_id": f"review_packet:{_short_hash([post_id, package_id, worker_ref, channel_ref])}",
        "package_id": package_id,
        "worker_ref": worker_ref,
        "channel_ref": channel_ref,
        "status": "REVIEW_PACKET_READY",
        "human_summary": str(post.get("plain_summary") or "Worker review output is ready."),
        "files_changed": [],
        "tests_run": [],
        "receipts": [],
        "screenshots": [],
        "unsafe_scan_result": {"status": "UNKNOWN", "unsafe_true_grants": []},
        "proof_refs": _proof_refs(post.get("proof_refs"), f"generated/read_models/openclaw_workroom_activity_feed.json#{post_id}"),
        "next_safe_action": str(post.get("next_safe_action") or "Review the packet and approve, request rework, or block by gate."),
        "operator_decision_required": True,
        "state_path": ["REVIEW_PACKET_READY"],
        "activity_post_refs": [post_id],
        "proof_collapsed_by_default": True,
        "operator_approval_required_before_merge_or_record": True,
        "worker_inherits_speaker_authority": False,
        "merge_allowed": False,
        "push_allowed": False,
        "business_action_performed": False,
        "review_packet_only": True,
    }


def _build_packets(payloads: Mapping[str, dict[str, Any]]) -> list[dict[str, Any]]:
    lifecycle = payloads.get("spawned_worker_package_lifecycle", {})
    activity = payloads.get("openclaw_workroom_activity_feed", {})
    review_posts_by_package = _activity_review_posts(activity)
    packets: list[dict[str, Any]] = []
    indexed_packages: set[str] = set()

    for example in _list(lifecycle.get("examples")):
        if not isinstance(example, Mapping):
            continue
        package_id = str(example.get("package_id") or "")
        matching_posts = review_posts_by_package.get(package_id, [])
        packets.append(_lifecycle_packet(example, matching_activity_posts=matching_posts))
        if package_id:
            indexed_packages.add(package_id)

    for posts in review_posts_by_package.values():
        for post in posts:
            package_id = str(post.get("package_id") or "")
            if package_id in indexed_packages:
                continue
            packets.append(_activity_only_packet(post))
            if package_id:
                indexed_packages.add(package_id)

    packets.sort(key=lambda packet: (packet["channel_ref"], packet["worker_ref"], packet["package_id"]))
    return packets


def _packets_by_key(packets: list[dict[str, Any]], key: str) -> dict[str, list[str]]:
    rows: dict[str, list[str]] = {}
    for packet in packets:
        rows.setdefault(str(packet.get(key) or ""), []).append(str(packet["review_packet_id"]))
    return dict(sorted(rows.items()))


def _counts_by_key(packets: list[dict[str, Any]], key: str) -> dict[str, int]:
    rows: dict[str, int] = {}
    for packet in packets:
        value = str(packet.get(key) or "")
        rows[value] = rows.get(value, 0) + 1
    return dict(sorted(rows.items()))


def build_read_model(
    *,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    preconditions = _preconditions(read_model_root)
    preconditions_ready = all(item["ready"] for item in preconditions)
    payloads = _source_payloads(read_model_root)
    lifecycle = payloads.get("spawned_worker_package_lifecycle", {})
    packets = _build_packets(payloads) if preconditions_ready else []
    status = INDEX_STATUS if preconditions_ready else INDEX_NOT_READY_STATUS
    lifecycle_states = _strings(lifecycle.get("lifecycle_states"))
    return {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "generated_at": generated_at,
        "status": status,
        "purpose": "PR-like review packet queue for spawned worker outputs across OpenClaw workrooms.",
        "mode": "local_read_model_generation_only_no_merge_push_or_worker_spawn",
        "preconditions": preconditions,
        "review_packet_fields": list(REVIEW_PACKET_FIELDS),
        "lifecycle_states": lifecycle_states,
        "review_packet_count": len(packets),
        "packets_by_channel": _packets_by_key(packets, "channel_ref"),
        "packets_by_worker": _packets_by_key(packets, "worker_ref"),
        "packet_counts_by_status": _counts_by_key(packets, "status"),
        "packets": packets,
        "display_policy": {
            "proof_collapsed_by_default": True,
            "show_machine_details_by_default": False,
            "review_packet_only": True,
            "plain_summary_first": True,
        },
        "review_rules": [
            "No merge or push action is authorized by this index.",
            "No business action is authorized by this index.",
            "Review packet readiness is not approval.",
            "Worker does not inherit speaker authority.",
            "Operator approval is required before merge or recorded completion.",
            "Proof refs remain collapsed by default.",
        ],
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "source_refs": [
            "generated/read_models/spawned_worker_package_lifecycle.json",
            "generated/read_models/openclaw_workroom_activity_feed.json",
            "generated/read_models/package_event_index.json",
        ],
        "machine_proof": {
            "local_only": True,
            "read_model_generation_only": True,
            "preconditions_ready": preconditions_ready,
            "lifecycle_states_parsed": bool(lifecycle_states),
            "all_packets_review_only": all(packet["review_packet_only"] is True for packet in packets),
            "all_packets_proof_collapsed_by_default": all(packet["proof_collapsed_by_default"] is True for packet in packets),
            "all_packets_require_operator_decision": all(packet["operator_decision_required"] is True for packet in packets),
            "workers_inherit_speaker_authority": False,
            "worker_spawn_performed": False,
            "child_agent_run_performed": False,
            "merge_performed": False,
            "git_push_performed": False,
            "business_action_performed": False,
            "email_send_performed": False,
            "gmail_access_performed": False,
            "browser_access_performed": False,
            "coupa_access_performed": False,
            "ledger_mutation_performed": False,
            "workbook_mutation_performed": False,
            "pdf_export_performed": False,
            "submit_performed": False,
            "paid_marking_performed": False,
            "unsafe_true_grants_absent": all(value is False for value in AUTHORITY_BOUNDARY.values()),
        },
    }


def build_wiki(read_model: Mapping[str, Any]) -> str:
    lines = [
        "# Workroom Review Packet Index",
        "",
        f"Status: `{read_model['status']}`",
        "",
        "This read model indexes spawned worker review packets across OpenClaw workrooms like a PR queue.",
        "",
        f"Review packets: `{read_model['review_packet_count']}`",
        "",
        "## Packets",
        "",
    ]
    for packet in read_model["packets"]:
        lines.extend(
            [
                f"### `{packet['review_packet_id']}`",
                "",
                f"- Worker: `{packet['worker_ref']}`",
                f"- Channel: `{packet['channel_ref']}`",
                f"- Package: `{packet['package_id']}`",
                f"- Status: `{packet['status']}`",
                f"- Summary: {packet['human_summary']}",
                f"- Next safe action: {packet['next_safe_action']}",
                "- Operator decision required: `true`",
                "",
            ]
        )
    lines.extend(
        [
            "## Boundary",
            "",
            "- No merge.",
            "- No git push.",
            "- No worker spawn or child agent run.",
            "- No email send.",
            "- No Gmail/browser/Coupa access.",
            "- No ledger or workbook mutation.",
            "- No PDF export.",
            "- No submit or mark-paid.",
            "- No business action.",
            "- Worker does not inherit speaker authority.",
            "- Proof refs are collapsed by default.",
        ]
    )
    return "\n".join(lines) + "\n"


def export_workroom_review_packet_index(
    *,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
    export_root: Path = DEFAULT_EXPORT_ROOT,
    bridge_export_root: Path | None = DEFAULT_BRIDGE_EXPORT_ROOT,
    wiki_path: Path = DEFAULT_WIKI_PATH,
    generated_at: str | None = None,
) -> dict[str, str]:
    read_model = build_read_model(read_model_root=read_model_root, generated_at=generated_at)
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
        "review_packet_count": str(read_model["review_packet_count"]),
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Export Workroom Review Packet Index V0.")
    parser.add_argument("--read-model-root", default=str(DEFAULT_READ_MODEL_ROOT))
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT))
    parser.add_argument("--bridge-export-root", default=str(DEFAULT_BRIDGE_EXPORT_ROOT))
    parser.add_argument("--wiki-path", default=str(DEFAULT_WIKI_PATH))
    parser.add_argument("--generated-at")
    parser.add_argument("--no-bridge", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    result = export_workroom_review_packet_index(
        read_model_root=Path(args.read_model_root),
        export_root=Path(args.export_root),
        bridge_export_root=None if args.no_bridge else Path(args.bridge_export_root),
        wiki_path=Path(args.wiki_path),
        generated_at=args.generated_at,
    )
    print(stable_json(result), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
