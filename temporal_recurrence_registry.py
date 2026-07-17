"""Generic recurrence and paid-through scoping for client/domain workflows."""

from __future__ import annotations

import calendar
import re
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Mapping


@dataclass(frozen=True)
class RecurrenceModel:
    client_ref: str
    cadence: str
    active: bool = True
    day_of_month: int | None = None
    domain: str = "invoice"
    channel: str = ""


@dataclass(frozen=True)
class PaidUpState:
    client_ref: str
    status: str
    paid_through: date | None
    next_expected_invoice: date | None
    recurrence_cadence: str
    domain: str = "invoice"


DEFAULT_RECURRENCE_MODELS: dict[str, dict[str, Any]] = {
    "st_annes": {
        "domain": "invoice",
        "cadence": "monthly",
        "day_of_month": 1,
        "active": True,
    },
    "live_arts_md": {
        "domain": "invoice",
        "cadence": "monthly",
        "day_of_month": 16,
        "active": True,
    },
    "capital_hilton": {
        "domain": "invoice",
        "cadence": "per_event",
        "channel": "coupa",
        "active": True,
    },
}


def client_ref_slug(value: Any) -> str:
    text = str(value or "").casefold().replace("&", "and")
    return re.sub(r"[^a-z0-9]+", "_", text).strip("_")


def _coerce_date(value: date | datetime | str) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return datetime.fromisoformat(str(value)).date()


def _month_start_after(anchor: date, day_of_month: int) -> date:
    year = anchor.year
    month = anchor.month
    while True:
        last_day = calendar.monthrange(year, month)[1]
        candidate = date(year, month, min(day_of_month, last_day))
        if candidate > anchor:
            return candidate
        month += 1
        if month == 13:
            month = 1
            year += 1


class ClientRecurrenceRegistry:
    def __init__(self, models: Mapping[str, Mapping[str, Any]] | None = None):
        source = models if models is not None else DEFAULT_RECURRENCE_MODELS
        self._models = {
            client_ref_slug(key): self._coerce_model(key, model)
            for key, model in source.items()
            if isinstance(model, Mapping)
        }

    def _coerce_model(self, key: str, model: Mapping[str, Any]) -> RecurrenceModel:
        client_ref = client_ref_slug(model.get("client_ref") or key)
        cadence = str(model.get("cadence") or "unknown").strip().casefold()
        day = model.get("day_of_month")
        day_of_month = int(day) if day not in (None, "") else None
        return RecurrenceModel(
            client_ref=client_ref,
            cadence=cadence,
            active=bool(model.get("active", True)),
            day_of_month=day_of_month,
            domain=str(model.get("domain") or "invoice"),
            channel=str(model.get("channel") or ""),
        )

    def get(self, client_ref: Any) -> RecurrenceModel | None:
        return self._models.get(client_ref_slug(client_ref))

    def next_expected_invoice(self, client_ref: Any, *, after: date | datetime | str) -> date | None:
        model = self.get(client_ref)
        if model is None or not model.active:
            return None
        if model.cadence == "monthly":
            return _month_start_after(_coerce_date(after), model.day_of_month or 1)
        if model.cadence == "per_event":
            return None
        return None

    def paid_up_state(
        self,
        client_ref: Any,
        *,
        paid_through: date | datetime | str | None,
        now: date | datetime | str,
    ) -> PaidUpState:
        slug = client_ref_slug(client_ref)
        model = self.get(slug)
        cadence = model.cadence if model else "unknown"
        domain = model.domain if model else "invoice"
        paid_date = _coerce_date(paid_through) if paid_through is not None else None
        if paid_date is None:
            return PaidUpState(slug, "unknown_scope", None, None, cadence, domain=domain)
        next_due = self.next_expected_invoice(slug, after=paid_date)
        if next_due is not None and _coerce_date(now) >= next_due:
            status = "invoice_due"
        else:
            status = "paid_up_through"
        return PaidUpState(slug, status, paid_date, next_due, cadence, domain=domain)


DEFAULT_REGISTRY = ClientRecurrenceRegistry()


def next_expected_invoice(client_ref: Any, *, after: date | datetime | str) -> date | None:
    return DEFAULT_REGISTRY.next_expected_invoice(client_ref, after=after)


def paid_up_state(
    client_ref: Any,
    *,
    paid_through: date | datetime | str | None,
    now: date | datetime | str,
) -> PaidUpState:
    return DEFAULT_REGISTRY.paid_up_state(client_ref, paid_through=paid_through, now=now)


__all__ = [
    "ClientRecurrenceRegistry",
    "DEFAULT_RECURRENCE_MODELS",
    "PaidUpState",
    "RecurrenceModel",
    "client_ref_slug",
    "next_expected_invoice",
    "paid_up_state",
]
