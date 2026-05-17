# OpenClaw Sync Health

Trust status: `stale_needs_mac_sync`
Mirror status: `needs_mac_sync`
Display status: `needs_mac_sync`
Next expected actor: `mac_sync_agent`

Mirror counts:
- canonical_expected=126
- observed=92
- missing_expected=34
- extra=0
- hash_mismatch=4
- matched_hash=88

Recommended fix:
- kind: `request_mac_sync`
- display status: `needs_mac_sync`
- next expected actor: `mac_sync_agent`
- next: Request Mac sync through the shared marker and let the Mac LaunchAgent refresh the mirror.
- app can request bounded Mac sync marker: `true`

Proof:
- Mac heartbeat: `idle` at `2026-05-17T14:01:44+00:00`
- Mac completion: `synced` at `2026-05-17T01:20:33+00:00`
- PC import: `skipped_unchanged` at `2026-05-17T01:34:51+00:00`
- Windows task log present: `true`

Stale files:
- `active_machinery_block_later_guardrail.json`
- `active_machinery_block_later_guardrail_OPERATOR.md`
- `active_machinery_classification_orchestrator.json`
- `active_machinery_classification_orchestrator_OPERATOR.md`
- `active_machinery_gemini_verification.json`
- `active_machinery_gemini_verification_OPERATOR.md`
- `active_machinery_high_risk_quarantine.json`
- `active_machinery_high_risk_quarantine_OPERATOR.md`
- `active_machinery_operator_disposition.json`
- `active_machinery_operator_disposition_OPERATOR.md`
- `active_machinery_quarantine_decision_packet.json`
- `active_machinery_quarantine_decision_packet_OPERATOR.md`
- `active_machinery_quarantine_operator_review.json`
- `active_machinery_quarantine_operator_review_OPERATOR.md`
- `capital_hilton_actionable_review_packet.json`
- `capital_hilton_actionable_review_packet_OPERATOR.md`
- `capital_hilton_review_packet_approval.json`
- `capital_hilton_review_packet_approval_OPERATOR.md`
- `cassandra_chief_memory_import_approval.json`
- `cassandra_chief_memory_import_approval_OPERATOR.md`
- `cassandra_chief_structured_fact_import.json`
- `cassandra_chief_structured_fact_import_OPERATOR.md`
- `cassandra_clara_fact_packet.json`
- `cassandra_clara_fact_packet_OPERATOR.md`
- `cassandra_date_awareness.json`
- `cassandra_date_awareness_OPERATOR.md`
- `cassandra_governed_review_packet_request_proof.json`
- `cassandra_governed_review_packet_request_proof_OPERATOR.md`
- `cassandra_listener_governed_intake_synthetic_proof.json`
- `cassandra_listener_governed_intake_synthetic_proof_OPERATOR.md`
- `cassandra_listener_governed_shadow.json`
- `cassandra_listener_governed_shadow_OPERATOR.md`
- `cassandra_send_status_dry_run.json`
- `cassandra_send_status_dry_run_OPERATOR.md`
- `guardian_hitl_cassandra_proposal_shadow.json`
- `guardian_hitl_cassandra_proposal_shadow_OPERATOR.md`
- `telegram_agent_runtime_readiness_rollup.json`
- `telegram_agent_runtime_readiness_rollup_OPERATOR.md`

No-authority posture:
- `app_direct_execution_allowed`: `false`
- `arbitrary_command_allowed`: `false`
- `remote_control_allowed`: `false`
- `ssh_scp_rsync_allowed`: `false`
- `docker_ollama_allowed`: `false`
- `runtime_activation_allowed`: `false`
- `agent_activation_allowed`: `false`
- `file_delete_allowed`: `false`
- `file_move_allowed`: `false`

Boundary:
- Sync Health is a read-model and ledger snapshot only.
- It does not remote-control Mac or Windows, run arbitrary commands, modify Mission Control, or broaden sync authority.
