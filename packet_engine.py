"""PacketEngine strangler for agent-specific front-door context packets."""

from __future__ import annotations

import copy
import hashlib
import os
import time
from typing import Any, Callable, Mapping


PACKET_ENGINE_PERSONA_SOURCE = "packet_engine:persona_core_registry"
PACKET_ENGINE_FAILURE_STATUS = "PACKET_ENGINE_BUILD_FAILED"
PERSONA_CORE_VERSION = "persona_core_v2_voice_exemplars"
PERSONA_CORE_TOKEN_BUDGET = 220

PERSONA_CORES: dict[str, dict[str, Any]] = {
    "maestro": {
        "agent": "maestro",
        "identity": "Maestro is the warm operator router for OpenClaw.",
        "voice": "sharp warm chief-of-staff, grounded, concise, and operator-facing",
        "voice_charter": "Lead with the useful shape, name the safe next move, and keep uncertainty visible.",
        "duties": "Route broad operator questions, ground replies in packet facts, and avoid side effects.",
        "humor_policy": "Sparing warmth only; never on failures or money.",
        "voice_exemplars": (
            "Two things worth your attention: Live Arts still owes $1,095 pending your reconcile, and Friday's gig needs a stage plot by Wednesday. Everything else is handled.",
            "You're clear today. One check may land from Capital Hilton — I'll flag it the moment it's confirmed, not before.",
        ),
    },
    "chief": {
        "agent": "chief",
        "identity": "Chief is the operations lead for OpenClaw.",
        "voice": "direct, operational, evidence-first, and bounded",
        "voice_charter": "Crisp ops steward: state the blocker, the proof, and the next bounded action.",
        "duties": "Summarize operational state, flag blockers, and preserve SEND_HOLD and money gates.",
        "humor_policy": "Minimal wit; never on failures or money.",
        "voice_exemplars": (
            "Current state: one blocker, one safe next action, no external move.",
            "I need the receipt before I mark this ready.",
        ),
    },
    "niles": {
        "agent": "niles",
        "identity": "Niles is the playful audio and vibes specialist for OpenClaw.",
        "voice": "most playful, studio-rat precise, punchy, audio-aware, and still grounded",
        "voice_charter": "Keep it quick, tactile, and musically exact; charm never outruns proof.",
        "duties": "Help with audio, music, and creative surface questions without inventing facts.",
        "humor_policy": "Small studio wit is allowed; never on failures or money.",
        "voice_exemplars": (
            "That low-mid mud? Cut 250-350Hz on the pads, tuck the bass 1dB, and the vocal will sit down in the pocket.",
            "Print the take. The timing's human in the good way — we can comp the bridge from pass two if you want it tighter.",
        ),
    },
    "guardian": {
        "agent": "guardian",
        "identity": "Guardian is the serious safety boundary reviewer for OpenClaw.",
        "voice": "dry, serious, safety-forward, and explicit about gates",
        "voice_charter": "Most serious voice: answer plainly, cite the gate, and do not soften blocked states.",
        "duties": "Review risk, enforce authority boundaries, and keep send/payment/ledger actions gated.",
        "severity_policy": "No levity. Failures, money, and authority gates stay dry.",
        "voice_exemplars": (
            "No. The packet does not grant send, payment, or ledger authority.",
            "Approval is missing; treat this as blocked until the required receipt exists.",
        ),
    },
    "cassandra": {
        "agent": "cassandra",
        "identity": "Cassandra is Clara's client-warm specialist voice.",
        "voice": "client-warm, polished, practical, and grounded",
        "voice_charter": "Warm professional client voice: clear, useful, and never loose with proof.",
        "duties": "Draft and reason about Clara-facing work while preserving source-of-truth boundaries.",
        "humor_policy": "Client warmth over wit; never on failures or money.",
        "voice_exemplars": (
            "Hi Draper, I hope the week's treating you well. Could you confirm the St. Anne's invoice made its way to Glenn? No rush — just keeping it tidy on our end. Warmly, Clara",
            "Megan, lovely to e-meet you. I'll have June's rental invoice over shortly — always happy to walk through any line item. Warmly, Clara",
        ),
    },
    "hermes": {
        "agent": "hermes",
        "identity": "Hermes is the sidecar status and routing-boundary reviewer.",
        "voice": "terse dispatch, status-clear, boundary-aware, and advisory",
        "voice_charter": "Dispatch posture only: short status, route, blocker, no flourish.",
        "duties": "Explain route posture and sidecar status without dispatching, sending, or bypassing gates.",
        "humor_policy": "No flourish; never on failures or money.",
        "voice_exemplars": (
            "Route holds. Packet source is present. No dispatch authorized.",
            "Status: ready for review, blocked for action.",
        ),
    },
}


LegacyPacketBuilder = Callable[..., Mapping[str, Any]]


def packet_engine_enabled() -> bool:
    """Return True unless OPENCLAW_PACKET_ENGINE explicitly disables the engine."""
    return os.environ.get("OPENCLAW_PACKET_ENGINE", "1").strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
    }


def build_agent_packet(
    *,
    agent: str,
    question: str = "",
    question_class: str | None = None,
    authority: Mapping[str, Any] | None = None,
    legacy_builder: LegacyPacketBuilder | None = None,
    **builder_kwargs: Any,
) -> dict[str, Any]:
    """Build an agent packet by decorating the existing context-packet builders.

    This is intentionally a strangler: data assembly still belongs to existing
    packet builders, while the packet engine adds a shared persona section and
    a build receipt around that legacy output.
    """
    started = time.perf_counter()
    normalized_agent = _normalize_agent(agent)
    persona_core = _persona_core_for(normalized_agent)
    question_class_value = str(question_class or "")
    failures: list[dict[str, str]] = []
    builder = legacy_builder or _default_maestro_builder
    builder_ref = _builder_ref(builder)
    packet: dict[str, Any] | None = None

    try:
        packet = copy.deepcopy(dict(builder(question=question, **builder_kwargs)))
    except Exception as exc:  # noqa: BLE001 - packet failures must be receipted
        failures.append(_failure_dict(exc))

    build_ms = _elapsed_ms(started)
    if packet is None:
        return _failure_packet(
            agent=normalized_agent,
            question=question,
            question_class=question_class_value,
            authority=authority,
            persona_core=persona_core,
            builder_ref=builder_ref,
            build_ms=build_ms,
            failures=failures,
        )

    decorated = _decorate_packet(
        packet,
        agent=normalized_agent,
        question_class=question_class_value,
        authority=authority,
        persona_core=persona_core,
        builder_ref=builder_ref,
        build_ms=build_ms,
        failures=failures,
    )
    return decorated


def build_fallback_receipt(
    *,
    agent: str,
    question_class: str | None,
    sources: Any = (),
    failure: BaseException | Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a receipt for front-door fail-open fallback to the legacy packet path."""
    normalized_agent = _normalize_agent(agent)
    failure_rows: list[dict[str, str]] = []
    if failure is not None:
        if isinstance(failure, Mapping):
            failure_rows.append(
                {
                    "type": str(failure.get("type") or "PacketEngineFallback"),
                    "message": str(failure.get("message") or ""),
                }
            )
        else:
            failure_rows.append(_failure_dict(failure))
    return _receipt(
        agent=normalized_agent,
        question_class=str(question_class or ""),
        sections=("legacy_packet_fallback",),
        sources=_source_refs(sources),
        build_ms=0,
        failures=failure_rows,
        status="FALLBACK_TO_LEGACY_PACKET",
        authority={},
        builder_ref="maestro_context_packet.build_maestro_context_packet",
        fallback_used=True,
    )


def _default_maestro_builder(**kwargs: Any) -> Mapping[str, Any]:
    from maestro_context_packet import build_maestro_context_packet

    return build_maestro_context_packet(**kwargs)


def _normalize_agent(agent: str) -> str:
    normalized = str(agent or "maestro").strip().lower()
    return normalized or "maestro"


def _persona_core_for(agent: str) -> dict[str, Any]:
    core = dict(PERSONA_CORES.get(agent) or PERSONA_CORES["maestro"] | {"agent": agent})
    core.setdefault("persona_core_version", PERSONA_CORE_VERSION)
    core.setdefault("token_budget", PERSONA_CORE_TOKEN_BUDGET)
    core["voice_exemplars"] = tuple(str(item) for item in core.get("voice_exemplars", ()) if str(item).strip())
    core["estimated_token_count"] = _estimate_persona_tokens(core)
    return core


def _estimate_persona_tokens(persona_core: Mapping[str, Any]) -> int:
    text_parts = [
        str(persona_core.get(key) or "")
        for key in ("identity", "voice", "voice_charter", "duties", "humor_policy", "severity_policy")
    ]
    text_parts.extend(str(item) for item in persona_core.get("voice_exemplars", ()) if str(item).strip())
    text = " ".join(text_parts)
    return len(repr(text).split())


def _persona_fact(persona_core: Mapping[str, Any]) -> dict[str, str]:
    agent = str(persona_core.get("agent") or "maestro")
    label = f"{agent.capitalize()} persona core"
    exemplars = tuple(str(item).strip() for item in persona_core.get("voice_exemplars", ()) if str(item).strip())
    value = " ".join(
        str(persona_core.get(key) or "").strip()
        for key in ("identity", "voice", "voice_charter", "duties")
        if str(persona_core.get(key) or "").strip()
    )
    if exemplars:
        value = f"{value} Exemplars: {' | '.join(exemplars)}"
    return {
        "fact_id": f"persona_core:{agent}",
        "topic": "persona_core",
        "label": label,
        "value": value,
        "source_ref": PACKET_ENGINE_PERSONA_SOURCE,
        "pii_tier": "PUBLIC",
    }


def _persona_text(persona_core: Mapping[str, Any]) -> str:
    agent = str(persona_core.get("agent") or "maestro")
    exemplars = tuple(str(item).strip() for item in persona_core.get("voice_exemplars", ()) if str(item).strip())
    return "\n".join(
        part
        for part in (
            f"{agent.capitalize()} PERSONA CORE:",
            f"Version: {persona_core.get('persona_core_version')}",
            f"Identity: {persona_core.get('identity')}",
            f"Voice: {persona_core.get('voice')}",
            f"Voice charter: {persona_core.get('voice_charter')}",
            f"Duties: {persona_core.get('duties')}",
            f"Voice exemplars: {' / '.join(exemplars)}" if exemplars else "",
            f"Token budget: {persona_core.get('estimated_token_count')}/{persona_core.get('token_budget')}",
        )
        if str(part).strip()
    )


def _decorate_packet(
    packet: dict[str, Any],
    *,
    agent: str,
    question_class: str,
    authority: Mapping[str, Any] | None,
    persona_core: Mapping[str, Any],
    builder_ref: str,
    build_ms: int,
    failures: list[dict[str, str]],
) -> dict[str, Any]:
    facts = [row for row in packet.get("facts", ()) if isinstance(row, Mapping)]
    source_refs = _source_refs(packet.get("source_refs", ()))
    persona = dict(persona_core)
    sections = ["persona_core", "legacy_packet"]
    packet["agent_id"] = agent
    packet["persona_core"] = persona
    packet["facts"] = [_persona_fact(persona), *facts]
    packet["source_refs"] = tuple(dict.fromkeys([PACKET_ENGINE_PERSONA_SOURCE, *source_refs]))
    packet["packet_text"] = "\n".join(
        part
        for part in (
            _persona_text(persona),
            str(packet.get("packet_text") or "").strip(),
        )
        if part
    )
    receipt = _receipt(
        agent=agent,
        question_class=question_class,
        sections=sections,
        sources=packet["source_refs"],
        build_ms=build_ms,
        failures=failures,
        status=str(packet.get("status") or "READY"),
        authority=authority,
        builder_ref=builder_ref,
        fallback_used=False,
    )
    packet["packet_engine_receipt"] = receipt
    proof = dict(packet.get("machine_proof") or {})
    proof.update(
        {
            "packet_engine_used": True,
            "packet_engine_receipt_id": str(receipt.get("receipt_id") or ""),
            "packet_engine_agent": agent,
            "packet_engine_persona_source": PACKET_ENGINE_PERSONA_SOURCE,
            "packet_engine_persona_core_version": persona.get("persona_core_version"),
            "packet_engine_persona_estimated_tokens": persona.get("estimated_token_count"),
            "packet_engine_sections": tuple(sections),
        }
    )
    packet["machine_proof"] = proof
    return packet


def _failure_packet(
    *,
    agent: str,
    question: str,
    question_class: str,
    authority: Mapping[str, Any] | None,
    persona_core: Mapping[str, Any],
    builder_ref: str,
    build_ms: int,
    failures: list[dict[str, str]],
) -> dict[str, Any]:
    persona = dict(persona_core)
    source_refs = (PACKET_ENGINE_PERSONA_SOURCE,)
    receipt = _receipt(
        agent=agent,
        question_class=question_class,
        sections=("persona_core", "legacy_packet"),
        sources=source_refs,
        build_ms=build_ms,
        failures=failures,
        status=PACKET_ENGINE_FAILURE_STATUS,
        authority=authority,
        builder_ref=builder_ref,
        fallback_used=False,
    )
    return {
        "schema_version": "packet_engine_packet_v1",
        "packet_id": f"packet_engine_failed:{_short_hash(agent, question, failures)}",
        "status": PACKET_ENGINE_FAILURE_STATUS,
        "question": question,
        "agent_id": agent,
        "persona_core": persona,
        "facts": [_persona_fact(persona)],
        "source_refs": source_refs,
        "packet_text": "\n".join(
            (
                _persona_text(persona),
                "PACKET ENGINE BUILD FAILED:",
                "; ".join(f"{row['type']}: {row['message']}" for row in failures),
            )
        ),
        "packet_engine_receipt": receipt,
        "machine_proof": {
            "packet_engine_used": False,
            "packet_engine_receipt_id": str(receipt.get("receipt_id") or ""),
            "packet_engine_agent": agent,
            "packet_engine_failure": True,
            "packet_engine_failures": tuple(failures),
        },
    }


def _receipt(
    *,
    agent: str,
    question_class: str,
    sections: Any,
    sources: Any,
    build_ms: int,
    failures: list[dict[str, str]],
    status: str,
    authority: Mapping[str, Any] | None,
    builder_ref: str,
    fallback_used: bool,
) -> dict[str, Any]:
    source_refs = _source_refs(sources)
    section_list = tuple(str(section) for section in sections if str(section).strip())
    authority_map = {str(key): value for key, value in dict(authority or {}).items()}
    receipt_seed = {
        "agent": agent,
        "question_class": question_class,
        "sections": section_list,
        "sources": source_refs,
        "failures": failures,
        "status": status,
        "fallback_used": fallback_used,
    }
    return {
        "schema_version": "packet_engine_receipt_v1",
        "receipt_id": f"packet_engine_receipt:{_short_hash(receipt_seed)}",
        "status": status,
        "agent": agent,
        "question_class": question_class,
        "sections": section_list,
        "sources": source_refs,
        "build_ms": max(0, int(build_ms)),
        "failures": list(failures),
        "fallback_used": fallback_used,
        "authority": authority_map,
        "builder": builder_ref,
    }


def _source_refs(value: Any) -> tuple[str, ...]:
    if isinstance(value, str):
        items = (value,)
    elif isinstance(value, Mapping):
        items = value.keys()
    else:
        try:
            items = tuple(value or ())
        except TypeError:
            items = (value,)
    return tuple(dict.fromkeys(str(item).strip() for item in items if str(item).strip()))


def _failure_dict(exc: BaseException) -> dict[str, str]:
    return {"type": type(exc).__name__, "message": str(exc)}


def _builder_ref(builder: LegacyPacketBuilder) -> str:
    module = getattr(builder, "__module__", "") or ""
    qualname = getattr(builder, "__qualname__", "") or getattr(builder, "__name__", "")
    if module and qualname:
        return f"{module}.{qualname}"
    return qualname or repr(builder)


def _elapsed_ms(started: float) -> int:
    return max(0, int(round((time.perf_counter() - started) * 1000)))


def _short_hash(*parts: Any) -> str:
    payload = repr(parts).encode("utf-8", errors="replace")
    return hashlib.sha256(payload).hexdigest()[:16]
