# Dynamic Card Packet

Status: `DYNAMIC_CARD_PACKET_READY`

The Dynamic Card Packet is the backend-generated operator card surface for Mission Control. It lets the Mac render current answers, status, safe next actions, proof drawers, trust state, and safe buttons without custom SwiftUI for every workflow.

## Boundary

- No live LM1 or LM2.
- No worker spawn or child-agent run.
- No external LLM or local model runtime.
- No email, Gmail, browser, Coupa, ledger, workbook, PDF, submit, mark-paid, merge, push, or repair authority.
- Enabled actions only reference deterministic `operator_action_payloads.json` payloads.
- Proof/details are collapsed by default.

## Cards

### Stay on payment watch

- Card id: `dynamic_card.finance.capital_hilton.payment_watch`
- Type: `payment_watch`
- Speaker: `chief`
- Trust: `trusted_current`
- Summary: Coupa is processing. Wait for payment evidence before anything touches the ledger.
- Next/status: `Payment watch`
- Visible by default: `true`

Actions:
- `capital_hilton.payment.open_finance` / `Open Finance / Capital Hilton` / enabled=`true`

### Payment proof received

- Card id: `dynamic_card.finance.live_arts_md.evidence_intake.payment_processing`
- Type: `evidence_intake`
- Speaker: `chief`
- Trust: `operator_reported`
- Summary: This appears to show payment processing for invoice 2026-1001. Ledger remains untouched until payment is confirmed.
- Next/status: `Processing evidence`
- Visible by default: `true`

Actions:
- `evidence_intake.attach_to_lane` / `Attach to lane` / enabled=`false`
- `evidence_intake.ask_what_this_means` / `Ask what this means` / enabled=`false`
- `evidence_intake.mark_as_test` / `Mark as test` / enabled=`false`
- `evidence_intake.show_details` / `Show details` / enabled=`false`

### Stay on payment watch

- Card id: `dynamic_card.finance.capital_hilton.contextual_question`
- Type: `answer`
- Speaker: `chief`
- Trust: `trusted_current`
- Summary: Coupa is processing. Wait for payment evidence before anything touches the ledger.
- Next/status: `Answer ready`
- Visible by default: `true`

Actions:
- `capital_hilton.payment.open_finance` / `Open Finance / Capital Hilton` / enabled=`true`

### Review packet needs local decision

- Card id: `dynamic_card.build.review_packet.current`
- Type: `review_packet`
- Speaker: `chief`
- Trust: `preview_only`
- Summary: PC_CODEX changed backend code and returned local validation proof for operator review.
- Next/status: `REVIEW_PACKET_READY`
- Visible by default: `true`

Actions:
- `review_packet.review_packet_c4ec166103f9aa35.approve_review_packet_for_record` / `Approve for record` / enabled=`true`
- `review_packet.review_packet_c4ec166103f9aa35.request_review_packet_rework` / `Request rework` / enabled=`true`
- `review_packet.review_packet_c4ec166103f9aa35.mark_review_packet_informational` / `Mark informational` / enabled=`true`

### Proposal follow-up is review-only

- Card id: `dynamic_card.business_development.capital_hilton.proposal`
- Type: `status`
- Speaker: `cassandra`
- Trust: `trusted_current`
- Summary: Capital Hilton proposal context is business development. Draft or stage a follow-up only for review; do not send.
- Next/status: `Proposal status`
- Visible by default: `true`

Actions:
- `capital_hilton.proposal.stage_followup` / `Stage proposal follow-up` / enabled=`true`

### Chief diagnostic only

- Card id: `dynamic_card.system.check_engine.diagnostic`
- Type: `status`
- Speaker: `chief`
- Trust: `preview_only`
- Summary: Open the Check Engine diagnostic or ask Chief; no repair authority is granted.
- Next/status: `Diagnostic`
- Visible by default: `true`

Actions:
- `chief_diagnostic.open` / `Open Chief diagnostic` / enabled=`true`
- `helm_question.hardwired_vs_spawned.ask` / `What is the difference between Chief and a spawned worker?` / enabled=`true`

### Workbook reference can be registered

- Card id: `dynamic_card.finance.capital_hilton.workbook_registration`
- Type: `workbook_registration`
- Speaker: `chief`
- Trust: `trusted_current`
- Summary: Register the workbook reference as metadata only; do not read workbook body, run Excel, or mutate the file.
- Next/status: `Workbook registration`
- Visible by default: `true`

Actions:
- `client_invoice_workbook.register` / `Register workbook` / enabled=`true`

### St. Anne's work-log review

- Card id: `dynamic_card.finance.st_annes.work_log_review`
- Type: `status`
- Speaker: `chief`
- Trust: `trusted_current`
- Summary: St. Anne's work-log review stays local; completed or test-only items are not primary active blockers.
- Next/status: `No active blocker`
- Visible by default: `false`

## Contract

- Contract read model: `generated/read_models/dynamic_card_packet_contract.json`
- Latest packet: `generated/read_models/dynamic_card_packet_latest.json`
- Required example cards: `8`

## Machine Proof

- All visible cards have trust state: `true`
- Enabled actions reference deterministic payloads: `true`
- Unsafe true grants absent: `true`
