"""LM2 structured-output retry approval packet V0.

Approval-packet/read-model only. This packet prepares an operator review record
for one future room-backed LM2 retry using structured-output enforcement. It
does not invoke models, connect runtimes, spawn workers, send prompts or proof
bundles, access business systems, mutate records, export PDFs, mark paid,
submit, or push.
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
import lm2_room_backed_worker_pilot_postmortem as postmortem
import lm2_room_backed_worker_one_time_pilot as one_time_pilot
import proof_bundle_builder as bundles
import proof_to_response_schema_adapter as schema_adapter


ROOT = Path(__file__).resolve().parent
DEFAULT_READ_MODEL_ROOT = Path("generated/read_models")
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_BRIDGE_ROOT = Path("/mnt/e/openclaw/generated/read_models")
DEFAULT_WIKI_PATH = Path("generated/wiki/openclaw/LM2 Structured Output Retry Approval Packet.md")

SCHEMA_VERSION = "lm2_structured_output_retry_approval_packet_v0"
READ_MODEL_ID = "lm2_structured_output_retry_approval_packet"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
READY_STATUS = "LM2_STRUCTURED_OUTPUT_RETRY_APPROVAL_PACKET_READY"
NOT_READY_STATUS = "LM2_STRUCTURED_OUTPUT_RETRY_APPROVAL_PACKET_NOT_READY"
APPROVAL_PACKET_ID = "approval_packet:lm2_room_backed_structured_output_retry:finance_capital_hilton_payment_watch:v0"
APPROVAL_PACKET_STATUS = "pending_operator_review"

PRIOR_ATTEMPT_REF = f"generated/read_models/{one_time_pilot.JSON_EXPORT_NAME}"
PRIOR_POSTMORTEM_REF = f"generated/read_models/{postmortem.JSON_EXPORT_NAME}"
PRIOR_FAILURE_CLASS = "non_json_model_output"
RETRY_REASON = "structured_output_required"

PRECONDITIONS = {
    "lm2_room_backed_worker_one_time_pilot": {
        "filename": one_time_pilot.JSON_EXPORT_NAME,
        "accepted_statuses": (one_time_pilot.READY_STATUS,),
    },
    "lm2_room_backed_worker_pilot_postmortem": {
        "filename": postmortem.JSON_EXPORT_NAME,
        "accepted_statuses": (postmortem.READY_STATUS,),
    },
    "proof_to_response_schema_adapter": {
        "filename": schema_adapter.STATUS_JSON_EXPORT_NAME,
        "accepted_statuses": (schema_adapter.READY_STATUS,),
    },
    "project_room_package_compiler_integration": {
        "filename": "project_room_package_compiler_integration.json",
        "accepted_statuses": ("PROJECT_ROOM_PACKAGE_COMPILER_INTEGRATION_READY",),
    },
    "lm2_room_backed_worker_pilot_boundary": {
        "filename": boundary.ROOM_BACKED_JSON_EXPORT_NAME,
        "accepted_statuses": (boundary.ROOM_BACKED_READY_STATUS,),
    },
    "local_model_selection_for_proof_response": {
        "filename": "local_model_selection_for_proof_response.json",
        "accepted_statuses": ("LOCAL_MODEL_SELECTION_FOR_PROOF_RESPONSE_READY",),
    },
    "proof_bundle_freshness_trace_integration": {
        "filename": bundles.FRESHNESS_TRACE_STATUS_JSON_EXPORT_NAME,
        "accepted_statuses": (bundles.FRESHNESS_TRACE_READY_STATUS,),
    },
    "proof_bundle_builder_redaction_integration": {
        "filename": bundles.REDACTION_STATUS_JSON_EXPORT_NAME,
        "accepted_statuses": (bundles.REDACTION_READY_STATUS,),
    },
}

REQUIRED_SCHEMA_FIELDS = (
    "headline",
    "body",
    "next_step",
    "missing_input",
    "can_do_now",
    "cannot_do_yet",
    "claimed_facts",
    "requested_controls",
    "uncertainty_notes",
)

STRUCTURED_OUTPUT_REQUIREMENTS = (
    "JSON-only response",
    "no markdown",
    "no code fences",
    "no prose outside JSON",
    "one valid JSON example included in prompt",
    "schema adapter runs before verifier",
    "verifier remains the publish gate",
)

PROTECTED_ACTIONS_FORBIDDEN = (
    "repeated_invocations",
    "external_provider",
    "tool_use",
    "browser_gmail_coupa",
    "email_send",
    "send",
    "submit",
    "ledger_mutation",
    "workbook_mutation",
    "pdf_export",
    "paid_marking",
    "memory_promotion",
    "worker_spawning_beyond_the_one_future_retry",
    "file_system_mutation",
    "shell_commands",
    "push_merge",
    "raw_finance_private_proof",
    "operator_device_session_secrets",
    "stale_source_as_current_truth",
    "duplicate_versions_as_equal_evidence",
    "missing_context_as_permission_to_invent",
)

RECEIPTS_REQUIRED_BEFORE = (
    "operator_approval_receipt",
    "structured_output_boundary_receipt",
    "room_backed_package_receipt",
    "project_room_readiness_receipt",
    "model_invocation_boundary_receipt",
    "redacted_proof_bundle_receipt",
    "no_external_provider_receipt",
    "no_tool_authority_receipt",
)

RECEIPTS_REQUIRED_AFTER = (
    "worker_started_receipt",
    "model_invocation_attempt_receipt",
    "raw_draft_captured_receipt",
    "schema_adapter_pass_fail_receipt",
    "worker_stopped_receipt",
    "verifier_pass_fail_receipt",
    "published_response_hash_receipt_or_fallback_receipt",
    "no_business_action_receipt",
)

STOP_CONDITIONS = (
    "project_room_not_ready",
    "source_inventory_missing",
    "unresolved_critical_conflict",
    "missing_context_blocks_supported_claim",
    "freshness_stale_superseded_or_unknown",
    "proof_bundle_contains_forbidden_field",
    "model_returns_non_json",
    "model_returns_markdown_code_fences_or_prose_outside_json",
    "schema_adapter_fails",
    "model_claims_paid_sent_submitted_or_executed",
    "model_promises_protected_action",
    "model_asks_for_hidden_private_context",
    "model_attempts_tool_use",
    "model_exceeds_one_attempt",
    "verifier_fails",
)

OPERATOR_DECISION_OPTIONS = (
    "approve_one_time_room_backed_lm2_structured_output_retry",
    "request_more_detail",
    "choose_different_model",
    "reject_for_now",
)

EXPECTED_OUTPUT_TARGET = {
    "headline": "Payment evidence needed",
    "body": "Coupa is processing. I can't mark this paid until payment evidence is attached. The ledger stays untouched.",
    "next_step": "Attach payment evidence.",
    "missing_input": ["payment_evidence"],
    "can_do_now": ["explain the payment-watch state", "accept payment evidence"],
    "cannot_do_yet": ["mark paid", "post to the ledger", "submit anything"],
    "claimed_facts": ["payment_evidence_missing", "processor_processing", "ledger_untouched", "paid_false"],
    "requested_controls": ["attach_proof"],
    "uncertainty_notes": [],
}

AUTHORITY_BOUNDARY = {
    "approval_packet_is_approval": False,
    "invocation_allowed": False,
    "worker_spawn_allowed": False,
    "proof_bundle_allowed": False,
    "model_invocation_allowed": False,
    "local_model_runtime_allowed": False,
    "structured_output_retry_approved": False,
    "next_invocation_approved": False,
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
    "git_merge_allowed": False,
    "raw_finance_private_proof_allowed": False,
    "operator_device_session_secrets_allowed": False,
    "stale_source_current_truth_allowed": False,
    "duplicate_versions_equal_evidence_allowed": False,
    "missing_context_invention_allowed": False,
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
    "git_merge_performed": False,
    "raw_financial_proof_sent": False,
    "operator_device_session_secret_sent": False,
}

UNSAFE_TRUE_KEYS = (
    set(AUTHORITY_BOUNDARY)
    | set(IMPLEMENTATION_BOUNDARY)
    | set(boundary.UNSAFE_TRUE_KEYS)
    | set(postmortem.UNSAFE_TRUE_KEYS)
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


def prior_result_summary(read_model_root: Path = DEFAULT_READ_MODEL_ROOT) -> dict[str, Any]:
    root = _rooted(read_model_root)
    pilot = _load_json(root / one_time_pilot.JSON_EXPORT_NAME)
    post = _load_json(root / postmortem.JSON_EXPORT_NAME)
    postmortem_record = post.get("postmortem") if isinstance(post.get("postmortem"), Mapping) else {}
    answers = (
        postmortem_record.get("question_answers")
        if isinstance(postmortem_record.get("question_answers"), Mapping)
        else {}
    )
    return {
        "prior_attempt_ref": PRIOR_ATTEMPT_REF,
        "prior_postmortem_ref": PRIOR_POSTMORTEM_REF,
        "prior_attempt_status": pilot.get("status") or "",
        "prior_failure_class": str(postmortem_record.get("failure_class") or PRIOR_FAILURE_CLASS),
        "prior_secondary_failure_class": str(postmortem_record.get("secondary_failure_class") or "structured_output_boundary_failure"),
        "prior_publication_decision": str(pilot.get("publication_decision") or ""),
        "prior_model": (pilot.get("pilot_scope") or {}).get("model_name") if isinstance(pilot.get("pilot_scope"), Mapping) else "",
        "prior_runtime": (pilot.get("pilot_scope") or {}).get("runtime_ref") if isinstance(pilot.get("pilot_scope"), Mapping) else "",
        "safety_wrapper_passed": postmortem_record.get("safety_wrapper_passed") is True,
        "room_backed_package_passed": postmortem_record.get("room_backed_package_passed") is True,
        "fallback_passed": postmortem_record.get("fallback_passed") is True,
        "receipts_passed": postmortem_record.get("receipts_complete") is True,
        "no_protected_actions_occurred": answers.get("did_model_attempt_protected_action") is False,
        "what_failed": answers.get("what_failed") or "",
    }


def build_approval_packet(read_model_root: Path = DEFAULT_READ_MODEL_ROOT) -> dict[str, Any]:
    package = boundary.build_room_backed_package()
    prior = prior_result_summary(read_model_root)
    return {
        "approval_packet_id": APPROVAL_PACKET_ID,
        "status": APPROVAL_PACKET_STATUS,
        "prior_attempt_ref": PRIOR_ATTEMPT_REF,
        "prior_failure_class": PRIOR_FAILURE_CLASS,
        "prior_result": prior,
        "retry_reason": RETRY_REASON,
        "invocation_allowed": False,
        "worker_spawn_allowed": False,
        "proof_bundle_allowed": False,
        "selected_worker_class": boundary.WORKER_CLASS,
        "selected_runtime_ref": boundary.RUNTIME_REF,
        "selected_model_ref": boundary.MODEL_REF,
        "selected_model_name": boundary.MODEL_NAME,
        "pilot_lane": boundary.PILOT_LANE,
        "pilot_question": boundary.QUESTION,
        "package_type": "room_backed_worker_package",
        "structured_output_required": True,
        "schema_adapter_required": True,
        "verifier_required": True,
        "fallback_required": True,
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
        "structured_output_retry_requirements": list(STRUCTURED_OUTPUT_REQUIREMENTS),
        "required_schema_fields": list(REQUIRED_SCHEMA_FIELDS),
        "strict_response_json_schema": schema_adapter.strict_json_draft_schema(),
        "expected_output_target": dict(EXPECTED_OUTPUT_TARGET),
        "protected_actions_forbidden": list(PROTECTED_ACTIONS_FORBIDDEN),
        "receipts_required_before_future_retry": list(RECEIPTS_REQUIRED_BEFORE),
        "receipts_required_after_future_retry": list(RECEIPTS_REQUIRED_AFTER),
        "stop_conditions": list(STOP_CONDITIONS),
        "operator_decision_options": list(OPERATOR_DECISION_OPTIONS),
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
    packet = build_approval_packet(read_model_root)
    stop_conditions = set(packet["stop_conditions"])
    protected = set(packet["protected_actions_forbidden"])
    required_stop_conditions = {
        "model_returns_non_json",
        "model_returns_markdown_code_fences_or_prose_outside_json",
        "schema_adapter_fails",
        "model_claims_paid_sent_submitted_or_executed",
        "model_promises_protected_action",
        "model_attempts_tool_use",
        "model_exceeds_one_attempt",
    }
    required_protected = {
        "repeated_invocations",
        "external_provider",
        "tool_use",
        "browser_gmail_coupa",
        "email_send",
        "send",
        "submit",
        "ledger_mutation",
        "workbook_mutation",
        "pdf_export",
        "paid_marking",
        "memory_promotion",
        "worker_spawning_beyond_the_one_future_retry",
        "file_system_mutation",
        "shell_commands",
        "push_merge",
        "raw_finance_private_proof",
        "operator_device_session_secrets",
        "stale_source_as_current_truth",
        "duplicate_versions_as_equal_evidence",
        "missing_context_as_permission_to_invent",
    }
    machine_proof = {
        "approval_packet_only": True,
        "preconditions_ready": all(row["ready"] for row in preconditions),
        "packet_pending_operator_review": packet["status"] == APPROVAL_PACKET_STATUS,
        "prior_failure_class_non_json": packet["prior_failure_class"] == PRIOR_FAILURE_CLASS,
        "structured_output_required": packet["structured_output_required"] is True,
        "invocation_disallowed": packet["invocation_allowed"] is False,
        "worker_spawn_disallowed": packet["worker_spawn_allowed"] is False,
        "proof_bundle_disallowed": packet["proof_bundle_allowed"] is False,
        "schema_adapter_and_verifier_mandatory": packet["schema_adapter_required"] is True
        and packet["verifier_required"] is True,
        "fallback_mandatory": packet["fallback_required"] is True,
        "required_schema_fields_complete": tuple(packet["required_schema_fields"]) == REQUIRED_SCHEMA_FIELDS,
        "stop_conditions_complete": required_stop_conditions <= stop_conditions,
        "protected_actions_remain_forbidden": required_protected <= protected,
        "operator_decision_options_review_only": tuple(packet["operator_decision_options"]) == OPERATOR_DECISION_OPTIONS,
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
        "purpose": "Create an operator approval packet for one future room-backed LM2 retry using structured-output enforcement.",
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
        "# LM2 Structured Output Retry Approval Packet",
        "",
        f"Status: `{read_model.get('status')}`",
        f"Packet status: `{packet.get('status')}`",
        "",
        "This packet is not approval and does not run LM2. It prepares a review-only operator decision for one future room-backed LM2 retry with structured-output enforcement.",
        "",
        "## Prior Attempt",
        "",
        f"- Prior attempt: `{packet.get('prior_attempt_ref')}`",
        f"- Failure class: `{packet.get('prior_failure_class')}`",
        f"- Retry reason: `{packet.get('retry_reason')}`",
        "",
        "## Retry Scope",
        "",
        f"- Worker class: `{packet.get('selected_worker_class')}`",
        f"- Runtime: `{packet.get('selected_runtime_ref')}`",
        f"- Model: `{packet.get('selected_model_name')}`",
        f"- Lane: `{packet.get('pilot_lane')}`",
        f"- Question: {packet.get('pilot_question')}",
        f"- Structured output required: `{str(packet.get('structured_output_required')).lower()}`",
        "",
        "## Structured Output Requirements",
        "",
    ]
    for item in packet.get("structured_output_retry_requirements") or []:
        lines.append(f"- {item}")
    lines.extend(["", "## Operator Decision Options", ""])
    for option in packet.get("operator_decision_options") or []:
        lines.append(f"- `{option}`")
    lines.extend(["", "## Rules", ""])
    for rule in packet.get("rules") or []:
        lines.append(f"- {rule}")
    lines.append("")
    return "\n".join(lines)


def export_lm2_structured_output_retry_approval_packet(
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
    parser = argparse.ArgumentParser(description="Publish LM2 structured-output retry approval packet.")
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
    result = export_lm2_structured_output_retry_approval_packet(
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
