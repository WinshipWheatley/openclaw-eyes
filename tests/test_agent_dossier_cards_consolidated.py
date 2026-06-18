import json
from pathlib import Path

import agent_dossier_cards_consolidated as manifest


def _by_agent(payload):
    return {agent["agent_id"]: agent for agent in payload["agents"]}


def test_build_consolidated_agent_manifest_includes_core_agent_fields():
    payload = manifest.build_consolidated_agent_manifest(generated_at="2026-06-18T00:00:00+00:00")
    agents = _by_agent(payload)

    assert payload["status"] == manifest.READY_STATUS
    assert "cassandra" in agents
    assert "chief" in agents

    cassandra = agents["cassandra"]
    assert cassandra["behavior"]["role_summary"]
    assert cassandra["capabilities"]["registry"]
    assert cassandra["voice"]["voice_profile_ref"] == "agent_voice_profile:cassandra"
    assert cassandra["lane"]["lane_id"]
    assert "actual_state" in cassandra["status"]
    assert ".claude/commands/cassandra.md" in cassandra["doc_links"]

    assert payload["machine_proof"]["model_calls_performed"] is False
    assert payload["machine_proof"]["services_started_or_restarted"] is False
    assert payload["secret_access_allowed"] is False


def test_build_consolidated_agent_manifest_includes_rich_agent_map():
    payload = manifest.build_consolidated_agent_manifest(generated_at="2026-06-18T00:00:00+00:00")

    assert set(payload["agent_map"]) == {agent["agent_id"] for agent in payload["agents"]}
    cassandra = payload["agent_map"]["cassandra"]
    section_ids = {section["section_id"] for section in cassandra["view_sections"]}
    assert {"behavior", "capabilities", "voice", "lane", "status", "safety"} <= section_ids
    assert cassandra["overview"]["role_summary"]
    assert cassandra["registry_coverage"]["role_registry"] is True
    assert cassandra["registry_coverage"]["capability_registry"] is True
    assert cassandra["safe_operator_view"]["display_only"] is True
    assert "activate_agent" in cassandra["safe_operator_view"]["blocked"]

    assert payload["agent_relationship_edges"]
    assert any(
        edge["source_agent_id"] == "cassandra" and edge["edge_type"] == "capability_domain"
        for edge in payload["agent_relationship_edges"]
    )
    assert payload["machine_proof"]["agent_map_ids"] == sorted(payload["agent_map"])
    assert payload["machine_proof"]["relationship_edge_count"] == len(payload["agent_relationship_edges"])


def test_export_consolidated_agent_manifest_writes_json(tmp_path: Path):
    result = manifest.export_consolidated_agent_manifest(
        export_root=tmp_path,
        generated_at="2026-06-18T00:00:00+00:00",
    )

    path = tmp_path / manifest.JSON_EXPORT_NAME
    assert path.is_file()
    loaded = json.loads(path.read_text(encoding="utf-8"))
    assert result["agent_count"] == loaded["agent_count"]
    assert loaded["read_model_id"] == manifest.READ_MODEL_ID
    assert "agent_map" in loaded
