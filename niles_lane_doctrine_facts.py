"""
niles_lane_doctrine_facts.py — Curated Niles creative-lane DOCTRINE facts (NL-1..NL-3).

Phase A1 of Niles Track A (deep memory / grounded packet). Mirrors
canonical_doctrine_facts.py and model_selection_doctrine_facts.py. These facts
describe Niles's CURRENT, grounded reality so the agents that reason about Niles
(maestro answers about it, chief routes to it, niles grounds itself, guardian
enforces) work from canonical truth.

Scope discipline (anti-drift): these describe what IS deployed — lane ownership,
the trust-tier-1 constraints, and the persistent-memory daemon. The X32/DAW
hardware-control capability lives in unmerged worktrees and is NOT yet in the
deployed system, so it is intentionally NOT asserted here; it becomes canonical
at Tier-3 graduation when the control code actually ships.

All GROUNDED against real repo artifacts (agent_lane_registry.py,
agent_memory_scope_contract.py, niles_memory_worker.py) + the recorded
trust-graduation roadmap.
"""

from canonical_fact_ingest import ingest_graded_fact


NILES_LANE_DOCTRINE_FACTS = [

    # ── NL-1 ─────────────────────────────────────────────────────────────────
    {
        "fact_id": "NL-1",
        "fact_text": (
            "Niles owns OpenClaw's music/creative/audio lane "
            "(lane_id=music_art_production): music and creative planning, "
            "live-set prep, song/session/setlist notes, and creative review "
            "packets. As of 2026-06-22 Niles runs as a live daemon "
            "(niles-listener) with persistent creative-lane memory "
            "(niles-memory-worker), alongside Chief/Cassandra/Hermes."
        ),
        "sensitivity_class": "public_canonical",
        "allowed_actors": ["niles", "chief", "maestro", "guardian"],
        "doc_category": "niles_lane_doctrine",
        "temporal_or_doctrine": "doctrine",
        "source_file": "agent_lane_registry.py",
        "section_heading": "NL-1: Niles owns the music/creative lane",
        "source_commit": "HEAD",
        "source_description": "Niles creative-lane ownership doctrine",
        "truth_status": "declared",
        "verification_required": 1,
        "provenance": {
            "source_file": "agent_lane_registry.py",
            "section_or_symbol": "DEFAULT_AGENT_LANE_SEEDS niles entry (lane_id='music_art_production')",
            "basis_quote": "agent_id='niles', lane_id='music_art_production', status='active_registry'",
            "secondary_sources": [
                {"file": "niles_memory_worker.py", "symbol": "MEMORY_LOG", "quote": "niles persistent creative-lane memory daemon"},
                {"file": "agent_memory_scope_contract.py", "symbol": "ACTOR_MEMORY_SCOPES", "quote": "actor_id='niles' memory scope"},
            ],
            "grounding_status": "GROUNDED",
        },
    },

    # ── NL-2 ─────────────────────────────────────────────────────────────────
    {
        "fact_id": "NL-2",
        "fact_text": (
            "Niles is trust-tier-1 (authority_level=advisory_only). It is "
            "constrained to intake, planning, notes, and review packets, and "
            "must NOT edit DAW sessions, mutate audio/media files, move or "
            "delete files, or directly execute (blocked_output_kinds). It has "
            "no model-call, network, send, or secret authority. DAW/hardware "
            "control and send authority are EARNED via the trust-graduation "
            "ladder — each rung requires a fresh operator approval plus a green "
            "gate; never auto-promotion. SEND_HOLD remains absolute regardless "
            "of tier."
        ),
        "sensitivity_class": "operational_canonical",
        "allowed_actors": ["niles", "chief", "maestro", "guardian"],
        "doc_category": "niles_lane_doctrine",
        "temporal_or_doctrine": "doctrine",
        "source_file": "agent_lane_registry.py",
        "section_heading": "NL-2: Niles trust-tier-1 constraints + graduation",
        "source_commit": "HEAD",
        "source_description": "Niles trust-tier and graduation doctrine",
        "truth_status": "declared",
        "verification_required": 1,
        "provenance": {
            "source_file": "agent_lane_registry.py",
            "section_or_symbol": "niles entry: authority_level='advisory_only'; blocked_output_kinds=('daw_session_edit','audio_file_mutation','file_move','file_delete','direct_execution')",
            "basis_quote": "authority_level='advisory_only', blocked_output_kinds=(...daw_session_edit...)",
            "secondary_sources": [
                {"file": "_specs/NILES-DAEMON-AND-TRUST-GRADUATION.md", "symbol": "Track B ladder", "quote": "each rung = track record + fresh operator approval + green gate"},
                {"file": "canonical_doctrine_facts.py", "symbol": "SD-1", "quote": "SEND_HOLD is absolute"},
            ],
            "grounding_status": "GROUNDED",
        },
    },

    # ── NL-3 ─────────────────────────────────────────────────────────────────
    {
        "fact_id": "NL-3",
        "fact_text": (
            "Niles has persistent creative-lane memory at parity with Chief's "
            "storage layer: niles-memory-worker tails the Niles intake queue "
            "into a durable, de-duplicated memory log (niles_memory_log.md). "
            "Niles's memory scope is contracted in agent_memory_scope_contract "
            "(actor_id='niles'). This memory is local storage/recall only at "
            "tier-1 — no model calls — and is the substrate for grounded recall "
            "and for graduation to model-backed reasoning."
        ),
        "sensitivity_class": "operational_canonical",
        "allowed_actors": ["niles", "chief", "maestro", "guardian"],
        "doc_category": "niles_lane_doctrine",
        "temporal_or_doctrine": "doctrine",
        "source_file": "niles_memory_worker.py",
        "section_heading": "NL-3: Niles persistent memory (Chief-parity storage)",
        "source_commit": "HEAD",
        "source_description": "Niles persistent-memory doctrine",
        "truth_status": "declared",
        "verification_required": 1,
        "provenance": {
            "source_file": "niles_memory_worker.py",
            "section_or_symbol": "QUEUE_LOG -> MEMORY_LOG tail loop (mirrors chief_memory_worker.py)",
            "basis_quote": "tails /mnt/c/OpenClaw/logs/niles_queue.log into niles_memory_log.md (dedup'd)",
            "secondary_sources": [
                {"file": "agent_memory_scope_contract.py", "symbol": "ACTOR_MEMORY_SCOPES", "quote": "actor_id='niles' memory scope (1 of 8 contracted actors)"},
            ],
            "grounding_status": "GROUNDED",
        },
    },
]


def load_niles_lane_doctrine(db_path: str, allow_production: bool = False) -> dict:
    """Ingest the Niles creative-lane doctrine via the single door.
    Mirrors canonical_doctrine_facts.load_doctrine_facts exactly.
    Idempotent (content_hash dedup); never ingests UNGROUNDED (none here are).
    """
    inserted = 0
    skipped = 0
    ungrounded_skipped = 0
    results = []

    for record in NILES_LANE_DOCTRINE_FACTS:
        if record.get("provenance", {}).get("grounding_status") == "UNGROUNDED":
            ungrounded_skipped += 1
            results.append({"status": "ungrounded_skipped", "fact_id": record.get("fact_id")})
            continue

        ingest_record = {
            "fact_id": record["fact_id"],
            "source_file": record["source_file"],
            "section_heading": record["section_heading"],
            "source_commit": record["source_commit"],
            "fact_text": record["fact_text"],
            "sensitivity_class": record["sensitivity_class"],
            "allowed_actors": record["allowed_actors"],
            "doc_category": record["doc_category"],
            "temporal_or_doctrine": record["temporal_or_doctrine"],
            "source_description": record.get("source_description"),
            "truth_status": record.get("truth_status", "declared"),
            "verification_required": record.get("verification_required", 1),
        }

        result = ingest_graded_fact(ingest_record, db_path=db_path, allow_production=allow_production)
        results.append(result)

        if result["status"] == "inserted":
            inserted += 1
        else:
            skipped += 1

    return {
        "inserted": inserted,
        "skipped": skipped,
        "ungrounded_skipped": ungrounded_skipped,
        "total": len(NILES_LANE_DOCTRINE_FACTS),
        "results": results,
    }
