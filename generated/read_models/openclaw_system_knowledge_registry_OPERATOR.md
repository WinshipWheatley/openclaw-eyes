# OpenClaw Eyes System Knowledge Registry

## Summary
- Registry ID: `openclaw_system_knowledge_registry`
- Schema version: `openclaw_system_knowledge_registry_v0`
- Component count: 14
- Known unknown count: 7
- Boundary: documentation/read-model/SQLite only.
- READY means local registry artifacts validated, not merged to main.

## Authority Boundary
- `documentation_read_model_sqlite_only`: True
- `live_automation_allowed`: False
- `service_start_allowed`: False
- `email_or_gmail_access_allowed`: False
- `browser_or_coupa_access_allowed`: False
- `workbook_cell_read_allowed`: False
- `pdf_export_allowed`: False
- `ledger_mutation_allowed`: False
- `production_mutation_allowed`: False
- `live_model_or_tool_action_allowed`: False
- `merge_to_main_allowed`: False

## Required SQLite Tables
- `system_component`
- `capability`
- `workflow_rail`
- `knowledge_claim`
- `known_unknown`
- `build_task`
- `agent_role`
- `artifact_policy`
- `registry_sqlite_display_surface`
- `repo_relationship_analysis`

## Coverage Assessment
Eight components would be too shallow for this checkout. Local evidence covers repo identity, read-models, context/evidence substrate, terrain/operator maps, workflow rails, bridge/shuttle, agent-role references, mac_eyes, polish_loop, legal, artifact policy, and external unknowns.

## Components
- `openclaw_eyes_repo_identity`: CONFIRMED_LOCAL - Local checkout for WinshipWheatley/openclaw-eyes with an allowlist tracked-file model.
- `generated_read_model_system`: CONFIRMED_LOCAL - Repo contains deterministic JSON, markdown, and text read-model outputs.
- `evidence_grounded_context_registry_concept`: PARTIAL_LOCAL - Local files support evidence-grounded context, freshness, and compiled substrate ideas.
- `work_terrain_operator_map_surfaces`: CONFIRMED_LOCAL - Repo has work-terrain query, relationship, classification, and operator map records.
- `operator_action_workflow_surfaces`: CONFIRMED_LOCAL - Repo records operator action requests, inboxes, workflow rails, and approval-bus contracts.
- `bridge_shuttle_sync_surfaces`: CONFIRMED_LOCAL - Repo contains Mac/PC read-model shuttle, bridge truth, and manual recovery packet surfaces.
- `cassandra_chief_guardian_references`: CONFIRMED_LOCAL - Agent-role code and packet templates exist for Cassandra, Chief, and Guardian rails.
- `mac_eyes_surfaces`: CONFIRMED_LOCAL - Mac reflection and launcher surfaces are present as local files.
- `polish_loop_runtime_task_area`: CONFIRMED_LOCAL - Repo contains a builder/review loop area and status files.
- `legal_module_surfaces`: CONFIRMED_LOCAL - Legal support, path guard, local policy, and console spike surfaces are present.
- `context_evidence_read_model_substrate`: CONFIRMED_LOCAL - Repo contains context packet, evidence freshness, and read-model selection machinery.
- `business_ops_artifact_policy_surfaces`: CONFIRMED_LOCAL - Repo has finance/artifact policy surfaces and protected evidence references.
- `external_repo_a_b_runtime_relationship`: UNKNOWN_EXTERNAL - Local repo mentions Repo A, Repo B, and runtime intake, but external repos are not present.
- `prior_codex_web_registry_commit`: UNKNOWN_UNREACHABLE - Reported Codex Web commit could not be fetched or pushed; this branch recreates locally.

## Known Unknowns
- `unknown_external_repo_a`: External Repo A - UNKNOWN_EXTERNAL. Next: Inspect the intended external repository in its own checkout when provided.
- `unknown_external_repo_b`: External Repo B - UNKNOWN_EXTERNAL. Next: Reconcile the cross-repo estate map with explicit repo paths or remotes.
- `unknown_runtime_state`: Runtime state - UNKNOWN_BY_BOUNDARY. Next: Use a separate runtime validation prompt if service inspection is authorized.
- `unknown_prior_codex_web_commit`: Prior Codex Web registry commit - UNKNOWN_UNREACHABLE. Next: Stop chasing the SHA; validate this local branch and pushed branch instead.
- `unknown_clara_runtime`: Clara runtime identity - REFERENCE_ONLY_UNKNOWN. Next: Treat Clara as reference-only until a source component is visible.
- `unknown_live_arts_pdf_helper`: Live Arts PDF export/helper implementation - UNKNOWN_OR_OUT_OF_SCOPE. Next: Design helper architecture separately without generating PDFs in this validation.
- `unknown_registry_pr_source`: Codex Web PR source - UNKNOWN_UNPUBLISHED. Next: Use this local branch as the review source after successful SSH push.

## Top 10 Build Tasks
1. Reconcile repo topology / cross-repo estate map (high-context reasoning model) - NEXT_BOUNDED_TASK
2. Adopt registry into Hermes/Chief later (systems architecture model) - FUTURE_INTEGRATION
3. Preserve Evidence-Grounded Context Registry as source of truth (deterministic code model) - ARCHITECTURE_GUARD
4. Avoid duplicating deterministic registry with generic vector RAG (retrieval-design model) - DESIGN_GUARD
5. Mac/PC artifact transport policy (cross-platform systems model) - POLICY_NEXT
6. Live Arts PDF export/helper architecture (macOS/Python helper architecture model) - ARCHITECTURE_ONLY
7. Access Broker permissions (security/policy model) - POLICY_NEXT
8. Request/response stability (test/stability model) - TEST_NEXT
9. Payment watch / ledger readiness (finance-control/guardrail model) - GUARDED_FUTURE_WORK
10. Stale UI/chat-card drift checks (UI regression/review model) - REVIEW_NEXT

## Generated Outputs
- `json`: `generated/read_models/openclaw_system_knowledge_registry.json`
- `operator_markdown`: `generated/read_models/openclaw_system_knowledge_registry_OPERATOR.md`
- `sqlite`: `generated/system_knowledge/openclaw_system_knowledge_registry.sqlite`
- `schema_sql`: `generated/system_knowledge/openclaw_system_knowledge_registry_SCHEMA.sql`
- `seed_sql`: `generated/system_knowledge/openclaw_system_knowledge_registry_SEED.sql`
