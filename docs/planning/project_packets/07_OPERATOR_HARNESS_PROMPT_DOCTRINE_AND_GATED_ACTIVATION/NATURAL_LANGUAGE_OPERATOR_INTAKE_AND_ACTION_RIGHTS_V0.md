# Natural-Language Operator Intake And Action-Rights Roadmap v0

Status type: OPERATING_DOCTRINE / STATIC_READ_MODEL / FUTURE_LANE

## Purpose

Define how OpenClaw should interpret plain operator language, frame the next safe move, and later earn bounded action rights lane by lane without becoming hidden authority.

This v0 is a Packet 07 bridge from manual command and prompt management toward conversation-driven operator work. It makes the future path legible while implementing only static Stage 1 proof now.

## North Star alignment

OpenClaw exists to make daily life lighter without becoming hidden authority.

This document supports that North Star by:

- reducing operator burden from command and prompt memory;
- translating rough language into useful intent frames;
- clarifying the next safe action before any tool or runtime step;
- preserving evidence boundaries through receipts and read models;
- creating a staged path toward future action rights only after gates, receipts, rollback, and explicit approval.

## What this v0 authorizes

This v0 authorizes static Stage 1 framing only:

- classify expected operator intent classes in documentation and receipts;
- describe the safest correct response frame for each intent;
- identify which receipts or read models should be consulted;
- prepare future prompt, handoff, or approval framing as static guidance;
- expose a read-only `operator-intake-status` proof receipt.

Level 0 static framing is the only action-right level authorized by this v0.

## What this v0 does not authorize

This v0 does not authorize live autonomy.

It does not authorize:

- live runtime launch, assistant daemons, listeners, speech, audio, Telegram, or UI surfaces;
- process scans, service scans, systemd/launchctl/service/timer/daemon/launcher mutation;
- provider/model/API calls;
- MCP calls, MCP connector mutation, shared-memory writes, or hidden memory writes;
- external sends;
- invoice, money, legal, private-root, or sensitive-data actions;
- commits, pushes, destructive operations, or broad repo mutation;
- treating "do the next thing" or any other natural-language phrase as execution authority.

Natural language can express operator intent. It cannot by itself grant hidden execution authority.

## Stage 1: Intent and response framing

Stage 1 target:

```text
Winship says X -> system understands intent -> frames safest correct next move.
```

Implemented now as static v0:

- maintain a bounded intent map;
- define correct response frames and follow-up rules;
- route risky or ambiguous requests to explicit approval;
- keep all output deterministic, local, and metadata-only;
- prove the doc shape with `./scripts/openclaw_receipts.py operator-intake-status`.

Stage 1 does not run a live classifier. It is a receipt-backed architecture/read-model surface for future chats and agents.

## Stage 2: Prompt/handoff generation

Stage 2 target:

```text
Winship says X -> system generates the right response/prompt/handoff for Codex, Gemini, Chief-style review, or operator review.
```

Future gated progression:

- generate Codex implementation prompts from bounded repo tasks;
- generate Gemini planning or architecture/scope review prompts;
- generate Chief-style review prompts for risk, scope, and approval posture;
- generate operator review summaries and handoff drafts;
- require tool-specific prompt doctrine from File 14 and prompt-pack receipts.

Stage 2 is not live in this v0. Draft generation remains future-gated and must not send, call, commit, launch, or mutate anything without the relevant gate.

## Stage 3: Safe read-only action rights

Stage 3 target:

```text
Winship says X -> system may perform safe read-only actions automatically, while risky actions route to explicit approval.
```

Future gated progression:

- read approved local receipts;
- summarize approved packet and handoff state;
- inspect exact allowed repo files when the request and policy permit it;
- never inspect private roots, live process state, service state, providers, MCP connectors, billing systems, legal roots, or external systems without a separate future gate.

Stage 3 is not live in this v0. This document only names the future lane.

## Stage 4: Earned bounded autonomy

Stage 4 target:

```text
Winship says X -> system may execute pre-approved low-risk lanes after earned trust, receipts, rollback, and gate checks.
```

Future gated progression:

- execute only pre-approved, low-risk lanes;
- require receipts, rollback or reversal boundaries, stop conditions, and audit trail;
- require exact lane scope and expiration;
- route any sensitive, external, destructive, runtime, MCP, provider, legal, money, private-root, or hidden-memory action to Level 5 restricted gates.

Stage 4 remains future-gated, not current authority.

## Intent map

Each intent records what the system should infer, what it should do now, and what future gate would be required before doing more.

| Intent | Example operator phrases | Inferred meaning | Correct response frame | Allowed behavior now | Future behavior after earned gates | Evidence/receipts to consult | Follow-up needed | Hard forbidden crossings |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| status_brief | "status"; "what changed?"; "give me the state" | Operator wants a short state snapshot. | Lead with current packet, repo cleanliness, changed files, receipt state, and blocked gates. | Point to static receipts and summarize only already-approved local evidence. | Auto-read Level 1 approved receipts and produce a concise brief. | `repo-check`, `packet-status`, `operator-harness-status`, active handoff. | Usually no, unless state is dirty or ambiguous. | No live process scan, MCP call, provider call, private-root read, or service status crawl. |
| next_safe_action | "what should we do next?"; "what is the safest move?"; "next step?" | Operator wants a recommended next move. | Name one next safe action, why it is safe, and what remains gated. | Use File 01 rails, active handoff train log, and relevant receipts. | Auto-prepare a bounded prompt or plan after Stage 2 gate. | File 01, active handoff, `operator-harness-status`, relevant lane receipt. | Follow up if multiple lanes have equal authority. | No mutation, launch, send, or hidden approval. |
| codex_prompt_request | "write the Codex prompt"; "give Codex the implementation task"; "make a coding prompt" | Operator wants a scoped Codex implementation prompt. | Produce bounded implementation prompt with allowed files, forbidden surfaces, validation, and review expectations. | Static prompt guidance only; no repo edit unless separately instructed in a Codex work session. | Generate draft prompt automatically under Level 2. | `prompt-pack-status`, File 14, File 06, active handoff. | Yes if scope/files/validation are unclear. | No broad refactor, no staging/commit/push, no live runtime/MCP/provider action. |
| gemini_review_request | "ask Gemini"; "get Gemini to review the plan"; "architecture review" | Operator wants planning, scope, risk, or architecture review. | Route to Gemini planning/review profile and make clear it cannot mutate repo or approve execution. | Prepare static review prompt guidance only. | Generate a Gemini review prompt under Level 2. | `prompt-pack-status`, File 14, File 01, relevant rail files. | Yes if review target is unclear. | No treating Gemini output as approval, no provider call in this v0, no repo mutation. |
| commit_review_request | "is this ready to commit?"; "review the diff"; "commit readiness" | Operator wants a diff/test/boundary review. | Use Codex review stance: findings first, changed files, tests, boundary leaks, READY/NOT_READY. | Static review framing only unless a separate Codex review task is authorized. | Generate or run bounded review workflow after Level 2/3 gates. | `repo-check`, `git diff --check`, targeted tests, `activation-evidence-status` when relevant. | Follow up if changed-file scope is unclear. | No commit before READY_TO_COMMIT review and explicit operator instruction; no push. |
| push_confirmation_context | "can I push?"; "should we push?"; "is this safe to send upstream?" | Operator wants external-publication context. | State commit state, remote/ahead status if already known, required final checks, and explicit push boundary. | Explain requirements; do not push. | Future Level 5 or separate GitHub/send gate may permit bounded push. | `repo-check`, post-commit receipts, review verdict. | Yes; push requires explicit approval. | No push, external send, credential use, or remote mutation from this v0. |
| handoff_request | "write the handoff"; "log this"; "where do we leave the train?" | Operator wants train-log or continuation context. | Produce concise handoff note: completed work, validation, next lane, gated surfaces, File 01 authority. | Static draft guidance; write only when explicitly scoped in a repo task. | Generate draft handoff under Level 2; mutate handoff under Level 3 with tests/receipts. | Active handoff, File 01, relevant receipt outputs. | Usually no if the completed milestone is clear. | No treating handoff as roadmap authority; no Packet 08 without approval. |
| activation_readiness_question | "can we move forward?"; "is activation ready?"; "are we launch-ready?" | Operator wants readiness versus authority separated. | Separate readiness evidence from approval; state current authorization status and next gate. | Read static readiness receipts only. | Stage 3 may auto-read approved receipts; Stage 4 still needs explicit activation gate. | `gated-activation-status`, `runtime-dry-run-readiness`, `activation-evidence-status`, `mcp-shared-memory-gate-status`. | Yes if "move forward" means live action. | No launch, process scan, service mutation, MCP call/write, provider call, invoice/legal/private-root action. |
| approval_required_action | "approve this"; "go ahead and launch"; "send it"; "commit it"; "turn it on" | Operator may be asking for an action that needs explicit gate checks. | Name the action-right level, required evidence, approval gate, and current non-authority if missing. | Refuse or request explicit approval and evidence; do not execute from this doc. | Execute only under the proper Level 3, 4, or 5 gate. | `activation-evidence-status`, targeted test receipt, relevant lane receipt, approval gate note. | Yes unless the current prompt already contains exact authority and gates. | No implied approval, no live activation, no external send, no destructive action, no private/sensitive action. |
| unsafe_or_ambiguous_action | "just handle it"; "do whatever"; "fix everything"; "use what you need" | Operator request is too broad or risky. | Narrow scope, identify risk, propose smallest safe next move, and ask for clarification if needed. | Static framing only. | Future gates may convert to bounded prompts or read-only receipt checks. | File 01, active handoff, relevant receipts. | Yes. | No broad cleanup, broad crawl, private-root read, hidden memory, external call, or authority expansion. |
| stop_or_wait_instruction | "stop"; "wait"; "pause"; "hold"; "do not continue" | Operator withdraws momentum or pauses execution. | Stop ongoing optional work, preserve state, report last safe state and pending next step. | Stop framing or edits as applicable; no new action. | Future runtime lanes must honor stop conditions and rollback boundaries. | Current task state, active handoff if a durable note is requested. | No, unless preserving state needs a chosen format. | No continuing because a previous prompt had momentum; no background action. |
| do_the_next_thing | "do the next thing"; "keep going"; "continue from here" | Operator wants progress but may not have named scope or authority. | Infer likely next safe lane, state the proposed action, and proceed only if it is already bounded and safe; otherwise ask for approval. | "do the next thing" is not execution authority. Static framing, prompt prep, or already-scoped repo work only. | Future Stage 3 may read approved receipts; Stage 4 may run pre-approved low-risk lanes only. | File 01, active handoff, `operator-harness-status`, relevant lane receipts. | Yes when the next thing would mutate, send, launch, inspect private state, or cross gates. | No hidden execution authority, launch, push, send, provider/MCP call, private-root read, invoice/legal action, or destructive operation. |
| send_that_to_codex | "send that to Codex"; "give this to Codex"; "Codex should do it" | Operator wants conversion into a Codex implementation task. | Produce Codex-ready prompt with scope, files, tests, boundaries, and expected final report. | Static prompt guidance only; no external send from this v0. | Level 2 prompt generation, then Level 3 bounded repo mutation in a Codex session. | `prompt-pack-status`, File 14, File 06, active handoff. | Yes if target task or allowed files are unclear. | No hidden send, no broad mutation, no commit/push without separate gate. |
| ask_gemini | "ask Gemini"; "run it by Gemini"; "get Gemini's take" | Operator wants planning, scope, architecture, or review perspective. | Convert into a Gemini planning/review prompt and note that model output is advice, not approval. | Static prompt guidance only; no provider call in this v0. | Level 2 can generate prompt; provider call requires separate future policy/gate. | `prompt-pack-status`, File 14, relevant rails. | Yes if review question is not clear. | No provider/API call, no repo mutation, no approval-by-model. |
| where_are_we | "where are we?"; "what's the state?"; "catch me up" | Operator wants low-context orientation. | Give concise repo, packet, handoff, validation, and next-lane summary. | Point to static receipts and known train-log state. | Stage 3 may auto-read approved receipts and summarize. | `repo-check`, `packet-status`, `operator-harness-status`, active handoff. | No unless repo is dirty or validation is stale. | No live scan, broad crawl, private-root inspection, provider/MCP call. |
| can_we_move_forward | "can we move forward?"; "is this safe to continue?"; "are we blocked?" | Operator wants a go/no-go distinction. | Say whether static evidence supports next dry step, and name the approval gate before anything riskier. | Static evidence framing only. | Stage 3 may gather approved receipts; Stage 4 still needs pre-approved lane authority. | `activation-evidence-status`, `gated-activation-status`, lane-specific receipt. | Yes if "forward" means live activation, send, commit, push, or private action. | No treating readiness as approval; no launch/send/provider/MCP/private/legal/invoice action. |
| make_my_life_easier | "make my life easier"; "reduce the burden"; "simplify this for me" | Operator wants burden reduction, not machinery. | Convert scattered state into one next safe action, one short prompt, or a concise decision frame. | Static framing and prompt/handoff preparation only. | Future Stage 3 can auto-read approved receipts; future Stage 4 can run pre-approved low-risk lanes. | File 05 North Star, File 06 operator experience, `operator-harness-status`. | Yes if the easiest action crosses a gate. | No hiding authority, no unsolicited external action, no broad automation. |
| tired_tell_me_what_matters | "I'm tired, just tell me what matters"; "only the important part"; "short version" | Operator wants attention protection and reduced cognitive load. | Give the smallest truthful brief: state, risk, next safe move, and what remains forbidden. | Static brief and evidence pointers only. | Future Stage 3 can auto-read approved receipts and compress them. | `operator-harness-status`, active handoff, relevant receipt. | No unless action is requested. | No omission of safety boundary when a risky gate is near; no hidden action. |

## Action-rights ladder

### Level 0 - Static framing only

- classify intent;
- explain next safe action;
- prepare prompts or handoffs as static guidance;
- no external calls;
- no runtime actions.

Current v0 authorization: yes.

### Level 1 - Read-only local evidence

- read approved receipts;
- summarize approved packet or handoff state;
- no mutation.

Current v0 authorization: future gated, not active.

### Level 2 - Draft/proposal generation

- generate Codex or Gemini prompts;
- generate draft handoffs;
- generate review plans;
- no commit, push, send, launch, or write without tool-specific gate.

Current v0 authorization: future gated, not active.

### Level 3 - Bounded repo mutation

- Codex may make explicitly scoped repo changes;
- tests required;
- review required;
- commit only after READY_TO_COMMIT review and operator instruction;
- no push.

Current v0 authorization: future gated, not active.

### Level 4 - Pre-approved low-risk execution

- only after future approval architecture exists;
- must have receipts, rollback, stop conditions, and audit trail;
- cannot include live runtime launch, MCP writes, invoice sends, legal/private-root action, provider calls, hidden memory writes, or external sends unless separately gated by future policy.

Current v0 authorization: future gated, not active.

### Level 5 - Restricted/high-risk actions

- money, legal, private data, external sending, runtime launch, connector writes, hidden memory, provider calls, destructive operations;
- always require explicit approval gate;
- not authorized by this v0.

Current v0 authorization: no.

## Approval and stop rules

- Approval must be explicit, scoped, evidence-backed, and tied to the relevant action-right level.
- Receipts and read models are evidence, not approval.
- A model recommendation is advice, not approval.
- Stale handoff state is not approval.
- "Do the next thing", "just handle it", and "make my life easier" are not execution authority.
- Stop, wait, pause, hold, or "do not continue" overrides prior momentum.
- Any uncertainty about authority routes to the smallest safe framing step or an approval question.

## Tool-specific routing

| Target | Use when | Current v0 behavior | Future gate before more |
| --- | --- | --- | --- |
| Operator response | The request needs a brief, next action, risk call, or stop response. | Frame intent and next safe move. | Level 1 for auto-reading receipts. |
| Codex implementation | The request is a bounded repo mutation. | Prepare scoped prompt guidance only. | Level 3 with allowed files, tests, review, and no push. |
| Codex commit-readiness review | The request asks whether a diff is safe to commit. | Frame review criteria only. | Level 3 review workflow; commit only after READY_TO_COMMIT and explicit instruction. |
| Gemini planning/review | The request needs architecture, scope, risk, or planning review. | Prepare Gemini prompt guidance only. | Level 2 prompt generation; provider call needs separate future policy. |
| Chief-style review | The request needs authority, gate, or stop-condition review. | Frame evidence and approval questions only. | Future approval architecture. |
| MCP/shared memory | The request asks to remember, share, or synchronize context. | Point to static MCP gate; no call or write. | Separate MCP/shared-memory gate with single-source-of-truth proof. |
| Runtime/activation | The request asks to launch, turn on, recover, or activate. | Point to dry-run readiness and activation evidence receipts; no launch. | Future activation gate with rollback and explicit approval. |

## Examples

Operator: "Where are we?"

Response frame: "Packet 07 is active. Repo state comes first, then packet/read-model receipts, then the next visible lane. I will keep this to state, risk, next safe action, and gated surfaces."

Operator: "Do the next thing."

Response frame: "I can infer the likely next safe lane and proceed only if it is already bounded and non-risky. This phrase is not authority to launch, send, push, inspect private roots, call providers/MCP, or mutate broad surfaces."

Operator: "Ask Gemini."

Response frame: "This routes to Gemini planning or review prompt guidance. In v0 I can draft the prompt shape, but I cannot call a provider or treat the answer as approval."

Operator: "Can we move forward?"

Response frame: "I will separate dry-run readiness from live authority. Static evidence may support the next dry step; any launch, send, MCP write, provider call, invoice/legal/private-root action, or destructive operation needs an explicit gate."

Operator: "I'm tired, just tell me what matters."

Response frame: "Give only the state, the risk, the next safe move, and what remains forbidden. Protect attention without hiding boundaries."

## Tests / receipt expectations

`./scripts/openclaw_receipts.py operator-intake-status` should prove:

- this document exists;
- Stage 1 through Stage 4 headings exist;
- the required intent classes exist;
- the action-rights ladder exists;
- "do the next thing" is not execution authority;
- Stage 4 is future-gated, not current authority;
- Level 5 restricted/high-risk actions remain restricted;
- the receipt does not imply runtime activation, provider calls, MCP calls, external sends, commits, pushes, hidden memory writes, or live autonomy are authorized.

The receipt is static proof only. It is not a live classifier, prompt generator, action router, approval engine, or daemon.

## Remaining risks

- Future agents may overread natural language as action authority unless the receipt and tests keep the boundary explicit.
- Stage 2 prompt generation could become noisy if it ignores File 14 tool-specific doctrine.
- Stage 3 read-only actions need a tight approved-source list before any automatic reads.
- Stage 4 needs a real future approval architecture with rollback and stop conditions before any execution.
- Operator burden is reduced only if examples stay practical and status surfaces stay sparse.
