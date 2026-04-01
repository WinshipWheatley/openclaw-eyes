"""
cassandra_whisper_relay.py

Relay Whisper STT transcript events into Cassandra command intake.

Responsibilities:
  - Confidence gate: reject transcripts below CONFIDENCE_MIN; flag those
    below CONFIDENCE_FLAG_BELOW for surface-level awareness without blocking.
  - Deduplication: suppress identical transcripts that arrive within
    DEDUP_WINDOW_SECONDS of a previous relay.
  - Routing: call cassandra_brain.handle() with accepted transcripts and
    return the reply list.

Public API
----------
relay_transcript(transcript, confidence, event_id=None, session=None)
    → dict with keys: status, reply, reason, confidence, event_id
transcribe_audio(audio_path)
    → (transcript: str, confidence: float)
"""

import hashlib
import json
import math
import os
import threading
import time
from datetime import datetime
from pathlib import Path

# ── Thresholds ────────────────────────────────────────────────────────────────

# Below this: hard reject — do not execute the command.
CONFIDENCE_MIN = float(os.environ.get("WHISPER_RELAY_CONFIDENCE_MIN", "0.60"))

# Below this (but ≥ CONFIDENCE_MIN): accept but annotate reply with a flag.
CONFIDENCE_FLAG_BELOW = float(os.environ.get("WHISPER_RELAY_CONFIDENCE_FLAG", "0.75"))

# Seconds within which an identical transcript is treated as a duplicate.
DEDUP_WINDOW_SECONDS = int(os.environ.get("WHISPER_RELAY_DEDUP_WINDOW", "60"))

# ── Paths ─────────────────────────────────────────────────────────────────────

_RELAY_LOG = Path("/mnt/c/OpenClaw/logs/whisper_relay.jsonl")

# ── Brain reference (module-level so tests can monkeypatch it) ────────────────

def cassandra_handle(text: str, session: dict) -> list[str]:
    """
    Forward a transcript to cassandra_brain.handle().

    Defined at module level so tests can replace it with a stub via
    monkeypatch.setattr(relay, 'cassandra_handle', fake).
    """
    from cassandra_brain import handle  # lazy import — heavy deps
    return handle(text, session)


# ── Dedup store ───────────────────────────────────────────────────────────────

_dedup_lock = threading.Lock()
# Maps transcript_hash → float(monotonic timestamp of last relay)
_dedup_cache: dict[str, float] = {}


def _transcript_hash(transcript: str) -> str:
    normalized = transcript.strip().lower()
    return hashlib.sha256(normalized.encode()).hexdigest()[:16]


def _is_duplicate(tx_hash: str) -> bool:
    with _dedup_lock:
        ts = _dedup_cache.get(tx_hash)
        if ts is None:
            return False
        return (time.monotonic() - ts) < DEDUP_WINDOW_SECONDS


def _record_relay(tx_hash: str) -> None:
    with _dedup_lock:
        _dedup_cache[tx_hash] = time.monotonic()
        # Prune entries older than 2× the window to keep memory bounded.
        cutoff = time.monotonic() - DEDUP_WINDOW_SECONDS * 2
        stale = [k for k, v in _dedup_cache.items() if v < cutoff]
        for k in stale:
            del _dedup_cache[k]


# ── Logging ───────────────────────────────────────────────────────────────────

def _log_relay(status: str, transcript: str, confidence: float,
               event_id: str | None, reason: str) -> None:
    try:
        _RELAY_LOG.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "status": status,
            "confidence": round(confidence, 4),
            "event_id": event_id,
            "reason": reason,
            "transcript_preview": transcript[:80],
        }
        with open(_RELAY_LOG, "a") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception as e:
        print(f"[whisper_relay] log error: {e}", flush=True)


# ── Public relay function ─────────────────────────────────────────────────────

def relay_transcript(
    transcript: str,
    confidence: float,
    event_id: str | None = None,
    session: dict | None = None,
) -> dict:
    """
    Route a Whisper transcript into Cassandra command intake.

    Parameters
    ----------
    transcript : str
        The raw text produced by Whisper.
    confidence : float
        A 0–1 confidence score derived from Whisper segment log-probabilities.
        Values below CONFIDENCE_MIN are rejected without execution.
    event_id : str | None
        Optional caller-supplied identifier for this transcription event.
        Used in log entries; auto-generated if omitted.
    session : dict | None
        Optional session metadata forwarded to cassandra_brain.handle().

    Returns
    -------
    dict
        {
          "status"     : "accepted" | "flagged" | "rejected" | "duplicate",
          "reply"      : list[str],   # Cassandra replies (empty when not accepted)
          "reason"     : str,         # human-readable explanation
          "confidence" : float,
          "event_id"   : str,
        }
    """
    if not event_id:
        event_id = f"w_{int(time.time() * 1000) % 1_000_000:06d}"

    transcript = transcript.strip()
    if not transcript:
        _log_relay("rejected", transcript, confidence, event_id, "empty_transcript")
        return {
            "status": "rejected",
            "reply": [],
            "reason": "empty_transcript",
            "confidence": confidence,
            "event_id": event_id,
        }

    # ── Confidence gate ───────────────────────────────────────────────────────
    if confidence < CONFIDENCE_MIN:
        reason = f"confidence_below_min ({confidence:.2f} < {CONFIDENCE_MIN})"
        _log_relay("rejected", transcript, confidence, event_id, reason)
        return {
            "status": "rejected",
            "reply": [],
            "reason": reason,
            "confidence": confidence,
            "event_id": event_id,
        }

    # ── Deduplication ─────────────────────────────────────────────────────────
    tx_hash = _transcript_hash(transcript)
    if _is_duplicate(tx_hash):
        _log_relay("duplicate", transcript, confidence, event_id, "within_dedup_window")
        return {
            "status": "duplicate",
            "reply": [],
            "reason": "within_dedup_window",
            "confidence": confidence,
            "event_id": event_id,
        }

    # ── Route to Cassandra ────────────────────────────────────────────────────
    session_meta = dict(session or {})
    session_meta["source"] = "whisper_relay"
    session_meta["whisper_event_id"] = event_id
    session_meta["whisper_confidence"] = confidence

    try:
        replies = cassandra_handle(transcript, session_meta)
    except Exception as e:
        print(f"[whisper_relay] cassandra_handle error: {e}", flush=True)
        _log_relay("error", transcript, confidence, event_id, str(e))
        return {
            "status": "rejected",
            "reply": [],
            "reason": f"cassandra_handle_error: {e}",
            "confidence": confidence,
            "event_id": event_id,
        }

    _record_relay(tx_hash)

    flagged = confidence < CONFIDENCE_FLAG_BELOW
    status = "flagged" if flagged else "accepted"
    reason = (
        f"low_confidence_flagged ({confidence:.2f} < {CONFIDENCE_FLAG_BELOW})"
        if flagged
        else "ok"
    )
    _log_relay(status, transcript, confidence, event_id, reason)
    return {
        "status": status,
        "reply": replies,
        "reason": reason,
        "confidence": confidence,
        "event_id": event_id,
    }


# ── Whisper audio transcription helper ───────────────────────────────────────

def transcribe_audio(audio_path: str) -> tuple[str, float]:
    """
    Transcribe an audio file with openai-whisper and return (transcript, confidence).

    Confidence is the mean of exp(avg_logprob) across segments, attenuated by
    each segment's no_speech_prob.  Returns (text, 0.0) when no segments are
    produced (e.g. silence), and ("", 0.0) on error.

    Requires openai-whisper and ffmpeg to be installed.
    """
    model = _get_whisper_model()
    result = model.transcribe(audio_path, language="en", fp16=False)
    segments = result.get("segments", [])
    if not segments:
        return result.get("text", "").strip(), 0.0

    # Convert avg_logprob (≤ 0) → linear confidence, attenuated by no_speech_prob.
    scores = []
    for seg in segments:
        log_prob = seg.get("avg_logprob", -1.0)
        no_speech = seg.get("no_speech_prob", 0.0)
        seg_conf = math.exp(max(log_prob, -3.0))   # clamp floor so exp stays meaningful
        seg_conf *= (1.0 - no_speech)
        scores.append(seg_conf)

    confidence = sum(scores) / len(scores)
    transcript = result.get("text", "").strip()
    return transcript, confidence


_whisper_model = None
_whisper_model_lock = threading.Lock()


def _get_whisper_model():
    """Lazy-load and cache the Whisper model (base, ~145 MB)."""
    global _whisper_model
    if _whisper_model is not None:
        return _whisper_model
    import whisper  # type: ignore

    with _whisper_model_lock:
        if _whisper_model is None:
            model_name = os.environ.get("WHISPER_MODEL", "base")
            print(f"[whisper_relay] loading model '{model_name}'…", flush=True)
            _whisper_model = whisper.load_model(model_name)
            print("[whisper_relay] model ready.", flush=True)
    return _whisper_model
