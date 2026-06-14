#!/usr/bin/env python3
"""
oclaw_doctools.py — Generic document/audio processing utilities for OpenClaw.

System-wide wrappers around local CLI tools:
    - OCR:           tesseract-ocr  (image → text)
    - PDF extraction: pdftotext     (PDF → text)
    - Audio transcode: ffmpeg       (normalize/convert audio)

These are neutral utilities. They take input paths, return output.
They do NOT enforce workspace boundaries, data classification, or approval
gates. Callers (legal, Cassandra, Chief, etc.) enforce their own policies.

Requirements:
    sudo apt install tesseract-ocr poppler-utils ffmpeg
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

# ── Tool availability ────────────────────────────────────────────────────────

def _which(tool: str) -> str | None:
    """Return path to tool binary, or None if not found."""
    return shutil.which(tool)


def check_tools() -> dict[str, bool]:
    """Check which document processing tools are installed.

    Returns dict of {tool_name: installed_bool}.
    """
    return {
        "tesseract": _which("tesseract") is not None,
        "pdftotext": _which("pdftotext") is not None,
        "ffmpeg":    _which("ffmpeg") is not None,
    }


# ── OCR ──────────────────────────────────────────────────────────────────────

def ocr_image(image_path: str | Path, lang: str = "eng",
              timeout: int = 60) -> dict:
    """Run Tesseract OCR on an image file.

    Args:
        image_path: Path to .png, .jpg, .tiff, .heic, etc.
        lang: Tesseract language code (default: eng).
        timeout: Max seconds for OCR process.

    Returns:
        {"ok": True, "text": "...", "confidence": "..."} on success.
        {"ok": False, "error": "..."} on failure.
    """
    image_path = Path(image_path)
    if not image_path.exists():
        return {"ok": False, "error": f"file not found: {image_path}"}

    if not _which("tesseract"):
        return {"ok": False, "error": "tesseract not installed (apt install tesseract-ocr)"}

    try:
        # tesseract <input> stdout -l <lang>
        result = subprocess.run(
            ["tesseract", str(image_path), "stdout", "-l", lang],
            capture_output=True, text=True, timeout=timeout,
        )
        if result.returncode != 0:
            return {"ok": False, "error": f"tesseract exit {result.returncode}: {result.stderr.strip()[:200]}"}

        text = result.stdout.strip()
        # Rough confidence heuristic: very short output for a real image = low confidence
        confidence = "normal"
        if len(text) < 20:
            confidence = "low"
        elif len(text) < 5:
            confidence = "very_low"

        return {"ok": True, "text": text, "confidence": confidence, "chars": len(text)}

    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"tesseract timed out after {timeout}s"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def ocr_image_to_file(image_path: str | Path, output_path: str | Path,
                      lang: str = "eng", timeout: int = 60) -> dict:
    """Run OCR and write result to a text file.

    Returns same dict as ocr_image(), plus "output_path" on success.
    """
    result = ocr_image(image_path, lang, timeout)
    if not result["ok"]:
        return result

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(result["text"], encoding="utf-8")
    result["output_path"] = str(output_path)
    return result


# ── PDF text extraction ──────────────────────────────────────────────────────

def pdf_to_text(pdf_path: str | Path, timeout: int = 60,
                first_page: int | None = None,
                last_page: int | None = None) -> dict:
    """Extract text from a PDF using pdftotext (poppler-utils).

    Args:
        pdf_path: Path to .pdf file.
        timeout: Max seconds.
        first_page: Start page (1-indexed, optional).
        last_page: End page (1-indexed, optional).

    Returns:
        {"ok": True, "text": "...", "pages": N} on success.
        {"ok": False, "error": "..."} on failure.
    """
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        return {"ok": False, "error": f"file not found: {pdf_path}"}

    if not _which("pdftotext"):
        return {"ok": False, "error": "pdftotext not installed (apt install poppler-utils)"}

    cmd = ["pdftotext", "-layout"]
    if first_page is not None:
        cmd.extend(["-f", str(first_page)])
    if last_page is not None:
        cmd.extend(["-l", str(last_page)])
    cmd.extend([str(pdf_path), "-"])  # "-" = stdout

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout,
        )
        if result.returncode != 0:
            return {"ok": False, "error": f"pdftotext exit {result.returncode}: {result.stderr.strip()[:200]}"}

        text = result.stdout
        # Estimate page count from form-feed characters
        pages = text.count("\f") + 1 if text.strip() else 0

        return {"ok": True, "text": text.strip(), "pages": pages, "chars": len(text.strip())}

    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"pdftotext timed out after {timeout}s"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def pdf_to_text_file(pdf_path: str | Path, output_path: str | Path,
                     timeout: int = 60) -> dict:
    """Extract PDF text and write to a file.

    Returns same dict as pdf_to_text(), plus "output_path" on success.
    """
    result = pdf_to_text(pdf_path, timeout)
    if not result["ok"]:
        return result

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(result["text"], encoding="utf-8")
    result["output_path"] = str(output_path)
    return result


# ── Audio transcode/normalize ────────────────────────────────────────────────

def audio_to_wav(input_path: str | Path, output_path: str | Path | None = None,
                 sample_rate: int = 16000, mono: bool = True,
                 timeout: int = 120) -> dict:
    """Convert/normalize audio to WAV format suitable for speech processing.

    Default output: 16kHz mono WAV (Whisper-friendly).

    Args:
        input_path: Any audio file (.m4a, .mp3, .ogg, .wav, etc.)
        output_path: Destination .wav path. If None, uses input stem + .wav in same dir.
        sample_rate: Target sample rate in Hz (default 16000 for Whisper).
        mono: Convert to mono (default True).
        timeout: Max seconds.

    Returns:
        {"ok": True, "output_path": "...", "duration_secs": N} on success.
        {"ok": False, "error": "..."} on failure.
    """
    input_path = Path(input_path)
    if not input_path.exists():
        return {"ok": False, "error": f"file not found: {input_path}"}

    if not _which("ffmpeg"):
        return {"ok": False, "error": "ffmpeg not installed (apt install ffmpeg)"}

    if output_path is None:
        output_path = input_path.with_suffix(".wav")
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        "ffmpeg", "-y",             # overwrite output
        "-i", str(input_path),
        "-ar", str(sample_rate),    # sample rate
    ]
    if mono:
        cmd.extend(["-ac", "1"])    # mono
    cmd.extend([
        "-acodec", "pcm_s16le",    # 16-bit PCM
        str(output_path),
    ])

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout,
        )
        if result.returncode != 0:
            return {"ok": False, "error": f"ffmpeg exit {result.returncode}: {result.stderr.strip()[-300:]}"}

        # Extract duration from ffmpeg stderr output
        duration = _parse_ffmpeg_duration(result.stderr)

        return {
            "ok": True,
            "output_path": str(output_path),
            "duration_secs": duration,
            "sample_rate": sample_rate,
            "mono": mono,
        }

    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"ffmpeg timed out after {timeout}s"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def audio_info(input_path: str | Path, timeout: int = 10) -> dict:
    """Get audio file metadata using ffprobe.

    Returns:
        {"ok": True, "duration_secs": N, "sample_rate": N, "channels": N, "codec": "..."}
        or {"ok": False, "error": "..."}.
    """
    input_path = Path(input_path)
    if not input_path.exists():
        return {"ok": False, "error": f"file not found: {input_path}"}

    ffprobe = _which("ffprobe")
    if not ffprobe:
        return {"ok": False, "error": "ffprobe not installed (comes with ffmpeg)"}

    cmd = [
        "ffprobe", "-v", "quiet",
        "-print_format", "json",
        "-show_streams", "-show_format",
        str(input_path),
    ]

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout,
        )
        if result.returncode != 0:
            return {"ok": False, "error": f"ffprobe exit {result.returncode}"}

        import json
        data = json.loads(result.stdout)
        fmt = data.get("format", {})
        streams = [s for s in data.get("streams", []) if s.get("codec_type") == "audio"]
        audio = streams[0] if streams else {}

        return {
            "ok": True,
            "duration_secs": float(fmt.get("duration", 0)),
            "sample_rate": int(audio.get("sample_rate", 0)),
            "channels": int(audio.get("channels", 0)),
            "codec": audio.get("codec_name", "unknown"),
            "format": fmt.get("format_name", "unknown"),
        }

    except Exception as e:
        return {"ok": False, "error": str(e)}


def _parse_ffmpeg_duration(stderr: str) -> float | None:
    """Extract duration in seconds from ffmpeg stderr."""
    import re
    m = re.search(r"Duration:\s+(\d+):(\d+):(\d+)\.(\d+)", stderr)
    if m:
        h, mi, s, cs = int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4))
        return h * 3600 + mi * 60 + s + cs / 100.0
    return None


# ── CLI ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    print("OpenClaw Document Tools — availability check")
    print()
    tools = check_tools()
    for name, installed in tools.items():
        status = "installed" if installed else "NOT INSTALLED"
        path = _which(name) or ""
        print(f"  {name}: {status}  {path}")

    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        path = sys.argv[2] if len(sys.argv) > 2 else None

        if cmd == "ocr" and path:
            print(f"\nOCR: {path}")
            print(ocr_image(path))
        elif cmd == "pdf" and path:
            print(f"\nPDF extract: {path}")
            print(pdf_to_text(path))
        elif cmd == "audio" and path:
            print(f"\nAudio info: {path}")
            print(audio_info(path))
        elif cmd == "transcode" and path:
            out = sys.argv[3] if len(sys.argv) > 3 else None
            print(f"\nTranscode: {path}")
            print(audio_to_wav(path, out))
