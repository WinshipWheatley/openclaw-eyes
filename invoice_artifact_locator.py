"""Deterministic manifest-first invoice artifact locator."""

from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict
from collections.abc import Sequence
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "invoice_artifact_locator_v0"
MANIFEST_SCHEMA = "openclaw_invoice_manifest_v1"
PROMOTION_SCHEMA = "openclaw_invoice_artifact_promotion_v1"
QUARANTINE_SEGMENT = ".openclaw_scope_quarantine"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json_object(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _client_key(value: object) -> str:
    text = re.sub(r"[^a-z0-9]+", "-", str(value or "").strip().lower()).strip("-")
    aliases = {
        "st-anne": "st-annes",
        "st-anne-s": "st-annes",
        "st-annes": "st-annes",
    }
    return aliases.get(text, text)


def _period_from_manifest(manifest: dict[str, Any]) -> str:
    start = str(manifest.get("service_period_start") or "").strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", start):
        return start[:7]
    invoice_key = str(manifest.get("invoice_key") or "").strip()
    match = re.match(r"^(\d{4}-\d{2})[_-]", invoice_key)
    return match.group(1) if match else ""


def _verified_test_promotion(manifest: dict[str, Any]) -> dict[str, Any] | None:
    raw = manifest.get("promotion")
    if not isinstance(raw, dict):
        return None
    supersedes = raw.get("supersedes_pdf_sha256")
    if (
        raw.get("schema") != PROMOTION_SCHEMA
        or raw.get("scope") != "test"
        or raw.get("status") != "verified"
        or not isinstance(supersedes, list)
        or not supersedes
        or not str(raw.get("verification_receipt_ref") or "").strip()
        or not str(raw.get("operator_confirmation_source_ref") or "").strip()
    ):
        return None
    normalized = [str(item).strip().lower() for item in supersedes]
    if len(set(normalized)) != len(normalized) or any(
        re.fullmatch(r"[0-9a-f]{64}", item) is None for item in normalized
    ):
        return None
    return {
        "schema": PROMOTION_SCHEMA,
        "scope": "test",
        "status": "verified",
        "supersedes_pdf_sha256": sorted(normalized),
        "verification_receipt_ref": str(raw["verification_receipt_ref"]).strip(),
        "operator_confirmation_source_ref": str(
            raw["operator_confirmation_source_ref"]
        ).strip(),
    }


def _within(path: Path, root: Path) -> bool:
    try:
        path.resolve(strict=False).relative_to(root.resolve(strict=False))
    except ValueError:
        return False
    return True


def _rejection(path: Path, reason: str) -> dict[str, str]:
    return {"manifest_path": path.as_posix(), "reason": reason}


def _verify_manifest_candidate(
    manifest_path: Path,
    *,
    client_key: str,
    service_period: str,
) -> tuple[dict[str, Any] | None, str]:
    manifest = _json_object(manifest_path)
    if not manifest:
        return None, "manifest_missing_or_invalid"
    if manifest.get("schema") != MANIFEST_SCHEMA:
        return None, "manifest_schema_invalid"
    if _client_key(manifest.get("client_slug")) != client_key:
        return None, "client_mismatch"
    if _period_from_manifest(manifest) != service_period:
        return None, "service_period_mismatch"

    package_dir = manifest_path.parent
    workbook_path = package_dir / "invoice.xlsx"
    pdf_path = package_dir / "invoice.pdf"
    if not workbook_path.is_file():
        return None, "workbook_missing"
    if not pdf_path.is_file():
        return None, "pdf_missing"
    expected_workbook_hash = str(manifest.get("package_workbook_sha256") or "").strip().lower()
    expected_pdf_hash = str(manifest.get("current_pdf_sha256") or "").strip().lower()
    workbook_hash = _sha256(workbook_path)
    pdf_hash = _sha256(pdf_path)
    if not expected_workbook_hash or workbook_hash != expected_workbook_hash:
        return None, "workbook_hash_mismatch"
    if not expected_pdf_hash or pdf_hash != expected_pdf_hash:
        return None, "pdf_hash_mismatch"
    source_sheet = str(manifest.get("source_sheet") or "").strip()
    invoice_number = str(manifest.get("invoice_number") or "").strip()
    amount = manifest.get("amount")
    if not source_sheet or not invoice_number:
        return None, "manifest_provenance_incomplete"
    if isinstance(amount, bool) or not isinstance(amount, (int, float)):
        return None, "manifest_amount_invalid"
    candidate = {
        "manifest_path": manifest_path.as_posix(),
        "workbook_path": workbook_path.as_posix(),
        "pdf_path": pdf_path.as_posix(),
        "workbook_sha256": workbook_hash,
        "pdf_sha256": pdf_hash,
        "client_ref": client_key.replace("-", "_"),
        "service_period": service_period,
        "invoice_number": invoice_number,
        "source_sheet": source_sheet,
        "amount": float(amount),
        "invoice_status": str(manifest.get("status") or ""),
        "send_receipt_present": bool(manifest.get("latest_send_receipt_path")),
    }
    promotion = _verified_test_promotion(manifest)
    if promotion is not None:
        candidate["promotion"] = promotion
    return candidate, ""


def _base_result(client_ref: str, service_period: str, roots: Sequence[Path]) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "client_ref": client_ref,
        "service_period": service_period,
        "status": "NOT_FOUND",
        "canonical_candidate": None,
        "candidate_groups": [],
        "superseded_pdf_sha256": [],
        "rejections": [],
        "searched_roots": [Path(root).as_posix() for root in roots],
        "agentic_fallback_required": False,
        "authority_boundary": {
            "attachment_send_allowed": False,
            "email_send_allowed": False,
            "workbook_mutation_allowed": False,
            "ledger_posting_allowed": False,
        },
        "machine_proof": {
            "allowlisted_roots_only": True,
            "quarantine_excluded": True,
            "manifest_hashes_verified": False,
            "promotion_chain_verified": False,
            "external_action_performed": False,
            "attachment_sent": False,
            "workbook_mutation_performed": False,
            "ledger_mutation_performed": False,
        },
    }


def locate_invoice_artifacts(
    client_ref: str,
    service_period: str,
    *,
    roots: Sequence[Path],
) -> dict[str, Any]:
    normalized_client = _client_key(client_ref)
    normalized_period = str(service_period or "").strip()
    result = _base_result(normalized_client.replace("-", "_"), normalized_period, roots)
    if not normalized_client or not re.fullmatch(r"\d{4}-\d{2}", normalized_period):
        result["status"] = "INVALID_QUERY"
        result["rejections"].append(_rejection(Path("."), "invalid_client_or_period"))
        return result

    valid_candidates: list[dict[str, Any]] = []
    for raw_root in roots:
        root = Path(raw_root)
        if not root.is_dir():
            result["rejections"].append(_rejection(root, "search_root_missing"))
            continue
        for manifest_path in sorted(root.rglob("invoice_manifest.json")):
            if not _within(manifest_path, root):
                result["rejections"].append(_rejection(manifest_path, "path_outside_allowlisted_root"))
                continue
            if QUARANTINE_SEGMENT in manifest_path.parts:
                result["rejections"].append(_rejection(manifest_path, "quarantined_path"))
                continue
            candidate, reason = _verify_manifest_candidate(
                manifest_path,
                client_key=normalized_client,
                service_period=normalized_period,
            )
            if candidate is None:
                result["rejections"].append(_rejection(manifest_path, reason))
                continue
            valid_candidates.append(candidate)

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for candidate in valid_candidates:
        grouped[candidate["pdf_sha256"]].append(candidate)
    candidate_groups: list[dict[str, Any]] = []
    for pdf_hash in sorted(grouped):
        copies = sorted(grouped[pdf_hash], key=lambda item: item["manifest_path"])
        promotions = {
            json.dumps(item["promotion"], sort_keys=True, separators=(",", ":"))
            for item in copies
            if isinstance(item.get("promotion"), dict)
        }
        promoted_copy = next(
            (item for item in copies if isinstance(item.get("promotion"), dict)),
            None,
        )
        canonical = dict(
            promoted_copy if promoted_copy is not None and len(promotions) == 1 else copies[0]
        )
        if len(promotions) != 1:
            canonical.pop("promotion", None)
        canonical["duplicate_pdf_paths"] = sorted(item["pdf_path"] for item in copies)
        canonical["duplicate_manifest_paths"] = sorted(item["manifest_path"] for item in copies)
        candidate_groups.append(canonical)
    result["candidate_groups"] = candidate_groups
    if len(candidate_groups) == 1:
        result["status"] = "FOUND"
        result["canonical_candidate"] = candidate_groups[0]
        result["machine_proof"]["manifest_hashes_verified"] = True
    elif len(candidate_groups) > 1:
        all_hashes = {item["pdf_sha256"] for item in candidate_groups}
        promoted = []
        for candidate in candidate_groups:
            promotion = candidate.get("promotion")
            if not isinstance(promotion, dict):
                continue
            if set(promotion["supersedes_pdf_sha256"]) == all_hashes - {
                candidate["pdf_sha256"]
            }:
                promoted.append(candidate)
        if len(promoted) == 1:
            result["status"] = "FOUND"
            result["canonical_candidate"] = promoted[0]
            result["superseded_pdf_sha256"] = list(
                promoted[0]["promotion"]["supersedes_pdf_sha256"]
            )
            result["machine_proof"]["manifest_hashes_verified"] = True
            result["machine_proof"]["promotion_chain_verified"] = True
        else:
            result["status"] = "AMBIGUOUS"
    else:
        result["agentic_fallback_required"] = True
    return result


def locate_latest_invoice_artifact(
    client_ref: str,
    *,
    roots: Sequence[Path],
) -> dict[str, Any]:
    """Locate the newest manifest-backed service period for one client."""

    normalized_client = _client_key(client_ref)
    periods: set[str] = set()
    for raw_root in roots:
        root = Path(raw_root)
        if not root.is_dir():
            continue
        for manifest_path in sorted(root.rglob("invoice_manifest.json")):
            if not _within(manifest_path, root) or QUARANTINE_SEGMENT in manifest_path.parts:
                continue
            manifest = _json_object(manifest_path)
            if _client_key(manifest.get("client_slug")) != normalized_client:
                continue
            period = _period_from_manifest(manifest)
            if re.fullmatch(r"\d{4}-\d{2}", period):
                periods.add(period)

    if not periods:
        result = _base_result(normalized_client.replace("-", "_"), "", roots)
        result["agentic_fallback_required"] = True
        result["query_resolution"] = "latest_service_period_not_found"
        return result

    latest_period = sorted(periods, reverse=True)[0]
    result = locate_invoice_artifacts(
        normalized_client,
        latest_period,
        roots=roots,
    )
    result["query_resolution"] = "latest_manifest_service_period"
    result["available_service_periods"] = sorted(periods, reverse=True)
    return result
