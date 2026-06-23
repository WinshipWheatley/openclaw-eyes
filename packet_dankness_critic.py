#!/usr/bin/env python3
"""Packet dankness critic — the scoring half of the self-improving packet loop.

Operator's design: after a run, score the dankness of the packet that was used; queue
the gaps; a later worker makes the packet danker for next time. This module is the
CRITIC + QUEUE half (deterministic, cheap, safe). The grounded ENRICHER (worker) is a
separate, supervised graduation.

THE LOAD-BEARING RULE (do not remove): the loop may only ever ADD GROUNDED facts (wire a
real source) or FLAG a data gap. It must NEVER fabricate content to raise a score. So the
critic scores REAL-SOURCE COVERAGE (grounded/current/useful/lane-rich), the gaps it emits
are TASK SPECS ("packet lacked a fact about X" / "source Y is stale"), and the downstream
enricher is contractually grounded-only. A scorer that could reward invented text would let
the system hallucinate its way to a perfect score — fatal for a truth engine (Goodhart).
"""
from __future__ import annotations

import dataclasses
import os
import re
from datetime import datetime, timezone
from typing import Any, Callable, Mapping, Sequence

try:  # pragma: no cover - package import
    from polish_loop.control_plane import ControlPlaneLedger
except ImportError:  # pragma: no cover - script import
    from control_plane import ControlPlaneLedger  # type: ignore

FRESH_DAYS = 21  # a fact older than this is "stale" for currency scoring
RICH_TARGET = 4  # distinct topics for a "lane-rich" packet
_STOP = frozenset(
    "the a an of to is at in on for and or what whats where when how do does my me i you "
    "with about are was were be been being this that it its".split()
)


@dataclasses.dataclass(frozen=True)
class DanknessScore:
    grounded: float
    current: float
    useful: float
    lane_rich: float
    overall: float
    fact_count: int
    gaps: tuple[dict[str, Any], ...]


def _terms(question: str) -> list[str]:
    toks = re.findall(r"[a-z0-9']+", str(question or "").lower())
    return [t for t in toks if t not in _STOP and len(t) > 2]


def _as_of(fact: Mapping[str, Any]) -> str:
    fr = fact.get("freshness")
    return str(fr.get("as_of") or "") if isinstance(fr, Mapping) else ""


def _is_fresh(as_of: str) -> bool:
    if not as_of:
        return False
    try:
        ts = datetime.fromisoformat(as_of.replace("Z", "+00:00"))
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
    except ValueError:
        return False
    return (datetime.now(timezone.utc) - ts).days <= FRESH_DAYS


def _grounded(fact: Mapping[str, Any]) -> bool:
    return bool(fact.get("source_ref")) and bool(fact.get("provenance"))


def _fact_text(fact: Mapping[str, Any]) -> str:
    return " ".join(
        str(fact.get(k) or "") for k in ("topic", "label", "value")
    ).lower()


def score_packet_dankness(
    packet: Mapping[str, Any],
    question: str = "",
    *,
    useful_scorer: Callable[[Sequence[Mapping[str, Any]], str], float] | None = None,
) -> DanknessScore:
    """Score a built packet's dankness on real-source coverage; identify grounded gaps.

    Never inspects or rewards content plausibility — only whether real, current, relevant,
    sourced facts are present. Gaps are task specs for grounded enrichment, not content.

    ``useful_scorer`` (optional) overrides the cheap deterministic term-match for the USEFUL
    dimension with a semantic judge (e.g. an LLM via ``lm_useful_scorer``). It only RATES
    relevance — it never adds content, so it carries no confabulation risk.
    """
    facts = [f for f in packet.get("facts", ()) if isinstance(f, Mapping)]
    n = len(facts)
    if n == 0:
        gaps = ({"kind": "empty_packet", "about": " ".join(_terms(question)[:4]),
                 "detail": "packet had zero facts"},)
        return DanknessScore(0.0, 0.0, 0.0, 0.0, 0.0, 0, gaps)

    grounded = sum(1 for f in facts if _grounded(f)) / n
    fresh_facts = [f for f in facts if _is_fresh(_as_of(f))]
    current = len(fresh_facts) / n
    topics = {str(f.get("topic") or "") for f in facts if f.get("topic")}
    lane_rich = min(1.0, len(topics) / RICH_TARGET)

    q_terms = _terms(question)
    useful_hits = [
        f for f in facts if q_terms and any(t in _fact_text(f) for t in q_terms)
    ]
    if not q_terms:
        useful = 1.0  # no question => relevance not assessable => neutral
    elif useful_scorer is not None:
        useful = max(0.0, min(1.0, float(useful_scorer(facts, question))))  # semantic judge
    else:
        useful = 1.0 if useful_hits else 0.0  # deterministic term-match

    gaps: list[dict[str, Any]] = []
    if q_terms and useful < 0.5:
        gaps.append({
            "kind": "missing_fact",
            "about": " ".join(q_terms[:4]),
            "detail": "packet carried no fact matching the operator's question",
        })
    # Stale sources -> refresh tasks (deduped by source_ref)
    seen: set[str] = set()
    for f in facts:
        if not _is_fresh(_as_of(f)):
            ref = str(f.get("source_ref") or "")
            if ref and ref not in seen:
                seen.add(ref)
                gaps.append({
                    "kind": "stale_source",
                    "source_ref": ref,
                    "detail": f"source is older than {FRESH_DAYS}d; refresh its generator",
                })

    overall = round((grounded + current + useful + lane_rich) / 4, 4)
    return DanknessScore(
        grounded=round(grounded, 4),
        current=round(current, 4),
        useful=round(useful, 4),
        lane_rich=round(lane_rich, 4),
        overall=overall,
        fact_count=n,
        gaps=tuple(gaps),
    )


def dankify_emit_enabled() -> bool:
    """Whether the critic may queue packet_enrich tasks to the LIVE ledger. DEFAULT ON.

    The loop's safety is NOT this switch — it is the grounded-only enricher contract (refresh
    a real source or escalate to the operator; never fabricate). Queueing a gap spec is itself
    harmless (it just records what's missing). Set OPENCLAW_PACKET_DANKIFY_EMIT to
    0/false/no/off to disable.
    """
    return os.environ.get("OPENCLAW_PACKET_DANKIFY_EMIT", "on").strip().lower() not in {
        "0", "false", "no", "off",
    }


def lm_useful_scorer(generate: Callable[[str], str]) -> Callable[[Sequence[Mapping[str, Any]], str], float]:
    """Build a USEFUL-dimension scorer backed by an LLM relevance judgment.

    ``generate(prompt) -> str`` is the injected model call (e.g. the system's protected_generate).
    The LM ONLY RATES whether the packet's facts can answer the question — it never adds or
    invents content, so scoring carries no confabulation risk. Fails safe: any error scores 0.0
    (which flags a gap) rather than crashing or inflating the score.
    """

    def _score(facts: Sequence[Mapping[str, Any]], question: str) -> float:
        summary = "; ".join(_fact_text(f)[:140] for f in list(facts)[:12])
        prompt = (
            "You rate packet relevance for a truth system. On a scale 0.0 to 1.0, how well do "
            "these facts let an agent answer the question? Reply with ONLY the number.\n"
            f"Question: {question}\nFacts: {summary}\n"
        )
        try:
            raw = str(generate(prompt)).strip()
            m = re.search(r"[01](?:\.\d+)?", raw)
            return max(0.0, min(1.0, float(m.group(0)))) if m else 0.0
        except Exception:  # noqa: BLE001 — never let a scorer crash a run; absence -> gap
            return 0.0

    return _score


def emit_packet_enrich_tasks(
    ledger: ControlPlaneLedger,
    score: DanknessScore,
    *,
    agent_id: str,
    question: str,
    enabled: bool | None = None,
) -> list[str]:
    """Queue one grounded packet_enrich task per gap (default OFF). Returns admitted ids.

    Each task is a GROUNDED SPEC (what real fact/source is missing) — never content to add.
    The downstream enricher must wire a real source or escalate; it must never fabricate.
    """
    if enabled is None:
        enabled = dankify_emit_enabled()
    if not enabled or not score.gaps:
        return []
    # Dedup: never re-queue a gap that already has a READY packet_enrich task. Without this
    # an always-on loop would re-file the same gap on every response (queue/escalation spam).
    existing: set[str] = set()
    try:
        import json as _json
        for _t in ledger.list_tasks():
            if _t.get("type") == "packet_enrich" and _t.get("status") == "READY":
                _pg = _t.get("payload") or {}
                if isinstance(_pg, str):
                    _pg = _json.loads(_pg)
                _g = _pg.get("gap", {}) if isinstance(_pg, Mapping) else {}
                existing.add(f"{_g.get('kind')}:{_g.get('source_ref') or _g.get('about')}")
    except Exception:
        existing = set()
    admitted: list[str] = []
    for gap in score.gaps:
        _key = f"{gap.get('kind')}:{gap.get('source_ref') or gap.get('about')}"
        if _key in existing:
            continue
        existing.add(_key)
        payload = {
            "kind": "packet_enrich",
            "agent_id": agent_id,
            "question": question,
            "gap": dict(gap),
            "dankness_overall": score.overall,
            "grounded_only": True,  # enricher contract: wire a real source or flag; never fabricate
            "rollback_no_send": True,
        }
        task_id = ledger.admit_task(
            source="detector",  # a packet-gap detector (READY source); task_type distinguishes it
            task_type="packet_enrich",
            requested_status="READY",
            payload=payload,
            max_attempts=2,
        )
        if task_id:
            admitted.append(task_id)
    return admitted


def default_lm_useful_scorer() -> Callable[[Sequence[Mapping[str, Any]], str], float]:
    """An lm_useful_scorer wired to the system's local LLM (chief_llm.ollama_call).

    This is the "LM useful-scorer live" wiring: relevance judged by the real model instead of
    the deterministic term-match. Intended for the periodic enrich drain (not the per-response
    path, for cost). The model only RATES relevance; it never adds content (no confab risk).
    """

    def _generate(prompt: str) -> str:
        from chief_llm import ollama_call  # local import: keeps the critic importable without the model

        return str(ollama_call(prompt) or "")

    return lm_useful_scorer(_generate)


def observe_packet_dankness(
    packet: Mapping[str, Any],
    question: str,
    agent_id: str,
    *,
    ledger: ControlPlaneLedger | None = None,
) -> DanknessScore | None:
    """Per-response hook for the live self-improving loop.

    Scores the packet that was just used (cheap, deterministic, NO LM call) and queues grounded
    gaps to the control-plane ledger. NEVER raises — a scoring/queueing failure must never
    affect the agent's answer. Returns the score (or None on failure). The actual enrichment
    (refresh/escalate, optional LM re-score) runs in a separate drain, not here, so the
    response path stays cheap.
    """
    try:
        score = score_packet_dankness(packet, question)
        if ledger is None:
            from polish_loop.control_plane import DEFAULT_LEDGER_PATH

            ledger = ControlPlaneLedger(DEFAULT_LEDGER_PATH)
        emit_packet_enrich_tasks(ledger, score, agent_id=agent_id, question=question)
        return score
    except Exception:  # noqa: BLE001 — observation must never break a live answer
        return None
