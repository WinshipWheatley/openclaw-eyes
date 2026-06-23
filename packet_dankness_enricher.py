#!/usr/bin/env python3
"""Packet dankness enricher — the GROUNDED other half of the self-improving loop.

Consumes the gaps the critic finds and actually makes packets danker — but under one
non-negotiable contract: it may only ADD GROUNDED facts (re-run a REAL generator to refresh
a stale source) or ESCALATE to the operator (when a gap needs a new source/pipeline/data).
It NEVER fabricates content to raise a score. That contract is what makes the loop safe to
run on by default: the system improves itself without ever lying to do it.

- stale_source gap  -> refresh: re-run the read-model's real generator (deterministic, no
  external effects). If no known/safe generator -> escalate.
- missing_fact / empty / unknown -> escalate: record an operator-facing note describing the
  needed source. Never invents the missing fact.
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

try:  # pragma: no cover
    from packet_dankness_critic import score_packet_dankness
except ImportError:  # pragma: no cover
    from .packet_dankness_critic import score_packet_dankness  # type: ignore

ROOT = Path(__file__).resolve().parent
DEFAULT_LEDGER = ROOT / ".openclaw" / "business_ops" / "ledger.sqlite"
ESCALATIONS_PATH = ROOT / "generated" / "read_models" / "packet_dankness_escalations.json"
SCORE_LOG_PATH = ROOT / "generated" / "read_models" / "packet_dankness_log.json"

# read-model filename -> the REAL generator that produces it (verified to exist).
# Only safe, self-contained generators belong here; anything else escalates.
READ_MODEL_GENERATORS: dict[str, dict[str, Any]] = {
    "orchestration_progress.json": {"script": "scripts/export_orchestration_progress_read_model.py"},
    "chief_agent_fleet_health.json": {"script": "scripts/export_chief_agent_fleet_health.py"},
    "guardian_approval_posture.json": {
        "script": "scripts/export_guardian_approval_posture_read_model.py",
        "env": {"OPENCLAW_LEDGER_PATH": str(DEFAULT_LEDGER)},
    },
    "niles_track_registry.json": {"script": "scripts/export_niles_track_registry_read_model.py"},
    "work_board.json": {"script": "scripts/export_work_board_read_model.py"},
    "chief_status_rail.json": {"script": "scripts/export_chief_status_rail.py"},
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _append_json_list(path: Path, record: Mapping[str, Any], *, cap: int = 500) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data: list[Any] = []
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(data, list):
                data = []
        except (ValueError, OSError):
            data = []
    data.append(dict(record))
    path.write_text(json.dumps(data[-cap:], indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _escalate(gap: Mapping[str, Any], reason: str, *, escalations_path: Path) -> dict[str, Any]:
    """Record an operator-facing escalation. Never fabricates the missing content."""
    rec = {"at": _now(), "gap": dict(gap), "reason": reason, "needs": "operator_or_new_source"}
    _append_json_list(escalations_path, rec)
    return {"outcome": "escalated", "reason": reason, "gap": dict(gap)}


def enrich_one(
    task_payload: Mapping[str, Any],
    *,
    runner: Callable[..., subprocess.CompletedProcess] = subprocess.run,
    python: str = sys.executable,
    repo_root: Path = ROOT,
    escalations_path: Path = ESCALATIONS_PATH,
) -> dict[str, Any]:
    """Process one packet_enrich gap: refresh a real source, or escalate. Grounded-only."""
    if task_payload.get("grounded_only") is not True:
        # Defense in depth: refuse anything not carrying the grounded-only contract.
        return {"outcome": "refused", "reason": "task missing grounded_only contract (anti-confabulation)"}

    gap = task_payload.get("gap") or {}
    kind = str(gap.get("kind") or "")

    if kind == "stale_source":
        ref = str(gap.get("source_ref") or "")
        name = ref.rsplit("/", 1)[-1]
        gen = READ_MODEL_GENERATORS.get(name)
        if not gen:
            return _escalate(gap, f"no known safe generator for {name}", escalations_path=escalations_path)
        script = repo_root / gen["script"]
        if not script.exists():
            return _escalate(gap, f"generator {gen['script']} not found", escalations_path=escalations_path)
        env = None
        if gen.get("env"):
            import os
            env = {**os.environ, **gen["env"]}
        try:
            res = runner(
                [python, str(script)], cwd=str(repo_root), capture_output=True, text=True,
                timeout=180, check=False, env=env,
            )
        except Exception as exc:  # noqa: BLE001 — a failed refresh escalates, never crashes the loop
            return _escalate(gap, f"generator raised: {exc}", escalations_path=escalations_path)
        if res.returncode == 0:
            return {"outcome": "refreshed", "source_ref": ref, "generator": gen["script"]}
        return _escalate(gap, f"generator exit {res.returncode}", escalations_path=escalations_path)

    # missing_fact / empty_packet / unknown — needs a new source/pipeline or operator data.
    return _escalate(gap, f"gap '{kind or 'unknown'}' needs a new source/pipeline or operator input",
                     escalations_path=escalations_path)


def run_dankness_cycle(
    packet: Mapping[str, Any],
    question: str,
    agent_id: str,
    *,
    useful_scorer: Callable | None = None,
    runner: Callable[..., subprocess.CompletedProcess] = subprocess.run,
    escalations_path: Path = ESCALATIONS_PATH,
    score_log_path: Path | None = SCORE_LOG_PATH,
) -> dict[str, Any]:
    """The whole loop in one inline call: score -> enrich each gap (refresh/escalate) -> log.

    Inline (no orchestrator needed) so it can run right after any agent answer. Records the
    dankness score over time so improvement is observable.
    """
    score = score_packet_dankness(packet, question, useful_scorer=useful_scorer)
    outcomes = []
    for gap in score.gaps:
        outcomes.append(enrich_one(
            {"gap": dict(gap), "grounded_only": True, "agent_id": agent_id, "question": question},
            runner=runner, escalations_path=escalations_path,
        ))
    if score_log_path is not None:
        _append_json_list(score_log_path, {
            "at": _now(), "agent_id": agent_id, "question": question,
            "overall": score.overall, "grounded": score.grounded, "current": score.current,
            "useful": score.useful, "lane_rich": score.lane_rich, "fact_count": score.fact_count,
            "gaps": len(score.gaps),
            "refreshed": sum(1 for o in outcomes if o["outcome"] == "refreshed"),
            "escalated": sum(1 for o in outcomes if o["outcome"] == "escalated"),
        })
    return {
        "score": score,
        "outcomes": outcomes,
        "refreshed": [o for o in outcomes if o["outcome"] == "refreshed"],
        "escalated": [o for o in outcomes if o["outcome"] == "escalated"],
    }
