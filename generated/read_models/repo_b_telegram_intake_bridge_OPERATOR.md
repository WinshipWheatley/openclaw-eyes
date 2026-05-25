# Repo B Telegram Intake Bridge

## Summary
Repo B's Telegram code contains useful intake and follow-up shapes, but its actual listeners and senders are unsafe for Repo A v0 because they start live bots, depend on bot credentials, post outbound replies, and can touch pending state. This bridge keeps only fixture-safe request-envelope mapping.

## Posture
- Bridge posture: INTAKE_ONLY_BRIDGE_WITH_REPO_A_REBUILT_REQUEST_ENVELOPE_ADAPTER
- Repo B invocation: none in v0
- Live Telegram: blocked
- Outbound Telegram: blocked
- Primary surface remains: Mac chat

## Safe Intake
- Operator message fixture maps to: CHAT_REQUEST
- Follow-up fixture maps to: CHAT_REQUEST
- Output is a request-envelope model, not a live inbox write.

## Blocked
- LIVE_TELEGRAM_LISTENER_START_ATTEMPTED: Telegram live listener startup is blocked. This lane only models fixture intake envelopes.
- TELEGRAM_OUTBOUND_ATTEMPTED: Outbound Telegram is blocked. OpenClaw should return local Mac-readable response files instead.
- BOT_TOKEN_INCLUDED: Bot credentials cannot appear in chat, read-models, fixtures, logs, or operator cards.
- RAW_PRIVATE_MESSAGE_EXPOSED: Raw private Telegram messages are blocked from normal read-models.
- PENDING_ACTION_DISPATCH_ATTEMPTED: Pending-action dispatch is blocked from Telegram intake.
- QUEUE_MUTATION_ATTEMPTED: Queue mutation is blocked in the Telegram intake bridge.
- EXTERNAL_ACTION_ATTEMPTED: External action is blocked.
- CREDENTIAL_OR_ENV_MUTATION_ATTEMPTED: Credential and environment mutation are blocked.
- UNSCOPED_PUBLIC_CHAT_SURFACE: Unscoped public chat surfaces are blocked.
- UNKNOWN_FAIL_CLOSED: Unknown Telegram intake behavior fails closed.

## Operator Example
- Input: Make the Capital Hilton invoice workflow happen.
- Readback: OpenClaw can turn this Telegram-style message into a local chat request envelope. Nothing was posted back to Telegram and no workflow ran.
- Next: Submit this shape to the bounded OpenClaw request processor only when a safe local intake adapter is approved.

## Boundary
No live Telegram listener, no Telegram outbound, no bot token access, no pending action dispatch, no queue mutation, no external action, no credential handling, no raw private body exposure.
