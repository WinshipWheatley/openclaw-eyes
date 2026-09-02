#!/usr/bin/env python3
"""Seed album work-log rows for the album songs the planner cannot see yet.

Dry-run by default: prints which songs are missing from the CSV and what would be written.
--apply writes one row per missing song with song_title, status=not_started, completion_pct=0
and touches nothing else. Existing rows are never changed. Safe to re-run.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import chief_album_io
from practice_loop import ALBUM_SONGS

SEED_ROW = {"status": "not_started", "completion_pct": "0"}


def plan_seed(songs: tuple[str, ...] = ALBUM_SONGS) -> dict[str, Any]:
    rows = chief_album_io.load_all_rows()
    present = {str(row.get("song_title") or "").strip().lower() for row in rows}
    missing = [title for title in songs if title.strip().lower() not in present]
    return {
        "csv_path": str(chief_album_io.CSV_PATH),
        "existing_row_count": len(rows),
        "album_song_count": len(songs),
        "missing": missing,
        "seed_fields": dict(SEED_ROW),
    }


def apply_seed(plan: dict[str, Any]) -> list[str]:
    written: list[str] = []
    for title in plan["missing"]:
        chief_album_io.upsert_csv_row({"song_title": title, **SEED_ROW})
        written.append(title)
    return written


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed missing album song rows (dry-run unless --apply).")
    parser.add_argument("--apply", action="store_true", help="Write the missing rows.")
    parser.add_argument("--csv", default=None, help="Override the album work log path (tests).")
    parser.add_argument("--format", choices=("operator", "json"), default="operator")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    if args.csv:
        chief_album_io.CSV_PATH = Path(args.csv)
    plan = plan_seed()
    written = apply_seed(plan) if args.apply else []
    summary = {**plan, "applied": bool(args.apply), "written": written}
    if args.format == "json":
        print(json.dumps(summary, indent=2, sort_keys=True))
        return 0
    print("Album Row Seed v0")
    print("")
    print(f"CSV: `{plan['csv_path']}`  existing rows: `{plan['existing_row_count']}`  album songs: `{plan['album_song_count']}`")
    if not plan["missing"]:
        print("Nothing missing; every album song already has a row.")
    else:
        verb = "Wrote" if args.apply else "Would write"
        print(f"{verb} {len(plan['missing'])} row(s) with status=not_started, completion_pct=0:")
        for title in plan["missing"]:
            print(f"- {title}")
        if not args.apply:
            print("")
            print("Dry run: nothing written. Re-run with --apply.")
    print("")
    print("Boundary: album CSV only; no audio read, no DAW, no send.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
