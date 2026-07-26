"""Spawn a doer: a character, played by a model, given a target.

The LM2 spot in the pipeline (gate -> LM1 -> gate -> SQLite -> gate -> LM2) is
sometimes an autospawned DOER. It keeps the agent's name — Cassandra, Niles,
Chief — but is *played by* whichever model fits the task:

    easy_lane  -> gpt-5.6-luna      mid_lane   -> gpt-5.6-terra
    hard_lane  -> gpt-5.6-sol       local_safe -> qwen3:8b

Character is data (`agent_voice_profiles`), actor is a routing decision
(`external_brain_router` + `model_lane_bindings.json`), and the packet is the
script. A doer's packet is target-shaped: the assignment, the facts bearing on
it, and deliberately nothing else — breadth is where a doer drifts.

**A doer produces WORK PRODUCT, never effects.** It returns text: a draft, a
plan, an answer. Money movement, external sends, deletes, installs and
enrollment remain operator-gated regardless of what a doer concludes. Nothing
in this module executes an effect.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Mapping

import external_brain_router
from packet_engine import build_agent_packet

DOER_INSTRUCTION = (
    "You are working an assignment. Use only the facts in this packet. "
    "Produce the work product asked for. If the packet does not cover "
    "something you need, say so plainly instead of guessing.\n"
    "You hold NO authority to send, pay, delete, install, enrol or change a "
    "gate. If the assignment implies any of those, produce the artifact up to "
    "that line and STOP.\n"
    "Never accomplish this target by getting AROUND a constraint. Do not "
    "BYPASS, disable, weaken or work around any guard, gate, check, test, "
    "permission or approval — not even to succeed at the assignment. A guard "
    "that blocks you is the answer, not the obstacle: STOP and say exactly "
    "which wall you hit. A partial result reported honestly is a SUCCESS; a "
    "complete result obtained by routing around a rule is a FAILURE."
)

# The doer prompt must fit the model that plays it. An over-context prompt
# comes back as a silent empty string, which reads like "the doer had nothing
# to say" while actually hiding a real wall. Measured against the live local
# model (qwen3:8b, 2048-token context): ~3k chars answers, ~4.9k returns empty.
DEFAULT_MAX_PROMPT_CHARS = 3_000


class _PromptTooLong(Exception):
    """Internal: prompt exceeds what the playing model can accept."""


@dataclass(frozen=True)
class DoerSpawn:
    """One spawned doer run: who played it, what it was told, what it produced."""

    agent: str
    model: str
    lane: str
    target: str
    packet: Mapping[str, Any]
    result: str | None
    receipt: Mapping[str, Any]
    error: str | None = None
    prompt_chars: int = 0


def _resolve_actor(
    *, agent: str, task_type: str, risk_tier: str, context_size: str
) -> tuple[str, str]:
    """Pick the lane (difficulty) and the model that plays this character."""

    lane = external_brain_router.select_difficulty_lane(
        task_type=task_type or "general task",
        risk_tier=risk_tier,
        context_size=context_size,
    )
    bindings = external_brain_router.load_model_lane_bindings()
    allowed = (
        bindings.get("agent_bindings", {}).get(agent, {}).get("allowed_lanes") or ()
    )
    if allowed and lane not in allowed:
        # Never exceed an agent's bound lanes — fall back to its best allowed.
        lane = allowed[-1]
    model = str(bindings["lanes"][lane].get("model") or "")
    return lane, model


def _default_model_call(prompt: str, *, lane: str = "", model: str = "") -> str:
    """Local, fit-walled invocation. External lanes route through the brain."""

    from adaptive_model_call import adaptive_ollama_text

    return adaptive_ollama_text(prompt, timeout=120, task_class="doer_spawn")


def _coverage_gap(packet: Mapping[str, Any], *, target: str, question: str) -> str:
    """Name what the packet fails to cover, or "" when it covers the target.

    Potency selects the best facts available — it cannot concentrate a fact the
    knowledge base does not hold. When nothing in the packet bears on the
    target, asking the model anyway is an invitation to confabulate. Dank af or
    an honest gap; never a confident fabrication.
    """
    import read_model_demand_index as _dmi

    tokens = _dmi._tokenize(f"{target} {question}")
    if not tokens:
        return ""
    for row in packet.get("facts", ()):
        if not isinstance(row, Mapping):
            continue
        marker = f"{row.get('topic','')} {row.get('fact_id','')}".lower()
        if "persona" in marker or "doctrine" in marker:
            continue  # identity is not coverage
        text = " ".join(
            str(row.get(key, "")) for key in ("topic", "label", "value", "source_ref")
        )
        if tokens & _dmi._tokenize(text):
            return ""
    missing = ", ".join(sorted(tokens)[:6])
    return f"packet_does_not_cover_target:{missing}"


def spawn_doer(
    agent: str,
    target: str,
    *,
    question: str = "",
    task_type: str = "",
    risk_tier: str = "low",
    context_size: str = "small",
    legacy_builder: Callable[..., Mapping[str, Any]] | None = None,
    model_call: Callable[..., str] | None = None,
    max_prompt_chars: int = DEFAULT_MAX_PROMPT_CHARS,
    research: bool = True,
    **builder_kwargs: Any,
) -> DoerSpawn:
    """Spawn ``agent`` as a doer against ``target`` and return its work product."""

    lane, model = _resolve_actor(
        agent=agent,
        task_type=task_type or target,
        risk_tier=risk_tier,
        context_size=context_size,
    )
    packet = build_agent_packet(
        agent=agent,
        question=question or target,
        consumer_kind="spawned",
        target=target,
        legacy_builder=legacy_builder,
        **builder_kwargs,
    )
    prompt = "\n\n".join(
        part
        for part in (
            DOER_INSTRUCTION,
            str(packet.get("packet_text") or "").strip(),
            f"Deliver the work product for: {target}",
        )
        if part
    )

    caller = model_call or _default_model_call
    result: str | None = None
    error: str | None = None
    gap = _coverage_gap(packet, target=target, question=question)
    researched = ""
    if gap and research:
        # Do not invite a guess — go and learn it, then answer from what was
        # learned. Only the unknown term is searched, and what comes back is
        # labelled web-sourced with its URL.
        import gap_research

        learned = gap_research.research_gap(
            target=target, uncovered_terms=gap.split(":", 1)[-1].split(", ")
        )
        if learned:
            packet = dict(packet)
            packet["facts"] = [*packet.get("facts", ()), learned]
            packet["packet_text"] = "\n".join(
                part
                for part in (
                    str(packet.get("packet_text") or "").strip(),
                    f"- {learned['label']}: {learned['value']} "
                    f"[web source: {learned['source_ref']}]",
                )
                if part
            )
            prompt = "\n\n".join(
                part
                for part in (
                    DOER_INSTRUCTION,
                    str(packet.get("packet_text") or "").strip(),
                    f"Deliver the work product for: {target}",
                )
                if part
            )
            researched = learned["source_ref"]
            gap = ""
    if gap:
        # Nothing learned — report the gap rather than let anything be invented.
        error = gap
    if not error and max_prompt_chars and len(prompt) > max_prompt_chars:
        # Honest wall, not a silent empty answer.
        error = (
            f"prompt_exceeds_model_context:{len(prompt)}>{max_prompt_chars}"
        )
    try:
        if error:
            raise _PromptTooLong(error)
        raw = caller(prompt, lane=lane, model=model)
        result = str(raw or "").strip() or None
        if result is None:
            error = "empty_model_reply"
    except TypeError:
        try:
            result = str(caller(prompt) or "").strip() or None
            if result is None:
                error = "empty_model_reply"
        except Exception as exc:  # honest failure, never a fabricated result
            error = type(exc).__name__
    except _PromptTooLong:
        pass
    except Exception as exc:
        error = type(exc).__name__

    dankness = packet.get("packet_dankness") or {}
    receipt = {
        "schema_version": "doer_spawn_receipt_v1",
        "agent": agent,
        "played_by": model,
        "lane": lane,
        "target": target,
        "consumer_kind": "spawned",
        "packet_receipt_id": str(
            (packet.get("packet_engine_receipt") or {}).get("receipt_id") or ""
        ),
        "packet_dankness_overall": dankness.get("overall"),
        "fact_count": len(packet.get("facts") or ()),
        "result_chars": len(result or ""),
        "error": error or "",
        "gap": gap,
        "researched": researched,
        # A doer is a producer of work product. Effects stay operator-gated.
        "effect_authority": "none",
    }
    return DoerSpawn(
        agent=agent,
        model=model,
        lane=lane,
        target=target,
        packet=packet,
        result=result,
        receipt=receipt,
        error=error,
        prompt_chars=len(prompt),
    )
