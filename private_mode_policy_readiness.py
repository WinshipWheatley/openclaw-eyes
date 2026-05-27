"""Private Mode policy readiness v0.

Backend-only readiness contract for future Mission Control Private Mode and
Strict Private Mode. It defines package effects without building UI, calling
models, or enabling live processing.
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

SCHEMA_VERSION = "private_mode_policy_readiness_v0"
READ_MODEL_ID = "private_mode_policy_readiness"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
OPERATOR_EXPORT_NAME = f"{READ_MODEL_ID}_OPERATOR.md"
CONTRACT_STATUS = "PRIVATE_MODE_POLICY_READY_INACTIVE"

AUTHORITY_BOUNDARY = {
    "private_mode_activation_by_this_contract_allowed": False,
    "live_lm_call_allowed": False,
    "model_api_integration_allowed": False,
    "network_allowed": False,
    "tool_execution_allowed": False,
    "external_action_allowed": False,
    "production_state_mutation_allowed": False,
    "raw_value_exposure_allowed": False,
    "detokenization_allowed": False,
}


@dataclass(frozen=True)
class PrivateModeState:
    state_id: str
    state_name: str
    active_by_default: bool
    tokenization_required: bool
    model_may_see_raw_values: bool
    detokenization_allowed: bool
    cloud_lm_allowed: bool
    local_only_required: bool
    lm1_package_effects: tuple[str, ...]
    lm2_package_effects: tuple[str, ...]
    operator_copy: str


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _short_hash(*parts: object) -> str:
    return hashlib.sha256("\0".join(str(part) for part in parts).encode("utf-8")).hexdigest()[:16]


def _content_hash(payload: dict[str, Any]) -> str:
    clone = json.loads(stable_json(payload))
    clone.get("machine_proof", {}).pop("content_hash", None)
    return "sha256:" + hashlib.sha256(stable_json(clone).encode("utf-8")).hexdigest()


def private_mode_states() -> tuple[dict[str, Any], ...]:
    specs = (
        (
            "standard",
            True,
            False,
            False,
            False,
            False,
            False,
            "Standard mode still keeps raw values out of model-shaped fixture packages.",
        ),
        (
            "private",
            False,
            True,
            False,
            False,
            False,
            True,
            "Private Mode keeps raw details local and requires tokenized or summarized packages.",
        ),
        (
            "strict_private",
            False,
            True,
            False,
            False,
            False,
            True,
            "Strict Private Mode requires local-only handling for sensitive model-shaped packages.",
        ),
    )
    states = []
    for state_name, active, tokenization_required, raw_allowed, detok, cloud, local_only, copy in specs:
        states.append(
            asdict(
                PrivateModeState(
                    state_id=f"private_mode_state:{_short_hash(state_name)}",
                    state_name=state_name,
                    active_by_default=active,
                    tokenization_required=bool(tokenization_required),
                    model_may_see_raw_values=raw_allowed,
                    detokenization_allowed=detok,
                    cloud_lm_allowed=cloud,
                    local_only_required=local_only,
                    lm1_package_effects=(
                        "raw_values_included=false",
                        "MachineIntentCandidate schema only",
                        "no tools",
                        "no authority",
                    ),
                    lm2_package_effects=(
                        "raw_values_included=false",
                        "forbidden tools explicit",
                        "detokenization denied without future receipt",
                        "Gate 4 validation required",
                    ),
                    operator_copy=copy,
                )
            )
        )
    return tuple(states)


def build_payload(*, generated_at: str | None = None) -> dict[str, Any]:
    generated_at = generated_at or DEFAULT_GENERATED_AT
    states = private_mode_states()
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "contract_status": CONTRACT_STATUS,
        "generated_at": generated_at,
        "active_state": "standard",
        "private_mode_available": True,
        "private_mode_active": False,
        "strict_private_mode_available": True,
        "strict_private_mode_active": False,
        "state_machine": {
            "states": states,
            "allowed_operator_choices": ("standard", "private", "strict_private"),
            "default_state": "standard",
            "activation_requires_future_operator_choice": True,
        },
        "package_effect_summary": {
            "lm1": "Private settings change what context LM1 packages may include; they do not call LM1.",
            "lm2": "Private settings change role-package privacy fields; they do not call LM2.",
            "strict_private": "Strict Private Mode requires local-only model eligibility before any future live review.",
            "raw_values_included": False,
            "model_may_see_raw_values": False,
        },
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "machine_proof": {
            "private_mode_policy_exported": True,
            "private_mode_active": False,
            "strict_private_mode_active": False,
            "state_count": len(states),
            "strict_private_state_exists": any(item["state_name"] == "strict_private" for item in states),
            "all_states_block_raw_model_values": all(item["model_may_see_raw_values"] is False for item in states),
            "strict_private_requires_local_only": any(
                item["state_name"] == "strict_private" and item["local_only_required"] is True for item in states
            ),
            "live_model_call_performed": False,
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
        "# Private Mode Policy Readiness",
        "",
        f"Status: {CONTRACT_STATUS}",
        f"Private Mode active: {str(payload['private_mode_active']).lower()}",
        f"Strict Private Mode active: {str(payload['strict_private_mode_active']).lower()}",
        "",
        "Package effects:",
        f"- LM1: {payload['package_effect_summary']['lm1']}",
        f"- LM2: {payload['package_effect_summary']['lm2']}",
        "",
        "This is backend policy shape only. It does not enable live models or tools.",
    ]
    operator_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return json_path, operator_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export private mode policy readiness read-model.")
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
                    "private_mode_active": payload["private_mode_active"],
                    "strict_private_mode_active": payload["strict_private_mode_active"],
                    "all_live_authority_false": payload["machine_proof"]["all_live_authority_false"],
                }
            ),
            end="",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
