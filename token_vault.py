"""Token Vault v1.

Minimal local privacy/tokenization contract using synthetic fixtures only. This
module does not process real private data, call cloud services, or reveal raw
fixture values in generated read-model output.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_GENERATED_AT = "2026-05-26T00:00:00+00:00"

SCHEMA_VERSION = "token_vault_v2"
READ_MODEL_ID = "token_vault_status"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
OPERATOR_EXPORT_NAME = f"{READ_MODEL_ID}_OPERATOR.md"
CONTRACT_STATUS = "SYNTHETIC_LOCAL_TOKEN_VAULT_NO_REAL_DATA"

TOKEN_KINDS = ("person_name", "email", "phone", "bank_account", "tax_id")

SYNTHETIC_VALUES = {
    "person_name": "Synthetic Example Person",
    "email": "synthetic.person@example.invalid",
    "phone": "555-0100",
    "bank_account": "000123456789",
    "tax_id": "00-0000000",
}

AUTHORITY_BOUNDARY = {
    "real_data_ingestion_allowed": False,
    "cloud_tokenization_allowed": False,
    "external_model_share_allowed": False,
    "raw_value_export_allowed": False,
    "credential_handling_allowed": False,
    "network_allowed": False,
    "production_state_mutation_allowed": False,
}


@dataclass(frozen=True)
class TokenizedValue:
    token_id: str
    token_kind: str
    token_scope: str
    stable_within_scope: bool
    raw_value_included: bool
    synthetic_fixture_only: bool
    authority_boundary: dict[str, bool]


@dataclass(frozen=True)
class TokenizationDeclaration:
    tokenization_applied: bool
    token_scope: str
    raw_values_included: bool
    privacy_level: str
    tokenization_required: bool
    model_may_see_raw_values: bool
    detokenization_allowed: bool
    local_only_required: bool
    reason_codes: tuple[str, ...]
    token_kinds: tuple[str, ...]
    safe_for_role_package: bool
    next_safe_move: str


@dataclass(frozen=True)
class TokenizationPolicyDecision:
    policy_decision_id: str
    privacy_level: str
    tokenization_required: bool
    model_may_see_raw_values: bool
    detokenization_allowed: bool
    local_only_required: bool
    reason_codes: tuple[str, ...]
    synthetic_fixture_only: bool
    authority_boundary: dict[str, bool]
    next_safe_move: str


@dataclass(frozen=True)
class PrivacyReadinessStatus:
    privacy_readiness_id: str
    privacy_readiness_status: str
    production_token_vault_ready: bool
    synthetic_tokenization_ready: bool
    real_sensitive_data_allowed: bool
    private_mode_requires_tokenization: bool
    strict_private_requires_local_only: bool
    cloud_lm_blocked_when_private: bool
    private_mode_backend_policy_exists: bool
    operator_summary: str
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


def _kind_for_value(raw_value: str) -> str:
    lowered = raw_value.lower()
    if "@" in lowered:
        return "email"
    if re.search(r"\b\d{2}-\d{7}\b", raw_value):
        return "tax_id"
    digits = re.sub(r"\D", "", raw_value)
    if len(digits) >= 10 and raw_value.startswith("555"):
        return "phone"
    if len(digits) >= 9:
        return "bank_account"
    return "person_name"


def tokenize_synthetic_value(raw_value: str, *, scope: str, token_kind: str | None = None) -> TokenizedValue:
    kind = token_kind or _kind_for_value(raw_value)
    if kind not in TOKEN_KINDS:
        kind = "person_name"
    token_id = f"tok_{kind}:{_short_hash(scope, kind, raw_value)}"
    return TokenizedValue(
        token_id=token_id,
        token_kind=kind,
        token_scope=scope,
        stable_within_scope=True,
        raw_value_included=False,
        synthetic_fixture_only=True,
        authority_boundary=dict(AUTHORITY_BOUNDARY),
    )


def tokenize_synthetic_fixture(scope: str) -> tuple[dict[str, Any], ...]:
    return tuple(asdict(tokenize_synthetic_value(value, scope=scope, token_kind=kind)) for kind, value in SYNTHETIC_VALUES.items())


def evaluate_tokenization_policy(context: Mapping[str, Any] | None = None) -> dict[str, Any]:
    context = context or {}
    world_ref = str(context.get("world_ref") or "").lower()
    client_ref = str(context.get("client_ref") or "").lower()
    artifact_kind = str(context.get("artifact_kind") or "").lower()
    file_type = str(context.get("file_type") or "").lower()
    private_mode_active = bool(context.get("private_mode_active", False))
    strict_private_mode_active = bool(context.get("strict_private_mode_active", False))

    reason_codes: list[str] = ["SYNTHETIC_POLICY_ONLY"]
    privacy_level = "LOW_METADATA"
    tokenization_required = False
    local_only_required = False

    if world_ref == "finance" or "invoice" in artifact_kind or "spreadsheet" in file_type:
        privacy_level = "CLIENT_FINANCE_FILE_METADATA"
        tokenization_required = True
        local_only_required = True
        reason_codes.extend(("FINANCE_CONTEXT", "CLIENT_FILE_METADATA", "INVOICE_WORKBOOK_REFERENCE"))
    if client_ref and client_ref != "unknown":
        reason_codes.append("CLIENT_SCOPED")
    if private_mode_active:
        tokenization_required = True
        local_only_required = True
        reason_codes.append("PRIVATE_MODE_ACTIVE")
    if strict_private_mode_active:
        privacy_level = "STRICT_PRIVATE_CLIENT_METADATA"
        tokenization_required = True
        local_only_required = True
        reason_codes.append("STRICT_PRIVATE_MODE_ACTIVE")

    decision = TokenizationPolicyDecision(
        policy_decision_id=f"tokenization_policy:{_short_hash(world_ref, client_ref, artifact_kind, private_mode_active, strict_private_mode_active)}",
        privacy_level=privacy_level,
        tokenization_required=tokenization_required,
        model_may_see_raw_values=False,
        detokenization_allowed=False,
        local_only_required=local_only_required,
        reason_codes=tuple(dict.fromkeys(reason_codes)),
        synthetic_fixture_only=True,
        authority_boundary=dict(AUTHORITY_BOUNDARY),
        next_safe_move=(
            "Attach scoped tokens and metadata summaries only; do not expose raw values."
            if tokenization_required
            else "Raw values still remain excluded in v1 fixtures; continue metadata-only packaging."
        ),
    )
    return asdict(decision)


def privacy_readiness_status() -> dict[str, Any]:
    status = PrivacyReadinessStatus(
        privacy_readiness_id="privacy_readiness:token_vault_v2",
        privacy_readiness_status="POLICY_SEEDED_PRODUCTION_TOKEN_VAULT_NOT_ACTIVE",
        production_token_vault_ready=False,
        synthetic_tokenization_ready=True,
        real_sensitive_data_allowed=False,
        private_mode_requires_tokenization=True,
        strict_private_requires_local_only=True,
        cloud_lm_blocked_when_private=True,
        private_mode_backend_policy_exists=True,
        operator_summary="Private Mode backend policy exists, but production token vault is not active yet.",
        authority_boundary=dict(AUTHORITY_BOUNDARY),
        next_safe_move="Keep live LM exposure off until production token vault and private-mode receipts exist.",
    )
    return asdict(status)


def role_package_tokenization_declaration(scope: str, token_kinds: tuple[str, ...] = TOKEN_KINDS) -> dict[str, Any]:
    policy = evaluate_tokenization_policy(
        {
            "world_ref": "finance" if "finance" in scope else "unknown",
            "client_ref": scope.split(":")[2] if len(scope.split(":")) > 2 else "unknown",
            "artifact_kind": "invoice_workbook" if "invoice" in scope or "finance" in scope else "",
        }
    )
    declaration = TokenizationDeclaration(
        tokenization_applied=True,
        token_scope=scope,
        raw_values_included=False,
        privacy_level=str(policy["privacy_level"]),
        tokenization_required=bool(policy["tokenization_required"]),
        model_may_see_raw_values=False,
        detokenization_allowed=False,
        local_only_required=bool(policy["local_only_required"]),
        reason_codes=tuple(policy["reason_codes"]),
        token_kinds=token_kinds,
        safe_for_role_package=True,
        next_safe_move="Attach tokenization metadata to future role packages; never include raw sensitive values.",
    )
    return asdict(declaration)


def build_payload(*, generated_at: str | None = None) -> dict[str, Any]:
    generated_at = generated_at or DEFAULT_GENERATED_AT
    scope_a = "scope:finance:capital_hilton_fixture"
    scope_b = "scope:finance:st_annes_fixture"
    tokens_a = tokenize_synthetic_fixture(scope_a)
    tokens_b = tokenize_synthetic_fixture(scope_b)
    stable_repeat = tokenize_synthetic_value(SYNTHETIC_VALUES["email"], scope=scope_a, token_kind="email")
    cross_scope = tokenize_synthetic_value(SYNTHETIC_VALUES["email"], scope=scope_b, token_kind="email")
    finance_policy = evaluate_tokenization_policy(
        {
            "world_ref": "finance",
            "client_ref": "capital_hilton",
            "artifact_kind": "running_invoice_workbook",
            "file_type": "spreadsheet",
        }
    )
    strict_policy = evaluate_tokenization_policy(
        {
            "world_ref": "finance",
            "client_ref": "capital_hilton",
            "artifact_kind": "running_invoice_workbook",
            "file_type": "spreadsheet",
            "strict_private_mode_active": True,
        }
    )
    privacy_readiness = privacy_readiness_status()
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "contract_status": CONTRACT_STATUS,
        "generated_at": generated_at,
        "token_policy": {
            "synthetic_only": True,
            "same_entity_stable_within_scope": True,
            "different_scopes_do_not_imply_same_raw_entity": True,
            "generated_readmodels_expose_raw_values": False,
        },
        "policy_examples": {
            "capital_hilton_finance_workbook": finance_policy,
            "strict_private_finance_workbook": strict_policy,
        },
        "privacy_readiness": privacy_readiness,
        "fixture_tokens": {
            "scope_a": tokens_a,
            "scope_b": tokens_b,
        },
        "role_package_declaration": role_package_tokenization_declaration(scope_a),
        "connects_to_chain": {
            "gate_3": "Role packages can declare tokenization_applied, token_scope, and raw_values_included=false.",
            "lm1_lm2": "Future LM calls must receive tokens/summaries, not raw sensitive values.",
            "readiness_gate": "Live LM readiness can block when tokenization is required but absent.",
        },
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "machine_proof": {
            "real_data_ingestion_performed": False,
            "cloud_call_performed": False,
            "network_performed": False,
            "raw_values_exported": False,
            "finance_policy_tokenization_required": finance_policy["tokenization_required"] is True,
            "finance_policy_blocks_raw_model_visibility": finance_policy["model_may_see_raw_values"] is False,
            "strict_policy_local_only_required": strict_policy["local_only_required"] is True,
            "privacy_readiness_production_token_vault_ready": privacy_readiness["production_token_vault_ready"],
            "privacy_readiness_synthetic_tokenization_ready": privacy_readiness["synthetic_tokenization_ready"],
            "cloud_lm_blocked_when_private": privacy_readiness["cloud_lm_blocked_when_private"],
            "stable_within_scope": stable_repeat.token_id == tokenize_synthetic_value(SYNTHETIC_VALUES["email"], scope=scope_a, token_kind="email").token_id,
            "different_scope_token_differs": stable_repeat.token_id != cross_scope.token_id,
            "role_package_raw_values_included": False,
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
        "# Token Vault Status",
        "",
        f"Status: {CONTRACT_STATUS}",
        f"Stable within scope: {str(proof.get('stable_within_scope')).lower()}",
        f"Different scope differs: {str(proof.get('different_scope_token_differs')).lower()}",
        f"Raw values exported: {str(proof.get('raw_values_exported')).lower()}",
        f"Production token vault ready: {str(proof.get('privacy_readiness_production_token_vault_ready')).lower()}",
        "",
        "Synthetic tokenization fixture only. No real sensitive values are exported.",
        "Private Mode backend policy exists, but production token vault is not active yet.",
    ]
    operator_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return json_path, operator_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export token vault status read-model.")
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
                    "stable_within_scope": payload["machine_proof"]["stable_within_scope"],
                    "different_scope_token_differs": payload["machine_proof"]["different_scope_token_differs"],
                    "raw_values_exported": payload["machine_proof"]["raw_values_exported"],
                }
            ),
            end="",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
