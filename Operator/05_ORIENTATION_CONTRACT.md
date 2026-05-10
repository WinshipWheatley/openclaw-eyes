# 05 Orientation Contract v0

## Purpose
This is the five-second orientation contract for any participant in OpenClaw (Human Operator, Cassandra, Chief, Guardian, Gemini/Codex, deterministic connector, future Mission Control UI, Map Room, or SQLite ledger reader). It ensures everyone knows where they are, what they are allowed to do, and where the boundaries lie.

## The 11-Question Orientation Contract

1. **Where are we?**
   Inside the OpenClaw repository stack. CWD is `/home/openclaw`. We are in the middle of hardening the Business Ops Spine and canonicalizing the Operator Doctrine.

2. **What lane is active?**
   Hardening the "Business Ops Spine" (deterministic intent, bounded capability, SQLite Ledger) and canonicalizing the "Operator Doctrine" (North Star, Manifesto, Anti-drift) into a concise Orientation Contract.

3. **What is confirmed?**
   - SQLite Ledger v0 exists, and Cassandra `handle()` is wired to record event/packet receipts.
   - Business Ops Packet v0 is defined for intent-based capability gating.
   - Operator Doctrine root files exist in `Operator/`.
   - The current session state is grounded in the `Active Handoff` and repository evidence.

4. **What is historical/non-authoritative?**
   - Old chats and model memory.
   - Legacy JSONL logs remain evidence, while SQLite Ledger is the emerging packet/receipt substrate.
   - Research docs in `docs/planning/` that have not been promoted to a Packet Rail.
   - The `Active Handoff` is a current checkpoint, not the sole truth.

5. **What is blocked or unknown?**
   - Live runtime launch or service mutation.
   - External MCP writes or hidden canonical memory writes.
   - PII/Sensitive data in the ledger.
   - Automated financial or legal actions.

6. **What tools/capabilities are allowed?**
   - Repository-local file reading and surgical editing.
   - Shell commands for status, testing, and non-destructive operations.
   - Business Ops Ledger append-only writes.
   - Classification of intent via `operator_intent_core.py`.

7. **What should not be touched?**
   - Private roots (`.google-secrets`, `.chief.env`, etc.).
   - Legal/Client/Private folders.
   - External provider/model APIs without an Action Covenant.
   - Credentials, tokens, and billing logic.

8. **What is the next safe move?**
   Complete the Orientation Contract v0, then build Orientation Snapshot v0 as a read-only status/orientation surface.

9. **How many moves ahead are clearly visible, what are they, and where does safe recommendation stop?**
   - **Visible moves**: Create Orientation Contract (1), Build read-only Orientation Snapshot v0 (2), then consider Cassandra `where are we?` wiring after snapshot proof (3).
   - **Safe recommendation stops** before Chief Router ledger integration, HITL migration, retrieval receipts, side-effect receipts, or runtime/service changes.

10. **What is the North Star?**
    Make daily life lighter without becoming hidden authority. The computer becomes a natural extension of the operator. The machine carries the weight; the operator keeps the crown.

11. **What is the operator/Winship manifesto, and how do we implement it without drifting or faking progress with slop?**
    Build with devotion to ideals, quality, and heart. Implementation must feel human, not corporate sludge. Avoid "No UI Before Grounding" and "No Live Surface Without Gates." Move with big, bounded strides on clear rails.

## Authority Rules
- **Old chats are historical context, not authority.**
- **Repo docs/source/tests/receipts/operator promotions are stronger than chat memory.**
- **The active handoff is the current checkpoint; canonical repo docs, committed source, receipts, tests, and explicit operator promotions govern durable truth.**
- **SQLite ledger records receipts, not permission.**
- **Map Room describes the field, not the terrain.**

## Recovered North Star Wording
"OpenClaw exists to make daily life lighter without becoming hidden authority. The computer becomes a natural extension of the operator. The machine carries the weight. The operator keeps the crown."
"Software should have curves and live in color. It must serve art, beauty, connection, and impact. Small, durable, local-first, and testable code is the highest form of taste."

## Trimmed Operator Manifesto
- Build for operators, artists, builders, and world-benders.
- The Action Covenant is the system's sacred pause before power.
- Code should be small, durable, local-first, testable, and revocable.
- Authority gates remain deterministic and explicit.
- Do not turn OpenClaw into corporate approval sludge.

## Anti-Drift Rules
- **Stop the Slop**: Big bounded strides on clear rails. No micro-prompts for visible work.
- **Implementation > Doctrine**: Stop writing once the rail is settled.
- **No Fake Progress**: No UI before grounding. No live surface without gates. No stale steering from transient watch files.

## Slop/Fake-Progress Warnings
- If the work feels "floaty," return to the Operator Loop: Intent -> Evidence -> Covenant -> Visible Frame.
- Beware of "No Baby Steps" violations where clear work is chopped into crumbs.
- Avoid building dashboards before the data contract is verified.

## Visible Road Horizon
*These fields define the safe boundary for any plan or proposal.*

- **visible_moves_count**: [Number of clearly mapped steps]
- **visible_moves**: [List of moves]
- **branch_after**: [The point where the path diverges or becomes unknown]
- **why_stop_there**: [Reason for the horizon limit (e.g., requires evidence, approval, or discovery)]
- **unsafe_to_recommend_beyond**: [The boundary where logic becomes speculative]
- **required_evidence_to_extend_horizon**: [The specific receipt or state required to move the boundary]

## Future Implementation Note
This Orientation Contract will serve as doctrine input for the **Orientation Snapshot v0** CLI tool. Orientation Snapshot v0 should populate fields from current repo state, committed doctrine docs, ledger receipts, runtime/readiness maps, tests, and active handoff checkpoint context. The active handoff is useful orientation, not sole authority.
