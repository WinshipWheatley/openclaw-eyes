"""LM1 thread-context package v0.

Standalone export for the non-live package a future LM1 intent proposer would
receive. The package is built from existing universal-intake, token/privacy, and
model-router contracts. It never calls a model and carries no tool authority.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

import lm_readiness_dashboard


DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_GENERATED_AT = "2026-05-26T00:00:00+00:00"

SCHEMA_VERSION = "lm1_thread_context_package_v0"
READ_MODEL_ID = "lm1_thread_context_package"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
OPERATOR_EXPORT_NAME = f"{READ_MODEL_ID}_OPERATOR.md"
CONTRACT_STATUS = "LM1_THREAD_CONTEXT_PACKAGE_READY_NO_LIVE_MODEL"

AUTHORITY_BOUNDARY = {
    "live_lm_call_allowed": False,
    "model_api_integration_allowed": False,
    "network_allowed": False,
    "tool_execution_allowed": False,
    "external_action_allowed": False,
    "send_submit_allowed": False,
    "workflow_execution_allowed": False,
    "production_state_mutation_allowed": False,
    "raw_values_included_allowed": False,
    "workbook_body_read_allowed": False,
    "spreadsheet_cell_read_allowed": False,
}


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _content_hash(payload: dict[str, Any]) -> str:
    clone = json.loads(stable_json(payload))
    clone.get("machine_proof", {}).pop("content_hash", None)
    return "sha256:" + hashlib.sha256(stable_json(clone).encode("utf-8")).hexdigest()


def build_lm1_package(*, source_request_id: str = "lm1_thread_context_package_fixture") -> dict[str, Any]:
    return lm_readiness_dashboard.build_lm1_thread_context_package(source_request_id=source_request_id)


def build_payload(*, generated_at: str | None = None, source_request_id: str = "lm1_thread_context_package_fixture") -> dict[str, Any]:
    generated_at = generated_at or DEFAULT_GENERATED_AT
    package = build_lm1_package(source_request_id=source_request_id)
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "contract_status": CONTRACT_STATUS,
        "generated_at": generated_at,
        "operator_summary": (
            "OpenClaw can build the future LM1 input package without calling a model.",
            "The package includes intake and privacy context, but no tools or authority.",
            "Raw workbook contents and private values are excluded.",
        ),
        "lm1_thread_context_package": package,
        "package_summary": {
            "package_id": package["package_id"],
            "source_request_id": package["source_request_id"],
            "world_ref": package["current_world_ref"],
            "client_ref": package["universal_intake_inference"]["client_ref"],
            "workflow_ref": package["universal_intake_inference"]["workflow_ref"],
            "privacy_classification": package["privacy_classification"],
            "tokenization_required": package["tokenization_required"],
            "raw_values_included": package["raw_values_included"],
            "selected_model_class": package["model_router_result"]["selected_model_class"],
            "selected_provider_ref": package["model_router_result"].get("selected_provider_ref"),
            "output_schema_ref": "MachineIntentCandidate",
            "ready_for_shadow": True,
        },
        "chain_contract": {
            "input_from": ("Gate 1 privacy/request readiness", "Universal intake", "Tokenization policy", "Model router"),
            "output_to": "Gate 2 intent ingest",
            "future_lm1_may_propose": "MachineIntentCandidate JSON only",
            "gate2_must_validate_before_ingest": True,
            "live_lm_enabled": False,
        },
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "machine_proof": {
            "package_built": True,
            "package_consumes_universal_intake": bool(package.get("universal_intake_inference")),
            "package_consumes_token_policy": bool(package.get("tokenization_policy")),
            "package_has_model_router_result": bool(package.get("model_router_result")),
            "raw_values_included": package["raw_values_included"],
            "tools_allowed_empty": package["tools_allowed"] == (),
            "authority_granted_any": any(package["authority_granted"].values()),
            "ready_for_shadow": True,
            "live_model_call_performed": False,
            "workbook_body_read_performed": False,
            "spreadsheet_cell_read_performed": False,
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
    summary = payload["package_summary"]
    lines = [
        "# LM1 Thread Context Package",
        "",
        f"Status: {CONTRACT_STATUS}",
        f"Package: {summary['package_id']}",
        f"World: {summary['world_ref']}",
        f"Client: {summary['client_ref']}",
        f"Workflow: {summary['workflow_ref']}",
        f"Privacy: {summary['privacy_classification']}",
        f"Selected model class: {summary['selected_model_class']}",
        "",
        "This is a shadow package only. Live models, tools, file reads, and external actions remain off.",
    ]
    operator_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return json_path, operator_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export LM1 thread-context package read-model.")
    parser.add_argument("--export-root", type=Path, default=DEFAULT_EXPORT_ROOT)
    parser.add_argument("--generated-at", default=DEFAULT_GENERATED_AT)
    parser.add_argument("--source-request-id", default="lm1_thread_context_package_fixture")
    parser.add_argument("--format", choices=("summary", "json"), default="summary")
    args = parser.parse_args(argv)

    payload = build_payload(generated_at=args.generated_at, source_request_id=args.source_request_id)
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
                    "selected_model_class": payload["package_summary"]["selected_model_class"],
                    "raw_values_included": payload["package_summary"]["raw_values_included"],
                    "ready_for_shadow": payload["package_summary"]["ready_for_shadow"],
                    "all_live_authority_false": payload["machine_proof"]["all_live_authority_false"],
                }
            ),
            end="",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
