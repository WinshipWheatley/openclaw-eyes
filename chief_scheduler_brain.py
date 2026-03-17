"""
chief_scheduler_brain.py

Time-block scheduler. Accept task + durations → start work block →
notify via Telegram when block ends → offer: continue / break /
switch task / stop → log what happened.

Triggered by:
  - "schedule [task] [X]min [Y]min break"
  - "timer [task] [X] minutes"
  - "continue" / "break" / "take break" / "switch [task]" / "stop"
  - "timer status" / "scheduler status"
Intent: scheduler in chief_router.py

Saves to:
  - /mnt/c/OpenClawShared/album/scheduler_state.json  (live state)
  - openclaw-vault/System/Scheduler Log.md             (history)
"""

import json
import re
import threading
from datetime import datetime, timedelta
from pathlib import Path

STATE_JSON = Path("/mnt/c/OpenClawShared/album/scheduler_state.json")
LOG_MD     = Path("/mnt/c/OpenClawShared/openclaw-vault/System/Scheduler Log.md")

_DEFAULT_WORK_MIN  = 45
_DEFAULT_BREAK_MIN = 15


# ── State ─────────────────────────────────────────────────────────────────────

def _load() -> dict:
    if STATE_JSON.exists():
        try:
            return json.loads(STATE_JSON.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"status": "idle", "blocks": []}


def _save(state: dict) -> None:
    STATE_JSON.parent.mkdir(parents=True, exist_ok=True)
    STATE_JSON.write_text(json.dumps(state, indent=2), encoding="utf-8")


# ── Log ───────────────────────────────────────────────────────────────────────

def _append_log(entry: dict) -> None:
    LOG_MD.parent.mkdir(parents=True, exist_ok=True)
    header = "---\ntype: scheduler-log\n---\n\n# Scheduler Log\n\n"
    existing = LOG_MD.read_text(encoding="utf-8") if LOG_MD.exists() else header
    note = f" | {entry['note']}" if entry.get("note") else ""
    line = (
        f"- [{entry['date']}] **{entry['task']}** — "
        f"{entry['type']} {entry['duration_min']}min{note}\n"
    )
    LOG_MD.write_text(existing + line, encoding="utf-8")


# ── Background timer ──────────────────────────────────────────────────────────

def _fire_timer(duration_min: int, block_type: str, task: str) -> None:
    import time
    time.sleep(duration_min * 60)

    state = _load()
    if state.get("status") != f"running_{block_type}":
        return  # block was cancelled or switched before it ended

    state["status"] = "prompting"
    _save(state)

    try:
        from chief_notify import send
        if block_type == "work":
            send(
                f"⏱ Work block done — {duration_min}min on *{task}*\n\n"
                "What next?\n"
                "  `continue` — start another block\n"
                "  `break` — take a break\n"
                "  `switch [task]` — switch tasks\n"
                "  `stop` — end session"
            )
        else:
            send(
                f"☕ Break done — {duration_min}min\n\n"
                "What next?\n"
                f"  `continue` — resume *{task}*\n"
                "  `switch [task]` — switch tasks\n"
                "  `stop` — end session"
            )
    except Exception:
        pass


def _start_timer(duration_min: int, block_type: str, task: str) -> None:
    t = threading.Thread(
        target=_fire_timer,
        args=(duration_min, block_type, task),
        daemon=True,
    )
    t.start()


# ── Parser ────────────────────────────────────────────────────────────────────

def _parse_start(text: str) -> tuple[str, int, int]:
    """Return (task, work_min, break_min) from a start command string."""
    # Strip command word
    stripped = re.sub(
        r"^\s*(schedule|timer|start\s+block|work\s+block)\s*",
        "", text, flags=re.IGNORECASE,
    ).strip()

    # Break duration: "break X" or "break Xmin"
    break_min = _DEFAULT_BREAK_MIN
    bm = re.search(r"break\s+(\d+)", stripped, re.IGNORECASE)
    if bm:
        break_min = max(1, min(60, int(bm.group(1))))

    # Remove break clause so we can isolate task + work duration
    core = re.sub(r"\s+break\s+\d+.*$", "", stripped, flags=re.IGNORECASE).strip()

    # Work duration: last number (with optional m/min) in core
    wm = re.search(r"(\d+)\s*m(?:in)?\s*$", core, re.IGNORECASE)
    if not wm:
        wm = re.search(r"(\d+)\s*$", core)
    if wm:
        work_min = max(1, min(180, int(wm.group(1))))
        task = core[:wm.start()].strip(" ,-:")
    else:
        work_min = _DEFAULT_WORK_MIN
        task = core.strip()

    if len(task) < 2:
        task = "Work block"
    return task, work_min, break_min


# ── Handlers ──────────────────────────────────────────────────────────────────

def _handle_start(text: str) -> list[str]:
    task, work_min, break_min = _parse_start(text)

    state = _load()
    state.update({
        "status":    "running_work",
        "task":      task,
        "work_min":  work_min,
        "break_min": break_min,
        "started":   datetime.now().isoformat(),
        "ends_at":   (datetime.now() + timedelta(minutes=work_min)).isoformat(),
    })
    state.setdefault("blocks", [])
    _save(state)
    _start_timer(work_min, "work", task)

    ends = (datetime.now() + timedelta(minutes=work_min)).strftime("%H:%M")
    return [f"⏱ Started: *{task}*\nWork {work_min}min | Break {break_min}min\nNotify at {ends}"]


def _handle_continue(state: dict) -> list[str]:
    task      = state.get("task", "Work block")
    work_min  = state.get("work_min", _DEFAULT_WORK_MIN)
    break_min = state.get("break_min", _DEFAULT_BREAK_MIN)

    _append_log({"date": datetime.now().strftime("%Y-%m-%d %H:%M"),
                 "task": task, "type": "continued", "duration_min": work_min})

    state.update({
        "status":  "running_work",
        "started": datetime.now().isoformat(),
        "ends_at": (datetime.now() + timedelta(minutes=work_min)).isoformat(),
    })
    _save(state)
    _start_timer(work_min, "work", task)

    ends = (datetime.now() + timedelta(minutes=work_min)).strftime("%H:%M")
    return [f"⏱ Continuing: *{task}*\n{work_min}min block. Notify at {ends}"]


def _handle_break(state: dict, text: str = "") -> list[str]:
    task      = state.get("task", "Work block")
    work_min  = state.get("work_min", _DEFAULT_WORK_MIN)
    # Allow inline override: "break 15"
    bm = re.search(r"break\s+(\d+)", text, re.IGNORECASE)
    break_min = max(1, min(60, int(bm.group(1)))) if bm else state.get("break_min", _DEFAULT_BREAK_MIN)
    state["break_min"] = break_min

    _append_log({"date": datetime.now().strftime("%Y-%m-%d %H:%M"),
                 "task": task, "type": "work", "duration_min": work_min})

    state.update({
        "status":  "running_break",
        "started": datetime.now().isoformat(),
        "ends_at": (datetime.now() + timedelta(minutes=break_min)).isoformat(),
    })
    _save(state)
    _start_timer(break_min, "break", task)

    ends = (datetime.now() + timedelta(minutes=break_min)).strftime("%H:%M")
    reply = f"☕ Break: {break_min}min. Notify at {ends}"

    # Surface any items held until next break
    try:
        from chief_focus_shield import surface_due
        from chief_notify import send as notify_send
        due = surface_due("next_break")
        if due:
            lines = [f"🔓 {len(due)} held idea(s) for your break:"]
            for h in due:
                lines.append(f"  • {h['id']}: {h.get('title', '—')}")
            notify_send("\n".join(lines))
    except Exception:
        pass

    return [reply]


def _handle_switch(text: str, state: dict) -> list[str]:
    new_task = re.sub(r"switch(\s+task)?", "", text, flags=re.IGNORECASE).strip(" ,-:")
    new_task = re.sub(r"\s+", " ", new_task).strip()
    if len(new_task) < 2:
        return ["What task do you want to switch to?"]

    old_task = state.get("task", "previous task")
    work_min = state.get("work_min", _DEFAULT_WORK_MIN)

    _append_log({"date": datetime.now().strftime("%Y-%m-%d %H:%M"),
                 "task": old_task, "type": "switched",
                 "duration_min": work_min, "note": f"→ {new_task}"})

    state.update({
        "status":  "running_work",
        "task":    new_task,
        "started": datetime.now().isoformat(),
        "ends_at": (datetime.now() + timedelta(minutes=work_min)).isoformat(),
    })
    _save(state)
    _start_timer(work_min, "work", new_task)

    ends = (datetime.now() + timedelta(minutes=work_min)).strftime("%H:%M")
    return [f"↩ Switched to: *{new_task}*\n{work_min}min block. Notify at {ends}"]


def _handle_stop(state: dict) -> list[str]:
    task     = state.get("task", "session")
    work_min = state.get("work_min", _DEFAULT_WORK_MIN)

    _append_log({"date": datetime.now().strftime("%Y-%m-%d %H:%M"),
                 "task": task, "type": "stopped", "duration_min": work_min})

    state.update({"status": "idle", "task": ""})
    _save(state)

    reply = "✓ Session ended. Log saved to vault/System/Scheduler Log.md"

    # Surface any items held until block completion
    try:
        from chief_focus_shield import surface_due
        from chief_notify import send as notify_send
        due = surface_due("after_current_block")
        if due:
            lines = [f"🔓 {len(due)} held idea(s) from your session:"]
            for h in due:
                lines.append(f"  • {h['id']}: {h.get('title', '—')}")
            notify_send("\n".join(lines))
    except Exception:
        pass

    return [reply]


def _handle_status(state: dict) -> list[str]:
    status = state.get("status", "idle")
    if status == "idle":
        return ["No active timer. Say `schedule [task] [X]min` to start."]
    if status == "prompting":
        task = state.get("task", "?")
        return [
            f"Block complete for *{task}*. What next?\n"
            "  `continue`  `break`  `switch [task]`  `stop`"
        ]
    task    = state.get("task", "?")
    ends_at = state.get("ends_at", "")
    try:
        ends_dt   = datetime.fromisoformat(ends_at)
        remaining = max(0, int((ends_dt - datetime.now()).total_seconds() / 60))
        time_str  = f"{remaining}min remaining (ends {ends_dt.strftime('%H:%M')})"
    except Exception:
        time_str = "time unknown"
    label = "Work" if "work" in status else "Break"
    return [f"⏱ {label}: *{task}* — {time_str}"]


# ── Public entry point ────────────────────────────────────────────────────────

def handle(text: str = "") -> list[str]:
    t     = text.lower().strip()
    state = _load()

    if any(k in t for k in ("timer status", "scheduler status", "block status")):
        return _handle_status(state)

    if any(k in t for k in ("stop for now", "stop session", "done for now", "end session")) or t == "stop":
        if state.get("status", "idle") == "idle":
            return ["No active session."]
        return _handle_stop(state)

    # Sticky: handle session commands whenever scheduler is active (any non-idle state)
    status = state.get("status", "idle")
    if status != "idle":
        if t == "continue":
            return _handle_continue(state)
        if t.startswith("break") or t in ("take break", "take a break"):
            return _handle_break(state, text)
        if t.startswith("switch"):
            return _handle_switch(text, state)
        if any(k in t for k in ("stop", "done")):
            return _handle_stop(state)
        if status == "prompting":
            return [
                "Block complete. What next?\n"
                "  `continue`  `break`  `switch [task]`  `stop`"
            ]

    # Start a new block
    if any(k in t for k in ("schedule ", "timer ", "start block", "work block")):
        return _handle_start(text)

    # Running — just show status
    if status in ("running_work", "running_break"):
        return _handle_status(state)

    return ["Say `schedule [task] [X]min` to start a work block."]


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    text = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "timer status"
    for line in handle(text):
        print(line)
