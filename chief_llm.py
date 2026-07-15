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
_FRONTDOOR_SYSTEM_LOAD_1M_HIGH_DEFAULT = 4.0
# Task 146: a "resident" model with offload_fraction (size_vram/size from /api/ps) below
# this floor is mostly CPU-offloaded and NOT fast (live 2026-07-07: fraction 0.4 -> 62s
# for 20 tokens) -- it loses residency preference in select_frontdoor_model.
_FRONTDOOR_OFFLOAD_FRACTION_MIN_DEFAULT = 0.8
_FRONTDOOR_SYSTEM_LOAD_PER_CPU_HIGH_DEFAULT = 0.75

# Hardware-fit ceiling for ALL local-model lanes (not just the front-door). A model whose
# on-disk size exceeds this never resolves on this box: gemma4:26b (~19GB) on a 24GB box
# swaps to ~0.75 tok/s and starves every other local model (it took the front-door brain
# DOWN -- the briefing scheduler's "strong" lane kept loading it). Default 12GB (VRAM card +
# a tolerable RAM spill); raised to the GPU card size on bigger rigs; env-overridable.
_LOCAL_MODEL_MAX_GB_DEFAULT = 12.0
_LOCAL_MODEL_MAX_GB_ENV = "OPENCLAW_LOCAL_MODEL_MAX_GB"

# Context-aware fit ceilings (operator policy 2026-06-29): interactive replies must fit the GPU
# card so they answer in real time; async/background work (briefs, synthesis, agentic code) may
# spill to RAM for better quality because the operator is not waiting.
_INTERACTIVE_MODEL_CEILING_GB = 8.0   # qwen3:8b (5.2) / qwen3.5:9b (6.6) / ornith:9b (5.6) fit; gemma4:e4b (9.6) + 14GB reasoners do not
_ASYNC_MODEL_CEILING_GB = 15.0        # magistral / mistral-small (14) allowed; 17GB+ (gemma4:26b/31b, qwen3.6, nemotron:30b) stay out — they swap-death this 24GB box
_ASYNC_MODEL_LONG_TIMEOUT_S = 3600    # a slow spilling async model must not be killed mid-generation

# Task classes whose work is background (operator not waiting) -> async ceiling + long timeout.
_ASYNC_TASK_CLASSES = frozenset({
    "cassandra_outbound_draft",
    "cassandra_morning_brief",
    "cassandra_morning_brief_test",
    "cassandra_morning_brief_fallback",
    "cassandra_inbox_summary",
    "cassandra_extract_classify",
    "chief_evidence_scan",
    "chief_evidence_synthesis",
    "chief_structured_plan",
    "chief_ambiguous_debug",
    "chief_agentic_code",
})
_ASYNC_LANES = frozenset({"deep", "code_challenger"})


def _is_async_workload(task_class: str | None, lane: str | None) -> bool:
    """True for background work (operator not waiting) -> bigger model + long timeout allowed."""
    return bool(task_class in _ASYNC_TASK_CLASSES or lane in _ASYNC_LANES)


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

# Candidates are PREFERENCE-ordered (best first); resolve_local_model returns the first installed
# candidate that fits the lane's ceiling. Interactive lanes (fast/strong) stay on card-fitting
# qwen models for real-time replies; async lanes (deep/code_challenger) may reach bigger models.
_LANE_CANDIDATES = {
    # fast = bounded/snappy work -> smallest quick model that fits fully on the card
    "fast": (
        "qwen3:4b",
        "qwen3:8b-q4_K_M",
        "nemotron-3-nano:4b",
    ),
    # strong = interactive user-facing reasoning -> qwen3:8b (clean + fully fits), then 4b
    "strong": (
        "qwen3:8b-q4_K_M",
        "qwen3:4b",
        "qwen3.5:9b",
    ),
    # deep = heavy async reasoning/synthesis -> reasoners first (spill OK, operator not waiting)
    "deep": (
        "magistral:latest",
        "mistral-small:latest",
        "qwen3.5:9b",
        "qwen3:8b-q4_K_M",
    ),
    # code_challenger = coding/builder work -> the coding specialist that fits the card
    "code_challenger": (
        "ornith:9b",
        "mistral-small:latest",
    ),
}

# Preference-ordered per task class. INTERACTIVE (operator waiting) classes stay on card-fitting
# qwen models for real-time replies; ASYNC classes (see _ASYNC_TASK_CLASSES) may reach bigger
# reasoners/coders that spill to RAM. gemma4:26b/31b are retired here — they swap-death this box.
_TASK_CLASS_MODEL_CANDIDATES = {
    # ── interactive (real-time) ───────────────────────────────────────────────
    "contract_semantic_vote": (
        "qwen3:8b-q4_K_M",
    ),
    "cassandra_user_reply_fast": (
        "qwen3:8b-q4_K_M",     # reuse the operator's resident interactive model
        "qwen3:4b",
    ),
    "cassandra_user_reply": (
        "qwen3:8b-q4_K_M",     # cleanest direct replies, fully fits the card
        "qwen3:4b",
    ),
    "chief_user_reply": (
        "qwen3:8b-q4_K_M",
        "qwen3:4b",
    ),
    # ── async (spill OK, operator not waiting) ────────────────────────────────
    "cassandra_outbound_draft": (
        "qwen3.5:9b",          # best quality that still fits, slower is fine for a draft
        "qwen3:8b-q4_K_M",
    ),
    "cassandra_morning_brief": (
        "qwen3.5:9b",          # near-26b quality without the box-kill (probe-confirmed)
        "magistral:latest",
        "qwen3:8b-q4_K_M",
    ),
    "cassandra_morning_brief_test": (
        "qwen3:4b",
        "qwen3:8b-q4_K_M",
    ),
    "cassandra_inbox_summary": (
        "qwen3:4b",
        "qwen3:8b-q4_K_M",
    ),
    "cassandra_extract_classify": (
        "qwen3:4b",
        "qwen3:8b-q4_K_M",
    ),
    "chief_evidence_scan": (
        "nemotron-3-nano:4b",
        "qwen3:4b",
    ),
    "chief_evidence_synthesis": (
        "magistral:latest",    # heavy reasoning; spill OK
        "mistral-small:latest",
        "qwen3.5:9b",
    ),
    "chief_structured_plan": (
        "magistral:latest",
        "qwen3.5:9b",
        "mistral-small:latest",
    ),
    "chief_ambiguous_debug": (
        "magistral:latest",
        "mistral-small:latest",
    ),
    "chief_agentic_code": (
        "ornith:9b",           # coding specialist, fits the card, fast
        "mistral-small:latest",
    ),
}

_TASK_CLASS_PREFERRED_LANES = {
    "contract_semantic_vote": "fast",
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


def _frontdoor_float_env(name: str, default: float) -> float:
    try:
        value = float(os.environ.get(name, "").strip() or default)
    except (TypeError, ValueError):
        return default
    return value if value > 0 else default


def _frontdoor_system_load_is_high(
    system_load_1m: float | None,
    cpu_count: int | None,
) -> bool:
    if system_load_1m is None:
        return False
    try:
        load_1m = float(system_load_1m)
    except (TypeError, ValueError):
        return False
    if load_1m < 0:
        return False

    absolute_threshold = _frontdoor_float_env(
        "OPENCLAW_FRONTDOOR_SYSTEM_LOAD_1M_HIGH",
        _FRONTDOOR_SYSTEM_LOAD_1M_HIGH_DEFAULT,
    )
    if load_1m >= absolute_threshold:
        return True

    try:
        cores = int(cpu_count or 0)
    except (TypeError, ValueError):
        cores = 0
    if cores <= 0:
        return False
    per_cpu_threshold = _frontdoor_float_env(
        "OPENCLAW_FRONTDOOR_SYSTEM_LOAD_PER_CPU_HIGH",
        _FRONTDOOR_SYSTEM_LOAD_PER_CPU_HIGH_DEFAULT,
    )
    return (load_1m / cores) >= per_cpu_threshold


def select_frontdoor_model(
    *,
    installed: set[str] | None = None,
    sizes: dict[str, float] | None = None,
    available_ram_gb: float | None = None,
    available_vram_gb: float | None = None,
    resident_vram_by_model_gb: dict[str, float] | None = None,
    offload_fraction_by_model: dict[str, float] | None = None,
    system_load_1m: float | None = None,
    cpu_count: int | None = None,
    max_gb: float | None = None,
) -> tuple[str | None, str]:
    """Pick the LARGEST allowlisted, installed model that fits the GPU card (and RAM).

    Fit rule (operator policy 2026-06-29 -- "fits in the 6GB card -> use it; spill to RAM
    is fine"):
        * ``max_gb`` is the card capacity / configured cap. A model fits the card when its
          on-disk size <= max_gb.
        * ``available_ram_gb`` - headroom(4) bounds RAM-backed spill.
        * A model that fits the card AND RAM CAN run (ollama spills overflow to RAM).
        * Among those, prefer the largest that ALSO fits currently-free VRAM (runs fully on
          the GPU = fast). If none fit free VRAM, fall back to the largest card-fit and let
          it spill to RAM rather than returning no model.
    The smallest-first ladder lets callers fall to smaller models at runtime when latency
    (measured live, not here) misses the budget.

    Task 146 (offload truth): "resident" alone never wins. ``offload_fraction_by_model``
    carries size_vram/size per resident model straight from /api/ps (see
    FrontdoorResourceSnapshot.offload_fraction_by_model). A resident candidate whose known
    fraction is below ``OPENCLAW_FRONTDOOR_OFFLOAD_FRACTION_MIN`` (default 0.8) is mostly
    CPU-offloaded and NOT fast (live 2026-07-07: fraction 0.4 -> 62s for 20 tokens), so it
    loses residency preference and competes as a plain free-VRAM fit; when that demotion
    hands the win to a smaller fully-fitting model the reason is
    ``frontdoor_offload_avoidance``. Fraction >= the floor or UNKNOWN (absent/None) keeps
    today's behavior byte-identical -- fail open, never guess.

    Returns (model_or_None, reason): ``frontdoor_largest_fitting`` (GPU-resident/fast),
    ``frontdoor_largest_fitting_ram_spill`` (fits the card, spills to RAM),
    ``frontdoor_step_down_system_load`` (high system load),
    ``frontdoor_offload_avoidance`` (partial-offload resident passed over), or
    ``no_fitting_model``.
    gemma4:26b/31b never appear (not in the allowlist, also too big).
    installed/sizes/available_ram_gb/available_vram_gb are injectable for tests; default to
    live queries.
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

    # ``max_gb`` is the GPU CARD capacity (total VRAM, e.g. 6GB on a 6GB card) AND the
    # configured size cap: a model fits the card when its on-disk size is <= max_gb.
    # ``available_ram_gb`` (minus headroom) bounds how much can spill to system RAM.
    #
    # A model CAN RUN if it fits the card AND fits RAM -- ollama keeps what fits in VRAM and
    # spills the remainder to system RAM. It runs FAST (fully GPU-resident, no spill) only if
    # it ALSO fits in currently-free VRAM. Operator policy (2026-06-29): prefer the fast,
    # free-VRAM fit for latency, but FALL BACK to a card-fit-with-RAM-spill rather than
    # refusing to answer. The earlier code gated the fit itself on FREE VRAM, so a tight-VRAM
    # box returned no_fitting_model and the brain fell to a deterministic dump.
    ram_budget = None
    if available_ram_gb is not None:
        ram_budget = float(available_ram_gb) - _FRONTDOOR_MODEL_RAM_HEADROOM_GB
    resident_vram_by_model_gb = dict(resident_vram_by_model_gb or {})
    offload_fraction_by_model = dict(offload_fraction_by_model or {})
    offload_fraction_min = _frontdoor_float_env(
        "OPENCLAW_FRONTDOOR_OFFLOAD_FRACTION_MIN",
        _FRONTDOOR_OFFLOAD_FRACTION_MIN_DEFAULT,
    )

    # Walk smallest-first. A candidate with NO known size cannot be proven to fit, so it is
    # conservatively excluded. An EMPTY ``installed`` set means "couldn't enumerate" (mirrors
    # _ollama_installed_models / resolve_local_model), so the installed filter is skipped
    # rather than read as "nothing installed".
    card_fitting: list[str] = []  # fits the card (+RAM) -> CAN run, possibly with RAM spill
    vram_fitting: list[str] = []  # ALSO fits free VRAM (or already resident) -> runs fast
    offload_demoted: set[str] = set()  # resident but mostly CPU-offloaded -> NOT fast (146)
    for candidate in allowlist:
        if installed and candidate not in installed:
            continue
        size_gb = sizes.get(candidate)
        if size_gb is None:
            continue
        if size_gb > max_gb:
            continue  # bigger than the card / configured cap -> cannot run on this GPU
        if ram_budget is not None and size_gb > ram_budget:
            continue  # not enough system RAM to back it even with spill
        card_fitting.append(candidate)
        resident_gb = float(resident_vram_by_model_gb.get(candidate, 0.0))
        fraction = offload_fraction_by_model.get(candidate)
        partially_offloaded = (
            isinstance(fraction, (int, float)) and float(fraction) < offload_fraction_min
        )
        if resident_gb > 0.0 and partially_offloaded:
            # Task 146: /api/ps says "resident" but the KNOWN offload fraction says mostly
            # CPU-offloaded (live 2026-07-07: size 6.0GB, size_vram 2.4GB -> 0.4, a 62s
            # 20-token reply). Residency preference would keep re-selecting the slow model,
            # so it competes as a plain free-VRAM fit instead. UNKNOWN fraction never lands
            # here -- selection stays byte-identical to today (fail open).
            offload_demoted.add(candidate)
            if available_vram_gb is None or size_gb <= float(available_vram_gb):
                vram_fitting.append(candidate)
        elif resident_gb > 0.0:
            # Already loaded -> keep it (no reload/evict cost), counts as a GPU-resident fit.
            vram_fitting.append(candidate)
        elif available_vram_gb is None or size_gb <= float(available_vram_gb):
            vram_fitting.append(candidate)

    # allowlist is smallest-first. For the interactive front door, free-VRAM contention
    # should step down to the smallest local model that can answer instead of selecting
    # a larger spill candidate and risking the deterministic floor.
    if (
        len(card_fitting) > 1
        and _frontdoor_system_load_is_high(system_load_1m, cpu_count)
    ):
        return card_fitting[0], "frontdoor_step_down_system_load"
    if vram_fitting:
        selected = vram_fitting[-1]
        is_resident = (
            float(resident_vram_by_model_gb.get(selected, 0.0)) > 0.0
            and selected not in offload_demoted
        )
        if card_fitting and selected != card_fitting[-1]:
            skipped_larger = card_fitting[card_fitting.index(selected) + 1 :]
            if any(candidate in offload_demoted for candidate in skipped_larger):
                # A larger "resident" candidate was passed over BECAUSE its known offload
                # fraction says it is mostly CPU-offloaded: the fully-fitting smaller
                # model wins. Labeled distinctly so the audit can count how often the
                # offload truth (not generic VRAM contention) drove the step-down.
                reason = "frontdoor_offload_avoidance"
            else:
                reason = "frontdoor_step_down_vram_contention"
        elif is_resident:
            # Operator policy 2026-07-07: reusing an already-resident model has ~zero marginal
            # VRAM cost, so it's the default over evicting-and-reloading a "colder" fit. Labeled
            # distinctly from frontdoor_largest_fitting so the audit can tell residency-driven
            # selections apart from a fresh free-VRAM fit.
            reason = "frontdoor_resident_reuse"
        else:
            reason = "frontdoor_largest_fitting"
        return selected, reason
    if card_fitting:
        if available_vram_gb is not None:
            return card_fitting[0], "frontdoor_step_down_vram_contention_ram_spill"
        return card_fitting[-1], "frontdoor_largest_fitting_ram_spill"
    return None, "no_fitting_model"


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


def _local_model_size_ceiling_gb(task_class: str | None = None, lane: str | None = None) -> float:
    """Max on-disk size (GB) a local model may have to resolve, by workload tier.

    ``OPENCLAW_LOCAL_MODEL_MAX_GB`` overrides both tiers. Otherwise INTERACTIVE workloads (operator
    waiting) cap at the card-fit ceiling so replies are real time, while ASYNC/background work
    (briefs, synthesis, agentic code -- see _is_async_workload) may spill to a larger model because
    the operator is not waiting. gemma4:26b/31b exceed even the async ceiling (swap-death).
    """
    env_val = os.environ.get(_LOCAL_MODEL_MAX_GB_ENV, "").strip()
    if env_val:
        try:
            parsed = float(env_val)
            if parsed > 0:
                return parsed
        except (TypeError, ValueError):
            pass
    if _is_async_workload(task_class, lane):
        return _ASYNC_MODEL_CEILING_GB
    return _INTERACTIVE_MODEL_CEILING_GB


def _effective_model_timeout(timeout: int, model: str, sizes: dict[str, float] | None = None) -> int:
    """Stretch the timeout for a big (spilling) model so it is not killed mid-generation.

    Operator policy 2026-06-29: "timeouts basically off when a big model gets used." A model whose
    on-disk size exceeds the interactive card ceiling is necessarily an async/spill model running
    slowly off CPU -- give it _ASYNC_MODEL_LONG_TIMEOUT_S. Small card-fitting models keep the
    caller's (short, real-time) timeout.
    """
    if sizes is None:
        sizes = _ollama_model_sizes()
    size_gb = sizes.get(model)
    if size_gb is not None and float(size_gb) > _INTERACTIVE_MODEL_CEILING_GB:
        return max(int(timeout or 0), _ASYNC_MODEL_LONG_TIMEOUT_S)
    return timeout


def _largest_fitting_installed_model(
    candidates: tuple[str, ...],
    installed: set[str],
    sizes: dict[str, float],
    ceiling_gb: float,
) -> str | None:
    """First (preference-order) installed candidate whose KNOWN size <= ceiling_gb.

    Candidates are largest-first, so the first match is the largest model that fits. A candidate
    with no known size cannot be proven to fit and is skipped in favour of a known-fitting one.
    Returns None when no installed candidate has a known fitting size (caller keeps the legacy
    first-installed pick — fail OPEN, never block resolution).
    """
    for candidate in candidates:
        if candidate not in installed:
            continue
        size_gb = sizes.get(candidate)
        if size_gb is None:
            continue
        if float(size_gb) <= ceiling_gb:
            return candidate
    return None


def _largest_fitting_installed_overall(
    installed: set[str],
    sizes: dict[str, float],
    ceiling_gb: float,
    prefer_family: str | None = None,
) -> str | None:
    """Largest installed model with KNOWN size <= ceiling_gb, preferring ``prefer_family``.

    Used when a lane's ENTIRE candidate list is oversized (e.g. cassandra_user_reply is only
    gemma4:26b/31b): rather than fail open to an oversized model that swaps and starves the
    fleet, downshift to the biggest model that actually fits this box, keeping the lane's family
    (the part before ':') when a fitting same-family model exists. None when nothing fits.
    """
    fitting = sorted(
        (
            (float(sizes[model]), model)
            for model in installed
            if sizes.get(model) is not None and float(sizes[model]) <= ceiling_gb
        ),
        reverse=True,
    )
    if not fitting:
        return None
    if prefer_family:
        for _size, model in fitting:
            if model.split(":", 1)[0] == prefer_family:
                return model
    return fitting[0][1]


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
    # Hardware-fit ceiling (2026-06-29): never resolve to a model too big for this box. The
    # briefing scheduler's strong/gemma lanes kept loading gemma4:26b (~19GB), which swapped on
    # this 24GB box and starved the front-door brain (took it DOWN). Downshift to the largest
    # installed candidate that fits; the smaller lane fallbacks (e.g. gemma4:e4b) exist for
    # exactly this. Fail OPEN to the legacy first-installed pick when nothing known fits.
    sizes = _ollama_model_sizes()
    ceiling_gb = _local_model_size_ceiling_gb(task_class=task_class, lane=selected_lane)
    fitted = _largest_fitting_installed_model(candidates, installed, sizes, ceiling_gb)
    if fitted is not None:
        return fitted, selected_lane
    # The lane's whole candidate list is oversized -> downshift to the largest installed model
    # that fits this box, preferring the lane's model family. Guarantees no oversized model ever
    # loads (and re-starves the fleet) while a fitting one is installed.
    family = candidates[0].split(":", 1)[0] if candidates else None
    overall = _largest_fitting_installed_overall(installed, sizes, ceiling_gb, prefer_family=family)
    if overall is not None:
        return overall, selected_lane
    # Pathological: nothing installed fits the ceiling -> legacy first-installed pick (fail open).
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
    _model_slot_held: bool = False,
    _governance_bypass: bool = False,
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
    if _is_async_workload(task_class, lane) and not _governance_bypass:
        from local_model_governance import run_async_model_call

        governed = run_async_model_call(
            lambda: ollama_call(
                prompt,
                timeout=timeout,
                model=model,
                lane=lane,
                task_class=task_class,
                attempts=attempts,
                think=think,
                num_predict=num_predict,
                options=options,
                keep_alive="0",
                return_metadata=return_metadata,
                _model_slot_held=True,
                _governance_bypass=True,
            ),
            task_class=str(task_class or lane or "async_model_call"),
            holder_id=f"async:{task_class or lane or 'model'}:{os.getpid()}",
            model_slot_already_held=_model_slot_held,
        )
        if governed.status == "completed":
            return governed.value
        if return_metadata:
            return {
                "text": "",
                "response": "",
                "done_reason": "interactive_reserved",
                "elapsed_ms": 0,
                "model": model,
                "status": "deferred",
                "response_metadata": {"governance_reason": governed.reason},
            }
        return ""

    selected_lane = lane
    models_to_try: tuple[str, ...]
    if model is not None:
        # The deep floor protects a genuinely BIG deep model from being killed
        # mid-generation. After the 2026-06-29 retiering OLLAMA_MODEL_DEEP can be
        # the SAME card-fit model as the interactive lane; flooring on name
        # equality alone stretched every 44s front-door call to 300s. Only floor
        # when deep is a distinct model from the standard interactive one — the
        # size-aware _effective_model_timeout still stretches real spill models.
        if model == OLLAMA_MODEL_DEEP and OLLAMA_MODEL_DEEP != OLLAMA_MODEL:
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
    # Reserved key: Ollama's grammar-constrained output lives at the TOP level of
    # the payload, not under options. Callers opt in via options={"format": "json"};
    # without it the payload stays byte-identical to before.
    response_format = merged_options.pop("format", None)
    for candidate_model in models_to_try:
        # Operator policy 2026-06-29: a big (spilling) model must not be killed mid-generation ->
        # stretch its timeout. Small card-fitting models keep the caller's short real-time timeout.
        effective_timeout = _effective_model_timeout(timeout, candidate_model)
        payload_dict: dict = {
            "model": candidate_model,
            "prompt": prompt,
            "stream": False,
        }
        if think is not None:
            payload_dict["think"] = bool(think)
        if merged_options:
            payload_dict["options"] = dict(merged_options)
        if response_format:
            payload_dict["format"] = response_format
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
                with urllib.request.urlopen(req, timeout=effective_timeout) as resp:
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
                        "timeout": effective_timeout,
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
