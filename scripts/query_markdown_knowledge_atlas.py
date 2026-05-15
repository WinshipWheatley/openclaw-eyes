#!/usr/bin/env python3
"""Query/report Markdown Knowledge Atlas v0 rows from the Business Ops ledger."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from business_ops_ledger import DEFAULT_DB_PATH
from markdown_knowledge_atlas import (
    REPORT_SECTIONS,
    format_markdown_report,
    query_markdown_report_section,
    stable_json,
)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Query Markdown Knowledge Atlas reports.")
    parser.add_argument("--db", default=DEFAULT_DB_PATH, help="SQLite ledger path.")
    parser.add_argument("--run-id", help="Optional Markdown Atlas run id. Defaults to latest.")
    parser.add_argument(
        "--report",
        choices=tuple(sorted(REPORT_SECTIONS)),
        default="summary",
        help="Report to emit.",
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
    payload = query_markdown_report_section(
        db_path=args.db,
        run_id=args.run_id,
        section=args.report,
    )
    if args.format == "json":
        print(stable_json(payload), end="")
    else:
        print(format_markdown_report(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
