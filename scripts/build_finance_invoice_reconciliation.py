#!/usr/bin/env python3
"""Build Finance Invoice Helper Reconciliation v0 metadata."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from business_ops_ledger import DEFAULT_DB_PATH
from finance_invoice_reconciliation import (
    DEFAULT_REPO_B_ROOT,
    build_finance_invoice_reconciliation,
    format_finance_invoice_reconciliation_result,
    stable_json,
)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build Finance Invoice Helper Reconciliation v0.")
    parser.add_argument("--db", default=DEFAULT_DB_PATH, help="SQLite ledger path.")
    parser.add_argument("--repo-root", default=DEFAULT_REPO_B_ROOT.as_posix(), help="Quarantined Repo B path.")
    parser.add_argument("--run-id", help="Optional deterministic run id.")
    parser.add_argument(
        "--allow-unknown-remote",
        action="store_true",
        help="Allow non-git test fixtures or unknown remote metadata.",
    )
    parser.add_argument(
        "--no-work-board",
        action="store_true",
        help="Skip metadata-only Work Board card projection.",
    )
    parser.add_argument("--format", choices=("operator", "json"), default="operator")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    result = build_finance_invoice_reconciliation(
        db_path=args.db,
        repo_root=args.repo_root,
        run_id=args.run_id,
        require_expected_remote=not args.allow_unknown_remote,
        create_work_board_cards=not args.no_work_board,
    )
    if args.format == "json":
        print(stable_json(result.__dict__), end="")
    else:
        print(format_finance_invoice_reconciliation_result(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
