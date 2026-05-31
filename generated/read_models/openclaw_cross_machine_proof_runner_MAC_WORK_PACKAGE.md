# OpenClaw Mac Local Proof Worker Work Package

Implement a Mac-local proof worker that watches only the bounded proof-job inbox.

- Expected Mac inbox: `/Volumes/openclaw_e/mac_local_jobs/inbox`
- Expected Mac results: `/Volumes/openclaw_e/mac_local_jobs/results`
- PC job path already written: `/mnt/e/openclaw/mac_local_jobs/inbox/mac_job_event_bridge_live_arts_prepare_pdf_f2ca7cfd360d4afc31a9.json`
- Mac-visible job path: `/Volumes/openclaw_e/mac_local_jobs/inbox/mac_job_event_bridge_live_arts_prepare_pdf_f2ca7cfd360d4afc31a9.json`
- Worker manifest expected at: `/Volumes/openclaw_e/mac_local_jobs/worker_manifest.json`
- Allowlisted job kind: `EMIT_EVENT_BRIDGE_ENVELOPE`
- For v0, emit only the provided `event_envelope` to the requested Event Bridge output path.
- Write a result JSON with `job_id`, `proof_run_id`, `status`, `emitted_event_path`, `correlation_id`, `error_code`, `error_message`, and `boundary_flags`.
- Do not use Excel, export PDFs, send email, open Gmail/browser/Coupa, read workbook cells, post ledgers, print, launch Chief, or call an LM.
