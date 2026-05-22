"""Capital Hilton Proof Metadata Packet v0 for OpenClaw.

This read-model defines protected proof metadata requirements for the Capital
Hilton invoice / finance steel thread. It is metadata only: no Coupa access,
browser/OAuth/account access, credentials, Gmail/calendar/email account access,
Excel raw body ingestion, raw finance/private body ingestion, invoice
generation, send/submit/approval, model/API execution, agent activation, tool
execution, queue/autonomy, Repo B inspection, Mac sync/import, network
operation, or PC system-drive writes are created.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
DEFAULT_EXPORT_ROOT = Path("generated/read_models")

SCHEMA_VERSION = "capital_hilton_proof_metadata_packet_v0"
JSON_EXPORT_NAME = "capital_hilton_proof_metadata_packet.json"
OPERATOR_EXPORT_NAME = "capital_hilton_proof_metadata_packet_OPERATOR.md"

NO_AUTHORITY_FLAGS = {
    "coupa_access_allowed": False,
    "browser_oauth_allowed": False,
    "credential_handling_allowed": False,
    "gmail_calendar_access_allowed": False,
    "excel_raw_body_ingestion_allowed": False,
    "raw_finance_body_ingestion_allowed": False,
    "invoice_generation_allowed": False,
    "send_submit_approval_allowed": False,
    "account_access_allowed": False,
    "model_call_allowed": False,
    "model_api_execution_allowed": False,
    "model_router_runtime_allowed": False,
    "agent_activation_allowed": False,
    "tool_execution_allowed": False,
    "queue_execution_allowed": False,
    "runtime_dispatch_allowed": False,
    "planner_builder_execution_allowed": False,
    "hidden_memory_allowed": False,
    "external_retained_memory_allowed": False,
    "broad_filesystem_indexing_allowed": False,
    "broad_private_file_inspection_allowed": False,
    "repo_b_mutation_allowed": False,
    "repo_b_body_inspection_allowed": False,
    "mission_control_app_changes_included": False,
    "mac_sync_or_import_triggered": False,
    "network_operation_allowed": False,
    "pc_c_drive_artifact_write_allowed": False,
    "operator_final_authority": True,
}

PROOF_CATEGORIES = (
    "CANDIDATE_FACT",
    "METADATA_PROOF",
    "PROTECTED_PROOF",
    "BLOCKED_RAW_BODY",
    "MISSING_PROOF",
    "FUTURE_ACTION_PROOF",
)

OPERATOR_QUESTION_CLASSIFICATIONS = (
    "memory_only_clarification",
    "proof_needed",
    "protected_proof_needed",
    "security_gate_needed",
    "world_transition_needed",
)

SOURCE_READ_MODELS = (
    ("capital_hilton_actionable_review_packet", "generated/read_models/capital_hilton_actionable_review_packet.json", "review-only Capital Hilton fact posture"),
    ("cassandra_governed_review_packet_request_proof", "generated/read_models/cassandra_governed_review_packet_request_proof.json", "Cassandra governed review proof request"),
    ("capital_hilton_coupa_execution_path", "generated/read_models/capital_hilton_coupa_execution_path.json", "future-gated Hilton/Coupa overlay posture"),
    ("capital_hilton_external_artifact_proof_capture", "generated/read_models/capital_hilton_external_artifact_proof_capture.json", "external artifact proof capture posture"),
    ("agent_identity_actor_router_contract", "generated/read_models/agent_identity_actor_router_contract.json", "actor identity and routing"),
    ("agent_package_preview_contract", "generated/read_models/agent_package_preview_contract.json", "package preview contract"),
    ("package_preview_receipt_contract", "generated/read_models/package_preview_receipt_contract.json", "package preview receipt grammar"),
    ("model_selection_receipt_contract", "generated/read_models/model_selection_receipt_contract.json", "model selection receipt grammar"),
    ("tool_adapter_receipt_contract", "generated/read_models/tool_adapter_receipt_contract.json", "tool adapter receipt grammar"),
    ("memory_candidate_receipt_contract", "generated/read_models/memory_candidate_receipt_contract.json", "memory candidate receipt grammar"),
    ("agent_memory_scope_contract", "generated/read_models/agent_memory_scope_contract.json", "memory scope boundary"),
    ("tool_protocol_adapter_registry_contract", "generated/read_models/tool_protocol_adapter_registry_contract.json", "tool adapter registry"),
    ("agent_terrain_awareness_readback_contract", "generated/read_models/agent_terrain_awareness_readback_contract.json", "terrain/dossier awareness"),
    ("stable_map_bundle", "generated/read_models/openclaw_map_manifest.json", "app-facing stable map generation"),
    ("threshold_map_contract", "generated/read_models/operator_threshold_map_contract.json", "threshold/world lane destiny"),
)

CANDIDATE_FACT_SLOTS = (
    ("completed_performance_dates", "Completed performance date(s)", "completed_service_dates", True),
    ("service_performance_description", "Service/performance description", None, True),
    ("rate", "Rate", "rate_or_amount_per_gig", True),
    ("subtotal", "Subtotal", "candidate_subtotal", True),
    ("customer_client_identity", "Customer/client identity", None, False),
    ("invoice_recipient_or_ap_route", "Invoice recipient or AP route", "recipient_posture_review_only", True),
    ("po_coupa_reference", "PO/Coupa reference", "po_or_portal_gate_status", True),
    ("excel_workbook_reference", "Excel/workbook reference", None, True),
    ("payment_status_reference", "Payment/status reference", None, True),
    ("tax_vendor_payment_handling_assumptions", "Tax/vendor/payment handling assumptions", None, True),
    ("invoice_shape_one_invoice_posture", "Invoice shape / one-invoice posture", "invoice_count_posture", True),
    ("final_invoice_packet_requirement", "Final invoice packet requirement", None, True),
)

REQUIRED_PROOF_METADATA_RECORDS = (
    {
        "proof_metadata_id": "performance_date_proof_metadata",
        "purpose": "Proves the performance date(s) worked before invoice action.",
        "expected_candidate_values": ("2026-05-08", "2026-05-15"),
        "source_expectation": "approved calendar/source-card/receipt/metadata ref; raw calendar/email bodies blocked",
        "required_for_security_audit": True,
        "required_for_finance_world_action": True,
        "raw_body_policy": "raw calendar/email bodies blocked",
    },
    {
        "proof_metadata_id": "rate_proof_metadata",
        "purpose": "Proves the rate, including the candidate $400/gig posture if supported.",
        "expected_candidate_values": ("$400 per gig",),
        "source_expectation": "approved source card, contract metadata, packet metadata, or operator-confirmed proof ref",
        "required_for_security_audit": True,
        "required_for_finance_world_action": True,
        "raw_body_policy": "raw contract/email body blocked unless protected metadata exists",
    },
    {
        "proof_metadata_id": "subtotal_proof_metadata",
        "purpose": "Proves invoice arithmetic after date and rate proof exist.",
        "expected_candidate_values": ("$800 candidate subtotal when two $400 performances are proven",),
        "source_expectation": "machine-derived arithmetic receipt only after date/rate proof metadata exists",
        "required_for_security_audit": True,
        "required_for_finance_world_action": True,
        "raw_body_policy": "no raw finance body required",
    },
    {
        "proof_metadata_id": "coupa_po_or_payment_reference_metadata",
        "purpose": "Proves Coupa, PO, or payment route metadata if present.",
        "expected_candidate_values": ("PO/Coupa unknown",),
        "source_expectation": "metadata-only Coupa/PO/payment reference after Guardian and Operator gates",
        "required_for_security_audit": True,
        "required_for_finance_world_action": True,
        "raw_body_policy": "Coupa access, credentials, browser/OAuth, and account session blocked",
    },
    {
        "proof_metadata_id": "excel_workbook_reference_metadata",
        "purpose": "Proves the workbook/source row exists if relevant.",
        "expected_candidate_values": ("workbook reference metadata only",),
        "source_expectation": "workbook filename/source-card/row metadata; no cell body or formulas",
        "required_for_security_audit": True,
        "required_for_finance_world_action": True,
        "raw_body_policy": "raw Excel body and workbook parsing blocked",
    },
    {
        "proof_metadata_id": "invoice_source_card_metadata",
        "purpose": "Proves what a future invoice packet should include.",
        "expected_candidate_values": ("invoice source card metadata",),
        "source_expectation": "approved invoice packet metadata and proof refs",
        "required_for_security_audit": True,
        "required_for_finance_world_action": True,
        "raw_body_policy": "raw private finance bodies blocked",
    },
    {
        "proof_metadata_id": "ap_recipient_route_metadata",
        "purpose": "Proves the AP recipient/payment route before any future send or submit lane.",
        "expected_candidate_values": ("AP route unknown or review-only",),
        "source_expectation": "metadata-only AP route/source-card; account access blocked",
        "required_for_security_audit": True,
        "required_for_finance_world_action": True,
        "raw_body_policy": "email/account bodies blocked",
    },
    {
        "proof_metadata_id": "guardian_protected_access_gate_metadata",
        "purpose": "Proves whether protected material is eligible for metadata-only review.",
        "expected_candidate_values": ("Guardian gate required",),
        "source_expectation": "Guardian gate receipt; no self-authorization",
        "required_for_security_audit": True,
        "required_for_finance_world_action": True,
        "raw_body_policy": "protected material remains metadata-only unless future gate permits scoped reference",
    },
    {
        "proof_metadata_id": "operator_confirmation_metadata",
        "purpose": "Captures operator memory/confirmation as candidate context only.",
        "expected_candidate_values": ("operator confirmation receipt candidate",),
        "source_expectation": "Memory Candidate Receipt, not machine proof by itself",
        "required_for_security_audit": True,
        "required_for_finance_world_action": False,
        "raw_body_policy": "operator statement can clarify but cannot include secrets or raw private bodies",
    },
    {
        "proof_metadata_id": "future_invoice_generation_receipt_requirement",
        "purpose": "Defines the future receipt required after security audit for any invoice generation.",
        "expected_candidate_values": ("future action receipt shape only",),
        "source_expectation": "future invoice generation receipt, Coupa submission receipt, or approval receipt if gates ever allow",
        "required_for_security_audit": False,
        "required_for_finance_world_action": True,
        "raw_body_policy": "not executable now; no invoice generation authority",
    },
)


@dataclass(frozen=True)
class CapitalHiltonProofPacketExportResult:
    schema_version: str
    json_path: str
    operator_path: str
    proof_metadata_record_count: int
    candidate_fact_count: int
    missing_proof_count: int
    protected_proof_required: bool
    live_authority_added: bool


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _content_hash(payload: dict[str, Any]) -> str:
    clone = json.loads(stable_json(payload))
    clone.get("machine_proof", {}).pop("content_hash", None)
    return "sha256:" + hashlib.sha256(stable_json(clone).encode("utf-8")).hexdigest()


def _read_json_if_present(repo_root: str | Path, relative_path: str) -> dict[str, Any]:
    path = Path(repo_root) / relative_path
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _source_record(repo_root: str | Path, source_id: str, path: str, role: str) -> dict[str, Any]:
    payload = _read_json_if_present(repo_root, path)
    return {
        "source_id": source_id,
        "path": path,
        "role": role,
        "present": bool(payload),
        "schema_version": payload.get("schema_version"),
        "raw_body_imported": False,
        "credential_or_secret_imported": False,
        "authority_granted_by_source_presence": False,
    }


def _first_read_model_payload(repo_root: str | Path, source_id: str) -> dict[str, Any]:
    for candidate_id, path, _role in SOURCE_READ_MODELS:
        if candidate_id == source_id:
            return _read_json_if_present(repo_root, path)
    return {}


def _invoice_fact_map(actionable_packet: dict[str, Any]) -> dict[str, dict[str, Any]]:
    facts = actionable_packet.get("invoice_facts")
    if not isinstance(facts, list):
        return {}
    mapped: dict[str, dict[str, Any]] = {}
    for fact in facts:
        if isinstance(fact, dict) and fact.get("field_name"):
            mapped[str(fact["field_name"])] = fact
    return mapped


def _candidate_value(
    slot_id: str,
    source_key: str | None,
    domain_summary: dict[str, Any],
    domain_summary_ref: str | None,
    fact_map: dict[str, dict[str, Any]],
) -> tuple[Any, str | None, str]:
    if source_key and source_key in domain_summary:
        return domain_summary[source_key], domain_summary_ref, "parsed_evidence_not_truth"
    if source_key and source_key in fact_map:
        fact = fact_map[source_key]
        return fact.get("value_text"), "generated/read_models/capital_hilton_actionable_review_packet.json#invoice_facts", str(fact.get("evidence_status") or "parsed_evidence_not_truth")
    if slot_id == "customer_client_identity":
        return "Capital Hilton", "stable_map/threshold terrain lane identity", "lane_identity_not_invoice_proof"
    if slot_id == "service_performance_description":
        return None, None, "not_discovered"
    if slot_id == "excel_workbook_reference":
        attachment = fact_map.get("invoice_attachment_output_path", {})
        value = attachment.get("value_text")
        if value:
            return "workbook metadata/reference mentioned; raw cells not read", "generated/read_models/capital_hilton_actionable_review_packet.json#invoice_facts", "metadata_reference_not_workbook_proof"
    if slot_id == "final_invoice_packet_requirement":
        return "future final invoice packet required after security audit", "package_preview_receipt_contract", "future_action_proof_required"
    return None, None, "missing_proof"


def _candidate_fact_record(
    slot_id: str,
    label: str,
    source_key: str | None,
    protected_required: bool,
    domain_summary: dict[str, Any],
    domain_summary_ref: str | None,
    fact_map: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    value, source_reference, source_authority_status = _candidate_value(slot_id, source_key, domain_summary, domain_summary_ref, fact_map)
    present = value is not None and value != ""
    proof_status = "CANDIDATE_FACT_NOT_PROVEN" if present else "MISSING_PROOF"
    if slot_id in {"customer_client_identity", "final_invoice_packet_requirement"} and present:
        proof_status = "METADATA_CONTEXT_NOT_FINAL_INVOICE_PROOF"
    return {
        "fact_id": slot_id,
        "display_name": label,
        "current_value": value,
        "current_status": "candidate_fact" if present else "missing_proof",
        "proof_category": "CANDIDATE_FACT" if present else "MISSING_PROOF",
        "proof_status": proof_status,
        "source_reference": source_reference,
        "source_authority_status": source_authority_status,
        "machine_proven": False,
        "operator_memory_only": source_authority_status in {"parsed_evidence_not_truth", "lane_identity_not_invoice_proof"},
        "protected_proof_required": protected_required,
        "guardian_review_required": protected_required,
        "operator_confirmation_required": True,
        "raw_body_included": False,
        "what_would_prove_it": _proof_needed_for_fact(slot_id),
    }


def _proof_needed_for_fact(slot_id: str) -> str:
    return {
        "completed_performance_dates": "performance_date_proof_metadata with approved metadata refs",
        "service_performance_description": "service/performance source card or invoice packet metadata",
        "rate": "rate_proof_metadata from approved source card or protected metadata",
        "subtotal": "subtotal_proof_metadata after date and rate proof exist",
        "customer_client_identity": "invoice source card or client metadata ref",
        "invoice_recipient_or_ap_route": "ap_recipient_route_metadata",
        "po_coupa_reference": "coupa_po_or_payment_reference_metadata",
        "excel_workbook_reference": "excel_workbook_reference_metadata",
        "payment_status_reference": "payment/status proof metadata or ledger receipt",
        "tax_vendor_payment_handling_assumptions": "operator-reviewed vendor/payment handling metadata",
        "invoice_shape_one_invoice_posture": "operator confirmation plus invoice source metadata",
        "final_invoice_packet_requirement": "future invoice generation receipt requirement after security audit",
    }[slot_id]


def _proof_metadata_record(record: dict[str, Any]) -> dict[str, Any]:
    protected = record["proof_metadata_id"] not in {"operator_confirmation_metadata", "future_invoice_generation_receipt_requirement"}
    return {
        **record,
        "proof_category": "PROTECTED_PROOF" if protected else "FUTURE_ACTION_PROOF" if record["proof_metadata_id"].startswith("future") else "METADATA_PROOF",
        "current_status": "missing_proof_metadata",
        "current_proof_present": False,
        "protected_proof_required": protected,
        "guardian_gate_required": protected,
        "operator_approval_required": True,
        "allowed_now": "metadata requirement display only",
        "blocked_now": [
            "raw body ingestion",
            "account/browser/Coupa/Gmail/calendar access",
            "send/submit/approval",
            "invoice generation",
        ],
        "receipt_requirement": "future receipt required before action; current packet only defines shape",
        "raw_body_included": False,
    }


def _operator_question(question_id: str, question: str, classification: str) -> dict[str, Any]:
    if classification not in OPERATOR_QUESTION_CLASSIFICATIONS:
        raise ValueError(f"unknown question classification: {classification}")
    return {
        "question_id": question_id,
        "question": question,
        "classification": classification,
        "answer_becomes": "memory_candidate_receipt",
        "answer_is_machine_proof": False,
    }


def build_capital_hilton_proof_metadata_packet(
    *,
    repo_root: str | Path = ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    actionable_packet = _first_read_model_payload(repo_root, "capital_hilton_actionable_review_packet")
    governed_packet = _first_read_model_payload(repo_root, "cassandra_governed_review_packet_request_proof")
    coupa_path = _first_read_model_payload(repo_root, "capital_hilton_coupa_execution_path")
    actionable_summary = actionable_packet.get("domain_fact_summary") if isinstance(actionable_packet.get("domain_fact_summary"), dict) else {}
    governed_summary = governed_packet.get("domain_fact_summary") if isinstance(governed_packet.get("domain_fact_summary"), dict) else {}
    if actionable_summary:
        domain_summary = actionable_summary
        domain_summary_ref = "generated/read_models/capital_hilton_actionable_review_packet.json#domain_fact_summary"
    elif governed_summary:
        domain_summary = governed_summary
        domain_summary_ref = "generated/read_models/cassandra_governed_review_packet_request_proof.json#domain_fact_summary"
    else:
        domain_summary = {}
        domain_summary_ref = None
    fact_map = _invoice_fact_map(actionable_packet)
    evidence_sources = [_source_record(repo_root, source_id, path, role) for source_id, path, role in SOURCE_READ_MODELS]
    candidate_facts = [
        _candidate_fact_record(slot_id, label, source_key, protected_required, domain_summary, domain_summary_ref, fact_map)
        for slot_id, label, source_key, protected_required in CANDIDATE_FACT_SLOTS
    ]
    proof_metadata = [_proof_metadata_record(record) for record in REQUIRED_PROOF_METADATA_RECORDS]
    missing_proof = [
        record["proof_metadata_id"]
        for record in proof_metadata
        if record["current_proof_present"] is False
    ]
    candidate_fact_ids_present = [fact["fact_id"] for fact in candidate_facts if fact["current_status"] == "candidate_fact"]
    candidate_fact_ids_missing = [fact["fact_id"] for fact in candidate_facts if fact["current_status"] == "missing_proof"]
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": "capital_hilton_proof_metadata_packet",
        "generated_at": generated_at,
        **NO_AUTHORITY_FLAGS,
        "contract_status": "deterministic_capital_hilton_proof_metadata_only",
        "operator_summary": (
            "Capital Hilton is represented as a Finance steel-thread proof metadata packet. "
            "The packet shows candidate invoice facts, missing protected proof, actor/package/tool posture, "
            "and the gates needed before any future Finance World action."
        ),
        "core_doctrine": {
            "this_is_not_invoice_execution": True,
            "this_is_not_coupa_access": True,
            "this_is_not_excel_file_opening": True,
            "this_is_not_gmail_calendar_browser_account_work": True,
            "this_is_not_send_submit_approval": True,
            "this_is_not_raw_private_finance_body_ingestion": True,
            "operator_answers_become_memory_candidates_not_proof": True,
            "candidate_facts_are_not_machine_proof": True,
        },
        "proof_category_taxonomy": [
            {
                "proof_category": category,
                "meaning": _proof_category_meaning(category),
                "raw_body_allowed": False,
                "current_execution_authority": False,
            }
            for category in PROOF_CATEGORIES
        ],
        "evidence_sources": evidence_sources,
        "source_surface_posture": {
            "capital_hilton_actionable_review_packet_present": bool(actionable_packet),
            "cassandra_governed_review_packet_present": bool(governed_packet),
            "capital_hilton_coupa_execution_path_present": bool(coupa_path),
            "source_values_are_candidate_or_review_metadata": True,
            "raw_source_bodies_imported": False,
            "canonical_proof_claimed": False,
        },
        "capital_hilton_lane_fact_posture": {
            "lane_id": "capital_hilton",
            "current_phase": "HELM_THRESHOLD_LANE",
            "target_world": "Finance",
            "lane_destiny": "MOVE_TO_WORLD_ACTION",
            "workflow_type": "invoice_review_and_proof_metadata",
            "current_status": "proof_needed_preview_only",
            "known": [
                "Capital Hilton is the finance steel-thread candidate.",
                "The lane is a Helm threshold lane aimed at Finance World.",
                "Cassandra is the review persona; Guardian gates protected proof; Operator remains final authority.",
                "Current authority is metadata/readback only.",
            ],
            "partly_known": [
                "Completed dates, rate, subtotal, and one-invoice posture appear as candidate facts when supported by existing review read-models.",
                "Coupa/PO and workbook references are known only as protected metadata needs, not accessible sources.",
                "Cassandra packet posture is review-only and not financial truth.",
            ],
            "known_unknown": [
                "PO/Coupa/payment reference",
                "approved AP recipient route",
                "whether workbook metadata is sufficient",
                "payment/status proof",
                "tax/vendor/payment handling",
                "final invoice packet shape",
            ],
            "not_discovered": [
                "Guardian-approved protected proof metadata",
                "Coupa/PO proof metadata",
                "Excel/workbook row metadata",
                "future invoice generation receipt",
            ],
            "operator_memory_needed": [
                "dates/rate/one-invoice confirmation",
                "where proof likely lives",
                "whether Coupa, Excel, email, PDF, or existing packet should be the source of truth",
                "what would convince the operator the lane can move to Finance World action",
            ],
            "machine_proof_needed": missing_proof,
            "protected_proof_needed": [
                "performance/date/rate/source proof refs",
                "Coupa/PO/payment route metadata",
                "Excel/workbook metadata",
                "AP recipient route metadata",
                "Guardian protected access gate receipt",
            ],
            "safe_next_detour": "Capture operator answers as Memory Candidate Receipts and then build protected proof metadata references; do not access Coupa, Excel, Gmail, browser, or accounts.",
            "quiet_condition": "All candidate facts are either backed by protected metadata refs, rejected, or parked; security audit readiness is explicit; no live invoice action is implied.",
            "security_audit_readiness": "not_ready_until_missing_proof_metadata_and_gates_are_defined",
            "finance_world_action_readiness": "not_actionable_until_security_audit_and_proof_metadata_pass",
        },
        "capital_hilton_candidate_facts": candidate_facts,
        "required_proof_metadata": proof_metadata,
        "missing_proof_checklist": missing_proof,
        "actor_package_adapter_binding": {
            "actors_personas": [
                {
                    "actor_id": "cassandra",
                    "role": "finance/comms/AP preview and packet review",
                    "current_allowed": ["metadata readback", "package preview review", "missing proof labeling"],
                    "current_blocked": ["Coupa access", "raw Gmail/calendar bodies", "browser/OAuth", "credentials", "send", "submit", "approval", "account actions"],
                },
                {
                    "actor_id": "guardian",
                    "role": "protected proof / redaction / access gate",
                    "current_allowed": ["recommend block/redact/quarantine/revoke", "identify gate requirements"],
                    "current_blocked": ["self-authorization", "raw protected body access", "bypassing Operator"],
                },
                {
                    "actor_id": "operator_winship",
                    "role": "final action authority and memory clarification",
                    "current_allowed": ["answer memory questions", "approve or reject future gates"],
                    "current_blocked": ["turning memory statement into machine proof without receipt"],
                },
                {
                    "actor_id": "finance_world",
                    "role": "eventual world action target",
                    "current_allowed": ["preview future action candidate"],
                    "current_blocked": ["invoice execution before proof and security audit"],
                },
            ],
            "package_references": [
                "agent_package_preview_contract",
                "package_preview_receipt_contract",
                "model_selection_receipt_contract",
                "tool_adapter_receipt_contract",
                "memory_candidate_receipt_contract",
                "agent_memory_scope_contract",
                "tool_protocol_adapter_registry_contract",
                "agent_terrain_awareness_readback_contract",
                "stable_map_bundle",
                "threshold_map_contract",
            ],
            "tool_adapter_posture": [
                {"adapter_id": "cassandra_capital_hilton_invoice_proof_adapter", "posture": "future_gated", "current_authority": False},
                {"adapter_id": "coupa_adapter", "posture": "blocked_future_gated", "current_authority": False},
                {"adapter_id": "excel_workbook_proof_adapter", "posture": "metadata_candidate_only", "current_authority": False},
                {"adapter_id": "gmail_calendar_email_adapter", "posture": "blocked_future_gated", "current_authority": False},
                {"adapter_id": "browser_oauth_account_adapter", "posture": "blocked", "current_authority": False},
                {"adapter_id": "package_preview_exporter", "posture": "preview_only", "current_authority": "metadata_export_only"},
                {"adapter_id": "stable_map_reader", "posture": "read_only", "current_authority": "metadata_readback_only"},
            ],
        },
        "authority_boundary": {
            **NO_AUTHORITY_FLAGS,
            "valid_current_actions": ["read-model export", "operator markdown digest", "focused tests", "metadata proof checklist"],
            "blocked_current_actions": [
                "Coupa access",
                "browser/OAuth/account access",
                "credential/token/cookie/API key handling",
                "Gmail/calendar/email account access",
                "Excel raw body ingestion",
                "raw finance/private body ingestion",
                "invoice generation",
                "send/submit/approval",
                "live model calls",
                "tool execution",
                "queue/autonomy",
            ],
        },
        "operator_memory_questions": [
            _operator_question("one_invoice_posture", "Do you remember whether the Capital Hilton invoice should cover both 2026-05-08 and 2026-05-15 on one invoice?", "memory_only_clarification"),
            _operator_question("rate_confirmation", "Do you remember whether $400/gig is the correct rate for both dates?", "proof_needed"),
            _operator_question("coupa_po_reference", "Is there a Coupa PO number or payment reference that should exist?", "protected_proof_needed"),
            _operator_question("proof_source_location", "Is the proof source likely Coupa, Excel, email, a PDF, a calendar entry, or a packet already in OpenClaw?", "proof_needed"),
            _operator_question("ap_route", "Should the invoice go through Coupa only, email/AP contact, or another payment route?", "world_transition_needed"),
            _operator_question("protected_material", "Is there any protected client material that must be represented only as metadata?", "security_gate_needed"),
            _operator_question("finance_world_ready", "What would convince you the invoice is ready to move from helm threshold lane into Finance World action?", "world_transition_needed"),
        ],
        "security_audit_readiness": {
            "ready_for_security_audit": False,
            "ready_for_finance_world_action": False,
            "readiness_requires": [
                "protected proof metadata identified",
                "raw bodies excluded",
                "Coupa/browser/account routes blocked",
                "Guardian gates identified",
                "Operator approvals identified",
                "package preview receipt exists or is defined",
                "tool adapter receipt requirements exist or are defined",
                "model selection receipt blocked/preview-only",
                "missing proof list complete",
                "future action boundaries explicit",
                "no live execution authority",
            ],
            "current_blockers": missing_proof,
            "security_audit_readiness_is_not_action_readiness": True,
        },
        "finance_world_transition_policy": {
            "current_lane_state": "HELM_THRESHOLD_LANE",
            "target_lane_state": "FINANCE_WORLD_ACTIONABLE_LANE",
            "transition_allowed_now": False,
            "transition_requires": [
                "proof metadata exists for date/rate/subtotal/customer/payment route as required",
                "protected proof has Guardian metadata posture",
                "package preview receipt is complete",
                "model/tool/memory/adapter receipt requirements are clear",
                "security audit grants or blocks future action authority",
                "operator confirms final action path if required",
            ],
            "until_then": [
                "Mission Control may show the lane in Helm as proof-needed",
                "Finance World may show preview-only future actionable candidate",
                "No invoice execution",
            ],
        },
        "mission_control_surface_guidance": {
            "show": [
                "ELI5 lane summary",
                "known / partly known / unknown fact posture",
                "candidate facts separated from proof",
                "missing proof checklist",
                "protected material boundary",
                "what Cassandra can review",
                "what Guardian must gate",
                "Finance World transition conditions",
                "operator memory questions",
            ],
            "hide_or_block": [
                "raw Coupa/Excel/Gmail/calendar/PDF bodies",
                "credentials/tokens/cookies/API keys",
                "browser/OAuth/account controls",
                "invoice generation controls",
                "send/submit/approval controls",
                "fake proof claims from operator memory alone",
            ],
        },
        "stable_map_integration": {
            "contract_generated_as_read_model": True,
            "summary_included_in_stable_map_now": False,
            "reason_not_included_now": "stable-map refresh is a separate lane; current worktree has unrelated sync/health residue",
            "safe_summary_for_next_refresh": {
                "contract_id": "capital_hilton_proof_metadata_packet",
                "capital_hilton_status": "proof_needed_preview_only",
                "target_world": "Finance",
                "missing_proof_count": len(missing_proof),
                "protected_proof_required": True,
                "future_gated_action": True,
                "next_safe_detour": "protected proof metadata packet review",
            },
        },
        "recommended_next_lanes": [
            {
                "lane_id": "stable_map_refresh_capital_hilton_proof_summary",
                "title": "Stable Map Refresh with Capital Hilton Proof Summary",
                "priority": "P1",
                "hard_boundary": "app-facing summary only; no Mac sync/import in this lane",
            },
            {
                "lane_id": "finance_world_capital_hilton_preview_surface",
                "title": "Finance World / Capital Hilton Preview Surfacing",
                "priority": "P2",
                "hard_boundary": "read-only UI; no invoice execution",
            },
        ],
        "machine_proof": {
            "proof_metadata_record_count": len(proof_metadata),
            "candidate_fact_count": len(candidate_facts),
            "candidate_fact_ids_present": candidate_fact_ids_present,
            "candidate_fact_ids_missing": candidate_fact_ids_missing,
            "missing_proof_count": len(missing_proof),
            "protected_proof_required": True,
            "all_candidate_facts_machine_proven": all(fact["machine_proven"] is True for fact in candidate_facts),
            "all_candidate_facts_not_machine_proven": all(fact["machine_proven"] is False for fact in candidate_facts),
            "all_authority_flags_false_except_operator_final": all(value is False for key, value in NO_AUTHORITY_FLAGS.items() if key != "operator_final_authority"),
            "raw_body_included": False,
            "credential_or_secret_included": False,
            "content_hash": None,
        },
    }
    payload["machine_proof"]["content_hash"] = _content_hash(payload)
    return payload


def _proof_category_meaning(category: str) -> str:
    return {
        "CANDIDATE_FACT": "operator- or read-model-reported fact not fully backed by protected proof metadata",
        "METADATA_PROOF": "approved source card, receipt, packet, spreadsheet metadata, Coupa metadata, invoice packet metadata, or protected proof reference",
        "PROTECTED_PROOF": "finance/client/account-sensitive proof represented as guarded metadata, not raw body",
        "BLOCKED_RAW_BODY": "raw Coupa, Excel, Gmail/calendar, PDF, portal, account, or private financial document body that must not be ingested or displayed",
        "MISSING_PROOF": "required proof not yet present",
        "FUTURE_ACTION_PROOF": "future receipt required only after security audit, such as invoice generation, Coupa submission, or approval receipt",
    }[category]


def format_operator_markdown(payload: dict[str, Any]) -> str:
    lane = payload["capital_hilton_lane_fact_posture"]
    lines = [
        "# Capital Hilton Proof Metadata Packet v0",
        "",
        "## ELI5 Summary",
        "",
        "OpenClaw knows Capital Hilton is the first hard Finance steel thread, but it is not allowed to touch Coupa, Excel, email, accounts, credentials, or invoices. This packet only lists the candidate facts and the proof metadata needed before Cassandra, Guardian, or Finance World can safely do anything later.",
        "",
        "## What We Know",
        "",
    ]
    lines.extend(f"- {item}" for item in lane["known"])
    lines.extend(["", "## What We Partly Know", ""])
    lines.extend(f"- {item}" for item in lane["partly_known"])
    lines.extend(["", "## What We Do Not Know", ""])
    lines.extend(f"- {item}" for item in lane["known_unknown"])
    lines.extend(["", "## Candidate Facts", ""])
    for fact in payload["capital_hilton_candidate_facts"]:
        value = fact["current_value"] if fact["current_value"] not in (None, "") else "missing"
        lines.append(f"- `{fact['fact_id']}`: `{value}` -> `{fact['proof_status']}`")
    lines.extend(["", "## Missing Proof Checklist", ""])
    lines.extend(f"- `{item}`" for item in payload["missing_proof_checklist"])
    lines.extend(
        [
            "",
            "## Protected Material Boundary",
            "",
            "- Raw Coupa, Excel, Gmail/calendar, PDF, portal, account, and private finance bodies remain blocked.",
            "- Credentials, tokens, cookies, browser sessions, and account access are blocked.",
            "- Operator answers become memory candidates, not proof.",
            "",
            "## Cassandra / Guardian / Finance World",
            "",
            "- Cassandra may review metadata, packet posture, and missing proof labels only.",
            "- Guardian must gate protected proof, redaction, quarantine, and access posture without self-authorizing.",
            "- Finance World becomes actionable only after proof metadata, package receipts, model/tool/memory receipt posture, security audit, and operator final path are complete.",
            "",
            "## Operator Memory Questions",
            "",
        ]
    )
    for question in payload["operator_memory_questions"]:
        lines.append(f"- `{question['classification']}`: {question['question']}")
    lines.extend(
        [
            "",
            "## Next Safe Move",
            "",
            f"- {lane['safe_next_detour']}",
            "",
            "## Stable Map",
            "",
            f"- Summary included now: `{str(payload['stable_map_integration']['summary_included_in_stable_map_now']).lower()}`",
            "- Next stable-map refresh should include the Capital Hilton proof metadata summary.",
            "",
            "## Boundary",
            "",
        ]
    )
    for key, value in NO_AUTHORITY_FLAGS.items():
        lines.append(f"- `{key}` = `{value}`")
    return "\n".join(lines) + "\n"


def export_capital_hilton_proof_metadata_packet(
    *,
    repo_root: str | Path = ROOT,
    export_root: str | Path = DEFAULT_EXPORT_ROOT,
    generated_at: str | None = None,
) -> CapitalHiltonProofPacketExportResult:
    payload = build_capital_hilton_proof_metadata_packet(repo_root=repo_root, generated_at=generated_at)
    root = Path(export_root)
    if not root.is_absolute():
        root = Path(repo_root) / root
    root.mkdir(parents=True, exist_ok=True)
    json_path = root / JSON_EXPORT_NAME
    operator_path = root / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(format_operator_markdown(payload), encoding="utf-8")
    return CapitalHiltonProofPacketExportResult(
        schema_version=SCHEMA_VERSION,
        json_path=json_path.as_posix(),
        operator_path=operator_path.as_posix(),
        proof_metadata_record_count=len(payload["required_proof_metadata"]),
        candidate_fact_count=len(payload["capital_hilton_candidate_facts"]),
        missing_proof_count=len(payload["missing_proof_checklist"]),
        protected_proof_required=payload["machine_proof"]["protected_proof_required"],
        live_authority_added=False,
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export the Capital Hilton Proof Metadata Packet read-model.")
    parser.add_argument("--repo-root", default=ROOT.as_posix())
    parser.add_argument("--export-root", default=DEFAULT_EXPORT_ROOT.as_posix())
    parser.add_argument("--format", choices=("summary", "json", "operator"), default="operator")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    result = export_capital_hilton_proof_metadata_packet(
        repo_root=args.repo_root,
        export_root=args.export_root,
    )
    summary = {
        "schema_version": result.schema_version,
        "json_path": result.json_path,
        "operator_path": result.operator_path,
        "proof_metadata_record_count": result.proof_metadata_record_count,
        "candidate_fact_count": result.candidate_fact_count,
        "missing_proof_count": result.missing_proof_count,
        "protected_proof_required": result.protected_proof_required,
        "live_authority_added": result.live_authority_added,
    }
    if args.format in {"summary", "json"}:
        print(stable_json(summary), end="")
    else:
        print(f"Capital Hilton Proof Metadata Packet: `{result.schema_version}`")
        print(f"- JSON: `{result.json_path}`")
        print(f"- Operator: `{result.operator_path}`")
    return 0


__all__ = [
    "JSON_EXPORT_NAME",
    "NO_AUTHORITY_FLAGS",
    "OPERATOR_EXPORT_NAME",
    "PROOF_CATEGORIES",
    "REQUIRED_PROOF_METADATA_RECORDS",
    "SCHEMA_VERSION",
    "build_capital_hilton_proof_metadata_packet",
    "export_capital_hilton_proof_metadata_packet",
    "format_operator_markdown",
    "stable_json",
]


if __name__ == "__main__":
    raise SystemExit(main())
