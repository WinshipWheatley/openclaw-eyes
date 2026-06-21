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
from typing import Any, Callable, Mapping

from agent_perspective import perspective_prompt


DEFAULT_AUDIT_LOG = Path("/mnt/c/OpenClaw/logs/protected_generate_audit.jsonl")
DEFAULT_EXTERNAL_TIMEOUT_SECONDS = 6.0
DEFAULT_LOCAL_TIMEOUT_SECONDS = 6.0
DEFAULT_LOCAL_ATTEMPTS = 1
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


def _call_local_ollama(prompt: str, *, timeout: float, attempts: int) -> str:
    from chief_llm import ollama_call

    try:
        signature = inspect.signature(ollama_call)
    except (TypeError, ValueError):
        signature = None
    kwargs: dict[str, Any] = {
        "timeout": timeout,
        "task_class": "chief_user_reply",
    }
    if signature is not None and (
        "attempts" in signature.parameters
        or any(param.kind == inspect.Parameter.VAR_KEYWORD for param in signature.parameters.values())
    ):
        kwargs["attempts"] = attempts
    return str(ollama_call(prompt, **kwargs) or "")


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


def _fallback_grounded_answer(prompt: str, context_packet: Mapping[str, Any] | str | None) -> str:
    packet = _packet_mapping(context_packet)
    facts = [fact for fact in packet.get("facts", ()) if isinstance(fact, Mapping)] if packet else []
    terms = _question_terms(prompt)
    allow_system_posture = _requests_system_posture(prompt)
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
        return (
            "I don't have that in the current Maestro packet. "
            "I can answer from the packet or ask Chief for a reviewed action plan, but I won't invent it."
        )
    return " ".join(matched[:3])


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
) -> dict[str, Any]:
    packet = _packet_mapping(context_packet)
    return {
        "schema_version": "protected_generate_receipt_v0",
        "receipt_id": f"protected_generate:{hashlib.sha256((prompt + _packet_text(context_packet)).encode('utf-8')).hexdigest()[:16]}",
        "generated_at": _utc_now(),
        "pii_tier": tier,
        "packet_id": str(packet.get("packet_id") or ""),
        "prompt_hash": _sha256(prompt),
        "packet_hash": _sha256(_packet_text(context_packet)),
        "send_hold_active": True,
        "outbound_action_allowed": False,
        "money_movement_allowed": False,
        "ledger_mutation_allowed": False,
        "raw_values_written_to_audit": False,
    }


def protected_generate_with_receipt(
    prompt: str,
    *,
    context_packet: Mapping[str, Any] | str | None,
    generator_fn: Callable[..., str] | None = None,
    audit_log_path: str | Path | None = None,
    allow_live_model: bool | None = None,
) -> ProtectedGenerateOutcome:
    """Generate text through graded PII tokenization and an audit receipt.

    This function returns a blocked outcome instead of raising for policy
    denials, because front-door callers need to give the operator a clear answer.
    """

    raw_prompt = str(prompt or "").strip()
    packet = _packet_mapping(context_packet)
    tier = detect_pii_tier(raw_prompt, context_packet)
    receipt = _base_receipt(prompt=raw_prompt, context_packet=context_packet, tier=tier)

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
    try:
        from chief_llm import external_model_packet_policy

        policy = external_model_packet_policy(safe_prompt + "\n" + safe_packet, metadata=metadata)
        external_safe = bool(policy.get("external_model_safe"))
        external_policy_reason = str(policy.get("reason") or "")
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

    route = "deterministic_fallback"
    local_invoked = False
    external_invoked = False
    raw_output = ""
    external_timeout = _float_env("OPENCLAW_PROTECTED_GENERATE_EXTERNAL_TIMEOUT", DEFAULT_EXTERNAL_TIMEOUT_SECONDS)
    local_timeout = _float_env("OPENCLAW_PROTECTED_GENERATE_LOCAL_TIMEOUT", DEFAULT_LOCAL_TIMEOUT_SECONDS)
    local_attempts = _int_env("OPENCLAW_PROTECTED_GENERATE_LOCAL_ATTEMPTS", DEFAULT_LOCAL_ATTEMPTS)
    if generator_fn is not None:
        route = "injected_generator"
        local_invoked = True
        raw_output = _call_generator(
            generator_fn,
            system_prompt,
            context_packet=safe_packet,
            metadata=metadata,
            receipt=dict(receipt),
        )
    elif _live_model_allowed(allow_live_model):
        if external_safe and os.environ.get("OPENCLAW_FREEFORM_CLOUD", "").strip().lower() in {"1", "true", "yes"}:
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
                raw_output = _call_local_ollama(system_prompt, timeout=local_timeout, attempts=local_attempts)
                local_invoked = bool(raw_output)
                route = "local_ollama" if raw_output else route
            except Exception:
                raw_output = ""
    if not raw_output:
        raw_output = _fallback_grounded_answer(raw_prompt, context_packet)

    text = ledger.rehydrate(raw_output)
    receipt.update(
        {
            "status": "ANSWER_READY",
            "decision": "ALLOW_TOKENIZED_MODEL_REASONING" if (local_invoked or external_invoked or generator_fn) else "ALLOW_GROUNDED_FALLBACK",
            "tokenization_applied": tokenization_applied,
            "token_count": token_count,
            "raw_values_included": raw_values_included,
            "model_call_performed": bool(local_invoked or external_invoked or generator_fn),
            "external_llm_invoked": external_invoked,
            "local_model_invoked": local_invoked,
            "route": route,
            "external_policy_safe": external_safe,
            "external_policy_reason": external_policy_reason,
            "external_timeout_seconds": external_timeout,
            "local_timeout_seconds": local_timeout,
            "local_model_attempts": local_attempts,
            "deterministic_fallback_used": not bool(local_invoked or external_invoked or generator_fn),
            "safe_prompt_hash": _sha256(system_prompt),
        }
    )
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
