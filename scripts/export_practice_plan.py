#!/usr/bin/env python3
"""Export today's practice plan read model (local store only; no model, no DAW, no send)."""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import practice_loop


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export the practice plan read model.")
    parser.add_argument("--db", default=str(practice_loop.DEFAULT_DB_PATH), help="Practice store path.")
    parser.add_argument("--now", default=None, help="ISO timestamp override (tests).")
    parser.add_argument("--minutes", type=int, default=practice_loop.DEFAULT_PLAN_MINUTES)
    parser.add_argument("--export-root", default=str(practice_loop.DEFAULT_EXPORT_ROOT))
    parser.add_argument("--format", choices=("operator", "json"), default="operator")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    now = datetime.fromisoformat(args.now.replace("Z", "+00:00")) if args.now else datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    summary = practice_loop.export_practice_plan(db_path=args.db, export_root=args.export_root, now=now, minutes_budget=args.minutes)
    if args.format == "json":
        print(practice_loop.stable_json(summary), end="")
    else:
        print("Practice Plan Export v0")
        print("")
        print(f"JSON: `{summary['json_path']}`")
        print(f"Operator: `{summary['operator_path']}`")
        print(f"Songs: `{summary['song_count']}`  Plan slots: `{summary['plan_count']}`")
        print("")
        print("Boundary: local practice store only; no DAW, audio, calendar, send, or model call.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
