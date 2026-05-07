import ast
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend_storage_intelligence import (
    DryRunStoragePlan,
    ProposedStorageOperation,
    StorageRiskFinding,
    assemble_dry_run_storage_plan,
    dry_run_storage_plan_as_dict,
    evaluate_storage_operation_risks,
    proposed_storage_operation_as_dict,
    storage_operation_is_non_executing,
    storage_risk_finding_as_dict,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "backend_storage_intelligence.py"


def module_ast() -> ast.Module:
    return ast.parse(MODULE_PATH.read_text(encoding="utf-8"))


def imported_module_names(tree: ast.Module) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def called_function_names(tree: ast.Module) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                names.add(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                names.add(node.func.attr)
    return names


def sample_operation(**overrides) -> ProposedStorageOperation:
    payload = {
        "operation_id": "operation-1",
        "operation_type": "backup_plan",
        "source_inventory_id": "inventory-1",
        "target_path": "operator-provided-target",
        "safety_tier": "read_only",
        "checksum_verification": 0,
        "operator_approval_ref": "",
        "execution_status": "dry_run",
        "risk_findings": (),
    } | overrides
    return ProposedStorageOperation(**payload)


def test_storage_intelligence_module_is_pure_and_non_executing():
    source = MODULE_PATH.read_text(encoding="utf-8").lower()
    tree = module_ast()

    assert imported_module_names(tree) <= {
        "__future__",
        "dataclasses",
        "backend_data_contract",
    }
    assert {
        "open",
        "read_text",
        "write_text",
        "stat",
        "iterdir",
        "glob",
        "walk",
        "copy",
        "move",
        "unlink",
        "remove",
        "rmdir",
        "rename",
        "connect",
        "execute",
        "run",
    }.isdisjoint(called_function_names(tree))
    assert re.search(r"\bsqlite3\b", source) is None
    assert re.search(r"\bpsutil\b", source) is None
    assert re.search(r"\bdiskutil\b", source) is None
    assert re.search(r"\bpowershell\b", source) is None
    assert re.search(r"\bchecksum execution\b", source) is None


def test_high_risk_operations_require_explicit_approval_and_verified_backup():
    operation = sample_operation(
        operation_type="drive_reformat",
        safety_tier="destructive_or_reformat",
        checksum_verification=0,
        operator_approval_ref="",
    )

    findings = evaluate_storage_operation_risks(operation)

    assert [finding.finding_kind for finding in findings] == [
        "explicit_approval_required",
        "missing_verified_backup",
    ]
    assert all(finding.requires_operator_approval for finding in findings)


def test_destructive_work_cannot_be_represented_as_read_only():
    operation = sample_operation(
        operation_type="delete_or_reformat_drive",
        safety_tier="read_only",
    )

    findings = evaluate_storage_operation_risks(operation)

    assert [finding.finding_kind for finding in findings] == [
        "destructive_not_read_only"
    ]


def test_private_or_excluded_path_risk_can_be_represented_without_execution():
    risk = StorageRiskFinding(
        finding_id="operation-1:private_or_excluded_path",
        finding_kind="private_or_excluded_path",
        severity="high",
        message="operation would touch an excluded/private path",
        requires_operator_approval=True,
    )
    operation = sample_operation(risk_findings=(risk,))

    assert evaluate_storage_operation_risks(operation) == (risk,)
    assert storage_risk_finding_as_dict(risk)["finding_kind"] == (
        "private_or_excluded_path"
    )


def test_dry_run_plan_is_plain_data_and_non_executing():
    operation = sample_operation()
    plan = assemble_dry_run_storage_plan(
        "plan-1",
        "backup_plan",
        (operation,),
        receipt_refs=("receipt-1",),
    )
    plan_dict = dry_run_storage_plan_as_dict(plan)

    assert isinstance(plan, DryRunStoragePlan)
    assert plan.plan_status == "non_executing"
    assert plan.status == "dry_run"
    assert plan.required_approval_tier == "none_required_for_dry_run"
    assert plan.receipt_refs == ("receipt-1",)
    assert plan_dict["operations"][0]["operation_id"] == "operation-1"
    assert proposed_storage_operation_as_dict(operation)["execution_status"] == "dry_run"
    assert storage_operation_is_non_executing(operation) is True


def test_dry_run_plan_blocks_executed_operations_as_reckless():
    operation = sample_operation(execution_status="executed")

    plan = assemble_dry_run_storage_plan("plan-1", "backup_plan", (operation,))

    assert plan.required_approval_tier == "explicit_operator_approval_required"
    assert [finding.finding_kind for finding in plan.risk_findings] == [
        "execution_status_not_dry_run"
    ]
    assert storage_operation_is_non_executing(operation) is False


def test_storage_safety_models_fail_closed_for_invalid_shapes_and_bool_values():
    with pytest.raises(ValueError):
        assemble_dry_run_storage_plan("", "backup_plan", ())
    with pytest.raises(ValueError):
        assemble_dry_run_storage_plan("plan-1", "backup_plan", [])
    with pytest.raises(ValueError):
        evaluate_storage_operation_risks(
            sample_operation(checksum_verification=True),
        )
    with pytest.raises(ValueError):
        evaluate_storage_operation_risks(sample_operation(safety_tier="magic"))
    with pytest.raises(ValueError):
        evaluate_storage_operation_risks(sample_operation(execution_status="magic"))
