INSERT INTO proof_run VALUES ('event_bridge_live_arts_prepare_pdf', 'proof_run_event_bridge_live_arts_prepare_pdf_f2ca7cfd360d4afc31a9', '2026-05-31T17:22:01+00:00', '2026-05-31T17:22:01+00:00', 'MAC_WORKER_MISSING', 'correlation:cross_machine_proof:f2ca7cfd360d4afc31a9', '/mnt/e/openclaw/mission_control_capture_requests/inbox/openclaw_event_bridge_event_bridge_live_arts_prepare_pdf_f2ca7cfd360d4afc31a9.json', '/mnt/e/openclaw/mission_control_responses/to_mac/openclaw_response_for_mac_openclaw_event_bridge_event_bridge_live_arts_prepare_pdf_f2ca7cfd360d4afc31a9.json', '/mnt/e/openclaw/mac_local_jobs/inbox/mac_job_event_bridge_live_arts_prepare_pdf_f2ca7cfd360d4afc31a9.json', '{
  "route_status": "ROUTE_MATCHED",
  "selected_handler_id": "invoice_review_action_request.live_arts_md",
  "workflow_status": "WORKFLOW_ACTION_ROUTED"
}', '{
  "route_status": "",
  "selected_handler_id": "",
  "workflow_status": ""
}', '', '{
  "all_passed": false,
  "evaluated_check_count": 0,
  "failed_checks": []
}', 'Mac local proof worker is missing. The PC wrote the bounded proof job and generated a Mac work package; no proof pass was claimed.');
INSERT INTO proof_step VALUES ('create_proof_run', 'proof_run_event_bridge_live_arts_prepare_pdf_f2ca7cfd360d4afc31a9', 'PASS', 'Create proof run and correlation id.', '');
INSERT INTO proof_step VALUES ('write_mac_job', 'proof_run_event_bridge_live_arts_prepare_pdf_f2ca7cfd360d4afc31a9', 'PASS', 'Write Mac proof job to bridge.', '/mnt/e/openclaw/mac_local_jobs/inbox/mac_job_event_bridge_live_arts_prepare_pdf_f2ca7cfd360d4afc31a9.json');
INSERT INTO proof_step VALUES ('detect_mac_worker', 'proof_run_event_bridge_live_arts_prepare_pdf_f2ca7cfd360d4afc31a9', 'FAIL', 'Check Mac local proof worker manifest.', '/mnt/e/openclaw/mac_local_jobs/worker_manifest.json');
INSERT INTO proof_step VALUES ('wait_for_mac_result', 'proof_run_event_bridge_live_arts_prepare_pdf_f2ca7cfd360d4afc31a9', 'PENDING', 'Wait for Mac proof result.', '/mnt/e/openclaw/mac_local_jobs/results/mac_job_event_bridge_live_arts_prepare_pdf_f2ca7cfd360d4afc31a9.json');
INSERT INTO proof_step VALUES ('verify_event', 'proof_run_event_bridge_live_arts_prepare_pdf_f2ca7cfd360d4afc31a9', 'PENDING', 'Verify emitted Event Bridge envelope.', '/mnt/e/openclaw/mission_control_capture_requests/inbox/openclaw_event_bridge_event_bridge_live_arts_prepare_pdf_f2ca7cfd360d4afc31a9.json');
INSERT INTO proof_step VALUES ('wait_for_pc_response', 'proof_run_event_bridge_live_arts_prepare_pdf_f2ca7cfd360d4afc31a9', 'PENDING', 'Wait for scoped PC response.', '/mnt/e/openclaw/mission_control_responses/to_mac/openclaw_response_for_mac_openclaw_event_bridge_event_bridge_live_arts_prepare_pdf_f2ca7cfd360d4afc31a9.json');
INSERT INTO proof_step VALUES ('verify_route', 'proof_run_event_bridge_live_arts_prepare_pdf_f2ca7cfd360d4afc31a9', 'PENDING', 'Verify route result and selected handler.', '/mnt/e/openclaw/mission_control_responses/to_mac/openclaw_response_for_mac_openclaw_event_bridge_event_bridge_live_arts_prepare_pdf_f2ca7cfd360d4afc31a9.json');
INSERT INTO proof_step VALUES ('verify_boundary', 'proof_run_event_bridge_live_arts_prepare_pdf_f2ca7cfd360d4afc31a9', 'PENDING', 'Verify no-authority proof flags.', '/mnt/e/openclaw/mission_control_responses/to_mac/openclaw_response_for_mac_openclaw_event_bridge_event_bridge_live_arts_prepare_pdf_f2ca7cfd360d4afc31a9.json');
INSERT INTO proof_step VALUES ('write_receipt', 'proof_run_event_bridge_live_arts_prepare_pdf_f2ca7cfd360d4afc31a9', 'PENDING', 'Write proof receipt/read-model.', '');
INSERT INTO proof_artifact VALUES ('mac_job_request', 'proof_run_event_bridge_live_arts_prepare_pdf_f2ca7cfd360d4afc31a9', '/mnt/e/openclaw/mac_local_jobs/inbox/mac_job_event_bridge_live_arts_prepare_pdf_f2ca7cfd360d4afc31a9.json', '1', 'mac job request');
INSERT INTO proof_artifact VALUES ('mac_worker_manifest', 'proof_run_event_bridge_live_arts_prepare_pdf_f2ca7cfd360d4afc31a9', '/mnt/e/openclaw/mac_local_jobs/worker_manifest.json', '0', 'mac worker manifest');
INSERT INTO proof_artifact VALUES ('mac_job_result', 'proof_run_event_bridge_live_arts_prepare_pdf_f2ca7cfd360d4afc31a9', '/mnt/e/openclaw/mac_local_jobs/results/mac_job_event_bridge_live_arts_prepare_pdf_f2ca7cfd360d4afc31a9.json', '0', 'mac job result');
INSERT INTO proof_artifact VALUES ('event_bridge_envelope', 'proof_run_event_bridge_live_arts_prepare_pdf_f2ca7cfd360d4afc31a9', '/mnt/e/openclaw/mission_control_capture_requests/inbox/openclaw_event_bridge_event_bridge_live_arts_prepare_pdf_f2ca7cfd360d4afc31a9.json', '0', 'event bridge envelope');
INSERT INTO proof_artifact VALUES ('pc_scoped_response', 'proof_run_event_bridge_live_arts_prepare_pdf_f2ca7cfd360d4afc31a9', '/mnt/e/openclaw/mission_control_responses/to_mac/openclaw_response_for_mac_openclaw_event_bridge_event_bridge_live_arts_prepare_pdf_f2ca7cfd360d4afc31a9.json', '0', 'pc scoped response');
INSERT INTO proof_result VALUES ('event_bridge_live_arts_prepare_pdf', 'proof_run_event_bridge_live_arts_prepare_pdf_f2ca7cfd360d4afc31a9', 'MAC_WORKER_MISSING', '', '', '', 'correlation:cross_machine_proof:f2ca7cfd360d4afc31a9');
INSERT INTO proof_failure VALUES ('missing_mac_worker', 'proof_run_event_bridge_live_arts_prepare_pdf_f2ca7cfd360d4afc31a9', 'MAC_WORKER_MISSING', 'Mac local proof worker manifest is missing or does not support EMIT_EVENT_BRIDGE_ENVELOPE.', '/mnt/e/openclaw/mac_local_jobs/worker_manifest.json');
