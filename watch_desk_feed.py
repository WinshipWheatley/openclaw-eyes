"""Watch Desk feed read model v0.

This module aggregates existing generated read models into a compact,
proof-backed desk feed. It is deliberately read-only with respect to source
models and does not call runtimes, external services, agents, or model tools.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


DEFAULT_READ_MODEL_ROOT = Path("generated/read_models")
DEFAULT_TASK_ROOT = Path("polish_loop/tasks")
DEFAULT_EXPORT_ROOT = Path("generated/read_models")

SCHEMA_VERSION = "watch_desk_feed_v0"
READ_MODEL_ID = "watch_desk_feed"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"

LANES = (
    "cassandra_ar",
    "chief_runtime",
    "niles_creative",
    "mac_sync",
    "guardian_approval",
    "hermes",
)
URGENCIES = ("info", "watch", "needs_operator", "blocked", "urgent")
PUSH_ELIGIBLE_CLASSES = ("approval_waiting", "failure")
SUPPORTED_INTAKE_ACTION_TYPES = (
    "income_payment_log",
    "expense_log",
    "gig_event_log",
    "identity_signature_preference",
)

APPROVAL_QUEUE_REF = "generated/read_models/approval_request_queue.json"
CASSANDRA_DRAFT_REF = "generated/read_models/cassandra_draft_worker_readback.json"
SYNC_HEALTH_REF = "generated/read_models/sync_health.json"
SERVICE_KEEPER_REF = "generated/read_models/openclaw_service_keeper_status.json"
PROOF_TO_RESPONSE_REF = "generated/read_models/proof_to_response_latest.json"
OPERATOR_INTAKE_REF = "generated/read_models/operator_intake_events.json"
GUIDED_REVIEW_REF = "generated/read_models/guided_review_sessions.json"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _rooted(path: str | Path) -> Path:
    path = Path(path)
    if path.is_absolute():
        return path
    return Path.cwd() / path


def _load_json(path: Path) -> dict[str, Any]:
    try:
        if not path.is_file():
            return {}
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _hash_state(payload: Mapping[str, Any]) -> str:
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return "sha256:" + hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _safe_int(value: Any) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        try:
            return int(value.strip())
        except ValueError:
            return 0
    return 0


def _parse_iso_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _display_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _is_pending_status(value: Any) -> bool:
    status = str(value or "").strip().lower()
    return status in {"pending", "waiting", "needs_operator", "operator_review_required"}


def _plural(count: int, singular: str, plural: str | None = None) -> str:
    if count == 1:
        return f"1 {singular}"
    return f"{count} {plural or singular + 's'}"


def _new_item(
    *,
    item_id: str,
    lane: str,
    urgency: str,
    plain_line: str,
    source_receipt_ref: str,
    one_next_safe_action: str,
    state: Mapping[str, Any],
    push_class: str,
    occurred_at: str = "",
) -> dict[str, Any]:
    if lane not in LANES:
        lane = "chief_runtime"
    if urgency not in URGENCIES:
        urgency = "watch"
    push_candidate = push_class in PUSH_ELIGIBLE_CLASSES
    item = {
        "item_id": item_id,
        "lane": lane,
        "urgency": urgency,
        "plain_line": plain_line,
        "source_receipt_ref": source_receipt_ref,
        "one_next_safe_action": one_next_safe_action,
        "state_hash": _hash_state(state),
        "push_allowed": False,
        "push_candidate": push_candidate,
        "push_class": push_class,
    }
    if occurred_at:
        item["occurred_at"] = occurred_at
    return item


def _approval_queue_item(queue: Mapping[str, Any]) -> dict[str, Any] | None:
    requests = queue.get("approval_requests")
    if not isinstance(requests, list):
        return None
    pending = [item for item in requests if isinstance(item, Mapping) and _is_pending_status(item.get("status"))]
    if not pending:
        return None

    ids = sorted(str(item.get("approval_request_id") or item.get("request_id") or "") for item in pending)
    action_refs = sorted(str(item.get("requested_action") or item.get("gate_ref") or "approval") for item in pending)
    count = len(pending)
    plain = f"{_plural(count, 'approval request')} waiting for operator review."
    return _new_item(
        item_id="guardian_approval:approval_request_queue:pending",
        lane="guardian_approval",
        urgency="needs_operator",
        plain_line=plain,
        source_receipt_ref=f"{APPROVAL_QUEUE_REF}#pending",
        one_next_safe_action="Review the existing approval queue and choose the next recorded decision there.",
        state={
            "pending_count": count,
            "pending_ids": ids,
            "action_refs": action_refs,
        },
        push_class="approval_waiting",
    )


def _cassandra_authority_item(readback: Mapping[str, Any]) -> dict[str, Any] | None:
    request = readback.get("request") if isinstance(readback.get("request"), Mapping) else {}
    response = readback.get("readback") if isinstance(readback.get("readback"), Mapping) else {}
    approval_required = bool(request.get("approval_required") or response.get("approval_required"))
    authority_waiting = request.get("send_authority") is False or str(response.get("status") or "").upper() in {
        "DRAFT_READY_FOR_REVIEW",
        "MISSING_INPUTS",
    }
    if not approval_required or not authority_waiting:
        return None

    request_ref = str(request.get("request_id") or response.get("request_ref") or "cassandra_draft_request")
    status = str(response.get("status") or "AUTHORITY_WAITING")
    missing_items = request.get("missing_inputs")
    missing_count = len(missing_items) if isinstance(missing_items, list) else 0
    return _new_item(
        item_id=f"cassandra_ar:{request_ref}:authority_waiting",
        lane="cassandra_ar",
        urgency="needs_operator",
        plain_line="Cassandra has a draft waiting for operator send-authority review.",
        source_receipt_ref=f"{CASSANDRA_DRAFT_REF}#readback",
        one_next_safe_action="Review the existing draft readback and keep external delivery blocked until the existing approval path is used.",
        state={
            "request_ref": request_ref,
            "approval_required": approval_required,
            "send_authority": request.get("send_authority"),
            "readback_status": status,
            "missing_input_count": missing_count,
        },
        push_class="approval_waiting",
    )


def _parse_task_header(path: Path) -> dict[str, str]:
    fields: dict[str, str] = {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return fields
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("- "):
            continue
        if ":" not in stripped:
            continue
        key, value = stripped.split(":", 1)
        key = key.strip()
        if key in {"title", "generated_by", "generated_at", "profile", "goal"}:
            fields[key] = value.strip()
    return fields


def _cassandra_failure_item(task_root: Path) -> dict[str, Any] | None:
    if not task_root.exists():
        return None
    task_records: list[dict[str, str]] = []
    for path in sorted(task_root.glob("chief-cassandra-failure-*.md")):
        header = _parse_task_header(path)
        generated_by = header.get("generated_by", "")
        title = header.get("title", path.stem)
        if generated_by != "chief_cassandra_failure" and "cassandra-failure" not in title:
            continue
        task_records.append(
            {
                "path": _display_path(path),
                "title": title,
                "generated_at": header.get("generated_at", ""),
            }
        )
    if not task_records:
        return None

    latest = sorted(task_records, key=lambda item: (item.get("generated_at", ""), item["path"]))[-1]
    count = len(task_records)
    plain = f"{_plural(count, 'Cassandra failure task')} open for reply-path diagnosis."
    return _new_item(
        item_id="cassandra_ar:reply_path_failure_tasks:open",
        lane="cassandra_ar",
        urgency="blocked",
        plain_line=plain,
        source_receipt_ref=f"{latest['path']}#generated_by",
        one_next_safe_action="Run bounded local diagnosis from existing proof and keep live listener wiring blocked.",
        state={
            "task_count": count,
            "task_refs": [record["path"] for record in task_records],
            "latest_generated_at": latest.get("generated_at", ""),
        },
        push_class="failure",
    )


def _sync_health_item(sync_health: Mapping[str, Any]) -> dict[str, Any] | None:
    display = str(sync_health.get("display_status") or "").strip().lower()
    mirror = str(sync_health.get("mirror_status") or "").strip().lower()
    missing = _safe_int(sync_health.get("missing_expected"))
    mismatched = _safe_int(sync_health.get("hash_mismatch"))
    stale_statuses = {
        "needs_mac_sync",
        "actionable_sync_failure",
        "map_hash_mismatch",
        "raw_mirror_stale_or_mismatched",
        "stale",
        "mismatched",
    }
    healthy_statuses = {"", "ok", "ready", "synced", "healthy", "clean"}
    stale = bool(missing or mismatched or display in stale_statuses or mirror in stale_statuses)
    if not stale or (display in healthy_statuses and mirror in healthy_statuses and not missing and not mismatched):
        return None

    details = []
    if missing:
        details.append(f"{missing} missing")
    if mismatched:
        details.append(_plural(mismatched, "hash mismatch", "hash mismatches"))
    suffix = f" ({', '.join(details)})" if details else ""
    return _new_item(
        item_id="mac_sync:read_model_mirror:stale",
        lane="mac_sync",
        urgency="watch",
        plain_line=f"Mac sync read model is stale or mismatched{suffix}.",
        source_receipt_ref=f"{SYNC_HEALTH_REF}#mirror_status",
        one_next_safe_action="Use the existing sync lifecycle; do not patch source read models by hand.",
        state={
            "display_status": display,
            "mirror_status": mirror,
            "missing_expected": missing,
            "hash_mismatch": mismatched,
        },
        push_class="on_demand",
    )


def _service_keeper_item(status: Mapping[str, Any]) -> dict[str, Any] | None:
    run_status = str(status.get("run_status") or "").strip().upper()
    unit_results = status.get("unit_results")
    units = unit_results if isinstance(unit_results, list) else []
    failed_units = [
        str(unit.get("unit_name") or "")
        for unit in units
        if isinstance(unit, Mapping) and "FAIL" in str(unit.get("status") or "").upper()
    ]
    if run_status in {"", "NO_ACTION_REQUIRED"} and not failed_units:
        return None

    failure = bool(failed_units or "FAIL" in run_status)
    return _new_item(
        item_id="chief_runtime:service_keeper:attention",
        lane="chief_runtime",
        urgency="blocked" if failure else "watch",
        plain_line="Chief runtime service keeper reports attention is needed.",
        source_receipt_ref=f"{SERVICE_KEEPER_REF}#run_status",
        one_next_safe_action="Review the service keeper status and use only existing allowlisted service controls.",
        state={
            "run_status": run_status,
            "failed_units": failed_units,
        },
        push_class="failure" if failure else "on_demand",
    )


def _proof_to_response_item(status: Mapping[str, Any]) -> dict[str, Any] | None:
    proof_status = str(status.get("proof_to_response_status") or status.get("status") or "").strip().lower()
    unavailable_reason = str(status.get("proof_to_response_unavailable_reason") or "").strip()
    if proof_status in {"", "publishable", "ready", "proof_to_response_runtime_ready"} and not unavailable_reason:
        return None

    failed = "fail" in proof_status or "unavailable" in proof_status or bool(unavailable_reason)
    return _new_item(
        item_id="hermes:proof_to_response:attention",
        lane="hermes",
        urgency="blocked" if failed else "watch",
        plain_line="Proof-to-response runtime needs attention before it can be trusted as current.",
        source_receipt_ref=f"{PROOF_TO_RESPONSE_REF}#proof_to_response_status",
        one_next_safe_action="Review the proof-to-response status read model and keep model/runtime invocation out of this feed.",
        state={
            "proof_to_response_status": proof_status,
            "unavailable_reason_present": bool(unavailable_reason),
        },
        push_class="failure" if failed else "on_demand",
    )


def _watch_lane(lane: Any) -> str:
    lane_text = str(lane or "").strip()
    if lane_text in LANES:
        return lane_text
    if lane_text == "cassandra_finance":
        return "cassandra_ar"
    if lane_text == "cassandra_business/niles_context":
        return "niles_creative"
    if lane_text == "chief_identity":
        return "chief_runtime"
    return "chief_runtime"


def _safe_intake_summary(event: Mapping[str, Any], action_type: str) -> str:
    summary = str(event.get("normalized_summary") or "").strip()
    if summary:
        return summary
    labels = {
        "income_payment_log": "Logged income/payment intake event.",
        "expense_log": "Logged expense intake event.",
        "gig_event_log": "Logged gig intake event.",
        "identity_signature_preference": "Staged identity preference locally.",
    }
    return labels.get(action_type, "Operator intake event logged locally.")


def _receipt_ref_from_event(event: Mapping[str, Any]) -> str:
    receipts = event.get("receipts")
    if not isinstance(receipts, list):
        return ""
    for receipt in receipts:
        if not isinstance(receipt, Mapping):
            continue
        path = str(receipt.get("path") or "").strip()
        if path:
            return path if "#" in path else f"{path}#receipt"
        receipt_id = str(receipt.get("receipt_id") or "").strip()
        if receipt_id:
            return f"{receipt_id}#receipt"
    return ""


def _operator_item_from_mapping(
    item: Mapping[str, Any],
    *,
    fallback_event: Mapping[str, Any] | None = None,
) -> dict[str, Any] | None:
    item_id = str(item.get("item_id") or "").strip()
    intake_id = str(item.get("intake_id") or (fallback_event or {}).get("intake_id") or "").strip()
    action_type = str(item.get("action_type") or "").strip()
    plain_line = str(item.get("plain_line") or "").strip()
    source_receipt_ref = str(item.get("source_receipt_ref") or "").strip()
    occurred_at = str((fallback_event or {}).get("received_at_utc") or item.get("occurred_at") or "").strip()
    if not item_id and intake_id:
        item_id = f"operator_intake:{intake_id}"
    if not source_receipt_ref and fallback_event:
        source_receipt_ref = _receipt_ref_from_event(fallback_event)
    if not plain_line and fallback_event:
        parsed = fallback_event.get("parsed") if isinstance(fallback_event.get("parsed"), Mapping) else {}
        action_type = action_type or str(parsed.get("action_type") or "")
        plain_line = _safe_intake_summary(fallback_event, action_type)
    if not item_id or not plain_line or not source_receipt_ref:
        return None
    fallback_parsed = fallback_event.get("parsed") if fallback_event and isinstance(fallback_event.get("parsed"), Mapping) else {}

    feed_item = _new_item(
        item_id=item_id,
        lane=_watch_lane(item.get("lane") or fallback_parsed.get("lane")),
        urgency=str(item.get("urgency") or "watch"),
        plain_line=plain_line,
        source_receipt_ref=source_receipt_ref,
        one_next_safe_action=str(
            item.get("one_next_safe_action")
            or "Review the local intake receipt before any external action."
        ),
        state={
            "intake_id": intake_id,
            "action_type": action_type,
            "source_receipt_ref": source_receipt_ref,
            "surface": str((fallback_event or {}).get("surface") or ""),
            "received_at_utc": occurred_at,
        },
        push_class=str(item.get("push_class") or "on_demand"),
        occurred_at=occurred_at,
    )
    for key in (
        "owner_agent",
        "owner_lane",
        "skill_id",
        "action_type",
        "missing_fields",
        "operator_local_timezone",
        "operator_local_date",
        "normalized_event_date",
    ):
        if key in item:
            feed_item[key] = item[key]
        elif fallback_event and key in fallback_event:
            feed_item[key] = fallback_event[key]
    return feed_item


def _operator_item_from_event(event: Mapping[str, Any]) -> dict[str, Any] | None:
    parsed = event.get("parsed") if isinstance(event.get("parsed"), Mapping) else {}
    action_type = str(parsed.get("action_type") or "").strip()
    if action_type not in SUPPORTED_INTAKE_ACTION_TYPES:
        return None
    receipt_ref = _receipt_ref_from_event(event)
    if not receipt_ref:
        return None
    intake_id = str(event.get("intake_id") or "").strip()
    if not intake_id:
        return None
    item = {
        "item_id": f"operator_intake:{intake_id}",
        "intake_id": intake_id,
        "action_type": action_type,
        "lane": _watch_lane(parsed.get("lane")),
        "urgency": "watch",
        "plain_line": _safe_intake_summary(event, action_type),
        "source_receipt_ref": receipt_ref,
        "one_next_safe_action": "Review the local receipt; keep external mutation behind the existing approval spine.",
        "push_class": "info",
        "owner_agent": str(event.get("owner_agent") or event.get("inferred_owner_agent") or ""),
        "owner_lane": str(event.get("owner_lane") or event.get("inferred_owner_lane") or ""),
        "skill_id": str(event.get("skill_id") or ""),
        "missing_fields": list(event.get("needs_clarification", [])),
    }
    return _operator_item_from_mapping(item, fallback_event=event)


def _operator_intake_freshness(
    read_model: Mapping[str, Any],
    *,
    feed_generated_at: str,
) -> dict[str, Any]:
    if not read_model:
        return {
            "status": "missing",
            "source_ref": f"{OPERATOR_INTAKE_REF}#missing",
            "source_generated_at": "",
            "latest_event_at": "",
            "event_count": 0,
        }
    events = read_model.get("events")
    event_rows = [event for event in events if isinstance(event, Mapping)] if isinstance(events, list) else []
    source_generated_at = str(read_model.get("generated_at") or "").strip()
    latest_event_at = ""
    latest_event_dt = None
    for event in event_rows:
        event_dt = _parse_iso_datetime(event.get("received_at_utc"))
        if event_dt and (latest_event_dt is None or event_dt > latest_event_dt):
            latest_event_dt = event_dt
            latest_event_at = str(event.get("received_at_utc") or "")

    source_dt = _parse_iso_datetime(source_generated_at)
    feed_dt = _parse_iso_datetime(feed_generated_at)
    status = "fresh"
    if event_rows and source_dt is None:
        status = "source_generated_at_missing"
    elif latest_event_dt and source_dt and latest_event_dt > source_dt:
        status = "source_stale"
    elif source_dt and feed_dt and source_dt > feed_dt:
        status = "feed_stale"
    elif not event_rows:
        status = "empty"

    return {
        "status": status,
        "source_ref": f"{OPERATOR_INTAKE_REF}#generated_at",
        "source_generated_at": source_generated_at,
        "latest_event_at": latest_event_at,
        "event_count": len(event_rows),
    }


def _operator_intake_warning_item(freshness: Mapping[str, Any]) -> dict[str, Any] | None:
    status = str(freshness.get("status") or "")
    if status in {"fresh", "empty"}:
        return None
    source_ref = str(freshness.get("source_ref") or f"{OPERATOR_INTAKE_REF}#generated_at")
    lines = {
        "missing": "Universal Operator Intake read model is missing; recent local-safe intake may not be visible.",
        "source_generated_at_missing": "Universal Operator Intake read model has events but no generated_at timestamp.",
        "source_stale": "Universal Operator Intake read model appears older than its latest event.",
        "feed_stale": "Watch Desk feed was generated before the latest Universal Operator Intake read model.",
    }
    return _new_item(
        item_id=f"chief_runtime:operator_intake_events:{status}",
        lane="chief_runtime",
        urgency="watch",
        plain_line=lines.get(status, "Universal Operator Intake freshness needs review."),
        source_receipt_ref=source_ref,
        one_next_safe_action="Regenerate the local Watch Desk feed from existing read models; do not call external systems.",
        state={
            "status": status,
            "source_generated_at": str(freshness.get("source_generated_at") or ""),
            "latest_event_at": str(freshness.get("latest_event_at") or ""),
            "event_count": int(freshness.get("event_count") or 0),
        },
        push_class="on_demand",
    )


def _operator_intake_items(
    read_model: Mapping[str, Any],
    *,
    feed_generated_at: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if not read_model:
        freshness = _operator_intake_freshness(read_model, feed_generated_at=feed_generated_at)
        warning = _operator_intake_warning_item(freshness)
        return ([warning] if warning else []), freshness

    feed_items: list[dict[str, Any]] = []
    events = read_model.get("events")
    event_rows = [event for event in events if isinstance(event, Mapping)] if isinstance(events, list) else []
    event_by_intake_id = {
        str(event.get("intake_id") or ""): event for event in event_rows if str(event.get("intake_id") or "")
    }
    for event in event_rows:
        event_items = event.get("watch_desk_items")
        if isinstance(event_items, list):
            for item in event_items:
                if isinstance(item, Mapping):
                    converted = _operator_item_from_mapping(item, fallback_event=event)
                    if converted:
                        feed_items.append(converted)
        fallback = _operator_item_from_event(event)
        if fallback:
            feed_items.append(fallback)

    top_items = read_model.get("watch_desk_items")
    if isinstance(top_items, list):
        for item in top_items:
            if isinstance(item, Mapping):
                intake_id = str(item.get("intake_id") or "").strip()
                converted = _operator_item_from_mapping(item, fallback_event=event_by_intake_id.get(intake_id))
                if converted:
                    feed_items.append(converted)

    freshness = _operator_intake_freshness(read_model, feed_generated_at=feed_generated_at)
    warning = _operator_intake_warning_item(freshness)
    if warning:
        feed_items.append(warning)
    return feed_items, freshness


def _guided_review_items(read_model: Mapping[str, Any]) -> list[dict[str, Any]]:
    if not read_model:
        return []
    items: list[dict[str, Any]] = []
    top_items = read_model.get("watch_desk_items")
    if not isinstance(top_items, list):
        return items
    for item in top_items:
        if not isinstance(item, Mapping):
            continue
        item_id = str(item.get("item_id") or "").strip()
        plain_line = str(item.get("plain_line") or "").strip()
        source_ref = str(item.get("source_receipt_ref") or "").strip()
        if not item_id or not plain_line or not source_ref:
            continue
        status = str(item.get("status") or "")
        items.append(
            _new_item(
                item_id=item_id,
                lane="chief_runtime",
                urgency=str(item.get("urgency") or ("needs_operator" if status in {"active", "paused"} else "info")),
                plain_line=plain_line,
                source_receipt_ref=source_ref,
                one_next_safe_action=str(
                    item.get("one_next_safe_action")
                    or "Continue the guided review with Cassandra, or say done to generate the promotion prompt."
                ),
                state={
                    "review_session_id": str(item.get("review_session_id") or ""),
                    "status": status,
                    "answered_count": _safe_int(item.get("answered_count")),
                    "deferred_count": _safe_int(item.get("deferred_count")),
                    "remaining_count": _safe_int(item.get("remaining_count")),
                },
                push_class=str(item.get("push_class") or "info"),
            )
        )
    return items


def _dedupe_items(items: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: dict[str, dict[str, Any]] = {}
    for item in items:
        key = f"{item['item_id']}|{item['state_hash']}"
        deduped.setdefault(key, item)
    return sorted(deduped.values(), key=lambda item: (item["urgency"], item["lane"], item["item_id"]))


def item_state_keys(items: Iterable[Mapping[str, Any]]) -> set[str]:
    keys: set[str] = set()
    for item in items:
        item_id = str(item.get("item_id") or "")
        state_hash = str(item.get("state_hash") or "")
        if item_id and state_hash:
            keys.add(f"{item_id}|{state_hash}")
    return keys


def _push_candidates(
    items: Sequence[Mapping[str, Any]],
    previous_item_states: Iterable[str] | None,
) -> list[dict[str, Any]]:
    previous = set(previous_item_states or [])
    candidates: list[dict[str, Any]] = []
    for item in items:
        if not item.get("push_candidate"):
            continue
        if item.get("push_class") not in PUSH_ELIGIBLE_CLASSES:
            continue
        key = f"{item.get('item_id')}|{item.get('state_hash')}"
        if key in previous:
            continue
        candidates.append(
            {
                "item_id": item["item_id"],
                "lane": item["lane"],
                "urgency": item["urgency"],
                "source_receipt_ref": item["source_receipt_ref"],
                "state_hash": item["state_hash"],
                "push_allowed": False,
            }
        )
    return candidates


def build_watch_desk_feed(
    *,
    read_model_root: str | Path = DEFAULT_READ_MODEL_ROOT,
    task_root: str | Path = DEFAULT_TASK_ROOT,
    generated_at: str | None = None,
    previous_item_states: Iterable[str] | None = None,
) -> dict[str, Any]:
    read_root = _rooted(read_model_root)
    tasks = _rooted(task_root)
    generated_at = generated_at or utc_now()

    candidate_items = [
        _approval_queue_item(_load_json(read_root / "approval_request_queue.json")),
        _cassandra_authority_item(_load_json(read_root / "cassandra_draft_worker_readback.json")),
        _cassandra_failure_item(tasks),
        _sync_health_item(_load_json(read_root / "sync_health.json")),
        _service_keeper_item(_load_json(read_root / "openclaw_service_keeper_status.json")),
        _proof_to_response_item(_load_json(read_root / "proof_to_response_latest.json")),
    ]
    operator_intake_items, operator_intake_freshness = _operator_intake_items(
        _load_json(read_root / Path(OPERATOR_INTAKE_REF).name),
        feed_generated_at=generated_at,
    )
    guided_review_items = _guided_review_items(_load_json(read_root / Path(GUIDED_REVIEW_REF).name))
    feed_items = _dedupe_items(
        [item for item in candidate_items if item is not None] + operator_intake_items + guided_review_items
    )
    source_refs = sorted({item["source_receipt_ref"] for item in feed_items})
    new_candidates = _push_candidates(feed_items, previous_item_states)

    return {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "generated_at": generated_at,
        "mode": "fixture_read_model_only_no_live_mutation",
        "feed_items": feed_items,
        "item_count": len(feed_items),
        "source_receipt_refs": source_refs,
        "new_push_candidates": new_candidates,
        "new_push_candidate_count": len(new_candidates),
        "source_freshness": {
            "operator_intake_events": operator_intake_freshness,
        },
        "push_policy": {
            "live_push_allowed": False,
            "eligible_classes": list(PUSH_ELIGIBLE_CLASSES),
            "dedupe_key": "item_id + state_hash",
            "everything_else": "on_demand",
        },
        "authority_boundary": {
            "read_only_aggregation": True,
            "source_read_model_mutation_allowed": False,
            "source_task_mutation_allowed": False,
            "runtime_database_mutation_allowed": False,
            "live_listener_wiring_allowed": False,
            "live_notification_allowed": False,
            "approval_semantics_added": False,
            "card_family_added": False,
        },
        "machine_proof": {
            "source_models_written": False,
            "runtime_databases_written": False,
            "live_listener_modified": False,
            "live_notifications_sent": False,
            "raw_private_body_copied": False,
            "operator_intake_read_model_checked": True,
            "external_calls_performed": False,
            "all_items_have_source_receipt_ref": all(bool(item["source_receipt_ref"]) for item in feed_items),
            "push_allowed_false_for_all_items": all(item["push_allowed"] is False for item in feed_items),
            "push_candidates_limited_to_approval_waiting_and_failure": all(
                item.get("push_class") in PUSH_ELIGIBLE_CLASSES for item in feed_items if item.get("push_candidate")
            ),
        },
    }


def write_watch_desk_feed(payload: Mapping[str, Any], *, export_root: str | Path = DEFAULT_EXPORT_ROOT) -> Path:
    root = _rooted(export_root)
    root.mkdir(parents=True, exist_ok=True)
    path = root / JSON_EXPORT_NAME
    path.write_text(stable_json(payload), encoding="utf-8")
    return path


def export_watch_desk_feed(
    *,
    read_model_root: str | Path = DEFAULT_READ_MODEL_ROOT,
    task_root: str | Path = DEFAULT_TASK_ROOT,
    export_root: str | Path = DEFAULT_EXPORT_ROOT,
    generated_at: str | None = None,
    previous_item_states: Iterable[str] | None = None,
) -> dict[str, Any]:
    payload = build_watch_desk_feed(
        read_model_root=read_model_root,
        task_root=task_root,
        generated_at=generated_at,
        previous_item_states=previous_item_states,
    )
    path = write_watch_desk_feed(payload, export_root=export_root)
    return {
        "read_model_path": path.as_posix(),
        "item_count": payload["item_count"],
        "new_push_candidate_count": payload["new_push_candidate_count"],
        "live_push_allowed": False,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the Watch Desk feed read model.")
    parser.add_argument("--read-model-root", default=DEFAULT_READ_MODEL_ROOT.as_posix())
    parser.add_argument("--task-root", default=DEFAULT_TASK_ROOT.as_posix())
    parser.add_argument("--export-root", default=DEFAULT_EXPORT_ROOT.as_posix())
    parser.add_argument("--generated-at", default=None)
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args(argv)

    summary = export_watch_desk_feed(
        read_model_root=Path(args.read_model_root),
        task_root=Path(args.task_root),
        export_root=Path(args.export_root),
        generated_at=args.generated_at,
    )
    if args.format == "json":
        print(stable_json(summary), end="")
    else:
        print(
            f"wrote {summary['read_model_path']} "
            f"items={summary['item_count']} "
            f"new_push_candidates={summary['new_push_candidate_count']} "
            "live_push_allowed=false"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
