from __future__ import annotations

import ast
import inspect
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import openclaw_receipts as receipts


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


def test_path_policy_denies_private_sensitive_and_parent_escape_paths(tmp_path):
    findings = receipts.path_policy_findings(
        (
            "legal/client-matter.md",
            "/Users/hwinshipwheatley/Sensitive Folder For Review/raw.pdf",
            "../.chief.env",
            "docs/planning/sensitive_roots/SENSITIVE_ROOT_REGISTRY_BREADCRUMB_20260507.md",
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


def test_sensitive_root_contract_is_metadata_only_and_deny_content():
    report = receipts.sensitive_root_contract()

    assert report["passed"] is True
    assert report["content_access_allowed"] is False
    assert report["path_policy_only"] is True
    assert "path_hint" in report["registry_fields"]
    assert "crawl" in report["forbidden_actions"]
    assert "external_model_access" in report["forbidden_actions"]


def test_operator_harness_read_model_combines_receipts_without_runtime_authority(tmp_path):
    _write_packet_fixture(tmp_path)

    report = receipts.operator_harness_read_model(
        root=tmp_path,
        files=(receipts.ChangedFile(status="M", path=str(receipts.ACTIVE_HANDOFF_RELATIVE_PATH)),),
    )

    cards = {card["card"]: card for card in report["cards"]}
    assert report["passed"] is True
    assert report["authority_note"].startswith("Receipts are proof snapshots")
    assert cards["repo"]["changed_file_count"] == 1
    assert cards["packet"]["rail_count"] == 24
    assert cards["source_set_exclusion"]["broad_scan_used"] is False
    assert cards["runtime_authority"]["live_service_inspection_used"] is False
    assert cards["runtime_authority"]["runtime_mutation_allowed"] is False
    assert cards["recovery"]["runtime_launched"] is False


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
        "pathlib",
        "subprocess",
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
