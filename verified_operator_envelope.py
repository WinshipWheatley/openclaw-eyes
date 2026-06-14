"""Verified Operator Envelope V0.

Deterministic validation for Mission Control requests that claim to come from
the operator. The validator checks the envelope supplied by the caller; it does
not mint missing operator, app, device, session, or request hash fields.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parent

SCHEMA_VERSION = "verified_operator_envelope_v0"
SOURCE_SURFACE = "mission_control"
STATUS_VERIFIED = "OPERATOR_VERIFIED"
STATUS_VERIFICATION_REQUIRED = "OPERATOR_VERIFICATION_REQUIRED"

REQUIRED_ENVELOPE_FIELDS = (
    "operator_ref",
    "app_instance_ref",
    "device_ref",
    "session_ref",
    "request_hash",
    "created_at",
)

VERIFIED_FLAG_FIELDS = (
    "operator_verified",
    "verified_operator_envelope",
    "operator_envelope_verified",
    "verified",
)


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _copy_without_request_hash(payload: Any) -> Any:
    if isinstance(payload, Mapping):
        return {
            str(key): _copy_without_request_hash(value)
            for key, value in payload.items()
            if key != "request_hash"
        }
    if isinstance(payload, list):
        return [_copy_without_request_hash(value) for value in payload]
    return payload


def compute_request_hash(request_payload: Mapping[str, Any]) -> str:
    """Return the canonical request hash, excluding any existing request_hash."""

    canonical = _copy_without_request_hash(request_payload)
    digest = hashlib.sha256(stable_json(canonical).encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def _extract_envelope(payload: Mapping[str, Any]) -> dict[str, Any]:
    envelope = payload.get("operator_envelope")
    if isinstance(envelope, Mapping):
        return dict(envelope)
    if any(field in payload for field in REQUIRED_ENVELOPE_FIELDS):
        return dict(payload)
    return {}


def _present(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _verified_flag(payload: Mapping[str, Any], envelope: Mapping[str, Any]) -> bool:
    for field in VERIFIED_FLAG_FIELDS:
        if envelope.get(field) is True or payload.get(field) is True:
            return True
    return False


def validate_operator_envelope(
    payload: Mapping[str, Any],
    *,
    enforce_request_hash: bool = True,
) -> dict[str, Any]:
    """Validate a first-class operator envelope without filling missing fields."""

    blockers: list[str] = []
    envelope = _extract_envelope(payload)

    if not envelope:
        blockers.append("operator_envelope_missing")

    for field in REQUIRED_ENVELOPE_FIELDS:
        if not _present(envelope.get(field)):
            blockers.append(f"{field}_missing")

    source_surface = str(payload.get("source_surface") or envelope.get("source_surface") or "")
    if source_surface != SOURCE_SURFACE:
        blockers.append("source_surface_not_mission_control")

    if not _verified_flag(payload, envelope):
        blockers.append("operator_verified_false_or_missing")

    request_hash = str(envelope.get("request_hash") or "")
    hash_checked = False
    expected_hash = ""
    if enforce_request_hash and "operator_envelope" in payload and request_hash:
        expected_hash = compute_request_hash(payload)
        hash_checked = True
        if request_hash != expected_hash:
            blockers.append("request_hash_mismatch")

    status = STATUS_VERIFICATION_REQUIRED if blockers else STATUS_VERIFIED
    return {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "verified": not blockers,
        "blockers": blockers,
        "operator_ref": str(envelope.get("operator_ref") or ""),
        "app_instance_ref": str(envelope.get("app_instance_ref") or ""),
        "device_ref": str(envelope.get("device_ref") or ""),
        "session_ref": str(envelope.get("session_ref") or ""),
        "source_surface": source_surface,
        "request_hash": request_hash,
        "request_hash_checked": hash_checked,
        "expected_request_hash": expected_hash if hash_checked else "",
        "machine_proof": {
            "missing_fields_were_not_filled": True,
            "operator_envelope_required": True,
            "request_hash_required": True,
            "source_surface_required": SOURCE_SURFACE,
            "external_llm_invoked": False,
            "local_model_runtime_connected": False,
            "worker_spawn_performed": False,
            "business_action_performed": False,
        },
    }


def attach_verified_operator_envelope(
    request_payload: Mapping[str, Any],
    *,
    operator_ref: str = "operator:winship",
    app_instance_ref: str = "mission_control:pc",
    device_ref: str = "device:pc",
    session_ref: str = "session:local",
    created_at: str | None = None,
) -> dict[str, Any]:
    """Build a verified envelope for trusted local fixtures and UI callers.

    Validation does not call this helper. It exists so tests and deterministic
    local publishers can create a correctly hashed envelope.
    """

    created_at = created_at or utc_now()
    request = deepcopy(dict(request_payload))
    request["source_surface"] = SOURCE_SURFACE
    request["operator_envelope"] = {
        "operator_ref": operator_ref,
        "app_instance_ref": app_instance_ref,
        "device_ref": device_ref,
        "session_ref": session_ref,
        "created_at": created_at,
        "source_surface": SOURCE_SURFACE,
        "operator_verified": True,
        "request_hash": "",
    }
    request["operator_envelope"]["request_hash"] = compute_request_hash(request)
    return request


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate a verified operator envelope.")
    parser.add_argument("request_json", help="Path to a JSON request file.")
    parser.add_argument("--no-hash-check", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    payload = json.loads(Path(args.request_json).read_text(encoding="utf-8"))
    result = validate_operator_envelope(payload, enforce_request_hash=not args.no_hash_check)
    print(stable_json(result), end="")
    return 0 if result["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
