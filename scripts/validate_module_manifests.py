#!/usr/bin/env python3
"""Validate inert synthetic module manifest examples in Markdown files."""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


DEFAULT_MANIFEST_DOC = Path(
    "docs/module_atlas/OPENCLAW_SYNTHETIC_MODULE_MANIFEST_EXAMPLES_V0.md"
)

REQUIRED_FIELDS = (
    "module_id",
    "module_family",
    "purpose",
    "authority_level",
    "allowed_inputs",
    "forbidden_inputs",
    "outputs_artifacts",
    "approval_gates",
    "sensitivity_gates",
    "dependencies",
    "tests_required",
    "receipts_required",
    "disable_path",
    "rollback_path",
    "NOT_READY_boundaries",
)

ALLOWED_AUTHORITY_LEVELS = {
    "docs_only",
    "proposal_only",
    "read_only_after_approval",
    "dry_run_after_approval",
    "runtime_blocked",
}

REQUIRED_NOT_READY_TERMS = (
    "runtime activation",
    "customer deployment",
    "autonomous action",
    "sensitive-data processing",
    "broker connection",
    "agent wiring",
    "sqlite write",
    "live system health claim",
)

FORBIDDEN_PERMISSION_TERMS = (
    "runtime activation",
    "sqlite write",
    "sqlite writes",
    "broker connection",
    "broker connections",
    "agent wiring",
    "private data read",
    "private data reads",
    "customer deployment",
    "autonomous action",
    "live system state",
    "live system health",
)

PERMISSION_SENSITIVE_FIELDS = (
    "module_id",
    "module_family",
    "purpose",
    "authority_level",
    "allowed_inputs",
    "outputs_artifacts",
    "dependencies",
    "disable_path",
    "rollback_path",
)

FORBIDDEN_PERMISSION_PATTERNS = (
    (
        "runtime activation claim",
        re.compile(r"\bruntime activation\s+(?:is\s+)?(?:approved|ready|enabled|active|permitted|allowed)\b"),
    ),
    (
        "SQLite write claim",
        re.compile(r"\bsqlite writes?\s+(?:are\s+|is\s+)?(?:approved|ready|enabled|active|permitted|allowed)\b"),
    ),
    (
        "broker connection claim",
        re.compile(r"\bbroker connections?\s+(?:are\s+|is\s+)?(?:approved|ready|enabled|active|permitted|allowed)\b"),
    ),
    (
        "agent wiring claim",
        re.compile(r"\bagent wiring\s+(?:is\s+)?(?:approved|ready|enabled|active|permitted|allowed)\b"),
    ),
    (
        "private data read claim",
        re.compile(r"\bprivate data reads?\s+(?:are\s+|is\s+)?(?:approved|ready|enabled|active|permitted|allowed)\b"),
    ),
    (
        "customer deployment claim",
        re.compile(r"\bcustomer deployment\s+(?:is\s+)?(?:approved|ready|enabled|active|permitted|allowed)\b"),
    ),
    (
        "autonomous action claim",
        re.compile(r"\bautonomous action\s+(?:is\s+)?(?:approved|ready|enabled|active|permitted|allowed)\b"),
    ),
    (
        "live system state claim",
        re.compile(r"\blive system (?:state|health)\s+(?:is\s+)?(?:ready|verified|healthy|available|active)\b"),
    ),
)

TOP_LEVEL_FIELD_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(.*)$")
FENCE_RE = re.compile(r"^```(?:yaml|yml)\s*\n(.*?)^```\s*$", re.MULTILINE | re.DOTALL)


@dataclass(frozen=True)
class ManifestBlock:
    path: Path
    index: int
    start_line: int
    text: str
    section_text: str


@dataclass(frozen=True)
class Finding:
    path: Path
    manifest_index: int
    line: int
    message: str

    def format(self) -> str:
        return f"{self.path}:{self.line}: manifest {self.manifest_index}: {self.message}"


def strip_quotes(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def extract_manifest_blocks(path: Path, markdown: str) -> list[ManifestBlock]:
    blocks: list[ManifestBlock] = []
    for index, match in enumerate(FENCE_RE.finditer(markdown), start=1):
        block_text = match.group(1)
        start_line = markdown[: match.start(1)].count("\n") + 1
        section_start = markdown.rfind("\n## ", 0, match.start())
        if section_start == -1:
            section_start = markdown.rfind("\n# ", 0, match.start())
        if section_start == -1:
            section_start = 0
        else:
            section_start += 1
        section_end = markdown.find("\n## ", match.end())
        if section_end == -1:
            section_end = len(markdown)
        section_text = markdown[section_start:section_end]
        blocks.append(
            ManifestBlock(
                path=path,
                index=index,
                start_line=start_line,
                text=block_text,
                section_text=section_text,
            )
        )
    return blocks


def top_level_fields(block_text: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for line in block_text.splitlines():
        match = TOP_LEVEL_FIELD_RE.match(line)
        if match:
            fields[match.group(1)] = strip_quotes(match.group(2))
    return fields


def field_text(block_text: str, field_name: str) -> str:
    lines = block_text.splitlines()
    selected: list[str] = []
    collecting = False
    for line in lines:
        match = TOP_LEVEL_FIELD_RE.match(line)
        if match and collecting and match.group(1) != field_name:
            break
        if match and match.group(1) == field_name:
            collecting = True
        if collecting:
            selected.append(line)
    return "\n".join(selected)


def validate_manifest(block: ManifestBlock) -> list[Finding]:
    findings: list[Finding] = []
    fields = top_level_fields(block.text)

    for field_name in REQUIRED_FIELDS:
        if field_name not in fields:
            findings.append(
                Finding(
                    block.path,
                    block.index,
                    block.start_line,
                    f"missing required field: {field_name}",
                )
            )

    authority_level = fields.get("authority_level")
    if authority_level and authority_level not in ALLOWED_AUTHORITY_LEVELS:
        findings.append(
            Finding(
                block.path,
                block.index,
                block.start_line,
                f"invalid authority_level: {authority_level}",
            )
        )

    section_lower = block.section_text.lower()
    if "synthetic" not in section_lower and "example" not in section_lower:
        findings.append(
            Finding(
                block.path,
                block.index,
                block.start_line,
                "manifest section lacks synthetic/example marker",
            )
        )
    inert_markers = (
        "does not describe an active",
        "not activation authority",
        "inert",
        "no live module",
    )
    if not any(marker in section_lower for marker in inert_markers):
        findings.append(
            Finding(
                block.path,
                block.index,
                block.start_line,
                "manifest section lacks inert or non-active marker",
            )
        )

    not_ready_text = field_text(block.text, "NOT_READY_boundaries").lower()
    for term in REQUIRED_NOT_READY_TERMS:
        if term not in not_ready_text:
            findings.append(
                Finding(
                    block.path,
                    block.index,
                    block.start_line,
                    f"missing NOT_READY boundary: {term}",
                )
            )

    permission_text = "\n".join(
        field_text(block.text, field_name) for field_name in PERMISSION_SENSITIVE_FIELDS
    ).lower()
    for term in FORBIDDEN_PERMISSION_TERMS:
        if term in permission_text:
            findings.append(
                Finding(
                    block.path,
                    block.index,
                    block.start_line,
                    f"forbidden permission term in permission-sensitive fields: {term}",
                )
            )

    claim_text = (block.section_text + "\n" + permission_text).lower()
    for label, pattern in FORBIDDEN_PERMISSION_PATTERNS:
        if pattern.search(claim_text):
            findings.append(
                Finding(
                    block.path,
                    block.index,
                    block.start_line,
                    f"forbidden permission claim: {label}",
                )
            )

    return findings


def validate_path(path: Path) -> tuple[int, list[Finding]]:
    markdown = path.read_text(encoding="utf-8")
    blocks = extract_manifest_blocks(path, markdown)
    if not blocks:
        return 0, [Finding(path, 0, 1, "no fenced yaml manifest blocks found")]

    findings: list[Finding] = []
    for block in blocks:
        findings.extend(validate_manifest(block))
    return len(blocks), findings


def validate_paths(paths: Iterable[Path]) -> tuple[int, list[Finding]]:
    total_blocks = 0
    findings: list[Finding] = []
    for path in paths:
        block_count, path_findings = validate_path(path)
        total_blocks += block_count
        findings.extend(path_findings)
    return total_blocks, findings


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate inert synthetic module manifest examples."
    )
    parser.add_argument(
        "paths",
        nargs="*",
        type=Path,
        default=[DEFAULT_MANIFEST_DOC],
        help="Markdown manifest example files to validate.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    total_blocks, findings = validate_paths(args.paths)

    if findings:
        for finding in findings:
            print(finding.format(), file=sys.stderr)
        print(
            f"FAIL: validated {total_blocks} manifest block(s), found {len(findings)} issue(s)",
            file=sys.stderr,
        )
        return 1

    print(f"OK: validated {total_blocks} inert synthetic module manifest block(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
