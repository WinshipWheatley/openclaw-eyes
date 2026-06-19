import importlib
from pathlib import Path

import agent_kokoro_voice
import cassandra_voice
import maestro_voice


def test_all_agent_kokoro_voice_assignments_are_distinct_and_non_piper():
    assert agent_kokoro_voice.AGENT_KOKORO_VOICES == {
        "maestro": "am_michael",
        "cassandra": "af_heart",
        "chief": "bm_george",
        "guardian": "am_onyx",
        "niles": "am_puck",
        "hermes": "am_echo",
    }
    assert len(set(agent_kokoro_voice.AGENT_KOKORO_VOICES.values())) == 6
    assert all("piper" not in voice for voice in agent_kokoro_voice.AGENT_KOKORO_VOICES.values())


def test_shared_kokoro_synth_uses_each_agent_voice_and_24khz(monkeypatch, tmp_path):
    calls = []

    class FakePipeline:
        def __call__(self, text, *, voice, speed):
            calls.append({"text": text, "voice": voice, "speed": speed})
            yield None, None, object()

    monkeypatch.setattr(agent_kokoro_voice, "_load_pipeline", lambda lang: FakePipeline())
    monkeypatch.setattr(agent_kokoro_voice, "_combine_audio_chunks", lambda chunks: list(chunks))

    writes = []

    def fake_write(path: Path, audio, sample_rate: int) -> None:
        writes.append({"path": path, "audio": audio, "sample_rate": sample_rate})
        path.write_bytes(b"RIFF")

    monkeypatch.setattr(agent_kokoro_voice, "_write_wav", fake_write)
    for agent, voice in agent_kokoro_voice.AGENT_KOKORO_VOICES.items():
        out = tmp_path / f"{agent}.wav"
        assert agent_kokoro_voice.synth_kokoro_wav(" hello   there ", voice, out, speed=1.05) is True
        assert out.read_bytes() == b"RIFF"

    assert [call["voice"] for call in calls] == list(agent_kokoro_voice.AGENT_KOKORO_VOICES.values())
    assert all(call["text"] == "hello there" for call in calls)
    assert all(call["speed"] == 1.05 for call in calls)
    assert [write["sample_rate"] for write in writes] == [24000] * 6


def test_cassandra_defaults_to_kokoro_af_heart(monkeypatch):
    monkeypatch.delenv("CASSANDRA_LIVE_BACKEND", raising=False)
    monkeypatch.delenv("CASSANDRA_KOKORO_VOICE", raising=False)
    voice = importlib.reload(cassandra_voice)

    assert voice.LIVE_BACKEND == "kokoro"
    assert voice._KOKORO_VOICE == "af_heart"
    assert voice.LIVE_BACKEND != "piper"


def test_cassandra_kokoro_backend_uses_shared_helper(monkeypatch, tmp_path):
    voice = importlib.reload(cassandra_voice)
    calls = []

    def fake_kokoro(text, selected_voice, wav_path, *, speed):
        calls.append((text, selected_voice, wav_path, speed))
        wav_path.write_bytes(b"RIFF")
        return True

    monkeypatch.setattr(voice, "synth_kokoro_wav", fake_kokoro)
    out = tmp_path / "cassandra.wav"

    assert voice._synth_plugin("hello", "kokoro", out) is True
    assert calls == [("hello", "af_heart", out, 0.9)]


def test_cassandra_forced_kokoro_failure_logs_piper_fallback(monkeypatch, tmp_path, capsys):
    voice = importlib.reload(cassandra_voice)
    voice._reset_voice_side_effect_state_for_tests()
    monkeypatch.setattr(voice, "PREMIUM_BACKEND", "")
    monkeypatch.setattr(voice, "LIVE_BACKEND", "kokoro")
    monkeypatch.setattr(voice, "_synth_plugin", lambda *_args, **_kwargs: False)

    piper_calls = []

    def fake_piper(_text, wav_path):
        piper_calls.append(wav_path)
        wav_path.write_bytes(b"RIFF")

    monkeypatch.setattr(voice, "_synth_piper", fake_piper)
    out = tmp_path / "fallback.wav"

    assert voice._synthesize_live_lane("hello", out) is True
    assert piper_calls == [out]
    captured = capsys.readouterr().out
    assert "live fallback -> Piper" in captured
    assert "tts_backend_fallback" in captured


def test_maestro_defaults_to_kokoro_am_michael(monkeypatch, tmp_path):
    voice = importlib.reload(maestro_voice)
    calls = []

    def fake_kokoro(text, selected_voice, wav_path, *, speed):
        calls.append((text, selected_voice, wav_path, speed))
        wav_path.write_bytes(b"RIFF")
        return True

    monkeypatch.setattr(voice, "synth_kokoro_wav", fake_kokoro)

    assert voice.synth_maestro_wav("brief", tmp_path / "maestro.wav") is True
    assert calls == [("brief", "am_michael", tmp_path / "maestro.wav", 1.0)]


def test_maestro_forced_kokoro_failure_logs_piper_fallback(monkeypatch, tmp_path, capsys):
    voice = importlib.reload(maestro_voice)
    monkeypatch.setattr(voice, "synth_kokoro_wav", lambda *_args, **_kwargs: False)
    piper_calls = []

    def fake_piper(text, wav_path):
        piper_calls.append((text, wav_path))
        wav_path.write_bytes(b"RIFF")
        return True

    monkeypatch.setattr(voice, "_synth_maestro_piper_wav", fake_piper)

    assert voice.synth_maestro_wav("brief", tmp_path / "maestro-fallback.wav") is True
    assert piper_calls == [("brief", tmp_path / "maestro-fallback.wav")]
    assert "Kokoro returned no audio; fallback -> Piper" in capsys.readouterr().out
