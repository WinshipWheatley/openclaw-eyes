from expert_escalation_job_manifest import build_expert_job_manifest, hash_expert_job_manifest
from expert_escalation_lane_policy import select_expert_lane
from expert_escalation_packet import REQUIRED_SENSITIVITY_ATTESTATIONS, build_expert_escalation_packet
from expert_provider_policy import hash_expert_provider_plan, select_expert_provider


def _attestation() -> dict[str, bool]:
    return {key: True for key in REQUIRED_SENSITIVITY_ATTESTATIONS}


def _valid_packet(**overrides):
    packet = build_expert_escalation_packet(
        packet_id="expert-20260501-static-chain",
        created_at="2026-05-01T09:00:00Z",
        operator_request_summary="Review a synthetic public parser helper.",
        task_type="code_review",
        data_classification="synthetic_public",
        cloud_allowed=True,
        sensitivity_attestation=_attestation(),
        allowed_paths=(
            "expert_escalation_job_manifest.py",
            "expert_provider_policy.py",
            "tests/test_expert_evidence_chain_static_contract.py",
        ),
        forbidden_paths=("private-vaults", "secret-env-files", "sensitive-source-data"),
        prompt="Review this synthetic public parser helper and return risks plus focused test ideas.",
        expected_outputs=("risk_summary", "test_suggestions"),
    )
    packet["execution_policy"]["candidate_provider"] = "openrouter"
    for key, value in overrides.items():
        if key == "execution_policy":
            merged = dict(packet["execution_policy"])
            merged.update(value)
            packet[key] = merged
        elif key == "sensitivity_attestation":
            merged = dict(packet["sensitivity_attestation"])
            merged.update(value)
            packet[key] = merged
        else:
            packet[key] = value
    return packet


def test_static_expert_evidence_chain_preserves_builder_owned_hashes():
    packet = _valid_packet()
    lane_plan = select_expert_lane(packet)

    manifest = build_expert_job_manifest(packet, created_at="2026-05-01T09:05:00Z")
    provider_plan = select_expert_provider(packet, lane_plan)
    downstream_record = {
        "packet_id": packet["packet_id"],
        "manifest_hash": manifest["manifest_hash"],
        "provider_plan_hash": provider_plan["provider_plan_hash"],
        "execution_allowed": False,
    }

    assert manifest["manifest_hash"].startswith("sha256:")
    assert manifest["manifest_hash"] == hash_expert_job_manifest(manifest)
    assert provider_plan["provider_plan_hash"].startswith("sha256:")
    assert provider_plan["provider_plan_hash"] == hash_expert_provider_plan(provider_plan)
    assert downstream_record["manifest_hash"] == manifest["manifest_hash"]
    assert downstream_record["provider_plan_hash"] == provider_plan["provider_plan_hash"]

    assert manifest["execution_allowed"] is False
    assert manifest["approval_required"] is True
    assert provider_plan["execution_allowed"] is False
    assert provider_plan["requires_operator_approval"] is True
    assert provider_plan["model_selected"] is None
    if provider_plan["provider_allowed"] is True:
        assert provider_plan.get("provider_candidate_is_metadata_only") is True
        assert provider_plan["selected_provider"] == "openrouter"
    else:
        assert provider_plan["selected_provider"] is None
        assert provider_plan["provider_role"] is None


def test_static_expert_evidence_chain_has_no_live_action_fields():
    packet = _valid_packet()
    lane_plan = select_expert_lane(packet)
    manifest = build_expert_job_manifest(packet, created_at="2026-05-01T09:05:00Z")
    provider_plan = select_expert_provider(packet, lane_plan)
    combined_keys = {str(key).lower() for artifact in (manifest, provider_plan) for key in artifact}
    rendered = repr({"manifest": manifest, "provider_plan": provider_plan}).lower()

    forbidden_key_fragments = {
        "command",
        "invoke",
        "shell",
        "telegram",
        "gmail",
        "service",
        "scheduler",
        "timer",
        "guardian",
        "live_request",
    }

    assert not any(fragment in key for key in combined_keys for fragment in forbidden_key_fragments)
    assert "openrouter_call" not in rendered
    assert "codex exec" not in rendered
    assert "guardian_live_request" not in rendered
    assert "telegram" not in rendered
    assert "gmail" not in rendered


def test_protected_marker_packet_fails_closed_through_manifest_and_provider_plan():
    packet = _valid_packet(prompt="Review synthetic code near /mnt/c/OpenClawLegalPrivate/demo.")
    lane_plan = select_expert_lane(packet)
    manifest = build_expert_job_manifest(packet, created_at="2026-05-01T09:05:00Z")
    provider_plan = select_expert_provider(packet, lane_plan)

    assert lane_plan["execution_allowed"] is False
    assert lane_plan["refusal_reason"] == "packet_checker_failed"
    assert any(violation.startswith("protected_marker:") for violation in lane_plan["violations"])

    assert manifest["execution_allowed"] is False
    assert manifest["approval_required"] is True
    assert manifest["checker_passed"] is False
    assert manifest["refusal_reason"] == "packet_checker_failed"
    assert any(violation.startswith("protected_marker:") for violation in manifest["violations"])

    assert provider_plan["provider_allowed"] is False
    assert provider_plan["execution_allowed"] is False
    assert provider_plan["requires_operator_approval"] is True
    assert provider_plan["refusal_reason"] == "packet_checker_failed"
    assert any(violation.startswith("protected_marker:") for violation in provider_plan["violations"])