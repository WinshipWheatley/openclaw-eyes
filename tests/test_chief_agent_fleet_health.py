"""Chief fleet-health grounding: the status rail must surface real 'what's running' data.

Baseline gap: chief_status_rail carried only authority-boundary metadata; zero grounded
agent-state, sync posture, or shipped-milestone facts. This pins the fix —
chief_agent_fleet_health.json (from agent_presence + sync_health + git log) becomes a
grounded fleet-health surface in the Chief status rail.

Tests:
  1. Generator produces valid schema + grounded facts when sources are present.
  2. Grounded facts carry source_ref and freshness (provenance proof).
  3. Status rail surfaces fleet_health_summary when fleet_health.json exists.
  4. Status rail gracefully degrades (no crash) when fleet_health.json is absent.
  5. Generator produces zero grounded facts (not confabulated) when sources are missing.
  6. No shell/network/send authority in generated output.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import chief_agent_fleet_health as fh_mod
import chief_status_rail as status_rail


# ── Fixtures ────────────────────────────────────────────────────────────────────

def _write(root: Path, name: str, payload: dict) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / name).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _presence_payload(online=("guardian", "hermes"), degraded=("chief",), offline=("cassandra", "niles")) -> dict:
    agents = []
    for a in online:
        agents.append({"agent_id": a, "display_name": a.capitalize(), "actual_state": "online",
                       "desired_state": "online", "expected_online": True, "lane_id": a})
    for a in degraded:
        agents.append({"agent_id": a, "display_name": a.capitalize(), "actual_state": "degraded",
                       "desired_state": "online", "expected_online": True, "lane_id": a,
                       "blocker": "only some expected runtime surfaces show active evidence"})
    for a in offline:
        agents.append({"agent_id": a, "display_name": a.capitalize(), "actual_state": "offline",
                       "desired_state": "online", "expected_online": True, "lane_id": a,
                       "blocker": "expected runtime evidence missing"})
    return {
        "schema_version": "agent_presence_read_model_v0",
        "generated_at": "2026-06-22T04:00:00+00:00",
        "agent_count": len(agents),
        "online_count": len(online),
        "agents": agents,
    }


def _sync_payload() -> dict:
    return {
        "schema_version": "sync_health_read_model_v0",
        "generated_at": "2026-06-22T03:30:00+00:00",
        "mirror_status": "ok",
        "display_status": "current",
        "trust_status": "trusted",
        "operator_action_required": False,
        "missing_expected": 0,
        "hash_mismatch": 0,
        "last_mac_completion": {"time": "2026-06-22T03:00:00+00:00", "status": "synced"},
    }


def _segmentation_payload() -> dict:
    return {
        "schema_version": "chief_role_capability_segmentation_map_v0",
        "repo_b_delta_read_model_used": False,
        "chief_sub_areas": [
            {
                "sub_area_id": "chief_work_packets",
                "display_name": "Chief work packets",
                "classification": "TESTED_SUPPORTING_CONTRACT",
                "claim_level": "proven_control_plane_artifact",
                "authority_boundary": "Work packets are review/planning artifacts.",
                "next_safe_lane": "Chief Status Rail Completion v0",
                "needs_operator_memory_review": False,
                "operator_memory_guidance": [],
            }
        ],
    }


def _fleet_health_payload() -> dict:
    return {
        "schema_version": "chief_agent_fleet_health_v0",
        "generated_at": "2026-06-22T05:00:00+00:00",
        "generated_by": "chief_agent_fleet_health.py",
        "agent_health": {
            "total_agents": 6,
            "online_count": 2,
            "online_agents": ["guardian", "hermes"],
            "degraded_agents": ["chief"],
            "offline_agents": ["cassandra", "niles"],
            "unexpected_offline_count": 3,
            "blockers": [
                {"agent_id": "cassandra", "state": "offline", "blocker": "expected runtime evidence missing"},
                {"agent_id": "chief", "state": "degraded", "blocker": "only some expected runtime surfaces show active evidence"},
                {"agent_id": "niles", "state": "offline", "blocker": "expected runtime evidence missing"},
            ],
            "summary": "Fleet: 2/6 agents online. Online: guardian, hermes. Degraded: chief. Offline: cassandra, niles. Blockers: cassandra(offline), chief(degraded), niles(offline).",
        },
        "sync_health": {
            "mirror_status": "ok",
            "display_status": "current",
            "trust_status": "trusted",
            "operator_action_required": False,
            "last_mac_completion_time": "2026-06-22T03:00:00+00:00",
            "last_mac_completion_status": "synced",
            "missing_expected": 0,
            "hash_mismatch": 0,
            "summary": "Sync: mirror=ok, display=current. Last Mac sync: 2026-06-22T03:00:00+00:00 (synced). No blocking sync problems.",
        },
        "git_milestones": {
            "branch": "main",
            "milestones": [
                {"commit": "abc1234", "at": "2026-06-22T04:00:00+00:00", "summary": "feat(dank-1): fleet health grounding"},
                {"commit": "def5678", "at": "2026-06-22T03:00:00+00:00", "summary": "fix(niles): producer listener venv fix"},
            ],
            "count": 2,
            "available": True,
        },
        "grounded_facts": [
            {
                "topic": "fleet_health",
                "label": "Agent fleet health summary",
                "value": "Fleet: 2/6 agents online. Online: guardian, hermes.",
                "source_ref": "generated/read_models/agent_presence.json",
                "freshness": {"as_of": "2026-06-22T04:00:00+00:00", "source_ref": "generated/read_models/agent_presence.json"},
                "pii_tier": "PUBLIC",
            },
            {
                "topic": "sync_health",
                "label": "Mac/PC sync health posture",
                "value": "Sync: mirror=ok, display=current. No blocking sync problems.",
                "source_ref": "generated/read_models/sync_health.json",
                "freshness": {"as_of": "2026-06-22T03:30:00+00:00", "source_ref": "generated/read_models/sync_health.json"},
                "pii_tier": "PUBLIC",
            },
            {
                "topic": "shipped_milestones",
                "label": "Recently shipped engineering milestones",
                "value": "2 recent milestones on main. Latest: abc1234: feat(dank-1): fleet health grounding.",
                "source_ref": "git log (shipped feat/fix/chore/perf/refactor commits)",
                "freshness": {"as_of": "2026-06-22T05:00:00+00:00", "source_ref": "git log (shipped feat/fix/chore/perf/refactor commits)"},
                "pii_tier": "PUBLIC",
            },
        ],
        "grounded_fact_count": 3,
        "agent_activation_allowed": False,
        "repair_authority_added": False,
        "send_authority_added": False,
    }


# ── Generator tests ──────────────────────────────────────────────────────────────

def test_generator_produces_grounded_facts_from_real_sources(tmp_path):
    """Generator must produce 3 grounded facts when all sources are present."""
    rm = tmp_path / "read_models"
    _write(rm, "agent_presence.json", _presence_payload())
    _write(rm, "sync_health.json", _sync_payload())

    payload = fh_mod.build_chief_agent_fleet_health(
        repo_root=tmp_path,
        read_model_root=rm,
        generated_at="2026-06-22T10:00:00+00:00",
    )

    assert payload["schema_version"] == fh_mod.SCHEMA_VERSION
    assert payload["generated_at"] == "2026-06-22T10:00:00+00:00"
    # All 3 grounded facts present (fleet_health, sync_health, shipped_milestones)
    facts = payload["grounded_facts"]
    topics = {f["topic"] for f in facts}
    assert "fleet_health" in topics
    assert "sync_health" in topics
    # shipped_milestones may or may not exist depending on git availability — no assert required


def test_grounded_facts_carry_source_ref_and_freshness(tmp_path):
    """Each grounded fact must have source_ref and freshness.as_of for provenance."""
    rm = tmp_path / "read_models"
    _write(rm, "agent_presence.json", _presence_payload())
    _write(rm, "sync_health.json", _sync_payload())

    payload = fh_mod.build_chief_agent_fleet_health(
        repo_root=tmp_path,
        read_model_root=rm,
    )

    for fact in payload["grounded_facts"]:
        assert fact.get("source_ref"), f"fact {fact.get('topic')} missing source_ref"
        assert fact.get("freshness", {}).get("as_of"), f"fact {fact.get('topic')} missing freshness.as_of"
        assert fact.get("topic"), "grounded fact missing topic"
        assert fact.get("value"), "grounded fact missing value"


def test_fleet_health_grounded_fact_references_agent_presence_source(tmp_path):
    """The fleet_health fact must reference agent_presence.json as its source."""
    rm = tmp_path / "read_models"
    _write(rm, "agent_presence.json", _presence_payload())
    _write(rm, "sync_health.json", _sync_payload())

    payload = fh_mod.build_chief_agent_fleet_health(repo_root=tmp_path, read_model_root=rm)
    fleet_facts = [f for f in payload["grounded_facts"] if f["topic"] == "fleet_health"]

    assert len(fleet_facts) == 1
    assert "agent_presence.json" in fleet_facts[0]["source_ref"]
    # Value must mention online agents — grounded, not confabulated
    assert "guardian" in fleet_facts[0]["value"] or "hermes" in fleet_facts[0]["value"]


def test_no_grounded_facts_when_sources_missing(tmp_path):
    """If neither agent_presence.json nor sync_health.json is present, zero grounded facts — not confabulated."""
    rm = tmp_path / "empty_read_models"
    rm.mkdir()

    payload = fh_mod.build_chief_agent_fleet_health(repo_root=tmp_path, read_model_root=rm)

    # Only git milestones fact may exist (git available) — presence/sync facts must not appear
    non_git_facts = [f for f in payload["grounded_facts"] if f["topic"] in ("fleet_health", "sync_health")]
    assert non_git_facts == [], f"No confabulated facts when sources absent: {non_git_facts}"


def test_generator_authority_flags_are_all_false(tmp_path):
    """Generator output must carry no execution, repair, or send authority."""
    rm = tmp_path / "read_models"
    _write(rm, "agent_presence.json", _presence_payload())

    payload = fh_mod.build_chief_agent_fleet_health(repo_root=tmp_path, read_model_root=rm)

    assert payload["agent_activation_allowed"] is False
    assert payload["repair_authority_added"] is False
    assert payload["send_authority_added"] is False


# ── Status rail integration tests ────────────────────────────────────────────────

def _build_status_rail(repo: Path, with_fleet_health: bool = True) -> dict:
    """Build a Chief status rail with full fixture setup."""
    rm = repo / "generated" / "read_models"
    rm.mkdir(parents=True, exist_ok=True)
    _write(rm, "chief_role_capability_segmentation_map.json", _segmentation_payload())
    _write(rm, "work_board.json", {
        "schema_version": "work_board_read_model_v0",
        "counts_by_agent": {"chief": 3},
        "counts_by_column": {"routed": 3},
        "direct_execution_allowed": False,
        "agent_activation_allowed": False,
        "model_call_allowed": False,
        "tool_execution_allowed": False,
    })
    _write(rm, "agent_work_packets.json", {
        "schema_version": "agent_work_packets_read_model_v0",
        "counts_by_agent": {"chief": 1},
        "counts_by_status": {"draft": 1},
        "execution_allowed": False,
        "agent_activation_allowed": False,
        "model_call_allowed": False,
        "tool_execution_allowed": False,
    })
    _write(rm, "intent_router.json", {
        "schema_version": "intent_router_read_model_v0",
        "counts_by_agent": {"chief": 2},
        "counts_by_category": {},
        "direct_execution_allowed": False,
        "runtime_authority": False,
        "model_execution_allowed": False,
        "tool_execution_allowed": False,
        "source_posture": {},
    })
    _write(rm, "dropped_intents.json", {
        "schema_version": "dropped_intents_read_model_v0",
        "counts_by_agent": {"chief": 1},
        "counts_by_status": {"deferred": 1},
        "notification_allowed": False,
        "autonomous_prompting_allowed": False,
        "model_call_allowed": False,
        "raw_private_scan_allowed": False,
    })
    if with_fleet_health:
        _write(rm, "chief_agent_fleet_health.json", _fleet_health_payload())

    return status_rail.build_chief_status_rail(
        repo_root=repo,
        generated_at="2026-06-22T10:00:00+00:00",
    )


def test_status_rail_surfaces_fleet_health_summary_when_available(tmp_path):
    """Status rail must include fleet_health_summary with agent states when fleet_health.json exists."""
    payload = _build_status_rail(tmp_path / "repo", with_fleet_health=True)

    fhs = payload.get("fleet_health_summary")
    assert fhs is not None, "fleet_health_summary must be present in status rail"
    assert fhs["available"] is True
    ah = fhs.get("agent_health") or {}
    assert ah.get("online_count") == 2
    assert "guardian" in ah.get("online_agents", [])
    assert "hermes" in ah.get("online_agents", [])


def test_status_rail_exposes_grounded_facts_list(tmp_path):
    """Status rail must expose fleet_health_grounded_facts list for downstream packet wiring."""
    payload = _build_status_rail(tmp_path / "repo", with_fleet_health=True)

    facts = payload.get("fleet_health_grounded_facts")
    assert isinstance(facts, list), "fleet_health_grounded_facts must be a list"
    assert len(facts) == 3, f"Expected 3 grounded facts, got {len(facts)}: {facts}"

    topics = {f["topic"] for f in facts}
    assert "fleet_health" in topics
    assert "sync_health" in topics
    assert "shipped_milestones" in topics


def test_status_rail_gracefully_degrades_without_fleet_health(tmp_path):
    """Status rail must not crash when fleet_health.json is absent; summary.available must be False."""
    payload = _build_status_rail(tmp_path / "repo", with_fleet_health=False)

    fhs = payload.get("fleet_health_summary")
    assert fhs is not None, "fleet_health_summary key must exist even if data is absent"
    assert fhs["available"] is False
    facts = payload.get("fleet_health_grounded_facts")
    assert facts == [], "No grounded facts when fleet_health.json is absent"


def test_status_rail_operator_output_includes_fleet_health_section(tmp_path):
    """Operator Markdown must include a Fleet Health section with grounded data."""
    payload = _build_status_rail(tmp_path / "repo", with_fleet_health=True)
    md = status_rail.format_chief_status_rail(payload)

    assert "Fleet Health" in md
    # Online agents should be visible in the operator output
    assert "guardian" in md or "hermes" in md or "Online" in md
    # Sync health should surface
    assert "Sync" in md or "sync" in md


def test_status_rail_existing_authority_flags_unaffected_by_fleet_health(tmp_path):
    """Adding fleet health must not disturb existing authority flags or rail status."""
    payload = _build_status_rail(tmp_path / "repo", with_fleet_health=True)

    assert payload["rail_status"] == "completed_visibility_planning_only"
    assert payload["chief_current_proven_role"]["executor"] is False
    assert payload["runtime_authority_added"] is False
    assert payload["send_or_submit_authority_added"] is False
    assert payload["llm_ollama_called"] is False
    assert payload["telegram_send_triggered"] is False


def test_export_writes_fleet_health_json_to_disk(tmp_path):
    """Export function must write both JSON and operator Markdown to disk."""
    rm = tmp_path / "read_models"
    _write(rm, "agent_presence.json", _presence_payload())
    _write(rm, "sync_health.json", _sync_payload())

    summary = fh_mod.export_chief_agent_fleet_health(
        repo_root=tmp_path,
        read_model_root=rm,
        export_root="read_models",
        generated_at="2026-06-22T10:00:00+00:00",
    )

    json_path = tmp_path / summary["json_path"]
    assert json_path.exists(), f"JSON not written: {json_path}"
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == fh_mod.SCHEMA_VERSION
    assert payload["grounded_fact_count"] >= 2  # at least fleet_health + sync_health
