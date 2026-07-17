# Invoice Validation W2 Activation Record - 2026-07-17

## Live State

- Operator validation event `invoice-validation:ec1f6eb9ca786420cf61df67` records Telegram message 1794, `"That looks perfect."`, for `live_arts_md/2026-07/2026-1004`.
- The validated and finalized PDF SHA-256 values are identical: `99c0d53b8077a2c8f85a6e3a14d0d3df60c740dd179fa5da917983b28356ce78`.
- The canonical workbook SHA-256 is `3eb8cd7c82c234cccc3051dadb692d8cb5c00afa0a11c9eca4b10927e8e80aad`.
- Transaction `invoice-send-tx:495069a26823c4d47826c151` is append-only `SUPERSEDED` by `invoice-send-tx:d6706f66ae8f24f8b0e8617c`.
- The replacement is the only same-obligation `PREPARED` transaction at rest.
- Guardian action `5FF438AC` was delivered and remains `WAITING_FOR_APPROVAL`.

## Owner Verification

- The canonical manifest-first locator resolves one `finalized_validated` artifact at the exact approved hash.
- A bounded replay through the active request-response service selected that artifact with delivery suppressed and no matching delivered-text row.
- The Guardian owner API reads the exact action as pending; the notification audit records `notification_sent` on `telegram_guardian`.
- No exact-send execution or fixture-execution attempt exists for this request.

## Authority Boundary

Artifact validation authorizes exact-byte finalization only. Provider draft/send, money movement, payment marking, business-ledger posting, and deletion remain false. The signed Guardian decision and the independent client SEND_HOLD gate are both required before any transport attempt.

## Evidence

- `/home/openclaw/Operator/from-codex/W2-B-VALIDATION-EVENT-1-RECEIPT-20260717-PC-Codex-Desktop.json`
- `/home/openclaw/Operator/from-codex/W2-B-VALIDATED-ARTIFACT-PROMOTION-RECEIPT-20260717-PC-Codex-Desktop.json`
- `/home/openclaw/Operator/from-codex/W2-B-VALIDATION-EVENT-1-CHAIN-RECEIPT-20260717-PC-Codex-Desktop.json`
