Bridge Trust / Sync Truth v0

State:
- Bridge trust state: `bridge_mount_missing`
- Secondary states: `local_readback_only, stale_pc_proof, waiting_for_mac`
- Check Engine should light: `true`
- Operator action required: `false`

What PC Knows:
- canonical_expected_count=202
- pc_observed_mac_count=192
- missing_expected_count=10
- hash_mismatch_count=0

What Mac Local Mirror Appears To Know:
- local_mac_manifest_count=194
- local_readback_status=`partial`
- full bridge proof: `false`

Bridge Proof:
- shuttle_mount_status=`missing`
- shuttle_completion_status=`stale`
- sync_lifecycle_state=`sync_requested_waiting_for_mac`
- request marker: `/mnt/e/openclaw/shuttle/to_mac/read_model_sync_required.json`

What Proof Is Missing:
- Mac mount availability proof for /Volumes/openclaw_e
- current Mac completion marker after the latest expected set
- PC import proof matching the latest Mac manifest
- all missing expected files mirrored with matching hashes

What Can Be Trusted:
- PC canonical expected set count
- PC-observed Mac proof count from sync_health
- operator-reported Mac mount/mirror facts as operator_reported context

What Cannot Be Trusted Yet:
- Mac-local file presence as full PC-Mac bridge proof
- Mirror Current status for the latest expected set
- Automatic remount or repair availability

Why Check Engine:
- Bridge/mirror proof is stale or blocked while the Mac mount is operator-reported missing; this is system/workbench reliability, not domain lane attention.

Safe Next Move:
- Keep Mission Control in Check Engine detail: show the truth split, wait for normal Mac sync proof, and ask Winship for manual Mac mount confirmation only if the mount remains unavailable.

Must Not Do:
- write OpenClaw artifacts to C:
- delete files or caches
- remount /Volumes/openclaw_e
- request, handle, or store credentials
- manual-copy generated files as the primary fix
- mutate Mission Control app code
- run backend repair automation
- activate agents or call models
- open browser, OAuth, Gmail, calendar, Coupa, Telegram, send, submit, or approval flows
- inspect raw private logs, broad temp listings, or raw file bodies

Boundary:
- Companion read-model only; sync_health remains the low-level mirror proof contract.
- No remount, delete, repair, credential, runtime, model, agent, browser, OAuth, Gmail, calendar, Coupa, Telegram, send, submit, or approval authority.
- No OpenClaw artifacts are written to C:.
