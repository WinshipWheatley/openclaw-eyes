"""Shared coordinator for guarded external advisory turns and local parity."""

from __future__ import annotations

import hashlib
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
    packet_quality_db_path: str | Path | None = DEFAULT_LEDGER_PATH,
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
    receipt["binding_model_id"] = admission.model
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
        turn = client.run_read_only_turn(
            admission=admission,
            raw_operator_prompt=raw_operator_prompt,
            context_aid=context_with_provenance,
            cwd=cwd,
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
        }
    )
    return ExternalBrainRuntimeResult(text=turn.text, source="external_brain", receipt=receipt)
