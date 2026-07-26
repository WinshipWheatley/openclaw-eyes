"""Niles' context packet.

Niles never had one either — its listener had a status renderer, a subprocess
intake parser and introspection, and its gear KB (X32 rack, DriveRack, DL32,
Push 2, APC40, MPC One+, FCB1010, Logic Pro X, Ableton Live, TH-U, MainStage)
was unreachable at answer time.

Thin by design: it reuses `niles_context_grounding` and emits the standard
packet shape so `packet_engine.build_agent_packet(agent="niles",
legacy_builder=...)` wraps it with persona, receipt and dankness scoring like
every other agent.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import niles_context_grounding
import read_model_demand_index

SCHEMA_VERSION = "niles_context_packet_v0"
DEFAULT_READ_MODEL_ROOT = Path("generated/read_models")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _compact(value: str, *, limit: int = 900) -> str:
    return " ".join(str(value or "").split())[:limit]


def _fact(*, topic: str, label: str, value: str, source_ref: str) -> dict[str, Any]:
    return {
        "fact_id": f"{topic}:{hashlib.sha256((label + source_ref).encode()).hexdigest()[:12]}",
        "topic": topic,
        "label": _compact(label, limit=160),
        "value": _compact(value),
        "provenance": "niles_gear_kb" if topic == "rig_gear" else "generated_read_model",
        "freshness": {},
        "source_ref": source_ref,
        "pii_tier": "PUBLIC",
    }


def build_niles_context_packet(
    *,
    question: str = "",
    read_model_root: str | Path = DEFAULT_READ_MODEL_ROOT,
    **_ignored: Any,
) -> dict[str, Any]:
    """Build Niles' packet: relevant rig/software knowledge + demand read-models."""

    root = Path(read_model_root)
    facts: list[dict[str, Any]] = []
    source_refs: list[str] = []

    for line in niles_context_grounding.select_gear_context(question):
        facts.append(
            _fact(
                topic="rig_gear",
                label="Rig/software",
                value=line.lstrip("- "),
                source_ref="niles_rig_kb.py",
            )
        )
    if facts:
        source_refs.append("niles_rig_kb.py")

    selection = read_model_demand_index.select_demand_read_models(
        root, question=question
    )
    for row in selection.rows:
        path = root / row.relative_path
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        ref = f"generated/read_models/{row.relative_path}"
        source_refs.append(ref)
        facts.append(
            _fact(
                topic="demand_read_model",
                label=f"Read-model: {row.id}{read_model_demand_index.age_label(row)}",
                value=json.dumps(payload, sort_keys=True),
                source_ref=ref,
            )
        )

    generated_at = _now()
    return {
        "schema_version": SCHEMA_VERSION,
        "packet_id": hashlib.sha256(
            f"{SCHEMA_VERSION}{generated_at}{question}".encode()
        ).hexdigest()[:16],
        "status": "READY",
        "generated_at": generated_at,
        "question": _compact(question, limit=300),
        "facts": facts,
        "source_refs": source_refs,
        "fact_count": len(facts),
        "bounds": {"demand_selection_error": selection.error or ""},
        "packet_text": "\n".join(f"- {f['label']}: {f['value']}" for f in facts),
    }
