# Mission Control Capture Request Intake

## What Landed
This is the backend bridge for a future Capture / Use This Draft button. The packet is visual-agnostic, so Mission Control, Telegram, or Cassandra can later send the same shape.

## Captured State
- Performance dates: `2026-05-08, 2026-05-15, 2026-05-22, 2026-05-29`
- Rate: `$400/show`
- Derived subtotal: `$1,600`
- SQLite state source: `/home/openclaw/.openclaw/business_ops/ledger.sqlite`

## Closeout
Nice. OpenClaw now has the Capital Hilton invoice draft captured with 4 performance dates, $400/show, and a $1,600 subtotal. Still blocked: PO/Coupa route, invoice artifact generation, and approval/send.

## Still Blocked
- PO/Coupa/payment reference still needs discovery or operator confirmation
- invoice artifact/PDF/Excel generator is not run in this lane
- AP/email delivery route is not confirmed by this lane
- approval/send remains locked
- Coupa portal submission remains an external protected-access gate

## Boundaries
- Local SQLite capture write: `true`
- Batch capture: `false`
- PO/Coupa capture: `false`
- Invoice generation: `false`
- Email send: `false`
- Coupa/browser/Gmail/Telegram access: `false`
- Model/tool/runtime execution: `false`

## Next Safe Move
Build or invoke the safe invoice packet/artifact rail, then gather PO/Coupa/AP delivery facts.
