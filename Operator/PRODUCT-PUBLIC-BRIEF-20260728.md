# OpenClaw public brief — external-lane safe

Derived from the canonical artifacts on the governed board. This projection exists so
an external model lane can answer the standing acceptance questions without any
private content crossing the boundary.

**Excluded by construction:** client and counterparty names, monetary amounts,
account or address identifiers, operator identity, destination addresses, credentials,
and anything describing a gated action as available. Nothing here grants authority;
every gate named below stays exactly as it is.

## 1. Owner-first product hypothesis

The strongest idea already built is **provable delegation**: an assistant can hold
real-world authority bound to an exact artifact, in a way that survives an adversary
and proves afterwards what was authorised and what happened.

Authority binds to bytes, not to intent. The grant is one-time, scope-bound and
expiry-bound. It is re-verified at the moment of effect, and drift is a refusal rather
than a re-prompt, because re-prompting is how a tired person approves version two.

## 2. Smallest v1 that earns trust

One repeating work item, one channel, one owner. The system prepares a draft, previews
it with a single-use token, the owner replies with that token, and the release is
re-verified against the draft before anything leaves.

Trust is earned by the refusals, not the sends. Editing the draft after preview and
watching the approval fail teaches more than fifty successful sends.

## 3. Top blocker before it is useful

Agent identity on the messaging surface, ahead of everything else, because it is the
only defect that has already misdirected a message to the wrong chat. Second is
evidence delivery: a selected artifact whose contents do not reach the answering turn.

Ordered on evidence from a six-agent acceptance run, not on prior assumption.

## 4. External-send exact-approval rule

An external send requires an exact, scope-bound approval naming that one artifact.
Approval is verified again immediately before release; any change to the destination
set, subject, body or attachments voids it. Message channels may carry an approval and
can never be one.

The client-voice agent drafts and stages only. It never releases, and the send gate is
enforced below it rather than by it.

## 5. Exact-send failure cause and commit evidence

The exact-send suite showed red for ten days while the gate itself was working. The
fixture pinned an absolute approval window that lapsed; tests driving the live clock
failed while the gate correctly refused an expired grant.

The fix anchored the window relatively and added a guard that fails if the fixture
ever rots again. A stale red is expensive in its own way: it teaches people to route
around a control that works.

## 6. Readiness evidence and next safe action

Working today: the kill-switch brake, the exact-send approval gate, messaging identity
proven by live audit, an approval interlock at the outbound boundary, named failure
reasons in place of generic retries, and retrieval status carried end to end.

Not yet proven: one live end-to-end approved send. Next safe action is a rehearsal
that clears every gate and performs no send.

## 7. Guardian refusal rule

Refusals name what was checked and why it failed. An unreadable or absent control is
treated as active, never as permission. A verifier that returns "unknown" is treated
as "no".

Nothing is approved by default, silence is never consent, and a refusal is an outcome
rather than an error.

## 8. Delivery proof distinction

Dispatch is not delivery. A doorbell firing proves a signal was emitted; it does not
prove the far side received or acted on it. Delivery is proven only by an
acknowledgement written by the far side.

Message delivery between agents is currently assumed, not proven, and that gap is
tracked rather than assumed closed.
