"""Capital Hilton Business Development proposal read model.

This module ingests a local proposal draft packet as review state only. It does
not send email, access Gmail/browser/Coupa, create invoices, mutate a ledger, or
mark a proposal accepted.
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


ROOT = Path(__file__).resolve().parent
DEFAULT_INPUT_DIR = Path("/mnt/e/openclaw/artifacts/proposals/capital_hilton/fight_weekend_2026")
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_BRIDGE_EXPORT_ROOT = Path("/mnt/e/openclaw/generated/read_models")

SCHEMA_VERSION = "capital_hilton_business_development_proposal_v1"
READ_MODEL_ID = "capital_hilton_business_development_proposal"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"

EXPECTED_MARKDOWN_NAME = "Capital_Hilton_Fight_Weekend_Entertainment_Proposal_DRAFT.md"
EXPECTED_PACKET_NAME = "capital_hilton_fight_weekend_proposal_packet.json"
EXPECTED_RECEIPT_NAME = "capital_hilton_fight_weekend_proposal_review_receipt.json"
OPTIONAL_PDF_NAME = "Capital_Hilton_Fight_Weekend_Entertainment_Proposal_DRAFT.pdf"
SEND_RECEIPT_PATTERN = "capital_hilton_proposal_email_sent_receipt_*.json"
SEND_RECEIPT_TIMESTAMP_RE = re.compile(r"_(\d{8}T\d{6}Z)\.json$")

SOURCE_READY_STATUSES = {
    "CAPITAL_HILTON_PROPOSAL_FILE_READY_FOR_REVIEW",
    "CAPITAL_HILTON_PROPOSAL_DRAFT_READY_FOR_REVIEW",
}

DRAFT_PROPOSAL_STATUS = "DRAFT_READY_FOR_OPERATOR_REVIEW"
SENT_PROPOSAL_STATUS = "SENT_FOR_CLIENT_REVIEW"
SEND_RECEIPT_STATUS = "CAPITAL_HILTON_PROPOSAL_EMAIL_SENT"

SAFETY_FLAGS = {
    "finance_handoff_allowed": False,
    "email_send_allowed": False,
    "ledger_posting_allowed": False,
    "browser_access_allowed": False,
    "gmail_allowed": False,
    "coupa_allowed": False,
    "portal_submit_allowed": False,
    "finance_invoice_allowed": False,
    "sent": False,
    "paid": False,
    "proposal_accepted": False,
}


@dataclass(frozen=True)
class ExportResult:
    schema_version: str
    read_model_path: str
    bridge_read_model_path: str
    proposal_draft_path: str
    proposal_status: str
    source_packet_path: str
    source_receipt_path: str
    proposal_send_receipt_path: str


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _rooted(path: Path) -> Path:
    if path.is_absolute():
        return path
    return ROOT / path


def _bridge_path_from_mac_path(value: str) -> str:
    if value.startswith("/Volumes/openclaw_e/"):
        return "/mnt/e/openclaw/" + value.removeprefix("/Volumes/openclaw_e/")
    return value


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected object JSON at {path}")
    return payload


def _false_or_missing(payload: Mapping[str, Any], keys: tuple[str, ...]) -> bool:
    return all(payload.get(key) is not True for key in keys)


def _all_false(mapping: Mapping[str, Any]) -> bool:
    return all(value is False for value in mapping.values())


def _send_receipt_timestamp(path: Path) -> str:
    match = SEND_RECEIPT_TIMESTAMP_RE.search(path.name)
    if not match:
        raise ValueError(f"Could not extract send receipt timestamp from {path.name}")
    return match.group(1)


def find_latest_send_receipt(input_dir: Path) -> Path | None:
    receipts = sorted(Path(input_dir).glob(SEND_RECEIPT_PATTERN), key=_send_receipt_timestamp)
    if not receipts:
        return None
    return receipts[-1]


def _validate_send_receipt(
    *,
    send_receipt_path: Path | None,
    pdf_path: Path,
) -> dict[str, Any]:
    if send_receipt_path is None:
        return {
            "send_receipt_present": False,
            "send_receipt_path": "",
            "send_receipt_sha256": "",
            "send_receipt_status": "",
            "proposal_sent_recorded": False,
            "email_send_recorded": False,
            "sent_by_openclaw": False,
            "operator_assisted_send": False,
            "recipient": "",
            "recipient_display_name": "",
            "subject": "",
            "sent_gmail_message_id": "",
            "sent_gmail_thread_id": "",
            "attachment_path": "",
            "attachment_sha256": "",
            "attachment_exists": False,
        }

    send_receipt = _read_json(send_receipt_path)
    failures: list[str] = []
    if send_receipt.get("status") != SEND_RECEIPT_STATUS:
        failures.append(f"send receipt status expected {SEND_RECEIPT_STATUS} got {send_receipt.get('status')!r}")
    if send_receipt.get("client_ref") != "capital_hilton":
        failures.append(f"send receipt client_ref expected capital_hilton got {send_receipt.get('client_ref')!r}")
    if send_receipt.get("proposal_sent") is not True:
        failures.append("send receipt proposal_sent expected true")
    if send_receipt.get("email_send_performed") is not True:
        failures.append("send receipt email_send_performed expected true")
    expected_false = (
        "finance_handoff_allowed",
        "ledger_posting_allowed",
        "ledger_mutation_performed",
        "invoice_created",
        "coupa_used",
        "paid",
        "proposal_accepted",
        "sent_by_openclaw",
    )
    for key in expected_false:
        if send_receipt.get(key) is not False:
            failures.append(f"send receipt {key} expected false got {send_receipt.get(key)!r}")

    attachment_path_value = _bridge_path_from_mac_path(str(send_receipt.get("attachment_path") or ""))
    attachment_path = Path(attachment_path_value) if attachment_path_value else pdf_path
    if attachment_path != pdf_path and not attachment_path.exists():
        failures.append(f"send receipt attachment path does not exist: {attachment_path}")
    if not pdf_path.exists():
        failures.append(f"proposal PDF missing: {pdf_path}")

    attachment_sha = ""
    if pdf_path.exists():
        attachment_sha = sha256_file(pdf_path)
        receipt_sha = str(send_receipt.get("attachment_sha256") or "")
        if receipt_sha and receipt_sha != attachment_sha:
            failures.append("send receipt attachment sha256 does not match proposal PDF")

    if failures:
        raise ValueError("; ".join(failures))

    return {
        "send_receipt_present": True,
        "send_receipt_path": str(send_receipt_path),
        "send_receipt_sha256": sha256_file(send_receipt_path),
        "send_receipt_status": str(send_receipt.get("status") or ""),
        "proposal_sent_recorded": True,
        "email_send_recorded": True,
        "sent_by_openclaw": False,
        "operator_assisted_send": bool(send_receipt.get("operator_assisted")),
        "recipient": str(send_receipt.get("recipient") or ""),
        "recipient_display_name": str(send_receipt.get("recipient_display_name") or ""),
        "subject": str(send_receipt.get("subject") or ""),
        "sent_gmail_message_id": str(send_receipt.get("sent_gmail_message_id") or ""),
        "sent_gmail_thread_id": str(send_receipt.get("sent_gmail_thread_id") or ""),
        "attachment_path": str(pdf_path),
        "attachment_sha256": attachment_sha,
        "attachment_exists": pdf_path.exists(),
    }


def _validate_source_package(
    *,
    input_dir: Path,
    markdown_path: Path,
    packet_path: Path,
    receipt_path: Path,
    pdf_path: Path,
    packet: Mapping[str, Any],
    receipt: Mapping[str, Any],
) -> dict[str, Any]:
    failures: list[str] = []
    for path in (markdown_path, packet_path, receipt_path):
        if not path.exists():
            failures.append(f"Missing required file: {path}")

    if packet.get("client_ref") != "capital_hilton":
        failures.append(f"packet client_ref expected capital_hilton got {packet.get('client_ref')!r}")
    if receipt.get("client_ref") != "capital_hilton":
        failures.append(f"receipt client_ref expected capital_hilton got {receipt.get('client_ref')!r}")
    if str(packet.get("world") or "").lower().replace(" ", "_") != "business_development":
        failures.append(f"packet world expected Business Development got {packet.get('world')!r}")

    packet_status = str(packet.get("status") or "")
    receipt_status = str(receipt.get("status") or "")
    if packet_status not in SOURCE_READY_STATUSES:
        failures.append(f"packet status not ready for review: {packet_status!r}")
    if receipt_status not in SOURCE_READY_STATUSES:
        failures.append(f"receipt status not ready for review: {receipt_status!r}")

    markdown_sha = sha256_file(markdown_path) if markdown_path.exists() else ""
    packet_markdown_sha = str(packet.get("markdown_sha256") or "")
    receipt_markdown_sha = str(receipt.get("markdown_sha256") or "")
    if packet_markdown_sha and markdown_sha != packet_markdown_sha:
        failures.append("markdown sha256 does not match packet")
    if receipt_markdown_sha and markdown_sha != receipt_markdown_sha:
        failures.append("markdown sha256 does not match receipt")

    packet_sha = sha256_file(packet_path) if packet_path.exists() else ""
    if receipt.get("packet_sha256") and packet_sha != str(receipt.get("packet_sha256")):
        failures.append("packet sha256 does not match receipt")

    pdf_present = pdf_path.exists()
    pdf_sha = sha256_file(pdf_path) if pdf_present else ""
    if pdf_present:
        if packet.get("pdf_sha256") and pdf_sha != str(packet.get("pdf_sha256")):
            failures.append("PDF sha256 does not match packet")
        if receipt.get("pdf_sha256") and pdf_sha != str(receipt.get("pdf_sha256")):
            failures.append("PDF sha256 does not match receipt")

    authority_keys = tuple(SAFETY_FLAGS)
    if not _false_or_missing(packet, authority_keys):
        failures.append("packet contains unsafe top-level true authority")
    if not _false_or_missing(receipt, authority_keys):
        failures.append("receipt contains unsafe top-level true authority")

    packet_boundary = packet.get("business_authority_boundary")
    if isinstance(packet_boundary, Mapping) and not _all_false(packet_boundary):
        failures.append("packet business_authority_boundary is not all false")
    receipt_boundary = receipt.get("safety_boundary")
    if isinstance(receipt_boundary, Mapping) and not _all_false(receipt_boundary):
        failures.append("receipt safety_boundary is not all false")
    actions = receipt.get("actions_performed")
    if isinstance(actions, Mapping) and any(value is True for value in actions.values()):
        failures.append("receipt actions_performed contains true value")

    if failures:
        raise ValueError("; ".join(failures))

    return {
        "input_dir": str(input_dir),
        "markdown_path": str(markdown_path),
        "markdown_sha256": markdown_sha,
        "packet_path": str(packet_path),
        "packet_sha256": packet_sha,
        "receipt_path": str(receipt_path),
        "receipt_sha256_actual": sha256_file(receipt_path),
        "pdf_path": str(pdf_path) if pdf_present else "",
        "pdf_present": pdf_present,
        "pdf_sha256": pdf_sha,
        "packet_status": packet_status,
        "receipt_status": receipt_status,
        "source_files_validated": True,
        "safety_boundaries_false": True,
    }


def build_read_model(
    *,
    input_dir: Path = DEFAULT_INPUT_DIR,
    generated_at: str | None = None,
) -> dict[str, Any]:
    input_dir = Path(input_dir)
    markdown_path = input_dir / EXPECTED_MARKDOWN_NAME
    packet_path = input_dir / EXPECTED_PACKET_NAME
    receipt_path = input_dir / EXPECTED_RECEIPT_NAME
    pdf_path = input_dir / OPTIONAL_PDF_NAME
    send_receipt_path = find_latest_send_receipt(input_dir)
    packet = _read_json(packet_path)
    receipt = _read_json(receipt_path)
    validation = _validate_source_package(
        input_dir=input_dir,
        markdown_path=markdown_path,
        packet_path=packet_path,
        receipt_path=receipt_path,
        pdf_path=pdf_path,
        packet=packet,
        receipt=receipt,
    )
    send_state = _validate_send_receipt(send_receipt_path=send_receipt_path, pdf_path=pdf_path)
    pricing = packet.get("pricing") if isinstance(packet.get("pricing"), Mapping) else {}
    generated_at = generated_at or utc_now()
    proposal_status = SENT_PROPOSAL_STATUS if send_state["proposal_sent_recorded"] else DRAFT_PROPOSAL_STATUS

    payload = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "generated_at": generated_at,
        "world": "business_development",
        "world_display": "Business Development",
        "client_ref": "capital_hilton",
        "client_display_name": "Capital Hilton",
        "proposal_ref": str(packet.get("proposal_ref") or "capital_hilton_fight_weekend_2026"),
        "proposal_status": proposal_status,
        "source_packet_status": validation["packet_status"],
        "source_receipt_status": validation["receipt_status"],
        "source_send_receipt_status": send_state["send_receipt_status"],
        "review_required": not send_state["proposal_sent_recorded"],
        "ready_for_operator_review": not send_state["proposal_sent_recorded"],
        "client_review_pending": bool(send_state["proposal_sent_recorded"]),
        "proposal_sent_recorded": bool(send_state["proposal_sent_recorded"]),
        "email_send_recorded": bool(send_state["email_send_recorded"]),
        "operator_assisted_send": bool(send_state["operator_assisted_send"]),
        "sent_by_openclaw": False,
        "proposal_accepted": False,
        "finance_handoff_allowed": False,
        "email_send_allowed": False,
        "ledger_posting_allowed": False,
        "browser_access_allowed": False,
        "gmail_allowed": False,
        "coupa_allowed": False,
        "portal_submit_allowed": False,
        "finance_invoice_allowed": False,
        "sent": False,
        "paid": False,
        "provider_decision": "local_only",
        "privacy_impact": "local_only",
        "artifact_refs": {
            "markdown": {
                "path": validation["markdown_path"],
                "sha256": validation["markdown_sha256"],
                "kind": "proposal_markdown_draft",
            },
            "pdf": {
                "path": validation["pdf_path"],
                "sha256": validation["pdf_sha256"],
                "kind": "proposal_pdf_draft",
                "present": validation["pdf_present"],
            },
            "packet": {
                "path": validation["packet_path"],
                "sha256": validation["packet_sha256"],
                "kind": "proposal_packet",
            },
            "review_receipt": {
                "path": validation["receipt_path"],
                "sha256": validation["receipt_sha256_actual"],
                "kind": "proposal_review_receipt",
            },
            "proposal_send_receipt": {
                "path": send_state["send_receipt_path"],
                "sha256": send_state["send_receipt_sha256"],
                "kind": "proposal_email_sent_receipt",
                "present": send_state["send_receipt_present"],
            },
        },
        "email_send_record": {
            "recorded": bool(send_state["email_send_recorded"]),
            "sent_by_openclaw": False,
            "operator_assisted": bool(send_state["operator_assisted_send"]),
            "recipient": send_state["recipient"],
            "recipient_display_name": send_state["recipient_display_name"],
            "subject": send_state["subject"],
            "sent_gmail_message_id": send_state["sent_gmail_message_id"],
            "sent_gmail_thread_id": send_state["sent_gmail_thread_id"],
            "attachment_path": send_state["attachment_path"],
            "attachment_sha256": send_state["attachment_sha256"],
            "attachment_exists": send_state["attachment_exists"],
            "raw_message_included": False,
        },
        "proposal_terms": {
            "title": str(packet.get("title") or "Capital Hilton Fight Weekend Entertainment Proposal"),
            "subtitle": str(packet.get("subtitle") or ""),
            "recommended_package": "Hybrid Live + DJ Lounge Set",
            "dates": "Friday and Saturday",
            "two_night_total_usd": pricing.get("two_night_hybrid_live_dj_package_total_usd"),
            "expanded_sound_system_add_on_usd": pricing.get("expanded_sound_system_add_on_usd"),
            "optional_subwoofer_each_usd": pricing.get("optional_subwoofer_each_usd"),
            "dj_only_pricing_note": pricing.get("dj_only_pricing_note"),
        },
        "source_path_normalization": {
            "packet_markdown_path": _bridge_path_from_mac_path(str(packet.get("markdown_path") or "")),
            "packet_pdf_path": _bridge_path_from_mac_path(str(packet.get("pdf_path") or "")),
            "receipt_markdown_path": _bridge_path_from_mac_path(str(receipt.get("markdown_path") or "")),
            "receipt_pdf_path": _bridge_path_from_mac_path(str(receipt.get("pdf_path") or "")),
        },
        "safety_boundary": dict(SAFETY_FLAGS),
        "business_authority_boundary": dict(SAFETY_FLAGS),
        "proof_refs": {
            "collapsed_by_default": True,
            "proposal_packet_ref": validation["packet_path"],
            "proposal_review_receipt_ref": validation["receipt_path"],
            "proposal_send_receipt_ref": send_state["send_receipt_path"],
            "proposal_pdf_ref": validation["pdf_path"],
        },
        "validation": validation,
        "send_validation": send_state,
        "machine_proof": {
            "source_packet_parsed": True,
            "source_receipt_parsed": True,
            "proposal_draft_exists": True,
            "proposal_draft_hash_matches_packet_and_receipt": True,
            "proposal_pdf_present": validation["pdf_present"],
            "proposal_pdf_hash_matches_packet_and_receipt": validation["pdf_present"],
            "proposal_status_ready_for_review": proposal_status == DRAFT_PROPOSAL_STATUS,
            "proposal_status_sent_for_client_review": proposal_status == SENT_PROPOSAL_STATUS,
            "send_receipt_parsed": bool(send_state["send_receipt_present"]),
            "proposal_send_recorded": bool(send_state["proposal_sent_recorded"]),
            "email_send_recorded": bool(send_state["email_send_recorded"]),
            "sent_by_openclaw_false": True,
            "finance_handoff_allowed_false": True,
            "email_send_allowed_false": True,
            "ledger_posting_allowed_false": True,
            "sent_false": True,
            "paid_false": True,
            "proposal_accepted_false": True,
            "no_business_action_performed": not send_state["proposal_sent_recorded"],
            "no_new_business_action_performed_by_ingest": True,
            "all_safety_flags_false": all(value is False for value in SAFETY_FLAGS.values()),
        },
        "next_safe_move": (
            "Proposal is recorded as sent for client review; do not create an invoice, hand off to finance, "
            "post ledger, or mark accepted until separate operator direction."
            if send_state["proposal_sent_recorded"]
            else "Operator reviews the proposal draft; no send, finance handoff, invoice, ledger, or acceptance state is authorized."
        ),
    }
    payload["content_hash"] = "sha256:" + hashlib.sha256(stable_json(payload).encode("utf-8")).hexdigest()
    return payload


def export_read_model(
    *,
    input_dir: Path = DEFAULT_INPUT_DIR,
    export_root: Path = DEFAULT_EXPORT_ROOT,
    bridge_export_root: Path = DEFAULT_BRIDGE_EXPORT_ROOT,
    generated_at: str | None = None,
) -> ExportResult:
    payload = build_read_model(input_dir=input_dir, generated_at=generated_at)
    local_root = _rooted(export_root)
    local_root.mkdir(parents=True, exist_ok=True)
    read_model_path = local_root / JSON_EXPORT_NAME
    read_model_path.write_text(stable_json(payload), encoding="utf-8")

    bridge_export_root.mkdir(parents=True, exist_ok=True)
    bridge_path = bridge_export_root / JSON_EXPORT_NAME
    bridge_path.write_text(stable_json(payload), encoding="utf-8")

    return ExportResult(
        schema_version=SCHEMA_VERSION,
        read_model_path=str(read_model_path),
        bridge_read_model_path=str(bridge_path),
        proposal_draft_path=payload["artifact_refs"]["markdown"]["path"],
        proposal_status=str(payload["proposal_status"]),
        source_packet_path=payload["artifact_refs"]["packet"]["path"],
        source_receipt_path=payload["artifact_refs"]["review_receipt"]["path"],
        proposal_send_receipt_path=payload["artifact_refs"]["proposal_send_receipt"]["path"],
    )


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Ingest Capital Hilton Business Development proposal artifacts.")
    parser.add_argument("--input-dir", default=str(DEFAULT_INPUT_DIR))
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT))
    parser.add_argument("--bridge-export-root", default=str(DEFAULT_BRIDGE_EXPORT_ROOT))
    parser.add_argument("--generated-at")
    parser.add_argument("--format", choices=("json", "summary"), default="summary")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    result = export_read_model(
        input_dir=Path(args.input_dir),
        export_root=Path(args.export_root),
        bridge_export_root=Path(args.bridge_export_root),
        generated_at=args.generated_at,
    )
    if args.format == "json":
        print(stable_json(result.__dict__), end="")
    else:
        print(
            stable_json(
                {
                    "proposal_status": result.proposal_status,
                    "proposal_draft_path": result.proposal_draft_path,
                    "read_model_path": result.read_model_path,
                    "bridge_read_model_path": result.bridge_read_model_path,
                    "source_packet_path": result.source_packet_path,
                    "source_receipt_path": result.source_receipt_path,
                    "proposal_send_receipt_path": result.proposal_send_receipt_path,
                }
            ),
            end="",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
