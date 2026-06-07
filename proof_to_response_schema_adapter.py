"""Proof-to-response schema adapter V0.

This module defines the JSON-only contract for future local or external LM draft
responses and adapts those drafts into the verifier-compatible shadow response
shape. It never invokes a model, sends a prompt, connects a runtime, or grants
business authority.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

import proof_to_response_runtime as runtime
import proof_to_response_verifier as verifier


ROOT = Path(__file__).resolve().parent
DEFAULT_READ_MODEL_ROOT = Path("generated/read_models")
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_BRIDGE_EXPORT_ROOT = Path("/mnt/e/openclaw/generated/read_models")
DEFAULT_WIKI_PATH = Path("generated/wiki/openclaw/Proof To Response Schema Adapter.md")

SCHEMA_VERSION = "proof_to_response_schema_adapter_v0"
CONTRACT_READ_MODEL_ID = "proof_to_response_schema_adapter_contract"
STATUS_READ_MODEL_ID = "proof_to_response_schema_adapter_status"
CONTRACT_JSON_EXPORT_NAME = f"{CONTRACT_READ_MODEL_ID}.json"
STATUS_JSON_EXPORT_NAME = f"{STATUS_READ_MODEL_ID}.json"
READY_STATUS = "PROOF_TO_RESPONSE_SCHEMA_ADAPTER_READY"
NOT_READY_STATUS = "PROOF_TO_RESPONSE_SCHEMA_ADAPTER_NOT_READY"

PARSE_STATUS_PARSED = "PARSED"
PARSE_STATUS_PARSE_ERROR = "PARSE_ERROR"
PARSE_STATUS_SCHEMA_ERROR = "SCHEMA_ERROR"

STRICT_DRAFT_FIELDS = (
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
STRING_FIELDS = ("headline", "body", "next_step")
LIST_FIELDS = (
    "missing_input",
    "can_do_now",
    "cannot_do_yet",
    "claimed_facts",
    "requested_controls",
    "uncertainty_notes",
)

PRECONDITIONS = {
    "local_lm_proof_response_pilot_postmortem": {
        "filename": "local_lm_proof_response_pilot_postmortem.json",
        "accepted_statuses": ("LOCAL_LM_PROOF_RESPONSE_PILOT_POSTMORTEM_READY",),
    },
    "proof_to_response_runtime": {
        "filename": "proof_to_response_runtime_status.json",
        "accepted_statuses": ("PROOF_TO_RESPONSE_RUNTIME_READY",),
    },
    "proof_to_response_verifier_optional": {
        "filename": "proof_to_response_verifier_status.json",
        "accepted_statuses": ("PROOF_TO_RESPONSE_VERIFIER_READY",),
        "optional_if_missing": True,
    },
    "proof_to_response_lm_shadow_harness": {
        "filename": "proof_to_response_lm_shadow_status.json",
        "accepted_statuses": ("PROOF_TO_RESPONSE_LM_SHADOW_HARNESS_READY",),
    },
    "proof_bundle_freshness_trace_integration": {
        "filename": "proof_bundle_freshness_trace_status.json",
        "accepted_statuses": ("PROOF_BUNDLE_FRESHNESS_TRACE_INTEGRATION_READY",),
    },
    "proof_bundle_builder_redaction_integration": {
        "filename": "proof_bundle_builder_redaction_status.json",
        "accepted_statuses": ("PROOF_BUNDLE_BUILDER_REDACTION_INTEGRATION_READY",),
    },
    "external_lm_proof_response_pilot_plan": {
        "filename": "external_lm_proof_response_pilot_plan.json",
        "accepted_statuses": ("EXTERNAL_LM_PROOF_RESPONSE_PILOT_PLAN_READY",),
    },
}

AUTHORITY_BOUNDARY = {
    "model_invocation_allowed": False,
    "live_lm_invocation_allowed": False,
    "external_lm_allowed": False,
    "external_provider_connect_allowed": False,
    "local_model_runtime_allowed": False,
    "worker_spawn_allowed": False,
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
    "git_push_allowed": False,
    "merge_allowed": False,
    "sent": False,
    "paid": False,
}

PERFORMED_FLAGS = {
    "model_invocation_performed": False,
    "external_llm_invoked": False,
    "local_model_runtime_connected": False,
    "external_provider_connected": False,
    "worker_spawn_performed": False,
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
    "git_push_performed": False,
    "merge_performed": False,
}

UNSAFE_TRUE_KEYS = set(AUTHORITY_BOUNDARY) | set(PERFORMED_FLAGS) | set(verifier.UNSAFE_TRUE_KEYS) | {
    "authority_granted",
    "submitted",
    "executed",
}

MODEL_INSTRUCTION_TEMPLATE = """Return JSON only.
No markdown.
No prose outside JSON.
No code fences.
Use only the provided proof bundle.
Do not claim paid/sent/submitted/executed unless proof says so.
Do not promise protected actions.
Do not ask for hidden context.
Keep response concise.
Return exactly these keys: headline, body, next_step, missing_input, can_do_now, cannot_do_yet, claimed_facts, requested_controls, uncertainty_notes.
"""

VALID_CAPITAL_HILTON_DRAFT = {
    "headline": "Payment evidence needed",
    "body": "Coupa is processing. I cannot mark this paid until payment evidence is attached. The ledger stays untouched.",
    "next_step": "Attach payment evidence.",
    "missing_input": ["payment_evidence"],
    "can_do_now": ["Hold payment watch", "Ask for proof"],
    "cannot_do_yet": ["paid marking", "ledger mutation", "Coupa/browser action"],
    "claimed_facts": ["payment_evidence_missing", "coupa_processing", "ledger_untouched"],
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


def _short_hash(payload: Any, *, length: int = 16) -> str:
    return hashlib.sha256(stable_json(payload).encode("utf-8")).hexdigest()[:length]


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


def model_instruction_template() -> str:
    return MODEL_INSTRUCTION_TEMPLATE


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
        exists = path.exists()
        optional_missing = bool(spec.get("optional_if_missing")) and not exists
        ready = optional_missing or observed in accepted or any(value in accepted for value in _strings(payload))
        rows.append(
            {
                "precondition_ref": ref,
                "source_ref": f"generated/read_models/{filename}",
                "exists": exists,
                "optional_if_missing": bool(spec.get("optional_if_missing")),
                "observed_status": observed or ("OPTIONAL_NOT_PRESENT" if optional_missing else ""),
                "accepted_statuses": accepted,
                "ready": ready,
            }
        )
    return rows


def _parse_json_only(raw_text: str) -> tuple[dict[str, Any] | None, list[str]]:
    text = str(raw_text or "").strip()
    if text.startswith("```") or text.endswith("```") or "```" in text:
        return None, ["markdown_wrapped_json_rejected"]
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        return None, [f"json_parse_error:{exc.msg}"]
    if not isinstance(payload, dict):
        return None, ["json_root_not_object"]
    return payload, []


def _normalize_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        text = value.strip()
        return [text] if text else []
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray)):
        return [str(item).strip() for item in value if str(item).strip()]
    return [str(value).strip()] if str(value).strip() else []


def _schema_errors(payload: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    for field in STRICT_DRAFT_FIELDS:
        if field not in payload:
            errors.append(f"missing_field:{field}")
    for field in STRING_FIELDS:
        if field in payload and not isinstance(payload.get(field), str):
            errors.append(f"field_not_string:{field}")
    for field in LIST_FIELDS:
        if field in payload and not (
            payload.get(field) is None
            or isinstance(payload.get(field), str)
            or isinstance(payload.get(field), list)
            or isinstance(payload.get(field), tuple)
        ):
            errors.append(f"field_not_list:{field}")
    for field in payload:
        if field not in STRICT_DRAFT_FIELDS:
            errors.append(f"unknown_field:{field}")
    return errors


def _normalize_draft(payload: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "headline": str(payload.get("headline") or "").strip(),
        "body": str(payload.get("body") or "").strip(),
        "next_step": str(payload.get("next_step") or "").strip(),
        "missing_input": _normalize_list(payload.get("missing_input")),
        "can_do_now": _normalize_list(payload.get("can_do_now")),
        "cannot_do_yet": _normalize_list(payload.get("cannot_do_yet")),
        "claimed_facts": _normalize_list(payload.get("claimed_facts")),
        "requested_controls": _normalize_list(payload.get("requested_controls")),
        "uncertainty_notes": _normalize_list(payload.get("uncertainty_notes")),
    }


def _adapted_candidate(
    normalized: Mapping[str, Any],
    proof_bundle: Mapping[str, Any],
    *,
    generated_at: str,
) -> dict[str, Any]:
    candidate = {
        "response_id": "proof_to_response_schema_adapter_candidate:" + _short_hash(
            {"draft": normalized, "proof_bundle_id": proof_bundle.get("proof_bundle_id"), "generated_at": generated_at}
        ),
        "proof_bundle_id": str(proof_bundle.get("proof_bundle_id") or ""),
        "speaker_ref": str(proof_bundle.get("response_speaker_ref") or "openclaw"),
        "draft_headline": str(normalized.get("headline") or ""),
        "draft_body": str(normalized.get("body") or ""),
        "draft_next_step": str(normalized.get("next_step") or ""),
        "claimed_facts": list(normalized.get("claimed_facts") or []),
        "implied_actions": [],
        "requested_controls": list(normalized.get("requested_controls") or []),
        "uncertainty_notes": list(normalized.get("uncertainty_notes") or []),
        "missing_input": list(normalized.get("missing_input") or []),
        "can_do_now": list(normalized.get("can_do_now") or []),
        "cannot_do_yet": list(normalized.get("cannot_do_yet") or []),
        "details_collapsed": True,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
    }
    return candidate


def adapt_model_draft(
    raw_model_output: str,
    *,
    proof_bundle: Mapping[str, Any] | None = None,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    bundle = dict(proof_bundle or {})
    parsed, parse_errors = _parse_json_only(raw_model_output)
    base: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "parse_status": PARSE_STATUS_PARSED,
        "adapter_errors": [],
        "adapted_candidate": {},
        "verifier_ready": False,
        "verifier_result": {},
        "verifier_failure_reasons": [],
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "machine_proof": {
            "json_only_adapter": True,
            "proof_only_prompt_contract": True,
            "truth_checks_not_loosened": True,
            **PERFORMED_FLAGS,
        },
    }
    if parse_errors:
        base["parse_status"] = PARSE_STATUS_PARSE_ERROR
        base["adapter_errors"] = parse_errors
        base["machine_proof"]["unsafe_true_grants"] = unsafe_true_grants(base)
        base["machine_proof"]["unsafe_true_grants_absent"] = not base["machine_proof"]["unsafe_true_grants"]
        return base
    assert parsed is not None
    schema_errors = _schema_errors(parsed)
    if schema_errors:
        base["parse_status"] = PARSE_STATUS_SCHEMA_ERROR
        base["adapter_errors"] = schema_errors
        base["machine_proof"]["unsafe_true_grants"] = unsafe_true_grants(base)
        base["machine_proof"]["unsafe_true_grants_absent"] = not base["machine_proof"]["unsafe_true_grants"]
        return base

    normalized = _normalize_draft(parsed)
    candidate = _adapted_candidate(normalized, bundle, generated_at=generated_at)
    verifier_result: dict[str, Any] = {}
    verifier_errors: list[str] = []
    if bundle:
        verifier_result = runtime.verify_candidate_response(candidate, bundle, read_model_root=read_model_root)
        verifier_errors = [str(error) for error in verifier_result.get("verification_errors") or []]
    else:
        verifier_errors = ["proof_bundle_missing"]
    base.update(
        {
            "parse_status": PARSE_STATUS_PARSED,
            "adapter_errors": [],
            "adapted_candidate": candidate,
            "verifier_result": verifier_result,
            "verifier_ready": bool(verifier_result.get("publishable") is True and not verifier_errors),
            "verifier_failure_reasons": verifier_errors,
        }
    )
    unsafe = unsafe_true_grants(base)
    base["machine_proof"]["unsafe_true_grants"] = unsafe
    base["machine_proof"]["unsafe_true_grants_absent"] = not unsafe
    if unsafe:
        base["verifier_ready"] = False
        base["verifier_failure_reasons"] = sorted(set(base["verifier_failure_reasons"] + [f"unsafe_true_grant:{item}" for item in unsafe]))
    return base


def strict_json_draft_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": list(STRICT_DRAFT_FIELDS),
        "properties": {
            "headline": {"type": "string", "description": "Short operator-facing headline."},
            "body": {"type": "string", "description": "Concise response body grounded only in proof."},
            "next_step": {"type": "string", "description": "One safe next step."},
            "missing_input": {"type": "array", "items": {"type": "string"}},
            "can_do_now": {"type": "array", "items": {"type": "string"}},
            "cannot_do_yet": {"type": "array", "items": {"type": "string"}},
            "claimed_facts": {"type": "array", "items": {"type": "string"}},
            "requested_controls": {"type": "array", "items": {"type": "string"}},
            "uncertainty_notes": {"type": "array", "items": {"type": "string"}},
        },
    }


def _valid_capital_hilton_example(generated_at: str) -> dict[str, Any]:
    bundle = runtime.build_or_load_proof_bundle("finance_capital_hilton_payment_watch")
    adapted = adapt_model_draft(stable_json(VALID_CAPITAL_HILTON_DRAFT), proof_bundle=bundle, generated_at=generated_at)
    return {
        "scenario_id": "finance_capital_hilton_payment_watch",
        "proof_summary": {
            "payment_evidence_missing": True,
            "coupa_processing": True,
            "ledger_untouched": True,
        },
        "draft": dict(VALID_CAPITAL_HILTON_DRAFT),
        "adapted_result": adapted,
    }


def build_contract_read_model(
    *,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    preconditions = precondition_rows(read_model_root)
    preconditions_ready = all(row["ready"] for row in preconditions)
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": CONTRACT_READ_MODEL_ID,
        "status": READY_STATUS if preconditions_ready else NOT_READY_STATUS,
        "generated_at": generated_at,
        "purpose": "Define JSON-only LM draft schema and adapt drafts into proof-to-response verifier shape without invoking any model.",
        "strict_json_draft_schema": strict_json_draft_schema(),
        "model_instruction_template": model_instruction_template(),
        "model_instruction_rules": [
            "return JSON only",
            "no markdown",
            "no prose outside JSON",
            "no code fences",
            "use only provided proof bundle",
            "do not claim paid/sent/submitted/executed unless proof says so",
            "do not promise protected actions",
            "do not ask for hidden context",
            "keep response concise",
        ],
        "adapter_behavior": [
            "parse strict JSON",
            "reject non-JSON",
            "reject markdown-wrapped JSON",
            "reject missing required fields",
            "normalize empty list fields",
            "map to proof_to_response_verifier shadow candidate fields",
            "preserve verifier failure reasons",
            "never loosen truth or authority checks",
        ],
        "verifier_candidate_mapping": {
            "headline": "draft_headline",
            "body": "draft_body",
            "next_step": "draft_next_step",
            "claimed_facts": "claimed_facts",
            "requested_controls": "requested_controls",
            "uncertainty_notes": "uncertainty_notes",
            "implied_actions": "always empty unless a future explicit schema version adds safe support",
        },
        "valid_examples": [_valid_capital_hilton_example(generated_at)],
        "preconditions": preconditions,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "implementation_boundary": dict(PERFORMED_FLAGS),
    }
    unsafe = unsafe_true_grants(payload)
    payload["machine_proof"] = {
        "preconditions_ready": preconditions_ready,
        "model_invocation_performed": False,
        "external_llm_invoked": False,
        "local_model_runtime_connected": False,
        "prompt_sent": False,
        "proof_bundle_sent": False,
        "truth_checks_not_loosened": True,
        "unsafe_true_grants": unsafe,
        "unsafe_true_grants_absent": not unsafe,
        **PERFORMED_FLAGS,
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
    sample = contract["valid_examples"][0]["adapted_result"]
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": STATUS_READ_MODEL_ID,
        "status": contract["status"],
        "generated_at": generated_at,
        "contract_ref": f"generated/read_models/{CONTRACT_JSON_EXPORT_NAME}",
        "adapter_ready": contract["status"] == READY_STATUS,
        "latest_sample_parse_status": sample.get("parse_status"),
        "latest_sample_verifier_ready": sample.get("verifier_ready"),
        "strict_schema_required_fields": list(STRICT_DRAFT_FIELDS),
        "json_only_prompt_contract_ready": True,
        "verifier_candidate_mapping_ready": True,
        "preconditions": contract["preconditions"],
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "implementation_boundary": dict(PERFORMED_FLAGS),
        "machine_proof": {
            "model_invocation_performed": False,
            "external_llm_invoked": False,
            "local_model_runtime_connected": False,
            "prompt_sent": False,
            "proof_bundle_sent": False,
            "business_action_performed": False,
        },
    }
    unsafe = unsafe_true_grants(payload)
    payload["machine_proof"]["unsafe_true_grants"] = unsafe
    payload["machine_proof"]["unsafe_true_grants_absent"] = not unsafe
    if unsafe:
        payload["status"] = NOT_READY_STATUS
        payload["adapter_ready"] = False
    return payload


def build_wiki(contract: Mapping[str, Any], status: Mapping[str, Any]) -> str:
    lines = [
        "# Proof To Response Schema Adapter",
        "",
        f"Status: `{status.get('status', NOT_READY_STATUS)}`",
        "",
        "This adapter defines the JSON-only response draft shape for future LM proof-to-response work.",
        "It does not invoke a model, send a prompt, connect a runtime, or grant protected authority.",
        "",
        "## Draft Fields",
        "",
    ]
    for field in STRICT_DRAFT_FIELDS:
        lines.append(f"- `{field}`")
    lines.extend([
        "",
        "## Prompt Rules",
        "",
    ])
    for rule in contract.get("model_instruction_rules", []):
        lines.append(f"- {rule}")
    lines.extend([
        "",
        "## Adapter Behavior",
        "",
    ])
    for rule in contract.get("adapter_behavior", []):
        lines.append(f"- {rule}")
    lines.extend([
        "",
        "## Safety Boundary",
        "",
        "- No local or external LM invocation.",
        "- No prompt or proof bundle is sent anywhere.",
        "- No email, browser, Gmail, Coupa, submit, ledger, workbook, PDF, paid marking, worker spawn, merge, or push.",
        "- Verifier failures are preserved; the adapter does not loosen truth checks.",
    ])
    return "\n".join(lines) + "\n"


def export_schema_adapter(
    *,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
    export_root: Path = DEFAULT_EXPORT_ROOT,
    bridge_export_root: Path | None = DEFAULT_BRIDGE_EXPORT_ROOT,
    wiki_path: Path = DEFAULT_WIKI_PATH,
    generated_at: str | None = None,
) -> dict[str, str]:
    generated_at = generated_at or utc_now()
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
        bridge_root = _rooted(bridge_export_root)
        bridge_root.mkdir(parents=True, exist_ok=True)
        bridge_contract = bridge_root / CONTRACT_JSON_EXPORT_NAME
        bridge_status = bridge_root / STATUS_JSON_EXPORT_NAME
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
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Export Proof To Response Schema Adapter V0 read models.")
    parser.add_argument("--read-model-root", default=str(DEFAULT_READ_MODEL_ROOT))
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT))
    parser.add_argument("--bridge-export-root", default=str(DEFAULT_BRIDGE_EXPORT_ROOT))
    parser.add_argument("--wiki-path", default=str(DEFAULT_WIKI_PATH))
    parser.add_argument("--generated-at")
    parser.add_argument("--no-bridge", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    result = export_schema_adapter(
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
