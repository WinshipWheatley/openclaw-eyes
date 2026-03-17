"""
chief_validator_brain.py

Middleware between LLM output and Telegram delivery.
Called by the listener before sending any natural-language reply.

Usage:
    from chief_validator_brain import validate_reply
    safe = validate_reply(original_question, llm_reply, intent)
    await update.message.reply_text(safe)

Does NOT touch structured/short replies (billing prompts, session questions).
Applied to: marketing_ideas, content_draft, system_report,
            album_continue, album_arc_start, album_arc_continue.
"""

import re
from datetime import datetime
from pathlib import Path

from chief_llm import ollama_call

VAULT_LOG = Path("/mnt/c/OpenClawShared/openclaw-vault/System/Validation Log.md")
MAX_TELEGRAM = 4096
SAFE_LENGTH  = 4000

# Intents that go through validation
VALIDATED_INTENTS = {
    "marketing_ideas",
    "content_draft",
    "system_report",
    "album_continue",
    "album_arc_start",
    "album_arc_continue",
}

# ── Log ────────────────────────────────────────────────────────────────────────

def _append_log(intent: str, issue: str, action: str) -> None:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = (
        f"\n## {ts}\n"
        f"- **Intent:** {intent}\n"
        f"- **Issue:** {issue}\n"
        f"- **Action:** {action}\n"
    )
    if VAULT_LOG.exists():
        content = VAULT_LOG.read_text(encoding="utf-8")
        content = content.replace("\n_(no failures recorded yet)_\n", "\n")
        VAULT_LOG.write_text(content + entry, encoding="utf-8")
    else:
        VAULT_LOG.write_text(entry, encoding="utf-8")


# ── Checks ─────────────────────────────────────────────────────────────────────

def _has_traceback(text: str) -> bool:
    return "Traceback (most recent call last)" in text or bool(
        re.search(r'File "[^"]+", line \d+', text)
    )


def _is_raw_code_dump(text: str, intent: str) -> bool:
    """True if reply starts with a code fence in a non-code context."""
    if intent == "content_draft":
        return False  # Drafts legitimately contain formatted blocks
    stripped = text.strip()
    return stripped.startswith("```") and len(stripped) > 200


def _strip_traceback(text: str) -> str:
    """Remove traceback blocks, return cleaned text or fallback."""
    # Remove from "Traceback..." to the end of the exception line
    cleaned = re.sub(
        r"Traceback \(most recent call last\):.*?(?:\n\S.*)?$",
        "",
        text,
        flags=re.DOTALL,
    ).strip()
    return cleaned if len(cleaned) > 20 else "An error occurred. Please try again."


def _strip_code_fences(text: str) -> str:
    return re.sub(r"```[a-z]*\n?", "", text).replace("```", "").strip()


def _truncate(text: str) -> str:
    if len(text) <= MAX_TELEGRAM:
        return text
    return text[:SAFE_LENGTH] + "\n… (truncated)"


# ── Retry ──────────────────────────────────────────────────────────────────────

def _retry_once(original_prompt: str, timeout: int = 45) -> str:
    """Ask LLM to retry. Returns new response or fallback."""
    retry_prompt = (
        "Your previous response was empty or unusable. "
        "Please try again and respond to this:\n\n" + original_prompt
    )
    result = ollama_call(retry_prompt, timeout=timeout).strip()
    return result


# ── Public API ─────────────────────────────────────────────────────────────────

def validate_reply(
    original_prompt: str,
    reply: str,
    intent: str = "",
    retry_prompt: str = "",
) -> str:
    """
    Validate and sanitize an LLM reply before it reaches Telegram.

    Args:
        original_prompt: The user's original message (for retry context).
        reply:           The raw LLM reply string.
        intent:          The routing intent (used to decide which checks apply).
        retry_prompt:    Optional full prompt to use on retry (falls back to original_prompt).

    Returns:
        A clean, safe string ready to send via Telegram.
    """
    if intent and intent not in VALIDATED_INTENTS:
        return _truncate(reply)  # Skip full validation for excluded intents

    # 1. Empty response
    if not reply or not reply.strip():
        _append_log(intent, "Empty response", "Retried LLM")
        fallback = _retry_once(retry_prompt or original_prompt)
        if fallback:
            _append_log(intent, "Empty response", "Retry succeeded")
            return _truncate(fallback)
        _append_log(intent, "Empty response", "Retry also empty — returned fallback message")
        return "I wasn't able to generate a response. Please try again."

    # 2. Traceback present
    if _has_traceback(reply):
        _append_log(intent, "Traceback detected", "Stripped error block")
        return _strip_traceback(reply) or "An error occurred. Please try again."

    # 3. Raw code dump in non-code context
    if _is_raw_code_dump(reply, intent):
        _append_log(intent, "Raw code dump in non-code context", "Stripped code fences")
        return _strip_code_fences(reply)

    # 4. Oversized for Telegram
    if len(reply) > MAX_TELEGRAM:
        _append_log(intent, f"Reply too long ({len(reply)} chars)", f"Truncated to {SAFE_LENGTH}")
        return _truncate(reply)

    return reply


# ── CLI smoke test ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("Running validator smoke tests...\n")

    # Test 1: empty
    r = validate_reply("What are my marketing ideas?", "", "marketing_ideas")
    print(f"Empty test: {repr(r[:80])}")

    # Test 2: traceback
    tb = (
        "Traceback (most recent call last):\n"
        '  File "chief_album_brain.py", line 42, in handle\n'
        "    result = do_thing()\n"
        "KeyError: 'song_title'"
    )
    r2 = validate_reply("What song?", tb, "album_continue")
    print(f"Traceback test: {repr(r2)}")

    # Test 3: code dump
    code = "```python\nimport os\nos.remove('file.md')\n```\n" + "x" * 300
    r3 = validate_reply("Any ideas?", code, "marketing_ideas")
    print(f"Code dump test (first 60): {repr(r3[:60])}")

    # Test 4: oversized
    big = "word " * 1000
    r4 = validate_reply("Report?", big, "system_report")
    print(f"Oversized test: len={len(r4)}, ends with truncated={r4.endswith('(truncated)')}")

    # Test 5: clean pass-through
    clean = "Here are three content ideas for Blue Weather."
    r5 = validate_reply("Ideas?", clean, "marketing_ideas")
    print(f"Clean pass-through: {r5 == clean}")

    print("\nValidation Log:", VAULT_LOG)
