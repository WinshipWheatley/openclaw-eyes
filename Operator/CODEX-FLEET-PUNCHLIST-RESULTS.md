# CODEX-FLEET-PUNCHLIST-RESULTS

result_schema: openclaw_fleet_punchlist_results_v2
repo_root: /home/openclaw
branch: codex/stress-fixes
overall_status: partial
do_not_push_observed: true
operator_pending_commands:
  - python3 scripts/ingest_canonical_docs.py --db /home/openclaw/.openclaw/business_ops/ledger.sqlite --source docs/operations/CASSANDRA_MACHINE_CONTRACT.md --confirm

## P1 - Doctrine Ledger Rebuild + Phantom Actor Guard

status: done
operator_followup_status: operator_reported_confirm_rebuild_ran
files_changed:
  - canonical_doctrine_facts.py
  - canonical_fact_ingest.py
  - model_selection_doctrine_facts.py
  - niles_lane_doctrine_facts.py
  - scripts/populate_real_ledger.py
  - tests/test_canonical_doctrine_facts.py
  - tests/test_canonical_fact_ingest.py
  - tests/test_populate_real_ledger.py
commits:
  - sha: 430dc6fd
    subject: "fix: validate doctrine actors before ledger seed"
tests:
  - command: python3 -m pytest tests/test_canonical_doctrine_facts.py tests/test_populate_real_ledger.py tests/test_canonical_fact_ingest.py::TestDeduplication::test_same_fact_id_changed_text_replaces_old_indexed_row
    result: pass
    counts: 14 passed
live_verification:
  result: operator_reported_clean
  note: Updated punch-list states the operator ran P1 --confirm; fin and SD-4 are clean.

## P1b - Cassandra Machine Contract Doc-Ingest Replacement

status: operator_pending
build_result: implemented
files_changed:
  - scripts/ingest_canonical_docs.py
  - tests/test_canonical_fact_ingest.py
commits:
  - sha: a5f9e433
    subject: "fix: replace stale doc-ingested facts"
tests:
  - command: python3 -m pytest tests/test_canonical_fact_ingest.py::TestWidenedMarkdownSources::test_doc_ingest_replaces_stale_source_section_fact_without_orphan tests/test_ingestion_guard.py
    result: pass
    counts: 7 passed
red_tests:
  - missing replace_stale_doc_section_facts import failed before implementation.
  - direct CLI failed before implementation with ModuleNotFoundError for scripts package.
implementation_notes:
  - Added replace_stale_doc_section_facts for doc-ingested facts keyed by source_file + section_heading.
  - Old canonical_facts rows and all FTS/embedding shadows for stale content hashes are removed before re-ingest.
  - scripts/ingest_canonical_docs.py now self-locates the repo root when run as a script.
  - Production DB writes require --confirm; without it, the script exits with an operator-pending command.
live_verification:
  current_live_ledger_read_only:
    canonical_facts:
      clara_reed_hits: 1
      fin_paren_hits: 0
      stale_rows:
        - [fact_4735dc85, docs/operations/CASSANDRA_MACHINE_CONTRACT.md, Role]
    fts_canonical_facts:
      clara_reed_hits: 1
      fin_paren_hits: 0
      stale_rows:
        - [fact_4735dc85, docs/operations/CASSANDRA_MACHINE_CONTRACT.md, Role]
  safety_probe:
    command: python3 scripts/ingest_canonical_docs.py --db /home/openclaw/.openclaw/business_ops/ledger.sqlite --source docs/operations/CASSANDRA_MACHINE_CONTRACT.md
    result: exited_2_no_write
    output: "SAFETY: production ledger write requires --confirm. Operator-pending command: python3 scripts/ingest_canonical_docs.py --db /home/openclaw/.openclaw/business_ops/ledger.sqlite --source docs/operations/CASSANDRA_MACHINE_CONTRACT.md --confirm"
  operator_pending_command: python3 scripts/ingest_canonical_docs.py --db /home/openclaw/.openclaw/business_ops/ledger.sqlite --source docs/operations/CASSANDRA_MACHINE_CONTRACT.md --confirm
  expected_after_operator_command: grep/count Clara Reed over canonical_facts + fts_canonical_facts should be 0.

## P2 - Non-Maestro No-Response Profiles

status: done
files_changed:
  - self_improvement_request.py
  - tests/test_no_response_watchdog.py
commits:
  - sha: eb245b97
    subject: "fix: file no-response packages for all agents"
tests:
  - command: python3 -m pytest tests/test_no_response_watchdog.py tests/test_hermes_observer.py
    result: pass
    counts: 18 passed
red_tests:
  - no_response_hermes profile compile failed before implementation with SelfImprovementPackageError.
implementation_notes:
  - Added bounded profiles for no_response_hermes, no_response_cassandra, no_response_niles, no_response_chief, and no_response_guardian.
  - Each profile keeps production restarts/systemd/crontab edits forbidden and routes through Chief/Guardian proposal flow.
live_verification:
  probe: temp aged Hermes request envelope with no response.
  result:
    suggestion_ids: [no_response_hermes]
    routed_to_chief: [no_response_hermes]
    temp_task_status: PROPOSED
    temp_task_source: agent
    approval_sender_called:
      - {task_id: probe_no_response_hermes, requester: hermes}
    auto_approved: false
    production_restart_performed: false

## P3 - Deferred Image Reprocess Queue

status: done
files_changed:
  - maestro_listener.py
  - tests/test_maestro_image_input.py
commits:
  - sha: 901b16f5
    subject: "feat: defer unreadable image OCR intake"
tests:
  - command: python3 -m pytest tests/test_maestro_image_input.py tests/test_workflow_package_request_consumer.py
    result: pass
    counts: 27 passed
red_tests:
  - missing _which, deferred_marker_dir, drain_deferred_image_markers, and build_operator_image_request failed before implementation.
implementation_notes:
  - Added agent-scoped build_operator_image_request plus Maestro wrapper.
  - OCR failure or empty OCR writes pending_vision marker with sha256/local ref and returns the honest deferred reply.
  - drain_deferred_image_markers retries local OCR and writes a normal bridge request only when OCR text is available.
  - handle_photo now uses the real _telegram_typing_loop helper and returns deferred reply without writing a bridge request on OCR failure.
  - Raw image bytes are not sent to the model; live_attachment_allowed remains false.
live_verification:
  probe: fake Telegram photo through handle_photo using OCR disabled, then drain with real tesseract/text2image fixture.
  result:
    deferred_reply: "noted — I can't read it yet, I'll reprocess when vision's back."
    marker_count: 1
    drain_resolved: 1
    drain_failed: 0
    written_request_count: 1
    ocr_text_reached_request: true
    raw_image_body_shared_with_model: false
    live_attachment_allowed: false

## P4 - A/B Latent Fixes

status: done
files_changed:
  - maestro_cassandra_responder.py
  - tests/test_maestro_brain_receipt_telemetry.py
  - tests/test_maestro_cassandra_responder.py
commits:
  - sha: 84a8d268
    subject: "fix: preserve agent identity in capability receipts"
tests:
  - command: python3 -m pytest tests/test_maestro_brain_receipt_telemetry.py tests/test_maestro_capability_classifier.py tests/test_interpreter_lm_integration.py tests/test_maestro_cassandra_responder.py
    result: pass
    counts: 71 passed
red_tests:
  - missing model_call_performed in protected-generate receipt defaulted true before implementation.
  - status/capability default protected-generate call passed agent=maestro before implementation.
  - non-Maestro deterministic fallback said "current Maestro packet" before implementation.
implementation_notes:
  - _protected_generate_receipt_machine_proof now defaults missing model_call_performed to false.
  - _answer_status_capability_with_brain receives and forwards the real agent.
  - Non-Maestro status/capability fallback now uses agent-scoped truthful readback instead of the generic Maestro-packet fallback.
  - Controller LM2 reused-proof telemetry remains labeled LOCAL_OLLAMA_REUSED_PROOF_RESPONSE with model_call_performed=false.
live_verification:
  capability_probe:
    agent: cassandra
    intent_class: status_capability_readback
    mentions_cassandra: true
    mentions_maestro_packet: false
    protected_generate_called: true
    protected_generate_route: deterministic_fallback
    model_call_performed: false
  deterministic_probe:
    prompt: "what is today's date?"
    intent_class: date_awareness
    reply: "Today is 2026-06-29 (Monday)."
    protected_generate_called: false
    model_call_performed: false

## Final Tree State

main_repo:
  branch_status: codex/stress-fixes ahead of origin/codex/stress-fixes by 12 commits
  latest_punchlist_commits:
    - 84a8d268 fix: preserve agent identity in capability receipts
    - 901b16f5 feat: defer unreadable image OCR intake
    - eb245b97 fix: file no-response packages for all agents
    - a5f9e433 fix: replace stale doc-ingested facts
    - 430dc6fd fix: validate doctrine actors before ledger seed
  pushed: false
  unrelated_dirty_state: generated/runtime files and pre-existing Operator packets remain dirty/untracked and were not reverted.
