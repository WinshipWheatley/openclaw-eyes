import pytest
from datetime import datetime, time, timedelta
import cassandra_briefing_brain as bb
import chief_morning_orchestrator
from cassandra_briefing_brain import generate_briefing


def test_morning_orchestrator_routes_reporter_through_scheduled_brief(monkeypatch):
    import chief_ceo_briefing
    import chief_morning_synthesis
    import chief_ops_reporter
    import chief_reporter_brain

    task_classes = []
    monkeypatch.setattr(chief_ops_reporter, "write_ops_actions_artifact", lambda: None)
    monkeypatch.setattr(chief_ceo_briefing, "refresh_nightly_polish_artifact", lambda: None)
    monkeypatch.setattr(
        chief_reporter_brain,
        "refresh_report_artifact",
        lambda *, task_class=None: task_classes.append(task_class),
    )
    monkeypatch.setattr(chief_morning_synthesis, "write_chief_morning_synthesis", lambda: None)

    assert chief_morning_orchestrator.refresh_morning_artifacts() is True
    assert task_classes == ["cassandra_scheduled_brief"]

def test_morning_orchestration_trigger(monkeypatch, tmp_path):
    # Setup paths
    synthesis = tmp_path / "Chief Morning Synthesis.md"
    monkeypatch.setattr(bb, "_CHIEF_MORNING_SYNTHESIS", synthesis)
    
    # Mock orchestrator
    refreshed_count = 0
    def mock_refresh():
        nonlocal refreshed_count
        refreshed_count += 1
        synthesis.write_text("# Chief Morning Synthesis\n\n## Top Priorities\n\n- Fresh priority", encoding="utf-8")
        return True
    
    monkeypatch.setattr(chief_morning_orchestrator, "refresh_morning_artifacts", mock_refresh)
    
    # Mock dependencies of generate_briefing
    monkeypatch.setattr(bb, "ollama_json", lambda *args, **kwargs: [{"header": "Priorities", "body": "Body"}])
    monkeypatch.setattr(bb, "_write_morning_reference_cache", lambda *args: None)
    
    # CASE 1: Missing Synthesis -> Trigger Refresh
    generate_briefing("morning")
    assert refreshed_count == 1
    
    # CASE 2: Fresh Synthesis (mtime > today 5am) -> No Refresh
    # Synthesis was just written (fresh).
    # CASE 2 fix: pin the synthesis mtime to 6am today so 'fresh synthesis' holds regardless of the
    # wall-clock time the test runs at. The clean-room gate flaked pre-5am because a 'now'-written
    # synthesis had mtime < today's 5am and the morning-window staleness check then forced a refresh.
    # Test-only; the briefing logic is unchanged.
    import os
    from cassandra_briefing_morning_policy import ORCHESTRATION_START_TIME
    _after_window_start = datetime.combine(
        datetime.now().date(),
        ORCHESTRATION_START_TIME,
    ) + timedelta(hours=1)
    _fresh_dt = max(datetime.now(), _after_window_start)
    _fresh = _fresh_dt.timestamp()
    os.utime(synthesis, (_fresh, _fresh))
    monkeypatch.setattr("cassandra_briefing_morning_policy.is_within_morning_window", lambda: True)
    
    # Reset count
    refreshed_count = 0
    generate_briefing("morning")
    assert refreshed_count == 0
    
    # CASE 3: Stale Synthesis (mtime < today 5am) -> Trigger Refresh
    # Set mtime to 4:00 AM today
    today_4am = datetime.combine(datetime.now().date(), time(4, 0))
    import os
    # utime needs epoch
    epoch = today_4am.timestamp()
    os.utime(synthesis, (epoch, epoch))
    
    refreshed_count = 0
    generate_briefing("morning")
    assert refreshed_count == 1

if __name__ == "__main__":
    pass
