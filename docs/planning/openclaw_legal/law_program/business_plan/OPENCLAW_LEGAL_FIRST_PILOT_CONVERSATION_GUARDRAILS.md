# OpenClaw Legal First Pilot Conversation Guardrails

## Purpose

This is an internal script and checklist for an exploratory first conversation with a possible OpenClaw Legal pilot firm.

It is not buyer-facing sales copy, not a final offer, not a contract, not legal advice, and not emergency support. It exists to help Winship keep the conversation useful, bounded, and honest.

The goal of the call is to learn whether the firm has a narrow discovery workflow worth exploring. The goal is not to sell a production deployment or accept a paid pilot on the call.

## Allowed opening posture

Use this posture:

```text
OpenClaw Legal is a promising local-first discovery workflow concept for small firms. I can discuss a narrow first-pilot shape and, if useful, show a synthetic/public demo. Any paid pilot would require written scope, support, data, hardware, backup, offboarding, attorney-review, and payment terms first.
```

Keep the tone calm and operational. The conversation is exploratory. Do not frame it as a launch, final offer, production deployment, or legal-automation product.

## Exact things Winship can safely say

Safe phrases:

- "This is about private local discovery infrastructure, not replacing lawyers."
- "The first possible pilot would be narrow: one firm, one scoped workflow, one primary machine, one local vault, and agreed file types only."
- "A synthetic/public demo can be shown with no real matter data. `Run Synthetic Dry Run` is allowed only under the synthetic demo validation package, fixed synthetic values, and sanitized status-only output."
- "Paid pilot planning is conditional on written scope, support, hardware, data, backup, offboarding, attorney-review, and payment terms."
- "Supported and unsupported file types have to be written down before any pilot."
- "Outputs are review aids. Attorneys remain responsible for legal judgment, privilege decisions, completeness decisions, and final use."
- "Support would need a written window and written boundaries."
- "If a problem requires raw matter access, the default answer is to pause and find a safer diagnostic path."
- "Real deployment is not approved yet."

Use these phrases only if they match the current source docs and current built proof.

## Exact things Winship must not say

Do not say or imply:

- "This is ready for production."
- "This replaces your e-discovery platform."
- "This can handle every file type."
- "This gives legal advice."
- "This can make privilege calls."
- "This can tell you what the evidence means legally."
- "I can be available for court-deadline emergencies."
- "Just send me the discovery."
- "I can remote in and look at the raw matter files by default."
- "Broader Run/Reset GUI controls are part of the pilot."
- "Real-matter GUI Run is available."
- "Connect, queue/ETA, model distribution, timelines, contradictions, privilege screening, email/cloud connectors, or broad OCR/media support are included now."
- "We can figure out scope, support, hardware, backups, and offboarding later."
- "This call is a final offer."

If the firm needs any of those promises, stop and move to no-go/pause.

## Discovery/workflow questions to ask

Ask plain workflow questions:

- How do you receive discovery today?
- Where do files live after download?
- Who is responsible for organizing and processing them?
- How do attorneys know what has been processed?
- How do staff know what failed, what is unsupported, and what still needs review?
- What is the smallest recurring discovery workflow that causes real pain?
- What would make a local workflow useful enough to test?
- What current tools are used, and where do they feel too expensive, opaque, or heavy?
- What would count as a successful narrow first pilot?

Do not ask for matter facts, privileged content, client names, filenames, or raw documents on the call.

## Budget/hardware/support questions to ask

Ask business-boundary questions:

- Is there a real budget for setup and support?
- Would the firm own or fund production hardware?
- Is the firm comfortable with a local vault workflow?
- Who would own backups, retention, restore testing, and offboarding?
- What support window would be realistic?
- What response expectations would the firm have?
- Would the firm accept that custom handlers, extra training, extra configuration, and extra nodes are paid separately?
- Would the firm accept no emergency support unless separately written, priced, and approved?
- Who at the firm would review and approve outputs before use?

If budget, hardware, support, or responsibility answers are vague, keep the conversation exploratory only.

## File-type/scope questions to ask

Ask scope questions before talking about price or pilot timing:

- What file types cause the most pain?
- Which file types are truly required for the first workflow?
- Are `.txt`, `.md`, text-layer `.pdf`, and verified local image OCR enough for a narrow first pilot?
- Are scanned PDFs, video, audio, email archives, phone dumps, proprietary exports, or broad media workflows required immediately?
- Can unsupported, failed, or no-text files be handled through a written Alternative Methods process instead of emergency support?
- Can the first workflow be limited to one matter or one recurring workflow?
- Can roadmap items stay clearly outside the first pilot unless separately scoped and priced?

If unsupported critical file types are required immediately, stop the pilot path unless the scope is rewritten and separately priced.

## Red-flag responses that stop the conversation

Stop or pause if the firm says or implies:

- "Can you just fix this before court tomorrow?"
- "Can you tell us what this evidence means legally?"
- "Can you determine privilege?"
- "Can we send you the whole discovery set?"
- "Can you remote in and look at the files?"
- "Can this replace our review staff or lawyers?"
- "Can it handle all file types right away?"
- "Can we include unlimited support?"
- "Can we pay after it works?"
- "Can you build the missing features first and then we decide?"
- "We need Run/Reset GUI controls, Connect, queue/ETA, model distribution, timelines, contradictions, privilege screening, email/cloud connectors, or broad OCR/media support now."

Those answers mean the next step is no-go/pause, not persuasion.

## How to describe synthetic/public demo status

Use this language:

```text
Synthetic/public demo: Go. I can show a safe demo using synthetic or public-safe material only. The demo is for proving the workflow shape, not processing real matter data or claiming production readiness.
```

`Run Synthetic Dry Run` may be shown only if it follows the synthetic demo validation package, fixed synthetic fixture values, and sanitized status-only output.

Do not use real matter data in the demo. Do not inspect private matter paths. Do not execute arbitrary bridge behavior, enable Reset, enable Real-matter GUI Run, or show private file contents.

## How to describe paid pilot status

Use this language:

```text
Paid pilot: Conditional. A paid pilot can only be planned after we agree in writing on the workflow, file types, support window, hardware, data ownership, backups, offboarding, attorney review, payment, and excluded services.
```

Paid pilot interest leads to a planning session, not implementation.

## How to describe real deployment no-go status

Use this language:

```text
Real deployment: No-Go until separately proven. Real matter operation needs written and proven support, liability, data, hardware, backup, offboarding, privacy, attorney-review, and emergency-support boundaries first.
```

Do not soften this. If the firm needs production deployment now, OpenClaw Legal is not ready for that ask.

## Next-step language after the call

If the firm is a possible fit:

```text
The next step is an internal go/no-go review and, if that stays conditional-go, a planning session to define scope, file types, support, hardware, data handling, backups, offboarding, payment, and excluded services. Nothing from this call is a final offer or contract.
```

If the firm is not a fit:

```text
This does not sound like the right first-pilot shape yet. The current system is not legal advice, not emergency support, and not a full e-discovery replacement. I would rather pause than overpromise.
```

If the firm wants a demo:

```text
The only demo I can offer at this stage is synthetic/public-safe. It will not use real matter data and will not prove production readiness.
```

## Explicit boundary

Use this boundary when needed:

```text
This conversation is exploratory. It is not legal advice, not emergency support, not a final offer, not a contract, and not approval for real deployment. Any pilot would require written scope, payment, support, data, hardware, backup, offboarding, attorney-review, and exclusion terms first.
```

## Operator rule

End the call with notes, not commitments.

After the call, use the first-pilot go/no-go review packet. If the review produces Conditional Go, schedule a planning session. If it produces No-Go, do not build features to rescue the opportunity.
