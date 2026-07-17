"""Resolve operator proof-display requests to verified invoice artifacts."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Sequence

import invoice_artifact_locator
import workflow_package_queue


SCHEMA_VERSION = "invoice_proof_request_v0"
DEFAULT_INVOICE_ARTIFACT_ROOTS = (
    Path("/mnt/e/openclaw/artifacts/invoice_workbooks"),
    Path("/mnt/e/openclaw/codex_mac_bridge/from-codex-mac/invoice_handoffs"),
)

_DISPLAY_INTENT_RE = re.compile(
    r"\b(?:show|see|open|view|preview|pull\s+up|bring\s+up|let\s+me\s+see|let\s+me\s+get)\b",
    re.IGNORECASE,
)
_PROOF_SUBJECT_RE = re.compile(r"\b(?:proof|pdf|invoice|package|artifact)\b", re.IGNORECASE)
_SEND_INTENT_RE = re.compile(r"\b(?:send|email|submit|deliver)\b", re.IGNORECASE)

_CLIENT_ALIASES = (
    (re.compile(r"\bst\.?\s*anne(?:'s|s)?\b", re.IGNORECASE), "st_annes"),
    (re.compile(r"\bcapital\s+hilton\b", re.IGNORECASE), "capital_hilton"),
    (re.compile(r"\blive\s+arts(?:\s+md)?\b", re.IGNORECASE), "live_arts_md"),
    (re.compile(r"\breynolds(?:\s+tavern)?\b", re.IGNORECASE), "reynolds_tavern"),
)

_MONTHS = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}


def _source_text(payload: Mapping[str, Any]) -> str:
    for key in ("source_text", "operator_message", "text", "message", "query"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def is_invoice_proof_request(text: str) -> bool:
    value = str(text or "").strip()
    return bool(
        _DISPLAY_INTENT_RE.search(value)
        and _PROOF_SUBJECT_RE.search(value)
        and not _SEND_INTENT_RE.search(value)
    )


def _client_from_text(text: str) -> str:
    for pattern, client_ref in _CLIENT_ALIASES:
        if pattern.search(text):
            return client_ref
    try:
        intent = workflow_package_queue.classify_intent(text)
    except Exception:
        return ""
    workflow_ref = str(intent.get("workflow_ref") or "")
    client_ref = str(intent.get("client_ref") or "")
    if client_ref and "invoice" in workflow_ref:
        return client_ref
    return ""


def _period_from_text(text: str, *, created_at: str = "") -> str:
    explicit = re.search(r"\b(20\d{2})-(0[1-9]|1[0-2])\b", str(text or ""))
    if explicit:
        return explicit.group(0)
    lowered = str(text or "").lower()
    month = next((number for name, number in _MONTHS.items() if re.search(rf"\b{name}\b", lowered)), 0)
    if not month:
        return ""
    year_match = re.search(r"\b(20\d{2})\b", lowered)
    if year_match:
        year = int(year_match.group(1))
    else:
        try:
            year = datetime.fromisoformat(str(created_at).replace("Z", "+00:00")).year
        except (TypeError, ValueError):
            return ""
    return f"{year:04d}-{month:02d}"


def _json_object(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _chat_ref(payload: Mapping[str, Any]) -> str:
    direct = str(payload.get("telegram_chat_ref") or "").strip()
    if direct:
        return direct
    correlation = payload.get("correlation")
    if isinstance(correlation, Mapping):
        return str(correlation.get("telegram_chat_ref") or "").strip()
    return ""


def _same_chat(left: Mapping[str, Any], right: Mapping[str, Any]) -> bool:
    left_ref = _chat_ref(left)
    right_ref = _chat_ref(right)
    if left_ref and right_ref:
        return left_ref == right_ref
    return bool(
        str(left.get("source_channel") or "") == str(right.get("source_channel") or "")
        and str(left.get("thread_ref") or left.get("current_thread_ref") or "")
        == str(right.get("thread_ref") or right.get("current_thread_ref") or "")
    )


def _prior_invoice_context(
    raw_request: Mapping[str, Any],
    request_path: Path,
    *,
    max_candidates: int = 24,
) -> dict[str, str]:
    current_created_at = str(raw_request.get("created_at") or "")
    candidates: list[tuple[int, str, Path]] = []
    try:
        paths = request_path.parent.glob("mission_control_operator_instruction_request_*.json")
        for path in paths:
            if path == request_path or not path.is_file():
                continue
            stat = path.stat()
            candidates.append((stat.st_mtime_ns, path.name, path))
    except OSError:
        return {}

    for _mtime, _name, path in sorted(candidates, reverse=True)[:max_candidates]:
        prior = _json_object(path)
        if not prior or not _same_chat(raw_request, prior):
            continue
        prior_created_at = str(prior.get("created_at") or "")
        if current_created_at and prior_created_at and prior_created_at >= current_created_at:
            continue
        prior_text = _source_text(prior)
        client_ref = _client_from_text(prior_text)
        if not client_ref:
            continue
        return {
            "client_ref": client_ref,
            "service_period": _period_from_text(
                prior_text,
                created_at=prior_created_at,
            ),
            "context_source": "prior_same_chat_request",
            "context_request_id": str(
                prior.get("request_id") or prior.get("source_request_id") or path.stem
            ),
        }
    return {}


def resolve_invoice_proof_request(
    raw_request: Mapping[str, Any],
    request_path: Path,
    *,
    roots: Sequence[Path] | None = None,
) -> dict[str, Any]:
    text = _source_text(raw_request)
    result: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "matched": is_invoice_proof_request(text),
        "status": "NOT_PROOF_REQUEST",
        "client_ref": "",
        "service_period": "",
        "context_source": "",
        "context_request_id": "",
        "locator_result": {},
        "model_call_performed": False,
        "external_action_performed": False,
    }
    if not result["matched"]:
        return result

    created_at = str(raw_request.get("created_at") or "")
    client_ref = _client_from_text(text)
    service_period = _period_from_text(text, created_at=created_at)
    if client_ref:
        context_source = "current_request"
        context_request_id = str(
            raw_request.get("request_id") or raw_request.get("source_request_id") or ""
        )
    else:
        prior = _prior_invoice_context(raw_request, request_path)
        client_ref = prior.get("client_ref", "")
        service_period = service_period or prior.get("service_period", "")
        context_source = prior.get("context_source", "")
        context_request_id = prior.get("context_request_id", "")

    result.update(
        {
            "client_ref": client_ref,
            "service_period": service_period,
            "context_source": context_source,
            "context_request_id": context_request_id,
        }
    )
    if not client_ref:
        result["status"] = "CONTEXT_REQUIRED"
        return result

    search_roots = tuple(Path(root) for root in (roots or DEFAULT_INVOICE_ARTIFACT_ROOTS))
    locator_result = (
        invoice_artifact_locator.locate_invoice_artifacts(
            client_ref,
            service_period,
            roots=search_roots,
        )
        if service_period
        else invoice_artifact_locator.locate_latest_invoice_artifact(
            client_ref,
            roots=search_roots,
        )
    )
    result["locator_result"] = locator_result
    result["service_period"] = str(locator_result.get("service_period") or service_period)
    result["status"] = str(locator_result.get("status") or "NOT_FOUND")
    return result


def _mac_path(path: str) -> str:
    value = str(path or "")
    bridge_root = "/mnt/e/openclaw"
    if value == bridge_root:
        return "/Volumes/openclaw_e"
    if value.startswith(bridge_root + "/"):
        return "/Volumes/openclaw_e" + value[len(bridge_root) :]
    return value


def proof_artifact_from_resolution(resolution: Mapping[str, Any]) -> dict[str, Any] | None:
    locator_result = resolution.get("locator_result")
    if not isinstance(locator_result, Mapping) or locator_result.get("status") != "FOUND":
        return None
    candidate = locator_result.get("canonical_candidate")
    if not isinstance(candidate, Mapping):
        return None
    bridge_path = str(candidate.get("pdf_path") or "")
    pdf_hash = str(candidate.get("pdf_sha256") or "")
    if not bridge_path or not pdf_hash:
        return None
    client_ref = str(candidate.get("client_ref") or resolution.get("client_ref") or "invoice")
    service_period = str(candidate.get("service_period") or resolution.get("service_period") or "latest")
    return {
        "artifact_id": f"invoice_pdf_{client_ref}_{service_period}_{pdf_hash[:12]}",
        "artifact_type": "proof_pdf",
        "role": "invoice_pdf",
        "mime_type": "application/pdf",
        "path": _mac_path(bridge_path),
        "bridge_path": bridge_path,
        "sha256": "sha256:" + pdf_hash,
        "client_ref": client_ref,
        "service_period": service_period,
        "presentation": {
            "presenter": "ProofPresenter",
            "mode": "quicklook",
            "should_open": True,
        },
        "review_only": True,
        "client_send_allowed": False,
        "external_action_allowed": False,
    }


def action_receipt_refs_for_artifact(artifact: Mapping[str, Any]) -> tuple[str, ...]:
    digest = hashlib.sha256(
        "\0".join(
            (
                str(artifact.get("artifact_id") or ""),
                str(artifact.get("sha256") or ""),
                str(artifact.get("path") or ""),
            )
        ).encode("utf-8")
    ).hexdigest()[:20]
    return (
        f"artifact_locator:{digest}",
        f"proof_presenter_request:{digest}",
    )


def artifact_label(resolution: Mapping[str, Any]) -> str:
    client_ref = str(resolution.get("client_ref") or "invoice")
    client_display = {
        "st_annes": "St. Anne's",
        "capital_hilton": "Capital Hilton",
        "live_arts_md": "Live Arts MD",
        "reynolds_tavern": "Reynolds Tavern",
    }.get(client_ref, client_ref.replace("_", " ").title())
    period = str(resolution.get("service_period") or "")
    try:
        period_display = datetime.strptime(period, "%Y-%m").strftime("%B %Y")
    except ValueError:
        period_display = "latest"
    return f"{client_display} {period_display} invoice PDF proof"


__all__ = [
    "DEFAULT_INVOICE_ARTIFACT_ROOTS",
    "SCHEMA_VERSION",
    "action_receipt_refs_for_artifact",
    "artifact_label",
    "is_invoice_proof_request",
    "proof_artifact_from_resolution",
    "resolve_invoice_proof_request",
]
