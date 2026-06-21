"""System-wide Quiet Luxury output renderer.

The renderer is deterministic by default and can call an injected or explicitly
allowed LLM renderer.  Test mode never performs a live model call.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import inspect
import json
import os
import re
from pathlib import Path
from typing import Any, Callable, Mapping

from openclaw_terminology_adapter import normalize_target_layer, translate_terms


ROOT = Path(__file__).resolve().parent
DEFAULT_DOCTRINE_PATH = ROOT / "generated/read_models/quiet_luxury_doctrine.json"
RAW_FACT_RE = re.compile(
    r"\b(?:FAILED_SEND|MISSED_DEADLINE|SECURITY_RISK|SEND_HOLD|BLOCKED_PENDING_APPROVAL|RATE_LIMIT_EXCEEDED)\b"
    r"|\$\s*\d[\d,]*(?:\.\d{2})?"
    r"|\b\d{4}-\d{2}-\d{2}\b"
)


@dataclass(frozen=True)
class LuxRenderResult:
    text: str
    target_layer: str
    prompt: str
    llm_invoked: bool
    fallback_used: bool

    def machine_proof(self) -> dict[str, Any]:
        return {
            "quiet_luxury_renderer_used": True,
            "quiet_luxury_target_layer": self.target_layer,
            "quiet_luxury_llm_invoked": self.llm_invoked,
            "quiet_luxury_fallback_used": self.fallback_used,
            "quiet_luxury_prompt_hash": _sha256(self.prompt),
        }


def _sha256(text: str) -> str:
    import hashlib

    return "sha256:" + hashlib.sha256(str(text or "").encode("utf-8")).hexdigest()


def _stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False)


def _packet_text(packet: Mapping[str, Any] | str | Any) -> str:
    if isinstance(packet, Mapping):
        text = packet.get("text")
        if isinstance(text, str) and text.strip():
            return text
        return _stable_json(packet)
    return str(packet or "")


def _load_doctrine(path: str | Path | None = None) -> Mapping[str, Any]:
    target = Path(path) if path is not None else DEFAULT_DOCTRINE_PATH
    try:
        with target.open("r", encoding="utf-8") as fh:
            payload = json.load(fh)
        return payload if isinstance(payload, Mapping) else {}
    except FileNotFoundError:
        return {}


def _doctrine_lines(doctrine: Mapping[str, Any]) -> tuple[str, ...]:
    principles = doctrine.get("core_principles") if isinstance(doctrine.get("core_principles"), Mapping) else {}
    names: list[str] = []
    for key in ("velvet_over_steel", "severity_integrity", "system_carries_complexity"):
        item = principles.get(key) if isinstance(principles.get(key), Mapping) else {}
        name = str(item.get("name") or key.replace("_", " ").title()).strip()
        description = str(item.get("description") or "").strip()
        names.append(f"- {name}: {description}" if description else f"- {name}")
    return tuple(names)


def build_lux_renderer_prompt(
    packet: Mapping[str, Any] | str | Any,
    *,
    target_agent: str = "maestro",
    doctrine_path: str | Path | None = None,
) -> str:
    """Build the exact prompt handed to the optional LLM renderer."""

    layer = normalize_target_layer(target_agent)
    raw_packet = _packet_text(packet)
    doctrine = _load_doctrine(doctrine_path)
    doctrine_text = "\n".join(_doctrine_lines(doctrine))
    return "\n".join(
        [
            "Apply the Quiet Luxury Communication Doctrine to the packet.",
            "Return exactly these three labeled sections in this order:",
            "Velvet: one sentence stating what is true and the recommended move.",
            "Concierge: one or two sentences of necessary context.",
            "Steel: exact raw numbers, dates, status codes, and approval boundaries.",
            "Severity Integrity: never soften FAILED_SEND, MISSED_DEADLINE, or SECURITY_RISK.",
            f"Target layer: {layer}.",
            "",
            "Doctrine:",
            doctrine_text,
            "",
            "Raw packet:",
            raw_packet,
        ]
    )


def _first_sentence(text: str, *, max_chars: int = 180) -> str:
    compact = " ".join(str(text or "").split())
    if not compact:
        return "No packet content was supplied."
    match = re.search(r"(.+?[.!?])(?:\s|$)", compact)
    sentence = match.group(1) if match else compact
    if len(sentence) <= max_chars:
        return sentence
    return sentence[: max_chars - 1].rstrip(" ,;:") + "."


def _raw_facts(raw_text: str, translated_text: str) -> str:
    raw_facts = RAW_FACT_RE.findall(raw_text) + RAW_FACT_RE.findall(translated_text)
    facts = []
    for fact in raw_facts:
        if fact.lstrip().startswith("$"):
            facts.append(f"Project investment: {fact.replace('$ ', '$')} / Total price: {fact.replace('$ ', '$')}")
        else:
            facts.append(fact)
    facts = list(dict.fromkeys(facts))
    if facts:
        return "; ".join(facts)
    return "No raw numbers, dates, status codes, or approval boundaries were present in the packet."


def _deterministic_render(packet: Mapping[str, Any] | str | Any, *, target_agent: str) -> str:
    layer = normalize_target_layer(target_agent)
    raw_text = _packet_text(packet)
    translated = translate_terms(raw_text, target_layer=layer)
    velvet = _first_sentence(translated)
    if "FAILED_SEND" in raw_text and "FAILED_SEND" not in velvet:
        velvet = "FAILED_SEND remains true; " + velvet[0].lower() + velvet[1:]
    if "MISSED_DEADLINE" in raw_text and "MISSED_DEADLINE" not in velvet:
        velvet = "MISSED_DEADLINE remains true; " + velvet[0].lower() + velvet[1:]
    if "SECURITY_RISK" in raw_text and "SECURITY_RISK" not in velvet:
        velvet = "SECURITY_RISK remains true; " + velvet[0].lower() + velvet[1:]
    return "\n".join(
        [
            f"Velvet: {velvet}",
            "Concierge: The system keeps the machinery out of the operator-facing copy while preserving boundaries and source facts.",
            f"Steel: {_raw_facts(raw_text, translated)}",
        ]
    )


def _has_required_sections(text: str) -> bool:
    return all(re.search(rf"^{label}:", text, re.MULTILINE) for label in ("Velvet", "Concierge", "Steel"))


def _call_llm(llm_fn: Callable[..., str], prompt: str) -> str:
    try:
        signature = inspect.signature(llm_fn)
    except (TypeError, ValueError):
        signature = None
    kwargs = {"task_class": "chief_user_reply", "timeout": 6, "attempts": 1}
    if signature is None:
        try:
            return str(llm_fn(prompt, **kwargs) or "")
        except TypeError:
            return str(llm_fn(prompt) or "")
    params = signature.parameters
    if any(param.kind == inspect.Parameter.VAR_KEYWORD for param in params.values()):
        return str(llm_fn(prompt, **kwargs) or "")
    accepted = {key: value for key, value in kwargs.items() if key in params}
    return str(llm_fn(prompt, **accepted) or "")


def _live_llm_allowed(allow_llm: bool | None) -> bool:
    if allow_llm is not None:
        return bool(allow_llm)
    if os.environ.get("OPENCLAW_TEST_MODE") == "1":
        return False
    return os.environ.get("OPENCLAW_LUX_RENDERER_LIVE", "").strip().lower() in {"1", "true", "yes", "on"}


def render_packet_result(
    packet: Mapping[str, Any] | str | Any,
    *,
    target_agent: str = "maestro",
    allow_llm: bool | None = None,
    llm_fn: Callable[..., str] | None = None,
    doctrine_path: str | Path | None = None,
) -> LuxRenderResult:
    layer = normalize_target_layer(target_agent)
    prompt = build_lux_renderer_prompt(packet, target_agent=layer, doctrine_path=doctrine_path)
    rendered = ""
    llm_invoked = False
    if llm_fn is not None:
        rendered = _call_llm(llm_fn, prompt)
        llm_invoked = bool(rendered)
    elif _live_llm_allowed(allow_llm):
        from chief_llm import ollama_call

        rendered = _call_llm(ollama_call, prompt)
        llm_invoked = bool(rendered)
    translated_rendered = translate_terms(rendered, target_layer=layer) if rendered else ""
    if not _has_required_sections(translated_rendered):
        translated_rendered = _deterministic_render(packet, target_agent=layer)
        fallback_used = True
    else:
        fallback_used = False
    return LuxRenderResult(
        text=translated_rendered,
        target_layer=layer,
        prompt=prompt,
        llm_invoked=llm_invoked,
        fallback_used=fallback_used,
    )


def render_packet(
    packet: Mapping[str, Any] | str | Any,
    *,
    target_agent: str = "maestro",
    allow_llm: bool | None = None,
    llm_fn: Callable[..., str] | None = None,
    doctrine_path: str | Path | None = None,
) -> str:
    return render_packet_result(
        packet,
        target_agent=target_agent,
        allow_llm=allow_llm,
        llm_fn=llm_fn,
        doctrine_path=doctrine_path,
    ).text


def render_packet_receipt(
    packet: Mapping[str, Any] | str | Any,
    *,
    target_agent: str = "maestro",
    allow_llm: bool | None = None,
    llm_fn: Callable[..., str] | None = None,
    doctrine_path: str | Path | None = None,
) -> dict[str, Any]:
    return asdict(
        render_packet_result(
            packet,
            target_agent=target_agent,
            allow_llm=allow_llm,
            llm_fn=llm_fn,
            doctrine_path=doctrine_path,
        )
    )


__all__ = [
    "LuxRenderResult",
    "build_lux_renderer_prompt",
    "render_packet",
    "render_packet_receipt",
    "render_packet_result",
]
