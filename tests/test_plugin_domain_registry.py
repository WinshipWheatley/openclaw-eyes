"""Tests for the read-only plugin domain registry."""

import pytest
from plugin_domain_registry import (
    _DOMAINS,
    get_plugin_domain,
    classify_plugin_domain_for_task,
    plugin_domain_registry_status,
)

REQUIRED_DOMAINS = {
    "architecture_map_gate",
    "file_territory_cleanup",
    "no_build_prior_art",
    "receipt_completion_gate",
    "sensitive_boundary",
    "map_room_query_navigation_lookup",
}

def test_every_required_domain_exists():
    assert set(_DOMAINS.keys()) == REQUIRED_DOMAINS

def test_every_domain_has_required_fields():
    for domain_id, domain in _DOMAINS.items():
        assert domain.domain_id == domain_id
        assert bool(domain.domain_name)
        assert bool(domain.artifact_type)
        assert bool(domain.value_space)
        assert bool(domain.job_owned)
        assert bool(domain.does_not_own)
        assert bool(domain.activation_trigger)
        assert bool(domain.forbidden_actions)
        assert bool(domain.right_size_check)
        assert bool(domain.proof_required_before_activation)
        assert domain.current_status in {"candidate", "designed", "scaffolded", "implemented", "active", "deprecated", "blocked"}

def test_no_domain_is_marked_active():
    for domain in _DOMAINS.values():
        assert domain.is_active_plugin is False
        assert domain.current_status != "active"

def test_implemented_does_not_mean_active_plugin():
    for domain in _DOMAINS.values():
        if domain.current_status == "implemented":
            assert domain.is_active_plugin is False

def test_classification_picks_expected_domain():
    assert classify_plugin_domain_for_task("check frontier map before building").matched_domain_id == "architecture_map_gate"
    assert classify_plugin_domain_for_task("reorganize the folder structure").matched_domain_id == "file_territory_cleanup"
    assert classify_plugin_domain_for_task("should we build this or use existing tools?").matched_domain_id == "no_build_prior_art"
    assert classify_plugin_domain_for_task("run receipt to prove task is done").matched_domain_id == "receipt_completion_gate"
    assert classify_plugin_domain_for_task("move files in private root legal directory").matched_domain_id == "sensitive_boundary"
    assert classify_plugin_domain_for_task("where is the chief_listener.py file?").matched_domain_id == "map_room_query_navigation_lookup"

def test_over_wide_task_text_marked_manual_review():
    match = classify_plugin_domain_for_task("plan the architecture and run receipt and then cleanup files")
    assert match.matched_domain_id is None
    assert match.is_manual_review_required is True

def test_unknown_task_text_marked_manual_review():
    match = classify_plugin_domain_for_task("make me a coffee")
    assert match.matched_domain_id is None
    assert match.is_manual_review_required is True

def test_registry_status_proves_read_only():
    status = plugin_domain_registry_status()
    assert status["is_execution_authority"] is False
    assert status["active_plugins_exist"] is False
    assert status["all_plugins_inactive"] is True
    assert "grants no execution authority" in status["authority_note"]

def test_module_does_not_import_forbidden_libraries():
    import sys
    import plugin_domain_registry
    
    # A bit hacky way to check for missing imports in the module
    forbidden_modules = {"subprocess", "socket", "urllib", "sqlite3"}
    for module_name in forbidden_modules:
        if module_name in sys.modules:
            # If it's loaded globally, check if it's imported in the specific module
            assert not hasattr(plugin_domain_registry, module_name)
    assert not hasattr(plugin_domain_registry, "requests")
    assert not hasattr(plugin_domain_registry, "http")
