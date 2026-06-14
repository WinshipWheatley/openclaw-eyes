"""Gate 1 privacy/request readiness v0.

Standalone read-model for the ingress privacy trigger that sits before future
LM1 packaging. This module classifies synthetic/request metadata only. It does
not call models, read file bodies, or grant authority.
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

SCHEMA_VERSION = "gate1_privacy_request_readiness_v0"
READ_MODEL_ID = "gate1_privacy_request_readiness"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
OPERATOR_EXPORT_NAME = f"{READ_MODEL_ID}_OPERATOR.md"
CONTRACT_STATUS = "GATE1_PRIVACY_TRIGGER_READY_NO_LIVE_LM"

AUTHORITY_BOUNDARY = {
    "live_lm_call_allowed": False,
    "model_api_integration_allowed": False,
    "network_allowed": False,
    "file_body_read_allowed": False,
    "workbook_body_read_allowed": False,
    "spreadsheet_cell_read_allowed": False,
    "ocr_allowed": False,
    "tool_execution_allowed": False,
    "external_action_allowed": False,
    "production_state_mutation_allowed": False,
}


@dataclass(frozen=True)
class Gate1PrivacyTriggerResult:
    trigger_id: str
    input_class: str
    world_ref: str
    privacy_class: str
    tokenization_required: bool
    private_mode_recommended: bool
    strict_local_only_required: bool
    lm1_raw_values_allowed: bool
    allowed_context_classes: tuple[str, ...]
    forbidden_context_classes: tuple[str, ...]
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


def classify_gate1_privacy_request(context: str | Mapping[str, Any]) -> dict[str, Any]:
    if isinstance(context, str):
        input_class = context.strip().lower().replace(" ", "_") or "normal"
        world_ref = "unknown"
        file_type = ""
        user_note = ""
    else:
        input_class = str(context.get("input_class") or context.get("request_class") or "normal").strip().lower().replace(" ", "_")
        world_ref = str(context.get("world_ref") or "").strip().lower()
        file_type = str(context.get("file_type") or context.get("file_extension") or "").strip().lower()
        user_note = str(context.get("user_note") or context.get("operator_text") or "").strip().lower()

    combined = " ".join((input_class, world_ref, file_type, user_note))
    if any(term in combined for term in ("strict", "strict_private", "strict_local_only")):
        privacy_class = "STRICT_PRIVATE_CLIENT_METADATA"
        tokenization_required = True
        private_mode_recommended = True
        strict_local_only_required = True
        operator_copy = "This looks private enough to keep local-only."
    elif any(term in combined for term in ("legal", "confidential", "protected")):
        privacy_class = "CONFIDENTIAL_CLIENT_METADATA"
        tokenization_required = True
        private_mode_recommended = True
        strict_local_only_required = True
        operator_copy = "This looks confidential, so OpenClaw should keep raw details out of model-shaped packages."
    elif any(term in combined for term in ("personal", "private")):
        privacy_class = "PERSONAL_PRIVATE_METADATA"
        tokenization_required = True
        private_mode_recommended = True
        strict_local_only_required = True
        operator_copy = "This may include personal details, so OpenClaw should use private handling."
    elif world_ref == "finance" or any(term in combined for term in ("client_finance", "invoice", "workbook", "spreadsheet", "xlsx", "xls")):
        privacy_class = "CLIENT_FINANCE_FILE_METADATA"
        tokenization_required = True
        private_mode_recommended = True
        strict_local_only_required = False
        operator_copy = "This looks like client finance metadata, so OpenClaw should keep raw workbook details out of model-shaped packages."
    else:
        privacy_class = "LOW_METADATA"
        tokenization_required = False
        private_mode_recommended = False
        strict_local_only_required = False
        operator_copy = "This looks like low-risk metadata. OpenClaw still keeps raw values out by default."

    allowed_context = ("source_request_id", "device_ref", "thread_ref", "world_ref", "metadata_summary", "tokenized_refs")
    forbidden_context = ("raw workbook body", "spreadsheet cells", "credentials", "raw private bodies", "unrelated client data")
    result = Gate1PrivacyTriggerResult(
        trigger_id=f"gate1_privacy_trigger:{_short_hash(input_class, world_ref, privacy_class)}",
        input_class=input_class or "normal",
        world_ref=world_ref or "unknown",
        privacy_class=privacy_class,
        tokenization_required=tokenization_required,
        private_mode_recommended=private_mode_recommended,
        strict_local_only_required=strict_local_only_required,
        lm1_raw_values_allowed=False,
        allowed_context_classes=allowed_context,
        forbidden_context_classes=forbidden_context,
        operator_copy=operator_copy,
        next_safe_move=(
            "Attach token/privacy declarations before LM1 packaging."
            if tokenization_required
            else "Allow metadata-only LM1 packaging; raw values still stay out by default."
        ),
    )
    return asdict(result)


def gate1_privacy_trigger_fixtures() -> tuple[dict[str, Any], ...]:
    return tuple(
        classify_gate1_privacy_request(item)
        for item in ("normal", "client_finance", "legal_confidential", "personal_private", "strict_local_only")
    )


def build_payload(*, generated_at: str | None = None) -> dict[str, Any]:
    generated_at = generated_at or DEFAULT_GENERATED_AT
    fixtures = gate1_privacy_trigger_fixtures()
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "contract_status": CONTRACT_STATUS,
        "generated_at": generated_at,
        "operator_summary": (
            "OpenClaw can classify privacy posture before a future LM1 package is built.",
            "Finance and private items require tokenized or summarized context.",
            "Raw file bodies, workbook cells, credentials, and unrelated client details stay out.",
        ),
        "privacy_trigger_fixtures": fixtures,
        "chain_contract": {
            "gate_1_output_can_feed_lm1_package": True,
            "lm1_may_receive_raw_values": False,
            "tokenization_declaration_required_for_private_or_finance": True,
            "private_mode_can_raise_local_only_requirement": True,
            "live_lm_enabled": False,
        },
        "read_model_refs": {
            "lm1_thread_context_package": "generated/read_models/lm1_thread_context_package.json",
            "token_vault_status": "generated/read_models/token_vault_status.json",
            "lm_readiness_dashboard": "generated/read_models/lm_readiness_dashboard.json",
        },
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "machine_proof": {
            "fixture_count": len(fixtures),
            "normal_classified_low_metadata": fixtures[0]["privacy_class"] == "LOW_METADATA",
            "finance_requires_tokenization": any(
                item["privacy_class"] == "CLIENT_FINANCE_FILE_METADATA" and item["tokenization_required"] for item in fixtures
            ),
            "strict_local_only_fixture_exists": any(item["strict_local_only_required"] for item in fixtures),
            "lm1_raw_values_allowed_any_fixture": any(item["lm1_raw_values_allowed"] for item in fixtures),
            "live_model_call_performed": False,
            "file_body_read_performed": False,
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
    lines = [
        "# Gate 1 Privacy Request Readiness",
        "",
        f"Status: {CONTRACT_STATUS}",
        "",
        "What this proves:",
        *[f"- {line}" for line in payload["operator_summary"]],
        "",
        "Fixtures:",
        *[
            f"- {item['input_class']}: {item['privacy_class']} ({item['next_safe_move']})"
            for item in payload["privacy_trigger_fixtures"]
        ],
        "",
        "Live models, tools, file reads, and external actions remain off.",
    ]
    operator_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return json_path, operator_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export Gate 1 privacy request readiness read-model.")
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
                    "fixture_count": payload["machine_proof"]["fixture_count"],
                    "finance_requires_tokenization": payload["machine_proof"]["finance_requires_tokenization"],
                    "all_live_authority_false": payload["machine_proof"]["all_live_authority_false"],
                }
            ),
            end="",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
