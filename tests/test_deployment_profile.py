from __future__ import annotations

import json
import re
import socket
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from legal.deployment_profile import (
    default_legal_local_profile,
    load_deployment_profile,
    save_deployment_profile,
    validate_deployment_profile,
)
from legal.path_guard import PRODUCT_REPO_ROOT


FORBIDDEN_INTERNAL_NAMES = (
    "Cassandra",
    "Chief",
    "Guardian",
    "Hermes",
    "PI",
    "cassandra",
    "chief",
    "guardian",
    "hermes",
)


def _assert_forbidden_names_absent(text: str) -> None:
    for forbidden in FORBIDDEN_INTERNAL_NAMES:
        if forbidden == "PI":
            assert re.search(r"\bPI\b", text) is None
        else:
            assert forbidden not in text


def test_default_profile_contains_required_fields() -> None:
    profile = default_legal_local_profile("Example Law")

    assert profile["profile_name"] == "legal-local"
    assert profile["firm_name"] == "Example Law"
    assert profile["created_at"].endswith("Z")
    assert profile["mode"] == "local_first"
    assert set(profile["enabled_modules"]) == {
        "matter_workspace",
        "local_ingestion",
        "local_search",
        "search_report",
        "demo_workflow",
    }
    assert "agent_labels" not in profile
    assert profile["role_labels"] == {
        "intake_clerk": "Intake Clerk",
        "evidence_clerk": "Evidence Clerk",
        "records_custodian": "Records Custodian",
        "review_coordinator": "Review Coordinator",
        "compliance_gate": "Compliance Gate",
        "systems_clerk": "Systems Clerk",
    }
    assert profile["storage"] == {
        "matters_root": "matters",
        "exports_root": None,
    }


def test_default_profile_does_not_expose_internal_openclaw_role_names() -> None:
    profile_text = json.dumps(default_legal_local_profile("Example Law"), sort_keys=True)

    _assert_forbidden_names_absent(profile_text)


def test_default_profile_is_local_first_and_cloud_disabled() -> None:
    profile = default_legal_local_profile("Example Law")

    assert profile["mode"] == "local_first"
    assert profile["enabled_modules"]["demo_workflow"] is False
    assert profile["safety_defaults"] == {
        "no_autonomous_send": True,
        "require_attorney_review": True,
        "no_cloud_llm_by_default": True,
        "source_grounded_outputs": True,
        "audit_all_actions": True,
    }
    assert profile["connectors"] == {
        "gmail_enabled": False,
        "calendar_enabled": False,
        "drive_enabled": False,
    }


def test_custom_firm_name_and_profile_name() -> None:
    profile = default_legal_local_profile(
        "Harbor Legal Group",
        profile_name="harbor-local",
    )

    assert profile["firm_name"] == "Harbor Legal Group"
    assert profile["profile_name"] == "harbor-local"


def test_validation_passes_for_default_profile() -> None:
    profile = default_legal_local_profile("Example Law")

    assert validate_deployment_profile(profile) == []


def test_validation_accepts_legacy_agent_labels_for_compatibility() -> None:
    profile = default_legal_local_profile("Example Law")
    profile.pop("role_labels")
    profile["agent_labels"] = {
        "cassandra": "Legal Intake Assistant",
        "chief": "Legal Operations Coordinator",
        "guardian": "Review and Safety Gate",
        "hermes": "Client Communications Relay",
    }

    assert validate_deployment_profile(profile) == []


def test_validation_catches_missing_required_sections() -> None:
    profile = default_legal_local_profile("Example Law")
    del profile["safety_defaults"]
    del profile["connectors"]

    errors = validate_deployment_profile(profile)

    assert "missing required field: safety_defaults" in errors
    assert "missing required field: connectors" in errors
    assert "safety_defaults must be a dict" in errors
    assert "connectors must be a dict" in errors


def test_validation_catches_non_bool_safety_defaults_and_connectors() -> None:
    profile = default_legal_local_profile("Example Law")
    profile["safety_defaults"]["audit_all_actions"] = "yes"
    profile["connectors"]["gmail_enabled"] = "false"
    profile["enabled_modules"]["local_search"] = 1

    errors = validate_deployment_profile(profile)

    assert "safety_defaults.audit_all_actions must be a bool" in errors
    assert "connectors.gmail_enabled must be a bool" in errors
    assert "enabled_modules.local_search must be a bool" in errors


def test_validation_catches_unknown_mode_values() -> None:
    profile = default_legal_local_profile("Example Law")
    profile["mode"] = "cloud_first"

    assert validate_deployment_profile(profile) == ["mode must be 'local_first'"]


def test_validation_allows_unknown_extra_keys_for_forward_compatibility() -> None:
    profile = default_legal_local_profile("Example Law")
    profile["future"] = {"new_field": True}
    profile["enabled_modules"]["future_module"] = True

    assert validate_deployment_profile(profile) == []


def test_validation_accepts_optional_safe_vault_roots(tmp_path: Path) -> None:
    profile = default_legal_local_profile("Example Law")
    profile["storage"]["vault_roots"] = [str(tmp_path / "legal-vault")]

    assert validate_deployment_profile(profile) == []


def test_validation_rejects_optional_repo_vault_roots() -> None:
    profile = default_legal_local_profile("Example Law")
    profile["storage"]["vault_roots"] = [str(PRODUCT_REPO_ROOT / "legal-vault")]

    errors = validate_deployment_profile(profile)

    assert len(errors) == 1
    assert "storage.vault_roots invalid" in errors[0]
    assert "vault root must be outside product repo" in errors[0]


@pytest.mark.parametrize("vault_roots", [[], [""], "not-a-list"])
def test_validation_rejects_malformed_optional_vault_roots(vault_roots: object) -> None:
    profile = default_legal_local_profile("Example Law")
    profile["storage"]["vault_roots"] = vault_roots

    assert validate_deployment_profile(profile)


def test_save_load_round_trip(tmp_path: Path) -> None:
    profile = default_legal_local_profile("Example Law")
    path = tmp_path / "profile.json"

    save_deployment_profile(profile, path)

    assert load_deployment_profile(path) == profile
    text = path.read_text(encoding="utf-8")
    assert text.endswith("\n")
    assert '\n  "role_labels": {' in text
    assert "agent_labels" not in text


def test_readme_does_not_expose_internal_openclaw_role_names() -> None:
    readme = (Path(__file__).resolve().parents[1] / "legal" / "README.md").read_text(
        encoding="utf-8"
    )

    _assert_forbidden_names_absent(readme)


def test_no_network_calls_for_profile_helpers(tmp_path: Path) -> None:
    path = tmp_path / "profile.json"

    with patch.object(socket, "create_connection", side_effect=AssertionError):
        profile = default_legal_local_profile("Example Law")
        assert validate_deployment_profile(profile) == []
        save_deployment_profile(profile, path)
        assert load_deployment_profile(path) == profile
