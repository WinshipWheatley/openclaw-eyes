import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import agent_handoff_event_consumer as consumer


FIXED_NOW = "2026-06-03T21:00:00+00:00"


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _fixture_root(tmp_path: Path) -> Path:
    root = tmp_path / "generated" / "read_models"
    _write_json(
        root / "agent_handoff_registry.json",
        {
            "status": "AGENT_HANDOFF_REGISTRY_READY",
            "handoffs": [
                {
                    "handoff_ref": "chief_to_pc_codex_backend_implementation",
                    "from_agent": "chief",
                    "to_agent_or_worker": "pc_codex",
                    "channel_ref": "build_openclaw_backend",
                    "package_type": "pc_codex_backend_worker_packet",
                    "requires_operator_approval": True,
                    "receipt_required": True,
                },
                {
                    "handoff_ref": "hermes_to_chief_build_packet",
                    "from_agent": "hermes",
                    "to_agent_or_worker": "chief",
                    "channel_ref": "operations_chief_workboard",
                    "package_type": "architecture_to_build_packet",
                    "requires_operator_approval": True,
                    "receipt_required": True,
                },
            ],
        },
    )
    _write_json(
        root / "openclaw_workroom_registry.json",
        {
            "status": "OPENCLAW_WORKROOM_REGISTRY_READY",
            "channels": [
                {
                    "channel_ref": "build_openclaw_backend",
                    "world_ref": "build",
                    "thread_ref": "workroom:build_openclaw_backend:main",
                    "primary_agent": "chief",
                },
                {
                    "channel_ref": "operations_chief_workboard",
                    "world_ref": "operations",
                    "thread_ref": "workroom:operations_chief_workboard:main",
                    "primary_agent": "chief",
                },
            ],
        },
    )
    _write_json(root / "package_event_index.json", {"status": "PACKAGE_EVENT_INDEX_READY", "events": []})
    _write_json(
        root / "openclaw_workroom_activity_feed.json",
        {
            "schema_version": "openclaw_workroom_activity_feed_v0",
            "read_model_id": "openclaw_workroom_activity_feed",
            "status": "OPENCLAW_WORKROOM_ACTIVITY_FEED_READY",
            "generated_at": FIXED_NOW,
            "post_count": 1,
            "posts": [
                {
                    "post_id": "workroom_post:existing",
                    "channel_ref": "operations_chief_workboard",
                    "timestamp": "2026-06-03T20:00:00+00:00",
                    "speaker_ref": "chief",
                    "post_type": "status",
                    "headline": "Existing workroom post",
                    "plain_summary": "Existing feed entry remains intact.",
                    "proof_refs": ["generated/read_models/openclaw_workroom_activity_feed.json"],
                    "business_action_performed": False,
                }
            ],
            "source_refs": ["generated/read_models/package_event_index.json"],
            "rules": [],
            "machine_proof": {"business_action_performed": False},
        },
    )
    return root


def _request_payload(**overrides: object) -> dict:
    payload = {
        "request_type": consumer.REQUEST_TYPE,
        "source_surface": "mission_control",
        "request_id": "handoff_fixture",
        "from_agent": "chief",
        "to_agent_or_worker": "pc_codex",
        "channel_ref": "build_openclaw_backend",
        "handoff_ref": "chief_to_pc_codex_backend_implementation",
        "reason": "Backend implementation packet is ready to stage for review.",
        "package_type": "pc_codex_backend_worker_packet",
        "authority_boundary": {
            "email_send_allowed": False,
            "ledger_posting_allowed": False,
            "browser_access_allowed": False,
            "gmail_allowed": False,
            "coupa_allowed": False,
            "portal_submit_allowed": False,
            "worker_spawn_allowed": False,
            "tool_execution_allowed": False,
            "sent": False,
            "paid": False,
        },
    }
    payload.update(overrides)
    return payload


def _consume(tmp_path: Path, request: dict) -> consumer.AgentHandoffEventResult:
    return consumer.consume_agent_handoff_event_request(
        request,
        source_request_filename="mission_control_agent_handoff_event_request_fixture.json",
        generated_at=FIXED_NOW,
        read_model_root=_fixture_root(tmp_path),
        export_root=tmp_path / "read_models",
        bridge_export_root=tmp_path / "bridge",
        wiki_path=tmp_path / "wiki" / "Agent Handoff Event Consumer.md",
    )


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
        "tool_execution_allowed",
        "external_llm_allowed",
        "live_provider_allowed",
        "git_push_allowed",
        "sent",
        "paid",
        "worker_execution_performed",
        "tool_execution_performed",
        "business_action_performed",
        "email_send_performed",
        "ledger_mutation_performed",
        "git_push_performed",
    }
    assert not [key for key, value in _walk_values(payload) if key in unsafe_keys and value is True]


def test_handoff_event_records_receipt_only_and_posts_activity(tmp_path):
    result = _consume(tmp_path, _request_payload())

    assert result.status == "RECORDED"
    assert result.event is not None
    assert result.receipt["status"] == "HANDOFF_EVENT_RECORDED"
    assert result.receipt["event_recorded"] is True
    assert result.receipt["speaker_ref"] == "chief"
    assert result.receipt["handoff_registry_match"]["handoff_ref"] == "chief_to_pc_codex_backend_implementation"
    assert result.receipt["workroom_channel"]["channel_ref"] == "build_openclaw_backend"
    assert result.receipt["downstream_worker_assigned"] is False
    assert result.receipt["worker_execution_performed"] is False
    assert result.receipt["tool_execution_performed"] is False
    assert result.receipt["business_action_performed"] is False
    _assert_no_unsafe_grants(result.receipt)

    status = json.loads((tmp_path / "read_models" / "agent_handoff_event_status.json").read_text(encoding="utf-8"))
    feed = json.loads((tmp_path / "read_models" / "openclaw_workroom_activity_feed.json").read_text(encoding="utf-8"))
    assert status["status"] == "AGENT_HANDOFF_EVENT_CONSUMER_READY"
    assert status["event_count"] == 1
    assert feed["post_count"] == 2
    handoff_posts = [post for post in feed["posts"] if post.get("source_kind") == "agent_handoff_event"]
    assert len(handoff_posts) == 1
    assert handoff_posts[0]["channel_ref"] == "build_openclaw_backend"
    assert handoff_posts[0]["target_world_ref"] == "build"
    assert handoff_posts[0]["target_thread_ref"] == "workroom:build_openclaw_backend:main"
    assert handoff_posts[0]["business_action_performed"] is False
    assert handoff_posts[0]["worker_execution_performed"] is False


def test_unsafe_authority_attempt_routes_guardian_and_does_not_post(tmp_path):
    request = _request_payload(
        request_id="unsafe_handoff_fixture",
        authority_boundary={
            "email_send_allowed": False,
            "ledger_posting_allowed": False,
            "browser_access_allowed": False,
            "gmail_allowed": False,
            "coupa_allowed": False,
            "portal_submit_allowed": False,
            "worker_spawn_allowed": True,
            "sent": False,
            "paid": False,
        },
    )

    result = _consume(tmp_path, request)

    assert result.status == "BLOCKED"
    assert result.event is None
    assert result.receipt["status"] == "BLOCKED_UNSAFE_AUTHORITY"
    assert result.receipt["event_recorded"] is False
    assert result.receipt["speaker_ref"] == "guardian"
    assert "unsafe_true_grant:worker_spawn_allowed" in result.blockers
    assert result.receipt["worker_execution_performed"] is False
    assert result.receipt["business_action_performed"] is False

    feed = json.loads((tmp_path / "read_models" / "openclaw_workroom_activity_feed.json").read_text(encoding="utf-8"))
    assert feed["post_count"] == 1
    assert not [post for post in feed["posts"] if post.get("source_kind") == "agent_handoff_event"]


def test_unknown_handoff_or_channel_blocks_without_execution(tmp_path):
    result = _consume(
        tmp_path,
        _request_payload(
            request_id="unknown_handoff_fixture",
            handoff_ref="missing_handoff",
            channel_ref="missing_channel",
        ),
    )

    assert result.status == "BLOCKED"
    assert result.receipt["status"] == "BLOCKED_INVALID_HANDOFF"
    assert result.receipt["speaker_ref"] == "chief"
    assert "unknown_handoff_ref" in result.blockers
    assert "unknown_channel_ref" in result.blockers
    assert result.receipt["worker_execution_performed"] is False
    assert result.receipt["tool_execution_performed"] is False
    assert result.receipt["business_action_performed"] is False
    _assert_no_unsafe_grants(result.receipt)


def test_bridge_status_and_activity_feed_equal_and_wiki_written(tmp_path):
    result = _consume(tmp_path, _request_payload())

    status_local = json.loads(Path(result.receipt["read_model_paths"]["local_status_path"]).read_text(encoding="utf-8"))
    status_bridge = json.loads(Path(result.receipt["read_model_paths"]["bridge_status_path"]).read_text(encoding="utf-8"))
    feed_local = json.loads(Path(result.receipt["read_model_paths"]["local_activity_feed_path"]).read_text(encoding="utf-8"))
    feed_bridge = json.loads(Path(result.receipt["read_model_paths"]["bridge_activity_feed_path"]).read_text(encoding="utf-8"))
    wiki = Path(result.receipt["read_model_paths"]["wiki_path"])

    assert status_local == status_bridge
    assert feed_local == feed_bridge
    assert status_local["machine_proof"]["worker_execution_performed"] is False
    assert feed_local["machine_proof"]["worker_execution_performed"] is False
    assert wiki.exists()
    assert "No worker is assigned or executed." in wiki.read_text(encoding="utf-8")
    _assert_no_unsafe_grants(status_local)
    _assert_no_unsafe_grants(feed_local)
