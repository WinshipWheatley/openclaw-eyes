"""Tests for [VOICE_METRIC] structured log emission from synthesis paths."""
import io
import sys
import types
import wave
from pathlib import Path
from unittest.mock import MagicMock


# ── Module-load helpers ───────────────────────────────────────────────────────

def _stub_cassandra_voice_deps(monkeypatch):
    stubs = {
        "chief_env": types.ModuleType("chief_env"),
        "chief_output_utils": types.ModuleType("chief_output_utils"),
        "cassandra_mode": types.ModuleType("cassandra_mode"),
        "hermes_gateway": types.ModuleType("hermes_gateway"),
        "agent_kokoro_voice": types.ModuleType("agent_kokoro_voice"),
        "harness_context": types.ModuleType("harness_context"),
    }
    stubs["chief_output_utils"].tts_clean = lambda t: t  # type: ignore[attr-defined]
    for fn in ("is_focus_mode", "is_social_mode", "is_live_mode", "is_batch_mode"):
        setattr(stubs["cassandra_mode"], fn, lambda: False)
    stubs["agent_kokoro_voice"].voice_for_agent = lambda _: "af_heart"  # type: ignore[attr-defined]
    stubs["agent_kokoro_voice"].synth_kokoro_wav = lambda *a, **kw: False  # type: ignore[attr-defined]
    stubs["hermes_gateway"].hermes_gate = lambda *a, **kw: None  # type: ignore[attr-defined]
    stubs["harness_context"].is_harness_mode = lambda: False  # type: ignore[attr-defined]
    for name, mod in stubs.items():
        if name not in sys.modules:
            monkeypatch.setitem(sys.modules, name, mod)
    return stubs


def _load_cv(monkeypatch):
    _stub_cassandra_voice_deps(monkeypatch)
    if "cassandra_voice" in sys.modules:
        del sys.modules["cassandra_voice"]
    import cassandra_voice
    return cassandra_voice


def _minimal_wav_bytes() -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(22050)
        wf.writeframes(b"\x00\x00" * 100)
    return buf.getvalue()


# ── Fake Piper pieces ─────────────────────────────────────────────────────────

class _FakeChunk:
    sample_channels = 1
    sample_width = 2
    sample_rate = 22050
    audio_int16_bytes = b"\x00\x00" * 50


class _FakePiperVoice:
    def synthesize(self, text, cfg):
        yield _FakeChunk()


class _EmptyPiperVoice:
    def synthesize(self, text, cfg):
        return iter([])


def _patch_piper_config(monkeypatch):
    piper_pkg = types.ModuleType("piper")
    piper_cfg = types.ModuleType("piper.config")
    piper_cfg.SynthesisConfig = MagicMock(return_value=MagicMock())  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "piper", piper_pkg)
    monkeypatch.setitem(sys.modules, "piper.config", piper_cfg)


# ── _synth_piper tests ────────────────────────────────────────────────────────

def test_synth_piper_emits_voice_metric(monkeypatch, tmp_path, capsys):
    cv = _load_cv(monkeypatch)
    _patch_piper_config(monkeypatch)
    monkeypatch.setattr(cv, "_load_piper_voice", lambda: _FakePiperVoice())
    wav = tmp_path / "out.wav"
    cv._synth_piper("hello world", wav)
    out = capsys.readouterr().out
    assert "[VOICE_METRIC]" in out
    assert "backend=piper" in out
    assert "latency_ms=" in out
    assert "audio_chars=11" in out
    assert "wav_bytes=" in out


def test_synth_piper_empty_chunks_logs_metric(monkeypatch, tmp_path, capsys):
    cv = _load_cv(monkeypatch)
    _patch_piper_config(monkeypatch)
    monkeypatch.setattr(cv, "_load_piper_voice", lambda: _EmptyPiperVoice())
    wav = tmp_path / "out.wav"
    cv._synth_piper("test", wav)
    out = capsys.readouterr().out
    assert "[VOICE_METRIC]" in out
    assert "result=empty_chunks" in out


# ── _synth_plugin tests ───────────────────────────────────────────────────────

def test_synth_plugin_kokoro_ok_emits_metric(monkeypatch, tmp_path, capsys):
    cv = _load_cv(monkeypatch)
    wav = tmp_path / "out.wav"

    def _fake_synth(text, voice, path, speed=1.0):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(_minimal_wav_bytes())
        return True

    monkeypatch.setattr(cv, "synth_kokoro_wav", _fake_synth)
    result = cv._synth_plugin("hi there", "kokoro", wav)
    out = capsys.readouterr().out
    assert result is True
    assert "[VOICE_METRIC]" in out
    assert "backend=kokoro" in out
    assert "latency_ms=" in out
    assert "audio_chars=8" in out
    assert "result=ok" in out


def test_synth_plugin_failed_emits_metric(monkeypatch, tmp_path, capsys):
    cv = _load_cv(monkeypatch)
    wav = tmp_path / "out.wav"
    monkeypatch.setattr(cv, "synth_kokoro_wav", lambda *a, **kw: False)
    result = cv._synth_plugin("hello", "kokoro", wav)
    out = capsys.readouterr().out
    assert result is False
    assert "[VOICE_METRIC]" in out
    assert "result=failed" in out


def test_synth_plugin_emits_exactly_one_metric_per_call(monkeypatch, tmp_path, capsys):
    cv = _load_cv(monkeypatch)
    wav = tmp_path / "out.wav"
    monkeypatch.setattr(cv, "synth_kokoro_wav", lambda *a, **kw: False)
    cv._synth_plugin("one two three", "kokoro", wav)
    out = capsys.readouterr().out
    assert out.count("[VOICE_METRIC]") == 1


# ── KokoroBackend chunk tracking ─────────────────────────────────────────────

class _FakeArray:
    """Minimal numpy array stub."""
    def __init__(self, data):
        self._data = list(data)

    def __len__(self):
        return len(self._data)

    def astype(self, dtype):
        return self


def _make_stub_numpy():
    np_stub = types.ModuleType("numpy")
    np_stub.float32 = float  # type: ignore[attr-defined]

    def _concatenate(arrays):
        combined = []
        for a in arrays:
            combined.extend(a._data)
        return _FakeArray(combined)

    def _zeros(n, dtype=None):
        return _FakeArray([0.0] * n)

    np_stub.concatenate = _concatenate  # type: ignore[attr-defined]
    np_stub.zeros = _zeros  # type: ignore[attr-defined]
    return np_stub


def _load_kokoro_backend(monkeypatch):
    stub_np = _make_stub_numpy()
    stub_sf = types.ModuleType("soundfile")
    stub_sf.write = MagicMock()  # type: ignore[attr-defined]
    stub_kokoro = types.ModuleType("kokoro")
    monkeypatch.setitem(sys.modules, "numpy", stub_np)
    monkeypatch.setitem(sys.modules, "soundfile", stub_sf)
    monkeypatch.setitem(sys.modules, "kokoro", stub_kokoro)
    if "cassandra_tts_backends" in sys.modules:
        del sys.modules["cassandra_tts_backends"]
    import cassandra_tts_backends as ctb
    return ctb, stub_np, stub_sf


def test_kokoro_backend_logs_metric_on_success(monkeypatch, tmp_path, capsys):
    ctb, stub_np, _ = _load_kokoro_backend(monkeypatch)

    class _FakePipeline:
        def __call__(self, text, voice, speed):
            yield None, None, stub_np.zeros(100)
            yield None, None, stub_np.zeros(200)

    b = ctb.KokoroBackend()
    b.__class__._pipeline = _FakePipeline()
    result = b.synthesize("hello", tmp_path / "out.wav")
    out = capsys.readouterr().out
    assert result is True
    assert "[VOICE_METRIC]" in out
    assert "backend=kokoro_backend" in out
    assert "chunks=2" in out
    assert "audio_samples=300" in out


def test_kokoro_backend_logs_empty_chunks(monkeypatch, tmp_path, capsys):
    ctb, _, _ = _load_kokoro_backend(monkeypatch)

    class _EmptyPipeline:
        def __call__(self, text, voice, speed):
            return iter([])

    b = ctb.KokoroBackend()
    b.__class__._pipeline = _EmptyPipeline()
    result = b.synthesize("empty", tmp_path / "out.wav")
    out = capsys.readouterr().out
    assert result is False
    assert "[VOICE_METRIC]" in out
    assert "result=empty_chunks" in out
