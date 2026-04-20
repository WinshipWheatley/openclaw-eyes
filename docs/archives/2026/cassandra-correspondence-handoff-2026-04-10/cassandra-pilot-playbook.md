# Approval-Gated Pilot for Inner-Circle Correspondence

## Summary
This playbook is for a **draft-first, human-in-the-loop rollout with anticipatory response preparation**. The goal is to improve speed and consistency for trusted-recipient messaging **without sacrificing authenticity, judgment, or relationship quality**.

**Operating stance:**
- All outbound messages are **human-approved before send**.
- The pilot is limited to a small **allowlisted inner circle**.
- The system may prepare likely replies and suggested responses, but it does **not** autonomously converse.
- Success is measured by **trust, edit efficiency, and relationship quality**, not raw reply rate.

---

## 1. Objectives and non-objectives

### Objectives
1. Reduce time-to-draft for routine, low-risk correspondence.
2. Preserve your authentic voice while making messaging more deliberate.
3. Prepare likely responses in advance so follow-up latency drops.
4. Build a learning loop from edits, approvals, and outcomes.
5. Contain risk with tight scope, clear policy, and abstention rules.

### Non-objectives
- Maximizing response rate at any cost.
- Fully autonomous outreach.
- Automating sensitive or high-stakes conversations.
- Simulating intimacy or emotional precision you did not explicitly intend.

---

## 2. First-principles design

### Principle 1: Optimize for trust before scale
A messaging agent is not just a text generator; it is a **relationship-facing system**. Trust loss is more expensive than time saved.

### Principle 2: Start with narrow permissions
Begin with:
- known recipients
- strong prior relationship context
- low-stakes use cases
- explicit send approval
- complete auditability

### Principle 3: Separate drafting from sending
Keep these functions distinct:
1. **Context assembly**
2. **Draft generation**
3. **Human approval/edit**
4. **Response preparation**
5. **Learning/logging**

### Principle 4: Reward abstention
A good system should often say:
- “Needs more context”
- “This seems sensitive”
- “Recommend manual writing”
- “Recommend hold/no-send”

### Principle 5: Expand one axis at a time
After the pilot starts, only expand **one** of these at once:
- recipient set
- message category
- autonomy level
- cadence/volume

---

## 3. Scope for the initial pilot

### Pilot audience
Start with **1–3 trusted recipients**.

Recommended attributes:
- already familiar with your natural style
- likely to forgive awkward drafts
- not currently in conflict with you
- not part of a high-stakes negotiation
- communication norms are already established

### Safe message categories for v1
- scheduling / logistics
- quick check-ins
- follow-ups on prior threads
- sharing a relevant update or link
- gratitude / acknowledgment
- lightweight asks with easy opt-out

### Categories excluded from v1
- conflict or repair conversations
- money/legal commitments
- hiring/firing or personnel issues
- emotionally loaded topics
- ambiguous personal or romantic messaging
- high-leverage intros where wording materially affects outcomes
- anything you would worry about being screenshotted out of context

---

## 4. Canonical workflow

### Stage A: Intake / context assembly
For every message request, capture:
- **Recipient**
- **Relationship tier**
- **Objective**
- **Why now**
- **Relevant thread/context**
- **Tone preset**
- **Constraints / do-not-say items**
- **Desired CTA** (if any)
- **Latest relationship state** (e.g. “haven’t replied in 2 weeks”)

If any of these is missing, the system should explicitly mark the gaps.

### Stage B: Draft generation
Generate:
- primary draft
- shorter variant
- optional warmer/directer variant
- assumptions made
- risk score
- flags for unsupported claims, awkward phrasing, over-familiarity, pressure, or ambiguity

### Stage C: Human approval
The reviewer can:
- approve as-is
- edit and approve
- reject
- regenerate
- hold
- mark manual-only

### Stage D: Anticipatory response preparation
Before sending, generate:
- likely positive reply
- likely neutral reply
- likely delayed/no-reply path
- likely decline/confusion path
- suggested responses for each
- recommended follow-up timing if no response

### Stage E: Logging and learning
Store:
- original context
- generated draft(s)
- final sent version
- edit delta
- outcome after 48h and 7d
- lessons learned

---

## 5. Approval policy

### Hard rules
1. **No autonomous send.**
2. **No outreach to non-allowlisted recipients without explicit approval.**
3. **No unsupported references to prior conversations, commitments, or facts.**
4. **No emotional intensification beyond the source context.**
5. **No manufactured urgency or pressure tactics.**
6. **No commitments on time, money, access, or decisions unless directly provided by you.**
7. **No attempts to mimic intimacy, vulnerability, or warmth that you would not naturally express yourself.**

### Approval display requirements
Every proposed message should show:
- recipient
- objective
- message category
- draft
- shorter alt draft
- assumptions
- risk score
- flags
- likely replies
- recommended next step

### Default approval standard
A draft should only be sent if all are true:
- factually grounded in supplied context
- proportionate to the relationship
- easy to understand
- easy to decline if it includes an ask
- consistent with your real voice
- low enough risk for pilot scope

---

## 6. Message taxonomy

| Category | Description | Pilot status | Approval bar |
|---|---|---:|---|
| Logistics | Scheduling, confirmations, practical coordination | Allowed | Low |
| Follow-up | Nudges on existing threads | Allowed | Low |
| Reconnect | Light touch-base with context | Allowed carefully | Medium |
| Gratitude | Thanks, acknowledgment | Allowed | Low |
| Share/update | Sending relevant link/update | Allowed | Low |
| Ask | Lightweight request | Allowed carefully | Medium |
| Introduction | Connecting two people | Not in v1 unless highly routine | High |
| Sensitive feedback | Personal/professional critique | Excluded | Very high |
| Commitment-bearing | Deadlines, money, promises | Excluded | Very high |
| Emotional repair | Apologies, conflict, trust repair | Excluded | Very high |

---

## 7. Risk rubric

### Low risk
- routine
- low emotional charge
- grounded in recent thread
- no hard commitment
- low reputational downside if awkward

### Medium risk
- light ask with asymmetry
- substantial delay since last contact
- interpretive wording matters
- recipient could infer more intent than intended

### High risk
- emotional, financial, legal, social, or reputational stakes
- ambiguous relationship dynamics
- recipient status/power differential makes wording sensitive
- message could be forwarded/screenshotted with downside

### Auto-escalate to manual-only if any are true
- apology or repair
- negotiation
- emotionally charged topic
- commitment or promise
- reference to private/sensitive information
- uncertainty about what the recipient knows
- strong tone ambiguity

---

## 8. Tone presets

Use explicit presets rather than freeform style prompting.

### Warm-minimal
Short, natural, friendly, no flourish.

### Concise-professional
Direct, clear, respectful, efficient.

### Casual-familiar
Relaxed, conversational, slightly informal.

### Thoughtful-longform
Use sparingly; only when context warrants a fuller note.

### Deferential-ask
For requests where you want to reduce pressure and make decline easy.

**Rule:** default to the lowest-intensity tone that still fits the relationship.

---

## 9. Drafting spec

For each requested outbound message, the system should output this structure:

```yaml
recipient:
relationship_tier:
objective:
category:
why_now:
tone_preset:
risk_level:
assumptions:
missing_context:
flags:
recommendation: send | edit | hold | manual-only
primary_draft:
shorter_alt:
response_branches:
  positive:
    likely_reply:
    suggested_response:
  neutral:
    likely_reply:
    suggested_response:
  decline:
    likely_reply:
    suggested_response:
  no_reply:
    suggested_follow_up:
    follow_up_timing:
```

---

## 10. Review checklist

Before approving any message, ask:
1. Is every factual statement grounded in supplied context?
2. Is the tone proportionate to the relationship?
3. Does this sound like me on a good day, not a synthetic high-polish version of me?
4. Is the ask easy to decline?
5. Is there any manipulative pressure, implied urgency, or false intimacy?
6. Is the message shorter than or equal to the minimum useful length?
7. Would I be comfortable if this were forwarded or screenshotted?
8. If they reply unexpectedly, do I have a prepared path?

If any answer is “no,” revise or hold.

---

## 11. Response-prep playbook

For each outbound, prepare only the most plausible branches.

### Standard branches
- positive acceptance
- neutral acknowledgment
- delayed response
- no response
- polite decline
- confusion / asks for clarification

### Response guidelines
- keep suggested replies shorter than the outbound unless context demands otherwise
- avoid overcompensating with warmth
- make next steps explicit when useful
- do not script emotionally loaded back-and-forths for excluded categories

### Example no-reply logic
- logistics: follow up after 24–72h if time-sensitive
- lightweight ask: follow up after 5–7d max once
- reconnect note: often no follow-up needed

---

## 12. Metrics

### Primary metrics
- **Approval rate**: % approved without changes
- **Light-edit rate**: % approved with minor edits
- **Reject/manual-only rate**
- **Average edit distance** between generated and sent draft
- **Response-prep usefulness** (1–5)
- **Your confidence before send** (1–5)

### Relationship health metrics
- recipient confusion incidents
- awkwardness/mismatch incidents
- observed warmth or responsiveness trend
- any explicit negative feedback

### Safety metrics
- unsupported claims caught in review
- taxonomy violations
- recipients outside allowlist attempted
- messages escalated for sensitivity

### Metrics to avoid over-weighting
- raw response rate
- reply speed alone
- “conversion” framing for close relationships

---

## 13. Recommended rollout plan

### Week 0: Manual baseline
Collect 20–30 manually written examples with:
- recipient type
- objective
- draft
- final sent version
- response outcome
- what you would have liked auto-prepared

### Weeks 1–2: Draft-only pilot
- 1–3 trusted recipients
- 2–3 safe categories
- all sends approved manually
- log edits and outcomes

### Weeks 3–4: Structured approval queue
- add risk scoring, assumptions, response branches, and hold/manual-only recommendations
- keep scope fixed
- review weekly

### Expansion rule
Only expand if all are true:
- low error rate
- no serious trust incidents
- edits getting smaller
- response prep is consistently useful
- no drift into excluded categories

Then expand **either** recipient set **or** category set, not both.

---

## 14. Failure modes and guardrails

### False intimacy
**Failure:** sounds more emotionally tuned than you intended.
**Guardrail:** prefer understatement; require explicit human-supplied emotional content.

### Context hallucination
**Failure:** invents history, promises, or shared knowledge.
**Guardrail:** internal requirement that every claim be source-grounded.

### Over-persuasion
**Failure:** language optimized to push for response/compliance.
**Guardrail:** asks must be low-pressure and easy to decline.

### Tone drift
**Failure:** all messages start sounding like the same polished assistant.
**Guardrail:** preserve your natural brevity and asymmetry; compare against real prior messages.

### Scope creep
**Failure:** pilot slowly absorbs sensitive use cases.
**Guardrail:** explicit excluded categories and auto-escalation triggers.

---

## 15. Recommended prompt template

```text
You are drafting an outbound message for a trusted inner-circle recipient.
Your job is to produce a draft that is authentic, low-pressure, and grounded only in the supplied context.

Constraints:
- Do not invent history, commitments, or emotional nuance.
- Do not increase intimacy, urgency, or persuasion beyond the source context.
- Prefer brevity and clarity.
- If context is insufficient or the message seems sensitive, recommend manual-only.

Inputs:
- Recipient: {recipient}
- Relationship tier: {relationship_tier}
- Objective: {objective}
- Why now: {why_now}
- Category: {category}
- Tone preset: {tone_preset}
- Relevant context/thread: {context}
- Constraints / do-not-say: {constraints}

Output:
1. Risk level
2. Assumptions
3. Missing context
4. Flags
5. Recommendation: send / edit / hold / manual-only
6. Primary draft
7. Shorter alt draft
8. Likely reply branches and suggested responses
```

---

## 16. Operating defaults

These should be the default settings:
- allowlist only
- no autonomous send
- max one follow-up unless you explicitly request otherwise
- default tone = warm-minimal
- default output includes assumptions and risk flags
- default action on ambiguity = hold or manual-only
- default ask framing = easy to decline
- default logging on every message

---

## 17. What a good pilot looks like after the first month

You should be able to say:
- drafts are usually directionally correct
- you catch issues early because metadata makes review easy
- your edits are getting smaller
- nobody has noticed weird tone drift
- response preparation meaningfully reduces friction
- the system abstains appropriately when context is weak or stakes are too high

If you cannot say those things, do not expand scope.

---

## 18. Immediate next steps

1. Pick 1–3 allowlisted recipients.
2. Pick 2–3 message categories for v1.
3. Define your default tone presets.
4. Gather 20–30 baseline messages you wrote manually.
5. Implement the structured output format above.
6. Start logging draft vs final vs outcome.
7. Review the pilot weekly for trust, quality, and scope drift.

---

## Sources
- This document is a first-principles operating spec derived from the user’s requested setup pattern; no external factual claims requiring web citation were introduced.
