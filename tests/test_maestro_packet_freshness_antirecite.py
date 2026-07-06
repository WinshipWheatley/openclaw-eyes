from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import operator_truth_store
from ar_expected_receivable_record import create_expected_receivable
from ar_gig_to_cash_store import GigToCashStore
from ar_invoice_record import create_invoice_record
from frontdoor_prompt import build_frontdoor_prompt
from maestro_context_packet import build_maestro_context_packet
from receivable_temporal_scoping import ClientPaidThroughStore


def _seed_read_models(tmp_path: Path) -> Path:
    root = tmp_path / "read_models"
    root.mkdir()
    (root / "agent_presence.json").write_text(
        json.dumps(
            {
                "generated_at": "2026-07-06T09:00:00+00:00",
                "agents": [{"agent_id": "cassandra", "display_name": "Cassandra", "actual_state": "online"}],
            }
        ),
        encoding="utf-8",
    )
    (root / "work_board.json").write_text(
        json.dumps(
            {
                "generated_at": "2026-07-06T09:01:00+00:00",
                "counts_by_column": {"active": 1, "blocked": 0},
            }
        ),
        encoding="utf-8",
    )
    (root / "finance_invoice_reconciliation.json").write_text(
        json.dumps(
            {
                "generated_at": "2026-07-06T09:02:00+00:00",
                "summary": "Finance packets are metadata only; send remains blocked.",
            }
        ),
        encoding="utf-8",
    )
    return root


def _seed_truth(monkeypatch, tmp_path: Path, value: str) -> Path:
    monkeypatch.setenv("OPENCLAW_TEST_MODE", "1")
    store_path = tmp_path / "operator_truth_store.json"
    operator_truth_store.upsert_operator_truth(
        "st_annes",
        value,
        source_surface="test",
        source_text=value,
        source_ref="telegram:test:st_annes_paid_note",
        at="2026-06-15T12:00:00+00:00",
        path=store_path,
    )
    return store_path


def _seed_open_st_annes_receivable(tmp_path: Path) -> tuple[Path, Path]:
    ar_path = tmp_path / "gig_to_cash.sqlite3"
    paid_path = tmp_path / "paid_through.sqlite3"
    paid_store = ClientPaidThroughStore(paid_path)
    paid_store.set_paid_through("st_annes", date(2026, 6, 15), source_ref="test")
    with GigToCashStore(str(ar_path)) as store:
        invoice = create_invoice_record(
            invoice_id="inv:st-annes-july",
            counterparty_ref="st_annes",
            billing_entity_ref="winship_live",
            lifecycle_state="issued",
            invoice_number="ST-ANNES-JULY",
            issue_date_iso="2026-07-01",
            due_date_iso="2026-07-01",
            currency_iso="USD",
            total_minor_units=25000,
            idempotency_key="invoice:st-annes-july",
            source_ref="test",
        )
        store.append(invoice)
        store.append(
            create_expected_receivable(
                receivable_id="recv:st-annes-july",
                invoice_id=invoice.invoice_id,
                invoice_version_id=invoice.invoice_version_id,
                counterparty_ref="st_annes",
                expected_minor_units=25000,
                currency_iso="USD",
                due_date_iso="2026-07-01",
                recognized_utc_iso="2026-07-01T00:00:00+00:00",
                idempotency_key="receivable:st-annes-july",
                source_ref="test",
            )
        )
    return ar_path, paid_path


def test_stale_paid_up_operator_truth_loses_to_current_receivable_state(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("OPENCLAW_TODAY", "2026-07-06")
    read_models = _seed_read_models(tmp_path)
    truth_path = _seed_truth(
        monkeypatch,
        tmp_path,
        "I got your message, one thing I want you to remember: I'm actually all paid up with St Annes.",
    )
    ar_path, paid_path = _seed_open_st_annes_receivable(tmp_path)

    packet = build_maestro_context_packet(
        question="who do I talk to at st annes + invoice status",
        read_model_root=read_models,
        operator_truth_store_path=truth_path,
        require_real_truth=True,
        session={
            "gig_to_cash_db_path": str(ar_path),
            "client_paid_through_store_path": str(paid_path),
            "as_of_date": "2026-07-06",
        },
    )

    temporal_facts = [fact for fact in packet["facts"] if fact.get("topic") == "receivable_temporal_state"]
    assert temporal_facts
    assert any("invoice_due" in fact["value"] for fact in temporal_facts)
    assert "actually all paid up" not in packet["packet_text"].lower()
    assert not any(
        fact.get("topic") == "operator_truth"
        and "paid up" in str(fact.get("value") or "").lower()
        and fact.get("current_truth", True) is True
        for fact in packet["facts"]
    )


def test_operator_truth_raw_notes_are_marked_no_verbatim_and_prompt_honors_it(monkeypatch, tmp_path: Path) -> None:
    read_models = _seed_read_models(tmp_path)
    raw_note = "I got your message, one thing I want you to remember: St Anne's is paid up through June 15."
    truth_path = _seed_truth(monkeypatch, tmp_path, raw_note)

    packet = build_maestro_context_packet(
        question="what is the St Anne's invoice status?",
        read_model_root=read_models,
        operator_truth_store_path=truth_path,
        require_real_truth=True,
    )

    truth_fact = next(fact for fact in packet["facts"] if fact.get("topic") == "operator_truth")
    assert truth_fact["raw_operator_note"] is True
    assert truth_fact["verbatim_readback"] is False
    assert truth_fact["operator_note_handling"] == "distill_not_quote"

    prompt, _manifest = build_frontdoor_prompt(
        packet,
        "what is the St Anne's invoice status?",
        max_chars=2400,
    )
    assert "I got your message" not in prompt
    assert "one thing I want you to remember" not in prompt
    assert "paid up through June 15" in prompt
    assert "do not quote verbatim" in prompt.lower()


def test_grounded_packet_keeps_sourced_read_model_facts_without_drift_session(monkeypatch, tmp_path: Path) -> None:
    read_models = _seed_read_models(tmp_path)
    truth_path = _seed_truth(monkeypatch, tmp_path, "St Anne's invoice contact is Draper and the status needs review.")

    packet = build_maestro_context_packet(
        question="who do I talk to at st annes + invoice status",
        read_model_root=read_models,
        operator_truth_store_path=truth_path,
        require_real_truth=True,
    )

    assert packet["machine_proof"]["read_model_count"] >= 2
    assert all(str(fact.get("source_ref") or "") for fact in packet["facts"])
    assert any("Work board columns" in str(fact.get("value") or "") for fact in packet["facts"])
