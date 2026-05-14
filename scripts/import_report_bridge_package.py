#!/usr/bin/env python3
"""Import a local Report Bridge package."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from business_ops_ledger import DEFAULT_DB_PATH
from report_bridge import (
    DEFAULT_REPORT_BRIDGE_INBOX,
    format_import_result,
    import_report_bridge_package,
    stable_json,
)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import a local Report Bridge package.")
    parser.add_argument("--db", default=DEFAULT_DB_PATH, help="SQLite ledger path.")
    parser.add_argument("--package", help="Package folder containing report_bridge_manifest.json.")
    parser.add_argument(
        "--inbox",
        default=DEFAULT_REPORT_BRIDGE_INBOX.as_posix(),
        help="Inbox to search when --package is omitted.",
    )
    parser.add_argument("--run-id", help="Optional deterministic import run id.")
    parser.add_argument(
        "--format",
        choices=("operator", "json"),
        default="operator",
        help="Output format.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    result = import_report_bridge_package(
        package=args.package,
        inbox=args.inbox,
        db_path=args.db,
        run_id=args.run_id,
    )
    payload = {
        "run_id": result.run_id,
        "db_path": result.db_path,
        "package_id": result.package_id,
        "package_path": result.package_path,
        "node_id": result.node_id,
        "node_kind": result.node_kind,
        "project_id": result.project_id,
        "client_id": result.client_id,
        "file_count": result.file_count,
        "imported_file_count": result.imported_file_count,
        "rejected_file_count": result.rejected_file_count,
        "status": result.status,
        "raw_body_included": result.raw_body_included,
        "client_data_included": result.client_data_included,
        "truth_promotion_allowed": result.truth_promotion_allowed,
        "runtime_authority": False,
        "deployment_authority": False,
        "remote_management_allowed": False,
        "agent_activation_allowed": False,
        "tool_execution_allowed": False,
        "model_execution_allowed": False,
        "container_execution_allowed": False,
        "network_authority": False,
    }
    if args.format == "json":
        print(stable_json(payload), end="")
    else:
        print(format_import_result(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
