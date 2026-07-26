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
    target: str = "",
    session_id: str = "",
    persona_already_delivered: bool = False,
    turn_self_facts: Mapping[str, Any] | None = None,
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
    if packet is not None and normalized_consumer == "spawned":
        packet = _concentrate_for_doer(packet, target=target, question=question)
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
            turn_self_facts=turn_self_facts,
            builder_ref=builder_ref,
            build_ms=build_ms,
            failures=failures,
        )

    decorated = _decorate_packet(
        packet,
        agent=normalized_agent,
        question=question,
        question_class=question_class_value,
        authority=authority,
        persona_core=persona_core,
        consumer_kind=normalized_consumer,
        target=target,
        session_id=session_id,
        persona_already_delivered=persona_already_delivered,
        turn_self_facts=turn_self_facts,
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
    autonomy_ladder = dict(persona_core.get("autonomy_ladder") or {})
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
                f"Autonomy rung: {autonomy_ladder.get('rung')} "
                "(classification only; no new authority)"
                if autonomy_ladder
                else ""
            ),
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
    autonomy_ladder = dict(persona_core.get("autonomy_ladder") or {})
    delivery = {
        "mode": mode,
        "consumer_kind": consumer_kind,
        "session_id": str(session_id or ""),
        "voice_profile_ref": persona_core["voice_profile_ref"],
        "persona_core_version": persona_core["persona_core_version"],
        "core_sha256": persona_core["core_sha256"],
        "autonomy_rung": str(autonomy_ladder.get("rung") or ""),
        "autonomy_classification_only": bool(autonomy_ladder.get("classification_only")),
        "autonomy_new_authority_conferred": bool(
            autonomy_ladder.get("new_authority_conferred")
        ),
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


def _score_packet_dankness(packet: dict[str, Any], question: str) -> dict[str, Any]:
    """Score every engine-built packet.

    The critic existed and was registered, but nothing in a reply path called
    it, so no real packet was ever scored. Scoring here means all agents get
    the feedback loop. Scoring must never break a packet: a critic failure is
    reported on the packet, not raised.
    """
    try:
        import dataclasses

        import packet_dankness_critic

        score = packet_dankness_critic.score_packet_dankness(packet, question)
        return {
            key: value
            for key, value in dataclasses.asdict(score).items()
            if not key.startswith("_")
        }
    except Exception as exc:  # scoring is advisory; never fail a packet on it
        return {"error": type(exc).__name__}


# A doer packet is deliberately narrow: the target, what bears on it, and
# nothing else. Extra breadth is where a spawned agent drifts off-assignment.
SPAWNED_FACT_LIMIT = 8
# Potency bounds for a doer packet: enough signal to act, small enough to fit.
DOER_FACT_VALUE_CHARS = 220
DOER_PACKET_TEXT_CHARS = 1_800


def _shape_for_doer(
    packet: dict[str, Any], *, target: str, question: str
) -> dict[str, Any]:
    """Narrow a packet to its assignment.

    Daemon packets are for judgement and keep their breadth. A spawned doer is
    told "this is your target" — so it gets the facts bearing on that target,
    bounded, plus an explicit assignment block. Never drops facts when nothing
    matches: an unfiltered packet beats an empty one.
    """
    import read_model_demand_index

    focus = f"{target} {question}".strip()
    tokens = read_model_demand_index._tokenize(focus)
    facts = [row for row in packet.get("facts", ()) if isinstance(row, Mapping)]
    if tokens and facts:
        scored = [
            (
                len(
                    tokens
                    & read_model_demand_index._tokenize(
                        " ".join(
                            str(row.get(key, "")) for key in ("topic", "label", "value")
                        )
                    )
                ),
                row,
            )
            for row in facts
        ]
        # Persona and doctrine facts are identity, not breadth — narrowing the
        # assignment must never strip who the doer is or the rules it works under.
        def _is_identity(row: Mapping[str, Any]) -> bool:
            marker = f"{row.get('topic','')} {row.get('fact_id','')}".lower()
            return "persona" in marker or "doctrine" in marker

        kept = [row for score, row in scored if score > 0 or _is_identity(row)]
        if any(score > 0 for score, _ in scored):
            facts = kept[:SPAWNED_FACT_LIMIT]
    packet["facts"] = facts
    packet["assignment"] = {
        "target": target,
        "mode": "doer",
        "instruction": (
            "This is your assignment. Work only from the facts in this packet. "
            "If the packet does not cover something you need, say so plainly "
            "instead of guessing."
        ),
    }
    existing_text = str(packet.get("packet_text") or "").strip()
    packet["packet_text"] = "\n".join(
        part for part in (f"ASSIGNMENT: {target}" if target else "", existing_text) if part
    )
    return packet


def _concentrate_for_doer(packet: dict[str, Any], *, target: str = "", question: str = ""
) -> dict[str, Any]:
    """Cure the legacy packet to its signal, before decoration.

    Premium potency is not "smaller" — it is maximum signal per token. So:
    rank facts against the assignment, spend the budget on the ones that earn
    it, and distil the resinous part out of each long value instead of cutting
    at an arbitrary character. Runs BEFORE persona and doctrine merge in, so
    curing the data can never cost a doer its identity or its rules.
    """
    import read_model_demand_index as _dmi

    tokens = _dmi._tokenize(f"{target} {question}")
    rows = [dict(r) for r in packet.get("facts", ()) if isinstance(r, Mapping)]

    def _relevance(row: Mapping[str, Any]) -> int:
        text = " ".join(
            str(row.get(k, "")) for k in ("topic", "label", "value", "source_ref")
        )
        return len(tokens & _dmi._tokenize(text))

    ranked = sorted(rows, key=lambda r: -_relevance(r))
    earning = [r for r in ranked if _relevance(r) > 0] or ranked

    # Spend the budget top-down: the most relevant fact gets room to be useful.
    kept: list[dict[str, Any]] = []
    spent = 0
    for row in earning:
        if spent >= DOER_PACKET_TEXT_CHARS:
            break
        row["value"] = _distil_value(str(row.get("value") or ""), tokens)
        kept.append(row)
        spent += len(str(row.get("label") or "")) + len(row["value"]) + 4

    packet["facts"] = kept
    packet["packet_text"] = "\n".join(
        f"- {row.get('label')}: {row.get('value')}" for row in kept
    )[:DOER_PACKET_TEXT_CHARS]
    return packet


def _distil_value(value: str, tokens: set[str]) -> str:
    """Keep the parts of a value that bear on the assignment.

    A long JSON dump truncated at a fixed character loses whatever mattered if
    it happened to sit at the end. Instead keep the fragments that match the
    assignment, and only fall back to a head-cut when nothing matches.
    """
    import re

    import read_model_demand_index as _dmi

    if len(value) <= DOER_FACT_VALUE_CHARS:
        return value
    fragments = [f for f in re.split(r"[,\n]", value) if f.strip()]
    hits = [f.strip().strip("{}\"' ") for f in fragments if tokens & _dmi._tokenize(f)]
    if hits:
        joined = "; ".join(dict.fromkeys(hits))
        return joined[:DOER_FACT_VALUE_CHARS]
    return value[:DOER_FACT_VALUE_CHARS]


def _decorate_packet(
    packet: dict[str, Any],
    *,
    agent: str,
    question: str,
    question_class: str,
    authority: Mapping[str, Any] | None,
    persona_core: Mapping[str, Any],
    consumer_kind: str,
    target: str = "",
    session_id: str = "",
    persona_already_delivered: bool = False,
    turn_self_facts: Mapping[str, Any] | None = None,
    builder_ref: str = "",
    build_ms: int,
    failures: list[dict[str, str]],
) -> dict[str, Any]:
    facts = [row for row in packet.get("facts", ()) if isinstance(row, Mapping)]
    source_refs = list(_source_refs(packet.get("source_refs", ())))
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
    from gig_business_doctrine import build_doctrine_delivery

    doctrine_delivery = build_doctrine_delivery(
        agent_id=agent,
        question_class=question_class,
        question=question,
    )
    if doctrine_delivery["status"] != "NOT_RELEVANT":
        packet["gig_business_doctrine_delivery"] = doctrine_delivery
        packet["packet_text"] = "\n".join(
            part
            for part in (
                str(packet.get("packet_text") or "").strip(),
                str(doctrine_delivery.get("packet_text") or "").strip(),
            )
            if part
        )
        sections.append("gig_business_doctrine")
        if doctrine_delivery["status"] == "READY":
            source_refs.append(str(doctrine_delivery["source_ref"]))
        else:
            packet["status"] = "GIG_BUSINESS_DOCTRINE_UNAVAILABLE"
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
    if turn_self_facts:
        from agent_introspection import inject_turn_self_facts

        packet = inject_turn_self_facts(packet, turn_self_facts)
        sections.append("turn_self_facts")
    # Shape last: the doer packet must be narrowed AFTER persona and
    # self-facts land, and scored on exactly what the consumer receives.
    if consumer_kind == "spawned":
        packet = _shape_for_doer(packet, target=target, question=question)
    packet["packet_dankness"] = _score_packet_dankness(packet, question)
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
            "packet_engine_autonomy_rung": dict(persona.get("autonomy_ladder") or {}).get("rung"),
            "packet_engine_autonomy_classification_only": dict(
                persona.get("autonomy_ladder") or {}
            ).get("classification_only"),
            "packet_engine_autonomy_new_authority_conferred": dict(
                persona.get("autonomy_ladder") or {}
            ).get("new_authority_conferred"),
            "packet_engine_sections": tuple(sections),
            "turn_self_facts_delivered": bool(turn_self_facts),
        }
    )
    packet["machine_proof"] = proof
    if doctrine_delivery["status"] != "NOT_RELEVANT":
        proof.update(
            {
                "gig_business_doctrine_ref": doctrine_delivery["doctrine_ref"],
                "gig_business_doctrine_source_sha256": doctrine_delivery[
                    "source_sha256"
                ],
                "gig_business_doctrine_freshness_class": doctrine_delivery[
                    "freshness"
                ]["freshness_class"],
                "gig_business_pricing_logistics_source_policy": doctrine_delivery[
                    "pricing_logistics_source_policy"
                ],
                "gig_business_doctrine_section_ids": tuple(
                    section["section_id"]
                    for section in doctrine_delivery["sections"]
                ),
                "gig_business_doctrine_current": doctrine_delivery["status"]
                == "READY",
                "gig_business_doctrine_delivery_status": doctrine_delivery[
                    "status"
                ],
            }
        )
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
    turn_self_facts: Mapping[str, Any] | None,
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
    sections = [
        "persona_core" if include_persona else "standing_persona_ref",
        "legacy_packet",
    ]
    if turn_self_facts:
        sections.append("turn_self_facts")
    receipt = _receipt(
        agent=agent,
        question_class=question_class,
        sections=sections,
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
    if turn_self_facts:
        from agent_introspection import inject_turn_self_facts

        result = inject_turn_self_facts(result, turn_self_facts)
        result["machine_proof"]["turn_self_facts_delivered"] = True
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
