"""
chief_ops_reporter.py

Deterministic parsing and artifact-writing logic for Ops Actions.
Extracts pending and completed items from the raw vault file to prepare
inputs for the morning synthesis.
"""

import re
from datetime import datetime
from pathlib import Path
from typing import TypedDict

# ── Paths ─────────────────────────────────────────────────────────────────────

_VAULT_SYS   = Path("/mnt/c/OpenClawShared/openclaw-vault/System")
_OPS_ACTIONS = _VAULT_SYS / "Ops Actions.md"
_OPS_ACTIONS_CONTEXT = _VAULT_SYS / "Ops Actions Context.md"

# ── Config ────────────────────────────────────────────────────────────────────

_OPS_ACTIONS_FRESH_SECONDS = 24 * 60 * 60
_FUTURE_CLOCK_SKEW_SECONDS = 5 * 60


class OpsActionsSlice(TypedDict):
    """Age-gated Ops Actions input admitted to scheduled briefings."""

    status: str
    as_of: str | None
    timestamp_source: str | None
    lines: list[str]

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


def _aware_now(now: datetime | None = None) -> datetime:
    value = now or datetime.now().astimezone()
    if value.tzinfo is None:
        return value.astimezone()
    return value


def _split_frontmatter(raw_lines: list[str]) -> tuple[dict[str, str], list[str], bool]:
    """Return simple YAML frontmatter fields and the document body.

    The Ops Actions file uses scalar metadata only, so a deliberately small
    parser avoids making scheduled briefing safety depend on a YAML package.
    """
    if not raw_lines or raw_lines[0].strip() != "---":
        return {}, raw_lines, True

    closing = next(
        (index for index, line in enumerate(raw_lines[1:], start=1) if line.strip() == "---"),
        None,
    )
    if closing is None:
        return {}, [], False

    metadata: dict[str, str] = {}
    for raw in raw_lines[1:closing]:
        if ":" not in raw:
            continue
        key, value = raw.split(":", 1)
        key = key.strip().lower()
        if not key:
            continue
        metadata[key] = value.strip().strip("\"'")
    return metadata, raw_lines[closing + 1 :], True


def _parse_as_of(value: str, *, now: datetime) -> datetime | None:
    normalized = str(value or "").strip().strip("\"'")
    if not normalized:
        return None
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=now.tzinfo)
    return parsed.astimezone(now.tzinfo)


def _action_lines(body: list[str], n_actions: int) -> list[str]:
    metadata_prefixes = (
        "type:",
        "as_of:",
        "updated:",
        "generated_at:",
        "last_updated:",
        "owner:",
        "status:",
        "slot:",
        "source_module:",
        "source_path:",
        "freshness:",
        "bounded_to_last_actions:",
        "slice_status:",
        "slice_as_of:",
        "slice_timestamp_source:",
    )
    lines: list[str] = []
    in_code = False
    for raw in body:
        stripped = raw.strip()
        if stripped.startswith("```"):
            in_code = not in_code
            continue
        if (
            in_code
            or not stripped
            or stripped.startswith("#")
            or stripped == "---"
            or any(stripped.lower().startswith(prefix) for prefix in metadata_prefixes)
        ):
            continue
        lines.append(stripped)
    return lines[-n_actions:]


def read_ops_actions_slice(
    n_actions: int = 12,
    *,
    now: datetime | None = None,
) -> OpsActionsSlice:
    """Read the bounded current slice, refusing stale or invalid action lines.

    Timestamp authority is deterministic: frontmatter ``as_of``, ``updated``,
    then ``generated_at``. File mtime is considered only when all three are
    absent. A present-but-invalid authoritative timestamp fails closed.
    """
    if not _OPS_ACTIONS.exists():
        return {
            "status": "missing",
            "as_of": None,
            "timestamp_source": None,
            "lines": [],
        }

    current = _aware_now(now)
    try:
        raw_lines = _OPS_ACTIONS.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return {
            "status": "invalid",
            "as_of": None,
            "timestamp_source": None,
            "lines": [],
        }

    frontmatter, body, frontmatter_valid = _split_frontmatter(raw_lines)
    if not frontmatter_valid:
        return {
            "status": "invalid",
            "as_of": None,
            "timestamp_source": "frontmatter:invalid",
            "lines": [],
        }
    timestamp_key = next(
        (key for key in ("as_of", "updated", "generated_at") if key in frontmatter),
        None,
    )
    if timestamp_key is not None:
        timestamp_source = f"frontmatter:{timestamp_key}"
        source_time = _parse_as_of(frontmatter[timestamp_key], now=current)
        if source_time is None:
            return {
                "status": "invalid",
                "as_of": None,
                "timestamp_source": timestamp_source,
                "lines": [],
            }
    else:
        timestamp_source = "mtime"
        try:
            source_time = datetime.fromtimestamp(
                _OPS_ACTIONS.stat().st_mtime,
                tz=current.tzinfo,
            )
        except OSError:
            return {
                "status": "invalid",
                "as_of": None,
                "timestamp_source": timestamp_source,
                "lines": [],
            }

    age_seconds = (current - source_time).total_seconds()
    if age_seconds < -_FUTURE_CLOCK_SKEW_SECONDS:
        status = "invalid"
    elif age_seconds > _OPS_ACTIONS_FRESH_SECONDS:
        status = "stale"
    else:
        status = "fresh"

    return {
        "status": status,
        "as_of": source_time.isoformat(timespec="seconds"),
        "timestamp_source": timestamp_source,
        "lines": _action_lines(body, n_actions) if status == "fresh" else [],
    }


def _slice_freshness_note(action_slice: OpsActionsSlice) -> str:
    status = action_slice["status"]
    as_of = action_slice["as_of"]
    source = action_slice["timestamp_source"]
    if status == "missing":
        return "missing: source file not found"
    if status == "invalid":
        if source:
            return f"invalid: source timestamp unreadable ({source})"
        return "invalid: source file unreadable"
    return f"{status}: source as of {as_of} ({source})"


def _read_ops_action_lines(n_actions: int = 12) -> tuple[list[str], str]:
    """Compatibility wrapper around the structured, age-gated slice."""
    action_slice = read_ops_actions_slice(n_actions)
    return action_slice["lines"], _slice_freshness_note(action_slice)


def build_action_summary(
    n_actions: int = 12,
    *,
    action_slice: OpsActionsSlice | None = None,
) -> str:
    """
    Read Ops Actions.md, classify into pending/completed, and return a
    structured summary string with counts and priority items first in Pending.
    """
    admitted = action_slice or read_ops_actions_slice(n_actions)
    lines = admitted["lines"]
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


def build_ops_actions_artifact_markdown(
    n_actions: int = 12,
    *,
    now: datetime | None = None,
    _action_slice: OpsActionsSlice | None = None,
) -> str:
    generated_at = _aware_now(now).isoformat(timespec="seconds")
    action_slice = _action_slice or read_ops_actions_slice(n_actions, now=now)
    lines = action_slice["lines"]
    freshness_note = _slice_freshness_note(action_slice)
    summary = build_action_summary(n_actions, action_slice=action_slice)
    source_path = str(_OPS_ACTIONS)
    module = "chief_ops_reporter.py"
    slice_as_of = action_slice["as_of"] or "null"
    timestamp_source = action_slice["timestamp_source"] or "null"
    status = action_slice["status"]
    if status == "fresh":
        admission_note = "Current action lines admitted from the fresh source slice."
    elif status == "stale":
        admission_note = "No current priority is claimed from this stale slice."
    else:
        admission_note = f"No current priority is claimed because the source slice is {status}."

    content = (
        "---\n"
        "type: ops-actions-context\n"
        f"generated_at: {generated_at}\n"
        f"source_module: {module}\n"
        f"source_path: {source_path}\n"
        f"slice_status: {status}\n"
        f"slice_as_of: {slice_as_of}\n"
        f"slice_timestamp_source: {timestamp_source}\n"
        f"freshness: {freshness_note}\n"
        f"bounded_to_last_actions: {n_actions}\n"
        "---\n\n"
        "# Ops Actions Context\n\n"
        f"- Generated: {generated_at}\n"
        f"- Source module: `{module}`\n"
        f"- Source: `{source_path}`\n"
        f"- Slice status: {status}; source as of {slice_as_of} via {timestamp_source}.\n"
        f"- Admission: {admission_note}\n"
        f"- Freshness: {freshness_note}\n"
        f"- Bound: last {n_actions} non-heading action lines; {len(lines)} source line(s) included.\n\n"
        "## Summary\n\n"
        "```text\n"
        f"{summary}\n"
        "```\n"
    )
    return content[:4000]


def write_ops_actions_artifact(
    n_actions: int = 12,
    *,
    now: datetime | None = None,
) -> dict:
    """
    Generate and write the Ops Actions Context.md artifact.
    Returns metadata dict including path and summary.
    """
    action_slice = read_ops_actions_slice(n_actions, now=now)
    content = build_ops_actions_artifact_markdown(
        n_actions,
        now=now,
        _action_slice=action_slice,
    )
    _OPS_ACTIONS_CONTEXT.parent.mkdir(parents=True, exist_ok=True)
    _OPS_ACTIONS_CONTEXT.write_text(content, encoding="utf-8")
    return {
        "path": str(_OPS_ACTIONS_CONTEXT),
        "summary": build_action_summary(n_actions, action_slice=action_slice),
        "markdown": content,
        "slice": action_slice,
    }

if __name__ == "__main__":
    result = write_ops_actions_artifact()
    print(f"Artifact written: {result['path']}")
