"""Pure storage-safety read models for Operator Storage Intelligence.

This module contains no filesystem access, crawling, checksum action,
operation execution, indexing, provider/model calls, API/app integration, or
runtime workers. It evaluates caller-provided plain data only.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

from backend_data_contract import (
    ENVIRONMENT_INTELLIGENCE_AUTHORIZATION_SCOPE_STATUSES,
    ENVIRONMENT_INTELLIGENCE_NODE_SOURCE_LINK_STATUSES,
    ENVIRONMENT_INTELLIGENCE_TRUST_STATUSES,
    RUNTIME_PRESENCE_CAPABILITY_STATUSES,
    RUNTIME_PRESENCE_COMPONENT_STATUSES,
    RUNTIME_PRESENCE_HEALTH_STATUSES,
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
AUTHORIZATION_READINESS_SCOPE_STATUSES = frozenset(
    ENVIRONMENT_INTELLIGENCE_AUTHORIZATION_SCOPE_STATUSES
) | {"missing"}
RUNTIME_COMPONENT_READINESS_STATUSES = frozenset(
    RUNTIME_PRESENCE_COMPONENT_STATUSES
) | {"missing"}
RUNTIME_HEARTBEAT_READINESS_STATUSES = frozenset(RUNTIME_PRESENCE_HEALTH_STATUSES) | {
    "missing",
    "expired",
}
RUNTIME_CAPABILITY_READINESS_STATUSES = frozenset(
    RUNTIME_PRESENCE_CAPABILITY_STATUSES
) | {"missing"}


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


@dataclass(frozen=True)
class NodeAuthorizationSnapshot:
    """Caller-provided node/source/tenant authorization state."""

    node_id: str
    node_trust_status: str
    node_status: str
    node_tenant_id: str
    source_id: str
    source_tenant_id: str
    source_link_status: str
    authorization_scope_status: str
    authorized_entity_family: str
    authorized_entity_id: str
    source_mode: str
    operator_approval_ref: str
    agent_version: str = ""


@dataclass(frozen=True)
class RuntimeComponentHealthSnapshot:
    """Caller-provided runtime component readiness state."""

    component_id: str
    node_id: str
    tenant_id: str
    component_status: str
    component_role: str
    requested_role: str
    heartbeat_status: str
    health_status: str
    capability_status: str
    required_capability: str
    component_version: str
    approved_for_tenant_id: str


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


def evaluate_node_authorization_risks(
    snapshot: NodeAuthorizationSnapshot,
) -> tuple[StorageRiskFinding, ...]:
    """Return deterministic zero-trust risks from caller-provided node state."""

    _validate_node_authorization_snapshot(snapshot)
    findings: list[StorageRiskFinding] = []
    if snapshot.node_trust_status == "unknown":
        findings.append(
            _node_risk(
                snapshot,
                "unknown_node",
                "high",
                "node trust is unknown; discovery does not authorize communication",
            )
        )
    if snapshot.node_trust_status == "pending_approval":
        findings.append(
            _node_risk(
                snapshot,
                "unapproved_node",
                "high",
                "node requires explicit operator approval before use",
            )
        )
    if snapshot.node_trust_status == "revoked":
        findings.append(
            _node_risk(snapshot, "revoked_node", "high", "node trust is revoked")
        )
    if snapshot.node_trust_status == "stale":
        findings.append(_node_risk(snapshot, "stale_node", "medium", "node trust is stale"))
    if snapshot.node_tenant_id != snapshot.source_tenant_id:
        findings.append(
            _node_risk(
                snapshot,
                "node_source_tenant_mismatch",
                "high",
                "node/source tenant mismatch blocks cross-tenant operation",
            )
        )
    if snapshot.source_link_status != "active":
        findings.append(
            _node_risk(
                snapshot,
                "source_not_actively_linked_to_node",
                "high",
                "source must have an active tenant-scoped node/source link",
            )
        )
    if snapshot.authorization_scope_status != "active":
        findings.append(
            _node_risk(
                snapshot,
                f"{snapshot.authorization_scope_status}_source_authorization_scope",
                "high",
                "source authorization scope is missing, expired, or revoked",
            )
        )
    if (
        snapshot.authorized_entity_family == "legal_matter"
        and snapshot.authorization_scope_status != "active"
    ):
        findings.append(
            _node_risk(
                snapshot,
                "legal_private_source_without_active_scope",
                "high",
                "legal/private source handling requires an active matching scope",
            )
        )
    if "remote" in snapshot.node_status.lower():
        findings.append(
            _node_risk(
                snapshot,
                "remote_execution_not_allowed",
                "high",
                "remote execution is not authorized by node/source approval",
            )
        )
    if snapshot.agent_version == "stale":
        findings.append(
            _node_risk(
                snapshot,
                "stale_agent_version",
                "medium",
                "node agent version is stale and needs review",
                requires_operator_approval=False,
            )
        )
    return tuple(findings)


def node_authorization_snapshot_as_dict(
    snapshot: NodeAuthorizationSnapshot,
) -> dict[str, object]:
    """Return deterministic plain-Python node authorization data."""

    return asdict(snapshot)


def evaluate_runtime_component_health_risks(
    snapshot: RuntimeComponentHealthSnapshot,
) -> tuple[StorageRiskFinding, ...]:
    """Return deterministic health/readiness risks from caller-provided state."""

    _validate_runtime_component_health_snapshot(snapshot)
    findings: list[StorageRiskFinding] = []
    if snapshot.tenant_id != snapshot.approved_for_tenant_id:
        findings.append(
            _component_risk(
                snapshot,
                "component_tenant_mismatch",
                "high",
                "component tenant mismatch blocks scoped runtime visibility",
            )
        )
    if snapshot.component_status == "missing":
        findings.append(
            _component_risk(
                snapshot,
                "missing_component",
                "high",
                "required runtime component is not represented",
            )
        )
    if snapshot.component_status == "unknown":
        findings.append(
            _component_risk(
                snapshot,
                "unknown_component",
                "high",
                "unknown component presence is a signal, not trusted inventory",
            )
        )
    if snapshot.component_status == "pending_approval":
        findings.append(
            _component_risk(
                snapshot,
                "component_present_but_not_approved",
                "high",
                "component presence does not imply approval",
            )
        )
    if snapshot.component_status == "revoked":
        findings.append(
            _component_risk(snapshot, "revoked_component", "high", "component revoked")
        )
    if snapshot.component_status == "stale":
        findings.append(
            _component_risk(
                snapshot,
                "stale_component",
                "medium",
                "component registration is stale",
            )
        )
    if snapshot.heartbeat_status == "missing":
        findings.append(
            _component_risk(
                snapshot,
                "missing_heartbeat",
                "medium",
                "component has no stored heartbeat data",
                requires_operator_approval=False,
            )
        )
    if snapshot.heartbeat_status == "expired":
        findings.append(
            _component_risk(
                snapshot,
                "expired_heartbeat_ttl",
                "medium",
                "component heartbeat TTL is expired",
                requires_operator_approval=False,
            )
        )
    if snapshot.health_status == "degraded":
        findings.append(
            _component_risk(
                snapshot,
                "degraded_component",
                "medium",
                "component health is degraded",
                requires_operator_approval=False,
            )
        )
    if snapshot.health_status == "critical":
        findings.append(
            _component_risk(
                snapshot,
                "critical_component_health",
                "high",
                "component health is critical",
            )
        )
    if snapshot.capability_status == "missing":
        findings.append(
            _component_risk(
                snapshot,
                "missing_required_capability",
                "high",
                "component lacks required capability metadata",
            )
        )
    if snapshot.capability_status == "revoked":
        findings.append(
            _component_risk(
                snapshot,
                "capability_revoked",
                "high",
                "required component capability is revoked",
            )
        )
    if snapshot.component_role != snapshot.requested_role:
        findings.append(
            _component_risk(
                snapshot,
                "component_cannot_run_requested_role",
                "high",
                "component role does not match the requested role",
            )
        )
    if snapshot.component_version == "stale":
        findings.append(
            _component_risk(
                snapshot,
                "stale_component_version",
                "medium",
                "component version is stale and needs review",
                requires_operator_approval=False,
            )
        )
    return tuple(findings)


def runtime_component_health_snapshot_as_dict(
    snapshot: RuntimeComponentHealthSnapshot,
) -> dict[str, object]:
    """Return deterministic plain-Python runtime component health data."""

    return asdict(snapshot)


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


def _validate_node_authorization_snapshot(snapshot: NodeAuthorizationSnapshot) -> None:
    if not isinstance(snapshot, NodeAuthorizationSnapshot):
        raise ValueError("snapshot must be a NodeAuthorizationSnapshot")
    _require_non_empty_string(snapshot.node_id, "node_id")
    _require_non_empty_string(snapshot.node_status, "node_status")
    _require_non_empty_string(snapshot.node_tenant_id, "node_tenant_id")
    _require_non_empty_string(snapshot.source_id, "source_id")
    _require_non_empty_string(snapshot.source_tenant_id, "source_tenant_id")
    _require_non_empty_string(
        snapshot.authorized_entity_family,
        "authorized_entity_family",
    )
    _require_non_empty_string(snapshot.authorized_entity_id, "authorized_entity_id")
    _require_non_empty_string(snapshot.source_mode, "source_mode")
    if snapshot.node_trust_status not in ENVIRONMENT_INTELLIGENCE_TRUST_STATUSES:
        raise ValueError(f"unknown node_trust_status: {snapshot.node_trust_status}")
    if snapshot.source_link_status not in ENVIRONMENT_INTELLIGENCE_NODE_SOURCE_LINK_STATUSES:
        raise ValueError(f"unknown source_link_status: {snapshot.source_link_status}")
    if (
        snapshot.authorization_scope_status
        not in AUTHORIZATION_READINESS_SCOPE_STATUSES
    ):
        raise ValueError(
            f"unknown authorization_scope_status: {snapshot.authorization_scope_status}"
        )


def _validate_runtime_component_health_snapshot(
    snapshot: RuntimeComponentHealthSnapshot,
) -> None:
    if not isinstance(snapshot, RuntimeComponentHealthSnapshot):
        raise ValueError("snapshot must be a RuntimeComponentHealthSnapshot")
    _require_non_empty_string(snapshot.component_id, "component_id")
    _require_non_empty_string(snapshot.node_id, "node_id")
    _require_non_empty_string(snapshot.tenant_id, "tenant_id")
    _require_non_empty_string(snapshot.component_role, "component_role")
    _require_non_empty_string(snapshot.requested_role, "requested_role")
    _require_non_empty_string(snapshot.required_capability, "required_capability")
    _require_non_empty_string(snapshot.component_version, "component_version")
    _require_non_empty_string(snapshot.approved_for_tenant_id, "approved_for_tenant_id")
    if snapshot.component_status not in RUNTIME_COMPONENT_READINESS_STATUSES:
        raise ValueError(f"unknown component_status: {snapshot.component_status}")
    if snapshot.heartbeat_status not in RUNTIME_HEARTBEAT_READINESS_STATUSES:
        raise ValueError(f"unknown heartbeat_status: {snapshot.heartbeat_status}")
    if snapshot.health_status not in RUNTIME_PRESENCE_HEALTH_STATUSES:
        raise ValueError(f"unknown health_status: {snapshot.health_status}")
    if snapshot.capability_status not in RUNTIME_CAPABILITY_READINESS_STATUSES:
        raise ValueError(f"unknown capability_status: {snapshot.capability_status}")


def _node_risk(
    snapshot: NodeAuthorizationSnapshot,
    finding_kind: str,
    severity: str,
    message: str,
    *,
    requires_operator_approval: bool = True,
) -> StorageRiskFinding:
    return StorageRiskFinding(
        finding_id=f"{snapshot.node_id}:{snapshot.source_id}:{finding_kind}",
        finding_kind=finding_kind,
        severity=severity,
        message=message,
        requires_operator_approval=requires_operator_approval,
    )


def _component_risk(
    snapshot: RuntimeComponentHealthSnapshot,
    finding_kind: str,
    severity: str,
    message: str,
    *,
    requires_operator_approval: bool = True,
) -> StorageRiskFinding:
    return StorageRiskFinding(
        finding_id=f"{snapshot.component_id}:{snapshot.required_capability}:{finding_kind}",
        finding_kind=finding_kind,
        severity=severity,
        message=message,
        requires_operator_approval=requires_operator_approval,
    )


def _looks_destructive(operation: ProposedStorageOperation) -> bool:
    normalized = operation.operation_type.lower().replace("-", "_").replace(" ", "_")
    return "delete" in normalized or "reformat" in normalized or "destructive" in normalized


def _require_non_empty_string(value: object, field_name: str) -> None:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field_name} must be a non-empty string")
