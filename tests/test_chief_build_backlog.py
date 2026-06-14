import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import chief_build_backlog as backlog


FIXED_NOW = "2026-06-03T23:00:00+00:00"


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _fixture_root(tmp_path: Path) -> Path:
    root = tmp_path / "generated" / "read_models"
    _write_json(root / "worker_package_staging_status.json", {"status": "WORKER_PACKAGE_STAGING_READY"})
    _write_json(root / "overnight_workboard.json", {"status": "READY_FOR_OPERATOR_REVIEW", "chief_work_packets": []})
    _write_json(root / "openclaw_workroom_registry.json", {"status": "OPENCLAW_WORKROOM_REGISTRY_READY"})
    _write_json(root / "package_event_index.json", {"status": "PACKAGE_EVENT_INDEX_READY"})
    _write_json(root / "workroom_review_packet_index.json", {"status": "WORKROOM_REVIEW_PACKET_INDEX_READY"})
    _write_json(root / "helm_actionability_surface.json", {"status": "HELM_ACTIONABILITY_SURFACE_READY"})
    _write_json(root / "sqlite_consolidation_plan.json", {"status": "SQLITE_CONSOLIDATION_PLAN_READY"})
    _write_json(root / "canonical_state_map.json", {"status": "CANONICAL_STATE_MAP_READY"})
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
        "worker_execution_allowed",
        "tool_execution_allowed",
        "external_llm_allowed",
        "live_provider_allowed",
        "local_model_runtime_allowed",
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


def test_builds_bounded_chief_backlog_items(tmp_path):
    read_model = backlog.build_read_model(read_model_root=_fixture_root(tmp_path), generated_at=FIXED_NOW)

    assert read_model["status"] == "CHIEF_BUILD_BACKLOG_READY"
    assert read_model["backlog_count"] >= 7
    packet_refs = {item["packet_ref"] for item in read_model["backlog_items"]}
    assert {
        "chief_backlog:mac_helm_action_desk_hierarchy",
        "chief_backlog:mac_workroom_review_decision_controls",
        "chief_backlog:pc_sqlite_unknown_classification_packets",
        "chief_backlog:pc_workroom_system_questions",
        "chief_backlog:pc_telegram_dry_run_workroom_integration",
        "chief_backlog:pc_tts_profile_smoke_harness",
        "chief_backlog:mac_homecoming_brief_tts_preview",
    }.issubset(packet_refs)

    for item in read_model["backlog_items"]:
        assert item["owner_agent"] == "chief"
        assert item["recommended_worker"] in {"pc_codex", "mac_codex"}
        assert item["operator_approval_required"] is True
        assert item["business_action_allowed"] is False
        assert item["worker_spawn_performed"] is False
        assert item["business_action_performed"] is False
        assert "send_email" in item["blocked_actions"]
        assert "push_git" in item["blocked_actions"]
        assert item["next_safe_action"]
    _assert_no_unsafe_grants(read_model)


def test_overnight_workboard_ready_for_review_satisfies_precondition(tmp_path):
    read_model = backlog.build_read_model(read_model_root=_fixture_root(tmp_path), generated_at=FIXED_NOW)

    workboard = [
        item
        for item in read_model["preconditions"]
        if item["precondition_ref"] == "overnight_workboard"
    ][0]
    assert workboard["observed_status"] == "READY_FOR_OPERATOR_REVIEW"
    assert workboard["ready"] is True
    assert "OVERNIGHT_WORKBOARD_READY" in workboard["accepted_statuses"]


def test_missing_required_precondition_marks_not_ready(tmp_path):
    root = _fixture_root(tmp_path)
    _write_json(root / "worker_package_staging_status.json", {"status": "NOT_READY"})

    read_model = backlog.build_read_model(read_model_root=root, generated_at=FIXED_NOW)

    assert read_model["status"] == "CHIEF_BUILD_BACKLOG_NOT_READY"
    assert read_model["machine_proof"]["preconditions_ready"] is False
    _assert_no_unsafe_grants(read_model)


def test_export_writes_local_bridge_equal_and_wiki(tmp_path):
    result = backlog.export_chief_build_backlog(
        read_model_root=_fixture_root(tmp_path),
        export_root=tmp_path / "read_models",
        bridge_export_root=tmp_path / "bridge",
        wiki_path=tmp_path / "wiki" / "Chief Build Backlog.md",
        generated_at=FIXED_NOW,
    )

    local = json.loads(Path(result["read_model_path"]).read_text(encoding="utf-8"))
    bridge = json.loads(Path(result["bridge_read_model_path"]).read_text(encoding="utf-8"))
    wiki = Path(result["wiki_path"])

    assert local == bridge
    assert result["backlog_count"] == str(local["backlog_count"])
    assert wiki.exists()
    assert "Planning only." in wiki.read_text(encoding="utf-8")
    _assert_no_unsafe_grants(local)
