from __future__ import annotations

import json
from pathlib import Path


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _ar_root(tmp_path: Path) -> Path:
    root = tmp_path / "read_models"
    root.mkdir()
    _write_json(
        root / "capital_hilton_invoice_operator_run_status.json",
        {
            "client_ref": "capital_hilton",
            "client_display_name": "Capital Hilton",
            "invoice_total": "$2,000.00",
            "coupa_submitted": True,
            "coupa_submission_status": "processing",
            "email_status": "sent_operator_assisted",
            "paid": False,
            "authority_boundary": {
                "coupa_submit_allowed": False,
                "email_send_allowed": False,
                "ledger_posting_allowed": False,
                "paid_marking_allowed": False,
            },
        },
    )
    _write_json(
        root / "live_arts_md_invoice_candidate_register.json",
        {
            "client_ref": "live_arts_md",
            "client_display_name": "Live Arts MD",
            "primary_next_action": "Choose which Live Arts MD invoice to prepare.",
            "authority_boundary": {
                "email_send_performed": False,
                "ledger_posting_performed": False,
                "workbook_body_read_performed": False,
                "operator_provided": True,
            },
            "invoice_candidates": [
                {
                    "invoice_id": "2026-1001",
                    "amount": 900,
                    "amount_display": "$900",
                    "invoice_status": "Draft - ready to send",
                    "receipt_status": "UNPAID",
                    "send_readiness": "BLOCKED_NEEDS_ARTIFACT_RECIPIENT_GUARDIAN_APPROVAL",
                    "readiness_status": "NEEDS_ARTIFACT_RECIPIENT_GUARDIAN_APPROVAL",
                    "paid": False,
                },
                {
                    "invoice_id": "2026-1002",
                    "amount": 4625,
                    "amount_display": "$4,625",
                    "invoice_status": "Draft - verify before send",
                    "receipt_status": "UNPAID",
                    "send_readiness": "NOT_SEND_READY",
                    "readiness_status": "NEEDS_OPERATOR_VERIFICATION",
                    "paid": False,
                },
                {
                    "invoice_id": "2026-1003",
                    "amount": 0,
                    "amount_display": "$0",
                    "invoice_status": "Future/draft",
                    "receipt_status": "UNPAID",
                    "paid": False,
                },
            ],
        },
    )
    _write_json(
        root / "st_annes_monthly_work_log_contract.json",
        {
            "client_ref": "st_annes",
            "client_display_name": "St. Anne's",
            "authority_boundary": {"email_send_allowed": False, "ledger_posting_allowed": False},
        },
    )
    _write_json(
        root / "st_annes_work_log_review_surface.json",
        {
            "client_ref": "st_annes",
            "authority_boundary": {"email_send_allowed": False, "ledger_posting_allowed": False},
            "events": [
                {
                    "amount": 125,
                    "invoice_inclusion_status": "NOT_INCLUDED_SMOKE_EVENT",
                    "billing_truth_status": "SMOKE_OR_TEST_EVENT",
                }
            ],
        },
    )
    return root


def test_ar_receivables_rollup_is_read_only_and_excludes_st_annes_smoke(tmp_path: Path) -> None:
    from ar_receivables_read_model import build_ar_receivables_read_model

    payload = build_ar_receivables_read_model(read_model_root=_ar_root(tmp_path), generated_at="2026-06-21T00:00:00Z")

    assert payload["status"] == "READY"
    assert payload["open_amount_display"] == "$7,525.00"
    assert payload["open_receivable_count"] == 3
    assert payload["authority_boundary"]["email_send_allowed"] is False
    assert payload["authority_boundary"]["money_movement_allowed"] is False
    assert payload["machine_proof"]["unsafe_authority_granted"] is False
    assert payload["machine_proof"]["st_annes_smoke_events_not_counted_as_ar"] is True
    assert any(row["client_display_name"] == "St. Anne's" and row["open_amount_value"] == 0 for row in payload["receivables"])
    assert "Capital Hilton" in payload["operator_summary"]
    assert "Live Arts MD" in payload["operator_summary"]
    assert "no send, money movement, bank access, or ledger mutation is allowed" in payload["next_safe_ar_move"]


def test_maestro_packet_includes_ar_receivables_rollup(monkeypatch, tmp_path: Path) -> None:
    from maestro_context_packet import build_maestro_context_packet, format_maestro_context_packet

    store_path = tmp_path / "operator_truth_store.json"
    seed_path = tmp_path / "OPERATOR-TRUTH.md"
    seed_path.write_text("Capital Hilton: $2000 received; Live Arts MD has draft AR candidates.", encoding="utf-8")
    monkeypatch.setenv("OPENCLAW_OPERATOR_TRUTH_STORE", str(store_path))
    monkeypatch.setenv("OPENCLAW_OPERATOR_TRUTH_SEED", str(seed_path))

    packet = build_maestro_context_packet(
        question="what is my AR status and next safe move?",
        read_model_root=_ar_root(tmp_path),
        operator_truth_store_path=store_path,
        require_real_truth=True,
    )
    text = format_maestro_context_packet(packet)
    ar_facts = [fact for fact in packet["facts"] if fact.get("topic") == "ar_receivables"]

    assert ar_facts
    assert "Open total: $7,525.00" in ar_facts[0]["value"]
    assert "Next safe AR move" in ar_facts[0]["value"]
    assert "generated/read_models/ar_receivables_status.json" in ar_facts[0]["source_ref"]
    assert any("$7,525.00" in item for item in packet["actionable"]["money_in_out"])
    assert "AR receivables rollup" in text
    assert packet["bounds"]["outbound_send_allowed"] is False
    assert packet["bounds"]["money_movement_allowed"] is False
