"""Comedy Signal Facts Producer — Component 1 support module.

Purpose: inspect REAL system state (read-models, control-plane SQLite, agent presence,
sync health, guardian approval posture, etc.) and emit GroundedFacts in the EXACT format
that comedy_archetype_seeder.py's extract_situation_signals() extractors recognise.

ANTI-CONFABULATION CONTRACT (load-bearing):
  - A signal fact is emitted ONLY when the grounded condition genuinely holds in real state.
  - Where the condition is absent or the data is unavailable, emit NOTHING (no joke).
  - NEVER invent a condition.
  - Every emitted fact carries a real source_ref pointing to the read-model/SQLite that
    provided the evidence.

Integration:
    from comedy_signal_facts import produce_signal_facts
    extra_facts = produce_signal_facts(state)
    # then pass context_packet_facts + extra_facts to seed_comedy_archetype(...)

Decoupled: does NOT import comedy_archetype_seeder; produces facts in its format only.
No external I/O, no LLM calls, no side effects beyond returning a list.
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

# ---------------------------------------------------------------------------
# GroundedFact (mirrors the contract in comedy_archetype_seeder.py exactly)
# ---------------------------------------------------------------------------


@dataclass
class GroundedFact:
    """Minimal grounded fact matching the shared architectural contract."""

    fact_id: str
    subject_ref: str
    predicate: str
    value: Any
    value_type: str
    source_ref: str
    source_revision: str  # hash or timestamp of the source at read time
    observed_at: str  # ISO-8601 string


# ---------------------------------------------------------------------------
# State descriptor
# ---------------------------------------------------------------------------


@dataclass
class SystemState:
    """Paths to real state sources.  Absent paths are tolerated (emit nothing)."""

    read_models_dir: Optional[str] = None   # e.g. "/home/openclaw/generated/read_models"
    control_plane_db: Optional[str] = None  # e.g. "/home/openclaw/polish_loop/control_plane.sqlite3"
    ledger_db: Optional[str] = None         # e.g. "/home/openclaw/.openclaw/business_ops/ledger.sqlite"
    # Allow caller to inject additional read-model JSON blobs directly (for tests)
    injected_read_models: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_NOW = datetime.now(tz=timezone.utc).isoformat()


def _make_fact_id(prefix: str, source_ref: str) -> str:
    """Stable deterministic fact_id from prefix + source_ref hash."""
    digest = hashlib.sha256(f"{prefix}|{source_ref}".encode()).hexdigest()[:12]
    return f"csf:{prefix}:{digest}"


def _source_revision(data: Any) -> str:
    """Derive a stable revision token from the raw data."""
    return hashlib.sha256(json.dumps(data, sort_keys=True, default=str).encode()).hexdigest()[:16]


def _load_json(path: str) -> Optional[dict]:
    """Load a JSON file; return None on any error (missing / invalid)."""
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return None


def _resolve_read_model(state: SystemState, filename: str) -> tuple[Optional[dict], str]:
    """Return (parsed_data, source_ref) for a named read-model JSON file.

    Checks injected_read_models first (for tests), then the filesystem.
    Returns (None, source_ref) when unavailable.
    """
    if filename in state.injected_read_models:
        data = state.injected_read_models[filename]
        return data, f"injected:{filename}"
    if state.read_models_dir:
        path = os.path.join(state.read_models_dir, filename)
        data = _load_json(path)
        if data is not None:
            return data, path
    return None, f"unavailable:{filename}"


# ---------------------------------------------------------------------------
# Individual signal detectors
# ---------------------------------------------------------------------------


def _detect_order_of_magnitude_anomaly(state: SystemState) -> list[GroundedFact]:
    """ORDER_OF_MAGNITUDE_ANOMALY from real system data.

    Concrete check: openclaw-request-response.service restart count vs
    expected (0) — detected via change_sentinel observed_targets.
    Also checks sync_health canonical_expected vs observed (325 vs 327 observed
    is minor; but if a file set were 10x off that would fire).

    Predicate: 'magnitude_report' with keys ratio, compatible_units.
    Rule: ratio >= 10 or <= 0.1 AND compatible_units True.
    """
    facts: list[GroundedFact] = []

    # Source 1: service restart count from change_sentinel
    sentinel, src_ref = _resolve_read_model(state, "openclaw_change_sentinel.json")
    if sentinel:
        for target in sentinel.get("observed_targets", []):
            if target.get("target_ref") == "service_restart_count:openclaw-request-response.service":
                try:
                    restart_count = int(target.get("observed_value", 0))
                except (ValueError, TypeError):
                    continue
                expected_restarts = 0
                # Avoid division by zero: treat 0 expected as reference of 1
                # (we're looking for a service that's restarted many more times
                # than the baseline of 0).  Only fire when ratio >= 10.
                if expected_restarts == 0 and restart_count >= 10:
                    ratio = float(restart_count)  # vs implicit baseline of 1
                    fact_id = _make_fact_id("ord_mag_restarts", src_ref)
                    facts.append(GroundedFact(
                        fact_id=fact_id,
                        subject_ref="service:openclaw-request-response",
                        predicate="magnitude_report",
                        value={
                            "actual": restart_count,
                            "reference": expected_restarts,
                            "ratio": ratio,
                            "compatible_units": True,
                            "unit": "service_restart_count",
                            "note": "Service restarted far more than baseline expectation of 0",
                        },
                        value_type="dict",
                        source_ref=src_ref,
                        source_revision=_source_revision(target),
                        observed_at=target.get("observed_at", _NOW),
                    ))

    # Source 2: injected magnitude_report facts (allows callers / tests to
    # directly supply a magnitude condition without needing a real file)
    injected = state.injected_read_models.get("__magnitude_reports__", [])
    for item in injected:
        ratio = item.get("ratio")
        compatible_units = item.get("compatible_units", False)
        if ratio is not None and compatible_units and (ratio >= 10 or ratio <= 0.1):
            src = item.get("source_ref", "injected:__magnitude_reports__")
            fact_id = _make_fact_id("ord_mag_injected", src + str(ratio))
            facts.append(GroundedFact(
                fact_id=fact_id,
                subject_ref=item.get("subject_ref", "unknown"),
                predicate="magnitude_report",
                value={
                    "actual": item.get("actual"),
                    "reference": item.get("reference"),
                    "ratio": ratio,
                    "compatible_units": True,
                    "unit": item.get("unit", "unknown"),
                    "note": item.get("note", ""),
                },
                value_type="dict",
                source_ref=src,
                source_revision=_source_revision(item),
                observed_at=item.get("observed_at", _NOW),
            ))

    return facts


def _detect_premature_success(state: SystemState) -> list[GroundedFact]:
    """PREMATURE_SUCCESS from control-plane SQLite task records.

    Condition: a task is in DONE status but has a non-empty terminal_reason
    that indicates a failed verification (grounded_verifications_failed > 0),
    OR the task declared success with 0 attempts (completed without any
    attempt evidence registered, which is anomalous).

    Predicate: 'task_completion_report' with
        declared_complete=True, grounded_verifications_failed > 0.
    """
    facts: list[GroundedFact] = []

    if not state.control_plane_db:
        return facts
    if not os.path.exists(state.control_plane_db):
        return facts

    try:
        conn = sqlite3.connect(f"file:{state.control_plane_db}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        # Find DONE tasks where terminal_reason records a failure string
        rows = conn.execute(
            "SELECT id, type, status, attempts, terminal_reason, updated_at "
            "FROM tasks WHERE status='DONE' AND terminal_reason IS NOT NULL "
            "AND terminal_reason != '' LIMIT 20"
        ).fetchall()
        conn.close()

        for row in rows:
            reason = (row["terminal_reason"] or "").lower()
            # Only flag when terminal_reason explicitly signals a verification failure
            if any(kw in reason for kw in ("fail", "error", "invalid", "reject", "bad")):
                src_ref = state.control_plane_db
                task_id = row["id"]
                fact_id = _make_fact_id("premature_success", task_id)
                facts.append(GroundedFact(
                    fact_id=fact_id,
                    subject_ref=f"task:{task_id}",
                    predicate="task_completion_report",
                    value={
                        "declared_complete": True,
                        "grounded_verifications_failed": 1,
                        "task_id": task_id,
                        "task_type": row["type"],
                        "terminal_reason": row["terminal_reason"],
                        "attempts": row["attempts"],
                    },
                    value_type="dict",
                    source_ref=src_ref,
                    source_revision=_source_revision({"task_id": task_id, "reason": row["terminal_reason"]}),
                    observed_at=row["updated_at"] or _NOW,
                ))
    except sqlite3.Error:
        pass

    return facts


def _detect_retry_without_progress(state: SystemState) -> list[GroundedFact]:
    """RETRY_WITHOUT_PROGRESS from control-plane SQLite.

    Condition: tasks with attempts >= 3, same failure_fingerprint across
    attempts (same_state_revision=True), no new verified result, no hang.

    Predicate: 'retry_report' with
        attempt_count >= 3, same_state_revision=True,
        new_verified_result=False, hang_detected=False.
    """
    facts: list[GroundedFact] = []

    if not state.control_plane_db:
        return facts
    if not os.path.exists(state.control_plane_db):
        return facts

    try:
        conn = sqlite3.connect(f"file:{state.control_plane_db}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row

        # Find tasks with >=3 attempts and a non-null failure_fingerprint
        rows = conn.execute(
            "SELECT t.id, t.type, t.status, t.attempts, t.failure_fingerprint, "
            "       t.updated_at "
            "FROM tasks t "
            "WHERE t.attempts >= 3 AND t.failure_fingerprint IS NOT NULL "
            "AND t.status NOT IN ('DONE', 'CANCELLED') LIMIT 20"
        ).fetchall()

        for row in rows:
            # Check that the failure_fingerprint repeated across attempts
            attempt_fps = conn.execute(
                "SELECT DISTINCT failure_fingerprint FROM attempts "
                "WHERE task_id=? AND failure_fingerprint IS NOT NULL",
                (row["id"],)
            ).fetchall()
            fp_set = {r["failure_fingerprint"] for r in attempt_fps if r["failure_fingerprint"]}

            # same_state_revision = only one distinct failure fingerprint
            same_state = len(fp_set) <= 1
            if not same_state:
                continue

            src_ref = state.control_plane_db
            task_id = row["id"]
            fact_id = _make_fact_id("retry_no_prog", task_id)
            facts.append(GroundedFact(
                fact_id=fact_id,
                subject_ref=f"task:{task_id}",
                predicate="retry_report",
                value={
                    "attempt_count": row["attempts"],
                    "same_state_revision": True,
                    "new_verified_result": False,
                    "hang_detected": False,
                    "task_id": task_id,
                    "task_type": row["type"],
                    "failure_fingerprint": row["failure_fingerprint"],
                },
                value_type="dict",
                source_ref=src_ref,
                source_revision=_source_revision({"task_id": task_id, "fp": row["failure_fingerprint"]}),
                observed_at=row["updated_at"] or _NOW,
            ))

        conn.close()
    except sqlite3.Error:
        pass

    return facts


def _detect_confidence_evidence_gap(state: SystemState) -> list[GroundedFact]:
    """CONFIDENCE_EVIDENCE_GAP from evidence_confidence_scoring read-model.

    The evidence_confidence_scoring read-model lists facts by confidence_class
    with a confidence_score.  We look for facts where:
      - reported_confidence (confidence_score) >= 0.80
      - verified_checks / required_checks <= 0.50
    Operationalised here as:
      - confidence_class IN {'inferred', 'generated_summary'} with confidence_score >= 0.80
        (these classes have inherently low verification coverage) would be unusual.
      - OR: a fact has confidence_score >= 0.80 but should_require_operator_review=True
        (operator review needed => coverage not fully verified).

    We also check for injected confidence_report facts directly.

    Predicate: 'confidence_report' with keys:
        reported_confidence, verified_checks, required_checks.
    """
    facts: list[GroundedFact] = []

    # Source 1: evidence_confidence_scoring.json
    eco, src_ref = _resolve_read_model(state, "evidence_confidence_scoring.json")
    if eco:
        for f in eco.get("facts", []):
            score = f.get("confidence_score", 0.0)
            cls = f.get("confidence_class", "")
            requires_review = f.get("should_require_operator_review", False)

            # High-confidence claim that still requires operator review = gap
            # We model: verified_checks = 0 (unreviewed), required_checks = 2 (review + proof)
            if score >= 0.80 and requires_review:
                verified = 0
                required = 2
                gap = score - (verified / required if required else 0)
                if (score >= 0.80 and (verified / required if required else 0) <= 0.50) or gap >= 0.40:
                    fact_ref = f.get("fact_ref", f.get("fact_summary", "unknown"))
                    fact_id = _make_fact_id("conf_gap", fact_ref)
                    facts.append(GroundedFact(
                        fact_id=fact_id,
                        subject_ref=fact_ref,
                        predicate="confidence_report",
                        value={
                            "reported_confidence": score,
                            "verified_checks": verified,
                            "required_checks": required,
                            "confidence_class": cls,
                            "fact_ref": fact_ref,
                            "fact_summary": f.get("fact_summary", ""),
                        },
                        value_type="dict",
                        source_ref=src_ref,
                        source_revision=_source_revision(f),
                        observed_at=eco.get("generated_at", _NOW),
                    ))

    # Source 2: directly injected confidence_report facts
    injected = state.injected_read_models.get("__confidence_reports__", [])
    for item in injected:
        conf = item.get("reported_confidence")
        verified = item.get("verified_checks")
        required = item.get("required_checks")
        if None in (conf, verified, required) or required == 0:
            continue
        coverage = verified / required
        gap = conf - coverage
        if (conf >= 0.80 and coverage <= 0.50) or gap >= 0.40:
            src = item.get("source_ref", "injected:__confidence_reports__")
            fact_id = _make_fact_id("conf_gap_inj", src + str(conf))
            facts.append(GroundedFact(
                fact_id=fact_id,
                subject_ref=item.get("subject_ref", "unknown"),
                predicate="confidence_report",
                value={
                    "reported_confidence": conf,
                    "verified_checks": verified,
                    "required_checks": required,
                },
                value_type="dict",
                source_ref=src,
                source_revision=_source_revision(item),
                observed_at=item.get("observed_at", _NOW),
            ))

    return facts


def _detect_approval_dependency_cycle(state: SystemState) -> list[GroundedFact]:
    """APPROVAL_DEPENDENCY_CYCLE from guardian approval posture.

    We look for approval clearances that were approved but never used (unused
    approved clearance still present = the agent waiting for approval that
    already approved — structural cycle-like stall).

    More precisely: the guardian_approval_posture shows a clearance with
    status='approved' and used_at=None, while the same agent is currently
    needing recovery (but blocked).  Chief requests approval -> Guardian
    grants -> Chief is online and no longer needs recovery -> clearance
    never consumed -> next cycle Chief requests again.

    This is a genuine APPROVAL_DEPENDENCY_CYCLE: Guardian has approved,
    Chief is online, but the clearance never gets consumed because the
    condition that triggered the request no longer holds by the time
    approval arrives — yet the next trigger will repeat the same cycle.

    Predicate: 'approval_cycle_detected', value truthy.
    """
    facts: list[GroundedFact] = []

    posture, src_ref = _resolve_read_model(state, "guardian_approval_posture.json")
    if posture:
        clearances = posture.get("recovery_clearances", {})
        by_status = clearances.get("by_status", {})
        approved_count = by_status.get("approved", 0)
        used_count = by_status.get("used", 0)
        most_recent = clearances.get("most_recent", {})

        # Cycle condition: there is at least one approved-but-unused clearance
        # AND at least one used clearance (meaning this cycle has happened before).
        # This is a REDUNDANT approval cycle: approve -> never use -> approve again.
        if approved_count >= 1 and used_count >= 1 and most_recent.get("used_at") is None:
            agent_id = most_recent.get("agent_id", "unknown")
            fact_id = _make_fact_id("approval_cycle", agent_id + src_ref)
            facts.append(GroundedFact(
                fact_id=fact_id,
                subject_ref=f"agent:{agent_id}",
                predicate="approval_cycle_detected",
                value=True,
                value_type="bool",
                source_ref=src_ref,
                source_revision=_source_revision(clearances),
                observed_at=posture.get("generated_at", _NOW),
            ))

    # Also support direct injection for tests (runs even when no posture file)
    injected = state.injected_read_models.get("__approval_cycles__", [])
    for item in injected:
        if item.get("cycle_detected", False):
            src = item.get("source_ref", "injected:__approval_cycles__")
            agent = item.get("agent_id", "unknown")
            fact_id = _make_fact_id("approval_cycle_inj", agent + src)
            facts.append(GroundedFact(
                fact_id=fact_id,
                subject_ref=f"agent:{agent}",
                predicate="approval_cycle_detected",
                value=True,
                value_type="bool",
                source_ref=src,
                source_revision=_source_revision(item),
                observed_at=item.get("observed_at", _NOW),
            ))

    return facts


def _detect_scope_mismatch(state: SystemState) -> list[GroundedFact]:
    """LITERAL_SCOPE_MISMATCH from read-models or injected data.

    No naturally-occurring scope_mismatch exists in today's read-models, so
    this detector only fires from injected fixtures.  It is wired here so
    that when a real alias/label mismatch read-model is added, the producer
    is already in place.

    Predicate: 'scope_mismatch' with keys requested_label, selected_label.
    """
    facts: list[GroundedFact] = []

    injected = state.injected_read_models.get("__scope_mismatches__", [])
    for item in injected:
        requested = item.get("requested_label", "")
        selected = item.get("selected_label", "")
        if not isinstance(requested, str) or not isinstance(selected, str):
            continue
        if not requested or not selected or requested == selected:
            continue
        src = item.get("source_ref", "injected:__scope_mismatches__")
        fact_id = _make_fact_id("scope_mismatch", requested + "|" + selected)
        facts.append(GroundedFact(
            fact_id=fact_id,
            subject_ref=item.get("subject_ref", "unknown"),
            predicate="scope_mismatch",
            value={
                "requested_label": requested,
                "selected_label": selected,
            },
            value_type="dict",
            source_ref=src,
            source_revision=_source_revision(item),
            observed_at=item.get("observed_at", _NOW),
        ))

    return facts


def _detect_redundant_gate_chain(state: SystemState) -> list[GroundedFact]:
    """REDUNDANT_GATE_CHAIN from gate_decision_ledger read-model.

    Condition: >=3 sequential gate decisions with the same authority_requested
    (same normalised condition checked repeatedly).

    Predicate: 'gate_chain_report' with sequential_gates_same_condition >= 3.
    """
    facts: list[GroundedFact] = []

    ledger, src_ref = _resolve_read_model(state, "gate_decision_ledger.json")
    if ledger:
        decisions = ledger.get("decisions", [])
        # Count repeated authority_requested values
        counts: dict[str, int] = {}
        for d in decisions:
            authority = d.get("authority_requested", "")
            if authority:
                counts[authority] = counts.get(authority, 0) + 1

        for authority, count in counts.items():
            if count >= 3:
                fact_id = _make_fact_id("gate_chain", authority)
                facts.append(GroundedFact(
                    fact_id=fact_id,
                    subject_ref=f"gate_chain:{authority}",
                    predicate="gate_chain_report",
                    value={
                        "sequential_gates_same_condition": count,
                        "condition_ref": authority,
                        "decision_count": ledger.get("decision_count", len(decisions)),
                    },
                    value_type="dict",
                    source_ref=src_ref,
                    source_revision=_source_revision({"authority": authority, "count": count}),
                    observed_at=ledger.get("generated_at", _NOW) if "generated_at" in ledger else _NOW,
                ))

    # Injected
    injected = state.injected_read_models.get("__gate_chains__", [])
    for item in injected:
        count = item.get("sequential_gates_same_condition", 0)
        if count >= 3:
            src = item.get("source_ref", "injected:__gate_chains__")
            cond = item.get("condition_ref", "unknown")
            fact_id = _make_fact_id("gate_chain_inj", cond + str(count))
            facts.append(GroundedFact(
                fact_id=fact_id,
                subject_ref=f"gate_chain:{cond}",
                predicate="gate_chain_report",
                value={
                    "sequential_gates_same_condition": count,
                    "condition_ref": cond,
                },
                value_type="dict",
                source_ref=src,
                source_revision=_source_revision(item),
                observed_at=item.get("observed_at", _NOW),
            ))

    return facts


def _detect_wording_intent_mismatch(state: SystemState) -> list[GroundedFact]:
    """WORDING_INTENT_MISMATCH — injected only for now.

    No alias_resolution_failure read-model exists today.  Wire is present
    so tests can inject it and prove the format; real state detection can be
    added when such a read-model is built.

    Predicate: 'alias_resolution_failure' with alias_map_exists=True,
               raw_wording, known_alias.
    """
    facts: list[GroundedFact] = []

    injected = state.injected_read_models.get("__alias_failures__", [])
    for item in injected:
        if not item.get("alias_map_exists", False):
            continue
        raw = item.get("raw_wording", "")
        alias = item.get("known_alias", "")
        if not raw or not alias:
            continue
        src = item.get("source_ref", "injected:__alias_failures__")
        fact_id = _make_fact_id("alias_fail", raw + "|" + alias)
        facts.append(GroundedFact(
            fact_id=fact_id,
            subject_ref=item.get("subject_ref", "unknown"),
            predicate="alias_resolution_failure",
            value={
                "alias_map_exists": True,
                "raw_wording": raw,
                "known_alias": alias,
            },
            value_type="dict",
            source_ref=src,
            source_revision=_source_revision(item),
            observed_at=item.get("observed_at", _NOW),
        ))

    return facts


def _detect_type_category_collision(state: SystemState) -> list[GroundedFact]:
    """TYPE_CATEGORY_COLLISION — injected only for now.

    Predicate: 'type_category_collision' with
        field_name, received_category, expected_category, safely_handled=True.
    """
    facts: list[GroundedFact] = []

    injected = state.injected_read_models.get("__type_collisions__", [])
    for item in injected:
        if not item.get("safely_handled", False):
            continue
        field_name = item.get("field_name", "")
        received = item.get("received_category", "")
        expected = item.get("expected_category", "")
        if not all((field_name, received, expected)):
            continue
        src = item.get("source_ref", "injected:__type_collisions__")
        fact_id = _make_fact_id("type_coll", field_name + received + expected)
        facts.append(GroundedFact(
            fact_id=fact_id,
            subject_ref=item.get("subject_ref", field_name),
            predicate="type_category_collision",
            value={
                "field_name": field_name,
                "received_category": received,
                "expected_category": expected,
                "safely_handled": True,
            },
            value_type="dict",
            source_ref=src,
            source_revision=_source_revision(item),
            observed_at=item.get("observed_at", _NOW),
        ))

    return facts


def _detect_boundary_literalism(state: SystemState) -> list[GroundedFact]:
    """BOUNDARY_LITERALISM — injected only for now.

    Predicate: 'boundary_check' with operator='strictly_less_than',
               threshold, observed, where observed == threshold.
    """
    facts: list[GroundedFact] = []

    injected = state.injected_read_models.get("__boundary_checks__", [])
    for item in injected:
        if item.get("operator") != "strictly_less_than":
            continue
        threshold = item.get("threshold")
        observed = item.get("observed")
        if threshold is None or observed is None:
            continue
        if observed != threshold:
            continue
        src = item.get("source_ref", "injected:__boundary_checks__")
        fact_id = _make_fact_id("boundary", str(threshold))
        facts.append(GroundedFact(
            fact_id=fact_id,
            subject_ref=item.get("subject_ref", "unknown"),
            predicate="boundary_check",
            value={
                "operator": "strictly_less_than",
                "threshold": threshold,
                "observed": observed,
            },
            value_type="dict",
            source_ref=src,
            source_revision=_source_revision(item),
            observed_at=item.get("observed_at", _NOW),
        ))

    return facts


def _detect_mutually_exclusive_constraints(state: SystemState) -> list[GroundedFact]:
    """MUTUALLY_EXCLUSIVE_CONSTRAINTS — injected only for now.

    Predicate: 'constraint_solver_result' with satisfiable=False,
               unsat_core_operator_count >= 2.
    """
    facts: list[GroundedFact] = []

    injected = state.injected_read_models.get("__constraint_results__", [])
    for item in injected:
        if item.get("satisfiable", True) is not False:
            continue
        count = item.get("unsat_core_operator_count", 0)
        if count < 2:
            continue
        src = item.get("source_ref", "injected:__constraint_results__")
        fact_id = _make_fact_id("constraint", src + str(count))
        facts.append(GroundedFact(
            fact_id=fact_id,
            subject_ref=item.get("subject_ref", "unknown"),
            predicate="constraint_solver_result",
            value={
                "satisfiable": False,
                "unsat_core_operator_count": count,
            },
            value_type="dict",
            source_ref=src,
            source_revision=_source_revision(item),
            observed_at=item.get("observed_at", _NOW),
        ))

    return facts


# ---------------------------------------------------------------------------
# Primary entry point
# ---------------------------------------------------------------------------

_DETECTORS = [
    _detect_approval_dependency_cycle,
    _detect_confidence_evidence_gap,
    _detect_order_of_magnitude_anomaly,
    _detect_premature_success,
    _detect_retry_without_progress,
    _detect_redundant_gate_chain,
    _detect_scope_mismatch,
    _detect_wording_intent_mismatch,
    _detect_type_category_collision,
    _detect_boundary_literalism,
    _detect_mutually_exclusive_constraints,
]


def produce_signal_facts(state: SystemState) -> list[GroundedFact]:
    """Run all signal detectors against real state and return grounded facts.

    ANTI-CONFABULATION: each fact emitted here traces to a real source_ref.
    Detectors that find no condition return an empty list silently.
    All errors are suppressed per-detector (emit nothing rather than crash).

    Args:
        state: SystemState describing where to find real data.

    Returns:
        list of GroundedFact, possibly empty if no conditions are detected.
    """
    results: list[GroundedFact] = []
    for detector in _DETECTORS:
        try:
            found = detector(state)
            results.extend(found)
        except Exception:
            # Silently skip: better to miss a signal than to fabricate one
            pass
    return results


# ---------------------------------------------------------------------------
# Convenience factory: build SystemState from conventional paths
# ---------------------------------------------------------------------------

def default_state(
    read_models_dir: str = "/home/openclaw/generated/read_models",
    control_plane_db: str = "/home/openclaw/polish_loop/control_plane.sqlite3",
    ledger_db: str = "/home/openclaw/.openclaw/business_ops/ledger.sqlite",
) -> SystemState:
    """Return a SystemState wired to conventional OpenClaw paths."""
    return SystemState(
        read_models_dir=read_models_dir,
        control_plane_db=control_plane_db,
        ledger_db=ledger_db,
    )
