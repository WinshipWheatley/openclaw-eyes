"""Workroom Review Decision Lifecycle V0.

Applies recorded Workroom review decisions to generated review packet and
activity feed read models. This is generated read-model work only. It does not
merge code, push git state, spawn workers, run child agents, send email, open
browser/Gmail/Coupa, mutate ledgers or workbooks, export PDFs, submit portals,
mark paid, or create business truth.
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
DEFAULT_WIKI_PATH = Path("generated/wiki/openclaw/Workroom Review Decision Lifecycle.md")

SCHEMA_VERSION = "workroom_review_decision_lifecycle_v0"
READ_MODEL_ID = "workroom_review_decision_lifecycle_status"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
LIFECYCLE_STATUS = "WORKROOM_REVIEW_DECISION_LIFECYCLE_READY"
LIFECYCLE_NOT_READY_STATUS = "WORKROOM_REVIEW_DECISION_LIFECYCLE_NOT_READY"

PACKET_INDEX_EXPORT_NAME = "workroom_review_packet_index.json"
ACTIVITY_FEED_EXPORT_NAME = "openclaw_workroom_activity_feed.json"

PRECONDITION_FILES = {
    "workroom_review_decision_status": "workroom_review_decision_status.json",
    "workroom_review_packet_index": PACKET_INDEX_EXPORT_NAME,
    "openclaw_workroom_activity_feed": ACTIVITY_FEED_EXPORT_NAME,
}

PRECONDITION_STATUSES = {
    "workroom_review_decision_status": "WORKROOM_REVIEW_DECISION_CONSUMER_READY",
    "workroom_review_packet_index": "WORKROOM_REVIEW_PACKET_INDEX_READY",
    "openclaw_workroom_activity_feed": "OPENCLAW_WORKROOM_ACTIVITY_FEED_READY",
}

ACTION_EFFECTS = {
    "approve_review_packet_for_record": {
        "packet_status": "OPERATOR_REVIEW_RECORDED",
        "visible_by_default": False,
        "completed": True,
        "operator_decision_required": False,
        "next_safe_action": "Record complete. No merge or push performed.",
        "post_headline": "Review recorded",
        "post_summary": "Chief recorded the review decision only; no merge or push ran.",
    },
    "request_review_packet_rework": {
        "packet_status": "REWORK_REQUIRED",
        "visible_by_default": True,
        "completed": False,
        "operator_decision_required": True,
        "next_safe_action": "Review the rework request before assigning any follow-up.",
        "post_headline": "Rework requested",
        "post_summary": "Chief recorded a rework request only; no worker was spawned.",
    },
    "mark_review_packet_informational": {
        "packet_status": "INFORMATIONAL_REVIEW_CLOSED",
        "visible_by_default": False,
        "completed": True,
        "operator_decision_required": False,
        "next_safe_action": "No action needed.",
        "post_headline": "Informational review closed",
        "post_summary": "Chief closed the review as informational only; no follow-up action ran.",
    },
}

COMPLETED_PACKET_STATUSES = {
    "OPERATOR_REVIEW_RECORDED",
    "INFORMATIONAL_REVIEW_CLOSED",
}

AUTHORITY_BOUNDARY = {
    "merge_allowed": False,
    "git_push_allowed": False,
    "worker_spawn_allowed": False,
    "child_agent_run_allowed": False,
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
    "business_action_allowed": False,
    "sent": False,
    "paid": False,
}

CHANNEL_WORLD_THREAD = {
    "finance_st_annes": ("finance", "st_annes"),
    "finance_capital_hilton": ("finance", "capital_hilton"),
    "business_development_capital_hilton": ("business_development", "capital_hilton"),
    "build_mission_control_mac": ("build", "build_mission_control_mac"),
    "build_openclaw_backend": ("build", "build_openclaw_backend"),
    "architecture_hermes": ("architecture", "architecture_hermes"),
    "security_guardian_gates": ("security", "security_guardian_gates"),
    "operations_chief_workboard": ("operations", "operations_chief_workboard"),
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


def _copy_json(payload: Mapping[str, Any]) -> dict[str, Any]:
    return json.loads(stable_json(payload))


def _short_hash(parts: list[str]) -> str:
    return hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()[:16]


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


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _strings(value: Any) -> list[str]:
    return [str(item) for item in _list(value) if str(item)]


def _append_unique(values: list[str], *extra: str) -> list[str]:
    merged = list(values)
    merged.extend(str(item) for item in extra if str(item))
    return list(dict.fromkeys(merged))


def _status_label(value: str) -> str:
    return str(value or "STATUS").replace("_", " ").title()


def _channel_world_thread(channel_ref: str) -> tuple[str, str]:
    return CHANNEL_WORLD_THREAD.get(channel_ref, ("operations", channel_ref or "operations_chief_workboard"))


def _review_decisions(decision_status: Mapping[str, Any]) -> list[dict[str, Any]]:
    history = decision_status.get("decision_history")
    rows = history if isinstance(history, list) else []
    if not rows and isinstance(decision_status.get("last_decision"), Mapping):
        rows = [decision_status["last_decision"]]
    decisions: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        action = str(row.get("decision_action") or "")
        packet_id = str(row.get("review_packet_id") or "")
        if not packet_id or action not in ACTION_EFFECTS:
            continue
        if row.get("decision_recorded") is not True and row.get("decision_accepted") is not True:
            continue
        if row.get("business_action_performed") is True or row.get("merge_performed") is True or row.get("git_push_performed") is True:
            continue
        decisions.append(dict(row))
    return decisions


def _latest_decisions_by_packet(decisions: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for decision in decisions:
        rows[str(decision["review_packet_id"])] = decision
    return rows


def _packets_by_id(packet_index: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for packet in _list(packet_index.get("packets")):
        if isinstance(packet, Mapping) and packet.get("review_packet_id"):
            rows[str(packet["review_packet_id"])] = dict(packet)
    return rows


def _packets_by_key(packets: list[dict[str, Any]], key: str) -> dict[str, list[str]]:
    rows: dict[str, list[str]] = {}
    for packet in packets:
        rows.setdefault(str(packet.get(key) or ""), []).append(str(packet.get("review_packet_id") or ""))
    return dict(sorted(rows.items()))


def _counts_by_key(packets: list[dict[str, Any]], key: str) -> dict[str, int]:
    rows: dict[str, int] = {}
    for packet in packets:
        value = str(packet.get(key) or "")
        rows[value] = rows.get(value, 0) + 1
    return dict(sorted(rows.items()))


def _decision_proof_ref(decision: Mapping[str, Any]) -> str:
    receipt_id = str(decision.get("receipt_id") or decision.get("review_packet_id") or "decision")
    return f"generated/read_models/workroom_review_decision_status.json#{receipt_id}"


def _apply_decision_to_packet(packet: Mapping[str, Any], decision: Mapping[str, Any]) -> dict[str, Any]:
    updated = _copy_json(packet)
    action = str(decision["decision_action"])
    effect = ACTION_EFFECTS[action]
    packet_status = effect["packet_status"]
    state_path = _strings(updated.get("state_path"))
    if packet_status not in state_path:
        state_path.append(packet_status)
    proof_refs = _append_unique(
        _strings(updated.get("proof_refs")),
        _decision_proof_ref(decision),
        "generated/read_models/workroom_review_decision_lifecycle_status.json",
    )
    updated.update(
        {
            "status": packet_status,
            "review_decision_status": packet_status,
            "decision_action": action,
            "decision_receipt_id": str(decision.get("receipt_id") or ""),
            "decision_recorded_at": str(decision.get("generated_at") or ""),
            "operator_decision_required": bool(effect["operator_decision_required"]),
            "visible_by_default": bool(effect["visible_by_default"]),
            "completed": bool(effect["completed"]),
            "next_safe_action": str(effect["next_safe_action"]),
            "state_path": state_path,
            "proof_refs": proof_refs,
            "proof_collapsed_by_default": True,
            "worker_inherits_speaker_authority": False,
            "merge_allowed": False,
            "push_allowed": False,
            "business_action_performed": False,
            "merge_performed": False,
            "git_push_performed": False,
            "business_state_mutation_performed": False,
        }
    )
    return updated


def _normalize_unaffected_packet(packet: Mapping[str, Any]) -> dict[str, Any]:
    updated = _copy_json(packet)
    status = str(updated.get("status") or "")
    completed = status in COMPLETED_PACKET_STATUSES
    visible_by_default = not completed
    updated.setdefault("visible_by_default", visible_by_default)
    updated.setdefault("completed", completed)
    updated.setdefault("merge_allowed", False)
    updated.setdefault("push_allowed", False)
    updated.setdefault("business_action_performed", False)
    updated.setdefault("proof_collapsed_by_default", True)
    updated.setdefault("worker_inherits_speaker_authority", False)
    return updated


def apply_decisions_to_packet_index(
    packet_index: Mapping[str, Any],
    decisions_by_packet: Mapping[str, dict[str, Any]],
    *,
    generated_at: str,
) -> dict[str, Any]:
    updated_index = _copy_json(packet_index)
    packets: list[dict[str, Any]] = []
    updated_packet_ids: list[str] = []
    for packet in _list(packet_index.get("packets")):
        if not isinstance(packet, Mapping):
            continue
        packet_id = str(packet.get("review_packet_id") or "")
        decision = decisions_by_packet.get(packet_id)
        if decision:
            packets.append(_apply_decision_to_packet(packet, decision))
            updated_packet_ids.append(packet_id)
        else:
            packets.append(_normalize_unaffected_packet(packet))
    packets.sort(key=lambda packet: (str(packet.get("channel_ref") or ""), str(packet.get("worker_ref") or ""), str(packet.get("package_id") or "")))
    open_packets = [packet for packet in packets if packet.get("visible_by_default") is True]
    completed_packets = [packet for packet in packets if packet.get("completed") is True]
    fields = _append_unique(
        _strings(updated_index.get("review_packet_fields")),
        "visible_by_default",
        "completed",
        "review_decision_status",
        "decision_action",
        "decision_receipt_id",
        "decision_recorded_at",
    )
    source_refs = _append_unique(
        _strings(updated_index.get("source_refs")),
        "generated/read_models/workroom_review_decision_status.json",
        "generated/read_models/workroom_review_decision_lifecycle_status.json",
    )
    machine_proof = dict(updated_index.get("machine_proof") if isinstance(updated_index.get("machine_proof"), Mapping) else {})
    machine_proof.update(
        {
            "decision_lifecycle_applied": True,
            "decision_updated_packet_count": len(updated_packet_ids),
            "completed_packets_hidden_by_default": all(packet.get("visible_by_default") is False for packet in completed_packets),
            "open_packets_visible_by_default": all(packet.get("visible_by_default") is True for packet in open_packets),
            "all_open_packets_require_operator_decision": all(packet.get("operator_decision_required") is True for packet in open_packets),
            "all_packets_require_operator_decision": all(packet.get("operator_decision_required") is True for packet in packets),
            "merge_performed": False,
            "git_push_performed": False,
            "business_action_performed": False,
            "business_state_mutation_performed": False,
            "unsafe_true_grants_absent": all(value is False for value in AUTHORITY_BOUNDARY.values()),
        }
    )
    updated_index.update(
        {
            "generated_at": generated_at,
            "review_packet_fields": fields,
            "review_packet_count": len(packets),
            "packets_by_channel": _packets_by_key(packets, "channel_ref"),
            "packets_by_worker": _packets_by_key(packets, "worker_ref"),
            "packet_counts_by_status": _counts_by_key(packets, "status"),
            "open_review_packet_ids": [str(packet["review_packet_id"]) for packet in open_packets],
            "completed_review_packet_ids": [str(packet["review_packet_id"]) for packet in completed_packets],
            "decision_lifecycle": {
                "applied": True,
                "updated_packet_ids": updated_packet_ids,
                "decision_source_ref": "generated/read_models/workroom_review_decision_status.json",
                "lifecycle_status_ref": "generated/read_models/workroom_review_decision_lifecycle_status.json",
            },
            "packets": packets,
            "source_refs": source_refs,
            "machine_proof": machine_proof,
        }
    )
    rules = _strings(updated_index.get("review_rules"))
    updated_index["review_rules"] = _append_unique(
        rules,
        "Recorded review decisions update packet visibility without merge, push, worker spawn, or business action authority.",
        "Completed review packets are hidden by default; rework packets remain visible.",
    )
    return updated_index


def _posts_by_channel(posts: list[dict[str, Any]]) -> dict[str, list[str]]:
    rows: dict[str, list[str]] = {}
    for post in posts:
        rows.setdefault(str(post.get("channel_ref") or ""), []).append(str(post.get("post_id") or ""))
    return dict(sorted(rows.items()))


def _channel_post_counts(posts: list[dict[str, Any]]) -> dict[str, int]:
    rows: dict[str, int] = {}
    for post in posts:
        channel = str(post.get("channel_ref") or "")
        rows[channel] = rows.get(channel, 0) + 1
    return dict(sorted(rows.items()))


def _decision_status_from_action(action: str) -> str:
    return str(ACTION_EFFECTS[action]["packet_status"])


def _decision_post(decision: Mapping[str, Any], packet: Mapping[str, Any], generated_at: str) -> dict[str, Any]:
    action = str(decision["decision_action"])
    effect = ACTION_EFFECTS[action]
    channel_ref = str(packet.get("channel_ref") or "operations_chief_workboard")
    world_ref, thread_ref = _channel_world_thread(channel_ref)
    display = decision.get("operator_display") if isinstance(decision.get("operator_display"), Mapping) else {}
    receipt_id = str(decision.get("receipt_id") or decision.get("review_packet_id") or action)
    proof_refs = _append_unique(
        _strings(decision.get("proof_refs")),
        _decision_proof_ref(decision),
        "generated/read_models/workroom_review_decision_lifecycle_status.json",
    )
    return {
        "post_id": f"workroom_post:{_short_hash(['workroom_review_decision_lifecycle', receipt_id, channel_ref])}",
        "source_kind": "workroom_review_decision_lifecycle",
        "channel_ref": channel_ref,
        "timestamp": str(decision.get("generated_at") or generated_at),
        "speaker_ref": "chief",
        "post_type": "decision",
        "headline": str(display.get("headline") or effect["post_headline"]),
        "plain_summary": str(display.get("plain_summary") or effect["post_summary"]),
        "status_label": _status_label(effect["packet_status"]),
        "next_safe_action": str(effect["next_safe_action"]),
        "target_world_ref": world_ref,
        "target_thread_ref": thread_ref,
        "package_id": str(packet.get("package_id") or ""),
        "review_packet_id": str(decision["review_packet_id"]),
        "decision_action": action,
        "decision_receipt_id": receipt_id,
        "review_decision_status": effect["packet_status"],
        "visible_by_default": bool(effect["visible_by_default"]),
        "completed": bool(effect["completed"]),
        "proof_refs": proof_refs,
        "proof_refs_collapsed": True,
        "show_machine_details_by_default": False,
        "business_action_performed": False,
    }


def _post_matches_packet(post: Mapping[str, Any], packet: Mapping[str, Any]) -> bool:
    post_packet_id = str(post.get("review_packet_id") or "")
    if post_packet_id and post_packet_id == str(packet.get("review_packet_id") or ""):
        return True
    return (
        str(post.get("post_type") or "") == "review_packet"
        and str(post.get("package_id") or "") == str(packet.get("package_id") or "")
        and str(post.get("channel_ref") or "") == str(packet.get("channel_ref") or "")
    )


def _update_review_post(post: Mapping[str, Any], packet: Mapping[str, Any], decision: Mapping[str, Any]) -> dict[str, Any]:
    updated = _copy_json(post)
    action = str(decision["decision_action"])
    effect = ACTION_EFFECTS[action]
    updated.update(
        {
            "review_packet_id": str(packet.get("review_packet_id") or decision.get("review_packet_id") or ""),
            "review_decision_status": effect["packet_status"],
            "decision_action": action,
            "decision_receipt_id": str(decision.get("receipt_id") or ""),
            "status_label": _status_label(effect["packet_status"]),
            "next_safe_action": str(effect["next_safe_action"]),
            "visible_by_default": bool(effect["visible_by_default"]),
            "completed": bool(effect["completed"]),
            "proof_refs": _append_unique(
                _strings(updated.get("proof_refs")),
                _decision_proof_ref(decision),
                "generated/read_models/workroom_review_decision_lifecycle_status.json",
            ),
            "proof_refs_collapsed": True,
            "show_machine_details_by_default": False,
            "business_action_performed": False,
        }
    )
    return updated


def apply_decisions_to_activity_feed(
    activity_feed: Mapping[str, Any],
    decisions_by_packet: Mapping[str, dict[str, Any]],
    packets_by_id: Mapping[str, dict[str, Any]],
    *,
    generated_at: str,
) -> dict[str, Any]:
    updated_feed = _copy_json(activity_feed)
    decision_posts: list[dict[str, Any]] = []
    posts: list[dict[str, Any]] = []
    for post in _list(activity_feed.get("posts")):
        if not isinstance(post, Mapping):
            continue
        if str(post.get("source_kind") or "") == "workroom_review_decision_lifecycle":
            continue
        replacement: dict[str, Any] | None = None
        for packet_id, decision in decisions_by_packet.items():
            packet = packets_by_id.get(packet_id)
            if packet and _post_matches_packet(post, packet):
                replacement = _update_review_post(post, packet, decision)
                break
        posts.append(replacement if replacement is not None else _copy_json(post))
    for packet_id, decision in decisions_by_packet.items():
        packet = packets_by_id.get(packet_id)
        if not packet:
            continue
        decision_posts.append(_decision_post(decision, packet, generated_at))
    posts.extend(decision_posts)
    posts.sort(key=lambda post: (str(post.get("timestamp") or ""), str(post.get("post_id") or "")))
    source_refs = _append_unique(
        _strings(updated_feed.get("source_refs")),
        "generated/read_models/workroom_review_decision_status.json",
        "generated/read_models/workroom_review_decision_lifecycle_status.json",
    )
    machine_proof = dict(updated_feed.get("machine_proof") if isinstance(updated_feed.get("machine_proof"), Mapping) else {})
    machine_proof.update(
        {
            "decision_lifecycle_applied": True,
            "decision_post_count": len(decision_posts),
            "proof_refs_collapsed_by_default": True,
            "new_business_truth_created": False,
            "merge_performed": False,
            "git_push_performed": False,
            "worker_spawn_performed": False,
            "business_action_performed": False,
            "unsafe_true_grants_absent": all(value is False for value in AUTHORITY_BOUNDARY.values()),
        }
    )
    updated_feed.update(
        {
            "generated_at": generated_at,
            "post_count": len(posts),
            "channel_post_counts": _channel_post_counts(posts),
            "posts_by_channel": _posts_by_channel(posts),
            "posts": posts,
            "source_refs": source_refs,
            "decision_lifecycle": {
                "applied": True,
                "decision_post_ids": [post["post_id"] for post in decision_posts],
                "decision_source_ref": "generated/read_models/workroom_review_decision_status.json",
                "lifecycle_status_ref": "generated/read_models/workroom_review_decision_lifecycle_status.json",
            },
            "machine_proof": machine_proof,
        }
    )
    rules = _strings(updated_feed.get("rules"))
    updated_feed["rules"] = _append_unique(
        rules,
        "Decision posts summarize review receipts only and create no business truth.",
        "Completed review packet posts are hidden by default; rework remains visible.",
    )
    return updated_feed


def build_lifecycle_read_models(
    *,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
    generated_at: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    generated_at = generated_at or utc_now()
    preconditions = _preconditions(read_model_root)
    preconditions_ready = all(item["ready"] for item in preconditions)
    payloads = _source_payloads(read_model_root)
    packet_index = payloads.get("workroom_review_packet_index", {})
    activity_feed = payloads.get("openclaw_workroom_activity_feed", {})
    decision_status = payloads.get("workroom_review_decision_status", {})
    decisions = _review_decisions(decision_status) if preconditions_ready else []
    decisions_by_packet = _latest_decisions_by_packet(decisions)
    base_packets_by_id = _packets_by_id(packet_index)
    updated_packet_index = apply_decisions_to_packet_index(packet_index, decisions_by_packet, generated_at=generated_at)
    updated_feed = apply_decisions_to_activity_feed(
        activity_feed,
        decisions_by_packet,
        base_packets_by_id,
        generated_at=generated_at,
    )
    updated_packet_ids = list(decisions_by_packet)
    status = LIFECYCLE_STATUS if preconditions_ready else LIFECYCLE_NOT_READY_STATUS
    lifecycle_status = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "generated_at": generated_at,
        "status": status,
        "purpose": "Applies Workroom review decisions to packet visibility/status and adds compact Workroom decision posts.",
        "mode": "local_generated_read_model_overlay_only_no_merge_push_or_business_action",
        "preconditions": preconditions,
        "decision_count": len(decisions),
        "updated_packet_count": len(updated_packet_ids),
        "updated_packet_ids": updated_packet_ids,
        "decision_posts_added": [
            post["post_id"]
            for post in updated_feed.get("posts", [])
            if isinstance(post, Mapping) and post.get("source_kind") == "workroom_review_decision_lifecycle"
        ],
        "packet_status_counts": updated_packet_index.get("packet_counts_by_status", {}),
        "open_review_packet_ids": updated_packet_index.get("open_review_packet_ids", []),
        "completed_review_packet_ids": updated_packet_index.get("completed_review_packet_ids", []),
        "source_refs": [
            "generated/read_models/workroom_review_decision_status.json",
            "generated/read_models/workroom_review_packet_index.json",
            "generated/read_models/openclaw_workroom_activity_feed.json",
        ],
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "machine_proof": {
            "local_only": True,
            "generated_read_model_overlay_only": True,
            "preconditions_ready": preconditions_ready,
            "review_packets_updated": len(updated_packet_ids),
            "activity_decision_posts_added": len(decisions_by_packet),
            "proof_refs_collapsed_by_default": True,
            "new_business_truth_created": False,
            "merge_performed": False,
            "git_push_performed": False,
            "worker_spawn_performed": False,
            "child_agent_run_performed": False,
            "email_send_performed": False,
            "gmail_access_performed": False,
            "browser_access_performed": False,
            "coupa_access_performed": False,
            "ledger_mutation_performed": False,
            "workbook_mutation_performed": False,
            "pdf_export_performed": False,
            "submit_performed": False,
            "paid_marking_performed": False,
            "business_action_performed": False,
            "business_state_mutation_performed": False,
            "unsafe_true_grants_absent": all(value is False for value in AUTHORITY_BOUNDARY.values()),
        },
    }
    return updated_packet_index, updated_feed, lifecycle_status


def build_wiki(lifecycle_status: Mapping[str, Any]) -> str:
    lines = [
        "# Workroom Review Decision Lifecycle",
        "",
        f"Status: `{lifecycle_status['status']}`",
        "",
        "This read model overlay applies recorded review decisions to Workroom review packet visibility and activity posts.",
        "",
        f"Decisions applied: `{lifecycle_status['decision_count']}`",
        f"Packets updated: `{lifecycle_status['updated_packet_count']}`",
        "",
        "## Packet Status Counts",
        "",
    ]
    for status, count in lifecycle_status.get("packet_status_counts", {}).items():
        lines.append(f"- `{status}`: `{count}`")
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            "- Approval records review only and hides completed packets by default.",
            "- Rework keeps the packet visible for follow-up review.",
            "- Informational review closes the packet without action.",
            "- No merge.",
            "- No git push.",
            "- No worker spawn or child agent run.",
            "- No email send.",
            "- No Gmail/browser/Coupa access.",
            "- No ledger or workbook mutation.",
            "- No PDF export.",
            "- No submit or mark-paid.",
            "- No business truth is created.",
            "- Proof refs remain collapsed.",
        ]
    )
    return "\n".join(lines) + "\n"


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(stable_json(payload), encoding="utf-8")


def export_workroom_review_decision_lifecycle(
    *,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
    export_root: Path = DEFAULT_EXPORT_ROOT,
    bridge_export_root: Path | None = DEFAULT_BRIDGE_EXPORT_ROOT,
    wiki_path: Path = DEFAULT_WIKI_PATH,
    generated_at: str | None = None,
) -> dict[str, str]:
    packet_index, activity_feed, lifecycle_status = build_lifecycle_read_models(
        read_model_root=read_model_root,
        generated_at=generated_at,
    )
    export_root = _rooted(export_root)
    packet_path = export_root / PACKET_INDEX_EXPORT_NAME
    feed_path = export_root / ACTIVITY_FEED_EXPORT_NAME
    status_path = export_root / JSON_EXPORT_NAME
    _write_json(packet_path, packet_index)
    _write_json(feed_path, activity_feed)
    _write_json(status_path, lifecycle_status)

    bridge_packet_path = ""
    bridge_feed_path = ""
    bridge_status_path = ""
    if bridge_export_root is not None:
        bridge_export_root.mkdir(parents=True, exist_ok=True)
        bridge_packet = bridge_export_root / PACKET_INDEX_EXPORT_NAME
        bridge_feed = bridge_export_root / ACTIVITY_FEED_EXPORT_NAME
        bridge_status = bridge_export_root / JSON_EXPORT_NAME
        _write_json(bridge_packet, packet_index)
        _write_json(bridge_feed, activity_feed)
        _write_json(bridge_status, lifecycle_status)
        bridge_packet_path = bridge_packet.as_posix()
        bridge_feed_path = bridge_feed.as_posix()
        bridge_status_path = bridge_status.as_posix()

    wiki_path = _rooted(wiki_path)
    wiki_path.parent.mkdir(parents=True, exist_ok=True)
    wiki_path.write_text(build_wiki(lifecycle_status), encoding="utf-8")
    return {
        "status": str(lifecycle_status["status"]),
        "packet_index_path": packet_path.as_posix(),
        "activity_feed_path": feed_path.as_posix(),
        "lifecycle_status_path": status_path.as_posix(),
        "bridge_packet_index_path": bridge_packet_path,
        "bridge_activity_feed_path": bridge_feed_path,
        "bridge_lifecycle_status_path": bridge_status_path,
        "wiki_path": wiki_path.as_posix(),
        "updated_packet_count": str(lifecycle_status["updated_packet_count"]),
        "decision_count": str(lifecycle_status["decision_count"]),
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Export Workroom Review Decision Lifecycle V0.")
    parser.add_argument("--read-model-root", default=str(DEFAULT_READ_MODEL_ROOT))
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT))
    parser.add_argument("--bridge-export-root", default=str(DEFAULT_BRIDGE_EXPORT_ROOT))
    parser.add_argument("--wiki-path", default=str(DEFAULT_WIKI_PATH))
    parser.add_argument("--generated-at")
    parser.add_argument("--no-bridge", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    result = export_workroom_review_decision_lifecycle(
        read_model_root=Path(args.read_model_root),
        export_root=Path(args.export_root),
        bridge_export_root=None if args.no_bridge else Path(args.bridge_export_root),
        wiki_path=Path(args.wiki_path),
        generated_at=args.generated_at,
    )
    print(stable_json(result), end="")
    return 0 if result["status"] == LIFECYCLE_STATUS else 2


if __name__ == "__main__":
    raise SystemExit(main())
