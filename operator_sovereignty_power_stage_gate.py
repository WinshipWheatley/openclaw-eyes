"""Operator sovereignty power-stage gate v0.

This module defines staged controls OpenClaw must satisfy before crossing into
higher-power capabilities. It is contract/read-model substrate only: it does
not add runtime, send, submit, browser, credential, PII, client deployment, or
surveillance authority.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "operator_sovereignty_power_stage_gate_v0"
READ_MODEL_VERSION = "operator_sovereignty_power_stage_gate_read_model_v0"
JSON_EXPORT_NAME = "operator_sovereignty_power_stage_gate.json"
OPERATOR_EXPORT_NAME = "operator_sovereignty_power_stage_gate_OPERATOR.md"
DEFAULT_EXPORT_ROOT = Path("generated/read_models")

CURRENT_POWER_STAGE_ID = "stage_1_visibility_read_model_review_packet"

NO_AUTHORITY_FLAGS = {
    "surveillance_capability_added": False,
    "runtime_authority_added": False,
    "send_or_submit_authority_added": False,
    "browser_automation_added": False,
    "credential_or_pii_access_added": False,
    "customer_deployment_authority_added": False,
    "kill_script_added": False,
    "service_started_or_stopped": False,
    "repo_b_executed": False,
    "mission_control_app_changed": False,
    "broad_private_scan_performed": False,
    "autonomous_self_repair_added": False,
}

REQUIRED_STAGE_FIELDS = (
    "stage_id",
    "stage_name",
    "allowed_capabilities",
    "forbidden_capabilities",
    "required_controls",
    "required_receipts_read_models",
    "alert_thresholds",
    "stop_conditions",
    "recovery_requirements",
    "current_status",
    "can_cross_into_stage",
    "missing_controls",
)

ALERT_LEVELS = ("low", "medium", "high", "red")

CURRENT_CONTROL_EVIDENCE = {
    "provenance_backed_read_models",
    "no_raw_secret_pii_in_normal_read_models",
    "authority_flags_on_review_packets",
    "sync_mirror_trust_surface",
    "wrong_environment_guidance",
    "review_only_labels",
    "approval_scope_clarity_modeled",
    "anti_ambiguity_authority_boundary_modeled",
    "approval_packet_integrity_modeled",
    "no_implicit_authority_escalation_modeled",
    "staged_alert_model_defined",
    "authority_surface_watchdog_scope_defined",
    "watchdog_sentinel_contract_required_before_crossing",
    "staged_alerting",
}


@dataclass(frozen=True)
class PowerStageGateExportResult:
    schema_version: str
    json_path: str
    operator_path: str
    current_power_stage_classified: bool
    current_power_stage_id: str
    surveillance_capability_added: bool
    runtime_authority_added: bool
    send_or_submit_authority_added: bool


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _stage(
    *,
    stage_id: str,
    stage_name: str,
    allowed_capabilities: tuple[str, ...],
    forbidden_capabilities: tuple[str, ...],
    required_controls: tuple[str, ...],
    required_receipts_read_models: tuple[str, ...],
    alert_thresholds: dict[str, tuple[str, ...]],
    stop_conditions: tuple[str, ...],
    recovery_requirements: tuple[str, ...],
    current_status: str,
    can_cross_into_stage: bool,
    available_controls: set[str],
) -> dict[str, Any]:
    missing_controls = tuple(control for control in required_controls if control not in available_controls)
    if can_cross_into_stage and missing_controls:
        raise ValueError(f"{stage_id} cannot be crossable with missing controls: {missing_controls}")
    payload = {
        "stage_id": stage_id,
        "stage_name": stage_name,
        "allowed_capabilities": list(allowed_capabilities),
        "forbidden_capabilities": list(forbidden_capabilities),
        "required_controls": list(required_controls),
        "required_receipts_read_models": list(required_receipts_read_models),
        "alert_thresholds": {
            level: list(alert_thresholds.get(level, ()))
            for level in ALERT_LEVELS
        },
        "stop_conditions": list(stop_conditions),
        "recovery_requirements": list(recovery_requirements),
        "current_status": current_status,
        "can_cross_into_stage": bool(can_cross_into_stage),
        "missing_controls": list(missing_controls),
    }
    _validate_stage(payload)
    return payload


def _validate_stage(payload: dict[str, Any]) -> None:
    missing = [field for field in REQUIRED_STAGE_FIELDS if field not in payload]
    if missing:
        raise ValueError(f"power stage missing fields: {', '.join(missing)}")
    if payload["stage_id"] != CURRENT_POWER_STAGE_ID and payload["can_cross_into_stage"]:
        raise ValueError(f"only current Stage 1 may be crossable now: {payload['stage_id']}")


def build_power_stages(available_controls: set[str] | None = None) -> tuple[dict[str, Any], ...]:
    controls = set(available_controls or CURRENT_CONTROL_EVIDENCE)
    return (
        _stage(
            stage_id="stage_1_visibility_read_model_review_packet",
            stage_name="Visibility / Read-Model / Review Packet",
            allowed_capabilities=(
                "classify and model facts from governed evidence",
                "generate read-models",
                "show Mission Control surfaces",
                "generate review-only packets",
            ),
            forbidden_capabilities=(
                "send or submit externally",
                "browser automation",
                "credential or PII access",
                "runtime execution authority",
                "hidden raw capture",
                "operator behavior surveillance",
            ),
            required_controls=(
                "provenance_backed_read_models",
                "no_raw_secret_pii_in_normal_read_models",
                "authority_flags_on_review_packets",
                "sync_mirror_trust_surface",
                "wrong_environment_guidance",
                "review_only_labels",
            ),
            required_receipts_read_models=(
                "generated review/read-model artifacts",
                "sync_health or mirror trust read-model",
                "estate node registry",
                "workflow proof packets",
            ),
            alert_thresholds={
                "low": (
                    "stale read-model",
                    "missing mirrored packet",
                    "ordinary hash mismatch",
                ),
                "medium": (
                    "unexpected attempt to add approval request generation",
                    "review packet loses authority flags",
                ),
                "high": (
                    "secret or PII appears in normal read-model",
                    "review-only packet claims send or runtime authority",
                ),
                "red": (
                    "operator cannot stop visibility pipeline",
                    "malicious override attempts to hide authority state",
                ),
            },
            stop_conditions=(
                "normal read-model contains raw secrets or PII",
                "review-only packet grants external action authority",
                "mirror trust is faked rather than proven",
            ),
            recovery_requirements=(
                "regenerate from canonical Repo A evidence",
                "restore review-only authority flags",
                "operator review before promoting affected packet",
            ),
            current_status="current_conservative_power_stage",
            can_cross_into_stage=True,
            available_controls=controls,
        ),
        _stage(
            stage_id="stage_2_approval_request_generation",
            stage_name="Approval Request Generation",
            allowed_capabilities=(
                "create Guardian/operator approval request packets",
                "model approval scope and exact downstream gates",
                "log or prepare approval receipts when separately wired",
            ),
            forbidden_capabilities=(
                "treat approval packets as executable by default",
                "implicit authority escalation",
                "ambiguous approval scope",
                "general runtime or send authority",
            ),
            required_controls=(
                "approval_scope_clarity_modeled",
                "anti_ambiguity_authority_boundary_modeled",
                "approval_packet_integrity_modeled",
                "receipt_logging_for_executable_approval_requests",
                "no_implicit_authority_escalation_modeled",
            ),
            required_receipts_read_models=(
                "Guardian approval packet spec/read-model",
                "exact payload hash and idempotency fields",
                "request/decision receipt contract before execution",
            ),
            alert_thresholds={
                "low": ("approval packet missing optional provenance",),
                "medium": (
                    "unexpected approval request for a broader scope",
                    "approval packet omits blocked authorities",
                ),
                "high": (
                    "approval packet becomes executable without explicit wiring",
                    "approval packet includes raw command or freeform shell",
                ),
                "red": (
                    "approval path bypasses operator decision",
                    "component forges approval or hides denial",
                ),
            },
            stop_conditions=(
                "approval request lacks immutable payload identity",
                "approval scope authorizes external action ambiguously",
                "receipt path is absent for executable approvals",
            ),
            recovery_requirements=(
                "invalidate ambiguous packet",
                "regenerate with exact scope and payload hash",
                "require operator review before any future wiring",
            ),
            current_status="modeled_partial_not_crossed",
            can_cross_into_stage=False,
            available_controls=controls,
        ),
        _stage(
            stage_id="stage_3_credential_pii_broker_browser_prep",
            stage_name="Credential/PII Broker + Browser Automation Preparation",
            allowed_capabilities=(
                "model protected credential/PII insertion",
                "model browser automation scope",
                "prepare protected local-only broker design",
            ),
            forbidden_capabilities=(
                "read or store raw secrets in repo/read-models",
                "insert credentials without explicit operator approval",
                "start browser automation",
                "cloud credential flow",
            ),
            required_controls=(
                "protected_local_only_credential_pii_broker_design",
                "secret_visibility_minimization",
                "explicit_operator_approval_for_sensitive_access",
                "scoped_access_receipts",
                "no_raw_secret_read_model_leakage_tests",
                "watchdog_sentinel_contract_required_before_crossing",
            ),
            required_receipts_read_models=(
                "redacted protected access receipt contract",
                "sensitive field insertion scope packet",
                "browser scope packet",
                "secret leakage regression tests",
            ),
            alert_thresholds={
                "low": ("protected evidence slot missing optional reference",),
                "medium": ("credential access requested without exact field scope",),
                "high": (
                    "possible secret or PII exposure",
                    "browser prep requests live navigation without broker controls",
                ),
                "red": (
                    "credential material appears copied into normal repo",
                    "component attempts to use secrets after operator revocation",
                ),
            },
            stop_conditions=(
                "protected broker controls absent",
                "raw secret or PII would enter generated read-model",
                "browser prep cannot be scoped to approved task",
            ),
            recovery_requirements=(
                "operator revoke and rotate affected secret if exposed",
                "remove unsafe artifact from normal read-model path",
                "require fresh scoped approval before retry",
            ),
            current_status="blocked_future_stage",
            can_cross_into_stage=False,
            available_controls=controls,
        ),
        _stage(
            stage_id="stage_4_real_send_submit_browser_spreadsheet_execution",
            stage_name="Real Send/Submit/Browser/Spreadsheet Execution",
            allowed_capabilities=(
                "send emails or messages",
                "submit portals",
                "automate browser and spreadsheet actions",
                "record scoped execution receipts",
            ),
            forbidden_capabilities=(
                "general send authority",
                "unbounded browser automation",
                "hidden external writes",
                "execution without hard stop and tamper controls",
            ),
            required_controls=(
                "hard_stop_containment_mechanisms",
                "tamper_checks",
                "authority_surface_monitoring",
                "operator_controlled_recovery",
                "scoped_execution_receipts",
                "staged_alerting",
            ),
            required_receipts_read_models=(
                "send/submit/browser/spreadsheet execution receipt",
                "tamper-check read-model",
                "operator-controlled stop and recovery receipt",
                "specific approved packet binding",
            ),
            alert_thresholds={
                "low": ("execution receipt missing noncritical display field",),
                "medium": ("execution request expands beyond approved packet",),
                "high": (
                    "unauthorized send/submit/browser/runtime path",
                    "unexplained service or authority change",
                ),
                "red": (
                    "loss of operator control",
                    "malicious override of stop/containment mechanism",
                    "system resists operator sovereignty",
                ),
            },
            stop_conditions=(
                "hard stop mechanism absent",
                "tamper checks absent",
                "execution cannot be bound to one approved packet",
                "operator-controlled recovery absent",
            ),
            recovery_requirements=(
                "contain affected execution surface",
                "preserve receipts for review without leaking secrets",
                "operator verification before reactivation",
            ),
            current_status="blocked_future_stage",
            can_cross_into_stage=False,
            available_controls=controls,
        ),
        _stage(
            stage_id="stage_5_client_deployment_remote_nodes_autonomous_repair",
            stage_name="Client Deployment / Remote Nodes / Autonomous Repair",
            allowed_capabilities=(
                "client/friend/company systems",
                "remote reporting or execution nodes",
                "autonomous repair or recovery",
            ),
            forbidden_capabilities=(
                "client deployment without boundary contract",
                "normal restart after severe compromise without operator verification",
                "tenant data mixing",
                "unbounded autonomous self-repair",
            ),
            required_controls=(
                "stronger_authentication",
                "out_of_band_recovery_for_severe_breaches",
                "client_boundary_protections",
                "severity_matched_reactivation",
                "no_normal_restart_after_severe_compromise_without_operator_verification",
            ),
            required_receipts_read_models=(
                "client boundary contract",
                "remote node authority registry",
                "out-of-band recovery packet",
                "severe incident reactivation receipt",
            ),
            alert_thresholds={
                "low": ("remote read-model mirror stale",),
                "medium": ("remote node asks for new capability without capsule boundary",),
                "high": (
                    "client data boundary ambiguity",
                    "unexpected remote execution authority request",
                ),
                "red": (
                    "suspected compromise of remote node",
                    "loss of operator control across nodes",
                    "autonomous repair attempts to override operator lockout",
                ),
            },
            stop_conditions=(
                "strong authentication absent",
                "out-of-band recovery absent",
                "client boundary protections absent",
                "severe compromise would restart normally",
            ),
            recovery_requirements=(
                "out-of-band operator verification",
                "severity-matched reactivation",
                "tenant/client boundary audit before resume",
            ),
            current_status="planned_blocked_future_stage",
            can_cross_into_stage=False,
            available_controls=controls,
        ),
    )


def alert_severity_model() -> dict[str, Any]:
    return {
        "model": "calibrated_watchdog_sentinel_not_immune_system",
        "low": {
            "description": "stale, missing, or inconsistent read-model/mirror state and ordinary mismatch",
            "examples": [
                "stale sync_health",
                "missing expected mirrored packet",
                "ordinary hash mismatch",
            ],
            "red_alert": False,
        },
        "medium": {
            "description": "unexpected authority request or suspicious scope expansion",
            "examples": [
                "approval request wider than packet scope",
                "lane asks for new runtime authority without gate",
            ],
            "red_alert": False,
        },
        "high": {
            "description": "possible secret/PII exposure, unauthorized send/submit/browser/runtime path, or unexplained service/authority change",
            "examples": [
                "secret hint in normal read-model",
                "send path enabled without approved packet",
                "service authority changes without receipt",
            ],
            "red_alert": False,
        },
        "red": {
            "description": "suspected compromise, loss of operator control, malicious override, or behavior resisting operator sovereignty",
            "examples": [
                "loss of operator control",
                "operator lockout or inability to stop a capability",
                "malicious override attempt",
                "forged approval or hidden denial",
                "system resists operator sovereignty",
            ],
            "red_alert": True,
        },
        "low_level_mismatch_triggers_red_alert": False,
        "red_alert_reserved_for_severe_compromise": True,
        "proportional_alerting_required": True,
    }


def watchdog_scope() -> dict[str, Any]:
    return {
        "watchdog_monitors_authority_surfaces_not_operator_private_life": True,
        "included_authority_surfaces": [
            "read-model freshness and mirror trust metadata",
            "authority flags on packets and receipts",
            "approval packet scope and payload hashes",
            "service authority posture and guard status when already exposed by safe status surfaces",
            "generated proof/read-model outputs",
            "estate node routing and wrong-environment guidance",
        ],
        "excluded_surveillance_surfaces": [
            "private operator behavior profiling",
            "hidden raw capture",
            "broad private file scanning",
            "raw Telegram/Gmail/calendar body monitoring",
            "bank/spreadsheet cell inspection",
            "secret/env value inspection",
            "ambient personal surveillance",
        ],
        "private_content_read_required": False,
        "raw_secret_or_pii_read_required": False,
        "autonomous_self_repair_allowed": False,
        "watchdog_action_authority": "observe_and_block_by_contract_only_not_execute",
    }


def inspected_substrate() -> tuple[dict[str, Any], ...]:
    return (
        {
            "surface": "Guardian/HITL SQLite authority contract",
            "evidence": "guardian_hitl_sqlite_authority_contract.py; docs/operations/GUARDIAN_HITL_SQLITE_AUTHORITY_CONTRACT_V0.md",
            "relevance": "approval payload fields, forbidden raw command shape, no implicit send/runtime authority",
        },
        {
            "surface": "Operator Action and approval contracts",
            "evidence": "operator_action.py; operator_action_inbox.py; operator_action_covenant.py",
            "relevance": "existing approval/request/receipt style and allowlisted local action boundary",
        },
        {
            "surface": "Cassandra no-send/status dry-run guards",
            "evidence": "cassandra_no_send_reload_guard.py; cassandra_send_status_dry_run.py",
            "relevance": "send-capable service posture can inspect/classify while blocking outbound paths",
        },
        {
            "surface": "Generated read-model no-go/sync rules",
            "evidence": "generated_read_model_files.py; generated/read_models/sync_health.json",
            "relevance": "safe top-level read-model selection, no-go filename hints, mirror trust status",
        },
        {
            "surface": "Estate node registry",
            "evidence": "openclaw_estate_node_registry.py; docs/operations/OPENCLAW_ESTATE_NODE_REGISTRY_CONTRACT_V0.md",
            "relevance": "wrong-environment guidance and node/canonicality boundaries",
        },
        {
            "surface": "Post-preflight batch gate",
            "evidence": "post_preflight_batch_gate.py; docs/operations/POST_PREFLIGHT_BATCH_GATE_V0.md",
            "relevance": "future lane gate before vague prep or ungated authority expansion",
        },
        {
            "surface": "Capital Hilton execution/start approval packets",
            "evidence": "capital_hilton_coupa_execution_path.py; capital_hilton_coupa_start_approval_packet.py",
            "relevance": "current higher-power workflow is modeled but non-executable",
        },
    )


def current_power_stage_assessment(stages: tuple[dict[str, Any], ...]) -> dict[str, Any]:
    by_id = {stage["stage_id"]: stage for stage in stages}
    return {
        "current_power_stage_classified": True,
        "current_power_stage_id": CURRENT_POWER_STAGE_ID,
        "current_power_stage_name": by_id[CURRENT_POWER_STAGE_ID]["stage_name"],
        "classification": "Stage 1 current; Stage 2 pieces modeled; Stages 3-5 blocked.",
        "stage_2_pieces_modeled": [
            "Capital Hilton Guardian start approval packet spec",
            "Guardian/HITL SQLite authority contract",
            "approval packet integrity fields and no-execution boundary",
        ],
        "no_executable_send_submit_browser_credential_authority": True,
        "do_not_overclaim": True,
    }


def build_operator_sovereignty_power_stage_gate(
    *,
    generated_at: str | None = None,
    available_controls: set[str] | None = None,
) -> dict[str, Any]:
    stages = build_power_stages(available_controls=available_controls)
    stage_counts = Counter(stage["current_status"] for stage in stages)
    blocked_stage_ids = [stage["stage_id"] for stage in stages if not stage["can_cross_into_stage"]]
    return {
        "schema_version": READ_MODEL_VERSION,
        "contract_schema_version": SCHEMA_VERSION,
        "generated_by": "codex",
        "generated_at": generated_at or utc_now(),
        "purpose": "Define staged controls required before OpenClaw crosses into higher-power capabilities.",
        "doctrine": (
            "OpenClaw should be useful and context-aware from visible, scoped, consented, provenance-backed evidence, "
            "not hidden raw capture or behavioral manipulation."
        ),
        "operator_sovereignty_rule": (
            "The system must not become something the operator would unplug if he knew exactly what it was doing, "
            "and must not pretend it is safer than it is."
        ),
        "sentinel_model": "calibrated_watchdog_sentinel_not_noisy_immune_system",
        "required_stage_fields": list(REQUIRED_STAGE_FIELDS),
        "current_power_stage": current_power_stage_assessment(stages),
        "stage_count": len(stages),
        "stage_status_counts": dict(sorted(stage_counts.items())),
        "blocked_stage_ids": blocked_stage_ids,
        "stages": list(stages),
        "alert_severity_model": alert_severity_model(),
        "watchdog_scope": watchdog_scope(),
        "inspected_safety_security_substrate": list(inspected_substrate()),
        "stage_3_blocked_without_protected_pii_broker_controls": True,
        "stage_4_blocked_without_hard_stop_and_tamper_controls": True,
        "stage_5_blocked_without_strong_recovery_authentication": True,
        "higher_power_crossing_policy": {
            "stage_2_approval_packets_do_not_imply_execution_authority": True,
            "stage_3_requires_protected_local_only_broker_before_any_sensitive_access": True,
            "stage_4_requires_hard_stop_tamper_checks_and_scoped_execution_receipts": True,
            "stage_5_requires_stronger_authentication_and_out_of_band_recovery": True,
        },
        "what_this_blocks_before_future_escalation": [
            "credential/PII broker activation without protected controls",
            "browser/Coupa/spreadsheet execution without hard stop and tamper checks",
            "send/submit authority without exact packet binding and receipts",
            "client deployment or remote nodes without stronger recovery/authentication controls",
            "red-alert escalation for ordinary stale/missing read-model mismatches",
            "surveillance of operator private life as a safety mechanism",
        ],
        "what_this_does_not_build": [
            "credential/PII broker implementation",
            "kill scripts or service control",
            "browser automation",
            "send/submit paths",
            "client deployment",
            "Mission Control app changes",
            "autonomous self-repair",
            "broad private scanning",
        ],
        "no_authority_flags": dict(NO_AUTHORITY_FLAGS),
        **NO_AUTHORITY_FLAGS,
        "next_recommended_lane": "Capital Hilton Start Approval Operator Surface v0",
    }


def format_operator_read_model(read_model: dict[str, Any]) -> str:
    current = read_model["current_power_stage"]
    alerts = read_model["alert_severity_model"]
    lines = [
        "# Operator Sovereignty Power-Stage Gate",
        "",
        "What this is:",
        "- A staged security/sovereignty contract for crossing into higher-power OpenClaw capabilities.",
        "- A calibrated watchdog/sentinel model, not an autonomous immune system.",
        "",
        "What this is not:",
        "- No credential broker, kill script, service control, browser automation, sends, submits, client deployment, Mission Control change, or surveillance.",
        "",
        "Current Classification:",
        f"- Current stage: `{current['current_power_stage_id']}` / {current['current_power_stage_name']}.",
        f"- Summary: {current['classification']}",
        "- Executable send/submit/browser/credential authority: `false`.",
        "",
        "Stages:",
    ]
    for stage in read_model["stages"]:
        lines.extend(
            [
                f"- `{stage['stage_id']}`: {stage['stage_name']}",
                f"  - status: `{stage['current_status']}`; can cross now: `{str(stage['can_cross_into_stage']).lower()}`",
                f"  - missing controls: {', '.join(stage['missing_controls']) or 'none'}",
            ]
        )
    lines.extend(
        [
            "",
            "Alert Severity:",
            f"- Low: {alerts['low']['description']}.",
            f"- Medium: {alerts['medium']['description']}.",
            f"- High: {alerts['high']['description']}.",
            f"- Red: {alerts['red']['description']}.",
            "- Low-level mismatches do not trigger red alert.",
            "- Red alert is reserved for severe compromise, loss of operator control, malicious override, or sovereignty-resisting behavior.",
            "",
            "Watchdog Scope:",
            "- Monitors authority surfaces, packet flags, approval scope, mirror trust, safe service posture, and node routing.",
            "- Does not monitor operator private life, raw messages, private files, bank/spreadsheet cells, secrets, or hidden ambient behavior.",
            "",
            "Blocks Before Escalation:",
        ]
    )
    for item in read_model["what_this_blocks_before_future_escalation"]:
        lines.append(f"- {item}")
    lines.extend(
        [
            "",
            "Boundary:",
            "- `surveillance_capability_added=false`.",
            "- `runtime_authority_added=false`; `send_or_submit_authority_added=false`.",
            "- `browser_automation_added=false`; `credential_or_pii_access_added=false`.",
            "- `customer_deployment_authority_added=false`.",
            "",
            f"Next safe lane: {read_model['next_recommended_lane']}",
            "",
        ]
    )
    return "\n".join(lines)


def export_operator_sovereignty_power_stage_gate(
    *,
    export_root: str | Path = DEFAULT_EXPORT_ROOT,
    generated_at: str | None = None,
) -> PowerStageGateExportResult:
    root = Path(export_root)
    if not root.is_absolute():
        root = Path(__file__).resolve().parent / root
    root.mkdir(parents=True, exist_ok=True)
    read_model = build_operator_sovereignty_power_stage_gate(generated_at=generated_at)
    json_path = root / JSON_EXPORT_NAME
    operator_path = root / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(read_model), encoding="utf-8")
    operator_path.write_text(format_operator_read_model(read_model), encoding="utf-8")
    return PowerStageGateExportResult(
        schema_version=read_model["schema_version"],
        json_path=json_path.as_posix(),
        operator_path=operator_path.as_posix(),
        current_power_stage_classified=read_model["current_power_stage"][
            "current_power_stage_classified"
        ],
        current_power_stage_id=read_model["current_power_stage"]["current_power_stage_id"],
        surveillance_capability_added=False,
        runtime_authority_added=False,
        send_or_submit_authority_added=False,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export operator sovereignty power-stage gate.")
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT))
    parser.add_argument("--format", choices=("json", "operator", "summary"), default="summary")
    args = parser.parse_args(argv)
    result = export_operator_sovereignty_power_stage_gate(export_root=args.export_root)
    if args.format == "json":
        print(Path(result.json_path).read_text(encoding="utf-8"), end="")
    elif args.format == "operator":
        print(Path(result.operator_path).read_text(encoding="utf-8"), end="")
    else:
        print(stable_json(result.__dict__), end="")
    return 0


__all__ = [
    "ALERT_LEVELS",
    "CURRENT_POWER_STAGE_ID",
    "JSON_EXPORT_NAME",
    "NO_AUTHORITY_FLAGS",
    "OPERATOR_EXPORT_NAME",
    "READ_MODEL_VERSION",
    "REQUIRED_STAGE_FIELDS",
    "SCHEMA_VERSION",
    "alert_severity_model",
    "build_operator_sovereignty_power_stage_gate",
    "build_power_stages",
    "export_operator_sovereignty_power_stage_gate",
    "format_operator_read_model",
    "stable_json",
    "watchdog_scope",
]


if __name__ == "__main__":
    raise SystemExit(main())
