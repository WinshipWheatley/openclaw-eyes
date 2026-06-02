"""Cassandra Telegram dry-run inbox V0.

This adapter converts simulated Telegram messages into Workflow Package Queue
entries. It never connects to Telegram, reads credentials, sends replies,
touches Excel, exports PDFs, opens Gmail/browser/Coupa, mutates ledgers, marks
paid/sent, or submits anything.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import workflow_package_queue
import workflow_package_request_consumer


ROOT = Path(__file__).resolve().parent
DEFAULT_INBOX_DIR = Path("/mnt/e/openclaw/cassandra_telegram_dryrun_inbox")
DEFAULT_RESPONSE_DIR = DEFAULT_INBOX_DIR / "responses"
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_BRIDGE_EXPORT_ROOT = Path("/mnt/e/openclaw/generated/read_models")
DEFAULT_WIKI_PATH = Path("generated/wiki/openclaw/Cassandra Telegram Dry Run Inbox.md")
DEFAULT_SQLITE_PATH = workflow_package_queue.DEFAULT_SQLITE_PATH

SCHEMA_VERSION = "cassandra_telegram_dryrun_inbox_v0"
READ_MODEL_ID = "cassandra_telegram_dryrun_status"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
CONTRACT_STATUS = "CASSANDRA_TELEGRAM_DRYRUN_INBOX_READY"

SOURCE_SURFACE = "telegram_dryrun"

AUTHORITY_FALSE_FIELDS = (
    "email_send_allowed",
    "ledger_posting_allowed",
    "browser_access_allowed",
    "gmail_allowed",
    "coupa_allowed",
    "portal_submit_allowed",
    "workbook_source_mutation_allowed",
    "workbook_mutation_allowed",
    "pdf_export_allowed",
    "sent",
    "paid",
    "telegram_send_allowed",
    "telegram_live_connection_allowed",
    "telegram_credentials_access_allowed",
)

TOP_LEVEL_FALSE_FIELDS = (
    "email_send_performed",
    "ledger_mutation_performed",
    "browser_access_performed",
    "gmail_access_performed",
    "coupa_access_performed",
    "workbook_mutation_performed",
    "pdf_export_performed",
    "paid_marking_performed",
    "submit_performed",
    "telegram_message_sent",
    "telegram_live_connected",
    "telegram_credentials_accessed",
)

AUTHORITY_BOUNDARY = {
    "telegram_live_connection_allowed": False,
    "telegram_credentials_access_allowed": False,
    "telegram_send_allowed": False,
    "email_send_allowed": False,
    "ledger_posting_allowed": False,
    "browser_access_allowed": False,
    "gmail_allowed": False,
    "coupa_allowed": False,
    "portal_submit_allowed": False,
    "workbook_source_mutation_allowed": False,
    "workbook_mutation_allowed": False,
    "pdf_export_allowed": False,
    "sent": False,
    "paid": False,
}

SUPPORTED_EXAMPLES = (
    {
        "message_id": "telegram_dryrun_fixture_st_annes_work_log",
        "message_text": "Mark that I'm at church running sound.",
        "expected_workflow_ref": "st_annes_work_log_event",
        "expected_package_status": "OPERATOR_REVIEW_REQUIRED",
    },
    {
        "message_id": "telegram_dryrun_fixture_capital_hilton_proposal",
        "message_text": "Follow up on Capital Hilton proposal.",
        "expected_workflow_ref": "capital_hilton_proposal_followup",
        "expected_package_status": "OPERATOR_REVIEW_REQUIRED",
    },
    {
        "message_id": "telegram_dryrun_fixture_st_annes_invoice_send",
        "message_text": "Send St. Anne's invoice.",
        "expected_workflow_ref": "st_annes_monthly_invoice_rollup",
        "expected_package_status": "PERMISSION_REQUIRED",
    },
)


@dataclass(frozen=True)
class DryRunProcessResult:
    status: str
    read_model_path: str
    bridge_read_model_path: str
    wiki_path: str
    inbox_path: str
    response_dir_path: str
    sqlite_path: str
    message_count: int
    package_count: int
    response_receipt_paths: tuple[str, ...]
    response_statuses: tuple[dict[str, str], ...]


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _rooted(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def _sha256_text(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def _safe_filename_part(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value or "").strip())
    return cleaned.strip("._")[:120] or "message"


def _message_id(message: Mapping[str, Any], source_path: Path) -> str:
    return str(message.get("message_id") or source_path.stem)


def _message_text(message: Mapping[str, Any]) -> str:
    return str(message.get("message_text") or "").strip()


def _authority_blockers(message: Mapping[str, Any]) -> tuple[str, ...]:
    blockers: list[str] = []
    authority = message.get("authority_boundary")
    if not isinstance(authority, Mapping):
        blockers.append("authority_boundary_missing_or_invalid")
    else:
        for key, value in authority.items():
            if value is True:
                blockers.append(f"authority_true:{key}")
        for key in AUTHORITY_FALSE_FIELDS:
            if authority.get(key) is True:
                blockers.append(f"unsafe_authority_true:{key}")
    for key in TOP_LEVEL_FALSE_FIELDS:
        if message.get(key) is True:
            blockers.append(f"unsafe_action_true:{key}")
    return tuple(dict.fromkeys(blockers))


def validate_dryrun_message(message: Mapping[str, Any]) -> tuple[bool, tuple[str, ...]]:
    blockers: list[str] = []
    if str(message.get("source_surface") or "").strip() != SOURCE_SURFACE:
        blockers.append("source_surface_not_telegram_dryrun")
    if not str(message.get("sender_ref") or "").startswith("protected:"):
        blockers.append("sender_ref_not_protected")
    if not str(message.get("chat_ref") or "").startswith("protected:"):
        blockers.append("chat_ref_not_protected")
    if not str(message.get("received_at") or "").strip():
        blockers.append("received_at_missing")
    if not _message_text(message):
        blockers.append("message_text_missing")
    blockers.extend(_authority_blockers(message))
    return not blockers, tuple(dict.fromkeys(blockers))


def list_dryrun_message_files(inbox_dir: Path) -> list[Path]:
    inbox_dir.mkdir(parents=True, exist_ok=True)
    files: list[Path] = []
    for path in sorted(inbox_dir.glob("*.json")):
        if path.is_file() and not path.name.startswith("cassandra_telegram_dryrun_response_"):
            files.append(path)
    return files


def load_json_file(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} did not contain a JSON object")
    return payload


def build_dryrun_message(
    *,
    message_id: str,
    message_text: str,
    received_at: str,
    sender_ref: str = "protected:test_operator",
    chat_ref: str = "protected:test_chat",
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "message_id": message_id,
        "source_surface": SOURCE_SURFACE,
        "sender_ref": sender_ref,
        "chat_ref": chat_ref,
        "received_at": received_at,
        "message_text": message_text,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
    }


def write_fixture_messages(inbox_dir: Path, *, received_at: str | None = None) -> tuple[str, ...]:
    received_at = received_at or utc_now()
    inbox_dir.mkdir(parents=True, exist_ok=True)
    paths: list[str] = []
    for example in SUPPORTED_EXAMPLES:
        message = build_dryrun_message(
            message_id=str(example["message_id"]),
            message_text=str(example["message_text"]),
            received_at=received_at,
        )
        path = inbox_dir / f"{_safe_filename_part(message['message_id'])}.json"
        path.write_text(stable_json(message), encoding="utf-8")
        paths.append(path.as_posix())
    return tuple(paths)


def _response_text(package: Mapping[str, Any] | None, blocker: str) -> str:
    if package is None:
        reason = blocker or "the dry-run envelope did not pass local safety checks"
        return f"Blocked: {reason}. No reply was sent."
    workflow_ref = str(package.get("workflow_ref") or "")
    status = str(package.get("status") or "")
    if workflow_ref == "st_annes_work_log_event":
        return "St. Anne's work log captured. Confirm or discard."
    if workflow_ref == "capital_hilton_proposal_followup":
        return "Capital Hilton proposal follow-up staged. Review the follow-up."
    if workflow_ref == "st_annes_monthly_invoice_rollup":
        if status in {"PERMISSION_REQUIRED", "ARTIFACT_REQUIRED"}:
            return "Blocked: St. Anne's invoice send still needs the required gate. No email was sent."
        return "St. Anne's invoice rollup package staged for review. No email was sent."
    if workflow_ref == "capital_hilton_invoice_operator_assist":
        return "Blocked: Capital Hilton invoice submission needs operator assist. No Coupa action ran."
    return "Workflow package staged for review. No live action ran."


def _blocker(package: Mapping[str, Any] | None, blockers: tuple[str, ...]) -> str:
    if blockers:
        return "; ".join(blockers)
    if package is None:
        return "package_not_created"
    if str(package.get("status") or "") in {"PERMISSION_REQUIRED", "ARTIFACT_REQUIRED", "PROVIDER_GATE_REQUIRED"}:
        capability = package.get("capability_gate_result")
        if isinstance(capability, Mapping):
            return str(capability.get("reason") or capability.get("status") or package.get("status") or "")
    return ""


def _receipt_path(response_dir: Path, message_id: str) -> Path:
    return response_dir / f"cassandra_telegram_dryrun_response_{_safe_filename_part(message_id)}.json"


def process_dryrun_message(
    message: Mapping[str, Any],
    *,
    source_message_filename: str,
    generated_at: str | None = None,
    sqlite_path: Path = DEFAULT_SQLITE_PATH,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    source_path = Path(source_message_filename)
    message_id = _message_id(message, source_path)
    ok, blockers = validate_dryrun_message(message)
    package: dict[str, Any] | None = None
    if ok:
        package = workflow_package_queue.create_package(
            _message_text(message),
            source_surface=SOURCE_SURFACE,
            created_at=str(message.get("received_at") or generated_at),
        )
        package["source_message_metadata"] = {
            "message_id": message_id,
            "source_message_filename": source_message_filename,
            "sender_ref": str(message.get("sender_ref") or ""),
            "chat_ref": str(message.get("chat_ref") or ""),
            "received_at": str(message.get("received_at") or ""),
            "message_text_ref": "protected_text_hash:" + _sha256_text(_message_text(message)),
            "protected_text_hash": _sha256_text(_message_text(message)),
        }
        workflow_package_queue.record_package(sqlite_path, package)

    blocker = _blocker(package, blockers)
    route_world, route_thread = workflow_package_request_consumer.target_lane_for_workflow(
        str(package.get("workflow_ref") if package else "")
    )
    operator_display = dict(package.get("operator_display") or {}) if package else {
        "speaker_ref": "guardian",
        "voice_profile_ref": "agent_voice_profile:guardian",
        "voice_mode": "safety_gate",
        "audience": "internal_operator",
        "headline": "Dry-run message blocked",
        "status_label": "Blocked",
        "tone": "blocked",
        "plain_summary": "The dry-run message did not pass local safety checks.",
        "next_safe_action": "Fix the dry-run envelope.",
        "proof_caption": "Proof available.",
        "show_machine_details_by_default": False,
    }
    receipt = {
        "schema_version": SCHEMA_VERSION,
        "receipt_type": "CASSANDRA_TELEGRAM_DRYRUN_RESULT_RECEIPT",
        "message_id": message_id,
        "source_message_filename": source_message_filename,
        "source_surface": SOURCE_SURFACE,
        "sender_ref": str(message.get("sender_ref") or ""),
        "chat_ref": str(message.get("chat_ref") or ""),
        "received_at": str(message.get("received_at") or ""),
        "message_text_ref": "protected_text_hash:" + _sha256_text(_message_text(message)) if _message_text(message) else "",
        "protected_text_hash": _sha256_text(_message_text(message)) if _message_text(message) else "",
        "raw_internal_status": "RESPONSE_READY" if package is not None else "BLOCKED_WITH_REASON",
        "primary_status": str(package.get("status") if package else "BLOCKED_BY_DRYRUN_VALIDATION"),
        "workflow_package_id": str(package.get("package_id") if package else ""),
        "workflow_ref": str(package.get("workflow_ref") if package else ""),
        "client_ref": package.get("client_ref") if package else None,
        "world": str(package.get("world") if package else ""),
        "target_world_ref": route_world if package else "",
        "target_thread_ref": route_thread if package else "",
        "package_status": str(package.get("status") if package else "NOT_CREATED"),
        "capability_gate_status": str((package.get("capability_gate_result") or {}).get("status") if package else "NOT_EVALUATED"),
        "blocker": blocker,
        "response_text": _response_text(package, blocker),
        "operator_display": operator_display,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "no_send_business_action": True,
        "no_excel_by_default": True,
        "no_ledger": True,
        "no_reply_sent": True,
        "sqlite_path": str(sqlite_path),
        "created_at": generated_at,
        "machine_proof": {
            "telegram_dryrun_only": True,
            "telegram_live_connected": False,
            "telegram_credentials_accessed": False,
            "telegram_message_sent": False,
            "package_recorded": package is not None,
            "queue_noop_worker_only": True,
            "business_action_gate_closed": bool(
                package and (package.get("business_action_gate_result") or {}).get("status") == "CLOSED"
            ),
            "authority_flags_all_false": all(value is False for value in AUTHORITY_BOUNDARY.values()),
            "email_send_performed": False,
            "ledger_mutation_performed": False,
            "browser_access_performed": False,
            "gmail_access_performed": False,
            "coupa_access_performed": False,
            "workbook_mutation_performed": False,
            "pdf_export_performed": False,
            "paid_marking_performed": False,
            "submit_performed": False,
            "unsafe_true_grants_absent": not blockers,
        },
    }
    return receipt


def build_status_read_model(
    *,
    receipts: list[Mapping[str, Any]],
    response_receipt_paths: list[str],
    inbox_dir: Path,
    response_dir: Path,
    sqlite_path: Path,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    package_receipts = [receipt for receipt in receipts if receipt.get("workflow_package_id")]
    blocked_receipts = [receipt for receipt in receipts if not receipt.get("workflow_package_id")]
    return {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "generated_at": generated_at,
        "status": CONTRACT_STATUS,
        "source_surface": SOURCE_SURFACE,
        "purpose": "Non-live Telegram/Cassandra dry-run inbox that converts simulated Telegram messages into Workflow Package Queue requests.",
        "inbox_path": inbox_dir.as_posix(),
        "response_receipt_dir": response_dir.as_posix(),
        "sqlite_path": sqlite_path.as_posix(),
        "workflow_package_queue_ref": "generated/read_models/workflow_package_queue_contract.json",
        "cassandra_telegram_intake_contract_ref": "generated/read_models/cassandra_telegram_intake_contract.json",
        "message_count": len(receipts),
        "package_queue_entries_recorded": len(package_receipts),
        "blocked_message_count": len(blocked_receipts),
        "response_receipt_paths": response_receipt_paths,
        "response_statuses": [
            {
                "message_id": str(receipt.get("message_id") or ""),
                "workflow_ref": str(receipt.get("workflow_ref") or ""),
                "client_ref": str(receipt.get("client_ref") or ""),
                "package_status": str(receipt.get("package_status") or ""),
                "capability_gate_status": str(receipt.get("capability_gate_status") or ""),
                "blocker": str(receipt.get("blocker") or ""),
                "response_text": str(receipt.get("response_text") or ""),
                "target_world_ref": str(receipt.get("target_world_ref") or ""),
                "target_thread_ref": str(receipt.get("target_thread_ref") or ""),
            }
            for receipt in receipts
        ],
        "supported_examples": [
            {
                "message_id": str(example["message_id"]),
                "expected_workflow_ref": str(example["expected_workflow_ref"]),
                "expected_package_status": str(example["expected_package_status"]),
            }
            for example in SUPPORTED_EXAMPLES
        ],
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "rules": [
            "No live Telegram connection.",
            "No Telegram reply is sent.",
            "No Excel or workbook mutation.",
            "No email, browser, Gmail, Coupa, portal submit, ledger mutation, paid marking, or PDF export.",
            "Missing permissions are recorded as blockers in response receipts.",
        ],
        "machine_proof": {
            "telegram_dryrun_only": True,
            "telegram_live_connected": False,
            "telegram_credentials_accessed": False,
            "telegram_message_sent": False,
            "response_receipts_written": len(response_receipt_paths),
            "package_queue_entries_recorded": len(package_receipts),
            "authority_flags_all_false": all(value is False for value in AUTHORITY_BOUNDARY.values()),
            "email_send_performed": False,
            "ledger_mutation_performed": False,
            "browser_access_performed": False,
            "gmail_access_performed": False,
            "coupa_access_performed": False,
            "workbook_mutation_performed": False,
            "pdf_export_performed": False,
            "paid_marking_performed": False,
            "submit_performed": False,
            "unsafe_true_grants_absent": True,
        },
    }


def build_wiki(read_model: Mapping[str, Any]) -> str:
    lines = [
        "# Cassandra Telegram Dry Run Inbox",
        "",
        f"Status: `{CONTRACT_STATUS}`",
        "",
        "This is a non-live inbox for simulated Telegram/Cassandra messages. It turns local JSON dry-run messages into Workflow Package Queue entries and response receipts.",
        "",
        "It does not connect Telegram, read Telegram credentials, send replies, send email, open Gmail/browser/Coupa, touch Excel, export PDFs, mutate ledgers, mark paid, or submit anything.",
        "",
        "## Paths",
        "",
        f"- Inbox: `{read_model['inbox_path']}`",
        f"- Response receipts: `{read_model['response_receipt_dir']}`",
        f"- Package queue SQLite: `{read_model['sqlite_path']}`",
        "",
        "## Supported Examples",
        "",
    ]
    for item in read_model["supported_examples"]:
        lines.append(
            f"- `{item['message_id']}` -> `{item['expected_workflow_ref']}` / `{item['expected_package_status']}`"
        )
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            "- Telegram live connection: no",
            "- Telegram reply send: no",
            "- Email/browser/Gmail/Coupa/portal: no",
            "- Excel/workbook/PDF: no",
            "- Ledger/paid/sent mutation: no",
            "",
            "## Last Processed Statuses",
            "",
        ]
    )
    if read_model["response_statuses"]:
        for item in read_model["response_statuses"]:
            lines.append(
                f"- `{item['message_id']}`: `{item['workflow_ref'] or 'blocked'}` / `{item['package_status']}`"
            )
    else:
        lines.append("- No dry-run messages were present when this status was generated.")
    return "\n".join(lines) + "\n"


def export_status_read_model(
    read_model: Mapping[str, Any],
    *,
    export_root: Path = DEFAULT_EXPORT_ROOT,
    bridge_export_root: Path | None = DEFAULT_BRIDGE_EXPORT_ROOT,
    wiki_path: Path = DEFAULT_WIKI_PATH,
) -> tuple[str, str, str]:
    export_root = _rooted(export_root)
    export_root.mkdir(parents=True, exist_ok=True)
    local_path = export_root / JSON_EXPORT_NAME
    local_path.write_text(stable_json(read_model), encoding="utf-8")

    bridge_path = ""
    if bridge_export_root is not None:
        bridge_export_root.mkdir(parents=True, exist_ok=True)
        bridge_file = bridge_export_root / JSON_EXPORT_NAME
        bridge_file.write_text(stable_json(read_model), encoding="utf-8")
        bridge_path = bridge_file.as_posix()

    wiki_path = _rooted(wiki_path)
    wiki_path.parent.mkdir(parents=True, exist_ok=True)
    wiki_path.write_text(build_wiki(read_model), encoding="utf-8")
    return local_path.as_posix(), bridge_path, wiki_path.as_posix()


def process_dryrun_inbox(
    *,
    inbox_dir: Path = DEFAULT_INBOX_DIR,
    response_dir: Path = DEFAULT_RESPONSE_DIR,
    export_root: Path = DEFAULT_EXPORT_ROOT,
    bridge_export_root: Path | None = DEFAULT_BRIDGE_EXPORT_ROOT,
    wiki_path: Path = DEFAULT_WIKI_PATH,
    sqlite_path: Path = DEFAULT_SQLITE_PATH,
    generated_at: str | None = None,
) -> DryRunProcessResult:
    generated_at = generated_at or utc_now()
    inbox_dir = _rooted(inbox_dir)
    response_dir = _rooted(response_dir)
    sqlite_path = _rooted(sqlite_path)
    response_dir.mkdir(parents=True, exist_ok=True)

    receipts: list[dict[str, Any]] = []
    response_paths: list[str] = []
    for message_path in list_dryrun_message_files(inbox_dir):
        message = load_json_file(message_path)
        receipt = process_dryrun_message(
            message,
            source_message_filename=message_path.name,
            generated_at=generated_at,
            sqlite_path=sqlite_path,
        )
        receipt_path = _receipt_path(response_dir, str(receipt["message_id"]))
        receipt["response_receipt_path"] = receipt_path.as_posix()
        receipt_path.write_text(stable_json(receipt), encoding="utf-8")
        receipts.append(receipt)
        response_paths.append(receipt_path.as_posix())

    read_model = build_status_read_model(
        receipts=receipts,
        response_receipt_paths=response_paths,
        inbox_dir=inbox_dir,
        response_dir=response_dir,
        sqlite_path=sqlite_path,
        generated_at=generated_at,
    )
    local_path, bridge_path, wiki_path_out = export_status_read_model(
        read_model,
        export_root=export_root,
        bridge_export_root=bridge_export_root,
        wiki_path=wiki_path,
    )
    response_statuses = tuple(
        {
            "message_id": str(item["message_id"]),
            "workflow_ref": str(item["workflow_ref"]),
            "package_status": str(item["package_status"]),
            "blocker": str(item["blocker"]),
        }
        for item in read_model["response_statuses"]
    )
    return DryRunProcessResult(
        status=CONTRACT_STATUS,
        read_model_path=local_path,
        bridge_read_model_path=bridge_path,
        wiki_path=wiki_path_out,
        inbox_path=inbox_dir.as_posix(),
        response_dir_path=response_dir.as_posix(),
        sqlite_path=sqlite_path.as_posix(),
        message_count=len(receipts),
        package_count=sum(1 for receipt in receipts if receipt.get("workflow_package_id")),
        response_receipt_paths=tuple(response_paths),
        response_statuses=response_statuses,
    )


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Process Cassandra Telegram dry-run inbox V0.")
    parser.add_argument("--inbox-dir", default=str(DEFAULT_INBOX_DIR))
    parser.add_argument("--response-dir", default=str(DEFAULT_RESPONSE_DIR))
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT))
    parser.add_argument("--bridge-export-root", default=str(DEFAULT_BRIDGE_EXPORT_ROOT))
    parser.add_argument("--wiki-path", default=str(DEFAULT_WIKI_PATH))
    parser.add_argument("--sqlite-path", default=str(DEFAULT_SQLITE_PATH))
    parser.add_argument("--generated-at")
    parser.add_argument("--no-bridge", action="store_true")
    parser.add_argument("--seed-fixtures", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    inbox_dir = Path(args.inbox_dir)
    generated_at = args.generated_at or utc_now()
    seeded_paths: tuple[str, ...] = ()
    if args.seed_fixtures:
        seeded_paths = write_fixture_messages(_rooted(inbox_dir), received_at=generated_at)
    result = process_dryrun_inbox(
        inbox_dir=inbox_dir,
        response_dir=Path(args.response_dir),
        export_root=Path(args.export_root),
        bridge_export_root=None if args.no_bridge else Path(args.bridge_export_root),
        wiki_path=Path(args.wiki_path),
        sqlite_path=Path(args.sqlite_path),
        generated_at=generated_at,
    )
    print(stable_json({**result.__dict__, "seeded_fixture_paths": list(seeded_paths)}), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
