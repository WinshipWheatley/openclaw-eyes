import json
import os
import re
import socket
import subprocess
import urllib.request
import urllib.error
import fcntl
from pathlib import Path
import time as _time
import inspect as _inspect

# -- External call logger --------------------------------------------------
_EXTERNAL_LOG = Path("/mnt/c/OpenClaw/logs/external_llm_log.csv")
_OLLAMA_DIAGNOSTICS_LOG = Path("/mnt/c/OpenClaw/logs/ollama_diagnostics.jsonl")


def _env_int(name: str, default: int, *, minimum: int = 1) -> int:
    try:
        return max(minimum, int(os.environ.get(name, str(default))))
    except ValueError:
        return default


_CASSANDRA_MORNING_BRIEF_TIMEOUT = _env_int("OPENCLAW_CASSANDRA_MORNING_BRIEF_TIMEOUT_SECONDS", 420, minimum=60)
_CASSANDRA_MORNING_TEST_TIMEOUT = _env_int("OPENCLAW_CASSANDRA_MORNING_TEST_TIMEOUT_SECONDS", 180, minimum=60)
_CASSANDRA_MORNING_BRIEF_ATTEMPTS = _env_int("OPENCLAW_CASSANDRA_MORNING_BRIEF_ATTEMPTS", 1)
_CASSANDRA_MORNING_TEST_ATTEMPTS = 1


def _diagnostics_enabled() -> bool:
    return os.environ.get("OPENCLAW_LLM_DIAGNOSTICS", "").strip().lower() not in {"0", "false", "no", "off"}


def _log_ollama_diagnostic(event: dict) -> None:
    if not _diagnostics_enabled():
        return
    try:
        _OLLAMA_DIAGNOSTICS_LOG.parent.mkdir(parents=True, exist_ok=True)
        event.setdefault("timestamp", _time.strftime("%Y-%m-%d %H:%M:%S"))
        event.setdefault("diagnostic_type", "local_model_usage")
        with open(_OLLAMA_DIAGNOSTICS_LOG, "a", encoding="utf-8") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            try:
                f.write(json.dumps(event, sort_keys=True) + "\n")
                f.flush()
            finally:
                fcntl.flock(f, fcntl.LOCK_UN)
    except Exception:
        pass

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
_MODEL_SIZE_CACHE: tuple[float, dict[str, float]] | None = None
_OLLAMA_UNREACHABLE_MEMO = False

# Front-door latency ladder (Revision 5): smallest-first ordered allowlist of
# RAM-fitting models that may serve the interactive operator front-door reply.
# Never contains gemma4:26b/31b. Env-overridable as a comma list.
_FRONTDOOR_MODEL_ALLOWLIST_DEFAULT = ("qwen3.5:4b", "qwen3:8b-q4_K_M", "qwen3.5:9b")
_FRONTDOOR_MODEL_HARD_DENY = frozenset({"gemma4:26b", "gemma4:31b"})
# RAM headroom (GB) reserved below available RAM, and a hard size ceiling.
_FRONTDOOR_MODEL_RAM_HEADROOM_GB = 4.0
_FRONTDOOR_MODEL_MAX_GB_DEFAULT = 12.0


def _ollama_tags_url() -> str:
    return OLLAMA_URL.rsplit("/", 1)[0] + "/tags"


def mark_ollama_unreachable() -> None:
    global _OLLAMA_UNREACHABLE_MEMO
    _OLLAMA_UNREACHABLE_MEMO = True


def clear_ollama_unreachable_memo() -> None:
    global _OLLAMA_UNREACHABLE_MEMO
    _OLLAMA_UNREACHABLE_MEMO = False


def ollama_is_unreachable(*, timeout: float = 0.2) -> bool:
    """Return True after a cheap Ollama health probe fails, memoizing failure."""
    if _OLLAMA_UNREACHABLE_MEMO:
        return True
    try:
        req = urllib.request.Request(_ollama_tags_url(), method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status = getattr(resp, "status", None)
            if status is None and hasattr(resp, "getcode"):
                status = resp.getcode()
            if status is not None and int(status) >= 500:
                mark_ollama_unreachable()
                return True
            return False
    except Exception:
        mark_ollama_unreachable()
        return True

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
        "gemma4:31b",
        "gemma4:26b",
        "gemma4:e4b",
    ),
    "cassandra_morning_brief_test": (
        "gemma4:e4b",
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
    "chief_user_reply": (
        "gemma4:26b",
        "gemma4:31b",
    ),
}

_TASK_CLASS_PREFERRED_LANES = {
    "cassandra_user_reply_fast": "fast",
    "cassandra_user_reply": "strong",
    "cassandra_outbound_draft": "strong",
    "cassandra_morning_brief": "strong",
    "cassandra_morning_brief_test": "fast",
    "cassandra_inbox_summary": "fast",
    "cassandra_morning_brief_fallback": "fast",
    "chief_evidence_scan": "fast",
    "chief_evidence_synthesis": "deep",
    "chief_structured_plan": "strong",
    "chief_user_reply": "strong",
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
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


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


def _external_model_log_name(provider: str, model: str) -> str:
    safe_provider = re.sub(r"[^A-Za-z0-9_.:/+-]+", "_", str(provider or "").strip())[:40]
    safe_model = re.sub(r"[^A-Za-z0-9_.:/+-]+", "_", str(model or "").strip())[:160]
    return f"{safe_provider or 'external'}:{safe_model or 'unknown'}"


def openrouter_call(
    prompt: str,
    *,
    model: str,
    metadata: dict | None,
    timeout: int = 30,
) -> str:
    """Call OpenRouter only for explicitly allowed external-model packets.

    The caller must provide a concrete OpenRouter model name and metadata that
    passes external_model_packet_policy(). This function reads only
    OPENROUTER_API_KEY from the environment and returns '' fail-closed.
    """
    prompt_text = str(prompt or "").strip()
    model_name = str(model or "").strip()
    if not prompt_text or not model_name or not isinstance(metadata, dict):
        return ""

    policy = external_model_packet_policy(prompt_text, metadata=dict(metadata))
    if not policy.get("external_model_safe"):
        return ""

    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    if not api_key:
        return ""

    payload = json.dumps({
        "model": model_name,
        "messages": [{"role": "user", "content": prompt_text}],
        "max_tokens": 1024,
    }).encode("utf-8")
    req = urllib.request.Request(
        OPENROUTER_URL,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
            "HTTP-Referer": "http://localhost/openclaw",
            "X-Title": "OpenClaw",
        },
        method="POST",
    )

    prompt_words = len(prompt_text.split())
    log_model = _external_model_log_name("openrouter", model_name)
    started = _time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status = getattr(resp, "status", None)
            if status is None and hasattr(resp, "getcode"):
                status = resp.getcode()
            if status is not None and not (200 <= int(status) < 300):
                _log_external_call(log_model, prompt_words, 0, int((_time.monotonic() - started) * 1000), False)
                return ""

            data = json.loads(resp.read().decode("utf-8"))
            choices = data.get("choices") if isinstance(data, dict) else None
            if not isinstance(choices, list) or not choices:
                _log_external_call(log_model, prompt_words, 0, int((_time.monotonic() - started) * 1000), False)
                return ""
            message = choices[0].get("message") if isinstance(choices[0], dict) else None
            content = message.get("content") if isinstance(message, dict) else None
            if not isinstance(content, str):
                _log_external_call(log_model, prompt_words, 0, int((_time.monotonic() - started) * 1000), False)
                return ""
            result = content.strip()
            if not result:
                _log_external_call(log_model, prompt_words, 0, int((_time.monotonic() - started) * 1000), False)
                return ""
            _log_external_call(log_model, prompt_words, len(result.split()), int((_time.monotonic() - started) * 1000), True)
            return result
    except Exception:
        _log_external_call(log_model, prompt_words, 0, int((_time.monotonic() - started) * 1000), False)
        return ""


def _configured_openrouter_model() -> str:
    """Return the configured OpenRouter model name, if any.

    This intentionally does not provide a baked-in cloud default. Choosing an
    external model is an operator/deployment decision, not a silent fallback.
    """
    for key in (
        "OPENCLAW_CASSANDRA_EXTERNAL_MODEL",
        "CASSANDRA_EXTERNAL_MODEL",
        "OPENCLAW_EXTERNAL_MODEL",
        "OPENROUTER_MODEL",
    ):
        value = os.environ.get(key, "").strip()
        if value:
            return value
    return ""


def external_language_model_call(
    prompt: str,
    *,
    metadata: dict | None,
    timeout: int = 30,
    model: str | None = None,
) -> str:
    """Use a configured external language model, then fail closed.

    OpenRouter is attempted only when a model has been explicitly configured and
    the packet passes the shared external-model policy. Nemotron remains a
    secondary external provider for existing deployments. All providers return
    an empty string on missing keys, blocked policy, or network failure.
    """
    prompt_text = str(prompt or "").strip()
    if not prompt_text or not isinstance(metadata, dict):
        return ""

    policy = external_model_packet_policy(prompt_text, metadata=dict(metadata))
    if not policy.get("external_model_safe"):
        return ""

    model_name = str(model or "").strip() or _configured_openrouter_model()
    if model_name:
        result = openrouter_call(
            prompt_text,
            model=model_name,
            metadata=dict(metadata),
            timeout=timeout,
        ).strip()
        if result:
            return result

    return nemotron_call(prompt_text, timeout=timeout).strip()


OLLAMA_MODEL      = os.environ.get("OPENCLAW_OLLAMA_MODEL", "qwen3:8b-q4_K_M")   # installed qwen, env-overridable
OLLAMA_MODEL_DEEP = os.environ.get("OPENCLAW_OLLAMA_MODEL_DEEP", "qwen3:8b-q4_K_M")  # env-overridable; bump to qwen3.6:latest if VRAM allows

CLAUDE_MODEL = "claude-sonnet-4-6"
CLAUDE_CLI   = "/home/openclaw/.local/bin/claude"

# External model packet policy -------------------------------------------------
#
# This is the shared deterministic gate for deciding whether a packet is safe
# to send to any external model or cloud runner. It intentionally does not try
# to sanitize or judge content with a model: callers must provide explicit
# cloud-allowed metadata, and protected professional/private markers block.

EXTERNAL_MODEL_SAFE_CLASSIFICATIONS = frozenset({
    "non_sensitive",
    "nonsensitive",
    "public",
    "public_fixture",
    "sanitized",
    "sanitized_public",
    "synthetic",
    "synthetic_public",
    "test_public",
})

EXTERNAL_MODEL_BLOCKED_CLASSIFICATIONS = frozenset({
    "client_matter",
    "confidential",
    "cpa",
    "financial",
    "gmail",
    "legal_matter",
    "matter",
    "music_law",
    "pii",
    "private",
    "publishing",
    "secret",
    "sensitive",
    "tax",
})

EXTERNAL_MODEL_BLOCK_MARKERS = frozenset({
    "/mnt/c/openclawlegalprivate",
    "openclawlegalprivate",
    ".env",
    "api key",
    "attorney",
    "billing record",
    "catalog registration",
    "client",
    "client identity",
    "client identities",
    "client matter",
    "confidential",
    "contract",
    "cpa",
    "credential",
    "dispute",
    "disputes",
    "expense",
    "gmail",
    "gmail body",
    "income",
    "invoice",
    "law firm",
    "legal matter",
    "matter",
    "music law",
    "oauth",
    "password",
    "payment",
    "pii",
    "pii vault",
    "private",
    "private correspondence",
    "private deal terms",
    "private key",
    "private rights",
    "private vault",
    "publishing",
    "publishing catalog",
    "registration",
    "registrations",
    "rights admin",
    "royalties",
    "royalty",
    "secret",
    "split sheet",
    "split sheets",
    "splits",
    "ssn",
    "tax",
    "token",
    "token file",
})

_EXTERNAL_MODEL_BLOCK_PATTERNS = (
    ("money_amount", re.compile(r"\$\s*\d|\b\d+(?:\.\d+)?\s*(?:dollars?|usd|bucks?)\b", re.IGNORECASE)),
)


def _policy_truthy(value) -> bool:
    return str(value).strip().lower() in {"true", "yes", "1", "y", "on"}


def _normalize_policy_value(value) -> str:
    return str(value).strip().lower().replace("-", "_").replace(" ", "_")


def _policy_text(value) -> str:
    if isinstance(value, dict):
        return " ".join(_policy_text(item) for item in value.values())
    if isinstance(value, (list, tuple, set)):
        return " ".join(_policy_text(item) for item in value)
    return str(value)


def external_model_packet_policy(packet="", metadata: dict | None = None) -> dict:
    """Return deterministic external-model/cloud eligibility for a packet.

    The result shape is intentionally plain so runner code, brains, and tests can
    share it without importing a policy framework.
    """
    meta = metadata or {}
    classification = _normalize_policy_value(
        meta.get("data_classification")
        or meta.get("classification")
        or meta.get("sensitivity")
        or meta.get("privacy")
        or ""
    )
    cloud_allowed = any(
        _policy_truthy(meta.get(key, ""))
        for key in ("cloud_allowed", "allow_cloud", "cloud_ok")
    )

    def blocked(reason: str, *, sensitive: bool) -> dict:
        return {
            "external_model_safe": False,
            "blocked": True,
            "sensitive": sensitive,
            "cloud_allowed": cloud_allowed,
            "classification": classification,
            "reason": reason,
        }

    if _policy_truthy(meta.get("local_required", "")):
        return blocked("local_required", sensitive=True)
    if _policy_truthy(meta.get("sensitive", "")):
        return blocked("sensitive_flag", sensitive=True)
    if classification in EXTERNAL_MODEL_BLOCKED_CLASSIFICATIONS:
        return blocked(f"blocked_classification:{classification}", sensitive=True)

    text_lower = _policy_text({"packet": packet, "metadata": meta}).lower()
    for marker in sorted(EXTERNAL_MODEL_BLOCK_MARKERS, key=len, reverse=True):
        if marker in text_lower:
            return blocked(f"blocked_marker:{marker}", sensitive=True)
    for pattern_name, pattern in _EXTERNAL_MODEL_BLOCK_PATTERNS:
        if pattern.search(text_lower):
            return blocked(f"blocked_pattern:{pattern_name}", sensitive=True)

    if not cloud_allowed:
        return blocked("cloud_not_explicitly_allowed", sensitive=False)
    if classification not in EXTERNAL_MODEL_SAFE_CLASSIFICATIONS:
        return blocked("classification_not_external_safe", sensitive=False)

    return {
        "external_model_safe": True,
        "blocked": False,
        "sensitive": False,
        "cloud_allowed": True,
        "classification": classification,
        "reason": "explicit_cloud_allowed_public_or_synthetic",
    }


def external_model_safe(packet="", metadata: dict | None = None) -> bool:
    return bool(external_model_packet_policy(packet, metadata).get("external_model_safe"))

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
_DEEP_TIMEOUT_FLOOR   = 300    # minimum timeout (s) when using 14b

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


def _ollama_model_sizes(force_refresh: bool = False) -> dict[str, float]:
    """Return {model_name: size_GB} by querying the Ollama /api/tags endpoint.

    Graceful: returns {} on ANY error (unreachable, bad JSON, missing fields).
    Cached for 60s like ``_ollama_installed_models``. The /api/tags ``size``
    field is bytes; we convert to GB (decimal, /1e9) to match disk-size budgets.
    """
    global _MODEL_SIZE_CACHE
    if not force_refresh and _MODEL_SIZE_CACHE is not None:
        cached_at, cached_sizes = _MODEL_SIZE_CACHE
        if (_time.time() - cached_at) < 60:
            return dict(cached_sizes)

    sizes: dict[str, float] = {}
    try:
        req = urllib.request.Request(_ollama_tags_url(), method="GET")
        with urllib.request.urlopen(req, timeout=2) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        for entry in (data.get("models") or []):
            if not isinstance(entry, dict):
                continue
            name = entry.get("name")
            size_bytes = entry.get("size")
            if isinstance(name, str) and isinstance(size_bytes, (int, float)) and size_bytes > 0:
                sizes[name] = float(size_bytes) / 1e9
    except Exception:
        sizes = {}

    _MODEL_SIZE_CACHE = (_time.time(), dict(sizes))
    return sizes


def FRONTDOOR_MODEL_ALLOWLIST() -> tuple[str, ...]:
    """Ordered (smallest-first) front-door latency ladder.

    Default ``_FRONTDOOR_MODEL_ALLOWLIST_DEFAULT``; overridable via
    ``OPENCLAW_FRONTDOOR_MODEL_ALLOWLIST`` (comma list). gemma4:26b/31b are hard
    filtered even when present in the environment override.
    """
    raw = os.environ.get("OPENCLAW_FRONTDOOR_MODEL_ALLOWLIST", "").strip()
    if not raw:
        return _FRONTDOOR_MODEL_ALLOWLIST_DEFAULT
    parsed = tuple(
        item.strip()
        for item in raw.split(",")
        if item.strip() and item.strip() not in _FRONTDOOR_MODEL_HARD_DENY
    )
    return parsed


def select_frontdoor_model(
    *,
    installed: set[str] | None = None,
    sizes: dict[str, float] | None = None,
    available_ram_gb: float | None = None,
    available_vram_gb: float | None = None,
    resident_vram_by_model_gb: dict[str, float] | None = None,
    max_gb: float | None = None,
) -> tuple[str | None, str]:
    """Pick the LARGEST allowlisted model that is installed AND fits the RAM/size budget.

    Sizing rule:
        budget_gb = min(available_ram_gb - headroom(4), OPENCLAW_FRONTDOOR_MODEL_MAX_GB[=12])
    From the allowlist (smallest-first), keep candidates that are installed and whose
    on-disk size is <= budget_gb, then return the LARGEST such (best quality within
    budget). The smallest-first ladder lets callers fall to smaller models at runtime
    when latency (measured live, not here) misses the budget.

    Returns (model_or_None, reason). gemma4:26b/31b never appear (not in the allowlist
    and also excluded by the size budget). installed/sizes/available_ram_gb are
    injectable for tests; default to live queries.
    """
    allowlist = FRONTDOOR_MODEL_ALLOWLIST()
    if installed is None:
        installed = _ollama_installed_models()
    if sizes is None:
        sizes = _ollama_model_sizes()

    if max_gb is None:
        try:
            max_gb = float(os.environ.get("OPENCLAW_FRONTDOOR_MODEL_MAX_GB", "").strip() or _FRONTDOOR_MODEL_MAX_GB_DEFAULT)
        except (TypeError, ValueError):
            max_gb = _FRONTDOOR_MODEL_MAX_GB_DEFAULT
    if max_gb <= 0:
        max_gb = _FRONTDOOR_MODEL_MAX_GB_DEFAULT

    budget_gb = max_gb
    if available_ram_gb is not None:
        ram_budget = float(available_ram_gb) - _FRONTDOOR_MODEL_RAM_HEADROOM_GB
        budget_gb = min(budget_gb, ram_budget)
    if available_vram_gb is not None:
        budget_gb = min(budget_gb, float(available_vram_gb))
    resident_vram_by_model_gb = dict(resident_vram_by_model_gb or {})

    # Walk smallest-first; collect installed candidates that fit the size budget.
    # The size table maps disk-size; a candidate with NO known size cannot be
    # proven to fit, so it is conservatively excluded from the fitting set.
    # An EMPTY ``installed`` set means "couldn't enumerate" (mirrors
    # _ollama_installed_models / resolve_local_model), so the installed filter is
    # skipped rather than read as "nothing installed".
    fitting: list[str] = []
    for candidate in allowlist:
        if installed and candidate not in installed:
            continue
        size_gb = sizes.get(candidate)
        if size_gb is None:
            continue
        ram_fits = True
        if available_ram_gb is not None:
            ram_fits = size_gb <= float(available_ram_gb) - _FRONTDOOR_MODEL_RAM_HEADROOM_GB
        if candidate in resident_vram_by_model_gb and size_gb <= max_gb and ram_fits:
            fitting.append(candidate)
            continue
        candidate_budget_gb = budget_gb
        if available_vram_gb is not None:
            candidate_budget_gb = min(
                max_gb,
                float(available_vram_gb) + float(resident_vram_by_model_gb.get(candidate, 0.0)),
            )
            if available_ram_gb is not None:
                candidate_budget_gb = min(
                    candidate_budget_gb,
                    float(available_ram_gb) - _FRONTDOOR_MODEL_RAM_HEADROOM_GB,
                )
        if size_gb <= candidate_budget_gb:
            fitting.append(candidate)

    if not fitting:
        return None, "no_fitting_model"
    # allowlist is smallest-first, so the LAST fitting entry is the largest fitting.
    chosen = fitting[-1]
    return chosen, "frontdoor_largest_fitting"


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
        return "cassandra production morning briefing uses the top gemma 4 lane with smaller local fallback"
    if task_class == "cassandra_morning_brief_test":
        return "cassandra morning briefing test mode uses the smallest installed gemma 4 lane"
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
    profile: str | None = None,
) -> tuple[str, str]:
    # Front-door profile path (additive, opt-in): return the latency-ladder pick from
    # select_frontdoor_model instead of the strong/gemma candidates. Reachable via
    # profile="frontdoor" OR task_class="frontdoor_reply". chief_user_reply is untouched.
    if profile == "frontdoor" or task_class == "frontdoor_reply":
        model, reason = select_frontdoor_model()
        return (model or ""), reason

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


# ── Agent-level default lane policy ──────────────────────────────────────────

AGENT_DEFAULT_LANES: dict[str, str] = {
    "cassandra":       "strong",
    "cassandra_brief": "strong",
    "chief_morning":   "deep",
    "chief_end_of_day":"deep",
    "guardian":        "fast",
}


def agent_default_lane(agent: str, slot: str | None = None) -> str:
    """Return the policy-default lane for an agent."""
    return AGENT_DEFAULT_LANES.get(agent, "strong")


def ollama_call(
    prompt: str,
    timeout: int = 15,
    model: str = None,
    lane: str | None = None,
    *,
    task_class: str | None = None,
    attempts: int | None = None,
    think: bool | None = None,
    num_predict: int | None = None,
    options: dict | None = None,
    keep_alive: str | None = None,
    return_metadata: bool = False,
) -> str | dict[str, object]:
    """Call Ollama and return raw text response. Returns '' on any error. Retries up to 3 times with backoff.

    model=None (default): auto-selects via should_escalate(), logs on escalation.
    model=<explicit>:     bypasses auto-escalation — used by Cassandra and tests
                          that have already made the routing decision.
    When using 14b (either path), timeout is raised to _DEEP_TIMEOUT_FLOOR.
    attempts=<n>:          optional caller budget override for latency-sensitive front-door paths.

    think / num_predict / options / keep_alive (ALL default None → payload BYTE-IDENTICAL to today):
        front-door-profile-only bounded options. When NONE of these are passed the
        json payload is exactly {"model","prompt","stream":False} as before. When
        think=False → payload gains "think": false. When num_predict=N → payload
        gains/merges "options":{"num_predict":N}. An explicit ``options`` dict is
        merged under the same "options" key without clobbering num_predict. When
        keep_alive is set, it is passed as Ollama's top-level keep_alive field.

    return_metadata=False preserves the legacy return shape (plain string). When True,
        return a dict containing text, done_reason, elapsed_ms, model, status, and
        response_metadata so front-door callers can classify truncation without
        affecting legacy callers.
    """
    selected_lane = lane
    models_to_try: tuple[str, ...]
    if model is not None:
        if model == OLLAMA_MODEL_DEEP:
            timeout = max(timeout, _DEEP_TIMEOUT_FLOOR)
        models_to_try = (model,)
    else:
        model, resolved_lane = resolve_local_model(prompt, lane=lane, task_class=task_class)
        selected_lane = resolved_lane
        if resolved_lane == "deep":
            timeout = max(timeout, _DEEP_TIMEOUT_FLOOR)
            print(f"[llm] routed → deep ({len(prompt.split())} words, timeout={timeout}s)",
                  flush=True)
        if task_class == "cassandra_morning_brief":
            installed = _ollama_installed_models()
            candidates = local_model_candidates(resolved_lane, task_class=task_class)
            models_to_try = tuple(candidate for candidate in candidates if not installed or candidate in installed)
            if not models_to_try:
                models_to_try = (model,)
        else:
            models_to_try = (model,)
    attempt_count = max(1, int(attempts)) if attempts is not None else 3
    if task_class == "cassandra_morning_brief" and attempts is None:
        timeout = max(timeout, _CASSANDRA_MORNING_BRIEF_TIMEOUT)
        attempt_count = max(1, _CASSANDRA_MORNING_BRIEF_ATTEMPTS)
    elif task_class == "cassandra_morning_brief_test" and attempts is None:
        timeout = max(timeout, _CASSANDRA_MORNING_TEST_TIMEOUT)
        attempt_count = _CASSANDRA_MORNING_TEST_ATTEMPTS
    prompt_words = len(prompt.split())

    def _metadata_response(
        *,
        text: str = "",
        done_reason: str | None = None,
        elapsed_ms: int | None = None,
        model_name: str | None = None,
        status: str = "failure",
        response_metadata: dict | None = None,
        exception: BaseException | None = None,
    ) -> dict[str, object]:
        payload: dict[str, object] = {
            "text": str(text or ""),
            "response": str(text or ""),
            "done_reason": done_reason,
            "elapsed_ms": elapsed_ms,
            "model": model_name,
            "status": status,
            "response_metadata": dict(response_metadata or {}),
        }
        if exception is not None:
            payload["exception_type"] = type(exception).__name__
            payload["exception"] = str(exception)
        return payload

    def _exception_done_reason(exc: BaseException) -> str:
        if isinstance(exc, (TimeoutError, socket.timeout)):
            return "timeout"
        name = type(exc).__name__.lower()
        text = str(exc).lower()
        if "timeout" in name or "timed out" in text or "timeout" in text:
            return "timeout"
        return "unreachable"

    # Merge bounded front-door options WITHOUT clobbering. When think / num_predict /
    # options are all None the resulting payload dict is byte-identical to the legacy
    # {"model","prompt","stream":False}; the extra keys are only inserted when a caller
    # opts in to the front-door profile, preserving DEFAULT-OFF byte-identity.
    merged_options: dict = dict(options) if isinstance(options, dict) else {}
    if num_predict is not None:
        merged_options["num_predict"] = num_predict
    for candidate_model in models_to_try:
        payload_dict: dict = {
            "model": candidate_model,
            "prompt": prompt,
            "stream": False,
        }
        if think is not None:
            payload_dict["think"] = bool(think)
        if merged_options:
            payload_dict["options"] = dict(merged_options)
        if keep_alive is not None and str(keep_alive).strip():
            payload_dict["keep_alive"] = str(keep_alive).strip()
        payload = json.dumps(payload_dict).encode("utf-8")
        req = urllib.request.Request(
            OLLAMA_URL,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        for attempt in range(attempt_count):
            started = _time.monotonic()
            try:
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    result = data.get("response", "").strip()
                    done_reason = data.get("done_reason")
                    response_metadata = {key: value for key, value in data.items() if key != "response"}
                    duration_ms = int((_time.monotonic() - started) * 1000)
                    _log_ollama_diagnostic({
                        "event": "ollama_call",
                        "status": "success" if result else "failure",
                        "attempt": attempt + 1,
                        "model": candidate_model,
                        "task_class": task_class,
                        "lane": selected_lane,
                        "timeout": timeout,
                        "duration_ms": duration_ms,
                        "elapsed_ms": duration_ms,
                        "done_reason": done_reason,
                        "num_predict": merged_options.get("num_predict"),
                        "think": payload_dict.get("think"),
                        "response_metadata": response_metadata,
                        "prompt_words": prompt_words,
                        "response_chars": len(result),
                        "empty_response": not bool(result),
                    })
                    if result:
                        if return_metadata:
                            return _metadata_response(
                                text=result,
                                done_reason=str(done_reason) if done_reason is not None else None,
                                elapsed_ms=duration_ms,
                                model_name=candidate_model,
                                status="success",
                                response_metadata=response_metadata,
                            )
                        return result
                    if return_metadata and attempt == attempt_count - 1:
                        return _metadata_response(
                            text="",
                            done_reason=str(done_reason) if done_reason is not None else None,
                            elapsed_ms=duration_ms,
                            model_name=candidate_model,
                            status="empty",
                            response_metadata=response_metadata,
                        )
            except Exception as e:
                duration_ms = int((_time.monotonic() - started) * 1000)
                done_reason = _exception_done_reason(e)
                _log_ollama_diagnostic({
                    "event": "ollama_call",
                    "status": "exception",
                    "attempt": attempt + 1,
                    "model": candidate_model,
                    "task_class": task_class,
                    "lane": selected_lane,
                    "timeout": timeout,
                    "duration_ms": duration_ms,
                    "elapsed_ms": duration_ms,
                    "done_reason": done_reason,
                    "num_predict": merged_options.get("num_predict"),
                    "think": payload_dict.get("think"),
                    "prompt_words": prompt_words,
                    "exception_type": type(e).__name__,
                    "exception": str(e),
                })
                if attempt < attempt_count - 1:
                    _time.sleep(2 ** attempt)
                    continue
                if return_metadata:
                    return _metadata_response(
                        text="",
                        done_reason=done_reason,
                        elapsed_ms=duration_ms,
                        model_name=candidate_model,
                        status="exception",
                        response_metadata={},
                        exception=e,
                    )
    if return_metadata:
        return _metadata_response(status="empty")
    return ""


def claude_call(prompt: str, timeout: int = 30, retries: int = 3) -> str:
    """Claude CLI is human-only; OpenClaw agents fail closed."""
    print("[chief_llm] claude_call blocked by policy: Claude CLI is human-only", flush=True)
    return ""


def claude_json(prompt: str, timeout: int = 20, retries: int = 3) -> dict | list:
    """Claude CLI JSON helper is blocked for OpenClaw agent-side use."""
    print("[chief_llm] claude_json blocked by policy: Claude CLI is human-only", flush=True)
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
