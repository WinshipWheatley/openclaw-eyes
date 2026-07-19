"""Publish the one validated LAMD monthly package consumed by the auto-send runner."""

from __future__ import annotations

import calendar
import hashlib
import json
import os
import re
import stat
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Mapping


OUTPUT_NAME = "lamd_monthly_autosend_package.json"
MAX_JSON_BYTES = 262_144
MONTH_PATTERN = re.compile(r"^\d{4}-\d{2}$")


class PackagePublicationError(ValueError):
    """A validated upstream package is absent, ambiguous, changed, or off-scope."""


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    try:
        metadata = os.lstat(path)
    except OSError as exc:
        raise PackagePublicationError("validated manifest unavailable") from exc
    if not stat.S_ISREG(metadata.st_mode) or stat.S_ISLNK(metadata.st_mode):
        raise PackagePublicationError("validated manifest is not a regular file")
    if metadata.st_size > MAX_JSON_BYTES:
        raise PackagePublicationError("validated manifest is oversized")
    try:
        fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        try:
            opened = os.fstat(fd)
            if (opened.st_dev, opened.st_ino) != (metadata.st_dev, metadata.st_ino):
                raise PackagePublicationError("validated manifest changed during read")
            raw = os.read(fd, MAX_JSON_BYTES + 1)
        finally:
            os.close(fd)
        if len(raw) > MAX_JSON_BYTES:
            raise PackagePublicationError("validated manifest is oversized")
        value = json.loads(raw.decode("utf-8"))
    except PackagePublicationError:
        raise
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PackagePublicationError("validated manifest is invalid") from exc
    if not isinstance(value, dict):
        raise PackagePublicationError("validated manifest is not an object")
    return value


def _month_bounds(month: str) -> tuple[str, str]:
    if MONTH_PATTERN.fullmatch(month) is None:
        raise PackagePublicationError("month directory must be YYYY-MM")
    try:
        year, month_number = (int(piece) for piece in month.split("-"))
        last_day = calendar.monthrange(year, month_number)[1]
    except (TypeError, ValueError) as exc:
        raise PackagePublicationError("month directory is invalid") from exc
    return f"{month}-01", f"{month}-{last_day:02d}"


def _validated_candidate(month_dir: Path) -> tuple[Path, dict[str, Any]]:
    try:
        root = month_dir.resolve(strict=True)
    except OSError as exc:
        raise PackagePublicationError("month artifact directory unavailable") from exc
    candidates: list[Path] = []
    for candidate in sorted(month_dir.glob("w1-finalized-*")):
        try:
            metadata = os.lstat(candidate)
            resolved = candidate.resolve(strict=True)
        except OSError:
            continue
        if stat.S_ISDIR(metadata.st_mode) and not stat.S_ISLNK(metadata.st_mode) and resolved.parent == root:
            candidates.append(candidate)
    if len(candidates) != 1:
        raise PackagePublicationError("exactly one validated W1 package is required")
    candidate = candidates[0]
    return candidate, _read_json(candidate / "invoice_manifest.json")


def build_monthly_package(month_dir: str | Path) -> dict[str, Any]:
    root = Path(month_dir)
    month = root.name
    period_start, period_end = _month_bounds(month)
    candidate, manifest = _validated_candidate(root)
    exact = {
        "schema": "openclaw_invoice_manifest_v1",
        "status": "finalized_validated",
        "client_slug": "live-arts-md",
        "stream": "speaker_rental",
        "service_period_start": period_start,
        "service_period_end": period_end,
    }
    changed = [key for key, expected in exact.items() if manifest.get(key) != expected]
    if changed:
        raise PackagePublicationError("validated manifest scope drift: " + ", ".join(changed))
    try:
        amount = Decimal(str(manifest.get("amount")))
    except (InvalidOperation, ValueError) as exc:
        raise PackagePublicationError("validated manifest amount is invalid") from exc
    if amount != Decimal("100.00"):
        raise PackagePublicationError("validated manifest amount changed")
    invoice_number = str(manifest.get("invoice_number") or "").strip()
    source_sheet = str(manifest.get("source_sheet") or "").strip()
    if not invoice_number or candidate.name != f"w1-finalized-{invoice_number}":
        raise PackagePublicationError("validated invoice number changed")
    if manifest.get("invoice_key") != f"{month}_live_arts_md_{invoice_number}":
        raise PackagePublicationError("validated invoice key changed")
    if not source_sheet:
        raise PackagePublicationError("validated source sheet is missing")
    if not str(manifest.get("validation_event_id") or "").strip():
        raise PackagePublicationError("validated event proof is missing")
    if not str(manifest.get("artifact_verification_receipt_id") or "").strip():
        raise PackagePublicationError("artifact verification proof is missing")
    expected_boundary = {
        "provider_draft_created": False,
        "external_send_performed": False,
        "money_moved": False,
        "ledger_posted": False,
    }
    if manifest.get("authority_boundary") != expected_boundary:
        raise PackagePublicationError("validated manifest authority boundary changed")
    workbook = candidate / "invoice.xlsx"
    pdf = candidate / "invoice.pdf"
    for path, field in (
        (workbook, "package_workbook_sha256"),
        (pdf, "current_pdf_sha256"),
    ):
        try:
            metadata = os.lstat(path)
        except OSError as exc:
            raise PackagePublicationError("validated artifact is unavailable") from exc
        if not stat.S_ISREG(metadata.st_mode) or stat.S_ISLNK(metadata.st_mode):
            raise PackagePublicationError("validated artifact is not a regular file")
        if _sha256_file(path) != str(manifest.get(field) or "").lower():
            raise PackagePublicationError("validated artifact hash changed")
    pdf_sha = _sha256_file(pdf)
    if pdf_sha != str(manifest.get("validated_artifact_sha256") or "").lower():
        raise PackagePublicationError("validated PDF proof hash changed")
    package: dict[str, Any] = {
        "schema_version": "lamd_monthly_autosend_package_v1",
        "client_ref": "live_arts_md",
        "stream": "speaker_rental",
        "source_stream": "speaker_rental",
        "service_month": month,
        "service_period_start": period_start,
        "service_period_end": period_end,
        "invoice_number": invoice_number,
        "amount_minor_units": 10_000,
        "currency": "USD",
        "recipient": "Accountant@liveartsmd.org",
        "source_workbook_path": str(workbook.resolve(strict=True)),
        "source_workbook_sha256": _sha256_file(workbook),
        "source_sheet": source_sheet,
        "pdf_path": str(pdf.resolve(strict=True)),
        "pdf_sha256": pdf_sha,
        "status": "finalized_validated",
        "manifest_path": str((candidate / "invoice_manifest.json").resolve(strict=True)),
        "validation_event_id": str(manifest["validation_event_id"]),
    }
    material = {key: package[key] for key in sorted(package)}
    package["package_sha256"] = hashlib.sha256(
        _stable_json(material).encode("utf-8")
    ).hexdigest()
    return package


def publish_monthly_package(
    month_dir: str | Path,
    *,
    output_path: str | Path | None = None,
) -> dict[str, Any]:
    root = Path(month_dir)
    output = Path(output_path) if output_path is not None else root / OUTPUT_NAME
    try:
        resolved_root = root.resolve(strict=True)
        resolved_parent = output.parent.resolve(strict=True)
    except OSError as exc:
        raise PackagePublicationError("package output parent unavailable") from exc
    if resolved_parent != resolved_root or output.name != OUTPUT_NAME:
        raise PackagePublicationError("package output path is outside the current month")
    package = build_monthly_package(root)
    if output.exists() or output.is_symlink():
        existing = _read_json(output)
        if existing != package:
            raise PackagePublicationError("existing output changed")
        return {
            "status": "IDEMPOTENT_REPLAY",
            "output_path": str(output),
            "package_sha256": package["package_sha256"],
            "provider_called": False,
            "ledger_posted": False,
        }
    temporary = output.with_name(f".{output.name}.{os.getpid()}.tmp")
    fd = os.open(
        temporary,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
        0o644,
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(json.dumps(package, indent=2, sort_keys=True, ensure_ascii=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, output)
        directory_fd = os.open(output.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass
    return {
        "status": "PUBLISHED",
        "output_path": str(output),
        "package_sha256": package["package_sha256"],
        "published_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "provider_called": False,
        "ledger_posted": False,
    }


__all__ = [
    "OUTPUT_NAME",
    "PackagePublicationError",
    "build_monthly_package",
    "publish_monthly_package",
]
