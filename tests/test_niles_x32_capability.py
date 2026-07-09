"""Niles X32 lane capability — deterministic intake routing (trust-tier-1).

The capability must: route X32/show-prep asks to the salvaged X32 slice
(showprofile / scene_corpus / topology grounding), stay file-and-planning only
(hardware gated: no sockets unless explicitly allowed), fail open into the
legacy producer template path, and never steal ordinary production questions.
"""

from pathlib import Path

import niles_x32_capability as cap
from x32_fake import X32Fake


INPUT_LIST_TEXT = """Here's the input list for Saturday:
1. Kick
2. Snare Top
3. Bass DI
4. Gtr Amp L
5. Lead Vox
"""


def test_detect_setup_intent():
    assert cap.detect_x32_intent("Set up the X32 flow for the show") == "x32_setup"
    assert cap.detect_x32_intent("prep the desk for soundcheck") == "x32_setup"


def test_detect_show_profile_intent_from_input_list():
    assert cap.detect_x32_intent(INPUT_LIST_TEXT) == "show_profile"
    assert cap.detect_x32_intent("build the show profile from the stage plot") == "show_profile"


def test_detect_scene_corpus_and_status():
    assert cap.detect_x32_intent("analyze the scene corpus") == "scene_corpus"
    assert cap.detect_x32_intent("is the X32 connected?") == "x32_status"


def test_rig_knowledge_question_routes_to_kb_not_generic_setup():
    assert cap.detect_x32_intent("what channel is the DL16 stagebox on?") == "rig_knowledge"
    result = cap.maybe_handle_x32("what channel is the DL16 stagebox on?")
    assert result is not None and result["handled"] is True
    assert result["intent"] == "rig_knowledge"
    assert result["hardware_gated"] is True
    reply = result["reply"].lower()
    assert "rig kb" in reply
    assert "stage" in reply or "aes50" in reply
    assert "x32 flow" not in reply


def test_unknown_rig_fact_is_honest_not_fabricated():
    result = cap.maybe_handle_x32("what patch is the fog machine on?")
    assert result is not None and result["handled"] is True
    assert result["intent"] == "rig_knowledge"
    reply = result["reply"].lower()
    assert "i don't have that in the rig kb" in reply
    assert "fog machine is on" not in reply


def test_ordinary_production_questions_are_not_stolen():
    assert cap.detect_x32_intent("the chorus is boring but spacious, help") is None
    assert cap.detect_x32_intent("make this hit harder in logic") is None
    assert cap.detect_x32_intent("I'm ready to record vocals") is None


def test_money_question_never_classifies_rig_knowledge():
    """Task 149 root cause #1: bare 'rig' substring-matched inside 'right' ('who owes me
    money RIGht now?'), shadowing the money branch before it ever got a chance."""
    assert cap.detect_x32_intent("who owes me money right now?") is None
    assert cap.detect_x32_intent("is everything all right with the mix?") is None
    assert cap.detect_x32_intent("that sounds right to me") is None


def test_word_boundary_marker_matching_does_not_false_positive_on_substrings():
    """Task 149: word-boundary fix generalized across detect_x32_intent's marker sets,
    not just _RIG_KB_MARKERS -- 'patch' inside 'dispatch', 'reach' inside 'reachable'."""
    assert cap._marker_matches(" dispatch the task ", ("patch",)) is False
    assert cap._marker_matches(" the mixer is unreachable ", ("reach",)) is False
    assert cap._marker_matches(" patch the cable ", ("patch",)) is True
    assert cap._marker_matches(" is it reachable ", ("reach", "reachable")) is True


def test_show_profile_and_setup_intents_still_match_with_word_boundaries():
    """Acceptance: the fix must not regress the legitimate matches."""
    assert cap.detect_x32_intent("here's the input list for the show") == "show_profile"
    assert cap.detect_x32_intent("prep the desk for soundcheck") == "x32_setup"
    assert cap.detect_x32_intent("what channel is the DL16 stagebox on?") == "rig_knowledge"


def test_show_profile_builds_scene_artifact(tmp_path: Path):
    result = cap.maybe_handle_x32(INPUT_LIST_TEXT, show_profile_dir=tmp_path)
    assert result is not None and result["handled"] is True
    assert result["intent"] == "show_profile"
    assert result["artifacts"], "expected a generated .scn artifact"
    scn = Path(result["artifacts"][0])
    assert scn.exists() and scn.suffix == ".scn"
    content = scn.read_text(encoding="utf-8")
    assert "Kick" in content and "Lead Vox" in content
    assert "Kick" in result["reply"] or "5" in result["reply"]
    assert result["hardware_gated"] is True


def test_show_profile_without_list_asks_for_it(tmp_path: Path):
    result = cap.maybe_handle_x32("build me a show profile", show_profile_dir=tmp_path)
    assert result["handled"] is True
    assert not result["artifacts"]
    assert "input list" in result["reply"].lower()


def test_setup_reply_grounded_and_gated():
    called = {"n": 0}

    def forbidden_factory(*a, **k):
        called["n"] += 1
        raise AssertionError("controller must not be constructed at tier-1")

    result = cap.maybe_handle_x32(
        "set up the X32 flow", controller_factory=forbidden_factory
    )
    assert result["handled"] is True
    assert result["hardware_gated"] is True
    assert "10023" in result["reply"]
    assert called["n"] == 0


def test_status_is_honestly_gated_without_network():
    result = cap.maybe_handle_x32("is the x32 connected?")
    assert result["handled"] is True
    assert result["hardware_gated"] is True
    assert "emulator" in result["reply"].lower() or "gated" in result["reply"].lower()


def test_fuzzy_live_mix_fader_move_hits_emulator_and_returns_proof():
    fake = X32Fake().start()
    try:
        result = cap.maybe_handle_x32(
            "bring up channel 3 a bit",
            emulator_endpoint=(fake.host, fake.port),
        )

        assert result is not None and result["handled"] is True
        assert result["intent"] == "live_mix"
        assert result["target"] == "emulator"
        assert result["hardware_gated"] is True
        assert result["live_hardware_control_allowed"] is False
        assert result["osc_messages"] == [
            {"address": "/ch/03/mix/fader", "args": [result["proof"]["osc_value"]]}
        ]
        assert fake.state["/ch/03/mix/fader"] == [result["proof"]["osc_value"]]
        assert result["proof"]["channel"] == 3
        assert result["proof"]["fader_db"] == -6.0
        assert "channel 3 fader now at -6 db" in result["reply"].lower()
    finally:
        fake.stop()


def test_fuzzy_live_mix_mute_named_source_hits_emulator_and_returns_proof():
    fake = X32Fake().start()
    try:
        result = cap.maybe_handle_x32(
            "mute the kick",
            emulator_endpoint=(fake.host, fake.port),
        )

        assert result is not None and result["handled"] is True
        assert result["intent"] == "live_mix"
        assert fake.state["/ch/01/mix/on"] == [0]
        assert result["proof"] == {
            "action": "mute",
            "channel": 1,
            "label": "kick",
            "muted": True,
            "osc_value": 0,
        }
        assert "kick muted" in result["reply"].lower()
    finally:
        fake.stop()


def test_live_mix_eq_and_comp_moves_hit_emulator_with_proof():
    fake = X32Fake().start()
    try:
        eq = cap.maybe_handle_x32(
            "add 2 db high eq on channel 3",
            emulator_endpoint=(fake.host, fake.port),
        )
        comp = cap.maybe_handle_x32(
            "set channel 3 comp threshold to -18 db",
            emulator_endpoint=(fake.host, fake.port),
        )

        assert eq["intent"] == "live_mix"
        assert fake.state["/ch/03/eq/4/g"] == [2.0]
        assert eq["proof"] == {
            "action": "eq",
            "band": "high",
            "channel": 3,
            "gain_db": 2.0,
            "label": "channel 3",
            "osc_value": 2.0,
        }
        assert "channel 3 high eq now at 2 db" in eq["reply"].lower()

        assert comp["intent"] == "live_mix"
        assert fake.state["/ch/03/dyn/thr"] == [-18.0]
        assert comp["proof"] == {
            "action": "comp",
            "channel": 3,
            "label": "channel 3",
            "threshold_db": -18.0,
            "osc_value": -18.0,
        }
        assert "channel 3 comp threshold now at -18 db" in comp["reply"].lower()
    finally:
        fake.stop()


def test_live_mix_real_console_path_refused_without_emulator():
    result = cap.maybe_handle_x32(
        "set channel 3 fader to -6 dB",
        emulator_endpoint=None,
        live_hardware_control_allowed=False,
    )

    assert result is not None and result["handled"] is True
    assert result["intent"] == "live_mix"
    assert result["target"] == "real_console_refused"
    assert result["hardware_gated"] is True
    assert result["live_hardware_control_allowed"] is False
    assert result["osc_messages"] == []
    assert "real x32 hardware control is still gated" in result["reply"].lower()


def test_live_mix_non_loopback_endpoint_refused_as_real_console():
    result = cap.maybe_handle_x32(
        "set channel 3 fader to -6 dB",
        emulator_endpoint=("192.0.2.10", 10023),
        live_hardware_control_allowed=False,
    )

    assert result is not None and result["handled"] is True
    assert result["intent"] == "live_mix"
    assert result["target"] == "real_console_refused"
    assert result["hardware_gated"] is True
    assert result["osc_messages"] == []
    assert "emulator endpoint must be loopback" in result["reply"].lower()


def test_scene_corpus_honest_when_missing(tmp_path: Path):
    result = cap.maybe_handle_x32(
        "analyze the scene corpus", scene_corpus_dir=tmp_path / "nope"
    )
    assert result["handled"] is True
    assert "no scene" in result["reply"].lower() or "not found" in result["reply"].lower()


def test_maybe_handle_never_raises(monkeypatch):
    monkeypatch.setattr(cap, "detect_x32_intent", lambda text: (_ for _ in ()).throw(RuntimeError("boom")))
    assert cap.maybe_handle_x32("set up the x32") is None


def test_producer_intake_routes_x32_and_preserves_legacy(tmp_path: Path, monkeypatch, capsys):
    import sys
    monkeypatch.setattr(sys, "argv", ["producer_intake.py", "--text", "Set up the X32 flow", "--human-only"])
    monkeypatch.setenv("NILES_SHOW_PROFILE_DIR", str(tmp_path))
    import importlib
    import scripts.producer_intake as intake
    importlib.reload(intake)
    intake.main()
    out = capsys.readouterr().out
    assert "10023" in out

    monkeypatch.setattr(sys, "argv", ["producer_intake.py", "--text", "the chorus is boring but spacious", "--human-only"])
    intake.main()
    out = capsys.readouterr().out
    assert "arrival point" in out  # legacy template answer preserved
