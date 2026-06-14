# Operator Session Timeline

Status: OPERATOR_SESSION_TIMELINE_READY

Operator Session Timeline V0 records the day as summarized scenes/domains, controller events, cards, receipts, evidence, and review decisions. It does not store raw chat dumps.

## Rules

- No raw prompt dumps.
- No secrets.
- No client PII beyond protected refs.
- History is summarized and receipt-backed.
- Resolved cards move to completed/history.
- Timeline does not create business truth.
- Ledger and paid truth remain separate.

## Event Counts

- `session_started`: `1`
- `world_entered`: `0`
- `lane_entered`: `0`
- `controller_event`: `2`
- `dynamic_card_shown`: `8`
- `proof_attached`: `1`
- `evidence_recorded`: `1`
- `approval_requested`: `0`
- `review_decision_recorded`: `1`
- `package_staged`: `0`
- `receipt_recorded`: `0`
- `card_resolved`: `2`
- `session_closed`: `1`

## Timeline

- `2026-05-20T04:07:48+00:00` `dynamic_card_shown` system/check_engine: Controller showed `gate_lock_card` for the current scene.
- `2026-05-26T00:00:00+00:00` `dynamic_card_shown` finance/capital_hilton: Controller showed `current_focus_card` for the current scene.
- `2026-06-01T22:28:55+00:00` `controller_event` finance/capital_hilton: Finance / Capital Hilton `ask_why` returned payment-watch context without execution.
- `2026-06-01T22:28:55+00:00` `dynamic_card_shown` finance/capital_hilton: Controller showed `answer_card` for the current scene.
- `2026-06-01T22:28:55+00:00` `dynamic_card_shown` finance/capital_hilton: Controller showed `payment_watch_card` for the current scene.
- `2026-06-01T22:39:43+00:00` `dynamic_card_shown` business_development/capital_hilton: Controller showed `workflow_composer_plan_card` for the current scene.
- `2026-06-02T21:57:46+00:00` `card_resolved` finance/st_annes: Resolved controller card moved to completed history.
- `2026-06-03T03:48:39+00:00` `review_decision_recorded` build/workroom_review: Workroom review was marked informational and moved to completed history; no merge or push.
- `2026-06-05T02:06:39Z` `dynamic_card_shown` controller/safe_next: Controller showed `contextual_what_should_i_do_card` for the current scene.
- `2026-06-05T04:07:25+00:00` `controller_event` finance/capital_hilton: Finance / Capital Hilton `ask_why` returned payment-watch context without execution.
- `2026-06-05T17:38:57+00:00` `card_resolved` build/review_packet: Resolved controller card moved to completed history.
- `2026-06-05T17:38:57+00:00` `dynamic_card_shown` build/review_packet: Controller showed `review_packet_card` for the current scene.
- `2026-06-05T18:44:27+00:00` `dynamic_card_shown` finance/live_arts_md: Controller showed `evidence_intake_receipt_card` for the current scene.
- `2026-06-05T18:44:27+00:00` `evidence_recorded` finance/live_arts_md: Evidence candidate recorded; paid and ledger truth were not inferred.
- `2026-06-05T18:44:27+00:00` `proof_attached` finance/live_arts_md: Proof was attached as protected local evidence metadata for a finance lane.
- `2026-06-05T20:00:00+00:00` `session_closed` system/session: Operator session timeline closed as summarized history.
- `2026-06-05T20:00:00+00:00` `session_started` system/session: Operator session timeline started for PC Mission Control handoff.

## Proof

- SQLite: `/home/openclaw/worktrees/pc3-bd-readmodels/generated/system_knowledge/operator_session_timeline.sqlite`
- JSON events: `17`
- SQLite rows: `17`
- Unsafe true grants absent: `true`
