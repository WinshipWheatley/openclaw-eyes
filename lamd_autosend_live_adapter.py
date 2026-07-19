"""Live-provider boundary for the operator-graduated LAMD monthly surface.

Importing this module cannot send.  The Gmail broker is called only by an explicit
``GovernedGmailProvider.send`` invocation after a root-owned standing-scope file,
the immutable monthly package, cadence, and scoped SEND_HOLD graduation all agree.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

from lamd_monthly_autosend import (
    AMOUNT_MINOR_UNITS,
    CLIENT_REF,
    CURRENCY,
    ELIGIBLE_DAY,
    RECIPIENT,
    STREAM,
    ProviderOutcomeUnknown,
    validate_package,
)
from send_hold_scoped_graduation import (
    ALLOWED_SENTINEL_MODES,
    issue_send_hold_scoped_graduation,
)


SCOPE_SCHEMA_VERSION = "lamd_autosend_scope_v1"
DEFAULT_SCOPE_CONFIG_PATH = Path("/var/lib/openclaw-authority/lamd-autosend-scope.json")
DEFAULT_SEND_HOLD_PATH = Path("/mnt/e/openclaw/orchestration/SEND_HOLD.md")
DEFAULT_ARTIFACT_ROOT = Path("/mnt/e/openclaw/artifacts/invoice_workbooks/live_arts_md")
MAX_CONFIG_BYTES = 65_536
MONTH_PATTERN = re.compile(r"^\d{4}-\d{2}$")


class ScopeConfigError(ValueError):
    """The standing LAMD scope is unavailable, unsafe, stopped, or changed."""


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _graduation_file_consumed(path: Path) -> bool:
    try:
        before = os.lstat(path)
        if (
            not stat.S_ISREG(before.st_mode)
            or stat.S_ISLNK(before.st_mode)
            or before.st_uid != os.geteuid()
            or before.st_mode & 0o077
            or before.st_size > MAX_CONFIG_BYTES
        ):
            return False
        fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        try:
            opened = os.fstat(fd)
            if (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino):
                return False
            raw = os.read(fd, MAX_CONFIG_BYTES + 1)
        finally:
            os.close(fd)
        if len(raw) > MAX_CONFIG_BYTES:
            return False
        value = json.loads(raw.decode("utf-8"))
        return bool(
            isinstance(value, dict)
            and value.get("status") == "CONSUMED"
            and int(value.get("use_count") or 0) == 1
            and str(value.get("consumed_at") or "").strip()
        )
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError):
        return False


def _read_metadata_bound_json(path: Path, *, expected_uid: int) -> dict[str, Any]:
    try:
        before = os.lstat(path)
    except OSError as exc:
        raise ScopeConfigError("standing scope config unavailable") from exc
    if (
        not stat.S_ISREG(before.st_mode)
        or stat.S_ISLNK(before.st_mode)
        or before.st_uid != int(expected_uid)
        or before.st_mode & 0o022
    ):
        raise ScopeConfigError("unsafe standing scope ownership or mode")
    if before.st_size > MAX_CONFIG_BYTES:
        raise ScopeConfigError("standing scope config oversized")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(path, flags)
        try:
            opened = os.fstat(fd)
            if (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino):
                raise ScopeConfigError("standing scope config changed during read")
            raw = os.read(fd, MAX_CONFIG_BYTES + 1)
        finally:
            os.close(fd)
        if len(raw) > MAX_CONFIG_BYTES:
            raise ScopeConfigError("standing scope config oversized")
        value = json.loads(raw.decode("utf-8"))
    except ScopeConfigError:
        raise
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ScopeConfigError("standing scope config invalid") from exc
    if not isinstance(value, dict):
        raise ScopeConfigError("standing scope config is not an object")
    return value


def load_scope_config(
    path: str | Path = DEFAULT_SCOPE_CONFIG_PATH,
    *,
    expected_uid: int = 0,
    require_armed: bool = False,
) -> dict[str, Any]:
    value = _read_metadata_bound_json(Path(path), expected_uid=expected_uid)
    expected = {
        "schema_version": SCOPE_SCHEMA_VERSION,
        "client_ref": CLIENT_REF,
        "stream": STREAM,
        "amount_minor_units": AMOUNT_MINOR_UNITS,
        "currency": CURRENCY,
        "recipient": RECIPIENT,
        "cadence_day": ELIGIBLE_DAY,
    }
    changed = [key for key, expected_value in expected.items() if value.get(key) != expected_value]
    if changed:
        raise ScopeConfigError("standing scope drift: " + ", ".join(changed))
    if type(value.get("armed")) is not bool or type(value.get("operator_stop")) is not bool:
        raise ScopeConfigError("standing scope authority flags are invalid")
    not_before = value.get("not_before_service_month")
    if not_before is not None and (
        not isinstance(not_before, str) or MONTH_PATTERN.fullmatch(not_before) is None
    ):
        raise ScopeConfigError("standing scope not-before service month is invalid")
    for field in ("standing_authority_ref", "authority_source_ref"):
        if not str(value.get(field) or "").strip():
            raise ScopeConfigError(f"standing scope {field} is required")
    if require_armed and value["armed"] is not True:
        raise ScopeConfigError("standing LAMD auto-send is not armed")
    if require_armed and value["operator_stop"] is True:
        raise ScopeConfigError("standing LAMD auto-send is operator-stopped")
    return value


def package_before_not_before_service_month(
    package: Mapping[str, Any],
    config: Mapping[str, Any],
) -> bool:
    not_before = config.get("not_before_service_month")
    return isinstance(not_before, str) and str(package.get("service_month") or "") < not_before


def _assert_package_matches_scope(package: Mapping[str, Any], config: Mapping[str, Any]) -> dict[str, Any]:
    bounded = validate_package(package)
    for field in ("client_ref", "stream", "amount_minor_units", "currency", "recipient"):
        if bounded.get(field) != config.get(field):
            raise ScopeConfigError(f"monthly package changed standing field: {field}")
    return bounded


def _artifacts_within_root(package: Mapping[str, Any], artifact_root: Path) -> bool:
    try:
        root = artifact_root.resolve(strict=True)
        workbook = Path(str(package["source_workbook_path"])).resolve(strict=True)
        pdf = Path(str(package["pdf_path"])).resolve(strict=True)
    except (KeyError, OSError):
        return False
    if not all(path == root or root in path.parents for path in (workbook, pdf)):
        return False
    return True


def build_exact_send_material(package: Mapping[str, Any]) -> dict[str, str]:
    bounded = validate_package(package)
    try:
        label = datetime.strptime(str(bounded["service_month"]), "%Y-%m").strftime("%B %Y")
    except ValueError as exc:
        raise ScopeConfigError("monthly package service month is invalid") from exc
    invoice_number = str(bounded["invoice_number"])
    subject = f"{invoice_number}: {label} Monthly Speaker Rental Invoice"
    body = (
        f"Hi Megan,\n\nAttached is Invoice {invoice_number} for {label}, covering the monthly "
        "speaker rental at $100.00.\n\nCould you send me a quick note once the invoice is in your "
        "accounting queue? That helps me know it landed and keeps our records straight.\n\n"
        "Warmly,\nClara Reid"
    )
    request_id = (
        f"lamd-autosend-exact-send:{bounded['service_month']}:"
        f"{str(bounded['package_sha256'])[:16]}"
    )
    payload_scope = {
        "request_id": request_id,
        "recipient": bounded["recipient"],
        "subject": subject,
        "body_sha256": _sha256_bytes(body.encode("utf-8")),
        "attachment_path": bounded["pdf_path"],
        "attachment_sha256": bounded["pdf_sha256"],
        "package_sha256": bounded["package_sha256"],
        "service_month": bounded["service_month"],
    }
    return {
        "request_id": request_id,
        "subject": subject,
        "body": body,
        "body_sha256": "sha256:" + payload_scope["body_sha256"],
        "payload_hash": "sha256:" + _sha256_bytes(_stable_json(payload_scope).encode("utf-8")),
    }


def _invalid(reason: str) -> dict[str, Any]:
    return {"valid": False, "reason": reason}


def verify_standing_send_context(
    agent: str,
    capability: str,
    params: Mapping[str, Any],
    *,
    now: datetime | None = None,
    scope_config_path: str | Path = DEFAULT_SCOPE_CONFIG_PATH,
    artifact_root: str | Path = DEFAULT_ARTIFACT_ROOT,
    expected_config_uid: int = 0,
) -> dict[str, Any]:
    """Re-verify standing authority at the broker's final approval boundary."""

    if str(agent).casefold() != "cassandra" or capability != "google.gmail.send":
        return _invalid("wrong_agent_or_capability")
    context = params.get("approval_context")
    if not isinstance(context, Mapping) or context.get("standing_autosend_gate") is not True:
        return _invalid("standing_gate_context_missing")
    trusted_config_path = Path(scope_config_path)
    if str(context.get("scope_config_path") or "") != str(trusted_config_path):
        return _invalid("scope_config_path_changed")
    try:
        config = load_scope_config(
            trusted_config_path,
            expected_uid=expected_config_uid,
            require_armed=True,
        )
        if str(context.get("scope_config_sha256") or "") != _sha256_file(trusted_config_path):
            return _invalid("scope_config_hash_changed")
        package_value = context.get("lamd_package")
        if not isinstance(package_value, Mapping):
            return _invalid("monthly_package_missing")
        package = _assert_package_matches_scope(package_value, config)
        if package_before_not_before_service_month(package, config):
            return _invalid("outside_not_before_service_month")
        material = build_exact_send_material(package)
    except (ScopeConfigError, ValueError, OSError):
        return _invalid("standing_scope_or_package_invalid")
    if not _artifacts_within_root(package, Path(artifact_root)):
        return _invalid("artifact_root_or_name_invalid")

    observed_at = now or datetime.now(timezone.utc)
    if observed_at.tzinfo is None:
        return _invalid("broker_time_not_timezone_aware")
    utc_now = observed_at.astimezone(timezone.utc)
    if (
        str(package["service_month"]) != utc_now.strftime("%Y-%m")
        or utc_now.day < int(config["cadence_day"])
    ):
        return _invalid("outside_monthly_cadence")
    exact = {
        "to": package["recipient"],
        "subject": material["subject"],
        "body": material["body"],
        "attachments": [package["pdf_path"]],
        "attachment_sha256": [package["pdf_sha256"]],
        "idempotency_key": material["request_id"],
        "exact_send_request_id": material["request_id"],
    }
    if any(params.get(key) != expected for key, expected in exact.items()):
        return _invalid("exact_send_material_changed")
    if str(params.get("cc") or "").strip() or str(params.get("bcc") or "").strip():
        return _invalid("additional_recipient_not_allowed")
    context_exact = {
        "request_id": material["request_id"],
        "idempotency_key": material["request_id"],
        "payload_hash": material["payload_hash"],
        "standing_authority_ref": config["standing_authority_ref"],
    }
    if any(context.get(key) != expected for key, expected in context_exact.items()):
        return _invalid("standing_authority_binding_changed")
    return {"valid": True, "reason": "lamd_standing_scope_verified"}


class StandingSendHoldAdmission:
    """Read-only preclaim/final admission for the still-present global hold."""

    def __init__(
        self,
        *,
        scope_config_path: str | Path = DEFAULT_SCOPE_CONFIG_PATH,
        send_hold_path: str | Path = DEFAULT_SEND_HOLD_PATH,
        expected_config_uid: int = 0,
    ):
        self.scope_config_path = Path(scope_config_path)
        self.send_hold_path = Path(send_hold_path)
        self.expected_config_uid = int(expected_config_uid)

    def __call__(self, package: dict[str, Any]) -> dict[str, Any]:
        try:
            config = load_scope_config(
                self.scope_config_path,
                expected_uid=self.expected_config_uid,
                require_armed=True,
            )
            _assert_package_matches_scope(package, config)
            if package_before_not_before_service_month(package, config):
                raise ScopeConfigError("monthly package is before standing not-before service month")
            metadata = os.lstat(self.send_hold_path)
            mode = stat.S_IMODE(metadata.st_mode)
            if not stat.S_ISREG(metadata.st_mode) or stat.S_ISLNK(metadata.st_mode):
                raise ScopeConfigError("SEND_HOLD is not a regular file")
            if mode not in ALLOWED_SENTINEL_MODES:
                raise ScopeConfigError("SEND_HOLD mode is unsafe")
            return {
                "allowed": True,
                "standing_authority_ref": config["standing_authority_ref"],
                "send_hold_sha256": _sha256_file(self.send_hold_path),
            }
        except (OSError, ScopeConfigError, ValueError):
            return {"allowed": False, "reason": "standing_scope_or_send_hold_invalid"}


class GovernedGmailProvider:
    """One exact Gmail call through the broker; never drafts and never retries."""

    def __init__(
        self,
        *,
        scope_config_path: str | Path = DEFAULT_SCOPE_CONFIG_PATH,
        send_hold_path: str | Path = DEFAULT_SEND_HOLD_PATH,
        graduation_path: str | Path,
        broker_call: Callable[[str, str, dict[str, Any]], Mapping[str, Any]],
        artifact_root: str | Path = DEFAULT_ARTIFACT_ROOT,
        expected_config_uid: int = 0,
        now_fn: Callable[[], datetime] | None = None,
    ):
        self.scope_config_path = Path(scope_config_path)
        self.send_hold_path = Path(send_hold_path)
        self.graduation_path = Path(graduation_path)
        self.broker_call = broker_call
        self.artifact_root = Path(artifact_root)
        self.expected_config_uid = int(expected_config_uid)
        self.now_fn = now_fn or (lambda: datetime.now(timezone.utc))

    def send(self, package: dict[str, Any], *, cycle_key: str) -> dict[str, Any]:
        config = load_scope_config(
            self.scope_config_path,
            expected_uid=self.expected_config_uid,
            require_armed=True,
        )
        bounded = _assert_package_matches_scope(package, config)
        if package_before_not_before_service_month(bounded, config):
            raise ScopeConfigError("monthly package is before standing not-before service month")
        if not _artifacts_within_root(bounded, self.artifact_root):
            raise ScopeConfigError("monthly artifacts are outside the approved root or workbook stream")
        expected_cycle_key = f"{CLIENT_REF}:{STREAM}:{bounded['service_month']}"
        if cycle_key != expected_cycle_key:
            raise ScopeConfigError("monthly cycle key changed")
        now = self.now_fn()
        if now.tzinfo is None:
            raise ScopeConfigError("provider clock must be timezone-aware")
        now_utc = now.astimezone(timezone.utc)
        if (
            str(bounded["service_month"]) != now_utc.strftime("%Y-%m")
            or now_utc.day < int(config["cadence_day"])
        ):
            raise ScopeConfigError("outside monthly cadence")
        material = build_exact_send_material(bounded)
        generated_at = now_utc.isoformat(timespec="seconds")
        expires_at = (now_utc + timedelta(minutes=10)).isoformat(timespec="seconds")
        issue_send_hold_scoped_graduation(
            graduation_path=self.graduation_path,
            send_hold_path=self.send_hold_path,
            request_id=material["request_id"],
            payload_hash=material["payload_hash"],
            recipient=str(bounded["recipient"]),
            body_sha256=material["body_sha256"],
            attachment_paths=[str(bounded["pdf_path"])],
            attachment_sha256=[str(bounded["pdf_sha256"])],
            authority_provenance=str(config["standing_authority_ref"]),
            active_heartbeat_hold_source="lamd_monthly_autosend_runner",
            generated_at=generated_at,
            expires_at=expires_at,
        )
        context = {
            "standing_autosend_gate": True,
            "request_id": material["request_id"],
            "idempotency_key": material["request_id"],
            "payload_hash": material["payload_hash"],
            "standing_authority_ref": config["standing_authority_ref"],
            "authority_source_ref": config["authority_source_ref"],
            "scope_config_path": str(self.scope_config_path),
            "scope_config_sha256": _sha256_file(self.scope_config_path),
            "lamd_package": bounded,
            "send_hold_graduation_ref": str(self.graduation_path),
        }
        params = {
            "to": bounded["recipient"],
            "subject": material["subject"],
            "body": material["body"],
            "attachments": [bounded["pdf_path"]],
            "attachment_sha256": [bounded["pdf_sha256"]],
            "idempotency_key": material["request_id"],
            "exact_send_request_id": material["request_id"],
            "send_hold_graduation_ref": str(self.graduation_path),
            "approval_context": context,
        }
        try:
            result = dict(self.broker_call("cassandra", "google.gmail.send", params))
        except Exception as exc:
            raise ProviderOutcomeUnknown(
                f"broker outcome unavailable after dispatch attempt: {type(exc).__name__}"
            ) from exc
        data = result.get("data") if isinstance(result.get("data"), Mapping) else {}
        if result.get("ok") is not True:
            raise ProviderOutcomeUnknown("broker did not prove a provider-negative outcome")
        if not str(data.get("message_id") or ""):
            raise ProviderOutcomeUnknown("broker success omitted provider message id")
        if data.get("send_hold_graduation_consumed") is not True:
            raise ProviderOutcomeUnknown("broker success omitted scoped graduation consumption proof")
        if not _graduation_file_consumed(self.graduation_path):
            raise ProviderOutcomeUnknown("broker success omitted graduation file consumption proof")
        return {
            "status": "SENT_VERIFIED",
            "message_id": str(data["message_id"]),
            "thread_id": str(data.get("thread_id") or ""),
            "recipient": bounded["recipient"],
            "amount_minor_units": bounded["amount_minor_units"],
            "service_month": bounded["service_month"],
            "package_sha256": bounded["package_sha256"],
            "sent_at": self.now_fn().astimezone(timezone.utc).isoformat(timespec="seconds"),
            "send_hold_graduation_ref": str(self.graduation_path),
            "send_hold_graduation_consumed": True,
        }


__all__ = [
    "DEFAULT_SCOPE_CONFIG_PATH",
    "DEFAULT_SEND_HOLD_PATH",
    "DEFAULT_ARTIFACT_ROOT",
    "GovernedGmailProvider",
    "SCOPE_SCHEMA_VERSION",
    "ScopeConfigError",
    "StandingSendHoldAdmission",
    "build_exact_send_material",
    "load_scope_config",
    "package_before_not_before_service_month",
    "verify_standing_send_context",
]
