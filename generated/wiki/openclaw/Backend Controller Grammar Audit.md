# Backend Controller Grammar Audit: Operator Controller Surface for Winship

## 1. Executive Summary

This document presents the **PC AGY Backend Controller Grammar Audit**, which defines the structural controller primitives Mission Control should use to "play" OpenClaw.

Mission Control is not a dashboard; it is an **Operator Controller Surface**. Under this paradigm:
* The **Backend** is the instrument rack/brain.
* **Mission Control** is the physical surface/controller.
* **Language Models (LMs)** are players, interpreters, and workers.
* **Packages** represent cues/patches.
* **Receipts** serve as the session log/tape.
* **Guardian** is the safety interlock (record-arm).
* **Proof** is the metering/signal path (not the performance).

The controller is built entirely around generic playable primitives (like dynamic cards and explicit control signals) rather than custom views for each client workflow.

---

## 2. Controller Grammar

The controller grammar aligns backend schemas directly to UI elements. By structuring interactions around a deterministic set of event envelopes, the backend drives the UI layout dynamically.

### Core Protocol Principles
* **Separation of Authority**: The client UI only requests action (`authority_requested`); the backend evaluates preconditions and records actual status (`authority_granted`). The UI never invents or grants execution authority.
* **Generic Card Representation**: A single Dynamic Card schema represents all state, review packets, gate decisions, and proof links.
* **Context Preservation**: Every controller event envelope must include the active `current_world_ref`, `current_thread_ref`, and `operator_ref` to bind actions to their respective lanes.

---

## 3. First-Class Controls

First-class controls represent the primary, universal physical interactions Winship uses to operate lanes.

### 1. Chat / say goal (`chat_goal`)
* **Purpose**: Set or adjust the high-level intent/direction of a lane or request a composer plan.
* **When Visible**: Always visible in the main chat/input panel.
* **Required Envelope Fields**: `envelope_id`, `operator_ref`, `app_instance_ref`, `device_ref`, `device_class`, `session_ref`, `request_hash`, `created_at`, `input_surface`, `current_world_ref`, `current_thread_ref`.
* **Required Backend Route**: `openclaw_request_processor.contextual_goal_or_workflow_composer`
* **Required Proof/Receipt**: None.
* **Allowed Payload Types**: `system_question`, `stage_package_request`, `navigate`.
* **Forbidden Payload Types**: All protected business execution actions.
* **Example Use**: `operator_controller_envelope` contains `chat_goal` "Get St. Anne's monthly invoice ready".
* **Current Backend Support**: **Ready**. Supported by request routing and system question rails.
* **Mac App Implication**: Tied directly to the primary chat input area.

### 2. Do it (`do_it`)
* **Purpose**: Authorize execution of a safe, local staged routine (e.g. running a dry run).
* **When Visible**: On a dynamic card when a safe local action is staged and awaits trigger.
* **Required Envelope Fields**: Standard fields + target package/run reference.
* **Required Backend Route**: `operator_action_payload_gate.contextual_safe_action`
* **Required Proof/Receipt**: Yes (writes a session receipt and updates state models).
* **Allowed Payload Types**: `system_question`, `stage_package_request`, `navigate`.
* **Forbidden Payload Types**: Protected business mutations (`email_send`, `coupa_access`, etc.).
* **Example Use**: Operator clicks "Do it" to execute a local invoice-pickup validation check.
* **Current Backend Support**: **Partial**. Backend handles routing, but active executor is dry-run only.
* **Mac App Implication**: Primary action button on active draft/staged cards.

### 3. Approve (`approve`)
* **Purpose**: Authorize a pending gate request or record operator review verification.
* **When Visible**: On approval or review packet cards.
* **Required Envelope Fields**: Standard fields + `active_entity_ref` (the approval or packet ID).
* **Required Backend Route**: `workroom_review_decision_or_guardian_approval_queue`
* **Required Proof/Receipt**: Yes (approval receipt reference recorded).
* **Allowed Payload Types**: `review_decision`, `explain_gate`.
* **Forbidden Payload Types**: Direct execution payloads (only signs approval, execution is gated separately).
* **Example Use**: Operator clicks "Approve" on a draft invoice review packet.
* **Current Backend Support**: **Ready**. Supported by `workroom_review_decision_consumer.py`.
* **Mac App Implication**: Green/success action button on review and gate cards.

### 4. Deny (`deny`)
* **Purpose**: Reject a pending gate or review request, halting the flow.
* **When Visible**: On approval or review packet cards.
* **Required Envelope Fields**: Standard fields + `active_entity_ref`.
* **Required Backend Route**: `workroom_review_decision_or_approval_request_queue`
* **Required Proof/Receipt**: Yes (writes a rejection receipt).
* **Allowed Payload Types**: `review_decision`, `explain_gate`.
* **Forbidden Payload Types**: Execution actions.
* **Example Use**: Operator rejects a Coupa submit request due to billing discrepancy.
* **Current Backend Support**: **Ready**.
* **Mac App Implication**: Red/destructive button that resets status to cancelled/rejected.

### 5. Ask why (`ask_why`)
* **Purpose**: Request an explanation of why a gate blocked or a provider class was selected.
* **When Visible**: On cards containing warning tones or blocked actions.
* **Required Envelope Fields**: Standard fields + target reference.
* **Required Backend Route**: `system_question_answer.contextual_answer`
* **Required Proof/Receipt**: None (read-only query).
* **Allowed Payload Types**: `system_question`, `inspect_proof`.
* **Forbidden Payload Types**: All mutations.
* **Example Use**: Clicking "Ask why" next to a blocked ledger-posting action.
* **Current Backend Support**: **Ready**. Supported by system question answer citing gate decision ledgers.
* **Mac App Implication**: Question icon or link that opens a popover showing the system's reasoning.

### 6. Attach proof (`attach_proof`)
* **Purpose**: Upload or link an external artifact (e.g. receipt PDF) to satisfy an evidence gate.
* **When Visible**: On cards requesting evidence, or inside the dropzone/proof drawer.
* **Required Envelope Fields**: Standard fields + target lane reference + uploaded file path.
* **Required Backend Route**: `evidence_intake.record_candidate_evidence`
* **Required Proof/Receipt**: Yes (writes a `protected_evidence_reference_receipt`).
* **Allowed Payload Types**: `record_payment_proof_intake`, `inspect_proof`.
* **Forbidden Payload Types**: Execution actions.
* **Example Use**: Dragging a payment screenshot into the dropzone to satisfy a ledger gate.
* **Current Backend Support**: **Ready**. Supported by `evidence_intake.py`.
* **Mac App Implication**: Tied directly to drag-and-drop areas and file selectors.

### 7. Open lane (`open_lane`)
* **Purpose**: Change UI focus to a specific thread, world, or lane.
* **When Visible**: On navigation cards, thread indexes, or chat redirects.
* **Required Envelope Fields**: Standard fields + target world and thread references.
* **Required Backend Route**: Local UI navigation (`operator_action_payloads.navigate`).
* **Required Proof/Receipt**: None (UI state only).
* **Allowed Payload Types**: `navigate`.
* **Forbidden Payload Types**: Mutations.
* **Example Use**: Clicking a link in the thread index to view "finance/st_annes".
* **Current Backend Support**: **Ready**. Supported by the finance thread index routing.
* **Mac App Implication**: Switches active sidebar filters.

### 8. Stage plan (`stage_plan`)
* **Purpose**: Compile and stage a proposed composer plan to the package queue.
* **When Visible**: On planning or composer cards after a draft has been generated.
* **Required Envelope Fields**: Standard fields + plan reference.
* **Required Backend Route**: `workflow_composer_or_workflow_package_request_consumer.stage_only`
* **Required Proof/Receipt**: Yes (writes staged package rows in SQLite).
* **Allowed Payload Types**: `stage_package_request`.
* **Forbidden Payload Types**: Direct executions.
* **Example Use**: Staging the weekly St. Anne's rollup plan.
* **Current Backend Support**: **Ready**. Supported by workflow package stagers.
* **Mac App Implication**: Button that registers the plan in the backend registry queue.

### 9. Continue (`continue`)
* **Purpose**: Acknowledge a non-critical warning and resume a paused local pipeline.
* **When Visible**: On status cards that have paused on a warning flag but remain safe to run.
* **Required Envelope Fields**: Standard fields + package run reference.
* **Required Backend Route**: `operator_action_payload_gate.continue_safe_local_flow`
* **Required Proof/Receipt**: Yes (updates status read model).
* **Allowed Payload Types**: `system_question`, `stage_package_request`, `navigate`.
* **Forbidden Payload Types**: Gated mutations.
* **Example Use**: Operator resumes Hilton invoice delivery after acknowledging a minor layout shift warning.
* **Current Backend Support**: **Partial**. (Dry-run status is updated, but execution resumption is missing).
* **Mac App Implication**: "Continue" button on warned/paused cards.

### 10. Request rework (`request_rework`)
* **Purpose**: Reject a review packet and send it back to compiler/stager stage with comments.
* **When Visible**: On active workroom review cards.
* **Required Envelope Fields**: Standard fields + packet reference + operator comments.
* **Required Backend Route**: `workroom_review_decision_consumer.request_rework`
* **Required Proof/Receipt**: Yes (writes a rework decision receipt).
* **Allowed Payload Types**: `review_decision`.
* **Forbidden Payload Types**: Execution actions.
* **Example Use**: Requesting rework on an invoice draft because billing amounts are mismatching.
* **Current Backend Support**: **Ready**. Supported by review decision stubs.
* **Mac App Implication**: Triggers a comments field and changes card status to "needs rework".

### 11. Mark informational (`mark_informational`)
* **Purpose**: Dismiss/archive a card that requires no execution or approval.
* **When Visible**: On active review packets or notifications.
* **Required Envelope Fields**: Standard fields + target reference.
* **Required Backend Route**: `workroom_review_decision_consumer.mark_informational`
* **Required Proof/Receipt**: Yes (writes an informational receipt).
* **Allowed Payload Types**: `review_decision`.
* **Forbidden Payload Types**: Execution actions.
* **Example Use**: Operator acknowledges a system-check diagnostic report.
* **Current Backend Support**: **Ready**.
* **Mac App Implication**: Archives the card from the primary workspace view.

### 12. Stop / hold (`stop_hold_cancel`)
* **Purpose**: Immediately freeze all progress in a lane or revoke a pending approval.
* **When Visible**: Always visible on active runs, gates, or pending approvals.
* **Required Envelope Fields**: Standard fields + target reference.
* **Required Backend Route**: `approval_request_queue_or_workroom_review_decision_consumer.stop_hold_cancel`
* **Required Proof/Receipt**: Yes (logs cancellation state and holds queue rows).
* **Allowed Payload Types**: `review_decision`, `explain_gate`.
* **Forbidden Payload Types**: Execution actions.
* **Example Use**: Freezing the Capital Hilton invoice lane after a customer change request.
* **Current Backend Support**: **Ready**.
* **Mac App Implication**: Red cancellation button on cards or lane headers.

### 13. Show details (`show_details`)
* **Purpose**: Expand/collapse developer proof, logs, and receipt hashes.
* **When Visible**: On any card containing a `proof_refs` list.
* **Required Envelope Fields**: Standard fields + card reference.
* **Required Backend Route**: `dynamic_card_packet.proof_drawer` (or local UI toggle if cached).
* **Required Proof/Receipt**: None.
* **Allowed Payload Types**: `inspect_proof`, `none`.
* **Forbidden Payload Types**: Execution actions.
* **Example Use**: Operator reveals the SHA256 hashes of a generated PDF.
* **Current Backend Support**: **Ready**. Backend embeds `proof_refs` directly.
* **Mac App Implication**: Disclosure triangle on card details.

---

## 4. Secondary Controls

Secondary controls are contextual and appear only when specific data conditions are met:
1. **Workbook Registration** (`workbook_registration` action)
   * *Purpose*: Register a newly detected invoice workbook in the registry.
   * *Visibility*: When a new workbook spreadsheet appears in the inbox.
   * *Route*: `client_invoice_workbook_registry.register_workbook`
2. **Work Log Review Actions** (`confirm_st_annes_work_log_event`, `discard...`, `mark_as_test...`, `edit...`)
   * *Purpose*: Refine individual time entry facts.
   * *Visibility*: On St. Anne's work-log review cards.
   * *Route*: `st_annes_work_log_review_surface.json` (writes to `st_annes_monthly_work_log.sqlite`).

### Controls That Should NOT Exist Yet
> [!WARNING]
> To preserve the safety interlock, the following controls must remain out-of-scope:
> * **Switch mode**: Manually forcing a lane to graduate to unattended mode is blocked. Graduation is backend-only based on pre-conditions.
> * **Remember this**: Long-term memory promotion must bypass manual operator button clicks to prevent recursive hallucinations from polluting core registries.
> * **Wake this up later**: Postponing/delaying task execution belongs in queue timers, not manual operator scheduler overrides.
> * **Direct execution buttons** (e.g. "Send Email Now", "Post Ledger"): The UI must only approve/deny a staged *intent*; actual execution is driven by backend agents under separate interlocks.

---

## 5. Zoom / Delegation / Proof Knobs

Knobs are parameter switches that customize how Winship interacts with the OpenClaw board.

* **Zoom Level**: Focuses the operator on the appropriate context density:
  * `moment`: Focuses on a single verification preflight card.
  * `task`: Focuses on a single package run (e.g., St. Anne's rollup).
  * `lane`: Focuses on a specific lane feed (e.g., `finance/capital_hilton`).
  * `world`: Filters card feed to a specific world (e.g., `finance`).
  * `system`: Displays global picture (WIP limits, diagnostics, cutovers).
* **Delegation Depth**: Sets how far the system executes before stopping for operator validation:
  * `readback`: Bounded read-only reporting; all actions are manual.
  * `plan`: Stops at composer plans.
  * `stage`: Compiles and queues packages in the registry.
  * `safe_work`: Automatically runs local dry runs and gathers proof.
  * `prepare_approval`: stages work, runs dry runs, and queues approval gates.
  * `execute_after_approval`: Automatically executes actions upon approval (Blocked).
* **Proof Depth**: Sets details shown:
  * `none`: Headline only; hides developer references.
  * `summary`: Bulleted descriptions and next safe actions.
  * `receipts`: SHA256 hashes, file path references, and logs.
  * `full_developer_proof`: raw JSON read models, databases, and schemas.
* **Urgency**: `park` | `normal` | `today` | `urgent` (manages queue execution priority).
* **Mode**: Filters card feeds by role: `artist` | `finance` | `build` | `business` | `creative` | `system`.

---

## 6. Backend Support Matrix

| Control | Status | Supporting Contract | Remaining Gaps |
|---|---|---|---|
| **Chat / say goal** | Ready | `operator_controller_protocol.json` | Bounded file pickup, not an active WebSocket chat event bus. |
| **Do it** | Partial | `operator_action_payloads.json` | Validates payloads but lacks live execution capability. |
| **Approve** | Ready | `workroom_review_decision_status.json` | None. |
| **Deny** | Ready | `workroom_review_decision_status.json` | Resets status but lacks a unified rollback state machine. |
| **Ask why** | Ready | `system_question_answer_contract.json` | Reasoning is lane-specific. |
| **Attach proof** | Ready | `evidence_intake_status.json` | Local file paths only; no active banking API verification. |
| **Open lane** | Ready | `finance_thread_index.json` | None. |
| **Stage plan** | Ready | `workflow_package_queue_contract.json` | Staging is manual; composer plans do not auto-inject into the queue. |
| **Continue** | Partial | `operator_controller_protocol.json` | Lacks pipeline resumption capability. |
| **Request rework** | Ready | `workroom_review_decision_status.json` | Rework is logged; compiler re-run must be triggered manually. |
| **Mark informational** | Ready | `workroom_review_decision_status.json` | None. |
| **Stop / hold** | Ready | `approval_request_queue.json` | Logs hold state; lacks process-kill signals for running scripts. |
| **Show details** | Ready | `dynamic_card_packet_latest.json` | None. |

---

## 7. Missing Backend Contracts

To enable this controller grammar fully, the following contracts need implementation:
1. **Universal Card Packet Outlet** (`dynamic_card_packet_latest.json`): A unified file output consolidating status, gates, reviews, and logs.
2. **Unified Receipt Schema**: A single schema mapping approval queue items, review decisions, and evidence intake metadata to a uniform ledger receipt format.
3. **Knob Filtering Contract**: Backend-side logic that prunes the card lists in the Dynamic Card Packet based on the operator's current zoom, proof depth, and mode.

---

## 8. Mac Implications

> [!TIP]
> Introducing this grammar allows the Mac app to be stripped of layout hardcoding.

* **SwiftUI Hardcoding**: The Mac app can remove custom views for Hilton invoices, St. Anne's work logs, and diagnostic pages.
* **Layout Mapping**: The app can use a generic `DynamicCardComponent` that renders headlines, summaries, bullets, and standard controls dynamically.
* **Local Policy**: Action button enablement logic can be stripped from the client; the backend drives button states and reasons.
* **Proof Heuristics**: The app no longer guesses which files to link; the backend lists them in `proof_refs` and `receipt_refs`.

---

## 9. Risks

* **Operator Alert Fatigue**: If the delegation depth is too shallow or proof depth is set to developer mode by default, the interface will overwhelm the operator.
* **Recursive Hallucinations**: If plans, planner recommendations, or chat summaries are displayed as ground-truth facts, LMs could feed on their own outputs and bypass evidence requirements.
* **Gate Circumvention**: The app might render action buttons before confirming that device, session, and operator verification status checks are complete.

---

## 10. Recommended Next Implementation Sequence

1. **Regression Freeze**: Freeze current request-response, system question, review, and workbook stagers with strict regression tests.
2. **Dynamic Card Packet Outlet**: Add `dynamic_card_packet` as an additive field in backend response structures without breaking the legacy fields.
3. **Port Local Rails**: Modify the four active rails to populate the new dynamic card structures.
4. **Bridge and Smoke Testing**: Perform bridge comparisons to verify card rendering parity before upgrading client code.
5. **Receipt Hardening**: Unify receipt structures before exposing active execution or provider gates.
