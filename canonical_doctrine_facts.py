"""
canonical_doctrine_facts.py — Curated shared-doctrine fact records (SD-1..SD-13).

EVERY fact is verifiable against a REAL tracked source in the repo.
Each record carries:
  - fact_text: the canonical claim
  - sensitivity_class: PUBLIC / LIGHT / MED / HIGH / MAX
  - allowed_actors: list of agent ids that need this fact
  - doc_category: thematic classification
  - temporal_or_doctrine: "doctrine" for all shared-doctrine facts
  - provenance: {source_file, section_or_symbol, basis_quote}
    - source_file must be `git ls-files`-tracked
    - basis_quote is a short verbatim string from that file

UNGROUNDED items are flagged with provenance["grounding_status"] = "UNGROUNDED"
and a reason. These must NOT be ingested until grounded.

Author: populate-1b build (curated, not LLM-generated).
"""

from canonical_fact_ingest import ingest_graded_fact

# ---------------------------------------------------------------------------
# Shared Doctrine Facts (SD-1 through SD-13)
# ---------------------------------------------------------------------------

SHARED_DOCTRINE_FACTS: list[dict] = [

    # ── SD-1 ─────────────────────────────────────────────────────────────────
    {
        "fact_id": "SD-1",
        "fact_text": (
            "SEND_HOLD is the system-wide money/external-send gate: no agent "
            "transmits an email, SMS, payment, invoice-send, or paid-mark on "
            "its own word. A send is HELD pending the deterministic approval "
            "path (Hard-T2 → Guardian out-of-band Telegram approval) and only "
            "releases after explicit operator approval with a receipt. Maestro "
            "enforces send_hold_active=True on every receipt; Cassandra is "
            "hard send-blocked; Chief cannot self-approve; executors "
            "(email/invoice) do not transmit on Chief's word alone."
        ),
        "sensitivity_class": "operational_canonical",
        "allowed_actors": ["maestro", "chief", "guardian", "cassandra"],
        "doc_category": "send_gate_doctrine",
        "temporal_or_doctrine": "doctrine",
        "source_file": "protected_generate.py",
        "section_heading": "SD-1: SEND_HOLD system-wide gate",
        "source_commit": "HEAD",
        "source_description": "System-wide SEND_HOLD doctrine",
        "truth_status": "declared",
        "verification_required": 1,
        "provenance": {
            "source_file": "protected_generate.py",
            "section_or_symbol": "send_hold_active (line ~494); system_prompt (line ~567)",
            "basis_quote": '"send_hold_active": True / "SEND_HOLD is absolute."',
            "secondary_sources": [
                {"file": "maestro_listener.py", "symbol": "AUTHORITY_BOUNDARY", "quote": "live_email_send_allowed: False"},
                {"file": "chief_approval_policy.py", "symbol": "_ALWAYS_T2", "quote": 'r"send\\s+email|send\\s+sms"'},
            ],
            "grounding_status": "GROUNDED",
        },
    },

    # ── SD-2 ─────────────────────────────────────────────────────────────────
    {
        "fact_id": "SD-2",
        "fact_text": (
            "OpenClaw's approval gate has three tiers. Tier 0 = no gate (pure "
            "reads, git status/diff/commit/push-without-force, run tests, "
            "vault edits). Tier 1 = local y/N confirm, escalating to Tier 2 if "
            "no TTY (installs, service restarts, mv/rename, non-secret config "
            "edits). Tier 2 = remote phone approval via Guardian bot, blocking "
            "until reply or timeout (auto-deny, fail-closed). Unknown actions "
            "default to Tier 2 (conservative). Hard-T2 rules ALWAYS force "
            "Tier 2 and can NEVER be downgraded by any caller (git force-push/"
            "reset --hard/clean; destructive verbs on billing/invoice/payment; "
            "any .csv/.jsonl touch; credential/secret files; SSN/tax-id; "
            "external publish/send; drop/truncate table; bulk deletions)."
        ),
        "sensitivity_class": "operational_canonical",
        "allowed_actors": ["chief", "guardian", "maestro", "cassandra"],
        "doc_category": "approval_policy",
        "temporal_or_doctrine": "doctrine",
        "source_file": "chief_approval_policy.py",
        "section_heading": "SD-2: Three-tier HITL approval gate",
        "source_commit": "HEAD",
        "source_description": "Three-tier approval gate doctrine",
        "truth_status": "declared",
        "verification_required": 1,
        "provenance": {
            "source_file": "chief_approval_policy.py",
            "section_or_symbol": "_ALWAYS_T2 (line ~150), _T1_PATTERNS (line ~186), _T0_PATTERNS (line ~202), classify() (line ~219), is_hard_t2() (line ~281)",
            "basis_quote": 'def is_hard_t2(action): "Hard T2 rules are structurally prior and cannot be overridden by any caller"',
            "grounding_status": "GROUNDED",
        },
    },

    # ── SD-3 ─────────────────────────────────────────────────────────────────
    {
        "fact_id": "SD-3",
        "fact_text": (
            "Guardian is the final human-in-the-loop approval/denial boundary "
            "and output/PII gate. Role separation is structural: Chief = "
            "orchestrator/router (cannot self-approve), Cassandra = assistant "
            "(intentionally excluded from the approval fallback chain), "
            "Guardian = the gate. Bypassing Guardian for a Tier 2 action, "
            "LLM-based approval of a gated action, silent mutation of the "
            "Approval Log, and shadow routing between agents without Chief's "
            "coordination are all explicitly blocked."
        ),
        "sensitivity_class": "public_canonical",
        "allowed_actors": ["chief", "guardian", "maestro", "cassandra"],
        "doc_category": "approval_policy",
        "temporal_or_doctrine": "doctrine",
        "source_file": "chief_guardian_sender.py",
        "section_heading": "SD-3: Guardian final HITL boundary",
        "source_commit": "HEAD",
        "source_description": "Guardian role-separation doctrine",
        "truth_status": "declared",
        "verification_required": 1,
        "provenance": {
            "source_file": "chief_guardian_sender.py",
            "section_or_symbol": "module docstring (line ~8-12)",
            "basis_quote": '"Cassandra bot is intentionally excluded from the fallback chain. Role separation: Chief = operator, Cassandra = assistant, Guardian = approval gate."',
            "secondary_sources": [
                {"file": "docs/operations/CHIEF_MACHINE_CONTRACT.md", "symbol": "Authority Boundary / Blocked Actions", "quote": "(tracked)"},
                {"file": "docs/operations/GUARDIAN_MACHINE_CONTRACT.md", "symbol": "role definition", "quote": "(tracked)"},
            ],
            "grounding_status": "GROUNDED",
        },
    },

    # ── SD-4 ─────────────────────────────────────────────────────────────────
    {
        "fact_id": "SD-4",
        "fact_text": (
            "OpenClaw agent roster: maestro (front-door conductor / operator "
            "voice, request_only, ZERO execution authority), chief "
            "(orchestrator / intent-router / approval-policy + acceptance "
            "authority, request_only), cassandra (email+calendar executive "
            "assistant 'Clara Reed', advisory_only, draft+send-blocked), "
            "guardian (safety / output-gate / PII / final HITL approval "
            "boundary), hermes (systems-engineering consultant SIDECAR — "
            "read-only, ZERO authority), niles (live audio: X32 via OSC + "
            "DAW), fin (finance/invoicing/AR/AP/ledger). Maestro answers "
            "roster questions from this fixed self-knowledge, not the LLM."
        ),
        "sensitivity_class": "public_canonical",
        "allowed_actors": ["maestro", "chief", "guardian", "hermes", "cassandra", "niles"],
        "doc_category": "system_self_knowledge",
        "temporal_or_doctrine": "doctrine",
        "source_file": "agent_lane_registry.py",
        "section_heading": "SD-4: Agent roster",
        "source_commit": "HEAD",
        "source_description": "Canonical agent roster",
        "truth_status": "declared",
        "verification_required": 1,
        "provenance": {
            "source_file": "agent_lane_registry.py",
            "section_or_symbol": "DEFAULT_AGENT_LANE_SEEDS (line ~121)",
            "basis_quote": 'AgentLaneSeed(agent_id="chief", authority_level="request_only", ...)',
            "secondary_sources": [
                {"file": "capability_registry.py", "symbol": "capability index", "quote": "(tracked)"},
            ],
            "grounding_status": "GROUNDED",
        },
    },

    # ── SD-5 ─────────────────────────────────────────────────────────────────
    {
        "fact_id": "SD-5",
        "fact_text": (
            "OPENCLAW_RUNTIME.md is the governance source-of-truth. AGENTS.md "
            "is a thin redirect that points to it. When doctrine and code "
            "disagree, the runtime doc governs intent and the code governs "
            "current enforcement; gaps between them are tracked in "
            "KNOWN_GAPS.md."
        ),
        "sensitivity_class": "public_canonical",
        "allowed_actors": ["maestro", "chief", "guardian", "hermes", "cassandra", "niles"],
        "doc_category": "governance_doctrine",
        "temporal_or_doctrine": "doctrine",
        "source_file": "OPENCLAW_RUNTIME.md",
        "section_heading": "SD-5: Runtime law source-of-truth",
        "source_commit": "HEAD",
        "source_description": "Governance source-of-truth declaration",
        "truth_status": "declared",
        "verification_required": 1,
        "provenance": {
            "source_file": "OPENCLAW_RUNTIME.md",
            "section_or_symbol": "document title (line 1-5)",
            "basis_quote": '"This is the canonical vendor-neutral runtime law for OpenClaw."',
            "secondary_sources": [
                {"file": "AGENTS.md", "symbol": "redirect", "quote": '"The canonical runtime law is OPENCLAW_RUNTIME.md"'},
                {"file": "KNOWN_GAPS.md", "symbol": "tracked gaps", "quote": "(tracked)"},
            ],
            "grounding_status": "GROUNDED",
            "note": (
                "Blueprint SD-5 also cites CORE_ARCHITECTURE_PRINCIPLES.md, "
                "OPEN_CLAW_MANIFEST.md, USER.md, RUNBOOK.md, STATE_MACHINE.md, "
                "SEND_PREREQUISITES.md, CURRENT_STATE.md — these are NOT tracked "
                "by git ls-files. Fact text narrowed to verifiable claims only."
            ),
        },
    },

    # ── SD-6 ─────────────────────────────────────────────────────────────────
    {
        "fact_id": "SD-6",
        "fact_text": (
            "PII in OpenClaw is GRADED tokenization, not an absolute wall: "
            "the system PROCESSES the operator's data through LLMs by design; "
            "mature practice is reversible, tiered tokenization — treat PII as "
            "typed numbered placeholders ([EMAIL_1],[NAME_1]) the model does "
            "not need the values of, re-identify in the response, and only "
            "gate the EXTERNAL/irreversible hop (money, external send). Keep "
            "data local/minimal; log detection COUNTS not the PII itself; "
            "default to sending the model the minimum it needs. Money and "
            "external sends stay gated regardless."
        ),
        "sensitivity_class": "public_canonical",
        "allowed_actors": ["guardian", "maestro", "chief", "cassandra"],
        "doc_category": "pii_doctrine",
        "temporal_or_doctrine": "doctrine",
        "source_file": "protected_generate.py",
        "section_heading": "SD-6: Graded-PII philosophy",
        "source_commit": "HEAD",
        "source_description": "Graded PII tokenization doctrine",
        "truth_status": "declared",
        "verification_required": 1,
        "provenance": {
            "source_file": "protected_generate.py",
            "section_or_symbol": "send_hold_active=True, pii_tier classification",
            "basis_quote": '"send_hold_active": True, "pii_tier": tier',
            "grounding_status": "PARTIALLY_GROUNDED",
            "note": (
                "Blueprint cites feedback_graded_pii.md as primary source — "
                "NOT tracked by git ls-files. The graded-PII principle is "
                "enforced in protected_generate.py (pii_tier classification) "
                "and the system prompt, but the philosophical source doc is "
                "untracked. Fact text grounded against code enforcement."
            ),
        },
    },

    # ── SD-7 ─────────────────────────────────────────────────────────────────
    {
        "fact_id": "SD-7",
        "fact_text": (
            "An LLM (including a guardrail/judge LLM) is one UNTRUSTED layer "
            "and must never be the enforcement boundary. The system that "
            "INTERPRETS policy must not be the system that ENFORCES it: "
            "deterministic controls (allow/deny lists, privilege separation, "
            "output blocking, tool sandboxing, human-in-the-loop) give hard "
            "boundaries regardless of what the model decides; probabilistic "
            "controls (input filters, classifiers) only layer on top. This "
            "grounds Chief's deterministic _ALWAYS_T2 rules enforced beneath "
            "LLM synthesis, Maestro's classify_frontdoor_intent pre-input "
            "gate plus Guardian's output gate, and the rule that Hard-T2 "
            "cannot be downgraded by any caller."
        ),
        "sensitivity_class": "public_canonical",
        "allowed_actors": ["chief", "guardian", "maestro", "hermes"],
        "doc_category": "security_doctrine",
        "temporal_or_doctrine": "doctrine",
        "source_file": "chief_approval_policy.py",
        "section_heading": "SD-7: Defense-in-depth — LLM only proposes",
        "source_commit": "HEAD",
        "source_description": "Defense-in-depth doctrine",
        "truth_status": "declared",
        "verification_required": 1,
        "provenance": {
            "source_file": "chief_approval_policy.py",
            "section_or_symbol": "_ALWAYS_T2, is_hard_t2()",
            "basis_quote": '"Hard T2 rules are structurally prior and cannot be overridden by any caller"',
            "secondary_sources": [
                {"file": "maestro_cassandra_responder.py", "symbol": "classify_frontdoor_intent", "quote": "(line ~256)"},
            ],
            "grounding_status": "GROUNDED",
        },
    },

    # ── SD-8 ─────────────────────────────────────────────────────────────────
    {
        "fact_id": "SD-8",
        "fact_text": (
            "Grounding is an ARCHITECTURAL concern, not a prompt trick: "
            "maestro_context_packet supplies deterministic facts with provenance "
            "and requires real truth inputs (require_real_truth=True). Each "
            "fact carries label/value/provenance/source_ref/pii_tier/freshness. "
            "When no relevant source is found, the system prompt instructs "
            "'If the answer is not in the packet, say you don't have it' — "
            "an explicit refusal path. Refusing is safer than hallucinating "
            "in high-stakes/private-data domains."
        ),
        "sensitivity_class": "public_canonical",
        "allowed_actors": ["maestro", "chief", "guardian", "cassandra"],
        "doc_category": "answer_doctrine",
        "temporal_or_doctrine": "doctrine",
        "source_file": "maestro_context_packet.py",
        "section_heading": "SD-8: Grounded answering with refusal path",
        "source_commit": "HEAD",
        "source_description": "Grounded answering doctrine",
        "truth_status": "declared",
        "verification_required": 1,
        "provenance": {
            "source_file": "maestro_context_packet.py",
            "section_or_symbol": "require_real_truth (line ~511, ~521)",
            "basis_quote": '"Maestro context packet requires real truth inputs: operator truth plus generated read models."',
            "secondary_sources": [
                {"file": "protected_generate.py", "symbol": "system_prompt (line ~567)", "quote": '"Use only the deterministic packet below. If the answer is not in the packet, say you don\'t have it."'},
            ],
            "grounding_status": "GROUNDED",
        },
    },

    # ── SD-9 ─────────────────────────────────────────────────────────────────
    {
        "fact_id": "SD-9",
        "fact_text": (
            "Least-privilege for multi-agent orchestrators: a coordinator may "
            "have broad routing reach, but at the DELEGATION/HANDOFF point a "
            "sub-agent or executor lane inherits only the minimum permissions "
            "for the specific task, never the orchestrator's full scope. An "
            "agent that reviews/plans must not be able to execute/deploy unless "
            "explicitly granted. This grounds Chief as request_only (prepares "
            "packets/routing/verdicts but is blocked from direct_execution, "
            "final approval_decision, truth_promotion, file move/delete) and "
            "the rule that a Chief handoff does not transfer Chief's authority "
            "to the receiving lane."
        ),
        "sensitivity_class": "public_canonical",
        "allowed_actors": ["chief", "maestro", "guardian", "cassandra", "niles", "hermes"],
        "doc_category": "authority_doctrine",
        "temporal_or_doctrine": "doctrine",
        "source_file": "agent_lane_registry.py",
        "section_heading": "SD-9: Authority-minimization at handoff",
        "source_commit": "HEAD",
        "source_description": "Least-privilege handoff doctrine",
        "truth_status": "declared",
        "verification_required": 1,
        "provenance": {
            "source_file": "agent_lane_registry.py",
            "section_or_symbol": "DEFAULT_AGENT_LANE_SEEDS — chief blocked_output_kinds",
            "basis_quote": 'authority_level="request_only", blocked_output_kinds=("direct_execution", "approval_decision", "truth_promotion", "file_move", ...)',
            "secondary_sources": [
                {"file": "agent_handoff_registry.py", "symbol": "handoff registry", "quote": "(tracked)"},
                {"file": "capability_registry.py", "symbol": "capability scoping", "quote": "(tracked)"},
            ],
            "grounding_status": "GROUNDED",
        },
    },

    # ── SD-10 ────────────────────────────────────────────────────────────────
    {
        "fact_id": "SD-10",
        "fact_text": (
            "In a multi-agent system, agents must identify and locate one "
            "another via Agent Registration and Discovery, and discovery is "
            "capability-centric — peers are found by functional skills, "
            "operational state, and verified trust level, not merely by name. "
            "On launch an agent registers in a registry and periodically "
            "advertises structured metadata (agent_id, functional tags, "
            "authority posture, last_seen). An agent that is not registered "
            "is effectively undiscoverable by capability. This is the basis "
            "for closing the maestro registration gap: maestro is not present "
            "in DEFAULT_AGENT_LANE_SEEDS."
        ),
        "sensitivity_class": "public_canonical",
        "allowed_actors": ["maestro", "chief", "guardian", "hermes"],
        "doc_category": "system_self_knowledge",
        "temporal_or_doctrine": "doctrine",
        "source_file": "agent_lane_registry.py",
        "section_heading": "SD-10: Capability-centric registration & discovery",
        "source_commit": "HEAD",
        "source_description": "Agent registration and discovery doctrine",
        "truth_status": "declared",
        "verification_required": 1,
        "provenance": {
            "source_file": "agent_lane_registry.py",
            "section_or_symbol": "DEFAULT_AGENT_LANE_SEEDS (line ~121) — no 'maestro' entry",
            "basis_quote": 'DEFAULT_AGENT_LANE_SEEDS contains chief, cassandra, guardian — maestro absent',
            "secondary_sources": [
                {"file": "capability_registry.py", "symbol": "capability index", "quote": "(tracked)"},
            ],
            "grounding_status": "GROUNDED",
        },
    },

    # ── SD-11 ────────────────────────────────────────────────────────────────
    {
        "fact_id": "SD-11",
        "fact_text": (
            "To prove an approval/decision message is authentic and unmodified, "
            "Chief signs the exact raw payload with HMAC-SHA256 using "
            "APPROVAL_HMAC_SECRET over action+approval_id+requested_at. The "
            "hash appears in both the Telegram message and the pending JSON. "
            "A callback whose stored hash does not verify is rejected as "
            "tampered/invalid (fail-closed), blocking forged/replayed Telegram "
            "approvals from releasing a gated action."
        ),
        "sensitivity_class": "public_canonical",
        "allowed_actors": ["chief", "guardian"],
        "doc_category": "integrity_doctrine",
        "temporal_or_doctrine": "doctrine",
        "source_file": "chief_approval_brain.py",
        "section_heading": "SD-11: HMAC tamper-evidence for approvals",
        "source_commit": "HEAD",
        "source_description": "HMAC signing for approval integrity",
        "truth_status": "declared",
        "verification_required": 1,
        "provenance": {
            "source_file": "chief_approval_brain.py",
            "section_or_symbol": "_compute_hash (line ~317-330)",
            "basis_quote": '"Compute a short HMAC-SHA256 hash linking the action, id, and timestamp. Tampering with the action in the JSON would produce a hash mismatch."',
            "grounding_status": "GROUNDED",
        },
    },

    # ── SD-12 ────────────────────────────────────────────────────────────────
    {
        "fact_id": "SD-12",
        "fact_text": (
            "A Time-of-Check-to-Time-of-Use race exists whenever a system "
            "checks a condition and later acts on it. Chief closes the TOCTOU "
            "race between has_pending_approval() and _save_pending() by "
            "acquiring an exclusive advisory flock slot-lock before the check "
            "and holding it through the write, so two requests cannot both "
            "claim the approval slot. Collision results in DENY "
            "(single-flight)."
        ),
        "sensitivity_class": "public_canonical",
        "allowed_actors": ["chief", "guardian"],
        "doc_category": "concurrency_doctrine",
        "temporal_or_doctrine": "doctrine",
        "source_file": "chief_approval_brain.py",
        "section_heading": "SD-12: Single-flight approval slot (TOCTOU)",
        "source_commit": "HEAD",
        "source_description": "Atomic single-flight approval slot doctrine",
        "truth_status": "declared",
        "verification_required": 1,
        "provenance": {
            "source_file": "chief_approval_brain.py",
            "section_or_symbol": "_acquire_slot_lock (line ~286), atomic slot claim (line ~582)",
            "basis_quote": '"Atomic slot claim: acquire exclusive advisory flock → check → write → release. The lock closes the TOCTOU race between has_pending_approval() and _save_pending()."',
            "grounding_status": "GROUNDED",
        },
    },

    # ── SD-13 ────────────────────────────────────────────────────────────────
    {
        "fact_id": "SD-13",
        "fact_text": (
            "All Google API access is brokered through google_access_broker.py "
            "— the ONLY permitted Google entry point; no brain module calls "
            "Google APIs directly. Each capability carries an approval class: "
            "Class A = safe reads, auto-proceed (always audit-logged); Class B "
            "= reversible internal writes requiring L1 confirm; Class C = "
            "externally consequential/irreversible requiring L2 phone approval. "
            "Scopes are staged incrementally (Pass 1 calendar.events+"
            "contacts.readonly; Pass 2 +gmail.readonly; Pass 3 +gmail.compose) "
            "per least-privilege. The broker is inert until secrets exist and "
            "--auth is run manually (never from the stack)."
        ),
        "sensitivity_class": "public_canonical",
        "allowed_actors": ["cassandra", "chief", "guardian", "maestro", "hermes"],
        "doc_category": "google_broker_doctrine",
        "temporal_or_doctrine": "doctrine",
        "source_file": "google_access_broker.py",
        "section_heading": "SD-13: Google access brokered, class-graded, least-privilege",
        "source_commit": "HEAD",
        "source_description": "Google access broker doctrine",
        "truth_status": "declared",
        "verification_required": 1,
        "provenance": {
            "source_file": "google_access_broker.py",
            "section_or_symbol": "module docstring (line ~22), _ACTIVE_SCOPES (line ~76-85)",
            "basis_quote": '"All calls are policy-checked, approval-gated (Class B/C), and audit-logged." / "Pass 1 only. Do NOT add Pass 2/3 scopes until prior pass is verified and audited."',
            "secondary_sources": [
                {"file": "google_access_policy.py", "symbol": "CLASS_A/B/C, get_class (line ~25-27, ~100)", "quote": 'CLASS_A = "A" # Safe reads — auto-proceed, always logged'},
            ],
            "grounding_status": "GROUNDED",
        },
    },
]


# ---------------------------------------------------------------------------
# Loader: ingest all curated doctrine facts via the single door
# ---------------------------------------------------------------------------

def load_doctrine_facts(db_path: str, allow_production: bool = False) -> dict:
    """
    Ingest all curated shared-doctrine facts via ingest_graded_fact.

    Idempotent: re-run returns all skipped (content_hash dedup).

    Returns:
        {"inserted": int, "skipped": int, "total": int, "results": list[dict]}
    """
    inserted = 0
    skipped = 0
    ungrounded_skipped = 0
    results = []

    for record in SHARED_DOCTRINE_FACTS:
        # Never ingest an ungrounded fact (honors this module's contract): an LLM
        # must not write unverified canonical truth. GROUNDED + PARTIALLY_GROUNDED
        # (verified against real code/source) are ingestible; UNGROUNDED is held.
        if record.get("provenance", {}).get("grounding_status") == "UNGROUNDED":
            ungrounded_skipped += 1
            results.append({"status": "ungrounded_skipped", "fact_id": record.get("fact_id")})
            continue
        # Build a clean record for ingest_graded_fact (strip provenance —
        # it's an audit/review field, not a canonical_facts column)
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
        "total": len(SHARED_DOCTRINE_FACTS),
        "results": results,
    }
