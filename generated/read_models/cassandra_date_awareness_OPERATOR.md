# Cassandra Date Awareness v0

Status: fixed. System date used: `2026-05-17` (Sunday).

## What Changed
- Cassandra now has deterministic answers for common relative-date questions.
- The authoritative date context is placed before persona/prompt text.
- Model memory is explicitly not allowed to decide current dates.

## Relative Date Proof
- `today` -> 2026-05-17 (Sunday)
- `yesterday` -> 2026-05-16 (Saturday)
- `tomorrow` -> 2026-05-18 (Monday)
- `this friday` -> 2026-05-22 (Friday)
- `last thursday` -> 2026-05-14 (Thursday)
- `next week` -> 2026-05-18 (Monday) through 2026-05-24 (Sunday)
- `last week` -> 2026-05-04 (Monday) through 2026-05-10 (Sunday)
- `next month` -> June 2026
- `last month` -> April 2026
- `next year` -> 2027
- `last year` -> 2025

## Wrong-Date Correspondence Scan
- Targeted files scanned: `2`.
- Wrong-date matches found: `0`.
- Raw content included: `false`.
- Correction sent: `false`.

No visible recent correspondence matching `June 24, 2024` / `2024-06-24` signatures was found.

## Boundaries
- No Telegram messages were sent.
- No replies were enabled.
- No tokens, raw chat IDs, secrets, env values, or raw private content were included.
- Runtime authority did not change.

## Next Safe Move
- Cassandra Intake-to-Work Packet Live Proof v0
