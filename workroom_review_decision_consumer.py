"""Workroom Review Decision Consumer V0.

Consumes Mission Control review decision requests for Workroom review packets
and records a generated receipt only. It does not merge code, push git state,
spawn workers, run child agents, send email, open browser/Gmail/Coupa, mutate
ledgers or workbooks, export PDFs, submit portals, mark paid, or grant worker
authority.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import workroom_review_decision_contract as decision_contract


ROOT = Path(__file__).resolve().parent
DEFAULT_READ_MODEL_ROOT = Path("generated/read_models")
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_BRIDGE_EXPORT_ROOT = Path("/mnt/e/openclaw/generated/read_models")
DEFAULT_WIKI_PATH = Path("generated/wiki/openclaw/Workroom Review Decision Consumer.md")

SCHEMA_VERSION = "workroom_review_decision_consumer_v0"
READ_MODEL_ID = "workroom_review_decision_status"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
CONSUMER_STATUS = "WORKROOM_REVIEW_DECISION_CONSUMER_READY"
CONSUMER_NOT_READY_STATUS = "WORKROOM_REVIEW_DECISION_CONSUMER_NOT_READY"

REQUEST_TYPE = "WORKROOM_REVIEW_DECISION_REQUEST_V0"
REQUEST_KIND = "WORKROOM_REVIEW_DECISION_REQUEST"
WORKFLOW_REF = "workroom_review_decision"
REQUEST_FILENAME_PATTERNS = (
    "mission_control_workroom_review_decision_request_*.json",
    "mission_control_capture_request_*workroom_review_decision*.json",
)

PRECONDITION_FILES = {
    "workroom_review_packet_index": "workroom_review_packet_index.json",
    "workroom_review_decision_contract": "workroom_review_decision_contract.json",
    "package_event_index": "package_event_index.json",
}

PRECONDITION_STATUSES = {
    "workroom_review_packet_index": "WORKROOM_REVIEW_PACKET_INDEX_READY",
    "workroom_review_decision_contract": "WORKROOM_REVIEW_DECISION_CONTRACT_READY",
    "package_event_index": "PACKAGE_EVENT_INDEX_READY",
}

ACTION_EFFECTS = {
    "approve_review_packet_for_record": {
        "status": "OPERATOR_REVIEW_RECORDED",
        "headline": "Review recorded",
        "summary": "Chief recorded the operator review decision only; no merge or push ran.",
        "next_safe_action": "Record complete. No merge or push performed.",
        "status_label": "Review recorded",
    },
    "request_review_packet_rework": {
        "status": "REWORK_REQUEST_RECORDED",
        "headline": "Rework request recorded",
        "summary": "Chief recorded the rework request only; no worker was spawned.",
        "next_safe_action": "Worker packet is marked for rework.",
        "status_label": "Rework recorded",
    },
    "mark_review_packet_informational": {
        "status": "INFORMATIONAL_REVIEW_CLOSED",
        "headline": "Informational review closed",
        "summary": "Chief closed the review as informational only; no follow-up action ran.",
        "next_safe_action": "No action needed.",
        "status_label": "Informational",
    },
}

AUTHORITY_BOUNDARY = dict(decision_contract.AUTHORITY_BOUNDARY)
UNSAFE_REQUEST_KEYS = set(decision_contract.UNSAFE_REQUEST_KEYS) | {
    "push_allowed",
    "merge_allowed",
    "browser_access_allowed",
    "gmail_allowed",
    "coupa_allowed",
    "portal_submit_allowed",
    "ledger_posting_allowed",
    "sent",
    "paid",
}


@dataclass(frozen=True)
class WorkroomReviewDecisionResult:
    status: str
    request_id: str
    request_filename: str
    review_packet_id: str
    decision_action: str
    blockers: tuple[str, ...]
    response_primary_status: str
    next_safe_action: str
    receipt: dict[str, Any]


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
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}


def _short_hash(parts: list[str]) -> str:
    return hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()[:16]


def _request_id(raw_request: Mapping[str, Any], filename: str) -> str:
    return str(
        raw_request.get("request_id")
        or raw_request.get("source_request_id")
        or f"workroom_review_decision:{filename or 'unknown'}"
    )


def is_workroom_review_decision_request(raw_request: Mapping[str, Any]) -> bool:
    request_type = str(raw_request.get("request_type") or raw_request.get("type") or "").strip().upper()
    kind = str(raw_request.get("kind") or "").strip().upper()
    return request_type == REQUEST_TYPE or kind == REQUEST_KIND


def _source_payloads(read_model_root: Path) -> dict[str, dict[str, Any]]:
    root = _rooted(read_model_root)
    return {
        ref: _load_json(root / filename)
        for ref, filename in PRECONDITION_FILES.items()
    }


def _preconditions(read_model_root: Path) -> list[dict[str, Any]]:
    root = _rooted(read_model_root)
    rows: list[dict[str, Any]] = []
    for ref, filename in PRECONDITION_FILES.items():
        payload = _load_json(root / filename)
        observed = str(payload.get("status") or payload.get("contract_status") or "")
        required = PRECONDITION_STATUSES[ref]
        rows.append(
            {
                "precondition_ref": ref,
                "required_status": required,
                "observed_status": observed,
                "ready": observed == required,
                "source_ref": f"generated/read_models/{filename}",
            }
        )
    return rows


def _review_packets(packet_index: Mapping[str, Any]) -> list[dict[str, Any]]:
    packets = packet_index.get("packets")
    if not isinstance(packets, list):
        return []
    return [dict(packet) for packet in packets if isinstance(packet, Mapping)]


def _packet_by_id(packet_index: Mapping[str, Any], review_packet_id: str) -> dict[str, Any] | None:
    for packet in _review_packets(packet_index):
        if str(packet.get("review_packet_id") or "") == review_packet_id:
            return packet
    return None


def _strings(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item)]


def _packet_summary(packet: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(packet, Mapping):
        return None
    unsafe_scan = packet.get("unsafe_scan_result") if isinstance(packet.get("unsafe_scan_result"), Mapping) else {}
    return {
        "review_packet_id": str(packet.get("review_packet_id") or ""),
        "package_id": str(packet.get("package_id") or ""),
        "worker_ref": str(packet.get("worker_ref") or ""),
        "channel_ref": str(packet.get("channel_ref") or ""),
        "status": str(packet.get("status") or ""),
        "human_summary": str(packet.get("human_summary") or ""),
        "files_changed": _strings(packet.get("files_changed")),
        "tests_run": _strings(packet.get("tests_run")),
        "receipts": _strings(packet.get("receipts")),
        "screenshots": _strings(packet.get("screenshots")),
        "proof_refs": _strings(packet.get("proof_refs")),
        "next_safe_action": str(packet.get("next_safe_action") or ""),
        "operator_decision_required": bool(packet.get("operator_decision_required") is True),
        "proof_collapsed_by_default": bool(packet.get("proof_collapsed_by_default") is True),
        "worker_inherits_speaker_authority": False,
        "merge_allowed": False,
        "push_allowed": False,
        "business_action_performed": False,
        "unsafe_scan_result": {
            "status": str(unsafe_scan.get("status") or "UNKNOWN"),
            "unsafe_true_grants": _strings(unsafe_scan.get("unsafe_true_grants")),
        },
    }


def _authority_true_grants(raw_request: Mapping[str, Any]) -> list[str]:
    grants: list[str] = []
    authority = raw_request.get("authority_boundary")
    if isinstance(authority, Mapping):
        for key, value in authority.items():
            if value is True:
                grants.append(str(key))
    for key, value in raw_request.items():
        if key in UNSAFE_REQUEST_KEYS and value is True:
            grants.append(str(key))
    return sorted(dict.fromkeys(grants))


def _proof_refs(packet: Mapping[str, Any] | None, *, status_ref: str) -> list[str]:
    refs: list[str] = [
        "generated/read_models/workroom_review_packet_index.json",
        "generated/read_models/workroom_review_decision_contract.json",
        "generated/read_models/package_event_index.json",
        status_ref,
    ]
    if isinstance(packet, Mapping):
        refs.extend(_strings(packet.get("proof_refs")))
    return list(dict.fromkeys(ref for ref in refs if ref))[:16]


def _operator_display(
    *,
    status: str,
    decision_action: str,
    blockers: tuple[str, ...],
    unsafe_true_grants: tuple[str, ...],
    review_packet_id: str,
    packet: Mapping[str, Any] | None,
) -> dict[str, Any]:
    if unsafe_true_grants:
        return {
            "speaker_ref": "guardian",
            "voice_profile_ref": "agent_voice_profile:guardian",
            "voice_mode": "safety_gate",
            "audience": "internal_operator",
            "headline": "Review decision blocked",
            "subheadline": "Unsafe authority was requested.",
            "status_label": "Blocked",
            "tone": "blocked",
            "plain_summary": "Guardian blocked this request because it asked for authority outside review recording.",
            "next_safe_action": "Remove push, merge, send, submit, ledger, paid, or external authority and resend.",
            "why_it_matters": "Review decisions can record operator intent, but they cannot perform protected actions.",
            "primary_fact": "No merge, push, send, submit, ledger, workbook, or paid action ran.",
            "secondary_facts": [f"Unsafe grant: {key}" for key in unsafe_true_grants],
            "proof_caption": "Proof available.",
            "proof_refs_collapsed": True,
            "show_machine_details_by_default": False,
            "routing_reason": "protected authority boundary",
        }
    if status == "BLOCKED_UNKNOWN_REVIEW_PACKET":
        return {
            "speaker_ref": "chief",
            "voice_profile_ref": "agent_voice_profile:chief",
            "voice_mode": "diagnostic",
            "audience": "internal_operator",
            "headline": "Review packet not found",
            "subheadline": "The packet index has no matching id.",
            "status_label": "Blocked",
            "tone": "blocked",
            "plain_summary": "Chief could not record the decision because the review packet id is not in the local packet index.",
            "next_safe_action": "Pick a packet from the Workroom Review Packet Index and resend.",
            "why_it_matters": "A decision must attach to a known review packet before it can become review evidence.",
            "primary_fact": f"Requested packet: {review_packet_id or 'missing'}.",
            "secondary_facts": list(blockers),
            "proof_caption": "Proof available.",
            "proof_refs_collapsed": True,
            "show_machine_details_by_default": False,
            "routing_reason": "review packet diagnostics",
        }
    if status == "BLOCKED_UNKNOWN_DECISION_ACTION":
        return {
            "speaker_ref": "chief",
            "voice_profile_ref": "agent_voice_profile:chief",
            "voice_mode": "diagnostic",
            "audience": "internal_operator",
            "headline": "Decision action not recognized",
            "subheadline": "The action is outside the review contract.",
            "status_label": "Blocked",
            "tone": "blocked",
            "plain_summary": "Chief blocked the request because the decision action is not in the local contract.",
            "next_safe_action": "Use approve_review_packet_for_record, request_review_packet_rework, or mark_review_packet_informational.",
            "why_it_matters": "Review decisions are deterministic and limited to the published contract.",
            "primary_fact": f"Requested action: {decision_action or 'missing'}.",
            "secondary_facts": list(blockers),
            "proof_caption": "Proof available.",
            "proof_refs_collapsed": True,
            "show_machine_details_by_default": False,
            "routing_reason": "review contract diagnostics",
        }
    if status == "BLOCKED_PRECONDITION_NOT_READY":
        return {
            "speaker_ref": "chief",
            "voice_profile_ref": "agent_voice_profile:chief",
            "voice_mode": "diagnostic",
            "audience": "internal_operator",
            "headline": "Review decision blocked",
            "subheadline": "Required read models are not ready.",
            "status_label": "Blocked",
            "tone": "blocked",
            "plain_summary": "Chief could not record the decision because required local read models are not ready.",
            "next_safe_action": "Restore the review packet index, decision contract, and package event index, then resend.",
            "why_it_matters": "The consumer records decisions only when the local evidence chain is available.",
            "primary_fact": "No review decision was recorded.",
            "secondary_facts": list(blockers),
            "proof_caption": "Proof available.",
            "proof_refs_collapsed": True,
            "show_machine_details_by_default": False,
            "routing_reason": "read model readiness diagnostics",
        }
    effect = ACTION_EFFECTS[decision_action]
    worker_ref = str(packet.get("worker_ref") or "unknown") if isinstance(packet, Mapping) else "unknown"
    return {
        "speaker_ref": "chief",
        "voice_profile_ref": "agent_voice_profile:chief",
        "voice_mode": "diagnostic",
        "audience": "internal_operator",
        "headline": effect["headline"],
        "subheadline": "Decision receipt only.",
        "status_label": effect["status_label"],
        "tone": "calm",
        "plain_summary": effect["summary"],
        "next_safe_action": effect["next_safe_action"],
        "why_it_matters": "Review decisions separate operator review from merge, push, and business action authority.",
        "primary_fact": f"Worker ref remains {worker_ref}; speaker authority stays with Chief.",
        "secondary_facts": [
            "No merge or push performed.",
            "No business action performed.",
        ],
        "proof_caption": "Proof available.",
        "proof_refs_collapsed": True,
        "show_machine_details_by_default": False,
        "routing_reason": "normal review decision status",
    }


def _receipt(
    *,
    raw_request: Mapping[str, Any],
    source_request_filename: str,
    generated_at: str,
    read_model_root: Path,
) -> dict[str, Any]:
    request_id = _request_id(raw_request, source_request_filename)
    review_packet_id = str(raw_request.get("review_packet_id") or "").strip()
    decision_action = str(raw_request.get("decision_action") or "").strip()
    reason = str(raw_request.get("reason") or "")
    preconditions = _preconditions(read_model_root)
    preconditions_ready = all(item["ready"] for item in preconditions)
    payloads = _source_payloads(read_model_root)
    packet_index = payloads.get("workroom_review_packet_index", {})
    packet = _packet_by_id(packet_index, review_packet_id)
    action_known = decision_action in decision_contract.DECISION_ACTIONS
    unsafe_true_grants = tuple(_authority_true_grants(raw_request))
    blockers: list[str] = []
    status = ""
    response_primary_status = ""
    next_safe_action = ""

    if not preconditions_ready:
        status = "BLOCKED_PRECONDITION_NOT_READY"
        blockers.extend(
            f"precondition_not_ready:{item['precondition_ref']}"
            for item in preconditions
            if not item["ready"]
        )
        response_primary_status = "Blocked"
        next_safe_action = "Restore the review packet index, decision contract, and package event index, then resend."
    elif unsafe_true_grants:
        status = "BLOCKED_UNSAFE_AUTHORITY"
        blockers.extend(f"unsafe_true_grant:{key}" for key in unsafe_true_grants)
        response_primary_status = "Blocked"
        next_safe_action = "Remove push, merge, send, submit, ledger, paid, or external authority and resend."
    elif not review_packet_id or packet is None:
        status = "BLOCKED_UNKNOWN_REVIEW_PACKET"
        blockers.append("unknown_review_packet_id" if review_packet_id else "missing_review_packet_id")
        response_primary_status = "Blocked"
        next_safe_action = "Pick a packet from the Workroom Review Packet Index and resend."
    elif not action_known:
        status = "BLOCKED_UNKNOWN_DECISION_ACTION"
        blockers.append("unknown_decision_action")
        response_primary_status = "Blocked"
        next_safe_action = "Use approve_review_packet_for_record, request_review_packet_rework, or mark_review_packet_informational."
    else:
        effect = ACTION_EFFECTS[decision_action]
        status = effect["status"]
        response_primary_status = effect["status_label"]
        next_safe_action = effect["next_safe_action"]

    accepted = status in {
        "OPERATOR_REVIEW_RECORDED",
        "REWORK_REQUEST_RECORDED",
        "INFORMATIONAL_REVIEW_CLOSED",
    }
    contract_receipt = decision_contract.build_decision_receipt(
        review_packet_id=review_packet_id,
        decision_action=decision_action,
        reason=reason,
        requested_authority=raw_request.get("authority_boundary") if isinstance(raw_request.get("authority_boundary"), Mapping) else None,
        generated_at=generated_at,
    )
    if not accepted:
        contract_receipt = dict(contract_receipt)
        contract_receipt["decision_accepted"] = False
        contract_receipt["operator_reviewed"] = False
        contract_receipt["review_closed"] = False
        contract_receipt["rework_requested"] = False
        contract_receipt["informational_only"] = False
    receipt_id = f"workroom_review_decision_consumer:{_short_hash([request_id, review_packet_id, decision_action, generated_at])}"
    read_model_ref = "generated/read_models/workroom_review_decision_status.json"
    proof_refs = _proof_refs(packet, status_ref=read_model_ref)
    operator_display = _operator_display(
        status=status,
        decision_action=decision_action,
        blockers=tuple(blockers),
        unsafe_true_grants=unsafe_true_grants,
        review_packet_id=review_packet_id,
        packet=packet,
    )
    raw_internal_status = "RESPONSE_READY" if accepted else "BLOCKED_WITH_REASON"
    return {
        "schema_version": SCHEMA_VERSION,
        "receipt_type": "WORKROOM_REVIEW_DECISION_CONSUMER_RECEIPT",
        "receipt_id": receipt_id,
        "generated_at": generated_at,
        "request_id": request_id,
        "source_request_filename": source_request_filename,
        "request_type": REQUEST_TYPE,
        "workflow_ref": WORKFLOW_REF,
        "status": status,
        "raw_internal_status": raw_internal_status,
        "decision_recorded": accepted,
        "decision_accepted": accepted,
        "operator_reviewed": accepted,
        "review_packet_found": packet is not None,
        "review_packet_id": review_packet_id,
        "decision_action": decision_action,
        "reason": reason,
        "blockers": blockers,
        "unsafe_true_grants": list(unsafe_true_grants),
        "response_primary_status": response_primary_status,
        "next_safe_action": next_safe_action,
        "operator_display": operator_display,
        "speaker_ref": operator_display["speaker_ref"],
        "voice_profile_ref": operator_display["voice_profile_ref"],
        "voice_mode": operator_display["voice_mode"],
        "worker_ref": str(packet.get("worker_ref") or "") if isinstance(packet, Mapping) else "",
        "worker_ref_is_speaker": False,
        "review_packet_summary": _packet_summary(packet),
        "contract_receipt": contract_receipt,
        "preconditions": preconditions,
        "proof_refs": proof_refs,
        "proof_refs_collapsed": True,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "no_push": True,
        "no_merge": True,
        "no_business_action": True,
        "business_action_performed": False,
        "merge_performed": False,
        "git_push_performed": False,
        "worker_spawn_performed": False,
        "child_agent_run_performed": False,
        "email_send_performed": False,
        "gmail_access_performed": False,
        "browser_access_performed": False,
        "coupa_access_performed": False,
        "ledger_mutation_performed": False,
        "workbook_mutation_performed": False,
        "pdf_export_performed": False,
        "submit_performed": False,
        "paid_marking_performed": False,
        "business_state_mutation_performed": False,
        "read_model_paths": {
            "local_status_path": "",
            "bridge_status_path": "",
            "wiki_path": "",
        },
    }


def _existing_history(export_root: Path) -> list[dict[str, Any]]:
    payload = _load_json(_rooted(export_root) / JSON_EXPORT_NAME)
    history = payload.get("decision_history")
    if not isinstance(history, list):
        return []
    return [dict(item) for item in history if isinstance(item, Mapping)]


def build_read_model(
    *,
    receipt: Mapping[str, Any] | None = None,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
    export_root: Path = DEFAULT_EXPORT_ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    preconditions = _preconditions(read_model_root)
    preconditions_ready = all(item["ready"] for item in preconditions)
    payloads = _source_payloads(read_model_root)
    packet_count = len(_review_packets(payloads.get("workroom_review_packet_index", {})))
    history = _existing_history(export_root)
    if isinstance(receipt, Mapping):
        receipt_id = str(receipt.get("receipt_id") or "")
        history = [item for item in history if str(item.get("receipt_id") or "") != receipt_id]
        history.append(dict(receipt))
    history = history[-200:]
    last_decision = dict(receipt) if isinstance(receipt, Mapping) else (history[-1] if history else None)
    status = CONSUMER_STATUS if preconditions_ready else CONSUMER_NOT_READY_STATUS
    return {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "generated_at": generated_at,
        "status": status,
        "purpose": "Generated status for Workroom review packet decisions recorded through Mission Control.",
        "mode": "local_generated_receipt_only_no_merge_push_or_business_action",
        "request_type": REQUEST_TYPE,
        "workflow_ref": WORKFLOW_REF,
        "decision_actions": list(decision_contract.DECISION_ACTIONS),
        "preconditions": preconditions,
        "known_review_packet_count": packet_count,
        "last_decision": last_decision,
        "decision_history": history,
        "decision_history_count": len(history),
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "source_refs": [
            "generated/read_models/workroom_review_packet_index.json",
            "generated/read_models/workroom_review_decision_contract.json",
            "generated/read_models/package_event_index.json",
        ],
        "machine_proof": {
            "local_only": True,
            "generated_receipt_only": True,
            "preconditions_ready": preconditions_ready,
            "review_packet_id_validated": bool(last_decision and last_decision.get("review_packet_found")),
            "decision_action_validated": bool(
                last_decision and last_decision.get("decision_action") in decision_contract.DECISION_ACTIONS
            ),
            "unsafe_authority_rejected": bool(last_decision and last_decision.get("status") == "BLOCKED_UNSAFE_AUTHORITY"),
            "worker_ref_is_speaker": False,
            "worker_output_inherits_speaker_authority": False,
            "merge_performed": False,
            "git_push_performed": False,
            "worker_spawn_performed": False,
            "child_agent_run_performed": False,
            "email_send_performed": False,
            "gmail_access_performed": False,
            "browser_access_performed": False,
            "coupa_access_performed": False,
            "ledger_mutation_performed": False,
            "workbook_mutation_performed": False,
            "pdf_export_performed": False,
            "submit_performed": False,
            "paid_marking_performed": False,
            "business_action_performed": False,
            "business_state_mutation_performed": False,
            "unsafe_true_grants_absent": all(value is False for value in AUTHORITY_BOUNDARY.values()),
        },
    }


def build_wiki(read_model: Mapping[str, Any]) -> str:
    last = read_model.get("last_decision") if isinstance(read_model.get("last_decision"), Mapping) else {}
    lines = [
        "# Workroom Review Decision Consumer",
        "",
        f"Status: `{read_model['status']}`",
        "",
        "This consumer records operator review decisions against Workroom review packets. It records receipts only.",
        "",
        "## Decision Actions",
        "",
    ]
    for action in read_model["decision_actions"]:
        effect = ACTION_EFFECTS.get(action, {})
        lines.extend(
            [
                f"- `{action}` -> `{effect.get('status', 'contract_only')}`",
            ]
        )
    lines.extend(
        [
            "",
            "## Latest Decision",
            "",
            f"- Receipt: `{last.get('receipt_id', '')}`",
            f"- Packet: `{last.get('review_packet_id', '')}`",
            f"- Action: `{last.get('decision_action', '')}`",
            f"- Status: `{last.get('status', '')}`",
            f"- Speaker: `{last.get('speaker_ref', '')}`",
            f"- Next safe action: {last.get('next_safe_action', '')}",
            "",
            "## Boundary",
            "",
            "- No merge.",
            "- No git push.",
            "- No worker spawn or child agent run.",
            "- No email send.",
            "- No Gmail/browser/Coupa access.",
            "- No ledger or workbook mutation.",
            "- No PDF export.",
            "- No submit or mark-paid.",
            "- No business action.",
            "- PC_CODEX and MAC_CODEX remain worker refs, not speakers.",
            "- Proof refs are collapsed by default.",
        ]
    )
    return "\n".join(lines) + "\n"


def export_workroom_review_decision_status(
    *,
    receipt: Mapping[str, Any] | None = None,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
    export_root: Path = DEFAULT_EXPORT_ROOT,
    bridge_export_root: Path | None = DEFAULT_BRIDGE_EXPORT_ROOT,
    wiki_path: Path = DEFAULT_WIKI_PATH,
    generated_at: str | None = None,
) -> dict[str, str]:
    read_model = build_read_model(
        receipt=receipt,
        read_model_root=read_model_root,
        export_root=export_root,
        generated_at=generated_at,
    )
    export_root = _rooted(export_root)
    export_root.mkdir(parents=True, exist_ok=True)
    read_model_path = export_root / JSON_EXPORT_NAME
    read_model_path.write_text(stable_json(read_model), encoding="utf-8")

    bridge_path = ""
    if bridge_export_root is not None:
        bridge_export_root.mkdir(parents=True, exist_ok=True)
        bridge_file = bridge_export_root / JSON_EXPORT_NAME
        bridge_file.write_text(stable_json(read_model), encoding="utf-8")
        bridge_path = bridge_file.as_posix()

    wiki_path = _rooted(wiki_path)
    wiki_path.parent.mkdir(parents=True, exist_ok=True)
    wiki_path.write_text(build_wiki(read_model), encoding="utf-8")
    return {
        "status": str(read_model["status"]),
        "read_model_path": read_model_path.as_posix(),
        "bridge_read_model_path": bridge_path,
        "wiki_path": wiki_path.as_posix(),
        "decision_history_count": str(read_model["decision_history_count"]),
    }


def consume_workroom_review_decision_request(
    raw_request: Mapping[str, Any],
    *,
    source_request_filename: str = "",
    generated_at: str | None = None,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
    export_root: Path = DEFAULT_EXPORT_ROOT,
    bridge_export_root: Path | None = DEFAULT_BRIDGE_EXPORT_ROOT,
    wiki_path: Path = DEFAULT_WIKI_PATH,
) -> WorkroomReviewDecisionResult:
    generated_at = generated_at or utc_now()
    receipt = _receipt(
        raw_request=raw_request,
        source_request_filename=source_request_filename,
        generated_at=generated_at,
        read_model_root=read_model_root,
    )
    export_result = export_workroom_review_decision_status(
        receipt=receipt,
        read_model_root=read_model_root,
        export_root=export_root,
        bridge_export_root=bridge_export_root,
        wiki_path=wiki_path,
        generated_at=generated_at,
    )
    receipt = dict(receipt)
    receipt["read_model_paths"] = {
        "local_status_path": export_result["read_model_path"],
        "bridge_status_path": export_result["bridge_read_model_path"],
        "wiki_path": export_result["wiki_path"],
    }
    export_workroom_review_decision_status(
        receipt=receipt,
        read_model_root=read_model_root,
        export_root=export_root,
        bridge_export_root=bridge_export_root,
        wiki_path=wiki_path,
        generated_at=generated_at,
    )
    recorded = bool(receipt.get("decision_recorded") is True)
    return WorkroomReviewDecisionResult(
        status="RECORDED" if recorded else "BLOCKED",
        request_id=str(receipt["request_id"]),
        request_filename=source_request_filename,
        review_packet_id=str(receipt["review_packet_id"]),
        decision_action=str(receipt["decision_action"]),
        blockers=tuple(str(item) for item in receipt.get("blockers") or ()),
        response_primary_status=str(receipt["response_primary_status"]),
        next_safe_action=str(receipt["next_safe_action"]),
        receipt=receipt,
    )


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Consume/export Workroom Review Decision Consumer V0 status.")
    parser.add_argument("--request-file", help="Optional WORKROOM_REVIEW_DECISION_REQUEST_V0 JSON file to consume.")
    parser.add_argument("--read-model-root", default=str(DEFAULT_READ_MODEL_ROOT))
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT))
    parser.add_argument("--bridge-export-root", default=str(DEFAULT_BRIDGE_EXPORT_ROOT))
    parser.add_argument("--wiki-path", default=str(DEFAULT_WIKI_PATH))
    parser.add_argument("--generated-at")
    parser.add_argument("--no-bridge", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    bridge_root = None if args.no_bridge else Path(args.bridge_export_root)
    if args.request_file:
        request_path = Path(args.request_file)
        raw_request = _load_json(request_path)
        result = consume_workroom_review_decision_request(
            raw_request,
            source_request_filename=request_path.name,
            generated_at=args.generated_at,
            read_model_root=Path(args.read_model_root),
            export_root=Path(args.export_root),
            bridge_export_root=bridge_root,
            wiki_path=Path(args.wiki_path),
        )
        print(stable_json(result.receipt), end="")
        return 0 if result.status == "RECORDED" else 2
    export_result = export_workroom_review_decision_status(
        read_model_root=Path(args.read_model_root),
        export_root=Path(args.export_root),
        bridge_export_root=bridge_root,
        wiki_path=Path(args.wiki_path),
        generated_at=args.generated_at,
    )
    print(stable_json(export_result), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
