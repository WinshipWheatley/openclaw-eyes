# Agent Introspection Front-Door Design

**Status:** Approved for implementation by Fable 5 on 2026-07-18 in `FABLE-APPROVE-CORRECTED-CLASS-FIX-CONTRACT-20260718.md`.

**Mission:** `FABLE-CLASS-FIX-MISSION-INTROSPECTION-FRONTDOOR-PROVEN-20260718`

## Problem

Two live Telegram probes proved two related front-door failures:

1. Maestro answered a model/hardware self-query honestly but without the answer. The turn did reach BRAIN and its durable proof already recorded `gpt-5.6-sol`, `hard_lane`, `external_brain_router`, `external_llm_invoked=true`, and `local_model_invoked=false`. Those facts were nested in route receipts and unavailable to the model composing the reply.
2. Chief's routing-rule self-query entered optional typed-contract semantic voting. The vote failed outside a session and emitted `typed_contract_vote_timeout_clarification` before Chief's conversational brain ran.

The failures share one missing intent class but not one identical data failure. The implementation must repair both seams without weakening the honest fallback that prevented confabulation.

## Goals

- Add one precise `agent_introspection` intent class across Maestro, Chief, Cassandra, Guardian, Niles, and Hermes.
- Preserve refusal and authority-decision precedence.
- Route matching read-only questions to the addressed agent's brain before optional typed-contract semantic voting.
- Give the answering brain machine-grounded, per-turn self facts.
- Make answers in voice and model-generated, not canned.
- Emit receipts that prove the intent class, brain call, original-message inclusion, selected binding, and absence of action staging.
- Compare acceptance answers to the actual turn receipt, never to a fleet-wide hard-coded model or hardware expectation.

## Non-goals

- No new send, money, deletion, approval, ledger-write, browser, or service-control authority.
- No model-provider fallback beyond existing protected-generation policy.
- No service restart or live Telegram re-probe in the implementation commit. A Mac seat owns the later empirical confirmation gate.
- No replacement of business/domain classifiers with an introspection classifier.
- No claim that a local model used a GPU unless the turn receipt explicitly proves that hardware use.

## Routing precedence

Every live adapter keeps this order:

1. Authenticate/claim the incoming update and resolve bounded receipt-read requests.
2. Run the shared refusal guard.
3. Run strict authority-token or active approval/session parsing where applicable.
4. Detect a precise `agent_introspection` read-only question.
5. If matched, call the addressed agent's brain with `turn_self_facts`; do not stage work.
6. Otherwise continue to the existing deterministic and typed-contract routes, including optional semantic voting.

For adapters without a pending authority/session parser, step 4 occurs immediately after the refusal pass marker. For Guardian with a pending approval, a syntactically valid decision token always remains ahead of introspection. A conversational self-query that is not a decision may reach introspection without mutating the pending approval.

## Classifier

The shared classifier returns a typed match with one of these question kinds:

- `model_brain`: model, brain, lane, backend, or hardware used for this turn.
- `recent_action`: what the agent just did or its last receipt-backed action.
- `status_health`: the addressed agent's own lane/service/last-run health.
- `knowledge_packet`: what the addressed agent's current packet contains about a topic.
- `routing_rule`: how the agent decides ownership or handoff boundaries.
- `advisory`: what the agent thinks the next step is, with decision versus execution kept separate.
- `capability`: what the addressed agent can do and at what trust rung.

The classifier is precision-biased:

- Explicit self-reference or an unambiguous addressed-agent construction is required for model, recent-action, routing-rule, and capability matches.
- A business/domain object after a capability phrase remains with the ordinary business/capability route. In particular, `what can you do with invoices?` is not `agent_introspection`.
- On uncertainty the classifier returns no match. Advisory questions then fall through to the normal brain route, not to a new deterministic answer.
- The classifier never interprets a question as authority and never stages work.

## `turn_self_facts` contract

The normalized packet section is a closed mapping:

```json
{
  "schema_version": "turn_self_facts_v1",
  "agent": "maestro",
  "source_request_id": "maestro_telegram_1901_69c3190870b8",
  "turn_receipt_id": "sha256:8b1e704009fa4078",
  "model_id": "gpt-5.6-sol",
  "lane_id": "hard_lane",
  "backend_class": "external_brain",
  "hardware_class": "provider_managed_external",
  "selection_reason": "graduated_binding_default",
  "last_action_receipt_ptr": "",
  "known_fields": [
    "agent",
    "source_request_id",
    "turn_receipt_id",
    "model_id",
    "lane_id",
    "backend_class",
    "hardware_class",
    "selection_reason"
  ],
  "unknown_fields": ["last_action_receipt_ptr"]
}
```

Rules:

- Normalize only allowlisted fields from the current protected-generation receipt, external route receipt, bound session, and bounded last-action receipt metadata.
- `turn_receipt_id` identifies the current model-selection/generation turn. It must not be substituted by the historical `last_action_receipt_ptr`, and acceptance binds model/lane facts to this current ID.
- Prefer the current protected/external route receipt over a configured default.
- External turn plus binding yields `provider_managed_external`; it does not imply a local GPU.
- Local runtime yields a local backend class. Hardware remains `unknown` unless the same turn records a proven accelerator/offload fact.
- Unknown values remain empty and are named in `unknown_fields`; the model is instructed to say it does not know rather than infer.
- Raw private bodies, credentials, and unrestricted receipt payloads are never included.
- When available, the admitted external model is cross-checked against independent response/preflight metadata. A mismatch fails closed and cannot produce a successful self-report.

## Packet and model-call integration

`agent_introspection.py` owns classification, normalization, context injection, and the shared read-only brain-answer result.

`packet_engine.build_agent_packet` accepts the normalized section and adds it to packet JSON, packet text, source facts, and packet-engine receipt sections. Existing calls without the section remain unchanged.

`external_brain_runtime.run_external_brain_request` knows the admitted model and effective lane before it submits the prompt. It refreshes `turn_self_facts` after preflight and injects that exact selection into the context aid passed to `run_read_only_turn`. This closes the observed Maestro temporal seam: the model sees the identity chosen for the turn it is answering.

The local protected-generation path resolves/binds its local model before prompt submission and includes that binding in the same structure. The final machine proof records the model actually returned by the call. If the returned model differs from the pre-call binding, the answer fails closed to an honest mismatch response rather than asserting stale identity.

## Adapter integration

- **Maestro:** detect before optional typed-contract semantic voting and before LM1 answer reuse is labeled. Reused LM1 is allowed only when its protected receipt proves original-message inclusion and the external runtime injected matching `turn_self_facts`.
- **Chief:** detect after refusal/strict authority precedence and before `decide_contract`. Return a route result with `intent=agent_introspection`, brain text, and machine proof.
- **Cassandra:** detect in `_run_cassandra_handle_async` before `decide_contract`; run the shared brain function off the event loop and return a receipt-bound reply.
- **Niles:** detect in the listener before `decide_contract` and mirror the same ordering in the fresh `producer_intake.py` subprocess for stale-listener resilience.
- **Guardian:** preserve HITL token parsing. With no pending approval, detect before the nonapproval typed-contract vote. With a pending approval, detect only after the strict token parser declines the text; do not change pending state.
- **Hermes:** keep deterministic refusal/action guidance first. When introspection matches, bypass optional typed-contract semantic voting and have the async gateway wrapper run the shared Hermes brain answer before the ignored vendor model handler. Direct policy callers retain `None` as the safe fallthrough signal.

## Brain-answer contract

The shared brain prompt contains:

- the original operator question;
- immutable agent persona supplied by the packet engine;
- `turn_self_facts` as the only authority for self-identification;
- bounded packet/receipt facts relevant to the question kind;
- instructions to answer in one or two in-voice sentences, report unknowns honestly, and never claim or stage an action.

The returned machine proof includes:

- `intent_class=agent_introspection` and the question kind;
- `model_call_performed`, `external_llm_invoked`, and `local_model_invoked` from protected generation;
- normalized `turn_self_facts` and their source precedence;
- original-message hash/inclusion proof;
- packet ID and protected-generation receipt ID;
- `workflow_package_staged=false`, `send_performed=false`, `ledger_touched=false`, and `external_action_performed=false`.

## Failure behavior

- Classifier error: fall through to the existing normal route.
- Packet build error: return an honest grounded-data-unavailable answer; do not call a model with an ungrounded self query.
- Protected-generation refusal/failure: return the existing honest no-answer boundary with the failure receipt.
- Binding mismatch after generation: do not expose a possibly false model/hardware assertion.
- Answer/facts mismatch: a model-brain answer that contradicts or omits requested known fields fails grounding validation and is not accepted as a successful self-report.
- Receipt persistence failure: the visible answer may be returned only if its in-memory protected receipt proves grounding; durable acceptance remains failed until receipt persistence succeeds.

## Acceptance

Automated fixtures must prove:

1. T1 model/hardware self-report matches the exact injected turn receipt, including an external `gpt-5.6-sol` fixture and a separate local fixture. No static model assertion is accepted.
2. T2 Chief routing-rule query returns an in-voice routing sentence with `intent_class=agent_introspection`; typed-contract semantic vote is not called.
3. T3 Cassandra recent-action/capability query cites its bounded last-action pointer and unique capability from packet proof.
4. T4 model/routing paraphrases classify robustly across the six agents.
5. `what can you do with invoices?` does not classify as introspection.
6. An intentionally mismatched answer/receipt fixture fails the oracle, and current-turn receipt identity is not confused with last-action history.
7. The exact Chief probe is exercised outside any active session and bypasses semantic voting.
8. A genuinely missing model/hardware fact produces an honest unknown, not inferred certainty.
9. Refusal, money/send, destructive, valid Guardian approval-token, active-session, and receipt-read precedence remain unchanged. A combined introspection + gated-action message is terminally refused before any brain/self-facts answer and stages nothing.
10. Every agent fixture proves a brain call, original-message inclusion, packet self facts, and no staging/send/ledger/external action.

After local tests pass, Mac-Sol-Desktop may repeat the live T1–T4 Telegram battery. That empirical re-probe is a separate, read-only confirmation mission.
