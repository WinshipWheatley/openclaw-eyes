"""OpenClaw bounded Markdown body ingest and work-query read model.

This extends the metadata-first Work Terrain / Markdown Atlas substrate with a
small body-reading lane for allowlisted repo Markdown. It does not scan broad
private roots, export full bodies, promote truth, mutate files, launch tools,
or grant action authority.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
DEFAULT_EXPORT_ROOT = Path("generated/read_models")

SCHEMA_VERSION = "openclaw_markdown_body_ingest_query_v0"
READ_MODEL_ID = "openclaw_markdown_body_ingest_query"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
OPERATOR_EXPORT_NAME = f"{READ_MODEL_ID}_OPERATOR.md"

DEFAULT_MARKDOWN_ROOTS = (
    "AGENTS.md",
    "OPENCLAW_RUNTIME.md",
    "USER.md",
    "CORE_ARCHITECTURE_PRINCIPLES.md",
    "README.md",
    "generated/read_models",
    "docs",
    "Operator",
)

SUBSTRATE_REFS = (
    "corpus_atlas.py",
    "markdown_atlas_scope_expansion.py",
    "openclaw_work_terrain_query_contract.py",
    "openclaw_work_terrain_relationship_index.py",
    "generated/read_models/openclaw_work_terrain_query_contract.json",
    "generated/read_models/markdown_atlas_scope_expansion.json",
)

MAX_DOCS_DEFAULT = 250
MAX_BODY_BYTES_DEFAULT = 64_000
MAX_SNIPPETS_PER_RESULT = 3
MAX_RESULTS_DEFAULT = 12
MAX_SNIPPET_CHARS = 240

PER_ROOT_DOC_LIMITS = {
    "generated/read_models": 100,
    "docs": 120,
    "Operator": 24,
}

BLOCKED_PATH_PARTS = {
    ".git",
    ".google-secrets",
    ".gnupg",
    ".ssh",
    ".venv",
    "__pycache__",
    "appdata",
    "cpa",
    "finance",
    "legal",
    "legal_discovery",
    "node_modules",
    "private",
    "secrets",
    "tax",
    "vault",
    "vaults",
}

BLOCKED_FILE_HINTS = (
    ".env",
    "credential",
    "credentials",
    "private_key",
    "secret",
    "token",
)

STOPWORDS = {
    "about",
    "after",
    "all",
    "and",
    "are",
    "for",
    "from",
    "how",
    "into",
    "markdown",
    "openclaw",
    "show",
    "that",
    "the",
    "this",
    "what",
    "when",
    "where",
    "which",
    "with",
    "work",
}

AUTHORITY_BOUNDARY = {
    "action_authority_granted": False,
    "truth_promotion_allowed": False,
    "file_move_allowed": False,
    "file_delete_allowed": False,
    "file_rename_allowed": False,
    "file_rewrite_allowed": False,
    "broad_private_root_scan_allowed": False,
    "c_drive_scan_allowed": False,
    "legal_discovery_access_allowed": False,
    "credential_store_access_allowed": False,
    "model_api_execution_allowed": False,
    "network_operation_allowed": False,
    "git_push_pull_fetch_allowed": False,
    "tool_execution_allowed": False,
    "runtime_dispatch_allowed": False,
    "agent_activation_allowed": False,
    "stable_map_update_allowed": False,
}


@dataclass(frozen=True)
class MarkdownBodyDocumentCard:
    doc_id: str
    relative_path: str
    title: str
    source_kind: str
    size_bytes: int
    bounded_body_sha256: str
    body_bytes_read: int
    body_truncated: bool
    heading_count: int
    headings_preview: tuple[str, ...]
    top_terms: tuple[str, ...]
    body_read: bool
    sensitivity_status: str
    body_storage_policy: str
    legal_discovery_excluded: bool
    action_authority_granted: bool
    runtime_dispatch_allowed: bool


@dataclass(frozen=True)
class MarkdownBodyQueryExportResult:
    schema_version: str
    json_path: str
    operator_path: str
    document_count: int
    result_count: int
    body_read_performed: bool
    full_body_exported: bool
    action_authority_granted: bool


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _content_hash(payload: dict[str, Any]) -> str:
    clone = json.loads(stable_json(payload))
    clone.get("machine_proof", {}).pop("content_hash", None)
    return "sha256:" + hashlib.sha256(stable_json(clone).encode("utf-8")).hexdigest()


def _sha256_text(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def _repo_relative(repo_root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _is_blocked_relative_path(relative_path: str) -> bool:
    parts = [part.lower() for part in Path(relative_path).parts]
    if any(blocked in part for part in parts for blocked in BLOCKED_PATH_PARTS):
        return True
    lowered = relative_path.lower()
    return any(hint in lowered for hint in BLOCKED_FILE_HINTS)


def _iter_markdown_paths(repo_root: Path, roots: tuple[str, ...], max_docs: int) -> list[Path]:
    candidates: list[Path] = []
    seen: set[str] = set()
    for root_ref in roots:
        root_added = 0
        root_limit = min(PER_ROOT_DOC_LIMITS.get(root_ref, max_docs), max_docs - len(candidates))
        if root_limit <= 0:
            break
        root = repo_root / root_ref
        if not root.exists():
            continue
        paths = [root] if root.is_file() else sorted(root.rglob("*.md"))
        for path in paths:
            if not path.is_file() or path.suffix.lower() != ".md":
                continue
            relative = _repo_relative(repo_root, path)
            if _is_blocked_relative_path(relative):
                continue
            if relative in seen:
                continue
            seen.add(relative)
            candidates.append(path)
            root_added += 1
            if len(candidates) >= max_docs:
                return candidates
            if root_added >= root_limit:
                break
    return candidates


def _read_text_bounded(path: Path, max_body_bytes: int) -> tuple[str, int, bool, int]:
    raw = path.read_bytes()
    size_bytes = len(raw)
    truncated = size_bytes > max_body_bytes
    bounded = raw[:max_body_bytes]
    return bounded.decode("utf-8", errors="replace"), len(bounded), truncated, size_bytes


def _headings(text: str) -> tuple[str, ...]:
    headings: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("#"):
            continue
        title = stripped.lstrip("#").strip()
        if title:
            headings.append(title)
    return tuple(headings[:8])


def _title_for(path: Path, text: str) -> str:
    headings = _headings(text)
    if headings:
        return headings[0]
    return path.stem.replace("_", " ").replace("-", " ").strip() or path.name


def _tokens(text: str) -> list[str]:
    return [
        token
        for token in re.findall(r"[A-Za-z][A-Za-z0-9_-]{2,}", text.lower())
        if token not in STOPWORDS
    ]


def _top_terms(relative_path: str, title: str, headings: tuple[str, ...], text: str) -> tuple[str, ...]:
    counts: dict[str, int] = {}
    for token in _tokens(" ".join((relative_path, title, " ".join(headings), text))):
        counts[token] = counts.get(token, 0) + 1
    ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    return tuple(term for term, _count in ranked[:30])


def _source_kind(relative_path: str) -> str:
    if relative_path in {"AGENTS.md", "OPENCLAW_RUNTIME.md", "USER.md", "CORE_ARCHITECTURE_PRINCIPLES.md"}:
        return "ROOT_GOVERNANCE_MARKDOWN"
    if relative_path.startswith("generated/read_models/"):
        return "GENERATED_OPERATOR_MARKDOWN"
    if relative_path.startswith("docs/"):
        return "DOCS_MARKDOWN"
    if relative_path.startswith("Operator/"):
        return "OPERATOR_MARKDOWN"
    return "ALLOWLISTED_MARKDOWN"


def _document_card(
    *,
    repo_root: Path,
    path: Path,
    text: str,
    body_bytes_read: int,
    body_truncated: bool,
    size_bytes: int,
) -> MarkdownBodyDocumentCard:
    relative = _repo_relative(repo_root, path)
    headings = _headings(text)
    title = _title_for(path, text)
    return MarkdownBodyDocumentCard(
        doc_id=_sha256_text(relative)[:24],
        relative_path=relative,
        title=title,
        source_kind=_source_kind(relative),
        size_bytes=size_bytes,
        bounded_body_sha256=_sha256_text(text),
        body_bytes_read=body_bytes_read,
        body_truncated=body_truncated,
        heading_count=len(headings),
        headings_preview=headings[:5],
        top_terms=_top_terms(relative, title, headings, text),
        body_read=True,
        sensitivity_status="ALLOWLISTED_REPO_MARKDOWN",
        body_storage_policy="hash_terms_and_bounded_snippets_only_no_full_body_export",
        legal_discovery_excluded=True,
        action_authority_granted=False,
        runtime_dispatch_allowed=False,
    )


def _extract_topic(query_text: str) -> str:
    lowered = query_text.strip().lower()
    lowered = re.sub(r"^\s*(show me|find|query|what)\s+", "", lowered)
    lowered = re.sub(r"^\s*(work|terrain|docs|notes)\s+", "", lowered)
    lowered = re.sub(r"^\s*(on|about|for|related to)\s+", "", lowered)
    lowered = re.sub(r"[^a-z0-9 _/-]+", " ", lowered)
    lowered = re.sub(r"\s+", " ", lowered).strip()
    return lowered or "openclaw"


def _topic_terms(topic: str) -> tuple[str, ...]:
    terms = tuple(dict.fromkeys(_tokens(topic)))
    return terms or (topic.strip().lower(),)


def _term_count(term: str, text: str) -> int:
    if not term:
        return 0
    return len(re.findall(rf"\b{re.escape(term.lower())}\b", text.lower()))


def _score_document(card: MarkdownBodyDocumentCard, text: str, terms: tuple[str, ...]) -> int:
    relative = card.relative_path.lower()
    title = card.title.lower()
    headings = " ".join(card.headings_preview).lower()
    body = text.lower()
    score = 0
    for term in terms:
        score += 10 if term in relative else 0
        score += 8 if term in title else 0
        score += min(_term_count(term, headings), 4) * 4
        score += min(_term_count(term, body), 12)
    return score


def _snippet(text: str, index: int, term: str) -> str:
    radius = max(40, (MAX_SNIPPET_CHARS - len(term)) // 2)
    start = max(0, index - radius)
    end = min(len(text), index + len(term) + radius)
    snippet = re.sub(r"\s+", " ", text[start:end]).strip()
    if start > 0:
        snippet = "..." + snippet
    if end < len(text):
        snippet = snippet + "..."
    return snippet[:MAX_SNIPPET_CHARS]


def _snippets(text: str, terms: tuple[str, ...]) -> tuple[str, ...]:
    results: list[str] = []
    lowered = text.lower()
    for term in terms:
        index = lowered.find(term.lower())
        if index < 0:
            continue
        candidate = _snippet(text, index, term)
        if candidate not in results:
            results.append(candidate)
        if len(results) >= MAX_SNIPPETS_PER_RESULT:
            break
    return tuple(results)


def _query_results(
    cards_and_text: list[tuple[MarkdownBodyDocumentCard, str]],
    *,
    query_text: str,
    max_results: int,
) -> dict[str, Any]:
    topic = _extract_topic(query_text)
    terms = _topic_terms(topic)
    scored: list[dict[str, Any]] = []
    for card, text in cards_and_text:
        score = _score_document(card, text, terms)
        if score <= 0:
            continue
        scored.append(
            {
                "doc_id": card.doc_id,
                "relative_path": card.relative_path,
                "title": card.title,
                "source_kind": card.source_kind,
                "score": score,
                "matched_terms": [term for term in terms if _term_count(term, " ".join((card.relative_path, card.title, text)))],
                "evidence_snippets": list(_snippets(text, terms)),
                "body_storage_policy": card.body_storage_policy,
                "truth_status": "BODY_EVIDENCE_CANDIDATE_NOT_PROOF",
                "action_authority_granted": False,
                "runtime_dispatch_allowed": False,
            }
        )
    scored.sort(key=lambda row: (-int(row["score"]), row["relative_path"]))
    results = scored[:max_results]
    return {
        "query_kind": "what_work_on_topic",
        "query_text": query_text,
        "normalized_topic": topic,
        "topic_terms": list(terms),
        "result_count": len(results),
        "results": results,
        "truth_status": "BODY_EVIDENCE_CANDIDATE_NOT_PROOF",
        "semantic_review_status": "DETERMINISTIC_TOKEN_AND_SNIPPET_MATCH_ONLY",
        "action_authority_granted": False,
        "runtime_dispatch_allowed": False,
        "next_safe_move": "Route high-scoring candidates to relationship/classification review before treating them as current truth.",
    }


def build_openclaw_markdown_body_ingest_query(
    *,
    repo_root: str | Path = ROOT,
    markdown_roots: tuple[str, ...] = DEFAULT_MARKDOWN_ROOTS,
    query_text: str = "what work on Chief",
    generated_at: str | None = None,
    max_docs: int = MAX_DOCS_DEFAULT,
    max_body_bytes: int = MAX_BODY_BYTES_DEFAULT,
    max_results: int = MAX_RESULTS_DEFAULT,
) -> dict[str, Any]:
    repo = Path(repo_root)
    cards_and_text: list[tuple[MarkdownBodyDocumentCard, str]] = []
    for path in _iter_markdown_paths(repo, markdown_roots, max_docs):
        text, bytes_read, truncated, size_bytes = _read_text_bounded(path, max_body_bytes)
        card = _document_card(
            repo_root=repo,
            path=path,
            text=text,
            body_bytes_read=bytes_read,
            body_truncated=truncated,
            size_bytes=size_bytes,
        )
        cards_and_text.append((card, text))

    cards = [asdict(card) for card, _text in cards_and_text]
    query_receipt = _query_results(cards_and_text, query_text=query_text, max_results=max_results)
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "generated_at": generated_at or utc_now(),
        "contract_status": "bounded_markdown_body_ingest_query",
        "source_substrate_refs": list(SUBSTRATE_REFS),
        "body_ingest_policy": {
            "allowed_root_policy": "repo_relative_allowlist_only",
            "default_markdown_roots": list(markdown_roots),
            "blocked_path_parts": sorted(BLOCKED_PATH_PARTS),
            "blocked_file_hints": list(BLOCKED_FILE_HINTS),
            "max_docs": max_docs,
            "per_root_doc_limits": dict(PER_ROOT_DOC_LIMITS),
            "max_body_bytes_per_doc": max_body_bytes,
            "full_body_exported": False,
            "snippets_are_bounded": True,
            "legal_discovery_excluded": True,
            "private_or_broad_root_scan_allowed": False,
        },
        "document_summary": {
            "document_count": len(cards),
            "body_read_count": len(cards),
            "truncated_document_count": sum(1 for card in cards if card["body_truncated"]),
            "source_kinds": sorted({card["source_kind"] for card in cards}),
        },
        "document_cards": cards,
        "work_query_receipt": query_receipt,
        "authority_boundary": {
            **AUTHORITY_BOUNDARY,
            "all_action_authority_flags_false": all(value is False for value in AUTHORITY_BOUNDARY.values()),
        },
        "machine_proof": {
            "body_read_performed": bool(cards),
            "body_reads_are_repo_allowlisted": True,
            "full_body_exported": False,
            "raw_private_body_included": False,
            "bounded_snippets_exported": True,
            "body_byte_cap": max_body_bytes,
            "document_cap": max_docs,
            "legal_discovery_excluded": True,
            "blocked_path_filter_present": True,
            "broad_private_root_scan_allowed": False,
            "c_drive_scan_allowed": False,
            "model_api_execution_performed": False,
            "runtime_dispatch_allowed": False,
            "action_authority_granted": False,
            "query_kind_supported": query_receipt["query_kind"] == "what_work_on_topic",
            "content_hash": None,
        },
    }
    payload["machine_proof"]["content_hash"] = _content_hash(payload)
    return payload


def format_openclaw_markdown_body_ingest_query(payload: dict[str, Any]) -> str:
    summary = payload["document_summary"]
    receipt = payload["work_query_receipt"]
    lines = [
        "# OpenClaw Markdown Body Ingest Query v0",
        "",
        "Evidence:",
        f"- Read `{summary['document_count']}` allowlisted Markdown documents with byte caps.",
        f"- Query `{receipt['query_text']}` returned `{receipt['result_count']}` evidence candidates.",
        "- Full Markdown bodies are not exported; results carry hashes, terms, and bounded snippets only.",
        "",
        "Top query results:",
    ]
    for result in receipt["results"][:5]:
        lines.append(f"- `{result['relative_path']}` score `{result['score']}` ({result['title']})")
    lines.extend(
        [
            "",
            "Boundary:",
            "- Repo-relative allowlist only; broad private roots, C-drive, Legal Discovery, credentials, finance/private folders, and hidden key stores are blocked.",
            "- This read model does not promote truth, mutate files, refresh stable maps, launch tools, call models, send externally, or dispatch agents.",
            "",
            "Blocked:",
            "- Treating body matches as current doctrine or completion proof remains blocked until relationship/classification review.",
            "- Full-body export and broad semantic review remain blocked.",
            "",
            "Next safe move:",
            "- Feed high-scoring candidates into the relationship index and classification candidate lanes before operator-facing promotion.",
        ]
    )
    return "\n".join(lines) + "\n"


def export_openclaw_markdown_body_ingest_query(
    *,
    repo_root: str | Path = ROOT,
    export_root: str | Path = DEFAULT_EXPORT_ROOT,
    query_text: str = "what work on Chief",
    generated_at: str | None = None,
    max_docs: int = MAX_DOCS_DEFAULT,
    max_body_bytes: int = MAX_BODY_BYTES_DEFAULT,
) -> MarkdownBodyQueryExportResult:
    payload = build_openclaw_markdown_body_ingest_query(
        repo_root=repo_root,
        query_text=query_text,
        generated_at=generated_at,
        max_docs=max_docs,
        max_body_bytes=max_body_bytes,
    )
    root = Path(export_root)
    if not root.is_absolute():
        root = Path(repo_root) / root
    root.mkdir(parents=True, exist_ok=True)
    json_path = root / JSON_EXPORT_NAME
    operator_path = root / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(format_openclaw_markdown_body_ingest_query(payload), encoding="utf-8")
    return MarkdownBodyQueryExportResult(
        schema_version=SCHEMA_VERSION,
        json_path=json_path.as_posix(),
        operator_path=operator_path.as_posix(),
        document_count=payload["document_summary"]["document_count"],
        result_count=payload["work_query_receipt"]["result_count"],
        body_read_performed=payload["machine_proof"]["body_read_performed"],
        full_body_exported=payload["machine_proof"]["full_body_exported"],
        action_authority_granted=payload["authority_boundary"]["action_authority_granted"],
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export bounded Markdown body ingest query read-model.")
    parser.add_argument("--repo-root", default=ROOT.as_posix())
    parser.add_argument("--export-root", default=DEFAULT_EXPORT_ROOT.as_posix())
    parser.add_argument("--query", default="what work on Chief")
    parser.add_argument("--generated-at", default=None)
    parser.add_argument("--max-docs", type=int, default=MAX_DOCS_DEFAULT)
    parser.add_argument("--max-body-bytes", type=int, default=MAX_BODY_BYTES_DEFAULT)
    parser.add_argument("--format", choices=("summary", "json", "operator"), default="operator")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    result = export_openclaw_markdown_body_ingest_query(
        repo_root=args.repo_root,
        export_root=args.export_root,
        query_text=args.query,
        generated_at=args.generated_at,
        max_docs=args.max_docs,
        max_body_bytes=args.max_body_bytes,
    )
    summary = asdict(result)
    if args.format in {"summary", "json"}:
        print(stable_json(summary), end="")
    else:
        print(f"OpenClaw Markdown Body Ingest Query: `{READ_MODEL_ID}`")
        print(f"- JSON: `{result.json_path}`")
        print(f"- Operator: `{result.operator_path}`")
        print(f"- Results: `{result.result_count}`")
    return 0


__all__ = [
    "JSON_EXPORT_NAME",
    "MAX_SNIPPET_CHARS",
    "OPERATOR_EXPORT_NAME",
    "READ_MODEL_ID",
    "SCHEMA_VERSION",
    "MarkdownBodyDocumentCard",
    "build_openclaw_markdown_body_ingest_query",
    "export_openclaw_markdown_body_ingest_query",
    "format_openclaw_markdown_body_ingest_query",
    "stable_json",
]
