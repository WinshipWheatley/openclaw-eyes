# Domain Module Onboarding Contract

Domain modules let OpenClaw add new territory, such as `record_label` or `legal`, by registration instead of rewriting existing invoice, St Anne's, or agent code. This contract is read-only until Fable promotes a specific domain implementation.

Required snap-in points:

1. FACTS -> the one knowledge ledger
   New domain facts go through `canonical_fact_ingest.py` into `canonical_facts`. Grounded packets read those facts through the existing domain-agnostic packet path.

2. ENTITIES -> registries
   New domain entities follow the registry pattern used by contacts and clients. Entity data does not get hardcoded into workflows.

3. WORKFLOWS -> declarative workflow engine
   New domain step chains are declared as workflow definitions. A declaration does not activate a runner or grant approval.

4. RECURRENCE/TEMPORAL -> client-recurrence registry
   New domain deadlines, recurrence, and paid-through style state register in the recurrence/temporal layer.

5. INTENTS -> shared interpreter
   Fuzzy user intents register at the shared LM1 interpreter seam so domains do not add parallel intent routers.

6. AGENTS/PERSONAS -> agent roster
   A domain may extend an agent or declare a light agent definition, but the definition is not runtime authority.

7. SELF-KNOWLEDGE -> crawler roots
   New domain roots must be visible to the self-knowledge crawl/orient surface, so operators can see what exists and what remains inactive.

Worked example: `record_label`

`domain_module_registry.py` registers a `record_label` stub with all seven points declared:

- facts: `record_label_canonical_fact`
- entities: artist, release, label contact
- workflow: release packet review
- recurrence: release deadline tracking
- intents: release status check and label contract packet status
- persona: advisory-only Niles extension
- self-knowledge: `record_label.self_knowledge_root`

Authority boundary:

- no sends
- no payment or money movement
- no ledger mutation by registry inspection
- no workflow activation
- no external calls
- no approval grant

Acceptance proof for task 83:

- the stub appears in the domain registry
- the stub appears in `self_knowledge_orient` under `map.domain_modules`
- a `record_label` canonical fact grounds through the existing Maestro packet SQLite path
- the implementation requires zero edits to invoicing or St Anne's code
