"""Local LM proof-to-response pilot plan V0.

Planning/read-model only. This module chooses the first safe local/approved
proof-to-response pilot lane and records the receipts required before any live
model invocation. It does not invoke models, connect runtimes, spawn workers,
send email, access browser/Gmail/Coupa, or mutate business state.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import proof_bundle_redaction_policy as redaction_policy
import proof_to_response_runtime


ROOT = Path(__file__).resolve().parent
DEFAULT_READ_MODEL_ROOT = Path("generated/read_models")
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_BRIDGE_ROOT = Path("/mnt/e/openclaw/generated/read_models")
DEFAULT_WIKI_PATH = Path("generated/wiki/openclaw/Local LM Proof To Response Pilot Plan.md")

SCHEMA_VERSION = "local_lm_proof_to_response_pilot_plan_v0"
READ_MODEL_ID = "local_lm_proof_to_response_pilot_plan"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
READY_STATUS = "LOCAL_LM_PROOF_RESPONSE_PILOT_PLAN_READY"
NOT_READY_STATUS = "LOCAL_LM_PROOF_RESPONSE_PILOT_PLAN_NOT_READY"

REQUIRED_OPERATOR_APPROVAL_REF = "operator_approval_receipt:local_lm_proof_response_pilot:v0"
SELECTED_HARNESS_REF = "local_llm_shadow_mode"

REQUIRED_RECEIPTS_BEFORE_LIVE_INVOCATION = (
    "operator_approval_receipt",
    "model_harness_selected_receipt",
    "no_external_provider_receipt",
    "redacted_proof_bundle_receipt",
    "no_tool_authority_receipt",
    "verifier_pass_fail_receipt",
    "published_response_hash_receipt",
)

FORBIDDEN_LM_INPUT = (
    "raw_finance_details",
    "bank_account_numbers",
    "credentials_tokens",
    "operator_device_session_verification_secrets",
    "raw_prompt_dumps",
    "raw_artifact_ocr_text",
    "workbook_email_ledger_bodies",
    "hidden_machine_contracts",
    "authority_granted_fields",
)

STOP_CONDITIONS = (
    "model_claims_paid_sent_submitted",
    "model_asks_for_hidden_or_prohibited_context",
    "model_leaks_machine_contract_jargon",
    "model_proposes_protected_action",
    "verifier_fails",
    "proof_bundle_contains_forbidden_field",
    "external_provider_path_appears",
)

AUTHORITY_BOUNDARY = {
    "live_lm_invocation_allowed": False,
    "external_llm_allowed": False,
    "external_provider_connect_allowed": False,
    "local_model_runtime_allowed": False,
    "codex_desktop_operator_assist_allowed": False,
    "hermes_sidecar_invocation_allowed": False,
    "worker_spawn_allowed": False,
    "tool_execution_allowed": False,
    "business_action_allowed": False,
    "email_send_allowed": False,
    "gmail_allowed": False,
    "browser_access_allowed": False,
    "coupa_allowed": False,
    "portal_submit_allowed": False,
    "ledger_mutation_allowed": False,
    "paid_marking_allowed": False,
    "workbook_mutation_allowed": False,
    "pdf_export_allowed": False,
    "memory_promotion_allowed": False,
    "authority_grant_allowed": False,
    "protected_actions_allowed": False,
    "git_push_allowed": False,
    "merge_allowed": False,
}

IMPLEMENTATION_BOUNDARY = {
    "model_invoked": False,
    "live_lm_invoked": False,
    "external_provider_connected": False,
    "external_llm_invoked": False,
    "local_model_runtime_connected": False,
    "worker_spawn_performed": False,
    "tool_execution_performed": False,
    "business_action_performed": False,
    "email_send_performed": False,
    "coupa_submit_performed": False,
    "portal_submit_performed": False,
    "ledger_mutation_performed": False,
    "paid_marking_performed": False,
    "workbook_mutation_performed": False,
    "pdf_export_performed": False,
    "memory_promotion_performed": False,
    "authority_grant_performed": False,
    "git_push_performed": False,
    "merge_performed": False,
}

UNSAFE_TRUE_KEYS = (
    set(AUTHORITY_BOUNDARY)
    | set(IMPLEMENTATION_BOUNDARY)
    | set(redaction_policy.UNSAFE_TRUE_KEYS)
    | set(proof_to_response_runtime.UNSAFE_TRUE_KEYS)
    | {
        "ready_for_live_invocation",
        "allowed_now",
        "live_invocation_ready",
        "authority_granted",
        "paid",
        "sent",
        "submitted",
        "executed",
    }
)

PRECONDITIONS = {
    "local_lm_proof_response_readiness_gate": {
        "filename": "local_lm_proof_to_response_readiness_gate.json",
        "accepted_statuses": ("LOCAL_LM_PROOF_RESPONSE_READINESS_GATE_READY",),
    },
    "local_lm_harness_inventory_receipts": {
        "filename": "local_lm_harness_inventory_receipts.json",
        "accepted_statuses": ("LOCAL_LM_HARNESS_INVENTORY_RECEIPTS_READY",),
    },
    "proof_bundle_redaction_hardening": {
        "filename": "proof_bundle_redaction_policy.json",
        "accepted_statuses": ("PROOF_BUNDLE_REDACTION_HARDENING_READY",),
    },
    "proof_bundle_builder_redaction_integration": {
        "filename": "proof_bundle_builder_redaction_status.json",
        "accepted_statuses": ("PROOF_BUNDLE_BUILDER_REDACTION_INTEGRATION_READY",),
    },
    "agent_response_voice_modes": {
        "filename": "agent_response_voice_modes.json",
        "accepted_statuses": ("AGENT_RESPONSE_VOICE_MODES_READY",),
    },
    "proof_to_response_runtime": {
        "filename": "proof_to_response_runtime_status.json",
        "accepted_statuses": ("PROOF_TO_RESPONSE_RUNTIME_READY",),
    },
    "goldilocks_gate_calibration": {
        "filename": "goldilocks_gate_calibration.json",
        "accepted_statuses": ("GOLDILOCKS_GATE_CALIBRATION_READY",),
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
    return str(payload.get("status") or payload.get("contract_status") or payload.get("readiness_status") or "")


def _shadow_runtime_row(read_model_root: Path) -> dict[str, Any]:
    root = _rooted(read_model_root)
    runtime_status = _load_json(root / proof_to_response_runtime.STATUS_JSON_EXPORT_NAME)
    latest = _load_json(root / proof_to_response_runtime.LATEST_JSON_EXPORT_NAME)
    active_source = str(runtime_status.get("active_candidate_source") or latest.get("candidate_source") or "")
    ready = (
        runtime_status.get("status") == proof_to_response_runtime.READY_STATUS
        and active_source == proof_to_response_runtime.CANDIDATE_SOURCE_SHADOW_PILOT
        and bool(runtime_status.get("source_request_id") or latest.get("source_request_id"))
        and bool(runtime_status.get("world_ref") or latest.get("world_ref"))
        and bool(runtime_status.get("thread_ref") or latest.get("thread_ref"))
    )
    return {
        "precondition_ref": "proof_to_response_shadow_pilot_runtime",
        "source_ref": "generated/read_models/proof_to_response_runtime_status.json",
        "observed_status": "PROOF_TO_RESPONSE_SHADOW_PILOT_RUNTIME_READY" if ready else "PROOF_TO_RESPONSE_SHADOW_PILOT_RUNTIME_NOT_READY",
        "accepted_statuses": ["PROOF_TO_RESPONSE_SHADOW_PILOT_RUNTIME_READY"],
        "ready": ready,
        "active_candidate_source": active_source,
    }


def precondition_rows(read_model_root: Path = DEFAULT_READ_MODEL_ROOT) -> list[dict[str, Any]]:
    root = _rooted(read_model_root)
    rows = [_shadow_runtime_row(root)]
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


def first_pilot_lane() -> dict[str, Any]:
    return {
        "world_ref": "finance",
        "thread_ref": "capital_hilton",
        "objective_ref": "capital_hilton_payment_watch",
        "risk_class": "low_action_risk",
        "reason": "Preferred first lane because it has low action risk, strong proof boundaries, no business execution, and a simple expected response.",
        "expected_response": "Payment evidence is missing. Ledger stays untouched. Next: attach payment evidence.",
        "business_execution_allowed": False,
        "protected_actions_allowed": False,
    }


def pilot_status() -> dict[str, Any]:
    return {
        "ready_for_operator_approval": True,
        "ready_for_live_invocation": False,
        "required_operator_approval_ref": REQUIRED_OPERATOR_APPROVAL_REF,
        "selected_harness_ref": SELECTED_HARNESS_REF,
        "selected_model_ref": "",
        "pilot_scope": ["finance_capital_hilton_payment_watch"],
        "missing_live_receipts": list(REQUIRED_RECEIPTS_BEFORE_LIVE_INVOCATION),
    }


def candidate_source_options() -> list[dict[str, Any]]:
    common_verifier = "proof_to_response_verifier_mandatory"
    return [
        {
            "harness_ref": "local_llm_shadow_mode",
            "allowed_now": False,
            "reason": "blocked_until_operator_approval_and_live_boundary_receipts",
            "missing_receipts": [
                "operator_approval_receipt",
                "model_harness_selected_receipt",
                "model_invocation_boundary_receipt",
                "no_tool_authority_receipt",
            ],
            "privacy_risk": "low_if_redacted_local_only",
            "verifier_requirement": common_verifier,
        },
        {
            "harness_ref": "future_local_open_model",
            "allowed_now": False,
            "reason": "future_model_not_selected_or_approved",
            "missing_receipts": [
                "operator_approval_receipt",
                "model_harness_selected_receipt",
                "approved_local_model_identity_receipt",
                "no_external_provider_receipt",
            ],
            "privacy_risk": "medium_until_model_identity_and_boundary_are_receipted",
            "verifier_requirement": common_verifier,
        },
        {
            "harness_ref": "hermes_sidecar_candidate",
            "allowed_now": False,
            "reason": "blocked_until_explicit_registration_and_receipts",
            "missing_receipts": [
                "explicit_hermes_proof_to_response_registration",
                "operator_approval_receipt",
                "no_tool_authority_receipt",
                "no_external_provider_receipt",
            ],
            "privacy_risk": "unknown_until_sidecar_registration_and_boundary_are_receipted",
            "verifier_requirement": common_verifier,
        },
        {
            "harness_ref": "codex_desktop_operator_assist",
            "allowed_now": False,
            "reason": "blocked_until_explicit_codex_desktop_assist_approval",
            "missing_receipts": [
                "operator_approval_receipt",
                "codex_desktop_operator_assist_scope_receipt",
                "no_tool_authority_receipt",
                "redacted_proof_bundle_receipt",
            ],
            "privacy_risk": "medium_until_surface_scope_and_no_tool_authority_are_receipted",
            "verifier_requirement": common_verifier,
        },
        {
            "harness_ref": "external_llm_blocked_by_default",
            "allowed_now": False,
            "reason": "external_provider_blocked_by_default",
            "missing_receipts": [
                "new_external_provider_exception_gate",
                "operator_approval_receipt",
                "privacy_review_receipt",
                "no_external_provider_receipt_not_possible_for_external_provider",
            ],
            "privacy_risk": "unacceptable_for_default_local_private_proof",
            "verifier_requirement": common_verifier,
        },
    ]


def pilot_runtime_flow() -> list[dict[str, Any]]:
    return [
        {"step_ref": "build_redacted_proof_bundle", "description": "Build Finance / Capital Hilton redacted proof bundle."},
        {"step_ref": "send_allowed_fields_only", "description": "Send only allowed LM input fields to the selected local or explicitly approved harness."},
        {"step_ref": "receive_draft", "description": "Receive a concise draft response; no tool calls or business execution."},
        {"step_ref": "run_deterministic_verifier", "description": "Run proof-to-response verifier before publication."},
        {"step_ref": "publish_or_fallback", "description": "Publish verified response or safe fallback if verification fails."},
        {"step_ref": "record_receipt", "description": "Record candidate source, bundle id, verifier result, rejected reason, and response hash."},
        {"step_ref": "no_tools_no_business_action_no_worker", "description": "Keep tool authority, business actions, and worker spawn disabled."},
    ]


def expected_success_criteria() -> list[str]:
    return [
        "concise_response",
        "correct_agent_voice",
        "no_unsupported_claims",
        "proof_refs_intact",
        "controls_safe",
        "fallback_works_on_bad_draft",
        "mac_can_render_text_first",
    ]


def build_read_model(
    *,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    preconditions = precondition_rows(read_model_root)
    status = pilot_status()
    candidates = candidate_source_options()
    all_preconditions_ready = all(row["ready"] for row in preconditions)
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "status": READY_STATUS if all_preconditions_ready else NOT_READY_STATUS,
        "generated_at": generated_at,
        "purpose": "Choose the first live/local proof-to-response pilot lane and record required receipts before invocation.",
        "pilot_status": status,
        "first_pilot_lane": first_pilot_lane(),
        "allowed_lm_input_fields": list(redaction_policy.ALLOWED_FIELD_REASONS),
        "forbidden_lm_input": list(FORBIDDEN_LM_INPUT),
        "candidate_source_options": candidates,
        "required_receipts_before_live_invocation": list(REQUIRED_RECEIPTS_BEFORE_LIVE_INVOCATION),
        "pilot_runtime_flow": pilot_runtime_flow(),
        "stop_conditions": list(STOP_CONDITIONS),
        "expected_success_criteria": expected_success_criteria(),
        "preconditions": preconditions,
        "source_refs": [
            "generated/read_models/local_lm_proof_to_response_readiness_gate.json",
            "generated/read_models/local_lm_harness_inventory_receipts.json",
            "generated/read_models/proof_bundle_redaction_policy.json",
            "generated/read_models/proof_bundle_builder_redaction_status.json",
            "generated/read_models/agent_response_voice_modes.json",
            "generated/read_models/proof_to_response_runtime_status.json",
            "generated/read_models/proof_to_response_latest.json",
            "generated/read_models/goldilocks_gate_calibration.json",
        ],
        "source_content_hashes": {
            "preconditions": _content_hash(preconditions),
            "pilot_status": _content_hash(status),
            "candidate_source_options": _content_hash(candidates),
            "allowed_lm_input_fields": _content_hash(list(redaction_policy.ALLOWED_FIELD_REASONS)),
        },
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "implementation_boundary": dict(IMPLEMENTATION_BOUNDARY),
        "machine_proof": {
            "preconditions_ready": all_preconditions_ready,
            "low_risk_first_lane_selected": True,
            "ready_for_operator_approval": status["ready_for_operator_approval"],
            "ready_for_live_invocation": status["ready_for_live_invocation"],
            "verifier_mandatory": all(row["verifier_requirement"] == "proof_to_response_verifier_mandatory" for row in candidates),
            "external_llm_blocked_by_default": True,
            "all_candidates_blocked_for_live_invocation": all(row["allowed_now"] is False for row in candidates),
            "unsafe_true_grants": [],
            "unsafe_true_grants_absent": True,
            **IMPLEMENTATION_BOUNDARY,
        },
    }
    unsafe = unsafe_true_grants(payload)
    payload["machine_proof"]["unsafe_true_grants"] = unsafe
    payload["machine_proof"]["unsafe_true_grants_absent"] = not unsafe
    if unsafe:
        payload["status"] = NOT_READY_STATUS
    return payload


def build_wiki(read_model: Mapping[str, Any]) -> str:
    status = read_model.get("pilot_status") if isinstance(read_model.get("pilot_status"), Mapping) else {}
    lane = read_model.get("first_pilot_lane") if isinstance(read_model.get("first_pilot_lane"), Mapping) else {}
    lines = [
        "# Local LM Proof To Response Pilot Plan",
        "",
        f"Status: {read_model.get('status')}",
        f"Ready for operator approval: `{str(status.get('ready_for_operator_approval')).lower()}`",
        f"Ready for live invocation: `{str(status.get('ready_for_live_invocation')).lower()}`",
        "",
        "This plan chooses the first local/approved proof-to-response pilot without invoking a model or connecting any runtime.",
        "",
        "## First Pilot Lane",
        "",
        f"- `{lane.get('world_ref')}/{lane.get('thread_ref')}`: {lane.get('reason')}",
        f"- Expected response: {lane.get('expected_response')}",
        "",
        "## Allowed LM Input",
        "",
    ]
    for field in read_model.get("allowed_lm_input_fields") or []:
        lines.append(f"- `{field}`")
    lines.extend(["", "## Candidate Sources", ""])
    for row in read_model.get("candidate_source_options") or []:
        lines.append(f"- `{row.get('harness_ref')}`: allowed `{str(row.get('allowed_now')).lower()}`, reason `{row.get('reason')}`")
    lines.extend(["", "## Required Receipts", ""])
    for receipt in read_model.get("required_receipts_before_live_invocation") or []:
        lines.append(f"- `{receipt}`")
    lines.extend(["", "## Stop Conditions", ""])
    for condition in read_model.get("stop_conditions") or []:
        lines.append(f"- `{condition}`")
    proof = read_model.get("machine_proof") if isinstance(read_model.get("machine_proof"), Mapping) else {}
    lines.extend(
        [
            "",
            "## Proof",
            "",
            f"- Verifier mandatory: `{str(proof.get('verifier_mandatory')).lower()}`",
            f"- Unsafe true grants absent: `{str(proof.get('unsafe_true_grants_absent')).lower()}`",
            "",
        ]
    )
    return "\n".join(lines)


def export_local_lm_proof_to_response_pilot_plan(
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
    parser = argparse.ArgumentParser(description="Publish Local LM Proof-to-Response Pilot Plan V0.")
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
    result = export_local_lm_proof_to_response_pilot_plan(
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
