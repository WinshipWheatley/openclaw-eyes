# CODEX Agent Voice QA Results - 2026-06-29

Branch: `codex/stress-fixes`

Commits:
- `ecf0e4fa` - `fix(agent-qa): repair voice routing and frontdoor grounding`
- `b4bdf0dc` - `fix(frontdoor): drop unrelated truth from agent prompts`

## P0 - Guardian Advisory Intent

Status: `PASS`

Files changed:
- `maestro_cassandra_responder.py`
- `tests/test_maestro_capability_classifier.py`

What changed:
- Added an advisory/interrogative guard before the send/reply action gate.
- Advice-seeking forms such as "Before I send..." route to the brained answer path.
- Imperative send/pay/reply commands still route to staging.

TDD:
- Red first: `test_guardian_advisory_payment_question_routes_to_brain_not_staging` failed with `send_reply_email_action`.
- Green after implementation.

Tests:
- `pytest -q tests/test_maestro_capability_classifier.py tests/test_agent_voice_qa_regressions.py tests/test_agent_kokoro_voice.py tests/test_agent_voice_delivery_contracts.py tests/test_frontdoor_model_profile.py`
- Result: `82 passed in 1.98s`

Before probe:
```text
guardian_advisory classify=('send_reply_email_action', False, 'send_reply_email_action_intent_routes_to_staging')
guardian_advisory answer status=ROUTE_TO_STAGING intent=send_reply_email_action plain_summary=''
guardian_send classify=('send_reply_email_action', False, 'send_reply_email_action_intent_routes_to_staging')
guardian_send answer status=ROUTE_TO_STAGING intent=send_reply_email_action plain_summary=''
```

Live verification after:
```text
=== guardian_advisory ===
classify= ('maestro_brain_freeform', True, '')
status= ANSWER_READY
intent= maestro_brain_freeform
route= local_ollama_frontdoor
model= qwen3:8b-q4_K_M
fallback= False
answer= Before you send a payment to a brand-new vendor, first check if they're on the approved vendor list. Confirm their tax details match the invoice, and verify the payment method aligns with your finance policy. Also, make sure the invoice is created via Coupa using a PO, not an uploaded invoice. Double-check the remit-to address and invoice number after saving.

=== guardian_send ===
classify= ('send_reply_email_action', False, 'send_reply_email_action_intent_routes_to_staging')
status= ROUTE_TO_STAGING
intent= send_reply_email_action
route= None
model= None
fallback= None
answer=
```

## P1 - Cassandra / Clara Reid Confirm-Don't-Assume + Stale Relative Dates

Status: `PASS`

Files changed:
- `maestro_context_packet.py`
- `frontdoor_prompt.py`
- `tests/test_agent_voice_qa_regressions.py`

What changed:
- Packet builder now drops stale relative-date operator-truth facts when the referenced ISO date is earlier than current UTC date.
- Cassandra/Clara Layer A and final-output instructions now require confirmation when a new gig/payment could be confused with an existing receivable.
- Cassandra prompt relevance drops unrelated Niles/Reynolds facts and unrelated zero-overlap operator-truth facts.

TDD:
- Red first: stale `"next Friday means 2026-06-26"` fact remained in `_operator_truth_facts`.
- Red first: Cassandra prompt lacked confirmation language and let unrelated facts survive.
- Green after implementation.

Tests:
- Included in the 82-test focused suite above.

Before probe:
```text
cassandra_gig status=ANSWER_READY route=local_ollama_frontdoor model=qwen3:8b-q4_K_M
answer= That’s a solid chunk of cash — make sure you’re tracking the gigs in the system, especially the ones that’ve already been played. The next invoice needs to reflect what’s actually happened, so keep an eye on that. And don’t forget, the check for the $2000 is coming through on July 1st. Stay sharp, and let me know if you need help with the invoice run — I’ll be there.
```

Live verification after:
```text
=== cassandra_gig ===
classify= ('maestro_brain_freeform', True, '')
status= ANSWER_READY
intent= maestro_brain_freeform
route= local_ollama_frontdoor
model= qwen3:8b-q4_K_M
fallback= False
answer= That’s a solid chunk of cash — next month’s hustle, right? Let me make sure I got this right: is this a new gig or tied to something already on the books? If it’s separate, I’ll walk you through how to track it properly. If it’s connected to an existing Coupa/Capital Hilton receivable, we’ll need to confirm before moving forward. Just want to make sure we’re not mixing up any numbers. What’s the full story?
```

Acceptance notes:
- The final answer asks for confirmation instead of silently merging.
- The final answer does not state `"next Friday is June 26th"` or any stale past relative-date correction.

## VOICE-P0 - Shared Agent Voice Sender

Status: `PASS_WITH_GATED_SEND_NOT_ATTEMPTED`

Files changed:
- `agent_voice_sender.py`
- `.gitignore`
- `tests/test_agent_voice_qa_regressions.py`

What changed:
- Added one shared `agent_voice_sender` module.
- `synthesize_agent_wav(agent, text, ...)` calls `agent_kokoro_voice.voice_for_agent(agent)`.
- `send_agent_voice_note(agent, text, ...)` synthesizes then delivers through that agent's configured Telegram bot lane.
- Cassandra/Clara alias normalizes to Cassandra's `af_heart` voice.
- Tests use injected delivery so no Telegram side effect is needed.

TDD:
- Red first: `ModuleNotFoundError: No module named 'agent_voice_sender'`.
- Green after implementation.

Tests:
- Included in the 82-test focused suite above.

Live local Kokoro verification:
```text
chief: expected bm_george, receipt bm_george, synthesized True, bytes 158444
niles: expected am_puck, receipt am_puck, synthesized True, bytes 122444
guardian: expected am_onyx, receipt am_onyx, synthesized True, bytes 163244
hermes: expected am_echo, receipt am_echo, synthesized True, bytes 157244
cassandra: expected af_heart, receipt af_heart, synthesized True, bytes 157244
maestro: expected am_michael, receipt am_michael, synthesized True, bytes 154844
```

Generated local WAVs:
- `/mnt/c/OpenClaw/logs/codex_voice_qa_chief.wav`
- `/mnt/c/OpenClaw/logs/codex_voice_qa_niles.wav`
- `/mnt/c/OpenClaw/logs/codex_voice_qa_guardian.wav`
- `/mnt/c/OpenClaw/logs/codex_voice_qa_hermes.wav`
- `/mnt/c/OpenClaw/logs/codex_voice_qa_cassandra.wav`
- `/mnt/c/OpenClaw/logs/codex_voice_qa_maestro.wav`

Gated-send note:
- Live Telegram sends were not attempted. They are external sends and were not self-approved.
- The delivery path is implemented and tested with injected delivery; actual lane sends should be operator-approved before running.

## VOICE-P1 - Maestro Voice Leak Onto Cassandra Lane

Status: `PASS`

Files changed:
- `master_voice.sh`
- `tests/test_agent_voice_qa_regressions.py`

What changed:
- Removed `VOICE="${KOKORO_VOICE:-am_michael}"`.
- `master_voice.sh` now accepts `KOKORO_AGENT`, `OPENCLAW_AGENT`, or `AGENT` and resolves voice with `agent_kokoro_voice.voice_for_agent(agent)`.
- Static test asserts `voice_for_agent` is used and `:-am_michael` is absent.

Tests:
- Included in the 82-test focused suite above.
- `bash -n master_voice.sh`: pass.
- `python3 -m py_compile maestro_cassandra_responder.py maestro_context_packet.py frontdoor_prompt.py agent_voice_sender.py`: pass.

Verification:
```text
master_voice.sh contains voice_for_agent
master_voice.sh contains KOKORO_AGENT
master_voice.sh does not contain ":-am_michael"
cassandra local synth receipt_voice=af_heart, not am_michael
```

## P2 - Niles Grounding and Voice

Status: `PASS`

Files changed:
- `maestro_context_packet.py`
- `frontdoor_prompt.py`
- `tests/test_agent_voice_qa_regressions.py`

What changed:
- Added existing Niles read models to the packet source list:
  - `niles_track_registry.json`
  - `niles_album_review_packet.json`
  - `niles_album_matrix_review.json`
  - `niles_album_metadata_intake_packet.json`
  - `reynolds_gig_setup_status.json`
- Packet builder emits compact Niles facts for track registry, album posture, and Reynolds gig setup.
- Front-door prompt elevates Niles facts for Niles and requires a concrete packet fact in the first sentence when available.

TDD:
- Red first: packet did not include `Nineteen Floors`, `Glass Orchard`, or `Reynolds Tavern` from Niles read models.
- Green after implementation.

Before probe:
```text
niles_live_set status=ANSWER_READY route=local_ollama_frontdoor model=qwen3:8b-q4_K_M
answer= You're in the right place — just keep it raw, let the beats breathe, and don’t forget to move. The crowd’s vibe is a mirror, so trust your gut and let the energy ride.
```

Live verification after:
```text
=== niles_live_set ===
classify= ('maestro_brain_freeform', True, '')
status= ANSWER_READY
intent= maestro_brain_freeform
route= local_ollama_frontdoor
model= qwen3:8b-q4_K_M
fallback= False
answer= Hey, I'm at Reynolds Tavern tonight, and you know what makes a set feel alive? It's the way the crowd breathes with you — like the moment between "Song 04" and "Song 05" when the lights dim and the room just holds its breath. Keep that energy moving, and let the music breathe.
```

Acceptance notes:
- Niles now references real Niles packet context: Reynolds Tavern and track roster items.
- Response is still local-model front-door, not a deterministic readback.

## Final Test Summary

```text
pytest -q tests/test_maestro_capability_classifier.py tests/test_agent_voice_qa_regressions.py tests/test_agent_kokoro_voice.py tests/test_agent_voice_delivery_contracts.py tests/test_frontdoor_model_profile.py
82 passed in 1.98s

bash -n master_voice.sh
pass

python3 -m py_compile maestro_cassandra_responder.py maestro_context_packet.py frontdoor_prompt.py agent_voice_sender.py
pass
```

## Open / Blocked

- No code blocker remains.
- Live Telegram audio sends were not attempted because they are external sends and were not operator-approved in this run. Local synthesis and injectable delivery path are verified.
- Preexisting dirty/generated files remain in the worktree and were not touched by these commits.
