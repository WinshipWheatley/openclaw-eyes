from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

from ar_expected_receivable_record import create_expected_receivable
from ar_gig_to_cash_store import GigToCashStore
from ar_invoice_record import create_invoice_record


FIXED_GENERATED_AT = "2026-07-07T10:00:00+00:00"


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _append_receivable(
    db_path: Path,
    *,
    client_ref: str,
    month: str,
    amount_minor_units: int,
    lifecycle_state: str = "open",
) -> None:
    with GigToCashStore(str(db_path)) as store:
        invoice = create_invoice_record(
            invoice_id=f"inv:{client_ref}:{month}",
            counterparty_ref=client_ref,
            billing_entity_ref="winship_live",
            lifecycle_state="issued",
            invoice_number=f"{client_ref.upper()}-{month}",
            issue_date_iso=f"{month}-01",
            due_date_iso=f"{month}-15",
            currency_iso="USD",
            total_minor_units=amount_minor_units,
            idempotency_key=f"invoice:{client_ref}:{month}",
            source_ref=f"test:g2c:invoice:{client_ref}:{month}",
        )
        store.append(invoice)
        store.append(
            create_expected_receivable(
                receivable_id=f"recv:{client_ref}:{month}",
                invoice_id=invoice.invoice_id,
                invoice_version_id=invoice.invoice_version_id,
                counterparty_ref=client_ref,
                expected_minor_units=amount_minor_units,
                currency_iso="USD",
                due_date_iso=f"{month}-15",
                recognized_utc_iso=f"{month}-01T00:00:00+00:00",
                idempotency_key=f"receivable:{client_ref}:{month}:{lifecycle_state}",
                source_ref=f"test:g2c:receivable:{client_ref}:{month}",
                lifecycle_state=lifecycle_state,
                resolution_ref="test:paid" if lifecycle_state == "satisfied" else None,
            )
        )


def _canonical_facts_path(tmp_path: Path) -> Path:
    path = tmp_path / "canonical_receivable_facts.json"
    _write_json(
        path,
        {
            "generated_at": FIXED_GENERATED_AT,
            "receivable_month_facts": [
                {
                    "client_ref": "live_arts_md",
                    "client_display_name": "Live Arts MD",
                    "month": "2026-06",
                    "currency_iso": "USD",
                    "invoiced_minor_units": 199500,
                    "paid_minor_units": 90000,
                    "open_minor_units": 109500,
                    "invoiced_derived": True,
                    "needs_reconcile": True,
                    "payment_status": "needs_reconcile",
                    "notes": ["$900 paid, $1,095 still open until operator reconciliation."],
                    "source_ref": "test:live-arts:1095-open-900-paid",
                },
                {
                    "client_ref": "st_annes",
                    "client_display_name": "St. Anne's",
                    "month": "2026-04",
                    "currency_iso": "USD",
                    "invoiced_minor_units": 62500,
                    "paid_minor_units": 62500,
                    "open_minor_units": 0,
                    "amount_evidence_minor_units": [62500],
                    "needs_reconcile": False,
                    "payment_status": "settled",
                    "notes": ["April share of Apr+May $1,250 paid total; do not resurface as owed."],
                    "source_ref": "test:st-annes:apr-may-paid",
                },
                {
                    "client_ref": "st_annes",
                    "client_display_name": "St. Anne's",
                    "month": "2026-05",
                    "currency_iso": "USD",
                    "invoiced_minor_units": 62500,
                    "paid_minor_units": 62500,
                    "open_minor_units": 0,
                    "amount_evidence_minor_units": [62500],
                    "needs_reconcile": False,
                    "payment_status": "settled",
                    "notes": ["May share of Apr+May $1,250 paid total; do not resurface as owed."],
                    "source_ref": "test:st-annes:apr-may-paid",
                },
                {
                    "client_ref": "capital_hilton",
                    "month": "2026-06",
                    "currency_iso": "USD",
                    "amount_known": False,
                    "needs_reconcile": True,
                    "payment_status": "open_amount_unknown",
                    "notes": ["check_unverified: check expected per operator; amount not yet evidenced."],
                    "source_ref": "test:capital-hilton:check-unverified",
                },
            ],
        },
    )
    return path


def _row(payload: dict[str, Any], client_ref: str, month: str) -> dict[str, Any]:
    matches = [
        row
        for row in payload["rows"]
        if row["client_ref"] == client_ref and row["month"] == month
    ]
    assert len(matches) == 1
    return matches[0]


def test_build_receivables_month_bounded_merges_g2c_and_canonical_facts(tmp_path: Path) -> None:
    from receivables_month_bounded import build_receivables_month_bounded

    db_path = tmp_path / "g2c.sqlite3"
    _append_receivable(
        db_path,
        client_ref="capital_hilton",
        month="2026-06",
        amount_minor_units=200000,
    )

    payload = build_receivables_month_bounded(
        g2c_db_path=db_path,
        facts_path=_canonical_facts_path(tmp_path),
        generated_at=FIXED_GENERATED_AT,
    )

    live_arts = _row(payload, "live_arts_md", "2026-06")
    assert live_arts["amount_known"] is True
    assert live_arts["invoiced_derived"] is True
    assert live_arts["invoiced_minor_units"] == 199500
    assert live_arts["paid_minor_units"] == 90000
    assert live_arts["open_minor_units"] == 109500
    assert live_arts["needs_reconcile"] is True
    assert live_arts["payment_status"] == "needs_reconcile"
    assert "1,095" in " ".join(live_arts["notes"])
    assert "900" in " ".join(live_arts["notes"])

    for month in ("2026-04", "2026-05"):
        st_annes = _row(payload, "st_annes", month)
        assert st_annes["payment_status"] == "settled"
        assert st_annes["open_minor_units"] == 0
        assert st_annes["paid_minor_units"] == st_annes["invoiced_minor_units"]
        assert st_annes["settled_past_no_compound"] is True
        assert st_annes["needs_reconcile"] is False

    capital = _row(payload, "capital_hilton", "2026-06")
    assert capital["source_kinds"] == ["canonical_business_fact", "g2c_expected_receivable"]
    assert capital["amount_known"] is True
    assert capital["invoiced_minor_units"] == 200000
    assert capital["paid_minor_units"] == 0
    assert capital["open_minor_units"] == 200000
    assert capital["payment_status"] == "open_not_paid"
    assert capital["needs_reconcile"] is True
    assert "check_unverified" in " ".join(capital["notes"])

    assert payload["summary"]["open_minor_units_by_client"]["live_arts_md"] == 109500
    assert payload["summary"]["open_minor_units_by_client"]["st_annes"] == 0
    assert payload["authority_boundary"]["ledger_mutation_performed"] is False
    assert payload["authority_boundary"]["money_movement_performed"] is False


def test_default_capital_hilton_unknown_amount_is_not_invented(tmp_path: Path) -> None:
    from receivables_month_bounded import build_receivables_month_bounded

    payload = build_receivables_month_bounded(
        g2c_db_path=tmp_path / "missing-g2c.sqlite3",
        facts_path=None,
        generated_at=FIXED_GENERATED_AT,
    )

    capital = _row(payload, "capital_hilton", "2026-06")
    assert capital["amount_known"] is False
    assert capital["payment_status"] == "open_amount_unknown"
    assert capital["open_minor_units"] is None
    assert capital["invoiced_minor_units"] is None
    assert "check expected per operator; amount not yet evidenced" in " ".join(capital["notes"])
    assert "capital_hilton:2026-06" in payload["summary"]["unknown_amount_keys"]
    assert "capital_hilton" not in payload["summary"]["open_minor_units_by_client"]


def test_default_live_arts_fact_uses_operator_graded_zero_balance(tmp_path: Path) -> None:
    from receivables_month_bounded import build_receivables_month_bounded

    payload = build_receivables_month_bounded(
        g2c_db_path=tmp_path / "missing-g2c.sqlite3",
        facts_path=None,
        generated_at="2026-07-17T22:30:00+00:00",
    )

    live_arts = _row(payload, "live_arts_md", "2026-06")
    assert live_arts["invoiced_minor_units"] == 100000
    assert live_arts["paid_minor_units"] == 100000
    assert live_arts["open_minor_units"] == 0
    assert live_arts["payment_status"] == "settled"
    assert live_arts["needs_reconcile"] is False
    assert live_arts["settled_past_no_compound"] is True
    assert live_arts["source_refs"] == [
        "operator_graded_fact:live_arts_md:2026-07-17:telegram_msg_1781:zero_current_balance"
    ]
    assert live_arts["source_kinds"] == ["operator_graded_fact"]
    assert "live_arts_md:2026-06" not in payload["summary"]["needs_reconcile_keys"]
    assert payload["summary"]["open_minor_units_by_client"]["live_arts_md"] == 0


def test_unevidenced_canonical_amount_fails_validation(tmp_path: Path) -> None:
    from receivables_month_bounded import build_receivables_month_bounded

    facts_path = tmp_path / "bad_facts.json"
    _write_json(
        facts_path,
        {
            "receivable_month_facts": [
                {
                    "client_ref": "capital_hilton",
                    "month": "2026-06",
                    "currency_iso": "USD",
                    "open_minor_units": 200000,
                    "payment_status": "open_not_paid",
                    "source_ref": "test:capital-hilton:check-unverified",
                }
            ]
        },
    )

    try:
        build_receivables_month_bounded(
            g2c_db_path=tmp_path / "missing-g2c.sqlite3",
            facts_path=facts_path,
            generated_at=FIXED_GENERATED_AT,
        )
    except ValueError as exc:
        assert "unevidenced amount" in str(exc)
        assert "open_minor_units" in str(exc)
    else:
        raise AssertionError("expected unevidenced canonical amount to fail validation")


def test_export_writes_receivables_month_bounded_to_generated_path(tmp_path: Path) -> None:
    from scripts.export_receivables_month_bounded import export_receivables_month_bounded_read_model

    db_path = tmp_path / "g2c.sqlite3"
    _append_receivable(
        db_path,
        client_ref="capital_hilton",
        month="2026-06",
        amount_minor_units=200000,
    )
    export_root = tmp_path / "generated" / "read_models"

    payload = export_receivables_month_bounded_read_model(
        g2c_db_path=db_path,
        facts_path=_canonical_facts_path(tmp_path),
        export_root=export_root,
        generated_at=FIXED_GENERATED_AT,
    )

    output_path = export_root / "receivables_month_bounded.json"
    assert output_path.exists()
    assert json.loads(output_path.read_text(encoding="utf-8")) == payload


def test_maestro_packet_uses_month_bounded_receivables_as_structured_money_fact(tmp_path: Path) -> None:
    from maestro_context_packet import build_maestro_context_packet
    from receivables_month_bounded import build_receivables_month_bounded, stable_json

    read_model_root = tmp_path / "read_models"
    _write_json(
        read_model_root / "agent_presence.json",
        {
            "generated_at": FIXED_GENERATED_AT,
            "agents": [{"agent_id": "maestro", "display_name": "Maestro", "actual_state": "online"}],
        },
    )
    _write_json(
        read_model_root / "finance_invoice_reconciliation.json",
        {
            "generated_at": FIXED_GENERATED_AT,
            "counts": {"finance_candidate_count": 1, "high_risk_count": 0},
        },
    )
    payload = build_receivables_month_bounded(
        g2c_db_path=tmp_path / "missing-g2c.sqlite3",
        facts_path=_canonical_facts_path(tmp_path),
        generated_at=FIXED_GENERATED_AT,
    )
    (read_model_root / "receivables_month_bounded.json").write_text(stable_json(payload), encoding="utf-8")

    packet = build_maestro_context_packet(
        question="What is the Live Arts invoice status for June?",
        read_model_root=read_model_root,
        require_real_truth=False,
    )

    receivable_facts = [fact for fact in packet["facts"] if fact.get("topic") == "receivable_month_bounded"]
    assert receivable_facts
    assert any(fact["client_ref"] == "live_arts_md" and fact["month"] == "2026-06" for fact in receivable_facts)
    assert all(fact["structured_fact"] is True for fact in receivable_facts)
    assert all(fact["as_of"] == FIXED_GENERATED_AT for fact in receivable_facts)
    assert not any(fact.get("topic") == "money_not_tracked" for fact in packet["facts"])
    assert "generated/read_models/receivables_month_bounded.json" in packet["source_refs"]
    assert packet["machine_proof"]["receivables_month_bounded_fact_count"] == len(receivable_facts)


def test_maestro_packet_keeps_unknown_receivable_amounts_unknown(tmp_path: Path) -> None:
    from maestro_context_packet import build_maestro_context_packet
    from receivables_month_bounded import build_receivables_month_bounded, stable_json

    read_model_root = tmp_path / "read_models"
    _write_json(
        read_model_root / "agent_presence.json",
        {
            "generated_at": FIXED_GENERATED_AT,
            "agents": [{"agent_id": "maestro", "display_name": "Maestro", "actual_state": "online"}],
        },
    )
    _write_json(
        read_model_root / "finance_invoice_reconciliation.json",
        {
            "generated_at": FIXED_GENERATED_AT,
            "counts": {"finance_candidate_count": 0, "high_risk_count": 0},
        },
    )
    payload = build_receivables_month_bounded(
        g2c_db_path=tmp_path / "missing-g2c.sqlite3",
        facts_path=None,
        generated_at=FIXED_GENERATED_AT,
    )
    (read_model_root / "receivables_month_bounded.json").write_text(stable_json(payload), encoding="utf-8")

    packet = build_maestro_context_packet(
        question="What is Capital Hilton's June invoice status?",
        read_model_root=read_model_root,
        require_real_truth=False,
    )

    [capital] = [
        fact
        for fact in packet["facts"]
        if fact.get("topic") == "receivable_month_bounded"
        and fact.get("client_ref") == "capital_hilton"
        and fact.get("month") == "2026-06"
    ]
    assert capital["amount_known"] is False
    assert capital["open_minor_units"] is None
    assert "open=unknown" in capital["value"]
    assert "$0.00" not in capital["value"]


def test_receivables_month_bounded_registered_for_refresh_and_money_coverage() -> None:
    from packet_coverage_contract import QUESTION_COVERAGE_CONTRACT
    from read_model_auto_refresh import READ_MODEL_REFRESH_REGISTRY

    entry = READ_MODEL_REFRESH_REGISTRY["receivables_month_bounded.json"]
    assert entry["refreshable"] is True
    assert entry["steps"][0]["args"][:2] == [
        "scripts/export_receivables_month_bounded.py",
        "--format",
    ]

    money_sources = {
        source
        for section in QUESTION_COVERAGE_CONTRACT["money_owed_invoice_status"]
        for source in section.source_names
    }
    plate_sources = {
        source
        for section in QUESTION_COVERAGE_CONTRACT["plate_orient_me"]
        for source in section.source_names
    }
    assert "receivables_month_bounded.json" in money_sources
    assert "receivables_month_bounded.json" in plate_sources
