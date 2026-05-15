#!/usr/bin/env python3
"""Ingest governed Capital Hilton invoice facts and contact candidates."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from business_ops_ledger import DEFAULT_DB_PATH
from capital_hilton_finance_fact_intake import (
    SELECTED_SPREADSHEET,
    build_capital_hilton_fact_intake_report,
    format_capital_hilton_fact_intake_report,
    format_capital_hilton_fact_intake_result,
    ingest_capital_hilton_invoice_facts,
    seed_capital_hilton_contact_candidates,
)
from finance_invoice_evidence_packet import stable_json


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ingest Capital Hilton invoice facts into governed packet storage.")
    parser.add_argument("--db", default=DEFAULT_DB_PATH, help="SQLite ledger path.")
    parser.add_argument("--run-id", help="Optional deterministic run id.")
    parser.add_argument("--spreadsheet-selection", help="Selected spreadsheet filename.")
    parser.add_argument("--tonight-gig-date", help="Operator-confirmed tonight gig date.")
    parser.add_argument("--last-friday-gig-date", help="Operator-confirmed last Friday gig date.")
    parser.add_argument("--rate-or-amount-per-gig", help="Operator-supplied rate or amount per gig.")
    parser.add_argument("--invoice-count-preference", help="Operator preference: one invoice or two.")
    parser.add_argument("--po-numbers", help="Operator-supplied PO number(s), or explicit none.")
    parser.add_argument("--billing-remit-details", help="Operator-confirmed billing/remit details.")
    parser.add_argument("--recipient-decision", help="Operator-confirmed To/CC decision.")
    parser.add_argument("--supplier-portal-reference", help="Operator-supplied supplier portal reference.")
    parser.add_argument("--invoice-attachment-output-path", help="Operator-approved invoice output/attachment path.")
    parser.add_argument("--send-to-annette", action="store_true", help="Record Annette as requested To candidate, pending email review.")
    parser.add_argument("--cc-chyna", action="store_true", help="Record Chyna as requested CC candidate, pending review.")
    parser.add_argument("--cc-lawrence", action="store_true", help="Record Lawrence/Will as requested CC candidate, pending review.")
    parser.add_argument("--source-kind", default="operator_prompt", choices=("operator_prompt", "manual_cli", "telegram_cassandra", "cassandra_governed_intake"))
    parser.add_argument("--source-text", help="Bounded operator text/excerpt to store through governed Telegram intake if source kind is telegram/cassandra.")
    parser.add_argument("--no-seed-contacts", action="store_true", help="Do not seed Capital Hilton contact candidates.")
    parser.add_argument("--contacts-only", action="store_true", help="Seed contact candidates without fact updates.")
    parser.add_argument("--no-artifacts", action="store_true", help="Skip generated packet artifact refresh.")
    parser.add_argument("--no-export", action="store_true", help="Skip read-model export.")
    parser.add_argument("--read-model-export-root", default="generated/read_models", help="Generated read-model export root.")
    parser.add_argument("--report", action="store_true", help="Print report instead of result summary.")
    parser.add_argument("--format", choices=("operator", "json"), default="operator")
    return parser.parse_args(argv)


def _facts_from_args(args: argparse.Namespace) -> dict[str, str | bool | None]:
    facts: dict[str, str | bool | None] = {
        "spreadsheet_selection": args.spreadsheet_selection,
        "tonight_gig_date": args.tonight_gig_date,
        "last_friday_gig_date": args.last_friday_gig_date,
        "rate_or_amount_per_gig": args.rate_or_amount_per_gig,
        "invoice_count_preference": args.invoice_count_preference,
        "po_numbers": args.po_numbers,
        "billing_remit_details": args.billing_remit_details,
        "recipient_decision": args.recipient_decision,
        "supplier_portal_reference": args.supplier_portal_reference,
        "invoice_attachment_output_path": args.invoice_attachment_output_path,
        "send_to_annette": args.send_to_annette,
        "cc_chyna": args.cc_chyna,
        "cc_lawrence": args.cc_lawrence,
    }
    return facts


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    if args.contacts_only:
        result = seed_capital_hilton_contact_candidates(
            db_path=args.db,
            run_id=args.run_id,
            update_artifacts=not args.no_artifacts,
            export_read_model=not args.no_export,
            read_model_export_root=args.read_model_export_root,
        )
    else:
        facts = _facts_from_args(args)
        if not any(value for value in facts.values()):
            facts["spreadsheet_selection"] = SELECTED_SPREADSHEET
        result = ingest_capital_hilton_invoice_facts(
            db_path=args.db,
            facts=facts,
            source_kind=args.source_kind,
            source_text=args.source_text,
            run_id=args.run_id,
            seed_contacts=not args.no_seed_contacts,
            update_artifacts=not args.no_artifacts,
            export_read_model=not args.no_export,
            read_model_export_root=args.read_model_export_root,
        )
    if args.report:
        payload = build_capital_hilton_fact_intake_report(db_path=args.db)
        if args.format == "json":
            print(stable_json(payload), end="")
        else:
            print(format_capital_hilton_fact_intake_report(payload))
    elif args.format == "json":
        print(stable_json(result.__dict__), end="")
    else:
        print(format_capital_hilton_fact_intake_result(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
