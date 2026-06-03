"""Approval Request Queue V0.

Publishes a central, non-executing queue for operator approval requests. The
queue gathers decisions Guardian, Chief, and Cassandra may need from Winship,
but it does not perform the approved action.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parent
DEFAULT_READ_MODEL_ROOT = Path("generated/read_models")
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_BRIDGE_EXPORT_ROOT = Path("/mnt/e/openclaw/generated/read_models")
DEFAULT_WIKI_PATH = Path("generated/wiki/openclaw/Approval Request Queue.md")
DEFAULT_SQLITE_PATH = Path("generated/system_knowledge/approval_request_queue.sqlite")

SCHEMA_VERSION = "approval_request_queue_v0"
READ_MODEL_ID = "approval_request_queue"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
STATUS_READY = "APPROVAL_REQUEST_QUEUE_READY"
STATUS_NOT_READY = "APPROVAL_REQUEST_QUEUE_NOT_READY"

PRECONDITIONS = {
    "gate_decision_ledger": {
        "filename": "gate_decision_ledger.json",
        "accepted_statuses": ["GATE_DECISION_LEDGER_READY"],
        "optional": False,
    },
    "workroom_review_decision_contract": {
        "filename": "workroom_review_decision_contract.json",
        "accepted_statuses": ["WORKROOM_REVIEW_DECISION_CONTRACT_READY"],
        "optional": True,
    },
    "operator_next_decision": {
        "filename": "operator_next_decision.json",
        "accepted_statuses": ["OPERATOR_NEXT_DECISION_READY", "READY"],
        "optional": False,
    },
}

AUTHORITY_BOUNDARY = {
    "email_send_allowed": False,
    "ledger_posting_allowed": False,
    "browser_access_allowed": False,
    "gmail_allowed": False,
    "coupa_allowed": False,
    "portal_submit_allowed": False,
    "workbook_mutation_allowed": False,
    "pdf_export_allowed": False,
    "business_action_allowed": False,
    "sent": False,
    "paid": False,
}

REQUEST_TEMPLATES = [
    {
        "gate_ref": "workroom_review_record",
        "requested_action": "approve_review_packet_for_record",
        "target_world_ref": "build",
        "target_thread_ref": "workroom_review",
        "requested_by_agent": "chief",
        "owner_speaker_ref": "chief",
        "plain_summary": "Approve a review packet for record only, with no merge or push.",
        "risk_summary": "Low. This records operator review state but does not execute code or business actions.",
        "safe_options": ["approve_for_record", "request_rework", "mark_informational"],
        "forbidden_options": ["merge_code", "push_git", "spawn_worker"],
    },
    {
        "gate_ref": "workroom_review_rework",
        "requested_action": "request_review_packet_rework",
        "target_world_ref": "build",
        "target_thread_ref": "workroom_review",
        "requested_by_agent": "chief",
        "owner_speaker_ref": "chief",
        "plain_summary": "Ask for review packet rework without spawning a worker automatically.",
        "risk_summary": "Low. Rework is recorded; execution requires a later package.",
        "safe_options": ["record_rework_request", "leave_pending"],
        "forbidden_options": ["run_worker", "spawn_worker", "push_git"],
    },
    {
        "gate_ref": "send_email",
        "requested_action": "approve_email_draft_send",
        "target_world_ref": "finance",
        "target_thread_ref": "capital_hilton",
        "requested_by_agent": "cassandra",
        "owner_speaker_ref": "guardian",
        "plain_summary": "Approve an already prepared email draft for manual or gated send.",
        "risk_summary": "Protected. Email send remains pending until explicit operator action and executor gate.",
        "safe_options": ["review_draft", "reject_request", "keep_pending"],
        "forbidden_options": ["send_email", "open_gmail_without_operator", "mark_sent_without_receipt"],
    },
    {
        "gate_ref": "coupa_submit",
        "requested_action": "approve_coupa_submit",
        "target_world_ref": "finance",
        "target_thread_ref": "capital_hilton",
        "requested_by_agent": "chief",
        "owner_speaker_ref": "guardian",
        "plain_summary": "Approve Coupa submit only through a separate operator-assisted provider gate.",
        "risk_summary": "Protected portal action. This queue cannot submit to Coupa.",
        "safe_options": ["review_provider_gate", "reject_request", "keep_pending"],
        "forbidden_options": ["coupa_submit", "open_coupa_unattended", "mark_submitted_without_receipt"],
    },
    {
        "gate_ref": "workbook_mutation",
        "requested_action": "approve_workbook_mutation",
        "target_world_ref": "finance",
        "target_thread_ref": "st_annes",
        "requested_by_agent": "cassandra",
        "owner_speaker_ref": "guardian",
        "plain_summary": "Approve source workbook edits only after operator review.",
        "risk_summary": "Source-data mutation. Excel remains blocked here.",
        "safe_options": ["review_change_summary", "reject_request", "keep_pending"],
        "forbidden_options": ["mutate_workbook", "open_excel_helper", "rewrite_source_rows"],
    },
    {
        "gate_ref": "pdf_export",
        "requested_action": "approve_pdf_export",
        "target_world_ref": "finance",
        "target_thread_ref": "st_annes",
        "requested_by_agent": "cassandra",
        "owner_speaker_ref": "guardian",
        "plain_summary": "Approve PDF export only through a later artifact-producing workflow.",
        "risk_summary": "Client-facing artifact creation. This queue records approval need only.",
        "safe_options": ["review_export_intent", "reject_request", "keep_pending"],
        "forbidden_options": ["export_pdf", "replace_pdf_without_lineage", "send_pdf"],
    },
    {
        "gate_ref": "ledger_post",
        "requested_action": "approve_ledger_post",
        "target_world_ref": "finance",
        "target_thread_ref": "capital_hilton",
        "requested_by_agent": "guardian",
        "owner_speaker_ref": "guardian",
        "plain_summary": "Approve ledger posting only after separate payment or posting evidence exists.",
        "risk_summary": "Protected accounting action. No ledger write can occur from this queue.",
        "safe_options": ["wait_for_payment_evidence", "reject_request", "keep_pending"],
        "forbidden_options": ["post_ledger", "mark_paid", "create_business_truth_without_evidence"],
    },
]


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


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(stable_json(payload), encoding="utf-8")


def _approval_request_id(gate_ref: str, requested_action: str) -> str:
    digest = hashlib.sha256(f"{gate_ref}:{requested_action}".encode("utf-8")).hexdigest()[:16]
    return f"approval_request:{digest}"


def _preconditions(read_model_root: Path) -> list[dict[str, Any]]:
    root = _rooted(read_model_root)
    rows: list[dict[str, Any]] = []
    for ref, contract in PRECONDITIONS.items():
        path = root / str(contract["filename"])
        exists = path.exists()
        payload = _load_json(path)
        observed = str(payload.get("status") or payload.get("contract_status") or "")
        accepted = [str(status) for status in contract["accepted_statuses"]]
        optional = bool(contract.get("optional"))
        ready = observed in accepted or (optional and not exists)
        rows.append(
            {
                "precondition_ref": ref,
                "observed_status": observed if exists else "OPTIONAL_ABSENT" if optional else "",
                "accepted_statuses": accepted,
                "optional": optional,
                "ready": ready,
                "source_ref": f"generated/read_models/{contract['filename']}",
            }
        )
    return rows


def _approval_requests(generated_at: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for template in REQUEST_TEMPLATES:
        rows.append(
            {
                "approval_request_id": _approval_request_id(
                    str(template["gate_ref"]), str(template["requested_action"])
                ),
                "gate_ref": str(template["gate_ref"]),
                "requested_action": str(template["requested_action"]),
                "target_world_ref": str(template["target_world_ref"]),
                "target_thread_ref": str(template["target_thread_ref"]),
                "requested_by_agent": str(template["requested_by_agent"]),
                "owner_speaker_ref": str(template["owner_speaker_ref"]),
                "plain_summary": str(template["plain_summary"]),
                "risk_summary": str(template["risk_summary"]),
                "safe_options": list(template["safe_options"]),
                "forbidden_options": list(template["forbidden_options"]),
                "proof_refs": [
                    "generated/read_models/gate_decision_ledger.json",
                    "generated/read_models/operator_next_decision.json",
                ],
                "status": "pending",
                "business_action_performed": False,
                "created_at": generated_at,
            }
        )
    return rows


def _write_sqlite(sqlite_path: Path, requests: list[Mapping[str, Any]]) -> None:
    sqlite_path = _rooted(sqlite_path)
    sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(sqlite_path)
    try:
        conn.execute("DROP TABLE IF EXISTS approval_requests")
        conn.execute(
            """
            CREATE TABLE approval_requests (
              approval_request_id TEXT PRIMARY KEY,
              gate_ref TEXT NOT NULL,
              requested_action TEXT NOT NULL,
              target_world_ref TEXT NOT NULL,
              target_thread_ref TEXT NOT NULL,
              requested_by_agent TEXT NOT NULL,
              owner_speaker_ref TEXT NOT NULL,
              plain_summary TEXT NOT NULL,
              risk_summary TEXT NOT NULL,
              safe_options_json TEXT NOT NULL,
              forbidden_options_json TEXT NOT NULL,
              proof_refs_json TEXT NOT NULL,
              status TEXT NOT NULL,
              business_action_performed INTEGER NOT NULL,
              created_at TEXT NOT NULL
            )
            """
        )
        conn.executemany(
            """
            INSERT INTO approval_requests (
              approval_request_id, gate_ref, requested_action, target_world_ref,
              target_thread_ref, requested_by_agent, owner_speaker_ref,
              plain_summary, risk_summary, safe_options_json,
              forbidden_options_json, proof_refs_json, status,
              business_action_performed, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    row["approval_request_id"],
                    row["gate_ref"],
                    row["requested_action"],
                    row["target_world_ref"],
                    row["target_thread_ref"],
                    row["requested_by_agent"],
                    row["owner_speaker_ref"],
                    row["plain_summary"],
                    row["risk_summary"],
                    json.dumps(row["safe_options"], sort_keys=True),
                    json.dumps(row["forbidden_options"], sort_keys=True),
                    json.dumps(row["proof_refs"], sort_keys=True),
                    row["status"],
                    1 if row["business_action_performed"] else 0,
                    row["created_at"],
                )
                for row in requests
            ],
        )
        conn.commit()
    finally:
        conn.close()


def build_read_model(
    *,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
    sqlite_path: Path = DEFAULT_SQLITE_PATH,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    preconditions = _preconditions(read_model_root)
    preconditions_ready = all(row["ready"] for row in preconditions)
    requests = _approval_requests(generated_at)
    _write_sqlite(sqlite_path, requests)
    return {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "status": STATUS_READY if preconditions_ready else STATUS_NOT_READY,
        "generated_at": generated_at,
        "approval_request_count": len(requests),
        "approval_requests": requests,
        "preconditions": preconditions,
        "sqlite_path": str(_rooted(sqlite_path)),
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "rules": [
            "The queue does not execute approvals.",
            "Business actions require a separate executor and gate.",
            "Send, Coupa, workbook, PDF, ledger, and paid actions remain pending until explicit operator action.",
            "This queue records pending decisions only.",
        ],
        "machine_proof": {
            "preconditions_ready": preconditions_ready,
            "business_action_performed": False,
            "email_sent": False,
            "gmail_opened": False,
            "browser_or_coupa_opened": False,
            "ledger_mutated": False,
            "workbook_mutated": False,
            "pdf_exported": False,
            "paid_marked": False,
            "submitted": False,
            "pushed": False,
        },
    }


def _wiki(read_model: Mapping[str, Any]) -> str:
    lines = [
        "# Approval Request Queue",
        "",
        "Status: " + str(read_model["status"]),
        "",
        "This queue centralizes approval requests and does not execute approvals.",
        "",
        "## Pending Requests",
    ]
    for request in read_model["approval_requests"]:
        lines.append(
            f"- {request['requested_action']} ({request['owner_speaker_ref']}): {request['plain_summary']}"
        )
    lines.extend(
        [
            "",
            "Business actions require a separate executor/gate. Protected send, Coupa, ledger, workbook, PDF, submit, and paid actions remain blocked here.",
            "",
        ]
    )
    return "\n".join(lines)


def export_approval_request_queue(
    *,
    read_model_root: Path = DEFAULT_READ_MODEL_ROOT,
    export_root: Path = DEFAULT_EXPORT_ROOT,
    bridge_export_root: Path = DEFAULT_BRIDGE_EXPORT_ROOT,
    sqlite_path: Path = DEFAULT_SQLITE_PATH,
    wiki_path: Path = DEFAULT_WIKI_PATH,
    generated_at: str | None = None,
) -> dict[str, str]:
    read_model = build_read_model(
        read_model_root=read_model_root,
        sqlite_path=sqlite_path,
        generated_at=generated_at,
    )
    export_path = _rooted(export_root) / JSON_EXPORT_NAME
    bridge_path = _rooted(bridge_export_root) / JSON_EXPORT_NAME
    wiki_path = _rooted(wiki_path)
    _write_json(export_path, read_model)
    _write_json(bridge_path, read_model)
    wiki_path.parent.mkdir(parents=True, exist_ok=True)
    wiki_path.write_text(_wiki(read_model), encoding="utf-8")
    return {
        "status": str(read_model["status"]),
        "read_model_path": str(export_path),
        "bridge_read_model_path": str(bridge_path),
        "sqlite_path": str(_rooted(sqlite_path)),
        "wiki_path": str(wiki_path),
        "approval_request_count": str(read_model["approval_request_count"]),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Publish Approval Request Queue V0.")
    parser.add_argument("--read-model-root", type=Path, default=DEFAULT_READ_MODEL_ROOT)
    parser.add_argument("--export-root", type=Path, default=DEFAULT_EXPORT_ROOT)
    parser.add_argument("--bridge-export-root", type=Path, default=DEFAULT_BRIDGE_EXPORT_ROOT)
    parser.add_argument("--sqlite-path", type=Path, default=DEFAULT_SQLITE_PATH)
    parser.add_argument("--wiki-path", type=Path, default=DEFAULT_WIKI_PATH)
    args = parser.parse_args()
    result = export_approval_request_queue(
        read_model_root=args.read_model_root,
        export_root=args.export_root,
        bridge_export_root=args.bridge_export_root,
        sqlite_path=args.sqlite_path,
        wiki_path=args.wiki_path,
    )
    print(stable_json(result), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
