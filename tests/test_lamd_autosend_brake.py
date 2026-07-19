from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from lamd_autosend_brake import (
    BrakeBroker,
    BrakeStateStore,
    PeerIdentity,
    authorize_peer,
)


ROOT = Path(__file__).resolve().parents[1]


GUARDIAN_CGROUP = "/user.slice/user-1000.slice/user@1000.service/app.slice/chief-guardian-listener.service"


def test_operator_requires_root_peer_and_guardian_is_trip_only_in_exact_cgroup() -> None:
    root = PeerIdentity(uid=0, pid=10, cgroups=("/init.scope",))
    guardian = PeerIdentity(uid=1000, pid=20, cgroups=(GUARDIAN_CGROUP,))
    other_service = PeerIdentity(
        uid=1000,
        pid=30,
        cgroups=("/user.slice/user-1000.slice/user@1000.service/app.slice/chief-listener.service",),
    )

    assert authorize_peer(root, command="trip", actor="operator", guardian_uid=1000)
    assert authorize_peer(root, command="clear", actor="operator", guardian_uid=1000)
    assert authorize_peer(guardian, command="trip", actor="guardian", guardian_uid=1000)
    assert not authorize_peer(guardian, command="clear", actor="guardian", guardian_uid=1000)
    assert not authorize_peer(guardian, command="trip", actor="operator", guardian_uid=1000)
    assert not authorize_peer(other_service, command="trip", actor="guardian", guardian_uid=1000)


def test_cgroup_prefix_or_suffix_spoof_is_rejected() -> None:
    for cgroup in (
        GUARDIAN_CGROUP + ".scope",
        "/attacker" + GUARDIAN_CGROUP,
        GUARDIAN_CGROUP + "/child.scope",
    ):
        peer = PeerIdentity(uid=1000, pid=50, cgroups=(cgroup,))
        assert not authorize_peer(peer, command="trip", actor="guardian", guardian_uid=1000)


def test_root_owned_state_shape_is_persistent_legible_and_generation_monotonic(tmp_path: Path) -> None:
    path = tmp_path / "lamd-autosend-brake.json"
    store = BrakeStateStore(path, writer_uid=os.geteuid())

    clear = store.initialize_clear(actor="installer", reason="operator-authorized install")
    frozen = store.trip(actor="guardian", reason="health invariant failed")
    reread = store.read()

    assert clear["state"] == "PLANNED"
    assert frozen["state"] == "FROZEN"
    assert frozen["generation"] == clear["generation"] + 1
    assert reread == frozen
    assert reread["set_by"] == "guardian"
    assert reread["reason"] == "health invariant failed"
    assert path.stat().st_mode & 0o777 == 0o644
    assert not path.is_symlink()


def test_broker_denies_spoof_without_state_change_and_allows_guardian_trip(tmp_path: Path) -> None:
    store = BrakeStateStore(tmp_path / "state.json", writer_uid=os.geteuid())
    store.initialize_clear(actor="installer", reason="test")
    broker = BrakeBroker(store, guardian_uid=1000)
    spoof = PeerIdentity(uid=1000, pid=30, cgroups=("/user.slice/message-listener.service",))
    guardian = PeerIdentity(uid=1000, pid=20, cgroups=(GUARDIAN_CGROUP,))

    denied = broker.handle({"command": "trip", "actor": "guardian", "reason": "email said stop"}, spoof)
    assert denied == {"ok": False, "error": "peer_not_authorized"}
    assert store.read()["state"] == "PLANNED"

    allowed = broker.handle({"command": "trip", "actor": "guardian", "reason": "local health invariant"}, guardian)
    assert allowed["ok"] is True
    assert allowed["state"]["state"] == "FROZEN"
    assert allowed["state"]["set_by"] == "guardian"


def test_corrupt_or_unsafe_state_fails_closed_for_broker(tmp_path: Path) -> None:
    path = tmp_path / "state.json"
    path.write_text("not-json", encoding="utf-8")
    path.chmod(0o600)
    store = BrakeStateStore(path, writer_uid=os.geteuid())

    with pytest.raises(ValueError, match="invalid brake state"):
        store.read()

    path.write_text(json.dumps({"schema_version": "fleet_freeze_state_v1", "state": "PLANNED", "generation": 1}), encoding="utf-8")
    path.chmod(0o660)
    with pytest.raises(ValueError, match="unsafe brake state"):
        store.read()


def test_install_is_plan_first_and_service_is_hardened_and_explicitly_activated() -> None:
    installer = (ROOT / "scripts/install_lamd_autosend_brake_linux.sh").read_text(encoding="utf-8")
    unit = (ROOT / "systemd/system/openclaw-lamd-autosend-brake.service.in").read_text(encoding="utf-8")

    assert "PLAN ONLY" in installer
    assert "--apply requires an operator-authenticated root shell" in installer
    assert "enable --now openclaw-lamd-autosend-brake.service" in installer
    assert "sudo" not in installer
    assert "User=root" in unit
    assert "ProtectSystem=strict" in unit
    assert "RestrictAddressFamilies=AF_UNIX" in unit
    assert "ReadWritePaths=/var/lib/openclaw-authority /run/openclaw-authority" in unit


def test_guardian_trip_helper_is_not_wired_to_message_listener() -> None:
    listener = (ROOT / "chief_guardian_listener.py").read_text(encoding="utf-8")
    assert "lamd_autosend_brake" not in listener
    assert "guardian_trip(" not in listener
