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


def _write_packet_fixture(root: Path) -> None:
    packet_index = root / receipts.PACKET_INDEX_RELATIVE_PATH
    rails_dir = root / receipts.ACTIVE_RAILS_RELATIVE_PATH
    handoff = root / receipts.ACTIVE_HANDOFF_RELATIVE_PATH

    packet_index.parent.mkdir(parents=True, exist_ok=True)
    packet_index.write_text(
        f"# OpenClaw Project Packets\n\n- `{receipts.ACTIVE_PACKET_RELATIVE_PATH.name}/`\n",
        encoding="utf-8",
    )
    rails_dir.mkdir(parents=True, exist_ok=True)
    handoff.write_text(
        "This handoff is the train. The roadmap authority is "
        "24_files/01_PROJECT_SOURCE_SET_INDEX_AND_RAIL_MAP.md.\n",
        encoding="utf-8",
    )
    for name in receipts.REQUIRED_RAIL_FILES:
        (rails_dir / name).write_text(f"# {name}\n", encoding="utf-8")


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
    assert report["rail_count"] == 24
    assert report["missing_rails"] == ()
    assert report["extra_rails"] == ()
    assert all(report["key_rails"].values())


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
    assert cards["packet"]["rail_count"] == 24
    assert cards["active_handoff"]["is_roadmap_authority"] is False
    assert cards["sensitive_root_policy"]["filesystem_inspected"] is False
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
            ("--no-pager", "log", "--oneline", "-1"): "b460cdd docs(project): create packet 06 source set\n",
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
    assert report["head"].startswith("b460cdd")
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
