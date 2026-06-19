import json
from pathlib import Path

import agent_capability_view as view
from agent_lane_registry import DEFAULT_AGENT_LANE_SEEDS
from scripts.export_agent_capability_view import main as export_main


FIXED_NOW = "2026-06-18T23:30:00+00:00"


def _build() -> dict:
    return view.build_agent_capability_view(generated_at=FIXED_NOW)


def test_rich_view_combines_lane_registry_and_legacy_capability_claims_without_authority():
    payload = _build()
    agents = {agent["agent_id"]: agent for agent in payload["agents"]}

    assert payload["schema_version"] == view.SCHEMA_VERSION
    assert payload["read_model_id"] == view.READ_MODEL_ID
    assert payload["agent_count"] == len(DEFAULT_AGENT_LANE_SEEDS)
    assert "watch_desk" in agents
    assert payload["authority_boundary"]["all_action_authority_flags_false"] is True
    assert payload["machine_proof"]["legacy_connected_claims_are_context_only"] is True
    assert payload["machine_proof"]["runtime_dispatch_allowed"] is False

    cassandra = agents["cassandra"]
    legacy = {cap["capability_name"]: cap for cap in cassandra["legacy_capability_claims"]}
    assert "email_draft" in legacy
    assert legacy["email_draft"]["legacy_connected"] is True
    assert legacy["email_draft"]["claim_status"] == "LEGACY_CONNECTED_CLAIM_NEEDS_RECEIPT"
    assert legacy["email_draft"]["runtime_authority_granted"] is False
    assert cassandra["integration_posture"]["legacy_claims_do_not_override_lane_authority"] is True
    assert cassandra["integration_posture"]["runtime_dispatch_allowed"] is False


def test_capability_indexes_cover_domains_outputs_worlds_and_sources():
    payload = _build()

    assert "cassandra" in payload["agents_by_capability_domain"]["email"]
    assert "chief" in payload["agents_by_capability_domain"]["approval"]
    assert "chief" in payload["agents_by_allowed_output_kind"]["codex_work_packet"]
    assert "niles" in payload["agents_by_world"]["music_art"]
    assert "watch_desk" in payload["agents_by_source_kind"]["report_bridge"]
    assert payload["registry_agent_ids_without_legacy_capability_claims"] == [
        "guardian",
        "hermes",
        "niles",
        "report_bridge",
        "watch_desk",
    ]
    assert payload["legacy_actor_ids_not_in_lane_registry"] == []


def test_agent_records_are_routing_context_not_activation():
    payload = _build()

    for agent in payload["agents"]:
        assert agent["activation_status"] == "NOT_ACTIVATED_BY_VIEW"
        assert agent["action_authority_granted"] is False
        assert agent["runtime_dispatch_allowed"] is False
        assert agent["capability_summary"]["blocked_output_count"] >= 1
        for cap in agent["lane_capabilities"]:
            assert cap["action_authority_granted"] is False
            assert cap["runtime_dispatch_allowed"] is False
        for claim in agent["legacy_capability_claims"]:
            assert claim["claim_basis"] == "legacy_capability_registry_context_only"
            assert claim["action_authority_granted"] is False


def test_exporter_writes_json_and_operator_markdown(tmp_path):
    export_root = tmp_path / "generated" / "read_models"

    result = export_main(
        [
            "--export-root",
            export_root.as_posix(),
            "--generated-at",
            FIXED_NOW,
            "--format",
            "summary",
        ]
    )

    assert result == 0
    json_path = export_root / view.JSON_EXPORT_NAME
    operator_path = export_root / view.OPERATOR_EXPORT_NAME
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    operator = operator_path.read_text(encoding="utf-8")
    assert payload["agent_count"] == len(DEFAULT_AGENT_LANE_SEEDS)
    assert payload["machine_proof"]["capability_view_exists"] is True
    assert "Agent Capability View" in operator
    assert "Boundary:" in operator
    assert "Next safe move:" in operator
