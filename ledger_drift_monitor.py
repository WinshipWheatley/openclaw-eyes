"""Detect recurring one-ledger runtime repairs and turn them into buildable gaps.

The runtime guard is allowed to self-heal a packet once. This monitor is the next
layer: recurring guard repairs become normal self-improvement gaps that flow into the
Guardian-gated polish loop. It reads receipts only; it does not mutate production state.
"""
from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping


DEFAULT_PROTECTED_GENERATE_AUDIT_LOG = Path("/mnt/c/OpenClaw/logs/protected_generate_audit.jsonl")
DEFAULT_LEDGER_DRIFT_LOG = Path("/home/openclaw/.openclaw/business_ops/ledger_runtime_drift_receipts.jsonl")
SYNTHETIC_MARKERS = (
    ".pytest_openclaw",
    "/tmp/pytest-",
    "manual_guard_probe",
    "maestro_context_packet:test",
)


def _iter_jsonl(path: str | Path | None) -> Iterable[dict[str, Any]]:
    if path is None:
        return
    p = Path(path)
    try:
        lines = p.read_text(encoding="utf-8").splitlines()
    except Exception:
        return
    for line in lines:
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            yield row


def _receipt_from_audit_row(row: Mapping[str, Any]) -> dict[str, Any] | None:
    guard = row.get("ledger_runtime_guard")
    if not isinstance(guard, Mapping):
        return None
    if guard.get("status") != "ledger_runtime_repair_applied":
        return None
    receipt = guard.get("receipt")
    if isinstance(receipt, Mapping):
        out = dict(receipt)
    else:
        out = dict(guard)
    out.setdefault("builder_name", guard.get("builder_name"))
    out.setdefault("packet_id", row.get("packet_id"))
    out.setdefault("agent_id", row.get("agent"))
    out["_audit_route"] = row.get("route")
    out["_audit_receipt_id"] = row.get("receipt_id")
    return out


def _receipt_from_drift_row(row: Mapping[str, Any]) -> dict[str, Any] | None:
    if row.get("schema_version") != "ledger_runtime_drift_receipt_v0":
        return None
    if row.get("status") != "ledger_runtime_repair_applied":
        return None
    return dict(row)


def _strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, Mapping):
        out: list[str] = []
        for child in value.values():
            out.extend(_strings(child))
        return out
    if isinstance(value, (list, tuple, set)):
        out: list[str] = []
        for child in value:
            out.extend(_strings(child))
        return out
    if value is None:
        return []
    return [str(value)]


def _is_synthetic_receipt(receipt: Mapping[str, Any]) -> bool:
    if str(receipt.get("_audit_route") or "") == "injected_generator":
        return True
    joined = "\n".join(_strings(receipt))
    return any(marker in joined for marker in SYNTHETIC_MARKERS)


def _short_hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, ensure_ascii=True, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:10]


def _unique(values: Iterable[Any], *, limit: int = 8) -> list[str]:
    out: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if text and text not in out:
            out.append(text)
        if len(out) >= limit:
            break
    return out


def _gap_for_builder(builder_name: str, receipts: list[dict[str, Any]]) -> dict[str, Any]:
    packet_ids = _unique(receipt.get("packet_id") for receipt in receipts)
    agents = _unique(receipt.get("agent_id") for receipt in receipts)
    original_refs = _unique(
        ref
        for receipt in receipts
        for ref in receipt.get("original_source_refs", [])
        if isinstance(receipt.get("original_source_refs"), list)
    )
    repair_refs = _unique(
        ref
        for receipt in receipts
        for ref in receipt.get("repair_source_refs", [])
        if isinstance(receipt.get("repair_source_refs"), list)
    )
    digest = _short_hash(
        {
            "builder_name": builder_name,
            "original_refs": original_refs,
            "agents": agents,
        }
    )
    count = len(receipts)
    evidence = (
        f"{count} runtime ledger repair(s) fired for {builder_name}. "
        f"Agents: {', '.join(agents) or 'unknown'}. "
        f"Packet ids: {', '.join(packet_ids) or 'unknown'}. "
        f"Original refs: {', '.join(original_refs) or 'none recorded'}. "
        f"Ledger repair refs: {', '.join(repair_refs[:3]) or 'none recorded'}."
    )
    return {
        "id": f"ledger_source_drift:{digest}",
        "say": f"I caught {builder_name} pulling packet context from the wrong place; I repaired it from the ledger live, but the source path needs fixing.",
        "build_goal": (
            f"Use the runtime ledger drift evidence for {builder_name} to find why this packet path "
            "returned empty, unprovenanced, or wrong-source facts. Rewrite the source path to pull "
            "from context_source/the business-ops ledger directly, preserve the runtime guard as a "
            "fail-closed backup, and add a regression test proving this drift no longer recurs."
        ),
        "evidence": evidence,
        "ledger_drift_builder_name": builder_name,
        "ledger_drift_count": count,
        "ledger_drift_original_source_refs": original_refs,
        "ledger_drift_repair_source_refs": repair_refs,
    }


def detect_ledger_source_drift_gaps(
    *,
    audit_log_path: str | Path | None = DEFAULT_PROTECTED_GENERATE_AUDIT_LOG,
    drift_log_path: str | Path | None = DEFAULT_LEDGER_DRIFT_LOG,
    min_occurrences: int = 2,
    include_synthetic: bool = False,
) -> list[dict[str, Any]]:
    """Return fileable gaps for recurring runtime ledger guard repairs."""
    receipts: list[dict[str, Any]] = []
    for row in _iter_jsonl(audit_log_path):
        receipt = _receipt_from_audit_row(row)
        if receipt is not None:
            receipts.append(receipt)
    for row in _iter_jsonl(drift_log_path):
        receipt = _receipt_from_drift_row(row)
        if receipt is not None:
            receipts.append(receipt)

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for receipt in receipts:
        if not include_synthetic and _is_synthetic_receipt(receipt):
            continue
        builder_name = str(receipt.get("builder_name") or "unknown_builder").strip()
        grouped[builder_name].append(receipt)

    gaps = [
        _gap_for_builder(builder, rows)
        for builder, rows in sorted(grouped.items())
        if len(rows) >= max(1, int(min_occurrences))
    ]
    return gaps


__all__ = [
    "DEFAULT_LEDGER_DRIFT_LOG",
    "DEFAULT_PROTECTED_GENERATE_AUDIT_LOG",
    "detect_ledger_source_drift_gaps",
]
