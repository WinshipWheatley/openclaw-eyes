"""Agent Handoff Registry V0.

Defines deterministic agent-to-agent and agent-to-worker handoff rules for
OpenClaw. This registry is local read-model/contract work only. It does not
connect external tools, send email, open Gmail/browser/Coupa, mutate ledgers or
workbooks, export PDFs, submit anything, push git state, spawn workers, or make
agents broad autonomous executors.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parent
DEFAULT_READ_MODEL_ROOT = Path("generated/read_models")
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_BRIDGE_EXPORT_ROOT = Path("/mnt/e/openclaw/generated/read_models")
DEFAULT_WIKI_PATH = Path("generated/wiki/openclaw/Agent Handoff Registry.md")

SCHEMA_VERSION = "agent_handoff_registry_v0"
READ_MODEL_ID = "agent_handoff_registry"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
REGISTRY_STATUS = "AGENT_HANDOFF_REGISTRY_READY"
REGISTRY_NOT_READY_STATUS = "AGENT_HANDOFF_REGISTRY_NOT_READY"

PRECONDITION_FILES = {
    "openclaw_workroom_registry": "openclaw_workroom_registry.json",
    "package_event_index": "package_event_index.json",
    "agent_voice_routing": "agent_voice_routing_contract.json",
}

PRECONDITION_STATUSES = {
    "openclaw_workroom_registry": "OPENCLAW_WORKROOM_REGISTRY_READY",
    "package_event_index": "PACKAGE_EVENT_INDEX_READY",
    "agent_voice_routing": "AGENT_VOICE_ROUTING_V0_READY",
}

REQUIRED_HANDOFF_REFS = (
    "cassandra_to_chief_package_needed",
    "cassandra_to_guardian_authority_detected",
    "chief_to_pc_codex_backend_implementation",
    "chief_to_mac_codex_ui_excel_gui_operator_assist",
    "chief_to_guardian_protected_authority",
    "hermes_to_chief_build_packet",
    "niles_to_chief_creative_build_tooling",
    "clara_to_cassandra_internal_review_state",
    "cassandra_external_register_internal_review_state",
)

COMMON_ALLOWED_ACTIONS = (
    "create_local_handoff_packet",
    "attach_collapsed_proof_refs",
    "record_receipt_requirement",
    "request_operator_review",
)

COMMON_BLOCKED_ACTIONS = (
    "connect_external_tool",
    "connect_slack_live",
    "connect_telegram_live",
    "send_message",
    "send_email",
    "open_gmail",
    "open_browser",
    "open_coupa",
    "mutate_ledger",
    "mutate_workbook",
    "export_pdf",
    "mark_paid",
    "submit_portal",
    "grant_authority",
    "use_credentials",
    "spawn_worker_from_handoff",
    "launch_agent_loop",
    "call_external_llm",
    "run_live_provider",
    "push_git",
)

AUTHORITY_BOUNDARY = {
    "external_tool_connect_allowed": False,
    "slack_connect_allowed": False,
    "telegram_live_connect_allowed": False,
    "message_send_allowed": False,
    "email_send_allowed": False,
    "gmail_allowed": False,
    "browser_access_allowed": False,
    "coupa_allowed": False,
    "portal_submit_allowed": False,
    "ledger_posting_allowed": False,
    "ledger_mutation_allowed": False,
    "workbook_mutation_allowed": False,
    "pdf_export_allowed": False,
    "paid_marking_allowed": False,
    "authority_grant_allowed": False,
    "credential_use_allowed": False,
    "worker_spawn_allowed": False,
    "agent_loop_allowed": False,
    "external_llm_allowed": False,
    "live_provider_allowed": False,
    "git_push_allowed": False,
    "sent": False,
    "paid": False,
}


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _rooted(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def _load_json(path: Path) -> dict[str, Any]:
    path = _rooted(path)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _preconditions(read_model_root: Path) -> list[dict[str, Any]]:
    root = _rooted(read_model_root)
    rows: list[dict[str, Any]] = []
    for ref, filename in PRECONDITION_FILES.items():
        path = root / filename
        payload = _load_json(path)
        observed = str(payload.get("status") or payload.get("contract_status") or "")
        required = PRECONDITION_STATUSES[ref]
        rows.append(
            {
                "precondition_ref": ref,
                "required_status": required,
                "observed_status": observed,
                "ready": observed == required,
                "source_ref": f"generated/read_models/{filename}",
            }
        )
    return rows


def _handoff(
    *,
    handoff_ref: str,
    from_agent: str,
    to_agent_or_worker: str,
    channel_ref: str,
    trigger_condition: str,
    package_type: str,
    allowed_actions: tuple[str, ...] = (),
    blocked_actions: tuple[str, ...] = (),
    from_register: str = "",
    to_register: str = "",
) -> dict[str, Any]:
    allowed = tuple(dict.fromkeys((*COMMON_ALLOWED_ACTIONS, *allowed_actions)))
    blocked = tuple(dict.fromkeys((*COMMON_BLOCKED_ACTIONS, *blocked_actions)))
    return {
        "handoff_ref": handoff_ref,
        "from_agent": from_agent,
        "to_agent_or_worker": to_agent_or_worker,
        "channel_ref": channel_ref,
        "from_register": from_register,
        "to_register": to_register,
        "trigger_condition": trigger_condition,
        "package_type": package_type,
        "allowed_actions": list(allowed),
        "blocked_actions": list(blocked),
        "requires_operator_approval": True,
        "receipt_required": True,
    }


def build_handoffs() -> list[dict[str, Any]]:
    return [
        _handoff(
            handoff_ref="cassandra_to_chief_package_needed",
            from_agent="cassandra",
            to_agent_or_worker="chief",
            channel_ref="operations_chief_workboard",
            trigger_condition="A work-log, invoice, correspondence, or follow-up item needs a package, diagnostic, or queue decision.",
            package_type="package_request_handoff_packet",
            allowed_actions=(
                "summarize_finance_or_correspondence_context",
                "request_package_queue_staging",
            ),
            blocked_actions=("create_invoice_from_handoff", "send_correspondence_from_handoff"),
        ),
        _handoff(
            handoff_ref="cassandra_to_guardian_authority_detected",
            from_agent="cassandra",
            to_agent_or_worker="guardian",
            channel_ref="security_guardian_gates",
            trigger_condition="Send, email, calendar, credential, PII, protected access, portal, ledger, or paid authority appears.",
            package_type="protected_authority_gate_packet",
            allowed_actions=(
                "summarize_authority_request",
                "request_guardian_gate_review",
            ),
            blocked_actions=("send_email_from_handoff", "open_calendar_from_handoff", "use_credential_from_handoff"),
        ),
        _handoff(
            handoff_ref="chief_to_pc_codex_backend_implementation",
            from_agent="chief",
            to_agent_or_worker="pc_codex",
            channel_ref="build_openclaw_backend",
            trigger_condition="A locally bounded backend package is ready for implementation or validation on PC.",
            package_type="pc_codex_backend_worker_packet",
            allowed_actions=(
                "prepare_backend_worker_packet",
                "request_local_code_validation",
                "record_worker_output_receipt",
            ),
            blocked_actions=("spawn_worker_without_operator_packet", "run_live_provider_from_worker_packet"),
        ),
        _handoff(
            handoff_ref="chief_to_mac_codex_ui_excel_gui_operator_assist",
            from_agent="chief",
            to_agent_or_worker="mac_codex",
            channel_ref="build_mission_control_mac",
            trigger_condition="Mission Control UI, Excel review surface, GUI operator-assist, or Mac-specific display work is ready for a Mac worker packet.",
            package_type="mac_codex_operator_assist_worker_packet",
            allowed_actions=(
                "prepare_mac_worker_packet",
                "request_ui_or_gui_validation",
                "record_worker_output_receipt",
            ),
            blocked_actions=("mutate_excel_from_handoff", "run_gui_automation_from_handoff"),
        ),
        _handoff(
            handoff_ref="chief_to_guardian_protected_authority",
            from_agent="chief",
            to_agent_or_worker="guardian",
            channel_ref="security_guardian_gates",
            trigger_condition="A package asks for send, submit, ledger, credential, browser, Coupa, Gmail, workbook, paid, or other protected authority.",
            package_type="protected_package_gate_packet",
            allowed_actions=(
                "summarize_package_authority_request",
                "request_guardian_block_or_approval_readback",
            ),
            blocked_actions=("grant_package_authority_from_handoff", "submit_from_handoff", "mark_paid_from_handoff"),
        ),
        _handoff(
            handoff_ref="hermes_to_chief_build_packet",
            from_agent="hermes",
            to_agent_or_worker="chief",
            channel_ref="operations_chief_workboard",
            trigger_condition="An architecture recommendation becomes concrete build work or a package queue candidate.",
            package_type="architecture_to_build_packet",
            allowed_actions=(
                "convert_recommendation_to_build_packet",
                "attach_tradeoff_summary",
            ),
            blocked_actions=("activate_runtime_from_recommendation", "migrate_from_recommendation"),
        ),
        _handoff(
            handoff_ref="niles_to_chief_creative_build_tooling",
            from_agent="niles",
            to_agent_or_worker="chief",
            channel_ref="operations_chief_workboard",
            trigger_condition="A creative recommendation needs app, build, tooling, metadata, or automation support.",
            package_type="creative_to_build_tooling_packet",
            allowed_actions=(
                "summarize_creative_tooling_need",
                "request_build_packet_review",
            ),
            blocked_actions=("publish_creative_artifact_from_handoff", "mutate_creative_source_from_handoff"),
        ),
        _handoff(
            handoff_ref="clara_to_cassandra_internal_review_state",
            from_agent="cassandra",
            to_agent_or_worker="cassandra",
            channel_ref="business_development_capital_hilton",
            from_register="clara_reid_external",
            to_register="cassandra_internal",
            trigger_condition="Cassandra has a Clara Reid client-facing draft artifact that needs internal review state, follow-up tracking, or correspondence staging.",
            package_type="external_register_internal_review_packet",
            allowed_actions=(
                "record_draft_review_state",
                "request_internal_correspondence_followup",
                "switch_register_without_agent_handoff",
            ),
            blocked_actions=("send_client_draft_from_handoff", "expose_internal_agent_names_to_client"),
        ),
        _handoff(
            handoff_ref="cassandra_external_register_internal_review_state",
            from_agent="cassandra",
            to_agent_or_worker="cassandra",
            channel_ref="business_development_capital_hilton",
            from_register="clara_reid_external",
            to_register="cassandra_internal",
            trigger_condition="Cassandra has a Clara Reid client-facing draft artifact that needs internal review state, follow-up tracking, or correspondence staging.",
            package_type="external_register_internal_review_packet",
            allowed_actions=(
                "record_draft_review_state",
                "request_internal_correspondence_followup",
                "switch_register_without_agent_handoff",
            ),
            blocked_actions=("send_client_draft_from_handoff", "expose_internal_agent_names_to_client"),
        ),
    ]


def build_examples() -> list[dict[str, Any]]:
    return [
        {
            "example_ref": "customer_reports_bug",
            "operator_phrase": "Customer reports bug",
            "route_summary": "Cassandra records the intake, Chief shapes the build package, then PC_CODEX receives a backend worker packet.",
            "route_path": [
                "cassandra_to_chief_package_needed",
                "chief_to_pc_codex_backend_implementation",
            ],
            "channel_refs": [
                "operations_chief_workboard",
                "build_openclaw_backend",
            ],
            "terminal_package_type": "pc_codex_backend_worker_packet",
            "authority_note": "No external tool connection or autonomous execution is granted by the route.",
        },
        {
            "example_ref": "capital_hilton_proposal_accepted",
            "operator_phrase": "Capital Hilton proposal accepted",
            "route_summary": "Cassandra switches from the Clara Reid external register to the internal register for review and finance/business-development follow-up packaging.",
            "route_path": [
                "clara_to_cassandra_internal_review_state",
                "cassandra_external_register_internal_review_state",
                "cassandra_to_chief_package_needed",
            ],
            "channel_refs": [
                "business_development_capital_hilton",
                "operations_chief_workboard",
            ],
            "terminal_package_type": "package_request_handoff_packet",
            "authority_note": "Proposal acceptance does not mark paid and does not submit anything.",
        },
        {
            "example_ref": "submit_invoice",
            "operator_phrase": "Submit invoice",
            "route_summary": "Chief must route to Guardian for a protected gate before any operator-assist path can be considered.",
            "route_path": [
                "chief_to_guardian_protected_authority",
            ],
            "channel_refs": [
                "security_guardian_gates",
            ],
            "terminal_package_type": "protected_package_gate_packet",
            "authority_note": "Submit remains blocked until explicit operator-present approval exists.",
        },
    ]


def _handoff_matrix(handoffs: list[Mapping[str, Any]]) -> dict[str, list[str]]:
    matrix: dict[str, list[str]] = {}
    for handoff in handoffs:
        matrix.setdefault(str(handoff["from_agent"]), []).append(str(handoff["handoff_ref"]))
    return {agent: sorted(refs) for agent, refs in sorted(matrix.items())}


def build_read_model(
    *,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    preconditions = _preconditions(read_model_root)
    preconditions_ready = all(item["ready"] for item in preconditions)
    handoffs = build_handoffs()
    handoff_refs = tuple(handoff["handoff_ref"] for handoff in handoffs)
    all_required_handoffs_present = set(handoff_refs) == set(REQUIRED_HANDOFF_REFS)
    all_receipts_required = all(handoff["receipt_required"] is True for handoff in handoffs)
    all_require_operator_approval = all(handoff["requires_operator_approval"] is True for handoff in handoffs)
    all_block_external_tools = all("connect_external_tool" in handoff["blocked_actions"] for handoff in handoffs)
    status = REGISTRY_STATUS if preconditions_ready and all_required_handoffs_present else REGISTRY_NOT_READY_STATUS
    return {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "generated_at": generated_at,
        "status": status,
        "purpose": "Deterministic handoff rules for routing agent work to channels, agents, and worker packet lanes without broad execution authority.",
        "mode": "local_read_model_contract_only_no_external_tools",
        "preconditions": preconditions,
        "handoff_count": len(handoffs),
        "required_handoff_refs": list(REQUIRED_HANDOFF_REFS),
        "handoffs": handoffs,
        "handoff_matrix": _handoff_matrix(handoffs),
        "examples": build_examples(),
        "truth_and_scope_rules": [
            "A handoff creates a packet request or review state; it does not execute the work.",
            "Workers receive bounded packet output lanes only; this registry cannot spawn workers.",
            "Protected authority routes to Guardian before any operator-assist path.",
            "Client-facing drafts hand back to internal review before follow-up state changes.",
            "Every handoff requires a receipt.",
        ],
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "source_refs": [
            "generated/read_models/openclaw_workroom_registry.json",
            "generated/read_models/package_event_index.json",
            "generated/read_models/agent_voice_routing_contract.json",
        ],
        "machine_proof": {
            "local_only": True,
            "read_model_contract_only": True,
            "preconditions_ready": preconditions_ready,
            "all_required_handoffs_present": all_required_handoffs_present,
            "all_receipts_required": all_receipts_required,
            "all_require_operator_approval": all_require_operator_approval,
            "all_handoffs_block_external_tools": all_block_external_tools,
            "external_tool_connected": False,
            "email_send_performed": False,
            "gmail_access_performed": False,
            "browser_access_performed": False,
            "coupa_access_performed": False,
            "ledger_mutation_performed": False,
            "workbook_mutation_performed": False,
            "pdf_export_performed": False,
            "submit_performed": False,
            "paid_marking_performed": False,
            "worker_spawn_performed": False,
            "agent_loop_launched": False,
            "git_push_performed": False,
            "unsafe_true_grants_absent": all(value is False for value in AUTHORITY_BOUNDARY.values()),
        },
    }


def build_wiki(read_model: Mapping[str, Any]) -> str:
    lines = [
        "# Agent Handoff Registry",
        "",
        f"Status: `{read_model['status']}`",
        "",
        "This registry defines deterministic handoff rules for routing agent work to the right channel, agent, or worker packet lane. It does not connect external tools or execute work.",
        "",
        f"Handoffs: `{read_model['handoff_count']}`",
        "",
        "## Handoffs",
        "",
    ]
    for handoff in read_model["handoffs"]:
        lines.extend(
            [
                f"### `{handoff['handoff_ref']}`",
                "",
                f"- From: `{handoff['from_agent']}`",
                f"- To: `{handoff['to_agent_or_worker']}`",
                f"- Channel: `{handoff['channel_ref']}`",
                f"- Trigger: {handoff['trigger_condition']}",
                f"- Package type: `{handoff['package_type']}`",
                "- Requires operator approval: `true`",
                "- Receipt required: `true`",
                "",
            ]
        )
    lines.extend(
        [
            "## Examples",
            "",
        ]
    )
    for example in read_model["examples"]:
        lines.append(f"- `{example['example_ref']}`: {example['route_summary']}")
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            "- No external tool connection.",
            "- No email send.",
            "- No Gmail/browser/Coupa access.",
            "- No ledger or workbook mutation.",
            "- No PDF export.",
            "- No submit or mark-paid.",
            "- No git push.",
            "- No worker spawn or agent loop launch.",
            "- Every handoff requires a receipt and operator review.",
        ]
    )
    return "\n".join(lines) + "\n"


def export_agent_handoff_registry(
    *,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
    export_root: Path = DEFAULT_EXPORT_ROOT,
    bridge_export_root: Path | None = DEFAULT_BRIDGE_EXPORT_ROOT,
    wiki_path: Path = DEFAULT_WIKI_PATH,
    generated_at: str | None = None,
) -> dict[str, str]:
    read_model = build_read_model(read_model_root=read_model_root, generated_at=generated_at)
    export_root = _rooted(export_root)
    export_root.mkdir(parents=True, exist_ok=True)
    read_model_path = export_root / JSON_EXPORT_NAME
    read_model_path.write_text(stable_json(read_model), encoding="utf-8")

    bridge_path = ""
    if bridge_export_root is not None:
        bridge_export_root.mkdir(parents=True, exist_ok=True)
        bridge_file = bridge_export_root / JSON_EXPORT_NAME
        bridge_file.write_text(stable_json(read_model), encoding="utf-8")
        bridge_path = bridge_file.as_posix()

    wiki_path = _rooted(wiki_path)
    wiki_path.parent.mkdir(parents=True, exist_ok=True)
    wiki_path.write_text(build_wiki(read_model), encoding="utf-8")
    return {
        "status": str(read_model["status"]),
        "read_model_path": read_model_path.as_posix(),
        "bridge_read_model_path": bridge_path,
        "wiki_path": wiki_path.as_posix(),
        "handoff_count": str(read_model["handoff_count"]),
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Export Agent Handoff Registry V0.")
    parser.add_argument("--read-model-root", default=str(DEFAULT_READ_MODEL_ROOT))
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT))
    parser.add_argument("--bridge-export-root", default=str(DEFAULT_BRIDGE_EXPORT_ROOT))
    parser.add_argument("--wiki-path", default=str(DEFAULT_WIKI_PATH))
    parser.add_argument("--generated-at")
    parser.add_argument("--no-bridge", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    result = export_agent_handoff_registry(
        read_model_root=Path(args.read_model_root),
        export_root=Path(args.export_root),
        bridge_export_root=None if args.no_bridge else Path(args.bridge_export_root),
        wiki_path=Path(args.wiki_path),
        generated_at=args.generated_at,
    )
    print(stable_json(result), end="")
    return 0 if result["status"] == REGISTRY_STATUS else 1


if __name__ == "__main__":
    raise SystemExit(main())
