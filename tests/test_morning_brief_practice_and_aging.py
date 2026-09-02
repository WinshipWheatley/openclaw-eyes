"""The morning brief carries one aging line and one practice line when the read models exist.

Both lines come from generated read models only. The aging line speaks an amount
only when the row says amount_known; the practice line is the plan's top three.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import openclaw_morning_brief as morning


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _presence(root: Path) -> None:
    _write_json(root / "agent_presence.json", {"agents": [{"agent_id": "cassandra", "actual_state": "online"}]})


def test_aging_line_names_client_days_and_action_without_inventing_amounts(tmp_path) -> None:
    root = tmp_path / "read_models"
    _presence(root)
    _write_json(
        root / morning.OPEN_AR_AGING_FILENAME,
        {
            "read_model_id": "open_ar_aging",
            "generated_at": "2026-09-02T07:35:00+00:00",
            "money_source_generated_at": "2026-09-01T23:00:00+00:00",
            "rows": [
                {
                    "client_display_name": "Capital Hilton",
                    "client_ref": "capital_hilton",
                    "month": "2026-06",
                    "amount_known": False,
                    "open_minor_units": None,
                    "currency_iso": "USD",
                    "days_past_due": 63,
                    "bucket": "60",
                    "next_action": "request_or_confirm_po",
                    "attention_priority": 1,
                },
                {
                    "client_display_name": "St. Anne's",
                    "client_ref": "st_annes",
                    "month": "2026-08",
                    "amount_known": True,
                    "open_minor_units": 25000,
                    "currency_iso": "USD",
                    "days_past_due": 0,
                    "bucket": "not_due",
                    "next_action": "wait",
                    "attention_priority": 3,
                },
            ],
        },
    )

    brief = morning.build_morning_brief(read_model_root=root, today=date(2026, 9, 2))

    assert "Aging: Capital Hilton, June, 63 days past due, request or confirm the PO." in brief
    assert "$" not in brief.split("Aging:")[1].split(".")[0]
    assert "St. Anne's" not in brief  # not due and nothing to do: stays quiet


def test_aging_line_speaks_known_amounts_and_is_dropped_when_stale(tmp_path) -> None:
    root = tmp_path / "read_models"
    _presence(root)
    row = {
        "client_display_name": "Live Arts MD",
        "client_ref": "live_arts_md",
        "month": "2026-07",
        "amount_known": True,
        "open_minor_units": 10000,
        "currency_iso": "USD",
        "days_past_due": 12,
        "bucket": "current",
        "next_action": "follow_up_draft",
        "attention_priority": 2,
    }
    _write_json(
        root / morning.OPEN_AR_AGING_FILENAME,
        {"generated_at": "2026-09-02T07:35:00+00:00", "money_source_generated_at": "2026-09-01T23:00:00+00:00", "rows": [row]},
    )
    fresh = morning.build_morning_brief(read_model_root=root, today=date(2026, 9, 2))
    assert "Aging: Live Arts MD, July, $100, 12 days past due, follow-up draft ready." in fresh

    _write_json(
        root / morning.OPEN_AR_AGING_FILENAME,
        {"generated_at": "2026-08-01T07:35:00+00:00", "money_source_generated_at": "2026-08-01T00:00:00+00:00", "rows": [row]},
    )
    stale = morning.build_morning_brief(read_model_root=root, today=date(2026, 9, 2))
    assert "Aging:" not in stale


def test_practice_line_reads_the_plan_and_streak(tmp_path) -> None:
    root = tmp_path / "read_models"
    _presence(root)
    _write_json(
        root / morning.PRACTICE_PLAN_FILENAME,
        {
            "read_model_id": "practice_plan",
            "generated_at": "2026-09-02T07:45:00+00:00",
            "plan": [
                {"title": "Blue Weather", "minutes": 15, "reason": "never practiced"},
                {"title": "The Future", "minutes": 15, "reason": "confidence 2 of 5"},
                {"title": "Slow Me Down", "minutes": 15, "reason": "12 days since last time"},
                {"title": "Ten Fingers", "minutes": 10, "reason": "would be fourth"},
            ],
            "summary": {"streak_days": 3},
        },
    )

    brief = morning.build_morning_brief(read_model_root=root, today=date(2026, 9, 2))

    assert (
        "Practice today: Blue Weather 15 min (never practiced); The Future 15 min (confidence 2 of 5); "
        "Slow Me Down 15 min (12 days since last time). Streak: 3 days."
    ) in brief
    assert "Ten Fingers" not in brief
    assert brief.startswith("Morning. You're clear today.")


def test_brief_without_either_read_model_is_unchanged(tmp_path) -> None:
    root = tmp_path / "read_models"
    _presence(root)
    assert morning.build_morning_brief(read_model_root=root, today=date(2026, 9, 2)) == "Morning. System: Cassandra online."


def test_new_daily_export_templates_render() -> None:
    for name, script in (
        ("open-ar-aging", "scripts/export_open_ar_aging.py"),
        ("capital-hilton-po-cycle", "scripts/export_capital_hilton_po_cycle.py"),
        ("practice-plan", "scripts/export_practice_plan.py"),
    ):
        service = (morning.REPO_ROOT / f"systemd/user/openclaw-{name}.service.in").read_text(encoding="utf-8")
        timer = (morning.REPO_ROOT / f"systemd/user/openclaw-{name}.timer.in").read_text(encoding="utf-8")
        rendered = service.replace("@REPO_ROOT@", "/home/openclaw")
        assert f"ExecStart=/usr/bin/env python3 /home/openclaw/{script} --format operator" in rendered
        assert "NoNewPrivileges=true" in rendered
        assert "Type=oneshot" in rendered
        assert f"Unit=openclaw-{name}.service" in timer
        assert "OnCalendar=*-*-* 07:" in timer  # all three run before the 08:00 brief
        assert "Persistent=true" in timer
