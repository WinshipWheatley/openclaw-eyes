"""Guardian responsibility and deterministic DNA audit v0.

This read-model audits existing Guardian/HITL/security/approval contracts before
new Guardian approval-request rails are added. It is metadata-only: it does not
send messages, create approvals, read credentials, access browsers or external
accounts, mutate spreadsheets, execute actions, or grant authority.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
SCHEMA_VERSION = "guardian_responsibility_dna_audit_v0"
JSON_EXPORT_NAME = "guardian_responsibility_dna_audit.json"
OPERATOR_EXPORT_NAME = "guardian_responsibility_dna_audit_OPERATOR.md"
NEXT_SAFE_LANE = "Guardian Draft Approval Request Contract v0"

CLASSIFICATIONS = {
    "CANONICAL_DETERMINISTIC",
    "TESTED_SUPPORTING_CONTRACT",
    "LEGACY_OR_REFERENCE",
    "IMPLIED_NOT_YET_CANONICAL",
    "UNSAFE_OR_BLOCKED",
    "UNKNOWN_NEEDS_REVIEW",
}

NO_AUTHORITY_FLAGS = {
    "review_only_audit": True,
    "guardian_modeled_as_executor": False,
    "generic_approval_authority_added": False,
    "approval_request_created": False,
    "approval_receipt_created": False,
    "execution_authority_added": False,
    "runtime_authority_added": False,
    "send_or_submit_authority_added": False,
    "browser_or_coupa_authority_added": False,
    "credential_or_oauth_access_added": False,
    "telegram_send_added": False,
    "gmail_draft_or_send_added": False,
    "calendar_access_added": False,
    "spreadsheet_mutation_added": False,
    "mission_control_app_changed": False,
    "repo_b_executed": False,
    "raw_private_content_inspected": False,
}


@dataclass(frozen=True)
class ResponsibilityRecord:
    responsibility_id: str
    label: str
    classification: str
    guardian_role: str
    explicit_not_responsible_for: tuple[str, ...]
    defining_files: tuple[str, ...]
    tested_by: tuple[str, ...]
    deterministic_status: str
    current_risk: str
    safe_next_use: str

    def __post_init__(self) -> None:
        if self.classification not in CLASSIFICATIONS:
            raise ValueError(f"invalid Guardian responsibility classification: {self.classification}")


RESPONSIBILITIES: tuple[ResponsibilityRecord, ...] = (
    ResponsibilityRecord(
        responsibility_id="specific_action_scope_gatekeeper",
        label="Specific action scope gatekeeper",
        classification="CANONICAL_DETERMINISTIC",
        guardian_role="Bind approval semantics to exact workflow/action scope, payload identity, TTL, idempotency, and receipts.",
        explicit_not_responsible_for=("generic authority", "freeform shell approval", "executor role"),
        defining_files=("guardian_hitl_sqlite_authority_contract.py", "templates/agent/guardian_approval_request_packet_template.json", "templates/agent/guardian_approval_decision_packet_template.json"),
        tested_by=("tests/test_guardian_hitl_sqlite_authority_contract.py", "tests/test_guardian_packet_templates.py"),
        deterministic_status="contract_defined_not_runtime_wired",
        current_risk="Readers may confuse a defined contract with live approval or execution authority.",
        safe_next_use="Use as the shape for future specific approval-request packets only.",
    ),
    ResponsibilityRecord(
        responsibility_id="start_vs_final_send_distinction",
        label="Start approval distinct from final send approval",
        classification="CANONICAL_DETERMINISTIC",
        guardian_role="Keep workflow start/preparation approval separate from any later final-send approval.",
        explicit_not_responsible_for=("treating start approval as send approval", "opening Coupa/email/browser authority"),
        defining_files=("capital_hilton_coupa_start_approval_packet.py", "capital_hilton_send_approval_gate.py"),
        tested_by=("tests/test_capital_hilton_coupa_start_approval_packet.py", "tests/test_capital_hilton_send_approval_gate.py"),
        deterministic_status="modeled_and_tested",
        current_risk="Future rails could accidentally collapse preparation and send into one approval if not checked.",
        safe_next_use="Require final-send packets to cite distinct proof, draft, attachment, and Guardian approval conditions.",
    ),
    ResponsibilityRecord(
        responsibility_id="review_request_receipt_execution_separation",
        label="Review, approval request, approval receipt, and execution separation",
        classification="CANONICAL_DETERMINISTIC",
        guardian_role="Preserve distinct lifecycle objects so review packets do not imply approval or execution.",
        explicit_not_responsible_for=("executing a reviewed action", "creating receipts before a decision", "approving generic future work"),
        defining_files=("guardian_hitl_sqlite_authority_contract.py", "cassandra_draft_review_packet.py", "capital_hilton_send_approval_gate.py"),
        tested_by=("tests/test_guardian_hitl_sqlite_authority_contract.py", "tests/test_cassandra_draft_review_packet.py", "tests/test_capital_hilton_send_approval_gate.py"),
        deterministic_status="modeled_and_tested",
        current_risk="Approval-request rails are safe only if they continue this separation.",
        safe_next_use="Add request packets before any receipt or execution wiring.",
    ),
    ResponsibilityRecord(
        responsibility_id="operator_sovereignty_power_stage",
        label="Operator sovereignty and power-stage boundary",
        classification="CANONICAL_DETERMINISTIC",
        guardian_role="Fail closed at higher-power boundaries and keep current Stage 1 visibility/review-only posture explicit.",
        explicit_not_responsible_for=("operator behavior surveillance", "hidden raw capture", "crossing stages without controls"),
        defining_files=("operator_sovereignty_power_stage_gate.py", "docs/operations/OPERATOR_SOVEREIGNTY_POWER_STAGE_GATE_V0.md"),
        tested_by=("tests/test_operator_sovereignty_power_stage_gate.py",),
        deterministic_status="modeled_and_tested",
        current_risk="Stage 2 approval generation could be mistaken for Stage 4 execution if labels are weak.",
        safe_next_use="Keep Guardian approval-request generation read-model-only until higher-stage controls exist.",
    ),
    ResponsibilityRecord(
        responsibility_id="sensitive_no_go_policy",
        label="Sensitive/no-go policy preservation",
        classification="TESTED_SUPPORTING_CONTRACT",
        guardian_role="Respect sensitive/no-go boundaries and avoid raw private content in normal read-models.",
        explicit_not_responsible_for=("raw private content ingestion", "credential/OAuth access", "legal/payment/contact raw storage"),
        defining_files=("openclaw_sensitive_policy.py", "file_event_queue.py", "docs/doctrine/SURFACE_AUTHORITY.md"),
        tested_by=("tests/test_ingestion_guard.py", "tests/test_file_event_queue.py", "tests/test_truth_gateway_boundary_audit.py"),
        deterministic_status="supporting_contracts_tested",
        current_risk="Guardian should monitor authority surfaces, not surveil private life or raw content.",
        safe_next_use="Reference no-go policy in future approval packets as boundary evidence.",
    ),
    ResponsibilityRecord(
        responsibility_id="operator_action_sqlite_spine",
        label="Operator Action SQLite spine",
        classification="TESTED_SUPPORTING_CONTRACT",
        guardian_role="Existing narrow SQLite request/approval/receipt pattern for allowlisted local actions.",
        explicit_not_responsible_for=("general remote builder", "send authority", "unbounded runtime execution"),
        defining_files=("operator_action.py", "operator_action_inbox.py", "scripts/request_operator_action.py"),
        tested_by=("tests/test_operator_action.py", "tests/test_operator_action_inbox.py", "tests/test_operator_action_covenant.py"),
        deterministic_status="active_narrow_supporting_spine",
        current_risk="Safe only if not generalized into arbitrary execution.",
        safe_next_use="Borrow receipt/request discipline, not execution behavior, for Guardian approval rails.",
    ),
    ResponsibilityRecord(
        responsibility_id="legacy_hitl_telegram_json_paths",
        label="Legacy HITL/Telegram/JSON approval compatibility paths",
        classification="LEGACY_OR_REFERENCE",
        guardian_role="Current compatibility evidence and transport/reference surfaces that must be reconciled before expansion.",
        explicit_not_responsible_for=("new generic sends", "new Telegram authority", "declaring old JSON obsolete without migration proof"),
        defining_files=("chief_approval_brain.py", "chief_guardian_listener.py", "chief_guardian_sender.py", "hitl_pending_store.py", "hitl_notification_service.py"),
        tested_by=("tests/test_guardian_hitl_authority_reconciliation.py", "tests/test_guardian_hitl_surface_disposition.py", "tests/test_hitl_notification_service.py"),
        deterministic_status="audited_as_authority_conflict_or_compatibility",
        current_risk="Mixed active/reference paths can look canonical unless the audit keeps them labeled.",
        safe_next_use="Keep as reference/compatibility until SQLite authority adapters exist.",
    ),
    ResponsibilityRecord(
        responsibility_id="cassandra_capital_hilton_review_integration",
        label="Cassandra and Capital Hilton review integration",
        classification="TESTED_SUPPORTING_CONTRACT",
        guardian_role="Guard later email approval by requiring governed draft, proof, attachment identity, and final-send gate conditions.",
        explicit_not_responsible_for=("Gmail draft creation", "email send", "Coupa/browser access", "PDF attachment", "spreadsheet mutation"),
        defining_files=("cassandra_draft_review_packet.py", "capital_hilton_external_artifact_proof_capture.py", "capital_hilton_send_approval_gate.py"),
        tested_by=("tests/test_cassandra_draft_review_packet.py", "tests/test_capital_hilton_external_artifact_proof_capture.py", "tests/test_capital_hilton_send_approval_gate.py"),
        deterministic_status="review_only_integration_tested",
        current_risk="Next Guardian lane could request approval before proof/draft/attachment identity is eligible.",
        safe_next_use="Build approval-request rail that remains unavailable until exact prerequisites are modeled.",
    ),
    ResponsibilityRecord(
        responsibility_id="cassandra_fixed_scope_recovery",
        label="Fixed-scope Cassandra recovery clearance",
        classification="IMPLIED_NOT_YET_CANONICAL",
        guardian_role="Special-case fixed-scope recovery approval/clearance evidence, not a general runtime model.",
        explicit_not_responsible_for=("general agent start/stop authority", "recovery command expansion", "unbounded service control"),
        defining_files=("scripts/request_cassandra_recovery_guardian_approval.py", "agent_presence.py", "guardian_hitl_authority_reconciliation.py"),
        tested_by=("tests/test_guardian_hitl_authority_reconciliation.py", "tests/test_agent_presence.py"),
        deterministic_status="special_case_observed_not_generalized",
        current_risk="Could be mistaken for general runtime activation authority.",
        safe_next_use="Leave out of draft approval rails except as no-general-runtime evidence.",
    ),
    ResponsibilityRecord(
        responsibility_id="future_live_external_actions",
        label="Future live external actions",
        classification="UNSAFE_OR_BLOCKED",
        guardian_role="Block until exact scope, proof, identity, receipt, and higher-stage execution controls exist.",
        explicit_not_responsible_for=("live Gmail", "calendar mutation", "Coupa/browser automation", "credential/OAuth access", "Telegram sends", "runtime execution"),
        defining_files=("google_access_broker.py", "cassandra_email_calendar_capability_reconciliation.py", "operator_sovereignty_power_stage_gate.py"),
        tested_by=("tests/test_google_access_policy.py", "tests/test_cassandra_email_calendar_capability_reconciliation.py", "tests/test_operator_sovereignty_power_stage_gate.py"),
        deterministic_status="blocked_before_new_authority",
        current_risk="Any approval rail that creates live access would violate the current lane boundary.",
        safe_next_use="Keep approval request generation separate from execution/connectors.",
    ),
    ResponsibilityRecord(
        responsibility_id="unknown_future_guardian_capability",
        label="Unknown future Guardian capability",
        classification="UNKNOWN_NEEDS_REVIEW",
        guardian_role="Fail closed when identity, scope, proof, authority, or source contract is unclear.",
        explicit_not_responsible_for=("implicit approval", "silent authority expansion", "private-life monitoring"),
        defining_files=("docs/operations/GUARDIAN_MACHINE_CONTRACT.md", "docs/doctrine/SURFACE_AUTHORITY.md"),
        tested_by=("tests/test_guardian_packet_templates.py",),
        deterministic_status="policy_only_fail_closed",
        current_risk="Unknown lanes can create vague Guardian personality/authority drift.",
        safe_next_use="Require a deterministic read-model/contract before implementation.",
    ),
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _export_root_path(export_root: str | Path) -> Path:
    path = Path(export_root)
    if path.is_absolute():
        return path
    return ROOT / path


def _display_path(path: str | Path) -> str:
    candidate = Path(path)
    try:
        return candidate.resolve().relative_to(ROOT.resolve()).as_posix()
    except (OSError, ValueError):
        return candidate.as_posix()


def build_guardian_responsibility_dna_audit(*, generated_at: str | None = None) -> dict[str, Any]:
    generated = generated_at or utc_now()
    classifications = Counter(item.classification for item in RESPONSIBILITIES)
    responsibility_rows = [asdict(item) for item in RESPONSIBILITIES]
    taxonomy = {
        "review_packet": "Visibility/review object; never approval or execution by itself.",
        "approval_request": "Specific proposed action packet with immutable scope, TTL, idempotency, payload hash, and blockers.",
        "approval_receipt": "Specific decision/result evidence bound to the exact request/payload; not generic authority.",
        "execution": "Future separately gated action path; not performed or enabled by this audit.",
    }
    gate_taxonomy = {
        "start_approval": {
            "meaning": "permission to begin governed preparation/review only",
            "send_authority": False,
            "defining_file": "capital_hilton_coupa_start_approval_packet.py",
        },
        "final_send_approval": {
            "meaning": "future specific draft+attachment approval after proof and blockers are satisfied",
            "send_authority_now": False,
            "defining_file": "capital_hilton_send_approval_gate.py",
        },
    }
    blocked_authorities = [
        "generic approval authority",
        "runtime execution",
        "send/submit authority",
        "browser/Coupa automation",
        "credential/OAuth/token access",
        "Gmail draft or email send",
        "Telegram send",
        "calendar read/write",
        "spreadsheet mutation",
        "raw private content surveillance",
        "Repo B execution",
    ]
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "generated_by": "codex",
        "generated_at": generated,
        "audit_kind": "guardian_responsibility_deterministic_dna_audit",
        "audit_status": "ready_for_specific_approval_request_contract_not_execution",
        "guardian_role_summary": "Guardian is the deterministic safety/HITL/security approval gatekeeper; Guardian is not an executor.",
        "responsibility_classifications": dict(sorted(classifications.items())),
        "responsibilities": responsibility_rows,
        "known_files_contracts": sorted({path for row in responsibility_rows for path in row["defining_files"]}),
        "tested_contracts": sorted({path for row in responsibility_rows for path in row["tested_by"]}),
        "approval_request_receipt_execution_taxonomy": taxonomy,
        "start_vs_final_send_approval_distinction": gate_taxonomy,
        "cassandra_capital_hilton_relevance": {
            "cassandra_current_role": "review-only draft packet producer, not executor",
            "capital_hilton_final_send_state": "blocked_until_coupa_excel_draft_attachment_and_specific_guardian_gate_conditions_are_satisfied",
            "approval_request_safe_only_when": "specific draft, attachment reference, Coupa proof, Excel match proof, and unresolved blockers are deterministic",
        },
        "operator_sovereignty_security_relevance": {
            "current_power_stage": "stage_1_visibility_read_model_review_packet",
            "higher_power_capabilities_blocked": True,
            "guardian_monitors_authority_surfaces_not_private_life": True,
            "unknown_or_ambiguous_authority_fails_closed": True,
        },
        "blocked_authority_surfaces": blocked_authorities,
        "unsafe_to_add_before_clarification": [
            "approval requests that omit exact draft/action scope",
            "approval requests without prerequisite proof state",
            "approval receipts without a specific request/payload hash",
            "any execution, connector, browser, send, submit, OAuth, credential, or runtime path",
            "treating legacy Telegram/JSON HITL paths as the new canonical store without adapter proof",
        ],
        "deterministic_and_tested_guardian_dna_found": True,
        "unclear_or_legacy_areas_remain": True,
        "next_safe_lane": NEXT_SAFE_LANE,
        "no_authority_flags": dict(NO_AUTHORITY_FLAGS),
        **NO_AUTHORITY_FLAGS,
    }
    return payload


def format_guardian_responsibility_dna_audit(payload: dict[str, Any]) -> str:
    lines = [
        "# Guardian Responsibility + Deterministic DNA Audit v0",
        "",
        f"Status: `{payload['audit_status']}`",
        f"Guardian role: {payload['guardian_role_summary']}",
        "",
        "## Responsibility Map",
    ]
    for item in payload["responsibilities"]:
        lines.extend(
            [
                f"- {item['label']}: `{item['classification']}`",
                f"  - Role: {item['guardian_role']}",
                f"  - Not responsible for: {', '.join(item['explicit_not_responsible_for'])}",
                f"  - Safe next use: {item['safe_next_use']}",
            ]
        )
    lines.extend(
        [
            "",
            "## Taxonomy",
            "- Review packet: visibility/review only; not approval or execution.",
            "- Approval request: specific immutable action scope with TTL/idempotency/payload hash.",
            "- Approval receipt: exact decision/result evidence; not generic authority.",
            "- Execution: future separately gated path; not enabled here.",
            "",
            "## Start vs Final Send",
            "- Start approval remains preparation-only and does not authorize send.",
            "- Final-send approval remains future, specific to one draft and one attachment, and unavailable until governed proof exists.",
            "",
            "## Blocked Authority",
        ]
    )
    for item in payload["blocked_authority_surfaces"]:
        lines.append(f"- {item}")
    lines.extend(
        [
            "",
            "## Cassandra / Capital Hilton",
            f"- Cassandra role: {payload['cassandra_capital_hilton_relevance']['cassandra_current_role']}",
            f"- Capital Hilton state: {payload['cassandra_capital_hilton_relevance']['capital_hilton_final_send_state']}",
            "",
            "## Next Safe Lane",
            f"`{payload['next_safe_lane']}`",
            "",
            "## Authority Boundary",
            "- Guardian is not modeled as executor: `false`",
            "- Generic approval authority added: `false`",
            "- Runtime/send/submit/browser/credential authority added: `false`",
        ]
    )
    return "\n".join(lines) + "\n"


def export_guardian_responsibility_dna_audit(
    *, export_root: str | Path = DEFAULT_EXPORT_ROOT, generated_at: str | None = None
) -> dict[str, Any]:
    root = _export_root_path(export_root)
    root.mkdir(parents=True, exist_ok=True)
    payload = build_guardian_responsibility_dna_audit(generated_at=generated_at)
    json_path = root / JSON_EXPORT_NAME
    operator_path = root / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(format_guardian_responsibility_dna_audit(payload), encoding="utf-8")
    return {
        "schema_version": payload["schema_version"],
        "json_path": _display_path(json_path),
        "operator_path": _display_path(operator_path),
        "next_safe_lane": payload["next_safe_lane"],
        "guardian_modeled_as_executor": payload["guardian_modeled_as_executor"],
        "generic_approval_authority_added": payload["generic_approval_authority_added"],
        "runtime_authority_added": payload["runtime_authority_added"],
        "send_or_submit_authority_added": payload["send_or_submit_authority_added"],
    }


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export Guardian responsibility/DNA audit read-models.")
    parser.add_argument("--export-root", default="generated/read_models")
    parser.add_argument("--format", choices=("operator", "json"), default="operator")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv if argv is not None else [])
    summary = export_guardian_responsibility_dna_audit(export_root=args.export_root)
    if args.format == "json":
        print(stable_json(summary), end="")
    else:
        print(format_guardian_responsibility_dna_audit(build_guardian_responsibility_dna_audit()), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
