"""Pytest-only sandbox for blocking live OpenClaw runtime side effects.

This module is intentionally imported from ``conftest.py`` only.  Runtime code
must not depend on it.
"""

from __future__ import annotations

import builtins
import os
import socket
import sqlite3
import subprocess
import sys
from pathlib import Path
from typing import Any
from urllib.parse import unquote


class OpenClawTestSandboxViolation(RuntimeError):
    """Raised when a test tries to touch live runtime infrastructure."""


class _GuardedSysPath(list):
    """List wrapper that prevents pytest from importing from the live checkout."""

    def __init__(self, sandbox: "OpenClawPytestSandbox", values: list[str]):
        self._sandbox = sandbox
        super().__init__(value for value in values if not sandbox.is_blocked_import_path(value))

    def insert(self, index: int, value: object) -> None:
        if not self._sandbox.is_blocked_import_path(value):
            super().insert(index, value)

    def append(self, value: object) -> None:
        if not self._sandbox.is_blocked_import_path(value):
            super().append(value)

    def extend(self, values: object) -> None:
        for value in values:  # type: ignore[union-attr]
            self.append(value)

    def __setitem__(self, index, value):  # type: ignore[no-untyped-def]
        if isinstance(index, slice):
            super().__setitem__(
                index,
                [item for item in value if not self._sandbox.is_blocked_import_path(item)],
            )
            return
        if not self._sandbox.is_blocked_import_path(value):
            super().__setitem__(index, value)


class OpenClawPytestSandbox:
    """Central guard for pytest live-runtime isolation."""

    def __init__(self, repo_root: Path):
        self.repo_root = repo_root.resolve(strict=False)
        self.sandbox_root = self.repo_root / ".pytest_openclaw"
        self.redirect_root = self.sandbox_root / "live_path_redirects"
        self.isolated_ledger = self.sandbox_root / "business_ops" / "ledger.sqlite"
        self.isolated_expense_log = self.sandbox_root / "logs" / "expense_log.json"
        self.isolated_google_token = self.sandbox_root / "secrets" / "token.json"
        self.isolated_mac_response_bridge = self.sandbox_root / "mission_control_responses" / "to_mac"
        self.isolated_send_hold = self.redirect_root / "mnt_e" / "openclaw" / "orchestration" / "SEND_HOLD.md"

        self.live_business_ledger = Path("/home/openclaw/.openclaw/business_ops/ledger.sqlite").resolve(strict=False)
        self.live_home_root = Path("/home/openclaw").resolve(strict=False)
        self.live_mnt_c_root = Path("/mnt/c").resolve(strict=False)
        self.live_mnt_e_root = Path("/mnt/e").resolve(strict=False)
        self.live_mac_response_bridge = Path("/mnt/e/openclaw/mission_control_responses/to_mac").resolve(strict=False)
        self.live_mac_generated_read_models = Path("/mnt/e/openclaw/generated/read_models").resolve(strict=False)

        self._installed = False
        self._original_sqlite_connect = sqlite3.connect
        self._original_builtins_open = builtins.open
        self._original_path_open = Path.open
        self._original_path_exists = Path.exists
        self._original_path_is_file = Path.is_file
        self._original_path_is_dir = Path.is_dir
        self._original_path_mkdir = Path.mkdir
        self._original_os_mkdir = os.mkdir
        self._original_os_makedirs = os.makedirs
        self._original_os_replace = os.replace
        self._original_os_rename = os.rename
        self._original_socket_create_connection = socket.create_connection
        self._original_socket_connect = socket.socket.connect
        self._original_subprocess_popen = subprocess.Popen

    def install(self) -> None:
        if self._installed:
            return
        os.environ["OPENCLAW_LEDGER_PATH"] = str(self.isolated_ledger)
        os.environ["OPENCLAW_EXPENSE_LOG_PATH"] = str(self.isolated_expense_log)
        os.environ["OPENCLAW_GOOGLE_TOKEN_FILE"] = str(self.isolated_google_token)
        os.environ["OPENCLAW_RESPONSE_BRIDGE_ROOT"] = str(self.isolated_mac_response_bridge)
        os.environ["OPENCLAW_TEST_REPO_ROOT"] = str(self.repo_root)
        os.environ["OPENCLAW_TEST_MODE"] = "1"
        os.environ["OPENCLAW_SEND_HOLD"] = "1"
        os.environ["OPENCLAW_NETWORK_DISABLED"] = "1"
        os.environ["OPENCLAW_LIVE_RUNTIME_DISABLED"] = "1"
        os.environ["GIT_TERMINAL_PROMPT"] = "0"
        os.environ["GIT_SSH_COMMAND"] = "ssh -oBatchMode=yes"
        os.environ.setdefault("PII_VAULT_KEY", "pytest-local-placeholder")

        self.isolated_expense_log.parent.mkdir(parents=True, exist_ok=True)
        self.isolated_google_token.parent.mkdir(parents=True, exist_ok=True)
        if not self.isolated_expense_log.exists():
            self.isolated_expense_log.write_text("[]\n", encoding="utf-8")
        if not self.isolated_google_token.exists():
            self.isolated_google_token.write_text("{}\n", encoding="utf-8")
        self.isolated_send_hold.parent.mkdir(parents=True, exist_ok=True)
        if not self.isolated_send_hold.exists():
            self.isolated_send_hold.write_text("SEND_HOLD active for pytest sandbox.\n", encoding="utf-8")

        sandbox = self

        def guarded_path_open(target: Path, *args: object, **kwargs: object):
            return sandbox._guarded_path_open(target, *args, **kwargs)

        def guarded_path_exists(target: Path):
            return sandbox._guarded_path_exists(target)

        def guarded_path_is_file(target: Path):
            return sandbox._guarded_path_is_file(target)

        def guarded_path_is_dir(target: Path):
            return sandbox._guarded_path_is_dir(target)

        def guarded_path_mkdir(target: Path, *args: object, **kwargs: object):
            return sandbox._guarded_path_mkdir(target, *args, **kwargs)

        def guarded_socket_connect(sock: socket.socket, address: object):
            return sandbox._guarded_socket_connect(sock, address)

        sqlite3.connect = self._guarded_sqlite_connect  # type: ignore[method-assign]
        builtins.open = self._guarded_open  # type: ignore[assignment]
        Path.open = guarded_path_open  # type: ignore[method-assign]
        Path.exists = guarded_path_exists  # type: ignore[method-assign]
        Path.is_file = guarded_path_is_file  # type: ignore[method-assign]
        Path.is_dir = guarded_path_is_dir  # type: ignore[method-assign]
        Path.mkdir = guarded_path_mkdir  # type: ignore[method-assign]
        os.mkdir = self._guarded_os_mkdir  # type: ignore[assignment]
        os.makedirs = self._guarded_os_makedirs  # type: ignore[assignment]
        os.replace = self._guarded_os_replace  # type: ignore[assignment]
        os.rename = self._guarded_os_rename  # type: ignore[assignment]
        socket.create_connection = self._guarded_create_connection  # type: ignore[assignment]
        socket.socket.connect = guarded_socket_connect  # type: ignore[method-assign]
        subprocess.Popen = self._guarded_popen  # type: ignore[assignment]
        if not isinstance(sys.path, _GuardedSysPath):
            sys.path = _GuardedSysPath(self, list(sys.path))
        self.enforce_import_path()
        self._installed = True

    def is_blocked_import_path(self, value: object) -> bool:
        try:
            text = os.fspath(value)  # type: ignore[arg-type]
        except TypeError:
            return False
        if isinstance(text, bytes):
            text = text.decode("utf-8", errors="ignore")
        try:
            resolved = Path(str(text)).expanduser().resolve(strict=False)
        except OSError:
            return False
        if resolved == self.repo_root:
            return False
        blocked = {
            self.live_home_root,
            self.live_home_root / "tools",
        }
        return resolved in blocked

    def enforce_import_path(self) -> None:
        """Keep pytest imports anchored to this worktree, not the live checkout."""
        repo = str(self.repo_root)
        sys.path[:] = [
            item
            for item in sys.path
            if not self.is_blocked_import_path(item)
        ]
        if repo in sys.path:
            sys.path.remove(repo)
        sys.path.insert(0, repo)

    def _resolved_path(self, value: object) -> Path | None:
        try:
            raw = os.fspath(value)  # type: ignore[arg-type]
        except TypeError:
            return None
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8", errors="ignore")
        try:
            return Path(str(raw)).expanduser().resolve(strict=False)
        except OSError:
            return None

    def _path_from_sqlite_database_arg(self, database: object) -> Path | None:
        if database in (":memory:", b":memory:"):
            return None
        try:
            raw = os.fspath(database)  # type: ignore[arg-type]
        except TypeError:
            return None
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8", errors="ignore")
        value = str(raw)
        if not value or value == ":memory:":
            return None
        if value.startswith("file:"):
            value = value[5:].split("?", 1)[0]
            value = unquote(value)
        return self._resolved_path(value)

    @staticmethod
    def _is_write_mode(mode: object) -> bool:
        text = str(mode or "r")
        return any(flag in text for flag in ("w", "a", "x", "+"))

    @staticmethod
    def _is_relative_to(path: Path, root: Path) -> bool:
        try:
            path.relative_to(root)
            return True
        except ValueError:
            return False

    def _shadow_path_for_live_path(self, path: Path | None) -> Path | None:
        if path is None:
            return None
        if self._is_relative_to(path, self.repo_root):
            return None
        roots = (
            ("home_openclaw", self.live_home_root),
            ("mnt_c", self.live_mnt_c_root),
            ("mnt_e", self.live_mnt_e_root),
        )
        for label, root in roots:
            if self._is_relative_to(path, root):
                rel = path.relative_to(root)
                return self.redirect_root / label / rel
        return None

    def _mapped_path_for_open(self, path: Path | None, *, write_mode: bool) -> Path | None:
        shadow = self._shadow_path_for_live_path(path)
        if shadow is None:
            return None
        if write_mode:
            shadow.parent.mkdir(parents=True, exist_ok=True)
            return shadow
        if shadow.exists():
            return shadow
        if path and self._is_relative_to(path, self.live_mac_generated_read_models):
            rel = path.relative_to(self.live_mac_generated_read_models)
            local_read_model = self.repo_root / "generated" / "read_models" / rel
            if local_read_model.exists():
                return local_read_model
            # Runtime code often probes the Mac mirror as an optional fallback.
            # In pytest, make that probe look like a missing local artifact
            # instead of ever reading the live bridge.
            raise FileNotFoundError(path)
        if path and self._is_relative_to(path, self.live_mac_response_bridge):
            raise OpenClawTestSandboxViolation(
                f"pytest attempted to read the live Mac response bridge: {path}"
            )
        return None

    def _mapped_path_for_stat(self, path: Path | None) -> Path | None:
        shadow = self._shadow_path_for_live_path(path)
        if shadow is None:
            return None
        if self._original_path_exists(shadow):
            return shadow
        if path and self._is_relative_to(path, self.live_mac_generated_read_models):
            rel = path.relative_to(self.live_mac_generated_read_models)
            local_read_model = self.repo_root / "generated" / "read_models" / rel
            return local_read_model if self._original_path_exists(local_read_model) else shadow
        return shadow

    def _guarded_open(self, file: object, *args: object, **kwargs: object):
        mode = args[0] if args else kwargs.get("mode", "r")
        path = self._resolved_path(file)
        mapped = self._mapped_path_for_open(path, write_mode=self._is_write_mode(mode))
        if mapped is not None:
            return self._original_builtins_open(mapped, *args, **kwargs)
        return self._original_builtins_open(file, *args, **kwargs)

    def _guarded_path_open(self, target: Path, *args: object, **kwargs: object):
        mode = args[0] if args else kwargs.get("mode", "r")
        path = target.resolve(strict=False)
        mapped = self._mapped_path_for_open(path, write_mode=self._is_write_mode(mode))
        if mapped is not None:
            return self._original_path_open(mapped, *args, **kwargs)
        return self._original_path_open(target, *args, **kwargs)

    def _guarded_path_exists(self, target: Path) -> bool:
        path = target.resolve(strict=False)
        mapped = self._mapped_path_for_stat(path)
        if mapped is not None:
            return self._original_path_exists(mapped)
        return self._original_path_exists(target)

    def _guarded_path_is_file(self, target: Path) -> bool:
        path = target.resolve(strict=False)
        mapped = self._mapped_path_for_stat(path)
        if mapped is not None:
            return self._original_path_is_file(mapped)
        return self._original_path_is_file(target)

    def _guarded_path_is_dir(self, target: Path) -> bool:
        path = target.resolve(strict=False)
        mapped = self._mapped_path_for_stat(path)
        if mapped is not None:
            return self._original_path_is_dir(mapped)
        return self._original_path_is_dir(target)

    def _guarded_path_mkdir(self, target: Path, *args: object, **kwargs: object):
        path = target.resolve(strict=False)
        shadow = self._shadow_path_for_live_path(path)
        if shadow is not None:
            return self._original_path_mkdir(shadow, *args, **kwargs)
        return self._original_path_mkdir(target, *args, **kwargs)

    def _guarded_os_mkdir(self, path: object, mode: int = 0o777, *args: object, **kwargs: object):
        resolved = self._resolved_path(path)
        shadow = self._shadow_path_for_live_path(resolved)
        if shadow is not None:
            return self._original_os_mkdir(shadow, mode, *args, **kwargs)
        return self._original_os_mkdir(path, mode, *args, **kwargs)

    def _guarded_os_makedirs(
        self,
        name: object,
        mode: int = 0o777,
        exist_ok: bool = False,
    ):
        resolved = self._resolved_path(name)
        shadow = self._shadow_path_for_live_path(resolved)
        if shadow is not None:
            return self._original_os_makedirs(shadow, mode=mode, exist_ok=exist_ok)
        return self._original_os_makedirs(name, mode=mode, exist_ok=exist_ok)

    def _mapped_path_for_mutation(self, path: object) -> object:
        resolved = self._resolved_path(path)
        shadow = self._shadow_path_for_live_path(resolved)
        if shadow is None:
            return path
        shadow.parent.mkdir(parents=True, exist_ok=True)
        return shadow

    def _guarded_os_replace(self, src: object, dst: object, *args: object, **kwargs: object):
        mapped_src = self._mapped_path_for_mutation(src)
        mapped_dst = self._mapped_path_for_mutation(dst)
        return self._original_os_replace(mapped_src, mapped_dst, *args, **kwargs)

    def _guarded_os_rename(self, src: object, dst: object, *args: object, **kwargs: object):
        mapped_src = self._mapped_path_for_mutation(src)
        mapped_dst = self._mapped_path_for_mutation(dst)
        return self._original_os_rename(mapped_src, mapped_dst, *args, **kwargs)

    def _guarded_sqlite_connect(self, database: object, *args: object, **kwargs: object):
        target = self._path_from_sqlite_database_arg(database)
        if target == self.live_business_ledger:
            self.isolated_ledger.parent.mkdir(parents=True, exist_ok=True)
            return self._original_sqlite_connect(self.isolated_ledger, *args, **kwargs)
        shadow = self._shadow_path_for_live_path(target)
        if shadow is not None:
            shadow.parent.mkdir(parents=True, exist_ok=True)
            return self._original_sqlite_connect(shadow, *args, **kwargs)
        return self._original_sqlite_connect(database, *args, **kwargs)

    def _blocked_network_message(self, address: object) -> str:
        return f"pytest attempted live network/runtime access in OPENCLAW_TEST_MODE=1: {address!r}"

    def _guarded_create_connection(self, address: object, *args: object, **kwargs: object):
        raise OpenClawTestSandboxViolation(self._blocked_network_message(address))

    def _guarded_socket_connect(self, sock: socket.socket, address: object):
        raise OpenClawTestSandboxViolation(self._blocked_network_message(address))

    @staticmethod
    def _command_parts(args: object) -> list[str]:
        if isinstance(args, (str, bytes)):
            return [args.decode("utf-8", errors="ignore") if isinstance(args, bytes) else args]
        try:
            return [os.fspath(part) for part in args]  # type: ignore[arg-type]
        except TypeError:
            return [str(args)]

    @staticmethod
    def _git_ref_looks_local(ref: str) -> bool:
        value = str(ref)
        if value.startswith("file://"):
            return True
        if value.startswith(("/", "./", "../")):
            return True
        if "://" in value or value.startswith("git@") or ":" in value:
            return False
        return Path(value).exists()

    def _git_ls_remote_is_local_only(self, parts: list[str]) -> bool:
        refs: list[str] = []
        for part in parts[2:]:
            if part == "--":
                continue
            if part.startswith("-"):
                continue
            refs.append(part)
            break
        return bool(refs) and all(self._git_ref_looks_local(ref) for ref in refs)

    def _guarded_popen(self, args: object, *popen_args: object, **popen_kwargs: object):
        parts = self._command_parts(args)
        executable = Path(parts[0]).name.lower() if parts else ""
        blocked_executables = {
            "ollama",
            "curl",
            "wget",
            "ssh",
            "scp",
            "sftp",
            "nc",
            "ncat",
            "telnet",
        }
        if executable in blocked_executables:
            raise OpenClawTestSandboxViolation(
                f"pytest attempted to spawn live-runtime/network command: {' '.join(parts)}"
            )
        if executable == "git" and len(parts) > 1:
            network_subcommands = {
                "clone",
                "fetch",
                "pull",
                "push",
                "ls-remote",
                "submodule",
            }
            if parts[1] in network_subcommands:
                if parts[1] == "ls-remote" and self._git_ls_remote_is_local_only(parts):
                    return self._original_subprocess_popen(args, *popen_args, **popen_kwargs)
                raise OpenClawTestSandboxViolation(
                    f"pytest attempted to spawn git network command: {' '.join(parts)}"
                )
            if parts[1] == "remote" and len(parts) > 2 and parts[2] not in {"get-url", "-v", "--verbose"}:
                raise OpenClawTestSandboxViolation(
                    f"pytest attempted to mutate git remote configuration: {' '.join(parts)}"
                )
        return self._original_subprocess_popen(args, *popen_args, **popen_kwargs)


def install_pytest_sandbox(repo_root: Path) -> OpenClawPytestSandbox:
    sandbox = OpenClawPytestSandbox(repo_root)
    if os.environ.get("OPENCLAW_TEST_MODE", "1") == "1":
        sandbox.install()
    return sandbox
