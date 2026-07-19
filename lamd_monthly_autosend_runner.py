#!/usr/bin/env python3
"""Disabled-by-default runner for the bounded LAMD monthly transaction."""

from __future__ import annotations

import argparse
import json
import os
import stat
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

from ar_gig_to_cash_store import DEFAULT_DB_PATH as DEFAULT_G2C_DB_PATH
from lamd_autosend_live_adapter import (
    DEFAULT_ARTIFACT_ROOT,
    DEFAULT_SCOPE_CONFIG_PATH,
    DEFAULT_SEND_HOLD_PATH,
    GovernedGmailProvider,
    ScopeConfigError,
    StandingSendHoldAdmission,
    load_scope_config,
)
from lamd_monthly_autosend import (
    AutosendPolicy,
    GigToCashLedgerAdapter,
    LamdMonthlyCycleStore,
    run_monthly_cycle,
    validate_package,
)
from lamd_monthly_package_publisher import (
    PackagePublicationError,
    publish_monthly_package,
)


DEFAULT_CYCLES_PATH = Path("/home/openclaw/state/lamd_autosend/monthly_cycles.sqlite3")
DEFAULT_GRADUATION_DIR = Path("/home/openclaw/state/lamd_autosend/graduations")
DEFAULT_RECEIPT_DIR = Path("/home/openclaw/state/lamd_autosend/receipts")
MAX_PACKAGE_BYTES = 262_144


def default_package_path(now: datetime, *, artifact_root: str | Path = DEFAULT_ARTIFACT_ROOT) -> Path:
    return Path(artifact_root) / now.astimezone(timezone.utc).strftime("%Y-%m") / "lamd_monthly_autosend_package.json"


def _load_package(path: Path) -> dict[str, Any]:
    try:
        metadata = os.lstat(path)
    except OSError as exc:
        raise ValueError("monthly package unavailable") from exc
    if not stat.S_ISREG(metadata.st_mode) or stat.S_ISLNK(metadata.st_mode):
        raise ValueError("monthly package is not a regular file")
    if metadata.st_size > MAX_PACKAGE_BYTES:
        raise ValueError("monthly package is oversized")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(path, flags)
        try:
            opened = os.fstat(fd)
            if (opened.st_dev, opened.st_ino) != (metadata.st_dev, metadata.st_ino):
                raise ValueError("monthly package changed during read")
            raw = os.read(fd, MAX_PACKAGE_BYTES + 1)
        finally:
            os.close(fd)
        if len(raw) > MAX_PACKAGE_BYTES:
            raise ValueError("monthly package is oversized")
        value = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("monthly package is invalid") from exc
    if not isinstance(value, dict):
        raise ValueError("monthly package is not an object")
    return validate_package(value)


def _write_receipt(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(temporary, flags, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(dict(payload), handle, indent=2, sort_keys=True, ensure_ascii=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        directory_fd = os.open(path.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def _production_freeze_guard():
    from lamd_autosend_brake import DEFAULT_STATE_PATH
    from openclaw_authority.freeze_guard import FreezeGuard

    return FreezeGuard(DEFAULT_STATE_PATH, enabled=True, expected_uid=0)


def _production_broker_call(agent: str, capability: str, params: dict[str, Any]) -> Mapping[str, Any]:
    from google_access_broker import call

    return call(agent, capability, params)


def run_once(
    *,
    execute: bool,
    now: datetime | None = None,
    package_path: str | Path | None = None,
    scope_config_path: str | Path = DEFAULT_SCOPE_CONFIG_PATH,
    cycles_path: str | Path = DEFAULT_CYCLES_PATH,
    ledger_path: str | Path = DEFAULT_G2C_DB_PATH,
    graduation_dir: str | Path = DEFAULT_GRADUATION_DIR,
    receipt_dir: str | Path = DEFAULT_RECEIPT_DIR,
    send_hold_path: str | Path = DEFAULT_SEND_HOLD_PATH,
    artifact_root: str | Path = DEFAULT_ARTIFACT_ROOT,
    expected_config_uid: int = 0,
    freeze_guard=None,
    broker_call: Callable[[str, str, dict[str, Any]], Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    observed_at = now or datetime.now(timezone.utc)
    if observed_at.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    resolved_package_path = Path(package_path) if package_path is not None else default_package_path(
        observed_at, artifact_root=artifact_root
    )
    if not execute:
        return {
            "status": "PLAN_ONLY",
            "execute": False,
            "package_path": str(resolved_package_path),
            "provider_called": False,
            "ledger_posted": False,
            "state_changed": False,
        }
    if not resolved_package_path.exists() and not resolved_package_path.is_symlink():
        try:
            publish_monthly_package(
                resolved_package_path.parent,
                output_path=resolved_package_path,
            )
        except PackagePublicationError as exc:
            return {
                "status": "BLOCKED_PACKAGE_UNAVAILABLE",
                "reason": str(exc),
                "package_path": str(resolved_package_path),
                "provider_called": False,
                "ledger_posted": False,
            }
    try:
        package = _load_package(resolved_package_path)
    except ValueError as exc:
        return {
            "status": "BLOCKED_PACKAGE_UNAVAILABLE",
            "reason": str(exc),
            "package_path": str(resolved_package_path),
            "provider_called": False,
            "ledger_posted": False,
        }
    try:
        config = load_scope_config(
            scope_config_path,
            expected_uid=expected_config_uid,
            require_armed=False,
        )
    except ScopeConfigError as exc:
        return {
            "status": "BLOCKED_SCOPE_CONFIG_INVALID",
            "reason": str(exc),
            "provider_called": False,
            "ledger_posted": False,
        }
    service_month = str(package["service_month"])
    package_sha = str(package["package_sha256"])
    graduation_path = Path(graduation_dir) / f"{service_month}-{package_sha[:16]}.json"
    provider = GovernedGmailProvider(
        scope_config_path=scope_config_path,
        send_hold_path=send_hold_path,
        graduation_path=graduation_path,
        broker_call=broker_call or _production_broker_call,
        artifact_root=artifact_root,
        expected_config_uid=expected_config_uid,
        now_fn=lambda: observed_at,
    )
    result = run_monthly_cycle(
        now=observed_at,
        package=package,
        policy=AutosendPolicy(
            armed=bool(config["armed"]),
            operator_stop=bool(config["operator_stop"]),
        ),
        store=LamdMonthlyCycleStore(cycles_path),
        freeze_guard=freeze_guard or _production_freeze_guard(),
        send_hold_admission=StandingSendHoldAdmission(
            scope_config_path=scope_config_path,
            send_hold_path=send_hold_path,
            expected_config_uid=expected_config_uid,
        ),
        provider=provider,
        ledger=GigToCashLedgerAdapter(ledger_path),
    )
    receipt = {
        "schema_version": "lamd_monthly_autosend_run_receipt_v1",
        **result,
        "package_path": str(resolved_package_path),
        "package_sha256": package_sha,
        "observed_at": observed_at.astimezone(timezone.utc).isoformat(timespec="seconds"),
    }
    receipt_path = Path(receipt_dir) / f"{service_month}-{package_sha[:16]}.json"
    _write_receipt(receipt_path, receipt)
    return {**result, "receipt_path": str(receipt_path)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    result = run_once(execute=args.execute)
    print(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=True))
    return 0 if result.get("status") not in {"BLOCKED_PACKAGE_UNAVAILABLE", "BLOCKED_SCOPE_CONFIG_INVALID"} else 2


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "DEFAULT_CYCLES_PATH",
    "DEFAULT_GRADUATION_DIR",
    "DEFAULT_RECEIPT_DIR",
    "default_package_path",
    "run_once",
]
