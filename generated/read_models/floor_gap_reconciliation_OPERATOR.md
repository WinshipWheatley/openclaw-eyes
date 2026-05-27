# Floor Gap Reconciliation

Status: FLOOR_GAP_RECONCILIATION_NO_LIVE_ACTIONS
Lanes classified: 22
Lanes raised this pass: 7

Raised this pass:
- Gate 1 operational request snapshot
- Universal intake
- Private Mode readiness
- Provider activation receipts
- Live LM shadow trial
- Read-model/mirror visibility
- Production/live blockers

Weakest remaining lanes:
- Production/live blockers: production_token_vault_inactive, provider_activation_receipts_missing, live_model_enablement_receipt_missing, production_privacy_policy_receipt_missing, rollback_disable_receipt_missing
- Gate 1 ingress/privacy/request readiness: Needs live device trust registry integration before live LM activation.
- Gate 1 operational request snapshot: Snapshot is fixture-only; live LM activation still needs provider/privacy receipts.
- Gate 2 intent ingest: Operator-facing visibility improved; live LM1 proposals still require explicit activation.
- Gate 3 role package: Package compiler is shadow-ready; live LM2 use still needs activation and production privacy receipts.

No live model, tool, workflow, or production action is enabled.
