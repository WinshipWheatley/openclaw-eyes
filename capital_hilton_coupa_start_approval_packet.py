"""Capital Hilton Coupa start approval packet spec v0.

This read-model builds a Guardian start-approval packet for the Hilton-only
Capital Hilton Coupa workflow. It is a packet/spec surface only: it does not
send Guardian messages, create approvals, automate Coupa, access credentials,
write spreadsheets, send email, or grant runtime/send/submit authority.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from capital_hilton_actionable_review_packet import DEFAULT_EXPORT_ROOT, stable_json
from guardian_hitl_sqlite_authority_contract import validate_canonical_approval_payload


ROOT = Path(__file__).resolve().parent
SCHEMA_VERSION = "capital_hilton_coupa_start_approval_packet_v0"
JSON_EXPORT_NAME = "capital_hilton_coupa_start_approval_packet.json"
OPERATOR_EXPORT_NAME = "capital_hilton_coupa_start_approval_packet_OPERATOR.md"
DEFAULT_EXECUTION_PATH = DEFAULT_EXPORT_ROOT / "capital_hilton_coupa_execution_path.json"

WORKFLOW_ID = "capital_hilton_coupa_supplier_portal_invoice"
APPROVAL_TYPE = "start_workflow_approval"
TTL_SECONDS = 24 * 60 * 60

NO_AUTHORITY_FLAGS = {
    "review_only": True,
    "start_approval_executable": False,
    "approval_request_persisted": False,
    "guardian_message_sent": False,
    "telegram_send_triggered": False,
    "gmail_or_email_send_triggered": False,
    "coupa_browser_automation_enabled": False,
    "coupa_submit_enabled": False,
    "email_send_enabled": False,
    "spreadsheet_write_enabled": False,
    "credential_or_pii_access_enabled": False,
    "raw_secret_or_pii_stored": False,
    "runtime_authority_added": False,
    "send_or_submit_authority_added": False,
    "approval_authority_added": False,
    "repo_b_executed": False,
    "mission_control_app_changed": False,
}

DOWNSTREAM_GATE_IDS = (
    "credential_pii_access_gate",
    "browser_automation_scope_gate",
    "coupa_submit_gate",
    "coupa_invoice_proof_capture_gate",
    "excel_companion_invoice_generation_match_gate",
    "guardian_send_approval_gate",
    "money_ledger_payment_verification_gate",
)


@dataclass(frozen=True)
class StartApprovalPacketExportResult:
    schema_version: str
    json_path: str
    operator_path: str
    start_approval_packet_modeled: bool
    start_approval_executable: bool
    existing_email_approval_inspected: bool
    rebuild_existing_email_approval_machinery: bool
    runtime_authority_added: bool
    send_or_submit_authority_added: bool


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _rooted(path: str | Path) -> Path:
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    return ROOT / candidate


def _display_path(path: str | Path) -> str:
    candidate = Path(path)
    try:
        return candidate.resolve().relative_to(ROOT.resolve()).as_posix()
    except (OSError, ValueError):
        return candidate.as_posix()


def _read_json_if_present(path: str | Path) -> dict[str, Any]:
    target = _rooted(path)
    if not target.exists():
        return {}
    payload = json.loads(target.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _row_id(prefix: str, *parts: object) -> str:
    digest = hashlib.sha256("\0".join(str(part) for part in parts).encode("utf-8")).hexdigest()
    return f"{prefix}_{digest[:20]}"


def _expires_at(requested_at: str) -> str:
    parsed = datetime.fromisoformat(requested_at.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return (parsed + timedelta(seconds=TTL_SECONDS)).replace(microsecond=0).isoformat()


def _safe_file_probe(path: str) -> dict[str, Any]:
    target = ROOT / path
    return {
        "path": path,
        "present": target.exists(),
        "static_inspection_only": True,
        "imported_or_executed": False,
    }


def _packet_basis(execution_path: dict[str, Any]) -> dict[str, Any]:
    return {
        "approval_type": APPROVAL_TYPE,
        "workflow": WORKFLOW_ID,
        "workflow_scope": execution_path.get("overlay_scope") or "Capital Hilton / Hilton only",
        "execution_contract_schema": execution_path.get("schema_version"),
        "allowed_scope": [
            "begin governed workflow preparation",
            "verify facts and read-model posture",
            "prepare for later gated Coupa, protected evidence, Excel match, and send-approval steps",
        ],
        "blocked_scope": [
            "Coupa submit",
            "browser automation",
            "credential or PII access",
            "Excel/spreadsheet write",
            "email send",
            "payment status change",
            "general runtime authority",
        ],
    }


def _canonical_approval_payload(packet_id: str, packet_hash: str, generated_at: str) -> dict[str, Any]:
    return {
        "approval_id": packet_id,
        "action_type": "capital_hilton_coupa_start_workflow",
        "actor": "guardian",
        "target": WORKFLOW_ID,
        "payload_hash": packet_hash,
        "payload_schema_version": SCHEMA_VERSION,
        "source_intent_ref": "modeled:cassandra_operator_intake:capital_hilton_coupa_start",
        "idempotency_key": _row_id("cap_hilton_start_idem", WORKFLOW_ID, packet_hash),
        "requested_at": generated_at,
        "expires_at": _expires_at(generated_at),
        "ttl_seconds": TTL_SECONDS,
        "authority_scope": "start_preparation_only_no_execution_no_send_no_submit",
        "risk_tier": "tier_1_start_review_no_external_action",
        "action_class": "workflow_start",
        "explicit_authorized_packet_ref": "",
        "payload_mutable_after_approval": False,
    }


def _authorization_scope() -> dict[str, Any]:
    return {
        "what_start_approval_authorizes": [
            "begin governed workflow preparation",
            "verify current Capital Hilton facts/read-models",
            "prepare readiness packets for later explicitly gated steps",
        ],
        "what_start_approval_does_not_authorize": [
            "Coupa submit",
            "browser automation",
            "credential/PII access",
            "Excel or spreadsheet write",
            "email send",
            "payment status change",
            "Guardian send approval",
            "final external communication",
            "general runtime authority",
        ],
        "preparation_scope_only": True,
        "external_action_authorized": False,
        "send_approval_created": False,
        "runtime_authority_created": False,
    }


def _downstream_gates() -> list[dict[str, Any]]:
    descriptions = {
        "credential_pii_access_gate": "Protected local mechanism must approve scoped credential/remit PII insertion.",
        "browser_automation_scope_gate": "Mac-local browser automation must be scoped and separately approved.",
        "coupa_submit_gate": "Coupa submit is a separate gate from browser navigation.",
        "coupa_invoice_proof_capture_gate": "Coupa invoice proof/download must be captured as protected evidence.",
        "excel_companion_invoice_generation_match_gate": "Excel companion artifact must be generated/updated and matched to Coupa proof.",
        "guardian_send_approval_gate": "Guardian send approval must bind one specific draft email and attachment.",
        "money_ledger_payment_verification_gate": "Paid status requires money-ledger payment verification.",
    }
    return [
        {
            "gate_id": gate_id,
            "required_after_start_approval": True,
            "satisfied_now": False,
            "authority_granted_by_start_approval": False,
            "description": descriptions[gate_id],
        }
        for gate_id in DOWNSTREAM_GATE_IDS
    ]


def _existing_email_approval_machinery_discovery() -> dict[str, Any]:
    surfaces = [
        {
            **_safe_file_probe("templates/agent/guardian_approval_request_packet_template.json"),
            "surface_role": "Guardian approval request packet template",
            "finding": "request packet shape exists as behavior-implied template",
            "reuse_posture": "candidate_pattern_for_later_send_approval_packet",
        },
        {
            **_safe_file_probe("templates/agent/cassandra_outreach_draft_packet_template.json"),
            "surface_role": "Cassandra outreach draft packet template",
            "finding": "draft-only outreach packet shape exists",
            "reuse_posture": "candidate_draft_record_shape_for_later_send_approval",
        },
        {
            **_safe_file_probe("cassandra_outreach.py"),
            "surface_role": "Cassandra email draft and known-contact action surface",
            "finding": (
                "contains draft creation helpers and an ask_guardian_send_approval operator action, "
                "but also has live broker/notification/send-adjacent paths that require detangling before reuse"
            ),
            "reuse_posture": "reuse_or_detangle_do_not_rebuild",
        },
        {
            **_safe_file_probe("google_access_policy.py"),
            "surface_role": "Google broker capability policy",
            "finding": "Gmail draft creation is Class B and Gmail send is Class C for Cassandra",
            "reuse_posture": "preserve_policy_boundary_for_later_send_approval",
        },
        {
            **_safe_file_probe("business_ops_ledger.py"),
            "surface_role": "outreach email draft receipt helper",
            "finding": "draft metadata receipt exists and is no-send/no-execution",
            "reuse_posture": "candidate_receipt_shape_for_later_send_approval",
        },
        {
            **_safe_file_probe("chief_guardian_sender.py"),
            "surface_role": "Guardian Telegram approval transport",
            "finding": "live Guardian sender exists but must not be invoked by this packet-spec lane",
            "reuse_posture": "future_transport_adapter_only_after_authority_packet_exists",
        },
        {
            **_safe_file_probe("chief_guardian_listener.py"),
            "surface_role": "Guardian approval response listener",
            "finding": "live Guardian listener exists and is tied to legacy approval state",
            "reuse_posture": "future_transport_adapter_only_after receipt compatibility is proven",
        },
    ]
    return {
        "existing_cassandra_guardian_email_approval_inspected": True,
        "inspection_method": "safe_static_repo_a_file_and_pattern_inspection_only",
        "surfaces": surfaces,
        "machinery_found": True,
        "existing_machinery_rebuilt_in_this_lane": False,
        "later_send_approval_should_reuse_or_detangle_existing_pattern": True,
        "send_approval_recommendation": (
            "Inspect and reuse the existing Cassandra draft + Guardian approval packet/receipt patterns where safe; "
            "detangle live Gmail/Telegram/runtime pieces before any send approval implementation."
        ),
        "start_approval_remains_separate_from_later_send_approval": True,
    }


def _reusable_pattern() -> dict[str, Any]:
    return {
        "pattern_id": "guardian_external_workflow_start_approval_packet",
        "reusable_later": True,
        "required_fields": [
            "approval_type",
            "workflow",
            "requested_by",
            "approving_actor",
            "what_start_approval_authorizes",
            "what_start_approval_does_not_authorize",
            "required_downstream_gates",
            "authority_boundary",
        ],
        "generalization_rule": (
            "Future external-action workflows may reuse this start-approval packet pattern, "
            "but must keep client-specific overlays separate from the base workflow."
        ),
        "approval_packet_not_execution_packet": True,
    }


def build_capital_hilton_coupa_start_approval_packet(
    *,
    execution_path_json: str | Path = DEFAULT_EXECUTION_PATH,
    generated_at: str | None = None,
) -> dict[str, Any]:
    ts = generated_at or utc_now()
    execution_path = _read_json_if_present(execution_path_json)
    basis = _packet_basis(execution_path)
    packet_hash = hashlib.sha256(stable_json(basis).encode("utf-8")).hexdigest()
    packet_id = _row_id("cap_hilton_start_approval", SCHEMA_VERSION, packet_hash)
    canonical_payload = _canonical_approval_payload(packet_id, packet_hash, ts)
    canonical_validation = validate_canonical_approval_payload(canonical_payload)
    discovery = _existing_email_approval_machinery_discovery()
    status_summary = {
        "start_approval_packet_modeled": True,
        "start_approval_executable": False,
        "existing_cassandra_guardian_email_approval_inspected": True,
        "rebuild_existing_email_approval_machinery": False,
        "later_send_approval_reuse_or_detangle_existing_pattern": True,
        "guardian_message_sent": False,
        "coupa_browser_automation_enabled": False,
        "coupa_submit_enabled": False,
        "email_send_enabled": False,
        "spreadsheet_write_enabled": False,
        "credential_or_pii_access_enabled": False,
        "raw_secret_or_pii_stored": False,
        "runtime_authority_added": False,
        "send_or_submit_authority_added": False,
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_by": "codex",
        "generated_at": ts,
        "packet_kind": "guardian_start_approval_packet_spec",
        "packet_status": "review_only_spec_not_dispatched",
        "packet_id": packet_id,
        "packet_hash": packet_hash,
        "approval_type": APPROVAL_TYPE,
        "workflow": WORKFLOW_ID,
        "workflow_scope": execution_path.get("overlay_scope") or "Capital Hilton / Hilton only",
        "client_specific_overlay": "hilton_coupa_supplier_portal",
        "base_invoice_workflow_remains_default": True,
        "requested_by": {
            "source": "Cassandra/operator intake",
            "modeled_source_only": True,
            "live_telegram_command_execution_enabled": False,
            "source_intent_ref": canonical_payload["source_intent_ref"],
        },
        "approving_actor": {
            "actor": "Guardian/operator",
            "guardian_message_sent": False,
            "approval_request_persisted": False,
            "decision_recorded": False,
        },
        "execution_path_context": {
            "source_path": _display_path(execution_path_json),
            "source_present": bool(execution_path),
            "schema_version": execution_path.get("schema_version"),
            "guardian_start_approval_modeled": bool(
                (execution_path.get("status_summary") or {}).get("guardian_start_approval_modeled")
            ),
            "guardian_send_approval_modeled": bool(
                (execution_path.get("status_summary") or {}).get("guardian_send_approval_modeled")
            ),
        },
        "authorization_scope": _authorization_scope(),
        "allowed_preparation_scope": _authorization_scope()["what_start_approval_authorizes"],
        "blocked_authorities": _authorization_scope()["what_start_approval_does_not_authorize"],
        "required_downstream_gates": _downstream_gates(),
        "downstream_gate_ids": list(DOWNSTREAM_GATE_IDS),
        "guardian_send_approval_relationship": {
            "separate_packet_required": True,
            "start_approval_does_not_authorize_send": True,
            "send_approval_currently_available": False,
            "send_approval_blocked_until_coupa_proof_exists": True,
            "send_approval_blocked_until_excel_match_verified": True,
        },
        "canonical_approval_payload_candidate": canonical_payload,
        "canonical_approval_payload_validation": canonical_validation,
        "existing_email_approval_machinery_discovery": discovery,
        "compatibility_detangling_note": discovery["send_approval_recommendation"],
        "reusable_approval_pattern": _reusable_pattern(),
        "authority_boundary": {
            "packet_spec_only": True,
            "approval_executable": False,
            "approval_can_become_executable_without_future_wiring": False,
            "no_authority_flags": dict(NO_AUTHORITY_FLAGS),
        },
        "status_summary": status_summary,
        "boundaries": dict(NO_AUTHORITY_FLAGS),
        **NO_AUTHORITY_FLAGS,
        "next_recommended_lane": "Capital Hilton Coupa Start Approval Operator Surface v0",
    }


def format_capital_hilton_coupa_start_approval_packet(payload: dict[str, Any]) -> str:
    lines = [
        "# Capital Hilton Coupa Start Approval Packet",
        "",
        "Status:",
        "- Start approval packet modeled: `true`.",
        "- Packet executable now: `false`.",
        "- Guardian message sent: `false`.",
        "- Coupa/browser/email/spreadsheet/credential/runtime authority added: `false`.",
        "",
        "## Approval Scope",
        f"- Approval type: `{payload['approval_type']}`.",
        f"- Workflow: `{payload['workflow']}`.",
        f"- Scope: {payload['workflow_scope']}.",
        "",
        "Authorizes:",
    ]
    lines.extend(f"- {item}" for item in payload["allowed_preparation_scope"])
    lines.extend(["", "Does not authorize:"])
    lines.extend(f"- {item}" for item in payload["blocked_authorities"])
    lines.extend(["", "## Downstream Gates Still Required"])
    for gate in payload["required_downstream_gates"]:
        lines.append(f"- `{gate['gate_id']}`: {gate['description']}")
    lines.extend(
        [
            "",
            "## Later Send Approval Compatibility",
            "- Existing Cassandra draft + Guardian approval machinery was inspected statically.",
            "- Later send approval should reuse or detangle existing draft/Guardian patterns rather than rebuild them.",
            "- Start approval remains separate from send approval.",
            "",
            "## Boundary",
            "- No Guardian/Telegram/Gmail/email message was sent.",
            "- No Coupa browser automation or submit was enabled.",
            "- No spreadsheet write, credential/PII access, raw secret storage, runtime authority, or send authority was added.",
            "",
            f"Next safe lane: {payload['next_recommended_lane']}",
            "",
        ]
    )
    return "\n".join(lines)


def export_capital_hilton_coupa_start_approval_packet(
    *,
    execution_path_json: str | Path = DEFAULT_EXECUTION_PATH,
    export_root: str | Path = DEFAULT_EXPORT_ROOT,
    generated_at: str | None = None,
) -> StartApprovalPacketExportResult:
    payload = build_capital_hilton_coupa_start_approval_packet(
        execution_path_json=execution_path_json,
        generated_at=generated_at,
    )
    root = _rooted(export_root)
    root.mkdir(parents=True, exist_ok=True)
    json_path = root / JSON_EXPORT_NAME
    operator_path = root / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(format_capital_hilton_coupa_start_approval_packet(payload), encoding="utf-8")
    status = payload["status_summary"]
    return StartApprovalPacketExportResult(
        schema_version=SCHEMA_VERSION,
        json_path=_display_path(json_path),
        operator_path=_display_path(operator_path),
        start_approval_packet_modeled=status["start_approval_packet_modeled"],
        start_approval_executable=status["start_approval_executable"],
        existing_email_approval_inspected=status["existing_cassandra_guardian_email_approval_inspected"],
        rebuild_existing_email_approval_machinery=status["rebuild_existing_email_approval_machinery"],
        runtime_authority_added=False,
        send_or_submit_authority_added=False,
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export Capital Hilton Coupa start approval packet spec.")
    parser.add_argument("--execution-path-json", default=str(DEFAULT_EXECUTION_PATH))
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT))
    parser.add_argument("--format", choices=("json", "operator", "summary"), default="summary")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    result = export_capital_hilton_coupa_start_approval_packet(
        execution_path_json=args.execution_path_json,
        export_root=args.export_root,
    )
    root = _rooted(args.export_root)
    if args.format == "json":
        print((root / JSON_EXPORT_NAME).read_text(encoding="utf-8"), end="")
    elif args.format == "operator":
        print((root / OPERATOR_EXPORT_NAME).read_text(encoding="utf-8"), end="")
    else:
        print(stable_json(result.__dict__), end="")
    return 0


__all__ = [
    "APPROVAL_TYPE",
    "DEFAULT_EXECUTION_PATH",
    "DOWNSTREAM_GATE_IDS",
    "JSON_EXPORT_NAME",
    "NO_AUTHORITY_FLAGS",
    "OPERATOR_EXPORT_NAME",
    "SCHEMA_VERSION",
    "WORKFLOW_ID",
    "build_capital_hilton_coupa_start_approval_packet",
    "export_capital_hilton_coupa_start_approval_packet",
    "format_capital_hilton_coupa_start_approval_packet",
    "stable_json",
]


if __name__ == "__main__":
    raise SystemExit(main())
