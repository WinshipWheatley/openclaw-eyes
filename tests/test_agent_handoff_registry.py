import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import agent_handoff_registry as registry


FIXED_NOW = "2026-06-03T15:00:00+00:00"


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _fixture_root(tmp_path: Path) -> Path:
    root = tmp_path / "generated" / "read_models"
    _write_json(root / "openclaw_workroom_registry.json", {"status": "OPENCLAW_WORKROOM_REGISTRY_READY"})
    _write_json(root / "package_event_index.json", {"status": "PACKAGE_EVENT_INDEX_READY"})
    _write_json(root / "agent_voice_routing_contract.json", {"status": "AGENT_VOICE_ROUTING_V0_READY"})
    return root


def _handoff(read_model: dict, handoff_ref: str) -> dict:
    matches = [handoff for handoff in read_model["handoffs"] if handoff["handoff_ref"] == handoff_ref]
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


def test_builds_required_handoffs_with_ready_preconditions(tmp_path):
    root = _fixture_root(tmp_path)
    read_model = registry.build_read_model(read_model_root=root, generated_at=FIXED_NOW)

    assert read_model["status"] == registry.REGISTRY_STATUS
    assert read_model["handoff_count"] == len(registry.REQUIRED_HANDOFF_REFS)
    assert {handoff["handoff_ref"] for handoff in read_model["handoffs"]} == set(registry.REQUIRED_HANDOFF_REFS)
    assert all(item["ready"] for item in read_model["preconditions"])
    for handoff in read_model["handoffs"]:
        assert handoff["requires_operator_approval"] is True
        assert handoff["receipt_required"] is True


def test_required_routes_target_expected_agents_channels_and_workers(tmp_path):
    read_model = registry.build_read_model(read_model_root=_fixture_root(tmp_path), generated_at=FIXED_NOW)

    cassandra_chief = _handoff(read_model, "cassandra_to_chief_package_needed")
    assert cassandra_chief["from_agent"] == "cassandra"
    assert cassandra_chief["to_agent_or_worker"] == "chief"
    assert cassandra_chief["channel_ref"] == "operations_chief_workboard"
    assert cassandra_chief["package_type"] == "package_request_handoff_packet"

    cassandra_guardian = _handoff(read_model, "cassandra_to_guardian_authority_detected")
    assert cassandra_guardian["to_agent_or_worker"] == "guardian"
    assert cassandra_guardian["channel_ref"] == "security_guardian_gates"
    assert "credential" in cassandra_guardian["trigger_condition"].lower()

    pc = _handoff(read_model, "chief_to_pc_codex_backend_implementation")
    assert pc["to_agent_or_worker"] == "pc_codex"
    assert pc["channel_ref"] == "build_openclaw_backend"
    assert pc["package_type"] == "pc_codex_backend_worker_packet"

    mac = _handoff(read_model, "chief_to_mac_codex_ui_excel_gui_operator_assist")
    assert mac["to_agent_or_worker"] == "mac_codex"
    assert mac["channel_ref"] == "build_mission_control_mac"
    assert "Excel" in mac["trigger_condition"]

    clara = _handoff(read_model, "cassandra_external_register_internal_review_state")
    assert clara["from_agent"] == "cassandra"
    assert clara["to_agent_or_worker"] == "cassandra"
    assert clara["from_register"] == "clara_reid_external"
    assert clara["to_register"] == "cassandra_internal"
    assert clara["channel_ref"] == "business_development_capital_hilton"


def test_examples_encode_required_escalation_paths(tmp_path):
    read_model = registry.build_read_model(read_model_root=_fixture_root(tmp_path), generated_at=FIXED_NOW)
    examples = {example["example_ref"]: example for example in read_model["examples"]}

    bug = examples["customer_reports_bug"]
    assert bug["route_path"] == [
        "cassandra_to_chief_package_needed",
        "chief_to_pc_codex_backend_implementation",
    ]
    assert bug["terminal_package_type"] == "pc_codex_backend_worker_packet"
    assert "build_openclaw_backend" in bug["channel_refs"]

    proposal = examples["capital_hilton_proposal_accepted"]
    assert "cassandra_external_register_internal_review_state" in proposal["route_path"]
    assert proposal["terminal_package_type"] == "package_request_handoff_packet"
    assert "does not mark paid" in proposal["authority_note"]

    submit = examples["submit_invoice"]
    assert submit["route_path"] == ["chief_to_guardian_protected_authority"]
    assert submit["channel_refs"] == ["security_guardian_gates"]
    assert "blocked" in submit["authority_note"]


def test_missing_precondition_marks_not_ready(tmp_path):
    root = _fixture_root(tmp_path)
    _write_json(root / "agent_voice_routing_contract.json", {"status": "NOT_READY"})

    read_model = registry.build_read_model(read_model_root=root, generated_at=FIXED_NOW)

    assert read_model["status"] == registry.REGISTRY_NOT_READY_STATUS
    assert read_model["machine_proof"]["preconditions_ready"] is False


def test_export_writes_local_bridge_equal_and_wiki(tmp_path):
    root = _fixture_root(tmp_path)
    result = registry.export_agent_handoff_registry(
        read_model_root=root,
        export_root=tmp_path / "read_models",
        bridge_export_root=tmp_path / "bridge",
        wiki_path=tmp_path / "wiki" / "Agent Handoff Registry.md",
        generated_at=FIXED_NOW,
    )

    local = json.loads(Path(result["read_model_path"]).read_text(encoding="utf-8"))
    bridge = json.loads(Path(result["bridge_read_model_path"]).read_text(encoding="utf-8"))
    assert local == bridge
    assert local["status"] == registry.REGISTRY_STATUS
    assert result["handoff_count"] == str(len(registry.REQUIRED_HANDOFF_REFS))
    wiki = Path(result["wiki_path"])
    assert wiki.exists()
    assert "No external tool connection." in wiki.read_text(encoding="utf-8")


def test_no_unsafe_authority_grants_or_execution_actions(tmp_path):
    read_model = registry.build_read_model(read_model_root=_fixture_root(tmp_path), generated_at=FIXED_NOW)

    unsafe_keys = {
        "external_tool_connect_allowed",
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
        "authority_grant_allowed",
        "credential_use_allowed",
        "worker_spawn_allowed",
        "agent_loop_allowed",
        "external_llm_allowed",
        "live_provider_allowed",
        "git_push_allowed",
        "sent",
        "paid",
    }
    assert not [key for key, value in _walk_values(read_model) if key in unsafe_keys and value is True]
    for handoff in read_model["handoffs"]:
        assert "connect_external_tool" in handoff["blocked_actions"]
        assert "spawn_worker_from_handoff" in handoff["blocked_actions"]
        assert "grant_authority" in handoff["blocked_actions"]
    assert read_model["machine_proof"]["external_tool_connected"] is False
    assert read_model["machine_proof"]["worker_spawn_performed"] is False
    assert read_model["machine_proof"]["submit_performed"] is False
