#!/usr/bin/env python3
"""Query approved Markdown evidence rows."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from business_ops_ledger import DEFAULT_DB_PATH
from markdown_evidence_ingestion import (
    REPORT_SECTIONS,
    format_markdown_evidence_report,
    query_markdown_evidence,
    stable_json,
)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Query approved Markdown evidence v0.")
    parser.add_argument("--db", default=DEFAULT_DB_PATH, help="SQLite ledger path.")
    parser.add_argument("--run-id", help="Optional evidence run id.")
    parser.add_argument("--report", choices=tuple(sorted(REPORT_SECTIONS)), default="summary")
    parser.add_argument("--query", help="Optional substring query over bounded excerpts/headings.")
    parser.add_argument("--format", choices=("operator", "json"), default="operator")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    payload = query_markdown_evidence(
        db_path=args.db,
        report=args.report,
        query=args.query,
        run_id=args.run_id,
    )
    if args.format == "json":
        print(stable_json(payload), end="")
    else:
        print(format_markdown_evidence_report(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
