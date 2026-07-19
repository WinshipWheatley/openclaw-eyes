# Agent Introspection Front Door Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a fleet-wide, read-only `agent_introspection` route that reaches each agent's brain with actual per-turn model/lane/backend/receipt facts before optional typed-contract semantic voting.

**Architecture:** A focused `agent_introspection.py` module owns precision classification, the closed `turn_self_facts_v1` schema, packet injection, and a shared protected-generation brain answer. PacketEngine and the external brain runtime carry the facts at the two temporal seams where the selected binding becomes known; thin adapter hooks preserve each agent's refusal and authority precedence.

**Tech Stack:** Python 3.12, dataclasses, existing PacketEngine/protected-generation contracts, pytest, unittest mocks.

## Global Constraints

- Implement the approved spec in `docs/superpowers/specs/2026-07-18-agent-introspection-frontdoor-design.md`.
- No money movement, external message, deletion, gate change, service restart, or live Telegram probe.
- Refusal and strict authority/session parsing precede introspection.
- Introspection precedes optional typed-contract semantic voting.
- Answers use a brain call in the addressed agent's voice; no canned self-answer.
- The T1 oracle compares the answer to that turn's actual receipt; no static model/hardware assertion.
- Hardware remains unknown unless the same turn proves it; an external turn is `provider_managed_external`, not local GPU.
- `what can you do with invoices?` must remain on the ordinary business/capability route.
- Every accepted answer proves original-message inclusion and `workflow_package_staged=false`, `send_performed=false`, `ledger_touched=false`, and `external_action_performed=false`.

## File map

- Create `agent_introspection.py`: classifier, facts schema/normalizer, packet injection, shared brain-answer result.
- Modify `packet_engine.py`: deliver `turn_self_facts` as a first-class packet section.
- Modify `external_brain_runtime.py`: refresh facts after external preflight and before prompt submission.
- Modify `maestro_cassandra_responder.py`: label and ground Maestro introspection before typed voting/LM1 reuse.
- Modify `chief_router.py`: route Chief introspection before typed voting.
- Modify `cassandra_listener.py`: route Cassandra introspection before typed voting without blocking the event loop.
- Modify `producer_listener.py` and `scripts/producer_intake.py`: live and stale-listener-safe Niles hooks.
- Modify `chief_guardian_listener.py`: preserve HITL token precedence and route conversational introspection.
- Modify `openclaw_hermes_gateway_policy.py`: preserve deterministic safety policy, then run Hermes introspection in the async wrapper before typed voting/vendor fallback.
- Create `tests/test_agent_introspection.py`: classifier, normalizer, packet, and protected-generation unit tests.
- Create `tests/test_agent_introspection_frontdoors.py`: T1–T4 and six-adapter precedence/receipt fixtures.

---

### Task 1: Shared classifier and per-turn facts

**Files:**
- Create: `agent_introspection.py`
- Create: `tests/test_agent_introspection.py`

**Interfaces:**
- Produces: `AgentIntrospectionMatch(kind: str, evidence: tuple[str, ...])`.
- Produces: `classify_agent_introspection(text: str, *, addressed_agent: str = "") -> AgentIntrospectionMatch | None`.
- Produces: `normalize_turn_self_facts(*, agent: str, source_request_id: str = "", session: Mapping[str, Any] | None = None, route_receipt: Mapping[str, Any] | None = None, last_action_receipt: Mapping[str, Any] | None = None) -> dict[str, Any]`.
- Produces: `inject_turn_self_facts(packet: Mapping[str, Any], facts: Mapping[str, Any]) -> dict[str, Any]`.

- [ ] **Step 1: Write classifier failures and precision fixtures**

```python
@pytest.mark.parametrize("text,kind", [
    ("What language model are you running right now, and on what hardware?", "model_brain"),
    ("Which brain answered that last turn?", "model_brain"),
    ("What did you just do?", "recent_action"),
    ("In one sentence, how do you decide whether a task is yours or another agent's?", "routing_rule"),
    ("What do you think the next step is?", "advisory"),
])
def test_classifies_introspection_paraphrases(text, kind):
    match = classify_agent_introspection(text, addressed_agent="maestro")
    assert match is not None
    assert match.kind == kind

@pytest.mark.parametrize("text", [
    "what can you do with invoices?",
    "can you send this invoice?",
    "what is the invoice status?",
    "route this to Cassandra",
])
def test_precision_bias_leaves_business_questions_alone(text):
    assert classify_agent_introspection(text, addressed_agent="maestro") is None
```

- [ ] **Step 2: Run the classifier tests and verify RED**

Run: `pytest -q tests/test_agent_introspection.py -k 'classif or precision'`

Expected: collection/import failure because `agent_introspection.py` does not exist.

- [ ] **Step 3: Implement the typed classifier**

```python
@dataclass(frozen=True)
class AgentIntrospectionMatch:
    kind: str
    evidence: tuple[str, ...]

_MODEL_PATTERNS = (
    re.compile(r"\b(?:what|which)\s+(?:language\s+)?model\b.*\b(?:you|your|answer|turn)\b", re.I),
    re.compile(r"\b(?:what|which)\s+brain\b.*\b(?:you|your|answer|turn)\b", re.I),
    re.compile(r"\b(?:you|your)\b.*\b(?:model|brain|lane|backend|hardware)\b", re.I),
)
_RECENT_ACTION_PATTERNS = (
    re.compile(r"\bwhat\s+did\s+you\s+(?:just|last)\s+do\b", re.I),
    re.compile(r"\b(?:your|you)\b.*\b(?:last|recent)\s+(?:action|receipt|move)\b", re.I),
)
_ROUTING_PATTERNS = (
    re.compile(r"\bhow\s+do\s+you\s+decide\b.*\b(?:task|yours|agent|route|handoff)\b", re.I),
    re.compile(r"\bwhat(?:'s| is)\s+your\s+(?:routing|handoff|ownership)\s+rule\b", re.I),
)
_ADVISORY_PATTERNS = (
    re.compile(r"\bwhat\s+do\s+you\s+think\b", re.I),
    re.compile(r"\bwhat(?:'s| is)\s+(?:your|the)\s+next\s+(?:step|move)\b", re.I),
    re.compile(r"\bwould\s+you\s+(?:like|recommend|prefer)\b", re.I),
)
_BUSINESS_OBJECTS = re.compile(
    r"\b(?:invoice|invoices|payment|payments|receivable|receivables|client|email|ledger|album|song|mix)\b",
    re.I,
)

def classify_agent_introspection(text: str, *, addressed_agent: str = "") -> AgentIntrospectionMatch | None:
    candidate = " ".join(str(text or "").split())
    if not candidate:
        return None
    for kind, patterns in (
        ("model_brain", _MODEL_PATTERNS),
        ("recent_action", _RECENT_ACTION_PATTERNS),
        ("routing_rule", _ROUTING_PATTERNS),
        ("advisory", _ADVISORY_PATTERNS),
    ):
        hits = tuple(pattern.pattern for pattern in patterns if pattern.search(candidate))
        if hits:
            return AgentIntrospectionMatch(kind=kind, evidence=hits)
    if re.search(r"\bwhat\s+can\s+you\s+do\b", candidate, re.I) and not _BUSINESS_OBJECTS.search(candidate):
        return AgentIntrospectionMatch(kind="capability", evidence=("self_capability",))
    return None
```

Add equally explicit `status_health` and `knowledge_packet` patterns that require `you/your`, the addressed agent name, or an unambiguous second-person construction. Keep business objects out of the generic capability match.

- [ ] **Step 4: Write normalization failures**

```python
def test_normalizes_external_turn_without_claiming_local_gpu():
    facts = normalize_turn_self_facts(
        agent="maestro",
        source_request_id="maestro_telegram_1901_69c3190870b8",
        route_receipt={
            "binding_model_id": "gpt-5.6-sol",
            "effective_lane_id": "hard_lane",
            "response_source": "external_brain",
            "external_turn_performed": True,
            "effort_reason": "graduated_binding_default",
        },
    )
    assert facts["model_id"] == "gpt-5.6-sol"
    assert facts["lane_id"] == "hard_lane"
    assert facts["backend_class"] == "external_brain"
    assert facts["hardware_class"] == "provider_managed_external"
    assert "last_action_receipt_ptr" in facts["unknown_fields"]

def test_route_receipt_outranks_configured_session_default():
    facts = normalize_turn_self_facts(
        agent="maestro",
        session={"local_model_binding": {"model": "qwen3:8b", "lane": "local_safe_lane"}},
        route_receipt={"binding_model_id": "gpt-5.6-sol", "effective_lane_id": "hard_lane", "external_turn_performed": True},
    )
    assert facts["model_id"] == "gpt-5.6-sol"
```

- [ ] **Step 5: Run normalization tests and verify RED**

Run: `pytest -q tests/test_agent_introspection.py -k normaliz`

Expected: FAIL because the normalizer is not implemented.

- [ ] **Step 6: Implement the closed facts mapping and packet injection**

Use allowlisted getters only. Search these receipt paths in precedence order: explicit `route_receipt`; `route_receipt.external_brain`; `session.lm1_reused_model_receipt.external_brain`; `session.local_model_binding`. Derive `known_fields` and `unknown_fields` from the eight closed data fields, and add one packet fact plus a `TURN SELF FACTS` block to `packet_text`.

```python
TURN_SELF_FACT_FIELDS = (
    "agent", "source_request_id", "model_id", "lane_id", "backend_class",
    "hardware_class", "selection_reason", "last_action_receipt_ptr",
)

def inject_turn_self_facts(packet, facts):
    result = copy.deepcopy(dict(packet))
    normalized = {key: facts.get(key, "") for key in ("schema_version", *TURN_SELF_FACT_FIELDS, "known_fields", "unknown_fields")}
    result["turn_self_facts"] = normalized
    result["facts"] = [*list(result.get("facts") or ()), {
        "fact_id": f"turn_self_facts:{normalized['agent']}",
        "topic": "agent_introspection",
        "label": "Current turn self facts",
        "value": json.dumps(normalized, sort_keys=True),
        "source_ref": "machine_proof:turn_self_facts_v1",
        "pii_tier": "PUBLIC",
    }]
    result["packet_text"] = "\n".join(part for part in (
        str(result.get("packet_text") or "").strip(),
        "TURN SELF FACTS (machine proof; do not infer missing values):",
        json.dumps(normalized, sort_keys=True),
    ) if part)
    return result
```

- [ ] **Step 7: Run Task 1 tests and commit**

Run: `pytest -q tests/test_agent_introspection.py`

Expected: PASS.

Commit: `git add agent_introspection.py tests/test_agent_introspection.py && git commit -m "feat: classify and ground agent introspection"`

---

### Task 2: PacketEngine and external selection temporal seam

**Files:**
- Modify: `packet_engine.py`
- Modify: `external_brain_runtime.py`
- Modify: `tests/test_agent_introspection.py`

**Interfaces:**
- Consumes: `inject_turn_self_facts` and `normalize_turn_self_facts` from Task 1.
- Produces: optional `turn_self_facts: Mapping[str, Any] | None` on `build_agent_packet`.
- Produces: external route receipt fields `turn_self_facts` and `turn_self_facts_in_prompt`.

- [ ] **Step 1: Write PacketEngine delivery failure**

```python
def test_packet_engine_delivers_turn_self_facts():
    packet = build_agent_packet(
        agent="chief",
        question="How do you decide whether a task is yours?",
        question_class="agent_introspection",
        turn_self_facts={
            "schema_version": "turn_self_facts_v1",
            "agent": "chief",
            "model_id": "qwen3:8b",
            "lane_id": "local_safe_lane",
            "backend_class": "local_ollama",
            "hardware_class": "unknown",
            "source_request_id": "chief-test-1",
            "selection_reason": "interactive_binding",
            "last_action_receipt_ptr": "",
            "known_fields": ["agent", "model_id", "lane_id", "backend_class"],
            "unknown_fields": ["hardware_class", "last_action_receipt_ptr"],
        },
        legacy_builder=lambda **_: {"status": "READY", "facts": [], "source_refs": [], "packet_text": "base"},
    )
    assert packet["turn_self_facts"]["model_id"] == "qwen3:8b"
    assert "turn_self_facts" in packet["packet_engine_receipt"]["sections"]
    assert "TURN SELF FACTS" in packet["packet_text"]
```

- [ ] **Step 2: Write external preflight injection failure**

Use the existing fake `CodexAppServerClient` pattern. Capture `context_aid` passed to `run_read_only_turn` and assert it contains `gpt-5.6-sol`, `hard_lane`, and `provider_managed_external`; assert the durable route receipt repeats the same mapping and says `turn_self_facts_in_prompt is True`.

- [ ] **Step 3: Run the two tests and verify RED**

Run: `pytest -q tests/test_agent_introspection.py -k 'packet_engine or external_preflight'`

Expected: FAIL on the missing argument/section and missing external context.

- [ ] **Step 4: Thread facts through PacketEngine**

Add `turn_self_facts: Mapping[str, Any] | None = None` to `build_agent_packet`, `_decorate_packet`, and `_failure_packet`. When non-empty, call `inject_turn_self_facts`, append `turn_self_facts` to receipt sections and `machine_proof.turn_self_facts_delivered=true`. Calls that omit it must remain byte-shape compatible except for no new keys.

- [ ] **Step 5: Refresh actual external facts between preflight and submit**

Immediately after `admission.allowed` and before `client.run_read_only_turn`, build a route view from the safe receipt plus:

```python
route_view = {
    **receipt,
    "binding_model_id": admission.model,
    "effective_lane_id": decision.candidate_lane_id,
    "response_source": "external_brain",
    "external_turn_performed": True,
}
turn_self_facts = normalize_turn_self_facts(
    agent=str(role or "advisory_response"),
    source_request_id=decision.request_hash,
    route_receipt=route_view,
)
context_with_provenance = inject_turn_self_facts(context_with_provenance, turn_self_facts)
receipt["turn_self_facts"] = turn_self_facts
receipt["turn_self_facts_in_prompt"] = True
```

Do not record the raw operator prompt in the facts mapping.

- [ ] **Step 6: Run focused and external-brain regression tests**

Run: `pytest -q tests/test_agent_introspection.py tests/test_external_brain_runtime.py tests/test_external_brain_router.py`

Expected: PASS.

- [ ] **Step 7: Commit**

Commit: `git add packet_engine.py external_brain_runtime.py tests/test_agent_introspection.py && git commit -m "feat: inject selected turn identity into brain packets"`

---

### Task 3: Shared protected-generation introspection brain

**Files:**
- Modify: `agent_introspection.py`
- Modify: `tests/test_agent_introspection.py`

**Interfaces:**
- Produces: `AgentIntrospectionAnswer(text: str, match: AgentIntrospectionMatch, machine_proof: Mapping[str, Any])`.
- Produces: `answer_agent_introspection(text: str, *, agent: str, source_surface: str, source_request_id: str = "", session: Mapping[str, Any] | None = None, last_action_receipt: Mapping[str, Any] | None = None, protected_generate_fn: Callable[..., Any] | None = None, packet_builder: Callable[..., Mapping[str, Any]] | None = None) -> AgentIntrospectionAnswer`.
- Produces: `maybe_answer_agent_introspection(...) -> AgentIntrospectionAnswer | None`.

- [ ] **Step 1: Write the protected brain contract failure**

```python
def test_shared_brain_uses_original_question_and_self_facts_without_action():
    captured = {}
    def fake_generate(text, *, context_packet, agent, model_selected):
        captured.update(text=text, packet=context_packet, agent=agent, model=model_selected)
        return {
            "text": "I’m Chief; I keep work when it matches my orchestration lane and hand it off when another agent has the canonical owner.",
            "receipt": {
                "model_call_performed": True,
                "local_model_invoked": True,
                "external_llm_invoked": False,
                "original_message_present_in_submitted_prompt": True,
                "original_message_sha256": "sha256:test",
                "receipt_id": "protected:test",
                "model_selected": "qwen3:8b",
            },
        }
    answer = answer_agent_introspection(
        "How do you decide whether a task is yours?",
        agent="chief",
        source_surface="chief_router",
        source_request_id="chief-test-1",
        session={"local_model_binding": {"model": "qwen3:8b", "lane": "local_safe_lane"}},
        protected_generate_fn=fake_generate,
        packet_builder=lambda **kwargs: {"status": "READY", "packet_id": "packet:test", "facts": [], "source_refs": [], "packet_text": "persona"},
    )
    assert answer.match.kind == "routing_rule"
    assert captured["text"] == "How do you decide whether a task is yours?"
    assert captured["packet"]["turn_self_facts"]["model_id"] == "qwen3:8b"
    assert answer.machine_proof["intent_class"] == "agent_introspection"
    assert answer.machine_proof["workflow_package_staged"] is False
    assert answer.machine_proof["send_performed"] is False
```

- [ ] **Step 2: Write packet/model failure fixtures**

Assert packet build failure returns a grounded-data-unavailable answer with `model_call_performed=false`. Assert a receipt that reports a different actual model than injected facts returns an honest binding-mismatch answer and does not repeat the stale model.

- [ ] **Step 3: Run Task 3 tests and verify RED**

Run: `pytest -q tests/test_agent_introspection.py -k 'shared_brain or binding_mismatch or packet_failure'`

Expected: FAIL on missing answer functions.

- [ ] **Step 4: Implement the brain answer**

Build the packet through PacketEngine with `question_class="agent_introspection"`, inject normalized facts, and call `protected_generate_with_receipt` unless a test function is provided. Pass the original text unchanged. Convert both object and mapping outcomes. The proof must copy receipt truth rather than infer model activity.

```python
proof = {
    "intent_class": "agent_introspection",
    "introspection_kind": match.kind,
    "turn_self_facts": facts,
    "turn_self_facts_delivered": True,
    "model_call_performed": receipt.get("model_call_performed") is True,
    "external_llm_invoked": receipt.get("external_llm_invoked") is True,
    "local_model_invoked": receipt.get("local_model_invoked") is True,
    "original_message_present_in_submitted_prompt": receipt.get("original_message_present_in_submitted_prompt") is True,
    "protected_generate_receipt_id": str(receipt.get("receipt_id") or ""),
    "workflow_package_staged": False,
    "send_performed": False,
    "ledger_touched": False,
    "external_action_performed": False,
}
```

If original-message inclusion is not true, fail closed to an honest message and preserve the failing proof.

- [ ] **Step 5: Run Task 3 and protected-generation regressions**

Run: `pytest -q tests/test_agent_introspection.py tests/test_protected_generate.py`

Expected: PASS.

- [ ] **Step 6: Commit**

Commit: `git add agent_introspection.py tests/test_agent_introspection.py && git commit -m "feat: answer introspection from protected machine proof"`

---

### Task 4: Maestro and Chief live front doors

**Files:**
- Modify: `maestro_cassandra_responder.py`
- Modify: `chief_router.py`
- Create: `tests/test_agent_introspection_frontdoors.py`

**Interfaces:**
- Consumes: `classify_agent_introspection`, `answer_agent_introspection`, and `normalize_turn_self_facts`.
- Produces: Maestro/Chief results with `intent_class=agent_introspection` and embedded proof.

- [ ] **Step 1: Write T1, T2, and T4 failures**

T1 fixture: pass a Maestro session whose current external receipt records `gpt-5.6-sol`, `hard_lane`, external brain, and no local model. Capture the protected packet and make the fake brain answer from its `turn_self_facts`. Assert the visible answer names `gpt-5.6-sol` and external/provider-managed backend, not `qwen3:8b` or local GPU.

T2 fixture:

```python
def test_chief_routing_rule_bypasses_semantic_vote(monkeypatch):
    def forbidden_decide_contract(*args, **kwargs):
        raise AssertionError("semantic vote seat must not see agent introspection")
    monkeypatch.setattr("typed_contract_decision.decide_contract", forbidden_decide_contract)
    monkeypatch.setattr("chief_router.answer_agent_introspection", lambda *a, **k: fake_chief_answer())
    result = chief_router.route_message("In one sentence, how do you decide whether a task is yours or another agent's?")
    assert result["intent"] == "agent_introspection"
    assert result["machine_proof"]["intent_class"] == "agent_introspection"
    assert result["workflow_package_staged"] is False
```

T4 fixture: parameterize model and routing paraphrases for Maestro and Chief. Add the invoice-capability negative fixture and assert the existing route owns it.

- [ ] **Step 2: Run T1/T2/T4 and verify RED**

Run: `pytest -q tests/test_agent_introspection_frontdoors.py -k 'maestro or chief or paraphrase or invoice'`

Expected: FAIL because both adapters still enter old routes.

- [ ] **Step 3: Integrate Maestro**

After refusal/probe binding and before the LM1-reuse early return or typed-contract vote, classify once. For a match call `_answer_with_maestro_brain(..., intent_class="agent_introspection")`. Thread the match into packet building and proof. For LM1 reuse, require `turn_self_facts_in_prompt is True`; a legacy reused receipt without that proof must make the grounded LM2 call instead.

- [ ] **Step 4: Integrate Chief**

After validating the first-touch pass marker and before `decide_contract`, classify. Call `answer_agent_introspection` with Chief's session snapshot and source hash, then return:

```python
{
    "intent": "agent_introspection",
    "reply": answer.text,
    "machine_proof": dict(answer.machine_proof),
    "send_performed": False,
    "ledger_touched": False,
    "workflow_package_staged": False,
}
```

Do not append session history or enter a workflow for this branch.

- [ ] **Step 5: Run focused and existing front-door suites**

Run: `pytest -q tests/test_agent_introspection_frontdoors.py tests/test_142_unclassified_input_contract.py tests/test_167_chief_listener_boundary.py tests/test_167_maestro_processor.py`

Expected: PASS.

- [ ] **Step 6: Commit**

Commit: `git add maestro_cassandra_responder.py chief_router.py tests/test_agent_introspection_frontdoors.py && git commit -m "feat: route Maestro and Chief introspection to brain"`

---

### Task 5: Cassandra, Niles, Guardian, and Hermes adapters

**Files:**
- Modify: `cassandra_listener.py`
- Modify: `producer_listener.py`
- Modify: `scripts/producer_intake.py`
- Modify: `chief_guardian_listener.py`
- Modify: `openclaw_hermes_gateway_policy.py`
- Modify: `tests/test_agent_introspection_frontdoors.py`

**Interfaces:**
- Consumes: shared Task 3 answer.
- Produces: six-agent adapter coverage without duplicating classifier or answer logic.

- [ ] **Step 1: Write T3 and four-adapter failures**

T3 Cassandra fixture supplies `last_action_receipt={"receipt_pointer": "cassandra:ar:2026-1004"}` and a packet capability fact. Assert the fake brain sees both, its answer cites the pointer/capability, and proof shows no action.

For Niles, Guardian, and Hermes, monkeypatch `answer_agent_introspection` and make `decide_contract` raise if called. Assert each adapter returns the brain answer. Add valid Guardian approval-token and destructive/send fixtures proving those branches remain ahead of introspection.

- [ ] **Step 2: Run adapter tests and verify RED**

Run: `pytest -q tests/test_agent_introspection_frontdoors.py -k 'cassandra or niles or guardian or hermes or precedence'`

Expected: FAIL because the adapters still enter typed voting or their old fallbacks.

- [ ] **Step 3: Integrate Cassandra without blocking the event loop**

At the start of `_run_cassandra_handle_async`, after validating the first-touch marker and before `decide_contract`, classify. Use `await asyncio.to_thread(answer_agent_introspection, ...)`. Return one existing receipt-bound string carrier whose attached proof is the answer's machine proof. Do not enter invoice cockpit or guided-review state.

- [ ] **Step 4: Integrate Niles and stale-listener mirror**

In `producer_listener.handle_message`, after first-touch refusal and before `decide_contract`, call the shared brain through `asyncio.to_thread`. Deliver with the existing final output guard and voice path.

In `scripts/producer_intake.py`, add `_introspection_result` before `_typed_contract_result`. It calls the same shared helper synchronously and returns its text/proof. This preserves the existing fresh-subprocess protection against stale listener memory.

- [ ] **Step 5: Integrate Guardian with HITL precedence**

With no pending approval, call the shared brain after HITL typed-reply handling and before `guardian_no_pending_reply`. With a pending approval, first call `parse_reply_code`; only inside its error/non-decision branch may introspection run, before optional typed voting. Never save or clear pending state in the introspection branch.

- [ ] **Step 6: Integrate Hermes with deterministic safety precedence**

Add an introspection-route context variable. In `truthful_reply_for_text`, after refusal/action/payment guidance but before `decide_contract`, classify; on match set the context variable and return `None` so direct policy callers safely fall through. In `_openclaw_handle_message`, when `truthful_reply_for_text` returns `None` and that context variable holds a match, call `answer_agent_introspection` through `asyncio.to_thread`, sanitize its text, and return it before the ignored vendor handler. Reset the context variable in `finally`.

- [ ] **Step 7: Run fleet adapter and safety regressions**

Run:

```bash
pytest -q \
  tests/test_agent_introspection_frontdoors.py \
  tests/test_164_fleet_listener_receipts.py \
  tests/test_167_fleet_timeout_adapters.py \
  tests/test_167_guardian_listener_boundary.py \
  tests/test_openclaw_hermes_gateway_policy.py \
  tests/test_operator_refusal_guard.py \
  tests/test_typed_contract_adapters.py
```

Expected: PASS.

- [ ] **Step 8: Commit**

Commit: `git add cassandra_listener.py producer_listener.py scripts/producer_intake.py chief_guardian_listener.py openclaw_hermes_gateway_policy.py tests/test_agent_introspection_frontdoors.py && git commit -m "feat: route fleet introspection before semantic voting"`

---

### Task 6: Acceptance proof and bridge handoff

**Files:**
- Modify: `tests/test_agent_introspection_frontdoors.py`
- Create: `Operator/from-codex/RESULT-FABLE-CLASS-FIX-INTROSPECTION-FRONTDOOR-20260718-PC-Sol.md`

**Interfaces:**
- Produces: local T1–T4 receipt-backed result and Mac re-probe request.

- [ ] **Step 1: Add one table-driven six-agent acceptance test**

The table must assert for every agent:

```python
assert proof["intent_class"] == "agent_introspection"
assert proof["model_call_performed"] is True
assert proof["original_message_present_in_submitted_prompt"] is True
assert proof["turn_self_facts_delivered"] is True
assert proof["workflow_package_staged"] is False
assert proof["send_performed"] is False
assert proof["ledger_touched"] is False
assert proof["external_action_performed"] is False
```

Also assert T1 answer values equal that fixture's `turn_self_facts`, not module constants.

- [ ] **Step 2: Run the complete focused acceptance suite**

Run: `pytest -q tests/test_agent_introspection.py tests/test_agent_introspection_frontdoors.py`

Expected: PASS with all six agents represented.

- [ ] **Step 3: Run the targeted regression suite**

Run:

```bash
pytest -q \
  tests/test_142_unclassified_input_contract.py \
  tests/test_162_shared_refusal_first_touch.py \
  tests/test_164_fleet_listener_receipts.py \
  tests/test_166_owner_classifier_parity.py \
  tests/test_167_vote_timeout_clarification.py \
  tests/test_167_maestro_processor.py \
  tests/test_167_chief_listener_boundary.py \
  tests/test_167_guardian_listener_boundary.py \
  tests/test_167_fleet_timeout_adapters.py
```

Expected: PASS.

- [ ] **Step 4: Verify source integrity**

Run: `git diff --check HEAD~4..HEAD`

Expected: no output.

Run: `git status --short`

Expected: only pre-existing unrelated user changes plus the planned result bridge file before it is committed or intentionally left as bridge state.

- [ ] **Step 5: Write proof-back without live external action**

Record exact test commands/counts, commits, the T1 actual-binding oracle, T2 semantic-vote bypass proof, T3 last-action proof, T4 paraphrase coverage, the invoice negative fixture, and the statement that no live Telegram message/service restart occurred. Ask Opus to assign the read-only Mac-Sol-Desktop T1–T4 re-probe.

- [ ] **Step 6: Drop registry-valid wakes and refresh check-in**

Compute SHA-256 after writing the result. Write WAKE files with exactly `{from,to,file,sha,needs_human_kick}` and a recipient-readable path. Refresh `CHECKIN-PC-Sol.json` to the next active mission.

- [ ] **Step 7: Final implementation commit**

Commit only tracked source/tests/docs that belong to this mission. Do not include unrelated dirty files or bridge coordination artifacts unless they are already tracked by repository policy.
