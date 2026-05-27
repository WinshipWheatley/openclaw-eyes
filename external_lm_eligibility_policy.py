"""External LM eligibility policy v0.

Determines whether a Gate 1/3 package is privacy-safe enough for a future
external LM lane. This module does not call models, access credentials, or
grant production authority.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import token_vault


DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_GENERATED_AT = "2026-05-26T00:00:00+00:00"

SCHEMA_VERSION = "external_lm_eligibility_policy_v0"
READ_MODEL_ID = "external_lm_eligibility_policy"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
OPERATOR_EXPORT_NAME = f"{READ_MODEL_ID}_OPERATOR.md"
CONTRACT_STATUS = "EXTERNAL_LM_ELIGIBILITY_POLICY_NO_LIVE_CALLS"

FAST_EXTERNAL_INTENT_MODEL = "FAST_EXTERNAL_INTENT_MODEL"
STRONG_EXTERNAL_ROLE_MODEL = "STRONG_EXTERNAL_ROLE_MODEL"
LOCAL_FALLBACK_MODEL = "LOCAL_FALLBACK_MODEL"
LOCAL_ONLY_MODEL = "LOCAL_ONLY_MODEL"
NO_SAFE_MODEL = "NO_SAFE_MODEL"

LM1 = "LM1"
LM2 = "LM2"

REQUIRED_PRIVACY_CONTROLS = (
    "production_token_vault_ready",
    "privacy_policy_receipt_present",
    "tokenization_when_sensitive",
    "raw_values_excluded",
    "context_minimized",
    "secrets_absent",
    "no_model_side_detokenization",
    "guardian_privacy_output_gate",
)

EXTERNAL_SAFE_DATA_CLASSES = (
    "LOW_METADATA",
    "TOKENIZED_METADATA",
    "TOKENIZED_CLIENT_FINANCE_METADATA",
    "MINIMIZED_ROLE_PACKAGE",
    "MACHINE_INTENT_PROPOSAL_SCHEMA",
)

EXTERNAL_BLOCKED_DATA_CLASSES = (
    "RAW_PRIVATE_BODY",
    "RAW_SECRET",
    "CREDENTIAL_MATERIAL",
    "STRICT_PRIVATE_CLIENT_METADATA",
    "UNMINIMIZED_CLIENT_CONTEXT",
    "LEGAL_PRIVILEGED_RAW",
    "HEALTH_RAW",
)

LOCAL_ONLY_DATA_CLASSES = (
    "STRICT_PRIVATE_CLIENT_METADATA",
    "LEGAL_PRIVILEGED_METADATA",
    "HEALTH_METADATA",
)

AUTHORITY_BOUNDARY = {
    "production_live_lm_authority_allowed": False,
    "model_api_integration_allowed": False,
    "provider_key_material_access_allowed": False,
    "network_allowed": False,
    "tool_execution_allowed": False,
    "external_action_allowed": False,
    "send_submit_allowed": False,
    "ledger_posting_allowed": False,
    "production_state_mutation_allowed": False,
    "raw_sensitive_cloud_exposure_allowed": False,
}


@dataclass(frozen=True)
class ExternalLmEligibilityResult:
    eligibility_id: str
    recommended_lane: str
    external_lm_allowed: bool
    local_lm_required: bool
    no_safe_model: bool
    reason_codes: tuple[str, ...]
    required_privacy_controls: tuple[str, ...]
    required_receipts: tuple[str, ...]
    safe_data_classes: tuple[str, ...]
    blocked_data_classes: tuple[str, ...]
    package_minimized: bool
    tokenization_applied: bool
    raw_values_included: bool
    detokenization_required_inside_model: bool
    guardian_privacy_gate_required: bool
    recommended_model_class: str
    package_token_estimate: int
    context_minimization_applied: bool
    serial_package_recommended: bool
    redundant_pass_avoidance: bool
    use_beast_model_only_when_needed: bool
    downgrade_testing_allowed_only_after_baseline_passes: bool
    cost_control_notes: tuple[str, ...]
    token_budget_notes: tuple[str, ...]
    live_production_activation_allowed: bool
    authority_boundary: dict[str, bool]
    next_safe_move: str


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _short_hash(*parts: object) -> str:
    return hashlib.sha256("\0".join(str(part) for part in parts).encode("utf-8")).hexdigest()[:16]


def _content_hash(payload: dict[str, Any]) -> str:
    clone = json.loads(stable_json(payload))
    clone.get("machine_proof", {}).pop("content_hash", None)
    return "sha256:" + hashlib.sha256(stable_json(clone).encode("utf-8")).hexdigest()


def _tuple_upper(value: object) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value.upper(),) if value else ()
    if isinstance(value, (list, tuple, set)):
        return tuple(str(item).upper() for item in value if str(item))
    return (str(value).upper(),)


def _truthy(mapping: Mapping[str, Any], key: str, default: bool = False) -> bool:
    if key in mapping:
        return bool(mapping.get(key, default))
    privacy = mapping.get("privacy") if isinstance(mapping.get("privacy"), Mapping) else {}
    if key in privacy:
        return bool(privacy.get(key, default))
    return bool(default)


def _token_estimate(package: Mapping[str, Any]) -> int:
    explicit = package.get("package_token_estimate")
    if isinstance(explicit, int) and explicit > 0:
        return explicit
    text = stable_json(
        {
            "lane": package.get("recommended_lane") or package.get("chain_lane"),
            "task": package.get("task") or package.get("requested_action"),
            "privacy_level": package.get("privacy_level") or package.get("privacy_classification"),
            "context_classes": package.get("context_classes") or package.get("allowed_context_classes"),
            "raw_values_included": package.get("raw_values_included"),
        }
    )
    return max(64, min(8192, len(text) // 4))


def _privacy_level(package: Mapping[str, Any]) -> str:
    privacy = package.get("privacy") if isinstance(package.get("privacy"), Mapping) else {}
    return str(
        package.get("privacy_level")
        or package.get("privacy_classification")
        or privacy.get("privacy_level")
        or "LOW_METADATA"
    ).upper()


def _data_classes(package: Mapping[str, Any], privacy_level: str) -> tuple[str, ...]:
    classes = _tuple_upper(package.get("data_classes"))
    if not classes:
        classes = _tuple_upper(package.get("context_classes"))
    if not classes:
        classes = _tuple_upper(package.get("allowed_context_classes"))
    if not classes:
        classes = (privacy_level,)
    return tuple(dict.fromkeys(classes))


def _safe_classes_for_package(
    *,
    data_classes: tuple[str, ...],
    privacy_level: str,
    tokenization_applied: bool,
    raw_values_included: bool,
) -> tuple[str, ...]:
    safe: list[str] = []
    if privacy_level in {"METADATA_ONLY_TOKENIZED_REFS", "TOKENIZED_FIXTURE"} and tokenization_applied and not raw_values_included:
        safe.append("TOKENIZED_METADATA")
    if privacy_level == "CLIENT_FINANCE_FILE_METADATA" and tokenization_applied and not raw_values_included:
        safe.append("TOKENIZED_CLIENT_FINANCE_METADATA")
    for data_class in data_classes:
        if data_class in EXTERNAL_SAFE_DATA_CLASSES:
            safe.append(data_class)
        elif data_class == "CLIENT_FINANCE_FILE_METADATA" and tokenization_applied and not raw_values_included:
            safe.append("TOKENIZED_CLIENT_FINANCE_METADATA")
    if not safe and privacy_level == "LOW_METADATA":
        safe.append("LOW_METADATA")
    safe.append("MINIMIZED_ROLE_PACKAGE")
    return tuple(dict.fromkeys(safe))


def evaluate_external_lm_eligibility(
    package: Mapping[str, Any] | None = None,
    *,
    lane: str = LM2,
    substrate: Mapping[str, Any] | None = None,
    privacy_policy_receipt_present: bool | None = None,
) -> dict[str, Any]:
    """Return the deterministic external-LM eligibility decision for a package."""

    package = package or {}
    lane = str(package.get("recommended_lane") or lane or LM2).upper()
    if lane in {"LM1_INTENT_PROPOSAL", "LM1"}:
        recommended_lane = LM1
    else:
        recommended_lane = LM2

    substrate = substrate or token_vault.inspect_production_token_vault_substrate()
    pii_vault_ready = bool(substrate.get("production_token_vault_ready"))
    privacy_receipt = (
        bool(privacy_policy_receipt_present)
        if privacy_policy_receipt_present is not None
        else bool(substrate.get("privacy_policy_receipt_present"))
    )

    privacy_level = _privacy_level(package)
    data_classes = _data_classes(package, privacy_level)
    tokenization_applied = _truthy(package, "tokenization_applied")
    raw_values_included = _truthy(package, "raw_values_included")
    package_minimized = _truthy(package, "package_minimized", _truthy(package, "context_minimization_applied", True))
    context_minimized = _truthy(package, "context_minimization_applied", package_minimized)
    privacy_policy_allows_external = _truthy(package, "privacy_policy_allows_external_model", True)
    model_allowed_for_data_classes = _truthy(package, "model_allowed_for_data_classes", True)
    detokenization_required_inside_model = _truthy(package, "detokenization_required_inside_model")
    credentials_or_secrets_present = _truthy(package, "credentials_or_secrets_present") or _truthy(package, "secrets_present")
    private_mode_active = _truthy(package, "private_mode_active")
    strict_private_mode_active = _truthy(package, "strict_private_mode_active")
    offline_mode = _truthy(package, "offline_mode")
    external_credits_low = _truthy(package, "external_credits_low")
    guardian_required = _truthy(package, "guardian_privacy_gate_required", True)

    sensitive_or_private = privacy_level != "LOW_METADATA" or any(
        data_class not in {"LOW_METADATA", "MINIMIZED_ROLE_PACKAGE", "MACHINE_INTENT_PROPOSAL_SCHEMA"}
        for data_class in data_classes
    )
    tokenization_missing = sensitive_or_private and not tokenization_applied

    blocked_data_classes: list[str] = []
    blocked_data_classes.extend(data_class for data_class in data_classes if data_class in EXTERNAL_BLOCKED_DATA_CLASSES)
    if raw_values_included:
        blocked_data_classes.append("RAW_PRIVATE_BODY")
    if credentials_or_secrets_present:
        blocked_data_classes.append("CREDENTIAL_MATERIAL")
    if not package_minimized:
        blocked_data_classes.append("UNMINIMIZED_CLIENT_CONTEXT")
    blocked_data_classes = list(dict.fromkeys(blocked_data_classes))

    reason_codes: list[str] = []
    local_required = False
    no_safe_model = False

    if pii_vault_ready:
        reason_codes.append("PII_VAULT_READY")
    else:
        reason_codes.append("PII_VAULT_NOT_READY")
    if privacy_receipt:
        reason_codes.append("PRIVACY_POLICY_RECEIPT_PRESENT")
    else:
        reason_codes.append("PRIVACY_POLICY_RECEIPT_MISSING")
    if sensitive_or_private:
        reason_codes.append("SENSITIVE_OR_PRIVATE_CONTEXT")
    if tokenization_applied:
        reason_codes.append("TOKENIZATION_APPLIED")
    if tokenization_missing:
        reason_codes.append("TOKENIZATION_REQUIRED_BUT_ABSENT")
        local_required = True
    if raw_values_included:
        reason_codes.append("RAW_VALUES_INCLUDED_BLOCK_EXTERNAL")
        local_required = True
    if not package_minimized:
        reason_codes.append("PACKAGE_NOT_MINIMIZED_BLOCK_EXTERNAL")
        local_required = True
    if not privacy_policy_allows_external:
        reason_codes.append("PRIVACY_POLICY_BLOCKS_EXTERNAL_MODEL")
        local_required = True
    if not model_allowed_for_data_classes:
        reason_codes.append("MODEL_POLICY_BLOCKS_DATA_CLASS")
        local_required = True
    if detokenization_required_inside_model:
        reason_codes.append("DETOKENIZATION_INSIDE_MODEL_BLOCKED")
        local_required = True
    if credentials_or_secrets_present:
        reason_codes.append("CREDENTIALS_OR_SECRETS_PRESENT")
        no_safe_model = True
    if private_mode_active:
        reason_codes.append("PRIVATE_MODE_REQUIRES_LOCAL_OR_BLOCKED_EXTERNAL")
        local_required = True
    if strict_private_mode_active or privacy_level in LOCAL_ONLY_DATA_CLASSES:
        reason_codes.append("STRICT_OR_LOCAL_ONLY_PRIVACY_REQUIRES_LOCAL")
        local_required = True
    if offline_mode:
        reason_codes.append("OFFLINE_MODE_LOCAL_REQUIRED")
        local_required = True
    if external_credits_low:
        reason_codes.append("EXTERNAL_CREDITS_LOW_LOCAL_FALLBACK_ALLOWED")
        local_required = True
    if not guardian_required:
        reason_codes.append("GUARDIAN_PRIVACY_GATE_REQUIRED")
    if blocked_data_classes:
        reason_codes.append("BLOCKED_DATA_CLASS_PRESENT")

    safe_data_classes = _safe_classes_for_package(
        data_classes=data_classes,
        privacy_level=privacy_level,
        tokenization_applied=tokenization_applied,
        raw_values_included=raw_values_included,
    )
    external_allowed = (
        pii_vault_ready
        and privacy_receipt
        and not tokenization_missing
        and not raw_values_included
        and package_minimized
        and context_minimized
        and privacy_policy_allows_external
        and model_allowed_for_data_classes
        and not detokenization_required_inside_model
        and not credentials_or_secrets_present
        and not private_mode_active
        and not strict_private_mode_active
        and not offline_mode
        and guardian_required
        and not blocked_data_classes
    )
    if external_allowed:
        reason_codes.append("EXTERNAL_LM_PRIVACY_ELIGIBLE")
        local_required = False
    elif not no_safe_model:
        reason_codes.append("EXTERNAL_LM_BLOCKED_LOCAL_FALLBACK_OR_LOCAL_ONLY")

    if no_safe_model:
        recommended_model = NO_SAFE_MODEL
    elif external_allowed and recommended_lane == LM1:
        recommended_model = FAST_EXTERNAL_INTENT_MODEL
    elif external_allowed and recommended_lane == LM2:
        recommended_model = STRONG_EXTERNAL_ROLE_MODEL
    elif strict_private_mode_active or privacy_level in LOCAL_ONLY_DATA_CLASSES:
        recommended_model = LOCAL_ONLY_MODEL
    elif local_required:
        recommended_model = LOCAL_FALLBACK_MODEL
    else:
        recommended_model = LOCAL_FALLBACK_MODEL

    required_receipts = (
        "production_token_vault_ready_receipt",
        "privacy_policy_receipt",
        "provider_policy_receipt",
        "model_selection_policy_receipt",
        "real_lm1_production_policy_receipt" if recommended_lane == LM1 else "real_lm2_production_policy_receipt",
        "guardian_privacy_output_gate_receipt",
    )
    token_estimate = _token_estimate(package)
    cost_notes = (
        "Use stronger external models when the package is protected; reduce cost by minimizing context first.",
        "Use local fallback for offline, strict/private, policy-blocked, or credit-saving work.",
        "Do not run weak/local downgrade tests until the external baseline has passed.",
    )
    token_notes = (
        f"Estimated package tokens: {token_estimate}.",
        "Prefer serial role packages over broad context dumps.",
        "Avoid redundant LM passes when Gate 2/Gate 4 already produced a deterministic answer.",
    )
    result = ExternalLmEligibilityResult(
        eligibility_id=f"external_lm_eligibility:{_short_hash(recommended_lane, privacy_level, tuple(reason_codes))}",
        recommended_lane=recommended_lane,
        external_lm_allowed=external_allowed,
        local_lm_required=local_required,
        no_safe_model=no_safe_model,
        reason_codes=tuple(dict.fromkeys(reason_codes)),
        required_privacy_controls=REQUIRED_PRIVACY_CONTROLS,
        required_receipts=required_receipts,
        safe_data_classes=safe_data_classes,
        blocked_data_classes=tuple(blocked_data_classes),
        package_minimized=package_minimized,
        tokenization_applied=tokenization_applied,
        raw_values_included=raw_values_included,
        detokenization_required_inside_model=detokenization_required_inside_model,
        guardian_privacy_gate_required=True,
        recommended_model_class=recommended_model,
        package_token_estimate=token_estimate,
        context_minimization_applied=context_minimized,
        serial_package_recommended=True,
        redundant_pass_avoidance=True,
        use_beast_model_only_when_needed=True,
        downgrade_testing_allowed_only_after_baseline_passes=True,
        cost_control_notes=cost_notes,
        token_budget_notes=token_notes,
        live_production_activation_allowed=False,
        authority_boundary=dict(AUTHORITY_BOUNDARY),
        next_safe_move=(
            "Package is privacy-eligible for a future external LM route, but production live LM remains off."
            if external_allowed
            else "Use local fallback/local-only or repair the listed privacy blockers before external LM review."
        ),
    )
    return asdict(result)


def evaluate_for_lm1_thread_package(package: Mapping[str, Any]) -> dict[str, Any]:
    privacy_level = _privacy_level(package)
    data_classes = tuple(dict.fromkeys((*_data_classes(package, privacy_level), "MACHINE_INTENT_PROPOSAL_SCHEMA")))
    return evaluate_external_lm_eligibility(
        {
            **dict(package),
            "recommended_lane": LM1,
            "data_classes": data_classes,
            "package_minimized": True,
            "context_minimization_applied": True,
            "privacy_policy_allows_external_model": True,
            "model_allowed_for_data_classes": True,
            "guardian_privacy_gate_required": True,
        },
        lane=LM1,
    )


def evaluate_for_lm2_role_package(package: Mapping[str, Any]) -> dict[str, Any]:
    privacy_level = _privacy_level(package)
    data_classes = tuple(dict.fromkeys((*_data_classes(package, privacy_level), "MINIMIZED_ROLE_PACKAGE")))
    return evaluate_external_lm_eligibility(
        {
            **dict(package),
            "recommended_lane": LM2,
            "data_classes": data_classes,
            "package_minimized": True,
            "context_minimization_applied": True,
            "privacy_policy_allows_external_model": True,
            "model_allowed_for_data_classes": True,
            "guardian_privacy_gate_required": True,
        },
        lane=LM2,
    )


def build_payload(*, generated_at: str | None = None) -> dict[str, Any]:
    generated_at = generated_at or DEFAULT_GENERATED_AT
    substrate = token_vault.ensure_production_token_vault_substrate(generated_at=generated_at)
    examples = {
        "finance_tokenized_lm1_external_allowed": evaluate_external_lm_eligibility(
            {
                "recommended_lane": LM1,
                "privacy_level": "CLIENT_FINANCE_FILE_METADATA",
                "data_classes": ("CLIENT_FINANCE_FILE_METADATA", "MACHINE_INTENT_PROPOSAL_SCHEMA"),
                "tokenization_applied": True,
                "raw_values_included": False,
                "package_minimized": True,
                "context_minimization_applied": True,
                "privacy_policy_allows_external_model": True,
                "model_allowed_for_data_classes": True,
            },
            lane=LM1,
            substrate=substrate,
        ),
        "finance_tokenized_lm2_external_allowed": evaluate_external_lm_eligibility(
            {
                "recommended_lane": LM2,
                "privacy_level": "CLIENT_FINANCE_FILE_METADATA",
                "data_classes": ("CLIENT_FINANCE_FILE_METADATA", "MINIMIZED_ROLE_PACKAGE"),
                "tokenization_applied": True,
                "raw_values_included": False,
                "package_minimized": True,
                "context_minimization_applied": True,
                "privacy_policy_allows_external_model": True,
                "model_allowed_for_data_classes": True,
            },
            lane=LM2,
            substrate=substrate,
        ),
        "raw_values_block_external": evaluate_external_lm_eligibility(
            {
                "recommended_lane": LM2,
                "privacy_level": "CLIENT_FINANCE_FILE_METADATA",
                "data_classes": ("CLIENT_FINANCE_FILE_METADATA",),
                "tokenization_applied": True,
                "raw_values_included": True,
                "package_minimized": True,
            },
            lane=LM2,
            substrate=substrate,
        ),
        "strict_private_local_only": evaluate_external_lm_eligibility(
            {
                "recommended_lane": LM2,
                "privacy_level": "STRICT_PRIVATE_CLIENT_METADATA",
                "data_classes": ("STRICT_PRIVATE_CLIENT_METADATA",),
                "tokenization_applied": True,
                "raw_values_included": False,
                "package_minimized": True,
                "strict_private_mode_active": True,
            },
            lane=LM2,
            substrate=substrate,
        ),
        "credentials_no_safe_model": evaluate_external_lm_eligibility(
            {
                "recommended_lane": LM1,
                "privacy_level": "LOW_METADATA",
                "data_classes": ("LOW_METADATA",),
                "tokenization_applied": False,
                "raw_values_included": False,
                "package_minimized": True,
                "credentials_or_secrets_present": True,
            },
            lane=LM1,
            substrate=substrate,
        ),
        "unminimized_local_fallback": evaluate_external_lm_eligibility(
            {
                "recommended_lane": LM2,
                "privacy_level": "CLIENT_FINANCE_FILE_METADATA",
                "data_classes": ("CLIENT_FINANCE_FILE_METADATA",),
                "tokenization_applied": True,
                "raw_values_included": False,
                "package_minimized": False,
            },
            lane=LM2,
            substrate=substrate,
        ),
    }
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "contract_status": CONTRACT_STATUS,
        "generated_at": generated_at,
        "policy_summary": {
            "target_posture": "prefer_external_when_privacy_safe",
            "local_models_are_for": (
                "fallback",
                "offline",
                "credit_saving",
                "strict_private_or_local_only",
                "policy_blocked_context",
                "shadow_smoke",
            ),
            "live_production_status": "NOT_ACTIVE",
        },
        "examples": examples,
        "connects_to_chain": {
            "gate_1": "Gate 1 classifies privacy and builds minimized/tokenized package input.",
            "lm1": "Eligible LM1 package may use a fast external intent model class later.",
            "gate_2": "Gate 2 still validates the MachineIntentCandidate; LM1 grants no authority.",
            "gate_3": "Gate 3 compiles the minimized role package and privacy fields.",
            "lm2": "Eligible LM2 package may use a strong external role model class later.",
            "gate_4": "Guardian privacy/output gate is required before any response can be trusted.",
        },
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "machine_proof": {
            "model_call_performed": False,
            "network_performed": False,
            "provider_key_material_access_performed": False,
            "production_live_lm_authority_granted": False,
            "finance_lm1_external_eligible": examples["finance_tokenized_lm1_external_allowed"]["external_lm_allowed"],
            "finance_lm2_external_eligible": examples["finance_tokenized_lm2_external_allowed"]["external_lm_allowed"],
            "raw_values_block_external": examples["raw_values_block_external"]["external_lm_allowed"] is False,
            "strict_private_local_only": examples["strict_private_local_only"]["recommended_model_class"] == LOCAL_ONLY_MODEL,
            "credentials_no_safe_model": examples["credentials_no_safe_model"]["no_safe_model"] is True,
            "unminimized_blocks_external": examples["unminimized_local_fallback"]["external_lm_allowed"] is False,
            "live_production_activation_allowed": False,
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
        "# External LM Eligibility Policy",
        "",
        f"Status: {CONTRACT_STATUS}",
        f"Finance LM1 external eligible: {str(proof.get('finance_lm1_external_eligible')).lower()}",
        f"Finance LM2 external eligible: {str(proof.get('finance_lm2_external_eligible')).lower()}",
        f"Raw values block external: {str(proof.get('raw_values_block_external')).lower()}",
        f"Strict Private local-only: {str(proof.get('strict_private_local_only')).lower()}",
        "",
        "External model classes are eligible only for minimized/tokenized packages. Live production models remain off.",
    ]
    operator_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return json_path, operator_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export external LM eligibility policy read-model.")
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
                    "finance_lm1_external_eligible": payload["machine_proof"]["finance_lm1_external_eligible"],
                    "finance_lm2_external_eligible": payload["machine_proof"]["finance_lm2_external_eligible"],
                    "live_production_activation_allowed": payload["machine_proof"]["live_production_activation_allowed"],
                }
            ),
            end="",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
