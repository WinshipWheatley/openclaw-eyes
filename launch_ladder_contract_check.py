#!/usr/bin/env python3
"""Static contract checker for the Launch Ladder planning package.

This is a docs/test-only helper. It reads Markdown contracts and reports missing
product-contract language; it does not inspect runtime state or generated ingest
folders.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
import sys


REPO_ROOT = Path(__file__).resolve().parent
LAUNCH_LADDER_DIR = REPO_ROOT / "docs" / "planning" / "launch_ladder"
MODULAR_LEDGER = REPO_ROOT / "docs" / "planning" / "OPENCLAW_MODULAR_READINESS_LEDGER.md"
VALIDATION_MAP = REPO_ROOT / "docs" / "testing" / "VALIDATION_MAP.md"
SYNC_OPERATOR_HARNESS = (
    REPO_ROOT / "mac_eyes" / "Launchers" / "sync_operator_harness_to_mac.sh"
)
REFRESH_OPERATOR_HARNESS = (
    REPO_ROOT / "mac_eyes" / "Launchers" / "refresh_operator_harness_ingest.sh"
)

ACTIVE_SOURCE_SET = "CHATGPT_PROJECT_INGEST_OPERATOR_HARNESS/02_MAC_IOS_APP_BUILD"
UPLOAD_AUTHORITY_COMMIT = "df52ff4687d7dd8a32990658d557cb2b4d1371d9"
MISSION_CONTROL_APP_SURFACE = "mac_desktop_mission_control_read_only"
MISSION_CONTROL_SOURCE_SET_BASELINE = "02_MAC_IOS_APP_BUILD"
MISSION_CONTROL_FIXTURE_DIR = (
    LAUNCH_LADDER_DIR / "fixtures" / "mission_control"
)
REQUIRED_MISSION_CONTROL_FIXTURES = (
    "fixture_fresh_navigation_profile.json",
    "fixture_malformed_executable_profile.json",
    "fixture_packet_available_not_approved.json",
    "fixture_approval_receipt_valid.json",
    "fixture_approval_receipt_expired.json",
    "fixture_stale_evidence_route.json",
    "fixture_blocked_missing_authority.json",
    "fixture_ui_claim_without_evidence.json",
    "fixture_operator_experience_golden_overview.json",
)
MISSION_CONTROL_UI_STATES = (
    "profile_available",
    "packet_available",
    "launch_ready",
    "approved",
    "executed",
    "succeeded",
    "stale",
    "blocked",
    "unknown",
)
MISSION_CONTROL_REQUIRED_HARD_BOUNDARIES = (
    "no_swiftui_appkit_implementation",
    "no_backend_api_schema_implementation",
    "no_runtime_calls",
    "no_service_control",
    "no_provider_model_calls",
    "no_gmail_telegram_actions",
    "no_hermes_runtime_expansion",
    "no_private_data_vault_log_legalprivate_secrets_inspection",
    "no_approval_mutation_guardian_control",
    "no_app_execution",
)


@dataclass(frozen=True)
class ContractCorpus:
    launch_ladder_text: str
    ledger_text: str
    validation_map_text: str
    script_text: str

    @property
    def combined_text(self) -> str:
        return "\n".join(
            [
                self.launch_ladder_text,
                self.ledger_text,
                self.validation_map_text,
                self.script_text,
            ]
        )


@dataclass(frozen=True)
class StaticContractReport:
    failures: tuple[str, ...]
    warnings: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.failures


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def load_corpus(repo_root: Path = REPO_ROOT) -> ContractCorpus:
    launch_dir = repo_root / "docs" / "planning" / "launch_ladder"
    launch_docs = sorted(launch_dir.glob("*.md"))
    launch_text = "\n\n".join(_read_text(path) for path in launch_docs)
    ledger_text = _read_text(
        repo_root / "docs" / "planning" / "OPENCLAW_MODULAR_READINESS_LEDGER.md"
    )
    validation_map_text = _read_text(
        repo_root / "docs" / "testing" / "VALIDATION_MAP.md"
    )
    script_text = "\n\n".join(
        _read_text(path)
        for path in (
            repo_root / "mac_eyes" / "Launchers" / "sync_operator_harness_to_mac.sh",
            repo_root / "mac_eyes" / "Launchers" / "refresh_operator_harness_ingest.sh",
        )
    )
    return ContractCorpus(
        launch_ladder_text=launch_text,
        ledger_text=ledger_text,
        validation_map_text=validation_map_text,
        script_text=script_text,
    )


def normalize(text: str) -> str:
    lowered = text.lower().replace("'", "")
    flattened = re.sub(r"[^a-z0-9]+", " ", lowered)
    return re.sub(r"\s+", " ", flattened).strip()


def _contains(haystack: str, needle: str) -> bool:
    return normalize(needle) in haystack


def _require_all(
    failures: list[str], normalized_text: str, section: str, terms: tuple[str, ...]
) -> None:
    missing = [term for term in terms if not _contains(normalized_text, term)]
    if missing:
        failures.append(f"{section}: missing {', '.join(missing)}")


def _require_any(
    failures: list[str],
    normalized_text: str,
    section: str,
    variants: tuple[str, ...],
) -> None:
    if not any(_contains(normalized_text, variant) for variant in variants):
        failures.append(f"{section}: missing one of {', '.join(variants)}")


def _fixture_dir(repo_root: Path = REPO_ROOT) -> Path:
    return repo_root / "docs" / "planning" / "launch_ladder" / "fixtures" / "mission_control"


def load_mission_control_fixtures(repo_root: Path = REPO_ROOT) -> dict[str, dict]:
    fixture_dir = _fixture_dir(repo_root)
    fixtures: dict[str, dict] = {}
    for filename in REQUIRED_MISSION_CONTROL_FIXTURES:
        path = fixture_dir / filename
        fixtures[filename] = json.loads(_read_text(path))
    return fixtures


def _profile_contains_executable_command_field(profile: object) -> bool:
    if not isinstance(profile, dict):
        return False
    return any("executable" in key or key in {"execution_commands", "commands"} for key in profile)


def _navigation_actions_are_clean(profile: dict) -> bool:
    actions = profile.get("allowed_navigation_actions", [])
    if not isinstance(actions, list):
        return False
    forbidden_fragments = ("run", "sync", "commit", "push", "service", "provider", "model", "execute")
    return not any(
        fragment in str(action).lower()
        for action in actions
        for fragment in forbidden_fragments
    )


def mission_control_fixture_failures(repo_root: Path = REPO_ROOT) -> tuple[str, ...]:
    failures: list[str] = []
    fixture_dir = _fixture_dir(repo_root)
    loaded: dict[str, dict] = {}

    for filename in REQUIRED_MISSION_CONTROL_FIXTURES:
        path = fixture_dir / filename
        if not path.is_file():
            failures.append(f"mission control fixtures: missing {path}")
            continue
        try:
            loaded[filename] = json.loads(_read_text(path))
        except json.JSONDecodeError as exc:
            failures.append(f"mission control fixtures: invalid JSON in {path}: {exc}")

    for filename, fixture in loaded.items():
        section = f"mission control fixture {filename}"
        expected_id = filename.removesuffix(".json")
        if fixture.get("fixture_id") != expected_id:
            failures.append(f"{section}: fixture_id must be {expected_id}")
        if fixture.get("app_surface") != MISSION_CONTROL_APP_SURFACE:
            failures.append(f"{section}: app_surface must be {MISSION_CONTROL_APP_SURFACE}")
        if fixture.get("source_set_baseline") != MISSION_CONTROL_SOURCE_SET_BASELINE:
            failures.append(
                f"{section}: source_set_baseline must be {MISSION_CONTROL_SOURCE_SET_BASELINE}"
            )
        if fixture.get("source_manifest_commit") != UPLOAD_AUTHORITY_COMMIT:
            failures.append(f"{section}: source_manifest_commit must be {UPLOAD_AUTHORITY_COMMIT}")
        if fixture.get("ui_state") not in MISSION_CONTROL_UI_STATES:
            failures.append(f"{section}: ui_state must be one of {', '.join(MISSION_CONTROL_UI_STATES)}")

        expected_validation = fixture.get("expected_validation")
        if not isinstance(expected_validation, dict):
            failures.append(f"{section}: expected_validation must be an object")
            continue
        if expected_validation.get("expected_ui_state") != fixture.get("ui_state"):
            failures.append(f"{section}: expected_ui_state must match ui_state")
        if expected_validation.get("app_can_execute") is True:
            failures.append(f"{section}: read-only Mission Control fixture cannot set app_can_execute true")

        hard_boundaries = fixture.get("hard_boundaries")
        if not isinstance(hard_boundaries, dict):
            failures.append(f"{section}: hard_boundaries must be an object")
        else:
            missing_boundaries = [
                boundary
                for boundary in MISSION_CONTROL_REQUIRED_HARD_BOUNDARIES
                if hard_boundaries.get(boundary) is not True
            ]
            if missing_boundaries:
                failures.append(f"{section}: missing true hard boundaries {', '.join(missing_boundaries)}")

        freshness = fixture.get("freshness")
        if not isinstance(freshness, dict):
            failures.append(f"{section}: freshness must be an object")
        else:
            for key in ("source_basis", "generated_at", "reviewed_at", "stale_conditions", "refresh_trigger"):
                if not freshness.get(key):
                    failures.append(f"{section}: freshness missing {key}")
            if expected_validation.get("fixture_valid") is True and freshness.get("source_commit") != UPLOAD_AUTHORITY_COMMIT:
                failures.append(f"{section}: valid fixtures must carry source_commit {UPLOAD_AUTHORITY_COMMIT}")

        evidence_refs = fixture.get("evidence_refs")
        if expected_validation.get("fixture_valid") is True and not evidence_refs:
            failures.append(f"{section}: valid fixtures must include evidence_refs")

        fixture_type = fixture.get("fixture_type")
        if fixture_type == "workspace_launch_profile":
            profile = fixture.get("profile")
            if not isinstance(profile, dict):
                failures.append(f"{section}: workspace fixture missing profile object")
            else:
                contains_exec = _profile_contains_executable_command_field(profile)
                if filename == "fixture_malformed_executable_profile.json":
                    if expected_validation.get("fixture_valid") is not False:
                        failures.append(f"{section}: malformed profile must be expected invalid")
                    if not contains_exec:
                        failures.append(f"{section}: malformed profile must contain a forbidden executable field")
                    if "reason_invalid" not in expected_validation:
                        failures.append(f"{section}: malformed profile must state reason_invalid")
                else:
                    if contains_exec:
                        failures.append(f"{section}: valid profile must not contain executable fields")
                    if not profile.get("required_next_launch_packet_for_execution"):
                        failures.append(f"{section}: profile missing required_next_launch_packet_for_execution")
                    if not _navigation_actions_are_clean(profile):
                        failures.append(f"{section}: profile navigation actions contain execution-looking terms")

        if filename == "fixture_packet_available_not_approved.json":
            packet = fixture.get("launch_packet", {})
            if packet.get("approval_receipt_or_operator_decision") is not None:
                failures.append(f"{section}: packet_available fixture must not include approval")
            if expected_validation.get("authorizes_execution") is not False:
                failures.append(f"{section}: packet_available fixture must not authorize execution")
            if expected_validation.get("must_display_for_review_only") is not True:
                failures.append(f"{section}: packet_available fixture must be review-only")

        if filename == "fixture_approval_receipt_valid.json":
            receipt = fixture.get("approval_receipt", {})
            required_receipt_fields = (
                "receipt_id",
                "launch_packet_id",
                "approved_by_operator",
                "approved_at",
                "approved_scope",
                "approved_action",
                "evidence_snapshot",
                "freshness_snapshot",
                "expiry",
                "replay_policy",
                "consumed_state",
                "lifecycle_state",
                "execution_result_reference",
                "revocation_state",
                "forbidden_scope_expansion",
            )
            missing = [field for field in required_receipt_fields if field not in receipt]
            if missing:
                failures.append(f"{section}: missing receipt fields {', '.join(missing)}")
            if receipt.get("expiry", {}).get("expired_state") is not False:
                failures.append(f"{section}: valid receipt fixture must not be expired")
            if expected_validation.get("authorizes_one_named_packet_action_scope") is not True:
                failures.append(f"{section}: valid receipt must bind one packet/action/scope")

        if filename == "fixture_approval_receipt_expired.json":
            receipt = fixture.get("approval_receipt", {})
            if receipt.get("expiry", {}).get("expired_state") is not True:
                failures.append(f"{section}: expired receipt must set expired_state true")
            if expected_validation.get("authorizes_execution") is not False:
                failures.append(f"{section}: expired receipt must not authorize execution")
            if expected_validation.get("must_display_expired_reason") is not True:
                failures.append(f"{section}: expired receipt must require visible reason")

        if filename == "fixture_stale_evidence_route.json":
            if fixture.get("freshness", {}).get("state") != "stale":
                failures.append(f"{section}: stale route must set freshness.state stale")
            route = fixture.get("launch_route", {})
            if route.get("launch_ready_claim_allowed") is not False:
                failures.append(f"{section}: stale route must block launch-ready claim")
            if expected_validation.get("must_display_stale_reason") is not True:
                failures.append(f"{section}: stale route must display stale reason")

        if filename == "fixture_blocked_missing_authority.json":
            route = fixture.get("launch_route", {})
            if not route.get("blocked_reason"):
                failures.append(f"{section}: blocked route missing blocked_reason")
            if route.get("launch_authorized_claim_allowed") is not False:
                failures.append(f"{section}: missing authority must block launch-authorized claim")
            if expected_validation.get("must_distinguish_launch_ready_from_launch_authorized") is not True:
                failures.append(f"{section}: must distinguish launch-ready from launch-authorized")

        if filename == "fixture_ui_claim_without_evidence.json":
            ui_claim = fixture.get("ui_claim", {})
            claimed_states = set(ui_claim.get("claimed_states", []))
            proof_claims = {"healthy", "current", "tested", "running", "synced"}
            if not claimed_states.intersection(proof_claims):
                failures.append(f"{section}: malformed UI claim must include proof-demanding states")
            if ui_claim.get("source_commit") is not None or ui_claim.get("artifact") is not None or ui_claim.get("evidence_refs"):
                failures.append(f"{section}: negative UI claim must lack source commit, artifact, and evidence")
            if expected_validation.get("fixture_valid") is not False:
                failures.append(f"{section}: UI claim without evidence must be expected invalid")
            if expected_validation.get("must_not_soften_unknown_into_confidence") is not True:
                failures.append(f"{section}: unknown must not soften into confidence")

        if filename == "fixture_operator_experience_golden_overview.json":
            overview = fixture.get("overview", {})
            taste_eval = overview.get("taste_eval", {})
            required_taste_flags = (
                "operator_can_orient_within_seconds",
                "authority_boundaries_visually_obvious",
                "status_copy_exact_and_evidence_backed",
                "calm_sparse_premium_controlled",
                "rejects_fake_intelligence",
                "rejects_chatbot_slop",
                "rejects_generic_admin_panel_energy",
            )
            missing_taste = [flag for flag in required_taste_flags if taste_eval.get(flag) is not True]
            if missing_taste:
                failures.append(f"{section}: missing true taste flags {', '.join(missing_taste)}")
            for visible in ("north_star", "current_route", "authority", "freshness", "evidence", "next_safe_action"):
                if visible not in overview.get("visible_sections", []):
                    failures.append(f"{section}: golden overview must expose {visible}")

    return tuple(failures)


def freshness_warnings(corpus: ContractCorpus) -> tuple[str, ...]:
    warnings: list[str] = []
    launch_text = corpus.launch_ladder_text
    internal_commits = sorted(
        set(re.findall(r"Source commit at creation:\s*`([^`]+)`", launch_text))
    )
    package_markers = sorted(
        set(re.findall(r"Package commit:\s*`([^`]+)`", launch_text))
    )
    older_internal_commits = [
        commit for commit in internal_commits if commit != UPLOAD_AUTHORITY_COMMIT
    ]
    stale_markers = older_internal_commits + [
        marker for marker in package_markers if marker == "TBD_AFTER_COMMIT"
    ]
    if stale_markers:
        warnings.append(
            "Freshness normalization TODO: "
            f"the generated MANIFEST.md for {ACTIVE_SOURCE_SET} is "
            f"upload authority and reports source commit {UPLOAD_AUTHORITY_COMMIT}; "
            "canonical Launch Ladder docs still contain package-level freshness "
            f"markers: {', '.join(stale_markers)}. Treat the manifest as source-set "
            "authority and the doc markers as package-level review metadata until "
            "a docs-only freshness normalization pass updates them."
        )

    return tuple(warnings)


def check_contract(corpus: ContractCorpus | None = None) -> StaticContractReport:
    corpus = corpus or load_corpus()
    launch = normalize(corpus.launch_ladder_text)
    combined = normalize(corpus.combined_text)
    validation_map = normalize(corpus.validation_map_text)
    scripts = normalize(corpus.script_text)
    failures: list[str] = []

    _require_all(
        failures,
        launch,
        "launch authorization separation",
        ("launch-ready is not launch-authorized",),
    )

    _require_all(
        failures,
        launch,
        "seven ladder stages",
        (
            "recommendation",
            "planned slice",
            "source set ready",
            "build ready",
            "validation ready",
            "launch ready",
            "launch authorized",
        ),
    )

    _require_all(
        failures,
        launch,
        "route compression fields",
        (
            "Direct Route",
            "Balanced Route",
            "System Route",
            "steps_to_launch",
            "estimated_true_steps",
            "includes",
            "defers",
            "risk",
            "confidence",
            "freshness",
        ),
    )

    _require_all(
        failures,
        launch,
        "ladder compact button fields",
        (
            "label",
            "resulting_step_count",
            "estimated_true_steps",
            "deferred_work_summary",
            "authority_required",
            "stop_condition",
            "evidence_output",
        ),
    )

    _require_all(
        failures,
        launch,
        "parallel step bundle requirements",
        (
            "Parallel Step Bundles",
            "independent lanes",
            "File/workspace collision matrix",
            "Validation commands per lane",
            "Commit boundaries per lane",
            "Stop conditions per lane",
        ),
    )

    _require_all(
        failures,
        launch,
        "view modes",
        ("Bird's Eye", "Route View", "Step View"),
    )

    _require_all(
        failures,
        launch,
        "evidence and freshness fields",
        (
            "source basis",
            "generated/reviewed",
            "source commit",
            "stale conditions",
            "refresh trigger",
        ),
    )

    _require_all(
        failures,
        launch,
        "source-set manifest authority",
        (
            "canonical Launch Ladder docs may contain package-level review/freshness fields",
            "MANIFEST.md is the upload authority",
            "use MANIFEST.md for the uploaded source set",
            "Do not hardcode fast-changing source-set commits across canonical docs",
        ),
    )

    _require_all(
        failures,
        launch,
        "source-set upload rule",
        ("23 content files + MANIFEST.md = 24 total upload files",),
    )

    _require_all(
        failures,
        launch,
        "source-set ladder and delta bridge",
        (
            "Source-Set Ladder",
            "01_CURRENT_PRODUCT_SPEC",
            "02_MAC_IOS_APP_BUILD",
            "03_BACKEND_AND_DATA_MODEL",
            UPLOAD_AUTHORITY_COMMIT,
            "source-set folders are not Launch Ladder steps",
            "When folder 01 is exhausted, move to folder 02",
            "When folder 02 is exhausted, move to folder 03",
            "By folder 03, the system should already propose what folder 04 should contain",
            "CHAT_STAY_UP_TO_DATE.md",
            "not counted in the 24 files",
            "bridge-only upload",
            "full 24-file refresh",
            "current source-set folder",
            "latest repo changes since upload",
            "next likely source-set folder",
            "openclaw_audit_build_readiness",
            "law_program",
            "later lanes",
            "prototype wording only",
        ),
    )

    _require_all(
        failures,
        launch,
        "workspace launch profiles",
        (
            "Workspace Launch Profile",
            "named, evidence-backed view/navigation route",
            "opens the right machine, folder, workspace, files, tabs, and optional prompt only",
            "does not imply permission to mutate repo/runtime state",
            "Opening VS Code/workspace/files is safe navigation",
            "Any execution must be a separate Launch Packet / Launch Ladder action",
            "profile_id",
            "display_name",
            "purpose",
            "owner_lane or domain",
            "target_machine or context",
            "target_root or path",
            "workspace_file or workspace_hint",
            "recommended_files or tabs",
            "optional_prompt_path or prompt_hint",
            "evidence_sources",
            "freshness_fields",
            "allowed_navigation_actions",
            "explicitly_forbidden_execution_actions",
            "required_next_launch_packet_for_execution",
            "tests, sync, commits, service commands, provider/model calls, app execution, runtime mutation, private-data inspection, secrets, logs, vault access, Gmail/Telegram behavior, Hermes runtime expansion, LegalPrivate work, or installed-unit checks",
            "pc_wsl_repo_view",
            "mac_upload_prep_view",
            "mac_desktop_app_planning_view",
            "legal_visual_polish_view",
            "audit_runtime_review_view",
            "hermes_advisory_packet_view",
        ),
    )

    _require_all(
        failures,
        launch,
        "workspace profile to launch packet handoff",
        (
            "Workspace Profile To Launch Packet Handoff",
            "profile-to-packet handoff is explicit and one-way",
            "Workspace Launch Profile opens context only",
            "The profile may point to required_next_launch_packet_for_execution",
            "Launch Packet authorizes a bounded next action",
            "evidence/freshness, operator-readable scope, validation, authority, and stop conditions",
            "Workspace Launch Profile must not contain executable commands",
            "silently authorize them",
            "tests, sync, commit, service command, provider/model call, runtime mutation, app execution, private-data inspection, launcher action",
            "handoff_reason",
            "handoff_evidence_sources",
            "handoff_freshness_fields",
            "handoff_operator_readable_scope",
            "operator_harness_refresh_packet",
            "executable_commands",
            "reason_invalid",
            "A Workspace Launch Profile with executable commands is invalid",
        ),
    )

    _require_all(
        failures,
        launch,
        "launch packet minimum fields",
        (
            "A Launch Packet is the separate execution-authorizing object for one bounded next action",
            "Opening a Workspace Launch Profile never creates, approves, or executes a Launch Packet",
            "packet_id",
            "source_profile_id",
            "bounded_next_action",
            "target_machine",
            "target_workspace",
            "operator_readable_scope",
            "execution_commands or execution_plan",
            "validation_commands",
            "withheld_surfaces",
            "approval_receipt_or_operator_decision",
            "The packet authorizes only the named bounded next action",
        ),
    )

    _require_all(
        failures,
        launch,
        "approval receipt primitive",
        (
            "Action Authorization / Approval Receipt",
            "Launch Packet exists does not equal approved",
            "Approval Receipt records explicit operator authorization",
            "Approval Receipt binds to one Launch Packet/action/scope",
            "visible evidence/freshness state at approval time",
            "expiry/replay rules",
            "consumed_state",
            "permitted",
            "executed",
            "succeeded",
            "failed",
            "expired",
            "revoked",
            "operator-readable",
            "must not broaden the Launch Packet scope",
            "receipt_id",
            "launch_packet_id",
            "approved_by_operator",
            "approved_at",
            "approved_scope",
            "evidence_snapshot",
            "freshness_snapshot",
            "expiry",
            "replay_policy",
            "execution_result_reference",
            "revocation_state",
            "forbidden_scope_expansion",
            "invalid_broadened_receipt",
            "Approval Receipt cannot broaden the Launch Packet scope",
        ),
    )

    _require_all(
        failures,
        launch,
        "ui state claim rules",
        (
            "UI State Claim Rules",
            "Profile available does not mean packet available",
            "Packet available does not mean approved",
            "Approved does not mean executed",
            "Executed does not mean succeeded",
            "Current/fresh requires evidence/freshness proof",
            "Synced/tested/healthy/running cannot be shown unless backed by explicit evidence",
            "configured vs observed",
            "requested vs approved",
            "approved vs executed",
            "executed vs succeeded",
            "current vs stale",
            "Convenience must not collapse navigation, approval, and execution into one hidden action",
            "Opening a Workspace Launch Profile must not auto-approve, auto-run, or auto-consume a Launch Packet",
            "invalid_tests_passed_without_evidence",
            "UI state claim says tests passed without evidence",
            "invalid_profile_open_auto_approves_and_runs",
            "silently approves/runs a packet",
        ),
    )

    _require_all(
        failures,
        launch,
        "product taste operator experience eval spine",
        (
            "Product Taste / Operator Experience Eval Spine",
            "Taste is not decorative polish",
            "operator trust, calm control, clear authority hierarchy, legible evidence, sparse high-confidence actions, and zero fake intelligence",
            "operator can orient within a few seconds",
            "authority boundaries are visually obvious",
            "highest-risk actions cannot be confused with navigation",
            "status copy is exact and evidence-backed",
            "calm, sparse, premium, and controlled",
            "F-22 cockpit discipline",
            "Bugatti material confidence",
            "SpaceX mission-control clarity",
            "high-end music studio ergonomics",
            "Apple-level restraint",
            "fake-futuristic AI slop",
            "generic SaaS admin dashboard",
            "vague chatbot panels",
            "Visual clutter",
            "Vague agent status",
            "Fake intelligence language",
            "Scary controls with unclear blast radius",
            "Hidden authority or hidden execution",
            "Dead generic admin-panel energy",
            "Unclear state hierarchy",
            "Chatbot slop",
            "Over-automation",
            "Evidence buried too deeply",
            "copy/state-language checks",
            "cockpit/instrument hierarchy checks",
            "action safety visibility checks",
            "density/calmness checks",
            "evidence visibility checks",
            "operator trust checks",
            "anti-slop checks",
            "accessibility/legibility checks",
            "golden_calm_mission_control_overview",
            "golden_navigation_only_workspace_card",
            "golden_bounded_packet_card",
            "golden_approval_receipt_card",
            "golden_stale_evidence_warning",
            "golden_blocked_action_with_clear_reason",
            "golden_ready_but_not_approved_action",
            "golden_fresh_evidence_backed_status",
            "invalid_chatbot_i_handled_it_state",
            "invalid_glowing_ai_brain_panel",
            "invalid_one_click_hides_approval",
            "invalid_tests_passed_without_evidence",
            "invalid_healthy_running_without_observation",
            "invalid_dense_admin_table_no_next_action",
            "invalid_profile_card_matches_execution_action",
            "invalid_fake_urgency_or_confidence",
            "app planning source set must preserve this eval spine before implementation",
        ),
    )

    _require_all(
        failures,
        launch,
        "mac desktop mission control fixture contract",
        (
            "Mac Desktop Mission Control Fixture Contract",
            "docs/planning/launch_ladder/fixtures/mission_control",
            "fixture_fresh_navigation_profile.json",
            "fixture_malformed_executable_profile.json",
            "fixture_packet_available_not_approved.json",
            "fixture_approval_receipt_valid.json",
            "fixture_approval_receipt_expired.json",
            "fixture_stale_evidence_route.json",
            "fixture_blocked_missing_authority.json",
            "fixture_ui_claim_without_evidence.json",
            "fixture_operator_experience_golden_overview.json",
            "profile_available",
            "packet_available",
            "launch_ready",
            "approved",
            "executed",
            "succeeded",
            "stale",
            "blocked",
            "unknown",
            "navigation context exists only",
            "bounded action object exists for review only",
            "Approval Receipt permits one named packet/action/scope only",
            "execution result plus validation evidence",
            "do not soften this into confidence",
            "must not collapse profile, packet, approval, execution, and result",
            "Product Taste / Operator Experience Evals must reject AI slop",
            "All nine required fixture files exist and parse as JSON",
            "Workspace Launch Profiles with executable command fields are invalid",
            "Expired receipts cannot authorize execution",
            "healthy, current, tested, running, or synced without evidence are invalid",
        ),
    )

    _require_all(
        failures,
        launch,
        "current source-set posture",
        (
            "active app-planning posture is 02_MAC_IOS_APP_BUILD",
            "read-only Mac desktop Mission Control fixture contract stays in 02_MAC_IOS_APP_BUILD",
            "does not move the active ChatGPT Project source-set posture to 03_BACKEND_AND_DATA_MODEL",
            "does not create source-set folder 04",
            "does not create generated source-set scripts",
            "does not edit generated source-set folders",
            "does not start app/backend/runtime implementation",
        ),
    )

    _require_all(
        failures,
        launch,
        "apple platform clarification",
        (
            "Mac/iOS is Apple-platform planning shorthand",
            "Mac desktop app first",
            "iOS companion later",
            "Do not read this brief as iOS-first implementation",
        ),
    )

    _require_all(
        failures,
        launch,
        "prototype bridge retirement",
        (
            "real bridge is this repo-side template",
            "~/OpenClaw_Watch/operator_harness_readiness/CHAT_STAY_UP_TO_DATE.md",
            "/Users/hwinshipwheatley/OpenClaw_Watch/.claude/Chat_Stay Up To Date.md",
            "prototype/example only",
            "not canonical",
            "explicit Mac cleanup step",
            "deletes it or clearly archives it",
            "Do not delete that prototype from this docs/test slice",
        ),
    )

    _require_all(
        failures,
        scripts,
        "operator harness bridge scripts",
        (
            "CHAT_STAY_UP_TO_DATE.md",
            "DELTA_BRIDGE_NAME",
            "adjacent_to_ingest=true",
            "counted_in_24=false",
            "CONTENT_FILES_PER_FOLDER=23",
            "EXPECTED_FILES_PER_FOLDER=24",
        ),
    )

    _require_any(
        failures,
        launch,
        "console/atlas non-authority warning",
        (
            "console/atlas is a window/router/evidence browser, not authority",
            "windows routers and evidence browsers",
        ),
    )

    _require_all(
        failures,
        combined,
        "non-authority and v1 safety warnings",
        (
            "operator remains authority",
            "Guardian may approve/deny",
            "must not handle secrets",
            "No service/runtime mutation in v1",
            "No private/legal/vault/log inspection in v1",
            "No provider/model calls in v1",
        ),
    )

    _require_all(
        failures,
        launch,
        "Multi-OpenClaw Command Atlas horizon",
        ("Multi-OpenClaw Command Atlas", "long-range product horizon"),
    )

    _require_all(
        failures,
        launch,
        "atlas zoom levels",
        (
            "all builds deployments",
            "one build deployment",
            "departments",
            "agents systems subsystems modules",
            "launch goals",
            "launch ladders",
            "steps",
            "evidence artifacts",
            "docs code prompts validation",
        ),
    )

    _require_all(
        failures,
        launch,
        "operator-facing unit of work",
        ("Launch Ladders replace vague lanes",),
    )

    _require_all(
        failures,
        launch,
        "v1 docs/spec-only boundary",
        ("docs/spec only in v1", "does not create generated folders or scripts"),
    )

    _require_all(
        failures,
        validation_map,
        "validation map entry",
        (
            "launch_ladder_contract_check.py",
            "test_launch_ladder_static_contract.py",
            "fixtures mission control",
        ),
    )

    failures.extend(mission_control_fixture_failures())

    return StaticContractReport(
        failures=tuple(failures),
        warnings=freshness_warnings(corpus),
    )


def main() -> int:
    report = check_contract()
    for warning in report.warnings:
        print(f"WARNING: {warning}")
    if report.failures:
        for failure in report.failures:
            print(f"ERROR: {failure}", file=sys.stderr)
        return 1
    print("Launch Ladder static contract: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
