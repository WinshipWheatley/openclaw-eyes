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
    # Other voice tests reload cassandra_voice in place. That legitimately
    # replaces its function objects, so object identity is not a wiring
    # contract. The scheduler's bound function must still execute against the
    # live Cassandra module globals and Cassandra's af_heart voice.
    assert fn.__module__ == cassandra_voice.__name__
    assert fn.__globals__ is vars(cassandra_voice)
    assert fn.__globals__["_KOKORO_VOICE"] == "af_heart"
    assert fn.__module__ != maestro_voice.speak_and_send_operator_brief_voice.__module__
