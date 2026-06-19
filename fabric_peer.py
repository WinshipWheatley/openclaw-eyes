from __future__ import annotations

import fnmatch
import ipaddress
import json
import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence


DEFAULT_REGISTRY_PATH = Path(__file__).with_name("home_fabric.json")

DEFAULT_VAULT_EXCLUDE_LIST = (
    "*LegalPrivate/*",
    "*FinancePrivate/*",
    "*MusicLawPrivate/*",
    "/mnt/c/OpenClawLegalPrivate/*",
    ".chief.env",
    "*/.chief.env",
    ".google-secrets/*",
    "*/.google-secrets/*",
)


class FabricError(RuntimeError):
    """Base error for home-fabric helper failures."""


class FabricConfigError(FabricError):
    """Raised when the fabric registry is missing or unsafe."""


class UnknownPeer(FabricConfigError):
    """Raised when a peer is not declared in the registry."""


class VaultPathError(FabricError, ValueError):
    """Raised before any peer operation can touch a vault or secret path."""


class PeerCommandError(FabricError):
    """Raised when an SSH or git helper command exits nonzero."""


Runner = Callable[..., subprocess.CompletedProcess[str]]


@dataclass(frozen=True)
class Peer:
    name: str
    host: str
    mdns_hostname: str
    role: str
    working_tree: str
    vault_exclude_list: tuple[str, ...]


def load_registry(registry_path: str | Path = DEFAULT_REGISTRY_PATH) -> dict[str, Any]:
    path = Path(registry_path)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise FabricConfigError(f"fabric registry not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise FabricConfigError(f"fabric registry is not valid JSON: {path}") from exc


def _is_ip_literal(value: str) -> bool:
    try:
        ipaddress.ip_address(value)
    except ValueError:
        return False
    return True


def _node_map(registry: Mapping[str, Any]) -> Mapping[str, Any]:
    nodes = registry.get("nodes")
    if not isinstance(nodes, Mapping):
        raise FabricConfigError("fabric registry must contain a nodes object")
    return nodes


def resolve_peer(
    peer_name: str,
    *,
    registry_path: str | Path = DEFAULT_REGISTRY_PATH,
) -> Peer:
    registry = load_registry(registry_path)
    nodes = _node_map(registry)
    raw = nodes.get(peer_name)
    if not isinstance(raw, Mapping):
        raise UnknownPeer(f"unknown fabric peer: {peer_name}")

    mdns_hostname = str(raw.get("mdns_hostname") or "").strip()
    if not mdns_hostname:
        raise FabricConfigError(f"peer {peer_name} is missing mdns_hostname")
    if _is_ip_literal(mdns_hostname):
        raise FabricConfigError(
            f"peer {peer_name} must use an mDNS hostname, not IP {mdns_hostname}"
        )

    excludes = tuple(str(item) for item in raw.get("vault_exclude_list") or ())
    if not excludes:
        raise FabricConfigError(f"peer {peer_name} must declare vault_exclude_list")

    return Peer(
        name=peer_name,
        host=str(raw.get("host") or peer_name),
        mdns_hostname=mdns_hostname,
        role=str(raw.get("role") or ""),
        working_tree=str(raw.get("working_tree") or ""),
        vault_exclude_list=excludes,
    )


def _normalize_path(path: str | Path) -> str:
    return str(path).strip().replace("\\", "/")


def _path_segments(path: str) -> list[str]:
    return [segment for segment in path.split("/") if segment]


def _matches_exclude_pattern(path: str, pattern: str) -> bool:
    if fnmatch.fnmatch(path, pattern):
        return True
    if not pattern.startswith("*") and fnmatch.fnmatch(path, f"*{pattern}"):
        return True
    return False


def is_vault_path(
    path: str | Path,
    *,
    exclude_list: Sequence[str] = DEFAULT_VAULT_EXCLUDE_LIST,
) -> bool:
    normalized = _normalize_path(path)
    segments = _path_segments(normalized)

    if normalized.startswith("/mnt/c/OpenClawLegalPrivate"):
        return True
    if any(
        segment.endswith(("LegalPrivate", "FinancePrivate", "MusicLawPrivate"))
        for segment in segments
    ):
        return True
    if ".chief.env" in segments:
        return True
    if ".google-secrets" in segments:
        return True

    return any(_matches_exclude_pattern(normalized, pattern) for pattern in exclude_list)


def assert_safe_path(
    path: str | Path,
    *,
    peer: Peer | None = None,
    exclude_list: Sequence[str] | None = None,
) -> None:
    excludes = tuple(exclude_list or ()) + tuple(
        peer.vault_exclude_list if peer is not None else DEFAULT_VAULT_EXCLUDE_LIST
    )
    if is_vault_path(path, exclude_list=excludes):
        raise VaultPathError(f"fabric operation refused vault/secret path: {path}")


def _quote_remote_path(path: str | Path) -> str:
    value = _normalize_path(path)
    if value == "~":
        return "~"
    if value.startswith("~/"):
        remainder = value[2:]
        return "~/" + shlex.quote(remainder)
    return shlex.quote(value)


def _run_checked(
    cmd: list[str],
    *,
    runner: Runner = subprocess.run,
    cwd: str | Path | None = None,
) -> subprocess.CompletedProcess[str]:
    completed = runner(
        cmd,
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise PeerCommandError(
            f"command failed ({completed.returncode}): {' '.join(cmd)}\n"
            f"{completed.stderr}"
        )
    return completed


def ssh_read(
    peer_name: str,
    remote_path: str | Path,
    *,
    registry_path: str | Path = DEFAULT_REGISTRY_PATH,
    runner: Runner = subprocess.run,
) -> str:
    peer = resolve_peer(peer_name, registry_path=registry_path)
    assert_safe_path(remote_path, peer=peer)
    remote_cmd = f"cat -- {_quote_remote_path(remote_path)}"
    completed = _run_checked(["ssh", peer.mdns_hostname, remote_cmd], runner=runner)
    return completed.stdout


def peer_git_fetch(
    peer_name: str,
    repo_path: str | Path,
    *,
    remote: str = "origin",
    registry_path: str | Path = DEFAULT_REGISTRY_PATH,
    runner: Runner = subprocess.run,
) -> subprocess.CompletedProcess[str]:
    peer = resolve_peer(peer_name, registry_path=registry_path)
    assert_safe_path(repo_path, peer=peer)
    remote_cmd = f"git -C {_quote_remote_path(repo_path)} fetch {shlex.quote(remote)}"
    return _run_checked(["ssh", peer.mdns_hostname, remote_cmd], runner=runner)


def peer_git_push(
    peer_name: str,
    repo_path: str | Path,
    branch: str,
    *,
    remote: str = "origin",
    registry_path: str | Path = DEFAULT_REGISTRY_PATH,
    runner: Runner = subprocess.run,
) -> subprocess.CompletedProcess[str]:
    if branch.startswith("-"):
        raise ValueError("branch names for fabric git push must not start with '-'")
    peer = resolve_peer(peer_name, registry_path=registry_path)
    assert_safe_path(repo_path, peer=peer)
    remote_cmd = (
        f"git -C {_quote_remote_path(repo_path)} push "
        f"{shlex.quote(remote)} {shlex.quote(branch)}"
    )
    return _run_checked(["ssh", peer.mdns_hostname, remote_cmd], runner=runner)


def git_push(
    branch: str,
    *,
    remote: str = "origin",
    cwd: str | Path | None = None,
    runner: Runner = subprocess.run,
) -> subprocess.CompletedProcess[str]:
    if branch.startswith("-"):
        raise ValueError("branch names for git push must not start with '-'")
    return _run_checked(["git", "push", remote, branch], cwd=cwd, runner=runner)


def git_fetch(
    *,
    remote: str = "origin",
    cwd: str | Path | None = None,
    runner: Runner = subprocess.run,
) -> subprocess.CompletedProcess[str]:
    return _run_checked(["git", "fetch", remote], cwd=cwd, runner=runner)
