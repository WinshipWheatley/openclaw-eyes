"""Canonical JSON serialization for Gig-to-Cash domain records. Spec: 20260625-G2C005-v1"""
import dataclasses
import hashlib
import json
from typing import Any

from ar_expected_receivable_record import ExpectedReceivableRecord
from ar_gig_record import GigRecord
from ar_invoice_record import InvoiceRecord
from ar_work_session_record import WorkSessionRecord

_SCHEMA_VERSION = "1.0"

_SUPPORTED_RECORD_TYPES: frozenset[str] = frozenset({
    "ExpectedReceivableRecord",
    "GigRecord",
    "InvoiceRecord",
    "WorkSessionRecord",
})

_SUPPORTED_SCHEMA_VERSIONS: frozenset[str] = frozenset({"1.0"})

_RECORD_CLASS_MAP: dict[str, type] = {
    "ExpectedReceivableRecord": ExpectedReceivableRecord,
    "GigRecord": GigRecord,
    "InvoiceRecord": InvoiceRecord,
    "WorkSessionRecord": WorkSessionRecord,
}


def to_json(record: Any) -> str:
    """Serialize a Gig-to-Cash record to canonical UTF-8 JSON with sorted keys."""
    record_type = type(record).__name__
    if record_type not in _SUPPORTED_RECORD_TYPES:
        raise TypeError(f"Unsupported record type: {record_type!r}")

    payload = {f.name: getattr(record, f.name) for f in dataclasses.fields(record)}
    envelope = {
        "payload": payload,
        "record_type": record_type,
        "schema_version": _SCHEMA_VERSION,
    }
    return json.dumps(
        envelope,
        sort_keys=True,
        separators=(',', ':'),
        ensure_ascii=False,
        allow_nan=False,
    )


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key!r}")
        result[key] = value
    return result


def from_json(data: str) -> Any:
    """Deserialize a canonical JSON string to a Gig-to-Cash record with strict validation."""
    try:
        envelope = json.loads(data, object_pairs_hook=_reject_duplicate_keys)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON: {exc}") from exc

    envelope_keys = set(envelope.keys())
    required_envelope_keys = {"payload", "record_type", "schema_version"}
    unknown_envelope_keys = envelope_keys - required_envelope_keys
    if unknown_envelope_keys:
        raise ValueError(f"Unknown envelope keys: {sorted(unknown_envelope_keys)}")
    missing_envelope_keys = required_envelope_keys - envelope_keys
    if missing_envelope_keys:
        raise ValueError(f"Missing envelope keys: {sorted(missing_envelope_keys)}")

    record_type: str = envelope["record_type"]
    schema_version: str = envelope["schema_version"]
    payload = envelope["payload"]

    if record_type not in _SUPPORTED_RECORD_TYPES:
        raise ValueError(f"Unknown record type: {record_type!r}")
    if schema_version not in _SUPPORTED_SCHEMA_VERSIONS:
        raise ValueError(f"Unknown schema version: {schema_version!r}")
    if not isinstance(payload, dict):
        raise ValueError("payload must be a JSON object")

    cls = _RECORD_CLASS_MAP[record_type]
    expected_fields = {f.name for f in dataclasses.fields(cls)}
    actual_fields = set(payload.keys())

    unknown_fields = actual_fields - expected_fields
    if unknown_fields:
        raise ValueError(f"Unknown payload fields for {record_type}: {sorted(unknown_fields)}")
    missing_fields = expected_fields - actual_fields
    if missing_fields:
        raise ValueError(f"Missing payload fields for {record_type}: {sorted(missing_fields)}")

    # ValueError from __post_init__ propagates directly; TypeError is wrapped
    try:
        return cls(**payload)
    except TypeError as exc:
        raise ValueError(f"Type error constructing {record_type}: {exc}") from exc


def canonical_sha256(record: Any) -> str:
    """Return the SHA-256 hex digest of the canonical JSON for a record."""
    return hashlib.sha256(to_json(record).encode("utf-8")).hexdigest()
