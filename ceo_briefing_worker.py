#!/usr/bin/env python3
"""Resilient 8:00 AM EST CEO briefing worker for Deep-Flight autopilot."""

from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path

try:
    from zoneinfo import ZoneInfo
except Exception:  # pragma: no cover
    ZoneInfo = None  # type: ignore

import chief_ceo_briefing as brief

SENTINEL_DIR = Path("/mnt/c/OpenClaw/logs")
WORKER_LOG = SENTINEL_DIR / "ceo_briefing_worker.log"
MAX_RETRIES = 5
RETRY_SLEEP = 600  # 10 min


def _log(msg: str) -> None:
    SENTINEL_DIR.mkdir(parents=True, exist_ok=True)
    with open(WORKER_LOG, "a", encoding="utf-8") as f:
        f.write(f"[{datetime.now().isoformat()}] {msg}\n")


def _sentinel(today_key: str) -> Path:
    return SENTINEL_DIR / f"ceo_briefing_sent_{today_key}.txt"


def _now_est() -> datetime:
    if ZoneInfo:
        return datetime.now(ZoneInfo("America/New_York"))
    return datetime.now()


def _try_send_with_retries(today_key: str) -> bool:
    for attempt in range(1, MAX_RETRIES + 1):
        ok, detail = brief.send_summary()
        if ok:
            _sentinel(today_key).write_text(f"sent at {_now_est().isoformat()} via {detail}\n", encoding="utf-8")
            _log(f"sent on attempt={attempt} via {detail}")
            return True
        _log(f"attempt={attempt} failed: {detail}")
        if attempt < MAX_RETRIES:
            time.sleep(RETRY_SLEEP)
    return False


def main() -> None:
    brief._load_env()
    _log("worker started")

    while True:
        now = _now_est()
        today_key = now.date().isoformat()
        sent_file = _sentinel(today_key)

        if now.hour == 8 and now.minute == 0 and not sent_file.exists():
            _log("8:00 window reached; sending briefing")
            _try_send_with_retries(today_key)

        time.sleep(30)


if __name__ == "__main__":
    main()
