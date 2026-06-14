"""Local LM proof-to-response readiness gate.

Planning/read-model only. This gate defines what must be true before any
future local or explicitly approved model may read a bounded proof bundle and
draft proof-to-response text. It does not invoke models, connect runtimes,
spawn workers, run tools, or perform business actions.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import proof_bundle_builder
import proof_to_response_runtime


ROOT = Path(__file__).resolve().parent
DEFAULT_READ_MODEL_ROOT = Path("generated/read_models")
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_BRIDGE_ROOT = Path("/mnt/e/openclaw/generated/read_models")
DEFAULT_WIKI_PATH = Path("generated/wiki/openclaw/Local LM Proof To Response Readiness Gate.md")

SCHEMA_VERSION = "local_lm_proof_to_response_readiness_gate_v0"
READ_MODEL_ID = "local_lm_proof_to_response_readiness_gate"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
READY_STATUS = "LOCAL_LM_PROOF_RESPONSE_READINESS_GATE_READY"
NOT_READY_STATUS = "LOCAL_LM_PROOF_RESPONSE_READINESS_GATE_NOT_READY"

MODEL_HARNESS_CLASSES = (
    "local_llm_shadow_mode",
    "future_local_open_model",
    "codex_desktop_operator_assist",
    "external_llm_blocked_by_default",
)

PRECONDITIONS = {
    "proof_to_response_lm_shadow_pilot": {
        "filename": "proof_to_response_lm_shadow_pilot.json",
        "accepted_statuses": ("PROOF_TO_RESPONSE_LM_SHADOW_PILOT_READY",),
    },
    "proof_to_response_runtime": {
        "filename": "proof_to_response_runtime_status.json",
        "accepted_statuses": ("PROOF_TO_RESPONSE_RUNTIME_READY",),
    },
    "goldilocks_gate_calibration": {
        "filename": "goldilocks_gate_calibration.json",
        "accepted_statuses": ("GOLDILOCKS_GATE_CALIBRATION_READY",),
    },
    "self_heal_repair_doctrine": {
        "filename": "self_heal_repair_doctrine.json",
        "accepted_statuses": ("SELF_HEAL_REPAIR_DOCTRINE_READY",),
    },
    "harness_provider_selection": {
        "filename": "harness_provider_selection_registry.json",
        "accepted_statuses": ("HARNESS_PROVIDER_SELECTION_READY",),
    },
    "operator_controller_protocol": {
        "filename": "operator_controller_protocol.json",
        "accepted_statuses": ("OPERATOR_CONTROLLER_PROTOCOL_READY",),
    },
}

AUTHORITY_BOUNDARY = {
    "live_lm_invocation_allowed": False,
    "external_llm_allowed": False,
    "external_provider_connect_allowed": False,
    "local_model_runtime_allowed": False,
    "codex_desktop_operator_assist_allowed": False,
    "worker_spawn_allowed": False,
    "tool_execution_allowed": False,
    "browser_access_allowed": False,
    "gmail_allowed": False,
    "coupa_allowed": False,
    "portal_submit_allowed": False,
    "ledger_mutation_allowed": False,
    "workbook_mutation_allowed": False,
    "pdf_export_allowed": False,
    "paid_marking_allowed": False,
    "memory_promotion_allowed": False,
    "business_action_allowed": False,
    "authority_grant_allowed": False,
    "protected_actions_allowed": False,
    "credential_use_allowed": False,
    "git_push_allowed": False,
    "merge_allowed": False,
}

IMPLEMENTATION_BOUNDARY = {
    "live_lm_invoked": False,
    "external_llm_invoked": False,
    "external_provider_connected": False,
    "local_model_runtime_connected": False,
    "codex_desktop_operator_assist_invoked": False,
    "worker_spawn_performed": False,
    "tool_execution_performed": False,
    "browser_opened": False,
    "gmail_opened": False,
    "coupa_opened": False,
    "portal_submit_performed": False,
    "ledger_mutation_performed": False,
    "workbook_mutation_performed": False,
    "pdf_export_performed": False,
    "paid_marking_performed": False,
    "memory_promotion_performed": False,
    "business_action_performed": False,
    "authority_grant_performed": False,
    "git_push_performed": False,
    "merge_performed": False,
}

UNSAFE_TRUE_KEYS = set(AUTHORITY_BOUNDARY) | set(IMPLEMENTATION_BOUNDARY) | set(proof_to_response_runtime.UNSAFE_TRUE_KEYS) | {
    "authority_granted",
    "paid",
    "sent",
    "submitted",
    "executed",
}

ALLOWED_FIRST_PILOT_SCOPE = (
    "finance_capital_hilton_payment_watch",
    "business_development_capital_hilton_followup",
    "finance_live_arts_md_evidence",
    "build_informational_review",
    "self_heal_repair_explanation",
)

EXPLICITLY_BLOCKED = (
    "business_action_execution",
    "tool_use",
    "browser_gmail_coupa",
    "ledger_workbook_mutation",
    "pdf_export",
    "paid_marking",
    "worker_spawn",
    "external_provider_call",
    "memory_promotion_to_truth",
)


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
    return str(payload.get("status") or payload.get("contract_status") or payload.get("readiness_status") or "")


def _shadow_runtime_row(read_model_root: Path) -> dict[str, Any]:
    root = _rooted(read_model_root)
    runtime_status = _load_json(root / proof_to_response_runtime.STATUS_JSON_EXPORT_NAME)
    latest = _load_json(root / proof_to_response_runtime.LATEST_JSON_EXPORT_NAME)
    active_source = str(runtime_status.get("active_candidate_source") or latest.get("candidate_source") or "")
    ready = (
        runtime_status.get("status") == proof_to_response_runtime.READY_STATUS
        and active_source == proof_to_response_runtime.CANDIDATE_SOURCE_SHADOW_PILOT
        and bool(latest.get("source_request_id"))
        and bool(latest.get("world_ref"))
        and bool(latest.get("thread_ref"))
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
    rows: list[dict[str, Any]] = [_shadow_runtime_row(root)]
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


def model_harness_classes() -> list[dict[str, Any]]:
    return [
        {
            "model_harness_class": "local_llm_shadow_mode",
            "display_name": "Local LLM Shadow Mode",
            "allowed_for_response_drafting": True,
            "allowed_for_live_pilot": False,
            "allowed_modes": ["proof_to_response_shadow_only"],
            "default_policy": "shadow_only_until_explicit_live_gate",
            "required_before_live": [
                "explicit_operator_approval",
                "local_only_runtime_sandbox_receipt",
                "proof_bundle_redaction_audit",
                "verifier_fallback_receipt",
            ],
            "business_execution_allowed": False,
            "authority_boundary": dict(AUTHORITY_BOUNDARY),
        },
        {
            "model_harness_class": "future_local_open_model",
            "display_name": "Future Local Open Model",
            "allowed_for_response_drafting": False,
            "allowed_for_live_pilot": False,
            "allowed_modes": ["future_gated_only"],
            "default_policy": "blocked_until_harness_receipt_and_operator_approval",
            "required_before_live": [
                "explicit_operator_approval",
                "approved_local_model_identity",
                "no_network_provider_receipt",
                "bounded_context_window_receipt",
                "verifier_fallback_receipt",
            ],
            "business_execution_allowed": False,
            "authority_boundary": dict(AUTHORITY_BOUNDARY),
        },
        {
            "model_harness_class": "codex_desktop_operator_assist",
            "display_name": "Codex Desktop Operator Assist",
            "allowed_for_response_drafting": False,
            "allowed_for_live_pilot": False,
            "allowed_modes": ["explicit_approval_only"],
            "default_policy": "blocked_unless_explicitly_approved_for_this_gate",
            "required_before_live": [
                "explicit_operator_approval",
                "surface_scope_receipt",
                "proof_bundle_redaction_audit",
            ],
            "business_execution_allowed": False,
            "authority_boundary": dict(AUTHORITY_BOUNDARY),
        },
        {
            "model_harness_class": "external_llm_blocked_by_default",
            "display_name": "External LLM",
            "allowed_for_response_drafting": False,
            "allowed_for_live_pilot": False,
            "allowed_modes": ["blocked_by_default"],
            "default_policy": "blocked_by_default",
            "required_before_live": [
                "new_explicit_provider_gate",
                "privacy_review",
                "operator_approval",
            ],
            "business_execution_allowed": False,
            "authority_boundary": dict(AUTHORITY_BOUNDARY),
        },
    ]


def data_boundaries() -> dict[str, Any]:
    allowed_fields = [field for field in proof_bundle_builder.REQUIRED_BUNDLE_FIELDS]
    return {
        "allowed_proof_bundle_fields": allowed_fields,
        "excluded_fields_and_material": [
            "raw_sensitive_details",
            "operator_envelope",
            "device_verification_material",
            "session_verification_material",
            "operator_device_secret_material",
            "credentials_or_tokens",
            "raw_bank_details",
            "raw_prompt_dumps",
            "source_workbook_bodies",
            "attachment_file_bodies",
            "browser_session_state",
            "gmail_message_bodies",
            "coupa_session_data",
        ],
        "financial_sensitive_policy": {
            "required_privacy_class": "financial_sensitive/local_only",
            "redaction_required": True,
            "raw_bank_details_allowed_to_model": False,
            "allowed_summary": "redacted payment status, proof refs, receipt refs, and candidate-evidence labels only",
        },
        "raw_prompt_policy": "no_raw_prompt_dumps_to_model",
        "workbook_policy": "source_workbook_bodies_excluded; read-model summaries only",
    }


def required_verifier_behavior() -> dict[str, Any]:
    return {
        "all_lm_drafts_pass_proof_to_response_verifier": True,
        "failed_drafts_publish_safe_fallback": True,
        "bad_claims_recorded": True,
        "unsafe_draft_text_published": False,
        "no_authority_grants": True,
        "no_protected_action_promises": True,
        "no_machine_contract_jargon": True,
        "blocked_claims": [
            "unsupported_paid_sent_submitted_executed_claims",
            "authority_grants",
            "protected_action_promises",
            "machine_contract_jargon",
            "unproven_receipt_or_source_claims",
        ],
        "verifier_ref": "proof_to_response_verifier.py",
    }


def required_audit_receipt_behavior() -> dict[str, Any]:
    return {
        "candidate_source_recorded": True,
        "proof_bundle_id_recorded": True,
        "verifier_result_recorded": True,
        "rejected_draft_reason_recorded": True,
        "published_response_hash_recorded": True,
        "receipt_refs_required": [
            "candidate_source",
            "proof_bundle_id",
            "verifier_result",
            "verification_errors",
            "response_content_hash",
        ],
    }


def readiness_decision(preconditions: list[dict[str, Any]]) -> dict[str, Any]:
    blockers = []
    if not all(row.get("ready") is True for row in preconditions):
        blockers.append("required_preconditions_not_ready")
    blockers.extend(
        [
            "explicit_operator_approval_missing",
            "approved_local_model_harness_receipt_missing",
            "live_local_model_runtime_sandbox_receipt_missing",
        ]
    )
    return {
        "ready_for_live_local_lm_pilot": False,
        "blockers": blockers,
        "next_safe_action": "Run another verifier-gated shadow/mock pilot or request explicit approval for a local-only model harness.",
    }


def build_read_model(
    *,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    preconditions = precondition_rows(read_model_root)
    decision = readiness_decision(preconditions)
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "status": READY_STATUS if all(row["ready"] for row in preconditions) else NOT_READY_STATUS,
        "generated_at": generated_at,
        "purpose": "Define the gate for any future local or explicitly approved model drafting proof-to-response text from bounded proof bundles.",
        "model_harness_classes": model_harness_classes(),
        "data_boundaries": data_boundaries(),
        "required_verifier_behavior": required_verifier_behavior(),
        "required_audit_receipt_behavior": required_audit_receipt_behavior(),
        "allowed_first_pilot_scope": list(ALLOWED_FIRST_PILOT_SCOPE),
        "scope_boundary": {
            "proof_to_response_only": True,
            "dynamic_cards_support_only": True,
            "details_collapsed_by_default": True,
            "business_execution_allowed": False,
        },
        "explicitly_blocked": list(EXPLICITLY_BLOCKED),
        "readiness_decision": decision,
        "preconditions": preconditions,
        "source_refs": [
            "generated/read_models/proof_to_response_lm_shadow_pilot.json",
            "generated/read_models/proof_to_response_runtime_status.json",
            "generated/read_models/proof_to_response_latest.json",
            "generated/read_models/goldilocks_gate_calibration.json",
            "generated/read_models/self_heal_repair_doctrine.json",
            "generated/read_models/harness_provider_selection_registry.json",
            "generated/read_models/operator_controller_protocol.json",
        ],
        "source_content_hashes": {
            "preconditions": _content_hash(preconditions),
            "model_harness_classes": _content_hash(model_harness_classes()),
            "data_boundaries": _content_hash(data_boundaries()),
        },
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "implementation_boundary": dict(IMPLEMENTATION_BOUNDARY),
    }
    unsafe = unsafe_true_grants(payload)
    payload["machine_proof"] = {
        "preconditions_ready": all(row["ready"] for row in preconditions),
        "gate_published": True,
        "ready_for_live_local_lm_pilot": decision["ready_for_live_local_lm_pilot"],
        "external_llm_blocked_by_default": True,
        "local_lm_shadow_only": True,
        "verifier_required": True,
        "unsafe_true_grants": unsafe,
        "unsafe_true_grants_absent": not unsafe,
        **IMPLEMENTATION_BOUNDARY,
    }
    if unsafe:
        payload["status"] = NOT_READY_STATUS
    return payload


def build_wiki(read_model: Mapping[str, Any]) -> str:
    decision = read_model.get("readiness_decision") if isinstance(read_model.get("readiness_decision"), Mapping) else {}
    lines = [
        "# Local LM Proof To Response Readiness Gate",
        "",
        f"Status: {read_model.get('status')}",
        f"Ready for live local LM pilot: `{str(decision.get('ready_for_live_local_lm_pilot')).lower()}`",
        "",
        "This gate defines what must be true before any future local or explicitly approved model may read a bounded proof bundle and draft proof-to-response text.",
        "",
        "## Allowed Harness Classes",
        "",
    ]
    for row in read_model.get("model_harness_classes") or []:
        lines.append(f"- `{row.get('model_harness_class')}`: {row.get('default_policy')}")
    lines.extend(["", "## Data Boundaries", ""])
    for item in (read_model.get("data_boundaries") or {}).get("excluded_fields_and_material") or []:
        lines.append(f"- Exclude `{item}`")
    lines.extend(["", "## Verifier Gate", ""])
    verifier = read_model.get("required_verifier_behavior") if isinstance(read_model.get("required_verifier_behavior"), Mapping) else {}
    for item in verifier.get("blocked_claims") or []:
        lines.append(f"- Block `{item}`")
    lines.extend(["", "## First Pilot Scope", ""])
    for item in read_model.get("allowed_first_pilot_scope") or []:
        lines.append(f"- `{item}`")
    lines.extend(["", "## Explicitly Blocked", ""])
    for item in read_model.get("explicitly_blocked") or []:
        lines.append(f"- `{item}`")
    lines.extend(
        [
            "",
            "## Decision",
            "",
            f"- Blockers: `{decision.get('blockers')}`",
            f"- Next safe action: {decision.get('next_safe_action')}",
            "",
        ]
    )
    return "\n".join(lines)


def export_local_lm_proof_to_response_readiness_gate(
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
        "ready_for_live_local_lm_pilot": str(read_model["readiness_decision"]["ready_for_live_local_lm_pilot"]).lower(),
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Publish Local LM Proof-to-Response Readiness Gate V0.")
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
    result = export_local_lm_proof_to_response_readiness_gate(
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
