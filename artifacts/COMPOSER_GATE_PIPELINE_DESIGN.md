# Composer + Gate Pipeline — Unified Design (v0 draft)

Status: **DESIGN OF RECORD. Initial code exists on the PC branch.** This is the
contract the backend API ("chief wrapper") is built around, fused with the
deterministic agent-package gate pipeline currently mid-build.

Author seam: written for Winship. Everything below names real modules already on
disk so the design is grounded, not aspirational. Where a stage is not yet wired,
it says so.

---

## 0. Why this doc exists

Two efforts collided and need one design:

1. **The lightweight client + API** ("say *set up the live stream* / *send invoice
   to X*; a thin app fires it; the PC backend does the work"). The keystone there
   is giving the backend a **front door** — today it only listens on Telegram and
   a shared folder.

2. **The deterministic agent-package gate pipeline with PII** — your
   `gate(PII) → agent 1 → gate → sqlite packet → gate → LM2 → gate` chain, which
   is "getting the tap for the composer areas in the brain."

These are the same thing viewed from two ends. The API is the **transport**; the
gate pipeline is the **composer** the transport feeds. Build the transport without
the composer seam and you tear it out the day the gates land. So: design the
composer first, wrap transport around the finished shape.

---

## 1. The two worlds today (reality, not plan)

### World 1 — live Telegram path (imperative, ungated)
- `chief_router.route_message(text) -> {"intent": str, "reply"|"replies": ...}`
- `chief_listener.py` calls it, then sends the reply segments to Telegram.
- Action intents (email, sms, billing, invoice) **draft/act inline**. No packet,
  no acceptance gate, no PII tokenization at the boundary.
- This is what actually serves you today. It works. It is not going away cheaply.

### World 2 — deterministic packet/gate substrate (your gate pipeline)
All real modules, all explicitly **non-executing** ("a plan is not authority"):

| Stage | Module / entry point | Notes |
|---|---|---|
| **G0 PII gate** | `pii_vault.redact_text(text) -> (redacted, TokenMap)` ; `rehydrate_text(text, token_map)` | Tokenizes emails/phones/SSNs/cards before prompt assembly. Also a Fernet vault for stored secrets. Built. |
| **A1 intent + provenance** | `intent_router.route_operator_intent(*, text, source_kind, source_channel, requested_by, ...) -> IntentRouteResult` | Classifies intent, stamps provenance, writes to the ledger. Built. |
| **P packet** | `agent_work_packet.build_agent_work_packet(...)` | Compiles latest intent into a bounded SQLite packet with `NO_AUTHORITY_FLAGS` (`execution_allowed: False`, `model_call_allowed: False`, …). Built. |
| **G2 acceptance gate** | `chief_acceptance_gate.evaluate_evidence(evidence: dict) -> "APPROVE"\|"REWORK"\|"INSUFFICIENT_EVIDENCE"` | Local-model bounded verdict. Built; header says "not yet wired into handle_mac_turn()." |
| **L2 second model / handoff** | `expert_staged_packet_flow`, `expert_synthetic_handoff.build_expert_synthetic_handoff(...)` | Staged, with a `FORBIDDEN_ACTIONS` list (no provider_call, no runner_invocation, no telegram_return…). Contract-stage. |
| **Spine (SQLite)** | `business_ops_ledger` @ `.openclaw/business_ops/ledger.sqlite` | Tables: `events, packets, capability_decisions, retrieval_receipts, side_effects, operator_explanations, canonical_facts, file_inventory, truth_registry_entries, verification_evidence`. Built. |

### The gap that defines the design
World 2 **plans and judges** but never **acts**. There is no *executor* that takes
an `APPROVE`d packet and performs the real side-effect (send the email, fire the
invoice, launch OBS). Execution today exists only in World 1, ungated. **The
executor is the missing piece, and it is the join between the two worlds.**

---

## 1.5 Deployment reality (RESOLVED via read-only PC probe, 2026-06-13)

Settled by SSHing the PC (`192.168.50.205`) read-only:

- The PC runs **two WSL distros**: `Ubuntu-E` (default) and `Ubuntu`.
- **`Ubuntu-E` is the live brain.** `/home/openclaw` there is the **`openclaw-eyes`**
  repo (HEAD `4cdc1d6`), and `chief_listener.py` is **running now** (PID 813,
  `/home/openclaw/chief_env/bin/python /home/openclaw/chief_listener.py`).
- **`Ubuntu` distro is dormant** — no `/home/openclaw`, no listener.
- **`openclaw-runtime` is legacy**, not live. Its name is misleading. Older router
  (Apr 1) and listener (Mar 29), 87 files vs eyes' 328.

**Consequence — the good news:** the live repo is `openclaw-eyes`, which is the
SAME repo as the `~/Eyes` checkout and already holds BOTH worlds (route_message +
the full packet/gate substrate). `compose()` is built here. No cross-repo port, no
consolidation step.

**Consequence — the caution:** the Mac `~/Eyes` checkout and the live PC have
**diverged**. Local `Eyes` is 3 commits ahead of `origin/main` (unpushed); the
PC's `4cdc1d6` is not in the Mac's history (PC has its own unpushed work). Two
live-ish checkouts, both diverged from origin. **Reconcile Mac ↔ PC ↔ origin
before any deploy/push.** Until then: additive local drafting only, no commits
into this repo.

The neutered `Eyes/start_chief.sh` ("Slice 4 refusal") is a red herring — the live
listener is launched by some other path (to be confirmed on the PC: likely
`start_chief_logged.sh`, `start_openclaw_brains.sh`, systemd, or manual nohup).

---

## 2. The unified `compose()` pipeline (proposal)

One transport-agnostic function. The API, the Telegram listener, and any future
client all call this and nothing deeper.

```
compose(text, source) -> ComposeResult

  G0  pii_vault.redact_text                     redact → TokenMap (held server-side)
   │
  A1  intent_router.route_operator_intent       classify + provenance → ledger
   │                                            ──► branch on intent class
   │
   ├─ READ-ONLY intent (status, Q&A, report) ───────────────┐
   │     fast path: route_message() or a read responder      │
   │     no packet, no gate. cheap. returns segments.         │
   │                                                          │
   └─ ACTION intent (email/sms/invoice/obs/...) ──┐           │
        │                                          │           │
       G1  capability_decisions                    │           │
            is this action class allowed at all?   │           │
        │                                          │           │
       P   agent_work_packet.build_*               │           │
            bounded plan in SQLite, no authority   │           │
        │                                          │           │
       G2  chief_acceptance_gate.evaluate_evidence │           │
            APPROVE / REWORK / INSUFFICIENT        │           │
        │                                          │           │
       L2  expert handoff / second model           │           │
            turn approved plan → concrete params   │           │
        │                                          │           │
       G3  HUMAN/Guardian gate  ◄── surfaced in app as APPROVE │
        │   on approve → EXECUTOR runs side-effect             │
        │   rehydrate PII in any outbound text                 │
        ▼                                          ▼           ▼
      ComposeResult { intent, segments[], packet_id?, gate_state, pending_approval? }
```

`ComposeResult` (proposed shape):
```jsonc
{
  "intent": "invoice_send",
  "gate_state": "PENDING_APPROVAL",      // or DONE | REWORK | BLOCKED | READ_ONLY
  "segments": ["Drafted invoice to Capital Hilton for $X.", "Approve to send."],
  "packet_id": "awp_2026...ab",          // null for read-only
  "pending_approval": {                   // null unless G3 is waiting
     "packet_id": "awp_2026...ab",
     "preview": { "to": "...", "amount": "...", "surface": "square_invoice" }
  }
}
```

### Why this is the good design, not just a safe one
- **The approval gate becomes an app tap, not a Telegram round-trip.** G3 is
  surfaced as one button. The "bloated card wall" collapses into: a packet preview
  + Approve/Rework. Small, purposeful surface — the opposite of today's card dump.
- **One choke point for safety.** Every action passes G0→G1→G2→G3. PII can't reach
  a model un-tokenized; nothing executes without an APPROVE and a human tap.
- **Read-only stays instant.** "what's my day look like" never touches the packet
  machinery — straight through the fast path.
- **Multi-device for free.** Telegram, Mac, iPad, iPhone, a friend's device all
  call `compose()`. The pipeline is identical; only transport differs.

---

## 3. Transport (the API) — wraps `compose()`, thin

Runs in WSL beside `chief_listener`. Tailscale-bound. Token auth.

| Endpoint | Purpose |
|---|---|
| `POST /message {text}` | → `ComposeResult`. The core. |
| `WS /ws` | stream `segments` live (talk feel; voice rides this later) |
| `GET /health` | brain up? |
| `POST /file` | register a file → `business_ops_ledger.file_inventory` (intake) |
| `GET /packets?state=pending` | list packets awaiting G3 |
| `POST /packets/{id}/approve` / `/rework` | drives G3; on approve → executor runs |

Voice needs **zero** backend work: Apple on-device Speech does mic→text on the
client, POSTs to `/message`; TTS reads `segments` back. The API is already
voice-shaped.

---

## 4. The executor (the missing piece — must be designed)

An **executor** consumes an `APPROVE`d packet and performs exactly the bounded
side-effect the packet names, then writes a receipt to `side_effects`.

Proposed contract:
```
execute_packet(packet_id) -> ExecutionReceipt
  preconditions: packet.gate_state == APPROVED (G2) AND human_approved (G3)
  dispatch on packet.surface:  e.g. "gmail_send" -> chief_email_brain.send(...)
                                     "square_invoice" -> invoice executor
                                     "obs_launch" -> local action broker
  on success: write side_effects receipt + canonical_facts update
  on failure: write side_effects(error), gate_state = FAILED, surface to operator
```
This is where World 1's brains (`chief_email_brain`, billing, etc.) get **reused
as executors** — but only ever called *behind* an approved packet, never inline.

---

## 5. Open design decisions (need Winship's call)

1. **`route_message`'s fate.** Keep it as the read-only fast path + legacy Telegram
   brain, while all *action* intents migrate to the gated `compose` path? Or fully
   absorb action intents into packet-executors and shrink `route_message` to
   read-only? (Recommendation: keep as fast path now; migrate actions one surface
   at a time — invoice first.)

2. **What is "LM2" to you?** Two candidate roles: (a) a *synthesizer* that turns an
   approved plan into concrete action parameters, or (b) a *second reviewer* that
   independently checks the packet before G3. The chain reads more like (a). Confirm.

3. **Ledger consolidation.** `business_ops_ledger.sqlite` (has `file_inventory`,
   live) vs the inert `backend_sqlite_schema.py` semantic-graph schema. Standardize
   on `business_ops_ledger` as the one spine and retire/fold the other?

4. **PII gate placement.** At `compose` entry only (cheap, catches obvious), or also
   inside each brain's prompt assembly (thorough, since internal model calls happen
   deep in the brains)? Likely both, with a documented policy. Define it.

5. **First action surface to take through the full pipeline end-to-end** as the
   proof: invoice send? email send? live-stream launch? (Recommendation: invoice —
   highest value, clearest gate story, `file_inventory` ties in proof docs.)

---

## 6. Build order (once design is signed off)

0. **Reconcile Mac ↔ PC ↔ origin git divergence** (see §1.5). The live PC repo and
   the Mac checkout have both diverged from origin. Pick a source of truth, merge,
   push, confirm the PC's live checkout. No `compose()` deploy until this is clean.
1. Lock `ComposeResult` + `execute_packet` contracts (`compose_contract.py` — done,
   dependency-free, see file). Ratify in this doc.
2. Implement `compose()` as the seam: G0 + A1 + read-only fast path delegating to
   `route_message`. Action path returns `PENDING_APPROVAL` with a real packet.
3. Stand up the transport (FastAPI + Tailscale + token) over `compose()`.
4. Build the executor for **one** surface (invoice) end-to-end: packet → G2 → G3
   tap in app → `execute_packet` → receipt.
5. Wire `POST /file` → `file_inventory`.
6. Strip the Mac app to: chat/voice in, segments out, packet-preview + Approve.
7. Then: iPad / iPhone reuse the same API.

Each step is independently shippable and leaves Telegram working throughout.

---

## 7. Drafting findings & open validation risks (v0, 2026-06-13)

Status: `compose_contract.py` ✅ done + self-test green. `chief_compose.py` ✅ drafted
against live signatures; pure branch logic self-test green; **full path needs PC
validation** (real `route_operator_intent` / `build_agent_work_packet` / `route_message`).

Discoveries that improve the design:
- **A1 already decides the gate.** Live `route_operator_intent` returns
  `approval_required`, `candidate_action_type`, `execution_allowed`, `status`,
  `rejection_reason`. So `compose()` branches on A1's own verdict — no hardcoded
  action list needed (`ACTION_INTENTS` is now only a safety net). Branch is
  fail-safe: unknown/missing fields → gated, never silent-execute.
- **Shared ledger confirmed:** both `intent_router` and `agent_work_packet` default
  to `.openclaw/business_ops/ledger.sqlite`, so the intent_id → packet handoff works.
- **`mission_control` and `future_client_node` are already valid `source_kind`s** —
  the Mac app and future iPad/iPhone/friends are first-class to the classifier.

Risks PC validation must close:
1. **Taxonomy alignment.** A1 (`route_operator_intent`) and the legacy
   `route_message` use different intent vocabularies. If A1 marks something
   not-approval but `route_message` would *act* on it, that's an ungated execution.
   `compose()` guards this (blocks + flags the disagreement) but the real fix is
   confirming A1 flags every action surface as `approval_required`.
2. **G2 gate mismatch.** `chief_acceptance_gate.evaluate_evidence` is shaped for
   *polish-loop task passes* (task_name/pass_num/verdict), not action authorization.
   The action path likely needs a different/authority gate at G2; human G3 remains
   the real authorization. Do not force `evaluate_evidence` in where it doesn't fit.

Safe validation plan (no production writes): copy `compose_contract.py` +
`chief_compose.py` to the PC, run `compose()` with `db_path=/tmp/compose_test.sqlite`
(throwaway ledger), read-only queries first, then one action query — assert it
returns PENDING_APPROVAL with a real packet and never executes.
