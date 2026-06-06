"""Proof-to-response LM shadow harness contract.

This harness prepares bounded proof bundles and fixture LM-shadow drafts, then
uses the deterministic verifier as the publish gate. It does not invoke any
external LM, local model runtime, worker, tool, or business executor.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import proof_bundle_builder as bundles
import proof_to_response_verifier as verifier


ROOT = Path(__file__).resolve().parent
DEFAULT_READ_MODEL_ROOT = Path("generated/read_models")
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_BRIDGE_EXPORT_ROOT = Path("/mnt/e/openclaw/generated/read_models")
DEFAULT_WIKI_PATH = Path("generated/wiki/openclaw/Proof To Response LM Shadow Harness.md")

SCHEMA_VERSION = "proof_to_response_lm_shadow_harness_v0"
CONTRACT_READ_MODEL_ID = "proof_to_response_lm_shadow_contract"
STATUS_READ_MODEL_ID = "proof_to_response_lm_shadow_status"
CONTRACT_JSON_EXPORT_NAME = f"{CONTRACT_READ_MODEL_ID}.json"
STATUS_JSON_EXPORT_NAME = f"{STATUS_READ_MODEL_ID}.json"
READY_STATUS = "PROOF_TO_RESPONSE_LM_SHADOW_HARNESS_READY"
NOT_READY_STATUS = "PROOF_TO_RESPONSE_LM_SHADOW_HARNESS_NOT_READY"

SUPPORTED_SCENARIOS = (
    "finance_capital_hilton_payment_watch",
    "finance_live_arts_payment_evidence",
    "business_development_capital_hilton_followup",
    "build_review_packet",
    "unknown_context",
    "protected_coupa_ledger_email_request",
)

PRECONDITIONS = {
    "proof_to_response_tdd_spec": {
        "filename": "proof_to_response_tdd_spec.json",
        "accepted_statuses": ["PROOF_TO_RESPONSE_TDD_SPEC_READY"],
    },
    "dynamic_card_packet_v1": {
        "filename": "dynamic_card_packet_latest.json",
        "accepted_statuses": ["DYNAMIC_CARD_PACKET_V1_READY", "DYNAMIC_CARD_PACKET_READY"],
    },
    "universal_receipt_envelope": {
        "filename": "universal_receipt_envelope_status.json",
        "accepted_statuses": ["UNIVERSAL_RECEIPT_ENVELOPE_READY"],
    },
    "proof_meter_normalization": {
        "filename": "proof_meter_normalization.json",
        "accepted_statuses": ["PROOF_METER_NORMALIZATION_READY"],
    },
    "objective_advancement_controller_route": {
        "filename": "objective_advancement_protocol.json",
        "accepted_statuses": ["OBJECTIVE_ADVANCEMENT_CONTROLLER_ROUTE_READY", "OBJECTIVE_ADVANCEMENT_PROTOCOL_READY"],
    },
    "operator_controller_protocol": {
        "filename": "operator_controller_protocol.json",
        "accepted_statuses": ["OPERATOR_CONTROLLER_PROTOCOL_READY"],
    },
    "harness_provider_selection": {
        "filename": "harness_provider_selection_registry.json",
        "accepted_statuses": ["HARNESS_PROVIDER_SELECTION_READY"],
    },
}

DOCTRINE = (
    "The deterministic proof-to-response spec is the test oracle, not the final user experience.",
    "The intended final response is agentic LM text grounded in proof.",
    "The LM may phrase, prioritize, and explain.",
    "The LM may not create truth, authority, or execution.",
    "The verifier decides whether the LM response can publish.",
)

AUTHORITY_BOUNDARY = {
    "model_invocation_allowed": False,
    "external_provider_connect_allowed": False,
    "provider_key_material_access_allowed": False,
    "local_model_runtime_allowed": False,
    "worker_spawn_allowed": False,
    "worker_execution_allowed": False,
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
    "authority_grant_allowed": False,
    "git_push_allowed": False,
    "merge_allowed": False,
    "paid": False,
    "sent": False,
}

UNSAFE_TRUE_KEYS = set(AUTHORITY_BOUNDARY) | {
    "model_invoked",
    "external_provider_connected",
    "live_lm_invoked",
    "local_model_runtime_connected",
    "worker_spawn_performed",
    "worker_execution_performed",
    "business_action_performed",
    "email_send_performed",
    "coupa_submit_performed",
    "ledger_mutation_performed",
    "paid_marking_performed",
    "workbook_mutation_performed",
    "pdf_export_performed",
    "git_push_performed",
    "merge_performed",
    "incoming_authority_granted_accepted",
}


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _rooted(path: Path) -> Path:
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


def _observed_status(payload: Mapping[str, Any]) -> str:
    return str(payload.get("status") or payload.get("contract_status") or payload.get("readiness_status") or "")


def _preconditions(read_model_root: Path) -> list[dict[str, Any]]:
    root = _rooted(read_model_root)
    rows: list[dict[str, Any]] = []
    for ref, spec in PRECONDITIONS.items():
        filename = str(spec["filename"])
        payload = _load_json(root / filename)
        observed = _observed_status(payload)
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


def build_lm_shadow_response_for_bundle(proof_bundle: Mapping[str, Any]) -> dict[str, Any]:
    scenario_id = str(proof_bundle.get("scenario_id") or "")
    response_id = f"lm_shadow_response:{scenario_id}"
    common = {
        "response_id": response_id,
        "proof_bundle_id": str(proof_bundle.get("proof_bundle_id") or ""),
        "speaker_ref": str(proof_bundle.get("response_speaker_ref") or "openclaw"),
        "implied_actions": [],
        "uncertainty_notes": [],
    }
    if scenario_id == "finance_capital_hilton_payment_watch":
        return {
            **common,
            "draft_headline": "Payment evidence is missing",
            "draft_body": "Payment evidence is still missing. Coupa is processing, and the ledger stays untouched until payment is confirmed.",
            "draft_next_step": "Attach proof",
            "claimed_facts": ["payment_evidence_missing", "coupa_processing", "ledger_untouched"],
            "requested_controls": ["Attach proof"],
        }
    if scenario_id == "finance_live_arts_payment_evidence":
        return {
            **common,
            "draft_headline": "Evidence recorded",
            "draft_body": "This evidence is recorded as payment-processing evidence. It does not mark the invoice paid.",
            "draft_next_step": "Verify arrival or attach stronger proof",
            "claimed_facts": ["candidate_evidence_recorded", "not_paid_truth"],
            "requested_controls": ["Verify arrival"],
        }
    if scenario_id == "business_development_capital_hilton_followup":
        return {
            **common,
            "draft_headline": "Follow-up can be staged",
            "draft_body": "I can stage a follow-up draft. I will not send it.",
            "draft_next_step": "Stage follow-up",
            "claimed_facts": ["followup_stageable", "no_email_send"],
            "requested_controls": ["Stage follow-up"],
        }
    if scenario_id == "build_review_packet":
        return {
            **common,
            "draft_headline": "Review packet is informational",
            "draft_body": "This review packet is closed as informational. No merge and no push were performed.",
            "draft_next_step": "Review packet",
            "claimed_facts": ["review_packet_informational", "no_merge_or_push"],
            "requested_controls": ["Review packet"],
        }
    if scenario_id == "unknown_context":
        return {
            **common,
            "draft_headline": "Needs lane context",
            "draft_body": "Which world and thread should I use for this?",
            "draft_next_step": "Pick the world and thread",
            "claimed_facts": ["lane_context_missing"],
            "requested_controls": ["Choose lane"],
            "uncertainty_notes": ["world_ref and thread_ref are missing"],
        }
    if scenario_id == "protected_coupa_ledger_email_request":
        return {
            **common,
            "draft_headline": "Blocked until proof and approval",
            "draft_body": "Protected action is blocked until proof and approval. No execution will happen.",
            "draft_next_step": "Prepare approval",
            "claimed_facts": ["protected_action_blocked", "proof_and_approval_required", "no_execution"],
            "requested_controls": ["Prepare approval"],
        }
    raise ValueError(f"unknown_scenario:{scenario_id}")


def build_shadow_runs(*, read_model_root: Path = DEFAULT_READ_MODEL_ROOT) -> list[dict[str, Any]]:
    runs: list[dict[str, Any]] = []
    for scenario_id in SUPPORTED_SCENARIOS:
        proof_bundle = bundles.build_proof_bundle(scenario_id, read_model_root=read_model_root)
        lm_shadow_response = build_lm_shadow_response_for_bundle(proof_bundle)
        verifier_result = verifier.verify_lm_shadow_response(lm_shadow_response, proof_bundle, read_model_root=read_model_root)
        runs.append(
            {
                "scenario_id": scenario_id,
                "proof_bundle": proof_bundle,
                "lm_shadow_response": lm_shadow_response,
                "verifier_result": verifier_result,
            }
        )
    return runs


def build_contract_read_model(
    *,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    preconditions = _preconditions(read_model_root)
    preconditions_ready = all(row["ready"] for row in preconditions)
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": CONTRACT_READ_MODEL_ID,
        "status": READY_STATUS if preconditions_ready else NOT_READY_STATUS,
        "generated_at": generated_at,
        "doctrine": list(DOCTRINE),
        "supported_scenarios": list(SUPPORTED_SCENARIOS),
        "proof_bundle_schema": {
            "required_fields": list(bundles.REQUIRED_BUNDLE_FIELDS),
            "purpose": "bounded redacted input packet for a future responding LM",
        },
        "lm_shadow_response_schema": {
            "required_fields": list(verifier.REQUIRED_SHADOW_RESPONSE_FIELDS),
            "purpose": "draft response the future LM would produce from the bundle",
        },
        "deterministic_verifier_checks": [
            "every factual claim maps to proof/ref/receipt/source",
            "no unsupported paid/sent/submitted/approved/executed claims",
            "no invented authority",
            "no protected-action promise",
            "no machine-contract jargon in primary response",
            "response is concise",
            "next step is allowed",
            "details remain collapsed",
            "controls map to operator_action_payloads/controller events",
        ],
        "contract": {
            "lm_response_is_not_truth": True,
            "verifier_decides_publishability": True,
            "failed_verification_returns_rewrite_or_safe_fallback": True,
            "lm_never_receives_verification_material": True,
            "lm_sees_only_allowed_proof_bundle_fields": True,
            "external_providers_remain_blocked_without_harness_selection": True,
            "local_model_runtime_future_gated": True,
        },
        "preconditions": preconditions,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
    }
    unsafe = unsafe_true_grants(payload)
    payload["machine_proof"] = {
        "preconditions_ready": preconditions_ready,
        "unsafe_true_grants": unsafe,
        "unsafe_true_grants_absent": not unsafe,
        "business_action_performed": False,
        "email_send_performed": False,
        "coupa_submit_performed": False,
        "ledger_mutation_performed": False,
        "paid_marking_performed": False,
        "worker_spawn_performed": False,
        "live_lm_invoked": False,
        "local_model_runtime_connected": False,
    }
    if unsafe:
        payload["status"] = NOT_READY_STATUS
    return payload


def build_status_read_model(
    *,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    contract = build_contract_read_model(read_model_root=read_model_root, generated_at=generated_at)
    shadow_runs = build_shadow_runs(read_model_root=read_model_root)
    all_verified = all(run["verifier_result"]["publishable"] is True for run in shadow_runs)
    verifier_errors = [
        {"scenario_id": run["scenario_id"], "errors": run["verifier_result"]["verification_errors"]}
        for run in shadow_runs
        if run["verifier_result"]["verification_errors"]
    ]
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": STATUS_READ_MODEL_ID,
        "status": READY_STATUS if contract["status"] == READY_STATUS and all_verified else NOT_READY_STATUS,
        "generated_at": generated_at,
        "contract_ref": "generated/read_models/proof_to_response_lm_shadow_contract.json",
        "source_refs": {
            "proof_to_response_tdd_spec": "generated/read_models/proof_to_response_tdd_spec.json",
            "dynamic_card_packet_v1": "generated/read_models/dynamic_card_packet_latest.json",
            "universal_receipts": "generated/read_models/universal_receipt_envelope_status.json",
            "proof_meters": "generated/read_models/proof_meter_normalization.json",
            "harness_provider_selection": "generated/read_models/harness_provider_selection_registry.json",
        },
        "source_content_hashes": {
            "contract": _content_hash(contract),
            "shadow_runs": _content_hash(shadow_runs),
        },
        "shadow_runs": shadow_runs,
        "shadow_run_count": len(shadow_runs),
        "implementation_boundary": {
            "live_lm_invoked": False,
            "local_model_runtime_connected": False,
            "worker_spawn_performed": False,
            "email_send_performed": False,
            "coupa_submit_performed": False,
            "ledger_mutation_performed": False,
            "workbook_mutation_performed": False,
            "pdf_export_performed": False,
            "paid_marking_performed": False,
            "business_action_performed": False,
        },
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "machine_proof": {
            "contract_ready": contract["status"] == READY_STATUS,
            "all_shadow_drafts_verified": all_verified,
            "verifier_errors": verifier_errors,
            "shadow_run_count_matches_supported_scenarios": len(shadow_runs) == len(SUPPORTED_SCENARIOS),
            "business_action_performed": False,
            "email_send_performed": False,
            "coupa_submit_performed": False,
            "ledger_mutation_performed": False,
            "paid_marking_performed": False,
            "worker_spawn_performed": False,
            "live_lm_invoked": False,
            "local_model_runtime_connected": False,
        },
    }
    unsafe = unsafe_true_grants(payload)
    payload["machine_proof"]["unsafe_true_grants"] = unsafe
    payload["machine_proof"]["unsafe_true_grants_absent"] = not unsafe
    if unsafe:
        payload["status"] = NOT_READY_STATUS
    return payload


def build_wiki(contract: Mapping[str, Any], status: Mapping[str, Any]) -> str:
    lines = [
        "# Proof To Response LM Shadow Harness",
        "",
        f"Status: {status.get('status')}",
        "",
        "This contract lets a future LM phrase concise agent responses from a bounded proof bundle while deterministic verification enforces truth, brevity, and authority boundaries.",
        "",
        "## Doctrine",
        "",
    ]
    for rule in contract.get("doctrine") or []:
        lines.append(f"- {rule}")
    lines.extend(
        [
            "",
            "## Bundle",
            "",
            "The proof bundle is redacted and bounded. It includes refs, known facts, unknowns, blocked actions, proof meters, and allowed response controls. It excludes sensitive bodies and verification material.",
            "",
            "## Verifier",
            "",
        ]
    )
    for check in contract.get("deterministic_verifier_checks") or []:
        lines.append(f"- {check}")
    lines.extend(["", "## Shadow Scenarios", ""])
    for run in status.get("shadow_runs") or []:
        response = run.get("lm_shadow_response") if isinstance(run.get("lm_shadow_response"), Mapping) else {}
        result = run.get("verifier_result") if isinstance(run.get("verifier_result"), Mapping) else {}
        lines.append(
            f"- `{run.get('scenario_id')}`: {response.get('draft_headline')} -> `{result.get('status')}`"
        )
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            "- No live LM integration.",
            "- No local model runtime connection.",
            "- No worker spawn.",
            "- No email, Gmail, browser, Coupa, ledger, workbook, PDF, paid marking, submit, merge, push, or business execution.",
            "",
            "## Proof",
            "",
            f"- Shadow run count: `{status.get('shadow_run_count')}`",
            f"- All shadow drafts verified: `{str((status.get('machine_proof') or {}).get('all_shadow_drafts_verified')).lower()}`",
            f"- Unsafe true grants absent: `{str((status.get('machine_proof') or {}).get('unsafe_true_grants_absent')).lower()}`",
            "",
        ]
    )
    return "\n".join(lines)


def export_proof_to_response_lm_shadow_harness(
    *,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
    export_root: Path = DEFAULT_EXPORT_ROOT,
    bridge_export_root: Path | None = DEFAULT_BRIDGE_EXPORT_ROOT,
    wiki_path: Path = DEFAULT_WIKI_PATH,
    generated_at: str | None = None,
) -> dict[str, str]:
    contract = build_contract_read_model(read_model_root=read_model_root, generated_at=generated_at)
    status = build_status_read_model(read_model_root=read_model_root, generated_at=generated_at)
    export_root = _rooted(export_root)
    export_root.mkdir(parents=True, exist_ok=True)
    contract_path = export_root / CONTRACT_JSON_EXPORT_NAME
    status_path = export_root / STATUS_JSON_EXPORT_NAME
    _write_json(contract_path, contract)
    _write_json(status_path, status)

    bridge_contract_path = ""
    bridge_status_path = ""
    if bridge_export_root is not None:
        bridge_export_root.mkdir(parents=True, exist_ok=True)
        bridge_contract = bridge_export_root / CONTRACT_JSON_EXPORT_NAME
        bridge_status = bridge_export_root / STATUS_JSON_EXPORT_NAME
        shutil.copy2(contract_path, bridge_contract)
        shutil.copy2(status_path, bridge_status)
        bridge_contract_path = bridge_contract.as_posix()
        bridge_status_path = bridge_status.as_posix()

    wiki_path = _rooted(wiki_path)
    wiki_path.parent.mkdir(parents=True, exist_ok=True)
    wiki_path.write_text(build_wiki(contract, status), encoding="utf-8")
    return {
        "status": str(status["status"]),
        "contract_path": contract_path.as_posix(),
        "status_path": status_path.as_posix(),
        "bridge_contract_path": bridge_contract_path,
        "bridge_status_path": bridge_status_path,
        "wiki_path": wiki_path.as_posix(),
        "shadow_run_count": str(status["shadow_run_count"]),
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Publish Proof-to-Response LM Shadow Harness V0.")
    parser.add_argument("--read-model-root", default=str(DEFAULT_READ_MODEL_ROOT))
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT))
    parser.add_argument("--bridge-export-root", default=str(DEFAULT_BRIDGE_EXPORT_ROOT))
    parser.add_argument("--wiki-path", default=str(DEFAULT_WIKI_PATH))
    parser.add_argument("--generated-at")
    parser.add_argument("--no-bridge", action="store_true")
    parser.add_argument("--format", choices=("summary", "json"), default="summary")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    result = export_proof_to_response_lm_shadow_harness(
        read_model_root=Path(args.read_model_root),
        export_root=Path(args.export_root),
        bridge_export_root=None if args.no_bridge else Path(args.bridge_export_root),
        wiki_path=Path(args.wiki_path),
        generated_at=args.generated_at,
    )
    if args.format == "json":
        print(stable_json(result), end="")
    else:
        print(f"{result['status']}: {result['status_path']}")
    return 0 if result["status"] == READY_STATUS else 1


if __name__ == "__main__":
    raise SystemExit(main())
