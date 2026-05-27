"""Operator Readiness Surface v0.

Mac-readable readiness/control payload for Mission Control. This is product
surface data only: it summarizes readiness in human language, suggests rare
operator choices, and keeps backend proof below deck. It does not enable live
LMs, tools, actions, or production state mutation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping

import gate_chain_harness
import guardian_output_gate
import guardian_trust_ramp_simulator
import lm_readiness_dashboard
import model_router_policy
import provider_policy_registry
import shadow_lm_mode
import token_vault
import universal_intake_contract


DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_GENERATED_AT = "2026-05-26T00:00:00+00:00"

SCHEMA_VERSION = "operator_readiness_surface_v0"
READ_MODEL_ID = "operator_readiness_surface"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
OPERATOR_EXPORT_NAME = f"{READ_MODEL_ID}_OPERATOR.md"
CONTRACT_STATUS = "MAC_READINESS_SURFACE_NO_LIVE_ACTIONS"

AUTHORITY_BOUNDARY = {
    "live_lm_call_allowed": False,
    "model_api_integration_allowed": False,
    "network_allowed": False,
    "provider_key_material_access_allowed": False,
    "agent_dispatch_allowed": False,
    "worker_dispatch_allowed": False,
    "tool_execution_allowed": False,
    "workflow_execution_allowed": False,
    "external_action_allowed": False,
    "send_submit_allowed": False,
    "approval_execution_allowed": False,
    "ledger_posting_allowed": False,
    "production_state_mutation_allowed": False,
    "workbook_body_read_allowed": False,
    "spreadsheet_cell_read_allowed": False,
    "ocr_allowed": False,
    "pdf_generation_allowed": False,
}

OPERATOR_SUMMARY_LINES = (
    "LM shadow rails are ready.",
    "Live models are not active.",
    "Private Mode backend policy is seeded.",
    "Production token vault is not active yet.",
    "No tools or actions are enabled.",
)

BACKEND_JARGON_TERMS = (
    "request contract",
    "provider policy registry",
    "token vault table",
    "gate 2",
    "gate 3",
)

BUTTON_LABELS = (
    "Enable Private Mode",
    "Enable Strict Private Mode",
    "Keep Standard Mode",
    "Explain Privacy",
    "View Proof",
    "Not now",
)


@dataclass(frozen=True)
class OperatorReadinessButton:
    button_id: str
    label: str
    human_reason: str
    choice_contract: dict[str, Any]
    requires_confirmation: bool
    enables_live_lm: bool
    enables_tool_action: bool
    safe_to_show_now: bool


@dataclass(frozen=True)
class PrivateModeCard:
    available: bool
    active: bool
    strict_available: bool
    strict_active: bool
    plain_language_description: str
    visual_state_hint: str
    allowed_toggles_for_mac: tuple[str, ...]
    backend_effect_if_enabled: tuple[str, ...]
    blocked_effects: tuple[str, ...]
    authority_boundary: dict[str, bool]


@dataclass(frozen=True)
class ProofShelf:
    gate_chain_status: str
    gate1_privacy_status: str
    gate1_operational_snapshot_status: str
    gate2_readback_status: str
    gate3_package_readback_status: str
    lm1_shadow_status: str
    lm2_shadow_status: str
    tokenization_status: str
    request_response_bridge_status: str
    production_live_blocker_status: str
    provider_activation_receipt_status: str
    private_mode_policy_status: str
    read_model_visibility_status: str
    provider_policy_status: str
    guardian_gate_status: str
    trust_ramp_candidate_level: int
    active_trust_level: int
    live_lm_blockers: tuple[str, ...]
    read_model_refs: tuple[str, ...]


@dataclass(frozen=True)
class OperatorReadinessSurfacePayload:
    surface_id: str
    contract_status: str
    operator_summary: tuple[str, ...]
    private_mode_card: dict[str, Any]
    suggested_buttons: tuple[dict[str, Any], ...]
    proof_shelf: dict[str, Any]
    operator_language: dict[str, Any]
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


def _readiness_inputs(generated_at: str) -> dict[str, Any]:
    dashboard = lm_readiness_dashboard.build_payload(generated_at=generated_at)
    return {
        "lm_readiness_dashboard": dashboard,
        "provider_policy_registry": provider_policy_registry.build_payload(generated_at=generated_at),
        "model_router_policy": model_router_policy.build_payload(generated_at=generated_at),
        "shadow_lm_mode": shadow_lm_mode.build_payload(generated_at=generated_at, persist=True),
        "token_vault_status": token_vault.build_payload(generated_at=generated_at),
        "universal_intake_contract": universal_intake_contract.build_payload(generated_at=generated_at),
        "guardian_trust_ramp_simulator": guardian_trust_ramp_simulator.run_trust_ramp(generated_at=generated_at, persist=True),
        "gate_chain_harness": gate_chain_harness.run_harness(generated_at=generated_at, persist=True),
        "guardian_output_gate": guardian_output_gate.build_payload(generated_at=generated_at),
    }


def build_private_mode_card(dashboard_payload: Mapping[str, Any]) -> dict[str, Any]:
    private = ((dashboard_payload.get("representative_flow") or {}).get("private_mode_readiness") or {})
    return asdict(
        PrivateModeCard(
            available=bool(private.get("private_mode_available", True)),
            active=bool(private.get("private_mode_active", False)),
            strict_available=bool(private.get("strict_private_mode_available", True)),
            strict_active=bool(private.get("strict_private_mode_active", False)),
            plain_language_description=(
                "Private Mode keeps raw details local. Strict Private Mode keeps processing local-only "
                "and blocks cloud model use unless a future policy explicitly allows it."
            ),
            visual_state_hint="available_inactive",
            allowed_toggles_for_mac=("private_mode", "strict_private_mode", "standard_mode"),
            backend_effect_if_enabled=(
                "Require tokenized or summarized context before model-shaped packages.",
                "Keep live models off until production privacy receipts exist.",
                "Prefer local-only model candidates when strict privacy is selected.",
            ),
            blocked_effects=(
                "Does not enable live models.",
                "Does not enable tools or actions.",
                "Does not send data outside OpenClaw.",
                "Does not read workbook bodies or cells.",
            ),
            authority_boundary=dict(AUTHORITY_BOUNDARY),
        )
    )


def _button(button_id: str, label: str, reason: str, choice: Mapping[str, Any], *, requires_confirmation: bool = False) -> dict[str, Any]:
    return asdict(
        OperatorReadinessButton(
            button_id=button_id,
            label=label,
            human_reason=reason,
            choice_contract=dict(choice),
            requires_confirmation=requires_confirmation,
            enables_live_lm=False,
            enables_tool_action=False,
            safe_to_show_now=True,
        )
    )


def suggested_buttons() -> tuple[dict[str, Any], ...]:
    return (
        _button(
            "operator_choice:enable_private_mode",
            "Enable Private Mode",
            "Keep raw details local when OpenClaw prepares future model-shaped packages.",
            {"choice_type": "privacy_mode", "requested_state": "private_mode_enabled", "live_lm_enabled": False},
            requires_confirmation=True,
        ),
        _button(
            "operator_choice:enable_strict_private_mode",
            "Enable Strict Private Mode",
            "Use the strongest local-only posture for sensitive work.",
            {"choice_type": "privacy_mode", "requested_state": "strict_private_mode_enabled", "live_lm_enabled": False},
            requires_confirmation=True,
        ),
        _button(
            "operator_choice:keep_standard_mode",
            "Keep Standard Mode",
            "Leave privacy mode off for now while live models remain inactive.",
            {"choice_type": "privacy_mode", "requested_state": "standard_mode"},
        ),
        _button(
            "operator_choice:explain_privacy",
            "Explain Privacy",
            "Show a plain explanation of what Private Mode changes.",
            {"choice_type": "readback", "requested_surface": "privacy_explanation"},
        ),
        _button(
            "operator_choice:view_proof",
            "View Proof",
            "Show the technical proof shelf below the calm summary.",
            {"choice_type": "readback", "requested_surface": "proof_shelf"},
        ),
        _button(
            "operator_choice:not_now",
            "Not now",
            "Dismiss this choice without changing backend readiness.",
            {"choice_type": "dismiss", "requested_state": "unchanged"},
        ),
    )


def build_proof_shelf(inputs: Mapping[str, Any]) -> dict[str, Any]:
    dashboard = inputs["lm_readiness_dashboard"]
    summary = dashboard["dashboard_summary"]
    guardian_payload = inputs["guardian_output_gate"]
    guardian_verdict = (
        (dashboard.get("representative_flow") or {}).get("gate4_result_summary") or {}
    ).get("verdict") or guardian_payload.get("examples", {}).get("safe_response", {}).get("validation_result", {}).get("verdict", "UNKNOWN")
    return asdict(
        ProofShelf(
            gate_chain_status="PASS" if inputs["gate_chain_harness"]["summary"]["failed"] == 0 else "CHECK",
            gate1_privacy_status=str(summary.get("gate1_privacy_request", "UNKNOWN")),
            gate1_operational_snapshot_status=str(summary.get("gate1_operational_snapshot", "UNKNOWN")),
            gate2_readback_status=str(summary.get("gate2_readback", "UNKNOWN")),
            gate3_package_readback_status=str(summary.get("gate3_package_readback", "UNKNOWN")),
            lm1_shadow_status=str(summary.get("lm1_shadow")),
            lm2_shadow_status=str(summary.get("lm2_package_shadow")),
            tokenization_status=str(summary.get("privacy_readiness_status")),
            request_response_bridge_status=str(summary.get("request_response_bridge", "UNKNOWN")),
            production_live_blocker_status=str(summary.get("production_live_blockers", "UNKNOWN")),
            provider_activation_receipt_status=str(summary.get("provider_activation_receipts", "UNKNOWN")),
            private_mode_policy_status=str(summary.get("private_mode_policy", "UNKNOWN")),
            read_model_visibility_status=str(summary.get("read_model_mirror_visibility", "UNKNOWN")),
            provider_policy_status=str(summary.get("provider_policy_registry")),
            guardian_gate_status=str(guardian_verdict),
            trust_ramp_candidate_level=int(summary.get("trust_ramp_candidate_level") or 0),
            active_trust_level=int(summary.get("trust_ramp_active_level") or 0),
            live_lm_blockers=tuple(summary.get("next_blockers") or ()),
            read_model_refs=(
                "generated/read_models/lm_readiness_dashboard.json",
                "generated/read_models/provider_policy_registry.json",
                "generated/read_models/model_router_policy.json",
                "generated/read_models/shadow_lm_mode.json",
                "generated/read_models/token_vault_status.json",
                "generated/read_models/universal_intake_contract.json",
                "generated/read_models/gate1_privacy_request_readiness.json",
                "generated/read_models/gate1_operational_snapshot.json",
                "generated/read_models/intent_ingest_gate.json",
                "generated/read_models/role_package_gate.json",
                "generated/read_models/request_response_bridge_readiness.json",
                "generated/read_models/live_lm_activation_requirements.json",
                "generated/read_models/private_mode_policy_readiness.json",
                "generated/read_models/read_model_mirror_visibility.json",
                "generated/read_models/guardian_trust_ramp_simulator.json",
                "generated/read_models/gate_chain_harness.json",
                "generated/read_models/guardian_output_gate.json",
            ),
        )
    )


def build_surface(inputs: Mapping[str, Any]) -> dict[str, Any]:
    dashboard = inputs["lm_readiness_dashboard"]
    summary = dashboard["dashboard_summary"]
    private_mode = build_private_mode_card(dashboard)
    buttons = suggested_buttons()
    proof_shelf = build_proof_shelf(inputs)
    surface = OperatorReadinessSurfacePayload(
        surface_id=f"operator_readiness_surface:{_short_hash(summary.get('lm1_shadow'), summary.get('lm2_package_shadow'), summary.get('privacy_readiness_status'))}",
        contract_status=CONTRACT_STATUS,
        operator_summary=OPERATOR_SUMMARY_LINES,
        private_mode_card=private_mode,
        suggested_buttons=buttons,
        proof_shelf=proof_shelf,
        operator_language={
            "primary_copy_avoids_backend_jargon": True,
            "preferred_phrases": (
                "Private Mode keeps raw details local.",
                "Models are not live yet.",
                "OpenClaw can test the chain safely.",
                "Strict Private Mode keeps processing local-only.",
            ),
            "hidden_as_proof_only": BACKEND_JARGON_TERMS,
        },
        authority_boundary=dict(AUTHORITY_BOUNDARY),
        next_safe_move=(
            "Mission Control can render this as a rare readiness/privacy choice card. "
            "Do not enable models, tools, or actions from this payload."
        ),
    )
    return asdict(surface)


def build_payload(*, generated_at: str | None = None) -> dict[str, Any]:
    generated_at = generated_at or DEFAULT_GENERATED_AT
    inputs = _readiness_inputs(generated_at)
    surface = build_surface(inputs)
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "contract_status": CONTRACT_STATUS,
        "generated_at": generated_at,
        "surface_payload": surface,
        "input_refs": tuple(inputs.keys()),
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "machine_proof": {
            "aggregates_lm_readiness_dashboard": inputs["lm_readiness_dashboard"]["read_model_id"] == lm_readiness_dashboard.READ_MODEL_ID,
            "private_mode_choices_exposed": bool(surface["private_mode_card"]["available"]),
            "private_mode_active": surface["private_mode_card"]["active"],
            "strict_private_mode_active": surface["private_mode_card"]["strict_active"],
            "live_lm_status": "NOT_ACTIVE",
            "live_model_call_performed": False,
            "model_api_call_performed": False,
            "tool_execution_performed": False,
            "external_action_performed": False,
            "production_state_mutation_performed": False,
            "operator_summary_backend_jargon_free": not any(
                term in " ".join(surface["operator_summary"]).lower() for term in BACKEND_JARGON_TERMS
            ),
            "suggested_button_count": len(surface["suggested_buttons"]),
            "suggested_buttons_enable_no_live_authority": all(
                button["enables_live_lm"] is False and button["enables_tool_action"] is False
                for button in surface["suggested_buttons"]
            ),
            "proof_shelf_available": bool(surface["proof_shelf"]["read_model_refs"]),
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
    surface = payload["surface_payload"]
    lines = [
        "# Operator Readiness Surface",
        "",
        f"Status: {CONTRACT_STATUS}",
        "",
        *surface["operator_summary"],
        "",
        "Suggested buttons:",
        *[f"- {button['label']}" for button in surface["suggested_buttons"]],
        "",
        "This payload is display/control shape only. It does not enable live models, tools, or actions.",
    ]
    operator_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return json_path, operator_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export operator readiness surface read-model.")
    parser.add_argument("--export-root", type=Path, default=DEFAULT_EXPORT_ROOT)
    parser.add_argument("--generated-at", default=DEFAULT_GENERATED_AT)
    parser.add_argument("--format", choices=("summary", "json"), default="summary")
    args = parser.parse_args(argv)

    payload = build_payload(generated_at=args.generated_at)
    json_path, operator_path = write_exports(payload, args.export_root)
    if args.format == "json":
        print(stable_json(payload), end="")
    else:
        surface = payload["surface_payload"]
        print(
            stable_json(
                {
                    "read_model_id": READ_MODEL_ID,
                    "json_path": json_path.as_posix(),
                    "operator_path": operator_path.as_posix(),
                    "operator_summary": surface["operator_summary"],
                    "suggested_buttons": tuple(button["label"] for button in surface["suggested_buttons"]),
                    "live_lm_status": payload["machine_proof"]["live_lm_status"],
                    "all_live_authority_false": payload["machine_proof"]["all_live_authority_false"],
                }
            ),
            end="",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
