import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import spawned_worker_package_lifecycle as lifecycle


FIXED_NOW = "2026-06-03T16:00:00+00:00"


def _walk_values(payload):
    if isinstance(payload, dict):
        for key, value in payload.items():
            yield key, value
            yield from _walk_values(value)
    elif isinstance(payload, list):
        for value in payload:
            yield from _walk_values(value)


def test_lifecycle_states_are_complete_and_ordered():
    read_model = lifecycle.build_read_model(generated_at=FIXED_NOW)

    assert read_model["status"] == lifecycle.LIFECYCLE_STATUS
    assert tuple(read_model["lifecycle_states"]) == lifecycle.LIFECYCLE_STATES
    assert [state["ordinal"] for state in read_model["state_definitions"]] == list(range(1, 10))
    assert {state["state"] for state in read_model["state_definitions"]} == set(lifecycle.LIFECYCLE_STATES)
    assert read_model["machine_proof"]["all_lifecycle_states_present"] is True


def test_transitions_are_pr_like_and_receipted():
    read_model = lifecycle.build_read_model(generated_at=FIXED_NOW)
    transitions = {(item["from_state"], item["to_state"]): item for item in read_model["transitions"]}

    assert ("PACKAGE_STAGED", "WORKER_ASSIGNED") in transitions
    assert ("WORKER_RUNNING", "RESULT_READY") in transitions
    assert ("RESULT_READY", "REVIEW_PACKET_READY") in transitions
    assert ("REVIEW_PACKET_READY", "OPERATOR_APPROVED") in transitions
    assert ("OPERATOR_APPROVED", "MERGED_OR_RECORDED") in transitions
    assert ("REVIEW_PACKET_READY", "REWORK_REQUIRED") in transitions
    assert ("REVIEW_PACKET_READY", "BLOCKED_BY_GATE") in transitions
    assert all(transition["receipt_required"] is True for transition in read_model["transitions"])
    assert transitions[("REVIEW_PACKET_READY", "OPERATOR_APPROVED")]["operator_review_required"] is True


def test_review_packet_contract_contains_required_fields():
    read_model = lifecycle.build_read_model(generated_at=FIXED_NOW)
    contract = read_model["review_packet_contract"]

    assert tuple(contract["required_fields"]) == lifecycle.REVIEW_PACKET_REQUIRED_FIELDS
    assert set(contract["field_contract"]) == set(lifecycle.REVIEW_PACKET_REQUIRED_FIELDS)
    for field in lifecycle.REVIEW_PACKET_REQUIRED_FIELDS:
        assert contract["field_contract"][field]["required"] is True
    assert contract["proof_collapsed_by_default"] is True
    assert contract["raw_diff_body_by_default"] is False
    assert contract["operator_approval_required_before_merge_or_record"] is True
    assert "unsafe_true_grants" in contract["field_contract"]["unsafe_scan_result"]["required_subfields"]


def test_worker_scope_and_authority_rules_are_explicit():
    read_model = lifecycle.build_read_model(generated_at=FIXED_NOW)
    workers = {worker["worker_ref"]: worker for worker in read_model["supported_workers"]}

    assert workers["pc_codex"]["default_channel_ref"] == "build_openclaw_backend"
    assert workers["mac_codex"]["default_channel_ref"] == "build_mission_control_mac"
    assert "Worker does not inherit speaker authority." in read_model["authority_rules"]
    assert "speaker_ref does not grant tools." in read_model["authority_rules"]
    assert "All business actions remain gated." in read_model["authority_rules"]
    assert "No child spawning unless LM2 cage/Guardian allows." in read_model["authority_rules"]
    assert "spawn_worker" in read_model["blocked_actions"]
    assert "grant_tool_authority_from_speaker_ref" in read_model["blocked_actions"]


def test_examples_show_review_packets_without_execution_authority():
    read_model = lifecycle.build_read_model(generated_at=FIXED_NOW)
    examples = {example["example_ref"]: example for example in read_model["examples"]}

    pc = examples["pc_backend_package_review"]
    assert pc["worker_ref"] == "pc_codex"
    assert pc["channel_ref"] == "build_openclaw_backend"
    assert pc["state_path"][-1] == "REVIEW_PACKET_READY"
    assert pc["review_packet_summary"]["unsafe_scan_result"]["unsafe_true_grants"] == []
    assert "does not push" in pc["authority_note"]

    mac = examples["mac_ui_package_review"]
    assert mac["worker_ref"] == "mac_codex"
    assert mac["channel_ref"] == "build_mission_control_mac"
    assert mac["review_packet_summary"]["screenshots"]
    assert "does not mutate workbooks" in mac["authority_note"]


def test_export_writes_local_bridge_equal_and_wiki(tmp_path):
    result = lifecycle.export_spawned_worker_package_lifecycle(
        export_root=tmp_path / "read_models",
        bridge_export_root=tmp_path / "bridge",
        wiki_path=tmp_path / "wiki" / "Spawned Worker Package Lifecycle.md",
        generated_at=FIXED_NOW,
    )

    local = json.loads(Path(result["read_model_path"]).read_text(encoding="utf-8"))
    bridge = json.loads(Path(result["bridge_read_model_path"]).read_text(encoding="utf-8"))
    assert local == bridge
    assert local["status"] == lifecycle.LIFECYCLE_STATUS
    assert result["state_count"] == str(len(lifecycle.LIFECYCLE_STATES))
    assert result["review_packet_field_count"] == str(len(lifecycle.REVIEW_PACKET_REQUIRED_FIELDS))
    wiki = Path(result["wiki_path"])
    assert wiki.exists()
    assert "No worker spawn." in wiki.read_text(encoding="utf-8")


def test_no_unsafe_authority_grants_or_worker_execution():
    read_model = lifecycle.build_read_model(generated_at=FIXED_NOW)

    unsafe_keys = {
        "worker_spawn_allowed",
        "child_agent_run_allowed",
        "agent_loop_allowed",
        "external_llm_allowed",
        "external_tool_connect_allowed",
        "git_push_allowed",
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
        "speaker_tool_grant_allowed",
        "business_action_allowed",
        "sent",
        "paid",
    }
    assert not [key for key, value in _walk_values(read_model) if key in unsafe_keys and value is True]
    assert read_model["machine_proof"]["worker_spawn_performed"] is False
    assert read_model["machine_proof"]["child_agent_run_performed"] is False
    assert read_model["machine_proof"]["git_push_performed"] is False
    assert read_model["machine_proof"]["ledger_mutation_performed"] is False
