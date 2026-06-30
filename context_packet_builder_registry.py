"""Registry and contract-test adapters for context/fact packet builders."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping


@dataclass(frozen=True)
class PacketBuilderSpec:
    filename: str
    module_name: str
    build_function: str
    adapter: str


REGISTERED_CONTEXT_PACKET_BUILDERS: dict[str, PacketBuilderSpec] = {
    "maestro_context_packet.py": PacketBuilderSpec(
        filename="maestro_context_packet.py",
        module_name="maestro_context_packet",
        build_function="build_maestro_context_packet",
        adapter="maestro",
    ),
    "cassandra_context_packet.py": PacketBuilderSpec(
        filename="cassandra_context_packet.py",
        module_name="cassandra_context_packet",
        build_function="build_cassandra_context_packet",
        adapter="cassandra",
    ),
    "hermes_context_packet.py": PacketBuilderSpec(
        filename="hermes_context_packet.py",
        module_name="hermes_context_packet",
        build_function="build_hermes_context_packet",
        adapter="hermes",
    ),
    "guardian_context_packet.py": PacketBuilderSpec(
        filename="guardian_context_packet.py",
        module_name="guardian_context_packet",
        build_function="build_guardian_context_packet",
        adapter="guardian",
    ),
    "cassandra_clara_fact_packet.py": PacketBuilderSpec(
        filename="cassandra_clara_fact_packet.py",
        module_name="cassandra_clara_fact_packet",
        build_function="build_cassandra_clara_fact_packet",
        adapter="cassandra_clara",
    ),
    "backend_knowledge_packet.py": PacketBuilderSpec(
        filename="backend_knowledge_packet.py",
        module_name="backend_knowledge_packet",
        build_function="build_backend_ledger_context_packet",
        adapter="backend",
    ),
}


def discover_context_packet_builder_files(root: str | Path) -> list[str]:
    base = Path(root)
    names = {
        path.name
        for pattern in ("*_context_packet.py", "*_fact_packet.py")
        for path in base.glob(pattern)
        if path.name != "__init__.py"
    }
    return sorted(names)


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _maestro_fixture(root: Path) -> None:
    _write_json(
        root / "agent_presence.json",
        {
            "generated_at": "2026-06-29T00:00:00+00:00",
            "agents": [{"agent_id": "maestro", "display_name": "Maestro", "actual_state": "online"}],
        },
    )
    _write_json(
        root / "openclaw_capability_index.json",
        {
            "generic_capabilities": [
                {
                    "capability_id": "ledger_context",
                    "capability_name": "Ledger context source",
                    "capability_status": "LIVE_IMPLEMENTED",
                }
            ]
        },
    )


def build_registered_packet(filename: str, *, tmp_path: Path) -> dict[str, Any]:
    spec = REGISTERED_CONTEXT_PACKET_BUILDERS[filename]
    if spec.adapter == "maestro":
        import maestro_context_packet as mod

        read_models = tmp_path / "maestro_read_models"
        _maestro_fixture(read_models)
        return mod.build_maestro_context_packet(
            question="ledger contract probe",
            read_model_root=read_models,
            operator_truth_store_path=tmp_path / "operator_truth_store.json",
            require_real_truth=False,
        )
    if spec.adapter == "cassandra":
        import cassandra_context_packet as mod

        return mod.build_cassandra_context_packet(
            question="ledger contract probe",
            read_model_root=tmp_path / "cassandra_read_models",
        )
    if spec.adapter == "hermes":
        import hermes_context_packet as mod

        return mod.build_hermes_context_packet(
            question="ledger contract probe",
            read_model_root=tmp_path / "hermes_read_models",
        )
    if spec.adapter == "guardian":
        import guardian_context_packet as mod

        return mod.build_guardian_context_packet(
            question="ledger contract probe",
            read_model_root=tmp_path / "guardian_read_models",
        )
    if spec.adapter == "cassandra_clara":
        import cassandra_clara_fact_packet as mod

        return mod.build_cassandra_clara_fact_packet(
            db_path=tmp_path / "cassandra_clara.sqlite",
            artifact_root=tmp_path / "cassandra_clara_artifacts",
        )
    if spec.adapter == "backend":
        import backend_knowledge_packet as mod

        return mod.build_backend_ledger_context_packet(question="ledger contract probe")
    raise KeyError(filename)


def packet_facts(packet: Mapping[str, Any]) -> list[dict[str, Any]]:
    if isinstance(packet.get("facts"), list):
        return [dict(f) for f in packet["facts"] if isinstance(f, Mapping)]
    facts: list[dict[str, Any]] = []
    for key in ("governed_facts", "invoice_facts_used", "contact_candidates", "receivable_posture"):
        values = packet.get(key)
        if isinstance(values, list):
            facts.extend(dict(v) for v in values if isinstance(v, Mapping))
    return facts


__all__ = [
    "PacketBuilderSpec",
    "REGISTERED_CONTEXT_PACKET_BUILDERS",
    "build_registered_packet",
    "discover_context_packet_builder_files",
    "packet_facts",
]
