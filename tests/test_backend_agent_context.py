from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend_knowledge_packet import (
    AgentContextRequest,
    AgentContextExportDecision,
    AgentContextExportPacket,
    assemble_agent_context_export,
    evaluate_agent_context_access,
)
from backend_sqlite_repository import (
    AgentContextProfile,
    ContextExportReceipt,
    SemanticRecord,
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
        sensitivity_ceiling="internal",
        model_policy_ref="default-model-policy",
        provider_policy_ref="default-provider-policy",
        status="active",
        approval_receipt_ref="receipt-1",
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
