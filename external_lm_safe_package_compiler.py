"""External LM safe package compiler v0.

Compiles minimized, tokenized, external-LM-ready packages only when
``external_lm_eligibility_policy`` says the package is safe. This compiler does
not call models, activate providers, access credentials, or execute actions.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping

import external_lm_eligibility_policy
import gate1_operational_snapshot
import machine_intent_candidate_validator
import role_package_gate
import token_vault


DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_GENERATED_AT = "2026-05-26T00:00:00+00:00"

SCHEMA_VERSION = "external_lm_safe_package_compiler_v0"
READ_MODEL_ID = "external_lm_safe_package"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
OPERATOR_EXPORT_NAME = f"{READ_MODEL_ID}_OPERATOR.md"
CONTRACT_STATUS = "EXTERNAL_LM_SAFE_PACKAGE_COMPILER_NO_LIVE_CALLS"

LM1 = "LM1"
LM2 = "LM2"

PACKAGE_COMPILED = "EXTERNAL_LM_SAFE_PACKAGE_COMPILED"
PACKAGE_BLOCKED = "EXTERNAL_LM_SAFE_PACKAGE_BLOCKED"
NO_LM_NEEDED = "NO_LM_NEEDED_DETERMINISTIC_PATH"

SENSITIVITY_LOW = "LOW"
SENSITIVITY_PERSONAL = "PERSONAL"
SENSITIVITY_PERSONAL_FINANCE = "PERSONAL_FINANCE"
SENSITIVITY_CLIENT_FINANCE = "CLIENT_FINANCE"
SENSITIVITY_LEGAL_DISCOVERY = "LEGAL_DISCOVERY"
SENSITIVITY_SENSITIVE = "SENSITIVE"
SENSITIVITY_STRICT_LOCAL_ONLY = "STRICT_LOCAL_ONLY"

TOKEN_VAULT_REF = "generated/read_models/token_vault_status.json"

AUTHORITY_BOUNDARY = {
    "live_lm_call_allowed": False,
    "model_api_integration_allowed": False,
    "network_allowed": False,
    "provider_key_material_access_allowed": False,
    "tool_execution_allowed": False,
    "external_action_allowed": False,
    "send_submit_allowed": False,
    "approval_execution_allowed": False,
    "ledger_posting_allowed": False,
    "production_state_mutation_allowed": False,
    "workbook_body_read_allowed": False,
    "spreadsheet_cell_read_allowed": False,
    "raw_sensitive_value_exposure_allowed": False,
    "credential_handling_allowed": False,
}


@dataclass(frozen=True)
class TokenizedContextPacket:
    context_packet_id: str
    source_request_id: str
    lane: str
    sensitivity_class: str
    privacy_level: str
    data_classes: tuple[str, ...]
    tokenization_required: bool
    tokenization_applied: bool
    tokenization_reason: str
    token_scope: str
    token_vault_ref: str
    minimized_context: dict[str, Any]
    allowed_context_classes: tuple[str, ...]
    forbidden_context_classes: tuple[str, ...]
    omitted_context_summary: tuple[str, ...]
    raw_values_included: bool
    credentials_present: bool
    secrets_present: bool
    detokenization_required_inside_model: bool


@dataclass(frozen=True)
class PackageLeakScanResult:
    scan_id: str
    passed: bool
    forbidden_raw_hits: tuple[str, ...]
    credential_like_hits: tuple[str, ...]
    scanned_field_count: int
    scan_scope: str
    next_safe_move: str


@dataclass(frozen=True)
class ExternalLmSafePackage:
    package_id: str
    source_request_id: str
    lane: str
    model_class_recommended: str
    eligibility_verdict: str
    privacy_level: str
    sensitivity_class: str
    data_classes: tuple[str, ...]
    tokenization_applied: bool
    tokenization_required: bool
    tokenization_reason: str
    raw_values_included: bool
    credentials_present: bool
    secrets_present: bool
    package_minimized: bool
    allowed_context_classes: tuple[str, ...]
    forbidden_context_classes: tuple[str, ...]
    token_scope: str
    token_vault_ref: str
    detokenization_required_inside_model: bool
    estimated_token_count: int
    omitted_context_summary: tuple[str, ...]
    leak_scan_passed: bool
    external_lm_allowed: bool
    local_lm_required: bool
    no_lm_needed: bool
    ready_for_external_shadow: bool
    ready_for_production: bool
    lm_input_payload: dict[str, Any]
    guardian_requirements: tuple[str, ...]
    authority_boundary: dict[str, bool]
    next_safe_move: str


@dataclass(frozen=True)
class ExternalLmPackageProof:
    proof_id: str
    source_request_id: str
    lane: str
    eligibility_result: dict[str, Any]
    tokenized_context_packet: dict[str, Any]
    leak_scan_result: dict[str, Any]
    model_call_performed: bool
    provider_activation_performed: bool
    authority_granted: bool
    production_ready: bool


@dataclass(frozen=True)
class SafePackageCompileResult:
    compile_result_id: str
    source_request_id: str
    lane: str
    package_status: str
    plain_reason: str
    safe_package: dict[str, Any] | None
    blocked_reasons: tuple[str, ...]
    no_lm_needed: bool
    eligibility_result: dict[str, Any] | None
    leak_scan_result: dict[str, Any] | None
    package_proof: dict[str, Any] | None
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


def _norm_lane(lane: str) -> str:
    return LM1 if str(lane).upper() in {"LM1", "LM1_INTENT_PROPOSAL"} else LM2


def _source_request_id(source: Mapping[str, Any]) -> str:
    return str(source.get("source_request_id") or source.get("request_id") or source.get("package_id") or "external_lm_safe_package_fixture")


def _source_text(source: Mapping[str, Any]) -> str:
    return str(
        source.get("user_message")
        or source.get("operator_message")
        or source.get("task")
        or source.get("requested_action")
        or ""
    )


def _contains_any(text: str, terms: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return any(term in lowered for term in terms)


def classify_privacy_context(source: Mapping[str, Any], *, lane: str) -> dict[str, Any]:
    text = _source_text(source)
    lowered = text.lower()
    file_name = str(source.get("file_display_name") or "")
    artifact_kind = str(source.get("artifact_kind") or "")
    world_ref = str(source.get("world_ref") or source.get("current_world_ref") or "").lower()
    client_ref = str(source.get("client_ref") or source.get("target_folder_ref") or "").lower()
    privacy_level = str(source.get("privacy_level") or source.get("privacy_classification") or "").upper()
    strict_private = bool(source.get("strict_private_mode_active", False))
    private_mode = bool(source.get("private_mode_active", False))
    deterministic = bool(source.get("deterministic_result_available", False)) or lowered.strip() in {
        "ping",
        "status light",
        "what time is it?",
    }
    send_or_post = _contains_any(lowered, ("send", "email", "submit", "post", "mark paid", "mark it paid"))
    credential_like = bool(_credential_like_strings(source))
    unsafe_raw_identifier = bool(_regulated_identifier_strings(source))

    if credential_like or unsafe_raw_identifier or strict_private or _contains_any(lowered, ("password", "api key", "secret")):
        sensitivity = SENSITIVITY_STRICT_LOCAL_ONLY
        privacy = "STRICT_PRIVATE_CLIENT_METADATA"
        data_classes = ("STRICT_PRIVATE_CLIENT_METADATA",)
        token_required = True
        token_reason = "Strict/local-only mode, credential-like material, or raw regulated identifiers block external packaging."
    elif client_ref == "personal_finance" or (
        _contains_any(
            lowered,
            ("personal finance", "bank ledger", "transaction", "transactions", "vendor", "payee", "reconciliation", "ledger mapping", "tax"),
        )
        and not _contains_any(lowered + " " + file_name.lower() + " " + artifact_kind.lower(), ("invoice", "workbook", "client finance"))
    ):
        sensitivity = SENSITIVITY_PERSONAL_FINANCE
        privacy = "PERSONAL_FINANCE_METADATA"
        data_classes = ("PERSONAL_FINANCE_METADATA", "MINIMIZED_ROLE_PACKAGE" if lane == LM2 else "MACHINE_INTENT_PROPOSAL_SCHEMA")
        token_required = True
        token_reason = "Personal finance context is tokenized/minimized so strong external reasoning can be used without raw identifiers."
    elif privacy_level in {"CLIENT_FINANCE_FILE_METADATA", "METADATA_ONLY_TOKENIZED_REFS"} or world_ref == "finance" or _contains_any(
        lowered + " " + file_name.lower() + " " + artifact_kind.lower(), ("invoice", "workbook", "hilton", "client finance")
    ):
        sensitivity = SENSITIVITY_CLIENT_FINANCE
        privacy = "CLIENT_FINANCE_FILE_METADATA"
        data_classes = ("CLIENT_FINANCE_FILE_METADATA", "MINIMIZED_ROLE_PACKAGE" if lane == LM2 else "MACHINE_INTENT_PROPOSAL_SCHEMA")
        token_required = True
        token_reason = "Client finance context requires tokenized/minimized package before external LM use."
    elif _contains_any(lowered, ("legal", "discovery", "matter", "privilege", "privileged", "confidential")):
        sensitivity = SENSITIVITY_LEGAL_DISCOVERY
        privacy = "LEGAL_DISCOVERY_METADATA"
        data_classes = ("LEGAL_DISCOVERY_METADATA", "MINIMIZED_ROLE_PACKAGE" if lane == LM2 else "MACHINE_INTENT_PROPOSAL_SCHEMA")
        token_required = True
        token_reason = "Discovery/legal context is matter-scoped, tokenized, and minimized before external LM use."
    elif private_mode or _contains_any(lowered, ("calendar", "schedule", "appointment", "meeting", "personal")):
        sensitivity = SENSITIVITY_PERSONAL
        privacy = "TOKENIZED_METADATA"
        data_classes = ("TOKENIZED_METADATA",)
        token_required = True
        token_reason = "Personal context is minimized and tokenized before external LM use."
    elif _contains_any(lowered, ("health", "medical", "private note", "private notes", "sensitive")):
        sensitivity = SENSITIVITY_SENSITIVE
        privacy = "SENSITIVE_METADATA"
        data_classes = ("SENSITIVE_METADATA", "MINIMIZED_ROLE_PACKAGE" if lane == LM2 else "MACHINE_INTENT_PROPOSAL_SCHEMA")
        token_required = True
        token_reason = "Sensitive context is tokenized/minimized before any external LM package can be prepared."
    else:
        sensitivity = SENSITIVITY_LOW
        privacy = "LOW_METADATA"
        data_classes = ("LOW_METADATA",)
        token_required = False
        token_reason = "Low-sensitivity metadata does not require tokenization by default."

    return {
        "sensitivity_class": sensitivity,
        "privacy_level": privacy,
        "data_classes": tuple(dict.fromkeys(data_classes)),
        "tokenization_required": token_required,
        "tokenization_reason": token_reason,
        "private_mode_active": private_mode,
        "strict_private_mode_active": strict_private,
        "external_action_requested": send_or_post,
        "no_lm_needed": deterministic,
        "credentials_or_secrets_present": credential_like or unsafe_raw_identifier,
    }


def _minimized_user_message(source: Mapping[str, Any], classification: Mapping[str, Any]) -> str:
    text = _source_text(source)
    sensitivity = str(classification["sensitivity_class"])
    if sensitivity == SENSITIVITY_LOW:
        return text
    if sensitivity == SENSITIVITY_PERSONAL:
        return "Operator asked about a personal schedule item; raw names, locations, and exact private details are omitted."
    if sensitivity == SENSITIVITY_PERSONAL_FINANCE:
        return "Operator asked about a personal finance or bank ledger workflow; payees/vendors are token refs and raw account/tax identifiers are omitted."
    if sensitivity == SENSITIVITY_CLIENT_FINANCE:
        if classification.get("external_action_requested"):
            return "Operator asked about an invoice-related external action; prepare approval-safe response only."
        return "Operator asked about a client finance invoice/workbook workflow; use tokenized/minimized context only."
    if sensitivity == SENSITIVITY_LEGAL_DISCOVERY:
        return "Operator asked about a legal/discovery workflow; matter-scoped entity tokens and confidentiality markers preserve reasoning structure without raw identities."
    if sensitivity == SENSITIVITY_SENSITIVE:
        return "Operator asked about sensitive material; raw private notes and identifiers are omitted from the model package."
    return "Operator asked about strict/private material; external package is blocked."


def _token_scope(source: Mapping[str, Any], classification: Mapping[str, Any]) -> str:
    world = str(source.get("world_ref") or source.get("current_world_ref") or "general").lower().replace(" ", "_")
    client = str(source.get("client_ref") or source.get("target_folder_ref") or "general").lower().replace(" ", "_")
    if classification["tokenization_required"] and client:
        client = f"client_{_short_hash(client)}"
    sensitivity = str(classification["sensitivity_class"]).lower()
    return f"scope:{world}:{client}:{sensitivity}:{_short_hash(_source_request_id(source))}"


def _minimized_ref(value: object, *, prefix: str, token_required: bool, token_scope: str) -> str:
    raw = str(value or "unknown")
    if token_required and raw not in {"", "unknown"}:
        return f"{prefix}_token:{_short_hash(token_scope, raw)}"
    return raw


def _omitted_context(source: Mapping[str, Any], classification: Mapping[str, Any]) -> tuple[str, ...]:
    omitted = [
        "raw workbook/body/cell contents",
        "credentials/secrets",
        "bank account/routing/tax/SSN/EIN identifiers",
        "unnecessary raw addresses/contact info/private notes",
        "detokenized private values",
    ]
    if classification["sensitivity_class"] == SENSITIVITY_LEGAL_DISCOVERY:
        omitted.append("privileged raw document bodies")
    if classification["tokenization_required"]:
        omitted.append("raw operator text where it could expose private/client details")
    if classification["external_action_requested"]:
        omitted.append("send/submit/post execution authority")
    return tuple(dict.fromkeys(omitted))


def _allowed_context_classes(lane: str, classification: Mapping[str, Any]) -> tuple[str, ...]:
    classes = ["minimized_request_summary", "privacy_policy_result", "tokenization_declaration"]
    if lane == LM1:
        classes.append("machine_intent_candidate_schema")
    else:
        classes.extend(("role_execution_package_summary", "guardian_requirements", "role_response_candidate_schema"))
    if classification["sensitivity_class"] == SENSITIVITY_LOW:
        classes.append("low_sensitivity_user_message")
    return tuple(dict.fromkeys(classes))


def _forbidden_context_classes(classification: Mapping[str, Any]) -> tuple[str, ...]:
    forbidden = [
        "raw workbook body",
        "spreadsheet cell values",
        "credentials",
        "secrets",
        "bank account numbers",
        "routing numbers",
        "tax IDs",
        "SSNs/EINs",
        "unnecessary raw addresses/contact info/private notes",
        "detokenized private values",
        "unrelated client data",
    ]
    if classification["external_action_requested"]:
        forbidden.append("external action execution authority")
    return tuple(dict.fromkeys(forbidden))


def _tokenized_context_packet(source: Mapping[str, Any], *, lane: str, classification: Mapping[str, Any]) -> dict[str, Any]:
    source_request_id = _source_request_id(source)
    token_required = bool(classification["tokenization_required"])
    token_scope = _token_scope(source, classification)
    minimized_context = {
        "source_request_id": source_request_id,
        "minimized_user_message": _minimized_user_message(source, classification),
        "world_ref": str(source.get("world_ref") or source.get("current_world_ref") or "unknown"),
        "client_ref": _minimized_ref(
            source.get("client_ref") or source.get("target_folder_ref"),
            prefix="client_ref",
            token_required=token_required,
            token_scope=token_scope,
        ),
        "workflow_ref": _minimized_ref(
            source.get("workflow_ref") or source.get("target_workflow_ref"),
            prefix="workflow_ref",
            token_required=token_required,
            token_scope=token_scope,
        ),
        "artifact_kind": str(source.get("artifact_kind") or ""),
        "file_display_name_present": bool(source.get("file_display_name")),
        "external_action_requested": bool(classification["external_action_requested"]),
    }
    packet = TokenizedContextPacket(
        context_packet_id=f"tokenized_context_packet:{_short_hash(source_request_id, lane, classification['privacy_level'])}",
        source_request_id=source_request_id,
        lane=lane,
        sensitivity_class=str(classification["sensitivity_class"]),
        privacy_level=str(classification["privacy_level"]),
        data_classes=tuple(classification["data_classes"]),
        tokenization_required=token_required,
        tokenization_applied=token_required,
        tokenization_reason=str(classification["tokenization_reason"]),
        token_scope=token_scope,
        token_vault_ref=TOKEN_VAULT_REF,
        minimized_context=minimized_context,
        allowed_context_classes=_allowed_context_classes(lane, classification),
        forbidden_context_classes=_forbidden_context_classes(classification),
        omitted_context_summary=_omitted_context(source, classification),
        raw_values_included=False,
        credentials_present=bool(classification["credentials_or_secrets_present"]),
        secrets_present=bool(classification["credentials_or_secrets_present"]),
        detokenization_required_inside_model=False,
    )
    return asdict(packet)


def _iter_strings(value: Any) -> tuple[str, ...]:
    found: list[str] = []
    if isinstance(value, str):
        found.append(value)
    elif isinstance(value, Mapping):
        for item in value.values():
            found.extend(_iter_strings(item))
    elif isinstance(value, (list, tuple, set)):
        for item in value:
            found.extend(_iter_strings(item))
    return tuple(found)


def _credential_like_strings(value: Any) -> tuple[str, ...]:
    hits: list[str] = []
    patterns = (
        re.compile(r"\bsk-[A-Za-z0-9_-]{8,}\b"),
        re.compile(r"\b(?:api[_-]?key|password|secret|credential)\s*[:=]\s*\S+", re.IGNORECASE),
        re.compile(r"\b[A-Za-z0-9_]*(?:SECRET|TOKEN|PASSWORD|API_KEY)[A-Za-z0-9_]*\s*=\s*\S+"),
    )
    for text in _iter_strings(value):
        for pattern in patterns:
            if pattern.search(text):
                hits.append("credential_like_value")
                break
    return tuple(dict.fromkeys(hits))


def _regulated_identifier_strings(value: Any) -> tuple[str, ...]:
    hits: list[str] = []
    patterns = (
        re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
        re.compile(r"\b\d{2}-\d{7}\b"),
        re.compile(r"\b(?:account|acct|routing|tax id|ssn|ein)\s*(?:number|no\.|#|id)?\s*[:=]?\s*\d{4,}\b", re.IGNORECASE),
    )
    for text in _iter_strings(value):
        for pattern in patterns:
            if pattern.search(text):
                hits.append("regulated_identifier_like_value")
                break
    return tuple(dict.fromkeys(hits))


def scan_package_for_leaks(payload: Mapping[str, Any], *, scan_scope: str = "external_lm_safe_package") -> dict[str, Any]:
    raw_fixture_hits: list[str] = []
    text_values = _iter_strings(payload)
    for raw in token_vault.SYNTHETIC_VALUES.values():
        if any(raw in text for text in text_values):
            raw_fixture_hits.append(f"raw_fixture:{token_vault._kind_for_value(raw)}")
    credential_hits = [*_credential_like_strings(payload), *_regulated_identifier_strings(payload)]
    passed = not raw_fixture_hits and not credential_hits
    result = PackageLeakScanResult(
        scan_id=f"package_leak_scan:{_short_hash(scan_scope, tuple(raw_fixture_hits), tuple(credential_hits))}",
        passed=passed,
        forbidden_raw_hits=tuple(dict.fromkeys(raw_fixture_hits)),
        credential_like_hits=tuple(dict.fromkeys(credential_hits)),
        scanned_field_count=len(text_values),
        scan_scope=scan_scope,
        next_safe_move=(
            "Package leak scan passed; continue to eligibility-gated shadow readiness."
            if passed
            else "Block external package compile and remove raw/credential-like values."
        ),
    )
    return asdict(result)


def _eligibility_input(packet: Mapping[str, Any], *, lane: str, classification: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "recommended_lane": lane,
        "privacy_level": packet["privacy_level"],
        "data_classes": packet["data_classes"],
        "tokenization_applied": packet["tokenization_applied"],
        "raw_values_included": False,
        "package_minimized": True,
        "context_minimization_applied": True,
        "privacy_policy_allows_external_model": True,
        "model_allowed_for_data_classes": True,
        "detokenization_required_inside_model": False,
        "guardian_privacy_gate_required": True,
        "strict_private_mode_active": bool(classification["strict_private_mode_active"]),
        "private_mode_active": False,
        "credentials_or_secrets_present": bool(classification["credentials_or_secrets_present"]),
    }


def _safe_universal_intake(source: Mapping[str, Any], packet: Mapping[str, Any]) -> dict[str, Any]:
    intake = source.get("universal_intake_inference")
    if not isinstance(intake, Mapping):
        return {}
    if not packet["tokenization_required"]:
        return dict(intake)
    return {
        "candidate_present": True,
        "world_ref": packet["minimized_context"]["world_ref"],
        "client_ref": packet["minimized_context"]["client_ref"],
        "workflow_ref": packet["minimized_context"]["workflow_ref"],
        "artifact_kind": intake.get("artifact_kind") or packet["minimized_context"]["artifact_kind"],
        "proposed_facts_only": bool(intake.get("proposed_facts_only", True)),
        "raw_values_included": False,
    }


def _lm1_payload(source: Mapping[str, Any], packet: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "source_request_id": packet["source_request_id"],
        "user_message": packet["minimized_context"]["minimized_user_message"],
        "current_world_ref": packet["minimized_context"]["world_ref"],
        "current_thread_ref": _minimized_ref(
            source.get("thread_ref") or f"thread_ref:{packet['minimized_context']['world_ref']}",
            prefix="thread_ref",
            token_required=bool(packet["tokenization_required"]),
            token_scope=str(packet["token_scope"]),
        ),
        "universal_intake_inference": _safe_universal_intake(source, packet),
        "allowed_context_classes": packet["allowed_context_classes"],
        "forbidden_context_classes": packet["forbidden_context_classes"],
        "output_schema": tuple(machine_intent_candidate_validator.MachineIntentCandidate.__dataclass_fields__),
        "tools_allowed": (),
        "authority_granted": {
            "tool_execution": False,
            "external_action": False,
            "send_submit": False,
            "workflow_execution": False,
        },
    }


def _lm2_payload(source: Mapping[str, Any], packet: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "source_request_id": packet["source_request_id"],
        "role_execution_package": {
            "package_id": source.get("package_id"),
            "role_identity": source.get("role_identity") or source.get("actor_label") or "OPENCLAW_SYSTEM",
            "actor_label": source.get("actor_label") or source.get("role_identity") or "OpenClaw",
            "task": packet["minimized_context"]["minimized_user_message"],
            "client_ref": packet["minimized_context"]["client_ref"],
            "workflow_ref": packet["minimized_context"]["workflow_ref"],
            "context_packet": {
                "allowed_context_refs": tuple((source.get("context_packet") or {}).get("allowed_context_refs", ())),
                "forbidden_context_refs": packet["forbidden_context_classes"],
                "raw_body_allowed": False,
                "credential_material_allowed": False,
            },
            "tool_policy": source.get("tool_policy") or {"allowed_tools": (), "forbidden_tools": role_package_gate.FORBIDDEN_TOOLS},
            "authority_policy": source.get("authority_policy")
            or {
                "tool_authority_granted": False,
                "external_action_authority_granted": False,
                "send_submit_authority_granted": False,
            },
            "output_destination": source.get("output_destination") or {},
        },
        "allowed_context_classes": packet["allowed_context_classes"],
        "forbidden_context_classes": packet["forbidden_context_classes"],
        "guardian_requirements": (
            "validate_role_response_candidate",
            "block_sent_submitted_paid_posted_claims_without_receipts",
            "block_detokenization_inside_model",
        ),
        "output_schema": (
            "source_request_id",
            "headline",
            "one_line_answer",
            "eliwinship",
            "next_action",
            "readback_files",
        ),
        "tools_allowed": (),
        "authority_granted": {
            "tool_execution": False,
            "external_action": False,
            "send_submit": False,
            "workflow_execution": False,
            "ledger_posting": False,
        },
    }


def _plain_block_reason(result: Mapping[str, Any] | None, leak_scan: Mapping[str, Any] | None, source_block: tuple[str, ...]) -> str:
    if source_block:
        return "OpenClaw could not prepare this for an external model because private or credential-like content was present."
    if leak_scan and not leak_scan.get("passed"):
        return "OpenClaw blocked the package because it still contained raw or credential-like values."
    if result and result.get("no_safe_model"):
        return "OpenClaw found no safe model package for this request."
    if result and result.get("local_lm_required"):
        return "OpenClaw must keep this package local under the current privacy policy."
    return "OpenClaw could not prove this package is safe for an external model."


def compile_external_lm_safe_package(
    source: Mapping[str, Any] | None = None,
    *,
    lane: str = LM1,
    eligibility_result: Mapping[str, Any] | None = None,
    require_existing_eligibility: bool = False,
) -> dict[str, Any]:
    source = dict(source or {})
    lane = _norm_lane(lane)
    source_request_id = _source_request_id(source)
    classification = classify_privacy_context(source, lane=lane)

    if classification["no_lm_needed"]:
        return asdict(
            SafePackageCompileResult(
                compile_result_id=f"safe_package_compile:{_short_hash(source_request_id, lane, NO_LM_NEEDED)}",
                source_request_id=source_request_id,
                lane=lane,
                package_status=NO_LM_NEEDED,
                plain_reason="OpenClaw can handle this with deterministic local logic; no model package is needed.",
                safe_package=None,
                blocked_reasons=(),
                no_lm_needed=True,
                eligibility_result=None,
                leak_scan_result=None,
                package_proof=None,
                authority_boundary=dict(AUTHORITY_BOUNDARY),
                next_safe_move="Use deterministic handling; do not call a model.",
            )
        )

    packet = _tokenized_context_packet(source, lane=lane, classification=classification)
    if require_existing_eligibility and eligibility_result is None:
        blocked = ("MISSING_EXTERNAL_LM_ELIGIBILITY_RESULT",)
        return asdict(
            SafePackageCompileResult(
                compile_result_id=f"safe_package_compile:{_short_hash(source_request_id, lane, blocked)}",
                source_request_id=source_request_id,
                lane=lane,
                package_status=PACKAGE_BLOCKED,
                plain_reason="OpenClaw cannot prepare this for an external model until eligibility proof exists.",
                safe_package=None,
                blocked_reasons=blocked,
                no_lm_needed=False,
                eligibility_result=None,
                leak_scan_result=None,
                package_proof=None,
                authority_boundary=dict(AUTHORITY_BOUNDARY),
                next_safe_move="Run external LM eligibility policy first; do not call a model.",
            )
        )

    source_leak_scan = scan_package_for_leaks(source, scan_scope=f"{lane}:source_input")
    eligibility = dict(
        eligibility_result
        or external_lm_eligibility_policy.evaluate_external_lm_eligibility(
            _eligibility_input(packet, lane=lane, classification=classification),
            lane=lane,
        )
    )
    payload = _lm1_payload(source, packet) if lane == LM1 else _lm2_payload(source, packet)
    safe_package = ExternalLmSafePackage(
        package_id=f"external_lm_safe_package:{_short_hash(source_request_id, lane, eligibility.get('eligibility_id'))}",
        source_request_id=source_request_id,
        lane=lane,
        model_class_recommended=str(eligibility.get("recommended_model_class") or external_lm_eligibility_policy.NO_SAFE_MODEL),
        eligibility_verdict="EXTERNAL_ALLOWED" if eligibility.get("external_lm_allowed") else "EXTERNAL_BLOCKED",
        privacy_level=str(packet["privacy_level"]),
        sensitivity_class=str(packet["sensitivity_class"]),
        data_classes=tuple(packet["data_classes"]),
        tokenization_applied=bool(packet["tokenization_applied"]),
        tokenization_required=bool(packet["tokenization_required"]),
        tokenization_reason=str(packet["tokenization_reason"]),
        raw_values_included=False,
        credentials_present=bool(packet["credentials_present"]),
        secrets_present=bool(packet["secrets_present"]),
        package_minimized=True,
        allowed_context_classes=tuple(packet["allowed_context_classes"]),
        forbidden_context_classes=tuple(packet["forbidden_context_classes"]),
        token_scope=str(packet["token_scope"]),
        token_vault_ref=str(packet["token_vault_ref"]),
        detokenization_required_inside_model=False,
        estimated_token_count=int(eligibility.get("package_token_estimate") or 0),
        omitted_context_summary=tuple(packet["omitted_context_summary"]),
        leak_scan_passed=False,
        external_lm_allowed=bool(eligibility.get("external_lm_allowed")),
        local_lm_required=bool(eligibility.get("local_lm_required")),
        no_lm_needed=False,
        ready_for_external_shadow=False,
        ready_for_production=False,
        lm_input_payload=payload,
        guardian_requirements=tuple(payload.get("guardian_requirements", ("validate_model_output", "block_unauthorized_action_claims"))),
        authority_boundary=dict(AUTHORITY_BOUNDARY),
        next_safe_move="Use this only as a future external shadow/test package; production live LM remains off.",
    )
    safe_package_dict = asdict(safe_package)
    package_leak_scan = scan_package_for_leaks(safe_package_dict, scan_scope=f"{lane}:compiled_package")
    safe_package_dict["leak_scan_passed"] = bool(package_leak_scan["passed"])
    safe_package_dict["ready_for_external_shadow"] = (
        bool(eligibility.get("external_lm_allowed")) and bool(package_leak_scan["passed"]) and bool(source_leak_scan["passed"])
    )

    blocked_reasons: list[str] = []
    if not source_leak_scan["passed"]:
        blocked_reasons.append("SOURCE_LEAK_SCAN_FAILED")
    if not package_leak_scan["passed"]:
        blocked_reasons.append("PACKAGE_LEAK_SCAN_FAILED")
    if not eligibility.get("external_lm_allowed"):
        blocked_reasons.extend(str(code) for code in eligibility.get("reason_codes", ()) if "BLOCK" in str(code) or "REQUIRED" in str(code))
        if not blocked_reasons:
            blocked_reasons.append("EXTERNAL_LM_ELIGIBILITY_BLOCKED")

    proof = ExternalLmPackageProof(
        proof_id=f"external_lm_package_proof:{_short_hash(source_request_id, lane, tuple(blocked_reasons))}",
        source_request_id=source_request_id,
        lane=lane,
        eligibility_result=eligibility,
        tokenized_context_packet=packet,
        leak_scan_result=package_leak_scan,
        model_call_performed=False,
        provider_activation_performed=False,
        authority_granted=False,
        production_ready=False,
    )
    status = PACKAGE_COMPILED if safe_package_dict["ready_for_external_shadow"] else PACKAGE_BLOCKED
    return asdict(
        SafePackageCompileResult(
            compile_result_id=f"safe_package_compile:{_short_hash(source_request_id, lane, status)}",
            source_request_id=source_request_id,
            lane=lane,
            package_status=status,
            plain_reason=(
                "OpenClaw prepared a minimized, tokenized package that is eligible for future external shadow testing."
                if status == PACKAGE_COMPILED
                else _plain_block_reason(eligibility, package_leak_scan, tuple(blocked_reasons))
            ),
            safe_package=safe_package_dict if status == PACKAGE_COMPILED else None,
            blocked_reasons=tuple(dict.fromkeys(blocked_reasons)),
            no_lm_needed=False,
            eligibility_result=eligibility,
            leak_scan_result=package_leak_scan,
            package_proof=asdict(proof),
            authority_boundary=dict(AUTHORITY_BOUNDARY),
            next_safe_move=(
                "Record package proof and keep live LM off until provider and live enablement receipts exist."
                if status == PACKAGE_COMPILED
                else "Use local/deterministic handling or remove the privacy blocker before external LM packaging."
            ),
        )
    )


def compile_lm1_safe_package(source: Mapping[str, Any] | None = None, **kwargs: Any) -> dict[str, Any]:
    return compile_external_lm_safe_package(source, lane=LM1, **kwargs)


def compile_lm2_safe_package(role_package: Mapping[str, Any] | None = None, **kwargs: Any) -> dict[str, Any]:
    return compile_external_lm_safe_package(role_package, lane=LM2, **kwargs)


def _lm2_fixture_package() -> dict[str, Any]:
    return {
        "source_request_id": "external_lm_safe_lm2_fixture",
        "package_id": "role_package:external_lm_safe_lm2_fixture",
        "role_identity": "CASSANDRA_CLARA",
        "actor_label": "Cassandra/Clara",
        "task": "Draft client-safe invoice package wording for Capital Hilton; do not send.",
        "world_ref": "finance",
        "client_ref": "capital_hilton",
        "workflow_ref": "capital_hilton_invoice_workflow",
        "privacy_level": "CLIENT_FINANCE_FILE_METADATA",
        "tokenization_applied": True,
        "raw_values_included": False,
        "tool_policy": {"allowed_tools": (), "forbidden_tools": role_package_gate.FORBIDDEN_TOOLS},
        "authority_policy": {
            "tool_authority_granted": False,
            "external_action_authority_granted": False,
            "send_submit_authority_granted": False,
        },
    }


def build_payload(*, generated_at: str | None = None) -> dict[str, Any]:
    generated_at = generated_at or DEFAULT_GENERATED_AT
    lm1_finance = compile_lm1_safe_package(
        {
            "source_request_id": "external_lm_safe_lm1_finance_fixture",
            "user_message": "what's next for the Capital Hilton invoice?",
            "world_ref": "finance",
            "client_ref": "capital_hilton",
            "workflow_ref": "capital_hilton_invoice_workflow",
            "file_display_name": "Invoice Capitol Hilton Running.xlsx",
            "file_type": "spreadsheet",
            "artifact_kind": "running_invoice_workbook",
        }
    )
    lm2_finance = compile_lm2_safe_package(_lm2_fixture_package())
    low_weather = compile_lm1_safe_package(
        {
            "source_request_id": "external_lm_safe_weather_fixture",
            "user_message": "What's the weather pattern generally?",
            "world_ref": "general",
        }
    )
    personal_calendar = compile_lm1_safe_package(
        {
            "source_request_id": "external_lm_safe_calendar_fixture",
            "user_message": "What is on my calendar tomorrow?",
            "world_ref": "personal",
        }
    )
    personal_finance = compile_lm2_safe_package(
        {
            "source_request_id": "external_lm_safe_personal_finance_fixture",
            "task": "Reconcile bank ledger metadata, transaction dates, amounts, vendor/payee tokens, categories, and proposed ledger mappings.",
            "world_ref": "finance",
            "client_ref": "personal_finance",
            "workflow_ref": "personal_finance_reconciliation",
        }
    )
    legal_discovery = compile_lm2_safe_package(
        {
            "source_request_id": "external_lm_safe_legal_discovery_fixture",
            "task": "Summarize discovery matter metadata with privilege and confidentiality markers; raw identities are tokenized.",
            "world_ref": "legal",
            "client_ref": "matter_alpha",
            "workflow_ref": "matter_scoped_discovery",
        }
    )
    deterministic = compile_lm1_safe_package(
        {
            "source_request_id": "external_lm_safe_no_lm_fixture",
            "user_message": "ping",
            "deterministic_result_available": True,
        }
    )
    strict_block = compile_lm1_safe_package(
        {
            "source_request_id": "external_lm_safe_strict_fixture",
            "user_message": "This has legal/private bank tax material.",
            "strict_private_mode_active": True,
        }
    )
    raw_block = compile_lm1_safe_package(
        {
            "source_request_id": "external_lm_safe_raw_block_fixture",
            "user_message": token_vault.SYNTHETIC_VALUES["email"],
            "world_ref": "finance",
            "client_ref": "capital_hilton",
        }
    )
    raw_identifier_block = compile_lm1_safe_package(
        {
            "source_request_id": "external_lm_safe_raw_identifier_block_fixture",
            "user_message": "Reconcile account number 1234567890 and routing 021000021.",
            "world_ref": "finance",
        }
    )
    send_request = compile_lm2_safe_package(
        {
            **_lm2_fixture_package(),
            "source_request_id": "external_lm_safe_send_fixture",
            "task": "Send the invoice now.",
        }
    )
    examples = {
        "lm1_client_finance": lm1_finance,
        "lm2_client_finance": lm2_finance,
        "low_sensitivity_weather": low_weather,
        "personal_calendar": personal_calendar,
        "personal_finance": personal_finance,
        "legal_discovery": legal_discovery,
        "deterministic_no_lm_needed": deterministic,
        "strict_private_block": strict_block,
        "raw_value_block": raw_block,
        "raw_identifier_block": raw_identifier_block,
        "send_request_no_authority": send_request,
    }
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "contract_status": CONTRACT_STATUS,
        "generated_at": generated_at,
        "examples": examples,
        "connects_to_chain": {
            "gate_1": "Consumes Gate 1-shaped request snapshots and minimized intake metadata.",
            "lm1": "Compiles LM1 external package only after eligibility passes.",
            "gate_3": "Consumes Gate 3 RoleExecutionPackage-shaped data for LM2.",
            "lm2": "Compiles LM2 external package only after eligibility passes.",
            "gate_4": "Carries Guardian requirements; output validation is still mandatory.",
        },
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "machine_proof": {
            "compiler_present": True,
            "lm1_safe_package_compiled": lm1_finance["package_status"] == PACKAGE_COMPILED,
            "lm2_safe_package_compiled": lm2_finance["package_status"] == PACKAGE_COMPILED,
            "low_sensitivity_tokenization_not_required": (
                (low_weather.get("safe_package") or {}).get("tokenization_required") is False
            ),
            "personal_context_tokenized": (personal_calendar.get("safe_package") or {}).get("tokenization_required") is True,
            "personal_finance_external_ready": personal_finance["package_status"] == PACKAGE_COMPILED,
            "legal_discovery_external_ready": legal_discovery["package_status"] == PACKAGE_COMPILED,
            "deterministic_no_lm_needed": deterministic["no_lm_needed"] is True,
            "strict_private_external_blocked": strict_block["package_status"] == PACKAGE_BLOCKED,
            "raw_value_leak_blocked": raw_block["package_status"] == PACKAGE_BLOCKED,
            "raw_identifier_leak_blocked": raw_identifier_block["package_status"] == PACKAGE_BLOCKED,
            "send_request_grants_no_authority": all(
                value is False for value in ((send_request.get("safe_package") or {}).get("authority_boundary") or {}).values()
            ),
            "model_call_performed": False,
            "provider_activation_performed": False,
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
    proof = payload.get("machine_proof", {})
    lines = [
        "# External LM Safe Package Compiler",
        "",
        f"Status: {CONTRACT_STATUS}",
        f"LM1 safe package: {str(proof.get('lm1_safe_package_compiled')).lower()}",
        f"LM2 safe package: {str(proof.get('lm2_safe_package_compiled')).lower()}",
        f"Raw value leak blocked: {str(proof.get('raw_value_leak_blocked')).lower()}",
        f"No-LM deterministic path: {str(proof.get('deterministic_no_lm_needed')).lower()}",
        "",
        "This compiler prepares minimized package proof only. It does not call models, activate providers, or grant authority.",
    ]
    operator_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return json_path, operator_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export external LM safe package compiler read-model.")
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
                    "lm1_safe_package_compiled": payload["machine_proof"]["lm1_safe_package_compiled"],
                    "lm2_safe_package_compiled": payload["machine_proof"]["lm2_safe_package_compiled"],
                    "all_live_authority_false": payload["machine_proof"]["all_live_authority_false"],
                }
            ),
            end="",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
