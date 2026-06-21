#!/usr/bin/env python3
"""Read-only Phase III memory inventory and boundary audit."""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from typing import Any, Iterable, Mapping, Sequence


SCHEMA_VERSION = "agent_memory_boundary_audit_v0"
DEFAULT_SCAN_ROOTS = (
    "generated/read_models",
    "generated/wiki",
    "generated/system_knowledge",
    ".claude/commands",
    "docs",
)
DEFAULT_MARKDOWN_OUTPUT = Path("artifacts/039_memory_boundary_audit.md")
DEFAULT_JSON_OUTPUT = Path("generated/read_models/agent_memory_boundary_audit.json")
DENY_PATH_PARTS = {
    ".git",
    ".venv",
    "__pycache__",
    "vault",
    "secrets",
    "node_modules",
}
DENY_FILENAMES = {
    ".chief.env",
    ".env",
    ".env.local",
}
TEXT_SUFFIXES = {".json", ".md", ".txt", ".yaml", ".yml", ".toml", ".py"}

CATEGORY_RULES: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("A", "SESSION CONTEXT", ("chat", "conversation", "session", "thread", "transcript")),
    ("B", "PROJECT FACT", ("project", "invoice", "client", "workflow", "task", "deliverable")),
    ("C", "SERVICE PREFERENCE", ("preference", "prefers", "communication style", "follow-up", "follow up")),
    ("D", "CREATIVE OR TECHNICAL PREFERENCE", ("creative", "technical preference", "x32", "niles", "music", "routing")),
    ("E", "RELATIONSHIP-CONTINUITY DETAIL", ("relationship", "family", "contact", "recipient", "client relationship")),
    (
        "F",
        "SENSITIVE OR RESTRICTED INFORMATION",
        (
            "address",
            "bank",
            "credential",
            "diagnosis",
            "email",
            "legal",
            "medical",
            "passport",
            "phone",
            "ssn",
            "tax",
            "token",
        ),
    ),
    (
        "G",
        "PROHIBITED INFERENCE",
        (
            "addiction",
            "diagnosed",
            "infer",
            "inferred",
            "likely has",
            "mental health",
            "personality type",
            "political",
            "religion",
        ),
    ),
)

EMAIL_RE = re.compile(r"[\w.+-]+@[\w.-]+\.[a-zA-Z]{2,}")
PHONE_RE = re.compile(r"\b(?:\+?1[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?)\d{3}[-.\s]?\d{4}\b")
LONG_NUMBER_RE = re.compile(r"\b\d{6,}\b")


@dataclass(frozen=True)
class Finding:
    path: str
    category: str
    category_name: str
    truth_state: str
    access_scope: str
    globally_accessible: bool
    risky_global_memory: bool
    matched_terms: tuple[str, ...]
    redacted_sample: str


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _is_denied_path(path: Path) -> bool:
    lowered_parts = {part.lower() for part in path.parts}
    if lowered_parts & DENY_PATH_PARTS:
        return True
    return path.name.lower() in DENY_FILENAMES


def _is_text_candidate(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() in TEXT_SUFFIXES and not _is_denied_path(path)


def iter_candidate_files(root: Path, scan_roots: Sequence[str] = DEFAULT_SCAN_ROOTS) -> Iterable[Path]:
    for rel in scan_roots:
        base = root / rel
        if not base.exists() or _is_denied_path(base):
            continue
        for path in sorted(base.rglob("*")):
            if _is_text_candidate(path):
                yield path


def _read_text_sample(path: Path, max_bytes: int) -> str:
    try:
        with path.open("rb") as fh:
            raw = fh.read(max_bytes)
    except OSError:
        return ""
    return raw.decode("utf-8", errors="ignore")


def _redact(text: str) -> str:
    text = EMAIL_RE.sub("[EMAIL]", text)
    text = PHONE_RE.sub("[PHONE]", text)
    text = LONG_NUMBER_RE.sub("[NUMBER]", text)
    return " ".join(text.split())[:260]


def _truth_state(text: str) -> str:
    lowered = text.lower()
    for state in ("do_not_use", "deleted", "disputed", "corrected", "stale"):
        if state in lowered or state.replace("_", " ") in lowered:
            return state.upper()
    if "operator_confirmed" in lowered or "confirmed_current" in lowered:
        return "CONFIRMED_CURRENT"
    if "inferred" in lowered or "hypothesis" in lowered:
        return "INFERRED_HYPOTHESIS"
    return "OBSERVED_PATTERN"


def _access_scope(root: Path, path: Path) -> str:
    try:
        rel = path.relative_to(root).as_posix()
    except ValueError:
        rel = path.as_posix()
    if rel.startswith(("generated/read_models/", "generated/wiki/", "docs/", ".claude/commands/")):
        return "GLOBAL_REPO_ACCESSIBLE"
    if rel.startswith("generated/system_knowledge/"):
        return "LOCAL_SYSTEM_KNOWLEDGE"
    return "UNKNOWN_SCOPE"


def _classify(path: Path, text: str, *, root: Path) -> list[Finding]:
    lowered = f"{path.as_posix()} {text}".lower()
    scope = _access_scope(root, path)
    globally_accessible = scope == "GLOBAL_REPO_ACCESSIBLE"
    findings: list[Finding] = []
    for category, category_name, terms in CATEGORY_RULES:
        matched = tuple(term for term in terms if term in lowered)
        if not matched:
            continue
        risky = globally_accessible and category in {"F", "G"}
        findings.append(
            Finding(
                path=path.relative_to(root).as_posix() if path.is_relative_to(root) else path.as_posix(),
                category=category,
                category_name=category_name,
                truth_state=_truth_state(text),
                access_scope=scope,
                globally_accessible=globally_accessible,
                risky_global_memory=risky,
                matched_terms=matched,
                redacted_sample=_redact(text),
            )
        )
    return findings


def build_audit(
    *,
    root: str | Path = ".",
    scan_roots: Sequence[str] = DEFAULT_SCAN_ROOTS,
    max_files: int = 2000,
    max_bytes_per_file: int = 20000,
) -> dict[str, Any]:
    base = Path(root)
    findings: list[Finding] = []
    scanned = 0
    skipped_after_limit = False
    for path in iter_candidate_files(base, scan_roots):
        if scanned >= max_files:
            skipped_after_limit = True
            break
        scanned += 1
        text = _read_text_sample(path, max_bytes_per_file)
        if not text.strip():
            continue
        findings.extend(_classify(path, text, root=base))

    by_category = Counter(finding.category for finding in findings)
    risky = [finding for finding in findings if finding.risky_global_memory]
    payload = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": "agent_memory_boundary_audit",
        "generated_at": _utc_now(),
        "status": "READY",
        "scan_roots": list(scan_roots),
        "files_scanned": scanned,
        "max_files": max_files,
        "skipped_after_limit": skipped_after_limit,
        "finding_count": len(findings),
        "category_counts": dict(sorted(by_category.items())),
        "risky_global_memory_count": len(risky),
        "risky_global_memory": [asdict(finding) for finding in risky[:100]],
        "findings": [asdict(finding) for finding in findings[:500]],
        "memory_categories": {category: name for category, name, _terms in CATEGORY_RULES},
        "machine_proof": {
            "read_only": True,
            "deleted_files": False,
            "mutated_prompts": False,
            "launched_personalization": False,
            "secret_paths_skipped": True,
            "samples_redacted": True,
        },
    }
    return payload


def render_markdown(payload: Mapping[str, Any]) -> str:
    risky = [row for row in payload.get("risky_global_memory", ()) if isinstance(row, Mapping)]
    lines = [
        "# Phase III Memory Boundary Audit",
        "",
        f"- Status: {payload.get('status')}",
        f"- Files scanned: {payload.get('files_scanned')}",
        f"- Findings: {payload.get('finding_count')}",
        f"- Risky global Category F/G findings: {payload.get('risky_global_memory_count')}",
        "",
        "## Category Counts",
    ]
    counts = payload.get("category_counts") if isinstance(payload.get("category_counts"), Mapping) else {}
    for category, count in sorted(counts.items()):
        name = payload.get("memory_categories", {}).get(category, "") if isinstance(payload.get("memory_categories"), Mapping) else ""
        lines.append(f"- Category {category} ({name}): {count}")
    lines.extend(["", "## Risky Global Findings"])
    if not risky:
        lines.append("- None found in the bounded scan.")
    for row in risky[:40]:
        lines.append(
            f"- Category {row.get('category')} at `{row.get('path')}` "
            f"[truth={row.get('truth_state')}; scope={row.get('access_scope')}]: {row.get('redacted_sample')}"
        )
    lines.extend(
        [
            "",
            "## Boundaries",
            "- Audit only: no deletion, prompt mutation, live personalization, send, money movement, deploy, or restart.",
            "- Secret/vault/env paths are skipped; samples are redacted.",
        ]
    )
    return "\n".join(lines).strip() + "\n"


def write_outputs(payload: Mapping[str, Any], *, json_output: Path, markdown_output: Path) -> None:
    json_output.parent.mkdir(parents=True, exist_ok=True)
    markdown_output.parent.mkdir(parents=True, exist_ok=True)
    json_output.write_text(stable_json(dict(payload)), encoding="utf-8")
    markdown_output.write_text(render_markdown(payload), encoding="utf-8")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run a read-only Phase III memory boundary audit.")
    parser.add_argument("--root", default=".")
    parser.add_argument("--scan-root", action="append", default=[])
    parser.add_argument("--json-output", default=DEFAULT_JSON_OUTPUT.as_posix())
    parser.add_argument("--markdown-output", default=DEFAULT_MARKDOWN_OUTPUT.as_posix())
    parser.add_argument("--max-files", type=int, default=2000)
    parser.add_argument("--max-bytes-per-file", type=int, default=20000)
    args = parser.parse_args(list(argv) if argv is not None else None)

    payload = build_audit(
        root=args.root,
        scan_roots=tuple(args.scan_root) if args.scan_root else DEFAULT_SCAN_ROOTS,
        max_files=max(1, args.max_files),
        max_bytes_per_file=max(1000, args.max_bytes_per_file),
    )
    write_outputs(payload, json_output=Path(args.json_output), markdown_output=Path(args.markdown_output))
    print(stable_json({"status": payload["status"], "finding_count": payload["finding_count"]}), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
