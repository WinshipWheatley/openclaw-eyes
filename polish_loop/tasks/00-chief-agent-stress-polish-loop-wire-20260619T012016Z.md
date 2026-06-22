title: 00-chief-agent-stress-polish-loop-wire-20260619T012016Z
profile: quick
goal: Validate the Cassandra stale-status repair and Chief-to-polish-loop repair routing with harness evidence.
scope:
- Verify Cassandra answers orientation/status from the read-only snapshot path without timing out on a local model.
- Verify Cassandra routes prefixed Capital Hilton status questions to stale-aware finance_status before universal operator intake.
- Verify stale callouts ask Winship what to change and then use the session correction.
- Verify Chief reports the real Cassandra failure class in operator-facing language and queues a polish-loop repair packet.
- Verify the polish-loop PC review fallback runs repo-local venv verification commands instead of skipping them.
- Stress deterministic agent contracts for Chief, Cassandra, Guardian, Niles, Hermes, Report Bridge, voice routing, Telegram intake, and Chief acceptance.
- No new Cassandra tools. If new tool work becomes necessary, use cassandra_custom_tools.py rather than growing cassandra_brain.py directly.
success:
- Focused Cassandra/Chief repair tests pass.
- Multi-agent deterministic smoke tests pass.
- pc_review_fallback accepts and runs ./chief_env/bin/python verification commands.
- Chief can report WORKING when the harness passes or REWORK when evidence fails.
verification:
```bash
./chief_env/bin/python -m pytest -q tests/test_pc_review_fallback.py tests/test_chief_cassandra_failure.py tests/test_chief_llm_router.py tests/test_cassandra_status_wiring.py tests/test_cassandra_payment_verify.py tests/test_non_runner_cloud_bypass_policy.py tests/test_agent_runtime_readiness.py tests/test_agent_voice_response_layer.py tests/test_agent_voice_router.py tests/test_telegram_agent_intake.py tests/test_chief_acceptance_gate.py
```
agent_id: chief
generated_by: codex_desktop_manual_queue
generated_at: 2026-06-19T01:20:16Z
evidence:
- Codex Desktop ran the verification command above successfully: 239 passed in 60.13s.
- Cassandra listener restart and Telegram live checks remain the final runtime verification step.
