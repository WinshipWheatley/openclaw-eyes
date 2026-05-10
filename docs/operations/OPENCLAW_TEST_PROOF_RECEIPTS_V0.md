# OpenClaw Test/Proof Receipts v0 Contract

## 1. Purpose
Test/proof receipts are deterministic evidence that a local check was run and what happened. They support evidence sufficiency, generated status read-models, morning briefs, and agent confidence by providing a ledger-backed trail of verification events.

## 2. Receipt is Not Truth
A passing test receipt proves a specific command passed at a specific time, for a specific commit, in a specific environment. It does NOT prove the whole system is functionally correct or that the code is free of bugs. It is a "receipt of execution," not a guarantee of total system integrity.

## 3. Minimum Safe Fields
The v0 contract for a `test_proof_receipt` event includes:

- **timestamp**: ISO 8601 UTC.
- **event_type**: `test_proof_receipt`.
- **command_label**: A human-readable label for the check (e.g., `static_contract_check`).
- **command_string**: The safe, redacted command string or argv executed.
- **exit_code**: The integer exit code of the process.
- **status**: `pass`, `fail`, or `skip`.
- **git_branch**: The current git branch name.
- **git_head**: The short SHA (8 chars) of the current HEAD.
- **git_dirty**: Boolean indicating if the repo had unstaged/uncommitted changes.
- **duration_ms**: (Optional) Process execution time in milliseconds.
- **summary**: A short (1-line) summary of the result.
- **output_hash**: A SHA-256 hash of the full stdout/stderr to detect tampering or changes.
- **output_tail**: (Optional) A bounded tail (e.g., last 10 lines) of safe, non-sensitive output.
- **redaction_marker**: Boolean indicating if output was redacted.
- **actor_source**: The recorder identity, e.g., `test_proof_recorder_v0`.

## 4. Sensitive Boundaries
To maintain security and privacy, receipts MUST NOT contain:
- **Raw Secrets**: No API keys, tokens, or passwords in `command_string` or `output_tail`.
- **Private Roots**: No full paths to `.google-secrets/`, `.ssh/`, or user-private directories unless explicitly approved.
- **Raw Full Logs**: No massive multi-megabyte log dumps; use `output_hash` and `output_tail`.
- **User Data**: No Gmail snippets, Telegram messages, legal documents, client names, or payment/billing details.
- **Runtime Health Claims**: A receipt only claims that a *process* finished; it does not claim the "system is healthy."

## 5. Event Taxonomy
- Canonical `event_type`: `test_proof_receipt`.
- Use this single type for all v0 proof evidence to keep ledger queries simple.

## 6. Failure Receipts
Failures are critical evidence. Do not suppress or hide failed tests. Record them with `status: fail` and a bounded `output_tail` describing the error (e.g., a traceback summary) while adhering to sensitive boundaries.

## 7. Future Consumers
- **Evidence Sufficiency Map**: Grounding agent "Confidence Levels" in actual proof receipts.
- **Generated Status / Read Models**: Incorporating the latest test results into the `OPERATOR_STATUS`.
- **Morning Brief Chain**: Alerting the operator to regressions found during overnight or early-morning sweeps.
- **Guardian / Chief**: Using proof receipts to validate that a proposed change was verified before being considered "Done."

## 8. Non-Goals
- **No Autonomy**: This contract does not grant agents the authority to run arbitrary commands.
- **No Scheduling**: No automated cron/loop testing is defined in this lane.
- **No Discovery**: This is not a test discovery engine; it is a receipt-recording contract.
- **No CI Replacement**: This ledger is for local "Operator Lane" evidence, not a replacement for GitHub Actions or other CI.
- **No Schema Change**: This lane does not modify the `business_ops` SQLite schema.
