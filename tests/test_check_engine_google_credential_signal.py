"""Google access health reaches Chief's check-engine rail — without this lane
ever touching the account layer itself."""

from __future__ import annotations

import ast
import json
from pathlib import Path

import chief_check_engine_environment_posture as posture


def _signal(payload):
    return next(
        s for s in payload["signals"] if s["signal_id"] == "google_access_authorisation_health"
    )


def _build(tmp_path, credential_health):
    root = tmp_path
    (root / "generated" / "read_models").mkdir(parents=True)
    if credential_health is not None:
        (root / "generated" / "read_models" / "google_credential_health.json").write_text(
            json.dumps(credential_health), encoding="utf-8"
        )
    return posture.build_chief_check_engine_environment_posture(repo_root=root)


REVOKED = {
    "status": "GOOGLE_ACCESS_EXPIRED_OR_REVOKED",
    "healthy": False,
    "checked_at": "2026-07-26T05:25:40Z",
    "downstream_at_risk": [
        {"what": "LAMD monthly auto-send", "stake": "money-adjacent"},
        {"what": "Cassandra inbound watch", "stake": "complaints unnoticed"},
    ],
}


def test_a_revoked_authorisation_lights_the_check_engine_as_blocked(tmp_path: Path) -> None:
    """Not a warning. An armed send that cannot fire is a stop."""

    payload = _build(tmp_path, REVOKED)
    signal = _signal(payload)

    assert signal["status"] == "blocked"
    assert signal["should_light_check_engine"] is True
    assert payload["check_engine"]["check_engine_on"] is True
    assert payload["check_engine"]["status"] == "blocked"


def test_the_armed_send_at_risk_is_named_on_the_rail(tmp_path: Path) -> None:
    signal = _signal(_build(tmp_path, REVOKED))
    downstream = next(e for e in signal["evidence"] if e["label"] == "downstream_at_risk")

    assert "LAMD monthly auto-send" in downstream["value"]


def test_healthy_access_does_not_light_the_lamp(tmp_path: Path) -> None:
    signal = _signal(_build(tmp_path, {"status": "GOOGLE_ACCESS_OK", "healthy": True}))

    assert signal["status"] == "ok"
    assert signal["should_light_check_engine"] is False


def test_never_observed_is_unknown_and_lights_rather_than_reading_as_all_clear(
    tmp_path: Path,
) -> None:
    """"Nobody looked" and "all clear" must not render the same."""

    signal = _signal(_build(tmp_path, None))

    assert signal["status"] == "unknown"
    assert signal["should_light_check_engine"] is True
    assert "not been observed" in signal["what_it_means_plain_language"]


def test_an_unrecognised_status_is_unknown_not_ok(tmp_path: Path) -> None:
    signal = _signal(_build(tmp_path, {"status": "SOMETHING_NEW"}))

    assert signal["status"] == "unknown"
    assert signal["should_light_check_engine"] is True


def test_missing_libraries_are_a_warning_not_a_blocked_account(tmp_path: Path) -> None:
    """Different wall, different urgency — the account may be perfectly fine."""

    signal = _signal(_build(tmp_path, {"status": "GOOGLE_ACCESS_DEPS_MISSING"}))

    assert signal["status"] == "warning"


def test_the_evidence_is_labelled_observed_and_stores_no_credential_material(
    tmp_path: Path,
) -> None:
    signal = _signal(_build(tmp_path, REVOKED))

    for evidence in signal["evidence"]:
        assert evidence["evidence_type"] == "observed"
        assert evidence["credentials_stored"] is False
        assert evidence["private_content_stored"] is False


def test_this_lane_still_swears_it_never_touched_the_account_layer(tmp_path: Path) -> None:
    """The signal is ingested from an exported read-model, not probed here."""

    payload = _build(tmp_path, REVOKED)

    assert posture.NO_AUTHORITY_FLAGS["credential_or_oauth_accessed"] is False
    assert posture.NO_AUTHORITY_FLAGS["gmail_calendar_coupa_accessed"] is False
    source = payload["source_inputs"]["observed_google_credential_health_source"]
    assert source["probe_performed_by_this_lane"] is False
    assert source["evidence_type"] == "observed"


def test_the_lane_does_not_import_the_broker_to_get_this_signal() -> None:
    """Reading a summary keeps the no-account-access contract literally true."""

    tree = ast.parse(Path("chief_check_engine_environment_posture.py").read_text(encoding="utf-8"))
    names = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    } | {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    }

    assert "google_access_broker" not in names
    assert "google_credential_health" not in names


def test_the_signal_forbids_re_authorising_from_this_lane(tmp_path: Path) -> None:
    """Surfacing the problem must not read as permission to fix it."""

    signal = _signal(_build(tmp_path, REVOKED))
    forbidden = " ".join(signal["forbidden_actions"]).lower()

    assert "re-authorise" in forbidden
    assert "operator" in signal["safe_next_diagnostic_step"].lower()
