# Operator Frontdoor F0 Activation Record - 2026-07-17

## Authority

- Fable directive: `FABLE-PASS-2-ALIGN-COMBINED-FRONTDOOR-BUILD-GO-20260717.md`
- Scope: surface-aware operator artifact delivery, candidate/current selection, honest canned-floor failure, repeated typing presence, and addressed-agent Kokoro voice.
- Boundary: operator Telegram delivery only; no provider draft, business send, money, deletion, secret disclosure, canonical invoice mutation, or ledger post.

## Deployed Owners

- `openclaw-request-response.service`: active after post-commit restart; typed surface/artifact disposition and candidate registry loaded.
- `maestro-listener.service`: active after post-commit restart; repeated typing, verified photo delivery, delivered-text receipt, and addressed-agent voice carrier loaded.
- `cassandra-listener.service`, `chief-listener.service`, `chief-guardian-listener.service`, `niles-listener.service`, and `hermes-gateway.service`: active after the shared-profile restart, all with `OPENCLAW_FLEET_VOICE_BOUNDARY=1`.
- Cassandra, Chief, and Producer/Niles retain the same repeated typing-loop class shape around their owner work; no single-agent presence patch was introduced.

## Real Process Evidence

- Replay 1697: Live Arts MD current finalized artifact selected; `delivery_mode=telegram_photo`; operator copy contains no QuickLook or local path language.
- Replay 1711: prior same-chat LAMD context resolved; the verified Candidate B column-width correction selected; candidate/not-final labeling present; PDF SHA `6b1ad7c4678a919db8d691cf6b47513987cb7acdfc67c73a37249b7533a07ccc`.
- Replay 1714: the live semantic vote mislabeled the prompt as status, and the shared status-eligibility seam returned an honest grounded-route failure with `status_intent_mismatch_blocked=true`.
- Replay 1719: the same shared guard blocked the unrelated fleet status answer and returned the honest route failure.
- Real Telegram provider canary: Maestro bot emitted two typing actions, delivered candidate photo message `1786`, then delivered locally synthesized Kokoro voice message `1787`.
- Artifact delivery receipt binds source request, selected PDF hash, preverified PNG hash `71018a717884e49a672bc1562469305bf43b66c22519d08d7013cd754144b18a`, caption hash, and delivered message ID.
- Voice receipt binds the same source request and caption hash to speaker `maestro`, carrier `maestro`, synthesis success, and delivered message ID; fallback was empty.
- Fleet delivered-text index row binds the source request and caption hash to photo message `1786`.

## Verification

- Targeted F0 suite before the live canary: 65 passed.
- Broad F0 suite before the live canary: 138 passed.
- Semantic-status misvote red/green: failed before shared guard, then 3 focused tests passed.
- Six agent owner services plus request/response remained active with zero systemd restart failures after activation.

## Rollback

Revert the F0 owner changes and restart `openclaw-request-response.service` plus `maestro-listener.service`. SEND_HOLD and all business effect gates remain independent and closed.
