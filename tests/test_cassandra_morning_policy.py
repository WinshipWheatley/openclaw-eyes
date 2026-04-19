import pytest
from datetime import datetime, time
from cassandra_briefing_morning_policy import resolve_morning_model_lane, is_within_morning_window

def test_resolve_morning_model_lane():
    # 07:00 -> strong
    dt_0700 = datetime(2026, 4, 19, 7, 0)
    task, mode = resolve_morning_model_lane(dt_0700)
    assert task == "cassandra_morning_brief"
    assert mode == "llm"

    # 07:50 -> fast (e4b)
    dt_0750 = datetime(2026, 4, 19, 7, 50)
    task, mode = resolve_morning_model_lane(dt_0750)
    assert task == "cassandra_morning_brief_test"
    assert mode == "llm"

    # 08:20 -> deterministic
    dt_0820 = datetime(2026, 4, 19, 8, 20)
    task, mode = resolve_morning_model_lane(dt_0820)
    assert task == "cassandra_morning_brief_fallback"
    assert mode == "deterministic"

def test_is_within_morning_window():
    # 04:59 -> False
    assert not is_within_morning_window(datetime(2026, 4, 19, 4, 59))
    # 05:00 -> True
    assert is_within_morning_window(datetime(2026, 4, 19, 5, 0))
    # 08:30 -> True
    assert is_within_morning_window(datetime(2026, 4, 19, 8, 30))
    # 08:31 -> False
    assert not is_within_morning_window(datetime(2026, 4, 19, 8, 31))
