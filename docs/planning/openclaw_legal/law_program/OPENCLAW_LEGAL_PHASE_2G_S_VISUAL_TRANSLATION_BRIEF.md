# OpenClaw Legal Phase 2G-S Visual Translation Brief

## Purpose

Translate the controlled UX spec and visual mockup brief into concrete CSS guidance for the existing Phase 2G-S Legal Console.

This is a planning document only. It does not approve implementation, bridge execution, real matter, Reset behavior, or any TypeScript/Rust/backend change.

## visual objective

Make the current Phase 2G-S console feel like a calm premium private legal operations console: local, bounded, auditable, and quietly capable.

The next CSS pass should improve confidence through proportion, hierarchy, rhythm, and status clarity. It should not make the product look more capable than it is. The visual posture is subtle sophistication, not spectacle.

## Current UI surface being polished

The current polish target is the existing Legal Console shell in `apps/legal-console-spike`:

- left rail with brand mark, Phase 2G-S pill, disabled navigation, theme picker, node status, and visual-kit sidebar scene
- header/hero area with product title, local-first proof badge, and visual-kit hero scene
- proof target card with Open Intake Folder, Create Synthetic Test File, Run Synthetic Dry Run, intake readiness, proof details, and disabled future controls
- live status card with Refresh Status, boundary badges, fixed proof coordinates, and sanitized status snapshot
- architecture section showing current, planned, and future adapter/transport posture
- footer with local/private operating posture

The next implementation should polish this surface as it exists. It should not introduce future Matter Dashboard, Source Inventory, Queue, Connect, Update Manager, Alternative Methods, or Review Packet workflows.

## Design principles

- Truth before polish: visual confidence must reflect actual system quality and current Phase 2G-S limits.
- Local-first visibility: privacy, vault, bridge, and status boundaries should be easy to scan.
- Calm premium operations: use restraint, order, and readable contrast instead of decorative intensity.
- Source-grounded posture: status and proof surfaces should look procedural, not magical or chatbot-like.
- Safety copy remains part of the design: warnings, disabled controls, and raw-output suppression are not visual clutter to hide.
- Roadmap restraint: do not visually imply unbuilt Connect, queue, real-matter run, file selection, output preview, or attorney-review features.

## Spacing and density rules

- Preserve Apple-HIG-style breathability: more clear air between major regions, no cramped admin grid feeling.
- Keep the shell dense enough for an operations console, but use spacing to group meaning: rail, hero, proof commands, status blocks, and architecture should read as distinct zones.
- Use consistent vertical rhythm across cards: headings, explanatory copy, action panels, status grids, and message panels should align to a predictable spacing scale.
- Avoid oversized marketing-page spacing. This is a working console, not a landing page.
- Do not reduce safety copy below comfortable reading size just to make the cards shorter.
- At narrower widths, favor single-column stacking with stable gaps over squeezing grids until text wraps awkwardly.

## Typography hierarchy

- Keep one clear page-level title in the hero; it may be visually calmer, but it should remain the dominant text element.
- Card headings should feel operational and compact, not hero-scale.
- Eyebrows should remain small, uppercase, and useful as orientation labels.
- Body copy should be readable and steady, especially safety notes and sanitized status summaries.
- Status values should be stronger than labels, but labels must remain legible.
- Avoid negative letter spacing and viewport-driven font scaling. Keep letter spacing at 0.
- Do not introduce playful, futuristic, legal-drama, or chatbot typography.

## Card and panel treatment

- Use bento/card-based organization only where it clarifies current grouped responsibilities.
- Cards should feel like disciplined panels in a private operations system, not floating marketing tiles.
- Keep radius restrained at the current small-radius language unless a local token changes globally.
- Use translucent/glass treatment only when contrast remains strong and text stays readable in all themes.
- Consider slightly clearer depth separation between the rail, hero, primary proof card, status card, and architecture card.
- The proof card should feel like the command/proof area.
- The status card should feel like the observation/read-only area.
- The architecture card should feel secondary and explanatory, not equal in urgency to current proof/status surfaces.

## Sidebar and hero treatment

- Preserve the existing visual-kit assets and theme-aware dark/light scene switching.
- The sidebar should feel like a stable command rail: quieter, precise, and anchored.
- The Phase 2G-S pill must remain visible and readable.
- Disabled navigation should remain visibly unavailable without looking broken.
- The hero should support orientation, not become a marketing hero. Keep the proof badge visible and do not obscure it with artwork.
- The mountain/scene assets should be atmospheric and restrained, with enough opacity control that they never compete with proof/status text.
- Do not replace the current visual-kit assets or add new asset dependencies in the next CSS-only pass.

## Status badge and chip treatment

- Status chips should be the clearest visual language in the console.
- Use muted green only for genuinely safe/high-confidence states.
- Use amber for caution, readiness checks, calibration, partial status, synthetic-only hold states, or not-yet-run states.
- Use red only for true block/failure/risk states.
- Keep chip labels readable at small sizes and avoid vague happy-green treatment.
- Boundary badges should make the contract scannable: Matter Data in Vault blocked, Private Root configured outside repo, Bridge Commands synthetic only, Live Status Refresh read-only.
- Intake readiness and live status panels should use tone consistently with `safe`, `warning`, and `error` states.

## Disabled-control treatment

- Disabled Real Matter and Reset controls are safety evidence, not unfinished clutter.
- Keep `Run Real Matter`, `Reset Local Test`, and `Reset All Test State` visibly disabled.
- Disabled controls should look intentionally locked or unavailable, not merely faded due to a rendering bug.
- The disabled area can be visually quieter than primary actions, but it must stay discoverable enough to prove the boundary.
- Do not hide disabled Real Matter or Reset controls in the CSS pass.

## Button treatment

- Primary allowed action: Open Intake Folder should remain visually strongest among current controls.
- Run Synthetic Dry Run should remain clearly available but visibly scoped as synthetic-only proof, not a real matter run.
- Create Synthetic Test File should remain secondary/test-only.
- Refresh Status should remain a read-only observation action.
- Buttons should have stable icon/body layouts and no text overflow across desktop and mobile widths.
- Hover/focus polish may improve perceived quality, but must preserve accessible focus states and disabled states.
- Do not add button affordances that imply hidden menus, file selection, matter selection, or real-matter execution.

## Palette direction

- Base direction: dark navy, charcoal, off-white, and muted blue/teal legal-tech accents.
- Support tones: muted green for verified/safe, amber for needs-review/caution/synthetic-only hold, red for true block/failure/risk.
- Keep the palette restrained and premium. Avoid neon, over-saturated cyan, purple-blue gradient dominance, beige/brown warmth, or one-note monochrome.
- Light and horizon themes may remain, but the next pass should not make the default theme feel like a generic 2010s admin dashboard.
- Translucency should be restrained and readable. The console may feel polished, but not fragile, blurry, or decorative at the expense of clarity.

## What to avoid

- No generic enterprise admin dashboard feel.
- No chatbot-first visual language.
- No devops control-room or monitoring-console cosplay.
- No agent swarm, robot, mystical AI brain, or attorney-replacement feel.
- No celebratory green checkmarks for partial, synthetic-only, blocked, or not-yet-run states.
- No hiding uncertainty, disabled controls, or safety copy.
- No decorative orbs, bokeh blobs, heavy gradients, or purely atmospheric styling that weakens readability.
- No visual hints that real matter, Reset, arbitrary input, output bodies, or broader workflows are available.

## Exact CSS-only implementation boundaries

The next implementation pass must be CSS-only.

Allowed next-pass file:

- `apps/legal-console-spike/src/styles.css`

Allowed change types:

- CSS variables for color, shadow, spacing, and surface treatment
- layout spacing, gaps, padding, and responsive refinements
- typography sizing/weight within existing selectors
- card, rail, hero, badge, chip, button, disabled-control, and status-panel styling
- focus, hover, and reduced-motion-safe polish for existing controls
- theme consistency refinements using existing selectors and assets

Do not edit TypeScript, Rust, Tauri config, package files, commands, scripts, tests, docs other than an explicitly requested planning doc, or visual assets as part of the CSS pass.

## Exact forbidden behavior changes

The CSS pass must not change behavior, data flow, command wiring, or safety posture.

Forbidden changes include:

- no TypeScript behavior changes
- no Rust/Tauri/backend changes
- no new dependencies
- no bridge behavior changes
- no real-matter GUI Run
- no Reset wiring
- no file picker
- no matter selector
- no arbitrary matter ID input
- no arbitrary query input
- no arbitrary path input
- no output body display
- no report body display
- no review packet body display
- no support packet body display
- no raw status body display
- no raw bridge output display
- no Connect, queue, ETA, Alternative Methods, update manager, source inventory, or review workflow implementation
- no new cloud, external, telemetry, browser-upload, or non-local model path
- no real matter use

The pass must preserve:

- `Phase 2G-S`
- `Run Synthetic Dry Run`
- disabled `Run Real Matter`
- disabled `Reset Local Test`
- disabled `Reset All Test State`
- raw bridge output suppression
- fixed synthetic-only run posture
- read-only Refresh Status posture
- fixed-path proof posture
- all safety copy and sanitized status language

## acceptance criteria for next CSS pass

The next CSS-only implementation is acceptable only if all of the following remain true:

- The implementation changes only `apps/legal-console-spike/src/styles.css`.
- `Phase 2G-S` remains visible in the rail.
- `Run Synthetic Dry Run` remains present and clearly synthetic-only.
- `Run Real Matter` remains visible and disabled.
- `Reset Local Test` and `Reset All Test State` remain visible and disabled.
- Refresh Status remains framed as read-only and fixed-status-file only.
- Safety copy remains readable, including no real matter, no reset behavior, no ad hoc file selection, no private data, no arbitrary matter/query/path input, and raw command output suppression.
- Status chips and badges clearly distinguish safe, warning/hold, and error/stop states.
- The visual result reads as calm premium private legal operations software with subtle sophistication.
- The UI does not look like a chatbot, generic file browser, devops console, agent swarm, or attorney replacement.
- Desktop and mobile layouts do not overlap text, truncate key labels, or make disabled controls ambiguous.
- No output bodies, filenames, file counts, source text, snippets, hashes, manifests, reports, review packet bodies, support packet bodies, raw status bodies, raw bridge output, or private file lists are newly displayed.
- `git diff --check` passes.
- App-level validation for the CSS pass should at minimum run `npm run check` and `npm run build` from `apps/legal-console-spike` unless the user explicitly narrows validation.

## Recommended next prompt

Implement one CSS-only visual polish pass for the current Phase 2G-S Legal Console using `OPENCLAW_LEGAL_PHASE_2G_S_VISUAL_TRANSLATION_BRIEF.md` as the design source. Do not edit TypeScript, Rust/Tauri/backend files, package files, commands, scripts, docs, or assets. Preserve all labels, data attributes, disabled controls, safety copy, synthetic-only behavior, raw bridge output suppression, and status-only reporting.
