#!/usr/bin/env python3
"""Build Finance Invoice Evidence Packet v0 metadata."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from business_ops_ledger import DEFAULT_DB_PATH
from finance_invoice_evidence_packet import (
    WORKFLOW_KINDS,
    build_finance_invoice_evidence_packet,
    format_finance_invoice_evidence_packet_result,
    parse_amount_arg,
    parse_fact_arg,
    stable_json,
)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a Finance Invoice Evidence Packet v0.")
    parser.add_argument("--db", default=DEFAULT_DB_PATH, help="SQLite ledger path.")
    parser.add_argument("--title", required=True, help="Packet title.")
    parser.add_argument("--subject", required=True, help="Subject/entity label.")
    parser.add_argument("--workflow-kind", choices=tuple(sorted(WORKFLOW_KINDS)), default="invoice_prep")
    parser.add_argument("--packet-id", help="Optional deterministic packet id.")
    parser.add_argument("--run-id", help="Optional deterministic run id.")
    parser.add_argument("--fact", action="append", default=[], help="Operator fact as label=value. May be repeated.")
    parser.add_argument("--amount", action="append", default=[], help="Operator amount as amount=123.45 or 123.45. May be repeated.")
    parser.add_argument("--spreadsheet-filename", help="Known Mac invoice spreadsheet filename, if operator provides one.")
    parser.add_argument("--no-work-board", action="store_true", help="Skip metadata-only Work Board cards.")
    parser.add_argument("--format", choices=("operator", "json"), default="operator")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    facts = [parse_fact_arg(item) for item in args.fact]
    facts.extend(parse_amount_arg(item) for item in args.amount)
    result = build_finance_invoice_evidence_packet(
        db_path=args.db,
        title=args.title,
        subject=args.subject,
        workflow_kind=args.workflow_kind,
        facts=facts,
        packet_id=args.packet_id,
        run_id=args.run_id,
        spreadsheet_filename=args.spreadsheet_filename,
        create_work_board_cards=not args.no_work_board,
    )
    if args.format == "json":
        print(stable_json(result.__dict__), end="")
    else:
        print(format_finance_invoice_evidence_packet_result(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
