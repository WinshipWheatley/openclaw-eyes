"""Dynamic Card Packet V0.

Backend-generated operator card packets for Mission Control. This module
renders local read-model state into compact card contracts. It does not build
live LM1/LM2, invoke models, spawn workers, connect providers, send email, open
browser/Gmail/Coupa, mutate ledgers or workbooks, export PDFs, submit portals,
mark paid/sent, push git, or grant authority.
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
DEFAULT_WIKI_PATH = Path("generated/wiki/openclaw/Dynamic Card Packet.md")

SCHEMA_VERSION = "dynamic_card_packet_v0"
CONTRACT_SCHEMA_VERSION = "dynamic_card_packet_contract_v0"
CONTRACT_READ_MODEL_ID = "dynamic_card_packet_contract"
LATEST_READ_MODEL_ID = "dynamic_card_packet_latest"
CONTRACT_JSON_EXPORT_NAME = f"{CONTRACT_READ_MODEL_ID}.json"
LATEST_JSON_EXPORT_NAME = f"{LATEST_READ_MODEL_ID}.json"
READY_STATUS = "DYNAMIC_CARD_PACKET_READY"
NOT_READY_STATUS = "DYNAMIC_CARD_PACKET_NOT_READY"
FIRST_CLASS_OPERATOR_ENVELOPE_CONTRACT_REF = "generated/read_models/first_class_operator_envelope_contract.json"
FIRST_CLASS_OPERATOR_ENVELOPE_STATUS_REF = "generated/read_models/first_class_operator_envelope_status.json"

CARD_TYPES = (
    "answer",
    "status",
    "next_action",
    "approval",
    "review_packet",
    "workflow_plan",
    "gate",
    "memory",
    "artifact",
    "evidence_intake",
    "payment_watch",
    "question",
    "workbook_registration",
)

SPEAKER_REFS = ("cassandra", "chief", "hermes", "guardian", "niles", "openclaw")
TONES = ("calm", "success", "warning", "blocked", "neutral")
TRUST_STATES = (
    "trusted_current",
    "preview_only",
    "future_gated",
    "stale_needs_proof",
    "operator_reported",
    "candidate_evidence",
    "unknown",
)
ACTION_TYPES = (
    "navigate",
    "stage_package_request",
    "system_question",
    "inspect_proof",
    "review_decision",
    "workbook_registration",
    "explain_gate",
    "none",
)

SOURCE_FILENAMES = {
    "operator_runtime_chain_current_state_audit": "operator_runtime_chain_current_state_audit.json",
    "operator_action_payloads": "operator_action_payloads.json",
    "lm_bounded_operator_orchestration": "lm_bounded_operator_orchestration_latest.json",
    "operator_next_decision": "operator_next_decision.json",
    "capital_hilton_invoice_operator_run_status": "capital_hilton_invoice_operator_run_status.json",
    "capital_hilton_business_development_proposal": "capital_hilton_business_development_proposal.json",
    "st_annes_work_log_review_surface": "st_annes_work_log_review_surface.json",
    "workroom_review_packet_index": "workroom_review_packet_index.json",
    "workroom_review_decision_status": "workroom_review_decision_status.json",
    "system_question_answer": "system_question_answer_contract.json",
    "client_invoice_workbook_registry": "client_invoice_workbook_registry.json",
    "package_event_index": "package_event_index.json",
    "chief_check_engine_diagnostic_package": "chief_check_engine_diagnostic_package.json",
    "evidence_intake": "evidence_intake_status.json",
    "first_class_operator_envelope_contract": "first_class_operator_envelope_contract.json",
    "first_class_operator_envelope_status": "first_class_operator_envelope_status.json",
}

PRECONDITIONS = {
    "operator_runtime_chain_current_state_audit": {
        "filename": "operator_runtime_chain_current_state_audit.json",
        "required_status": "OPERATOR_RUNTIME_CHAIN_CURRENT_STATE_AUDIT_READY",
    },
    "operator_action_payloads": {
        "filename": "operator_action_payloads.json",
        "required_status": "OPERATOR_ACTION_PAYLOADS_READY",
    },
    "lm_bounded_operator_orchestration": {
        "filename": "lm_bounded_operator_orchestration_latest.json",
        "required_status": "LM_BOUNDED_OPERATOR_ORCHESTRATION_READY",
        "status_keys": ("readiness_status", "status"),
        "accepted_statuses": ("LM_BOUNDED_OPERATOR_ORCHESTRATION_READY", "READY"),
    },
    "system_question_route": {
        "filename": "system_question_answer_contract.json",
        "required_status": "SYSTEM_QUESTION_ROUTE_READY",
        "equivalent_status": "SYSTEM_QUESTION_ANSWER_V0_READY",
    },
    "workroom_review_decision_consumer": {
        "filename": "workroom_review_decision_status.json",
        "required_status": "WORKROOM_REVIEW_DECISION_CONSUMER_READY",
    },
    "workbook_registration_route": {
        "filename": "client_invoice_workbook_registry.json",
        "required_status": "WORKBOOK_REGISTRATION_ROUTE_READY",
        "equivalent_status": "DETERMINISTIC_CLIENT_INVOICE_WORKBOOK_REGISTRY_NO_CELL_READ",
        "status_keys": ("status", "contract_status"),
    },
    "package_event_index": {
        "filename": "package_event_index.json",
        "required_status": "PACKAGE_EVENT_INDEX_READY",
    },
}

AUTHORITY_BOUNDARY = {
    "email_send_allowed": False,
    "ledger_posting_allowed": False,
    "browser_access_allowed": False,
    "gmail_allowed": False,
    "coupa_allowed": False,
    "portal_submit_allowed": False,
    "workbook_source_mutation_allowed": False,
    "ledger_mutation_allowed": False,
    "workbook_mutation_allowed": False,
    "pdf_export_allowed": False,
    "paid_marking_allowed": False,
    "business_action_allowed": False,
    "external_action_allowed": False,
    "authority_grant_allowed": False,
    "sent": False,
    "paid": False,
}

UNSAFE_TRUE_KEYS = set(AUTHORITY_BOUNDARY) | {
    "coupa_submit_allowed",
    "gmail_access_allowed",
    "coupa_access_allowed",
    "browser_automation_allowed",
    "workbook_open_allowed",
    "workbook_body_read_allowed",
    "spreadsheet_cell_read_allowed",
    "workbook_mutation_allowed",
    "excel_automation_allowed",
    "email_draft_allowed",
    "ledger_mutation_allowed",
    "payment_marking_allowed",
    "paid_marking_allowed",
    "model_call_allowed",
    "agent_activation_allowed",
    "tool_execution_allowed",
    "runtime_dispatch_allowed",
    "raw_body_ingestion_allowed",
    "merge_allowed",
    "push_allowed",
    "git_push_allowed",
    "worker_spawn_allowed",
    "child_agent_run_allowed",
    "agent_loop_allowed",
    "external_action_allowed",
    "business_action_allowed",
    "repair_authority_allowed",
    "email_send_performed",
    "gmail_access_performed",
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
    "agent_loop_started",
    "external_llm_invoked",
    "external_llm_called",
    "local_model_runtime_connected",
    "model_invoked",
    "external_provider_connected",
    "merge_performed",
    "git_push_performed",
    "push_performed",
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
    return cleaned or "card"


def _status(payload: Mapping[str, Any], keys: tuple[str, ...] = ("status", "readiness_status", "contract_status")) -> str:
    for key in keys:
        value = payload.get(key)
        if value:
            return str(value)
    return ""


def _source_ref(filename: str) -> str:
    return f"generated/read_models/{filename}"


def _source_payloads(read_model_root: Path = DEFAULT_READ_MODEL_ROOT) -> dict[str, dict[str, Any]]:
    root = _rooted(read_model_root)
    return {
        name: _load_json(root / filename)
        for name, filename in SOURCE_FILENAMES.items()
    }


def _proof_refs(value: Any) -> list[str]:
    refs: list[str] = []
    if isinstance(value, Mapping):
        for key, item in value.items():
            if key == "collapsed_by_default":
                continue
            if isinstance(item, str) and item:
                refs.append(item)
            elif isinstance(item, list):
                refs.extend(str(ref) for ref in item if str(ref))
    elif isinstance(value, list):
        refs.extend(str(ref) for ref in value if str(ref))
    elif isinstance(value, str) and value:
        refs.append(value)
    return list(dict.fromkeys(refs))


def _action_index(operator_action_payloads: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    actions = operator_action_payloads.get("action_payloads")
    if not isinstance(actions, list):
        return {}
    return {
        str(action.get("action_id")): dict(action)
        for action in actions
        if isinstance(action, Mapping) and action.get("action_id")
    }


def action_payload_ref(action_id: str) -> str:
    return f"generated/read_models/operator_action_payloads.json#action_payloads.{action_id}"


def _action_from_payload(
    action_index: Mapping[str, Mapping[str, Any]],
    action_id: str,
    *,
    enabled_override: bool | None = None,
    disabled_reason_override: str | None = None,
) -> dict[str, Any]:
    source = action_index.get(action_id)
    if not isinstance(source, Mapping):
        return _disabled_action(
            action_id=action_id,
            label=action_id.replace("_", " ").replace(".", " ").title(),
            action_type="none",
            disabled_reason="No deterministic operator_action_payload exists for this action.",
        )
    enabled = bool(source.get("enabled"))
    if enabled_override is not None:
        enabled = enabled_override
    disabled_reason = source.get("disabled_reason")
    if disabled_reason_override is not None:
        disabled_reason = disabled_reason_override
    if not enabled and not disabled_reason:
        disabled_reason = "Action is disabled by the backend gate."
    return {
        "action_id": str(source["action_id"]),
        "label": str(source.get("label") or source["action_id"]),
        "action_type": str(source.get("action_type") or "none"),
        "enabled": enabled,
        "disabled_reason": None if enabled else str(disabled_reason),
        "payload_ref": action_payload_ref(str(source["action_id"])),
        "business_action": bool(source.get("business_action")),
    }


def _disabled_action(
    *,
    action_id: str,
    label: str,
    action_type: str = "none",
    disabled_reason: str,
) -> dict[str, Any]:
    return {
        "action_id": action_id,
        "label": label,
        "action_type": action_type if action_type in ACTION_TYPES else "none",
        "enabled": False,
        "disabled_reason": disabled_reason,
        "payload_ref": "",
        "business_action": False,
    }


def _proof(
    *,
    proof_refs: list[str] | tuple[str, ...] = (),
    receipt_refs: list[str] | tuple[str, ...] = (),
    read_model_refs: list[str] | tuple[str, ...] = (),
    label: str = "Details",
) -> dict[str, Any]:
    return {
        "label": label,
        "collapsed_by_default": True,
        "proof_refs": list(dict.fromkeys(str(ref) for ref in proof_refs if str(ref))),
        "receipt_refs": list(dict.fromkeys(str(ref) for ref in receipt_refs if str(ref))),
        "read_model_refs": list(dict.fromkeys(str(ref) for ref in read_model_refs if str(ref))),
    }


def _card(
    *,
    card_id: str,
    card_type: str,
    speaker_ref: str,
    headline: str,
    plain_summary: str,
    supporting_lines: list[str] | tuple[str, ...],
    status_label: str,
    tone: str,
    trust_state: str,
    priority: int,
    visible_by_default: bool,
    actions: list[dict[str, Any]] | tuple[dict[str, Any], ...],
    proof: Mapping[str, Any],
) -> dict[str, Any]:
    if card_type not in CARD_TYPES:
        raise ValueError(f"unsupported card_type: {card_type}")
    if speaker_ref not in SPEAKER_REFS:
        raise ValueError(f"unsupported speaker_ref: {speaker_ref}")
    if tone not in TONES:
        raise ValueError(f"unsupported tone: {tone}")
    if trust_state not in TRUST_STATES:
        raise ValueError(f"unsupported trust_state: {trust_state}")
    return {
        "card_id": card_id,
        "card_type": card_type,
        "speaker_ref": speaker_ref,
        "headline": headline,
        "plain_summary": plain_summary,
        "supporting_lines": list(supporting_lines),
        "status_label": status_label,
        "tone": tone,
        "trust_state": trust_state,
        "priority": int(priority),
        "visible_by_default": bool(visible_by_default),
        "actions": list(actions),
        "proof": dict(proof),
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
    }


def _capital_hilton_payment_watch_card(sources: Mapping[str, Mapping[str, Any]], action_index: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    invoice = sources.get("capital_hilton_invoice_operator_run_status", {})
    lm = sources.get("lm_bounded_operator_orchestration", {})
    status = str(invoice.get("coupa_submission_status") or invoice.get("coupa_status_observed") or "processing")
    proof_refs = [
        _source_ref("capital_hilton_invoice_operator_run_status.json"),
        _source_ref("operator_action_payloads.json"),
        _source_ref("lm_bounded_operator_orchestration_latest.json"),
        *_proof_refs(invoice.get("proof_refs")),
        *_proof_refs((lm.get("lm_recommended_action") or {}).get("proof_refs") if isinstance(lm.get("lm_recommended_action"), Mapping) else []),
    ]
    return _card(
        card_id="dynamic_card.finance.capital_hilton.payment_watch",
        card_type="payment_watch",
        speaker_ref="chief",
        headline="Stay on payment watch",
        plain_summary="Coupa is processing. Wait for payment evidence before anything touches the ledger.",
        supporting_lines=[
            f"Coupa status: {status}.",
            "Payment evidence is not recorded as ledger truth.",
            "No Coupa, browser, ledger, or paid action is available from this card.",
        ],
        status_label="Payment watch",
        tone="calm",
        trust_state="trusted_current",
        priority=100,
        visible_by_default=True,
        actions=[
            _action_from_payload(action_index, "capital_hilton.payment.open_finance"),
        ],
        proof=_proof(
            proof_refs=proof_refs,
            receipt_refs=_proof_refs(invoice.get("proof_refs")),
            read_model_refs=[
                _source_ref("capital_hilton_invoice_operator_run_status.json"),
                _source_ref("lm_bounded_operator_orchestration_latest.json"),
            ],
        ),
    )


def _contextual_question_card(action_index: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    return _card(
        card_id="dynamic_card.finance.capital_hilton.contextual_question",
        card_type="answer",
        speaker_ref="chief",
        headline="Stay on payment watch",
        plain_summary="Coupa is processing. Wait for payment evidence before anything touches the ledger.",
        supporting_lines=[
            "Answered from current lane metadata: Finance / Capital Hilton.",
            "This is a local answer, not package staging.",
            "Diagnostic workflow queue routing is not needed for this question.",
        ],
        status_label="Answer ready",
        tone="calm",
        trust_state="trusted_current",
        priority=95,
        visible_by_default=True,
        actions=[
            _action_from_payload(action_index, "capital_hilton.payment.open_finance"),
        ],
        proof=_proof(
            proof_refs=[
                _source_ref("system_question_answer_contract.json"),
                _source_ref("capital_hilton_invoice_operator_run_status.json"),
                _source_ref("finance_thread_index.json"),
            ],
            read_model_refs=[
                _source_ref("system_question_answer_contract.json"),
                _source_ref("finance_thread_index.json"),
            ],
        ),
    )


def _open_review_packet(packet_index: Mapping[str, Any]) -> dict[str, Any]:
    packets = packet_index.get("packets")
    if not isinstance(packets, list):
        return {}
    for packet in packets:
        if not isinstance(packet, Mapping):
            continue
        status = str(packet.get("status") or packet.get("review_decision_status") or "")
        if (
            packet.get("operator_decision_required") is True
            and packet.get("completed") is not True
            and status not in {"OPERATOR_REVIEW_RECORDED", "INFORMATIONAL_REVIEW_CLOSED"}
        ):
            return dict(packet)
    return {}


def _review_packet_card(sources: Mapping[str, Mapping[str, Any]], action_index: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    packet = _open_review_packet(sources.get("workroom_review_packet_index", {}))
    packet_id = str(packet.get("review_packet_id") or "review_packet:unknown")
    packet_slug = _slug(packet_id)
    action_ids = [
        f"review_packet.{packet_slug}.approve_review_packet_for_record",
        f"review_packet.{packet_slug}.request_review_packet_rework",
        f"review_packet.{packet_slug}.mark_review_packet_informational",
    ]
    proof_refs = [
        _source_ref("workroom_review_packet_index.json"),
        _source_ref("workroom_review_decision_status.json"),
        *_proof_refs(packet.get("proof_refs")),
    ]
    return _card(
        card_id="dynamic_card.build.review_packet.current",
        card_type="review_packet",
        speaker_ref="chief",
        headline="Review packet needs local decision",
        plain_summary=str(packet.get("human_summary") or "A review packet is ready for operator review."),
        supporting_lines=[
            f"Packet: {packet_id}.",
            f"Worker: {packet.get('worker_ref', 'unknown')}.",
            "Use review controls only; no merge or push is authorized.",
        ],
        status_label=str(packet.get("status") or "Review required"),
        tone="warning",
        trust_state="preview_only",
        priority=90,
        visible_by_default=bool(packet),
        actions=[_action_from_payload(action_index, action_id) for action_id in action_ids],
        proof=_proof(
            proof_refs=proof_refs,
            read_model_refs=[
                _source_ref("workroom_review_packet_index.json"),
                _source_ref("workroom_review_decision_status.json"),
            ],
        ),
    )


def _business_development_card(sources: Mapping[str, Mapping[str, Any]], action_index: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    proposal = sources.get("capital_hilton_business_development_proposal", {})
    status = str(proposal.get("proposal_status") or "proposal status unknown")
    pending = proposal.get("client_review_pending") is True
    return _card(
        card_id="dynamic_card.business_development.capital_hilton.proposal",
        card_type="status",
        speaker_ref="cassandra",
        headline="Proposal follow-up is review-only",
        plain_summary="Capital Hilton proposal context is business development. Draft or stage a follow-up only for review; do not send.",
        supporting_lines=[
            f"Proposal status: {status}.",
            f"Client review pending: {str(pending).lower()}.",
            "Email send, finance handoff, ledger posting, and accepted/paid truth are closed.",
        ],
        status_label="Proposal status",
        tone="calm",
        trust_state="trusted_current",
        priority=80,
        visible_by_default=True,
        actions=[
            _action_from_payload(action_index, "capital_hilton.proposal.stage_followup"),
        ],
        proof=_proof(
            proof_refs=[
                _source_ref("capital_hilton_business_development_proposal.json"),
                *_proof_refs(proposal.get("proof_refs")),
            ],
            read_model_refs=[_source_ref("capital_hilton_business_development_proposal.json")],
        ),
    )


def _check_engine_card(action_index: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    return _card(
        card_id="dynamic_card.system.check_engine.diagnostic",
        card_type="status",
        speaker_ref="chief",
        headline="Chief diagnostic only",
        plain_summary="Open the Check Engine diagnostic or ask Chief; no repair authority is granted.",
        supporting_lines=[
            "This card can explain or open diagnostics only.",
            "No repair, worker spawn, push, or business action follows from this card.",
        ],
        status_label="Diagnostic",
        tone="neutral",
        trust_state="preview_only",
        priority=70,
        visible_by_default=True,
        actions=[
            _action_from_payload(action_index, "chief_diagnostic.open"),
            _action_from_payload(action_index, "helm_question.hardwired_vs_spawned.ask"),
        ],
        proof=_proof(
            proof_refs=[
                _source_ref("chief_check_engine_diagnostic_package.json"),
                _source_ref("operator_action_payloads.json"),
            ],
            read_model_refs=[
                _source_ref("chief_check_engine_diagnostic_package.json"),
                _source_ref("operator_action_payloads.json"),
            ],
        ),
    )


def _workbook_registration_card(sources: Mapping[str, Mapping[str, Any]], action_index: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    registry = sources.get("client_invoice_workbook_registry", {})
    active = registry.get("active_record") if isinstance(registry.get("active_record"), Mapping) else {}
    workbook_name = str(active.get("workbook_display_name") or "selected workbook reference")
    status = str(active.get("workbook_status") or registry.get("contract_status") or "workbook reference")
    return _card(
        card_id="dynamic_card.finance.capital_hilton.workbook_registration",
        card_type="workbook_registration",
        speaker_ref="chief",
        headline="Workbook reference can be registered",
        plain_summary="Register the workbook reference as metadata only; do not read workbook body, run Excel, or mutate the file.",
        supporting_lines=[
            f"Workbook: {workbook_name}.",
            f"Status: {status}.",
            "Metadata registration is separate from any governed sheet audit.",
        ],
        status_label="Workbook registration",
        tone="calm",
        trust_state="trusted_current",
        priority=60,
        visible_by_default=True,
        actions=[
            _action_from_payload(action_index, "client_invoice_workbook.register"),
        ],
        proof=_proof(
            proof_refs=[_source_ref("client_invoice_workbook_registry.json")],
            read_model_refs=[_source_ref("client_invoice_workbook_registry.json")],
        ),
    )


def _st_annes_work_log_card(sources: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    surface = sources.get("st_annes_work_log_review_surface", {})
    counts = surface.get("event_counts") if isinstance(surface.get("event_counts"), Mapping) else {}
    pending = int(counts.get("pending_operator_review") or 0)
    test_only = int(counts.get("smoke_or_test_not_included") or 0)
    actions: list[dict[str, Any]] = []
    if pending:
        disabled_reason = "No deterministic operator_action_payload exists yet for St. Anne's review actions."
        actions = [
            _disabled_action(
                action_id="st_annes.work_log.confirm",
                label="Confirm",
                disabled_reason=disabled_reason,
            ),
            _disabled_action(
                action_id="st_annes.work_log.discard",
                label="Discard",
                disabled_reason=disabled_reason,
            ),
            _disabled_action(
                action_id="st_annes.work_log.mark_as_test",
                label="Mark as test",
                disabled_reason=disabled_reason,
            ),
        ]
    return _card(
        card_id="dynamic_card.finance.st_annes.work_log_review",
        card_type="status",
        speaker_ref="chief",
        headline="St. Anne's work-log review",
        plain_summary="St. Anne's work-log review stays local; completed or test-only items are not primary active blockers.",
        supporting_lines=[
            f"Pending review: {pending}.",
            f"Smoke/test not included: {test_only}.",
            "Excel, PDF, email, ledger, and invoice inclusion remain gated.",
        ],
        status_label="No active blocker" if pending == 0 else "Review pending",
        tone="neutral" if pending == 0 else "warning",
        trust_state="trusted_current",
        priority=20 if pending == 0 else 75,
        visible_by_default=pending > 0,
        actions=actions,
        proof=_proof(
            proof_refs=[_source_ref("st_annes_work_log_review_surface.json")],
            read_model_refs=[_source_ref("st_annes_work_log_review_surface.json")],
        ),
    )


def _evidence_envelope_required_action(*, action_id: str, label: str, disabled_reason: str) -> dict[str, Any]:
    action = _disabled_action(
        action_id=action_id,
        label=label,
        disabled_reason=disabled_reason,
    )
    action.update(
        {
            "requires_operator_authority_envelope": True,
            "operator_authority_envelope_contract_ref": FIRST_CLASS_OPERATOR_ENVELOPE_CONTRACT_REF,
            "operator_authority_envelope_status_ref": FIRST_CLASS_OPERATOR_ENVELOPE_STATUS_REF,
            "authority_granted_by_action": False,
        }
    )
    return action


def _evidence_intake_card(sources: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    status = sources.get("evidence_intake", {})
    record = status.get("latest_record") if isinstance(status.get("latest_record"), Mapping) else {}
    card = status.get("dynamic_card") if isinstance(status.get("dynamic_card"), Mapping) else {}
    artifact = record.get("artifact") if isinstance(record.get("artifact"), Mapping) else {}
    payment = record.get("payment") if isinstance(record.get("payment"), Mapping) else {}
    world_ref = str(record.get("current_world_ref") or "finance")
    thread_ref = str(record.get("current_thread_ref") or "evidence_intake")
    disabled_reason = "No deterministic operator_action_payload exists yet for evidence intake card actions."
    summary = str(
        card.get("summary")
        or "This appears to show payment processing for invoice 2026-1001. Ledger remains untouched until payment is confirmed."
    )
    return _card(
        card_id=f"dynamic_card.{_slug(world_ref)}.{_slug(thread_ref)}.evidence_intake.payment_processing",
        card_type="evidence_intake",
        speaker_ref="chief",
        headline=str(card.get("headline") or "Payment proof received"),
        plain_summary=summary,
        supporting_lines=[
            f"Evidence status: {record.get('evidence_status', 'unknown')}.",
            f"Payment state: {payment.get('payment_state', 'unknown')}.",
            "Candidate evidence does not mark paid or touch the ledger.",
        ],
        status_label=str(card.get("status_label") or "Processing evidence"),
        tone="calm",
        trust_state=str(card.get("trust_state") or "operator_reported"),
        priority=97,
        visible_by_default=bool(record),
        actions=[
            _evidence_envelope_required_action(
                action_id="evidence_intake.attach_to_lane",
                label="Attach to lane",
                disabled_reason=disabled_reason,
            ),
            _evidence_envelope_required_action(
                action_id="evidence_intake.ask_what_this_means",
                label="Ask what this means",
                disabled_reason=disabled_reason,
            ),
            _evidence_envelope_required_action(
                action_id="evidence_intake.mark_as_test",
                label="Mark as test",
                disabled_reason=disabled_reason,
            ),
            _evidence_envelope_required_action(
                action_id="evidence_intake.show_details",
                label="Show details",
                disabled_reason=disabled_reason,
            ),
        ],
        proof=_proof(
            proof_refs=[
                _source_ref("evidence_intake_status.json"),
                str(artifact.get("artifact_ref") or record.get("artifact_ref") or ""),
            ],
            read_model_refs=[_source_ref("evidence_intake_status.json")],
        ),
    )


def _precondition_rows(read_model_root: Path = DEFAULT_READ_MODEL_ROOT) -> list[dict[str, Any]]:
    root = _rooted(read_model_root)
    rows: list[dict[str, Any]] = []
    for precondition_ref, spec in PRECONDITIONS.items():
        payload = _load_json(root / str(spec["filename"]))
        status_keys = tuple(spec.get("status_keys") or ("status", "readiness_status", "contract_status"))
        observed = _status(payload, status_keys)
        accepted = tuple(spec.get("accepted_statuses") or (str(spec["required_status"]), str(spec.get("equivalent_status") or "")))
        accepted = tuple(status for status in accepted if status)
        rows.append(
            {
                "precondition_ref": precondition_ref,
                "required_status": str(spec["required_status"]),
                "observed_status": observed,
                "equivalent_status_accepted": str(spec.get("equivalent_status") or ""),
                "ready": observed in accepted,
                "source_ref": _source_ref(str(spec["filename"])),
            }
        )
    return rows


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


def validate_packet(packet: Mapping[str, Any], action_index: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    errors: list[str] = []
    cards = packet.get("cards")
    if not isinstance(cards, list) or not cards:
        errors.append("cards_missing")
        cards = []
    enabled_action_ids: list[str] = []
    disabled_action_ids: list[str] = []
    for card in cards:
        if not isinstance(card, Mapping):
            errors.append("card_not_object")
            continue
        card_id = str(card.get("card_id") or "unknown_card")
        if card.get("trust_state") not in TRUST_STATES:
            errors.append(f"{card_id}:trust_state_missing_or_invalid")
        if card.get("card_type") not in CARD_TYPES:
            errors.append(f"{card_id}:card_type_invalid")
        if card.get("speaker_ref") not in SPEAKER_REFS:
            errors.append(f"{card_id}:speaker_ref_invalid")
        proof = card.get("proof")
        if not isinstance(proof, Mapping) or proof.get("collapsed_by_default") is not True:
            errors.append(f"{card_id}:proof_not_collapsed_by_default")
        authority = card.get("authority_boundary")
        if not isinstance(authority, Mapping) or any(value is not False for value in authority.values()):
            errors.append(f"{card_id}:authority_boundary_not_all_false")
        for action in card.get("actions") or []:
            if not isinstance(action, Mapping):
                errors.append(f"{card_id}:action_not_object")
                continue
            action_id = str(action.get("action_id") or "")
            if action.get("action_type") not in ACTION_TYPES:
                errors.append(f"{card_id}:{action_id}:action_type_invalid")
            if action.get("enabled") is True:
                enabled_action_ids.append(action_id)
                if action_id not in action_index:
                    errors.append(f"{card_id}:{action_id}:enabled_action_missing_deterministic_payload")
                if not str(action.get("payload_ref") or "").startswith("generated/read_models/operator_action_payloads.json#"):
                    errors.append(f"{card_id}:{action_id}:enabled_action_payload_ref_missing")
                if action.get("business_action") is True:
                    errors.append(f"{card_id}:{action_id}:enabled_business_action")
            else:
                disabled_action_ids.append(action_id)
                if not action.get("disabled_reason"):
                    errors.append(f"{card_id}:{action_id}:disabled_reason_missing")
    unsafe = unsafe_true_grants(packet)
    if unsafe:
        errors.extend(f"unsafe_true_grant:{key}" for key in unsafe)
    return {
        "valid": not errors,
        "errors": errors,
        "enabled_action_ids": enabled_action_ids,
        "disabled_action_ids": disabled_action_ids,
        "all_visible_cards_have_trust_state": all(
            isinstance(card, Mapping) and card.get("trust_state") in TRUST_STATES
            for card in cards
            if isinstance(card, Mapping) and card.get("visible_by_default") is True
        ),
        "enabled_actions_reference_deterministic_payloads": all(action_id in action_index for action_id in enabled_action_ids),
        "proof_collapsed_by_default": all(
            isinstance(card, Mapping)
            and isinstance(card.get("proof"), Mapping)
            and card["proof"].get("collapsed_by_default") is True
            for card in cards
        ),
        "unsafe_true_grants": unsafe,
        "unsafe_true_grants_absent": not unsafe,
    }


def build_latest_packet(
    *,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    sources = _source_payloads(read_model_root)
    action_index = _action_index(sources.get("operator_action_payloads", {}))
    preconditions = _precondition_rows(read_model_root)
    cards = [
        _capital_hilton_payment_watch_card(sources, action_index),
        _evidence_intake_card(sources),
        _contextual_question_card(action_index),
        _review_packet_card(sources, action_index),
        _business_development_card(sources, action_index),
        _check_engine_card(action_index),
        _workbook_registration_card(sources, action_index),
        _st_annes_work_log_card(sources),
    ]
    cards = sorted(cards, key=lambda card: (-int(card["priority"]), str(card["card_id"])))
    packet: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": LATEST_READ_MODEL_ID,
        "status": READY_STATUS if all(row["ready"] for row in preconditions) else NOT_READY_STATUS,
        "packet_id": f"dynamic_card_packet:{_short_hash(generated_at, len(cards))}",
        "generated_at": generated_at,
        "surface_context": {
            "world_ref": "mission_control",
            "thread_ref": "operator_surface",
            "workflow_ref": "dynamic_card_packet",
            "client_ref": "mixed",
            "active_entity_ref": "operator_current_surface",
        },
        "cards": cards,
        "card_count": len(cards),
        "visible_card_count": sum(1 for card in cards if card.get("visible_by_default") is True),
        "source_refs": [_source_ref(filename) for filename in SOURCE_FILENAMES.values()],
        "preconditions": preconditions,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
    }
    validation = validate_packet(packet, action_index)
    packet["machine_proof"] = {
        "preconditions_ready": all(row["ready"] for row in preconditions),
        "dynamic_card_packet_generated": True,
        "backend_generated_operator_surface": True,
        "human_copy_first": True,
        "machine_contracts_hidden_by_default": True,
        "proof_collapsed_by_default": validation["proof_collapsed_by_default"],
        "all_visible_cards_have_trust_state": validation["all_visible_cards_have_trust_state"],
        "enabled_actions_reference_deterministic_payloads": validation["enabled_actions_reference_deterministic_payloads"],
        "no_card_invents_authority": validation["valid"],
        "payment_truth_requires_payment_evidence": True,
        "generated_summaries_do_not_override_receipts": True,
        "memory_candidates_do_not_become_truth": True,
        "external_llm_invoked": False,
        "local_model_runtime_connected": False,
        "worker_spawn_performed": False,
        "worker_execution_performed": False,
        "child_agent_run_performed": False,
        "email_send_performed": False,
        "gmail_access_performed": False,
        "browser_access_performed": False,
        "coupa_access_performed": False,
        "coupa_submit_performed": False,
        "ledger_mutation_performed": False,
        "workbook_open_performed": False,
        "workbook_body_read_performed": False,
        "spreadsheet_cell_read_performed": False,
        "workbook_mutation_performed": False,
        "excel_automation_performed": False,
        "pdf_export_performed": False,
        "paid_marking_performed": False,
        "submit_performed": False,
        "business_action_performed": False,
        "repair_performed": False,
        "merge_performed": False,
        "git_push_performed": False,
        "unsafe_true_grants": validation["unsafe_true_grants"],
        "unsafe_true_grants_absent": validation["unsafe_true_grants_absent"],
        "validation_errors": validation["errors"],
    }
    return packet


def build_contract_read_model(
    *,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    latest = build_latest_packet(read_model_root=read_model_root, generated_at=generated_at)
    preconditions = latest["preconditions"]
    payload: dict[str, Any] = {
        "schema_version": CONTRACT_SCHEMA_VERSION,
        "read_model_id": CONTRACT_READ_MODEL_ID,
        "status": READY_STATUS if latest["status"] == READY_STATUS else NOT_READY_STATUS,
        "generated_at": generated_at,
        "purpose": "Backend-generated operator cards for Mission Control without custom SwiftUI per workflow.",
        "latest_packet_ref": _source_ref(LATEST_JSON_EXPORT_NAME),
        "output_schema_version": SCHEMA_VERSION,
        "required_top_level_fields": [
            "schema_version",
            "packet_id",
            "generated_at",
            "surface_context",
            "cards",
        ],
        "card_schema": {
            "card_types": list(CARD_TYPES),
            "speaker_refs": list(SPEAKER_REFS),
            "tones": list(TONES),
            "trust_states": list(TRUST_STATES),
            "action_types": list(ACTION_TYPES),
            "authority_boundary": dict(AUTHORITY_BOUNDARY),
        },
        "rules": [
            "Every card must have trust_state.",
            "Every enabled action must reference an existing operator_action_payload.",
            "Disabled actions must include disabled_reason.",
            "No card may invent authority.",
            "Proof/details are collapsed by default.",
            "Machine contracts are hidden by default.",
            "Human copy appears before backend ids.",
            "Generated summaries cannot override receipts.",
            "Memory candidates cannot become truth.",
            "Payment truth cannot come from email, Coupa, or proposal status without payment evidence.",
        ],
        "required_example_cards": [
            "Finance / Capital Hilton payment watch",
            "Contextual question answer for Finance / Capital Hilton",
            "Build review packet",
            "Business Development / Capital Hilton proposal",
            "Check Engine diagnostic",
            "Workbook registration",
            "St. Anne's work-log review",
            "Evidence intake payment-processing artifact",
        ],
        "example_packet_digest": {
            "packet_id": latest["packet_id"],
            "card_count": latest["card_count"],
            "visible_card_count": latest["visible_card_count"],
            "card_ids": [card["card_id"] for card in latest["cards"]],
        },
        "preconditions": preconditions,
        "source_refs": latest["source_refs"],
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "machine_proof": {
            "preconditions_ready": all(row["ready"] for row in preconditions),
            "contract_only": True,
            "latest_packet_valid": latest["machine_proof"]["no_card_invents_authority"],
            "all_visible_cards_have_trust_state": latest["machine_proof"]["all_visible_cards_have_trust_state"],
            "enabled_actions_reference_deterministic_payloads": latest["machine_proof"]["enabled_actions_reference_deterministic_payloads"],
            "proof_collapsed_by_default": latest["machine_proof"]["proof_collapsed_by_default"],
            "external_llm_invoked": False,
            "local_model_runtime_connected": False,
            "worker_spawn_performed": False,
            "worker_execution_performed": False,
            "child_agent_run_performed": False,
            "email_send_performed": False,
            "browser_access_performed": False,
            "coupa_access_performed": False,
            "ledger_mutation_performed": False,
            "workbook_body_read_performed": False,
            "workbook_mutation_performed": False,
            "pdf_export_performed": False,
            "paid_marking_performed": False,
            "submit_performed": False,
            "business_action_performed": False,
            "merge_performed": False,
            "git_push_performed": False,
            "unsafe_true_grants": unsafe_true_grants(latest),
            "unsafe_true_grants_absent": not unsafe_true_grants(latest),
        },
    }
    return payload


def build_wiki(contract: Mapping[str, Any], latest: Mapping[str, Any]) -> str:
    lines = [
        "# Dynamic Card Packet",
        "",
        f"Status: `{latest.get('status', NOT_READY_STATUS)}`",
        "",
        "The Dynamic Card Packet is the backend-generated operator card surface for Mission Control. It lets the Mac render current answers, status, safe next actions, proof drawers, trust state, and safe buttons without custom SwiftUI for every workflow.",
        "",
        "## Boundary",
        "",
        "- No live LM1 or LM2.",
        "- No worker spawn or child-agent run.",
        "- No external LLM or local model runtime.",
        "- No email, Gmail, browser, Coupa, ledger, workbook, PDF, submit, mark-paid, merge, push, or repair authority.",
        "- Enabled actions only reference deterministic `operator_action_payloads.json` payloads.",
        "- Proof/details are collapsed by default.",
        "",
        "## Cards",
        "",
    ]
    for card in latest.get("cards") or []:
        if not isinstance(card, Mapping):
            continue
        lines.extend(
            [
                f"### {card.get('headline')}",
                "",
                f"- Card id: `{card.get('card_id')}`",
                f"- Type: `{card.get('card_type')}`",
                f"- Speaker: `{card.get('speaker_ref')}`",
                f"- Trust: `{card.get('trust_state')}`",
                f"- Summary: {card.get('plain_summary')}",
                f"- Next/status: `{card.get('status_label')}`",
                f"- Visible by default: `{str(card.get('visible_by_default')).lower()}`",
                "",
            ]
        )
        actions = card.get("actions") if isinstance(card.get("actions"), list) else []
        if actions:
            lines.append("Actions:")
            for action in actions:
                if isinstance(action, Mapping):
                    lines.append(
                        f"- `{action.get('action_id')}` / `{action.get('label')}` / enabled=`{str(action.get('enabled')).lower()}`"
                    )
            lines.append("")
    lines.extend(
        [
            "## Contract",
            "",
            f"- Contract read model: `generated/read_models/{CONTRACT_JSON_EXPORT_NAME}`",
            f"- Latest packet: `generated/read_models/{LATEST_JSON_EXPORT_NAME}`",
            f"- Required example cards: `{len(contract.get('required_example_cards') or [])}`",
            "",
            "## Machine Proof",
            "",
            f"- All visible cards have trust state: `{str((latest.get('machine_proof') or {}).get('all_visible_cards_have_trust_state')).lower()}`",
            f"- Enabled actions reference deterministic payloads: `{str((latest.get('machine_proof') or {}).get('enabled_actions_reference_deterministic_payloads')).lower()}`",
            f"- Unsafe true grants absent: `{str((latest.get('machine_proof') or {}).get('unsafe_true_grants_absent')).lower()}`",
        ]
    )
    return "\n".join(lines) + "\n"


def export_dynamic_card_packet(
    *,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
    export_root: Path = DEFAULT_EXPORT_ROOT,
    bridge_root: Path | None = DEFAULT_BRIDGE_ROOT,
    wiki_path: Path = DEFAULT_WIKI_PATH,
    generated_at: str | None = None,
) -> dict[str, str]:
    generated_at = generated_at or utc_now()
    contract = build_contract_read_model(read_model_root=read_model_root, generated_at=generated_at)
    latest = build_latest_packet(read_model_root=read_model_root, generated_at=generated_at)

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
        "status": str(latest["status"]),
        "contract_read_model_path": contract_path.as_posix(),
        "latest_read_model_path": latest_path.as_posix(),
        "bridge_contract_read_model_path": bridge_contract_path,
        "bridge_latest_read_model_path": bridge_latest_path,
        "wiki_path": wiki_path.as_posix(),
        "card_count": str(latest["card_count"]),
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Publish Dynamic Card Packet V0.")
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
    result = export_dynamic_card_packet(
        read_model_root=Path(args.read_model_root),
        export_root=Path(args.export_root),
        bridge_root=None if args.no_bridge else Path(args.bridge_root),
        wiki_path=Path(args.wiki_path),
        generated_at=args.generated_at,
    )
    if args.format == "json":
        print(stable_json(result), end="")
    else:
        print(f"{result['status']}: {result['card_count']} cards")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
