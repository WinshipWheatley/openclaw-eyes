"""Chief's conversational grounding reaches the whole read-model library.

Chief had no context packet: its fallback reply grounded on a fixed,
question-independent snapshot plus three hardcoded read-models, so ~499 were
unreachable no matter how relevant.
"""

from __future__ import annotations

import json
from pathlib import Path

import chief_router


def _write(root: Path, name: str, payload: dict) -> None:
    (root / name).write_text(json.dumps(payload), encoding="utf-8")


def test_chief_grounding_is_built_through_the_packet_engine(tmp_path: Path) -> None:
    """Chief's live grounding must come from the shared engine, not ad-hoc, so
    it gets persona, a build receipt and dankness scoring like every agent."""

    root = tmp_path / "generated" / "read_models"
    root.mkdir(parents=True)
    _write(root, "gpu_model_health.json", {"gpu": "starved"})

    packet = chief_router._chief_engine_packet(
        "why is the gpu model health bad", root=root
    )

    assert packet["agent_id"] == "chief"
    assert packet["packet_engine_receipt"]
    assert packet["persona_delivery"]


def test_relevant_read_model_is_added_to_chief_grounding(tmp_path: Path) -> None:
    root = tmp_path / "generated" / "read_models"
    root.mkdir(parents=True)
    _write(
        root,
        "gpu_model_health.json",
        {"gpu": "starved", "available_vram_gb": 0.4},
    )

    grounding = chief_router._chief_demand_context(
        "why is the gpu model health bad", root=root
    )

    assert "gpu_model_health" in grounding
    assert "starved" in grounding


def test_unrelated_question_adds_no_grounding(tmp_path: Path) -> None:
    root = tmp_path / "generated" / "read_models"
    root.mkdir(parents=True)
    _write(root, "gpu_model_health.json", {"gpu": "starved"})

    assert chief_router._chief_demand_context(
        "what is the weather in paris", root=root
    ) == ""


def test_broken_root_yields_no_grounding_and_never_raises(tmp_path: Path) -> None:
    assert chief_router._chief_demand_context(
        "gpu model health", root=tmp_path / "missing"
    ) == ""
