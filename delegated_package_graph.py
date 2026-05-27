"""Delegated package graph v0.

This module adds package-scoped delegation for Repo A packages. A parent role
package may request bounded child packages only when its package carries an
explicit delegation policy. Every child request is deterministically validated,
child work reuses existing offline worker paths, child outputs pass Guardian,
and parent continuation depends on receipt-backed child results.

It does not start Repo B, call models, execute tools, send messages, read
workbook bodies, post ledgers, or mutate production state.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

import guardian_output_gate
import repoa_worker_boundary_harness as worker_harness


SCHEMA_VERSION = "delegated_package_graph_v0"
READ_MODEL_ID = "delegated_package_graph"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
OPERATOR_EXPORT_NAME = f"{READ_MODEL_ID}_OPERATOR.md"
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_DB_PATH = Path(".openclaw/test_harness/delegated_package_graph.sqlite")
DEFAULT_GENERATED_AT = "2026-05-26T00:00:00+00:00"

VALIDATED = "CHILD_PACKAGE_VALIDATED"
BLOCKED = "CHILD_PACKAGE_BLOCKED"
PARENT_VALIDATED = "DELEGATED_PARENT_OUTPUT_VALIDATED"
PARENT_BLOCKED = "DELEGATED_PARENT_OUTPUT_BLOCKED"

ROLE_CHIEF = "CHIEF"
ROLE_CASSANDRA_CLARA = "CASSANDRA_CLARA"

PRIVACY_RANK = {
    "public": 0,
    "low": 0,
    "low_metadata": 0,
    "metadata_only": 1,
    "metadata_only_tokenized_refs": 1,
    "personal": 2,
    "client_finance": 2,
    "client_finance_tokenized": 2,
    "legal_confidential": 3,
    "strict": 4,
    "strict_local_only": 4,
}

NEVER_DELEGATED_AUTHORITIES = {
    "send",
    "send_submit",
    "email",
    "email_send",
    "gmail",
    "gmail_send",
    "submit",
    "coupa",
    "coupa_submit",
    "browser",
    "network",
    "ledger",
    "ledger_posting",
    "tool",
    "tool_execution",
    "workflow",
    "workflow_execution",
    "credential",
    "credential_access",
    "external_action",
}

FORBIDDEN_CONTEXT_REFS = {
    "raw_private_body",
    "raw_workbook_body",
    "spreadsheet_cells",
    "credentials",
    "credential_values",
    "secrets",
    "api_keys",
}


@dataclass(frozen=True)
class DelegationPolicy:
    delegation_allowed: bool
    allowed_child_roles: tuple[str, ...]
    max_child_packages: int
    max_depth: int
    parallel_allowed: bool
    child_tools_allowed: bool
    child_external_actions_allowed: bool
    child_privacy_must_be_same_or_stricter: bool
    parent_may_continue_only_after_child_receipts: bool
    delegation_reason_required: bool
    budget_tokens: int
    budget_cost_class: str
    timeout_policy: str


@dataclass(frozen=True)
class ChildPackageRequest:
    parent_package_id: str
    parent_source_request_id: str
    child_request_id: str
    requested_role_family: str
    requested_task: str
    required_inputs: tuple[str, ...]
    allowed_context_refs: tuple[str, ...]
    forbidden_context_refs: tuple[str, ...]
    requested_tools: tuple[str, ...]
    requested_authority: tuple[str, ...]
    privacy_level: str
    tokenization_required: bool
    output_required: str
    receipt_required: bool
    delegation_reason: str
    depth: int = 1


@dataclass(frozen=True)
class ChildPackageValidationResult:
    validation_result_id: str
    child_request_id: str
    parent_package_id: str
    requested_role_family: str
    verdict: str
    accepted: bool
    blocked_reasons: tuple[str, ...]
    safe_next_move: str


@dataclass(frozen=True)
class PackageLineage:
    parent_package_id: str
    parent_source_request_id: str
    child_package_ids: tuple[str, ...]
    child_receipt_ids: tuple[str, ...]
    parent_receipt_id: str
    final_parent_verdict: str


@dataclass(frozen=True)
class DelegatedPackageGraph:
    graph_run_id: str
    parent_package_id: str
    parent_source_request_id: str
    child_package_ids: tuple[str, ...]
    child_receipt_ids: tuple[str, ...]
    parent_receipt_id: str
    validation_verdicts: tuple[dict[str, Any], ...]
    final_parent_verdict: str
    created_at: str


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _short_hash(*parts: object) -> str:
    return hashlib.sha256("\0".join(str(part) for part in parts).encode("utf-8")).hexdigest()[:16]


def _content_hash(payload: Mapping[str, Any]) -> str:
    clone = json.loads(stable_json(dict(payload)))
    machine = clone.get("machine_proof")
    if isinstance(machine, dict):
        machine.pop("content_hash", None)
    return "sha256:" + hashlib.sha256(stable_json(clone).encode("utf-8")).hexdigest()


def _normalize_tuple(values: Sequence[object] | object) -> tuple[str, ...]:
    if values is None:
        return ()
    if isinstance(values, str):
        return (values,)
    if isinstance(values, Sequence):
        return tuple(str(value) for value in values if str(value or "").strip())
    return (str(values),)


def _role(value: object) -> str:
    return str(value or "").strip().upper().replace("-", "_").replace(" ", "_")


def _privacy_rank(value: object) -> int:
    return PRIVACY_RANK.get(str(value or "").strip().lower(), 1)


def _policy_from_parent(parent_package: Mapping[str, Any]) -> DelegationPolicy | None:
    payload = parent_package.get("delegation_policy")
    if not isinstance(payload, Mapping):
        return None
    return DelegationPolicy(
        delegation_allowed=bool(payload.get("delegation_allowed")),
        allowed_child_roles=tuple(_role(role) for role in payload.get("allowed_child_roles") or ()),
        max_child_packages=int(payload.get("max_child_packages") or 0),
        max_depth=int(payload.get("max_depth") or 0),
        parallel_allowed=bool(payload.get("parallel_allowed")),
        child_tools_allowed=bool(payload.get("child_tools_allowed")),
        child_external_actions_allowed=bool(payload.get("child_external_actions_allowed")),
        child_privacy_must_be_same_or_stricter=bool(payload.get("child_privacy_must_be_same_or_stricter")),
        parent_may_continue_only_after_child_receipts=bool(payload.get("parent_may_continue_only_after_child_receipts")),
        delegation_reason_required=bool(payload.get("delegation_reason_required")),
        budget_tokens=int(payload.get("budget_tokens") or 0),
        budget_cost_class=str(payload.get("budget_cost_class") or "NONE"),
        timeout_policy=str(payload.get("timeout_policy") or "fail_closed"),
    )


def capital_hilton_delegation_policy(*, delegation_allowed: bool = True) -> DelegationPolicy:
    return DelegationPolicy(
        delegation_allowed=delegation_allowed,
        allowed_child_roles=(ROLE_CHIEF, ROLE_CASSANDRA_CLARA),
        max_child_packages=2,
        max_depth=1,
        parallel_allowed=False,
        child_tools_allowed=False,
        child_external_actions_allowed=False,
        child_privacy_must_be_same_or_stricter=True,
        parent_may_continue_only_after_child_receipts=True,
        delegation_reason_required=True,
        budget_tokens=2400,
        budget_cost_class="fixture_only_no_model_cost",
        timeout_policy="fail_closed_without_child_receipt",
    )


def build_capital_hilton_parent_package(
    *,
    source_request_id: str = "delegated_capital_hilton_invoice_package_parent",
    delegation_allowed: bool = True,
) -> dict[str, Any]:
    package_flow = worker_harness.build_cassandra_clara_role_package(
        source_request_id=source_request_id,
        user_message="Prepare the Capital Hilton invoice package.",
        audience="internal",
    )
    role_package = dict(package_flow["role_package"])
    policy = capital_hilton_delegation_policy(delegation_allowed=delegation_allowed)
    context_packet = dict(role_package.get("context_packet") or {})
    context_packet["allowed_delegated_context_refs"] = (
        "client_ref:capital_hilton",
        "workflow_ref:capital_hilton_invoice_workflow",
        "tokenized_invoice_package_metadata",
    )
    role_package.update(
        {
            "role_identity": ROLE_CASSANDRA_CLARA,
            "role_family": ROLE_CASSANDRA_CLARA,
            "internal_role_identity": "CASSANDRA",
            "external_voice_identity": "CLARA",
            "audience": "internal",
            "selected_voice": "CASSANDRA",
            "task": "prepare_invoice_package",
            "delegation_allowed": delegation_allowed,
            "delegation_policy": asdict(policy),
            "context_packet": context_packet,
            "raw_values_included": False,
            "model_may_see_raw_values": False,
            "next_safe_move": "Validate child package requests before any delegated offline worker path runs.",
        }
    )
    return {**package_flow, "role_package": role_package}


def capital_hilton_child_requests(parent_package: Mapping[str, Any]) -> tuple[ChildPackageRequest, ...]:
    parent_package_id = str(parent_package.get("package_id") or "")
    parent_source_request_id = str(parent_package.get("source_request_id") or "")
    common_context = (
        "client_ref:capital_hilton",
        "workflow_ref:capital_hilton_invoice_workflow",
        "tokenized_invoice_package_metadata",
    )
    return (
        ChildPackageRequest(
            parent_package_id=parent_package_id,
            parent_source_request_id=parent_source_request_id,
            child_request_id="delegated_child:chief_status_capital_hilton",
            requested_role_family=ROLE_CHIEF,
            requested_task="status_or_next_safe_move",
            required_inputs=("Capital Hilton invoice package preparation",),
            allowed_context_refs=common_context,
            forbidden_context_refs=("raw_workbook_body", "credentials", "coupa", "gmail"),
            requested_tools=(),
            requested_authority=(),
            privacy_level="metadata_only_tokenized_refs",
            tokenization_required=True,
            output_required="status_summary_and_next_safe_move",
            receipt_required=True,
            delegation_reason="Identify the next safe move and blockers before package preparation continues.",
        ),
        ChildPackageRequest(
            parent_package_id=parent_package_id,
            parent_source_request_id=parent_source_request_id,
            child_request_id="delegated_child:clara_draft_capital_hilton",
            requested_role_family=ROLE_CASSANDRA_CLARA,
            requested_task="comms_draft_or_status",
            required_inputs=("Client-safe draft note about the invoice package",),
            allowed_context_refs=common_context,
            forbidden_context_refs=("raw_workbook_body", "credentials", "coupa", "gmail"),
            requested_tools=(),
            requested_authority=(),
            privacy_level="metadata_only_tokenized_refs",
            tokenization_required=True,
            output_required="client_safe_draft_text",
            receipt_required=True,
            delegation_reason="Prepare Clara draft text for review without sending.",
        ),
    )


def validate_child_package_request(
    *,
    parent_package: Mapping[str, Any],
    child_request: ChildPackageRequest,
    sibling_count: int = 1,
) -> ChildPackageValidationResult:
    reasons: list[str] = []
    policy = _policy_from_parent(parent_package)
    if policy is None:
        reasons.append("Parent package has no delegation policy.")
    elif not policy.delegation_allowed:
        reasons.append("Parent package does not allow delegation.")

    requested_role = _role(child_request.requested_role_family)
    if policy is not None and requested_role not in policy.allowed_child_roles:
        reasons.append("Requested child role is not whitelisted by the parent package.")
    if policy is not None and sibling_count > policy.max_child_packages:
        reasons.append("Requested child package count exceeds parent package limit.")
    if policy is not None and child_request.depth > policy.max_depth:
        reasons.append("Requested child package depth exceeds parent package limit.")
    if policy is not None and policy.delegation_reason_required and not child_request.delegation_reason.strip():
        reasons.append("Delegation reason is required.")

    if policy is not None and policy.child_privacy_must_be_same_or_stricter:
        parent_privacy = parent_package.get("privacy_level") or "metadata_only_tokenized_refs"
        if _privacy_rank(child_request.privacy_level) < _privacy_rank(parent_privacy):
            reasons.append("Child privacy level is weaker than the parent package.")

    if child_request.requested_tools and not (policy and policy.child_tools_allowed):
        reasons.append("Child package requested tools, but parent policy allows no child tools.")
    requested_authority = {_role(value).lower() for value in child_request.requested_authority}
    if requested_authority and not (policy and policy.child_external_actions_allowed):
        reasons.append("Child package requested authority, but parent policy allows no child external actions.")
    if requested_authority.intersection(NEVER_DELEGATED_AUTHORITIES):
        reasons.append("Child package requested send/tool/external authority that cannot be delegated in v0.")

    requested_context = set(child_request.allowed_context_refs)
    parent_context = parent_package.get("context_packet") if isinstance(parent_package.get("context_packet"), Mapping) else {}
    parent_allowed_context = set(parent_context.get("allowed_delegated_context_refs") or ())
    if requested_context - parent_allowed_context:
        reasons.append("Child package requested context not exposed by the parent package.")
    forbidden_context = {str(value).lower() for value in child_request.allowed_context_refs}
    if forbidden_context.intersection(FORBIDDEN_CONTEXT_REFS):
        reasons.append("Child package requested raw/private/credential context.")

    if not child_request.receipt_required:
        reasons.append("Child package must require a receipt.")

    accepted = not reasons
    verdict = VALIDATED if accepted else BLOCKED
    return ChildPackageValidationResult(
        validation_result_id=f"child_package_validation:{_short_hash(child_request.child_request_id, verdict, tuple(reasons))}",
        child_request_id=child_request.child_request_id,
        parent_package_id=child_request.parent_package_id,
        requested_role_family=requested_role,
        verdict=verdict,
        accepted=accepted,
        blocked_reasons=tuple(reasons),
        safe_next_move=(
            "Compile and run the bounded child package through the offline worker path."
            if accepted
            else "Do not compile or run this child package request."
        ),
    )


def validate_child_package_requests(
    *,
    parent_package: Mapping[str, Any],
    child_requests: Sequence[ChildPackageRequest],
) -> tuple[ChildPackageValidationResult, ...]:
    sibling_count = len(child_requests)
    return tuple(
        validate_child_package_request(
            parent_package=parent_package,
            child_request=child_request,
            sibling_count=sibling_count,
        )
        for child_request in child_requests
    )


def _create_graph_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
CREATE TABLE IF NOT EXISTS delegated_package_graph_runs (
  graph_run_id TEXT PRIMARY KEY,
  parent_package_id TEXT NOT NULL,
  parent_source_request_id TEXT NOT NULL,
  child_package_ids_json TEXT NOT NULL,
  child_receipt_ids_json TEXT NOT NULL,
  parent_receipt_id TEXT NOT NULL,
  final_parent_verdict TEXT NOT NULL,
  validation_verdicts_json TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  created_at TEXT NOT NULL
)
"""
    )


def _read_graph_record(db_path: Path, graph_run_id: str) -> dict[str, Any]:
    with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM delegated_package_graph_runs WHERE graph_run_id = ?",
            (graph_run_id,),
        ).fetchone()
    if row is None:
        return {}
    result = dict(row)
    for key in ("child_package_ids_json", "child_receipt_ids_json", "validation_verdicts_json", "payload_json"):
        result[key.removesuffix("_json")] = json.loads(result.pop(key))
    return result


def _record_graph_run(
    *,
    db_path: Path,
    payload: Mapping[str, Any],
    created_at: str,
) -> dict[str, Any]:
    graph_run_id = str(payload["graph_run_id"])
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        worker_harness._create_schema(conn)
        _create_graph_schema(conn)
        conn.execute(
            """
INSERT OR REPLACE INTO delegated_package_graph_runs
  (graph_run_id, parent_package_id, parent_source_request_id, child_package_ids_json,
   child_receipt_ids_json, parent_receipt_id, final_parent_verdict,
   validation_verdicts_json, payload_json, created_at)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
""",
            (
                graph_run_id,
                payload["parent_package_id"],
                payload["parent_source_request_id"],
                stable_json(payload["child_package_ids"]),
                stable_json(payload["child_receipt_ids"]),
                payload["parent_receipt_id"],
                payload["final_parent_verdict"],
                stable_json(payload["validation_verdicts"]),
                stable_json(dict(payload)),
                created_at,
            ),
        )
        conn.commit()
    return _read_graph_record(db_path, graph_run_id)


def _run_validated_child(
    *,
    child_request: ChildPackageRequest,
    db_path: Path,
    created_at: str,
) -> dict[str, Any]:
    role = _role(child_request.requested_role_family)
    if role == ROLE_CHIEF:
        return worker_harness.run_chief_status_worker_path(
            source_request_id=child_request.child_request_id,
            receipt_db_path=db_path,
            created_at=created_at,
        )
    if role == ROLE_CASSANDRA_CLARA:
        return worker_harness.run_cassandra_clara_worker_path(
            source_request_id=child_request.child_request_id,
            user_message="Draft a client-facing note to Hilton about the invoice package.",
            audience="external",
            receipt_db_path=db_path,
            created_at=created_at,
        )
    raise ValueError(f"Unsupported child role: {role}")


def parent_can_continue(
    *,
    parent_package: Mapping[str, Any],
    child_validation_results: Sequence[ChildPackageValidationResult],
    child_receipt_ids: Sequence[str],
) -> dict[str, Any]:
    policy = _policy_from_parent(parent_package)
    accepted_children = [result for result in child_validation_results if result.accepted]
    missing_receipts = max(0, len(accepted_children) - len([receipt for receipt in child_receipt_ids if receipt]))
    blocked_reasons: list[str] = []
    if policy is None or not policy.delegation_allowed:
        blocked_reasons.append("Parent package does not allow delegation.")
    if any(not result.accepted for result in child_validation_results):
        blocked_reasons.append("At least one child package request was blocked.")
    if policy and policy.parent_may_continue_only_after_child_receipts and missing_receipts:
        blocked_reasons.append("Parent package is waiting for required child receipts.")
    return {
        "can_continue": not blocked_reasons,
        "accepted_child_count": len(accepted_children),
        "child_receipt_count": len([receipt for receipt in child_receipt_ids if receipt]),
        "missing_receipt_count": missing_receipts,
        "blocked_reasons": blocked_reasons,
        "safe_next_move": (
            "Validate final parent output with Guardian."
            if not blocked_reasons
            else "Do not let the parent package rely on child work yet."
        ),
    }


def _parent_summary_result(
    *,
    parent_package: Mapping[str, Any],
    child_receipts: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    receipt_refs = ", ".join(str(receipt.get("receipt_id")) for receipt in child_receipts)
    return {
        "schema_version": SCHEMA_VERSION,
        "worker_adapter_id": "delegated_package_graph.parent_summary_v0",
        "result_id": f"delegated_parent_result:{_short_hash(parent_package.get('package_id'), receipt_refs)}",
        "source_package_id": parent_package["package_id"],
        "source_request_id": parent_package["source_request_id"],
        "response_author": ROLE_CASSANDRA_CLARA,
        "role_family": ROLE_CASSANDRA_CLARA,
        "selected_voice": "CASSANDRA",
        "headline": "Package prep readback",
        "one_line_answer": "The Capital Hilton invoice package is still a draft/proposed preparation path.",
        "eliwinship": (
            "Child receipts are present for Chief status and Clara draft checks. No send, Coupa, ledger, "
            "browser, file-body, or workbook-cell step happened."
        ),
        "status_summary": "The parent package may use receipt-backed child results for a local readback only.",
        "draft_text": "",
        "next_action": "Next: review the draft package and ask for approval before any outside step.",
        "next_safe_move": "Return the scoped parent summary after Guardian validation.",
        "action_taken": "none",
        "requested_tool_calls": (),
        "requested_external_actions": (),
        "external_action": False,
        "authority_used": False,
        "authority_boundary": dict(worker_harness.AUTHORITY_BOUNDARY),
    }


def run_capital_hilton_delegated_fixture(
    *,
    db_path: Path = DEFAULT_DB_PATH,
    created_at: str | None = None,
) -> dict[str, Any]:
    created_at = created_at or utc_now()
    parent_flow = build_capital_hilton_parent_package()
    parent_package = parent_flow["role_package"]
    child_requests = capital_hilton_child_requests(parent_package)
    child_validations = validate_child_package_requests(
        parent_package=parent_package,
        child_requests=child_requests,
    )
    child_results: list[dict[str, Any]] = []
    child_receipts: list[dict[str, Any]] = []
    for child_request, validation in zip(child_requests, child_validations, strict=True):
        if not validation.accepted:
            continue
        result = _run_validated_child(
            child_request=child_request,
            db_path=db_path,
            created_at=created_at,
        )
        child_results.append(result)
        child_receipts.append(result["sqlite_receipt"])

    continue_result = parent_can_continue(
        parent_package=parent_package,
        child_validation_results=child_validations,
        child_receipt_ids=tuple(str(receipt.get("receipt_id") or "") for receipt in child_receipts),
    )
    if not continue_result["can_continue"]:
        final_validation = {
            "validation_result": {
                "verdict": PARENT_BLOCKED,
                "blocked_reasons": continue_result["blocked_reasons"],
                "output_publish_allowed": False,
            }
        }
        parent_receipt: dict[str, Any] = {}
        parent_result: dict[str, Any] = {}
    else:
        parent_result = _parent_summary_result(parent_package=parent_package, child_receipts=child_receipts)
        final_validation = worker_harness.validate_worker_result(parent_result, parent_package)
        parent_receipt = worker_harness.record_worker_receipt(
            role_package=parent_package,
            worker_result=parent_result,
            validation_result=final_validation["validation_result"],
            db_path=db_path,
            created_at=created_at,
            receipt_classification="delegated_parent_offline_fixture",
            harness_ref=READ_MODEL_ID,
        )

    child_package_ids = tuple(str(result["role_package"]["package_id"]) for result in child_results)
    child_receipt_ids = tuple(str(receipt.get("receipt_id") or "") for receipt in child_receipts)
    final_verdict = (
        PARENT_VALIDATED
        if final_validation.get("validation_result", {}).get("verdict") == guardian_output_gate.VALIDATED
        else PARENT_BLOCKED
    )
    lineage = PackageLineage(
        parent_package_id=str(parent_package["package_id"]),
        parent_source_request_id=str(parent_package["source_request_id"]),
        child_package_ids=child_package_ids,
        child_receipt_ids=child_receipt_ids,
        parent_receipt_id=str(parent_receipt.get("receipt_id") or ""),
        final_parent_verdict=final_verdict,
    )
    graph_payload = {
        "graph_run_id": f"delegated_package_graph_run:{_short_hash(parent_package['package_id'], child_receipt_ids, final_verdict)}",
        "parent_package_id": lineage.parent_package_id,
        "parent_source_request_id": lineage.parent_source_request_id,
        "child_package_ids": list(lineage.child_package_ids),
        "child_receipt_ids": list(lineage.child_receipt_ids),
        "parent_receipt_id": lineage.parent_receipt_id,
        "final_parent_verdict": lineage.final_parent_verdict,
        "validation_verdicts": [asdict(result) for result in child_validations],
        "parent_may_continue": continue_result,
        "created_at": created_at,
    }
    graph_record = _record_graph_run(db_path=db_path, payload=graph_payload, created_at=created_at)
    return {
        "schema_version": SCHEMA_VERSION,
        "source_request_id": parent_package["source_request_id"],
        "created_at": created_at,
        "db_path": db_path.as_posix(),
        "parent_package": parent_package,
        "delegation_policy": parent_package["delegation_policy"],
        "child_requests": [asdict(request) for request in child_requests],
        "child_validation_results": [asdict(result) for result in child_validations],
        "child_worker_results": child_results,
        "parent_can_continue": continue_result,
        "parent_result": parent_result,
        "final_parent_guardian_validation": final_validation,
        "parent_receipt": parent_receipt,
        "package_lineage": asdict(lineage),
        "graph_record": graph_record,
        "operator_summary": {
            "headline": "Delegated package graph fixture passed",
            "body": (
                "Capital Hilton package prep used bounded Chief and Clara child packages. "
                "Each child wrote a receipt before the parent readback was validated."
            ),
            "boundary": "Draft/proposed only. No send, Coupa, ledger, browser, workbook read, or production mutation.",
        },
        "machine_proof": {
            "parent_delegation_policy_used": True,
            "child_package_gate_used": True,
            "child_receipts_written": bool(child_receipt_ids),
            "parent_receipt_written": bool(parent_receipt.get("receipt_id")),
            "guardian_output_gate_used": final_verdict == PARENT_VALIDATED,
            "repo_b_runtime_started": False,
            "live_model_call_performed": False,
            "tool_execution_performed": False,
            "external_action_performed": False,
            "send_submit_performed": False,
            "ledger_posting_performed": False,
            "workbook_body_read_performed": False,
            "production_state_mutation_performed": False,
            "all_live_authority_false": all(value is False for value in worker_harness.AUTHORITY_BOUNDARY.values()),
        },
    }


def build_read_model(
    *,
    db_path: Path = DEFAULT_DB_PATH,
    generated_at: str = DEFAULT_GENERATED_AT,
) -> dict[str, Any]:
    fixture = run_capital_hilton_delegated_fixture(db_path=db_path, created_at=generated_at)
    read_model = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "generated_at": generated_at,
        "contract_status": "PACKAGE_SCOPED_DELEGATION_V0_NO_PRODUCTION_AUTHORITY",
        "delegation_contracts": {
            "child_package_request": tuple(ChildPackageRequest.__dataclass_fields__.keys()),
            "delegation_policy": tuple(DelegationPolicy.__dataclass_fields__.keys()),
            "child_package_validation_result": tuple(ChildPackageValidationResult.__dataclass_fields__.keys()),
            "package_lineage": tuple(PackageLineage.__dataclass_fields__.keys()),
            "delegated_package_graph": tuple(DelegatedPackageGraph.__dataclass_fields__.keys()),
        },
        "capital_hilton_fixture": fixture,
        "readiness_summary": {
            "delegated_package_graph": "READY_FOR_OFFLINE_SHADOW_FIXTURE",
            "parent_package_delegation": "POLICY_GATED",
            "child_package_gate": "DETERMINISTIC",
            "receipt_linkage": "SQLITE_ISOLATED_TEST_HARNESS",
            "production_authority": "NOT_ACTIVE",
        },
        "boundary": {
            "repo_b_runtime_started": False,
            "live_model_call_performed": False,
            "tool_execution_performed": False,
            "external_action_performed": False,
            "send_submit_performed": False,
            "ledger_posting_performed": False,
            "workbook_body_read_performed": False,
            "production_state_mutation_performed": False,
        },
    }
    return {**read_model, "machine_proof": {"content_hash": _content_hash(read_model)}}


def operator_markdown(read_model: Mapping[str, Any]) -> str:
    fixture = read_model["capital_hilton_fixture"]
    lineage = fixture["package_lineage"]
    child_receipts = lineage["child_receipt_ids"]
    parent_receipt = lineage["parent_receipt_id"]
    lines = [
        "# Delegated Package Graph",
        "",
        "Status: READY_FOR_OFFLINE_SHADOW_FIXTURE",
        "",
        "Capital Hilton package prep can request bounded child packages only when the parent package grants delegation.",
        "",
        "What happened:",
        "- Chief child package produced a local status/next-safe-move result.",
        "- Clara child package produced client-safe draft wording.",
        "- Each child output passed Guardian before a receipt was written.",
        "- Parent readback used receipt-backed child results only.",
        "",
        "Receipts:",
        *(f"- Child: {receipt_id}" for receipt_id in child_receipts),
        f"- Parent: {parent_receipt}",
        "",
        "Boundary:",
        "- No Repo B runtime started.",
        "- No live LM call happened.",
        "- No tools, sends, Coupa/browser step, ledger posting, workbook-body read, or production mutation happened.",
    ]
    return "\n".join(lines) + "\n"


def export_read_model(
    *,
    export_root: Path = DEFAULT_EXPORT_ROOT,
    db_path: Path = DEFAULT_DB_PATH,
    generated_at: str = DEFAULT_GENERATED_AT,
) -> dict[str, Path]:
    export_root.mkdir(parents=True, exist_ok=True)
    read_model = build_read_model(db_path=db_path, generated_at=generated_at)
    json_path = export_root / JSON_EXPORT_NAME
    operator_path = export_root / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(read_model), encoding="utf-8")
    operator_path.write_text(operator_markdown(read_model), encoding="utf-8")
    return {"json": json_path, "operator": operator_path}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export delegated package graph read-model.")
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT))
    parser.add_argument("--db-path", default=str(DEFAULT_DB_PATH))
    parser.add_argument("--generated-at", default=DEFAULT_GENERATED_AT)
    args = parser.parse_args(argv)
    paths = export_read_model(
        export_root=Path(args.export_root),
        db_path=Path(args.db_path),
        generated_at=args.generated_at,
    )
    print(paths["json"].as_posix())
    print(paths["operator"].as_posix())
    return 0


__all__ = [
    "BLOCKED",
    "DEFAULT_DB_PATH",
    "DelegationPolicy",
    "ChildPackageRequest",
    "ChildPackageValidationResult",
    "DelegatedPackageGraph",
    "PackageLineage",
    "VALIDATED",
    "build_capital_hilton_parent_package",
    "build_read_model",
    "capital_hilton_child_requests",
    "capital_hilton_delegation_policy",
    "export_read_model",
    "parent_can_continue",
    "run_capital_hilton_delegated_fixture",
    "validate_child_package_request",
    "validate_child_package_requests",
]
