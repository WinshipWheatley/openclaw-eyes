# Cross-Machine Worker Dispatch Package v0

ELIOPERATOR: One OpenClaw chat can prepare the right worker package without auto-dispatching it.

## What This Means

- Mac Codex owns Apple/Mac-side ship experience: Mission Control SwiftUI, Xcode validation, Mac-local rendering, screenshots, and Apple app boundaries.
- PC Codex owns canonical Repo A backend / Shipyard substrate: Python, tests, generated read-models, package/shuttle rails, and backend contracts.
- Gemini/Agy owns read-only scouting, audit, taste/design targeting, and prompt shaping.
- Packages carry the context, allowed work, forbidden work, proof requirements, validation, and return format.
- Nothing is auto-dispatched yet.

## Example Routes

### Send this to Mac Codex
- This is Apple/Mac-side app work. It should go to Mac Codex, not PC Codex.
- Worker: Mac Codex.
- Machine: Mac.
- Status: `PACKAGE_READY_NOT_SENT`.

### Send Apple-side project recognition to Mac Codex
- Logic Pro project recognition belongs to the Mac app lane with DAW mutation blocked.
- Worker: Mac Codex.
- Machine: Mac.
- Status: `PACKAGE_READY_NOT_SENT`.

### Send Final Cut display work to Mac Codex
- This is Mac-side metadata display work; project export or mutation remains blocked.
- Worker: Mac Codex.
- Machine: Mac.
- Status: `PACKAGE_READY_NOT_SENT`.

### Send this to PC Codex
- This is canonical Repo A backend work. It should go to PC Codex.
- Worker: PC Codex.
- Machine: PC/WSL.
- Status: `PACKAGE_READY_NOT_SENT`.

### Send this to Gemini/Agy
- This is read-only scouting and prompt shaping, not implementation.
- Worker: Gemini/Agy.
- Machine: External model lane.
- Status: `WAITING_FOR_OPERATOR_SEND`.

### I need a target before routing
- “Make it better” is too broad to pick a worker safely.
- Worker: Needs routing.
- Machine: Unknown.
- Status: `BLOCKED_MISSING_CONTEXT`.

## Blocked Examples

- Mail send request: Mac Codex may review UI/boundary only; actual send remains governed and blocked.
- SwiftUI routed to PC Codex: blocked as wrong worker/machine.
- UI package with Gmail/Coupa/send authority: blocked as authority too broad.

## Boundary

- No live auto-dispatch.
- No worker execution.
- No cross-machine send.
- No model call, agent dispatch, workflow run, external action, credential handling, raw-body ingestion, Mac sync/import, Swift change, or push.

Next safe move: show the dispatch card, let the operator send/edit/cancel, and keep readback returning to the same chat.
