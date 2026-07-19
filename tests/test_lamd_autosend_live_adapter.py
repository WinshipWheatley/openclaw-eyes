from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import pytest

from lamd_autosend_live_adapter import (
    GovernedGmailProvider,
    ScopeConfigError,
    build_exact_send_material,
    load_scope_config,
    verify_standing_send_context,
)
from send_hold_scoped_graduation import verify_send_hold_scoped_graduation


NOW = datetime(2026, 8, 16, 14, 0, tzinfo=timezone.utc)


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


def _scope_config(tmp_path: Path, **changes) -> Path:
    value = {
        "schema_version": "lamd_autosend_scope_v1",
        "armed": True,
        "operator_stop": False,
        "client_ref": "live_arts_md",
        "stream": "speaker_rental",
        "amount_minor_units": 10000,
        "currency": "USD",
        "recipient": "Accountant@liveartsmd.org",
        "cadence_day": 16,
        "standing_authority_ref": "operator-terminal-grant:lamd-monthly-autosend:2026-07-18",
        "authority_source_ref": "/home/openclaw/Operator/to-codex/OPUS-ARM-LAMD-MONTHLY-AUTOSEND-20260718.md",
    }
    value.update(changes)
    path = tmp_path / "scope.json"
    path.write_text(json.dumps(value), encoding="utf-8")
    path.chmod(0o644)
    return path


def _context(package: dict, config_path: Path) -> tuple[dict, dict]:
    material = build_exact_send_material(package)
    params = {
        "to": package["recipient"],
        "subject": material["subject"],
        "body": material["body"],
        "attachments": [package["pdf_path"]],
        "attachment_sha256": [package["pdf_sha256"]],
        "idempotency_key": material["request_id"],
        "exact_send_request_id": material["request_id"],
        "approval_context": {
            "standing_autosend_gate": True,
            "request_id": material["request_id"],
            "idempotency_key": material["request_id"],
            "payload_hash": material["payload_hash"],
            "standing_authority_ref": load_scope_config(
                config_path, expected_uid=os.getuid()
            )["standing_authority_ref"],
            "scope_config_path": str(config_path),
            "scope_config_sha256": _sha(config_path),
            "lamd_package": package,
        },
    }
    return params, material


def test_scope_config_is_root_metadata_bound_and_unarmed_refuses(tmp_path: Path) -> None:
    config_path = _scope_config(tmp_path)
    loaded = load_scope_config(config_path, expected_uid=os.getuid())
    assert loaded["armed"] is True

    config_path.chmod(0o666)
    with pytest.raises(ScopeConfigError, match="ownership or mode"):
        load_scope_config(config_path, expected_uid=os.getuid())

    config_path = _scope_config(tmp_path, armed=False)
    with pytest.raises(ScopeConfigError, match="not armed"):
        load_scope_config(config_path, expected_uid=os.getuid(), require_armed=True)


@pytest.mark.parametrize(
    "change",
    (
        {"recipient": "other@example.com"},
        {"amount_minor_units": 10001},
        {"cadence_day": 15},
        {"operator_stop": True},
    ),
)
def test_scope_config_drift_or_stop_refuses(tmp_path: Path, change: dict) -> None:
    config_path = _scope_config(tmp_path, **change)
    with pytest.raises(ScopeConfigError):
        load_scope_config(config_path, expected_uid=os.getuid(), require_armed=True)


def test_standing_context_verifier_rechecks_exact_material_and_time(tmp_path: Path) -> None:
    package = _package(tmp_path)
    config_path = _scope_config(tmp_path)
    params, _material = _context(package, config_path)

    verdict = verify_standing_send_context(
        "cassandra",
        "google.gmail.send",
        params,
        now=NOW,
        scope_config_path=config_path,
        artifact_root=tmp_path,
        expected_config_uid=os.getuid(),
    )
    assert verdict == {"valid": True, "reason": "lamd_standing_scope_verified"}

    changed = json.loads(json.dumps(params))
    changed["body"] += " drift"
    assert verify_standing_send_context(
        "cassandra",
        "google.gmail.send",
        changed,
        now=NOW,
        scope_config_path=config_path,
        artifact_root=tmp_path,
        expected_config_uid=os.getuid(),
    )["valid"] is False

    early = verify_standing_send_context(
        "cassandra",
        "google.gmail.send",
        params,
        now=datetime(2026, 8, 15, 23, 59, tzinfo=timezone.utc),
        scope_config_path=config_path,
        artifact_root=tmp_path,
        expected_config_uid=os.getuid(),
    )
    assert early == {"valid": False, "reason": "outside_monthly_cadence"}

    outside = verify_standing_send_context(
        "cassandra",
        "google.gmail.send",
        params,
        now=NOW,
        scope_config_path=config_path,
        artifact_root=tmp_path / "different-approved-root",
        expected_config_uid=os.getuid(),
    )
    assert outside == {"valid": False, "reason": "artifact_root_or_name_invalid"}


def test_provider_issues_one_exact_graduation_and_requires_consumed_proof(tmp_path: Path) -> None:
    package = _package(tmp_path)
    config_path = _scope_config(tmp_path)
    send_hold = tmp_path / "SEND_HOLD.md"
    send_hold.write_text("SEND_HOLD remains active.\n", encoding="utf-8")
    send_hold.chmod(0o644)
    graduation = tmp_path / "graduation.json"
    calls: list[tuple[str, str, dict]] = []

    def fake_broker(agent: str, capability: str, params: dict) -> dict:
        calls.append((agent, capability, params))
        verdict = verify_standing_send_context(
            agent,
            capability,
            params,
            now=NOW,
            scope_config_path=config_path,
            artifact_root=tmp_path,
            expected_config_uid=os.getuid(),
        )
        assert verdict["valid"] is True
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
                "message_id": "provider-august",
                "thread_id": "provider-thread",
                "send_hold_graduation_consumed": True,
            },
            "error": "",
        }

    provider = GovernedGmailProvider(
        scope_config_path=config_path,
        send_hold_path=send_hold,
        graduation_path=graduation,
        broker_call=fake_broker,
        artifact_root=tmp_path,
        expected_config_uid=os.getuid(),
        now_fn=lambda: NOW,
    )
    receipt = provider.send(package, cycle_key="live_arts_md:speaker_rental:2026-08")

    assert receipt["status"] == "SENT_VERIFIED"
    assert receipt["message_id"] == "provider-august"
    assert graduation.is_file()
    assert len(calls) == 1
    params = calls[0][2]
    assert params["approval_context"]["standing_autosend_gate"] is True
    assert params["to"] == "Accountant@liveartsmd.org"
    assert params["attachments"] == [package["pdf_path"]]


def test_provider_treats_missing_consumption_proof_as_unknown_outcome(tmp_path: Path) -> None:
    package = _package(tmp_path)
    config_path = _scope_config(tmp_path)
    send_hold = tmp_path / "SEND_HOLD.md"
    send_hold.write_text("SEND_HOLD remains active.\n", encoding="utf-8")
    send_hold.chmod(0o644)
    provider = GovernedGmailProvider(
        scope_config_path=config_path,
        send_hold_path=send_hold,
        graduation_path=tmp_path / "graduation.json",
        broker_call=lambda *_args: {
            "ok": True,
            "data": {
                "message_id": "maybe-sent",
                "send_hold_graduation_consumed": True,
            },
            "error": "",
        },
        artifact_root=tmp_path,
        expected_config_uid=os.getuid(),
        now_fn=lambda: NOW,
    )

    from lamd_monthly_autosend import ProviderOutcomeUnknown

    with pytest.raises(ProviderOutcomeUnknown, match="graduation file"):
        provider.send(package, cycle_key="live_arts_md:speaker_rental:2026-08")


def test_broker_exact_send_gate_delegates_standing_context_to_lamd_verifier(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import google_access_broker as broker
    import lamd_autosend_live_adapter as live_adapter

    calls: list[tuple[str, str, dict]] = []

    def verified(agent: str, capability: str, params: dict) -> dict:
        calls.append((agent, capability, params))
        return {"valid": True, "reason": "lamd_standing_scope_verified"}

    monkeypatch.setattr(live_adapter, "verify_standing_send_context", verified)
    params = {"approval_context": {"standing_autosend_gate": True}}

    assert broker._exact_send_gate_context_verified(
        "cassandra", "google.gmail.send", params
    ) is True
    assert calls == [("cassandra", "google.gmail.send", params)]

    monkeypatch.setattr(
        live_adapter,
        "verify_standing_send_context",
        lambda *_args: {"valid": False, "reason": "standing_scope_or_package_invalid"},
    )
    assert broker._exact_send_gate_context_verified(
        "cassandra", "google.gmail.send", params
    ) is False


def test_real_broker_gate_consumes_standing_graduation_before_fake_provider(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import google_access_broker as broker
    import lamd_autosend_live_adapter as live_adapter

    now = datetime(2026, 7, 19, 14, 0, tzinfo=timezone.utc)
    package = _package(
        tmp_path,
        service_month="2026-07",
        service_period_start="2026-07-01",
        service_period_end="2026-07-31",
        invoice_number="2026-1004",
    )
    config_path = _scope_config(tmp_path)
    send_hold = tmp_path / "SEND_HOLD.md"
    send_hold.write_text("SEND_HOLD remains active.\n", encoding="utf-8")
    send_hold.chmod(0o644)
    graduation = tmp_path / "graduation.json"
    actual_verify = live_adapter.verify_standing_send_context
    monkeypatch.setattr(
        live_adapter,
        "verify_standing_send_context",
        lambda agent, capability, params: actual_verify(
            agent,
            capability,
            params,
            now=now,
            scope_config_path=config_path,
            artifact_root=tmp_path,
            expected_config_uid=os.getuid(),
        ),
    )
    monkeypatch.setenv("OPENCLAW_SEND_HOLD_PATH", str(send_hold))
    monkeypatch.setattr(broker, "_is_configured", lambda: True)
    monkeypatch.setattr(broker, "_load_credentials", lambda: object())
    monkeypatch.setattr(
        broker,
        "check_gmail_broker_runtime_dependencies",
        lambda: {
            "ok": True,
            "checked_modules": [],
            "missing": [],
            "credentials_read": False,
            "google_api_called": False,
        },
    )
    monkeypatch.setattr(broker, "_resolve_broker_run_mode", lambda: ("production", ""))
    monkeypatch.setattr(
        broker,
        "_request_approval",
        lambda *_args, **_kwargs: pytest.fail("per-send approval was requested"),
    )
    provider_calls: list[dict] = []

    def fake_send(_credentials, params: dict) -> dict:
        provider_calls.append(dict(params))
        return {
            "ok": True,
            "data": {"message_id": "fake-google-id", "thread_id": "fake-thread"},
            "error": "",
        }

    monkeypatch.setattr(broker, "_exec_gmail_send", fake_send)
    monkeypatch.setattr(broker, "_audit", lambda *_args, **_kwargs: None)
    provider = GovernedGmailProvider(
        scope_config_path=config_path,
        send_hold_path=send_hold,
        graduation_path=graduation,
        broker_call=broker.call,
        artifact_root=tmp_path,
        expected_config_uid=os.getuid(),
        now_fn=lambda: now,
    )

    receipt = provider.send(package, cycle_key="live_arts_md:speaker_rental:2026-07")

    assert receipt["status"] == "SENT_VERIFIED"
    assert receipt["message_id"] == "fake-google-id"
    assert len(provider_calls) == 1
    graduation_payload = json.loads(graduation.read_text(encoding="utf-8"))
    assert graduation_payload["status"] == "CONSUMED"
    assert graduation_payload["use_count"] == 1
    assert send_hold.is_file()


def test_broker_refuses_standing_autosend_if_global_hold_disappears(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import google_access_broker as broker
    import lamd_autosend_live_adapter as live_adapter

    monkeypatch.setattr(
        live_adapter,
        "verify_standing_send_context",
        lambda *_args: {"valid": True, "reason": "lamd_standing_scope_verified"},
    )
    monkeypatch.setattr(broker, "_broker_send_hold_active", lambda: False)
    monkeypatch.setattr(broker, "_gmail_self_test_enabled", lambda: False)
    monkeypatch.setattr(broker, "_is_configured", lambda: True)
    monkeypatch.setattr(broker, "_load_credentials", lambda: object())
    monkeypatch.setattr(
        broker,
        "check_gmail_broker_runtime_dependencies",
        lambda: {
            "ok": True,
            "checked_modules": [],
            "missing": [],
            "credentials_read": False,
            "google_api_called": False,
        },
    )
    monkeypatch.setattr(broker, "_resolve_broker_run_mode", lambda: ("production", ""))
    monkeypatch.setattr(broker, "_audit", lambda *_args, **_kwargs: None)
    provider_calls: list[dict] = []
    monkeypatch.setattr(
        broker,
        "_exec_gmail_send",
        lambda _credentials, params: provider_calls.append(params)
        or {"ok": True, "data": {"message_id": "must-not-send"}, "error": ""},
    )

    result = broker.call(
        "cassandra",
        "google.gmail.send",
        {
            "to": "Accountant@liveartsmd.org",
            "subject": "bounded fixture",
            "body": "bounded fixture",
            "approval_context": {"standing_autosend_gate": True},
        },
    )

    assert result["ok"] is False
    assert "active send_hold" in result["error"].casefold()
    assert provider_calls == []
