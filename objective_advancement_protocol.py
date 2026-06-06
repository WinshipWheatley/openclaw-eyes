"""Objective Advancement Protocol V0.

Defines what generic controller actions such as Continue, Advance, Prepare it,
Stage it, Handle what you can, What's missing?, and Next safe move mean for
OpenClaw.

Objective advancement is not a final-action executor. It advances the current
objective to the next safe internal state, or returns a dynamic-card-shaped
blocker explaining the missing proof, input, or approval.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parent
DEFAULT_READ_MODEL_ROOT = Path("generated/read_models")
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_BRIDGE_ROOT = Path("/mnt/e/openclaw/generated/read_models")
DEFAULT_WIKI_PATH = Path("generated/wiki/openclaw/Objective Advancement Protocol.md")
DEFAULT_SQLITE_PATH = Path("generated/system_knowledge/objective_advancement_protocol.sqlite")

SCHEMA_VERSION = "objective_advancement_protocol_v0"
READ_MODEL_ID = "objective_advancement_protocol"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
READY_STATUS = "OBJECTIVE_ADVANCEMENT_PROTOCOL_READY"
NOT_READY_STATUS = "OBJECTIVE_ADVANCEMENT_PROTOCOL_NOT_READY"

MAC_REAL_USE_SMOKE_REF = "/mnt/e/openclaw/generated/read_models/mac_controller_real_use_smoke_status.json"

CLASS_A_MAY_ALLOW = (
    "readback",
    "plan",
    "draft",
    "stage package",
    "inspect local/status refs",
    "prepare evidence request",
    "prepare approval package",
    "prepare review packet",
)

CLASS_A_MUST_NOT_ALLOW = (
    "email send",
    "Gmail/browser/Coupa access",
    "portal submit",
    "ledger mutation",
    "mark paid",
    "workbook source mutation",
    "PDF export/send",
    "git push/merge",
    "worker spawn",
    "external provider call",
)

AUTHORITY_BOUNDARY = {
    "email_send_allowed": False,
    "gmail_allowed": False,
    "browser_access_allowed": False,
    "coupa_allowed": False,
    "portal_submit_allowed": False,
    "ledger_posting_allowed": False,
    "ledger_mutation_allowed": False,
    "workbook_source_mutation_allowed": False,
    "workbook_mutation_allowed": False,
    "pdf_export_allowed": False,
    "paid_marking_allowed": False,
    "business_action_allowed": False,
    "external_action_allowed": False,
    "authority_grant_allowed": False,
    "worker_spawn_allowed": False,
    "child_agent_run_allowed": False,
    "external_llm_allowed": False,
    "local_model_runtime_allowed": False,
    "external_provider_connect_allowed": False,
    "git_push_allowed": False,
    "merge_allowed": False,
    "sent": False,
    "paid": False,
}

UNSAFE_TRUE_KEYS = set(AUTHORITY_BOUNDARY) | {
    "email_send_performed",
    "email_sent",
    "gmail_access_performed",
    "gmail_opened",
    "browser_access_performed",
    "browser_opened",
    "coupa_access_performed",
    "coupa_opened",
    "coupa_submit_performed",
    "portal_submit_performed",
    "ledger_posting_performed",
    "ledger_mutation_performed",
    "workbook_open_performed",
    "workbook_body_read_performed",
    "spreadsheet_cell_read_performed",
    "workbook_mutation_performed",
    "excel_automation_performed",
    "pdf_export_performed",
    "paid_marking_performed",
    "payment_marking_performed",
    "mark_paid_performed",
    "submit_performed",
    "business_action_performed",
    "authority_grant_performed",
    "worker_spawn_performed",
    "worker_execution_performed",
    "child_agent_run_performed",
    "external_llm_invoked",
    "external_llm_called",
    "external_provider_connected",
    "local_model_runtime_connected",
    "model_invoked",
    "git_push_performed",
    "push_performed",
    "merge_performed",
}

PRECONDITIONS = {
    "operator_controller_event_live_route": {
        "filename": "operator_controller_event_router_status.json",
        "accepted_statuses": ("OPERATOR_CONTROLLER_EVENT_LIVE_ROUTE_READY",),
        "status_fields": ("live_route_status", "status"),
    },
    "operator_controller_protocol": {
        "filename": "operator_controller_protocol.json",
        "accepted_statuses": ("OPERATOR_CONTROLLER_PROTOCOL_READY",),
    },
    "first_class_operator_envelope": {
        "filename": "first_class_operator_envelope_status.json",
        "accepted_statuses": ("FIRST_CLASS_OPERATOR_ENVELOPE_READY",),
    },
    "dynamic_card_packet_v1": {
        "filename": "dynamic_card_packet_latest.json",
        "accepted_statuses": ("DYNAMIC_CARD_PACKET_V1_READY", "DYNAMIC_CARD_PACKET_READY"),
    },
    "dynamic_card_v1_rails": {
        "filename": "mac_thinning_readiness_map.json",
        "accepted_statuses": ("DYNAMIC_CARD_V1_RAILS_READY",),
    },
    "universal_receipt_envelope": {
        "filename": "universal_receipt_envelope_status.json",
        "accepted_statuses": ("UNIVERSAL_RECEIPT_ENVELOPE_READY",),
    },
    "proof_meter_normalization": {
        "filename": "proof_meter_normalization.json",
        "accepted_statuses": ("PROOF_METER_NORMALIZATION_READY",),
    },
    "controller_knob_mode_filters": {
        "filename": "controller_knob_mode_filters.json",
        "accepted_statuses": ("CONTROLLER_KNOB_MODE_FILTERS_READY",),
    },
    "operator_session_timeline": {
        "filename": "operator_session_timeline.json",
        "accepted_statuses": ("OPERATOR_SESSION_TIMELINE_READY",),
    },
    "mac_controller_real_use_smoke": {
        "absolute_path": MAC_REAL_USE_SMOKE_REF,
        "accepted_statuses": ("MAC_CONTROLLER_REAL_USE_SMOKE_READY",),
    },
}


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _rooted(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def _short_hash(*parts: object, length: int = 16) -> str:
    joined = "\0".join(str(part) for part in parts)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()[:length]


def _load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError:
        return {}


def _strings(payload: Any) -> list[str]:
    if isinstance(payload, str):
        return [payload]
    if isinstance(payload, Mapping):
        values: list[str] = []
        for value in payload.values():
            values.extend(_strings(value))
        return values
    if isinstance(payload, Sequence) and not isinstance(payload, (bytes, bytearray)):
        values: list[str] = []
        for value in payload:
            values.extend(_strings(value))
        return values
    return []


def unsafe_true_grants(payload: Any) -> list[str]:
    grants: list[str] = []
    if isinstance(payload, Mapping):
        for key, value in payload.items():
            if key in UNSAFE_TRUE_KEYS and value is True:
                grants.append(str(key))
            grants.extend(unsafe_true_grants(value))
    elif isinstance(payload, Sequence) and not isinstance(payload, (str, bytes, bytearray)):
        for item in payload:
            grants.extend(unsafe_true_grants(item))
    return sorted(set(grants))


def class_a_approval_scope(class_a_approval_present: bool = False) -> dict[str, Any]:
    return {
        "class_a_approval_present": bool(class_a_approval_present),
        "definition": (
            "Objective-level operator permission to advance safe internal steps "
            "without asking about every granular substep."
        ),
        "may_allow": list(CLASS_A_MAY_ALLOW),
        "must_not_allow": list(CLASS_A_MUST_NOT_ALLOW),
        "requires_separate_future_gate_for_protected_actions": True,
    }


def _machine_proof(extra: Mapping[str, Any] | None = None) -> dict[str, Any]:
    proof = {
        "email_send_performed": False,
        "gmail_access_performed": False,
        "browser_access_performed": False,
        "coupa_access_performed": False,
        "coupa_submit_performed": False,
        "portal_submit_performed": False,
        "ledger_posting_performed": False,
        "ledger_mutation_performed": False,
        "workbook_open_performed": False,
        "workbook_body_read_performed": False,
        "spreadsheet_cell_read_performed": False,
        "workbook_mutation_performed": False,
        "pdf_export_performed": False,
        "paid_marking_performed": False,
        "submit_performed": False,
        "business_action_performed": False,
        "worker_spawn_performed": False,
        "child_agent_run_performed": False,
        "external_llm_invoked": False,
        "local_model_runtime_connected": False,
        "external_provider_connected": False,
        "git_push_performed": False,
        "merge_performed": False,
        "generated_summaries_are_not_truth": True,
        "receipts_read_models_and_proof_refs_define_truth": True,
    }
    if extra:
        proof.update(dict(extra))
    proof["unsafe_true_grants"] = unsafe_true_grants(proof)
    proof["unsafe_true_grants_absent"] = not proof["unsafe_true_grants"]
    return proof


def _dynamic_card(
    *,
    objective_ref: str,
    world: str,
    thread: str,
    headline: str,
    summary: str,
    next_safe_action: str,
    status_label: str,
    action_label: str,
    proof_refs: Sequence[str],
    blocked: bool,
    generated_at: str,
) -> dict[str, Any]:
    card_id = "dynamic_card.objective_advancement:" + _short_hash(objective_ref, world, thread, headline, generated_at)
    return {
        "schema_version": "dynamic_card_packet_v1",
        "card_id": card_id,
        "card_family": "objective_advancement_card",
        "card_type": "objective_advancement",
        "generated_at": generated_at,
        "world_ref": world or "unknown",
        "thread_ref": thread or "unknown",
        "entity_refs": [objective_ref] if objective_ref else [],
        "speaker_ref": "openclaw",
        "voice_profile_ref": "agent_voice_profile:openclaw",
        "headline": headline,
        "plain_summary": summary,
        "supporting_lines": [
            "Protected final actions remain gated.",
            "Receipts, read models, and proof refs define truth.",
        ],
        "status_label": status_label,
        "tone": "blocked" if blocked else "calm",
        "trust_state": "trusted_current" if not blocked else "needs_operator_input",
        "confidence_class": "generated_summary",
        "freshness_state": "current",
        "operator_attention_required": bool(blocked),
        "visible_by_default": True,
        "collapse_when_resolved": False,
        "action_slots": [
            {
                "slot": "primary",
                "label": action_label,
                "enabled": True,
                "controller_event_type": "attach_proof" if "proof" in action_label.lower() else "continue",
                "receipt_required": True,
                "authority_boundary": dict(AUTHORITY_BOUNDARY),
                "proof_refs": list(proof_refs),
            }
        ],
        "proof": {
            "read_model_refs": list(proof_refs),
            "receipt_refs": [],
            "redacted_summary": "Proof refs collapsed by default.",
            "sensitive_detail_policy": "collapsed_by_default",
            "developer_proof_only": False,
        },
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "next_safe_action": next_safe_action,
    }


def _decision(
    *,
    objective_ref: str,
    world: str,
    thread: str,
    current_state: Mapping[str, Any],
    desired_outcome: str,
    next_safe_state: str,
    operator_response: str,
    next_safe_action: str,
    action_label: str,
    blocked: bool = False,
    blocker: str = "",
    missing_input: str = "",
    proof_needed: str = "",
    operator_question: str = "",
    allowed_internal_advance: Sequence[str] = (),
    protected_final_action: str = "",
    final_approval_required: bool = False,
    receipt_requirement: str = "universal_receipt_required_for_state_change",
    proof_refs: Sequence[str] = (),
    class_a_approved: bool = False,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    dynamic_card_ref = "dynamic_card.objective_advancement:" + _short_hash(
        objective_ref, world, thread, next_safe_state
    )
    card = _dynamic_card(
        objective_ref=objective_ref,
        world=world,
        thread=thread,
        headline=next_safe_state.replace("_", " ").title(),
        summary=operator_response,
        next_safe_action=next_safe_action,
        status_label=next_safe_state,
        action_label=action_label,
        proof_refs=proof_refs,
        blocked=blocked,
        generated_at=generated_at,
    )
    card["card_id"] = dynamic_card_ref
    return {
        "schema_version": "objective_advancement_decision_v0",
        "objective_ref": objective_ref,
        "current_world_ref": world,
        "current_thread_ref": thread,
        "current_state": dict(current_state),
        "desired_outcome": desired_outcome,
        "next_safe_state": next_safe_state,
        "blocked": bool(blocked),
        "blocker": blocker,
        "missing_input": missing_input,
        "proof_needed": proof_needed,
        "operator_question": operator_question,
        "operator_response": operator_response,
        "suggested_operator_action": {"label": action_label, "safe": True},
        "allowed_internal_advance": list(allowed_internal_advance),
        "protected_final_action": protected_final_action,
        "final_approval_required": bool(final_approval_required),
        "class_a_approval_scope": class_a_approval_scope(class_a_approved),
        "dynamic_card_ref": dynamic_card_ref,
        "dynamic_card": card,
        "receipt_requirement": receipt_requirement,
        "proof_refs": list(proof_refs),
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "machine_proof": _machine_proof(),
        "generated_at": generated_at,
    }


def advance_objective(context: Mapping[str, Any], *, generated_at: str | None = None) -> dict[str, Any]:
    world = str(context.get("current_world_ref") or context.get("target_world_ref") or "").strip().lower()
    thread = str(context.get("current_thread_ref") or context.get("target_thread_ref") or "").strip().lower()
    objective_ref = str(context.get("objective_ref") or f"objective:{world or 'unknown'}:{thread or 'unknown'}:advance")
    current_state = context.get("current_state") if isinstance(context.get("current_state"), Mapping) else {}
    desired_outcome = str(context.get("desired_outcome") or "advance current objective safely")
    class_a_approved = bool(context.get("class_a_approved"))

    if world == "finance" and thread == "capital_hilton":
        evidence_present = bool(current_state.get("payment_evidence_present") or context.get("payment_evidence_present"))
        if not evidence_present:
            return _decision(
                objective_ref=objective_ref,
                world=world,
                thread=thread,
                current_state=current_state,
                desired_outcome=desired_outcome,
                next_safe_state="REQUEST_PAYMENT_EVIDENCE",
                operator_response="I can't complete payment yet. I need payment evidence first.",
                next_safe_action="Attach proof",
                action_label="Attach proof",
                blocked=True,
                blocker="payment_evidence_missing",
                missing_input="payment_evidence",
                proof_needed="Bank deposit, remittance notice, Coupa payment status screenshot, or other payment proof.",
                operator_question="Can you attach payment proof?",
                allowed_internal_advance=("readback", "prepare_evidence_request", "inspect_local_status_refs"),
                protected_final_action="ledger_post_or_mark_paid",
                final_approval_required=True,
                proof_refs=("generated/read_models/capital_hilton_invoice_operator_run_status.json",),
                class_a_approved=class_a_approved,
                generated_at=generated_at,
            )

    if world == "finance" and thread == "live_arts_md":
        evidence_attached = bool(current_state.get("evidence_attached") or context.get("evidence_attached"))
        if evidence_attached:
            return _decision(
                objective_ref=objective_ref,
                world=world,
                thread=thread,
                current_state=current_state,
                desired_outcome=desired_outcome,
                next_safe_state="EVIDENCE_RECORDED_WAITING_FOR_CONFIRMATION",
                operator_response="I recorded this as payment-processing evidence. Ledger remains untouched.",
                next_safe_action="Review confirmation when payment proof is complete.",
                action_label="Review evidence",
                allowed_internal_advance=("record_candidate_evidence", "prepare_confirmation_review"),
                protected_final_action="ledger_post_or_mark_paid",
                final_approval_required=True,
                proof_refs=("generated/read_models/evidence_intake_status.json",),
                class_a_approved=class_a_approved,
                generated_at=generated_at,
            )

    if world == "business_development" and thread == "capital_hilton":
        return _decision(
            objective_ref=objective_ref,
            world=world,
            thread=thread,
            current_state=current_state,
            desired_outcome=desired_outcome,
            next_safe_state="FOLLOWUP_DRAFT_STAGED",
            operator_response="I can stage a Capital Hilton follow-up draft. I will not send it.",
            next_safe_action="Review the staged follow-up draft.",
            action_label="Stage follow-up draft",
            allowed_internal_advance=("readback", "plan", "draft", "stage_followup_draft"),
            protected_final_action="email_send",
            final_approval_required=True,
            proof_refs=("generated/read_models/capital_hilton_business_development_proposal.json",),
            class_a_approved=class_a_approved,
            generated_at=generated_at,
        )

    if world == "build" and ("review" in thread or "packet" in thread):
        requested = str(context.get("requested_review_action") or "").strip()
        allowed = ["open_review_controls", "prepare_review_decision"]
        next_state = "REVIEW_CONTROLS_READY"
        response = "I can open review controls. No merge or push is allowed."
        action = "Open review controls"
        if requested in {"mark_review_packet_informational", "request_review_packet_rework"}:
            allowed.append("record_review_decision_receipt")
            next_state = "REVIEW_DECISION_READY_TO_RECORD"
            response = "I can record the review decision receipt. No merge or push will run."
            action = "Record review decision"
        return _decision(
            objective_ref=objective_ref,
            world=world,
            thread=thread,
            current_state=current_state,
            desired_outcome=desired_outcome,
            next_safe_state=next_state,
            operator_response=response,
            next_safe_action=action,
            action_label=action,
            allowed_internal_advance=allowed,
            protected_final_action="merge_or_git_push",
            final_approval_required=True,
            proof_refs=("generated/read_models/workroom_review_decision_status.json",),
            class_a_approved=class_a_approved,
            generated_at=generated_at,
        )

    if world == "finance" and thread in {"st_annes", "st_anne", "st_annes_work_log"}:
        return _decision(
            objective_ref=objective_ref,
            world=world,
            thread=thread,
            current_state=current_state,
            desired_outcome=desired_outcome,
            next_safe_state="SURFACE_WORK_LOG_REVIEW_CHOICES",
            operator_response="I can surface the St. Anne's work-log review choices. I will not create an invoice, PDF, or email.",
            next_safe_action="Choose confirm, discard, edit, or mark test.",
            action_label="Review work-log choices",
            operator_question="Confirm, discard, edit, or mark this St. Anne's work-log event as test?",
            allowed_internal_advance=("readback", "inspect_local_status_refs", "prepare_review_choices"),
            protected_final_action="invoice_pdf_or_email_send",
            final_approval_required=True,
            proof_refs=("generated/read_models/st_annes_work_log_review_surface.json",),
            class_a_approved=class_a_approved,
            generated_at=generated_at,
        )

    return _decision(
        objective_ref=objective_ref,
        world=world or "unknown",
        thread=thread or "unknown",
        current_state=current_state,
        desired_outcome=desired_outcome,
        next_safe_state="NEEDS_VERIFICATION",
        operator_response="I need the lane or objective before I can safely advance it.",
        next_safe_action="Tell me the lane or objective.",
        action_label="Provide context",
        blocked=True,
        blocker="unknown_context",
        missing_input="lane_or_objective_context",
        operator_question="Which lane or objective should I advance?",
        allowed_internal_advance=("readback", "ask_context_question"),
        protected_final_action="unknown",
        final_approval_required=True,
        proof_refs=("generated/read_models/operator_controller_protocol.json",),
        class_a_approved=class_a_approved,
        generated_at=generated_at,
    )


def _observed_status(payload: Mapping[str, Any], fields: Sequence[str]) -> str:
    for field in fields:
        value = payload.get(field)
        if isinstance(value, str) and value:
            return value
    strings = _strings(payload)
    for value in strings:
        if value.endswith("_READY"):
            return value
    return ""


def build_preconditions(read_model_root: Path = DEFAULT_READ_MODEL_ROOT) -> list[dict[str, Any]]:
    root = _rooted(read_model_root)
    rows: list[dict[str, Any]] = []
    for ref, spec in PRECONDITIONS.items():
        path = Path(str(spec["absolute_path"])) if "absolute_path" in spec else root / str(spec["filename"])
        payload = _load_json(path)
        observed = _observed_status(payload, tuple(spec.get("status_fields", ("status",))))
        accepted = tuple(str(item) for item in spec["accepted_statuses"])
        ready = observed in accepted or any(value in accepted for value in _strings(payload))
        rows.append(
            {
                "precondition_ref": ref,
                "source_ref": str(path),
                "accepted_statuses": list(accepted),
                "observed_status": observed,
                "ready": bool(ready),
            }
        )
    return rows


def _examples(generated_at: str) -> list[dict[str, Any]]:
    contexts = [
        {
            "objective_ref": "objective:finance:capital_hilton:payment_watch",
            "current_world_ref": "finance",
            "current_thread_ref": "capital_hilton",
            "current_state": {"invoice_submitted": True, "coupa_processing": True, "payment_evidence_present": False, "paid": False},
        },
        {
            "objective_ref": "objective:finance:live_arts_md:payment_evidence",
            "current_world_ref": "finance",
            "current_thread_ref": "live_arts_md",
            "current_state": {"evidence_attached": True, "paid": False},
        },
        {
            "objective_ref": "objective:business_development:capital_hilton:followup",
            "current_world_ref": "business_development",
            "current_thread_ref": "capital_hilton",
        },
        {
            "objective_ref": "objective:build:review_packet",
            "current_world_ref": "build",
            "current_thread_ref": "review_packet",
            "requested_review_action": "mark_review_packet_informational",
        },
        {
            "objective_ref": "objective:finance:st_annes:work_log_review",
            "current_world_ref": "finance",
            "current_thread_ref": "st_annes",
        },
        {
            "objective_ref": "objective:unknown",
            "current_world_ref": "unknown",
            "current_thread_ref": "",
        },
    ]
    return [advance_objective(context, generated_at=generated_at) for context in contexts]


def build_protocol_read_model(
    *,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    preconditions = build_preconditions(read_model_root=read_model_root)
    ready = all(row["ready"] for row in preconditions)
    examples = _examples(generated_at)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "status": READY_STATUS if ready else NOT_READY_STATUS,
        "generated_at": generated_at,
        "purpose": "Define safe objective advancement for generic controller actions.",
        "controller_phrases": [
            "Continue",
            "Advance",
            "Prepare it",
            "Stage it",
            "Handle what you can",
            "What's missing?",
            "Next safe move",
        ],
        "core_doctrine": (
            "An objective-advance event advances the current goal to the next safe state, "
            "or explains the exact missing input, proof, or approval needed. It does not "
            "execute protected final actions."
        ),
        "definitions": {
            key: key
            for key in (
                "objective_ref",
                "current_state",
                "desired_outcome",
                "next_safe_state",
                "blocker",
                "missing_input",
                "proof_needed",
                "operator_question",
                "allowed_internal_advance",
                "protected_final_action",
                "final_approval_required",
                "class_a_approval_scope",
                "dynamic_card_ref",
                "receipt_requirement",
            )
        },
        "class_a_approval_scope": class_a_approval_scope(),
        "preconditions": preconditions,
        "examples": examples,
        "rules": [
            "Objective advancement must always return a dynamic card.",
            "Blocked cards explain the blocker in human language.",
            "Missing-proof cards say what proof counts.",
            "Approval-needed cards say what approval authorizes and does not authorize.",
            "Protected actions remain blocked.",
            "Generated summaries are not truth.",
            "Receipts, read models, and proof refs define truth.",
        ],
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "machine_proof": _machine_proof(
            {
                "all_examples_emit_dynamic_cards": all("dynamic_card" in item for item in examples),
                "class_a_never_grants_protected_actions": True,
                "mac_real_use_smoke_bridge_proof_accepted": any(
                    row["precondition_ref"] == "mac_controller_real_use_smoke" and row["ready"]
                    for row in preconditions
                ),
            }
        ),
    }
    payload["machine_proof"]["unsafe_true_grants"] = unsafe_true_grants(payload)
    payload["machine_proof"]["unsafe_true_grants_absent"] = not payload["machine_proof"]["unsafe_true_grants"]
    return payload


def build_wiki(read_model: Mapping[str, Any]) -> str:
    lines = [
        "# Objective Advancement Protocol",
        "",
        f"Status: `{read_model.get('status', NOT_READY_STATUS)}`",
        f"Generated: `{read_model.get('generated_at', '')}`",
        "",
        "Objective advancement is the backend meaning behind Continue, Advance, Prepare it, Stage it, Handle what you can, What's missing?, and Next safe move.",
        "",
        "It does not mean execute the final protected action. It means advance to the next safe internal state, or explain the missing input/proof/approval.",
        "",
        "## Class A Approval",
        "",
        "Class A approval may allow safe internal steps:",
    ]
    for item in read_model["class_a_approval_scope"]["may_allow"]:
        lines.append(f"- {item}")
    lines += ["", "Class A approval must not allow:"]
    for item in read_model["class_a_approval_scope"]["must_not_allow"]:
        lines.append(f"- {item}")
    lines += ["", "## Examples"]
    for example in read_model.get("examples", []):
        lines += [
            "",
            f"### {example.get('objective_ref', '')}",
            f"- Next safe state: `{example.get('next_safe_state', '')}`",
            f"- Response: {example.get('operator_response', '')}",
            f"- Next safe action: {example.get('dynamic_card', {}).get('next_safe_action', '')}",
            f"- Protected final action: `{example.get('protected_final_action', '')}`",
        ]
    lines += [
        "",
        "## Authority Boundary",
        "",
        "Email, Gmail/browser/Coupa, portal submit, ledger mutation, paid marking, workbook mutation, PDF export/send, git push/merge, worker spawn, external provider calls, external LLM calls, and local model runtime connections remain blocked.",
        "",
        f"Status: `{read_model.get('status', NOT_READY_STATUS)}`",
        "",
    ]
    return "\n".join(lines)


def _write_sqlite(sqlite_path: Path, read_model: Mapping[str, Any]) -> None:
    sqlite_path = _rooted(sqlite_path)
    sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(sqlite_path)
    try:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS objective_advancement_examples (
              objective_ref TEXT PRIMARY KEY,
              current_world_ref TEXT NOT NULL,
              current_thread_ref TEXT NOT NULL,
              next_safe_state TEXT NOT NULL,
              blocked INTEGER NOT NULL CHECK(blocked IN (0, 1)),
              protected_final_action TEXT NOT NULL,
              final_approval_required INTEGER NOT NULL CHECK(final_approval_required IN (0, 1)),
              dynamic_card_ref TEXT NOT NULL,
              receipt_requirement TEXT NOT NULL,
              generated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS objective_advancement_preconditions (
              precondition_ref TEXT PRIMARY KEY,
              source_ref TEXT NOT NULL,
              observed_status TEXT NOT NULL,
              ready INTEGER NOT NULL CHECK(ready IN (0, 1))
            );
            """
        )
        for example in read_model.get("examples", []):
            conn.execute(
                """
                INSERT OR REPLACE INTO objective_advancement_examples (
                  objective_ref, current_world_ref, current_thread_ref, next_safe_state,
                  blocked, protected_final_action, final_approval_required,
                  dynamic_card_ref, receipt_requirement, generated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    example["objective_ref"],
                    example["current_world_ref"],
                    example["current_thread_ref"],
                    example["next_safe_state"],
                    int(bool(example["blocked"])),
                    example["protected_final_action"],
                    int(bool(example["final_approval_required"])),
                    example["dynamic_card_ref"],
                    example["receipt_requirement"],
                    example["generated_at"],
                ),
            )
        for row in read_model.get("preconditions", []):
            conn.execute(
                """
                INSERT OR REPLACE INTO objective_advancement_preconditions (
                  precondition_ref, source_ref, observed_status, ready
                ) VALUES (?, ?, ?, ?)
                """,
                (
                    row["precondition_ref"],
                    row["source_ref"],
                    row["observed_status"],
                    int(bool(row["ready"])),
                ),
            )
        conn.commit()
    finally:
        conn.close()


def export_objective_advancement_protocol(
    *,
    export_root: Path = DEFAULT_EXPORT_ROOT,
    bridge_root: Path = DEFAULT_BRIDGE_ROOT,
    wiki_path: Path = DEFAULT_WIKI_PATH,
    sqlite_path: Path = DEFAULT_SQLITE_PATH,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
    generated_at: str | None = None,
) -> dict[str, str]:
    read_model = build_protocol_read_model(read_model_root=read_model_root, generated_at=generated_at)
    export_root = _rooted(export_root)
    bridge_root = bridge_root if bridge_root.is_absolute() else _rooted(bridge_root)
    wiki_path = _rooted(wiki_path)
    read_model_path = export_root / JSON_EXPORT_NAME
    bridge_path = bridge_root / JSON_EXPORT_NAME

    export_root.mkdir(parents=True, exist_ok=True)
    bridge_root.mkdir(parents=True, exist_ok=True)
    wiki_path.parent.mkdir(parents=True, exist_ok=True)

    read_model_path.write_text(stable_json(read_model), encoding="utf-8")
    shutil.copyfile(read_model_path, bridge_path)
    wiki_path.write_text(build_wiki(read_model), encoding="utf-8")
    _write_sqlite(sqlite_path, read_model)

    return {
        "status": str(read_model["status"]),
        "read_model_path": str(read_model_path),
        "bridge_read_model_path": str(bridge_path),
        "wiki_path": str(wiki_path),
        "sqlite_path": str(_rooted(sqlite_path)),
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Publish Objective Advancement Protocol V0.")
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT))
    parser.add_argument("--bridge-root", default=str(DEFAULT_BRIDGE_ROOT))
    parser.add_argument("--wiki-path", default=str(DEFAULT_WIKI_PATH))
    parser.add_argument("--sqlite-path", default=str(DEFAULT_SQLITE_PATH))
    parser.add_argument("--read-model-root", default=str(DEFAULT_READ_MODEL_ROOT))
    parser.add_argument("--generated-at", default=None)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    result = export_objective_advancement_protocol(
        export_root=Path(args.export_root),
        bridge_root=Path(args.bridge_root),
        wiki_path=Path(args.wiki_path),
        sqlite_path=Path(args.sqlite_path),
        read_model_root=Path(args.read_model_root),
        generated_at=args.generated_at,
    )
    print(stable_json(result), end="")
    return 0 if result["status"] == READY_STATUS else 1


if __name__ == "__main__":
    raise SystemExit(main())
