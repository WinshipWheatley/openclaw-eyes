# Class-fix known baseline — 2026-07-18

Command pinned for the class-fix acceptance check:

```text
pytest -q -s tests/test_142_unclassified_input_contract.py
```

Expected result after updating the intentional generic self-capability route:
`68 passed, 7 failed`.

The seven accepted pre-existing persona/copy drift failures and signatures are:

1. `test_identity_routes_to_persona_core[maestro]` — `IndexError: list index out of range` at `core_identity.split(" is ", 1)[1].split()[1]`.
2. `test_identity_routes_to_persona_core[chief]` — same `IndexError` and assertion expression.
3. `test_identity_routes_to_persona_core[cassandra]` — same `IndexError` and assertion expression.
4. `test_identity_routes_to_persona_core[niles]` — same `IndexError` and assertion expression.
5. `test_identity_routes_to_persona_core[hermes]` — same `IndexError` and assertion expression.
6. `test_e2e_gibberish_never_gets_digest_through_frontdoor` — expected `Not sure I follow — what do you need?`; observed `I didn't catch what you need — say it any way you like.`
7. `test_e2e_identity_compound_ask_gets_persona_core_through_frontdoor` — expected `"router"` in the lowercase summary; observed the Maestro response-card orchestration identity copy without that word.

Acceptance rule: these exact seven may remain only with the same signatures. A changed signature or any additional failure blocks class-fix acceptance. These are recorded truth, not approval to edit the concurrent persona/copy changes.

Separate observation, outside this pinned Task 142 baseline: `tests/test_167_maestro_processor.py::test_addressed_non_maestro_cannot_borrow_maestro_digest_authority` currently reaches the already-dirty packet-engine brain path and fails its downstream sentinel. It is not approved baseline drift and must not be counted among the seven above.

Separate time-sensitive fixture observation: `tests/test_typed_contract_adapters.py::test_hermes_status_uses_fresh_presence_only` labels a fixed `2026-07-09T22:00:00Z` presence snapshot as fresh. On 2026-07-18 the production three-day freshness guard correctly excludes it, so the assertion `"Hermes runtime: online" in fresh` fails. This is not class-fix regression or authority to weaken freshness truth.
