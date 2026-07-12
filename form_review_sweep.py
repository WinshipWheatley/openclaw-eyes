#!/usr/bin/env python3
"""Mode-shift form-review sweep v1.

Prepare-only recommendation engine. It observes structures and emits
recommendations; it never executes shifts or mutates live structures.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from activation_gate_register import build_activation_gate_register
from mode_shift_ledger import query_mode_shifts, seed_mode_shift_ledger, stable_json
from operator_surface_guard import operator_surface_text
from read_model_auto_refresh import READ_MODEL_REFRESH_REGISTRY


SCHEMA_VERSION = "form_review_recommendations_v1"
READ_MODEL_ID = "form_review_recommendations"
READ_MODEL_NAME = f"{READ_MODEL_ID}.json"
DEFAULT_READ_MODEL_ROOT = Path("generated/read_models")
LADDER_STAGE = "RECOMMENDATION"


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _signal_int(signals: Mapping[str, Any], key: str) -> int:
    try:
        return int(signals.get(key) or 0)
    except (TypeError, ValueError):
        return 0


def _structure_display_name(structure: Mapping[str, Any]) -> str:
    return str(
        structure.get("display_name")
        or structure.get("capability_id")
        or structure.get("structure_ref")
        or "Unknown structure"
    )


def _evidence_refs(structure: Mapping[str, Any]) -> list[str]:
    refs = structure.get("evidence_refs")
    if isinstance(refs, Sequence) and not isinstance(refs, (str, bytes)):
        return [str(ref) for ref in refs if str(ref).strip()]
    return []


def _recommendation_for_structure(structure: Mapping[str, Any]) -> dict[str, Any] | None:
    signals = structure.get("signals") if isinstance(structure.get("signals"), Mapping) else {}
    display = _structure_display_name(structure)
    structure_ref = str(structure.get("structure_ref") or display).strip()
    evidence = _evidence_refs(structure)
    trap_signals: list[str] = []
    leverage_signals: list[str] = []

    ritual_repeats = _signal_int(signals, "ritual_repeats_without_new_info")
    new_info = _signal_int(signals, "new_information_count")
    if ritual_repeats >= 3 and new_info == 0:
        trap_signals.append("ritual repeats without new information")

    cost_score = _signal_int(signals, "cost_score")
    yield_score = _signal_int(signals, "yield_score")
    if cost_score > yield_score and cost_score >= 3:
        trap_signals.append("cost exceeds yield")

    fallback_count = _signal_int(signals, "fallback_count")
    if fallback_count >= 3:
        trap_signals.append("fallbacks frequent")

    repeated = _signal_int(signals, "fluid_pattern_repetition_count")
    positives = _signal_int(signals, "positive_outcome_count")
    if repeated >= 3 and positives >= 3:
        leverage_signals.append("fluid pattern repeated 3+ times with good outcomes")

    if leverage_signals:
        shift = "FREEZE"
        next_step = "Draft a validator, battery item, doctrine fact, or exemplar; do not execute it."
        reasons = leverage_signals
    elif trap_signals:
        shift = "LOOSEN"
        next_step = "Propose pruning or loosening this structure; do not execute it."
        reasons = trap_signals
    else:
        return None

    evidence_text = ", ".join(evidence[:3]) if evidence else "local form-review signals"
    operator_line = operator_surface_text(
        f"{display}: {shift.lower()} recommended — {', '.join(reasons)}. Evidence: {evidence_text}."
    )
    return {
        "structure_ref": structure_ref,
        "display_name": display,
        "ladder_stage": LADDER_STAGE,
        "recommended_shift": shift,
        "recommended_next_step": next_step,
        "trap_signals": trap_signals,
        "leverage_signals": leverage_signals,
        "evidence_refs": evidence,
        "operator_line": operator_line,
        "execution_allowed": False,
        "shift_executed": False,
    }


def _activation_register_structures(repo_root: Path) -> list[dict[str, Any]]:
    try:
        register = build_activation_gate_register(repo_root=repo_root)
    except Exception:
        return []
    structures: list[dict[str, Any]] = []
    for capability in register.get("capabilities", [])[:200]:
        if not isinstance(capability, Mapping):
            continue
        capability_id = str(capability.get("capability_id") or "")
        if not capability_id:
            continue
        structures.append(
            {
                "structure_ref": f"activation_gate_register:{capability_id}",
                "display_name": str(capability.get("display_name") or capability_id.replace("_", " ").title()),
                "signals": {
                    "fallback_count": 1 if capability.get("gate_stage") == "blocked" else 0,
                    "ritual_repeats_without_new_info": 0,
                    "new_information_count": 1,
                },
                "evidence_refs": [f"activation_gate_register:{capability_id}"],
            }
        )
    return structures


def _registry_structures() -> list[dict[str, Any]]:
    structures: list[dict[str, Any]] = []
    for name, entry in sorted(READ_MODEL_REFRESH_REGISTRY.items()):
        reason = str(entry.get("reason") or "")
        structures.append(
            {
                "structure_ref": f"read_model_refresh_registry:{name}",
                "display_name": f"Read-model refresh: {name}",
                "signals": {
                    "ritual_repeats_without_new_info": 0,
                    "new_information_count": 1 if reason else 0,
                },
                "evidence_refs": [f"read_model_auto_refresh:{name}"],
            }
        )
    return structures


def _polish_status_structure(repo_root: Path) -> list[dict[str, Any]]:
    path = repo_root / "polish_loop" / "status.json"
    if not path.is_file():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    status = str(payload.get("phase_c_status") or payload.get("status") or "")
    return [
        {
            "structure_ref": "polish_loop:status",
            "display_name": "Polish loop status",
            "signals": {
                "fallback_count": 1 if status.lower() in {"blocked", "failed"} else 0,
                "ritual_repeats_without_new_info": 0,
                "new_information_count": 1,
            },
            "evidence_refs": ["polish_loop/status.json"],
        }
    ]


def _default_structures(repo_root: Path) -> list[dict[str, Any]]:
    return [
        *_activation_register_structures(repo_root),
        *_registry_structures(),
        *_polish_status_structure(repo_root),
    ]


def build_form_review_recommendations(
    *,
    repo_root: str | Path = ".",
    db_path: str | Path | None = None,
    structure_fixtures: Sequence[Mapping[str, Any]] | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    repo = Path(repo_root)
    seed_mode_shift_ledger(db_path=db_path)
    structures = [dict(item) for item in structure_fixtures] if structure_fixtures is not None else _default_structures(repo)
    recommendations = [
        rec
        for structure in structures
        for rec in [_recommendation_for_structure(structure)]
        if rec is not None
    ]
    ledger_rows = query_mode_shifts(db_path=db_path)
    return {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "generated_at": generated_at or _utc_now(),
        "ladder_stage": LADDER_STAGE,
        "mode_shift_ledger_seed_count": len(ledger_rows),
        "structure_count": len(structures),
        "recommendation_count": len(recommendations),
        "recommendations": recommendations,
        "operator_attention_items": [
            {
                "attention_id": f"form_review:{rec['structure_ref']}",
                "operator_summary": rec["operator_line"],
                "recommended_shift": rec["recommended_shift"],
                "evidence_refs": rec["evidence_refs"],
                "send_allowed": False,
                "external_action_allowed": False,
                "ledger_mutation_allowed": False,
                "shift_execution_allowed": False,
            }
            for rec in recommendations[:20]
        ],
        "source_refs": [
            "activation_gate_register.py",
            "read_model_auto_refresh.py:READ_MODEL_REFRESH_REGISTRY",
            "Operator/SUPERB-BATTERY.md",
            "polish_loop/status.json",
            "mode_shift_ledger",
        ],
        "machine_proof": {
            "ladder_stage_recommendation_only": True,
            "shift_executed": False,
            "live_structure_mutation_allowed": False,
            "external_action_allowed": False,
            "send_allowed": False,
            "money_movement_allowed": False,
            "ledger_posting_allowed": False,
            "mode_shift_ledger_seeded": len(ledger_rows) >= 5,
        },
    }


def export_form_review_recommendations(
    *,
    repo_root: str | Path = ".",
    db_path: str | Path | None = None,
    read_model_root: str | Path = DEFAULT_READ_MODEL_ROOT,
    structure_fixtures: Sequence[Mapping[str, Any]] | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    payload = build_form_review_recommendations(
        repo_root=repo_root,
        db_path=db_path,
        structure_fixtures=structure_fixtures,
        generated_at=generated_at,
    )
    root = Path(read_model_root)
    if not root.is_absolute():
        root = Path(repo_root) / root
    root.mkdir(parents=True, exist_ok=True)
    json_path = root / READ_MODEL_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    return {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "json_path": json_path.as_posix(),
        "recommendation_count": payload["recommendation_count"],
        "shift_executed": False,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the prepare-only form-review sweep.")
    parser.add_argument("--once", action="store_true", help="Run one prepare-only recommendation sweep.")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--db", default=None)
    parser.add_argument("--read-model-root", default=DEFAULT_READ_MODEL_ROOT.as_posix())
    parser.add_argument("--generated-at", default=None)
    args = parser.parse_args(argv)
    if not args.once:
        parser.error("--once is required; this tool is prepare-only and has no daemon mode")
    summary = export_form_review_recommendations(
        repo_root=args.repo_root,
        db_path=args.db,
        read_model_root=args.read_model_root,
        generated_at=args.generated_at,
    )
    print(stable_json(summary), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
