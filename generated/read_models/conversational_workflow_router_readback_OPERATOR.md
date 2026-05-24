# Conversational Workflow Router Readback v0

ELIOPERATOR: This readback is for the Mac chat surface. It shows what OpenClaw understood, what is proposed, what is missing, and what stays locked. It does not execute anything.

- Route mode: `NO_REQUEST_AVAILABLE`.
- Parse status: `NEEDS_MORE_DETAIL`.
- Source request: `none yet`.

## Cards

### Request blocked
- ELIOPERATOR: No Mission Control chat request is available at /mnt/e/openclaw/mission_control_capture_requests/inbox.

## Operator Choices

- Looks right: future rail needed.
- Edit understanding: available now.
- Store as procedure later: future rail needed.
- Prepare package later: future rail needed.
- Cancel: available now.

## Boundary

- No live LM/model parser was used.
- No agent dispatch, workflow run, procedure memory write, Cassandra draft, or Guardian approval occurred.
- No email, Coupa, browser, invoice generation, attachment, approval request, send, submit, or payment-state change occurred.
- No credentials, raw bodies, network, Mac sync/import, Swift change, or push occurred.

Next safe move: Fix the request shape and retry.
