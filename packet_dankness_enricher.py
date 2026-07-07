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
SCORE_LOG_SCHEMA_VERSION = "packet_dankness_log_v0"
ESCALATIONS_SCHEMA_VERSION = "packet_dankness_escalations_v0"

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


def _read_records(path: Path, collection_key: str) -> list[Any]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return []
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        records = data.get(collection_key)
        if isinstance(records, list):
            return records
        for fallback in ("records", "escalations"):
            records = data.get(fallback)
            if isinstance(records, list):
                return records
    return []


def _read_model_payload(
    *,
    read_model_id: str,
    schema_version: str,
    collection_key: str,
    records: list[Any],
    generated_at: str,
) -> dict[str, Any]:
    return {
        "schema_version": schema_version,
        "read_model_id": read_model_id,
        "generated_at": generated_at,
        collection_key: records,
        f"{collection_key[:-1] if collection_key.endswith('s') else collection_key}_count": len(records),
        "latest": records[-1] if records else None,
        "machine_proof": {
            "grounded_only_contract": True,
            "fabrication_allowed": False,
            "external_side_effects_allowed": False,
        },
    }


def _write_read_model_records(
    path: Path,
    records: list[Any],
    *,
    read_model_id: str,
    schema_version: str,
    collection_key: str,
    generated_at: str | None = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = _read_model_payload(
        read_model_id=read_model_id,
        schema_version=schema_version,
        collection_key=collection_key,
        records=records,
        generated_at=generated_at or _now(),
    )
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _append_read_model_record(
    path: Path,
    record: Mapping[str, Any],
    *,
    read_model_id: str,
    schema_version: str,
    collection_key: str,
    cap: int = 500,
) -> None:
    data = _read_records(path, collection_key)
    data.append(dict(record))
    _write_read_model_records(
        path,
        data[-cap:],
        read_model_id=read_model_id,
        schema_version=schema_version,
        collection_key=collection_key,
    )


def ensure_packet_dankness_read_models(
    *,
    escalations_path: Path = ESCALATIONS_PATH,
    score_log_path: Path = SCORE_LOG_PATH,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Create or normalize the two packet dankness read-models.

    This is a visibility export, not a scorer: it preserves any existing records,
    writes empty read-model objects when absent, and performs no source refreshes.
    """

    moment = generated_at or _now()
    score_records = _read_records(score_log_path, "records")
    escalation_records = _read_records(escalations_path, "escalations")
    _write_read_model_records(
        score_log_path,
        score_records,
        read_model_id="packet_dankness_log",
        schema_version=SCORE_LOG_SCHEMA_VERSION,
        collection_key="records",
        generated_at=moment,
    )
    _write_read_model_records(
        escalations_path,
        escalation_records,
        read_model_id="packet_dankness_escalations",
        schema_version=ESCALATIONS_SCHEMA_VERSION,
        collection_key="escalations",
        generated_at=moment,
    )
    return {
        "score_log_path": str(score_log_path),
        "escalations_path": str(escalations_path),
        "score_record_count": len(score_records),
        "escalation_count": len(escalation_records),
        "generated_at": moment,
    }


def _escalate(gap: Mapping[str, Any], reason: str, *, escalations_path: Path) -> dict[str, Any]:
    """Record an operator-facing escalation. Never fabricates the missing content."""
    rec = {"at": _now(), "gap": dict(gap), "reason": reason, "needs": "operator_or_new_source"}
    _append_read_model_record(
        escalations_path,
        rec,
        read_model_id="packet_dankness_escalations",
        schema_version=ESCALATIONS_SCHEMA_VERSION,
        collection_key="escalations",
    )
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
        _append_read_model_record(
            score_log_path,
            {
                "at": _now(), "agent_id": agent_id, "question": question,
                "overall": score.overall, "grounded": score.grounded, "current": score.current,
                "useful": score.useful, "lane_rich": score.lane_rich, "fact_count": score.fact_count,
                "gaps": len(score.gaps),
                "refreshed": sum(1 for o in outcomes if o["outcome"] == "refreshed"),
                "escalated": sum(1 for o in outcomes if o["outcome"] == "escalated"),
            },
            read_model_id="packet_dankness_log",
            schema_version=SCORE_LOG_SCHEMA_VERSION,
            collection_key="records",
        )
    return {
        "score": score,
        "outcomes": outcomes,
        "refreshed": [o for o in outcomes if o["outcome"] == "refreshed"],
        "escalated": [o for o in outcomes if o["outcome"] == "escalated"],
    }
