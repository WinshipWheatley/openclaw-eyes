# CODEX Agent Freshness-Awareness Result

Date: 2026-07-01
Branch/worktree: `codex/fail-closed-sweep-20260701` in `/tmp/openclaw-failclosed-20260701`

## Status

PARTIAL PASS / safe hardening landed.

What is fixed:

- Front-door prompts now include per-fact freshness tags when packet facts carry `freshness.as_of`.
- Stale facts (>=14 days old) are marked `stale-needs-refresh`.
- The fixed prompt instruction says: `Do not present stale facts as current`.
- Protected-generate receipts now include `stale_fact_ids` so stale packet use is auditable after live answers.
- A read-only packet read-model freshness audit utility now inventories packet source read-models and classifies freshness rot.

What is not auto-mutated:

- I did not hand-edit or regenerate `generated/read_models/*`.
- I did not add/modify production cron/systemd refresh jobs in this branch.
- The real audit found many stale packet sources; those should be routed into a dedicated refresh-cadence repair rather than blindly regenerating generated state from this code branch.

## Files Changed

- `frontdoor_prompt.py`
- `protected_generate.py`
- `read_model_freshness_audit.py`
- `tests/test_frontdoor_model_profile.py`
- `tests/test_read_model_freshness_audit.py`
- `Operator/CODEX-FRESHNESS-AWARENESS-RESULT.md`

## Real Packet Source Freshness Audit

Command:

```text
python3 - <<'PY'
from pathlib import Path
from read_model_freshness_audit import audit_read_models, discover_packet_read_models
r = audit_read_models(discover_packet_read_models(), read_model_root=Path('generated/read_models'), repo_root=Path('.'))
print(r['summary'])
for item in r['items']:
    if item['freshness_status'] != 'fresh':
        print(item['freshness_status'], item['name'], item['timestamp'], item['age_days'], item['producer_hints'][:2])
PY
```

Summary:

```text
{'read_model_count': 25, 'problem_count': 19, 'stale_count': 18, 'missing_file_count': 1, 'missing_timestamp_count': 0, 'bad_json_count': 0, 'stale_after_days': 14, 'today': '2026-07-01'}
```

Non-fresh packet sources:

```text
stale capital_hilton_invoice_operator_readback.json 2026-05-25T22:42:54+00:00 37
stale capital_hilton_invoice_operator_run_status.json 2026-06-14T17:33:31+00:00 17
stale cassandra_draft_review_packet.json 2026-05-18T22:21:07+00:00 44
stale cassandra_email_calendar_delta_detangle.json 2026-05-19T01:10:51+00:00 43
stale cassandra_governed_review_packet_request_proof.json 2026-05-17T14:42:34+00:00 45
stale cassandra_listener_governed_intake_synthetic_proof.json 2026-05-17T03:45:17+00:00 45
stale cassandra_runtime_wiring_audit.json 2026-05-16T05:11:26+00:00 46
stale cassandra_send_status_dry_run.json 2026-05-17T13:34:00+00:00 45
stale chief_status_rail.json 2026-05-19T00:30:34+00:00 43
stale finance_invoice_reconciliation.json 2026-05-15T19:27:11+00:00 47
stale hermes_chief_build_handoff.json 2026-05-28T15:01:54-04:00 34
stale hermes_gravity_controller.json 2026-05-28T12:00:00+00:00 34
stale hermes_mission_sentinel.json 2026-05-28T15:01:54-04:00 34
stale niles_album_matrix_review.json 2026-05-18T01:41:16+00:00 44
stale niles_album_metadata_intake_packet.json 2026-05-18T01:44:40+00:00 44
stale niles_album_review_packet.json 2026-05-17T12:00:00+00:00 45
stale openclaw_hermes_sidecar.json 2026-05-31T23:00:00+00:00 31
missing_file reynolds_gig_setup_status.json
stale work_board.json 2026-05-15T15:07:35+00:00 47
```

## Tests

Red-first proof:

- `test_build_frontdoor_prompt_marks_stale_fact_freshness` failed before `frontdoor_prompt.py` appended freshness tags.
- `test_build_frontdoor_prompt_recent_fact_is_not_stale` failed before freshness tags existed.
- `test_pgwr_frontdoor_receipt_records_stale_fact_ids` failed before receipts copied stale ids.
- `tests/test_read_model_freshness_audit.py` failed before `read_model_freshness_audit.py` existed.

Passing verification:

```text
python3 -m pytest tests/test_frontdoor_model_profile.py tests/test_protected_generate.py tests/test_read_model_freshness_audit.py -q
55 passed in 1.09s
```

## Recommendation

Next repair should wire the stale packet-source list into the read-model refresh cadence with producer-specific tests, then rerun `read_model_freshness_audit.py` until packet source `problem_count == 0`. This should be a generated-state producer/cadence repair, not manual JSON editing.
