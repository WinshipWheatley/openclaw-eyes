import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import worker_package_staging as staging


FIXED_NOW = "2026-06-03T22:00:00+00:00"


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _fixture_root(tmp_path: Path) -> Path:
    root = tmp_path / "generated" / "read_models"
    _write_json(
        root / "agent_handoff_event_status.json",
        {
            "status": "AGENT_HANDOFF_EVENT_CONSUMER_READY",
            "event_history": [
                {
                    "event_id": "agent_handoff_event:pc_fixture",
                    "status": "HANDOFF_EVENT_RECORDED",
                    "handoff_ref": "chief_to_pc_codex_backend_implementation",
                    "from_agent": "chief",
                    "to_agent_or_worker": "pc_codex",
                    "channel_ref": "build_openclaw_backend",
                    "package_type": "pc_codex_backend_worker_packet",
                    "reason": "Backend packet is ready for local PC staging.",
                    "proof_refs": ["generated/read_models/agent_handoff_event_status.json#pc_fixture"],
                    "worker_execution_performed": False,
                    "tool_execution_performed": False,
                    "business_action_performed": False,
                },
                {
                    "event_id": "agent_handoff_event:mac_fixture",
                    "status": "HANDOFF_EVENT_RECORDED",
                    "handoff_ref": "chief_to_mac_codex_ui_excel_gui_operator_assist",
                    "from_agent": "chief",
                    "to_agent_or_worker": "mac_codex",
                    "channel_ref": "build_mission_control_mac",
                    "package_type": "mac_codex_operator_assist_worker_packet",
                    "reason": "Mac UI packet is ready for local Mac staging.",
                    "proof_refs": ["generated/read_models/agent_handoff_event_status.json#mac_fixture"],
                    "worker_execution_performed": False,
                    "tool_execution_performed": False,
                    "business_action_performed": False,
                },
                {
                    "event_id": "agent_handoff_event:chief_fixture",
                    "status": "HANDOFF_EVENT_RECORDED",
                    "handoff_ref": "hermes_to_chief_build_packet",
                    "from_agent": "hermes",
                    "to_agent_or_worker": "chief",
                    "channel_ref": "operations_chief_workboard",
                    "package_type": "architecture_to_build_packet",
                    "reason": "This is not a worker package handoff.",
                    "proof_refs": [],
                    "worker_execution_performed": False,
                    "tool_execution_performed": False,
                    "business_action_performed": False,
                },
            ],
        },
    )
    _write_json(root / "spawned_worker_package_lifecycle.json", {"status": "SPAWNED_WORKER_PACKAGE_LIFECYCLE_READY"})
    _write_json(
        root / "workroom_review_packet_index.json",
        {
            "schema_version": "workroom_review_packet_index_v0",
            "read_model_id": "workroom_review_packet_index",
            "status": "WORKROOM_REVIEW_PACKET_INDEX_READY",
            "packets": [
                {
                    "review_packet_id": "review_packet:existing",
                    "package_id": "pkg:example:existing",
                    "worker_ref": "pc_codex",
                    "status": "REVIEW_PACKET_READY",
                    "business_action_performed": False,
                    "git_push_performed": False,
                }
            ],
            "source_refs": ["generated/read_models/spawned_worker_package_lifecycle.json"],
            "machine_proof": {"business_action_performed": False},
        },
    )
    return root


def _walk_values(payload):
    if isinstance(payload, dict):
        for key, value in payload.items():
            yield key, value
            yield from _walk_values(value)
    elif isinstance(payload, list):
        for value in payload:
            yield from _walk_values(value)


def _assert_no_unsafe_grants(payload: dict) -> None:
    unsafe_keys = {
        "email_send_allowed",
        "ledger_posting_allowed",
        "browser_access_allowed",
        "gmail_allowed",
        "coupa_allowed",
        "portal_submit_allowed",
        "worker_spawn_allowed",
        "worker_assignment_allowed",
        "worker_execution_allowed",
        "tool_execution_allowed",
        "external_llm_allowed",
        "live_provider_allowed",
        "git_push_allowed",
        "sent",
        "paid",
        "worker_spawn_performed",
        "worker_execution_performed",
        "tool_execution_performed",
        "business_action_performed",
        "git_push_performed",
    }
    assert not [key for key, value in _walk_values(payload) if key in unsafe_keys and value is True]


def test_recorded_worker_handoffs_become_package_stubs(tmp_path):
    read_model = staging.build_status_read_model(read_model_root=_fixture_root(tmp_path), generated_at=FIXED_NOW)

    assert read_model["status"] == "WORKER_PACKAGE_STAGING_READY"
    assert read_model["staged_package_count"] == 2
    workers = {package["worker_ref"] for package in read_model["staged_packages"]}
    assert workers == {"pc_codex", "mac_codex"}
    for package in read_model["staged_packages"]:
        assert package["status"] == "PACKAGE_STAGED"
        assert package["result_receipt_required"] is True
        assert package["business_action_allowed"] is False
        assert package["worker_inherits_speaker_authority"] is False
        assert package["worker_spawn_performed"] is False
        assert package["worker_execution_performed"] is False
        assert package["git_push_allowed"] is False
        assert package["source_handoff_ref"].startswith("chief_to_")
        assert package["allowed_files_or_paths"]
        assert package["blocked_actions"]
        assert package["expected_outputs"]
        assert package["tests_required"]
    _assert_no_unsafe_grants(read_model)


def test_review_packet_index_tracks_staging_without_creating_review_packet(tmp_path):
    root = _fixture_root(tmp_path)
    status = staging.build_status_read_model(read_model_root=root, generated_at=FIXED_NOW)
    index = staging.build_review_packet_index(read_model_root=root, staging_status=status, generated_at=FIXED_NOW)

    assert len(index["packets"]) == 1
    assert index["packets"][0]["review_packet_id"] == "review_packet:existing"
    assert index["worker_package_staging"]["applied"] is True
    assert len(index["worker_package_staging"]["staged_package_ids"]) == 2
    assert index["machine_proof"]["no_review_packet_created_from_staging"] is True
    assert index["machine_proof"]["worker_execution_performed"] is False
    _assert_no_unsafe_grants(index)


def test_export_writes_local_bridge_equal_and_wiki(tmp_path):
    root = _fixture_root(tmp_path)
    result = staging.export_worker_package_staging(
        read_model_root=root,
        export_root=tmp_path / "read_models",
        bridge_export_root=tmp_path / "bridge",
        wiki_path=tmp_path / "wiki" / "Worker Package Staging.md",
        generated_at=FIXED_NOW,
    )

    status_local = json.loads(Path(result["read_model_path"]).read_text(encoding="utf-8"))
    status_bridge = json.loads(Path(result["bridge_read_model_path"]).read_text(encoding="utf-8"))
    index_local = json.loads(Path(result["review_packet_index_path"]).read_text(encoding="utf-8"))
    index_bridge = json.loads(Path(result["bridge_review_packet_index_path"]).read_text(encoding="utf-8"))
    wiki = Path(result["wiki_path"])

    assert status_local == status_bridge
    assert index_local == index_bridge
    assert result["staged_package_count"] == "2"
    assert wiki.exists()
    assert "No worker is spawned or run." in wiki.read_text(encoding="utf-8")
    _assert_no_unsafe_grants(status_local)
    _assert_no_unsafe_grants(index_local)


def test_blocked_or_non_worker_handoffs_are_not_staged(tmp_path):
    root = _fixture_root(tmp_path)
    status_payload = json.loads((root / "agent_handoff_event_status.json").read_text(encoding="utf-8"))
    status_payload["event_history"] = [
        {
            "event_id": "agent_handoff_event:blocked_fixture",
            "status": "BLOCKED_UNSAFE_AUTHORITY",
            "handoff_ref": "chief_to_pc_codex_backend_implementation",
            "to_agent_or_worker": "pc_codex",
            "channel_ref": "build_openclaw_backend",
            "package_type": "pc_codex_backend_worker_packet",
        },
        {
            "event_id": "agent_handoff_event:chief_fixture",
            "status": "HANDOFF_EVENT_RECORDED",
            "handoff_ref": "hermes_to_chief_build_packet",
            "to_agent_or_worker": "chief",
            "channel_ref": "operations_chief_workboard",
            "package_type": "architecture_to_build_packet",
        },
    ]
    _write_json(root / "agent_handoff_event_status.json", status_payload)

    read_model = staging.build_status_read_model(read_model_root=root, generated_at=FIXED_NOW)

    assert read_model["staged_package_count"] == 0
    assert read_model["staged_packages"] == []
    assert read_model["machine_proof"]["worker_spawn_performed"] is False
    assert read_model["machine_proof"]["worker_execution_performed"] is False
    _assert_no_unsafe_grants(read_model)
