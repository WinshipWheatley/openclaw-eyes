"""Make governed product artifacts selectable, instead of unreachable.

The CHAT interpreter chooses a read-model from a hardcoded list of ten filenames.
`PRODUCT-THESIS-PROVABLE-DELEGATION-20260728.md` is not one of them, so the operator's
question about the product hypothesis could not select it — not because ranking scored
it poorly, but because it was never a candidate. The interpreter then picked the
nearest-looking entry, `chief_status_rail.json`, and answered that its contents were
unavailable. Both halves of that were true and neither was useful.

This indexes the governed `fleet_coord/PRODUCT` artifact set into a real read-model,
so the existing machinery can select and load it like any other. Nothing here knows
what the answer is, and no question is special-cased: artifacts are ranked by token
evidence exactly as read-models already are.

Two rules carried over from the rest of tonight:

* **Bounded.** Sections are clipped to a byte budget. A packet that swallows a whole
  document starves everything else in it.
* **Named failure.** A selected artifact that cannot be read produces a status, never
  a silent fallthrough. Silence is what turned a retrieval failure into a bare UNKNOWN
  in the first place.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

SCHEMA_VERSION = "product_artifact_index_v1"
READ_MODEL_ID = "product_artifact_index"

ROOT = Path(__file__).resolve().parent
READ_MODEL_PATH = ROOT / "generated" / "read_models" / "product_artifact_index.json"

#: Governed source. The shared board is authoritative — it is what the fleet reads.
DEFAULT_SOURCE_DIRS = (
    Path("/mnt/e/openclaw/fleet_coord/PRODUCT"),
)

#: Per-section and per-artifact clips. Big enough to answer, small enough to share.
SECTION_TEXT_BUDGET = 1400
ARTIFACT_TEXT_BUDGET = 6000

#: A title/heading hit outweighs a body mention. See rank_artifacts for why.
TITLE_MATCH_WEIGHT = 2.5

#: No single artifact may claim more than this many section slots. See
#: rank_sections_across — without it, one document crowds out every other.
SECTIONS_PER_ARTIFACT_CAP = 3

LOAD_OK = "OK"
LOAD_MISSING = "ARTIFACT_MISSING"
LOAD_UNREADABLE = "ARTIFACT_UNREADABLE"
LOAD_HASH_DRIFT = "ARTIFACT_HASH_DRIFT"
LOAD_FAILURES = frozenset({LOAD_MISSING, LOAD_UNREADABLE, LOAD_HASH_DRIFT})

_STOPWORDS = frozenset(
    "the a an is are was were do does did what which how why when who whom to of in on "
    "for with and or if it its this that these those you your i me my we our can could "
    "should would will shall may might be been being at by from as not no yes there here"
    .split()
)


def _tokenize(text: str) -> set[str]:
    words = re.findall(r"[a-z0-9][a-z0-9_.-]{2,}", str(text or "").lower())
    return {w.strip("._-") for w in words if w not in _STOPWORDS}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _sha256_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _clip(text: str, budget: int) -> str:
    text = str(text or "").strip()
    if len(text) <= budget:
        return text
    cut = text[:budget]
    boundary = cut.rfind("\n")
    return (cut[:boundary] if boundary > budget // 2 else cut).rstrip() + " …"


@dataclass(frozen=True)
class ArtifactSection:
    heading: str
    text: str

    def to_dict(self) -> dict[str, Any]:
        return {"heading": self.heading, "text": self.text}


@dataclass(frozen=True)
class ArtifactRow:
    source_ref: str
    path: str
    title: str
    sha256: str
    size_bytes: int
    modified_at: str
    age_days: float
    sections: tuple[ArtifactSection, ...] = ()
    bounded_text: str = ""

    def match_tokens(self) -> set[str]:
        tokens = _tokenize(self.title) | _tokenize(Path(self.path).name)
        for section in self.sections:
            tokens |= _tokenize(section.heading)
        tokens |= _tokenize(self.bounded_text)
        return tokens

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_ref": self.source_ref,
            "path": self.path,
            "title": self.title,
            "sha256": self.sha256,
            "size_bytes": self.size_bytes,
            "modified_at": self.modified_at,
            "age_days": round(self.age_days, 3),
            "sections": [s.to_dict() for s in self.sections],
            "bounded_text": self.bounded_text,
        }


def _split_sections(body: str) -> tuple[ArtifactSection, ...]:
    """Markdown headings become addressable sections; prose before the first stays."""

    sections: list[ArtifactSection] = []
    heading = ""
    buffer: list[str] = []

    def flush() -> None:
        text = _clip("\n".join(buffer), SECTION_TEXT_BUDGET)
        if text:
            sections.append(ArtifactSection(heading or "(preamble)", text))

    for line in str(body or "").splitlines():
        match = re.match(r"^(#{1,4})\s+(.*)$", line)
        if match:
            flush()
            heading = match.group(2).strip()
            buffer = []
            continue
        buffer.append(line)
    flush()
    return tuple(sections)


def _title_for(path: Path, body: str) -> str:
    for line in body.splitlines():
        match = re.match(r"^#\s+(.*)$", line)
        if match and match.group(1).strip():
            return match.group(1).strip()
    return path.stem.replace("-", " ").replace("_", " ")


def build_index(
    source_dirs: Sequence[Path] | None = None, *, now: datetime | None = None
) -> tuple[ArtifactRow, ...]:
    """Index every governed markdown artifact. Unreadable files are skipped, not faked."""

    moment = now or datetime.now(timezone.utc)
    rows: list[ArtifactRow] = []
    for directory in (source_dirs or DEFAULT_SOURCE_DIRS):
        directory = Path(directory)
        if not directory.is_dir():
            continue
        for path in sorted(directory.glob("*.md")):
            try:
                data = path.read_bytes()
                body = data.decode("utf-8", errors="replace")
                stat = path.stat()
            except OSError:
                continue
            modified = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
            rows.append(
                ArtifactRow(
                    source_ref=f"fleet_coord/PRODUCT/{path.name}",
                    path=str(path),
                    title=_title_for(path, body),
                    sha256=_sha256_bytes(data),
                    size_bytes=len(data),
                    modified_at=modified.isoformat(timespec="seconds").replace("+00:00", "Z"),
                    age_days=max(0.0, (moment - modified).total_seconds() / 86400.0),
                    sections=_split_sections(body),
                    bounded_text=_clip(body, ARTIFACT_TEXT_BUDGET),
                )
            )
    return tuple(rows)


def _as_row(value: Any) -> ArtifactRow | None:
    """Accept either a live ArtifactRow or a row read back from the read-model."""

    if isinstance(value, ArtifactRow):
        return value
    if not isinstance(value, Mapping):
        return None
    sections = tuple(
        ArtifactSection(str(s.get("heading") or ""), str(s.get("text") or ""))
        for s in (value.get("sections") or ())
        if isinstance(s, Mapping)
    )
    return ArtifactRow(
        source_ref=str(value.get("source_ref") or ""),
        path=str(value.get("path") or ""),
        title=str(value.get("title") or ""),
        sha256=str(value.get("sha256") or ""),
        size_bytes=int(value.get("size_bytes") or 0),
        modified_at=str(value.get("modified_at") or ""),
        age_days=float(value.get("age_days") or 0.0),
        sections=sections,
        bounded_text=str(value.get("bounded_text") or ""),
    )


def rank_sections(
    row: ArtifactRow, query: str, *, limit: int = 2, clip: int = 320
) -> tuple[ArtifactSection, ...]:
    """The query-relevant sections of one artifact, clipped hard.

    A 1024-token front-door context cannot take a whole document, and injecting one
    would starve every other fact in the packet. Sections are the unit that fits: a
    heading is a claim about what its text answers, so ranking them against the
    question is cheap and the result is small enough to share the budget.
    """

    query_tokens = _tokenize(query)
    if not row.sections:
        return ()
    if not query_tokens:
        return tuple(
            ArtifactSection(s.heading, _clip(s.text, clip)) for s in row.sections[:limit]
        )

    def score(section: ArtifactSection) -> float:
        heading_hits = len(query_tokens & _tokenize(section.heading))
        body_hits = len(query_tokens & _tokenize(section.text))
        return heading_hits * TITLE_MATCH_WEIGHT + body_hits

    ranked = sorted(row.sections, key=lambda s: (-score(s), s.heading))
    keep = [s for s in ranked if score(s) > 0][:limit] or list(ranked[:limit])
    return tuple(ArtifactSection(s.heading, _clip(s.text, clip)) for s in keep)


def rank_sections_across(
    index: Sequence[Any], query: str, *, limit: int = 3, clip: int = 320
) -> tuple[tuple[ArtifactRow, ArtifactSection], ...]:
    """Rank SECTIONS across every artifact, not documents then sections.

    Document-first ranking answers "which file is this question about", which is a
    different question from "which passage answers it". The operator's real prompt
    opens with an instruction preamble whose words legitimately match a document
    about acceptance testing, so the document-first order put the report ahead of the
    thesis the question was actually about — the ranker was right about the text and
    wrong about the need.

    Sections do not have that problem: a heading is a claim about what its passage
    answers, so the passages that match the question win regardless of which file
    they live in. Returning () on no overlap is unchanged — an honest empty still
    beats dragging in a paragraph because it shares the word "the".
    """

    query_tokens = _tokenize(query)
    rows = tuple(r for r in (_as_row(item) for item in index) if r is not None)
    if not query_tokens or not rows:
        return ()

    scored: list[tuple[float, str, ArtifactRow, ArtifactSection]] = []
    for row in rows:
        freshness = 1.0 / (1.0 + (row.age_days / 30.0))
        for section in row.sections:
            heading_hits = len(query_tokens & _tokenize(section.heading))
            body_hits = len(query_tokens & _tokenize(section.text))
            score = (heading_hits * TITLE_MATCH_WEIGHT + body_hits) * freshness
            if score > 0:
                scored.append((score, f"{row.source_ref}|{section.heading}", row, section))

    scored.sort(key=lambda item: (-item[0], item[1]))

    # Diversity cap. Without it one document takes most of the slots and the others
    # are unrepresented: the operator's prompt opens with an instruction preamble
    # whose words match the acceptance report, so that report claimed three of six
    # slots and the thesis sections answering "hypothesis" and "smallest v1" never
    # appeared. The model then correctly refused two of three sub-questions for lack
    # of evidence. Standard result diversification, not a rule about any document.
    per_doc: dict[str, int] = {}
    picked: list[tuple[float, str, ArtifactRow, ArtifactSection]] = []
    for item in scored:
        ref = item[2].source_ref
        if per_doc.get(ref, 0) >= SECTIONS_PER_ARTIFACT_CAP:
            continue
        per_doc[ref] = per_doc.get(ref, 0) + 1
        picked.append(item)
        if len(picked) >= limit:
            break
    # If the cap starved the result (only one artifact matched at all), fall back to
    # pure rank rather than return less evidence than the budget allows.
    if len(picked) < limit:
        seen = {id(item) for item in picked}
        picked.extend(item for item in scored if id(item) not in seen)
        picked = picked[:limit]

    return tuple(
        (row, ArtifactSection(section.heading, _clip(section.text, clip)))
        for _s, _k, row, section in picked
    )


def rank_artifacts(
    index: Sequence[Any], query: str, *, limit: int = 2
) -> tuple[ArtifactRow, ...]:
    """Deterministic token-evidence ranking. Empty query or no overlap returns ().

    Same shape as the existing read-model demand index: rare tokens are strong
    evidence, common ones are near-noise, freshness breaks ties. Returning () when
    nothing matches is deliberate — an honest empty beats dragging an unrelated
    document into the packet.
    """

    query_tokens = _tokenize(query)
    rows = tuple(r for r in (_as_row(item) for item in index) if r is not None)
    if not query_tokens or not rows:
        return ()
    index = rows

    total = len(index) or 1
    frequency: dict[str, int] = {}
    for row in index:
        for token in row.match_tokens():
            frequency[token] = frequency.get(token, 0) + 1

    def score(row: ArtifactRow) -> float:
        matched = query_tokens & row.match_tokens()
        if not matched:
            return 0.0
        # A document whose TITLE or a section HEADING matches is about the subject.
        # One that merely mentions the words somewhere in its body may only be
        # discussing it. General principle, not a rule about any one document:
        # without it, a report ABOUT a thesis outranks the thesis.
        headline_tokens = _tokenize(row.title) | {
            t for section in row.sections for t in _tokenize(section.heading)
        }
        relevance = sum(
            math.log((total + 1) / (frequency.get(token, 1) + 0.5))
            * (TITLE_MATCH_WEIGHT if token in headline_tokens else 1.0)
            for token in matched
        )
        return relevance * (1.0 / (1.0 + (row.age_days / 30.0)))

    scored = [(score(row), row) for row in index]
    hits = [(s, r) for s, r in scored if s > 0]
    hits.sort(key=lambda pair: (-pair[0], pair[1].source_ref))
    return tuple(row for _s, row in hits[:limit])


def load_artifact(row: Mapping[str, Any]) -> tuple[str, str, str]:
    """Load a selected artifact's text. Returns ``(status, text, detail)``.

    A selected artifact that cannot be read is a NAMED failure. Falling through
    silently is what let a retrieval failure reach the operator as a bare UNKNOWN.
    """

    path = Path(str(row.get("path") or ""))
    if not path.exists():
        return LOAD_MISSING, "", f"no file at {path}"
    try:
        data = path.read_bytes()
    except OSError as exc:
        return LOAD_UNREADABLE, "", f"{type(exc).__name__}: {exc}"
    expected = str(row.get("sha256") or "")
    if expected and _sha256_bytes(data) != expected:
        return LOAD_HASH_DRIFT, "", "artifact changed since it was indexed"
    return LOAD_OK, _clip(data.decode("utf-8", errors="replace"), ARTIFACT_TEXT_BUDGET), ""


def build_read_model(index: Sequence[ArtifactRow] | None = None) -> dict[str, Any]:
    rows = index if index is not None else build_index()
    return {
        "read_model_id": READ_MODEL_ID,
        "schema_version": SCHEMA_VERSION,
        "generated_at": utc_now(),
        "doctrine": (
            "Governed product artifacts are indexed so the harness can SELECT them. "
            "Selection is token evidence, never a special case for a question."
        ),
        "artifact_count": len(rows),
        "artifacts": [row.to_dict() for row in rows],
        "source_refs": [row.source_ref for row in rows],
    }


def export_read_model(path: str | Path | None = None, index: Sequence[ArtifactRow] | None = None) -> Path:
    target = Path(path) if path else READ_MODEL_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(build_read_model(index), indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return target


def load_index_rows(path: str | Path | None = None) -> tuple[dict[str, Any], ...]:
    target = Path(path) if path else READ_MODEL_PATH
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return ()
    rows = payload.get("artifacts")
    return tuple(r for r in rows if isinstance(r, Mapping)) if isinstance(rows, list) else ()


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Index governed product artifacts.")
    parser.add_argument("--export", action="store_true")
    parser.add_argument("--query", default="")
    args = parser.parse_args(argv)

    index = build_index()
    if args.export:
        print(f"wrote {export_read_model(index=index)} ({len(index)} artifacts)")
    if args.query:
        for row in rank_artifacts(index, args.query):
            print(f"  {row.source_ref}  ({row.title})")
    if not args.export and not args.query:
        for row in index:
            print(f"  {row.source_ref}  sections={len(row.sections)}  {row.sha256[:19]}")
    return 0


__all__ = [
    "ARTIFACT_TEXT_BUDGET",
    "ArtifactRow",
    "ArtifactSection",
    "LOAD_FAILURES",
    "LOAD_HASH_DRIFT",
    "LOAD_MISSING",
    "LOAD_OK",
    "LOAD_UNREADABLE",
    "READ_MODEL_PATH",
    "SECTION_TEXT_BUDGET",
    "build_index",
    "build_read_model",
    "export_read_model",
    "load_artifact",
    "load_index_rows",
    "rank_artifacts",
]


if __name__ == "__main__":
    raise SystemExit(main())
