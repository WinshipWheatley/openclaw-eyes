# OpenClaw Interactive 8B Keep-Warm

This timer preserves the operator-facing `qwen3:8b-q4_K_M` residency without
evicting another model, preempting a GPU lease, waiting for the model slot, or
retrying a hot lane. Every fire goes through `run_interactive_model_call` and
uses the shared interactive profile, including the 2048 context ceiling.

## Activation

Activation is operator-window work. The scoped installer renders only
`openclaw-8b-keepwarm.service` and `openclaw-8b-keepwarm.timer`, reloads the user
unit manager, and enables the timer:

```bash
scripts/install_openclaw_stack.sh --apply --enable --keepwarm-only
```

Record the unit names and verify the model is resident within 15 minutes of a
boot. After an overnight idle interval, record first-touch latency and compare
it with the interactive latency threshold. The existing GPU health watcher owns
latency alerting; this timer only warms and writes its latest local receipt to
`~/.openclaw/receipts/openclaw_8b_keepwarm_latest.json`.

## Rollback

```bash
systemctl --user disable --now openclaw-8b-keepwarm.timer
```

Disabling this timer does not stop Ollama and does not unload any model.
