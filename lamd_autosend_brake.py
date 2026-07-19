"""Root broker for the persistent LAMD unattended-send emergency brake."""

from __future__ import annotations

import argparse
import json
import os
import socket
import stat
import struct
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


SCHEMA_VERSION = "fleet_freeze_state_v1"
CLEAR = "PLANNED"
TRIPPED = "FROZEN"
DEFAULT_STATE_PATH = Path("/var/lib/openclaw-authority/lamd-autosend-brake.json")
DEFAULT_SOCKET_PATH = Path("/run/openclaw-authority/lamd-autosend-brake.sock")
DEFAULT_GUARDIAN_CGROUP = (
    "/user.slice/user-1000.slice/user@1000.service/app.slice/"
    "chief-guardian-listener.service"
)


def _stable_json(value: Any) -> str:
    return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass(frozen=True)
class PeerIdentity:
    uid: int
    pid: int
    cgroups: tuple[str, ...]


def read_peer_cgroups(pid: int) -> tuple[str, ...]:
    raw = Path(f"/proc/{int(pid)}/cgroup").read_text(encoding="utf-8")
    result: list[str] = []
    for line in raw.splitlines():
        pieces = line.split(":", 2)
        if len(pieces) == 3 and pieces[2].startswith("/"):
            result.append(pieces[2])
    return tuple(result)


def authorize_peer(
    peer: PeerIdentity,
    *,
    command: str,
    actor: str,
    guardian_uid: int,
    guardian_cgroup: str = DEFAULT_GUARDIAN_CGROUP,
) -> bool:
    if actor == "operator":
        return peer.uid == 0 and command in {"trip", "clear"}
    if actor == "guardian":
        return (
            command == "trip"
            and peer.uid == int(guardian_uid)
            and peer.cgroups == (guardian_cgroup,)
        )
    return False


class BrakeStateStore:
    def __init__(self, path: str | Path = DEFAULT_STATE_PATH, *, writer_uid: int = 0):
        self.path = Path(path)
        self.writer_uid = int(writer_uid)

    def _assert_safe_metadata(self) -> os.stat_result:
        try:
            metadata = os.lstat(self.path)
        except OSError as exc:
            raise ValueError("brake state unavailable") from exc
        if not stat.S_ISREG(metadata.st_mode) or stat.S_ISLNK(metadata.st_mode):
            raise ValueError("unsafe brake state type")
        if metadata.st_uid != self.writer_uid or metadata.st_mode & 0o022:
            raise ValueError("unsafe brake state ownership or mode")
        return metadata

    def read(self) -> dict[str, Any]:
        metadata = self._assert_safe_metadata()
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
        try:
            fd = os.open(self.path, flags)
            try:
                opened = os.fstat(fd)
                if (opened.st_dev, opened.st_ino) != (metadata.st_dev, metadata.st_ino):
                    raise ValueError("brake state changed during read")
                raw = os.read(fd, 65537)
            finally:
                os.close(fd)
            if len(raw) > 65536:
                raise ValueError("brake state oversized")
            payload = json.loads(raw.decode("utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("brake state is not an object")
            if payload.get("schema_version") != SCHEMA_VERSION:
                raise ValueError("brake state schema changed")
            if payload.get("state") not in {CLEAR, TRIPPED}:
                raise ValueError("brake state is unknown")
            if int(payload.get("generation") or 0) < 1:
                raise ValueError("brake generation is invalid")
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError) as exc:
            if isinstance(exc, ValueError) and str(exc).startswith("unsafe brake state"):
                raise
            raise ValueError("invalid brake state") from exc
        return payload

    def _write(self, *, state: str, actor: str, reason: str, generation: int) -> dict[str, Any]:
        if os.geteuid() != self.writer_uid:
            raise PermissionError("brake state writer is not the configured privileged uid")
        if state not in {CLEAR, TRIPPED}:
            raise ValueError("unknown brake state")
        actor = " ".join(str(actor).split())
        reason = " ".join(str(reason).split())
        if not actor or not reason or len(actor) > 80 or len(reason) > 500:
            raise ValueError("actor and bounded reason are required")
        payload = {
            "schema_version": SCHEMA_VERSION,
            "state": state,
            "generation": int(generation),
            "set_by": actor,
            "reason": reason,
            "updated_at": _now(),
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_name(f".{self.path.name}.{os.getpid()}.tmp")
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o644)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(_stable_json(payload))
                handle.flush()
                os.fsync(handle.fileno())
            os.chmod(temporary, 0o644, follow_symlinks=False)
            os.replace(temporary, self.path)
            directory_fd = os.open(self.path.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        finally:
            try:
                temporary.unlink()
            except FileNotFoundError:
                pass
        return payload

    def initialize_clear(self, *, actor: str, reason: str) -> dict[str, Any]:
        if self.path.exists() or self.path.is_symlink():
            return self.read()
        return self._write(state=CLEAR, actor=actor, reason=reason, generation=1)

    def trip(self, *, actor: str, reason: str) -> dict[str, Any]:
        current = self.read()
        if current["state"] == TRIPPED:
            return current
        return self._write(
            state=TRIPPED,
            actor=actor,
            reason=reason,
            generation=int(current["generation"]) + 1,
        )

    def clear(self, *, actor: str, reason: str) -> dict[str, Any]:
        current = self.read()
        if current["state"] == CLEAR:
            return current
        return self._write(
            state=CLEAR,
            actor=actor,
            reason=reason,
            generation=int(current["generation"]) + 1,
        )


class BrakeBroker:
    def __init__(
        self,
        store: BrakeStateStore,
        *,
        guardian_uid: int,
        guardian_cgroup: str = DEFAULT_GUARDIAN_CGROUP,
    ):
        self.store = store
        self.guardian_uid = int(guardian_uid)
        self.guardian_cgroup = guardian_cgroup

    def handle(self, request: Mapping[str, Any], peer: PeerIdentity) -> dict[str, Any]:
        command = str(request.get("command") or "").casefold()
        actor = str(request.get("actor") or "").casefold()
        if command == "status":
            try:
                return {"ok": True, "state": self.store.read()}
            except ValueError as exc:
                return {"ok": False, "error": str(exc), "fail_closed": True}
        if command not in {"trip", "clear"}:
            return {"ok": False, "error": "unknown_command"}
        if not authorize_peer(
            peer,
            command=command,
            actor=actor,
            guardian_uid=self.guardian_uid,
            guardian_cgroup=self.guardian_cgroup,
        ):
            return {"ok": False, "error": "peer_not_authorized"}
        reason = " ".join(str(request.get("reason") or "").split())
        if not reason or len(reason) > 500:
            return {"ok": False, "error": "bounded_reason_required"}
        state = (
            self.store.trip(actor=actor, reason=reason)
            if command == "trip"
            else self.store.clear(actor=actor, reason=reason)
        )
        return {"ok": True, "state": state}


def _peer_from_connection(connection: socket.socket) -> PeerIdentity:
    raw = connection.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i"))
    pid, uid, _gid = struct.unpack("3i", raw)
    try:
        cgroups = read_peer_cgroups(pid)
    except OSError:
        cgroups = ()
    return PeerIdentity(uid=uid, pid=pid, cgroups=cgroups)


def serve(
    *,
    state_path: str | Path = DEFAULT_STATE_PATH,
    socket_path: str | Path = DEFAULT_SOCKET_PATH,
    guardian_uid: int = 1000,
    socket_gid: int = 1000,
) -> None:
    store = BrakeStateStore(state_path)
    store.read()  # Missing/corrupt/unsafe state prevents the broker from starting.
    broker = BrakeBroker(store, guardian_uid=guardian_uid)
    path = Path(socket_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() or path.is_symlink():
        path.unlink()
    server = socket.socket(socket.AF_UNIX, socket.SOCK_SEQPACKET)
    try:
        server.bind(str(path))
        os.chown(path, 0, int(socket_gid), follow_symlinks=False)
        os.chmod(path, 0o660, follow_symlinks=False)
        server.listen(16)
        while True:
            connection, _address = server.accept()
            with connection:
                try:
                    raw = connection.recv(4097)
                    if len(raw) > 4096:
                        response = {"ok": False, "error": "request_too_large"}
                    else:
                        request = json.loads(raw.decode("utf-8"))
                        if not isinstance(request, dict):
                            raise ValueError("request_not_object")
                        response = broker.handle(request, _peer_from_connection(connection))
                except Exception as exc:
                    response = {"ok": False, "error": f"invalid_request:{type(exc).__name__}"}
                connection.sendall(_stable_json(response).encode("utf-8"))
    finally:
        server.close()
        try:
            path.unlink()
        except FileNotFoundError:
            pass


def request_broker(
    command: str,
    *,
    actor: str,
    reason: str = "",
    socket_path: str | Path = DEFAULT_SOCKET_PATH,
) -> dict[str, Any]:
    request = {"command": command, "actor": actor, "reason": reason}
    client = socket.socket(socket.AF_UNIX, socket.SOCK_SEQPACKET)
    try:
        client.connect(str(socket_path))
        client.sendall(json.dumps(request, sort_keys=True).encode("utf-8"))
        raw = client.recv(65537)
    finally:
        client.close()
    result = json.loads(raw.decode("utf-8"))
    if not isinstance(result, dict):
        raise RuntimeError("brake broker returned a non-object")
    return result


def guardian_trip(reason: str, *, socket_path: str | Path = DEFAULT_SOCKET_PATH) -> dict[str, Any]:
    """Trip-only local helper; intentionally not registered on any message handler."""
    return request_broker("trip", actor="guardian", reason=reason, socket_path=socket_path)


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    init_parser = subparsers.add_parser("init")
    init_parser.add_argument("--reason", required=True)
    server_parser = subparsers.add_parser("serve")
    server_parser.add_argument("--guardian-uid", type=int, default=1000)
    server_parser.add_argument("--socket-gid", type=int, default=1000)
    for name in ("status", "trip", "clear"):
        child = subparsers.add_parser(name)
        child.add_argument("--reason", default="")
    args = parser.parse_args()
    if args.command == "init":
        state = BrakeStateStore().initialize_clear(actor="installer", reason=args.reason)
        print(_stable_json({"ok": True, "state": state}), end="")
        return 0
    if args.command == "serve":
        serve(guardian_uid=args.guardian_uid, socket_gid=args.socket_gid)
        return 0
    result = request_broker(args.command, actor="operator", reason=args.reason)
    print(_stable_json(result), end="")
    return 0 if result.get("ok") is True else 2


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "BrakeBroker",
    "BrakeStateStore",
    "PeerIdentity",
    "authorize_peer",
    "guardian_trip",
    "request_broker",
    "serve",
]
