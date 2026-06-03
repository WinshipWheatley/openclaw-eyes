import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import workroom_wip_limits as wip


FIXED_NOW = "2026-06-03T23:30:00+00:00"


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _fixture_root(
    tmp_path: Path,
    *,
    packets: list[dict] | None = None,
    approvals: list[dict] | None = None,
    dead_letters: list[dict] | None = None,
) -> Path:
    root = tmp_path / "generated" / "read_models"
    _write_json(root / "openclaw_workroom_activity_feed.json", {"status": "OPENCLAW_WORKROOM_ACTIVITY_FEED_READY"})
    _write_json(root / "workroom_review_packet_index.json", {"status": "WORKROOM_REVIEW_PACKET_INDEX_READY", "packets": packets or []})
    _write_json(root / "approval_request_queue.json", {"status": "APPROVAL_REQUEST_QUEUE_READY", "approval_requests": approvals or []})
    _write_json(root / "dead_letter_queue.json", {"status": "DEAD_LETTER_QUEUE_READY", "dead_letters": dead_letters or []})
    _write_json(
        root / "track_a_workroom_backbone_status.json",
        {
            "status": "TRACK_A_WORKROOM_BACKBONE_READY",
            "phases": [
                {
                    "phase": "operator_next_decision_workrooms",
                    "status": "OPERATOR_NEXT_DECISION_WORKROOMS_READY",
                }
            ],
        },
    )
    return root


def _packet(channel_ref: str, packet_id: str, *, completed: bool = False) -> dict:
    return {
        "review_packet_id": packet_id,
        "channel_ref": channel_ref,
        "status": "REVIEW_PACKET_READY" if not completed else "OPERATOR_REVIEW_RECORDED",
        "completed": completed,
        "operator_decision_required": not completed,
        "business_action_performed": False,
        "git_push_performed": False,
    }


def _approval(channel_ref: str, approval_id: str, *, gate_ref: str = "workroom_review_rework") -> dict:
    return {
        "approval_request_id": approval_id,
        "channel_ref": channel_ref,
        "gate_ref": gate_ref,
        "requested_action": "request_review_packet_rework",
        "status": "pending",
        "plain_summary": "Approval pending.",
        "forbidden_options": ["run_worker", "spawn_worker", "push_git"],
        "business_action_performed": False,
    }


def _dead_letter(channel_ref: str, dead_letter_id: str) -> dict:
    return {
        "dead_letter_id": dead_letter_id,
        "channel_ref": channel_ref,
        "failure_kind": "malformed_request",
        "plain_summary": "Malformed request.",
        "raw_body_stored": False,
    }


def _channel(payload: dict, channel_ref: str) -> dict:
    matches = [row for row in payload["channels"] if row["channel_ref"] == channel_ref]
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


def test_multiple_review_packets_create_pileup_risk(tmp_path):
    root = _fixture_root(
        tmp_path,
        packets=[
            _packet("build_openclaw_backend", "review_packet:one"),
            _packet("build_openclaw_backend", "review_packet:two"),
        ],
    )

    read_model = wip.build_read_model(read_model_root=root, generated_at=FIXED_NOW)
    row = _channel(read_model, "build_openclaw_backend")

    assert row["active_packet_count"] == 2
    assert row["review_packet_count"] == 2
    assert row["wip_status"] == "pileup_risk"
    assert row["stage_new_work_allowed"] is False
    assert "finishing review" in row["recommended_action"]


def test_pending_approvals_block_more_staging(tmp_path):
    root = _fixture_root(
        tmp_path,
        approvals=[_approval("build_openclaw_backend", "approval_request:one")],
    )

    read_model = wip.build_read_model(read_model_root=root, generated_at=FIXED_NOW)
    row = _channel(read_model, "build_openclaw_backend")

    assert row["pending_approval_count"] == 1
    assert row["wip_status"] == "pileup_risk"
    assert row["stage_new_work_allowed"] is False
    assert "pending approvals" in row["recommended_action"]


def test_quiet_channel_remains_clear(tmp_path):
    root = _fixture_root(
        tmp_path,
        packets=[_packet("build_mission_control_mac", "review_packet:done", completed=True)],
    )

    read_model = wip.build_read_model(read_model_root=root, generated_at=FIXED_NOW)
    row = _channel(read_model, "build_mission_control_mac")

    assert row["active_packet_count"] == 0
    assert row["review_packet_count"] == 1
    assert row["pending_approval_count"] == 0
    assert row["dead_letter_count"] == 0
    assert row["wip_status"] == "clear"
    assert row["stage_new_work_allowed"] is True


def test_protected_gate_blocks_action(tmp_path):
    root = _fixture_root(
        tmp_path,
        approvals=[
            _approval(
                "finance_capital_hilton",
                "approval_request:send",
                gate_ref="email_send",
            )
        ],
    )

    read_model = wip.build_read_model(read_model_root=root, generated_at=FIXED_NOW)
    row = _channel(read_model, "finance_capital_hilton")

    assert row["protected_gate_count"] == 1
    assert row["protected_gate_refs"] == ["email_send"]
    assert row["wip_status"] == "blocked"
    assert row["stage_new_work_allowed"] is False
    assert "protected Guardian gate" in row["recommended_action"]
    assert read_model["machine_proof"]["protected_gates_block_escalation"] is True


def test_dead_letter_backlog_raises_attention(tmp_path):
    root = _fixture_root(
        tmp_path,
        dead_letters=[
            _dead_letter("operations_mission_control", "dead_letter:one"),
        ],
    )

    read_model = wip.build_read_model(read_model_root=root, generated_at=FIXED_NOW)
    row = _channel(read_model, "operations_mission_control")

    assert row["dead_letter_count"] == 1
    assert row["wip_status"] == "watch"
    assert row["stage_new_work_allowed"] is False
    assert "dead-letter backlog" in row["recommended_action"]


def test_no_unsafe_authority_grants(tmp_path):
    read_model = wip.build_read_model(read_model_root=_fixture_root(tmp_path), generated_at=FIXED_NOW)

    assert wip._unsafe_true_grants(read_model) == []
    assert not [key for key, value in _walk_values(read_model) if key in wip.UNSAFE_TRUE_KEYS and value is True]
    assert read_model["machine_proof"]["worker_spawn_performed"] is False
    assert read_model["machine_proof"]["email_send_performed"] is False
    assert read_model["machine_proof"]["git_push_performed"] is False


def test_export_writes_local_bridge_equal_and_wiki(tmp_path):
    result = wip.export_workroom_wip_limits(
        read_model_root=_fixture_root(tmp_path),
        export_root=tmp_path / "read_models",
        bridge_root=tmp_path / "bridge",
        wiki_path=tmp_path / "wiki" / "Workroom WIP Limits.md",
        generated_at=FIXED_NOW,
    )

    local = json.loads(Path(result["read_model_path"]).read_text(encoding="utf-8"))
    bridge = json.loads(Path(result["bridge_read_model_path"]).read_text(encoding="utf-8"))

    assert local == bridge
    assert local["status"] == wip.READY_STATUS
    assert Path(result["wiki_path"]).exists()
    assert "No workers or agents are run." in Path(result["wiki_path"]).read_text(encoding="utf-8")
