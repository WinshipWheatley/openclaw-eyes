#!/usr/bin/env python3
"""Land the Reynolds gig artifact through the safe gig-intake ledger path.

This script is local-only. It does not send email, generate an invoice, call
external APIs, or register executors. It records the candidate gig and pending
approval packets in the business ops ledger if they are not already present.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from business_ops_ledger import DEFAULT_DB_PATH, init_business_ops_ledger
from gig_intake import (
    booking_text_from_fixture,
    confirm_gig_intake_slots,
    emit_gig_handoff_packets,
    start_gig_intake_session,
)


DEFAULT_FIXTURE = Path("/mnt/e/openclaw/orchestration/artifacts/reynolds/gig_facts.json")
DEFAULT_SOURCE_COMMIT = "orchestration_reynolds_gig_facts_2026-06-13"


def _load_fixture(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _existing_reynolds_counts(db_path: str | Path) -> dict[str, int]:
    path = str(db_path)
    init_business_ops_ledger(path)
    with sqlite3.connect(path) as conn:
        return {
            "events": conn.execute(
                "SELECT COUNT(*) FROM events "
                "WHERE event_type = 'gig_intake_recorded' "
                "AND operator_visible_summary LIKE '%Reynolds Tavern%'"
            ).fetchone()[0],
            "packets": conn.execute(
                "SELECT COUNT(*) FROM packets "
                "WHERE request_category IN ('candidate_gig_record', 'action_proposal') "
                "AND packet_json_safe LIKE '%Reynolds Tavern%'"
            ).fetchone()[0],
            "canonical_facts": conn.execute(
                "SELECT COUNT(*) FROM canonical_facts "
                "WHERE doc_category = 'gig_intake' "
                "AND fact_text LIKE '%Reynolds Tavern%'"
            ).fetchone()[0],
        }


def land_reynolds_gig(
    *,
    fixture_path: Path = DEFAULT_FIXTURE,
    db_path: str | Path = DEFAULT_DB_PATH,
    source_commit: str = DEFAULT_SOURCE_COMMIT,
) -> dict[str, Any]:
    fixture = _load_fixture(fixture_path)
    before = _existing_reynolds_counts(db_path)
    if before["events"] and before["packets"] and before["canonical_facts"]:
        return {
            "status": "already_recorded",
            "db_path": str(db_path),
            "fixture_path": str(fixture_path),
            "before_counts": before,
            "after_counts": before,
            "email_send_performed": False,
            "invoice_send_performed": False,
            "external_send_performed": False,
        }

    state = start_gig_intake_session(
        booking_text_from_fixture(fixture),
        fixture=fixture,
        persist_session=False,
    )
    confirmed = confirm_gig_intake_slots(
        state,
        invoice_business_identity="Winship Wheatley",
        payment_terms="due upon receipt",
    )
    handoff = emit_gig_handoff_packets(
        confirmed,
        db_path=db_path,
        source_channel="pc16_reynolds_canonical_landing",
        source_file=str(fixture_path),
        source_commit=source_commit,
        source_description=str(fixture.get("source") or "Reynolds gig facts artifact"),
    )
    after = _existing_reynolds_counts(db_path)
    return {
        "status": "recorded" if handoff["ledger_record"]["recorded"] else "record_attempted",
        "db_path": str(db_path),
        "fixture_path": str(fixture_path),
        "before_counts": before,
        "after_counts": after,
        "ledger_record": handoff["ledger_record"],
        "deliverable_packet_ids": [
            packet["packet_id"] for packet in handoff["deliverable_packets"] if packet.get("packet_id")
        ],
        "email_send_performed": False,
        "invoice_send_performed": False,
        "external_send_performed": False,
        "no_executor_registered": True,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Land Reynolds gig facts through the safe gig-intake path.")
    parser.add_argument("--fixture", default=str(DEFAULT_FIXTURE))
    parser.add_argument("--db", default=DEFAULT_DB_PATH)
    parser.add_argument("--source-commit", default=DEFAULT_SOURCE_COMMIT)
    args = parser.parse_args(argv)
    result = land_reynolds_gig(
        fixture_path=Path(args.fixture),
        db_path=args.db,
        source_commit=args.source_commit,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
