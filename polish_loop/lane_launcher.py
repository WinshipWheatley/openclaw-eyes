#!/usr/bin/env python3
"""Capacity-aware detached lane launcher for the polish loop.

This module is intentionally event-driven: an orchestrator/master decision is
submitted once, the launcher records what it started or queued, then exits.
Workers are detached process groups; full green gates remain serialized through
the existing gate-token protocol.
"""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
import errno
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
from typing import Any, Callable


SCHEMA_VERSION = "polish_loop_lane_registry_v0"
EVENT_SCHEMA_VERSION = "polish_loop_lane_event_v0"
DEFAULT_BASE_REF = "origin/codex/maestro-author"
DEFAULT_GATE_TOKEN_DIR = Path("/mnt/e/openclaw/orchestration/inbox/to-claude")
DEFAULT_FLEET_PROTOCOL_PATH = Path("/mnt/e/openclaw/orchestration/FLEET-PROTOCOL.md")
DEFAULT_REGISTRY_PATH = Path("/home/openclaw/polish_loop/lane_registry.json")
DEFAULT_LANES_ROOT = Path("/home/openclaw/worktrees/polish-loop-lanes")
DEFAULT_LOG_PATH = Path("/mnt/c/OpenClaw/logs/polish_loop_lane_launcher.jsonl")
DEFAULT_MAX_PARALLEL_LANES = 2
FALLBACK_FLEET_PROTOCOL = """# OpenClaw Fleet Protocol

Workers use a two-tier gate:
- FAST pre-gate: focused tests only, parallel-safe, no full-gate token.
- FULL gate: `scripts/green_gate.sh <branch>` only after the atomic full-gate lock is available.

The FULL gate lock is atomic and lives outside lane-local worktrees. Do not merge,
deploy, restart production, force-push, send external messages, or bypass SEND_HOLD.
"""

TERMINAL_STATUSES = {"dead", "finished", "launch_failed", "cancelled"}
ACTIVE_STATUSES = {"starting", "running"}
AUTHORIZED_ROLE_TOKENS = ("opus", "orchestrator", "master", "winship")


@dataclass(frozen=True)
class LauncherConfig:
    repo_root: Path
    registry_path: Path = DEFAULT_REGISTRY_PATH
    lanes_root: Path = DEFAULT_LANES_ROOT
    log_path: Path = DEFAULT_LOG_PATH
    gate_token_dir: Path = DEFAULT_GATE_TOKEN_DIR
    fleet_protocol_path: Path = DEFAULT_FLEET_PROTOCOL_PATH
    base_ref: str = DEFAULT_BASE_REF
    max_parallel_lanes: int = DEFAULT_MAX_PARALLEL_LANES
    create_worktrees: bool = True
    default_worker_command: tuple[str, ...] = ()


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def stable_json(data: Mapping[str, Any]) -> str:
    return json.dumps(data, indent=2, sort_keys=True) + "\n"


def _empty_registry() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "lanes": {},
        "queue": [],
        "updated_at": utc_now(),
        "gate_policy": {
            "full_green_gate_serialized": True,
            "token_protocol": "scripts/green_gate.sh uses an atomic FULL gate lock; use --fast for focused pre-gate",
            "fast_pre_gate_parallel_safe": True,
        },
    }


def load_registry(path: str | Path = DEFAULT_REGISTRY_PATH) -> dict[str, Any]:
    target = Path(path)
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except Exception:
        payload = _empty_registry()
    if not isinstance(payload, dict):
        payload = _empty_registry()
    if not isinstance(payload.get("lanes"), dict):
        payload["lanes"] = {}
    if not isinstance(payload.get("queue"), list):
        payload["queue"] = []
    payload["schema_version"] = SCHEMA_VERSION
    payload.setdefault("gate_policy", _empty_registry()["gate_policy"])
    return payload


def save_registry(payload: Mapping[str, Any], path: str | Path = DEFAULT_REGISTRY_PATH) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    data = dict(payload)
    data["schema_version"] = SCHEMA_VERSION
    data["updated_at"] = utc_now()
    tmp = target.with_name(f"{target.name}.tmp")
    tmp.write_text(stable_json(data), encoding="utf-8")
    os.replace(tmp, target)


def append_event(config: LauncherConfig, event_type: str, details: Mapping[str, Any]) -> None:
    config.log_path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "schema_version": EVENT_SCHEMA_VERSION,
        "event_type": event_type,
        "at": utc_now(),
        **dict(details),
    }
    with config.log_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, sort_keys=True) + "\n")


def _slug(value: str, *, fallback: str) -> str:
    raw = str(value or "").strip().lower()
    raw = re.sub(r"[^a-z0-9._/-]+", "-", raw)
    raw = re.sub(r"-+", "-", raw).strip("-./")
    raw = raw.replace("..", ".")
    return raw or fallback


def _lane_id(raw_lane: Mapping[str, Any], index: int) -> str:
    return _slug(str(raw_lane.get("lane_id") or raw_lane.get("id") or f"lane-{index + 1}"), fallback=f"lane-{index + 1}")


def _branch_for_lane(raw_lane: Mapping[str, Any], lane_id: str) -> str:
    configured = str(raw_lane.get("branch") or "").strip()
    if configured:
        return _slug(configured, fallback=f"codex/polish-lane-{lane_id}")
    return f"codex/polish-lane-{lane_id}"


def _worktree_for_lane(config: LauncherConfig, lane_id: str) -> Path:
    return config.lanes_root / lane_id


def _decision_authorized(decision: Mapping[str, Any]) -> tuple[bool, str]:
    authorization = decision.get("authorization")
    auth_map = authorization if isinstance(authorization, Mapping) else {}
    explicitly_authorized = bool(
        decision.get("parallel_lanes_authorized")
        or decision.get("authorized")
        or auth_map.get("parallel_lanes_authorized")
        or auth_map.get("fanout_authorized")
    )
    human_supervised = bool(
        decision.get("human_supervised")
        or auth_map.get("human_supervised")
        or auth_map.get("master_supervised")
    )
    role_text = " ".join(
        str(value or "")
        for value in (
            decision.get("authorized_by"),
            decision.get("authorized_by_role"),
            auth_map.get("authorized_by"),
            auth_map.get("role"),
        )
    ).lower()
    role_ok = any(token in role_text for token in AUTHORIZED_ROLE_TOKENS)
    if not explicitly_authorized:
        return False, "parallel lanes not explicitly authorized"
    if not human_supervised:
        return False, "human/master supervision flag missing"
    if not role_ok:
        return False, "authorized_by role is not orchestrator/master/Opus"
    return True, "authorized"


def _lane_specs(decision: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    lanes = decision.get("lanes") or decision.get("tasks") or []
    if not isinstance(lanes, list):
        return []
    return [lane for lane in lanes if isinstance(lane, Mapping)]


def _configured_capacity(config: LauncherConfig) -> int:
    configured = max(0, int(config.max_parallel_lanes))
    env_value = os.environ.get("OPENCLAW_POLISH_MAX_PARALLEL_LANES", "").strip()
    if env_value:
        try:
            configured = min(configured, max(0, int(env_value)))
        except ValueError:
            pass
    cpu_count = os.cpu_count() or 1
    cpu_bound = max(1, cpu_count - 1)
    return max(0, min(configured, cpu_bound))


def running_lane_count(registry: Mapping[str, Any]) -> int:
    lanes = registry.get("lanes", {})
    if not isinstance(lanes, Mapping):
        return 0
    return sum(1 for record in lanes.values() if isinstance(record, Mapping) and record.get("status") in ACTIVE_STATUSES)


def capacity_snapshot(config: LauncherConfig, registry: Mapping[str, Any]) -> dict[str, int]:
    max_lanes = _configured_capacity(config)
    running = running_lane_count(registry)
    return {
        "max_parallel_lanes": max_lanes,
        "running_lanes": running,
        "available_lanes": max(0, max_lanes - running),
    }


def _default_worker_command(config: LauncherConfig, lane_id: str, task_text: str, worktree: Path) -> list[str]:
    env_command = os.environ.get("OPENCLAW_POLISH_LANE_WORKER_CMD", "").strip()
    if env_command:
        return shlex.split(env_command)
    if config.default_worker_command:
        return [part.format(lane_id=lane_id, worktree=str(worktree)) for part in config.default_worker_command]

    local_builder = config.repo_root / "polish_loop" / "local_builder.py"
    if local_builder.exists():
        return [sys.executable, str(local_builder), "--lane-id", lane_id]

    escaped_task = task_text.replace("\n", " ")[:500]
    return [
        "codex",
        "exec",
        "--sandbox",
        "danger-full-access",
        "--",
        f"Build polish-loop lane {lane_id}: {escaped_task}",
    ]


def _command_for_lane(config: LauncherConfig, raw_lane: Mapping[str, Any], lane_id: str, worktree: Path) -> list[str]:
    command = raw_lane.get("worker_command") or raw_lane.get("command")
    if isinstance(command, str) and command.strip():
        return shlex.split(command)
    if isinstance(command, Sequence) and not isinstance(command, (str, bytes)):
        return [str(part) for part in command if str(part)]
    task_text = str(raw_lane.get("task") or raw_lane.get("spec") or raw_lane.get("title") or lane_id)
    return _default_worker_command(config, lane_id, task_text, worktree)


def _safe_env(lane_id: str, decision_id: str, fleet_protocol_path: Path | None = None) -> dict[str, str]:
    env = dict(os.environ)
    env["OPENCLAW_SEND_HOLD"] = "1"
    env["OPENCLAW_TEST_MODE"] = env.get("OPENCLAW_TEST_MODE", "1")
    env["OPENCLAW_LANE_ID"] = lane_id
    env["OPENCLAW_PARALLEL_DECISION_ID"] = decision_id
    env["OPENCLAW_GATE_SERIALIZED"] = "1"
    if fleet_protocol_path is not None:
        env["OPENCLAW_FLEET_PROTOCOL_PATH"] = str(fleet_protocol_path)
    return env


def _prepare_worktree(config: LauncherConfig, branch: str, worktree: Path) -> None:
    if not config.create_worktrees:
        worktree.mkdir(parents=True, exist_ok=True)
        return
    worktree.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["git", "worktree", "add", "-B", branch, str(worktree), config.base_ref],
        cwd=str(config.repo_root),
        check=True,
        capture_output=True,
        text=True,
    )


def _stamp_fleet_protocol(config: LauncherConfig, worktree: Path) -> Path:
    stamp = worktree / ".openclaw_lane" / "FLEET-PROTOCOL.md"
    stamp.parent.mkdir(parents=True, exist_ok=True)
    source = config.fleet_protocol_path
    if source.exists():
        protocol_text = source.read_text(encoding="utf-8")
    else:
        protocol_text = FALLBACK_FLEET_PROTOCOL
    stamp.write_text(protocol_text, encoding="utf-8")
    return stamp


def _launch_lane(config: LauncherConfig, decision_id: str, raw_lane: Mapping[str, Any], index: int) -> dict[str, Any]:
    lane_id = _lane_id(raw_lane, index)
    branch = _branch_for_lane(raw_lane, lane_id)
    worktree = _worktree_for_lane(config, lane_id)
    command = _command_for_lane(config, raw_lane, lane_id, worktree)
    task_text = str(raw_lane.get("task") or raw_lane.get("spec") or raw_lane.get("title") or lane_id).strip()
    now = utc_now()
    record: dict[str, Any] = {
        "lane_id": lane_id,
        "decision_id": decision_id,
        "task": task_text,
        "branch": branch,
        "worktree": str(worktree),
        "status": "starting",
        "pid": None,
        "command": command,
        "created_at": now,
        "updated_at": now,
        "heartbeat_at": None,
        "bounds": {
            "send_hold": True,
            "branch_only": True,
            "no_merge_to_master": True,
            "no_force_push": True,
            "no_prod_restart": True,
        },
        "gate_policy": {
            "full_green_gate_serialized": True,
            "gate_token_dir": str(config.gate_token_dir),
            "worker_may_run_full_gate_without_token": False,
            "fast_pre_gate_parallel_safe": True,
            "atomic_full_gate_lock": True,
        },
    }
    try:
        _prepare_worktree(config, branch, worktree)
        log_dir = worktree / ".openclaw_lane"
        log_dir.mkdir(parents=True, exist_ok=True)
        protocol_stamp = _stamp_fleet_protocol(config, worktree)
        output_log = log_dir / "worker.out"
        stdout_handle = output_log.open("a", encoding="utf-8")
        try:
            process = subprocess.Popen(
                command,
                cwd=str(worktree),
                env=_safe_env(lane_id, decision_id, protocol_stamp),
                stdin=subprocess.DEVNULL,
                stdout=stdout_handle,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
        finally:
            stdout_handle.close()
        record.update(
            {
                "status": "running",
                "pid": int(process.pid),
                "started_at": utc_now(),
                "heartbeat_at": utc_now(),
                "output_log": str(output_log),
                "protocol_stamp": str(protocol_stamp),
            }
        )
        append_event(config, "lane_launched", {"lane_id": lane_id, "pid": int(process.pid), "branch": branch})
    except Exception as exc:
        record.update({"status": "launch_failed", "error": f"{exc.__class__.__name__}: {exc}", "updated_at": utc_now()})
        append_event(config, "lane_launch_failed", {"lane_id": lane_id, "error": record["error"]})
    return record


def _queue_lane(config: LauncherConfig, decision_id: str, raw_lane: Mapping[str, Any], index: int, reason: str) -> dict[str, Any]:
    lane_id = _lane_id(raw_lane, index)
    worktree = _worktree_for_lane(config, lane_id)
    record = {
        "lane_id": lane_id,
        "decision_id": decision_id,
        "task": str(raw_lane.get("task") or raw_lane.get("spec") or raw_lane.get("title") or lane_id).strip(),
        "branch": _branch_for_lane(raw_lane, lane_id),
        "worktree": str(worktree),
        "status": "queued",
        "pid": None,
        "queued_at": utc_now(),
        "queue_reason": reason,
        "gate_policy": {
            "full_green_gate_serialized": True,
            "gate_token_dir": str(config.gate_token_dir),
            "fast_pre_gate_parallel_safe": True,
            "atomic_full_gate_lock": True,
        },
    }
    append_event(config, "lane_queued", {"lane_id": lane_id, "reason": reason})
    return record


def submit_parallelization_decision(
    decision: Mapping[str, Any],
    *,
    config: LauncherConfig,
) -> dict[str, Any]:
    registry = load_registry(config.registry_path)
    reaped = reap_lanes(config=config, registry=registry)
    registry = reaped["registry"]

    authorized, reason = _decision_authorized(decision)
    decision_id = str(decision.get("decision_id") or decision.get("id") or f"decision-{utc_now()}").strip()
    lane_specs = _lane_specs(decision)
    if not authorized:
        append_event(config, "decision_rejected", {"decision_id": decision_id, "reason": reason})
        return {
            "status": "rejected",
            "reason": reason,
            "decision_id": decision_id,
            "launched": [],
            "queued": [],
            "reaped": reaped["reaped"],
        }
    if not lane_specs:
        append_event(config, "decision_rejected", {"decision_id": decision_id, "reason": "no lanes supplied"})
        return {
            "status": "rejected",
            "reason": "no lanes supplied",
            "decision_id": decision_id,
            "launched": [],
            "queued": [],
            "reaped": reaped["reaped"],
        }

    capacity = capacity_snapshot(config, registry)
    available = capacity["available_lanes"]
    launched: list[str] = []
    queued: list[str] = []

    for index, raw_lane in enumerate(lane_specs):
        lane_id = _lane_id(raw_lane, index)
        existing = registry["lanes"].get(lane_id)
        if isinstance(existing, Mapping) and existing.get("status") in ACTIVE_STATUSES | {"queued"}:
            queued.append(lane_id)
            continue
        if available <= 0:
            record = _queue_lane(config, decision_id, raw_lane, index, "capacity_exhausted")
            registry["lanes"][lane_id] = record
            registry["queue"].append(lane_id)
            queued.append(lane_id)
            continue
        record = _launch_lane(config, decision_id, raw_lane, index)
        registry["lanes"][lane_id] = record
        if record["status"] == "running":
            launched.append(lane_id)
            available -= 1
        else:
            queued.append(lane_id)

    save_registry(registry, config.registry_path)
    append_event(
        config,
        "decision_processed",
        {
            "decision_id": decision_id,
            "launched": launched,
            "queued": queued,
            "capacity": capacity,
        },
    )
    return {
        "status": "accepted",
        "decision_id": decision_id,
        "launched": launched,
        "queued": queued,
        "capacity": capacity,
        "reaped": reaped["reaped"],
        "registry_path": str(config.registry_path),
    }


def default_pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except OSError as exc:
        return exc.errno == errno.EPERM
    return True


def reap_lanes(
    *,
    config: LauncherConfig,
    registry: Mapping[str, Any] | None = None,
    pid_alive: Callable[[int], bool] = default_pid_alive,
) -> dict[str, Any]:
    payload = dict(registry or load_registry(config.registry_path))
    payload.setdefault("lanes", {})
    reaped: list[str] = []
    for lane_id, raw_record in list(payload["lanes"].items()):
        if not isinstance(raw_record, dict):
            continue
        if raw_record.get("status") not in ACTIVE_STATUSES:
            continue
        try:
            pid = int(raw_record.get("pid") or 0)
        except (TypeError, ValueError):
            pid = 0
        if pid and pid_alive(pid):
            continue
        raw_record["status"] = "dead"
        raw_record["reaped_at"] = utc_now()
        raw_record["updated_at"] = raw_record["reaped_at"]
        reaped.append(str(lane_id))
        append_event(config, "lane_reaped_dead", {"lane_id": lane_id, "pid": pid})
    if reaped:
        save_registry(payload, config.registry_path)
    return {"registry": payload, "reaped": reaped}


def record_lane_heartbeat(lane_id: str, *, config: LauncherConfig) -> dict[str, Any]:
    registry = load_registry(config.registry_path)
    record = registry["lanes"].get(lane_id)
    if not isinstance(record, dict):
        raise KeyError(f"unknown lane_id: {lane_id}")
    record["heartbeat_at"] = utc_now()
    record["updated_at"] = record["heartbeat_at"]
    save_registry(registry, config.registry_path)
    append_event(config, "lane_heartbeat", {"lane_id": lane_id})
    return record


def active_gate_token_present(token_dir: str | Path = DEFAULT_GATE_TOKEN_DIR) -> bool:
    root = Path(token_dir)
    claims = sorted(root.glob("CLAIM-GATE-TOKEN-*"), key=lambda p: p.stat().st_mtime)
    releases = sorted(root.glob("RELEASE-GATE-TOKEN-*"), key=lambda p: p.stat().st_mtime)
    if not claims:
        return False
    latest_claim = claims[-1].stat().st_mtime
    latest_release = releases[-1].stat().st_mtime if releases else -1
    return latest_claim > latest_release


def gate_token_state(token_dir: str | Path = DEFAULT_GATE_TOKEN_DIR) -> dict[str, Any]:
    root = Path(token_dir)
    claims = sorted(root.glob("CLAIM-GATE-TOKEN-*"), key=lambda p: p.stat().st_mtime)
    releases = sorted(root.glob("RELEASE-GATE-TOKEN-*"), key=lambda p: p.stat().st_mtime)
    return {
        "gate_available": not active_gate_token_present(root),
        "latest_claim": claims[-1].name if claims else "",
        "latest_release": releases[-1].name if releases else "",
        "token_dir": str(root),
    }


def _config_from_args(args: argparse.Namespace) -> LauncherConfig:
    command = tuple(shlex.split(args.worker_command)) if args.worker_command else ()
    return LauncherConfig(
        repo_root=Path(args.repo_root).resolve(),
        registry_path=Path(args.registry),
        lanes_root=Path(args.lanes_root),
        log_path=Path(args.log_path),
        gate_token_dir=Path(args.gate_token_dir),
        fleet_protocol_path=DEFAULT_FLEET_PROTOCOL_PATH,
        base_ref=args.base_ref,
        max_parallel_lanes=args.max_parallel_lanes,
        create_worktrees=not args.no_worktrees,
        default_worker_command=command,
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Submit or inspect polish-loop parallel lane launches.")
    parser.add_argument("--repo-root", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--registry", default=str(DEFAULT_REGISTRY_PATH))
    parser.add_argument("--lanes-root", default=str(DEFAULT_LANES_ROOT))
    parser.add_argument("--log-path", default=str(DEFAULT_LOG_PATH))
    parser.add_argument("--gate-token-dir", default=str(DEFAULT_GATE_TOKEN_DIR))
    parser.add_argument("--base-ref", default=DEFAULT_BASE_REF)
    parser.add_argument("--max-parallel-lanes", type=int, default=DEFAULT_MAX_PARALLEL_LANES)
    parser.add_argument("--worker-command", default="")
    parser.add_argument("--no-worktrees", action="store_true")
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--submit", help="Path to orchestrator parallelization decision JSON.")
    action.add_argument("--reap", action="store_true", help="Reap dead running lanes and print registry state.")
    action.add_argument("--status", action="store_true", help="Print registry and gate-token state.")
    args = parser.parse_args(argv)
    config = _config_from_args(args)

    if args.submit:
        decision = json.loads(Path(args.submit).read_text(encoding="utf-8"))
        result = submit_parallelization_decision(decision, config=config)
        print(stable_json(result), end="")
        return 0 if result["status"] == "accepted" else 2
    if args.reap:
        result = reap_lanes(config=config)
        print(stable_json(result), end="")
        return 0
    registry = load_registry(config.registry_path)
    print(stable_json({"registry": registry, "gate_token": gate_token_state(config.gate_token_dir)}), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
