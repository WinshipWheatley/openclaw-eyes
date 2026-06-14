import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import workroom_review_packet_index as index


FIXED_NOW = "2026-06-03T18:00:00+00:00"


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _fixture_root(tmp_path: Path) -> Path:
    root = tmp_path / "generated" / "read_models"
    _write_json(
        root / "spawned_worker_package_lifecycle.json",
        {
            "status": "SPAWNED_WORKER_PACKAGE_LIFECYCLE_READY",
            "lifecycle_states": [
                "PACKAGE_STAGED",
                "WORKER_ASSIGNED",
                "WORKER_RUNNING",
                "RESULT_READY",
                "REVIEW_PACKET_READY",
                "OPERATOR_APPROVED",
                "MERGED_OR_RECORDED",
                "REWORK_REQUIRED",
                "BLOCKED_BY_GATE",
            ],
            "authority_rules": [
                "Worker does not inherit speaker authority.",
                "Operator approval is required before merge or recorded completion.",
            ],
            "examples": [
                {
                    "example_ref": "pc_backend_package_review",
                    "worker_ref": "pc_codex",
                    "channel_ref": "build_openclaw_backend",
                    "package_id": "pkg:example:backend",
                    "authority_note": "PC_CODEX output is reviewable; it does not push.",
                    "state_path": [
                        "PACKAGE_STAGED",
                        "WORKER_ASSIGNED",
                        "WORKER_RUNNING",
                        "RESULT_READY",
                        "REVIEW_PACKET_READY",
                    ],
                    "review_packet_summary": {
                        "human_summary": "PC_CODEX changed backend code and returned validation proof.",
                        "files_changed": ["backend.py", "tests/test_backend.py"],
                        "tests_run": ["pytest -q tests/test_backend.py"],
                        "receipts": ["generated/read_models/pc_backend_receipt.json"],
                        "screenshots": [],
                        "proof_refs": ["generated/read_models/backend_packet.json"],
                        "next_safe_action": "Review backend packet before approval.",
                        "unsafe_scan_result": {
                            "status": "PASS",
                            "unsafe_true_grants": [],
                        },
                    },
                },
                {
                    "example_ref": "mac_ui_package_review",
                    "worker_ref": "mac_codex",
                    "channel_ref": "build_mission_control_mac",
                    "package_id": "pkg:example:mission_control_ui",
                    "authority_note": "MAC_CODEX output is reviewable; it does not mutate workbooks.",
                    "state_path": [
                        "PACKAGE_STAGED",
                        "WORKER_ASSIGNED",
                        "WORKER_RUNNING",
                        "RESULT_READY",
                        "REVIEW_PACKET_READY",
                    ],
                    "review_packet_summary": {
                        "human_summary": "MAC_CODEX returned Mission Control UI output.",
                        "files_changed": ["MissionControlView.swift"],
                        "tests_run": ["pytest -q tests/test_mission_control_view_contract.py"],
                        "receipts": ["generated/read_models/mac_ui_receipt.json"],
                        "screenshots": ["generated/screenshots/mission_control_ui.png"],
                        "proof_refs": ["generated/read_models/mac_ui_packet.json"],
                        "next_safe_action": "Inspect screenshot proof before approval.",
                        "unsafe_scan_result": {
                            "status": "PASS",
                            "unsafe_true_grants": [],
                        },
                    },
                },
            ],
        },
    )
    _write_json(
        root / "openclaw_workroom_activity_feed.json",
        {
            "status": "OPENCLAW_WORKROOM_ACTIVITY_FEED_READY",
            "posts": [
                {
                    "post_id": "workroom_post:pc",
                    "channel_ref": "build_openclaw_backend",
                    "speaker_ref": "pc_codex",
                    "post_type": "review_packet",
                    "package_id": "pkg:example:backend",
                    "plain_summary": "PC review packet ready.",
                    "next_safe_action": "Review backend packet.",
                    "proof_refs": ["generated/read_models/openclaw_workroom_activity_feed.json#pc"],
                    "show_machine_details_by_default": False,
                    "business_action_performed": False,
                },
                {
                    "post_id": "workroom_post:mac",
                    "channel_ref": "build_mission_control_mac",
                    "speaker_ref": "mac_codex",
                    "post_type": "review_packet",
                    "package_id": "pkg:example:mission_control_ui",
                    "plain_summary": "Mac review packet ready.",
                    "next_safe_action": "Review UI packet.",
                    "proof_refs": ["generated/read_models/openclaw_workroom_activity_feed.json#mac"],
                    "show_machine_details_by_default": False,
                    "business_action_performed": False,
                },
            ],
        },
    )
    _write_json(
        root / "package_event_index.json",
        {
            "status": "PACKAGE_EVENT_INDEX_READY",
            "events": [],
            "authority_boundary": {
                "git_push_allowed": False,
                "email_send_allowed": False,
                "ledger_posting_allowed": False,
                "business_action_allowed": False,
            },
        },
    )
    return root


def _packets_by_worker(read_model: dict) -> dict[str, dict]:
    return {packet["worker_ref"]: packet for packet in read_model["packets"]}


def _walk_values(payload):
    if isinstance(payload, dict):
        for key, value in payload.items():
            yield key, value
            yield from _walk_values(value)
    elif isinstance(payload, list):
        for value in payload:
            yield from _walk_values(value)


def test_packet_index_parses_lifecycle_states(tmp_path):
    read_model = index.build_read_model(read_model_root=_fixture_root(tmp_path), generated_at=FIXED_NOW)

    assert read_model["status"] == index.INDEX_STATUS
    assert "REVIEW_PACKET_READY" in read_model["lifecycle_states"]
    assert "MERGED_OR_RECORDED" in read_model["lifecycle_states"]
    assert read_model["review_packet_count"] == 2
    assert read_model["packet_counts_by_status"] == {"REVIEW_PACKET_READY": 2}
    for packet in read_model["packets"]:
        assert set(index.REVIEW_PACKET_FIELDS) <= set(packet)
        assert packet["state_path"][-1] == "REVIEW_PACKET_READY"
        assert packet["status"] == "REVIEW_PACKET_READY"
    assert read_model["machine_proof"]["lifecycle_states_parsed"] is True


def test_mac_codex_and_pc_codex_packets_render_as_review_outputs(tmp_path):
    read_model = index.build_read_model(read_model_root=_fixture_root(tmp_path), generated_at=FIXED_NOW)
    packets = _packets_by_worker(read_model)

    assert set(packets) == {"pc_codex", "mac_codex"}
    pc = packets["pc_codex"]
    assert pc["channel_ref"] == "build_openclaw_backend"
    assert pc["files_changed"] == ["backend.py", "tests/test_backend.py"]
    assert pc["tests_run"] == ["pytest -q tests/test_backend.py"]
    assert pc["receipts"] == ["generated/read_models/pc_backend_receipt.json"]
    assert pc["review_packet_only"] is True

    mac = packets["mac_codex"]
    assert mac["channel_ref"] == "build_mission_control_mac"
    assert mac["screenshots"] == ["generated/screenshots/mission_control_ui.png"]
    assert "Mission Control UI output" in mac["human_summary"]
    assert mac["activity_post_refs"] == ["workroom_post:mac"]


def test_operator_approval_required_before_merge_or_recorded_state(tmp_path):
    read_model = index.build_read_model(read_model_root=_fixture_root(tmp_path), generated_at=FIXED_NOW)

    assert "Operator approval is required before merge or recorded completion." in read_model["review_rules"]
    for packet in read_model["packets"]:
        assert packet["operator_decision_required"] is True
        assert packet["operator_approval_required_before_merge_or_record"] is True
        assert packet["merge_allowed"] is False
        assert packet["push_allowed"] is False
        assert packet["business_action_performed"] is False
        assert packet["worker_inherits_speaker_authority"] is False
    assert read_model["machine_proof"]["merge_performed"] is False
    assert read_model["machine_proof"]["git_push_performed"] is False
    assert read_model["machine_proof"]["business_action_performed"] is False


def test_no_unsafe_authority_grants(tmp_path):
    read_model = index.build_read_model(read_model_root=_fixture_root(tmp_path), generated_at=FIXED_NOW)
    unsafe_keys = {
        "worker_spawn_allowed",
        "child_agent_run_allowed",
        "agent_loop_allowed",
        "external_llm_allowed",
        "external_tool_connect_allowed",
        "git_push_allowed",
        "merge_allowed",
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
        "push_allowed",
        "business_action_performed",
        "worker_inherits_speaker_authority",
    }

    assert not [key for key, value in _walk_values(read_model) if key in unsafe_keys and value is True]
    assert read_model["machine_proof"]["worker_spawn_performed"] is False
    assert read_model["machine_proof"]["child_agent_run_performed"] is False
    assert read_model["machine_proof"]["ledger_mutation_performed"] is False
    assert read_model["machine_proof"]["unsafe_true_grants_absent"] is True


def test_export_writes_json_parseable_local_and_bridge_equal(tmp_path):
    result = index.export_workroom_review_packet_index(
        read_model_root=_fixture_root(tmp_path),
        export_root=tmp_path / "read_models",
        bridge_export_root=tmp_path / "bridge",
        wiki_path=tmp_path / "wiki" / "Workroom Review Packet Index.md",
        generated_at=FIXED_NOW,
    )

    local = json.loads(Path(result["read_model_path"]).read_text(encoding="utf-8"))
    bridge = json.loads(Path(result["bridge_read_model_path"]).read_text(encoding="utf-8"))
    assert local == bridge
    assert local["status"] == index.INDEX_STATUS
    assert local["review_packet_count"] == 2
    assert result["review_packet_count"] == "2"
    assert Path(result["wiki_path"]).exists()
