#!/usr/bin/env python3
"""Stub interpreter for master_voice.sh's PYV, used only by test_master_voice_shell.py.

Distinguishes which of the script's several python invocations this is by sniffing the
passed code (via -c or a script file argument), and either fakes a deterministic result
(kokoro synth -- forced failure to exercise the retry+fallback path; chunked-text-send --
faked "success" without a real network call) or delegates to the real system python for
invocations that are safe/necessary to run for real (the leak guard, voice resolution).
"""
import os
import subprocess
import sys

args = sys.argv[1:]


def _code_from_args(args):
    if args and args[0] == "-c" and len(args) >= 2:
        return args[1]
    if args:
        try:
            return open(args[-1], encoding="utf-8").read()
        except OSError:
            return ""
    return ""


code = _code_from_args(args)
FORCE_SYNTH_FAIL = os.environ.get("STUB_FORCE_SYNTH_FAIL") == "1"

if "KPipeline" in code:
    # Kokoro synth invocation (both the GPU attempt and the CUDA_VISIBLE_DEVICES= retry
    # use this same code). Controlled by STUB_FORCE_SYNTH_FAIL so tests can exercise
    # either the success path or the retry+fallback path deterministically.
    cuda = os.environ.get("CUDA_VISIBLE_DEVICES", "<unset>")
    sys.stderr.write(f"[stub] kokoro synth invoked, CUDA_VISIBLE_DEVICES={cuda!r}\n")
    marker_dir = os.environ.get("STUB_MARKER_DIR")
    if marker_dir:
        label = "cpu_retry" if cuda == "" else "gpu_attempt"
        open(os.path.join(marker_dir, f"synth_call_{label}"), "a").close()
    if FORCE_SYNTH_FAIL:
        sys.exit(3)
    # Simulated success: write a genuinely valid (tiny, silent) WAV so ffmpeg can actually
    # process it -- proving the real success path, not just a placeholder file existing.
    import wave

    wav_path = os.environ["WAV"]
    os.makedirs(os.path.dirname(wav_path), exist_ok=True)
    with wave.open(wav_path, "wb") as fh:
        fh.setnchannels(1)
        fh.setsampwidth(2)
        fh.setframerate(24000)
        fh.writeframes(b"\x00\x00" * 2400)  # 0.1s of silence
    sys.exit(0)
elif "urllib.request.urlopen" in code:
    # send_chunked_text: fake a successful Telegram sendMessage without a real network call.
    text = sys.stdin.read()
    marker_dir = os.environ.get("STUB_MARKER_DIR")
    if marker_dir:
        with open(os.path.join(marker_dir, "chunked_text_sent.txt"), "a", encoding="utf-8") as fh:
            fh.write(text + "\n---\n")
    print("text 1/1 ok: True | err: None")
    sys.exit(0)
else:
    # Leak guard / voice resolution / sendVoice-response parsing -- safe to run for real.
    result = subprocess.run(["python3", *args], input=None, capture_output=False)
    sys.exit(result.returncode)
