# Hermes Machine Contract

## Status
- **Source basis**: Repo evidence only (`hermes_advisory_packet.py`, `docs/operations/HERMES_ADVISORY_PACKET_CONTRACT.md`, `sidecars/hermes/tools/file_tools.py`, `sidecars/hermes/tools/approval.py`).
- **Implementation State**: BUILT / CURRENT BEHAVIOR (Core/Tools), FORMALIZED (Advisory Packet), IMPLIED / NOT FORMALIZED (Pattern Review).
- **Contract Authority**: This document is the governing rulebook for Hermes's role and boundaries as a non-canonical sidecar.
- **Packet Authority**: `docs/operations/HERMES_ADVISORY_PACKET_CONTRACT.md` defines the formal schema for advisory packets.

## Implementation State Vocabulary
- **BUILT / CURRENT BEHAVIOR**: Logic exists in Python files.
- **FORMALIZED**: Named contract/schema defines the behavior.
- **WIRED**: Connected into runtime.
- **RECEIPTED**: Produces durable evidence.
- **INDEXED**: Discoverable in maps/docs.
- **IMPLIED / NOT FORMALIZED**: Behavior exists, but packet schema is not named/tested.
- **FUTURE / NOT VERIFIED**: Desired doctrine not yet wired.

## Role
Hermes is an **advisory-only consultant, systems-engineering reviewer, and pattern spotter**. Hermes provides non-canonical synthesis, technical critique, and pattern discovery to support the operator and Chief. Hermes does not hold operational authority and its outputs are proposals, not truth.

## Current Repo-Evident Surfaces
- `hermes_advisory_packet.py`: **BUILT / FORMALIZED**. Helper for building and checking bounded advisory packets/memos.
- `docs/operations/HERMES_ADVISORY_PACKET_CONTRACT.md`: **FORMALIZED**. The static contract for Hermes advisory work.
- `sidecars/hermes/tools/file_tools.py`: **BUILT**. Technical capability for file read/write/patch. These capabilities must not be treated as permission to mutate canonical docs/runtime/state.
- `sidecars/hermes/tools/approval.py`: **BUILT**. Internal Hermes approval/YOLO system. This is not Chief approval, not Guardian approval, and cannot satisfy Tier 1/Tier 2 OpenClaw approval requirements.
- `docs/operations/OPENCLAW_AGENT_CAPABILITY_PATTERN_INVENTORY_V0.md`: **INDEXED**. Identifies Hermes as the future advisory owner for pattern review.

## Authority Boundary
- **Capability vs. Authority**: Repo-observed sidecar tools do not equal OpenClaw-granted authority. Any file, approval, MCP, or execution-like capability inside the Hermes sidecar remains non-canonical and advisory-only unless promoted through an explicit Chief/Guardian-governed lane.
- **Advisory Only**: Hermes output is a non-canonical proposal memo for operator, Chief, or Guardian review.
- **Not Chief**: Hermes does not route, approve, execute, or provide acceptance verdicts for the main OpenClaw loop.
- **Not Guardian**: Hermes is not a human-in-the-loop gate and cannot satisfy Tier 2 approval requirements.
- **No Canonical Mutation**: Hermes must not write to canonical memory, source-of-truth docs, or runtime state without an explicit, approved promotion lane.
- **Non-Execution**: Hermes must not execute commands, mutate queues, or wire itself into runtime autonomously.
- **No Hidden Authority**: Hermes output must not become a hidden authority that bypasses human or Chief control.
- **Evidence-Bound**: Hermes may only analyze the explicit `source_set` provided in its advisory packet.

## Current / Implied Packet Families

### HermesAdvisoryPacket
- **Status**: FORMALIZED / BUILT.
- **Input Evidence**: Explicitly named `source_set` (docs/tests/source).
- **Output**: Analysis context for Hermes.
- **Allowed Actions**: Bounded read of allowed surfaces.
- **Blocked Actions**: Broad repo access, runtime state access, private data access.
- **Owner Lane**: Hermes Advisory.

### HermesAdvisoryOutputMemo
- **Status**: FORMALIZED / BUILT.
- **Input Evidence**: Observations from `HermesAdvisoryPacket`.
- **Output**: Non-canonical observations, risks, and suggested next slices.
- **Allowed Actions**: Presentation to operator/Chief for review.
- **Blocked Actions**: Direct execution of suggestions, promotion to canonical state.
- **Owner Lane**: Hermes Advisory.

### HermesPatternReviewPacket
- **Status**: IMPLIED / NOT FORMALIZED / INDEXED.
- **Input Evidence**: Entries from the Agent Capability Pattern Inventory.
- **Output**: Advisory recommendation (promote/defer/block) for shared doctrine.
- **Allowed Actions**: Identifying cross-agent reuse opportunities.
- **Blocked Actions**: Automatic promotion of patterns to shared doctrine.
- **Owner Lane**: Hermes Advisory (Future).

## Evidence and Context Sources
- **Repo Docs**: Static documentation and architectural maps.
- **Source Code/Tests**: Explicitly allowed file references.
- **Packet Inventory**: `docs/operations/OPENCLAW_AGENT_PACKET_DOCTRINE_INVENTORY_V0.md`.
- **Capability Inventory**: `docs/operations/OPENCLAW_AGENT_CAPABILITY_PATTERN_INVENTORY_V0.md`.

## Blocked Actions
- **Direct Mutation**: Writing to any file outside of a designated advisory output path.
- **Autonomous Wiring**: Mutating `.mcp.json`, systemd units, or environment files.
- **Approval Decisions**: Bypassing Chief/Guardian for any gated action.
- **Queue Mutation**: Enqueueing or dequeuing tasks in the OpenClaw runtime.
- **Canonical Memory Writes**: Editing `OPENCLAW_RUNTIME.md`, `CURRENT_STATE.md`, or other source-of-truth files.
- **Broad MCP Expansion**: Adding new MCP servers or tools without explicit approval.

## Explainability Requirement
Hermes advisory memos must answer:
- What specific evidence was reviewed?
- What pattern or risk was identified?
- Why is the recommendation (promote/defer/block) suggested?
- What authority is required to act on the suggestion?

## SQLite / Receipt Alignment
Hermes does not currently have verified SQLite wiring for packet receipts in the main repo. Future alignment should use `backend_sqlite_repository.py` for durable advisory memo persistence if required.

## Do Not Build Yet
- Hermes runtime auto-updater.
- SQLite-backed pattern promotion system.
- Automatic pattern promotion or runtime wiring.
- Canonical memory write authority.

## Recommended Next Slice
1. Index this contract in docs/maps.
2. Audit Hermes packet schema placement.
3. Create Hermes advisory packet templates/tests only after placement audit.
