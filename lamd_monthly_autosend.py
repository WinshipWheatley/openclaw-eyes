"""Bounded monthly auto-send transaction for the fixed LAMD speaker-rental surface.

The live provider is injected. Importing this module cannot draft, send, move money,
change an authority gate, or touch the production ledger.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Protocol

from ar_expected_receivable_record import ExpectedReceivableRecord
from ar_gig_to_cash_store import GigToCashStore
from ar_invoice_record import InvoiceRecord


CLIENT_REF = "live_arts_md"
STREAM = "speaker_rental"
RECIPIENT = "Accountant@liveartsmd.org"
AMOUNT_MINOR_UNITS = 10_000
CURRENCY = "USD"
ELIGIBLE_DAY = 16


class PackageDriftError(ValueError):
    """The prepared package is outside the operator-graduated fixed surface."""


class ProviderOutcomeUnknown(RuntimeError):
    """The provider may have accepted the send; automatic retry is forbidden."""


@dataclass(frozen=True)
class GuardDecision:
    allowed: bool
    reason: str
    generation: int = 0


@dataclass(frozen=True)
class AutosendPolicy:
    armed: bool
    operator_stop: bool


class FreezeGuardLike(Protocol):
    def check(self, operation: str) -> GuardDecision: ...


class ProviderLike(Protocol):
    def send(self, package: dict[str, Any], *, cycle_key: str) -> dict[str, Any]: ...


class LedgerLike(Protocol):
    def post(self, package: dict[str, Any], receipt: dict[str, Any]) -> dict[str, Any]: ...


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _parse_time(value: str) -> datetime:
    result = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if result.tzinfo is None:
        raise ValueError("provider sent_at must be timezone-aware")
    return result.astimezone(timezone.utc)


def validate_package(package: Mapping[str, Any]) -> dict[str, Any]:
    value = dict(package)
    exact = {
        "schema_version": "lamd_monthly_autosend_package_v1",
        "client_ref": CLIENT_REF,
        "stream": STREAM,
        "source_stream": STREAM,
        "amount_minor_units": AMOUNT_MINOR_UNITS,
        "currency": CURRENCY,
        "recipient": RECIPIENT,
        "status": "finalized_validated",
    }
    drift = {
        key: {"expected": expected, "observed": value.get(key)}
        for key, expected in exact.items()
        if value.get(key) != expected
    }
    if drift:
        raise PackageDriftError("fixed LAMD surface drift: " + _stable_json(drift))
    month = str(value.get("service_month") or "")
    try:
        month_start = datetime.strptime(month, "%Y-%m").date().replace(day=1)
    except ValueError as exc:
        raise PackageDriftError("service_month must be YYYY-MM") from exc
    if value.get("service_period_start") != month_start.isoformat():
        raise PackageDriftError("service period does not start in the bound month")
    if not str(value.get("source_sheet") or "").strip():
        raise PackageDriftError("source_sheet is required")
    if not str(value.get("invoice_number") or "").strip():
        raise PackageDriftError("invoice number is required")
    for path_key, sha_key, suffix in (
        ("source_workbook_path", "source_workbook_sha256", ".xlsx"),
        ("pdf_path", "pdf_sha256", ".pdf"),
    ):
        path = Path(str(value.get(path_key) or ""))
        expected_sha = str(value.get(sha_key) or "").lower()
        if not path.is_file() or path.suffix.casefold() != suffix:
            raise PackageDriftError(f"{path_key} is not a present {suffix} artifact")
        if _sha256_file(path) != expected_sha:
            raise PackageDriftError(f"{path_key} hash changed")
    material = {key: value[key] for key in sorted(value) if key != "package_sha256"}
    observed_hash = hashlib.sha256(_stable_json(material).encode("utf-8")).hexdigest()
    if observed_hash != str(value.get("package_sha256") or "").lower():
        raise PackageDriftError("package binding hash changed")
    return value


class LamdMonthlyCycleStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)

    def _connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.path, timeout=30, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=FULL")
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS monthly_cycles (
              client_ref TEXT NOT NULL,
              stream TEXT NOT NULL,
              cycle_month TEXT NOT NULL,
              cycle_key TEXT NOT NULL UNIQUE,
              package_sha256 TEXT NOT NULL,
              status TEXT NOT NULL,
              detail_json TEXT NOT NULL,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              UNIQUE(client_ref, stream, cycle_month)
            );
            CREATE TABLE IF NOT EXISTS refusal_events (
              event_id TEXT PRIMARY KEY,
              cycle_key TEXT NOT NULL,
              reason TEXT NOT NULL,
              detail_json TEXT NOT NULL,
              created_at TEXT NOT NULL
            );
            """
        )
        return conn

    def record_refusal(self, cycle_key: str, reason: str, detail: Mapping[str, Any], now: str) -> None:
        event_id = "lamd-refusal:" + hashlib.sha256(
            f"{cycle_key}|{reason}|{now}|{_stable_json(detail)}".encode()
        ).hexdigest()[:24]
        with self._connect() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO refusal_events VALUES (?, ?, ?, ?, ?)",
                (event_id, cycle_key, reason, _stable_json(detail), now),
            )

    def claim(self, *, month: str, package_sha256: str, now: str) -> tuple[bool, dict[str, Any]]:
        cycle_key = f"{CLIENT_REF}:{STREAM}:{month}"
        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            existing = conn.execute(
                "SELECT * FROM monthly_cycles WHERE client_ref=? AND stream=? AND cycle_month=?",
                (CLIENT_REF, STREAM, month),
            ).fetchone()
            if existing is not None:
                conn.execute("COMMIT")
                return False, dict(existing)
            detail = {"provider_called": False, "queued_for_release": False}
            conn.execute(
                "INSERT INTO monthly_cycles VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    CLIENT_REF,
                    STREAM,
                    month,
                    cycle_key,
                    package_sha256,
                    "CLAIMED",
                    _stable_json(detail),
                    now,
                    now,
                ),
            )
            conn.execute("COMMIT")
            return True, {"cycle_key": cycle_key, "status": "CLAIMED", "detail_json": _stable_json(detail)}
        except Exception:
            if conn.in_transaction:
                conn.execute("ROLLBACK")
            raise
        finally:
            conn.close()

    def mark(self, cycle_key: str, status: str, detail: Mapping[str, Any], now: str) -> None:
        with self._connect() as conn:
            changed = conn.execute(
                "UPDATE monthly_cycles SET status=?, detail_json=?, updated_at=? WHERE cycle_key=?",
                (status, _stable_json(detail), now, cycle_key),
            ).rowcount
        if changed != 1:
            raise RuntimeError("monthly cycle claim disappeared")

    def cycle_count(self) -> int:
        with self._connect() as conn:
            return int(conn.execute("SELECT COUNT(*) FROM monthly_cycles").fetchone()[0])


def _refusal(
    *,
    store: LamdMonthlyCycleStore,
    cycle_key: str,
    status: str,
    reason: str,
    now: str,
    decision: GuardDecision | None = None,
) -> dict[str, Any]:
    detail = {
        "status": status,
        "reason": reason,
        "queued_for_release": False,
        "provider_called": False,
    }
    if decision is not None:
        detail["freeze_generation"] = decision.generation
    store.record_refusal(cycle_key, reason, detail, now)
    return detail


def _existing_result(row: Mapping[str, Any]) -> dict[str, Any]:
    status = str(row.get("status") or "")
    if status == "LEDGER_POSTED":
        result = "ALREADY_SENT_VERIFIED"
    elif status == "LEDGER_REPAIR_REQUIRED":
        result = "ALREADY_SENT_LEDGER_REPAIR_REQUIRED"
    else:
        result = "ALREADY_CLAIMED_NO_RETRY"
    return {"status": result, "cycle_key": row["cycle_key"], "provider_called": False}


def _verify_provider_receipt(receipt: Mapping[str, Any], package: Mapping[str, Any]) -> dict[str, Any]:
    value = dict(receipt)
    expected = {
        "status": "SENT_VERIFIED",
        "recipient": package["recipient"],
        "amount_minor_units": package["amount_minor_units"],
        "service_month": package["service_month"],
        "package_sha256": package["package_sha256"],
    }
    if any(value.get(key) != expected_value for key, expected_value in expected.items()):
        raise ProviderOutcomeUnknown("provider receipt did not match the immutable monthly package")
    if not str(value.get("message_id") or ""):
        raise ProviderOutcomeUnknown("provider receipt omitted message_id")
    _parse_time(str(value.get("sent_at") or ""))
    return value


def run_monthly_cycle(
    *,
    now: datetime,
    package: Mapping[str, Any],
    policy: AutosendPolicy,
    store: LamdMonthlyCycleStore,
    freeze_guard: FreezeGuardLike,
    send_hold_admission: Callable[[dict[str, Any]], Mapping[str, Any]],
    provider: ProviderLike,
    ledger: LedgerLike,
) -> dict[str, Any]:
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    now_utc = now.astimezone(timezone.utc)
    timestamp = now_utc.isoformat(timespec="seconds")
    bounded = validate_package(package)
    month = str(bounded["service_month"])
    cycle_key = f"{CLIENT_REF}:{STREAM}:{month}"
    current_month = now_utc.strftime("%Y-%m")
    if month < current_month:
        return {"status": "REFUSED_PRIOR_MONTH", "cycle_key": cycle_key, "provider_called": False}
    if month > current_month:
        return {"status": "NOT_ELIGIBLE", "cycle_key": cycle_key, "provider_called": False}
    if now_utc.day < ELIGIBLE_DAY:
        return {"status": "NOT_ELIGIBLE", "cycle_key": cycle_key, "provider_called": False}
    if not policy.armed:
        return _refusal(store=store, cycle_key=cycle_key, status="REFUSED_UNARMED", reason="autosend_unarmed", now=timestamp)
    if policy.operator_stop:
        return _refusal(store=store, cycle_key=cycle_key, status="REFUSED_OPERATOR_STOP", reason="operator_stop", now=timestamp)
    first_guard = freeze_guard.check("lamd_monthly_autosend_preclaim")
    if not first_guard.allowed:
        return _refusal(
            store=store,
            cycle_key=cycle_key,
            status="REFUSED_FLEET_FREEZE",
            reason=first_guard.reason,
            now=timestamp,
            decision=first_guard,
        )
    first_hold = dict(send_hold_admission(bounded))
    if first_hold.get("allowed") is not True:
        return _refusal(store=store, cycle_key=cycle_key, status="REFUSED_SEND_HOLD", reason="send_hold", now=timestamp)
    claimed, row = store.claim(month=month, package_sha256=bounded["package_sha256"], now=timestamp)
    if not claimed:
        return _existing_result(row)
    final_guard = freeze_guard.check("lamd_monthly_autosend_provider_admission")
    if not final_guard.allowed:
        detail = _refusal(
            store=store,
            cycle_key=cycle_key,
            status="REFUSED_FLEET_FREEZE_NO_RETRY",
            reason=final_guard.reason,
            now=timestamp,
            decision=final_guard,
        )
        store.mark(cycle_key, detail["status"], detail, timestamp)
        return detail
    final_hold = dict(send_hold_admission(bounded))
    if final_hold.get("allowed") is not True:
        detail = {"status": "REFUSED_SEND_HOLD_NO_RETRY", "provider_called": False, "queued_for_release": False}
        store.mark(cycle_key, detail["status"], detail, timestamp)
        return detail
    try:
        raw_receipt = provider.send(bounded, cycle_key=cycle_key)
        receipt = _verify_provider_receipt(raw_receipt, bounded)
    except ProviderOutcomeUnknown as exc:
        detail = {"status": "UNKNOWN_OUTCOME", "error": str(exc), "provider_called": True, "retry_allowed": False}
        store.mark(cycle_key, detail["status"], detail, timestamp)
        return detail
    except Exception as exc:
        detail = {"status": "SEND_FAILED_NO_RETRY", "error": f"{type(exc).__name__}: {exc}", "provider_called": True, "retry_allowed": False}
        store.mark(cycle_key, detail["status"], detail, timestamp)
        return detail
    sent_detail = {"status": "SENT_VERIFIED", "provider_called": True, "provider_receipt": receipt}
    store.mark(cycle_key, "SENT_VERIFIED", sent_detail, timestamp)
    try:
        ledger_result = ledger.post(bounded, receipt)
    except Exception as exc:
        detail = {
            **sent_detail,
            "status": "LEDGER_REPAIR_REQUIRED",
            "ledger_error": f"{type(exc).__name__}: {exc}",
            "resend_allowed": False,
        }
        store.mark(cycle_key, detail["status"], detail, timestamp)
        return detail
    detail = {**sent_detail, "status": "LEDGER_POSTED", "ledger": dict(ledger_result)}
    store.mark(cycle_key, detail["status"], detail, timestamp)
    return detail


def post_sent_receivable(
    package: Mapping[str, Any],
    provider_receipt: Mapping[str, Any],
    *,
    db_path: str | Path,
) -> dict[str, bool]:
    bounded = validate_package(package)
    receipt = _verify_provider_receipt(provider_receipt, bounded)
    receipt_sha = hashlib.sha256(_stable_json(receipt).encode("utf-8")).hexdigest()
    invoice_number = str(bounded["invoice_number"])
    invoice_id = f"inv:{CLIENT_REF}:{invoice_number}"
    version_token = receipt_sha[:16]
    invoice_version_id = f"inv_ver:{CLIENT_REF}:{invoice_number}:{version_token}"
    receivable_id = f"recv:{CLIENT_REF}:{invoice_number}"
    receivable_version_id = f"recv_ver:{CLIENT_REF}:{invoice_number}:open:{version_token}"
    sent_at = _parse_time(str(receipt["sent_at"]))
    issue_date = sent_at.date().isoformat()
    source_ref = f"sent_verified_receipt:sha256:{receipt_sha}:provider:{receipt['message_id']}"
    invoice = InvoiceRecord(
        invoice_id=invoice_id,
        invoice_version_id=invoice_version_id,
        counterparty_ref=CLIENT_REF,
        billing_entity_ref="winship_music",
        lifecycle_state="issued",
        idempotency_key=f"lamd:invoice:{invoice_number}:sent_verified:{receipt_sha}",
        source_ref=source_ref,
        invoice_number=invoice_number,
        issue_date_iso=issue_date,
        due_date_iso=issue_date,
        currency_iso=CURRENCY,
        total_minor_units=AMOUNT_MINOR_UNITS,
    )
    receivable = ExpectedReceivableRecord(
        receivable_id=receivable_id,
        receivable_version_id=receivable_version_id,
        invoice_id=invoice_id,
        invoice_version_id=invoice_version_id,
        counterparty_ref=CLIENT_REF,
        lifecycle_state="open",
        expected_minor_units=AMOUNT_MINOR_UNITS,
        currency_iso=CURRENCY,
        due_date_iso=issue_date,
        recognized_utc_iso=sent_at.isoformat(timespec="seconds"),
        idempotency_key=f"lamd:receivable:{invoice_number}:sent_verified:{receipt_sha}",
        source_ref=source_ref,
    )
    with GigToCashStore(str(db_path)) as store:
        invoice_result = store.append(invoice)
        receivable_result = store.append(receivable)
    return {
        "invoice_created": bool(invoice_result.created),
        "receivable_created": bool(receivable_result.created),
    }


class GigToCashLedgerAdapter:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)

    def post(self, package: dict[str, Any], receipt: dict[str, Any]) -> dict[str, Any]:
        return post_sent_receivable(package, receipt, db_path=self.db_path)


__all__ = [
    "AutosendPolicy",
    "GigToCashLedgerAdapter",
    "GuardDecision",
    "LamdMonthlyCycleStore",
    "PackageDriftError",
    "ProviderOutcomeUnknown",
    "post_sent_receivable",
    "run_monthly_cycle",
    "validate_package",
]
