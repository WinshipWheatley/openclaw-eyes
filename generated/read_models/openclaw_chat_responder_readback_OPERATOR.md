# OpenClaw Chat Responder Router v0

ELIOPERATOR: This routes a chat message to a safe responder context package. It does not execute the workflow.

- Workflow: `invoice_delivery_workflow`.
- Client: `capital_hilton`.
- Responder role: `finance_workflow_responder`.
- Response status: `LOCAL_MODEL_UNAVAILABLE`.
- Selected model: `False`.

## Assistant Message

No approved local responder model is available yet. The router and context package are ready, but OpenClaw cannot produce a live LM reply until a local model responder rail is connected.

## Context Package

- Package type: `CHAT_RESPONSE_CONTEXT_PACKAGE`.
- Included summary: OpenClaw routed the Capital Hilton invoice message to draft human cards. The response may explain the draft understanding, missing pieces, locked actions, and next safe move.
- Truth boundary: This is a draft assistant explanation grounded in readbacks; receipts/readbacks remain truth.

Known:
- 4 dates at $400 each working basis
- Excel/PDF companion invoice desired
- Annette contact candidate
- Coupa/PO payment rail candidate
- invoice should be saved for records

Missing:
- exact Coupa PO/reference or a decision to keep discovery open
- confirmation that Annette is the right contact
- final invoice artifact/hash
- Guardian approval
- send/submit receipts

Locked:
- email draft
- email send
- Coupa access
- Coupa submit
- browser automation
- approval request
- invoice generation
- attachment
- payment state update

## Responder Selection

- Model source: existing chief_llm local helper detected but not approved for this chat responder lane
- Model available: `False`.
- Blocked reason: No approved local chat responder adapter is connected.

## Boundary

- No cloud model/API was used.
- No network was used.
- No tools, agents, workflow run, procedure memory write, email, Coupa, browser, approval, invoice generation, attachment, payment tracking write, or external action happened.

Next safe move: Show the unavailable responder readback and connect the missing local responder rail.
