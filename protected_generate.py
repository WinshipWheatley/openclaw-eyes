"""PII-safe model gate for Maestro and future agent free-form reasoning."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import inspect
import json
import os
from pathlib import Path
import re
import time
from typing import Any, Callable, Mapping

from agent_perspective import perspective_prompt


DEFAULT_AUDIT_LOG = Path("/mnt/c/OpenClaw/logs/protected_generate_audit.jsonl")
DEFAULT_EXTERNAL_TIMEOUT_SECONDS = 6.0
DEFAULT_LOCAL_TIMEOUT_SECONDS = 6.0
DEFAULT_LOCAL_ATTEMPTS = 1
DEFAULT_FRONTDOOR_NUM_PREDICT = 200
DEFAULT_FRONTDOOR_MODEL_MAX_GB = 6.0
MAX_FRONTDOOR_TIMEOUT_SECONDS = 45.0
PUBLIC = "PUBLIC"
LIGHT = "LIGHT"
MED = "MED"
HIGH = "HIGH"
MAX = "MAX"


@dataclass(frozen=True)
class ProtectedGenerateOutcome:
    status: str
    text: str
    receipt: dict[str, Any]


class ProtectedGenerateBlocked(RuntimeError):
    """Raised only for callers that opt into exceptions; default is a blocked outcome."""


class _TokenLedger:
    def __init__(self) -> None:
        self._by_value: dict[str, str] = {}
        self._values: dict[str, str] = {}
        self._counters: dict[str, int] = {}

    def add(self, kind: str, value: str) -> str:
        clean_kind = re.sub(r"[^A-Z0-9_]+", "_", str(kind or "SECRET").upper()).strip("_") or "SECRET"
        if value in self._by_value:
            return self._by_value[value]
        self._counters[clean_kind] = self._counters.get(clean_kind, 0) + 1
        token = f"[{clean_kind}_{self._counters[clean_kind]}]"
        self._by_value[value] = token
        self._values[token] = value
        return token

    def token_count(self) -> int:
        return len(self._values)

    def rehydrate(self, text: str) -> str:
        result = str(text or "")
        for token, value in self._values.items():
            result = result.replace(token, value)
        return result


TOKEN_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("SECRET", re.compile(r"\b(?:sk-[A-Za-z0-9_-]{12,}|AIza[0-9A-Za-z_-]{20,}|Bearer\s+[A-Za-z0-9._~+/=-]{16,})\b")),
    ("PEM_KEY", re.compile(r"-----BEGIN [A-Z ]+PRIVATE KEY-----.*?-----END [A-Z ]+PRIVATE KEY-----", re.DOTALL)),
    ("CREDIT_CARD", re.compile(r"\b(?:\d{4}[-\s]){3}\d{4}\b")),
    ("SSN", re.compile(r"\b\d{3}[ -]?\d{2}[ -]?\d{4}\b")),
    ("EMAIL", re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b")),
    ("PHONE", re.compile(r"\b(?:\+?\d{1,3}[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?)\d{3}[-.\s]?\d{4}\b")),
    ("ACCOUNT", re.compile(r"\b(?:acct|account|routing|iban|ledger)\s*(?:no\.?|number|#|:)?\s*([A-Z]{2}\d{2}[A-Z0-9]{10,30}|\d{8,20})\b", re.IGNORECASE)),
)

ORG_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("ORG", re.compile(r"\bCapital Hilton\b")),
    ("ORG", re.compile(r"\bSt\.?\s+Anne'?s\b", re.IGNORECASE)),
    ("ORG", re.compile(r"\bLive Arts MD\b")),
    ("PERSON", re.compile(r"\bWill Valcovic\b")),
)
MONEY_PATTERN = re.compile(r"\$\s*\d[\d,]*(?:\.\d{2})?|\b\d+(?:\.\d+)?\s*(?:dollars?|usd|bucks?)\b", re.IGNORECASE)
LONG_NUMBER_PATTERN = re.compile(r"\b\d{7,}\b")
LEGAL_RAW_PATTERNS = (
    re.compile(r"/mnt/[ce]/OpenClawLegalPrivate\b", re.IGNORECASE),
    re.compile(r"\bOpenClawLegalPrivate\b", re.IGNORECASE),
    re.compile(r"\bLegalPrivate\b", re.IGNORECASE),
    re.compile(r"\blegal discovery\b", re.IGNORECASE),
    re.compile(r"\battorney[- ]client\b", re.IGNORECASE),
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _now_ms() -> int:
    return int(time.monotonic() * 1000)


def _stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def _sha256(text: str) -> str:
    return "sha256:" + hashlib.sha256(str(text or "").encode("utf-8")).hexdigest()


def _packet_text(context_packet: Mapping[str, Any] | str | None) -> str:
    if context_packet is None:
        return ""
    if isinstance(context_packet, str):
        return context_packet
    if isinstance(context_packet, Mapping):
        packet_text = context_packet.get("packet_text")
        if isinstance(packet_text, str) and packet_text.strip():
            return packet_text
        return _stable_json(context_packet)
    return str(context_packet)


def _packet_mapping(context_packet: Mapping[str, Any] | str | None) -> Mapping[str, Any]:
    return context_packet if isinstance(context_packet, Mapping) else {}


def _contains(patterns: tuple[re.Pattern[str], ...], text: str) -> bool:
    return any(pattern.search(text) for pattern in patterns)


def _legal_fully_tokenized(prompt: str, context_packet: Mapping[str, Any]) -> bool:
    privacy = context_packet.get("privacy") if isinstance(context_packet.get("privacy"), Mapping) else {}
    if privacy.get("legal_discovery_fully_tokenized") is True:
        return True
    text = f"{prompt}\n{_packet_text(context_packet)}"
    if _contains(LEGAL_RAW_PATTERNS, text):
        return False
    return bool(re.search(r"\[(?:LEGAL|LEGAL_DOC|LEGAL_ENTITY|MAX)_\d+\]", text))


def detect_pii_tier(prompt: str, context_packet: Mapping[str, Any] | str | None = None) -> str:
    packet = _packet_mapping(context_packet)
    text = f"{prompt}\n{_packet_text(context_packet)}"
    privacy = packet.get("privacy") if isinstance(packet.get("privacy"), Mapping) else {}
    tiers = [str(item).upper() for item in privacy.get("tiers_present", ())] if isinstance(privacy.get("tiers_present"), list) else []
    if "MAX" in tiers or _contains(LEGAL_RAW_PATTERNS, text):
        return MAX
    if "HIGH" in tiers or re.search(r"\b(ssn|social security|medical|health|tax id)\b", text, re.IGNORECASE):
        return HIGH
    if "MED" in tiers or re.search(r"\b(email|gmail|calendar|meeting|invoice|recipient)\b", text, re.IGNORECASE):
        return MED
    if "LIGHT" in tiers or re.search(r"\b(bank|finance|financial|ledger|payment|paid|owed|coupa|receivable)\b", text, re.IGNORECASE):
        return LIGHT
    return PUBLIC


def _apply_patterns(text: str, ledger: _TokenLedger, patterns: tuple[tuple[str, re.Pattern[str]], ...]) -> str:
    result = str(text or "")
    for kind, pattern in patterns:
        def repl(match: re.Match[str], _kind: str = kind) -> str:
            value = match.group(1) if match.lastindex else match.group(0)
            token = ledger.add(_kind, value)
            if match.lastindex:
                return match.group(0).replace(value, token)
            return token

        result = pattern.sub(repl, result)
    return result


def tokenize_text_for_tier(text: str, tier: str, ledger: _TokenLedger | None = None) -> tuple[str, _TokenLedger]:
    token_ledger = ledger or _TokenLedger()
    normalized_tier = str(tier or PUBLIC).upper()
    result = _apply_patterns(str(text or ""), token_ledger, TOKEN_PATTERNS)
    if normalized_tier in {MED, HIGH, MAX}:
        result = _apply_patterns(result, token_ledger, ORG_PATTERNS)
    if normalized_tier in {HIGH, MAX}:
        result = MONEY_PATTERN.sub(lambda match: token_ledger.add("MONEY", match.group(0)), result)
        result = LONG_NUMBER_PATTERN.sub(lambda match: token_ledger.add("NUMBER", match.group(0)), result)
    if normalized_tier == MAX:
        for pattern in LEGAL_RAW_PATTERNS:
            result = pattern.sub(lambda match: token_ledger.add("LEGAL", match.group(0)), result)
    return result, token_ledger


def _tokenize_packet(context_packet: Mapping[str, Any] | str | None, tier: str, ledger: _TokenLedger) -> str:
    text = _packet_text(context_packet)
    tokenized, _ledger = tokenize_text_for_tier(text, tier, ledger)
    return tokenized


def _is_maestro_frontdoor_packet(context_packet: Mapping[str, Any] | str | None) -> bool:
    packet = _packet_mapping(context_packet)
    return (
        str(packet.get("schema_version") or "") == "maestro_context_packet_v0"
        and str(packet.get("packet_id") or "").startswith("maestro_context_packet:")
    )


def _frontdoor_model_profile_flag_enabled() -> bool:
    return os.environ.get("OPENCLAW_FRONTDOOR_MODEL_PROFILE", "0").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _frontdoor_profile_active(
    explicit: bool | None,
    context_packet: Mapping[str, Any] | str | None,
) -> bool:
    if explicit is not None:
        return bool(explicit)
    return _frontdoor_model_profile_flag_enabled() and _is_maestro_frontdoor_packet(context_packet)


def _frontdoor_timeout_from_env() -> float | None:
    raw = os.environ.get("OPENCLAW_FRONTDOOR_REPLY_TIMEOUT")
    if raw is None or not raw.strip():
        return None
    try:
        value = float(raw)
    except ValueError:
        return None
    if value <= 0 or value > MAX_FRONTDOOR_TIMEOUT_SECONDS:
        return None
    return value


def _frontdoor_num_predict() -> int:
    return _int_env("OPENCLAW_FRONTDOOR_NUM_PREDICT", DEFAULT_FRONTDOOR_NUM_PREDICT)


def _frontdoor_optional_int_env(name: str) -> int | None:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return None
    try:
        value = int(raw)
    except ValueError:
        return None
    return value if value > 0 else None


def _frontdoor_ollama_options() -> dict[str, int]:
    options: dict[str, int] = {}
    num_ctx = _frontdoor_optional_int_env("OPENCLAW_FRONTDOOR_NUM_CTX")
    num_gpu = _frontdoor_optional_int_env("OPENCLAW_FRONTDOOR_NUM_GPU")
    if num_ctx is not None:
        options["num_ctx"] = num_ctx
    if num_gpu is not None:
        options["num_gpu"] = num_gpu
    return options


def _frontdoor_keep_alive() -> str | None:
    value = os.environ.get("OPENCLAW_FRONTDOOR_KEEP_ALIVE")
    if value is None:
        return None
    value = value.strip()
    return value or None


def _frontdoor_model_max_gb() -> float:
    raw = os.environ.get("OPENCLAW_FRONTDOOR_MODEL_MAX_GB")
    if raw is None or not raw.strip():
        return DEFAULT_FRONTDOOR_MODEL_MAX_GB
    try:
        value = float(raw)
    except ValueError:
        return DEFAULT_FRONTDOOR_MODEL_MAX_GB
    return value if value > 0 else DEFAULT_FRONTDOOR_MODEL_MAX_GB


def _tokenized_frontdoor_packet(
    packet: Mapping[str, Any],
    tier: str,
    ledger: _TokenLedger,
) -> dict[str, Any]:
    """Return a structured packet copy whose model-facing string fields are tokenized."""
    tokenized: dict[str, Any] = dict(packet)
    raw_facts = packet.get("facts") if isinstance(packet, Mapping) else None
    facts: list[dict[str, Any]] = []
    for fact in (raw_facts or ()):
        if not isinstance(fact, Mapping):
            continue
        clean_fact: dict[str, Any] = dict(fact)
        for key in ("topic", "label", "value", "source_ref", "provenance"):
            if key in clean_fact:
                clean_fact[key], _ = tokenize_text_for_tier(str(clean_fact.get(key) or ""), tier, ledger)
        facts.append(clean_fact)
    tokenized["facts"] = facts
    question = tokenized.get("question")
    if isinstance(question, str):
        tokenized["question"], _ = tokenize_text_for_tier(question, tier, ledger)
    return tokenized


def _model_result_tuple(result: Any) -> tuple[str, str | None, int | None, dict[str, Any]]:
    if isinstance(result, Mapping):
        text = str(result.get("text") or result.get("response") or "")
        done = result.get("done_reason")
        elapsed = result.get("elapsed_ms") or result.get("model_elapsed_ms")
        try:
            elapsed_ms = int(elapsed) if elapsed is not None else None
        except (TypeError, ValueError):
            elapsed_ms = None
        metadata = result.get("response_metadata") or result.get("metadata") or {}
        return text, (str(done) if done is not None else None), elapsed_ms, dict(metadata) if isinstance(metadata, Mapping) else {}
    return str(result or ""), None, None, {}


def _metadata_for_tier(tier: str, token_count: int) -> dict[str, Any]:
    if tier == PUBLIC:
        return {"classification": "public", "cloud_allowed": True, "tokenization_applied": False}
    return {
        "classification": "private",
        "cloud_allowed": False,
        "local_required": True,
        "tokenization_applied": token_count > 0,
        "sensitive": tier in {HIGH, MAX},
    }


def _call_generator(generator_fn: Callable[..., str], prompt: str, **kwargs: Any) -> str:
    try:
        signature = inspect.signature(generator_fn)
    except (TypeError, ValueError):
        signature = None
    if signature is not None:
        params = signature.parameters
        if any(param.kind == inspect.Parameter.VAR_KEYWORD for param in params.values()):
            return str(generator_fn(prompt, **kwargs) or "")
        accepted = {key: value for key, value in kwargs.items() if key in params}
        return str(generator_fn(prompt, **accepted) or "")
    try:
        return str(generator_fn(prompt, **kwargs) or "")
    except TypeError:
        return str(generator_fn(prompt) or "")


def _call_generator_capturing(
    generator_fn: Callable[..., Any], prompt: str, **kwargs: Any
) -> tuple[str, str | None, int | None, dict[str, Any]]:
    """Call a front-door generator and surface text + metadata.

    The generator may return either plain text (str) — done_reason unknown — or a
    Mapping carrying {"text"/"response", "done_reason", "elapsed_ms",
    "response_metadata"} so the caller can classify truncation. Anything else is
    coerced to str with done_reason=None.
    """
    try:
        signature = inspect.signature(generator_fn)
    except (TypeError, ValueError):
        signature = None
    if signature is not None:
        params = signature.parameters
        if any(param.kind == inspect.Parameter.VAR_KEYWORD for param in params.values()):
            result = generator_fn(prompt, **kwargs)
        else:
            accepted = {key: value for key, value in kwargs.items() if key in params}
            result = generator_fn(prompt, **accepted)
    else:
        try:
            result = generator_fn(prompt, **kwargs)
        except TypeError:
            result = generator_fn(prompt)

    return _model_result_tuple(result)


def _live_model_allowed(explicit: bool | None = None) -> bool:
    if explicit is not None:
        return explicit
    if os.environ.get("OPENCLAW_TEST_MODE") == "1":
        return False
    return os.environ.get("OPENCLAW_MAESTRO_BRAIN_LIVE", "1").strip().lower() not in {"0", "false", "no", "off"}


def _float_env(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        value = float(raw)
    except ValueError:
        return default
    return value if value > 0 else default


def _int_env(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if value > 0 else default


def _call_local_ollama(
    prompt: str,
    *,
    timeout: float,
    attempts: int,
    model: str | None = None,
    task_class: str = "chief_user_reply",
    think: bool | None = None,
    num_predict: int | None = None,
    options: Mapping[str, Any] | None = None,
    keep_alive: str | None = None,
    return_metadata: bool = False,
) -> Any:
    from chief_llm import ollama_call

    try:
        signature = inspect.signature(ollama_call)
    except (TypeError, ValueError):
        signature = None
    kwargs: dict[str, Any] = {
        "timeout": timeout,
        "task_class": task_class,
    }
    if model:
        kwargs["model"] = model
    if signature is not None and (
        "attempts" in signature.parameters
        or any(param.kind == inspect.Parameter.VAR_KEYWORD for param in signature.parameters.values())
    ):
        kwargs["attempts"] = attempts
    for key, value in {
        "think": think,
        "num_predict": num_predict,
        "return_metadata": return_metadata,
    }.items():
        if signature is None or key in signature.parameters or any(
            param.kind == inspect.Parameter.VAR_KEYWORD for param in signature.parameters.values()
        ):
            kwargs[key] = value
    for key, value in {
        "options": dict(options) if options else None,
        "keep_alive": keep_alive,
    }.items():
        if value is not None and (
            signature is None or key in signature.parameters or any(
                param.kind == inspect.Parameter.VAR_KEYWORD for param in signature.parameters.values()
            )
        ):
            kwargs[key] = value
    result = ollama_call(prompt, **kwargs)
    if return_metadata:
        return result
    return str(result or "")


QUESTION_STOP_WORDS = frozenset(
    {
        "about",
        "across",
        "and",
        "are",
        "can",
        "could",
        "does",
        "for",
        "from",
        "have",
        "how",
        "into",
        "know",
        "like",
        "look",
        "next",
        "now",
        "status",
        "tell",
        "that",
        "the",
        "this",
        "today",
        "what",
        "whats",
        "what's",
        "when",
        "where",
        "which",
        "with",
        "would",
        "you",
        "your",
        # 000i: conversational/meta filler verbs — not business content. Because
        # _fact_match_score does naive substring matching, "need" (in "I NEED to
        # understand X") matched a finance fact whose value contained "need", so
        # "explain X" wrongly out-scored honesty and returned an invoice. Same
        # collision family as the 000h gig/day fix.
        "better",
        "explain",
        "explaining",
        "explains",
        "mean",
        "meant",
        "means",
        "need",
        "needed",
        "needs",
        "say",
        "said",
        "saying",
        "says",
        "think",
        "thinking",
        "thinks",
        "understand",
        "understands",
        "want",
        "wanted",
        "wants",
        "wonder",
        "wondering",
        # 000i (extended, per AGY-G validation): more conversational filler verbs/adverbs
        # that substring-collide the same way. NOTE: business-ambiguous nouns like
        # "check" ($2000 check) are deliberately NOT stopworded — protecting legit finance
        # queries. The naive substring matcher means this list is necessarily best-effort;
        # the structural fix (word-boundary + low-signal/rarity scoring) is a later pass.
        "detail",
        "details",
        "did",
        "doing",
        "give",
        "given",
        "gives",
        "giving",
        "gave",
        "help",
        "helped",
        "helping",
        "helps",
        "more",
        "please",
        "should",
        "show",
        "showing",
        "shown",
        "shows",
        "telling",
        "tells",
        "these",
        "told",
        "those",
    }
)
SYSTEM_POSTURE_TOPICS = frozenset({"agent_presence", "capability", "chief", "freshness", "work_board"})
SYSTEM_POSTURE_MARKERS = (
    "capability posture",
    "classification counts",
    "live calendar access",
    "live-implemented",
    "merged-context",
    "online agents",
    "readback/non-executing",
    "role boundary",
)
SYSTEM_POSTURE_TERMS = frozenset(
    {"agent", "agents", "capability", "capabilities", "chief", "openclaw", "online", "rail", "rails", "roster", "system"}
)
ANSWER_FILLER_MARKERS = ("next friday",)
_WORD_RE = re.compile(r"[a-z0-9']+")
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+|;\s+")


def _question_terms(prompt: str) -> set[str]:
    return {
        token
        for token in _WORD_RE.findall(str(prompt or "").lower())
        if len(token) > 2 and token not in QUESTION_STOP_WORDS
    }


def _requests_system_posture(prompt: str) -> bool:
    return bool(_question_terms(prompt) & SYSTEM_POSTURE_TERMS)


def _is_system_posture_fact(fact: Mapping[str, Any]) -> bool:
    topic = str(fact.get("topic") or "").strip().lower()
    text = f"{fact.get('label') or ''} {fact.get('value') or ''}".lower()
    return topic in SYSTEM_POSTURE_TOPICS or any(marker in text for marker in SYSTEM_POSTURE_MARKERS)


def _fact_match_score(fact: Mapping[str, Any], terms: set[str], *, allow_system_posture: bool) -> int:
    if not allow_system_posture and _is_system_posture_fact(fact):
        return 0
    text = " ".join(str(fact.get(key) or "") for key in ("topic", "label", "value")).lower()
    if not terms:
        return 1 if not _is_system_posture_fact(fact) else 0
    score = sum(2 for term in terms if term in text)
    label = str(fact.get("label") or "").lower()
    score += sum(1 for term in terms if term in label)
    return score


def _clean_answer_value(value: object) -> str:
    chunks = []
    for chunk in _SENTENCE_SPLIT_RE.split(str(value or "")):
        clean = chunk.strip(" \t\r\n.")
        if not clean:
            continue
        lowered = clean.lower()
        if any(marker in lowered for marker in ANSWER_FILLER_MARKERS):
            continue
        if any(marker in lowered for marker in SYSTEM_POSTURE_MARKERS):
            continue
        chunks.append(clean)
    return "; ".join(chunks[:4])


def _format_answer_fact(fact: Mapping[str, Any]) -> str:
    label = str(fact.get("label") or "").strip()
    value = _clean_answer_value(fact.get("value"))
    if not value:
        return ""
    if label and label.lower() not in value.lower():
        return f"{label}: {value}."
    return value.rstrip(".") + "."


# 000h: gig/day/schedule questions must answer from the calendar, never from a
# finance fact whose vocabulary collides with the terms. "$400 gigs" contains "gig"
# and "next Friday" contains "day" (fri-DAY), so a Capital Hilton finance fact would
# out-score the real calendar_day fact and "how many gigs"/"what's my day" wrongly
# returned Capital Hilton. Named-entity and domain routing are unaffected (they carry
# no schedule marker and keep the generic term-scoring path below).
_SCHEDULE_INTENT_MARKERS = (
    "gig",
    "gigs",
    "my day",
    "day look",
    "the day ahead",
    "my schedule",
    "today",
    "agenda",
    "calendar",
    "upcoming",
    "coming up",
    "this week",
    "next week",
    "rehearsal",
)
_SCHEDULE_ANSWER_TOPICS = frozenset({"calendar_day"})
_NO_PACKET_ANSWER = (
    "I don't have that in the current Maestro packet. "
    "I can answer from the packet or ask Chief for a reviewed action plan, but I won't invent it."
)


def _is_schedule_intent(prompt: str) -> bool:
    lowered = str(prompt or "").lower()
    return any(marker in lowered for marker in _SCHEDULE_INTENT_MARKERS)


# 000i: a question that reduces to zero content terms is ambiguous. It can be a
# genuine "give me the overview" ask (worth a headline digest) or a pure-meta /
# clarification question such as "what do you mean" or "what are you saying" (must
# stay honest — never dump a random business fact). Only an explicit overview/status
# ask earns the digest; everything else falls through to _NO_PACKET_ANSWER. This keeps
# the new filler-word stopwords from opening a fresh confabulation path.
_OVERVIEW_INTENT_MARKERS = (
    "status",
    "update",
    "what's up",
    "whats up",
    "what's new",
    "whats new",
    "catch me up",
    "fill me in",
    "brief me",
    "the latest",
    "how are things",
    "overview",
    "summary",
    "summarize",
    "rundown",
    "recap",
    "everything",
)


def _requests_overview(prompt: str) -> bool:
    lowered = str(prompt or "").lower()
    return any(marker in lowered for marker in _OVERVIEW_INTENT_MARKERS)


def _schedule_grounded_answer(facts: list[Mapping[str, Any]]) -> str | None:
    matched: list[str] = []
    seen: set[str] = set()
    for fact in facts:
        if str(fact.get("topic") or "").strip().lower() not in _SCHEDULE_ANSWER_TOPICS:
            continue
        sentence = _format_answer_fact(fact)
        key = sentence.lower()
        if sentence and key not in seen:
            matched.append(sentence)
            seen.add(key)
        if len(matched) >= 3:
            break
    return " ".join(matched[:3]) if matched else None


# Social/casual messages — greetings, reactions, thanks, "I hear…". They ask for NO fact,
# so the anti-confab "won't invent it" deflection is wrong for them: there is nothing to
# invent. They get a warm reply (and the existing reply_pipeline comedy/voice on top).
# Clarification-metas ("what do you mean") and anything carrying a factual/schedule data
# request are explicitly NOT social — those still deflect, so grounding stays intact.
_SOCIAL_INTENT_MARKERS = (
    "hey", "hello", "yo ", "yo,", "sup", "what's good", "whats good", "good morning",
    "good evening", "good to hear", "good to see", "howdy", "how's it going",
    "hows it going", "how are you", "how you doing", "you good", "haha", "lol", "lmao",
    "nice", "cool", "awesome", "love it", "love that", "that's great", "thats great",
    "that's awesome", "sweet", "dope", "right on", "thanks", "thank you", "appreciate",
    "congrats", "amazing", "i hear", "i heard", "heard you", "glad", "proud of",
)
# NOT a round-robin: with the conversational lane the MODEL writes casual replies (varied,
# human). This single line is only the rare model-DOWN backstop — if the operator sees it
# repeat, the local model was unreachable (a real signal), not canned chat.
_SOCIAL_BACKSTOP_LINES = (
    "Give me a sec — I'm having trouble thinking straight right now. Hit me again in a bit?",
)


def _social_backstop_line() -> str:
    return _SOCIAL_BACKSTOP_LINES[0]


def _is_social_intent(prompt: str) -> bool:
    # Shared classifier so the front-door conversational lane and this backstop always agree.
    try:
        from social_intent import is_social_intent
        return is_social_intent(prompt)
    except Exception:
        return False


def _social_backstop(prompt: str) -> str:
    return _social_backstop_line()


def _fallback_grounded_answer(prompt: str, context_packet: Mapping[str, Any] | str | None) -> str:
    # Pure-social message with no factual/schedule intent: never deflect with "won't invent
    # it" — there's no fact at stake. The conversational lane has the MODEL write these; this
    # single line is only the rare model-down backstop (a repeat = the model was unreachable).
    if _is_social_intent(prompt):
        return _social_backstop(prompt)
    packet = _packet_mapping(context_packet)
    facts = [fact for fact in packet.get("facts", ()) if isinstance(fact, Mapping)] if packet else []

    if _is_schedule_intent(prompt):
        scheduled = _schedule_grounded_answer(facts)
        return scheduled if scheduled is not None else _NO_PACKET_ANSWER

    terms = _question_terms(prompt)
    allow_system_posture = _requests_system_posture(prompt)

    # 000i: a prompt that reduces to zero content terms only earns a fact digest when
    # it is an explicit overview/status ask ("status", "what's up", "catch me up").
    # Otherwise — a pure-meta/clarification question like "what do you mean" or "what
    # are you saying" — stay honest. Without this guard the new filler-word stopwords
    # would push such questions into _fact_match_score's empty-terms branch (which
    # scores every non-posture fact 1) and dump an arbitrary business fact.
    if not terms and not _requests_overview(prompt):
        return _NO_PACKET_ANSWER

    scored: list[tuple[int, int, Mapping[str, Any]]] = []
    for index, fact in enumerate(facts):
        score = _fact_match_score(fact, terms, allow_system_posture=allow_system_posture)
        if score > 0:
            scored.append((score, -index, fact))
    scored.sort(reverse=True)
    matched: list[str] = []
    seen: set[str] = set()
    for _score, _index, fact in scored:
        sentence = _format_answer_fact(fact)
        key = sentence.lower()
        if sentence and key not in seen:
            matched.append(sentence)
            seen.add(key)
        if len(matched) >= 3:
            break

    if not matched and not terms:
        for fact in facts:
            if not allow_system_posture and _is_system_posture_fact(fact):
                continue
            sentence = _format_answer_fact(fact)
            if sentence:
                matched.append(sentence)
            if len(matched) >= 3:
                break

    if not matched:
        return _NO_PACKET_ANSWER
    return " ".join(matched[:3])


# ── Front-door profile: completeness + Stage-1 validation (Revision 8) ────────
# A truncated-mid-sentence answer is NEVER delivered. done_reason=="length" is a
# FAILURE unless the text is a complete utterance AND passes the Stage-1 validator.

_SENTENCE_FINAL_RE = re.compile(r"[.!?][\"')\]]*\s*$")
# A dangling clause typically ends on a coordinating/subordinating conjunction or a
# comma — an obvious mid-sentence cut even if punctuation were appended.
_DANGLING_TAIL_WORDS = frozenset(
    {
        "and",
        "or",
        "but",
        "so",
        "because",
        "with",
        "for",
        "the",
        "a",
        "an",
        "to",
        "of",
        "in",
        "on",
        "at",
        "as",
        "that",
        "which",
        "while",
        "when",
        "if",
        "then",
    }
)


def _is_complete_utterance(text: str) -> bool:
    """True when ``text`` ends on sentence-final punctuation with no dangling clause."""
    stripped = str(text or "").strip()
    if not stripped:
        return False
    if not _SENTENCE_FINAL_RE.search(stripped):
        return False
    # Strip trailing punctuation/quotes to inspect the final word.
    tail = re.sub(r"[.!?\"')\]\s]+$", "", stripped)
    last_word = tail.split()[-1].lower().strip(",;:") if tail.split() else ""
    if last_word in _DANGLING_TAIL_WORDS:
        return False
    # A bare comma right before the final punctuation also signals a cut clause.
    if re.search(r",\s*$", tail):
        return False
    return True


def _stage1_validate(text: str) -> tuple[bool, bool, tuple[str, ...]]:
    """Run the existing Stage-1 operator-surface validator on ``text``.

    Returns (passed, available, reasons). ``available`` is False when the validator
    module cannot be imported. For ``done_reason=length`` callers must fail closed
    unless the validator is available and passes.
    """
    try:
        from operator_surface_guard import check_machine_contract_leak
    except Exception:
        return True, False, ()
    try:
        result = check_machine_contract_leak(str(text or ""))
        return (not bool(result.is_leak)), True, tuple(result.reasons)
    except Exception:
        return True, False, ()


def _write_audit(receipt: Mapping[str, Any], audit_log_path: str | Path | None = None) -> str:
    target = Path(audit_log_path or os.environ.get("OPENCLAW_PII_AUDIT_LOG", "") or DEFAULT_AUDIT_LOG)
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        safe = dict(receipt)
        safe.pop("raw_prompt", None)
        with target.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(safe, sort_keys=True, ensure_ascii=True) + "\n")
        return target.as_posix()
    except Exception:
        return ""


def _base_receipt(
    *,
    prompt: str,
    context_packet: Mapping[str, Any] | str | None,
    tier: str,
    agent: str = "maestro",
) -> dict[str, Any]:
    packet = _packet_mapping(context_packet)
    agent_id = str(agent or "maestro").strip().lower() or "maestro"
    skill_receipts = [
        dict(receipt)
        for receipt in packet.get("skill_receipts", ())
        if isinstance(receipt, Mapping) and receipt.get("applied")
    ]
    receipt = {
        "schema_version": "protected_generate_receipt_v0",
        "receipt_id": f"protected_generate:{hashlib.sha256((prompt + _packet_text(context_packet)).encode('utf-8')).hexdigest()[:16]}",
        "generated_at": _utc_now(),
        "pii_tier": tier,
        "agent": agent_id,
        "packet_id": str(packet.get("packet_id") or ""),
        "prompt_hash": _sha256(prompt),
        "packet_hash": _sha256(_packet_text(context_packet)),
        "send_hold_active": True,
        "outbound_action_allowed": False,
        "money_movement_allowed": False,
        "ledger_mutation_allowed": False,
        "raw_values_written_to_audit": False,
    }
    if skill_receipts:
        receipt["skills_applied"] = [
            str(item.get("skill_id") or "")
            for item in skill_receipts
            if str(item.get("skill_id") or "").strip()
        ]
        receipt["skill_receipts"] = skill_receipts
    return receipt


def _strip_speaker_prefix(text: str, agent: str) -> str:
    """Drop a leading '<AgentName>:' label the front-door model sometimes echoes from the
    prompt's trailing speaker cue (e.g. 'Maestro: hi' -> 'hi'). Only the agent's OWN name is
    removed, only at the very start, and only when real content remains after it."""
    s = str(text or "")
    name = str(agent or "maestro").strip() or "maestro"
    match = re.match(r"\s*" + re.escape(name) + r"\s*:\s*", s, re.IGNORECASE)
    if not match:
        return s
    remainder = s[match.end():]
    return remainder if remainder.strip() else s


def protected_generate_with_receipt(
    prompt: str,
    *,
    context_packet: Mapping[str, Any] | str | None,
    generator_fn: Callable[..., str] | None = None,
    audit_log_path: str | Path | None = None,
    allow_live_model: bool | None = None,
    front_door_profile: bool | None = None,
    interactive_timeout_s: float | None = None,
    num_predict: int | None = None,
    model_selected: str | None = None,
    model_think: bool | None = None,
    done_reason: str | None = None,
    context_facts_kept: int | None = None,
    context_facts_dropped: int | None = None,
    prompt_chars: int | None = None,
    agent: str = "maestro",
) -> ProtectedGenerateOutcome:
    """Generate text through graded PII tokenization and an audit receipt.

    This function returns a blocked outcome instead of raising for policy
    denials, because front-door callers need to give the operator a clear answer.

    front_door_profile (DEFAULT-OFF): when False the receipt and behavior are
    BYTE-IDENTICAL to before — NONE of the new telemetry fields are emitted. When
    True, the front-door classification (model_fallback_reason), truncation/validation
    policy (Revision 8), and telemetry fields (Revision 9) are added to the receipt.
    When None, this function auto-selects the profile only for the real Maestro
    front-door context packet shape, which is how the existing responder reaches
    this allowed file without changing the responder module.
    The other new params (interactive_timeout_s / num_predict / model_selected /
    done_reason / context_facts_kept / context_facts_dropped / prompt_chars) are
    front-door pass-throughs recorded only when front_door_profile=True; ``done_reason``
    may also be threaded by a caller that only has the text (the injected generator
    can alternatively return a dict carrying done_reason).
    """

    raw_prompt = str(prompt or "").strip()
    packet = _packet_mapping(context_packet)
    front_door_profile = _frontdoor_profile_active(front_door_profile, context_packet)
    tier = detect_pii_tier(raw_prompt, context_packet)
    receipt = _base_receipt(prompt=raw_prompt, context_packet=context_packet, tier=tier, agent=agent)

    if tier == MAX and not _legal_fully_tokenized(raw_prompt, packet):
        receipt.update(
            {
                "status": "BLOCKED",
                "decision": "BLOCK_LEGAL_DISCOVERY_UNTOKENIZED",
                "blocked_reason": "legal_discovery_requires_full_tokenization",
                "tokenization_applied": False,
                "raw_values_included": True,
                "model_call_performed": False,
                "external_llm_invoked": False,
                "local_model_invoked": False,
            }
        )
        audit_ref = _write_audit(receipt, audit_log_path)
        receipt["audit_ref"] = audit_ref
        return ProtectedGenerateOutcome(
            status="BLOCKED",
            text="I can't process Legal Discovery unless it is fully tokenized first.",
            receipt=receipt,
        )

    ledger = _TokenLedger()
    safe_prompt, ledger = tokenize_text_for_tier(raw_prompt, tier, ledger)
    safe_packet = _tokenize_packet(context_packet, tier, ledger)
    token_count = ledger.token_count()
    tokenization_applied = token_count > 0
    raw_values_included = tier in {LIGHT, MED} and token_count == 0
    metadata = _metadata_for_tier(tier, token_count)
    external_safe = False
    external_policy_reason = "not_checked"
    external_model_configured = False
    try:
        from chief_llm import _configured_openrouter_model, external_model_packet_policy

        policy = external_model_packet_policy(safe_prompt + "\n" + safe_packet, metadata=metadata)
        external_safe = bool(policy.get("external_model_safe"))
        external_policy_reason = str(policy.get("reason") or "")
        external_model_configured = bool(_configured_openrouter_model())
    except Exception as exc:
        external_policy_reason = f"policy_error:{type(exc).__name__}"

    system_prompt = "\n".join(
        [
            "You are Maestro, speaking in first person as the operator's conductor.",
            perspective_prompt("maestro"),
            "Use only the deterministic packet below. If the answer is not in the packet, say you don't have it.",
            "Big picture, then middle, then small. Warm plain English. Never claim send/spend/mutation authority.",
            "SEND_HOLD is absolute.",
            "",
            "DETERMINISTIC PACKET:",
            safe_packet,
            "",
            "OPERATOR QUESTION:",
            safe_prompt,
        ]
    )
    fd_prompt_manifest: dict[str, Any] = {}
    if front_door_profile:
        try:
            from frontdoor_prompt import build_frontdoor_prompt

            system_prompt, fd_prompt_manifest = build_frontdoor_prompt(
                _tokenized_frontdoor_packet(packet, tier, ledger),
                safe_prompt,
                agent=agent,
            )
        except Exception:
            fd_prompt_manifest = {}

    fd_interactive_timeout_s = (
        float(interactive_timeout_s)
        if interactive_timeout_s is not None
        else _frontdoor_timeout_from_env()
    )
    if fd_interactive_timeout_s is not None and (
        fd_interactive_timeout_s <= 0 or fd_interactive_timeout_s > MAX_FRONTDOOR_TIMEOUT_SECONDS
    ):
        fd_interactive_timeout_s = None
    fd_num_predict = num_predict if num_predict is not None else (_frontdoor_num_predict() if front_door_profile else None)
    fd_model_think = model_think if model_think is not None else (False if front_door_profile else None)
    fd_ollama_options = _frontdoor_ollama_options() if front_door_profile else {}
    # Social conversational lane: raise temperature so casual replies read human and are
    # never the same. Factual answers keep the default (low-temp, grounded).
    if front_door_profile and fd_prompt_manifest.get("conversational_lane"):
        # Enough heat to vary + sound human, not so much it reaches for zingers/metaphors.
        fd_ollama_options = {**fd_ollama_options, "temperature": 0.7, "top_p": 0.9}
    fd_keep_alive = _frontdoor_keep_alive() if front_door_profile else None
    fd_model_max_gb = _frontdoor_model_max_gb() if front_door_profile else None
    fd_model_selected = model_selected
    fd_model_selection_reason: str | None = None
    fd_resource_probe_fields: dict[str, Any] = {}
    fd_available_vram_gb: float | None = None
    fd_available_ram_gb: float | None = None
    fd_resident_vram_by_model_gb: dict[str, float] = {}
    if front_door_profile:
        try:
            from frontdoor_resource_probe import probe_frontdoor_resources

            _resource_snapshot = probe_frontdoor_resources()
            fd_resource_probe_fields = _resource_snapshot.to_receipt_fields()
            fd_available_vram_gb = _resource_snapshot.available_vram_gb
            fd_available_ram_gb = _resource_snapshot.available_ram_gb
            fd_resident_vram_by_model_gb = _resource_snapshot.resident_vram_by_model_gb()
        except Exception as exc:
            fd_resource_probe_fields = {"resource_probe_errors": [f"probe_exception:{type(exc).__name__}"]}

    route = "deterministic_fallback"
    local_invoked = False
    external_invoked = False
    # Tracks whether an injected generator's output is actually DELIVERED. Starts as
    # generator_fn (off-path unchanged) and is cleared only if the front-door profile
    # discards the model output, so model_call_performed / decision /
    # deterministic_fallback_used stay truthful. Off-path: identical to generator_fn.
    generator_fn_used = generator_fn
    raw_output = ""
    external_timeout = _float_env("OPENCLAW_PROTECTED_GENERATE_EXTERNAL_TIMEOUT", DEFAULT_EXTERNAL_TIMEOUT_SECONDS)
    local_timeout = _float_env("OPENCLAW_PROTECTED_GENERATE_LOCAL_TIMEOUT", DEFAULT_LOCAL_TIMEOUT_SECONDS)
    local_attempts = _int_env("OPENCLAW_PROTECTED_GENERATE_LOCAL_ATTEMPTS", DEFAULT_LOCAL_ATTEMPTS)
    ollama_probe_timeout = _float_env("OPENCLAW_PROTECTED_GENERATE_OLLAMA_PROBE_TIMEOUT", 0.2)
    ollama_unreachable_shortcircuit = False
    # Front-door telemetry capture (only consulted when front_door_profile=True).
    fd_captured_done_reason: str | None = done_reason
    fd_model_elapsed_ms: int | None = None
    fd_response_metadata: dict[str, Any] = {}
    fd_model_call_attempted = False
    fd_model_output_delivered = False
    fd_delivered_response_source = "grounded_fallback"
    fd_call_started = _now_ms()
    if generator_fn is not None:
        route = "injected_generator"
        local_invoked = True
        fd_model_call_attempted = bool(front_door_profile)
        if front_door_profile:
            raw_output, _captured, _captured_elapsed, _captured_metadata = _call_generator_capturing(
                generator_fn,
                system_prompt,
                context_packet=safe_packet,
                metadata=metadata,
                receipt=dict(receipt),
            )
            if _captured is not None:
                fd_captured_done_reason = _captured
            fd_model_elapsed_ms = _captured_elapsed if _captured_elapsed is not None else _now_ms() - fd_call_started
            fd_response_metadata = _captured_metadata
        else:
            raw_output = _call_generator(
                generator_fn,
                system_prompt,
                context_packet=safe_packet,
                metadata=metadata,
                receipt=dict(receipt),
            )
    elif _live_model_allowed(allow_live_model):
        if (
            external_safe
            and external_model_configured
            and os.environ.get("OPENCLAW_FREEFORM_CLOUD", "").strip().lower() in {"1", "true", "yes"}
            and not front_door_profile
        ):
            try:
                from chief_llm import external_language_model_call

                raw_output = external_language_model_call(system_prompt, metadata=metadata, timeout=external_timeout)
                external_invoked = bool(raw_output)
                route = "external_language_model_call" if raw_output else "external_empty_fallback"
            except Exception:
                raw_output = ""
                route = "external_exception_fallback"
        if not raw_output:
            try:
                if front_door_profile:
                    if fd_interactive_timeout_s is None:
                        route = "deterministic_fallback_frontdoor_timeout_unset"
                    else:
                        from chief_llm import ollama_is_unreachable, select_frontdoor_model

                        if ollama_is_unreachable(timeout=ollama_probe_timeout):
                            ollama_unreachable_shortcircuit = True
                            fd_captured_done_reason = "unreachable"
                            route = "grounded_fallback_no_external_model_ollama_unreachable"
                        else:
                            _model, _reason = select_frontdoor_model(
                                max_gb=fd_model_max_gb,
                                available_vram_gb=fd_available_vram_gb,
                                available_ram_gb=fd_available_ram_gb,
                                resident_vram_by_model_gb=fd_resident_vram_by_model_gb,
                            )
                            fd_model_selection_reason = _reason
                            fd_model_selected = fd_model_selected or _model
                            if not _model:
                                fd_captured_done_reason = "no_fitting_model"
                                route = "deterministic_fallback_no_fitting_model"
                            else:
                                fd_model_call_attempted = True
                                _started = _now_ms()
                                _result = _call_local_ollama(
                                    system_prompt,
                                    timeout=fd_interactive_timeout_s,
                                    attempts=1,
                                    model=_model,
                                    task_class="frontdoor_reply",
                                    think=fd_model_think,
                                    num_predict=fd_num_predict,
                                    options=fd_ollama_options,
                                    keep_alive=fd_keep_alive,
                                    return_metadata=True,
                                )
                                raw_output, _captured, _elapsed, _metadata = _model_result_tuple(_result)
                                if _captured is not None:
                                    fd_captured_done_reason = _captured
                                fd_model_elapsed_ms = _elapsed if _elapsed is not None else _now_ms() - _started
                                fd_response_metadata = _metadata
                                local_invoked = bool(raw_output)
                                route = "local_ollama_frontdoor" if raw_output else "local_ollama_frontdoor_empty"
                elif not external_model_configured:
                    from chief_llm import ollama_is_unreachable

                    if ollama_is_unreachable(timeout=ollama_probe_timeout):
                        ollama_unreachable_shortcircuit = True
                        route = "grounded_fallback_no_external_model_ollama_unreachable"
                    else:
                        raw_output = _call_local_ollama(system_prompt, timeout=local_timeout, attempts=local_attempts)
                        local_invoked = bool(raw_output)
                        route = "local_ollama" if raw_output else route
                else:
                    raw_output = _call_local_ollama(system_prompt, timeout=local_timeout, attempts=local_attempts)
                    local_invoked = bool(raw_output)
                    route = "local_ollama" if raw_output else route
            except Exception:
                raw_output = ""
        if front_door_profile and fd_model_call_attempted and fd_model_elapsed_ms is None:
            fd_model_elapsed_ms = _now_ms() - fd_call_started

    # ── Front-door classification + truncation/validation (Revisions 8/9) ──────
    # All of this is gated behind front_door_profile; when off, nothing below runs
    # and the receipt is byte-identical to the legacy path.
    fd_fallback_reason: str | None = None
    fd_response_truncated = False
    fd_validation_unavailable = False
    fd_validation_reasons: tuple[str, ...] = ()
    if front_door_profile:
        dr_lower = str(fd_captured_done_reason or "").strip().lower()
        model_was_invoked = bool(local_invoked or external_invoked)
        if dr_lower == "timeout":
            # A caller/generator that surfaced a timeout outcome (Rev 2 ceiling exceeded).
            fd_fallback_reason = "timeout"
        elif dr_lower == "no_fitting_model":
            # Caller (the selector) found no allowlisted model that fits the box.
            fd_fallback_reason = "no_fitting_model"
        elif dr_lower == "unreachable" or ollama_unreachable_shortcircuit:
            fd_fallback_reason = "unreachable"
        elif not model_was_invoked:
            # No live model answer. Distinguish WHY for first-class telemetry.
            if route == "grounded_fallback_no_external_model_ollama_unreachable":
                fd_fallback_reason = "unreachable"
            elif route == "deterministic_fallback_frontdoor_timeout_unset":
                fd_fallback_reason = "never_invoked"
            elif not _live_model_allowed(allow_live_model) and generator_fn is None:
                fd_fallback_reason = "never_invoked"
            else:
                fd_fallback_reason = "empty_output"
        elif not str(raw_output or "").strip():
            fd_fallback_reason = "empty_output"
        else:
            # Model produced non-empty text. Apply truncation + Stage-1 validation.
            passed, available, vreasons = _stage1_validate(raw_output)
            fd_validation_unavailable = not available
            fd_validation_reasons = vreasons
            if dr_lower == "length":
                # done_reason=length is a FAILURE unless complete + validator-available
                # + validator-passing (Rev 8). Validator unavailable is NOT a pass.
                if available and passed and _is_complete_utterance(raw_output):
                    fd_fallback_reason = "model_ok"
                else:
                    fd_fallback_reason = "truncated"
                    fd_response_truncated = True
            elif not passed:
                fd_fallback_reason = "validation_failed"
            else:
                fd_fallback_reason = "model_ok"

        # Any non-model_ok reason → never deliver a bad/late/truncated answer; drop the
        # model output, route to the grounded deterministic fallback, and reflect that
        # no model answer was delivered in the model_call fields.
        if fd_fallback_reason == "model_ok":
            fd_model_output_delivered = True
            fd_delivered_response_source = "model"
        if fd_fallback_reason != "model_ok":
            raw_output = ""
            local_invoked = False
            external_invoked = False
            # The model output was DISCARDED → the receipt's model_call_performed /
            # decision / deterministic_fallback_used must reflect that no model answer
            # was delivered. Clearing generator_fn_used (not generator_fn itself, which
            # is left intact for the off-path) makes those three fields truthful.
            generator_fn_used = None
            route = f"deterministic_fallback_{fd_fallback_reason}"

    if not raw_output:
        raw_output = _fallback_grounded_answer(raw_prompt, context_packet)

    text = ledger.rehydrate(raw_output)
    # Strip a leading "<AgentName>:" the front-door model occasionally echoes from the
    # prompt's trailing speaker cue. Gated to delivered model output so the legacy path
    # (and the grounded fallback text) stay byte-identical.
    if front_door_profile and fd_model_output_delivered:
        text = _strip_speaker_prefix(text, agent)
    receipt.update(
        {
            "status": "ANSWER_READY",
            "decision": "ALLOW_TOKENIZED_MODEL_REASONING" if (local_invoked or external_invoked or generator_fn_used) else "ALLOW_GROUNDED_FALLBACK",
            "tokenization_applied": tokenization_applied,
            "token_count": token_count,
            "raw_values_included": raw_values_included,
            "model_call_performed": bool(local_invoked or external_invoked or generator_fn_used),
            "external_llm_invoked": external_invoked,
            "local_model_invoked": local_invoked,
            "route": route,
            "external_policy_safe": external_safe,
            "external_policy_reason": external_policy_reason,
            "external_model_configured": external_model_configured,
            "external_timeout_seconds": external_timeout,
            "local_timeout_seconds": local_timeout,
            "local_model_attempts": local_attempts,
            "ollama_probe_timeout_seconds": ollama_probe_timeout,
            "ollama_unreachable_shortcircuit": ollama_unreachable_shortcircuit,
            "deterministic_fallback_used": not bool(local_invoked or external_invoked or generator_fn_used),
            "safe_prompt_hash": _sha256(system_prompt),
        }
    )
    # Front-door telemetry (Revision 9). ONLY emitted when front_door_profile=True so
    # the default-off receipt stays byte-identical to the pre-change schema.
    if front_door_profile:
        resolved_prompt_chars = (
            prompt_chars
            if prompt_chars is not None
            else fd_prompt_manifest.get("prompt_chars", len(system_prompt))
        )
        resolved_kept = (
            context_facts_kept
            if context_facts_kept is not None
            else fd_prompt_manifest.get("context_facts_kept")
        )
        resolved_dropped = (
            context_facts_dropped
            if context_facts_dropped is not None
            else fd_prompt_manifest.get("context_facts_dropped")
        )
        receipt.update(
            {
                "front_door_profile_used": True,
                "model_selected": fd_model_selected,
                "model_selection_reason": fd_model_selection_reason,
                "prompt_chars": resolved_prompt_chars,
                "prompt_context_chars": fd_prompt_manifest.get("prompt_context_chars"),
                "model_elapsed_ms": fd_model_elapsed_ms,
                "model_timeout_s": fd_interactive_timeout_s,
                "model_num_predict": fd_num_predict,
                "model_num_ctx": fd_ollama_options.get("num_ctx"),
                "model_num_gpu": fd_ollama_options.get("num_gpu"),
                "model_keep_alive": fd_keep_alive,
                "model_max_gb": fd_model_max_gb,
                "model_think": fd_model_think,
                "done_reason": fd_captured_done_reason,
                "model_fallback_reason": fd_fallback_reason,
                "response_truncated": fd_response_truncated,
                "context_facts_kept": resolved_kept,
                "context_facts_dropped": resolved_dropped,
                "model_call_attempted": fd_model_call_attempted,
                "model_output_delivered": fd_model_output_delivered,
                "delivered_response_source": fd_delivered_response_source,
                "model_response_metadata": dict(fd_response_metadata),
                **fd_resource_probe_fields,
            }
        )
        if fd_validation_unavailable:
            receipt["validation_unavailable"] = True
        if fd_validation_reasons:
            receipt["validation_reasons"] = list(fd_validation_reasons)
    audit_ref = _write_audit(receipt, audit_log_path)
    receipt["audit_ref"] = audit_ref
    return ProtectedGenerateOutcome(status="ANSWER_READY", text=text, receipt=receipt)


def protected_generate(
    prompt: str,
    *,
    context_packet: Mapping[str, Any] | str | None,
    generator_fn: Callable[..., str] | None = None,
    audit_log_path: str | Path | None = None,
    allow_live_model: bool | None = None,
) -> str:
    return protected_generate_with_receipt(
        prompt,
        context_packet=context_packet,
        generator_fn=generator_fn,
        audit_log_path=audit_log_path,
        allow_live_model=allow_live_model,
    ).text


__all__ = [
    "ProtectedGenerateBlocked",
    "ProtectedGenerateOutcome",
    "detect_pii_tier",
    "protected_generate",
    "protected_generate_with_receipt",
    "tokenize_text_for_tier",
]
