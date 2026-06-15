import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

from guardian_watchdog import (
    WatchdogConfig,
    emit_alerts_to_ledger,
    evaluate_active_session_rule,
    evaluate_cross_role_rule,
    evaluate_guardian_watchdog,
    evaluate_morning_brief_rule,
    query_watchdog_alert_packets,
    run_guardian_watchdog,
)


FIXED_NOW = datetime(2026, 6, 15, 8, 0, 0)


def _write_morning_brief(root: Path, generated_at: datetime) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"{generated_at.date().isoformat()}_morning.json"
    path.write_text(
        json.dumps(
            {
                "slot": "morning",
                "date": generated_at.date().isoformat(),
                "generated_at": generated_at.isoformat(timespec="seconds"),
                "text": "Cassandra morning brief generated.",
                "delivered": False,
            }
        ),
        encoding="utf-8",
    )
    return path


def test_no_morning_brief_rule_fires_when_archive_is_empty(tmp_path):
    alert = evaluate_morning_brief_rule(
        briefing_dir=tmp_path / "briefings",
        now=FIXED_NOW,
        config=WatchdogConfig(morning_brief_max_age_days=1),
    )

    assert alert is not None
    assert alert.rule_id == "no_morning_brief_produced"
    assert "No Cassandra morning brief" in alert.summary
    assert alert.details["threshold_days"] == 1
    assert alert.details["guardian_action"] == "alert_only"


def test_no_morning_brief_rule_fires_when_latest_brief_is_stale(tmp_path):
    _write_morning_brief(tmp_path, FIXED_NOW - timedelta(days=3))

    alert = evaluate_morning_brief_rule(
        briefing_dir=tmp_path,
        now=FIXED_NOW,
        config=WatchdogConfig(morning_brief_max_age_days=1),
    )

    assert alert is not None
    assert alert.rule_id == "no_morning_brief_produced"
    assert "stale" in alert.summary
    assert alert.details["age_days"] > 1


def test_no_morning_brief_rule_stays_quiet_inside_configured_threshold(tmp_path):
    _write_morning_brief(tmp_path, FIXED_NOW - timedelta(days=2))

    alert = evaluate_morning_brief_rule(
        briefing_dir=tmp_path,
        now=FIXED_NOW,
        config=WatchdogConfig(morning_brief_max_age_days=3),
    )

    assert alert is None


def test_active_session_rule_fires_when_session_exceeds_threshold():
    state = {
        "status": "active",
        "active_workflow": "billing",
        "started_at": (FIXED_NOW - timedelta(hours=9)).isoformat(timespec="seconds"),
        "workflow_state": {"active": True},
    }

    alert = evaluate_active_session_rule(
        session_state=state,
        now=FIXED_NOW,
        config=WatchdogConfig(active_session_max_hours=4),
    )

    assert alert is not None
    assert alert.rule_id == "active_session_too_old"
    assert "billing" in alert.summary
    assert alert.details["age_hours"] > 4
    assert alert.details["guardian_action"] == "alert_only"


def test_active_session_rule_stays_quiet_for_recent_active_session():
    state = {
        "status": "active",
        "active_workflow": "billing",
        "started_at": (FIXED_NOW - timedelta(hours=1)).isoformat(timespec="seconds"),
    }

    alert = evaluate_active_session_rule(
        session_state=state,
        now=FIXED_NOW,
        config=WatchdogConfig(active_session_max_hours=4),
    )

    assert alert is None


def test_active_session_rule_flags_missing_start_time_for_active_session():
    state = {
        "status": "active",
        "active_workflow": "billing",
        "workflow_state": {"active": True},
    }

    alert = evaluate_active_session_rule(
        session_state=state,
        now=FIXED_NOW,
        config=WatchdogConfig(active_session_max_hours=4),
    )

    assert alert is not None
    assert alert.rule_id == "active_session_missing_started_at"
    assert "no deterministic start timestamp" in alert.summary


def test_cross_role_rule_flags_mismatched_owner_action():
    alert = evaluate_cross_role_rule(
        {
            "work_type": "morning_brief",
            "artifact_ref": "brief:2026-06-15",
            "actual_author": "Niles",
        },
        now=FIXED_NOW,
    )

    assert alert is not None
    assert alert.rule_id == "cross_role_owner_violation"
    assert alert.details["declared_owner"] == "cassandra"
    assert alert.details["observed_author"] == "niles"
    assert "owned by cassandra" in alert.summary


def test_cross_role_rule_stays_quiet_when_owner_matches():
    alert = evaluate_cross_role_rule(
        {
            "work_type": "morning_brief",
            "artifact_ref": "brief:2026-06-15",
            "actual_author": "Cassandra",
        },
        now=FIXED_NOW,
    )

    assert alert is None


def test_evaluate_guardian_watchdog_collects_all_alert_types(tmp_path):
    role_record = {
        "work_type": "morning_brief",
        "artifact_ref": "brief:2026-06-15",
        "actual_author": "Niles",
    }
    session = {
        "status": "active",
        "active_workflow": "billing",
        "started_at": (FIXED_NOW - timedelta(hours=9)).isoformat(timespec="seconds"),
    }

    alerts = evaluate_guardian_watchdog(
        briefing_dir=tmp_path / "missing-briefings",
        session_state=session,
        role_records=[role_record],
        now=FIXED_NOW,
        config=WatchdogConfig(morning_brief_max_age_days=1, active_session_max_hours=4),
    )

    assert [alert.rule_id for alert in alerts] == [
        "no_morning_brief_produced",
        "active_session_too_old",
        "cross_role_owner_violation",
    ]


def test_emit_alerts_to_ledger_records_event_packet_and_operator_explanation(tmp_path):
    alert = evaluate_cross_role_rule(
        {
            "work_type": "morning_brief",
            "artifact_ref": "brief:2026-06-15",
            "actual_author": "Niles",
        },
        now=FIXED_NOW,
    )
    assert alert is not None
    db_path = tmp_path / "ledger.sqlite"

    emitted = emit_alerts_to_ledger([alert], db_path=db_path)

    assert emitted == (alert.alert_id,)
    packets = query_watchdog_alert_packets(db_path)
    assert len(packets) == 1
    assert packets[0]["packet_id"] == alert.alert_id
    assert packets[0]["request_category"] == "cross_role_owner_violation"
    assert packets[0]["action_status"] == "alert_recorded"

    with sqlite3.connect(db_path) as conn:
        event = conn.execute(
            "SELECT event_type, actor, operator_visible_summary FROM events WHERE event_id = ?",
            (alert.alert_id,),
        ).fetchone()
        explanation = conn.execute(
            "SELECT summary, safe_for_telegram FROM operator_explanations WHERE packet_id = ?",
            (alert.alert_id,),
        ).fetchone()

    assert event == ("guardian_watchdog_alert", "guardian", alert.summary)
    assert explanation == (alert.summary, 1)


def test_run_guardian_watchdog_can_emit_alerts_without_autofix(tmp_path):
    result = run_guardian_watchdog(
        briefing_dir=tmp_path / "missing-briefings",
        session_state={"status": "idle", "workflow_state": {"active": False}},
        role_records=[],
        now=FIXED_NOW,
        emit=True,
        db_path=tmp_path / "ledger.sqlite",
    )

    assert len(result.alerts) == 1
    assert result.alerts[0].details["guardian_action"] == "alert_only"
    assert result.emitted_alert_ids == (result.alerts[0].alert_id,)
    assert query_watchdog_alert_packets(tmp_path / "ledger.sqlite")
