import ast
import builtins
import copy
import inspect
import sys

import expert_approval_review_bundle as review_module
from expert_approval_packet import build_expert_approval_packet
from expert_approval_review_bundle import (
    build_expert_approval_review_bundle,
    render_expert_approval_review_bundle_markdown,
)
from expert_escalation_packet import REQUIRED_SENSITIVITY_ATTESTATIONS, build_expert_escalation_packet
from expert_staged_packet_flow import build_expert_staged_packet_artifact


def _attestation() -> dict[str, bool]:
    return {key: True for key in REQUIRED_SENSITIVITY_ATTESTATIONS}


def _valid_packet(**overrides):
    packet = build_expert_escalation_packet(
        packet_id="expert-20260501-review-bundle-code-review",
        created_at="2026-05-01T08:00:00Z",
        operator_request_summary="Review a synthetic public parser helper.",
        task_type="code_review",
        data_classification="synthetic_public",
        cloud_allowed=True,
        sensitivity_attestation=_attestation(),
        allowed_paths=("expert_approval_review_bundle.py", "tests/test_expert_approval_review_bundle.py"),
        forbidden_paths=("private-vaults", "secret-env-files", "gmail-bodies"),
        prompt="Review this synthetic public parser helper and return risks plus focused test ideas.",
        expected_outputs=("risk_summary", "test_suggestions"),
        execution_policy={
            "runner_class": "external_expert",
            "mode": "sequential_external_runner_only",
            "hermes_may_execute": False,
            "requires_checker_pass": True,
            "preferred_lane": "code_review",
            "candidate_provider": "openrouter",
        },
    )
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


def _valid_approval_packet(packet=None):
    source_packet = packet or _valid_packet()
    staged_artifact = build_expert_staged_packet_artifact(source_packet, created_at="2026-05-01T09:00:00Z")
    return build_expert_approval_packet(
        source_packet,
        staged_artifact,
        created_at="2026-05-01T10:00:00Z",
        staged_artifact_ref="staged_artifact:expert-20260501-review-bundle-code-review",
    )


def test_valid_approval_packet_produces_deterministic_review_bundle():
    approval_packet = _valid_approval_packet()

    first = build_expert_approval_review_bundle(approval_packet, created_at="2026-05-01T11:00:00Z")
    second = build_expert_approval_review_bundle(copy.deepcopy(approval_packet), created_at="2026-05-01T11:00:00Z")

    assert first == second
    assert first["bundle_type"] == "external_expert.approval_review_bundle"
    assert first["schema_version"] == 1
    assert first["created_at"] == "2026-05-01T11:00:00Z"
    assert first["packet_id"] == approval_packet["packet_id"]
    assert first["review_status"] == "ready_for_operator_review"
    assert first["operator_summary"]["task_title"] == approval_packet["task_title"]
    assert first["risk_summary"]["violation_count"] == 0
    assert first["next_allowed_action"] == "manual_operator_review_and_acknowledgement"
    assert first["source_artifact_refs"] == approval_packet["source_artifact_refs"]
    assert first["audit_refs"]["staged_packet_check"]["passed"] is True


def test_hashes_are_preserved_and_rendered_in_bounded_summary_form():
    approval_packet = _valid_approval_packet()

    bundle = build_expert_approval_review_bundle(approval_packet, created_at="2026-05-01T11:00:00Z")
    markdown = render_expert_approval_review_bundle_markdown(bundle)

    assert bundle["hash_summary"]["provider_plan_hash"] == approval_packet["provider_plan_hash"]
    assert bundle["hash_summary"]["manifest_hash"] == approval_packet["manifest_hash"]
    assert bundle["hash_summary"]["provider_plan_hash_short"].startswith("sha256:")
    assert bundle["hash_summary"]["manifest_hash_short"].startswith("sha256:")
    assert len(bundle["hash_summary"]["provider_plan_hash_short"]) < len(approval_packet["provider_plan_hash"])
    assert len(bundle["hash_summary"]["manifest_hash_short"]) < len(approval_packet["manifest_hash"])
    assert bundle["hash_summary"]["provider_plan_hash_short"] in markdown
    assert bundle["hash_summary"]["manifest_hash_short"] in markdown
    assert approval_packet["provider_plan_hash"] not in markdown
    assert approval_packet["manifest_hash"] not in markdown


def test_execution_provider_telegram_and_guardian_live_flags_remain_false():
    approval_packet = _valid_approval_packet()
    approval_packet["execution_allowed"] = True
    approval_packet["provider_call_allowed"] = True
    approval_packet["telegram_return_allowed"] = True
    approval_packet["approval_request_allowed"] = True

    bundle = build_expert_approval_review_bundle(approval_packet, created_at="2026-05-01T11:00:00Z")

    assert bundle["review_status"] == "blocked_pending_packet_repair"
    assert bundle["execution_allowed"] is False
    assert bundle["provider_call_allowed"] is False
    assert bundle["telegram_send_allowed"] is False
    assert bundle["guardian_live_request_allowed"] is False
    assert bundle["requires_human_review"] is True
    assert "execution_allowed" in bundle["risk_summary"]["violations"]
    assert "provider_call_allowed" in bundle["risk_summary"]["violations"]
    assert "telegram_return_allowed" in bundle["risk_summary"]["violations"]
    assert "approval_request_allowed" in bundle["risk_summary"]["violations"]


def test_required_acknowledgements_and_forbidden_actions_are_preserved():
    approval_packet = _valid_approval_packet()

    bundle = build_expert_approval_review_bundle(approval_packet, created_at="2026-05-01T11:00:00Z")

    assert bundle["required_human_acknowledgements"] == approval_packet["required_human_acknowledgements"]
    assert bundle["forbidden_actions"] == approval_packet["forbidden_actions"]
    assert "not_live_approval" in bundle["required_human_acknowledgements"]
    assert "provider_call" in bundle["forbidden_actions"]
    assert "live_guardian_approval_request" in bundle["forbidden_actions"]


def test_protected_private_markers_fail_closed_and_markdown_is_redacted():
    source_packet = _valid_packet(prompt="Review a synthetic parser near private logs and an api key.")
    approval_packet = _valid_approval_packet(source_packet)
    approval_packet["raw_private_text"] = "private logs api key should never be rendered"

    bundle = build_expert_approval_review_bundle(approval_packet, created_at="2026-05-01T11:00:00Z")
    markdown = render_expert_approval_review_bundle_markdown(bundle)

    assert bundle["review_status"] == "blocked_pending_packet_repair"
    assert bundle["execution_allowed"] is False
    assert bundle["provider_call_allowed"] is False
    assert bundle["telegram_send_allowed"] is False
    assert bundle["guardian_live_request_allowed"] is False
    assert any(violation.startswith("protected_marker:") for violation in bundle["risk_summary"]["violations"])
    assert bundle["operator_summary"]["task_summary"] == "Redacted pending sanitized approval packet repair."
    assert "private logs" not in markdown.lower()
    assert "api key" not in markdown.lower()
    assert "raw_private_text" not in markdown
    assert "should never be rendered" not in markdown


def test_missing_or_malformed_approval_packet_fails_closed():
    missing = build_expert_approval_review_bundle(None, created_at="2026-05-01T11:00:00Z")
    malformed = build_expert_approval_review_bundle(
        {"packet_type": "external_expert.approval_packet", "packet_id": "expert-20260501-malformed"},
        created_at="2026-05-01T11:00:00Z",
    )

    assert missing["review_status"] == "blocked_pending_packet_repair"
    assert missing["execution_allowed"] is False
    assert missing["provider_call_allowed"] is False
    assert missing["guardian_live_request_allowed"] is False
    assert "approval_packet_must_be_object" in missing["risk_summary"]["violations"]

    assert malformed["review_status"] == "blocked_pending_packet_repair"
    assert malformed["packet_id"] == "expert-20260501-malformed"
    assert malformed["execution_allowed"] is False
    assert malformed["provider_call_allowed"] is False
    assert malformed["telegram_send_allowed"] is False
    assert "missing_required_field:schema_version" in malformed["risk_summary"]["violations"]
    assert "approval_packet_not_passed" in malformed["risk_summary"]["violations"]


def test_markdown_renderer_is_string_only_and_bounded():
    approval_packet = _valid_approval_packet()
    bundle = build_expert_approval_review_bundle(approval_packet, created_at="2026-05-01T11:00:00Z")

    markdown = render_expert_approval_review_bundle_markdown(bundle)

    assert isinstance(markdown, str)
    assert len(markdown) <= 3601
    assert "# Expert Approval Review Bundle" in markdown
    assert "Provider plan hash" in markdown
    assert not hasattr(review_module, "write_expert_approval_review_bundle")
    assert not hasattr(review_module, "save_expert_approval_review_bundle")
    assert not hasattr(review_module, "write_expert_approval_review_bundle_markdown")


def test_review_bundle_module_does_not_import_or_call_external_surfaces(monkeypatch):
    source = inspect.getsource(review_module)
    tree = ast.parse(source)
    imported_modules = set()
    called_names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.add(node.module.split(".")[0])
        elif isinstance(node, ast.Call):
            called = node.func
            if isinstance(called, ast.Name):
                called_names.add(called.id)
            elif isinstance(called, ast.Attribute):
                called_names.add(called.attr)

    assert imported_modules <= {"__future__", "datetime", "expert_approval_packet", "re", "typing"}
    assert called_names.isdisjoint({"open", "write", "write_text", "openrouter_call", "run", "Popen", "urlopen", "Request", "systemctl"})
    forbidden_call_text = {
        "openrouter_call",
        "gmail_send",
        "guardian_send",
        "provider_execute",
        "model_execute",
        "runner_execute",
        "subprocess",
        "requests",
        "run_agent",
        "systemctl",
    }
    for text in forbidden_call_text:
        assert text not in source

    forbidden_modules = {
        "builder_watcher",
        "chief_llm",
        "chief_notify",
        "chief_sender",
        "cloud",
        "codex",
        "gateway",
        "gmail",
        "hermes_cli",
        "mcp",
        "openai",
        "openrouter",
        "pathlib",
        "requests",
        "runner_profiles",
        "runner_registry",
        "run_agent",
        "service",
        "subprocess",
        "systemd",
        "telegram",
        "urllib",
    }
    real_import = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        assert name.split(".")[0] not in forbidden_modules
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    approval_packet = _valid_approval_packet()
    bundle = build_expert_approval_review_bundle(approval_packet, created_at="2026-05-01T11:00:00Z")
    markdown = render_expert_approval_review_bundle_markdown(bundle)

    assert bundle["review_status"] == "ready_for_operator_review"
    assert bundle["execution_allowed"] is False
    assert bundle["guardian_live_request_allowed"] is False
    assert "Expert Approval Review Bundle" in markdown
    assert "expert_approval_review_bundle" in sys.modules