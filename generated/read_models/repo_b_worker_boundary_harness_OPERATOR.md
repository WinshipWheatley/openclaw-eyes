# Repo B Worker Boundary Harness

Repo B can supply useful worker ideas and selected bounded workers, but Repo A must wrap, sanitize, time-limit, and receipt them before chat sees results.

What this enables:
- Classify legacy workers by value and risk.
- Generate scoped worker input packages with exclusions.
- Return token-safe candidate readbacks to Repo A and Mac chat.
- Quarantine unsafe services, listeners, and repair loops.

Worker examples:
- Chief offline reasoning worker: WRAP_AS_WORKER via FIXTURE_ONLY
- Cassandra draft-only worker: DRAFT_ONLY via DRAFT_ONLY_BRIDGE
- Google read-only broker: BRIDGE_READ_ONLY via READ_ONLY_BRIDGE
- CPA budget calculator: COMPUTE_ONLY via COMPUTE_ONLY_BRIDGE
- Niles/music creative worker: WRAP_AS_WORKER via FIXTURE_ONLY
- Telegram listener intake: REFERENCE_ONLY via NONE
- Watchdog/repair worker: UNSAFE_DO_NOT_CONNECT via NONE

Boundary:
- No Repo B worker executed.
- No Repo B service/listener/watcher/daemon started.
- Telegram output, email send, Google write, file mutation, watchdog repair, credentials, and raw bodies are blocked.

Next safe move: Use this harness as the common decision layer before adding any new Repo B wrapper.
