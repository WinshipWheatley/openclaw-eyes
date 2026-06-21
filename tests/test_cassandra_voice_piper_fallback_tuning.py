"""Tests that Cassandra Piper fallback tuning constants hold their conservative clarity values."""
import importlib
import sys
import types


def _load_cassandra_voice_constants(monkeypatch):
    """Load cassandra_voice with all heavy imports stubbed out."""
    stub_names = [
        "chief_env",
        "chief_output_utils",
        "cassandra_mode",
        "hermes_gateway",
        "agent_kokoro_voice",
        "harness_context",
    ]
    for name in stub_names:
        if name not in sys.modules:
            monkeypatch.setitem(sys.modules, name, types.ModuleType(name))

    # Stub chief_output_utils.tts_clean
    sys.modules["chief_output_utils"].tts_clean = lambda t: t  # type: ignore[attr-defined]
    # Stub cassandra_mode booleans
    for fn in ("is_focus_mode", "is_social_mode", "is_live_mode", "is_batch_mode"):
        setattr(sys.modules["cassandra_mode"], fn, lambda: False)
    # Stub agent_kokoro_voice
    sys.modules["agent_kokoro_voice"].voice_for_agent = lambda _: "af_heart"  # type: ignore[attr-defined]
    sys.modules["agent_kokoro_voice"].synth_kokoro_wav = lambda *a, **kw: False  # type: ignore[attr-defined]
    # Stub hermes_gateway
    sys.modules["hermes_gateway"].hermes_gate = lambda *a, **kw: None  # type: ignore[attr-defined]
    # Stub harness_context
    sys.modules["harness_context"].is_harness_mode = lambda: False  # type: ignore[attr-defined]

    if "cassandra_voice" in sys.modules:
        del sys.modules["cassandra_voice"]
    import cassandra_voice as cv
    return cv


def test_length_scale_is_1_12(monkeypatch):
    cv = _load_cassandra_voice_constants(monkeypatch)
    assert cv.LENGTH_SCALE == 1.12, f"Expected 1.12, got {cv.LENGTH_SCALE}"


def test_noise_scale_is_0_55(monkeypatch):
    cv = _load_cassandra_voice_constants(monkeypatch)
    assert cv.NOISE_SCALE == 0.55, f"Expected 0.55, got {cv.NOISE_SCALE}"


def test_noise_w_unchanged_at_0_8(monkeypatch):
    cv = _load_cassandra_voice_constants(monkeypatch)
    assert cv.NOISE_W == 0.8, f"Expected 0.8, got {cv.NOISE_W}"


def test_env_override_still_respected(monkeypatch):
    monkeypatch.setenv("CASSANDRA_VOICE_LENGTH_SCALE", "1.0")
    monkeypatch.setenv("CASSANDRA_VOICE_NOISE_SCALE", "0.4")
    monkeypatch.setenv("CASSANDRA_VOICE_NOISE_W", "0.7")
    cv = _load_cassandra_voice_constants(monkeypatch)
    assert cv.LENGTH_SCALE == 1.0
    assert cv.NOISE_SCALE == 0.4
    assert cv.NOISE_W == 0.7
