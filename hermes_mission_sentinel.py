"""Hermes mission sentinel for the Live Arts MD 4 PM critical path.

Hermes observes mission state, deadline pressure, blockers, and the next safe
package. It does not execute, approve, send, poll Telegram/Gmail, read workbook
cells, generate invoices, post ledger entries, or mutate production state.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping
from zoneinfo import ZoneInfo

import live_arts_md_invoice_review_bundle
import workflow_operating_mode_policy


SCHEMA_VERSION = "hermes_mission_sentinel_v0"
READ_MODEL_ID = "hermes_mission_sentinel"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
OPERATOR_EXPORT_NAME = f"{READ_MODEL_ID}_OPERATOR.md"
CONTRACT_STATUS = "READINESS_SENTINEL_NO_EXECUTION"
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_BRIDGE_EXPORT_ROOT = Path("/mnt/e/openclaw/generated/read_models")
DEFAULT_GENERATED_AT = "2026-05-28T15:01:54-04:00"
DEADLINE_LOCAL = "2026-05-28T16:00:00-04:00"
LOCAL_TZ = ZoneInfo("America/New_York")

AUTHORITY_BOUNDARY = {
    "email_send_allowed": False,
    "gmail_draft_creation_allowed": False,
    "gmail_polling_allowed": False,
    "coupa_browser_allowed": False,
    "workbook_cell_read_allowed": False,
    "invoice_generation_allowed": False,
    "ledger_mutation_allowed": False,
    "production_mutation_allowed": False,
    "repo_b_runtime_start_allowed": False,
    "live_model_call_allowed": False,
    "tool_execution_allowed": False,
    "approval_execution_allowed": False,
}


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def _content_hash(payload: Mapping[str, Any]) -> str:
    clone = json.loads(stable_json(dict(payload)))
    clone.get("machine_proof", {}).pop("content_hash", None)
    return "sha256:" + hashlib.sha256(stable_json(clone).encode("utf-8")).hexdigest()


def _parse_local(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=LOCAL_TZ)
    return parsed.astimezone(LOCAL_TZ)


def time_remaining_bucket(*, now_local: str, deadline_local: str = DEADLINE_LOCAL) -> dict[str, Any]:
    now = _parse_local(now_local)
    deadline = _parse_local(deadline_local)
    seconds = int((deadline - now).total_seconds())
    minutes = max(0, seconds // 60)
    if seconds <= 0:
        bucket = "CUTOFF_PASSED"
    elif minutes <= 15:
        bucket = "FINAL_15_MINUTES"
    elif minutes <= 45:
        bucket = "UNDER_45_MINUTES"
    elif minutes <= 75:
        bucket = "UNDER_75_MINUTES"
    else:
        bucket = "ENOUGH_TIME_IF_BLOCKERS_CLEAR"
    return {
        "now_local": now.isoformat(),
        "deadline_local": deadline.isoformat(),
        "minutes_remaining": minutes,
        "bucket": bucket,
    }


def _live_arts_state(bundle: Mapping[str, Any] | None = None) -> dict[str, Any]:
    payload = (
        dict(bundle)
        if bundle is not None
        else live_arts_md_invoice_review_bundle.build_live_arts_md_bundle(generated_at=DEFAULT_GENERATED_AT)
    )
    source = payload["source_workbook"]
    draft = payload["clara_invoice_email_draft_package"]
    return {
        "source_workbook_confirmed": source.get("status") == "CONFIRMED",
        "source_workbook_path": source.get("source_workbook_mac_path") or source.get("workbook_path_ref"),
        "invoice_selection_status": payload["invoice_selection"]["status"],
        "invoice_artifact_status": payload["invoice_artifact"]["status"],
        "attachment_ready": bool(payload["invoice_artifact"]["attachment_ready"]),
        "recipient_status": payload["recipient_state"]["status"],
        "approval_ready": bool(payload["approval_footer"]["approval_ready"]),
        "send_ready": payload["send_readiness"]["manual_send_package_status"] == "MANUAL_SEND_PACKAGE_READY",
        "supplier_portal_required": bool(payload["supplier_portal_invoice_submission"]["required"]),
        "clara_draft_status": draft["draft_status"],
        "clara_target_blueprint_present": "target_client_email_blueprint" in draft,
        "candidate_count": payload["invoice_candidate_register"]["candidate_count"],
        "invoice_candidates": tuple(payload["invoice_candidate_register"]["invoice_candidates"]),
        "recipient_candidates": tuple(payload["recipient_state"]["recipient_candidates"]),
    }


def _critical_path() -> tuple[dict[str, Any], ...]:
    return (
        {
            "step_ref": "critical_path:choose_invoice_candidate",
            "title": "Choose invoice candidate",
            "target": "Pick 2026-1001 Speaker Rental or 2026-1002 AV Tech for today's send.",
            "required_receipt": "live_arts_md_invoice_candidate_selected_receipt",
            "status": "BLOCKING",
        },
        {
            "step_ref": "critical_path:artifact_attachment",
            "title": "Get invoice artifact/attachment right",
            "target": "Export/link the correct invoice artifact and confirm attachment readiness.",
            "required_receipt": "invoice_attachment_confirmed_receipt",
            "status": "BLOCKING",
        },
        {
            "step_ref": "critical_path:recipients",
            "title": "Confirm recipients",
            "target": "Confirm Dane as To, Draper/Earnie/Winship as CC, and provide missing emails.",
            "required_receipt": "recipient_confirmation_receipt",
            "status": "BLOCKING",
        },
        {
            "step_ref": "critical_path:clara_email",
            "title": "Finalize Clara email package",
            "target": "Convert the target blueprint into the exact approval-ready client email after prerequisites exist.",
            "required_receipt": "clara_email_draft_receipt",
            "status": "BLOCKED_BY_ARTIFACT_AND_RECIPIENTS",
        },
        {
            "step_ref": "critical_path:approval_or_manual_send",
            "title": "Send path decision",
            "target": "If OpenClaw is not send-ready by safe cutoff, Winship manually sends and captures proof.",
            "required_receipt": "manual_send_receipt_or_email_send_receipt",
            "status": "DEADLINE_DECISION",
        },
    )


def _manual_send_checklist() -> tuple[str, ...]:
    return (
        "recipient list",
        "subject",
        "attachment/file name",
        "send timestamp",
        "invoice id",
        "amount",
        "payment watch target",
        "manual send receipt",
    )


def _next_packages() -> tuple[dict[str, Any], ...]:
    return (
        {
            "package_ref": "live_arts_md_select_invoice_candidate",
            "prompt": "Select the Live Arts MD invoice candidate for today's send: 2026-1001 Speaker Rental or 2026-1002 AV Tech.",
            "expected_receipt": "live_arts_md_invoice_candidate_selected_receipt",
            "stop_condition": "No invoice candidate selected.",
        },
        {
            "package_ref": "live_arts_md_link_invoice_artifact",
            "prompt": "Link the operator-provided Live Arts MD invoice artifact by metadata only and keep it candidate-only until attachment confirmation.",
            "expected_receipt": "operator_provided_invoice_artifact_linked_candidate_receipt",
            "stop_condition": "No artifact path or attachment confirmation.",
        },
        {
            "package_ref": "live_arts_md_confirm_recipients",
            "prompt": "Confirm Dane, Draper, Earnie, and Winship recipient details without inventing emails.",
            "expected_receipt": "recipient_confirmation_receipt",
            "stop_condition": "Missing recipient email or inclusion confirmation.",
        },
        {
            "package_ref": "live_arts_md_manual_send_receipt_after_fallback",
            "prompt": "If Winship manually sends before 4 PM, capture the manual send receipt and payment watch target.",
            "expected_receipt": "manual_send_receipt",
            "stop_condition": "Manual send proof missing.",
        },
    )


def build_hermes_mission_sentinel(
    *,
    generated_at: str | None = None,
    deadline_local: str = DEADLINE_LOCAL,
    live_arts_bundle: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or DEFAULT_GENERATED_AT
    clock = time_remaining_bucket(now_local=generated_at, deadline_local=deadline_local)
    live_state = _live_arts_state(live_arts_bundle)
    operating_context = workflow_operating_mode_policy.classify_operating_context(
        operator_intent="Send the Live Arts invoice today",
        access_class="WINSHIP_DEVELOPER",
        channel="APP",
        client_ref="live_arts_md",
        workflow_ref="live_arts_md_invoice_workflow",
    )
    current_blockers = []
    if live_state["invoice_selection_status"] not in {"CANDIDATE_SELECTED", "COMPLETE"}:
        current_blockers.append("invoice candidate not selected")
    if not live_state["attachment_ready"]:
        current_blockers.append("invoice artifact/attachment not ready")
    if live_state["recipient_status"] != "CONFIRMED":
        current_blockers.append("recipient details unconfirmed")
    if not live_state["approval_ready"]:
        current_blockers.append("approval/send readiness disabled")
    near_cutoff = clock["bucket"] in {"UNDER_45_MINUTES", "FINAL_15_MINUTES", "CUTOFF_PASSED"}
    manual_fallback_time = "2026-05-28T15:45:00-04:00"
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "contract_status": CONTRACT_STATUS,
        "generated_at": generated_at,
        "mission_ref": "hermes_mission:live_arts_md_invoice_4pm_cutoff",
        "world_ref": "finance",
        "workflow_ref": "live_arts_md_invoice_workflow",
        "client_ref": "live_arts_md",
        "access_class": "WINSHIP_DEVELOPER",
        "current_mode": {
            "primary": "OPERATOR_RUNTIME",
            "urgency": "URGENT_DEADLINE",
            "developer_context_available": True,
            "human_trial_if_testing_in_app": True,
            "workflow_operating_mode_policy_ref": "generated/read_models/workflow_operating_mode_policy.json",
        },
        "deadline_local": deadline_local,
        "time_remaining": clock,
        "urgent_goal": "Send the Live Arts MD invoice today before the 4:00 PM cutoff, or manually send it.",
        "short_term_goal": "Select the invoice, get the artifact/email package correct, and confirm recipients.",
        "medium_term_goal": "Capture send proof and start payment watch readiness.",
        "long_term_goal": "Ledger/tax evidence after payment proof, not from workbook existence.",
        "live_arts_md_state": live_state,
        "critical_path": _critical_path(),
        "current_blockers": tuple(current_blockers),
        "automation_ready_status": "NOT_SEND_READY",
        "manual_fallback_required_by": manual_fallback_time,
        "recommended_human_action": (
            "Manually send the invoice and capture proof now if OpenClaw has not produced a safe send-ready package."
            if near_cutoff
            else "Prioritize selecting the invoice and confirming/linking the artifact before the manual fallback time."
        ),
        "recommended_codex_pc_action": (
            "Stop broad workflow building; only work on the shortest path to artifact/recipient/send-proof readiness."
        ),
        "recommended_codex_mac_action": (
            "Keep the app focused on choosing the invoice, linking/opening the artifact, recipient confirmation, and manual-send proof capture."
        ),
        "do_not_spend_time_on": (
            "Telegram integration",
            "Coupa/PO rails",
            "ledger automation",
            "payment matching",
            "new dashboards",
            "large refactors",
            "invoice generator architecture unless it directly produces today's safe artifact path",
        ),
        "proof_to_capture_after_manual_send": _manual_send_checklist(),
        "next_right_sized_packages": _next_packages(),
        "drift_warnings": (
            "Do not keep building general framework past the cutoff.",
            "Do not fake send, attachment, approval, payment, or ledger receipts.",
            "Running workbook facts are source intent, not send/payment proof.",
            "If the invoice is manually sent, capture proof before resuming build work.",
        ),
        "operator_summary": (
            "Live Arts MD is not send-ready in OpenClaw yet. The confirmed workbook and candidate facts exist, "
            "but the invoice candidate, attachment, recipients, approval, and send proof still block automation. "
            "If this is not cleared by the safe cutoff, Winship should manually send and record proof."
        ),
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "machine_proof": {
            "read_model_only": True,
            "hermes_executes": False,
            "hermes_approves": False,
            "hermes_sends": False,
            "no_email_send": True,
            "no_gmail_draft": True,
            "no_gmail_polling": True,
            "no_coupa_browser": True,
            "no_workbook_cell_read": True,
            "no_invoice_generation": True,
            "no_ledger_mutation": True,
            "no_production_mutation": True,
            "all_authority_flags_false": all(value is False for value in AUTHORITY_BOUNDARY.values()),
        },
        "proof_refs": (
            "generated/read_models/live_arts_md_invoice_review_bundle.json",
            "generated/read_models/live_arts_md_invoice_candidate_register.json",
            "generated/read_models/workflow_operating_mode_policy.json",
        ),
    }
    payload["machine_proof"]["content_hash"] = _content_hash(payload)
    return payload


def render_operator_summary(payload: Mapping[str, Any]) -> str:
    lines = [
        "# Hermes Mission Sentinel",
        "",
        f"Goal: {payload['urgent_goal']}",
        f"Cutoff: {payload['deadline_local']}",
        f"Time bucket: {payload['time_remaining']['bucket']} ({payload['time_remaining']['minutes_remaining']} minutes remaining)",
        "",
        "Current blocker: invoice candidate/artifact/recipient/send readiness.",
        "",
        "Recommended human action:",
        payload["recommended_human_action"],
        "",
        "Manual send proof to capture:",
        *[f"- {item}" for item in payload["proof_to_capture_after_manual_send"]],
        "",
        "Codex PC should stop spending time on:",
        *[f"- {item}" for item in payload["do_not_spend_time_on"]],
        "",
        "Boundary: Hermes observes only. No email, Gmail, Coupa/browser, workbook cell read, invoice generation, ledger mutation, production mutation, live model/tool action, or Repo B start.",
    ]
    return "\n".join(lines) + "\n"


def export_read_model(
    *,
    export_root: Path = DEFAULT_EXPORT_ROOT,
    bridge_export_root: Path | None = DEFAULT_BRIDGE_EXPORT_ROOT,
    generated_at: str | None = None,
    deadline_local: str = DEADLINE_LOCAL,
) -> dict[str, Any]:
    payload = build_hermes_mission_sentinel(generated_at=generated_at, deadline_local=deadline_local)
    export_root.mkdir(parents=True, exist_ok=True)
    json_path = export_root / JSON_EXPORT_NAME
    operator_path = export_root / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(render_operator_summary(payload), encoding="utf-8")
    bridge_path = None
    if bridge_export_root is not None:
        bridge_export_root.mkdir(parents=True, exist_ok=True)
        bridge_path = bridge_export_root / JSON_EXPORT_NAME
        shutil.copy2(json_path, bridge_path)
    return {
        "json_path": json_path.as_posix(),
        "operator_path": operator_path.as_posix(),
        "bridge_path": bridge_path.as_posix() if bridge_path else None,
        "mission_ref": payload["mission_ref"],
        "time_remaining_bucket": payload["time_remaining"]["bucket"],
        "automation_ready_status": payload["automation_ready_status"],
        "content_hash": payload["machine_proof"]["content_hash"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export Hermes mission sentinel read-model.")
    parser.add_argument("--export-root", default=DEFAULT_EXPORT_ROOT.as_posix())
    parser.add_argument("--bridge-export-root", default=DEFAULT_BRIDGE_EXPORT_ROOT.as_posix())
    parser.add_argument("--no-bridge", action="store_true")
    parser.add_argument("--generated-at", default=DEFAULT_GENERATED_AT)
    parser.add_argument("--deadline-local", default=DEADLINE_LOCAL)
    args = parser.parse_args(argv)
    result = export_read_model(
        export_root=Path(args.export_root),
        bridge_export_root=None if args.no_bridge else Path(args.bridge_export_root),
        generated_at=args.generated_at,
        deadline_local=args.deadline_local,
    )
    print(stable_json(result), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
