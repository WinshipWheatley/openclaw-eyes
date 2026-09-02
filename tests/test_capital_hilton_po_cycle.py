from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import capital_hilton_po_cycle as cycle

CONTACTS = {
    "annette-sunga": {"id": "annette-sunga", "name": "Annette Sunga", "email": None},
    "lawrence-valcovic": {"id": "lawrence-valcovic", "name": "Lawrence Valcovic", "email": "will@example.invalid"},
}


def _resolver(ref: str):
    return CONTACTS.get(ref)


def _config(tmp_path: Path, performances: list[dict]) -> Path:
    payload = {
        "schema_version": "capital_hilton_po_cycle_v1",
        "client_ref": "capital_hilton",
        "client_display_name": "Capital Hilton",
        "currency_iso": "USD",
        "rate_minor_units_per_performance": 40000,
        "standard_po_performances": 5,
        "request_when_uninvoiced_reaches": 1,
        "purchase_orders": [
            {"po_number": "DCASH01147910", "cap_minor_units": 200000, "invoiced_minor_units": 200000, "source_ref": "operator"},
        ],
        "performances": performances,
        "ap_contact_refs": ["annette-sunga"],
        "requester_contact_refs": ["lawrence-valcovic"],
        "notes": [],
    }
    path = tmp_path / "po.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_shipped_config_loads_and_is_idle_with_no_performances() -> None:
    config = cycle.load_config(Path(__file__).resolve().parents[1] / "config" / "capital_hilton_po_cycle.v1.json")
    payload = cycle.build_po_cycle(config, today=date(2026, 9, 2), generated_at="2026-09-02T07:40:00+00:00", contact_resolver=_resolver)
    assert payload["purchase_orders"][0]["po_number"] == "DCASH01147910"
    assert payload["purchase_orders"][0]["status"] == "exhausted"
    assert payload["decision"]["needs_new_po"] is False
    assert payload["performances"]["uninvoiced_count"] == 0
    assert all(value is False for value in payload["authority_boundary"].values())


def test_exhausted_po_plus_one_performed_show_needs_a_new_po(tmp_path: Path) -> None:
    config = cycle.load_config(_config(tmp_path, [
        {"date": "2026-08-29", "description": "solo piano, lobby", "invoiced_under_po": None},
        {"date": "2026-09-19", "description": "upcoming", "invoiced_under_po": None},
    ]))
    payload = cycle.build_po_cycle(config, today=date(2026, 9, 2), generated_at="2026-09-02T07:40:00+00:00", contact_resolver=_resolver)
    assert payload["performances"]["performed_count"] == 1
    assert payload["performances"]["upcoming_count"] == 1
    assert payload["performances"]["uninvoiced_count"] == 1
    assert payload["capacity"]["shortfall_minor_units"] == 40000
    decision = payload["decision"]
    assert decision["needs_new_po"] is True
    assert decision["recommended_po_performances"] == 5
    assert decision["recommended_po_minor_units"] == 200000
    assert payload["contacts"]["ap"][0]["email_known"] is False


def test_invoiced_performance_does_not_trigger(tmp_path: Path) -> None:
    config = cycle.load_config(_config(tmp_path, [
        {"date": "2026-06-14", "description": "lobby", "invoiced_under_po": "DCASH01147910"},
    ]))
    payload = cycle.build_po_cycle(config, today=date(2026, 9, 2), generated_at="x", contact_resolver=_resolver)
    assert payload["decision"]["needs_new_po"] is False
    assert "invoiced under a PO" in payload["decision"]["reason"]


def test_export_writes_draft_and_attention_only_when_needed(tmp_path: Path) -> None:
    (tmp_path / "idle").mkdir(exist_ok=True)
    idle_config = _config(tmp_path / "idle", [])
    idle = cycle.export_po_cycle(
        config_path=idle_config, export_root=tmp_path / "idle" / "rm", draft_root=tmp_path / "idle" / "drafts",
        today=date(2026, 9, 2), generated_at="2026-09-02T07:40:00+00:00", contact_resolver=_resolver,
    )
    assert idle["needs_new_po"] is False
    assert idle["draft_path"] is None
    assert not (tmp_path / "idle" / "drafts").exists()
    attention = json.loads(Path(idle["attention_path"]).read_text(encoding="utf-8"))
    assert attention["status"] == "IDLE" and attention["events"] == []

    (tmp_path / "hot").mkdir(exist_ok=True)
    hot_config = _config(tmp_path / "hot", [{"date": "2026-08-29", "description": "solo piano", "invoiced_under_po": None}])
    hot = cycle.export_po_cycle(
        config_path=hot_config, export_root=tmp_path / "hot" / "rm", draft_root=tmp_path / "hot" / "drafts",
        today=date(2026, 9, 2), generated_at="2026-09-02T07:40:00+00:00", contact_resolver=_resolver,
    )
    assert hot["needs_new_po"] is True
    draft = Path(hot["draft_path"]).read_text(encoding="utf-8")
    assert draft.startswith("X-OpenClaw-Draft: prepared_only; send_hold=locked")
    assert "To: Annette Sunga" in draft
    assert "Cc: Lawrence Valcovic <will@example.invalid>" in draft
    assert "Subject: Purchase order request: Capital Hilton live music, 5 performances" in draft
    assert "5 performances at $400 each, total $2,000" in draft
    assert "- 2026-08-29 (solo piano)" in draft
    assert "DCASH01147910" in draft
    attention = json.loads(Path(hot["attention_path"]).read_text(encoding="utf-8"))
    assert attention["status"] == "CAPITAL_HILTON_PO_REQUEST_READY"
    event = attention["events"][0]
    assert event["event_id"] == "capital_hilton_po_cycle:2026-09-02"
    assert event["machine_proof"]["email_send_performed"] is False
    assert event["telegram_nudge"]["telegram_send_performed"] is False
    read_model = json.loads(Path(hot["json_path"]).read_text(encoding="utf-8"))
    assert read_model["machine_proof"]["draft_written"] is True
    assert read_model["machine_proof"]["email_send_performed"] is False
    operator = Path(hot["operator_path"]).read_text(encoding="utf-8")
    assert "NEW PO NEEDED" in operator
    assert "the machine never sends" in operator


def test_export_is_stable_on_rerun(tmp_path: Path) -> None:
    config = _config(tmp_path, [{"date": "2026-08-29", "description": "solo piano", "invoiced_under_po": None}])
    kwargs = dict(config_path=config, export_root=tmp_path / "rm", draft_root=tmp_path / "drafts", today=date(2026, 9, 2), generated_at="2026-09-02T07:40:00+00:00", contact_resolver=_resolver)
    first = cycle.export_po_cycle(**kwargs)
    first_json = Path(first["json_path"]).read_bytes()
    first_draft = Path(first["draft_path"]).read_bytes()
    second = cycle.export_po_cycle(**kwargs)
    assert Path(second["json_path"]).read_bytes() == first_json
    assert Path(second["draft_path"]).read_bytes() == first_draft
