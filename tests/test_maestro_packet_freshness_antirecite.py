from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import operator_truth_store
from ar_expected_receivable_record import create_expected_receivable
from ar_gig_to_cash_store import GigToCashStore
from ar_invoice_record import create_invoice_record
from frontdoor_prompt import build_frontdoor_prompt
import maestro_cassandra_responder as maestro
from maestro_context_packet import build_maestro_context_packet
from receivable_temporal_scoping import ClientPaidThroughStore


ROOT = Path(__file__).resolve().parents[1]


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
    src = ROOT / "generated/read_models/client_invoice_workflow_framework.json"
    (root / "client_invoice_workflow_framework.json").write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
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


def test_plate_question_packet_carries_operator_attention_and_due_receivables(monkeypatch, tmp_path: Path) -> None:
    read_models = _seed_read_models(tmp_path)
    truth_path = _seed_truth(
        monkeypatch,
        tmp_path,
        "St Anne's invoice contact is Draper and plate questions should use current read models.",
    )
    (read_models / "operator_attention_delivery_contract.json").write_text(
        json.dumps(
            {
                "generated_at": "2026-07-07T14:00:00+00:00",
                "read_model_id": "operator_attention_delivery_contract",
                "surfaced_attention_items": {
                    "st_annes_followup": {
                        "actor_label": "Cassandra",
                        "human_message": "St. Anne's needs Draper follow-up tonight.",
                        "reason_for_attention": "needs_reconcile",
                        "primary_human_action_label": "Review follow-up",
                        "concise_spoken_guidance": "Ask Draper to confirm he forwarded the 2026-06 invoice to Glenn.",
                        "urgency_level": "open_not_paid",
                        "client_ref": "st_annes",
                        "workflow_ref": "st_annes_forward_tracking",
                        "world_ref": "finance",
                        "email_send_allowed": False,
                        "external_action_allowed": False,
                        "telegram_send_allowed": False,
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    (read_models / "helm_operator_attention_package.json").write_text(
        json.dumps(
            {
                "generated_at": "2026-07-07T14:01:00+00:00",
                "read_model_id": "helm_operator_attention_package",
                "primary_cards": [
                    {
                        "card_ref": "primary:st_annes_followup",
                        "actionability": "ACTION_REQUIRED",
                        "operator_summary": "St. Anne's forward-to-Glenn proof is still the plate item.",
                        "safe_next_move": "Review the Draper follow-up draft before any send.",
                        "proof_refs": ["generated/read_models/st_annes_receivable_state.json"],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    (read_models / "autonomous_followup_watch_attention.json").write_text(
        json.dumps(
            {
                "generated_at": "2026-07-07T14:02:00+00:00",
                "read_model_id": "autonomous_followup_watch_attention",
                "attention_items": [
                    {
                        "attention_id": "st_annes_forward_watch",
                        "client_ref": "st_annes",
                        "summary": "St. Anne's is awaiting Draper's confirmation that Glenn has the invoice.",
                        "next_safe_move": "Surface the draft for operator review only.",
                        "requires_operator": True,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    (read_models / "st_annes_receivable_state.json").write_text(
        json.dumps(
            {
                "generated_at": "2026-07-07T14:03:00+00:00",
                "read_model_id": "st_annes_receivable_state",
                "client_ref": "st_annes",
                "paid_up_status": "invoice_due",
                "summary": "St. Anne's July receivable is due and needs follow-up with Draper.",
                "next_safe_move": "Confirm Draper forwarded the invoice to Glenn before any send.",
                "send_hold_active": True,
                "ledger_mutation_allowed": False,
            }
        ),
        encoding="utf-8",
    )

    packet = build_maestro_context_packet(
        question="what's on my plate tonight, and what actually needs me?",
        read_model_root=read_models,
        operator_truth_store_path=truth_path,
        require_real_truth=True,
    )

    source_refs = set(packet["source_refs"])
    assert "generated/read_models/operator_attention_delivery_contract.json" in source_refs
    assert "generated/read_models/helm_operator_attention_package.json" in source_refs
    assert "generated/read_models/autonomous_followup_watch_attention.json" in source_refs
    assert "generated/read_models/st_annes_receivable_state.json" in source_refs
    plate_blob = "\n".join(str(fact.get("value") or "") for fact in packet["facts"])
    assert "St. Anne's needs Draper follow-up tonight." in plate_blob
    assert "forward-to-Glenn proof" in plate_blob
    assert "awaiting Draper's confirmation" in plate_blob
    assert "July receivable is due" in plate_blob
    assert "needs_reconcile" not in plate_blob
    assert "open_not_paid" not in packet["packet_text"]
    assert "needs your reconcile" in packet["packet_text"]
    assert "check expected, not yet paid" in packet["packet_text"]
    assert "June invoice" in packet["packet_text"]
    attention_blob = "\n".join(packet["actionable"]["needs_attention"])
    assert "St. Anne's needs Draper follow-up tonight." in attention_blob
    assert "July receivable is due" in packet["packet_text"]
    assert "I don't have that" not in packet["packet_text"]

    def _plate_grounded_stub(text: str, *, context_packet=None, **kwargs):
        packet_text = str((context_packet or {}).get("packet_text") or "")
        if "St. Anne's needs Draper follow-up tonight." in packet_text and "July receivable is due" in packet_text:
            return {
                "text": (
                    "Tonight: St. Anne's needs Draper follow-up. "
                    "The July receivable is due; review the Draper follow-up draft before any send."
                ),
                "receipt": {
                    "receipt_id": "stub_plate_grounded",
                    "decision": "INJECTED_STUB",
                    "external_llm_invoked": False,
                    "local_model_invoked": False,
                    "model_call_performed": False,
                },
            }
        return {
            "text": "I don't have that in the current Maestro packet.",
            "receipt": {
                "receipt_id": "stub_plate_missing",
                "decision": "INJECTED_STUB",
                "external_llm_invoked": False,
                "local_model_invoked": False,
                "model_call_performed": False,
            },
        }

    result = maestro.answer_frontdoor_chat(
        "what's on my plate tonight, and what actually needs me?",
        session={
            "read_model_root": read_models.as_posix(),
            "operator_truth_store_path": truth_path.as_posix(),
        },
        source_surface="operator_maestro_chat",
        protected_generate_fn=_plate_grounded_stub,
    )

    assert result.status == "ANSWER_READY"
    assert "St. Anne's needs Draper follow-up" in result.plain_summary
    assert "July receivable is due" in result.plain_summary
    assert "I don't have that" not in result.plain_summary


def test_freeform_maestro_brain_gets_client_billing_channel_facts(monkeypatch, tmp_path: Path) -> None:
    read_models = _seed_read_models(tmp_path)
    truth_path = _seed_truth(
        monkeypatch,
        tmp_path,
        "Use the canonical client invoice workflow framework for client billing-channel facts.",
    )
    captured: dict[str, object] = {}

    def _billing_grounded_stub(text: str, *, context_packet=None, **kwargs):
        captured["context_packet"] = context_packet
        packet_text = str((context_packet or {}).get("packet_text") or "").lower()
        if (
            "st. anne's does not use coupa" in packet_text
            and "capital hilton uses coupa" in packet_text
            and "client_invoice_workflow_framework.json" in packet_text
        ):
            return {
                "text": "St Anne's does not use Coupa by default. Capital Hilton uses Coupa for its client recipe.",
                "receipt": {
                    "receipt_id": "stub_billing_grounded",
                    "decision": "INJECTED_STUB",
                    "external_llm_invoked": False,
                    "local_model_invoked": False,
                    "model_call_performed": False,
                },
            }
        return {
            "text": "St Anne's uses Coupa from a PO.",
            "receipt": {
                "receipt_id": "stub_billing_ungrounded",
                "decision": "INJECTED_STUB",
                "external_llm_invoked": False,
                "local_model_invoked": False,
                "model_call_performed": False,
            },
        }

    result = maestro.answer_frontdoor_chat(
        "What should I check before I submit St Anne's invoice through Coupa, and does Capital Hilton need Coupa?",
        session={
            "read_model_root": read_models.as_posix(),
            "operator_truth_store_path": truth_path.as_posix(),
        },
        source_surface="operator_maestro_chat",
        protected_generate_fn=_billing_grounded_stub,
    )

    assert result.status == "ANSWER_READY"
    assert result.intent_class == "maestro_brain_freeform"
    answer = result.plain_summary.lower()
    assert "st anne's uses coupa" not in answer
    assert "st anne's does not use coupa" in answer
    assert "capital hilton uses coupa" in answer

    packet = captured["context_packet"]
    assert isinstance(packet, dict)
    billing_facts = [fact for fact in packet["facts"] if fact.get("topic") == "client_billing_channel"]
    facts_by_client = {
        str(fact.get("client_ref") or ""): bool(fact.get("uses_coupa"))
        for fact in billing_facts
    }
    assert facts_by_client.items() >= {"st_annes": False, "capital_hilton": True}.items()
    assert any(
        fact.get("client_ref") == "st_annes"
        and fact.get("purchase_order_required") is False
        and "does not use Coupa" in str(fact.get("value") or "")
        for fact in billing_facts
    )
    assert "generated/read_models/client_invoice_workflow_framework.json" in packet["source_refs"]
