"""Comedy Archetype Seeder — Component 1 of the Three-Component Spec.

Purpose: given a ComedyGateDecision (already admitted by the existing gate in
operator_surface_guard.py), select WHICH archetype + reviewed template best
exposes the diagnostic situation, using ONLY grounded facts from the context
packet.

This module is DETERMINISTIC and has:
  - No LLM calls
  - No external I/O
  - No side effects
  - No imports from operator_surface_guard (it is an injected dependency)

Spec reference: THREE-COMPONENT-SPEC.md § "Component 1: Comedy Archetype Seeding"
Policy version: comedy_archetype_seeder_v1
"""

from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass, field
from typing import Any, Optional

# ---------------------------------------------------------------------------
# Policy version — bumping this changes HMAC domains, invalidating all prior
# deterministic fallback selections so they can be reviewed.
# ---------------------------------------------------------------------------
POLICY_VERSION = "comedy_archetype_seeder_v1"

# ---------------------------------------------------------------------------
# Archetypes (abstract mechanisms; comedian names are doc aliases only)
# ---------------------------------------------------------------------------
ARCHETYPES = frozenset(
    {"absurdist", "logical_literalism", "misplaced_confidence", "bureaucratic_overthinker"}
)

# ---------------------------------------------------------------------------
# Agent rank map (1-based, Guardian=1, Niles=6)
# Rank controls template INTENSITY only, not factual freedom.
# ---------------------------------------------------------------------------
AGENT_RANK: dict[str, int] = {
    "GUARDIAN": 1,
    "CHIEF": 2,
    "CASSANDRA": 3,
    "HERMES": 4,
    "MAESTRO": 5,
    "NILES": 6,
}

# ---------------------------------------------------------------------------
# Signal priorities (from spec)
# ---------------------------------------------------------------------------
SIGNAL_PRIORITY: dict[str, int] = {
    "APPROVAL_DEPENDENCY_CYCLE": 100,
    "LITERAL_SCOPE_MISMATCH": 95,
    "BOUNDARY_LITERALISM": 90,
    "WORDING_INTENT_MISMATCH": 88,
    "CONFIDENCE_EVIDENCE_GAP": 85,
    "PREMATURE_SUCCESS": 78,
    "RETRY_WITHOUT_PROGRESS": 80,
    "MUTUALLY_EXCLUSIVE_CONSTRAINTS": 75,
    "TYPE_CATEGORY_COLLISION": 70,
    "ORDER_OF_MAGNITUDE_ANOMALY": 65,
    "REDUNDANT_GATE_CHAIN": 60,
    # Generic/fallback signals
    "GENERIC_REDUNDANCY": 30,
    "GENERIC_EXPECTATION_GAP": 25,
    "UNUSUAL_VALID_SEQUENCE": 20,
}

# Signal → forced archetype (these map uniquely to one archetype → context_rule)
SIGNAL_FORCED_ARCHETYPE: dict[str, str] = {
    "APPROVAL_DEPENDENCY_CYCLE": "bureaucratic_overthinker",
    "REDUNDANT_GATE_CHAIN": "bureaucratic_overthinker",
    "PROCESS_EXCEEDS_TASK": "bureaucratic_overthinker",
    "LITERAL_SCOPE_MISMATCH": "logical_literalism",
    "BOUNDARY_LITERALISM": "logical_literalism",
    "WORDING_INTENT_MISMATCH": "logical_literalism",
    "CONFIDENCE_EVIDENCE_GAP": "misplaced_confidence",
    "RETRY_WITHOUT_PROGRESS": "misplaced_confidence",
    "PREMATURE_SUCCESS": "misplaced_confidence",
    "TYPE_CATEGORY_COLLISION": "absurdist",
    "MUTUALLY_EXCLUSIVE_CONSTRAINTS": "absurdist",
    "ORDER_OF_MAGNITUDE_ANOMALY": "absurdist",
}

# Seeded-fallback controlled allowed lists (from spec)
SEEDED_FALLBACK_ALLOWED: dict[str, frozenset] = {
    "GENERIC_REDUNDANCY": frozenset(
        {"logical_literalism", "misplaced_confidence", "bureaucratic_overthinker"}
    ),
    "GENERIC_EXPECTATION_GAP": frozenset(
        {"logical_literalism", "misplaced_confidence", "absurdist"}
    ),
    "UNUSUAL_VALID_SEQUENCE": frozenset({"absurdist", "bureaucratic_overthinker"}),
}


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class GroundedFact:
    """Minimal grounded fact as per the shared architectural contract."""

    fact_id: str
    subject_ref: str
    predicate: str
    value: Any
    value_type: str
    source_ref: str
    source_revision: str
    observed_at: str  # ISO-8601 string


@dataclass
class SituationSignal:
    """A deterministically extracted diagnostic signal from grounded facts."""

    code: str
    priority: int  # causal specificity; higher = more specific
    salience: int  # 0..100 deterministic rule score
    forced_archetype: Optional[str]  # if code uniquely maps to one archetype
    allowed_archetypes: frozenset  # archetypes compatible with this signal
    evidence_fact_ids: list
    template_family: str  # code of the template family to search
    slot_bindings: dict  # slot_name -> fact_id


@dataclass
class ComedyHint:
    """Comedy hint written into context_packet.render_hints.comedy."""

    enabled: bool
    archetype_hint: Optional[str]  # absurdist | logical_literalism | ...
    selection_mode: str  # none | context_rule | seeded_fallback
    diagnostic_signal: Optional[str]
    evidence_fact_ids: list
    template_id: Optional[str]
    slot_bindings: dict  # slot -> fact_id
    agent_rank: int  # 1..6
    intensity_cap: int  # 0..6 (copied from gate)
    max_sentences: int  # v1: 0 or 1
    gate_decision_ref: str
    policy_version: str
    # Rendered comedy line (None = not yet realized or disabled)
    rendered_line: Optional[str] = None


# ---------------------------------------------------------------------------
# Null hint factory
# ---------------------------------------------------------------------------

def _null_hint(
    agent_rank: int,
    intensity_cap: int,
    gate_decision_ref: str,
) -> ComedyHint:
    """Return a fully-null hint (comedy disabled)."""
    return ComedyHint(
        enabled=False,
        archetype_hint=None,
        selection_mode="none",
        diagnostic_signal=None,
        evidence_fact_ids=[],
        template_id=None,
        slot_bindings={},
        agent_rank=agent_rank,
        intensity_cap=intensity_cap,
        max_sentences=0,
        gate_decision_ref=gate_decision_ref,
        policy_version=POLICY_VERSION,
    )


# ---------------------------------------------------------------------------
# Comedy Template registry
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ComedyTemplate:
    """A reviewed, grounded comedy template.

    ``rendered_pattern`` uses {slot_name} placeholders.  Every {slot_name}
    MUST be resolved from a grounded fact_id in slot_bindings — no invented
    values.

    ``required_slots`` lists the slot names that MUST be present.
    ``minimum_rank`` / ``maximum_rank`` enforce agent intensity constraints.
    """

    template_id: str
    signal_code: str
    archetype: str
    minimum_rank: int  # 1..6
    maximum_rank: int  # 1..6
    required_slots: tuple  # tuple[str, ...]
    rendered_pattern: str  # human-readable; {slot} filled with grounded values


# ---------------------------------------------------------------------------
# Reviewed template registry (v1 — covers spec worked examples + canonical cases)
# ---------------------------------------------------------------------------

TEMPLATE_REGISTRY: list = [
    # --- Worked example 1: approval cycle → bureaucratic_overthinker ---
    ComedyTemplate(
        template_id="APPROVAL_CYCLE_BUREAUCRATIC_v1",
        signal_code="APPROVAL_DEPENDENCY_CYCLE",
        archetype="bureaucratic_overthinker",
        minimum_rank=1,
        maximum_rank=6,
        required_slots=("cycle_entity",),
        rendered_pattern=(
            "Each approval is waiting for the next approval to go first."
        ),
    ),
    # --- Worked example 2: exact-label bug → logical_literalism ---
    ComedyTemplate(
        template_id="LITERAL_SCOPE_MISMATCH_LOGIC_v1",
        signal_code="LITERAL_SCOPE_MISMATCH",
        archetype="logical_literalism",
        minimum_rank=1,
        maximum_rank=6,
        required_slots=("requested_label", "selected_label"),
        rendered_pattern=(
            'It followed "{requested_label}" so literally that '
            '"{selected_label}" did not qualify.'
        ),
    ),
    # --- Worked example 3: premature certainty → misplaced_confidence ---
    ComedyTemplate(
        template_id="CONFIDENCE_EVIDENCE_GAP_CONFIDENCE_v1",
        signal_code="CONFIDENCE_EVIDENCE_GAP",
        archetype="misplaced_confidence",
        minimum_rank=1,
        maximum_rank=6,
        required_slots=("confidence_pct", "checks_passed", "checks_required"),
        rendered_pattern=(
            "The confidence finished the job before the checklist did."
        ),
    ),
    # Additional canonical coverage:
    # PREMATURE_SUCCESS → misplaced_confidence
    ComedyTemplate(
        template_id="PREMATURE_SUCCESS_CONFIDENCE_v1",
        signal_code="PREMATURE_SUCCESS",
        archetype="misplaced_confidence",
        minimum_rank=1,
        maximum_rank=6,
        required_slots=("task_label",),
        rendered_pattern=(
            "The task declared success before verifying the work was actually done."
        ),
    ),
    # TYPE_CATEGORY_COLLISION → absurdist
    ComedyTemplate(
        template_id="TYPE_CATEGORY_COLLISION_ABSURDIST_v1",
        signal_code="TYPE_CATEGORY_COLLISION",
        archetype="absurdist",
        minimum_rank=1,
        maximum_rank=6,
        required_slots=("field_name", "received_category", "expected_category"),
        rendered_pattern=(
            "The system handled a {received_category} arriving in a "
            '{expected_category} field for "{field_name}" — gracefully, if '
            "somewhat confused."
        ),
    ),
    # BOUNDARY_LITERALISM → logical_literalism
    ComedyTemplate(
        template_id="BOUNDARY_LITERALISM_LOGIC_v1",
        signal_code="BOUNDARY_LITERALISM",
        archetype="logical_literalism",
        minimum_rank=1,
        maximum_rank=6,
        required_slots=("threshold_value", "observed_value"),
        rendered_pattern=(
            "The rule said strictly less than {threshold_value}, "
            "and {observed_value} was not less — it was equal."
        ),
    ),
]


def _templates_for(
    signal_code: str,
    archetype: str,
    agent_rank: int,
    intensity_cap: int,
) -> list:
    """Return all templates matching signal+archetype+rank constraints."""
    return [
        t
        for t in TEMPLATE_REGISTRY
        if t.signal_code == signal_code
        and t.archetype == archetype
        and t.minimum_rank <= agent_rank <= t.maximum_rank
        and t.minimum_rank <= intensity_cap
    ]


# ---------------------------------------------------------------------------
# HMAC-based deterministic selector
# ---------------------------------------------------------------------------

# Secret key guards against operator manipulation via crafted IDs.
# In production this would be loaded from a secrets store; for v1 we use a
# fixed-but-non-trivial key so tests are deterministic without requiring env.
_HMAC_SECRET_KEY = b"openclaw-comedy-archetype-seeder-v1-secret"


def _hmac_select(
    reply_id: str,
    agent_id: str,
    domain: str,
    policy_version: str,
    candidates: list,
) -> str:
    """Deterministically select one candidate using HMAC.

    Domains keep comedy-admission, comedy-archetype, and comedy-template-variant
    separate so the same (reply_id, agent_id) pair can diverge per domain.
    """
    if not candidates:
        raise ValueError("candidates must be non-empty")
    msg = f"{reply_id}|{agent_id}|{domain}|{policy_version}".encode("utf-8")
    digest = hmac.new(_HMAC_SECRET_KEY, msg, hashlib.sha256).digest()
    idx = int.from_bytes(digest[:4], "big") % len(sorted(candidates))
    return sorted(candidates)[idx]


# ---------------------------------------------------------------------------
# Signal extraction helpers
# ---------------------------------------------------------------------------


def _fact_by_id(facts: list, fact_id: str) -> Optional[GroundedFact]:
    for f in facts:
        if f.fact_id == fact_id:
            return f
    return None


def _build_signal(
    code: str,
    salience: int,
    evidence_fact_ids: list,
    slot_bindings: dict,
) -> SituationSignal:
    priority = SIGNAL_PRIORITY.get(code, 0)
    forced = SIGNAL_FORCED_ARCHETYPE.get(code)
    allowed = frozenset({forced}) if forced else SEEDED_FALLBACK_ALLOWED.get(code, frozenset())
    return SituationSignal(
        code=code,
        priority=priority,
        salience=salience,
        forced_archetype=forced,
        allowed_archetypes=allowed,
        evidence_fact_ids=evidence_fact_ids,
        template_family=code,
        slot_bindings=slot_bindings,
    )


def extract_situation_signals(
    facts: list,
) -> list:
    """Extract deterministic SituationSignals from grounded facts only.

    v1: NO LLM inference.  Each signal requires specific structured
    fact predicates with typed values.  Unknown predicates are skipped.
    """
    signals: list = []

    # Index facts by predicate for efficient lookup
    by_predicate: dict = {}
    for f in facts:
        by_predicate.setdefault(f.predicate, []).append(f)

    # ------------------------------------------------------------------
    # APPROVAL_DEPENDENCY_CYCLE
    # Trigger: fact predicate="approval_cycle_detected", value truthy
    # ------------------------------------------------------------------
    for f in by_predicate.get("approval_cycle_detected", []):
        if f.value:
            signals.append(
                _build_signal(
                    "APPROVAL_DEPENDENCY_CYCLE",
                    salience=90,
                    evidence_fact_ids=[f.fact_id],
                    slot_bindings={"cycle_entity": f.fact_id},
                )
            )

    # ------------------------------------------------------------------
    # LITERAL_SCOPE_MISMATCH
    # Trigger: fact predicate="scope_mismatch", value dict with
    # requested_label + selected_label (exact token mismatch)
    # ------------------------------------------------------------------
    for f in by_predicate.get("scope_mismatch", []):
        val = f.value
        if isinstance(val, dict) and "requested_label" in val and "selected_label" in val:
            requested = val["requested_label"]
            selected = val["selected_label"]
            if isinstance(requested, str) and isinstance(selected, str) and requested != selected:
                signals.append(
                    _build_signal(
                        "LITERAL_SCOPE_MISMATCH",
                        salience=85,
                        evidence_fact_ids=[f.fact_id],
                        slot_bindings={
                            "requested_label": f.fact_id,
                            "selected_label": f.fact_id,
                        },
                    )
                )

    # ------------------------------------------------------------------
    # CONFIDENCE_EVIDENCE_GAP
    # Trigger: fact predicate="confidence_report" with keys:
    #   reported_confidence (float 0..1), verified_checks (int), required_checks (int)
    # Rule: conf >= 0.80 AND coverage <= 0.50, OR conf-coverage >= 0.40
    # ------------------------------------------------------------------
    for f in by_predicate.get("confidence_report", []):
        val = f.value
        if not isinstance(val, dict):
            continue
        conf = val.get("reported_confidence")
        verified = val.get("verified_checks")
        required = val.get("required_checks")
        if None in (conf, verified, required) or required == 0:
            continue
        coverage = verified / required
        gap = conf - coverage
        high_conf = conf >= 0.80
        low_coverage = coverage <= 0.50
        if (high_conf and low_coverage) or gap >= 0.40:
            signals.append(
                _build_signal(
                    "CONFIDENCE_EVIDENCE_GAP",
                    salience=int(min(100, int(gap * 100))),
                    evidence_fact_ids=[f.fact_id],
                    slot_bindings={
                        "confidence_pct": f.fact_id,
                        "checks_passed": f.fact_id,
                        "checks_required": f.fact_id,
                    },
                )
            )

    # ------------------------------------------------------------------
    # PREMATURE_SUCCESS
    # Trigger: fact predicate="task_completion_report" with
    #   declared_complete=True AND grounded_verifications_failed > 0
    # ------------------------------------------------------------------
    for f in by_predicate.get("task_completion_report", []):
        val = f.value
        if isinstance(val, dict):
            declared = val.get("declared_complete", False)
            failed_verif = val.get("grounded_verifications_failed", 0)
            if declared and failed_verif > 0:
                signals.append(
                    _build_signal(
                        "PREMATURE_SUCCESS",
                        salience=80,
                        evidence_fact_ids=[f.fact_id],
                        slot_bindings={"task_label": f.fact_id},
                    )
                )

    # ------------------------------------------------------------------
    # TYPE_CATEGORY_COLLISION
    # Trigger: fact predicate="type_category_collision" with
    #   field_name, received_category, expected_category (all strings)
    #   AND safely_handled=True (no unresolved error)
    # ------------------------------------------------------------------
    for f in by_predicate.get("type_category_collision", []):
        val = f.value
        if not isinstance(val, dict):
            continue
        if not val.get("safely_handled", False):
            continue
        if all(k in val for k in ("field_name", "received_category", "expected_category")):
            signals.append(
                _build_signal(
                    "TYPE_CATEGORY_COLLISION",
                    salience=70,
                    evidence_fact_ids=[f.fact_id],
                    slot_bindings={
                        "field_name": f.fact_id,
                        "received_category": f.fact_id,
                        "expected_category": f.fact_id,
                    },
                )
            )

    # ------------------------------------------------------------------
    # BOUNDARY_LITERALISM
    # Trigger: fact predicate="boundary_check" with
    #   operator="strictly_less_than", threshold (number), observed (number)
    #   AND observed == threshold (equality excluded by rule)
    # ------------------------------------------------------------------
    for f in by_predicate.get("boundary_check", []):
        val = f.value
        if not isinstance(val, dict):
            continue
        if val.get("operator") != "strictly_less_than":
            continue
        threshold = val.get("threshold")
        observed = val.get("observed")
        if threshold is None or observed is None:
            continue
        if observed == threshold:
            signals.append(
                _build_signal(
                    "BOUNDARY_LITERALISM",
                    salience=82,
                    evidence_fact_ids=[f.fact_id],
                    slot_bindings={
                        "threshold_value": f.fact_id,
                        "observed_value": f.fact_id,
                    },
                )
            )

    # ------------------------------------------------------------------
    # RETRY_WITHOUT_PROGRESS
    # Trigger: fact predicate="retry_report" with
    #   attempt_count >= 3, same_state_revision=True, new_verified_result=False,
    #   hang_detected=False
    # ------------------------------------------------------------------
    for f in by_predicate.get("retry_report", []):
        val = f.value
        if not isinstance(val, dict):
            continue
        attempts = val.get("attempt_count", 0)
        same_state = val.get("same_state_revision", False)
        new_result = val.get("new_verified_result", True)
        hung = val.get("hang_detected", True)
        if attempts >= 3 and same_state and not new_result and not hung:
            signals.append(
                _build_signal(
                    "RETRY_WITHOUT_PROGRESS",
                    salience=75,
                    evidence_fact_ids=[f.fact_id],
                    slot_bindings={"retry_entity": f.fact_id},
                )
            )

    # ------------------------------------------------------------------
    # MUTUALLY_EXCLUSIVE_CONSTRAINTS
    # Trigger: fact predicate="constraint_solver_result" with
    #   satisfiable=False AND unsat_core_operator_count >= 2
    # ------------------------------------------------------------------
    for f in by_predicate.get("constraint_solver_result", []):
        val = f.value
        if not isinstance(val, dict):
            continue
        if val.get("satisfiable", True) is not False:
            continue
        if val.get("unsat_core_operator_count", 0) >= 2:
            signals.append(
                _build_signal(
                    "MUTUALLY_EXCLUSIVE_CONSTRAINTS",
                    salience=72,
                    evidence_fact_ids=[f.fact_id],
                    slot_bindings={"constraint_entity": f.fact_id},
                )
            )

    # ------------------------------------------------------------------
    # REDUNDANT_GATE_CHAIN
    # Trigger: fact predicate="gate_chain_report" with
    #   sequential_gates_same_condition >= 3
    # ------------------------------------------------------------------
    for f in by_predicate.get("gate_chain_report", []):
        val = f.value
        if not isinstance(val, dict):
            continue
        if val.get("sequential_gates_same_condition", 0) >= 3:
            signals.append(
                _build_signal(
                    "REDUNDANT_GATE_CHAIN",
                    salience=60,
                    evidence_fact_ids=[f.fact_id],
                    slot_bindings={"gate_entity": f.fact_id},
                )
            )

    # ------------------------------------------------------------------
    # ORDER_OF_MAGNITUDE_ANOMALY
    # Trigger: fact predicate="magnitude_report" with
    #   ratio (actual/reference) >= 10 or <= 0.1 and compatible_units=True
    # ------------------------------------------------------------------
    for f in by_predicate.get("magnitude_report", []):
        val = f.value
        if not isinstance(val, dict):
            continue
        if not val.get("compatible_units", False):
            continue
        ratio = val.get("ratio")
        if ratio is not None and (ratio >= 10 or ratio <= 0.1):
            signals.append(
                _build_signal(
                    "ORDER_OF_MAGNITUDE_ANOMALY",
                    salience=65,
                    evidence_fact_ids=[f.fact_id],
                    slot_bindings={"magnitude_entity": f.fact_id},
                )
            )

    # ------------------------------------------------------------------
    # WORDING_INTENT_MISMATCH
    # Trigger: fact predicate="alias_resolution_failure" with
    #   alias_map_exists=True, raw_wording (str), known_alias (str)
    # ------------------------------------------------------------------
    for f in by_predicate.get("alias_resolution_failure", []):
        val = f.value
        if not isinstance(val, dict):
            continue
        if not val.get("alias_map_exists", False):
            continue
        if "raw_wording" in val and "known_alias" in val:
            signals.append(
                _build_signal(
                    "WORDING_INTENT_MISMATCH",
                    salience=80,
                    evidence_fact_ids=[f.fact_id],
                    slot_bindings={
                        "raw_wording": f.fact_id,
                        "known_alias": f.fact_id,
                    },
                )
            )

    return signals


# ---------------------------------------------------------------------------
# Primary signal selection
# ---------------------------------------------------------------------------


def _select_primary_signal(
    signals: list,
    reply_id: str,
    agent_id: str,
) -> Optional[SituationSignal]:
    """Select the primary signal per spec rules.

    1. Highest priority wins.
    2. Tie-break: higher salience.
    3. Same archetype ties: merge evidence (handled externally).
    4. Different-but-compatible archetypes → seeded fallback (returns first).
    5. Materially different diagnoses → ABSTAIN (return None).
    """
    if not signals:
        return None

    # Sort: priority DESC, salience DESC, code ASC (stable tie-break)
    ranked = sorted(signals, key=lambda s: (-s.priority, -s.salience, s.code))
    best = ranked[0]

    # Check for tied priority
    tied = [s for s in ranked if s.priority == best.priority]
    if len(tied) == 1:
        return best

    # Tie-break: highest salience among tied
    max_salience = max(s.salience for s in tied)
    salience_winners = [s for s in tied if s.salience == max_salience]
    if len(salience_winners) == 1:
        return salience_winners[0]

    # Same salience + same priority: check archetype divergence
    archetypes_in_tie = {s.forced_archetype for s in salience_winners}
    if len(archetypes_in_tie) == 1:
        # Same archetype — return first (merge evidence is caller's concern)
        return salience_winners[0]

    # Materially different diagnoses → ABSTAIN
    return None


# ---------------------------------------------------------------------------
# Slot value resolution (for template rendering)
# ---------------------------------------------------------------------------


def resolve_slot_value(
    slot_name: str,
    fact_id: str,
    facts: list,
) -> Optional[str]:
    """Extract the human-readable value for a template slot from a grounded fact.

    Returns None if the fact is not found (which triggers validation failure).
    """
    fact = _fact_by_id(facts, fact_id)
    if fact is None:
        return None
    val = fact.value
    # For dict-valued facts, try to extract the slot name as a key
    if isinstance(val, dict) and slot_name in val:
        return str(val[slot_name])
    # For simple scalar facts, return the value directly
    return str(val)


# ---------------------------------------------------------------------------
# Template rendering
# ---------------------------------------------------------------------------


def render_template(
    template: ComedyTemplate,
    slot_bindings: dict,  # slot_name -> fact_id
    facts: list,
) -> Optional[str]:
    """Render a template by substituting grounded slot values.

    Returns None if any required slot cannot be resolved (caller removes
    the comedy line — no reroll per spec).
    """
    resolved: dict = {}
    for slot in template.required_slots:
        fact_id = slot_bindings.get(slot)
        if fact_id is None:
            return None
        value = resolve_slot_value(slot, fact_id, facts)
        if value is None:
            return None
        resolved[slot] = value

    try:
        return template.rendered_pattern.format(**resolved)
    except (KeyError, ValueError):
        return None


# ---------------------------------------------------------------------------
# Fact-id validation
# ---------------------------------------------------------------------------


def _validate_refs(hint: ComedyHint, facts: list) -> bool:
    """Ensure every evidence + slot fact_id exists in the packet."""
    fact_ids = {f.fact_id for f in facts}
    for fid in hint.evidence_fact_ids:
        if fid not in fact_ids:
            return False
    for fid in hint.slot_bindings.values():
        if fid not in fact_ids:
            return False
    return True


# ---------------------------------------------------------------------------
# Main seeder entry point
# ---------------------------------------------------------------------------


def seed_comedy_archetype(
    *,
    context_packet_facts: list,
    gate_decision: dict,  # ComedyGateDecision-shaped dict
    reply_id: str,
    agent_id: str,
) -> ComedyHint:
    """Run the 13-step seeder procedure from the spec.

    ``gate_decision`` must have keys:
      admitted, zero_error_pass, agent_rank, intensity_cap,
      golden_ratio_roll_passed, gate_decision_ref

    Returns a ComedyHint.  On any failure, returns the null hint.
    Comedy metadata never enters grounded facts (TRUTH FIRST invariant).
    """
    # Extract gate fields — consumed EXACTLY, never re-admitted
    admitted: bool = gate_decision.get("admitted", False)
    zero_error_pass: bool = gate_decision.get("zero_error_pass", False)
    agent_rank: int = gate_decision.get("agent_rank", 1)
    intensity_cap: int = gate_decision.get("intensity_cap", 0)
    golden_ratio_roll_passed: bool = gate_decision.get("golden_ratio_roll_passed", False)
    gate_decision_ref: str = gate_decision.get("gate_decision_ref", "")

    null = _null_hint(agent_rank, intensity_cap, gate_decision_ref)

    # Step 1 — disabled if zero_error_pass False
    if not zero_error_pass:
        return null

    # Step 2 — disabled if admitted False OR golden_ratio_roll_passed False
    if not admitted or not golden_ratio_roll_passed:
        return null

    # Step 3 — extract deterministic signals from grounded facts only
    signals = extract_situation_signals(context_packet_facts)

    # Step 4 — select primary signal (priority, salience, stable tie-break)
    primary = _select_primary_signal(signals, reply_id, agent_id)

    # Step 5 — disabled if no primary signal
    if primary is None:
        return null

    # Step 6 — forced archetype → context_rule
    if primary.forced_archetype:
        selection_mode = "context_rule"
        archetype = primary.forced_archetype

        # Step 10 — select reviewed template
        templates = _templates_for(
            primary.code, archetype, agent_rank, intensity_cap
        )

        # Step 11 — disabled if no template
        if not templates:
            return null

        # Deterministic template selection within family
        template_id = _hmac_select(
            reply_id, agent_id,
            domain="comedy-template-variant",
            policy_version=POLICY_VERSION,
            candidates=[t.template_id for t in templates],
        )
        chosen_template = next(t for t in templates if t.template_id == template_id)

    else:
        # Step 7 — seeded fallback: filter allowed archetypes to those with reviewed templates
        allowed = primary.allowed_archetypes
        archetypes_with_templates = [
            a for a in sorted(allowed)
            if _templates_for(primary.code, a, agent_rank, intensity_cap)
        ]

        # Step 8 — disabled if none remain
        if not archetypes_with_templates:
            return null

        # Step 9 — deterministically pick one archetype
        archetype = _hmac_select(
            reply_id, agent_id,
            domain="comedy-archetype",
            policy_version=POLICY_VERSION,
            candidates=archetypes_with_templates,
        )
        selection_mode = "seeded_fallback"

        # Step 10 — select template
        templates = _templates_for(primary.code, archetype, agent_rank, intensity_cap)
        if not templates:
            return null  # Step 11

        template_id = _hmac_select(
            reply_id, agent_id,
            domain="comedy-template-variant",
            policy_version=POLICY_VERSION,
            candidates=[t.template_id for t in templates],
        )
        chosen_template = next(t for t in templates if t.template_id == template_id)

    # Step 12 — build ComedyHint with grounded evidence + slots
    hint = ComedyHint(
        enabled=True,
        archetype_hint=archetype,
        selection_mode=selection_mode,
        diagnostic_signal=primary.code,
        evidence_fact_ids=list(primary.evidence_fact_ids),
        template_id=chosen_template.template_id,
        slot_bindings=dict(primary.slot_bindings),
        agent_rank=agent_rank,
        intensity_cap=intensity_cap,
        max_sentences=1,
        gate_decision_ref=gate_decision_ref,
        policy_version=POLICY_VERSION,
    )

    # Step 13 — validate every ref
    if not _validate_refs(hint, context_packet_facts):
        return null

    return hint


# ---------------------------------------------------------------------------
# Comedy line realization (template → rendered text)
# Called by ComedyRealizer; seeder exposes a helper for the pipeline.
# ---------------------------------------------------------------------------


def realize_comedy_line(
    hint: ComedyHint,
    facts: list,
    *,
    literal_explanation: str,
) -> Optional[str]:
    """Render the comedy line from a ComedyHint.

    Returns None if rendering fails (caller REMOVES the line — no reroll).
    The literal explanation is provided by the PersonaRenderer and must
    precede the comedy line in the final output.

    This helper returns ONLY the comedy sentence; the caller concatenates.
    Invariant: literal_explanation must be non-empty (literal precedes joke).
    """
    if not hint.enabled or not hint.template_id:
        return None

    # Find the template
    template = next(
        (t for t in TEMPLATE_REGISTRY if t.template_id == hint.template_id),
        None,
    )
    if template is None:
        return None

    # Validate literal explanation is present (required by spec)
    if not literal_explanation or not literal_explanation.strip():
        return None

    return render_template(template, hint.slot_bindings, facts)
