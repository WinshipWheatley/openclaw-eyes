#!/usr/bin/env python3
"""Ingest Mac finance spreadsheet metadata for the Capital Hilton packet."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from business_ops_ledger import DEFAULT_DB_PATH
from capital_hilton_finance_fact_intake import (
    DEFAULT_METADATA_PATH,
    SELECTED_SPREADSHEET,
    format_capital_hilton_fact_intake_result,
    ingest_finance_spreadsheet_metadata,
)
from finance_invoice_evidence_packet import stable_json


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ingest Capital Hilton spreadsheet metadata JSON.")
    parser.add_argument("--db", default=DEFAULT_DB_PATH, help="SQLite ledger path.")
    parser.add_argument("--metadata-path", default=str(DEFAULT_METADATA_PATH), help="Mac metadata JSON packet path.")
    parser.add_argument("--selected-candidate", default=SELECTED_SPREADSHEET, help="Selected spreadsheet filename.")
    parser.add_argument("--run-id", help="Optional deterministic run id.")
    parser.add_argument("--no-artifacts", action="store_true", help="Skip generated packet artifact refresh.")
    parser.add_argument("--no-export", action="store_true", help="Skip read-model export.")
    parser.add_argument("--read-model-export-root", default="generated/read_models", help="Generated read-model export root.")
    parser.add_argument("--format", choices=("operator", "json"), default="operator")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    result = ingest_finance_spreadsheet_metadata(
        db_path=args.db,
        metadata_path=args.metadata_path,
        selected_filename=args.selected_candidate,
        run_id=args.run_id,
        update_artifacts=not args.no_artifacts,
        export_read_model=not args.no_export,
        read_model_export_root=args.read_model_export_root,
    )
    if args.format == "json":
        print(stable_json(result.__dict__), end="")
    else:
        print(format_capital_hilton_fact_intake_result(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
