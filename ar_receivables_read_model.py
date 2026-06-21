"""Read-only AR receivables rollup for Maestro context packets."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import re
from typing import Any, Mapping, Sequence


SCHEMA_VERSION = "ar_receivables_read_model_v0"
READ_MODEL_ID = "ar_receivables_status"
EXPORT_NAME = f"{READ_MODEL_ID}.json"
DEFAULT_READ_MODEL_ROOT = Path("generated/read_models")

UNSAFE_AUTHORITY_KEY_MARKERS = (
    "access",
    "allowed",
    "created",
    "generation",
    "mutation",
    "performed",
    "posting",
    "send",
    "sent",
    "submit",
    "write",
)
SAFE_TRUE_AUTHORITY_KEYS = frozenset({"operator_provided"})


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _display_ref(root: Path, path: Path) -> str:
    try:
        relative = path.relative_to(root)
    except ValueError:
        return path.as_posix()
    return f"generated/read_models/{relative.as_posix()}"


def _money_value(value: Any) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    match = re.search(r"-?\d[\d,]*(?:\.\d+)?", str(value or ""))
    if not match:
        return 0.0
    return float(match.group(0).replace(",", ""))


def _usd(value: float) -> str:
    return f"${value:,.2f}"


def _unsafe_authority_granted(boundary: Mapping[str, Any]) -> bool:
    for key, value in boundary.items():
        normalized = str(key or "").lower()
        if normalized in SAFE_TRUE_AUTHORITY_KEYS:
            continue
        if any(marker in normalized for marker in UNSAFE_AUTHORITY_KEY_MARKERS) and bool(value):
            return True
    return False


def _source_ref(root: Path, name: str) -> str:
    return _display_ref(root, root / name)


def _capital_hilton_receivable(root: Path, payload: Mapping[str, Any]) -> dict[str, Any] | None:
    if not payload:
        return None
    amount = _money_value(payload.get("invoice_total") or payload.get("amount") or payload.get("total_amount"))
    paid = bool(payload.get("paid"))
    submitted = bool(payload.get("coupa_submitted"))
    status = str(payload.get("coupa_submission_status") or payload.get("coupa_status_observed") or "unknown").strip()
    email_status = str(payload.get("email_status") or "").strip()
    boundary = payload.get("authority_boundary") if isinstance(payload.get("authority_boundary"), Mapping) else {}
    return {
        "client_ref": str(payload.get("client_ref") or "capital_hilton"),
        "client_display_name": str(payload.get("client_display_name") or "Capital Hilton"),
        "receivable_ref": "capital_hilton:coupa_invoice",
        "amount_value": amount,
        "amount_display": _usd(amount) if amount else "",
        "open_amount_value": 0.0 if paid else amount,
        "invoice_status": status or "unknown",
        "receipt_status": "PAID" if paid else "UNPAID",
        "send_or_submit_status": "COUPA_SUBMITTED_PROCESSING" if submitted else "NOT_SUBMITTED_BY_OPENCLAW",
        "email_status": email_status,
        "next_safe_move": "Review Coupa/payment proof before any follow-up; do not mark paid or mutate ledger.",
        "source_refs": [_source_ref(root, "capital_hilton_invoice_operator_run_status.json")],
        "authority_boundary": dict(boundary),
        "unsafe_authority_granted": _unsafe_authority_granted(boundary),
    }


def _live_arts_receivables(root: Path, payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    if not payload:
        return []
    boundary = payload.get("authority_boundary") if isinstance(payload.get("authority_boundary"), Mapping) else {}
    rows = payload.get("invoice_candidates") if isinstance(payload.get("invoice_candidates"), Sequence) else ()
    receivables: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        amount = _money_value(row.get("amount") or row.get("amount_display"))
        if amount <= 0:
            continue
        paid = bool(row.get("paid"))
        invoice_id = str(row.get("invoice_id") or "unknown_invoice")
        receivables.append(
            {
                "client_ref": str(payload.get("client_ref") or row.get("client_ref") or "live_arts_md"),
                "client_display_name": str(payload.get("client_display_name") or row.get("client") or "Live Arts MD"),
                "receivable_ref": f"live_arts_md:{invoice_id}",
                "amount_value": amount,
                "amount_display": str(row.get("amount_display") or _usd(amount)),
                "open_amount_value": 0.0 if paid else amount,
                "invoice_status": str(row.get("invoice_status") or ""),
                "receipt_status": str(row.get("receipt_status") or ("PAID" if paid else "UNPAID")),
                "send_or_submit_status": str(row.get("send_readiness") or ""),
                "readiness_status": str(row.get("readiness_status") or ""),
                "next_safe_move": str(payload.get("primary_next_action") or "Choose or verify the Live Arts MD invoice candidate."),
                "source_refs": [_source_ref(root, "live_arts_md_invoice_candidate_register.json")],
                "authority_boundary": dict(boundary),
                "unsafe_authority_granted": _unsafe_authority_granted(boundary),
            }
        )
    return receivables


def _st_annes_receivable(root: Path, review_surface: Mapping[str, Any], contract: Mapping[str, Any]) -> dict[str, Any] | None:
    if not review_surface and not contract:
        return None
    events = review_surface.get("events") if isinstance(review_surface.get("events"), Sequence) else ()
    ready_events = [
        event
        for event in events
        if isinstance(event, Mapping)
        and str(event.get("invoice_inclusion_status") or "").upper() == "READY_FOR_MONTHLY_ROLLUP"
    ]
    amount = sum(_money_value(event.get("amount")) for event in ready_events)
    boundary = (
        review_surface.get("authority_boundary")
        if isinstance(review_surface.get("authority_boundary"), Mapping)
        else contract.get("authority_boundary")
        if isinstance(contract.get("authority_boundary"), Mapping)
        else {}
    )
    return {
        "client_ref": str(review_surface.get("client_ref") or contract.get("client_ref") or "st_annes"),
        "client_display_name": str(contract.get("client_display_name") or "St. Anne's"),
        "receivable_ref": "st_annes:monthly_rollup",
        "amount_value": amount,
        "amount_display": _usd(amount) if amount else "$0.00",
        "open_amount_value": amount,
        "invoice_status": "READY_FOR_MONTHLY_ROLLUP" if ready_events else "NO_ACTIVE_AR_IN_READ_MODELS",
        "receipt_status": "UNPAID" if ready_events else "NO_ACTIVE_RECEIVABLE",
        "send_or_submit_status": "NOT_SENT_BY_OPENCLAW",
        "next_safe_move": "Only operator-confirmed non-smoke events can roll into a St. Anne's invoice package.",
        "source_refs": [
            _source_ref(root, "st_annes_work_log_review_surface.json"),
            _source_ref(root, "st_annes_monthly_work_log_contract.json"),
        ],
        "authority_boundary": dict(boundary),
        "unsafe_authority_granted": _unsafe_authority_granted(boundary),
    }


def _client_rollups(receivables: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for row in receivables:
        key = str(row.get("client_ref") or row.get("client_display_name") or "unknown")
        current = grouped.setdefault(
            key,
            {
                "client_ref": str(row.get("client_ref") or key),
                "client_display_name": str(row.get("client_display_name") or key),
                "open_amount_value": 0.0,
                "receivable_count": 0,
                "statuses": [],
            },
        )
        current["open_amount_value"] += float(row.get("open_amount_value") or 0.0)
        current["receivable_count"] += 1
        status = str(row.get("invoice_status") or row.get("receipt_status") or "").strip()
        if status and status not in current["statuses"]:
            current["statuses"].append(status)
    rollups = []
    for row in grouped.values():
        amount = float(row["open_amount_value"])
        rollups.append(
            {
                **row,
                "open_amount_display": _usd(amount),
            }
        )
    return sorted(rollups, key=lambda row: (-float(row["open_amount_value"]), str(row["client_display_name"])))


def _operator_summary(rollups: Sequence[Mapping[str, Any]]) -> str:
    parts = []
    for row in rollups[:5]:
        statuses = ", ".join(str(status) for status in row.get("statuses", ()) if str(status).strip())
        parts.append(f"{row.get('client_display_name')}: {row.get('open_amount_display')} open ({statuses or 'status unknown'})")
    return "; ".join(parts)


def build_ar_receivables_read_model(
    *,
    read_model_root: str | Path | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    root = Path(read_model_root or DEFAULT_READ_MODEL_ROOT)
    capital = _read_json(root / "capital_hilton_invoice_operator_run_status.json")
    live_arts = _read_json(root / "live_arts_md_invoice_candidate_register.json")
    st_review = _read_json(root / "st_annes_work_log_review_surface.json")
    st_contract = _read_json(root / "st_annes_monthly_work_log_contract.json")

    receivables = [
        row
        for row in [
            _capital_hilton_receivable(root, capital),
            *_live_arts_receivables(root, live_arts),
            _st_annes_receivable(root, st_review, st_contract),
        ]
        if row
    ]
    source_refs = sorted({ref for row in receivables for ref in row.get("source_refs", ())})
    rollups = _client_rollups(receivables)
    open_total = sum(float(row.get("open_amount_value") or 0.0) for row in receivables)
    unsafe_authority = any(bool(row.get("unsafe_authority_granted")) for row in receivables)
    operator_summary = _operator_summary(rollups)
    return {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "generated_at": generated_at or _utc_now(),
        "status": "READY" if receivables else "EMPTY",
        "operator_summary": operator_summary,
        "next_safe_ar_move": (
            "Review payment/proof status for submitted invoices, then choose one draft receivable packet to prepare; "
            "no send, money movement, bank access, or ledger mutation is allowed."
        ),
        "receivables": receivables,
        "client_rollups": rollups,
        "open_receivable_count": sum(1 for row in receivables if float(row.get("open_amount_value") or 0.0) > 0),
        "open_amount_value": open_total,
        "open_amount_display": _usd(open_total),
        "source_refs": source_refs,
        "authority_boundary": {
            "bank_access_allowed": False,
            "email_send_allowed": False,
            "invoice_send_allowed": False,
            "ledger_posting_allowed": False,
            "money_movement_allowed": False,
            "paid_marking_allowed": False,
            "workbook_body_read_allowed": False,
            "workbook_write_allowed": False,
        },
        "machine_proof": {
            "source_read_model_count": len(source_refs),
            "unsafe_authority_granted": unsafe_authority,
            "read_only_rollup": True,
            "no_bank_access": True,
            "no_send_or_money_movement": True,
            "no_ledger_mutation": True,
            "st_annes_smoke_events_not_counted_as_ar": True,
        },
    }


def write_exports(
    payload: Mapping[str, Any],
    export_root: str | Path | None = None,
) -> Path:
    root = Path(export_root or DEFAULT_READ_MODEL_ROOT)
    root.mkdir(parents=True, exist_ok=True)
    target = root / EXPORT_NAME
    target.write_text(stable_json(dict(payload)), encoding="utf-8")
    return target


__all__ = [
    "EXPORT_NAME",
    "READ_MODEL_ID",
    "SCHEMA_VERSION",
    "build_ar_receivables_read_model",
    "write_exports",
]
