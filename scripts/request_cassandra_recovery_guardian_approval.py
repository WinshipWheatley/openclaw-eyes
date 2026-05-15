#!/usr/bin/env python3
"""Request Guardian approval for one Cassandra recovery clearance.

This script is intended for the OpenClaw runtime host where the Guardian
approval channel is configured. It can approve a local Cassandra recovery
clearance after Guardian says yes, but it never executes recovery itself.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent_presence import (
    approve_agent_recovery_clearance,
    build_agent_recovery_clearance_report,
    format_agent_recovery_clearance_result,
    reject_agent_recovery_clearance,
    request_agent_recovery_clearance,
    stable_json,
)
from business_ops_ledger import DEFAULT_DB_PATH, record_approval_request_record
from chief_approval_brain import request_approval


ACTION_LABEL = "Start Cassandra fixed systemd user units"
ACTION_DESCRIPTION = (
    "Approve one Cassandra recovery clearance for the fixed systemd user start action: "
    "systemctl --user start cassandra-listener.service cassandra-watcher.service "
    "cassandra-briefing-scheduler.service. This approval does not execute recovery."
)


def _latest_requested_clearance_id(*, db_path: str) -> str | None:
    report = build_agent_recovery_clearance_report(db_path=db_path, agent="cassandra")
    for item in report.get("items", []):
        if item.get("status") == "requested":
            return str(item["clearance_id"])
    return None


def run_guardian_clearance_flow(
    *,
    db_path: str,
    clearance_id: str | None = None,
    requested_by: str = "chief",
    reason: str = "Cassandra expected online but offline; request one Guardian-approved fixed start attempt.",
    approved_by: str = "guardian",
    approval_func: Callable[..., bool] = request_approval,
) -> dict:
    resolved_clearance_id = clearance_id or _latest_requested_clearance_id(db_path=db_path)
    request_payload = None
    if not resolved_clearance_id:
        request_payload = request_agent_recovery_clearance(
            agent_id="cassandra",
            requested_by=requested_by,
            reason=reason,
            db_path=db_path,
        )
        resolved_clearance_id = request_payload["clearance_id"]

    record_approval_request_record(
        packet_id=f"guardian_cassandra_recovery_request_{resolved_clearance_id}",
        packet_type="guardian.approval_request_packet",
        approval_id=resolved_clearance_id,
        approval_request_summary=ACTION_DESCRIPTION,
        requester_agent=requested_by,
        action_intent_ref=resolved_clearance_id,
        risk_tier="Tier 2",
        db_path=db_path,
        agent_id="cassandra",
        recovery_action_id="cassandra_systemd_user_start",
        no_auto_approval=True,
        execution_recorded=False,
        no_execution_recorded=True,
    )

    approved = approval_func(
        ACTION_DESCRIPTION,
        requester=requested_by,
        allow_yes_for_all=False,
        explicit_tier=2,
        approval_context={
            "action_label": ACTION_LABEL,
            "mode": "Guardian approval for one local recovery clearance; no execution",
            "subject": "Cassandra recovery clearance",
            "thread_synopsis": (
                "Cassandra is expected online but offline. Recovery remains blocked until "
                "Guardian approves this exact clearance."
            ),
            "proposed_send": (
                "If approved, backend marks one fixed Cassandra recovery clearance approved. "
                "A separate recover_agent.py --execute call is still required."
            ),
            "draft_preview": (
                "No arbitrary shell, no Telegram send, no model/tool/container execution, "
                "no broad agent activation."
            ),
        },
    )

    if not approved:
        rejection = reject_agent_recovery_clearance(
            clearance_id=resolved_clearance_id,
            rejected_by=approved_by,
            reason="Guardian denied, timed out, or delivery failed.",
            db_path=db_path,
        )
        return {
            "status": "guardian_denied",
            "clearance_id": resolved_clearance_id,
            "requested": request_payload,
            "decision": rejection,
            "summary": "Guardian did not approve Cassandra recovery clearance; no recovery authority granted.",
        }

    approval = approve_agent_recovery_clearance(
        clearance_id=resolved_clearance_id,
        approved_by=approved_by,
        approval_note="Guardian approved one Cassandra fixed systemd user start clearance.",
        confirm_agent="cassandra",
        confirm_action="cassandra_systemd_user_start",
        db_path=db_path,
    )
    return {
        "status": "guardian_approved",
        "clearance_id": resolved_clearance_id,
        "requested": request_payload,
        "decision": approval,
        "summary": "Guardian approved the Cassandra clearance; recovery still has not executed.",
    }


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Send Guardian approval request for Cassandra recovery clearance.")
    parser.add_argument("--db", default=DEFAULT_DB_PATH)
    parser.add_argument("--clearance-id")
    parser.add_argument("--requested-by", default="chief")
    parser.add_argument("--reason", default="Cassandra expected online but offline; request one Guardian-approved fixed start attempt.")
    parser.add_argument("--approved-by", default="guardian")
    parser.add_argument("--format", choices=("operator", "json"), default="operator")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    payload = run_guardian_clearance_flow(
        db_path=args.db,
        clearance_id=args.clearance_id,
        requested_by=args.requested_by,
        reason=args.reason,
        approved_by=args.approved_by,
    )
    if args.format == "json":
        print(stable_json(payload), end="")
    else:
        decision = payload.get("decision") or {}
        if decision.get("status") == "approved":
            print(format_agent_recovery_clearance_result(decision))
        else:
            print("OpenClaw Cassandra Guardian Recovery Approval v0")
            print("")
            print(f"Status: `{payload['status']}`")
            print(f"Clearance: `{payload['clearance_id']}`")
            print(f"Summary: {payload['summary']}")
            print("")
            print("Boundary:")
            print("- Guardian approval request only; no recovery command executed.")
    return 0 if payload["status"] == "guardian_approved" else 1


if __name__ == "__main__":
    raise SystemExit(main())
