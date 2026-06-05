"""Mac Thinning Readiness Map V0.

Publishes a backend-informed map of which Mission Control Mac surfaces can move
from workflow-specific UI to backend-authored dynamic cards, and which must
remain bespoke shell/controller components.
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
DEFAULT_BRIDGE_EXPORT_ROOT = Path("/mnt/e/openclaw/generated/read_models")
DEFAULT_WIKI_PATH = Path("generated/wiki/openclaw/Mac Thinning Readiness Map.md")

SCHEMA_VERSION = "mac_thinning_readiness_map_v0"
READ_MODEL_ID = "mac_thinning_readiness_map"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
READY_STATUS = "MAC_THINNING_READINESS_MAP_READY"
NOT_READY_STATUS = "MAC_THINNING_READINESS_MAP_NOT_READY"

CLASSIFICATIONS = (
    "keep_bespoke",
    "convert_to_dynamic_card_now",
    "convert_after_v1_parity",
    "hide_developer_proof",
    "remove_after_receipt_parity",
    "needs_backend_contract",
    "do_not_build",
)

AUTHORITY_BOUNDARY = {
    "authority_grant_allowed": False,
    "business_action_allowed": False,
    "email_send_allowed": False,
    "gmail_allowed": False,
    "browser_access_allowed": False,
    "coupa_allowed": False,
    "portal_submit_allowed": False,
    "ledger_mutation_allowed": False,
    "ledger_posting_allowed": False,
    "paid": False,
    "paid_marking_allowed": False,
    "workbook_mutation_allowed": False,
    "pdf_export_allowed": False,
    "git_push_allowed": False,
    "worker_spawn_allowed": False,
    "external_action_allowed": False,
}

UNSAFE_TRUE_KEYS = {
    "authority_granted",
    "authority_grant_allowed",
    "business_action_allowed",
    "business_action_performed",
    "paid",
    "paid_marking_allowed",
    "paid_marking_performed",
    "ledger_mutation_allowed",
    "ledger_mutation_performed",
    "ledger_posting_allowed",
    "email_send_allowed",
    "email_send_performed",
    "coupa_allowed",
    "coupa_submit_performed",
    "portal_submit_allowed",
    "protected_execution_exposed",
    "workbook_mutation_allowed",
    "workbook_mutation_performed",
    "pdf_export_allowed",
    "pdf_export_performed",
    "git_push_allowed",
    "worker_spawn_allowed",
    "worker_run_performed",
    "external_action_allowed",
    "incoming_authority_granted_accepted",
    "recommend_remove_without_dynamic_card_coverage",
    "recommend_convert_without_action_or_receipt_coverage",
}

PRECONDITIONS = {
    "dynamic_card_packet_v1": {
        "filename": "dynamic_card_packet_latest.json",
        "accepted_statuses": ["DYNAMIC_CARD_PACKET_V1_READY", "DYNAMIC_CARD_PACKET_READY"],
    },
    "controller_knob_mode_filters": {
        "filename": "controller_knob_mode_filters.json",
        "accepted_statuses": ["CONTROLLER_KNOB_MODE_FILTERS_READY"],
    },
    "proof_meter_normalization": {
        "filename": "proof_meter_normalization.json",
        "accepted_statuses": ["PROOF_METER_NORMALIZATION_READY"],
    },
    "operator_session_timeline": {
        "filename": "operator_session_timeline.json",
        "accepted_statuses": ["OPERATOR_SESSION_TIMELINE_READY"],
    },
}

RAIL_STATUS_FILES = (
    "system_question_answer_contract.json",
    "workflow_package_request_consumer_status.json",
    "workroom_review_decision_status.json",
    "evidence_intake_status.json",
    "client_invoice_workbook_registry.json",
    "approval_request_queue.json",
    "gate_decision_ledger.json",
    "workflow_composer_latest.json",
    "memory_promotion_gate.json",
)

SURFACE_TEMPLATES = (
    {
        "surface_ref": "helm",
        "display_name": "Helm",
        "surface_kind": "shell",
        "classification": "keep_bespoke",
        "card_ids": [],
        "payload_keywords": [],
        "receipt_types": [],
        "controller_event_types": [],
        "recommended_mac_action": "Keep as native Mac shell/controller navigation.",
        "risk_if_removed_too_early": "The app loses its primary control frame even if cards render correctly.",
        "confidence": "high",
    },
    {
        "surface_ref": "composer",
        "display_name": "Composer",
        "surface_kind": "shell",
        "classification": "keep_bespoke",
        "card_ids": [],
        "payload_keywords": [],
        "receipt_types": [],
        "controller_event_types": [],
        "recommended_mac_action": "Keep as native text/input controller; dispatch verified controller events.",
        "risk_if_removed_too_early": "The operator loses the generic command/input surface.",
        "confidence": "high",
    },
    {
        "surface_ref": "world_bank_switcher",
        "display_name": "World/bank switcher",
        "surface_kind": "shell",
        "classification": "keep_bespoke",
        "card_ids": [],
        "payload_keywords": [],
        "receipt_types": [],
        "controller_event_types": [],
        "recommended_mac_action": "Keep as native Mac navigation state.",
        "risk_if_removed_too_early": "Dynamic cards cannot replace global world/bank selection.",
        "confidence": "high",
    },
    {
        "surface_ref": "dynamic_card_renderer",
        "display_name": "Dynamic card renderer",
        "surface_kind": "shell",
        "classification": "keep_bespoke",
        "card_ids": [],
        "payload_keywords": [],
        "receipt_types": ["dynamic_card_emitted"],
        "controller_event_types": [],
        "recommended_mac_action": "Keep a generic renderer; remove workflow-specific card classes behind it.",
        "risk_if_removed_too_early": "Backend cards exist but have nowhere stable to render.",
        "confidence": "high",
    },
    {
        "surface_ref": "evidence_drop_zone",
        "display_name": "Evidence drop zone",
        "surface_kind": "shell_input",
        "classification": "keep_bespoke",
        "card_ids": ["dynamic_card.finance.live_arts_md.evidence_intake.payment_processing"],
        "payload_keywords": ["evidence", "record_proof"],
        "receipt_types": ["evidence_recorded"],
        "controller_event_types": ["attach_proof"],
        "recommended_mac_action": "Keep native drop/file-picker UX; let backend cards own receipt/status copy.",
        "risk_if_removed_too_early": "The Mac loses local file-intake affordances even though evidence receipts can render.",
        "confidence": "high",
    },
    {
        "surface_ref": "proof_details_drawer",
        "display_name": "Proof/details drawer",
        "surface_kind": "shell",
        "classification": "keep_bespoke",
        "card_ids": [],
        "payload_keywords": ["show_details", "explain"],
        "receipt_types": [],
        "controller_event_types": ["show_details"],
        "recommended_mac_action": "Keep generic drawer shell; populate contents from proof objects and meters.",
        "risk_if_removed_too_early": "Proof remains generated but not inspectable by the operator.",
        "confidence": "high",
    },
    {
        "surface_ref": "finance_capital_hilton",
        "display_name": "Finance / Capital Hilton",
        "surface_kind": "workflow",
        "classification": "convert_to_dynamic_card_now",
        "card_ids": [
            "dynamic_card.finance.capital_hilton.payment_watch",
            "dynamic_card.finance.capital_hilton.contextual_question",
            "dynamic_card.finance.capital_hilton.workbook_registration",
        ],
        "payload_keywords": ["capital_hilton.payment", "client_invoice_workbook.register", "helm_question.capital_hilton"],
        "receipt_types": ["controller_event_received", "dynamic_card_emitted", "gate_blocked"],
        "controller_event_types": ["ask_why", "open_lane", "show_details"],
        "recommended_mac_action": "Replace workflow-specific payment-watch/status panels with dynamic cards.",
        "risk_if_removed_too_early": "Low if generic renderer, proof drawer, and native navigation stay bespoke.",
        "confidence": "high",
    },
    {
        "surface_ref": "finance_live_arts_md",
        "display_name": "Finance / Live Arts MD",
        "surface_kind": "workflow",
        "classification": "convert_to_dynamic_card_now",
        "card_ids": ["dynamic_card.finance.live_arts_md.evidence_intake.payment_processing"],
        "payload_keywords": ["evidence", "record_proof"],
        "receipt_types": ["evidence_recorded"],
        "controller_event_types": ["attach_proof"],
        "recommended_mac_action": "Replace workflow-specific evidence receipt panel with backend evidence-intake card.",
        "risk_if_removed_too_early": "Medium if native drop zone is removed; low for status panel thinning.",
        "confidence": "high",
    },
    {
        "surface_ref": "business_development_capital_hilton",
        "display_name": "Business Development / Capital Hilton",
        "surface_kind": "workflow",
        "classification": "convert_to_dynamic_card_now",
        "card_ids": ["dynamic_card.business_development.capital_hilton.proposal"],
        "payload_keywords": ["capital_hilton.proposal.stage_followup"],
        "receipt_types": ["package_staged", "package_rejected"],
        "controller_event_types": ["do_it", "stage_plan"],
        "recommended_mac_action": "Replace bespoke follow-up/proposal status panel with workflow composer plan card.",
        "risk_if_removed_too_early": "Low while send remains blocked and staging remains receipt-backed.",
        "confidence": "high",
    },
    {
        "surface_ref": "build_review_packets",
        "display_name": "Build review packets",
        "surface_kind": "workflow",
        "classification": "convert_to_dynamic_card_now",
        "card_ids": [
            "dynamic_card.build.review_packet.current",
            "dynamic_card.build.review_packet.completed_historical_receipt",
        ],
        "payload_keywords": ["review_packet"],
        "receipt_types": ["review_decision_recorded"],
        "controller_event_types": ["mark_informational", "request_rework", "approve"],
        "recommended_mac_action": "Replace bespoke packet cards with backend review-packet cards once using review action slots.",
        "risk_if_removed_too_early": "Medium if review actions are not routed through deterministic payloads.",
        "confidence": "high",
    },
    {
        "surface_ref": "workrooms",
        "display_name": "Workrooms",
        "surface_kind": "shell_and_workflow",
        "classification": "convert_after_v1_parity",
        "card_ids": ["dynamic_card.build.review_packet.current"],
        "payload_keywords": ["review_packet"],
        "receipt_types": ["review_decision_recorded"],
        "controller_event_types": ["request_rework", "mark_informational"],
        "recommended_mac_action": "Keep workroom navigation shell; convert packet/status contents after all workroom lanes emit v1 cards.",
        "risk_if_removed_too_early": "High. Workroom shell, routing, and navigation are not just card content.",
        "confidence": "medium",
    },
    {
        "surface_ref": "approval_gate_surfaces",
        "display_name": "Approval/gate surfaces",
        "surface_kind": "protected_workflow",
        "classification": "convert_to_dynamic_card_now",
        "card_ids": [
            "dynamic_card.finance.capital_hilton.approval_request.coupa_submit",
            "dynamic_card.system.check_engine.diagnostic",
        ],
        "payload_keywords": ["guardian_gate", "chief_diagnostic"],
        "receipt_types": ["approval_recorded", "gate_blocked"],
        "controller_event_types": ["approve", "deny", "show_details"],
        "recommended_mac_action": "Render gate/approval states as dynamic cards; never expose protected execution from these cards.",
        "risk_if_removed_too_early": "Medium if disabled execution affordances are not preserved.",
        "confidence": "high",
    },
    {
        "surface_ref": "memory_candidates",
        "display_name": "Memory candidates",
        "surface_kind": "workflow",
        "classification": "convert_after_v1_parity",
        "card_ids": ["dynamic_card.memory.payment_evidence_candidate"],
        "payload_keywords": ["memory"],
        "receipt_types": ["memory_candidate_recorded"],
        "controller_event_types": ["show_details"],
        "recommended_mac_action": "Use dynamic memory candidate cards for display; keep review controls until promotion actions have parity.",
        "risk_if_removed_too_early": "Medium. Candidate display exists, but promotion/rejection control parity is incomplete.",
        "confidence": "medium",
    },
    {
        "surface_ref": "st_annes_work_log_review",
        "display_name": "St. Anne’s work-log review",
        "surface_kind": "workflow",
        "classification": "convert_to_dynamic_card_now",
        "card_ids": ["dynamic_card.finance.st_annes.work_log_review"],
        "payload_keywords": [],
        "receipt_types": ["review_decision_recorded"],
        "controller_event_types": ["show_details"],
        "recommended_mac_action": "Replace resolved/test-only bespoke status panel with completed historical receipt card.",
        "risk_if_removed_too_early": "Low for resolved history; keep any future active edit controls separate.",
        "confidence": "high",
    },
    {
        "surface_ref": "workbook_registration",
        "display_name": "Workbook registration",
        "surface_kind": "workflow",
        "classification": "convert_to_dynamic_card_now",
        "card_ids": ["dynamic_card.finance.capital_hilton.workbook_registration"],
        "payload_keywords": ["client_invoice_workbook.register"],
        "receipt_types": ["dynamic_card_emitted"],
        "controller_event_types": ["do_it"],
        "recommended_mac_action": "Replace bespoke workbook metadata panel with current-focus workbook registration card.",
        "risk_if_removed_too_early": "Low if workbook mutation remains blocked and only metadata refs are shown.",
        "confidence": "high",
    },
    {
        "surface_ref": "developer_proof",
        "display_name": "Developer Proof",
        "surface_kind": "proof",
        "classification": "hide_developer_proof",
        "card_ids": ["dynamic_card.artifact.evidence_intake.proof_only"],
        "payload_keywords": ["show_details"],
        "receipt_types": ["dynamic_card_emitted"],
        "controller_event_types": ["show_details"],
        "recommended_mac_action": "Keep available behind explicit proof-depth/detail opt-in; hide by default.",
        "risk_if_removed_too_early": "High. Operators and developers lose source refs, hashes, and receipt details.",
        "confidence": "high",
    },
    {
        "surface_ref": "evidence_drawer",
        "display_name": "Evidence drawer",
        "surface_kind": "proof_workflow",
        "classification": "convert_after_v1_parity",
        "card_ids": [
            "dynamic_card.finance.live_arts_md.evidence_intake.payment_processing",
            "dynamic_card.artifact.evidence_intake.proof_only",
        ],
        "payload_keywords": ["evidence", "show_details"],
        "receipt_types": ["evidence_recorded"],
        "controller_event_types": ["attach_proof", "show_details"],
        "recommended_mac_action": "Keep generic drawer shell; convert workflow-specific evidence rows after proof drawer parity.",
        "risk_if_removed_too_early": "Medium. Evidence proof exists, but local file preview and redaction UX must stay intact.",
        "confidence": "medium",
    },
    {
        "surface_ref": "legacy_invoice_review_panels",
        "display_name": "Legacy invoice review panels",
        "surface_kind": "legacy_workflow",
        "classification": "remove_after_receipt_parity",
        "card_ids": [
            "dynamic_card.finance.capital_hilton.payment_watch",
            "dynamic_card.finance.live_arts_md.evidence_intake.payment_processing",
            "dynamic_card.finance.capital_hilton.workbook_registration",
        ],
        "payload_keywords": ["capital_hilton.payment", "evidence", "client_invoice_workbook.register"],
        "receipt_types": ["controller_event_received", "evidence_recorded", "dynamic_card_emitted"],
        "controller_event_types": ["ask_why", "attach_proof", "show_details"],
        "recommended_mac_action": "Remove old workflow-specific panels only after card, receipt, proof-drawer, and action parity are confirmed.",
        "risk_if_removed_too_early": "High. Some legacy invoice states may still lack v1 receipt parity.",
        "confidence": "medium",
    },
    {
        "surface_ref": "manual_authority_override",
        "display_name": "Manual authority override",
        "surface_kind": "unsafe_request",
        "classification": "do_not_build",
        "card_ids": [],
        "payload_keywords": [],
        "receipt_types": [],
        "controller_event_types": [],
        "recommended_mac_action": "Do not build. Incoming authority_granted remains ignored or rejected.",
        "risk_if_removed_too_early": "No removal risk; the surface should not exist.",
        "confidence": "high",
    },
)


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


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(stable_json(payload), encoding="utf-8")


def _source_ref(filename: str) -> str:
    return f"generated/read_models/{filename}"


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


def _preconditions(read_model_root: Path) -> list[dict[str, Any]]:
    root = _rooted(read_model_root)
    rows: list[dict[str, Any]] = []
    for ref, contract in PRECONDITIONS.items():
        filename = str(contract["filename"])
        payload = _load_json(root / filename)
        observed = str(payload.get("status") or payload.get("contract_status") or "")
        accepted = [str(status) for status in contract["accepted_statuses"]]
        rows.append(
            {
                "precondition_ref": ref,
                "source_ref": _source_ref(filename),
                "observed_status": observed,
                "accepted_statuses": accepted,
                "ready": observed in accepted,
            }
        )
    rail_rows = []
    for filename in RAIL_STATUS_FILES:
        payload = _load_json(root / filename)
        proof = payload.get("machine_proof") if isinstance(payload.get("machine_proof"), Mapping) else {}
        rail_rows.append(
            {
                "source_ref": _source_ref(filename),
                "dynamic_card_packet_v1_valid": proof.get("dynamic_card_packet_v1_valid") is True,
                "dynamic_card_packet_v1_emitted": proof.get("dynamic_card_packet_v1_emitted") is True,
            }
        )
    rails_ready = all(row["dynamic_card_packet_v1_valid"] and row["dynamic_card_packet_v1_emitted"] for row in rail_rows)
    rows.append(
        {
            "precondition_ref": "dynamic_card_v1_rails",
            "source_ref": "generated/read_models/*rail dynamic_card_packet_v1 machine_proof",
            "observed_status": "DYNAMIC_CARD_V1_RAILS_READY" if rails_ready else "DYNAMIC_CARD_V1_RAILS_NOT_READY",
            "accepted_statuses": ["DYNAMIC_CARD_V1_RAILS_READY"],
            "ready": rails_ready,
            "rail_sources": rail_rows,
        }
    )
    return rows


def _card_index(packet: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    return {
        str(card.get("card_id") or ""): card
        for card in packet.get("cards") or []
        if isinstance(card, Mapping) and str(card.get("card_id") or "")
    }


def _payload_index(action_payloads: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    rows = action_payloads.get("action_payloads")
    if not isinstance(rows, list):
        return {}
    index: dict[str, Mapping[str, Any]] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        payload_id = str(row.get("action_payload_id") or row.get("action_payload_ref") or row.get("action_id") or "")
        if payload_id:
            index[payload_id] = row
    return index


def _receipt_types(universal_receipts: Mapping[str, Any]) -> set[str]:
    return {
        str(receipt.get("receipt_type") or "")
        for receipt in universal_receipts.get("receipts") or []
        if isinstance(receipt, Mapping)
    }


def _timeline_controller_events(timeline: Mapping[str, Any]) -> set[str]:
    events: set[str] = set()
    for event in timeline.get("timeline_events") or []:
        if isinstance(event, Mapping) and str(event.get("controller_event_type") or ""):
            events.add(str(event.get("controller_event_type")))
    return events


def _meter_cards(proof_meters: Mapping[str, Any]) -> set[str]:
    return {
        str(card_set.get("card_id") or "")
        for card_set in proof_meters.get("card_meter_sets") or []
        if isinstance(card_set, Mapping)
    }


def _lifecycle_covered(card_ids: list[str], cards: Mapping[str, Mapping[str, Any]], classification: str) -> dict[str, Any]:
    states = [str(cards[card_id].get("lifecycle_state") or "") for card_id in card_ids if card_id in cards]
    if classification == "keep_bespoke":
        status = "not_applicable"
    elif states:
        status = "covered"
    else:
        status = "missing"
    return {"status": status, "lifecycle_states": states}


def _payloads_for_keywords(payloads: Mapping[str, Mapping[str, Any]], keywords: list[str]) -> list[str]:
    refs: list[str] = []
    for payload_id in payloads:
        if any(keyword in payload_id for keyword in keywords):
            refs.append(payload_id)
    return sorted(refs)


def _payloads_are_safe(payload_refs: list[str], payloads: Mapping[str, Mapping[str, Any]]) -> bool:
    for payload_ref in payload_refs:
        payload = payloads.get(payload_ref) or {}
        boundary = payload.get("authority_boundary") if isinstance(payload.get("authority_boundary"), Mapping) else {}
        if any(value is not False for value in boundary.values()):
            return False
    return True


def _controller_event_status(required: list[str], available: set[str], classification: str) -> str:
    if classification == "keep_bespoke" and not required:
        return "not_applicable"
    if not required:
        return "not_required"
    return "covered" if any(event_type in available for event_type in required) else "partial"


def _recommended_remove(classification: str) -> bool:
    return classification == "remove_after_receipt_parity"


def _recommended_convert(classification: str) -> bool:
    return classification in {"convert_to_dynamic_card_now", "convert_after_v1_parity"}


def evaluate_surface(template: Mapping[str, Any], sources: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    cards = _card_index(sources.get("dynamic_card_packet_latest", {}))
    payloads = _payload_index(sources.get("operator_action_payloads", {}))
    receipt_types = _receipt_types(sources.get("universal_receipt_envelope_status", {}))
    controller_events = _timeline_controller_events(sources.get("operator_session_timeline", {}))
    meter_cards = _meter_cards(sources.get("proof_meter_normalization", {}))

    classification = str(template["classification"])
    card_ids = [str(card_id) for card_id in template.get("card_ids") or []]
    present_card_ids = [card_id for card_id in card_ids if card_id in cards]
    payload_refs = _payloads_for_keywords(payloads, [str(item) for item in template.get("payload_keywords") or []])
    required_receipts = [str(item) for item in template.get("receipt_types") or []]
    present_receipts = [receipt_type for receipt_type in required_receipts if receipt_type in receipt_types]
    required_events = [str(item) for item in template.get("controller_event_types") or []]
    present_meter_card_ids = [card_id for card_id in present_card_ids if card_id in meter_cards]
    shell = str(template["surface_kind"]) in {"shell", "shell_input"}
    coverage_exists = bool(present_card_ids)
    action_or_receipt_covered = bool(payload_refs or present_receipts or shell)

    backend_card_status = "not_applicable" if shell and not card_ids else "full" if len(present_card_ids) == len(card_ids) and card_ids else "partial" if present_card_ids else "none"
    action_status = "not_applicable" if shell and not template.get("payload_keywords") else "covered" if payload_refs or present_receipts else "missing"
    receipt_status = "not_required" if not required_receipts else "covered" if len(present_receipts) == len(required_receipts) else "partial" if present_receipts else "missing"
    proof_status = "not_applicable" if shell and not card_ids else "covered" if len(present_meter_card_ids) == len(present_card_ids) and present_card_ids else "partial" if present_meter_card_ids else "missing"

    recommendation_errors: list[str] = []
    if _recommended_remove(classification) and not coverage_exists:
        recommendation_errors.append("remove_recommended_without_dynamic_card_coverage")
    if _recommended_convert(classification) and not action_or_receipt_covered:
        recommendation_errors.append("convert_recommended_without_action_or_receipt_coverage")

    protected_execution_exposed = False
    for card_id in present_card_ids:
        card = cards[card_id]
        for slot in (card.get("action_slots") or {}).values():
            if isinstance(slot, Mapping):
                boundary = slot.get("authority_boundary") if isinstance(slot.get("authority_boundary"), Mapping) else {}
                if any(value is not False for value in boundary.values()):
                    protected_execution_exposed = True
    protected_execution_exposed = protected_execution_exposed or not _payloads_are_safe(payload_refs, payloads)

    return {
        "surface_ref": str(template["surface_ref"]),
        "display_name": str(template["display_name"]),
        "surface_kind": str(template["surface_kind"]),
        "classification": classification,
        "backend_card_coverage": {
            "status": backend_card_status,
            "required_card_ids": card_ids,
            "covered_card_ids": present_card_ids,
            "coverage_exists": coverage_exists,
        },
        "action_payload_coverage": {
            "status": action_status,
            "required_keywords": [str(item) for item in template.get("payload_keywords") or []],
            "covered_action_payload_refs": payload_refs,
            "receipt_or_shell_coverage_counts_as_action_parity": bool(present_receipts or shell),
            "all_payload_authority_boundaries_false": _payloads_are_safe(payload_refs, payloads),
        },
        "lifecycle_coverage": _lifecycle_covered(present_card_ids, cards, classification),
        "proof_meter_coverage": {
            "status": proof_status,
            "covered_card_ids": present_meter_card_ids,
        },
        "controller_event_coverage": {
            "status": _controller_event_status(required_events, controller_events, classification),
            "required_controller_event_types": required_events,
            "observed_controller_event_types": sorted(event for event in required_events if event in controller_events),
        },
        "receipt_coverage": {
            "status": receipt_status,
            "required_receipt_types": required_receipts,
            "covered_receipt_types": present_receipts,
        },
        "confidence": str(template["confidence"]),
        "recommended_mac_action": str(template["recommended_mac_action"]),
        "risk_if_removed_too_early": str(template["risk_if_removed_too_early"]),
        "recommendation_errors": recommendation_errors,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "machine_proof": {
            "protected_execution_exposed": protected_execution_exposed,
            "recommend_remove_without_dynamic_card_coverage": _recommended_remove(classification) and not coverage_exists,
            "recommend_convert_without_action_or_receipt_coverage": _recommended_convert(classification) and not action_or_receipt_covered,
            "incoming_authority_granted_accepted": False,
            "business_action_performed": False,
            "paid_marking_performed": False,
            "ledger_mutation_performed": False,
            "email_send_performed": False,
            "coupa_submit_performed": False,
            "workbook_mutation_performed": False,
            "pdf_export_performed": False,
        },
    }


def _load_sources(read_model_root: Path) -> dict[str, dict[str, Any]]:
    root = _rooted(read_model_root)
    return {
        "dynamic_card_packet_latest": _load_json(root / "dynamic_card_packet_latest.json"),
        "controller_knob_mode_filters": _load_json(root / "controller_knob_mode_filters.json"),
        "proof_meter_normalization": _load_json(root / "proof_meter_normalization.json"),
        "operator_session_timeline": _load_json(root / "operator_session_timeline.json"),
        "operator_action_payloads": _load_json(root / "operator_action_payloads.json"),
        "universal_receipt_envelope_status": _load_json(root / "universal_receipt_envelope_status.json"),
    }


def build_read_model(
    *,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    sources = _load_sources(read_model_root)
    preconditions = _preconditions(read_model_root)
    surface_rows = [evaluate_surface(template, sources) for template in SURFACE_TEMPLATES]
    validation_errors: list[str] = []
    for row in surface_rows:
        if row["classification"] not in CLASSIFICATIONS:
            validation_errors.append(f"{row['surface_ref']}:unknown_classification")
        validation_errors.extend(f"{row['surface_ref']}:{error}" for error in row["recommendation_errors"])
        if row["machine_proof"]["protected_execution_exposed"]:
            validation_errors.append(f"{row['surface_ref']}:protected_execution_exposed")
    preconditions_ready = all(row["ready"] for row in preconditions)
    classification_counts = {classification: 0 for classification in CLASSIFICATIONS}
    for row in surface_rows:
        classification_counts[row["classification"]] += 1
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "status": READY_STATUS if preconditions_ready and not validation_errors else NOT_READY_STATUS,
        "generated_at": generated_at,
        "source_refs": [
            _source_ref("dynamic_card_packet_latest.json"),
            _source_ref("controller_knob_mode_filters.json"),
            _source_ref("proof_meter_normalization.json"),
            _source_ref("operator_session_timeline.json"),
            _source_ref("operator_action_payloads.json"),
            _source_ref("universal_receipt_envelope_status.json"),
        ],
        "source_content_hashes": {
            name: _content_hash(payload)
            for name, payload in sources.items()
        },
        "classifications": list(CLASSIFICATIONS),
        "surface_count": len(surface_rows),
        "classification_counts": classification_counts,
        "surface_readiness": surface_rows,
        "preconditions": preconditions,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "rules": [
            "Do not recommend removing a Mac surface unless dynamic card coverage exists.",
            "Do not recommend converting if action payload or receipt coverage is missing.",
            "Shell components stay bespoke.",
            "Developer Proof stays available but hidden.",
            "Protected/gate surfaces cannot expose execution.",
        ],
        "machine_proof": {
            "preconditions_ready": preconditions_ready,
            "validation_errors": validation_errors,
            "mac_code_edited": False,
            "protected_execution_exposed": False,
            "incoming_authority_granted_accepted": False,
            "business_action_performed": False,
            "paid_marking_performed": False,
            "ledger_mutation_performed": False,
            "email_send_performed": False,
            "coupa_submit_performed": False,
            "workbook_mutation_performed": False,
            "pdf_export_performed": False,
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
        "# Mac Thinning Readiness Map",
        "",
        "Status: " + str(read_model["status"]),
        "",
        "This map identifies which Mission Control Mac surfaces can thin into backend-authored dynamic cards and which must stay bespoke shell/controller UI.",
        "",
        "## Rules",
        "",
    ]
    for rule in read_model.get("rules") or []:
        lines.append(f"- {rule}")
    lines.extend(["", "## Classifications", ""])
    for classification, count in (read_model.get("classification_counts") or {}).items():
        lines.append(f"- `{classification}`: `{count}`")
    lines.extend(["", "## Surfaces", ""])
    for row in read_model.get("surface_readiness") or []:
        lines.append(
            f"- `{row['surface_ref']}`: `{row['classification']}` confidence=`{row['confidence']}` cards=`{row['backend_card_coverage']['status']}` actions=`{row['action_payload_coverage']['status']}`"
        )
        lines.append(f"  - Mac action: {row['recommended_mac_action']}")
        lines.append(f"  - Early-removal risk: {row['risk_if_removed_too_early']}")
    lines.extend(
        [
            "",
            "## Proof",
            "",
            f"- Surface count: `{read_model.get('surface_count')}`",
            f"- Unsafe true grants absent: `{str((read_model.get('machine_proof') or {}).get('unsafe_true_grants_absent')).lower()}`",
            f"- Validation errors: `{len((read_model.get('machine_proof') or {}).get('validation_errors') or [])}`",
            "",
        ]
    )
    return "\n".join(lines)


def export_mac_thinning_readiness_map(
    *,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
    export_root: Path = DEFAULT_EXPORT_ROOT,
    bridge_export_root: Path | None = DEFAULT_BRIDGE_EXPORT_ROOT,
    wiki_path: Path = DEFAULT_WIKI_PATH,
    generated_at: str | None = None,
) -> dict[str, str]:
    read_model = build_read_model(read_model_root=read_model_root, generated_at=generated_at)
    export_root = _rooted(export_root)
    export_root.mkdir(parents=True, exist_ok=True)
    export_path = export_root / JSON_EXPORT_NAME
    _write_json(export_path, read_model)

    bridge_path = ""
    if bridge_export_root is not None:
        bridge_export_root.mkdir(parents=True, exist_ok=True)
        bridge = bridge_export_root / JSON_EXPORT_NAME
        shutil.copy2(export_path, bridge)
        bridge_path = bridge.as_posix()

    wiki_path = _rooted(wiki_path)
    wiki_path.parent.mkdir(parents=True, exist_ok=True)
    wiki_path.write_text(build_wiki(read_model), encoding="utf-8")
    return {
        "status": str(read_model["status"]),
        "read_model_path": export_path.as_posix(),
        "bridge_read_model_path": bridge_path,
        "wiki_path": wiki_path.as_posix(),
        "surface_count": str(read_model["surface_count"]),
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Publish Mac Thinning Readiness Map V0.")
    parser.add_argument("--read-model-root", default=str(DEFAULT_READ_MODEL_ROOT))
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT))
    parser.add_argument("--bridge-export-root", default=str(DEFAULT_BRIDGE_EXPORT_ROOT))
    parser.add_argument("--wiki-path", default=str(DEFAULT_WIKI_PATH))
    parser.add_argument("--generated-at")
    parser.add_argument("--no-bridge", action="store_true")
    parser.add_argument("--format", choices=("summary", "json"), default="summary")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    result = export_mac_thinning_readiness_map(
        read_model_root=Path(args.read_model_root),
        export_root=Path(args.export_root),
        bridge_export_root=None if args.no_bridge else Path(args.bridge_export_root),
        wiki_path=Path(args.wiki_path),
        generated_at=args.generated_at,
    )
    if args.format == "json":
        print(stable_json(result), end="")
    else:
        print(f"{result['status']}: {result['read_model_path']}")
    return 0 if result["status"] == READY_STATUS else 1


if __name__ == "__main__":
    raise SystemExit(main())
