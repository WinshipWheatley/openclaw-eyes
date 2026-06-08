# Context Compaction Preview Policy

Status: CONTEXT_COMPACTION_PREVIEW_POLICY_READY

This contract keeps OpenClaw agent context high-signal and scoped. Large artifacts are previewed first, full files stay referenced, stale material is demoted, and protected/raw material is hidden by default.

## Summary

- Context tiers: `7`
- Required scenarios: `6`
- Preview first: `true`
- Full artifacts referenced, not embedded: `true`
- Developer proof hidden by default: `true`

## Context Tiers

### 0. tier_0_operator_request

- Purpose: Preserve the current operator ask and explicit constraints.
- Agent-visible by default: `true`
- Content policy: Exact current request summary, scoped constraints, and requested status only.

### 1. tier_1_current_lane_summary

- Purpose: Give the agent the latest scoped lane facts without raw source bodies.
- Agent-visible by default: `true`
- Content policy: Redacted current lane summary backed by receipts or decision trace.

### 2. tier_2_current_receipts_and_proof_meters

- Purpose: Expose proof state labels and receipt references, not private proof bodies.
- Agent-visible by default: `true`
- Content policy: Receipt refs, proof meter labels, confidence labels, and current blockers.

### 3. tier_3_decision_trace_summary

- Purpose: Explain relevant prior decisions and rejections without dumping old responses.
- Agent-visible by default: `true`
- Content policy: Short decision trace summary when it changes the next safe action.

### 4. tier_4_preview_snippets

- Purpose: Show only safe excerpts from large artifacts when a preview is useful.
- Agent-visible by default: `true`
- Content policy: Bounded safe snippet with omission count and full artifact reference.

### 5. tier_5_full_artifact_or_log_reference

- Purpose: Keep full artifacts reachable by reference without embedding them.
- Agent-visible by default: `true`
- Content policy: Reference, hash, path class, owner, and access instruction only.

### 6. tier_6_developer_proof_only

- Purpose: Retain verification material for developers/harnesses without exposing it to ordinary agents.
- Agent-visible by default: `false`
- Content policy: Developer proof refs and test internals are hidden unless a separate approved route asks for them.

## Preview Rules

- `preview_large_artifacts_first`: Large logs/files/artifacts are not dumped into model context.
- `reference_not_embed_full_artifact`: Full artifact remains referenced, not embedded.
- `dig_only_when_needed_and_allowed`: Agent must ask/dig only when needed and allowed.
- `raw_ocr_artifact_text_excluded`: Raw OCR/artifact text is excluded unless explicitly approved.

## Compaction Rules

- `controller_responses_to_decision_trace`: old controller responses -> decision trace summary
- `tool_outputs_to_receipts_and_proof`: old tool outputs -> receipt refs and proof meter labels
- `stale_summaries_demoted`: stale or superseded summaries -> history or refresh-needed note
- `superseded_receipts_historical`: superseded receipts -> historical receipt refs, not current truth
- `preserve_high_signal_lessons`: resolved blockers, failed attempts, operator decisions -> short lesson tied to decision trace
- `archive_low_signal_chatter`: low-signal chatter and obsolete status noise -> archive reference only

## Agent-Visible Context

Allowed by default:
- redacted current facts
- current proof meter labels
- latest receipt refs
- relevant decision trace summary
- missing input
- blocked action summary
- allowed next controls
- preview snippets only when safe

Forbidden by default:
- full logs
- raw file bodies
- raw email/Coupa/Gmail/browser content
- raw OCR/artifact text
- raw workbook/ledger bodies
- credentials/secrets
- operator/device/session verification material
- full chat history dumps
- stale context as current truth

## Scenarios

### Large server/error log

- Scenario id: `large_server_error_log`
- Goal: Expose a safe diagnostic preview without dumping the full log.
- Selected tiers: tier_1_current_lane_summary, tier_3_decision_trace_summary, tier_4_preview_snippets, tier_5_full_artifact_or_log_reference
- Excluded: full log body, raw file body, credentials/secrets, operator/device/session verification material

### Local LM non-JSON postmortem

- Scenario id: `local_lm_non_json_postmortem`
- Goal: Keep the useful failure lesson without embedding raw non-JSON output.
- Selected tiers: tier_1_current_lane_summary, tier_2_current_receipts_and_proof_meters, tier_3_decision_trace_summary, tier_5_full_artifact_or_log_reference
- Excluded: raw candidate text, raw artifact body, runtime connection details

### Finance payment watch

- Scenario id: `finance_payment_watch`
- Goal: Provide current finance state and decision trace without private proof bodies.
- Selected tiers: tier_1_current_lane_summary, tier_2_current_receipts_and_proof_meters, tier_3_decision_trace_summary
- Excluded: private payment proof body, raw bank details, raw ledger rows, raw workbook bodies

### Build review history

- Scenario id: `build_review_history`
- Goal: Keep resolved review history available without making it active context.
- Selected tiers: tier_3_decision_trace_summary, tier_5_full_artifact_or_log_reference
- Excluded: resolved review as active context, stale summary as current truth

### Niles creative mapping

- Scenario id: `niles_creative_mapping`
- Goal: Allow creative context while excluding unrelated finance proof.
- Selected tiers: tier_0_operator_request, tier_1_current_lane_summary, tier_4_preview_snippets
- Excluded: finance proof, payment evidence, ledger receipts, private finance artifacts

### Developer proof only

- Scenario id: `developer_proof_only`
- Goal: Record that developer proof exists without showing it to ordinary agents.
- Selected tiers: tier_6_developer_proof_only
- Excluded: developer proof bodies, test fixture internals, session verification material

## Boundary

This policy does not invoke models, connect runtimes, spawn workers, send email, open Gmail/browser/Coupa, mutate ledger/workbooks, export PDFs, mark paid, submit, push, or grant business authority.
