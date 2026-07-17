#!/usr/bin/env python3
"""Apply the operator-confirmed W0 Live Arts registry/contact truth batch."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Sequence


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from contacts_registry import (  # noqa: E402
    DEFAULT_CONTACTS_DB_PATH,
    DEFAULT_CONTACT_SEEDS,
    ContactsRegistry,
)
from invoice_cockpit_client_registry import DEFAULT_CLARA_INVOICE_CLIENT_REGISTRY  # noqa: E402
from receivable_temporal_scoping import ClientPaidThroughStore  # noqa: E402
from temporal_recurrence_registry import ClientRecurrenceRegistry  # noqa: E402


SCHEMA_VERSION = "w0_lamd_registry_truth_batch_v1"
SOURCE_REF = "Operator/to-codex/OPERATOR-DECISIONS-ALL-3-YES-PLUS-LAMD-FACTS-20260717.md"
DEFAULT_PAID_THROUGH_STORE = ROOT / "generated/system_knowledge/client_paid_through.sqlite"
DEFAULT_RECEIPT_PATH = ROOT / "generated/system_knowledge/w0_lamd_registry_truth_receipt.json"
PAID_THROUGH = date(2026, 6, 30)


def _stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def _accountant_seed():
    return next(seed for seed in DEFAULT_CONTACT_SEEDS if seed.id == "live-arts-md-accountant")


def apply_batch(
    *,
    contacts_db: str | Path = DEFAULT_CONTACTS_DB_PATH,
    paid_through_store: str | Path = DEFAULT_PAID_THROUGH_STORE,
    receipt_path: str | Path = DEFAULT_RECEIPT_PATH,
    confirm: bool = False,
    recorded_at: str | None = None,
) -> dict[str, Any]:
    recorded_at = recorded_at or datetime.now(timezone.utc).isoformat(timespec="seconds")
    client = DEFAULT_CLARA_INVOICE_CLIENT_REGISTRY["live_arts_md"]
    recurrence = ClientRecurrenceRegistry().get("live_arts_md")
    preview = {
        "schema_version": SCHEMA_VERSION,
        "status": "operator_confirmation_required" if not confirm else "applying",
        "recorded_at": recorded_at,
        "source_ref": SOURCE_REF,
        "client_ref": "live_arts_md",
        "registry_update": {
            "send_state": client.get("send_state"),
            "canonical_recipient": client.get("canonical_recipient"),
            "within_days": client.get("within_days"),
            "paid_through_period": client.get("paid_through_period"),
            "numbering_collision_requires_reconciliation": client.get("numbering_collision_requires_reconciliation"),
        },
        "recurrence_update": {
            "cadence": recurrence.cadence if recurrence else None,
            "day_of_month": recurrence.day_of_month if recurrence else None,
        },
        "contacts_db": str(contacts_db),
        "paid_through_store": str(paid_through_store),
        "receipt_path": str(receipt_path),
        "authority_boundary": {
            "email_send_performed": False,
            "gmail_draft_created": False,
            "money_moved": False,
            "workbook_mutated": False,
            "invoice_number_allocated": False,
            "payment_state_mutated": False,
            "delete_performed": False,
        },
    }
    if not confirm:
        preview["operator_command"] = (
            f"{sys.executable} {Path(__file__)} --confirm --contacts-db {contacts_db} "
            f"--paid-through-store {paid_through_store} --receipt-path {receipt_path}"
        )
        return preview

    if client.get("send_state") != "SEND_REQUIRES_GUARDIAN":
        raise RuntimeError("Live Arts registry is not at SEND_REQUIRES_GUARDIAN")
    if recurrence is None or recurrence.cadence != "monthly" or recurrence.day_of_month != 16:
        raise RuntimeError("Live Arts recurrence does not match the operator-confirmed monthly rule")

    contacts = ContactsRegistry(str(contacts_db), seed=False)
    contacts.upsert_contact_additive(_accountant_seed())
    accountant = contacts.get_contact("Accountant@liveartsmd.org")
    if accountant is None or accountant.get("email") != "Accountant@liveartsmd.org":
        raise RuntimeError("operator-confirmed Live Arts accountant contact did not persist")

    paid_store = ClientPaidThroughStore(paid_through_store)
    observed_paid_through = paid_store.set_paid_through(
        "live_arts_md",
        PAID_THROUGH,
        source_ref=SOURCE_REF,
    )
    if observed_paid_through != PAID_THROUGH:
        raise RuntimeError("existing paid-through state is later than operator-confirmed June truth")

    receipt = {
        **preview,
        "status": "APPLIED",
        "contact": {
            "contact_id": accountant["id"],
            "email": accountant["email"],
            "role": accountant["role"],
        },
        "paid_through": PAID_THROUGH.isoformat(),
        "next_expected_invoice": "2026-07-16",
        "idempotent_additive_upsert": True,
        "send_hold_unchanged": True,
    }
    receipt_id = "w0-lamd-truth:" + hashlib.sha256(_stable_json(receipt).encode("utf-8")).hexdigest()[:20]
    receipt["receipt_id"] = receipt_id
    target = Path(receipt_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(_stable_json(receipt), encoding="utf-8")
    return receipt


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--confirm", action="store_true")
    parser.add_argument("--contacts-db", default=DEFAULT_CONTACTS_DB_PATH)
    parser.add_argument("--paid-through-store", default=str(DEFAULT_PAID_THROUGH_STORE))
    parser.add_argument("--receipt-path", default=str(DEFAULT_RECEIPT_PATH))
    parser.add_argument("--recorded-at")
    args = parser.parse_args(argv)
    result = apply_batch(
        contacts_db=args.contacts_db,
        paid_through_store=args.paid_through_store,
        receipt_path=args.receipt_path,
        confirm=args.confirm,
        recorded_at=args.recorded_at,
    )
    print(_stable_json(result), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
