"""OpenClaw LM child package gate v0.

Deterministic contract/read-model for the future LM Gate -> SQLite Package
Gate -> LM2 -> Guardian -> Child Worker chain. This module defines package
schemas, delegation policy, budget/authority checks, Guardian requirements, and
receipt closure rules. It does not call models, spawn workers, launch Chief,
start services, access email/Gmail/browser/Coupa, read workbook cells, export
PDFs, mutate ledgers, mutate production state, or push.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parent
DEFAULT_READ_MODEL_ROOT = Path("generated/read_models")
DEFAULT_SYSTEM_KNOWLEDGE_ROOT = Path("generated/system_knowledge")

SCHEMA_VERSION = "openclaw_lm_child_package_gate_v0"
READ_MODEL_ID = "openclaw_lm_child_package_gate"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
OPERATOR_EXPORT_NAME = f"{READ_MODEL_ID}_OPERATOR.md"
SQLITE_EXPORT_NAME = f"{READ_MODEL_ID}.sqlite"
SCHEMA_EXPORT_NAME = f"{READ_MODEL_ID}_SCHEMA.sql"
SEED_EXPORT_NAME = f"{READ_MODEL_ID}_SEED.sql"
CONTRACT_STATUS = "DETERMINISTIC_LM_CHILD_PACKAGE_GATE_CONTRACT_NO_RUNTIME_SWARMS"
READINESS = "READY_FOR_CONTRACT_NOT_RUNTIME_SPAWNING"

DECISIONS = (
    "ALLOW",
    "BLOCK",
    "REQUIRE_GUARDIAN",
    "REQUIRE_OPERATOR",
    "BUDGET_EXCEEDED",
    "AUTHORITY_DENIED",
)

VALIDATION_STATUSES = (
    "NOT_EVALUATED",
    "ALLOW",
    "BLOCK",
    "REQUIRE_GUARDIAN",
    "REQUIRE_OPERATOR",
    "BUDGET_EXCEEDED",
    "AUTHORITY_DENIED",
)

GUARDIAN_STATUSES = (
    "NOT_REQUIRED",
    "PENDING",
    "APPROVED",
    "DENIED",
)

PACKAGE_STATUSES = (
    "DRAFT",
    "CONTRACT_ONLY",
    "WAITING_GUARDIAN",
    "BLOCKED",
    "CLOSED",
)

REQUIRED_SQLITE_TABLES = (
    "lm_package",
    "child_spawn_policy",
    "child_package_request",
    "package_receipt",
    "package_gate_decision",
)

LM_PACKAGE_FIELDS = (
    "package_ref",
    "parent_package_ref",
    "mission",
    "model_class",
    "budget_limit",
    "allowed_files",
    "forbidden_files",
    "allowed_commands",
    "forbidden_actions",
    "required_tests",
    "expected_outputs",
    "authority_profile_ref",
    "guardian_required",
    "live_action_authority",
    "status",
    "package_depth",
    "stop_conditions",
    "child_receipt_required",
    "source_refs",
)

CHILD_SPAWN_POLICY_FIELDS = (
    "policy_ref",
    "parent_model_class",
    "child_model_class",
    "spawn_allowed",
    "max_children",
    "max_depth",
    "max_total_budget",
    "allowed_child_task_types",
    "forbidden_child_task_types",
    "requires_guardian_approval",
    "requires_operator_approval",
    "policy_status",
)

CHILD_PACKAGE_REQUEST_FIELDS = (
    "request_ref",
    "parent_package_ref",
    "proposed_child_package_ref",
    "reason",
    "requested_model_class",
    "requested_budget",
    "requested_files",
    "requested_commands",
    "requested_authority",
    "validation_status",
    "guardian_status",
    "child_task_type",
    "requested_depth",
    "stop_conditions",
    "receipt_required",
    "validation_reasons",
)

PACKAGE_RECEIPT_FIELDS = (
    "receipt_ref",
    "package_ref",
    "worker_ref",
    "result_status",
    "files_changed",
    "tests_run",
    "boundary_check",
    "child_packages_spawned",
    "budget_used",
    "proof_refs",
)

PACKAGE_GATE_DECISION_FIELDS = (
    "decision_ref",
    "package_ref",
    "decision",
    "reason",
    "source_refs",
    "request_ref",
)

FORBIDDEN_CHILD_AUTHORITIES = frozenset(
    {
        "email",
        "email_send",
        "email_send_allowed",
        "gmail",
        "gmail_access",
        "gmail_access_allowed",
        "browser",
        "browser_access",
        "browser_access_allowed",
        "coupa",
        "coupa_access",
        "coupa_access_allowed",
        "workbook",
        "workbook_body_read",
        "workbook_cell_read",
        "workbook_cell_read_allowed",
        "spreadsheet_cell_read",
        "pdf",
        "pdf_export",
        "pdf_generation",
        "ledger",
        "ledger_post",
        "ledger_posting",
        "ledger_post_allowed",
        "production_mutation",
        "production_state_mutation",
        "business_mutation",
        "external_action",
        "send_submit",
        "credential",
        "credential_access",
        "network",
        "service_start",
        "runtime_activation",
        "swarm",
    }
)

FORBIDDEN_ACTIONS_BASE = (
    "call_lm",
    "spawn_child",
    "spawn_swarm",
    "recursive_spawn",
    "launch_chief",
    "start_service",
    "send_email",
    "access_gmail",
    "open_browser",
    "access_coupa",
    "read_workbook_cells",
    "export_pdf",
    "post_ledger",
    "mutate_production_state",
    "push_git",
)

FORBIDDEN_FILE_MARKERS = (
    ".chief.env",
    ".google-secrets",
    "id_rsa",
    "id_ed25519",
    "token",
    "secret",
    "credential",
    "ledger",
    ".xlsx",
    ".xlsm",
    ".pdf",
)

SOURCE_INPUT_SPECS = (
    ("authority_semantics_registry", "generated/read_models/openclaw_authority_semantics_registry.json", False, "Canonical authority polarity and deny-by-default registry."),
    ("lane_capability_harvest", "generated/read_models/openclaw_lane_capability_harvest.json", False, "Reusable lane capabilities and Hermes recommendation posture."),
    ("hermes_chief_build_handoff", "generated/read_models/hermes_chief_build_handoff.json", False, "Hermes/Chief handoff read-model if present."),
    ("hermes_mission_sentinel", "generated/read_models/hermes_mission_sentinel.json", False, "Hermes mission sentinel read-model if present."),
    ("chief_test_harness_cross_off_receipt_contract", "generated/read_models/chief_test_harness_cross_off_receipt_contract.json", False, "Chief receipt/cross-off contract if present."),
    ("business_object_layer_audit", "generated/read_models/openclaw_business_object_layer_audit.json", False, "Business-object audit posture if present."),
    ("delegated_package_graph", "generated/read_models/delegated_package_graph.json", False, "Prior delegated package fixture, referenced as non-runtime precedent only."),
)


@dataclass(frozen=True)
class LMPackage:
    package_ref: str
    parent_package_ref: str
    mission: str
    model_class: str
    budget_limit: int
    allowed_files: tuple[str, ...]
    forbidden_files: tuple[str, ...]
    allowed_commands: tuple[str, ...]
    forbidden_actions: tuple[str, ...]
    required_tests: tuple[str, ...]
    expected_outputs: tuple[str, ...]
    authority_profile_ref: str
    guardian_required: bool = False
    live_action_authority: bool = False
    status: str = "CONTRACT_ONLY"
    package_depth: int = 0
    stop_conditions: tuple[str, ...] = (
        "budget_exhausted",
        "scope_boundary_hit",
        "guardian_required",
        "operator_required",
        "forbidden_authority_requested",
    )
    child_receipt_required: bool = True
    source_refs: tuple[str, ...] = ()


@dataclass(frozen=True)
class ChildSpawnPolicy:
    policy_ref: str
    parent_model_class: str
    child_model_class: str
    spawn_allowed: bool = False
    max_children: int = 0
    max_depth: int = 0
    max_total_budget: int = 0
    allowed_child_task_types: tuple[str, ...] = ()
    forbidden_child_task_types: tuple[str, ...] = ("swarm", "recursive_spawn", "live_action")
    requires_guardian_approval: bool = False
    requires_operator_approval: bool = False
    policy_status: str = "CONTRACT_ONLY"


@dataclass(frozen=True)
class ChildPackageRequest:
    request_ref: str
    parent_package_ref: str
    proposed_child_package_ref: str
    reason: str
    requested_model_class: str
    requested_budget: int
    requested_files: tuple[str, ...]
    requested_commands: tuple[str, ...]
    requested_authority: tuple[str, ...]
    validation_status: str = "NOT_EVALUATED"
    guardian_status: str = "PENDING"
    child_task_type: str = "audit_read_only"
    requested_depth: int = 1
    stop_conditions: tuple[str, ...] = (
        "task_complete",
        "budget_exhausted",
        "boundary_check_failed",
        "guardian_required",
    )
    receipt_required: bool = True
    validation_reasons: tuple[str, ...] = ()


@dataclass(frozen=True)
class PackageReceipt:
    receipt_ref: str
    package_ref: str
    worker_ref: str
    result_status: str
    files_changed: tuple[str, ...]
    tests_run: tuple[str, ...]
    boundary_check: str
    child_packages_spawned: tuple[str, ...]
    budget_used: int
    proof_refs: tuple[str, ...]


@dataclass(frozen=True)
class PackageGateDecision:
    decision_ref: str
    package_ref: str
    decision: str
    reason: str
    source_refs: tuple[str, ...]
    request_ref: str = ""


@dataclass(frozen=True)
class LMChildPackageGateExportResult:
    schema_version: str
    json_path: str
    operator_path: str
    sqlite_path: str
    schema_sql_path: str
    seed_sql_path: str
    package_count: int
    child_spawn_policy_count: int
    decision_count: int
    readiness: str


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def _compact_json(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, ensure_ascii=True)


def _short_hash(*parts: object) -> str:
    return hashlib.sha256(_compact_json(parts).encode("utf-8")).hexdigest()[:20]


def _content_hash(payload: Mapping[str, Any]) -> str:
    clone = json.loads(stable_json(dict(payload)))
    machine = clone.get("machine_proof")
    if isinstance(machine, dict):
        machine.pop("content_hash", None)
    return "sha256:" + hashlib.sha256(stable_json(clone).encode("utf-8")).hexdigest()


def _rooted(path: str | Path, *, root: str | Path = ROOT) -> Path:
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    return Path(root) / candidate


def _display_path(path: str | Path) -> str:
    candidate = Path(path)
    try:
        return candidate.resolve().relative_to(ROOT.resolve()).as_posix()
    except (OSError, ValueError):
        return candidate.as_posix()


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(text, encoding="utf-8")
    temp_path.replace(path)


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def _manifest_path(path_value: str, *, read_model_root: str | Path) -> Path:
    if path_value.startswith("generated/read_models/"):
        return _rooted(read_model_root) / path_value.removeprefix("generated/read_models/")
    return _rooted(path_value)


def _source_manifest(read_model_root: str | Path) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    payloads: dict[str, dict[str, Any]] = {}
    for input_ref, path_value, required, purpose in SOURCE_INPUT_SPECS:
        path = _manifest_path(path_value, read_model_root=read_model_root)
        status = "PRESENT" if path.is_file() else ("MISSING" if required else "NOT_PRESENT")
        schema_version = ""
        sha256 = ""
        if path.is_file():
            sha256 = _sha256_file(path)
            payload = _read_json(path)
            payloads[input_ref] = payload
            schema_version = str(payload.get("schema_version", ""))
            if not payload:
                status = "BAD_JSON"
        rows.append(
            {
                "input_ref": input_ref,
                "path": path_value,
                "resolved_path": _display_path(path),
                "required": required,
                "status": status,
                "schema_version": schema_version,
                "sha256": sha256,
                "purpose": purpose,
            }
        )
    return rows, payloads


def _tuple(values: Sequence[object] | object | None) -> tuple[str, ...]:
    if values is None:
        return ()
    if isinstance(values, str):
        cleaned = values.strip()
        return (cleaned,) if cleaned else ()
    if isinstance(values, Sequence):
        return tuple(str(value).strip() for value in values if str(value).strip())
    return (str(values).strip(),)


def _asdict(instance: Any) -> dict[str, Any]:
    row = asdict(instance)
    return {key: value for key, value in row.items()}


def _policy_key(value: object) -> str:
    return str(value or "").strip()


def _norm(value: object) -> str:
    return str(value or "").strip().lower().replace("-", "_").replace(" ", "_")


def _json_tuple(values: Sequence[object] | object | None) -> str:
    return stable_json(list(_tuple(values))).strip()


def default_lm_package(**overrides: Any) -> LMPackage:
    package = LMPackage(
        package_ref="lm_package:default_no_spawn",
        parent_package_ref="",
        mission="Default LM2 package contract with child spawning disabled.",
        model_class="LM2",
        budget_limit=1000,
        allowed_files=("openclaw_lm_child_package_gate.py", "tests/test_openclaw_lm_child_package_gate.py"),
        forbidden_files=(".chief.env", ".google-secrets/", "*.xlsx", "*.xlsm", "*.pdf", "generated/system_knowledge/business_ops_ledger.sqlite"),
        allowed_commands=("rg", "sed", "python -m py_compile", "python -m pytest tests/test_openclaw_lm_child_package_gate.py"),
        forbidden_actions=FORBIDDEN_ACTIONS_BASE,
        required_tests=("tests/test_openclaw_lm_child_package_gate.py",),
        expected_outputs=("read_model_json", "operator_markdown", "sqlite_contract_registry", "test_results"),
        authority_profile_ref="default_no_spawn",
        guardian_required=False,
        live_action_authority=False,
        status="CONTRACT_ONLY",
        package_depth=0,
        source_refs=("generated/read_models/openclaw_authority_semantics_registry.json",),
    )
    return replace(package, **overrides)


def seed_lm_packages() -> tuple[LMPackage, ...]:
    default = default_lm_package()
    audit = default_lm_package(
        package_ref="lm_package:audit_child_parent",
        mission="Allow one read-only audit child to inspect contract files and emit a receipt.",
        budget_limit=200,
        authority_profile_ref="audit_child_allowed",
        allowed_files=("openclaw_lm_child_package_gate.py", "tests/test_openclaw_lm_child_package_gate.py", "generated/read_models/openclaw_lm_child_package_gate.json"),
        allowed_commands=("rg", "sed", "python -m py_compile"),
    )
    test_writer = default_lm_package(
        package_ref="lm_package:test_writer_child_parent",
        mission="Allow one child to edit test files only when the parent package permits it.",
        budget_limit=300,
        authority_profile_ref="test_writer_child_allowed",
        allowed_files=("tests/test_openclaw_lm_child_package_gate.py",),
        allowed_commands=("python -m pytest tests/test_openclaw_lm_child_package_gate.py", "python -m py_compile"),
    )
    implementation = default_lm_package(
        package_ref="lm_package:implementation_child_parent",
        mission="Prepare source implementation child package, blocked until Guardian approves.",
        budget_limit=500,
        authority_profile_ref="implementation_child_requires_guardian",
        allowed_files=("openclaw_lm_child_package_gate.py",),
        allowed_commands=("python -m py_compile openclaw_lm_child_package_gate.py",),
        guardian_required=True,
        status="WAITING_GUARDIAN",
    )
    live_action = default_lm_package(
        package_ref="lm_package:live_action_child_forbidden_parent",
        mission="Document that live business-action children remain forbidden.",
        budget_limit=0,
        authority_profile_ref="live_action_child_forbidden",
        allowed_files=(),
        allowed_commands=(),
        guardian_required=True,
        status="BLOCKED",
    )
    return (default, audit, test_writer, implementation, live_action)


def seed_child_spawn_policies() -> tuple[ChildSpawnPolicy, ...]:
    return (
        ChildSpawnPolicy(
            policy_ref="default_no_spawn",
            parent_model_class="LM2",
            child_model_class="ANY_CHILD",
            spawn_allowed=False,
            max_children=0,
            max_depth=0,
            max_total_budget=0,
            allowed_child_task_types=(),
            forbidden_child_task_types=("audit_read_only", "test_write", "implementation_scoped", "live_action", "swarm", "recursive_spawn"),
            requires_guardian_approval=False,
            requires_operator_approval=False,
            policy_status="DEFAULT_DENY",
        ),
        ChildSpawnPolicy(
            policy_ref="audit_child_allowed",
            parent_model_class="LM2",
            child_model_class="AUDIT_CHILD",
            spawn_allowed=True,
            max_children=1,
            max_depth=1,
            max_total_budget=200,
            allowed_child_task_types=("audit_read_only",),
            forbidden_child_task_types=("test_write", "implementation_scoped", "file_edit", "service_start", "live_action", "swarm", "recursive_spawn"),
            requires_guardian_approval=False,
            requires_operator_approval=False,
            policy_status="CONTRACT_ONLY_READ_ONLY",
        ),
        ChildSpawnPolicy(
            policy_ref="test_writer_child_allowed",
            parent_model_class="LM2",
            child_model_class="TEST_WRITER_CHILD",
            spawn_allowed=True,
            max_children=1,
            max_depth=1,
            max_total_budget=300,
            allowed_child_task_types=("test_write",),
            forbidden_child_task_types=("source_change", "implementation_scoped", "service_start", "live_action", "swarm", "recursive_spawn"),
            requires_guardian_approval=False,
            requires_operator_approval=False,
            policy_status="CONTRACT_ONLY_TEST_FILES",
        ),
        ChildSpawnPolicy(
            policy_ref="implementation_child_requires_guardian",
            parent_model_class="LM2",
            child_model_class="IMPLEMENTATION_CHILD",
            spawn_allowed=True,
            max_children=1,
            max_depth=1,
            max_total_budget=500,
            allowed_child_task_types=("implementation_scoped",),
            forbidden_child_task_types=("unscoped_source_change", "service_start", "live_action", "swarm", "recursive_spawn"),
            requires_guardian_approval=True,
            requires_operator_approval=False,
            policy_status="CONTRACT_ONLY_REQUIRES_GUARDIAN",
        ),
        ChildSpawnPolicy(
            policy_ref="live_action_child_forbidden",
            parent_model_class="LM2",
            child_model_class="LIVE_ACTION_CHILD",
            spawn_allowed=False,
            max_children=0,
            max_depth=0,
            max_total_budget=0,
            allowed_child_task_types=(),
            forbidden_child_task_types=("email", "gmail", "browser", "coupa", "workbook", "pdf", "ledger", "external_action", "production_mutation", "swarm"),
            requires_guardian_approval=True,
            requires_operator_approval=True,
            policy_status="FORBIDDEN",
        ),
    )


def _seed_parent(ref: str) -> LMPackage:
    packages = {package.package_ref: package for package in seed_lm_packages()}
    return packages[ref]


def seed_child_package_requests() -> tuple[ChildPackageRequest, ...]:
    return (
        ChildPackageRequest(
            request_ref="child_request:audit_read_only",
            parent_package_ref="lm_package:audit_child_parent",
            proposed_child_package_ref="lm_package:child:audit_read_only",
            reason="Inspect package-gate files for schema and authority boundary consistency.",
            requested_model_class="AUDIT_CHILD",
            requested_budget=100,
            requested_files=("openclaw_lm_child_package_gate.py",),
            requested_commands=("rg",),
            requested_authority=(),
            guardian_status="NOT_REQUIRED",
            child_task_type="audit_read_only",
            requested_depth=1,
        ),
        ChildPackageRequest(
            request_ref="child_request:forbidden_file_scope",
            parent_package_ref="lm_package:audit_child_parent",
            proposed_child_package_ref="lm_package:child:forbidden_scope",
            reason="Attempt to inspect forbidden credential scope.",
            requested_model_class="AUDIT_CHILD",
            requested_budget=100,
            requested_files=(".chief.env",),
            requested_commands=("rg",),
            requested_authority=(),
            guardian_status="NOT_REQUIRED",
            child_task_type="audit_read_only",
            requested_depth=1,
        ),
        ChildPackageRequest(
            request_ref="child_request:forbidden_live_authority",
            parent_package_ref="lm_package:audit_child_parent",
            proposed_child_package_ref="lm_package:child:forbidden_authority",
            reason="Attempt to request ledger, email, and browser authority.",
            requested_model_class="AUDIT_CHILD",
            requested_budget=100,
            requested_files=("openclaw_lm_child_package_gate.py",),
            requested_commands=("rg",),
            requested_authority=("ledger_post_allowed", "email_send_allowed", "browser_access_allowed"),
            guardian_status="NOT_REQUIRED",
            child_task_type="audit_read_only",
            requested_depth=1,
        ),
        ChildPackageRequest(
            request_ref="child_request:implementation_requires_guardian",
            parent_package_ref="lm_package:implementation_child_parent",
            proposed_child_package_ref="lm_package:child:implementation_scoped",
            reason="Propose a source implementation child package after Guardian review.",
            requested_model_class="IMPLEMENTATION_CHILD",
            requested_budget=200,
            requested_files=("openclaw_lm_child_package_gate.py",),
            requested_commands=("python -m py_compile openclaw_lm_child_package_gate.py",),
            requested_authority=(),
            guardian_status="PENDING",
            child_task_type="implementation_scoped",
            requested_depth=1,
        ),
    )


def seed_package_receipts() -> tuple[PackageReceipt, ...]:
    return (
        PackageReceipt(
            receipt_ref="package_receipt:child_audit_read_only_fixture",
            package_ref="lm_package:child:audit_read_only",
            worker_ref="worker:contract_fixture_only_no_runtime_spawn",
            result_status="PASS",
            files_changed=(),
            tests_run=("tests/test_openclaw_lm_child_package_gate.py::test_allowed_audit_package_can_spawn_one_read_only_child",),
            boundary_check="PASS_READ_ONLY_NO_LIVE_ACTION",
            child_packages_spawned=(),
            budget_used=40,
            proof_refs=("generated/read_models/openclaw_lm_child_package_gate.json#package_receipt:child_audit_read_only_fixture",),
        ),
    )


def _policy_for_parent(
    parent_package: LMPackage | Mapping[str, Any],
    policies: Sequence[ChildSpawnPolicy] | None = None,
) -> ChildSpawnPolicy:
    parent = _package_from(parent_package)
    by_ref = {policy.policy_ref: policy for policy in (policies or seed_child_spawn_policies())}
    return by_ref.get(parent.authority_profile_ref, by_ref["default_no_spawn"])


def _package_from(value: LMPackage | Mapping[str, Any]) -> LMPackage:
    if isinstance(value, LMPackage):
        return value
    payload = dict(value)
    tuple_fields = {
        "allowed_files",
        "forbidden_files",
        "allowed_commands",
        "forbidden_actions",
        "required_tests",
        "expected_outputs",
        "stop_conditions",
        "source_refs",
    }
    for field in tuple_fields:
        payload[field] = _tuple(payload.get(field))
    payload["budget_limit"] = int(payload.get("budget_limit") or 0)
    payload["guardian_required"] = bool(payload.get("guardian_required"))
    payload["live_action_authority"] = bool(payload.get("live_action_authority"))
    payload["package_depth"] = int(payload.get("package_depth") or 0)
    payload["child_receipt_required"] = bool(payload.get("child_receipt_required", True))
    return LMPackage(**{field: payload.get(field) for field in LM_PACKAGE_FIELDS})


def _request_from(value: ChildPackageRequest | Mapping[str, Any]) -> ChildPackageRequest:
    if isinstance(value, ChildPackageRequest):
        return value
    payload = dict(value)
    for field in ("requested_files", "requested_commands", "requested_authority", "stop_conditions", "validation_reasons"):
        payload[field] = _tuple(payload.get(field))
    payload["requested_budget"] = int(payload.get("requested_budget") or 0)
    payload["requested_depth"] = int(payload.get("requested_depth") or 0)
    payload["receipt_required"] = bool(payload.get("receipt_required", True))
    return ChildPackageRequest(**{field: payload.get(field) for field in CHILD_PACKAGE_REQUEST_FIELDS})


def _matches_allowed_file(path: str, allowed: Sequence[str]) -> bool:
    if not allowed:
        return False
    normalized = path.strip()
    for candidate in allowed:
        item = candidate.strip()
        if item in {"*", "**/*"}:
            return True
        if item.endswith("/"):
            if normalized.startswith(item):
                return True
            continue
        if "*" in item:
            left, _, right = item.partition("*")
            if normalized.startswith(left) and normalized.endswith(right):
                return True
            continue
        if normalized == item or normalized.startswith(item.rstrip("/") + "/"):
            return True
    return False


def _hits_forbidden_file(path: str, forbidden: Sequence[str]) -> bool:
    lowered = path.lower()
    if any(marker in lowered for marker in FORBIDDEN_FILE_MARKERS):
        return True
    for candidate in forbidden:
        item = candidate.lower().strip()
        if not item:
            continue
        if item.endswith("/"):
            if lowered.startswith(item):
                return True
            continue
        if "*" in item:
            left, _, right = item.partition("*")
            if lowered.startswith(left) and lowered.endswith(right):
                return True
            continue
        if lowered == item or item in lowered:
            return True
    return False


def _command_allowed(command: str, allowed_commands: Sequence[str]) -> bool:
    normalized = command.strip()
    for allowed in allowed_commands:
        item = allowed.strip()
        if not item:
            continue
        if normalized == item or normalized.startswith(item + " "):
            return True
    return False


def _authority_denied(requested_authority: Sequence[str]) -> tuple[str, ...]:
    denied: list[str] = []
    for authority in requested_authority:
        normalized = _norm(authority)
        if normalized in FORBIDDEN_CHILD_AUTHORITIES:
            denied.append(str(authority))
            continue
        if any(token in normalized for token in ("email", "gmail", "browser", "coupa", "workbook", "spreadsheet", "pdf", "ledger", "credential", "network", "production", "external_action", "send_submit")):
            denied.append(str(authority))
    return tuple(dict.fromkeys(denied))


def _gate_decision(
    *,
    package_ref: str,
    request_ref: str,
    decision: str,
    reasons: Sequence[str],
    source_refs: Sequence[str],
) -> PackageGateDecision:
    reason = " ".join(str(item).strip() for item in reasons if str(item).strip()) or "No reason supplied."
    return PackageGateDecision(
        decision_ref=f"package_gate_decision:{_short_hash(package_ref, request_ref, decision, reason)}",
        package_ref=package_ref,
        request_ref=request_ref,
        decision=decision,
        reason=reason,
        source_refs=tuple(source_refs),
    )


def validate_child_package_request(
    *,
    parent_package: LMPackage | Mapping[str, Any],
    child_request: ChildPackageRequest | Mapping[str, Any],
    policies: Sequence[ChildSpawnPolicy] | None = None,
    sibling_count: int = 1,
    guardian_approved: bool = False,
    operator_approved: bool = False,
) -> PackageGateDecision:
    parent = _package_from(parent_package)
    request = _request_from(child_request)
    policy = _policy_for_parent(parent, policies)
    reasons: list[str] = []
    source_refs = (
        "openclaw_lm_child_package_gate.py",
        "generated/read_models/openclaw_authority_semantics_registry.json",
        "generated/read_models/openclaw_lane_capability_harvest.json",
    )

    if request.parent_package_ref != parent.package_ref:
        reasons.append("Child request parent_package_ref does not match the parent package.")
    if not request.proposed_child_package_ref:
        reasons.append("Child request must name a proposed child package ref; hidden children are forbidden.")
    if not request.reason.strip():
        reasons.append("Child request must state a delegation reason.")
    if not request.stop_conditions:
        reasons.append("Child package must define stop conditions.")
    if not request.receipt_required:
        reasons.append("Child package must require a receipt.")
    if parent.live_action_authority:
        reasons.append("Parent package has live_action_authority=true, which is forbidden for this v0 gate.")

    if not policy.spawn_allowed or policy.max_children <= 0:
        reasons.append("Parent package policy does not allow child spawning.")
    if policy.parent_model_class != parent.model_class:
        reasons.append("Child spawn policy parent model class does not match the parent package.")
    if policy.child_model_class not in {"ANY_CHILD", request.requested_model_class}:
        reasons.append("Requested child model class is not allowed by the parent policy.")
    if sibling_count > policy.max_children:
        reasons.append("Requested child package count exceeds policy max_children.")
    if request.requested_depth > policy.max_depth:
        reasons.append("Requested child depth exceeds policy max_depth.")
    if request.child_task_type not in policy.allowed_child_task_types:
        reasons.append("Requested child task type is not allowed by the policy.")
    if _norm(request.child_task_type) in {_norm(item) for item in policy.forbidden_child_task_types}:
        reasons.append("Requested child task type is explicitly forbidden by the policy.")

    if reasons:
        return _gate_decision(
            package_ref=parent.package_ref,
            request_ref=request.request_ref,
            decision="BLOCK",
            reasons=reasons,
            source_refs=source_refs,
        )

    if request.requested_budget > parent.budget_limit or request.requested_budget > policy.max_total_budget:
        return _gate_decision(
            package_ref=parent.package_ref,
            request_ref=request.request_ref,
            decision="BUDGET_EXCEEDED",
            reasons=(
                f"Requested child budget {request.requested_budget} exceeds parent/policy budget limits.",
                "Parent package must account for child budget before delegation.",
            ),
            source_refs=source_refs,
        )

    denied_authority = _authority_denied(request.requested_authority)
    if denied_authority:
        return _gate_decision(
            package_ref=parent.package_ref,
            request_ref=request.request_ref,
            decision="AUTHORITY_DENIED",
            reasons=(
                "Child package requested forbidden authority: " + ", ".join(denied_authority) + ".",
                "Email/Gmail/browser/Coupa/workbook/PDF/ledger/live-action authorities remain forbidden in v0.",
            ),
            source_refs=source_refs,
        )

    forbidden_files = [path for path in request.requested_files if _hits_forbidden_file(path, parent.forbidden_files)]
    if forbidden_files:
        reasons.append("Child package requested forbidden file scope: " + ", ".join(forbidden_files) + ".")
    scope_expansions = [path for path in request.requested_files if not _matches_allowed_file(path, parent.allowed_files)]
    if scope_expansions and not (guardian_approved or operator_approved):
        reasons.append("Child package requested file scope outside the parent package: " + ", ".join(scope_expansions) + ".")

    disallowed_commands = [command for command in request.requested_commands if not _command_allowed(command, parent.allowed_commands)]
    if disallowed_commands:
        reasons.append("Child package requested command outside the parent package: " + ", ".join(disallowed_commands) + ".")
    command_text = " ".join(request.requested_commands).lower()
    forbidden_actions = [action for action in parent.forbidden_actions if action.replace("_", " ") in command_text or action in command_text]
    if forbidden_actions:
        reasons.append("Child command implies forbidden action: " + ", ".join(forbidden_actions) + ".")

    if reasons:
        return _gate_decision(
            package_ref=parent.package_ref,
            request_ref=request.request_ref,
            decision="BLOCK",
            reasons=reasons,
            source_refs=source_refs,
        )

    if (parent.guardian_required or policy.requires_guardian_approval) and request.guardian_status != "APPROVED" and not guardian_approved:
        return _gate_decision(
            package_ref=parent.package_ref,
            request_ref=request.request_ref,
            decision="REQUIRE_GUARDIAN",
            reasons=("Guardian approval is required before this child package can proceed.",),
            source_refs=source_refs,
        )

    if policy.requires_operator_approval and not operator_approved:
        return _gate_decision(
            package_ref=parent.package_ref,
            request_ref=request.request_ref,
            decision="REQUIRE_OPERATOR",
            reasons=("Operator approval is required before this child package can proceed.",),
            source_refs=source_refs,
        )

    return _gate_decision(
        package_ref=parent.package_ref,
        request_ref=request.request_ref,
        decision="ALLOW",
        reasons=("Child package request is within policy, budget, file, command, authority, depth, and receipt boundaries.",),
        source_refs=source_refs,
    )


def package_receipt_refs_for(receipts: Sequence[PackageReceipt | Mapping[str, Any]]) -> set[str]:
    refs: set[str] = set()
    for receipt in receipts:
        payload = asdict(receipt) if isinstance(receipt, PackageReceipt) else dict(receipt)
        package_ref = str(payload.get("package_ref") or "")
        if package_ref:
            refs.add(package_ref)
    return refs


def parent_close_decision(
    *,
    parent_package: LMPackage | Mapping[str, Any],
    child_package_refs: Sequence[str],
    receipts: Sequence[PackageReceipt | Mapping[str, Any]],
) -> PackageGateDecision:
    parent = _package_from(parent_package)
    if parent.child_receipt_required:
        receipt_packages = package_receipt_refs_for(receipts)
        missing = tuple(ref for ref in child_package_refs if ref not in receipt_packages)
        if missing:
            return _gate_decision(
                package_ref=parent.package_ref,
                request_ref="",
                decision="BLOCK",
                reasons=("Parent package cannot close before child receipts exist: " + ", ".join(missing) + ".",),
                source_refs=("openclaw_lm_child_package_gate.py",),
            )
    return _gate_decision(
        package_ref=parent.package_ref,
        request_ref="",
        decision="ALLOW",
        reasons=("Parent package can close because required child receipts are present.",),
        source_refs=("openclaw_lm_child_package_gate.py",),
    )


def _with_validation(request: ChildPackageRequest, decision: PackageGateDecision) -> ChildPackageRequest:
    status = decision.decision if decision.decision in VALIDATION_STATUSES else "BLOCK"
    return replace(
        request,
        validation_status=status,
        validation_reasons=(decision.reason,),
    )


def _seed_decisions(
    packages: Sequence[LMPackage],
    requests: Sequence[ChildPackageRequest],
    policies: Sequence[ChildSpawnPolicy],
) -> tuple[PackageGateDecision, ...]:
    by_ref = {package.package_ref: package for package in packages}
    decisions: list[PackageGateDecision] = []
    for request in requests:
        parent = by_ref[request.parent_package_ref]
        decisions.append(
            validate_child_package_request(
                parent_package=parent,
                child_request=request,
                policies=policies,
                sibling_count=1,
            )
        )
    close_without_receipt = parent_close_decision(
        parent_package=by_ref["lm_package:audit_child_parent"],
        child_package_refs=("lm_package:child:audit_read_only",),
        receipts=(),
    )
    close_with_receipt = parent_close_decision(
        parent_package=by_ref["lm_package:audit_child_parent"],
        child_package_refs=("lm_package:child:audit_read_only",),
        receipts=seed_package_receipts(),
    )
    decisions.extend((close_without_receipt, close_with_receipt))
    return tuple(decisions)


def _schema_description() -> dict[str, Any]:
    return {
        "lm_package": list(LM_PACKAGE_FIELDS),
        "child_spawn_policy": list(CHILD_SPAWN_POLICY_FIELDS),
        "child_package_request": list(CHILD_PACKAGE_REQUEST_FIELDS),
        "package_receipt": list(PACKAGE_RECEIPT_FIELDS),
        "package_gate_decision": list(PACKAGE_GATE_DECISION_FIELDS),
    }


def build_lm_child_package_gate(
    *,
    read_model_root: str | Path = DEFAULT_READ_MODEL_ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated = generated_at or utc_now()
    input_manifest, source_payloads = _source_manifest(read_model_root)
    packages = seed_lm_packages()
    policies = seed_child_spawn_policies()
    seed_requests = seed_child_package_requests()
    decisions = _seed_decisions(packages, seed_requests, policies)
    decisions_by_request = {decision.request_ref: decision for decision in decisions if decision.request_ref}
    requests = tuple(_with_validation(request, decisions_by_request[request.request_ref]) for request in seed_requests)
    receipts = seed_package_receipts()
    present_inputs = [row["input_ref"] for row in input_manifest if row["status"] == "PRESENT"]
    read_model: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "contract_status": CONTRACT_STATUS,
        "generated_at": generated,
        "readiness": READINESS,
        "chain": {
            "name": "LM Gate -> SQLite Package Gate -> LM2 -> Guardian -> Child Worker",
            "runtime_activation_allowed": False,
            "child_spawning_enabled": False,
            "sqlite_gate_is_contract_read_model_only": True,
        },
        "package_gate_shape": _schema_description(),
        "default_limits": {
            "max_children": 0,
            "max_depth": 0,
            "live_action_authority": False,
            "recursive_spawning": False,
            "swarm_mode": False,
            "production_mutation": False,
            "hidden_children": False,
        },
        "guardian_requirements": {
            "guardian_required_package_blocks_without_approval": True,
            "implementation_child_requires_guardian": True,
            "scope_expansion_requires_guardian_or_operator": True,
            "guardian_approval_is_not_live_action_authority": True,
        },
        "budget_controls": {
            "parent_package_must_account_for_child_budget": True,
            "policy_max_total_budget_enforced": True,
            "request_budget_must_not_exceed_parent_budget": True,
            "budget_exceeded_decision": "BUDGET_EXCEEDED",
        },
        "forbidden_delegation_rules": {
            "email_gmail_browser_coupa_workbook_pdf_ledger_forbidden": True,
            "live_business_actions_forbidden": True,
            "services_forbidden": True,
            "production_mutation_forbidden": True,
            "no_recursive_spawning_by_default": True,
            "no_swarm_mode": True,
            "no_hidden_children": True,
        },
        "allowed_delegation_rules": {
            "audit_child_allowed": "Read-only inspection, no edits, no services, no live actions.",
            "test_writer_child_allowed": "Test-file edits only when parent package permits the test file scope.",
            "implementation_child_requires_guardian": "Source edits require explicit package scope and Guardian approval.",
            "live_action_child_forbidden": "Live business actions remain forbidden.",
        },
        "input_manifest": input_manifest,
        "source_integration_summary": {
            "authority_semantics_registry_present": "authority_semantics_registry" in present_inputs,
            "lane_capability_harvest_present": "lane_capability_harvest" in present_inputs,
            "hermes_chief_readback_present": any(ref in present_inputs for ref in ("hermes_chief_build_handoff", "hermes_mission_sentinel", "chief_test_harness_cross_off_receipt_contract")),
            "business_object_audit_present": "business_object_layer_audit" in present_inputs,
            "source_schemas": {
                ref: payload.get("schema_version", "")
                for ref, payload in source_payloads.items()
            },
        },
        "lm_packages": tuple(_asdict(package) for package in packages),
        "child_spawn_policies": tuple(_asdict(policy) for policy in policies),
        "child_package_requests": tuple(_asdict(request) for request in requests),
        "package_receipts": tuple(_asdict(receipt) for receipt in receipts),
        "package_gate_decisions": tuple(_asdict(decision) for decision in decisions),
        "evals": (
            "default package cannot spawn children",
            "allowed audit package can spawn one read-only child",
            "child requesting forbidden file scope is blocked",
            "child requesting ledger/email/browser authority is blocked",
            "child depth over max_depth is blocked",
            "max_children enforced",
            "guardian_required package cannot proceed without Guardian status",
            "child receipt required before parent can close",
            "no live_action_authority by default",
            "JSON parses and SQLite integrity passes",
        ),
        "operator_next_safe_move": "Use this gate as a contract/read-model only. Do not enable runtime child spawning until a future activation task explicitly wires receipts, Guardian approval, and budget accounting.",
        "machine_proof": {
            "contract_only": True,
            "child_spawning_enabled": False,
            "runtime_swarm_enabled": False,
            "recursive_spawning_enabled": False,
            "hidden_children_allowed": False,
            "default_max_children_zero": True,
            "default_max_depth_zero": True,
            "default_live_action_authority_false": True,
            "child_receipts_required": True,
            "lm_called": False,
            "children_spawned": False,
            "chief_launched": False,
            "services_started": False,
            "email_accessed": False,
            "gmail_accessed": False,
            "browser_accessed": False,
            "coupa_accessed": False,
            "workbook_cells_read": False,
            "pdf_exported": False,
            "ledger_mutated": False,
            "production_state_mutated": False,
            "git_push_performed": False,
            "required_sqlite_tables": REQUIRED_SQLITE_TABLES,
            "content_hash": "",
        },
    }
    read_model["machine_proof"]["content_hash"] = _content_hash(read_model)
    return read_model


def operator_markdown(read_model: Mapping[str, Any]) -> str:
    policy_count = len(read_model.get("child_spawn_policies", ()))
    package_count = len(read_model.get("lm_packages", ()))
    decisions = read_model.get("package_gate_decisions", ())
    decision_counts: dict[str, int] = {}
    for decision in decisions:
        decision_counts[str(decision.get("decision", "UNKNOWN"))] = decision_counts.get(str(decision.get("decision", "UNKNOWN")), 0) + 1
    lines = [
        "# OpenClaw LM Child Package Gate",
        "",
        f"- Readiness: `{read_model.get('readiness', 'UNKNOWN')}`",
        f"- Contract status: `{read_model.get('contract_status', 'UNKNOWN')}`",
        "- Runtime child spawning: `false`",
        "- Swarm mode: `false`",
        "- Live action authority default: `false`",
        "",
        "## Package Gate Shape",
        "",
        "- `lm_package` defines parent/child package scope, budget, authority, tests, outputs, and stop conditions.",
        "- `child_spawn_policy` defines whether any child can be requested, plus max children, depth, and budget.",
        "- `child_package_request` is the only visible request path for a child package.",
        "- `package_receipt` is required before parent closure can rely on child work.",
        "- `package_gate_decision` records allow/block/Guardian/operator/budget/authority outcomes.",
        "",
        "## Child Spawn Policy",
        "",
        f"- Packages seeded: `{package_count}`",
        f"- Policies seeded: `{policy_count}`",
        "- Default policy: `max_children=0`, `max_depth=0`, `spawn_allowed=false`.",
        "- Audit child: read-only inspection only.",
        "- Test-writer child: test files only.",
        "- Implementation child: Guardian required.",
        "- Live-action child: forbidden.",
        "",
        "## Guardian Requirements",
        "",
        "- Guardian is required for implementation children and scope/authority escalation.",
        "- Guardian approval does not grant live business action authority.",
        "- Operator approval is separate and required only when a policy explicitly says so.",
        "",
        "## Decisions",
        "",
    ]
    for key in sorted(decision_counts):
        lines.append(f"- `{key}`: `{decision_counts[key]}`")
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            "- No LM call, child spawn, Chief launch, service start, email/Gmail/browser/Coupa access, workbook cell read, PDF export, ledger mutation, production mutation, or push.",
            "- This is readiness/contract work only.",
            "",
        ]
    )
    return "\n".join(lines)


def sqlite_schema_sql() -> str:
    return """
CREATE TABLE lm_package (
  package_ref TEXT PRIMARY KEY,
  parent_package_ref TEXT NOT NULL,
  mission TEXT NOT NULL,
  model_class TEXT NOT NULL,
  budget_limit INTEGER NOT NULL CHECK(budget_limit >= 0),
  allowed_files TEXT NOT NULL,
  forbidden_files TEXT NOT NULL,
  allowed_commands TEXT NOT NULL,
  forbidden_actions TEXT NOT NULL,
  required_tests TEXT NOT NULL,
  expected_outputs TEXT NOT NULL,
  authority_profile_ref TEXT NOT NULL,
  guardian_required INTEGER NOT NULL CHECK(guardian_required IN (0, 1)),
  live_action_authority INTEGER NOT NULL DEFAULT 0 CHECK(live_action_authority IN (0, 1)),
  status TEXT NOT NULL,
  package_depth INTEGER NOT NULL DEFAULT 0 CHECK(package_depth >= 0),
  stop_conditions TEXT NOT NULL,
  child_receipt_required INTEGER NOT NULL DEFAULT 1 CHECK(child_receipt_required IN (0, 1)),
  source_refs TEXT NOT NULL
);

CREATE TABLE child_spawn_policy (
  policy_ref TEXT PRIMARY KEY,
  parent_model_class TEXT NOT NULL,
  child_model_class TEXT NOT NULL,
  spawn_allowed INTEGER NOT NULL DEFAULT 0 CHECK(spawn_allowed IN (0, 1)),
  max_children INTEGER NOT NULL DEFAULT 0 CHECK(max_children >= 0),
  max_depth INTEGER NOT NULL DEFAULT 0 CHECK(max_depth >= 0),
  max_total_budget INTEGER NOT NULL DEFAULT 0 CHECK(max_total_budget >= 0),
  allowed_child_task_types TEXT NOT NULL,
  forbidden_child_task_types TEXT NOT NULL,
  requires_guardian_approval INTEGER NOT NULL CHECK(requires_guardian_approval IN (0, 1)),
  requires_operator_approval INTEGER NOT NULL CHECK(requires_operator_approval IN (0, 1)),
  policy_status TEXT NOT NULL
);

CREATE TABLE child_package_request (
  request_ref TEXT PRIMARY KEY,
  parent_package_ref TEXT NOT NULL,
  proposed_child_package_ref TEXT NOT NULL,
  reason TEXT NOT NULL,
  requested_model_class TEXT NOT NULL,
  requested_budget INTEGER NOT NULL CHECK(requested_budget >= 0),
  requested_files TEXT NOT NULL,
  requested_commands TEXT NOT NULL,
  requested_authority TEXT NOT NULL,
  validation_status TEXT NOT NULL,
  guardian_status TEXT NOT NULL,
  child_task_type TEXT NOT NULL,
  requested_depth INTEGER NOT NULL CHECK(requested_depth >= 0),
  stop_conditions TEXT NOT NULL,
  receipt_required INTEGER NOT NULL CHECK(receipt_required IN (0, 1)),
  validation_reasons TEXT NOT NULL
);

CREATE TABLE package_receipt (
  receipt_ref TEXT PRIMARY KEY,
  package_ref TEXT NOT NULL,
  worker_ref TEXT NOT NULL,
  result_status TEXT NOT NULL,
  files_changed TEXT NOT NULL,
  tests_run TEXT NOT NULL,
  boundary_check TEXT NOT NULL,
  child_packages_spawned TEXT NOT NULL,
  budget_used INTEGER NOT NULL CHECK(budget_used >= 0),
  proof_refs TEXT NOT NULL
);

CREATE TABLE package_gate_decision (
  decision_ref TEXT PRIMARY KEY,
  package_ref TEXT NOT NULL,
  decision TEXT NOT NULL CHECK(decision IN ('ALLOW', 'BLOCK', 'REQUIRE_GUARDIAN', 'REQUIRE_OPERATOR', 'BUDGET_EXCEEDED', 'AUTHORITY_DENIED')),
  reason TEXT NOT NULL,
  source_refs TEXT NOT NULL,
  request_ref TEXT NOT NULL
);
""".lstrip()


def _sql_literal(value: Any) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, (list, tuple, dict)):
        value = _compact_json(value)
    return "'" + str(value).replace("'", "''") + "'"


def _sqlite_value(value: Any) -> Any:
    if isinstance(value, bool):
        return 1 if value else 0
    if isinstance(value, (list, tuple, dict)):
        return _compact_json(value)
    return value


def _rows_by_table(read_model: Mapping[str, Any]) -> dict[str, tuple[dict[str, Any], ...]]:
    return {
        "lm_package": tuple(dict(row) for row in read_model["lm_packages"]),
        "child_spawn_policy": tuple(dict(row) for row in read_model["child_spawn_policies"]),
        "child_package_request": tuple(dict(row) for row in read_model["child_package_requests"]),
        "package_receipt": tuple(dict(row) for row in read_model["package_receipts"]),
        "package_gate_decision": tuple(dict(row) for row in read_model["package_gate_decisions"]),
    }


def sqlite_seed_sql(read_model: Mapping[str, Any]) -> str:
    statements: list[str] = []
    for table in REQUIRED_SQLITE_TABLES:
        for row in _rows_by_table(read_model)[table]:
            columns = list(row)
            statements.append(
                f"INSERT INTO {table} ({', '.join(columns)}) "
                f"VALUES ({', '.join(_sql_literal(row[column]) for column in columns)});"
            )
    return "\n".join(statements) + "\n"


def create_sqlite_registry(read_model: Mapping[str, Any], sqlite_path: str | Path) -> None:
    path = _rooted(sqlite_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    rows_by_table = _rows_by_table(read_model)
    connection = sqlite3.connect(path)
    try:
        connection.executescript(sqlite_schema_sql())
        for table in REQUIRED_SQLITE_TABLES:
            for row in rows_by_table[table]:
                columns = list(row)
                placeholders = ", ".join("?" for _ in columns)
                connection.execute(
                    f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders})",
                    [_sqlite_value(row[column]) for column in columns],
                )
        connection.commit()
    finally:
        connection.close()


def export_openclaw_lm_child_package_gate(
    *,
    read_model_root: str | Path = DEFAULT_READ_MODEL_ROOT,
    system_knowledge_root: str | Path = DEFAULT_SYSTEM_KNOWLEDGE_ROOT,
    generated_at: str | None = None,
) -> LMChildPackageGateExportResult:
    read_root = _rooted(read_model_root)
    system_root = _rooted(system_knowledge_root)
    read_model = build_lm_child_package_gate(
        read_model_root=read_model_root,
        generated_at=generated_at,
    )
    json_path = read_root / JSON_EXPORT_NAME
    operator_path = read_root / OPERATOR_EXPORT_NAME
    sqlite_path = system_root / SQLITE_EXPORT_NAME
    schema_path = system_root / SCHEMA_EXPORT_NAME
    seed_path = system_root / SEED_EXPORT_NAME
    _atomic_write_text(json_path, stable_json(read_model))
    _atomic_write_text(operator_path, operator_markdown(read_model))
    _atomic_write_text(schema_path, sqlite_schema_sql())
    _atomic_write_text(seed_path, sqlite_seed_sql(read_model))
    create_sqlite_registry(read_model, sqlite_path)
    return LMChildPackageGateExportResult(
        schema_version=SCHEMA_VERSION,
        json_path=_display_path(json_path),
        operator_path=_display_path(operator_path),
        sqlite_path=_display_path(sqlite_path),
        schema_sql_path=_display_path(schema_path),
        seed_sql_path=_display_path(seed_path),
        package_count=len(read_model["lm_packages"]),
        child_spawn_policy_count=len(read_model["child_spawn_policies"]),
        decision_count=len(read_model["package_gate_decisions"]),
        readiness=str(read_model["readiness"]),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export the OpenClaw LM child package gate contract.")
    parser.add_argument("--read-model-root", default=str(DEFAULT_READ_MODEL_ROOT))
    parser.add_argument("--system-knowledge-root", default=str(DEFAULT_SYSTEM_KNOWLEDGE_ROOT))
    parser.add_argument("--generated-at", default="")
    parser.add_argument("--format", choices=("summary", "json"), default="summary")
    args = parser.parse_args(argv)
    result = export_openclaw_lm_child_package_gate(
        read_model_root=args.read_model_root,
        system_knowledge_root=args.system_knowledge_root,
        generated_at=args.generated_at or None,
    )
    if args.format == "json":
        print(stable_json(asdict(result)), end="")
    else:
        print(f"json={result.json_path}")
        print(f"operator={result.operator_path}")
        print(f"sqlite={result.sqlite_path}")
        print(f"schema={result.schema_sql_path}")
        print(f"seed={result.seed_sql_path}")
        print(f"packages={result.package_count}")
        print(f"child_spawn_policies={result.child_spawn_policy_count}")
        print(f"decisions={result.decision_count}")
        print(f"readiness={result.readiness}")
    return 0 if result.readiness.startswith("READY") else 2


__all__ = [
    "CHILD_PACKAGE_REQUEST_FIELDS",
    "CHILD_SPAWN_POLICY_FIELDS",
    "CONTRACT_STATUS",
    "DECISIONS",
    "DEFAULT_READ_MODEL_ROOT",
    "DEFAULT_SYSTEM_KNOWLEDGE_ROOT",
    "FORBIDDEN_CHILD_AUTHORITIES",
    "JSON_EXPORT_NAME",
    "LM_PACKAGE_FIELDS",
    "OPERATOR_EXPORT_NAME",
    "PACKAGE_GATE_DECISION_FIELDS",
    "PACKAGE_RECEIPT_FIELDS",
    "READINESS",
    "READ_MODEL_ID",
    "REQUIRED_SQLITE_TABLES",
    "SCHEMA_EXPORT_NAME",
    "SCHEMA_VERSION",
    "SEED_EXPORT_NAME",
    "SQLITE_EXPORT_NAME",
    "ChildPackageRequest",
    "ChildSpawnPolicy",
    "LMPackage",
    "LMChildPackageGateExportResult",
    "PackageGateDecision",
    "PackageReceipt",
    "build_lm_child_package_gate",
    "create_sqlite_registry",
    "default_lm_package",
    "export_openclaw_lm_child_package_gate",
    "operator_markdown",
    "package_receipt_refs_for",
    "parent_close_decision",
    "seed_child_package_requests",
    "seed_child_spawn_policies",
    "seed_lm_packages",
    "seed_package_receipts",
    "sqlite_schema_sql",
    "sqlite_seed_sql",
    "stable_json",
    "utc_now",
    "validate_child_package_request",
]


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
