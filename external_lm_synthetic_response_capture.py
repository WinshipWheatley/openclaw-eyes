"""Manual external LM synthetic response capture V0.

Local-only intake for a manually pasted response to the synthetic external LM
proof-to-response packet. This never invokes a model, sends proof, reads
secrets, or publishes business truth.
"""

from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

import external_lm_synthetic_test_packet as synthetic_packet
import proof_to_response_schema_adapter as schema_adapter
import proof_to_response_verifier as verifier


ROOT = Path(__file__).resolve().parent
DEFAULT_READ_MODEL_ROOT = Path("generated/read_models")
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_BRIDGE_EXPORT_ROOT = Path("/mnt/e/openclaw/generated/read_models")
DEFAULT_WIKI_PATH = Path("generated/wiki/openclaw/External LM Synthetic Response Capture.md")

SCHEMA_VERSION = "external_lm_synthetic_response_capture_v0"
CONTRACT_READ_MODEL_ID = "external_lm_synthetic_response_capture_contract"
JSON_EXPORT_NAME = f"{CONTRACT_READ_MODEL_ID}.json"
READY_STATUS = "EXTERNAL_LM_SYNTHETIC_RESPONSE_CAPTURE_READY"
NOT_READY_STATUS = "EXTERNAL_LM_SYNTHETIC_RESPONSE_CAPTURE_NOT_READY"
CAPTURE_STATUS_VERIFIER_PASS = "verifier_pass"
CAPTURE_STATUS_VERIFIER_FAIL = "verifier_fail"
BUSINESS_TRUTH_STATUS = "SYNTHETIC_ONLY_NOT_FINANCE_TRUTH"

PRECONDITIONS = {
    "external_lm_synthetic_test_packet": {
        "filename": "external_lm_synthetic_test_packet.json",
        "accepted_statuses": ("EXTERNAL_LM_SYNTHETIC_TEST_PACKET_READY",),
    },
    "proof_to_response_schema_adapter_status": {
        "filename": "proof_to_response_schema_adapter_status.json",
        "accepted_statuses": ("PROOF_TO_RESPONSE_SCHEMA_ADAPTER_READY",),
    },
    "proof_to_response_runtime_status": {
        "filename": "proof_to_response_runtime_status.json",
        "accepted_statuses": ("PROOF_TO_RESPONSE_RUNTIME_READY",),
    },
    "proof_to_response_verifier_optional": {
        "filename": "proof_to_response_verifier_status.json",
        "accepted_statuses": ("PROOF_TO_RESPONSE_VERIFIER_READY",),
        "optional_if_missing": True,
    },
}

AUTHORITY_BOUNDARY = {
    "external_api_allowed": False,
    "external_lm_allowed": False,
    "model_invocation_allowed": False,
    "local_model_runtime_allowed": False,
    "prompt_send_allowed": False,
    "proof_bundle_send_allowed": False,
    "private_proof_allowed": False,
    "secret_read_allowed": False,
    "business_action_allowed": False,
    "authority_grant_allowed": False,
    "protected_actions_allowed": False,
    "email_send_allowed": False,
    "gmail_allowed": False,
    "browser_access_allowed": False,
    "coupa_allowed": False,
    "portal_submit_allowed": False,
    "ledger_mutation_allowed": False,
    "ledger_posting_allowed": False,
    "paid_marking_allowed": False,
    "workbook_mutation_allowed": False,
    "pdf_export_allowed": False,
    "worker_spawn_allowed": False,
    "git_push_allowed": False,
    "merge_allowed": False,
    "sent": False,
    "paid": False,
}

PERFORMED_FLAGS = {
    "external_api_called": False,
    "external_llm_invoked": False,
    "local_model_runtime_connected": False,
    "prompt_sent": False,
    "proof_bundle_sent": False,
    "secret_read_performed": False,
    "business_action_performed": False,
    "email_send_performed": False,
    "gmail_access_performed": False,
    "browser_access_performed": False,
    "coupa_access_performed": False,
    "portal_submit_performed": False,
    "ledger_mutation_performed": False,
    "ledger_posting_performed": False,
    "paid_marking_performed": False,
    "workbook_mutation_performed": False,
    "pdf_export_performed": False,
    "worker_spawn_performed": False,
    "git_push_performed": False,
    "merge_performed": False,
}

UNSAFE_TRUE_KEYS = (
    set(AUTHORITY_BOUNDARY)
    | set(PERFORMED_FLAGS)
    | set(schema_adapter.UNSAFE_TRUE_KEYS)
    | set(verifier.UNSAFE_TRUE_KEYS)
    | {
        "authority_granted",
        "submitted",
        "executed",
        "published_as_real_business_truth",
        "finance_truth_mutation_performed",
        "private_proof_present",
        "real_client_data_present",
    }
)

VALID_SYNTHETIC_RESPONSE = {
    "headline": "Payment evidence needed",
    "body": "Payment evidence is missing. The processor says processing, and the ledger stays untouched.",
    "next_step": "Attach payment evidence.",
    "missing_input": ["payment_evidence"],
    "can_do_now": ["Hold payment watch", "Ask for payment proof"],
    "cannot_do_yet": ["paid marking", "ledger mutation", "submit", "send"],
    "claimed_facts": ["payment_evidence_missing", "processor_processing", "ledger_untouched", "paid_false"],
    "requested_controls": ["Attach payment evidence"],
    "uncertainty_notes": [],
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


def _strings(payload: Any) -> list[str]:
    if isinstance(payload, str):
        return [payload]
    if isinstance(payload, Mapping):
        out: list[str] = []
        for value in payload.values():
            out.extend(_strings(value))
        return out
    if isinstance(payload, Sequence) and not isinstance(payload, (bytes, bytearray)):
        out: list[str] = []
        for value in payload:
            out.extend(_strings(value))
        return out
    return []


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
    for key in ("status", "readiness_status", "contract_status"):
        value = payload.get(key)
        if isinstance(value, str) and value:
            return value
    for value in _strings(payload):
        if value.endswith("_READY"):
            return value
    return ""


def precondition_rows(read_model_root: Path = DEFAULT_READ_MODEL_ROOT) -> list[dict[str, Any]]:
    root = _rooted(read_model_root)
    rows = []
    for ref, spec in PRECONDITIONS.items():
        filename = str(spec["filename"])
        path = root / filename
        payload = _load_json(path)
        observed = _observed_status(payload)
        accepted = [str(status) for status in spec["accepted_statuses"]]
        exists = path.exists()
        optional_missing = bool(spec.get("optional_if_missing")) and not exists
        ready = optional_missing or observed in accepted or any(value in accepted for value in _strings(payload))
        rows.append(
            {
                "precondition_ref": ref,
                "source_ref": f"generated/read_models/{filename}",
                "observed_status": "OPTIONAL_NOT_PRESENT" if optional_missing else observed,
                "accepted_statuses": accepted,
                "optional_if_missing": bool(spec.get("optional_if_missing")),
                "exists": exists,
                "ready": ready,
            }
        )
    return rows


def synthetic_verifier_proof_bundle() -> dict[str, Any]:
    source_bundle = synthetic_packet.synthetic_proof_bundle()
    known_facts = []
    proof_refs = []
    for fact in source_bundle.get("proof_facts") or []:
        if not isinstance(fact, Mapping):
            continue
        proof_ref = str(fact.get("source_ref") or f"synthetic_fact:{fact.get('fact_id')}")
        proof_refs.append(proof_ref)
        known_facts.append(
            {
                "fact_id": str(fact.get("fact_id") or ""),
                "text": str(fact.get("text") or ""),
                "source_refs": [proof_ref],
            }
        )
    return {
        "proof_bundle_id": "proof_bundle:external_lm_synthetic_response_capture:payment_watch",
        "bundle_kind": "synthetic_redacted_test_only",
        "scenario_id": "finance_capital_hilton_payment_watch",
        "source_synthetic_scenario_id": str(source_bundle.get("scenario_id") or ""),
        "world_ref": "synthetic_finance",
        "thread_ref": "synthetic_capital_hilton_shape",
        "privacy_class": "synthetic_only_no_private_proof",
        "synthetic_only": True,
        "real_client_data_present": False,
        "private_proof_present": False,
        "bank_or_account_details_present": False,
        "credentials_present": False,
        "raw_ocr_or_artifact_text_present": False,
        "internal_paths_present": False,
        "response_speaker_ref": "chief",
        "response_voice_mode": "diagnostic",
        "known_facts": known_facts,
        "proof_refs": proof_refs,
        "unknowns": ["payment_evidence"],
        "blocked_actions": list(source_bundle.get("blocked_actions") or []),
        "allowed_response_controls": [
            {
                "label": "Attach payment evidence",
                "controller_event_type": "attach_proof",
                "authority_boundary": {"protected_actions_allowed": False},
            }
        ],
        "objective_ref": "synthetic_objective:capital_hilton_payment_watch",
        "operator_question": "What should happen next?",
        "selected_card_ref": "synthetic_card:capital_hilton_payment_watch",
        "receipt_refs": ["synthetic_receipt:payment_watch"],
        "read_model_refs": ["generated/read_models/external_lm_synthetic_test_packet.json"],
        "gate_refs": ["synthetic_gate:payment_evidence_required", "synthetic_gate:ledger_blocked"],
        "proof_meters": [
            {
                "proof_ref": "synthetic_fact:payment_evidence_missing",
                "confidence_class": "synthetic_only",
                "confidence_score": 1.0,
            }
        ],
        "excluded_context": [
            "private proof",
            "real client data",
            "credentials",
            "internal paths",
            "raw OCR or artifact bodies",
        ],
        "sensitive_detail_policy": "synthetic_summary_only",
        "next_safe_action": "Attach payment evidence.",
    }


def _capture_failure_reasons(adapter_result: Mapping[str, Any]) -> list[str]:
    reasons = [f"adapter:{error}" for error in adapter_result.get("adapter_errors") or []]
    reasons.extend(str(error) for error in adapter_result.get("verifier_failure_reasons") or [])
    return sorted(dict.fromkeys(reasons))


def capture_manual_synthetic_response(
    pasted_response_text: str,
    *,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    proof_bundle = synthetic_verifier_proof_bundle()
    adapter_result = schema_adapter.adapt_model_draft(
        pasted_response_text,
        proof_bundle=proof_bundle,
        read_model_root=read_model_root,
        generated_at=generated_at,
    )
    verifier_pass = bool(adapter_result.get("verifier_ready") is True)
    result: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "capture_status": CAPTURE_STATUS_VERIFIER_PASS if verifier_pass else CAPTURE_STATUS_VERIFIER_FAIL,
        "generated_at": generated_at,
        "input_mode": "manual_pasted_synthetic_response_text",
        "adapter_result": adapter_result,
        "adapted_candidate": adapter_result.get("adapted_candidate") or {},
        "verifier_pass": verifier_pass,
        "failure_reasons": [] if verifier_pass else _capture_failure_reasons(adapter_result),
        "synthetic_response_only": True,
        "business_truth_status": BUSINESS_TRUTH_STATUS,
        "published_as_real_business_truth": False,
        "finance_truth_mutation_performed": False,
        "private_proof_allowed": False,
        "private_proof_accepted": False,
        "real_client_data_allowed": False,
        "proof_bundle_ref": proof_bundle["proof_bundle_id"],
        "proof_bundle_policy": {
            "synthetic_only": True,
            "private_proof_allowed": False,
            "real_client_data_allowed": False,
            "no_private_proof_allowed": True,
            "never_publish_as_real_business_truth": True,
            "never_treat_synthetic_response_as_finance_truth": True,
        },
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "implementation_boundary": dict(PERFORMED_FLAGS),
        "machine_proof": {
            "manual_paste_only": True,
            "external_llm_invoked": False,
            "external_api_called": False,
            "local_model_runtime_connected": False,
            "prompt_sent": False,
            "proof_bundle_sent": False,
            "secret_read_performed": False,
            "business_action_performed": False,
            "synthetic_only_not_finance_truth": True,
            **PERFORMED_FLAGS,
        },
    }
    unsafe = unsafe_true_grants(result)
    result["machine_proof"]["unsafe_true_grants"] = unsafe
    result["machine_proof"]["unsafe_true_grants_absent"] = not unsafe
    if unsafe:
        result["capture_status"] = CAPTURE_STATUS_VERIFIER_FAIL
        result["verifier_pass"] = False
        result["failure_reasons"] = sorted(set(result["failure_reasons"] + [f"unsafe_true_grant:{item}" for item in unsafe]))
    return result


def build_contract_read_model(
    *,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    preconditions = precondition_rows(read_model_root)
    preconditions_ready = all(row["ready"] for row in preconditions)
    sample_capture = capture_manual_synthetic_response(
        stable_json(VALID_SYNTHETIC_RESPONSE),
        read_model_root=read_model_root,
        generated_at=generated_at,
    )
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": CONTRACT_READ_MODEL_ID,
        "status": READY_STATUS if preconditions_ready and sample_capture["verifier_pass"] else NOT_READY_STATUS,
        "generated_at": generated_at,
        "purpose": "Define local intake for manually pasted synthetic external LM responses and run the JSON adapter plus deterministic verifier.",
        "contract": {
            "input": "manual_pasted_synthetic_response_text",
            "adapter": "proof_to_response_schema_adapter.adapt_model_draft",
            "verifier": "proof_to_response_runtime.verify_candidate_response",
            "output": "verifier_pass_or_verifier_fail_receipt",
            "synthetic_packet_ref": "generated/read_models/external_lm_synthetic_test_packet.json",
        },
        "required_behavior": [
            "accept manual pasted synthetic response text",
            "parse JSON-only response through the schema adapter",
            "run deterministic proof-to-response verifier checks for truth, authority, and concision",
            "mark verifier_pass only when adapter and verifier both pass",
            "mark verifier_fail with reasons when parsing, schema, truth, authority, or style checks fail",
            "never publish as real business truth",
            "never treat synthetic response as Finance truth",
            "reject private proof by policy",
        ],
        "manual_capture_steps": [
            "Paste only the synthetic external LM response text into this local capture harness.",
            "Do not paste private proof, real client data, credentials, internal paths, OCR, or artifact bodies.",
            "Run capture_manual_synthetic_response or the focused tests to get a verifier receipt.",
            "Use verifier_pass/verifier_fail for quality comparison only.",
        ],
        "verifier_checks": [
            "strict JSON-only parse",
            "required draft schema fields",
            "claimed facts must exist in the synthetic proof bundle",
            "no paid, sent, submitted, ledger-updated, or executed claims",
            "no send, submit, browser, Coupa, ledger, paid marking, workbook, PDF, push, merge, or worker-spawn promises",
            "requested controls must be safe and allowed by the synthetic bundle",
            "response must be concise and human-readable",
            "machine-contract jargon is rejected",
        ],
        "rules": {
            "manual_paste_only": True,
            "no_private_proof_allowed": True,
            "never_publish_as_real_business_truth": True,
            "never_treat_synthetic_response_as_finance_truth": True,
            "no_external_provider_invocation": True,
            "no_prompt_or_proof_send": True,
        },
        "preconditions": preconditions,
        "synthetic_verifier_proof_bundle": synthetic_verifier_proof_bundle(),
        "sample_capture": sample_capture,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "implementation_boundary": dict(PERFORMED_FLAGS),
    }
    unsafe = unsafe_true_grants(payload)
    payload["machine_proof"] = {
        "preconditions_ready": preconditions_ready,
        "sample_capture_passed": sample_capture["verifier_pass"],
        "external_llm_invoked": False,
        "external_api_called": False,
        "local_model_runtime_connected": False,
        "prompt_sent": False,
        "proof_bundle_sent": False,
        "business_action_performed": False,
        "unsafe_true_grants": unsafe,
        "unsafe_true_grants_absent": not unsafe,
        **PERFORMED_FLAGS,
    }
    if unsafe:
        payload["status"] = NOT_READY_STATUS
    return payload


def build_wiki(contract_model: Mapping[str, Any]) -> str:
    lines = [
        "# External LM Synthetic Response Capture",
        "",
        f"Status: `{contract_model.get('status', NOT_READY_STATUS)}`",
        "",
        "This is a local-only intake path for manually pasted responses to the synthetic external LM test packet.",
        "It does not call an external provider, send prompts, send proof bundles, read secrets, or mutate business systems.",
        "",
        "## Manual Capture",
        "",
    ]
    for step in contract_model.get("manual_capture_steps", []):
        lines.append(f"- {step}")
    lines.extend(["", "## Verifier Checks", ""])
    for check in contract_model.get("verifier_checks", []):
        lines.append(f"- {check}")
    lines.extend(
        [
            "",
            "## Boundaries",
            "",
            "- Synthetic responses are never Finance truth.",
            "- Private proof is not allowed.",
            "- A passing verifier receipt is quality evidence for the synthetic test only.",
            "- Protected actions remain blocked.",
        ]
    )
    return "\n".join(lines) + "\n"


def export_response_capture_contract(
    *,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
    export_root: Path = DEFAULT_EXPORT_ROOT,
    bridge_export_root: Path | None = DEFAULT_BRIDGE_EXPORT_ROOT,
    wiki_path: Path = DEFAULT_WIKI_PATH,
    generated_at: str | None = None,
) -> dict[str, str]:
    model = build_contract_read_model(read_model_root=read_model_root, generated_at=generated_at)
    export_root = _rooted(export_root)
    export_root.mkdir(parents=True, exist_ok=True)
    contract_path = export_root / JSON_EXPORT_NAME
    _write_json(contract_path, model)

    bridge_contract_path = ""
    if bridge_export_root is not None:
        bridge_root = _rooted(bridge_export_root)
        bridge_root.mkdir(parents=True, exist_ok=True)
        bridge_path = bridge_root / JSON_EXPORT_NAME
        shutil.copy2(contract_path, bridge_path)
        bridge_contract_path = bridge_path.as_posix()

    wiki_path = _rooted(wiki_path)
    wiki_path.parent.mkdir(parents=True, exist_ok=True)
    wiki_path.write_text(build_wiki(model), encoding="utf-8")
    return {
        "status": str(model["status"]),
        "contract_path": contract_path.as_posix(),
        "bridge_contract_path": bridge_contract_path,
        "wiki_path": wiki_path.as_posix(),
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Export External LM Synthetic Response Capture V0.")
    parser.add_argument("--read-model-root", default=str(DEFAULT_READ_MODEL_ROOT))
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT))
    parser.add_argument("--bridge-export-root", default=str(DEFAULT_BRIDGE_EXPORT_ROOT))
    parser.add_argument("--wiki-path", default=str(DEFAULT_WIKI_PATH))
    parser.add_argument("--generated-at")
    parser.add_argument("--no-bridge", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    result = export_response_capture_contract(
        read_model_root=Path(args.read_model_root),
        export_root=Path(args.export_root),
        bridge_export_root=None if args.no_bridge else Path(args.bridge_export_root),
        wiki_path=Path(args.wiki_path),
        generated_at=args.generated_at,
    )
    print(stable_json(result), end="")
    return 0 if result["status"] == READY_STATUS else 1


if __name__ == "__main__":
    raise SystemExit(main())
