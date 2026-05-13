#!/usr/bin/env python3
"""Build deterministic source cards from safe extraction artifacts."""

from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path
from typing import Any

try:
    from scripts.extract_accepted_sources import (
        EVIDENCE_LABEL,
        EXTRACTION_ARTIFACT_VERSION,
    )
    from scripts.promote_accepted_context import (
        load_json_artifact,
        stable_json,
        write_json_artifact,
    )
except ImportError:
    from extract_accepted_sources import EVIDENCE_LABEL, EXTRACTION_ARTIFACT_VERSION
    from promote_accepted_context import load_json_artifact, stable_json, write_json_artifact


SOURCE_CARDS_VERSION = "source_cards_v0"
MAX_KNOWN_FACTS = 5


def _first_sentence(text: str) -> str:
    compact = " ".join(text.strip().split())
    if not compact:
        return ""
    for delimiter in (". ", "? ", "! "):
        if delimiter in compact:
            return compact.split(delimiter, 1)[0].strip() + delimiter.strip()
    return compact[:180]


def _clean_markdown_line(line: str) -> str:
    stripped = line.strip()
    while stripped.startswith("#"):
        stripped = stripped[1:].strip()
    for prefix in ("- ", "* ", "1. "):
        if stripped.startswith(prefix):
            stripped = stripped[len(prefix):].strip()
    return " ".join(stripped.split())


def _markdown_facts(text: str) -> tuple[str, list[str]]:
    headings: list[str] = []
    bullets: list[str] = []
    first_nonempty = ""
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if not first_nonempty:
            first_nonempty = _clean_markdown_line(stripped)
        if stripped.startswith("#"):
            headings.append(_clean_markdown_line(stripped))
        elif stripped.startswith(("- ", "* ")):
            bullets.append(_clean_markdown_line(stripped))

    purpose = headings[0] if headings else first_nonempty
    facts = []
    for item in [*headings[1:], *bullets, first_nonempty]:
        if item and item not in facts and item != purpose:
            facts.append(item)
        if len(facts) >= MAX_KNOWN_FACTS:
            break
    if not facts and purpose:
        facts.append(purpose)
    return purpose or "Markdown source evidence", facts


def _python_facts(text: str) -> tuple[str, list[str]]:
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return "Python source evidence", ["Python source could not be parsed by ast."]

    docstring = ast.get_docstring(tree) or ""
    purpose = _first_sentence(docstring) if docstring else "Python source evidence"
    facts: list[str] = []
    if docstring:
        facts.append(_first_sentence(docstring))

    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            facts.append(f"Defines class `{node.name}`.")
        elif isinstance(node, ast.FunctionDef):
            facts.append(f"Defines function `{node.name}`.")
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id.isupper():
                    facts.append(f"Defines constant `{target.id}`.")
        if len(facts) >= MAX_KNOWN_FACTS:
            break

    return purpose, facts[:MAX_KNOWN_FACTS] or ["Python source parsed without top-level summary."]


def _purpose_and_facts(record: dict[str, Any]) -> tuple[str, list[str]]:
    text = record.get("extracted_text", "")
    if record.get("extension") == ".py":
        return _python_facts(text)
    return _markdown_facts(text)


def _module_lane(record: dict[str, Any]) -> tuple[str, str]:
    path = record.get("path", "")
    source_class = record.get("source_class", "")
    if path.startswith("docs/module_atlas/") or source_class.startswith("module_atlas"):
        return "module_atlas", "module_atlas"
    if "operator_status" in source_class:
        return "operator_status", "operator_status"
    if "receipt" in source_class:
        return "receipt_spine", "receipt_spine"
    if "manifest" in source_class:
        return "module_manifest", "module_manifest"
    if source_class == "validation_test":
        return "validation", "validation"
    return "openclaw_context", "context_substrate"


def _eligible_for_card(record: dict[str, Any]) -> bool:
    return (
        record.get("extraction_state") == "extracted"
        and record.get("evidence_label") == EVIDENCE_LABEL
        and record.get("runtime_authority") is False
        and record.get("not_runtime_authority") is True
        and record.get("authority_label") != "blocked"
    )


def _source_card(record: dict[str, Any]) -> dict[str, Any]:
    purpose, known_facts = _purpose_and_facts(record)
    module, lane = _module_lane(record)
    return {
        "card_version": SOURCE_CARDS_VERSION,
        "path": record["path"],
        "module": module,
        "lane": lane,
        "source_class": record["source_class"],
        "purpose": purpose,
        "known_facts": known_facts,
        "limits": [
            "Deterministic extractive summary only; no LLM call.",
            "Parsed evidence is not truth.",
            "No full source body is stored in this card.",
            "No runtime, broker, agent, or deployment authority.",
        ],
        "freshness": {
            "source_sha256": record["source_sha256"],
            "source_size_bytes": record["source_size_bytes"],
            "extraction_time": record["extraction_time"],
            "extraction_time_policy": record["extraction_time_policy"],
        },
        "authority_label": record["authority_label"],
        "ingestion_state": "summarized",
        "source_ingestion_state": record["ingestion_state"],
        "evidence_label": record["evidence_label"],
        "usable_by_agents": True,
        "context_for_reasoning_only": True,
        "not_runtime_authority": True,
        "runtime_authority": False,
        "full_body_included": False,
        "provenance": {
            "source_path": record["path"],
            "source_sha256": record["source_sha256"],
            "extraction_artifact_version": EXTRACTION_ARTIFACT_VERSION,
            "promotion_ref": record.get("promotion_ref", {}),
        },
    }


def build_source_cards(extraction_artifact: dict[str, Any]) -> dict[str, Any]:
    cards: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []

    for record in extraction_artifact.get("records", []):
        if _eligible_for_card(record):
            cards.append(_source_card(record))
        else:
            excluded.append(
                {
                    "path": record.get("path"),
                    "reason_excluded": "record_not_extracted_evidence_or_has_runtime_authority",
                    "runtime_authority": bool(record.get("runtime_authority")),
                }
            )

    for refusal in extraction_artifact.get("refusals", []):
        excluded.append(
            {
                "path": refusal.get("path"),
                "reason_excluded": refusal.get("reason_refused", "extraction_refusal"),
                "runtime_authority": False,
            }
        )

    return {
        "artifact_version": SOURCE_CARDS_VERSION,
        "source_extraction_artifact_version": extraction_artifact.get("artifact_version"),
        "cards": cards,
        "excluded_records": excluded,
        "summary": {
            "cards_total": len(cards),
            "usable_by_agents": sum(1 for card in cards if card["usable_by_agents"]),
            "excluded_records": len(excluded),
            "full_bodies_in_cards": False,
            "source_body_ingested_upstream": extraction_artifact.get("summary", {}).get("body_ingested", False),
            "runtime_authority": False,
        },
    }


def format_operator_source_cards(artifact: dict[str, Any]) -> str:
    summary = artifact["summary"]
    source_groups: dict[str, int] = {}
    for card in artifact.get("cards", []):
        source_groups[card["source_class"]] = source_groups.get(card["source_class"], 0) + 1
    group_text = ", ".join(
        f"{name}={count}" for name, count in sorted(source_groups.items())
    ) or "none"

    lines = [
        "Source Card / Document Summary v0",
        "",
        "Evidence:",
        f"- {summary['cards_total']} deterministic source cards were built from safe extraction records.",
        f"- Source groups: {group_text}.",
        "- Cards include path, source class, purpose, known facts, limits, freshness, authority, and provenance.",
        "",
        "Boundary:",
        "- Cards are deterministic/extractive only; no LLM calls, vector search, or broad retrieval are used.",
        "- Cards do not contain full source bodies and remain parsed evidence, not truth.",
        "- `runtime_authority=false`; cards are context for reasoning only.",
        "",
        "Blocked:",
        f"- {summary['excluded_records']} extraction records/refusals are excluded from usable source cards.",
        "- Blocked/no-go paths and unextracted sources are not included as cards.",
        "- No agents, modules, brokers, customer deployment, external tools, or runtime behavior are activated.",
        "",
        "Next safe move:",
        "- Compile accepted working context packets from usable cards with provenance and authority boundaries intact.",
    ]
    return "\n".join(lines)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build deterministic source cards from a safe extraction artifact."
    )
    parser.add_argument(
        "--extraction-artifact",
        required=True,
        help="Safe extraction JSON artifact.",
    )
    parser.add_argument(
        "--format",
        choices=("operator", "json"),
        default="operator",
        help="Output format. Defaults to operator.",
    )
    parser.add_argument(
        "--output",
        help="Optional JSON output path for the source cards artifact.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    extraction_artifact = load_json_artifact(args.extraction_artifact)
    artifact = build_source_cards(extraction_artifact)

    if args.output:
        write_json_artifact(artifact, args.output)

    if args.format == "json":
        print(stable_json(artifact), end="")
    else:
        print(format_operator_source_cards(artifact))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
