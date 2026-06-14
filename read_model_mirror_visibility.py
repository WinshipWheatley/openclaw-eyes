"""Read-model mirror visibility v0.

Read-only proof that readiness payloads exist and name their intended local
surface. This does not create a sync system, write to Mac, or publish responses.
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

SCHEMA_VERSION = "read_model_mirror_visibility_v0"
READ_MODEL_ID = "read_model_mirror_visibility"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
OPERATOR_EXPORT_NAME = f"{READ_MODEL_ID}_OPERATOR.md"
CONTRACT_STATUS = "READ_MODEL_VISIBILITY_PROOF_ONLY_NO_SYNC"

AUTHORITY_BOUNDARY = {
    "mac_sync_allowed": False,
    "response_publication_allowed_by_this_contract": False,
    "new_transport_allowed": False,
    "network_allowed": False,
    "tool_execution_allowed": False,
    "external_action_allowed": False,
    "production_state_mutation_allowed": False,
}


@dataclass(frozen=True)
class ReadModelVisibilityRecord:
    record_id: str
    read_model_ref: str
    exists: bool
    intended_surface: str
    operator_copy_available: bool
    mac_visible_guaranteed: bool
    next_safe_move: str


READINESS_REFS = (
    "generated/read_models/floor_gap_reconciliation.json",
    "generated/read_models/lm_readiness_dashboard.json",
    "generated/read_models/operator_readiness_surface.json",
    "generated/read_models/gate1_privacy_request_readiness.json",
    "generated/read_models/lm1_thread_context_package.json",
    "generated/read_models/request_response_bridge_readiness.json",
    "generated/read_models/live_lm_activation_requirements.json",
    "generated/read_models/private_mode_policy_readiness.json",
    "generated/read_models/read_model_mirror_visibility.json",
    "generated/read_models/provider_policy_registry.json",
    "generated/read_models/model_router_policy.json",
    "generated/read_models/token_vault_status.json",
    "generated/read_models/universal_intake_contract.json",
)


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _short_hash(*parts: object) -> str:
    return hashlib.sha256("\0".join(str(part) for part in parts).encode("utf-8")).hexdigest()[:16]


def _content_hash(payload: dict[str, Any]) -> str:
    clone = json.loads(stable_json(payload))
    clone.get("machine_proof", {}).pop("content_hash", None)
    return "sha256:" + hashlib.sha256(stable_json(clone).encode("utf-8")).hexdigest()


def build_visibility_records() -> tuple[dict[str, Any], ...]:
    records = []
    for ref in READINESS_REFS:
        path = Path(ref)
        operator_ref = path.with_name(path.stem + "_OPERATOR.md")
        records.append(
            asdict(
                ReadModelVisibilityRecord(
                    record_id=f"read_model_visibility:{_short_hash(ref)}",
                    read_model_ref=ref,
                    exists=path.exists(),
                    intended_surface="generated_read_model",
                    operator_copy_available=operator_ref.exists(),
                    mac_visible_guaranteed=False,
                    next_safe_move="Expose through existing response/read-model paths when a future UI lane asks for it; do not add a second sync system.",
                )
            )
        )
    return tuple(records)


def build_payload(*, generated_at: str | None = None) -> dict[str, Any]:
    generated_at = generated_at or DEFAULT_GENERATED_AT
    records = build_visibility_records()
    own_ref = f"generated/read_models/{JSON_EXPORT_NAME}"
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "contract_status": CONTRACT_STATUS,
        "generated_at": generated_at,
        "visibility_records": records,
        "operator_summary": (
            "Readiness payloads have local generated read-model refs.",
            "This does not guarantee Mac rendering by itself.",
            "OpenClaw should use the existing response bridge for chat-thread delivery.",
        ),
        "mirror_policy": {
            "canonical_writer": "pc_generated_read_models",
            "new_sync_system_allowed": False,
            "mac_visible_guaranteed_by_this_contract": False,
            "use_existing_scoped_response_bridge_for_chat": True,
        },
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "machine_proof": {
            "visibility_record_count": len(records),
            "all_known_readiness_refs_recorded": len(records) == len(READINESS_REFS),
            "generated_refs_present": all(item["exists"] for item in records if item["read_model_ref"] != own_ref),
            "operator_copies_available": all(item["operator_copy_available"] for item in records if item["read_model_ref"] != own_ref),
            "mac_visible_guaranteed": False,
            "new_sync_system_created": False,
            "response_publication_performed": False,
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
        "# Read-Model Mirror Visibility",
        "",
        f"Status: {CONTRACT_STATUS}",
        f"Readiness refs tracked: {payload['machine_proof']['visibility_record_count']}",
        f"Mac-visible guaranteed here: {str(payload['machine_proof']['mac_visible_guaranteed']).lower()}",
        "",
        "This is proof only. It does not add a sync system or publish responses.",
    ]
    operator_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return json_path, operator_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export read-model mirror visibility read-model.")
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
                    "visibility_record_count": payload["machine_proof"]["visibility_record_count"],
                    "mac_visible_guaranteed": payload["machine_proof"]["mac_visible_guaranteed"],
                    "all_live_authority_false": payload["machine_proof"]["all_live_authority_false"],
                }
            ),
            end="",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
