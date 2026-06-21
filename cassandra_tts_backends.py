"""
cassandra_tts_backends.py

Pluggable TTS backends for Cassandra evaluation.
NOT the production path — Piper in cassandra_voice.py remains the production default.

Backends
--------
  qwen3   — Qwen3-TTS-0.6B via HuggingFace transformers  (CPU, ~1.5–2 GB RAM)
  kokoro  — Kokoro-82M via kokoro Python package           (CPU, ~300–400 MB RAM)

Install
-------
  # Shared
  pip install soundfile numpy

  # Qwen3-TTS (heavy — downloads ~1.2 GB model on first run)
  pip install transformers torch accelerate

  # Kokoro (lightweight — downloads ~300 MB on first run)
  pip install kokoro

Environment overrides
---------------------
  CASSANDRA_QWEN3_MODEL   default: Qwen/Qwen3-TTS-0.6B
  CASSANDRA_KOKORO_VOICE  default: af_heart   (warm female; try af_sky, am_adam)
  CASSANDRA_KOKORO_SPEED  default: 0.9        (slightly slower = more Cassandra)
  CASSANDRA_KOKORO_LANG   default: a          ('a' = American English)
"""

import os
import threading
from pathlib import Path

import numpy as np

# ── Qwen3-TTS-0.6B ────────────────────────────────────────────────────────────

_QWEN3_MODEL = os.environ.get("CASSANDRA_QWEN3_MODEL", "Qwen/Qwen3-TTS-0.6B")


# ── HuggingFace auth ───────────────────────────────────────────────────────────

def _login_hf() -> None:
    """Log in to HuggingFace Hub if HF_TOKEN is set in the environment.

    Authenticated requests avoid anonymous rate limits on model downloads.
    Silently skips if token is absent or huggingface_hub is not installed.
    """
    token = os.environ.get("HF_TOKEN")
    if not token:
        return
    try:
        from huggingface_hub import login
        login(token=token, add_to_git_credential=False)
        print("[hf_auth] logged in to HuggingFace Hub.", flush=True)
    except Exception as e:  # noqa: BLE001
        print(f"[hf_auth] login skipped: {e}", flush=True)


_login_hf()


class Qwen3Backend:
    """
    Qwen3-TTS-0.6B loaded on CPU via HuggingFace transformers.

    Notes:
    - ~1.5–2 GB RAM; model download ~1.2 GB (cached after first run)
    - CPU synthesis: expect 30–90 s per sentence — not suitable for live use yet
    - trust_remote_code=True required for Qwen custom model code
    - If transformers adds a named Qwen3TtsProcessor class, prefer that import;
      AutoProcessor is the safe fallback.
    """

    _model = None
    _processor = None
    _lock = threading.Lock()
    SAMPLE_RATE = 24000  # Qwen3-TTS default; override if model card differs

    def warmup(self) -> None:
        """Pre-load model into memory (call once before synthesis loop)."""
        self._load()

    def _load(self) -> None:
        if self.__class__._model is not None:
            return
        with self.__class__._lock:
            if self.__class__._model is not None:
                return
            import torch
            from transformers import AutoModel, AutoProcessor

            print(f"[qwen3_tts] loading {_QWEN3_MODEL} on CPU …", flush=True)
            try:
                processor = AutoProcessor.from_pretrained(
                    _QWEN3_MODEL, trust_remote_code=True
                )
                model = AutoModel.from_pretrained(
                    _QWEN3_MODEL,
                    trust_remote_code=True,
                    torch_dtype=torch.float32,  # float32 for CPU stability
                    low_cpu_mem_usage=True,
                )
                model.eval()
                self.__class__._processor = processor
                self.__class__._model = model
                print("[qwen3_tts] model ready.", flush=True)
            except Exception as e:
                print(f"[qwen3_tts] load failed: {e}", flush=True)
                raise

    def synthesize(self, text: str, out_path: Path) -> bool:
        """Synthesize text → WAV at out_path. Returns True on success."""
        try:
            import soundfile as sf
            import torch

            self._load()

            inputs = self.__class__._processor(text=text, return_tensors="pt")
            with torch.no_grad():
                output = self.__class__._model.generate(**inputs)

            # Expected shape: [1, T] or [T]; squeeze to 1-D float32
            audio = output.squeeze().cpu().numpy().astype(np.float32)

            # Normalise if integer output (some models emit int16 range)
            if np.abs(audio).max() > 1.0:
                audio = audio / 32768.0

            sr = getattr(self.__class__._processor, "sampling_rate", self.SAMPLE_RATE)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            sf.write(str(out_path), audio, sr, subtype="PCM_16")
            return True

        except Exception as e:
            print(f"[qwen3_tts] synthesize error: {e}", flush=True)
            return False


# ── Kokoro-82M ────────────────────────────────────────────────────────────────

_KOKORO_VOICE = os.environ.get("CASSANDRA_KOKORO_VOICE", "af_heart")
_KOKORO_SPEED = float(os.environ.get("CASSANDRA_KOKORO_SPEED", "0.9"))
_KOKORO_LANG  = os.environ.get("CASSANDRA_KOKORO_LANG", "a")  # 'a' = American English


class KokoroBackend:
    """
    Kokoro-82M — lightweight neural TTS via the 'kokoro' HuggingFace package.

    Install:  pip install kokoro soundfile
    RAM:      ~300–400 MB
    Speed:    Near-realtime on CPU for short phrases (~2–5 s per sentence).
    Voices:   af_heart (warm/neutral), af_sky (lighter), am_adam (male)
              Full list: https://huggingface.co/hexgrad/Kokoro-82M
    """

    _pipeline = None
    _lock = threading.Lock()
    _synth_lock = threading.Lock()
    SAMPLE_RATE = 24000

    def warmup(self) -> None:
        self._load()

    def _load(self) -> None:
        if self.__class__._pipeline is not None:
            return
        with self.__class__._lock:
            if self.__class__._pipeline is not None:
                return
            print(
                f"[kokoro_tts] loading Kokoro-82M "
                f"(voice={_KOKORO_VOICE}, lang={_KOKORO_LANG}) …",
                flush=True,
            )
            try:
                from kokoro import KPipeline

                self.__class__._pipeline = KPipeline(lang_code=_KOKORO_LANG)
                print("[kokoro_tts] model ready.", flush=True)
            except Exception as e:
                print(f"[kokoro_tts] load failed: {e}", flush=True)
                raise

    def synthesize(self, text: str, out_path: Path) -> bool:
        try:
            import soundfile as sf

            self._load()

            chunks = []
            with self.__class__._synth_lock:
                for _gs, _ps, audio in self.__class__._pipeline(
                    text, voice=_KOKORO_VOICE, speed=_KOKORO_SPEED
                ):
                    chunks.append(audio)

            if not chunks:
                print("[VOICE_METRIC] backend=kokoro_backend chunks=0 result=empty_chunks", flush=True)
                return False

            combined = np.concatenate(chunks).astype(np.float32)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            sf.write(str(out_path), combined, self.SAMPLE_RATE, subtype="PCM_16")
            print(
                f"[VOICE_METRIC] backend=kokoro_backend chunks={len(chunks)}"
                f" audio_samples={len(combined)}",
                flush=True,
            )
            return True

        except Exception as e:
            print(f"[kokoro_tts] synthesize error: {e}", flush=True)
            return False


# ── Factory ────────────────────────────────────────────────────────────────────

_REGISTRY = {
    "qwen3":  Qwen3Backend,
    "kokoro": KokoroBackend,
}

_instances: dict[str, object] = {}
_inst_lock = threading.Lock()


def get_backend(name: str):
    """Return a singleton backend instance by name ('qwen3' or 'kokoro')."""
    name = name.lower()
    if name not in _REGISTRY:
        raise ValueError(
            f"Unknown TTS backend: {name!r}. Valid: {sorted(_REGISTRY)}"
        )
    with _inst_lock:
        if name not in _instances:
            _instances[name] = _REGISTRY[name]()
    return _instances[name]
