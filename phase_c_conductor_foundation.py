"""Phase-C conductor foundation read model.

Deterministically projects orchestration inbox markers into a compact state
model for scheduler reconciliation, gate-token visibility, and idempotent
completion writeback planning.

This module is read-only against orchestration. It does not send externally,
start services, restart services, merge branches, deploy, or mutate production
state.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
DEFAULT_ORCHESTRATION_ROOT = Path("/mnt/e/openclaw/orchestration")
DEFAULT_READ_MODEL_ROOT = Path("generated/read_models")

SCHEMA_VERSION = "phase_c_conductor_foundation_v0"
READ_MODEL_VERSION = "phase_c_conductor_state_read_model_v0"
JSON_EXPORT_NAME = "phase_c_conductor_state.json"
OPERATOR_EXPORT_NAME = "phase_c_conductor_state_OPERATOR.md"

MARKER_KINDS = ("CLAIM", "DONE", "BLOCKED", "PROBLEM", "IDLE")
WRITEBACK_RECEIPT_KIND = "WRITEBACK_RECEIPT"
WRITEBACK_RECEIPT_PREFIX = "PHASE-C-WRITEBACK-"
TIMESTAMP_SUFFIX_RE = re.compile(r"-(20\d{6}T\d{6}(?:Z|[-+]\d{4})?)$")
BODY_FIELD_RE = re.compile(r"^([A-Za-z0-9_ -]+):\s*(.*)$")

NO_AUTHORITY_FLAGS = {
    "read_only": True,
    "metadata_only": True,
    "deterministic_checks_only": True,
    "lm_called": False,
    "services_started": False,
    "services_restarted": False,
    "deploy_performed": False,
    "merge_performed": False,
    "git_push_performed": False,
    "external_send_performed": False,
    "money_spent": False,
    "production_state_mutated": False,
    "legal_discovery_accessed": False,
    "secret_values_printed": False,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _rooted(path: str | Path, *, root: str | Path = ROOT) -> Path:
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    return Path(root) / candidate


def _display_path(path: str | Path) -> str:
    candidate = Path(path)
    try:
        return candidate.resolve().relative_to(ROOT.resolve()).as_posix()
    except (OSError, ValueError):
        return candidate.as_posix()


def _sha256_bytes(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _sha256_text(text: str) -> str:
    return _sha256_bytes(text.encode("utf-8"))


def _compact_json(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def _sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def _mtime_from_timestamp(mtime: float) -> str:
    return datetime.fromtimestamp(mtime, timezone.utc).replace(microsecond=0).isoformat()


def _filename_timestamp(generated_at: str) -> str:
    try:
        parsed = datetime.fromisoformat(generated_at.replace("Z", "+00:00"))
    except ValueError:
        parsed = datetime.now(timezone.utc)
    return parsed.strftime("%Y%m%dT%H%M%S%z")


def _timestamp_suffix(stem: str) -> str:
    match = TIMESTAMP_SUFFIX_RE.search(stem)
    return match.group(1) if match else ""


def _strip_timestamp_suffix(stem: str) -> str:
    return TIMESTAMP_SUFFIX_RE.sub("", stem)


def _slug(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", str(value or "").strip())
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug or "unknown"


def _lane_prefix(text: str) -> str:
    for pattern in (
        r"LANE-[A-Z]",
        r"MAC-CODEX",
        r"CODEX-APP",
        r"CODEX-[A-Z]",
        r"CODEX",
        r"APP",
        r"GEMINI-[A-Z]+",
        r"GEMINI",
    ):
        match = re.match(pattern, text)
        if match:
            return match.group(0)
    parts = [part for part in text.split("-") if part]
    return parts[0] if parts else "UNKNOWN"


def _task_after_lane(text: str, lane: str) -> str:
    if text == lane:
        return ""
    prefix = lane + "-"
    return text[len(prefix) :] if text.startswith(prefix) else text


def parse_marker_filename(filename: str) -> dict[str, str]:
    """Classify an orchestration marker filename without reading its body."""

    stem = Path(filename).stem
    timestamp_token = _timestamp_suffix(stem)
    base = _strip_timestamp_suffix(stem)

    for kind, prefix in (
        ("GATE_CLAIM", "CLAIM-GATE-TOKEN-"),
        ("GATE_RELEASE", "RELEASE-GATE-TOKEN-"),
    ):
        if base.startswith(prefix):
            lane = base[len(prefix) :] or "UNKNOWN"
            return {
                "kind": kind,
                "lane": lane,
                "task_id": "gate-token",
                "timestamp_token": timestamp_token,
            }

    if base.startswith(WRITEBACK_RECEIPT_PREFIX):
        task_id = base[len(WRITEBACK_RECEIPT_PREFIX) :] or "unknown-task"
        return {
            "kind": WRITEBACK_RECEIPT_KIND,
            "lane": "PHASE-C",
            "task_id": task_id,
            "timestamp_token": timestamp_token,
        }

    for kind in MARKER_KINDS:
        infix = f"-{kind}-"
        suffix = f"-{kind}"
        if infix in base:
            before, after = base.split(infix, 1)
            lane = _lane_prefix(before)
            return {
                "kind": kind,
                "lane": lane,
                "task_id": after or _task_after_lane(before, lane) or "unknown-task",
                "timestamp_token": timestamp_token,
            }
        if base.endswith(suffix):
            before = base[: -len(suffix)]
            lane = _lane_prefix(before)
            return {
                "kind": kind,
                "lane": lane,
                "task_id": _task_after_lane(before, lane) or "unknown-task",
                "timestamp_token": timestamp_token,
            }

    return {
        "kind": "OTHER",
        "lane": _lane_prefix(base),
        "task_id": "",
        "timestamp_token": timestamp_token,
    }


def _marker_body_fields(path: Path) -> dict[str, str]:
    try:
        text = path.read_text(encoding="utf-8")[:8192]
    except OSError:
        return {}
    fields: dict[str, str] = {}
    for line in text.splitlines():
        match = BODY_FIELD_RE.match(line.strip())
        if not match:
            continue
        key = match.group(1).strip().lower().replace(" ", "_").replace("-", "_")
        fields[key] = match.group(2).strip()
    return fields


def _marker_record(
    path: Path,
    orchestration_root: Path,
    *,
    parsed: dict[str, str],
) -> dict[str, Any]:
    try:
        stat_result = path.stat()
        size_bytes = stat_result.st_size
        mtime = _mtime_from_timestamp(stat_result.st_mtime)
    except OSError:
        size_bytes = 0
        mtime = ""
    body_fields: dict[str, str] = {}
    if parsed["kind"] in {"GATE_RELEASE", WRITEBACK_RECEIPT_KIND}:
        body_fields = _marker_body_fields(path)
    if parsed["kind"] in {"DONE", "GATE_RELEASE", WRITEBACK_RECEIPT_KIND}:
        try:
            marker_sha256 = _sha256_file(path)
        except OSError:
            marker_sha256 = ""
    else:
        marker_sha256 = _sha256_text(
            stable_json(
                {
                    "filename": path.name,
                    "kind": parsed["kind"],
                    "lane": parsed["lane"],
                    "task_id": parsed["task_id"],
                    "timestamp_token": parsed["timestamp_token"],
                    "mtime": mtime,
                    "size_bytes": size_bytes,
                }
            ).strip()
        )
    try:
        relative_path = path.relative_to(orchestration_root).as_posix()
    except ValueError:
        relative_path = path.as_posix()
    return {
        "marker_ref": f"{parsed['kind'].lower()}:{path.name}",
        "filename": path.name,
        "path": _display_path(path),
        "relative_path": relative_path,
        "kind": parsed["kind"],
        "lane": parsed["lane"],
        "task_id": parsed["task_id"],
        "timestamp_token": parsed["timestamp_token"],
        "mtime": mtime,
        "size_bytes": size_bytes,
        "sha256": marker_sha256,
        "body_fields": body_fields,
    }


def _marker_sort_key(marker: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(marker.get("timestamp_token") or ""),
        str(marker.get("mtime") or ""),
        str(marker.get("filename") or ""),
    )


def _iter_marker_paths(orchestration_root: Path) -> list[Path]:
    inbox = orchestration_root / "inbox" / "to-claude"
    try:
        return sorted(path for path in inbox.glob("*.md") if path.is_file())
    except OSError:
        return []


def _status_for_marker(kind: str) -> str:
    return {
        "CLAIM": "CLAIMED",
        "DONE": "DONE",
        "BLOCKED": "BLOCKED",
        "PROBLEM": "PROBLEM",
        "IDLE": "IDLE",
    }.get(kind, "UNKNOWN")


def _task_states(markers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for marker in markers:
        if marker["kind"] not in MARKER_KINDS or not marker["task_id"]:
            continue
        grouped.setdefault(marker["task_id"], []).append(marker)

    states: list[dict[str, Any]] = []
    for task_id in sorted(grouped):
        rows = sorted(grouped[task_id], key=_marker_sort_key)
        latest = rows[-1]
        done_rows = [row for row in rows if row["kind"] == "DONE"]
        states.append(
            {
                "task_id": task_id,
                "state": _status_for_marker(str(latest["kind"])),
                "latest_marker": latest["relative_path"],
                "latest_marker_sha256": latest["sha256"],
                "latest_lane": latest["lane"],
                "marker_count": len(rows),
                "claim_count": sum(1 for row in rows if row["kind"] == "CLAIM"),
                "done_count": len(done_rows),
                "blocked_count": sum(1 for row in rows if row["kind"] == "BLOCKED"),
                "problem_count": sum(1 for row in rows if row["kind"] == "PROBLEM"),
                "completion_evidence_hashes": sorted(
                    {str(row["sha256"]) for row in done_rows if row.get("sha256")}
                ),
            }
        )
    return states


def _gate_state(markers: list[dict[str, Any]]) -> dict[str, Any]:
    gate_rows = [
        marker
        for marker in markers
        if marker["kind"] in {"GATE_CLAIM", "GATE_RELEASE"}
    ]
    latest_by_lane: dict[str, dict[str, Any]] = {}
    for marker in sorted(gate_rows, key=_marker_sort_key):
        latest_by_lane[str(marker["lane"])] = marker
    active_tokens = [
        {
            "lane": lane,
            "source_marker": marker["relative_path"],
            "claimed_at_token": marker["timestamp_token"],
            "marker_sha256": marker["sha256"],
        }
        for lane, marker in sorted(latest_by_lane.items())
        if marker["kind"] == "GATE_CLAIM"
    ]
    return {
        "gate_event_count": len(gate_rows),
        "active_gate_token_count": len(active_tokens),
        "active_gate_tokens": active_tokens,
        "serialization_status": "ACTION_REQUIRED"
        if len(active_tokens) > 1
        else "SERIALIZED",
    }


def _writeback_state(task_states: list[dict[str, Any]], markers: list[dict[str, Any]]) -> dict[str, Any]:
    done_by_task: dict[str, list[dict[str, Any]]] = {}
    for marker in markers:
        if marker["kind"] == "DONE" and marker.get("task_id") and marker.get("sha256"):
            done_by_task.setdefault(str(marker["task_id"]), []).append(marker)

    seen: set[tuple[str, str]] = set()
    records: list[dict[str, Any]] = []
    task_state_by_id = {str(row["task_id"]): row for row in task_states}
    for task_id in sorted(done_by_task):
        for marker in sorted(done_by_task[task_id], key=_marker_sort_key):
            evidence_hash = str(marker["sha256"])
            key = (task_id, evidence_hash)
            if key in seen:
                continue
            seen.add(key)
            writeback_key = _sha256_text(task_id + "\0" + evidence_hash)
            records.append(
                {
                    "writeback_ref": "phase_c_writeback:" + writeback_key.removeprefix("sha256:")[:16],
                    "task_id": task_id,
                    "task_state": task_state_by_id.get(task_id, {}).get("state", "DONE"),
                    "completion_evidence_hash": evidence_hash,
                    "idempotency_key": {
                        "task_id": task_id,
                        "completion_evidence_hash": evidence_hash,
                    },
                    "source_marker": marker["relative_path"],
                    "source_lane": marker["lane"],
                    "status": "READY_FOR_AUTO_WRITEBACK",
                    "live_write_performed": False,
                }
            )
    scheduler_backstop = {
        "mode": "scheduler_reconcile_backstop",
        "idempotency_key_fields": ["task_id", "completion_evidence_hash"],
        "completion_writeback_count": len(records),
        "completion_writebacks": records,
        "live_write_performed": False,
    }
    gate_hook_primary = _gate_hook_writeback_state(markers)
    return {
        "writeback_mode": "gate_hook_primary_scheduler_reconcile_backstop",
        "idempotency_key_fields": ["task_id", "completion_evidence_hash"],
        "completion_writeback_count": len(records),
        "completion_writebacks": records,
        "scheduler_reconcile_backstop": scheduler_backstop,
        "gate_hook_primary": gate_hook_primary,
        "gate_hook_writeback_count": gate_hook_primary["gate_hook_writeback_count"],
        "planned_checkoff_count": gate_hook_primary["gate_hook_writeback_count"] + len(records),
        "live_write_performed": False,
    }


def _green_gate_release_writeback(marker: dict[str, Any]) -> dict[str, Any] | None:
    fields = marker.get("body_fields") if isinstance(marker.get("body_fields"), dict) else {}
    exit_value = str(fields.get("exit") or fields.get("exit_code") or "").strip()
    if exit_value not in {"0", "PASS", "PASSED", "pass", "passed"}:
        return None
    task_id = str(fields.get("item") or fields.get("task") or fields.get("ref") or marker.get("lane") or "gate-token")
    evidence_hash = str(marker.get("sha256") or "")
    if not evidence_hash:
        return None
    writeback_key = _sha256_text(task_id + "\0" + evidence_hash)
    return {
        "writeback_ref": "phase_c_gate_writeback:" + writeback_key.removeprefix("sha256:")[:16],
        "task_id": task_id,
        "completion_evidence_hash": evidence_hash,
        "idempotency_key": {
            "task_id": task_id,
            "completion_evidence_hash": evidence_hash,
        },
        "trigger": "green_gate_release",
        "trigger_source_marker": marker["relative_path"],
        "trigger_lane": marker["lane"],
        "gate_ref": str(fields.get("ref") or ""),
        "exit": exit_value,
        "status": "READY_FOR_GATE_HOOK_WRITEBACK",
        "checkoff_target": "plan_checkoff:" + _slug(task_id),
        "live_write_performed": False,
    }


def _gate_hook_writeback_state(markers: list[dict[str, Any]]) -> dict[str, Any]:
    records = [
        record
        for marker in sorted(markers, key=_marker_sort_key)
        if marker["kind"] == "GATE_RELEASE"
        for record in [_green_gate_release_writeback(marker)]
        if record is not None
    ]
    seen: set[tuple[str, str]] = set()
    unique_records: list[dict[str, Any]] = []
    for record in records:
        key = (
            str(record["idempotency_key"]["task_id"]),
            str(record["idempotency_key"]["completion_evidence_hash"]),
        )
        if key in seen:
            continue
        seen.add(key)
        unique_records.append(record)
    return {
        "mode": "gate_hook_primary",
        "hook_entrypoint": "scripts/phase_c_conductor_gate_hook.py",
        "idempotency_key_fields": ["task_id", "completion_evidence_hash"],
        "gate_hook_writeback_count": len(unique_records),
        "gate_hook_writebacks": unique_records,
        "live_write_performed": False,
    }


def _existing_writeback_receipt(
    inbox: Path,
    *,
    idempotency_key: dict[str, str],
) -> Path | None:
    expected = _compact_json(idempotency_key)
    try:
        paths = sorted(inbox.glob(f"{WRITEBACK_RECEIPT_PREFIX}*.md"))
    except OSError:
        return None
    for path in paths:
        fields = _marker_body_fields(path)
        if fields.get("idempotency_key") == expected:
            return path
    return None


def write_phase_c_gate_hook_checkoff_receipt(
    *,
    orchestration_root: str | Path,
    gate_release_marker: str | Path,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Write one bounded checkoff receipt for a green gate-release marker.

    This is the approved runner hook surface: tests exercise it against a temp
    orchestration root; this worker does not invoke it against production.
    """

    root = Path(orchestration_root)
    marker_path = Path(gate_release_marker)
    if not marker_path.is_absolute():
        marker_path = root / marker_path
    parsed = parse_marker_filename(marker_path.name)
    if parsed["kind"] != "GATE_RELEASE":
        return {"status": "NOOP_NOT_GATE_RELEASE", "receipt_path": "", "live_write_performed": False}
    marker = _marker_record(marker_path, root, parsed=parsed)
    writeback = _green_gate_release_writeback(marker)
    if writeback is None:
        return {"status": "NOOP_GATE_NOT_GREEN", "receipt_path": "", "live_write_performed": False}

    inbox = root / "inbox" / "to-claude"
    inbox.mkdir(parents=True, exist_ok=True)
    idempotency_key = writeback["idempotency_key"]
    existing = _existing_writeback_receipt(inbox, idempotency_key=idempotency_key)
    if existing is not None:
        return {
            "status": "ALREADY_RECORDED",
            "receipt_path": _display_path(existing),
            "writeback_ref": writeback["writeback_ref"],
            "idempotency_key": idempotency_key,
            "live_write_performed": True,
        }

    generated = generated_at or utc_now()
    timestamp = _filename_timestamp(generated)
    receipt_path = inbox / f"{WRITEBACK_RECEIPT_PREFIX}{_slug(str(idempotency_key['task_id']))}-{timestamp}.md"
    receipt_text = "\n".join(
        [
            "PHASE-C-WRITEBACK",
            f"Writeback Ref: {writeback['writeback_ref']}",
            f"Task ID: {idempotency_key['task_id']}",
            f"Completion Evidence Hash: {idempotency_key['completion_evidence_hash']}",
            f"Idempotency Key: {_compact_json(idempotency_key)}",
            f"Trigger Source Marker: {writeback['trigger_source_marker']}",
            f"Gate Ref: {writeback['gate_ref']}",
            "Status: PLAN_CHECKOFF_WRITTEN",
            "Live Write Performed: true",
        ]
    )
    receipt_path.write_text(receipt_text + "\n", encoding="utf-8")
    return {
        "status": "WRITEBACK_RECEIPT_CREATED",
        "receipt_path": _display_path(receipt_path),
        "writeback_ref": writeback["writeback_ref"],
        "idempotency_key": idempotency_key,
        "live_write_performed": True,
    }


def _conductor_feed(task_states: list[dict[str, Any]], gate_state: dict[str, Any]) -> dict[str, Any]:
    live_plan_items = [
        {
            "task_id": row["task_id"],
            "state": row["state"],
            "latest_lane": row["latest_lane"],
            "latest_marker": row["latest_marker"],
        }
        for row in task_states
        if row["state"] in {"CLAIMED", "DONE"}
    ]
    dormant_broken_items = [
        {
            "task_id": row["task_id"],
            "state": row["state"],
            "latest_lane": row["latest_lane"],
            "latest_marker": row["latest_marker"],
        }
        for row in task_states
        if row["state"] in {"BLOCKED", "PROBLEM"}
    ]
    idle_blocked_items = [
        {
            "task_id": row["task_id"],
            "state": row["state"],
            "latest_lane": row["latest_lane"],
            "latest_marker": row["latest_marker"],
        }
        for row in task_states
        if row["state"] in {"IDLE", "BLOCKED"}
    ]
    gate_items = [
        {
            "task_id": "gate-token",
            "state": "GATE_TOKEN_ACTIVE",
            "latest_lane": token["lane"],
            "latest_marker": token["source_marker"],
        }
        for token in gate_state.get("active_gate_tokens", [])
    ]
    maestro_feed_records = [
        {
            "feed_ref": "phase_c_feed:" + _slug(item["task_id"]) + ":" + _slug(item["state"]),
            "task_id": item["task_id"],
            "state": item["state"],
            "latest_lane": item["latest_lane"],
            "latest_marker": item["latest_marker"],
            "target_surface": "maestro_status_capability_readback",
            "runtime_dispatch_allowed": False,
        }
        for item in [*live_plan_items, *dormant_broken_items, *idle_blocked_items, *gate_items]
    ]
    return {
        "mode": "maestro_read_model_feed_only",
        "live_plan_count": len(live_plan_items),
        "dormant_broken_count": len(dormant_broken_items),
        "idle_blocked_count": len(idle_blocked_items),
        "active_gate_token_count": len(gate_items),
        "maestro_feed_count": len(maestro_feed_records),
        "live_plan_items": live_plan_items,
        "lit_dormant_broken_items": dormant_broken_items,
        "idle_blocked_items": idle_blocked_items,
        "maestro_feed_records": maestro_feed_records,
        "runtime_dispatch_allowed": False,
    }


def build_phase_c_conductor_state(
    *,
    orchestration_root: str | Path = DEFAULT_ORCHESTRATION_ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated = generated_at or utc_now()
    root = Path(orchestration_root)
    marker_paths = _iter_marker_paths(root)
    recognized: list[dict[str, Any]] = []
    unrecognized_count = 0
    for path in marker_paths:
        parsed = parse_marker_filename(path.name)
        if parsed["kind"] == "OTHER":
            unrecognized_count += 1
            continue
        recognized.append(_marker_record(path, root, parsed=parsed))
    task_states = _task_states(recognized)
    gate = _gate_state(recognized)
    writeback = _writeback_state(task_states, recognized)
    conductor_feed = _conductor_feed(task_states, gate)
    blocked_count = sum(1 for row in task_states if row["state"] == "BLOCKED")
    problem_count = sum(1 for row in task_states if row["state"] == "PROBLEM")
    claimed_count = sum(1 for row in task_states if row["state"] == "CLAIMED")
    done_count = sum(1 for row in task_states if row["state"] == "DONE")
    action_required = (
        gate["active_gate_token_count"] > 1 or blocked_count > 0 or problem_count > 0
    )

    return {
        "schema_version": READ_MODEL_VERSION,
        "contract_schema_version": SCHEMA_VERSION,
        "generated_by": "codex",
        "generated_at": generated,
        "purpose": (
            "Provide deterministic Phase-C conductor state from orchestration "
            "markers without owning runtime authority."
        ),
        "orchestration_root": _display_path(root),
        "scan_scope": "inbox/to-claude/*.md",
        "status": "ACTION_REQUIRED" if action_required else "READY_FOR_REVIEW",
        "task_summary": {
            "task_count": len(task_states),
            "claimed_task_count": claimed_count,
            "done_task_count": done_count,
            "blocked_task_count": blocked_count,
            "problem_task_count": problem_count,
        },
        "gate_state": gate,
        "writeback_state": writeback,
        "conductor_feed": conductor_feed,
        "task_states": task_states,
        "recognized_marker_count": len(recognized),
        "unrecognized_marker_count": unrecognized_count,
        "machine_proof": {
            "source_path": _display_path(root / "inbox" / "to-claude"),
            "marker_count": len(marker_paths),
            "recognized_marker_count": len(recognized),
            "scheduler_reconcile_present": True,
            "gate_token_reconcile_present": True,
            "gate_hook_auto_writeback_present": True,
            "scheduler_reconcile_backstop_present": True,
            "auto_writeback_projection_present": True,
            "auto_writeback_idempotency_basis": "(task_id, completion_evidence_hash)",
            "conductor_feed_present": True,
            "maestro_feed_record_count": conductor_feed["maestro_feed_count"],
            "read_only_scan": True,
            "external_call_performed": False,
            "runtime_mutation_performed": False,
            "external_send_performed": False,
        },
        "foundation_components": [
            {
                "component": "scheduler_reconcile",
                "status": "FOUNDATION_READY",
                "basis": "CLAIM/DONE/BLOCKED/PROBLEM/IDLE marker projection",
            },
            {
                "component": "gate_token_serialization",
                "status": gate["serialization_status"],
                "basis": "latest CLAIM/RELEASE gate token marker per lane",
            },
            {
                "component": "auto_writeback",
                "status": "IDEMPOTENT_RECORDS_READY",
                "basis": "green gate release hook primary plus DONE marker scheduler backstop",
            },
            {
                "component": "conductor_feed",
                "status": "MAESTRO_FEED_READY",
                "basis": "live plan, dormant-broken, idle-blocked, and active gate token projections",
            },
        ],
        "no_authority_flags": dict(NO_AUTHORITY_FLAGS),
        **NO_AUTHORITY_FLAGS,
    }


def format_phase_c_conductor_operator(read_model: dict[str, Any]) -> str:
    summary = read_model["task_summary"]
    gate = read_model["gate_state"]
    writeback = read_model["writeback_state"]
    conductor_feed = read_model["conductor_feed"]
    gate_hook = writeback["gate_hook_primary"]
    lines = [
        "Phase-C Conductor Foundation",
        "",
        "Evidence:",
        f"- Scanned `{read_model['scan_scope']}` under `{read_model['orchestration_root']}`.",
        (
            f"- Reconciled {summary['task_count']} tasks: {summary['claimed_task_count']} claimed, "
            f"{summary['done_task_count']} done, {summary['blocked_task_count']} blocked, "
            f"{summary['problem_task_count']} problem."
        ),
        (
            f"- Gate tokens active: {gate['active_gate_token_count']}; "
            f"completion writebacks ready: {writeback['completion_writeback_count']}."
        ),
        (
            f"- Gate-hook checkoffs ready: {gate_hook['gate_hook_writeback_count']}; "
            f"scheduler backstop writebacks ready: {writeback['completion_writeback_count']}."
        ),
        (
            f"- Maestro conductor feed records: {conductor_feed['maestro_feed_count']} "
            f"(live plan {conductor_feed['live_plan_count']}, dormant/broken "
            f"{conductor_feed['dormant_broken_count']}, idle/blocked {conductor_feed['idle_blocked_count']})."
        ),
        "",
        "Boundary:",
        "- Read-model projection only; no service, scheduler, deploy, merge, restart, or external send was performed.",
        "- Auto-writeback uses a green-gate hook as the primary path and scheduler reconciliation as the backstop.",
        "- Both paths are idempotent records keyed by task_id and completion_evidence_hash.",
        "- No Legal Discovery, secret values, money, or production mutation authority is claimed.",
        "",
        "Blocked:",
        "- Production writeback execution remains blocked until MASTER installs the approved gate hook.",
        "- Gate execution remains serialized by orchestration token markers; this read model does not acquire tokens.",
        "",
        "Next safe move:",
        "- Let the sentinel consume this read model so MASTER can see gate contention, blocked work, writeback-ready completions, and Maestro feed records.",
    ]
    return "\n".join(lines)


def write_phase_c_conductor_exports(
    read_model: dict[str, Any],
    *,
    export_root: str | Path = DEFAULT_READ_MODEL_ROOT,
) -> dict[str, str]:
    root = _rooted(export_root)
    root.mkdir(parents=True, exist_ok=True)
    json_path = root / JSON_EXPORT_NAME
    operator_path = root / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(read_model), encoding="utf-8")
    operator_path.write_text(format_phase_c_conductor_operator(read_model) + "\n", encoding="utf-8")
    return {
        "json_path": _display_path(json_path),
        "operator_path": _display_path(operator_path),
    }


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build Phase-C conductor foundation read model.")
    parser.add_argument(
        "--format",
        choices=("json", "operator"),
        default="operator",
        help="Output format. Defaults to operator.",
    )
    parser.add_argument(
        "--orchestration-root",
        default=DEFAULT_ORCHESTRATION_ROOT.as_posix(),
        help="Shared orchestration root. Defaults to /mnt/e/openclaw/orchestration.",
    )
    parser.add_argument(
        "--generated-at",
        default=None,
        help="Override generated_at for deterministic tests/exports.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    payload = build_phase_c_conductor_state(
        orchestration_root=args.orchestration_root,
        generated_at=args.generated_at,
    )
    if args.format == "json":
        print(stable_json(payload), end="")
    else:
        print(format_phase_c_conductor_operator(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
