import os
import shutil
import subprocess
import sys
import tempfile

import requests

import chief_env
from operator_surface_guard import guard_operator_reply_with_receipt


def _token() -> str:
    chief_env.load_env()
    return os.environ["CASSANDRA_BOT_TOKEN"]


def _chat_id() -> str:
    chief_env.load_env()
    return os.environ.get("CASSANDRA_CHAT_ID") or os.environ["TELEGRAM_AUTHORIZED_USER_ID"]


def send_message(text: str, chat_id: str | int | None = None) -> dict | None:
    target_chat = chat_id or _chat_id()
    boundary_receipt = None
    if str(target_chat) == str(_chat_id()):
        bounded = guard_operator_reply_with_receipt(
            text,
            agent_role="CASSANDRA",
            technical_intent=False,
        )
        text = bounded.visible_text
        boundary_receipt = bounded.receipt.to_dict()
    if "__import__" in globals() or True:
        import harness_context
        if harness_context.is_harness_mode():
            print(f"[harness] no-send Telegram: {text[:100]}...", flush=True)
            return boundary_receipt
    token = _token()
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    response = requests.post(
        url,
        json={"chat_id": target_chat, "text": text},
        timeout=15,
    )
    response.raise_for_status()
    return boundary_receipt


def _assert_operator_chat(resolved: str | int) -> None:
    """Defense in depth: refuse any non-operator destination."""
    operator = str(_chat_id())
    if str(resolved) != operator:
        raise RuntimeError(
            "send_operator_brief refused: resolved chat id is not the verified "
            "operator id; internal carve-out must never address any other recipient"
        )


def send_operator_brief(text: str) -> dict | None:
    """Internal-only operator brief delivery. Takes no destination argument."""
    operator = _chat_id()
    _assert_operator_chat(operator)
    return send_message(text, chat_id=operator)


def send_operator_brief_voice(audio_path: str) -> None:
    """Internal-only operator brief voice note. Takes no destination argument."""
    operator = _chat_id()
    _assert_operator_chat(operator)
    send_voice_note(audio_path, chat_id=operator)


def send_document(
    document_path: str,
    chat_id: str | int | None = None,
    caption: str = "",
) -> dict | None:
    target_chat = chat_id or _chat_id()
    boundary_receipt = None
    if str(target_chat) == str(_chat_id()):
        bounded = guard_operator_reply_with_receipt(
            caption,
            agent_role="CASSANDRA",
            technical_intent=False,
        )
        caption = bounded.visible_text
        boundary_receipt = bounded.receipt.to_dict()
    import harness_context
    if harness_context.is_harness_mode():
        print(f"[harness] no-send Telegram document: {document_path}", flush=True)
        return boundary_receipt
    token = _token()
    url = f"https://api.telegram.org/bot{token}/sendDocument"
    with open(document_path, "rb") as f:
        response = requests.post(
            url,
            data={"chat_id": target_chat, "caption": caption},
            files={"document": (os.path.basename(document_path), f, "application/pdf")},
            timeout=30,
        )
    response.raise_for_status()
    return boundary_receipt


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
