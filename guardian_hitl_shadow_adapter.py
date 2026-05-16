"""Guardian/HITL SQLite shadow adapter read-model v0.

This module maps legacy and compatibility Guardian/HITL surfaces into the
canonical SQLite Guardian/Operator Action contract shape for visibility only.
It does not read live HITL JSON contents, write live approval state, create
approval requests, send messages, import Repo B code, or change runtime
authority.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from guardian_hitl_sqlite_authority_contract import (
    CANONICAL_DECISION_REQUIRED_FIELDS,
    CANONICAL_PAYLOAD_REQUIRED_FIELDS,
    CANONICAL_RECEIPT_REQUIRED_FIELDS,
    FORBIDDEN_PAYLOAD_KEYS,
    build_guardian_hitl_sqlite_authority_contract,
)
from guardian_hitl_surface_disposition import build_guardian_hitl_surface_disposition


ROOT = Path(__file__).resolve().parent
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
SCHEMA_VERSION = "guardian_hitl_shadow_adapter_v0"
JSON_EXPORT_NAME = "guardian_hitl_shadow_adapter.json"
OPERATOR_EXPORT_NAME = "guardian_hitl_shadow_adapter_OPERATOR.md"

OLD_HITL_CLASSIFICATION = "authority_conflict_reconcile_first"
CHOICE_PENDING_CLASSIFICATION = "workflow_choice_substrate"

MAPPED_DISPOSITIONS = {
    "keep_compatibility_shim",
    "replace_with_sqlite_operator_action",
    "retire_after_migration",
}

ADAPTER_STRATEGIES = {
    "chief_approval_brain": "shadow_write_to_sqlite_later",
    "chief_approval_policy": "read_only_reference",
    "chief_guardian_listener": "read_only_reference_then_translate_legacy_request_to_operator_action",
    "chief_guardian_sender": "read_only_reference_then_notification_receipt_shadow",
    "chief_router_approval_reply": "read_only_reference_then_translate_legacy_request_to_operator_action",
    "chief_watcher_approval_replay": "read_only_reference_then_notification_receipt_shadow",
    "approval_pending_json": "shadow_write_to_sqlite_later",
    "hitl_pending_store": "shadow_write_to_sqlite_later_then_translate_legacy_request_to_operator_action",
    "hitl_action_service": "replace_backing_store_with_sqlite_contract_later",
    "hitl_notification_service": "freeze_until_replaced_then_notification_receipt_shadow",
    "hitl_pending_state_json": "shadow_write_to_sqlite_later",
    "hitl_audit_jsonl": "read_only_reference_then_sqlite_receipts",
    "hitl_notifications_jsonl": "retire_after_equivalent_receipts_proven",
    "hitl_pending_action_legacy": "retire_after_equivalent_proven",
    "approval_log_md": "retire_after_receipt_export_proven",
    "google_access_broker_approval_hook": "translate_legacy_request_to_operator_action_later",
}

TARGET_TABLES_BY_SURFACE = {
    "chief_approval_brain": ["guardian_hitl_approval_requests", "guardian_hitl_approval_decisions"],
    "chief_approval_policy": ["guardian_hitl_legacy_authority_refs"],
    "chief_guardian_listener": ["guardian_hitl_approval_decisions", "guardian_hitl_approval_receipts"],
    "chief_guardian_sender": ["guardian_hitl_approval_receipts"],
    "chief_router_approval_reply": ["guardian_hitl_approval_decisions", "guardian_hitl_approval_receipts"],
    "chief_watcher_approval_replay": ["guardian_hitl_approval_receipts"],
    "approval_pending_json": ["guardian_hitl_approval_requests", "guardian_hitl_legacy_authority_refs"],
    "hitl_pending_store": ["guardian_hitl_approval_requests", "guardian_hitl_approval_decisions"],
    "hitl_action_service": ["guardian_hitl_approval_requests", "guardian_hitl_approval_decisions"],
    "hitl_notification_service": ["guardian_hitl_approval_receipts"],
    "hitl_pending_state_json": ["guardian_hitl_approval_requests", "guardian_hitl_legacy_authority_refs"],
    "hitl_audit_jsonl": ["guardian_hitl_approval_receipts", "guardian_hitl_legacy_authority_refs"],
    "hitl_notifications_jsonl": ["guardian_hitl_approval_receipts", "guardian_hitl_legacy_authority_refs"],
    "hitl_pending_action_legacy": ["guardian_hitl_legacy_authority_refs"],
    "approval_log_md": ["guardian_hitl_approval_receipts", "guardian_hitl_legacy_authority_refs"],
    "google_access_broker_approval_hook": ["guardian_hitl_approval_requests", "guardian_hitl_approval_receipts"],
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _export_root_path(export_root: str | Path) -> Path:
    path = Path(export_root)
    if path.is_absolute():
        return path
    return ROOT / path


def _target_tables(surface_id: str) -> list[str]:
    return TARGET_TABLES_BY_SURFACE.get(surface_id, ["guardian_hitl_legacy_authority_refs"])


def _old_hitl_classification(surface: dict[str, Any]) -> str:
    text = " ".join(
        str(surface.get(key, ""))
        for key in (
            "surface_id",
            "file_path",
            "current_state_store",
            "approval_object_shape",
            "reason",
        )
    ).lower()
    if any(marker in text for marker in ("approval_pending", "hitl_", ".json", ".jsonl")):
        return OLD_HITL_CLASSIFICATION
    if surface.get("disposition") == "replace_with_sqlite_operator_action":
        return OLD_HITL_CLASSIFICATION
    return "compatibility_reference_only"


def _shadow_record(surface: dict[str, Any], contract: dict[str, Any]) -> dict[str, Any]:
    surface_id = surface["surface_id"]
    return {
        "shadow_record_id": f"shadow_{surface_id}",
        "source_surface_id": surface_id,
        "source_surface": surface["surface"],
        "source_file_path": surface["file_path"],
        "source_disposition": surface["disposition"],
        "current_role": surface["current_role"],
        "current_state_store": surface["current_state_store"],
        "approval_object_shape": surface["approval_object_shape"],
        "adapter_strategy": ADAPTER_STRATEGIES.get(surface_id, "read_only_reference"),
        "old_hitl_classification": _old_hitl_classification(surface),
        "canonical_target": {
            "state_store": contract["canonical_state_store"],
            "target_tables": _target_tables(surface_id),
            "required_request_fields": list(CANONICAL_PAYLOAD_REQUIRED_FIELDS),
            "required_decision_fields": list(CANONICAL_DECISION_REQUIRED_FIELDS),
            "required_receipt_fields": list(CANONICAL_RECEIPT_REQUIRED_FIELDS),
        },
        "canonical_shape_status": "metadata_shape_only_not_persisted",
        "runtime_authority": False,
        "runtime_authority_changed": False,
        "shadow_only": True,
        "dual_write_enabled": False,
        "caller_switched": False,
        "old_hitl_deleted": False,
        "live_legacy_store_read": False,
        "live_legacy_store_written": False,
        "live_legacy_store_deleted": False,
        "raw_content_read": False,
        "real_approval_request_created": False,
        "canonical_request_persisted": False,
        "can_approve": False,
        "can_execute": False,
        "raw_command_or_shell_allowed": False,
        "repo_b_imported_or_executed": False,
        "required_before_dual_write": [
            "synthetic fixture coverage for this surface",
            "no raw private/log content read",
            "canonical request/decision/receipt fields proven from safe metadata",
            "old JSON remains live decision source until switch-over lane",
        ],
    }


def _surface_summary(surface: dict[str, Any], *, reason: str) -> dict[str, Any]:
    return {
        "surface_id": surface["surface_id"],
        "surface": surface["surface"],
        "file_path": surface["file_path"],
        "disposition": surface["disposition"],
        "reason": reason,
        "runtime_authority": False,
        "shadow_only": True,
    }


def _canonical_contract_summary(contract: dict[str, Any]) -> dict[str, Any]:
    return {
        "contract_id": contract["schema_version"],
        "canonical_state_store": contract["canonical_state_store"],
        "required_request_fields": list(CANONICAL_PAYLOAD_REQUIRED_FIELDS),
        "required_decision_fields": list(CANONICAL_DECISION_REQUIRED_FIELDS),
        "required_receipt_fields": list(CANONICAL_RECEIPT_REQUIRED_FIELDS),
        "forbidden_payload_keys": sorted(FORBIDDEN_PAYLOAD_KEYS),
        "contract_tables": [table["table_name"] for table in contract["contract_tables"]],
        "raw_command_text_allowed": False,
        "freeform_shell_approval_allowed": False,
        "legacy_json_still_active": True,
    }


def build_guardian_hitl_shadow_adapter(
    *,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Return a deterministic shadow/read-model adapter payload.

    This reads only Repo A static read-model builders. It does not read or write
    live approval JSON/JSONL files and it does not create approval requests.
    """
    disposition = build_guardian_hitl_surface_disposition(generated_at=generated_at)
    contract = build_guardian_hitl_sqlite_authority_contract(generated_at=generated_at)
    surfaces = disposition["surfaces"]

    shadow_records = [
        _shadow_record(surface, contract)
        for surface in surfaces
        if surface["disposition"] in MAPPED_DISPOSITIONS
        and surface["surface_id"] != "choice_pending_json_bridge"
    ]
    legacy_surfaces_mapped = [
        {
            "surface_id": record["source_surface_id"],
            "source_disposition": record["source_disposition"],
            "adapter_strategy": record["adapter_strategy"],
            "target_tables": record["canonical_target"]["target_tables"],
        }
        for record in shadow_records
    ]
    blocked_surfaces = [
        _surface_summary(surface, reason=surface["reason"])
        for surface in surfaces
        if surface["disposition"] == "block_no_go"
    ]
    unmapped_surfaces = [
        {
            **_surface_summary(
                surface,
                reason="Workflow choice state is not Guardian approval authority and stays outside this adapter.",
            ),
            "classification": CHOICE_PENDING_CLASSIFICATION,
            "guardian_approval_authority": False,
        }
        for surface in surfaces
        if surface["surface_id"] == "choice_pending_json_bridge"
    ]

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at or utc_now(),
        "runtime_authority_changed": False,
        "runtime_authority": False,
        "shadow_only": True,
        "dual_write_enabled": False,
        "caller_switched": False,
        "old_hitl_deleted": False,
        "old_hitl_classification": OLD_HITL_CLASSIFICATION,
        "choice_pending_classification": CHOICE_PENDING_CLASSIFICATION,
        "choice_pending_is_guardian_approval_authority": False,
        "repo_b_execution_allowed": False,
        "repo_b_code_imported": False,
        "live_legacy_store_read": False,
        "live_legacy_store_written": False,
        "live_legacy_store_deleted": False,
        "real_approval_request_created": False,
        "canonical_request_persisted": False,
        "raw_command_or_shell_allowed": False,
        "canonical_contract_summary": _canonical_contract_summary(contract),
        "shadow_records": shadow_records,
        "shadow_record_count": len(shadow_records),
        "legacy_surfaces_mapped": legacy_surfaces_mapped,
        "unmapped_surfaces": unmapped_surfaces,
        "blocked_surfaces": blocked_surfaces,
        "boundaries": {
            "read_model_only": True,
            "raw_content_read": False,
            "data_imported": False,
            "runtime_services_modified": False,
            "approval_paths_disabled": False,
            "telegram_send_added": False,
            "gmail_send_added": False,
            "email_send_added": False,
            "approval_bypass_allowed": False,
            "safe_to_import_cassandra_chief_memory": False,
            "safe_to_enable_remote_builder": False,
            "safe_to_expand_send_paths": False,
        },
        "required_before_dual_write": [
            "operator review of shadow mapping",
            "fixture coverage for Chief JSON, Cassandra HITL, Guardian transport, and Google broker mappings",
            "proof that shadow records do not mutate live JSON stores",
            "approval contract receipt fields proven without raw private/log content",
            "separate decision on workflow-choice substrate if needed",
        ],
        "next_safe_move": "Review the shadow mapping, then plan a bounded dual-write compatibility spec without switching callers.",
    }


def format_guardian_hitl_shadow_adapter(payload: dict[str, Any]) -> str:
    """Render a concise operator-facing Markdown read-model."""
    lines = [
        "# Guardian HITL SQLite Shadow Adapter v0",
        "",
        "## Bottom Line",
        "",
        "Legacy Guardian/HITL surfaces were mapped into the canonical SQLite contract shape for visibility only. No runtime behavior changed, no live JSON was read or written, no approval request was created, and callers were not switched.",
        "",
        "## What Was Mapped",
        "",
    ]
    for item in payload["legacy_surfaces_mapped"]:
        targets = ", ".join(item["target_tables"])
        lines.append(
            f"- `{item['surface_id']}` -> `{targets}` ({item['adapter_strategy']})"
        )

    lines.extend(["", "## Still Legacy Or Mixed", ""])
    for record in payload["shadow_records"]:
        if record["old_hitl_classification"] == OLD_HITL_CLASSIFICATION:
            lines.append(
                f"- `{record['source_surface_id']}` remains `{OLD_HITL_CLASSIFICATION}`."
            )

    lines.extend(["", "## Shadow Only", ""])
    lines.extend(
        [
            f"- Runtime authority changed: `{str(payload['runtime_authority_changed']).lower()}`",
            f"- Shadow only: `{str(payload['shadow_only']).lower()}`",
            f"- Dual-write enabled: `{str(payload['dual_write_enabled']).lower()}`",
            f"- Callers switched: `{str(payload['caller_switched']).lower()}`",
            f"- Old HITL deleted: `{str(payload['old_hitl_deleted']).lower()}`",
            f"- Real approval request created: `{str(payload['real_approval_request_created']).lower()}`",
        ]
    )

    lines.extend(["", "## Not Guardian Approval Authority", ""])
    for item in payload["unmapped_surfaces"]:
        lines.append(f"- `{item['surface_id']}`: `{item['classification']}`.")

    lines.extend(["", "## Blocked", ""])
    for item in payload["blocked_surfaces"]:
        lines.append(f"- `{item['surface_id']}`: {item['reason']}")

    lines.extend(["", "## Before Dual-Write", ""])
    for item in payload["required_before_dual_write"]:
        lines.append(f"- {item}")

    lines.extend(["", "## Next Safe Move", "", payload["next_safe_move"], ""])
    return "\n".join(lines)


def export_guardian_hitl_shadow_adapter(
    *,
    export_root: str | Path = DEFAULT_EXPORT_ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    export_path = _export_root_path(export_root)
    export_path.mkdir(parents=True, exist_ok=True)
    payload = build_guardian_hitl_shadow_adapter(generated_at=generated_at)
    operator_payload = format_guardian_hitl_shadow_adapter(payload)

    json_path = export_path / JSON_EXPORT_NAME
    operator_path = export_path / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(operator_payload, encoding="utf-8")

    return {
        "json_path": json_path.as_posix(),
        "operator_path": operator_path.as_posix(),
        "shadow_record_count": payload["shadow_record_count"],
        "runtime_authority_changed": payload["runtime_authority_changed"],
        "shadow_only": payload["shadow_only"],
        "dual_write_enabled": payload["dual_write_enabled"],
        "caller_switched": payload["caller_switched"],
        "old_hitl_deleted": payload["old_hitl_deleted"],
        "choice_pending_classification": payload["choice_pending_classification"],
    }


__all__ = [
    "CHOICE_PENDING_CLASSIFICATION",
    "JSON_EXPORT_NAME",
    "OLD_HITL_CLASSIFICATION",
    "OPERATOR_EXPORT_NAME",
    "SCHEMA_VERSION",
    "build_guardian_hitl_shadow_adapter",
    "export_guardian_hitl_shadow_adapter",
    "format_guardian_hitl_shadow_adapter",
    "stable_json",
]
