import json
import os
from pathlib import Path
from scripts.file_path_dependency_scan import scan_repo, REQUIRED_TERMS

REPO_ROOT = Path(__file__).resolve().parents[1]

def test_scanner_read_only():
    """Scanner should only generate reports and not mutate repo state."""
    report = scan_repo()
    assert report["metadata"]["mode"] == "read-only/static-reference-scan"
    assert report["cleanup_decision_posture"]["allowed_actions"] == "none"
    assert report["metadata"]["repo_root"] == str(REPO_ROOT)

def test_scanner_accepts_explicit_root_and_skips_symlink_files(tmp_path):
    """Scanner should support isolated roots and avoid symlink file reads."""
    source = tmp_path / "source.md"
    source.write_text("mac_eyes\n/mnt/c/OpenClaw\n", encoding="utf-8")
    (tmp_path / "source-link.md").symlink_to(source)

    report = scan_repo(root=tmp_path)

    assert report["metadata"]["repo_root"] == str(tmp_path.resolve())
    assert report["metadata"]["scanned_file_count"] == 1
    assert report["dependency_sensitive_files"] == {
        "source.md": ["/mnt/c/OpenClaw", "mac_eyes"]
    }

def test_scanner_forbidden_dirs_skipped():
    """Scanner must skip forbidden directories."""
    report = scan_repo()
    assert "mac_eyes" in report["metadata"]["skipped_categories"]
    assert ".git" in report["metadata"]["skipped_categories"]

def test_scanner_required_terms_checked():
    """Scanner must check for all required terms."""
    report = scan_repo()
    found_terms = [t["term"] for t in report["term_summary"]]
    for term in REQUIRED_TERMS:
        assert term in found_terms

def test_scanner_risk_classes_present():
    """Scanner must categorize findings into risk classes."""
    report = scan_repo()
    classes = report["cleanup_risk_classes"]
    assert "high risk" in classes
    assert "medium risk" in classes
    assert "low risk" in classes

def test_scanner_no_cleanup_authority():
    """Scanner must explicitly state it grants no cleanup authority."""
    report = scan_repo()
    posture = report["cleanup_decision_posture"]
    assert "no move/delete/rename allowed" in posture["posture"]
    assert posture["allowed_actions"] == "none"

def test_scanner_no_forbidden_imports():
    """Scanner must not use SQLite, MCP, or embeddings."""
    with open("scripts/file_path_dependency_scan.py") as f:
        content = f.read()
    assert "import sqlite3" not in content
    assert "import mcp" not in content.lower()
    assert "import embedding" not in content.lower()
