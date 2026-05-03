# Mac Desktop Sound Haptics Quiet Feedback Addendum

Status: docs/test-only quiet feedback addendum for the Mac desktop Mission Control surface. This file does not create audio assets, sound asset folders, haptic implementation, notification behavior, sound settings UI, UI implementation, SwiftUI/AppKit files, source-set folders, backend/schema files, SQLite DBs, ingestion scripts, provider/model calls, private-data inspection, runtime/service/approval mutation, or app execution.

Freshness:

- Generated/reviewed: 2026-05-02
- Active source-set baseline: `02_MAC_IOS_APP_BUILD`
- Source commit from active `MANIFEST.md`: `df52ff4687d7dd8a32990658d557cb2b4d1371d9`
- Source basis: `14_MAC_DESKTOP_TASTE_AND_ATMOSPHERE_SPEC.md`, first-screen composition spec, Mission Control fixture contract, and Product Taste / Operator Experience Eval Spine.
- Stale when: taste spec, sound policy, accessibility posture, implementation boundary, app-planning posture, or naming boundary changes.
- Refresh trigger: update before any sound, haptics, notifications, settings UI, or Mac desktop app implementation prompt.

## 1. Sound Thesis

Sound should play a minor, disciplined role. Sound should behave like tactile confirmation from a well-built studio surface: soft relay, settled switch, quiet indication that a visible state transition completed.

Emotional target: settled confidence, not excitement.

Sound should not create anticipation, urgency, mystery, or the sense that hidden agents are working somewhere offscreen. The best sound design is almost forgettable.

Brand/audio identity is deferred.

## 2. Default Policy

Sound should be off by default for v1.

Quiet feedback mode should be opt-in.

Critical information must never be sound-only. Every sound, if later implemented, must correspond to visible state copy, evidence, and an accessible non-audio indication.

Sound, if enabled in a future implementation, must be:

- short;
- low-volume;
- low-frequency;
- non-melodic;
- tied only to visible state transitions.

This addendum does not authorize audio assets, sound settings UI, notification systems, haptic implementation, or app code.

## 3. Allowed Sound Moments

Allowed sound moments for future evaluation only:

- app opened;
- source-set changed;
- evidence/proof completed;
- blocked boundary;
- unknown/evidence missing;
- approval needed;
- local checkpoint committed;
- push/sync failed;
- lane selected;
- drawer opened.

Each moment must be tied to visible state transition evidence. If there is no visible state transition, there is no sound.

## 4. Forbidden Sound Patterns

Forbidden sound patterns:

- AI thinking sounds;
- sci-fi sweeps;
- startup chimes;
- notification spam;
- casino/game pings;
- dramatic warning alarms;
- hidden-worker sounds;
- chatbot message sounds;
- ambient "system is alive" hum;
- anything implying background action without visible evidence.

Forbidden patterns should fail static review before implementation.

## 5. Sonic Reference Vocabulary

Reference vocabulary for future design discussion:

- soft relay;
- muted tape transport;
- console click;
- felt switch;
- low meter tick;
- subdued room tone as dangerous if continuous;
- quiet confirmation;
- boundary thud.

These are references for restraint, not asset names, product identity, or implementation instructions.

## 6. Haptics / Tactile Feedback Posture

Haptics are a future posture, not an implementation task in this slice.

If a future Mac desktop or companion client supports tactile feedback, it should behave like quiet physical confirmation:

- lane selected;
- drawer opened;
- blocked boundary encountered;
- approval needed;
- evidence/proof completed.

No haptic feedback may imply hidden work, background execution, model thinking, or approval. Haptics must be optional and subordinate to visible state.

## 7. Accessibility And Operator Control

- Sound off by default.
- Quiet feedback mode opt-in.
- Per-event control is a future design question, not this slice.
- Critical information must never be sound-only.
- Visual state, text, and evidence must remain complete without sound.
- Sound/haptics must not punish repeated daily use.
- Operator control matters more than atmosphere.

## 8. Vibe Tests

Required sound/haptics vibe tests:

- `sound_confirms_visible_state`
- `studio_console_not_notification_pack`
- `blocked_without_alarm`
- `no_hidden_worker_audio`
- `quiet_by_default`
- `daily_use_no_fatigue`
- `sound_optional_not_identity`

## 9. Anti-Vibe Tests

Required sound/haptics anti-vibe tests:

- `ai_thinking_blips`
- `sci_fi_sweep`
- `jira_notification_ping`
- `casino_success_chime`
- `dramatic_error_alarm`
- `ambient_agent_hum`
- `startup_brand_sting`

Any future audio/haptics artifact that passes one of these anti-vibe tests should stop before build work continues.

## 10. Recommendation For Codex Artifact

Treat this file as a separate addendum to `14_MAC_DESKTOP_TASTE_AND_ATMOSPHERE_SPEC.md` and include it in the next combined source-set generation package.

Do not generate audio assets, sound asset folders, haptic code, notification behavior, sound settings UI, source-set folders, backend/schema files, SQLite DBs, ingestion scripts, runtime hooks, provider/model calls, approval behavior, private-data access, or app names from this addendum.
