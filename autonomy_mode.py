#!/usr/bin/env python3
"""autonomy_mode.py

Walk-away autonomy mode toggle and status tool.

Modes:
- off
- focus_10h (strict low-interruption unattended profile)

State file:
  /mnt/c/OpenClaw/logs/autonomy_mode.json
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta
from pathlib import Path

STATE_FILE = Path("/mnt/c/OpenClaw/logs/autonomy_mode.json")
DEFAULT_WINDOW_HOURS = 10


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _default_state() -> dict:
    return {
        "mode": "off",
        "enabled_at": None,
        "expires_at": None,
        "label": "Manual mode",
        "guardian_triggers": [
            "external irreversible actions (email/publish/send)",
            "sensitive identity/financial operations (SSN, credentials, billing records)",
            "scope expansion (new integrations/capabilities/authority changes)",
            "broad drift containment requiring elevated authority",
        ],
    }


def load_state() -> dict:
    if not STATE_FILE.exists():
        return _default_state()
    try:
        data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return _default_state()
        base = _default_state()
        base.update(data)
        return base
    except Exception:
        return _default_state()


def save_state(state: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")


def mode_active(state: dict) -> bool:
    if state.get("mode") != "focus_10h":
        return False
    expires_at = (state.get("expires_at") or "").strip()
    if not expires_at:
        return False
    try:
        return datetime.fromisoformat(expires_at) > datetime.now()
    except Exception:
        return False


def cmd_enable(hours: int) -> int:
    now = datetime.now()
    state = _default_state()
    state.update(
        {
            "mode": "focus_10h",
            "enabled_at": now.isoformat(timespec="seconds"),
            "expires_at": (now + timedelta(hours=hours)).isoformat(timespec="seconds"),
            "label": f"Focus Mode ({hours}h walk-away)",
        }
    )
    save_state(state)
    print(json.dumps(state, indent=2))
    return 0


def cmd_disable() -> int:
    state = _default_state()
    save_state(state)
    print(json.dumps(state, indent=2))
    return 0


def cmd_status() -> int:
    state = load_state()
    state["active"] = mode_active(state)
    print(json.dumps(state, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Autonomy mode toggle")
    parser.add_argument("--enable-focus-10h", action="store_true", help="Enable focus autonomy mode for 10h")
    parser.add_argument("--enable-hours", type=int, help="Enable focus autonomy mode for N hours")
    parser.add_argument("--disable", action="store_true", help="Disable focus autonomy mode")
    parser.add_argument("--status", action="store_true", help="Show current autonomy mode")
    args = parser.parse_args()

    if args.enable_focus_10h:
        return cmd_enable(DEFAULT_WINDOW_HOURS)
    if args.enable_hours is not None:
        hours = max(1, min(24, args.enable_hours))
        return cmd_enable(hours)
    if args.disable:
        return cmd_disable()
    return cmd_status()


if __name__ == "__main__":
    raise SystemExit(main())
