from __future__ import annotations

import json
from pathlib import Path

from scripts.apply_w0_lamd_registry_truth import apply_batch


def test_batch_requires_confirm_and_then_applies_additive_receipted_truth(tmp_path: Path) -> None:
    contacts = tmp_path / "contacts.sqlite3"
    paid = tmp_path / "paid-through.sqlite"
    receipt = tmp_path / "receipt.json"

    preview = apply_batch(
        contacts_db=contacts,
        paid_through_store=paid,
        receipt_path=receipt,
        confirm=False,
        recorded_at="2026-07-17T16:20:00+00:00",
    )
    assert preview["status"] == "operator_confirmation_required"
    assert not contacts.exists()
    assert not paid.exists()
    assert not receipt.exists()

    applied = apply_batch(
        contacts_db=contacts,
        paid_through_store=paid,
        receipt_path=receipt,
        confirm=True,
        recorded_at="2026-07-17T16:20:00+00:00",
    )
    replay = apply_batch(
        contacts_db=contacts,
        paid_through_store=paid,
        receipt_path=receipt,
        confirm=True,
        recorded_at="2026-07-17T16:20:00+00:00",
    )

    assert applied["status"] == "APPLIED"
    assert applied["contact"]["email"] == "Accountant@liveartsmd.org"
    assert applied["paid_through"] == "2026-06-30"
    assert applied["next_expected_invoice"] == "2026-07-16"
    assert all(value is False for value in applied["authority_boundary"].values())
    assert replay["receipt_id"] == applied["receipt_id"]
    assert json.loads(receipt.read_text(encoding="utf-8"))["receipt_id"] == applied["receipt_id"]
