# Operator Conversation Journal

Status: OPERATOR_CONVERSATION_JOURNAL_READY

The operator conversation journal is a compact Mission Control history grouped by target world and thread. It is for app display and operator orientation, not for business execution.

## What It Stores

- Target world/thread routing.
- Current world/thread context.
- Speaker and voice mode.
- Operator-display headline and short summary.
- Package/action status.
- Request, response, source-text, package, and SQLite proof refs.

## What It Does Not Store

- Raw long prompt dumps.
- Raw backend proof bodies.
- Gmail, Coupa, browser, Excel, PDF, ledger, sent, or paid actions.
- Any new business truth.

## Thread Rules

- Finance / St. Anne's includes St. Anne's work-log package responses.
- Business Development / Capital Hilton includes proposal follow-up package responses.
- Finance / Capital Hilton includes invoice operator-assist package responses.

## Privacy

The journal uses request/response file paths and protected text refs. The app should show the short operator-display fields by default and keep proof/details collapsed.

## Authority

All authority flags stay false. This journal is a read model and optional SQLite mirror only.
