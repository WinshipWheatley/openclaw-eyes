"""Live LM Readiness Gate v0.

Deterministic readiness contract for moving LM1/LM2 from fixtures toward shadow
or live candidate mode. This gate reports readiness only; it does not enable or
call models.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import guardian_output_gate
import model_router_policy


DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_GENERATED_AT = "2026-05-26T00:00:00+00:00"

SCHEMA_VERSION = "live_lm_readiness_gate_v0"
READ_MODEL_ID = "live_lm_readiness_gate"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
OPERATOR_EXPORT_NAME = f"{READ_MODEL_ID}_OPERATOR.md"
CONTRACT_STATUS = "LIVE_LM_READINESS_NOT_ACTIVE"

LM1_SHADOW_READY = "LM1_SHADOW_READY"
LM1_LIVE_READY = "LM1_LIVE_READY"
LM2_PACKAGE_SHADOW_READY = "LM2_PACKAGE_SHADOW_READY"
LM2_LIVE_RESPONSE_READY = "LM2_LIVE_RESPONSE_READY"
NOT_READY = "NOT_READY"
BLOCKED_POLICY_GAP = "BLOCKED_POLICY_GAP"
BLOCKED_TOKENIZATION_GAP = "BLOCKED_TOKENIZATION_GAP"
BLOCKED_GUARDIAN_GAP = "BLOCKED_GUARDIAN_GAP"
BLOCKED_RECEIPT_GAP = "BLOCKED_RECEIPT_GAP"

READINESS_OUTCOMES = (
    LM1_SHADOW_READY,
    LM1_LIVE_READY,
    LM2_PACKAGE_SHADOW_READY,
    LM2_LIVE_RESPONSE_READY,
    NOT_READY,
    BLOCKED_POLICY_GAP,
    BLOCKED_TOKENIZATION_GAP,
    BLOCKED_GUARDIAN_GAP,
    BLOCKED_RECEIPT_GAP,
)

AUTHORITY_BOUNDARY = {
    "live_lm_enable_allowed": False,
    "live_model_call_allowed": False,
    "model_api_integration_allowed": False,
    "network_allowed": False,
    "provider_key_material_access_allowed": False,
    "tool_execution_allowed": False,
    "external_action_allowed": False,
    "send_submit_allowed": False,
    "workflow_execution_allowed": False,
    "production_state_mutation_allowed": False,
}


@dataclass(frozen=True)
class LiveLMReadinessRequest:
    request_id: str
    lane: str
    target_mode: str
    model_policy_available: bool
    tokenization_required: bool
    tokenization_applied: bool
    guardian_available: bool
    receipt_policy_available: bool
    explicit_enablement_present: bool
    route_policy_available: bool
    fixture_shadow_available: bool


@dataclass(frozen=True)
class LiveLMReadinessDecision:
    decision_id: str
    request_id: str
    lane: str
    target_mode: str
    outcome: str
    selected_model_class: str
    blocked_reasons: tuple[str, ...]
    default_active_state: str
    live_lm_call_allowed: bool
    fixture_shadow_allowed: bool
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


def check_readiness(request: LiveLMReadinessRequest | Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(request, LiveLMReadinessRequest):
        request = LiveLMReadinessRequest(
            request_id=str(request.get("request_id") or "lm_readiness_request"),
            lane=str(request.get("lane") or "LM1").upper(),
            target_mode=str(request.get("target_mode") or "shadow").lower(),
            model_policy_available=bool(request.get("model_policy_available", True)),
            tokenization_required=bool(request.get("tokenization_required", False)),
            tokenization_applied=bool(request.get("tokenization_applied", False)),
            guardian_available=bool(request.get("guardian_available", True)),
            receipt_policy_available=bool(request.get("receipt_policy_available", False)),
            explicit_enablement_present=bool(request.get("explicit_enablement_present", False)),
            route_policy_available=bool(request.get("route_policy_available", True)),
            fixture_shadow_available=bool(request.get("fixture_shadow_available", True)),
        )

    lane = request.lane.upper()
    live_mode = request.target_mode == "live"
    model_decision = (
        model_router_policy.select_model_class(
            {
                "request_id": f"{request.request_id}:model_route",
                "chain_lane": "LM1_INTENT_PROPOSAL" if lane == "LM1" else "LM2_ROLE_RESPONSE",
                "task_type": "intent_proposal" if lane == "LM1" else "role_response",
                "role": "OPENCLAW_SYSTEM" if lane == "LM1" else "CASSANDRA",
                "risk_level": "low" if lane == "LM1" else "medium",
                "sensitivity_level": "low" if not request.tokenization_required else "high",
                "context_size": "small" if lane == "LM1" else "medium",
                "requires_structured_output": True,
                "tokenization_applied": request.tokenization_applied,
            }
        )
        if request.model_policy_available
        else {"selected_model_class": model_router_policy.NO_SAFE_MODEL}
    )

    blocked: list[str] = []
    if not request.model_policy_available:
        blocked.append("MODEL_POLICY_MISSING")
    if not request.route_policy_available:
        blocked.append("ROUTE_POLICY_MISSING")
    if request.tokenization_required and not request.tokenization_applied:
        blocked.append("TOKENIZATION_REQUIRED_BUT_ABSENT")
    if lane == "LM2" and not request.guardian_available:
        blocked.append("GUARDIAN_OUTPUT_GATE_MISSING")
    if live_mode and not request.receipt_policy_available:
        blocked.append("LIVE_RECEIPT_POLICY_MISSING")
    if live_mode and not request.explicit_enablement_present:
        blocked.append("EXPLICIT_LIVE_ENABLEMENT_MISSING")
    if model_decision.get("selected_model_class") == model_router_policy.NO_SAFE_MODEL:
        blocked.append("NO_SAFE_MODEL_CLASS")

    if "MODEL_POLICY_MISSING" in blocked or "ROUTE_POLICY_MISSING" in blocked:
        outcome = BLOCKED_POLICY_GAP
    elif "TOKENIZATION_REQUIRED_BUT_ABSENT" in blocked:
        outcome = BLOCKED_TOKENIZATION_GAP
    elif "GUARDIAN_OUTPUT_GATE_MISSING" in blocked:
        outcome = BLOCKED_GUARDIAN_GAP
    elif "LIVE_RECEIPT_POLICY_MISSING" in blocked or "EXPLICIT_LIVE_ENABLEMENT_MISSING" in blocked:
        outcome = BLOCKED_RECEIPT_GAP
    elif blocked:
        outcome = NOT_READY
    elif live_mode and lane == "LM1":
        outcome = LM1_LIVE_READY
    elif live_mode and lane == "LM2":
        outcome = LM2_LIVE_RESPONSE_READY
    elif lane == "LM1" and request.fixture_shadow_available:
        outcome = LM1_SHADOW_READY
    elif lane == "LM2" and request.fixture_shadow_available:
        outcome = LM2_PACKAGE_SHADOW_READY
    else:
        outcome = NOT_READY

    decision = LiveLMReadinessDecision(
        decision_id=f"live_lm_readiness_decision:{_short_hash(request.request_id, outcome, tuple(blocked))}",
        request_id=request.request_id,
        lane=lane,
        target_mode=request.target_mode,
        outcome=outcome,
        selected_model_class=str(model_decision.get("selected_model_class") or model_router_policy.NO_SAFE_MODEL),
        blocked_reasons=tuple(dict.fromkeys(blocked)),
        default_active_state="NOT_ACTIVE",
        live_lm_call_allowed=False,
        fixture_shadow_allowed=outcome in {LM1_SHADOW_READY, LM2_PACKAGE_SHADOW_READY},
        authority_boundary=dict(AUTHORITY_BOUNDARY),
        next_safe_move=(
            "Use fixture/shadow mode only; do not enable live LM calls."
            if outcome in {LM1_SHADOW_READY, LM2_PACKAGE_SHADOW_READY}
            else "Resolve readiness blockers before any live LM candidate lane."
        ),
    )
    return asdict(decision)


def build_payload(*, generated_at: str | None = None) -> dict[str, Any]:
    generated_at = generated_at or DEFAULT_GENERATED_AT
    examples = {
        "lm1_shadow": check_readiness({"request_id": "readiness_lm1_shadow", "lane": "LM1", "target_mode": "shadow"}),
        "lm2_shadow": check_readiness({"request_id": "readiness_lm2_shadow", "lane": "LM2", "target_mode": "shadow"}),
        "live_missing_policy": check_readiness(
            {
                "request_id": "readiness_missing_model_policy",
                "lane": "LM1",
                "target_mode": "live",
                "model_policy_available": False,
                "receipt_policy_available": True,
                "explicit_enablement_present": True,
            }
        ),
        "live_missing_tokenization": check_readiness(
            {
                "request_id": "readiness_missing_tokenization",
                "lane": "LM2",
                "target_mode": "live",
                "tokenization_required": True,
                "tokenization_applied": False,
                "receipt_policy_available": True,
                "explicit_enablement_present": True,
            }
        ),
        "live_default_not_active": check_readiness({"request_id": "readiness_live_default", "lane": "LM1", "target_mode": "live"}),
    }
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "contract_status": CONTRACT_STATUS,
        "generated_at": generated_at,
        "readiness_outcomes": READINESS_OUTCOMES,
        "examples": examples,
        "connects_to_chain": {
            "lm1": "Shadow-ready LM1 can accept MachineIntentCandidate fixtures before Gate 2.",
            "lm2": "Package-shadow-ready LM2 can accept role response fixtures after Gate 3.",
            "guardian": guardian_output_gate.READ_MODEL_ID,
            "default_state": "NOT_ACTIVE until explicit future enablement and receipts exist.",
        },
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "machine_proof": {
            "lm1_shadow_ready": examples["lm1_shadow"]["outcome"] == LM1_SHADOW_READY,
            "lm2_shadow_ready": examples["lm2_shadow"]["outcome"] == LM2_PACKAGE_SHADOW_READY,
            "missing_model_policy_blocks": examples["live_missing_policy"]["outcome"] == BLOCKED_POLICY_GAP,
            "missing_tokenization_blocks": examples["live_missing_tokenization"]["outcome"] == BLOCKED_TOKENIZATION_GAP,
            "live_default_not_active": examples["live_default_not_active"]["outcome"] in {BLOCKED_RECEIPT_GAP, NOT_READY},
            "live_model_call_performed": False,
            "model_api_integration_performed": False,
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
    proof = payload.get("machine_proof", {})
    lines = [
        "# Live LM Readiness Gate",
        "",
        f"Status: {CONTRACT_STATUS}",
        f"LM1 shadow ready: {str(proof.get('lm1_shadow_ready')).lower()}",
        f"LM2 package shadow ready: {str(proof.get('lm2_shadow_ready')).lower()}",
        f"Missing model policy blocks: {str(proof.get('missing_model_policy_blocks')).lower()}",
        f"Missing tokenization blocks: {str(proof.get('missing_tokenization_blocks')).lower()}",
        "",
        "Live LM calls remain NOT_ACTIVE in this lane.",
    ]
    operator_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return json_path, operator_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export live LM readiness gate read-model.")
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
                    "lm1_shadow_ready": payload["machine_proof"]["lm1_shadow_ready"],
                    "lm2_shadow_ready": payload["machine_proof"]["lm2_shadow_ready"],
                    "live_default_not_active": payload["machine_proof"]["live_default_not_active"],
                }
            ),
            end="",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
