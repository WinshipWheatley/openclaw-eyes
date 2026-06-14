"""Local LM model selection review packet V0.

Review-only packet recommending one model/harness candidate for the first
proof-to-response local LM pilot. This module reads existing read models and
writes generated read-model/wiki artifacts only. It does not invoke a model,
connect a runtime, send prompts or proof bundles, start services, call external
providers, read secrets/API keys, spawn workers, mutate business state, export
PDFs, mark paid, submit, or push.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import local_lm_proof_response_preflight_receipts as preflight
import model_catalog_inventory as catalog
import proof_to_response_runtime


ROOT = Path(__file__).resolve().parent
DEFAULT_READ_MODEL_ROOT = Path("generated/read_models")
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_BRIDGE_ROOT = Path("/mnt/e/openclaw/generated/read_models")
DEFAULT_WIKI_PATH = Path("generated/wiki/openclaw/Local LM Model Selection Review Packet.md")

SCHEMA_VERSION = "local_lm_model_selection_review_packet_v0"
READ_MODEL_ID = "local_lm_model_selection_review_packet"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
READY_STATUS = "LOCAL_LM_MODEL_SELECTION_REVIEW_READY"
NOT_READY_STATUS = "LOCAL_LM_MODEL_SELECTION_REVIEW_NOT_READY"
PACKET_ID = "local_lm_model_selection_review_packet:finance_capital_hilton:v0"
PACKET_STATUS = "pending_operator_review"

PREFERRED_CANDIDATE_REF = "model_candidate:sidecar:local_llm_shadow_mode"
PREFERRED_HARNESS_REF = "local_llm_shadow_mode"
FIRST_PILOT_LANE = "finance/capital_hilton"
PILOT_QUESTION = "What should I do here?"
DEFAULT_REDACTION_POLICY_REF = "generated/read_models/proof_bundle_redaction_policy.json"
DEFAULT_VERIFIER_REF = "proof_to_response_verifier.py#proof_to_response_verifier_v0"

PRECONDITIONS = {
    "model_catalog_inventory": {
        "filename": "model_catalog_inventory.json",
        "accepted_statuses": ("MODEL_CATALOG_INVENTORY_READY",),
    },
    "local_lm_runtime_discovery": {
        "filename": "local_lm_runtime_discovery.json",
        "accepted_statuses": ("LOCAL_LM_RUNTIME_DISCOVERY_READY",),
    },
    "local_lm_proof_response_preflight_receipts": {
        "filename": "local_lm_proof_response_preflight_receipts.json",
        "accepted_statuses": ("LOCAL_LM_PROOF_RESPONSE_PREFLIGHT_RECEIPTS_READY",),
    },
    "local_lm_proof_response_pilot_plan": {
        "filename": "local_lm_proof_to_response_pilot_plan.json",
        "accepted_statuses": ("LOCAL_LM_PROOF_RESPONSE_PILOT_PLAN_READY",),
    },
    "local_lm_pilot_harness_selection_packet": {
        "filename": "local_lm_pilot_harness_selection_packet.json",
        "accepted_statuses": ("LOCAL_LM_PILOT_HARNESS_SELECTION_PACKET_READY",),
    },
    "local_lm_proof_response_readiness_gate": {
        "filename": "local_lm_proof_to_response_readiness_gate.json",
        "accepted_statuses": ("LOCAL_LM_PROOF_RESPONSE_READINESS_GATE_READY",),
    },
    "proof_bundle_redaction_policy": {
        "filename": "proof_bundle_redaction_policy.json",
        "accepted_statuses": ("PROOF_BUNDLE_REDACTION_HARDENING_READY",),
    },
    "proof_bundle_builder_redaction_integration": {
        "filename": "proof_bundle_builder_redaction_status.json",
        "accepted_statuses": ("PROOF_BUNDLE_BUILDER_REDACTION_INTEGRATION_READY",),
    },
    "proof_to_response_runtime": {
        "filename": proof_to_response_runtime.STATUS_JSON_EXPORT_NAME,
        "accepted_statuses": (proof_to_response_runtime.READY_STATUS,),
    },
}

REQUIRED_RECEIPTS_BEFORE_INVOCATION = (
    "operator_approval_receipt",
    "model_invocation_boundary_receipt",
    "verifier_pass_fail_receipt",
    "published_response_hash_receipt",
)

DECISION_OPTIONS = (
    "approve_model_selection_for_one_time_pilot",
    "request_more_detail",
    "choose_different_candidate",
    "reject_for_now",
)

AUTHORITY_BOUNDARY = {
    "selection_review_is_invocation_approval": False,
    "selected_for_review_grants_authority": False,
    "invocation_allowed": False,
    "proof_bundle_allowed": False,
    "protected_actions_allowed": False,
    "authority_granted": False,
    "authority_grant_allowed": False,
    "model_invocation_allowed": False,
    "live_lm_invocation_allowed": False,
    "external_llm_allowed": False,
    "external_provider_connect_allowed": False,
    "provider_key_material_access_allowed": False,
    "tool_authority": False,
    "tool_authority_allowed": False,
    "tool_execution_allowed": False,
    "memory_write_authority": False,
    "memory_write_access": False,
    "memory_promotion_allowed": False,
    "worker_spawn_allowed": False,
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
    "git_push_allowed": False,
    "merge_allowed": False,
}

IMPLEMENTATION_BOUNDARY = {
    "model_invoked": False,
    "runtime_connected": False,
    "local_model_runtime_connected": False,
    "external_provider_connected": False,
    "provider_api_called": False,
    "prompt_sent": False,
    "proof_bundle_sent": False,
    "service_started_or_stopped": False,
    "worker_spawn_performed": False,
    "secret_read": False,
    "api_key_read": False,
    "tool_execution_performed": False,
    "memory_write_performed": False,
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
    "merge_performed": False,
}

UNSAFE_TRUE_KEYS = (
    set(AUTHORITY_BOUNDARY)
    | set(IMPLEMENTATION_BOUNDARY)
    | set(catalog.UNSAFE_TRUE_KEYS)
    | set(preflight.UNSAFE_TRUE_KEYS)
    | set(proof_to_response_runtime.UNSAFE_TRUE_KEYS)
    | {
        "approved",
        "operator_approved",
        "invocation_approved",
        "proof_bundle_exposure_approved",
        "ready_for_live_invocation",
        "live_invocation_ready",
        "external_provider_used",
        "tool_access",
        "memory_write_access",
        "business_action_authority",
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


def _catalog_payload(read_model_root: Path) -> dict[str, Any]:
    return _load_json(_rooted(read_model_root) / "model_catalog_inventory.json")


def _preflight_payload(read_model_root: Path) -> dict[str, Any]:
    return _load_json(_rooted(read_model_root) / "local_lm_proof_response_preflight_receipts.json")


def _pilot_plan_payload(read_model_root: Path) -> dict[str, Any]:
    return _load_json(_rooted(read_model_root) / "local_lm_proof_to_response_pilot_plan.json")


def _selection_payload(read_model_root: Path) -> dict[str, Any]:
    payload = _load_json(_rooted(read_model_root) / "local_lm_pilot_harness_selection_packet.json")
    nested = payload.get("selection_packet")
    return dict(nested) if isinstance(nested, Mapping) else {}


def _redaction_payload(read_model_root: Path) -> dict[str, Any]:
    return _load_json(_rooted(read_model_root) / "proof_bundle_redaction_policy.json")


def _candidate_rows(read_model_root: Path) -> list[dict[str, Any]]:
    payload = _catalog_payload(read_model_root)
    rows = payload.get("model_candidates")
    return [dict(row) for row in rows if isinstance(row, Mapping)] if isinstance(rows, list) else []


def _candidate_by_ref(candidates: list[Mapping[str, Any]], candidate_ref: str) -> dict[str, Any]:
    for candidate in candidates:
        if candidate.get("candidate_ref") == candidate_ref:
            return dict(candidate)
    return {}


def _receipt_refs(rows: Any) -> list[str]:
    if not isinstance(rows, list):
        return []
    refs: list[str] = []
    for row in rows:
        if isinstance(row, Mapping) and row.get("receipt_ref"):
            refs.append(str(row["receipt_ref"]))
        elif isinstance(row, str):
            refs.append(row)
    return refs


def required_receipts_before_invocation(read_model_root: Path = DEFAULT_READ_MODEL_ROOT) -> list[str]:
    preflight_payload = _preflight_payload(read_model_root)
    missing = _receipt_refs(preflight_payload.get("receipts_missing"))
    if not missing:
        missing = list(REQUIRED_RECEIPTS_BEFORE_INVOCATION)
    required = list(dict.fromkeys([*missing, *REQUIRED_RECEIPTS_BEFORE_INVOCATION]))
    return required


def _field_list(payload: Mapping[str, Any], key: str, fallback: list[str]) -> list[str]:
    rows = payload.get(key)
    if isinstance(rows, list) and rows:
        values: list[str] = []
        for row in rows:
            if isinstance(row, Mapping):
                field_ref = row.get("field_ref") or row.get("field") or row.get("name")
                if field_ref:
                    values.append(str(field_ref))
            elif row:
                values.append(str(row))
        if values:
            return list(dict.fromkeys(values))
    return fallback


def allowed_proof_bundle_fields(read_model_root: Path = DEFAULT_READ_MODEL_ROOT) -> list[str]:
    redaction = _redaction_payload(read_model_root)
    builder = _load_json(_rooted(read_model_root) / "proof_bundle_builder_redaction_status.json")
    fallback = [
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
    ]
    redaction_fields = _field_list(redaction, "allowed_lm_input_fields", [])
    builder_fields = _field_list(builder, "allowed_lm_input_fields", [])
    return list(dict.fromkeys(redaction_fields or builder_fields or fallback))


def forbidden_proof_bundle_fields(read_model_root: Path = DEFAULT_READ_MODEL_ROOT) -> list[str]:
    redaction = _redaction_payload(read_model_root)
    forbidden = redaction.get("forbidden_material_policy")
    values: list[str] = []
    if isinstance(forbidden, Mapping):
        for key, value in forbidden.items():
            if isinstance(value, Mapping) and value.get("forbidden") is True:
                values.append(str(key))
            elif value is True:
                values.append(str(key))
    elif isinstance(forbidden, list):
        values.extend(str(item) for item in forbidden if str(item))
    fallback = [
        "raw_finance_details",
        "bank_account_numbers",
        "credentials_or_tokens",
        "operator_device_session_verification_secrets",
        "raw_prompt_dumps",
        "raw_artifact_ocr_text",
        "workbook_email_ledger_bodies",
        "hidden_machine_contracts",
        "authority_granted_fields",
    ]
    return list(dict.fromkeys(values or fallback))


def _harness_ref_from_candidate(candidate_ref: str) -> str:
    if candidate_ref.startswith("model_candidate:sidecar:"):
        return candidate_ref.rsplit(":", 1)[-1]
    if candidate_ref.startswith("model_candidate:local_runtime:"):
        return candidate_ref.rsplit(":", 1)[-1]
    return candidate_ref.rsplit(":", 1)[-1] if ":" in candidate_ref else candidate_ref


def _selection_reason(candidate: Mapping[str, Any], selected_ref: str) -> str:
    candidate_ref = str(candidate.get("candidate_ref") or "")
    locality = str(candidate.get("locality") or "")
    if candidate_ref == selected_ref:
        return (
            "Selected for review because it is local/sidecar, already aligned with the shadow pilot path, "
            "requires no external provider or API key, and can draft from redacted proof only after explicit approval."
        )
    if locality == "external":
        return "Rejected external_provider candidate because external providers remain blocked for private finance/client proof."
    if candidate_ref.endswith(":ollama"):
        return "Rejected for invocation now because runtime presence does not prove model boundary, approval, or proof-bundle receipts."
    if "hermes_sidecar" in candidate_ref:
        return "Rejected for invocation now because Hermes needs explicit proof-to-response registration and receipts."
    if locality == "operator_assist":
        return "Rejected for this pilot because operator-assist harnesses require separate scope and proof-bundle approval."
    return "Rejected for this pilot until selection, privacy, redaction, verifier, and approval receipts exist."


def _quality_risk(candidate: Mapping[str, Any], selected: bool) -> str:
    if selected:
        return "mock/shadow quality may be less capable than a live model, but it is sufficient for concise proof-to-response review."
    if str(candidate.get("locality")) == "external":
        return "quality may be high, but privacy/egress risk blocks this lane by default."
    if str(candidate.get("locality")) == "local":
        return "unknown installed model quality until model identity and boundary receipts exist."
    return "quality cannot be relied on until the harness is registered and receipted."


def _operational_risk(candidate: Mapping[str, Any], selected: bool) -> str:
    if selected:
        return "low operational risk for review because no live runtime is connected and verifier publication remains mandatory."
    if candidate.get("running") is True:
        return "runtime may be present/running, but connecting or querying it is still blocked without receipts."
    if str(candidate.get("locality")) == "external":
        return "external path would require provider/privacy exception receipts and is out of scope."
    return "operational boundary remains incomplete until explicit receipts exist."


def _considered_candidate(candidate: Mapping[str, Any], *, selected_ref: str) -> dict[str, Any]:
    candidate_ref = str(candidate.get("candidate_ref") or "")
    selected = candidate_ref == selected_ref
    return {
        "candidate_ref": candidate_ref,
        "model_or_harness_name": str(candidate.get("model_or_harness_name") or candidate.get("provider_or_runtime") or candidate_ref),
        "locality": str(candidate.get("locality") or "unknown"),
        "present": candidate.get("present", "unknown"),
        "running": candidate.get("running", "unknown"),
        "configured": candidate.get("configured", "unknown"),
        "invocation_allowed": False,
        "proof_bundle_allowed": False,
        "reason_selected_or_rejected": _selection_reason(candidate, selected_ref),
        "missing_receipts": [str(item) for item in candidate.get("missing_receipts") or REQUIRED_RECEIPTS_BEFORE_INVOCATION],
        "privacy_risk": str(candidate.get("privacy_risk") or "privacy boundary missing until receipts exist"),
        "expected_quality_risk": _quality_risk(candidate, selected),
        "operational_risk": _operational_risk(candidate, selected),
        "verifier_mandatory": True,
        "tool_authority": False,
        "memory_write_authority": False,
        "business_action_authority": False,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
    }


def candidate_refs_to_consider(candidates: list[Mapping[str, Any]], selected_ref: str) -> list[str]:
    preferred_order = [
        selected_ref,
        "model_candidate:local_runtime:ollama",
        "model_candidate:sidecar:hermes_sidecar",
        "model_candidate:operator_assist:codex_desktop_operator_assist",
        "model_candidate:external_provider:openai",
    ]
    observed = {str(row.get("candidate_ref")) for row in candidates}
    external_refs = [str(row.get("candidate_ref")) for row in candidates if row.get("locality") == "external"]
    ordered = [ref for ref in preferred_order if ref in observed]
    for ref in external_refs:
        if ref not in ordered:
            ordered.append(ref)
    if not ordered:
        ordered = [str(row.get("candidate_ref")) for row in candidates[:5] if row.get("candidate_ref")]
    return ordered


def recommended_candidate_ref(candidates: list[Mapping[str, Any]], preflight_payload: Mapping[str, Any], selection_payload: Mapping[str, Any]) -> str:
    selected_harness = str(
        selection_payload.get("selected_harness_ref")
        or preflight_payload.get("selected_harness_ref")
        or PREFERRED_HARNESS_REF
    )
    candidate_ref = f"model_candidate:sidecar:{selected_harness}"
    if _candidate_by_ref(candidates, candidate_ref):
        return candidate_ref
    if _candidate_by_ref(candidates, PREFERRED_CANDIDATE_REF):
        return PREFERRED_CANDIDATE_REF
    return "none"


def build_review_packet(
    *,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    candidates = _candidate_rows(read_model_root)
    preflight_payload = _preflight_payload(read_model_root)
    pilot_plan = _pilot_plan_payload(read_model_root)
    selection_payload = _selection_payload(read_model_root)
    selected_ref = recommended_candidate_ref(candidates, preflight_payload, selection_payload)
    selected_candidate = _candidate_by_ref(candidates, selected_ref)
    no_suitable_candidate = not selected_candidate
    candidate_refs = candidate_refs_to_consider(candidates, selected_ref)
    considered = [
        _considered_candidate(_candidate_by_ref(candidates, ref), selected_ref=selected_ref)
        for ref in candidate_refs
        if _candidate_by_ref(candidates, ref)
    ]
    required_receipts = required_receipts_before_invocation(read_model_root)
    selected_for_review = not no_suitable_candidate
    selected_harness_ref = _harness_ref_from_candidate(selected_ref) if selected_for_review else "none"
    expected_response = {
        "headline": "Payment evidence needed",
        "body": "Coupa is processing. I can't mark this paid until payment evidence is attached. The ledger stays untouched.",
        "next_step": "Attach payment evidence.",
    }
    first_pilot_scope = {
        "lane": FIRST_PILOT_LANE,
        "world_ref": "finance",
        "thread_ref": "capital_hilton",
        "question": str(preflight_payload.get("pilot_question") or PILOT_QUESTION),
        "scenario_ref": "finance_capital_hilton_payment_watch",
        "proof_bundle_policy": "redacted_proof_bundle_only",
        "raw_financial_private_proof_allowed": False,
        "operator_device_session_verification_material_allowed": False,
    }
    if isinstance(pilot_plan.get("first_pilot_lane"), Mapping):
        first_pilot_scope["source_plan_lane_ref"] = str(pilot_plan["first_pilot_lane"].get("lane_ref") or FIRST_PILOT_LANE)
    return {
        "packet_id": PACKET_ID,
        "status": PACKET_STATUS,
        "generated_at": generated_at,
        "recommended_candidate_ref": selected_ref,
        "recommended_harness_ref": selected_harness_ref,
        "recommended_model_ref": None,
        "selected_for_review": selected_for_review,
        "no_suitable_candidate_reason": "" if selected_for_review else "No catalog candidate matched the selected local/shadow harness.",
        "invocation_allowed": False,
        "proof_bundle_allowed": False,
        "required_operator_decision": "approve_model_selection_for_one_time_pilot",
        "required_receipts_before_invocation": required_receipts,
        "first_pilot_scope": first_pilot_scope,
        "expected_response": expected_response,
        "allowed_proof_bundle_fields": allowed_proof_bundle_fields(read_model_root),
        "forbidden_proof_bundle_fields": forbidden_proof_bundle_fields(read_model_root),
        "selection_criteria": {
            "local_only_preferred": True,
            "no_external_provider": True,
            "no_api_key_required": True,
            "no_tool_authority": True,
            "no_memory_write_authority": True,
            "suitable_for_concise_proof_to_response_drafting": True,
            "redacted_proof_bundle_only": True,
            "verifier_mandatory": True,
            "first_pilot_lane": FIRST_PILOT_LANE,
            "no_raw_financial_private_proof": True,
            "no_operator_device_session_verification_material": True,
        },
        "candidate_considered": considered,
        "stop_conditions": [
            "model_invocation_attempted_without_operator_approval",
            "runtime_connection_attempted_without_model_boundary_receipt",
            "external_provider_path_appears",
            "proof_bundle_contains_forbidden_field",
            "raw_financial_private_proof_requested_or_exposed",
            "operator_device_session_verification_material_requested_or_exposed",
            "model_claims_paid_sent_submitted_or_executed_without_receipt",
            "model_requests_tool_memory_or_business_authority",
            "verifier_fails",
        ],
        "fallback_plan": {
            "if_operator_does_not_approve": "stay_shadow_only",
            "if_candidate_boundary_missing": "request_more_detail_or_choose_different_candidate",
            "if_candidate_text_fails_verifier": "publish_safe_fallback_and_record_failure_reason",
            "if_forbidden_input_detected": "abort_pilot_before_invocation",
            "safe_fallback_response": expected_response,
        },
        "decision_options": list(DECISION_OPTIONS),
        "verifier_ref": DEFAULT_VERIFIER_REF,
        "redaction_policy_ref": DEFAULT_REDACTION_POLICY_REF,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "implementation_boundary": dict(IMPLEMENTATION_BOUNDARY),
    }


def build_read_model(
    *,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    preconditions = precondition_rows(read_model_root)
    packet = build_review_packet(read_model_root=read_model_root, generated_at=generated_at)
    all_ready = all(row.get("ready") is True for row in preconditions)
    packet_ready = packet.get("selected_for_review") is True
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "status": READY_STATUS if all_ready and packet_ready else NOT_READY_STATUS,
        "generated_at": generated_at,
        "purpose": "Recommend one model/harness candidate for review before a one-time proof-to-response local LM pilot.",
        "review_packet": packet,
        "preconditions": preconditions,
        "source_refs": [
            "generated/read_models/model_catalog_inventory.json",
            "generated/read_models/local_lm_runtime_discovery.json",
            "generated/read_models/local_lm_proof_response_preflight_receipts.json",
            "generated/read_models/local_lm_proof_to_response_pilot_plan.json",
            "generated/read_models/local_lm_pilot_harness_selection_packet.json",
            "generated/read_models/local_lm_proof_to_response_readiness_gate.json",
            "generated/read_models/proof_bundle_redaction_policy.json",
            "generated/read_models/proof_bundle_builder_redaction_status.json",
            "generated/read_models/proof_to_response_runtime_status.json",
        ],
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "implementation_boundary": dict(IMPLEMENTATION_BOUNDARY),
        "machine_proof": {
            "review_only": True,
            "status_pending_operator_review": True,
            "selected_for_review_does_not_grant_invocation": True,
            "approved": False,
            "invocation_allowed": False,
            "proof_bundle_allowed": False,
            "model_invoked": False,
            "runtime_connected": False,
            "external_provider_used": False,
            "secret_read": False,
            "api_key_read": False,
            "tool_access": False,
            "memory_write_access": False,
            "business_action_authority": False,
            "unsafe_true_grants_absent": True,
        },
        "source_content_hashes": {
            "preconditions": _content_hash(preconditions),
            "review_packet": _content_hash(packet),
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
    packet = read_model.get("review_packet") if isinstance(read_model.get("review_packet"), Mapping) else {}
    scope = packet.get("first_pilot_scope") if isinstance(packet.get("first_pilot_scope"), Mapping) else {}
    response = packet.get("expected_response") if isinstance(packet.get("expected_response"), Mapping) else {}
    lines = [
        "# Local LM Model Selection Review Packet",
        "",
        f"Status: {read_model.get('status')}",
        f"Packet status: {packet.get('status')}",
        "",
        "This is selection review only. It does not invoke a model, connect a runtime, send a prompt, send a proof bundle, call a provider, read secrets, or grant authority.",
        "",
        "## Recommendation",
        "",
        f"- Candidate: `{packet.get('recommended_candidate_ref')}`",
        f"- Harness: `{packet.get('recommended_harness_ref')}`",
        f"- Model: `{packet.get('recommended_model_ref')}`",
        f"- Selected for review: `{str(packet.get('selected_for_review')).lower()}`",
        f"- Invocation allowed: `{str(packet.get('invocation_allowed')).lower()}`",
        f"- Proof bundle allowed: `{str(packet.get('proof_bundle_allowed')).lower()}`",
        f"- Required operator decision: `{packet.get('required_operator_decision')}`",
        "",
        "## First Pilot Scope",
        "",
        f"- Lane: `{scope.get('lane')}`",
        f"- Question: {scope.get('question')}",
        f"- Scenario: `{scope.get('scenario_ref')}`",
        "",
        "## Expected Response",
        "",
        f"- Headline: {response.get('headline')}",
        f"- Body: {response.get('body')}",
        f"- Next step: {response.get('next_step')}",
        "",
        "## Candidates Considered",
        "",
    ]
    for row in packet.get("candidate_considered") or []:
        if not isinstance(row, Mapping):
            continue
        lines.append(
            f"- `{row.get('candidate_ref')}`: {row.get('reason_selected_or_rejected')} "
            f"Invocation `{str(row.get('invocation_allowed')).lower()}`, proof `{str(row.get('proof_bundle_allowed')).lower()}`."
        )
    lines.extend(["", "## Required Receipts Before Invocation", ""])
    for receipt in packet.get("required_receipts_before_invocation") or []:
        lines.append(f"- `{receipt}`")
    lines.extend(["", "## Stop Conditions", ""])
    for condition in packet.get("stop_conditions") or []:
        lines.append(f"- `{condition}`")
    lines.extend(["", "## Decision Options", ""])
    for option in packet.get("decision_options") or []:
        lines.append(f"- `{option}`")
    lines.append("")
    return "\n".join(lines)


def export_local_lm_model_selection_review_packet(
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
    packet = read_model.get("review_packet", {})
    return {
        "status": str(read_model.get("status") or NOT_READY_STATUS),
        "packet_status": str(packet.get("status") or ""),
        "recommended_candidate_ref": str(packet.get("recommended_candidate_ref") or ""),
        "invocation_allowed": str(packet.get("invocation_allowed")).lower(),
        "proof_bundle_allowed": str(packet.get("proof_bundle_allowed")).lower(),
        "read_model_path": read_model_path.as_posix(),
        "bridge_read_model_path": bridge_read_model_path,
        "wiki_path": wiki_path.as_posix(),
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Publish Local LM Model Selection Review Packet V0.")
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
    result = export_local_lm_model_selection_review_packet(
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
