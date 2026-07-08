from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import openclaw_morning_brief as morning


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def test_morning_brief_uses_structured_facts_and_skips_empty_sections(tmp_path) -> None:
    root = tmp_path / "read_models"
    _write_json(
        root / "st_annes_receivable_state.json",
        {
            "as_of": "2026-07-06",
            "open_items": [
                {
                    "client": "St. Anne's",
                    "project": "two-event PDF",
                    "amount": 1095,
                    "currency": "USD",
                    "status": "open",
                }
            ],
        },
    )
    _write_json(
        root / "niles_gig_schedule.json",
        {
            "events": [
                {
                    "date": "2026-07-07",
                    "time": "7:00 PM",
                    "title": "St. Anne's helper preview",
                    "type": "gig",
                },
                {
                    "date": "2026-07-08",
                    "time": "9:00 PM",
                    "title": "Tomorrow should not appear",
                    "type": "gig",
                },
            ]
        },
    )
    _write_json(root / "work_board.json", {"latest_cards": []})
    _write_json(
        root / "agent_presence.json",
        {
            "agents": [
                {"agent_id": "maestro", "actual_state": "online"},
                {"agent_id": "cassandra", "actual_state": "online"},
            ]
        },
    )

    brief = morning.build_morning_brief(read_model_root=root, today=date(2026, 7, 7))

    assert "St. Anne's two-event PDF still owes $1,095" in brief
    assert "7:00 PM St. Anne's helper preview" in brief
    assert "Tomorrow should not appear" not in brief
    assert "decision" not in brief.lower()
    assert "nothing" not in brief.lower()
    assert "|" not in brief
    assert "- " not in brief


def test_morning_brief_does_not_launder_unstructured_money(tmp_path) -> None:
    root = tmp_path / "read_models"
    _write_json(
        root / "finance_invoice_reconciliation.json",
        {
            "items": [
                {
                    "client": "Loose Note",
                    "summary": "Client may owe $1095, maybe.",
                    "status": "open",
                }
            ]
        },
    )

    brief = morning.build_morning_brief(read_model_root=root, today=date(2026, 7, 7))

    assert "$1,095" not in brief
    assert "Loose Note" not in brief


def test_morning_brief_uses_approved_humanizer_for_known_amount(tmp_path) -> None:
    """Task 127: money items render via operator_surface_guard.render_operator_money_
    status_line -- no raw snake_case status token, month code shown as a name in parens."""
    root = tmp_path / "read_models"
    _write_json(
        root / "receivable_status.json",
        {
            "items": [
                {
                    "client": "Live Arts MD",
                    "month": "2026-06",
                    "open_minor_units": 109500,
                    "currency": "USD",
                    "payment_status": "needs_reconcile",
                    "as_of": "2026-07-07",
                }
            ]
        },
    )

    brief = morning.build_morning_brief(read_model_root=root, today=date(2026, 7, 7))

    assert "Live Arts MD (June) still owes $1,095 — needs your reconcile" in brief
    assert "needs_reconcile" not in brief
    assert "2026-06" not in brief


def test_morning_brief_includes_unknown_amount_item_as_attention_line(tmp_path) -> None:
    """Task 127: a pending 'check expected' item is plate-worthy even with no confirmed
    amount -- must not be silently dropped just because there's no number yet."""
    root = tmp_path / "read_models"
    _write_json(
        root / "receivable_status.json",
        {
            "items": [
                {
                    "client": "Capital Hilton",
                    "month": "2026-06",
                    "payment_status": "open_amount_unknown",
                    "as_of": "2026-07-07",
                }
            ]
        },
    )

    brief = morning.build_morning_brief(read_model_root=root, today=date(2026, 7, 7))

    assert "Capital Hilton (June): check expected, amount not yet confirmed" in brief
    assert "open_amount_unknown" not in brief


def test_morning_brief_live_probe_quality_money_decisions_and_voice(tmp_path) -> None:
    root = tmp_path / "read_models"
    src = morning.REPO_ROOT / "generated/read_models/receivables_month_bounded.json"
    (root / "receivables_month_bounded.json").parent.mkdir(parents=True, exist_ok=True)
    (root / "receivables_month_bounded.json").write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    _write_json(
        root / "work_board.json",
        {
            "cards": [
                {
                    "status": "needs_operator_review",
                    "summary": "Intent: Hermes, synthesize current posture",
                },
                {
                    "status": "pending_approval",
                    "title": "Approve Capital Hilton invoice review packet",
                },
            ],
        },
    )
    _write_json(
        root / "agent_presence.json",
        {"agents": [{"agent_id": "maestro", "display_name": "Maestro", "actual_state": "online"}]},
    )

    brief = morning.build_morning_brief(read_model_root=root, today=date(2026, 7, 7))
    lowered = brief.lower()

    assert "live arts" in lowered
    assert "$1,095" in brief
    # Task 127: zero raw snake_case tokens -- the approved humanizer renders "needs your
    # reconcile", never the machine status token.
    assert "needs_reconcile" not in lowered
    assert "needs your reconcile" in lowered
    assert "Intent:" not in brief
    assert "Hermes, synthesize current posture" not in brief
    assert "Approve Capital Hilton invoice review packet" in brief
    assert brief.startswith("Morning. You're clear today except")
    assert len([part for part in brief.split(".") if part.strip()]) <= 4
    assert "timer" not in lowered


def test_morning_brief_once_invokes_master_voice_with_stdin(tmp_path) -> None:
    root = tmp_path / "read_models"
    _write_json(
        root / "agent_presence.json",
        {"agents": [{"agent_id": "maestro", "actual_state": "online"}]},
    )
    calls: list[dict[str, object]] = []

    def fake_run(argv, *, input, text, check, env):
        calls.append({"argv": argv, "input": input, "text": text, "check": check, "env": env})

    sent = morning.run_once(read_model_root=root, today=date(2026, 7, 7), runner=fake_run)

    assert sent == "Morning. System: Maestro online."
    assert calls[0]["argv"][-1] == str(morning.REPO_ROOT / "master_voice.sh")
    assert calls[0]["input"] == sent
    assert calls[0]["text"] is True
    assert calls[0]["check"] is True
    assert calls[0]["env"]["OPENCLAW_AGENT"] == "maestro"


def test_morning_brief_systemd_templates_render() -> None:
    service = (morning.REPO_ROOT / "systemd/user/openclaw-morning-brief.service.in").read_text(encoding="utf-8")
    timer = (morning.REPO_ROOT / "systemd/user/openclaw-morning-brief.timer.in").read_text(encoding="utf-8")

    rendered_service = service.replace("@REPO_ROOT@", "/home/openclaw")
    rendered_timer = timer.replace("@REPO_ROOT@", "/home/openclaw")

    assert "ExecStart=/usr/bin/env python3 /home/openclaw/openclaw_morning_brief.py --once" in rendered_service
    assert "OnCalendar=*-*-* 08:00:00" in rendered_timer
    assert "Unit=openclaw-morning-brief.service" in rendered_timer
    assert "@REPO_ROOT@" not in rendered_service
    assert "@REPO_ROOT@" not in rendered_timer
