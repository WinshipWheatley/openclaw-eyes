#!/usr/bin/env python3
"""autonomy_qualification.py

Generate a 24-hour autonomy scorecard with hard metrics.
Outputs JSON and markdown:
- /mnt/c/OpenClaw/logs/autonomy_qualification.json
- /home/openclaw/mac_eyes/Autonomy Qualification.md
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta
from pathlib import Path

ORCH_LOG = Path("/mnt/c/OpenClaw/logs/orchestrator.log")
APPROVAL_LOG = Path("/mnt/c/OpenClawShared/openclaw-vault/System/Approval Log.md")
STATUS_FILE = Path("/home/openclaw/polish_loop/status.json")
AUTO_HEAL_STATE = Path("/home/openclaw/mac_eyes/loop_auto_heal_state.json")
OUT_JSON = Path("/mnt/c/OpenClaw/logs/autonomy_qualification.json")
OUT_MD = Path("/home/openclaw/mac_eyes/Autonomy Qualification.md")


def _tail_lines(path: Path, max_lines: int = 3000) -> list[str]:
    if not path.exists():
        return []
    try:
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        return lines[-max_lines:]
    except Exception:
        return []


def _parse_orch_ts(line: str) -> datetime | None:
    m = re.match(r"^\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\]", line)
    if not m:
        return None
    try:
        return datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S")
    except Exception:
        return None


def _load_json(path: Path, default: dict) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def build_metrics() -> dict:
    now = datetime.now()
    cutoff = now - timedelta(hours=24)

    orch_lines = _tail_lines(ORCH_LOG)
    recent_orch = []
    for line in orch_lines:
        ts = _parse_orch_ts(line)
        if ts is not None and ts >= cutoff:
            recent_orch.append(line)

    parked = sum("pc_turn → parked" in l for l in recent_orch)
    blocked = sum("→ blocked" in l for l in recent_orch)
    approved = sum("mac_turn → approved" in l for l in recent_orch)
    resets = sum("[RESET]" in l for l in recent_orch)
    relaunch = sum("re-launch" in l.lower() for l in recent_orch)

    approval_lines = _tail_lines(APPROVAL_LOG)
    approval_recent = [l for l in approval_lines if re.search(r"^## \\d{4}-\\d{2}-\\d{2}", l)]
    # coarse count: decisions logged in last ~24h based on date substring only
    today = now.strftime("%Y-%m-%d")
    yesterday = (now - timedelta(days=1)).strftime("%Y-%m-%d")
    day_scoped = [l for l in approval_recent if today in l or yesterday in l]

    guardian_decisions = 0
    for i, line in enumerate(approval_lines):
        if line.startswith("- **Tier:**") and "L2-phone" in line:
            guardian_decisions += 1

    status = _load_json(STATUS_FILE, {})
    heal = _load_json(AUTO_HEAL_STATE, {})
    daily = heal.get("daily_metrics", {}) if isinstance(heal, dict) else {}

    metrics = {
        "window_hours": 24,
        "generated_at": now.isoformat(timespec="seconds"),
        "loop_status": status.get("status", "unknown"),
        "parked_events": parked,
        "blocked_events": blocked,
        "approved_transitions": approved,
        "relaunch_events": relaunch,
        "reset_events": resets,
        "guardian_decisions_logged": guardian_decisions,
        "autoheal_silent_fix_attempts": int(daily.get("silent_fix_attempts", 0)),
        "autoheal_silent_fix_successes": int(daily.get("silent_fix_successes", 0)),
    }

    # Qualification thresholds for 8-10h walk-away confidence.
    checks = {
        "status_not_stuck": metrics["loop_status"] not in {"blocked", "parked"},
        "parked_under_budget": metrics["parked_events"] <= 2,
        "blocked_under_budget": metrics["blocked_events"] <= 2,
        "guardian_interrupt_budget": metrics["guardian_decisions_logged"] <= 6,
        "autoheal_success_ratio_ok": (
            metrics["autoheal_silent_fix_successes"] >= 0
            and (
                metrics["autoheal_silent_fix_attempts"] == 0
                or metrics["autoheal_silent_fix_successes"] / metrics["autoheal_silent_fix_attempts"] >= 0.6
            )
        ),
    }
    metrics["checks"] = checks
    metrics["qualified"] = all(checks.values())
    return metrics


def write_outputs(metrics: dict) -> None:
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(metrics, indent=2), encoding="utf-8")

    check_lines = []
    for key, ok in metrics.get("checks", {}).items():
        check_lines.append(f"- {'PASS' if ok else 'FAIL'}: {key}")

    md = [
        "# Autonomy Qualification (24h)",
        "",
        f"Generated: {metrics.get('generated_at', '')}",
        "",
        "## Summary",
        "",
        f"- Qualified for walk-away window: {'YES' if metrics.get('qualified') else 'NO'}",
        f"- Current loop status: {metrics.get('loop_status', 'unknown')}",
        f"- Parked events: {metrics.get('parked_events', 0)}",
        f"- Blocked events: {metrics.get('blocked_events', 0)}",
        f"- Guardian decisions logged: {metrics.get('guardian_decisions_logged', 0)}",
        f"- Auto-heal fixes: {metrics.get('autoheal_silent_fix_successes', 0)}/{metrics.get('autoheal_silent_fix_attempts', 0)}",
        "",
        "## Hard Checks",
        "",
        *check_lines,
        "",
    ]
    OUT_MD.write_text("\n".join(md), encoding="utf-8")


def main() -> int:
    metrics = build_metrics()
    write_outputs(metrics)
    print(json.dumps(metrics, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
