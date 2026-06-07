"""Local LM proof-to-response retry approval packet V0.

Review/approval packet for one future local Qwen proof-to-response retry using
the JSON-only schema adapter. This module only writes read-model/wiki artifacts;
it does not invoke models, connect Ollama, send prompts or proof bundles, call
APIs, spawn workers, mutate business systems, or push.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import proof_to_response_model_quality_comparison as quality_comparison
import proof_to_response_schema_adapter as schema_adapter
import proof_to_response_verifier as verifier


ROOT = Path(__file__).resolve().parent
DEFAULT_READ_MODEL_ROOT = Path("generated/read_models")
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_BRIDGE_ROOT = Path("/mnt/e/openclaw/generated/read_models")
DEFAULT_WIKI_PATH = Path("generated/wiki/openclaw/Local LM Proof Response Retry Approval Packet.md")

SCHEMA_VERSION = "local_lm_proof_response_retry_approval_packet_v0"
READ_MODEL_ID = "local_lm_proof_response_retry_approval_packet"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
READY_STATUS = "LOCAL_LM_PROOF_RESPONSE_RETRY_APPROVAL_PACKET_READY"
NOT_READY_STATUS = "LOCAL_LM_PROOF_RESPONSE_RETRY_APPROVAL_PACKET_NOT_READY"
PACKET_STATUS = "pending_operator_review"
PACKET_ID = "approval_packet:local_lm_proof_response_retry:finance_capital_hilton:qwen_schema_adapter:v0"

RUNTIME_REF = "ollama"
MODEL_REF = "qwen3:8b-q4_K_M"
LANE_REF = "finance/capital_hilton"
QUESTION = "What should I do here?"
PRIOR_ATTEMPT_RESULT = "failed_non_json"
RETRY_REASON = "schema_adapter_now_ready"
REQUIRED_PROMPT_MODE = "json_only"

DECISION_OPTIONS = (
    "approve_one_time_local_lm_retry_with_schema_adapter",
    "request_more_detail",
    "choose_different_model",
    "reject_for_now",
)

REQUIRED_RECEIPTS_BEFORE_RETRY = (
    "operator_approval_receipt",
    "model_invocation_boundary_receipt",
    "redacted_freshness_gated_proof_bundle_receipt",
    "json_only_prompt_receipt",
    "valid_example_included_receipt",
    "no_external_provider_receipt",
    "no_tool_authority_receipt",
    "verifier_pass_fail_receipt",
    "published_response_hash_or_fallback_receipt",
)

FORBIDDEN_ACTIONS = (
    "external_provider_call",
    "tool_use",
    "memory_promotion",
    "browser_access",
    "gmail_access",
    "coupa_access",
    "email_send",
    "send",
    "submit",
    "ledger_mutation",
    "workbook_mutation",
    "pdf_export",
    "paid_marking",
    "worker_spawn",
    "git_push",
    "merge",
    "raw_finance_private_proof",
    "operator_device_session_secrets",
)

ALLOWED_INPUT_FIELDS = (
    "world_ref",
    "thread_ref",
    "objective_ref",
    "redacted_known_facts",
    "proof_meter_labels",
    "receipt_refs",
    "gate_labels",
    "missing_input",
    "allowed_controls",
    "blocked_action_summaries",
    "human_safe_summaries",
    "agent_voice_mode",
)

FORBIDDEN_INPUTS = (
    "raw_finance_details",
    "private_finance_proof",
    "bank_account_numbers",
    "routing_numbers",
    "credentials_or_tokens",
    "operator_device_session_verification_secrets",
    "raw_prompt_dumps",
    "raw_artifact_or_ocr_text",
    "workbook_bodies",
    "email_bodies",
    "ledger_rows",
    "internal_paths",
    "authority_granted_fields",
)

AUTHORITY_BOUNDARY = {
    "approval_packet_is_invocation_approval": False,
    "invocation_allowed": False,
    "proof_bundle_allowed": False,
    "model_invocation_allowed": False,
    "local_model_runtime_allowed": False,
    "external_llm_allowed": False,
    "external_provider_connect_allowed": False,
    "tool_authority_allowed": False,
    "tool_execution_allowed": False,
    "memory_promotion_allowed": False,
    "worker_spawn_allowed": False,
    "business_action_allowed": False,
    "email_send_allowed": False,
    "gmail_allowed": False,
    "browser_access_allowed": False,
    "coupa_allowed": False,
    "portal_submit_allowed": False,
    "ledger_mutation_allowed": False,
    "ledger_posting_allowed": False,
    "workbook_mutation_allowed": False,
    "pdf_export_allowed": False,
    "paid_marking_allowed": False,
    "git_push_allowed": False,
    "merge_allowed": False,
    "authority_grant_allowed": False,
    "protected_actions_allowed": False,
}

IMPLEMENTATION_BOUNDARY = {
    "model_invocation_performed": False,
    "local_model_runtime_connected": False,
    "external_api_called": False,
    "external_llm_invoked": False,
    "external_provider_connected": False,
    "prompt_sent": False,
    "proof_bundle_sent": False,
    "worker_spawn_performed": False,
    "business_action_performed": False,
    "email_send_performed": False,
    "gmail_access_performed": False,
    "browser_access_performed": False,
    "coupa_access_performed": False,
    "portal_submit_performed": False,
    "ledger_mutation_performed": False,
    "ledger_posting_performed": False,
    "workbook_mutation_performed": False,
    "pdf_export_performed": False,
    "paid_marking_performed": False,
    "git_push_performed": False,
    "merge_performed": False,
    "secret_read_performed": False,
}

UNSAFE_TRUE_KEYS = (
    set(AUTHORITY_BOUNDARY)
    | set(IMPLEMENTATION_BOUNDARY)
    | set(schema_adapter.UNSAFE_TRUE_KEYS)
    | set(verifier.UNSAFE_TRUE_KEYS)
    | set(quality_comparison.UNSAFE_TRUE_KEYS)
    | {
        "approved",
        "operator_approved",
        "approval_granted",
        "invocation_approved",
        "approved_for_live_invocation",
        "ready_for_live_invocation",
        "proof_bundle_exposure_approved",
        "tool_authority_granted",
        "authority_granted",
        "paid",
        "sent",
        "submitted",
        "executed",
    }
)

PRECONDITIONS = {
    "local_lm_proof_response_pilot_postmortem": {
        "filename": "local_lm_proof_response_pilot_postmortem.json",
        "accepted_statuses": ("LOCAL_LM_PROOF_RESPONSE_PILOT_POSTMORTEM_READY",),
    },
    "proof_to_response_schema_adapter": {
        "filename": "proof_to_response_schema_adapter_status.json",
        "accepted_statuses": ("PROOF_TO_RESPONSE_SCHEMA_ADAPTER_READY",),
    },
    "local_model_selection_for_proof_response": {
        "filename": "local_model_selection_for_proof_response.json",
        "accepted_statuses": ("LOCAL_MODEL_SELECTION_FOR_PROOF_RESPONSE_READY",),
    },
    "proof_bundle_freshness_trace_integration": {
        "filename": "proof_bundle_freshness_trace_status.json",
        "accepted_statuses": ("PROOF_BUNDLE_FRESHNESS_TRACE_INTEGRATION_READY",),
    },
    "proof_bundle_builder_redaction_integration": {
        "filename": "proof_bundle_builder_redaction_status.json",
        "accepted_statuses": ("PROOF_BUNDLE_BUILDER_REDACTION_INTEGRATION_READY",),
    },
    "proof_to_response_runtime": {
        "filename": "proof_to_response_runtime_status.json",
        "accepted_statuses": ("PROOF_TO_RESPONSE_RUNTIME_READY",),
    },
    "local_lm_proof_response_one_time_pilot": {
        "filename": "local_lm_proof_response_one_time_pilot.json",
        "accepted_statuses": ("LOCAL_LM_PROOF_RESPONSE_ONE_TIME_PILOT_READY",),
    },
    "proof_response_model_quality_comparison": {
        "filename": "proof_to_response_model_quality_comparison.json",
        "accepted_statuses": ("PROOF_RESPONSE_MODEL_QUALITY_COMPARISON_READY",),
    },
}


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _rooted(path: Path | str) -> Path:
    path = Path(path)
    return path if path.is_absolute() else ROOT / path


def _load_json(path: Path) -> dict[str, Any]:
    path = _rooted(path)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
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


def _source_hashes(read_model_root: Path, filenames: list[str]) -> dict[str, str]:
    root = _rooted(read_model_root)
    hashes: dict[str, str] = {}
    for filename in filenames:
        payload = _load_json(root / filename)
        hashes[f"generated/read_models/{filename}"] = _content_hash(payload) if payload else ""
    return hashes


def _prior_failure(postmortem: Mapping[str, Any]) -> dict[str, Any]:
    answer = postmortem.get("answer_to_required_questions") if isinstance(postmortem.get("answer_to_required_questions"), Mapping) else {}
    analysis = postmortem.get("analysis") if isinstance(postmortem.get("analysis"), Mapping) else {}
    classification = analysis.get("failure_classification") if isinstance(analysis.get("failure_classification"), Mapping) else {}
    return {
        "prior_attempt_result": PRIOR_ATTEMPT_RESULT,
        "source_failure_type": str(answer.get("failure_type") or ""),
        "what_failed": str(answer.get("what_exactly_failed") or analysis.get("what_failed") or ""),
        "non_json": classification.get("non_json") is True,
        "structurally_invalid": classification.get("structurally_invalid") is True,
        "unsupported_completion_claims_present": answer.get("unsupported_completion_claims_present") is True,
        "protected_action_promises_present": answer.get("protected_action_promises_present") is True,
        "machine_contract_jargon_present": answer.get("machine_contract_jargon_present") is True,
        "fallback_correctly_published": answer.get("fallback_correctly_published") is True,
    }


def _retry_rationale(comparison: Mapping[str, Any], schema_status: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "retry_reason": RETRY_REASON,
        "comparison_recommended_next_test": str(comparison.get("recommended_next_test") or ""),
        "schema_adapter_ready": schema_status.get("adapter_ready") is True,
        "json_only_prompt_contract_ready": schema_status.get("json_only_prompt_contract_ready") is True,
        "verifier_candidate_mapping_ready": schema_status.get("verifier_candidate_mapping_ready") is True,
        "reasons": list(comparison.get("reasons") or []),
    }


def build_retry_approval_packet(
    *,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    root = _rooted(read_model_root)
    postmortem = _load_json(root / "local_lm_proof_response_pilot_postmortem.json")
    schema_status = _load_json(root / "proof_to_response_schema_adapter_status.json")
    comparison = _load_json(root / "proof_to_response_model_quality_comparison.json")
    preconditions = precondition_rows(root)
    preconditions_ready = all(row["ready"] for row in preconditions)
    source_filenames = [str(spec["filename"]) for spec in PRECONDITIONS.values()]

    packet = {
        "packet_id": PACKET_ID,
        "status": PACKET_STATUS,
        "prior_attempt_result": PRIOR_ATTEMPT_RESULT,
        "retry_reason": RETRY_REASON,
        "runtime": RUNTIME_REF,
        "model": MODEL_REF,
        "lane": LANE_REF,
        "question": QUESTION,
        "allowed_input": "redacted freshness-gated proof bundle only",
        "allowed_input_fields": list(ALLOWED_INPUT_FIELDS),
        "forbidden_inputs": list(FORBIDDEN_INPUTS),
        "required_prompt_mode": REQUIRED_PROMPT_MODE,
        "required_valid_example": True,
        "schema_adapter_required": True,
        "schema_adapter_ref": "proof_to_response_schema_adapter.adapt_model_draft",
        "verifier_required": True,
        "verifier_ref": "proof_to_response_verifier.verify_lm_shadow_response",
        "fallback_required": True,
        "invocation_allowed": False,
        "proof_bundle_allowed": False,
        "one_retry_attempt_only_if_later_approved": True,
        "boundary": {
            "external_provider_allowed": False,
            "tool_use_allowed": False,
            "memory_promotion_allowed": False,
            "browser_gmail_coupa_allowed": False,
            "email_send_submit_allowed": False,
            "ledger_workbook_pdf_paid_mutation_allowed": False,
            "worker_spawn_allowed": False,
            "push_merge_allowed": False,
            "raw_finance_private_proof_allowed": False,
            "operator_device_session_secrets_allowed": False,
        },
        "forbidden_actions": list(FORBIDDEN_ACTIONS),
        "decision_options": list(DECISION_OPTIONS),
        "required_receipts_before_retry": list(REQUIRED_RECEIPTS_BEFORE_RETRY),
    }

    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "status": READY_STATUS if preconditions_ready else NOT_READY_STATUS,
        "generated_at": generated_at,
        "purpose": "Review-only approval packet for one future local Qwen proof-to-response retry using the JSON-only schema adapter.",
        "packet": packet,
        "prior_attempt": _prior_failure(postmortem),
        "retry_rationale": _retry_rationale(comparison, schema_status),
        "preconditions": preconditions,
        "source_refs": [f"generated/read_models/{filename}" for filename in source_filenames],
        "source_content_hashes": _source_hashes(root, source_filenames),
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "implementation_boundary": dict(IMPLEMENTATION_BOUNDARY),
    }
    unsafe = unsafe_true_grants(payload)
    payload["machine_proof"] = {
        "review_only": True,
        "preconditions_ready": preconditions_ready,
        "packet_pending_operator_review": packet["status"] == PACKET_STATUS,
        "invocation_allowed": False,
        "proof_bundle_allowed": False,
        "schema_adapter_required": True,
        "verifier_required": True,
        "fallback_required": True,
        "protected_actions_blocked": True,
        "model_invocation_performed": False,
        "local_model_runtime_connected": False,
        "external_api_called": False,
        "prompt_sent": False,
        "proof_bundle_sent": False,
        "business_action_performed": False,
        "unsafe_true_grants": unsafe,
        "unsafe_true_grants_absent": not unsafe,
    }
    if unsafe:
        payload["status"] = NOT_READY_STATUS
    payload["content_hash"] = _content_hash({k: v for k, v in payload.items() if k != "content_hash"})
    return payload


def build_wiki(model: Mapping[str, Any]) -> str:
    packet = model.get("packet") if isinstance(model.get("packet"), Mapping) else {}
    lines = [
        "# Local LM Proof Response Retry Approval Packet",
        "",
        f"Status: `{model.get('status', NOT_READY_STATUS)}`",
        f"Packet status: `{packet.get('status', PACKET_STATUS)}`",
        "",
        "This is a review-only packet for one future local Qwen proof-to-response retry using the JSON-only schema adapter.",
        "It does not invoke a model, connect Ollama, send a prompt, send a proof bundle, call APIs, mutate business systems, or push.",
        "",
        "## Scope",
        "",
        f"- Runtime: `{packet.get('runtime')}`",
        f"- Model: `{packet.get('model')}`",
        f"- Lane: `{packet.get('lane')}`",
        f"- Question: {packet.get('question')}",
        f"- Prior result: `{packet.get('prior_attempt_result')}`",
        f"- Retry reason: `{packet.get('retry_reason')}`",
        "",
        "## Requirements",
        "",
        "- JSON-only prompt mode.",
        "- One valid example must be included.",
        "- Schema adapter, verifier, and fallback are mandatory.",
        "- Invocation and proof bundle access remain false until a separate operator approval.",
        "",
        "## Decision Options",
        "",
    ]
    for option in packet.get("decision_options", []):
        lines.append(f"- `{option}`")
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            "- No external provider.",
            "- No tool use, memory promotion, browser/Gmail/Coupa, email/send/submit, ledger/workbook/PDF/paid mutation, worker spawn, push, or merge.",
            "- No raw finance/private proof or operator/device/session secrets.",
        ]
    )
    return "\n".join(lines) + "\n"


def export_retry_approval_packet(
    *,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
    export_root: Path = DEFAULT_EXPORT_ROOT,
    bridge_root: Path | None = DEFAULT_BRIDGE_ROOT,
    wiki_path: Path = DEFAULT_WIKI_PATH,
    generated_at: str | None = None,
) -> dict[str, str]:
    model = build_retry_approval_packet(read_model_root=read_model_root, generated_at=generated_at)
    export_root = _rooted(export_root)
    export_root.mkdir(parents=True, exist_ok=True)
    json_path = export_root / JSON_EXPORT_NAME
    _write_json(json_path, model)

    bridge_path = ""
    if bridge_root is not None:
        bridge_root = _rooted(bridge_root)
        bridge_root.mkdir(parents=True, exist_ok=True)
        target = bridge_root / JSON_EXPORT_NAME
        shutil.copy2(json_path, target)
        bridge_path = target.as_posix()

    wiki_path = _rooted(wiki_path)
    wiki_path.parent.mkdir(parents=True, exist_ok=True)
    wiki_path.write_text(build_wiki(model), encoding="utf-8")
    return {
        "status": str(model["status"]),
        "json_path": json_path.as_posix(),
        "bridge_path": bridge_path,
        "wiki_path": wiki_path.as_posix(),
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Export local LM proof-response retry approval packet V0.")
    parser.add_argument("--read-model-root", default=str(DEFAULT_READ_MODEL_ROOT))
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT))
    parser.add_argument("--bridge-root", default=str(DEFAULT_BRIDGE_ROOT))
    parser.add_argument("--wiki-path", default=str(DEFAULT_WIKI_PATH))
    parser.add_argument("--generated-at")
    parser.add_argument("--no-bridge", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    result = export_retry_approval_packet(
        read_model_root=Path(args.read_model_root),
        export_root=Path(args.export_root),
        bridge_root=None if args.no_bridge else Path(args.bridge_root),
        wiki_path=Path(args.wiki_path),
        generated_at=args.generated_at,
    )
    print(stable_json(result), end="")
    return 0 if result["status"] == READY_STATUS else 1


if __name__ == "__main__":
    raise SystemExit(main())
