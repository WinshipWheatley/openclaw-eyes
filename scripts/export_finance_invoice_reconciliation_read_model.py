#!/usr/bin/env python3
"""Export Finance Invoice Helper Reconciliation generated read-model files."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from business_ops_ledger import DEFAULT_DB_PATH
from finance_invoice_reconciliation import export_finance_invoice_reconciliation_read_model, stable_json


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export Finance Invoice Helper Reconciliation read-model.")
    parser.add_argument("--db", default=DEFAULT_DB_PATH, help="SQLite ledger path.")
    parser.add_argument("--export-root", default="generated/read_models", help="Read-model export root.")
    parser.add_argument("--format", choices=("operator", "json"), default="operator")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    summary = export_finance_invoice_reconciliation_read_model(db_path=args.db, export_root=args.export_root)
    if args.format == "json":
        print(stable_json(summary), end="")
    else:
        print("Finance Invoice Helper Reconciliation Read-Model Export v0")
        print("")
        print(f"JSON: `{summary['json_path']}`")
        print(f"Operator: `{summary['operator_path']}`")
        print(f"Finance candidates: {summary['finance_candidate_count']}")
        print(f"High risk: {summary['high_risk_count']}")
        print(f"Workflow proposal: `{summary['workflow_proposal_id']}`")
        print("")
        print("Boundary:")
        print("- Export writes generated read-model files only; no finance action, send, bank access, or truth claim is performed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
