import os
import shutil
import subprocess
import sys
import tempfile

import requests

import chief_env


def _token() -> str:
    chief_env.load_env()
    return os.environ["CASSANDRA_BOT_TOKEN"]


def _chat_id() -> str:
    chief_env.load_env()
    return os.environ.get("CASSANDRA_CHAT_ID") or os.environ["TELEGRAM_AUTHORIZED_USER_ID"]


def send_message(text: str, chat_id: str | int | None = None) -> None:
    if "__import__" in globals() or True:
        import harness_context
        if harness_context.is_harness_mode():
            print(f"[harness] no-send Telegram: {text[:100]}...", flush=True)
            return
    token = _token()
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    response = requests.post(
        url,
        json={"chat_id": chat_id or _chat_id(), "text": text},
        timeout=15,
    )
    response.raise_for_status()


def send_document(document_path: str, chat_id: str | int | None = None, caption: str = "") -> None:
    import harness_context
    if harness_context.is_harness_mode():
        print(f"[harness] no-send Telegram document: {document_path}", flush=True)
        return
    token = _token()
    target_chat = chat_id or _chat_id()
    url = f"https://api.telegram.org/bot{token}/sendDocument"
    with open(document_path, "rb") as f:
        response = requests.post(
            url,
            data={"chat_id": target_chat, "caption": caption},
            files={"document": (os.path.basename(document_path), f, "application/pdf")},
            timeout=30,
        )
    response.raise_for_status()


def send_voice_note(audio_path: str, chat_id: str | None = None) -> None:
    import harness_context
    if harness_context.is_harness_mode():
        print(f"[harness] no-send Voice: {audio_path}", flush=True)
        return
    """
    Send an audio file as a Telegram voice note (OGG/Opus required by Telegram).
    If audio_path is a .wav file, converts to OGG/Opus using ffmpeg before upload.
    Logs a warning and returns without raising if the send fails.
    """
    token = _token()
    target_chat = chat_id or _chat_id()
    url = f"https://api.telegram.org/bot{token}/sendVoice"
    ogg_path: str | None = None

    try:
        send_path = audio_path
        if audio_path.lower().endswith(".wav"):
            ffmpeg = shutil.which("ffmpeg")
            if not ffmpeg:
                print("[cassandra_sender] send_voice_note: ffmpeg not found — skipping", flush=True)
                return
            fd, ogg_path = tempfile.mkstemp(suffix=".ogg")
            os.close(fd)
            subprocess.run(
                [ffmpeg, "-y", "-i", audio_path, "-c:a", "libopus", "-b:a", "32k", ogg_path],
                check=True,
                capture_output=True,
                timeout=30,
            )
            send_path = ogg_path

        with open(send_path, "rb") as f:
            response = requests.post(
                url,
                data={"chat_id": target_chat},
                files={"voice": ("voice.ogg", f, "audio/ogg")},
                timeout=30,
            )
        response.raise_for_status()
        print("[cassandra_sender] voice note sent", flush=True)

    except Exception as e:
        print(f"[cassandra_sender] voice note failed (non-fatal): {e}", flush=True)

    finally:
        if ogg_path and os.path.exists(ogg_path):
            try:
                os.unlink(ogg_path)
            except Exception:
                pass


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print('Usage: python cassandra_sender.py "your message here"')
        sys.exit(1)
    send_message(" ".join(sys.argv[1:]))
    print("Message sent.")
