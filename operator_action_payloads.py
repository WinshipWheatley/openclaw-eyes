"""Operator Action Payloads V0.

This read-model publishes backend action payloads for Mac-visible operator
cards. It does not execute actions, open providers, mutate ledgers or
workbooks, export PDFs, submit portals, mark paid/sent, push git, spawn
workers, or launch agent loops.
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
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_WIKI_PATH = Path("generated/wiki/openclaw/Operator Action Payloads.md")
DEFAULT_BRIDGE_ROOT = Path("/mnt/e/openclaw/generated/read_models")

SCHEMA_VERSION = "operator_action_payloads_v0"
READ_MODEL_ID = "operator_action_payloads"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
READY_STATUS = "OPERATOR_ACTION_PAYLOADS_READY"

DEFAULT_SOURCE_PATHS = {
    "helm_actionability_surface": Path("generated/read_models/helm_actionability_surface.json"),
    "workroom_review_packet_index": Path("generated/read_models/workroom_review_packet_index.json"),
    "workroom_review_decision_contract": Path("generated/read_models/workroom_review_decision_contract.json"),
    "capital_hilton_business_development_proposal": Path(
        "generated/read_models/capital_hilton_business_development_proposal.json"
    ),
    "capital_hilton_invoice_operator_run_status": Path(
        "generated/read_models/capital_hilton_invoice_operator_run_status.json"
    ),
    "client_invoice_workbook_registry": Path("generated/read_models/client_invoice_workbook_registry.json"),
    "approval_request_queue": Path("generated/read_models/approval_request_queue.json"),
    "chief_check_engine_diagnostic_package": Path("generated/read_models/chief_check_engine_diagnostic_package.json"),
    "chief_check_engine_environment_posture": Path(
        "generated/read_models/chief_check_engine_environment_posture.json"
    ),
}

ACTION_TYPES = (
    "navigate",
    "stage_package_request",
    "system_question",
    "objective_advancement",
    "inspect_proof",
    "review_decision",
    "workbook_registration",
    "record_payment_proof_intake",
    "explain_gate",
    "none",
)

AUTHORITY_BOUNDARY = {
    "email_send_allowed": False,
    "ledger_posting_allowed": False,
    "browser_access_allowed": False,
    "gmail_allowed": False,
    "coupa_allowed": False,
    "portal_submit_allowed": False,
    "workbook_source_mutation_allowed": False,
    "pdf_export_allowed": False,
    "sent": False,
    "paid": False,
    "ledger_mutation_allowed": False,
    "workbook_mutation_allowed": False,
    "workbook_open_allowed": False,
    "workbook_body_read_allowed": False,
    "spreadsheet_cell_read_allowed": False,
    "merge_allowed": False,
    "push_allowed": False,
    "git_push_allowed": False,
    "worker_spawn_allowed": False,
    "child_agent_run_allowed": False,
    "agent_loop_allowed": False,
    "repair_authority_allowed": False,
    "external_action_allowed": False,
    "business_action_allowed": False,
}

UNSAFE_TRUE_KEYS = set(AUTHORITY_BOUNDARY) | {
    "coupa_submit_allowed",
    "gmail_access_allowed",
    "coupa_access_allowed",
    "browser_automation_allowed",
    "excel_automation_allowed",
    "email_draft_allowed",
    "ledger_mutation_allowed",
    "payment_marking_allowed",
    "model_call_allowed",
    "agent_activation_allowed",
    "tool_execution_allowed",
    "runtime_dispatch_allowed",
    "raw_body_ingestion_allowed",
    "merge_performed",
    "git_push_performed",
    "business_action_performed",
    "email_send_performed",
    "submit_performed",
    "paid_marking_performed",
    "ledger_mutation_performed",
    "workbook_mutation_performed",
    "pdf_export_performed",
}

GATE_REFS_BY_LABEL = {
    "Email send locked": "send_email",
    "Coupa submit locked": "coupa_submit",
    "Ledger posting locked": "ledger_post",
    "Excel mutation locked": "workbook_mutation",
    "PDF export locked": "pdf_export",
}

DEFAULT_GATE_LANES = {
    "send_email": ("finance", "capital_hilton"),
    "coupa_submit": ("finance", "capital_hilton"),
    "ledger_post": ("finance", "capital_hilton"),
    "workbook_mutation": ("finance", "st_annes"),
    "pdf_export": ("finance", "st_annes"),
}


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _rooted(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def _read_json(path: Path) -> dict[str, Any]:
    rooted = _rooted(path)
    if not rooted.exists():
        return {}
    try:
        value = json.loads(rooted.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}


def _short_hash(*parts: object) -> str:
    return hashlib.sha256("\0".join(str(part) for part in parts).encode("utf-8")).hexdigest()[:16]


def _slug(value: object) -> str:
    text = str(value or "").strip().lower()
    cleaned = "".join(char if char.isalnum() else "_" for char in text).strip("_")
    return cleaned or "unknown"


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


def _action_payload(
    *,
    action_id: str,
    label: str,
    action_type: str,
    enabled: bool = True,
    disabled_reason: str | None = None,
    safe_to_render_button: bool = True,
    business_action: bool = False,
    target_world_ref: str = "",
    target_thread_ref: str = "",
    payload: Mapping[str, Any] | None = None,
    proof_refs: list[str] | tuple[str, ...] | None = None,
    controller_event_type: str = "",
    control_scope: str = "lane",
    text_response_preferred: bool = False,
) -> dict[str, Any]:
    if action_type not in ACTION_TYPES:
        raise ValueError(f"unsupported action_type: {action_type}")
    return {
        "action_id": action_id,
        "label": label,
        "action_type": action_type,
        "enabled": enabled,
        "disabled_reason": disabled_reason,
        "safe_to_render_button": safe_to_render_button,
        "business_action": business_action,
        "target_world_ref": target_world_ref,
        "target_thread_ref": target_thread_ref,
        "controller_event_type": controller_event_type,
        "control_scope": control_scope,
        "text_response_preferred": bool(text_response_preferred),
        "payload": dict(payload or {}),
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "proof_refs": list(dict.fromkeys(str(ref) for ref in proof_refs or [] if str(ref))),
    }


def _source_payloads(source_paths: Mapping[str, Path]) -> dict[str, dict[str, Any]]:
    return {name: _read_json(path) for name, path in source_paths.items()}


def _open_review_packets(packet_index: Mapping[str, Any]) -> list[dict[str, Any]]:
    packets: list[dict[str, Any]] = []
    for packet in packet_index.get("packets") or []:
        if not isinstance(packet, Mapping):
            continue
        status = str(packet.get("status") or packet.get("review_decision_status") or "")
        if (
            packet.get("operator_decision_required") is True
            and packet.get("completed") is not True
            and packet.get("visible_by_default") is not False
            and status not in {"OPERATOR_REVIEW_RECORDED", "INFORMATIONAL_REVIEW_CLOSED"}
            and packet.get("business_action_performed") is not True
            and packet.get("git_push_performed") is not True
        ):
            packets.append(dict(packet))
    return packets


def _decision_actions(contract: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows = contract.get("decision_actions")
    if isinstance(rows, list) and rows:
        return [dict(row) for row in rows if isinstance(row, Mapping)]
    return [
        {"decision_action": "approve_review_packet_for_record", "display_label": "Approve for record"},
        {"decision_action": "request_review_packet_rework", "display_label": "Request rework"},
        {"decision_action": "mark_review_packet_informational", "display_label": "Mark informational"},
    ]


def _approval_by_gate(queue: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    approvals: dict[str, dict[str, Any]] = {}
    for item in queue.get("approval_requests") or []:
        if isinstance(item, Mapping):
            gate_ref = str(item.get("gate_ref") or "")
            if gate_ref:
                approvals[gate_ref] = dict(item)
    return approvals


def _check_engine_actions(sources: Mapping[str, Mapping[str, Any]]) -> list[dict[str, Any]]:
    proof_refs = [
        "generated/read_models/chief_check_engine_diagnostic_package.json",
        "generated/read_models/chief_check_engine_environment_posture.json",
    ]
    return [
        _action_payload(
            action_id="chief_diagnostic.open",
            label="Open Chief diagnostic",
            action_type="navigate",
            target_world_ref="system",
            target_thread_ref="chief_diagnostic",
            payload={
                "payload_ref": "generated/read_models/chief_check_engine_diagnostic_package.json",
                "environment_posture_ref": "generated/read_models/chief_check_engine_environment_posture.json",
                "payload_ref_semantics": "chief_check_engine_diagnostic_package / environment posture",
                "repair_authority": False,
                "no_repair_authority": True,
            },
            proof_refs=proof_refs,
        )
    ]


def _review_packet_actions(sources: Mapping[str, Mapping[str, Any]]) -> list[dict[str, Any]]:
    packet_index = sources.get("workroom_review_packet_index", {})
    contract = sources.get("workroom_review_decision_contract", {})
    actions: list[dict[str, Any]] = []
    for packet in _open_review_packets(packet_index):
        packet_id = str(packet.get("review_packet_id") or "")
        channel_ref = str(packet.get("channel_ref") or "build_openclaw_backend")
        packet_slug = _slug(packet_id or _short_hash(packet))
        proof_refs = [
            "generated/read_models/workroom_review_packet_index.json",
            "generated/read_models/workroom_review_decision_contract.json",
        ]
        proof_refs.extend(str(ref) for ref in packet.get("proof_refs") or [] if str(ref))
        actions.append(
            _action_payload(
                action_id=f"review_packet.{packet_slug}.open",
                label="Open review packet",
                action_type="navigate",
                target_world_ref="build",
                target_thread_ref=channel_ref,
                payload={
                    "review_packet_id": packet_id,
                    "package_id": str(packet.get("package_id") or ""),
                    "worker_ref": str(packet.get("worker_ref") or ""),
                    "channel_ref": channel_ref,
                    "merge_allowed": False,
                    "push_allowed": False,
                    "git_push_allowed": False,
                },
                proof_refs=proof_refs,
            )
        )
        for decision in _decision_actions(contract):
            decision_action = str(decision.get("decision_action") or "")
            label = str(decision.get("display_label") or decision_action.replace("_", " ").title())
            actions.append(
                _action_payload(
                    action_id=f"review_packet.{packet_slug}.{_slug(decision_action)}",
                    label=label,
                    action_type="review_decision",
                    target_world_ref="build",
                    target_thread_ref=channel_ref,
                    payload={
                        "request_type": "WORKROOM_REVIEW_DECISION_REQUEST_V0",
                        "kind": "WORKROOM_REVIEW_DECISION_REQUEST",
                        "source_surface": "mission_control",
                        "requested_mode": "operator",
                        "result_receipt_required": True,
                        "review_packet_id": packet_id,
                        "decision_action": decision_action,
                        "reason": "",
                        "authority_boundary": dict(AUTHORITY_BOUNDARY),
                        "merge_allowed": False,
                        "push_allowed": False,
                        "business_action_allowed": False,
                    },
                    proof_refs=proof_refs,
                )
            )
    return actions


def _capital_hilton_actions(sources: Mapping[str, Mapping[str, Any]]) -> list[dict[str, Any]]:
    proposal = sources.get("capital_hilton_business_development_proposal", {})
    invoice_status = sources.get("capital_hilton_invoice_operator_run_status", {})
    proposal_refs = [
        "generated/read_models/capital_hilton_business_development_proposal.json",
        *_proof_refs(proposal.get("proof_refs")),
    ]
    invoice_refs = [
        "generated/read_models/capital_hilton_invoice_operator_run_status.json",
        *_proof_refs(invoice_status.get("proof_refs")),
    ]
    return [
        _action_payload(
            action_id="capital_hilton.payment.ask_why",
            label="Ask why",
            action_type="system_question",
            target_world_ref="finance",
            target_thread_ref="capital_hilton",
            controller_event_type="ask_why",
            control_scope="lane",
            text_response_preferred=True,
            payload={
                "question_id": "capital_hilton_payment_watch_lane",
                "question_text": "Why am I here?",
                "workflow_ref": "capital_hilton_invoice_payment_watch",
                "client_ref": "capital_hilton",
                "text_response_preferred": True,
                "control_scope": "lane",
                "expected_response_scenario": "finance_capital_hilton_payment_watch",
                "source_card_id": "dynamic_card.finance.capital_hilton.payment_watch",
            },
            proof_refs=invoice_refs,
        ),
        _action_payload(
            action_id="capital_hilton.payment.advance_objective",
            label="Advance payment watch",
            action_type="objective_advancement",
            target_world_ref="finance",
            target_thread_ref="capital_hilton",
            controller_event_type="advance_objective",
            control_scope="lane",
            text_response_preferred=True,
            payload={
                "objective_ref": "objective:finance:capital_hilton:payment_watch",
                "workflow_ref": "capital_hilton_invoice_payment_watch",
                "client_ref": "capital_hilton",
                "next_safe_controller_event": "attach_proof",
                "requires_payment_evidence": True,
                "ledger_mutation_allowed": False,
                "paid_marking_allowed": False,
                "coupa_allowed": False,
                "browser_access_allowed": False,
                "text_response_preferred": True,
                "control_scope": "lane",
                "expected_response_scenario": "finance_capital_hilton_payment_watch",
                "source_card_id": "dynamic_card.finance.capital_hilton.payment_watch",
                "authority_boundary": dict(AUTHORITY_BOUNDARY),
            },
            proof_refs=invoice_refs,
        ),
        _action_payload(
            action_id="capital_hilton.proposal.stage_followup",
            label="Stage proposal follow-up",
            action_type="stage_package_request",
            target_world_ref="business_development",
            target_thread_ref="capital_hilton",
            payload={
                "request_type": "WORKFLOW_PACKAGE_REQUEST_V0",
                "kind": "OPERATOR_INSTRUCTION_PACKAGE_REQUEST",
                "source_surface": "mission_control",
                "requested_mode": "dry_run_package_only",
                "workflow_ref": "capital_hilton_proposal_followup",
                "client_ref": "capital_hilton",
                "target_agent_refs": ["cassandra", "clara"],
                "package_goal": "Draft a Capital Hilton proposal follow-up package for operator review.",
                "result_receipt_required": True,
                "email_send_allowed": False,
                "authority_boundary": dict(AUTHORITY_BOUNDARY),
            },
            proof_refs=proposal_refs,
        ),
        _action_payload(
            action_id="capital_hilton.payment.record_proof",
            label="Attach payment evidence",
            action_type="record_payment_proof_intake",
            enabled=True,
            target_world_ref="finance",
            target_thread_ref="capital_hilton",
            controller_event_type="attach_proof",
            control_scope="lane",
            text_response_preferred=True,
            payload={
                "request_type": "CAPITAL_HILTON_PAYMENT_PROOF_INTAKE_REQUEST_V0",
                "source_surface": "mission_control",
                "client_ref": "capital_hilton",
                "workflow_ref": "capital_hilton_invoice_payment_watch",
                "requires_payment_evidence": True,
                "artifact_required": True,
                "ledger_mutation_allowed": False,
                "ledger_posting_allowed": False,
                "paid_marking_allowed": False,
                "text_response_preferred": True,
                "control_scope": "lane",
                "expected_response_scenario": "finance_capital_hilton_payment_watch",
                "source_card_id": "dynamic_card.finance.capital_hilton.payment_watch",
                "authority_boundary": dict(AUTHORITY_BOUNDARY),
            },
            proof_refs=invoice_refs,
        ),
        _action_payload(
            action_id="capital_hilton.payment.open_finance",
            label="Open Finance / Capital Hilton",
            action_type="navigate",
            target_world_ref="finance",
            target_thread_ref="capital_hilton",
            payload={
                "payload_ref": "generated/read_models/capital_hilton_invoice_operator_run_status.json",
                "reason": "Payment proof is not ready to record; inspect the finance lane instead.",
            },
            proof_refs=invoice_refs,
        ),
    ]


def _workbook_actions(sources: Mapping[str, Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [
        _action_payload(
            action_id="client_invoice_workbook.register",
            label="Register workbook",
            action_type="workbook_registration",
            target_world_ref="finance",
            target_thread_ref="capital_hilton",
            payload={
                "request_type": "WORKBOOK_REGISTRATION_REQUEST_V0",
                "kind": "WORKBOOK_REGISTRATION_REQUEST",
                "source_surface": "mission_control",
                "client_ref": "capital_hilton",
                "workflow_ref": "capital_hilton_invoice_workflow",
                "selected_local_path": "",
                "selected_local_path_required": True,
                "file_display_name": "",
                "file_extension": "",
                "source_surface_contract": "mission_control",
                "no_workbook_mutation": True,
                "workbook_body_read_allowed": False,
                "spreadsheet_cell_read_allowed": False,
                "authority_boundary": dict(AUTHORITY_BOUNDARY),
            },
            proof_refs=["generated/read_models/client_invoice_workbook_registry.json"],
        )
    ]


def _guardian_actions(sources: Mapping[str, Mapping[str, Any]]) -> list[dict[str, Any]]:
    surface = sources.get("helm_actionability_surface", {})
    approvals = _approval_by_gate(sources.get("approval_request_queue", {}))
    actions: list[dict[str, Any]] = []
    for item in surface.get("guardian_checklist") or []:
        if not isinstance(item, Mapping):
            continue
        label = str(item.get("plain_label") or "")
        gate_ref = GATE_REFS_BY_LABEL.get(label, _slug(label))
        world_ref, thread_ref = DEFAULT_GATE_LANES.get(gate_ref, ("system", "guardian"))
        proof_refs = ["generated/read_models/helm_actionability_surface.json"]
        if gate_ref in approvals:
            proof_refs.append("generated/read_models/approval_request_queue.json")
        gate_payload = {
            "gate_ref": gate_ref,
            "plain_label": label,
                "why_it_matters": str(item.get("why_it_matters") or ""),
                "status": str(item.get("status") or ""),
                "safe_actions_only": True,
                "control_scope": "gate",
            }
        actions.append(
            _action_payload(
                action_id=f"guardian_gate.{gate_ref}.explain",
                label="Explain this gate",
                action_type="explain_gate",
                target_world_ref="system",
                target_thread_ref="guardian",
                controller_event_type="ask_why",
                control_scope="gate",
                text_response_preferred=True,
                payload=gate_payload,
                proof_refs=proof_refs,
            )
        )
        actions.append(
            _action_payload(
                action_id=f"guardian_gate.{gate_ref}.open",
                label="Open relevant lane",
                action_type="navigate",
                target_world_ref=world_ref,
                target_thread_ref=thread_ref,
                control_scope="gate",
                payload={**gate_payload, "open_lane_only": True},
                proof_refs=proof_refs,
            )
        )
        approval = approvals.get(gate_ref)
        if approval:
            actions.append(
                _action_payload(
                    action_id=f"guardian_gate.{gate_ref}.stage_approval_request",
                    label="Stage approval request",
                    action_type="stage_package_request",
                    target_world_ref=str(approval.get("target_world_ref") or world_ref),
                    target_thread_ref=str(approval.get("target_thread_ref") or thread_ref),
                    control_scope="gate",
                    payload={
                        **gate_payload,
                        "approval_request_id": str(approval.get("approval_request_id") or ""),
                        "requested_action": str(approval.get("requested_action") or ""),
                        "safe_options": list(approval.get("safe_options") or []),
                        "forbidden_options": list(approval.get("forbidden_options") or []),
                        "approval_queue_ref": "generated/read_models/approval_request_queue.json",
                        "stage_only": True,
                        "authority_boundary": dict(AUTHORITY_BOUNDARY),
                    },
                    proof_refs=proof_refs,
                )
            )
    return actions


def _question_actions(sources: Mapping[str, Mapping[str, Any]]) -> list[dict[str, Any]]:
    surface = sources.get("helm_actionability_surface", {})
    actions: list[dict[str, Any]] = []
    for item in surface.get("suggested_questions") or []:
        if not isinstance(item, Mapping):
            continue
        question_id = str(item.get("question_id") or _short_hash(item.get("question_text") or "question"))
        question_text = str(item.get("question_text") or "")
        source_action = item.get("action") if isinstance(item.get("action"), Mapping) else {}
        target_world = str(source_action.get("target_world_ref") or "system")
        target_thread = str(source_action.get("target_thread_ref") or "questions")
        precomputed_answer_ref = (
            f"generated/read_models/helm_actionability_surface.json#suggested_questions.{question_id}.precomputed_answer"
            if isinstance(item.get("precomputed_answer"), Mapping)
            else ""
        )
        actions.append(
            _action_payload(
                action_id=f"helm_question.{_slug(question_id)}.ask",
                label=question_text,
                action_type="system_question",
                target_world_ref=target_world,
                target_thread_ref=target_thread,
                payload={
                    "question_id": question_id,
                    "question_text": question_text,
                    "precomputed_answer_ref": precomputed_answer_ref,
                    "target_lane": {
                        "target_world_ref": target_world,
                        "target_thread_ref": target_thread,
                    },
                    "source_action": dict(source_action),
                },
                proof_refs=["generated/read_models/helm_actionability_surface.json"],
            )
        )
    return actions


def _payload_index(actions: list[dict[str, Any]]) -> dict[str, list[str]]:
    index: dict[str, list[str]] = {}
    for action in actions:
        payload = action.get("payload") if isinstance(action.get("payload"), Mapping) else {}
        for key in (
            "review_packet_id",
            "gate_ref",
            "question_id",
            "workflow_ref",
            "client_ref",
            "payload_ref",
        ):
            value = str(payload.get(key) or "")
            if value:
                index.setdefault(f"{key}:{value}", []).append(str(action["action_id"]))
    return {key: sorted(set(value)) for key, value in sorted(index.items())}


def _walk_values(payload: Any):
    if isinstance(payload, Mapping):
        for key, value in payload.items():
            yield str(key), value
            yield from _walk_values(value)
    elif isinstance(payload, list):
        for value in payload:
            yield from _walk_values(value)


def _unsafe_true_grants(payload: Mapping[str, Any]) -> list[str]:
    grants: list[str] = []
    for key, value in _walk_values(payload):
        if key in UNSAFE_TRUE_KEYS and value is True:
            grants.append(key)
    return sorted(set(grants))


def build_operator_action_payloads(
    *,
    source_paths: Mapping[str, Path] | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    source_paths = source_paths or DEFAULT_SOURCE_PATHS
    sources = _source_payloads(source_paths)
    actions: list[dict[str, Any]] = []
    for builder in (
        _check_engine_actions,
        _review_packet_actions,
        _capital_hilton_actions,
        _workbook_actions,
        _guardian_actions,
        _question_actions,
    ):
        actions.extend(builder(sources))
    actions = sorted(actions, key=lambda action: str(action["action_id"]))
    source_read_models = [
        path.as_posix() if path.is_absolute() else path.as_posix()
        for path in source_paths.values()
    ]
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "status": READY_STATUS,
        "generated_at": generated_at,
        "action_types": ACTION_TYPES,
        "action_payloads": actions,
        "action_payload_count": len(actions),
        "action_payload_ids": [str(action["action_id"]) for action in actions],
        "payload_index": _payload_index(actions),
        "source_read_models": source_read_models,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "machine_proof": {
            "payloads_are_render_contracts_only": True,
            "actions_execute_nothing": True,
            "all_actions_have_authority_boundary": all(isinstance(action.get("authority_boundary"), Mapping) for action in actions),
            "all_actions_have_required_render_fields": all(
                action.get("label")
                and action.get("action_type") in ACTION_TYPES
                and "enabled" in action
                and "safe_to_render_button" in action
                for action in actions
            ),
            "check_engine_has_no_repair_authority": True,
            "review_packet_has_no_merge_or_push_authority": True,
            "business_development_followup_is_draft_package_only": True,
            "payment_proof_does_not_mutate_ledger": True,
            "workbook_registration_does_not_read_or_mutate_workbook": True,
            "guardian_actions_are_explain_open_or_stage_only": True,
            "suggested_questions_have_system_question_payloads": True,
            "email_send_performed": False,
            "gmail_opened": False,
            "browser_or_coupa_opened": False,
            "ledger_mutation_performed": False,
            "workbook_mutation_performed": False,
            "pdf_export_performed": False,
            "portal_submit_performed": False,
            "paid_marking_performed": False,
            "git_push_performed": False,
            "worker_spawn_performed": False,
            "agent_loop_started": False,
            "unsafe_true_grants": [],
            "unsafe_true_grants_absent": True,
        },
    }
    unsafe = _unsafe_true_grants(payload)
    payload["machine_proof"]["unsafe_true_grants"] = unsafe
    payload["machine_proof"]["unsafe_true_grants_absent"] = not unsafe
    return payload


def _wiki_text(payload: Mapping[str, Any]) -> str:
    actions = payload.get("action_payloads") if isinstance(payload.get("action_payloads"), list) else []
    by_type: dict[str, int] = {}
    for action in actions:
        if isinstance(action, Mapping):
            by_type[str(action.get("action_type") or "none")] = by_type.get(str(action.get("action_type") or "none"), 0) + 1
    lines = [
        "# Operator Action Payloads",
        "",
        f"Status: `{payload.get('status', READY_STATUS)}`",
        "",
        "This read-model gives Mac cards safe backend button payloads. It is a render/stage contract only.",
        "",
        "## Counts",
        "",
        f"- Payloads: `{payload.get('action_payload_count', 0)}`",
    ]
    for action_type, count in sorted(by_type.items()):
        lines.append(f"- `{action_type}`: `{count}`")
    lines.extend(
        [
            "",
            "## Payloads",
            "",
        ]
    )
    for action in actions:
        if not isinstance(action, Mapping):
            continue
        target = f"{action.get('target_world_ref')}/{action.get('target_thread_ref')}".strip("/")
        lines.append(f"- `{action.get('action_id')}` - {action.get('label')} ({action.get('action_type')}, {target})")
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            "No payload grants email send, Gmail, browser, Coupa, portal submit, ledger posting, workbook mutation, PDF export, paid/sent truth, merge, push, repair authority, worker spawn, child agents, or agent loops.",
            "",
        ]
    )
    return "\n".join(lines)


def write_outputs(
    *,
    export_root: Path = DEFAULT_EXPORT_ROOT,
    wiki_path: Path = DEFAULT_WIKI_PATH,
    bridge_root: Path | None = DEFAULT_BRIDGE_ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    payload = build_operator_action_payloads(generated_at=generated_at)
    rooted_export = _rooted(export_root)
    rooted_wiki = _rooted(wiki_path)
    rooted_export.mkdir(parents=True, exist_ok=True)
    rooted_wiki.parent.mkdir(parents=True, exist_ok=True)
    json_path = rooted_export / JSON_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    rooted_wiki.write_text(_wiki_text(payload), encoding="utf-8")
    if bridge_root is not None:
        bridge_root.mkdir(parents=True, exist_ok=True)
        shutil.copy2(json_path, bridge_root / JSON_EXPORT_NAME)
    return payload


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Publish operator action payloads.")
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT))
    parser.add_argument("--wiki-path", default=str(DEFAULT_WIKI_PATH))
    parser.add_argument("--bridge-root", default=str(DEFAULT_BRIDGE_ROOT))
    parser.add_argument("--no-bridge", action="store_true")
    parser.add_argument("--generated-at")
    parser.add_argument("--format", choices=("json", "summary"), default="summary")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    payload = write_outputs(
        export_root=Path(args.export_root),
        wiki_path=Path(args.wiki_path),
        bridge_root=None if args.no_bridge else Path(args.bridge_root),
        generated_at=args.generated_at,
    )
    if args.format == "json":
        print(stable_json(payload), end="")
    else:
        print(f"{payload['status']}: {payload['action_payload_count']} payloads")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
