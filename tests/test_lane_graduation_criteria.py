import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import lane_graduation_criteria as criteria


FIXED_NOW = "2026-06-03T14:45:00+00:00"


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _fixture_root(tmp_path: Path) -> Path:
    root = tmp_path / "generated" / "read_models"
    _write_json(root / "package_event_index.json", {"status": "PACKAGE_EVENT_INDEX_READY"})
    _write_json(root / "canonical_state_map.json", {"status": "CANONICAL_STATE_MAP_READY"})
    _write_json(root / "approval_request_queue.json", {"status": "APPROVAL_REQUEST_QUEUE_READY"})
    _write_json(root / "evidence_confidence_scoring.json", {"status": "EVIDENCE_CONFIDENCE_SCORING_READY"})
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
        "business_action_performed",
        "sent",
        "paid",
    }
    assert not [key for key, value in _walk_values(payload) if key in unsafe_keys and value is True]


def test_lane_graduation_criteria_include_required_checks(tmp_path):
    read_model = criteria.build_read_model(read_model_root=_fixture_root(tmp_path), generated_at=FIXED_NOW)

    assert read_model["status"] == "LANE_GRADUATION_CRITERIA_READY"
    criterion_refs = {criterion["criterion_ref"] for criterion in read_model["criteria"]}
    assert {
        "read_model_exists",
        "canonical_truth_source_known",
        "package_path_works",
        "operator_display_exists",
        "proof_collapsed",
        "permissions_known",
        "unsafe_actions_gated",
        "test_smoke_hygiene_handled",
        "stale_surface_sentinel_clean",
        "review_packet_path_exists_if_worker_needed",
        "manual_workaround_declared",
    } == criterion_refs
    _assert_no_unsafe_true_grants(read_model)


def test_initial_lane_statuses_are_recorded(tmp_path):
    read_model = criteria.build_read_model(read_model_root=_fixture_root(tmp_path), generated_at=FIXED_NOW)
    lanes = {lane["lane_ref"]: lane for lane in read_model["lanes"]}

    assert lanes["st_annes_work_log_intake"]["graduation_status"] in {"operator_ready", "near_operator_ready"}
    assert lanes["st_annes_month_end_invoice"]["graduation_status"] == "developer_mode"
    assert lanes["capital_hilton_invoice"]["graduation_status"] == "operator_assist_ready"
    assert lanes["capital_hilton_proposal"]["graduation_status"] == "operator_assist_ready"
    assert lanes["live_arts_invoice_pdf_approval"]["graduation_status"] == "proven_artifact_path"
    assert all(lane["business_action_allowed"] is False for lane in read_model["lanes"])


def test_missing_approval_queue_precondition_marks_not_ready(tmp_path):
    root = _fixture_root(tmp_path)
    _write_json(root / "approval_request_queue.json", {"status": "NOT_READY"})

    read_model = criteria.build_read_model(read_model_root=root, generated_at=FIXED_NOW)

    assert read_model["status"] == "LANE_GRADUATION_CRITERIA_NOT_READY"
    assert read_model["machine_proof"]["preconditions_ready"] is False
    _assert_no_unsafe_true_grants(read_model)


def test_export_writes_local_bridge_equal_and_wiki(tmp_path):
    result = criteria.export_lane_graduation_criteria(
        read_model_root=_fixture_root(tmp_path),
        export_root=tmp_path / "read_models",
        bridge_export_root=tmp_path / "bridge",
        wiki_path=tmp_path / "wiki" / "Lane Graduation Criteria.md",
        generated_at=FIXED_NOW,
    )

    local = json.loads(Path(result["read_model_path"]).read_text(encoding="utf-8"))
    bridge = json.loads(Path(result["bridge_read_model_path"]).read_text(encoding="utf-8"))
    wiki = Path(result["wiki_path"]).read_text(encoding="utf-8")

    assert local == bridge
    assert "developer mode to operator mode" in wiki
    assert result["status"] == "LANE_GRADUATION_CRITERIA_READY"
    _assert_no_unsafe_true_grants(local)
