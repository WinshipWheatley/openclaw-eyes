# App Cards And UI States

Status: app-planning contract only. This file defines future read-only display concepts and does not create SwiftUI/AppKit, backend/API/schema, runtime calls, or ingestion behavior.

## Mission Control Doctrine

The app displays evidence-backed state. It must not imply hidden ingestion, hidden analysis, approval, execution, or truth.

Workspace Launch Profiles remain navigation-only. Launch Packets remain bounded action objects. Approval Receipts remain explicit operator authorization. UI State Claims require evidence/freshness proof. Product Taste / Operator Experience Evals must reject AI slop.

## Future App Cards

| Card | Purpose | Required visible proof | Must not imply |
| --- | --- | --- | --- |
| Knowledge Atlas Overview card | Shows the local knowledge substrate map by source class, sensitivity, freshness, and promotion state. | source counts by sensitivity, unknown count, blocked count, latest reviewed timestamp, stale warnings. | Hidden ingestion, completeness, or truth. |
| Discovered Source card | Shows a source exists in scope. | source id, source kind, path/ref redaction, hash if available, discovered timestamp, sensitivity. | Permission to read, summarize, export, or model-call the source. |
| Extracted Text card | Shows parsed text exists. | extraction id, extractor, extracted timestamp, quality/warnings, source basis. | Correctness, completeness, or safe prompt use. |
| Rendered Fragment card | Shows source shape preserved as HTML/rich/plaintext fragment. | fragment id, page/region, html/plaintext refs, rendering warning. | That the content is low sensitivity or truth. |
| Artifact Classification card | Shows type and sensitivity label. | classification id, artifact type, confidence, basis, review state. | That classification is correct or operator-accepted. |
| Claim card | Shows a bounded evidence-backed statement. | claim id, claim text, evidence refs, confidence, contradiction state. | Truth by default or current-state authority. |
| Compiled Note card | Shows interpretation compiled from evidence. | note id, markdown body/ref, source basis, claim refs, limitations. | Operator acceptance or factual truth. |
| Contradiction card | Shows claims or sources disagree. | contradiction id, claim refs, evidence refs, unresolved/resolved state. | Automatic adjudication. |
| Freshness/Staleness card | Shows current/stale/unknown basis for one target. | timestamp/commit, stale conditions, refresh trigger, state. | Overall system health or live runtime state. |
| Operator Promotion card | Shows explicit acceptance/rejection/historical/sensitive/excluded decision. | promotion id, target, decision, scope, operator, decided timestamp. | Scope expansion beyond the named target. |
| Conversation Packet card | Shows a safe handoff package for review. | packet id, included notes/claims, withheld surfaces, sensitivity summary, freshness snapshot. | Execution authorization or external-model safety. |
| Blocked Sensitive Source card | Shows a source is blocked due to sensitivity or unknown classification. | block reason, sensitivity level, restricted default, required future approval path. | That content was read or summarized. |

## App State Language

| State | Meaning | Required proof | Forbidden copy |
| --- | --- | --- | --- |
| `discovered` | Source reference exists in scoped substrate records. | source id, source kind, discovered timestamp. | "read", "analyzed", "safe". |
| `extracted` | Parsed text exists for a source. | extraction id, extractor, timestamp, warnings. | "understood", "complete", "true". |
| `classified` | Artifact has a type/sensitivity label. | classification id, basis, confidence, review state. | "approved", "safe". |
| `compiled` | A durable note exists from evidence/claims. | note id, source basis, evidence refs, limitations. | "accepted", "truth". |
| `promoted` | Operator explicitly accepted/rejected/marked/excluded a target. | promotion id, decision, scope, operator, timestamp. | Scope expansion or execution authorization. |
| `contradicted` | Evidence-backed claims conflict. | conflicting claim refs, evidence refs, contradiction state. | Automatic resolution. |
| `stale` | Source basis/timestamp/evidence/freshness no longer valid. | stale condition, refresh trigger, target id. | Current/fresh/healthy copy. |
| `blocked` | Sensitivity, authority, evidence, scope, or freshness prevents display/use. | block reason, required next authority path. | Hidden analysis or implied access. |
| `unknown` | App lacks evidence. | unknown reason or missing field. | Confidence, likely-safe, probably-current. |
| `excluded` | Operator or policy removed target from active use. | exclusion decision or policy, scope, timestamp. | Deletion of source evidence unless separately authorized. |

## Taste Boundary

The cards should feel calm, sparse, precise, and evidence-backed. Avoid fake intelligence language, vague chatbot panels, magic source understanding, noisy admin tables, and controls that blur navigation, approval, execution, and result.
