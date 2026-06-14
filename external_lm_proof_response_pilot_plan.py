"""External LM proof-to-response pilot plan V0.

Planning/read-model only for a future synthetic or fully redacted external LLM
quality test. This module does not invoke providers, call APIs, browse, read
secrets/API keys, send prompts or proof bundles, spawn workers, send email,
open browser/Gmail/Coupa, mutate ledgers/workbooks, export PDFs, mark paid,
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

import model_catalog_inventory
import proof_bundle_redaction_policy as redaction_policy
import proof_to_response_runtime


ROOT = Path(__file__).resolve().parent
DEFAULT_READ_MODEL_ROOT = Path("generated/read_models")
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_BRIDGE_ROOT = Path("/mnt/e/openclaw/generated/read_models")
DEFAULT_WIKI_PATH = Path("generated/wiki/openclaw/External LM Proof Response Pilot Plan.md")

SCHEMA_VERSION = "external_lm_proof_response_pilot_plan_v0"
READ_MODEL_ID = "external_lm_proof_response_pilot_plan"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
READY_STATUS = "EXTERNAL_LM_PROOF_RESPONSE_PILOT_PLAN_READY"
NOT_READY_STATUS = "EXTERNAL_LM_PROOF_RESPONSE_PILOT_PLAN_NOT_READY"

PRECONDITIONS = {
    "model_catalog_inventory": {
        "filename": "model_catalog_inventory.json",
        "accepted_statuses": ("MODEL_CATALOG_INVENTORY_READY",),
    },
    "proof_to_response_lm_shadow_pilot": {
        "filename": "proof_to_response_lm_shadow_pilot.json",
        "accepted_statuses": ("PROOF_TO_RESPONSE_LM_SHADOW_PILOT_READY",),
    },
    "proof_bundle_redaction_hardening": {
        "filename": "proof_bundle_redaction_policy.json",
        "accepted_statuses": ("PROOF_BUNDLE_REDACTION_HARDENING_READY",),
    },
    "proof_bundle_builder_redaction_integration": {
        "filename": "proof_bundle_builder_redaction_status.json",
        "accepted_statuses": ("PROOF_BUNDLE_BUILDER_REDACTION_INTEGRATION_READY",),
    },
    "context_freshness_decision_trace_gate": {
        "filename": "context_freshness_decision_trace_gate.json",
        "accepted_statuses": ("CONTEXT_FRESHNESS_DECISION_TRACE_GATE_READY",),
    },
    "proof_bundle_freshness_trace_integration": {
        "filename": "proof_bundle_freshness_trace_status.json",
        "accepted_statuses": ("PROOF_BUNDLE_FRESHNESS_TRACE_INTEGRATION_READY",),
    },
    "agent_response_voice_modes": {
        "filename": "agent_response_voice_modes.json",
        "accepted_statuses": ("AGENT_RESPONSE_VOICE_MODES_READY",),
    },
    "proof_to_response_runtime": {
        "filename": proof_to_response_runtime.STATUS_JSON_EXPORT_NAME,
        "accepted_statuses": (proof_to_response_runtime.READY_STATUS,),
    },
    "goldilocks_gate_calibration": {
        "filename": "goldilocks_gate_calibration.json",
        "accepted_statuses": ("GOLDILOCKS_GATE_CALIBRATION_READY",),
    },
}

PILOT_PURPOSE = (
    "Compare external LLM response quality against local and shadow response quality.",
    "Test agent voice, concision, helpfulness, and verifier compatibility.",
    "Do not test business execution.",
    "Do not send private proof.",
)

APPROVED_FIRST_TEST_DATA = (
    "synthetic_proof_bundle",
    "fully_redacted_real_shaped_proof_bundle",
)

SYNTHETIC_FACTS = (
    "payment evidence missing",
    "payment processor says processing",
    "ledger untouched",
    "paid=false",
    "next safe action: attach payment evidence",
)

EXPECTED_EXTERNAL_OUTPUT = {
    "headline": "Payment evidence needed",
    "body_requirements": [
        "concise human text",
        "no paid claim",
        "no sent or submitted claim",
        "no execution promise",
    ],
    "next_step": "Attach payment evidence.",
}

EXPLICITLY_BLOCKED_DATA = (
    "real_private_finance_proof",
    "client_payment_documents",
    "actual_bank_screenshots",
    "raw_email_coupa_gmail_browser_content",
    "workbook_bodies",
    "ledger_rows",
    "credentials_or_tokens",
    "any_unredacted_proof_bundle",
)

REQUIRED_RECEIPTS_BEFORE_EXTERNAL_TEST = (
    "operator_approval_receipt",
    "provider_selected_receipt",
    "synthetic_or_redacted_bundle_receipt",
    "no_private_proof_receipt",
    "no_tool_authority_receipt",
    "verifier_pass_fail_receipt",
    "published_or_rejected_response_hash_receipt",
)

OPERATOR_DECISION_OPTIONS = (
    "approve_synthetic_external_llm_quality_test",
    "approve_manual_external_llm_test_with_synthetic_bundle",
    "request_more_detail",
    "reject_for_now",
)

VERIFIER_REQUIREMENTS = (
    "proof_to_response_verifier",
    "no_unsupported_paid_sent_submitted_executed_claims",
    "no_authority_grant",
    "no_protected_action_promise",
    "no_machine_contract_jargon",
    "concise_response",
    "allowed_controls_only",
)

AUTHORITY_BOUNDARY = {
    "invocation_allowed": False,
    "proof_bundle_allowed": False,
    "synthetic_bundle_allowed": False,
    "private_proof_allowed": False,
    "protected_actions_allowed": False,
    "authority_granted": False,
    "authority_grant_allowed": False,
    "external_provider_connect_allowed": False,
    "external_llm_allowed": False,
    "tool_authority": False,
    "tool_authority_allowed": False,
    "business_action_authority": False,
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
    "worker_spawn_allowed": False,
    "memory_promotion_allowed": False,
    "git_push_allowed": False,
    "merge_allowed": False,
}

IMPLEMENTATION_BOUNDARY = {
    "external_llm_invoked": False,
    "external_provider_connected": False,
    "provider_api_called": False,
    "prompt_sent": False,
    "proof_bundle_sent": False,
    "api_key_read": False,
    "secret_read": False,
    "worker_spawn_performed": False,
    "business_action_performed": False,
    "email_send_performed": False,
    "browser_opened": False,
    "gmail_opened": False,
    "coupa_opened": False,
    "ledger_mutation_performed": False,
    "workbook_mutation_performed": False,
    "pdf_export_performed": False,
    "paid_marking_performed": False,
    "submit_performed": False,
    "memory_promotion_performed": False,
    "git_push_performed": False,
    "merge_performed": False,
}

UNSAFE_TRUE_KEYS = (
    set(AUTHORITY_BOUNDARY)
    | set(IMPLEMENTATION_BOUNDARY)
    | set(model_catalog_inventory.UNSAFE_TRUE_KEYS)
    | set(redaction_policy.UNSAFE_TRUE_KEYS)
    | set(proof_to_response_runtime.UNSAFE_TRUE_KEYS)
    | {
        "approved",
        "operator_approved",
        "invocation_approved",
        "synthetic_external_test_approved",
        "manual_external_test_approved",
        "private_proof_external_allowed",
        "external_provider_used",
        "ready_for_live_invocation",
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
    return str(payload.get("readiness_status") or payload.get("status") or payload.get("contract_status") or "")


def _shadow_runtime_row(read_model_root: Path) -> dict[str, Any]:
    root = _rooted(read_model_root)
    status = _load_json(root / proof_to_response_runtime.STATUS_JSON_EXPORT_NAME)
    active = str(status.get("active_candidate_source") or "")
    ready = status.get("status") == proof_to_response_runtime.READY_STATUS and active == proof_to_response_runtime.CANDIDATE_SOURCE_SHADOW_PILOT
    return {
        "precondition_ref": "proof_to_response_shadow_pilot_runtime",
        "source_ref": f"generated/read_models/{proof_to_response_runtime.STATUS_JSON_EXPORT_NAME}",
        "observed_status": "PROOF_TO_RESPONSE_SHADOW_PILOT_RUNTIME_READY" if ready else "PROOF_TO_RESPONSE_SHADOW_PILOT_RUNTIME_NOT_READY",
        "accepted_statuses": ["PROOF_TO_RESPONSE_SHADOW_PILOT_RUNTIME_READY"],
        "observed_active_candidate_source": active,
        "accepted_active_candidate_source": proof_to_response_runtime.CANDIDATE_SOURCE_SHADOW_PILOT,
        "ready": ready,
    }


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
    rows.append(_shadow_runtime_row(root))
    return rows


def _external_catalog_candidates(read_model_root: Path) -> list[dict[str, Any]]:
    payload = _load_json(_rooted(read_model_root) / "model_catalog_inventory.json")
    rows = payload.get("model_candidates")
    output: list[dict[str, Any]] = []
    if not isinstance(rows, list):
        return output
    for row in rows:
        if not isinstance(row, Mapping) or row.get("candidate_class") != "external_provider_catalog":
            continue
        output.append(
            {
                "provider_ref": str(row.get("candidate_ref") or ""),
                "provider_or_runtime": str(row.get("provider_or_runtime") or ""),
                "provider_name": str(row.get("model_or_harness_name") or ""),
                "candidate_class": "external_provider_catalog",
                "invocation_allowed": False,
                "proof_bundle_allowed": False,
                "synthetic_bundle_allowed": False,
                "private_proof_allowed": False,
                "missing_receipts": list(REQUIRED_RECEIPTS_BEFORE_EXTERNAL_TEST) + [
                    "external_provider_exception_receipt",
                    "provider_privacy_policy_receipt",
                ],
                "privacy_risk": "External provider catalog only; private OpenClaw proof remains blocked.",
                "quality_test_value": "Useful for future non-private phrasing quality comparison after operator approval.",
                "authority_boundary": dict(AUTHORITY_BOUNDARY),
            }
        )
    return output


def candidate_provider_classes(read_model_root: Path = DEFAULT_READ_MODEL_ROOT) -> list[dict[str, Any]]:
    base = [
        {
            "provider_ref": "external_llm_blocked_by_default",
            "provider_or_runtime": "external_default_policy",
            "provider_name": "External LLM blocked by default",
            "candidate_class": "external_llm_blocked_by_default",
            "invocation_allowed": False,
            "proof_bundle_allowed": False,
            "synthetic_bundle_allowed": False,
            "private_proof_allowed": False,
            "missing_receipts": list(REQUIRED_RECEIPTS_BEFORE_EXTERNAL_TEST),
            "privacy_risk": "Default posture blocks external LLM use for private OpenClaw proof.",
            "quality_test_value": "Baseline policy class; no quality test until separate approval exists.",
            "authority_boundary": dict(AUTHORITY_BOUNDARY),
        },
        {
            "provider_ref": "manual_paste_test_with_synthetic_bundle",
            "provider_or_runtime": "manual_operator_mediated_external_surface",
            "provider_name": "Manual paste test with synthetic bundle",
            "candidate_class": "manual_paste_test",
            "invocation_allowed": False,
            "proof_bundle_allowed": False,
            "synthetic_bundle_allowed": False,
            "private_proof_allowed": False,
            "missing_receipts": [
                "operator_approval_receipt",
                "synthetic_bundle_receipt",
                "manual_copy_boundary_receipt",
                "no_private_proof_receipt",
                "verifier_pass_fail_receipt",
                "published_or_rejected_response_hash_receipt",
            ],
            "privacy_risk": "Lowest external test risk if the bundle is synthetic and copied manually after approval.",
            "quality_test_value": "Good first external quality comparison because it avoids private proof and API integration.",
            "authority_boundary": dict(AUTHORITY_BOUNDARY),
        },
        {
            "provider_ref": "approved_api_test_future_gated",
            "provider_or_runtime": "future_external_api",
            "provider_name": "Approved API test future-gated",
            "candidate_class": "approved_api_test_future_gated",
            "invocation_allowed": False,
            "proof_bundle_allowed": False,
            "synthetic_bundle_allowed": False,
            "private_proof_allowed": False,
            "missing_receipts": list(REQUIRED_RECEIPTS_BEFORE_EXTERNAL_TEST) + [
                "provider_selected_receipt",
                "api_invocation_boundary_receipt",
                "no_secret_leak_receipt",
            ],
            "privacy_risk": "Higher operational risk because API transport and provider policy must be receipted first.",
            "quality_test_value": "Useful only after manual synthetic test proves verifier compatibility.",
            "authority_boundary": dict(AUTHORITY_BOUNDARY),
        },
    ]
    return [base[0], *_external_catalog_candidates(read_model_root), *base[1:]]


def first_safe_pilot_scope() -> dict[str, Any]:
    return {
        "preferred_scope": "synthetic_finance_capital_hilton_payment_watch",
        "world_ref": "finance",
        "thread_ref": "capital_hilton",
        "synthetic_only": True,
        "synthetic_bundle_allowed_now": False,
        "private_proof_allowed": False,
        "synthetic_facts": list(SYNTHETIC_FACTS),
        "expected_external_lm_output": dict(EXPECTED_EXTERNAL_OUTPUT),
        "allowed_next_control": "Attach payment evidence",
        "business_execution_allowed": False,
    }


def build_read_model(*, read_model_root: Path = DEFAULT_READ_MODEL_ROOT, generated_at: str | None = None) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    preconditions = precondition_rows(read_model_root)
    candidates = candidate_provider_classes(read_model_root)
    all_ready = all(row.get("ready") is True for row in preconditions)
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "status": READY_STATUS if all_ready else NOT_READY_STATUS,
        "generated_at": generated_at,
        "purpose": "Plan a future external LLM proof-to-response quality test using synthetic or fully redacted proof bundles only.",
        "pilot_purpose": list(PILOT_PURPOSE),
        "approved_first_test_data": list(APPROVED_FIRST_TEST_DATA),
        "approved_first_test_data_policy": {
            "synthetic_bundle_may_be_proposed": True,
            "synthetic_bundle_approved_now": False,
            "fully_redacted_real_shaped_bundle_may_be_proposed": True,
            "private_proof_allowed": False,
            "operator_approval_required_before_any_external_test": True,
        },
        "explicitly_blocked_data": list(EXPLICITLY_BLOCKED_DATA),
        "candidate_external_provider_classes": candidates,
        "first_safe_pilot_scope": first_safe_pilot_scope(),
        "verifier_requirements": list(VERIFIER_REQUIREMENTS),
        "receipts_required_before_any_external_test": list(REQUIRED_RECEIPTS_BEFORE_EXTERNAL_TEST),
        "operator_decision_options": list(OPERATOR_DECISION_OPTIONS),
        "rules": [
            "This plan does not approve invocation.",
            "This plan does not call any provider.",
            "This plan does not allow private proof externally.",
            "External LLMs remain blocked for private OpenClaw proof.",
            "Manual copy/paste tests must use synthetic or redacted bundles only.",
        ],
        "preconditions": preconditions,
        "source_refs": [
            "generated/read_models/model_catalog_inventory.json",
            "generated/read_models/proof_to_response_lm_shadow_pilot.json",
            "generated/read_models/proof_to_response_runtime_status.json",
            "generated/read_models/proof_bundle_redaction_policy.json",
            "generated/read_models/proof_bundle_builder_redaction_status.json",
            "generated/read_models/context_freshness_decision_trace_gate.json",
            "generated/read_models/proof_bundle_freshness_trace_status.json",
            "generated/read_models/agent_response_voice_modes.json",
            "generated/read_models/goldilocks_gate_calibration.json",
        ],
        "source_content_hashes": {
            "preconditions": _content_hash(preconditions),
            "candidate_external_provider_classes": _content_hash(candidates),
            "first_safe_pilot_scope": _content_hash(first_safe_pilot_scope()),
        },
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "implementation_boundary": dict(IMPLEMENTATION_BOUNDARY),
        "machine_proof": {
            "planning_only": True,
            "private_proof_blocked": True,
            "synthetic_bundle_proposed_not_approved": True,
            "external_invocation_allowed_count": sum(1 for row in candidates if row.get("invocation_allowed") is True),
            "private_proof_allowed_count": sum(1 for row in candidates if row.get("private_proof_allowed") is True),
            "verifier_mandatory": True,
            "operator_approval_required": True,
            "unsafe_true_grants_absent": True,
            **IMPLEMENTATION_BOUNDARY,
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
    scope = read_model.get("first_safe_pilot_scope") if isinstance(read_model.get("first_safe_pilot_scope"), Mapping) else {}
    proof = read_model.get("machine_proof") if isinstance(read_model.get("machine_proof"), Mapping) else {}
    lines = [
        "# External LM Proof Response Pilot Plan",
        "",
        f"Status: {read_model.get('status')}",
        "",
        "This is planning only. It does not invoke an external model, call APIs, read secrets, browse, send prompts, or send proof bundles.",
        "",
        "## Purpose",
        "",
    ]
    for item in read_model.get("pilot_purpose") or []:
        lines.append(f"- {item}")
    lines.extend(["", "## First Safe Scope", ""])
    lines.append(f"- Scope: `{scope.get('preferred_scope')}`")
    lines.append(f"- Synthetic allowed now: `{str(scope.get('synthetic_bundle_allowed_now')).lower()}`")
    lines.append(f"- Private proof allowed: `{str(scope.get('private_proof_allowed')).lower()}`")
    lines.append(f"- Expected next step: {scope.get('allowed_next_control')}")
    lines.extend(["", "## Synthetic Facts", ""])
    for fact in scope.get("synthetic_facts") or []:
        lines.append(f"- {fact}")
    lines.extend(["", "## Blocked Data", ""])
    for item in read_model.get("explicitly_blocked_data") or []:
        lines.append(f"- `{item}`")
    lines.extend(["", "## Candidate External Provider Classes", ""])
    for row in read_model.get("candidate_external_provider_classes") or []:
        lines.append(
            f"- `{row.get('provider_ref')}`: invocation `{str(row.get('invocation_allowed')).lower()}`, "
            f"synthetic `{str(row.get('synthetic_bundle_allowed')).lower()}`, private proof `{str(row.get('private_proof_allowed')).lower()}`"
        )
    lines.extend(["", "## Verifier Requirements", ""])
    for item in read_model.get("verifier_requirements") or []:
        lines.append(f"- `{item}`")
    lines.extend(["", "## Operator Decision Options", ""])
    for item in read_model.get("operator_decision_options") or []:
        lines.append(f"- `{item}`")
    lines.extend(
        [
            "",
            "## Proof",
            "",
            f"- Private proof blocked: `{str(proof.get('private_proof_blocked')).lower()}`",
            f"- Verifier mandatory: `{str(proof.get('verifier_mandatory')).lower()}`",
            f"- Unsafe true grants absent: `{str(proof.get('unsafe_true_grants_absent')).lower()}`",
            "",
        ]
    )
    return "\n".join(lines)


def export_external_lm_proof_response_pilot_plan(
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
    parser = argparse.ArgumentParser(description="Publish External LM Proof Response Pilot Plan V0.")
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
    result = export_external_lm_proof_response_pilot_plan(
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
