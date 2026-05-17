"""Capital Hilton review packet approval receipt v0.

Records the operator approval for manual Coupa review preparation from the
generated Cassandra/Clara packet. This is a read-model receipt only: it does
not send email, submit to a portal, access credentials, read spreadsheet cells,
or grant runtime authority.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cassandra_clara_fact_packet import (
    JSON_EXPORT_NAME as CASSANDRA_CLARA_PACKET_JSON,
    SCHEMA_VERSION as CASSANDRA_CLARA_PACKET_SCHEMA_VERSION,
    TARGET_WORKFLOW,
    stable_json,
)


ROOT = Path(__file__).resolve().parent
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_PACKET_PATH = DEFAULT_EXPORT_ROOT / CASSANDRA_CLARA_PACKET_JSON
SCHEMA_VERSION = "capital_hilton_review_packet_approval_v0"
JSON_EXPORT_NAME = "capital_hilton_review_packet_approval.json"
OPERATOR_EXPORT_NAME = "capital_hilton_review_packet_approval_OPERATOR.md"

APPROVAL_SCOPE = "manual_coupa_review_preparation_only"
APPROVAL_DECISION = "approved_for_manual_coupa_review_preparation_pending_po_confirmation"
SOURCE_POLICY_REQUIRED = "imported_cassandra_chief_memory_sqlite_only"

BLOCKED_ACTIONS = (
    "email_send",
    "gmail_send",
    "portal_submit",
    "coupa_submit",
    "supplier_portal_submit",
    "credential_access",
    "credential_storage_or_tokenization",
    "spreadsheet_cell_read",
    "workbook_parsing",
    "raw_private_file_read",
    "ad_hoc_memory_use",
    "old_hitl_import_or_authority",
    "runtime_activation",
    "agent_enablement",
    "recipient_email_send_authority",
)


@dataclass(frozen=True)
class CapitalHiltonReviewPacketApprovalResult:
    schema_version: str
    approval_receipt_id: str
    packet_approved_for_manual_review_preparation: bool
    json_path: str
    operator_path: str
    email_sent: bool
    portal_submitted: bool
    credentials_accessed: bool
    spreadsheet_cells_read: bool
    runtime_authority_changed: bool


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _rooted_path(path: str | Path) -> Path:
    path_obj = Path(path)
    if path_obj.is_absolute():
        return path_obj
    return ROOT / path_obj


def _display_path(path: str | Path) -> str:
    path_obj = Path(path)
    try:
        return path_obj.resolve().relative_to(ROOT.resolve()).as_posix()
    except (OSError, ValueError):
        return path_obj.as_posix()


def _read_json(path: str | Path) -> dict[str, Any]:
    payload = json.loads(_rooted_path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {path}")
    return payload


def _row_id(prefix: str, *parts: object) -> str:
    digest = hashlib.sha256("\0".join(str(part) for part in parts).encode("utf-8")).hexdigest()
    return f"{prefix}_{digest[:20]}"


def _packet_gate_failures(packet: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    expected_values = {
        "schema_version": CASSANDRA_CLARA_PACKET_SCHEMA_VERSION,
        "target_workflow": TARGET_WORKFLOW,
        "packet_kind": "capital_hilton_review_packet",
        "usable_capital_hilton_review_packet": True,
        "missing_required_fact_count": 0,
        "source_policy": SOURCE_POLICY_REQUIRED,
        "raw_data_imported": False,
        "raw_private_files_read": False,
        "ad_hoc_notes_read": False,
        "raw_messages_read": False,
        "spreadsheet_cells_read": False,
        "old_hitl_read": False,
        "agent_presence_read": False,
        "send_authority_granted": False,
        "runtime_authority_changed": False,
    }
    for key, expected in expected_values.items():
        if packet.get(key) != expected:
            failures.append(f"`{key}` must be `{expected}`, found `{packet.get(key)}`")

    boundaries = packet.get("boundaries")
    if not isinstance(boundaries, dict):
        failures.append("`boundaries` must be present")
    else:
        boundary_expectations = {
            "email_send_allowed": False,
            "invoice_send_allowed": False,
            "supplier_portal_login_allowed": False,
            "browser_automation_allowed": False,
            "spreadsheet_cell_read_allowed": False,
            "workbook_parsing_allowed": False,
            "no_send_authority": True,
            "no_runtime_authority": True,
        }
        for key, expected in boundary_expectations.items():
            if boundaries.get(key) != expected:
                failures.append(f"`boundaries.{key}` must be `{expected}`, found `{boundaries.get(key)}`")

    invoice_facts = packet.get("invoice_facts_used")
    if not isinstance(invoice_facts, list) or not invoice_facts:
        failures.append("`invoice_facts_used` must contain governed facts")
    else:
        for fact in invoice_facts:
            if not isinstance(fact, dict):
                failures.append("`invoice_facts_used` entries must be objects")
                continue
            if fact.get("evidence_status") != "parsed_evidence_not_truth":
                failures.append(f"`{fact.get('field_name')}` must remain parsed evidence, not truth")
            if fact.get("trust_status") != "needs_operator_confirmation":
                failures.append(f"`{fact.get('field_name')}` must need operator confirmation")
            if fact.get("no_send_authority") is not True:
                failures.append(f"`{fact.get('field_name')}` must not grant send authority")
            if fact.get("no_runtime_authority") is not True:
                failures.append(f"`{fact.get('field_name')}` must not grant runtime authority")

    return failures


def _source_artifacts(packet: dict[str, Any]) -> dict[str, str]:
    artifacts = packet.get("artifacts")
    if not isinstance(artifacts, dict):
        return {}
    return {str(key): str(value) for key, value in artifacts.items()}


def build_capital_hilton_review_packet_approval(
    *,
    packet: dict[str, Any] | None = None,
    packet_path: str | Path = DEFAULT_PACKET_PATH,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Build the manual-review approval receipt from a generated packet."""
    source_packet = packet or _read_json(packet_path)
    gate_failures = _packet_gate_failures(source_packet)
    approved = not gate_failures
    decision_basis = {
        "schema_version": SCHEMA_VERSION,
        "operator_decision": APPROVAL_DECISION,
        "packet_id": source_packet.get("packet_id"),
        "packet_generated_at": source_packet.get("generated_at"),
        "source_policy": source_packet.get("source_policy"),
        "usable_capital_hilton_review_packet": source_packet.get("usable_capital_hilton_review_packet"),
        "missing_required_fact_count": source_packet.get("missing_required_fact_count"),
        "gate_failures": gate_failures,
    }
    receipt_id = _row_id("cap_hilton_review_approval", stable_json(decision_basis))
    now = generated_at or utc_now()

    next_safe_move = (
        "Capital Hilton Manual Coupa Review Preparation v0"
        if approved
        else "Capital Hilton fact packet edits before approval"
    )

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": now,
        "approval_receipt_id": receipt_id,
        "operator_decision": APPROVAL_DECISION,
        "approval_scope": APPROVAL_SCOPE,
        "packet_approved_for_manual_review_preparation": approved,
        "manual_coupa_review_preparation_allowed": approved,
        "po_coupa_confirmation_required": True,
        "po_coupa_confirmation_gate": {
            "required": True,
            "status": "must_confirm_in_coupa_before_final_submission",
            "final_submission_allowed": False,
            "credential_access_allowed": False,
            "portal_submit_allowed": False,
        },
        "recipient_email_posture": {
            "status": "review_only_until_explicitly_confirmed",
            "email_send_allowed": False,
            "recipient_send_authority": False,
            "requires_separate_confirmation_before_send": True,
        },
        "source_packet": {
            "path": _display_path(packet_path),
            "schema_version": source_packet.get("schema_version"),
            "packet_id": source_packet.get("packet_id"),
            "packet_kind": source_packet.get("packet_kind"),
            "generated_at": source_packet.get("generated_at"),
            "target_workflow": source_packet.get("target_workflow"),
            "artifact_root": source_packet.get("artifact_root"),
            "artifacts": _source_artifacts(source_packet),
        },
        "facts_came_from_imported_sqlite_memory_facts": source_packet.get("source_policy") == SOURCE_POLICY_REQUIRED,
        "facts_source_policy": source_packet.get("source_policy"),
        "ad_hoc_memory_used": False,
        "missing_required_fact_count": source_packet.get("missing_required_fact_count"),
        "governed_fact_count": source_packet.get("governed_fact_count"),
        "contact_candidate_count": source_packet.get("contact_candidate_count"),
        "receivable_posture_count": source_packet.get("receivable_posture_count"),
        "facts_needing_operator_confirmation": [
            {
                "field_name": item.get("field_name"),
                "display_name": item.get("display_name"),
                "evidence_status": item.get("evidence_status"),
                "trust_status": item.get("trust_status"),
            }
            for item in source_packet.get("required_fact_status", [])
            if isinstance(item, dict) and item.get("present") is True
        ],
        "gate_failures": gate_failures,
        "edits_needed_before_approval": gate_failures,
        "blocked_actions": list(BLOCKED_ACTIONS),
        "boundaries": {
            "email_sent": False,
            "portal_submitted": False,
            "credentials_accessed": False,
            "spreadsheet_cells_read": False,
            "runtime_authority_changed": False,
            "send_authority_granted": False,
            "portal_submit_allowed": False,
            "credential_access_allowed": False,
            "supplier_portal_login_allowed": False,
            "spreadsheet_cell_read_allowed": False,
            "workbook_parsing_allowed": False,
            "ad_hoc_memory_used": False,
            "raw_private_files_read": False,
            "raw_messages_read": False,
            "old_hitl_read": False,
            "agent_presence_read": False,
            "repo_b_execution_allowed": False,
        },
        "email_sent": False,
        "portal_submitted": False,
        "credentials_accessed": False,
        "spreadsheet_cells_read": False,
        "runtime_authority_changed": False,
        "send_authority_granted": False,
        "next_safe_move": next_safe_move,
    }


def format_capital_hilton_review_packet_approval(payload: dict[str, Any]) -> str:
    approved = str(payload["packet_approved_for_manual_review_preparation"]).lower()
    lines = [
        "# Capital Hilton Review Packet Approval v0",
        "",
        "Status:",
        f"- Approved for manual Coupa review preparation: `{approved}`.",
        f"- Approval scope: `{payload['approval_scope']}`.",
        f"- Facts source: `{payload['facts_source_policy']}`.",
        "- No ad hoc memory was used.",
        "- No email was sent.",
        "- No portal was submitted.",
        "- No credentials were accessed.",
        "- No spreadsheet cells were read.",
        "",
        "## What Is Approved",
        "- Use the generated Cassandra/Clara packet as a manual review-prep packet.",
        "- Prepare for human Coupa review using the packet artifacts.",
        "- Keep all facts as parsed evidence needing operator confirmation.",
        "",
        "## Still Blocked",
    ]
    for action in payload["blocked_actions"]:
        lines.append(f"- `{action}`")

    lines.extend(
        [
            "",
            "## PO / Coupa Gate",
            "- PO must still be confirmed in Coupa before any final submission.",
            "- OpenClaw may not access credentials, log in, upload, save, or submit from this receipt.",
            "",
            "## Recipient / Email Posture",
            "- Recipient and CC posture remains review-only.",
            "- No email send is authorized until a separate explicit confirmation lane.",
            "",
            "## Packet Artifacts",
        ]
    )
    for name, path in payload["source_packet"].get("artifacts", {}).items():
        lines.append(f"- `{name}`: `{path}`")

    lines.extend(["", "## Edits Needed"])
    if payload["edits_needed_before_approval"]:
        for item in payload["edits_needed_before_approval"]:
            lines.append(f"- {item}")
    else:
        lines.append("- None for manual review preparation.")

    lines.extend(
        [
            "",
            "## Next Safe Move",
            f"- {payload['next_safe_move']}.",
            "",
        ]
    )
    return "\n".join(lines)


def export_capital_hilton_review_packet_approval(
    *,
    packet_path: str | Path = DEFAULT_PACKET_PATH,
    export_root: str | Path = DEFAULT_EXPORT_ROOT,
    generated_at: str | None = None,
) -> CapitalHiltonReviewPacketApprovalResult:
    export_path = _rooted_path(export_root)
    export_path.mkdir(parents=True, exist_ok=True)
    payload = build_capital_hilton_review_packet_approval(
        packet_path=packet_path,
        generated_at=generated_at,
    )
    json_path = export_path / JSON_EXPORT_NAME
    operator_path = export_path / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(format_capital_hilton_review_packet_approval(payload), encoding="utf-8")
    return CapitalHiltonReviewPacketApprovalResult(
        schema_version=SCHEMA_VERSION,
        approval_receipt_id=payload["approval_receipt_id"],
        packet_approved_for_manual_review_preparation=payload[
            "packet_approved_for_manual_review_preparation"
        ],
        json_path=_display_path(json_path),
        operator_path=_display_path(operator_path),
        email_sent=False,
        portal_submitted=False,
        credentials_accessed=False,
        spreadsheet_cells_read=False,
        runtime_authority_changed=False,
    )


__all__ = [
    "APPROVAL_DECISION",
    "APPROVAL_SCOPE",
    "BLOCKED_ACTIONS",
    "DEFAULT_EXPORT_ROOT",
    "DEFAULT_PACKET_PATH",
    "JSON_EXPORT_NAME",
    "OPERATOR_EXPORT_NAME",
    "SCHEMA_VERSION",
    "CapitalHiltonReviewPacketApprovalResult",
    "build_capital_hilton_review_packet_approval",
    "export_capital_hilton_review_packet_approval",
    "format_capital_hilton_review_packet_approval",
]
