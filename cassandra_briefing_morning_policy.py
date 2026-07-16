"""
cassandra_briefing_morning_policy.py

Time-aware orchestration policy for Cassandra's morning briefing.
Defines windows, deadlines, and model selection rules based on the clock.
"""

from datetime import datetime, time

# ── Policy Windows ────────────────────────────────────────────────────────────

ORCHESTRATION_START_TIME = time(5, 0)
TARGET_DELIVERY_TIME = time(8, 0)
ADAPTIVE_DOWNGRADE_TIME = time(7, 45)
DETERMINISTIC_FALLBACK_TIME = time(8, 15)
EMERGENCY_OVERFLOW_TIME = time(8, 30)

# ── Chunk Ordering ────────────────────────────────────────────────────────────

MORNING_CHUNK_ORDER = [
    "Priorities",
    "Watchlist",
    "Money / follow-ups",
    "Schedule / conditions",
    "Directive"
]

# ── Model Selection ────────────────────────────────────────────────────────────

def resolve_morning_model_lane(current_dt: datetime | None = None) -> tuple[str, str]:
    """
    Select the appropriate model and lane based on the current time.
    
    - Before 07:45: production 8B scheduled-brief lane
    - 07:45 - 08:15: compact-context 8B scheduled-brief lane
    - After 08:15: 'deterministic' fallback mode
    
    Returns:
        tuple (task_class, mode) where mode is 'llm' or 'deterministic'.
    """
    now = current_dt or datetime.now()
    current_time = now.time()

    if current_time >= DETERMINISTIC_FALLBACK_TIME:
        return "cassandra_morning_brief_fallback", "deterministic"
    
    if current_time >= ADAPTIVE_DOWNGRADE_TIME:
        # Use compact test-mode context while preserving the fixed resident 8B model.
        return "cassandra_morning_brief_test", "llm"
    
    return "cassandra_morning_brief", "llm"

def is_within_morning_window(current_dt: datetime | None = None) -> bool:
    now = current_dt or datetime.now()
    current_time = now.time()
    # 5:00 AM to 8:30 AM
    return time(5, 0) <= current_time <= EMERGENCY_OVERFLOW_TIME

def is_too_early_for_morning_delivery(current_dt: datetime | None = None) -> bool:
    """
    Returns True if it is currently before the TARGET_DELIVERY_TIME (08:00).
    Used to keep the morning brief in 'pending' state even if generated at 05:00.
    """
    now = current_dt or datetime.now()
    # If it's before 5 AM, it's also "early" but technically outside the morning window.
    # We only care about the gap between 5 AM and 8 AM.
    current_time = now.time()
    if current_time < TARGET_DELIVERY_TIME:
        return True
    return False

def sort_morning_chunks(chunks: list[dict]) -> list[dict]:
    """
    Sort a list of chunk dicts [{"header": "...", "body": "..."}] 
    according to MORNING_CHUNK_ORDER.
    """
    order_map = {header: i for i, header in enumerate(MORNING_CHUNK_ORDER)}
    # Use float('inf') for unknown headers so they go to the end
    return sorted(chunks, key=lambda c: order_map.get(c.get("header"), 99))
