"""LM2 room-backed worker pilot approval packet V0.

Approval-packet/read-model only. This packet prepares an operator review record
for one future room-backed LM2 worker pilot. It does not invoke models, connect
local runtimes, spawn workers, send prompts or proof bundles, access business
systems, mutate records, export PDFs, mark paid, submit, or push.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import lm2_live_worker_pilot_boundary_packet as boundary
import local_model_selection_for_proof_response as model_selection


ROOT = Path(__file__).resolve().parent
DEFAULT_READ_MODEL_ROOT = Path("generated/read_models")
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_BRIDGE_ROOT = Path("/mnt/e/openclaw/generated/read_models")
DEFAULT_WIKI_PATH = Path("generated/wiki/openclaw/LM2 Room Backed Worker Pilot Approval Packet.md")

SCHEMA_VERSION = "lm2_room_backed_worker_pilot_approval_packet_v0"
READ_MODEL_ID = "lm2_room_backed_worker_pilot_approval_packet"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
READY_STATUS = "LM2_ROOM_BACKED_WORKER_PILOT_APPROVAL_PACKET_READY"
NOT_READY_STATUS = "LM2_ROOM_BACKED_WORKER_PILOT_APPROVAL_PACKET_NOT_READY"
APPROVAL_PACKET_ID = "approval_packet:lm2_room_backed_worker:finance_capital_hilton_payment_watch:v0"
APPROVAL_PACKET_STATUS = "pending_operator_review"

PRECONDITIONS = {
    "project_room_sourceset_contract": {
        "filename": "project_room_sourceset_contract.json",
        "accepted_statuses": ("PROJECT_ROOM_SOURCESET_CONTRACT_READY",),
    },
    "project_room_package_compiler_integration": {
        "filename": "project_room_package_compiler_integration.json",
        "accepted_statuses": ("PROJECT_ROOM_PACKAGE_COMPILER_INTEGRATION_READY",),
    },
    "lm2_room_backed_worker_pilot_boundary": {
        "filename": boundary.ROOM_BACKED_JSON_EXPORT_NAME,
        "accepted_statuses": (boundary.ROOM_BACKED_READY_STATUS,),
    },
    "proof_bundle_freshness_trace_integration": {
        "filename": "proof_bundle_freshness_trace_status.json",
        "accepted_statuses": ("PROOF_BUNDLE_FRESHNESS_TRACE_INTEGRATION_READY",),
    },
    "proof_bundle_builder_redaction_integration": {
        "filename": "proof_bundle_builder_redaction_status.json",
        "accepted_statuses": ("PROOF_BUNDLE_BUILDER_REDACTION_INTEGRATION_READY",),
    },
    "context_freshness_decision_trace_gate": {
        "filename": "context_freshness_decision_trace_gate.json",
        "accepted_statuses": ("CONTEXT_FRESHNESS_DECISION_TRACE_GATE_READY",),
    },
    "proof_to_response_schema_adapter": {
        "filename": "proof_to_response_schema_adapter_status.json",
        "accepted_statuses": ("PROOF_TO_RESPONSE_SCHEMA_ADAPTER_READY",),
    },
    "universal_receipt_envelope": {
        "filename": "universal_receipt_envelope_status.json",
        "accepted_statuses": ("UNIVERSAL_RECEIPT_ENVELOPE_READY",),
    },
    "goldilocks_gate_calibration": {
        "filename": "goldilocks_gate_calibration.json",
        "accepted_statuses": ("GOLDILOCKS_GATE_CALIBRATION_READY",),
    },
    "local_model_selection_for_proof_response": {
        "filename": "local_model_selection_for_proof_response.json",
        "accepted_statuses": ("LOCAL_MODEL_SELECTION_FOR_PROOF_RESPONSE_READY",),
    },
}

AUTHORITY_BOUNDARY = {
    "approval_packet_is_approval": False,
    "invocation_allowed": False,
    "worker_spawn_allowed": False,
    "proof_bundle_allowed": False,
    "model_invocation_allowed": False,
    "local_model_runtime_allowed": False,
    "tool_authority": False,
    "tool_authority_allowed": False,
    "tool_execution_allowed": False,
    "business_action_authority": False,
    "business_action_allowed": False,
    "external_provider_allowed": False,
    "email_send_allowed": False,
    "gmail_allowed": False,
    "browser_access_allowed": False,
    "coupa_allowed": False,
    "portal_submit_allowed": False,
    "ledger_mutation_allowed": False,
    "workbook_mutation_allowed": False,
    "pdf_export_allowed": False,
    "paid_marking_allowed": False,
    "memory_promotion_allowed": False,
    "file_system_mutation_allowed": False,
    "shell_command_allowed": False,
    "repeated_invocations_allowed": False,
    "git_push_allowed": False,
}

IMPLEMENTATION_BOUNDARY = {
    "model_invoked": False,
    "runtime_connected": False,
    "local_model_runtime_connected": False,
    "worker_spawn_performed": False,
    "prompt_sent": False,
    "proof_bundle_sent": False,
    "tool_execution_performed": False,
    "business_action_performed": False,
    "email_send_performed": False,
    "gmail_opened": False,
    "browser_opened": False,
    "coupa_opened": False,
    "portal_submit_performed": False,
    "ledger_mutation_performed": False,
    "workbook_mutation_performed": False,
    "pdf_export_performed": False,
    "paid_marking_performed": False,
    "memory_promotion_performed": False,
    "external_provider_used": False,
    "file_system_mutation_performed": False,
    "shell_command_performed": False,
    "git_push_performed": False,
}

UNSAFE_TRUE_KEYS = (
    set(AUTHORITY_BOUNDARY)
    | set(IMPLEMENTATION_BOUNDARY)
    | set(boundary.UNSAFE_TRUE_KEYS)
    | set(model_selection.UNSAFE_TRUE_KEYS)
    | {
        "approval_granted",
        "operator_approved",
        "approved",
        "approved_for_live_invocation",
        "ready_for_live_invocation",
        "worker_started",
        "worker_spawned",
        "authority_granted",
        "paid",
        "sent",
        "submitted",
        "executed",
    }
)


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _rooted(path: Path | str) -> Path:
    path = Path(path)
    return path if path.is_absolute() else ROOT / path


def _load_json(path: Path | str) -> dict[str, Any]:
    path = _rooted(path)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_json(path: Path | str, payload: Mapping[str, Any]) -> None:
    path = _rooted(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(stable_json(payload), encoding="utf-8")


def _content_hash(payload: Any) -> str:
    return "sha256:" + hashlib.sha256(stable_json(payload).encode("utf-8")).hexdigest()


def _walk_values(payload: Any):
    if isinstance(payload, Mapping):
        for key, value in payload.items():
            yield str(key), value
            yield from _walk_values(value)
    elif isinstance(payload, list):
        for value in payload:
            yield from _walk_values(value)


def unsafe_true_grants(payload: Mapping[str, Any]) -> list[str]:
    return sorted({key for key, value in _walk_values(payload) if key in UNSAFE_TRUE_KEYS and value is True})


def _status(payload: Mapping[str, Any]) -> str:
    return str(payload.get("status") or payload.get("readiness_status") or payload.get("contract_status") or "")


def precondition_rows(read_model_root: Path = DEFAULT_READ_MODEL_ROOT) -> list[dict[str, Any]]:
    root = _rooted(read_model_root)
    rows: list[dict[str, Any]] = []
    for ref, spec in PRECONDITIONS.items():
        filename = str(spec["filename"])
        payload = _load_json(root / filename)
        observed = _status(payload)
        accepted = [str(status) for status in spec["accepted_statuses"]]
        rows.append(
            {
                "precondition_ref": ref,
                "source_ref": f"generated/read_models/{filename}",
                "observed_status": observed,
                "accepted_statuses": accepted,
                "ready": observed in accepted,
            }
        )
    return rows


def build_approval_packet() -> dict[str, Any]:
    package = boundary.build_room_backed_package()
    return {
        "approval_packet_id": APPROVAL_PACKET_ID,
        "status": APPROVAL_PACKET_STATUS,
        "invocation_allowed": False,
        "worker_spawn_allowed": False,
        "proof_bundle_allowed": False,
        "room_backed_package_required": True,
        "selected_worker_class": boundary.WORKER_CLASS,
        "selected_runtime_ref": boundary.RUNTIME_REF,
        "selected_model_ref": boundary.MODEL_REF,
        "selected_model_name": boundary.MODEL_NAME,
        "pilot_lane": boundary.PILOT_LANE,
        "pilot_question": boundary.QUESTION,
        "pilot_objective": boundary.OBJECTIVE_REF,
        "pilot_mode": boundary.MODE,
        "package_type": "room-backed worker package",
        "project_room_ref": package["project_room_id"],
        "source_inventory_ref": package["source_inventory_ref"],
        "conflict_log_ref": package["conflict_log_ref"],
        "missing_context_ref": package["missing_context_ref"],
        "duplicate_report_ref": package["duplicate_report_ref"],
        "decision_trace_ref": package["decision_trace_ref"],
        "freshness_gate_ref": package["freshness_gate_ref"],
        "compaction_policy_ref": package["compaction_policy_ref"],
        "redacted_proof_bundle_ref": package["redacted_proof_bundle_ref"],
        "authority_boundary_ref": package["authority_boundary_ref"],
        "receipt_requirement_ref": package["receipt_requirement_ref"],
        "room_backed_package_ref": package["package_ref"],
        "may_receive_only": list(boundary.ROOM_BACKED_ALLOWED_WORKER_INPUTS),
        "must_not_receive": list(boundary.ROOM_BACKED_FORBIDDEN_WORKER_INPUTS),
        "allowed_worker_capability_after_future_approval": list(boundary.WORKER_CAPABILITIES_ALLOWED),
        "forbidden_worker_capability": list(boundary.WORKER_CAPABILITIES_FORBIDDEN),
        "required_receipts_before_future_invocation": list(boundary.ROOM_BACKED_RECEIPTS_REQUIRED_BEFORE),
        "required_receipts_after_future_invocation": list(boundary.ROOM_BACKED_RECEIPTS_REQUIRED_AFTER),
        "stop_conditions": list(boundary.ROOM_BACKED_STOP_CONDITIONS),
        "expected_worker_output_target": dict(boundary.ROOM_BACKED_EXPECTED_RESPONSE),
        "operator_decision_options": list(boundary.ROOM_BACKED_OPERATOR_DECISION_OPTIONS),
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "implementation_boundary": dict(IMPLEMENTATION_BOUNDARY),
        "rules": [
            "This packet is not approval.",
            "This packet does not run LM2.",
            "invocation_allowed=false.",
            "worker_spawn_allowed=false.",
            "proof_bundle_allowed=false.",
            "No protected business action.",
            "No external provider.",
            "No tool authority.",
        ],
    }


def build_read_model(
    *,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    preconditions = precondition_rows(read_model_root)
    packet = build_approval_packet()
    required_refs = (
        "project_room_ref",
        "source_inventory_ref",
        "conflict_log_ref",
        "missing_context_ref",
        "duplicate_report_ref",
        "decision_trace_ref",
        "freshness_gate_ref",
        "compaction_policy_ref",
        "redacted_proof_bundle_ref",
        "authority_boundary_ref",
        "receipt_requirement_ref",
    )
    stop_conditions = set(packet["stop_conditions"])
    required_stop_conditions = {
        "freshness_stale_superseded_or_unknown",
        "model_returns_non_json",
        "model_claims_paid_sent_submitted_or_executed",
        "model_promises_protected_action",
        "model_attempts_tool_use",
        "model_exceeds_one_attempt",
    }
    forbidden_inputs = set(packet["must_not_receive"])
    required_forbidden_inputs = {
        "raw_financial_proof",
        "credentials_or_tokens",
        "operator_device_session_verification_secrets",
        "raw_ocr_or_artifact_text",
        "workbook_email_or_ledger_bodies",
        "authority_granted_fields",
        "stale_source_as_current_truth",
    }
    machine_proof = {
        "approval_packet_only": True,
        "preconditions_ready": all(row["ready"] for row in preconditions),
        "packet_pending_operator_review": packet["status"] == APPROVAL_PACKET_STATUS,
        "invocation_disallowed": packet["invocation_allowed"] is False,
        "worker_spawn_disallowed": packet["worker_spawn_allowed"] is False,
        "proof_bundle_disallowed": packet["proof_bundle_allowed"] is False,
        "room_backed_package_required": packet["room_backed_package_required"] is True,
        "project_room_refs_present": all(str(packet.get(ref) or "") for ref in required_refs),
        "forbidden_inputs_complete": required_forbidden_inputs <= forbidden_inputs,
        "tool_authority_false": packet["authority_boundary"]["tool_authority"] is False
        and packet["authority_boundary"]["tool_authority_allowed"] is False,
        "business_action_authority_false": packet["authority_boundary"]["business_action_authority"] is False
        and packet["authority_boundary"]["business_action_allowed"] is False,
        "stop_conditions_complete": required_stop_conditions <= stop_conditions,
        "operator_decision_options_review_only": tuple(packet["operator_decision_options"])
        == boundary.ROOM_BACKED_OPERATOR_DECISION_OPTIONS,
        "model_invocation_absent": packet["implementation_boundary"]["model_invoked"] is False,
        "worker_spawn_absent": packet["implementation_boundary"]["worker_spawn_performed"] is False,
        "prompt_send_absent": packet["implementation_boundary"]["prompt_sent"] is False,
        "proof_bundle_send_absent": packet["implementation_boundary"]["proof_bundle_sent"] is False,
        "unsafe_true_grants_absent": True,
    }
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "status": READY_STATUS if all(value is True for value in machine_proof.values()) else NOT_READY_STATUS,
        "generated_at": generated_at,
        "purpose": "Create an operator approval packet for one future room-backed LM2 worker pilot.",
        "approval_packet": packet,
        "approval_packet_id": packet["approval_packet_id"],
        "packet_status": packet["status"],
        "preconditions": preconditions,
        "source_refs": [row["source_ref"] for row in preconditions],
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "implementation_boundary": dict(IMPLEMENTATION_BOUNDARY),
        "machine_proof": machine_proof,
        "source_content_hashes": {
            "preconditions": _content_hash(preconditions),
            "approval_packet": _content_hash(packet),
        },
    }
    unsafe = unsafe_true_grants(payload)
    payload["unsafe_true_grants"] = unsafe
    payload["machine_proof"]["unsafe_true_grants_absent"] = not unsafe
    if unsafe:
        payload["status"] = NOT_READY_STATUS
    payload["content_hash"] = _content_hash({key: value for key, value in payload.items() if key != "content_hash"})
    return payload


def build_wiki(read_model: Mapping[str, Any]) -> str:
    packet = read_model.get("approval_packet") if isinstance(read_model.get("approval_packet"), Mapping) else {}
    lines = [
        "# LM2 Room Backed Worker Pilot Approval Packet",
        "",
        f"Status: {read_model.get('status')}",
        f"Packet status: {packet.get('status')}",
        "",
        "This packet is not approval and does not run LM2. It prepares a review-only operator decision for one future room-backed LM2 worker pilot.",
        "",
        "## Pilot Scope",
        "",
        f"- Worker class: `{packet.get('selected_worker_class')}`",
        f"- Runtime: `{packet.get('selected_runtime_ref')}`",
        f"- Model: `{packet.get('selected_model_name')}`",
        f"- Lane: `{packet.get('pilot_lane')}`",
        f"- Question: {packet.get('pilot_question')}",
        f"- Mode: `{packet.get('pilot_mode')}`",
        "",
        "## Required Room Refs",
        "",
    ]
    for ref in (
        "project_room_ref",
        "source_inventory_ref",
        "conflict_log_ref",
        "missing_context_ref",
        "duplicate_report_ref",
        "decision_trace_ref",
        "freshness_gate_ref",
        "compaction_policy_ref",
        "redacted_proof_bundle_ref",
    ):
        lines.append(f"- `{ref}`: `{packet.get(ref)}`")
    lines.extend(["", "## Operator Decision Options", ""])
    for option in packet.get("operator_decision_options") or []:
        lines.append(f"- `{option}`")
    lines.extend(["", "## Rules", ""])
    for rule in packet.get("rules") or []:
        lines.append(f"- {rule}")
    lines.append("")
    return "\n".join(lines)


def export_lm2_room_backed_worker_pilot_approval_packet(
    *,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
    export_root: Path = DEFAULT_EXPORT_ROOT,
    bridge_root: Path | None = DEFAULT_BRIDGE_ROOT,
    wiki_path: Path = DEFAULT_WIKI_PATH,
    generated_at: str | None = None,
) -> dict[str, str]:
    read_model = build_read_model(read_model_root=read_model_root, generated_at=generated_at)
    export_root = _rooted(export_root)
    export_root.mkdir(parents=True, exist_ok=True)
    read_model_path = export_root / JSON_EXPORT_NAME
    _write_json(read_model_path, read_model)

    bridge_read_model_path = ""
    if bridge_root is not None:
        bridge_root = _rooted(bridge_root)
        bridge_root.mkdir(parents=True, exist_ok=True)
        bridge_path = bridge_root / JSON_EXPORT_NAME
        shutil.copy2(read_model_path, bridge_path)
        bridge_read_model_path = bridge_path.as_posix()

    wiki_path = _rooted(wiki_path)
    wiki_path.parent.mkdir(parents=True, exist_ok=True)
    wiki_path.write_text(build_wiki(read_model), encoding="utf-8")
    return {
        "status": str(read_model.get("status") or NOT_READY_STATUS),
        "read_model_path": read_model_path.as_posix(),
        "bridge_read_model_path": bridge_read_model_path,
        "wiki_path": wiki_path.as_posix(),
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Publish LM2 Room Backed Worker Pilot Approval Packet V0.")
    parser.add_argument("--read-model-root", default=str(DEFAULT_READ_MODEL_ROOT))
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT))
    parser.add_argument("--bridge-root", default=str(DEFAULT_BRIDGE_ROOT))
    parser.add_argument("--wiki-path", default=str(DEFAULT_WIKI_PATH))
    parser.add_argument("--generated-at")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    bridge_root = Path(args.bridge_root) if args.bridge_root else None
    result = export_lm2_room_backed_worker_pilot_approval_packet(
        read_model_root=Path(args.read_model_root),
        export_root=Path(args.export_root),
        bridge_root=bridge_root,
        wiki_path=Path(args.wiki_path),
        generated_at=args.generated_at,
    )
    print(stable_json(result), end="")
    return 0 if result["status"] == READY_STATUS else 1


if __name__ == "__main__":
    raise SystemExit(main())
