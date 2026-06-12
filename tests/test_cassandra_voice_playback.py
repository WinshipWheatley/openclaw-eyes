import importlib
import builtins
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import cassandra_voice
import harness_context


def _reload_voice():
    return importlib.reload(cassandra_voice)


def test_voice_failure_does_not_raise_from_speak(monkeypatch):
    voice = _reload_voice()
    voice._reset_voice_side_effect_state_for_tests()
    monkeypatch.setattr(voice, "VOICE_ENABLED", True)
    monkeypatch.setattr(voice, "is_focus_mode", lambda: False)
    monkeypatch.setattr(voice, "is_social_mode", lambda: False)
    monkeypatch.setattr(harness_context, "is_harness_mode", lambda: False)
    monkeypatch.setattr(voice, "_synthesize_live_lane", lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("boom")))

    class ImmediateThread:
        def __init__(self, target, args=(), daemon=False):
            self.target = target
            self.args = args

        def start(self):
            self.target(*self.args)

    monkeypatch.setattr(voice.threading, "Thread", ImmediateThread)

    voice.speak("hello from Cassandra")


def test_powershell_exec_failure_is_caught_and_classified(monkeypatch, tmp_path):
    voice = _reload_voice()
    voice._reset_voice_side_effect_state_for_tests()
    wav = tmp_path / "reply.wav"
    wav.write_bytes(b"RIFF")
    monkeypatch.setattr(voice, "ALLOW_WINDOWS_POWERSHELL_PLAYBACK", True)
    monkeypatch.setattr(voice, "_playback_commands", lambda _path: [])
    monkeypatch.setattr(voice.shutil, "which", lambda name: "/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe")
    monkeypatch.setattr(voice.Path, "exists", lambda self: True)

    def raise_exec_format(*_args, **_kwargs):
        raise OSError(8, "Exec format error", "/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe")

    monkeypatch.setattr(voice.subprocess, "run", raise_exec_format)
    ok, reason = voice._play_wav(r"C:\OpenClaw\logs\reply.wav", wav)

    assert ok is False
    assert "PowerShell" in str(reason)
    assert "Exec format error" in str(reason)
    assert voice._local_playback_cooldown_remaining() > 0


def test_voice_side_effect_log_cooldown_suppresses_spam(capsys):
    voice = _reload_voice()
    voice._reset_voice_side_effect_state_for_tests()

    assert voice._log_voice_side_effect("playback_degraded", "first", key="same") is True
    assert voice._log_voice_side_effect("playback_degraded", "second", key="same") is False

    out = capsys.readouterr().out
    assert out.count("VOICE_SIDE_EFFECT") == 1
    assert "first" in out
    assert "second" not in out


def test_local_only_mode_falls_back_to_piper_when_configured_for_plugin_backend(monkeypatch, tmp_path):
    voice = _reload_voice()
    voice._reset_voice_side_effect_state_for_tests()
    monkeypatch.setattr(voice, "VOICE_LOCAL_ONLY", True)
    monkeypatch.setattr(voice, "LIVE_BACKEND", "kokoro")
    monkeypatch.setattr(voice, "PREMIUM_BACKEND", "kokoro")

    calls = {"plugin": 0, "piper": 0}

    def plugin_called(*_args, **_kwargs):
        calls["plugin"] += 1
        return False

    def piper_called(_text, out_path):
        calls["piper"] += 1
        out_path.write_bytes(b"RIFF")

    monkeypatch.setattr(voice, "_synth_plugin", plugin_called)
    monkeypatch.setattr(voice, "_synth_piper", piper_called)

    assert voice._synthesize_live_lane("hello", tmp_path / "reply.wav") is True
    assert calls["plugin"] == 2
    assert calls["piper"] == 1


def test_synth_plugin_returns_false_in_local_only_without_importing_backend(monkeypatch, tmp_path):
    voice = _reload_voice()
    voice._reset_voice_side_effect_state_for_tests()
    monkeypatch.setattr(voice, "VOICE_LOCAL_ONLY", True)

    original_import = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        if name == "cassandra_tts_backends":
            raise AssertionError("backend import should be skipped")
        return original_import(name, *args, **kwargs)

    builtins.__import__ = guarded_import
    try:
        assert voice._synth_plugin("hello", "kokoro", tmp_path / "reply.wav") is False
    finally:
        builtins.__import__ = original_import


def test_voice_disabled_mode_returns_cleanly(monkeypatch):
    voice = _reload_voice()
    voice._reset_voice_side_effect_state_for_tests()
    monkeypatch.setattr(voice, "VOICE_ENABLED", False)

    class ForbiddenThread:
        def __init__(self, *_args, **_kwargs):
            raise AssertionError("voice disabled should not start worker")

    monkeypatch.setattr(voice.threading, "Thread", ForbiddenThread)

    voice.speak("hello")
    assert voice.synthesize_for_voice_note("hello") is None


def test_linux_playback_command_success_clears_failure(monkeypatch, tmp_path):
    voice = _reload_voice()
    voice._reset_voice_side_effect_state_for_tests()
    wav = tmp_path / "reply.wav"
    wav.write_bytes(b"RIFF")
    voice._mark_local_playback_failure()
    voice._clear_local_playback_failure()
    monkeypatch.setattr(voice, "_playback_commands", lambda path: [("paplay", ["/usr/bin/paplay", str(path)])])
    monkeypatch.setattr(
        voice.subprocess,
        "run",
        lambda *_args, **_kwargs: subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr=""),
    )

    ok, reason = voice._play_wav(r"C:\OpenClaw\logs\reply.wav", wav)

    assert ok is True
    assert reason is None
    assert voice._local_playback_cooldown_remaining() == 0.0
