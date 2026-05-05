# Import Priority and Sequence

The following sequence is recommended for the actual import phase to ensure structural integrity and security.

## Phase 1: Foundational Documentation (Highest Priority)
1. **Visual/Spatial Markdown Packets**: Import `operator_harness_north_star_v1` into `docs/planning/launch_ladder/visual/`.
2. **Doctrine Papers**: Import `DOMAIN_AGNOSTIC_OPERATOR_SYSTEMS.md` and `STUDIO_BORN_OPERATOR_INTELLIGENCE.md` into `docs/planning/launch_ladder/operator_harness_research/`.

## Phase 2: Knowledge & Handoffs
3. **Sanitized Ledger/Invoice Workflow Notes**: Import planning materials into `docs/planning/launch_ladder/ledger_invoice_steel_thread/`.
4. **Knowledge Substrate**: Import notes into `docs/planning/launch_ladder/knowledge_substrate/`.
5. **Consolidation Packets**: Review and import only durable breadcrumbs/handoffs into `docs/handoffs/`.

## Phase 3: Functional Proof-of-Concept (POC)
6. **Code Review**: Create a separate review process for `bank_csv_to_reconciliation_report.py` and its tests.
7. **Implementation**: Only after full review and alignment with PC repo test structures, consider moving logic into `src/`.

## Summary
The goal is to move from abstract doctrine and visuals to concrete planning before touching any implementation code.
