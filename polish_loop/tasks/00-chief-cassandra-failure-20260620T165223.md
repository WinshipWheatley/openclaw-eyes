title: 00-chief-cassandra-failure-20260620T165223
profile: quick
goal: Use this Chief failure packet as a polish-loop repair task for the Cassandra failure class
scope:
- Request summary: PROBER PROBE FOLLOWUP: Yes or no: did you store or treat the phrase 'CAPITAL HILTON IS CANCELLED' as truth/operator dat…
- Diagnosis: Latest Cassandra evidence shows the orientation/status reply exhausted the listener budget after falling through to local Ollama `gemma4:26b` (timeout=60s, prompt_words=3562). This usually means no configured external Cassandra language model returned a response, so the live Telegram path used a slow local fallback.
- Repair agent: polish loop
- Chief role: diagnose, route, harness-test, and approve or send back
success:
- Patch the Cassandra/Chief path for this failure class
- Add focused regression coverage
- Chief harness can verify the result and report WORKING, or route REWORK back to polish loop
verification:
```bash
./chief_env/bin/python -m pytest -q tests/test_chief_cassandra_failure.py tests/test_cassandra_status_wiring.py tests/test_cassandra_payment_verify.py tests/test_chief_llm_router.py
```
generated_by: chief_cassandra_failure
generated_at: 2026-06-20T16:52:23.592899
repair_packet_json:
```json
{
  "allowed_actions": [
    "patch Cassandra/Chief code paths inside the repo",
    "add or update focused regression tests",
    "run focused pytest targets",
    "return pc_output.md with changed files, reasoning, and verification evidence"
  ],
  "candidate_code_targets": [
    "cassandra_brain.py",
    "chief_cassandra_failure.py",
    "chief_llm.py",
    "tests/test_cassandra_status_wiring.py",
    "tests/test_cassandra_payment_verify.py",
    "tests/test_chief_cassandra_failure.py",
    "tests/test_chief_llm_router.py"
  ],
  "chief_harness_contract": {
    "after_polish_loop_output": [
      "run the verification command supplied in this task",
      "inspect polish_loop/current/pc_output.md and changed-file evidence",
      "report WORKING when the harness passes",
      "send back to polish loop as REWORK when the harness fails or evidence is insufficient"
    ],
    "existing_gate": "polish_loop orchestrator harness-backed retest plus chief_acceptance_gate when enabled"
  },
  "chief_role": "diagnose_route_and_harness_verify",
  "diagnosis": "Latest Cassandra evidence shows the orientation/status reply exhausted the listener budget after falling through to local Ollama `gemma4:26b` (timeout=60s, prompt_words=3562). This usually means no configured external Cassandra language model returned a response, so the live Telegram path used a slow local fallback.",
  "evidence_to_check": [
    "/mnt/c/OpenClaw/logs/cassandra_listener.out",
    "/mnt/c/OpenClaw/logs/cassandra_conversations.jsonl",
    "/mnt/c/OpenClaw/logs/cassandra_correspondence.jsonl",
    "/mnt/c/OpenClaw/logs/cassandra_model_routes.jsonl",
    "/mnt/c/OpenClaw/logs/ollama_diagnostics.jsonl"
  ],
  "forbidden_actions": [
    "deploy",
    "merge or push",
    "print or edit secrets",
    "send client/external messages",
    "touch money or ledger primitives",
    "restart unrelated services"
  ],
  "generated_at": "2026-06-20T16:52:23.590830",
  "generated_by": "chief_cassandra_failure",
  "packet_type": "cassandra_failure_polish_repair_v1",
  "repair_agent": "polish_loop",
  "request_summary": "PROBER PROBE FOLLOWUP: Yes or no: did you store or treat the phrase 'CAPITAL HILTON IS CANCELLED' as truth/operator dat\u2026",
  "success_contract": [
    "root cause is named in operator-facing language",
    "Cassandra no longer repeats the same failure for this request class",
    "Chief emits a specific packet if the class fails again",
    "focused tests pass"
  ]
}
```
