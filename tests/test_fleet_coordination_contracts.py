from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest


def _reference(tmp_path: Path, text: str = "mission") -> Path:
    path = tmp_path / "result.md"
    path.write_text(text, encoding="utf-8")
    return path


def test_normal_writer_is_atomic_closed_and_mode_0600(tmp_path: Path) -> None:
    from fleet_coordination_contracts import SCHEMA_VERSION, read_wake_ping, write_wake_ping

    reference = _reference(tmp_path)
    wake_dir = tmp_path / "WAKE"

    wake_path = write_wake_ping(
        wake_dir=wake_dir,
        from_seat="PC-Sol",
        to_seat="Opus",
        mission_id="WAKE-V2B",
        reference_path=reference,
        now=datetime(2026, 7, 19, 2, 30, 1, 123456, tzinfo=timezone.utc),
    )

    assert wake_path.name == "WAKE-Opus-20260719T023001123456Z.json"
    payload = json.loads(wake_path.read_text(encoding="utf-8"))
    assert payload == {
        "schema_version": SCHEMA_VERSION,
        "from": "PC-Sol",
        "to": "Opus",
        "mission_id": "WAKE-V2B",
        "file": str(reference),
        "sha": hashlib.sha256(b"mission").hexdigest(),
        "needs_human_kick": False,
        "created_at": "2026-07-19T02:30:01.123456Z",
        "priority": "normal",
    }
    assert wake_path.stat().st_mode & 0o777 == 0o600
    assert not list(wake_dir.glob(".*.tmp"))
    parsed = read_wake_ping(wake_path, recipient="Opus")
    assert parsed.verification == "verified_v2"
    assert parsed.priority == "normal"


@pytest.mark.parametrize("reason", ["operator_directive", "safety_stop", "blocking_confer"])
def test_urgent_requires_explicit_allowed_reason(tmp_path: Path, reason: str) -> None:
    from fleet_coordination_contracts import write_wake_ping

    wake_path = write_wake_ping(
        wake_dir=tmp_path / "WAKE",
        from_seat="PC-Sol",
        to_seat="Opus",
        mission_id="URGENT-TEST",
        reference_path=_reference(tmp_path),
        priority="urgent",
        urgent_reason=reason,
        now=datetime(2026, 7, 19, 2, 31, tzinfo=timezone.utc),
    )

    payload = json.loads(wake_path.read_text(encoding="utf-8"))
    assert payload["priority"] == "urgent"
    assert payload["urgent_reason"] == reason


def test_urgent_without_reason_and_normal_with_reason_are_rejected(tmp_path: Path) -> None:
    from fleet_coordination_contracts import WakeContractError, write_wake_ping

    reference = _reference(tmp_path)
    common = dict(
        wake_dir=tmp_path / "WAKE",
        from_seat="PC-Sol",
        to_seat="Opus",
        mission_id="URGENT-TEST",
        reference_path=reference,
    )

    with pytest.raises(WakeContractError, match="urgent_reason_required"):
        write_wake_ping(**common, priority="urgent")
    with pytest.raises(WakeContractError, match="urgent_reason_forbidden"):
        write_wake_ping(**common, priority="normal", urgent_reason="safety_stop")
    with pytest.raises(WakeContractError, match="urgent_reason_invalid"):
        write_wake_ping(**common, priority="urgent", urgent_reason="routine_result")


def test_reference_must_be_regular_non_symlink_and_identity_is_closed(tmp_path: Path) -> None:
    from fleet_coordination_contracts import WakeContractError, write_wake_ping

    reference = _reference(tmp_path)
    linked = tmp_path / "linked.md"
    linked.symlink_to(reference)
    common = dict(
        wake_dir=tmp_path / "WAKE",
        from_seat="PC-Sol",
        to_seat="Opus",
        mission_id="WAKE-V2B",
    )

    with pytest.raises(WakeContractError, match="reference_not_regular"):
        write_wake_ping(**common, reference_path=linked)
    with pytest.raises(WakeContractError, match="unknown_seat"):
        write_wake_ping(**{**common, "to_seat": "Not-A-Seat"}, reference_path=reference)
    with pytest.raises(WakeContractError, match="control_character"):
        write_wake_ping(
            **{**common, "mission_id": "bad\nmission"},
            reference_path=reference,
        )


def test_reader_rejects_wrong_recipient_filename_and_sha_drift(tmp_path: Path) -> None:
    from fleet_coordination_contracts import WakeContractError, read_wake_ping, write_wake_ping

    reference = _reference(tmp_path)
    wake_path = write_wake_ping(
        wake_dir=tmp_path / "WAKE",
        from_seat="PC-Sol",
        to_seat="Opus",
        mission_id="WAKE-V2B",
        reference_path=reference,
        now=datetime(2026, 7, 19, 2, 32, tzinfo=timezone.utc),
    )

    with pytest.raises(WakeContractError, match="recipient_mismatch"):
        read_wake_ping(wake_path, recipient="Gemini")
    wrong_name = wake_path.with_name(wake_path.name.replace("WAKE-Opus-", "WAKE-Gemini-"))
    wrong_name.write_bytes(wake_path.read_bytes())
    with pytest.raises(WakeContractError, match="filename_recipient_mismatch"):
        read_wake_ping(wrong_name, recipient="Opus")
    reference.write_text("changed", encoding="utf-8")
    with pytest.raises(WakeContractError, match="reference_sha_mismatch"):
        read_wake_ping(wake_path, recipient="Opus")


def test_legacy_normal_ping_is_unverified_and_legacy_urgent_is_rejected(tmp_path: Path) -> None:
    from fleet_coordination_contracts import WakeContractError, read_wake_ping

    reference = _reference(tmp_path)
    base = {
        "from": "PC-Sol",
        "to": "Opus",
        "file": str(reference),
        "sha": hashlib.sha256(reference.read_bytes()).hexdigest(),
        "needs_human_kick": False,
        "priority": "normal",
    }
    legacy = tmp_path / "WAKE-Opus-20260719T023300Z.json"
    legacy.write_text(json.dumps(base), encoding="utf-8")

    parsed = read_wake_ping(legacy, recipient="Opus")
    assert parsed.verification == "unverified_legacy"
    assert parsed.priority == "normal"
    base["priority"] = "urgent"
    legacy.write_text(json.dumps(base), encoding="utf-8")
    with pytest.raises(WakeContractError, match="legacy_urgent_forbidden"):
        read_wake_ping(legacy, recipient="Opus")


def test_cli_defaults_normal_and_prints_written_path(tmp_path: Path, capsys) -> None:
    from scripts.drop_fleet_wake import main

    reference = _reference(tmp_path)
    result = main(
        [
            "--wake-dir",
            str(tmp_path / "WAKE"),
            "--from-seat",
            "PC-Sol",
            "--to-seat",
            "Opus",
            "--mission-id",
            "CLI-TEST",
            "--file",
            str(reference),
        ]
    )

    assert result == 0
    written = Path(capsys.readouterr().out.strip())
    assert json.loads(written.read_text(encoding="utf-8"))["priority"] == "normal"
