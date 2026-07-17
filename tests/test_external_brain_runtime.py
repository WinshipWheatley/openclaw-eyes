from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import external_brain_runtime as runtime
from codex_app_server_client import CodexTurnResult, SubscriptionAdmission


def _public_metadata() -> dict[str, Any]:
    return {
        "classification": "public",
        "original_pii_tier": "PUBLIC",
        "cloud_allowed": True,
        "local_required": False,
        "tokenization_applied": False,
        "package_minimized": True,
        "raw_values_included": False,
        "secrets_present": False,
    }


@dataclass
class FakeClient:
    admission: SubscriptionAdmission
    answer: str = "External answer."
    preflights: list[dict[str, Any]] = field(default_factory=list)
    turns: list[dict[str, Any]] = field(default_factory=list)
    raise_on_turn: bool = False

    def preflight(self, **kwargs):
        self.preflights.append(kwargs)
        return self.admission

    def run_read_only_turn(self, **kwargs):
        self.turns.append(kwargs)
        if self.raise_on_turn:
            raise TimeoutError("synthetic timeout")
        return CodexTurnResult(
            text=self.answer,
            thread_id_hash="sha256:thread",
            turn_id_hash="sha256:turn",
            packet_critique={
                "summary": "The packet supported this synthetic test turn.",
                "quality_score": 90,
                "missing": [],
                "noise": [],
                "mis_scoped": [],
                "improvement_items": [],
                "grounded_in_turn": ["bounded test fact was sufficient"],
            },
        )


@dataclass
class FakeGuardianBridge:
    queued: list[tuple[dict[str, Any], bool]] = field(default_factory=list)

    def queue_approval_request(self, scope, *, notify_operator=False):
        self.queued.append((dict(scope), notify_operator))
        return {"action_id": "guardian-action", "notification_sent": notify_operator}


def test_default_off_uses_local_callback_without_preflight() -> None:
    client = FakeClient(SubscriptionAdmission(True, "ok", "unused"))
    local_calls: list[str] = []

    result = runtime.run_external_brain_request(
        raw_operator_prompt="Public quick task",
        context_aid={"facts": ["bounded"]},
        privacy_metadata=_public_metadata(),
        task_type="quick summary",
        client=client,
        local_fallback=lambda: local_calls.append("local") or "Local answer.",
        cwd="/home/openclaw",
        activation_enabled=False,
        packet_quality_db_path=None,
    )

    assert result.text == "Local answer."
    assert result.source == "local_fallback"
    assert client.preflights == []
    assert local_calls == ["local"]
    assert result.receipt["fallback_reason"] == "external_router_default_off"


def test_activated_safe_request_passes_raw_prompt_and_effort_to_client() -> None:
    admission = SubscriptionAdmission(
        True,
        "subscription_headroom_ok",
        "gpt-5.6-luna",
        effort_level="low",
        account_type="chatgpt",
        used_percent=25,
        window_duration_mins=10080,
    )
    client = FakeClient(admission)
    raw_prompt = "My exact punctuation stays: yes?!"

    result = runtime.run_external_brain_request(
        raw_operator_prompt=raw_prompt,
        context_aid={"facts": ["bounded"]},
        privacy_metadata=_public_metadata(),
        task_type="quick summary",
        chain_lane="LM1_INTENT_PROPOSAL",
        client=client,
        local_fallback=lambda: "Local answer.",
        cwd="/home/openclaw",
        activation_enabled=True,
        packet_quality_db_path=None,
    )

    assert result.text == "External answer."
    assert result.source == "external_brain"
    assert client.preflights[0]["model"] == "gpt-5.6-terra"
    assert client.preflights[0]["effort_level"] == "medium"
    assert client.turns[0]["raw_operator_prompt"] == raw_prompt
    assert client.turns[0]["context_aid"]["facts"] == ["bounded"]
    assert client.turns[0]["context_aid"]["packet_build_provenance"]["builder_version"] == (
        "external_brain_packet_aid_v2"
    )
    assert result.receipt["thread_id_hash"] == "sha256:thread"
    assert "My exact punctuation" not in str(result.receipt)


def test_guardian_boundary_queues_scope_and_falls_local_without_turn() -> None:
    scope = {
        "schema_version": "external_subscription_guardian_request_v1",
        "action_type": "external_subscription_over_reserve",
        "request_hash": "sha256:request",
        "lane_id": "easy_lane",
        "effort_level": "low",
        "used_percent": 80,
        "reserve_threshold_percent": 80,
        "window_duration_mins": 10080,
        "binding_model_id": "gpt-5.6-luna",
    }
    admission = SubscriptionAdmission(
        False,
        "guardian_approval_required",
        "gpt-5.6-luna",
        effort_level="low",
        account_type="chatgpt",
        used_percent=80,
        window_duration_mins=10080,
        guardian_approval_required=True,
        guardian_approval_request=scope,
    )
    client = FakeClient(admission)
    guardian = FakeGuardianBridge()

    result = runtime.run_external_brain_request(
        raw_operator_prompt="Public quick task",
        context_aid={},
        privacy_metadata=_public_metadata(),
        task_type="quick summary",
        chain_lane="LM1_INTENT_PROPOSAL",
        client=client,
        local_fallback=lambda: "Local answer.",
        guardian_bridge=guardian,
        guardian_notify_operator=True,
        cwd="/home/openclaw",
        activation_enabled=True,
        packet_quality_db_path=None,
    )

    assert result.text == "Local answer."
    assert client.turns == []
    assert guardian.queued == [(scope, True)]
    assert result.receipt["guardian_action_id_hash"].startswith("sha256:")


def test_timeout_or_protocol_failure_falls_local_without_variant_swap() -> None:
    admission = SubscriptionAdmission(
        True,
        "subscription_headroom_ok",
        "gpt-5.6-luna",
        effort_level="low",
        account_type="chatgpt",
        used_percent=25,
    )
    client = FakeClient(admission, raise_on_turn=True)

    result = runtime.run_external_brain_request(
        raw_operator_prompt="Public quick task",
        context_aid={},
        privacy_metadata=_public_metadata(),
        task_type="quick summary",
        chain_lane="LM1_INTENT_PROPOSAL",
        client=client,
        local_fallback=lambda: "Local after timeout.",
        cwd="/home/openclaw",
        activation_enabled=True,
        packet_quality_db_path=None,
    )

    assert result.text == "Local after timeout."
    assert result.source == "local_fallback"
    assert len(client.preflights) == 1
    assert len(client.turns) == 1
    assert result.receipt["fallback_reason"] == "external_turn_error:TimeoutError"
