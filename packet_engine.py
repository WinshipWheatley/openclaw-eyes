"""PacketEngine strangler for agent-specific front-door context packets."""

from __future__ import annotations

import copy
import hashlib
import os
import time
from typing import Any, Callable, Mapping


PACKET_ENGINE_PERSONA_SOURCE = "agent_voice_profiles:immutable_persona_core"
PACKET_ENGINE_FAILURE_STATUS = "PACKET_ENGINE_BUILD_FAILED"
PERSONA_CORE_TOKEN_BUDGET = 220


def _canonical_persona_cores() -> dict[str, dict[str, Any]]:
    from agent_voice_profiles import immutable_persona_core_for_speaker

    return {
        agent: immutable_persona_core_for_speaker(agent)
        for agent in ("maestro", "chief", "niles", "guardian", "cassandra", "hermes")
    }


# Compatibility export for inspectors; authored only by agent_voice_profiles.
PERSONA_CORES = _canonical_persona_cores()


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
    consumer_kind: str = "daemon",
    session_id: str = "",
    persona_already_delivered: bool = False,
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
    normalized_consumer = str(consumer_kind or "daemon").strip().lower()
    if normalized_consumer not in {"daemon", "spawned"}:
        raise ValueError(f"Unsupported packet consumer_kind: {consumer_kind}")
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
            consumer_kind=normalized_consumer,
            session_id=session_id,
            persona_already_delivered=persona_already_delivered,
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
        consumer_kind=normalized_consumer,
        session_id=session_id,
        persona_already_delivered=persona_already_delivered,
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
    from agent_voice_profiles import immutable_persona_core_for_speaker

    core = dict(immutable_persona_core_for_speaker(agent))
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
    quiet_luxury = dict(persona_core.get("quiet_luxury") or {})
    register_flow = " -> ".join(str(item) for item in quiet_luxury.get("flow", ()) if str(item))
    return "\n".join(
        part
        for part in (
            f"{agent.capitalize()} PERSONA CORE:",
            f"Version: {persona_core.get('persona_core_version')}",
            f"Identity: {persona_core.get('identity')}",
            f"Voice: {persona_core.get('voice')}",
            f"Voice charter: {persona_core.get('voice_charter')}",
            f"Duties: {persona_core.get('duties')}",
            (
                f"Quiet Luxury doctrine: {quiet_luxury.get('doctrine_ref')} "
                f"({register_flow})"
                if quiet_luxury
                else ""
            ),
            f"Voice exemplars: {' / '.join(exemplars)}" if exemplars else "",
            f"Token budget: {persona_core.get('estimated_token_count')}/{persona_core.get('token_budget')}",
        )
        if str(part).strip()
    )


def _persona_source_refs(persona_core: Mapping[str, Any]) -> tuple[str, ...]:
    quiet_luxury = dict(persona_core.get("quiet_luxury") or {})
    doctrine_path = str(quiet_luxury.get("doctrine_path") or "").strip()
    return tuple(dict.fromkeys([PACKET_ENGINE_PERSONA_SOURCE, doctrine_path] if doctrine_path else [PACKET_ENGINE_PERSONA_SOURCE]))


def _persona_delivery(
    persona_core: Mapping[str, Any],
    *,
    mode: str,
    consumer_kind: str,
    session_id: str,
) -> dict[str, Any]:
    quiet_luxury = dict(persona_core.get("quiet_luxury") or {})
    delivery = {
        "mode": mode,
        "consumer_kind": consumer_kind,
        "session_id": str(session_id or ""),
        "voice_profile_ref": persona_core["voice_profile_ref"],
        "persona_core_version": persona_core["persona_core_version"],
        "core_sha256": persona_core["core_sha256"],
    }
    if quiet_luxury:
        delivery.update(
            {
                "doctrine_ref": quiet_luxury["doctrine_ref"],
                "doctrine_path": quiet_luxury["doctrine_path"],
                "register_flow": list(quiet_luxury["flow"]),
                "severity_integrity": quiet_luxury["severity_integrity"],
            }
        )
    return delivery


def _decorate_packet(
    packet: dict[str, Any],
    *,
    agent: str,
    question_class: str,
    authority: Mapping[str, Any] | None,
    persona_core: Mapping[str, Any],
    consumer_kind: str,
    session_id: str,
    persona_already_delivered: bool,
    builder_ref: str,
    build_ms: int,
    failures: list[dict[str, str]],
) -> dict[str, Any]:
    facts = [row for row in packet.get("facts", ()) if isinstance(row, Mapping)]
    source_refs = _source_refs(packet.get("source_refs", ()))
    persona = dict(persona_core)
    include_persona = consumer_kind == "spawned" and not persona_already_delivered
    delivery_mode = (
        "first_spawn_package"
        if include_persona
        else "spawn_session_already_has_persona"
        if consumer_kind == "spawned"
        else "standing_daemon_profile"
    )
    sections = ["persona_core" if include_persona else "standing_persona_ref", "legacy_packet"]
    packet["agent_id"] = agent
    packet["persona_delivery"] = _persona_delivery(
        persona,
        mode=delivery_mode,
        consumer_kind=consumer_kind,
        session_id=session_id,
    )
    if include_persona:
        packet["persona_core"] = persona
        packet["facts"] = [_persona_fact(persona), *facts]
    else:
        packet.pop("persona_core", None)
        packet["facts"] = facts
    packet["source_refs"] = tuple(dict.fromkeys([*_persona_source_refs(persona), *source_refs]))
    if include_persona:
        packet["packet_text"] = "\n".join(
            part for part in (_persona_text(persona), str(packet.get("packet_text") or "").strip()) if part
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
            "packet_engine_doctrine_ref": dict(persona.get("quiet_luxury") or {}).get("doctrine_ref"),
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
    consumer_kind: str,
    session_id: str,
    persona_already_delivered: bool,
    builder_ref: str,
    build_ms: int,
    failures: list[dict[str, str]],
) -> dict[str, Any]:
    persona = dict(persona_core)
    include_persona = consumer_kind == "spawned" and not persona_already_delivered
    delivery_mode = (
        "first_spawn_package" if include_persona else
        "spawn_session_already_has_persona" if consumer_kind == "spawned" else
        "standing_daemon_profile"
    )
    source_refs = _persona_source_refs(persona)
    receipt = _receipt(
        agent=agent,
        question_class=question_class,
        sections=(("persona_core" if include_persona else "standing_persona_ref"), "legacy_packet"),
        sources=source_refs,
        build_ms=build_ms,
        failures=failures,
        status=PACKET_ENGINE_FAILURE_STATUS,
        authority=authority,
        builder_ref=builder_ref,
        fallback_used=False,
    )
    result = {
        "schema_version": "packet_engine_packet_v1",
        "packet_id": f"packet_engine_failed:{_short_hash(agent, question, failures)}",
        "status": PACKET_ENGINE_FAILURE_STATUS,
        "question": question,
        "agent_id": agent,
        "persona_delivery": _persona_delivery(
            persona,
            mode=delivery_mode,
            consumer_kind=consumer_kind,
            session_id=session_id,
        ),
        "facts": [_persona_fact(persona)] if include_persona else [],
        "source_refs": source_refs,
        "packet_text": "\n".join(
            part for part in (
                _persona_text(persona) if include_persona else "",
                "PACKET ENGINE BUILD FAILED:",
                "; ".join(f"{row['type']}: {row['message']}" for row in failures),
            ) if part
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
    if include_persona:
        result["persona_core"] = persona
    return result


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
