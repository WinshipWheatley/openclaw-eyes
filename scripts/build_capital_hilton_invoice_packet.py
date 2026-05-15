#!/usr/bin/env python3
"""Build the Capital Hilton invoice evidence packet."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from business_ops_ledger import DEFAULT_DB_PATH
from capital_hilton_invoice_packet import (
    DEFAULT_ARTIFACT_ROOT,
    build_capital_hilton_invoice_packet,
    format_capital_hilton_invoice_packet_result,
    stable_json,
)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build Capital Hilton Invoice Packet v0.")
    parser.add_argument("--db", default=DEFAULT_DB_PATH, help="SQLite ledger path.")
    parser.add_argument("--artifact-root", default=str(DEFAULT_ARTIFACT_ROOT), help="Generated artifact folder.")
    parser.add_argument("--read-model-export-root", default="generated/read_models", help="Generated read-model export folder.")
    parser.add_argument("--run-id", help="Optional deterministic run id.")
    parser.add_argument("--no-export", action="store_true", help="Skip finance evidence packet read-model export.")
    parser.add_argument("--format", choices=("operator", "json"), default="operator")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    result = build_capital_hilton_invoice_packet(
        db_path=args.db,
        artifact_root=args.artifact_root,
        run_id=args.run_id,
        export_read_model=not args.no_export,
        read_model_export_root=args.read_model_export_root,
    )
    if args.format == "json":
        print(stable_json(result.__dict__), end="")
    else:
        print(format_capital_hilton_invoice_packet_result(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
