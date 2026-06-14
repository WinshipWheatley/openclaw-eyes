import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import workroom_review_decision_lifecycle as lifecycle


FIXED_NOW = "2026-06-03T21:00:00+00:00"


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _decision(packet_id: str, action: str) -> dict:
    status = {
        "approve_review_packet_for_record": "OPERATOR_REVIEW_RECORDED",
        "request_review_packet_rework": "REWORK_REQUEST_RECORDED",
        "mark_review_packet_informational": "INFORMATIONAL_REVIEW_CLOSED",
    }[action]
    return {
        "receipt_id": f"decision_receipt:{packet_id.split(':')[-1]}",
        "generated_at": FIXED_NOW,
        "review_packet_id": packet_id,
        "decision_action": action,
        "status": status,
        "decision_recorded": True,
        "decision_accepted": True,
        "operator_reviewed": True,
        "speaker_ref": "chief",
        "worker_ref_is_speaker": False,
        "proof_refs": ["generated/read_models/workroom_review_decision_status.json"],
        "operator_display": {
            "speaker_ref": "chief",
            "headline": "Review recorded",
            "plain_summary": "Chief recorded the decision only.",
            "next_safe_action": "Record complete. No merge or push performed.",
        },
        "merge_performed": False,
        "git_push_performed": False,
        "business_action_performed": False,
        "business_state_mutation_performed": False,
    }


def _packet(packet_id: str, package_id: str, channel_ref: str, worker_ref: str) -> dict:
    return {
        "review_packet_id": packet_id,
        "package_id": package_id,
        "worker_ref": worker_ref,
        "channel_ref": channel_ref,
        "status": "REVIEW_PACKET_READY",
        "human_summary": f"{worker_ref.upper()} review packet ready.",
        "files_changed": ["example.py"],
        "tests_run": ["pytest -q tests/test_example.py"],
        "receipts": [],
        "screenshots": [],
        "unsafe_scan_result": {"status": "PASS", "unsafe_true_grants": []},
        "proof_refs": [f"generated/read_models/workroom_review_packet_index.json#{packet_id}"],
        "next_safe_action": "Review the packet and approve, request rework, or block by gate.",
        "operator_decision_required": True,
        "state_path": ["PACKAGE_STAGED", "REVIEW_PACKET_READY"],
        "activity_post_refs": [f"post:{packet_id}"],
        "proof_collapsed_by_default": True,
        "operator_approval_required_before_merge_or_record": True,
        "worker_inherits_speaker_authority": False,
        "merge_allowed": False,
        "push_allowed": False,
        "business_action_performed": False,
        "review_packet_only": True,
    }


def _review_post(packet: dict) -> dict:
    return {
        "post_id": f"workroom_post:{packet['review_packet_id'].split(':')[-1]}",
        "channel_ref": packet["channel_ref"],
        "timestamp": FIXED_NOW,
        "speaker_ref": packet["worker_ref"],
        "post_type": "review_packet",
        "headline": f"{packet['worker_ref'].upper()} review packet ready",
        "plain_summary": packet["human_summary"],
        "status_label": "Review Packet Ready",
        "next_safe_action": "Review the packet and approve, request rework, or block by gate.",
        "target_world_ref": "build",
        "target_thread_ref": packet["channel_ref"],
        "package_id": packet["package_id"],
        "proof_refs": [f"generated/read_models/openclaw_workroom_activity_feed.json#{packet['review_packet_id']}"],
        "show_machine_details_by_default": False,
        "business_action_performed": False,
    }


def _fixture_root(tmp_path: Path) -> Path:
    root = tmp_path / "generated" / "read_models"
    packets = [
        _packet("review_packet:approve", "pkg:approve", "build_openclaw_backend", "pc_codex"),
        _packet("review_packet:rework", "pkg:rework", "build_openclaw_backend", "pc_codex"),
        _packet("review_packet:info", "pkg:info", "build_mission_control_mac", "mac_codex"),
    ]
    _write_json(
        root / "workroom_review_packet_index.json",
        {
            "schema_version": "workroom_review_packet_index_v0",
            "read_model_id": "workroom_review_packet_index",
            "generated_at": FIXED_NOW,
            "status": "WORKROOM_REVIEW_PACKET_INDEX_READY",
            "review_packet_fields": [
                "review_packet_id",
                "package_id",
                "worker_ref",
                "channel_ref",
                "status",
                "human_summary",
                "files_changed",
                "tests_run",
                "receipts",
                "screenshots",
                "unsafe_scan_result",
                "proof_refs",
                "next_safe_action",
                "operator_decision_required",
            ],
            "review_packet_count": len(packets),
            "packet_counts_by_status": {"REVIEW_PACKET_READY": len(packets)},
            "packets_by_channel": {},
            "packets_by_worker": {},
            "packets": packets,
            "review_rules": ["No merge or push action is authorized by this index."],
            "source_refs": ["generated/read_models/spawned_worker_package_lifecycle.json"],
            "machine_proof": {
                "merge_performed": False,
                "git_push_performed": False,
                "business_action_performed": False,
            },
        },
    )
    _write_json(
        root / "openclaw_workroom_activity_feed.json",
        {
            "schema_version": "openclaw_workroom_activity_feed_v0",
            "read_model_id": "openclaw_workroom_activity_feed",
            "generated_at": FIXED_NOW,
            "status": "OPENCLAW_WORKROOM_ACTIVITY_FEED_READY",
            "post_count": len(packets),
            "channel_post_counts": {},
            "posts_by_channel": {},
            "posts": [_review_post(packet) for packet in packets],
            "rules": ["Worker posts are review outputs only."],
            "source_refs": ["generated/read_models/spawned_worker_package_lifecycle.json"],
            "machine_proof": {
                "new_business_truth_created": False,
                "merge_performed": False,
                "git_push_performed": False,
                "business_action_performed": False,
            },
        },
    )
    _write_json(
        root / "workroom_review_decision_status.json",
        {
            "schema_version": "workroom_review_decision_consumer_v0",
            "read_model_id": "workroom_review_decision_status",
            "generated_at": FIXED_NOW,
            "status": "WORKROOM_REVIEW_DECISION_CONSUMER_READY",
            "decision_history": [
                _decision("review_packet:approve", "approve_review_packet_for_record"),
                _decision("review_packet:rework", "request_review_packet_rework"),
                _decision("review_packet:info", "mark_review_packet_informational"),
            ],
            "decision_history_count": 3,
            "last_decision": _decision("review_packet:info", "mark_review_packet_informational"),
            "machine_proof": {
                "merge_performed": False,
                "git_push_performed": False,
                "business_action_performed": False,
            },
        },
    )
    return root


def _packets_by_id(packet_index: dict) -> dict[str, dict]:
    return {packet["review_packet_id"]: packet for packet in packet_index["packets"]}


def _walk_values(payload):
    if isinstance(payload, dict):
        for key, value in payload.items():
            yield key, value
            yield from _walk_values(value)
    elif isinstance(payload, list):
        for value in payload:
            yield from _walk_values(value)


def test_approve_resolves_packet_without_merge_or_push(tmp_path):
    packet_index, _feed, status = lifecycle.build_lifecycle_read_models(
        read_model_root=_fixture_root(tmp_path),
        generated_at=FIXED_NOW,
    )
    packet = _packets_by_id(packet_index)["review_packet:approve"]

    assert packet["status"] == "OPERATOR_REVIEW_RECORDED"
    assert packet["visible_by_default"] is False
    assert packet["completed"] is True
    assert packet["operator_decision_required"] is False
    assert packet["merge_performed"] is False
    assert packet["git_push_performed"] is False
    assert packet["business_action_performed"] is False
    assert "review_packet:approve" in packet_index["completed_review_packet_ids"]
    assert status["machine_proof"]["merge_performed"] is False
    assert status["machine_proof"]["git_push_performed"] is False


def test_rework_keeps_packet_visible(tmp_path):
    packet_index, _feed, _status = lifecycle.build_lifecycle_read_models(
        read_model_root=_fixture_root(tmp_path),
        generated_at=FIXED_NOW,
    )
    packet = _packets_by_id(packet_index)["review_packet:rework"]

    assert packet["status"] == "REWORK_REQUIRED"
    assert packet["visible_by_default"] is True
    assert packet["completed"] is False
    assert packet["operator_decision_required"] is True
    assert packet["next_safe_action"] == "Review the rework request before assigning any follow-up."
    assert "review_packet:rework" in packet_index["open_review_packet_ids"]


def test_informational_closes_packet(tmp_path):
    packet_index, _feed, _status = lifecycle.build_lifecycle_read_models(
        read_model_root=_fixture_root(tmp_path),
        generated_at=FIXED_NOW,
    )
    packet = _packets_by_id(packet_index)["review_packet:info"]

    assert packet["status"] == "INFORMATIONAL_REVIEW_CLOSED"
    assert packet["visible_by_default"] is False
    assert packet["completed"] is True
    assert packet["operator_decision_required"] is False
    assert packet["next_safe_action"] == "No action needed."


def test_activity_feed_records_decision_post_and_updates_review_post(tmp_path):
    _packet_index, feed, _status = lifecycle.build_lifecycle_read_models(
        read_model_root=_fixture_root(tmp_path),
        generated_at=FIXED_NOW,
    )
    decision_posts = [
        post for post in feed["posts"] if post.get("source_kind") == "workroom_review_decision_lifecycle"
    ]
    rework_review_posts = [
        post
        for post in feed["posts"]
        if post.get("post_type") == "review_packet" and post.get("review_packet_id") == "review_packet:rework"
    ]

    assert len(decision_posts) == 3
    assert {post["review_packet_id"] for post in decision_posts} == {
        "review_packet:approve",
        "review_packet:rework",
        "review_packet:info",
    }
    assert all(post["speaker_ref"] == "chief" for post in decision_posts)
    assert all(post["proof_refs_collapsed"] is True for post in decision_posts)
    assert all(post["business_action_performed"] is False for post in decision_posts)
    assert rework_review_posts[0]["review_decision_status"] == "REWORK_REQUIRED"
    assert rework_review_posts[0]["visible_by_default"] is True


def test_export_json_parse_local_bridge_equal_and_unsafe_scan_clean(tmp_path):
    result = lifecycle.export_workroom_review_decision_lifecycle(
        read_model_root=_fixture_root(tmp_path),
        export_root=tmp_path / "read_models",
        bridge_export_root=tmp_path / "bridge",
        wiki_path=tmp_path / "wiki" / "Workroom Review Decision Lifecycle.md",
        generated_at=FIXED_NOW,
    )
    pairs = [
        ("packet_index_path", "bridge_packet_index_path"),
        ("activity_feed_path", "bridge_activity_feed_path"),
        ("lifecycle_status_path", "bridge_lifecycle_status_path"),
    ]
    payloads = []
    for local_key, bridge_key in pairs:
        local = json.loads(Path(result[local_key]).read_text(encoding="utf-8"))
        bridge = json.loads(Path(result[bridge_key]).read_text(encoding="utf-8"))
        assert local == bridge
        payloads.append(local)

    assert payloads[0]["packet_counts_by_status"] == {
        "INFORMATIONAL_REVIEW_CLOSED": 1,
        "OPERATOR_REVIEW_RECORDED": 1,
        "REWORK_REQUIRED": 1,
    }
    assert payloads[1]["machine_proof"]["new_business_truth_created"] is False
    assert payloads[2]["status"] == lifecycle.LIFECYCLE_STATUS
    assert Path(result["wiki_path"]).exists()

    unsafe_keys = {
        "merge_allowed",
        "git_push_allowed",
        "worker_spawn_allowed",
        "child_agent_run_allowed",
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
        "business_action_allowed",
        "sent",
        "paid",
        "merge_performed",
        "git_push_performed",
        "worker_spawn_performed",
        "business_action_performed",
        "business_state_mutation_performed",
        "new_business_truth_created",
    }
    violations = [
        (key, value)
        for payload in payloads
        for key, value in _walk_values(payload)
        if key in unsafe_keys and value is True
    ]
    assert violations == []
