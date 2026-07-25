"""Read-model DEMAND INDEX — progressive disclosure over the read-model library.

The problem this closes: `generated/read_models/` holds hundreds of files with no
semantic index, so a consumer cannot deterministically select the one or two
read-models relevant to a question. It must either load everything (bloat) or
guess a filename (confabulation). Both silently force a large model.

The shape:

    small always-loaded INDEX  ->  deterministic SELECTION  ->  lazy load of only
    the selected read-model(s)

This module builds the index. It carries no read-model payload content: rows hold
identity, topic tags, key field names, freshness and size only.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from generated_read_model_files import (
    DEFAULT_GENERATED_READ_MODEL_ROOT,
    ROOT,
    iter_safe_generated_read_models,
    resolve_repo_path,
)


# Right-sizing budget for one selection (bytes). Tuned so a small local
# model receives a useful slice without a bloated context.
DEFAULT_SELECTION_BYTE_BUDGET = 60_000

_STOPWORDS = frozenset(
    """a an and are as at be by do does for from get give has have how i in is it
    its me my of on or our that the their there this to was we what when where
    which who why will with you your""".split()
)


@dataclass(frozen=True)
class ReadModelIndexRow:
    """One compact index row. Never carries payload content."""

    id: str
    relative_path: str
    key_fields: tuple[str, ...]
    size_bytes: int

    @property
    def topic_tags(self) -> tuple[str, ...]:
        """Selection tags derived from the id — the spine's whole payload."""

        return tuple(sorted(_tokenize(self.id)))

    def match_tokens(self) -> frozenset[str]:
        """Tokens this read-model can be selected by."""

        tokens: set[str] = set()
        for source in (self.id, *self.key_fields):
            tokens.update(_tokenize(source))
        return frozenset(tokens)


def _tokenize(text: str) -> set[str]:
    """Split into lowercase word tokens, dropping stopwords and noise."""

    cleaned = "".join(char.lower() if char.isalnum() else " " for char in str(text))
    return {
        token
        for token in cleaned.split()
        if len(token) > 2 and token not in _STOPWORDS
    }


def select_read_models(
    index: tuple[ReadModelIndexRow, ...],
    query: str,
    *,
    limit: int = 3,
    max_bytes: int | None = DEFAULT_SELECTION_BYTE_BUDGET,
) -> tuple[ReadModelIndexRow, ...]:
    """Deterministically select the read-models relevant to ``query``.

    Selection is harness-owned: exact token overlap against the index, not a
    model guess. Returns ``()`` when nothing matches — an honest empty answer
    beats loading the library or inventing a filename.

    ``max_bytes`` keeps the selection right-sized: a candidate that would push
    the payload over budget is skipped rather than silently bloating the packet.
    """

    query_tokens = _tokenize(query)
    if not query_tokens:
        return ()
    matches = sorted(
        (
            (score, row)
            for score, row in (
                (len(query_tokens & row.match_tokens()), row) for row in index
            )
            if score > 0
        ),
        key=lambda item: (-item[0], item[1].id),
    )
    selected: list[ReadModelIndexRow] = []
    spent = 0
    for _, row in matches:
        if len(selected) >= limit:
            break
        if max_bytes is not None and spent + row.size_bytes > max_bytes:
            continue
        selected.append(row)
        spent += row.size_bytes
    return tuple(selected)


@dataclass(frozen=True)
class DemandSelection:
    """Result of one demand selection. ``error`` is never disguised as no-match."""

    rows: tuple[ReadModelIndexRow, ...]
    error: str | None = None


def select_demand_read_models(
    source_root: str | Path,
    *,
    question: str,
    already_loaded: Any = (),
    limit: int = 3,
    max_bytes: int | None = DEFAULT_SELECTION_BYTE_BUDGET,
) -> DemandSelection:
    """Shared demand selection for every agent packet.

    One place owns resolving the root, excluding what the caller already loads,
    honest failure reporting, and the byte budget — so no agent can re-introduce
    the "broken root looks like nothing matched" defect.
    """

    if not str(question or "").strip():
        return DemandSelection(())
    already = {str(name) for name in (already_loaded or ())}
    try:
        # Production passes a repo-relative nested root; an unresolved one would
        # silently find nothing.
        resolved = Path(source_root).resolve()
        index = build_demand_index(resolved, repo_root=resolved.parent)
        candidates = tuple(row for row in index if row.relative_path not in already)
        return DemandSelection(
            select_read_models(candidates, question, limit=limit, max_bytes=max_bytes)
        )
    except Exception as exc:
        return DemandSelection((), error=type(exc).__name__)


def index_rows_json(index: tuple[ReadModelIndexRow, ...]) -> list[dict[str, Any]]:
    """Full index rows — the on-demand detail layer."""

    return [
        {
            "id": row.id,
            "path": row.relative_path,
            "tags": list(row.topic_tags),
            "key_fields": list(row.key_fields),
            "bytes": row.size_bytes,
        }
        for row in index
    ]


def index_spine(index: tuple[ReadModelIndexRow, ...]) -> list[dict[str, Any]]:
    """The SMALL always-loaded layer: identity + topic tags only.

    Deliberately omits ``key_fields`` — those are the bulk of the index and are
    only needed once a read-model is already a candidate.
    """

    return [
        {"id": row.id, "tags": list(row.topic_tags), "bytes": row.size_bytes}
        for row in index
    ]


def _key_fields(payload: Any) -> tuple[str, ...]:
    if isinstance(payload, dict):
        return tuple(sorted(str(key) for key in payload))
    return ()


def _load_payload(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _library_signature(root: Path) -> tuple[Any, ...]:
    """Cheap fingerprint of the library — stat only, no payload parsing."""

    entries: list[tuple[str, int, int]] = []
    try:
        with __import__("os").scandir(root) as scan:
            for entry in scan:
                if not entry.name.endswith(".json") or entry.name.startswith("_"):
                    continue
                stat_result = entry.stat()
                entries.append(
                    (entry.name, stat_result.st_size, int(stat_result.st_mtime_ns))
                )
    except OSError:
        return ()
    return tuple(sorted(entries))


_INDEX_CACHE: dict[str, tuple[tuple[Any, ...], tuple[ReadModelIndexRow, ...]]] = {}


def build_demand_index(
    source_root: str | Path = DEFAULT_GENERATED_READ_MODEL_ROOT,
    *,
    repo_root: str | Path = ROOT,
) -> tuple[ReadModelIndexRow, ...]:
    """Build one index row per safe JSON read-model under ``source_root``.

    Cached on a stat-only signature: a packet build re-uses the existing index
    unless the library actually changed, so selection stays cheap per turn.
    """

    root = resolve_repo_path(source_root, repo_root=repo_root)
    cache_key = root.as_posix()
    signature = _library_signature(root)
    cached = _INDEX_CACHE.get(cache_key)
    if cached is not None and cached[0] == signature:
        return cached[1]
    rows: list[ReadModelIndexRow] = []
    for path in iter_safe_generated_read_models(root, repo_root=repo_root):
        if path.suffix.lower() != ".json":
            continue
        if path.name.startswith("_"):
            # Index artifacts (``_INDEX.json``) never index themselves.
            continue
        rows.append(
            ReadModelIndexRow(
                id=path.stem,
                relative_path=path.relative_to(root).as_posix(),
                key_fields=_key_fields(_load_payload(path)),
                size_bytes=path.stat().st_size,
            )
        )
    index = tuple(rows)
    _INDEX_CACHE[cache_key] = (signature, index)
    return index


INDEX_ARTIFACT_NAME = "_INDEX.json"
SPINE_ARTIFACT_NAME = "_INDEX_SPINE.json"


def write_index_artifacts(
    source_root: str | Path = DEFAULT_GENERATED_READ_MODEL_ROOT,
    *,
    repo_root: str | Path = ROOT,
) -> dict[str, Any]:
    """Regenerate the index artifacts. Safe to re-run; never hand-maintained."""

    root = resolve_repo_path(source_root, repo_root=repo_root)
    rows = build_demand_index(root, repo_root=repo_root)
    (root / INDEX_ARTIFACT_NAME).write_text(
        json.dumps(index_rows_json(rows), indent=2, sort_keys=True), encoding="utf-8"
    )
    (root / SPINE_ARTIFACT_NAME).write_text(
        json.dumps(index_spine(rows), separators=(",", ":"), sort_keys=True),
        encoding="utf-8",
    )
    return {"rows": len(rows), "root": root.as_posix()}


if __name__ == "__main__":  # pragma: no cover - operational entry point
    print(json.dumps(write_index_artifacts(), indent=2))
