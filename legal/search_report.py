"""Markdown export for local legal search results."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from legal.local_search import search_extracted_text
from legal.path_guard import canonicalize_matter_root, resolve_matter_child


AUDIT_FILENAME = "audit.jsonl"
EXPORTS_DIRECTORY = "exports"


def export_search_report(
    matter_root: str | Path,
    query: str,
    *,
    report_name: str | None = None,
    max_results: int = 20,
    snippet_chars: int = 80,
) -> dict[str, Any]:
    """Export a deterministic Markdown report for local search results."""

    root = canonicalize_matter_root(matter_root)
    results = search_extracted_text(
        root,
        query,
        max_results=max_results,
        snippet_chars=snippet_chars,
    )
    exports_dir = resolve_matter_child(root, root / EXPORTS_DIRECTORY, label="exports directory")
    exports_dir.mkdir(exist_ok=True)
    report_path = exports_dir / _report_filename(query, report_name)
    created_at = _utc_now()

    report_path.write_text(
        _render_markdown_report(query, results, created_at),
        encoding="utf-8",
    )
    _append_audit(
        root / AUDIT_FILENAME,
        {
            "event": "search_report_exported",
            "query": query,
            "result_count": len(results),
            "report_path": str(report_path),
            "created_at": created_at,
        },
    )
    return {
        "query": query,
        "result_count": len(results),
        "report_path": str(report_path),
        "created_at": created_at,
    }


def _report_filename(query: str, report_name: str | None) -> str:
    base = report_name if report_name and report_name.strip() else f"search-report-{query}"
    slug = _slugify(Path(base).name)
    if not slug:
        slug = _slugify(f"search-report-{query}")
    if not slug.endswith(".md"):
        slug = f"{slug}.md"
    return slug


def _slugify(value: str) -> str:
    without_suffix = value[:-3] if value.lower().endswith(".md") else value
    slug = re.sub(r"[^A-Za-z0-9_-]+", "-", without_suffix.strip()).strip("-")
    return slug.lower()


def _render_markdown_report(
    query: str,
    results: list[dict[str, Any]],
    created_at: str,
) -> str:
    lines = [
        "# Legal Search Report",
        "",
        f"- Query: `{query}`",
        f"- Result count: {len(results)}",
        f"- Created at: {created_at}",
        "",
    ]
    if not results:
        lines.extend(["No results found.", ""])
        return "\n".join(lines)

    for index, result in enumerate(results, start=1):
        lines.extend(
            [
                f"## Result {index}",
                "",
                f"- Source ID: `{result['source_id']}`",
                f"- Original filename: `{result['original_filename']}`",
                f"- SHA-256: `{result['sha256']}`",
                f"- Match count: {result['match_count']}",
                "",
                "### Snippets",
                "",
            ]
        )
        for snippet in result["snippets"]:
            lines.extend(["```text", snippet, "```", ""])
    return "\n".join(lines)


def _append_audit(path: Path, entry: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, sort_keys=True))
        handle.write("\n")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
