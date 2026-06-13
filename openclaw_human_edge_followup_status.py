"""OpenClaw human-edge swarm follow-up status.

This is a local status/read-model generator. It does not call models, external
APIs, Gmail, Calendar, Telegram, Hermes, or business systems.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parent
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_BRIDGE_ROOT = Path("/mnt/e/openclaw/generated/read_models")
DEFAULT_WIKI_PATH = Path("generated/wiki/openclaw/OpenClaw Human Edge Followup Status.md")

SCHEMA_VERSION = "openclaw_human_edge_followup_status_v0"
READ_MODEL_ID = "openclaw_human_edge_followup_status"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
GRAPH_JSON_EXPORT_NAME = "openclaw_human_edge_test_coverage_graph.json"
READY_STATUS = "OPENCLAW_HUMAN_EDGE_SWARM_FOLLOWUP_READY"

AUTHORITY_BOUNDARY = {
    "external_api_called": False,
    "model_invoked": False,
    "telegram_send_performed": False,
    "gmail_called": False,
    "email_sent": False,
    "calendar_api_called": False,
    "calendar_event_created": False,
    "calendar_event_deleted": False,
    "hermes_started": False,
    "worker_spawned": False,
    "guardian_approval_created": False,
    "invoice_marked_paid": False,
    "ledger_mutated": False,
    "workbook_mutated": False,
    "runtime_policy_changed": False,
    "confirmed_reference_data_created": False,
}

UNSAFE_TRUE_KEYS = set(AUTHORITY_BOUNDARY) | {
    "paid",
    "sent",
    "submitted",
    "executed",
    "authority_granted",
    "external_effect",
    "business_action_performed",
}


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _rooted(path: Path | str) -> Path:
    path = Path(path)
    return path if path.is_absolute() else ROOT / path


def _short_hash(payload: Any, *, length: int = 16) -> str:
    return hashlib.sha256(stable_json(payload).encode("utf-8")).hexdigest()[:length]


def unsafe_true_paths(value: Any, path: str = "$") -> list[str]:
    found: list[str] = []
    if isinstance(value, Mapping):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if key in UNSAFE_TRUE_KEYS and child is True:
                found.append(child_path)
            found.extend(unsafe_true_paths(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.extend(unsafe_true_paths(child, f"{path}[{index}]"))
    return sorted(found)


def build_coverage_graph() -> dict[str, Any]:
    nodes = [
        {
            "id": "cassandra-guided-review",
            "label": "Cassandra Guided Review",
            "type": "project",
            "description": "Data Room question flow for provisional review answers and confirmation handling.",
            "metadata": {"status": "tested_local", "authority": "provisional_only"},
        },
        {
            "id": "operator-context-switchboard",
            "label": "Operator Context Switchboard",
            "type": "project",
            "description": "Routes messy operator language across active review, detours, and protected-action boundaries.",
            "metadata": {"status": "tested_local", "authority": "routing_only"},
        },
        {
            "id": "human-edge-lab",
            "label": "Human Edge Lab",
            "type": "project",
            "description": "Local dry-run harness for messy human-language probes.",
            "metadata": {"status": "ready", "run_mode": "test_dry_run"},
        },
        {
            "id": "test-effect-adapters",
            "label": "Test Effect Adapters",
            "type": "technology",
            "description": "Converts risky effects into labeled dry-run receipts during Test Mode.",
            "metadata": {"status": "ready", "external_effects": "blocked"},
        },
        {
            "id": "dry-run-email",
            "label": "Dry-Run Email Receipt",
            "type": "solution",
            "description": "Records test email intent without sending mail or calling Gmail.",
            "metadata": {"email_send_performed": False, "target": "winshiplive@gmail.com"},
        },
        {
            "id": "dry-run-calendar",
            "label": "Dry-Run Calendar Receipt",
            "type": "solution",
            "description": "Records test calendar intent without calling Calendar or creating/deleting an event.",
            "metadata": {"calendar_api_called": False, "calendar_event_created": False},
        },
        {
            "id": "finance-payment-watch",
            "label": "Finance Payment Watch",
            "type": "project",
            "description": "Finance / Capital Hilton proof-to-response lane for missing payment evidence.",
            "metadata": {"status": "tested_local", "paid_marking_allowed": False},
        },
        {
            "id": "data-room-pending-candidates",
            "label": "Data Room Pending Candidates",
            "type": "concept",
            "description": "Candidate answers remain unrecorded until explicit confirmation.",
            "metadata": {"confirmed_reference_data_created": False, "runtime_policy_changed": False},
        },
        {
            "id": "industry-best-practices-fix",
            "label": "Industry Best Practices Fix",
            "type": "solution",
            "description": "Normalizes vague best-practice replies into a concrete trust-gating candidate.",
            "metadata": {"commit": "86d5156"},
        },
        {
            "id": "scope-question-fix",
            "label": "Recording-Scope Question Fix",
            "type": "solution",
            "description": "Explains where a pending candidate would go instead of treating the question as a new lane.",
            "metadata": {"commit": "86d5156"},
        },
        {
            "id": "live-email-transport",
            "label": "Live Email Transport",
            "type": "issue",
            "description": "Live Gmail/email transport was not tested; dry-run receipts must not be treated as sends.",
            "metadata": {"status": "blocked_pending_explicit_transport_test"},
        },
        {
            "id": "live-calendar-transport",
            "label": "Live Calendar Transport",
            "type": "issue",
            "description": "Live Calendar create/delete was not tested; dry-run receipts must not be treated as events.",
            "metadata": {"status": "blocked_pending_explicit_transport_test"},
        },
        {
            "id": "hermes-boundary",
            "label": "Hermes Boundary",
            "type": "issue",
            "description": "Hermes was not started and remains outside this local dry-run pass.",
            "metadata": {"status": "not_started"},
        },
    ]
    edges = [
        ("operator-context-switchboard", "cassandra-guided-review", "preserves active review context"),
        ("human-edge-lab", "cassandra-guided-review", "replays messy Data Room phrases"),
        ("human-edge-lab", "operator-context-switchboard", "probes detours and resume behavior"),
        ("test-effect-adapters", "human-edge-lab", "supports labeled dry-run receipts"),
        ("test-effect-adapters", "dry-run-email", "implements dry-run email receipt"),
        ("test-effect-adapters", "dry-run-calendar", "implements dry-run calendar receipt"),
        ("dry-run-email", "live-email-transport", "contrasts dry-run proof with live transport"),
        ("dry-run-calendar", "live-calendar-transport", "contrasts dry-run proof with live transport"),
        ("finance-payment-watch", "operator-context-switchboard", "depends on correct lane routing"),
        ("data-room-pending-candidates", "cassandra-guided-review", "guards provisional answers"),
        ("industry-best-practices-fix", "data-room-pending-candidates", "improves candidate wording"),
        ("scope-question-fix", "data-room-pending-candidates", "explains pending candidate scope"),
        ("scope-question-fix", "operator-context-switchboard", "prevents bogus lane request"),
        ("hermes-boundary", "human-edge-lab", "requires separate boundary test"),
    ]
    return {
        "schema_version": "OPENCLAW_HUMAN_EDGE_TEST_COVERAGE_GRAPH_V0",
        "graph_id": "openclaw_human_edge_test_coverage_graph",
        "title": "OpenClaw Human-Edge Test Coverage Map",
        "nodes": nodes,
        "edges": [
            {
                "id": f"edge:{_short_hash({'source': source, 'target': target, 'label': label})}",
                "source": source,
                "target": target,
                "relationship": label,
            }
            for source, target, label in edges
        ],
    }


def build_payload(*, generated_at: str | None = None) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    graph = build_coverage_graph()
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "status": READY_STATUS,
        "generated_at": generated_at,
        "source_commits": [
            {"commit": "588dab7", "summary": "add Cassandra human edge lab"},
            {"commit": "6dd5273", "summary": "add calendar dry run test receipt"},
            {"commit": "86d5156", "summary": "fix Data Room pending candidate explanations"},
        ],
        "graphiffy_status": {
            "requested": True,
            "connector": "Ace Knowledge Graph",
            "latest_result": "connector_timeout",
            "local_fallback_graph_id": graph["graph_id"],
            "operator_note": "Graph connector did not return a durable artifact; local graph JSON is the fallback truth.",
        },
        "completed_local_outcomes": [
            {
                "outcome_id": "dry_run_email_to_operator",
                "label": "Dry-run email route",
                "result": "receipt_recorded_no_send",
                "external_effect": False,
                "email_send_performed": False,
            },
            {
                "outcome_id": "dry_run_calendar_event",
                "label": "Dry-run calendar route",
                "result": "receipt_recorded_no_calendar_call",
                "external_effect": False,
                "calendar_api_called": False,
                "calendar_event_created": False,
                "calendar_event_deleted": False,
            },
            {
                "outcome_id": "finance_payment_watch_coworker_help",
                "label": "Finance payment-watch answer",
                "result": "returns_payment_evidence_guidance",
                "paid_marking_allowed": False,
                "ledger_mutation_allowed": False,
            },
            {
                "outcome_id": "data_room_pending_candidate_scope",
                "label": "Data Room pending-candidate explanation",
                "result": "explains_provisional_scope_without_recording",
                "runtime_policy_changed": False,
                "confirmed_reference_data_created": False,
            },
        ],
        "remaining_work": [
            {
                "gap_id": "live_email_transport_not_proven",
                "status": "blocked_pending_explicit_transport_test",
                "reason": "Dry-run email routing is proven, but no live Gmail/send path was exercised.",
                "next_safe_action": "Create an allowlisted live-email transport smoke packet with Guardian/HITL boundary before any send.",
            },
            {
                "gap_id": "live_calendar_transport_not_proven",
                "status": "blocked_pending_explicit_transport_test",
                "reason": "Dry-run calendar routing is proven, but no Calendar API create/delete path was exercised.",
                "next_safe_action": "Create an allowlisted live-calendar create/delete smoke packet before any Calendar call.",
            },
            {
                "gap_id": "graphiffy_connector_timeout",
                "status": "partial_local_fallback_available",
                "reason": "Ace Knowledge Graph timed out after schema-compliant retry.",
                "next_safe_action": "Retry Ace later or use the local fallback graph JSON for operator review.",
            },
            {
                "gap_id": "hermes_not_started",
                "status": "not_tested_by_design",
                "reason": "Hermes was outside the local dry-run pass and should not be started as a generic sidecar.",
                "next_safe_action": "Run a separate Hermes boundary/status probe before any Hermes live behavior test.",
            },
            {
                "gap_id": "post_fix_live_cassandra_smoke_needed",
                "status": "waiting_for_operator_telegram_message",
                "reason": "Code tests pass and Cassandra was restarted, but no post-restart live Telegram turn has verified the new reply.",
                "next_safe_action": "Ask Cassandra: 'use industry best practices' and then 'are you just recording it or is it going into the Data Room thing?'",
            },
        ],
        "next_safe_live_test_sequence": [
            "Verify the Data Room pending-candidate fix through live Telegram with operator-sent messages only.",
            "Keep email and Calendar in dry-run until explicit live transport packets exist.",
            "Treat Hermes as a separate boundary test; do not start it from this follow-up.",
        ],
        "coverage_graph": graph,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "safety_confirmation": {
            "external_apis_called_by_generator": False,
            "models_invoked_by_generator": False,
            "business_systems_mutated": False,
            "dry_run_outputs_labeled": True,
            "live_transport_not_claimed": True,
        },
    }
    payload["unsafe_true_paths"] = unsafe_true_paths(payload)
    return payload


def render_wiki(payload: Mapping[str, Any]) -> str:
    remaining = "\n".join(
        f"- `{item['gap_id']}`: {item['status']} — {item['next_safe_action']}"
        for item in payload["remaining_work"]
    )
    outcomes = "\n".join(
        f"- `{item['outcome_id']}`: {item['result']}"
        for item in payload["completed_local_outcomes"]
    )
    return (
        "# OpenClaw Human Edge Followup Status\n\n"
        f"Status: `{payload['status']}`\n\n"
        "## Completed Local Outcomes\n"
        f"{outcomes}\n\n"
        "## Remaining Work\n"
        f"{remaining}\n\n"
        "## Graphiffy/Ace Status\n"
        f"- Result: `{payload['graphiffy_status']['latest_result']}`\n"
        f"- Local fallback graph: `{payload['graphiffy_status']['local_fallback_graph_id']}`\n\n"
        "## Safety\n"
        "- No live email, Calendar, Telegram send, model invocation, Hermes start, or business mutation is authorized by this packet.\n"
        "- Dry-run receipts are test evidence only; they are not proof of live transport.\n"
    )


def write_outputs(
    *,
    export_root: str | Path = DEFAULT_EXPORT_ROOT,
    bridge_root: str | Path = DEFAULT_BRIDGE_ROOT,
    wiki_path: str | Path = DEFAULT_WIKI_PATH,
    generated_at: str | None = None,
) -> dict[str, Any]:
    payload = build_payload(generated_at=generated_at)
    export_root = _rooted(export_root)
    bridge_root = Path(bridge_root)
    wiki_path = _rooted(wiki_path)
    read_model_path = export_root / JSON_EXPORT_NAME
    graph_path = export_root / GRAPH_JSON_EXPORT_NAME
    bridge_path = bridge_root / JSON_EXPORT_NAME
    bridge_graph_path = bridge_root / GRAPH_JSON_EXPORT_NAME

    read_model_path.parent.mkdir(parents=True, exist_ok=True)
    graph_path.parent.mkdir(parents=True, exist_ok=True)
    bridge_path.parent.mkdir(parents=True, exist_ok=True)
    wiki_path.parent.mkdir(parents=True, exist_ok=True)

    read_model_path.write_text(stable_json(payload), encoding="utf-8")
    graph_path.write_text(stable_json(payload["coverage_graph"]), encoding="utf-8")
    shutil.copy2(read_model_path, bridge_path)
    shutil.copy2(graph_path, bridge_graph_path)
    wiki_path.write_text(render_wiki(payload), encoding="utf-8")

    payload["artifact_paths"] = {
        "read_model_path": read_model_path.as_posix(),
        "bridge_path": bridge_path.as_posix(),
        "graph_path": graph_path.as_posix(),
        "bridge_graph_path": bridge_graph_path.as_posix(),
        "wiki_path": wiki_path.as_posix(),
    }
    read_model_path.write_text(stable_json(payload), encoding="utf-8")
    shutil.copy2(read_model_path, bridge_path)
    return payload


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Write OpenClaw human-edge follow-up status artifacts.")
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT))
    parser.add_argument("--bridge-root", default=str(DEFAULT_BRIDGE_ROOT))
    parser.add_argument("--wiki-path", default=str(DEFAULT_WIKI_PATH))
    parser.add_argument("--generated-at", default="")
    args = parser.parse_args(list(argv) if argv is not None else None)
    payload = write_outputs(
        export_root=args.export_root,
        bridge_root=args.bridge_root,
        wiki_path=args.wiki_path,
        generated_at=args.generated_at or None,
    )
    print(stable_json({"status": payload["status"], **payload["artifact_paths"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
