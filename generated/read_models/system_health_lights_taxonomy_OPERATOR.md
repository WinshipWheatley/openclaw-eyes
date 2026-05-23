System Health Lights Taxonomy v0

PC Import Proof:
- Mac-to-E-drive-to-PC sync proof complete: `false`
- canonical_expected=291
- observed=218
- missing_expected=73
- hash_mismatch=4
- backend_head=200c3e134c2b16e75a2090d33b8498d188396e6e
- backend_head_matches_expected=`false`
- Core PC import proof is not complete.

Current Lights:
- Check Engine: `WARNING`
  - Chief posture still has older non-bridge maintenance warnings or source-truth items; bridge-specific status is read from sync_health through Check Transmission.
  - Opens: Chief diagnostic/system health lane
- Check Transmission: `WARNING`
  - Stable map bundle pending
  - Opens: Bridge / mirror / sync trust lane
- Low Fuel / Low Battery: `WARNING`
  - C: was recently near full and later cleaned to about 22GB free, but this lane did not perform a new live disk measurement.
  - Opens: Resource posture lane
- Oil Pressure / Coolant: `WARNING`
  - RD Client trace growth and Mac validation friction are maintenance risks even if the bridge import proof is now current.
  - Opens: Maintenance / environment degradation lane
- Brake / Parking Brake: `ON_NORMAL`
  - Runtime, send, approval, remount, credential, and repair authorities remain intentionally blocked in these contracts.
  - Opens: Authority boundary lane
- Traction Control: `QUIET`
  - No current action package in this lane needs a confidence detour; deterministic confidence UI should stay quiet.
  - Opens: Confidence / detour lane

Steel Thread Flow:
- Understand: ELI5/operator orientation.
- Inspect: machine contract/proof.
- Decide: package/detour/fix path.

Check Transmission Detail:
- Stable map bundle pending

What Makes Lights Quiet:
- Check Engine: Chief-owned system proof is current, no core workbench fault is active, and bridge faults are owned by Check Transmission.
- Check Transmission: PC proof agrees with Mac completion, sync_health has missing_expected=0 and hash_mismatch=0, and no final app-visible sync-health echo is pending.; Stable map generation and Mac receipt agree; raw proof-detail churn does not block app-visible map readiness.
- Low Fuel / Low Battery: Resource pressure is measured healthy or no longer materially affects operator action.
- Oil Pressure / Coolant: Maintenance risk is measured stable, bounded, or resolved without recurring warnings.
- Brake / Parking Brake: No relevant authority boundary affects the current lane or package.
- Traction Control: Current package confidence is deterministic/full-trust or no package is being considered.

What Must Not Be Done Automatically:
- write OpenClaw artifacts to C:
- delete files or caches
- remount /Volumes/openclaw_e automatically
- handle or store credentials
- create auto-remount authority
- run Mac commands from PC
- manual-copy generated read-model files as the primary fix
- mutate Mission Control app code
- repair backend services from this taxonomy
- activate agents or call models
- open browser, OAuth, Gmail, calendar, Coupa, Telegram, send, submit, or approval flows
- inspect raw private logs, raw trace contents, broad temp listings, or raw file bodies

Boundary:
- Taxonomy/read-model only; no UI, repair, remount, delete, credential, runtime, model, agent, browser, OAuth, Gmail, calendar, Coupa, Telegram, send, submit, or approval authority.
- Fresh machine proof beats stale operator-reported bridge facts for current light classification.
- No OpenClaw artifacts are written to C:.
