"""Request-scoped state isolation for probes and dry-run replays.

Probe metadata is part of the request contract, not an incidental test-only
environment flag.  Stateful adapters consume the paths returned here so a
replay cannot fall through to production truth, recurrence, proposal, guided
review, or workflow stores.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
import re
from typing import Any, Mapping


SCHEMA_VERSION = "probe_state_contract_v0"
PROBE_RUN_MODES = frozenset({"test_dry_run", "test_live", "probe", "replay"})
DEFAULT_PROBE_STATE_ROOT = Path("/tmp/openclaw_probe_state")

STATE_FILENAMES = {
    "operator_truth_store_path": "operator_truth_store.json",
    "recurrence_rule_db_path": "recurrence_rules.sqlite3",
    "proposal_ledger_path": "proposal_ledger.json",
    "guided_review_state_path": "guided_review_state.json",
    "guided_review_root": "guided_review",
    "guided_review_read_model_root": "guided_review_read_models",
    "guided_review_receipt_root": "guided_review_receipts",
    "workflow_package_sqlite_path": "workflow_packages.sqlite3",
}


class ProbeStateBindingError(RuntimeError):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def _compact_scalar(value: Any, *, limit: int = 160) -> str:
    if not isinstance(value, (str, int)):
        return ""
    text = " ".join(str(value).replace("\x00", " ").split()).strip()
    return text[:limit]


def _first_scalar(payload: Mapping[str, Any], *keys: str) -> str:
    sources: list[Mapping[str, Any]] = [payload]
    for container_key in ("session", "context", "current_context", "event", "metadata"):
        value = payload.get(container_key)
        if isinstance(value, Mapping):
            sources.append(value)
    for source in sources:
        for key in keys:
            value = _compact_scalar(source.get(key))
            if value:
                return value
    return ""


def _root() -> Path:
    configured = os.environ.get("OPENCLAW_PROBE_STATE_ROOT", "").strip()
    candidate = (Path(configured) if configured else DEFAULT_PROBE_STATE_ROOT).resolve(strict=False)
    temp_root = Path("/tmp").resolve(strict=False)
    try:
        candidate.relative_to(temp_root)
    except ValueError as exc:
        raise ProbeStateBindingError("probe_root_not_temporary") from exc
    return candidate


def _namespace_token(payload: Mapping[str, Any], marker: str, run_mode: str, test_run_id: str) -> str:
    raw = "\0".join((test_run_id, marker, run_mode))
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:20]
    label_source = test_run_id or marker or "probe"
    label = re.sub(r"[^a-z0-9]+", "-", label_source.lower()).strip("-")[:32] or "probe"
    return f"{label}-{digest}"


def _effective_test_run_id(marker: str, run_mode: str, test_run_id: str) -> str:
    if test_run_id:
        return test_run_id
    digest = hashlib.sha256("\0".join((marker, run_mode)).encode("utf-8")).hexdigest()[:20]
    return f"probe-run-{digest}"


def _state_paths(root: Path, namespace: str) -> dict[str, str]:
    namespace_root = (root / namespace).resolve(strict=False)
    try:
        namespace_root.relative_to(root)
    except ValueError as exc:
        raise ProbeStateBindingError("probe_namespace_escaped_root") from exc
    paths: dict[str, str] = {}
    for key, filename in STATE_FILENAMES.items():
        candidate = (namespace_root / filename).resolve(strict=False)
        try:
            candidate.relative_to(root)
        except ValueError as exc:
            raise ProbeStateBindingError("probe_state_path_escaped_root") from exc
        paths[key] = str(candidate)
    return paths


def probe_activation_metadata(payload: Mapping[str, Any] | None) -> dict[str, Any]:
    source = payload if isinstance(payload, Mapping) else {}
    marker = _first_scalar(source, "probe_marker", "test_marker")
    run_mode = _first_scalar(source, "run_mode", "requested_run_mode").lower()
    test_run_id = _first_scalar(source, "test_run_id", "probe_run_id", "replay_id")
    return {
        "active": bool(marker) or run_mode in PROBE_RUN_MODES,
        "probe_marker": marker or ("OPENCLAW_PROBE_REPLAY" if run_mode in PROBE_RUN_MODES else ""),
        "run_mode": run_mode or ("probe" if marker else "production"),
        "test_run_id": test_run_id,
    }


def resolve_probe_state_contract(payload: Mapping[str, Any] | None) -> dict[str, Any]:
    source = payload if isinstance(payload, Mapping) else {}
    activation = probe_activation_metadata(source)
    marker = str(activation["probe_marker"] or "")
    run_mode = str(activation["run_mode"] or "")
    test_run_id = str(activation["test_run_id"] or "")
    active = bool(activation["active"])
    if not active:
        return {
            "schema_version": SCHEMA_VERSION,
            "active": False,
            "probe_marker": "",
            "run_mode": run_mode or "production",
            "test_run_id": "",
            "namespace": "",
            "state_paths": {},
            "production_state_allowed": True,
        }

    test_run_id = _effective_test_run_id(marker, run_mode, test_run_id)
    namespace = _namespace_token(source, marker, run_mode, test_run_id)
    root = _root()
    return {
        "schema_version": SCHEMA_VERSION,
        "active": True,
        "probe_marker": marker or "OPENCLAW_PROBE_REPLAY",
        "run_mode": run_mode or "probe",
        "test_run_id": test_run_id,
        "namespace": namespace,
        "state_paths": _state_paths(root, namespace),
        "production_state_allowed": False,
    }


def bind_probe_state_session(
    payload: Mapping[str, Any] | None,
    session: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    bound = dict(session or {})
    source = dict(payload or {})
    for key, value in bound.items():
        source.setdefault(key, value)
    contract = resolve_probe_state_contract(source)
    if not contract["active"]:
        return bound
    # Never trust caller-supplied namespace/path material.  Active probe state
    # is derived again on every seam crossing and overwrites all such values.
    for key in (*STATE_FILENAMES, "probe_state_namespace", "probe_state_contract_status"):
        bound.pop(key, None)
    bound.update(
        {
            "probe_marker": contract["probe_marker"],
            "run_mode": contract["run_mode"],
            "test_run_id": contract["test_run_id"],
            "probe_state_namespace": contract["namespace"],
            "probe_state_contract_status": "isolated",
            **contract["state_paths"],
        }
    )
    return bound


def validate_bound_probe_session(session: Mapping[str, Any] | None) -> bool:
    if not isinstance(session, Mapping):
        return False
    if str(session.get("probe_state_contract_status") or "") != "isolated":
        return False
    try:
        expected = resolve_probe_state_contract(session)
    except ProbeStateBindingError:
        return False
    if not expected["active"]:
        return False
    if str(session.get("probe_state_namespace") or "") != expected["namespace"]:
        return False
    return all(
        str(session.get(key) or "") == str(expected["state_paths"].get(key) or "")
        for key in STATE_FILENAMES
    )


__all__ = [
    "DEFAULT_PROBE_STATE_ROOT",
    "ProbeStateBindingError",
    "PROBE_RUN_MODES",
    "SCHEMA_VERSION",
    "STATE_FILENAMES",
    "bind_probe_state_session",
    "probe_activation_metadata",
    "resolve_probe_state_contract",
    "validate_bound_probe_session",
]
