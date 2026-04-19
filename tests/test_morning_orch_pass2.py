import pytest
from datetime import datetime, time
from cassandra_briefing_morning_policy import (
    is_too_early_for_morning_delivery,
    sort_morning_chunks,
    TARGET_DELIVERY_TIME
)

def test_too_early():
    # 07:59 -> True
    dt_early = datetime(2026, 4, 19, 7, 59)
    assert is_too_early_for_morning_delivery(dt_early) is True

    # 08:00 -> False
    dt_ok = datetime(2026, 4, 19, 8, 0)
    assert is_too_early_for_morning_delivery(dt_ok) is False

    # 09:00 -> False
    dt_late = datetime(2026, 4, 19, 9, 0)
    assert is_too_early_for_morning_delivery(dt_late) is False

def test_sorting():
    chunks = [
        {"header": "Directive", "body": "..."},
        {"header": "Priorities", "body": "..."},
        {"header": "Watchlist", "body": "..."},
        {"header": "Schedule / conditions", "body": "..."},
        {"header": "Money / follow-ups", "body": "..."},
    ]
    sorted_chunks = sort_morning_chunks(chunks)
    headers = [c["header"] for c in sorted_chunks]
    assert headers == ["Priorities", "Watchlist", "Money / follow-ups", "Schedule / conditions", "Directive"]

if __name__ == "__main__":
    test_too_early()
    test_sorting()
    print("Tests passed!")
