# Agent TTS Text Sanitizer

Status: `AGENT_TTS_SANITIZER_READY`

This sanitizer prepares operator-display copy for local TTS by converting it to plain text. It does not call a TTS provider or send messages.

## What It Strips

- Backticks and code fence markers.
- Asterisks and markdown emphasis.
- Hash headings.
- Bullet symbols.
- Raw JSON object or array text.
- Markdown links, preserving the readable label.

## Profile Rules

### `cassandra`

- Policy: commas and ellipses allowed for calm intake cadence
- Voice profile: `agent_voice_profile:cassandra`

### `chief`

- Policy: periods and colons, no ellipses
- Voice profile: `agent_voice_profile:chief`

### `hermes`

- Policy: measured commas and em dashes allowed
- Voice profile: `agent_voice_profile:hermes`

### `guardian`

- Policy: terse periods, no ellipses
- Voice profile: `agent_voice_profile:guardian`

### `niles`

- Policy: relaxed pauses without parody markers
- Voice profile: `agent_voice_profile:niles`

### `clara`

- Policy: professional punctuation only
- Voice profile: `agent_voice_profile:clara`

### `openclaw`

- Policy: neutral status punctuation
- Voice profile: `agent_voice_profile:openclaw`

## Boundary

- No TTS live connection.
- No message send.
- No email, browser, Gmail, or Coupa.
- No ledger or workbook mutation.
- No paid or sent marking.
