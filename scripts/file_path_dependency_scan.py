#!/usr/bin/env python3
"""
File Path Dependency Scan v0

A read-only scanner to identify references to Mac Watch paths, sync scripts, 
and potential cleanup targets without executing any cleanup or modifications.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

ROOT = Path(__file__).resolve().parents[1]

# Skip configurations
SKIPPED_DIRS = {
    ".git", "__pycache__", "node_modules", ".venv", "venv", "env",
    ".pytest_cache", ".claude", ".codex", ".feynman", ".gemini",
    ".kimi", ".nemoclaw", ".openclaw", "chief_env", "mac_eyes",
    "OpenClawLegalPrivate", "OpenClawShared", ".google-secrets",
    ".private", "compliance_verdicts"
}

SKIPPED_EXTENSIONS = {
    ".pyc", ".pyo", ".pyd", ".so", ".dll", ".dylib", ".exe", ".bin",
    ".jpg", ".jpeg", ".png", ".gif", ".ico", ".pdf", ".zip", ".tar",
    ".gz", ".tgz", ".bz2", ".7z", ".mp3", ".mp4", ".avi", ".mov",
    ".sqlite", ".sqlite3", ".db", ".lock", ".svg", ".woff", ".ttf",
    ".eot", ".pem", ".class", ".jar"
}

REQUIRED_TERMS = [
    "OpenClaw_Watch",
    "mac_eyes",
    "Operator Watch.md",
    "Right now.md",
    "dashboard_gen.py",
    "reports/mac_watch_index",
    "MAC_WATCH_MARKDOWN_INDEX",
    "sync_operator_harness_to_mac",
    "sync_legal_planning_to_mac",
    "watch_legal_planning_to_mac",
    "sync_legal",
    "Launchers",
    "OpenClawShared",
    "OpenClawLegalPrivate",
    "/mnt/c/OpenClaw",
    "/mnt/c/OpenClawShared",
    "/mnt/c/OpenClawLegalPrivate"
]

REPORT_DIR = ROOT / "reports" / "file_path_dependency_scan"
REPORT_MD = REPORT_DIR / "FILE_PATH_DEPENDENCY_SCAN.md"
REPORT_JSON = REPORT_DIR / "FILE_PATH_DEPENDENCY_SCAN.json"

def is_text_file(filepath: Path) -> bool:
    if filepath.suffix.lower() in SKIPPED_EXTENSIONS:
        return False
    if filepath.name.startswith("."):
        return False
    
    # Try reading first few bytes to detect binary
    try:
        with open(filepath, 'rb') as f:
            chunk = f.read(1024)
            if b'\0' in chunk:
                return False
    except Exception:
        return False
    return True

def get_risk_class(filepath: Path, *, root: Path = ROOT) -> str:
    path_str = str(filepath.relative_to(root))
    if path_str.startswith("scripts/") or path_str.startswith("Launchers/") or "dashboard" in path_str.lower() or path_str.endswith(".sh") or path_str.endswith(".py"):
        return "high risk"
    elif path_str.startswith("docs/") or path_str.startswith("reports/") or path_str.endswith(".md"):
        return "medium risk"
    return "low risk"

def scan_repo(root: str | Path | None = None) -> Dict[str, Any]:
    repo_root = Path(root) if root is not None else ROOT
    scanned_count = 0
    term_matches: Dict[str, Dict[str, Any]] = {
        term: {"count": 0, "files": set()}
        for term in REQUIRED_TERMS
    }
    
    file_references: Dict[str, Set[str]] = {}

    for dirpath, dirnames, filenames in os.walk(repo_root):
        # Exclude skipped directories in-place
        dirnames[:] = [d for d in dirnames if d not in SKIPPED_DIRS and not d.startswith(".")]

        for filename in filenames:
            filepath = Path(dirpath) / filename
            if filepath.is_symlink():
                continue
            if not is_text_file(filepath):
                continue
            
            scanned_count += 1
            
            try:
                content = filepath.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue

            rel_path = str(filepath.relative_to(repo_root))
            found_terms_in_file = set()

            for term in REQUIRED_TERMS:
                count = content.count(term)
                if count > 0:
                    term_matches[term]["count"] += count
                    term_matches[term]["files"].add(rel_path)
                    found_terms_in_file.add(term)
            
            if found_terms_in_file:
                file_references[rel_path] = found_terms_in_file

    dependency_sensitive = {
        path: sorted(terms)
        for path, terms in file_references.items()
        if len(terms) > 1
    }

    # Format term summary
    term_summary = []
    for term, data in term_matches.items():
        term_summary.append({
            "term": term,
            "match_count": data["count"],
            "file_count": len(data["files"]),
            "sample_files": sorted(list(data["files"]))[:3]
        })

    # Risk categorization
    risk_classes = {
        "high risk": [],
        "medium risk": [],
        "low risk": [],
        "unknown": []
    }
    
    for path in file_references:
        risk = get_risk_class(repo_root / path, root=repo_root)
        risk_classes[risk].append(path)

    return {
        "metadata": {
            "mode": "read-only/static-reference-scan",
            "repo_root": str(repo_root),
            "scanned_file_count": scanned_count,
            "skipped_categories": list(SKIPPED_DIRS) + ["binary files", "private roots"]
        },
        "term_summary": term_summary,
        "dependency_sensitive_files": dependency_sensitive,
        "cleanup_risk_classes": {k: sorted(v) for k, v in risk_classes.items()},
        "cleanup_decision_posture": {
            "allowed_actions": "none",
            "posture": "no move/delete/rename allowed from this scan alone",
            "purpose": "scan only identifies dependency pressure",
            "status": "proposed cleanup actions remain candidate-only"
        },
        "explicit_next_safe_edge": [
            "review high-risk references",
            "create candidate move map only after dependency owners are understood"
        ]
    }

def write_reports(data: Dict[str, Any]) -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    # Write JSON
    with open(REPORT_JSON, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    # Write Markdown
    md_lines = [
        "# File Path Dependency Scan",
        "",
        "## Metadata",
        f"- **Mode:** {data['metadata']['mode']}",
        f"- **Repo Root:** {data['metadata']['repo_root']}",
        f"- **Scanned File Count:** {data['metadata']['scanned_file_count']}",
        f"- **Skipped Categories:** {', '.join(data['metadata']['skipped_categories'])}",
        "",
        "## Cleanup Decision Posture",
        f"- **Status:** {data['cleanup_decision_posture']['posture']}",
        f"- **Purpose:** {data['cleanup_decision_posture']['purpose']}",
        f"- **Proposed actions:** {data['cleanup_decision_posture']['status']}",
        "",
        "## Explicit Next Safe Edge",
    ]
    for edge in data['explicit_next_safe_edge']:
        md_lines.append(f"- {edge}")
    md_lines.append("")
    
    md_lines.append("## Term Summary")
    md_lines.append("| Term | Matches | Files | Sample Files |")
    md_lines.append("|---|---|---|---|")
    for t in data["term_summary"]:
        samples = ", ".join(t["sample_files"])
        md_lines.append(f"| `{t['term']}` | {t['match_count']} | {t['file_count']} | {samples} |")
    md_lines.append("")

    md_lines.append("## Dependency-Sensitive Files (Multiple References)")
    for path, terms in sorted(data["dependency_sensitive_files"].items()):
        md_lines.append(f"- `{path}`: {', '.join(f'`{t}`' for t in terms)}")
    md_lines.append("")

    md_lines.append("## Cleanup Risk Classes")
    for risk, files in data["cleanup_risk_classes"].items():
        if files:
            md_lines.append(f"### {risk.title()}")
            for f in sorted(files):
                md_lines.append(f"- `{f}`")
            md_lines.append("")

    with open(REPORT_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines) + "\n")

if __name__ == "__main__":
    report_data = scan_repo()
    write_reports(report_data)
    print(f"Scan complete. Reports generated at {REPORT_DIR}")
