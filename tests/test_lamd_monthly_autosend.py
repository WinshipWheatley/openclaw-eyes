from __future__ import annotations

import hashlib
import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import pytest

from lamd_monthly_autosend import (
    AutosendPolicy,
    GuardDecision,
    LamdMonthlyCycleStore,
    PackageDriftError,
    ProviderOutcomeUnknown,
    post_sent_receivable,
    run_monthly_cycle,
)


NOW = datetime(2026, 8, 16, 14, 0, tzinfo=timezone.utc)


class FakeGuard:
    def __init__(self, *decisions: bool):
        self.decisions = list(decisions or (True, True))
        self.calls: list[str] = []

    def check(self, operation: str) -> GuardDecision:
        self.calls.append(operation)
        allowed = self.decisions.pop(0) if self.decisions else True
        return GuardDecision(allowed, "freeze_not_applied" if allowed else "fleet_frozen", 7)


class FakeProvider:
    def __init__(self, outcome: str = "sent"):
        self.outcome = outcome
        self.calls: list[dict] = []

    def send(self, package: dict, *, cycle_key: str) -> dict:
        self.calls.append({"package": package, "cycle_key": cycle_key})
        if self.outcome == "unknown":
            raise ProviderOutcomeUnknown("provider response lost after dispatch")
        if self.outcome == "failed":
            raise RuntimeError("definitive provider refusal")
        return {
            "status": "SENT_VERIFIED",
            "message_id": "provider-msg-august",
            "recipient": package["recipient"],
            "amount_minor_units": package["amount_minor_units"],
            "service_month": package["service_month"],
            "package_sha256": package["package_sha256"],
            "sent_at": "2026-08-16T14:00:01+00:00",
        }


class FakeLedger:
    def __init__(self, fail: bool = False):
        self.fail = fail
        self.calls: list[tuple[dict, dict]] = []

    def post(self, package: dict, receipt: dict) -> dict:
        self.calls.append((package, receipt))
        if self.fail:
            raise RuntimeError("ledger temporarily unavailable")
        return {"invoice_created": True, "receivable_created": True}


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _package(tmp_path: Path, **changes) -> dict:
    workbook = tmp_path / "Speaker Rentals August 2026.xlsx"
    pdf = tmp_path / "invoice.pdf"
    workbook.write_bytes(b"speaker-rental-workbook")
    pdf.write_bytes(b"%PDF-1.4 bounded-test")
    package = {
        "schema_version": "lamd_monthly_autosend_package_v1",
        "client_ref": "live_arts_md",
        "stream": "speaker_rental",
        "source_stream": "speaker_rental",
        "service_month": "2026-08",
        "service_period_start": "2026-08-01",
        "service_period_end": "2026-08-31",
        "invoice_number": "2026-1005",
        "amount_minor_units": 10000,
        "currency": "USD",
        "recipient": "Accountant@liveartsmd.org",
        "source_workbook_path": str(workbook),
        "source_workbook_sha256": _sha(workbook),
        "source_sheet": "August 2026 Speaker Rental",
        "pdf_path": str(pdf),
        "pdf_sha256": _sha(pdf),
        "status": "finalized_validated",
    }
    package.update(changes)
    material = {key: package[key] for key in sorted(package) if key != "package_sha256"}
    package["package_sha256"] = hashlib.sha256(
        json.dumps(material, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return package


def _run(tmp_path: Path, *, package=None, guard=None, provider=None, ledger=None, now=NOW):
    store = LamdMonthlyCycleStore(tmp_path / "cycles.sqlite3")
    return run_monthly_cycle(
        now=now,
        package=package or _package(tmp_path),
        policy=AutosendPolicy(armed=True, operator_stop=False),
        store=store,
        freeze_guard=guard or FakeGuard(),
        send_hold_admission=lambda _package: {"allowed": True, "graduation_id": "test-only"},
        provider=provider or FakeProvider(),
        ledger=ledger or FakeLedger(),
    )


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("client_ref", "other_client"),
        ("stream", "av_tech"),
        ("source_stream", "av_tech"),
        ("amount_minor_units", 10001),
        ("currency", "EUR"),
        ("recipient", "other@example.com"),
        ("source_sheet", ""),
        ("status", "draft"),
    ),
)
def test_fixed_surface_drift_refuses_before_claim_or_provider(tmp_path: Path, field: str, value) -> None:
    package = _package(tmp_path, **{field: value})
    provider = FakeProvider()

    with pytest.raises(PackageDriftError):
        _run(tmp_path, package=package, provider=provider)

    assert provider.calls == []
    assert LamdMonthlyCycleStore(tmp_path / "cycles.sqlite3").cycle_count() == 0


def test_not_eligible_before_sixteenth_or_after_month_rollover(tmp_path: Path) -> None:
    provider = FakeProvider()
    early = _run(tmp_path, provider=provider, now=datetime(2026, 8, 15, tzinfo=timezone.utc))
    assert early["status"] == "NOT_ELIGIBLE"
    assert provider.calls == []

    september_package = _package(tmp_path, service_month="2026-08")
    late = _run(
        tmp_path,
        package=september_package,
        provider=provider,
        now=datetime(2026, 9, 16, tzinfo=timezone.utc),
    )
    assert late["status"] == "REFUSED_PRIOR_MONTH"
    assert provider.calls == []


def test_enabled_freeze_guard_is_checked_twice_and_tripped_precheck_does_not_queue(tmp_path: Path) -> None:
    guard = FakeGuard(False)
    provider = FakeProvider()

    result = _run(tmp_path, guard=guard, provider=provider)

    assert result["status"] == "REFUSED_FLEET_FREEZE"
    assert result["queued_for_release"] is False
    assert guard.calls == ["lamd_monthly_autosend_preclaim"]
    assert provider.calls == []
    assert LamdMonthlyCycleStore(tmp_path / "cycles.sqlite3").cycle_count() == 0


def test_brake_trip_at_last_admission_calls_provider_zero_and_terminals_claim(tmp_path: Path) -> None:
    guard = FakeGuard(True, False)
    provider = FakeProvider()

    first = _run(tmp_path, guard=guard, provider=provider)
    second = _run(tmp_path, provider=provider)

    assert first["status"] == "REFUSED_FLEET_FREEZE_NO_RETRY"
    assert first["queued_for_release"] is False
    assert guard.calls == ["lamd_monthly_autosend_preclaim", "lamd_monthly_autosend_provider_admission"]
    assert second["status"] == "ALREADY_CLAIMED_NO_RETRY"
    assert provider.calls == []


def test_atomic_monthly_claim_allows_exactly_one_provider_call_and_one_ledger_post(tmp_path: Path) -> None:
    provider = FakeProvider()
    ledger = FakeLedger()

    first = _run(tmp_path, provider=provider, ledger=ledger)
    second = _run(tmp_path, provider=provider, ledger=ledger)

    assert first["status"] == "LEDGER_POSTED"
    assert second["status"] == "ALREADY_SENT_VERIFIED"
    assert len(provider.calls) == 1
    assert len(ledger.calls) == 1
    assert provider.calls[0]["cycle_key"] == "live_arts_md:speaker_rental:2026-08"


def test_unknown_provider_outcome_is_never_retried(tmp_path: Path) -> None:
    provider = FakeProvider("unknown")

    first = _run(tmp_path, provider=provider)
    second = _run(tmp_path, provider=provider)

    assert first["status"] == "UNKNOWN_OUTCOME"
    assert second["status"] == "ALREADY_CLAIMED_NO_RETRY"
    assert len(provider.calls) == 1


def test_sent_but_ledger_failure_enters_repair_state_without_resend(tmp_path: Path) -> None:
    provider = FakeProvider()
    ledger = FakeLedger(fail=True)

    first = _run(tmp_path, provider=provider, ledger=ledger)
    second = _run(tmp_path, provider=provider, ledger=ledger)

    assert first["status"] == "LEDGER_REPAIR_REQUIRED"
    assert second["status"] == "ALREADY_SENT_LEDGER_REPAIR_REQUIRED"
    assert len(provider.calls) == 1


def test_g2c_post_is_deterministic_and_idempotent(tmp_path: Path) -> None:
    package = _package(tmp_path)
    receipt = FakeProvider().send(package, cycle_key="live_arts_md:speaker_rental:2026-08")
    db_path = tmp_path / "g2c.sqlite3"

    first = post_sent_receivable(package, receipt, db_path=db_path)
    second = post_sent_receivable(package, receipt, db_path=db_path)

    assert first == {"invoice_created": True, "receivable_created": True}
    assert second == {"invoice_created": False, "receivable_created": False}
    with sqlite3.connect(db_path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM invoice_records").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM expected_receivable_records").fetchone()[0] == 1


def test_concurrent_scheduler_collision_still_calls_provider_once(tmp_path: Path) -> None:
    package = _package(tmp_path)
    provider = FakeProvider()
    ledger = FakeLedger()
    store = LamdMonthlyCycleStore(tmp_path / "cycles.sqlite3")

    def attempt(_index: int) -> dict:
        return run_monthly_cycle(
            now=NOW,
            package=package,
            policy=AutosendPolicy(armed=True, operator_stop=False),
            store=store,
            freeze_guard=FakeGuard(),
            send_hold_admission=lambda _package: {"allowed": True},
            provider=provider,
            ledger=ledger,
        )

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(attempt, range(8)))

    assert len(provider.calls) == 1
    assert len(ledger.calls) == 1
    assert sum(row["status"] == "LEDGER_POSTED" for row in results) == 1
    assert all(
        row["status"] in {"LEDGER_POSTED", "ALREADY_CLAIMED_NO_RETRY", "ALREADY_SENT_VERIFIED"}
        for row in results
    )


@pytest.mark.parametrize(
    ("policy", "hold_allowed", "expected"),
    (
        (AutosendPolicy(armed=False, operator_stop=False), True, "REFUSED_UNARMED"),
        (AutosendPolicy(armed=True, operator_stop=True), True, "REFUSED_OPERATOR_STOP"),
        (AutosendPolicy(armed=True, operator_stop=False), False, "REFUSED_SEND_HOLD"),
    ),
)
def test_authority_and_send_hold_refusals_are_provider_zero(
    tmp_path: Path,
    policy: AutosendPolicy,
    hold_allowed: bool,
    expected: str,
) -> None:
    provider = FakeProvider()
    result = run_monthly_cycle(
        now=NOW,
        package=_package(tmp_path),
        policy=policy,
        store=LamdMonthlyCycleStore(tmp_path / "cycles.sqlite3"),
        freeze_guard=FakeGuard(),
        send_hold_admission=lambda _package: {"allowed": hold_allowed},
        provider=provider,
        ledger=FakeLedger(),
    )
    assert result["status"] == expected
    assert result["provider_called"] is False
    assert provider.calls == []
