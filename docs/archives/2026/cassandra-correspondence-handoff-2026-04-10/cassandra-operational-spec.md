# Agentic Messaging Operational Spec

## Summary
This document operationalizes the pilot playbook into two concrete components:
1. a **system prompt + JSON schema** for the drafting agent
2. a **review queue spec / UI field list** for human approval

This spec assumes the safer pilot shape:
- **1–3 trusted recipients only**
- **draft-first** workflow
- **human approval before every send**
- **anticipatory response preparation enabled**
- **no autonomous conversation**

---

## 1. Drafting agent system prompt

```text
You are the drafting agent for an approval-gated inner-circle correspondence pilot.

Your job is to produce outbound message drafts that are authentic, low-pressure, and grounded only in the supplied context. You are not the sender. You do not send messages. You prepare drafts and response options for human review.

Operating rules:
- Treat trust as the primary objective.
- Prefer clarity, brevity, and relationship-appropriate tone over polish.
- Do not invent history, commitments, facts, or emotional nuance.
- Do not imply urgency, intimacy, certainty, or familiarity beyond the supplied context.
- Do not optimize for persuasion or response rate at the expense of authenticity.
- If context is missing, ambiguous, or the topic appears sensitive, explicitly say so.
- When risk is non-trivial, recommend hold or manual-only.
- Keep asks easy to decline.
- Preserve the sender's likely voice as a slightly more organized version of them, not a more polished stranger.
- Generate only the minimum number of drafts needed for useful review.

Pilot scope:
- allowlisted recipients only
- 1–3 trusted recipients in initial rollout
- safe categories only unless the human explicitly overrides
- no autonomous send
- no emotionally loaded, legal, financial, personnel, or repair conversations

Allowed message categories in the initial pilot:
- logistics
- lightweight follow-up
- check-in
- share/update
- gratitude
- lightweight ask

Manual-only / escalate categories:
- apology or repair
- conflict
- legal, financial, or commitment-bearing content
- emotionally loaded topics
- ambiguous personal/romantic topics
- high-stakes introductions
- anything that could cause material downside if screenshotted or forwarded

You must produce structured JSON matching the required schema.

Risk rules:
- low risk: routine, grounded in thread, low emotional charge, low downside if awkward
- medium risk: ask, long silence, interpretive wording matters, or possibility of over-reading intent
- high risk: emotional, social, financial, legal, reputational, or power-sensitive

Escalation rules:
- If any high-risk criterion is met, set recommendation to manual_only or hold.
- If important context is missing, include it in missing_context and lower confidence.
- If you cannot support a factual statement from the provided context, do not include it in the draft.

Drafting rules:
- Prefer one primary draft and one shorter alternative.
- The draft should be short unless the context clearly requires length.
- Avoid sales-like cadence, over-explaining, and synthetic enthusiasm.
- Avoid false intimacy and over-specific emotional language.
- If there is an ask, make it specific and easy to decline.
- If the best action is not to send, say so.

Response-prep rules:
- Prepare only the most plausible branches.
- Suggested responses should usually be shorter than the outbound.
- Include no-reply follow-up guidance only when appropriate.
- Do not script extended emotionally sensitive exchanges.

Output requirements:
- Return valid JSON only.
- Include risk, assumptions, missing context, flags, recommendation, drafts, and response branches.
- Keep flag text concrete and reviewable.
- Do not include hidden reasoning.
```

---

## 2. Drafting agent input contract

The drafting agent should receive one payload per requested outbound message.

### Required input fields

```json
{
  "request_id": "msgreq_001",
  "recipient": {
    "recipient_id": "person_001",
    "name": "Alex",
    "relationship_tier": "inner_circle",
    "allowlisted": true,
    "preferred_address": "Alex"
  },
  "message": {
    "category": "follow_up",
    "objective": "Nudge on prior thread about meeting next week",
    "why_now": "No reply for 5 days and scheduling matters",
    "tone_preset": "warm_minimal",
    "desired_cta": "Confirm whether Tuesday still works",
    "constraints": [
      "Do not sound pushy",
      "Do not imply urgency beyond scheduling need"
    ]
  },
  "context": {
    "thread_summary": "Last exchange was about finding time next week.",
    "source_snippets": [
      "You mentioned Tuesday afternoon might work.",
      "I said I was flexible after 2pm."
    ],
    "last_contact_age_days": 5,
    "relationship_state": "normal",
    "known_sensitivities": [],
    "do_not_reference": []
  },
  "policy": {
    "pilot_phase": "v1",
    "autonomous_send_allowed": false,
    "manual_only_categories": [
      "repair",
      "conflict",
      "financial",
      "legal",
      "emotional"
    ]
  }
}
```

---

## 3. Drafting agent JSON schema

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "AgenticMessagingDraftOutput",
  "type": "object",
  "additionalProperties": false,
  "required": [
    "request_id",
    "recipient_id",
    "category",
    "objective",
    "risk_level",
    "confidence",
    "assumptions",
    "missing_context",
    "flags",
    "recommendation",
    "primary_draft",
    "shorter_alt",
    "response_branches"
  ],
  "properties": {
    "request_id": {
      "type": "string"
    },
    "recipient_id": {
      "type": "string"
    },
    "category": {
      "type": "string",
      "enum": [
        "logistics",
        "follow_up",
        "check_in",
        "share_update",
        "gratitude",
        "lightweight_ask",
        "introduction",
        "repair",
        "conflict",
        "financial",
        "legal",
        "emotional",
        "other"
      ]
    },
    "objective": {
      "type": "string",
      "minLength": 1
    },
    "risk_level": {
      "type": "string",
      "enum": ["low", "medium", "high"]
    },
    "confidence": {
      "type": "number",
      "minimum": 0,
      "maximum": 1
    },
    "assumptions": {
      "type": "array",
      "items": { "type": "string" }
    },
    "missing_context": {
      "type": "array",
      "items": { "type": "string" }
    },
    "flags": {
      "type": "array",
      "items": {
        "type": "object",
        "additionalProperties": false,
        "required": ["code", "severity", "message"],
        "properties": {
          "code": {
            "type": "string",
            "enum": [
              "missing_context",
              "unsupported_claim",
              "tone_risk",
              "false_intimacy_risk",
              "pressure_risk",
              "sensitivity_risk",
              "scope_violation",
              "allowlist_violation",
              "followup_risk",
              "ambiguity_risk"
            ]
          },
          "severity": {
            "type": "string",
            "enum": ["info", "warning", "critical"]
          },
          "message": {
            "type": "string"
          }
        }
      }
    },
    "recommendation": {
      "type": "string",
      "enum": ["send", "edit", "hold", "manual_only"]
    },
    "primary_draft": {
      "type": "string"
    },
    "shorter_alt": {
      "type": "string"
    },
    "response_branches": {
      "type": "object",
      "additionalProperties": false,
      "required": ["positive", "neutral", "decline", "no_reply"],
      "properties": {
        "positive": {
          "$ref": "#/$defs/replyBranch"
        },
        "neutral": {
          "$ref": "#/$defs/replyBranch"
        },
        "decline": {
          "$ref": "#/$defs/replyBranch"
        },
        "no_reply": {
          "type": "object",
          "additionalProperties": false,
          "required": ["suggested_follow_up", "follow_up_timing", "should_follow_up"],
          "properties": {
            "suggested_follow_up": { "type": "string" },
            "follow_up_timing": { "type": "string" },
            "should_follow_up": { "type": "boolean" }
          }
        }
      }
    }
  },
  "$defs": {
    "replyBranch": {
      "type": "object",
      "additionalProperties": false,
      "required": ["likely_reply", "suggested_response"],
      "properties": {
        "likely_reply": { "type": "string" },
        "suggested_response": { "type": "string" }
      }
    }
  }
}
```

---

## 4. Recommended flag meanings

| Code | Meaning | Typical reviewer action |
|---|---|---|
| missing_context | Key input needed for safe drafting is absent | Edit input or hold |
| unsupported_claim | Draft may assert something not supported by source context | Remove or rewrite |
| tone_risk | Tone may be too formal, too warm, too cold, or mismatched | Edit tone |
| false_intimacy_risk | Message may imply more closeness than intended | Reduce warmth/intimacy |
| pressure_risk | Ask may feel too pushy or hard to decline | Soften or narrow ask |
| sensitivity_risk | Topic may be outside pilot-safe scope | Manual-only or hold |
| scope_violation | Category or content violates pilot rules | Reject or manual-only |
| allowlist_violation | Recipient is outside approved pilot scope | Do not draft/send |
| followup_risk | Suggested follow-up timing may be too aggressive | Delay or remove follow-up |
| ambiguity_risk | Wording may be interpreted multiple ways | Clarify or simplify |

---

## 5. Example output

```json
{
  "request_id": "msgreq_001",
  "recipient_id": "person_001",
  "category": "follow_up",
  "objective": "Nudge on prior thread about meeting next week",
  "risk_level": "low",
  "confidence": 0.84,
  "assumptions": [
    "Tuesday is still a live option",
    "A brief follow-up is socially normal in this relationship"
  ],
  "missing_context": [],
  "flags": [],
  "recommendation": "send",
  "primary_draft": "Hey Alex — just following up on next week. Does Tuesday afternoon still work for you?",
  "shorter_alt": "Hey Alex — does Tuesday afternoon still work for next week?",
  "response_branches": {
    "positive": {
      "likely_reply": "Yes, Tuesday works.",
      "suggested_response": "Great — Tuesday works for me too. After 2pm is still easiest on my side."
    },
    "neutral": {
      "likely_reply": "Maybe, need to check.",
      "suggested_response": "No rush — just let me know when you have a better sense."
    },
    "decline": {
      "likely_reply": "Tuesday won’t work after all.",
      "suggested_response": "No problem — happy to find another time if useful."
    },
    "no_reply": {
      "suggested_follow_up": "Hey Alex — just bumping this once in case it got buried. Happy to leave it here if timing is bad.",
      "follow_up_timing": "2-3 days if scheduling is time-sensitive",
      "should_follow_up": true
    }
  }
}
```

---

## 6. Review queue spec

The review queue is the human-control layer. Its job is to make approval fast **without hiding risk**.

### Queue-level goals
- show the minimum information required for safe approval
- surface risk before polish
- make “edit”, “hold”, and “manual-only” as easy as “approve”
- preserve an audit trail

### Queue item states
- `drafted`
- `needs_review`
- `approved`
- `edited_and_approved`
- `held`
- `rejected`
- `manual_only`
- `sent`
- `closed`

### Queue-level columns
Each row in the review queue should show:
- request ID
- recipient name
- relationship tier
- category
- objective (short)
- risk level
- recommendation
- flag count
- confidence
- last contact age
- created time
- status

Recommended sort order:
1. critical flags first
2. medium/high risk next
3. oldest pending next
4. low-risk logistics last

---

## 7. Review pane UI field list

When a reviewer opens one queue item, show these sections.

### A. Header
- request ID
- recipient name
- relationship tier
- allowlist status
- status
- created timestamp
- last updated timestamp

### B. Intent and scope
- message category
- objective
- why now
- desired CTA
- tone preset
- pilot phase

### C. Context panel
- thread summary
- source snippets / source messages
- last contact age (days)
- relationship state
- known sensitivities
- do-not-reference list
- constraints / do-not-say items

### D. Risk panel
- risk level
- confidence score
- recommendation
- flags list with severity badges
- missing context list
- assumptions list

### E. Draft panel
- primary draft (editable text area)
- shorter alt draft
- diff view if edited after generation
- character count / word count

### F. Response-prep panel
- likely positive reply + suggested response
- likely neutral reply + suggested response
- likely decline reply + suggested response
- no-reply follow-up recommendation + timing

### G. Reviewer actions
Primary actions:
- Approve as-is
- Edit and approve
- Hold
- Reject
- Mark manual-only
- Regenerate

Secondary actions:
- Change tone preset
- Change category
- Request missing context
- Disable follow-up suggestion
- Copy draft
- Export audit record

### H. Reviewer notes
- freeform reviewer note
- reason code for hold/reject/manual-only
- post-send lesson

---

## 8. Suggested reason codes

### Hold / reject / manual-only reason codes
- missing_context
- unsupported_claim
- too_sensitive
- tone_mismatch
- too_long
- too_pushy
- false_intimacy
- not_worth_sending
- wrong_category
- recipient_out_of_scope
- needs_human_rewrite

These reason codes are useful for prompt tuning and policy refinement later.

---

## 9. Minimum audit log schema

Every reviewed item should write an audit record with:

```json
{
  "request_id": "msgreq_001",
  "recipient_id": "person_001",
  "status": "edited_and_approved",
  "reviewer_action": "edit_and_approve",
  "generated_at": "2026-04-10T12:00:00Z",
  "reviewed_at": "2026-04-10T12:05:00Z",
  "risk_level": "low",
  "recommendation": "send",
  "flags": [],
  "primary_draft_original": "Hey Alex — just following up on next week. Does Tuesday afternoon still work for you?",
  "primary_draft_final": "Hey Alex — just checking whether Tuesday afternoon still works for next week.",
  "edit_distance_note": "light",
  "reason_codes": [],
  "reviewer_note": "Trimmed slightly to sound more natural.",
  "sent": true,
  "outcome_48h": "replied_positive",
  "outcome_7d": "scheduled"
}
```

---

## 10. Recommended implementation defaults

### Drafting defaults
- generate one primary draft + one shorter alt
- default tone preset = `warm_minimal`
- default recommendation threshold:
  - `manual_only` for high risk
  - `hold` if missing context materially affects safety
  - `edit` if tone/clarity issues are minor
  - `send` only when clearly low risk and grounded

### Review defaults
- queue filter defaults to `needs_review`
- show risk panel above draft panel
- show source snippets before approve button
- require explicit reviewer click for send handoff
- prefill reason codes on hold/reject/manual-only

### Pilot defaults
- recipients limited to 1–3 trusted people
- safe categories only
- max one follow-up suggestion by default
- no autonomous send
- no autonomous reply sending

---

## 11. Operational acceptance criteria

This setup is working if:
- reviewers can approve or reject quickly without losing context
- risk and missing context are visible before send
- edit deltas shrink over time
- false intimacy and unsupported claims are caught early
- response prep is useful but not overbearing
- the team can explain exactly why any message was approved

This setup is not ready to expand if:
- frequent manual-only escalations happen in supposedly safe categories
- reviewers routinely rewrite entire drafts
- flags are noisy or ignored
- awkwardness or trust issues appear in recipient responses

---

## 12. Immediate next build order

1. Implement the JSON schema validator.
2. Wire the drafting agent to the system prompt above.
3. Build the review queue table with the queue-level columns.
4. Build the single-item review pane with editable draft field and risk panel.
5. Write audit records for every reviewer action.
6. Run the pilot with **1–3 trusted recipients only**.

---

## Sources
- Internal operationalization of the previously created pilot playbook in this workspace.
- Updated pilot constraint from the user: “Start with 1–3 trusted recipients.”
