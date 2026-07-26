"""Shared coordinator for guarded external advisory turns and local parity."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Protocol

from codex_app_server_client import (
    CodexAppServerClient,
    CodexAppServerRefusal,
    SubscriptionAdmission,
    build_safe_subscription_receipt,
)
from external_brain_router import (
    LOCAL_SAFE_LANE,
    build_safe_route_receipt,
    load_model_lane_bindings,
    route_external_brain_request,
)
from packet_quality_telemetry import (
    DEFAULT_LEDGER_PATH,
    build_packet_provenance,
    record_packet_quality_report,
)


class GuardianBridge(Protocol):
    def queue_approval_request(
        self,
        scope: Mapping[str, Any],
        *,
        notify_operator: bool = False,
    ) -> Mapping[str, Any]: ...


@dataclass(frozen=True)
class ExternalBrainRuntimeResult:
    text: str
    source: str
    receipt: dict[str, Any]


def _hash_identifier(value: object) -> str:
    digest = hashlib.sha256(str(value or "").encode("utf-8")).hexdigest()
    return f"sha256:{digest[:16]}"


def _stable_agent_cache_prefix(role: str) -> str:
    """Return the immutable persona/doctrine prefix shared by an agent's turns."""

    from agent_voice_profiles import immutable_persona_core_for_speaker

    core = immutable_persona_core_for_speaker(role)
    return "OPENCLAW IMMUTABLE AGENT PREFIX:\n" + json.dumps(
        core,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )


def _local_result(
    local_fallback: Callable[[], str],
    receipt: dict[str, Any],
    *,
    reason: str,
) -> ExternalBrainRuntimeResult:
    receipt.update(
        {
            "effective_lane_id": LOCAL_SAFE_LANE,
            "fallback_reason": reason,
            "response_source": "local_fallback",
            "external_turn_performed": False,
        }
    )
    return ExternalBrainRuntimeResult(
        text=str(local_fallback() or ""),
        source="local_fallback",
        receipt=receipt,
    )


def run_external_brain_request(
    *,
    raw_operator_prompt: str,
    original_operator_message: str | None = None,
    context_aid: Mapping[str, Any],
    privacy_metadata: Mapping[str, Any],
    task_type: str,
    client: CodexAppServerClient,
    local_fallback: Callable[[], str],
    cwd: str,
    chain_lane: str = "LM2_ROLE_RESPONSE",
    role: str = "advisory_response",
    risk_tier: str = "low",
    context_size: str = "small",
    effort_override: str | None = None,
    activation_enabled: bool = False,
    reserve_threshold_percent: int = 80,
    guardian_approval_id: str = "",
    guardian_bridge: GuardianBridge | None = None,
    guardian_notify_operator: bool = False,
    comparison_lane_id: str | None = None,
    packet_quality_db_path: str | Path | None = DEFAULT_LEDGER_PATH,
    usage_recorder: Callable[..., Mapping[str, Any]] | None = None,
) -> ExternalBrainRuntimeResult:
    """Run one external advisory turn or reuse the caller's local path immediately.

    No alternative external model is attempted after any refusal or failure.
    """

    decision = route_external_brain_request(
        raw_operator_prompt=raw_operator_prompt,
        task_type=task_type,
        privacy_metadata=privacy_metadata,
        chain_lane=chain_lane,
        role=role,
        risk_tier=risk_tier,
        context_size=context_size,
        effort_override=effort_override,
        activation_enabled=activation_enabled,
        comparison_lane_id=comparison_lane_id,
    )
    receipt = build_safe_route_receipt(decision)
    receipt["response_source"] = "pending"
    receipt["external_turn_performed"] = False
    if decision.effective_lane_id == LOCAL_SAFE_LANE:
        return _local_result(
            local_fallback,
            receipt,
            reason=decision.fallback_reason or "model_policy_selected_local",
        )

    try:
        bindings = load_model_lane_bindings()["lanes"]
        binding = bindings[decision.candidate_lane_id]
        if binding.get("transport") != "codex_app_server":
            return _local_result(local_fallback, receipt, reason="external_binding_transport_invalid")
        bound_model = str(binding.get("model") or "")
        admission = client.preflight(
            model=bound_model,
            effort_level=decision.effort_level,
            request_hash=decision.request_hash,
            lane_id=decision.candidate_lane_id,
            reserve_threshold_percent=reserve_threshold_percent,
            guardian_approval_id=guardian_approval_id,
        )
    except Exception as exc:
        return _local_result(
            local_fallback,
            receipt,
            reason=f"external_preflight_error:{type(exc).__name__}",
        )

    subscription_receipt = build_safe_subscription_receipt(
        admission,
        request_hash=decision.request_hash,
        lane_id=decision.candidate_lane_id,
        fallback_reason="" if admission.allowed else admission.reason,
    )
    receipt["subscription"] = subscription_receipt
    receipt["configured_binding_model_id"] = bound_model
    receipt["binding_model_id"] = admission.model
    if admission.allowed and str(admission.model or "") != bound_model:
        return _local_result(
            local_fallback,
            receipt,
            reason="external_preflight_model_mismatch",
        )
    if not admission.allowed:
        if (
            admission.reason == "guardian_approval_required"
            and isinstance(admission.guardian_approval_request, Mapping)
            and guardian_bridge is not None
        ):
            try:
                queued = guardian_bridge.queue_approval_request(
                    admission.guardian_approval_request,
                    notify_operator=bool(guardian_notify_operator),
                )
                action_id = str(queued.get("action_id") or "")
                receipt["guardian_action_id_hash"] = _hash_identifier(action_id) if action_id else ""
                receipt["guardian_notification_sent"] = bool(queued.get("notification_sent"))
            except Exception as exc:
                receipt["guardian_queue_error"] = type(exc).__name__
        return _local_result(local_fallback, receipt, reason=admission.reason)

    provenance = build_packet_provenance(context_aid)
    context_with_provenance = dict(context_aid)
    context_with_provenance["packet_build_provenance"] = provenance
    from agent_introspection import normalize_turn_self_facts

    turn_self_facts = normalize_turn_self_facts(
        agent=str(role or "advisory_response"),
        source_request_id=decision.request_hash,
        route_receipt={
            **receipt,
            "turn_id_hash": decision.request_hash,
            "binding_model_id": admission.model,
            "effective_lane_id": decision.candidate_lane_id,
            "response_source": "external_brain",
            "external_turn_performed": True,
        },
    )
    context_with_provenance["turn_self_facts"] = turn_self_facts
    receipt["turn_self_facts"] = turn_self_facts
    receipt["turn_self_facts_in_prompt"] = True
    receipt["packet_build_provenance"] = {
        key: provenance[key]
        for key in (
            "schema_version",
            "packet_id",
            "packet_hash",
            "built_at",
            "builder_name",
            "builder_version",
            "builder_config_hash",
        )
    }

    try:
        cache_prefix = _stable_agent_cache_prefix(role)
        turn = client.run_read_only_turn(
            admission=admission,
            raw_operator_prompt=raw_operator_prompt,
            original_operator_message=original_operator_message,
            context_aid=context_with_provenance,
            cwd=cwd,
            cache_prefix=cache_prefix,
        )
    except Exception as exc:
        if isinstance(exc, CodexAppServerRefusal):
            turn_error = f"external_turn_error:CodexAppServerRefusal:{str(exc)[:120]}"
        else:
            turn_error = f"external_turn_error:{type(exc).__name__}"
        return _local_result(
            local_fallback,
            receipt,
            reason=turn_error,
        )
    if packet_quality_db_path is not None:
        try:
            packet_quality_receipt = record_packet_quality_report(
                db_path=packet_quality_db_path,
                turn_ref_hash=turn.turn_id_hash,
                task_class="_".join(str(task_type or "advisory_response").lower().split()),
                task_difficulty=decision.nominal_lane_id.removesuffix("_lane"),
                nominal_lane_id=decision.nominal_lane_id,
                work_lane_id=decision.candidate_lane_id,
                model_id=admission.model,
                provenance=provenance,
                critique=turn.packet_critique,
            )
        except Exception as exc:
            packet_quality_receipt = {
                "schema_version": "packet_quality_report_receipt_v1",
                "status": "write_failed",
                "error_type": type(exc).__name__,
            }
    else:
        packet_quality_receipt = {
            "schema_version": "packet_quality_report_receipt_v1",
            "status": "disabled_for_test",
        }
    receipt.update(
        {
            "response_source": "external_brain",
            "external_turn_performed": True,
            "fallback_reason": "",
            "thread_id_hash": turn.thread_id_hash,
            "turn_id_hash": turn.turn_id_hash,
            "packet_quality": packet_quality_receipt,
            "original_message_sha256": turn.original_message_sha256,
            "original_message_present_in_prompt": turn.original_message_present_in_prompt,
            "prompt_sha256": turn.prompt_sha256,
            "prompt_composition_sha256": turn.prompt_composition_sha256,
            "model_call_id_hash": turn.turn_id_hash,
            "cache_prefix_sha256": turn.cache_prefix_sha256,
            "cache_prefix_chars": turn.cache_prefix_chars,
            "input_tokens": turn.input_tokens,
            "cached_input_tokens": turn.cached_input_tokens,
            "cache_read_hit": turn.cache_read_hit,
            "cache_read_ratio": turn.cache_read_ratio,
        }
    )
    if usage_recorder is not None:
        try:
            receipt["router_usage"] = dict(
                usage_recorder(
                    agent_id=str(role or "").strip().lower(),
                    route_receipt=receipt,
                    answer_text=turn.text,
                )
            )
        except Exception as exc:
            receipt["router_usage"] = {
                "schema_version": "lm1_router_usage_receipt_v1",
                "status": "write_failed",
                "error_type": type(exc).__name__,
            }
    return ExternalBrainRuntimeResult(text=turn.text, source="external_brain", receipt=receipt)
