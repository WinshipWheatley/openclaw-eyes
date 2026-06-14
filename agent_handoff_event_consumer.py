"""Agent Handoff Event Consumer V0.

Records deterministic OpenClaw agent-to-agent and agent-to-worker handoff
events without executing downstream work. The consumer validates handoff rules
against the Agent Handoff Registry and channel refs against the Workroom
Registry, writes generated read-model receipts, and appends compact local
Workroom activity posts. It does not assign or run workers, execute tools,
connect providers, send messages or email, open browser/Gmail/Coupa, mutate
ledgers or workbooks, export PDFs, submit portals, mark paid, or push git state.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parent
DEFAULT_READ_MODEL_ROOT = Path("generated/read_models")
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_BRIDGE_EXPORT_ROOT = Path("/mnt/e/openclaw/generated/read_models")
DEFAULT_WIKI_PATH = Path("generated/wiki/openclaw/Agent Handoff Event Consumer.md")

SCHEMA_VERSION = "agent_handoff_event_consumer_v0"
READ_MODEL_ID = "agent_handoff_event_status"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
CONSUMER_STATUS = "AGENT_HANDOFF_EVENT_CONSUMER_READY"
CONSUMER_NOT_READY_STATUS = "AGENT_HANDOFF_EVENT_CONSUMER_NOT_READY"

REQUEST_TYPE = "AGENT_HANDOFF_EVENT_REQUEST_V0"
ACTIVITY_FEED_EXPORT_NAME = "openclaw_workroom_activity_feed.json"

PRECONDITION_FILES = {
    "agent_handoff_registry": "agent_handoff_registry.json",
    "openclaw_workroom_registry": "openclaw_workroom_registry.json",
    "package_event_index": "package_event_index.json",
}

PRECONDITION_STATUSES = {
    "agent_handoff_registry": "AGENT_HANDOFF_REGISTRY_READY",
    "openclaw_workroom_registry": "OPENCLAW_WORKROOM_REGISTRY_READY",
    "package_event_index": "PACKAGE_EVENT_INDEX_READY",
}

SOURCE_SURFACES = {"mission_control", "system", "codex"}

AUTHORITY_BOUNDARY = {
    "external_tool_connect_allowed": False,
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
    "authority_grant_allowed": False,
    "credential_use_allowed": False,
    "worker_spawn_allowed": False,
    "worker_assignment_allowed": False,
    "agent_loop_allowed": False,
    "external_llm_allowed": False,
    "live_provider_allowed": False,
    "tool_execution_allowed": False,
    "git_push_allowed": False,
    "business_action_allowed": False,
    "sent": False,
    "paid": False,
}

UNSAFE_REQUEST_KEYS = set(AUTHORITY_BOUNDARY) | {
    "push_allowed",
    "merge_allowed",
    "worker_assigned",
    "worker_execution_allowed",
    "worker_execution_performed",
    "tool_execution_performed",
    "business_action_performed",
    "submit_performed",
    "email_send_performed",
}


@dataclass(frozen=True)
class AgentHandoffEventResult:
    status: str
    request_id: str
    request_filename: str
    event: dict[str, Any] | None
    blockers: tuple[str, ...]
    response_primary_status: str
    next_safe_action: str
    receipt: dict[str, Any]


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


def _request_id(raw_request: Mapping[str, Any], filename: str) -> str:
    return str(
        raw_request.get("request_id")
        or raw_request.get("source_request_id")
        or f"agent_handoff_event:{filename or _short_hash([stable_json(raw_request)])}"
    )


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
    payloads = {
        ref: _load_json(root / filename)
        for ref, filename in PRECONDITION_FILES.items()
    }
    payloads["openclaw_workroom_activity_feed"] = _load_json(root / ACTIVITY_FEED_EXPORT_NAME)
    return payloads


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _strings(value: Any) -> list[str]:
    return [str(item) for item in _list(value) if str(item)]


def _append_unique(values: list[str], *extra: str) -> list[str]:
    merged = list(values)
    merged.extend(str(item) for item in extra if str(item))
    return list(dict.fromkeys(merged))


def _handoffs_by_ref(registry: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for handoff in _list(registry.get("handoffs")):
        if isinstance(handoff, Mapping) and handoff.get("handoff_ref"):
            rows[str(handoff["handoff_ref"])] = dict(handoff)
    return rows


def _channels_by_ref(workroom_registry: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for channel in _list(workroom_registry.get("channels")):
        if isinstance(channel, Mapping) and channel.get("channel_ref"):
            rows[str(channel["channel_ref"])] = dict(channel)
    return rows


def _authority_true_grants(raw_request: Mapping[str, Any]) -> list[str]:
    grants: list[str] = []
    authority = raw_request.get("authority_boundary")
    if isinstance(authority, Mapping):
        for key, value in authority.items():
            if value is True:
                grants.append(str(key))
    for key, value in raw_request.items():
        if key in UNSAFE_REQUEST_KEYS and value is True:
            grants.append(str(key))
    return sorted(dict.fromkeys(grants))


def _validate_handoff_request(
    raw_request: Mapping[str, Any],
    *,
    preconditions: list[dict[str, Any]],
    handoff_registry: Mapping[str, Any],
    workroom_registry: Mapping[str, Any],
) -> tuple[str, list[str], dict[str, Any] | None, dict[str, Any] | None, list[str]]:
    blockers: list[str] = []
    unsafe_true_grants = _authority_true_grants(raw_request)
    handoff_ref = str(raw_request.get("handoff_ref") or "")
    channel_ref = str(raw_request.get("channel_ref") or "")
    from_agent = str(raw_request.get("from_agent") or "").lower()
    to_agent_or_worker = str(raw_request.get("to_agent_or_worker") or "").lower()
    package_type = str(raw_request.get("package_type") or "")
    source_surface = str(raw_request.get("source_surface") or "").lower()
    request_type = str(raw_request.get("request_type") or "")

    if not all(item["ready"] for item in preconditions):
        blockers.extend(
            f"precondition_not_ready:{item['precondition_ref']}"
            for item in preconditions
            if not item["ready"]
        )
        return "BLOCKED_PRECONDITION_NOT_READY", blockers, None, None, unsafe_true_grants

    if request_type != REQUEST_TYPE:
        blockers.append("invalid_request_type")
    if source_surface not in SOURCE_SURFACES:
        blockers.append("invalid_source_surface")
    if not isinstance(raw_request.get("authority_boundary"), Mapping):
        blockers.append("missing_authority_boundary")
    if unsafe_true_grants:
        blockers.extend(f"unsafe_true_grant:{key}" for key in unsafe_true_grants)
        return "BLOCKED_UNSAFE_AUTHORITY", blockers, None, None, unsafe_true_grants

    handoff = _handoffs_by_ref(handoff_registry).get(handoff_ref)
    if handoff is None:
        blockers.append("unknown_handoff_ref")
    else:
        expected = {
            "from_agent": str(handoff.get("from_agent") or "").lower(),
            "to_agent_or_worker": str(handoff.get("to_agent_or_worker") or "").lower(),
            "channel_ref": str(handoff.get("channel_ref") or ""),
            "package_type": str(handoff.get("package_type") or ""),
        }
        observed = {
            "from_agent": from_agent,
            "to_agent_or_worker": to_agent_or_worker,
            "channel_ref": channel_ref,
            "package_type": package_type,
        }
        for key, expected_value in expected.items():
            if observed[key] != expected_value:
                blockers.append(f"handoff_{key}_mismatch")

    channel = _channels_by_ref(workroom_registry).get(channel_ref)
    if channel is None:
        blockers.append("unknown_channel_ref")
    elif handoff is not None and str(handoff.get("channel_ref") or "") != channel_ref:
        blockers.append("handoff_channel_not_in_registry")

    if blockers:
        return "BLOCKED_INVALID_HANDOFF", blockers, handoff, channel, unsafe_true_grants
    return "HANDOFF_EVENT_RECORDED", blockers, handoff, channel, unsafe_true_grants


def _operator_display(
    *,
    status: str,
    from_agent: str,
    to_agent_or_worker: str,
    handoff_ref: str,
    blockers: list[str],
    unsafe_true_grants: list[str],
) -> dict[str, Any]:
    if status == "BLOCKED_UNSAFE_AUTHORITY":
        return {
            "speaker_ref": "guardian",
            "voice_profile_ref": "agent_voice_profile:guardian",
            "voice_mode": "safety_gate",
            "audience": "internal_operator",
            "headline": "Handoff blocked",
            "status_label": "Blocked",
            "tone": "blocked",
            "plain_summary": "Guardian blocked this handoff because it requested authority outside receipt recording.",
            "next_safe_action": "Remove worker execution, tool execution, send, submit, ledger, paid, or push authority and resend.",
            "proof_caption": "Proof available.",
            "proof_refs_collapsed": True,
            "show_machine_details_by_default": False,
            "routing_reason": "protected authority boundary",
            "secondary_facts": [f"Unsafe grant: {key}" for key in unsafe_true_grants],
        }
    if status != "HANDOFF_EVENT_RECORDED":
        return {
            "speaker_ref": "chief",
            "voice_profile_ref": "agent_voice_profile:chief",
            "voice_mode": "diagnostic",
            "audience": "internal_operator",
            "headline": "Handoff blocked",
            "status_label": "Blocked",
            "tone": "blocked",
            "plain_summary": "Chief could not record the handoff because it did not match the local registry.",
            "next_safe_action": "Choose a registered handoff and channel, then resend without execution authority.",
            "proof_caption": "Proof available.",
            "proof_refs_collapsed": True,
            "show_machine_details_by_default": False,
            "routing_reason": "handoff registry diagnostics",
            "secondary_facts": list(blockers),
        }
    return {
        "speaker_ref": "chief",
        "voice_profile_ref": "agent_voice_profile:chief",
        "voice_mode": "diagnostic",
        "audience": "internal_operator",
        "headline": "Handoff recorded",
        "status_label": "Handoff recorded",
        "tone": "calm",
        "plain_summary": f"Chief recorded {from_agent} to {to_agent_or_worker} as a handoff receipt only.",
        "next_safe_action": "Review the handoff packet; downstream work has not run.",
        "proof_caption": "Proof available.",
        "proof_refs_collapsed": True,
        "show_machine_details_by_default": False,
        "routing_reason": "deterministic handoff event",
        "primary_fact": f"Handoff ref: {handoff_ref}.",
        "secondary_facts": [
            "No worker was assigned or executed.",
            "No tools or business action ran.",
        ],
    }


def _receipt(
    raw_request: Mapping[str, Any],
    *,
    source_request_filename: str,
    generated_at: str,
    read_model_root: Path,
) -> dict[str, Any]:
    request_id = _request_id(raw_request, source_request_filename)
    payloads = _source_payloads(read_model_root)
    preconditions = _preconditions(read_model_root)
    status, blockers, handoff, channel, unsafe_true_grants = _validate_handoff_request(
        raw_request,
        preconditions=preconditions,
        handoff_registry=payloads.get("agent_handoff_registry", {}),
        workroom_registry=payloads.get("openclaw_workroom_registry", {}),
    )
    from_agent = str(raw_request.get("from_agent") or "").lower()
    to_agent_or_worker = str(raw_request.get("to_agent_or_worker") or "").lower()
    channel_ref = str(raw_request.get("channel_ref") or "")
    handoff_ref = str(raw_request.get("handoff_ref") or "")
    package_type = str(raw_request.get("package_type") or "")
    event_recorded = status == "HANDOFF_EVENT_RECORDED"
    event_id = f"agent_handoff_event:{_short_hash([request_id, handoff_ref, from_agent, to_agent_or_worker, generated_at])}"
    proof_refs = [
        "generated/read_models/agent_handoff_registry.json",
        "generated/read_models/openclaw_workroom_registry.json",
        "generated/read_models/package_event_index.json",
        "generated/read_models/agent_handoff_event_status.json",
    ]
    operator_display = _operator_display(
        status=status,
        from_agent=from_agent,
        to_agent_or_worker=to_agent_or_worker,
        handoff_ref=handoff_ref,
        blockers=blockers,
        unsafe_true_grants=unsafe_true_grants,
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "receipt_type": "AGENT_HANDOFF_EVENT_RECEIPT",
        "receipt_id": f"agent_handoff_event_receipt:{_short_hash([event_id, status])}",
        "event_id": event_id,
        "generated_at": generated_at,
        "request_id": request_id,
        "source_request_filename": source_request_filename,
        "request_type": REQUEST_TYPE,
        "source_surface": str(raw_request.get("source_surface") or ""),
        "status": status,
        "raw_internal_status": "RESPONSE_READY" if event_recorded else "BLOCKED_WITH_REASON",
        "event_recorded": event_recorded,
        "handoff_ref": handoff_ref,
        "from_agent": from_agent,
        "to_agent_or_worker": to_agent_or_worker,
        "channel_ref": channel_ref,
        "reason": str(raw_request.get("reason") or ""),
        "package_type": package_type,
        "handoff_registry_match": handoff,
        "workroom_channel": channel,
        "blockers": blockers,
        "unsafe_true_grants": unsafe_true_grants,
        "operator_display": operator_display,
        "speaker_ref": operator_display["speaker_ref"],
        "voice_profile_ref": operator_display["voice_profile_ref"],
        "voice_mode": operator_display["voice_mode"],
        "response_primary_status": str(operator_display["status_label"]),
        "next_safe_action": str(operator_display["next_safe_action"]),
        "proof_refs": proof_refs,
        "proof_refs_collapsed": True,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "downstream_worker_assigned": False,
        "worker_assignment_performed": False,
        "worker_execution_performed": False,
        "tool_execution_performed": False,
        "external_tool_connect_performed": False,
        "message_send_performed": False,
        "email_send_performed": False,
        "gmail_access_performed": False,
        "browser_access_performed": False,
        "coupa_access_performed": False,
        "ledger_mutation_performed": False,
        "workbook_mutation_performed": False,
        "pdf_export_performed": False,
        "submit_performed": False,
        "paid_marking_performed": False,
        "git_push_performed": False,
        "business_action_performed": False,
        "business_state_mutation_performed": False,
        "read_model_paths": {
            "local_status_path": "",
            "bridge_status_path": "",
            "local_activity_feed_path": "",
            "bridge_activity_feed_path": "",
            "wiki_path": "",
        },
    }


def _event_from_receipt(receipt: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "event_id": str(receipt.get("event_id") or ""),
        "receipt_id": str(receipt.get("receipt_id") or ""),
        "generated_at": str(receipt.get("generated_at") or ""),
        "request_id": str(receipt.get("request_id") or ""),
        "source_surface": str(receipt.get("source_surface") or ""),
        "handoff_ref": str(receipt.get("handoff_ref") or ""),
        "from_agent": str(receipt.get("from_agent") or ""),
        "to_agent_or_worker": str(receipt.get("to_agent_or_worker") or ""),
        "channel_ref": str(receipt.get("channel_ref") or ""),
        "reason": str(receipt.get("reason") or ""),
        "package_type": str(receipt.get("package_type") or ""),
        "status": str(receipt.get("status") or ""),
        "proof_refs": list(receipt.get("proof_refs") or []),
        "proof_refs_collapsed": True,
        "downstream_worker_assigned": False,
        "worker_assignment_performed": False,
        "worker_execution_performed": False,
        "tool_execution_performed": False,
        "business_action_performed": False,
    }


def _existing_status(export_root: Path) -> dict[str, Any]:
    return _load_json(_rooted(export_root) / JSON_EXPORT_NAME)


def build_status_read_model(
    *,
    receipt: Mapping[str, Any] | None = None,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
    export_root: Path = DEFAULT_EXPORT_ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    preconditions = _preconditions(read_model_root)
    preconditions_ready = all(item["ready"] for item in preconditions)
    existing = _existing_status(export_root)
    event_history = [
        dict(item)
        for item in _list(existing.get("event_history"))
        if isinstance(item, Mapping)
    ]
    attempt_history = [
        dict(item)
        for item in _list(existing.get("attempt_history"))
        if isinstance(item, Mapping)
    ]
    if isinstance(receipt, Mapping):
        receipt_id = str(receipt.get("receipt_id") or "")
        attempt_history = [item for item in attempt_history if str(item.get("receipt_id") or "") != receipt_id]
        attempt_history.append(dict(receipt))
        if receipt.get("event_recorded") is True:
            event = _event_from_receipt(receipt)
            event_history = [item for item in event_history if str(item.get("event_id") or "") != str(event["event_id"])]
            event_history.append(event)
    event_history = event_history[-200:]
    attempt_history = attempt_history[-200:]
    status = CONSUMER_STATUS if preconditions_ready else CONSUMER_NOT_READY_STATUS
    return {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "generated_at": generated_at,
        "status": status,
        "purpose": "Generated receipts for deterministic agent handoff events. Downstream work is not executed.",
        "mode": "local_generated_event_receipts_only_no_worker_execution",
        "request_type": REQUEST_TYPE,
        "preconditions": preconditions,
        "event_count": len(event_history),
        "attempt_count": len(attempt_history),
        "last_event": event_history[-1] if event_history else None,
        "last_attempt": attempt_history[-1] if attempt_history else None,
        "event_history": event_history,
        "attempt_history": attempt_history,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "source_refs": [
            "generated/read_models/agent_handoff_registry.json",
            "generated/read_models/openclaw_workroom_registry.json",
            "generated/read_models/package_event_index.json",
            "generated/read_models/openclaw_workroom_activity_feed.json",
        ],
        "machine_proof": {
            "local_only": True,
            "generated_receipt_only": True,
            "preconditions_ready": preconditions_ready,
            "handoff_registry_validated": bool(receipt and receipt.get("handoff_registry_match")),
            "workroom_channel_validated": bool(receipt and receipt.get("workroom_channel")),
            "unsafe_authority_rejected": bool(receipt and receipt.get("status") == "BLOCKED_UNSAFE_AUTHORITY"),
            "downstream_worker_assigned": False,
            "worker_assignment_performed": False,
            "worker_execution_performed": False,
            "tool_execution_performed": False,
            "external_tool_connect_performed": False,
            "message_send_performed": False,
            "email_send_performed": False,
            "gmail_access_performed": False,
            "browser_access_performed": False,
            "coupa_access_performed": False,
            "ledger_mutation_performed": False,
            "workbook_mutation_performed": False,
            "pdf_export_performed": False,
            "submit_performed": False,
            "paid_marking_performed": False,
            "git_push_performed": False,
            "business_action_performed": False,
            "business_state_mutation_performed": False,
            "unsafe_true_grants_absent": all(value is False for value in AUTHORITY_BOUNDARY.values()),
        },
    }


def _posts_by_channel(posts: list[dict[str, Any]]) -> dict[str, list[str]]:
    rows: dict[str, list[str]] = {}
    for post in posts:
        rows.setdefault(str(post.get("channel_ref") or ""), []).append(str(post.get("post_id") or ""))
    return dict(sorted(rows.items()))


def _channel_post_counts(posts: list[dict[str, Any]]) -> dict[str, int]:
    rows: dict[str, int] = {}
    for post in posts:
        channel_ref = str(post.get("channel_ref") or "")
        rows[channel_ref] = rows.get(channel_ref, 0) + 1
    return dict(sorted(rows.items()))


def _event_post(receipt: Mapping[str, Any]) -> dict[str, Any]:
    channel = receipt.get("workroom_channel") if isinstance(receipt.get("workroom_channel"), Mapping) else {}
    event_id = str(receipt.get("event_id") or "")
    channel_ref = str(receipt.get("channel_ref") or "")
    from_agent = str(receipt.get("from_agent") or "")
    to_agent = str(receipt.get("to_agent_or_worker") or "")
    return {
        "post_id": f"workroom_post:{_short_hash(['agent_handoff_event', event_id, channel_ref])}",
        "source_kind": "agent_handoff_event",
        "channel_ref": channel_ref,
        "timestamp": str(receipt.get("generated_at") or utc_now()),
        "speaker_ref": from_agent or "openclaw",
        "post_type": "handoff",
        "headline": f"Handoff: {from_agent} to {to_agent}",
        "plain_summary": str(receipt.get("reason") or "A deterministic handoff event was recorded."),
        "status_label": "Handoff Recorded",
        "next_safe_action": "Review the handoff packet; downstream work has not run.",
        "target_world_ref": str(channel.get("world_ref") or "operations"),
        "target_thread_ref": str(channel.get("thread_ref") or channel_ref),
        "package_id": "",
        "handoff_ref": str(receipt.get("handoff_ref") or ""),
        "from_agent": from_agent,
        "to_agent_or_worker": to_agent,
        "package_type": str(receipt.get("package_type") or ""),
        "proof_refs": list(dict.fromkeys(receipt.get("proof_refs") or [])),
        "proof_refs_collapsed": True,
        "show_machine_details_by_default": False,
        "business_action_performed": False,
        "downstream_worker_assigned": False,
        "worker_execution_performed": False,
        "tool_execution_performed": False,
    }


def build_activity_feed(
    *,
    receipt: Mapping[str, Any] | None = None,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    feed = _load_json(_rooted(read_model_root) / ACTIVITY_FEED_EXPORT_NAME)
    if not feed:
        feed = {
            "schema_version": "openclaw_workroom_activity_feed_v0",
            "read_model_id": "openclaw_workroom_activity_feed",
            "status": "OPENCLAW_WORKROOM_ACTIVITY_FEED_READY",
            "posts": [],
            "source_refs": [],
            "machine_proof": {},
            "rules": [],
        }
    updated = _copy_json(feed)
    posts = [
        dict(post)
        for post in _list(updated.get("posts"))
        if isinstance(post, Mapping)
    ]
    added_post_id = ""
    if isinstance(receipt, Mapping) and receipt.get("event_recorded") is True:
        post = _event_post(receipt)
        added_post_id = post["post_id"]
        posts = [item for item in posts if str(item.get("post_id") or "") != added_post_id]
        posts.append(post)
    posts.sort(key=lambda post: (str(post.get("timestamp") or ""), str(post.get("post_id") or "")))
    source_refs = _append_unique(
        _strings(updated.get("source_refs")),
        "generated/read_models/agent_handoff_event_status.json",
    )
    rules = _append_unique(
        _strings(updated.get("rules")),
        "Agent handoff event posts record routing receipts only and do not execute downstream work.",
    )
    machine_proof = dict(updated.get("machine_proof") if isinstance(updated.get("machine_proof"), Mapping) else {})
    machine_proof.update(
        {
            "agent_handoff_event_consumer_applied": True,
            "agent_handoff_event_post_added": bool(added_post_id),
            "downstream_worker_assigned": False,
            "worker_execution_performed": False,
            "tool_execution_performed": False,
            "new_business_truth_created": False,
            "message_send_performed": False,
            "email_send_performed": False,
            "git_push_performed": False,
            "unsafe_true_grants_absent": all(value is False for value in AUTHORITY_BOUNDARY.values()),
        }
    )
    updated.update(
        {
            "generated_at": generated_at,
            "post_count": len(posts),
            "channel_post_counts": _channel_post_counts(posts),
            "posts_by_channel": _posts_by_channel(posts),
            "posts": posts,
            "source_refs": source_refs,
            "agent_handoff_event_consumer": {
                "applied": True,
                "latest_post_id": added_post_id,
                "status_ref": "generated/read_models/agent_handoff_event_status.json",
            },
            "rules": rules,
            "machine_proof": machine_proof,
        }
    )
    return updated


def build_wiki(status_read_model: Mapping[str, Any]) -> str:
    last_event = status_read_model.get("last_event") if isinstance(status_read_model.get("last_event"), Mapping) else {}
    lines = [
        "# Agent Handoff Event Consumer",
        "",
        f"Status: `{status_read_model['status']}`",
        "",
        "This consumer records deterministic agent handoff events without executing the downstream work.",
        "",
        f"Events recorded: `{status_read_model['event_count']}`",
        f"Attempts recorded: `{status_read_model['attempt_count']}`",
        "",
        "## Latest Event",
        "",
        f"- Event: `{last_event.get('event_id', '')}`",
        f"- Handoff: `{last_event.get('handoff_ref', '')}`",
        f"- Route: `{last_event.get('from_agent', '')}` -> `{last_event.get('to_agent_or_worker', '')}`",
        f"- Channel: `{last_event.get('channel_ref', '')}`",
        "",
        "## Boundary",
        "",
        "- Handoff events are receipts only.",
        "- No worker is assigned or executed.",
        "- No tools execute.",
        "- No Slack or Telegram live connection.",
        "- No email send.",
        "- No Gmail/browser/Coupa access.",
        "- No ledger or workbook mutation.",
        "- No PDF export.",
        "- No submit or mark-paid.",
        "- No git push.",
        "- Proof refs remain collapsed.",
    ]
    return "\n".join(lines) + "\n"


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(stable_json(payload), encoding="utf-8")


def export_agent_handoff_event_status(
    *,
    receipt: Mapping[str, Any] | None = None,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
    export_root: Path = DEFAULT_EXPORT_ROOT,
    bridge_export_root: Path | None = DEFAULT_BRIDGE_EXPORT_ROOT,
    wiki_path: Path = DEFAULT_WIKI_PATH,
    generated_at: str | None = None,
) -> dict[str, str]:
    generated_at = generated_at or utc_now()
    status_read_model = build_status_read_model(
        receipt=receipt,
        read_model_root=read_model_root,
        export_root=export_root,
        generated_at=generated_at,
    )
    activity_feed = build_activity_feed(receipt=receipt, read_model_root=read_model_root, generated_at=generated_at)
    export_root = _rooted(export_root)
    status_path = export_root / JSON_EXPORT_NAME
    feed_path = export_root / ACTIVITY_FEED_EXPORT_NAME
    _write_json(status_path, status_read_model)
    _write_json(feed_path, activity_feed)

    bridge_status_path = ""
    bridge_feed_path = ""
    if bridge_export_root is not None:
        bridge_export_root.mkdir(parents=True, exist_ok=True)
        bridge_status = bridge_export_root / JSON_EXPORT_NAME
        bridge_feed = bridge_export_root / ACTIVITY_FEED_EXPORT_NAME
        _write_json(bridge_status, status_read_model)
        _write_json(bridge_feed, activity_feed)
        bridge_status_path = bridge_status.as_posix()
        bridge_feed_path = bridge_feed.as_posix()

    wiki_path = _rooted(wiki_path)
    wiki_path.parent.mkdir(parents=True, exist_ok=True)
    wiki_path.write_text(build_wiki(status_read_model), encoding="utf-8")
    return {
        "status": str(status_read_model["status"]),
        "read_model_path": status_path.as_posix(),
        "activity_feed_path": feed_path.as_posix(),
        "bridge_read_model_path": bridge_status_path,
        "bridge_activity_feed_path": bridge_feed_path,
        "wiki_path": wiki_path.as_posix(),
        "event_count": str(status_read_model["event_count"]),
        "attempt_count": str(status_read_model["attempt_count"]),
    }


def consume_agent_handoff_event_request(
    raw_request: Mapping[str, Any],
    *,
    source_request_filename: str = "",
    generated_at: str | None = None,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
    export_root: Path = DEFAULT_EXPORT_ROOT,
    bridge_export_root: Path | None = DEFAULT_BRIDGE_EXPORT_ROOT,
    wiki_path: Path = DEFAULT_WIKI_PATH,
) -> AgentHandoffEventResult:
    generated_at = generated_at or utc_now()
    receipt = _receipt(
        raw_request,
        source_request_filename=source_request_filename,
        generated_at=generated_at,
        read_model_root=read_model_root,
    )
    export_result = export_agent_handoff_event_status(
        receipt=receipt,
        read_model_root=read_model_root,
        export_root=export_root,
        bridge_export_root=bridge_export_root,
        wiki_path=wiki_path,
        generated_at=generated_at,
    )
    receipt = dict(receipt)
    receipt["read_model_paths"] = {
        "local_status_path": export_result["read_model_path"],
        "bridge_status_path": export_result["bridge_read_model_path"],
        "local_activity_feed_path": export_result["activity_feed_path"],
        "bridge_activity_feed_path": export_result["bridge_activity_feed_path"],
        "wiki_path": export_result["wiki_path"],
    }
    export_agent_handoff_event_status(
        receipt=receipt,
        read_model_root=read_model_root,
        export_root=export_root,
        bridge_export_root=bridge_export_root,
        wiki_path=wiki_path,
        generated_at=generated_at,
    )
    event = _event_from_receipt(receipt) if receipt.get("event_recorded") is True else None
    return AgentHandoffEventResult(
        status="RECORDED" if receipt.get("event_recorded") is True else "BLOCKED",
        request_id=str(receipt["request_id"]),
        request_filename=source_request_filename,
        event=event,
        blockers=tuple(str(item) for item in receipt.get("blockers") or ()),
        response_primary_status=str(receipt["response_primary_status"]),
        next_safe_action=str(receipt["next_safe_action"]),
        receipt=receipt,
    )


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Consume/export Agent Handoff Event Consumer V0 status.")
    parser.add_argument("--request-file", help="Optional AGENT_HANDOFF_EVENT_REQUEST_V0 JSON file to consume.")
    parser.add_argument("--read-model-root", default=str(DEFAULT_READ_MODEL_ROOT))
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT))
    parser.add_argument("--bridge-export-root", default=str(DEFAULT_BRIDGE_EXPORT_ROOT))
    parser.add_argument("--wiki-path", default=str(DEFAULT_WIKI_PATH))
    parser.add_argument("--generated-at")
    parser.add_argument("--no-bridge", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    bridge_root = None if args.no_bridge else Path(args.bridge_export_root)
    if args.request_file:
        request_path = Path(args.request_file)
        raw_request = _load_json(request_path)
        result = consume_agent_handoff_event_request(
            raw_request,
            source_request_filename=request_path.name,
            generated_at=args.generated_at,
            read_model_root=Path(args.read_model_root),
            export_root=Path(args.export_root),
            bridge_export_root=bridge_root,
            wiki_path=Path(args.wiki_path),
        )
        print(stable_json(result.receipt), end="")
        return 0 if result.status == "RECORDED" else 2
    result = export_agent_handoff_event_status(
        read_model_root=Path(args.read_model_root),
        export_root=Path(args.export_root),
        bridge_export_root=bridge_root,
        wiki_path=Path(args.wiki_path),
        generated_at=args.generated_at,
    )
    print(stable_json(result), end="")
    return 0 if result["status"] == CONSUMER_STATUS else 2


if __name__ == "__main__":
    raise SystemExit(main())
