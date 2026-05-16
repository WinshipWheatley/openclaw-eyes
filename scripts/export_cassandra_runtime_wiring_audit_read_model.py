#!/usr/bin/env python3
"""Export Cassandra Runtime Wiring Audit v0 read-model."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from business_ops_ledger import DEFAULT_DB_PATH
from cassandra_runtime_wiring_audit import (
    export_cassandra_runtime_wiring_audit_read_model,
    stable_json,
)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export Cassandra runtime wiring audit read-model.")
    parser.add_argument("--db", default=DEFAULT_DB_PATH)
    parser.add_argument("--export-root", default="generated/read_models")
    parser.add_argument("--format", choices=("operator", "json"), default="operator")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    result = export_cassandra_runtime_wiring_audit_read_model(
        db_path=args.db,
        export_root=args.export_root,
    )
    if args.format == "json":
        print(stable_json(result), end="")
    else:
        print("Cassandra Runtime Wiring Audit Read-Model Export v0")
        print("")
        print(f"JSON: `{result['json_path']}`")
        print(f"Operator: `{result['operator_path']}`")
        print(f"Live receive proven: `{str(result['live_receive_proven']).lower()}`")
        print(f"Governed storage proven: `{str(result['governed_storage_proven']).lower()}`")
        print(f"Reply-ready: `{str(result['reply_ready']).lower()}`")
        print("")
        print("Boundary:")
        print("- Export only; no Telegram send, Repo B execution, secret read, approval bypass, arbitrary command, or external API call.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
