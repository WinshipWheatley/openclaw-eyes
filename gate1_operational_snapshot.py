"""Gate 1 operational request snapshot v0.

This is the concrete pre-LM1 object for a Mission Control-shaped request. It
combines request metadata, universal intake inference, privacy classification,
tokenization policy, and private-mode effects without calling a model, reading
file bodies, or granting authority.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping

import gate1_privacy_request_readiness
import private_mode_policy_readiness
import token_vault
import universal_intake_contract


DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_GENERATED_AT = "2026-05-26T00:00:00+00:00"

SCHEMA_VERSION = "gate1_operational_snapshot_v0"
READ_MODEL_ID = "gate1_operational_snapshot"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
OPERATOR_EXPORT_NAME = f"{READ_MODEL_ID}_OPERATOR.md"
CONTRACT_STATUS = "GATE1_OPERATIONAL_SNAPSHOT_READY_NO_LIVE_LM"

AUTHORITY_BOUNDARY = {
    "live_lm_call_allowed": False,
    "model_api_integration_allowed": False,
    "network_allowed": False,
    "tool_execution_allowed": False,
    "external_action_allowed": False,
    "workflow_execution_allowed": False,
    "production_state_mutation_allowed": False,
    "file_body_read_allowed": False,
    "workbook_body_read_allowed": False,
    "spreadsheet_cell_read_allowed": False,
    "ocr_allowed": False,
    "raw_value_exposure_allowed": False,
    "credential_handling_allowed": False,
}


@dataclass(frozen=True)
class Gate1OperationalSnapshot:
    snapshot_id: str
    source_request_id: str
    source_device_ref: str
    thread_ref: str
    world_ref: str
    workflow_ref: str
    client_ref: str
    user_message: str
    artifact_metadata: dict[str, Any]
    universal_intake_inference: dict[str, Any]
    privacy_class: str
    tokenization_required: bool
    tokenization_policy: dict[str, Any]
    private_mode_effect: dict[str, Any]
    strict_private_mode_effect: dict[str, Any]
    allowed_context_classes: tuple[str, ...]
    forbidden_context_classes: tuple[str, ...]
    safe_to_package_for_lm1: bool
    unsafe_reason: str
    raw_values_included: bool
    authority_boundary: dict[str, bool]
    next_safe_move: str


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _short_hash(*parts: object) -> str:
    return hashlib.sha256("\0".join(str(part) for part in parts).encode("utf-8")).hexdigest()[:16]


def _content_hash(payload: dict[str, Any]) -> str:
    clone = json.loads(stable_json(payload))
    clone.get("machine_proof", {}).pop("content_hash", None)
    return "sha256:" + hashlib.sha256(stable_json(clone).encode("utf-8")).hexdigest()


def _safe_artifact_metadata(context: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "file_display_name": str(context.get("file_display_name") or ""),
        "file_extension": str(context.get("file_extension") or ""),
        "file_type": str(context.get("file_type") or ""),
        "artifact_kind": str(context.get("artifact_kind") or ""),
        "body_read": False,
        "workbook_body_read": False,
        "spreadsheet_cell_read": False,
        "ocr_performed": False,
        "external_shared": False,
    }


def _private_mode_effects(context: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    policy = private_mode_policy_readiness.build_payload()
    private_active = bool(context.get("private_mode_active", False))
    strict_active = bool(context.get("strict_private_mode_active", False))
    private_effect = {
        "available": bool(policy["private_mode_available"]),
        "active": private_active,
        "raw_values_included": False,
        "model_may_see_raw_values": False,
        "tokenization_required_when_active": True,
        "operator_copy": "Private Mode would keep raw details local and use tokenized or summarized context.",
    }
    strict_effect = {
        "available": bool(policy["strict_private_mode_available"]),
        "active": strict_active,
        "raw_values_included": False,
        "model_may_see_raw_values": False,
        "local_only_required_when_active": True,
        "operator_copy": "Strict Private Mode would require local-only handling for sensitive packages.",
    }
    return private_effect, strict_effect


def build_gate1_operational_snapshot(context: Mapping[str, Any] | None = None) -> dict[str, Any]:
    context = dict(context or {})
    source_request_id = str(context.get("source_request_id") or "gate1_operational_snapshot_fixture")
    user_message = str(
        context.get("user_message")
        or context.get("operator_message")
        or "these are the invoice workbooks for the clients named in the files, handle them how you're supposed to"
    )
    file_display_name = str(context.get("file_display_name") or "Invoice Capitol Hilton Running.xlsx")
    file_extension = str(context.get("file_extension") or Path(file_display_name).suffix or ".xlsx")
    file_type = str(context.get("file_type") or "spreadsheet")
    world_ref = str(context.get("world_ref") or context.get("current_world_ref") or "finance")
    source_device_ref = str(context.get("source_device_ref") or "mission_control_mac")
    thread_ref = str(context.get("thread_ref") or "thread_ref:finance_capital_hilton")

    intake = universal_intake_contract.infer_universal_intake(
        {
            "intake_id": str(context.get("intake_id") or "gate1_operational_snapshot_intake"),
            "source_request_id": source_request_id,
            "file_display_name": file_display_name,
            "file_extension": file_extension,
            "file_type": file_type,
            "user_note": user_message,
            "current_world_ref": world_ref,
        }
    )
    privacy_trigger = gate1_privacy_request_readiness.classify_gate1_privacy_request(
        {
            "input_class": str(intake.get("privacy_class") or "normal"),
            "world_ref": str(intake.get("world_ref") or world_ref),
            "file_type": file_type,
            "file_extension": file_extension,
            "user_note": user_message,
        }
    )
    private_effect, strict_effect = _private_mode_effects(context)
    token_policy = token_vault.evaluate_tokenization_policy(
        {
            "world_ref": intake.get("world_ref") or world_ref,
            "client_ref": intake.get("client_ref") or context.get("client_ref") or "unknown",
            "artifact_kind": intake.get("artifact_kind") or context.get("artifact_kind") or "",
            "file_type": file_type,
            "private_mode_active": private_effect["active"],
            "strict_private_mode_active": strict_effect["active"],
        }
    )
    tokenization_policy_available = bool(context.get("tokenization_policy_available", True))
    privacy_policy_available = bool(context.get("privacy_policy_available", True))
    safe_to_package = bool(intake.get("lm1_chain_ready")) and privacy_policy_available
    unsafe_reason = ""
    if token_policy["tokenization_required"] and not tokenization_policy_available:
        safe_to_package = False
        unsafe_reason = "TOKENIZATION_POLICY_REQUIRED"
    elif not privacy_policy_available:
        safe_to_package = False
        unsafe_reason = "PRIVACY_POLICY_REQUIRED"
    elif not bool(intake.get("lm1_chain_ready")):
        unsafe_reason = str((intake.get("chain_contract") or {}).get("blocking_reason") or "INTAKE_CLARIFICATION_REQUIRED")

    allowed_context_classes = tuple(
        dict.fromkeys(
            tuple(privacy_trigger["allowed_context_classes"])
            + ("universal_intake_summary", "privacy_trigger_result", "tokenization_policy_result")
        )
    )
    forbidden_context_classes = tuple(
        dict.fromkeys(
            tuple(privacy_trigger["forbidden_context_classes"])
            + ("full workbook", "full sheet dump", "external private data")
        )
    )
    snapshot = Gate1OperationalSnapshot(
        snapshot_id=f"gate1_operational_snapshot:{_short_hash(source_request_id, file_display_name, user_message)}",
        source_request_id=source_request_id,
        source_device_ref=source_device_ref,
        thread_ref=thread_ref,
        world_ref=str(intake.get("world_ref") or world_ref or "unknown"),
        workflow_ref=str(intake.get("workflow_ref") or context.get("workflow_ref") or "unknown"),
        client_ref=str(intake.get("client_ref") or context.get("client_ref") or "unknown"),
        user_message=user_message,
        artifact_metadata=_safe_artifact_metadata(
            {
                **context,
                "file_display_name": file_display_name,
                "file_extension": file_extension,
                "file_type": file_type,
                "artifact_kind": intake.get("artifact_kind") or context.get("artifact_kind") or "",
            }
        ),
        universal_intake_inference=intake,
        privacy_class=str(privacy_trigger["privacy_class"]),
        tokenization_required=bool(token_policy["tokenization_required"]),
        tokenization_policy=token_policy,
        private_mode_effect=private_effect,
        strict_private_mode_effect=strict_effect,
        allowed_context_classes=allowed_context_classes,
        forbidden_context_classes=forbidden_context_classes,
        safe_to_package_for_lm1=safe_to_package,
        unsafe_reason=unsafe_reason,
        raw_values_included=False,
        authority_boundary=dict(AUTHORITY_BOUNDARY),
        next_safe_move=(
            "Build the LM1 shadow package from this snapshot; no model call or action is allowed."
            if safe_to_package
            else "Ask one clarification or attach the missing privacy/token policy before LM1 packaging."
        ),
    )
    return asdict(snapshot)


def gate1_operational_snapshot_fixtures() -> dict[str, dict[str, Any]]:
    return {
        "capital_hilton_next_step": build_gate1_operational_snapshot(
            {
                "source_request_id": "gate1_capital_hilton_next_step_fixture",
                "user_message": "what's next for the Capital Hilton invoice?",
                "file_display_name": "Invoice Capitol Hilton Running.xlsx",
                "file_extension": ".xlsx",
                "file_type": "spreadsheet",
                "world_ref": "finance",
            }
        ),
        "privacy_policy_missing": build_gate1_operational_snapshot(
            {
                "source_request_id": "gate1_privacy_policy_missing_fixture",
                "user_message": "handle this private client finance workbook",
                "file_display_name": "Invoice Capitol Hilton Running.xlsx",
                "file_extension": ".xlsx",
                "file_type": "spreadsheet",
                "world_ref": "finance",
                "tokenization_policy_available": False,
            }
        ),
    }


def build_payload(*, generated_at: str | None = None) -> dict[str, Any]:
    generated_at = generated_at or DEFAULT_GENERATED_AT
    fixtures = gate1_operational_snapshot_fixtures()
    capital = fixtures["capital_hilton_next_step"]
    blocked = fixtures["privacy_policy_missing"]
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "contract_status": CONTRACT_STATUS,
        "generated_at": generated_at,
        "operator_summary": (
            "OpenClaw can build a clean pre-model snapshot from request metadata.",
            "Client finance requests require tokenized or summarized context before LM1.",
            "Raw workbook bodies, cells, credentials, and unrelated client details stay out.",
        ),
        "snapshots": fixtures,
        "chain_contract": {
            "output_to": "lm1_thread_context_package",
            "safe_snapshot_can_feed_lm1_package": capital["safe_to_package_for_lm1"],
            "unsafe_snapshot_blocks_lm1_package": blocked["safe_to_package_for_lm1"] is False,
            "lm1_output_schema_required": "MachineIntentCandidate",
            "live_lm_enabled": False,
        },
        "read_model_refs": {
            "gate1_privacy_request_readiness": "generated/read_models/gate1_privacy_request_readiness.json",
            "lm1_thread_context_package": "generated/read_models/lm1_thread_context_package.json",
            "universal_intake_contract": "generated/read_models/universal_intake_contract.json",
            "token_vault_status": "generated/read_models/token_vault_status.json",
        },
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "machine_proof": {
            "snapshot_contract_present": True,
            "capital_hilton_snapshot_safe_for_lm1": capital["safe_to_package_for_lm1"],
            "client_finance_classified": capital["privacy_class"] == "CLIENT_FINANCE_FILE_METADATA",
            "tokenization_required": capital["tokenization_required"],
            "raw_values_included": capital["raw_values_included"],
            "privacy_policy_missing_blocks_lm1": blocked["safe_to_package_for_lm1"] is False,
            "privacy_policy_missing_reason": blocked["unsafe_reason"],
            "universal_intake_inference_attached": bool(capital["universal_intake_inference"]),
            "workbook_body_read_performed": False,
            "spreadsheet_cell_read_performed": False,
            "model_call_performed": False,
            "tool_execution_performed": False,
            "external_action_performed": False,
            "all_live_authority_false": all(value is False for value in AUTHORITY_BOUNDARY.values()),
            "content_hash": "",
        },
    }
    payload["machine_proof"]["content_hash"] = _content_hash(payload)
    return payload


def write_exports(payload: Mapping[str, Any], export_root: Path = DEFAULT_EXPORT_ROOT) -> tuple[Path, Path]:
    export_root.mkdir(parents=True, exist_ok=True)
    json_path = export_root / JSON_EXPORT_NAME
    operator_path = export_root / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    capital = payload["snapshots"]["capital_hilton_next_step"]
    blocked = payload["snapshots"]["privacy_policy_missing"]
    lines = [
        "# Gate 1 Operational Snapshot",
        "",
        f"Status: {CONTRACT_STATUS}",
        "",
        "What this proves:",
        *[f"- {line}" for line in payload["operator_summary"]],
        "",
        f"Capital Hilton safe for LM1 package: {str(capital['safe_to_package_for_lm1']).lower()}",
        f"Privacy-missing fixture blocks LM1 package: {str(not blocked['safe_to_package_for_lm1']).lower()}",
        "",
        "Boundary: no live model, no workbook read, no cell read, no tools, no external action.",
    ]
    operator_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return json_path, operator_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export Gate 1 operational snapshot read-model.")
    parser.add_argument("--export-root", type=Path, default=DEFAULT_EXPORT_ROOT)
    parser.add_argument("--generated-at", default=DEFAULT_GENERATED_AT)
    parser.add_argument("--format", choices=("summary", "json"), default="summary")
    args = parser.parse_args(argv)

    payload = build_payload(generated_at=args.generated_at)
    json_path, operator_path = write_exports(payload, args.export_root)
    if args.format == "json":
        print(stable_json(payload), end="")
    else:
        print(
            stable_json(
                {
                    "read_model_id": READ_MODEL_ID,
                    "json_path": json_path.as_posix(),
                    "operator_path": operator_path.as_posix(),
                    "capital_hilton_snapshot_safe_for_lm1": payload["machine_proof"][
                        "capital_hilton_snapshot_safe_for_lm1"
                    ],
                    "privacy_policy_missing_blocks_lm1": payload["machine_proof"]["privacy_policy_missing_blocks_lm1"],
                    "all_live_authority_false": payload["machine_proof"]["all_live_authority_false"],
                }
            ),
            end="",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
