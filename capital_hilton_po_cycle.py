"""Capital Hilton purchase-order cycle: know each PO's cap, what is invoiced, how many
performances are uninvoiced, and when a new PO is needed prepare the request.

Prepare-only. Reads an operator-maintained config, writes a read model, and when a new PO is
needed writes one local .eml draft under generated/email_drafts/ and one attention event.
Coupa stays manual. Sending stays behind SEND_HOLD, Guardian, and the exact-send phrase.
No money moves, nothing is marked paid, no model is called.
"""

from __future__ import annotations

import json
import math
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

SCHEMA_VERSION = "capital_hilton_po_cycle_v0"
READ_MODEL_ID = "capital_hilton_po_cycle"
ATTENTION_SCHEMA_VERSION = "capital_hilton_po_cycle_attention_v0"
DEFAULT_CONFIG_PATH = Path("config/capital_hilton_po_cycle.v1.json")
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_DRAFT_ROOT = Path("generated/email_drafts/capital_hilton_po_cycle")
PO_STATUSES = ("open", "exhausted", "unknown")

AUTHORITY_BOUNDARY = {
    "send_performed": False,
    "email_send_performed": False,
    "coupa_access_performed": False,
    "browser_access_performed": False,
    "money_movement_performed": False,
    "ledger_mutation_performed": False,
    "ledger_posting_performed": False,
    "paid_marking_performed": False,
    "telegram_send_performed": False,
    "external_model_called": False,
}

ContactResolver = Callable[[str], Mapping[str, Any] | None]


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _int(value: Any, default: int = 0) -> int:
    if isinstance(value, bool):
        return default
    if isinstance(value, int):
        return value
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default


def _dollars(minor_units: int, currency: str = "USD") -> str:
    prefix = "$" if currency == "USD" else f"{currency} "
    whole, cents = divmod(int(minor_units), 100)
    return f"{prefix}{whole:,}" if cents == 0 else f"{prefix}{whole:,}.{cents:02d}"


def load_config(path: str | Path = DEFAULT_CONFIG_PATH) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError("PO cycle config must be a JSON object")
    return dict(payload)


def _default_contact_resolver(ref: str) -> Mapping[str, Any] | None:
    try:
        from contacts_registry import ContactsRegistry

        return ContactsRegistry().get_contact(ref)
    except Exception:
        return None


def _contact_lines(refs: list[str], resolver: ContactResolver) -> list[dict[str, Any]]:
    lines: list[dict[str, Any]] = []
    for ref in refs:
        contact = None
        try:
            contact = resolver(ref)
        except Exception:
            contact = None
        name = str((contact or {}).get("name") or "").strip()
        email = str((contact or {}).get("email") or "").strip()
        lines.append({"contact_ref": ref, "name": name or ref, "email_known": bool(email), "email": email})
    return lines


def _po_rows(config: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for raw in config.get("purchase_orders") or []:
        if not isinstance(raw, Mapping):
            continue
        cap = _int(raw.get("cap_minor_units"), -1)
        invoiced = _int(raw.get("invoiced_minor_units"), 0)
        remaining = cap - invoiced if cap >= 0 else 0
        if cap < 0:
            status = "unknown"
        elif remaining <= 0:
            status = "exhausted"
        else:
            status = "open"
        rows.append(
            {
                "po_number": str(raw.get("po_number") or "").strip(),
                "cap_minor_units": cap if cap >= 0 else None,
                "invoiced_minor_units": invoiced,
                "remaining_minor_units": max(0, remaining),
                "status": status,
                "source_ref": str(raw.get("source_ref") or ""),
                "note": str(raw.get("note") or ""),
            }
        )
    return sorted(rows, key=lambda row: row["po_number"])


def _performance_rows(config: Mapping[str, Any], *, today: date) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for raw in config.get("performances") or []:
        if not isinstance(raw, Mapping):
            continue
        day_text = str(raw.get("date") or "").strip()
        try:
            day = date.fromisoformat(day_text)
        except ValueError:
            continue
        po = str(raw.get("invoiced_under_po") or "").strip()
        rows.append(
            {
                "date": day.isoformat(),
                "description": str(raw.get("description") or "").strip(),
                "invoiced_under_po": po or None,
                "performed": day <= today,
                "invoice_ref": str(raw.get("invoice_ref") or "") or None,
            }
        )
    return sorted(rows, key=lambda row: row["date"])


def build_po_cycle(
    config: Mapping[str, Any],
    *,
    today: date | None = None,
    generated_at: str | None = None,
    contact_resolver: ContactResolver | None = None,
) -> dict[str, Any]:
    today = today or datetime.now(timezone.utc).date()
    generated_at = generated_at or _utc_now()
    resolver = contact_resolver or _default_contact_resolver
    currency = str(config.get("currency_iso") or "USD").upper()
    rate = _int(config.get("rate_minor_units_per_performance"), 0)
    standard_shows = max(1, _int(config.get("standard_po_performances"), 5))
    threshold = max(1, _int(config.get("request_when_uninvoiced_reaches"), 1))

    pos = _po_rows(config)
    performances = _performance_rows(config, today=today)
    performed = [row for row in performances if row["performed"]]
    uninvoiced = [row for row in performed if not row["invoiced_under_po"]]
    uninvoiced_value = rate * len(uninvoiced)
    open_capacity = sum(row["remaining_minor_units"] for row in pos if row["status"] == "open")
    shortfall = max(0, uninvoiced_value - open_capacity)
    needs_new_po = len(uninvoiced) >= threshold and shortfall > 0
    recommended_shows = max(standard_shows, int(math.ceil(shortfall / rate)) if rate else standard_shows)
    recommended_minor_units = recommended_shows * rate

    if rate <= 0:
        reason = "No per-performance rate configured; cannot size a purchase order."
        needs_new_po = False
    elif not performed:
        reason = "No performances recorded yet; nothing to invoice, no PO needed."
    elif not uninvoiced:
        reason = "Every performance so far is invoiced under a PO."
    elif not needs_new_po:
        reason = f"{len(uninvoiced)} uninvoiced performance(s) fit inside open PO capacity {_dollars(open_capacity, currency)}."
    else:
        reason = (
            f"{len(uninvoiced)} uninvoiced performance(s) worth {_dollars(uninvoiced_value, currency)} exceed open PO capacity "
            f"{_dollars(open_capacity, currency)}; request a new PO for {recommended_shows} performances "
            f"({_dollars(recommended_minor_units, currency)})."
        )

    ap_refs = [str(ref) for ref in (config.get("ap_contact_refs") or []) if str(ref).strip()]
    requester_refs = [str(ref) for ref in (config.get("requester_contact_refs") or []) if str(ref).strip()]
    return {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "generated_at": generated_at,
        "as_of": today.isoformat(),
        "client_ref": str(config.get("client_ref") or "capital_hilton"),
        "client_display_name": str(config.get("client_display_name") or "Capital Hilton"),
        "currency_iso": currency,
        "rate_minor_units_per_performance": rate,
        "purchase_orders": pos,
        "performances": {
            "total": len(performances),
            "performed_count": len(performed),
            "upcoming_count": len(performances) - len(performed),
            "invoiced_count": len(performed) - len(uninvoiced),
            "uninvoiced_count": len(uninvoiced),
            "uninvoiced": uninvoiced,
            "uninvoiced_value_minor_units": uninvoiced_value,
        },
        "capacity": {
            "open_po_remaining_minor_units": open_capacity,
            "shortfall_minor_units": shortfall,
        },
        "decision": {
            "needs_new_po": needs_new_po,
            "reason": reason,
            "recommended_po_performances": recommended_shows if needs_new_po else 0,
            "recommended_po_minor_units": recommended_minor_units if needs_new_po else 0,
            "threshold_uninvoiced": threshold,
        },
        "contacts": {
            "ap": _contact_lines(ap_refs, resolver),
            "requester": _contact_lines(requester_refs, resolver),
        },
        "notes": [str(note) for note in (config.get("notes") or [])],
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "machine_proof": {
            "prepared_only": True,
            "draft_written": False,
            "attention_event_emitted": False,
            "email_send_performed": False,
            "coupa_access_performed": False,
            "ledger_mutation_performed": False,
        },
    }


def render_po_request_eml(payload: Mapping[str, Any]) -> str:
    """A plain local .eml the operator reads and sends by hand. Never sent by the machine."""
    decision = payload["decision"]
    currency = str(payload["currency_iso"])
    rate = int(payload["rate_minor_units_per_performance"])
    ap = list(payload["contacts"]["ap"])
    requester = list(payload["contacts"]["requester"])
    to_header = ", ".join(f"{c['name']} <{c['email']}>" if c["email_known"] else f"{c['name']}" for c in ap) or "(AP contact)"
    cc_header = ", ".join(f"{c['name']} <{c['email']}>" if c["email_known"] else f"{c['name']}" for c in requester)
    shows = int(decision["recommended_po_performances"])
    amount = int(decision["recommended_po_minor_units"])
    uninvoiced = list(payload["performances"]["uninvoiced"])
    exhausted = [row["po_number"] for row in payload["purchase_orders"] if row["status"] == "exhausted"]
    lines = [
        "X-OpenClaw-Draft: prepared_only; send_hold=locked; provider_send=never",
        "X-OpenClaw-Read-Model: " + READ_MODEL_ID,
        f"X-OpenClaw-To-Contact-Refs: {', '.join(c['contact_ref'] for c in ap)}",
        f"To: {to_header}",
    ]
    if cc_header:
        lines.append(f"Cc: {cc_header}")
    lines.extend(
        [
            f"Subject: Purchase order request: Capital Hilton live music, {shows} performances",
            "MIME-Version: 1.0",
            "Content-Type: text/plain; charset=utf-8",
            "",
            "Hi " + (ap[0]["name"].split(" ")[0] if ap else "there") + ",",
            "",
            f"Could you open a new purchase order for live music at the Capital Hilton? "
            f"The last PO{'s' if len(exhausted) > 1 else ''} ({', '.join(exhausted) or 'on file'}) "
            f"{'are' if len(exhausted) > 1 else 'is'} fully invoiced.",
            "",
            f"Requested: {shows} performances at {_dollars(rate, currency)} each, total {_dollars(amount, currency)}.",
        ]
    )
    if uninvoiced:
        lines.append("")
        lines.append("Performances already delivered and waiting on a PO to invoice against:")
        for row in uninvoiced:
            desc = f" ({row['description']})" if row.get("description") else ""
            lines.append(f"- {row['date']}{desc}")
    lines.extend(
        [
            "",
            "Once the PO number is issued I will invoice against it through Coupa as before.",
            "",
            "Thank you,",
            "Winship",
            "",
        ]
    )
    return "\n".join(lines)


def _attention_event(payload: Mapping[str, Any], *, draft_path: str) -> dict[str, Any]:
    decision = payload["decision"]
    currency = str(payload["currency_iso"])
    return {
        "event_id": f"capital_hilton_po_cycle:{payload['as_of']}",
        "schema_version": ATTENTION_SCHEMA_VERSION,
        "generated_at": payload["generated_at"],
        "target_surface": "operator_attention_lane",
        "headline": "Capital Hilton needs a new purchase order",
        "operator_message": (
            f"{payload['performances']['uninvoiced_count']} performance(s) are waiting on a PO. "
            f"I drafted the request to AP for {decision['recommended_po_performances']} performances "
            f"({_dollars(int(decision['recommended_po_minor_units']), currency)}). Read the draft, then send it yourself."
        ),
        "client_ref": payload["client_ref"],
        "draft_path": draft_path,
        "proof_refs": [f"generated/read_models/{READ_MODEL_ID}.json"],
        "telegram_nudge": {"would_notify_operator": True, "telegram_send_performed": False, "send_hold_locked": True},
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "machine_proof": {
            "prepared_only": True,
            "operator_surface_emitted": True,
            "email_send_performed": False,
            "telegram_send_performed": False,
            "ledger_mutation_performed": False,
            "business_action_performed": False,
        },
    }


def _write_attention(path: Path, events: list[dict[str, Any]], *, generated_at: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        stable_json(
            {
                "schema_version": ATTENTION_SCHEMA_VERSION,
                "read_model_id": f"{READ_MODEL_ID}_attention",
                "generated_at": generated_at,
                "status": "CAPITAL_HILTON_PO_REQUEST_READY" if events else "IDLE",
                "events": sorted(events, key=lambda row: str(row.get("event_id") or "")),
                "machine_proof": {
                    "operator_attention_lane_surface": True,
                    "email_send_performed": False,
                    "telegram_send_performed": False,
                    "ledger_mutation_performed": False,
                    "unsafe_true_grants_absent": True,
                },
            }
        ),
        encoding="utf-8",
    )


def format_operator_markdown(payload: Mapping[str, Any]) -> str:
    currency = str(payload["currency_iso"])
    decision = payload["decision"]
    perf = payload["performances"]
    lines = ["Capital Hilton PO Cycle v0", "", f"As of: `{payload['as_of']}`", ""]
    lines.append("Purchase orders:")
    for row in payload["purchase_orders"]:
        cap = _dollars(row["cap_minor_units"], currency) if row["cap_minor_units"] is not None else "unknown cap"
        lines.append(f"- `{row['po_number']}`: {row['status']}; {_dollars(row['invoiced_minor_units'], currency)} invoiced of {cap}; {_dollars(row['remaining_minor_units'], currency)} left.")
    if not payload["purchase_orders"]:
        lines.append("- none on file")
    lines.append("")
    lines.append(
        f"Performances: {perf['performed_count']} performed, {perf['invoiced_count']} invoiced, {perf['uninvoiced_count']} waiting "
        f"({_dollars(perf['uninvoiced_value_minor_units'], currency)}), {perf['upcoming_count']} upcoming."
    )
    lines.append(f"Decision: {'NEW PO NEEDED' if decision['needs_new_po'] else 'no PO request'}. {decision['reason']}")
    draft = payload.get("draft") or {}
    if draft.get("path"):
        lines.append(f"Draft: `{draft['path']}` (read it, then send it yourself; the machine never sends).")
    lines.append("")
    lines.append("Boundary: prepare-only; Coupa and sending stay manual; no money moved, nothing marked paid.")
    return "\n".join(lines) + "\n"


def export_po_cycle(
    *,
    config_path: str | Path = DEFAULT_CONFIG_PATH,
    export_root: str | Path = DEFAULT_EXPORT_ROOT,
    draft_root: str | Path = DEFAULT_DRAFT_ROOT,
    today: date | None = None,
    generated_at: str | None = None,
    contact_resolver: ContactResolver | None = None,
) -> dict[str, Any]:
    config = load_config(config_path)
    payload = build_po_cycle(config, today=today, generated_at=generated_at, contact_resolver=contact_resolver)
    root = Path(export_root)
    root.mkdir(parents=True, exist_ok=True)
    drafts = Path(draft_root)
    attention_path = root / f"{READ_MODEL_ID}_attention.json"
    events: list[dict[str, Any]] = []
    payload["draft"] = None
    if payload["decision"]["needs_new_po"]:
        drafts.mkdir(parents=True, exist_ok=True)
        draft_path = drafts / f"CAPITAL_HILTON_PO_REQUEST_DRAFT_{payload['as_of']}.eml"
        draft_path.write_text(render_po_request_eml(payload), encoding="utf-8")
        payload["draft"] = {
            "path": str(draft_path),
            "to_contact_refs": [c["contact_ref"] for c in payload["contacts"]["ap"]],
            "send_performed": False,
        }
        payload["machine_proof"]["draft_written"] = True
        events.append(_attention_event(payload, draft_path=str(draft_path)))
        payload["machine_proof"]["attention_event_emitted"] = True
    _write_attention(attention_path, events, generated_at=payload["generated_at"])
    json_path = root / f"{READ_MODEL_ID}.json"
    operator_path = root / f"{READ_MODEL_ID}_OPERATOR.md"
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(format_operator_markdown(payload), encoding="utf-8")
    return {
        "json_path": str(json_path),
        "operator_path": str(operator_path),
        "attention_path": str(attention_path),
        "draft_path": (payload["draft"] or {}).get("path"),
        "needs_new_po": payload["decision"]["needs_new_po"],
        "uninvoiced_count": payload["performances"]["uninvoiced_count"],
    }
