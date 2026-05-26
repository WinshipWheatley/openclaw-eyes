import json
import re
import sys
from dataclasses import fields
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import agent_roster_model_backend_policy as policy
from scripts.export_agent_roster_model_backend_policy import main as export_main


FIXED_NOW = "2026-05-26T00:00:00+00:00"


def _payload() -> dict:
    return policy.build_payload(generated_at=FIXED_NOW, repo_root=ROOT)


def _by_key(rows: tuple[dict, ...] | list[dict], key: str) -> dict[str, dict]:
    return {row[key]: row for row in rows}


def test_required_models_exist_with_required_fields():
    expected = {
        "AgentRosterPolicy": (
            "policy_id",
            "doctrine",
            "agent_roles",
            "system_identities",
            "model_backend_roles",
            "worker_backend_roles",
            "separation_policy",
            "forbidden_conflations",
            "legacy_migration_notes",
            "authority_boundary",
            "next_safe_move",
        ),
        "OpenClawAgentProfile": (
            "agent_role",
            "display_name",
            "primary_domain",
            "role_purpose",
            "voice_profile_ref",
            "vibe_profile_ref",
            "allowed_task_types",
            "forbidden_task_types",
            "default_model_policy_ref",
            "authority_boundary",
            "next_safe_move",
        ),
        "SystemIdentityProfile": (
            "system_identity_ref",
            "display_name",
            "purpose",
            "allowed_surfaces",
            "forbidden_persona_behavior",
            "authority_boundary",
            "next_safe_move",
        ),
        "ModelBackendProfile": (
            "model_backend_ref",
            "provider_family",
            "display_name",
            "suitable_task_types",
            "strengths",
            "weaknesses",
            "local_or_cloud",
            "privacy_class_allowed",
            "credit_cost_class",
            "latency_class",
            "context_window_class",
            "json_schema_reliability",
            "code_quality_score",
            "creative_quality_score",
            "reasoning_quality_score",
            "tool_support_class",
            "blocked_contexts",
            "next_safe_move",
        ),
        "ModelSelectionPolicy": (
            "model_selection_id",
            "agent_role",
            "task_type",
            "candidate_model_backends",
            "preferred_model_backend",
            "fallback_model_backend",
            "local_or_cloud_preference",
            "privacy_class",
            "credit_cost_class",
            "latency_requirement",
            "context_window_need",
            "tool_support_need",
            "json_schema_reliability_need",
            "creative_quality_need",
            "code_quality_need",
            "reasoning_quality_need",
            "selected_reason",
            "blocked_models",
            "authority_boundary",
            "next_safe_move",
        ),
        "WorkerBackendType": (
            "worker_backend_ref",
            "worker_type",
            "description",
            "allowed_task_types",
            "target_machine",
            "authority_boundary",
            "next_safe_move",
        ),
        "LegacyOntologyFinding": (
            "finding_id",
            "source_file",
            "legacy_pattern",
            "risk",
            "recommended_replacement",
            "migration_status",
            "next_safe_move",
        ),
        "AgentModelBindingExample": (
            "example_id",
            "agent_role",
            "task_type",
            "selected_model_backend",
            "selected_worker_type",
            "allowed_tools",
            "forbidden_tools",
            "authority_boundary",
            "why_this_is_correct",
            "bad_example",
            "why_bad",
            "next_safe_move",
        ),
    }
    classes = {
        "AgentRosterPolicy": policy.AgentRosterPolicy,
        "OpenClawAgentProfile": policy.OpenClawAgentProfile,
        "SystemIdentityProfile": policy.SystemIdentityProfile,
        "ModelBackendProfile": policy.ModelBackendProfile,
        "ModelSelectionPolicy": policy.ModelSelectionPolicy,
        "WorkerBackendType": policy.WorkerBackendType,
        "LegacyOntologyFinding": policy.LegacyOntologyFinding,
        "AgentModelBindingExample": policy.AgentModelBindingExample,
    }
    for name, required_fields in expected.items():
        assert tuple(field.name for field in fields(classes[name])) == required_fields


def test_five_required_agents_exist_and_backends_are_not_agents():
    payload = _payload()
    agents = _by_key(payload["agent_profiles"], "agent_role")
    systems = _by_key(payload["system_identity_profiles"], "system_identity_ref")

    assert set(agents) == {"CASSANDRA", "CHIEF", "NILES", "GUARDIAN", "HERMES"}
    assert "system_identity:openclaw_system" in systems
    assert "OPENCLAW_SYSTEM" not in agents
    assert "CODEX" not in agents
    assert "GEMINI_AGY" not in agents
    assert "LOCAL_OLLAMA" not in agents
    assert payload["machine_proof"]["codex_is_not_agent"] is True
    assert payload["machine_proof"]["gemini_agy_is_not_agent"] is True
    assert payload["machine_proof"]["openclaw_system_is_system_identity_not_agent"] is True


def test_agent_profiles_capture_required_domains_and_boundaries():
    payload = _payload()
    agents = _by_key(payload["agent_profiles"], "agent_role")

    assert "communications" in agents["CASSANDRA"]["primary_domain"]
    assert "SEND_EMAIL_WITHOUT_GATE" in agents["CASSANDRA"]["forbidden_task_types"]
    assert "operations" in agents["CHIEF"]["primary_domain"]
    assert "music" in agents["NILES"]["primary_domain"]
    assert "DAW_FILE_MUTATION_WITHOUT_GATE" in agents["NILES"]["forbidden_task_types"]
    assert "proof" in agents["GUARDIAN"]["primary_domain"]
    assert "systems auditor" in agents["HERMES"]["primary_domain"]
    assert "REPLACE_GUARDIAN" in agents["HERMES"]["forbidden_task_types"]
    for agent in agents.values():
        assert all(value is False for value in agent["authority_boundary"].values())


def test_model_backend_profiles_and_model_selection_exist():
    payload = _payload()
    backends = _by_key(payload["model_backend_profiles"], "model_backend_ref")
    selections = _by_key(payload["model_selection_policies"], "model_selection_id")

    assert {"OPENAI_CODEX", "OPENAI_GPT", "GEMINI_AGY", "CLAUDE", "LOCAL_OLLAMA"}.issubset(
        {backend["provider_family"] for backend in backends.values()}
    )
    assert backends["model_backend:openai_codex"]["provider_family"] == "OPENAI_CODEX"
    assert "not an agent" in " ".join(backends["model_backend:openai_codex"]["weaknesses"])
    assert selections["model_selection:chief:planning_code_backend"]["agent_role"] == "CHIEF"
    assert selections["model_selection:chief:planning_code_backend"]["preferred_model_backend"] == "model_backend:openai_codex"
    assert selections["model_selection:hermes:audit"]["agent_role"] == "HERMES"
    assert selections["model_selection:hermes:audit"]["preferred_model_backend"] == "model_backend:gemini_agy"
    for selection in selections.values():
        assert all(value is False for value in selection["authority_boundary"].values())


def test_worker_backend_types_are_not_agent_identity():
    payload = _payload()
    workers = _by_key(payload["worker_backend_types"], "worker_type")

    assert set(workers) == set(policy.WORKER_TYPES)
    assert workers["PC_CODEX_WORKER"]["target_machine"] == "PC_WSL"
    assert workers["MAC_CODEX_WORKER"]["target_machine"] == "MAC"
    assert workers["GEMINI_AGY_ADVISORY_WORKER"]["target_machine"] == "EXTERNAL_MODEL"
    assert workers["UNKNOWN_FAIL_CLOSED"]["target_machine"] == "UNKNOWN"
    for worker in workers.values():
        assert all(value is False for value in worker["authority_boundary"].values())


def test_legacy_ontology_findings_cover_present_codex_and_gemini_patterns():
    payload = _payload()
    findings = _by_key(payload["legacy_ontology_findings"], "finding_id")

    assert findings["legacy:request_processor:codex_responder_future"]["migration_status"] == "FOUND_LEGACY_COMPATIBILITY_NAME"
    assert findings["legacy:request_processor:gemini_responder_future"]["migration_status"] == "FOUND_LEGACY_COMPATIBILITY_NAME"
    assert findings["legacy:scoped_context:target_agent_roles"]["migration_status"] == "FOUND_LEGACY_COMPATIBILITY_NAME"
    assert findings["legacy:agent_phrases:codex_gemini"]["migration_status"] in {
        "FOUND_LEGACY_COMPATIBILITY_NAME",
        "SOURCE_FILE_NOT_PRESENT",
        "NOT_PRESENT",
    }
    assert findings["legacy:agent_role_enum:codex"]["migration_status"] == "MIGRATED_TO_MODEL_BACKEND"


def test_required_examples_exist_and_invalid_examples_are_invalid():
    payload = _payload()
    examples = _by_key(payload["binding_examples"], "example_id")

    assert examples["example:chief_uses_code_backend"]["agent_role"] == "CHIEF"
    assert examples["example:chief_uses_code_backend"]["selected_model_backend"] == "model_backend:openai_codex"
    assert examples["example:hermes_uses_gemini_agy"]["agent_role"] == "HERMES"
    assert examples["example:hermes_uses_gemini_agy"]["selected_worker_type"] == "GEMINI_AGY_ADVISORY_WORKER"
    assert examples["example:cassandra_draft_model"]["agent_role"] == "CASSANDRA"
    assert "email_send" in examples["example:cassandra_draft_model"]["forbidden_tools"]
    assert examples["example:niles_creative_model"]["agent_role"] == "NILES"
    assert "daw_mutation" in examples["example:niles_creative_model"]["forbidden_tools"]
    assert examples["example:guardian_deterministic_first"]["agent_role"] == "GUARDIAN"
    assert "deterministic gates" in examples["example:guardian_deterministic_first"]["why_this_is_correct"]
    assert examples["example:openclaw_system_file_intake"]["agent_role"] == "SYSTEM_IDENTITY:OPENCLAW_SYSTEM"
    assert examples["bad_example:codex_as_agent"]["agent_role"] == "INVALID:CODEX"
    assert "not one of the five named agents" in examples["bad_example:codex_as_agent"]["why_bad"]
    assert examples["bad_example:model_backend_grants_authority"]["agent_role"] == "INVALID:GEMINI_AGY"
    assert "cannot grant authority" in examples["bad_example:model_backend_grants_authority"]["why_bad"]
    assert payload["machine_proof"]["codex_as_agent_bad_example_invalid"] is True
    assert payload["machine_proof"]["model_backend_grants_authority_bad_example_invalid"] is True


def test_all_live_authority_false_and_no_private_bodies():
    payload = _payload()

    assert payload["machine_proof"]["all_live_authority_false"] is True
    assert payload["machine_proof"]["model_call_performed"] is False
    assert payload["machine_proof"]["agent_dispatch_performed"] is False
    assert payload["machine_proof"]["worker_dispatch_performed"] is False
    assert payload["machine_proof"]["tool_use_performed"] is False
    for value in payload["authority_boundary"].values():
        assert value is False

    text = policy.stable_json(payload)
    assert "-----BEGIN" not in text
    assert "raw_body_value" not in text
    assert "raw_private_body" not in text
    assert "api_key:" not in text.lower()
    assert not re.search(r"(?i)(password|token|secret|credential)\s*[:=]\s*[A-Za-z0-9+/=_-]{12,}", text)


def test_export_writes_json_and_operator_markdown(tmp_path, capsys):
    assert export_main(
        [
            "--generated-at",
            FIXED_NOW,
            "--repo-root",
            str(ROOT),
            "--export-root",
            str(tmp_path),
            "--format",
            "summary",
        ]
    ) == 0
    summary = json.loads(capsys.readouterr().out)
    payload = json.loads((tmp_path / policy.JSON_EXPORT_NAME).read_text(encoding="utf-8"))
    operator = (tmp_path / policy.OPERATOR_EXPORT_NAME).read_text(encoding="utf-8")

    assert summary["read_model_id"] == policy.READ_MODEL_ID
    assert summary["agent_count"] == 5
    assert summary["codex_is_not_agent"] is True
    assert summary["gemini_agy_is_not_agent"] is True
    assert summary["all_live_authority_false"] is True
    assert payload["read_model_id"] == policy.READ_MODEL_ID
    assert "Agent Roster + Model Backend Policy" in operator
