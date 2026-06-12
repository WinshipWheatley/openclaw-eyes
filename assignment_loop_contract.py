"""Assignment Loop V0 contract for bounded OpenClaw work.

This module formalizes the job wrapper around Codex, Gemini, Fable, and local
worker tasks. It is deterministic contract/read-model work only: it does not
call models, spawn workers, create approvals, create dashboards, mutate runtime
policy, send email, or inspect secrets.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence


SCHEMA_VERSION = "ASSIGNMENT_LOOP_V0"
READ_MODEL_ID = "assignment_loop_contract"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
READY_STATUS = "OPENCLAW_ASSIGNMENT_LOOP_CONTRACT_READY"
BLOCKED_STATUS = "OPENCLAW_ASSIGNMENT_LOOP_CONTRACT_BLOCKED"

DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_BRIDGE_ROOT = Path("/mnt/e/openclaw/generated/read_models")
DEFAULT_WIKI_PATH = Path("generated/wiki/openclaw/Assignment Loop Contract.md")

ASSIGNMENT_PHASES = (
    "intake",
    "package",
    "dispatch",
    "work",
    "verify",
    "summarize",
    "next_action",
    "archive",
)

ASSIGNMENT_STATUSES = (
    "intake",
    "packaged",
    "dispatched",
    "active",
    "blocked",
    "ready_for_review",
    "completed",
    "archived",
)

WORKER_TYPES = (
    "codex",
    "gemini",
    "fable",
    "local_worker",
    "mac_codex",
    "pc_codex",
    "local_model",
    "human_operator",
)

REFERENCE_SURFACES = {
    "model_work_package_router": "model_work_package_router.py",
    "worker_package_staging": "generated/read_models/worker_package_staging_status.json",
    "spawned_worker_lifecycle": "generated/read_models/spawned_worker_package_lifecycle.json",
    "watch_desk": "watch_desk_feed.py",
    "operator_context_switchboard": "operator_context_switchboard.py",
    "guardian_hitl": "hitl_action_service.py",
    "agent_lane_registry": "agent_lane_registry.py",
}

DEFAULT_PERMISSION_BOUNDARY = {
    "model_output_runtime_mutation_allowed": False,
    "model_output_business_mutation_allowed": False,
    "guardian_approval_created_by_assignment_loop": False,
    "guardian_hitl_remains_separate": True,
    "watch_desk_is_display_only": True,
    "dashboard_created": False,
    "email_send_allowed": False,
    "gmail_allowed": False,
    "external_api_allowed": False,
    "secret_inspection_allowed": False,
    "runtime_policy_mutation_allowed": False,
    "ledger_mutation_allowed": False,
    "workbook_mutation_allowed": False,
    "pdf_export_allowed": False,
    "paid_marking_allowed": False,
    "worker_spawn_allowed_without_dispatch_gate": False,
    "approval_bypass_allowed": False,
}

DEFAULT_SAFETY_FLAGS = {
    "model_called": False,
    "external_api_called": False,
    "runtime_policy_mutated": False,
    "email_sent": False,
    "gmail_draft_created": False,
    "secret_inspected": False,
    "approval_created": False,
    "guardian_bypassed": False,
    "ledger_mutated": False,
    "workbook_mutated": False,
    "pdf_exported": False,
    "invoice_marked_paid": False,
    "worker_spawned": False,
    "dashboard_created": False,
}

UNSAFE_TRUE_KEYS = set(DEFAULT_SAFETY_FLAGS) | {
    key for key in DEFAULT_PERMISSION_BOUNDARY if key.endswith("_allowed") or key.endswith("_created")
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _short_hash(*parts: object, length: int = 16) -> str:
    return hashlib.sha256("\0".join(str(part) for part in parts).encode("utf-8")).hexdigest()[:length]


def _as_list(values: Sequence[str] | None) -> list[str]:
    return [str(value) for value in values or [] if str(value or "").strip()]


def _boundary(overrides: Mapping[str, Any] | None = None) -> dict[str, Any]:
    boundary = dict(DEFAULT_PERMISSION_BOUNDARY)
    if overrides:
        for key, value in overrides.items():
            if key in boundary:
                boundary[key] = bool(value)
            else:
                boundary[str(key)] = value
    return boundary


def _safety(overrides: Mapping[str, Any] | None = None) -> dict[str, bool]:
    flags = dict(DEFAULT_SAFETY_FLAGS)
    if overrides:
        for key, value in overrides.items():
            if key in flags:
                flags[key] = bool(value)
    return flags


def build_assignment_loop(
    *,
    requested_by: str,
    owner_agent: str,
    worker_type: str,
    goal: str,
    sources: Sequence[str],
    standard: str,
    permission_boundary: Mapping[str, Any] | None = None,
    proof_required: Sequence[str] | None = None,
    stop_condition: str,
    current_status: str = "intake",
    receipts: Sequence[str] | None = None,
    watch_desk_refs: Sequence[str] | None = None,
    operator_next_action: str = "",
    safety_flags: Mapping[str, Any] | None = None,
    created_at_utc: str | None = None,
    assignment_id: str = "",
    parking_lot_refs: Sequence[str] | None = None,
) -> dict[str, Any]:
    created_at_utc = created_at_utc or utc_now()
    sources_list = _as_list(sources)
    proof_list = _as_list(proof_required) or ["source refs", "validation receipt", "summary receipt"]
    assignment_id = assignment_id or "assignment_loop:" + _short_hash(
        created_at_utc,
        requested_by,
        owner_agent,
        worker_type,
        goal,
        tuple(sources_list),
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "assignment_id": assignment_id,
        "created_at_utc": created_at_utc,
        "requested_by": str(requested_by),
        "owner_agent": str(owner_agent),
        "worker_type": str(worker_type),
        "goal": str(goal),
        "sources": sources_list,
        "standard": str(standard),
        "permission_boundary": _boundary(permission_boundary),
        "proof_required": proof_list,
        "stop_condition": str(stop_condition),
        "current_status": str(current_status),
        "receipts": _as_list(receipts),
        "watch_desk_refs": _as_list(watch_desk_refs),
        "operator_next_action": str(operator_next_action),
        "safety_flags": _safety(safety_flags),
        "phases": list(ASSIGNMENT_PHASES),
        "parking_lot_refs": _as_list(parking_lot_refs),
    }


def assignment_ready_status(assignment: Mapping[str, Any]) -> dict[str, Any]:
    required = _as_list(assignment.get("proof_required") if isinstance(assignment.get("proof_required"), list) else [])
    receipts = _as_list(assignment.get("receipts") if isinstance(assignment.get("receipts"), list) else [])
    missing = []
    if required and not receipts:
        missing.append("receipt_or_proof_ref")
    if not _as_list(assignment.get("sources") if isinstance(assignment.get("sources"), list) else []):
        missing.append("sources")
    unsafe = unsafe_true_grants(assignment)
    ready = not missing and not unsafe
    return {
        "assignment_id": str(assignment.get("assignment_id") or ""),
        "ready": ready,
        "missing_before_ready": missing,
        "unsafe_true_grants": unsafe,
        "ready_status_allowed": ready,
    }


def attach_parking_lot_item(
    assignment: Mapping[str, Any],
    *,
    parking_ref: str,
    reason: str,
) -> dict[str, Any]:
    updated = dict(assignment)
    refs = _as_list(updated.get("parking_lot_refs") if isinstance(updated.get("parking_lot_refs"), list) else [])
    if parking_ref not in refs:
        refs.append(parking_ref)
    updated["parking_lot_refs"] = refs
    updated["parking_lot_policy"] = {
        "parking_ref": parking_ref,
        "reason": reason,
        "attached_to_assignment": True,
        "does_not_mark_ready": True,
    }
    return updated


def add_assignment_ref_to_model_work_package(package: Mapping[str, Any], assignment: Mapping[str, Any]) -> dict[str, Any]:
    updated = dict(package)
    updated["assignment_loop_ref"] = str(assignment.get("assignment_id") or "")
    updated["assignment_loop_schema"] = SCHEMA_VERSION
    updated["execution_allowed"] = False
    updated["runtime_mutation_allowed"] = False
    updated["external_call_allowed"] = False
    return updated


def build_assignment_for_model_work_package(
    package: Mapping[str, Any],
    *,
    requested_by: str | None = None,
    standard: str = "Return a bounded advisory result with proof refs and no runtime mutation.",
    created_at_utc: str | None = None,
) -> dict[str, Any]:
    return build_assignment_loop(
        requested_by=requested_by or str(package.get("requested_by_agent") or "operator"),
        owner_agent=str(package.get("owner_agent") or package.get("requested_by_agent") or "chief"),
        worker_type=str(package.get("resolved_model_class") or package.get("candidate_model") or "codex"),
        goal=str(package.get("task_type") or "bounded model work package"),
        sources=_as_list(package.get("context_refs") if isinstance(package.get("context_refs"), list) else []),
        standard=standard,
        proof_required=["model work package receipt", "validation receipt", "operator summary"],
        stop_condition=str(package.get("stop_condition") or "Stop before execution or unsupported claim."),
        current_status=str(package.get("status") or "packaged"),
        receipts=[],
        watch_desk_refs=[],
        operator_next_action="Review the assignment package and keep Guardian approvals separate.",
        created_at_utc=created_at_utc,
    )


def build_watch_desk_item_for_assignment(assignment: Mapping[str, Any]) -> dict[str, Any]:
    status = str(assignment.get("current_status") or "active")
    urgency = "blocked" if status == "blocked" else "info" if status in {"completed", "archived"} else "watch"
    item_id = "assignment_loop:" + _short_hash(assignment.get("assignment_id"), status)
    source_receipt_ref = ""
    receipts = assignment.get("receipts")
    if isinstance(receipts, list) and receipts:
        source_receipt_ref = str(receipts[0])
    if not source_receipt_ref:
        source_receipt_ref = f"{assignment.get('assignment_id')}#assignment"
    return {
        "item_id": item_id,
        "lane": "chief_runtime",
        "urgency": urgency,
        "plain_line": f"Assignment {status}: {assignment.get('goal')}",
        "source_receipt_ref": source_receipt_ref,
        "one_next_safe_action": str(assignment.get("operator_next_action") or "Review assignment proof and next action."),
        "push_allowed": False,
        "push_candidate": status == "blocked",
        "push_class": "failure" if status == "blocked" else "info",
        "state": {
            "assignment_id": str(assignment.get("assignment_id") or ""),
            "current_status": status,
            "owner_agent": str(assignment.get("owner_agent") or ""),
            "worker_type": str(assignment.get("worker_type") or ""),
            "proof_required": list(assignment.get("proof_required") or []),
            "proof_ready": assignment_ready_status(assignment)["ready"],
            "model_output_runtime_mutation_allowed": False,
            "guardian_hitl_separate": True,
        },
    }


def contract_doctrine() -> dict[str, Any]:
    return {
        "summary": "Every Codex/Gemini/Fable/local-worker task is a bounded assignment with goal, sources, standard, permission boundary, proof, and stop condition.",
        "assignment_phases": list(ASSIGNMENT_PHASES),
        "reused_surfaces": dict(REFERENCE_SURFACES),
        "rules": [
            "Model output is advisory until deterministic verification and receipts exist.",
            "No model output directly mutates runtime policy or business state.",
            "Guardian/HITL remains the existing approval path and is not replaced by assignments.",
            "Watch Desk may display assignments but does not approve or execute them.",
            "Parking-lot items may attach to active assignments without marking them ready.",
            "READY requires proof refs or receipts.",
        ],
    }


def build_read_model(*, generated_at: str | None = None) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    examples = [
        build_assignment_loop(
            requested_by="operator",
            owner_agent="chief",
            worker_type="codex",
            goal="Patch a scoped backend contract with tests.",
            sources=["model_work_package_router.py", "tests/test_model_work_package_router.py"],
            standard="Focused tests pass, py_compile passes, unsafe scan clean.",
            proof_required=["focused pytest output", "py_compile output", "unsafe scan result"],
            stop_condition="Stop after local validation and summary; do not push.",
            current_status="active",
            receipts=["generated/read_models/model_work_package_router_status.json#receipt"],
            watch_desk_refs=["assignment_loop:example_codex_patch"],
            operator_next_action="Review the validation proof and decide whether to merge later through the normal process.",
            created_at_utc=generated_at,
            assignment_id="assignment_loop:example_codex_patch",
        ),
        attach_parking_lot_item(
            build_assignment_loop(
                requested_by="operator",
                owner_agent="cassandra",
                worker_type="local_worker",
                goal="Resolve a blocked Data Room review context mismatch.",
                sources=["generated/read_models/guided_review_sessions.json"],
                standard="Explain blocker, preserve session proof, and avoid confirmed reference promotion.",
                proof_required=["session receipt", "watch desk ref"],
                stop_condition="Stop if context is stale or operator confirmation is missing.",
                current_status="blocked",
                receipts=[],
                watch_desk_refs=["guided_review:data_room_review:example"],
                operator_next_action="Provide missing lane context or park the note.",
                created_at_utc=generated_at,
                assignment_id="assignment_loop:example_parked_context",
            ),
            parking_ref="consult_parked_note:example",
            reason="Missing matching active question.",
        ),
    ]
    readiness = [assignment_ready_status(item) for item in examples]
    payload = {
        "schema_version": "assignment_loop_contract_read_model_v0",
        "status": READY_STATUS,
        "generated_at": generated_at,
        "contract": contract_doctrine(),
        "field_contract": {
            field: "required"
            for field in (
                "assignment_id",
                "requested_by",
                "owner_agent",
                "worker_type",
                "goal",
                "sources",
                "standard",
                "permission_boundary",
                "proof_required",
                "stop_condition",
                "current_status",
                "receipts",
                "watch_desk_refs",
                "operator_next_action",
                "safety_flags",
            )
        },
        "assignment_statuses": list(ASSIGNMENT_STATUSES),
        "worker_types": list(WORKER_TYPES),
        "permission_boundary_defaults": dict(DEFAULT_PERMISSION_BOUNDARY),
        "safety_flag_defaults": dict(DEFAULT_SAFETY_FLAGS),
        "examples": examples,
        "example_readiness": readiness,
        "machine_proof": {
            "model_calls_performed": False,
            "external_api_calls_performed": False,
            "runtime_policy_mutated": False,
            "new_approval_system_created": False,
            "new_dashboard_created": False,
            "watch_desk_reused": True,
            "guardian_hitl_reused": True,
            "agent_lane_registry_reused": True,
            "model_work_package_router_reused": True,
            "proof_required_before_ready": True,
            "unsafe_true_grants_absent": unsafe_true_grants(examples) == [],
        },
        "unsafe_true_grants": unsafe_true_grants(examples),
    }
    if payload["unsafe_true_grants"]:
        payload["status"] = BLOCKED_STATUS
    return payload


def unsafe_true_grants(payload: Any) -> list[str]:
    hits: set[str] = set()
    if isinstance(payload, Mapping):
        for key, value in payload.items():
            if key in UNSAFE_TRUE_KEYS and value is True:
                hits.add(str(key))
            hits.update(unsafe_true_grants(value))
    elif isinstance(payload, list):
        for value in payload:
            hits.update(unsafe_true_grants(value))
    return sorted(hits)


def format_wiki(read_model: Mapping[str, Any]) -> str:
    rules = "\n".join(f"- {rule}" for rule in read_model["contract"]["rules"])
    fields = "\n".join(f"- `{field}`" for field in read_model["field_contract"])
    phases = " -> ".join(read_model["contract"]["assignment_phases"])
    return (
        "# Assignment Loop Contract\n\n"
        f"Status: `{read_model['status']}`\n\n"
        "Every Codex/Gemini/Fable/local-worker task is framed as a bounded job.\n\n"
        "## Required Fields\n\n"
        f"{fields}\n\n"
        "## Phases\n\n"
        f"{phases}\n\n"
        "## Doctrine\n\n"
        f"{rules}\n\n"
        "## Existing Systems Reused\n\n"
        "- `model_work_package_router.py`\n"
        "- worker package staging and spawned worker lifecycle read models\n"
        "- Watch Desk feed items\n"
        "- Operator Context Switchboard\n"
        "- Guardian/HITL approval spine\n"
        "- receipts/read models\n"
        "- `agent_lane_registry.py`\n\n"
        "This contract does not create a new approval system, dashboard, model call, or runtime mutation path.\n"
    )


def export_assignment_loop_contract(
    *,
    export_root: str | Path = DEFAULT_EXPORT_ROOT,
    bridge_root: str | Path = DEFAULT_BRIDGE_ROOT,
    wiki_path: str | Path = DEFAULT_WIKI_PATH,
    generated_at: str | None = None,
) -> dict[str, Any]:
    read_model = build_read_model(generated_at=generated_at)
    export_root = Path(export_root)
    bridge_root = Path(bridge_root)
    json_path = export_root / JSON_EXPORT_NAME
    bridge_path = bridge_root / JSON_EXPORT_NAME
    wiki_path = Path(wiki_path)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    bridge_path.parent.mkdir(parents=True, exist_ok=True)
    wiki_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(stable_json(read_model), encoding="utf-8")
    shutil.copyfile(json_path, bridge_path)
    wiki_path.write_text(format_wiki(read_model), encoding="utf-8")
    return {
        "status": read_model["status"],
        "read_model_path": json_path.as_posix(),
        "bridge_read_model_path": bridge_path.as_posix(),
        "wiki_path": wiki_path.as_posix(),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export Assignment Loop V0 contract.")
    parser.add_argument("--export-root", default=DEFAULT_EXPORT_ROOT.as_posix())
    parser.add_argument("--bridge-root", default=DEFAULT_BRIDGE_ROOT.as_posix())
    parser.add_argument("--wiki-path", default=DEFAULT_WIKI_PATH.as_posix())
    args = parser.parse_args(list(argv) if argv is not None else None)
    result = export_assignment_loop_contract(
        export_root=args.export_root,
        bridge_root=args.bridge_root,
        wiki_path=args.wiki_path,
    )
    print(stable_json(result), end="")
    return 0


__all__ = [
    "ASSIGNMENT_PHASES",
    "READY_STATUS",
    "SCHEMA_VERSION",
    "add_assignment_ref_to_model_work_package",
    "assignment_ready_status",
    "attach_parking_lot_item",
    "build_assignment_for_model_work_package",
    "build_assignment_loop",
    "build_read_model",
    "build_watch_desk_item_for_assignment",
    "export_assignment_loop_contract",
    "unsafe_true_grants",
]


if __name__ == "__main__":
    raise SystemExit(main())
