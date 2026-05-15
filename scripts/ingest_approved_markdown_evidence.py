#!/usr/bin/env python3
"""Ingest bounded evidence from approved Markdown docs."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from business_ops_ledger import DEFAULT_DB_PATH
from markdown_evidence_ingestion import (
    format_markdown_evidence_report,
    ingest_approved_markdown_evidence,
    query_markdown_evidence,
    stable_json,
)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ingest approved Markdown evidence v0.")
    parser.add_argument("--db", default=DEFAULT_DB_PATH, help="SQLite ledger path.")
    parser.add_argument("--repo-root", default=str(ROOT), help="Repository root.")
    parser.add_argument("--run-id", help="Optional deterministic run id.")
    parser.add_argument("--format", choices=("operator", "json"), default="operator")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    result = ingest_approved_markdown_evidence(
        db_path=args.db,
        repo_root=args.repo_root,
        run_id=args.run_id,
    )
    payload = query_markdown_evidence(db_path=args.db, run_id=result.run_id, report="summary")
    if args.format == "json":
        print(stable_json(payload), end="")
    else:
        print(format_markdown_evidence_report(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
