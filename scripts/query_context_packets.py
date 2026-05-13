#!/usr/bin/env python3
"""Retrieve accepted working context packets through exact deterministic filters."""

from __future__ import annotations

import argparse
import sys
from typing import Any

try:
    from scripts.build_working_context_packets import PACKETS_ARTIFACT_VERSION
    from scripts.promote_accepted_context import load_json_artifact, stable_json
except ImportError:
    from build_working_context_packets import PACKETS_ARTIFACT_VERSION
    from promote_accepted_context import load_json_artifact, stable_json


RETRIEVAL_ARTIFACT_VERSION = "agent_context_retrieval_gate_v0"


def _safe_packet(packet: dict[str, Any]) -> bool:
    if packet.get("context_state") != "accepted_working_context":
        return False
    if packet.get("context_for_reasoning_only") is not True:
        return False
    if packet.get("runtime_authority") is not False:
        return False
    if packet.get("full_body_included") is not False:
        return False
    boundaries = packet.get("authority_boundaries", {})
    if boundaries.get("runtime_activation") is not False:
        return False
    if boundaries.get("agent_activation") is not False:
        return False
    for card in packet.get("cards", []):
        if card.get("authority_label") == "blocked":
            return False
        if card.get("full_body_included") is not False:
            return False
        if "extracted_text" in card:
            return False
    return True


def _refused(reason: str, filters: dict[str, str], packets_artifact: dict[str, Any]) -> dict[str, Any]:
    return {
        "artifact_version": RETRIEVAL_ARTIFACT_VERSION,
        "source_packets_artifact_version": packets_artifact.get("artifact_version"),
        "query": filters,
        "query_allowed": False,
        "query_state": reason,
        "context_for_reasoning_only": True,
        "runtime_authority": False,
        "packets": [],
        "summary": {
            "packets_returned": 0,
            "raw_files_read": False,
            "raw_full_bodies_returned": False,
            "runtime_authority": False,
        },
    }


def query_context_packets(
    packets_artifact: dict[str, Any],
    *,
    module: str | None = None,
    source_class: str | None = None,
    lane: str | None = None,
) -> dict[str, Any]:
    filters = {
        key: value
        for key, value in {
            "module": module,
            "source_class": source_class,
            "lane": lane,
        }.items()
        if value
    }
    if not filters:
        return _refused("refused_broad_query", filters, packets_artifact)

    safe_packets = [
        packet
        for packet in packets_artifact.get("packets", [])
        if _safe_packet(packet)
    ]
    if not safe_packets:
        return _refused("refused_no_safe_packets", filters, packets_artifact)

    for key, value in filters.items():
        known_values = {packet.get(key) for packet in safe_packets}
        if value not in known_values:
            return _refused(f"refused_unknown_{key}", filters, packets_artifact)

    matches = [
        packet
        for packet in safe_packets
        if all(packet.get(key) == value for key, value in filters.items())
    ]
    if not matches:
        return _refused("refused_no_exact_packet_match", filters, packets_artifact)

    return {
        "artifact_version": RETRIEVAL_ARTIFACT_VERSION,
        "source_packets_artifact_version": packets_artifact.get("artifact_version"),
        "query": filters,
        "query_allowed": True,
        "query_state": "allowed_exact_filter_match",
        "context_for_reasoning_only": True,
        "runtime_authority": False,
        "packets": matches,
        "summary": {
            "packets_returned": len(matches),
            "raw_files_read": False,
            "raw_full_bodies_returned": False,
            "runtime_authority": False,
        },
    }


def format_operator_retrieval(result: dict[str, Any]) -> str:
    summary = result["summary"]
    filters = ", ".join(f"{key}={value}" for key, value in sorted(result["query"].items())) or "none"
    packet_ids = "; ".join(f"`{packet['packet_id']}`" for packet in result.get("packets", [])) or "none"

    lines = [
        "Agent Context Retrieval Gate v0",
        "",
        "Evidence:",
        f"- Query state is `{result['query_state']}` for exact filters: {filters}.",
        f"- {summary['packets_returned']} accepted working context packets returned: {packet_ids}.",
        "- Returned packets are compact context packets, not raw source files.",
        "",
        "Boundary:",
        "- Retrieval reads packet artifacts only; it does not read raw source files or extracted body artifacts.",
        "- Retrieval is exact-filter only by module, lane, or source class; no fuzzy broad retrieval or vector search.",
        "- Output is `context_for_reasoning_only`; `runtime_authority=false`.",
        "",
        "Blocked:",
        "- Broad, unknown, unsafe, blocked, runtime-authority, and full-body packet requests are refused.",
        "- No agents, modules, brokers, customer deployment, external tools, or runtime behavior are activated.",
        "",
        "Next safe move:",
        "- Use returned packets as reasoning context only; runtime or module action still requires a separate blocked activation gate.",
    ]
    return "\n".join(lines)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Retrieve accepted working context packets by exact deterministic filters."
    )
    parser.add_argument("--packets", required=True, help="Accepted working context packets JSON artifact.")
    parser.add_argument("--module", help="Exact module filter.")
    parser.add_argument("--source-class", help="Exact source_class filter.")
    parser.add_argument("--lane", help="Exact lane filter.")
    parser.add_argument(
        "--format",
        choices=("operator", "json"),
        default="operator",
        help="Output format. Defaults to operator.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    packets_artifact = load_json_artifact(args.packets)
    result = query_context_packets(
        packets_artifact,
        module=args.module,
        source_class=args.source_class,
        lane=args.lane,
    )

    if args.format == "json":
        print(stable_json(result), end="")
    else:
        print(format_operator_retrieval(result))
    return 0 if result["query_allowed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
