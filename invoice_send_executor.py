"""Gated Square invoice-send executor.

This module wires the `invoice_send` executor surface without granting live
Square, email, workbook, ledger-payment, or paid-marking authority. Under the
active orchestration SEND_HOLD it always fails closed. When the hold is absent
and a packet is explicitly execution-approved, it records a local Square
sandbox receipt by default. The Reynolds branded-PDF-via-Square rail can be
previewed or invoked through an injected Square sender after the same gate
checks pass.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any, Callable, Mapping

from business_ops_ledger import DEFAULT_DB_PATH, append_side_effect, init_business_ops_ledger
from compose_contract import ExecutionReceipt


INVOICE_SEND_SURFACE = "invoice_send"
SQUARE_SANDBOX_EFFECT = "invoice_send.square.sandbox"
DEFAULT_SEND_HOLD_PATH = Path("/mnt/e/openclaw/orchestration/SEND_HOLD.md")
INVOICE_DELIVERY_MODE_SQUARE_SANDBOX = "square_sandbox"
INVOICE_DELIVERY_MODE_BRANDED_PDF_VIA_SQUARE = "branded_pdf_via_square"
REYNOLDS_BRANDED_INVOICE_PDF_PATH = (
    "artifacts/reynolds/Winship_Wheatley_Reynolds_Tavern_2026-06-27_invoice.pdf"
)


def invoice_send_executor_registered() -> bool:
    """Return whether the compose registry has an invoice sender installed."""

    from chief_compose import EXECUTORS

    return INVOICE_SEND_SURFACE in EXECUTORS


def _safe_db_path(db_path: str | None) -> str:
    return str(db_path or DEFAULT_DB_PATH)


def _side_effect_exists(packet_id: str, db_path: str | None, *, status: str) -> bool:
    path = _safe_db_path(db_path)
    init_business_ops_ledger(path)
    conn = sqlite3.connect(path)
    try:
        row = conn.execute(
            """
SELECT 1
FROM side_effects
WHERE packet_id = ?
  AND effect_type = ?
  AND status = ?
LIMIT 1
""".strip(),
            (packet_id, SQUARE_SANDBOX_EFFECT, status),
        ).fetchone()
        return row is not None
    finally:
        conn.close()


def _sandbox_ref(packet_id: str) -> str:
    digest = hashlib.sha256(f"square-sandbox\0{packet_id}".encode("utf-8")).hexdigest()
    return f"square_sandbox_local:{digest[:20]}"


def _append_invoice_side_effect(
    *,
    packet_id: str,
    status: str,
    db_path: str | None,
    external_ref: str | None = None,
) -> str | None:
    init_business_ops_ledger(db_path)
    return append_side_effect(
        packet_id=packet_id,
        effect_type=SQUARE_SANDBOX_EFFECT,
        status=status,
        approval_required=True,
        approval_tier="G3",
        replay_safe=False,
        external_ref=external_ref,
        db_path=db_path,
    )


def _receipt(
    *,
    packet_id: str,
    ok: bool,
    detail: str,
    status: str,
    db_path: str | None,
    external_ref: str | None = None,
    meta: dict[str, Any] | None = None,
) -> ExecutionReceipt:
    side_effect_id = _append_invoice_side_effect(
        packet_id=packet_id,
        status=status,
        db_path=db_path,
        external_ref=external_ref,
    )
    return ExecutionReceipt(
        packet_id=packet_id,
        surface=INVOICE_SEND_SURFACE,
        ok=ok,
        detail=detail,
        side_effect_id=side_effect_id,
        meta={
            "provider": "square",
            "square_environment": "sandbox",
            "square_api_called": False,
            "square_production_used": False,
            "external_send_performed": False,
            "email_send_performed": False,
            "workbook_written": False,
            "ledger_payment_posted": False,
            "invoice_marked_paid": False,
            "side_effect_recorded": bool(side_effect_id),
            **(meta or {}),
        },
    )


def _payload_hash(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(json.dumps(dict(payload), sort_keys=True).encode("utf-8")).hexdigest()


def build_reynolds_branded_invoice_payload(
    *,
    rendered_pdf_path: str | Path,
) -> dict[str, Any]:
    """Return the exact Reynolds invoice payload for the branded Square rail."""

    attachment_path = str(rendered_pdf_path).strip()
    if not attachment_path:
        raise ValueError("rendered_pdf_path is required for branded-PDF-via-Square delivery")
    return {
        "to": "Sally <reservations@reynoldstavern.com>",
        "delivery_mode": INVOICE_DELIVERY_MODE_BRANDED_PDF_VIA_SQUARE,
        "attachment_path": attachment_path,
        "amount": "250.00",
        "currency": "USD",
        "description": "Live music performance at Reynolds Tavern on 2026-06-27, 19:00-22:00",
        "payment_terms": "Due upon receipt",
    }


def preview_reynolds_invoice_payload(
    *,
    rendered_pdf_path: str | Path = REYNOLDS_BRANDED_INVOICE_PDF_PATH,
    packet_id: str = "invoice_send_preview",
    db_path: str | None = None,
) -> ExecutionReceipt:
    """Return the Reynolds invoice payload without sending or touching Square."""

    payload = build_reynolds_branded_invoice_payload(rendered_pdf_path=rendered_pdf_path)
    return _receipt(
        packet_id=packet_id,
        ok=True,
        detail="Branded invoice Square preview generated. Nothing was sent.",
        status="preview_no_send",
        db_path=db_path,
        meta={
            "preview_only": True,
            "delivery_mode": INVOICE_DELIVERY_MODE_BRANDED_PDF_VIA_SQUARE,
            "outbound_payload": payload,
            "payload_hash": _payload_hash(payload),
        },
    )


def _provider_result_ok(result: Any) -> bool:
    return not (isinstance(result, Mapping) and result.get("ok") is False)


def _provider_external_ref(result: Any) -> str | None:
    if not isinstance(result, Mapping):
        return None
    data = result.get("data")
    if isinstance(data, Mapping):
        for key in ("invoice_id", "payment_link", "id"):
            if data.get(key):
                return f"square:{data[key]}"
    for key in ("provider_invoice_id", "invoice_id", "payment_link", "id"):
        if result.get(key):
            return f"square:{result[key]}"
    return None


def execute_invoice_send_packet(
    *,
    packet_id: str,
    db_path: str | None = None,
    expected_packet_hash: str | None = None,
    send_hold_path: str | Path = DEFAULT_SEND_HOLD_PATH,
    square_environment: str = "sandbox",
    delivery_mode: str = INVOICE_DELIVERY_MODE_SQUARE_SANDBOX,
    rendered_pdf_path: str | Path | None = None,
    square_sender: Callable[..., Any] | None = None,
    preview_only: bool = False,
) -> ExecutionReceipt:
    """Execute or preview an approved invoice-send packet."""

    from chief_compose import get_packet_approval_state

    packet_id = (packet_id or "").strip()
    if not packet_id:
        return ExecutionReceipt(packet_id="", surface=INVOICE_SEND_SURFACE, ok=False, detail="packet_id is required")

    if preview_only:
        try:
            return preview_reynolds_invoice_payload(
                rendered_pdf_path=rendered_pdf_path or REYNOLDS_BRANDED_INVOICE_PDF_PATH,
                packet_id=packet_id,
                db_path=db_path,
            )
        except ValueError as exc:
            return _receipt(
                packet_id=packet_id,
                ok=False,
                detail=str(exc),
                status="blocked_invalid_payload",
                db_path=db_path,
                meta={"preview_only": True},
            )

    try:
        state = get_packet_approval_state(
            packet_id,
            expected_packet_hash=expected_packet_hash,
            db_path=_safe_db_path(db_path),
        )
    except ValueError as exc:
        return _receipt(
            packet_id=packet_id,
            ok=False,
            detail=str(exc),
            status="blocked_guard_failed",
            db_path=db_path,
        )

    if state["surface"] != INVOICE_SEND_SURFACE:
        return _receipt(
            packet_id=packet_id,
            ok=False,
            detail=f"Packet surface is {state['surface']!r}, not 'invoice_send'. Nothing was sent.",
            status="blocked_guard_failed",
            db_path=db_path,
            meta={"approval_state": state},
        )
    if state["stale"]:
        return _receipt(
            packet_id=packet_id,
            ok=False,
            detail="Packet stale-hash check failed. Nothing was sent.",
            status="blocked_guard_failed",
            db_path=db_path,
            meta={"approval_state": state},
        )
    if Path(send_hold_path).is_file():
        return _receipt(
            packet_id=packet_id,
            ok=False,
            detail="SEND_HOLD is active. Square invoice sandbox send is blocked; nothing was sent.",
            status="blocked_send_hold",
            db_path=db_path,
            meta={"approval_state": state, "send_hold_active": True},
        )
    if not state["execution_allowed"]:
        return _receipt(
            packet_id=packet_id,
            ok=False,
            detail="Packet is not execution-approved. Nothing was sent.",
            status="blocked_guard_failed",
            db_path=db_path,
            meta={"approval_state": state, "send_hold_active": False},
        )
    if delivery_mode not in {
        INVOICE_DELIVERY_MODE_SQUARE_SANDBOX,
        INVOICE_DELIVERY_MODE_BRANDED_PDF_VIA_SQUARE,
    }:
        return _receipt(
            packet_id=packet_id,
            ok=False,
            detail=f"Unsupported invoice delivery mode {delivery_mode!r}. Nothing was sent.",
            status="blocked_guard_failed",
            db_path=db_path,
            meta={"approval_state": state, "send_hold_active": False, "delivery_mode": delivery_mode},
        )
    if delivery_mode == INVOICE_DELIVERY_MODE_BRANDED_PDF_VIA_SQUARE:
        try:
            payload = build_reynolds_branded_invoice_payload(rendered_pdf_path=rendered_pdf_path or "")
        except ValueError as exc:
            return _receipt(
                packet_id=packet_id,
                ok=False,
                detail=f"{exc}. Nothing was sent.",
                status="blocked_invalid_payload",
                db_path=db_path,
                meta={"approval_state": state, "send_hold_active": False},
            )
        if square_sender is None:
            return _receipt(
                packet_id=packet_id,
                ok=False,
                detail="No approved Square branded-PDF transport is attached. Nothing was sent.",
                status="blocked_no_square_transport",
                db_path=db_path,
                meta={
                    "approval_state": state,
                    "send_hold_active": False,
                    "delivery_mode": delivery_mode,
                    "outbound_payload": payload,
                    "payload_hash": _payload_hash(payload),
                },
            )
        if _side_effect_exists(packet_id, db_path, status="branded_pdf_square_send_invoked"):
            return _receipt(
                packet_id=packet_id,
                ok=False,
                detail="A branded-PDF Square send receipt already exists for this packet. Nothing was sent again.",
                status="blocked_duplicate_success",
                db_path=db_path,
                meta={"approval_state": state, "send_hold_active": False, "delivery_mode": delivery_mode},
            )
        provider_result = square_sender(
            **payload,
            approval_state=state,
            packet_id=packet_id,
        )
        if not _provider_result_ok(provider_result):
            return _receipt(
                packet_id=packet_id,
                ok=False,
                detail=f"Square branded-PDF send failed: {provider_result.get('error', 'unknown error')}",
                status="branded_pdf_square_send_failed",
                db_path=db_path,
                meta={
                    "approval_state": state,
                    "send_hold_active": False,
                    "delivery_mode": delivery_mode,
                    "outbound_payload": payload,
                    "payload_hash": _payload_hash(payload),
                    "provider_result": provider_result,
                    "square_api_called": True,
                    "external_send_performed": False,
                },
            )
        return _receipt(
            packet_id=packet_id,
            ok=True,
            detail="Branded-PDF Square rail invoked for approved invoice packet.",
            status="branded_pdf_square_send_invoked",
            db_path=db_path,
            external_ref=_provider_external_ref(provider_result),
            meta={
                "approval_state": state,
                "send_hold_active": False,
                "delivery_mode": delivery_mode,
                "outbound_payload": payload,
                "payload_hash": _payload_hash(payload),
                "provider_result": provider_result,
                "square_environment": square_environment,
                "square_api_called": True,
                "external_send_performed": True,
                "sandbox_receipt_only": False,
            },
        )
    if square_environment != "sandbox":
        return _receipt(
            packet_id=packet_id,
            ok=False,
            detail="Only Square sandbox execution is allowed in this lane. Nothing was sent.",
            status="blocked_non_sandbox",
            db_path=db_path,
            meta={"approval_state": state, "send_hold_active": False, "requested_environment": square_environment},
        )
    if _side_effect_exists(packet_id, db_path, status="sandbox_send_recorded"):
        return _receipt(
            packet_id=packet_id,
            ok=False,
            detail="A Square sandbox invoice send receipt already exists for this packet. Nothing was sent again.",
            status="blocked_duplicate_success",
            db_path=db_path,
            meta={"approval_state": state, "send_hold_active": False},
        )

    sandbox_ref = _sandbox_ref(packet_id)
    return _receipt(
        packet_id=packet_id,
        ok=True,
        detail=(
            "Square sandbox invoice send recorded locally. No production send, email, workbook write, "
            "ledger payment post, or paid marking occurred."
        ),
        status="sandbox_send_recorded",
        db_path=db_path,
        external_ref=sandbox_ref,
        meta={
            "approval_state": state,
            "send_hold_active": False,
            "square_sandbox_ref": sandbox_ref,
            "sandbox_receipt_only": True,
        },
    )


__all__ = [
    "DEFAULT_SEND_HOLD_PATH",
    "INVOICE_DELIVERY_MODE_BRANDED_PDF_VIA_SQUARE",
    "INVOICE_DELIVERY_MODE_SQUARE_SANDBOX",
    "INVOICE_SEND_SURFACE",
    "REYNOLDS_BRANDED_INVOICE_PDF_PATH",
    "SQUARE_SANDBOX_EFFECT",
    "build_reynolds_branded_invoice_payload",
    "execute_invoice_send_packet",
    "invoice_send_executor_registered",
    "preview_reynolds_invoice_payload",
]
