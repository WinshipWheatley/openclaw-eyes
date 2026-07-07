from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

import operator_truth_store
import pytest

from contacts_registry import ContactsRegistry
from maestro_context_packet import build_maestro_context_packet


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _seed_operator_truth(tmp_path: Path) -> Path:
    truth_path = tmp_path / "operator_truth.json"
    operator_truth_store.upsert_operator_truth(
        "coverage",
        "Coverage fixture truth: Capital Hilton invoice and St. Anne's receivable answers must use packet facts, not memory.",
        source_surface="test",
        source_text="Coverage fixture truth: Capital Hilton invoice and St. Anne's receivable answers must use packet facts, not memory.",
        source_ref="test:coverage",
        at="2026-07-07T10:00:00+00:00",
        path=truth_path,
    )
    return truth_path


def _seed_read_models(tmp_path: Path, *, stale_agent_presence: bool = False) -> Path:
    root = tmp_path / "read_models"
    fresh = "2026-07-07T10:00:00+00:00"
    _write_json(
        root / "agent_presence.json",
        {
            "generated_at": "2026-06-01T10:00:00+00:00" if stale_agent_presence else fresh,
            "agents": [
                {"agent_id": "cassandra", "display_name": "Cassandra", "actual_state": "online"},
                {"agent_id": "chief", "display_name": "Chief", "actual_state": "online"},
            ],
            "next_safe_move": "Review agent coverage before dispatch.",
        },
    )
    _write_json(
        root / "chief_status_rail.json",
        {
            "generated_at": fresh,
            "chief_current_status": "Chief is available for bounded status readback.",
            "chief_current_proven_role": {"role_summary": "ops router, no self-approval"},
        },
    )
    _write_json(
        root / "openclaw_capability_index.json",
        {
            "generated_at": fresh,
            "generic_capabilities": [
                {"capability_id": "packet", "capability_name": "Packet building", "capability_status": "LIVE_IMPLEMENTED"}
            ],
        },
    )
    _write_json(
        root / "operator_attention_delivery_contract.json",
        {
            "generated_at": fresh,
            "surfaced_attention_items": [
                {
                    "attention_id": "plate-1",
                    "actor_label": "Chief",
                    "human_message": "Capital Hilton and St. Anne's need review today.",
                    "concise_spoken_guidance": "Check receivables and upcoming gigs.",
                    "reason_for_attention": "operator plate fixture",
                    "client_ref": "st_annes",
                }
            ],
        },
    )
    _write_json(
        root / "helm_operator_attention_package.json",
        {
            "generated_at": fresh,
            "primary_cards": {
                "helm-1": {
                    "operator_summary": "Finance plate has one follow-up.",
                    "safe_next_move": "Use the packet coverage matrix.",
                    "actionability": "review_only",
                }
            },
        },
    )
    _write_json(
        root / "autonomous_followup_watch_attention.json",
        {
            "generated_at": fresh,
            "attention_items": [
                {"id": "follow-1", "summary": "Follow up with St. Anne's.", "next_safe_move": "Review only."}
            ],
        },
    )
    _write_json(
        root / "st_annes_receivable_state.json",
        {
            "generated_at": fresh,
            "client_ref": "st_annes",
            "paid_up_status": "invoice_due",
            "summary": "St. Anne's has a month-bounded receivable needing review.",
            "next_safe_move": "Review the structured receivable before saying paid up.",
            "send_hold_active": True,
            "ledger_mutation_allowed": False,
        },
    )
    _write_json(
        root / "finance_invoice_reconciliation.json",
        {
            "generated_at": fresh,
            "counts": {"finance_candidate_count": 2, "high_risk_count": 0},
            "first_safe_workflow_proposal": {"operator_summary": "Receivable facts are review-only."},
        },
    )
    _write_json(
        root / "cassandra_email_calendar_delta_detangle.json",
        {
            "generated_at": fresh,
            "calendar_operator_context": {
                "google_apple_calendar_merged_context_recorded": True,
                "live_calendar_access_enabled": False,
            },
            "classification_counts": {"DRAFT_PREVIEW_ONLY": 1},
            "upcoming_calendar_events": [
                {"title": "Live Arts rehearsal", "start": "2026-07-09T19:00:00-04:00", "location": "hall"}
            ],
        },
    )
    _write_json(
        root / "local_gig_schedule.json",
        {
            "generated_at": fresh,
            "gigs": [
                {
                    "gig_id": "gig-live-arts-1",
                    "title": "Live Arts rehearsal",
                    "date": "2026-07-09",
                    "venue": "Live Arts MD",
                    "status": "scheduled",
                }
            ],
        },
    )
    _write_json(
        root / "client_invoice_workflow_framework.json",
        {
            "generated_at": fresh,
            "clients": {
                "st_annes": {"display_name": "St. Anne's", "uses_coupa": False, "default_channel": "email"}
            },
        },
    )
    return root


def _build_packet(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    stale_agent_presence: bool = False,
) -> tuple[dict[str, Any], Path]:
    root = _seed_read_models(tmp_path, stale_agent_presence=stale_agent_presence)
    truth_path = _seed_operator_truth(tmp_path)
    contacts_db = tmp_path / "contacts.sqlite3"
    ContactsRegistry(str(contacts_db), seed=True)
    monkeypatch.setenv("OPENCLAW_CONTACTS_DB_PATH", str(contacts_db))
    packet = build_maestro_context_packet(
        question="orient me on my plate, invoices, gigs, contacts, agent status, advice, and drafting",
        read_model_root=root,
        operator_truth_store_path=truth_path,
        require_real_truth=True,
    )
    return packet, root


def test_each_question_class_has_required_sections_from_real_packet_fixtures(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from packet_coverage_contract import QUESTION_CLASSES, evaluate_packet_coverage

    packet, root = _build_packet(tmp_path, monkeypatch)

    for question_class in QUESTION_CLASSES:
        report = evaluate_packet_coverage(
            packet,
            question_class=question_class,
            read_model_root=root,
            today=date(2026, 7, 7),
        )
        assert report["covered"] is True, question_class
        missing = [section["section_id"] for section in report["sections"] if not section["covered"]]
        assert missing == []


def test_matrix_export_refreshes_and_flags_stale_source(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from packet_coverage_contract import build_packet_coverage_matrix
    from scripts.export_packet_coverage_matrix import export_packet_coverage_matrix

    packet, root = _build_packet(tmp_path, monkeypatch, stale_agent_presence=True)
    payload = build_packet_coverage_matrix(
        read_model_root=root,
        packets_by_agent={"maestro": packet},
        today=date(2026, 7, 7),
    )
    status_row = next(
        row
        for row in payload["coverage"]
        if row["agent"] == "maestro" and row["question_class"] == "agent_system_status"
    )
    assert status_row["covered"] is True
    assert status_row["sources_fresh"] is False
    assert status_row["source_statuses"]["agent_presence.json"]["freshness_status"] == "stale"

    exported = export_packet_coverage_matrix(
        read_model_root=root,
        export_root=tmp_path / "generated" / "read_models",
        packets_by_agent={"maestro": packet},
        today=date(2026, 7, 7),
    )
    output = tmp_path / "generated" / "read_models" / "packet_coverage_matrix.json"
    assert output.exists()
    assert exported["schema_version"] == "packet_coverage_matrix_v1"
    assert json.loads(output.read_text())["coverage"] == exported["coverage"]


def test_packet_coverage_matrix_registered_for_auto_refresh() -> None:
    from read_model_auto_refresh import READ_MODEL_REFRESH_REGISTRY

    entry = READ_MODEL_REFRESH_REGISTRY["packet_coverage_matrix.json"]
    assert entry["refreshable"] is True
    assert entry["steps"][0]["args"][:2] == ["scripts/export_packet_coverage_matrix.py", "--format"]


def test_plate_probe_packet_carries_attention_receivables_and_generic_gigs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    packet, _root = _build_packet(tmp_path, monkeypatch)
    packet_text = packet["packet_text"].lower()

    assert "capital hilton and st. anne's need review today" in packet_text
    assert "month-bounded receivable" in packet_text
    assert "live arts rehearsal" in packet_text
    assert any(fact.get("source_ref", "").endswith("local_gig_schedule.json") for fact in packet["facts"])
