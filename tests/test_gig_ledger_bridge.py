from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import gig_ledger_bridge as bridge
import receivables_month_bounded
from ar_expected_receivable_record import ExpectedReceivableRecord
from ar_gig_record import GigRecord
from ar_gig_to_cash_store import GigToCashStore
from ar_invoice_record import InvoiceRecord

NOW = datetime(2026, 9, 2, 12, 0, tzinfo=timezone.utc)
SENTENCE = "Dane asked me to play Oct 17 at 49 West for $500"


class FakeRegistry:
    def __init__(self, contacts: dict[str, dict] | None = None) -> None:
        self.contacts = contacts or {}

    def get_contact(self, query: str):
        return self.contacts.get(query.strip().lower())


def _hilton_registry() -> FakeRegistry:
    return FakeRegistry({"annette": {"id": "annette-sunga", "name": "Annette Sunga", "connected_client": ("capital-hilton",)}})


def _count(db: Path) -> dict[str, int]:
    with GigToCashStore(str(db)) as store:
        return {
            "gig": store.get_current(GigRecord, "gig:land:" + _landing(db)) is not None and 1 or 0,
        }


def _landing(db: Path) -> str:
    return (db.parent / "landing").read_text()


def test_interpret_reads_who_what_where_when_and_how_much() -> None:
    intent = bridge.interpret_gig_text(SENTENCE)
    assert intent.contact_hint == "Dane"
    assert intent.description == "play"
    assert intent.venue == "49 West"
    assert intent.date_text == "Oct 17"
    assert intent.amount_minor_units == 50000


def test_capture_phrase_shape_still_reads() -> None:
    intent = bridge.interpret_gig_text("Annette asked me to do a solo piano set on Sept 12 for $400")
    assert intent.contact_hint == "Annette"
    assert intent.description == "do a solo piano set"
    assert intent.venue == ""
    assert intent.date_text == "Sept 12"
    assert intent.amount_minor_units == 40000


def test_unknown_contact_fails_closed_and_writes_nothing(tmp_path: Path) -> None:
    db = tmp_path / "g2c.sqlite3"
    result = bridge.land_gig(SENTENCE, db_path=db, apply=True, now=NOW, registry=FakeRegistry())
    assert result["status"] == "needs_client"
    assert result["suggested_client_ref"] == "49_west"
    assert "--client 49_west" in result["hint"]
    assert result["machine_proof"]["ledger_fact_write_performed"] is False
    assert not db.exists()


def test_dry_run_plans_three_records_and_writes_nothing(tmp_path: Path) -> None:
    db = tmp_path / "g2c.sqlite3"
    result = bridge.land_gig(SENTENCE, db_path=db, now=NOW, registry=FakeRegistry(), client_ref="49_west", client_name="49 West")
    assert result["status"] == "dry_run"
    assert result["resolved"]["service_date"] == "2026-10-17"
    assert result["resolved"]["due_date"] == "2026-10-17"
    assert result["money_source_month"] == "2026-10"
    records = result["records"]
    assert records["gig"]["lifecycle_state"] == "active"
    assert records["invoice"]["lifecycle_state"] == "draft"
    assert records["receivable"]["lifecycle_state"] == "open"
    assert records["receivable"]["expected_minor_units"] == 50000
    assert records["receivable"]["invoice_version_id"] == records["invoice"]["invoice_version_id"]
    assert not db.exists()
    assert result["authority_boundary"]["money_movement_performed"] is False


def test_apply_lands_once_and_repeats_are_no_ops(tmp_path: Path) -> None:
    db = tmp_path / "g2c.sqlite3"
    first = bridge.land_gig(SENTENCE, db_path=db, apply=True, now=NOW, registry=FakeRegistry(), client_ref="49_west", client_name="49 West")
    assert first["status"] == "landed"
    assert first["machine_proof"]["records_created"] == ["gig", "invoice", "receivable"]
    second = bridge.land_gig(SENTENCE, db_path=db, apply=True, now=NOW, registry=FakeRegistry(), client_ref="49_west", client_name="49 West")
    assert second["status"] == "already_landed"
    assert second["machine_proof"]["ledger_fact_write_performed"] is False
    with GigToCashStore(str(db)) as store:
        gig = store.get_current(GigRecord, first["records"]["gig"]["gig_id"])
        invoice = store.get_current(InvoiceRecord, first["records"]["invoice"]["invoice_id"])
        receivable = store.get_current(ExpectedReceivableRecord, first["records"]["receivable"]["receivable_id"])
    assert gig.counterparty_name == "49 West"
    assert invoice.total_minor_units == 50000
    assert receivable.due_date_iso == "2026-10-17"
    assert len(receivables_month_bounded._iter_current_receivables(db)) == 1


def test_known_contact_uses_default_rate_and_terms(tmp_path: Path) -> None:
    db = tmp_path / "g2c.sqlite3"
    result = bridge.land_gig(
        "Annette asked me to do a solo piano set on Sept 12",
        db_path=db, now=NOW, registry=_hilton_registry(), terms_days=30,
    )
    assert result["status"] == "dry_run"
    assert result["resolved"]["client_ref"] == "capital_hilton"
    assert result["resolved"]["client_display_name"] == "Capital Hilton"
    assert result["resolved"]["amount_minor_units"] == 40000
    assert result["resolved"]["service_date"] == "2026-09-12"
    assert result["resolved"]["due_date"] == "2026-10-12"


def test_landed_row_reaches_the_one_money_source(tmp_path: Path) -> None:
    db = tmp_path / "g2c.sqlite3"
    bridge.land_gig(SENTENCE, db_path=db, apply=True, now=NOW, registry=FakeRegistry(), client_ref="49_west", client_name="49 West")
    facts = tmp_path / "facts.json"
    facts.write_text("[]", encoding="utf-8")
    payload = receivables_month_bounded.build_receivables_month_bounded(
        g2c_db_path=db, facts_path=facts, generated_at="2026-09-02T12:00:00+00:00",
        recurrence_rule_db_path=tmp_path / "no_rules.sqlite3",
    )
    rows = [row for row in payload["rows"] if row["client_ref"] == "49_west"]
    assert len(rows) == 1
    assert rows[0]["month"] == "2026-10"
    assert rows[0]["open_minor_units"] == 50000
    assert rows[0]["payment_status"] == "open_not_paid"


def test_operator_markdown_and_json_are_boundary_honest(tmp_path: Path) -> None:
    result = bridge.land_gig(SENTENCE, db_path=tmp_path / "g2c.sqlite3", now=NOW, registry=FakeRegistry(), client_ref="49_west", client_name="49 West")
    text = bridge.format_operator_markdown(result)
    assert "49 West: play at 49 West on 2026-10-17 for $500, due 2026-10-17." in text
    assert "Dry run: nothing written" in text
    assert "no money moved" in text
    json.loads(bridge.stable_json(result))


def test_contact_resolution_with_a_different_venue_is_flagged_not_hidden(tmp_path: Path) -> None:
    registry = FakeRegistry({"dane": {"id": "dane", "name": "Dane", "connected_client": ("live-arts-md",)}})
    result = bridge.land_gig(SENTENCE, db_path=tmp_path / "g2c.sqlite3", now=NOW, registry=registry)
    assert result["status"] == "dry_run"
    assert result["resolved"]["client_ref"] == "live_arts_md"
    assert result["resolved"]["resolution"] == "contact"
    assert "--client 49_west" in result["resolved"]["venue_note"]
    text = bridge.format_operator_markdown(result)
    assert "Client via: `contact`" in text
    assert "Check: Client came from contact 'Dane' (Live Arts MD)" in text
