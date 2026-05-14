#!/usr/bin/env python3
"""Import Operator Action Inbox v0 request files."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from business_ops_ledger import DEFAULT_DB_PATH
from operator_action_inbox import (
    DEFAULT_OPERATOR_ACTION_INBOX,
    format_inbox_import_summary,
    import_operator_action_requests,
    stable_json,
)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Import shared-drop operator action request JSON files."
    )
    parser.add_argument("--db", default=DEFAULT_DB_PATH, help="SQLite ledger path.")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--file", help="Specific request JSON file to import.")
    group.add_argument(
        "--inbox",
        default=DEFAULT_OPERATOR_ACTION_INBOX.as_posix(),
        help="Inbox folder to scan for request JSON files.",
    )
    parser.add_argument("--import-run-id", help="Optional import run id.")
    parser.add_argument(
        "--format",
        choices=("operator", "json"),
        default="operator",
        help="Output format.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    summary = import_operator_action_requests(
        file_path=args.file,
        inbox=args.inbox,
        db_path=args.db,
        import_run_id=args.import_run_id,
    )
    payload = {
        "import_run_id": summary.import_run_id,
        "imported_request_count": summary.imported_request_count,
        "rejected_request_count": summary.rejected_request_count,
        "action_ids": list(summary.action_ids),
        "rejected_files": list(summary.rejected_files),
        "items": [item.__dict__ for item in summary.items],
        "no_execution_occurred": summary.no_execution_occurred,
        "approval_still_required": summary.approval_still_required,
    }
    if args.format == "json":
        print(stable_json(payload), end="")
    else:
        print(format_inbox_import_summary(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
