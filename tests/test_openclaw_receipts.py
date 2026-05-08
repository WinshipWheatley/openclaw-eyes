from __future__ import annotations

import ast
import inspect
import stat
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import openclaw_receipts as receipts
import openclaw_sensitive_policy as sensitive_policy


def _rail_fixture_text(name: str) -> str:
    if name == receipts.PROMPT_DOCTRINE_RAIL:
        return (
            "# Model And Tool Specific Prompt Doctrine\n\n"
            "Gemini planning/audit prompts are for rail interpretation, "
            "architecture/design judgment, tradeoffs, risk, scope, campaign "
            "shaping, and READY/NOT_READY recommendations.\n"
            "Gemini plans are not automatic execution authority.\n"
            "Codex implementation prompts are for bounded repo mutation: "
            "inspect conventions, edit files, add focused tests, run checks, "
            "fix failures, and produce reviewable diffs.\n"
            "Do not castrate Codex with generic forbiddance spam. Guard the "
            "real risks and actual strengths and failure modes.\n"
            "Gemini review: architecture, scope, risk, rail alignment.\n"
            "Codex review: dirty diff, line behavior, tests, failure modes, "
            "boundary leaks, commit readiness.\n"
        )
    gated_text = {
        "16_SENSITIVE_ROOT_AND_LEGAL_EXPORT_BOUNDARIES.md": (
            "No legal-private content reads.\nNo private-root inspection.\n"
        ),
        "17_INVOICE_ARTIFACT_AND_BILLING_BRIDGE_BOUNDARIES.md": (
            "Do not generate final invoices.\n"
        ),
        "19_GATED_ACTIVATION_READINESS_MAP.md": (
            "Packet 07 does not authorize live runtime launch.\n"
            "No live service launch.\nNo private-root inspection.\n"
        ),
        "22_MCP_SHARED_MEMORY_AND_HIDDEN_AUTHORITY_GATES.md": (
            "Single-source-of-truth requirements.\n"
            "Receipts/read models as evidence, not approval.\n"
            "No MCP invocation.\nNo external MCP calls.\n"
            "No hidden memory writes.\nhidden authority\n"
            "No private-root exposure.\n"
        ),
        "23_BROAD_SOURCE_SET_EXCLUSION_AND_PACKET_RENEWAL_GUARD.md": (
            "No broad filesystem crawling.\nNo path-metadata-as-authority.\n"
            "No source-set generation from hidden chat memory.\n"
        ),
    }
    return f"# {name}\n\n{gated_text.get(name, '')}"


def _write_packet_fixture(root: Path) -> None:
    packet_index = root / receipts.PACKET_INDEX_RELATIVE_PATH
    rails_dir = root / receipts.ACTIVE_RAILS_RELATIVE_PATH
    handoff = root / receipts.ACTIVE_HANDOFF_RELATIVE_PATH
    archive_dir = root / receipts.PACKET06_ARCHIVE_RELATIVE_PATH
    archive_rails = archive_dir / "24_files"
    archive_handoff = archive_dir / "00_ACTIVE_HANDOFF.md"

    packet_index.parent.mkdir(parents=True, exist_ok=True)
    packet_index.write_text(
        "# OpenClaw Project Packets\n\n"
        "## Active Packet\n\n"
        f"- `{receipts.ACTIVE_PACKET_RELATIVE_PATH.name}/`\n\n"
        "## Archived Packet Snapshots\n\n"
        f"- `../project_packets_archive/{receipts.PACKET06_ARCHIVE_RELATIVE_PATH.name}/`\n",
        encoding="utf-8",
    )
    rails_dir.mkdir(parents=True, exist_ok=True)
    handoff.write_text(
        "This handoff is the train. The roadmap authority is "
        "24_files/01_PROJECT_SOURCE_SET_INDEX_AND_RAIL_MAP.md.\n",
        encoding="utf-8",
    )
    for name in receipts.REQUIRED_RAIL_FILES:
        (rails_dir / name).write_text(_rail_fixture_text(name), encoding="utf-8")
    archive_rails.mkdir(parents=True, exist_ok=True)
    archive_handoff.write_text(
        "This handoff is the train. The roadmap authority is "
        "24_files/01_PROJECT_SOURCE_SET_INDEX_AND_RAIL_MAP.md.\n",
        encoding="utf-8",
    )
    for name in receipts.PACKET06_REQUIRED_RAIL_FILES:
        (archive_rails / name).write_text(f"# {name}\n", encoding="utf-8")


def test_parse_porcelain_status_handles_changed_untracked_and_renames():
    parsed = receipts.parse_porcelain_status(
        " M scripts/openclaw_receipts.py\n"
        '?? "docs/file with space.md"\n'
        "R  old.md -> new.md\n"
    )

    assert parsed == [
        receipts.ChangedFile(status="M", path="scripts/openclaw_receipts.py"),
        receipts.ChangedFile(status="??", path="docs/file with space.md"),
        receipts.ChangedFile(status="R", path="old.md"),
        receipts.ChangedFile(status="R", path="new.md"),
    ]


def test_packet_status_checks_exact_active_packet_without_broad_scan(tmp_path):
    _write_packet_fixture(tmp_path)

    report = receipts.packet_status(tmp_path)

    assert report["passed"] is True
    assert report["active_packet"] == str(receipts.ACTIVE_PACKET_RELATIVE_PATH)
    assert report["target_packet"] == str(receipts.ACTIVE_PACKET_RELATIVE_PATH)
    assert report["target_is_active"] is True
    assert report["rail_count"] == 24
    assert report["missing_rails"] == ()
    assert report["extra_rails"] == ()
    assert all(report["key_rails"].values())
    assert report["key_rails"][receipts.PROMPT_DOCTRINE_RAIL] is True
    assert report["key_rails"]["19_GATED_ACTIVATION_READINESS_MAP.md"] is True
    assert report["packet06_archive"]["preserved"] is True
    assert report["packet06_archive"]["rail_count"] == 24


def test_packet_status_fails_if_packet06_archive_snapshot_is_missing(tmp_path):
    _write_packet_fixture(tmp_path)
    (tmp_path / receipts.PACKET06_ARCHIVE_RELATIVE_PATH / "00_ACTIVE_HANDOFF.md").unlink()

    report = receipts.packet_status(tmp_path)

    assert report["passed"] is False
    assert report["packet06_archive"]["preserved"] is False


def test_docs_only_guard_blocks_changed_files_outside_allowed_prefix(tmp_path):
    _write_packet_fixture(tmp_path)
    report = receipts.docs_only_guard_report(
        (
            receipts.ChangedFile(
                status="M",
                path=str(receipts.ACTIVE_HANDOFF_RELATIVE_PATH),
            ),
            receipts.ChangedFile(status="M", path="scripts/openclaw_receipts.py"),
        ),
        allowed_prefixes=(str(receipts.ACTIVE_PACKET_RELATIVE_PATH),),
        root=tmp_path,
    )

    assert report["passed"] is False
    assert report["outside_allowed"] == ("scripts/openclaw_receipts.py",)
    assert report["private_findings"] == ()
    assert report["broad_allowed_prefixes"] == ()


def test_docs_only_guard_rejects_broad_source_set_prefixes(tmp_path):
    _write_packet_fixture(tmp_path)

    report = receipts.docs_only_guard_report(
        (
            receipts.ChangedFile(
                status="M",
                path=str(receipts.ACTIVE_HANDOFF_RELATIVE_PATH),
            ),
        ),
        allowed_prefixes=("docs",),
        root=tmp_path,
    )

    assert report["passed"] is False
    assert report["broad_allowed_prefixes"] == ("docs",)


def test_docs_only_guard_redacts_sensitive_paths_from_outside_allowed(tmp_path, capsys):
    _write_packet_fixture(tmp_path)
    denied_path = "legal/client/private-matter.md"
    report = receipts.docs_only_guard_report(
        (receipts.ChangedFile(status="M", path=denied_path),),
        allowed_prefixes=(str(receipts.ACTIVE_PACKET_RELATIVE_PATH),),
        root=tmp_path,
    )

    receipts.print_docs_only_guard(report)
    output = capsys.readouterr().out

    assert report["passed"] is False
    assert denied_path not in output
    assert "outside_allowed:" in output
    assert "<withheld_by_static_path_policy>" in output


def test_path_policy_denies_private_sensitive_and_parent_escape_paths(tmp_path):
    findings = receipts.path_policy_findings(
        (
            "legal/client-matter.md",
            "/Users/hwinshipwheatley/Sensitive Folder For Review/raw.pdf",
            "../.chief.env",
            "docs/planning/sensitive_roots/SENSITIVE_ROOT_REGISTRY_BREADCRUMB_20260507.md",
            "openclaw_sensitive_policy.py",
        ),
        root=tmp_path,
    )

    by_path = {finding.path: finding for finding in findings}
    assert by_path["legal/client-matter.md"].finding == "sensitive_path_component"
    assert by_path["/Users/hwinshipwheatley/Sensitive Folder For Review/raw.pdf"].finding == (
        "outside_repo_or_parent_escape"
    )
    assert by_path["../.chief.env"].finding == "outside_repo_or_parent_escape"
    assert "docs/planning/sensitive_roots/SENSITIVE_ROOT_REGISTRY_BREADCRUMB_20260507.md" not in by_path
    assert "openclaw_sensitive_policy.py" not in by_path


def test_sensitive_root_contract_is_metadata_only_and_deny_content():
    report = receipts.sensitive_root_contract()

    assert report["passed"] is True
    assert report["content_access_allowed"] is False
    assert report["path_policy_only"] is True
    assert report["filesystem_inspected"] is False
    assert "path_hint" in report["registry_fields"]
    assert report["quarantine_intake_contract"]["content_read_allowed"] is False
    assert report["quarantine_intake_contract"]["filesystem_inventory_allowed"] is False
    assert "crawl" in report["forbidden_actions"]
    assert "external_model_access" in report["forbidden_actions"]


def test_packet06_final_static_boundary_contract_preserves_deferred_authority():
    report = sensitive_policy.packet06_final_static_boundary_contract()

    assert report["passed"] is True
    assert report["invoice_artifact"]["draft_only"] is True
    assert report["invoice_artifact"]["invoice_generation_allowed"] is False
    assert report["invoice_artifact"]["invoice_send_allowed"] is False
    assert report["invoice_artifact"]["invoice_reconciliation_authority"] is False
    assert report["legal_context_export"]["metadata_only"] is True
    assert report["legal_context_export"]["content_access_allowed"] is False
    assert report["legal_context_export"]["outside_model_access_allowed"] is False
    assert report["legal_context_export"]["no_echo_required"] is True
    assert report["mcp_shared_memory"]["external_mcp_calls_allowed"] is False
    assert report["mcp_shared_memory"]["hidden_canonical_memory_writes_allowed"] is False
    assert report["mcp_shared_memory"]["receipts_are_execution_authority"] is False
    assert report["runtime_and_legacy_gating"]["static_review_only"] is True
    assert report["runtime_and_legacy_gating"]["live_service_launch_allowed"] is False
    assert report["runtime_and_legacy_gating"]["runtime_mutation_allowed"] is False
    assert report["source_set_exclusion"]["broad_preload_allowed"] is False
    assert report["source_set_exclusion"]["path_metadata_is_authority"] is False
    assert report["source_set_exclusion"]["packet07_carry_forward_constraint"] is True


def test_no_private_root_check_receipt_redacts_denied_path_strings(tmp_path, capsys):
    private_path = "/Users/hwinshipwheatley/Sensitive Folder For Review/raw.pdf"

    exit_code = receipts.main(
        [
            "--root",
            str(tmp_path),
            "no-private-root-check",
            private_path,
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 1
    assert "filesystem_inspected: False" in output
    assert "content_accessed: False" in output
    assert "outside_repo_or_parent_escape" in output
    assert private_path not in output
    assert "<withheld_by_static_path_policy>" in output


def test_sensitive_path_hint_values_ignore_non_path_ids():
    values = sensitive_policy.sensitive_path_hint_values(
        {
            "profile_id": "private-profile",
            "source_path": "legal/client/private-matter.pdf",
        }
    )

    assert values == ("legal/client/private-matter.pdf",)


def test_canonical_receipt_surface_is_executable_and_names_itself():
    script = ROOT / "scripts" / "openclaw_receipts.py"

    assert script.stat().st_mode & stat.S_IXUSR
    completed = subprocess.run(
        [str(script), "--help"],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    assert completed.returncode == 0
    assert "usage: ./scripts/openclaw_receipts.py" in completed.stdout


def test_prompt_doctrine_status_checks_packet07_model_profiles(tmp_path):
    _write_packet_fixture(tmp_path)

    report = receipts.prompt_doctrine_status(tmp_path)

    assert report["passed"] is True
    assert report["target_packet"] == str(receipts.ACTIVE_PACKET_RELATIVE_PATH)
    assert report["mutates_files"] is False
    assert report["generates_prompts"] is False
    assert report["checks"]["file14_present"] is True
    assert report["checks"]["gemini_planning_profile_present"] is True
    assert report["checks"]["codex_implementation_profile_present"] is True
    assert report["checks"]["review_prompt_split_present"] is True
    assert report["checks"]["non_generic_prompting_doctrine_present"] is True


def test_gated_activation_status_is_static_and_non_authorizing(tmp_path):
    _write_packet_fixture(tmp_path)

    report = receipts.gated_activation_status(tmp_path)

    assert report["passed"] is True
    assert report["runtime_activation_authorized"] is False
    assert report["receipt_grants_execution_authority"] is False
    assert report["mcp_hidden_memory_write_authorized"] is False
    assert report["invoice_legal_private_root_activation_authorized"] is False
    assert report["filesystem_inspected"] is False
    assert report["runtime_launched"] is False
    assert report["provider_or_model_called"] is False
    assert report["checks"]["runtime_activation_not_authorized"] is True
    assert report["checks"]["mcp_hidden_authority_blocked"] is True
    assert report["checks"]["invoice_legal_private_root_activation_gated"] is True
    assert report["checks"]["broad_source_set_laundering_blocked"] is True
    assert report["runtime_dry_run_readiness_command"].endswith("runtime-dry-run-readiness")
    assert report["mcp_shared_memory_gate_command"].endswith("mcp-shared-memory-gate-status")
    assert report["future_activation_path"] == receipts.RUNTIME_DRY_RUN_FUTURE_PATH


def test_runtime_dry_run_readiness_classifies_surfaces_without_execution(tmp_path):
    _write_packet_fixture(tmp_path)

    report = receipts.runtime_dry_run_readiness(tmp_path)

    assert report["passed"] is True
    assert report["runtime_activation_authorized"] is False
    assert report["receipt_grants_execution_authority"] is False
    assert report["runtime_launched"] is False
    assert report["process_scan_used"] is False
    assert report["service_state_inspected"] is False
    assert report["runtime_state_mutated"] is False
    assert report["provider_or_model_called"] is False
    assert report["mcp_called"] is False
    assert report["invoice_action_taken"] is False
    assert report["private_root_inspected"] is False
    assert report["future_path"] == (
        "static guard",
        "dry-run readiness harness",
        "approval gate",
        "future live authorization",
    )

    groups = {group["surface"]: group for group in report["surface_groups"]}
    assert groups["legacy_launch_scripts"]["classification"] == "blocked"
    assert groups["legacy_stack_installer"]["classification"] == "blocked"
    assert groups["hermes_gateway_installer"]["classification"] == "dry-run-only"
    assert groups["service_inventory_audit"]["classification"] == "review-required"
    assert groups["systemd_user_templates"]["classification"] == "future-approval-required"
    assert all(group["executes_surface"] is False for group in groups.values())
    assert all(group["mutates_surface"] is False for group in groups.values())


def test_runtime_approval_gate_is_shape_not_current_permission(tmp_path):
    _write_packet_fixture(tmp_path)

    report = receipts.runtime_dry_run_readiness(tmp_path)
    gate = report["approval_gate"]

    assert gate["current_approval_granted"] is False
    assert gate["future_explicit_authority_required"] is True
    assert gate["live_approval_engine_implemented"] is False
    assert "model recommendation alone" in gate["not_sufficient"]
    assert "dry_run_readiness_receipt" in gate["required_evidence"]
    assert report["first_controlled_activation_lane"]["lane"] == (
        "runtime_authority_and_legacy_gating"
    )
    assert "receipt treated as approval" in report["first_controlled_activation_lane"][
        "failure_modes"
    ]


def test_prompt_pack_status_defines_distinct_model_review_and_commit_profiles(tmp_path):
    _write_packet_fixture(tmp_path)

    report = receipts.prompt_pack_status(tmp_path)

    assert report["passed"] is True
    assert report["mutates_files"] is False
    assert report["generates_prompts"] is False
    assert report["generated_prompt_count"] == 0
    profiles = {profile["profile"]: profile for profile in report["profiles"]}
    assert set(profiles) == {
        "gemini_planning_prompt",
        "codex_implementation_prompt",
        "gemini_architecture_scope_review_prompt",
        "codex_diff_commit_readiness_review_prompt",
        "codex_commit_mechanics_prompt",
    }
    assert profiles["gemini_planning_prompt"]["tool"] == "Gemini"
    assert profiles["codex_implementation_prompt"]["tool"] == "Codex"
    assert "invented architecture" in profiles["codex_implementation_prompt"][
        "drift_guards"
    ]
    assert "generic forbiddance spam" not in str(report["profiles"])
    assert "prior review returned READY_TO_COMMIT" in profiles[
        "codex_commit_mechanics_prompt"
    ]["requires"]
    assert report["checks"]["commit_mechanics_requires_ready_to_commit"] is True


def test_activation_evidence_packet_contains_required_static_evidence(tmp_path):
    _write_packet_fixture(tmp_path)

    report = receipts.activation_evidence_status(tmp_path)

    assert report["passed"] is True
    assert report["execution_authority_granted"] is False
    assert report["live_activation_implemented"] is False
    evidence = {item["item"]: item for item in report["required_evidence"]}
    assert tuple(evidence) == (
        "repo_receipt",
        "packet_receipt",
        "operator_harness_read_model_receipt",
        "dry_run_readiness_receipt",
        "boundary_non_authority_receipt",
        "targeted_test_receipt",
        "approval_gate_note",
    )
    assert evidence["repo_receipt"]["command"].endswith("repo-check")
    assert evidence["packet_receipt"]["command"].endswith("packet-status")
    assert evidence["operator_harness_read_model_receipt"]["command"].endswith(
        "operator-harness-status"
    )
    assert evidence["dry_run_readiness_receipt"]["command"].endswith(
        "runtime-dry-run-readiness"
    )
    assert evidence["boundary_non_authority_receipt"]["command"].endswith(
        "gated-activation-status"
    )
    assert evidence["targeted_test_receipt"]["command"] == (
        "pytest tests/test_openclaw_receipts.py -q"
    )
    assert all(item["purpose"] for item in evidence.values())
    assert report["approval_gate"]["current_approval_granted"] is False
    assert "mcp_shared_memory_activation" in report["supported_future_lanes"]


def test_mcp_shared_memory_gate_is_static_no_call_and_non_authorizing(tmp_path):
    _write_packet_fixture(tmp_path)

    report = receipts.mcp_shared_memory_gate_status(tmp_path)

    assert report["passed"] is True
    assert report["external_mcp_calls_allowed"] is False
    assert report["external_mcp_calls_used"] is False
    assert report["mcp_connector_mutated"] is False
    assert report["hidden_canonical_memory_writes_allowed"] is False
    assert report["hidden_canonical_memory_writes_used"] is False
    assert report["private_context_leakage_allowed"] is False
    assert report["shared_memory_is_execution_authority"] is False
    assert report["receipts_are_execution_authority"] is False
    pointers = {pointer["surface"]: pointer for pointer in report["static_pointers"]}
    assert pointers["mcp_profile_config"]["classification"] == "future-approval-required"
    assert pointers["receipt_read_model_bridge"]["classification"] == "dry-run-only"
    assert "single source of truth" in report["required_future_evidence"]
    assert report["checks"]["external_mcp_calls_blocked"] is True


def test_new_static_receipt_commands_exist_and_pass(tmp_path, capsys):
    _write_packet_fixture(tmp_path)

    for command in (
        "runtime-dry-run-readiness",
        "prompt-pack-status",
        "activation-evidence-status",
        "mcp-shared-memory-gate-status",
    ):
        exit_code = receipts.main(["--root", str(tmp_path), command])
        output = capsys.readouterr().out

        assert exit_code == 0
        assert "passed: True" in output


def test_operator_harness_read_model_combines_receipts_without_runtime_authority(tmp_path):
    _write_packet_fixture(tmp_path)

    report = receipts.operator_harness_read_model(
        root=tmp_path,
        files=(receipts.ChangedFile(status="M", path=str(receipts.ACTIVE_HANDOFF_RELATIVE_PATH)),),
    )

    cards = {card["card"]: card for card in report["cards"]}
    assert report["passed"] is True
    assert report["authority_note"].startswith("Receipts are proof snapshots")
    assert cards["command_surface"]["canonical_command"] == receipts.CANONICAL_RECEIPT_COMMAND
    assert cards["repo"]["changed_file_count"] == 1
    assert cards["packet"]["active_packet"] == str(receipts.ACTIVE_PACKET_RELATIVE_PATH)
    assert cards["packet"]["target_packet"] == str(receipts.ACTIVE_PACKET_RELATIVE_PATH)
    assert cards["packet"]["target_is_active"] is True
    assert cards["packet"]["rail_count"] == 24
    assert cards["packet06_archive"]["preserved"] is True
    assert cards["packet06_archive"]["rail_count"] == 24
    assert cards["active_handoff"]["is_roadmap_authority"] is False
    assert cards["sensitive_root_policy"]["filesystem_inspected"] is False
    assert cards["prompt_doctrine"]["passed"] is True
    assert cards["prompt_doctrine"]["gemini_planning_profile_present"] is True
    assert cards["prompt_doctrine"]["codex_implementation_profile_present"] is True
    assert cards["gated_activation"]["passed"] is True
    assert cards["gated_activation"]["runtime_activation_authorized"] is False
    assert cards["gated_activation"]["receipt_grants_execution_authority"] is False
    assert cards["runtime_dry_run_readiness"]["passed"] is True
    assert cards["runtime_dry_run_readiness"]["runtime_activation_authorized"] is False
    assert (
        cards["runtime_dry_run_readiness"]["receipt_grants_execution_authority"]
        is False
    )
    assert cards["runtime_dry_run_readiness"]["readiness_command"].endswith(
        "runtime-dry-run-readiness"
    )
    assert cards["runtime_dry_run_readiness"]["future_path"] == (
        "static guard",
        "dry-run readiness harness",
        "approval gate",
        "future live authorization",
    )
    assert cards["invoice_artifact"]["draft_only"] is True
    assert cards["invoice_artifact"]["invoice_generation_allowed"] is False
    assert cards["invoice_artifact"]["invoice_send_allowed"] is False
    assert cards["legal_context_export"]["metadata_only"] is True
    assert cards["legal_context_export"]["content_access_allowed"] is False
    assert cards["legal_context_export"]["outside_model_access_allowed"] is False
    assert cards["source_set_exclusion"]["broad_scan_used"] is False
    assert cards["source_set_exclusion"]["broad_preload_allowed"] is False
    assert cards["source_set_exclusion"]["broad_source_set_authority"] is False
    assert cards["source_set_exclusion"]["path_metadata_is_authority"] is False
    assert cards["runtime_authority"]["live_service_inspection_used"] is False
    assert cards["runtime_authority"]["runtime_mutation_allowed"] is False
    assert cards["runtime_authority"]["receipt_grants_execution"] is False
    assert cards["recovery"]["runtime_launched"] is False
    assert cards["recovery"]["self_authorizing"] is False
    assert cards["mcp_shared_memory"]["external_mcp_calls_allowed"] is False
    assert cards["mcp_shared_memory"]["hidden_memory_writes_allowed"] is False
    assert cards["mcp_shared_memory"]["shared_memory_is_roadmap_authority"] is False
    assert cards["packet07_carry_forward"]["receipt_is_roadmap_authority"] is False
    assert cards["packet07_carry_forward"]["read_from_handoff_before_renewal"] is True


def test_operator_harness_read_model_blocks_private_path_strings(tmp_path):
    _write_packet_fixture(tmp_path)

    report = receipts.operator_harness_read_model(
        root=tmp_path,
        files=(receipts.ChangedFile(status="M", path="legal/private-matter.md"),),
    )

    assert report["passed"] is False
    assert report["private_findings"][0].finding == "sensitive_path_component"


def test_repo_check_receipt_is_testable_without_shell_or_live_services(tmp_path, monkeypatch):
    _write_packet_fixture(tmp_path)

    def fake_run_git(root: Path, args: list[str]) -> receipts.GitCommandResult:
        stdout_by_args = {
            ("status", "-sb", "--untracked-files=all"): "## main...origin/main\n",
            ("--no-pager", "log", "--oneline", "-1"): "91c24a4 docs(project): create packet 07 source set\n",
            ("diff", "--check"): "",
            ("diff", "--cached", "--check"): "",
            ("status", "--porcelain=v1", "--untracked-files=all"): "",
        }
        return receipts.GitCommandResult(
            args=tuple(args),
            returncode=0,
            stdout=stdout_by_args[tuple(args)],
            stderr="",
        )

    monkeypatch.setattr(receipts, "_run_git", fake_run_git)

    report = receipts.repo_check_receipt(tmp_path)

    assert report["passed"] is True
    assert report["head"].startswith("91c24a4")
    assert report["worktree_clean"] is True
    assert report["packet_status_passed"] is True


def test_receipt_module_has_no_broad_walk_or_live_service_calls():
    source = inspect.getsource(receipts)
    tree = ast.parse(source)
    imported_modules = set()
    called_names = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.add(node.module.split(".")[0])
        elif isinstance(node, ast.Call):
            called = node.func
            if isinstance(called, ast.Name):
                called_names.add(called.id)
            elif isinstance(called, ast.Attribute):
                called_names.add(called.attr)

    assert imported_modules <= {
        "__future__",
        "argparse",
        "ast",
        "dataclasses",
        "openclaw_sensitive_policy",
        "pathlib",
        "subprocess",
        "sys",
        "typing",
    }
    assert called_names.isdisjoint(
        {
            "check_call",
            "check_output",
            "connect",
            "open_url",
            "popen",
            "system",
            "urlopen",
            "walk",
        }
    )
    assert "os.walk" not in source
    assert "glob(" not in source


def test_static_sensitive_policy_module_has_no_filesystem_inspection_calls():
    source = inspect.getsource(sensitive_policy)
    tree = ast.parse(source)
    called_names = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            called = node.func
            if isinstance(called, ast.Name):
                called_names.add(called.id)
            elif isinstance(called, ast.Attribute):
                called_names.add(called.attr)

    assert called_names.isdisjoint(
        {
            "exists",
            "glob",
            "is_dir",
            "is_file",
            "iterdir",
            "open",
            "read_text",
            "resolve",
            "walk",
        }
    )
