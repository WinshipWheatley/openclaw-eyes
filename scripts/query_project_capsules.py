#!/usr/bin/env python3
"""Query Project Capsule v0 rows."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from business_ops_ledger import DEFAULT_DB_PATH
from project_capsule import (
    build_project_capsule_report,
    format_project_capsule_detail,
    format_project_capsule_report,
    get_project_capsule,
    stable_json,
)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Query bounded Project Capsule v0 rows.")
    parser.add_argument("--db", default=DEFAULT_DB_PATH, help="SQLite ledger path.")
    parser.add_argument("--run-id", help="Project capsule run id. Defaults to latest.")
    parser.add_argument("--project-id", help="Show a project capsule detail report.")
    parser.add_argument(
        "--report",
        choices=("summary",),
        default="summary",
        help="Report section.",
    )
    parser.add_argument(
        "--format",
        choices=("operator", "json"),
        default="operator",
        help="Output format.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    if args.project_id:
        payload = get_project_capsule(db_path=args.db, project_id=args.project_id)
        if args.format == "json":
            print(stable_json(payload or {"status": "not_found"}), end="")
        else:
            print(format_project_capsule_detail(payload))
        return 0
    report = build_project_capsule_report(db_path=args.db, run_id=args.run_id)
    if args.format == "json":
        print(stable_json(report), end="")
    else:
        print(format_project_capsule_report(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
