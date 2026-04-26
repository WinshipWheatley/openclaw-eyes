#!/usr/bin/env python3
"""Read-only inventory of local model usage surfaces.

This script reports direct Ollama callers, hardcoded model names, long
timeouts, and paths that appear to bypass the shared chief_llm routing helpers.
It does not import project runtime modules or change behavior.
"""

from __future__ import annotations

import argparse
import os
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path


ROOT = Path("/home/openclaw")
DEFAULT_EXTENSIONS = {".py", ".sh"}
SOURCE_DIRS = (
    "polish_loop",
    "scripts",
    "sidecars/hermes/scripts",
    "sidecars/hermes/gateway",
    "sidecars/hermes/hermes_cli",
    "tools",
)
EXCLUDED_DIR_PARTS = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    "__pycache__",
    ".venv",
    "venv",
    "chief_env",
    "node_modules",
    "legal",
    "tests",
}

MODEL_RE = re.compile(
    r"\b("
    r"gemma[\w:.\-/]*|"
    r"qwen[\w:.\-/]*|"
    r"nemotron[\w:.\-/]*|"
    r"mistral[\w:.\-/]*|"
    r"magistral[\w:.\-/]*"
    r")\b",
    re.IGNORECASE,
)
TIMEOUT_RE = re.compile(r"\b(?:timeout|TIMEOUT|API_TIMEOUT|PLANNER_TIMEOUT)\s*=\s*(\d{3,})\b")
OLLAMA_HTTP_RE = re.compile(r"(?:OLLAMA_URL|localhost:11434|127\.0\.0\.1:11434|/api/generate|ollama serve)")
OLLAMA_CALL_RE = re.compile(r"\bollama_call\s*\(")
RESOLVE_MODEL_RE = re.compile(r"\bresolve_local_model\s*\(")

HEAVY_MODEL_MARKERS = (
    "qwen3.6",
    "gemma4:31b",
    "gemma4:26b",
    "nemotron-3-nano:30b",
    "magistral",
    "mistral-small",
)


@dataclass(frozen=True)
class Finding:
    path: str
    line_number: int
    finding_type: str
    excerpt: str
    severity: str


def _is_relevant_file(path: Path, root: Path = ROOT) -> bool:
    if path.suffix not in DEFAULT_EXTENSIONS:
        return False
    rel_parts = path.relative_to(root).parts
    return not any(part in EXCLUDED_DIR_PARTS for part in rel_parts)


def _excerpt(line: str) -> str:
    compact = " ".join(line.strip().split())
    return compact[:180]


def _severity_for_model(model: str) -> str:
    normalized = model.lower()
    if any(marker in normalized for marker in HEAVY_MODEL_MARKERS):
        return "high"
    return "review"


def _line_findings(path: Path, line_number: int, line: str, root: Path = ROOT) -> list[Finding]:
    rel = str(path.relative_to(root))
    findings: list[Finding] = []
    excerpt = _excerpt(line)

    if OLLAMA_CALL_RE.search(line):
        severity = "info" if rel == "chief_llm.py" else "review"
        findings.append(Finding(rel, line_number, "ollama_call", excerpt, severity))

    if RESOLVE_MODEL_RE.search(line):
        severity = "info" if rel == "chief_llm.py" else "review"
        findings.append(Finding(rel, line_number, "resolve_local_model", excerpt, severity))

    if OLLAMA_HTTP_RE.search(line):
        severity = "info" if rel == "chief_llm.py" else "high"
        findings.append(Finding(rel, line_number, "direct_ollama_http_or_url", excerpt, severity))

    for match in MODEL_RE.finditer(line):
        model = match.group(1)
        findings.append(
            Finding(rel, line_number, f"hardcoded_model:{model}", excerpt, _severity_for_model(model))
        )

    timeout_match = TIMEOUT_RE.search(line)
    if timeout_match:
        timeout_value = int(timeout_match.group(1))
        if timeout_value >= 300:
            severity = "high" if timeout_value >= 600 else "review"
            findings.append(Finding(rel, line_number, f"long_timeout:{timeout_value}", excerpt, severity))

    return findings


def collect_findings(root: Path = ROOT) -> list[Finding]:
    findings: list[Finding] = []
    paths: set[Path] = set()
    for child in root.iterdir():
        if child.is_file() and child.suffix in DEFAULT_EXTENSIONS:
            paths.add(child)
    for dirname in SOURCE_DIRS:
        base = root / dirname
        if base.exists():
            for dirpath, dirnames, filenames in os.walk(base):
                dirnames[:] = sorted(
                    name for name in dirnames if name not in EXCLUDED_DIR_PARTS
                )
                for filename in filenames:
                    paths.add(Path(dirpath) / filename)

    for path in sorted(paths):
        if not path.is_file() or not _is_relevant_file(path, root):
            continue
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        for idx, line in enumerate(lines, start=1):
            findings.extend(_line_findings(path, idx, line, root))
    return findings


def print_report(findings: list[Finding], root: Path = ROOT) -> None:
    print("LOCAL MODEL USAGE INVENTORY")
    print(f"root: {root}")
    print("mode: read-only")
    print()

    print("SUMMARY")
    print(f"total_findings: {len(findings)}")
    by_severity = Counter(f.severity for f in findings)
    by_type = Counter(f.finding_type.split(":", 1)[0] for f in findings)
    for severity in ("high", "review", "info"):
        print(f"{severity}: {by_severity.get(severity, 0)}")
    print()
    print("finding_types:")
    for finding_type, count in sorted(by_type.items()):
        print(f"- {finding_type}: {count}")
    print()

    print("FINDINGS")
    if not findings:
        print("(none)")
        return
    print("file\tline\tseverity\tfinding_type\texcerpt")
    for item in findings:
        print(
            f"{item.path}\t{item.line_number}\t{item.severity}\t"
            f"{item.finding_type}\t{item.excerpt}"
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only local model usage inventory")
    parser.add_argument(
        "--root",
        type=Path,
        default=ROOT,
        help="Repository root to scan (default: /home/openclaw)",
    )
    args = parser.parse_args(argv)

    root = args.root.resolve()
    print_report(collect_findings(root), root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
