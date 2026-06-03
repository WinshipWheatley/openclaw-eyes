"""Dead Letter Queue V0.

Publishes compact recovery records for failed, blocked, stale, or malformed
package requests. The queue makes failures visible without retrying or
performing business actions.
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
DEFAULT_WIKI_PATH = Path("generated/wiki/openclaw/Dead Letter Queue.md")
DEFAULT_SQLITE_PATH = Path("generated/system_knowledge/dead_letter_queue.sqlite")

SCHEMA_VERSION = "dead_letter_queue_v0"
READ_MODEL_ID = "dead_letter_queue"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
STATUS_READY = "DEAD_LETTER_QUEUE_READY"
STATUS_NOT_READY = "DEAD_LETTER_QUEUE_NOT_READY"

PRECONDITIONS = {
    "package_event_index": {
        "filename": "package_event_index.json",
        "accepted_statuses": ["PACKAGE_EVENT_INDEX_READY"],
    },
    "workflow_package_request_consumer": {
        "filename": "workflow_package_request_consumer_status.json",
        "accepted_statuses": [
            "WORKFLOW_PACKAGE_REQUEST_CONSUMER_READY",
            "PC_WORKFLOW_PACKAGE_REQUEST_CONSUMER_READY",
            "WORKFLOW_PACKAGE_RAIL_STATUS_READY",
        ],
    },
    "operator_conversation_journal": {
        "filename": "operator_conversation_journal.json",
        "accepted_statuses": ["OPERATOR_CONVERSATION_JOURNAL_READY"],
    },
}

AUTHORITY_BOUNDARY = {
    "email_send_allowed": False,
    "ledger_posting_allowed": False,
    "browser_access_allowed": False,
    "gmail_allowed": False,
    "coupa_allowed": False,
    "portal_submit_allowed": False,
    "business_action_allowed": False,
    "sent": False,
    "paid": False,
}

DEAD_LETTER_TEMPLATES = [
    {
        "failure_kind": "malformed_request",
        "owner_speaker_ref": "chief",
        "recoverability": "needs_operator",
        "plain_summary": "A package request could not be parsed into a valid request shape.",
        "next_safe_action": "Ask Mission Control to resend a valid package request.",
        "target_world_ref": "operations",
        "target_thread_ref": "mission_control",
    },
    {
        "failure_kind": "missing_required_field",
        "owner_speaker_ref": "chief",
        "recoverability": "retry",
        "plain_summary": "A request is missing a required workflow, package, or target field.",
        "next_safe_action": "Create a corrected request with the missing field included.",
        "target_world_ref": "operations",
        "target_thread_ref": "mission_control",
    },
    {
        "failure_kind": "unsafe_authority_requested",
        "owner_speaker_ref": "guardian",
        "recoverability": "needs_operator",
        "plain_summary": "A request asked for protected authority such as send, submit, ledger, provider, or paid truth.",
        "next_safe_action": "Keep it blocked and ask Guardian for an approval path.",
        "target_world_ref": "governance",
        "target_thread_ref": "guardian",
    },
    {
        "failure_kind": "unknown_workflow_ref",
        "owner_speaker_ref": "chief",
        "recoverability": "investigate",
        "plain_summary": "A request referenced a workflow OpenClaw does not currently route.",
        "next_safe_action": "Map the workflow or route it to system_question_answer for explanation.",
        "target_world_ref": "build",
        "target_thread_ref": "workflow_router",
    },
    {
        "failure_kind": "stale_response",
        "owner_speaker_ref": "openclaw",
        "recoverability": "investigate",
        "plain_summary": "A response appears older than the current package/read-model state.",
        "next_safe_action": "Regenerate a compact status response from current local read models.",
        "target_world_ref": "operations",
        "target_thread_ref": "mission_control",
    },
    {
        "failure_kind": "missing_bridge_file",
        "owner_speaker_ref": "openclaw",
        "recoverability": "retry",
        "plain_summary": "A local read model exists but the expected bridge copy is missing.",
        "next_safe_action": "Republish the specific read model to bridge after validation.",
        "target_world_ref": "operations",
        "target_thread_ref": "bridge",
    },
    {
        "failure_kind": "service_not_current",
        "owner_speaker_ref": "chief",
        "recoverability": "investigate",
        "plain_summary": "A service may be running older code than the committed local route.",
        "next_safe_action": "Validate first, then restart only if request-response code changed.",
        "target_world_ref": "build",
        "target_thread_ref": "request_response_service",
    },
    {
        "failure_kind": "permission_required",
        "owner_speaker_ref": "openclaw",
        "recoverability": "needs_operator",
        "plain_summary": "A local or bridge write requires operator-granted filesystem permission.",
        "next_safe_action": "Ask for the narrow filesystem permission needed for the target path.",
        "target_world_ref": "operations",
        "target_thread_ref": "permissions",
    },
    {
        "failure_kind": "provider_gate_required",
        "owner_speaker_ref": "guardian",
        "recoverability": "needs_operator",
        "plain_summary": "A provider action requires an explicit provider gate and operator approval.",
        "next_safe_action": "Leave provider work pending until the operator opens the protected lane.",
        "target_world_ref": "finance",
        "target_thread_ref": "provider_gate",
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


def _dead_letter_id(failure_kind: str) -> str:
    digest = hashlib.sha256(f"dead_letter:{failure_kind}".encode("utf-8")).hexdigest()[:16]
    return f"dead_letter:{digest}"


def _preconditions(read_model_root: Path) -> list[dict[str, Any]]:
    root = _rooted(read_model_root)
    rows: list[dict[str, Any]] = []
    for ref, contract in PRECONDITIONS.items():
        payload = _load_json(root / str(contract["filename"]))
        observed = str(payload.get("status") or payload.get("contract_status") or "")
        accepted = [str(status) for status in contract["accepted_statuses"]]
        rows.append(
            {
                "precondition_ref": ref,
                "observed_status": observed,
                "accepted_statuses": accepted,
                "ready": observed in accepted,
                "source_ref": f"generated/read_models/{contract['filename']}",
            }
        )
    return rows


def _dead_letters(generated_at: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for template in DEAD_LETTER_TEMPLATES:
        failure_kind = str(template["failure_kind"])
        rows.append(
            {
                "dead_letter_id": _dead_letter_id(failure_kind),
                "source_request_ref": f"dead_letter_seed:{failure_kind}",
                "package_id": "",
                "failure_kind": failure_kind,
                "plain_summary": str(template["plain_summary"]),
                "owner_speaker_ref": str(template["owner_speaker_ref"]),
                "recoverability": str(template["recoverability"]),
                "next_safe_action": str(template["next_safe_action"]),
                "target_world_ref": str(template["target_world_ref"]),
                "target_thread_ref": str(template["target_thread_ref"]),
                "proof_refs": [
                    "generated/read_models/package_event_index.json",
                    "generated/read_models/workflow_package_request_consumer_status.json",
                    "generated/read_models/operator_conversation_journal.json",
                ],
                "raw_body_stored": False,
                "created_at": generated_at,
            }
        )
    return rows


def _write_sqlite(sqlite_path: Path, dead_letters: list[Mapping[str, Any]]) -> None:
    sqlite_path = _rooted(sqlite_path)
    sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(sqlite_path)
    try:
        conn.execute("DROP TABLE IF EXISTS dead_letters")
        conn.execute(
            """
            CREATE TABLE dead_letters (
              dead_letter_id TEXT PRIMARY KEY,
              source_request_ref TEXT NOT NULL,
              package_id TEXT NOT NULL,
              failure_kind TEXT NOT NULL,
              plain_summary TEXT NOT NULL,
              owner_speaker_ref TEXT NOT NULL,
              recoverability TEXT NOT NULL,
              next_safe_action TEXT NOT NULL,
              target_world_ref TEXT NOT NULL,
              target_thread_ref TEXT NOT NULL,
              proof_refs_json TEXT NOT NULL,
              raw_body_stored INTEGER NOT NULL,
              created_at TEXT NOT NULL
            )
            """
        )
        conn.executemany(
            """
            INSERT INTO dead_letters (
              dead_letter_id, source_request_ref, package_id, failure_kind,
              plain_summary, owner_speaker_ref, recoverability,
              next_safe_action, target_world_ref, target_thread_ref,
              proof_refs_json, raw_body_stored, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    row["dead_letter_id"],
                    row["source_request_ref"],
                    row["package_id"],
                    row["failure_kind"],
                    row["plain_summary"],
                    row["owner_speaker_ref"],
                    row["recoverability"],
                    row["next_safe_action"],
                    row["target_world_ref"],
                    row["target_thread_ref"],
                    json.dumps(row["proof_refs"], sort_keys=True),
                    1 if row["raw_body_stored"] else 0,
                    row["created_at"],
                )
                for row in dead_letters
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
    dead_letters = _dead_letters(generated_at)
    _write_sqlite(sqlite_path, dead_letters)
    return {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "status": STATUS_READY if preconditions_ready else STATUS_NOT_READY,
        "generated_at": generated_at,
        "dead_letter_count": len(dead_letters),
        "dead_letters": dead_letters,
        "preconditions": preconditions,
        "sqlite_path": str(_rooted(sqlite_path)),
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "rules": [
            "No retries are executed.",
            "No business action is performed.",
            "Raw request bodies are not stored.",
            "Proof refs remain collapsed.",
        ],
        "machine_proof": {
            "preconditions_ready": preconditions_ready,
            "retry_executed": False,
            "raw_body_stored": False,
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
        "# Dead Letter Queue",
        "",
        "Status: " + str(read_model["status"]),
        "",
        "No retries are executed by this queue. It records compact recovery metadata for failed, blocked, stale, or malformed package requests.",
        "",
        "## Failure Kinds",
    ]
    for row in read_model["dead_letters"]:
        lines.append(
            f"- {row['failure_kind']} ({row['recoverability']}): {row['next_safe_action']}"
        )
    lines.extend(["", "Raw request bodies are not dumped; proof refs stay collapsed.", ""])
    return "\n".join(lines)


def export_dead_letter_queue(
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
        "dead_letter_count": str(read_model["dead_letter_count"]),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Publish Dead Letter Queue V0.")
    parser.add_argument("--read-model-root", type=Path, default=DEFAULT_READ_MODEL_ROOT)
    parser.add_argument("--export-root", type=Path, default=DEFAULT_EXPORT_ROOT)
    parser.add_argument("--bridge-export-root", type=Path, default=DEFAULT_BRIDGE_EXPORT_ROOT)
    parser.add_argument("--sqlite-path", type=Path, default=DEFAULT_SQLITE_PATH)
    parser.add_argument("--wiki-path", type=Path, default=DEFAULT_WIKI_PATH)
    args = parser.parse_args()
    result = export_dead_letter_queue(
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
