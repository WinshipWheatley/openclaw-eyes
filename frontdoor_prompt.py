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
from datetime import date
from typing import Any, Mapping

from agent_voice_profiles import (
    SPEAKER_REFS,
    conversational_prompt_descriptor_for_speaker,
)

# Layer A persona/system + task framing reserve (chars). Small, fixed, ALWAYS present.
_LAYER_A_RESERVE_CHARS = 800
# Default Layer A/B max budget; env-overridable (Revision 4).
_DEFAULT_PROMPT_MAX_CHARS = 2200

_WORD_RE = re.compile(r"[a-z0-9']+")
_DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")
_STALE_FACT_DAYS = 14

# Layer A persona preamble — fixed framing for the front-door renderer. Kept short so
# it always fits inside the reserve. Mirrors the protected_generate system framing.
# Agent-aware personas are consumed from agent_voice_profiles.py. Keeping the
# descriptor in the canonical registry prevents a listener or draft path from
# quietly growing a second, stale version of an agent's voice.
_DEFAULT_AGENT = "maestro"


def _conversational_persona(agent: str | None) -> str:
    key = str(agent or _DEFAULT_AGENT).strip().lower()
    if key not in SPEAKER_REFS:
        key = _DEFAULT_AGENT
    return conversational_prompt_descriptor_for_speaker(key)


def _agent_display_name(agent: str | None) -> str:
    key = str(agent or _DEFAULT_AGENT).strip().lower()
    if key == "clara":
        return "Cassandra using the Clara Reid external register"
    return key[:1].upper() + key[1:] if key else "Maestro"


def _grounded_preamble(agent: str | None) -> str:
    name = _agent_display_name(agent)
    key = str(agent or _DEFAULT_AGENT).strip().lower()
    agent_note = ""
    if key in {"cassandra", "clara"}:
        agent_note = (
            "\nCassandra/Clara finance rule: when the operator describes a new gig, payment, "
            "or amount that resembles an existing receivable, do not silently merge them. "
            "Ask whether it is the same receivable or a new gig/payment before treating them "
            "as one item. If the packet names an existing Coupa/Capital Hilton receivable "
            "with the same amount, ask directly whether the new gig is that receivable or "
            "separate money. If no packet fact proves the match, ask whether it is separate "
            "money or tied to an existing Coupa/Capital Hilton receivable; do not name "
            "unrelated Niles/Reynolds gigs in this finance ambiguity lane."
        )
    elif key == "niles":
        agent_note = (
            "\nNiles rule: for music, set, gig, or studio questions, use concrete Niles packet "
            "facts such as track names, transitions, venues, set constraints, or album posture. "
            "If any concrete packet fact is present, name at least one of it. Keep it musically "
            "literate and lightly characterful, not generic inspiration."
        )
    elif key == "guardian":
        agent_note = (
            "\nGuardian rule: for advisory safety questions, answer with a concise protective "
            "checklist. Do not stage or imply action unless the operator gave a real imperative "
            "send/pay/reply/approve command."
        )
    return (
        f"You are {name}, speaking to the operator in first person.\n"
        "If the operator is greeting you, making small talk, reacting, or just chatting, "
        "reply warmly and naturally like a sharp, easy friend — no facts required, have some "
        "personality. For a specific factual question, answer from the deterministic packet "
        "facts below; if a fact you'd need isn't there, say so plainly rather than inventing "
        "it. Do not present stale facts as current; say \"as of...\" or \"needs refresh.\" "
        "Be concise; never claim send/spend/mutation authority. SEND_HOLD is absolute."
        f"{agent_note}"
    )


def _is_niles_audio_advice_request(agent: str | None, message: str) -> bool:
    key = str(agent or _DEFAULT_AGENT).strip().lower()
    if key != "niles":
        return False
    message_lower = str(message or "").lower()
    return any(marker in message_lower for marker in _NILES_AUDIO_ADVICE_MARKERS)


def _fact_blob(fact: Mapping[str, Any]) -> str:
    return " ".join(
        str(value or "")
        for value in (
            fact.get("fact_id"),
            fact.get("id"),
            fact.get("topic"),
            fact.get("label"),
            fact.get("value"),
            _fact_source_ref(fact),
        )
    ).lower()


def _is_audio_domain_fact(fact: Mapping[str, Any]) -> bool:
    blob = _fact_blob(fact)
    return any(marker in blob for marker in _AUDIO_DOMAIN_FACT_MARKERS)


def _niles_audio_advice_facts() -> list[dict[str, Any]]:
    try:
        import niles_rig_kb

        lines = (
            *niles_rig_kb.x32_control_summary_lines(),
            *niles_rig_kb.x32_vocal_channel_advice_lines(),
        )
    except Exception:
        lines = (
            "X32 vocal channel advice: start with gain, HPF, light compression, EQ shaping, and careful monitor sends.",
            "This is advice only; no hardware, OSC, MIDI, DAW, or live execution is authorized.",
        )
    return [
        {
            "fact_id": "niles_audio_advice:x32_vocal_channel",
            "topic": "niles_audio_advice",
            "label": "Niles X32 vocal channel advice",
            "value": " ".join(lines),
            "source_ref": "niles_rig_kb.py:x32_vocal_channel_advice_lines",
        }
    ]


def _final_reply_instruction(agent: str | None, message: str | None = None) -> str:
    key = str(agent or _DEFAULT_AGENT).strip().lower()
    if key == "niles":
        if _is_niles_audio_advice_request(agent, message or ""):
            return (
                "For Niles audio how-to, treat this as advice, not live device control. "
                "Give practical X32 vocal-channel guidance: gain, HPF, compression, EQ, "
                "routing, and monitor-send cautions as relevant. Do not refuse, do not "
                "mention Maestro, SEND_HOLD, authority, or finance/receivables, and do "
                "not imply that any console state was changed."
            )
        return (
            "For Niles, if the packet includes a concrete music/gig fact, the first sentence "
            "must name one of those facts, such as Reynolds Tavern, a track title, a transition, "
            "or album posture."
        )
    if key in {"cassandra", "clara"}:
        return (
            "For Cassandra/Clara, if a new money/gig item could be confused with an existing "
            "receivable, ask the confirmation question before giving tracking advice."
        )
    if key == "guardian":
        return "For Guardian, answer advisory questions as safety advice, not as a staged action."
    return ""


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
_QUESTION_DOMAIN_FACT_MARKERS = {
    "audio": (
        (
            "x32",
            "vocal",
            "vocal channel",
            "channel strip",
            "gain",
            "hpf",
            "high pass",
            "compression",
            "compressor",
            "eq",
            "monitor send",
            "foh",
            "iem",
        ),
        (
            "x32",
            "vocal",
            "channel",
            "gain",
            "hpf",
            "high pass",
            "compression",
            "compressor",
            "eq",
            "monitor",
            "foh",
            "iem",
            "rig",
            "audio",
        ),
    ),
    "gig": (
        ("gig", "gigs", "show", "shows", "booking", "performance", "venue", "set", "calendar"),
        ("gig", "gigs", "reynolds", "tavern", "booking", "performance", "venue", "set", "calendar"),
    ),
    "invoice": (
        # Task 137: "did X pay us?" / "has X paid?" are payment-status QUESTIONS -- the bare
        # word "pay" was missing, so they fell through to generic lexical overlap and lost
        # to contacts_registry facts that also mention the client's name.
        ("invoice", "invoices", "receivable", "receivables", "payment", "pay", "paid", "owed", "owes", "coupa"),
        ("invoice", "receivable", "payment", "paid", "owed", "owes", "coupa", "capital hilton"),
    ),
    "approval": (
        ("approval", "approve", "approvals", "guardian", "send_hold", "send hold", "gate", "proof"),
        ("approval", "approve", "guardian", "send_hold", "send hold", "gate", "proof", "protected"),
    ),
}

_NILES_AUDIO_ADVICE_MARKERS = (
    "x32",
    "vocal channel",
    "channel strip",
    "vocal",
    "gain",
    "hpf",
    "high pass",
    "compression",
    "compressor",
    "eq",
    "monitor send",
    "foh",
    "iem",
)

_AUDIO_DOMAIN_FACT_MARKERS = (
    "x32",
    "vocal",
    "channel",
    "gain",
    "hpf",
    "high pass",
    "compression",
    "compressor",
    "eq",
    "monitor",
    "foh",
    "iem",
    "rig",
    "audio",
    "niles_audio_advice",
    "niles_gear_kb",
)


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
    body = body or str(fact.get("value") or "").strip()
    if fact.get("raw_operator_note") and fact.get("verbatim_readback") is False:
        body = f"{body} [raw operator note: distill the meaning; do not quote verbatim]"
    if fact.get("current_truth") is False:
        body = f"{body} [not current truth: {fact.get('drift_resolution') or 'downranked'}]"
    note, _stale = _fact_freshness_note(fact)
    return f"{body} {note}".strip() if note else body


def _today() -> date:
    raw = os.environ.get("OPENCLAW_TODAY", "").strip()
    parsed = _parse_date(raw)
    return parsed or date.today()


def _parse_date(raw: str) -> date | None:
    match = _DATE_RE.search(str(raw or ""))
    if not match:
        return None
    try:
        return date.fromisoformat(match.group(1))
    except ValueError:
        return None


def _fact_freshness_as_of(fact: Mapping[str, Any]) -> str:
    freshness = fact.get("freshness")
    if isinstance(freshness, Mapping):
        for key in ("as_of", "updated_at", "generated_at", "observed_at"):
            value = freshness.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    for key in ("freshness_as_of", "as_of", "updated_at", "generated_at", "observed_at"):
        value = fact.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _age_phrase(days: int) -> str:
    if days < 0:
        return "future-dated"
    if days == 0:
        return "today"
    if days == 1:
        return "1 day old"
    if days < 14:
        return f"{days} days old"
    weeks = max(2, round(days / 7))
    if weeks == 1:
        return "about 1 week old"
    return f"about {weeks} weeks old"


def _fact_freshness_note(fact: Mapping[str, Any]) -> tuple[str, bool]:
    as_of_raw = _fact_freshness_as_of(fact)
    if not as_of_raw:
        return "", False
    as_of_date = _parse_date(as_of_raw)
    if as_of_date is None:
        return f"[freshness: as of {as_of_raw}; date-unparsed]", False
    age_days = (_today() - as_of_date).days
    stale = age_days >= _STALE_FACT_DAYS
    status = "stale-needs-refresh" if stale else "current-enough"
    return (
        f"[freshness: as of {as_of_date.isoformat()}; {_age_phrase(age_days)}; {status}]",
        stale,
    )


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


def _agent_relevant_fact(agent: str | None, fact: Mapping[str, Any]) -> bool:
    key = str(agent or _DEFAULT_AGENT).strip().lower()
    topic = str(fact.get("topic") or "").strip().lower()
    ref = _fact_source_ref(fact).lower()
    blob = f"{fact.get('label') or ''} {fact.get('value') or ''}".lower()
    if key == "niles":
        return (
            topic.startswith("niles_")
            or "niles_" in ref
            or "reynolds_gig" in ref
            or _is_audio_domain_fact(fact)
        )
    if key in {"cassandra", "clara"}:
        if topic.startswith("niles_") or "niles_" in ref or "reynolds_gig" in ref:
            return False
        return topic in {"finance", "invoice_status", "email_calendar", "calendar_day"} or any(
            marker in blob for marker in ("receivable", "coupa", "capital hilton")
        )
    if key == "guardian":
        return any(marker in blob for marker in ("safety", "guardian", "approval", "send_hold", "protected"))
    return False


def _question_domain_fact(message: str, fact: Mapping[str, Any]) -> bool:
    question = str(message or "").lower()
    blob = " ".join(
        str(value or "")
        for value in (
            fact.get("topic"),
            fact.get("label"),
            fact.get("value"),
            _fact_source_ref(fact),
        )
    ).lower()
    for question_markers, fact_markers in _QUESTION_DOMAIN_FACT_MARKERS.values():
        if any(marker in question for marker in question_markers) and any(
            marker in blob for marker in fact_markers
        ):
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
        # Self-awareness: when the operator is talking ABOUT this agent / its improvements,
        # give it a grounded note on what recently got better + what would still help, so it
        # can react genuinely ("yeah that helped — and X would help too"). Rephrased in plain
        # words, never quoted. Pure small talk gets none of this.
        self_note = ""
        try:
            from social_intent import is_self_referential
            if is_self_referential(message):
                from self_knowledge import self_knowledge_hint
                hint = self_knowledge_hint()
                if hint:
                    self_note = (
                        "\n\n(Background you MAY use — rephrase in your own plain casual words, "
                        f"never quote it or use technical terms: {hint} "
                        "If the operator is noticing or praising an improvement, own it "
                        "genuinely. Only bring up the 'next thing that would help' if you "
                        "genuinely sense they'd want it RIGHT NOW — if it doesn't clearly fit "
                        "the moment, DON'T mention it at all, just reply naturally. Never force "
                        "a suggestion, and never invent one beyond what's listed.)"
                    )
        except Exception:
            self_note = ""
        convo = (
            f"You are {persona}. Reply in first person — natural, easy, and short, like "
            "texting a friend back. Keep it low-key: DON'T try hard, skip the forced "
            "metaphors, zingers, and filler. One or two plain sentences is plenty. Don't "
            "mention systems, protocols, SEND_HOLD, status, packets, or facts unless the "
            f"operator brings them up. Just talk like a normal person.{self_note}\n\n"
            f"The operator just said: \"{message}\"\n\n{name}:"
        )
        manifest = {
            "context_facts_kept": 0, "context_facts_dropped": 0, "kept_fact_ids": [],
            "dropped_fact_ids": [], "stale_fact_ids": [], "prompt_context_chars": 0,
            "prompt_chars": len(convo), "layer_a_chars": len(convo), "max_chars": max_chars,
            "layer_b_budget": 0, "over_budget": False, "conversational_lane": True,
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
    niles_audio_advice_request = _is_niles_audio_advice_request(agent, message)
    if niles_audio_advice_request:
        facts = [*_niles_audio_advice_facts(), *facts]

    terms = _message_terms(message)

    # Rank facts deterministically. Lower rank_key sorts first (kept first).
    # Priority tier (smaller = keep first):
    #   0 interpreter-selected facts
    #   1 operator_truth / lexical-overlap facts (non-posture)
    #   2 other non-posture facts
    #   3 generic system-posture facts (dropped first)
    ranked: list[tuple[tuple[int, int, int], str, str, Mapping[str, Any]]] = []
    pre_dropped_ids: list[str] = []
    agent_key = str(agent or _DEFAULT_AGENT).strip().lower()
    message_lower = str(message or "").lower()
    has_finance_anchor = any(
        any(marker in f"{fact.get('topic') or ''} {fact.get('label') or ''} {fact.get('value') or ''}".lower()
            for marker in ("receivable", "coupa", "capital hilton", "invoice", "payment"))
        for fact in facts
    )
    cassandra_money_ambiguity = agent_key in {"cassandra", "clara"} and has_finance_anchor and any(
        marker in message_lower for marker in ("$", "gig", "payment", "invoice", "receivable", "money", "landed")
    )

    for index, fact in enumerate(facts):
        fid = _fact_id(fact, index)
        selected = _selection_match(fact, fact_selection)
        agent_relevant = _agent_relevant_fact(agent, fact)
        topic = str(fact.get("topic") or "").strip().lower()
        ref = _fact_source_ref(fact).lower()
        posture = _is_system_posture(fact)
        overlap = _lexical_overlap(fact, terms)
        operator_truth = _is_operator_truth(fact)
        question_domain = _question_domain_fact(message, fact)
        if agent_key == "niles" and niles_audio_advice_request and not _is_audio_domain_fact(fact):
            pre_dropped_ids.append(fid)
            continue
        if (
            agent_key in {"cassandra", "clara"}
            and not selected
            and (cassandra_money_ambiguity or not question_domain)
            and (topic.startswith("niles_") or "niles_" in ref or "reynolds_gig" in ref)
        ):
            pre_dropped_ids.append(fid)
            continue
        if (
            operator_truth
            and agent_key in {"cassandra", "clara", "niles"}
            and not selected
            and not agent_relevant
            and overlap <= 0
        ):
            pre_dropped_ids.append(fid)
            continue
        operator_truth_high = operator_truth and (
            agent_key not in {"cassandra", "clara", "niles"} or overlap > 0 or agent_relevant
        )
        if selected:
            tier = 0
        elif agent_relevant:
            tier = 0
        elif question_domain:
            tier = 0
        elif posture:
            tier = 3
        elif operator_truth_high or overlap > 0:
            tier = 1
        else:
            tier = 2
        # within a tier: higher overlap first (negate), then stable original order
        rank_key = (tier, -overlap, index)
        line = _fact_text(fact)
        ranked.append((rank_key, fid, line, fact))

    ranked.sort(key=lambda item: item[0])

    kept_ids: list[str] = []
    dropped_ids: list[str] = list(pre_dropped_ids)
    stale_fact_ids: list[str] = []
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
            _note, stale = _fact_freshness_note(_fact)
            if stale:
                stale_fact_ids.append(fid)
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
        f"{_final_reply_instruction(agent, message)}\n\n"
        f"Now write {_agent_display_name(agent)}'s reply — first person, speaking directly to "
        "the operator. Do NOT describe or summarize the text above; just respond.\n"
        f"{_agent_display_name(agent)}:"
    )

    manifest: dict[str, Any] = {
        "context_facts_kept": len(kept_ids),
        "context_facts_dropped": len(dropped_ids),
        "kept_fact_ids": kept_ids,
        "dropped_fact_ids": dropped_ids,
        "stale_fact_ids": stale_fact_ids,
        "prompt_context_chars": prompt_context_chars,
        "prompt_chars": len(prompt),
        "layer_a_chars": layer_a_chars,
        "max_chars": max_chars,
        "layer_b_budget": layer_b_budget,
        "over_budget": budget_narrowing_occurred,
    }
    return prompt, manifest


__all__ = ["build_frontdoor_prompt"]
