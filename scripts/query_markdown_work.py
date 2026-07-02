#!/usr/bin/env python3
"""Query "what work on X" from the Markdown Knowledge Atlas."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from business_ops_ledger import DEFAULT_DB_PATH
from markdown_knowledge_query import format_markdown_work_query, query_markdown_work, stable_json


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Query Markdown Atlas work topics.")
    parser.add_argument("topic", help="Topic to search for, e.g. 'runtime gate'.")
    parser.add_argument("--db", default=DEFAULT_DB_PATH, help="SQLite ledger path.")
    parser.add_argument("--run-id", help="Optional Markdown Atlas run id. Defaults to latest.")
    parser.add_argument("--limit", type=int, default=10, help="Maximum section results.")
    parser.add_argument("--format", choices=("operator", "json"), default="operator")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    payload = query_markdown_work(
        args.topic,
        db_path=args.db,
        run_id=args.run_id,
        limit=args.limit,
    )
    if args.format == "json":
        print(stable_json(payload), end="")
    else:
        print(format_markdown_work_query(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
