from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend_knowledge_packet import (
    AgentContextRequest,
    ActorProfileSnapshot,
    ActorContextTrustDecision,
    AgentContextExportDecision,
    AgentContextExportPacket,
    assemble_agent_context_export,
    agent_context_export_as_dict,
    evaluate_actor_agent_context_access,
    evaluate_actor_context_trust,
    evaluate_agent_context_access,
)
import backend_knowledge_packet as knowledge_packet
from backend_sqlite_repository import (
    AgentContextProfile,
    ActorProfile,
    ContextExportReceipt,
    SemanticRecord,
    write_actor_profile,
    read_agent_context_profile,
    read_context_export_receipt,
    write_agent_context_profile,
    write_semantic_record,
)
from backend_sqlite_runtime import create_in_memory_connection


def sample_agent_context_profile(
    profile_id: str = "profile-1",
    tenant_id: str = "tenant-1",
    agent_role: str = "cassandra",
    task_class: str = "user_reply",
    sensitivity_ceiling: str = "internal",
) -> AgentContextProfile:
    return AgentContextProfile(
        context_profile_id=profile_id,
        tenant_id=tenant_id,
        agent_role=agent_role,
        task_class=task_class,
        capability_scope="personal",
        allowed_entity_family="person",
        allowed_source_mode="metadata_safe",
        max_records=100,
        max_depth=3,
        sensitivity_ceiling=sensitivity_ceiling,
        model_policy_ref="default-model-policy",
        provider_policy_ref="default-provider-policy",
        status="active",
        approval_receipt_ref="receipt-1",
        created_at="2026-05-07T12:00:00Z",
    )


def sample_actor_profile(
    actor_profile_id: str = "actor-1",
    tenant_id: str = "tenant-1",
    actor_role: str = "generic_sidecar",
    actor_class: str = "local_sidecar",
    sensitivity_ceiling: str = "sensitive_local",
    status: str = "active",
    model_policy_ref: str = "model-policy-a",
    provider_policy_ref: str = "provider-policy-a",
) -> ActorProfile:
    return ActorProfile(
        actor_profile_id=actor_profile_id,
        tenant_id=tenant_id,
        actor_role=actor_role,
        actor_class=actor_class,
        trust_tier=2,
        sensitivity_ceiling=sensitivity_ceiling,
        capability_scope="proposal_only",
        runtime_component_id="runtime-component-optional",
        model_policy_ref=model_policy_ref,
        provider_policy_ref=provider_policy_ref,
        write_canonical_memory=0,
        runtime_execution_authority=0,
        requires_receipt=1,
        allowed_export_formats="json",
        status=status,
        approval_receipt_ref="actor-approval-1",
        created_at="2026-05-07T12:00:00Z",
    )


def sample_semantic_record(record_id: str = "record-1") -> SemanticRecord:
    return SemanticRecord(
        record_id=record_id,
        entity_family="person",
        knowledge_layer="raw layer",
        contract_state="confirmed",
        validator_decision="allowed",
        synthesis_not_truth=0,
        accepted_knowledge_derived=0,
        provenance_refs="test",
        freshness_refs="test",
        confidence_label="high",
        sensitivity_label="internal",
        authority_label="test",
        review_status_label="confirmed",
    )


def test_agent_context_profile_repository():
    connection = create_in_memory_connection()
    profile = sample_agent_context_profile()

    write_agent_context_profile(connection, profile)

    read_back = read_agent_context_profile(connection, "profile-1")
    assert read_back is not None
    assert read_back["agent_role"] == "cassandra"
    assert read_back["task_class"] == "user_reply"
    assert read_back["max_records"] == 100


def test_evaluate_agent_context_access_allowed():
    connection = create_in_memory_connection()
    write_agent_context_profile(connection, sample_agent_context_profile())

    request = AgentContextRequest(
        tenant_id="tenant-1",
        requesting_actor="operator-1",
        agent_role="cassandra",
        task_class="user_reply",
        seed_strategy="direct_record_id",
        seed_params={"record_id": "record-1"},
    )

    decision = evaluate_agent_context_access(connection, request)
    assert decision.allowed is True
    assert decision.reason == "active_profile_match"
    assert decision.profile_id == "profile-1"


def test_evaluate_agent_context_access_denied_no_profile():
    connection = create_in_memory_connection()

    request = AgentContextRequest(
        tenant_id="tenant-1",
        requesting_actor="operator-1",
        agent_role="cassandra",
        task_class="user_reply",
        seed_strategy="direct_record_id",
        seed_params={"record_id": "record-1"},
    )

    decision = evaluate_agent_context_access(connection, request)
    assert decision.allowed is False
    assert decision.reason == "no_active_profile_found"


def test_evaluate_agent_context_access_denied_wrong_tenant():
    connection = create_in_memory_connection()
    write_agent_context_profile(connection, sample_agent_context_profile(tenant_id="tenant-A"))

    request = AgentContextRequest(
        tenant_id="tenant-B",
        requesting_actor="operator-1",
        agent_role="cassandra",
        task_class="user_reply",
        seed_strategy="direct_record_id",
        seed_params={"record_id": "record-1"},
    )

    decision = evaluate_agent_context_access(connection, request)
    assert decision.allowed is False
    assert decision.reason == "no_active_profile_found"


def test_assemble_agent_context_export_success():
    connection = create_in_memory_connection()
    write_agent_context_profile(connection, sample_agent_context_profile())
    write_semantic_record(connection, sample_semantic_record("record-1"))

    request = AgentContextRequest(
        tenant_id="tenant-1",
        requesting_actor="operator-1",
        agent_role="cassandra",
        task_class="user_reply",
        seed_strategy="direct_record_id",
        seed_params={"record_id": "record-1"},
    )

    packet = assemble_agent_context_export(
        connection,
        request,
        export_receipt_id="export-1",
        created_at="2026-05-07T12:01:00Z"
    )

    assert packet.export_receipt_id == "export-1"
    assert packet.context_profile_id == "profile-1"
    assert len(packet.selections) == 1
    assert packet.selections[0].record_id == "record-1"

    # Verify receipt was written
    receipt = read_context_export_receipt(connection, "export-1")
    assert receipt is not None
    assert receipt["export_status"] == "allowed"
    assert receipt["records_returned"] == 1


def test_assemble_agent_context_export_denied():
    connection = create_in_memory_connection()

    request = AgentContextRequest(
        tenant_id="tenant-1",
        requesting_actor="operator-1",
        agent_role="cassandra",
        task_class="user_reply",
        seed_strategy="direct_record_id",
        seed_params={"record_id": "record-1"},
    )

    packet = assemble_agent_context_export(
        connection,
        request,
        export_receipt_id="export-fail-1",
        created_at="2026-05-07T12:02:00Z"
    )

    assert packet.context_profile_id == "none"
    assert len(packet.selections) == 0

    # Verify receipt was written
    receipt = read_context_export_receipt(connection, "export-fail-1")
    assert receipt is not None
    assert receipt["export_status"] == "denied"
    assert receipt["denied_reason"] == "no_active_profile_found"


def test_future_agent_compatibility():
    connection = create_in_memory_connection()
    # Register a "future_agent" role without schema changes
    write_agent_context_profile(connection, sample_agent_context_profile(
        profile_id="future-profile",
        agent_role="future_agent",
        task_class="future_task"
    ))

    request = AgentContextRequest(
        tenant_id="tenant-1",
        requesting_actor="future-actor",
        agent_role="future_agent",
        task_class="future_task",
        seed_strategy="direct_record_id",
        seed_params={"record_id": "record-future"},
    )

    decision = evaluate_agent_context_access(connection, request)
    assert decision.allowed is True
    assert decision.profile_id == "future-profile"


def actor_request(
    actor_profile_id: str = "actor-1",
    agent_role: str = "future_agent",
    task_class: str = "future_task",
    receipt_ref: str = "",
) -> AgentContextRequest:
    return AgentContextRequest(
        tenant_id="tenant-1",
        requesting_actor="example-requester",
        agent_role=agent_role,
        task_class=task_class,
        seed_strategy="direct_record_id",
        seed_params={"record_id": "record-1"},
        actor_profile_id=actor_profile_id,
        context_access_receipt_ref=receipt_ref,
    )


def test_actor_context_trust_denies_missing_actor_profile():
    connection = create_in_memory_connection()
    write_agent_context_profile(
        connection,
        sample_agent_context_profile(
            profile_id="future-profile",
            agent_role="future_agent",
            task_class="future_task",
        ),
    )

    missing_id_decision = evaluate_actor_agent_context_access(
        connection,
        actor_request(actor_profile_id=""),
    )
    missing_profile_decision = evaluate_actor_agent_context_access(
        connection,
        actor_request(actor_profile_id="missing-actor"),
    )

    assert missing_id_decision.allowed is False
    assert missing_id_decision.reason == "missing_actor_profile_id"
    assert missing_profile_decision.allowed is False
    assert missing_profile_decision.reason == "missing_actor_profile"


def test_actor_context_trust_denies_tenant_mismatch_and_inactive_or_revoked():
    connection = create_in_memory_connection()
    write_agent_context_profile(
        connection,
        sample_agent_context_profile(
            profile_id="future-profile",
            agent_role="future_agent",
            task_class="future_task",
        ),
    )
    write_actor_profile(connection, sample_actor_profile(tenant_id="tenant-other"))
    write_actor_profile(
        connection,
        sample_actor_profile("inactive-actor", status="inactive"),
    )
    write_actor_profile(
        connection,
        sample_actor_profile("revoked-actor", status="revoked"),
    )

    tenant_decision = evaluate_actor_agent_context_access(connection, actor_request())
    inactive_decision = evaluate_actor_agent_context_access(
        connection,
        actor_request(actor_profile_id="inactive-actor"),
    )
    revoked_decision = evaluate_actor_agent_context_access(
        connection,
        actor_request(actor_profile_id="revoked-actor"),
    )

    assert tenant_decision.allowed is False
    assert tenant_decision.reason == "tenant_mismatch"
    assert inactive_decision.allowed is False
    assert inactive_decision.reason == "actor_not_active"
    assert revoked_decision.allowed is False
    assert revoked_decision.reason == "actor_not_active"


def test_cloud_sidecar_denies_private_context_by_default_without_leaking_content():
    connection = create_in_memory_connection()
    write_agent_context_profile(
        connection,
        sample_agent_context_profile(
            profile_id="cloud-private-profile",
            agent_role="future_agent",
            task_class="future_task",
            sensitivity_ceiling="private_strict",
        ),
    )
    write_actor_profile(
        connection,
        sample_actor_profile(
            actor_role="cloud_worker",
            actor_class="cloud_sidecar",
            sensitivity_ceiling="sanitized",
        ),
    )

    decision = evaluate_actor_agent_context_access(connection, actor_request())

    assert decision.allowed is False
    assert decision.reason == "cloud_sidecar_context_not_public_or_sanitized"
    assert "record-1" not in decision.reason


def test_cloud_sidecar_allows_public_context_when_policy_permits():
    connection = create_in_memory_connection()
    write_agent_context_profile(
        connection,
        sample_agent_context_profile(
            profile_id="public-profile",
            agent_role="future_agent",
            task_class="future_task",
            sensitivity_ceiling="public",
        ),
    )
    write_actor_profile(
        connection,
        sample_actor_profile(
            actor_role="cloud_worker",
            actor_class="cloud_sidecar",
            sensitivity_ceiling="public",
        ),
    )

    decision = evaluate_actor_agent_context_access(connection, actor_request())

    assert decision.allowed is True
    assert decision.reason == "active_profile_and_actor_trust_match"
    assert decision.profile_id == "public-profile"


def test_cloud_sidecar_allows_sanitized_context_only_with_explicit_receipt():
    connection = create_in_memory_connection()
    write_agent_context_profile(
        connection,
        sample_agent_context_profile(
            profile_id="sanitized-profile",
            agent_role="future_agent",
            task_class="future_task",
            sensitivity_ceiling="sanitized",
        ),
    )
    write_actor_profile(
        connection,
        sample_actor_profile(
            actor_role="cloud_worker",
            actor_class="cloud_sidecar",
            sensitivity_ceiling="sanitized",
        ),
    )

    denied = evaluate_actor_agent_context_access(connection, actor_request())
    allowed = evaluate_actor_agent_context_access(
        connection,
        actor_request(receipt_ref="sanitization-receipt-1"),
    )

    assert denied.allowed is False
    assert denied.reason == "cloud_sidecar_requires_sanitization_or_approval_receipt"
    assert allowed.allowed is True


def test_actor_sidecar_and_worker_profiles_do_not_grant_action_authority():
    advisory = sample_actor_profile(
        actor_profile_id="advisory-1",
        actor_role="Hermes",
        actor_class="advisory_sidecar",
    )
    build_worker = sample_actor_profile(
        actor_profile_id="build-1",
        actor_role="Codex",
        actor_class="build_worker",
    )

    for profile in (advisory, build_worker):
        snapshot = ActorProfileSnapshot(**profile.__dict__)
        decision = evaluate_actor_context_trust(
            actor_request(actor_profile_id=profile.actor_profile_id),
            sample_agent_context_profile(sensitivity_ceiling="sensitive_local"),
            snapshot,
        )

        assert isinstance(decision, ActorContextTrustDecision)
        assert decision.allowed is True
        assert decision.write_canonical_memory == 0
        assert decision.runtime_execution_authority == 0


def test_future_actor_and_model_provider_names_are_data_not_branches():
    connection = create_in_memory_connection()
    write_agent_context_profile(
        connection,
        sample_agent_context_profile(
            profile_id="future-profile",
            agent_role="renamed_agent",
            task_class="new_task_class",
            sensitivity_ceiling="public",
        ),
    )
    write_actor_profile(
        connection,
        sample_actor_profile(
            actor_role="Jules",
            actor_class="future_actor",
            model_policy_ref="Gemini",
            provider_policy_ref="OpenRouter",
        ),
    )

    decision = evaluate_actor_agent_context_access(
        connection,
        actor_request(agent_role="renamed_agent", task_class="new_task_class"),
    )

    assert decision.allowed is True
    source = Path(knowledge_packet.__file__).read_text(encoding="utf-8")
    assert 'actor_role == "Jules"' not in source
    assert "sanitize_packet" not in source


def test_actor_aware_assemble_denies_without_source_content_or_fake_sanitization():
    connection = create_in_memory_connection()
    write_agent_context_profile(
        connection,
        sample_agent_context_profile(
            profile_id="cloud-private-profile",
            agent_role="future_agent",
            task_class="future_task",
            sensitivity_ceiling="tenant_strict",
        ),
    )
    write_actor_profile(
        connection,
        sample_actor_profile(
            actor_role="cloud_worker",
            actor_class="cloud_sidecar",
            sensitivity_ceiling="sanitized",
        ),
    )
    write_semantic_record(connection, sample_semantic_record("record-1"))

    packet = assemble_agent_context_export(
        connection,
        actor_request(),
        export_receipt_id="cloud-denied-export",
        created_at="2026-05-07T12:03:00Z",
    )
    receipt = read_context_export_receipt(connection, "cloud-denied-export")

    assert packet.truth_status == "not_accepted_truth"
    assert packet.synthesized is False
    assert packet.selections == ()
    assert receipt is not None
    assert receipt["export_status"] == "denied"
    assert receipt["denied_reason"] == "cloud_sidecar_context_not_public_or_sanitized"


def test_denied_actor_export_does_not_echo_seed_record_ids_into_packet_or_receipt():
    connection = create_in_memory_connection()
    write_agent_context_profile(
        connection,
        sample_agent_context_profile(
            profile_id="cloud-private-profile",
            agent_role="future_agent",
            task_class="future_task",
            sensitivity_ceiling="tenant_strict",
        ),
    )
    write_actor_profile(
        connection,
        sample_actor_profile(
            actor_role="cloud_worker",
            actor_class="cloud_sidecar",
            sensitivity_ceiling="sanitized",
        ),
    )
    write_semantic_record(connection, sample_semantic_record("record-1"))

    packet = assemble_agent_context_export(
        connection,
        actor_request(),
        export_receipt_id="cloud-denied-export-no-echo",
        created_at="2026-05-07T12:04:00Z",
    )
    receipt = read_context_export_receipt(connection, "cloud-denied-export-no-echo")

    assert receipt is not None
    rendered_packet = str(agent_context_export_as_dict(packet))
    rendered_receipt = str(dict(receipt))
    assert "record-1" not in rendered_packet
    assert "record-1" not in rendered_receipt
    assert packet.selections == ()
    assert packet.omissions == ()
    assert receipt["records_returned"] == 0
    assert receipt["records_omitted"] == 0
