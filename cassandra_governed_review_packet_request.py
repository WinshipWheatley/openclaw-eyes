"""Governed Cassandra/Clara request to review-packet proof.

This module proves a bounded operator request can refresh a review-only Capital
Hilton packet from governed Repo A facts/read-models. It does not send, reply,
submit a portal form, access credentials, run Repo B, or grant runtime authority.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from capital_hilton_actionable_review_packet import (
    DEFAULT_APPROVAL_PATH,
    DEFAULT_FACT_PACKET_PATH,
    JSON_EXPORT_NAME as CAPITAL_HILTON_JSON_EXPORT_NAME,
    OPERATOR_EXPORT_NAME as CAPITAL_HILTON_OPERATOR_EXPORT_NAME,
    export_capital_hilton_actionable_review_packet,
)
from cassandra_clara_fact_packet import (
    DEFAULT_ARTIFACT_ROOT,
    DEFAULT_EXPORT_ROOT,
    JSON_EXPORT_NAME as CASSANDRA_CLARA_JSON_EXPORT_NAME,
    OPERATOR_EXPORT_NAME as CASSANDRA_CLARA_OPERATOR_EXPORT_NAME,
    export_cassandra_clara_fact_packet,
    stable_json,
)
from business_ops_ledger import DEFAULT_DB_PATH


ROOT = Path(__file__).resolve().parent
SCHEMA_VERSION = "cassandra_governed_review_packet_request_proof_v0"
JSON_EXPORT_NAME = "cassandra_governed_review_packet_request_proof.json"
OPERATOR_EXPORT_NAME = "cassandra_governed_review_packet_request_proof_OPERATOR.md"
DEFAULT_STATUS_DRY_RUN_PATH = Path("generated/read_models/cassandra_send_status_dry_run.json")
DEFAULT_STRUCTURED_FACT_IMPORT_PATH = Path("generated/read_models/cassandra_chief_structured_fact_import.json")
DEFAULT_MEMORY_APPROVAL_PATH = Path("generated/read_models/cassandra_chief_memory_import_approval.json")

REQUEST_TEXT = (
    "Refresh the Capital Hilton invoice review packet from governed facts only. "
    "Include what is ready to invoice, what is blocked, and what I must confirm manually."
)

NO_AUTHORITY_FLAGS = {
    "review_only": True,
    "used_ad_hoc_memory_as_authority": False,
    "email_sent": False,
    "gmail_reply_sent": False,
    "calendar_write_triggered": False,
    "portal_submitted": False,
    "credentials_accessed": False,
    "spreadsheet_cells_read": False,
    "raw_private_data_read": False,
    "repo_b_executed": False,
    "runtime_authority_changed": False,
    "runtime_execution_triggered": False,
    "send_authority_added": False,
    "telegram_send_triggered": False,
    "old_files_treated_as_truth": False,
    "sqlite_facts_treated_as_final_truth": False,
}


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


def _read_json(path: str | Path) -> dict[str, Any]:
    target = _rooted(path)
    if not target.exists():
        return {}
    payload = json.loads(target.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _write_json(path: str | Path, payload: dict[str, Any]) -> str:
    target = _rooted(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(stable_json(payload), encoding="utf-8")
    return _display_path(target)


def _write_text(path: str | Path, text: str) -> str:
    target = _rooted(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")
    return _display_path(target)


def _request_id(text: str) -> str:
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return f"cass_review_request_{digest[:20]}"


def _prior_status(path: str | Path) -> dict[str, Any]:
    payload = _read_json(path)
    services = payload.get("services") or {}
    return {
        "source_path": _display_path(_rooted(path)),
        "schema_version": payload.get("schema_version"),
        "dry_run_resume_complete": payload.get("schema_version") == "cassandra_send_status_dry_run_v0",
        "advanced_beyond_startup_guard": bool((services.get("watcher") or {}).get("advanced_beyond_startup_guard"))
        and bool((services.get("briefing_scheduler") or {}).get("advanced_beyond_startup_guard")),
        "real_telegram_send_triggered": bool(payload.get("real_telegram_send_triggered")),
        "real_gmail_or_email_send_triggered": bool(payload.get("real_gmail_or_email_send_triggered")),
        "real_briefing_delivery_triggered": bool(payload.get("real_briefing_delivery_triggered")),
        "real_voice_delivery_triggered": bool(payload.get("real_voice_delivery_triggered")),
        "send_authority_added": bool(payload.get("send_authority_added")),
        "niles_used_for_cassandra_path": bool(payload.get("niles_used_for_cassandra_path")),
    }


def _fact_summary(cassandra_clara: dict[str, Any], capital_hilton: dict[str, Any]) -> dict[str, Any]:
    invoice_facts = capital_hilton.get("invoice_facts") or []
    completed_dates = (capital_hilton.get("review_calculation") or {}).get("known_completed_service_dates") or []
    known_fact_map = {fact.get("field_name"): fact.get("value_text") for fact in invoice_facts if fact.get("present")}
    return {
        "source_policy": cassandra_clara.get("source_policy"),
        "governed_fact_count": cassandra_clara.get("governed_fact_count", 0),
        "contact_candidate_count": cassandra_clara.get("contact_candidate_count", 0),
        "receivable_posture_count": cassandra_clara.get("receivable_posture_count", 0),
        "completed_service_dates": completed_dates,
        "rate_or_amount_per_gig": known_fact_map.get("rate_or_amount_per_gig", ""),
        "review_subtotal": (capital_hilton.get("review_calculation") or {}).get("candidate_subtotal", ""),
        "one_invoice_posture": known_fact_map.get("invoice_count_preference", ""),
        "po_coupa_gate": (capital_hilton.get("po_coupa_confirmation_gate") or {}).get("status", ""),
        "recipient_posture_review_only": bool((capital_hilton.get("recipient_posture") or {}).get("operator_confirmation_required")),
        "all_facts_parsed_evidence_not_truth": True,
        "all_facts_need_operator_confirmation": True,
    }


def _blocked_unknowns(capital_hilton: dict[str, Any]) -> list[dict[str, Any]]:
    blockers = list(capital_hilton.get("remaining_blockers") or [])
    return [
        {
            "blocker_id": item.get("blocker_id", "unknown_blocker"),
            "severity": item.get("severity", "unknown"),
            "description": item.get("description", ""),
            "next_safe_move": item.get("next_safe_move", ""),
        }
        for item in blockers
    ]


def build_governed_review_packet_request_proof(
    *,
    db_path: str | Path | None = None,
    export_root: str | Path = DEFAULT_EXPORT_ROOT,
    artifact_root: str | Path = DEFAULT_ARTIFACT_ROOT,
    status_dry_run_path: str | Path = DEFAULT_STATUS_DRY_RUN_PATH,
    structured_fact_import_path: str | Path = DEFAULT_STRUCTURED_FACT_IMPORT_PATH,
    memory_approval_path: str | Path = DEFAULT_MEMORY_APPROVAL_PATH,
    approval_path: str | Path = DEFAULT_APPROVAL_PATH,
    generated_at: str | None = None,
) -> dict[str, Any]:
    ts = generated_at or utc_now()
    status = _prior_status(status_dry_run_path)
    fact_result = export_cassandra_clara_fact_packet(
        db_path=db_path or DEFAULT_DB_PATH,
        artifact_root=artifact_root,
        export_root=export_root,
        generated_at=ts,
    )
    action_result = export_capital_hilton_actionable_review_packet(
        db_path=db_path or DEFAULT_DB_PATH,
        fact_packet_path=Path(export_root) / CASSANDRA_CLARA_JSON_EXPORT_NAME,
        approval_path=approval_path,
        export_root=export_root,
        generated_at=ts,
    )
    export_root_path = _rooted(export_root)
    cassandra_clara = _read_json(export_root_path / CASSANDRA_CLARA_JSON_EXPORT_NAME)
    capital_hilton = _read_json(export_root_path / CAPITAL_HILTON_JSON_EXPORT_NAME)
    structured_import = _read_json(structured_fact_import_path)
    memory_approval = _read_json(memory_approval_path)
    request_id = _request_id(REQUEST_TEXT)
    packet_ready = bool(capital_hilton.get("actionable_for_manual_review")) and not bool(capital_hilton.get("ready_for_submission"))
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_by": "codex",
        "generated_at": ts,
        "request": {
            "request_id": request_id,
            "request_source": "operator_prompt_lane",
            "request_text": REQUEST_TEXT,
            "request_hash": hashlib.sha256(REQUEST_TEXT.encode("utf-8")).hexdigest(),
            "live_telegram_request_used": False,
            "command_level_governed_request_used": True,
        },
        "prior_lane_status": status,
        "route": {
            "selected_route": "cassandra_clara_capital_hilton_review_packet",
            "internal_agent": "cassandra",
            "external_persona": "Clara Reid",
            "target_workflow": "capital_hilton_invoice",
            "route_reason": "Capital Hilton review packet has imported SQLite facts and a review-only actionable packet builder.",
            "work_board_or_agent_packet_created": False,
            "operator_action_created": False,
        },
        "facts_and_sources_consulted": [
            {
                "source_id": "business_ops_ledger_sqlite",
                "source_path": _display_path(db_path or DEFAULT_DB_PATH),
                "source_role": "governed_sqlite_fact_surface",
                "authority_status": "parsed_evidence_not_truth",
            },
            {
                "source_id": "cassandra_clara_fact_packet",
                "source_path": _display_path(export_root_path / CASSANDRA_CLARA_JSON_EXPORT_NAME),
                "source_role": "review_only_fact_packet",
                "authority_status": "review_packet_not_truth",
            },
            {
                "source_id": "capital_hilton_actionable_review_packet",
                "source_path": _display_path(export_root_path / CAPITAL_HILTON_JSON_EXPORT_NAME),
                "source_role": "operator_review_packet",
                "authority_status": "review_only_not_submission_authority",
            },
            {
                "source_id": "structured_fact_import",
                "source_path": _display_path(_rooted(structured_fact_import_path)),
                "source_role": "import_receipt",
                "authority_status": "parsed_evidence_not_truth",
                "records_imported_count": structured_import.get("records_imported_count"),
                "raw_logs_imported": structured_import.get("raw_logs_imported"),
                "old_hitl_imported": structured_import.get("old_hitl_imported"),
            },
            {
                "source_id": "memory_import_approval",
                "source_path": _display_path(_rooted(memory_approval_path)),
                "source_role": "operator_approval_receipt",
                "authority_status": "approval_receipt_not_raw_data",
                "raw_content_read": memory_approval.get("raw_content_read"),
                "data_imported": memory_approval.get("data_imported"),
            },
            {
                "source_id": "capital_hilton_review_packet_approval",
                "source_path": _display_path(_rooted(approval_path)),
                "source_role": "manual_review_preparation_approval",
                "authority_status": "review_approval_not_send_or_submit_authority",
            },
        ],
        "packet_outputs": {
            "cassandra_clara_json": _display_path(export_root_path / CASSANDRA_CLARA_JSON_EXPORT_NAME),
            "cassandra_clara_operator": _display_path(export_root_path / CASSANDRA_CLARA_OPERATOR_EXPORT_NAME),
            "capital_hilton_actionable_json": _display_path(export_root_path / CAPITAL_HILTON_JSON_EXPORT_NAME),
            "capital_hilton_actionable_operator": _display_path(export_root_path / CAPITAL_HILTON_OPERATOR_EXPORT_NAME),
            "artifact_root": _display_path(_rooted(artifact_root)),
            "cassandra_clara_export_result": fact_result.__dict__,
            "capital_hilton_export_result": action_result.__dict__,
        },
        "capital_hilton_fact_summary": _fact_summary(cassandra_clara, capital_hilton),
        "blocked_or_manual_confirmation": _blocked_unknowns(capital_hilton),
        "packet_review_only": True,
        "capital_hilton_packet_ready_for_operator_review": packet_ready,
        "proof_receipts": [
            {
                "receipt_kind": "request_received",
                "status": "observed_command_level_request",
                "request_id": request_id,
            },
            {
                "receipt_kind": "route_selected",
                "status": "capital_hilton_review_packet",
                "send_authority_added": False,
            },
            {
                "receipt_kind": "packet_generated",
                "status": "review_only_packet_refreshed",
                "packet_ready_for_operator_review": packet_ready,
            },
            {
                "receipt_kind": "external_authority_blocked",
                "status": "email_portal_runtime_sends_blocked",
                "telegram_send_triggered": False,
                "gmail_or_email_send_triggered": False,
                "portal_submit_triggered": False,
                "runtime_execution_triggered": False,
            },
        ],
        "boundaries": dict(NO_AUTHORITY_FLAGS),
        **NO_AUTHORITY_FLAGS,
        "next_recommended_lane": "Capital Hilton Manual Coupa PO Confirmation",
    }


def render_operator_markdown(payload: dict[str, Any]) -> str:
    facts = payload["capital_hilton_fact_summary"]
    blockers = payload["blocked_or_manual_confirmation"]
    lines = [
        "# Cassandra Governed Request -> Review Packet Proof",
        "",
        "Status:",
        f"- Packet ready for operator review: `{str(payload['capital_hilton_packet_ready_for_operator_review']).lower()}`.",
        "- Review only: `true`.",
        "- Email sent: `false`.",
        "- Portal submitted: `false`.",
        "- Runtime execution triggered: `false`.",
        "- Send authority added: `false`.",
        "",
        "## Request",
        f"- {payload['request']['request_text']}",
        "",
        "## Route",
        f"- Selected: `{payload['route']['selected_route']}`",
        "- Input mode: command-level governed request proof; no Telegram send/reply.",
        "",
        "## Governed Facts Used",
        f"- Completed service dates: {', '.join(facts['completed_service_dates']) or '[missing]'}",
        f"- Rate: {facts['rate_or_amount_per_gig'] or '[missing]'}",
        f"- Review subtotal: {facts['review_subtotal'] or '[manual calculation required]'}",
        f"- Invoice posture: {facts['one_invoice_posture'] or '[missing]'}",
        "- Facts remain parsed evidence, not truth; operator confirmation is still required.",
        "",
        "## Manual Gates Still Blocked",
    ]
    if not blockers:
        lines.append("- None for manual review preparation.")
    else:
        for blocker in blockers:
            lines.append(f"- `{blocker['blocker_id']}`: {blocker['description']} Next: {blocker['next_safe_move']}")
    lines.extend(
        [
            "",
            "## Outputs",
            f"- Cassandra/Clara packet: `{payload['packet_outputs']['cassandra_clara_operator']}`",
            f"- Capital Hilton actionable packet: `{payload['packet_outputs']['capital_hilton_actionable_operator']}`",
            f"- Artifact folder: `{payload['packet_outputs']['artifact_root']}`",
            "",
            "## Boundaries",
            "- No Telegram send.",
            "- No Gmail/email send or reply.",
            "- No Coupa or portal submit.",
            "- No credentials accessed.",
            "- No spreadsheet cells read.",
            "- No runtime authority added.",
            "",
            f"Next recommended lane: {payload['next_recommended_lane']}",
            "",
        ]
    )
    return "\n".join(lines)


def export_governed_review_packet_request_proof(
    *,
    db_path: str | Path | None = None,
    export_root: str | Path = DEFAULT_EXPORT_ROOT,
    artifact_root: str | Path = DEFAULT_ARTIFACT_ROOT,
    status_dry_run_path: str | Path = DEFAULT_STATUS_DRY_RUN_PATH,
    structured_fact_import_path: str | Path = DEFAULT_STRUCTURED_FACT_IMPORT_PATH,
    memory_approval_path: str | Path = DEFAULT_MEMORY_APPROVAL_PATH,
    approval_path: str | Path = DEFAULT_APPROVAL_PATH,
    generated_at: str | None = None,
) -> dict[str, str]:
    payload = build_governed_review_packet_request_proof(
        db_path=db_path,
        export_root=export_root,
        artifact_root=artifact_root,
        status_dry_run_path=status_dry_run_path,
        structured_fact_import_path=structured_fact_import_path,
        memory_approval_path=memory_approval_path,
        approval_path=approval_path,
        generated_at=generated_at,
    )
    root = _rooted(export_root)
    return {
        "json": _write_json(root / JSON_EXPORT_NAME, payload),
        "operator": _write_text(root / OPERATOR_EXPORT_NAME, render_operator_markdown(payload)),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export Cassandra governed review packet request proof.")
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH))
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT))
    parser.add_argument("--artifact-root", default=str(DEFAULT_ARTIFACT_ROOT))
    parser.add_argument("--status-dry-run-json", default=str(DEFAULT_STATUS_DRY_RUN_PATH))
    parser.add_argument("--structured-fact-import-json", default=str(DEFAULT_STRUCTURED_FACT_IMPORT_PATH))
    parser.add_argument("--memory-approval-json", default=str(DEFAULT_MEMORY_APPROVAL_PATH))
    parser.add_argument("--approval-json", default=str(DEFAULT_APPROVAL_PATH))
    parser.add_argument("--format", choices=("json", "operator", "both"), default="both")
    args = parser.parse_args(argv)
    paths = export_governed_review_packet_request_proof(
        db_path=args.db,
        export_root=args.export_root,
        artifact_root=args.artifact_root,
        status_dry_run_path=args.status_dry_run_json,
        structured_fact_import_path=args.structured_fact_import_json,
        memory_approval_path=args.memory_approval_json,
        approval_path=args.approval_json,
    )
    if args.format in {"json", "both"}:
        print(paths["json"])
    if args.format in {"operator", "both"}:
        print(paths["operator"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
