#!/usr/bin/env python3
"""Build conservative per-world status from the deterministic world registry."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

try:
    from scripts.build_world_domain_registry import build_world_domain_registry
except ImportError:
    from build_world_domain_registry import build_world_domain_registry


READ_MODEL_VERSION = "world_status_v0"
MODE = "deterministic_registry_status"

CLAIMS_NOT_MADE = [
    "runtime_activation_authority",
    "backend_execution",
    "backend_execution_authorization",
    "agent_activation",
    "active_agent_presence",
    "dynamic_world_state",
    "dynamic_attention_state",
    "strategic_gravity_scoring",
    "strategic_gravity_support",
    "live_health_claim",
    "process_liveness",
    "broker_connection",
    "networking",
    "external_tool_call",
    "customer_deployment",
    "sqlite_write",
    "broad_file_scan",
    "private_data_access",
    "full_body_ingest",
]


def stable_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _world_status_record(world: dict[str, Any]) -> dict[str, Any]:
    world_id = world["world_id"]
    return {
        "world_id": world_id,
        "label": world["label"],
        "state": "inspect_only",
        "state_source": "registry_only",
        "evidence": [
            f"`{world_id}` is present in World / Domain Registry v0.",
            "Status is derived from deterministic registry metadata only.",
            "No live, dynamic, runtime, agent, or strategic-gravity input is read.",
        ],
        "boundary": [
            world["authority_boundary"],
            "This record is for inspection only and does not authorize backend execution.",
            "No world file bodies, private data, runtime state, live health, agent presence, or strategic scoring are read or claimed.",
        ],
        "blocked": [
            "Dynamic attention states require deterministic evidence that is not implemented in v0.",
            "Runtime activation, backend execution, agent activation, broker wiring, external tools, networking, and customer deployment remain blocked.",
        ],
        "next_safe_move": (
            f"Add explicit evidence freshness and strategic-gravity inputs before changing `{world_id}` "
            "beyond inspect-only."
        ),
        "runtime_authority": False,
        "activation_allowed": False,
        "backend_execution": False,
        "backend_execution_authorized": False,
        "claims_not_made": list(CLAIMS_NOT_MADE),
    }


def build_world_status(
    *,
    world_domain_registry: dict[str, Any] | None = None,
) -> dict[str, Any]:
    registry = world_domain_registry or build_world_domain_registry()
    worlds = [_world_status_record(world) for world in registry["worlds"]]
    return {
        "read_model_version": READ_MODEL_VERSION,
        "mode": MODE,
        "runtime_authority": False,
        "activation_allowed": False,
        "backend_execution": False,
        "backend_execution_authorized": False,
        "dynamic_world_state": False,
        "strategic_gravity_supported": False,
        "agent_presence_supported": False,
        "world_count": len(worlds),
        "worlds": worlds,
        "world_status_source": "world_domain_registry_v0",
        "state_source": "registry_only",
        "status_mode": "inspect_only_registry_backed",
        "registry_basis": registry.get("registry_basis", []),
        "claims_not_made": list(CLAIMS_NOT_MADE),
    }


def format_operator_world_status(read_model: dict[str, Any]) -> str:
    world_ids = ", ".join(f"`{world['world_id']}`" for world in read_model["worlds"])
    lines = [
        "World Status Read-Model v0",
        "",
        "Evidence:",
        (
            f"- {read_model['world_count']} worlds have conservative "
            "registry-backed status records."
        ),
        "- World status is inspect-only / registry-only.",
        f"- Worlds: {world_ids}.",
        "",
        "Boundary:",
        "- World Status v0 reads the deterministic World / Domain Registry only.",
        "- `runtime_authority=false`; `activation_allowed=false`; `backend_execution=false`.",
        "- No dynamic world state, gravity, or agent presence is implemented; live health, runtime action, private-data access, and body ingest are also not implemented.",
        "",
        "Blocked:",
        "- Dynamic world state, strategic gravity scoring, active agent presence, and live health remain unimplemented.",
        "- Runtime activation, backend execution, agent activation, broker wiring, external tools, networking, and customer deployment remain blocked.",
        "",
        "Next safe move:",
        "- Add evidence freshness / strategic gravity inputs before dynamic attention states.",
    ]
    return "\n".join(lines)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build conservative per-world status from the deterministic registry."
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
    read_model = build_world_status()

    if args.format == "json":
        print(stable_json(read_model), end="")
    else:
        print(format_operator_world_status(read_model))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
