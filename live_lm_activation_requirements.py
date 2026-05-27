"""Live LM activation requirements v0.

Read-only blocker/receipt contract for future LM1/LM2 activation. It makes the
remaining live-model blockers explicit without enabling models, providers,
tools, or production actions.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping


DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_GENERATED_AT = "2026-05-26T00:00:00+00:00"

SCHEMA_VERSION = "live_lm_activation_requirements_v0"
READ_MODEL_ID = "live_lm_activation_requirements"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
OPERATOR_EXPORT_NAME = f"{READ_MODEL_ID}_OPERATOR.md"
CONTRACT_STATUS = "LIVE_LM_ACTIVATION_BLOCKED_REQUIREMENTS_MISSING"

AUTHORITY_BOUNDARY = {
    "live_lm_call_allowed": False,
    "model_api_integration_allowed": False,
    "provider_key_material_access_allowed": False,
    "network_allowed": False,
    "tool_execution_allowed": False,
    "agent_dispatch_allowed": False,
    "worker_dispatch_allowed": False,
    "workflow_execution_allowed": False,
    "external_action_allowed": False,
    "send_submit_allowed": False,
    "approval_execution_allowed": False,
    "ledger_posting_allowed": False,
    "production_state_mutation_allowed": False,
}


@dataclass(frozen=True)
class ActivationReceiptRequirement:
    receipt_id: str
    receipt_type: str
    human_label: str
    required_for_lanes: tuple[str, ...]
    present: bool
    blocks_live_lm1: bool
    blocks_live_lm2: bool
    blocks_provider_activation: bool
    operator_copy: str
    next_safe_move: str


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _short_hash(*parts: object) -> str:
    return hashlib.sha256("\0".join(str(part) for part in parts).encode("utf-8")).hexdigest()[:16]


def _content_hash(payload: dict[str, Any]) -> str:
    clone = json.loads(stable_json(payload))
    clone.get("machine_proof", {}).pop("content_hash", None)
    return "sha256:" + hashlib.sha256(stable_json(clone).encode("utf-8")).hexdigest()


def required_receipts() -> tuple[dict[str, Any], ...]:
    specs = (
        (
            "live_model_enablement_receipt",
            "Operator enablement",
            ("LM1", "LM2"),
            "OpenClaw needs an explicit operator enablement receipt before live models can turn on.",
        ),
        (
            "provider_policy_receipt",
            "Provider policy",
            ("LM1", "LM2"),
            "OpenClaw needs a recorded provider policy choice before any provider can be used.",
        ),
        (
            "model_selection_policy_receipt",
            "Model selection policy",
            ("LM1", "LM2"),
            "OpenClaw needs a model-selection receipt that matches the lane, privacy class, and risk.",
        ),
        (
            "privacy_policy_receipt",
            "Privacy policy",
            ("LM1", "LM2"),
            "OpenClaw needs the production privacy policy receipt before live model-shaped packages can leave shadow mode.",
        ),
        (
            "production_token_vault_ready_receipt",
            "Production token vault",
            ("LM1", "LM2"),
            "OpenClaw needs production token-vault readiness before sensitive live model packages are allowed.",
        ),
        (
            "shadow_comparison_live_run_receipt",
            "Live-shadow comparison",
            ("LM1", "LM2"),
            "OpenClaw needs successful real shadow comparison receipts beyond fixtures.",
        ),
        (
            "rollback_disable_receipt",
            "Rollback switch",
            ("LM1", "LM2"),
            "OpenClaw needs a rollback or disable receipt before any future live model lane can be reviewed.",
        ),
    )
    return tuple(
        asdict(
            ActivationReceiptRequirement(
                receipt_id=f"activation_receipt:{_short_hash(receipt_type)}",
                receipt_type=receipt_type,
                human_label=human_label,
                required_for_lanes=lanes,
                present=False,
                blocks_live_lm1="LM1" in lanes,
                blocks_live_lm2="LM2" in lanes,
                blocks_provider_activation=receipt_type in {"provider_policy_receipt", "model_selection_policy_receipt"},
                operator_copy=operator_copy,
                next_safe_move="Keep live models off; collect this receipt through a future governed review lane.",
            )
        )
        for receipt_type, human_label, lanes, operator_copy in specs
    )


def build_payload(*, generated_at: str | None = None) -> dict[str, Any]:
    generated_at = generated_at or DEFAULT_GENERATED_AT
    receipts = required_receipts()
    missing = tuple(item["receipt_type"] for item in receipts if item["present"] is False)
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "contract_status": CONTRACT_STATUS,
        "generated_at": generated_at,
        "operator_summary": (
            "Live models are still off.",
            "OpenClaw now has an explicit checklist for what must exist before live LM1 or LM2 can be reviewed.",
            "No provider, model, tool, or action is activated by this checklist.",
        ),
        "live_lm1_activation_status": "NOT_READY",
        "live_lm2_activation_status": "NOT_READY",
        "provider_activation_status": "RECEIPTS_REQUIRED_NOT_PRESENT",
        "activation_receipt_requirements": receipts,
        "missing_receipts": missing,
        "hard_blockers": (
            "production_token_vault_inactive",
            "provider_activation_receipts_missing",
            "live_model_enablement_receipt_missing",
            "production_privacy_policy_receipt_missing",
            "live_shadow_comparison_receipt_missing",
            "rollback_disable_receipt_missing",
        ),
        "next_safe_move": "Keep using fixture/shadow mode until these receipts exist.",
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "machine_proof": {
            "receipt_requirement_count": len(receipts),
            "missing_receipt_count": len(missing),
            "provider_activation_receipts_required": True,
            "provider_activation_receipts_present": False,
            "production_token_vault_ready_receipt_present": False,
            "live_model_enablement_receipt_present": False,
            "live_lm1_ready": False,
            "live_lm2_ready": False,
            "live_lm_status": "NOT_ACTIVE",
            "live_model_call_performed": False,
            "model_api_call_performed": False,
            "network_performed": False,
            "tool_execution_performed": False,
            "external_action_performed": False,
            "production_state_mutation_performed": False,
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
    lines = [
        "# Live LM Activation Requirements",
        "",
        f"Status: {CONTRACT_STATUS}",
        f"LM1 live: {payload['live_lm1_activation_status']}",
        f"LM2 live: {payload['live_lm2_activation_status']}",
        f"Missing receipts: {payload['machine_proof']['missing_receipt_count']}",
        "",
        "Still blocked:",
        *[f"- {item}" for item in payload["hard_blockers"]],
        "",
        "No live model, provider, tool, or action is enabled.",
    ]
    operator_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return json_path, operator_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export live LM activation requirements read-model.")
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
                    "missing_receipt_count": payload["machine_proof"]["missing_receipt_count"],
                    "live_lm_status": payload["machine_proof"]["live_lm_status"],
                    "all_live_authority_false": payload["machine_proof"]["all_live_authority_false"],
                }
            ),
            end="",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
