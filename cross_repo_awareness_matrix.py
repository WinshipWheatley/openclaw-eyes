"""Cross-repo awareness matrix v0.

This read-model shows what OpenClaw is aware of across Repo A and reference-only
Repo B. It classifies tagged/tracked Repo A rails, Repo B concepts already
represented in Repo A, Repo B safe path metadata that still appears untagged,
operator-memory-only items, blocked/unsafe surfaces, and unknowns.

It does not migrate code, execute Repo B, import Repo B modules, activate tools
or agents, inspect private raw content, access credentials/OAuth/browser/email/
calendar/Coupa, send messages, create approvals, or grant runtime authority.
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

from repo_b_remaining_capability_delta_map import (
    DEFAULT_REPO_B_ROOT,
    safe_repo_b_inventory,
)


ROOT = Path(__file__).resolve().parent
DEFAULT_EXPORT_ROOT = Path("generated/read_models")

SCHEMA_VERSION = "cross_repo_awareness_matrix_v0"
JSON_EXPORT_NAME = "cross_repo_awareness_matrix.json"
OPERATOR_EXPORT_NAME = "cross_repo_awareness_matrix_OPERATOR.md"
NEXT_RECOMMENDED_LANE = "Cassandra Draft Identity Reference Rail v0"

CLASSIFICATIONS = (
    "REPO_A_TRACKED",
    "REPO_A_PARTIALLY_TRACKED",
    "REPO_A_BLOCKED",
    "REPO_B_ALREADY_REPRESENTED",
    "REPO_B_PARTIALLY_REPRESENTED",
    "REPO_B_UNTAGGED",
    "REPO_B_UNSAFE_OR_BLOCKED",
    "REPO_B_OBSOLETE_OR_STALE",
    "OPERATOR_MEMORY_ONLY",
    "UNKNOWN_NEEDS_REVIEW",
)

NO_AUTHORITY_FLAGS = {
    "read_model_only": True,
    "classification_only": True,
    "repo_b_reference_only": True,
    "repo_b_reference_path_metadata_inspected": True,
    "repo_b_content_body_read": False,
    "repo_b_code_executed": False,
    "repo_b_modules_imported": False,
    "repo_b_code_migrated": False,
    "tools_activated": False,
    "agents_activated": False,
    "planner_builder_automation_activated": False,
    "repair_fix_loop_activated": False,
    "browser_automation_added": False,
    "oauth_or_credentials_accessed": False,
    "gmail_calendar_coupa_accessed": False,
    "email_send_triggered": False,
    "telegram_send_triggered": False,
    "approval_authority_added": False,
    "runtime_authority_added": False,
    "send_or_submit_authority_added": False,
    "mission_control_app_changed": False,
    "security_pass_started": False,
    "private_raw_content_inspected": False,
}


@dataclass(frozen=True)
class SourceReadModel:
    key: str
    path: str
    role: str


@dataclass(frozen=True)
class AwarenessSpec:
    matrix_item_id: str
    plain_name: str
    classification: str
    source_repo: str
    source_type: str
    path_or_read_model_refs: tuple[str, ...]
    what_openclaw_currently_knows: str
    what_is_missing: str
    safe_to_use_now: bool
    metadata_only: bool
    needs_winship_memory_review: bool
    should_be_brought_forward: bool
    suggested_next_lane: str
    authority_boundary: str


@dataclass(frozen=True)
class CrossRepoAwarenessMatrixExportResult:
    schema_version: str
    json_path: str
    operator_path: str
    matrix_item_count: int
    repo_b_untagged_count: int
    runtime_authority_added: bool
    send_or_submit_authority_added: bool


SOURCE_READ_MODELS = (
    SourceReadModel("repo_a_known_rail_completion_map", "generated/read_models/repo_a_known_rail_completion_map.json", "Repo A baseline rail completion map"),
    SourceReadModel("repo_b_remaining_capability_delta_map", "generated/read_models/repo_b_remaining_capability_delta_map.json", "Repo B remaining capability delta map"),
    SourceReadModel("capability_skill_registry_metadata_delta", "generated/read_models/capability_skill_registry_metadata_delta.json", "capability/skill metadata registry"),
    SourceReadModel("chief_role_capability_segmentation_map", "generated/read_models/chief_role_capability_segmentation_map.json", "Chief segmentation map"),
    SourceReadModel("chief_status_rail", "generated/read_models/chief_status_rail.json", "Chief status rail"),
    SourceReadModel("build_now_vs_hold_queue_posture", "generated/read_models/build_now_vs_hold_queue_posture.json", "build-now-vs-hold posture"),
    SourceReadModel("cassandra_email_calendar_delta_detangle", "generated/read_models/cassandra_email_calendar_delta_detangle.json", "Cassandra email/calendar detangle"),
    SourceReadModel("protected_access_broker_concept", "generated/read_models/protected_access_broker_concept.json", "protected access concept"),
    SourceReadModel("protected_evidence_reference_receipt", "generated/read_models/protected_evidence_reference_receipt.json", "protected evidence receipt"),
    SourceReadModel("guardian_protected_access_gate_spec", "generated/read_models/guardian_protected_access_gate_spec.json", "Guardian protected-access gate"),
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
        "repo_b_code_executed": False,
        "repo_b_modules_imported": False,
        "raw_private_content_read": False,
        "executed_or_dispatched": False,
    }


def _record(spec: AwarenessSpec) -> dict[str, Any]:
    if spec.classification not in CLASSIFICATIONS:
        raise ValueError(f"unknown awareness classification: {spec.classification}")
    return {
        "matrix_item_id": spec.matrix_item_id,
        "plain_name": spec.plain_name,
        "classification": spec.classification,
        "source_repo": spec.source_repo,
        "source_type": spec.source_type,
        "path_or_read_model_refs": list(spec.path_or_read_model_refs),
        "what_openclaw_currently_knows": spec.what_openclaw_currently_knows,
        "what_is_missing": spec.what_is_missing,
        "safe_to_use_now": spec.safe_to_use_now,
        "metadata_only": spec.metadata_only,
        "needs_winship_memory_review": spec.needs_winship_memory_review,
        "should_be_brought_forward": spec.should_be_brought_forward,
        "suggested_next_lane": spec.suggested_next_lane,
        "authority_boundary": spec.authority_boundary,
        "authority_added_now": False,
        "unknown_fails_closed": spec.classification == "UNKNOWN_NEEDS_REVIEW",
    }


def _base_specs() -> tuple[AwarenessSpec, ...]:
    return (
        AwarenessSpec(
            "capital_hilton_finance",
            "Capital Hilton / Cassandra-Clara finance",
            "REPO_A_TRACKED",
            "repo_a",
            "rail_read_model_contract_tests",
            (
                "generated/read_models/capital_hilton_actionable_review_packet.json",
                "generated/read_models/capital_hilton_external_artifact_proof_capture.json",
                "generated/read_models/capital_hilton_send_approval_gate.json",
            ),
            "Repo A has review packet, proof rail, approval-request gates, and protected evidence posture.",
            "Real proof references, approval receipts, and execution are not present.",
            True,
            True,
            False,
            False,
            "Cassandra Draft Identity Reference Rail v0",
            "visibility_review_proof_request_only_no_execution",
        ),
        AwarenessSpec(
            "cassandra_email_calendar",
            "Cassandra email/calendar/draft/Telegram detangle",
            "REPO_A_TRACKED",
            "repo_a",
            "read_model_contract_tests",
            (
                "generated/read_models/cassandra_email_calendar_delta_detangle.json",
                "generated/read_models/cassandra_draft_review_packet.json",
                "generated/read_models/guardian_draft_approval_request_contract.json",
            ),
            "Repo A distinguishes review packets, draft preview, Telegram notification separation, live Gmail blocks, calendar future work, and OAuth/credential blocks.",
            "Stable draft/attachment identity and approval receipts are not present.",
            True,
            True,
            False,
            False,
            "Cassandra Draft Identity Reference Rail v0",
            "review_visibility_only_no_gmail_calendar_send_or_telegram_change",
        ),
        AwarenessSpec(
            "guardian_protected_access",
            "Guardian approval/HITL/security/protected access",
            "REPO_A_TRACKED",
            "repo_a",
            "contract_read_model_tests",
            (
                "generated/read_models/guardian_protected_access_gate_spec.json",
                "generated/read_models/protected_access_broker_concept.json",
                "generated/read_models/protected_evidence_reference_receipt.json",
            ),
            "Repo A has Guardian request/receipt/execution separation and protected-access gate specs.",
            "Live protected access and approval execution remain absent.",
            True,
            True,
            False,
            False,
            "Guardian Approval Receipt Boundary v0",
            "gate_specs_only_no_access_or_execution",
        ),
        AwarenessSpec(
            "chief_work_packet_queue",
            "Chief listener/router/session/work packets/queue posture",
            "REPO_A_TRACKED",
            "repo_a",
            "status_read_model_work_packet_metadata",
            (
                "generated/read_models/chief_status_rail.json",
                "generated/read_models/build_now_vs_hold_queue_posture.json",
                "generated/read_models/work_board.json",
                "generated/read_models/agent_work_packets.json",
            ),
            "Repo A knows Chief as safe coordination/status/work-packet substrate, not executor authority.",
            "Listener/router/session runtime semantics are partially inferred and not live.",
            True,
            True,
            False,
            True,
            "Chief Domain Overlap Segmentation Review v0",
            "planning_visibility_only_no_runtime",
        ),
        AwarenessSpec(
            "brain_dump_cue_dropped_intent",
            "Brain-dump / cue parser / dropped intent",
            "REPO_A_TRACKED",
            "repo_a",
            "intent_read_model_metadata",
            (
                "generated/read_models/build_now_vs_hold_queue_posture.json",
                "generated/read_models/dropped_intents.json",
                "generated/read_models/intent_router.json",
            ),
            "Repo A tracks dropped-intent/build-now-vs-hold posture as visibility/routing metadata.",
            "A governed cue parser delta remains future work.",
            True,
            True,
            False,
            True,
            "Governed Cue Parser Delta v0",
            "intent_visibility_only_no_automation",
        ),
        AwarenessSpec(
            "niles_music_struna",
            "Niles/music/album/Struna",
            "REPO_A_TRACKED",
            "repo_a",
            "review_packet_metadata",
            (
                "generated/read_models/niles_album_review_packet.json",
                "generated/read_models/niles_album_metadata_intake_packet.json",
                "generated/read_models/struna_obscura_project_capsule.json",
            ),
            "Repo A has Niles/Struna project capsule and review packet metadata.",
            "Producer/runtime behavior and broader music lane completion are not live.",
            True,
            True,
            False,
            True,
            "Niles Struna Review Packet Rail v0",
            "review_metadata_only_no_producer_runtime",
        ),
        AwarenessSpec(
            "report_bridge_client_reporting",
            "Report Bridge/client reporting",
            "REPO_A_TRACKED",
            "repo_a",
            "read_model_capsule_metadata",
            (
                "generated/read_models/report_bridge.json",
                "generated/read_models/project_capsules.json",
                "generated/read_models/custom_build_module_detangling_contract.json",
            ),
            "Repo A has Report Bridge and client/project capsule metadata surfaces.",
            "Client deployment/reporting nodes remain future and blocked.",
            True,
            True,
            False,
            True,
            "Report Bridge Review Packet Rail v0",
            "visibility_only_no_customer_deployment",
        ),
        AwarenessSpec(
            "repo_b_website_custom_build",
            "Website/custom-build concepts",
            "REPO_B_PARTIALLY_REPRESENTED",
            "repo_b_and_repo_a",
            "reference_path_metadata_and_repo_a_contract",
            (
                "chief_website_coordinator.py",
                "chief_website_creative.py",
                "chief_website_qa.py",
                "generated/read_models/custom_build_module_detangling_contract.json",
            ),
            "Repo A has custom-build/module-detangling substrate; Repo B path metadata shows older website-focused Chief surfaces.",
            "No website execution/client build rail is proven or live.",
            True,
            True,
            False,
            True,
            "Website Custom Build Surface Delta v0",
            "metadata_only_no_client_repo_generation_or_deployment",
        ),
        AwarenessSpec(
            "repo_b_system_health_watchdog_watcher",
            "System health/watchdog/watcher concepts",
            "REPO_B_UNSAFE_OR_BLOCKED",
            "repo_b_and_repo_a",
            "reference_path_metadata_and_repo_a_guardrails",
            (
                "chief_watcher_brain.py",
                "cassandra_watcher.py",
                "loop_dashboard_watchdog.sh",
                "generated/read_models/active_machinery_high_risk_quarantine.json",
                "generated/read_models/operator_sovereignty_power_stage_gate.json",
            ),
            "OpenClaw is aware of old watcher/watchdog concepts and has current guardrail/quarantine read-models.",
            "No watcher or repair loop activation is allowed; system-health work must stay as read-model/status until security threshold.",
            False,
            True,
            False,
            False,
            "System Health Watcher Boundary Map v0",
            "known_but_not_allowed_to_run",
        ),
        AwarenessSpec(
            "tool_inventory_capability_registry",
            "Tool inventory/tool intake/capability registry",
            "REPO_A_TRACKED",
            "repo_a",
            "metadata_registry",
            (
                "generated/read_models/tool_inventory.json",
                "generated/read_models/tool_intake.json",
                "generated/read_models/capability_skill_registry_metadata_delta.json",
            ),
            "Repo A tracks tool/capability metadata without approval, integration, or activation.",
            "No tools are enabled by this metadata.",
            True,
            True,
            False,
            False,
            "Tool Candidate Review Packet v0",
            "metadata_only_no_tool_activation",
        ),
        AwarenessSpec(
            "operator_memory_calendar_merge_context",
            "Google/Apple calendar merge context",
            "OPERATOR_MEMORY_ONLY",
            "operator_memory",
            "operator_supplied_context",
            ("generated/read_models/cassandra_email_calendar_delta_detangle.json",),
            "Operator memory/context only: Google and Apple calendars are merged enough to work on iPhone, but Mac Calendar is confusing.",
            "No live calendar evidence or normalization proof exists.",
            False,
            True,
            True,
            False,
            "Calendar Source Normalization Packet v0",
            "memory_not_truth_no_calendar_access",
        ),
        AwarenessSpec(
            "hermes_advisory_status",
            "Hermes advisory synthesis",
            "REPO_A_PARTIALLY_TRACKED",
            "repo_a_operator_memory",
            "metadata_and_memory_gap",
            (
                "generated/read_models/repo_a_known_rail_completion_map.json",
                "generated/read_models/repo_b_remaining_capability_delta_map.json",
            ),
            "Repo A knows Hermes as metadata/reference, and Repo B delta flags Hermes status for memory review.",
            "No completed Hermes steel-thread rail is proven.",
            False,
            True,
            True,
            True,
            "Hermes Advisory Status Rail v0",
            "metadata_only_needs_memory_review",
        ),
        AwarenessSpec(
            "repo_b_oauth_browser_credential_bridges",
            "OAuth/browser/credential bridges",
            "REPO_B_UNSAFE_OR_BLOCKED",
            "repo_b",
            "reference_or_delta_metadata",
            (
                "generated/read_models/protected_access_broker_concept.json",
                "generated/read_models/guardian_protected_access_gate_spec.json",
                "generated/read_models/capability_skill_registry_metadata_delta.json",
            ),
            "OpenClaw knows old OAuth/browser/credential bridge ideas exist and has represented them as protected-access/security-threshold blocked.",
            "No safe live access design or authority exists.",
            False,
            True,
            False,
            False,
            "Protected Access Security Threshold Design v0",
            "known_but_not_allowed_to_run",
        ),
        AwarenessSpec(
            "unknown_unclassified_capability",
            "Unknown or unclassified capability",
            "UNKNOWN_NEEDS_REVIEW",
            "unknown",
            "fail_closed_placeholder",
            (),
            "Unknowns are represented as fail-closed gaps, not as usable capability.",
            "Needs a named classification lane and safe evidence source.",
            False,
            True,
            True,
            False,
            "Capability Classification Intake v0",
            "unknown_fails_closed",
        ),
    )


def _repo_b_delta_classification_to_matrix(classification: str) -> str:
    mapping = {
        "ALREADY_REPRESENTED_IN_REPO_A": "REPO_B_ALREADY_REPRESENTED",
        "PARTIALLY_REPRESENTED_IN_REPO_A": "REPO_B_PARTIALLY_REPRESENTED",
        "MISSING_FROM_REPO_A": "REPO_B_UNTAGGED",
        "SUPERSEDED_BY_REPO_A": "REPO_B_OBSOLETE_OR_STALE",
        "UNSAFE_OR_BLOCKED": "REPO_B_UNSAFE_OR_BLOCKED",
        "OBSOLETE_OR_STALE": "REPO_B_OBSOLETE_OR_STALE",
        "WORTH_BRINGING_FORWARD": "REPO_B_PARTIALLY_REPRESENTED",
        "UNKNOWN_NEEDS_OPERATOR_MEMORY_REVIEW": "UNKNOWN_NEEDS_REVIEW",
    }
    return mapping.get(classification, "UNKNOWN_NEEDS_REVIEW")


def _repo_b_item_id(capability_id: str) -> str:
    aliases = {
        "cassandra_core_listener_review": "repo_b_cassandra_listener_review",
        "cassandra_calendar_email_draft": "repo_b_cassandra_email_calendar",
        "chief_orchestrator_planner_status": "repo_b_chief_listener_router_session",
        "planner_builder_automation_loops": "repo_b_planner_builder_automation",
        "automatic_fix_repair_loops": "repo_b_automatic_repair_loops",
        "oauth_tool_browser_credential_bridges": "repo_b_oauth_browser_credential_bridges",
        "brain_dump_inbox_parser": "repo_b_brain_dump_cue_parser",
        "niles_music_producer_album": "repo_b_niles_music_album",
        "report_bridge_client_company_reporting": "repo_b_report_bridge_client_reporting",
        "demo_dashboard_mobile_sync": "repo_b_old_dashboard_mobile_demo_surfaces",
        "capability_skill_registry": "repo_b_capability_skill_registry",
        "claude_command_notes": "repo_b_claude_command_notes",
    }
    return aliases.get(capability_id, f"repo_b_{capability_id}")


def _delta_specs(repo_b_delta: dict[str, Any]) -> tuple[AwarenessSpec, ...]:
    specs: list[AwarenessSpec] = []
    for item in repo_b_delta.get("capability_delta_list", []):
        if not isinstance(item, dict):
            continue
        classification = _repo_b_delta_classification_to_matrix(str(item.get("classification") or ""))
        safe = classification in {"REPO_B_ALREADY_REPRESENTED", "REPO_B_PARTIALLY_REPRESENTED"}
        blocked = classification in {"REPO_B_UNSAFE_OR_BLOCKED", "REPO_B_OBSOLETE_OR_STALE"}
        needs_memory = classification == "UNKNOWN_NEEDS_REVIEW" or str(item.get("classification")) == "MISSING_FROM_REPO_A"
        refs = tuple(str(path) for path in item.get("repo_b_paths", []) if isinstance(path, str))
        repo_a_refs = tuple(
            str(ref.get("path"))
            for ref in item.get("repo_a_equivalent", [])
            if isinstance(ref, dict) and ref.get("path")
        )
        specs.append(
            AwarenessSpec(
                matrix_item_id=_repo_b_item_id(str(item.get("capability_id") or "unknown")),
                plain_name=str(item.get("capability_id") or "Unknown Repo B capability").replace("_", " "),
                classification=classification,
                source_repo="repo_b",
                source_type="reference_path_metadata_and_repo_a_delta",
                path_or_read_model_refs=refs + repo_a_refs,
                what_openclaw_currently_knows=str(item.get("short_description") or "Repo B delta classified this capability as reference metadata."),
                what_is_missing=str(item.get("why_or_why_not") or "Needs a bounded future lane before any promotion."),
                safe_to_use_now=safe and not blocked,
                metadata_only=True,
                needs_winship_memory_review=needs_memory,
                should_be_brought_forward=bool(item.get("should_bring_forward")) and not blocked,
                suggested_next_lane=str(item.get("suggested_future_lane") or "Operator Memory Review v0"),
                authority_boundary="known_but_not_allowed_to_run" if blocked else "reference_metadata_not_runtime_authority",
            )
        )
    return tuple(specs)


def _covered_repo_b_paths(repo_b_delta: dict[str, Any]) -> set[str]:
    covered: set[str] = set()
    for item in repo_b_delta.get("capability_delta_list", []):
        if not isinstance(item, dict):
            continue
        for path in item.get("repo_b_paths", []):
            if isinstance(path, str):
                covered.add(path)
    return covered


def _untagged_repo_b_paths(repo_b_inventory: dict[str, Any], repo_b_delta: dict[str, Any]) -> tuple[str, ...]:
    safe_paths = [str(path) for path in repo_b_inventory.get("safe_relative_paths", []) if isinstance(path, str)]
    covered = _covered_repo_b_paths(repo_b_delta)
    fixture_or_low_signal = ("tests/fixtures/",)
    untagged = [
        path
        for path in safe_paths
        if path not in covered and not path.startswith(fixture_or_low_signal)
    ]
    return tuple(sorted(untagged))


def _untagged_spec(untagged_paths: tuple[str, ...]) -> AwarenessSpec:
    sample = untagged_paths[:40]
    return AwarenessSpec(
        "repo_b_untagged_safe_path_inventory",
        "Repo B safe path metadata not clearly tagged",
        "REPO_B_UNTAGGED" if untagged_paths else "REPO_B_ALREADY_REPRESENTED",
        "repo_b",
        "safe_path_metadata_inventory",
        sample,
        f"Repo B safe path inventory has {len(untagged_paths)} path(s) not covered by the current Repo B delta capability patterns.",
        "Each path needs future classification before promotion; path names are metadata only and not proof of working capability.",
        False,
        True,
        bool(untagged_paths),
        False,
        "Repo B Untagged Safe Path Classification v0" if untagged_paths else "None",
        "path_metadata_only_no_code_execution",
    )


def _classification_counts(records: list[dict[str, Any]]) -> dict[str, int]:
    counts = Counter(record["classification"] for record in records)
    return {classification: counts.get(classification, 0) for classification in CLASSIFICATIONS}


def _awareness_answers(records: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "definitely_aware_of": [
            item["matrix_item_id"]
            for item in records
            if item["classification"] in {"REPO_A_TRACKED", "REPO_B_ALREADY_REPRESENTED", "REPO_A_PARTIALLY_TRACKED"}
        ],
        "repo_a_tagged_or_tracked": [
            item["matrix_item_id"]
            for item in records
            if item["classification"] in {"REPO_A_TRACKED", "REPO_A_PARTIALLY_TRACKED", "REPO_A_BLOCKED"}
        ],
        "repo_b_already_represented": [
            item["matrix_item_id"]
            for item in records
            if item["classification"] == "REPO_B_ALREADY_REPRESENTED"
        ],
        "repo_b_partially_represented": [
            item["matrix_item_id"]
            for item in records
            if item["classification"] == "REPO_B_PARTIALLY_REPRESENTED"
        ],
        "repo_b_untagged_or_unclear": [
            item["matrix_item_id"]
            for item in records
            if item["classification"] in {"REPO_B_UNTAGGED", "UNKNOWN_NEEDS_REVIEW"}
        ],
        "known_but_blocked": [
            item["matrix_item_id"]
            for item in records
            if item["classification"] in {"REPO_A_BLOCKED", "REPO_B_UNSAFE_OR_BLOCKED", "REPO_B_OBSOLETE_OR_STALE"}
        ],
        "operator_memory_only": [
            item["matrix_item_id"]
            for item in records
            if item["classification"] == "OPERATOR_MEMORY_ONLY"
        ],
        "needs_winship_memory_review": [
            item["matrix_item_id"]
            for item in records
            if item["needs_winship_memory_review"]
        ],
    }


def _aware_examples(records: list[dict[str, Any]], untagged_paths: tuple[str, ...]) -> dict[str, Any]:
    aware = [
        "Capital Hilton finance workflow",
        "Cassandra email/calendar review path",
        "Chief work packet / build-now-vs-hold posture",
        "Guardian protected-access gates",
        "Niles/Struna packet metadata",
    ]
    not_classified = list(untagged_paths[:5]) or ["No untagged Repo B safe paths found in this run."]
    return {
        "aware_of_examples": aware,
        "not_yet_aware_or_not_classified_examples": not_classified,
        "operator_memory_examples": ["Google/Apple calendar merge context", "Hermes status confidence"],
        "blocked_examples": ["planner/builder automation loops", "automatic repair loops", "OAuth/browser/credential bridges"],
    }


def _eli5(records: list[dict[str, Any]], untagged_paths: tuple[str, ...]) -> dict[str, Any]:
    answers = _awareness_answers(records)
    return {
        "what_openclaw_is_definitely_aware_of": (
            "OpenClaw is definitely aware of the Capital Hilton finance rail, Cassandra review/email-calendar posture, "
            "Guardian gates, Chief queue/work-packet posture, Niles/Struna, Report Bridge, tool/capability metadata, "
            "and protected-access boundaries."
        ),
        "what_repo_a_has_tagged": (
            f"Repo A has tagged {len(answers['repo_a_tagged_or_tracked'])} matrix item(s) as tracked or partially tracked."
        ),
        "what_repo_b_had_already_represented": (
            f"Repo B had {len(answers['repo_b_already_represented'])} item(s) already represented in Repo A and "
            f"{len(answers['repo_b_partially_represented'])} item(s) partially represented."
        ),
        "what_repo_b_still_has_that_may_not_be_tagged": (
            f"Repo B still has {len(untagged_paths)} safe path-metadata item(s) not clearly covered by current delta categories."
        ),
        "what_is_known_but_blocked": (
            "Planner/builder automation, repair loops, OAuth/browser/credential bridges, old dashboard/mobile/demo surfaces, "
            "and live email/calendar paths are known but blocked."
        ),
        "what_only_exists_as_winship_memory": (
            "Calendar merge/Mac Calendar confusion and Hermes certainty still need memory/evidence review before becoming truth."
        ),
        "what_needs_to_be_uncovered_next": (
            "Classify untagged Repo B safe paths, then complete narrow identity/reference rails before live authority work."
        ),
        "next_1_to_3_sensible_lanes": [
            "Cassandra Draft Identity Reference Rail v0",
            "Repo B Untagged Safe Path Classification v0",
            "Hermes Advisory Status Rail v0",
        ],
    }


def build_cross_repo_awareness_matrix(
    *,
    repo_root: str | Path = ROOT,
    repo_b_root: str | Path = DEFAULT_REPO_B_ROOT,
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
    repo_b_inventory = safe_repo_b_inventory(repo_b_root)
    repo_b_delta = sources["repo_b_remaining_capability_delta_map"]
    untagged_paths = _untagged_repo_b_paths(repo_b_inventory, repo_b_delta)
    specs = list(_base_specs()) + list(_delta_specs(repo_b_delta)) + [_untagged_spec(untagged_paths)]
    deduped: dict[str, dict[str, Any]] = {}
    for spec in specs:
        deduped.setdefault(spec.matrix_item_id, _record(spec))
    records = list(deduped.values())
    answers = _awareness_answers(records)
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_by": "codex",
        "generated_at": generated_at or utc_now(),
        "lane": "Cross-Repo Awareness Matrix v0",
        "matrix_status": "cross_repo_awareness_read_model_only",
        "definition": {
            "aware": "OpenClaw has a deterministic record/read-model/category for it.",
            "tagged_tracked_in_repo_a": "Repo A has code/read-model/test/metadata representing it.",
            "repo_b_represented": "Repo B concept has a Repo A equivalent, bridge, block, or metadata reference.",
            "repo_b_untagged": "Repo B safe path metadata appears without clear Repo A representation/classification.",
            "operator_memory_only": "Operator memory guidance exists, but repo evidence does not prove it yet.",
            "blocked_unsafe": "Known but not allowed to run or be treated as usable.",
        },
        "classification_labels": list(CLASSIFICATIONS),
        "classification_counts": _classification_counts(records),
        "matrix_item_count": len(records),
        "matrix_items": records,
        "awareness_answers": answers,
        "aware_of_x_not_y_examples": _aware_examples(records, untagged_paths),
        "repo_a_baselines_used": [
            "repo_a_known_rail_completion_map.json",
            "repo_b_remaining_capability_delta_map.json",
            "capability_skill_registry_metadata_delta.json",
            "chief_role_capability_segmentation_map.json",
            "chief_status_rail.json",
            "build_now_vs_hold_queue_posture.json",
            "cassandra_email_calendar_delta_detangle.json",
            "protected_access_broker_concept.json",
            "protected_evidence_reference_receipt.json",
            "guardian_protected_access_gate_spec.json",
        ],
        "repo_b_inspection_scope": {
            "repo_b_root": str(repo_b_root),
            "repo_b_present": bool(repo_b_inventory.get("repo_b_present")),
            "inspection_mode": "safe_path_metadata_only",
            "safe_path_count": int(repo_b_inventory.get("path_count", 0)),
            "skipped_sensitive_or_no_go_count": int(repo_b_inventory.get("skipped_sensitive_or_no_go_count", 0)),
            "untagged_safe_path_count": len(untagged_paths),
            "untagged_safe_path_sample": list(untagged_paths[:40]),
            "body_read": False,
            "repo_b_code_executed": False,
            "repo_b_modules_imported": False,
        },
        "source_read_models": source_records,
        "operator_eli5_summary": _eli5(records, untagged_paths),
        "no_authority_flags": dict(NO_AUTHORITY_FLAGS),
        **NO_AUTHORITY_FLAGS,
        "next_recommended_lane": NEXT_RECOMMENDED_LANE,
    }


def format_cross_repo_awareness_matrix(payload: dict[str, Any]) -> str:
    eli5 = payload["operator_eli5_summary"]
    lines = [
        "# Cross-Repo Awareness Matrix v0",
        "",
        "Status:",
        "- Matrix posture: read-model/classification only.",
        "- No Repo B code was executed, imported, migrated, or activated.",
        "- Repo B inspection scope: safe path metadata only; raw content body read: `false`.",
        "- Runtime/send/submit/tool/agent/browser/OAuth/credential authority added: `false`.",
        "",
        "## ELI5 Summary",
        f"- {eli5['what_openclaw_is_definitely_aware_of']}",
        f"- {eli5['what_repo_a_has_tagged']}",
        f"- {eli5['what_repo_b_had_already_represented']}",
        f"- {eli5['what_repo_b_still_has_that_may_not_be_tagged']}",
        f"- {eli5['what_is_known_but_blocked']}",
        f"- {eli5['what_only_exists_as_winship_memory']}",
        f"- {eli5['what_needs_to_be_uncovered_next']}",
        "",
        "## Classification Counts",
    ]
    for classification in CLASSIFICATIONS:
        lines.append(f"- `{classification}`: {payload['classification_counts'].get(classification, 0)}")
    lines.extend(["", "## Aware Of / Not Yet Classified Examples"])
    examples = payload["aware_of_x_not_y_examples"]
    lines.append("- Aware of: " + ", ".join(examples["aware_of_examples"]))
    lines.append("- Not yet classified: " + ", ".join(examples["not_yet_aware_or_not_classified_examples"][:8]))
    lines.append("- Operator memory: " + ", ".join(examples["operator_memory_examples"]))
    lines.append("- Known but blocked: " + ", ".join(examples["blocked_examples"]))
    lines.extend(["", "## Repo B Untagged Sample"])
    sample = payload["repo_b_inspection_scope"]["untagged_safe_path_sample"]
    if sample:
        lines.extend(f"- `{path}`" for path in sample[:20])
    else:
        lines.append("- None in this run.")
    lines.extend(["", "## Boundaries"])
    lines.extend(
        [
            "- Awareness does not mean execution authority.",
            "- Repo B safe path names are evidence to classify, not code to run.",
            "- Operator memory is not treated as proven system truth.",
            "- Unknowns fail closed.",
            "",
            f"Next safe lane: {payload['next_recommended_lane']}",
            "",
        ]
    )
    return "\n".join(lines)


def export_cross_repo_awareness_matrix(
    *,
    repo_root: str | Path = ROOT,
    repo_b_root: str | Path = DEFAULT_REPO_B_ROOT,
    export_root: str | Path = DEFAULT_EXPORT_ROOT,
    generated_at: str | None = None,
) -> CrossRepoAwarenessMatrixExportResult:
    root = Path(repo_root)
    out_dir = _rooted(export_root, repo_root=root)
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = build_cross_repo_awareness_matrix(
        repo_root=root,
        repo_b_root=repo_b_root,
        generated_at=generated_at,
    )
    json_path = out_dir / JSON_EXPORT_NAME
    operator_path = out_dir / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(format_cross_repo_awareness_matrix(payload), encoding="utf-8")
    return CrossRepoAwarenessMatrixExportResult(
        schema_version=SCHEMA_VERSION,
        json_path=_display_path(json_path),
        operator_path=_display_path(operator_path),
        matrix_item_count=len(payload["matrix_items"]),
        repo_b_untagged_count=payload["repo_b_inspection_scope"]["untagged_safe_path_count"],
        runtime_authority_added=payload["runtime_authority_added"],
        send_or_submit_authority_added=payload["send_or_submit_authority_added"],
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export cross-repo awareness matrix read-model.")
    parser.add_argument("--repo-root", default=str(ROOT), help="Repo A root.")
    parser.add_argument("--repo-b-root", default=str(DEFAULT_REPO_B_ROOT), help="Repo B reference-only root.")
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT), help="Generated read-model export root.")
    parser.add_argument("--format", choices=("json", "operator", "summary"), default="summary")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    result = export_cross_repo_awareness_matrix(
        repo_root=args.repo_root,
        repo_b_root=args.repo_b_root,
        export_root=args.export_root,
    )
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
    "build_cross_repo_awareness_matrix",
    "export_cross_repo_awareness_matrix",
    "format_cross_repo_awareness_matrix",
    "stable_json",
]


if __name__ == "__main__":
    raise SystemExit(main())
