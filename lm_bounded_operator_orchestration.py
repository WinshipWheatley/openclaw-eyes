"""LM Bounded Operator Orchestration V0.

Contract/read-model layer for LM-shaped operator reasoning bounded by
deterministic OpenClaw action payloads. No live model is invoked. No providers
are connected. No workers, child agents, business actions, ledgers, workbooks,
Gmail, Coupa, browsers, PDFs, submits, mark-paid actions, pushes, or authority
grants occur here.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parent
DEFAULT_READ_MODEL_ROOT = Path("generated/read_models")
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_BRIDGE_ROOT = Path("/mnt/e/openclaw/generated/read_models")
DEFAULT_WIKI_PATH = Path("generated/wiki/openclaw/LM Bounded Operator Orchestration.md")

SCHEMA_VERSION = "lm_bounded_operator_orchestration_v0"
CONTRACT_READ_MODEL_ID = "lm_bounded_operator_orchestration_contract"
LATEST_READ_MODEL_ID = "lm_bounded_operator_orchestration_latest"
CONTRACT_JSON_EXPORT_NAME = f"{CONTRACT_READ_MODEL_ID}.json"
LATEST_JSON_EXPORT_NAME = f"{LATEST_READ_MODEL_ID}.json"
READY_STATUS = "LM_BOUNDED_OPERATOR_ORCHESTRATION_READY"
NOT_READY_STATUS = "LM_BOUNDED_OPERATOR_ORCHESTRATION_NOT_READY"
ORCHESTRATION_READY = "READY"
ORCHESTRATION_NOT_READY = "NOT_READY"
MODE = "contract_only_no_live_lm"

CAPITAL_HILTON_HUMAN_COPY = (
    "Coupa is already processing. Wait for payment proof before anything touches the ledger."
)

PRECONDITIONS = {
    "operator_action_payloads": {
        "filename": "operator_action_payloads.json",
        "required_status": "OPERATOR_ACTION_PAYLOADS_READY",
        "status_source": "top_level",
    },
    "workflow_composer": {
        "filename": "workflow_composer_latest.json",
        "required_status": "WORKFLOW_COMPOSER_READY",
        "status_source": "top_level",
    },
    "harness_provider_selection": {
        "filename": "harness_provider_selection_registry.json",
        "required_status": "HARNESS_PROVIDER_SELECTION_READY",
        "status_source": "top_level",
    },
    "evidence_confidence_scoring": {
        "filename": "evidence_confidence_scoring.json",
        "required_status": "EVIDENCE_CONFIDENCE_SCORING_READY",
        "status_source": "top_level",
    },
    "gate_decision_ledger": {
        "filename": "gate_decision_ledger.json",
        "required_status": "GATE_DECISION_LEDGER_READY",
        "status_source": "top_level",
    },
    "operator_next_decision_workrooms": {
        "filename": "track_a_workroom_backbone_status.json",
        "required_status": "OPERATOR_NEXT_DECISION_WORKROOMS_READY",
        "status_source": "phase",
        "phase": "operator_next_decision_workrooms",
    },
}

SOURCE_FILENAMES = {
    "operator_action_payloads": "operator_action_payloads.json",
    "operator_next_decision": "operator_next_decision.json",
    "workflow_composer": "workflow_composer_latest.json",
    "harness_provider_selection": "harness_provider_selection_registry.json",
    "evidence_confidence_scoring": "evidence_confidence_scoring.json",
    "gate_decision_ledger": "gate_decision_ledger.json",
    "capital_hilton_invoice_operator_run_status": "capital_hilton_invoice_operator_run_status.json",
    "capital_hilton_business_development_proposal": "capital_hilton_business_development_proposal.json",
    "workroom_wip_limits": "workroom_wip_limits.json",
    "openclaw_operating_picture": "openclaw_operating_picture_latest.json",
    "workroom_review_packet_index": "workroom_review_packet_index.json",
    "track_a_workroom_backbone": "track_a_workroom_backbone_status.json",
}

AUTHORITY_BOUNDARY = {
    "model_invocation_allowed": False,
    "external_llm_allowed": False,
    "external_provider_connect_allowed": False,
    "local_model_runtime_allowed": False,
    "provider_key_material_access_allowed": False,
    "codex_automation_allowed": False,
    "worker_spawn_allowed": False,
    "worker_execution_allowed": False,
    "child_agent_run_allowed": False,
    "agent_loop_allowed": False,
    "tool_execution_allowed": False,
    "email_send_allowed": False,
    "gmail_allowed": False,
    "calendar_write_allowed": False,
    "browser_access_allowed": False,
    "coupa_allowed": False,
    "portal_submit_allowed": False,
    "ledger_posting_allowed": False,
    "ledger_mutation_allowed": False,
    "workbook_open_allowed": False,
    "workbook_body_read_allowed": False,
    "spreadsheet_cell_read_allowed": False,
    "workbook_mutation_allowed": False,
    "workbook_source_mutation_allowed": False,
    "excel_automation_allowed": False,
    "pdf_export_allowed": False,
    "paid_marking_allowed": False,
    "payment_marking_allowed": False,
    "business_action_allowed": False,
    "authority_grant_allowed": False,
    "repair_authority_allowed": False,
    "credential_use_allowed": False,
    "merge_allowed": False,
    "git_push_allowed": False,
    "push_allowed": False,
    "sent": False,
    "paid": False,
}

UNSAFE_TRUE_KEYS = set(AUTHORITY_BOUNDARY) | {
    "model_invoked",
    "model_runtime_connected",
    "external_provider_connected",
    "local_model_runtime_connected",
    "codex_automation_run",
    "tool_execution_performed",
    "email_send_performed",
    "gmail_access_performed",
    "calendar_write_performed",
    "browser_access_performed",
    "coupa_access_performed",
    "coupa_submit_performed",
    "portal_submit_performed",
    "ledger_posting_performed",
    "ledger_mutation_performed",
    "workbook_open_performed",
    "workbook_body_read_performed",
    "spreadsheet_cell_read_performed",
    "workbook_mutation_performed",
    "workbook_source_mutation_performed",
    "excel_automation_performed",
    "pdf_export_performed",
    "paid_marking_performed",
    "payment_marking_performed",
    "mark_paid_performed",
    "submit_performed",
    "business_action_performed",
    "authority_grant_performed",
    "repair_performed",
    "worker_spawn_performed",
    "worker_execution_performed",
    "child_agent_run_performed",
    "agent_loop_started",
    "merge_performed",
    "git_push_performed",
    "push_performed",
}

TERMINAL_REVIEW_STATUSES = {
    "OPERATOR_REVIEW_RECORDED",
    "INFORMATIONAL_REVIEW_CLOSED",
    "REWORK_REQUEST_RECORDED",
    "REVIEW_PACKET_CANCELLED",
    "COMPLETED",
    "CLOSED",
    "RESOLVED",
}

SCENARIO_ACTIONS = {
    "capital_hilton_payment_watch": (
        "capital_hilton.payment.open_finance",
        "capital_hilton.payment.record_proof",
        "helm_question.safe_next.ask",
    ),
    "check_engine_diagnostic": (
        "chief_diagnostic.open",
        "helm_question.hardwired_vs_spawned.ask",
    ),
    "business_development_followup": (
        "capital_hilton.proposal.stage_followup",
        "helm_question.safe_next.ask",
    ),
    "workbook_registration": (
        "client_invoice_workbook.register",
        "guardian_gate.workbook_mutation.explain",
    ),
    "workroom_review": (
        "helm_question.safe_next.ask",
    ),
    "needs_verification": (
        "helm_question.safe_next.ask",
        "helm_question.hardwired_vs_spawned.ask",
    ),
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


def _short_hash(*parts: object) -> str:
    return hashlib.sha256("\0".join(str(part) for part in parts).encode("utf-8")).hexdigest()[:12]


def _slug(value: object) -> str:
    text = str(value or "").strip().lower()
    cleaned = "".join(char if char.isalnum() else "_" for char in text).strip("_")
    return cleaned or "orchestration"


def _status(payload: Mapping[str, Any]) -> str:
    return str(payload.get("status") or payload.get("readiness_status") or payload.get("contract_status") or "")


def _observed_status(payload: Mapping[str, Any], spec: Mapping[str, Any]) -> str:
    if spec.get("status_source") == "phase":
        phase_ref = str(spec.get("phase") or "")
        for phase in payload.get("phases") or []:
            if isinstance(phase, Mapping) and str(phase.get("phase") or "") == phase_ref:
                return str(phase.get("status") or "")
        return ""
    return _status(payload)


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


def build_preconditions(read_model_root: Path = DEFAULT_READ_MODEL_ROOT) -> list[dict[str, Any]]:
    root = _rooted(read_model_root)
    rows: list[dict[str, Any]] = []
    for ref, spec in PRECONDITIONS.items():
        payload = _load_json(root / str(spec["filename"]))
        observed = _observed_status(payload, spec)
        required = str(spec["required_status"])
        source_ref = f"generated/read_models/{spec['filename']}"
        if spec.get("status_source") == "phase":
            source_ref += f"#phases.{spec.get('phase')}"
        rows.append(
            {
                "precondition_ref": ref,
                "required_status": required,
                "observed_status": observed,
                "ready": observed == required,
                "source_ref": source_ref,
            }
        )
    return rows


def _load_sources(read_model_root: Path) -> dict[str, dict[str, Any]]:
    root = _rooted(read_model_root)
    return {ref: _load_json(root / filename) for ref, filename in SOURCE_FILENAMES.items()}


def _action_payloads(sources: Mapping[str, Mapping[str, Any]]) -> list[dict[str, Any]]:
    payload = sources.get("operator_action_payloads") or {}
    return [dict(item) for item in payload.get("action_payloads") or [] if isinstance(item, Mapping)]


def _action_index(actions: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(action.get("action_id") or ""): action for action in actions if action.get("action_id")}


def _nested_authority(action: Mapping[str, Any]) -> dict[str, Any]:
    boundary: dict[str, Any] = {}
    if isinstance(action.get("authority_boundary"), Mapping):
        boundary.update(action["authority_boundary"])
    payload = action.get("payload")
    if isinstance(payload, Mapping) and isinstance(payload.get("authority_boundary"), Mapping):
        boundary.update(payload["authority_boundary"])
    return boundary


def _action_unsafe_true_keys(action: Mapping[str, Any]) -> list[str]:
    keys: set[str] = set()
    for key, value in _walk_values(action):
        if key in UNSAFE_TRUE_KEYS and value is True:
            keys.add(key)
    return sorted(keys)


def _proof_refs(action: Mapping[str, Any]) -> list[str]:
    refs = action.get("proof_refs")
    if isinstance(refs, list):
        return [str(ref) for ref in refs if str(ref)]
    return []


def _action_summary(action: Mapping[str, Any], *, relevance: str = "available") -> dict[str, Any]:
    authority = _nested_authority(action)
    unsafe = _action_unsafe_true_keys(action)
    return {
        "action_id": str(action.get("action_id") or ""),
        "label": str(action.get("label") or ""),
        "action_type": str(action.get("action_type") or ""),
        "target_world_ref": str(action.get("target_world_ref") or ""),
        "target_thread_ref": str(action.get("target_thread_ref") or ""),
        "enabled": action.get("enabled") is True,
        "disabled_reason": action.get("disabled_reason"),
        "business_action": action.get("business_action") is True,
        "safe_to_render_button": action.get("safe_to_render_button") is True,
        "safe_to_choose": (
            action.get("enabled") is True
            and action.get("safe_to_render_button") is True
            and action.get("business_action") is not True
            and not unsafe
        ),
        "relevance": relevance,
        "proof_refs": _proof_refs(action),
        "authority_boundary_valid": all(
            authority.get(key) is not True for key in UNSAFE_TRUE_KEYS if key in authority
        )
        and not unsafe,
    }


def _action_snapshot(action: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "action_id": str(action.get("action_id") or ""),
        "label": str(action.get("label") or ""),
        "action_type": str(action.get("action_type") or ""),
        "target_world_ref": str(action.get("target_world_ref") or ""),
        "target_thread_ref": str(action.get("target_thread_ref") or ""),
        "enabled": action.get("enabled") is True,
        "disabled_reason": action.get("disabled_reason"),
        "business_action": action.get("business_action") is True,
        "safe_to_render_button": action.get("safe_to_render_button") is True,
        "payload": action.get("payload") if isinstance(action.get("payload"), Mapping) else {},
        "proof_refs": _proof_refs(action),
        "authority_boundary": dict(action.get("authority_boundary") or {}),
    }


def validate_lm_recommendation(
    proposal: Mapping[str, Any],
    action_payloads: list[dict[str, Any]],
    *,
    require_enabled: bool = True,
) -> dict[str, Any]:
    """Validate an LM-shaped proposal against deterministic action payloads."""

    action_id = str(proposal.get("action_id") or "")
    index = _action_index(action_payloads)
    action = index.get(action_id)
    reject_reasons: list[str] = []
    unsafe: list[str] = []
    exists = action is not None
    enabled = False
    renderable = False
    business_safe = True

    if not exists:
        reject_reasons.append("unknown_action_payload")
    else:
        enabled = action.get("enabled") is True
        renderable = action.get("safe_to_render_button") is True
        business_safe = action.get("business_action") is not True
        unsafe = _action_unsafe_true_keys(action)
        if require_enabled and not enabled:
            reject_reasons.append("action_payload_disabled")
        if not renderable:
            reject_reasons.append("not_safe_to_render_button")
        if not business_safe:
            reject_reasons.append("business_action_not_allowed")
        if unsafe:
            reject_reasons.append("unsafe_authority_true")

    valid = exists and business_safe and not unsafe and renderable and (enabled or not require_enabled)
    return {
        "proposal_action_id": action_id,
        "selected_action_exists_in_payloads": exists,
        "action_payload_enabled": enabled,
        "safe_to_render_button": renderable,
        "business_action_blocked": business_safe or not exists,
        "authority_boundary_valid": exists and not unsafe,
        "proof_refs": _proof_refs(action) if action else [],
        "unsafe_true_keys": unsafe,
        "reject_reasons": reject_reasons,
        "valid": valid,
        "deterministic_rejection": not valid,
        "new_business_action_introduced": not exists or not business_safe,
        "authority_created": False,
        "operator_approval_still_required": True,
    }


def _confidence_for_fact(sources: Mapping[str, Mapping[str, Any]], fact_ref: str, fallback: float) -> float:
    evidence = sources.get("evidence_confidence_scoring") or {}
    for fact in evidence.get("facts") or evidence.get("scored_facts") or []:
        if isinstance(fact, Mapping) and str(fact.get("fact_ref") or "") == fact_ref:
            try:
                return float(fact.get("confidence_score"))
            except (TypeError, ValueError):
                return fallback
    return fallback


def _capital_hilton_processing(sources: Mapping[str, Mapping[str, Any]]) -> bool:
    receipt = sources.get("capital_hilton_invoice_operator_run_status") or {}
    submitted = receipt.get("coupa_submitted") is True or receipt.get("coupa_submission_recorded") is True
    status_text = " ".join(
        str(receipt.get(key) or "")
        for key in ("coupa_submission_status", "coupa_status_observed", "source_receipt_status")
    ).lower()
    return submitted and ("processing" in status_text or "submitted" in status_text)


def _capital_hilton_payment_evidence_missing(sources: Mapping[str, Mapping[str, Any]]) -> bool:
    receipt = sources.get("capital_hilton_invoice_operator_run_status") or {}
    return not (receipt.get("payment_received_recorded") is True or receipt.get("paid") is True)


def _review_packet_open_action_id(packet_id: str) -> str:
    normalized = "".join(char if char.isalnum() else "_" for char in packet_id).strip("_")
    return f"review_packet.{normalized}.open"


def _packet_status(packet: Mapping[str, Any]) -> str:
    return str(packet.get("status") or packet.get("review_decision_status") or "").upper()


def _packet_unresolved(packet: Mapping[str, Any]) -> bool:
    if packet.get("completed") is True:
        return False
    status = _packet_status(packet)
    if status in TERMINAL_REVIEW_STATUSES:
        return False
    return packet.get("operator_decision_required") is True or status in {
        "REVIEW_PACKET_READY",
        "READY_FOR_OPERATOR_REVIEW",
        "WAITING_FOR_OPERATOR_REVIEW",
    }


def _find_packet(
    sources: Mapping[str, Mapping[str, Any]],
    *,
    target_review_packet_id: str | None = None,
) -> dict[str, Any] | None:
    packet_index = sources.get("workroom_review_packet_index") or {}
    packets = [dict(packet) for packet in packet_index.get("packets") or [] if isinstance(packet, Mapping)]
    if target_review_packet_id:
        for packet in packets:
            if str(packet.get("review_packet_id") or packet.get("package_id") or "") == target_review_packet_id:
                return packet
    for packet in packets:
        if _packet_unresolved(packet):
            return packet
    return packets[0] if packets else None


def _rejected_action(
    *,
    action_id: str,
    label: str,
    rejection_reason: str,
    proof_refs: tuple[str, ...] = (),
    deterministic_rule: str = "bounded_orchestration_validator",
) -> dict[str, Any]:
    return {
        "action_id": action_id,
        "label": label,
        "rejection_reason": rejection_reason,
        "deterministic_rule": deterministic_rule,
        "proof_refs": list(proof_refs),
        "authority_created": False,
        "business_action_performed": False,
    }


def _scenario_proposals(
    *,
    scenario_ref: str,
    sources: Mapping[str, Mapping[str, Any]],
    target_review_packet_id: str | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], str]:
    proposals: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    display_copy = "Needs verification. Ask Chief/Hermes to clarify the safest deterministic action before staging work."

    if scenario_ref == "capital_hilton_payment_watch":
        if _capital_hilton_processing(sources):
            proposals.append(
                {
                    "action_id": "capital_hilton.payment.open_finance",
                    "confidence_score": _confidence_for_fact(
                        sources,
                        "fact:capital_hilton_invoice_processing",
                        0.75,
                    ),
                    "rationale": "Receipt says the Capital Hilton Coupa submission is already submitted/processing.",
                    "human_copy": CAPITAL_HILTON_HUMAN_COPY,
                }
            )
            rejected.append(
                _rejected_action(
                    action_id="capital_hilton.coupa.start_proof_step",
                    label="Start Coupa proof step",
                    rejection_reason="contradicts_submitted_processing_receipt",
                    proof_refs=("generated/read_models/capital_hilton_invoice_operator_run_status.json",),
                    deterministic_rule="submitted_processing_receipt_blocks_restart",
                )
            )
            if _capital_hilton_payment_evidence_missing(sources):
                rejected.append(
                    _rejected_action(
                        action_id="capital_hilton.payment.record_proof",
                        label="Record payment proof",
                        rejection_reason="disabled_until_payment_evidence_exists",
                        proof_refs=("generated/read_models/capital_hilton_invoice_operator_run_status.json",),
                        deterministic_rule="payment_proof_required_before_ledger_touch",
                    )
                )
            display_copy = CAPITAL_HILTON_HUMAN_COPY
        else:
            proposals.append(
                {
                    "action_id": "helm_question.safe_next.ask",
                    "confidence_score": 0.4,
                    "rationale": "Capital Hilton state needs verification before choosing a finance action.",
                    "human_copy": display_copy,
                }
            )
    elif scenario_ref == "check_engine_diagnostic":
        proposals.append(
            {
                "action_id": "chief_diagnostic.open",
                "confidence_score": 0.8,
                "rationale": "Check Engine is a diagnostic/navigation outcome; it has no repair authority.",
                "human_copy": "Open Chief diagnostic explanation. Do not repair anything from this route.",
            }
        )
    elif scenario_ref == "business_development_followup":
        proposals.append(
            {
                "action_id": "capital_hilton.proposal.stage_followup",
                "confidence_score": 0.7,
                "rationale": "The Capital Hilton proposal lane can stage an internal Cassandra/Clara follow-up packet only.",
                "human_copy": "Stage a proposal follow-up packet for review only. Do not send.",
            }
        )
    elif scenario_ref == "workbook_registration":
        proposals.append(
            {
                "action_id": "client_invoice_workbook.register",
                "confidence_score": 0.7,
                "rationale": "Workbook chooser may register a selected local path; it may not read workbook cells or mutate the workbook.",
                "human_copy": "Register the workbook path only. Do not read the workbook body or change cells.",
            }
        )
    elif scenario_ref == "workroom_review":
        packet = _find_packet(sources, target_review_packet_id=target_review_packet_id)
        if packet:
            packet_id = str(packet.get("review_packet_id") or packet.get("package_id") or "")
            action_id = _review_packet_open_action_id(packet_id)
            if _packet_unresolved(packet):
                proposals.append(
                    {
                        "action_id": action_id,
                        "confidence_score": 0.65,
                        "rationale": "The review packet is unresolved and still requires operator review.",
                        "human_copy": "Open the unresolved review packet. Do not merge, push, or execute workers.",
                    }
                )
            else:
                rejected.append(
                    _rejected_action(
                        action_id=action_id,
                        label="Open resolved review packet",
                        rejection_reason="resolved_or_closed_review_packet",
                        proof_refs=("generated/read_models/workroom_review_packet_index.json",),
                        deterministic_rule="terminal_review_packets_are_not_recommended",
                    )
                )
                proposals.append(
                    {
                        "action_id": "helm_question.safe_next.ask",
                        "confidence_score": 0.45,
                        "rationale": "The requested review packet is resolved or closed; ask for the next safe workroom action instead.",
                        "human_copy": display_copy,
                    }
                )
        else:
            proposals.append(
                {
                    "action_id": "helm_question.safe_next.ask",
                    "confidence_score": 0.4,
                    "rationale": "No review packet is available in the deterministic index.",
                    "human_copy": display_copy,
                }
            )
    else:
        proposals.append(
            {
                "action_id": "helm_question.safe_next.ask",
                "confidence_score": 0.4,
                "rationale": "Candidates conflict or are ambiguous; ask Chief/Hermes before choosing.",
                "human_copy": display_copy,
            }
        )
    return proposals, rejected, display_copy


def _select_valid_proposal(
    proposals: list[dict[str, Any]],
    action_payloads: list[dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    ranked = sorted(proposals, key=lambda item: float(item.get("confidence_score") or 0), reverse=True)
    deterministic_rejections: list[dict[str, Any]] = []
    for proposal in ranked:
        validation = validate_lm_recommendation(proposal, action_payloads)
        if validation["valid"]:
            return proposal, validation, deterministic_rejections
        deterministic_rejections.append(
            _rejected_action(
                action_id=str(proposal.get("action_id") or ""),
                label=str(proposal.get("label") or proposal.get("action_id") or ""),
                rejection_reason=";".join(validation["reject_reasons"]) or "deterministic_validation_failed",
                proof_refs=tuple(validation.get("proof_refs") or ()),
                deterministic_rule="proposal_must_match_allowed_action_payload",
            )
        )
    fallback = {"action_id": "", "confidence_score": 0.0, "rationale": "No safe deterministic action was available."}
    return fallback, validate_lm_recommendation(fallback, action_payloads), deterministic_rejections


def _candidate_action_ids(
    *,
    scenario_ref: str,
    sources: Mapping[str, Mapping[str, Any]],
    target_review_packet_id: str | None = None,
) -> set[str]:
    action_ids = set(SCENARIO_ACTIONS.get(scenario_ref, SCENARIO_ACTIONS["needs_verification"]))
    if scenario_ref == "workroom_review":
        packet = _find_packet(sources, target_review_packet_id=target_review_packet_id)
        if packet:
            packet_id = str(packet.get("review_packet_id") or packet.get("package_id") or "")
            action_ids.add(_review_packet_open_action_id(packet_id))
    return action_ids


def build_current_state_summary(
    *,
    sources: Mapping[str, Mapping[str, Any]],
    scenario_ref: str,
    target_review_packet_id: str | None = None,
) -> dict[str, Any]:
    invoice = sources.get("capital_hilton_invoice_operator_run_status") or {}
    business_proposal = sources.get("capital_hilton_business_development_proposal") or {}
    workroom_wip = sources.get("workroom_wip_limits") or {}
    packet = _find_packet(sources, target_review_packet_id=target_review_packet_id)
    payment_evidence_missing = _capital_hilton_payment_evidence_missing(sources)
    return {
        "scenario_ref": scenario_ref,
        "capital_hilton": {
            "coupa_submitted": invoice.get("coupa_submitted") is True
            or invoice.get("coupa_submission_recorded") is True,
            "coupa_submission_status": str(
                invoice.get("coupa_submission_status") or invoice.get("coupa_status_observed") or ""
            ),
            "coupa_processing_receipt_present": _capital_hilton_processing(sources),
            "payment_evidence_missing": payment_evidence_missing,
            "paid_truth": "unknown_until_payment_evidence" if payment_evidence_missing else "payment_evidence_recorded",
            "ledger_touch_allowed": False,
        },
        "business_development": {
            "client_ref": str(business_proposal.get("client_ref") or "capital_hilton"),
            "client_review_pending": business_proposal.get("client_review_pending") is True,
            "send_authority_available": False,
            "finance_handoff_allowed": False,
        },
        "workroom": {
            "global_wip_status": str(workroom_wip.get("chief_recommendation") or ""),
            "target_review_packet_id": str(
                (packet or {}).get("review_packet_id")
                or (packet or {}).get("package_id")
                or target_review_packet_id
                or ""
            ),
            "target_review_packet_status": _packet_status(packet or {}),
            "target_review_packet_unresolved": _packet_unresolved(packet or {}) if packet else False,
        },
        "truth_policy": {
            "receipts_are_canonical": True,
            "lm_output_is_non_authoritative": True,
            "deterministic_payloads_are_only_selectable_actions": True,
        },
    }


def build_orchestration(
    *,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
    scenario_ref: str = "capital_hilton_payment_watch",
    target_review_packet_id: str | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    sources = _load_sources(read_model_root)
    actions = _action_payloads(sources)
    action_index = _action_index(actions)
    preconditions = build_preconditions(read_model_root)
    preconditions_ready = all(row["ready"] for row in preconditions)
    scenario_candidate_ids = _candidate_action_ids(
        scenario_ref=scenario_ref,
        sources=sources,
        target_review_packet_id=target_review_packet_id,
    )

    proposals, rejected, display_copy = _scenario_proposals(
        scenario_ref=scenario_ref,
        sources=sources,
        target_review_packet_id=target_review_packet_id,
    )
    selected_proposal, validation, deterministic_rejections = _select_valid_proposal(proposals, actions)
    rejected.extend(deterministic_rejections)
    selected_action = action_index.get(str(selected_proposal.get("action_id") or ""), {})

    candidate_actions = [
        _action_summary(
            action,
            relevance="scenario_candidate" if str(action.get("action_id") or "") in scenario_candidate_ids else "available",
        )
        for action in actions
    ]
    selected_action_id = str(selected_proposal.get("action_id") or "")
    selected_label = str(selected_action.get("label") or selected_action_id or "Needs verification")
    human_copy = str(selected_proposal.get("human_copy") or display_copy)
    orchestration_id = (
        f"lm_bounded_orchestration:{_slug(scenario_ref)}:"
        f"{_short_hash(generated_at, scenario_ref, selected_action_id, target_review_packet_id)}"
    )
    action_snapshot = _action_snapshot(selected_action) if selected_action else {}

    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": LATEST_READ_MODEL_ID,
        "status": ORCHESTRATION_READY if preconditions_ready else ORCHESTRATION_NOT_READY,
        "readiness_status": READY_STATUS if preconditions_ready else NOT_READY_STATUS,
        "mode": MODE,
        "orchestration_id": orchestration_id,
        "generated_at": generated_at,
        "current_state_summary": build_current_state_summary(
            sources=sources,
            scenario_ref=scenario_ref,
            target_review_packet_id=target_review_packet_id,
        ),
        "candidate_actions": candidate_actions,
        "candidate_action_count": len(candidate_actions),
        "candidate_source_ref": "generated/read_models/operator_action_payloads.json",
        "selection_policy": "highest_confidence_safe_action_after_deterministic_validation",
        "lm_recommended_action": {
            "action_id": selected_action_id,
            "label": selected_label,
            "action_type": str(selected_action.get("action_type") or ""),
            "target_world_ref": str(selected_action.get("target_world_ref") or ""),
            "target_thread_ref": str(selected_action.get("target_thread_ref") or ""),
            "confidence_score": float(selected_proposal.get("confidence_score") or 0),
            "rationale": str(selected_proposal.get("rationale") or ""),
            "human_copy": human_copy,
            "action_payload": action_snapshot,
            "proof_refs": _proof_refs(selected_action) if selected_action else [],
            "safe_to_execute_now": False,
            "operator_approval_required_before_execution": True,
            "provider_choice_grants_authority": False,
            "business_action": selected_action.get("business_action") is True if selected_action else False,
        },
        "rejected_actions": rejected,
        "deterministic_validation": {
            **validation,
            "selected_action_id": selected_action_id,
            "selected_action_allowed": validation["valid"],
            "lm_may_only_choose_existing_payload": True,
            "validator_rejects_unknown_payloads": True,
            "receipts_are_canonical_truth": True,
            "guardian_gates_remain_protected": True,
            "safe_to_execute": False,
        },
        "operator_display": {
            "headline": _operator_headline(scenario_ref, selected_label),
            "human_copy": human_copy,
            "primary_action_id": selected_action_id,
            "primary_button_label": selected_label,
            "warning_lines": [
                "This is not a worker run.",
                "This does not grant authority.",
                "Protected business actions still require separate approval.",
            ],
            "needs_verification": not validation["valid"] or selected_action_id == "helm_question.safe_next.ask",
        },
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "lm_capability_boundary": {
            "permitted_operations": [
                "interpret_operator_goal",
                "rank_existing_action_payloads",
                "summarize_human_meaning",
                "compose_operator_display_copy",
            ],
            "forbidden_operations": [
                "invent_action_payload",
                "grant_authority",
                "perform_business_action",
                "invoke_live_model_runtime",
                "connect_external_provider",
                "spawn_worker_or_child_agent",
            ],
        },
        "source_refs": [
            f"generated/read_models/{filename}" for filename in SOURCE_FILENAMES.values()
        ],
        "preconditions": preconditions,
        "machine_proof": {
            "preconditions_ready": preconditions_ready,
            "contract_only_no_live_lm": True,
            "model_invoked": False,
            "model_runtime_connected": False,
            "external_provider_connected": False,
            "local_model_runtime_connected": False,
            "selected_action_exists_in_payloads": validation["selected_action_exists_in_payloads"],
            "selected_action_allowed": validation["valid"],
            "authority_created": False,
            "provider_choice_grants_authority": False,
            "email_send_performed": False,
            "gmail_access_performed": False,
            "calendar_write_performed": False,
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
            "workbook_source_mutation_performed": False,
            "excel_automation_performed": False,
            "pdf_export_performed": False,
            "paid_marking_performed": False,
            "payment_marking_performed": False,
            "mark_paid_performed": False,
            "submit_performed": False,
            "business_action_performed": False,
            "authority_grant_performed": False,
            "repair_performed": False,
            "worker_spawn_performed": False,
            "worker_execution_performed": False,
            "child_agent_run_performed": False,
            "agent_loop_started": False,
            "merge_performed": False,
            "git_push_performed": False,
            "push_performed": False,
            "unsafe_true_grants": [],
            "unsafe_true_grants_absent": True,
        },
    }
    unsafe = unsafe_true_grants(payload)
    payload["machine_proof"]["unsafe_true_grants"] = unsafe
    payload["machine_proof"]["unsafe_true_grants_absent"] = not unsafe
    return payload


def _operator_headline(scenario_ref: str, selected_label: str) -> str:
    if scenario_ref == "capital_hilton_payment_watch":
        return "Capital Hilton payment watch"
    if scenario_ref == "check_engine_diagnostic":
        return "Chief diagnostic only"
    if scenario_ref == "business_development_followup":
        return "Capital Hilton proposal follow-up"
    if scenario_ref == "workbook_registration":
        return "Workbook registration only"
    if scenario_ref == "workroom_review":
        return "Workroom review packet"
    return selected_label or "Needs verification"


def build_contract_read_model(
    *,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    preconditions = build_preconditions(read_model_root)
    preconditions_ready = all(row["ready"] for row in preconditions)
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": CONTRACT_READ_MODEL_ID,
        "status": READY_STATUS if preconditions_ready else NOT_READY_STATUS,
        "contract_status": ORCHESTRATION_READY if preconditions_ready else ORCHESTRATION_NOT_READY,
        "mode": MODE,
        "generated_at": generated_at,
        "purpose": "Bound LM-shaped operator reasoning to deterministic OpenClaw action payloads without granting authority.",
        "preconditions": preconditions,
        "input_refs": [f"generated/read_models/{filename}" for filename in SOURCE_FILENAMES.values()],
        "output_contract": {
            "required_fields": [
                "schema_version",
                "status",
                "mode",
                "current_state_summary",
                "candidate_actions",
                "lm_recommended_action",
                "rejected_actions",
                "deterministic_validation",
                "operator_display",
            ],
            "status_value_when_ready": ORCHESTRATION_READY,
            "mode_value": MODE,
        },
        "doctrine": [
            "LMs may interpret, rank, summarize, and compose operator-facing copy.",
            "LMs may only choose from deterministic action payloads.",
            "The deterministic validator rejects any proposal not present in operator_action_payloads.",
            "Provider/harness choice does not grant authority.",
            "Receipts and read models remain canonical truth.",
            "Guardian gates protect send, Coupa, ledger, workbook, PDF, paid, submit, repair, and worker actions.",
        ],
        "required_behavior": [
            "Capital Hilton submitted/processing rejects Start Coupa proof step and recommends payment watch.",
            "Check Engine routes to Chief diagnostic explanation/navigation with no repair authority.",
            "Workroom packets are recommended only while unresolved.",
            "Business Development follow-up may stage a packet only and cannot send.",
            "Workbook chooser may register a workbook path only and cannot read or mutate workbook body.",
            "Ambiguous conflicts choose the highest-confidence safe action or ask Chief/Hermes for verification.",
        ],
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "machine_proof": {
            "preconditions_ready": preconditions_ready,
            "contract_only": True,
            "model_invoked": False,
            "external_provider_connected": False,
            "local_model_runtime_connected": False,
            "authority_created": False,
            "business_action_performed": False,
            "worker_spawn_performed": False,
            "worker_execution_performed": False,
            "child_agent_run_performed": False,
            "unsafe_true_grants": [],
            "unsafe_true_grants_absent": True,
        },
    }
    unsafe = unsafe_true_grants(payload)
    payload["machine_proof"]["unsafe_true_grants"] = unsafe
    payload["machine_proof"]["unsafe_true_grants_absent"] = not unsafe
    return payload


def build_latest_read_model(
    *,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    latest = build_orchestration(
        read_model_root=read_model_root,
        scenario_ref="capital_hilton_payment_watch",
        generated_at=generated_at,
    )
    scenario_payloads = {
        scenario_ref: build_orchestration(
            read_model_root=read_model_root,
            scenario_ref=scenario_ref,
            generated_at=generated_at,
        )
        for scenario_ref in (
            "check_engine_diagnostic",
            "business_development_followup",
            "workbook_registration",
            "workroom_review",
        )
    }
    scenarios = {
        scenario_ref: _scenario_digest(payload)
        for scenario_ref, payload in scenario_payloads.items()
    }
    latest["contract_ref"] = f"generated/read_models/{CONTRACT_JSON_EXPORT_NAME}"
    latest["scenario_orchestrations"] = scenarios
    latest["scenario_orchestration_count"] = len(scenarios)
    unsafe = unsafe_true_grants(latest)
    latest["machine_proof"]["unsafe_true_grants"] = unsafe
    latest["machine_proof"]["unsafe_true_grants_absent"] = not unsafe
    latest["machine_proof"]["scenario_count"] = len(scenarios)
    return latest


def _scenario_digest(payload: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "scenario_ref": str(
            (payload.get("current_state_summary") or {}).get("scenario_ref")
            if isinstance(payload.get("current_state_summary"), Mapping)
            else ""
        ),
        "status": str(payload.get("status") or ""),
        "mode": str(payload.get("mode") or ""),
        "current_state_summary": payload.get("current_state_summary") or {},
        "lm_recommended_action": payload.get("lm_recommended_action") or {},
        "rejected_actions": payload.get("rejected_actions") or [],
        "deterministic_validation": payload.get("deterministic_validation") or {},
        "operator_display": payload.get("operator_display") or {},
    }


def build_wiki(contract: Mapping[str, Any], latest: Mapping[str, Any]) -> str:
    recommended = latest.get("lm_recommended_action") if isinstance(latest.get("lm_recommended_action"), Mapping) else {}
    validation = latest.get("deterministic_validation") if isinstance(latest.get("deterministic_validation"), Mapping) else {}
    lines = [
        "# LM Bounded Operator Orchestration",
        "",
        f"Status: `{latest.get('readiness_status', NOT_READY_STATUS)}`",
        f"Mode: `{latest.get('mode', MODE)}`",
        "",
        "This read-model lets LM-shaped operator reasoning interpret, rank, summarize, and compose while remaining bounded by deterministic OpenClaw action payloads. No live LM is invoked.",
        "",
        "## Current Recommendation",
        "",
        f"- Action: `{recommended.get('action_id', '')}`",
        f"- Label: {recommended.get('label', '')}",
        f"- Human copy: {recommended.get('human_copy', '')}",
        f"- Deterministic validation: `{str(validation.get('valid')).lower()}`",
        "",
        "## Deterministic Boundary",
        "",
        "- The selected action must already exist in `generated/read_models/operator_action_payloads.json`.",
        "- Unknown proposals are rejected.",
        "- Disabled, unsafe, or business-action payloads are rejected.",
        "- Receipts and read models remain canonical truth.",
        "- Guardian gates remain protected.",
        "",
        "## Scenario Coverage",
        "",
    ]
    for scenario_ref, scenario in (latest.get("scenario_orchestrations") or {}).items():
        if not isinstance(scenario, Mapping):
            continue
        action = scenario.get("lm_recommended_action") if isinstance(scenario.get("lm_recommended_action"), Mapping) else {}
        lines.extend(
            [
                f"- `{scenario_ref}` -> `{action.get('action_id', '')}`",
            ]
        )
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            "- No model invocation.",
            "- No external provider connection.",
            "- No email, Gmail, browser, Coupa, ledger, workbook body read/mutation, PDF export, submit, mark-paid, repair, merge, push, worker, child-agent, or agent-loop authority.",
            "- Provider choice and action recommendation do not grant authority.",
            "",
            "## Contract",
            "",
            f"- Contract read-model: `generated/read_models/{CONTRACT_JSON_EXPORT_NAME}`",
            f"- Latest read-model: `generated/read_models/{LATEST_JSON_EXPORT_NAME}`",
            f"- Preconditions ready: `{str(contract.get('machine_proof', {}).get('preconditions_ready')).lower()}`",
        ]
    )
    return "\n".join(lines) + "\n"


def export_lm_bounded_operator_orchestration(
    *,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
    export_root: Path = DEFAULT_EXPORT_ROOT,
    bridge_root: Path | None = DEFAULT_BRIDGE_ROOT,
    wiki_path: Path = DEFAULT_WIKI_PATH,
    generated_at: str | None = None,
) -> dict[str, str]:
    generated_at = generated_at or utc_now()
    contract = build_contract_read_model(read_model_root=read_model_root, generated_at=generated_at)
    latest = build_latest_read_model(read_model_root=read_model_root, generated_at=generated_at)

    export_root = _rooted(export_root)
    export_root.mkdir(parents=True, exist_ok=True)
    contract_path = export_root / CONTRACT_JSON_EXPORT_NAME
    latest_path = export_root / LATEST_JSON_EXPORT_NAME
    contract_path.write_text(stable_json(contract), encoding="utf-8")
    latest_path.write_text(stable_json(latest), encoding="utf-8")

    bridge_contract_path = ""
    bridge_latest_path = ""
    if bridge_root is not None:
        bridge_root.mkdir(parents=True, exist_ok=True)
        bridge_contract = bridge_root / CONTRACT_JSON_EXPORT_NAME
        bridge_latest = bridge_root / LATEST_JSON_EXPORT_NAME
        shutil.copy2(contract_path, bridge_contract)
        shutil.copy2(latest_path, bridge_latest)
        bridge_contract_path = bridge_contract.as_posix()
        bridge_latest_path = bridge_latest.as_posix()

    wiki_path = _rooted(wiki_path)
    wiki_path.parent.mkdir(parents=True, exist_ok=True)
    wiki_path.write_text(build_wiki(contract, latest), encoding="utf-8")

    return {
        "status": str(latest["readiness_status"]),
        "contract_path": contract_path.as_posix(),
        "latest_path": latest_path.as_posix(),
        "bridge_contract_path": bridge_contract_path,
        "bridge_latest_path": bridge_latest_path,
        "wiki_path": wiki_path.as_posix(),
        "candidate_action_count": str(latest["candidate_action_count"]),
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Publish LM Bounded Operator Orchestration V0.")
    parser.add_argument("--read-model-root", default=str(DEFAULT_READ_MODEL_ROOT))
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT))
    parser.add_argument("--bridge-root", default=str(DEFAULT_BRIDGE_ROOT))
    parser.add_argument("--wiki-path", default=str(DEFAULT_WIKI_PATH))
    parser.add_argument("--generated-at")
    parser.add_argument("--no-bridge", action="store_true")
    parser.add_argument("--format", choices=("summary", "json"), default="summary")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    result = export_lm_bounded_operator_orchestration(
        read_model_root=Path(args.read_model_root),
        export_root=Path(args.export_root),
        bridge_root=None if args.no_bridge else Path(args.bridge_root),
        wiki_path=Path(args.wiki_path),
        generated_at=args.generated_at,
    )
    if args.format == "json":
        print(stable_json(result), end="")
    else:
        print(f"{result['status']}: {result['candidate_action_count']} candidate actions")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
