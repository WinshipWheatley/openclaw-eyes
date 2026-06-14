"""Repo B Telegram Intake Bridge v0.

This deterministic Repo A read-model evaluates Repo B Telegram listener and
message-routing code as a possible alternate operator intake surface. Repo B has
useful message-envelope, command-normalization, session, follow-up, and handoff
patterns, but the legacy modules also start live Telegram polling, read bot-token
environment names, reply outbound, write pending state, and can resume actions.

This bridge is intake-only and fixture-only in v0. It does not import or execute
Repo B code, start Telegram listeners, post replies, access bot tokens, mutate
queues, dispatch pending actions, call agents, run workflows, access external
systems, ingest raw private bodies, mutate Mission Control Swift, sync/import Mac
files, or push.
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
REPO_B_ROOT = Path("/home/openclaw_external/openclaw-runtime")

SCHEMA_VERSION = "repo_b_telegram_intake_bridge_v0"
READ_MODEL_ID = "repo_b_telegram_intake_bridge"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
OPERATOR_EXPORT_NAME = f"{READ_MODEL_ID}_OPERATOR.md"
CONTRACT_STATUS = "DETERMINISTIC_INTAKE_ONLY_TELEGRAM_BRIDGE"

POSTURES = (
    "INTAKE_ONLY_BRIDGE",
    "REBUILD_SMALL_SUBSET_IN_REPO_A",
    "REFERENCE_ONLY",
    "UNSAFE_DO_NOT_CONNECT",
    "ALREADY_SUPERSEDED",
    "UNKNOWN_NEEDS_DEEPER_REVIEW",
)

CAPABILITY_TYPES = (
    "OPERATOR_MESSAGE_INTAKE",
    "COMMAND_NORMALIZATION",
    "SESSION_MAPPING",
    "FOLLOWUP_INTENT_PARSE",
    "REQUEST_ENVELOPE_CREATION",
    "INTAKE_DIRECTORY_WRITE",
    "OUTBOUND_REPLY",
    "PENDING_ACTION_DISPATCH",
    "UNKNOWN",
)

TARGET_REQUEST_TYPES = (
    "CHAT_REQUEST",
    "FILE_METADATA_REQUEST_FUTURE",
    "SECRET_INTAKE_REQUEST_FUTURE",
    "WORKER_DISPATCH_REQUEST_FUTURE",
    "UNKNOWN_FAIL_CLOSED",
)

READBACK_STATUSES = (
    "INTAKE_MAPPING_READY",
    "FIXTURE_MAPPING_READY",
    "BLOCKED_OUTBOUND_TELEGRAM",
    "BLOCKED_TOKEN_REQUIRED",
    "BLOCKED_LIVE_LISTENER",
    "BLOCKED_PRIVACY_BOUNDARY",
    "UNKNOWN_FAIL_CLOSED",
)

BLOCKER_TYPES = (
    "LIVE_TELEGRAM_LISTENER_START_ATTEMPTED",
    "TELEGRAM_OUTBOUND_ATTEMPTED",
    "BOT_TOKEN_INCLUDED",
    "RAW_PRIVATE_MESSAGE_EXPOSED",
    "PENDING_ACTION_DISPATCH_ATTEMPTED",
    "QUEUE_MUTATION_ATTEMPTED",
    "EXTERNAL_ACTION_ATTEMPTED",
    "CREDENTIAL_OR_ENV_MUTATION_ATTEMPTED",
    "UNSCOPED_PUBLIC_CHAT_SURFACE",
    "UNKNOWN_FAIL_CLOSED",
)

AUTHORITY_BOUNDARY = {
    "live_telegram_listener_allowed": False,
    "live_telegram_outbound_allowed": False,
    "live_bot_token_access_allowed": False,
    "live_pending_action_dispatch_allowed": False,
    "live_queue_mutation_allowed": False,
    "live_external_action_allowed": False,
    "credential_handling_allowed": False,
    "raw_body_ingestion_allowed": False,
    "network_allowed": False,
    "repo_b_runtime_execution_allowed": False,
    "repo_b_service_start_allowed": False,
    "telegram_voice_download_allowed": False,
    "telegram_voice_output_allowed": False,
    "telegram_public_chat_activation_allowed": False,
    "mac_sync_import_allowed": False,
    "mission_control_swift_change_allowed": False,
    "git_push_pull_fetch_allowed": False,
}

COMMON_BLOCKED_ACTIONS = (
    "start live Telegram bot, listener, watcher, or daemon",
    "send, post, reply, or edit Telegram messages",
    "read bot tokens or credential values",
    "dispatch pending actions",
    "mutate queues or approval state",
    "start Repo B runtime services",
    "trigger agents, workflows, or external systems",
    "include raw private Telegram message bodies in normal read-models",
)


@dataclass(frozen=True)
class RepoBTelegramIntakeBridgeDecision:
    decision_id: str
    source_module: str
    source_path: str
    apparent_value: str
    dependencies: tuple[str, ...]
    recommended_posture: str
    wrapper_scope: tuple[str, ...]
    rebuild_scope: tuple[str, ...]
    blocked_items: tuple[str, ...]
    privacy_boundary: str
    next_safe_move: str


@dataclass(frozen=True)
class TelegramIntakeCapability:
    capability_id: str
    source_module_ref: str
    capability_type: str
    description: str
    inputs_required: tuple[str, ...]
    outputs_produced: tuple[str, ...]
    external_authority: bool
    credential_required: bool
    outbound_required: bool
    wrapper_allowed: bool
    next_safe_move: str


@dataclass(frozen=True)
class TelegramIntakeEnvelope:
    envelope_id: str
    source_surface: str
    source_channel: str
    source_message_ref: str
    operator_ref: str
    chat_ref: str
    normalized_message: str
    command_hint: str
    world_ref: str
    lane_ref: str
    workflow_ref: str
    privacy_class: str
    authority_boundary: dict[str, bool]
    next_safe_move: str


@dataclass(frozen=True)
class TelegramToOpenClawRequestMapping:
    mapping_id: str
    intake_envelope_ref: str
    target_request_type: str
    target_request_shape: dict[str, Any]
    required_fields: tuple[str, ...]
    excluded_fields: tuple[str, ...]
    tokenization_required: bool
    output_path_policy: str
    next_safe_move: str


@dataclass(frozen=True)
class TelegramIntakeReadback:
    readback_id: str
    envelope_ref: str
    status: str
    safe_summary: str
    mapped_request_ref: str
    blocked_items: tuple[str, ...]
    operator_message: str
    how_to_fix: str
    next_safe_move: str


@dataclass(frozen=True)
class TelegramIntakeBlocker:
    blocker_id: str
    blocker_type: str
    condition: str
    severity: str
    elioperator_warning: str
    fail_closed: bool
    next_safe_move: str


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _stable_id(prefix: str, *parts: object) -> str:
    digest = hashlib.sha256("\0".join(str(part) for part in parts).encode("utf-8")).hexdigest()
    return f"{prefix}_{digest[:16]}"


def _repo_b_path(filename: str) -> str:
    return str(REPO_B_ROOT / filename)


def _safe_message(text: str) -> str:
    return " ".join(text.strip().split())


def build_decisions() -> tuple[RepoBTelegramIntakeBridgeDecision, ...]:
    return (
        RepoBTelegramIntakeBridgeDecision(
            decision_id="repo_b_telegram_decision_chief_listener",
            source_module="chief_listener.py",
            source_path=_repo_b_path("chief_listener.py"),
            apparent_value="Operator authorization check, command routing entrypoint, callback handling shape, and message-to-intent normalization concepts.",
            dependencies=(
                "python-telegram-bot runtime",
                "Chief router",
                "approval bridge",
                "queue check on startup",
                "Telegram bot token environment names",
                "authorized user environment names",
            ),
            recommended_posture="REBUILD_SMALL_SUBSET_IN_REPO_A",
            wrapper_scope=(
                "fixture-only sanitized operator message envelope",
                "command hint extraction",
                "Repo A request-envelope mapping",
            ),
            rebuild_scope=(
                "small request-envelope adapter compatible with OpenClaw request processor",
                "session/chat ref mapping without Telegram runtime",
                "blocked-readback translation for unsupported live behavior",
            ),
            blocked_items=(
                "live Telegram listener startup",
                "outbound Telegram replies",
                "bot-token access",
                "queue notification on startup",
                "pending choice callback execution",
                "direct Chief/Cassandra workflow handoff",
            ),
            privacy_boundary="Use only fixture/sanitized message summaries in v0; do not expose raw Telegram update objects or private message bodies.",
            next_safe_move="Rebuild the useful intake shape in Repo A and feed it to the bounded OpenClaw request processor.",
        ),
        RepoBTelegramIntakeBridgeDecision(
            decision_id="repo_b_telegram_decision_cassandra_listener",
            source_module="cassandra_listener.py",
            source_path=_repo_b_path("cassandra_listener.py"),
            apparent_value="Assistant-intake routing shape, designated contact checks, text/voice branch separation, and conversational handoff concepts.",
            dependencies=(
                "python-telegram-bot runtime",
                "Cassandra brain",
                "voice download/transcription helpers",
                "voice-note sender",
                "Telegram bot token environment names",
            ),
            recommended_posture="REFERENCE_ONLY",
            wrapper_scope=(
                "source-level design reference only",
                "future scoped assistant-intake mapping",
            ),
            rebuild_scope=(
                "text-only request envelope adapter if Telegram becomes an approved alternate surface",
            ),
            blocked_items=(
                "live Cassandra bot startup",
                "outbound replies",
                "voice file download",
                "voice transcription",
                "voice note output",
                "direct Cassandra execution",
            ),
            privacy_boundary="Do not carry raw contact names, chat ids, or Telegram updates into normal read-models; use protected refs later.",
            next_safe_move="Keep Cassandra Telegram listener as reference-only until a governed intake adapter exists.",
        ),
        RepoBTelegramIntakeBridgeDecision(
            decision_id="repo_b_telegram_decision_chief_sender",
            source_module="chief_sender.py",
            source_path=_repo_b_path("chief_sender.py"),
            apparent_value="Simple outbound Telegram send helper, useful only as a risk marker.",
            dependencies=(
                "requests",
                "Telegram send API",
                "bot token environment names",
                "chat id environment names",
            ),
            recommended_posture="UNSAFE_DO_NOT_CONNECT",
            wrapper_scope=(),
            rebuild_scope=(),
            blocked_items=(
                "outbound Telegram message send",
                "bot-token access",
                "network call",
            ),
            privacy_boundary="Never expose token values or call outbound sender from Repo A bridge.",
            next_safe_move="Quarantine this as outbound-only behavior.",
        ),
        RepoBTelegramIntakeBridgeDecision(
            decision_id="repo_b_telegram_decision_chief_guardian_listener",
            source_module="chief_guardian_listener.py",
            source_path=_repo_b_path("chief_guardian_listener.py"),
            apparent_value="Approval-button callback parsing and typed approval fallback concepts.",
            dependencies=(
                "Guardian bot token environment names",
                "authorized user environment names",
                "Telegram callback queries",
                "approval pending state",
            ),
            recommended_posture="REFERENCE_ONLY",
            wrapper_scope=(
                "approval callback shape as future Guardian reference",
            ),
            rebuild_scope=(
                "future governed approval-intake adapter, separate from this Telegram intake bridge",
            ),
            blocked_items=(
                "live approval listener startup",
                "approval decision recording",
                "pending approval mutation",
                "outbound status messages",
            ),
            privacy_boundary="Approval codes and pending state stay out of this intake-only read-model.",
            next_safe_move="Route approval work to Guardian contracts, not to this bridge.",
        ),
        RepoBTelegramIntakeBridgeDecision(
            decision_id="repo_b_telegram_decision_chief_approval_bridge",
            source_module="chief_approval_bridge.py",
            source_path=_repo_b_path("chief_approval_bridge.py"),
            apparent_value="Follow-up response parsing and multi-choice pending-action vocabulary.",
            dependencies=(
                "pending choice JSON state",
                "Chief notify outbound sender",
                "Telegram inline keyboard payload shape",
            ),
            recommended_posture="REFERENCE_ONLY",
            wrapper_scope=(
                "follow-up intent wording reference",
            ),
            rebuild_scope=(
                "future active-thread follow-up parser that produces request envelopes only",
            ),
            blocked_items=(
                "pending choice dispatch",
                "pending JSON state mutation",
                "outbound notification",
            ),
            privacy_boundary="Follow-up fixtures may indicate intent but cannot approve, deny, or dispatch anything.",
            next_safe_move="Model follow-up messages as chat requests with active-thread context unresolved.",
        ),
        RepoBTelegramIntakeBridgeDecision(
            decision_id="repo_b_telegram_decision_chief_notify",
            source_module="chief_notify.py",
            source_path=_repo_b_path("chief_notify.py"),
            apparent_value="Background outbound notifier, useful only to identify forbidden behavior.",
            dependencies=(
                "Telegram send API",
                "bot token environment names",
                "authorized user environment names",
            ),
            recommended_posture="UNSAFE_DO_NOT_CONNECT",
            wrapper_scope=(),
            rebuild_scope=(),
            blocked_items=(
                "outbound Telegram send",
                "network call",
                "bot-token access",
            ),
            privacy_boundary="No outbound notifier is allowed in this intake-only lane.",
            next_safe_move="Keep quarantined; Mac chat response files are the approved local response path.",
        ),
    )


def build_capabilities() -> tuple[TelegramIntakeCapability, ...]:
    safe_common_inputs = (
        "fixture-safe operator message",
        "sanitized source channel label",
        "operator_ref placeholder",
    )
    return (
        TelegramIntakeCapability(
            capability_id="telegram_capability_operator_message_intake",
            source_module_ref="chief_listener.py",
            capability_type="OPERATOR_MESSAGE_INTAKE",
            description="Convert a fixture Telegram-style operator message into a sanitized intake envelope.",
            inputs_required=safe_common_inputs,
            outputs_produced=("TelegramIntakeEnvelope",),
            external_authority=False,
            credential_required=False,
            outbound_required=False,
            wrapper_allowed=True,
            next_safe_move="Map the envelope to a Repo A chat request shape.",
        ),
        TelegramIntakeCapability(
            capability_id="telegram_capability_command_normalization",
            source_module_ref="chief_router.py / chief_listener.py",
            capability_type="COMMAND_NORMALIZATION",
            description="Normalize plain operator text into a command hint without executing the command.",
            inputs_required=("fixture-safe normalized text",),
            outputs_produced=("command_hint", "workflow_ref candidate"),
            external_authority=False,
            credential_required=False,
            outbound_required=False,
            wrapper_allowed=True,
            next_safe_move="Keep the hint advisory; Repo A request processor remains the next rail.",
        ),
        TelegramIntakeCapability(
            capability_id="telegram_capability_session_mapping",
            source_module_ref="chief_listener.py / cassandra_listener.py",
            capability_type="SESSION_MAPPING",
            description="Model operator/chat/session refs without exposing Telegram chat ids or handles.",
            inputs_required=("operator_ref placeholder", "chat_ref placeholder"),
            outputs_produced=("safe chat_ref", "source_message_ref"),
            external_authority=False,
            credential_required=False,
            outbound_required=False,
            wrapper_allowed=True,
            next_safe_move="Use protected refs for real sender identity in a future approved runtime.",
        ),
        TelegramIntakeCapability(
            capability_id="telegram_capability_followup_intent_parse",
            source_module_ref="chief_approval_bridge.py",
            capability_type="FOLLOWUP_INTENT_PARSE",
            description="Identify short follow-up phrases as active-thread intent candidates without approval or action execution.",
            inputs_required=("fixture-safe follow-up phrase", "future active_thread_ref"),
            outputs_produced=("follow_up_intent_candidate",),
            external_authority=False,
            credential_required=False,
            outbound_required=False,
            wrapper_allowed=True,
            next_safe_move="Ask the request processor to resolve active thread context later.",
        ),
        TelegramIntakeCapability(
            capability_id="telegram_capability_request_envelope_creation",
            source_module_ref="repo_b_telegram_intake_bridge.py",
            capability_type="REQUEST_ENVELOPE_CREATION",
            description="Create a Mac/request-processor-compatible CHAT_REQUEST shape from a sanitized Telegram envelope.",
            inputs_required=("TelegramIntakeEnvelope",),
            outputs_produced=("TelegramToOpenClawRequestMapping",),
            external_authority=False,
            credential_required=False,
            outbound_required=False,
            wrapper_allowed=True,
            next_safe_move="Do not write live inbox requests in v0; publish deterministic read-model only.",
        ),
        TelegramIntakeCapability(
            capability_id="telegram_capability_intake_directory_write",
            source_module_ref="future Repo A adapter",
            capability_type="INTAKE_DIRECTORY_WRITE",
            description="Future bounded local write of request-envelope files into the approved OpenClaw inbox.",
            inputs_required=("validated request envelope", "idempotency key", "authority boundary false"),
            outputs_produced=("mission_control_chat_request file future",),
            external_authority=False,
            credential_required=False,
            outbound_required=False,
            wrapper_allowed=True,
            next_safe_move="Keep as modeled future behavior; this export writes only read-model artifacts.",
        ),
        TelegramIntakeCapability(
            capability_id="telegram_capability_outbound_reply_blocked",
            source_module_ref="chief_sender.py / chief_notify.py",
            capability_type="OUTBOUND_REPLY",
            description="Outbound Telegram reply/post/send is explicitly outside this intake-only bridge.",
            inputs_required=("bot credential value", "chat id", "message text"),
            outputs_produced=("Telegram message external side effect",),
            external_authority=True,
            credential_required=True,
            outbound_required=True,
            wrapper_allowed=False,
            next_safe_move="Use Mac-readable local response files instead of Telegram outbound.",
        ),
        TelegramIntakeCapability(
            capability_id="telegram_capability_pending_action_dispatch_blocked",
            source_module_ref="chief_approval_bridge.py / chief_guardian_listener.py",
            capability_type="PENDING_ACTION_DISPATCH",
            description="Pending action resolution, approval recording, and queue mutation are blocked in this bridge.",
            inputs_required=("pending action state", "operator decision text"),
            outputs_produced=("state mutation or approval decision"),
            external_authority=True,
            credential_required=False,
            outbound_required=False,
            wrapper_allowed=False,
            next_safe_move="Route future approvals to Guardian, not Telegram intake bridge.",
        ),
    )


def build_blockers() -> tuple[TelegramIntakeBlocker, ...]:
    return (
        TelegramIntakeBlocker(
            blocker_id="telegram_blocker_live_listener",
            blocker_type="LIVE_TELEGRAM_LISTENER_START_ATTEMPTED",
            condition="A wrapper attempts to instantiate a Telegram bot, call polling, or run a Repo B listener.",
            severity="critical",
            elioperator_warning="Telegram live listener startup is blocked. This lane only models fixture intake envelopes.",
            fail_closed=True,
            next_safe_move="Use a sanitized fixture or a future approved local intake adapter.",
        ),
        TelegramIntakeBlocker(
            blocker_id="telegram_blocker_outbound",
            blocker_type="TELEGRAM_OUTBOUND_ATTEMPTED",
            condition="A wrapper attempts to reply, post, edit, or send through Telegram.",
            severity="critical",
            elioperator_warning="Outbound Telegram is blocked. OpenClaw should return local Mac-readable response files instead.",
            fail_closed=True,
            next_safe_move="Publish the operator response through the OpenClaw response read-model path.",
        ),
        TelegramIntakeBlocker(
            blocker_id="telegram_blocker_bot_token",
            blocker_type="BOT_TOKEN_INCLUDED",
            condition="A request, read-model, log, fixture, or operator card includes a bot credential value.",
            severity="critical",
            elioperator_warning="Bot credentials cannot appear in chat, read-models, fixtures, logs, or operator cards.",
            fail_closed=True,
            next_safe_move="Replace any credential value with a protected secret ref in a future approved runtime.",
        ),
        TelegramIntakeBlocker(
            blocker_id="telegram_blocker_raw_private_message",
            blocker_type="RAW_PRIVATE_MESSAGE_EXPOSED",
            condition="A private raw Telegram update or message body is copied into a normal generated read-model.",
            severity="high",
            elioperator_warning="Raw private Telegram messages are blocked from normal read-models.",
            fail_closed=True,
            next_safe_move="Use a fixture-safe summary or tokenized/protected message ref.",
        ),
        TelegramIntakeBlocker(
            blocker_id="telegram_blocker_pending_dispatch",
            blocker_type="PENDING_ACTION_DISPATCH_ATTEMPTED",
            condition="A follow-up phrase attempts to approve, deny, resume, or dispatch a pending action.",
            severity="critical",
            elioperator_warning="Pending-action dispatch is blocked from Telegram intake.",
            fail_closed=True,
            next_safe_move="Convert the follow-up to a chat request and let governed Repo A rails decide the next step.",
        ),
        TelegramIntakeBlocker(
            blocker_id="telegram_blocker_queue_mutation",
            blocker_type="QUEUE_MUTATION_ATTEMPTED",
            condition="A Telegram message attempts to mutate queues or workflow state.",
            severity="critical",
            elioperator_warning="Queue mutation is blocked in the Telegram intake bridge.",
            fail_closed=True,
            next_safe_move="Produce a request envelope only; no queue writes.",
        ),
        TelegramIntakeBlocker(
            blocker_id="telegram_blocker_external_action",
            blocker_type="EXTERNAL_ACTION_ATTEMPTED",
            condition="A Telegram intake path attempts to call external systems, agents, workflows, senders, or browsers.",
            severity="critical",
            elioperator_warning="External action is blocked.",
            fail_closed=True,
            next_safe_move="Return a blocked readback with a human fix path.",
        ),
        TelegramIntakeBlocker(
            blocker_id="telegram_blocker_credential_env_mutation",
            blocker_type="CREDENTIAL_OR_ENV_MUTATION_ATTEMPTED",
            condition="A wrapper attempts to read credential values, mutate environment, or load secret files.",
            severity="critical",
            elioperator_warning="Credential and environment mutation are blocked.",
            fail_closed=True,
            next_safe_move="Use protected secret intake in a future approved runtime.",
        ),
        TelegramIntakeBlocker(
            blocker_id="telegram_blocker_unscoped_public_chat",
            blocker_type="UNSCOPED_PUBLIC_CHAT_SURFACE",
            condition="A public or unscoped Telegram chat is treated as an operator command surface.",
            severity="high",
            elioperator_warning="Unscoped public chat surfaces are blocked.",
            fail_closed=True,
            next_safe_move="Require an operator_ref, chat_ref, scope, and privacy boundary before mapping.",
        ),
        TelegramIntakeBlocker(
            blocker_id="telegram_blocker_unknown",
            blocker_type="UNKNOWN_FAIL_CLOSED",
            condition="A Telegram intake request does not match a supported fixture or safe mapping.",
            severity="high",
            elioperator_warning="Unknown Telegram intake behavior fails closed.",
            fail_closed=True,
            next_safe_move="Ask for a scoped request envelope fixture or use the Mac chat surface.",
        ),
    )


def build_envelope(fixture: str, generated_at: str = DEFAULT_GENERATED_AT) -> TelegramIntakeEnvelope:
    if fixture == "operator_message":
        message = _safe_message("Make the Capital Hilton invoice workflow happen.")
        return TelegramIntakeEnvelope(
            envelope_id="telegram_envelope_capital_hilton_make_it_happen_fixture",
            source_surface="telegram_fixture",
            source_channel="telegram_intake_fixture",
            source_message_ref="telegram_fixture_message:capital_hilton_make_it_happen",
            operator_ref="operator_ref:winship_fixture",
            chat_ref="telegram_chat_ref:operator_fixture",
            normalized_message=message,
            command_hint="workflow_make_it_happen",
            world_ref="finance",
            lane_ref="operator_chat",
            workflow_ref="capital_hilton_invoice_workflow",
            privacy_class="operator_local_private_fixture",
            authority_boundary=dict(AUTHORITY_BOUNDARY),
            next_safe_move="Map to CHAT_REQUEST for the bounded OpenClaw request processor; do not reply through Telegram.",
        )
    if fixture == "followup":
        message = _safe_message("looks right")
        return TelegramIntakeEnvelope(
            envelope_id="telegram_envelope_followup_looks_right_fixture",
            source_surface="telegram_fixture",
            source_channel="telegram_intake_fixture",
            source_message_ref="telegram_fixture_message:looks_right_followup",
            operator_ref="operator_ref:winship_fixture",
            chat_ref="telegram_chat_ref:operator_fixture",
            normalized_message=message,
            command_hint="followup_confirmation_candidate",
            world_ref="active_thread_future",
            lane_ref="operator_chat",
            workflow_ref="active_thread_context_future",
            privacy_class="operator_local_private_fixture",
            authority_boundary=dict(AUTHORITY_BOUNDARY),
            next_safe_move="Map to CHAT_REQUEST with active-thread context unresolved; do not approve or execute anything.",
        )
    raise ValueError(f"Unsupported Telegram intake fixture: {fixture}")


def build_mapping(envelope: TelegramIntakeEnvelope, generated_at: str = DEFAULT_GENERATED_AT) -> TelegramToOpenClawRequestMapping:
    request_ref = _stable_id("telegram_to_openclaw_request", envelope.envelope_id, generated_at)
    target_shape = {
        "request_id": request_ref,
        "origin_surface": "telegram_intake_bridge_fixture",
        "source_channel": "telegram",
        "source_message_ref": envelope.source_message_ref,
        "operator_ref": envelope.operator_ref,
        "chat_ref": envelope.chat_ref,
        "workflow_ref": envelope.workflow_ref,
        "world_ref": envelope.world_ref,
        "lane_ref": envelope.lane_ref,
        "operator_message_summary": envelope.normalized_message,
        "command_hint": envelope.command_hint,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "created_at": generated_at,
    }
    return TelegramToOpenClawRequestMapping(
        mapping_id=_stable_id("telegram_mapping", envelope.envelope_id, "CHAT_REQUEST"),
        intake_envelope_ref=envelope.envelope_id,
        target_request_type="CHAT_REQUEST",
        target_request_shape=target_shape,
        required_fields=(
            "request_id",
            "origin_surface",
            "source_channel",
            "workflow_ref",
            "world_ref",
            "lane_ref",
            "operator_message_summary",
            "authority_boundary",
            "created_at",
        ),
        excluded_fields=(
            "bot token value",
            "raw Telegram update object",
            "raw private message body",
            "sender handle or phone value",
            "outbound reply target",
            "approval or pending-action command",
            "queue mutation command",
        ),
        tokenization_required=True,
        output_path_policy="read-model only in v0; future approved adapter may write to approved OpenClaw inbox",
        next_safe_move="Submit this shape to the bounded OpenClaw request processor only when a safe local intake adapter is approved.",
    )


def build_readback(
    envelope: TelegramIntakeEnvelope,
    mapping: TelegramToOpenClawRequestMapping,
) -> TelegramIntakeReadback:
    if envelope.command_hint == "followup_confirmation_candidate":
        safe_summary = "Fixture follow-up was normalized as an active-thread chat request candidate."
        operator_message = (
            "I can treat this as a follow-up candidate, but this bridge will not approve, send, dispatch, "
            "or mutate anything. The next rail must resolve the active thread first."
        )
        how_to_fix = "If this should apply to a specific workflow, include the active thread or workflow ref."
    else:
        safe_summary = "Fixture Telegram operator message was mapped to a CHAT_REQUEST shape."
        operator_message = (
            "OpenClaw can turn this Telegram-style message into a local chat request envelope. "
            "Nothing was posted back to Telegram and no workflow ran."
        )
        how_to_fix = "To process it for real later, connect an approved local intake adapter to the bounded request processor."
    return TelegramIntakeReadback(
        readback_id=_stable_id("telegram_readback", envelope.envelope_id, mapping.mapping_id),
        envelope_ref=envelope.envelope_id,
        status="FIXTURE_MAPPING_READY",
        safe_summary=safe_summary,
        mapped_request_ref=str(mapping.target_request_shape["request_id"]),
        blocked_items=(
            "Telegram outbound reply",
            "live listener startup",
            "bot-token access",
            "pending action dispatch",
            "queue mutation",
            "external action",
        ),
        operator_message=operator_message,
        how_to_fix=how_to_fix,
        next_safe_move=mapping.next_safe_move,
    )


def build_blocked_readback(blocker_type: str) -> TelegramIntakeReadback:
    if blocker_type == "TELEGRAM_OUTBOUND_ATTEMPTED":
        return TelegramIntakeReadback(
            readback_id="telegram_readback_blocked_outbound_reply",
            envelope_ref="blocked:no_envelope",
            status="BLOCKED_OUTBOUND_TELEGRAM",
            safe_summary="Outbound Telegram reply/post/send was requested and blocked.",
            mapped_request_ref="none",
            blocked_items=("Telegram outbound reply", "network call", "bot-token access"),
            operator_message="I blocked the Telegram reply path. This bridge is intake-only.",
            how_to_fix="Use OpenClaw's Mac-readable response file path for operator readback.",
            next_safe_move="Do not call Repo B sender helpers from Repo A.",
        )
    if blocker_type == "LIVE_TELEGRAM_LISTENER_START_ATTEMPTED":
        return TelegramIntakeReadback(
            readback_id="telegram_readback_blocked_live_listener",
            envelope_ref="blocked:no_envelope",
            status="BLOCKED_LIVE_LISTENER",
            safe_summary="Live Telegram bot/listener startup was requested and blocked.",
            mapped_request_ref="none",
            blocked_items=("live listener startup", "bot-token access", "public chat activation"),
            operator_message="I blocked live Telegram listener startup. v0 only builds a deterministic intake model.",
            how_to_fix="Use fixture mapping now; add a future approved local intake adapter before any live listener.",
            next_safe_move="Keep Mac chat as the primary operator surface.",
        )
    if blocker_type == "BOT_TOKEN_INCLUDED":
        return TelegramIntakeReadback(
            readback_id="telegram_readback_blocked_bot_token",
            envelope_ref="blocked:no_envelope",
            status="BLOCKED_TOKEN_REQUIRED",
            safe_summary="A bot credential value was detected or requested and blocked.",
            mapped_request_ref="none",
            blocked_items=("bot credential value", "credential handling", "read-model exposure"),
            operator_message="I blocked bot credential handling. Credentials cannot enter chat, read-models, tests, or operator cards.",
            how_to_fix="Use Protected Secret Intake in a future approved runtime and expose only token refs.",
            next_safe_move="Keep this bridge credential-free.",
        )
    return TelegramIntakeReadback(
        readback_id="telegram_readback_unknown_fail_closed",
        envelope_ref="blocked:no_envelope",
        status="UNKNOWN_FAIL_CLOSED",
        safe_summary="Unknown Telegram intake behavior failed closed.",
        mapped_request_ref="none",
        blocked_items=("unknown Telegram bridge behavior",),
        operator_message="I could not safely map that Telegram behavior.",
        how_to_fix="Provide a fixture-safe operator message or use the Mac chat request path.",
        next_safe_move="Fail closed until scoped.",
    )


def build_examples(generated_at: str = DEFAULT_GENERATED_AT) -> dict[str, Any]:
    operator_envelope = build_envelope("operator_message", generated_at)
    operator_mapping = build_mapping(operator_envelope, generated_at)
    followup_envelope = build_envelope("followup", generated_at)
    followup_mapping = build_mapping(followup_envelope, generated_at)
    return {
        "operator_message": {
            "input": "Make the Capital Hilton invoice workflow happen.",
            "envelope": asdict(operator_envelope),
            "mapping": asdict(operator_mapping),
            "readback": asdict(build_readback(operator_envelope, operator_mapping)),
        },
        "followup": {
            "input": "looks right",
            "envelope": asdict(followup_envelope),
            "mapping": asdict(followup_mapping),
            "readback": asdict(build_readback(followup_envelope, followup_mapping)),
        },
        "outbound_blocker": {
            "attempt": "Reply to the operator through Telegram.",
            "readback": asdict(build_blocked_readback("TELEGRAM_OUTBOUND_ATTEMPTED")),
        },
        "listener_blocker": {
            "attempt": "Start Repo B chief_listener or cassandra_listener.",
            "readback": asdict(build_blocked_readback("LIVE_TELEGRAM_LISTENER_START_ATTEMPTED")),
        },
        "token_blocker": {
            "attempt": "Include a bot credential value in a request/read-model.",
            "readback": asdict(build_blocked_readback("BOT_TOKEN_INCLUDED")),
        },
    }


def build_payload(*, generated_at: str = DEFAULT_GENERATED_AT) -> dict[str, Any]:
    decisions = build_decisions()
    capabilities = build_capabilities()
    blockers = build_blockers()
    examples = build_examples(generated_at)
    safe_capabilities = tuple(cap.capability_id for cap in capabilities if cap.wrapper_allowed)
    blocked_capabilities = tuple(cap.capability_id for cap in capabilities if not cap.wrapper_allowed)
    return {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "contract_status": CONTRACT_STATUS,
        "generated_at": generated_at,
        "repo_b_root": str(REPO_B_ROOT),
        "postures": POSTURES,
        "capability_types": CAPABILITY_TYPES,
        "target_request_types": TARGET_REQUEST_TYPES,
        "readback_statuses": READBACK_STATUSES,
        "blocker_types": BLOCKER_TYPES,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "telegram_intake_bridge_decisions": [asdict(row) for row in decisions],
        "telegram_intake_capabilities": [asdict(row) for row in capabilities],
        "telegram_intake_blockers": [asdict(row) for row in blockers],
        "bridge_plan": {
            "posture": "INTAKE_ONLY_BRIDGE_WITH_REPO_A_REBUILT_REQUEST_ENVELOPE_ADAPTER",
            "repo_b_invocation": "none in v0",
            "fixture_mode": True,
            "safe_capabilities": safe_capabilities,
            "blocked_capabilities": blocked_capabilities,
            "mapping_target": "bounded OpenClaw request processor CHAT_REQUEST",
            "output_path": "generated read-model only in v0",
            "excluded_scope": COMMON_BLOCKED_ACTIONS,
            "next_safe_move": "Use fixture-safe Telegram envelope mapping as a future alternate intake path; Mac chat remains primary.",
        },
        "examples": examples,
        "machine_proof": {
            "all_live_authority_false": all(value is False for value in AUTHORITY_BOUNDARY.values()),
            "repo_b_code_imported": False,
            "repo_b_runtime_executed": False,
            "telegram_listener_started": False,
            "telegram_outbound_performed": False,
            "bot_token_access_performed": False,
            "pending_action_dispatch_performed": False,
            "queue_mutation_performed": False,
            "external_action_performed": False,
            "credential_handling_performed": False,
            "raw_private_message_exposure": False,
            "mac_sync_import_performed": False,
            "swift_change_performed": False,
            "git_push_performed": False,
        },
        "operator_summary": (
            "Repo B's Telegram code contains useful intake and follow-up shapes, but its actual listeners and senders "
            "are unsafe for Repo A v0 because they start live bots, depend on bot credentials, post outbound replies, "
            "and can touch pending state. This bridge keeps only fixture-safe request-envelope mapping."
        ),
        "next_safe_move": "Keep Telegram as an alternate future intake surface; route real work through Mac chat and the bounded request processor now.",
    }


def format_operator_markdown(payload: dict[str, Any]) -> str:
    operator_example = payload["examples"]["operator_message"]
    followup_example = payload["examples"]["followup"]
    lines = [
        "# Repo B Telegram Intake Bridge",
        "",
        "## Summary",
        payload["operator_summary"],
        "",
        "## Posture",
        f"- Bridge posture: {payload['bridge_plan']['posture']}",
        "- Repo B invocation: none in v0",
        "- Live Telegram: blocked",
        "- Outbound Telegram: blocked",
        "- Primary surface remains: Mac chat",
        "",
        "## Safe Intake",
        f"- Operator message fixture maps to: {operator_example['mapping']['target_request_type']}",
        f"- Follow-up fixture maps to: {followup_example['mapping']['target_request_type']}",
        "- Output is a request-envelope model, not a live inbox write.",
        "",
        "## Blocked",
    ]
    for blocker in payload["telegram_intake_blockers"]:
        lines.append(f"- {blocker['blocker_type']}: {blocker['elioperator_warning']}")
    lines += [
        "",
        "## Operator Example",
        f"- Input: {operator_example['input']}",
        f"- Readback: {operator_example['readback']['operator_message']}",
        f"- Next: {operator_example['readback']['next_safe_move']}",
        "",
        "## Boundary",
        "No live Telegram listener, no Telegram outbound, no bot token access, no pending action dispatch, no queue mutation, no external action, no credential handling, no raw private body exposure.",
    ]
    return "\n".join(lines) + "\n"


def write_exports(payload: dict[str, Any], export_root: Path = DEFAULT_EXPORT_ROOT) -> tuple[Path, Path]:
    export_root.mkdir(parents=True, exist_ok=True)
    json_path = export_root / JSON_EXPORT_NAME
    operator_path = export_root / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(format_operator_markdown(payload), encoding="utf-8")
    return json_path, operator_path


def _summary(payload: dict[str, Any], export_root: Path = DEFAULT_EXPORT_ROOT) -> dict[str, Any]:
    return {
        "read_model_id": payload["read_model_id"],
        "posture": payload["bridge_plan"]["posture"],
        "safe_capabilities": len(payload["bridge_plan"]["safe_capabilities"]),
        "blocked_capabilities": len(payload["bridge_plan"]["blocked_capabilities"]),
        "operator_message_target": payload["examples"]["operator_message"]["mapping"]["target_request_type"],
        "followup_target": payload["examples"]["followup"]["mapping"]["target_request_type"],
        "all_live_authority_false": payload["machine_proof"]["all_live_authority_false"],
        "json_export": str(export_root / JSON_EXPORT_NAME),
        "operator_export": str(export_root / OPERATOR_EXPORT_NAME),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export Repo B Telegram intake bridge read-model.")
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT))
    parser.add_argument("--generated-at", default=DEFAULT_GENERATED_AT)
    parser.add_argument("--format", choices=("json", "summary"), default="summary")
    args = parser.parse_args(argv)

    export_root = Path(args.export_root)
    payload = build_payload(generated_at=args.generated_at)
    write_exports(payload, export_root)
    if args.format == "json":
        print(stable_json(payload), end="")
    else:
        print(stable_json(_summary(payload, export_root)), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
