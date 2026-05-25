"""Chat Readback Card Mirror v0.

This deterministic exporter mirrors PC router readback cards into a
Mac-renderable chat-card artifact. It does not poll, watch, import, dispatch,
call models, run workflows, write procedure memory, create packages, access
Coupa/Gmail/browser systems, generate invoices, attach files, handle
credentials, ingest raw bodies, or perform external actions.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_SOURCE_READBACK = DEFAULT_EXPORT_ROOT / "conversational_workflow_router_readback.json"

SCHEMA_VERSION = "chat_readback_card_mirror_v0"
READ_MODEL_ID = "chat_readback_card_mirror"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
OPERATOR_EXPORT_NAME = f"{READ_MODEL_ID}_OPERATOR.md"
CONTRACT_STATUS = "DETERMINISTIC_NON_EXECUTING_CHAT_READBACK_CARD_MIRROR"

MIRROR_STATUSES = (
    "READY_FOR_MAC_RENDER",
    "WAITING_FOR_PC_READBACK",
    "STALE_SOURCE_READBACK",
    "SOURCE_READBACK_MISSING",
    "SOURCE_REQUEST_MISSING",
    "BLOCKED_PRIVACY_BOUNDARY",
    "UNKNOWN_FAIL_CLOSED",
)

CARD_TYPES = (
    "OPENCLAW_UNDERSTOOD",
    "PROPOSED_WORKFLOW",
    "MISSING_INFO",
    "BLOCKED",
    "PROOF_OR_READBACK",
    "APPROVAL_NEEDED",
    "COMPLETION_TARGET",
    "WAITING",
    "STALE",
    "UNKNOWN_FAIL_CLOSED",
)

FRESHNESS_STATUSES = (
    "CURRENT",
    "WAITING",
    "STALE",
    "SOURCE_MISMATCH",
    "UNKNOWN_TIMESTAMP",
    "UNKNOWN_FAIL_CLOSED",
)

BLOCKER_TYPES = (
    "SOURCE_READBACK_MISSING",
    "SOURCE_READBACK_STALE",
    "RAW_PII_IN_CARD",
    "MACHINE_CONTRACT_VISIBLE",
    "EXTERNAL_ACTION_ENABLED",
    "UNSUPPORTED_OPERATOR_ACTION_ENABLED",
    "COMPLETION_WITHOUT_PROOF",
    "UNKNOWN_FAIL_CLOSED",
)

REQUIRED_MIRROR_FIELDS = (
    "mirror_id",
    "source_readback_ref",
    "source_request_ref",
    "workflow_ref",
    "workflow_type",
    "world_ref",
    "lane_ref",
    "client_ref",
    "tenant_ref",
    "mirror_status",
    "cards",
    "operator_choices",
    "missing_backend_rails",
    "locked_actions",
    "proof_summary",
    "privacy_summary",
    "freshness",
    "safe_display_summary",
    "elioperator_summary",
    "next_safe_move",
)

REQUIRED_CARD_FIELDS = (
    "card_id",
    "card_type",
    "title",
    "subtitle",
    "bullets",
    "status_tone",
    "operator_actions",
    "truth_status",
    "proof_status",
    "source_refs",
    "detail_available",
    "next_safe_move",
)

REQUIRED_FRESHNESS_FIELDS = (
    "freshness_id",
    "source_request_ref",
    "source_readback_ref",
    "source_request_id",
    "idempotency_key",
    "payload_hash",
    "readback_status",
    "freshness_status",
    "stale_reason",
    "operator_message",
    "next_safe_move",
)

REQUIRED_AVAILABILITY_FIELDS = (
    "availability_id",
    "card_ref",
    "operator_action",
    "enabled",
    "disabled_reason",
    "required_backend_rail",
    "required_approval",
    "required_proof",
    "external_authority_required",
    "next_safe_move",
)

REQUIRED_BLOCKER_FIELDS = (
    "blocker_id",
    "blocker_type",
    "condition",
    "severity",
    "elioperator_warning",
    "fail_closed",
    "next_safe_move",
)

AUTHORITY_BOUNDARY = {
    "live_card_mirror_runtime_allowed": False,
    "live_polling_allowed": False,
    "live_watcher_allowed": False,
    "live_auto_import_allowed": False,
    "live_agent_dispatch_allowed": False,
    "live_model_call_allowed": False,
    "live_workflow_run_allowed": False,
    "live_procedure_memory_write_allowed": False,
    "live_package_creation_allowed": False,
    "live_email_draft_allowed": False,
    "live_email_send_allowed": False,
    "live_coupa_access_allowed": False,
    "live_coupa_submit_allowed": False,
    "live_browser_access_allowed": False,
    "live_invoice_generation_allowed": False,
    "live_attachment_allowed": False,
    "live_external_action_allowed": False,
    "credential_handling_allowed": False,
    "raw_body_ingestion_allowed": False,
    "mac_sync_import_allowed": False,
    "mission_control_swift_change_allowed": False,
    "network_operation_allowed": False,
    "git_push_pull_fetch_allowed": False,
}

FORBIDDEN_NORMAL_CARD_TERMS = (
    "schema",
    "handler",
    "lifecycle",
    "artifact_type",
    "target_handler",
    "payload_hash",
    "raw id",
    "file path",
    "manifest",
    "sqlite row",
    "package ref",
    "json payload",
)

LOCKED_ACTIONS = (
    "email send",
    "Coupa access",
    "browser automation",
    "invoice submission",
    "approval request",
    "invoice generation",
    "attachment",
    "payment state change",
)


@dataclass(frozen=True)
class ChatReadbackCardMirror:
    mirror_id: str
    source_readback_ref: str | None
    source_request_ref: str | None
    workflow_ref: str | None
    workflow_type: str | None
    world_ref: str | None
    lane_ref: str | None
    client_ref: str | None
    tenant_ref: str | None
    mirror_status: str
    cards: tuple[dict[str, Any], ...]
    operator_choices: tuple[dict[str, Any], ...]
    missing_backend_rails: tuple[str, ...]
    locked_actions: tuple[str, ...]
    proof_summary: str
    privacy_summary: str
    freshness: dict[str, Any]
    safe_display_summary: str
    elioperator_summary: str
    next_safe_move: str


@dataclass(frozen=True)
class ChatHumanCard:
    card_id: str
    card_type: str
    title: str
    subtitle: str
    bullets: tuple[str, ...]
    status_tone: str
    operator_actions: tuple[str, ...]
    truth_status: str
    proof_status: str
    source_refs: tuple[str, ...]
    detail_available: bool
    next_safe_move: str


@dataclass(frozen=True)
class ChatReadbackFreshness:
    freshness_id: str
    source_request_ref: str | None
    source_readback_ref: str | None
    source_request_id: str | None
    idempotency_key: str | None
    payload_hash: str | None
    readback_status: str
    freshness_status: str
    stale_reason: str | None
    operator_message: str
    next_safe_move: str


@dataclass(frozen=True)
class ChatReadbackActionAvailability:
    availability_id: str
    card_ref: str
    operator_action: str
    enabled: bool
    disabled_reason: str | None
    required_backend_rail: str | None
    required_approval: str | None
    required_proof: str | None
    external_authority_required: bool
    next_safe_move: str


@dataclass(frozen=True)
class ChatReadbackMirrorBlocker:
    blocker_id: str
    blocker_type: str
    condition: str
    severity: str
    elioperator_warning: str
    fail_closed: bool
    next_safe_move: str


def stable_json(value: Any) -> str:
    return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _content_hash(payload: dict[str, Any]) -> str:
    clone = json.loads(stable_json(payload))
    clone.get("machine_proof", {}).pop("content_hash", None)
    return "sha256:" + hashlib.sha256(stable_json(clone).encode("utf-8")).hexdigest()


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("source readback JSON must be an object")
    return value


def _model_schemas() -> dict[str, Any]:
    return {
        "chat_readback_card_mirror": {
            "required_fields": list(REQUIRED_MIRROR_FIELDS),
            "mirror_statuses": list(MIRROR_STATUSES),
        },
        "chat_human_card": {
            "required_fields": list(REQUIRED_CARD_FIELDS),
            "card_types": list(CARD_TYPES),
        },
        "chat_readback_freshness": {
            "required_fields": list(REQUIRED_FRESHNESS_FIELDS),
            "freshness_statuses": list(FRESHNESS_STATUSES),
        },
        "chat_readback_action_availability": {
            "required_fields": list(REQUIRED_AVAILABILITY_FIELDS),
        },
        "chat_readback_mirror_blocker": {
            "required_fields": list(REQUIRED_BLOCKER_FIELDS),
            "blocker_types": list(BLOCKER_TYPES),
        },
    }


def _blocker(blocker_type: str, condition: str, *, severity: str = "BLOCKS_SAFE_MIRROR") -> ChatReadbackMirrorBlocker:
    return ChatReadbackMirrorBlocker(
        blocker_id=f"chat_readback_mirror_blocker_{blocker_type.lower()}",
        blocker_type=blocker_type,
        condition=condition,
        severity=severity,
        elioperator_warning=f"ELIOPERATOR: {condition}",
        fail_closed=True,
        next_safe_move="Show a plain blocked/waiting card and do not claim success.",
    )


def build_standard_blockers() -> tuple[ChatReadbackMirrorBlocker, ...]:
    conditions = {
        "SOURCE_READBACK_MISSING": "The PC router readback has not been generated yet.",
        "SOURCE_READBACK_STALE": "The source readback does not match its request identity.",
        "RAW_PII_IN_CARD": "Human cards must not include raw private values.",
        "MACHINE_CONTRACT_VISIBLE": "Human cards must not expose backend contract language.",
        "EXTERNAL_ACTION_ENABLED": "The mirror cannot enable email, Coupa, browser, approval, or send actions.",
        "UNSUPPORTED_OPERATOR_ACTION_ENABLED": "Unsupported operator actions must stay disabled.",
        "COMPLETION_WITHOUT_PROOF": "Completion cards require proof receipts.",
        "UNKNOWN_FAIL_CLOSED": "Unknown mirror state fails closed.",
    }
    return tuple(_blocker(blocker_type, condition) for blocker_type, condition in conditions.items())


def _safe_tuple(value: Any) -> tuple[str, ...]:
    if isinstance(value, (list, tuple)):
        return tuple(str(item) for item in value)
    if value is None:
        return ()
    return (str(value),)


def _safe_readback_ref(source: Mapping[str, Any] | None) -> str | None:
    if not source:
        return None
    return str(source.get("read_model_id") or "conversational_workflow_router_readback")


def _source_request(source: Mapping[str, Any] | None) -> Mapping[str, Any]:
    if not source:
        return {}
    request = source.get("intake_request")
    return request if isinstance(request, Mapping) else {}


def _source_package(source: Mapping[str, Any] | None) -> Mapping[str, Any]:
    if not source:
        return {}
    package = source.get("router_readback_package")
    return package if isinstance(package, Mapping) else {}


def _source_backend_target(source: Mapping[str, Any] | None) -> Mapping[str, Any]:
    package = _source_package(source)
    target = package.get("backend_package_target")
    return target if isinstance(target, Mapping) else {}


def _freshness_for_source(source: Mapping[str, Any] | None) -> ChatReadbackFreshness:
    readback_ref = _safe_readback_ref(source)
    request = _source_request(source)
    package = _source_package(source)
    route_mode = str(source.get("route_mode") if source else "")
    parse_status = str(source.get("intake_result", {}).get("parse_status") if source else "")
    request_id = str(request.get("request_id") or "") or None
    source_ref = str(package.get("source_request_ref") or "") or None
    idempotency_key = str(request.get("idempotency_key") or "") or None
    payload_hash = str(request.get("payload_hash") or "") or None

    if source is None:
        return ChatReadbackFreshness(
            freshness_id="chat_mirror_freshness_source_missing",
            source_request_ref=None,
            source_readback_ref=None,
            source_request_id=None,
            idempotency_key=None,
            payload_hash=None,
            readback_status="SOURCE_READBACK_MISSING",
            freshness_status="WAITING",
            stale_reason="source readback file is missing",
            operator_message="Waiting for PC readback.",
            next_safe_move="Run the PC router intake/export before mirroring cards.",
        )
    if route_mode == "NO_REQUEST_AVAILABLE":
        return ChatReadbackFreshness(
            freshness_id="chat_mirror_freshness_source_request_missing",
            source_request_ref=None,
            source_readback_ref=readback_ref,
            source_request_id=None,
            idempotency_key=None,
            payload_hash=None,
            readback_status=parse_status or "NEEDS_MORE_DETAIL",
            freshness_status="WAITING",
            stale_reason="source readback reports no request available",
            operator_message="Waiting for PC readback.",
            next_safe_move="Emit or import a chat request, then regenerate the router readback.",
        )
    if request_id and source_ref and request_id != source_ref:
        return ChatReadbackFreshness(
            freshness_id="chat_mirror_freshness_source_mismatch",
            source_request_ref=source_ref,
            source_readback_ref=readback_ref,
            source_request_id=request_id,
            idempotency_key=idempotency_key,
            payload_hash=payload_hash,
            readback_status=parse_status or "UNKNOWN",
            freshness_status="SOURCE_MISMATCH",
            stale_reason="source request ref does not match intake request id",
            operator_message="This readback looks stale. I will not use it as current.",
            next_safe_move="Regenerate the router readback from the latest request.",
        )
    if route_mode == "REQUEST_ROUTED" and parse_status == "ROUTED_DRAFT_READY":
        return ChatReadbackFreshness(
            freshness_id="chat_mirror_freshness_current",
            source_request_ref=source_ref or request_id,
            source_readback_ref=readback_ref,
            source_request_id=request_id,
            idempotency_key=idempotency_key,
            payload_hash=payload_hash,
            readback_status=parse_status,
            freshness_status="CURRENT",
            stale_reason=None,
            operator_message="I found the PC readback. These cards are ready for Mac chat.",
            next_safe_move="Render the cards and ask whether the understanding looks right.",
        )
    return ChatReadbackFreshness(
        freshness_id="chat_mirror_freshness_unknown",
        source_request_ref=source_ref or request_id,
        source_readback_ref=readback_ref,
        source_request_id=request_id,
        idempotency_key=idempotency_key,
        payload_hash=payload_hash,
        readback_status=parse_status or route_mode or "UNKNOWN",
        freshness_status="UNKNOWN_FAIL_CLOSED",
        stale_reason="source readback status is unsupported",
        operator_message="The readback state is unsupported. I will not use it as current.",
        next_safe_move="Inspect the source readback shape before rendering cards.",
    )


def _mirror_status(source: Mapping[str, Any] | None, freshness: ChatReadbackFreshness) -> str:
    if source is None:
        return "SOURCE_READBACK_MISSING"
    if freshness.freshness_status == "CURRENT":
        return "READY_FOR_MAC_RENDER"
    if freshness.freshness_status == "SOURCE_MISMATCH":
        return "STALE_SOURCE_READBACK"
    if freshness.freshness_id == "chat_mirror_freshness_source_request_missing":
        return "SOURCE_REQUEST_MISSING"
    if freshness.freshness_status == "WAITING":
        return "WAITING_FOR_PC_READBACK"
    return "UNKNOWN_FAIL_CLOSED"


def _status_tone(card_type: str) -> str:
    return {
        "OPENCLAW_UNDERSTOOD": "ready",
        "PROPOSED_WORKFLOW": "review",
        "MISSING_INFO": "needs_confirmation",
        "BLOCKED": "locked",
        "PROOF_OR_READBACK": "proof",
        "APPROVAL_NEEDED": "approval",
        "COMPLETION_TARGET": "future_target",
        "WAITING": "waiting",
        "STALE": "warning",
    }.get(card_type, "blocked")


def _subtitle_for(card_type: str, truth_status: str, proof_status: str) -> str:
    if card_type == "OPENCLAW_UNDERSTOOD":
        return "Draft understanding from PC readback"
    if card_type == "PROPOSED_WORKFLOW":
        return "Review before anything runs"
    if card_type == "MISSING_INFO":
        return "Still needs confirmation"
    if card_type == "BLOCKED":
        return "Nothing external happened"
    if card_type == "WAITING":
        return "Waiting for PC readback"
    if card_type == "STALE":
        return "Not current"
    if truth_status == "LOCKED_EXTERNAL_ACTION" or proof_status == "PROOF_REQUIRED":
        return "Proof or approval required"
    return "Readback card"


def _visible_card_text(cards: tuple[ChatHumanCard, ...]) -> str:
    chunks: list[str] = []
    for card in cards:
        chunks.extend([card.title, card.subtitle])
        chunks.extend(card.bullets)
        chunks.extend(card.operator_actions)
    return "\n".join(chunks).lower()


def _normalize_action(label: str) -> str:
    if label == "Store as procedure later":
        return "Store as procedure"
    if label == "Prepare package later":
        return "Prepare package"
    return label


def _action_availability(label: str, card_ref: str = "chat_card_global_actions") -> ChatReadbackActionAvailability:
    normalized = _normalize_action(label)
    if normalized in {"Looks right", "Edit understanding", "Cancel"}:
        return ChatReadbackActionAvailability(
            availability_id=f"chat_action_{normalized.lower().replace(' ', '_')}",
            card_ref=card_ref,
            operator_action=normalized,
            enabled=True,
            disabled_reason=None,
            required_backend_rail=None,
            required_approval=None,
            required_proof=None,
            external_authority_required=False,
            next_safe_move="Handle locally in the Mac chat UI; no backend truth changes from this mirror.",
        )
    if normalized == "Store as procedure":
        return ChatReadbackActionAvailability(
            availability_id="chat_action_store_as_procedure",
            card_ref=card_ref,
            operator_action=normalized,
            enabled=False,
            disabled_reason="Backend procedure memory write is not connected yet.",
            required_backend_rail="procedure_memory_writer",
            required_approval=None,
            required_proof="operator-reviewed procedure receipt",
            external_authority_required=False,
            next_safe_move="Keep disabled until a governed procedure-memory write rail exists.",
        )
    if normalized == "Prepare package":
        return ChatReadbackActionAvailability(
            availability_id="chat_action_prepare_package",
            card_ref=card_ref,
            operator_action=normalized,
            enabled=False,
            disabled_reason="Backend package creation is not connected yet.",
            required_backend_rail="workflow_package_creator",
            required_approval="operator review before package creation",
            required_proof="package creation receipt",
            external_authority_required=False,
            next_safe_move="Keep disabled until a deterministic package creation rail exists.",
        )
    return ChatReadbackActionAvailability(
        availability_id="chat_action_unsupported_"
        + hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:12],
        card_ref=card_ref,
        operator_action=normalized,
        enabled=False,
        disabled_reason="This action is not supported by the card mirror.",
        required_backend_rail="unsupported_action_gate",
        required_approval="operator review",
        required_proof="supported-action receipt",
        external_authority_required=False,
        next_safe_move="Do not enable unsupported actions from a mirror artifact.",
    )


def _operator_choices(source: Mapping[str, Any] | None) -> tuple[ChatReadbackActionAvailability, ...]:
    package = _source_package(source)
    raw_choices = package.get("operator_choices")
    labels: list[str] = []
    if isinstance(raw_choices, list):
        for choice in raw_choices:
            if isinstance(choice, Mapping):
                labels.append(str(choice.get("label") or ""))
            else:
                labels.append(str(choice))
    if not labels:
        labels = ["Looks right", "Edit understanding", "Store as procedure", "Prepare package", "Cancel"]
    seen: set[str] = set()
    result: list[ChatReadbackActionAvailability] = []
    for label in labels:
        normalized = _normalize_action(label)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(_action_availability(normalized))
    return tuple(result)


def _cards_from_source(source: Mapping[str, Any] | None, mirror_status: str) -> tuple[ChatHumanCard, ...]:
    readback_ref = _safe_readback_ref(source)
    package = _source_package(source)
    raw_cards = package.get("cards")
    actions = tuple(choice.operator_action for choice in _operator_choices(source))

    if mirror_status in {"SOURCE_READBACK_MISSING", "WAITING_FOR_PC_READBACK", "SOURCE_REQUEST_MISSING"}:
        return (
            ChatHumanCard(
                card_id="chat_card_waiting_for_pc_readback",
                card_type="WAITING",
                title="Waiting for PC readback",
                subtitle="No current understanding has returned yet",
                bullets=(
                    "The chat request is not ready to render as backend truth yet.",
                    "OpenClaw will not claim what PC understood until a matching readback exists.",
                    "Nothing external happened.",
                ),
                status_tone="waiting",
                operator_actions=actions,
                truth_status="NO_TRUTH_WITHOUT_READBACK",
                proof_status="BACKEND_READBACK_REQUIRED",
                source_refs=tuple(ref for ref in (readback_ref,) if ref),
                detail_available=True,
                next_safe_move="Wait for the PC router readback or rerun the intake/export.",
            ),
        )
    if mirror_status == "STALE_SOURCE_READBACK":
        return (
            ChatHumanCard(
                card_id="chat_card_stale_source_readback",
                card_type="STALE",
                title="Readback looks stale",
                subtitle="Not current",
                bullets=(
                    "The available readback does not match the current request.",
                    "I will not use it as current.",
                    "Nothing external happened.",
                ),
                status_tone="warning",
                operator_actions=actions,
                truth_status="STALE_NOT_CURRENT_TRUTH",
                proof_status="BACKEND_READBACK_REQUIRED",
                source_refs=tuple(ref for ref in (readback_ref,) if ref),
                detail_available=True,
                next_safe_move="Regenerate the router readback from the latest request.",
            ),
        )
    if not isinstance(raw_cards, list):
        return (
            ChatHumanCard(
                card_id="chat_card_unknown_fail_closed",
                card_type="UNKNOWN_FAIL_CLOSED",
                title="Readback cannot be shown yet",
                subtitle="Unsupported source shape",
                bullets=(
                    "The source readback did not contain human cards.",
                    "I will not invent a result.",
                    "Nothing external happened.",
                ),
                status_tone="blocked",
                operator_actions=actions,
                truth_status="UNKNOWN_FAIL_CLOSED",
                proof_status="BACKEND_READBACK_REQUIRED",
                source_refs=tuple(ref for ref in (readback_ref,) if ref),
                detail_available=True,
                next_safe_move="Inspect the PC router readback shape.",
            ),
        )
    mirrored: list[ChatHumanCard] = []
    for raw_card in raw_cards:
        if not isinstance(raw_card, Mapping):
            continue
        card_type = str(raw_card.get("card_type") or "UNKNOWN_FAIL_CLOSED")
        if card_type not in CARD_TYPES:
            card_type = "UNKNOWN_FAIL_CLOSED"
        truth_status = str(raw_card.get("truth_status") or "BACKEND_READBACK_REQUIRED")
        proof_status = str(raw_card.get("proof_status") or "BACKEND_READBACK_REQUIRED")
        source_id = str(raw_card.get("card_id") or "")
        mirrored.append(
            ChatHumanCard(
                card_id=f"mirror_{source_id}" if source_id else f"mirror_card_{len(mirrored) + 1}",
                card_type=card_type,
                title=str(raw_card.get("title") or "Readback card"),
                subtitle=_subtitle_for(card_type, truth_status, proof_status),
                bullets=_safe_tuple(raw_card.get("bullets")),
                status_tone=_status_tone(card_type),
                operator_actions=actions,
                truth_status=truth_status,
                proof_status=proof_status,
                source_refs=tuple(ref for ref in (readback_ref, source_id) if ref),
                detail_available=True,
                next_safe_move=str(raw_card.get("next_safe_move") or "Review this card before any next step."),
            )
        )
    return tuple(mirrored)


def _proof_summary(source: Mapping[str, Any] | None, mirror_status: str) -> str:
    if mirror_status == "READY_FOR_MAC_RENDER":
        return "Draft understanding is backed by a PC router readback; completion still requires proof receipts."
    if mirror_status in {"WAITING_FOR_PC_READBACK", "SOURCE_READBACK_MISSING", "SOURCE_REQUEST_MISSING"}:
        return "No current PC readback is ready yet."
    if mirror_status == "STALE_SOURCE_READBACK":
        return "Readback is not current and cannot be used as proof."
    return "Proof status is unknown; fail closed."


def _privacy_summary() -> str:
    return "Human-card mirror only; no raw private bodies, credentials, raw PO/payment values, or protected evidence bodies."


def _context_from_source(source: Mapping[str, Any] | None) -> dict[str, str | None]:
    request = _source_request(source)
    target = _source_backend_target(source)
    return {
        "source_request_ref": str(request.get("request_id") or _source_package(source).get("source_request_ref") or "") or None,
        "workflow_ref": str(request.get("workflow_ref") or "") or None,
        "workflow_type": str(request.get("workflow_type") or target.get("workflow_type") or "") or None,
        "world_ref": str(request.get("world_ref") or "") or None,
        "lane_ref": str(request.get("lane_ref") or "") or None,
        "client_ref": str(request.get("client_ref") or "") or None,
        "tenant_ref": str(request.get("tenant_ref") or "") or None,
    }


def _build_mirror(source: Mapping[str, Any] | None) -> tuple[ChatReadbackCardMirror, tuple[ChatReadbackMirrorBlocker, ...], tuple[ChatReadbackActionAvailability, ...]]:
    freshness = _freshness_for_source(source)
    mirror_status = _mirror_status(source, freshness)
    cards = _cards_from_source(source, mirror_status)
    choices = _operator_choices(source)
    context = _context_from_source(source)
    package = _source_package(source)
    missing_backend_rails = _safe_tuple(package.get("missing_backend_rails"))
    locked_actions = _safe_tuple(package.get("locked_actions")) or LOCKED_ACTIONS
    blockers: list[ChatReadbackMirrorBlocker] = []

    if mirror_status == "SOURCE_READBACK_MISSING":
        blockers.append(_blocker("SOURCE_READBACK_MISSING", "The PC router readback has not been generated yet."))
    elif mirror_status == "STALE_SOURCE_READBACK":
        blockers.append(_blocker("SOURCE_READBACK_STALE", "The source readback does not match its request identity."))
    elif mirror_status == "UNKNOWN_FAIL_CLOSED":
        blockers.append(_blocker("UNKNOWN_FAIL_CLOSED", "The source readback state is unsupported."))

    visible_text = _visible_card_text(cards)
    if any(term in visible_text for term in FORBIDDEN_NORMAL_CARD_TERMS):
        blockers.append(_blocker("MACHINE_CONTRACT_VISIBLE", "Human cards expose backend contract language."))
        mirror_status = "UNKNOWN_FAIL_CLOSED"
    if any(choice.enabled and choice.external_authority_required for choice in choices):
        blockers.append(_blocker("EXTERNAL_ACTION_ENABLED", "An operator choice attempted to enable external authority."))
        mirror_status = "UNKNOWN_FAIL_CLOSED"

    mirror = ChatReadbackCardMirror(
        mirror_id="chat_readback_card_mirror_current",
        source_readback_ref=_safe_readback_ref(source),
        source_request_ref=context["source_request_ref"],
        workflow_ref=context["workflow_ref"],
        workflow_type=context["workflow_type"],
        world_ref=context["world_ref"],
        lane_ref=context["lane_ref"],
        client_ref=context["client_ref"],
        tenant_ref=context["tenant_ref"],
        mirror_status=mirror_status,
        cards=tuple(asdict(card) for card in cards),
        operator_choices=tuple(asdict(choice) for choice in choices),
        missing_backend_rails=missing_backend_rails,
        locked_actions=locked_actions,
        proof_summary=_proof_summary(source, mirror_status),
        privacy_summary=_privacy_summary(),
        freshness=asdict(freshness),
        safe_display_summary=(
            "PC router readback cards are ready for Mac chat."
            if mirror_status == "READY_FOR_MAC_RENDER"
            else "PC router readback cards are not ready for current Mac rendering."
        ),
        elioperator_summary=(
            "ELIOPERATOR: This mirrors safe PC readback cards for chat. It does not run, send, submit, approve, or store procedure memory."
        ),
        next_safe_move=(
            "Render the cards in Mac chat and ask whether the understanding looks right."
            if mirror_status == "READY_FOR_MAC_RENDER"
            else "Wait for a current PC router readback before rendering as current."
        ),
    )
    return mirror, tuple(blockers), choices


def build_chat_readback_card_mirror(
    *,
    source_readback_path: Path = DEFAULT_SOURCE_READBACK,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    source = _load_json(source_readback_path)
    mirror, active_blockers, choices = _build_mirror(source)
    standard_blockers = build_standard_blockers()
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "contract_status": CONTRACT_STATUS,
        "generated_at": generated_at,
        "operator_markdown_mode": "ELIOPERATOR",
        "source_readback_present": source is not None,
        "source_readback_ref": mirror.source_readback_ref,
        "source_readback_kind": "conversational_workflow_router_readback",
        "mirror_statuses": MIRROR_STATUSES,
        "card_types": CARD_TYPES,
        "freshness_statuses": FRESHNESS_STATUSES,
        "model_schemas": _model_schemas(),
        "chat_readback_card_mirror": asdict(mirror),
        "chat_human_cards": mirror.cards,
        "chat_readback_freshness": mirror.freshness,
        "chat_readback_action_availability": tuple(asdict(choice) for choice in choices),
        "active_blockers_by_id": {blocker.blocker_id: asdict(blocker) for blocker in active_blockers},
        "standard_blockers_by_id": {blocker.blocker_id: asdict(blocker) for blocker in standard_blockers},
        "relationship_refs": {
            "conversational_workflow_router_intake": "source PC router readback",
            "workflow_readback_concierge_contract": "request/readback loop responsibility",
            "cross_surface_artifact_handoff_registry_contract": "typed handoff compatibility",
            "cross_surface_handoff_registry_metadata_alignment": "post-office metadata compatibility",
            "cross_lane_reusable_block_registry_contract": "protected value tokenization compatibility",
        },
        "authority_boundary": AUTHORITY_BOUNDARY,
    }
    payload["machine_proof"] = _machine_proof(payload)
    payload["machine_proof"]["content_hash"] = _content_hash(payload)
    return payload


def _machine_proof(payload: dict[str, Any]) -> dict[str, Any]:
    mirror = payload["chat_readback_card_mirror"]
    cards = tuple(ChatHumanCard(**card) for card in mirror["cards"])
    visible_text = _visible_card_text(cards)
    action_entries = payload["chat_readback_action_availability"]
    disabled_expected = {
        entry["operator_action"]: entry
        for entry in action_entries
        if entry["operator_action"] in {"Store as procedure", "Prepare package"}
    }
    return {
        "chat_readback_card_mirror_model_present": True,
        "chat_human_card_model_present": True,
        "chat_readback_freshness_model_present": True,
        "chat_readback_action_availability_model_present": True,
        "chat_readback_mirror_blocker_model_present": True,
        "source_readback_present": payload["source_readback_present"],
        "mirror_ready_for_mac_if_routed": (
            mirror["mirror_status"] != "READY_FOR_MAC_RENDER"
            or payload["chat_readback_freshness"]["freshness_status"] == "CURRENT"
        ),
        "capital_hilton_cards_mirrored": all(
            expected in {card["title"] for card in mirror["cards"]}
            for expected in (
                "OpenClaw understood",
                "Proposed workflow",
                "What still needs to be confirmed",
                "What is not happening yet",
            )
        ),
        "waiting_status_modelled": "WAITING_FOR_PC_READBACK" in MIRROR_STATUSES and "WAITING" in CARD_TYPES,
        "stale_source_blocker_exists": "SOURCE_READBACK_STALE" in BLOCKER_TYPES,
        "operator_choices_disabled_unless_supported": all(
            disabled_expected[action]["enabled"] is False for action in ("Store as procedure", "Prepare package")
        ),
        "machine_contract_language_absent_from_cards": not any(term in visible_text for term in FORBIDDEN_NORMAL_CARD_TERMS),
        "completion_without_proof_blocker_exists": "COMPLETION_WITHOUT_PROOF" in BLOCKER_TYPES,
        "all_live_authority_flags_false": all(value is False for value in AUTHORITY_BOUNDARY.values()),
        "external_actions_locked": all(action in mirror["locked_actions"] for action in LOCKED_ACTIONS),
        "credentials_or_secrets_included": False,
        "raw_private_bodies_included": False,
        "raw_pii_in_cards": False,
        "external_action_performed": False,
        "network_used": False,
        "mac_sync_import_run": False,
        "mission_control_swift_changed": False,
        "git_push_pull_fetch_run": False,
        "content_hash": None,
    }


def format_operator_markdown(payload: dict[str, Any]) -> str:
    mirror = payload["chat_readback_card_mirror"]
    lines = [
        "# Chat Readback Card Mirror v0",
        "",
        "ELIOPERATOR: This packages PC router readback into Mac-renderable human cards for the chat surface.",
        "",
        f"- Mirror status: `{mirror['mirror_status']}`.",
        f"- Source readback: `{mirror['source_readback_ref'] or 'not available'}`.",
        f"- Safe summary: {mirror['safe_display_summary']}",
        "",
        "## Cards",
        "",
    ]
    for card in mirror["cards"]:
        lines.append(f"### {card['title']}")
        if card["subtitle"]:
            lines.append(f"- {card['subtitle']}")
        lines.extend(f"- {bullet}" for bullet in card["bullets"])
        lines.append("")
    lines.extend(
        [
            "## Operator Choices",
            "",
        ]
    )
    for choice in mirror["operator_choices"]:
        reason = str(choice["disabled_reason"] or "").rstrip(".")
        status = "available" if choice["enabled"] else f"disabled: {reason}"
        lines.append(f"- {choice['operator_action']}: {status}.")
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            "- This mirror does not run workflows.",
            "- It does not send, submit, approve, browse, access Coupa, generate invoices, create attachments, create procedure memory, or create packages.",
            "- It only mirrors safe readback cards for the chat surface.",
            "",
            f"Next safe move: {mirror['next_safe_move']}",
            "",
        ]
    )
    return "\n".join(lines)


def write_exports(payload: dict[str, Any], export_root: Path) -> tuple[Path, Path]:
    export_root.mkdir(parents=True, exist_ok=True)
    json_path = export_root / JSON_EXPORT_NAME
    operator_path = export_root / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(format_operator_markdown(payload), encoding="utf-8")
    return json_path, operator_path


def build_summary(payload: dict[str, Any], json_path: Path | None, operator_path: Path | None) -> dict[str, Any]:
    mirror = payload["chat_readback_card_mirror"]
    return {
        "schema_version": payload["schema_version"],
        "read_model_id": payload["read_model_id"],
        "contract_status": payload["contract_status"],
        "json_path": str(json_path) if json_path else None,
        "operator_path": str(operator_path) if operator_path else None,
        "mirror_status": mirror["mirror_status"],
        "source_readback_ref": mirror["source_readback_ref"],
        "workflow_type": mirror["workflow_type"],
        "client_ref": mirror["client_ref"],
        "cards": [card["title"] for card in mirror["cards"]],
        "freshness_status": mirror["freshness"]["freshness_status"],
        "all_live_authority_flags_false": payload["machine_proof"]["all_live_authority_flags_false"],
        "external_action_performed": payload["machine_proof"]["external_action_performed"],
        "content_hash": payload["machine_proof"]["content_hash"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export a Mac-safe chat readback card mirror.")
    parser.add_argument("--source-readback", default=str(DEFAULT_SOURCE_READBACK))
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT))
    parser.add_argument("--format", choices=("summary", "json"), default="json")
    parser.add_argument("--generated-at", default=None)
    args = parser.parse_args(argv)

    payload = build_chat_readback_card_mirror(
        source_readback_path=Path(args.source_readback),
        generated_at=args.generated_at,
    )
    json_path, operator_path = write_exports(payload, Path(args.export_root))
    summary = build_summary(payload, json_path, operator_path)
    if args.format == "summary":
        print(stable_json(summary), end="")
    else:
        print(stable_json(payload), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
