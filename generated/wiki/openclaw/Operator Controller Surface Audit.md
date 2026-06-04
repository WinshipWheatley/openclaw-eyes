# Operator Controller Surface Audit

## 1. Executive Summary
Mission Control must evolve from a proof browser and dashboard into a playable Operator Controller. Like a production instrument, it should protect flow state, map discrete gestures to backend scenes/cues, and only reveal deep complexity (the 'monitor path' or 'arrangement view') when explicitly summoned. The backend is the instrument rack; Mission Control is the Ableton Push.

## 2. Controller Analogy Translated
- **Keys**: Chat and prompt input (improvisational input to the LMs).
- **Pads**: Discrete action triggers ('Do it', 'Approve', 'Deny').
- **Knobs**: Context selectors (tuning into a specific lane, client, or trust level).
- **Faders**: Trust ramps / Delegation depth (how far an agent can run before stopping).
- **Transport Controls**: Workflow execution (Pause, Resume, Stop, Hold, Continue).
- **Scene Launcher**: World/Mode switches (Helm, Finance, Build, Business Development, Art).
- **Display**: Dynamic Action Cards (rendering the current state, focus, and read models).
- **Metering**: System health lights, sync status, and Guardian activity.
- **Record-Arm**: Guardian interlocks (gating protected or destructive actions).
- **Monitor Path**: Proof drawer / Reading receipts (inspecting the actual work).
- **Patch Browser**: Tool inventory / Agent roster.
- **Session View**: Helm / current actionability surface (what needs doing right now).
- **Arrangement View**: Ledger / history / operator conversation journal.

## 3. Playable Control Vocabulary
**First-Class Controls:**
- Chat / say goal
- Do it
- Approve
- Deny
- Attach proof
- Stop / cancel / hold
- Switch mode
- Ask why

**Deprioritized or Contextual (handled dynamically):**
- Continue, Show details, Open lane, Stage plan, Review packet, Request rework, Mark informational, Park this, Remember this, Wake this up later, Record evidence.

## 4. Controller Surface Layers
- **Bespoke Mac UI**: Global navigation, persistent metering (system health/sync), and the physical layout of the controller window.
- **Dynamic Card Rendering**: All lane-specific status, question answering, approval requests, and active task tracking. The app should merely render `dynamic_card_packet` without hardcoded knowledge of the business domains.
- **Proof / Developer Mode**: Raw read models, deep execution logs, detailed evidence receipts, and LM reasoning traces.
- **Removed from Operator Mode**: Hardcoded status cards for specific clients, redundant file-system state displays, and un-actionable telemetry.

## 5. Multi-Device Roles
- **Mac (The Studio Workstation)**: Deep monitoring, proof drawer, arrangement view, full file-system integration. High resolution proof, root authority.
- **iPad (The Tabletop Performance Controller)**: Scene launching, pad pushing, visual evidence review (PDFs/images), flow state preservation. High authority (ideal for signing/approving).
- **iPhone (The Remote Transport Control)**: Chat, quick approve/deny, low-res metering, on-the-go capture. Limited authority, summary-level proof.

## 6. Persistent Agents vs Spawned Workers
- **Persistent Characters**: Cassandra (Memory & Comm), Chief (Orchestration & Status), Guardian (Safety & Interlocks), Niles (Music/Art), Clara (Operations). They maintain stable roles, tones, and represent institutional memory.
- **Temporary Workers**: Hermes (Transport), PC_CODEX, MAC_CODEX, and other spawned harnesses.
- **Session Behavior**: Sessions resume via compiled receipts in SQLite, not endless chat context windows. Context follows the thread, not the worker, avoiding false recursive truth.

## 7. First-Class Operator Authority Envelope
When the controller fires an action, it wraps it in an indisputable authority envelope:
```json
{
  "operator_ref": "winship",
  "app_instance_ref": "uuid",
  "device_ref": "mac|ipad|iphone",
  "session_ref": "uuid",
  "request_hash": "sha256",
  "operator_verified": true,
  "input_surface": "chat|pad|card",
  "current_world": "finance",
  "authority_requested": ["ledger_mutation"],
  "authority_granted": ["ledger_mutation"],
  "proof_required": true
}
```

## 8. Dynamic Card Requirements
- **Evolution**: Move beyond `dynamic_card_packet_v0` to ensure the app is a pure renderer.
- **Contents**: Needs `card_id`, `priority`, `headline`, `plain_summary`, `trust_state`, `speaker_ref`, `tone`, actionable deterministic buttons (`actions`), and `proof_drawer_refs`.
- **Eliminated**: Hardcoded UI views for Capital Hilton, St. Annes, etc.

## 9. Evidence Intake as Controller Gesture
- **Gesture**: Like sampling audio: drag-and-drop a file, paste an image, or record a voice note.
- **Process**: Intake -> Classify & Route -> Generate Review Card -> Unlock associated gate (e.g., payment watch resolves to Paid).

## 10. What to Hide / Remove / Deprioritize
- **Hide**: Internal state packages, raw JSON responses, LM token metrics.
- **Remove**: Bespoke Mac UI for specific workflows.
- **Chat Summon Only**: Deep dive analytics, historical logs.
- **Developer Proof Only**: Full LM1/LM2 prompts, SQLite table dumps.

## 11. Human-Language Glossary
- **internal machine term** -> **human UI term**
- package -> Cue / Patch
- gate -> Safety Lock
- worker -> Script / Delegate
- proof -> Receipts
- read model -> Dashboard Data
- receipt -> Record
- authority boundary -> Permission
- capability -> Skill
- deterministic rail -> Routine
- LM2 worker cage -> Sandbox
- dynamic card -> Focus Card
- operator review -> Human Check
- business-action gate -> Final Approval

## 12. The Playability Test
1. Can Winship open the app and know the next move in 5 seconds?
2. Can he attach proof without thinking about files/contracts?
3. Can he approve/deny safely?
4. Can he ask 'what should I do here?' and get a lane-aware answer?
5. Can he stay in creative mode while business work is handled?
6. Can he step into finance/build when he wants?
7. Can he trust that protected actions are locked?
8. Can he find proof without seeing proof all day?

## 13. Recommended Next Build Sequence
1. Implement the generic `dynamic_card_packet` renderer in the Mac App, ripping out hardcoded business domain UIs.
2. Build the 'First-class authority envelope' architecture for secure requests from App to Backend.
3. Implement 'World/Bank' switching in the App, filtering dynamic cards and context by active Mode (Helm, Finance, Build, etc.).
4. Build the 'Pad' execution endpoints (Approve, Deny, Do It, Stop) that map to the authority envelope.
5. Create the universal 'Evidence Intake' dropzone gesture (the 'sampler').

## 14. Risks
- If dynamic cards become too flexible, they become mini-web-pages, recreating the bloat problem. Keep them bounded.
- If World/Bank switching hides too much, critical Guardian alerts might be missed. Guardian alerts must bypass banks.

## 15. Final Recommendation
Commit fully to the Controller metaphor. Treat the backend as a rack of gear. Mission Control is the APC40/Push controller. Make it fast, tactile, and highly bounded. Do not build a dashboard.
