"""
chief_chat.py

Lightweight interactive chat REPL with the Chief local model.
Uses Ollama /api/chat (multi-turn support).

Does NOT touch the Telegram stack, router, session state, or approval gate.
Completely standalone — safe to run while the Chief stack is live.

Usage:
  python ~/chief_chat.py            # fast model (qwen2.5-coder:7b)
  python ~/chief_chat.py --smart    # deep model  (qwen2.5-coder:14b)

In-chat commands:
  /clear    — clear conversation history (reset to system prompt)
  /model    — show current model
  /vram     — show loaded model memory split (GPU vs CPU)
  exit / quit / Ctrl+C  — quit
"""

import json
import sys
import urllib.request
import urllib.error

OLLAMA_CHAT_URL = "http://localhost:11434/api/chat"
OLLAMA_PS_URL   = "http://localhost:11434/api/ps"

MODEL_FAST  = "qwen2.5-coder:7b"
MODEL_SMART = "qwen2.5-coder:14b"

SYSTEM_FAST = (
    "You are Chief, an AI assistant for OpenClaw — an independent music producer "
    "and record label. Be direct, concise, and practical."
)
SYSTEM_SMART = (
    "You are Chief, an AI analyst for OpenClaw. Provide detailed synthesis, "
    "analysis, and recommendations. Be thorough and specific with numbers and context."
)


def _chat_turn(messages: list[dict], model: str, timeout: int = 90) -> str:
    payload = json.dumps({
        "model":    model,
        "messages": messages,
        "stream":   False,
    }).encode("utf-8")
    req = urllib.request.Request(
        OLLAMA_CHAT_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data.get("message", {}).get("content", "").strip()
    except urllib.error.URLError as e:
        return f"[connection error: {e}]"
    except Exception as e:
        return f"[error: {e}]"


def _show_vram(model: str) -> None:
    try:
        with urllib.request.urlopen(OLLAMA_PS_URL, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        for m in data.get("models", []):
            if model.split(":")[0] in m.get("name", ""):
                total = m.get("size", 0)
                vram  = m.get("size_vram", 0)
                cpu   = total - vram
                pct   = int(100 * vram / total) if total else 0
                ctx   = m.get("context_length", "?")
                print(f"  {m['name']}: {total/1e9:.2f} GB total | "
                      f"{vram/1e9:.2f} GB VRAM ({pct}% GPU) | "
                      f"{cpu/1e9:.2f} GB CPU RAM | ctx {ctx}")
                return
        print(f"  {model}: not currently loaded (will load on first message)")
    except Exception as e:
        print(f"  [vram check failed: {e}]")


def run(model: str) -> None:
    system_prompt = SYSTEM_SMART if model == MODEL_SMART else SYSTEM_FAST
    messages: list[dict] = [{"role": "system", "content": system_prompt}]
    label = "smart (14b)" if model == MODEL_SMART else "fast (7b)"

    print(f"\nChief local chat — {label}")
    print(f"Model: {model}")
    print("Commands: /clear  /model  /vram  |  exit to quit")
    print("-" * 60)

    while True:
        try:
            user_input = input("\nYou: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye.")
            break

        if not user_input:
            continue

        lower = user_input.lower()

        if lower in ("exit", "quit", "bye"):
            print("Bye.")
            break
        if lower == "/clear":
            messages = [{"role": "system", "content": system_prompt}]
            print("[conversation cleared]")
            continue
        if lower == "/model":
            print(f"[model: {model}]")
            continue
        if lower == "/vram":
            _show_vram(model)
            continue

        messages.append({"role": "user", "content": user_input})
        print("Chief: ", end="", flush=True)
        reply = _chat_turn(messages, model)
        print(reply)
        messages.append({"role": "assistant", "content": reply})


if __name__ == "__main__":
    use_smart = "--smart" in sys.argv
    run(MODEL_SMART if use_smart else MODEL_FAST)
