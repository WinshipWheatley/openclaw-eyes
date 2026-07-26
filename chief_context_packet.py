"""Chief's context packet.

Chief never had one. Its conversational grounding was a fixed, question-
independent snapshot plus three hardcoded read-models, assembled inline in the
router — so the packet engine (shared persona, build receipt, dankness scoring)
could not wrap it the way it wraps every other agent.

This is deliberately thin: it reuses Chief's existing standing snapshot and the
shared demand index, and emits the standard packet shape so
`packet_engine.build_agent_packet(agent="chief", legacy_builder=...)` works.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import read_model_demand_index

SCHEMA_VERSION = "chief_context_packet_v0"
DEFAULT_READ_MODEL_ROOT = Path("generated/read_models")

# Chief's standing operational read-models — always considered, then topped up
# by demand selection over the rest of the library.
CHIEF_STANDING_READ_MODELS = (
    "agent_presence.json",
    "chief_status_rail.json",
    "work_board.json",
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _compact(value: str, *, limit: int = 900) -> str:
    text = " ".join(str(value or "").split())
    return text[:limit]


def _fact(*, topic: str, label: str, value: str, source_ref: str, age: str = "") -> dict[str, Any]:
    return {
        "fact_id": f"{topic}:{hashlib.sha256((label + source_ref).encode()).hexdigest()[:12]}",
        "topic": topic,
        "label": _compact(label, limit=160),
        "value": _compact(value),
        "provenance": "generated_read_model",
        "freshness": {"as_of_note": age} if age else {},
        "source_ref": source_ref,
        "pii_tier": "PUBLIC",
    }


def _read(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def build_chief_context_packet(
    *,
    question: str = "",
    read_model_root: str | Path = DEFAULT_READ_MODEL_ROOT,
    **_ignored: Any,
) -> dict[str, Any]:
    """Build Chief's packet: standing operational state + demand-selected facts."""

    root = Path(read_model_root)
    facts: list[dict[str, Any]] = []
    source_refs: list[str] = []

    for name in CHIEF_STANDING_READ_MODELS:
        payload = _read(root / name)
        if not payload:
            continue
        ref = f"generated/read_models/{name}"
        source_refs.append(ref)
        facts.append(
            _fact(
                topic="chief_standing_state",
                label=f"Standing read-model: {Path(name).stem}",
                value=json.dumps(payload, sort_keys=True),
                source_ref=ref,
            )
        )

    selection = read_model_demand_index.select_demand_read_models(
        root, question=question, already_loaded=set(CHIEF_STANDING_READ_MODELS)
    )
    for row in selection.rows:
        payload = _read(root / row.relative_path)
        if not payload:
            continue
        ref = f"generated/read_models/{row.relative_path}"
        source_refs.append(ref)
        facts.append(
            _fact(
                topic="demand_read_model",
                label=f"Read-model: {row.id}",
                value=json.dumps(payload, sort_keys=True),
                source_ref=ref,
                age=read_model_demand_index.age_label(row).strip(" ()"),
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
