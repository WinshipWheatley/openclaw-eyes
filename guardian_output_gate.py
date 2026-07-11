"""Guardian output gate v0.

One deterministic output gate for role/model/worker output candidates. It
validates what a role is allowed to say or request before OpenClaw treats the
output as publishable or actionable.

This module does not call models, dispatch agents/workers, execute workflows,
send email, access external systems, read bodies, mutate files, or grant
authority.
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

SCHEMA_VERSION = "guardian_output_gate_v0"
READ_MODEL_ID = "guardian_output_gate"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
OPERATOR_EXPORT_NAME = f"{READ_MODEL_ID}_OPERATOR.md"
CONTRACT_STATUS = "DETERMINISTIC_GUARDIAN_OUTPUT_GATE_NO_EXECUTION"

VALIDATED = "ROLE_OUTPUT_VALIDATED"
BLOCKED_AUTHORITY = "ROLE_OUTPUT_BLOCKED_BY_AUTHORITY"
BLOCKED_FORBIDDEN_CLAIM = "ROLE_OUTPUT_BLOCKED_BY_FORBIDDEN_CLAIM"
BLOCKED_FORBIDDEN_TOOL = "ROLE_OUTPUT_BLOCKED_BY_FORBIDDEN_TOOL"
BLOCKED_SCOPE = "ROLE_OUTPUT_BLOCKED_BY_SCOPE"
BLOCKED_LEAKAGE = "ROLE_OUTPUT_BLOCKED_BY_LEAKAGE"
UNKNOWN_FAIL_CLOSED = "UNKNOWN_FAIL_CLOSED"
LAST_RESORT_BLOCKED_RESPONSE = "GUARDIAN_LAST_RESORT_BLOCKED_RESPONSE"

PUBLICATION_DENIAL_HEADLINE = "Guardian held this reply"
PUBLICATION_DENIAL_MESSAGE = (
    "Guardian held this reply before publication. Nothing was sent, changed, or executed. "
    "Ask me to retry or show the gate reason."
)

VERDICTS = (
    VALIDATED,
    BLOCKED_AUTHORITY,
    BLOCKED_FORBIDDEN_CLAIM,
    BLOCKED_FORBIDDEN_TOOL,
    BLOCKED_SCOPE,
    BLOCKED_LEAKAGE,
    UNKNOWN_FAIL_CLOSED,
)

AUTHORITY_BOUNDARY = {
    "live_model_call_allowed": False,
    "live_agent_dispatch_allowed": False,
    "live_worker_dispatch_allowed": False,
    "live_workflow_execution_allowed": False,
    "live_external_action_allowed": False,
    "live_send_submit_allowed": False,
    "live_approval_execution_allowed": False,
    "live_file_body_read_allowed": False,
    "live_workbook_body_read_allowed": False,
    "live_spreadsheet_cell_read_allowed": False,
    "live_file_mutation_allowed": False,
    "live_pdf_generation_allowed": False,
    "live_browser_allowed": False,
    "live_coupa_access_allowed": False,
    "live_email_send_allowed": False,
    "credential_handling_allowed": False,
    "raw_body_ingestion_allowed": False,
    "network_allowed": False,
}

FORBIDDEN_ACTIONS = (
    "send",
    "submit",
    "email_send",
    "gmail_send",
    "coupa_access",
    "coupa_submit",
    "browser",
    "network",
    "credential_handling",
    "raw_body_read",
    "file_body_read",
    "workbook_body_read",
    "spreadsheet_cell_read",
    "file_mutation",
    "pdf_generation",
    "ledger_posting",
    "workflow_execution",
    "agent_dispatch",
    "worker_dispatch",
)

COMPLETION_CLAIMS = (
    "sent",
    "submitted",
    "posted",
    "paid",
    "completed",
    "approved",
    "authorized",
    "dispatched",
    "emailed",
    "removed",
    "replaced",
    "deleted",
    "retired",
    "updated",
)

PROOF_BACKED_LOCAL_CLAIMS = (
    "completed",
    "updated",
)

APPROVAL_EXECUTION_CLAIMS = (
    "approved",
    "authorized",
)

LEAKAGE_PATTERNS = (
    "password=",
    "password:",
    "credential value",
    "actual credential",
    "actual secret",
    "secret=",
    "api_key=",
    "token=",
    "oauth_token",
    "private_key:",
    "client_secret=",
    "raw private body",
    "base64",
    "cookie",
    "/mnt/",
    "/home/",
    "/users/",
    "c:\\",
    "sha256:",
)
LEAKAGE_REGEX_PATTERNS = (
    (
        "api key",
        re.compile(r"\bapi[_ -]?key\b\s*(?:=|:|\s+)(?!ref(?:erence)?\b|missing\b|not\s+provided\b)[a-z0-9_\-]{8,}", re.IGNORECASE),
    ),
    ("bearer token", re.compile(r"\bbearer\s+[a-z0-9._~+/=-]{16,}", re.IGNORECASE)),
    ("authorization", re.compile(r"\bauthorization:\s*(?:bearer\s+)?[a-z0-9._~+/=-]{16,}", re.IGNORECASE)),
    ("jwt", re.compile(r"\b(?:jwt\s+)?eyj[a-z0-9_-]{8,}(?:\.[a-z0-9_-]+){0,2}", re.IGNORECASE)),
    ("private_key", re.compile(r"\bprivate_key\s*[:=]\s*\S+", re.IGNORECASE)),
    ("client_secret", re.compile(r"\bclient_secret\s*[:=]\s*\S+", re.IGNORECASE)),
)

NEGATION_CUES = (
    "no",
    "not",
    "nothing",
    "never",
    "neither",
    "nor",
    "cannot",
    "cant",
    "can't",
    "dont",
    "don't",
    "doesnt",
    "doesn't",
    "didnt",
    "didn't",
    "hasnt",
    "hasn't",
    "havent",
    "haven't",
    "hadnt",
    "hadn't",
    "isnt",
    "isn't",
    "arent",
    "aren't",
    "wasnt",
    "wasn't",
    "werent",
    "weren't",
    "wont",
    "won't",
    "without",
    "blocked",
    "missing",
    "unproven",
)
HEDGING_CUES = (
    "conditional",
    "contingent",
    "pending",
    "subject",
    "unconfirmed",
    "unverified",
)

_CLAUSE_BOUNDARY_RE = re.compile(
    r"[.;!?\n]+|\b(?:but|however|though|although|nevertheless)\b|\b(?:and|or)\s+(?:i|we|he|she|they|it|the|this|that|a|an)\b",
    re.IGNORECASE,
)
_NEGATION_TOKEN_RE = re.compile(r"[a-z0-9]+(?:'[a-z0-9]+)?")


@dataclass(frozen=True)
class RoleExecutionPackage:
    package_id: str
    source_request_id: str
    source_intent_ref: str
    role: str
    model_backend: str
    device_response_target: str
    workflow_ref: str
    client_ref: str
    allowed_tools: tuple[str, ...]
    allowed_actions: tuple[str, ...]
    forbidden_actions: tuple[str, ...]
    proof_refs: tuple[str, ...]
    authority_boundary: dict[str, bool]
    output_contract: tuple[str, ...]
    validation_required: bool
    next_safe_move: str


@dataclass(frozen=True)
class RoleResponseCandidate:
    candidate_id: str
    source_package_id: str
    source_request_id: str
    response_author: str
    target_device_ref: str
    target_thread_ref: str
    headline: str
    one_line_answer: str
    eliwinship: str
    next_action: str
    requested_tool_calls: tuple[str, ...]
    requested_external_actions: tuple[str, ...]
    completion_claims: tuple[str, ...]
    proof_refs: tuple[str, ...]
    authority_requested: dict[str, bool]
    raw_output_text: str
    next_safe_move: str


@dataclass(frozen=True)
class RoleOutputValidationResult:
    validation_result_id: str
    verdict: str
    source_package_id: str
    source_candidate_id: str
    response_author: str
    blocked_reasons: tuple[str, ...]
    forbidden_claims: tuple[str, ...]
    forbidden_tools: tuple[str, ...]
    forbidden_actions: tuple[str, ...]
    leakage_hits: tuple[str, ...]
    authority_granted: dict[str, bool]
    output_publish_allowed: bool
    external_action_allowed: bool
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


def _all_false_authority() -> dict[str, bool]:
    return {
        "model_call": False,
        "agent_dispatch": False,
        "worker_dispatch": False,
        "workflow_execution": False,
        "external_action": False,
        "send_submit": False,
        "approval_execution": False,
        "file_body_read": False,
        "workbook_body_read": False,
        "spreadsheet_cell_read": False,
        "file_mutation": False,
        "credential_handling": False,
        "raw_body_ingestion": False,
    }


def _normalized_role(value: object) -> str:
    role = str(value or "OPENCLAW_SYSTEM").strip().upper().replace(" ", "_")
    return role or "OPENCLAW_SYSTEM"


def _normalize_tool(value: object) -> str:
    return str(value or "").strip().lower().replace(" ", "_")


def _public_text(payload: Mapping[str, Any]) -> str:
    fields = (
        "headline",
        "one_line_answer",
        "eliwinship",
        "primary_status",
        "primary_blocker",
        "next_action",
        "operator_headline",
        "operator_message",
        "how_to_fix",
        "next_safe_move",
    )
    spoken = payload.get("spoken_response_packet") if isinstance(payload.get("spoken_response_packet"), Mapping) else {}
    return " ".join(str(payload.get(field) or "") for field in fields) + " " + str(spoken.get("spoken_script") or "")


def _same_clause_prefix(text: str, claim_start: int) -> str:
    prefix = text[max(0, claim_start - 96) : claim_start]
    last_boundary_end = 0
    for match in _CLAUSE_BOUNDARY_RE.finditer(prefix):
        last_boundary_end = match.end()
    return prefix[last_boundary_end:]


def _benign_approval_adjective(text: str, claim_start: int, claim_end: int) -> bool:
    suffix = text[claim_end : claim_end + 96]
    return bool(
        re.match(
            r"\s+(?:pc(?:[- ]readable)?\s+)?(?:inbox|path|workbook\s+(?:path|access)|artifact\s+reference|contract|invoice\s+sheet\s+fields?|sheet\s+fields?)\b",
            suffix,
            re.IGNORECASE,
        )
    )


def _approval_execution_claims_from_text(text: str) -> tuple[str, ...]:
    lowered = str(text or "").lower()
    patterns = {
        "approved": (
            r"\b(?:i|we|you|he|she|they|the\s+operator|guardian|openclaw|the\s+system)\s+(?:(?:have|has|had)\s+)?approved\b",
            r"\b(?:the\s+)?(?:invoice|request|everything|it|this|that|send|payment|action|workflow)\s+(?:is|was|were|has\s+been|have\s+been)\s+approved\b",
            r"\bapproved\s+(?:it|this|that|everything|the\s+(?:invoice|request|send|payment|action|workflow|architecture))\b",
        ),
        "authorized": (
            r"\b(?:i|we|you|he|she|they|the\s+operator|guardian|openclaw|the\s+system)\s+(?:(?:have|has|had)\s+)?authorized\b",
            r"\b(?:the\s+)?(?:invoice|request|everything|it|this|that|send|payment|action|workflow)\s+(?:is|was|were|has\s+been|have\s+been)\s+(?:now\s+)?authorized\b",
            r"\bauthorized\s+(?:it|this|that|everything|the\s+(?:invoice|request|send|payment|action|workflow))\b",
        ),
    }
    found = [claim for claim, claim_patterns in patterns.items() if any(re.search(pattern, lowered) for pattern in claim_patterns)]
    return tuple(found)


def _unnegated_claims(text: str) -> tuple[str, ...]:
    lowered = str(text or "").lower()
    claims: list[str] = []
    for claim in COMPLETION_CLAIMS:
        for match in re.finditer(rf"\b{re.escape(claim)}\b", lowered):
            clause_prefix = _same_clause_prefix(lowered, match.start())
            prefix_tokens = _NEGATION_TOKEN_RE.findall(clause_prefix)
            suffix_tokens = _NEGATION_TOKEN_RE.findall(lowered[match.end() : match.end() + 96])
            nearby_tokens = [*prefix_tokens[-8:], *suffix_tokens[:8]]
            has_true_negation = any(token in NEGATION_CUES for token in prefix_tokens[-8:])
            has_hedge = any(token in HEDGING_CUES for token in nearby_tokens)
            if claim in APPROVAL_EXECUTION_CLAIMS and _benign_approval_adjective(
                lowered, match.start(), match.end()
            ):
                continue
            if has_hedge or not has_true_negation:
                claims.append(claim)
                break
    return tuple(dict.fromkeys(claims))


def _leakage_hits(text: str) -> tuple[str, ...]:
    lowered = str(text or "").lower()
    hits = [pattern for pattern in LEAKAGE_PATTERNS if pattern in lowered]
    for label, pattern in LEAKAGE_REGEX_PATTERNS:
        if pattern.search(str(text or "")):
            hits.append(label)
    if re.search(r"[\w.+-]+@[\w.-]+\.[a-z]{2,}", lowered):
        hits.append("email_address")
    return tuple(dict.fromkeys(hits))


def _blocked_completion_claims(claims: tuple[str, ...], proof_refs: tuple[str, ...]) -> tuple[str, ...]:
    if not claims:
        return ()
    if not proof_refs:
        return claims
    proof_backed_local = set(PROOF_BACKED_LOCAL_CLAIMS)
    return tuple(claim for claim in claims if claim not in proof_backed_local)


def _grounded_receivables_paid_status(candidate: RoleResponseCandidate) -> bool:
    if "paid" not in candidate.completion_claims:
        return False
    if "generated/read_models/receivables_month_bounded.json" not in candidate.proof_refs:
        return False
    row_ref_pattern = re.compile(
        r"^receivables_row:(?P<entity>[a-z0-9_]+):(?P<month>\d{4}-\d{2}):settled$"
    )
    requested_rows = []
    for proof_ref in candidate.proof_refs:
        match = row_ref_pattern.fullmatch(proof_ref)
        if match:
            requested_rows.append((match.group("entity"), match.group("month")))
    if not requested_rows:
        return False
    try:
        read_model_path = Path(__file__).resolve().parent / "generated/read_models/receivables_month_bounded.json"
        read_model = json.loads(read_model_path.read_text(encoding="utf-8"))
    except Exception:
        return False
    rows = read_model.get("rows") if isinstance(read_model, Mapping) else None
    if not isinstance(rows, list):
        return False
    settled_rows = {
        (str(row.get("client_ref") or ""), str(row.get("month") or ""))
        for row in rows
        if isinstance(row, Mapping)
        and row.get("structured_fact") is True
        and row.get("current_truth") is True
        and str(row.get("payment_status") or "") == "settled"
        and row.get("open_minor_units") == 0
        and row.get("needs_reconcile") is False
    }
    proven_rows = tuple(row for row in requested_rows if row in settled_rows)
    if not proven_rows:
        return False
    text = candidate.raw_output_text.lower()
    # Preserve character offsets while preventing the honorific-style "St."
    # abbreviation from being mistaken for a sentence boundary.
    paid_scan_text = re.sub(r"\bst\.", "st ", text)
    saw_grounded = False
    entity_patterns = {
        "capital_hilton": r"capital\s+hilton",
        "live_arts_md": r"live\s+arts(?:\s+md)?",
        "st_annes": r"st\.?\s+anne(?:'s|s)?",
    }
    month_names = {
        "01": r"(?:jan(?:uary)?\s+{year}|{year}-01)",
        "02": r"(?:feb(?:ruary)?\s+{year}|{year}-02)",
        "03": r"(?:mar(?:ch)?\s+{year}|{year}-03)",
        "04": r"(?:apr(?:il)?\s+{year}|{year}-04)",
        "05": r"(?:may\s+{year}|{year}-05)",
        "06": r"(?:jun(?:e)?\s+{year}|{year}-06)",
        "07": r"(?:jul(?:y)?\s+{year}|{year}-07)",
        "08": r"(?:aug(?:ust)?\s+{year}|{year}-08)",
        "09": r"(?:sep(?:t(?:ember)?)?\s+{year}|{year}-09)",
        "10": r"(?:oct(?:ober)?\s+{year}|{year}-10)",
        "11": r"(?:nov(?:ember)?\s+{year}|{year}-11)",
        "12": r"(?:dec(?:ember)?\s+{year}|{year}-12)",
    }
    grounded_prefixes = []
    for entity, month in proven_rows:
        entity_pattern = entity_patterns.get(entity)
        year, month_number = month.split("-", 1)
        month_pattern = month_names.get(month_number, "").format(year=re.escape(year))
        if not entity_pattern or not month_pattern:
            continue
        grounded_prefixes.append(
            re.compile(
                rf"\b{entity_pattern}\b[^.!?;]{{0,64}}\b{month_pattern}\b"
                rf"[^.!?;]{{0,64}}(?:\b(?:is|was|shows\s+as|status\s+is)\s+|\bsettled\s*[—-]\s*)$"
            )
        )
    if not grounded_prefixes:
        return False
    for match in re.finditer(r"\bpaid\b", paid_scan_text):
        clause_prefix = _same_clause_prefix(paid_scan_text, match.start())
        prefix_tokens = _NEGATION_TOKEN_RE.findall(clause_prefix)
        if any(token in NEGATION_CUES for token in prefix_tokens[-8:]):
            continue
        if not any(pattern.search(clause_prefix) for pattern in grounded_prefixes):
            return False
        saw_grounded = True
    return saw_grounded


def package_from_response_payload(payload: Mapping[str, Any]) -> RoleExecutionPackage:
    source_request_id = str(payload.get("source_request_id") or "unknown_request")
    role = _normalized_role(payload.get("response_author") or payload.get("agent_role"))
    return RoleExecutionPackage(
        package_id=f"role_execution_package:{_short_hash(source_request_id, role, payload.get('workflow_ref'))}",
        source_request_id=source_request_id,
        source_intent_ref=str(payload.get("response_kind") or payload.get("internal_status") or "unknown_intent"),
        role=role,
        model_backend=str(payload.get("selected_model_backend") or "NONE_DETERMINISTIC"),
        device_response_target="mission_control_scoped_response",
        workflow_ref=str(payload.get("workflow_ref") or "unknown"),
        client_ref=str(payload.get("client_ref") or "unknown"),
        allowed_tools=tuple(_normalize_tool(tool) for tool in payload.get("allowed_tools_plugins") or ()),
        allowed_actions=("respond_to_originating_device",),
        forbidden_actions=FORBIDDEN_ACTIONS,
        proof_refs=tuple(str(ref) for ref in payload.get("proof_refs") or payload.get("readback_files") or ()),
        authority_boundary=dict(AUTHORITY_BOUNDARY),
        output_contract=(
            "respond only to scoped originating device/thread",
            "do not claim send/submit/paid/completed without proof",
            "do not request tools/actions outside package",
            "do not expose credentials, raw bodies, hashes, or local paths",
        ),
        validation_required=True,
        next_safe_move="Validate role output before publication or action.",
    )


def candidate_from_response_payload(payload: Mapping[str, Any], package: RoleExecutionPackage) -> RoleResponseCandidate:
    raw_text = _public_text(payload)
    requested_tools = tuple(_normalize_tool(tool) for tool in payload.get("requested_tool_calls") or ())
    requested_actions = tuple(_normalize_tool(action) for action in payload.get("requested_external_actions") or ())
    detail = payload.get("detail_disclosure") if isinstance(payload.get("detail_disclosure"), Mapping) else {}
    authority_requested = detail.get("authority_requested") if isinstance(detail.get("authority_requested"), Mapping) else {}
    completion_claims = _unnegated_claims(raw_text)
    explicit_proof_refs = tuple(str(ref) for ref in payload.get("proof_refs") or ())
    readback_files = tuple(str(ref) for ref in payload.get("readback_files") or ())
    proof_refs = explicit_proof_refs if completion_claims else explicit_proof_refs or readback_files
    return RoleResponseCandidate(
        candidate_id=f"role_response_candidate:{_short_hash(package.package_id, raw_text)}",
        source_package_id=package.package_id,
        source_request_id=package.source_request_id,
        response_author=_normalized_role(payload.get("response_author") or payload.get("agent_role")),
        target_device_ref="mission_control_scoped_response",
        target_thread_ref=str(payload.get("source_request_id") or "unknown_thread"),
        headline=str(payload.get("headline") or ""),
        one_line_answer=str(payload.get("one_line_answer") or ""),
        eliwinship=str(payload.get("eliwinship") or ""),
        next_action=str(payload.get("next_action") or ""),
        requested_tool_calls=requested_tools,
        requested_external_actions=requested_actions,
        completion_claims=completion_claims,
        proof_refs=proof_refs,
        authority_requested={str(key): bool(value) for key, value in dict(authority_requested or {}).items()},
        raw_output_text=raw_text,
        next_safe_move=str(payload.get("next_safe_move") or payload.get("next_action") or "Validate before publishing."),
    )


def validate_role_output(candidate: RoleResponseCandidate, package: RoleExecutionPackage) -> RoleOutputValidationResult:
    blocked: list[str] = []
    if candidate.source_package_id != package.package_id:
        blocked.append("Candidate package id does not match role package.")
    if candidate.response_author != package.role:
        blocked.append("Candidate response author does not match role package.")
    if candidate.target_device_ref != package.device_response_target:
        blocked.append("Candidate target device does not match package target.")

    allowed_tools = set(package.allowed_tools)
    forbidden_tools = tuple(tool for tool in candidate.requested_tool_calls if tool and tool not in allowed_tools)
    forbidden_actions = tuple(
        action
        for action in candidate.requested_external_actions
        if action and (action not in package.allowed_actions or action in package.forbidden_actions)
    )
    if forbidden_tools:
        blocked.append("Requested tool is not in the package allowlist.")
    if forbidden_actions:
        blocked.append("Requested external action is not allowed.")

    authority_requested = any(candidate.authority_requested.values())
    package_authority_granted = any(package.authority_boundary.values())
    if authority_requested or package_authority_granted:
        blocked.append("Role output requested or package exposed live authority.")

    leakage = _leakage_hits(candidate.raw_output_text)
    if leakage:
        blocked.append("Role output appears to expose protected/private details.")

    forbidden_claims = candidate.completion_claims
    approval_execution_claims = _approval_execution_claims_from_text(candidate.raw_output_text)
    approval_authority_granted = any(
        bool(package.authority_boundary.get(key))
        for key in ("approval_execution", "approval_execution_allowed", "live_approval_execution_allowed")
    )
    approval_claim_without_authority = bool(approval_execution_claims and not approval_authority_granted)
    if approval_claim_without_authority:
        blocked.append("Role output claims approval execution without approval authority.")
    claims_requiring_block = tuple(
        claim
        for claim in forbidden_claims
        if not (claim == "paid" and _grounded_receivables_paid_status(candidate))
    )
    blocked_claims = _blocked_completion_claims(claims_requiring_block, candidate.proof_refs)
    if blocked_claims and not candidate.proof_refs:
        blocked.append("Role output makes completion/action claims without proof refs.")
    elif blocked_claims:
        blocked.append("Role output makes live-action or mutation claims that proof refs cannot authorize.")

    if forbidden_tools:
        verdict = BLOCKED_FORBIDDEN_TOOL
    elif forbidden_actions or authority_requested or package_authority_granted or approval_claim_without_authority:
        verdict = BLOCKED_AUTHORITY
    elif blocked_claims:
        verdict = BLOCKED_FORBIDDEN_CLAIM
    elif leakage:
        verdict = BLOCKED_LEAKAGE
    elif blocked:
        verdict = BLOCKED_SCOPE
    else:
        verdict = VALIDATED

    return RoleOutputValidationResult(
        validation_result_id=f"role_output_validation:{_short_hash(candidate.candidate_id, verdict)}",
        verdict=verdict,
        source_package_id=package.package_id,
        source_candidate_id=candidate.candidate_id,
        response_author=candidate.response_author,
        blocked_reasons=tuple(blocked),
        forbidden_claims=forbidden_claims,
        forbidden_tools=forbidden_tools,
        forbidden_actions=forbidden_actions,
        leakage_hits=leakage,
        authority_granted=_all_false_authority(),
        output_publish_allowed=verdict == VALIDATED,
        external_action_allowed=False,
        next_safe_move=(
            "Publish the scoped response; no external action is allowed."
            if verdict == VALIDATED
            else "Block or rewrite the role output before publication; do not execute anything."
        ),
    )


def validate_response_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    package = package_from_response_payload(payload)
    candidate = candidate_from_response_payload(payload, package)
    result = validate_role_output(candidate, package)
    return {
        "schema_version": SCHEMA_VERSION,
        "contract_status": CONTRACT_STATUS,
        "role_execution_package": asdict(package),
        "role_response_candidate": asdict(candidate),
        "validation_result": asdict(result),
        "machine_proof": {
            "guardian_output_gate_used": True,
            "role_output_validator_used": True,
            "output_publish_allowed": result.output_publish_allowed,
            "external_action_allowed": False,
            "model_call_performed": False,
            "agent_dispatch_performed": False,
            "worker_dispatch_performed": False,
            "workflow_execution_performed": False,
            "send_submit_performed": False,
            "approval_execution_performed": False,
            "credential_handling_performed": False,
            "raw_body_ingestion_performed": False,
            "all_live_authority_false": all(value is False for value in AUTHORITY_BOUNDARY.values()),
            "content_hash": "",
        },
    }


def build_publication_denial_substitution(
    payload: Mapping[str, Any],
    gate_payload: Mapping[str, Any],
    *,
    committed_effect_receipts: tuple[Mapping[str, Any], ...] = (),
) -> dict[str, Any]:
    """Return a bounded public replacement without retaining denied bytes.

    The raw candidate is represented only by a digest.  The caller may keep
    the gate's structured verdict, but must never copy ``payload`` or the role
    candidate into the published response after this function fires.
    """

    validation = gate_payload.get("validation_result")
    validation = validation if isinstance(validation, Mapping) else {}
    candidate_digest = hashlib.sha256(_public_text(payload).encode("utf-8")).hexdigest()
    committed_receipts = tuple(
        receipt
        for receipt in committed_effect_receipts
        if str(receipt.get("status") or "") == "committed"
    )
    file_mutation = any(receipt.get("file_mutation_performed") is True for receipt in committed_receipts)
    business_mutation = any(
        receipt.get("business_state_mutation_performed") is True
        for receipt in committed_receipts
    )
    if file_mutation or business_mutation:
        message = (
            "Guardian held the reply after a local truth-store update committed. "
            "No external action ran. Ask me to show the write receipt and gate reason."
        )
    else:
        message = PUBLICATION_DENIAL_MESSAGE
    return {
        "schema_version": "guardian_publication_enforcement_v0",
        "substituted": True,
        "original_output_publish_allowed": False,
        "original_verdict": str(validation.get("verdict") or UNKNOWN_FAIL_CLOSED),
        "validation_result_id": str(validation.get("validation_result_id") or ""),
        "blocked_reasons": [str(item) for item in validation.get("blocked_reasons") or ()],
        "forbidden_claims": [str(item) for item in validation.get("forbidden_claims") or ()],
        "leakage_hits": [str(item) for item in validation.get("leakage_hits") or ()],
        "candidate_digest": f"sha256:{candidate_digest}",
        "headline": PUBLICATION_DENIAL_HEADLINE,
        "message": message,
        "next_safe_move": "Retry the bounded readback or ask for the gate reason.",
        "external_action_performed": False,
        "effect_receipt_ids": [str(receipt.get("receipt_id") or "") for receipt in committed_receipts],
        "file_mutation_performed": file_mutation,
        "business_state_mutation_performed": business_mutation,
    }


def build_last_resort_publication_gate(
    prior_gate_payload: Mapping[str, Any],
) -> dict[str, Any]:
    """Authorize only the hard-coded Guardian blocked readback after re-deny.

    The caller has already discarded the candidate before invoking this path.
    No candidate or raw prior response is copied into this receipt.
    """

    prior = prior_gate_payload.get("validation_result")
    prior = prior if isinstance(prior, Mapping) else {}
    validation = {
        "validation_result_id": f"guardian_last_resort:{_short_hash(prior.get('validation_result_id'), LAST_RESORT_BLOCKED_RESPONSE)}",
        "verdict": LAST_RESORT_BLOCKED_RESPONSE,
        "source_package_id": "guardian:last_resort_blocked_readback",
        "source_candidate_id": "guardian:hard_coded_blocked_readback",
        "response_author": "GUARDIAN",
        "blocked_reasons": ["The gate-authored substitution was denied; hard-coded blocked readback used."],
        "forbidden_claims": [],
        "forbidden_tools": [],
        "forbidden_actions": [],
        "leakage_hits": [],
        "authority_granted": _all_false_authority(),
        "output_publish_allowed": True,
        "external_action_allowed": False,
        "next_safe_move": "Publish only the hard-coded blocked readback.",
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "contract_status": CONTRACT_STATUS,
        "role_execution_package": {
            "package_id": "guardian:last_resort_blocked_readback",
            "role": "GUARDIAN",
            "allowed_actions": ["publish_hard_coded_blocked_readback"],
            "forbidden_actions": list(FORBIDDEN_ACTIONS),
            "authority_boundary": dict(AUTHORITY_BOUNDARY),
        },
        "validation_result": validation,
        "machine_proof": {
            "guardian_output_gate_used": True,
            "role_output_validator_used": True,
            "output_publish_allowed": True,
            "external_action_allowed": False,
            "last_resort_blocked_readback": True,
        },
    }


def build_payload(*, generated_at: str | None = None) -> dict[str, Any]:
    generated_at = generated_at or DEFAULT_GENERATED_AT
    safe_payload = {
        "source_request_id": "guardian_output_gate_fixture_safe",
        "workflow_ref": "capital_hilton_invoice_workflow",
        "response_author": "CASSANDRA",
        "selected_model_backend": "GPT",
        "allowed_tools_plugins": ("draft_readback_only",),
        "headline": "Draft ready",
        "one_line_answer": "I prepared review language only.",
        "eliwinship": "Draft review language is ready. Send authority remains locked.",
        "next_action": "Next: review the draft.",
        "readback_files": ("generated/read_models/guardian_output_gate.json",),
    }
    blocked_payload = {
        **safe_payload,
        "source_request_id": "guardian_output_gate_fixture_blocked",
        "headline": "Invoice sent",
        "eliwinship": "I sent the invoice and posted the ledger.",
        "requested_external_actions": ("email_send",),
    }
    safe_result = validate_response_payload(safe_payload)
    blocked_result = validate_response_payload(blocked_payload)
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "contract_status": CONTRACT_STATUS,
        "generated_at": generated_at,
        "verdicts": VERDICTS,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "examples": {
            "safe_role_response": safe_result,
            "blocked_rogue_role_response": blocked_result,
        },
        "machine_proof": {
            "safe_example_validated": safe_result["validation_result"]["verdict"] == VALIDATED,
            "rogue_example_blocked": blocked_result["validation_result"]["verdict"] != VALIDATED,
            "model_call_performed": False,
            "agent_dispatch_performed": False,
            "worker_dispatch_performed": False,
            "workflow_execution_performed": False,
            "external_action_performed": False,
            "send_submit_performed": False,
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
    blocked = payload.get("examples", {}).get("blocked_rogue_role_response", {}).get("validation_result", {})
    lines = [
        "# Guardian Output Gate",
        "",
        f"Status: {CONTRACT_STATUS}",
        f"Safe example: {payload.get('examples', {}).get('safe_role_response', {}).get('validation_result', {}).get('verdict', '')}",
        f"Rogue example: {blocked.get('verdict', '')}",
        "",
        "One shared output gate validates role output before publication or action.",
        "",
        "Boundary: no model call, no execution, no send/submit, no body read, no authority grant.",
    ]
    operator_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return json_path, operator_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export Guardian output gate read-model.")
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
                    "safe_example_validated": payload["machine_proof"]["safe_example_validated"],
                    "rogue_example_blocked": payload["machine_proof"]["rogue_example_blocked"],
                    "all_live_authority_false": payload["machine_proof"]["all_live_authority_false"],
                }
            ),
            end="",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
