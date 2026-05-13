#!/usr/bin/env python3
"""Compile source cards into accepted working context packets."""

from __future__ import annotations

import argparse
import re
import sys
from collections import defaultdict
from typing import Any

try:
    from scripts.build_source_cards import SOURCE_CARDS_VERSION
    from scripts.extract_accepted_sources import EVIDENCE_LABEL
    from scripts.promote_accepted_context import (
        load_json_artifact,
        stable_json,
        write_json_artifact,
    )
except ImportError:
    from build_source_cards import SOURCE_CARDS_VERSION
    from extract_accepted_sources import EVIDENCE_LABEL
    from promote_accepted_context import load_json_artifact, stable_json, write_json_artifact


PACKETS_ARTIFACT_VERSION = "accepted_working_context_packets_v0"


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_]+", "_", value.strip().lower()).strip("_")
    return slug or "unknown"


def _accepted_card(card: dict[str, Any]) -> bool:
    return (
        card.get("usable_by_agents") is True
        and card.get("ingestion_state") == "summarized"
        and card.get("evidence_label") == EVIDENCE_LABEL
        and card.get("not_runtime_authority") is True
        and card.get("runtime_authority") is False
        and card.get("full_body_included") is False
        and card.get("authority_label") != "blocked"
    )


def _compact_card(card: dict[str, Any]) -> dict[str, Any]:
    return {
        "path": card["path"],
        "source_class": card["source_class"],
        "purpose": card["purpose"],
        "known_facts": card["known_facts"],
        "limits": card["limits"],
        "freshness": card["freshness"],
        "authority_label": card["authority_label"],
        "ingestion_state": card["ingestion_state"],
        "usable_by_agents": card["usable_by_agents"],
        "not_runtime_authority": card["not_runtime_authority"],
        "runtime_authority": False,
        "full_body_included": False,
        "provenance": card["provenance"],
    }


def _packet_for_group(
    module: str,
    lane: str,
    source_class: str,
    cards: list[dict[str, Any]],
) -> dict[str, Any]:
    compact_cards = [_compact_card(card) for card in sorted(cards, key=lambda item: item["path"])]
    packet_id = f"accepted_context:{_slug(module)}:{_slug(lane)}:{_slug(source_class)}"
    return {
        "packet_version": PACKETS_ARTIFACT_VERSION,
        "packet_id": packet_id,
        "context_state": "accepted_working_context",
        "context_for_reasoning_only": True,
        "module": module,
        "lane": lane,
        "source_class": source_class,
        "cards": compact_cards,
        "provenance": [
            {
                "source_path": card["path"],
                "source_card_ref": f"{SOURCE_CARDS_VERSION}:{card['path']}",
                "source_sha256": card["freshness"]["source_sha256"],
                "extraction_artifact_version": card["provenance"]["extraction_artifact_version"],
            }
            for card in compact_cards
        ],
        "limits": [
            "Accepted working context only; no raw full source bodies included.",
            "Source cards are parsed evidence, not truth.",
            "Packet retrieval is deterministic exact-filter retrieval only.",
            "No runtime, broker, agent, module activation, or customer deployment authority.",
        ],
        "authority_boundaries": {
            "runtime_authority": False,
            "runtime_activation": False,
            "agent_activation": False,
            "broker_connection": False,
            "customer_deployment": False,
            "context_for_reasoning_only": True,
        },
        "runtime_authority": False,
        "full_body_included": False,
    }


def build_working_context_packets(source_cards_artifact: dict[str, Any]) -> dict[str, Any]:
    grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    excluded: list[dict[str, Any]] = []

    for card in source_cards_artifact.get("cards", []):
        if not _accepted_card(card):
            excluded.append(
                {
                    "path": card.get("path"),
                    "reason_excluded": "card_missing_required_accepted_context_labels",
                    "runtime_authority": bool(card.get("runtime_authority")),
                }
            )
            continue
        grouped[(card["module"], card["lane"], card["source_class"])].append(card)

    for excluded_record in source_cards_artifact.get("excluded_records", []):
        excluded.append(
            {
                "path": excluded_record.get("path"),
                "reason_excluded": excluded_record.get("reason_excluded", "source_card_exclusion"),
                "runtime_authority": False,
            }
        )

    packets = [
        _packet_for_group(module, lane, source_class, cards)
        for (module, lane, source_class), cards in sorted(grouped.items())
    ]

    return {
        "artifact_version": PACKETS_ARTIFACT_VERSION,
        "source_cards_artifact_version": source_cards_artifact.get("artifact_version"),
        "packets": packets,
        "excluded_records": excluded,
        "summary": {
            "packets_total": len(packets),
            "cards_included": sum(len(packet["cards"]) for packet in packets),
            "cards_excluded": len(excluded),
            "accepted_working_context_packets": len(packets),
            "raw_full_bodies_included": False,
            "runtime_authority": False,
        },
    }


def format_operator_packets(artifact: dict[str, Any]) -> str:
    summary = artifact["summary"]
    packet_groups = ", ".join(
        f"{packet['module']}/{packet['lane']}/{packet['source_class']}"
        for packet in artifact.get("packets", [])
    ) or "none"

    lines = [
        "Accepted Working Context Packets v0",
        "",
        "Evidence:",
        f"- {summary['packets_total']} accepted working context packets compile {summary['cards_included']} source cards.",
        f"- Packet groups: {packet_groups}.",
        "- Packets include compact cards, provenance, limits, and authority boundaries.",
        "",
        "Boundary:",
        "- Packets are accepted working context for reasoning only; no raw full bodies are included.",
        "- Packet construction is deterministic grouping by module, lane, and source class.",
        "- `runtime_authority=false`; packets do not grant module or action authority.",
        "",
        "Blocked:",
        f"- {summary['cards_excluded']} cards/refusals are excluded from packets.",
        "- Blocked, unaccepted, runtime-authority, or full-body cards are not packetized.",
        "- No agents, modules, brokers, customer deployment, external tools, or runtime behavior are activated.",
        "",
        "Next safe move:",
        "- Use the retrieval gate for exact packet filters; agents should not read raw source files directly.",
    ]
    return "\n".join(lines)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compile source cards into accepted working context packets."
    )
    parser.add_argument(
        "--source-cards",
        required=True,
        help="Source cards JSON artifact.",
    )
    parser.add_argument(
        "--format",
        choices=("operator", "json"),
        default="operator",
        help="Output format. Defaults to operator.",
    )
    parser.add_argument(
        "--output",
        help="Optional JSON output path for packets.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    source_cards_artifact = load_json_artifact(args.source_cards)
    artifact = build_working_context_packets(source_cards_artifact)

    if args.output:
        write_json_artifact(artifact, args.output)

    if args.format == "json":
        print(stable_json(artifact), end="")
    else:
        print(format_operator_packets(artifact))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
