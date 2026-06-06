import ast
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import goldilocks_gate_calibration as calibration


FIXED_NOW = "2026-06-06T18:00:00+00:00"


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _fixture_root(tmp_path: Path) -> Path:
    root = tmp_path / "generated" / "read_models"
    for spec in calibration.PRECONDITIONS.values():
        _write_json(root / spec["filename"], {"status": spec["accepted_statuses"][0]})
    return root


def _build(tmp_path: Path) -> dict:
    return calibration.build_read_model(read_model_root=_fixture_root(tmp_path), generated_at=FIXED_NOW)


def _level(payload: dict, gate_ref: str) -> dict:
    matches = [level for level in payload["gate_levels"] if level["gate_ref"] == gate_ref]
    assert len(matches) == 1
    return matches[0]


def _scenario(payload: dict, scenario_id: str) -> dict:
    matches = [row for row in payload["scenarios"] if row["scenario_id"] == scenario_id]
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


def test_readback_never_mutates(tmp_path):
    payload = _build(tmp_path)
    readback = _level(payload, "readback")

    assert readback["level"] == 0
    assert "answer_from_existing_proof" in readback["allowed_capabilities"]
    assert "mutation" in readback["forbidden_capabilities"]
    assert "command_execution" in readback["forbidden_capabilities"]
    assert readback["authority_boundary"]["business_action_allowed"] is False


def test_plan_never_stages_package_unless_promoted(tmp_path):
    plan = _level(_build(tmp_path), "plan")

    assert "propose_plan" in plan["allowed_capabilities"]
    assert "stage_package" in plan["forbidden_capabilities"]
    assert "create_package_or_draft_artifact" in plan["forbidden_capabilities"]
    assert "stage_package" not in plan["allowed_capabilities"]


def test_safe_internal_work_cannot_send_submit_post_or_mark_paid(tmp_path):
    safe_internal = _level(_build(tmp_path), "safe_internal_work")

    for protected in ("send_email", "submit_portal", "post_ledger", "mark_paid"):
        assert protected in safe_internal["forbidden_capabilities"]
    assert "repo_inspect_edit_test" in safe_internal["allowed_capabilities"]
    assert "commit_after_validation_if_package_grants" in safe_internal["allowed_capabilities"]


def test_prepare_approval_can_produce_proof_package_but_not_execute(tmp_path):
    prepare = _level(_build(tmp_path), "prepare_approval")

    assert "fill_approval_package" in prepare["allowed_capabilities"]
    assert "queue_non_executing_approval_request" in prepare["allowed_capabilities"]
    assert "final_submit" in prepare["forbidden_capabilities"]
    assert "execute_approval_as_action" in prepare["forbidden_capabilities"]
    assert "no_execution_receipt" in prepare["required_receipt"]


def test_execute_after_approval_remains_future_gated(tmp_path):
    payload = _build(tmp_path)
    execute = _level(payload, "execute_after_approval")

    assert execute["level"] == 5
    assert execute["future_gated_only"] is True
    assert execute["currently_available"] is False
    assert payload["machine_proof"]["execute_after_approval_currently_available"] is False
    assert "current_execution_from_this_read_model" in execute["forbidden_capabilities"]


def test_codex_like_patch_allows_repo_work_but_push_blocked(tmp_path):
    scenario = _scenario(_build(tmp_path), "codex_like_code_patch_inside_repo")

    assert scenario["calibrated_gate_ref"] == "safe_internal_work"
    assert "inspect_repo" in scenario["allowed_now"]
    assert "edit_repo_files_in_package_scope" in scenario["allowed_now"]
    assert "run_focused_tests" in scenario["allowed_now"]
    assert "commit_after_validation_if_package_grants" in scenario["allowed_now"]
    assert "git_push" in scenario["blocked_now"]


def test_finance_payment_watch_blocks_ledger_and_paid(tmp_path):
    scenario = _scenario(_build(tmp_path), "finance_payment_watch")

    assert scenario["calibrated_gate_ref"] == "stage"
    assert "readback_payment_state_from_proof" in scenario["allowed_now"]
    assert "attach_payment_proof_reference" in scenario["allowed_now"]
    assert "stage_ledger_review_packet" in scenario["allowed_now"]
    assert "post_ledger" in scenario["blocked_now"]
    assert "mark_paid" in scenario["blocked_now"]


def test_unsafe_true_grant_scan_clean(tmp_path):
    payload = _build(tmp_path)

    assert calibration.unsafe_true_grants(payload) == []
    assert payload["machine_proof"]["unsafe_true_grants_absent"] is True
    assert not [
        key
        for key, value in _walk_values(payload)
        if key in calibration.UNSAFE_TRUE_KEYS and value is True
    ]


def test_export_writes_local_bridge_equal_and_wiki(tmp_path):
    result = calibration.export_goldilocks_gate_calibration(
        read_model_root=_fixture_root(tmp_path),
        export_root=tmp_path / "read_models",
        bridge_root=tmp_path / "bridge",
        wiki_path=tmp_path / "wiki" / "Goldilocks Gate Calibration.md",
        generated_at=FIXED_NOW,
    )

    local = json.loads(Path(result["read_model_path"]).read_text(encoding="utf-8"))
    bridge = json.loads(Path(result["bridge_read_model_path"]).read_text(encoding="utf-8"))
    wiki = Path(result["wiki_path"]).read_text(encoding="utf-8")

    assert local == bridge
    assert local["status"] == calibration.READY_STATUS
    assert "Goldilocks Gate Calibration" in wiki
    assert "does not loosen live gates" in wiki
    assert calibration.unsafe_true_grants(local) == []


def test_missing_precondition_marks_not_ready(tmp_path):
    root = _fixture_root(tmp_path)
    _write_json(root / "gate_decision_ledger.json", {"status": "NOT_READY"})

    payload = calibration.build_read_model(read_model_root=root, generated_at=FIXED_NOW)

    assert payload["status"] == calibration.NOT_READY_STATUS
    assert payload["machine_proof"]["preconditions_ready"] is False
    assert calibration.unsafe_true_grants(payload) == []


def test_source_does_not_import_execution_or_provider_surfaces():
    source = Path("goldilocks_gate_calibration.py").read_text(encoding="utf-8").lower()
    forbidden_tokens = [
        "import subprocess",
        "subprocess.",
        "os.system",
        "import requests",
        "import httpx",
        "urllib.request",
        "import socket",
        "smtplib",
        "selenium",
        "playwright",
        "pyautogui",
        "openpyxl",
        ".chief.env",
        ".google-secrets",
        "ollama",
        "litellm",
    ]
    for token in forbidden_tokens:
        assert token not in source

    tree = ast.parse(Path("goldilocks_gate_calibration.py").read_text(encoding="utf-8"))
    imported = {
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    assert imported <= {"argparse", "json"}
