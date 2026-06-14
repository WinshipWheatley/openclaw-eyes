# Operator Controller Design Brief

Status: `OPERATOR_CONTROLLER_DESIGN_BRIEF_READY`

This is the canonical build brief for Mission Control and the OpenClaw controller protocol. It synthesizes the controller grammar, runtime fit, dynamic-card, envelope, action payload, WIP, gate, lifecycle, and evidence audits into one build spec.

## Doctrine

- Cards cost attention.
- Controller is 95 percent control and 5 percent status.
- Proof is metering and detail drawer, not primary UI.
- LM output is not truth.
- Receipts, read models, and proof refs define truth.
- The app is a controller shell, not the brain.
- Incoming `authority_requested` is only a request. Incoming `authority_granted` is ignored or rejected. `authority_granted` is backend-only.
- Approvals, plans, generated summaries, and staged packages do not equal execution proof.

## Controller Shell

Mission Control is a thin operator shell. It owns the window, world/bank switcher, Composer input, generic card renderer, safe action dispatcher, verified controller-envelope creation, evidence drop zone, proof/details drawer, compact meters, local/offline/bridge status, accessibility, and view preferences.

The backend owns workflow-specific copy, lane interpretation, trust/freshness labels, lifecycle and visibility decisions, proof refs, receipts, safe action payload refs, gate state, and source hashes.

The Mac app must not own workflow truth, protected action policy, client-specific status copy, or proof inference. It renders what the backend packet says and dispatches only verified controller events.

## Controller Events

Every mutating event requires `envelope_id`, `operator_ref`, `app_instance_ref`, `device_ref`, `device_class`, `session_ref`, `request_hash`, `created_at`, `input_surface`, `current_world_ref`, `current_thread_ref`, `operator_verified`, `app_instance_verified`, `device_verified`, `session_verified`, and `verification_status`.

Backend-only fields are `authority_granted`, `gate_decision_ref`, and `approval_receipt_ref`.

First-class event types:

- `chat_goal`: express a goal or contextual question.
- `do_it`: run or continue a staged safe local action.
- `approve`: record an approval or review verdict.
- `deny`: reject a pending gate, approval, or review packet.
- `attach_proof`: record local candidate evidence or attach an artifact to a lane.
- `ask_why`: explain a gate, card, status, or provider choice from existing proof.
- `open_lane`: navigate to a world, thread, lane, or object.
- `stage_plan`: stage a workflow plan without running it.
- `continue`: continue a paused safe local flow.
- `request_rework`: return a review packet to staging with comments.
- `mark_informational`: acknowledge and archive as informational.
- `stop_hold_cancel`: pause a lane, cancel staged work, or revoke pending approval state.
- `show_details`: open the proof/details drawer.

No controller event may directly perform email send, Gmail access, browser access, Coupa access, portal submit, ledger posting/mutation, workbook mutation, PDF export, paid marking, merge, push, worker spawn, or external-provider calls.

## Dynamic Card V1

`dynamic_card_packet_v1` is backend-authored and rendered by generic app components. The Mac must not switch behavior on client-specific card ids.

Required packet fields: `schema_version`, `packet_id`, `generated_at`, `surface_context`, `source_request_id`, `packet_source_read_model_refs`, `packet_content_hash`, and `cards`.

Required card fields include `card_id`, `card_family`, `card_type`, world/thread/lane/workflow/object refs, headline, plain summary, supporting lines, status label, trust state, confidence class/score, freshness state, lifecycle state, visibility fields, source refs, source timestamps/hashes, action slots, proof object, accessibility text, and device render hints.

Action slots are `primary`, `secondary`, `detail`, `dismiss`, and `danger_disabled`. Each action carries `action_payload_ref`, `controller_event_type`, label, enabled state, disabled reason, `requires_operator_envelope`, `receipt_required`, authority boundary, and proof refs.

Generic card families:

- `current_focus_card`
- `answer_card`
- `payment_watch_card`
- `evidence_intake_receipt_card`
- `approval_request_card`
- `review_packet_card`
- `workflow_composer_plan_card`
- `gate_lock_card`
- `memory_candidate_card`
- `artifact_proof_card`
- `contextual_what_should_i_do_card`
- `completed_historical_receipt_card`

## Proof Meters

Proof meters are compact controller indicators. They translate backend proof into readable labels and open the details drawer when needed. They must never become primary UI.

| Meter | Human labels | Backend fields/read models | Shown | Hidden | Opens details | Must never imply |
|---|---|---|---|---|---|---|
| Truth meter | Receipt-backed, Artifact hash, Trusted current, Operator-reported, Candidate evidence, Generated summary, Inferred, Needs verification, Test-only, Rejected, Unknown | `trust_state`, `confidence_class`, `confidence_score`, `proof.receipt_refs`, `proof.hash_refs`, `evidence_confidence_scoring.json`, `evidence_intake_status.json`, `gate_decision_ledger.json` | Factual finance, evidence, approval, gate, review, memory, and status cards | Pure navigation, empty composer state, cards without factual claims | Non-receipt/non-hash labels, finance/payment/gate cards, or click | LM output is truth, paid/sent state, provider action, execution proof |
| Freshness meter | Current, Waiting external, Needs verification, Superseded, Historical, Unknown | `freshness_state`, `lifecycle_state`, `source_generated_at`, `source_content_hash`, `stale_after`, `expires_at`, `replacement_card_ref`, `superseded_by_card_ref`, `resolved_by_receipt_ref`, `dynamic_card_lifecycle_policy.json` | Active, waiting, needs_operator, stale, payment-watch, and timestamped cards | Timeless shell controls and collapsed history | Needs verification, superseded, historical, unknown, or source hash/timestamp changes | External systems were checked or stale read models override newer receipts |
| Authority meter | Verified control, Approval required, Blocked gate, No grant, Needs verification, Rejected | Controller envelope verification fields, action-slot authority boundaries, `requires_operator_envelope`, `receipt_required`, `operator_controller_protocol.json`, `first_class_operator_envelope_status.json`, `gate_decision_ledger.json` | Enabled mutating controls, disabled protected controls, approval/review cards, gate locks, stop/hold controls | Read-only text, passive history, meter-only surfaces | Disabled actions, approval required, missing verification, blocked gates | Authority came from the app, an LM, request text, or identity alone |
| Evidence meter | Receipt present, Artifact hash present, Candidate evidence, Operator-reported, No evidence, Test-only, Rejected | `proof.artifact_refs`, `proof.receipt_refs`, `proof.hash_refs`, `proof.redacted_summary`, `proof.sensitive_detail_policy`, `evidence_intake_status.json`, `evidence_confidence_scoring.json`, `artifact_lineage_registry.json` | Payment watch, evidence intake, artifact proof, review packet, memory candidate, business-object cards | Ordinary navigation and developer-metadata-only proof | Candidate, test-only, rejected, no evidence, or raw detail available | Raw sensitive detail is safe, candidate proof is verified truth, paid/sent/ledger state changed |
| Sync meter | Bridge synced, Local only, Bridge stale, Needs mount, Mismatch, Unknown | Local/bridge artifact paths, parse status, content hashes, bridge equality, `operator_runtime_chain_current_state_audit.json#validation_expectations`, `sync_health.json` | Multi-device, bridge-dependent, or handoff-sensitive packets | Local-only controls and cards without bridge dependency | Hash mismatch, bridge parse failure, absent mount, local-only source | External-system sync, email delivery, ledger posting, Coupa/Gmail/browser access, workbook mutation |
| Risk meter | Calm, Watch, Pileup risk, Blocked, Protected, Unknown | `attention_cost`, `visibility_reason`, disabled reasons, `proof.unsafe_scan_result`, validation commands, authority boundary, `workroom_wip_limits.json`, `gate_decision_ledger.json`, `operator_action_payloads.json` | Blocked gates, WIP bottlenecks, approvals, review packets, protected disabled actions, unsafe scans, pileup warnings | Calm current-focus cards without protected actions | Blocked, Protected, Pileup risk, Unknown, failed validation, unsafe scan output | Real-world severity beyond proof or protected action safety from calm UI copy |

## Lifecycle Rules

- Active and needs_operator cards show by default only when they provide the next playable control.
- Resolved cards hide by default after a receipt is recorded.
- Historical cards collapse under Completed / History.
- Stale cards must display Needs verification and name `stale_reason`.
- Proof-only cards are hidden unless requested through details.
- Workroom cards show only when operator decision is required.
- Finance payment-watch cards stay visible only while payment evidence is missing.
- Payment-processing evidence becomes waiting evidence, not paid truth.
- No card remains primary when a newer receipt or replacement card supersedes it.
- Machine-contract cards stay hidden in operator mode.
- WIP/watch metrics are meters unless they require a concrete decision.

## Device Roles

Mac is the primary Mission Control controller. It renders full cards, creates verified envelopes, dispatches safe controller events, accepts local evidence, shows compact meters, and owns bridge/offline status.

iPad is the review and pad controller. It supports touch review, pad input, lane navigation, proof summaries, and approval/rework/informational controls when verification passes. Developer proof and raw sensitive details stay hidden by default.

iPhone is the interrupt and triage controller. It supports current-focus alerts, stop/hold, ask why, open lane, small proof meters, and minimal approval visibility under strong verification. It should not handle complex review editing or bulk proof browsing.

## Mac Bespoke Boundary

Mac keeps bespoke: app shell, window layout, world/bank switcher, lane navigation state, Composer input, generic card renderer, safe dispatcher, controller-envelope creation, evidence drop zone, file picker, local preview, proof drawer, compact meters, offline/bridge status, accessibility, keyboard focus, and view preferences.

Mac converts to dynamic cards: Capital Hilton payment watch, Capital Hilton proposal follow-up, Live Arts MD evidence receipt, St. Anne's work-log review, workroom review packets, approval/protected gate cards, contextual what-should-I-do answers, workflow composer plan previews, memory candidate reviews, and completed receipt/history rows.

## Developer Proof

Developer Proof is hidden by default and opened through `show_details` or proof-meter clicks. It contains proof refs, read-model refs, receipt refs, artifact refs, hashes, SQLite refs, raw request/response refs, source content hashes, validation commands, unsafe scan results, sensitive detail policy, redacted summaries, machine-contract cards, raw proof cards, generated summary-only proof, test-only evidence, non-current gate ledger rows, and WIP/watch metrics without a needed decision.

## Next Build Sequence

1. Freeze existing request-response, workflow-package, system-question, workroom-review, and workbook-registration behavior with focused regression tests.
2. Add `dynamic_card_packet_v1` as an additive backend field beside existing `visible_cards` and `operator_display`.
3. Populate v1 packets first for system-question, workflow-package, workroom-review, workbook-registration, gate, and evidence-intake rails.
4. Render one Mac pane exclusively through the generic renderer while preserving v0 compatibility.
5. Implement proof meters from backend fields and route all meter clicks to the proof/details drawer.
6. Add bridge equality, JSON parse, unsafe true-grant, and Mac-render smoke validation.
7. Move approval, gate, workflow composer, memory candidate, and historical receipt surfaces into backend dynamic cards.
8. Unify proof/details drawer around categorized proof fields.
9. Retire Mac workflow-specific card code after parity screenshots and controller-event smoke tests.
10. Only after dynamic cards are stable, define a universal receipt envelope shared by package, approval, review, and future worker rails.

## Hold

Do not build live LM1, real LM2 worker cage runtime, live business-action executor gate, universal approval-to-execution bridge, manual switch-mode override, manual remember-this truth promotion, or unattended wake-this-up-later scheduling yet.

## Safety

This brief is generated/read-model/wiki work only. It does not implement runtime code, mutate ledgers or workbooks, send email, open browser/Gmail/Coupa, export PDFs, mark paid, submit anything, push, spawn workers, invoke external LMs, or grant authority.
