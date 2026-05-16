#!/usr/bin/env python3
"""Build Cassandra Runtime Wiring Audit v0."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from business_ops_ledger import DEFAULT_DB_PATH
from cassandra_runtime_wiring_audit import (
    build_cassandra_runtime_wiring_audit,
    format_cassandra_runtime_wiring_audit_result,
    stable_json,
)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build Cassandra runtime wiring audit.")
    parser.add_argument("--db", default=DEFAULT_DB_PATH)
    parser.add_argument("--repo-a-root", default=str(ROOT))
    parser.add_argument("--repo-b-root", default="/home/openclaw_external/openclaw-runtime")
    parser.add_argument("--run-id")
    parser.add_argument("--no-synthetic-proofs", action="store_true")
    parser.add_argument("--no-log-scan", action="store_true")
    parser.add_argument("--format", choices=("operator", "json"), default="operator")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    result = build_cassandra_runtime_wiring_audit(
        db_path=args.db,
        repo_a_root=args.repo_a_root,
        repo_b_root=args.repo_b_root,
        run_id=args.run_id,
        create_synthetic_proofs=not args.no_synthetic_proofs,
        scan_app_logs=not args.no_log_scan,
    )
    if args.format == "json":
        print(stable_json(result.__dict__), end="")
    else:
        print(format_cassandra_runtime_wiring_audit_result(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
