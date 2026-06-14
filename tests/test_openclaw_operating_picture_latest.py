import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import openclaw_operating_picture_latest as picture


FIXED_NOW = "2026-06-03T16:00:00+00:00"


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _fixture_root(tmp_path: Path) -> Path:
    root = tmp_path / "generated" / "read_models"
    _write_json(root / "track_a_workroom_backbone_status.json", {"status": "TRACK_A_WORKROOM_BACKBONE_READY"})
    _write_json(root / "track_b_governance_memory_cutover_status.json", {"status": "TRACK_B_GOVERNANCE_MEMORY_CUTOVER_READY"})
    _write_json(root / "openclaw_workroom_registry.json", {"status": "OPENCLAW_WORKROOM_REGISTRY_READY", "workrooms": []})
    _write_json(root / "openclaw_workroom_activity_feed.json", {"status": "OPENCLAW_WORKROOM_ACTIVITY_FEED_READY", "activity_count": 4})
    _write_json(
        root / "workroom_review_packet_index.json",
        {
            "status": "WORKROOM_REVIEW_PACKET_INDEX_READY",
            "packets": [
                {
                    "review_packet_id": "review_packet:done",
                    "human_summary": "MAC_CODEX returned UI work.",
                    "operator_decision_required": False,
                    "completed": True,
                    "status": "OPERATOR_REVIEW_RECORDED",
                    "channel_ref": "build_mission_control_mac",
                },
                {
                    "review_packet_id": "review_packet:active",
                    "human_summary": "PC_CODEX changed backend code and returned local validation proof for operator review.",
                    "operator_decision_required": True,
                    "completed": False,
                    "status": "REVIEW_PACKET_READY",
                    "channel_ref": "build_openclaw_backend",
                },
            ],
        },
    )
    _write_json(root / "workroom_review_decision_status.json", {"status": "WORKROOM_REVIEW_DECISION_CONSUMER_READY"})
    _write_json(root / "chief_build_backlog.json", {"status": "CHIEF_BUILD_BACKLOG_READY", "backlog_count": 7, "backlog_items": [{"packet_ref": "chief_backlog:mac", "goal": "Render Workroom review controls.", "recommended_worker": "mac_codex"}]})
    _write_json(
        root / "operator_next_decision.json",
        {
            "status": "READY",
            "headline": "Review Workroom packet",
            "plain_summary": "PC_CODEX changed backend code and returned local validation proof for operator review.",
            "action_label": "Open review packet",
            "action_type": "navigate",
            "target_world_ref": "build",
            "target_thread_ref": "build_openclaw_backend",
            "speaker_ref": "chief",
        },
    )
    _write_json(
        root / "operator_mode_cutover_board.json",
        {
            "status": "OPERATOR_MODE_CUTOVER_BOARD_READY",
            "workflows": [
                {"workflow_ref": "helm_composer", "display_name": "Helm Composer", "cutover_status": "operator_ready", "plain_summary": "Ready.", "owner_speaker_ref": "openclaw"},
                {"workflow_ref": "system_question_answering", "display_name": "System question answering", "cutover_status": "operator_ready", "plain_summary": "Ready.", "owner_speaker_ref": "hermes"},
                {"workflow_ref": "capital_hilton_invoice", "display_name": "Capital Hilton invoice", "cutover_status": "operator_assist_ready", "plain_summary": "Provider gated.", "owner_speaker_ref": "chief"},
                {"workflow_ref": "st_annes_invoice_generation", "display_name": "St. Anne's invoice generation", "cutover_status": "developer_mode", "plain_summary": "Developer mode.", "owner_speaker_ref": "chief"},
                {"workflow_ref": "ledger_posting", "display_name": "Ledger posting", "cutover_status": "blocked", "plain_summary": "Blocked.", "owner_speaker_ref": "guardian"},
            ],
        },
    )
    _write_json(root / "approval_request_queue.json", {"status": "APPROVAL_REQUEST_QUEUE_READY", "approval_requests": [{"requested_action": "approve_email_draft_send", "status": "pending", "owner_speaker_ref": "guardian", "plain_summary": "Approve draft send."}]})
    _write_json(root / "gate_decision_ledger.json", {"status": "GATE_DECISION_LEDGER_READY", "decisions": [{"gate_ref": "send_email", "decision": "approval_required"}, {"gate_ref": "ledger_post", "decision": "blocked"}]})
    _write_json(root / "dead_letter_queue.json", {"status": "DEAD_LETTER_QUEUE_READY", "dead_letters": [{"failure_kind": "malformed_request", "plain_summary": "Malformed request."}]})
    _write_json(root / "artifact_lineage_registry.json", {"status": "ARTIFACT_LINEAGE_REGISTRY_READY", "artifact_count": 3})
    _write_json(root / "evidence_confidence_scoring.json", {"status": "EVIDENCE_CONFIDENCE_SCORING_READY", "facts": [{"confidence_class": "proven_receipt"}, {"confidence_class": "unknown"}]})
    _write_json(root / "operator_memory_distillation.json", {"status": "OPERATOR_MEMORY_DISTILLATION_READY", "memory_candidates": [{"category": "workflow_lessons"}]})
    _write_json(root / "memory_promotion_gate.json", {"status": "MEMORY_PROMOTION_GATE_READY", "promotion_entries": [{"memory_ref": "memory_candidate:1", "candidate_summary": "Proof should be collapsed.", "operator_approval_required": False}]})
    _write_json(root / "lane_graduation_criteria.json", {"status": "LANE_GRADUATION_CRITERIA_READY", "lanes": []})
    _write_json(root / "teamroom_e2e_smoke_plan.json", {"status": "TEAMROOM_E2E_SMOKE_PLAN_READY", "planning_only": True})
    _write_json(root / "backend_queue_recovery_status.json", {"status": "BACKEND_QUEUE_RECOVERY_READY"})
    return root


def _walk_values(payload):
    if isinstance(payload, dict):
        for key, value in payload.items():
            yield key, value
            yield from _walk_values(value)
    elif isinstance(payload, list):
        for value in payload:
            yield from _walk_values(value)


def _assert_no_unsafe_true_grants(payload: dict) -> None:
    unsafe_keys = {
        "email_send_allowed",
        "ledger_posting_allowed",
        "browser_access_allowed",
        "gmail_allowed",
        "coupa_allowed",
        "portal_submit_allowed",
        "worker_spawn_allowed",
        "business_action_performed",
        "sent",
        "paid",
    }
    assert not [key for key, value in _walk_values(payload) if key in unsafe_keys and value is True]


def test_operating_picture_has_required_sections_and_counts(tmp_path):
    payload = picture.build_operating_picture(read_model_root=_fixture_root(tmp_path), generated_at=FIXED_NOW)

    assert payload["status"] == "OPENCLAW_OPERATING_PICTURE_READY"
    required_sections = [
        "executive_summary",
        "operator_ready_workflows",
        "operator_assist_workflows",
        "developer_mode_workflows",
        "blocked_protected_workflows",
        "workrooms_status",
        "review_packets_needing_attention",
        "approval_requests_pending",
        "dead_letters_failures",
        "evidence_confidence_summary",
        "memory_candidates_needing_promotion",
        "current_next_safe_action",
        "can_run_while_winship_sleeps",
        "must_wait_for_explicit_approval",
        "recommended_next_build_lane",
    ]
    assert payload["section_order"] == required_sections
    assert payload["counts"]["operator_ready"] == 2
    assert payload["counts"]["operator_assist"] == 1
    assert payload["counts"]["developer_mode"] == 1
    assert payload["counts"]["blocked"] == 1
    assert payload["counts"]["pending_approvals"] == 1
    assert payload["counts"]["memory_candidates"] == 1
    _assert_no_unsafe_true_grants(payload)


def test_current_next_action_and_recommended_lane_are_human_readable(tmp_path):
    payload = picture.build_operating_picture(read_model_root=_fixture_root(tmp_path), generated_at=FIXED_NOW)

    assert payload["current_next_safe_action"]["headline"] == "Review Workroom packet"
    assert payload["current_next_safe_action"]["action_label"] == "Open review packet"
    assert payload["recommended_next_build_lane"]["lane_ref"] == "mac_helm_workroom_rendering"
    rendered_primary = json.dumps(
        {
            "summary": payload["executive_summary"],
            "next": payload["current_next_safe_action"],
            "mac": payload["what_mac_should_render_next"],
        }
    )
    assert "review_packet:" not in rendered_primary
    assert ".sqlite" not in rendered_primary.lower()


def test_missing_track_b_precondition_marks_not_ready(tmp_path):
    root = _fixture_root(tmp_path)
    _write_json(root / "track_b_governance_memory_cutover_status.json", {"status": "NOT_READY"})

    payload = picture.build_operating_picture(read_model_root=root, generated_at=FIXED_NOW)

    assert payload["status"] == "OPENCLAW_OPERATING_PICTURE_NOT_READY"
    assert payload["machine_proof"]["preconditions_ready"] is False
    _assert_no_unsafe_true_grants(payload)


def test_export_writes_local_bridge_equal_and_wiki(tmp_path):
    result = picture.export_operating_picture(
        read_model_root=_fixture_root(tmp_path),
        export_root=tmp_path / "read_models",
        bridge_export_root=tmp_path / "bridge",
        wiki_path=tmp_path / "wiki" / "OpenClaw Operating Picture Latest.md",
        generated_at=FIXED_NOW,
    )

    local = json.loads(Path(result["read_model_path"]).read_text(encoding="utf-8"))
    bridge = json.loads(Path(result["bridge_read_model_path"]).read_text(encoding="utf-8"))
    wiki = Path(result["wiki_path"]).read_text(encoding="utf-8")

    assert local == bridge
    assert "What is working" in wiki
    assert result["status"] == "OPENCLAW_OPERATING_PICTURE_READY"
    _assert_no_unsafe_true_grants(local)
