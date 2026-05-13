#!/usr/bin/env python3
"""Build the deterministic Mission Control world/domain registry read model."""

from __future__ import annotations

import argparse
import json
import sys
from copy import deepcopy
from typing import Any


READ_MODEL_VERSION = "world_domain_registry_v0"
MODE = "deterministic_registry"

EXPECTED_WORLD_IDS = (
    "music_art",
    "finance",
    "operations",
    "security",
    "build",
    "research",
    "communications",
    "business_development",
)

ALLOWED_SIGNAL_TYPES = (
    "quiet",
    "flagged",
    "ready",
    "glowing",
    "hot",
    "critical_consequence",
    "blocked",
    "stale_evidence",
    "inspect_only",
)

CLAIMS_NOT_MADE = [
    "runtime_activation_authority",
    "backend_execution",
    "agent_activation",
    "active_agent_presence",
    "dynamic_world_state",
    "world_status_claims",
    "strategic_gravity_scoring",
    "peripheral_hud_state",
    "external_system_trigger",
    "process_liveness",
    "broker_connection",
    "networking",
    "customer_deployment",
    "sqlite_write",
    "broad_file_scan",
    "private_data_access",
]

REGISTRY_BASIS = [
    "Operator/01_NORTH_STAR_AND_TASTE.md",
    "Operator/05_ORIENTATION_CONTRACT.md",
    "docs/operations/OPENCLAW_OPERATOR_STATUS_GRAMMAR_V0.md",
]

WORLD_RECORDS: tuple[dict[str, Any], ...] = (
    {
        "world_id": "music_art",
        "label": "Music / Art",
        "purpose": "Creative production, taste, practice, releases, live/DJ work, and producer-domain orientation.",
        "examples_of_work": [
            "album and song direction",
            "guitar, production, DJ, and live-show preparation",
            "creative review and producer judgment",
        ],
        "authority_boundary": "Registry-only creative domain; no files are opened, no creative body is ingested, and no agent or app action is authorized.",
    },
    {
        "world_id": "finance",
        "label": "Finance",
        "purpose": "Bounded orientation for obligations, money posture, and future finance workflows without touching private finance, tax, CPA, or banking data.",
        "examples_of_work": [
            "non-sensitive obligation summaries",
            "future receipt-backed finance reviews",
            "approval-gated preparation for later financial workflows",
        ],
        "authority_boundary": "Registry-only finance domain; no private finance, banking, tax, CPA, legal, or credential material is read or acted on.",
    },
    {
        "world_id": "operations",
        "label": "Operations",
        "purpose": "Coordination, execution posture, operator grounding, receipts, status grammar, and next-safe-move orientation.",
        "examples_of_work": [
            "generated operator status review",
            "lane coordination and blocker visibility",
            "readiness contracts and safe next moves",
        ],
        "authority_boundary": "Registry-only operations domain; no runtime mutation, broker wiring, external tool call, or deployment is authorized.",
    },
    {
        "world_id": "security",
        "label": "Security",
        "purpose": "Authorization integrity, containment posture, sensitive boundary visibility, gates, and no-go surface protection.",
        "examples_of_work": [
            "authority boundary inspection",
            "blocked/no-go path posture",
            "future containment and gate readiness records",
        ],
        "authority_boundary": "Registry-only security domain; no secret, credential, private folder, AppData, or runtime-log material is read.",
    },
    {
        "world_id": "build",
        "label": "Build",
        "purpose": "Backend, app, test, and artifact build lanes that turn product intent into deterministic read-models and shipped surfaces.",
        "examples_of_work": [
            "script and test lane status",
            "Mac Mission Control fixture/read-model handoffs",
            "future build readiness records",
        ],
        "authority_boundary": "Registry-only build domain; no app work, runtime activation, deployment, or external build service is invoked.",
    },
    {
        "world_id": "research",
        "label": "Research",
        "purpose": "Source-backed discovery, synthesis, comparison, and future evidence freshness without broad retrieval or vector search.",
        "examples_of_work": [
            "bounded source review",
            "synthesis and doctrine comparison",
            "future research packet readiness",
        ],
        "authority_boundary": "Registry-only research domain; no broad scan, external research call, vector database, or body ingestion is performed.",
    },
    {
        "world_id": "communications",
        "label": "Communications",
        "purpose": "Outward-facing continuity, clients, industry context, drafting posture, and human-world coordination.",
        "examples_of_work": [
            "future draft/readiness review",
            "client or industry context orientation",
            "support and relationship continuity",
        ],
        "authority_boundary": "Registry-only communications domain; no email, message, post, customer contact, or external send is performed.",
    },
    {
        "world_id": "business_development",
        "label": "Business Development",
        "purpose": "Opportunity mapping, customer-specific surface planning, proposals, partnerships, and economic leverage lanes.",
        "examples_of_work": [
            "future opportunity records",
            "customer-specific Mission Control planning",
            "proposal and partnership readiness",
        ],
        "authority_boundary": "Registry-only business-development domain; no customer deployment, outreach, contract, billing, or external action is authorized.",
    },
)


def stable_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _world_with_registry_fields(record: dict[str, Any]) -> dict[str, Any]:
    world = deepcopy(record)
    world.update(
        {
            "allowed_signal_types": list(ALLOWED_SIGNAL_TYPES),
            "signal_vocabulary_only": True,
            "runtime_authority": False,
            "activation_allowed": False,
            "backend_execution": False,
            "current_status_source": "registry_only",
            "dynamic_status_supported": False,
            "strategic_gravity_supported": False,
            "agent_presence_supported": False,
            "evidence_refs": [],
            "claims_not_made": list(CLAIMS_NOT_MADE),
        }
    )
    return world


def build_world_domain_registry() -> dict[str, Any]:
    worlds = [_world_with_registry_fields(record) for record in WORLD_RECORDS]
    return {
        "read_model_version": READ_MODEL_VERSION,
        "mode": MODE,
        "runtime_authority": False,
        "activation_allowed": False,
        "backend_execution": False,
        "dynamic_world_state": False,
        "strategic_gravity_supported": False,
        "agent_presence_supported": False,
        "current_status_source": "registry_only",
        "allowed_signal_types": list(ALLOWED_SIGNAL_TYPES),
        "signal_vocabulary_only": True,
        "active_signal_claims": [],
        "world_count": len(worlds),
        "worlds": worlds,
        "registry_basis": list(REGISTRY_BASIS),
        "claims_not_made": list(CLAIMS_NOT_MADE),
    }


def format_operator_world_domain_registry(read_model: dict[str, Any]) -> str:
    world_ids = ", ".join(f"`{world['world_id']}`" for world in read_model["worlds"])
    signal_types = ", ".join(f"`{signal}`" for signal in read_model["allowed_signal_types"])
    lines = [
        "World / Domain Registry v0",
        "",
        "Evidence:",
        (
            f"- Registered {read_model['world_count']} durable worlds/domains as "
            "registry-only records."
        ),
        f"- Worlds: {world_ids}.",
        f"- Allowed signal types are vocabulary only: {signal_types}.",
        "- Registry basis uses repo-local doctrine/status grammar references; no world file bodies are read.",
        "",
        "Boundary:",
        "- This is a deterministic metadata/read-model registry, not dynamic world status.",
        "- `runtime_authority=false`; `activation_allowed=false`; `backend_execution=false`.",
        "- `dynamic_world_state=false`; `strategic_gravity_supported=false`; `agent_presence_supported=false`.",
        "- It does not claim live health, active agents, peripheral HUD state, external triggers, networking, or customer deployment.",
        "",
        "Blocked:",
        "- Dynamic world state, strategic gravity scoring, and agent presence records are not implemented in this lane.",
        "- Runtime activation, agent activation, broker wiring, external tools, customer deployment, SQLite writes, and private-data access remain blocked.",
        "",
        "Next safe move:",
        (
            "- Let app surfaces render worlds from this registry; add a separate "
            "deterministic world-status or evidence-freshness read-model before "
            "claiming live/dynamic world behavior."
        ),
    ]
    return "\n".join(lines)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build the deterministic Mission Control world/domain registry read model."
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
    read_model = build_world_domain_registry()

    if args.format == "json":
        print(stable_json(read_model), end="")
    else:
        print(format_operator_world_domain_registry(read_model))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
