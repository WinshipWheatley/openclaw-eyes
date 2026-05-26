"""Private value HMAC matching primitive for OpenClaw.

This module computes keyed, purpose-bound match tokens for private values.
It is for local matching only. It does not store keys, reveal keys, print raw
values, inspect credential files, call external systems, or treat plain
SHA-256 as a privacy boundary.
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import sys
import unicodedata
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import Any


DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_GENERATED_AT = "2026-05-25T00:00:00+00:00"

SCHEMA_VERSION = "private_value_hash_policy_v0"
READ_MODEL_ID = "private_value_hash_policy"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
OPERATOR_EXPORT_NAME = f"{READ_MODEL_ID}_OPERATOR.md"
CONTRACT_STATUS = "PRIVACY_SAFE_PRIVATE_VALUE_HMAC_POLICY_NO_SECRET_REVEAL"

KEY_ENV_VAR = "OPENCLAW_PRIVATE_VALUE_HMAC_KEY"
TEST_KEY_ENV_VAR = "OPENCLAW_PRIVATE_VALUE_HMAC_TEST_KEY"
ALLOW_TEST_KEY_ENV_VAR = "OPENCLAW_PRIVATE_VALUE_HMAC_ALLOW_TEST_KEY"
HMAC_VERSION = "v1"

PURPOSES = (
    "contact_email",
    "phone",
    "po_reference",
    "client_label",
    "source_ref",
    "generic_private_value",
)

AUTHORITY_BOUNDARY = {
    "live_secret_reveal_allowed": False,
    "live_key_export_allowed": False,
    "live_credential_handling_allowed": False,
    "live_external_action_allowed": False,
    "live_model_call_allowed": False,
    "live_tool_execution_allowed": False,
    "live_agent_dispatch_allowed": False,
    "raw_body_ingestion_allowed": False,
    "network_allowed": False,
    "mac_sync_import_allowed": False,
    "mission_control_swift_change_allowed": False,
    "git_push_pull_fetch_allowed": False,
}

BLOCKED_USES = (
    "plain_sha256_for_private_value_matching",
    "raw_value_in_read_model",
    "raw_value_in_log",
    "raw_value_in_model_context",
    "cross_purpose_hash_comparison",
    "production_use_of_test_key",
    "key_print_or_export",
    "dictionary_attack_prone_public_digest",
)


@dataclass(frozen=True)
class PrivateValueHashPolicy:
    policy_id: str
    doctrine: tuple[str, ...]
    key_policy: tuple[str, ...]
    normalization_policy: tuple[str, ...]
    purpose_binding_policy: tuple[str, ...]
    output_policy: tuple[str, ...]
    artifact_hash_distinction: tuple[str, ...]
    blocked_uses: tuple[str, ...]
    authority_boundary: dict[str, bool]
    next_safe_move: str


@dataclass(frozen=True)
class PrivateValueHashExample:
    example_id: str
    purpose: str
    raw_value_included: bool
    normalized_value_included: bool
    example_match_token_ref: str
    same_value_same_purpose_matches: bool
    same_value_different_purpose_matches: bool
    changed_value_matches: bool
    key_mode: str
    next_safe_move: str


@dataclass(frozen=True)
class PrivateValueHashBlocker:
    blocker_id: str
    blocker_type: str
    condition: str
    severity: str
    fail_closed: bool
    next_safe_move: str


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _content_hash(payload: dict[str, Any]) -> str:
    clone = json.loads(stable_json(payload))
    clone.get("machine_proof", {}).pop("content_hash", None)
    return "sha256:" + hashlib.sha256(stable_json(clone).encode("utf-8")).hexdigest()


def normalize_private_value(value: str) -> str:
    """Normalize a private value for local matching without exposing it."""

    if not isinstance(value, str):
        raise TypeError("private value must be a string")
    normalized = unicodedata.normalize("NFKC", value)
    normalized = " ".join(normalized.strip().split())
    return normalized.casefold()


def _normalize_purpose(purpose: str) -> str:
    normalized = str(purpose).strip().casefold().replace("-", "_")
    if normalized not in PURPOSES:
        raise ValueError(f"unsupported private value HMAC purpose: {normalized or 'missing'}")
    return normalized


def _load_hmac_key() -> tuple[bytes, str]:
    key = os.environ.get(KEY_ENV_VAR, "")
    if key:
        return key.encode("utf-8"), "protected_env_key"

    test_key = os.environ.get(TEST_KEY_ENV_VAR, "")
    allow_test_key = os.environ.get(ALLOW_TEST_KEY_ENV_VAR, "") == "1"
    if test_key and allow_test_key:
        return test_key.encode("utf-8"), "test_key_only"

    raise RuntimeError(
        f"{KEY_ENV_VAR} is not configured. Live private value matching is blocked until a protected local key is provided."
    )


def private_value_hmac(value: str, *, purpose: str) -> str:
    """Return a purpose-bound HMAC match token for a private value."""

    purpose_norm = _normalize_purpose(purpose)
    normalized = normalize_private_value(value)
    key, _key_mode = _load_hmac_key()
    message = f"openclaw-private-value-hmac\0{HMAC_VERSION}\0{purpose_norm}\0{normalized}".encode("utf-8")
    digest = hmac.new(key, message, hashlib.sha256).hexdigest()
    return f"hmac:{HMAC_VERSION}:{purpose_norm}:{digest}"


def verify_private_value_hmac(value: str, expected: str, *, purpose: str) -> bool:
    """Verify a private value against an expected HMAC token."""

    try:
        actual = private_value_hmac(value, purpose=purpose)
    except (RuntimeError, TypeError, ValueError):
        return False
    return hmac.compare_digest(actual, str(expected))


def key_policy_status() -> dict[str, Any]:
    """Return safe key status metadata. Never includes key material."""

    has_protected_key = bool(os.environ.get(KEY_ENV_VAR))
    test_key_enabled = bool(os.environ.get(TEST_KEY_ENV_VAR)) and os.environ.get(ALLOW_TEST_KEY_ENV_VAR, "") == "1"
    return {
        "protected_env_key_present": has_protected_key,
        "test_key_enabled": test_key_enabled and not has_protected_key,
        "live_integration_ready": has_protected_key,
        "key_material_exposed": False,
        "key_env_var_ref": KEY_ENV_VAR,
        "test_key_treated_as_production": False,
    }


def build_policy() -> PrivateValueHashPolicy:
    return PrivateValueHashPolicy(
        policy_id="private_value_hash_policy_v0",
        doctrine=(
            "Private value matching must use a local keyed HMAC, not public raw SHA-256.",
            "Raw private values never enter read-models, logs, model context, or operator markdown.",
            "The HMAC key stays local/protected and is never exported.",
            "The helper returns match tokens only; match tokens are not permission to reveal raw values.",
        ),
        key_policy=(
            f"Live key lookup uses protected local environment reference {KEY_ENV_VAR}.",
            "No production key is hardcoded in this module or read-model.",
            "Tests may use a test-only key only when explicitly enabled by a test environment flag.",
            "If no protected key exists, live matching fails closed rather than downgrading to plain SHA-256.",
        ),
        normalization_policy=(
            "Use Unicode NFKC normalization.",
            "Strip leading/trailing whitespace.",
            "Collapse internal whitespace.",
            "Use casefold for case-insensitive matching.",
            "Do not emit normalized private values.",
        ),
        purpose_binding_policy=tuple(f"Purpose supported: {purpose}" for purpose in PURPOSES)
        + (
            "HMAC message includes version and purpose for domain separation.",
            "Same raw value under different purposes must not produce the same token.",
        ),
        output_policy=(
            "Output format is hmac:v1:<purpose>:<digest>.",
            "Digest is HMAC-SHA256 over version, purpose, and normalized value.",
            "Output token is non-reversible without the local key.",
            "Verification uses constant-time compare.",
        ),
        artifact_hash_distinction=(
            "Plain SHA-256 may be used for artifact integrity and content hashes.",
            "Plain SHA-256 must not be used as a privacy boundary for names, emails, phone numbers, PO references, client labels, or source refs.",
            "Private-value HMACs are for local matching only, not file integrity.",
        ),
        blocked_uses=BLOCKED_USES,
        authority_boundary=AUTHORITY_BOUNDARY,
        next_safe_move="Provide a protected local key before live private-value matching; use test-only key only inside tests.",
    )


def build_blockers() -> tuple[PrivateValueHashBlocker, ...]:
    conditions = {
        "PLAIN_SHA256_PRIVATE_VALUE": (
            "critical",
            "Plain SHA-256 is attempted for private-value matching.",
            "Use purpose-bound keyed HMAC.",
        ),
        "RAW_VALUE_IN_READMODEL": (
            "critical",
            "A raw private value would enter generated output.",
            "Keep only match token refs and safe labels.",
        ),
        "KEY_NOT_CONFIGURED": (
            "high",
            "No protected local HMAC key is configured for live matching.",
            "Configure protected local key ref before live use.",
        ),
        "TEST_KEY_USED_AS_PRODUCTION": (
            "critical",
            "A test-only key is treated as production key material.",
            "Fail closed and provide protected production key ref.",
        ),
        "CROSS_PURPOSE_COMPARE": (
            "high",
            "A match token is compared under the wrong purpose.",
            "Verify using the exact purpose embedded in the token.",
        ),
        "KEY_EXPORT_ATTEMPTED": (
            "critical",
            "Key material would be printed or exported.",
            "Return safe key status metadata only.",
        ),
    }
    return tuple(
        PrivateValueHashBlocker(
            blocker_id=f"private_value_hash_blocker:{blocker_type.lower()}",
            blocker_type=blocker_type,
            condition=condition,
            severity=severity,
            fail_closed=True,
            next_safe_move=next_move,
        )
        for blocker_type, (severity, condition, next_move) in conditions.items()
    )


def build_examples() -> dict[str, Any]:
    return {
        "contact_email_match": asdict(
            PrivateValueHashExample(
                example_id="contact_email_match_token_policy",
                purpose="contact_email",
                raw_value_included=False,
                normalized_value_included=False,
                example_match_token_ref="hmac:v1:contact_email:<local-keyed-digest>",
                same_value_same_purpose_matches=True,
                same_value_different_purpose_matches=False,
                changed_value_matches=False,
                key_mode="test_key_only_for_unit_tests; protected_env_key_required_for_live",
                next_safe_move="Use match token only; keep raw contact value out of read-models.",
            )
        ),
        "po_reference_match": asdict(
            PrivateValueHashExample(
                example_id="po_reference_match_token_policy",
                purpose="po_reference",
                raw_value_included=False,
                normalized_value_included=False,
                example_match_token_ref="hmac:v1:po_reference:<local-keyed-digest>",
                same_value_same_purpose_matches=True,
                same_value_different_purpose_matches=False,
                changed_value_matches=False,
                key_mode="test_key_only_for_unit_tests; protected_env_key_required_for_live",
                next_safe_move="Use purpose-bound PO match token; do not expose raw PO/reference.",
            )
        ),
    }


def _model_schemas() -> dict[str, tuple[str, ...]]:
    return {
        "PrivateValueHashPolicy": tuple(field.name for field in fields(PrivateValueHashPolicy)),
        "PrivateValueHashExample": tuple(field.name for field in fields(PrivateValueHashExample)),
        "PrivateValueHashBlocker": tuple(field.name for field in fields(PrivateValueHashBlocker)),
    }


def build_payload(generated_at: str = DEFAULT_GENERATED_AT) -> dict[str, Any]:
    policy = build_policy()
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "contract_status": CONTRACT_STATUS,
        "generated_at": generated_at,
        "purposes": PURPOSES,
        "output_format": "hmac:v1:<purpose>:<digest>",
        "model_schemas": _model_schemas(),
        "policy": asdict(policy),
        "examples": build_examples(),
        "blockers": tuple(asdict(blocker) for blocker in build_blockers()),
        "key_policy_status": key_policy_status(),
        "authority_boundary": AUTHORITY_BOUNDARY,
    }
    payload["machine_proof"] = {
        "hmac_helper_present": True,
        "purpose_binding_required": True,
        "plain_sha256_private_matching_allowed": False,
        "plain_sha256_artifact_integrity_only": True,
        "raw_values_in_read_model": False,
        "normalized_values_in_read_model": False,
        "key_material_exposed": False,
        "test_key_treated_as_production": False,
        "external_action_performed": False,
        "model_call_performed": False,
        "tool_execution_performed": False,
        "credential_handling_performed": False,
        "raw_body_ingestion_performed": False,
        "network_used": False,
        "mac_sync_import_performed": False,
        "mission_control_swift_changed": False,
        "git_push_performed": False,
        "all_live_authority_false": all(value is False for value in AUTHORITY_BOUNDARY.values()),
        "content_hash": None,
    }
    payload["machine_proof"]["content_hash"] = _content_hash(payload)
    return payload


def format_operator_markdown(payload: dict[str, Any]) -> str:
    status = payload["key_policy_status"]
    return "\n".join(
        [
            "# Private Value Hash Policy",
            "",
            "Purpose-bound HMAC match tokens are required for private value matching.",
            "",
            "## Key Policy",
            f"- Protected key ref: `{status['key_env_var_ref']}`",
            f"- Live integration ready: `{str(status['live_integration_ready']).lower()}`",
            "- Key material is never printed or exported.",
            "- Test keys are not production keys.",
            "",
            "## Hash Boundary",
            "- Plain SHA-256 remains allowed for artifact integrity only.",
            "- Plain SHA-256 is blocked for private names, emails, phone numbers, PO references, client labels, and source refs.",
            "- HMAC output format: `hmac:v1:<purpose>:<digest>`.",
            "",
            "## Blocked Uses",
            *[f"- {item}" for item in payload["policy"]["blocked_uses"]],
            "",
            "## Authority",
            "- No secret reveal.",
            "- No production key exposure.",
            "- No credential handling.",
            "- No external action.",
            "",
        ]
    )


def write_exports(payload: dict[str, Any], export_root: Path = DEFAULT_EXPORT_ROOT) -> tuple[Path, Path]:
    export_root.mkdir(parents=True, exist_ok=True)
    json_path = export_root / JSON_EXPORT_NAME
    operator_path = export_root / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(format_operator_markdown(payload), encoding="utf-8")
    return json_path, operator_path


def build_summary(payload: dict[str, Any], json_path: Path, operator_path: Path) -> dict[str, Any]:
    return {
        "read_model_id": payload["read_model_id"],
        "contract_status": payload["contract_status"],
        "json_path": str(json_path),
        "operator_path": str(operator_path),
        "output_format": payload["output_format"],
        "purpose_count": len(payload["purposes"]),
        "live_integration_ready": payload["key_policy_status"]["live_integration_ready"],
        "plain_sha256_private_matching_allowed": payload["machine_proof"]["plain_sha256_private_matching_allowed"],
        "raw_values_in_read_model": payload["machine_proof"]["raw_values_in_read_model"],
        "key_material_exposed": payload["machine_proof"]["key_material_exposed"],
        "all_live_authority_false": payload["machine_proof"]["all_live_authority_false"],
        "content_hash": payload["machine_proof"]["content_hash"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export private value HMAC policy read-model.")
    parser.add_argument("--export-root", type=Path, default=DEFAULT_EXPORT_ROOT)
    parser.add_argument("--generated-at", default=DEFAULT_GENERATED_AT)
    parser.add_argument("--format", choices=("summary", "json"), default="summary")
    args = parser.parse_args(argv)

    payload = build_payload(generated_at=args.generated_at)
    json_path, operator_path = write_exports(payload, args.export_root)
    summary = build_summary(payload, json_path, operator_path)
    print(stable_json(payload if args.format == "json" else summary), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
