from __future__ import annotations

import sys
from pathlib import Path
import threading

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import kokoro_voice_service as svc  # noqa: E402


def _fake_synth_ok(agent, text, wav_path):
    Path(wav_path).write_bytes(b"RIFFfakewav")
    return True, wav_path


def _fake_synth_fail(agent, text, wav_path):
    return False, wav_path


def _fake_convert_ok(wav_path):
    ogg = wav_path.rsplit(".", 1)[0] + ".ogg"
    Path(ogg).write_bytes(b"OggSfake")
    return ogg


def _fake_convert_missing(wav_path):
    return None  # ffmpeg not available


def test_happy_path_returns_ogg(tmp_path):
    out = svc.build_voice_audio("hermes", "hello", synth_fn=_fake_synth_ok,
                                convert_fn=_fake_convert_ok, out_dir=tmp_path)
    assert out["ok"] is True and out["format"] == "ogg"
    assert out["ogg"].endswith(".ogg") and Path(out["ogg"]).is_file()


def test_synth_failure_is_reported_not_raised(tmp_path):
    out = svc.build_voice_audio("hermes", "hello", synth_fn=_fake_synth_fail,
                                convert_fn=_fake_convert_ok, out_dir=tmp_path)
    assert out["ok"] is False and out["error"] == "synth_failed"


def test_missing_ffmpeg_falls_back_to_wav(tmp_path):
    # No ffmpeg -> still deliver the wav rather than nothing.
    out = svc.build_voice_audio("hermes", "hello", synth_fn=_fake_synth_ok,
                                convert_fn=_fake_convert_missing, out_dir=tmp_path)
    assert out["ok"] is True and out["format"] == "wav"
    assert out["ogg"] is None and Path(out["wav"]).is_file()


def test_empty_text_is_rejected(tmp_path):
    out = svc.build_voice_audio("hermes", "   ", synth_fn=_fake_synth_ok,
                                convert_fn=_fake_convert_ok, out_dir=tmp_path)
    assert out["ok"] is False


def test_guarded_synthesis_rejects_a_second_request_instead_of_queueing(tmp_path):
    lock = threading.Lock()
    lock.acquire()
    try:
        out = svc.build_voice_audio_guarded(
            "hermes",
            "hello",
            synth_fn=_fake_synth_ok,
            convert_fn=_fake_convert_ok,
            out_dir=tmp_path,
            request_lock=lock,
        )
    finally:
        lock.release()

    assert out == {"ok": False, "error": "busy"}
    assert list(tmp_path.iterdir()) == []


def test_guarded_synthesis_releases_its_slot_after_completion(tmp_path):
    lock = threading.Lock()

    out = svc.build_voice_audio_guarded(
        "hermes",
        "hello",
        synth_fn=_fake_synth_ok,
        convert_fn=_fake_convert_ok,
        out_dir=tmp_path,
        request_lock=lock,
    )

    assert out["ok"] is True
    assert lock.acquire(blocking=False) is True
    lock.release()


def test_cleanup_result_audio_removes_only_generated_paths(tmp_path):
    wav = tmp_path / "voice.wav"
    ogg = tmp_path / "voice.ogg"
    wav.write_bytes(b"RIFF")
    ogg.write_bytes(b"OggS")

    svc.cleanup_result_audio({"ok": True, "wav": str(wav), "ogg": str(ogg)})

    assert not wav.exists()
    assert not ogg.exists()
