#!/usr/bin/env python3
"""Mac Watch Markdown Knowledge Index v0.

Collects a bounded knowledge index of markdown files in ~/OpenClaw_Watch
on the Mac over SSH, classifies them, and produces a report.
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import subprocess
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPORTS_DIR = ROOT / "reports" / "mac_watch_index"

# These terms must be audited
AUDIT_TERMS = (
    "OpenClaw_Watch",
    "mac_eyes",
    "Right now.md",
    "Operator Watch.md",
    "operator_harness_readiness",
    "MAC_WATCH_MARKDOWN_CENSUS_REPORT",
    "sync_operator_harness_to_mac",
    "dashboard_gen.py",
)

def get_mac_script(root_path: str) -> str:
    """Return a python script to run on the Mac to fetch file metadata."""
    return f"""
import os
import json
from pathlib import Path

def extract_markdown_info(filepath, root):
    try:
        st = filepath.stat()
        size = st.st_size
        mtime = st.st_mtime
    except Exception:
        return None

    try:
        with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()
    except Exception:
        return None

    lines = content.splitlines()
    headings = []
    first_heading = ""
    for line in lines:
        if line.startswith("#"):
            h = line.strip()
            headings.append(h)
            if not first_heading:
                first_heading = h

    excerpt = content[:1500]
    
    try:
        rel_path = str(filepath.relative_to(root))
    except Exception:
        rel_path = str(filepath)

    return {{
        "relative_path": rel_path,
        "size_bytes": size,
        "modified_time": mtime,
        "first_heading": first_heading,
        "headings": headings[:12],
        "excerpt_preview": excerpt,
    }}

def run(root_dir):
    root = Path(root_dir).expanduser()
    results = []
    if not root.is_dir():
        print(json.dumps({{"error": f"Root directory {{root_dir}} not found"}}))
        return

    for dirpath, _, filenames in os.walk(root):
        for name in filenames:
            if name.endswith(".md") or name.endswith(".markdown"):
                full = Path(dirpath) / name
                info = extract_markdown_info(full, root)
                if info:
                    results.append(info)
    print(json.dumps({{"files": results}}))

run("{root_path}")
"""

def classify_file(info: dict[str, object]) -> dict[str, object]:
    """Classify family/type with deterministic rules and assign tags."""
    path = str(info.get("relative_path", ""))
    content_preview = str(info.get("excerpt_preview", "")).lower()
    
    # 1. Detect top-level loose files
    is_top_level = "/" not in path

    # 2. Grouping
    group = "unknowns"
    path_lower = path.lower()
    
    if is_top_level:
        group = "top-level loose files"

    # Precise matching based on path keywords overrides top-level check
    if "watch" in path_lower or "dashboard" in path_lower or "right now.md" in path_lower or "operator watch" in path_lower:
        group = "generated watch surfaces"
    elif "research" in path_lower or "source" in path_lower:
        group = "research/source material"
    elif "legal" in path_lower or "vault" in path_lower:
        group = "legal product docs"
    elif "ingest" in path_lower or "packet" in path_lower:
        group = "ingest packets"
    elif "mirror" in path_lower:
        group = "mirrors"
    elif "handoff" in path_lower or "history" in path_lower:
        group = "historical handoffs"
        
    # 3. Tags
    tags = []
    if "todo" in content_preview or "fixme" in content_preview:
        tags.append("has_todos")
        
    # 4. Authority guess
    authority_guess = "none"
    if group == "legal product docs":
        authority_guess = "legal_reference"
    elif group == "generated watch surfaces":
        authority_guess = "read_only_mirror"
    elif group == "ingest packets":
        authority_guess = "source_truth"
        
    # 5. Freshness class
    freshness_class = "stale"
    now = datetime.now().timestamp()
    mtime = float(info.get("modified_time", 0))
    age_seconds = now - mtime
    if age_seconds < 86400:
        freshness_class = "fresh"
    elif age_seconds < 86400 * 7:
        freshness_class = "recent"
        
    # 6. Needs deeper review
    needs_deeper_review = group == "unknowns" or "error" in content_preview or is_top_level and group == "top-level loose files"
    
    return {
        "group": group,
        "tags": tags,
        "authority_guess": authority_guess,
        "freshness_class": freshness_class,
        "needs_deeper_review": needs_deeper_review,
        "is_top_level_loose": is_top_level
    }

def scan_pc_dependencies(root: Path) -> dict[str, list[str]]:
    """Scan PC repo for path dependencies referencing terms."""
    results: dict[str, list[str]] = {term: [] for term in AUDIT_TERMS}
    
    for filepath in root.rglob("*"):
        if not filepath.is_file():
            continue
        if filepath.suffix not in (".py", ".md", ".sh"):
            continue
        parts = filepath.parts
        if "node_modules" in parts or "reports" in parts or "__pycache__" in parts or "sidecars" in parts or "chief_env" in parts or any(p.startswith(".") for p in parts):
            continue
            
        try:
            content = filepath.read_text(encoding='utf-8', errors='ignore')
            for term in AUDIT_TERMS:
                if term in content:
                    results[term].append(str(filepath.relative_to(root)))
        except Exception:
            pass
            
    return {k: sorted(list(set(v))) for k, v in results.items()}

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root-mac-path", default="~/OpenClaw_Watch", help="Root path on Mac")
    parser.add_argument("--output-dir", default=str(REPORTS_DIR), help="Output directory")
    args = parser.parse_args()
    
    mac_script = get_mac_script(args.root_mac_path)
    
    # Run SSH
    try:
        res = subprocess.run(
            ["ssh", "mac", "python3", "-"],
            input=mac_script,
            capture_output=True, 
            text=True, 
            check=True
        )
        try:
            mac_data = json.loads(res.stdout)
        except json.JSONDecodeError:
            mac_data = {"files": [], "error": "Invalid JSON from Mac", "raw": res.stdout}
    except subprocess.CalledProcessError as e:
        print(f"Error fetching from Mac: {e.stderr}")
        mac_data = {"files": [], "error": f"SSH subprocess failed: {e.stderr}"}
    except Exception as e:
        print(f"Execution error: {e}")
        mac_data = {"files": [], "error": f"Execution error: {str(e)}"}
        
    error_msg = mac_data.get("error")
    if error_msg:
        print(f"Mac returned error/warning: {error_msg}")
        
    files = mac_data.get("files", [])
    indexed_files = []
    for f in files:
        classification = classify_file(f)
        indexed_files.append({**f, **classification})
        
    deps = scan_pc_dependencies(ROOT)
    
    out_dir = Path(args.output_dir).resolve()
    json_report_path = out_dir / "MAC_WATCH_MARKDOWN_INDEX.json"
    md_report_path = out_dir / "MAC_WATCH_MARKDOWN_INDEX.md"
    
    report = {
        "summary": {
            "total_markdown_files": len(indexed_files),
            "generated_at": datetime.now().isoformat(),
            "status": "unavailable/invalid" if error_msg else "success",
            "error": error_msg
        },
        "files": indexed_files,
        "dependency_audit": deps,
        "boundary_check": "Mac Watch files were only read. No moves, renames, deletes, or writes occurred on Mac. Mac Watch is not canonical authority.",
        "output_paths": {
            "json": str(json_report_path.relative_to(ROOT)),
            "md": str(md_report_path.relative_to(ROOT))
        }
    }
    
    out_dir.mkdir(parents=True, exist_ok=True)
    
    with open(json_report_path, "w", encoding="utf-8") as jf:
        json.dump(report, jf, indent=2)
        
    with open(md_report_path, "w", encoding="utf-8") as mf:
        mf.write("# Mac Watch Markdown Index\n\n")
        if error_msg:
            mf.write(f"**STATUS: UNAVAILABLE / INVALID**\n")
            mf.write(f"Error: {error_msg}\n\n")
        else:
            mf.write(f"Total files: {len(indexed_files)}\n\n")
            
        mf.write("## Boundaries Checked\n")
        mf.write(report["boundary_check"] + "\n\n")
        
        mf.write("## Dependencies\n")
        for k, v in deps.items():
            mf.write(f"- **{k}**: {len(v)} references\n")
            
        mf.write("\n## Files\n")
        for f in indexed_files:
            mf.write(f"### {f['relative_path']}\n")
            mf.write(f"- Group: {f['group']}\n")
            mf.write(f"- Authority: {f['authority_guess']}\n")
            mf.write(f"- Freshness: {f['freshness_class']}\n")
            mf.write(f"- Needs Review: {f['needs_deeper_review']}\n")
            if f.get('first_heading'):
                mf.write(f"- First Heading: {f['first_heading']}\n")
            mf.write("\n")
            
    print(f"Count of indexed markdown files: {len(indexed_files)}")
    print(f"Classification behavior applied.")
    print(f"Dependency audit complete.")
    print("READY_FOR_CHATGPT_REVIEW")

    if error_msg:
        import sys
        sys.exit(1)

if __name__ == "__main__":
    main()
