import json
import sys
from dataclasses import fields
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import self_heal_repair_doctrine as doctrine


FIXED_NOW = "2026-06-06T12:00:00+00:00"


def _read_model():
    return doctrine.build_read_model(read_model_root=ROOT / "generated/read_models", generated_at=FIXED_NOW)


def _scenario(read_model, scenario_id):
    for package in read_model["repair_packages"]:
        if package["scenario_id"] == scenario_id:
            return package
    raise AssertionError(f"missing scenario: {scenario_id}")


def _text(package):
    response = package["dynamic_response_copy"]
    parts = [
        package["blocker_summary"],
        package["next_step"],
        " ".join(package["proof_refs"]),
        " ".join(package["safe_internal_actions"]),
        " ".join(package["forbidden_actions"]),
        response["headline"],
        response["body"],
        response["proof_citation"],
        response["next_step"],
        response["required_operator_action"],
        " ".join(response["what_i_can_do_now"]),
        " ".join(response["what_i_cannot_do_yet"]),
    ]
    return " ".join(parts).lower()


def test_repair_package_dataclass_matches_required_fields():
    assert tuple(field.name for field in fields(doctrine.RepairPackage)) == doctrine.REPAIR_PACKAGE_FIELDS


def test_every_repair_scenario_has_blocker_proof_safe_actions_forbidden_actions_and_next_step():
    read_model = _read_model()

    assert read_model["status"] == doctrine.READY_STATUS
    assert {package["scenario_id"] for package in read_model["repair_packages"]} == set(doctrine.REQUIRED_SCENARIOS)
    for package in read_model["repair_packages"]:
        assert package["blocker_summary"]
        assert package["proof_refs"]
        assert package["safe_internal_actions"]
        assert package["forbidden_actions"]
        assert package["next_step"]
        assert package["dynamic_response_copy"]["proof_citation"]
        assert doctrine.validate_repair_package(package) == []


def test_required_scenario_response_contracts():
    read_model = _read_model()

    stale = _text(_scenario(read_model, "mac_controller_response_stale_after_lane_switch"))
    assert "response is stale" in stale
    assert "request/card scope does not match the active lane" in stale
    assert "stage scoped renderer fix" in stale
    assert "claim fixed" in stale
    assert "release validation" in stale
    assert "smoke" in stale

    picker = _text(_scenario(read_model, "evidence_picker_path_leaked_into_composer"))
    assert "proof file path was routed as chat input" in picker
    assert "isolate evidence picker from composer" in picker
    assert "stage a workflow package from the proof path" in picker

    excel = _text(_scenario(read_model, "excel_export_blocked_by_file_access"))
    assert "excel file access is blocked" in excel
    assert "grant access to the named workbook or choose a different workbook reference" in excel
    assert "cannot read cells" in excel or "read workbook cells" in excel

    trace = _text(_scenario(read_model, "remote_desktop_trace_log_leak"))
    assert "trace logs are filling c:" in trace
    assert "targeted cleanup" in trace
    assert "tracing-disable package" in trace

    payment = _text(_scenario(read_model, "missing_proof_for_payment"))
    assert "payment evidence is missing" in payment
    assert "attach payment proof" in payment or "attach payment evidence" in payment
    assert "mark paid" in payment
    assert "mutate ledger" in payment


def test_manual_work_uses_smallest_required_operator_action():
    read_model = _read_model()

    for package in read_model["repair_packages"]:
        action = package["required_operator_action"]
        assert doctrine.manual_action_is_smallest_required(package)
        smallest = action["smallest_action"].lower()
        assert "credentials" not in smallest
        assert "full disk" not in smallest
        assert "admin" not in smallest
        assert "broad authority" not in smallest

    assert _scenario(read_model, "excel_export_blocked_by_file_access")["required_operator_action"]["smallest_action"] == (
        "Grant access to the named workbook or choose a different workbook reference."
    )
    assert _scenario(read_model, "missing_proof_for_payment")["required_operator_action"]["smallest_action"] == "Attach payment evidence."


def test_no_scenario_grants_protected_authority():
    read_model = _read_model()

    assert read_model["machine_proof"]["no_scenario_grants_protected_authority"] is True
    assert doctrine.unsafe_true_grants(read_model) == []
    for package in read_model["repair_packages"]:
        assert doctrine.package_grants_protected_authority(package) is False
        for key, value in package["authority_boundary"].items():
            assert value is False, key


def test_repair_success_requires_validation_and_receipt():
    read_model = _read_model()

    assert read_model["rules"]["repair_success_requires_validation_and_receipt"] is True
    assert read_model["machine_proof"]["repair_success_requires_validation_and_receipt"] is True
    for package in read_model["repair_packages"]:
        receipt = package["receipt_requirement"]
        assert receipt["validation_required"] is True
        assert receipt["receipt_required"] is True
        assert receipt["success_claim_allowed_without_receipt"] is False
        assert {"validation_passed", "receipt_recorded"}.issubset(receipt["success_claim_requires_states"])


def test_excel_scenario_blocks_pdf_and_workbook_reads_until_permission_proof():
    read_model = _read_model()
    excel = _scenario(read_model, "excel_export_blocked_by_file_access")

    assert doctrine.excel_blocks_pdf_and_workbook_reads_until_permission_proof(excel) is True
    assert "export PDF before file-access proof exists" in excel["forbidden_actions"]
    assert "read workbook cells before file-access proof exists" in excel["forbidden_actions"]
    assert excel["authority_boundary"]["pdf_export_allowed"] is False
    assert excel["authority_boundary"]["workbook_read_allowed"] is False


def test_trace_cleanup_scenario_does_not_delete_unknown_active_files():
    read_model = _read_model()
    trace = _scenario(read_model, "remote_desktop_trace_log_leak")
    safe = " ".join(trace["safe_internal_actions"]).lower()

    assert doctrine.trace_cleanup_does_not_delete_unknown_active_files(trace) is True
    assert "delete unknown temp files" in trace["forbidden_actions"]
    assert "delete active swap or vhdx files" in trace["forbidden_actions"]
    assert "delete unknown" not in safe
    assert "delete active" not in safe
    assert trace["authority_boundary"]["file_delete_allowed"] is False
    assert trace["authority_boundary"]["trace_cleanup_execution_allowed"] is False


def test_unsafe_true_grant_scan_clean():
    read_model = _read_model()

    assert read_model["machine_proof"]["unsafe_true_grants_absent"] is True
    assert read_model["machine_proof"]["unsafe_true_grants"] == []
    assert doctrine.unsafe_true_grants(read_model) == []


def test_export_writes_json_wiki_and_bridge_round_trip(tmp_path):
    result = doctrine.export_self_heal_repair_doctrine(
        read_model_root=ROOT / "generated/read_models",
        export_root=tmp_path / "read_models",
        bridge_export_root=tmp_path / "bridge",
        wiki_path=tmp_path / "Self Heal Repair Doctrine.md",
        generated_at=FIXED_NOW,
    )
    local_payload = json.loads(Path(result["read_model_path"]).read_text(encoding="utf-8"))
    bridge_payload = json.loads(Path(result["bridge_read_model_path"]).read_text(encoding="utf-8"))
    wiki = Path(result["wiki_path"]).read_text(encoding="utf-8")

    assert result["status"] == doctrine.READY_STATUS
    assert local_payload == bridge_payload
    assert local_payload["read_model_id"] == doctrine.READ_MODEL_ID
    assert "Self Heal Repair Doctrine" in wiki
    assert "Every fix requires validation and receipt" in wiki
