"""Cassandra handler for operator "show me the proof" requests.

This is review/display only. It returns the Reynolds draft email text plus a
typed invoice PDF artifact for the app, and mirrors the same proof package to
Winship's authorized Telegram through the default-off B3 delivery adapter.
It does not send anything to Sally or touch SEND_HOLD.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping

import cassandra_telegram_delivery as telegram_delivery


SCHEMA_VERSION = "cassandra_show_proof_handler_v0"
DEFAULT_REYNOLDS_DRAFT_PATH = Path("/mnt/e/openclaw/orchestration/artifacts/reynolds/intro_email_draft.md")
DEFAULT_APP_INVOICE_PDF_PATH = Path(
    "/Volumes/openclaw_e/orchestration/artifacts/reynolds/Winship_Wheatley_Reynolds_Tavern_2026-06-27_invoice.pdf"
)
DEFAULT_TELEGRAM_INVOICE_PDF_PATH = Path(
    "/mnt/e/openclaw/orchestration/artifacts/reynolds/Winship_Wheatley_Reynolds_Tavern_2026-06-27_invoice.pdf"
)

SHOW_PROOF_PATTERNS = (
    re.compile(r"\bshow\s+me\s+the\s+proof\b", re.IGNORECASE),
    re.compile(r"\bshow\s+(me\s+)?the\s+reynolds\b", re.IGNORECASE),
    re.compile(r"\bshow\s+me\s+the\s+invoice\b", re.IGNORECASE),
    re.compile(r"\bshow\s+me\s+the\s+package\b", re.IGNORECASE),
    re.compile(r"\breynolds\s+(invoice|package|proof)\b", re.IGNORECASE),
)


@dataclass(frozen=True)
class ShowProofResponse:
    status: str
    intent_matched: bool
    response_text: str
    draft_email_text: str
    draft_source_path: str
    proof_artifacts: tuple[dict[str, Any], ...]
    telegram_text_receipt: dict[str, Any] | None
    telegram_document_receipt: dict[str, Any] | None
    client_send_performed: bool = False
    external_client_send_performed: bool = False
    email_send_performed: bool = False
    send_hold_touched: bool = False
    telegram_operator_only: bool = True
    schema_version: str = SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["proof_artifacts"] = [dict(item) for item in self.proof_artifacts]
        return data


def is_show_proof_intent(text: str) -> bool:
    cleaned = str(text or "").strip()
    return any(pattern.search(cleaned) for pattern in SHOW_PROOF_PATTERNS)


def _fallback_reynolds_draft() -> str:
    return (
        "To: Sally <reservations@reynoldstavern.com>\n"
        "Subject: June 27 music at Reynolds Tavern\n\n"
        "Hi Sally,\n\n"
        "Mike Heuer asked me to cover his Reynolds Tavern date on Friday, June 27, from 7-10pm, "
        "and I am looking forward to it.\n\n"
        "Best,\n\n"
        "Winship Wheatley"
    )


def _extract_email_draft(markdown: str) -> str:
    lines = str(markdown or "").replace("\r\n", "\n").splitlines()
    to_line = ""
    subject_line = ""
    body_lines: list[str] = []
    body_started = False
    for line in lines:
        stripped = line.strip()
        lower = stripped.lower()
        if lower.startswith("to:"):
            to_line = stripped
            continue
        if lower.startswith("subject:"):
            subject_line = stripped
            body_started = True
            continue
        if stripped.startswith("## Approval Notes"):
            break
        if body_started:
            body_lines.append(line.rstrip())

    body = "\n".join(body_lines).strip()
    pieces = [item for item in (to_line, subject_line) if item]
    if body:
        pieces.append(body)
    draft = "\n".join(pieces).strip()
    return draft or _fallback_reynolds_draft()


def load_reynolds_draft_email_text(draft_path: str | Path = DEFAULT_REYNOLDS_DRAFT_PATH) -> str:
    path = Path(draft_path)
    try:
        return _extract_email_draft(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return _fallback_reynolds_draft()


def build_reynolds_proof_artifact(
    *,
    app_invoice_pdf_path: str | Path = DEFAULT_APP_INVOICE_PDF_PATH,
    telegram_invoice_pdf_path: str | Path = DEFAULT_TELEGRAM_INVOICE_PDF_PATH,
) -> dict[str, Any]:
    return {
        "artifact_id": "reynolds_invoice_pdf_2026_06_27",
        "artifact_type": "proof_pdf",
        "role": "invoice_pdf",
        "mime_type": "application/pdf",
        "path": str(app_invoice_pdf_path),
        "telegram_document_path": str(telegram_invoice_pdf_path),
        "presentation": {
            "presenter": "ProofPresenter",
            "mode": "quicklook",
            "should_open": True,
        },
        "review_only": True,
        "client_send_allowed": False,
    }


def build_show_proof_response_text(draft_email_text: str, artifact: Mapping[str, Any]) -> str:
    return (
        "Here is the Reynolds package proof for review: the draft email text is included, "
        f"and the invoice PDF is ready as a proof artifact for QuickLook: {artifact.get('path')}. "
        "Nothing has been sent to Sally; SEND_HOLD remains untouched."
    )


def handle_show_proof_intent(
    operator_text: str,
    *,
    draft_path: str | Path = DEFAULT_REYNOLDS_DRAFT_PATH,
    app_invoice_pdf_path: str | Path = DEFAULT_APP_INVOICE_PDF_PATH,
    telegram_invoice_pdf_path: str | Path = DEFAULT_TELEGRAM_INVOICE_PDF_PATH,
    env: Mapping[str, str] | None = None,
    toggle_path: str | Path = telegram_delivery.DEFAULT_TOGGLE_PATH,
    dry_run_log_path: str | Path = telegram_delivery.DEFAULT_DRY_RUN_LOG_PATH,
    authorized_chat_id: str | int | None = None,
    telegram_sender: telegram_delivery.TelegramSender | None = None,
    telegram_document_sender: telegram_delivery.TelegramSender | None = None,
) -> ShowProofResponse:
    if not is_show_proof_intent(operator_text):
        return ShowProofResponse(
            status="not_show_proof_intent",
            intent_matched=False,
            response_text="",
            draft_email_text="",
            draft_source_path=str(draft_path),
            proof_artifacts=(),
            telegram_text_receipt=None,
            telegram_document_receipt=None,
        )

    draft_email_text = load_reynolds_draft_email_text(draft_path)
    artifact = build_reynolds_proof_artifact(
        app_invoice_pdf_path=app_invoice_pdf_path,
        telegram_invoice_pdf_path=telegram_invoice_pdf_path,
    )
    response_text = build_show_proof_response_text(draft_email_text, artifact)
    text_receipt = telegram_delivery.deliver_to_authorized_telegram(
        message_text=draft_email_text,
        delivery_kind="reynolds_show_proof_draft_text",
        env=env,
        toggle_path=toggle_path,
        dry_run_log_path=dry_run_log_path,
        authorized_chat_id=authorized_chat_id,
        telegram_sender=telegram_sender,
        source_refs=("reynolds_show_proof", str(draft_path)),
    )
    document_receipt = telegram_delivery.deliver_document_to_authorized_telegram(
        document_path=telegram_invoice_pdf_path,
        caption="Reynolds Tavern invoice proof for review only. No client send.",
        delivery_kind="reynolds_show_proof_invoice_document",
        env=env,
        toggle_path=toggle_path,
        dry_run_log_path=dry_run_log_path,
        authorized_chat_id=authorized_chat_id,
        telegram_document_sender=telegram_document_sender,
        source_refs=("reynolds_show_proof", str(telegram_invoice_pdf_path)),
    )

    return ShowProofResponse(
        status="reynolds_proof_ready_for_review",
        intent_matched=True,
        response_text=response_text,
        draft_email_text=draft_email_text,
        draft_source_path=str(draft_path),
        proof_artifacts=(artifact,),
        telegram_text_receipt=text_receipt.to_dict(),
        telegram_document_receipt=document_receipt.to_dict(),
    )


__all__ = [
    "DEFAULT_APP_INVOICE_PDF_PATH",
    "DEFAULT_REYNOLDS_DRAFT_PATH",
    "DEFAULT_TELEGRAM_INVOICE_PDF_PATH",
    "SCHEMA_VERSION",
    "ShowProofResponse",
    "build_reynolds_proof_artifact",
    "build_show_proof_response_text",
    "handle_show_proof_intent",
    "is_show_proof_intent",
    "load_reynolds_draft_email_text",
]
