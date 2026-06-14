# Workflow Readback Concierge Contract v0

ELIOPERATOR: The active agent should own the request/readback loop. The operator should not have to hunt for backend files or know where readbacks live.

## What This Enables

An active surface can say whether a request is waiting, ready, stale, blocked, duplicate, or missing.

## How It Works

- The agent tracks the request it caused.
- It looks for a matching backend readback by request identity and workflow context.
- It checks whether the readback is current before using it.
- It explains waiting, ready, stale, duplicate, blocked, or missing states plainly.
- It never claims success without a matched readback or proof receipt.

## Example Cards

### Waiting for PC backend
- I sent your request. No understanding has returned yet.
- The request is tracked.
- No backend readback has been matched yet.
- I will not claim what OpenClaw understood until the readback exists.

### OpenClaw understood
- I found the readback. Here is what OpenClaw understood.
- Capital Hilton invoice workflow was routed for review.
- Excel/PDF companion invoice, Coupa/PO payment rail, and contact follow-up are understood as draft workflow context.
- This is ready for review, not execution.
- Send, Coupa, approval, browser, and invoice-generation actions remain locked.

### Readback looks stale
- This readback looks stale. I will not use it as current.
- The readback exists, but it is not proof of the current request.
- I will not use it as current.
- The safe move is to wait for or regenerate the matching readback.

### Ready for review, not execution
- This is ready for review, not execution. Send/Coupa/approval remain locked.
- No email was sent.
- No Coupa or browser access occurred.
- No approval was requested.
- No invoice was generated or submitted.

## Boundary

- No live polling, watcher, model call, agent dispatch, workflow run, or external action exists here.
- No email, Coupa, browser, invoice generation, approval, credential handling, raw-body ingestion, Mac sync/import, Swift change, network, or push occurred.

Next safe move: Use the ready card to ask the operator whether the Capital Hilton understanding looks right.
