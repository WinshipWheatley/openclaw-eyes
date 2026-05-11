# Chief Machine Contract

## Status
- **Source basis**: Repo evidence only (`chief_router.py`, `chief_approval_policy.py`, `chief_approval_brain.py`, `chief_acceptance_gate.py`, `chief_session_manager.py`).
- **Implementation State**: BUILT / CURRENT BEHAVIOR (Core), IMPLIED / NOT FORMALIZED (Packets).
- **Contract Authority**: This document is the governing rulebook for Chief's role and boundaries.
- **Packet Authority**: Formal schemas (future) will derive from this contract.

## Implementation State Vocabulary
- **BUILT / CURRENT BEHAVIOR**: Logic exists in Python files.
- **FORMALIZED**: Named contract/schema defines the behavior.
- **WIRED**: Connected into runtime.
- **RECEIPTED**: Produces durable evidence (e.g., Approval Log.md).
- **INDEXED**: Discoverable in maps/docs.
- **IMPLIED / NOT FORMALIZED**: Behavior exists, but packet schema is not named/tested.
- **FUTURE / NOT VERIFIED**: Desired doctrine not yet wired.

## Role
Chief is the central **Orchestration, Routing, Approval-Policy, and Acceptance Authority**. Chief acts as the primary interface between the operator's intent and the agentic execution lanes. Chief does not perform high-risk side-effects directly but evaluates their intent, classifies their risk, and routes them to the appropriate gate or executor.

## Current Repo-Evident Surfaces
- `chief_router.py`: **BUILT**. Intent detection and routing to specialized brains.
- `chief_approval_policy.py`: **BUILT**. Definition of Tier 0/1/2 risk classifications and "Hard T2" rules.
- `chief_approval_brain.py`: **BUILT**. Lifecycle management of approval requests and HMAC-backed integrity.
- `chief_acceptance_gate.py`: **BUILT**. Model-backed verdict (APPROVE/REWORK) for loop results.
- `chief_session_manager.py`: **BUILT**. Workflow state and history persistence.
- `Chief/Approval Log.md`: **RECEIPTED**. Durable record of operator decisions.

## Authority Boundary
- **Centralized Routing**: Chief owns the intent-to-lane mapping authority. Other agents must not implement independent top-level routing.
- **Policy Enforcement**: Chief evaluates `ActionIntent` against `chief_approval_policy.py`. 
- **Guardian Deference**: Chief **MUST** defer to Guardian (Telegram) for all Tier 2 (high-risk) actions. Chief cannot downgrade "Hard T2" rules.
- **Acceptance Authority**: Chief provides the acceptance verdict for polish-loop completion based on configured evidence and harness expectations; this does not override Guardian, operator, or proof requirements.
- **No Side-Effects (Self)**: Chief's "brains" are generally `no_side_effects: true` for evaluation; execution is delegated to specialized scripts/lanes.
- **No Hidden Authority**: Chief must not use LLM synthesis to override deterministic policy or skip human approval.

## Current / Implied Packet Families

### ChiefActionIntentEvaluationPacket
- **Status**: BUILT BEHAVIOR / IMPLIED PACKET / NOT FORMALIZED.
- **Input Evidence**: Raw operator text or agentic proposal.
- **Output**: Intent classification, suggested lane, and identified risk tier (0, 1, or 2).
- **Allowed Actions**: Routing to sub-brain, request for clarification.
- **Blocked Actions**: Execution of intent before approval evaluation.
- **Owner Lane**: Chief.

### ChiefApprovalDecisionPacket
- **Status**: BUILT BEHAVIOR / IMPLIED PACKET / RECEIPTED / NOT FORMALIZED AS TEMPLATE.
- **Input Evidence**: `ActionIntent`, risk tier, and operator decision (Yes/No/Delay).
- **Output**: `approved: true/false`, HMAC action hash, and decision timestamp.
- **Allowed Actions**: Signal execution lane to proceed.
- **Blocked Actions**: Modification of the action after approval; bypassing Guardian for T2.
- **Required Receipt**: Entry in `Approval Log.md`.
- **Owner Lane**: Chief / Guardian.

### ChiefAcceptanceVerdictPacket
- **Status**: BUILT BEHAVIOR / IMPLIED PACKET / NOT FORMALIZED.
- **Input Evidence**: Task name, pass number, planner verdict, PC output summary, and harness manifest.
- **Output**: `APPROVE`, `REWORK`, or `INSUFFICIENT_EVIDENCE`.
- **Allowed Actions**: Archive task as complete or trigger re-pass.
- **Blocked Actions**: Marking a task as "done" without an `APPROVE` verdict.
- **Owner Lane**: Chief.

### ChiefRoutingDecisionPacket
- **Status**: BUILT BEHAVIOR / IMPLIED PACKET / NOT FORMALIZED.
- **Input Evidence**: Operator input text and current session state.
- **Output**: Target brain (e.g., `scout`, `email`, `financial`) and route method (`pattern`, `llm_local`, `fallback`).
- **Allowed Actions**: Invoke target brain.
- **Blocked Actions**: Routing to unauthorized or non-indexed lanes.
- **Owner Lane**: Chief.

## Evidence and Context Sources
- **Action Intent**: Captured from `chief_router.py` input.
- **Approval Policy**: `chief_approval_policy.py`.
- **Guardian Receipts**: Validated via `chief_approval_brain.py` and `chief_guardian_listener.py`.
- **Harness Manifests**: Used by `chief_acceptance_gate.py`.
- **Session History**: `chief_session_manager.py`.

## Blocked Actions
- **Bypassing Guardian**: No Tier 2 action may skip the out-of-band Telegram gate.
- **LLM-Based Approval**: Synthesis cannot override `ALWAYS_T2` regex rules.
- **Silent Mutation**: No mutation of `Approval Log.md` or financial records without an explicit, logged approval.
- **Shadow Routing**: Agents must not route requests to each other without Chief's coordination.

## Explainability Requirement (FUTURE)
Chief should answer "Why was this decision made?" by linking:
1. The `ActionIntentEvaluationPacket`.
2. The specific rule in `chief_approval_policy.py` that triggered the tier.
3. The `ChiefApprovalDecisionPacket` and its `Approval Log.md` receipt.
4. For acceptance, the specific evidence fields in `ChiefAcceptanceVerdictPacket`.

## SQLite / Receipt Alignment
Current `backend_sqlite_schema.py` supports `validation_receipts` and `operator_promotions`. Chief should leverage these for durable proof-of-acceptance in future iterations.

## Do Not Build Yet
- New runtime router architecture.
- Automatic action execution without explicit "ActionIntent" isolation.
- LLM-based policy overrides.
- Removal of `chief_approval_policy.py` regex safety.

## Recommended Next Slice
1. Index this contract in docs/maps.
2. Audit Chief packet schema placement.
3. Create Chief packet templates/tests only after placement audit.
