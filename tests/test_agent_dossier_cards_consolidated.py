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
