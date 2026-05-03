# Mac Desktop Taste And Atmosphere Spec

Status: docs/test-only taste and atmosphere contract for the Mac desktop Mission Control surface. This file does not create UI, SwiftUI/AppKit files, source-set folders, backend/schema files, SQLite DBs, ingestion scripts, audio assets, haptics, notification behavior, provider/model calls, private-data inspection, runtime/service/approval mutation, or app execution.

Freshness:

- Generated/reviewed: 2026-05-02
- Active source-set baseline: `02_MAC_IOS_APP_BUILD`
- Source commit from active `MANIFEST.md`: `df52ff4687d7dd8a32990658d557cb2b4d1371d9`
- Source basis: Mission Control fixture contract, first-screen composition spec, Compiled Knowledge Substrate planning package, and Product Taste / Operator Experience Eval Spine.
- Stale when: taste vocabulary, first-screen composition, quiet feedback posture, evidence/freshness copy, knowledge-substrate posture, app-planning boundaries, or naming boundary changes.
- Refresh trigger: update before combined source-set generation or any Mac desktop app implementation prompt.

## 1. Taste Thesis

Opening the Mac desktop app should feel like sitting down at a trusted personal command surface. It should feel closer to powering on a well-built studio console before a session than launching a productivity app.

Target emotional state: centered operational clarity.

The operator should feel: "I know where things stand. I know what is safe. I know what is blocked. I know what deserves my attention."

Dominant blend: quiet instrument panel + studio console + evidence drawer + chart table.

Taste comes from structure, not branding. The app should feel personal and daily-use-worthy, not merely correct.

Neutral phrases only: Mac desktop app, Operator Harness app, personal operator console, Mission Control surface.

No app naming. No implementation authorization.

## 2. Visual Reference Vocabulary

- Cockpit guides discipline, not decoration.
- Studio console is the strongest personal metaphor, but do not literalize knobs/faders everywhere.
- The chart table suggests evidence, orientation, and route comparison.
- The evidence drawer suggests proof close at hand without paperwork sprawl.
- The personal command surface suggests operator-specific daily use without introducing a name, codename, mascot, slogan, logo, or brand identity.

This vocabulary is not a mandate to copy physical objects. It is a constraint on clarity, posture, hierarchy, and restraint.

## 3. Material And Surface Language

- Tactile but not skeuomorphic.
- Dimensional but not flashy.
- Evidence-backed but not bureaucratic.
- Personal but not cute.
- Creative but not whimsical slop.
- Calm enough for daily use.
- Precise enough for authority and evidence.

Surfaces should make zones feel intentionally placed: operating context, active lanes, current focus, next safe move, evidence drawer, recent changes, and future knowledge context. Surface treatment should separate navigation, evidence, approval, and blocked states without creating decorative noise.

## 4. Typography And Density

- Text should feel like instrument labeling, not marketing copy.
- Use short exact state phrases: `planning`, `local ahead`, `blocked`, `unknown`, `available`, `not approved`, `not implemented`.
- Avoid generic dashboard labels such as "overview", "activity", or "insights" when a more exact operator state exists.
- Density should support fast orientation, not task-manager sprawl.
- Evidence should be visible, but long proof should live in drawers.
- Typography should support repeated daily use: legible, quiet, and exact.

## 5. Motion And Interaction Feel

Motion should be minimal purposeful motion only. Minimal purposeful motion only.

Allowed future motion posture:

- subtle zone focus;
- drawer open/close;
- lane selection;
- evidence card expansion;
- blocked or unknown state settling into view.

Forbidden posture:

- fake AI thinking animation;
- hidden-worker theatre;
- bouncing status pills;
- progress animations without evidence;
- dramatic launch sequences;
- motion that implies background execution.

Nothing moves just because it is visible.

## 6. Personal-To-Winship Signals

The surface should feel built for the operator's actual working style without becoming cute or branded.

Personal signals should come from:

- exact source-set and repo context;
- active Launch Ladder lane;
- next safe move;
- evidence/freshness visibility;
- calm handling of blocked and unknown states;
- respect for local-first private boundaries;
- knowledge context that supports historical business understanding without overclaiming.

Do not use personal slogans, mascots, logo concepts, codename energy, or fake familiarity. The personal feeling should come from fit, memory, and proof.

## 7. Empty States And Quiet States

Empty states should preserve operational calm:

- "No Launch Packet selected" means no packet is selected; it does not mean nothing is happening.
- "Unknown" means the app lacks evidence; do not soften it into confidence.
- "Blocked" means a protected boundary is working; do not make it feel like panic or failure.
- "No knowledge context promoted" means no operator promotion exists; do not create a RAG search/chat-with-files default.
- "Remote sync not verified" means no push evidence exists; do not show current/synced.

Quiet states should avoid fake urgency and notification-wall energy.

## 8. Vibe Tests

Required taste vibe tests:

- `would_open_this_every_morning`: the operator would open it daily because it gives calm useful orientation.
- `cockpit_not_chatbot`: the surface feels like instruments and authority, not a vague assistant panel.
- `studio_console_not_saas`: the strongest personal metaphor is a well-built studio console, not generic SaaS.
- `evidence_without_paperwork`: proof is visible and accessible without bureaucratic sprawl.
- `blocked_without_panic`: blocked states feel like protected boundaries, not emergencies.
- `personal_without_branding`: the surface feels fitted to the operator without names, slogans, mascots, or logo work.
- `creative_without_whimsy`: the surface supports creative operations without whimsical slop.
- `knowledge_without_rag_search_box`: knowledge context does not default to RAG search/chat-with-files UX.
- `approval_visible_not_dominant`: approval state is visible when relevant, but not the whole product.
- `daily_control_not_project_management`: the surface feels like daily operational control, not project-management software.

## 9. Anti-Vibe Tests

Required taste anti-vibe tests:

- `jira_cosplay`
- `ai_orb_centerpiece`
- `startup_dashboard`
- `compliance_portal_mood`
- `neon_command_center`
- `wall_of_status_chips`
- `fake_product_name_energy`
- `overexplained_receipt_drawer`
- `agent_theatre`
- `rag_search_default`

Any future design or implementation artifact that passes one of these anti-vibe tests should stop before build work continues.

## 10. Implementation Risk Warnings For Future Codex/Mac Work

Future Codex/Mac work must not turn this taste spec into implementation authorization.

Do not:

- implement UI;
- create SwiftUI/AppKit files;
- create source-set folders in this slice;
- create backend/schema files;
- create SQLite DBs;
- create ingestion scripts;
- scan old business files;
- inspect private data;
- call providers/models;
- mutate runtime/services/approvals;
- create audio assets, haptic implementation, notification behavior, or sound settings UI;
- introduce app/product/brand/codename/mascot/logo/slogan.

Knowledge substrate must not default to RAG search/chat-with-files UX. It remains future context/navigation posture until a separate backend/data-model contract exists.

## 11. Next Artifact Recommendation

Recommended next artifact: combined source-set generation for the app-planning package.

Do not do another broad design pass before generating the combined source set unless static validation fails or the operator explicitly asks for more taste exploration. The combined source set should carry:

- Mission Control fixture contract;
- first-screen composition spec and fixtures;
- Compiled Knowledge Substrate planning package;
- this taste and atmosphere spec;
- `15_MAC_DESKTOP_SOUND_HAPTICS_QUIET_FEEDBACK_ADDENDUM.md` as a separate addendum;
- validation map and static checker expectations.

This recommendation does not create source-set folders. It identifies the next planning artifact after this docs/test slice is committed.
