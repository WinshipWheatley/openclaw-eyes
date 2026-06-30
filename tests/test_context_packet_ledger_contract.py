from __future__ import annotations

from pathlib import Path


def test_registered_context_packet_builders_match_filesystem() -> None:
    from context_packet_builder_registry import (
        REGISTERED_CONTEXT_PACKET_BUILDERS,
        discover_context_packet_builder_files,
    )

    discovered = set(discover_context_packet_builder_files(Path(__file__).resolve().parents[1]))
    registered = set(REGISTERED_CONTEXT_PACKET_BUILDERS)

    assert discovered <= registered
    assert "backend_knowledge_packet.py" in registered
    assert registered - discovered == {"backend_knowledge_packet.py"}


def test_registered_context_packet_builders_emit_ledger_provenance(tmp_path: Path) -> None:
    from context_packet_builder_registry import (
        REGISTERED_CONTEXT_PACKET_BUILDERS,
        build_registered_packet,
        packet_facts,
    )
    from context_source import facts_have_ledger_provenance

    for filename in REGISTERED_CONTEXT_PACKET_BUILDERS:
        packet = build_registered_packet(filename, tmp_path=tmp_path)
        facts = packet_facts(packet)
        assert isinstance(facts, list), filename
        assert facts_have_ledger_provenance(facts), filename
