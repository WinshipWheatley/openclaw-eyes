"""
Architecture & Map Gate v0
A read-only callable intake gate for architecture and build requests.
This module classifies requests to prevent duplicate work, protect sensitive boundaries,
and ensure prior-art checks. It grants no execution authority.
"""

from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Optional

import plugin_domain_registry
import map_room_query
import operator_frontier_map

@dataclass(frozen=True)
class ArchitectureGateResult:
    request_text: str
    matched_plugin_domain_id: Optional[str]
    gate_decision: str
    decision_reason: str
    already_built_risk: bool
    too_broad: bool
    blocked: bool
    needs_prior_art_check: bool
    sensitive_boundary_risk: bool
    ready_for_bounded_slice: bool
    required_maps_checked: List[str]
    required_registry_domains_checked: List[str]
    forbidden_actions: List[str]
    next_safe_step: str
    execution_authority_granted: bool
    active_plugin_claimed: bool

def evaluate_architecture_request(request_text: str) -> ArchitectureGateResult:
    """
    Evaluate an architecture request and return a gate decision.
    This function is read-only and does not grant execution authority.
    """
    # 1. Use plugin_domain_registry.classify_plugin_domain_for_task()
    domain_match = plugin_domain_registry.classify_plugin_domain_for_task(request_text)
    
    # 2. Use plugin_domain_registry.get_plugin_domain("architecture_map_gate")
    arch_domain = plugin_domain_registry.get_plugin_domain("architecture_map_gate")
    
    # Initial state
    gate_decision = "unknown_manual_review"
    decision_reason = domain_match.reason
    already_built_risk = False
    too_broad = (
        domain_match.is_manual_review_required
        and domain_match.reason.startswith("Task is too broad")
    )
    blocked = False
    needs_prior_art_check = False
    sensitive_boundary_risk = False
    ready_for_bounded_slice = False
    next_safe_step = "manual review required"
    
    normalized_text = request_text.lower()
    
    # 3. Use map_room_query.lookup_file_territory() when request mentions known file territory terms
    # Check for sensitive paths/terms
    sensitive_terms = ("mac_eyes", "openclawlegalprivate", "private", "sensitive", "legal", "finance")
    for term in sensitive_terms:
        if term in normalized_text:
            sensitive_boundary_risk = True
            blocked = True
            break
            
    # Priority classification logic
    
    # 4. Detect already-built compiled knowledge substrate / frontier map rebuild requests
    frontier_finding = operator_frontier_map.evaluate_frontier_task(request_text)
    if frontier_finding.duplicate_risk:
        already_built_risk = True
        gate_decision = "already_built_review_required"
        decision_reason = frontier_finding.recommendation
        next_safe_step = frontier_finding.prerequisite_to_finish_first
    
    # 5. Sensitive/private-root requests must return blocked_sensitive_boundary
    elif sensitive_boundary_risk or blocked:
        gate_decision = "blocked_sensitive_boundary"
        decision_reason = "Request targets a sensitive or private-root boundary."
        next_safe_step = "Do not access private roots. Consult operator for manual review."
        blocked = True

    # 6. Rebuilding known OpenClaw substrate must not be treated as generic prior art.
    elif "rebuild" in normalized_text and any(
        kw in normalized_text for kw in ("map room", "plugin system", "registry", "frontier", "openclaw")
    ):
        already_built_risk = True
        gate_decision = "already_built_review_required"
        decision_reason = "Request to rebuild established Map Room, plugin system, or core substrate."
        next_safe_step = "Consult existing maps and registry before proposing a rebuild."

    # 7. Broad all-system/all-file requests must not be treated as ready or generic prior-art.
    elif too_broad or any(kw in normalized_text for kw in ("everything", "all folders", "all files")):
        gate_decision = "too_broad_manual_review"
        decision_reason = domain_match.reason if too_broad else "Request is too broad or impacts too many files/folders."
        next_safe_step = "Break the request into smaller, bounded slices."

    # 8. Generic tool/app/dashboard/service build requests must return prior_art_check_required.
    elif (
        any(kw in normalized_text for kw in ("dashboard", "app", "service", "tool", "interface", "frontend", "backend", "plugin", "hook", "mcp", "script"))
        and any(kw in normalized_text for kw in ("build", "create", "new", "scratch", "install"))
    ) or "from scratch" in normalized_text:
        gate_decision = "prior_art_check_required"
        decision_reason = "Generic build or installation request requires a prior-art check to avoid duplication."
        needs_prior_art_check = True
        next_safe_step = "Consult NO_BUILD_PRIOR_ART_SOURCES.md before proceeding."

    # 9. Explicitly bounded architecture/planning requests may return ready_for_bounded_architecture_slice
    # even if they mention other domains (e.g., "Plan a receipt integration").
    elif (
        any(kw in normalized_text for kw in ("architecture slice", "planning slice", "design slice", "bounded architecture"))
        or (
            any(kw in normalized_text for kw in ("design", "plan"))
            and any(kw in normalized_text for kw in ("domain", "router", "architecture", "map", "integration", "hardening"))
        )
    ) and not too_broad:
        gate_decision = "ready_for_bounded_architecture_slice"
        decision_reason = "Request is for a bounded architecture/planning slice."
        ready_for_bounded_slice = True
        next_safe_step = "Proceed with architectural planning within the defined boundary. Note: This gate grants no implementation or execution authority."

    # 10. Unknown requests must return unknown_manual_review (already set)

    return ArchitectureGateResult(
        request_text=request_text,
        matched_plugin_domain_id=domain_match.matched_domain_id,
        gate_decision=gate_decision,
        decision_reason=decision_reason,
        already_built_risk=already_built_risk,
        too_broad=too_broad,
        blocked=blocked,
        needs_prior_art_check=needs_prior_art_check,
        sensitive_boundary_risk=sensitive_boundary_risk,
        ready_for_bounded_slice=ready_for_bounded_slice,
        required_maps_checked=arch_domain.required_maps.split(", "),
        required_registry_domains_checked=["architecture_map_gate", "sensitive_boundary", "no_build_prior_art"],
        forbidden_actions=arch_domain.forbidden_actions.split(", "),
        next_safe_step=next_safe_step,
        execution_authority_granted=False,  # 10. Never grant execution authority
        active_plugin_claimed=False         # 10. Never claim an active plugin exists
    )

def architecture_map_gate_status() -> dict:
    """Return the status of the architecture map gate."""
    return {
        "status": "implemented_substrate",
        "passed": True,
        "read_only": True,
        "no_runtime": True,
        "no_provider": True,
        "no_mcp": True,
        "no_cleanup": True,
        "no_active_plugin": True,
        "authority_note": "This gate is an implemented substrate, inactive plugin, read-only, and grants no execution authority.",
        "registered_domain": "architecture_map_gate"
    }
