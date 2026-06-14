"""Local LM proof-to-response invocation boundary packet V0.

Review/planning artifact for the first one-time local LM proof-to-response
pilot. This module does not invoke a model, contact Ollama, send prompts or
proof bundles, start/stop services, spawn workers, open browser/Gmail/Coupa,
mutate ledgers/workbooks, export PDFs, mark paid, submit, push, or grant
authority.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import local_model_list_inventory
import local_model_selection_for_proof_response
import proof_to_response_runtime


ROOT = Path(__file__).resolve().parent
DEFAULT_READ_MODEL_ROOT = Path("generated/read_models")
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_BRIDGE_ROOT = Path("/mnt/e/openclaw/generated/read_models")
DEFAULT_WIKI_PATH = Path("generated/wiki/openclaw/Local LM Proof Response Invocation Boundary Packet.md")

SCHEMA_VERSION = "local_lm_proof_response_invocation_boundary_packet_v0"
READ_MODEL_ID = "local_lm_proof_response_invocation_boundary_packet"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
READY_STATUS = "LOCAL_LM_PROOF_RESPONSE_INVOCATION_BOUNDARY_PACKET_READY"
NOT_READY_STATUS = "LOCAL_LM_PROOF_RESPONSE_INVOCATION_BOUNDARY_PACKET_NOT_READY"
PACKET_STATUS = "pending_operator_review"

SELECTED_RUNTIME_REF = "ollama"
SELECTED_MODEL_REF = "local_model:ollama:qwen3_8b-q4_k_m"
SELECTED_MODEL_NAME = "qwen3:8b-q4_K_M"
PILOT_LANE = "finance/capital_hilton"
PILOT_WORLD_REF = "finance"
PILOT_THREAD_REF = "capital_hilton"
PILOT_QUESTION = "What should I do here?"
CANDIDATE_SOURCE_MODE = "future_live_local_lm_pending_approval"

PRECONDITIONS = {
    "local_model_selection_for_proof_response": {
        "filename": "local_model_selection_for_proof_response.json",
        "accepted_statuses": ("LOCAL_MODEL_SELECTION_FOR_PROOF_RESPONSE_READY",),
    },
    "local_model_list_inventory": {
        "filename": "local_model_list_inventory.json",
        "accepted_statuses": ("LOCAL_MODEL_LIST_INVENTORY_READY",),
    },
    "local_lm_proof_response_preflight_receipts": {
        "filename": "local_lm_proof_response_preflight_receipts.json",
        "accepted_statuses": ("LOCAL_LM_PROOF_RESPONSE_PREFLIGHT_RECEIPTS_READY",),
    },
    "local_lm_proof_response_pilot_plan": {
        "filename": "local_lm_proof_to_response_pilot_plan.json",
        "accepted_statuses": ("LOCAL_LM_PROOF_RESPONSE_PILOT_PLAN_READY",),
    },
    "proof_bundle_freshness_trace_integration": {
        "filename": "proof_bundle_freshness_trace_status.json",
        "accepted_statuses": ("PROOF_BUNDLE_FRESHNESS_TRACE_INTEGRATION_READY",),
    },
    "proof_bundle_builder_redaction_integration": {
        "filename": "proof_bundle_builder_redaction_status.json",
        "accepted_statuses": ("PROOF_BUNDLE_BUILDER_REDACTION_INTEGRATION_READY",),
    },
    "proof_bundle_redaction_hardening": {
        "filename": "proof_bundle_redaction_policy.json",
        "accepted_statuses": ("PROOF_BUNDLE_REDACTION_HARDENING_READY",),
    },
    "proof_to_response_runtime": {
        "filename": proof_to_response_runtime.STATUS_JSON_EXPORT_NAME,
        "accepted_statuses": (proof_to_response_runtime.READY_STATUS,),
    },
    "context_freshness_decision_trace_gate": {
        "filename": "context_freshness_decision_trace_gate.json",
        "accepted_statuses": ("CONTEXT_FRESHNESS_DECISION_TRACE_GATE_READY",),
    },
}

ALLOWED_INPUTS = (
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
    "freshness_state",
    "confidence_class",
    "decision_trace_summary",
)

FORBIDDEN_INPUTS = (
    "raw_bank_or_account_details",
    "credentials_or_tokens",
    "operator_device_session_verification_secrets",
    "raw_prompt_dumps",
    "raw_artifact_or_ocr_text",
    "full_workbook_contents",
    "source_workbook_bodies",
    "raw_email_bodies",
    "raw_ledger_rows",
    "hidden_machine_contracts",
    "incoming_authority_granted_fields",
)

FORBIDDEN_ACTIONS = (
    "tool_use",
    "browser_access",
    "gmail_access",
    "coupa_access",
    "ledger_mutation",
    "workbook_mutation",
    "pdf_export",
    "paid_marking",
    "submit",
    "git_push_or_merge",
    "worker_spawn",
    "memory_promotion",
    "external_provider_call",
    "raw_financial_or_private_proof_exposure",
    "operator_device_session_secret_exposure",
)

STOP_CONDITIONS = (
    "proof_bundle_contains_forbidden_field",
    "context_freshness_is_stale_superseded_or_unknown",
    "runtime_or_model_mismatch",
    "model_asks_for_hidden_context",
    "model_claims_paid_sent_submitted_or_executed",
    "model_promises_protected_action",
    "model_includes_machine_contract_jargon",
    "verifier_fails",
    "external_provider_path_appears",
    "tool_call_attempt_appears",
)

RECEIPTS_REQUIRED_BEFORE = (
    "operator_approval_receipt",
    "model_invocation_boundary_receipt",
    "redacted_proof_bundle_receipt",
    "no_external_provider_receipt",
    "no_tool_authority_receipt",
)

RECEIPTS_REQUIRED_AFTER = (
    "verifier_pass_fail_receipt",
    "published_response_hash_receipt",
    "model_invocation_attempt_receipt",
    "fallback_receipt_if_verifier_blocks",
)

OPERATOR_DECISION_OPTIONS = (
    "approve_one_time_local_lm_invocation_for_finance_payment_watch",
    "request_more_detail",
    "choose_different_model",
    "reject_for_now",
)

AUTHORITY_BOUNDARY = {
    "invocation_allowed": False,
    "proof_bundle_allowed": False,
    "protected_actions_allowed": False,
    "authority_granted": False,
    "authority_grant_allowed": False,
    "model_invocation_allowed": False,
    "local_model_runtime_contact_allowed": False,
    "external_llm_allowed": False,
    "external_provider_connect_allowed": False,
    "tool_authority": False,
    "tool_authority_allowed": False,
    "tool_execution_allowed": False,
    "memory_write_authority": False,
    "memory_write_access": False,
    "memory_promotion_allowed": False,
    "business_action_authority": False,
    "business_action_allowed": False,
    "worker_spawn_allowed": False,
    "email_send_allowed": False,
    "gmail_allowed": False,
    "browser_access_allowed": False,
    "coupa_allowed": False,
    "portal_submit_allowed": False,
    "ledger_mutation_allowed": False,
    "paid_marking_allowed": False,
    "workbook_mutation_allowed": False,
    "pdf_export_allowed": False,
    "git_push_allowed": False,
    "git_merge_allowed": False,
}

IMPLEMENTATION_BOUNDARY = {
    "model_invoked": False,
    "ollama_called": False,
    "runtime_connected": False,
    "local_model_runtime_connected": False,
    "prompt_sent": False,
    "prompt_sent_to_model": False,
    "proof_bundle_sent": False,
    "proof_bundle_sent_to_model": False,
    "external_provider_used": False,
    "external_provider_connected": False,
    "provider_api_called": False,
    "secrets_read": False,
    "worker_spawn_performed": False,
    "tool_execution_performed": False,
    "memory_promotion_performed": False,
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
    "git_push_performed": False,
    "git_merge_performed": False,
}

UNSAFE_TRUE_KEYS = (
    set(AUTHORITY_BOUNDARY)
    | set(IMPLEMENTATION_BOUNDARY)
    | set(local_model_list_inventory.UNSAFE_TRUE_KEYS)
    | set(local_model_selection_for_proof_response.UNSAFE_TRUE_KEYS)
    | set(proof_to_response_runtime.UNSAFE_TRUE_KEYS)
    | {
        "approved",
        "operator_approved",
        "invocation_approved",
        "proof_bundle_exposure_approved",
        "ready_for_invocation",
        "live_invocation_ready",
        "runtime_contact_allowed_now",
        "tool_access",
        "memory_write_access",
        "business_action_authority",
        "external_provider_used",
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
    runtime_status = _load_json(root / proof_to_response_runtime.STATUS_JSON_EXPORT_NAME)
    active_source = str(runtime_status.get("active_candidate_source") or "")
    ready = runtime_status.get("status") == proof_to_response_runtime.READY_STATUS and active_source == proof_to_response_runtime.CANDIDATE_SOURCE_SHADOW_PILOT
    return {
        "precondition_ref": "proof_to_response_shadow_pilot_runtime",
        "source_ref": f"generated/read_models/{proof_to_response_runtime.STATUS_JSON_EXPORT_NAME}",
        "observed_status": "PROOF_TO_RESPONSE_SHADOW_PILOT_RUNTIME_READY" if ready else "PROOF_TO_RESPONSE_SHADOW_PILOT_RUNTIME_NOT_READY",
        "accepted_statuses": ["PROOF_TO_RESPONSE_SHADOW_PILOT_RUNTIME_READY"],
        "observed_active_candidate_source": active_source,
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


def _selection_packet(read_model_root: Path) -> dict[str, Any]:
    payload = _load_json(_rooted(read_model_root) / "local_model_selection_for_proof_response.json")
    packet = payload.get("selection_packet")
    return dict(packet) if isinstance(packet, Mapping) else {}


def _model_inventory(read_model_root: Path) -> list[dict[str, Any]]:
    payload = _load_json(_rooted(read_model_root) / "local_model_list_inventory.json")
    rows = payload.get("discovered_models")
    return [dict(row) for row in rows if isinstance(row, Mapping)] if isinstance(rows, list) else []


def selected_model_present(read_model_root: Path = DEFAULT_READ_MODEL_ROOT) -> bool:
    for row in _model_inventory(read_model_root):
        if row.get("model_ref") == SELECTED_MODEL_REF and row.get("runtime_ref") == SELECTED_RUNTIME_REF and row.get("model_name") == SELECTED_MODEL_NAME:
            return row.get("present") is True
    return False


def selection_matches_required_model(read_model_root: Path = DEFAULT_READ_MODEL_ROOT) -> bool:
    packet = _selection_packet(read_model_root)
    return (
        packet.get("recommended_runtime_ref") == SELECTED_RUNTIME_REF
        and packet.get("recommended_model_ref") == SELECTED_MODEL_REF
        and packet.get("recommended_model_name") == SELECTED_MODEL_NAME
        and packet.get("ready_for_invocation") is False
        and packet.get("proof_bundle_allowed") is False
    )


def runtime_contact_method() -> dict[str, Any]:
    return {
        "recommended_method_ref": "ollama_cli_one_shot_stdin_after_operator_approval",
        "runtime_ref": SELECTED_RUNTIME_REF,
        "model_name": SELECTED_MODEL_NAME,
        "command_template_review_only_not_executed": f"ollama run {SELECTED_MODEL_NAME}",
        "runtime_contact_allowed_now": False,
        "runtime_connected": False,
        "prompt_sent": False,
        "proof_bundle_sent": False,
        "reason": (
            "Recommended for the first pilot because it is local-only, names the exact model, keeps the first invocation "
            "surface small, and avoids expanding to an HTTP endpoint until a later approval explicitly chooses that path."
        ),
        "alternatives_considered": [
            {
                "method_ref": "local_ollama_api_after_operator_approval",
                "recommended_for_first_pilot": False,
                "reason": "Possible later, but it adds endpoint handling and request logging surface not needed for the first one-time pilot.",
            }
        ],
    }


def prompt_shape() -> dict[str, Any]:
    return {
        "segments": [
            "system_developer_boundary_text",
            "redacted_freshness_gated_decision_trace_proof_bundle",
            "required_response_schema",
            "forbidden_claims",
            "verifier_reminder",
        ],
        "system_developer_boundary_text": [
            "Use only the supplied redacted proof bundle.",
            "Do not claim paid, sent, submitted, or executed unless a receipt proves it.",
            "Do not ask for hidden context or protected secrets.",
            "Do not grant authority or promise protected actions.",
        ],
        "redacted_proof_bundle_only": True,
        "required_response_schema": list(response_shape().keys()),
        "forbidden_claims": [
            "paid",
            "sent",
            "submitted",
            "executed",
            "ledger_mutated",
            "workbook_mutated",
            "Coupa_submit_performed",
            "authority_granted",
        ],
        "verifier_reminder": "Publication is allowed only after the deterministic proof-to-response verifier passes.",
    }


def response_shape() -> dict[str, str]:
    return {
        "headline": "Concise operator-facing headline.",
        "body": "One or two short paragraphs grounded only in proof refs.",
        "next_step": "One safe next controller action.",
        "missing_input": "List of missing proof/context fields.",
        "can_do_now": "Safe actions available without protected authority.",
        "cannot_do_yet": "Protected or unproven actions that remain blocked.",
        "requested_controls": "Safe controller controls requested by the draft.",
        "claimed_facts": "Factual claims that must map to proof, receipt, or gate refs.",
    }


def build_invocation_boundary_packet(*, read_model_root: Path = DEFAULT_READ_MODEL_ROOT, generated_at: str | None = None) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    return {
        "packet_id": "local_lm_invocation_boundary:finance_capital_hilton:qwen3_8b_q4_k_m:v0",
        "status": PACKET_STATUS,
        "generated_at": generated_at,
        "invocation_allowed": False,
        "proof_bundle_allowed": False,
        "selected_runtime_ref": SELECTED_RUNTIME_REF,
        "selected_model_ref": SELECTED_MODEL_REF,
        "selected_model_name": SELECTED_MODEL_NAME,
        "pilot_lane": PILOT_LANE,
        "pilot_context": {
            "world_ref": PILOT_WORLD_REF,
            "thread_ref": PILOT_THREAD_REF,
            "context_ref": "context:finance:capital_hilton:payment_watch",
            "objective_ref": "objective:finance:capital_hilton:payment_watch",
        },
        "pilot_question": PILOT_QUESTION,
        "candidate_source_mode": CANDIDATE_SOURCE_MODE,
        "expected_response_summary": (
            "Payment evidence is missing. Coupa is processing. The ledger stays untouched. Next: attach payment evidence."
        ),
        "exact_boundary": {
            "summary": "One-time local proof-to-response draft only after explicit operator approval; no tool, provider, business, or memory authority.",
            "no_tools": True,
            "no_browser": True,
            "no_gmail": True,
            "no_coupa": True,
            "no_ledger_mutation": True,
            "no_workbook_mutation": True,
            "no_pdf_export": True,
            "no_paid_marking": True,
            "no_submit": True,
            "no_push_or_merge": True,
            "no_worker_spawn": True,
            "no_memory_promotion": True,
            "no_external_provider": True,
            "no_raw_financial_or_private_proof": True,
            "no_operator_device_session_verification_secrets": True,
            "authority_boundary": dict(AUTHORITY_BOUNDARY),
        },
        "allowed_inputs": list(ALLOWED_INPUTS),
        "forbidden_inputs": list(FORBIDDEN_INPUTS),
        "forbidden_actions": list(FORBIDDEN_ACTIONS),
        "runtime_contact_method": runtime_contact_method(),
        "prompt_shape": prompt_shape(),
        "response_shape": response_shape(),
        "verifier_required": True,
        "fallback_required": True,
        "stop_conditions": list(STOP_CONDITIONS),
        "receipts_required": {
            "before_invocation": list(RECEIPTS_REQUIRED_BEFORE),
            "after_invocation": list(RECEIPTS_REQUIRED_AFTER),
        },
        "operator_decision_options": list(OPERATOR_DECISION_OPTIONS),
        "review_only_assertions": {
            "this_packet_is_not_approval": True,
            "model_not_invoked": True,
            "ollama_not_contacted": True,
            "prompt_not_sent": True,
            "proof_bundle_not_sent": True,
            "proof_bundle_exposure_not_approved": True,
        },
        "source_refs": [
            "generated/read_models/local_model_selection_for_proof_response.json",
            "generated/read_models/local_model_list_inventory.json",
            "generated/read_models/local_lm_proof_response_preflight_receipts.json",
            "generated/read_models/local_lm_proof_to_response_pilot_plan.json",
            "generated/read_models/proof_bundle_freshness_trace_status.json",
            "generated/read_models/proof_bundle_builder_redaction_status.json",
            "generated/read_models/proof_bundle_redaction_policy.json",
            f"generated/read_models/{proof_to_response_runtime.STATUS_JSON_EXPORT_NAME}",
            "generated/read_models/context_freshness_decision_trace_gate.json",
        ],
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "implementation_boundary": dict(IMPLEMENTATION_BOUNDARY),
    }


def build_read_model(*, read_model_root: Path = DEFAULT_READ_MODEL_ROOT, generated_at: str | None = None) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    preconditions = precondition_rows(read_model_root)
    packet = build_invocation_boundary_packet(read_model_root=read_model_root, generated_at=generated_at)
    selected_model_ok = selected_model_present(read_model_root) and selection_matches_required_model(read_model_root)
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "status": READY_STATUS if all(row.get("ready") is True for row in preconditions) and selected_model_ok else NOT_READY_STATUS,
        "generated_at": generated_at,
        "purpose": "Define the review-only invocation boundary for a future one-time local LM proof-to-response pilot.",
        "invocation_boundary_packet": packet,
        "packet_id": packet["packet_id"],
        "packet_status": packet["status"],
        "invocation_allowed": False,
        "proof_bundle_allowed": False,
        "selected_runtime_ref": SELECTED_RUNTIME_REF,
        "selected_model_ref": SELECTED_MODEL_REF,
        "selected_model_name": SELECTED_MODEL_NAME,
        "pilot_lane": PILOT_LANE,
        "pilot_question": PILOT_QUESTION,
        "candidate_source_mode": CANDIDATE_SOURCE_MODE,
        "preconditions": preconditions,
        "source_refs": packet["source_refs"],
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "implementation_boundary": dict(IMPLEMENTATION_BOUNDARY),
        "machine_proof": {
            "review_only": True,
            "selected_model_present": selected_model_present(read_model_root),
            "selection_matches_required_model": selection_matches_required_model(read_model_root),
            "model_invoked": False,
            "ollama_called": False,
            "runtime_connected": False,
            "prompt_sent": False,
            "proof_bundle_sent": False,
            "external_provider_used": False,
            "tool_authority": False,
            "business_action_authority": False,
            "unsafe_true_grants_absent": True,
        },
        "source_content_hashes": {
            "preconditions": _content_hash(preconditions),
            "invocation_boundary_packet": _content_hash(packet),
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
    packet = read_model.get("invocation_boundary_packet") if isinstance(read_model.get("invocation_boundary_packet"), Mapping) else {}
    contact = packet.get("runtime_contact_method") if isinstance(packet.get("runtime_contact_method"), Mapping) else {}
    lines = [
        "# Local LM Proof Response Invocation Boundary Packet",
        "",
        f"Status: {read_model.get('status')}",
        f"Packet status: {packet.get('status')}",
        "",
        "This is review-only. It does not invoke a model, contact Ollama, send a prompt, send a proof bundle, grant authority, or create an execution path.",
        "",
        "## Selected Model",
        "",
        f"- Runtime: `{packet.get('selected_runtime_ref')}`",
        f"- Model ref: `{packet.get('selected_model_ref')}`",
        f"- Model name: `{packet.get('selected_model_name')}`",
        f"- Invocation allowed: `{str(packet.get('invocation_allowed')).lower()}`",
        f"- Proof bundle allowed: `{str(packet.get('proof_bundle_allowed')).lower()}`",
        "",
        "## Pilot Boundary",
        "",
        f"- Lane: `{packet.get('pilot_lane')}`",
        f"- Question: {packet.get('pilot_question')}",
        f"- Expected response: {packet.get('expected_response_summary')}",
        f"- Candidate source mode: `{packet.get('candidate_source_mode')}`",
        "",
        "## Runtime Contact Method",
        "",
        f"- Recommended method: `{contact.get('recommended_method_ref')}`",
        f"- Command template, not executed: `{contact.get('command_template_review_only_not_executed')}`",
        f"- Contact allowed now: `{str(contact.get('runtime_contact_allowed_now')).lower()}`",
        f"- Reason: {contact.get('reason')}",
        "",
        "## Allowed Input",
        "",
    ]
    for item in packet.get("allowed_inputs") or []:
        lines.append(f"- `{item}`")
    lines.extend(["", "## Forbidden Input", ""])
    for item in packet.get("forbidden_inputs") or []:
        lines.append(f"- `{item}`")
    lines.extend(["", "## Stop Conditions", ""])
    for item in packet.get("stop_conditions") or []:
        lines.append(f"- `{item}`")
    lines.extend(["", "## Operator Decision Options", ""])
    for item in packet.get("operator_decision_options") or []:
        lines.append(f"- `{item}`")
    lines.append("")
    return "\n".join(lines)


def export_local_lm_proof_response_invocation_boundary_packet(
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
        "packet_status": str(read_model.get("packet_status") or ""),
        "selected_runtime_ref": str(read_model.get("selected_runtime_ref") or ""),
        "selected_model_ref": str(read_model.get("selected_model_ref") or ""),
        "invocation_allowed": str(read_model.get("invocation_allowed")).lower(),
        "proof_bundle_allowed": str(read_model.get("proof_bundle_allowed")).lower(),
        "read_model_path": read_model_path.as_posix(),
        "bridge_read_model_path": bridge_read_model_path,
        "wiki_path": wiki_path.as_posix(),
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Publish Local LM Proof Response Invocation Boundary Packet V0.")
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
    result = export_local_lm_proof_response_invocation_boundary_packet(
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
