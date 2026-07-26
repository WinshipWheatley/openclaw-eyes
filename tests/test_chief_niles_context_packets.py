"""Chief and Niles get real context packets and go through the packet engine.

Both previously had no `*_context_packet.py` at all: Chief grounded on an
ad-hoc snapshot, Niles on nothing. Every other agent had a builder, so the
packet engine — the shared persona/receipt/dank layer — could never wrap them.
"""

from __future__ import annotations

import json
from pathlib import Path

import chief_context_packet
import niles_context_packet
from packet_engine import build_agent_packet


def _write(root: Path, name: str, payload: dict) -> None:
    (root / name).write_text(json.dumps(payload), encoding="utf-8")


def test_chief_packet_is_ready_and_carries_question_relevant_facts(
    tmp_path: Path,
) -> None:
    root = tmp_path / "generated" / "read_models"
    root.mkdir(parents=True)
    _write(root, "gpu_model_health.json", {"available_vram_gb": 0.4})

    packet = chief_context_packet.build_chief_context_packet(
        question="why is the gpu model health bad", read_model_root=root
    )

    assert packet["status"] == "READY"
    assert any("gpu_model_health" in str(f.get("source_ref")) for f in packet["facts"])


def test_niles_packet_carries_rig_knowledge(tmp_path: Path) -> None:
    root = tmp_path / "generated" / "read_models"
    root.mkdir(parents=True)

    packet = niles_context_packet.build_niles_context_packet(
        question="x32 monitor mix vocal channel", read_model_root=root
    )

    assert packet["status"] == "READY"
    joined = " ".join(str(f.get("value", "")) for f in packet["facts"]).lower()
    assert "x32" in joined


def test_chief_routes_through_the_packet_engine(tmp_path: Path) -> None:
    root = tmp_path / "generated" / "read_models"
    root.mkdir(parents=True)
    _write(root, "gpu_model_health.json", {"available_vram_gb": 0.4})

    packet = build_agent_packet(
        agent="chief",
        question="why is the gpu model health bad",
        legacy_builder=chief_context_packet.build_chief_context_packet,
        read_model_root=root,
    )

    assert packet["agent_id"] == "chief"
    assert packet["persona_delivery"]
    assert packet["packet_engine_receipt"]


def test_niles_routes_through_the_packet_engine(tmp_path: Path) -> None:
    root = tmp_path / "generated" / "read_models"
    root.mkdir(parents=True)

    packet = build_agent_packet(
        agent="niles",
        question="push 2 ableton mapping",
        legacy_builder=niles_context_packet.build_niles_context_packet,
        read_model_root=root,
    )

    assert packet["agent_id"] == "niles"
    assert packet["persona_delivery"]
    assert packet["packet_engine_receipt"]
