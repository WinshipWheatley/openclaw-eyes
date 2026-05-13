#!/usr/bin/env python3
"""Build the deterministic Mission Control Helm State read model."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

try:
    from scripts.build_source_inventory import build_inventory
    from scripts.check_runtime_activation_gate import build_activation_gate_report
    from scripts.generate_operator_status import CONTEXT_GATE_SCRIPTS
except ImportError:
    from build_source_inventory import build_inventory
    from check_runtime_activation_gate import build_activation_gate_report
    from generate_operator_status import CONTEXT_GATE_SCRIPTS


ROOT = Path(__file__).resolve().parents[1]
READ_MODEL_VERSION = "helm_state_v0"

STATE_DEFINITIONS: dict[str, dict[str, Any]] = {
    "quiet_helm": {
        "state": "quiet_helm",
        "state_family": "system_integrity",
        "label": "Quiet Helm",
        "meaning": "No surfaced fault or interruption is currently reported by the available generated read-models.",
        "required_evidence": [
            "generated status is current",
            "required deterministic read-model artifacts are present",
            "no activation or authority overreach is reported",
        ],
        "must_never_imply": [
            "nothing is happening",
            "all work is complete",
            "runtime status has been checked",
            "agent activation",
            "future capabilities are available",
        ],
    },
    "flagged_world": {
        "state": "flagged_world",
        "state_family": "operational_attention",
        "label": "Flagged World",
        "meaning": "A world has a specific item available for inspection or attention.",
        "required_evidence": ["a deterministic world record naming the item and source basis"],
        "must_never_imply": ["urgency", "interruption", "system fault", "runtime action"],
    },
    "glowing_world": {
        "state": "glowing_world",
        "state_family": "strategic_gravity",
        "label": "Glowing World",
        "meaning": "A world has increased readiness, opportunity, or strategic usefulness.",
        "required_evidence": ["a deterministic world/gravity record explaining the readiness or opportunity basis"],
        "must_never_imply": ["emergency", "failure", "panic", "execution authority"],
    },
    "hot_world": {
        "state": "hot_world",
        "state_family": "strategic_gravity",
        "label": "Hot World",
        "meaning": "A world deserves serious attention because consequence is rising.",
        "required_evidence": ["a deterministic consequence record with reason, scope, and source basis"],
        "must_never_imply": ["notification volume", "agent noise", "fake urgency", "automatic interruption"],
    },
    "critical_consequence": {
        "state": "critical_consequence",
        "state_family": "strategic_gravity",
        "label": "Critical Consequence",
        "meaning": "A narrow state for material consequence affecting safety, money, trust, legal/security posture, major opportunity, autonomy, or system integrity.",
        "required_evidence": ["a deterministic high-consequence record and interruption reason"],
        "must_never_imply": ["ordinary backlog", "routine reminder", "general incompleteness", "productivity pressure"],
    },
    "ready_world": {
        "state": "ready_world",
        "state_family": "operational_attention",
        "label": "Ready World",
        "meaning": "A world is prepared for low-friction inspection or entry.",
        "required_evidence": ["prepared context, accepted packet, source card, or world-readiness record"],
        "must_never_imply": ["work has executed", "approval has been granted", "the world is complete"],
    },
    "agent_present": {
        "state": "agent_present",
        "state_family": "operational_attention",
        "label": "Agent Present",
        "meaning": "A domain officer is relevant because unresolved domain work, review, alignment, hardening, taste, communication, or architecture judgment is needed.",
        "required_evidence": ["an agent-presence record explaining agent, world, reason, and evidence basis"],
        "must_never_imply": ["system fault", "agent activation", "chatbot availability", "autonomous execution"],
    },
    "approval_needed": {
        "state": "approval_needed",
        "state_family": "system_integrity",
        "label": "Approval Needed",
        "meaning": "The system has reached a boundary where operator consent is required before any later action could proceed.",
        "required_evidence": ["an approval-needed record or blocked gate naming the requested authority"],
        "must_never_imply": ["approval has been granted", "execution is queued", "operator consent can be bypassed"],
    },
    "blocked_locked": {
        "state": "blocked_locked",
        "state_family": "system_integrity",
        "label": "Blocked / Locked",
        "meaning": "A path is unavailable because proof, authority, implementation, safety, or approval is missing.",
        "required_evidence": ["a blocker reason, missing prerequisite, unsupported capability marker, or failed gate"],
        "must_never_imply": ["crash", "dead end", "bad outcome", "operator failure"],
    },
    "security_concern": {
        "state": "security_concern",
        "state_family": "system_integrity",
        "label": "Security Concern",
        "meaning": "A containment, authorization, integrity, gate, or boundary issue deserves attention.",
        "required_evidence": ["a deterministic security or boundary record"],
        "must_never_imply": ["ordinary backlog", "generic incompleteness", "runtime mutation"],
    },
    "system_fault": {
        "state": "system_fault",
        "state_family": "system_integrity",
        "label": "System Fault",
        "meaning": "A required proof, artifact, gate, or authority invariant failed inside the deterministic read-model scope.",
        "required_evidence": ["failed check, missing required artifact, unavailable required read-model, or authority overreach"],
        "must_never_imply": ["ordinary domain work", "agent presence", "routine backlog"],
    },
    "stale_evidence": {
        "state": "stale_evidence",
        "state_family": "system_integrity",
        "label": "Stale Evidence",
        "meaning": "The displayed claim may be based on old or insufficiently current generated evidence.",
        "required_evidence": ["generated status check failed or freshness rule is not satisfied"],
        "must_never_imply": ["the claim is false", "runtime failure", "agent failure"],
    },
    "inspect_only": {
        "state": "inspect_only",
        "state_family": "read_only",
        "label": "Inspect Only",
        "meaning": "The helm may be inspected as deterministic read-model context, but no backend action or activation is authorized.",
        "required_evidence": [
            "generated status is current",
            "source/context read-models are available",
            "runtime activation gate remains blocked",
        ],
        "must_never_imply": [
            "execution authority",
            "operator approval",
            "agent activation",
            "broker wiring",
            "customer deployment",
        ],
    },
    "next_safe_move": {
        "state": "next_safe_move",
        "state_family": "read_only",
        "label": "Next Safe Move",
        "meaning": "A bounded next step is available without exceeding current evidence or authority.",
        "required_evidence": ["a deterministic status, gate, blocker, or readiness record"],
        "must_never_imply": ["hidden automation", "silent execution", "runtime activation"],
    },
}

CLAIMS_NOT_MADE = [
    "runtime_activation_authority",
    "backend_execution",
    "agent_activation",
    "active_agent_presence",
    "dynamic_world_state",
    "strategic_gravity_scoring",
    "peripheral_hud_state",
    "external_system_trigger",
    "process_liveness",
    "broker_connection",
    "customer_deployment",
    "broad_file_scan",
    "vector_search",
]


def stable_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _bool_text(value: bool) -> str:
    return "true" if value else "false"


def _generated_status_check(root: Path) -> dict[str, Any]:
    script_path = root / "scripts" / "generate_operator_status.py"
    if not script_path.is_file():
        return {
            "checked": True,
            "current": False,
            "status": "status_script_missing",
            "exit_code": None,
        }

    try:
        result = subprocess.run(
            [sys.executable, str(script_path), "--check"],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return {
            "checked": True,
            "current": False,
            "status": "status_check_error",
            "exit_code": None,
        }

    return {
        "checked": True,
        "current": result.returncode == 0,
        "status": "current" if result.returncode == 0 else "stale_or_missing",
        "exit_code": result.returncode,
    }


def _generated_artifact_state(root: Path) -> dict[str, Any]:
    current_state = root / "Operator" / "GENERATED_CURRENT_STATE.md"
    next_actions = root / "Operator" / "GENERATED_NEXT_ACTIONS.md"
    return {
        "current_state_path": current_state.relative_to(root).as_posix(),
        "current_state_exists": current_state.is_file(),
        "next_actions_path": next_actions.relative_to(root).as_posix(),
        "next_actions_exists": next_actions.is_file(),
    }


def _context_gate_availability(root: Path) -> dict[str, Any]:
    gates = [
        {
            "label": label,
            "version": version,
            "path": path,
            "available": (root / path).is_file(),
        }
        for label, version, path in CONTEXT_GATE_SCRIPTS
    ]
    available = sum(1 for gate in gates if gate["available"])
    return {
        "available": available,
        "total": len(gates),
        "all_available": available == len(gates),
        "gates": gates,
    }


def _select_state(
    *,
    generated_status: dict[str, Any],
    context_gates: dict[str, Any],
    activation_gate: dict[str, Any],
) -> dict[str, Any]:
    if (
        activation_gate.get("activation_allowed") is not False
        or activation_gate.get("runtime_authority") is not False
    ):
        return STATE_DEFINITIONS["system_fault"]

    if generated_status.get("checked") and generated_status.get("current") is not True:
        return STATE_DEFINITIONS["stale_evidence"]

    if not context_gates.get("all_available", False):
        return STATE_DEFINITIONS["blocked_locked"]

    return STATE_DEFINITIONS["inspect_only"]


def build_helm_state(
    *,
    root: Path = ROOT,
    generated_status: dict[str, Any] | None = None,
    run_generated_status_check: bool = True,
    source_inventory: dict[str, Any] | None = None,
    activation_gate: dict[str, Any] | None = None,
) -> dict[str, Any]:
    root = root.resolve()
    generated_status = (
        generated_status
        if generated_status is not None
        else (
            _generated_status_check(root)
            if run_generated_status_check
            else {"checked": False, "current": None, "status": "not_checked", "exit_code": None}
        )
    )
    source_inventory = source_inventory or build_inventory(root=root)
    activation_gate = activation_gate or build_activation_gate_report()
    context_gates = _context_gate_availability(root)
    generated_artifacts = _generated_artifact_state(root)
    helm_state = _select_state(
        generated_status=generated_status,
        context_gates=context_gates,
        activation_gate=activation_gate,
    )

    inventory_summary = source_inventory.get("summary", {})
    missing_prerequisites = activation_gate.get("missing_prerequisites", [])

    evidence = [
        f"Generated operator status check is `{generated_status['status']}`.",
        (
            f"Generated status artifacts present: current_state="
            f"{_bool_text(generated_artifacts['current_state_exists'])}, "
            f"next_actions={_bool_text(generated_artifacts['next_actions_exists'])}."
        ),
        (
            f"Source Inventory reports {inventory_summary.get('allowlisted_records', 0)} "
            "allowlisted metadata-only records with body_ingested=false."
        ),
        (
            f"Source Inventory represents {inventory_summary.get('blocked_records', 0)} "
            "blocked no-go examples without body read."
        ),
        (
            f"Context gate scripts available: {context_gates['available']}/"
            f"{context_gates['total']}."
        ),
        (
            f"Runtime activation gate state is `{activation_gate.get('gate_state')}`; "
            f"activation_allowed={_bool_text(activation_gate.get('activation_allowed') is True)}."
        ),
    ]

    boundary = [
        "Helm State v0 is a deterministic read-model for inspection, not a runtime control surface.",
        "It does not promote, extract, summarize, packetize, retrieve, or activate context.",
        "It does not call runtime services, agents, brokers, external tools, or customer deployment.",
        "Dynamic worlds, agent presence, peripheral HUD, and strategic gravity scoring are not supported backend records in v0.",
        "`runtime_authority=false`; `backend_execution=false`; `activation_allowed=false`.",
    ]

    blocked = [
        "Runtime/module activation remains blocked by the v0 readiness contract.",
        (
            "Missing activation prerequisites: "
            + ", ".join(f"`{item}`" for item in missing_prerequisites)
            + "."
        ),
        "Dynamic world states, agent presence records, and strategic gravity scoring remain future-gated.",
        "No agents, modules, brokers, customer deployment, external tools, or runtime mutation are activated.",
    ]

    next_safe_move = (
        "Use this read-model as inspect-only cockpit context; add deterministic "
        "world/domain, agent-presence, evidence-freshness, and strategic-gravity "
        "records before the app claims dynamic helm behavior."
    )

    return {
        "read_model_version": READ_MODEL_VERSION,
        "mode": "deterministic_read_model",
        "runtime_authority": False,
        "activation_allowed": False,
        "backend_execution": False,
        "helm_state": helm_state,
        "state_definitions": STATE_DEFINITIONS,
        "evidence": evidence,
        "boundary": boundary,
        "blocked": blocked,
        "next_safe_move": next_safe_move,
        "worlds": [],
        "worlds_model": {
            "supported": False,
            "reason": "not_yet_implemented",
        },
        "agent_presence": [],
        "agent_presence_model": {
            "supported": False,
            "reason": "not_yet_implemented",
            "live_agents_claimed": False,
        },
        "strategic_gravity": {
            "supported": False,
            "reason": "not_yet_implemented",
        },
        "generated_status": generated_status,
        "generated_artifacts": generated_artifacts,
        "source_inventory": {
            "inventory_version": source_inventory.get("inventory_version"),
            "mode": source_inventory.get("mode"),
            "allowlisted_records": inventory_summary.get("allowlisted_records", 0),
            "blocked_records": inventory_summary.get("blocked_records", 0),
            "body_ingested": bool(inventory_summary.get("body_ingested", False)),
            "metadata_only_records": inventory_summary.get("metadata_only_records", 0),
        },
        "context_gates": context_gates,
        "activation_gate": {
            "artifact_version": activation_gate.get("artifact_version"),
            "gate_state": activation_gate.get("gate_state"),
            "activation_allowed": False,
            "runtime_authority": False,
            "missing_prerequisites": missing_prerequisites,
            "live_runtime_status_claimed": False,
        },
        "claims_not_made": CLAIMS_NOT_MADE,
    }


def format_operator_helm_state(read_model: dict[str, Any]) -> str:
    helm = read_model["helm_state"]
    lines = [
        "Helm State Read-Model v0",
        "",
        "Evidence:",
        (
            f"- Emitted helm state is `{helm['state']}` ({helm['state_family']}): "
            f"{helm['meaning']}"
        ),
        *[f"- {item}" for item in read_model["evidence"]],
        "",
        "Boundary:",
        *[f"- {item}" for item in read_model["boundary"]],
        "",
        "Blocked:",
        *[f"- {item}" for item in read_model["blocked"]],
        "",
        "Next safe move:",
        f"- {read_model['next_safe_move']}",
    ]
    return "\n".join(lines)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build the deterministic Mission Control Helm State read model."
    )
    parser.add_argument(
        "--format",
        choices=("operator", "json"),
        default="operator",
        help="Output format. Defaults to operator.",
    )
    parser.add_argument(
        "--skip-generated-status-check",
        action="store_true",
        help="Do not run generate_operator_status.py --check before building the read model.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    read_model = build_helm_state(
        run_generated_status_check=not args.skip_generated_status_check
    )

    if args.format == "json":
        print(stable_json(read_model), end="")
    else:
        print(format_operator_helm_state(read_model))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
