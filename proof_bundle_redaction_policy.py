"""Proof bundle redaction policy V0.

Defines and tests what a future proof-to-response LM may see. This module is
policy/read-model work only: it does not invoke LMs, connect runtimes, spawn
workers, send email, open browser/Gmail/Coupa, or mutate ledgers/workbooks.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import agent_response_voice_modes
import proof_bundle_builder
import proof_to_response_runtime


ROOT = Path(__file__).resolve().parent
DEFAULT_READ_MODEL_ROOT = Path("generated/read_models")
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_BRIDGE_ROOT = Path("/mnt/e/openclaw/generated/read_models")
DEFAULT_WIKI_PATH = Path("generated/wiki/openclaw/Proof Bundle Redaction Policy.md")

SCHEMA_VERSION = "proof_bundle_redaction_policy_v0"
READ_MODEL_ID = "proof_bundle_redaction_policy"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
READY_STATUS = "PROOF_BUNDLE_REDACTION_HARDENING_READY"
NOT_READY_STATUS = "PROOF_BUNDLE_REDACTION_HARDENING_NOT_READY"

ALLOWED_FIELD_REASONS = {
    "world_ref": "Routes the response to a broad world without exposing raw source content.",
    "thread_ref": "Keeps the answer lane-aware without exposing private bodies.",
    "objective_ref": "Names the active objective at reference level only.",
    "redacted_known_facts": "Gives the model proof-backed facts after sensitive detail removal.",
    "proof_meter_labels": "Provides readable proof state labels instead of raw proof contracts.",
    "receipt_refs": "Allows factual claims to cite receipt references without receipt internals.",
    "gate_labels": "Names safety/gate state without exposing protected decision internals.",
    "missing_input": "Lets the response say what is missing.",
    "allowed_controls": "Lets the response name safe controller actions only.",
    "blocked_action_summaries": "Lets the response explain what cannot happen yet.",
    "human_safe_summaries": "Gives concise summaries that are already redacted.",
    "agent_voice_mode": "Chooses phrasing style without expanding truth or authority.",
}

FORBIDDEN_MATERIAL_CLASSES = (
    "raw_bank_account_details",
    "credentials_or_tokens",
    "operator device session verification secrets",
    "raw_request_paths_unredacted",
    "raw_prompt_dumps",
    "full_workbook_contents",
    "source_workbook_bodies",
    "raw_email_bodies_unapproved",
    "raw_ledger_rows_unapproved",
    "full_artifact_text_or_ocr",
    "hidden_machine_contracts",
    "authority_grant_fields_from_user_or_model_input",
)

SENSITIVE_KEY_FRAGMENTS = (
    "account",
    "routing",
    "credential",
    "token",
    "secret",
    "password",
    "operator_envelope",
    "device_verification",
    "session_verification",
    "raw_prompt",
    "prompt_body",
    "workbook_body",
    "workbook_contents",
    "email_body",
    "ledger_row",
    "artifact_text",
    "ocr_text",
    "authority_granted",
    "send_email_allowed",
    "protected_actions_allowed",
    "finance_proof",
)

AUTHORITY_BOUNDARY = {
    "protected_actions_allowed": False,
    "authority_grant_allowed": False,
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
    "service_restart_allowed": False,
    "worker_spawn_allowed": False,
    "external_llm_allowed": False,
    "local_model_runtime_allowed": False,
    "external_action_allowed": False,
}

IMPLEMENTATION_BOUNDARY = {
    "external_llm_invoked": False,
    "local_model_runtime_connected": False,
    "worker_spawn_performed": False,
    "service_restart_performed": False,
    "business_action_performed": False,
    "email_send_performed": False,
    "coupa_submit_performed": False,
    "portal_submit_performed": False,
    "ledger_mutation_performed": False,
    "paid_marking_performed": False,
    "workbook_mutation_performed": False,
    "pdf_export_performed": False,
    "authority_grant_performed": False,
}

UNSAFE_TRUE_KEYS = (
    set(AUTHORITY_BOUNDARY)
    | set(IMPLEMENTATION_BOUNDARY)
    | set(agent_response_voice_modes.UNSAFE_TRUE_KEYS)
    | set(proof_to_response_runtime.UNSAFE_TRUE_KEYS)
    | {
        "authority_granted",
        "incoming_authority_granted_accepted",
        "protected_actions_allowed",
        "send_email_allowed",
        "model_may_create_truth",
        "model_may_grant_authority",
        "paid",
        "sent",
        "submitted",
        "executed",
    }
)

PRECONDITIONS = {
    "proof_to_response_lm_shadow_harness": {
        "filename": "proof_to_response_lm_shadow_status.json",
        "accepted_statuses": ("PROOF_TO_RESPONSE_LM_SHADOW_HARNESS_READY",),
    },
    "local_lm_proof_response_readiness_gate": {
        "filename": "local_lm_proof_to_response_readiness_gate.json",
        "accepted_statuses": ("LOCAL_LM_PROOF_RESPONSE_READINESS_GATE_READY",),
    },
    "evidence_confidence_scoring": {
        "filename": "evidence_confidence_scoring.json",
        "accepted_statuses": ("EVIDENCE_CONFIDENCE_SCORING_READY",),
    },
    "verified_evidence_intake": {
        "filename": "evidence_intake_status.json",
        "accepted_statuses": ("VERIFIED_EVIDENCE_INTAKE_READY", "EVIDENCE_INTAKE_READY"),
        "proxy_note": "Existing status is EVIDENCE_INTAKE_READY with verified_operator_evidence_intake_ready=true.",
    },
    "agent_response_voice_modes": {
        "filename": "agent_response_voice_modes.json",
        "accepted_statuses": ("AGENT_RESPONSE_VOICE_MODES_READY",),
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
        ready = observed in accepted
        if ref == "verified_evidence_intake":
            proof = payload.get("machine_proof") if isinstance(payload.get("machine_proof"), Mapping) else {}
            ready = ready and proof.get("verified_operator_evidence_intake_ready") is True
        row = {
            "precondition_ref": ref,
            "source_ref": f"generated/read_models/{filename}",
            "observed_status": observed,
            "accepted_statuses": accepted,
            "ready": ready,
        }
        if spec.get("proxy_note"):
            row["proxy_note"] = str(spec["proxy_note"])
        rows.append(row)
    return rows


def allowed_lm_input_fields() -> list[dict[str, str]]:
    return [{"field_ref": field, "reason": reason} for field, reason in ALLOWED_FIELD_REASONS.items()]


def forbidden_material_policy() -> list[dict[str, Any]]:
    return [
        {
            "material_class": material,
            "default_policy": "excluded",
            "allowed_only_if": "explicitly_approved_and_redacted" if material in {"raw_email_bodies_unapproved", "raw_ledger_rows_unapproved", "raw_request_paths_unredacted"} else "never_in_default_lm_bundle",
        }
        for material in FORBIDDEN_MATERIAL_CLASSES
    ]


def _fact(text: str, *refs: str) -> dict[str, Any]:
    return {"text": text, "source_refs": list(refs)}


SCENARIOS: dict[str, dict[str, Any]] = {
    "capital_hilton_payment_watch": {
        "world_ref": "finance",
        "thread_ref": "capital_hilton",
        "objective_ref": "capital_hilton_payment_watch",
        "redacted_known_facts": [
            _fact("Payment evidence is missing.", "proof_meter:capital_hilton.truth", "receipt:payment_watch"),
            _fact("The ledger remains untouched.", "receipt:ledger_no_mutation"),
            _fact("Coupa is processing or under watch, not paid truth.", "proof_meter:capital_hilton.freshness"),
        ],
        "proof_meter_labels": ["Truth: trusted/current", "Freshness: waiting external", "Risk: watch"],
        "receipt_refs": ["receipt:capital_hilton_payment_watch"],
        "gate_labels": ["No paid marking without payment evidence"],
        "missing_input": ["payment_evidence"],
        "allowed_controls": ["attach_proof", "open_finance_lane"],
        "blocked_action_summaries": ["mark paid blocked", "ledger mutation blocked", "Coupa submit blocked"],
        "human_safe_summaries": ["Payment evidence is missing; ledger remains untouched."],
        "agent_voice_mode": "diagnostic",
        "privacy_class": "financial_sensitive/local_only",
        "proof_scope": ["finance", "capital_hilton", "payment_watch"],
    },
    "live_arts_payment_evidence": {
        "world_ref": "finance",
        "thread_ref": "live_arts_md",
        "objective_ref": "live_arts_payment_evidence",
        "redacted_known_facts": [
            _fact("candidate payment-processing evidence was recorded.", "receipt:evidence_recorded"),
            _fact("This does not mark the invoice paid.", "receipt:paid_false"),
            _fact("Raw account and routing details are excluded.", "policy:financial_redaction"),
        ],
        "proof_meter_labels": ["Truth: candidate evidence", "Evidence: operator reported", "Risk: watch"],
        "receipt_refs": ["receipt:live_arts_candidate_payment_evidence"],
        "gate_labels": ["Paid marking still blocked"],
        "missing_input": ["payment_arrival_confirmation", "ledger_evidence"],
        "allowed_controls": ["verify_arrival", "attach_stronger_proof"],
        "blocked_action_summaries": ["mark paid blocked", "ledger mutation blocked"],
        "human_safe_summaries": ["Candidate payment-processing evidence is recorded; paid truth is not established."],
        "agent_voice_mode": "diagnostic",
        "privacy_class": "financial_sensitive/local_only",
        "proof_scope": ["finance", "live_arts_md", "candidate_evidence"],
    },
    "business_development_capital_hilton_followup": {
        "world_ref": "business_development",
        "thread_ref": "capital_hilton",
        "objective_ref": "capital_hilton_followup",
        "redacted_known_facts": [
            _fact("Proposal follow-up can be staged.", "action:stage_followup"),
            _fact("No email send authority is present.", "authority:no_send"),
        ],
        "proof_meter_labels": ["Authority: no grant", "Risk: calm"],
        "receipt_refs": ["receipt:followup_stageable"],
        "gate_labels": ["Send blocked without separate approval"],
        "missing_input": [],
        "allowed_controls": ["stage_followup_draft", "show_details"],
        "blocked_action_summaries": ["email send blocked", "external update blocked"],
        "human_safe_summaries": ["A follow-up draft can be staged for review; sending is not authorized."],
        "agent_voice_mode": "operations",
        "privacy_class": "internal_operator_safe",
        "proof_scope": ["business_development", "capital_hilton", "followup"],
    },
    "music_niles_controller_mapping": {
        "world_ref": "music",
        "thread_ref": "controller_mapping",
        "objective_ref": "niles_controller_mapping",
        "redacted_known_facts": [
            _fact("Creative mapping can be discussed as options, not truth.", "voice:niles"),
            _fact("Target software and controller are needed before concrete mapping.", "missing:target"),
        ],
        "proof_meter_labels": ["Truth: creative candidate", "Authority: no grant"],
        "receipt_refs": ["receipt:voice_mode_contract"],
        "gate_labels": ["Creative ideas are not canonical truth"],
        "missing_input": ["target_software", "controller"],
        "allowed_controls": ["ask_taste_question", "offer_mapping_options"],
        "blocked_action_summaries": ["metadata truth claim blocked", "unrelated finance proof excluded"],
        "human_safe_summaries": ["Niles may discuss vibe, feel, arrangement, and controller mapping options."],
        "agent_voice_mode": "creative",
        "privacy_class": "creative_internal_safe",
        "proof_scope": ["music", "creative_mapping"],
    },
    "self_heal_repair": {
        "world_ref": "system",
        "thread_ref": "self_heal_repair",
        "objective_ref": "self_heal_blocker",
        "redacted_known_facts": [
            _fact("A blocker summary is available.", "self_heal:blocker"),
            _fact("Validation failure can be named without raw logs unless redacted.", "self_heal:validation"),
            _fact("Safe repair options can be staged.", "self_heal:repair_options"),
        ],
        "proof_meter_labels": ["Truth: receipt-backed blocker", "Risk: blocked"],
        "receipt_refs": ["receipt:self_heal_blocker"],
        "gate_labels": ["Service restart authority not included"],
        "missing_input": ["repair_receipt_or_manual_step"],
        "allowed_controls": ["stage_repair_package", "run_safe_validation"],
        "blocked_action_summaries": ["service restart blocked", "worker spawn blocked"],
        "human_safe_summaries": ["The model may see the blocker summary, validation failure, and safe repair options."],
        "agent_voice_mode": "diagnostic",
        "privacy_class": "internal_operator_safe",
        "proof_scope": ["system", "repair"],
    },
    "unknown_context": {
        "world_ref": "unknown",
        "thread_ref": "unknown",
        "objective_ref": "unknown",
        "redacted_known_facts": [_fact("Lane context is missing.", "router:missing_context")],
        "proof_meter_labels": ["Truth: needs verification"],
        "receipt_refs": [],
        "gate_labels": [],
        "missing_input": ["world_ref", "thread_ref"],
        "allowed_controls": ["choose_lane"],
        "blocked_action_summaries": ["package staging blocked", "business action routing blocked"],
        "human_safe_summaries": ["Only missing lane context is visible."],
        "agent_voice_mode": "brief",
        "privacy_class": "internal_operator_safe",
        "proof_scope": ["unknown_context"],
    },
}


def _sanitize_extra_context(extra: Mapping[str, Any] | None) -> dict[str, str]:
    if not isinstance(extra, Mapping):
        return {}
    allowed: dict[str, str] = {}
    for key in ("target_software", "controller", "agent_voice_mode"):
        value = extra.get(key)
        if value is not None:
            allowed[key] = str(value)[:120]
    return allowed


def build_redacted_lm_input(
    scenario_id: str,
    *,
    raw_request: Mapping[str, Any] | None = None,
    model_draft: Mapping[str, Any] | None = None,
    creative_context: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if scenario_id not in SCENARIOS:
        raise ValueError(f"unknown_redaction_scenario:{scenario_id}")
    scenario = json.loads(stable_json(SCENARIOS[scenario_id]))
    context = _sanitize_extra_context(creative_context)
    missing_input = list(scenario["missing_input"])
    if scenario_id == "music_niles_controller_mapping":
        if context.get("target_software"):
            scenario["human_safe_summaries"].append(f"Target software supplied: {context['target_software']}.")
            missing_input = [item for item in missing_input if item != "target_software"]
        if context.get("controller"):
            scenario["human_safe_summaries"].append(f"Controller supplied: {context['controller']}.")
            missing_input = [item for item in missing_input if item != "controller"]
        if context.get("agent_voice_mode"):
            scenario["agent_voice_mode"] = context["agent_voice_mode"]
    excluded_markers = excluded_markers_from_inputs(raw_request, model_draft)
    return {
        "redacted_bundle_id": f"redacted_lm_input:{scenario_id}",
        "scenario_id": scenario_id,
        "world_ref": scenario["world_ref"],
        "thread_ref": scenario["thread_ref"],
        "objective_ref": scenario["objective_ref"],
        "redacted_known_facts": [fact["text"] for fact in scenario["redacted_known_facts"]],
        "proof_meter_labels": scenario["proof_meter_labels"],
        "receipt_refs": scenario["receipt_refs"],
        "gate_labels": scenario["gate_labels"],
        "missing_input": missing_input,
        "allowed_controls": scenario["allowed_controls"],
        "blocked_action_summaries": scenario["blocked_action_summaries"],
        "human_safe_summaries": scenario["human_safe_summaries"],
        "agent_voice_mode": scenario["agent_voice_mode"],
        "voice_mode_policy": {
            "may_shape_phrasing": True,
            "may_prioritize": True,
            "may_create_truth": False,
            "may_grant_authority": False,
        },
        "privacy_class": scenario["privacy_class"],
        "sensitive_detail_policy": "redacted_summary_only",
        "proof_scope": scenario["proof_scope"],
        "excluded_material_classes": list(FORBIDDEN_MATERIAL_CLASSES),
        "excluded_input_markers": excluded_markers,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
    }


def excluded_markers_from_inputs(*inputs: Mapping[str, Any] | None) -> list[str]:
    markers: set[str] = set()
    for value in inputs:
        if not isinstance(value, Mapping):
            continue
        for key, _child in _walk_values(value):
            lower = key.lower()
            if any(fragment in lower for fragment in SENSITIVE_KEY_FRAGMENTS):
                markers.add(redacted_marker_for_key(lower))
    return sorted(markers)


def redacted_marker_for_key(key: str) -> str:
    if "authority" in key or "send_email_allowed" in key or "protected_actions_allowed" in key:
        return "authority_input_excluded"
    if "prompt" in key:
        return "raw_prompt_excluded"
    if "artifact" in key or "ocr" in key:
        return "raw_artifact_or_ocr_excluded"
    if "workbook" in key:
        return "workbook_body_excluded"
    if "email" in key:
        return "raw_email_body_excluded"
    if "ledger" in key:
        return "raw_ledger_row_excluded"
    if "account" in key or "routing" in key:
        return "financial_detail_excluded"
    if "operator_envelope" in key or "device" in key or "session" in key:
        return "operator_device_session_secret_excluded"
    if "credential" in key or "token" in key or "secret" in key or "password" in key:
        return "credential_or_secret_excluded"
    return "raw_sensitive_detail_excluded"


def validate_redacted_lm_input(bundle: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    allowed = set(ALLOWED_FIELD_REASONS) | {
        "redacted_bundle_id",
        "scenario_id",
        "voice_mode_policy",
        "privacy_class",
        "sensitive_detail_policy",
        "proof_scope",
        "excluded_material_classes",
        "excluded_input_markers",
        "authority_boundary",
    }
    for key in bundle:
        if key not in allowed:
            errors.append(f"unexpected_field:{key}")
    text = stable_json(bundle).lower()
    forbidden_literals = (
        "operator_envelope",
        "device_verification_secret",
        "session_verification_secret",
        "credential_token",
        "raw_prompt_body",
        "raw_artifact_text",
        "raw_ocr_text",
        "authority_granted",
        "send_email_allowed",
    )
    for literal in forbidden_literals:
        if literal in text:
            errors.append(f"forbidden_literal_present:{literal}")
    if unsafe_true_grants(bundle):
        errors.append("unsafe_true_grants_present")
    return errors


def scenario_policy_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for scenario_id in SCENARIOS:
        bundle = build_redacted_lm_input(scenario_id)
        rows.append(
            {
                "scenario_id": scenario_id,
                "world_ref": bundle["world_ref"],
                "thread_ref": bundle["thread_ref"],
                "privacy_class": bundle["privacy_class"],
                "agent_voice_mode": bundle["agent_voice_mode"],
                "lm_visible_summary": bundle["human_safe_summaries"],
                "lm_visible_missing_input": bundle["missing_input"],
                "lm_visible_blocked_actions": bundle["blocked_action_summaries"],
                "validation_errors": validate_redacted_lm_input(bundle),
                "redacted_input_example": bundle,
            }
        )
    return rows


def build_read_model(
    *,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    preconditions = precondition_rows(read_model_root)
    scenarios = scenario_policy_rows()
    validation_errors = [
        f"{row['scenario_id']}:{error}"
        for row in scenarios
        for error in row.get("validation_errors") or []
    ]
    all_preconditions_ready = all(row.get("ready") is True for row in preconditions)
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "status": READY_STATUS if all_preconditions_ready and not validation_errors else NOT_READY_STATUS,
        "generated_at": generated_at,
        "purpose": "Prove future proof-to-response LM input is bounded, private, redacted, and authority-free.",
        "allowed_lm_input_fields": allowed_lm_input_fields(),
        "forbidden_material_policy": forbidden_material_policy(),
        "scenario_policies": scenarios,
        "default_redaction_rules": {
            "financial_sensitive_requires_local_only": True,
            "raw_artifact_or_ocr_excluded_by_default": True,
            "raw_prompt_bodies_excluded": True,
            "raw_email_bodies_require_explicit_redaction": True,
            "raw_ledger_rows_require_explicit_redaction": True,
            "source_workbook_bodies_excluded": True,
            "authority_granted_from_input_excluded": True,
            "agent_voice_mode_does_not_expand_truth_or_authority": True,
        },
        "preconditions": preconditions,
        "source_refs": [
            "generated/read_models/proof_to_response_lm_shadow_status.json",
            "generated/read_models/proof_to_response_runtime_status.json",
            "generated/read_models/local_lm_proof_to_response_readiness_gate.json",
            "generated/read_models/evidence_confidence_scoring.json",
            "generated/read_models/evidence_intake_status.json",
            "generated/read_models/agent_response_voice_modes.json",
            "proof_bundle_builder.py",
        ],
        "source_content_hashes": {
            "allowed_lm_input_fields": _content_hash(allowed_lm_input_fields()),
            "forbidden_material_policy": _content_hash(forbidden_material_policy()),
            "scenario_policies": _content_hash(scenarios),
            "proof_bundle_required_fields": _content_hash(list(proof_bundle_builder.REQUIRED_BUNDLE_FIELDS)),
        },
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "implementation_boundary": dict(IMPLEMENTATION_BOUNDARY),
        "validation_errors": validation_errors,
        "machine_proof": {
            "preconditions_ready": all_preconditions_ready,
            "allowed_fields_all_have_reasons": all(bool(row.get("reason")) for row in allowed_lm_input_fields()),
            "scenario_count": len(scenarios),
            "validation_errors": validation_errors,
            "external_llm_invoked": False,
            "local_model_runtime_connected": False,
            "worker_spawn_performed": False,
            "business_action_performed": False,
            "unsafe_true_grants": [],
            "unsafe_true_grants_absent": True,
        },
    }
    unsafe = unsafe_true_grants(payload)
    payload["machine_proof"]["unsafe_true_grants"] = unsafe
    payload["machine_proof"]["unsafe_true_grants_absent"] = not unsafe
    if unsafe:
        payload["status"] = NOT_READY_STATUS
    return payload


def build_wiki(read_model: Mapping[str, Any]) -> str:
    lines = [
        "# Proof Bundle Redaction Policy",
        "",
        f"Status: {read_model.get('status')}",
        "",
        "This policy defines what a future proof-to-response LM may see. It keeps input bounded, private, redacted, and authority-free.",
        "",
        "## Allowed Fields",
        "",
    ]
    for row in read_model.get("allowed_lm_input_fields") or []:
        lines.append(f"- `{row.get('field_ref')}`: {row.get('reason')}")
    lines.extend(["", "## Forbidden Material", ""])
    for row in read_model.get("forbidden_material_policy") or []:
        lines.append(f"- `{row.get('material_class')}`: {row.get('default_policy')}")
    lines.extend(["", "## Scenarios", ""])
    for row in read_model.get("scenario_policies") or []:
        lines.append(
            f"- `{row.get('scenario_id')}`: `{row.get('privacy_class')}`, voice `{row.get('agent_voice_mode')}`, errors `{row.get('validation_errors')}`"
        )
    proof = read_model.get("machine_proof") if isinstance(read_model.get("machine_proof"), Mapping) else {}
    lines.extend(
        [
            "",
            "## Proof",
            "",
            f"- Unsafe true grants absent: `{str(proof.get('unsafe_true_grants_absent')).lower()}`",
            f"- Validation errors: `{proof.get('validation_errors')}`",
            "",
        ]
    )
    return "\n".join(lines)


def export_proof_bundle_redaction_policy(
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
    parser = argparse.ArgumentParser(description="Publish Proof Bundle Redaction Policy V0.")
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
    result = export_proof_bundle_redaction_policy(
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
