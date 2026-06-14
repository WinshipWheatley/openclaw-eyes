# OpenClaw Cross-Machine Proof Runner

- Status: `MAC_WORKER_MISSING`
- Proof: `event_bridge_live_arts_prepare_pdf`
- Proof run: `proof_run_event_bridge_live_arts_prepare_pdf_f2ca7cfd360d4afc31a9`
- Correlation: `correlation:cross_machine_proof:f2ca7cfd360d4afc31a9`
- Mac worker ready: `False`
- Operator summary: Mac local proof worker is missing. The PC wrote the bounded proof job and generated a Mac work package; no proof pass was claimed.

## Paths

- pc_job_inbox: `/mnt/e/openclaw/mac_local_jobs/inbox`
- mac_job_inbox: `/Volumes/openclaw_e/mac_local_jobs/inbox`
- pc_result_dir: `/mnt/e/openclaw/mac_local_jobs/results`
- mac_result_dir: `/Volumes/openclaw_e/mac_local_jobs/results`
- pc_event_inbox: `/mnt/e/openclaw/mission_control_capture_requests/inbox`
- pc_response_dir: `/mnt/e/openclaw/mission_control_responses/to_mac`

## Result

- `MAC_WORKER_MISSING` route=`` workflow=`` handler=``

## Failures

- `MAC_WORKER_MISSING`: Mac local proof worker manifest is missing or does not support EMIT_EVENT_BRIDGE_ENVELOPE. (`/mnt/e/openclaw/mac_local_jobs/worker_manifest.json`)

## Boundary

No LM, Chief, services, email/Gmail/browser/Coupa, workbook cell read, PDF export, ledger mutation, production mutation, or physical printing is authorized.
