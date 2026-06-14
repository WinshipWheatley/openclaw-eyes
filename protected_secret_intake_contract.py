"""Protected Secret Intake Contract v0.

This deterministic read-model defines how future operator-entered secrets from
chat should become protected references. It does not capture, store, reveal, use,
or create real secrets. It does not log secrets, send secrets to an LLM, access
external systems, run adapters, log in, open browsers, mutate Mission Control,
run Mac sync/import, or push.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_GENERATED_AT = "2026-05-25T00:00:00+00:00"

SCHEMA_VERSION = "protected_secret_intake_contract_v0"
READ_MODEL_ID = "protected_secret_intake_contract"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
OPERATOR_EXPORT_NAME = f"{READ_MODEL_ID}_OPERATOR.md"
CONTRACT_STATUS = "DETERMINISTIC_CONTRACT_ONLY_PROTECTED_SECRET_INTAKE"

SUPPORTED_SECRET_MODES = (
    "USE_ONCE",
    "STORE_PROTECTED",
    "SESSION_TTL",
    "TASK_SCOPED",
    "NEVER_STORE",
)

SECRET_KINDS = (
    "PASSWORD",
    "API_KEY",
    "OAUTH_TOKEN",
    "SESSION_COOKIE",
    "SSH_KEY",
    "BANKING_OR_PAYMENT_SECRET",
    "COUPA_CREDENTIAL",
    "EMAIL_ACCOUNT_SECRET",
    "APP_SPECIFIC_PASSWORD",
    "UNKNOWN_SECRET_FAIL_CLOSED",
)

RECEIPT_ACTIONS = (
    "TOKEN_CREATED",
    "TOKEN_STORED",
    "TOKEN_USED_ONCE",
    "TOKEN_EXPIRED",
    "TOKEN_REVOKED",
    "TOKEN_ROTATION_REQUIRED",
    "TOKEN_USE_BLOCKED",
)

BLOCKER_TYPES = (
    "RAW_SECRET_IN_CHAT",
    "RAW_SECRET_IN_READMODEL",
    "RAW_SECRET_IN_LLM_CONTEXT",
    "RAW_SECRET_IN_LOG",
    "RAW_SECRET_IN_TEST_FIXTURE",
    "RAW_SECRET_SENT_EXTERNAL",
    "ADAPTER_NOT_APPROVED",
    "TTL_MISSING",
    "SCOPE_MISSING",
    "GUARDIAN_REQUIRED",
    "UNKNOWN_SECRET_FAIL_CLOSED",
)

AUTHORITY_BOUNDARY = {
    "live_secret_capture_allowed": False,
    "live_secret_store_allowed": False,
    "live_secret_reveal_allowed": False,
    "live_secret_adapter_use_allowed": False,
    "live_login_allowed": False,
    "live_browser_allowed": False,
    "live_external_action_allowed": False,
    "live_llm_secret_exposure_allowed": False,
    "live_model_call_allowed": False,
    "live_tool_execution_allowed": False,
    "live_agent_dispatch_allowed": False,
    "credential_handling_allowed": False,
    "raw_body_ingestion_allowed": False,
    "network_allowed": False,
    "mission_control_swift_change_allowed": False,
    "mac_sync_import_allowed": False,
    "git_push_pull_fetch_allowed": False,
}

TOKEN_REF_PREFIX = "secret_ref"
PROTECTED_STORE_REF_PREFIX = "protected_store_ref"


@dataclass(frozen=True)
class ProtectedSecretIntakeContract:
    contract_id: str
    doctrine: tuple[str, ...]
    supported_secret_modes: tuple[str, ...]
    protected_storage_policy: tuple[str, ...]
    tokenization_policy: tuple[str, ...]
    ttl_policy: tuple[str, ...]
    scope_policy: tuple[str, ...]
    reveal_policy: tuple[str, ...]
    adapter_use_policy: tuple[str, ...]
    operator_confirmation_policy: tuple[str, ...]
    audit_receipt_policy: tuple[str, ...]
    privacy_boundary: tuple[str, ...]
    authority_boundary: dict[str, bool]
    next_safe_move: str


@dataclass(frozen=True)
class ProtectedSecretIntakeRequest:
    request_id: str
    origin_surface: str
    source_channel: str
    workflow_ref: str
    task_ref: str
    secret_kind: str
    secret_mode: str
    requested_scope: str
    requested_ttl: str
    operator_intent_summary: str
    raw_secret_allowed_in_request: bool
    raw_secret_allowed_in_read_model: bool
    raw_secret_allowed_in_llm_context: bool
    next_safe_move: str


@dataclass(frozen=True)
class ProtectedSecretToken:
    token_ref: str
    protected_store_ref: str
    safe_display_label: str
    secret_kind: str
    privacy_class: str
    sensitivity_class: str
    allowed_scope: str
    ttl_seconds: int | None
    expires_at_policy: str
    reuse_policy: str
    rotation_policy: str
    reveal_allowed: bool
    adapter_use_required: bool
    guardian_review_required: bool
    next_safe_move: str


@dataclass(frozen=True)
class SecretUsePolicy:
    policy_id: str
    token_ref: str
    allowed_workflow_refs: tuple[str, ...]
    allowed_adapter_refs: tuple[str, ...]
    allowed_machine: str
    one_time_use: bool
    ttl_required: bool
    operator_confirmation_required: bool
    guardian_review_required: bool
    raw_value_reveal_forbidden: bool
    use_receipt_required: bool
    next_safe_move: str


@dataclass(frozen=True)
class ProtectedSecretReceipt:
    receipt_id: str
    token_ref: str
    intake_request_ref: str
    action: str
    mode: str
    scope: str
    ttl_policy: str
    raw_secret_stored: bool
    raw_secret_logged: bool
    raw_secret_sent_to_llm: bool
    raw_secret_sent_external: bool
    external_authority: bool
    created_at_policy: str
    next_safe_move: str


@dataclass(frozen=True)
class ProtectedSecretBlocker:
    blocker_id: str
    blocker_type: str
    condition: str
    severity: str
    elioperator_warning: str
    fail_closed: bool
    next_safe_move: str


@dataclass(frozen=True)
class ProtectedSecretElioperatorReport:
    report_id: str
    plain_summary: str
    what_this_enables: str
    what_this_does_not_do_yet: str
    how_enter_secret_should_work: str
    how_agents_see_tokens: str
    how_ttl_and_scope_work: str
    how_future_adapters_may_use_secret: str
    next_safe_move: str


REQUIRED_CONTRACT_FIELDS = tuple(ProtectedSecretIntakeContract.__dataclass_fields__.keys())
REQUIRED_REQUEST_FIELDS = tuple(ProtectedSecretIntakeRequest.__dataclass_fields__.keys())
REQUIRED_TOKEN_FIELDS = tuple(ProtectedSecretToken.__dataclass_fields__.keys())
REQUIRED_USE_POLICY_FIELDS = tuple(SecretUsePolicy.__dataclass_fields__.keys())
REQUIRED_RECEIPT_FIELDS = tuple(ProtectedSecretReceipt.__dataclass_fields__.keys())
REQUIRED_BLOCKER_FIELDS = tuple(ProtectedSecretBlocker.__dataclass_fields__.keys())
REQUIRED_REPORT_FIELDS = tuple(ProtectedSecretElioperatorReport.__dataclass_fields__.keys())


def stable_json(data: Any) -> str:
    return json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _content_hash(payload: dict[str, Any]) -> str:
    clean = json.loads(stable_json(payload))
    clean.get("machine_proof", {}).pop("content_hash", None)
    return hashlib.sha256(stable_json(clean).encode("utf-8")).hexdigest()


def build_contract() -> ProtectedSecretIntakeContract:
    return ProtectedSecretIntakeContract(
        contract_id="protected_secret_intake_contract_v0",
        doctrine=(
            "The operator may enter a secret only through a future protected intake surface.",
            "OpenClaw converts raw secret material into a protected reference.",
            "Agents and LLMs see references and safe metadata, not values.",
            "Normal read-models, chat transcripts, logs, tests, fixtures, screenshots, and cards never contain raw values.",
            "Only a future approved adapter may use a raw value, only inside the declared scope.",
            "This contract does not handle live credentials.",
        ),
        supported_secret_modes=SUPPORTED_SECRET_MODES,
        protected_storage_policy=(
            "STORE_PROTECTED requires a protected local vault or future Keychain-compatible store.",
            "USE_ONCE and NEVER_STORE must avoid persistence by default.",
            "SESSION_TTL must expire automatically by policy.",
            "Generated read-models expose only token refs and safe labels.",
        ),
        tokenization_policy=(
            "Token refs use an opaque protected reference.",
            "Safe labels describe kind and scope without including value material.",
            "Token maps and vault internals must never be rendered in normal outputs.",
            "Existing PII tokenization hooks are referenced as precedent, not activated here.",
        ),
        ttl_policy=(
            "TTL is required for SESSION_TTL.",
            "USE_ONCE expires after one approved future use.",
            "TASK_SCOPED expires when declared task scope ends.",
            "Missing TTL fails closed when the selected mode requires a TTL.",
        ),
        scope_policy=(
            "Every token must have a declared workflow/task scope.",
            "Adapters must match allowed workflow and adapter refs.",
            "Scope cannot be expanded silently by an agent or LLM.",
            "Missing scope fails closed.",
        ),
        reveal_policy=(
            "Raw value reveal is forbidden in normal UI, chat, logs, prompts, cards, and read-models.",
            "Operators should see labels and refs, not values.",
            "Future reveal would require explicit protected local path and Guardian review; no such authority exists here.",
        ),
        adapter_use_policy=(
            "Future adapter use requires explicit operator confirmation, Guardian review when sensitive, scope match, and use receipt.",
            "No browser, login, Coupa, Gmail, OAuth, or external action is allowed by this contract.",
            "Adapters receive the raw value only inside a future secure runtime envelope, never through LLM context.",
        ),
        operator_confirmation_policy=(
            "Operator must confirm mode, scope, and TTL before future protected intake can become usable.",
            "USE_ONCE and TASK_SCOPED require task confirmation.",
            "STORE_PROTECTED requires durable-storage confirmation and rotation posture.",
        ),
        audit_receipt_policy=(
            "Receipts record token ref, action, mode, scope, and whether raw value leakage was prevented.",
            "Receipts never include raw value material.",
            "Use receipts are required before any future adapter use can be considered complete.",
        ),
        privacy_boundary=(
            "Raw secret never appears in normal read-models.",
            "Raw secret never appears in chat transcript.",
            "Raw secret never appears in LLM/model context.",
            "Raw secret never appears in generated operator markdown.",
            "Raw secret never appears in logs/tests/fixtures.",
            "Agents see refs, not values.",
        ),
        authority_boundary=AUTHORITY_BOUNDARY,
        next_safe_move="Use fake token refs only and build future adapter gates before any live secret handling.",
    )


def _request(
    *,
    request_id: str,
    workflow_ref: str,
    task_ref: str,
    secret_kind: str,
    secret_mode: str,
    requested_scope: str,
    requested_ttl: str,
    operator_intent_summary: str,
    next_safe_move: str,
) -> ProtectedSecretIntakeRequest:
    return ProtectedSecretIntakeRequest(
        request_id=request_id,
        origin_surface="future_chat_plus_menu_enter_secret",
        source_channel="operator_local_chat",
        workflow_ref=workflow_ref,
        task_ref=task_ref,
        secret_kind=secret_kind,
        secret_mode=secret_mode,
        requested_scope=requested_scope,
        requested_ttl=requested_ttl,
        operator_intent_summary=operator_intent_summary,
        raw_secret_allowed_in_request=False,
        raw_secret_allowed_in_read_model=False,
        raw_secret_allowed_in_llm_context=False,
        next_safe_move=next_safe_move,
    )


def _token(
    *,
    token_ref: str,
    protected_store_ref: str,
    safe_display_label: str,
    secret_kind: str,
    allowed_scope: str,
    ttl_seconds: int | None,
    expires_at_policy: str,
    reuse_policy: str,
    rotation_policy: str,
    guardian_review_required: bool,
    next_safe_move: str,
) -> ProtectedSecretToken:
    return ProtectedSecretToken(
        token_ref=token_ref,
        protected_store_ref=protected_store_ref,
        safe_display_label=safe_display_label,
        secret_kind=secret_kind,
        privacy_class="protected_secret_ref_only",
        sensitivity_class="secret_material_value_excluded",
        allowed_scope=allowed_scope,
        ttl_seconds=ttl_seconds,
        expires_at_policy=expires_at_policy,
        reuse_policy=reuse_policy,
        rotation_policy=rotation_policy,
        reveal_allowed=False,
        adapter_use_required=True,
        guardian_review_required=guardian_review_required,
        next_safe_move=next_safe_move,
    )


def _use_policy(
    *,
    policy_id: str,
    token_ref: str,
    allowed_workflow_refs: tuple[str, ...],
    allowed_adapter_refs: tuple[str, ...],
    allowed_machine: str,
    one_time_use: bool,
    ttl_required: bool,
    guardian_review_required: bool,
    next_safe_move: str,
) -> SecretUsePolicy:
    return SecretUsePolicy(
        policy_id=policy_id,
        token_ref=token_ref,
        allowed_workflow_refs=allowed_workflow_refs,
        allowed_adapter_refs=allowed_adapter_refs,
        allowed_machine=allowed_machine,
        one_time_use=one_time_use,
        ttl_required=ttl_required,
        operator_confirmation_required=True,
        guardian_review_required=guardian_review_required,
        raw_value_reveal_forbidden=True,
        use_receipt_required=True,
        next_safe_move=next_safe_move,
    )


def _receipt(
    *,
    receipt_id: str,
    token_ref: str,
    intake_request_ref: str,
    action: str,
    mode: str,
    scope: str,
    ttl_policy: str,
    next_safe_move: str,
) -> ProtectedSecretReceipt:
    return ProtectedSecretReceipt(
        receipt_id=receipt_id,
        token_ref=token_ref,
        intake_request_ref=intake_request_ref,
        action=action,
        mode=mode,
        scope=scope,
        ttl_policy=ttl_policy,
        raw_secret_stored=False,
        raw_secret_logged=False,
        raw_secret_sent_to_llm=False,
        raw_secret_sent_external=False,
        external_authority=False,
        created_at_policy="deterministic_fixture_no_live_timestamp",
        next_safe_move=next_safe_move,
    )


def build_use_once_coupa_example() -> dict[str, Any]:
    request = _request(
        request_id="protected_secret_request_coupa_use_once",
        workflow_ref="capital_hilton_invoice_workflow",
        task_ref="future_coupa_login_step",
        secret_kind="COUPA_CREDENTIAL",
        secret_mode="USE_ONCE",
        requested_scope="capital_hilton_coupa_future_login_only",
        requested_ttl="one approved future use then erase",
        operator_intent_summary="Operator wants to provide a Coupa credential later for one approved task.",
        next_safe_move="Create protected ref only; do not log in or expose value.",
    )
    token = _token(
        token_ref=f"{TOKEN_REF_PREFIX}:coupa_use_once_capital_hilton",
        protected_store_ref=f"{PROTECTED_STORE_REF_PREFIX}:volatile_future_envelope_only",
        safe_display_label="Coupa credential for Capital Hilton (protected ref only)",
        secret_kind="COUPA_CREDENTIAL",
        allowed_scope="capital_hilton_coupa_future_login_only",
        ttl_seconds=None,
        expires_at_policy="expires immediately after one approved future adapter use",
        reuse_policy="single approved future use only",
        rotation_policy="rotation required if future use is blocked or scope changes",
        guardian_review_required=True,
        next_safe_move="Route only token ref and scope to agents.",
    )
    policy = _use_policy(
        policy_id="secret_use_policy_coupa_use_once",
        token_ref=token.token_ref,
        allowed_workflow_refs=("capital_hilton_invoice_workflow",),
        allowed_adapter_refs=("future_governed_coupa_adapter",),
        allowed_machine="LOCAL_ONLY",
        one_time_use=True,
        ttl_required=False,
        guardian_review_required=True,
        next_safe_move="Wait for future approved Coupa adapter and Guardian review.",
    )
    receipt = _receipt(
        receipt_id="protected_secret_receipt_coupa_token_created",
        token_ref=token.token_ref,
        intake_request_ref=request.request_id,
        action="TOKEN_CREATED",
        mode="USE_ONCE",
        scope=token.allowed_scope,
        ttl_policy=token.expires_at_policy,
        next_safe_move="No login occurs; show only protected ref metadata.",
    )
    return {
        "example_id": "use_once_for_coupa_login_later",
        "intake_request": asdict(request),
        "protected_secret_token": asdict(token),
        "secret_use_policy": asdict(policy),
        "protected_secret_receipt": asdict(receipt),
        "agent_visible_context": {
            "token_ref": token.token_ref,
            "safe_display_label": token.safe_display_label,
            "allowed_scope": token.allowed_scope,
            "raw_value_visible": False,
        },
        "login_performed": False,
        "next_safe_move": "Ask operator to confirm future scope and keep Coupa login blocked.",
    }


def build_store_protected_api_key_example() -> dict[str, Any]:
    request = _request(
        request_id="protected_secret_request_api_key_store_protected",
        workflow_ref="future_api_integration_setup",
        task_ref="future_adapter_configuration",
        secret_kind="API_KEY",
        secret_mode="STORE_PROTECTED",
        requested_scope="future_named_adapter_only",
        requested_ttl="durable until revoked or rotated",
        operator_intent_summary="Operator wants to store a protected API key for a future named adapter.",
        next_safe_move="Create tokenized ref only; raw key is not present in this read-model.",
    )
    token = _token(
        token_ref=f"{TOKEN_REF_PREFIX}:api_key_future_named_adapter",
        protected_store_ref=f"{PROTECTED_STORE_REF_PREFIX}:future_local_vault_slot",
        safe_display_label="API key for future named adapter (protected ref only)",
        secret_kind="API_KEY",
        allowed_scope="future_named_adapter_only",
        ttl_seconds=None,
        expires_at_policy="valid until revoked or rotation required by policy",
        reuse_policy="adapter-scoped reuse only",
        rotation_policy="rotation required on scope change, revocation, or suspected exposure",
        guardian_review_required=True,
        next_safe_move="Future adapter must request token use receipt before use.",
    )
    policy = _use_policy(
        policy_id="secret_use_policy_api_key_store_protected",
        token_ref=token.token_ref,
        allowed_workflow_refs=("future_api_integration_setup",),
        allowed_adapter_refs=("future_named_adapter",),
        allowed_machine="LOCAL_ONLY",
        one_time_use=False,
        ttl_required=False,
        guardian_review_required=True,
        next_safe_move="Keep raw key unavailable to agents and LLMs.",
    )
    receipt = _receipt(
        receipt_id="protected_secret_receipt_api_key_token_stored_future",
        token_ref=token.token_ref,
        intake_request_ref=request.request_id,
        action="TOKEN_STORED",
        mode="STORE_PROTECTED",
        scope=token.allowed_scope,
        ttl_policy=token.expires_at_policy,
        next_safe_move="Record token metadata only; no live store is written by this contract.",
    )
    return {
        "example_id": "store_protected_api_key",
        "intake_request": asdict(request),
        "protected_secret_token": asdict(token),
        "secret_use_policy": asdict(policy),
        "protected_secret_receipt": asdict(receipt),
        "raw_key_visible": False,
        "future_adapter_required": True,
        "next_safe_move": "Wait for a future protected store lane before any real API key is accepted.",
    }


def build_session_ttl_example() -> dict[str, Any]:
    request = _request(
        request_id="protected_secret_request_session_ttl",
        workflow_ref="future_session_bound_workflow",
        task_ref="future_session_bound_task",
        secret_kind="SESSION_COOKIE",
        secret_mode="SESSION_TTL",
        requested_scope="single_local_session_window",
        requested_ttl="900 seconds",
        operator_intent_summary="Operator wants a secret available for a bounded local session only.",
        next_safe_move="Require expiry and block use after session TTL.",
    )
    token = _token(
        token_ref=f"{TOKEN_REF_PREFIX}:session_ttl_future_window",
        protected_store_ref=f"{PROTECTED_STORE_REF_PREFIX}:volatile_session_slot",
        safe_display_label="Session TTL secret (protected ref only)",
        secret_kind="SESSION_COOKIE",
        allowed_scope="single_local_session_window",
        ttl_seconds=900,
        expires_at_policy="expires 900 seconds after future secure intake",
        reuse_policy="session-limited reuse only before expiry",
        rotation_policy="new intake required after expiry",
        guardian_review_required=True,
        next_safe_move="Do not allow use after expiry policy.",
    )
    policy = _use_policy(
        policy_id="secret_use_policy_session_ttl",
        token_ref=token.token_ref,
        allowed_workflow_refs=("future_session_bound_workflow",),
        allowed_adapter_refs=("future_session_bound_adapter",),
        allowed_machine="LOCAL_ONLY",
        one_time_use=False,
        ttl_required=True,
        guardian_review_required=True,
        next_safe_move="Block use after TTL expires.",
    )
    receipt = _receipt(
        receipt_id="protected_secret_receipt_session_ttl_expired_example",
        token_ref=token.token_ref,
        intake_request_ref=request.request_id,
        action="TOKEN_EXPIRED",
        mode="SESSION_TTL",
        scope=token.allowed_scope,
        ttl_policy=token.expires_at_policy,
        next_safe_move="Request new protected intake if the task still needs access.",
    )
    return {
        "example_id": "session_ttl_secret",
        "intake_request": asdict(request),
        "protected_secret_token": asdict(token),
        "secret_use_policy": asdict(policy),
        "protected_secret_receipt": asdict(receipt),
        "use_after_expiry_allowed": False,
        "next_safe_move": "Show expired token state and request a new protected intake if needed.",
    }


def build_block_raw_secret_chat_example() -> dict[str, Any]:
    return {
        "example_id": "block_raw_secret_in_chat",
        "operator_action_summary": "Operator pasted a credential-like value into ordinary chat instead of protected intake.",
        "raw_value_recorded": False,
        "blocker_type": "RAW_SECRET_IN_CHAT",
        "elioperator_warning": "This looks like secret material in normal chat. I am not storing or repeating it. Use Enter Secret so OpenClaw can create a protected ref.",
        "fail_closed": True,
        "next_safe_move": "Discard visible value from normal flow and ask operator to re-enter through protected intake later.",
    }


def build_block_llm_exposure_example() -> dict[str, Any]:
    return {
        "example_id": "block_raw_secret_in_llm_context",
        "package_attempt_summary": "A package tries to include raw secret material in model context.",
        "raw_value_included": False,
        "blocker_type": "RAW_SECRET_IN_LLM_CONTEXT",
        "elioperator_warning": "Agents and LLMs get the protected ref only, not the value.",
        "fail_closed": True,
        "next_safe_move": "Replace the raw value with token ref metadata or block the package.",
    }


def build_examples() -> dict[str, Any]:
    return {
        "use_once_coupa_login_later": build_use_once_coupa_example(),
        "store_protected_api_key": build_store_protected_api_key_example(),
        "session_ttl_secret": build_session_ttl_example(),
        "block_raw_secret_in_chat": build_block_raw_secret_chat_example(),
        "block_raw_secret_in_llm_context": build_block_llm_exposure_example(),
    }


def build_blockers() -> tuple[ProtectedSecretBlocker, ...]:
    details = {
        "RAW_SECRET_IN_CHAT": (
            "A raw secret is pasted into ordinary chat transcript.",
            "This belongs in Enter Secret, not chat. I will not repeat or store it here.",
        ),
        "RAW_SECRET_IN_READMODEL": (
            "A generated read-model contains raw secret material.",
            "Generated read-models may show protected refs only.",
        ),
        "RAW_SECRET_IN_LLM_CONTEXT": (
            "A package attempts to send raw secret material to a model.",
            "Models get the protected ref and safe metadata only.",
        ),
        "RAW_SECRET_IN_LOG": (
            "A log line includes raw secret material.",
            "Logs must show no originals.",
        ),
        "RAW_SECRET_IN_TEST_FIXTURE": (
            "A test fixture includes realistic secret material.",
            "Use fake refs and labels only.",
        ),
        "RAW_SECRET_SENT_EXTERNAL": (
            "A raw secret is sent to an external system outside a future approved adapter.",
            "External secret use is blocked unless a future adapter is approved and scoped.",
        ),
        "ADAPTER_NOT_APPROVED": (
            "A package tries to use a token without an approved adapter.",
            "No adapter use until approval, scope match, and use receipt exist.",
        ),
        "TTL_MISSING": (
            "A TTL-required mode has no TTL policy.",
            "Add a TTL or fail closed.",
        ),
        "SCOPE_MISSING": (
            "A secret token lacks workflow/task scope.",
            "Add a declared scope or fail closed.",
        ),
        "GUARDIAN_REQUIRED": (
            "Sensitive secret use needs Guardian review.",
            "Route to Guardian review before any future adapter use.",
        ),
        "UNKNOWN_SECRET_FAIL_CLOSED": (
            "The secret kind, scope, or mode is unknown.",
            "Fail closed and ask the operator to classify the secret.",
        ),
    }
    return tuple(
        ProtectedSecretBlocker(
            blocker_id=f"protected_secret_blocker_{blocker_type.lower()}",
            blocker_type=blocker_type,
            condition=condition,
            severity="CRITICAL" if blocker_type == "UNKNOWN_SECRET_FAIL_CLOSED" else "HIGH",
            elioperator_warning=warning,
            fail_closed=True,
            next_safe_move="Block raw value handling and return a protected-ref-only explanation.",
        )
        for blocker_type, (condition, warning) in details.items()
    )


def build_report() -> ProtectedSecretElioperatorReport:
    return ProtectedSecretElioperatorReport(
        report_id="protected_secret_elioperator_report_v0",
        plain_summary="Enter Secret should create a protected reference, not put a value into chat.",
        what_this_enables="OpenClaw can plan for secrets without exposing them to chats, models, logs, cards, tests, or normal read-models.",
        what_this_does_not_do_yet="This does not capture, store, reveal, use, or transmit real credentials. No browser/login/external action is added.",
        how_enter_secret_should_work="The future plus-menu intake accepts the value inside a secure envelope, creates a protected ref, and immediately hides the raw value from normal surfaces.",
        how_agents_see_tokens="Agents see a token ref, safe label, kind, scope, TTL policy, and gate status. They never see the value.",
        how_ttl_and_scope_work="USE_ONCE, SESSION_TTL, TASK_SCOPED, and NEVER_STORE all require explicit scope; SESSION_TTL requires expiry.",
        how_future_adapters_may_use_secret="A future adapter may request the raw value only inside its approved scope, after operator confirmation and Guardian review when required, and must emit a use receipt.",
        next_safe_move="Build UI/runtime intake later; keep this read-model protected-ref-only.",
    )


def _model_schemas() -> dict[str, Any]:
    return {
        "protected_secret_intake_contract": {"required_fields": list(REQUIRED_CONTRACT_FIELDS)},
        "protected_secret_intake_request": {"required_fields": list(REQUIRED_REQUEST_FIELDS)},
        "protected_secret_token": {"required_fields": list(REQUIRED_TOKEN_FIELDS)},
        "secret_use_policy": {"required_fields": list(REQUIRED_USE_POLICY_FIELDS)},
        "protected_secret_receipt": {"required_fields": list(REQUIRED_RECEIPT_FIELDS)},
        "protected_secret_blocker": {"required_fields": list(REQUIRED_BLOCKER_FIELDS)},
        "protected_secret_elioperator_report": {"required_fields": list(REQUIRED_REPORT_FIELDS)},
    }


def _all_authority_false(payload: dict[str, Any]) -> bool:
    if any(payload["authority_boundary"].values()):
        return False
    examples = payload["examples"]
    return all(
        example.get("protected_secret_receipt", {}).get("external_authority", False) is False
        for example in examples.values()
    )


def _agents_see_refs_only(payload: dict[str, Any]) -> bool:
    context = payload["examples"]["use_once_coupa_login_later"]["agent_visible_context"]
    return context["raw_value_visible"] is False and context["token_ref"].startswith(f"{TOKEN_REF_PREFIX}:")


def _machine_proof(payload: dict[str, Any]) -> dict[str, Any]:
    blockers = payload["protected_secret_blockers_by_id"].values()
    blocker_types = {blocker["blocker_type"] for blocker in blockers}
    examples = payload["examples"]
    return {
        "protected_secret_intake_contract_model_present": True,
        "protected_secret_intake_request_model_present": True,
        "protected_secret_token_model_present": True,
        "secret_use_policy_model_present": True,
        "protected_secret_receipt_model_present": True,
        "protected_secret_blocker_model_present": True,
        "protected_secret_elioperator_report_model_present": True,
        "all_secret_modes_exist": set(SUPPORTED_SECRET_MODES).issubset(payload["supported_secret_modes"]),
        "secret_kinds_exist": set(SECRET_KINDS).issubset(payload["secret_kinds"]),
        "receipt_actions_exist": set(RECEIPT_ACTIONS).issubset(payload["receipt_actions"]),
        "raw_secret_blockers_exist": {
            "RAW_SECRET_IN_CHAT",
            "RAW_SECRET_IN_READMODEL",
            "RAW_SECRET_IN_LOG",
            "RAW_SECRET_IN_TEST_FIXTURE",
        }.issubset(blocker_types),
        "llm_exposure_blocker_exists": "RAW_SECRET_IN_LLM_CONTEXT" in blocker_types,
        "ttl_requirement_exists": "TTL_MISSING" in blocker_types
        and examples["session_ttl_secret"]["secret_use_policy"]["ttl_required"] is True,
        "scope_requirement_exists": "SCOPE_MISSING" in blocker_types
        and all(
            example.get("protected_secret_token", {}).get("allowed_scope")
            for example in examples.values()
            if "protected_secret_token" in example
        ),
        "agents_see_token_refs_only": _agents_see_refs_only(payload),
        "all_live_authority_flags_false": _all_authority_false(payload),
        "live_secret_capture_performed": False,
        "live_secret_store_performed": False,
        "live_secret_reveal_performed": False,
        "live_adapter_use_performed": False,
        "login_performed": False,
        "browser_access_performed": False,
        "external_action_performed": False,
        "raw_secret_in_read_models": False,
        "raw_secret_in_llm_context": False,
        "credentials_or_real_secrets_included": False,
        "raw_private_bodies_included": False,
        "network_used": False,
        "mac_sync_import_run": False,
        "mission_control_swift_changed": False,
        "git_push_pull_fetch_run": False,
        "content_hash": None,
    }


def build_protected_secret_intake_contract(*, generated_at: str | None = None) -> dict[str, Any]:
    generated_at = generated_at or DEFAULT_GENERATED_AT
    contract = build_contract()
    blockers = build_blockers()
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "contract_status": CONTRACT_STATUS,
        "generated_at": generated_at,
        "operator_markdown_mode": "ELIOPERATOR",
        "supported_secret_modes": SUPPORTED_SECRET_MODES,
        "secret_kinds": SECRET_KINDS,
        "receipt_actions": RECEIPT_ACTIONS,
        "model_schemas": _model_schemas(),
        "protected_secret_intake_contract": asdict(contract),
        "examples": build_examples(),
        "protected_secret_blockers_by_id": {
            blocker.blocker_id: asdict(blocker)
            for blocker in blockers
        },
        "protected_secret_elioperator_report": asdict(build_report()),
        "relationship_refs": {
            "pii_vault": "existing tokenization/vault precedent; not activated by this contract",
            "cassandra_pii_hooks": "pre-LLM tokenization precedent; agents see safe tokens only",
            "cross_lane_reusable_block_registry_contract": "PII/tokenization reusable block posture",
            "openclaw_sensitive_policy": "sensitive path and content boundary posture",
            "guardian_protected_access_gate_spec": "future protected access review gate",
            "workflow_execution_package_compiler": "future packages may reference secret refs, not raw values",
            "worker_routing_intelligence": "future secret-bound tasks route to proper worker with authority stripped",
            "business_ops_ledger": "receipt style precedent if future metadata-only receipts are persisted",
        },
        "allowed_scope": (
            "deterministic contract/read-model generation",
            "tests",
            "fake token refs only",
            "no real secrets",
        ),
        "authority_boundary": AUTHORITY_BOUNDARY,
    }
    payload["machine_proof"] = _machine_proof(payload)
    payload["machine_proof"]["content_hash"] = _content_hash(payload)
    return payload


def format_operator_markdown(payload: dict[str, Any]) -> str:
    report = payload["protected_secret_elioperator_report"]
    examples = payload["examples"]
    return "\n".join(
        [
            "# Protected Secret Intake Contract v0",
            "",
            "ELIOPERATOR: Enter Secret should create a protected reference. It must not put a value into chat, prompts, logs, cards, tests, or normal read-models.",
            "",
            "## What This Enables",
            "",
            report["what_this_enables"],
            "",
            "## What This Does Not Do Yet",
            "",
            report["what_this_does_not_do_yet"],
            "",
            "## How It Should Work",
            "",
            report["how_enter_secret_should_work"],
            "",
            "## Modes",
            "",
            "\n".join(f"- `{mode}`" for mode in payload["supported_secret_modes"]),
            "",
            "## Agent View",
            "",
            report["how_agents_see_tokens"],
            "",
            "Example protected ref:",
            f"- {examples['use_once_coupa_login_later']['agent_visible_context']['token_ref']}",
            "",
            "## Required Blocks",
            "",
            "- Raw value in normal chat is blocked.",
            "- Raw value in read-models is blocked.",
            "- Raw value in model context is blocked.",
            "- Raw value in logs or tests is blocked.",
            "- Adapter use requires future approval, scope, and receipts.",
            "",
            "## Boundary",
            "",
            "No live secret capture, store, reveal, adapter use, login, browser, external action, model exposure, credential handling, raw-body ingestion, Mac sync/import, Swift change, or push was added.",
            "",
            f"Next safe move: {payload['protected_secret_intake_contract']['next_safe_move']}",
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


def build_summary(payload: dict[str, Any], json_path: Path | None, operator_path: Path | None) -> dict[str, Any]:
    proof = payload["machine_proof"]
    return {
        "schema_version": payload["schema_version"],
        "read_model_id": payload["read_model_id"],
        "contract_status": payload["contract_status"],
        "json_path": str(json_path) if json_path else None,
        "operator_path": str(operator_path) if operator_path else None,
        "all_secret_modes_exist": proof["all_secret_modes_exist"],
        "secret_kinds_exist": proof["secret_kinds_exist"],
        "raw_secret_blockers_exist": proof["raw_secret_blockers_exist"],
        "llm_exposure_blocker_exists": proof["llm_exposure_blocker_exists"],
        "ttl_requirement_exists": proof["ttl_requirement_exists"],
        "scope_requirement_exists": proof["scope_requirement_exists"],
        "agents_see_token_refs_only": proof["agents_see_token_refs_only"],
        "all_live_authority_flags_false": proof["all_live_authority_flags_false"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export protected secret intake contract read-model.")
    parser.add_argument("--export-root", type=Path, default=DEFAULT_EXPORT_ROOT)
    parser.add_argument("--format", choices=("summary", "json"), default="json")
    args = parser.parse_args(argv)

    payload = build_protected_secret_intake_contract()
    json_path, operator_path = write_exports(payload, args.export_root)
    output = payload if args.format == "json" else build_summary(payload, json_path, operator_path)
    sys.stdout.write(stable_json(output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
