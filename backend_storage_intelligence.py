"""Pure storage-safety read models for Operator Storage Intelligence.

This module contains no filesystem access, crawling, checksum action,
operation execution, indexing, provider/model calls, API/app integration, or
runtime workers. It evaluates caller-provided plain data only.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

from backend_data_contract import (
    STORAGE_INTELLIGENCE_EXECUTION_STATUSES,
    STORAGE_INTELLIGENCE_SAFETY_TIERS,
)


HIGH_RISK_SAFETY_TIERS = frozenset(
    {
        "move_after_verified_copy",
        "destructive_or_reformat",
    }
)
NON_EXECUTING_PLAN_STATUSES = frozenset({"dry_run", "planned", "blocked"})


@dataclass(frozen=True)
class StorageRiskFinding:
    """Plain risk signal for a proposed storage operation or dry-run plan."""

    finding_id: str
    finding_kind: str
    severity: str
    message: str
    requires_operator_approval: bool


@dataclass(frozen=True)
class ProposedStorageOperation:
    """Plain proposed operation data; it cannot execute storage behavior."""

    operation_id: str
    operation_type: str
    source_inventory_id: str
    target_path: str
    safety_tier: str
    checksum_verification: int
    operator_approval_ref: str
    execution_status: str = "dry_run"
    risk_findings: tuple[StorageRiskFinding, ...] = ()


@dataclass(frozen=True)
class DryRunStoragePlan:
    """Plain dry-run plan containing proposed operations and risk findings."""

    plan_id: str
    plan_kind: str
    operations: tuple[ProposedStorageOperation, ...]
    required_approval_tier: str
    status: str = "dry_run"
    receipt_refs: tuple[str, ...] = ()
    risk_findings: tuple[StorageRiskFinding, ...] = ()
    plan_status: str = "non_executing"


def evaluate_storage_operation_risks(
    operation: ProposedStorageOperation,
) -> tuple[StorageRiskFinding, ...]:
    """Return deterministic risk findings for one caller-provided operation."""

    _validate_operation_shape(operation)
    findings = list(operation.risk_findings)
    if operation.safety_tier in HIGH_RISK_SAFETY_TIERS and not operation.operator_approval_ref:
        findings.append(
            StorageRiskFinding(
                finding_id=f"{operation.operation_id}:explicit_approval_required",
                finding_kind="explicit_approval_required",
                severity="high",
                message="high-risk storage operation requires explicit operator approval",
                requires_operator_approval=True,
            )
        )
    if (
        operation.safety_tier in HIGH_RISK_SAFETY_TIERS
        and operation.checksum_verification == 0
    ):
        findings.append(
            StorageRiskFinding(
                finding_id=f"{operation.operation_id}:missing_verified_backup",
                finding_kind="missing_verified_backup",
                severity="high",
                message="high-risk storage operation lacks verified backup/checksum proof",
                requires_operator_approval=True,
            )
        )
    if operation.safety_tier == "read_only" and _looks_destructive(operation):
        findings.append(
            StorageRiskFinding(
                finding_id=f"{operation.operation_id}:destructive_not_read_only",
                finding_kind="destructive_not_read_only",
                severity="high",
                message="destructive or reformat intent cannot be represented as read-only",
                requires_operator_approval=True,
            )
        )
    return tuple(findings)


def storage_operation_is_non_executing(operation: ProposedStorageOperation) -> bool:
    """Return True when operation status is representable as non-executing."""

    _validate_operation_shape(operation)
    return operation.execution_status in NON_EXECUTING_PLAN_STATUSES


def assemble_dry_run_storage_plan(
    plan_id: str,
    plan_kind: str,
    operations: tuple[ProposedStorageOperation, ...],
    *,
    receipt_refs: tuple[str, ...] = (),
) -> DryRunStoragePlan:
    """Assemble a deterministic non-executing storage plan from plain data."""

    _require_non_empty_string(plan_id, "plan_id")
    _require_non_empty_string(plan_kind, "plan_kind")
    if not isinstance(operations, tuple):
        raise ValueError("operations must be a tuple")
    if not isinstance(receipt_refs, tuple):
        raise ValueError("receipt_refs must be a tuple")

    findings: list[StorageRiskFinding] = []
    for operation in operations:
        findings.extend(evaluate_storage_operation_risks(operation))
        if not storage_operation_is_non_executing(operation):
            findings.append(
                StorageRiskFinding(
                    finding_id=f"{operation.operation_id}:execution_status_not_dry_run",
                    finding_kind="execution_status_not_dry_run",
                    severity="high",
                    message="dry-run plan cannot contain executed storage operations",
                    requires_operator_approval=True,
                )
            )

    required_approval_tier = (
        "explicit_operator_approval_required"
        if any(finding.requires_operator_approval for finding in findings)
        else "none_required_for_dry_run"
    )
    return DryRunStoragePlan(
        plan_id=plan_id,
        plan_kind=plan_kind,
        operations=operations,
        required_approval_tier=required_approval_tier,
        receipt_refs=receipt_refs,
        risk_findings=tuple(findings),
    )


def storage_risk_finding_as_dict(finding: StorageRiskFinding) -> dict[str, object]:
    """Return a deterministic plain-Python risk finding representation."""

    return asdict(finding)


def proposed_storage_operation_as_dict(
    operation: ProposedStorageOperation,
) -> dict[str, object]:
    """Return a deterministic plain-Python proposed operation representation."""

    return asdict(operation)


def dry_run_storage_plan_as_dict(plan: DryRunStoragePlan) -> dict[str, object]:
    """Return a deterministic plain-Python dry-run plan representation."""

    return asdict(plan)


def _validate_operation_shape(operation: ProposedStorageOperation) -> None:
    if not isinstance(operation, ProposedStorageOperation):
        raise ValueError("operation must be a ProposedStorageOperation")
    _require_non_empty_string(operation.operation_id, "operation_id")
    _require_non_empty_string(operation.operation_type, "operation_type")
    _require_non_empty_string(operation.source_inventory_id, "source_inventory_id")
    _require_non_empty_string(operation.target_path, "target_path")
    if operation.safety_tier not in STORAGE_INTELLIGENCE_SAFETY_TIERS:
        raise ValueError(f"unknown safety_tier: {operation.safety_tier}")
    if type(operation.checksum_verification) is not int or (
        operation.checksum_verification not in {0, 1}
    ):
        raise ValueError("checksum_verification must be 0 or 1")
    if operation.execution_status not in STORAGE_INTELLIGENCE_EXECUTION_STATUSES:
        raise ValueError(f"unknown execution_status: {operation.execution_status}")
    if not isinstance(operation.risk_findings, tuple):
        raise ValueError("risk_findings must be a tuple")


def _looks_destructive(operation: ProposedStorageOperation) -> bool:
    normalized = operation.operation_type.lower().replace("-", "_").replace(" ", "_")
    return "delete" in normalized or "reformat" in normalized or "destructive" in normalized


def _require_non_empty_string(value: object, field_name: str) -> None:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field_name} must be a non-empty string")
