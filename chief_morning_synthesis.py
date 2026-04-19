"""
chief_morning_synthesis.py

Builds the Chief-owned morning synthesis artifact from bounded upstream
morning-layer artifacts. This is an artifact-first writer only; Cassandra
delivery remains separate.

Writes:
  - openclaw-vault/System/Chief Morning Synthesis.md
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


VAULT_ROOT = Path("/mnt/c/OpenClawShared/openclaw-vault")
SYSTEM_DIR = VAULT_ROOT / "System"
WEBSITE_DIR = VAULT_ROOT / "Website"

OUTPUT_PATH = SYSTEM_DIR / "Chief Morning Synthesis.md"
SOURCE_MODULE = "chief_morning_synthesis.py"

MAX_SOURCE_CHARS = 6_000
MAX_LINE_CHARS = 220
FRESH_AFTER_HOURS = 12


@dataclass(frozen=True)
class UpstreamArtifact:
    label: str
    path: Path
    required: bool = True


@dataclass(frozen=True)
class ArtifactSnapshot:
    label: str
    path: Path
    exists: bool
    modified_at: str
    freshness: str
    content: str


DEFAULT_UPSTREAM_ARTIFACTS = (
    UpstreamArtifact("System Health Report", SYSTEM_DIR / "Daily Report.md"),
    UpstreamArtifact("Nightly Polish Log", SYSTEM_DIR / "Nightly Polish Log.md"),
    UpstreamArtifact("Ops Actions Context", SYSTEM_DIR / "Ops Actions Context.md"),
    UpstreamArtifact("Ops Calendar Notes", SYSTEM_DIR / "Ops Calendar Notes.md", required=False),
    UpstreamArtifact("Website QA Log", WEBSITE_DIR / "QA Log.md", required=False),
)


def _now() -> datetime:
    return datetime.now().astimezone()


def _format_dt(dt: datetime) -> str:
    return dt.isoformat(timespec="seconds")


def _freshness(path: Path, now: datetime) -> tuple[str, str]:
    try:
        modified = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).astimezone()
    except OSError:
        return "missing", "missing"

    age_hours = max(0.0, (now - modified).total_seconds() / 3600)
    modified_at = _format_dt(modified)
    if age_hours <= FRESH_AFTER_HOURS:
        return modified_at, f"fresh: source last changed {modified_at}"
    return modified_at, f"stale: source last changed {modified_at}"


def _read_snapshot(artifact: UpstreamArtifact, now: datetime) -> ArtifactSnapshot:
    modified_at, freshness = _freshness(artifact.path, now)
    if not artifact.path.exists():
        note = "missing required source" if artifact.required else "missing optional source"
        return ArtifactSnapshot(
            label=artifact.label,
            path=artifact.path,
            exists=False,
            modified_at=modified_at,
            freshness=note,
            content="",
        )

    try:
        content = artifact.path.read_text(encoding="utf-8", errors="replace")[:MAX_SOURCE_CHARS]
    except OSError:
        return ArtifactSnapshot(
            label=artifact.label,
            path=artifact.path,
            exists=False,
            modified_at=modified_at,
            freshness="unreadable source",
            content="",
        )

    return ArtifactSnapshot(
        label=artifact.label,
        path=artifact.path,
        exists=True,
        modified_at=modified_at,
        freshness=freshness,
        content=content,
    )


def _clean_candidate_lines(content: str) -> list[str]:
    lines: list[str] = []
    in_frontmatter = False
    in_code = False
    for raw in content.splitlines():
        line = raw.strip()
        if line == "---":
            in_frontmatter = not in_frontmatter
            continue
        if in_frontmatter:
            continue
        if line.startswith("```"):
            in_code = not in_code
            continue
        if not line or line.startswith("#"):
            continue
        if line.startswith("_Generated") or line.startswith("_Freshness"):
            continue
        if line.startswith("----"):
            continue
        if len(line) > MAX_LINE_CHARS:
            line = line[: MAX_LINE_CHARS - 3].rstrip() + "..."
        lines.append(line)
    return lines


def _select_lines(
    snapshots: list[ArtifactSnapshot],
    *,
    labels: tuple[str, ...],
    keywords: tuple[str, ...],
    limit: int,
) -> list[str]:
    selected: list[str] = []
    lower_keywords = tuple(keyword.lower() for keyword in keywords)
    for snapshot in snapshots:
        if snapshot.label not in labels or not snapshot.exists:
            continue
        for line in _clean_candidate_lines(snapshot.content):
            lower = line.lower()
            if lower_keywords and not any(keyword in lower for keyword in lower_keywords):
                continue
            selected.append(f"{snapshot.label}: {line}")
            if len(selected) >= limit:
                return selected
    return selected


def _fallback_lines(
    snapshots: list[ArtifactSnapshot],
    *,
    labels: tuple[str, ...],
    limit: int,
) -> list[str]:
    selected: list[str] = []
    for snapshot in snapshots:
        if snapshot.label not in labels or not snapshot.exists:
            continue
        for line in _clean_candidate_lines(snapshot.content):
            selected.append(f"{snapshot.label}: {line}")
            if len(selected) >= limit:
                return selected
    return selected


def _lines_or_none(lines: list[str], none_text: str) -> list[str]:
    if lines:
        return [f"- {line}" for line in lines]
    return [f"- {none_text}"]


def build_chief_morning_synthesis_markdown(
    *,
    now: datetime | None = None,
    upstream_artifacts: tuple[UpstreamArtifact, ...] = DEFAULT_UPSTREAM_ARTIFACTS,
) -> str:
    generated_at = now or _now()
    snapshots = [_read_snapshot(artifact, generated_at) for artifact in upstream_artifacts]

    priorities = _select_lines(
        snapshots,
        labels=("Ops Actions Context", "Nightly Polish Log"),
        keywords=("open", "pending", "ready", "priority", "queue", "approval", "follow-through"),
        limit=6,
    )
    if not priorities:
        priorities = _fallback_lines(
            snapshots,
            labels=("Ops Actions Context", "Nightly Polish Log"),
            limit=4,
        )

    blockers = _select_lines(
        snapshots,
        labels=("System Health Report", "Nightly Polish Log", "Ops Actions Context", "Website QA Log"),
        keywords=("error", "blocked", "blocker", "stale", "offline", "waiting", "approval", "unavailable"),
        limit=6,
    )

    system_ops = _select_lines(
        snapshots,
        labels=("System Health Report", "Nightly Polish Log", "Ops Actions Context"),
        keywords=("worker", "watcher", "system health", "health", "queue", "gate", "pending", "completed"),
        limit=7,
    )
    if not system_ops:
        system_ops = _fallback_lines(
            snapshots,
            labels=("System Health Report", "Nightly Polish Log", "Ops Actions Context"),
            limit=5,
        )

    schedule_qa = _select_lines(
        snapshots,
        labels=("Ops Calendar Notes", "Website QA Log"),
        keywords=("fact", "calendar", "qa", "offline", "status", "schedule", "golf", "appointment"),
        limit=6,
    )
    if not schedule_qa:
        schedule_qa = _fallback_lines(
            snapshots,
            labels=("Ops Calendar Notes", "Website QA Log"),
            limit=4,
        )

    stale_or_missing = [
        f"{snapshot.label}: {snapshot.freshness}"
        for snapshot in snapshots
        if not snapshot.exists or snapshot.freshness.startswith("stale")
    ]
    if not stale_or_missing:
        stale_or_missing = ["All selected upstream artifacts are fresh by the 24-hour synthesis rule."]

    upstream_rows = [
        f"| {snapshot.label} | `{snapshot.path}` | {snapshot.freshness} |"
        for snapshot in snapshots
    ]

    generated = _format_dt(generated_at)
    body = [
        "---",
        "type: chief-morning-synthesis",
        f"generated_at: {generated}",
        f"source_module: {SOURCE_MODULE}",
        "bounded: true",
        "---",
        "",
        "# Chief Morning Synthesis",
        "",
        f"- Generated: {generated}",
        f"- Source module: `{SOURCE_MODULE}`",
        f"- Output artifact: `{OUTPUT_PATH}`",
        f"- Bound: deterministic excerpts capped at {MAX_SOURCE_CHARS} characters per upstream artifact.",
        "",
        "## Upstream Artifacts Read",
        "",
        "| Artifact | Path | Freshness / Staleness |",
        "| --- | --- | --- |",
        *upstream_rows,
        "",
        "## Top Priorities",
        "",
        *_lines_or_none(priorities, "No concrete priorities found in the selected artifacts."),
        "",
        "## Blockers / Watchlist",
        "",
        *_lines_or_none(blockers, "No explicit blockers found in the selected artifacts."),
        "",
        "## System / Ops State",
        "",
        *_lines_or_none(system_ops, "No system or ops state found in the selected artifacts."),
        "",
        "## Schedule / QA",
        "",
        *_lines_or_none(schedule_qa, "No bounded calendar or QA artifact content found."),
        "",
        "## Confidence / What May Be Stale",
        "",
        *_lines_or_none(stale_or_missing, "No stale or missing upstream artifacts detected."),
        "",
    ]
    return "\n".join(body)


def write_chief_morning_synthesis(
    *,
    output_path: Path = OUTPUT_PATH,
    now: datetime | None = None,
    upstream_artifacts: tuple[UpstreamArtifact, ...] = DEFAULT_UPSTREAM_ARTIFACTS,
) -> Path:
    markdown = build_chief_morning_synthesis_markdown(
        now=now,
        upstream_artifacts=upstream_artifacts,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(markdown, encoding="utf-8")
    return output_path


def main() -> None:
    path = write_chief_morning_synthesis()
    print(path)


if __name__ == "__main__":
    main()
