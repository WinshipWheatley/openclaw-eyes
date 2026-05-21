# Memory Candidate Receipt Contract v0

## Operator Summary
OpenClaw now has a deterministic receipt grammar for proposed memory candidates. A candidate can be captured, classified, reviewed, rejected, stale, revoked, or quarantined, but it is not canonical memory until a separate future promotion lane approves it into an allowed surface with proof and receipts.

## Candidate Types
- `OPERATOR_CONTEXT_CANDIDATE`: Operator-provided context that may guide later work but is not proof.
- `OPERATOR_CORRECTION_CANDIDATE`: Operator correction to a label, framing, status, or doctrine.
- `OPERATOR_PREFERENCE_CANDIDATE`: Operator taste or workflow preference eligible for review.
- `PROJECT_FACT_CANDIDATE`: Project fact candidate requiring source/proof before canonical use.
- `LANE_STATUS_CANDIDATE`: Lane state or readiness candidate.
- `PROOF_GAP_CANDIDATE`: Known missing proof or source gap.
- `ARCHITECTURE_DOCTRINE_CANDIDATE`: Architecture or doctrine rule candidate.
- `ACTOR_ROUTING_CANDIDATE`: Actor/routing rule candidate.
- `MODEL_POLICY_CANDIDATE`: Model-selection policy candidate.
- `TOOL_ADAPTER_CANDIDATE`: Tool adapter state or capability candidate.
- `PACKAGE_TEMPLATE_CANDIDATE`: Package template or field candidate.
- `SAFETY_BOUNDARY_CANDIDATE`: Safety, authority, redaction, or protected-access boundary candidate.
- `WORKER_RESULT_CANDIDATE`: Worker result candidate requiring source/receipt review.
- `BUILD_VERIFICATION_CANDIDATE`: Build/test verification candidate requiring command/output receipt.
- `HOLDING_CELL_CANDIDATE`: Premature but valid idea or lane parked for later review.
- `WORLD_WORKFLOW_CANDIDATE`: Domain/world workflow memory candidate.
- `CREATIVE_CONTEXT_CANDIDATE`: Music/art/creative context candidate.
- `FINANCE_PROTECTED_CONTEXT_CANDIDATE`: Finance/AP/protected context candidate requiring Guardian review.
- `BLOCKED_MEMORY_CANDIDATE`: Blocked or unsafe memory candidate that must not drive packages.

## Candidate States
- `OBSERVED_CONTEXT`: Context was observed but is not yet a candidate receipt.
- `CANDIDATE_CAPTURED`: A bounded candidate has been captured with required receipt fields started.
- `CANDIDATE_CLASSIFIED`: Candidate type, source class, sensitivity, and destination have been classified.
- `NEEDS_SOURCE_REFERENCE`: Candidate lacks a valid source reference.
- `NEEDS_REDACTION`: Candidate needs redaction or reference-only handling before review.
- `NEEDS_OPERATOR_REVIEW`: Candidate needs operator review before promotion can be considered.
- `NEEDS_GUARDIAN_REVIEW`: Candidate needs Guardian review before promotion can be considered.
- `NEEDS_PROOF`: Candidate needs machine proof or approved metadata before promotion.
- `RECEIPT_READY`: Receipt has the required fields and can enter review.
- `APPROVED_FOR_PROMOTION`: Review has approved future promotion; promotion execution is still outside this contract.
- `PROMOTED_CANONICAL`: Possible future state after a separate promotion lane writes canonical memory.
- `REJECTED`: Candidate has been rejected and must not drive packages as memory.
- `STALE`: Candidate must be re-reviewed before use.
- `REVOKED`: Candidate or promoted memory has been revoked and blocked downstream.
- `QUARANTINED`: Candidate is isolated due to risk, contradiction, leakage, or malformed proof.
- `UNKNOWN_FAIL_CLOSED`: Candidate cannot be trusted and fails closed.

## Receipt Fields
- `candidate_id`
- `receipt_id`
- `candidate_type`
- `candidate_state`
- `source_actor`
- `source_surface`
- `source_reference`
- `source_class`
- `captured_at`
- `captured_by`
- `package_id`
- `actor_id`
- `model_class`
- `tool_adapter_id`
- `source_excerpt_policy`
- `raw_body_included`
- `redaction_status`
- `sensitivity`
- `proof_status`
- `operator_gate_status`
- `guardian_gate_status`
- `destination_canonical_surface`
- `promotion_allowed`
- `promotion_blockers`
- `review_required_by`
- `expires_or_review_after`
- `staleness_rule`
- `revocation_status`
- `quarantine_status`
- `receipt_hash`
- `what_this_would_change`
- `why_it_matters`
- `what_would_make_it_canonical`

## Proof / Redaction
- Operator statements are context, not machine proof.
- Worker output requires command/output/file-change evidence before it can serve as proof.
- Raw private bodies and credentials/secrets are blocked by default.

## Promotion / Review
- Requires: valid source reference
- Requires: candidate classification
- Requires: sensitivity classification
- Requires: redaction status
- Requires: proof status
- Requires: destination canonical surface
- Requires: Operator approval where required
- Requires: Guardian approval where required
- Requires: receipt hash
- Requires: staleness/review policy
- Requires: no blocked source material
- Requires: no unresolved proof conflict
- This contract does not promote memory.

## Actor Candidate Rules
- `operator_winship`: may propose 8 candidate types; cannot make a fact machine-proof by statement alone, authorize execution by memory statement, bypass security audit.
- `chief`: may propose 4 candidate types; cannot self-promote, self-authorize repairs, treat missing proof as proof.
- `guardian`: may propose 3 candidate types; cannot self-authorize execution, bypass operator, store raw secrets.
- `cassandra`: may propose 4 candidate types; cannot send, submit, approve, access accounts, self-promote finance facts.
- `hermes`: may propose 3 candidate types; cannot promote doctrine unilaterally, ingest broad history, claim authority from prose.
- `niles`: may propose 3 candidate types; cannot treat creative preference as machine proof, publish/release/account action, self-promote.
- `codex`: may propose 4 candidate types; cannot use hidden IDE memory as proof, self-promote, expand scope, write canonical memory.
- `gemini_antigravity`: may propose 3 candidate types; cannot retain memory, write canonical surfaces, treat output as truth without receipt.

## Mission Control Guidance
- Show candidate inbox, proof/context distinction, gates, blockers, staleness, revocation, and quarantine.
- Hide raw private bodies, credentials, raw chat archives, hidden memory dumps, broad indexes, and direct ungated promotion controls.

## Stable Map Integration
- Summary included in stable map now: `false`
- Next requirement: Include this summary in the next stable map bundle refresh after this contract lands.

## Authority Boundary
- `runtime_authority`: `false`
- `model_memory_authority`: `false`
- `hidden_memory_authority`: `false`
- `autonomous_memory_capture`: `false`
- `raw_chat_ingestion_authority`: `false`
- `vector_memory_authority`: `false`
- `external_retained_memory_authority`: `false`
- `canonical_memory_promotion_authority`: `false`
- `tool_execution_authority`: `false`
- `model_call_authority`: `false`
- `agent_call_authority`: `false`
- `browser_oauth_account_access_enabled`: `false`
- `gmail_calendar_coupa_telegram_enabled`: `false`
- `credential_authority`: `false`
- `send_submit_approval_enabled`: `false`
- `network_execution_enabled`: `false`
- `runtime_daemon_enabled`: `false`
- `planner_builder_execution_enabled`: `false`
- `queue_autonomy_execution_enabled`: `false`
- `raw_private_body_ingestion_enabled`: `false`
- `broad_filesystem_indexing_enabled`: `false`
- `repo_b_mutation_enabled`: `false`
- `mission_control_app_authority_added`: `false`
- `mac_sync_or_import_triggered`: `false`
- `pc_c_drive_artifact_write_allowed`: `false`
- `operator_final_authority`: `true`

## Next Lanes
- `model_selection_receipt_v0` (P1): Model Selection Receipt v0
- `package_preview_receipt_v0` (P1): Package Preview Receipt v0
- `mission_control_package_preview_actor_routing_surface_v0` (P2): Mission Control Package Preview / Actor Routing Surface v0
- `tool_adapter_receipt_v0` (P2): Tool Adapter Receipt v0
- `memory_review_promotion_surface_v0` (P3): Memory Review / Promotion Surface v0
