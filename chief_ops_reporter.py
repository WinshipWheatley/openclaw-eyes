"""
chief_ops_reporter.py

Deterministic parsing and artifact-writing logic for Ops Actions.
Extracts pending and completed items from the raw vault file to prepare
inputs for the morning synthesis.
"""

import re
from datetime import datetime
from pathlib import Path

# ── Paths ─────────────────────────────────────────────────────────────────────

_VAULT_SYS   = Path("/mnt/c/OpenClawShared/openclaw-vault/System")
_OPS_ACTIONS = _VAULT_SYS / "Ops Actions.md"
_OPS_ACTIONS_CONTEXT = _VAULT_SYS / "Ops Actions Context.md"

# ── Config ────────────────────────────────────────────────────────────────────

_OPS_ACTIONS_FRESH_SECONDS = 24 * 60 * 60

_DONE_RE = re.compile(
    r"\[done\]|\[completed\]|\[x\]|✓|~~.+~~|\(done\)",
    re.IGNORECASE,
)
_PRIORITY_RE = re.compile(
    r"\burgent\b|\basap\b|\bcritical\b|\bhigh.?priority\b|\btoday\b|\boverdue\b",
    re.IGNORECASE,
)

# ── Logic ─────────────────────────────────────────────────────────────────────

def classify_ops_actions(lines: list[str]) -> tuple[list[str], list[str]]:
    """
    Split action lines into (pending, completed).
    Lines matching _DONE_RE are completed; all others are pending.
    Pending list is sorted: priority items first.
    """
    pending: list[str] = []
    completed: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if _DONE_RE.search(stripped):
            completed.append(stripped)
        else:
            pending.append(stripped)
    pending.sort(key=lambda l: (0 if _PRIORITY_RE.search(l) else 1))
    return pending, completed


def _read_ops_action_lines(n_actions: int = 12) -> tuple[list[str], str]:
    if not _OPS_ACTIONS.exists():
        return [], "missing: source file not found"

    raw = _OPS_ACTIONS.read_text(encoding="utf-8").splitlines()
    lines = [
        l.strip() for l in raw
        if l.strip() and not l.startswith("#") and not l.startswith("---")
    ][-n_actions:]

    try:
        source_mtime = datetime.fromtimestamp(_OPS_ACTIONS.stat().st_mtime)
        age_seconds = (datetime.now() - source_mtime).total_seconds()
        if age_seconds > _OPS_ACTIONS_FRESH_SECONDS:
            note = f"stale: source last changed {source_mtime.isoformat(timespec='seconds')}"
        else:
            note = f"fresh: source last changed {source_mtime.isoformat(timespec='seconds')}"
    except Exception:
        note = "unknown: source timestamp unreadable"
    return lines, note


def build_action_summary(n_actions: int = 12) -> str:
    """
    Read Ops Actions.md, classify into pending/completed, and return a
    structured summary string with counts and priority items first in Pending.
    """
    lines, _freshness_note = _read_ops_action_lines(n_actions)
    pending, completed = classify_ops_actions(lines)

    parts: list[str] = []
    parts.append(f"Pending ({len(pending)}):")
    if pending:
        for item in pending:
            marker = "[PRIORITY] " if _PRIORITY_RE.search(item) else ""
            parts.append(f"  {marker}{item}")
    else:
        parts.append("  (none)")

    parts.append(f"Completed ({len(completed)}):")
    if completed:
        for item in completed:
            parts.append(f"  {item}")
    else:
        parts.append("  (none)")

    return "\n".join(parts)


def build_ops_actions_artifact_markdown(n_actions: int = 12) -> str:
    generated_at = datetime.now().isoformat(timespec="seconds")
    lines, freshness_note = _read_ops_action_lines(n_actions)
    summary = build_action_summary(n_actions)
    source_path = str(_OPS_ACTIONS)
    module = "chief_ops_reporter.py"

    content = (
        "---\n"
        "type: ops-actions-context\n"
        f"generated_at: {generated_at}\n"
        f"source_module: {module}\n"
        f"source_path: {source_path}\n"
        f"freshness: {freshness_note}\n"
        f"bounded_to_last_actions: {n_actions}\n"
        "---\n\n"
        "# Ops Actions Context\n\n"
        f"- Generated: {generated_at}\n"
        f"- Source module: `{module}`\n"
        f"- Source: `{source_path}`\n"
        f"- Freshness: {freshness_note}\n"
        f"- Bound: last {n_actions} non-heading action lines; {len(lines)} source line(s) included.\n\n"
        "## Summary\n\n"
        "```text\n"
        f"{summary}\n"
        "```\n"
    )
    return content[:4000]


def write_ops_actions_artifact(n_actions: int = 12) -> dict:
    """
    Generate and write the Ops Actions Context.md artifact.
    Returns metadata dict including path and summary.
    """
    content = build_ops_actions_artifact_markdown(n_actions)
    _OPS_ACTIONS_CONTEXT.parent.mkdir(parents=True, exist_ok=True)
    _OPS_ACTIONS_CONTEXT.write_text(content, encoding="utf-8")
    return {
        "path": str(_OPS_ACTIONS_CONTEXT),
        "summary": build_action_summary(n_actions),
        "markdown": content,
    }

if __name__ == "__main__":
    result = write_ops_actions_artifact()
    print(f"Artifact written: {result['path']}")
