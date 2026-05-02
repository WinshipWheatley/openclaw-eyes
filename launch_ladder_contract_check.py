#!/usr/bin/env python3
"""Static contract checker for the Launch Ladder planning package.

This is a docs/test-only helper. It reads Markdown contracts and reports missing
product-contract language; it does not inspect runtime state or generated ingest
folders.
"""

from __future__ import annotations

from dataclasses import dataclass
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

UPLOADED_CURRENT_PRODUCT_SPEC = (
    "CHATGPT_PROJECT_INGEST_OPERATOR_HARNESS/01_CURRENT_PRODUCT_SPEC"
)
UPLOAD_AUTHORITY_COMMIT = "005a4081d6fa78d36a22c1e26d7f6731f8e2dbb2"
OMITTED_CURRENT_PRODUCT_SPEC_FILES = (
    "docs/planning/launch_ladder/09_MAC_IOS_APP_BUILD_BRIEF.md",
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
            f"the generated MANIFEST.md for {UPLOADED_CURRENT_PRODUCT_SPEC} is "
            f"upload authority and reports source commit {UPLOAD_AUTHORITY_COMMIT}; "
            "canonical Launch Ladder docs still contain package-level freshness "
            f"markers: {', '.join(stale_markers)}. Treat the manifest as source-set "
            "authority and the doc markers as package-level review metadata until "
            "a docs-only freshness normalization pass updates them."
        )

    for omitted in OMITTED_CURRENT_PRODUCT_SPEC_FILES:
        if (REPO_ROOT / omitted).is_file():
            warnings.append(
                "Source-set limitation: "
                f"{omitted} exists repo-side but was omitted from "
                f"{UPLOADED_CURRENT_PRODUCT_SPEC}; do not generate Mac/iOS "
                "app-build prompts from that source set alone."
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
            "005a4081d6fa78d36a22c1e26d7f6731f8e2dbb2",
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
        "current source-set posture",
        (
            "This Workspace Launch Profile and profile-to-packet handoff contract slice stays in 01_CURRENT_PRODUCT_SPEC",
            "does not move the active ChatGPT Project source-set posture to 02_MAC_IOS_APP_BUILD",
            "does not create source-set folder 04",
            "does not create generated source-set scripts",
            "does not edit generated source-set folders",
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
        ("launch_ladder_contract_check.py", "test_launch_ladder_static_contract.py"),
    )

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
