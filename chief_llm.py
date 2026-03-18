import json
import os
import re
import urllib.request
import urllib.error

OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL      = "qwen2.5-coder:7b"   # default: fast hot-path model
OLLAMA_MODEL_DEEP = "qwen2.5-coder:14b"  # escalation: synthesis / deep analysis

CLAUDE_MODEL = "claude-sonnet-4-6"

# ── Escalation logic ──────────────────────────────────────────────────────────
#
# Automatic local model escalation: use 14b instead of 7b when the prompt
# clearly warrants deeper synthesis.  All thresholds are explicit and tunable.
#
# Rules (ANY one match → escalate):
#   1. Long prompt  — > 400 words: synthesis prompts filled with dynamic data
#                     always exceed this; hot-path prompts never do.
#   2. Keyword hit  — > 150 words AND contains a synthesis keyword: catches
#                     shorter synthesis prompts (mixer, financial narrative)
#                     that have a clear semantic signal.
#
# Hot-path prompts (router classify, prefill, validator, billing) are all
# < 150 words — they will never trigger rule 2, and never reach 400 words
# for rule 1.  Safe to leave auto-escalation always on.

_WORD_THRESHOLD_HARD  = 400   # escalate unconditionally above this word count
_WORD_THRESHOLD_SOFT  = 100   # escalate above this count if keyword also matches
_DEEP_TIMEOUT_FLOOR   = 60    # minimum timeout (s) when using 14b

_ESCALATION_KEYWORDS = frozenset({
    # explicit synthesis tasks
    "synthesize", "synthesis",
    # reflection brain — "reflection assessment"
    "reflection",
    # integration brain — "generate integration proposals"
    "proposals",
    # reporter brain — "daily digest"
    "daily digest",
    # scout brain — "technology scout"
    "technology scout",
    # album cross-analysis
    "across all songs", "cross-song",
})


def should_escalate(prompt: str) -> bool:
    """
    Return True if this prompt warrants the deeper local model (14b).

    Inspectable decision:
      - Hard rule:  word count > 400
      - Soft rule:  word count > 150  AND  prompt contains a synthesis keyword
    """
    words = len(prompt.split())
    if words > _WORD_THRESHOLD_HARD:
        return True
    if words > _WORD_THRESHOLD_SOFT:
        lower = prompt.lower()
        if any(kw in lower for kw in _ESCALATION_KEYWORDS):
            return True
    return False


def _pick_model(prompt: str) -> str:
    """Return OLLAMA_MODEL_DEEP if escalation triggered, else OLLAMA_MODEL."""
    return OLLAMA_MODEL_DEEP if should_escalate(prompt) else OLLAMA_MODEL


def ollama_call(prompt: str, timeout: int = 15, model: str = None) -> str:
    """Call Ollama and return raw text response. Returns '' on any error.

    model=None (default): auto-selects via should_escalate(), logs on escalation.
    model=<explicit>:     bypasses auto-escalation — used by Cassandra and tests
                          that have already made the routing decision.
    When using 14b (either path), timeout is raised to _DEEP_TIMEOUT_FLOOR.
    """
    if model is not None:
        if model == OLLAMA_MODEL_DEEP:
            timeout = max(timeout, _DEEP_TIMEOUT_FLOOR)
    else:
        model = _pick_model(prompt)
        if model == OLLAMA_MODEL_DEEP:
            timeout = max(timeout, _DEEP_TIMEOUT_FLOOR)
            print(f"[llm] escalated → 14b ({len(prompt.split())} words, timeout={timeout}s)",
                  flush=True)
    payload = json.dumps({
        "model": model,
        "prompt": prompt,
        "stream": False,
    }).encode("utf-8")
    req = urllib.request.Request(
        OLLAMA_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data.get("response", "").strip()
    except Exception:
        return ""


def claude_call(prompt: str, timeout: int = 30) -> str:
    """Call Claude API and return raw text response. Returns '' on any error."""
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return ""
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        message = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
            timeout=timeout,
        )
        return message.content[0].text.strip()
    except Exception:
        return ""


def claude_json(prompt: str, timeout: int = 20) -> dict | list:
    """Call Claude API and parse JSON from response. Returns {} on error or parse failure."""
    raw = claude_call(prompt, timeout=timeout)
    if not raw:
        return {}
    text = raw.strip()
    # Strip markdown fences
    if text.startswith("```"):
        lines = text.splitlines()
        inner = lines[1:-1] if lines and lines[-1].strip() == "```" else lines[1:]
        text = "\n".join(inner)
    try:
        return json.loads(text)
    except Exception:
        # Try finding a JSON object or array
        m = re.search(r"(\{.*\}|\[.*\])", text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(0))
            except Exception:
                pass
    return {}


def ollama_json(prompt: str, timeout: int = 15) -> dict:
    """Call Ollama and parse JSON from response. Returns {} on error or parse failure."""
    raw = ollama_call(prompt, timeout=timeout)
    if not raw:
        return {}
    text = raw.strip()
    # Strip markdown fences
    if text.startswith("```"):
        lines = text.splitlines()
        inner = lines[1:-1] if lines and lines[-1].strip() == "```" else lines[1:]
        text = "\n".join(inner)
    try:
        return json.loads(text)
    except Exception:
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(0))
            except Exception:
                pass
    return {}
