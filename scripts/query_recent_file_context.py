#!/usr/bin/env python3
"""Query Recent File Context v0 reports and phrase resolutions."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from business_ops_ledger import DEFAULT_DB_PATH
from recent_file_context import (
    REPORT_SECTIONS,
    build_recent_file_context_report,
    format_recent_file_context_report,
    format_resolution_result,
    resolve_recent_file_reference,
    stable_json,
)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Query Recent File Context v0.")
    parser.add_argument("--db", default=DEFAULT_DB_PATH, help="SQLite ledger path.")
    parser.add_argument("--run-id", help="Optional recent context run id.")
    parser.add_argument("--report", choices=tuple(sorted(REPORT_SECTIONS)), default="summary")
    parser.add_argument("--resolve", help="Resolve a vague file phrase, e.g. 'that new file'.")
    parser.add_argument("--query-id", help="Optional deterministic query id for --resolve.")
    parser.add_argument("--format", choices=("operator", "json"), default="operator")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    if args.resolve:
        result = resolve_recent_file_reference(
            query_text=args.resolve,
            db_path=args.db,
            run_id=args.run_id,
            query_id=args.query_id,
        )
        if args.format == "json":
            print(stable_json(result.__dict__), end="")
        else:
            print(format_resolution_result(result))
        return 0

    payload = build_recent_file_context_report(
        db_path=args.db,
        report=args.report,
        run_id=args.run_id,
    )
    if args.format == "json":
        print(stable_json(payload), end="")
    else:
        print(format_recent_file_context_report(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
