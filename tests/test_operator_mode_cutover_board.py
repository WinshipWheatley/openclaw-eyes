import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import operator_mode_cutover_board as board


FIXED_NOW = "2026-06-03T15:00:00+00:00"


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _fixture_root(tmp_path: Path) -> Path:
    root = tmp_path / "generated" / "read_models"
    _write_json(root / "lane_graduation_criteria.json", {"status": "LANE_GRADUATION_CRITERIA_READY"})
    _write_json(root / "operator_next_decision.json", {"status": "READY"})
    _write_json(root / "automation_permission_registry.json", {"status": "AUTOMATION_PERMISSION_REGISTRY_READY"})
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


def test_cutover_board_records_ready_assist_developer_and_blocked_workflows(tmp_path):
    read_model = board.build_read_model(read_model_root=_fixture_root(tmp_path), generated_at=FIXED_NOW)

    assert read_model["status"] == "OPERATOR_MODE_CUTOVER_BOARD_READY"
    statuses = {item["workflow_ref"]: item["cutover_status"] for item in read_model["workflows"]}
    assert statuses["helm_composer"] == "operator_ready"
    assert statuses["system_question_answering"] == "operator_ready"
    assert statuses["st_annes_work_log_intake_review"] in {"operator_ready", "near_operator_ready"}
    assert statuses["capital_hilton_invoice"] == "operator_assist_ready"
    assert statuses["st_annes_invoice_generation"] == "developer_mode"
    assert statuses["coupa_unattended_submit"] == "blocked"
    assert statuses["ledger_posting"] == "blocked"
    assert statuses["excel_source_workbook_mutation"] == "blocked"
    assert all(item["business_action_allowed"] is False for item in read_model["workflows"])
    _assert_no_unsafe_true_grants(read_model)


def test_blocked_items_have_guardian_owned_next_action(tmp_path):
    read_model = board.build_read_model(read_model_root=_fixture_root(tmp_path), generated_at=FIXED_NOW)
    blocked = [item for item in read_model["workflows"] if item["cutover_status"] == "blocked"]

    assert blocked
    assert all(item["owner_speaker_ref"] == "guardian" for item in blocked)
    assert all("blocked" in item["plain_summary"].lower() for item in blocked)


def test_missing_lane_criteria_precondition_marks_not_ready(tmp_path):
    root = _fixture_root(tmp_path)
    _write_json(root / "lane_graduation_criteria.json", {"status": "NOT_READY"})

    read_model = board.build_read_model(read_model_root=root, generated_at=FIXED_NOW)

    assert read_model["status"] == "OPERATOR_MODE_CUTOVER_BOARD_NOT_READY"
    assert read_model["machine_proof"]["preconditions_ready"] is False
    _assert_no_unsafe_true_grants(read_model)


def test_export_writes_local_bridge_equal_and_wiki(tmp_path):
    result = board.export_operator_mode_cutover_board(
        read_model_root=_fixture_root(tmp_path),
        export_root=tmp_path / "read_models",
        bridge_export_root=tmp_path / "bridge",
        wiki_path=tmp_path / "wiki" / "Operator Mode Cutover Board.md",
        generated_at=FIXED_NOW,
    )

    local = json.loads(Path(result["read_model_path"]).read_text(encoding="utf-8"))
    bridge = json.loads(Path(result["bridge_read_model_path"]).read_text(encoding="utf-8"))
    wiki = Path(result["wiki_path"]).read_text(encoding="utf-8")

    assert local == bridge
    assert "operator use" in wiki
    assert result["status"] == "OPERATOR_MODE_CUTOVER_BOARD_READY"
    _assert_no_unsafe_true_grants(local)
