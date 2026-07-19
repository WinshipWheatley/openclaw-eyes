#!/usr/bin/env python3
"""Installed-path clear/tripped LAMD acceptance using a fake provider only."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(os.environ.get("OPENCLAW_REPO_ROOT", "/home/openclaw"))
INSTALLED_AUTHORITY_ROOT = Path("/usr/local/libexec/openclaw-authority")
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(INSTALLED_AUTHORITY_ROOT) not in sys.path:
    sys.path.insert(0, str(INSTALLED_AUTHORITY_ROOT))

from lamd_autosend_brake import DEFAULT_STATE_PATH, request_broker
from lamd_monthly_autosend import AutosendPolicy, LamdMonthlyCycleStore, run_monthly_cycle
from openclaw_authority.freeze_guard import FreezeGuard


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _stable(value: object) -> str:
    return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


class FakeProvider:
    def __init__(self):
        self.calls = 0

    def send(self, package: dict, *, cycle_key: str) -> dict:
        self.calls += 1
        return {
            "status": "SENT_VERIFIED",
            "message_id": "fake-installed-acceptance",
            "recipient": package["recipient"],
            "amount_minor_units": package["amount_minor_units"],
            "service_month": package["service_month"],
            "package_sha256": package["package_sha256"],
            "sent_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }


class FakeLedger:
    def post(self, _package: dict, _receipt: dict) -> dict:
        return {"fake": True, "production_ledger_touched": False}


def _package(root: Path, month: str) -> dict:
    workbook = root / f"{month} Speaker Rentals.xlsx"
    pdf = root / "invoice.pdf"
    workbook.write_bytes(b"installed acceptance workbook; fake only")
    pdf.write_bytes(b"%PDF-1.4 installed acceptance; fake only")
    value = {
        "schema_version": "lamd_monthly_autosend_package_v1",
        "client_ref": "live_arts_md",
        "stream": "speaker_rental",
        "service_month": month,
        "service_period_start": month + "-01",
        "service_period_end": datetime.strptime(month + "-01", "%Y-%m-%d").date().replace(day=28).isoformat(),
        "invoice_number": "ACCEPTANCE-ONLY",
        "amount_minor_units": 10000,
        "currency": "USD",
        "recipient": "Accountant@liveartsmd.org",
        "source_workbook_path": str(workbook),
        "source_workbook_sha256": _sha(workbook),
        "source_sheet": "Acceptance Speaker Rental",
        "pdf_path": str(pdf),
        "pdf_sha256": _sha(pdf),
        "status": "finalized_validated",
    }
    material = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    value["package_sha256"] = hashlib.sha256(material.encode()).hexdigest()
    return value


def run_acceptance() -> dict:
    if os.geteuid() != 0:
        raise PermissionError("installed acceptance requires operator-authenticated root")
    status = request_broker("status", actor="operator")
    initial = dict(status.get("state") or {})
    if status.get("ok") is not True or initial.get("state") != "PLANNED":
        raise RuntimeError("acceptance requires an already-clear, healthy installed brake")
    temporary_root = Path(tempfile.mkdtemp(prefix="lamd-acceptance-", dir="/run/openclaw-authority"))
    trip_reason = "bounded fake-provider installed-path acceptance"
    tripped_generation: int | None = None
    provider = FakeProvider()
    try:
        now = datetime.now(timezone.utc).replace(day=max(16, datetime.now(timezone.utc).day))
        package = _package(temporary_root, now.strftime("%Y-%m"))
        guard = FreezeGuard(DEFAULT_STATE_PATH, enabled=True, expected_uid=0)
        clear = run_monthly_cycle(
            now=now,
            package=package,
            policy=AutosendPolicy(armed=True, operator_stop=False),
            store=LamdMonthlyCycleStore(temporary_root / "clear.sqlite3"),
            freeze_guard=guard,
            send_hold_admission=lambda _package: {"allowed": True, "acceptance_only": True},
            provider=provider,
            ledger=FakeLedger(),
        )
        if clear.get("status") != "LEDGER_POSTED" or provider.calls != 1:
            raise RuntimeError("clear-state fake provider proof failed")
        trip = request_broker("trip", actor="operator", reason=trip_reason)
        tripped = dict(trip.get("state") or {})
        if trip.get("ok") is not True or tripped.get("state") != "FROZEN":
            raise RuntimeError("installed operator trip failed")
        tripped_generation = int(tripped["generation"])
        denied = run_monthly_cycle(
            now=now,
            package=package,
            policy=AutosendPolicy(armed=True, operator_stop=False),
            store=LamdMonthlyCycleStore(temporary_root / "tripped.sqlite3"),
            freeze_guard=guard,
            send_hold_admission=lambda _package: {"allowed": True, "acceptance_only": True},
            provider=provider,
            ledger=FakeLedger(),
        )
        if denied.get("status") != "REFUSED_FLEET_FREEZE" or provider.calls != 1:
            raise RuntimeError("tripped-state zero-provider proof failed")
        if denied.get("queued_for_release") is not False:
            raise RuntimeError("brake refusal was queued")
        proof = {
            "schema_version": "lamd_installed_brake_acceptance_v1",
            "status": "PASS",
            "state_path": str(DEFAULT_STATE_PATH),
            "installed_freeze_guard": str(INSTALLED_AUTHORITY_ROOT / "openclaw_authority/freeze_guard.py"),
            "clear_result": clear,
            "tripped_result": denied,
            "fake_provider_total_calls": provider.calls,
            "production_provider_calls": 0,
            "production_ledger_writes": 0,
            "queued_for_release": False,
            "observed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
    finally:
        if tripped_generation is not None:
            observed = request_broker("status", actor="operator")
            state = dict(observed.get("state") or {})
            if (
                observed.get("ok") is True
                and state.get("state") == "FROZEN"
                and int(state.get("generation") or 0) == tripped_generation
                and state.get("set_by") == "operator"
                and state.get("reason") == trip_reason
            ):
                request_broker("clear", actor="operator", reason="completed bounded fake-provider acceptance")
        shutil.rmtree(temporary_root, ignore_errors=True)
    return proof


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if not args.apply:
        print("PLAN ONLY: fake provider, temporary ledger, real installed brake state; no Gmail or production G2C.")
        return 0
    print(_stable(run_acceptance()), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
