"""Append-only invoice validation receipts and exact-byte canonical promotion."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import sqlite3
from pathlib import Path
from typing import Any, Mapping


VALIDATION_SCHEMA_VERSION = "invoice_artifact_validation_event_v1"
PROMOTION_SCHEMA_VERSION = "invoice_validated_promotion_v1"
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class InvoiceValidationError(ValueError):
    """Raised before a validation or promotion invariant can be violated."""


def _stable_json(value: Any) -> str:
    return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_text(value: str) -> str:
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()


def _clean(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def _require_sha256(value: Any, *, field: str) -> str:
    digest = _clean(value).lower()
    if not _SHA256_RE.fullmatch(digest):
        raise InvoiceValidationError(f"{field} must be a SHA-256 digest")
    return digest


def ensure_invoice_validation_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS invoice_artifact_validation_events (
          event_id TEXT PRIMARY KEY,
          obligation_key TEXT NOT NULL,
          client_ref TEXT NOT NULL,
          service_period TEXT NOT NULL,
          invoice_number TEXT NOT NULL,
          artifact_sha256 TEXT NOT NULL,
          operator_message_ref TEXT NOT NULL UNIQUE,
          operator_message_text_sha256 TEXT NOT NULL,
          surface_ref TEXT NOT NULL,
          validated_at TEXT NOT NULL,
          receipt_json TEXT NOT NULL
        );
        CREATE TRIGGER IF NOT EXISTS invoice_artifact_validation_events_no_update
        BEFORE UPDATE ON invoice_artifact_validation_events
        BEGIN
          SELECT RAISE(ABORT, 'invoice artifact validation events are append-only');
        END;
        CREATE TRIGGER IF NOT EXISTS invoice_artifact_validation_events_no_delete
        BEFORE DELETE ON invoice_artifact_validation_events
        BEGIN
          SELECT RAISE(ABORT, 'invoice artifact validation events are append-only');
        END;
        """
    )


def record_invoice_validation_event(
    *,
    db_path: str | Path,
    client_ref: str,
    service_period: str,
    invoice_number: str,
    artifact_sha256: str,
    operator_message_ref: str,
    operator_message_text: str,
    surface_ref: str,
    validated_at: str,
) -> dict[str, Any]:
    client = _clean(client_ref)
    period = _clean(service_period)
    invoice = _clean(invoice_number)
    digest = _require_sha256(artifact_sha256, field="artifact_sha256")
    message_ref = _clean(operator_message_ref)
    message_text = _clean(operator_message_text)
    surface = _clean(surface_ref)
    timestamp = _clean(validated_at)
    if not all((client, period, invoice, message_ref, message_text, surface, timestamp)):
        raise InvoiceValidationError("validation event fields are incomplete")
    obligation_key = f"{client}/{period}/{invoice}"
    event_id = "invoice-validation:" + hashlib.sha256(
        "|".join((obligation_key, digest, message_ref, surface)).encode("utf-8")
    ).hexdigest()[:24]
    receipt = {
        "schema_version": VALIDATION_SCHEMA_VERSION,
        "event_id": event_id,
        "obligation_key": obligation_key,
        "client_ref": client,
        "service_period": period,
        "invoice_number": invoice,
        "artifact_sha256": digest,
        "operator_message_ref": message_ref,
        "operator_message_text_sha256": _sha256_text(message_text),
        "operator_message_text": message_text,
        "surface_ref": surface,
        "validated_at": timestamp,
        "append_only": True,
        "authority_boundary": {
            "artifact_finalization_authorized": True,
            "provider_draft_authorized": False,
            "business_send_authorized": False,
            "money_movement_authorized": False,
        },
    }
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        ensure_invoice_validation_schema(conn)
        conn.execute("BEGIN IMMEDIATE")
        existing = conn.execute(
            "SELECT receipt_json FROM invoice_artifact_validation_events WHERE event_id = ?",
            (event_id,),
        ).fetchone()
        if existing is not None:
            stored = json.loads(existing["receipt_json"])
            if _canonical_json(stored) != _canonical_json(receipt):
                raise InvoiceValidationError("validation event replay changed immutable fields")
            conn.commit()
            return {**stored, "created": False, "idempotent_replay": True}
        conn.execute(
            """
            INSERT INTO invoice_artifact_validation_events (
              event_id, obligation_key, client_ref, service_period, invoice_number,
              artifact_sha256, operator_message_ref, operator_message_text_sha256,
              surface_ref, validated_at, receipt_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event_id,
                obligation_key,
                client,
                period,
                invoice,
                digest,
                message_ref,
                receipt["operator_message_text_sha256"],
                surface,
                timestamp,
                _canonical_json(receipt),
            ),
        )
        conn.commit()
        return {**receipt, "created": True, "idempotent_replay": False}
    except sqlite3.IntegrityError as exc:
        conn.rollback()
        raise InvoiceValidationError("operator validation message is already bound to another event") from exc
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise InvoiceValidationError(f"invalid JSON file: {path}") from exc
    if not isinstance(payload, dict):
        raise InvoiceValidationError(f"JSON root must be an object: {path}")
    return payload


def _registry_transition(
    registry: Mapping[str, Any],
    *,
    validation: Mapping[str, Any],
    package_dir: Path,
    published_at: str,
    workbook_sha256: str,
) -> dict[str, Any]:
    payload = dict(registry)
    rows = payload.get("candidates")
    if payload.get("schema_version") != "invoice_candidate_artifact_registry_v0" or not isinstance(rows, list):
        raise InvoiceValidationError("candidate registry schema is invalid")
    matches = [
        row
        for row in rows
        if isinstance(row, Mapping)
        and _clean(row.get("client_ref")) == validation["client_ref"]
        and _clean(row.get("service_period")) == validation["service_period"]
        and _clean(row.get("invoice_number")) == validation["invoice_number"]
    ]
    if len(matches) != 1:
        raise InvoiceValidationError("candidate registry does not contain exactly one matching row")
    match = matches[0]
    if _require_sha256(match.get("pdf_sha256"), field="registry pdf_sha256") != validation["artifact_sha256"]:
        raise InvoiceValidationError("candidate registry hash differs from validation event")
    if match.get("validation_received") is True and match.get("finalized") is True:
        return payload
    if match.get("active_for_review") is not True or match.get("finalized") is not False:
        raise InvoiceValidationError("candidate registry row is not active review-only state")

    transitioned: list[Any] = []
    for raw in rows:
        if raw is not match:
            transitioned.append(raw)
            continue
        row = dict(raw)
        row.update(
            {
                "status": "finalized_validated",
                "active_for_review": False,
                "finalized": True,
                "validation_received": True,
                "validation_event_id": validation["event_id"],
                "validation_message_ref": validation["operator_message_ref"],
                "finalized_at": published_at,
                "finalized_pdf_path": (package_dir / "invoice.pdf").as_posix(),
                "finalized_pdf_sha256": validation["artifact_sha256"],
                "finalized_workbook_path": (package_dir / "invoice.xlsx").as_posix(),
                "finalized_workbook_sha256": workbook_sha256,
            }
        )
        transitioned.append(row)
    payload["generated_at"] = published_at
    payload["candidates"] = transitioned
    return payload


def publish_validated_invoice_package(
    *,
    candidate_pdf: str | Path,
    candidate_workbook: str | Path,
    package_dir: str | Path,
    registry_path: str | Path,
    validation_receipt: Mapping[str, Any],
    published_at: str,
) -> dict[str, Any]:
    pdf = Path(candidate_pdf)
    workbook = Path(candidate_workbook)
    package = Path(package_dir)
    registry_target = Path(registry_path)
    validation = dict(validation_receipt)
    if validation.get("schema_version") != VALIDATION_SCHEMA_VERSION:
        raise InvoiceValidationError("validation receipt schema is invalid")
    expected_pdf_sha = _require_sha256(validation.get("artifact_sha256"), field="validated artifact hash")
    if not pdf.is_file() or _sha256(pdf) != expected_pdf_sha:
        raise InvoiceValidationError("validated artifact hash does not match candidate PDF")
    if not workbook.is_file():
        raise InvoiceValidationError("candidate workbook is missing")
    workbook_sha = _sha256(workbook)
    registry = _load_json(registry_target)
    transitioned_registry = _registry_transition(
        registry,
        validation=validation,
        package_dir=package,
        published_at=published_at,
        workbook_sha256=workbook_sha,
    )

    current_manifest_path = package / "invoice_manifest.json"
    if package.is_dir() and current_manifest_path.is_file():
        current_manifest = _load_json(current_manifest_path)
        if (
            current_manifest.get("validation_event_id") == validation["event_id"]
            and current_manifest.get("current_pdf_sha256") == expected_pdf_sha
            and _sha256(package / "invoice.pdf") == expected_pdf_sha
            and _sha256(package / "invoice.xlsx") == workbook_sha
        ):
            return {
                "schema_version": PROMOTION_SCHEMA_VERSION,
                "status": "IDEMPOTENT_REPLAY",
                "validation_event_id": validation["event_id"],
                "validated_sha256": expected_pdf_sha,
                "finalized_sha256": expected_pdf_sha,
                "finalized_workbook_sha256": workbook_sha,
                "package_dir": package.as_posix(),
                "superseded_package_archive": str(current_manifest.get("superseded_package_archive") or ""),
                "idempotent_replay": True,
            }

    stage = package.parent / f".{package.name}.{validation['event_id'].replace(':', '_')}.staging"
    if stage.exists():
        raise InvoiceValidationError("validation promotion staging path already exists")
    stage.mkdir(parents=True, exist_ok=False)
    shutil.copyfile(pdf, stage / "invoice.pdf")
    shutil.copyfile(workbook, stage / "invoice.xlsx")
    if _sha256(stage / "invoice.pdf") != expected_pdf_sha or _sha256(stage / "invoice.xlsx") != workbook_sha:
        raise InvoiceValidationError("staged validated bytes changed during copy")

    old_pdf_sha = _sha256(package / "invoice.pdf") if (package / "invoice.pdf").is_file() else "none"
    archive = package.parent / ".superseded_validation_event_1" / old_pdf_sha / package.name
    if package.exists() and archive.exists():
        raise InvoiceValidationError("superseded package archive already exists")
    manifest = {
        "schema": "openclaw_invoice_manifest_v1",
        "status": "finalized_validated",
        "client_slug": "live-arts-md",
        "invoice_key": "2026-07_live_arts_md_2026-1004",
        "invoice_number": validation["invoice_number"],
        "service_period_start": "2026-07-01",
        "service_period_end": "2026-07-31",
        "source_sheet": "July 2026",
        "amount": 100.0,
        "package_workbook_sha256": workbook_sha,
        "current_pdf_sha256": expected_pdf_sha,
        "validated_artifact_sha256": expected_pdf_sha,
        "validation_event_id": validation["event_id"],
        "validation_message_ref": validation["operator_message_ref"],
        "validation_surface_ref": validation["surface_ref"],
        "validated_at": validation["validated_at"],
        "published_at": published_at,
        "artifact_verification_receipt_id": validation["event_id"],
        "formula_freshness_receipt_id": "w1-prior-balance-formula-fixed-real-excel-20260717",
        "latest_send_receipt_path": None,
        "superseded_package_archive": archive.as_posix() if package.exists() else "",
        "authority_boundary": {
            "provider_draft_created": False,
            "external_send_performed": False,
            "money_moved": False,
            "ledger_posted": False,
        },
    }
    (stage / "invoice_manifest.json").write_text(_stable_json(manifest), encoding="utf-8")
    registry_temp = registry_target.parent / f".{registry_target.name}.{validation['event_id'].replace(':', '_')}.tmp"
    registry_temp.write_text(_stable_json(transitioned_registry), encoding="utf-8")

    if package.exists():
        archive.parent.mkdir(parents=True, exist_ok=True)
        os.replace(package, archive)
        archived_manifest = archive / "invoice_manifest.json"
        if archived_manifest.is_file():
            os.replace(archived_manifest, archive / "invoice_manifest.superseded.json")
    package.parent.mkdir(parents=True, exist_ok=True)
    os.replace(stage, package)
    os.replace(registry_temp, registry_target)
    finalized_sha = _sha256(package / "invoice.pdf")
    if finalized_sha != expected_pdf_sha:
        raise InvoiceValidationError("finalized artifact differs from validated artifact")
    return {
        "schema_version": PROMOTION_SCHEMA_VERSION,
        "status": "PUBLISHED_VALIDATED",
        "validation_event_id": validation["event_id"],
        "validated_sha256": expected_pdf_sha,
        "finalized_sha256": finalized_sha,
        "finalized_workbook_sha256": workbook_sha,
        "package_dir": package.as_posix(),
        "superseded_package_archive": archive.as_posix() if archive.is_dir() else "",
        "idempotent_replay": False,
        "authority_boundary": manifest["authority_boundary"],
    }


__all__ = [
    "InvoiceValidationError",
    "PROMOTION_SCHEMA_VERSION",
    "VALIDATION_SCHEMA_VERSION",
    "ensure_invoice_validation_schema",
    "publish_validated_invoice_package",
    "record_invoice_validation_event",
]
