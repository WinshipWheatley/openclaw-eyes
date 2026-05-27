"""Request-response bridge readiness v0.

Read-only readiness view for the Mission Control bridge. This does not start a
service, process requests, or publish responses; it only summarizes the bounded
bridge contract from safe local read-models/templates.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping


DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_GENERATED_AT = "2026-05-26T00:00:00+00:00"

SCHEMA_VERSION = "request_response_bridge_readiness_v0"
READ_MODEL_ID = "request_response_bridge_readiness"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
OPERATOR_EXPORT_NAME = f"{READ_MODEL_ID}_OPERATOR.md"
CONTRACT_STATUS = "REQUEST_RESPONSE_BRIDGE_VISIBLE_NO_SERVICE_ACTION"

STATUS_READ_MODEL_PATH = Path("generated/read_models/openclaw_request_response_service_status.json")
SERVICE_TEMPLATE_PATH = Path("systemd/user/openclaw-request-response.service.in")

AUTHORITY_BOUNDARY = {
    "service_start_allowed": False,
    "request_processing_allowed_by_this_readmodel": False,
    "live_lm_call_allowed": False,
    "model_api_integration_allowed": False,
    "network_allowed": False,
    "tool_execution_allowed": False,
    "external_action_allowed": False,
    "workflow_execution_allowed": False,
    "production_state_mutation_allowed": False,
    "workbook_body_read_allowed": False,
    "spreadsheet_cell_read_allowed": False,
}


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _content_hash(payload: dict[str, Any]) -> str:
    clone = json.loads(stable_json(payload))
    clone.get("machine_proof", {}).pop("content_hash", None)
    return "sha256:" + hashlib.sha256(stable_json(clone).encode("utf-8")).hexdigest()


def _load_status(path: Path = STATUS_READ_MODEL_PATH) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def build_payload(*, generated_at: str | None = None, status_path: Path = STATUS_READ_MODEL_PATH) -> dict[str, Any]:
    generated_at = generated_at or DEFAULT_GENERATED_AT
    status = _load_status(status_path)
    manual_help = status.get("manual_run_help") if isinstance(status.get("manual_run_help"), Mapping) else {}
    response_policy = status.get("response_output_policy") if isinstance(status.get("response_output_policy"), Mapping) else {}
    proof = status.get("machine_proof") if isinstance(status.get("machine_proof"), Mapping) else {}
    service_template_present = SERVICE_TEMPLATE_PATH.exists()
    approved_inbox_ref = str(manual_help.get("approved_inbox") or "/mnt/e/openclaw/mission_control_capture_requests/inbox")
    response_dir_ref = str(manual_help.get("response_dir") or "/mnt/e/openclaw/mission_control_responses/to_mac")
    scoped_contract = str(response_policy.get("per_request_filename") or "openclaw_response_for_mac_<source_request_id>.json")
    bridge_ready_for_live_review = bool(
        status
        and service_template_present
        and proof.get("approved_inbox_only") is True
        and proof.get("per_request_response_written") is True
        and proof.get("terminal_response_written") is True
    )
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "contract_status": CONTRACT_STATUS,
        "generated_at": generated_at,
        "readiness_status": "READY_FOR_LIVE_REVIEW" if bridge_ready_for_live_review else "SEEDED_NEEDS_OPERATOR_SERVICE_CHECK",
        "operator_summary": (
            "The Mission Control bridge has a bounded request-response contract.",
            "It watches the approved OpenClaw inbox and writes scoped responses for the same request.",
            "This read-model does not start the service or process requests.",
        ),
        "bridge_contract": {
            "status_read_model_ref": status_path.as_posix(),
            "service_template_ref": SERVICE_TEMPLATE_PATH.as_posix(),
            "service_template_present": service_template_present,
            "approved_inbox_ref": approved_inbox_ref,
            "response_output_ref": response_dir_ref,
            "scoped_response_filename_contract": scoped_contract,
            "latest_response_supported": bool(response_policy.get("latest_filename") or "openclaw_response_for_mac_latest.json"),
            "route_aware_heartbeat_supported": proof.get("route_aware_processing_heartbeat_written") is True,
            "dashboard_visible": True,
            "ready_for_live_review": bridge_ready_for_live_review,
        },
        "safe_delivery_policy": {
            "approved_inbox_only": proof.get("approved_inbox_only") is True,
            "scoped_response_required": True,
            "arbitrary_destination_allowed": False,
            "telegram_email_push_routing_allowed": False,
            "lm_inferred_routing_allowed": False,
        },
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "machine_proof": {
            "status_read_model_present": bool(status),
            "service_template_present": service_template_present,
            "approved_inbox_only": proof.get("approved_inbox_only") is True,
            "per_request_response_written": proof.get("per_request_response_written") is True,
            "terminal_response_written": proof.get("terminal_response_written") is True,
            "route_aware_processing_heartbeat_written": proof.get("route_aware_processing_heartbeat_written") is True,
            "model_call_performed": proof.get("model_call_performed") is True,
            "tool_execution_performed": proof.get("tool_execution_performed") is True,
            "workflow_execution_performed": proof.get("workflow_execution_performed") is True,
            "external_action_performed": proof.get("external_action_performed") is True,
            "service_started_by_this_readmodel": False,
            "request_processed_by_this_readmodel": False,
            "ready_for_live_review": bridge_ready_for_live_review,
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
    contract = payload["bridge_contract"]
    lines = [
        "# Request-Response Bridge Readiness",
        "",
        f"Status: {payload['readiness_status']}",
        f"Inbox: {contract['approved_inbox_ref']}",
        f"Responses: {contract['response_output_ref']}",
        f"Scoped response: {contract['scoped_response_filename_contract']}",
        "",
        "This is visibility only. It does not start the service, process requests, or enable external actions.",
    ]
    operator_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return json_path, operator_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export request-response bridge readiness read-model.")
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
                    "readiness_status": payload["readiness_status"],
                    "service_template_present": payload["bridge_contract"]["service_template_present"],
                    "ready_for_live_review": payload["bridge_contract"]["ready_for_live_review"],
                    "all_live_authority_false": payload["machine_proof"]["all_live_authority_false"],
                }
            ),
            end="",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
