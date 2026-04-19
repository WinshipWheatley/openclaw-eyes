"""
cassandra_briefing_morning_policy.py

Time-aware orchestration policy for Cassandra's morning briefing.
Defines windows, deadlines, and model selection rules based on the clock.
"""

from datetime import datetime, time

# ── Policy Windows ────────────────────────────────────────────────────────────

TARGET_DELIVERY_TIME = time(8, 0)
ADAPTIVE_DOWNGRADE_TIME = time(7, 45)
DETERMINISTIC_FALLBACK_TIME = time(8, 15)
EMERGENCY_OVERFLOW_TIME = time(8, 30)

# ── Model Selection ────────────────────────────────────────────────────────────

def resolve_morning_model_lane(current_dt: datetime | None = None) -> tuple[str, str]:
    """
    Select the appropriate model and lane based on the current time.
    
    - Before 07:45: 'strong' lane (gemma4:26b)
    - 07:45 - 08:15: 'fast' lane (gemma4:e4b)
    - After 08:15: 'deterministic' fallback mode
    
    Returns:
        tuple (task_class, mode) where mode is 'llm' or 'deterministic'.
    """
    now = current_dt or datetime.now()
    current_time = now.time()

    if current_time >= DETERMINISTIC_FALLBACK_TIME:
        return "cassandra_morning_brief_fallback", "deterministic"
    
    if current_time >= ADAPTIVE_DOWNGRADE_TIME:
        # Use test-mode task class even in production to force gemma4:e4b / fast lane
        return "cassandra_morning_brief_test", "llm"
    
    return "cassandra_morning_brief", "llm"

def is_within_morning_window(current_dt: datetime | None = None) -> bool:
    now = current_dt or datetime.now()
    current_time = now.time()
    # 5:00 AM to 8:30 AM
    return time(5, 0) <= current_time <= EMERGENCY_OVERFLOW_TIME
