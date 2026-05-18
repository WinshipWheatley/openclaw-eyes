"""Cassandra email/calendar capability reconciliation read-model v0.

This read-model reconciles older Cassandra/Clara email and calendar capability
with the current governed OpenClaw steel-thread. It is audit metadata only: it
never reads live Gmail or calendar data, creates drafts, sends messages, opens
OAuth, imports Repo B runtime modules, or grants execution authority.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
SCHEMA_VERSION = "cassandra_email_calendar_capability_reconciliation_v0"
JSON_EXPORT_NAME = "cassandra_email_calendar_capability_reconciliation.json"
OPERATOR_EXPORT_NAME = "cassandra_email_calendar_capability_reconciliation_OPERATOR.md"
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
NEXT_RECOMMENDED_LANE = "Cassandra Draft Review Packet v0"

CLASSIFICATIONS = {
    "KEEP_AND_BRIDGE",
    "KEEP_AS_REFERENCE",
    "SUPERSEDED",
    "UNSAFE_OR_BLOCKED",
    "UNKNOWN_NEEDS_REVIEW",
    "NOT_FOUND",
}

NO_AUTHORITY_FLAGS = {
    "read_model_only": True,
    "audit_only": True,
    "live_gmail_read_enabled": False,
    "live_calendar_read_enabled": False,
    "gmail_draft_creation_enabled": False,
    "email_send_enabled": False,
    "calendar_mutation_enabled": False,
    "oauth_or_credentials_accessed": False,
    "browser_automation_added": False,
    "repo_b_executed": False,
    "repo_b_runtime_authority_added": False,
    "mission_control_app_changed": False,
    "runtime_authority_added": False,
    "send_or_submit_authority_added": False,
    "approval_authority_added": False,
    "generic_calendar_cleanup_started": False,
    "raw_private_mail_or_calendar_content_read": False,
}

@dataclass(frozen=True)
class CapabilityFinding:
    capability_id: str
    classification: str
    file_path: str
    capability_area: str
    appears_to_do: str
    authority_risk: str
    steel_thread_fit: str
    safe_reuse_path: str
    evidence: str

    def to_dict(self) -> dict[str, Any]:
        if self.classification not in CLASSIFICATIONS:
            raise ValueError(f"invalid classification: {self.classification}")
        return {
            "capability_id": self.capability_id,
            "classification": self.classification,
            "file_path": self.file_path,
            "capability_area": self.capability_area,
            "appears_to_do": self.appears_to_do,
            "authority_risk": self.authority_risk,
            "steel_thread_fit": self.steel_thread_fit,
            "safe_reuse_path": self.safe_reuse_path,
            "evidence": self.evidence,
        }


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _display_path(path: str | Path) -> str:
    candidate = Path(path)
    try:
        return candidate.resolve().relative_to(ROOT.resolve()).as_posix()
    except (OSError, ValueError):
        return candidate.as_posix()


def _findings() -> tuple[CapabilityFinding, ...]:
    return (
        CapabilityFinding(
            capability_id="cassandra_metadata_email_triage",
            classification="KEEP_AND_BRIDGE",
            file_path="cassandra_email_triage.py",
            capability_area="email_triage_metadata",
            appears_to_do="Classifies operator-confirmed Gmail metadata/snippet candidates and blocks full message bodies and mail mutations.",
            authority_risk="Low when fed governed metadata; unsafe if expanded into ambient inbox surveillance.",
            steel_thread_fit="Fits operator intent -> governed intake -> facts/context/read-models.",
            safe_reuse_path="Reuse classification schema after a bounded operator-supplied or broker-receipted metadata intake packet exists.",
            evidence="Module docstring and EMAIL_TRIAGE_DISALLOWED_LIVE_ACTIONS block full body reads, drafts, sends, label changes, archive/delete, and approval requests.",
        ),
        CapabilityFinding(
            capability_id="cassandra_outreach_draft_era",
            classification="KEEP_AS_REFERENCE",
            file_path="cassandra_outreach.py",
            capability_area="email_draft_and_known_contact_workflow",
            appears_to_do="Older outreach flow can poll Gmail metadata, resolve contacts, and create Gmail drafts through google_access_broker.",
            authority_risk="Draft creation and contact lookup are live external-account actions; not safe to enable in the current lane.",
            steel_thread_fit="Useful as historical behavior evidence, but must be split into draft/review packet and later action-scoped approval receipt before execution.",
            safe_reuse_path="Extract review-packet shape only; leave broker draft creation blocked until a future gated execution lane with specific approval.",
            evidence="Tests patch google_access_broker.call and expect draft creation behavior; current reconciliation does not call that path.",
        ),
        CapabilityFinding(
            capability_id="cassandra_brain_email_calendar_intents",
            classification="KEEP_AS_REFERENCE",
            file_path="cassandra_brain.py",
            capability_area="intent_detection_email_calendar",
            appears_to_do="Detects email, outreach, payment verification, Gmail polling, and calendar-create intent phrases.",
            authority_risk="Intent detection can be useful, but live Gmail/calendar actions would be authority expansion without governed intake and receipts.",
            steel_thread_fit="Intent detection can become operator intent intake; action execution must remain later and gated.",
            safe_reuse_path="Use only to populate bounded intent/review packets; fail closed for calendar mutation and broad inbox reads.",
            evidence="tests/test_gmail_intent_gate.py and tests/test_cassandra_calendar_create_intent.py show older intent recognition and broker-call expectations.",
        ),
        CapabilityFinding(
            capability_id="google_access_broker_email_calendar_surface",
            classification="UNSAFE_OR_BLOCKED",
            file_path="google_access_broker.py",
            capability_area="external_google_account_broker",
            appears_to_do="Central broker for Google capabilities including Gmail metadata/body/draft and calendar/contact classes.",
            authority_risk="External account access, OAuth/credential reliance, and live reads/writes are outside this lane.",
            steel_thread_fit="Can be a future gated executor after receipts exist, not a source of current Mission Control authority.",
            safe_reuse_path="Keep disabled for this bridge; future lanes must bind one draft/action/scope to Guardian approval and a receipt before any broker action.",
            evidence="Guardian reconciliation already warns not to expand Gmail/calendar send/write until approval authority is consolidated.",
        ),
        CapabilityFinding(
            capability_id="cassandra_send_status_dry_run",
            classification="KEEP_AND_BRIDGE",
            file_path="cassandra_send_status_dry_run.py",
            capability_area="no_send_status_and_delivery_blocking",
            appears_to_do="Inspects safe status counts and dry-run posture while blocking outbound delivery paths.",
            authority_risk="Low; it is explicitly dry-run/status-only and returns metadata counts, not private bodies or chat IDs.",
            steel_thread_fit="Fits read-model visibility and no-send proof for future Cassandra communication rails.",
            safe_reuse_path="Use as proof that readiness/status is not delivery authority.",
            evidence="tests/test_cassandra_send_status_dry_run.py asserts no sends, no raw message text, no chat IDs, and delivery blocked.",
        ),
        CapabilityFinding(
            capability_id="cassandra_governed_review_packet_request",
            classification="KEEP_AND_BRIDGE",
            file_path="cassandra_governed_review_packet_request.py",
            capability_area="governed_review_packet_refresh",
            appears_to_do="Turns a bounded operator request into a review-only Capital Hilton packet from governed facts/read-models.",
            authority_risk="Low in current form; it explicitly blocks email, portal, runtime, Repo B, and send authority.",
            steel_thread_fit="Directly matches the desired operator intent -> governed facts -> draft/review packet pattern.",
            safe_reuse_path="Use as the model for Cassandra Draft Review Packet v0.",
            evidence="NO_AUTHORITY_FLAGS include gmail_reply_sent=false, calendar_write_triggered=false, portal_submitted=false, runtime_execution_triggered=false.",
        ),
        CapabilityFinding(
            capability_id="guardian_specific_approval_contracts",
            classification="KEEP_AND_BRIDGE",
            file_path="guardian_hitl_authority_reconciliation.py",
            capability_area="guardian_approval_request_and_receipt_boundary",
            appears_to_do="Maps current and legacy approval surfaces and requires exact action binding, TTL, idempotency, receipts, and no blanket grants.",
            authority_risk="Approval surfaces are powerful if broadened; safe only as a specific scoped receipt boundary.",
            steel_thread_fit="Matches Guardian approval request -> specific approval receipt -> later gated action.",
            safe_reuse_path="Future email/calendar execution must consume a specific Guardian receipt and fail closed on ambiguity.",
            evidence="tests/test_guardian_hitl_authority_reconciliation.py verifies no raw commands, no freeform shell, no send expansion, and authority conflicts visible.",
        ),
        CapabilityFinding(
            capability_id="agent_packet_templates",
            classification="KEEP_AND_BRIDGE",
            file_path="templates/agent/*.json",
            capability_area="packet_templates",
            appears_to_do="Existing templates cover Cassandra triage/outreach and Guardian approval request/decision packet shapes.",
            authority_risk="Low as templates; unsafe only if treated as executable approval or account access.",
            steel_thread_fit="Good substrate for formal draft/review/approval packets.",
            safe_reuse_path="Align Cassandra Draft Review Packet v0 with templates while keeping execution blocked.",
            evidence="Templates exist for cassandra_email_triage_packet_template, cassandra_outreach_draft_packet_template, guardian_approval_request_packet_template, and guardian_approval_decision_packet_template.",
        ),
        CapabilityFinding(
            capability_id="calendar_source_cleanup",
            classification="UNSAFE_OR_BLOCKED",
            file_path="operator_context_only",
            capability_area="calendar_normalization_cleanup",
            appears_to_do="Operator reports Google and Apple Calendar are merged/confusing, but no bounded workflow currently needs cleanup.",
            authority_risk="Generic calendar cleanup would require private calendar inspection and potential mutation.",
            steel_thread_fit="Only safe as future scoped discovery/normalization when a real workflow needs calendar context.",
            safe_reuse_path="Do not start cleanup; define a Calendar Source Normalization Packet only when explicitly requested.",
            evidence="Lane instruction says calendar reconciliation is scoped discovery/normalization only when a real workflow needs calendar context.",
        ),
        CapabilityFinding(
            capability_id="repo_b_runtime_reference",
            classification="KEEP_AS_REFERENCE",
            file_path="/home/openclaw_external/openclaw-runtime",
            capability_area="reference_only_external_runtime",
            appears_to_do="Repo B may contain older runtime capability, but Repo A already has enough current evidence for this reconciliation.",
            authority_risk="Executing or importing Repo B would expand runtime authority and violate the lane.",
            steel_thread_fit="Reference-only evidence at most; not needed for this implementation.",
            safe_reuse_path="Leave uninspected in this lane unless a future explicit audit needs read-only comparison.",
            evidence="Repo B was not executed or imported; Repo A current files/tests/docs were sufficient.",
        ),
        CapabilityFinding(
            capability_id="unknown_email_calendar_capability",
            classification="UNKNOWN_NEEDS_REVIEW",
            file_path="future_or_unmapped_capability",
            capability_area="unknown",
            appears_to_do="Any email/calendar behavior not captured in this reconciliation is not trusted by default.",
            authority_risk="Unknown capabilities may hide live reads, writes, credentials, broad scraping, or stale approval semantics.",
            steel_thread_fit="Fails closed until mapped into governed intake/review/approval/execution phases.",
            safe_reuse_path="Classify before reuse; do not enable by assumption.",
            evidence="Fail-closed policy for unmapped capability.",
        ),
    )


def build_cassandra_email_calendar_capability_reconciliation(*, generated_at: str | None = None) -> dict[str, Any]:
    findings = [finding.to_dict() for finding in _findings()]
    by_classification: dict[str, list[str]] = {classification: [] for classification in sorted(CLASSIFICATIONS)}
    for finding in findings:
        by_classification[finding["classification"]].append(finding["capability_id"])

    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "generated_by": "codex",
        "generated_at": generated_at or utc_now(),
        "lane": "Cassandra Email + Calendar Capability Reconciliation v0",
        "status": "reconciled_review_only_no_live_authority",
        "operator_meaning": "Cassandra has older email/calendar-related capability evidence, but the safe path is governed draft/review packets before any future action-scoped approval or execution.",
        "searched_locations": {
            "repo_a": {
                "path": "/home/openclaw",
                "inspected_first": True,
                "sufficient_for_reconciliation": True,
                "evidence_types": ["source", "tests", "docs", "templates", "generated_read_models"],
            },
            "repo_b": {
                "path": "/home/openclaw_external/openclaw-runtime",
                "inspection_status": "not_inspected_repo_a_sufficient",
                "reference_only_if_future_lane_needs_it": True,
                "executed": False,
                "imported": False,
            },
        },
        "classification_map": findings,
        "classification_summary": by_classification,
        "safe_forward_path": [
            {"phase": "operator_intent", "allowed_now": True, "authority": "intent capture only"},
            {"phase": "governed_intake", "allowed_now": True, "authority": "bounded metadata/context packet only"},
            {"phase": "facts_context_read_models", "allowed_now": True, "authority": "visibility not execution"},
            {"phase": "draft_review_packet", "allowed_now": True, "authority": "review-only draft/context; no Gmail draft creation"},
            {"phase": "guardian_approval_request", "allowed_now": False, "authority": "future specific request only"},
            {"phase": "specific_approval_receipt", "allowed_now": False, "authority": "future action/scope-bound receipt only"},
            {"phase": "gated_send_or_calendar_action", "allowed_now": False, "authority": "future executor only after explicit approved item"},
        ],
        "blocked_until_future_gated_lane": [
            "live_gmail_read",
            "gmail_body_read",
            "gmail_draft_creation",
            "email_send_or_reply",
            "google_calendar_read",
            "apple_calendar_read_or_write",
            "calendar_create_update_delete",
            "oauth_or_credential_access",
            "browser_automation",
            "generic_calendar_cleanup",
            "repo_b_runtime_execution",
            "broad_private_content_scraping",
        ],
        "approval_policy": {
            "guardian_remains_gate": True,
            "approval_scope": "specific_draft_or_calendar_action_only",
            "blanket_approval_allowed": False,
            "cassandra_executor": False,
            "cassandra_role": "draft_or_review_packet_preparer_only",
            "fail_closed_when_identity_scope_or_authority_unclear": True,
        },
        "calendar_policy": {
            "generic_cleanup_started": False,
            "normalization_allowed_only_when_workflow_needs_context": True,
            "mac_calendar_confusion_recorded_as_context_not_task": True,
            "live_calendar_access_enabled": False,
        },
        "receipt_proof_status": {
            "reconciliation_read_model_created": True,
            "repo_b_reference_only": True,
            "repo_b_executed": False,
            "live_gmail_calendar_authority_enabled": False,
            "draft_review_approval_execution_distinguished": True,
            "unknown_capability_fails_closed": True,
            "calendar_cleanup_not_started": True,
            "approval_specific_action_scoped": True,
            "send_calendar_mutation_blocked": True,
        },
        "next_recommended_lane": NEXT_RECOMMENDED_LANE,
        **NO_AUTHORITY_FLAGS,
    }
    return payload


def format_cassandra_email_calendar_capability_reconciliation(payload: dict[str, Any]) -> str:
    summary = payload["classification_summary"]
    lines = [
        "# Cassandra Email + Calendar Capability Reconciliation v0",
        "",
        "Status:",
        f"- Reconciliation status: `{payload['status']}`.",
        "- Live Gmail/calendar/send/calendar mutation authority enabled: `false`.",
        "- Repo B executed/imported: `false`.",
        "- Generic calendar cleanup started: `false`.",
        "",
        "## Operator Meaning",
        f"- {payload['operator_meaning']}",
        "- Cassandra may prepare review-only packets later; Guardian remains the specific approval gate.",
        "",
        "## Existing Capability Classification",
    ]
    for classification in ("KEEP_AND_BRIDGE", "KEEP_AS_REFERENCE", "UNSAFE_OR_BLOCKED", "UNKNOWN_NEEDS_REVIEW", "SUPERSEDED", "NOT_FOUND"):
        values = summary.get(classification) or []
        lines.append(f"- {classification}: {', '.join(values) if values else 'none'}")
    lines.extend([
        "",
        "## Safe Forward Path",
    ])
    for phase in payload["safe_forward_path"]:
        allowed = str(phase["allowed_now"]).lower()
        lines.append(f"- {phase['phase']}: allowed_now=`{allowed}`; {phase['authority']}.")
    lines.extend([
        "",
        "## Blocked Now",
    ])
    for item in payload["blocked_until_future_gated_lane"]:
        lines.append(f"- `{item}`")
    lines.extend([
        "",
        "## Calendar Posture",
        "- Calendar cleanup is not started generically.",
        "- Calendar normalization should only happen in a future scoped workflow that needs calendar context.",
        "",
        "## Next Safe Lane",
        f"- `{payload['next_recommended_lane']}`",
    ])
    return "\n".join(lines) + "\n"


@dataclass(frozen=True)
class ExportResult:
    schema_version: str
    json_path: str
    operator_path: str
    status: str
    next_recommended_lane: str
    runtime_authority_added: bool
    send_or_submit_authority_added: bool
    approval_authority_added: bool


def export_cassandra_email_calendar_capability_reconciliation(*, repo_root: str | Path = ROOT, export_root: str | Path = DEFAULT_EXPORT_ROOT, generated_at: str | None = None) -> ExportResult:
    root = Path(repo_root)
    out_dir = root / export_root
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = build_cassandra_email_calendar_capability_reconciliation(generated_at=generated_at)
    json_path = out_dir / JSON_EXPORT_NAME
    operator_path = out_dir / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(format_cassandra_email_calendar_capability_reconciliation(payload), encoding="utf-8")
    return ExportResult(
        schema_version=SCHEMA_VERSION,
        json_path=_display_path(json_path),
        operator_path=_display_path(operator_path),
        status=payload["status"],
        next_recommended_lane=payload["next_recommended_lane"],
        runtime_authority_added=payload["runtime_authority_added"],
        send_or_submit_authority_added=payload["send_or_submit_authority_added"],
        approval_authority_added=payload["approval_authority_added"],
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export Cassandra email/calendar capability reconciliation read-model.")
    parser.add_argument("--repo-root", default=str(ROOT), help="Repository root to write generated read-models.")
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT), help="Read-model export directory.")
    parser.add_argument("--format", choices=("json", "operator"), default="operator", help="Print result format.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(list(sys.argv[1:] if argv is None else argv))
    result = export_cassandra_email_calendar_capability_reconciliation(repo_root=args.repo_root, export_root=args.export_root)
    if args.format == "json":
        print(stable_json(result.__dict__), end="")
    else:
        print(
            "Cassandra email/calendar capability reconciliation exported: "
            f"{result.json_path} and {result.operator_path} "
            f"(status={result.status}; next={result.next_recommended_lane})."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
