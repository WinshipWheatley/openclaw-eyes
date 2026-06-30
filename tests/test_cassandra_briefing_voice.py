"""Regression guard: Cassandra's scheduled briefs must speak in HER voice (af_heart),
not Maestro's (am_michael). The scheduler had been pointed at the maestro_voice drop-in,
so her midday brief came through sounding like Maestro."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def test_briefing_scheduler_uses_cassandra_voice_not_maestro():
    import cassandra_briefing_scheduler as sched
    import cassandra_voice
    import maestro_voice

    fn = sched.speak_and_send_operator_brief_voice
    assert fn is cassandra_voice.speak_and_send_operator_brief_voice, (
        "Cassandra's brief must use cassandra_voice (af_heart), not a borrowed voice"
    )
    assert fn is not maestro_voice.speak_and_send_operator_brief_voice, (
        "regression: brief is wired to Maestro's voice (am_michael)"
    )
