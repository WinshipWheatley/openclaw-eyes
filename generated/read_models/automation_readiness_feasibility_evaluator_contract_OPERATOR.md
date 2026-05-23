# Automation Readiness / Feasibility Evaluator Contract v0

## ELIWINSHIP Summary

Manual forever is not the goal. Manual is the safe fallback while OpenClaw figures out which parts are actually worth automating and which parts are blocked by security, credentials, terms, proof, or approval risk.

The point is to find the bottleneck before polishing the path. If the hard part is Coupa/PO lookup, stale approvals, protected evidence, or unsafe repair, OpenClaw should say that plainly instead of making Winship babysit more panels.

## What The Evaluator Does

- Names the bottleneck in each workflow.
- Separates low-hanging fruit from high-risk or blocked automation.
- Keeps manual fallback available without treating it as the destination.
- Marks assisted capture as the near-term bridge and governed automation as future-gated.
- Lists the gates, receipts, and infrastructure needed before any live action.

## Capital Hilton Coupa / PO Bottleneck

- Current fallback: `guided manual capture`.
- Near-term path: `build assisted capture first`.
- Future path: `evaluate supervised/read-only automation after site, credential, receipt, and Guardian gates exist`.
- Feasibility: `ASSISTED_CAPTURE_FEASIBLE`.
- Risk: `HIGH`.
- The safe next step is guided manual capture / assisted capture modeling. Coupa, browser, network, credentials, and automation remain blocked now.

## What Would Make Automation Safe Later

- Approved site registry.
- Protected credential broker.
- Supervised browser session.
- Protected evidence store.
- Receipt writer.
- Workflow session store and approval bus.
- Guardian/security review and operator final authority.

## What Remains Blocked

- No automation execution, browser/Coupa/network access, credential handling, invoice generation, email send, ledger write, approval submission, model/tool/agent/runtime/queue execution, or workflow execution.

## Why This Makes Life Easier

Winship should see the few real blockers and the cleanest next safe move. If automation is easy, OpenClaw can propose the next bridge. If it is unsafe or not worth it, OpenClaw should stop early instead of turning one hard step into a complicated cockpit.

## Machine Proof Summary

- Bottleneck assessments: `6`.
- Readiness evaluations: `4`.
- Infrastructure candidates: `10`.
- Dead-on-arrival criteria: `10`.
- Capital Hilton Coupa/PO bottleneck present: `true`.
- All current authority flags false: `true`.
- Content hash: `sha256:5098a4370905942752c437297c8108ee316322ab6a6fcb887e1aab3cebd01154`.
