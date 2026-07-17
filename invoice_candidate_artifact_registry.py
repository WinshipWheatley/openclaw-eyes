"""Hash-verify review candidates before an operator surface may present them."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping


SCHEMA_VERSION = "invoice_candidate_artifact_registry_v0"
DEFAULT_REGISTRY_PATH = Path("generated/read_models/invoice_candidate_artifact_registry.json")
VERIFIED_REVIEW_STATUS = "verified_review_candidate"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _client_ref(value: object) -> str:
    key = re.sub(r"[^a-z0-9]+", "_", str(value or "").strip().lower()).strip("_")
    return {"st_anne": "st_annes", "st_anne_s": "st_annes"}.get(key, key)


def _load(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _verified_candidate(row: Mapping[str, Any]) -> tuple[dict[str, Any] | None, str]:
    if str(row.get("status") or "") != VERIFIED_REVIEW_STATUS:
        return None, "status_not_verified_review_candidate"
    if row.get("active_for_review") is not True or row.get("finalized") is not False:
        return None, "candidate_not_active_review_only"
    pdf_path = Path(str(row.get("pdf_path") or ""))
    image_path = Path(str(row.get("rendered_image_path") or ""))
    if not pdf_path.is_absolute() or not pdf_path.is_file():
        return None, "candidate_pdf_missing"
    if not image_path.is_absolute() or not image_path.is_file():
        return None, "candidate_rendered_image_missing"
    pdf_sha = str(row.get("pdf_sha256") or "").lower()
    image_sha = str(row.get("rendered_image_sha256") or "").lower()
    if not re.fullmatch(r"[0-9a-f]{64}", pdf_sha) or _sha256(pdf_path) != pdf_sha:
        return None, "candidate_pdf_hash_mismatch"
    if not re.fullmatch(r"[0-9a-f]{64}", image_sha) or _sha256(image_path) != image_sha:
        return None, "candidate_rendered_image_hash_mismatch"
    source_receipt_ref = str(row.get("source_receipt_ref") or "").strip()
    if not source_receipt_ref:
        return None, "candidate_source_receipt_missing"
    candidate = dict(row)
    candidate.update(
        {
            "client_ref": _client_ref(row.get("client_ref")),
            "pdf_path": pdf_path.as_posix(),
            "pdf_sha256": pdf_sha,
            "rendered_image_path": image_path.as_posix(),
            "rendered_image_sha256": image_sha,
            "invoice_status": VERIFIED_REVIEW_STATUS,
            "artifact_variant": "candidate",
            "send_receipt_present": False,
        }
    )
    return candidate, ""


def locate_candidate_invoice_artifact(
    client_ref: str,
    service_period: str,
    *,
    registry_path: Path = DEFAULT_REGISTRY_PATH,
) -> dict[str, Any]:
    """Return exactly one active, hash-verified candidate or fail closed."""

    normalized_client = _client_ref(client_ref)
    normalized_period = str(service_period or "").strip()
    result: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "client_ref": normalized_client,
        "service_period": normalized_period,
        "status": "NOT_FOUND",
        "canonical_candidate": None,
        "candidate_groups": [],
        "rejections": [],
        "registry_path": Path(registry_path).as_posix(),
        "agentic_fallback_required": False,
        "machine_proof": {
            "registry_schema_verified": False,
            "artifact_hashes_verified": False,
            "external_action_performed": False,
        },
    }
    payload = _load(Path(registry_path))
    if payload.get("schema_version") != SCHEMA_VERSION:
        result["status"] = "REGISTRY_INVALID"
        result["rejections"].append({"reason": "registry_missing_or_schema_invalid"})
        return result
    result["machine_proof"]["registry_schema_verified"] = True
    rows = payload.get("candidates")
    if not isinstance(rows, list):
        result["status"] = "REGISTRY_INVALID"
        result["rejections"].append({"reason": "candidates_not_list"})
        return result

    valid: list[dict[str, Any]] = []
    for index, raw in enumerate(rows):
        if not isinstance(raw, Mapping):
            result["rejections"].append({"index": index, "reason": "candidate_not_object"})
            continue
        if _client_ref(raw.get("client_ref")) != normalized_client:
            continue
        if str(raw.get("service_period") or "") != normalized_period:
            continue
        candidate, reason = _verified_candidate(raw)
        if candidate is None:
            result["rejections"].append({"index": index, "reason": reason})
            continue
        valid.append(candidate)

    result["candidate_groups"] = valid
    if len(valid) == 1:
        result["status"] = "FOUND"
        result["canonical_candidate"] = valid[0]
        result["machine_proof"]["artifact_hashes_verified"] = True
    elif len(valid) > 1:
        result["status"] = "AMBIGUOUS"
    return result


__all__ = [
    "DEFAULT_REGISTRY_PATH",
    "SCHEMA_VERSION",
    "locate_candidate_invoice_artifact",
]
