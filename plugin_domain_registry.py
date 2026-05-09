"""
Plugin Domain Registry v0
A read-only, durable registry for future OpenClaw plugin/workflow-package domains.
This module classifies tasks and looks up domain definitions. It does NOT claim any
active plugins exist, and it grants no execution authority.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

@dataclass(frozen=True)
class PluginDomain:
    domain_id: str
    domain_name: str
    artifact_type: str
    value_space: str
    job_owned: str
    does_not_own: str
    activation_trigger: str
    inputs: str
    outputs: str
    required_maps: str
    required_scripts_hooks_checks: str
    authority_boundaries: str
    forbidden_actions: str
    right_size_check: str
    current_status: str
    is_active_plugin: bool
    proof_required_before_activation: str


@dataclass(frozen=True)
class PluginDomainMatch:
    matched_domain_id: Optional[str]
    is_manual_review_required: bool
    reason: str


_DOMAINS: Dict[str, PluginDomain] = {
    "architecture_map_gate": PluginDomain(
        domain_id="architecture_map_gate",
        domain_name="Architecture & Map Gate",
        artifact_type="candidate plugin/workflow domain, not active plugin",
        value_space="Ensures safe codebase navigation by looking up built/unbuilt territory before planning, preventing duplicated work and unapproved custom builds.",
        job_owned="Architecture intake, Map Room lookup, frontier check, duplicate-work prevention, no-build/prior-art check, boundary framing.",
        does_not_own="Editing files directly, moving folders, runtime launch, approval, private-root access, or final commit authority.",
        activation_trigger="Starting a new task, receiving a new feature request, or mapping a proposed solution.",
        inputs="User request, current frontier, existing docs/navigation_maps/.",
        outputs="Safe navigation path, prior-art warnings, and boundary framing context.",
        required_maps="Map Room Index, Frontier Maps, No-Build / Prior-Art Sources.",
        required_scripts_hooks_checks="map_room_query.py, operator_frontier_map.py, receipt checks.",
        authority_boundaries="Strictly read-only navigation lookup.",
        forbidden_actions="Mutating maps, directly editing code, granting approval, launching execution.",
        right_size_check="One coherent workflow validating 'what exists and what is allowed' before any work begins. It does not mix validation with execution.",
        current_status="scaffolded",
        is_active_plugin=False,
        proof_required_before_activation="Deterministic lookup tests, Map Room Query v0 completion, receipt integration.",
    ),
    "file_territory_cleanup": PluginDomain(
        domain_id="file_territory_cleanup",
        domain_name="File Territory / Cleanup",
        artifact_type="candidate plugin/workflow domain, not active plugin",
        value_space="Makes repository hygiene and structural evolution safer by pre-validating moves and enforcing explicit path-dependency safety.",
        job_owned="Path lookup, dependency scan, candidate move plans, dry-run validation, rollback proof.",
        does_not_own="Actual move/delete/rename/archive until separately approved.",
        activation_trigger="Proposal to refactor paths, organize folders, or remove stale files.",
        inputs="Target paths, dependency scans (FILE_PATH_DEPENDENCY_SCAN.json).",
        outputs="Dry-run readiness receipt, candidate move plan, rollback steps.",
        required_maps="FILE_TERRITORY_CLEANUP_READINESS_MAP.md, DEPENDENCY_OWNER_CANDIDATE_MOVE_MAP.md.",
        required_scripts_hooks_checks="scripts/file_path_dependency_scan.py, dry-run validators.",
        authority_boundaries="Analysis and planning only. Blocks on explicit approval.",
        forbidden_actions="Moving, deleting, renaming, or archiving files.",
        right_size_check="Strictly scoping file-path analysis separate from file-content editing.",
        current_status="candidate",
        is_active_plugin=False,
        proof_required_before_activation="Path dependency map tests, dry-run hooks built.",
    ),
    "no_build_prior_art": PluginDomain(
        domain_id="no_build_prior_art",
        domain_name="No-Build / Prior-Art",
        artifact_type="candidate plugin/workflow domain, not active plugin",
        value_space="Prevents reinventing existing tools and promotes using established prior art.",
        job_owned="Identifying if a tool already exists for a given task.",
        does_not_own="Building new features, executing tools.",
        activation_trigger="Proposing a new feature or script.",
        inputs="Feature description, task intent.",
        outputs="List of existing tools or confirmation of novelty.",
        required_maps="No-Build / Prior-Art Sources.",
        required_scripts_hooks_checks="Registry lookups.",
        authority_boundaries="Read-only suggestions.",
        forbidden_actions="Installing packages, altering build scripts.",
        right_size_check="Separating tool discovery from tool execution.",
        current_status="candidate",
        is_active_plugin=False,
        proof_required_before_activation="Prior-art catalog completion.",
    ),
    "receipt_completion_gate": PluginDomain(
        domain_id="receipt_completion_gate",
        domain_name="Receipt / Completion Gate",
        artifact_type="candidate plugin/workflow domain, not active plugin",
        value_space="Ensures strict definition of done before marking tasks as complete.",
        job_owned="Running receipts, verifying tests, proving completeness.",
        does_not_own="Writing code, changing tests, committing.",
        activation_trigger="Requesting to finish, commit, or close a task.",
        inputs="Completed work, test commands, receipt scripts.",
        outputs="Proof of completeness or rejection.",
        required_maps="Validation maps.",
        required_scripts_hooks_checks="scripts/openclaw_receipts.py, pytest.",
        authority_boundaries="Read-only test execution.",
        forbidden_actions="Altering test results, skipping tests.",
        right_size_check="Validating work, not doing the work.",
        current_status="candidate",
        is_active_plugin=False,
        proof_required_before_activation="Receipt script integration.",
    ),
    "sensitive_boundary": PluginDomain(
        domain_id="sensitive_boundary",
        domain_name="Sensitive Boundary",
        artifact_type="candidate plugin/workflow domain, not active plugin",
        value_space="Guards private-root, legal, finance, and sensitive areas.",
        job_owned="Detecting sensitive territory, applying quarantine policies.",
        does_not_own="Reading sensitive files, modifying sensitive files.",
        activation_trigger="Attempting to access or alter private or sensitive paths.",
        inputs="Target paths.",
        outputs="Boundary enforcement ruling.",
        required_maps="Sensitive root quarantine policy.",
        required_scripts_hooks_checks="openclaw_sensitive_policy.py.",
        authority_boundaries="Access control mapping, not access granting.",
        forbidden_actions="Reading or editing legal/finance/private files.",
        right_size_check="Boundary detection isolated from boundary crossing.",
        current_status="candidate",
        is_active_plugin=False,
        proof_required_before_activation="Sensitive policy strict test coverage.",
    ),
    "map_room_query_navigation_lookup": PluginDomain(
        domain_id="map_room_query_navigation_lookup",
        domain_name="Map Room Query / Navigation Lookup",
        artifact_type="candidate plugin/workflow domain, not active plugin",
        value_space="Provides deterministic answers to 'Where is X?' and 'What depends on X?'.",
        job_owned="Querying map room definitions, finding dependencies.",
        does_not_own="Modifying map room definitions.",
        activation_trigger="Questions about file locations, dependencies, or territory.",
        inputs="Query string (file path, dependency name).",
        outputs="Territory lookup results.",
        required_maps="All map room artifacts.",
        required_scripts_hooks_checks="map_room_query.py.",
        authority_boundaries="Read-only map room lookup.",
        forbidden_actions="Mutating map room files.",
        right_size_check="Querying only, isolated from map creation.",
        current_status="implemented",
        is_active_plugin=False,
        proof_required_before_activation="map_room_query.py fully tested.",
    ),
}

def get_plugin_domain(domain_id: str) -> PluginDomain:
    """Retrieve a plugin domain by its ID. Raises KeyError if not found."""
    return _DOMAINS[domain_id]

def classify_plugin_domain_for_task(task_text: str) -> PluginDomainMatch:
    """
    Classify task text to determine which plugin domain owns it.
    Returns manual review if unknown or too broad.
    """
    text = task_text.lower()
    
    # Priority 1: Sensitive Boundary (Always gate sensitive areas first)
    if any(kw in text for kw in ("private root", "legal", "finance", "music-law", "sensitive path", "sensitive root")):
        return PluginDomainMatch("sensitive_boundary", False, "Matches sensitive boundary tasks.")

    # Check for multiple distinct intents making the task too broad
    intents = []
    if any(kw in text for kw in ("architecture", "planning", "frontier", "map", "check before build", "check-before-build")):
        intents.append("architecture_map_gate")
    if any(kw in text for kw in ("cleanup", "reorganize", "move", "archive dependency", "path dependency", "file cleanup")):
        intents.append("file_territory_cleanup")
    if any(kw in text for kw in ("should we build this", "use existing tools", "prior art")):
        intents.append("no_build_prior_art")
    if any(kw in text for kw in ("finish", "commit", "proof", "test", "receipt")):
        intents.append("receipt_completion_gate")
    if any(kw in text for kw in ("where is", "what depends on", "territory lookup", "navigation lookup")):
        intents.append("map_room_query_navigation_lookup")

    if len(intents) > 1:
        return PluginDomainMatch(
            matched_domain_id=None,
            is_manual_review_required=True,
            reason=f"Task is too broad and spans multiple plugin domains: {', '.join(intents)}"
        )

    if "architecture_map_gate" in intents:
        return PluginDomainMatch("architecture_map_gate", False, "Matches architecture/planning tasks.")
    if "file_territory_cleanup" in intents:
        return PluginDomainMatch("file_territory_cleanup", False, "Matches file cleanup/dependency tasks.")
    if "no_build_prior_art" in intents:
        return PluginDomainMatch("no_build_prior_art", False, "Matches no-build/prior-art tasks.")
    if "receipt_completion_gate" in intents:
        return PluginDomainMatch("receipt_completion_gate", False, "Matches finish/commit/receipt tasks.")
    if "map_room_query_navigation_lookup" in intents:
        return PluginDomainMatch("map_room_query_navigation_lookup", False, "Matches map room lookup tasks.")

    return PluginDomainMatch(
        matched_domain_id=None,
        is_manual_review_required=True,
        reason="Unknown task type requires manual review."
    )

def plugin_domain_registry_status() -> dict[str, object]:
    """Return the status of the plugin domain registry."""
    return {
        "receipt_type": "openclaw.plugin_domain_registry_status",
        "mode": "read-only/static-registry/no-active-plugins",
        "registry_active": True,
        "is_execution_authority": False,
        "active_plugins_exist": False,
        "registered_domains": list(_DOMAINS.keys()),
        "domain_statuses": {domain_id: domain.current_status for domain_id, domain in _DOMAINS.items()},
        "all_plugins_inactive": all(not domain.is_active_plugin for domain in _DOMAINS.values()),
        "authority_note": "This registry is a read-only planning surface. It grants no execution authority and claims no live plugins.",
    }
