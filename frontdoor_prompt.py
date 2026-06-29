"""Front-door packet→prompt budgeting (FRONT-DOOR-LOCAL-MODEL-PROFILE-SPEC Rev 4/6/7).

DEFAULT-OFF / additive: this module is ONLY used by the front-door reply profile.
It bounds the *context* sent to a small local model so a budgeted prompt can return
a complete answer inside the interactive latency ceiling. It NEVER truncates the
model OUTPUT — only the CONTEXT layer (Layer B). Layer A (persona/system + task
framing) is a small fixed reserve that is ALWAYS present.

The narrowing is deterministic and recorded (manifest of kept/dropped fact ids) so
the eventual answer remains traceable.
"""

from __future__ import annotations

import os
import re
from typing import Any, Mapping


# Layer A persona/system + task framing reserve (chars). Small, fixed, ALWAYS present.
_LAYER_A_RESERVE_CHARS = 800
# Default Layer A/B max budget; env-overridable (Revision 4).
_DEFAULT_PROMPT_MAX_CHARS = 2200

_WORD_RE = re.compile(r"[a-z0-9']+")

# Layer A persona preamble — fixed framing for the front-door renderer. Kept short so
# it always fits inside the reserve. Mirrors the protected_generate system framing.
# Agent-aware personas — this is NOT a Maestro-only snowglobe. Each agent talks in its own
# voice (mirrors agent_voice_profiles roles). The CONVERSATIONAL descriptor drives casual
# chat; the grounded preamble names the agent for factual answers.
_CONVERSATIONAL_PERSONAS = {
    "maestro": "Maestro — the operator's witty, warm right hand",
    "cassandra": "Cassandra — the operator's warm, sharp executive assistant",
    "niles": "Niles — a cultured Australian studio and creative operator with dry wit",
    "chief": "Chief — a practical, no-nonsense foreman who keeps it real and a little gruff",
    "clara": "Clara — a polished, personable client-facing voice",
    "hermes": "Hermes — an elegant, precise systems advisor with a light touch",
    "guardian": "Guardian — a calm, protective gatekeeper, brief and steady",
    "openclaw": "OpenClaw — a neutral, easygoing cockpit voice",
}
_DEFAULT_AGENT = "maestro"


def _conversational_persona(agent: str | None) -> str:
    key = str(agent or _DEFAULT_AGENT).strip().lower()
    return _CONVERSATIONAL_PERSONAS.get(key, _CONVERSATIONAL_PERSONAS[_DEFAULT_AGENT])


def _agent_display_name(agent: str | None) -> str:
    key = str(agent or _DEFAULT_AGENT).strip().lower()
    return key[:1].upper() + key[1:] if key else "Maestro"


def _grounded_preamble(agent: str | None) -> str:
    name = _agent_display_name(agent)
    return (
        f"You are {name}, speaking to the operator in first person.\n"
        "If the operator is greeting you, making small talk, reacting, or just chatting, "
        "reply warmly and naturally like a sharp, easy friend — no facts required, have some "
        "personality. For a specific factual question, answer from the deterministic packet "
        "facts below; if a fact you'd need isn't there, say so plainly rather than inventing "
        "it. Be concise; never claim send/spend/mutation authority. SEND_HOLD is absolute."
    )


# Back-compat: the default (Maestro) grounded preamble as a module constant.
_LAYER_A_PREAMBLE = _grounded_preamble(_DEFAULT_AGENT)

# System-posture topics/markers are the generic facts dropped FIRST when over budget
# (Revision 4 step 3: prefer operator_truth + directly-asked topic).
_SYSTEM_POSTURE_TOPICS = frozenset(
    {"system_posture", "agent_presence", "sync_health", "capability_index", "fleet_status"}
)
_SYSTEM_POSTURE_MARKERS = (
    "fleet",
    "agents online",
    "read model",
    "read-model",
    "sync health",
    "system posture",
    "capability index",
)
_OPERATOR_TRUTH_TOPICS = frozenset({"operator_truth"})


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if value > 0 else default


def _message_terms(message: str) -> set[str]:
    return {tok for tok in _WORD_RE.findall(str(message or "").lower()) if len(tok) > 2}


def _fact_id(fact: Mapping[str, Any], index: int) -> str:
    for key in ("fact_id", "id"):
        value = fact.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return f"fact_{index}"


def _fact_source_ref(fact: Mapping[str, Any]) -> str:
    ref = fact.get("source_ref")
    if isinstance(ref, str) and ref.strip():
        return ref
    return ""


def _fact_text(fact: Mapping[str, Any]) -> str:
    parts = [str(fact.get(key) or "") for key in ("label", "value")]
    body = ": ".join(part for part in parts if part).strip()
    return body or str(fact.get("value") or "").strip()


def _is_system_posture(fact: Mapping[str, Any]) -> bool:
    topic = str(fact.get("topic") or "").strip().lower()
    if topic in _SYSTEM_POSTURE_TOPICS:
        return True
    blob = f"{fact.get('label') or ''} {fact.get('value') or ''}".lower()
    return any(marker in blob for marker in _SYSTEM_POSTURE_MARKERS)


def _is_operator_truth(fact: Mapping[str, Any]) -> bool:
    topic = str(fact.get("topic") or "").strip().lower()
    return topic in _OPERATOR_TRUTH_TOPICS


def _selection_match(fact: Mapping[str, Any], fact_selection: list[str] | None) -> bool:
    """True when this fact belongs to an interpreter-selected read-model / entity."""
    if not fact_selection:
        return False
    ref = _fact_source_ref(fact).lower()
    fid = str(fact.get("fact_id") or fact.get("id") or "").lower()
    topic = str(fact.get("topic") or "").strip().lower()
    for sel in fact_selection:
        token = str(sel or "").strip().lower()
        if not token:
            continue
        # match by read-model filename substring, fact_id, or topic
        if token in ref or token in fid or token == topic:
            return True
    return False


def _lexical_overlap(fact: Mapping[str, Any], terms: set[str]) -> int:
    if not terms:
        return 0
    blob = " ".join(str(fact.get(key) or "") for key in ("topic", "label", "value")).lower()
    return sum(1 for term in terms if term in blob)


def build_frontdoor_prompt(
    packet: Mapping[str, Any],
    message: str,
    *,
    max_chars: int | None = None,
    fact_selection: list[str] | None = None,
    agent: str = _DEFAULT_AGENT,
) -> tuple[str, dict[str, Any]]:
    """Build a budgeted front-door prompt + a kept/dropped manifest.

    Layer A (persona/system + task framing) is a small fixed reserve (~600-900 chars)
    and is ALWAYS present. Layer B (selected packet facts) gets the budgeted remainder
    ``max_chars - layer_a_reserve``. When facts exceed the Layer-B budget they are
    narrowed deterministically (Revision 4 order):
      1. keep interpreter ``fact_selection`` read-models/entities first;
      2. rank remaining facts by lexical overlap with ``message`` (keep top-N in budget);
      3. prefer operator_truth + the directly-asked topic; drop generic system-posture
         facts first;
      4. deterministic elision of lowest-rank facts.
    The model OUTPUT is NEVER truncated — only the CONTEXT.

    Returns (bounded_prompt, manifest). Manifest keys:
      context_facts_kept (int), context_facts_dropped (int),
      kept_fact_ids (list), dropped_fact_ids (list), prompt_context_chars (int),
      prompt_chars (int), layer_a_chars (int), max_chars (int), over_budget (bool).
    """
    if max_chars is None:
        max_chars = _env_int("OPENCLAW_FRONTDOOR_PROMPT_MAX_CHARS", _DEFAULT_PROMPT_MAX_CHARS)

    # SOCIAL CONVERSATIONAL LANE: for greetings/reactions/small talk, a heavy grounded
    # prompt (persona + packet + constraints) makes the small model RECITE system posture
    # instead of chatting. A lightweight prompt — no facts, no protocol-speak — lets it
    # actually talk. Factual/schedule/clarification messages fall through to the grounded
    # path below (grounding intact).
    try:
        from social_intent import is_social_intent
        _social = is_social_intent(message)
    except Exception:
        _social = False
    if _social:
        persona = _conversational_persona(agent)
        name = _agent_display_name(agent)
        convo = (
            f"You are {persona}. Reply in first person — natural, easy, and short, like "
            "texting a friend back. Keep it low-key: DON'T try hard, skip the forced "
            "metaphors, zingers, and filler. One or two plain sentences is plenty. Don't "
            "mention systems, protocols, SEND_HOLD, status, packets, or facts unless the "
            "operator brings them up. Just talk like a normal person.\n\n"
            f"The operator just said: \"{message}\"\n\n{name}:"
        )
        manifest = {
            "context_facts_kept": 0, "context_facts_dropped": 0, "kept_fact_ids": [],
            "dropped_fact_ids": [], "prompt_context_chars": 0, "prompt_chars": len(convo),
            "layer_a_chars": len(convo), "max_chars": max_chars, "layer_b_budget": 0,
            "over_budget": False, "conversational_lane": True,
        }
        return convo, manifest

    layer_a = _grounded_preamble(agent)
    layer_a_chars = len(layer_a)
    # Layer A reserve is the smaller of the fixed reserve and the actual preamble size;
    # Layer B budget is whatever remains. Layer A is ALWAYS emitted in full.
    layer_a_reserve = min(_LAYER_A_RESERVE_CHARS, layer_a_chars) if layer_a_chars else _LAYER_A_RESERVE_CHARS
    layer_b_budget = max(0, max_chars - max(layer_a_reserve, layer_a_chars))

    raw_facts = packet.get("facts") if isinstance(packet, Mapping) else None
    facts = [f for f in (raw_facts or ()) if isinstance(f, Mapping)]

    terms = _message_terms(message)

    # Rank facts deterministically. Lower rank_key sorts first (kept first).
    # Priority tier (smaller = keep first):
    #   0 interpreter-selected facts
    #   1 operator_truth / lexical-overlap facts (non-posture)
    #   2 other non-posture facts
    #   3 generic system-posture facts (dropped first)
    ranked: list[tuple[tuple[int, int, int], str, str, Mapping[str, Any]]] = []
    for index, fact in enumerate(facts):
        fid = _fact_id(fact, index)
        selected = _selection_match(fact, fact_selection)
        posture = _is_system_posture(fact)
        overlap = _lexical_overlap(fact, terms)
        operator_truth = _is_operator_truth(fact)
        if selected:
            tier = 0
        elif posture:
            tier = 3
        elif operator_truth or overlap > 0:
            tier = 1
        else:
            tier = 2
        # within a tier: higher overlap first (negate), then stable original order
        rank_key = (tier, -overlap, index)
        line = _fact_text(fact)
        ranked.append((rank_key, fid, line, fact))

    ranked.sort(key=lambda item: item[0])

    kept_ids: list[str] = []
    dropped_ids: list[str] = []
    kept_lines: list[str] = []
    used_chars = 0
    # over_budget reflects BUDGET narrowing only — a non-empty fact that could not fit.
    # Empty facts are dropped for traceability but are NOT budget pressure.
    budget_narrowing_occurred = False
    for _rank_key, fid, line, _fact in ranked:
        if not line:
            # empty facts contribute nothing; record as dropped for traceability
            dropped_ids.append(fid)
            continue
        # +1 for the joining newline between facts
        addition = len(line) + (1 if kept_lines else 0)
        if used_chars + addition <= layer_b_budget:
            kept_lines.append(line)
            kept_ids.append(fid)
            used_chars += addition
        else:
            dropped_ids.append(fid)
            budget_narrowing_occurred = True

    layer_b = "\n".join(kept_lines)
    prompt_context_chars = len(layer_b)

    prompt = (
        f"{layer_a}\n\n"
        "DETERMINISTIC PACKET (facts you may use; may be empty):\n"
        f"{layer_b}\n\n"
        "OPERATOR JUST SAID:\n"
        f"{message}\n\n"
        f"Now write {_agent_display_name(agent)}'s reply — first person, speaking directly to "
        "the operator. Do NOT describe or summarize the text above; just respond.\n"
        f"{_agent_display_name(agent)}:"
    )

    manifest: dict[str, Any] = {
        "context_facts_kept": len(kept_ids),
        "context_facts_dropped": len(dropped_ids),
        "kept_fact_ids": kept_ids,
        "dropped_fact_ids": dropped_ids,
        "prompt_context_chars": prompt_context_chars,
        "prompt_chars": len(prompt),
        "layer_a_chars": layer_a_chars,
        "max_chars": max_chars,
        "layer_b_budget": layer_b_budget,
        "over_budget": budget_narrowing_occurred,
    }
    return prompt, manifest


__all__ = ["build_frontdoor_prompt"]
