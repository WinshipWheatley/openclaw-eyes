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
import hashlib
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
_PACKET_ENRICH_TESTS = (
    "python -m pytest tests/test_packet_dankness_critic.py "
    "tests/test_packet_dankness_enricher.py tests/test_packet_dankness_drain.py "
    "tests/test_polish_loop_task_package_materialization.py -q"
)
_PACKET_ENRICH_ALLOWED_FILES = (
    "packet_dankness_critic.py",
    "packet_dankness_enricher.py",
    "packet_dankness_drain.py",
    "read_model_auto_refresh.py",
    "generated/read_models/packet_dankness_log.json",
    "generated/read_models/packet_dankness_escalations.json",
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
    right_sized: float
    source_fact_count: int
    size_state: str


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


def _fact_id(fact: Mapping[str, Any]) -> str:
    return str(fact.get("fact_id") or "").strip()


def _gap_key(gap: Mapping[str, Any]) -> str:
    return f"{gap.get('kind')}:{gap.get('source_ref') or gap.get('about')}"


def _packet_enrich_task_package_fields(
    gap: Mapping[str, Any],
    score: DanknessScore,
    *,
    agent_id: str,
    question: str,
) -> dict[str, Any]:
    """Return the Phase-C task-package fields for a grounded packet_enrich task.

    The package tells the worker how to resolve the gap. It deliberately does not
    include any candidate fact content: refresh a real source, or write an escalation.
    """

    target = str(gap.get("source_ref") or gap.get("about") or "packet gap").strip()
    kind = str(gap.get("kind") or "unknown_gap").strip()
    return {
        "goal": (
            f"Resolve packet enrichment gap {kind} for agent {agent_id}: {target}. "
            "Use grounded sources only; otherwise record an operator-facing escalation."
        ),
        "scope": [
            "Process one packet_enrich control-plane task.",
            "Preserve the original gap payload and grounded_only contract.",
            "Use existing packet dankness enricher and drain mechanisms.",
        ],
        "success_criteria": [
            "Known stale read-model sources are refreshed through their registered local generator.",
            "Unknown, missing, or insufficient sources append a packet dankness escalation record.",
            "No fact is created unless it comes from a real source with provenance.",
            f"Dankness score at queue time is recorded as {score.overall}.",
        ],
        "allowed_files": list(_PACKET_ENRICH_ALLOWED_FILES),
        "forbidden_files": [
            ".chief.env",
            ".google-secrets/",
            "private vaults",
            "production account material",
        ],
        "allowed_actions": [
            "Run registered local read-model exporters.",
            "Append packet dankness observation or escalation read-model records.",
            "Update only this packet_enrich control-plane task outcome.",
        ],
        "forbidden_actions": [
            "external communication",
            "financial account mutation",
            "credential access",
            "production service restart",
            "ungrounded fact creation",
        ],
        "tests_to_run": [_PACKET_ENRICH_TESTS],
        "stop_conditions": [
            "The gap lacks grounded source data and no safe local source exists.",
            "A refresh would need private credentials or external side effects.",
            "The result would require inferred content rather than provenance.",
        ],
        "output_contract": [
            "Return a refreshed source receipt or a packet_dankness_escalations read-model record.",
            "Keep grounded_only true in all task evidence.",
        ],
        "help_or_escalation_route": [
            "Append to generated/read_models/packet_dankness_escalations.json for operator review."
        ],
        "rollback_expectation": [
            "Remove or terminalize only the queued packet_enrich task if this task is invalid."
        ],
        "production_prohibitions": [
            "No external network side effects.",
            "No financial account mutation.",
            "No credential or private-vault access.",
        ],
    }


def score_packet_dankness(
    packet: Mapping[str, Any],
    question: str = "",
    *,
    useful_scorer: Callable[[Sequence[Mapping[str, Any]], str], float] | None = None,
    sizing_manifest: Mapping[str, Any] | None = None,
) -> DanknessScore:
    """Score a built packet's dankness on real-source coverage; identify grounded gaps.

    Never inspects or rewards content plausibility — only whether real, current, relevant,
    sourced facts are present. Gaps are task specs for grounded enrichment, not content.

    ``useful_scorer`` (optional) overrides the cheap deterministic term-match for the USEFUL
    dimension with a semantic judge (e.g. an LLM via ``lm_useful_scorer``). It only RATES
    relevance — it never adds content, so it carries no confabulation risk.
    """
    source_facts = [f for f in packet.get("facts", ()) if isinstance(f, Mapping)]
    manifest = dict(sizing_manifest or {})
    if manifest.get("task_kind") == "canned_revoice":
        return DanknessScore(
            1.0, 1.0, 1.0, 1.0, 1.0, 0, (), 1.0, len(source_facts),
            "canned_revoice_no_business_facts_required",
        )
    if manifest.get("conversational_lane") is True and not source_facts:
        return DanknessScore(
            1.0, 1.0, 1.0, 1.0, 1.0, 0, (), 1.0, 0,
            "social_no_facts_required",
        )
    kept_ids = {
        str(item).strip() for item in manifest.get("kept_fact_ids", ()) if str(item).strip()
    }
    if sizing_manifest is not None:
        facts = [fact for fact in source_facts if _fact_id(fact) in kept_ids]
    else:
        facts = source_facts
    n = len(facts)
    source_n = len(source_facts)
    if n == 0:
        gaps = ({"kind": "empty_packet", "about": " ".join(_terms(question)[:4]),
                 "detail": "packet had zero facts"},)
        return DanknessScore(0.0, 0.0, 0.0, 0.0, 0.0, 0, gaps, 0.0, source_n, "starved")

    grounded = sum(1 for f in facts if _grounded(f)) / n
    fresh_facts = [f for f in facts if _is_fresh(_as_of(f))]
    current = len(fresh_facts) / n
    topics = {str(f.get("topic") or "") for f in facts if f.get("topic")}
    lane_rich = min(1.0, len(topics) / RICH_TARGET)

    q_terms = _terms(question)
    useful_hits = [
        f for f in facts if q_terms and any(t in _fact_text(f) for t in q_terms)
    ]
    if re.search(
        r"\b(what do you think|next correct step|what should (?:we|i) do next|what would you recommend)\b",
        question,
        flags=re.IGNORECASE,
    ):
        useful_hits.extend(
            fact
            for fact in facts
            if str(fact.get("topic") or "") in {"pending_operator_action", "current_guardian_action"}
        )
    if not q_terms:
        useful = 1.0  # no question => relevance not assessable => neutral
    elif useful_scorer is not None:
        useful = max(0.0, min(1.0, float(useful_scorer(facts, question))))  # semantic judge
    else:
        useful = 1.0 if useful_hits else 0.0  # deterministic term-match

    gaps: list[dict[str, Any]] = []
    dropped_count = int(
        manifest.get("context_facts_dropped")
        or len(manifest.get("dropped_fact_ids") or ())
        or 0
    )
    if manifest.get("over_budget") is True:
        sizing_total = max(1, n + dropped_count)
        right_sized = n / sizing_total
        size_state = "bloated_trimmed"
        gaps.append({
            "kind": "bloated_packet",
            "about": "prompt_context_budget",
            "detail": f"deterministic budgeter kept {n} facts and trimmed {dropped_count}",
        })
    else:
        right_sized = 1.0
        size_state = "right_sized"
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

    overall = round((grounded + current + useful + lane_rich + right_sized) / 5, 4)
    return DanknessScore(
        grounded=round(grounded, 4),
        current=round(current, 4),
        useful=round(useful, 4),
        lane_rich=round(lane_rich, 4),
        overall=overall,
        fact_count=n,
        gaps=tuple(gaps),
        right_sized=round(right_sized, 4),
        source_fact_count=source_n,
        size_state=size_state,
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
    # Dedup + CONVERGENCE guard. Two skips:
    #  (1) a gap that already has a READY packet_enrich task (same-cycle queue spam), and
    #  (2) a gap that has already been ESCALATED >= MAX_ESCALATIONS times. An escalated gap needs
    #      the operator or a NEW source/pipeline — re-filing it on every response can never fix it,
    #      it just churns (this is exactly what spun the loop 546x on one agent). Escalated gaps
    #      stay recorded for the operator in the escalations read-model; a gap re-enters only if it
    #      actually changes (different kind/source_ref -> different key).
    MAX_ESCALATIONS = 2
    existing: set[str] = set()
    _escalated_counts: dict[str, int] = {}
    try:
        import json as _json
        for _t in ledger.list_tasks():
            if _t.get("type") != "packet_enrich":
                continue
            _pg = _t.get("payload") or {}
            if isinstance(_pg, str):
                _pg = _json.loads(_pg)
            _g = _pg.get("gap", {}) if isinstance(_pg, Mapping) else {}
            _k = _gap_key(_g) if isinstance(_g, Mapping) else "unknown:unknown"
            if _t.get("status") == "READY":
                existing.add(_k)
            elif "escalat" in str(_t.get("terminal_reason") or ""):
                _escalated_counts[_k] = _escalated_counts.get(_k, 0) + 1
        for _k, _n in _escalated_counts.items():
            if _n >= MAX_ESCALATIONS:
                existing.add(_k)
    except Exception:
        existing = set()
    admitted: list[str] = []
    for gap in score.gaps:
        if gap.get("kind") == "bloated_packet":
            # The deterministic budgeter already fixed this run. Record it for taste
            # scoring; do not queue a source-enrichment task that cannot reduce bloat.
            continue
        _key = _gap_key(gap)
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
        payload.update(
            _packet_enrich_task_package_fields(
                gap,
                score,
                agent_id=agent_id,
                question=question,
            )
        )
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
    """An lm_useful_scorer wired to the system's adaptive local LLM layer.

    This is the "LM useful-scorer live" wiring: relevance judged by the real model instead of
    the deterministic term-match. Intended for the periodic enrich drain (not the per-response
    path, for cost). The model only RATES relevance; it never adds content (no confab risk).
    """

    def _generate(prompt: str) -> str:
        from adaptive_model_call import adaptive_ollama_text

        return str(adaptive_ollama_text(prompt) or "")

    return lm_useful_scorer(_generate)


def observe_packet_dankness(
    packet: Mapping[str, Any],
    question: str,
    agent_id: str,
    *,
    ledger: ControlPlaneLedger | None = None,
    sizing_manifest: Mapping[str, Any] | None = None,
    consumer_id: str = "frontdoor",
    score_log_path: Any = None,
) -> DanknessScore | None:
    """Per-response hook for the live self-improving loop.

    Scores the packet that was just used (cheap, deterministic, NO LM call) and queues grounded
    gaps to the control-plane ledger. NEVER raises — a scoring/queueing failure must never
    affect the agent's answer. Returns the score (or None on failure). The actual enrichment
    (refresh/escalate, optional LM re-score) runs in a separate drain, not here, so the
    response path stays cheap.
    """
    try:
        score = score_packet_dankness(
            packet,
            question,
            sizing_manifest=sizing_manifest,
        )
        if ledger is None:
            from polish_loop.control_plane import DEFAULT_LEDGER_PATH

            ledger = ControlPlaneLedger(DEFAULT_LEDGER_PATH)
        emit_packet_enrich_tasks(ledger, score, agent_id=agent_id, question=question)
        from packet_dankness_enricher import (
            SCORE_LOG_PATH,
            SCORE_LOG_SCHEMA_VERSION,
            _append_read_model_record,
            _read_records,
        )

        log_path = SCORE_LOG_PATH if score_log_path is None else score_log_path
        previous = next(
            (
                row for row in reversed(_read_records(log_path, "records"))
                if row.get("agent_id") == agent_id and row.get("consumer_id") == consumer_id
            ),
            {},
        )
        previous_overall = previous.get("overall")
        _append_read_model_record(
            log_path,
            {
                "at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
                "agent_id": agent_id,
                "consumer_id": consumer_id,
                "question_sha256": "sha256:" + hashlib.sha256(
                    str(question or "").encode("utf-8")
                ).hexdigest(),
                "packet_id": str(packet.get("packet_id") or ""),
                "overall": score.overall,
                "grounded": score.grounded,
                "current": score.current,
                "useful": score.useful,
                "lane_rich": score.lane_rich,
                "right_sized": score.right_sized,
                "size_state": score.size_state,
                "fact_count": score.fact_count,
                "source_fact_count": score.source_fact_count,
                "gap_kinds": [str(gap.get("kind") or "") for gap in score.gaps],
                "previous_overall": previous_overall,
                "overall_delta": (
                    round(score.overall - float(previous_overall), 4)
                    if isinstance(previous_overall, (int, float))
                    else None
                ),
                "raw_question_included": False,
            },
            read_model_id="packet_dankness_log",
            schema_version=SCORE_LOG_SCHEMA_VERSION,
            collection_key="records",
        )
        return score
    except Exception:  # noqa: BLE001 — observation must never break a live answer
        return None
