#!/usr/bin/env python3
"""Export Finance Invoice Evidence Packet generated read-model files."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from business_ops_ledger import DEFAULT_DB_PATH
from finance_invoice_evidence_packet import export_finance_invoice_evidence_packets_read_model, stable_json


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export Finance Invoice Evidence Packet read-model.")
    parser.add_argument("--db", default=DEFAULT_DB_PATH, help="SQLite ledger path.")
    parser.add_argument("--export-root", default="generated/read_models", help="Read-model export root.")
    parser.add_argument("--format", choices=("operator", "json"), default="operator")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    summary = export_finance_invoice_evidence_packets_read_model(db_path=args.db, export_root=args.export_root)
    if args.format == "json":
        print(stable_json(summary), end="")
    else:
        print("Finance Invoice Evidence Packets Read-Model Export v0")
        print("")
        print(f"JSON: `{summary['json_path']}`")
        print(f"Operator: `{summary['operator_path']}`")
        print(f"Packets: {summary['packet_count']}")
        print(f"Missing items: {summary['missing_items_count']}")
        print(f"Spreadsheet candidate known: `{str(summary['spreadsheet_candidate_known']).lower()}`")
        print(f"Spreadsheet ingestion allowed: `{str(summary['spreadsheet_ingestion_allowed']).lower()}`")
        print("")
        print("Boundary:")
        print("- Export writes generated read-model files only; no invoice/email/bank/ledger/tax action is performed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
