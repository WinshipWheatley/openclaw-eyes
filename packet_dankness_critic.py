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
from typing import Any, Mapping, Sequence

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


def score_packet_dankness(packet: Mapping[str, Any], question: str = "") -> DanknessScore:
    """Score a built packet's dankness on real-source coverage; identify grounded gaps.

    Never inspects or rewards content plausibility — only whether real, current, relevant,
    sourced facts are present. Gaps are task specs for grounded enrichment, not content.
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
    # No question terms => usefulness is not assessable from the question; treat as neutral.
    useful = 1.0 if (not q_terms or useful_hits) else 0.0

    gaps: list[dict[str, Any]] = []
    if q_terms and not useful_hits:
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
    """Whether the critic may queue packet_enrich tasks to the LIVE ledger. DEFAULT OFF.

    Mirrors the control-plane detector wire: scoring is always safe and free; queueing into
    the live self-improvement loop is dormant until the operator turns it on for a
    supervised run (OPENCLAW_PACKET_DANKIFY_EMIT=1).
    """
    return os.environ.get("OPENCLAW_PACKET_DANKIFY_EMIT", "").strip().lower() in {
        "1", "true", "yes", "on",
    }


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
    admitted: list[str] = []
    for gap in score.gaps:
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
