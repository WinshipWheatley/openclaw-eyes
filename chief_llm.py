import json
import os
import re
import subprocess
import urllib.request
import urllib.error
import fcntl
from pathlib import Path
import time as _time
import inspect as _inspect

# -- External call logger --------------------------------------------------
_EXTERNAL_LOG = Path("/mnt/c/OpenClaw/logs/external_llm_log.csv")

def _log_external_call(model: str, prompt_words: int, response_words: int,
                       latency_ms: int, success: bool) -> None:
    """Append one row to external_llm_log.csv. Fails open, never raises."""
    try:
        caller = "unknown"
        for frame in _inspect.stack():
            fname = frame.filename
            if ("chief_" in fname or "cassandra_" in fname) and "chief_llm" not in fname:
                caller = Path(fname).stem
                break
        needs_header = not _EXTERNAL_LOG.exists() or _EXTERNAL_LOG.stat().st_size == 0
        with open(_EXTERNAL_LOG, "a") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            try:
                if needs_header:
                    f.write("timestamp,caller,model,prompt_words,response_words,latency_ms,success\n")
                ts = _time.strftime("%Y-%m-%d %H:%M:%S")
                f.write(f"{ts},{caller},{model},{prompt_words},{response_words},{latency_ms},{success}\n")
                f.flush()
            finally:
                fcntl.flock(f, fcntl.LOCK_UN)
    except Exception:
        pass

OLLAMA_URL = "http://localhost:11434/api/generate"
_INSTALLED_MODEL_CACHE: tuple[float, set[str]] | None = None

_LANE_CANDIDATES = {
    "fast": (
        "nemotron-3-nano:4b",
        "gemma4:31b",
        "nemotron-3-nano:30b",
    ),
    "strong": (
        "gemma4:31b",
        "nemotron-3-nano:30b",
        "qwen2.5-coder:14b",
    ),
    "deep": (
        "nemotron-3-nano:30b",
        "gemma4:31b",
        "qwen2.5-coder:14b",
    ),
    "code_challenger": (
        "qwen2.5-coder:14b",
    ),
}

_TASK_CLASS_MODEL_CANDIDATES = {
    "cassandra_user_reply_fast": (
        "gemma4:e4b",
        "gemma4:26b",
        "gemma4:31b",
    ),
    "cassandra_user_reply": (
        "gemma4:26b",
        "gemma4:31b",
    ),
    "cassandra_outbound_draft": (
        "gemma4:31b",
        "gemma4:26b",
    ),
    "cassandra_morning_brief": (
        "gemma4:26b",
        "gemma4:31b",
    ),
    "cassandra_inbox_summary": (
        "gemma4:e4b",
        "gemma4:26b",
        "gemma4:31b",
    ),
    "cassandra_extract_classify": (
        "gemma4:e4b",
        "gemma4:26b",
        "gemma4:31b",
    ),
    "chief_evidence_scan": (
        "nemotron-3-nano:4b",
        "nemotron-3-nano:30b",
    ),
    "chief_evidence_synthesis": (
        "nemotron-3-nano:30b",
        "mistral-small:latest",
        "magistral:latest",
    ),
    "chief_structured_plan": (
        "mistral-small:latest",
        "magistral:latest",
        "nemotron-3-nano:30b",
    ),
    "chief_ambiguous_debug": (
        "magistral:latest",
        "nemotron-3-nano:30b",
        "mistral-small:latest",
    ),
    "chief_agentic_code": (
        "qwen3.6:latest",
        "mistral-small:latest",
    ),
}

_TASK_CLASS_PREFERRED_LANES = {
    "cassandra_user_reply_fast": "fast",
    "cassandra_user_reply": "strong",
    "cassandra_outbound_draft": "strong",
    "cassandra_morning_brief": "strong",
    "cassandra_inbox_summary": "fast",
    "cassandra_extract_classify": "fast",
    "chief_evidence_scan": "fast",
    "chief_evidence_synthesis": "deep",
    "chief_structured_plan": "strong",
    "chief_ambiguous_debug": "deep",
    "chief_agentic_code": "code_challenger",
}

_FAST_PROMPT_HINTS = frozenset({
    "classify",
    "return json only",
    "extract",
    "sender and subject only",
    "subject only",
    "bounded summary",
    "micro-report",
})

# ── Nemotron cloud inference ───────────────────────────────────────────────────
#
# Called only from paths that have already passed a privacy pre-routing check.
# Do not call nemotron_call() directly — use it via a workload-specific routing
# function (e.g. _synthesize() in chief_brainstorm_brain.py) that checks safety first.
#
NEMOTRON_URL   = "https://integrate.api.nvidia.com/v1/chat/completions"
NEMOTRON_MODEL = "nvidia/nemotron-3-super-120b-a12b"
_NEMOCLAW_CREDS = Path.home() / ".nemoclaw" / "credentials.json"


def _nemotron_api_key() -> str:
    """Return NVIDIA_API_KEY from env, then ~/.nemoclaw/credentials.json. Empty string if absent."""
    key = os.environ.get("NVIDIA_API_KEY", "")
    if key:
        return key
    try:
        creds = json.loads(_NEMOCLAW_CREDS.read_text())
        return creds.get("NVIDIA_API_KEY", "")
    except Exception:
        return ""


def nemotron_call(prompt: str, timeout: int = 30) -> str:
    """Call NVIDIA Nemotron cloud API. Returns '' on any error.

    IMPORTANT: Only call this function after a workload-specific privacy pre-routing
    check has returned True. This function does not inspect content itself.
    """
    api_key = _nemotron_api_key()
    if not api_key:
        return ""
    payload = json.dumps({
        "model": NEMOTRON_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 1024,
    }).encode("utf-8")
    req = urllib.request.Request(
        NEMOTRON_URL,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    _pw = len(prompt.split())
    for attempt in range(3):
        _t0 = _time.monotonic()
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                result = data["choices"][0]["message"]["content"].strip()
                _log_external_call(NEMOTRON_MODEL, _pw, len(result.split()),
                                   int((_time.monotonic() - _t0) * 1000), True)
                return result
        except Exception:
            _log_external_call(NEMOTRON_MODEL, _pw, 0,
                               int((_time.monotonic() - _t0) * 1000), False)
            if attempt < 2:
                _time.sleep(2 ** attempt)
                continue
            return ""
    return ""
OLLAMA_MODEL      = "qwen2.5-coder:7b"   # default: fast hot-path model
OLLAMA_MODEL_DEEP = "qwen2.5-coder:14b"  # escalation: synthesis / deep analysis

CLAUDE_MODEL = "claude-sonnet-4-6"
CLAUDE_CLI   = "/home/openclaw/.local/bin/claude"

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


def _ollama_installed_models(force_refresh: bool = False) -> set[str]:
    global _INSTALLED_MODEL_CACHE
    if not force_refresh and _INSTALLED_MODEL_CACHE is not None:
        cached_at, cached_models = _INSTALLED_MODEL_CACHE
        if (_time.time() - cached_at) < 60:
            return set(cached_models)

    models: set[str] = set()
    try:
        result = subprocess.run(
            ["ollama", "list"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        if result.returncode == 0:
            for line in result.stdout.splitlines():
                stripped = line.strip()
                if not stripped or stripped.lower().startswith("name "):
                    continue
                models.add(stripped.split()[0])
    except Exception:
        models = set()

    _INSTALLED_MODEL_CACHE = (_time.time(), set(models))
    return models


def local_model_candidates(lane: str, *, task_class: str | None = None) -> tuple[str, ...]:
    if task_class in _TASK_CLASS_MODEL_CANDIDATES:
        return _TASK_CLASS_MODEL_CANDIDATES[task_class]
    return _LANE_CANDIDATES.get(lane, _LANE_CANDIDATES["strong"])


def choose_local_model_lane(
    prompt: str,
    lane: str | None = None,
    *,
    task_class: str | None = None,
) -> str:
    if lane in _LANE_CANDIDATES:
        return lane
    if task_class in _TASK_CLASS_PREFERRED_LANES:
        return _TASK_CLASS_PREFERRED_LANES[task_class]

    lowered = prompt.lower()
    if any(hint in lowered for hint in _FAST_PROMPT_HINTS):
        return "fast"
    if should_escalate(prompt):
        return "deep"
    return "strong"


def local_model_route_reason(
    prompt: str,
    lane: str,
    *,
    task_class: str | None = None,
) -> str:
    if task_class == "cassandra_user_reply_fast":
        return "cassandra easy conversational reply stays in the smallest installed gemma 4 lane"
    if task_class == "cassandra_user_reply":
        return "cassandra normal conversational reply policy uses gemma 4 26b before the top lane"
    if task_class == "cassandra_outbound_draft":
        return "cassandra outbound draft policy uses the top gemma 4 lane"
    if task_class == "cassandra_morning_brief":
        return "cassandra morning briefing policy uses the top gemma 4 lane with gemma 26b fallback"
    if task_class in {"cassandra_inbox_summary", "cassandra_extract_classify"}:
        return "cassandra bounded hidden task uses the smallest installed gemma 4 lane"
    if task_class == "chief_evidence_scan":
        return "chief bounded evidence scan uses the small nemotron lane"
    if task_class == "chief_evidence_synthesis":
        return "chief heavy evidence synthesis uses nemotron 30b"
    if task_class == "chief_structured_plan":
        return "chief structured planning uses mistral small"
    if task_class == "chief_ambiguous_debug":
        return "chief ambiguous debugging uses magistral"
    if task_class == "chief_agentic_code":
        return "chief agentic code work uses qwen 3.6"
    if lane == "fast":
        return "fast-lane policy for bounded extract/classify work"
    if lane == "deep":
        return "deep threshold triggered for broad synthesis work"
    return "default strong lane for normal user-facing reasoning"


def resolve_local_model(
    prompt: str,
    lane: str | None = None,
    *,
    task_class: str | None = None,
) -> tuple[str, str]:
    selected_lane = choose_local_model_lane(prompt, lane, task_class=task_class)
    installed = _ollama_installed_models()
    candidates = local_model_candidates(selected_lane, task_class=task_class)
    if not installed:
        return candidates[0], selected_lane
    for candidate in candidates:
        if candidate in installed:
            return candidate, selected_lane
    return candidates[0], selected_lane


def _pick_model(prompt: str) -> str:
    """Return OLLAMA_MODEL_DEEP if escalation triggered, else OLLAMA_MODEL."""
    return OLLAMA_MODEL_DEEP if should_escalate(prompt) else OLLAMA_MODEL


def ollama_call(
    prompt: str,
    timeout: int = 15,
    model: str = None,
    lane: str | None = None,
    *,
    task_class: str | None = None,
) -> str:
    """Call Ollama and return raw text response. Returns '' on any error. Retries up to 3 times with backoff.

    model=None (default): auto-selects via should_escalate(), logs on escalation.
    model=<explicit>:     bypasses auto-escalation — used by Cassandra and tests
                          that have already made the routing decision.
    When using 14b (either path), timeout is raised to _DEEP_TIMEOUT_FLOOR.
    """
    if model is not None:
        if model == OLLAMA_MODEL_DEEP:
            timeout = max(timeout, _DEEP_TIMEOUT_FLOOR)
    else:
        model, resolved_lane = resolve_local_model(prompt, lane=lane, task_class=task_class)
        if resolved_lane == "deep":
            timeout = max(timeout, _DEEP_TIMEOUT_FLOOR)
            print(f"[llm] routed → deep ({len(prompt.split())} words, timeout={timeout}s)",
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
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data.get("response", "").strip()
        except Exception:
            if attempt < 2:
                _time.sleep(2 ** attempt)
                continue
            return ""
    return ""


def claude_call(prompt: str, timeout: int = 30, retries: int = 3) -> str:
    """Call Claude via CLI (Pro sub). Returns '' on any error.

    Policy: blocked by default. Only allowed when the explicit manual override
    environment variable OPENCLAW_ALLOW_CLAUDE_MANUAL is truthy.
    """
    manual_ok = os.environ.get("OPENCLAW_ALLOW_CLAUDE_MANUAL", "").strip().lower() in {"1", "true", "yes"}
    if not manual_ok:
        print("[chief_llm] claude_call blocked by policy", flush=True)
        return ""
    import subprocess as _subprocess
    _pw = len(prompt.split())
    retries = max(1, int(retries))
    for attempt in range(retries):
        _t0 = _time.monotonic()
        try:
            # Strip ANTHROPIC_API_KEY so CLI uses OAuth/Pro auth, not API billing
            env = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}
            result = _subprocess.run(
                [CLAUDE_CLI, "--print", "--output-format", "json",
                 "--model", CLAUDE_MODEL, "--no-session-persistence"],
                input=prompt,
                capture_output=True,
                text=True,
                timeout=timeout,
                env=env,
            )
            if result.returncode != 0:
                _log_external_call(CLAUDE_MODEL, _pw, 0,
                                   int((_time.monotonic() - _t0) * 1000), False)
                if attempt < retries - 1:
                    _time.sleep(2 ** attempt)
                    continue
                return ""
            data = json.loads(result.stdout)
            text = data.get("result", "").strip()
            _log_external_call(CLAUDE_MODEL, _pw, len(text.split()),
                               int((_time.monotonic() - _t0) * 1000), bool(text))
            return text
        except Exception:
            _log_external_call(CLAUDE_MODEL, _pw, 0,
                               int((_time.monotonic() - _t0) * 1000), False)
            if attempt < retries - 1:
                _time.sleep(2 ** attempt)
                continue
            return ""
    return ""


def claude_json(prompt: str, timeout: int = 20, retries: int = 3) -> dict | list:
    """Call Claude API and parse JSON from response. Returns {} on error or parse failure."""
    raw = claude_call(prompt, timeout=timeout, retries=retries)
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


def ollama_json(prompt: str, timeout: int = 15, task_class: str | None = None) -> dict:
    """Call Ollama and parse JSON from response. Returns {} on error or parse failure."""
    raw = ollama_call(prompt, timeout=timeout, task_class=task_class)
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
