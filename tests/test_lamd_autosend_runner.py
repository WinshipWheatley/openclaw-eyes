from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from lamd_monthly_autosend import GuardDecision
from lamd_monthly_autosend_runner import run_once
from send_hold_scoped_graduation import verify_send_hold_scoped_graduation


NOW = datetime(2026, 8, 16, 14, 0, tzinfo=timezone.utc)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _package(root: Path) -> dict:
    workbook = root / "Speaker Rentals August 2026.xlsx"
    pdf = root / "invoice.pdf"
    workbook.write_bytes(b"speaker-rental-workbook")
    pdf.write_bytes(b"%PDF-1.4 bounded-test")
    value = {
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
    material = {key: value[key] for key in sorted(value)}
    value["package_sha256"] = hashlib.sha256(
        json.dumps(material, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return value


def _validated_w1(root: Path) -> Path:
    month_dir = root / "2026-08"
    package_dir = month_dir / "w1-finalized-2026-1005"
    package_dir.mkdir(parents=True)
    workbook = package_dir / "invoice.xlsx"
    pdf = package_dir / "invoice.pdf"
    workbook.write_bytes(b"validated speaker-rental workbook")
    pdf.write_bytes(b"%PDF-1.4 validated speaker-rental invoice")
    manifest = {
        "schema": "openclaw_invoice_manifest_v1",
        "status": "finalized_validated",
        "client_slug": "live-arts-md",
        "stream": "speaker_rental",
        "invoice_key": "2026-08_live_arts_md_2026-1005",
        "invoice_number": "2026-1005",
        "service_period_start": "2026-08-01",
        "service_period_end": "2026-08-31",
        "source_sheet": "August 2026",
        "amount": 100.0,
        "package_workbook_sha256": _sha(workbook),
        "current_pdf_sha256": _sha(pdf),
        "validated_artifact_sha256": _sha(pdf),
        "validation_event_id": "invoice-validation:august",
        "artifact_verification_receipt_id": "invoice-validation:august",
        "authority_boundary": {
            "provider_draft_created": False,
            "external_send_performed": False,
            "money_moved": False,
            "ledger_posted": False,
        },
    }
    (package_dir / "invoice_manifest.json").write_text(
        json.dumps(manifest), encoding="utf-8"
    )
    return month_dir


def _write_scope(path: Path, *, armed: bool, operator_stop: bool, **changes) -> None:
    payload = {
        "schema_version": "lamd_autosend_scope_v1",
        "armed": armed,
        "operator_stop": operator_stop,
        "client_ref": "live_arts_md",
        "stream": "speaker_rental",
        "amount_minor_units": 10000,
        "currency": "USD",
        "recipient": "Accountant@liveartsmd.org",
        "cadence_day": 16,
        "standing_authority_ref": "operator-terminal-grant:lamd-monthly-autosend:2026-07-18",
        "authority_source_ref": "/home/openclaw/Operator/to-codex/OPUS-ARM-LAMD-MONTHLY-AUTOSEND-20260718.md",
    }
    payload.update(changes)
    path.write_text(
        json.dumps(payload),
        encoding="utf-8",
    )
    path.chmod(0o644)


class ClearGuard:
    def check(self, _operation: str) -> GuardDecision:
        return GuardDecision(True, "freeze_not_applied", 4)


def test_plan_mode_never_reads_or_creates_runtime_state(tmp_path: Path) -> None:
    result = run_once(
        execute=False,
        now=NOW,
        package_path=tmp_path / "missing-package.json",
        scope_config_path=tmp_path / "missing-scope.json",
        cycles_path=tmp_path / "cycles.sqlite3",
        ledger_path=tmp_path / "g2c.sqlite3",
        graduation_dir=tmp_path / "graduations",
        receipt_dir=tmp_path / "receipts",
        send_hold_path=tmp_path / "missing-hold.md",
        artifact_root=tmp_path,
    )

    assert result["status"] == "PLAN_ONLY"
    assert list(tmp_path.iterdir()) == []


def test_missing_package_blocks_before_runtime_state(tmp_path: Path) -> None:
    scope = tmp_path / "scope.json"
    _write_scope(scope, armed=True, operator_stop=False)

    result = run_once(
        execute=True,
        now=NOW,
        package_path=tmp_path / "missing-package.json",
        scope_config_path=scope,
        cycles_path=tmp_path / "cycles.sqlite3",
        ledger_path=tmp_path / "g2c.sqlite3",
        graduation_dir=tmp_path / "graduations",
        receipt_dir=tmp_path / "receipts",
        send_hold_path=tmp_path / "missing-hold.md",
        artifact_root=tmp_path,
        expected_config_uid=os.getuid(),
        freeze_guard=ClearGuard(),
        broker_call=lambda *_args: (_ for _ in ()).throw(AssertionError("broker called")),
    )

    assert result["status"] == "BLOCKED_PACKAGE_UNAVAILABLE"
    assert not (tmp_path / "cycles.sqlite3").exists()
    assert not (tmp_path / "g2c.sqlite3").exists()


def test_unarmed_scope_is_provider_zero_and_claim_zero(tmp_path: Path) -> None:
    package_path = tmp_path / "package.json"
    package_path.write_text(json.dumps(_package(tmp_path)), encoding="utf-8")
    scope = tmp_path / "scope.json"
    _write_scope(scope, armed=False, operator_stop=True)
    send_hold = tmp_path / "SEND_HOLD.md"
    send_hold.write_text("SEND_HOLD remains active.\n", encoding="utf-8")
    send_hold.chmod(0o644)
    calls: list[dict] = []

    result = run_once(
        execute=True,
        now=NOW,
        package_path=package_path,
        scope_config_path=scope,
        cycles_path=tmp_path / "cycles.sqlite3",
        ledger_path=tmp_path / "g2c.sqlite3",
        graduation_dir=tmp_path / "graduations",
        receipt_dir=tmp_path / "receipts",
        send_hold_path=send_hold,
        artifact_root=tmp_path,
        expected_config_uid=os.getuid(),
        freeze_guard=ClearGuard(),
        broker_call=lambda *_args: calls.append({}) or {},
    )

    assert result["status"] == "REFUSED_UNARMED"
    assert result["provider_called"] is False
    assert calls == []
    assert not (tmp_path / "g2c.sqlite3").exists()
    with sqlite3.connect(tmp_path / "cycles.sqlite3") as conn:
        assert conn.execute("SELECT COUNT(*) FROM monthly_cycles").fetchone()[0] == 0


def test_scope_not_before_month_refuses_stale_current_package_provider_zero(tmp_path: Path) -> None:
    july_now = datetime(2026, 7, 19, 14, 35, tzinfo=timezone.utc)
    package = _package(tmp_path)
    package.update(
        {
            "service_month": "2026-07",
            "service_period_start": "2026-07-01",
            "service_period_end": "2026-07-31",
            "invoice_number": "2026-1004",
        }
    )
    material = {key: package[key] for key in sorted(package) if key != "package_sha256"}
    package["package_sha256"] = hashlib.sha256(
        json.dumps(material, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    package_path = tmp_path / "package.json"
    package_path.write_text(json.dumps(package), encoding="utf-8")
    scope = tmp_path / "scope.json"
    _write_scope(
        scope,
        armed=True,
        operator_stop=False,
        not_before_service_month="2026-08",
    )
    send_hold = tmp_path / "SEND_HOLD.md"
    send_hold.write_text("SEND_HOLD remains active.\n", encoding="utf-8")
    send_hold.chmod(0o644)
    calls: list[dict] = []

    result = run_once(
        execute=True,
        now=july_now,
        package_path=package_path,
        scope_config_path=scope,
        cycles_path=tmp_path / "cycles.sqlite3",
        ledger_path=tmp_path / "g2c.sqlite3",
        graduation_dir=tmp_path / "graduations",
        receipt_dir=tmp_path / "receipts",
        send_hold_path=send_hold,
        artifact_root=tmp_path,
        expected_config_uid=os.getuid(),
        freeze_guard=ClearGuard(),
        broker_call=lambda *_args: calls.append({}) or {},
    )

    assert result["status"] == "REFUSED_NOT_BEFORE_SERVICE_MONTH"
    assert result["not_before_service_month"] == "2026-08"
    assert result["provider_called"] is False
    assert calls == []
    assert not (tmp_path / "g2c.sqlite3").exists()
    with sqlite3.connect(tmp_path / "cycles.sqlite3") as conn:
        assert conn.execute("SELECT COUNT(*) FROM monthly_cycles").fetchone()[0] == 0


def test_execute_uses_fake_broker_once_and_posts_one_receivable(tmp_path: Path) -> None:
    package = _package(tmp_path)
    package_path = tmp_path / "package.json"
    package_path.write_text(json.dumps(package), encoding="utf-8")
    scope = tmp_path / "scope.json"
    _write_scope(scope, armed=True, operator_stop=False)
    send_hold = tmp_path / "SEND_HOLD.md"
    send_hold.write_text("SEND_HOLD remains active.\n", encoding="utf-8")
    send_hold.chmod(0o644)
    calls: list[dict] = []

    def fake_broker(_agent: str, _capability: str, params: dict) -> dict:
        calls.append(params)
        verify_send_hold_scoped_graduation(
            graduation_path=params["send_hold_graduation_ref"],
            send_hold_path=send_hold,
            request_id=params["exact_send_request_id"],
            payload_hash=params["approval_context"]["payload_hash"],
            recipient=params["to"],
            body_sha256="sha256:" + hashlib.sha256(params["body"].encode()).hexdigest(),
            attachment_paths=params["attachments"],
            attachment_sha256=params["attachment_sha256"],
            observed_at=NOW.isoformat(timespec="seconds"),
            consume=True,
        )
        return {
            "ok": True,
            "data": {
                "message_id": "fake-provider-message",
                "thread_id": "fake-provider-thread",
                "send_hold_graduation_consumed": True,
            },
            "error": "",
        }

    result = run_once(
        execute=True,
        now=NOW,
        package_path=package_path,
        scope_config_path=scope,
        cycles_path=tmp_path / "cycles.sqlite3",
        ledger_path=tmp_path / "g2c.sqlite3",
        graduation_dir=tmp_path / "graduations",
        receipt_dir=tmp_path / "receipts",
        send_hold_path=send_hold,
        artifact_root=tmp_path,
        expected_config_uid=os.getuid(),
        freeze_guard=ClearGuard(),
        broker_call=fake_broker,
    )

    assert result["status"] == "LEDGER_POSTED"
    assert len(calls) == 1
    with sqlite3.connect(tmp_path / "g2c.sqlite3") as conn:
        assert conn.execute("SELECT COUNT(*) FROM invoice_records").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM expected_receivable_records").fetchone()[0] == 1
    receipts = list((tmp_path / "receipts").glob("*.json"))
    assert len(receipts) == 1
    assert json.loads(receipts[0].read_text())["status"] == "LEDGER_POSTED"


def test_execute_publishes_validated_w1_before_one_send_and_receivable(tmp_path: Path) -> None:
    month_dir = _validated_w1(tmp_path)
    package_path = month_dir / "lamd_monthly_autosend_package.json"
    scope = tmp_path / "scope.json"
    _write_scope(scope, armed=True, operator_stop=False)
    send_hold = tmp_path / "SEND_HOLD.md"
    send_hold.write_text("SEND_HOLD remains active.\n", encoding="utf-8")
    send_hold.chmod(0o644)
    calls: list[dict] = []

    def fake_broker(_agent: str, _capability: str, params: dict) -> dict:
        calls.append(params)
        verify_send_hold_scoped_graduation(
            graduation_path=params["send_hold_graduation_ref"],
            send_hold_path=send_hold,
            request_id=params["exact_send_request_id"],
            payload_hash=params["approval_context"]["payload_hash"],
            recipient=params["to"],
            body_sha256="sha256:" + hashlib.sha256(params["body"].encode()).hexdigest(),
            attachment_paths=params["attachments"],
            attachment_sha256=params["attachment_sha256"],
            observed_at=NOW.isoformat(timespec="seconds"),
            consume=True,
        )
        return {
            "ok": True,
            "data": {
                "message_id": "fake-provider-message",
                "thread_id": "fake-provider-thread",
                "send_hold_graduation_consumed": True,
            },
            "error": "",
        }

    result = run_once(
        execute=True,
        now=NOW,
        package_path=package_path,
        scope_config_path=scope,
        cycles_path=tmp_path / "cycles.sqlite3",
        ledger_path=tmp_path / "g2c.sqlite3",
        graduation_dir=tmp_path / "graduations",
        receipt_dir=tmp_path / "receipts",
        send_hold_path=send_hold,
        artifact_root=tmp_path,
        expected_config_uid=os.getuid(),
        freeze_guard=ClearGuard(),
        broker_call=fake_broker,
    )

    assert result["status"] == "LEDGER_POSTED"
    assert package_path.is_file()
    assert len(calls) == 1
    with sqlite3.connect(tmp_path / "g2c.sqlite3") as conn:
        assert conn.execute("SELECT COUNT(*) FROM invoice_records").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM expected_receivable_records").fetchone()[0] == 1
