"""Cassandra email/calendar delta detangle v0.

This read-model separates Cassandra email/calendar capability into governed
review paths, separate Telegram/operator notification posture, blocked live
email/calendar paths, future calendar normalization, and protected-access
requirements. It is classification/readiness metadata only: it does not access
Gmail, calendars, OAuth, credentials, browsers, Telegram, create Gmail drafts,
send messages, mutate calendar events, activate tools/agents, inspect Repo B,
or grant runtime authority.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
DEFAULT_EXPORT_ROOT = Path("generated/read_models")

SCHEMA_VERSION = "cassandra_email_calendar_delta_detangle_v0"
JSON_EXPORT_NAME = "cassandra_email_calendar_delta_detangle.json"
OPERATOR_EXPORT_NAME = "cassandra_email_calendar_delta_detangle_OPERATOR.md"
NEXT_RECOMMENDED_LANE = "Cassandra Draft Identity Reference Rail v0"

CLASSIFICATIONS = (
    "GOVERNED_REVIEW_PACKET_READY",
    "DRAFT_PREVIEW_ONLY",
    "TELEGRAM_NOTIFICATION_SEPARATE",
    "LIVE_GMAIL_BLOCKED",
    "EMAIL_SEND_BLOCKED",
    "CALENDAR_DISCOVERY_BLOCKED",
    "CALENDAR_NORMALIZATION_FUTURE",
    "OAUTH_CREDENTIAL_BLOCKED",
    "PROTECTED_ACCESS_REQUIRED",
    "SECURITY_THRESHOLD_REQUIRED",
    "LEGACY_REFERENCE_ONLY",
    "UNKNOWN_FAIL_CLOSED",
)

NO_AUTHORITY_FLAGS = {
    "classification_only": True,
    "read_model_only": True,
    "live_gmail_access_enabled": False,
    "live_google_calendar_access_enabled": False,
    "live_apple_calendar_access_enabled": False,
    "oauth_or_credentials_accessed": False,
    "gmail_draft_created": False,
    "email_send_triggered": False,
    "gmail_or_email_send_triggered": False,
    "telegram_send_triggered": False,
    "telegram_notification_behavior_changed": False,
    "calendar_access_triggered": False,
    "calendar_mutation_triggered": False,
    "calendar_cleanup_started": False,
    "calendar_normalization_started": False,
    "browser_automation_added": False,
    "tools_enabled": False,
    "agents_activated": False,
    "repo_b_filesystem_inspected": False,
    "repo_b_code_executed": False,
    "repo_b_modules_imported": False,
    "raw_private_inbox_or_calendar_content_read": False,
    "mission_control_app_changed": False,
    "security_pass_started": False,
    "approval_authority_added": False,
    "runtime_authority_added": False,
    "send_or_submit_authority_added": False,
}


@dataclass(frozen=True)
class SourceReadModel:
    key: str
    path: str
    role: str


@dataclass(frozen=True)
class SurfaceSpec:
    surface_id: str
    display_name: str
    primary_classification: str
    classifications: tuple[str, ...]
    current_posture: str
    governed_now: bool
    review_only: bool
    mission_control_visibility: bool
    telegram_notification_separate: bool
    protected_access_gate_applies: bool
    security_threshold_required: bool
    live_behavior_changed_now: bool
    source_evidence: tuple[str, ...]
    blocked_authorities: tuple[str, ...]
    next_safe_move: str
    operator_note: str


@dataclass(frozen=True)
class CassandraEmailCalendarDeltaDetangleExportResult:
    schema_version: str
    json_path: str
    operator_path: str
    surface_count: int
    runtime_authority_added: bool
    send_or_submit_authority_added: bool


SOURCE_READ_MODELS = (
    SourceReadModel("cassandra_email_calendar_capability_reconciliation", "generated/read_models/cassandra_email_calendar_capability_reconciliation.json", "current email/calendar capability reconciliation"),
    SourceReadModel("cassandra_draft_review_packet", "generated/read_models/cassandra_draft_review_packet.json", "review-only Cassandra draft packet"),
    SourceReadModel("cassandra_send_status_dry_run", "generated/read_models/cassandra_send_status_dry_run.json", "Cassandra no-send status/dry-run posture"),
    SourceReadModel("cassandra_governed_review_packet_request_proof", "generated/read_models/cassandra_governed_review_packet_request_proof.json", "governed request-to-review packet proof"),
    SourceReadModel("guardian_draft_approval_request_contract", "generated/read_models/guardian_draft_approval_request_contract.json", "Guardian final-send approval request contract"),
    SourceReadModel("protected_access_broker_concept", "generated/read_models/protected_access_broker_concept.json", "protected access concept"),
    SourceReadModel("protected_evidence_reference_receipt", "generated/read_models/protected_evidence_reference_receipt.json", "protected evidence reference receipt"),
    SourceReadModel("guardian_protected_access_gate_spec", "generated/read_models/guardian_protected_access_gate_spec.json", "Guardian protected-access gate"),
    SourceReadModel("capability_skill_registry_metadata_delta", "generated/read_models/capability_skill_registry_metadata_delta.json", "capability registry metadata delta"),
    SourceReadModel("repo_b_remaining_capability_delta_map", "generated/read_models/repo_b_remaining_capability_delta_map.json", "Repo B delta read-model reference from Repo A only"),
    SourceReadModel("tool_inventory", "generated/read_models/tool_inventory.json", "tool inventory metadata"),
    SourceReadModel("tool_intake", "generated/read_models/tool_intake.json", "tool intake metadata"),
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _rooted(path: str | Path, *, repo_root: str | Path = ROOT) -> Path:
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    return Path(repo_root) / candidate


def _display_path(path: str | Path) -> str:
    candidate = Path(path)
    try:
        return candidate.resolve().relative_to(ROOT.resolve()).as_posix()
    except (OSError, ValueError):
        return candidate.as_posix()


def _read_json_if_present(path: str | Path, *, repo_root: str | Path = ROOT) -> dict[str, Any]:
    target = _rooted(path, repo_root=repo_root)
    if not target.exists():
        return {}
    payload = json.loads(target.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _source_record(source: SourceReadModel, *, repo_root: str | Path, payload: dict[str, Any]) -> dict[str, Any]:
    target = _rooted(source.path, repo_root=repo_root)
    repo_b_delta = source.key == "repo_b_remaining_capability_delta_map"
    return {
        "key": source.key,
        "path": source.path,
        "present": target.exists(),
        "schema_version": payload.get("schema_version") or payload.get("read_model_version"),
        "role": source.role,
        "truth_status": "repo_a_read_model_evidence_not_truth",
        "repo_a_only": True,
        "repo_b_delta_read_model_used": repo_b_delta and bool(payload),
        "repo_b_filesystem_inspected": False,
        "repo_b_code_executed": False,
        "external_account_accessed": False,
        "raw_private_content_read": False,
        "executed_or_dispatched": False,
    }


def _surface_specs() -> tuple[SurfaceSpec, ...]:
    return (
        SurfaceSpec(
            surface_id="governed_cassandra_review_packet_path",
            display_name="Current governed Cassandra review packet path",
            primary_classification="GOVERNED_REVIEW_PACKET_READY",
            classifications=("GOVERNED_REVIEW_PACKET_READY", "DRAFT_PREVIEW_ONLY"),
            current_posture="available_as_review_packet_read_model_only",
            governed_now=True,
            review_only=True,
            mission_control_visibility=True,
            telegram_notification_separate=False,
            protected_access_gate_applies=False,
            security_threshold_required=False,
            live_behavior_changed_now=False,
            source_evidence=(
                "cassandra_draft_review_packet.json",
                "cassandra_governed_review_packet_request_proof.json",
                "guardian_draft_approval_request_contract.json",
            ),
            blocked_authorities=("Gmail draft creation", "email send", "calendar mutation", "runtime execution"),
            next_safe_move="Use generated review/draft packets only; keep execution and live account work separate.",
            operator_note="Cassandra can represent a draft/review packet from governed facts without touching Gmail or calendars.",
        ),
        SurfaceSpec(
            surface_id="cassandra_draft_preview_packet",
            display_name="Cassandra draft preview packet",
            primary_classification="DRAFT_PREVIEW_ONLY",
            classifications=("DRAFT_PREVIEW_ONLY", "GOVERNED_REVIEW_PACKET_READY"),
            current_posture="review_preview_visible_no_gmail_draft",
            governed_now=True,
            review_only=True,
            mission_control_visibility=True,
            telegram_notification_separate=False,
            protected_access_gate_applies=False,
            security_threshold_required=False,
            live_behavior_changed_now=False,
            source_evidence=("cassandra_draft_review_packet.json", "guardian_draft_approval_request_contract.json"),
            blocked_authorities=("Gmail draft creation", "attachment generation", "email send", "approval receipt creation"),
            next_safe_move="Create stable draft/attachment identity metadata later; do not create a Gmail draft.",
            operator_note="A draft preview is a packet/read-model, not a live Gmail draft.",
        ),
        SurfaceSpec(
            surface_id="telegram_operator_notification_path",
            display_name="Telegram/operator notification path",
            primary_classification="TELEGRAM_NOTIFICATION_SEPARATE",
            classifications=("TELEGRAM_NOTIFICATION_SEPARATE",),
            current_posture="separate_runtime_surface_unchanged_by_this_lane",
            governed_now=False,
            review_only=True,
            mission_control_visibility=False,
            telegram_notification_separate=True,
            protected_access_gate_applies=False,
            security_threshold_required=True,
            live_behavior_changed_now=False,
            source_evidence=("cassandra_send_status_dry_run.json", "capability_skill_registry_metadata_delta.json"),
            blocked_authorities=("Telegram send", "Guardian live notification", "operator ping behavior change"),
            next_safe_move="Leave Telegram notification behavior unchanged; use Mission Control/read-model visibility for this lane.",
            operator_note="Telegram draft preview/notification behavior is separate from Mission Control read-model visibility.",
        ),
        SurfaceSpec(
            surface_id="gmail_live_account_access",
            display_name="Live Gmail account access",
            primary_classification="LIVE_GMAIL_BLOCKED",
            classifications=("LIVE_GMAIL_BLOCKED", "OAUTH_CREDENTIAL_BLOCKED", "PROTECTED_ACCESS_REQUIRED", "SECURITY_THRESHOLD_REQUIRED"),
            current_posture="blocked_no_live_account_access",
            governed_now=False,
            review_only=False,
            mission_control_visibility=False,
            telegram_notification_separate=False,
            protected_access_gate_applies=True,
            security_threshold_required=True,
            live_behavior_changed_now=False,
            source_evidence=(
                "cassandra_email_calendar_capability_reconciliation.json",
                "protected_access_broker_concept.json",
                "guardian_protected_access_gate_spec.json",
            ),
            blocked_authorities=("Gmail read", "mailbox body inspection", "OAuth", "credentials", "tool bridge access"),
            next_safe_move="Keep Gmail as protected-access-gated future work tied to a specific workflow.",
            operator_note="Gmail metadata/body access is blocked; review packets must use governed facts/read-models only.",
        ),
        SurfaceSpec(
            surface_id="email_send_and_gmail_draft_creation",
            display_name="Email send and Gmail draft creation",
            primary_classification="EMAIL_SEND_BLOCKED",
            classifications=("EMAIL_SEND_BLOCKED", "LIVE_GMAIL_BLOCKED", "PROTECTED_ACCESS_REQUIRED", "SECURITY_THRESHOLD_REQUIRED"),
            current_posture="blocked_no_draft_no_send",
            governed_now=False,
            review_only=False,
            mission_control_visibility=False,
            telegram_notification_separate=False,
            protected_access_gate_applies=True,
            security_threshold_required=True,
            live_behavior_changed_now=False,
            source_evidence=("guardian_draft_approval_request_contract.json", "cassandra_draft_review_packet.json"),
            blocked_authorities=("Gmail draft creation", "email send", "email reply", "attachment send", "approval execution"),
            next_safe_move="Model stable draft identity and proof prerequisites before any future send-approval receipt lane.",
            operator_note="A final-send approval request contract exists, but no draft creation, receipt, or send authority exists.",
        ),
        SurfaceSpec(
            surface_id="calendar_discovery_understanding",
            display_name="Calendar discovery/understanding",
            primary_classification="CALENDAR_DISCOVERY_BLOCKED",
            classifications=("CALENDAR_DISCOVERY_BLOCKED", "CALENDAR_NORMALIZATION_FUTURE", "OAUTH_CREDENTIAL_BLOCKED", "PROTECTED_ACCESS_REQUIRED", "SECURITY_THRESHOLD_REQUIRED"),
            current_posture="blocked_context_recorded_no_live_calendar_read",
            governed_now=False,
            review_only=True,
            mission_control_visibility=False,
            telegram_notification_separate=False,
            protected_access_gate_applies=True,
            security_threshold_required=True,
            live_behavior_changed_now=False,
            source_evidence=("cassandra_email_calendar_capability_reconciliation.json", "protected_access_broker_concept.json"),
            blocked_authorities=("Google Calendar read", "Apple Calendar read", "OAuth", "calendar event scraping", "calendar mutation"),
            next_safe_move="Only create a scoped calendar source-normalization packet when a named workflow needs calendar evidence.",
            operator_note="The merged Google/Apple calendar situation is context, not a cleanup task in this lane.",
        ),
        SurfaceSpec(
            surface_id="calendar_normalization_future",
            display_name="Calendar source normalization",
            primary_classification="CALENDAR_NORMALIZATION_FUTURE",
            classifications=("CALENDAR_NORMALIZATION_FUTURE", "CALENDAR_DISCOVERY_BLOCKED", "PROTECTED_ACCESS_REQUIRED", "SECURITY_THRESHOLD_REQUIRED"),
            current_posture="future_scoped_evidence_normalization_only",
            governed_now=False,
            review_only=True,
            mission_control_visibility=False,
            telegram_notification_separate=False,
            protected_access_gate_applies=True,
            security_threshold_required=True,
            live_behavior_changed_now=False,
            source_evidence=("cassandra_email_calendar_capability_reconciliation.json",),
            blocked_authorities=("generic calendar cleanup", "calendar mutation", "broad private calendar inspection"),
            next_safe_move="Wait for a real workflow needing calendar context; then build a metadata-only normalization packet first.",
            operator_note="Calendar cleanup is not happening yet.",
        ),
        SurfaceSpec(
            surface_id="oauth_credential_tool_browser_bridges",
            display_name="OAuth/credential/tool/browser bridges",
            primary_classification="OAUTH_CREDENTIAL_BLOCKED",
            classifications=("OAUTH_CREDENTIAL_BLOCKED", "PROTECTED_ACCESS_REQUIRED", "SECURITY_THRESHOLD_REQUIRED", "LEGACY_REFERENCE_ONLY"),
            current_posture="blocked_reference_or_metadata_only",
            governed_now=False,
            review_only=False,
            mission_control_visibility=False,
            telegram_notification_separate=False,
            protected_access_gate_applies=True,
            security_threshold_required=True,
            live_behavior_changed_now=False,
            source_evidence=(
                "protected_access_broker_concept.json",
                "guardian_protected_access_gate_spec.json",
                "tool_inventory.json",
                "tool_intake.json",
            ),
            blocked_authorities=("OAuth flow", "credential access", "browser automation", "tool bridge execution", "account access"),
            next_safe_move="Keep as protected-access metadata until future security-threshold work.",
            operator_note="Tool/OAuth/browser bridges are unsafe to activate from capability metadata.",
        ),
        SurfaceSpec(
            surface_id="legacy_repo_b_email_calendar_delta",
            display_name="Repo B-derived email/calendar delta",
            primary_classification="LEGACY_REFERENCE_ONLY",
            classifications=("LEGACY_REFERENCE_ONLY", "OAUTH_CREDENTIAL_BLOCKED", "EMAIL_SEND_BLOCKED"),
            current_posture="existing_delta_read_model_reference_only",
            governed_now=False,
            review_only=True,
            mission_control_visibility=False,
            telegram_notification_separate=False,
            protected_access_gate_applies=False,
            security_threshold_required=True,
            live_behavior_changed_now=False,
            source_evidence=("repo_b_remaining_capability_delta_map.json", "capability_skill_registry_metadata_delta.json"),
            blocked_authorities=("Repo B execution", "legacy live loops", "legacy send/OAuth bridge reuse"),
            next_safe_move="Use the existing Repo B delta read-model only; do not inspect or run Repo B here.",
            operator_note="Repo B email/calendar material is reference metadata until a specific promotion lane exists.",
        ),
        SurfaceSpec(
            surface_id="unknown_email_calendar_surface",
            display_name="Unknown email/calendar surface",
            primary_classification="UNKNOWN_FAIL_CLOSED",
            classifications=("UNKNOWN_FAIL_CLOSED",),
            current_posture="blocked_until_classified",
            governed_now=False,
            review_only=False,
            mission_control_visibility=False,
            telegram_notification_separate=False,
            protected_access_gate_applies=True,
            security_threshold_required=True,
            live_behavior_changed_now=False,
            source_evidence=(),
            blocked_authorities=("all live account access", "send", "draft", "calendar mutation", "OAuth", "credentials", "runtime execution"),
            next_safe_move="Create a narrow classification lane before any routing or use.",
            operator_note="Unknown email/calendar capability fails closed.",
        ),
    )


def _surface_record(spec: SurfaceSpec) -> dict[str, Any]:
    invalid = [item for item in (spec.primary_classification, *spec.classifications) if item not in CLASSIFICATIONS]
    if invalid:
        raise ValueError(f"unknown Cassandra email/calendar classification(s): {invalid}")
    return {
        "surface_id": spec.surface_id,
        "display_name": spec.display_name,
        "primary_classification": spec.primary_classification,
        "classifications": list(spec.classifications),
        "current_posture": spec.current_posture,
        "governed_now": spec.governed_now,
        "review_only": spec.review_only,
        "mission_control_visibility": spec.mission_control_visibility,
        "telegram_notification_separate": spec.telegram_notification_separate,
        "protected_access_gate_applies": spec.protected_access_gate_applies,
        "security_threshold_required": spec.security_threshold_required,
        "live_behavior_changed_now": spec.live_behavior_changed_now,
        "source_evidence": list(spec.source_evidence),
        "blocked_authorities": list(spec.blocked_authorities),
        "unknown_fails_closed": spec.primary_classification == "UNKNOWN_FAIL_CLOSED",
        "next_safe_move": spec.next_safe_move,
        "operator_note": spec.operator_note,
    }


def _classification_counts(surfaces: list[dict[str, Any]]) -> dict[str, int]:
    counts = Counter(surface["primary_classification"] for surface in surfaces)
    return {classification: counts.get(classification, 0) for classification in CLASSIFICATIONS}


def _classification_label_counts(surfaces: list[dict[str, Any]]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for surface in surfaces:
        counts.update(surface["classifications"])
    return {classification: counts.get(classification, 0) for classification in CLASSIFICATIONS}


def _eli5_summary() -> dict[str, Any]:
    return {
        "what_cassandra_can_safely_represent_now": (
            "Cassandra can safely represent review-only packets and draft previews from governed read-model facts."
        ),
        "what_email_calendar_parts_are_blocked": (
            "Gmail access, Gmail draft creation, email send/reply, Google/Apple Calendar access, calendar mutation, OAuth, credentials, and browser/tool bridges are blocked."
        ),
        "telegram_vs_mission_control": (
            "Telegram draft preview behavior is separate from Mission Control visibility; this lane changes neither."
        ),
        "calendar_cleanup_not_happening_yet": (
            "Calendar cleanup is not happening yet. The merged Google/Apple calendar situation is recorded only as future context."
        ),
        "what_must_happen_before_real_email_calendar_work": (
            "A named workflow, protected-access gate, Guardian/security-threshold controls, specific draft/attachment identity, and later approval receipt would be required first."
        ),
        "next_1_to_3_sensible_lanes": [
            "Cassandra Draft Identity Reference Rail v0",
            "Calendar Source Normalization Packet v0",
            "Cassandra Email Send Approval Receipt Boundary v0",
        ],
    }


def build_cassandra_email_calendar_delta_detangle(
    *,
    repo_root: str | Path = ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    sources = {
        source.key: _read_json_if_present(source.path, repo_root=repo_root)
        for source in SOURCE_READ_MODELS
    }
    source_records = [
        _source_record(source, repo_root=repo_root, payload=sources[source.key])
        for source in SOURCE_READ_MODELS
    ]
    surfaces = [_surface_record(spec) for spec in _surface_specs()]
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_by": "codex",
        "generated_at": generated_at or utc_now(),
        "lane": "Cassandra Email Calendar Delta Detangle v0",
        "detangle_status": "classification_only_no_live_authority",
        "purpose": "Separate governed Cassandra review/draft capability from live email, calendar, OAuth, Telegram notification, and protected-access future work.",
        "classification_labels": list(CLASSIFICATIONS),
        "detangled_surfaces": surfaces,
        "classification_counts": _classification_counts(surfaces),
        "classification_label_counts": _classification_label_counts(surfaces),
        "current_governed_capabilities": {
            "governed_review_packet_path_ready": True,
            "draft_preview_read_model_ready": True,
            "mission_control_visibility_supported_by_read_model": True,
            "guardian_final_send_request_contract_modeled": True,
            "approval_receipt_present": False,
            "execution_enabled": False,
        },
        "mission_control_vs_telegram_boundary": {
            "mission_control_visibility_is_read_model_mirror": True,
            "telegram_operator_notification_is_separate_path": True,
            "telegram_behavior_changed_by_this_lane": False,
            "telegram_send_triggered": False,
            "draft_preview_packet_can_be_visible_without_telegram_notification": True,
        },
        "calendar_operator_context": {
            "google_apple_calendar_merged_context_recorded": True,
            "iphone_calendar_still_seems_to_work_context_recorded": True,
            "mac_calendar_confusing_context_recorded": True,
            "google_calendar_may_be_messy_context_recorded": True,
            "generic_calendar_cleanup_started": False,
            "calendar_normalization_allowed_now": False,
            "future_scoped_normalization_requires_named_workflow": True,
            "live_calendar_access_enabled": False,
        },
        "protected_access_requirements": {
            "protected_access_gate_required_for_live_gmail_calendar": True,
            "guardian_protected_access_gate_required": True,
            "security_threshold_required": True,
            "credential_or_oauth_access_allowed_now": False,
            "protected_reference_receipts_are_not_access_authority": True,
            "unknown_surfaces_fail_closed": True,
        },
        "repo_b_delta_handling": {
            "used_existing_repo_a_delta_read_model_only": bool(sources.get("repo_b_remaining_capability_delta_map")),
            "repo_b_filesystem_inspected": False,
            "repo_b_code_executed": False,
            "repo_b_modules_imported": False,
            "legacy_email_calendar_surfaces_reference_only": True,
        },
        "source_read_models": source_records,
        "operator_eli5_summary": _eli5_summary(),
        "no_authority_flags": dict(NO_AUTHORITY_FLAGS),
        **NO_AUTHORITY_FLAGS,
        "next_recommended_lane": NEXT_RECOMMENDED_LANE,
    }


def format_cassandra_email_calendar_delta_detangle(payload: dict[str, Any]) -> str:
    eli5 = payload["operator_eli5_summary"]
    lines = [
        "# Cassandra Email Calendar Delta Detangle v0",
        "",
        "Status:",
        "- Detangle posture: classification/read-model only.",
        "- Live Gmail/calendar/OAuth/send/draft authority: `false`.",
        "- Telegram notification behavior changed: `false`.",
        "- Calendar cleanup/normalization started: `false`.",
        "- Repo B inspected/executed: `false`.",
        "",
        "## ELI5 Summary",
        f"- {eli5['what_cassandra_can_safely_represent_now']}",
        f"- {eli5['what_email_calendar_parts_are_blocked']}",
        f"- {eli5['telegram_vs_mission_control']}",
        f"- {eli5['calendar_cleanup_not_happening_yet']}",
        f"- {eli5['what_must_happen_before_real_email_calendar_work']}",
        "",
        "## Surfaces",
    ]
    for surface in payload["detangled_surfaces"]:
        lines.append(
            f"- `{surface['surface_id']}`: `{surface['primary_classification']}`; "
            f"posture `{surface['current_posture']}`."
        )
    lines.extend(["", "## Classification Counts"])
    for classification in CLASSIFICATIONS:
        lines.append(f"- `{classification}`: {payload['classification_counts'].get(classification, 0)} primary / {payload['classification_label_counts'].get(classification, 0)} labels")
    lines.extend(["", "## Boundaries"])
    lines.extend(
        [
            "- Mission Control visibility is read-model/mirror visibility, not a backend command path.",
            "- Telegram/operator notification remains a separate unchanged runtime path.",
            "- Unknown email/calendar capability fails closed.",
            "- No Gmail, calendar, OAuth, credentials, Telegram send, Gmail draft, email send, browser, tools, agents, or runtime authority was enabled.",
            "",
            f"Next safe lane: {payload['next_recommended_lane']}",
            "",
        ]
    )
    return "\n".join(lines)


def export_cassandra_email_calendar_delta_detangle(
    *,
    repo_root: str | Path = ROOT,
    export_root: str | Path = DEFAULT_EXPORT_ROOT,
    generated_at: str | None = None,
) -> CassandraEmailCalendarDeltaDetangleExportResult:
    root = Path(repo_root)
    out_dir = _rooted(export_root, repo_root=root)
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = build_cassandra_email_calendar_delta_detangle(repo_root=root, generated_at=generated_at)
    json_path = out_dir / JSON_EXPORT_NAME
    operator_path = out_dir / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(format_cassandra_email_calendar_delta_detangle(payload), encoding="utf-8")
    return CassandraEmailCalendarDeltaDetangleExportResult(
        schema_version=SCHEMA_VERSION,
        json_path=_display_path(json_path),
        operator_path=_display_path(operator_path),
        surface_count=len(payload["detangled_surfaces"]),
        runtime_authority_added=payload["runtime_authority_added"],
        send_or_submit_authority_added=payload["send_or_submit_authority_added"],
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export Cassandra email/calendar delta detangle read-model.")
    parser.add_argument("--repo-root", default=str(ROOT), help="Repo A root.")
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT), help="Generated read-model export root.")
    parser.add_argument("--format", choices=("json", "operator", "summary"), default="summary")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    result = export_cassandra_email_calendar_delta_detangle(repo_root=args.repo_root, export_root=args.export_root)
    root = _rooted(args.export_root, repo_root=args.repo_root)
    if args.format == "json":
        print((root / JSON_EXPORT_NAME).read_text(encoding="utf-8"), end="")
    elif args.format == "operator":
        print((root / OPERATOR_EXPORT_NAME).read_text(encoding="utf-8"), end="")
    else:
        print(stable_json(result.__dict__), end="")
    return 0 if result.schema_version == SCHEMA_VERSION else 1


__all__ = [
    "CLASSIFICATIONS",
    "JSON_EXPORT_NAME",
    "NO_AUTHORITY_FLAGS",
    "OPERATOR_EXPORT_NAME",
    "SCHEMA_VERSION",
    "build_cassandra_email_calendar_delta_detangle",
    "export_cassandra_email_calendar_delta_detangle",
    "format_cassandra_email_calendar_delta_detangle",
    "stable_json",
]


if __name__ == "__main__":
    raise SystemExit(main())
