"""Tests for master_voice.sh's text-only fallback (task 128).

Task 128 root cause (live incident 2026-07-07 ~17:05): a Kokoro CUDA OOM caused the script
to exit 3 BEFORE the Telegram send -- the operator's correction acknowledgment silently
never sent, twice. The 8b resident-model policy now reserves the GPU for Ollama: voice must
try the warm CPU service, fall back to one local CPU synth, and then send text rather than
ever exposing CUDA to Kokoro (words > silence, always).

Static assertions (the established convention for this file -- see
test_agent_voice_qa_regressions.py) cover structure; the dynamic tests below actually
EXECUTE the script with a stub PYV interpreter to prove the real bash control-flow (retry,
then fallback) works, not just that the right strings appear in the source.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "master_voice.sh"
STUB_PYV = Path(__file__).resolve().parent / "fixtures" / "stub_pyv.py"


def _run_master_voice(
    text: str,
    *,
    force_synth_fail: bool,
    tmp_path: Path,
    marker_dir: Path,
    warm_service_fail: bool = True,
) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env.update(
        {
            "PYV": str(STUB_PYV),
            "PYGUARD": "python3",
            "KOKORO_VOICE": "test_voice",  # skip the real voice-resolution python call
            "MAESTRO_BOT_TOKEN": "test-token",
            "TELEGRAM_AUTHORIZED_USER_ID": "12345",
            "OPENCLAW_SKIP_CHIEF_ENV": "1",
            "CURL_BIN": "true",
            # Isolated from the real, shared /mnt/c/OpenClaw/logs/master_voice.* path --
            # a live Telegram send could be using that file at any time.
            "WAV": str(tmp_path / "master_voice.wav"),
            "OGG": str(tmp_path / "master_voice.ogg"),
            "STUB_MARKER_DIR": str(marker_dir),
            "STUB_FORCE_SYNTH_FAIL": "1" if force_synth_fail else "0",
            "STUB_WARM_SERVICE_FAIL": "1" if warm_service_fail else "0",
        }
    )
    return subprocess.run(
        ["bash", str(SCRIPT)],
        input=text,
        text=True,
        capture_output=True,
        env=env,
        timeout=30,
    )


class TestMasterVoiceShellStatic:
    """Static structural checks, matching this file's established test convention."""

    def test_voice_synthesis_is_cpu_only(self) -> None:
        source = SCRIPT.read_text(encoding="utf-8")
        assert 'export CUDA_VISIBLE_DEVICES=""' in source
        assert "synthesize_remote" in source
        assert "SYNTH FAILED (GPU)" not in source

    def test_test_harness_can_isolate_secrets_and_network(self) -> None:
        source = SCRIPT.read_text(encoding="utf-8")
        assert "OPENCLAW_SKIP_CHIEF_ENV" in source
        assert 'CURL_BIN="${CURL_BIN:-curl}"' in source

    def test_text_only_fallback_never_silent(self) -> None:
        source = SCRIPT.read_text(encoding="utf-8")
        assert "send_text_only_fallback" in source
        assert "(voice unavailable)" in source
        assert "words > silence" in source or "text-only fallback" in source

    def test_status_line_present_in_every_delivery_path(self) -> None:
        source = SCRIPT.read_text(encoding="utf-8")
        assert "voice sent ok" in source
        assert "text sent ok" in source

    def test_provenance_leak_guard_and_chunking_preserved(self) -> None:
        source = SCRIPT.read_text(encoding="utf-8")
        assert "RELAY_LABEL" in source
        assert "REFUSED: master_voice received machine-contract content" in source
        assert 'cut=txt.rfind("\\n\\n",0,LIM)' in source

    def test_syntax_is_valid_bash(self) -> None:
        result = subprocess.run(["bash", "-n", str(SCRIPT)], capture_output=True, text=True)
        assert result.returncode == 0, result.stderr


class TestMasterVoiceShellDynamic:
    """Real execution against a stub PYV -- proves the actual control-flow, not just text."""

    def test_synth_success_delivers_voice_no_fallback(self, tmp_path: Path) -> None:
        marker_dir = tmp_path / "markers"
        marker_dir.mkdir()
        result = _run_master_voice(
            "Short acknowledgment.", force_synth_fail=False, tmp_path=tmp_path, marker_dir=marker_dir
        )

        assert (marker_dir / "warm_service_attempt").exists(), result.stdout + result.stderr
        assert (marker_dir / "synth_call_cpu_fallback").exists(), result.stdout + result.stderr
        assert not (marker_dir / "synth_call_gpu_attempt").exists(), "voice must never see CUDA"
        assert not (marker_dir / "chunked_text_sent.txt").exists(), "must not fall back to text when voice succeeds"
        assert "text sent ok" not in result.stdout

    def test_warm_cpu_service_success_avoids_local_model_load(self, tmp_path: Path) -> None:
        marker_dir = tmp_path / "markers"
        marker_dir.mkdir()
        result = _run_master_voice(
            "Short acknowledgment.",
            force_synth_fail=True,
            warm_service_fail=False,
            tmp_path=tmp_path,
            marker_dir=marker_dir,
        )

        assert (marker_dir / "warm_service_attempt").exists(), result.stdout + result.stderr
        assert not (marker_dir / "synth_call_cpu_fallback").exists(), "warm service should avoid a second model load"
        assert not (marker_dir / "synth_call_gpu_attempt").exists(), "voice must never see CUDA"
        assert "text sent ok" not in result.stdout

    def test_synth_failure_retries_cpu_then_falls_back_to_text(self, tmp_path: Path) -> None:
        marker_dir = tmp_path / "markers"
        marker_dir.mkdir()
        text = "Got it — St Anne's now bills on the 15th."
        result = _run_master_voice(text, force_synth_fail=True, tmp_path=tmp_path, marker_dir=marker_dir)

        assert result.returncode == 0, "the operator still got the message -- this is a success, not a failure"
        assert (marker_dir / "warm_service_attempt").exists(), result.stdout + result.stderr
        assert (marker_dir / "synth_call_cpu_fallback").exists(), "must fall back to one local CPU synth"
        assert not (marker_dir / "synth_call_gpu_attempt").exists(), "voice must never see CUDA"
        assert "WARM KOKORO SERVICE UNAVAILABLE" in result.stderr
        assert "text sent ok: true" in result.stdout

        sent_path = marker_dir / "chunked_text_sent.txt"
        assert sent_path.exists(), "the text must actually be delivered, not just logged"
        sent_text = sent_path.read_text(encoding="utf-8")
        assert text in sent_text
        assert "(voice unavailable)" in sent_text

    def test_machine_contract_still_refused_before_any_synth_attempt(self, tmp_path: Path) -> None:
        marker_dir = tmp_path / "markers"
        marker_dir.mkdir()
        result = _run_master_voice(
            '{"status": "ok", "request_id": "abc"}', force_synth_fail=True, tmp_path=tmp_path, marker_dir=marker_dir
        )

        assert result.returncode == 6
        assert "REFUSED" in result.stderr
        assert not (marker_dir / "warm_service_attempt").exists(), "leak guard must fire before any synth attempt"
        assert not (marker_dir / "synth_call_cpu_fallback").exists(), "leak guard must fire before any synth attempt"
