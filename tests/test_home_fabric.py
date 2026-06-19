from __future__ import annotations

import ipaddress
import json
import subprocess
from pathlib import Path

import pytest

import fabric_peer


REGISTRY_PATH = Path("home_fabric.json")


def test_home_fabric_registry_declares_nodes_with_mdns_and_vault_excludes() -> None:
    registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    nodes = registry["nodes"]

    assert {"pc", "mac", "home-server"} <= set(nodes)
    for name in ("pc", "mac", "home-server"):
        node = nodes[name]
        assert node["host"]
        assert node["mdns_hostname"].endswith(".local")
        with pytest.raises(ValueError):
            ipaddress.ip_address(node["mdns_hostname"])
        assert node["role"]
        excludes = node["vault_exclude_list"]
        assert "*LegalPrivate/*" in excludes
        assert "*FinancePrivate/*" in excludes
        assert "*MusicLawPrivate/*" in excludes
        assert ".chief.env" in excludes


def test_ssh_read_refuses_vault_paths_before_ssh() -> None:
    def forbidden_runner(*_args, **_kwargs):  # pragma: no cover - only called on regression
        raise AssertionError("ssh must not run for blocked vault paths")

    blocked_paths = [
        "/mnt/c/OpenClawLegalPrivate/case.json",
        "/home/openclaw/client/LegalPrivate/case.json",
        "/Users/winship/FinancePrivate/ledger.csv",
        "/Volumes/openclaw_e/MusicLawPrivate/splits.md",
        "/home/openclaw/.chief.env",
        "/home/openclaw/.google-secrets/token.json",
    ]

    for path in blocked_paths:
        with pytest.raises(fabric_peer.VaultPathError):
            fabric_peer.ssh_read("mac", path, runner=forbidden_runner)


def test_ssh_read_uses_mdns_hostname_not_ip() -> None:
    calls: list[list[str]] = []

    def runner(cmd, **_kwargs):
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, stdout="ok\n", stderr="")

    output = fabric_peer.ssh_read("mac", "~/Eyes/README.md", runner=runner)

    assert output == "ok\n"
    assert calls
    assert calls[0][0] == "ssh"
    assert calls[0][1] == "Hs-MBP-2.local"
    assert "192.168" not in " ".join(calls[0])


def test_peer_git_fetch_enforces_vault_wall_and_uses_mdns_hostname() -> None:
    calls: list[list[str]] = []

    def runner(cmd, **_kwargs):
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    fabric_peer.peer_git_fetch("mac", "~/Eyes", runner=runner)

    assert calls[0][0] == "ssh"
    assert calls[0][1] == "Hs-MBP-2.local"
    assert "git -C" in calls[0][2]
    assert "fetch origin" in calls[0][2]

    with pytest.raises(fabric_peer.VaultPathError):
        fabric_peer.peer_git_fetch("mac", "/Users/winship/FinancePrivate/repo", runner=runner)


def test_registry_rejects_ip_address_as_mdns_hostname(tmp_path: Path) -> None:
    registry = {
        "nodes": {
            "mac": {
                "host": "mac2",
                "mdns_hostname": "192.168.50.181",
                "role": "bad fixture",
                "vault_exclude_list": [".chief.env"],
            }
        }
    }
    path = tmp_path / "home_fabric.json"
    path.write_text(json.dumps(registry), encoding="utf-8")

    with pytest.raises(fabric_peer.FabricConfigError):
        fabric_peer.resolve_peer("mac", registry_path=path)


def test_local_git_push_and_fetch_helpers_do_not_force_push() -> None:
    calls: list[list[str]] = []

    def runner(cmd, **_kwargs):
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    fabric_peer.git_push("codex/example", runner=runner)
    fabric_peer.git_fetch(runner=runner)

    assert calls[0] == ["git", "push", "origin", "codex/example"]
    assert calls[1] == ["git", "fetch", "origin"]
    assert "--force" not in calls[0]
