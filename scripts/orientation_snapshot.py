import os
import subprocess
import sqlite3
import json
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional

# --- Configuration ---
CONTRACT_PATH = "Operator/05_ORIENTATION_CONTRACT.md"
RUNTIME_MAP_PATH = "docs/operations/OPENCLAW_CURRENT_RUNTIME_MAP.md"
LEDGER_DB_PATH = ".openclaw/business_ops/ledger.sqlite"


def run_git_command(args: List[str]) -> str:
    """Safely runs a git command and returns the output."""
    try:
        result = subprocess.run(
            ["git"] + args,
            capture_output=True,
            text=True,
            timeout=5,
            check=False
        )
        if result.returncode == 0:
            return result.stdout.strip()
        return f"Error: {result.stderr.strip()}"
    except Exception as e:
        return f"Exception: {str(e)}"


def get_git_info() -> Dict[str, str]:
    """Gather current git metadata."""
    return {
        "branch": run_git_command(["rev-parse", "--abbrev-ref", "HEAD"]),
        "head_commit": run_git_command(["rev-parse", "HEAD"]),
        "recent_commit": run_git_command(["log", "-1", "--oneline"]),
        "status_summary": run_git_command(["status", "-s"]),
    }


def get_ledger_status() -> Dict[str, Any]:
    """Check Business Ops Ledger presence and metadata."""
    if not os.path.exists(LEDGER_DB_PATH):
        return {"status": "missing", "path": LEDGER_DB_PATH}

    try:
        conn = sqlite3.connect(LEDGER_DB_PATH)
        cursor = conn.cursor()

        # Get table count
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]

        # Get event count if events table exists
        event_count = 0
        if "events" in tables:
            cursor.execute("SELECT COUNT(*) FROM events")
            event_count = cursor.fetchone()[0]

        conn.close()
        return {
            "status": "active",
            "path": LEDGER_DB_PATH,
            "table_count": len(tables),
            "event_count": event_count,
            "tables": tables
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


def parse_markdown_section(content: str, search_text: str) -> str:
    """
    Extract content related to search_text.
    First tries to find it as a header, then as a numbered list item.
    """
    lines = content.splitlines()
    section = []
    found = False

    # 1. Try as Header
    header_level = 0
    for i, line in enumerate(lines):
        if line.lstrip().startswith("#") and search_text.lower() in line.lower():
            found = True
            header_level = len(line.split()[0]) # e.g. '##' -> 2
            continue
        if found:
            # Stop if we hit a header of same or higher level
            if line.lstrip().startswith("#"):
                current_level = len(line.split()[0])
                if current_level <= header_level:
                    break
            section.append(line)

    if found:
        return "\n".join(section).strip()

    # 2. Try as Numbered List Item (for the 11 questions)
    found = False
    for i, line in enumerate(lines):
        # Look for "1. **Where are we?**" or similar at the START of the line
        if (line.startswith(tuple(f"{n}." for n in range(1, 13)))) and search_text.lower() in line.lower():
            found = True
            continue
        if found:
            # Stop if we hit the next numbered item (no indentation) or a header
            if (line.startswith(tuple(f"{n}." for n in range(1, 13)))) or line.startswith("#"):
                break
            section.append(line)

    return "\n".join(section).strip()


def get_orientation_snapshot() -> Dict[str, Any]:
    """Assembles the 11-question orientation snapshot."""

    # Load base documents
    contract_content = ""
    if os.path.exists(CONTRACT_PATH):
        with open(CONTRACT_PATH, "r") as f:
            contract_content = f.read()

    runtime_map = ""
    if os.path.exists(RUNTIME_MAP_PATH):
        with open(RUNTIME_MAP_PATH, "r") as f:
            runtime_map = f.read()

    git_info = get_git_info()
    ledger_info = get_ledger_status()

    # Try to find Active Handoff context dynamically
    packets_dir = "docs/planning/project_packets"
    handoff_summary = "Not found"
    if os.path.exists(packets_dir):
        # Look for 00_ACTIVE_HANDOFF.md in subdirectories, sorted by name descending (highest number first)
        packet_dirs = sorted([d for d in os.listdir(packets_dir) if os.path.isdir(os.path.join(packets_dir, d))], reverse=True)
        for d in packet_dirs:
            potential_handoff = os.path.join(packets_dir, d, "00_ACTIVE_HANDOFF.md")
            if os.path.exists(potential_handoff):
                with open(potential_handoff, "r") as f:
                    handoff_lines = f.readlines()
                    for line in handoff_lines:
                        if line.strip() and not line.startswith("#"):
                            handoff_summary = line.strip()
                            break
                if handoff_summary != "Not found":
                    break

    # Parse confirmed facts from contract
    contract_confirmed = parse_markdown_section(contract_content, "What is confirmed?")
    confirmed_list = []
    if contract_confirmed:
        # Simple extraction of bullet points
        confirmed_list = [line.strip("- ").strip() for line in contract_confirmed.splitlines() if line.strip().startswith("-")]

    snapshot = {
        "timestamp": datetime.now().isoformat(),
        "where_are_we": {
            "cwd": os.getcwd(),
            "git_branch": git_info["branch"],
            "git_head": git_info["head_commit"][:8],
            "git_status": "Clean" if not git_info["status_summary"] else "Modified"
        },
        "active_lane": parse_markdown_section(contract_content, "What lane is active?"),
        "confirmed_current": [
            f"Git HEAD: {git_info['recent_commit']}",
            f"Ledger Status: {ledger_info['status']} ({ledger_info.get('event_count', 0)} events)",
            f"Active Handoff: {handoff_summary}"
        ] + confirmed_list,
        "historical_context": parse_markdown_section(contract_content, "What is historical/non-authoritative?"),
        "blocked_or_unknown": parse_markdown_section(contract_content, "What is blocked or unknown?"),
        "allowed_tools": parse_markdown_section(contract_content, "What tools/capabilities are allowed?"),
        "forbidden_surfaces": parse_markdown_section(contract_content, "What should not be touched?"),
        "next_safe_move": parse_markdown_section(contract_content, "What is the next safe move?"),
        "visible_road_horizon": {
            "visible_moves": [
                "Taste-polish Orientation Snapshot v0 wording until it is clear and durable",
                "Optionally record snapshot summaries to SQLite Ledger",
                "Consider Cassandra \"where are we?\" wiring after snapshot proof"
            ],
            "branch_after": "Orientation Snapshot v0 proof results",
            "unsafe_beyond": "Chief Router ledger integration, HITL migration, retrieval receipts, side-effect receipts, runtime/service changes, Mission Control UI implementation, or broad doctrine expansion"
        },
        "north_star": parse_markdown_section(contract_content, "What is the North Star?"),
        "manifesto_posture": parse_markdown_section(contract_content, "What is the operator/Winship manifesto"),
        "runtime_status": "Not checked by this read-only snapshot (refer to docs/operations/)"
    }

    return snapshot


def render_markdown(snapshot: Dict[str, Any]):
    """Print the snapshot in Markdown format."""
    print("# OpenClaw Orientation Snapshot v0")
    print(f"*Generated: {snapshot['timestamp']}*")
    print("\n## 1. Where are we?")
    print(f"- **CWD**: `{snapshot['where_are_we']['cwd']}`")
    print(f"- **Git**: `{snapshot['where_are_we']['git_branch']}` ({snapshot['where_are_we']['git_head']})")
    print(f"- **Status**: {snapshot['where_are_we']['git_status']}")

    print("\n## 2. Active Lane")
    print(snapshot['active_lane'])

    print("\n## 3. Confirmed Current Facts")
    for fact in snapshot['confirmed_current']:
        print(f"- {fact}")

    print("\n## 4. Historical / Non-Authoritative")
    print(snapshot['historical_context'])

    print("\n## 5. Blocked or Unknown")
    print(snapshot['blocked_or_unknown'])

    print("\n## 6. Allowed Tools / Capabilities")
    print(snapshot['allowed_tools'])

    print("\n## 7. What Should Not Be Touched")
    print(snapshot['forbidden_surfaces'])

    print("\n## 8. Next Safe Move")
    print(snapshot['next_safe_move'])

    print("\n## 9. Visible Road Horizon")
    print(f"- **Visible Moves**: {', '.join(snapshot['visible_road_horizon']['visible_moves'])}")
    print(f"- **Branch After**: {snapshot['visible_road_horizon']['branch_after']}")
    print(f"- **Unsafe Beyond**: {snapshot['visible_road_horizon']['unsafe_beyond']}")

    print("\n## 10. North Star")
    print(snapshot['north_star'])

    print("\n## 11. Manifesto / Anti-Slop Posture")
    print(snapshot['manifesto_posture'])

    print("\n---\n*Status: READY_FOR_CHAT_GATED_PROMOTION*")


def main():
    use_json = "--json" in sys.argv
    snapshot = get_orientation_snapshot()

    if use_json:
        print(json.dumps(snapshot, indent=2))
    else:
        render_markdown(snapshot)


if __name__ == "__main__":
    main()
