#!/usr/bin/env python3
"""
Generate a live runtime snapshot at docs/_ai/runtime_snapshot.md.

This file is machine-written. Do not edit by hand.
Run: python3 generate_runtime_snapshot.py
"""

from __future__ import annotations

import json
import subprocess
from datetime import datetime
from pathlib import Path

SNAPSHOT_PATH = Path("/home/openclaw/docs/_ai/runtime_snapshot.md")

SESSION_FILE   = Path("/home/openclaw/OpenClaw/state/chief_session.json")
LOOP_STATUS    = Path("/home/openclaw/polish_loop/status.json")
QUEUE_LOG      = Path("/mnt/c/OpenClaw/logs/claude_queue.log")
STAGING_ROOT   = Path("/home/openclaw/staging")

HARNESS_LANES = [
    ("morning_brief",          STAGING_ROOT / "morning_brief_harness" / "runs"),
    ("chief_end_of_day_review", STAGING_ROOT / "chief_eod_harness"    / "runs"),
]


def _read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _session_summary() -> str:
    s = _read_json(SESSION_FILE)
    if not s:
        return "(unavailable)"
    workflow = s.get("active_workflow") or "none"
    mode     = s.get("active_mode")     or "none"
    step     = s.get("step", 0)
    return f"workflow={workflow}  mode={mode}  step={step}"


def _loop_status_summary() -> str:
    s = _read_json(LOOP_STATUS)
    if not s:
        return "(unavailable)"
    status      = s.get("status", "?")
    task        = s.get("task_name") or "none"
    block       = s.get("block_reason") or ""
    updated     = s.get("last_updated", "?")
    block_note  = f"  block={block}" if block else ""
    return f"status={status}  task={task}{block_note}  updated={updated}"


def _live_processes() -> list[str]:
    try:
        result = subprocess.run(
            ["pgrep", "-af", "python"],
            capture_output=True, text=True, timeout=5, check=False,
        )
        lines = [
            ln.strip() for ln in result.stdout.splitlines()
            if "chief" in ln or "cassandra" in ln or "guardian" in ln
        ]
        return lines or ["(no chief/cassandra/guardian processes found)"]
    except Exception as e:
        return [f"(pgrep unavailable: {e})"]


def _queue_summary() -> str:
    if not QUEUE_LOG.exists():
        return "(queue log not found)"
    try:
        lines = [ln.strip() for ln in QUEUE_LOG.read_text(errors="replace").splitlines() if ln.strip()]
    except Exception as e:
        return f"(unreadable: {e})"
    if not lines:
        return "empty"
    return f"{len(lines)} entries — last: {lines[-1][:120]}"


def _latest_harness_run(runs_dir: Path) -> str:
    if not runs_dir.exists():
        return "(no runs)"
    run_dirs = sorted(
        (d for d in runs_dir.iterdir() if d.is_dir()),
        key=lambda d: d.stat().st_mtime,
        reverse=True,
    )
    if not run_dirs:
        return "(no runs)"
    latest = run_dirs[0]
    manifest_path = latest / "manifest.json"
    if not manifest_path.exists():
        return f"{latest.name} (no manifest)"
    m = _read_json(manifest_path)
    lane    = m.get("structured_output_lane") or m.get("inference_mode") or "?"
    summary = (m.get("summary") or "")[:80].strip()
    dry_run = "dry-run" if m.get("dry_run") else "live"
    return f"{latest.name}  mode={dry_run}  lane={lane}  summary={summary!r}"


def _model_lanes() -> str:
    try:
        import chief_llm as llm
        fast   = llm.LOCAL_MODEL_LANES["fast"][0]
        strong = llm.LOCAL_MODEL_LANES["strong"][0]
        deep   = llm.LOCAL_MODEL_LANES["deep"][0]
        return f"fast={fast}  strong={strong}  deep={deep}"
    except Exception as e:
        return f"(unavailable: {e})"


def generate() -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    proc_lines = _live_processes()

    lines = [
        "<!-- GENERATED — do not edit by hand. Run: python3 generate_runtime_snapshot.py -->",
        f"# Runtime Snapshot",
        f"_Generated: {now} — live evidence only, not doctrine._",
        "",
        "## Session",
        f"    {_session_summary()}",
        "",
        "## Loop Status",
        f"    {_loop_status_summary()}",
        "",
        "## Live Processes",
    ]
    for p in proc_lines:
        lines.append(f"    {p}")
    lines += [
        "",
        "## Queue",
        f"    {_queue_summary()}",
        "",
        "## Latest Harness Runs",
    ]
    for flow, runs_dir in HARNESS_LANES:
        lines.append(f"    {flow}: {_latest_harness_run(runs_dir)}")
    lines += [
        "",
        "## Model Lanes",
        f"    {_model_lanes()}",
        "",
        "---",
        "_This file is overwritten on each run. Source: `generate_runtime_snapshot.py`_",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    content = generate()
    SNAPSHOT_PATH.parent.mkdir(parents=True, exist_ok=True)
    SNAPSHOT_PATH.write_text(content, encoding="utf-8")
    print(SNAPSHOT_PATH)


if __name__ == "__main__":
    main()
