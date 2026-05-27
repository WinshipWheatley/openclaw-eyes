"""Proposal-only intent interpreter contract v0.

This module builds the safe package a future interpreter may use to propose a
MachineIntentCandidate. It does not call a model, dispatch agents/workers, run
workflows, read private bodies, grant authority, or execute actions.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import asdict, dataclass, fields
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import machine_intent_candidate_validator as intent_validator
import openclaw_capability_index
import session_state_resolver
from machine_intent_candidate_validator import MachineIntentCandidate


DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_GENERATED_AT = "2026-05-26T00:00:00+00:00"

SCHEMA_VERSION = "lm_intent_proposal_contract_v0"
READ_MODEL_ID = "lm_intent_proposal_contract"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
OPERATOR_EXPORT_NAME = f"{READ_MODEL_ID}_OPERATOR.md"
CONTRACT_STATUS = "PROPOSAL_ONLY_INTENT_CONTRACT_NO_MODEL_CALL"

INTENDED_USE = "operator_intent_proposal_package"

AUTHORITY_BOUNDARY = {
    "live_lm_call_allowed": False,
    "live_model_call_allowed": False,
    "live_agent_dispatch_allowed": False,
    "live_worker_dispatch_allowed": False,
    "live_workflow_execution_allowed": False,
    "live_external_action_allowed": False,
    "live_send_submit_allowed": False,
    "live_approval_execution_allowed": False,
    "live_candidate_promotion_allowed": False,
    "live_file_body_read_allowed": False,
    "live_workbook_body_read_allowed": False,
    "live_spreadsheet_cell_read_allowed": False,
    "live_file_mutation_allowed": False,
    "live_pdf_generation_allowed": False,
    "live_browser_allowed": False,
    "live_coupa_access_allowed": False,
    "live_email_send_allowed": False,
    "credential_handling_allowed": False,
    "raw_body_ingestion_allowed": False,
    "network_allowed": False,
    "mission_control_swift_change_allowed": False,
    "git_push_pull_fetch_allowed": False,
}

FORBIDDEN_OUTPUTS = (
    "authority_granted_true",
    "workflow_execution",
    "agent_dispatch",
    "worker_dispatch",
    "send_submit",
    "approval_execution",
    "credential_or_secret_request",
    "raw_body_request",
    "file_body_read",
    "workbook_body_read",
    "spreadsheet_cell_read",
    "browser_or_coupa_action",
    "email_send",
    "ledger_posting",
    "submitted_sent_paid_completed_claim",
)


@dataclass(frozen=True)
class IntentProposalPackage:
    package_id: str
    source_request_id: str
    source_request_filename: str
    intended_use: str
    operator_text: str
    world_ref: str
    workflow_ref: str
    client_ref: str
    tenant_scope: str
    latest_response_ref: str
    latest_next_action: str
    latest_primary_blocker: str
    safe_readmodel_refs: tuple[str, ...]
    allowed_output_schema: tuple[str, ...]
    allowed_intent_types: tuple[str, ...]
    required_candidate_defaults: dict[str, Any]
    forbidden_outputs: tuple[str, ...]
    authority_boundary: dict[str, bool]
    validation_required: bool
    next_safe_move: str


@dataclass(frozen=True)
class IntentProposalReadback:
    readback_id: str
    status: str
    operator_headline: str
    operator_message: str
    package_summary: str
    missing_items: tuple[str, ...]
    next_action: str
    authority_boundary: dict[str, bool]
    next_safe_move: str


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _short_hash(*parts: object) -> str:
    return hashlib.sha256("\0".join(str(part) for part in parts).encode("utf-8")).hexdigest()[:16]


def _content_hash(payload: dict[str, Any]) -> str:
    clone = json.loads(stable_json(payload))
    clone.get("machine_proof", {}).pop("content_hash", None)
    return "sha256:" + hashlib.sha256(stable_json(clone).encode("utf-8")).hexdigest()


def _operator_text(raw_request: Mapping[str, Any]) -> str:
    seen: set[str] = set()
    parts: list[str] = []
    for field in ("operator_message", "sanitized_message_summary", "operator_goal", "message", "text"):
        value = raw_request.get(field)
        if isinstance(value, str) and value.strip():
            cleaned = " ".join(value.split())
            lowered = cleaned.lower()
            if lowered not in seen:
                seen.add(lowered)
                parts.append(cleaned)
    return " ".join(parts)[:500]


def _scope_value(raw_request: Mapping[str, Any], field: str, fallback: str) -> str:
    value = str(raw_request.get(field) or "").strip()
    return value if value and value.lower() != "unknown" else fallback


def _all_false_authority() -> dict[str, bool]:
    return {
        "workflow_run": False,
        "agent_dispatch": False,
        "worker_dispatch": False,
        "external_action": False,
        "send_submit": False,
        "approval_execution": False,
        "candidate_promotion": False,
        "credential_handling": False,
        "raw_body_ingestion": False,
        "file_mutation": False,
    }


def build_payload(
    raw_request: Mapping[str, Any],
    *,
    request_filename: str = "",
    export_root: Path = DEFAULT_EXPORT_ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    state = session_state_resolver.default_resolver().resolve(export_root=export_root, now=generated_at)
    source_request_id = str(raw_request.get("request_id") or f"intent_proposal_{_short_hash(request_filename, generated_at)}")
    operator_text = _operator_text(raw_request)
    package = IntentProposalPackage(
        package_id=f"intent_proposal_package:{_short_hash(source_request_id, operator_text)}",
        source_request_id=source_request_id,
        source_request_filename=request_filename,
        intended_use=INTENDED_USE,
        operator_text=operator_text,
        world_ref=_scope_value(raw_request, "world_ref", state.active_world_ref),
        workflow_ref=_scope_value(raw_request, "workflow_ref", state.active_workflow_ref),
        client_ref=_scope_value(raw_request, "client_ref", state.client_scope),
        tenant_scope=state.tenant_scope,
        latest_response_ref=state.latest_response_ref,
        latest_next_action=state.latest_next_action,
        latest_primary_blocker=state.latest_primary_blocker,
        safe_readmodel_refs=tuple(ref for ref in state.safe_readmodel_refs if ref),
        allowed_output_schema=tuple(field.name for field in fields(MachineIntentCandidate)),
        allowed_intent_types=tuple(intent_validator.INTENT_TYPES),
        required_candidate_defaults={
            "authority_granted": _all_false_authority(),
            "validation_required": True,
            "confidence_minimum_for_action": "HIGH",
            "if_ambiguous": "ASK_CLARIFICATION",
        },
        forbidden_outputs=FORBIDDEN_OUTPUTS,
        authority_boundary=dict(AUTHORITY_BOUNDARY),
        validation_required=True,
        next_safe_move="A verified interpreter may propose MachineIntentCandidate JSON only; validator decides the outcome.",
    )
    readback = IntentProposalReadback(
        readback_id=f"intent_proposal_readback:{_short_hash(source_request_id, 'readback')}",
        status="PROPOSAL_PACKAGE_CREATED",
        operator_headline="I need one more detail",
        operator_message="OpenClaw could not safely turn that into a bounded action yet. Nothing was run or changed.",
        package_summary="A proposal-only package was created for a future verified interpreter. It grants no authority.",
        missing_items=("bounded intent",),
        next_action="Next: say the object and the safe outcome you want, or choose the visible app option.",
        authority_boundary=dict(AUTHORITY_BOUNDARY),
        next_safe_move="Wait for a verified intent proposal or clearer operator instruction; do not execute anything.",
    )
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "contract_status": CONTRACT_STATUS,
        "generated_at": generated_at,
        "proposal_package": asdict(package),
        "proposal_readback": asdict(readback),
        "machine_proof": {
            "proposal_package_created": True,
            "model_call_performed": False,
            "live_lm_call_performed": False,
            "agent_dispatch_performed": False,
            "worker_dispatch_performed": False,
            "workflow_execution_performed": False,
            "external_action_performed": False,
            "send_submit_performed": False,
            "approval_execution_performed": False,
            "candidate_promotion_performed": False,
            "file_body_read_performed": False,
            "workbook_body_read_performed": False,
            "spreadsheet_cell_read_performed": False,
            "credential_handling_performed": False,
            "raw_body_ingestion_performed": False,
            "network_used": False,
            "all_live_authority_false": all(value is False for value in AUTHORITY_BOUNDARY.values()),
            "content_hash": "",
        },
    }
    payload["machine_proof"]["content_hash"] = _content_hash(payload)
    return payload


def _candidate_from_mapping(proposal: Mapping[str, Any]) -> MachineIntentCandidate:
    field_names = tuple(field.name for field in fields(MachineIntentCandidate))
    missing = tuple(name for name in field_names if name not in proposal)
    if missing:
        raise ValueError(f"Missing MachineIntentCandidate field(s): {', '.join(missing)}")
    tuple_fields = {
        "evidence_refs_used",
        "context_refs_used",
        "source_refs_used",
        "missing_requirements",
        "forbidden_assumptions",
    }
    values: dict[str, Any] = {}
    for name in field_names:
        value = proposal[name]
        if name in tuple_fields:
            values[name] = tuple(str(item) for item in (value or ()))
        elif name in {"authority_requested", "authority_granted"}:
            values[name] = {str(key): bool(flag) for key, flag in dict(value or {}).items()}
        elif name == "validation_required":
            values[name] = bool(value)
        else:
            values[name] = str(value)
    return MachineIntentCandidate(**values)


def validate_proposed_candidate(
    proposal: Mapping[str, Any],
    *,
    package_payload: Mapping[str, Any] | None = None,
    capability_index_payload: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    candidate = _candidate_from_mapping(proposal)
    package = package_payload.get("proposal_package", {}) if isinstance(package_payload, Mapping) else {}
    if package and candidate.source_request_id != str(package.get("source_request_id") or ""):
        candidate = MachineIntentCandidate(
            **{**asdict(candidate), "source_request_id": str(package.get("source_request_id") or candidate.source_request_id)}
        )
    validation_result, missing, build_cues, context_gaps, blockers = intent_validator.validate_machine_intent_candidate(
        candidate,
        capability_index_payload=dict(capability_index_payload or openclaw_capability_index.build_payload()),
    )
    status = "PROPOSAL_VALIDATED" if validation_result.verdict == "VALIDATED_INTENT" else "PROPOSAL_BLOCKED_BY_VALIDATOR"
    receipt = {
        "receipt_id": f"intent_proposal_validation:{_short_hash(candidate.intent_id, validation_result.verdict)}",
        "status": status,
        "source_request_id": candidate.source_request_id,
        "candidate_ref": candidate.intent_id,
        "validation_verdict": validation_result.verdict,
        "authority_granted": validation_result.authority_granted,
        "next_safe_move": validation_result.next_safe_move,
        "model_call_performed": False,
        "execution_performed": False,
    }
    return {
        "proposal_validation_receipt": receipt,
        "candidate": asdict(candidate),
        "validation_result": asdict(validation_result),
        "missing_requirements": tuple(asdict(item) for item in missing),
        "build_cues": tuple(asdict(item) for item in build_cues),
        "context_gaps": tuple(asdict(item) for item in context_gaps),
        "blockers": tuple(asdict(item) for item in blockers),
    }


def write_exports(payload: Mapping[str, Any], export_root: Path = DEFAULT_EXPORT_ROOT) -> tuple[Path, Path]:
    export_root.mkdir(parents=True, exist_ok=True)
    json_path = export_root / JSON_EXPORT_NAME
    operator_path = export_root / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    readback = payload.get("proposal_readback", {}) if isinstance(payload, Mapping) else {}
    package = payload.get("proposal_package", {}) if isinstance(payload, Mapping) else {}
    operator_lines = [
        "# Intent Proposal Contract",
        "",
        f"Status: {readback.get('status', 'UNKNOWN_FAIL_CLOSED')}",
        f"Source request: {package.get('source_request_id', '')}",
        f"Headline: {readback.get('operator_headline', '')}",
        "",
        str(readback.get("operator_message") or ""),
        "",
        str(readback.get("next_action") or ""),
        "",
        "Boundary: no model call, no execution, no send/submit, no body read, no authority grant.",
    ]
    operator_path.write_text("\n".join(operator_lines).rstrip() + "\n", encoding="utf-8")
    return json_path, operator_path


def export_readmodel(
    *,
    export_root: Path = DEFAULT_EXPORT_ROOT,
    generated_at: str | None = None,
    raw_request: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return build_payload(raw_request or {}, export_root=export_root, generated_at=generated_at or DEFAULT_GENERATED_AT)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export proposal-only intent contract read-model.")
    parser.add_argument("--export-root", type=Path, default=DEFAULT_EXPORT_ROOT)
    parser.add_argument("--generated-at", default=DEFAULT_GENERATED_AT)
    parser.add_argument("--format", choices=("summary", "json"), default="summary")
    args = parser.parse_args(argv)

    payload = export_readmodel(export_root=args.export_root, generated_at=args.generated_at)
    json_path, operator_path = write_exports(payload, args.export_root)
    if args.format == "json":
        print(stable_json(payload), end="")
    else:
        summary = {
            "read_model_id": READ_MODEL_ID,
            "status": payload["proposal_readback"]["status"],
            "json_path": json_path.as_posix(),
            "operator_path": operator_path.as_posix(),
            "model_call_performed": payload["machine_proof"]["model_call_performed"],
            "all_live_authority_false": payload["machine_proof"]["all_live_authority_false"],
        }
        print(stable_json(summary), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
