import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import openclaw_workroom_registry as registry


FIXED_NOW = "2026-06-03T14:00:00+00:00"


def _channel(read_model: dict, channel_ref: str) -> dict:
    matches = [channel for channel in read_model["channels"] if channel["channel_ref"] == channel_ref]
    assert len(matches) == 1
    return matches[0]


def _walk_values(payload):
    if isinstance(payload, dict):
        for key, value in payload.items():
            yield key, value
            yield from _walk_values(value)
    elif isinstance(payload, list):
        for value in payload:
            yield from _walk_values(value)


def test_builds_all_required_channels_with_required_fields():
    read_model = registry.build_read_model(generated_at=FIXED_NOW)

    assert read_model["status"] == registry.REGISTRY_STATUS
    assert read_model["channel_count"] == len(registry.REQUIRED_CHANNEL_REFS)
    assert {channel["channel_ref"] for channel in read_model["channels"]} == set(registry.REQUIRED_CHANNEL_REFS)
    required_fields = {
        "channel_ref",
        "display_name",
        "world_ref",
        "thread_ref",
        "primary_agent",
        "allowed_speakers",
        "allowed_package_types",
        "blocked_actions",
        "proof_collapsed_by_default",
        "history_policy",
        "operator_next_action_policy",
    }
    for channel in read_model["channels"]:
        assert required_fields <= set(channel)
        assert channel["proof_collapsed_by_default"] is True
        assert channel["history_policy"]["mode"] == "local_read_model_thread_refs_only"
        assert channel["operator_next_action_policy"]["mode"] == "operator_review_required"


def test_channel_agent_and_package_mappings_are_domain_specific():
    read_model = registry.build_read_model(generated_at=FIXED_NOW)

    st_annes = _channel(read_model, "finance_st_annes")
    assert st_annes["primary_agent"] == "cassandra"
    assert "work_log_status_packet" in st_annes["allowed_package_types"]
    assert "cassandra" in st_annes["allowed_speakers"]
    assert "clara" not in st_annes["allowed_speakers"]

    architecture = _channel(read_model, "architecture_hermes")
    assert architecture["primary_agent"] == "hermes"
    assert "architecture_recommendation_packet" in architecture["allowed_package_types"]

    guardian = _channel(read_model, "security_guardian_gates")
    assert guardian["primary_agent"] == "guardian"
    assert "protected_gate_packet" in guardian["allowed_package_types"]

    creative = _channel(read_model, "creative_niles_studio")
    assert creative["primary_agent"] == "niles"
    assert creative["allowed_speakers"] == ["niles", "openclaw", "pc_codex", "mac_codex"]

    business_development = _channel(read_model, "business_development_capital_hilton")
    assert business_development["primary_agent"] == "clara"
    assert "external_draft_artifact_packet" in business_development["allowed_package_types"]


def test_agent_mapping_covers_required_speakers_and_worker_outputs_only():
    read_model = registry.build_read_model(generated_at=FIXED_NOW)
    agents = {agent["agent_ref"]: agent for agent in read_model["agent_mapping"]}

    for agent_ref in (
        "cassandra",
        "chief",
        "hermes",
        "guardian",
        "niles",
        "clara",
        "openclaw",
        "pc_codex",
        "mac_codex",
    ):
        assert agent_ref in agents

    assert "finance work logs" in agents["cassandra"]["scope"]
    assert "architecture recommendations" in agents["hermes"]["scope"]
    assert "protected action gates" in agents["guardian"]["scope"]
    assert agents["clara"]["scope"] == "external draft artifacts only"
    assert agents["pc_codex"]["scope"] == "spawned worker outputs only"
    assert agents["mac_codex"]["scope"] == "spawned worker outputs only"
    assert "spawning workers" in agents["pc_codex"]["blocked_output_scope"]


def test_blocks_live_slack_telegram_and_business_actions():
    read_model = registry.build_read_model(generated_at=FIXED_NOW)

    for channel in read_model["channels"]:
        for action in (
            "connect_slack_live",
            "connect_telegram_live",
            "send_slack_message",
            "send_telegram_message",
            "send_email",
            "open_gmail",
            "open_browser",
            "open_coupa",
            "mutate_ledger",
            "mutate_workbook",
            "export_pdf",
            "mark_paid",
            "submit_portal",
            "push_git",
            "run_live_provider",
        ):
            assert action in channel["blocked_actions"]
            assert action in channel["operator_next_action_policy"]["blocked_next_actions"]
    assert read_model["machine_proof"]["all_channels_block_live_slack_and_telegram"] is True


def test_export_writes_local_bridge_equal_and_wiki(tmp_path):
    result = registry.export_openclaw_workroom_registry(
        export_root=tmp_path / "read_models",
        bridge_export_root=tmp_path / "bridge",
        wiki_path=tmp_path / "wiki" / "OpenClaw Workroom Registry.md",
        generated_at=FIXED_NOW,
    )

    local = json.loads(Path(result["read_model_path"]).read_text(encoding="utf-8"))
    bridge = json.loads(Path(result["bridge_read_model_path"]).read_text(encoding="utf-8"))
    assert local == bridge
    assert local["status"] == registry.REGISTRY_STATUS
    assert result["channel_count"] == str(len(registry.REQUIRED_CHANNEL_REFS))
    wiki = Path(result["wiki_path"])
    assert wiki.exists()
    assert "No Slack connection." in wiki.read_text(encoding="utf-8")


def test_no_unsafe_authority_grants():
    read_model = registry.build_read_model(generated_at=FIXED_NOW)

    unsafe_keys = {
        "slack_connect_allowed",
        "telegram_live_connect_allowed",
        "message_send_allowed",
        "email_send_allowed",
        "gmail_allowed",
        "browser_access_allowed",
        "coupa_allowed",
        "portal_submit_allowed",
        "ledger_posting_allowed",
        "ledger_mutation_allowed",
        "workbook_mutation_allowed",
        "pdf_export_allowed",
        "paid_marking_allowed",
        "live_provider_allowed",
        "external_llm_allowed",
        "agent_loop_allowed",
        "git_push_allowed",
        "sent",
        "paid",
    }
    assert not [key for key, value in _walk_values(read_model) if key in unsafe_keys and value is True]
    assert read_model["machine_proof"]["slack_connected"] is False
    assert read_model["machine_proof"]["telegram_live_connected"] is False
    assert read_model["machine_proof"]["message_send_performed"] is False
    assert read_model["machine_proof"]["ledger_mutation_performed"] is False
