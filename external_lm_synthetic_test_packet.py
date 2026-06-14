"""External LM synthetic test packet V0.

Builds a copy/paste-safe synthetic packet for manual proof-to-response quality
comparison. This module does not call APIs, browse, read secrets, send prompts,
invoke models, or mutate business systems.
"""

from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

import proof_to_response_schema_adapter as schema_adapter


ROOT = Path(__file__).resolve().parent
DEFAULT_READ_MODEL_ROOT = Path("generated/read_models")
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_BRIDGE_EXPORT_ROOT = Path("/mnt/e/openclaw/generated/read_models")
DEFAULT_WIKI_PATH = Path("generated/wiki/openclaw/External LM Synthetic Test Packet.md")

SCHEMA_VERSION = "external_lm_synthetic_test_packet_v0"
READ_MODEL_ID = "external_lm_synthetic_test_packet"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
READY_STATUS = "EXTERNAL_LM_SYNTHETIC_TEST_PACKET_READY"
NOT_READY_STATUS = "EXTERNAL_LM_SYNTHETIC_TEST_PACKET_NOT_READY"

STRICT_RESPONSE_FIELDS = schema_adapter.STRICT_DRAFT_FIELDS

PRECONDITIONS = {
    "external_lm_proof_response_pilot_plan": {
        "filename": "external_lm_proof_response_pilot_plan.json",
        "accepted_statuses": ("EXTERNAL_LM_PROOF_RESPONSE_PILOT_PLAN_READY",),
    },
    "proof_to_response_schema_adapter": {
        "filename": "proof_to_response_schema_adapter_status.json",
        "accepted_statuses": ("PROOF_TO_RESPONSE_SCHEMA_ADAPTER_READY",),
    },
    "agent_response_voice_modes": {
        "filename": "agent_response_voice_modes.json",
        "accepted_statuses": ("AGENT_RESPONSE_VOICE_MODES_READY",),
    },
    "proof_bundle_redaction_hardening": {
        "filename": "proof_bundle_redaction_policy.json",
        "accepted_statuses": ("PROOF_BUNDLE_REDACTION_HARDENING_READY",),
    },
}

AUTHORITY_BOUNDARY = {
    "external_api_allowed": False,
    "external_lm_allowed": False,
    "model_invocation_allowed": False,
    "local_model_runtime_allowed": False,
    "prompt_send_allowed": False,
    "proof_bundle_send_allowed": False,
    "secret_read_allowed": False,
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
    "workbook_mutation_performed": False,
    "pdf_export_performed": False,
    "paid_marking_performed": False,
    "worker_spawn_performed": False,
    "git_push_performed": False,
    "merge_performed": False,
}

UNSAFE_TRUE_KEYS = set(AUTHORITY_BOUNDARY) | set(PERFORMED_FLAGS) | {
    "authority_granted",
    "protected_actions_allowed",
    "submitted",
    "executed",
}

EXPECTED_VERIFIER_CHECKS = [
    "JSON only: parse strict object with no markdown or code fences.",
    "Required fields: headline, body, next_step, missing_input, can_do_now, cannot_do_yet, claimed_facts, requested_controls, uncertainty_notes.",
    "Claimed facts must come from the synthetic proof bundle.",
    "No paid claim unless proof says paid, and this packet says paid=false.",
    "No sent or submitted claim.",
    "No ledger mutation, ledger post, submit, send, browser, Coupa, or protected action promise.",
    "Next step must map to an allowed safe control.",
    "Response must be concise and human-readable.",
]

MANUAL_TEST_INSTRUCTIONS = [
    "Copy/paste the copy_paste_prompt into the external LM test surface manually.",
    "Do not paste private proof.",
    "Do not add real client files, screenshots, OCR text, amounts, account data, internal paths, or device details.",
    "Do not call API tools from this packet.",
    "Do not send any message or proof bundle from OpenClaw.",
    "Do not use secrets or API keys.",
    "Paste the returned JSON back into the local schema adapter/verifier harness for comparison.",
]

EXPECTED_RESPONSE = {
    "headline": "Payment evidence needed",
    "body_contains": [
        "payment evidence is missing",
        "processor says processing",
        "ledger stays untouched",
    ],
    "next_step": "Attach payment evidence.",
    "must_not_claim": [
        "paid",
        "sent",
        "submitted",
        "ledger updated",
        "ledger changed",
        "Coupa submit executed",
        "email sent",
    ],
    "style": "concise human response, not a proof wall",
}

CANONICAL_SYNTHETIC_FACTS = [
    {
        "fact_id": "payment_evidence_missing",
        "text": "Payment evidence is missing.",
        "source_ref": "synthetic_fact:payment_evidence_missing",
    },
    {
        "fact_id": "processor_processing",
        "text": "The synthetic payment processor status says processing.",
        "source_ref": "synthetic_fact:processor_processing",
    },
    {
        "fact_id": "ledger_untouched",
        "text": "The ledger is untouched.",
        "source_ref": "synthetic_fact:ledger_untouched",
    },
    {
        "fact_id": "paid_false",
        "text": "Paid is false.",
        "source_ref": "synthetic_fact:paid_false",
    },
    {
        "fact_id": "no_email_sent",
        "text": "No email was sent.",
        "source_ref": "synthetic_fact:no_email_sent",
    },
    {
        "fact_id": "no_coupa_submit",
        "text": "No Coupa submit occurred.",
        "source_ref": "synthetic_fact:no_coupa_submit",
    },
    {
        "fact_id": "no_ledger_mutation",
        "text": "No ledger mutation occurred.",
        "source_ref": "synthetic_fact:no_ledger_mutation",
    },
    {
        "fact_id": "no_paid_marking",
        "text": "No paid marking occurred.",
        "source_ref": "synthetic_fact:no_paid_marking",
    },
]

CANONICAL_SYNTHETIC_FACT_IDS = tuple(fact["fact_id"] for fact in CANONICAL_SYNTHETIC_FACTS)


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
    rows: list[dict[str, Any]] = []
    for ref, spec in PRECONDITIONS.items():
        filename = str(spec["filename"])
        path = root / filename
        payload = _load_json(path)
        observed = _observed_status(payload)
        accepted = [str(status) for status in spec["accepted_statuses"]]
        ready = observed in accepted or any(value in accepted for value in _strings(payload))
        rows.append(
            {
                "precondition_ref": ref,
                "source_ref": f"generated/read_models/{filename}",
                "observed_status": observed,
                "accepted_statuses": accepted,
                "ready": ready,
            }
        )
    return rows


def synthetic_proof_bundle() -> dict[str, Any]:
    return {
        "bundle_kind": "synthetic_redacted_test_only",
        "scenario_id": "synthetic_finance_capital_hilton_shaped_payment_watch",
        "scenario_shape": "capital_hilton_payment_watch",
        "world_ref": "finance",
        "client_ref": "synthetic_hotel_account",
        "privacy_class": "synthetic_only_no_private_proof",
        "real_client_data_present": False,
        "private_proof_present": False,
        "bank_or_account_details_present": False,
        "credentials_present": False,
        "raw_ocr_or_artifact_text_present": False,
        "internal_paths_present": False,
        "canonical_fact_ids": list(CANONICAL_SYNTHETIC_FACT_IDS),
        "proof_facts": [dict(fact) for fact in CANONICAL_SYNTHETIC_FACTS],
        "payment_evidence_status": "missing",
        "payment_processor_status": "processing",
        "ledger_untouched": True,
        "paid": False,
        "email_sent": False,
        "coupa_submit_occurred": False,
        "ledger_mutation_occurred": False,
        "paid_marking_occurred": False,
        "allowed_response_controls": [
            {
                "label": "Attach payment evidence",
                "controller_event_type": "attach_proof",
                "protected_actions_allowed": False,
            }
        ],
        "blocked_actions": [
            "mark_paid",
            "ledger_mutation",
            "ledger_post",
            "portal_submit",
            "coupa_submit",
            "email_send",
        ],
        "next_safe_action": "Attach payment evidence.",
    }


def json_only_response_schema() -> dict[str, Any]:
    schema = schema_adapter.strict_json_draft_schema()
    schema["title"] = "External LM synthetic proof-to-response draft"
    return schema


def copy_paste_prompt() -> str:
    packet = {
        "warning": "Do not paste private proof. Use this synthetic packet only.",
        "instructions": [
            "Return JSON only.",
            "No markdown.",
            "No prose outside JSON.",
            "No code fences.",
            "Use only the synthetic proof bundle below.",
            "Do not claim paid.",
            "Do not claim sent.",
            "Do not claim submitted.",
            "Do not promise send, submit, browser, Coupa, paid marking, or ledger action.",
            "Do not promise ledger updates or ledger posting.",
            "Keep the response concise and human.",
        ],
        "json_only_response_schema": json_only_response_schema(),
        "synthetic_proof_bundle": synthetic_proof_bundle(),
        "expected_next_step": "Attach payment evidence.",
    }
    return stable_json(packet)


def copy_paste_packet() -> dict[str, Any]:
    return {
        "packet_name": "external_lm_synthetic_test_packet_v0",
        "packet_mode": "manual_copy_paste_test_only",
        "copy_paste_safety": {
            "synthetic_proof_only": True,
            "private_proof_allowed": False,
            "real_client_data_allowed": False,
            "bank_or_account_details_allowed": False,
            "secret_or_api_key_allowed": False,
            "raw_ocr_or_artifact_text_allowed": False,
            "internal_paths_allowed": False,
        },
        "json_only_response_schema": json_only_response_schema(),
        "synthetic_proof_bundle": synthetic_proof_bundle(),
        "copy_paste_prompt": copy_paste_prompt(),
    }


def build_packet_read_model(
    *,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    preconditions = precondition_rows(read_model_root)
    preconditions_ready = all(row["ready"] for row in preconditions)
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "status": READY_STATUS if preconditions_ready else NOT_READY_STATUS,
        "generated_at": generated_at,
        "purpose": "Copy/paste-safe synthetic external LM test packet for proof-to-response quality comparison.",
        "copy_paste_packet": copy_paste_packet(),
        "expected_verifier_checks": list(EXPECTED_VERIFIER_CHECKS),
        "expected_response": dict(EXPECTED_RESPONSE),
        "manual_test_instructions": list(MANUAL_TEST_INSTRUCTIONS),
        "preconditions": preconditions,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "implementation_boundary": dict(PERFORMED_FLAGS),
    }
    unsafe = unsafe_true_grants(payload)
    payload["machine_proof"] = {
        "preconditions_ready": preconditions_ready,
        "synthetic_proof_only": True,
        "no_private_proof": True,
        "no_real_client_data": True,
        "no_internal_paths_in_copy_paste_packet": True,
        "no_model_or_api_invocation": True,
        "unsafe_true_grants": unsafe,
        "unsafe_true_grants_absent": not unsafe,
        **PERFORMED_FLAGS,
    }
    if unsafe:
        payload["status"] = NOT_READY_STATUS
    return payload


def build_wiki(packet_model: Mapping[str, Any]) -> str:
    lines = [
        "# External LM Synthetic Test Packet",
        "",
        f"Status: `{packet_model.get('status', NOT_READY_STATUS)}`",
        "",
        "This is a manual, synthetic-only proof-to-response test packet for comparing external LM draft quality.",
        "It does not call an external API, send a prompt, send proof, invoke local models, or touch business systems.",
        "",
        "## Warning",
        "",
        "Do not paste private proof. Do not add real client files, OCR text, account details, secrets, internal paths, or credentials.",
        "",
        "## Synthetic Scenario",
        "",
        "Finance / Capital Hilton-shaped payment watch:",
        "- Payment evidence missing.",
        "- Synthetic processor status says processing.",
        "- Ledger untouched.",
        "- Paid is false.",
        "- Next safe action: attach payment evidence.",
        "",
        "## Manual Test",
        "",
    ]
    for item in packet_model.get("manual_test_instructions", []):
        lines.append(f"- {item}")
    lines.extend(["", "## Expected Verifier Checks", ""])
    for item in packet_model.get("expected_verifier_checks", []):
        lines.append(f"- {item}")
    return "\n".join(lines) + "\n"


def export_packet(
    *,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
    export_root: Path = DEFAULT_EXPORT_ROOT,
    bridge_export_root: Path | None = DEFAULT_BRIDGE_EXPORT_ROOT,
    wiki_path: Path = DEFAULT_WIKI_PATH,
    generated_at: str | None = None,
) -> dict[str, str]:
    model = build_packet_read_model(read_model_root=read_model_root, generated_at=generated_at)
    export_root = _rooted(export_root)
    export_root.mkdir(parents=True, exist_ok=True)
    packet_path = export_root / JSON_EXPORT_NAME
    _write_json(packet_path, model)

    bridge_packet_path = ""
    if bridge_export_root is not None:
        bridge_root = _rooted(bridge_export_root)
        bridge_root.mkdir(parents=True, exist_ok=True)
        bridge_packet = bridge_root / JSON_EXPORT_NAME
        shutil.copy2(packet_path, bridge_packet)
        bridge_packet_path = bridge_packet.as_posix()

    wiki_path = _rooted(wiki_path)
    wiki_path.parent.mkdir(parents=True, exist_ok=True)
    wiki_path.write_text(build_wiki(model), encoding="utf-8")
    return {
        "status": str(model["status"]),
        "packet_path": packet_path.as_posix(),
        "bridge_packet_path": bridge_packet_path,
        "wiki_path": wiki_path.as_posix(),
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Export External LM Synthetic Test Packet V0.")
    parser.add_argument("--read-model-root", default=str(DEFAULT_READ_MODEL_ROOT))
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT))
    parser.add_argument("--bridge-export-root", default=str(DEFAULT_BRIDGE_EXPORT_ROOT))
    parser.add_argument("--wiki-path", default=str(DEFAULT_WIKI_PATH))
    parser.add_argument("--generated-at")
    parser.add_argument("--no-bridge", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    result = export_packet(
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
