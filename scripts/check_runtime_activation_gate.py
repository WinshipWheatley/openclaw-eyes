#!/usr/bin/env python3
"""Report runtime/module activation readiness as a blocked v0 gate."""

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


ACTIVATION_GATE_VERSION = "runtime_module_activation_gate_v0"

REQUIRED_PREREQUISITES = [
    "explicit_operator_approval",
    "rollback_plan",
    "module_manifest_validation",
    "runtime_boundary_declaration",
    "logging_receipt_path",
    "dry_run_proof",
]


def _packet_summary(packets_artifact: dict[str, Any] | None) -> dict[str, Any]:
    if not packets_artifact:
        return {
            "packets_artifact_present": False,
            "source_packets_artifact_version": None,
            "accepted_packets": 0,
            "cards_available": 0,
        }

    packets = packets_artifact.get("packets", [])
    return {
        "packets_artifact_present": True,
        "source_packets_artifact_version": packets_artifact.get("artifact_version"),
        "accepted_packets": sum(
            1
            for packet in packets
            if packet.get("context_state") == "accepted_working_context"
        ),
        "cards_available": sum(len(packet.get("cards", [])) for packet in packets),
    }


def build_activation_gate_report(
    packets_artifact: dict[str, Any] | None = None,
) -> dict[str, Any]:
    packets = _packet_summary(packets_artifact)
    return {
        "artifact_version": ACTIVATION_GATE_VERSION,
        "gate_state": "blocked_v0_contract",
        "activation_allowed": False,
        "runtime_authority": False,
        "module_activation_authority": False,
        "live_runtime_health_claimed": False,
        "evidence": {
            "packets_artifact_present": packets["packets_artifact_present"],
            "source_packets_artifact_version": packets["source_packets_artifact_version"],
            "accepted_packets": packets["accepted_packets"],
            "cards_available": packets["cards_available"],
            "packets_version_expected": PACKETS_ARTIFACT_VERSION,
        },
        "missing_prerequisites": REQUIRED_PREREQUISITES,
        "scope": {
            "agent_activation": False,
            "broker_wiring": False,
            "module_activation": False,
            "customer_deployment": False,
            "external_tools": False,
            "runtime_mutation": False,
            "runtime_health_check": False,
            "sqlite_touched": False,
        },
        "next_safe_move": (
            "Keep packets as reasoning context; prepare explicit approval, rollback, "
            "manifest validation, boundary, receipt, and dry-run evidence in a later lane."
        ),
    }


def format_operator_activation_gate(report: dict[str, Any]) -> str:
    evidence = report["evidence"]
    missing = ", ".join(f"`{item}`" for item in report["missing_prerequisites"])

    lines = [
        "Runtime / Module Activation Gate v0",
        "",
        "Evidence:",
        (
            f"- Gate state is `{report['gate_state']}`; activation_allowed="
            f"{str(report['activation_allowed']).lower()}."
        ),
        (
            f"- Accepted packets visible to the gate: {evidence['accepted_packets']} "
            f"with {evidence['cards_available']} compact cards."
        ),
        "- This report is a readiness contract only, not a live runtime check.",
        "",
        "Boundary:",
        "- v0 always blocks runtime/module activation; it only names prerequisites for a future approved lane.",
        "- It does not call runtime services, agents, brokers, external tools, customer deployment, or SQLite writers.",
        "- `runtime_authority=false`; no live runtime health is claimed.",
        "",
        "Blocked:",
        f"- Missing prerequisites: {missing}.",
        "- Module activation, agent activation, broker wiring, customer deployment, external tools, and runtime mutation remain blocked.",
        "",
        "Next safe move:",
        f"- {report['next_safe_move']}",
    ]
    return "\n".join(lines)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Report runtime/module activation as a blocked v0 readiness gate."
    )
    parser.add_argument(
        "--packets",
        help="Optional accepted working context packets JSON artifact.",
    )
    parser.add_argument(
        "--format",
        choices=("operator", "json"),
        default="operator",
        help="Output format. Defaults to operator.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    packets_artifact = load_json_artifact(args.packets) if args.packets else None
    report = build_activation_gate_report(packets_artifact)

    if args.format == "json":
        print(stable_json(report), end="")
    else:
        print(format_operator_activation_gate(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
