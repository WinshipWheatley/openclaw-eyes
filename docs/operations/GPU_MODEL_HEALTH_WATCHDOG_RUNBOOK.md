# GPU Model Health Watchdog Runbook

Installation and unit-lifecycle changes require operator approval and the runtime
approval-brain check. The collector itself is observation-only: it reads bounded
local diagnostics, Ollama's local process listing, and aggregate GPU memory, then
atomically writes two generated read-model files.

## Narrow deployment

Run from the canonical `/home/openclaw` checkout after the source commit is
promoted. The scoped mode renders only the watchdog service and timer.

```bash
bash scripts/install_openclaw_stack.sh --dry-run --gpu-health-only
bash scripts/install_openclaw_stack.sh --apply --enable --gpu-health-only
```

The timer is the boot-required unit. The one-shot service is expected to become inactive after each successful pass and must not be added to the required-active service list.

## Read-only verification

```bash
systemctl --user is-enabled openclaw-gpu-model-health.timer
systemctl --user is-active openclaw-gpu-model-health.timer
systemctl --user list-timers openclaw-gpu-model-health.timer --no-pager
journalctl --user -u openclaw-gpu-model-health.service --since "10 minutes ago" --no-pager
python3 -m json.tool /home/openclaw/generated/read_models/gpu_model_health.json
sed -n '1,160p' /home/openclaw/generated/read_models/gpu_model_health_OPERATOR.md
```

## Rollback

With operator approval, disable the timer, remove only its two rendered unit files,
and reload the user manager. Source rollback is a separate Git decision.

```bash
systemctl --user disable --now openclaw-gpu-model-health.timer
rm -f "$HOME/.config/systemd/user/openclaw-gpu-model-health.service"
rm -f "$HOME/.config/systemd/user/openclaw-gpu-model-health.timer"
systemctl --user daemon-reload
```

## Authority boundary

The watchdog never invokes a model, unloads a model, restarts a service, kills a
process, sends a notification, or files an action proposal. A degraded or unknown
read model is evidence for an operator or a future governed broker consumer; it is
not authority to mutate runtime state.
