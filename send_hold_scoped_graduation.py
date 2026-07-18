"""Hash-bound, single-use graduation for one exact send under SEND_HOLD."""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import stat
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence


SCHEMA_VERSION = "SEND_HOLD_SCOPED_GRADUATION_V1"
ACTIVE = "ACTIVE"
CONSUMED = "CONSUMED"
ALLOWED_SENTINEL_MODES = frozenset({0o600, 0o640, 0o644})


class SendHoldGraduationError(ValueError):
    """Raised when a graduation is absent, stale, changed, or out of scope."""


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


def _clean(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def _parse_timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _normalize_sha256(value: Any) -> str:
    digest = _clean(value).lower()
    if digest.startswith("sha256:"):
        digest = digest.split(":", 1)[1]
    if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
        raise SendHoldGraduationError("invalid sha256 binding")
    return digest


def _validated_attachments(paths: Sequence[str], digests: Sequence[str]) -> tuple[list[str], list[str]]:
    clean_paths = [str(Path(path)) for path in paths]
    clean_digests = [_normalize_sha256(value) for value in digests]
    if not clean_paths or len(clean_paths) != len(clean_digests):
        raise SendHoldGraduationError("graduation requires matching attachment paths and sha256 bindings")
    for path_text, expected in zip(clean_paths, clean_digests, strict=True):
        path = Path(path_text)
        if not path.is_file() or path.suffix.lower() != ".pdf":
            raise SendHoldGraduationError("graduation attachment must be an existing PDF")
        if _sha256_file(path) != expected:
            raise SendHoldGraduationError("graduation attachment sha256 mismatch")
    return clean_paths, clean_digests


def issue_send_hold_scoped_graduation(
    *,
    graduation_path: str | Path,
    send_hold_path: str | Path,
    request_id: str,
    payload_hash: str,
    recipient: str,
    body_sha256: str,
    attachment_paths: Sequence[str],
    attachment_sha256: Sequence[str],
    authority_provenance: str,
    active_heartbeat_hold_source: str,
    generated_at: str,
    expires_at: str,
) -> dict[str, Any]:
    path = Path(graduation_path)
    sentinel = Path(send_hold_path)
    if path.exists():
        raise SendHoldGraduationError("graduation path already exists")
    if not sentinel.is_file():
        raise SendHoldGraduationError("SEND_HOLD sentinel must remain present")
    mode = stat.S_IMODE(sentinel.stat().st_mode)
    if mode not in ALLOWED_SENTINEL_MODES:
        raise SendHoldGraduationError("SEND_HOLD sentinel permissions are not hardened")
    if _parse_timestamp(expires_at) <= _parse_timestamp(generated_at):
        raise SendHoldGraduationError("graduation expiry must follow issuance")
    clean_paths, clean_digests = _validated_attachments(attachment_paths, attachment_sha256)
    scope = {
        "request_id": _clean(request_id),
        "payload_hash": _clean(payload_hash).lower(),
        "recipient": _clean(recipient).lower(),
        "body_sha256": _normalize_sha256(body_sha256),
        "attachment_paths": clean_paths,
        "attachment_sha256": clean_digests,
    }
    if not all((scope["request_id"], scope["payload_hash"], scope["recipient"])):
        raise SendHoldGraduationError("graduation scope is incomplete")
    scope_hash = "sha256:" + _sha256_bytes(_stable_json(scope).encode("utf-8"))
    sentinel_sha = _sha256_file(sentinel)
    graduation_id = "send-hold-graduation:" + _sha256_bytes(
        f"{scope_hash}|{sentinel_sha}|{generated_at}".encode("utf-8")
    )[:24]
    payload = {
        "schema_version": SCHEMA_VERSION,
        "graduation_id": graduation_id,
        "status": ACTIVE,
        "send_hold_path": str(sentinel),
        "send_hold_sha256": sentinel_sha,
        "send_hold_mode": f"0o{mode:03o}",
        "scope": scope,
        "scope_hash": scope_hash,
        "one_time_only": True,
        "max_use_count": 1,
        "use_count": 0,
        "consumed_at": "",
        "authority_provenance": _clean(authority_provenance),
        "active_heartbeat_hold_source": _clean(active_heartbeat_hold_source),
        "generated_at": generated_at,
        "expires_at": expires_at,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    path.chmod(0o600)
    return dict(payload)


def verify_send_hold_scoped_graduation(
    *,
    graduation_path: str | Path,
    send_hold_path: str | Path,
    request_id: str,
    payload_hash: str,
    recipient: str,
    body_sha256: str,
    attachment_paths: Sequence[str],
    attachment_sha256: Sequence[str],
    observed_at: str,
    consume: bool = False,
) -> dict[str, Any]:
    path = Path(graduation_path)
    lock_path = path.with_suffix(path.suffix + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_fd = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX)
        if not path.is_file():
            raise SendHoldGraduationError("scoped graduation does not exist")
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("schema_version") != SCHEMA_VERSION:
            raise SendHoldGraduationError("scoped graduation schema is invalid")
        if payload.get("status") != ACTIVE or int(payload.get("use_count") or 0) != 0:
            raise SendHoldGraduationError("scoped graduation is already consumed")
        if _parse_timestamp(payload["expires_at"]) <= _parse_timestamp(observed_at):
            raise SendHoldGraduationError("scoped graduation is expired")
        sentinel = Path(send_hold_path)
        if str(sentinel) != str(payload.get("send_hold_path") or "") or not sentinel.is_file():
            raise SendHoldGraduationError("SEND_HOLD sentinel binding changed")
        mode = stat.S_IMODE(sentinel.stat().st_mode)
        if mode not in ALLOWED_SENTINEL_MODES:
            raise SendHoldGraduationError("SEND_HOLD sentinel permissions are not hardened")
        if _sha256_file(sentinel) != str(payload.get("send_hold_sha256") or ""):
            raise SendHoldGraduationError("SEND_HOLD sentinel hash changed")
        clean_paths, clean_digests = _validated_attachments(attachment_paths, attachment_sha256)
        observed_scope = {
            "request_id": _clean(request_id),
            "payload_hash": _clean(payload_hash).lower(),
            "recipient": _clean(recipient).lower(),
            "body_sha256": _normalize_sha256(body_sha256),
            "attachment_paths": clean_paths,
            "attachment_sha256": clean_digests,
        }
        if observed_scope != payload.get("scope"):
            raise SendHoldGraduationError("scoped graduation does not match the exact send")
        observed_scope_hash = "sha256:" + _sha256_bytes(_stable_json(observed_scope).encode("utf-8"))
        if observed_scope_hash != payload.get("scope_hash"):
            raise SendHoldGraduationError("scoped graduation hash is invalid")
        if consume:
            payload["status"] = CONSUMED
            payload["use_count"] = 1
            payload["consumed_at"] = observed_at
            temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
            temporary.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n", encoding="utf-8")
            temporary.chmod(0o600)
            os.replace(temporary, path)
        return {
            "valid": True,
            "consumed": consume,
            "graduation_id": str(payload.get("graduation_id") or ""),
            "scope_hash": str(payload.get("scope_hash") or ""),
            "status": str(payload.get("status") or ""),
            "send_hold_sha256": str(payload.get("send_hold_sha256") or ""),
            "authority_provenance": str(payload.get("authority_provenance") or ""),
            "active_heartbeat_hold_source": str(payload.get("active_heartbeat_hold_source") or ""),
            "expires_at": str(payload.get("expires_at") or ""),
        }
    finally:
        fcntl.flock(lock_fd, fcntl.LOCK_UN)
        os.close(lock_fd)


__all__ = [
    "ACTIVE",
    "CONSUMED",
    "SCHEMA_VERSION",
    "SendHoldGraduationError",
    "issue_send_hold_scoped_graduation",
    "verify_send_hold_scoped_graduation",
]
