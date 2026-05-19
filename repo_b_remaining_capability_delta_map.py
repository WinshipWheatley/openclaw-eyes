"""Repo B remaining capability delta map v0.

This read-model inspects Repo B as reference-only path metadata and compares
notable older capability surfaces against the Repo A known rail completion map.
It does not import or execute Repo B modules, read secrets, run daemons, migrate
code, or grant runtime/send/submit/security authority.
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

from post_preflight_batch_gate import PASS, evaluate_post_preflight_lane


ROOT = Path(__file__).resolve().parent
DEFAULT_REPO_B_ROOT = Path("/home/openclaw_external/openclaw-runtime")
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_BASELINE_PATH = DEFAULT_EXPORT_ROOT / "repo_a_known_rail_completion_map.json"

SCHEMA_VERSION = "repo_b_remaining_capability_delta_map_v0"
JSON_EXPORT_NAME = "repo_b_remaining_capability_delta_map.json"
OPERATOR_EXPORT_NAME = "repo_b_remaining_capability_delta_map_OPERATOR.md"

CLASSIFICATIONS = (
    "ALREADY_REPRESENTED_IN_REPO_A",
    "PARTIALLY_REPRESENTED_IN_REPO_A",
    "MISSING_FROM_REPO_A",
    "SUPERSEDED_BY_REPO_A",
    "UNSAFE_OR_BLOCKED",
    "OBSOLETE_OR_STALE",
    "WORTH_BRINGING_FORWARD",
    "UNKNOWN_NEEDS_OPERATOR_MEMORY_REVIEW",
)

CONFIDENCE_LEVELS = ("high", "medium", "low")

SAFE_EXTENSIONS = {".py", ".sh", ".md", ".json", ".yaml", ".yml"}
SKIP_PATH_PARTS = {
    ".git",
    "__pycache__",
    ".venv",
    "venv",
    "node_modules",
    "logs",
    "log",
    "archive",
    "backups",
    "polish_loop/tasks",
}
SENSITIVE_NAME_FRAGMENTS = (
    ".env",
    "secret",
    "token",
    "credential",
    "password",
    "keyfile",
    "oauth",
    "cookie",
)

NO_AUTHORITY_FLAGS = {
    "repo_b_reference_only": True,
    "repo_b_code_executed": False,
    "repo_b_modules_imported": False,
    "repo_b_code_migrated": False,
    "runtime_authority_added": False,
    "send_or_submit_authority_added": False,
    "approval_execution_authority_added": False,
    "browser_or_coupa_authority_added": False,
    "credential_or_oauth_accessed": False,
    "gmail_calendar_coupa_accessed": False,
    "planner_builder_agent_automation_activated": False,
    "mission_control_app_changed": False,
    "security_pass_started": False,
    "live_workflow_authority_created": False,
}

REMEMBERED_GAPS = (
    "Cassandra calendar",
    "Chief status",
    "Hermes status",
    "Niles status",
    "deterministic + agentic planner/builder automation",
    "automatic fix loop",
    "brain-dump/cue parser",
    "dropped intent / build-now-vs-hold-until-right-time workflow",
)


@dataclass(frozen=True)
class CapabilitySpec:
    capability_id: str
    title: str
    likely_lane_domain: str
    description: str
    repo_b_patterns: tuple[str, ...]
    repo_a_equivalents: tuple[str, ...]
    classification_when_found: str
    classification_when_missing: str
    confidence_when_found: str
    authority_risk: str
    should_bring_forward: bool
    why_or_why_not: str
    suggested_future_lane: str


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


def _safe_repo_b_path(path: Path, repo_b_root: Path) -> bool:
    try:
        rel = path.resolve().relative_to(repo_b_root.resolve())
    except (OSError, ValueError):
        return False
    rel_text = rel.as_posix().lower()
    if path.suffix.lower() not in SAFE_EXTENSIONS:
        return False
    if any(part in rel_text.split("/") for part in {".git", "__pycache__", ".venv", "venv", "node_modules"}):
        return False
    if any(skip in rel_text for skip in SKIP_PATH_PARTS):
        return False
    return not any(fragment in rel.name.lower() for fragment in SENSITIVE_NAME_FRAGMENTS)


def safe_repo_b_inventory(repo_b_root: str | Path = DEFAULT_REPO_B_ROOT) -> dict[str, Any]:
    root = Path(repo_b_root)
    if not root.exists():
        return {
            "repo_b_root": str(root),
            "repo_b_present": False,
            "safe_relative_paths": [],
            "path_count": 0,
            "skipped_sensitive_or_no_go_count": 0,
            "inspection_mode": "reference_only_path_metadata",
            "body_read": False,
            "repo_b_code_executed": False,
        }
    safe_paths: list[str] = []
    skipped = 0
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        try:
            rel = path.resolve().relative_to(root.resolve()).as_posix()
        except (OSError, ValueError):
            skipped += 1
            continue
        if _safe_repo_b_path(path, root):
            safe_paths.append(rel)
        else:
            skipped += 1
    return {
        "repo_b_root": str(root),
        "repo_b_present": True,
        "safe_relative_paths": sorted(safe_paths),
        "path_count": len(safe_paths),
        "skipped_sensitive_or_no_go_count": skipped,
        "inspection_mode": "reference_only_path_metadata",
        "body_read": False,
        "repo_b_code_executed": False,
    }


def _read_json_if_present(path: str | Path, *, repo_root: str | Path = ROOT) -> dict[str, Any]:
    target = _rooted(path, repo_root=repo_root)
    if not target.exists():
        return {}
    payload = json.loads(target.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _capability_specs() -> tuple[CapabilitySpec, ...]:
    return (
        CapabilitySpec(
            capability_id="cassandra_core_listener_review",
            title="Cassandra listener / review core",
            likely_lane_domain="cassandra_receive_review",
            description="Older Cassandra receive/review files are present, but Repo A already has governed receive and draft review rails.",
            repo_b_patterns=("cassandra_listener.py", "cassandra_brain.py", "cassandra_capability.py"),
            repo_a_equivalents=(
                "generated/read_models/cassandra_listener_governed_shadow.json",
                "generated/read_models/cassandra_draft_review_packet.json",
                "cassandra_listener.py",
            ),
            classification_when_found="ALREADY_REPRESENTED_IN_REPO_A",
            classification_when_missing="UNKNOWN_NEEDS_OPERATOR_MEMORY_REVIEW",
            confidence_when_found="high",
            authority_risk="medium_if_legacy_listener_paths_are_reused_directly",
            should_bring_forward=False,
            why_or_why_not="Repo A already has receive/review rails; only compare deltas, do not re-import legacy listener behavior.",
            suggested_future_lane="None unless a specific missing Cassandra behavior is identified",
        ),
        CapabilitySpec(
            capability_id="cassandra_calendar_email_draft",
            title="Cassandra calendar/email/draft systems",
            likely_lane_domain="cassandra_email_calendar",
            description="Repo B carries live-adjacent email/calendar/draft surfaces; Repo A has reconciliation and review-only draft rails.",
            repo_b_patterns=("cassandra_outreach.py", "chief_email_brain.py", "chief_calendar_brain.py", "google_access_broker.py"),
            repo_a_equivalents=(
                "generated/read_models/cassandra_email_calendar_capability_reconciliation.json",
                "generated/read_models/cassandra_draft_review_packet.json",
                "generated/read_models/guardian_draft_approval_request_contract.json",
            ),
            classification_when_found="PARTIALLY_REPRESENTED_IN_REPO_A",
            classification_when_missing="UNKNOWN_NEEDS_OPERATOR_MEMORY_REVIEW",
            confidence_when_found="high",
            authority_risk="high_live_email_calendar_oauth_if_reused",
            should_bring_forward=True,
            why_or_why_not="Bring forward only missing draft/review semantics through existing no-live-authority rails; do not bring forward live OAuth/send behavior.",
            suggested_future_lane="Cassandra Email Calendar Delta Detangle v0",
        ),
        CapabilitySpec(
            capability_id="chief_orchestrator_planner_status",
            title="Chief orchestrator/planner/status systems",
            likely_lane_domain="chief_work_packets",
            description="Repo B contains many Chief brains and routing/status surfaces; Repo A has Work Board and Agent Work Packet visibility but not full Chief status maturity.",
            repo_b_patterns=("chief_router.py", "chief_queue_brain.py", "chief_session_manager.py", "chief_worker.py", "chief_watcher_brain.py"),
            repo_a_equivalents=(
                "generated/read_models/work_board.json",
                "generated/read_models/agent_work_packets.json",
                "generated/read_models/intent_router.json",
            ),
            classification_when_found="PARTIALLY_REPRESENTED_IN_REPO_A",
            classification_when_missing="UNKNOWN_NEEDS_OPERATOR_MEMORY_REVIEW",
            confidence_when_found="high",
            authority_risk="high_if_legacy_chief_runtime_or_watchers_are_activated",
            should_bring_forward=True,
            why_or_why_not="Bring forward status/readiness semantics, not runtime brains or watchers.",
            suggested_future_lane="Chief Status Rail Completion v0",
        ),
        CapabilitySpec(
            capability_id="guardian_legacy_approval_hitl",
            title="Legacy Guardian approval/HITL paths",
            likely_lane_domain="guardian_hitl",
            description="Repo B has legacy approval sender/listener/brain files that Repo A has already audited and modeled as compatibility/reference.",
            repo_b_patterns=("chief_approval_brain.py", "chief_guardian_listener.py", "chief_guardian_sender.py", "hitl_flowchart_gen.py"),
            repo_a_equivalents=(
                "generated/read_models/guardian_hitl_authority_reconciliation.json",
                "generated/read_models/guardian_hitl_sqlite_authority_contract.json",
                "generated/read_models/guardian_responsibility_dna_audit.json",
            ),
            classification_when_found="SUPERSEDED_BY_REPO_A",
            classification_when_missing="ALREADY_REPRESENTED_IN_REPO_A",
            confidence_when_found="high",
            authority_risk="high_legacy_telegram_json_approval_if_reactivated",
            should_bring_forward=False,
            why_or_why_not="Repo A contract/read-model rails supersede these as authority; keep as reference only.",
            suggested_future_lane="HITL Transition Criteria Review v0",
        ),
        CapabilitySpec(
            capability_id="planner_builder_automation_loops",
            title="Deterministic + agentic planner/builder automation",
            likely_lane_domain="automation_builder",
            description="Repo B contains builder/watchdog/orchestrator/runner surfaces that should not run before authority and security threshold work.",
            repo_b_patterns=("builder_watcher.sh", "loop_supervisor.sh", "polish_loop/orchestrator.py", "runner_registry.py", "runner_profiles.py"),
            repo_a_equivalents=(
                "generated/read_models/active_machinery_block_later_guardrail.json",
                "generated/read_models/active_machinery_high_risk_quarantine.json",
                "generated/read_models/repo_a_known_rail_completion_map.json",
            ),
            classification_when_found="UNSAFE_OR_BLOCKED",
            classification_when_missing="UNKNOWN_NEEDS_OPERATOR_MEMORY_REVIEW",
            confidence_when_found="high",
            authority_risk="high_agentic_runtime_execution_if_activated",
            should_bring_forward=False,
            why_or_why_not="Do not bring forward as runnable machinery; only later compare specific planner/builder state concepts.",
            suggested_future_lane="Planner Builder Delta Safety Review v0",
        ),
        CapabilitySpec(
            capability_id="automatic_fix_repair_loops",
            title="Automatic fix / repair loops",
            likely_lane_domain="automation_repair",
            description="Repo B has polish-loop and fallback repair surfaces that may contain useful workflow ideas but are unsafe as live repair loops.",
            repo_b_patterns=("polish_loop/pc_review_fallback.py", "polish_loop/run_polish_pass.sh", "queue_balancer.py", "queue_validator.py"),
            repo_a_equivalents=(
                "generated/read_models/active_machinery_quarantine_decision_packet.json",
                "generated/read_models/operator_sovereignty_power_stage_gate.json",
            ),
            classification_when_found="UNSAFE_OR_BLOCKED",
            classification_when_missing="UNKNOWN_NEEDS_OPERATOR_MEMORY_REVIEW",
            confidence_when_found="high",
            authority_risk="high_automatic_mutation_or_self_repair_if_enabled",
            should_bring_forward=False,
            why_or_why_not="Useful ideas may be harvested later as receipts/status contracts, but live repair loops remain blocked.",
            suggested_future_lane="Automatic Repair Loop Contract Harvest v0",
        ),
        CapabilitySpec(
            capability_id="brain_dump_inbox_parser",
            title="Brain-dump / inbox parser",
            likely_lane_domain="operator_intake",
            description="Repo B has inbox parser evidence; Repo A has intent/dropped-intent surfaces and a legacy brain dump parser requiring governance before use.",
            repo_b_patterns=("inbox_parser.py", "CURRENT_STATE.md", "NEXT_ACTIONS.md"),
            repo_a_equivalents=(
                "brain_dump_parser.py",
                "generated/read_models/dropped_intents.json",
                "generated/read_models/intent_router.json",
            ),
            classification_when_found="PARTIALLY_REPRESENTED_IN_REPO_A",
            classification_when_missing="UNKNOWN_NEEDS_OPERATOR_MEMORY_REVIEW",
            confidence_when_found="medium",
            authority_risk="medium_old_freeform_notes_could_be_misread_as_truth",
            should_bring_forward=True,
            why_or_why_not="Bring forward only safe cue/intake classification semantics, not broad note ingestion.",
            suggested_future_lane="Governed Cue Parser Delta v0",
        ),
        CapabilitySpec(
            capability_id="dropped_intent_task_queue_timing",
            title="Dropped intent / build-now-vs-hold workflow",
            likely_lane_domain="operator_intake_queue",
            description="Repo B queue balancer/validator hints at timing decisions; Repo A has dropped intent and work board visibility.",
            repo_b_patterns=("queue_balancer.py", "queue_validator.py", "chief_queue_brain.py"),
            repo_a_equivalents=(
                "generated/read_models/dropped_intents.json",
                "generated/read_models/work_board.json",
                "generated/read_models/agent_work_packets.json",
            ),
            classification_when_found="WORTH_BRINGING_FORWARD",
            classification_when_missing="UNKNOWN_NEEDS_OPERATOR_MEMORY_REVIEW",
            confidence_when_found="medium",
            authority_risk="medium_if_queue_logic_starts_execution_instead_of_classification",
            should_bring_forward=True,
            why_or_why_not="The hold-vs-build timing concept looks useful as read-model decision support before Repo B migration.",
            suggested_future_lane="Build Now Vs Hold Queue Posture v0",
        ),
        CapabilitySpec(
            capability_id="hermes_advisory_synthesis",
            title="Hermes advisory/synthesis systems",
            likely_lane_domain="hermes_advisory",
            description="Repo A has Hermes advisory helpers, but this Repo B inventory did not show a clear Hermes-named rail.",
            repo_b_patterns=("hermes", "advisory", "synthesis"),
            repo_a_equivalents=("hermes_advisory_packet.py", "generated/read_models/agent_lanes.json"),
            classification_when_found="PARTIALLY_REPRESENTED_IN_REPO_A",
            classification_when_missing="UNKNOWN_NEEDS_OPERATOR_MEMORY_REVIEW",
            confidence_when_found="low",
            authority_risk="medium_if_advisory_output_is_treated_as_decision_authority",
            should_bring_forward=False,
            why_or_why_not="Need Winship memory review: Repo B does not obviously expose Hermes by name in safe path inventory.",
            suggested_future_lane="Hermes Memory Review And Advisory Rail Check v0",
        ),
        CapabilitySpec(
            capability_id="niles_music_producer_album",
            title="Niles/music/producer systems",
            likely_lane_domain="music_art_projects",
            description="Repo B has album/music Chief modules; Repo A has Niles/Struna metadata and review packets.",
            repo_b_patterns=("chief_album_brain.py", "chief_album_batch.py", "chief_album_mixer.py", "chief_musiclaw_brain.py", "start_album_brain.sh"),
            repo_a_equivalents=(
                "generated/read_models/niles_album_review_packet.json",
                "generated/read_models/niles_album_evidence_intake_boundary.json",
                "generated/read_models/struna_obscura_project_capsule.json",
            ),
            classification_when_found="PARTIALLY_REPRESENTED_IN_REPO_A",
            classification_when_missing="UNKNOWN_NEEDS_OPERATOR_MEMORY_REVIEW",
            confidence_when_found="high",
            authority_risk="medium_if_raw_music_session_files_or_legacy_album_runtime_are_scanned",
            should_bring_forward=True,
            why_or_why_not="Bring forward album/status semantics through metadata-only Niles rail; do not scan creative folders.",
            suggested_future_lane="Niles Governed Metadata Review Packet Completion v0",
        ),
        CapabilitySpec(
            capability_id="report_bridge_client_company_reporting",
            title="Report Bridge / client/friend/company reporting",
            likely_lane_domain="report_bridge_client_capsules",
            description="Repo B has reporter/dashboard/briefing surfaces; Repo A has Report Bridge and project/client capsule substrate.",
            repo_b_patterns=("chief_reporter_brain.py", "ceo_briefing_worker.py", "dashboard_gen.py", "send_demo_dashboard.py"),
            repo_a_equivalents=(
                "generated/read_models/report_bridge.json",
                "generated/read_models/project_capsules.json",
                "generated/read_models/custom_build_module_detangling_contract.json",
            ),
            classification_when_found="PARTIALLY_REPRESENTED_IN_REPO_A",
            classification_when_missing="UNKNOWN_NEEDS_OPERATOR_MEMORY_REVIEW",
            confidence_when_found="high",
            authority_risk="medium_to_high_if_demo_send_or_client_reporting_runs_live",
            should_bring_forward=True,
            why_or_why_not="Bring forward reporting/capsule semantics only; demo send/dashboard live paths remain blocked or obsolete.",
            suggested_future_lane="Client Reporting Rail Delta Review v0",
        ),
        CapabilitySpec(
            capability_id="oauth_tool_browser_credential_bridges",
            title="Tool/OAuth/browser/credential bridges",
            likely_lane_domain="protected_access",
            description="Repo B contains Google broker/policy and PII vault surfaces that are useful only behind future protected-access controls.",
            repo_b_patterns=("google_access_broker.py", "google_access_policy.py", "pii_vault.py", "skill_loader.py", "skill_vetter.py"),
            repo_a_equivalents=(
                "generated/read_models/operator_sovereignty_power_stage_gate.json",
                "generated/read_models/cassandra_email_calendar_capability_reconciliation.json",
            ),
            classification_when_found="UNSAFE_OR_BLOCKED",
            classification_when_missing="UNKNOWN_NEEDS_OPERATOR_MEMORY_REVIEW",
            confidence_when_found="high",
            authority_risk="very_high_credentials_oauth_tool_execution",
            should_bring_forward=False,
            why_or_why_not="Do not bring forward until protected broker and Stage 3/4 controls exist; path metadata only for now.",
            suggested_future_lane="Protected Access Broker Design Review v0",
        ),
        CapabilitySpec(
            capability_id="pii_vault_protected_broker_concept",
            title="PII vault / protected broker concept",
            likely_lane_domain="protected_evidence",
            description="Repo B PII vault naming may contain useful concept evidence for later protected proof/credential broker design.",
            repo_b_patterns=("pii_vault.py",),
            repo_a_equivalents=("generated/read_models/operator_sovereignty_power_stage_gate.json",),
            classification_when_found="WORTH_BRINGING_FORWARD",
            classification_when_missing="UNKNOWN_NEEDS_OPERATOR_MEMORY_REVIEW",
            confidence_when_found="medium",
            authority_risk="very_high_if_raw_pii_or_secrets_are_read",
            should_bring_forward=True,
            why_or_why_not="Bring forward only the protected-reference concept later; do not read values or implement credential access now.",
            suggested_future_lane="Protected PII Broker Concept Delta v0",
        ),
        CapabilitySpec(
            capability_id="demo_dashboard_mobile_sync",
            title="Old dashboard/demo/mobile sync surfaces",
            likely_lane_domain="operator_helm_legacy",
            description="Repo B dashboard/demo/mobile sync surfaces appear superseded by Mission Control and governed read-model mirror posture.",
            repo_b_patterns=("dashboard_gen.py", "send_demo_dashboard.py", "retry_send_demo_dashboard.sh", "sync_to_mobile.sh"),
            repo_a_equivalents=(
                "generated/read_models/sync_health.json",
                "generated/read_models/context_selection.json",
                "generated/read_models/helm_state.json",
            ),
            classification_when_found="OBSOLETE_OR_STALE",
            classification_when_missing="SUPERSEDED_BY_REPO_A",
            confidence_when_found="medium",
            authority_risk="medium_if_old_dashboard_send_or_mobile_sync_paths_are_reused",
            should_bring_forward=False,
            why_or_why_not="Mission Control/read-model mirror should remain the helm path; old dashboards are reference only unless a missing view is proven.",
            suggested_future_lane="None before Mission Control asks for a specific missing view",
        ),
        CapabilitySpec(
            capability_id="budget_tracker_finance_legacy",
            title="Budget tracker / legacy finance helper",
            likely_lane_domain="finance",
            description="Repo B has old budget tracking; Repo A has Capital Hilton and finance evidence packet rails but not a full generic budget tracker.",
            repo_b_patterns=("budget_tracker.py", "chief_billing_brain.py", "chief_financial_brain.py", "chief_invoice_brain.py"),
            repo_a_equivalents=(
                "generated/read_models/finance_invoice_evidence_packets.json",
                "generated/read_models/finance_invoice_reconciliation.json",
                "generated/read_models/capital_hilton_two_invoice_workflow.json",
            ),
            classification_when_found="PARTIALLY_REPRESENTED_IN_REPO_A",
            classification_when_missing="UNKNOWN_NEEDS_OPERATOR_MEMORY_REVIEW",
            confidence_when_found="high",
            authority_risk="medium_if_old_finance_state_or_spreadsheet_cells_are_treated_as_truth",
            should_bring_forward=True,
            why_or_why_not="Bring forward only generic finance/budget posture if a named workflow needs it; no spreadsheet/bank reads.",
            suggested_future_lane="Generic Finance Budget Posture Delta v0",
        ),
        CapabilitySpec(
            capability_id="capability_skill_registry",
            title="Capability registry / skill system",
            likely_lane_domain="module_tooling",
            description="Repo B has capability and skill loading/vetting surfaces; Repo A has module registry and custom-build contracts.",
            repo_b_patterns=("capability_registry.py", "skill_loader.py", "skill_vetter.py"),
            repo_a_equivalents=(
                "approved_module_registry.py",
                "module_registry.py",
                "generated/read_models/custom_build_module_detangling_contract.json",
            ),
            classification_when_found="WORTH_BRINGING_FORWARD",
            classification_when_missing="UNKNOWN_NEEDS_OPERATOR_MEMORY_REVIEW",
            confidence_when_found="medium",
            authority_risk="high_if_skill_loading_executes_tools_or_code",
            should_bring_forward=True,
            why_or_why_not="Worth reviewing as metadata/tool classification, not as executable skill loading.",
            suggested_future_lane="Capability Skill Registry Metadata Delta v0",
        ),
        CapabilitySpec(
            capability_id="claude_command_notes",
            title="Claude command/runtime notes",
            likely_lane_domain="operator_memory_review",
            description="Repo B contains Claude-oriented command/runtime notes that are not a Repo A steel-thread rail.",
            repo_b_patterns=("CLAUDE.md", ".claude/commands/cassandra.md"),
            repo_a_equivalents=("OPENCLAW_RUNTIME.md", "USER.md"),
            classification_when_found="MISSING_FROM_REPO_A",
            classification_when_missing="UNKNOWN_NEEDS_OPERATOR_MEMORY_REVIEW",
            confidence_when_found="medium",
            authority_risk="low_to_medium_if_old_tool_notes_are_treated_as_current_law",
            should_bring_forward=False,
            why_or_why_not="Do not promote old tool-specific notes to law; compare later only if Winship remembers missing behavior.",
            suggested_future_lane="Operator Memory Review For Legacy Tool Notes v0",
        ),
    )


def _matches_pattern(path: str, pattern: str) -> bool:
    lowered_path = path.lower()
    lowered_pattern = pattern.lower()
    return lowered_path == lowered_pattern or lowered_path.endswith("/" + lowered_pattern) or lowered_pattern in lowered_path


def _path_present(path: str, *, repo_root: str | Path) -> bool:
    return _rooted(path, repo_root=repo_root).exists()


def _capability_record(
    spec: CapabilitySpec,
    *,
    repo_a_root: str | Path,
    safe_repo_b_paths: list[str],
) -> dict[str, Any]:
    if spec.classification_when_found not in CLASSIFICATIONS:
        raise ValueError(f"unsupported classification: {spec.classification_when_found}")
    if spec.classification_when_missing not in CLASSIFICATIONS:
        raise ValueError(f"unsupported missing classification: {spec.classification_when_missing}")
    if spec.confidence_when_found not in CONFIDENCE_LEVELS:
        raise ValueError(f"unsupported confidence: {spec.confidence_when_found}")
    matched = sorted(
        {
            path
            for path in safe_repo_b_paths
            for pattern in spec.repo_b_patterns
            if _matches_pattern(path, pattern)
        }
    )
    found = bool(matched)
    repo_a_equivalents = [
        {
            "path": path,
            "present": _path_present(path, repo_root=repo_a_root),
            "repo_a_evidence_not_truth": True,
        }
        for path in spec.repo_a_equivalents
    ]
    classification = spec.classification_when_found if found else spec.classification_when_missing
    repo_a_equivalent_present = any(item["present"] for item in repo_a_equivalents)
    return {
        "capability_id": spec.capability_id,
        "classification": classification,
        "repo_b_found": found,
        "repo_b_paths": matched,
        "short_description": spec.description,
        "likely_lane_domain": spec.likely_lane_domain,
        "repo_a_equivalent": repo_a_equivalents,
        "repo_a_equivalent_found": repo_a_equivalent_present,
        "confidence": spec.confidence_when_found if found else "low",
        "should_bring_forward": bool(spec.should_bring_forward and found),
        "why_or_why_not": spec.why_or_why_not,
        "suggested_future_lane": spec.suggested_future_lane,
        "authority_risk": spec.authority_risk,
        "reference_only": True,
        "repo_b_body_read": False,
        "repo_b_code_executed": False,
        "old_files_treated_as_truth": False,
    }


def _remembered_gap_records(capabilities: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id = {item["capability_id"]: item for item in capabilities}
    mapping = {
        "Cassandra calendar": ("cassandra_calendar_email_draft", "cassandra_email_calendar_capability_reconciliation"),
        "Chief status": ("chief_orchestrator_planner_status", "chief_work_packets"),
        "Hermes status": ("hermes_advisory_synthesis", "hermes_advisory"),
        "Niles status": ("niles_music_producer_album", "niles_album_struna"),
        "deterministic + agentic planner/builder automation": ("planner_builder_automation_loops", "planner_builder_guardrails"),
        "automatic fix loop": ("automatic_fix_repair_loops", "active_machinery_guardrails"),
        "brain-dump/cue parser": ("brain_dump_inbox_parser", "intent_dropped_intent"),
        "dropped intent / build-now-vs-hold-until-right-time workflow": ("dropped_intent_task_queue_timing", "dropped_intent_work_board"),
    }
    records: list[dict[str, Any]] = []
    for label in REMEMBERED_GAPS:
        cap_id, repo_a_hint = mapping[label]
        cap = by_id[cap_id]
        proven = cap["repo_a_equivalent_found"]
        found_b = cap["repo_b_found"]
        if cap["classification"] == "UNKNOWN_NEEDS_OPERATOR_MEMORY_REVIEW":
            status = "needs_operator_memory_review"
        elif proven and found_b and cap["classification"] in {
            "ALREADY_REPRESENTED_IN_REPO_A",
            "PARTIALLY_REPRESENTED_IN_REPO_A",
            "WORTH_BRINGING_FORWARD",
            "UNSAFE_OR_BLOCKED",
        }:
            status = "partially_matched" if cap["classification"] != "ALREADY_REPRESENTED_IN_REPO_A" else "proven_in_repo_a"
        elif found_b:
            status = "found_in_repo_b"
        elif proven:
            status = "proven_in_repo_a"
        else:
            status = "needs_operator_memory_review"
        records.append(
            {
                "remembered_area": label,
                "repo_a_hint": repo_a_hint,
                "proven_in_repo_a": proven,
                "found_in_repo_b": found_b,
                "partial_match": status == "partially_matched",
                "not_found_yet": not proven and not found_b,
                "needs_operator_memory_review": status in {"needs_operator_memory_review", "found_in_repo_b"},
                "status": status,
                "capability_id": cap_id,
                "classification": cap["classification"],
            }
        )
    return records


def _recommendations() -> list[dict[str, Any]]:
    lanes = (
        (
            "Chief Status Rail Completion v0",
            "Bring forward Chief status/readiness semantics as read-model proof, not runtime brains.",
            "Chief status and work-packet readiness",
            "chief_status_read_model_gap",
            "repo_a_known_rail_completion_map_v0",
            "Reusable status/readiness rail for legacy orchestration surfaces.",
            "Chief status completion read-model with legacy runtime blocked.",
        ),
        (
            "Build Now Vs Hold Queue Posture v0",
            "Model the hold-vs-build timing workflow from queue/dropped-intent evidence without executing queues.",
            "Dropped intent and build-now-vs-hold workflow",
            "queue_timing_decision_gap",
            "dropped_intents_work_board_read_models",
            "Reusable queue posture map for operator timing decisions.",
            "Read-model showing what should be built now, held, or memory-reviewed.",
        ),
        (
            "Protected Access Broker Concept Delta v0",
            "Review Repo B protected PII/OAuth/tool concepts as metadata only before any security-threshold lane.",
            "Future protected credential/PII broker design",
            "protected_access_concept_gap",
            "operator_sovereignty_power_stage_gate_v0",
            "Reusable protected-reference concept map without reading secrets or enabling credentials.",
            "Protected broker concept delta read-model; no implementation.",
        ),
    )
    results: list[dict[str, Any]] = []
    for lane_name, summary, workflow, bottleneck, contract_link, substrate, proof_output in lanes:
        gate = evaluate_post_preflight_lane(
            lane_name=lane_name,
            lane_summary=summary,
            named_operator_workflow=workflow,
            shared_bottleneck=bottleneck,
            steel_thread_contract_link=contract_link,
            reusable_substrate_improvement=substrate,
            workflow_proof_output=proof_output,
            detangling_scope={
                "serves_lane_directly": True,
                "opportunistic_only": True,
                "physical_module_extraction_requested": False,
                "client_repo_generation_requested": False,
                "detangling_required_before_workflow_proof": False,
                "notes": "Repo B delta is reference-only; record useful concepts as read-models before any migration.",
            },
            module_split_disposition={
                "disposition": "record_future_work",
                "recorded_future_work": True,
                "reason": "Potential module splits should be recorded for later, not acted on in this map.",
            },
            authority_change_requested={
                "requested": False,
                "authority_types": [],
                "reason": "Read-model/contract mapping only.",
            },
            expected_artifacts=[
                {"artifact_kind": "read_model", "path_or_contract": "generated/read_models/<future>.json"},
                {"artifact_kind": "operator_packet", "path_or_contract": "generated/read_models/<future>_OPERATOR.md"},
                {"artifact_kind": "test_proof", "path_or_contract": "focused tests"},
            ],
            validation_required=("focused tests", "JSON validation", "authority flags"),
            synthetic_example=False,
        )
        results.append(
            {
                "lane_name": lane_name,
                "why_next": summary,
                "post_preflight_batch_gate_evaluation": gate,
            }
        )
    return results


def _eli5_summary(
    *,
    capabilities: list[dict[str, Any]],
    remembered_gaps: list[dict[str, Any]],
    recommendations: list[dict[str, Any]],
) -> dict[str, Any]:
    already = [item["capability_id"] for item in capabilities if item["classification"] == "ALREADY_REPRESENTED_IN_REPO_A"]
    partial = [item["capability_id"] for item in capabilities if item["classification"] == "PARTIALLY_REPRESENTED_IN_REPO_A"]
    unsafe = [item["capability_id"] for item in capabilities if item["classification"] == "UNSAFE_OR_BLOCKED"]
    worth = [item["capability_id"] for item in capabilities if item["classification"] == "WORTH_BRINGING_FORWARD"]
    unknown = [item["remembered_area"] for item in remembered_gaps if item["needs_operator_memory_review"]]
    return {
        "summary_text": (
            "Repo B still contains a lot of the older OpenClaw machinery, but much of it is already "
            "represented in Repo A as safer read-models, proof rails, or blocked contracts. The useful "
            "remaining delta looks less like code to copy and more like concepts to harvest: Chief status, "
            "queue timing, protected-access ideas, and some music/reporting semantics. The risky old pieces "
            "are still the live loops, send/OAuth/tool bridges, and automatic repair machinery. Nothing here "
            "is ready for live execution."
        ),
        "already_handled_or_represented": already,
        "partly_tracked": partial,
        "may_need_bring_forward": worth,
        "unsafe_old_or_blocked": unsafe,
        "needs_winship_memory_review": unknown,
        "next_1_to_3_sensible_lanes": [item["lane_name"] for item in recommendations[:3]],
    }


def build_repo_b_remaining_capability_delta_map(
    *,
    repo_a_root: str | Path = ROOT,
    repo_b_root: str | Path = DEFAULT_REPO_B_ROOT,
    baseline_json: str | Path = DEFAULT_BASELINE_PATH,
    generated_at: str | None = None,
) -> dict[str, Any]:
    baseline = _read_json_if_present(baseline_json, repo_root=repo_a_root)
    inventory = safe_repo_b_inventory(repo_b_root)
    safe_paths = list(inventory["safe_relative_paths"])
    capabilities = [
        _capability_record(spec, repo_a_root=repo_a_root, safe_repo_b_paths=safe_paths)
        for spec in _capability_specs()
    ]
    classification_counts = Counter(item["classification"] for item in capabilities)
    authority_risk_counts = Counter(item["authority_risk"].split("_")[0] for item in capabilities)
    remembered = _remembered_gap_records(capabilities)
    recommendations = _recommendations()
    gate_pass_count = sum(
        1
        for item in recommendations
        if item["post_preflight_batch_gate_evaluation"]["gate_status"] == PASS
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_by": "codex",
        "generated_at": generated_at or utc_now(),
        "baseline_repo_a": {
            "path": _display_path(_rooted(baseline_json, repo_root=repo_a_root)),
            "present": bool(baseline),
            "schema_version": baseline.get("schema_version"),
            "known_rail_count": baseline.get("known_rail_count", 0),
            "maturity_counts": baseline.get("maturity_counts", {}),
            "readiness_counts": baseline.get("readiness_counts", {}),
            "security_pass_current": bool(baseline.get("security_pass_current", False)),
            "live_workflow_ready_count": (baseline.get("readiness_counts") or {}).get("live_workflow", 0),
        },
        "repo_b_inspection": {
            "repo_b_root": inventory["repo_b_root"],
            "repo_b_present": inventory["repo_b_present"],
            "inspection_mode": inventory["inspection_mode"],
            "path_count": inventory["path_count"],
            "skipped_sensitive_or_no_go_count": inventory["skipped_sensitive_or_no_go_count"],
            "body_read": False,
            "repo_b_code_executed": False,
            "repo_b_modules_imported": False,
            "representative_paths": safe_paths[:80],
            "inspected_locations": sorted({path.split("/")[0] for path in safe_paths})[:80],
        },
        "classification_labels": list(CLASSIFICATIONS),
        "classification_counts": dict(sorted(classification_counts.items())),
        "authority_risk_summary": dict(sorted(authority_risk_counts.items())),
        "capability_delta_list": capabilities,
        "already_represented": [
            item for item in capabilities if item["classification"] == "ALREADY_REPRESENTED_IN_REPO_A"
        ],
        "partially_represented": [
            item for item in capabilities if item["classification"] == "PARTIALLY_REPRESENTED_IN_REPO_A"
        ],
        "missing_from_repo_a": [
            item for item in capabilities if item["classification"] == "MISSING_FROM_REPO_A"
        ],
        "unsafe_or_obsolete": [
            item
            for item in capabilities
            if item["classification"] in {"UNSAFE_OR_BLOCKED", "OBSOLETE_OR_STALE", "SUPERSEDED_BY_REPO_A"}
        ],
        "worth_bringing_forward": [
            item for item in capabilities if item["classification"] == "WORTH_BRINGING_FORWARD"
        ],
        "remembered_but_not_proven_gaps": remembered,
        "operator_memory_review_items": [
            item for item in remembered if item["needs_operator_memory_review"]
        ],
        "future_lane_recommendations": recommendations,
        "recommended_next_lanes_all_gate_pass": gate_pass_count == len(recommendations),
        "security_pass_current": False,
        "security_pass_posture": "future_threshold_not_current_delta_lane",
        "live_execution_recommended": False,
        "repo_b_reference_only": True,
        "old_files_treated_as_evidence_not_truth": True,
        "operator_eli5_summary": _eli5_summary(
            capabilities=capabilities,
            remembered_gaps=remembered,
            recommendations=recommendations,
        ),
        "no_authority_flags": dict(NO_AUTHORITY_FLAGS),
        **NO_AUTHORITY_FLAGS,
    }


def format_repo_b_remaining_capability_delta_map(payload: dict[str, Any]) -> str:
    eli5 = payload["operator_eli5_summary"]
    lines = [
        "# Repo B Remaining Capability Delta Map v0",
        "",
        "Status:",
        f"- Repo A baseline rails: `{payload['baseline_repo_a']['known_rail_count']}`.",
        f"- Repo B paths inspected as metadata: `{payload['repo_b_inspection']['path_count']}`.",
        "- Repo B code executed: `false`.",
        "- Live/security-threshold work started: `false`.",
        "",
        "## ELI5 Summary",
        eli5["summary_text"],
        "",
        "Already handled or represented:",
    ]
    lines.extend(f"- `{item}`" for item in eli5["already_handled_or_represented"][:8])
    lines.extend(["", "Partly tracked:"])
    lines.extend(f"- `{item}`" for item in eli5["partly_tracked"][:10])
    lines.extend(["", "May need bringing forward:"])
    lines.extend(f"- `{item}`" for item in eli5["may_need_bring_forward"][:8])
    lines.extend(["", "Unsafe, old, or blocked:"])
    lines.extend(f"- `{item}`" for item in eli5["unsafe_old_or_blocked"][:8])
    lines.extend(["", "Needs Winship memory review:"])
    if eli5["needs_winship_memory_review"]:
        lines.extend(f"- {item}" for item in eli5["needs_winship_memory_review"])
    else:
        lines.append("- None flagged by this metadata pass.")
    lines.extend(["", "## Classification Counts"])
    for classification, count in payload["classification_counts"].items():
        lines.append(f"- `{classification}`: {count}")
    lines.extend(["", "## Recommended Next Lanes"])
    for item in payload["future_lane_recommendations"]:
        gate = item["post_preflight_batch_gate_evaluation"]
        lines.append(f"- `{item['lane_name']}`: gate `{gate['gate_status']}` - {item['why_next']}")
    lines.extend(["", "## Boundaries"])
    lines.extend(
        [
            "- Repo B remains reference-only.",
            "- No Repo B code was imported, executed, migrated, or activated.",
            "- No live send, browser, credential, approval execution, planner/builder automation, or security pass was enabled.",
        ]
    )
    return "\n".join(lines) + "\n"


@dataclass(frozen=True)
class RepoBRemainingCapabilityDeltaMapExportResult:
    schema_version: str
    json_path: str
    operator_path: str
    repo_b_present: bool
    inspected_path_count: int
    capability_count: int
    repo_b_code_executed: bool
    runtime_authority_added: bool
    send_or_submit_authority_added: bool


def export_repo_b_remaining_capability_delta_map(
    *,
    repo_a_root: str | Path = ROOT,
    repo_b_root: str | Path = DEFAULT_REPO_B_ROOT,
    baseline_json: str | Path = DEFAULT_BASELINE_PATH,
    export_root: str | Path = DEFAULT_EXPORT_ROOT,
    generated_at: str | None = None,
) -> RepoBRemainingCapabilityDeltaMapExportResult:
    root = Path(repo_a_root)
    out_dir = root / export_root
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = build_repo_b_remaining_capability_delta_map(
        repo_a_root=repo_a_root,
        repo_b_root=repo_b_root,
        baseline_json=baseline_json,
        generated_at=generated_at,
    )
    json_path = out_dir / JSON_EXPORT_NAME
    operator_path = out_dir / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(format_repo_b_remaining_capability_delta_map(payload), encoding="utf-8")
    return RepoBRemainingCapabilityDeltaMapExportResult(
        schema_version=SCHEMA_VERSION,
        json_path=_display_path(json_path),
        operator_path=_display_path(operator_path),
        repo_b_present=payload["repo_b_inspection"]["repo_b_present"],
        inspected_path_count=payload["repo_b_inspection"]["path_count"],
        capability_count=len(payload["capability_delta_list"]),
        repo_b_code_executed=payload["repo_b_code_executed"],
        runtime_authority_added=payload["runtime_authority_added"],
        send_or_submit_authority_added=payload["send_or_submit_authority_added"],
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export Repo B remaining capability delta map read-model.")
    parser.add_argument("--repo-a-root", default=str(ROOT), help="Repo A root.")
    parser.add_argument("--repo-b-root", default=str(DEFAULT_REPO_B_ROOT), help="Repo B reference root.")
    parser.add_argument("--baseline-json", default=str(DEFAULT_BASELINE_PATH), help="Repo A completion baseline JSON.")
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT), help="Generated read-model export root.")
    parser.add_argument("--format", choices=("json", "operator"), default="operator")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    result = export_repo_b_remaining_capability_delta_map(
        repo_a_root=args.repo_a_root,
        repo_b_root=args.repo_b_root,
        baseline_json=args.baseline_json,
        export_root=args.export_root,
    )
    if args.format == "json":
        print(stable_json(result.__dict__), end="")
    else:
        payload = build_repo_b_remaining_capability_delta_map(
            repo_a_root=args.repo_a_root,
            repo_b_root=args.repo_b_root,
            baseline_json=args.baseline_json,
        )
        print(format_repo_b_remaining_capability_delta_map(payload), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
