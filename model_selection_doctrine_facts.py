"""
model_selection_doctrine_facts.py — Curated model-selection DOCTRINE facts (MS-1..MS-4).

Mirrors canonical_doctrine_facts.py (the SD-1..13 pattern). These are DURABLE
doctrine (temporal_or_doctrine="doctrine") distilled from the operator's
model-selection reference ("Choosing an LLM Brain", 2026-06-22) and GROUNDED
against the real routing/enforcement code that already implements them.

Each record carries:
  - sensitivity_class: operational_canonical / public_canonical (matches SD facts)
  - allowed_actors: agents that reason about model selection (chief routes,
    hermes does model-intelligence, guardian enforces, maestro must know prompts
    are not the security layer). NOT cassandra/niles/fin — they do not pick models.
  - temporal_or_doctrine: "doctrine"
  - provenance.grounding_status: GROUNDED (verified against code) /
    PARTIALLY_GROUNDED (verified against the reference doc, not code).

IMPORTANT: this is the §B DOCTRINE set ONLY. The §C model CATALOG (concrete
vendor model strings) is TEMPORAL and is NOT ingested here — it requires the
TTL / live-verify mechanism first (observational-trap guardrail). Catalog lives
in model_backend_catalog.py (Hermes thread), not in this doctrine set.

UNGROUNDED items would be skipped by the loader; none here are UNGROUNDED.
"""

from canonical_fact_ingest import ingest_graded_fact


# ---------------------------------------------------------------------------
# Model-Selection Doctrine Facts (MS-1 through MS-4)
# ---------------------------------------------------------------------------

MODEL_SELECTION_DOCTRINE_FACTS = [

    # ── MS-1 ─────────────────────────────────────────────────────────────────
    {
        "fact_id": "MS-1",
        "fact_text": (
            "OpenClaw routes model work by abstract model-CLASS, not vendor "
            "name. Deterministic code handles webhooks, health, schedules, and "
            "filtering with no LLM; a cheap fast-worker class classifies, "
            "extracts, summarizes, and decides escalation; a deep-reasoner / "
            "architect class is reserved for hard planning, ambiguous judgment, "
            "failure recovery, and high-stakes tool use; coding is delegated to "
            "a coding-optimized worker. Routing is privacy-aware (a provider "
            "privacy level gates external vs local-only) and Guardian-gated. "
            "Decoupling policy from vendor names lets the model catalog change "
            "without changing routing policy."
        ),
        "sensitivity_class": "operational_canonical",
        "allowed_actors": ["chief", "hermes", "guardian"],
        "doc_category": "model_selection_doctrine",
        "temporal_or_doctrine": "doctrine",
        "source_file": "model_router_policy.py",
        "section_heading": "MS-1: Hierarchical class-based model routing",
        "source_commit": "HEAD",
        "source_description": "Hierarchical class-based model routing doctrine",
        "truth_status": "declared",
        "verification_required": 1,
        "provenance": {
            "source_file": "model_router_policy.py",
            "section_or_symbol": "ModelCandidateClass (line ~53); model_candidate_classes() (line ~131); select_model_class() (line ~248); _provider_privacy_level() (line ~213)",
            "basis_quote": 'class ModelCandidateClass / def select_model_class(request) / def _provider_privacy_level(request)',
            "secondary_sources": [
                {"file": "model_selection_policy_contract.py", "symbol": "MODEL_CLASSES", "quote": 'MODEL_CLASSES = ("local_small_fast", "external_fast_worker", "external_deep_reasoner", ...)'},
            ],
            "grounding_status": "GROUNDED",
        },
    },

    # ── MS-2 ─────────────────────────────────────────────────────────────────
    {
        "fact_id": "MS-2",
        "fact_text": (
            "Model escalation and fallback are distinct mechanisms. Fallbacks "
            "advance on SERVICE errors (auth, rate-limit, overload, timeout, "
            "billing) and stay within the same capability tier — they never "
            "switch to a smarter model because a task got hard. Complexity "
            "escalation to a higher model class must be EXPLICIT: driven by "
            "routing rules, a coordinator decision, confidence checks, "
            "validation failures, or subagent delegation — never by a "
            "service-error fallback. Conflating the two silently upgrades cost "
            "and capability and breaks consequence accounting."
        ),
        "sensitivity_class": "operational_canonical",
        "allowed_actors": ["chief", "hermes", "guardian"],
        "doc_category": "model_selection_doctrine",
        "temporal_or_doctrine": "doctrine",
        "source_file": "model_router_policy.py",
        "section_heading": "MS-2: Escalation is explicit, not a fallback",
        "source_commit": "HEAD",
        "source_description": "Escalation-vs-fallback doctrine",
        "truth_status": "declared",
        "verification_required": 1,
        "provenance": {
            "source_file": "model_router_policy.py",
            "section_or_symbol": "fallback_provider_policy_id (line ~97); default_posture='fallback_conservative' (line ~160)",
            "basis_quote": 'fallback_provider_policy_id: str  /  default_posture="fallback_conservative"',
            "secondary_sources": [
                {"file": "_specs/POLISH-LOOP-DISPATCHER-DESIGN.md", "symbol": "consequence/complexity dispatcher", "quote": "consequence is an un-discountable hard floor; escalation is explicit"},
            ],
            "grounding_status": "GROUNDED",
        },
    },

    # ── MS-3 ─────────────────────────────────────────────────────────────────
    {
        "fact_id": "MS-3",
        "fact_text": (
            "Tool policies, execution approvals, sandboxing, and allowlists are "
            "the HARD enforcement layer for a tool-enabled agent; system "
            "prompts are soft guidance and cannot reliably secure it. Prompt "
            "injection is unsolved, especially on untrusted content (web, "
            "email, files, attachments). Apply least-privilege, spend limits, "
            "bounded retries, timeouts, idempotent jobs, audit logs, isolated "
            "sessions, and human-in-the-loop at defined risk thresholds. In "
            "OpenClaw this hard layer is SEND_HOLD plus the three-tier HITL gate "
            "plus the deterministic Python authority gate — never a model's "
            "system prompt."
        ),
        "sensitivity_class": "operational_canonical",
        "allowed_actors": ["chief", "hermes", "guardian", "maestro"],
        "doc_category": "model_selection_doctrine",
        "temporal_or_doctrine": "doctrine",
        "source_file": "chief_approval_policy.py",
        "section_heading": "MS-3: Hard enforcement layer, not soft prompts",
        "source_commit": "HEAD",
        "source_description": "Enforcement-is-the-hard-layer doctrine",
        "truth_status": "declared",
        "verification_required": 1,
        "provenance": {
            "source_file": "chief_approval_policy.py",
            "section_or_symbol": "is_hard_t2() (line ~281)",
            "basis_quote": 'def is_hard_t2(action): "Hard T2 rules are structurally prior and cannot be overridden by any caller"',
            "secondary_sources": [
                {"file": "protected_generate.py", "symbol": "send_hold_active", "quote": '"SEND_HOLD is absolute."'},
                {"file": "canonical_doctrine_facts.py", "symbol": "SD-1, SD-2", "quote": "SEND_HOLD + three-tier HITL gate doctrine"},
            ],
            "grounding_status": "GROUNDED",
        },
    },

    # ── MS-4 ─────────────────────────────────────────────────────────────────
    {
        "fact_id": "MS-4",
        "fact_text": (
            "An always-on model Gateway does not burn tokens merely by being "
            "online — tokens are consumed only on invocation (messages, "
            "webhooks, scheduled runs, heartbeats, subagent calls). Heartbeats "
            "default to roughly 30 minutes and are tunable, can use a cheaper "
            "model, or be disabled. A large context window is NOT permanent "
            "memory: transcripts, compaction, memory files, and search are "
            "separate mechanisms; persistence must be designed, not assumed "
            "from context-window size."
        ),
        "sensitivity_class": "public_canonical",
        "allowed_actors": ["chief", "hermes"],
        "doc_category": "model_selection_doctrine",
        "temporal_or_doctrine": "doctrine",
        "source_file": "_specs/MODEL-SELECTION-DOCTRINE-AND-CATALOG.md",
        "section_heading": "MS-4: Gateway economics and memory",
        "source_commit": "HEAD",
        "source_description": "Gateway-economics and context-vs-memory doctrine",
        "truth_status": "declared",
        "verification_required": 1,
        "provenance": {
            "source_file": "_specs/MODEL-SELECTION-DOCTRINE-AND-CATALOG.md",
            "section_or_symbol": "§B Economics bullet",
            "basis_quote": "an always-on Gateway does NOT burn tokens by being online — tokens are consumed on invocation; large context window != permanent memory",
            "secondary_sources": [],
            # PARTIALLY_GROUNDED: verified against the operator reference doc (a
            # tracked artifact), not against implementing code. The loader still
            # ingests PARTIALLY_GROUNDED; only UNGROUNDED is held.
            "grounding_status": "PARTIALLY_GROUNDED",
        },
    },
]


# ---------------------------------------------------------------------------
# Loader: ingest the model-selection doctrine via the single door.
# Mirrors canonical_doctrine_facts.load_doctrine_facts exactly.
# ---------------------------------------------------------------------------

def load_model_selection_doctrine(db_path: str, allow_production: bool = False) -> dict:
    """
    Ingest all curated model-selection doctrine facts via ingest_graded_fact.

    Idempotent: re-run returns all skipped (content_hash dedup).
    Never ingests an UNGROUNDED fact (none here are). GROUNDED +
    PARTIALLY_GROUNDED are ingestible.

    Returns:
        {"inserted": int, "skipped": int, "ungrounded_skipped": int,
         "total": int, "results": list[dict]}
    """
    inserted = 0
    skipped = 0
    ungrounded_skipped = 0
    results = []

    for record in MODEL_SELECTION_DOCTRINE_FACTS:
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
        "total": len(MODEL_SELECTION_DOCTRINE_FACTS),
        "results": results,
    }
