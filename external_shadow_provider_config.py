"""External shadow provider configuration v0.

This module turns provider-policy records plus local credential-presence probes
into a redacted shadow-only configuration. It never reads or stores credential
values, never calls a provider, and never grants production authority.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping

import external_lm_safe_package_compiler
import provider_policy_registry


DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_GENERATED_AT = "2026-05-26T00:00:00+00:00"

SCHEMA_VERSION = "external_shadow_provider_config_v0"
READ_MODEL_ID = "external_shadow_provider_config"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
OPERATOR_EXPORT_NAME = f"{READ_MODEL_ID}_OPERATOR.md"
CONTRACT_STATUS = "EXTERNAL_SHADOW_PROVIDER_CONFIG_NO_PRODUCTION_AUTHORITY"

SHADOW_ONLY = "SHADOW_ONLY"
SHADOW_CALL_READY = "SHADOW_CALL_READY"
SHADOW_PROVIDER_NOT_CONFIGURED = "SHADOW_PROVIDER_NOT_CONFIGURED"
SHADOW_PROVIDER_POLICY_BLOCKED = "SHADOW_PROVIDER_POLICY_BLOCKED"

LM1 = external_lm_safe_package_compiler.LM1
LM2 = external_lm_safe_package_compiler.LM2

AUTHORITY_BOUNDARY = {
    "production_live_lm_authority_allowed": False,
    "production_provider_activation_allowed": False,
    "provider_key_material_access_allowed": False,
    "credential_value_storage_allowed": False,
    "network_call_allowed": False,
    "tool_execution_allowed": False,
    "external_action_allowed": False,
    "send_submit_allowed": False,
    "ledger_posting_allowed": False,
    "production_state_mutation_allowed": False,
}

_SHARED_SHADOW_CREDENTIAL_ENV = "OPENCLAW_EXTERNAL_SHADOW_CREDENTIAL"
_LM1_SHADOW_CREDENTIAL_ENV = "OPENCLAW_EXTERNAL_LM1_SHADOW_CREDENTIAL"
_LM2_SHADOW_CREDENTIAL_ENV = "OPENCLAW_EXTERNAL_LM2_SHADOW_CREDENTIAL"

_CREDENTIAL_ENV_BY_MODEL_CLASS = {
    provider_policy_registry.FAST_EXTERNAL_INTENT_MODEL: (
        _LM1_SHADOW_CREDENTIAL_ENV,
        _SHARED_SHADOW_CREDENTIAL_ENV,
    ),
    provider_policy_registry.STRONG_EXTERNAL_ROLE_MODEL: (
        _LM2_SHADOW_CREDENTIAL_ENV,
        _SHARED_SHADOW_CREDENTIAL_ENV,
    ),
}


@dataclass(frozen=True)
class ExternalShadowProviderConfigRecord:
    provider_ref: str
    provider_class: str
    model_alias: str
    lane_allowed: tuple[str, ...]
    allowed_mode: str
    production_allowed: bool
    credentials_present: bool
    credential_source_ref: str
    credential_value_exposed: bool
    shadow_calls_allowed: bool
    allowed_data_classes: tuple[str, ...]
    forbidden_data_classes: tuple[str, ...]
    privacy_requirements: tuple[str, ...]
    tokenization_required: bool
    raw_values_allowed: bool
    cost_tier: str
    latency_tier: str
    expected_strengths: tuple[str, ...]
    expected_failure_modes: tuple[str, ...]
    blocked_reasons: tuple[str, ...]
    authority_boundary: dict[str, bool]
    next_safe_move: str


@dataclass(frozen=True)
class ExternalShadowProviderSelection:
    selection_id: str
    source_request_id: str
    lane: str
    model_alias: str
    provider_ref: str
    provider_class: str
    status: str
    shadow_call_ready: bool
    production_allowed: bool
    credentials_present: bool
    credential_source_ref: str
    package_policy_passed: bool
    adapter_provider_config: dict[str, Any]
    blocked_reasons: tuple[str, ...]
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


def _credential_present(env: Mapping[str, str], model_alias: str) -> bool:
    return any(bool(str(env.get(name) or "")) for name in _CREDENTIAL_ENV_BY_MODEL_CLASS.get(model_alias, ()))


def _credential_ref(model_alias: str, present: bool) -> str:
    if model_alias == provider_policy_registry.FAST_EXTERNAL_INTENT_MODEL:
        lane = "lm1"
    elif model_alias == provider_policy_registry.STRONG_EXTERNAL_ROLE_MODEL:
        lane = "lm2"
    else:
        lane = "unknown"
    state = "present" if present else "absent"
    return f"env:redacted_external_shadow_{lane}_credential_{state}"


def _provider_class(provider_ref: str) -> str:
    if provider_ref == "provider_class:external_privacy_safe_fast_intent":
        return "fast_external_intent_shadow_provider_class"
    if provider_ref == "provider_class:external_privacy_safe_role_reasoner":
        return "strong_external_role_shadow_provider_class"
    return provider_ref.replace("provider_class:", "")


def _external_provider_policy_records() -> tuple[provider_policy_registry.ProviderPolicyRecord, ...]:
    records = []
    for record in provider_policy_registry.provider_policy_records():
        if record.model_class_ref in {
            provider_policy_registry.FAST_EXTERNAL_INTENT_MODEL,
            provider_policy_registry.STRONG_EXTERNAL_ROLE_MODEL,
        } and record.provider_ref.startswith("provider_class:external_privacy_safe"):
            records.append(record)
    return tuple(records)


def build_provider_config_records(env: Mapping[str, str] | None = None) -> tuple[dict[str, Any], ...]:
    env = os.environ if env is None else env
    records: list[ExternalShadowProviderConfigRecord] = []
    for policy in _external_provider_policy_records():
        credentials_present = _credential_present(env, policy.model_class_ref)
        blocked: list[str] = []
        if not credentials_present:
            blocked.append("MISSING_SHADOW_CREDENTIAL")
        record = ExternalShadowProviderConfigRecord(
            provider_ref=policy.provider_ref,
            provider_class=_provider_class(policy.provider_ref),
            model_alias=policy.model_class_ref,
            lane_allowed=policy.lane_allowed,
            allowed_mode=SHADOW_ONLY,
            production_allowed=False,
            credentials_present=credentials_present,
            credential_source_ref=_credential_ref(policy.model_class_ref, credentials_present),
            credential_value_exposed=False,
            shadow_calls_allowed=credentials_present,
            allowed_data_classes=policy.allowed_context_classes,
            forbidden_data_classes=policy.forbidden_context_classes,
            privacy_requirements=(
                "tokenized/minimized package",
                "raw_values_included=false",
                "credentials_present=false",
                "secrets_present=false",
                "detokenization outside the model",
                "Guardian privacy/output gate required",
            ),
            tokenization_required=True,
            raw_values_allowed=False,
            cost_tier=policy.cost_tier,
            latency_tier=policy.latency_tier,
            expected_strengths=policy.strengths,
            expected_failure_modes=policy.expected_failure_modes,
            blocked_reasons=tuple(blocked),
            authority_boundary=dict(AUTHORITY_BOUNDARY),
            next_safe_move=(
                "This provider class may be used for isolated shadow calls only."
                if credentials_present
                else "Keep returning SHADOW_PROVIDER_NOT_CONFIGURED until a shadow credential is present."
            ),
        )
        records.append(record)
    return tuple(asdict(record) for record in records)


def _chain_lane(lane: object) -> str:
    lane_value = str(lane or "").upper()
    if lane_value in {"LM1", "LM1_INTENT_PROPOSAL"}:
        return "LM1_INTENT_PROPOSAL"
    return "LM2_ROLE_RESPONSE"


def _safe_package_from_input(package_or_result: Mapping[str, Any] | None) -> dict[str, Any]:
    if not isinstance(package_or_result, Mapping):
        return {}
    if isinstance(package_or_result.get("safe_package"), Mapping):
        return dict(package_or_result["safe_package"])
    return dict(package_or_result)


def adapter_provider_config(
    payload_or_records: Mapping[str, Any] | tuple[Mapping[str, Any], ...] | None = None,
    *,
    lane: str | None = None,
    model_alias: str | None = None,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    if payload_or_records is None:
        records = build_provider_config_records(env)
    elif isinstance(payload_or_records, Mapping):
        records = tuple(payload_or_records.get("provider_configs") or ())
    else:
        records = tuple(payload_or_records)
    chain_lane = _chain_lane(lane) if lane else ""
    configured_refs = []
    for record in records:
        if chain_lane and chain_lane not in tuple(record.get("lane_allowed") or ()):
            continue
        if model_alias and str(record.get("model_alias") or "") != model_alias:
            continue
        if bool(record.get("shadow_calls_allowed")):
            configured_refs.append(str(record.get("provider_ref") or ""))
    return {
        "external_shadow_enabled": bool(configured_refs),
        "configured_external_provider_refs": tuple(dict.fromkeys(ref for ref in configured_refs if ref)),
        "allow_local_fallback_smoke": False,
        "local_fallback_provider_refs": ("provider_class:local_or_private_fallback_model",),
    }


def adapter_provider_config_from_environment(
    *,
    lane: str | None = None,
    model_alias: str | None = None,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    return adapter_provider_config(None, lane=lane, model_alias=model_alias, env=env)


def select_provider_for_safe_package(
    package_or_result: Mapping[str, Any] | None,
    *,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    package = _safe_package_from_input(package_or_result)
    source_request_id = str(package.get("source_request_id") or "")
    lane = external_lm_safe_package_compiler.LM1 if _chain_lane(package.get("lane")) == "LM1_INTENT_PROPOSAL" else external_lm_safe_package_compiler.LM2
    chain_lane = _chain_lane(lane)
    model_alias = str(package.get("model_class_recommended") or "")
    records = build_provider_config_records(env)
    matching = next(
        (
            record
            for record in records
            if record.get("model_alias") == model_alias and chain_lane in tuple(record.get("lane_allowed") or ())
        ),
        None,
    )
    blocked: list[str] = []
    if not package.get("package_id", "").startswith("external_lm_safe_package:"):
        blocked.append("NOT_EXTERNAL_LM_SAFE_PACKAGE")
    if not bool(package.get("external_lm_allowed")) or str(package.get("eligibility_verdict") or "") != "EXTERNAL_ALLOWED":
        blocked.append("EXTERNAL_ELIGIBILITY_NOT_PASSED")
    if bool(package.get("local_lm_required")):
        blocked.append("LOCAL_ONLY_REQUIRED")
    if str(package.get("privacy_level") or "").upper() == "STRICT_PRIVATE_CLIENT_METADATA":
        blocked.append("STRICT_PRIVATE_LOCAL_ONLY")
    if bool(package.get("raw_values_included")):
        blocked.append("RAW_VALUES_NOT_ALLOWED")
    if bool(package.get("credentials_present")) or bool(package.get("secrets_present")):
        blocked.append("PACKAGE_CONTAINS_CREDENTIAL_OR_SECRET")
    if bool(package.get("tokenization_required")) and not bool(package.get("tokenization_applied")):
        blocked.append("TOKENIZATION_REQUIRED")
    if not bool(package.get("package_minimized")):
        blocked.append("PACKAGE_NOT_MINIMIZED")
    if not bool(package.get("leak_scan_passed")):
        blocked.append("LEAK_SCAN_NOT_PASSED")
    if not bool(package.get("ready_for_external_shadow")):
        blocked.append("NOT_READY_FOR_EXTERNAL_SHADOW")
    if bool(package.get("ready_for_production")):
        blocked.append("PACKAGE_READY_FOR_PRODUCTION_MUST_BE_FALSE")
    if matching is None:
        blocked.append("NO_SHADOW_PROVIDER_POLICY_MATCH")

    credentials_present = bool((matching or {}).get("credentials_present", False))
    credential_source_ref = str((matching or {}).get("credential_source_ref") or "env:redacted_external_shadow_credential_absent")
    if matching is not None and not credentials_present:
        blocked.append("MISSING_SHADOW_CREDENTIAL")

    package_policy_passed = not any(
        reason
        in {
            "NOT_EXTERNAL_LM_SAFE_PACKAGE",
            "EXTERNAL_ELIGIBILITY_NOT_PASSED",
            "LOCAL_ONLY_REQUIRED",
            "STRICT_PRIVATE_LOCAL_ONLY",
            "RAW_VALUES_NOT_ALLOWED",
            "PACKAGE_CONTAINS_CREDENTIAL_OR_SECRET",
            "TOKENIZATION_REQUIRED",
            "PACKAGE_NOT_MINIMIZED",
            "LEAK_SCAN_NOT_PASSED",
            "NOT_READY_FOR_EXTERNAL_SHADOW",
            "PACKAGE_READY_FOR_PRODUCTION_MUST_BE_FALSE",
            "NO_SHADOW_PROVIDER_POLICY_MATCH",
        }
        for reason in blocked
    )
    shadow_call_ready = package_policy_passed and credentials_present
    status = (
        SHADOW_CALL_READY
        if shadow_call_ready
        else SHADOW_PROVIDER_POLICY_BLOCKED
        if package_policy_passed is False and "MISSING_SHADOW_CREDENTIAL" not in blocked
        else SHADOW_PROVIDER_NOT_CONFIGURED
    )
    adapter_config = adapter_provider_config(records, lane=lane, model_alias=model_alias)
    selection = ExternalShadowProviderSelection(
        selection_id=f"external_shadow_provider_selection:{_short_hash(source_request_id, lane, model_alias, status)}",
        source_request_id=source_request_id,
        lane=lane,
        model_alias=model_alias,
        provider_ref=str((matching or {}).get("provider_ref") or ""),
        provider_class=str((matching or {}).get("provider_class") or ""),
        status=status,
        shadow_call_ready=shadow_call_ready,
        production_allowed=False,
        credentials_present=credentials_present,
        credential_source_ref=credential_source_ref,
        package_policy_passed=package_policy_passed,
        adapter_provider_config=adapter_config,
        blocked_reasons=tuple(dict.fromkeys(blocked)),
        authority_boundary=dict(AUTHORITY_BOUNDARY),
        next_safe_move=(
            "External shadow call may proceed only through the shadow adapter; production remains blocked."
            if shadow_call_ready
            else "Do not call an external model until the blocked provider/package condition is resolved."
        ),
    )
    return asdict(selection)


def build_payload(*, generated_at: str | None = None, env: Mapping[str, str] | None = None) -> dict[str, Any]:
    generated_at = generated_at or DEFAULT_GENERATED_AT
    records = build_provider_config_records(env)
    configured_refs = tuple(record["provider_ref"] for record in records if record["shadow_calls_allowed"])
    lm1_safe = external_lm_safe_package_compiler.compile_lm1_safe_package(
        {
            "source_request_id": "external_shadow_provider_lm1_fixture",
            "user_message": "what's next for the Capital Hilton invoice?",
            "world_ref": "finance",
            "client_ref": "capital_hilton",
            "workflow_ref": "capital_hilton_invoice_workflow",
            "file_display_name": "Invoice Capitol Hilton Running.xlsx",
            "artifact_kind": "running_invoice_workbook",
        }
    )
    lm2_safe = external_lm_safe_package_compiler.compile_lm2_safe_package(
        {
            "source_request_id": "external_shadow_provider_lm2_fixture",
            "package_id": "role_package:external_shadow_provider_lm2_fixture",
            "role_identity": "CASSANDRA_CLARA",
            "task": "Draft client-safe invoice package wording for Capital Hilton; do not send.",
            "world_ref": "finance",
            "client_ref": "capital_hilton",
            "workflow_ref": "capital_hilton_invoice_workflow",
            "privacy_level": "CLIENT_FINANCE_FILE_METADATA",
            "tokenization_applied": True,
            "raw_values_included": False,
        }
    )
    examples = {
        "lm1_provider_selection": select_provider_for_safe_package(lm1_safe, env=env),
        "lm2_provider_selection": select_provider_for_safe_package(lm2_safe, env=env),
    }
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "contract_status": CONTRACT_STATUS,
        "generated_at": generated_at,
        "provider_configs": records,
        "configured_provider_refs": configured_refs,
        "target_aliases": {
            "lm1": provider_policy_registry.FAST_EXTERNAL_INTENT_MODEL,
            "lm2": provider_policy_registry.STRONG_EXTERNAL_ROLE_MODEL,
        },
        "examples": examples,
        "operator_summary": (
            "External shadow provider policy exists. Credential presence is recorded only as booleans; "
            "production model authority remains blocked."
        ),
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "machine_proof": {
            "provider_config_present": True,
            "credential_values_exposed": False,
            "any_shadow_provider_configured": bool(configured_refs),
            "lm1_alias_supported": any(
                record["model_alias"] == provider_policy_registry.FAST_EXTERNAL_INTENT_MODEL for record in records
            ),
            "lm2_alias_supported": any(
                record["model_alias"] == provider_policy_registry.STRONG_EXTERNAL_ROLE_MODEL for record in records
            ),
            "production_allowed": False,
            "network_call_performed": False,
            "model_call_performed": False,
            "tool_execution_performed": False,
            "external_action_performed": False,
            "secret_values_stored": False,
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
        "# External Shadow Provider Config",
        "",
        f"Status: {CONTRACT_STATUS}",
        f"LM1 alias supported: {str(proof.get('lm1_alias_supported')).lower()}",
        f"LM2 alias supported: {str(proof.get('lm2_alias_supported')).lower()}",
        f"Any shadow provider configured: {str(proof.get('any_shadow_provider_configured')).lower()}",
        "Credential values exposed: false",
        "Production provider authority: false",
        "",
        "This is a shadow/test configuration surface only. It records credential presence as booleans and redacted refs.",
    ]
    operator_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return json_path, operator_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export external shadow provider configuration read-model.")
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
                    "any_shadow_provider_configured": payload["machine_proof"]["any_shadow_provider_configured"],
                    "production_allowed": payload["machine_proof"]["production_allowed"],
                    "credential_values_exposed": payload["machine_proof"]["credential_values_exposed"],
                }
            ),
            end="",
        )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
