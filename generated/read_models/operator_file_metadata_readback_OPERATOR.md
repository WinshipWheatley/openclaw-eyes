# Operator File Metadata Readback v0

ELIOPERATOR: This readback captures file metadata as a safe source reference. It does not read the file body or execute anything.

- Route mode: `REQUEST_BLOCKED`.
- Readback status: `BLOCKED_INVALID_REQUEST`.

## File reference blocked

OpenClaw did not capture this file reference because the request was not safe metadata-only.

- ELIOPERATOR: payload_hash does not match request metadata.

## What did not happen

- No file body was read or ingested.
- No OCR, spreadsheet parsing, PDF parsing, or image analysis occurred.
- No folder scan, app automation, model call, credential handling, or external action occurred.

## Registry posture

- Persistent source registry is not connected yet.
- Idempotency is validated, but duplicate persistence is not claimed.

Next safe move: Send a metadata-only file reference with idempotency and payload hash.
