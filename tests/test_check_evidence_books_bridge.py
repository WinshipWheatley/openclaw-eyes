from __future__ import annotations

from pathlib import Path

from ar_expected_receivable_record import ExpectedReceivableRecord
from ar_gig_to_cash_store import GigToCashStore
import check_evidence_books_bridge as bridge


def test_reynolds_check_matches_receivable_and_confirm_deposit_is_idempotent(tmp_path: Path) -> None:
    db_path = tmp_path / "gig_to_cash.sqlite3"
    seed = bridge.seed_reynolds_receivable(
        db_path=db_path,
        amount_minor_units=50000,
        gig_date_iso="2026-06-27",
        due_date_iso="2026-06-27",
    )
    evidence = {
        "artifact_ref": "artifact:check_1",
        "claimed_client_ref": "reynolds_tavern",
        "operator_note": "Reynolds Tavern check for $500.00 invoice RT-2026-06-27",
        "amount_minor_units": 50000,
        "currency_iso": "USD",
    }

    match = bridge.match_check_to_receivable(evidence, db_path=db_path)

    assert match["amount_matches"] is True
    assert match["receivable_id"] == seed["receivable_id"]
    assert match["gig_id"] == seed["gig_id"]
    assert match["expected_minor_units"] == 50000
    assert "Did you deposit it?" in bridge.build_deposit_question_card(match)["summary"]

    logged: list[dict] = []
    duplicate_amounts: list[float] = []

    def _duplicate(amount: float):
        duplicate_amounts.append(amount)
        return logged[0] if logged else None

    def _log(**kwargs):
        entry = {"id": "INC-test", **kwargs}
        logged.append(entry)
        return entry

    result1 = bridge.confirm_deposit(
        match,
        db_path=db_path,
        artifact_ref="artifact:check_1",
        duplicate_fn=_duplicate,
        log_fn=_log,
    )
    result2 = bridge.confirm_deposit(
        match,
        db_path=db_path,
        artifact_ref="artifact:check_1",
        duplicate_fn=_duplicate,
        log_fn=_log,
    )

    store = GigToCashStore(str(db_path)).open()
    receivable = store.get_current(ExpectedReceivableRecord, seed["receivable_id"])
    store.close()
    assert receivable.lifecycle_state == "satisfied"
    assert receivable.resolution_ref == "artifact:check_1"
    assert result1["receivable_satisfied"] is True
    assert result2["receivable_satisfied"] is False
    assert len(logged) == 1
    assert logged[0]["amount"] == 500.0
    assert logged[0]["entry_type"] == "income"
    assert logged[0]["payer"] == "reynolds_tavern"
    links = bridge.list_gig_evidence_links(db_path=db_path)
    assert links == [
        {
            "artifact_ref": "artifact:check_1",
            "gig_id": seed["gig_id"],
            "receivable_id": seed["receivable_id"],
            "vendor": "reynolds_tavern",
        }
    ]
