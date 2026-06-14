"""Workroom Review Decision Contract V0.

Defines safe operator decisions for Workroom review packets: approve for
record, request rework, or mark informational. This contract records review
decisions only. It does not merge code, push git state, spawn workers, run
child agents, send email, open browser/Gmail/Coupa, mutate ledgers or
workbooks, export PDFs, submit portals, or grant authority.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parent
DEFAULT_READ_MODEL_ROOT = Path("generated/read_models")
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_BRIDGE_EXPORT_ROOT = Path("/mnt/e/openclaw/generated/read_models")
DEFAULT_WIKI_PATH = Path("generated/wiki/openclaw/Workroom Review Decision Contract.md")

SCHEMA_VERSION = "workroom_review_decision_contract_v0"
READ_MODEL_ID = "workroom_review_decision_contract"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
CONTRACT_STATUS = "WORKROOM_REVIEW_DECISION_CONTRACT_READY"
CONTRACT_NOT_READY_STATUS = "WORKROOM_REVIEW_DECISION_CONTRACT_NOT_READY"

PRECONDITION_FILES = {
    "workroom_review_packet_index": "workroom_review_packet_index.json",
    "spawned_worker_package_lifecycle": "spawned_worker_package_lifecycle.json",
}

PRECONDITION_STATUSES = {
    "workroom_review_packet_index": "WORKROOM_REVIEW_PACKET_INDEX_READY",
    "spawned_worker_package_lifecycle": "SPAWNED_WORKER_PACKAGE_LIFECYCLE_READY",
}

DECISION_ACTIONS = (
    "approve_review_packet_for_record",
    "request_review_packet_rework",
    "mark_review_packet_informational",
)

REQUIRED_DECISION_FIELDS = (
    "review_packet_id",
    "decision_action",
    "operator_reviewed",
    "reason",
    "no_push",
    "no_merge",
    "no_business_action",
    "authority_boundary",
)

AUTHORITY_BOUNDARY = {
    "merge_allowed": False,
    "git_push_allowed": False,
    "worker_spawn_allowed": False,
    "child_agent_run_allowed": False,
    "agent_loop_allowed": False,
    "external_llm_allowed": False,
    "external_tool_connect_allowed": False,
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
    "speaker_tool_grant_allowed": False,
    "business_action_allowed": False,
    "sent": False,
    "paid": False,
}

UNSAFE_REQUEST_KEYS = set(AUTHORITY_BOUNDARY) | {
    "push_allowed",
    "merge_performed",
    "git_push_performed",
    "business_action_performed",
    "email_send_performed",
    "submit_performed",
}

ACTION_DEFINITIONS = {
    "approve_review_packet_for_record": {
        "decision_status": "APPROVED_FOR_RECORD_ONLY",
        "display_label": "Approve for record",
        "effect": "operator_review_recorded_only",
        "review_closed": True,
        "rework_requested": False,
        "informational_only": False,
        "next_safe_action": "Record the operator review receipt only; do not merge or push.",
    },
    "request_review_packet_rework": {
        "decision_status": "REWORK_REQUESTED",
        "display_label": "Request rework",
        "effect": "rework_request_receipt_only",
        "review_closed": False,
        "rework_requested": True,
        "informational_only": False,
        "next_safe_action": "Record a rework request receipt only; do not spawn a worker from this decision.",
    },
    "mark_review_packet_informational": {
        "decision_status": "MARKED_INFORMATIONAL",
        "display_label": "Mark informational",
        "effect": "review_closed_without_action",
        "review_closed": True,
        "rework_requested": False,
        "informational_only": True,
        "next_safe_action": "Close the review as informational; no work or business action follows from this decision.",
    },
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
        payload = _load_json(root / filename)
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


def _source_payloads(read_model_root: Path) -> dict[str, dict[str, Any]]:
    root = _rooted(read_model_root)
    return {
        ref: _load_json(root / filename)
        for ref, filename in PRECONDITION_FILES.items()
    }


def _short_hash(parts: list[str]) -> str:
    return hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()[:16]


def _unsafe_true_grants(requested_authority: Mapping[str, Any] | None) -> list[str]:
    if not isinstance(requested_authority, Mapping):
        return []
    return sorted(
        str(key)
        for key, value in requested_authority.items()
        if key in UNSAFE_REQUEST_KEYS and value is True
    )


def _known_packet_ids(packet_index: Mapping[str, Any]) -> list[str]:
    packets = packet_index.get("packets")
    if not isinstance(packets, list):
        return []
    return [
        str(packet.get("review_packet_id"))
        for packet in packets
        if isinstance(packet, Mapping) and packet.get("review_packet_id")
    ]


def build_decision_receipt(
    *,
    review_packet_id: str,
    decision_action: str,
    reason: str = "",
    requested_authority: Mapping[str, Any] | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    review_packet_id = str(review_packet_id or "").strip()
    decision_action = str(decision_action or "").strip()
    unsafe_grants = _unsafe_true_grants(requested_authority)
    action_known = decision_action in ACTION_DEFINITIONS
    accepted = bool(review_packet_id and action_known and not unsafe_grants)
    action = ACTION_DEFINITIONS.get(decision_action, {})
    status = str(action.get("decision_status") or "REJECTED_UNKNOWN_DECISION_ACTION")
    blockers: list[str] = []
    if not review_packet_id:
        blockers.append("missing_review_packet_id")
    if not action_known:
        blockers.append("unknown_decision_action")
    blockers.extend(f"unsafe_true_grant:{key}" for key in unsafe_grants)
    if blockers:
        status = "REJECTED_UNSAFE_OR_INVALID_DECISION"
    receipt_id = f"workroom_review_decision:{_short_hash([review_packet_id, decision_action, generated_at])}"
    return {
        "schema_version": SCHEMA_VERSION,
        "receipt_type": "WORKROOM_REVIEW_DECISION_RECEIPT",
        "receipt_id": receipt_id,
        "generated_at": generated_at,
        "status": status,
        "decision_accepted": accepted,
        "blockers": blockers,
        "review_packet_id": review_packet_id,
        "decision_action": decision_action,
        "operator_reviewed": accepted,
        "reason": str(reason or ""),
        "no_push": True,
        "no_merge": True,
        "no_business_action": True,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "decision_effect": str(action.get("effect") or "none"),
        "review_closed": bool(action.get("review_closed")) if accepted else False,
        "rework_requested": bool(action.get("rework_requested")) if accepted else False,
        "informational_only": bool(action.get("informational_only")) if accepted else False,
        "next_safe_action": str(
            action.get("next_safe_action")
            or "Fix blockers before recording a review decision."
        ),
        "worker_inherits_speaker_authority": False,
        "proof_collapsed_by_default": True,
        "business_action_performed": False,
        "merge_performed": False,
        "git_push_performed": False,
        "worker_spawn_performed": False,
        "email_send_performed": False,
        "ledger_mutation_performed": False,
        "workbook_mutation_performed": False,
        "submit_performed": False,
        "unsafe_true_grants": unsafe_grants,
    }


def _decision_actions() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for action_ref in DECISION_ACTIONS:
        definition = ACTION_DEFINITIONS[action_ref]
        rows.append(
            {
                "decision_action": action_ref,
                "display_label": definition["display_label"],
                "decision_status": definition["decision_status"],
                "effect": definition["effect"],
                "review_closed": definition["review_closed"],
                "rework_requested": definition["rework_requested"],
                "informational_only": definition["informational_only"],
                "operator_reviewed": True,
                "no_push": True,
                "no_merge": True,
                "no_business_action": True,
                "next_safe_action": definition["next_safe_action"],
            }
        )
    return rows


def _example_receipts(packet_index: Mapping[str, Any], generated_at: str) -> list[dict[str, Any]]:
    packet_ids = _known_packet_ids(packet_index)
    packet_id = packet_ids[0] if packet_ids else "review_packet:example"
    return [
        build_decision_receipt(
            review_packet_id=packet_id,
            decision_action=action,
            reason=f"Example {ACTION_DEFINITIONS[action]['display_label'].lower()} decision.",
            generated_at=generated_at,
        )
        for action in DECISION_ACTIONS
    ]


def build_read_model(
    *,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    preconditions = _preconditions(read_model_root)
    preconditions_ready = all(item["ready"] for item in preconditions)
    payloads = _source_payloads(read_model_root)
    packet_index = payloads.get("workroom_review_packet_index", {})
    example_receipts = _example_receipts(packet_index, generated_at) if preconditions_ready else []
    status = CONTRACT_STATUS if preconditions_ready else CONTRACT_NOT_READY_STATUS
    return {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "generated_at": generated_at,
        "status": status,
        "purpose": "Safe operator decision contract for Workroom review packets: approve for record, request rework, or mark informational.",
        "mode": "local_read_model_contract_only_no_merge_push_or_business_action",
        "preconditions": preconditions,
        "decision_actions": _decision_actions(),
        "required_decision_fields": list(REQUIRED_DECISION_FIELDS),
        "example_decision_receipts": example_receipts,
        "rules": [
            "Approval records operator review only.",
            "Approval does not merge or push.",
            "Rework creates a rework request receipt only.",
            "Informational closes the review without action.",
            "All business and external actions remain false.",
            "Worker output does not inherit speaker authority.",
            "Proof refs stay collapsed by default.",
        ],
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "source_refs": [
            "generated/read_models/workroom_review_packet_index.json",
            "generated/read_models/spawned_worker_package_lifecycle.json",
        ],
        "machine_proof": {
            "local_only": True,
            "read_model_contract_only": True,
            "preconditions_ready": preconditions_ready,
            "all_decision_actions_present": set(DECISION_ACTIONS)
            == {row["decision_action"] for row in _decision_actions()},
            "example_receipts_safe": all(receipt["decision_accepted"] for receipt in example_receipts),
            "worker_output_inherits_speaker_authority": False,
            "merge_performed": False,
            "git_push_performed": False,
            "worker_spawn_performed": False,
            "child_agent_run_performed": False,
            "email_send_performed": False,
            "gmail_access_performed": False,
            "browser_access_performed": False,
            "coupa_access_performed": False,
            "ledger_mutation_performed": False,
            "workbook_mutation_performed": False,
            "pdf_export_performed": False,
            "submit_performed": False,
            "paid_marking_performed": False,
            "business_action_performed": False,
            "unsafe_true_grants_absent": all(value is False for value in AUTHORITY_BOUNDARY.values()),
        },
    }


def build_wiki(read_model: Mapping[str, Any]) -> str:
    lines = [
        "# Workroom Review Decision Contract",
        "",
        f"Status: `{read_model['status']}`",
        "",
        "This contract defines safe operator decisions for Workroom review packets. Decisions record review state only.",
        "",
        "## Decision Actions",
        "",
    ]
    for action in read_model["decision_actions"]:
        lines.extend(
            [
                f"### `{action['decision_action']}`",
                "",
                f"- Effect: `{action['effect']}`",
                f"- Status: `{action['decision_status']}`",
                f"- Next safe action: {action['next_safe_action']}",
                "- No push: `true`",
                "- No merge: `true`",
                "- No business action: `true`",
                "",
            ]
        )
    lines.extend(
        [
            "## Boundary",
            "",
            "- Approval records operator review only.",
            "- No merge.",
            "- No git push.",
            "- No worker spawn or child agent run.",
            "- No email send.",
            "- No Gmail/browser/Coupa access.",
            "- No ledger or workbook mutation.",
            "- No PDF export.",
            "- No submit or mark-paid.",
            "- No business action.",
            "- Worker output does not inherit speaker authority.",
        ]
    )
    return "\n".join(lines) + "\n"


def export_workroom_review_decision_contract(
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
        "decision_action_count": str(len(read_model["decision_actions"])),
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Export Workroom Review Decision Contract V0.")
    parser.add_argument("--read-model-root", default=str(DEFAULT_READ_MODEL_ROOT))
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT))
    parser.add_argument("--bridge-export-root", default=str(DEFAULT_BRIDGE_EXPORT_ROOT))
    parser.add_argument("--wiki-path", default=str(DEFAULT_WIKI_PATH))
    parser.add_argument("--generated-at")
    parser.add_argument("--no-bridge", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    result = export_workroom_review_decision_contract(
        read_model_root=Path(args.read_model_root),
        export_root=Path(args.export_root),
        bridge_export_root=None if args.no_bridge else Path(args.bridge_export_root),
        wiki_path=Path(args.wiki_path),
        generated_at=args.generated_at,
    )
    print(stable_json(result), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
