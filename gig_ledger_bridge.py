"""Gig ledger bridge: a gig said out loud becomes ledger facts the money truth can see.

"Dane asked me to play Oct 17 at 49 West for $500" becomes one GigRecord (active), one draft
InvoiceRecord, and one open ExpectedReceivableRecord in the Gig-to-Cash store. The receivable
is due on the service date (pay on the night) unless terms_days says otherwise, so the row lands
in the service month of receivables_month_bounded the next time that export runs.

Dry-run by default. apply=True writes local ledger facts only: expected cash. Nothing here
moves money, marks anything paid, sends anything, or calls a model. Deterministic ids and
idempotency keys make the same sentence a no-op on repeat, never a duplicate.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Callable, Mapping

from ar_expected_receivable_record import ExpectedReceivableRecord
from ar_gig_record import GigRecord
from ar_gig_to_cash_store import DEFAULT_DB_PATH, GigToCashStore, IdempotencyConflict
from ar_invoice_record import InvoiceRecord

try:  # the same resolver the capture path uses; fail closed to a bare parser if absent
    from gig_capture import DEFAULT_CLIENT_MODELS, _resolve_date as _capture_resolve_date
except Exception:  # pragma: no cover - defensive import
    DEFAULT_CLIENT_MODELS = {}
    _capture_resolve_date = None

try:
    from receivables_month_bounded import _CLIENT_ALIAS_TO_REF, _CLIENT_DISPLAY_NAMES
except Exception:  # pragma: no cover - defensive import
    _CLIENT_ALIAS_TO_REF = {}
    _CLIENT_DISPLAY_NAMES = {}

SCHEMA_VERSION = "gig_ledger_bridge_v0"
BILLING_ENTITY_REF = "billing_entity:winship"
DEFAULT_TIMEZONE = "America/New_York"
DEFAULT_CURRENCY = "USD"
MONEY_SOURCE_REFRESH = "python3 scripts/export_receivables_month_bounded.py"

AUTHORITY_BOUNDARY = {
    "money_movement_performed": False,
    "paid_marking_performed": False,
    "send_performed": False,
    "email_send_performed": False,
    "telegram_send_performed": False,
    "calendar_write_performed": False,
    "bank_access_performed": False,
    "external_model_called": False,
}

_ASKED_RE = re.compile(
    r"^(?P<who>[A-Za-z][A-Za-z.' -]{0,80}?)\s+asked\s+me\s+to\s+(?P<body>.+)$",
    re.IGNORECASE,
)
_AMOUNT_RE = re.compile(r"\bfor\s+\$\s*(?P<amount>[0-9][0-9,]*(?:\.[0-9]{1,2})?)\b|\$\s*(?P<bare>[0-9][0-9,]*(?:\.[0-9]{1,2})?)\b")
_MONTH_WORDS = r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*"
_DATE_RE = re.compile(
    r"\b(?P<date>"
    r"(?:20\d{2}-\d{1,2}-\d{1,2})"
    r"|(?:(?:next|this)\s+[A-Za-z]+)"
    rf"|(?:{_MONTH_WORDS}\.?\s+\d{{1,2}}(?:st|nd|rd|th)?(?:,\s*20\d{{2}})?)"
    r"|today|tomorrow"
    r"|(?:the\s+\d{1,2}(?:st|nd|rd|th))"
    r")\b",
    re.IGNORECASE,
)
_VENUE_RE = re.compile(
    r"\bat\s+(?P<venue>[A-Za-z0-9][A-Za-z0-9&.' -]{0,60}?)(?=\s+for\s+\$|\s+on\s+|\s*,|\s*$)",
    re.IGNORECASE,
)


class GigTextError(ValueError):
    """The sentence is not a gig the bridge can read."""


@dataclass(frozen=True)
class GigIntent:
    contact_hint: str
    description: str
    venue: str
    date_text: str
    amount_minor_units: int | None


@dataclass(frozen=True)
class ResolvedGig:
    client_ref: str
    client_display_name: str
    service_date: str
    due_date: str
    description: str
    venue: str
    amount_minor_units: int
    currency_iso: str
    contact_hint: str
    resolution: str  # override | contact
    venue_note: str = ""


def _clean(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _slug(value: object) -> str:
    text = re.sub(r"[^a-z0-9]+", "_", _clean(value).lower()).strip("_")
    return text or "unknown"


def _minor_units(text: str) -> int | None:
    try:
        value = Decimal(text.replace(",", ""))
    except (InvalidOperation, AttributeError):
        return None
    return int((value * 100).to_integral_value())


def money_client_ref(slug_or_name: str) -> str:
    slug = _slug(slug_or_name)
    return str(_CLIENT_ALIAS_TO_REF.get(slug, slug))


def _client_display(client_ref: str, fallback: str = "") -> str:
    if client_ref in _CLIENT_DISPLAY_NAMES:
        return str(_CLIENT_DISPLAY_NAMES[client_ref])
    dashed = client_ref.replace("_", "-")
    model = DEFAULT_CLIENT_MODELS.get(dashed) or {}
    if model.get("display_name"):
        return str(model["display_name"])
    if fallback:
        return _clean(fallback)
    return " ".join(part.capitalize() for part in client_ref.split("_"))


def _client_rate_minor_units(client_ref: str) -> int | None:
    model = DEFAULT_CLIENT_MODELS.get(client_ref.replace("_", "-")) or {}
    rate = model.get("rate")
    if rate is None:
        return None
    return _minor_units(str(rate))


def interpret_gig_text(text: str) -> GigIntent:
    """Read '<who> asked me to <what> [on] <date> [at <venue>] [for $<amount>]'."""
    cleaned = _clean(text)
    match = _ASKED_RE.match(cleaned)
    if not match:
        raise GigTextError("Could not read a gig from that sentence; expected '<who> asked me to <what> <date> ...'.")
    who = _clean(match.group("who"))
    body = _clean(match.group("body"))
    date_match = _DATE_RE.search(body)
    if not date_match:
        raise GigTextError("Could not find the gig date; say a date like 'Oct 17', '2026-10-17', 'tomorrow', or 'next Friday'.")
    amount_match = _AMOUNT_RE.search(body)
    amount = None
    if amount_match:
        amount = _minor_units(amount_match.group("amount") or amount_match.group("bare") or "")
    remainder = body
    remainder = remainder[: date_match.start()] + " " + remainder[date_match.end():]
    if amount_match:
        remainder = remainder.replace(amount_match.group(0), " ")
    venue_match = _VENUE_RE.search(_clean(remainder))
    venue = _clean(venue_match.group("venue")) if venue_match else ""
    if venue_match:
        remainder = _clean(remainder).replace(venue_match.group(0), " ")
    description = re.sub(r"\b(?:on|for)\s*$", "", _clean(remainder)).strip(" ,.")
    if not description:
        description = "gig"
    return GigIntent(
        contact_hint=who,
        description=_clean(description),
        venue=venue,
        date_text=_clean(date_match.group("date")),
        amount_minor_units=amount,
    )


def _resolve_date(date_text: str, *, now: datetime) -> str:
    if _capture_resolve_date is None:
        return date.fromisoformat(date_text).isoformat()
    return _capture_resolve_date(date_text, now=now)


def resolve_gig(
    intent: GigIntent,
    *,
    now: datetime,
    registry: Any = None,
    client_ref: str | None = None,
    client_name: str | None = None,
    amount_minor_units: int | None = None,
    terms_days: int = 0,
) -> ResolvedGig | dict[str, Any]:
    """Turn an intent into a fully specified gig, or a dict naming exactly what is missing."""
    try:
        service_date = _resolve_date(intent.date_text, now=now)
    except ValueError as exc:
        return {"status": "needs_date", "reason": str(exc), "date_text": intent.date_text}

    resolution = ""
    ref = ""
    display = ""
    if client_ref:
        ref = money_client_ref(client_ref)
        display = _client_display(ref, client_name or "")
        resolution = "override"
    else:
        contact = None
        if registry is not None:
            try:
                contact = registry.get_contact(intent.contact_hint)
            except Exception:
                contact = None
        options = tuple((contact or {}).get("connected_client") or ())
        if contact and len(options) == 1:
            ref = money_client_ref(options[0])
            display = _client_display(ref, client_name or "")
            resolution = "contact"
        elif contact and len(options) > 1:
            return {
                "status": "needs_client",
                "reason": f"{intent.contact_hint} is connected to more than one client; pass --client.",
                "client_options": [money_client_ref(option) for option in options],
            }
        else:
            hint = intent.venue or intent.contact_hint
            return {
                "status": "needs_client",
                "reason": f"No client on file for '{intent.contact_hint}'.",
                "suggested_client_ref": _slug(hint),
                "suggested_client_name": _clean(hint),
                "hint": f'Re-run with --client {_slug(hint)} --client-name "{_clean(hint)}" to land it under that name.',
            }

    amount = amount_minor_units if amount_minor_units is not None else intent.amount_minor_units
    if amount is None:
        amount = _client_rate_minor_units(ref)
    if amount is None or amount <= 0:
        return {
            "status": "needs_amount",
            "reason": f"No amount in the sentence and no default rate for {display}; pass --amount.",
            "client_ref": ref,
        }

    due = date.fromisoformat(service_date) + timedelta(days=max(0, int(terms_days)))
    venue_note = ""
    if resolution == "contact" and intent.venue and _slug(intent.venue) != ref and _slug(intent.venue) not in display.lower().replace(" ", "_"):
        venue_note = (
            f"Client came from contact '{intent.contact_hint}' ({display}); the sentence names venue '{intent.venue}'. "
            f"If the venue is the payer, re-run with --client {_slug(intent.venue)} --client-name \"{_clean(intent.venue)}\"."
        )
    return ResolvedGig(
        client_ref=ref,
        client_display_name=display,
        service_date=service_date,
        due_date=due.isoformat(),
        description=intent.description,
        venue=intent.venue,
        amount_minor_units=int(amount),
        currency_iso=DEFAULT_CURRENCY,
        contact_hint=intent.contact_hint,
        resolution=resolution,
        venue_note=venue_note,
    )


@dataclass(frozen=True)
class LandingPlan:
    landing_id: str
    gig: GigRecord
    invoice: InvoiceRecord
    receivable: ExpectedReceivableRecord


def landing_id_for(resolved: ResolvedGig) -> str:
    key = "|".join([resolved.client_ref, resolved.service_date, _slug(resolved.description), _slug(resolved.venue)])
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]


def plan_records(resolved: ResolvedGig, *, now: datetime, source_text: str) -> LandingPlan:
    landing = landing_id_for(resolved)
    source_ref = f"gig_ledger_bridge:{landing}:{hashlib.sha256(_clean(source_text).encode('utf-8')).hexdigest()[:12]}"
    title = resolved.description if not resolved.venue else f"{resolved.description} at {resolved.venue}"
    gig = GigRecord(
        gig_id=f"gig:land:{landing}",
        counterparty_ref=resolved.client_ref,
        counterparty_name=resolved.client_display_name,
        lifecycle_state="active",
        timezone=DEFAULT_TIMEZONE,
        billing_policy_ref=f"billing_policy:{resolved.client_ref}:per_show",
        idempotency_key=f"land_gig:gig:{landing}",
        scheduled_start_iso=f"{resolved.service_date}T00:00:00",
        scheduled_end_iso=None,
    )
    invoice = InvoiceRecord(
        invoice_id=f"inv:land:{landing}",
        invoice_version_id=f"inv_ver:land:{landing}:1",
        counterparty_ref=resolved.client_ref,
        billing_entity_ref=BILLING_ENTITY_REF,
        lifecycle_state="draft",
        idempotency_key=f"land_gig:invoice:{landing}",
        source_ref=f"{source_ref}:{_slug(title)[:48]}",
        currency_iso=resolved.currency_iso,
        total_minor_units=resolved.amount_minor_units,
        due_date_iso=resolved.due_date,
    )
    receivable = ExpectedReceivableRecord(
        receivable_id=f"recv:land:{landing}",
        receivable_version_id=f"recv_ver:land:{landing}:1",
        invoice_id=invoice.invoice_id,
        invoice_version_id=invoice.invoice_version_id,
        counterparty_ref=resolved.client_ref,
        lifecycle_state="open",
        expected_minor_units=resolved.amount_minor_units,
        currency_iso=resolved.currency_iso,
        due_date_iso=resolved.due_date,
        recognized_utc_iso=now.astimezone(timezone.utc).replace(microsecond=0).isoformat(),
        idempotency_key=f"land_gig:receivable:{landing}",
        source_ref=invoice.source_ref,
    )
    return LandingPlan(landing_id=landing, gig=gig, invoice=invoice, receivable=receivable)


def _record_dict(record: Any) -> dict[str, Any]:
    return {key: value for key, value in asdict(record).items()}


def write_plan(plan: LandingPlan, *, db_path: str | Path) -> dict[str, Any]:
    """Append the three records. Returns what was created; a repeat is a no-op."""
    with GigToCashStore(str(db_path)) as store:
        if store.get_current(GigRecord, plan.gig.gig_id) is not None:
            return {"status": "already_landed", "created": [], "gig_id": plan.gig.gig_id}
        created: list[str] = []
        try:
            for record, label in ((plan.gig, "gig"), (plan.invoice, "invoice"), (plan.receivable, "receivable")):
                result = store.append(record)
                if result.created:
                    created.append(label)
        except IdempotencyConflict as exc:
            return {"status": "conflict", "created": created, "reason": str(exc)}
    return {"status": "landed", "created": created, "gig_id": plan.gig.gig_id}


def land_gig(
    text: str,
    *,
    db_path: str | Path = DEFAULT_DB_PATH,
    apply: bool = False,
    now: datetime | None = None,
    registry: Any = None,
    registry_factory: Callable[[], Any] | None = None,
    client_ref: str | None = None,
    client_name: str | None = None,
    amount_dollars: str | None = None,
    terms_days: int = 0,
) -> dict[str, Any]:
    """Read the sentence, resolve the client and amount, plan the three records, and (with apply) write them."""
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    base = {
        "schema_version": SCHEMA_VERSION,
        "source_text": _clean(text),
        "apply_requested": bool(apply),
        "db_path": str(db_path),
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "machine_proof": {"ledger_fact_write_performed": False, "records_created": []},
    }
    try:
        intent = interpret_gig_text(text)
    except GigTextError as exc:
        return {**base, "status": "needs_clarify", "reason": str(exc)}
    base["intent"] = asdict(intent)

    if registry is None and registry_factory is not None:
        try:
            registry = registry_factory()
        except Exception:
            registry = None
    if registry is None and client_ref is None:
        try:
            from contacts_registry import ContactsRegistry

            registry = ContactsRegistry()
        except Exception:
            registry = None

    amount_override = _minor_units(str(amount_dollars)) if amount_dollars else None
    resolved = resolve_gig(
        intent,
        now=now,
        registry=registry,
        client_ref=client_ref,
        client_name=client_name,
        amount_minor_units=amount_override,
        terms_days=terms_days,
    )
    if isinstance(resolved, dict):
        return {**base, **resolved}

    plan = plan_records(resolved, now=now, source_text=text)
    result = {
        **base,
        "status": "ready",
        "resolved": asdict(resolved),
        "landing_id": plan.landing_id,
        "records": {
            "gig": _record_dict(plan.gig),
            "invoice": _record_dict(plan.invoice),
            "receivable": _record_dict(plan.receivable),
        },
        "money_source_month": resolved.due_date[:7],
        "follow_through": [
            f"{MONEY_SOURCE_REFRESH}  # refresh the ONE money source so the row shows the same day",
            "python3 scripts/export_open_ar_aging.py  # the aging line in the brief picks it up",
        ],
    }
    if not apply:
        result["status"] = "dry_run"
        return result
    outcome = write_plan(plan, db_path=db_path)
    result["status"] = outcome["status"]
    result["machine_proof"] = {
        "ledger_fact_write_performed": bool(outcome.get("created")),
        "records_created": list(outcome.get("created") or []),
    }
    if outcome.get("reason"):
        result["reason"] = outcome["reason"]
    return result


def _dollars(minor_units: int, currency: str = DEFAULT_CURRENCY) -> str:
    prefix = "$" if currency == "USD" else f"{currency} "
    whole, cents = divmod(int(minor_units), 100)
    return f"{prefix}{whole:,}" if cents == 0 else f"{prefix}{whole:,}.{cents:02d}"


def format_operator_markdown(result: Mapping[str, Any]) -> str:
    lines = ["Gig Ledger Bridge v0", ""]
    status = str(result.get("status") or "")
    lines.append(f"Status: `{status}`")
    resolved = result.get("resolved") if isinstance(result.get("resolved"), Mapping) else None
    if resolved:
        title = resolved["description"] if not resolved.get("venue") else f"{resolved['description']} at {resolved['venue']}"
        lines.append(
            f"{resolved['client_display_name']}: {title} on {resolved['service_date']} for "
            f"{_dollars(int(resolved['amount_minor_units']), str(resolved['currency_iso']))}, due {resolved['due_date']}."
        )
        lines.append(f"Landing id: `{result.get('landing_id')}`  Money month: `{result.get('money_source_month')}`  Client via: `{resolved.get('resolution')}`")
        if resolved.get("venue_note"):
            lines.append(f"Check: {resolved['venue_note']}")
        created = list((result.get("machine_proof") or {}).get("records_created") or [])
        if status == "dry_run":
            lines.append("Dry run: nothing written. Re-run with --apply to write gig, draft invoice, and open receivable.")
        elif status == "landed":
            lines.append(f"Written: {', '.join(created)}.")
        elif status == "already_landed":
            lines.append("Already in the ledger; nothing written.")
        elif status == "conflict":
            lines.append(f"Not written: {result.get('reason')}")
        if status in {"landed", "already_landed"}:
            lines.append("")
            lines.append("Next:")
            for step in result.get("follow_through") or []:
                lines.append(f"- `{step}`")
    else:
        lines.append(str(result.get("reason") or ""))
        if result.get("hint"):
            lines.append(str(result["hint"]))
    lines.append("")
    lines.append("Boundary: local ledger facts only; no money moved, nothing marked paid, nothing sent.")
    return "\n".join(lines) + "\n"


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False, default=str) + "\n"
