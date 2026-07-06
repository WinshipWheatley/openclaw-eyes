"""Versioned hot-swap block registry for OpenClaw modules.

The registry owns immutable block-version metadata and active-version pointers.
It is deliberately local and explicit: callers must resolve through this module
to observe a swap. It does not rewrite source files, start services, send
messages, move money, or mutate any live ledger.
"""

from __future__ import annotations

import copy
import json
from datetime import datetime, timezone
from typing import Any, Callable, Mapping

try:
    from domain_module_registry import authority_boundary as _domain_authority_boundary
except Exception:  # noqa: BLE001 - keep this module importable in isolation.
    _domain_authority_boundary = None


SCHEMA_VERSION = "versioned_block_registry_v0"
HealthCheck = Callable[[Mapping[str, Any]], Mapping[str, Any] | bool]


def stable_json(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def block_registry_authority_boundary() -> dict[str, bool]:
    """Return the authority boundary for block-registry pointer management."""

    inherited = _domain_authority_boundary() if _domain_authority_boundary is not None else {}
    boundary = {
        "read_only": False,
        "local_registry_pointer_update_allowed": True,
        "in_memory_only": True,
        "runtime_mutation_allowed": False,
        "source_rewrite_allowed": False,
        "ledger_mutation_allowed": False,
        "workflow_activation_allowed": False,
        "external_call_allowed": False,
        "send_or_payment_allowed": False,
        "approval_granted": False,
    }
    for key in (
        "runtime_mutation_allowed",
        "ledger_mutation_allowed",
        "workflow_activation_allowed",
        "external_call_allowed",
        "send_or_payment_allowed",
        "approval_granted",
    ):
        if inherited.get(key):
            boundary[key] = False
    return boundary


def new_block_registry(*, created_at: str | None = None) -> dict[str, Any]:
    """Return an empty versioned block registry."""

    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": created_at or _utc_now(),
        "authority_boundary": block_registry_authority_boundary(),
        "blocks": {},
        "copies": {},
        "events": [],
        "machine_proof": {
            "immutable_versions": True,
            "active_pointer_indirection": True,
            "old_versions_retained": True,
            "auto_rollback_supported": True,
            "live_runtime_mutation_authorized": False,
        },
    }


def _require_registry(registry: Mapping[str, Any]) -> None:
    if registry.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(f"registry schema_version must be {SCHEMA_VERSION}")


def _require_id(value: str, field: str) -> str:
    clean = str(value or "").strip()
    if not clean:
        raise ValueError(f"{field} is required")
    return clean


def _ensure_block(registry: dict[str, Any], block_id: str) -> dict[str, Any]:
    blocks = registry.setdefault("blocks", {})
    return blocks.setdefault(
        block_id,
        {
            "block_id": block_id,
            "versions": {},
            "active_version": None,
            "last_known_good_version": None,
            "active_pointer_history": [],
        },
    )


def _event(registry: dict[str, Any], event_type: str, **payload: Any) -> dict[str, Any]:
    events = registry.setdefault("events", [])
    event = {
        "event_id": f"block_evt_{len(events) + 1:06d}",
        "event_type": event_type,
        "created_at": payload.pop("created_at", None) or _utc_now(),
        **payload,
    }
    events.append(event)
    return event


def _version_payload(
    *,
    block_id: str,
    version: str,
    impl_ref: str,
    provenance: Mapping[str, Any],
    metrics: Mapping[str, Any],
    created_at: str | None,
) -> dict[str, Any]:
    test_pass = metrics.get("test_pass") if isinstance(metrics, Mapping) else None
    return {
        "block_id": block_id,
        "version": version,
        "impl_ref": impl_ref,
        "provenance": copy.deepcopy(dict(provenance)),
        "metrics": copy.deepcopy(dict(metrics)),
        "created_at": created_at or _utc_now(),
        "immutable": True,
        "health_status": "passed" if test_pass is True else "unknown",
        "last_health_check": None,
    }


def register_block_version(
    registry: dict[str, Any],
    *,
    block_id: str,
    version: str,
    impl_ref: str,
    provenance: Mapping[str, Any],
    metrics: Mapping[str, Any],
    created_at: str | None = None,
) -> dict[str, Any]:
    """Register an immutable block version and set first version active."""

    _require_registry(registry)
    block_id = _require_id(block_id, "block_id")
    version = _require_id(version, "version")
    impl_ref = _require_id(impl_ref, "impl_ref")
    block = _ensure_block(registry, block_id)
    candidate = _version_payload(
        block_id=block_id,
        version=version,
        impl_ref=impl_ref,
        provenance=provenance,
        metrics=metrics,
        created_at=created_at,
    )
    existing = block["versions"].get(version)
    if existing is not None:
        if stable_json(existing) != stable_json(candidate):
            raise ValueError(f"block version is immutable once registered: {block_id}@{version}")
        return copy.deepcopy(existing)

    block["versions"][version] = candidate
    _event(
        registry,
        "register_version",
        block_id=block_id,
        version=version,
        impl_ref=impl_ref,
        metrics=copy.deepcopy(dict(metrics)),
    )
    if block.get("active_version") is None:
        block["active_version"] = version
        if candidate["health_status"] == "passed":
            block["last_known_good_version"] = version
        block["active_pointer_history"].append(
            {
                "from_version": None,
                "to_version": version,
                "reason": "initial_registration",
            }
        )
        _event(registry, "set_initial_active", block_id=block_id, version=version)
    return copy.deepcopy(candidate)


def resolve_active_block(registry: Mapping[str, Any], block_id: str) -> dict[str, Any]:
    """Resolve a block through its active-version pointer."""

    _require_registry(registry)
    block_id = _require_id(block_id, "block_id")
    block = (registry.get("blocks") or {}).get(block_id)
    if not isinstance(block, Mapping):
        raise KeyError(block_id)
    active_version = block.get("active_version")
    if not active_version:
        raise KeyError(f"{block_id} has no active version")
    version = (block.get("versions") or {}).get(active_version)
    if not isinstance(version, Mapping):
        raise KeyError(f"{block_id}@{active_version}")
    return copy.deepcopy(dict(version))


def _normalize_health_check(receipt: Mapping[str, Any] | bool | None, version: Mapping[str, Any]) -> dict[str, Any]:
    if receipt is None:
        return {
            "passed": True,
            "receipt_id": "implicit_health_check_not_provided",
            "details": "No health_check callback supplied; pointer update only.",
        }
    if isinstance(receipt, bool):
        return {
            "passed": receipt,
            "receipt_id": f"boolean_health_check:{version.get('block_id')}@{version.get('version')}",
            "details": "",
        }
    normalized = dict(receipt)
    normalized["passed"] = bool(normalized.get("passed"))
    normalized.setdefault("receipt_id", f"health_check:{version.get('block_id')}@{version.get('version')}")
    normalized.setdefault("details", "")
    return normalized


def promote_block_version(
    registry: dict[str, Any],
    *,
    block_id: str,
    version: str,
    health_check: HealthCheck | None = None,
    swapped_by: str = "unknown",
) -> dict[str, Any]:
    """Promote a version through the active pointer and auto-rollback on failed health."""

    _require_registry(registry)
    block_id = _require_id(block_id, "block_id")
    version = _require_id(version, "version")
    block = _ensure_block(registry, block_id)
    versions = block["versions"]
    if version not in versions:
        raise KeyError(f"{block_id}@{version}")

    previous_version = block.get("active_version")
    block["active_version"] = version
    block["active_pointer_history"].append(
        {
            "from_version": previous_version,
            "to_version": version,
            "reason": "promote_optimized_version",
            "swapped_by": swapped_by,
        }
    )
    _event(
        registry,
        "promote_active",
        block_id=block_id,
        from_version=previous_version,
        to_version=version,
        swapped_by=swapped_by,
    )

    candidate = versions[version]
    receipt = _normalize_health_check(health_check(copy.deepcopy(candidate)) if health_check else None, candidate)
    candidate["last_health_check"] = receipt

    if receipt["passed"]:
        candidate["health_status"] = "passed"
        block["last_known_good_version"] = version
        _event(
            registry,
            "health_check_passed",
            block_id=block_id,
            version=version,
            receipt_id=receipt["receipt_id"],
            details=receipt.get("details", ""),
        )
        return {
            "status": "active",
            "block_id": block_id,
            "active_version": version,
            "previous_version": previous_version,
            "health_check": receipt,
        }

    candidate["health_status"] = "failed"
    _event(
        registry,
        "health_check_failed",
        block_id=block_id,
        version=version,
        receipt_id=receipt["receipt_id"],
        details=receipt.get("details", ""),
    )
    rollback_version = previous_version or block.get("last_known_good_version")
    if rollback_version is None:
        block["active_version"] = None
    else:
        block["active_version"] = rollback_version
    _event(
        registry,
        "rollback_active",
        block_id=block_id,
        failed_version=version,
        rolled_back_to=rollback_version,
        receipt_id=receipt["receipt_id"],
        swapped_by="auto_rollback",
    )
    return {
        "status": "rolled_back",
        "block_id": block_id,
        "failed_version": version,
        "rolled_back_to": rollback_version,
        "health_check": receipt,
    }


def register_block_copy(
    registry: dict[str, Any],
    *,
    copy_id: str,
    block_id: str,
    observed_version: str,
    location_ref: str,
) -> dict[str, Any]:
    """Register an observed copy/consumer of a block."""

    _require_registry(registry)
    copy_id = _require_id(copy_id, "copy_id")
    block_id = _require_id(block_id, "block_id")
    observed_version = _require_id(observed_version, "observed_version")
    location_ref = _require_id(location_ref, "location_ref")
    if block_id not in registry.get("blocks", {}):
        raise KeyError(block_id)
    if observed_version not in registry["blocks"][block_id]["versions"]:
        raise KeyError(f"{block_id}@{observed_version}")
    copy_row = {
        "copy_id": copy_id,
        "block_id": block_id,
        "observed_version": observed_version,
        "location_ref": location_ref,
        "resolution_mode": "registry_pointer",
    }
    registry.setdefault("copies", {})[copy_id] = copy_row
    _event(
        registry,
        "copy_registered",
        copy_id=copy_id,
        block_id=block_id,
        observed_version=observed_version,
        location_ref=location_ref,
    )
    return copy.deepcopy(copy_row)


def resolve_block_for_copy(registry: Mapping[str, Any], copy_id: str) -> dict[str, Any]:
    """Resolve a registered copy through its block's active pointer."""

    _require_registry(registry)
    copy_id = _require_id(copy_id, "copy_id")
    copy_row = (registry.get("copies") or {}).get(copy_id)
    if not isinstance(copy_row, Mapping):
        raise KeyError(copy_id)
    return resolve_active_block(registry, str(copy_row["block_id"]))


def _optimization_score(version: Mapping[str, Any]) -> float:
    metrics = version.get("metrics") if isinstance(version.get("metrics"), Mapping) else {}
    try:
        return float(metrics.get("optimization_score", 0.0))
    except (TypeError, ValueError):
        return 0.0


def _best_version(block: Mapping[str, Any]) -> str | None:
    versions = block.get("versions") if isinstance(block.get("versions"), Mapping) else {}
    if not versions:
        return None
    return max(versions, key=lambda version: _optimization_score(versions[version]))


def block_drift_report(registry: Mapping[str, Any], block_id: str) -> dict[str, Any]:
    """Surface duplicate-copy drift against the active and optimized versions."""

    _require_registry(registry)
    block_id = _require_id(block_id, "block_id")
    block = (registry.get("blocks") or {}).get(block_id)
    if not isinstance(block, Mapping):
        raise KeyError(block_id)
    active_version = str(block.get("active_version") or "")
    best_version = _best_version(block)
    copies = [
        dict(copy_row)
        for copy_row in (registry.get("copies") or {}).values()
        if isinstance(copy_row, Mapping) and copy_row.get("block_id") == block_id
    ]
    out_of_date = [copy_row for copy_row in copies if copy_row.get("observed_version") != active_version]
    return {
        "block_id": block_id,
        "active_version": active_version,
        "optimized_version": best_version,
        "copy_count": len(copies),
        "copies_on_active_version": sum(1 for copy_row in copies if copy_row.get("observed_version") == active_version),
        "copies_on_optimized_version": sum(1 for copy_row in copies if copy_row.get("observed_version") == best_version),
        "out_of_date_copies": out_of_date,
        "versions_retained_count": len(block.get("versions") or {}),
    }


def converge_block_copies(registry: dict[str, Any], block_id: str, *, actor: str = "unknown") -> dict[str, Any]:
    """Update observed copies to the active version and record each swap."""

    _require_registry(registry)
    block_id = _require_id(block_id, "block_id")
    active_version = str((registry.get("blocks") or {}).get(block_id, {}).get("active_version") or "")
    if not active_version:
        raise KeyError(f"{block_id} has no active version")

    swapped: list[dict[str, Any]] = []
    for copy_id, copy_row in sorted((registry.get("copies") or {}).items()):
        if not isinstance(copy_row, dict) or copy_row.get("block_id") != block_id:
            continue
        previous = copy_row.get("observed_version")
        if previous == active_version:
            continue
        copy_row["observed_version"] = active_version
        event = _event(
            registry,
            "copy_swapped",
            copy_id=copy_id,
            block_id=block_id,
            from_version=previous,
            to_version=active_version,
            actor=actor,
        )
        swapped.append(event)

    return {
        "status": "converged",
        "block_id": block_id,
        "active_version": active_version,
        "swapped_copy_count": len(swapped),
        "events": swapped,
    }


def block_registry_status(registry: Mapping[str, Any]) -> dict[str, Any]:
    """Return compact registry status for Fable/operator inspection."""

    _require_registry(registry)
    return {
        "schema_version": SCHEMA_VERSION,
        "block_count": len(registry.get("blocks") or {}),
        "copy_count": len(registry.get("copies") or {}),
        "event_count": len(registry.get("events") or []),
        "authority_boundary": block_registry_authority_boundary(),
        "active_versions": {
            block_id: block.get("active_version")
            for block_id, block in sorted((registry.get("blocks") or {}).items())
            if isinstance(block, Mapping)
        },
    }
