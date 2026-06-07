# Dynamic Card Packet

Status: `DYNAMIC_CARD_PACKET_READY`

The Dynamic Card Packet is the backend-generated operator card surface for Mission Control. It lets the Mac render current answers, status, safe next actions, proof drawers, trust state, and safe buttons without custom SwiftUI for every workflow.

`dynamic_card_packet_v1` is a controller-grade packet: the Mac renders card families and action slots, not workflow-specific card ids.

## Boundary

- No live LM1 or LM2.
- No worker spawn or child-agent run.
- No external LLM or local model runtime.
- No email, Gmail, browser, Coupa, ledger, workbook, PDF, submit, mark-paid, merge, push, or repair authority.
- Enabled actions only reference deterministic `operator_action_payloads.json` payloads.
- Proof/details are collapsed by default.
- Incoming `authority_granted` is rejected or ignored; cards never grant authority.
- Payment-processing evidence never marks paid or mutates the ledger.

## Cards

### Stay on payment watch

- Card id: `dynamic_card.finance.capital_hilton.payment_watch`
- Family: `payment_watch_card`
- Type: `payment_watch`
- Speaker: `chief`
- Trust: `trusted_current`
- Freshness: `current`
- Lifecycle: `active`
- Confidence: `trusted_current` / `0.86`
- Summary: Coupa is processing. Wait for payment evidence before anything touches the ledger.
- Next/status: `Payment watch`
- Visible by default: `true`

Action slots:
- `primary`: `ask_why` / `Ask why` / enabled=`true`
- `secondary`: `advance_objective` / `Advance payment watch` / enabled=`true`
- `detail`: `attach_proof` / `Attach payment evidence` / enabled=`true`
- `dismiss`: `show_details` / `Dismiss` / enabled=`false`
- `danger_disabled`: `do_it` / `Submit in Coupa` / enabled=`false`

Proof categories:
- receipts=`4` artifacts=`3` hashes=`0` sqlite=`0` read_models=`3`

### Payment proof received

- Card id: `dynamic_card.finance.live_arts_md.evidence_intake.payment_processing`
- Family: `evidence_intake_receipt_card`
- Type: `evidence_intake`
- Speaker: `chief`
- Trust: `operator_reported`
- Freshness: `waiting_on_external`
- Lifecycle: `waiting`
- Confidence: `operator_reported` / `0.56`
- Summary: This appears to show payment processing for invoice 2026-1001. Ledger remains untouched until payment is confirmed.
- Next/status: `Processing evidence`
- Visible by default: `true`

Action slots:
- `primary`: `attach_proof` / `Attach to lane` / enabled=`false`
- `secondary`: `ask_why` / `Ask what this means` / enabled=`false`
- `detail`: `mark_informational` / `Mark as test` / enabled=`false`
- `dismiss`: `show_details` / `Dismiss` / enabled=`false`
- `danger_disabled`: `do_it` / `Mark paid` / enabled=`false`

Proof categories:
- receipts=`0` artifacts=`2` hashes=`0` sqlite=`1` read_models=`1`

### Stay on payment watch

- Card id: `dynamic_card.finance.capital_hilton.contextual_question`
- Family: `answer_card`
- Type: `answer`
- Speaker: `chief`
- Trust: `trusted_current`
- Freshness: `current`
- Lifecycle: `active`
- Confidence: `trusted_current` / `0.86`
- Summary: Coupa is processing. Wait for payment evidence before anything touches the ledger.
- Next/status: `Answer ready`
- Visible by default: `true`

Action slots:
- `primary`: `open_lane` / `Open Finance / Capital Hilton` / enabled=`true`
- `secondary`: `show_details` / `No secondary action` / enabled=`false`
- `detail`: `show_details` / `Show details` / enabled=`false`
- `dismiss`: `show_details` / `Dismiss` / enabled=`false`
- `danger_disabled`: `do_it` / `Protected action unavailable` / enabled=`false`

Proof categories:
- receipts=`0` artifacts=`0` hashes=`0` sqlite=`0` read_models=`3`

### Review packet needs local decision

- Card id: `dynamic_card.build.review_packet.current`
- Family: `review_packet_card`
- Type: `review_packet`
- Speaker: `chief`
- Trust: `preview_only`
- Freshness: `current`
- Lifecycle: `needs_operator`
- Confidence: `generated_summary` / `0.38`
- Summary: PC_CODEX changed backend code and returned local validation proof for operator review.
- Next/status: `REVIEW_PACKET_READY`
- Visible by default: `true`

Action slots:
- `primary`: `approve` / `Approve for record` / enabled=`true`
- `secondary`: `request_rework` / `Request rework` / enabled=`true`
- `detail`: `mark_informational` / `Mark informational` / enabled=`true`
- `dismiss`: `show_details` / `Dismiss` / enabled=`false`
- `danger_disabled`: `do_it` / `Merge or push` / enabled=`false`

Proof categories:
- receipts=`0` artifacts=`0` hashes=`0` sqlite=`0` read_models=`3`

### Proposal follow-up is review-only

- Card id: `dynamic_card.business_development.capital_hilton.proposal`
- Family: `workflow_composer_plan_card`
- Type: `status`
- Speaker: `cassandra`
- Trust: `trusted_current`
- Freshness: `current`
- Lifecycle: `active`
- Confidence: `trusted_current` / `0.86`
- Summary: Capital Hilton proposal context is business development. Draft or stage a follow-up only for review; do not send.
- Next/status: `Proposal status`
- Visible by default: `true`

Action slots:
- `primary`: `do_it` / `Stage proposal follow-up` / enabled=`true`
- `secondary`: `show_details` / `No secondary action` / enabled=`false`
- `detail`: `show_details` / `Show details` / enabled=`false`
- `dismiss`: `show_details` / `Dismiss` / enabled=`false`
- `danger_disabled`: `do_it` / `Send follow-up` / enabled=`false`

Proof categories:
- receipts=`2` artifacts=`2` hashes=`0` sqlite=`0` read_models=`1`

### Chief diagnostic only

- Card id: `dynamic_card.system.check_engine.diagnostic`
- Family: `gate_lock_card`
- Type: `status`
- Speaker: `chief`
- Trust: `preview_only`
- Freshness: `current`
- Lifecycle: `active`
- Confidence: `generated_summary` / `0.38`
- Summary: Open the Check Engine diagnostic or ask Chief; no repair authority is granted.
- Next/status: `Diagnostic`
- Visible by default: `true`

Action slots:
- `primary`: `open_lane` / `Open Chief diagnostic` / enabled=`true`
- `secondary`: `ask_why` / `What is the difference between Chief and a spawned worker?` / enabled=`true`
- `detail`: `show_details` / `Show details` / enabled=`false`
- `dismiss`: `show_details` / `Dismiss` / enabled=`false`
- `danger_disabled`: `do_it` / `Run repair` / enabled=`false`

Proof categories:
- receipts=`0` artifacts=`0` hashes=`0` sqlite=`0` read_models=`2`

### Workbook reference can be registered

- Card id: `dynamic_card.finance.capital_hilton.workbook_registration`
- Family: `current_focus_card`
- Type: `workbook_registration`
- Speaker: `chief`
- Trust: `trusted_current`
- Freshness: `current`
- Lifecycle: `active`
- Confidence: `trusted_current` / `0.86`
- Summary: Register the workbook reference as metadata only; do not read workbook body, run Excel, or mutate the file.
- Next/status: `Workbook registration`
- Visible by default: `true`

Action slots:
- `primary`: `do_it` / `Register workbook` / enabled=`true`
- `secondary`: `show_details` / `No secondary action` / enabled=`false`
- `detail`: `show_details` / `Show details` / enabled=`false`
- `dismiss`: `show_details` / `Dismiss` / enabled=`false`
- `danger_disabled`: `do_it` / `Open workbook body` / enabled=`false`

Proof categories:
- receipts=`0` artifacts=`0` hashes=`0` sqlite=`0` read_models=`1`

### Coupa submit requires a protected gate

- Card id: `dynamic_card.finance.capital_hilton.approval_request.coupa_submit`
- Family: `approval_request_card`
- Type: `approval`
- Speaker: `guardian`
- Trust: `future_gated`
- Freshness: `historical`
- Lifecycle: `archived`
- Confidence: `approval_required` / `0.32`
- Summary: The controller may stage an approval request or explain the gate, but it cannot submit to Coupa.
- Next/status: `Approval required`
- Visible by default: `false`

Action slots:
- `primary`: `do_it` / `Stage approval request` / enabled=`true`
- `secondary`: `open_lane` / `Open relevant lane` / enabled=`true`
- `detail`: `ask_why` / `Explain this gate` / enabled=`true`
- `dismiss`: `show_details` / `Dismiss` / enabled=`false`
- `danger_disabled`: `do_it` / `Submit in Coupa` / enabled=`false`

Proof categories:
- receipts=`0` artifacts=`0` hashes=`0` sqlite=`0` read_models=`3`

### Ask what is safe next

- Card id: `dynamic_card.controller.safe_next.what_should_i_do`
- Family: `contextual_what_should_i_do_card`
- Type: `question`
- Speaker: `chief`
- Trust: `trusted_current`
- Freshness: `current`
- Lifecycle: `active`
- Confidence: `trusted_current` / `0.86`
- Summary: The controller can ask for a contextual safe-next answer without staging a package or executing a business action.
- Next/status: `Contextual control`
- Visible by default: `true`

Action slots:
- `primary`: `ask_why` / `What is safe next?` / enabled=`true`
- `secondary`: `show_details` / `No secondary action` / enabled=`false`
- `detail`: `show_details` / `Show details` / enabled=`false`
- `dismiss`: `show_details` / `Dismiss` / enabled=`false`
- `danger_disabled`: `do_it` / `Execute protected action` / enabled=`false`

Proof categories:
- receipts=`0` artifacts=`0` hashes=`0` sqlite=`0` read_models=`3`

### St. Anne's work-log review

- Card id: `dynamic_card.finance.st_annes.work_log_review`
- Family: `completed_historical_receipt_card`
- Type: `status`
- Speaker: `chief`
- Trust: `trusted_current`
- Freshness: `historical`
- Lifecycle: `resolved`
- Confidence: `trusted_current` / `0.86`
- Summary: St. Anne's work-log review stays local; completed or test-only items are not primary active blockers.
- Next/status: `No active blocker`
- Visible by default: `false`

Action slots:
- `primary`: `show_details` / `No primary action` / enabled=`false`
- `secondary`: `show_details` / `No secondary action` / enabled=`false`
- `detail`: `show_details` / `Show details` / enabled=`false`
- `dismiss`: `show_details` / `Dismiss` / enabled=`false`
- `danger_disabled`: `do_it` / `Include in invoice` / enabled=`false`

Proof categories:
- receipts=`0` artifacts=`0` hashes=`0` sqlite=`0` read_models=`1`

### Review decision recorded

- Card id: `dynamic_card.build.review_packet.completed_historical_receipt`
- Family: `completed_historical_receipt_card`
- Type: `review_packet`
- Speaker: `chief`
- Trust: `trusted_current`
- Freshness: `historical`
- Lifecycle: `resolved`
- Confidence: `trusted_current` / `0.86`
- Summary: A workroom review decision is recorded as history. It is not merge, push, worker, or business execution proof.
- Next/status: `Review recorded`
- Visible by default: `false`

Action slots:
- `primary`: `show_details` / `No primary action` / enabled=`false`
- `secondary`: `show_details` / `No secondary action` / enabled=`false`
- `detail`: `show_details` / `Show details` / enabled=`false`
- `dismiss`: `show_details` / `Dismiss` / enabled=`false`
- `danger_disabled`: `do_it` / `Merge or push` / enabled=`false`

Proof categories:
- receipts=`1` artifacts=`1` hashes=`0` sqlite=`0` read_models=`3`

### Candidate memory stays unpromoted

- Card id: `dynamic_card.memory.payment_evidence_candidate`
- Family: `memory_candidate_card`
- Type: `memory`
- Speaker: `openclaw`
- Trust: `candidate_evidence`
- Freshness: `historical`
- Lifecycle: `archived`
- Confidence: `candidate_evidence` / `0.46`
- Summary: Payment-processing evidence can become a reviewed memory candidate, but candidate memory is not business truth.
- Next/status: `Candidate only`
- Visible by default: `false`

Action slots:
- `primary`: `show_details` / `No primary action` / enabled=`false`
- `secondary`: `show_details` / `No secondary action` / enabled=`false`
- `detail`: `show_details` / `Show details` / enabled=`false`
- `dismiss`: `show_details` / `Dismiss` / enabled=`false`
- `danger_disabled`: `do_it` / `Promote memory` / enabled=`false`

Proof categories:
- receipts=`0` artifacts=`0` hashes=`0` sqlite=`0` read_models=`2`

### Artifact proof is available

- Card id: `dynamic_card.artifact.evidence_intake.proof_only`
- Family: `artifact_proof_card`
- Type: `artifact`
- Speaker: `openclaw`
- Trust: `operator_reported`
- Freshness: `historical`
- Lifecycle: `archived`
- Confidence: `operator_reported` / `0.56`
- Summary: Artifact refs, hashes, and SQLite lineage are available in Developer Proof, not as primary controller UI.
- Next/status: `Proof only`
- Visible by default: `false`

Action slots:
- `primary`: `show_details` / `No primary action` / enabled=`false`
- `secondary`: `show_details` / `No secondary action` / enabled=`false`
- `detail`: `show_details` / `Show details` / enabled=`false`
- `dismiss`: `show_details` / `Dismiss` / enabled=`false`
- `danger_disabled`: `do_it` / `Read raw artifact` / enabled=`false`

Proof categories:
- receipts=`0` artifacts=`2` hashes=`0` sqlite=`1` read_models=`1`

## Contract

- Contract read model: `generated/read_models/dynamic_card_packet_contract.json`
- Latest packet: `generated/read_models/dynamic_card_packet_latest.json`
- Required example cards: `12`
- Required card families: `12`
- Required action slots: `primary, secondary, detail, dismiss, danger_disabled`

## Machine Proof

- All visible cards have trust state: `true`
- Enabled actions reference deterministic payloads: `true`
- Action slots present: `true`
- Proof categorized: `true`
- Required families present: `true`
- Unsafe true grants absent: `true`
