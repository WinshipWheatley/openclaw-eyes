# OpenClaw Estate Topology Registry

Plain Summary:
- Machines: 2 (`PC`, `Mac`).
- Working copies: 5.
- Actual repos: 3 (openclaw-eyes, openclaw-mission-control, openclaw-runtime).
- Known unknowns: 6.
- System knowledge registry is canonical on openclaw-eyes main; the review branch remains historical evidence.
- Older unreachable Codex Web commits remain recorded as artifacts, not source truth.

Working Copies:
- `pc_openclaw_eyes_backend`: `PC_BACKEND` on `pc` at `/home/openclaw` (dirty).
- `pc_openclaw_runtime`: `RUNTIME_ACTORS` on `pc` at `/home/openclaw_external/openclaw-runtime` (clean).
- `mac_mission_control_app`: `MAC_APP` on `mac` at `/Users/hwinshipwheatley/Developer/OpenClawMissionControl/OpenClaw Mission Controle` (dirty).
- `mac_openclaw_eyes_context`: `EYES_CONTEXT_REPO` on `mac` at `/Users/hwinshipwheatley/Eyes` (clean).
- `mac_openclaw_runtime`: `RUNTIME_ACTORS` on `mac` at `/Users/hwinshipwheatley/Developer/OpenClawIntake/openclaw-runtime` (clean).

Ownership Boundaries:
- Mission Control app: `MAC_APP` / `CONFIRMED`. Swift app source belongs in the Mac app repo.
- Mac Excel Edge Worker: `MAC_APP` / `CONFIRMED`. Mac-local Excel/PDF helper code belongs with the Mac app/helper architecture.
- Access Broker: `SPLIT_MAC_UI_BACKEND_POLICY` / `PARTIAL`. Swift UI surface belongs in Mac app; policy/registry side belongs in backend when present.
- Live Arts invoice bundle: `PC_BACKEND` / `CONFIRMED`. Live Arts backend bundle/read-model state belongs in /home/openclaw.
- Capital Hilton invoice bundle: `PC_BACKEND` / `CONFIRMED`. Capital Hilton backend bundle/read-model state belongs in /home/openclaw.
- Request/Response service: `PC_BACKEND` / `CONFIRMED`. The request/response backend service code belongs in /home/openclaw.
- Hermes: `PC_BACKEND` / `PARTIAL`. Hermes reads /home/openclaw first for estate-wide task planning unless runtime evidence says otherwise.
- Chief/Guardian/Cassandra/Clara runtime: `RUNTIME_ACTORS` / `PARTIAL`. Runtime actor implementation is mapped to openclaw-runtime pending canonical-home decision.
- Evidence-Grounded Context Registry: `PC_BACKEND_CANONICAL_MAIN` / `CANONICAL_ON_MAIN`. openclaw-eyes main is canonical for the system knowledge registry; review branch remains historical.
- openclaw-eyes Mac repo: `EYES_CONTEXT_REPO` / `CONFIRMED`. Mac Eyes is context/mirror, not live backend unless later proven.
- bridge/mirror transport: `BRIDGE_TRANSPORT` / `PARTIAL`. /mnt/e/openclaw <-> /Volumes/openclaw_e is transport, not source truth.

Known Unknowns:
- Why Codex Web commits were not reachable from GitHub remotes.
- Whether Mac app should get a GitHub remote and backup/PR flow.
- Whether PC /home/openclaw and Mac /Users/.../Eyes should both track openclaw-eyes long-term.
- Whether openclaw-runtime should be the canonical home for Chief/Cassandra/Guardian runtime.
- Which repo Hermes should read first for estate-wide task planning.
- How Mac bridge permission failures should be represented.

Recommended Actions:
- 1. Install estate topology registry in /home/openclaw.
- 2. Mirror registry read-model to Mac.
- 3. Add Mission Control app remote/back-up strategy.
- 4. Record system knowledge registry as canonical on openclaw-eyes main.
- 5. Build cross-registry merge only after each repo's registry is reachable locally.
- 6. Stabilize Mac app dirty state before further PDF trials.
- 7. Keep Live Arts PDF export blocked until Mac permission/helper architecture is resolved.

Boundary:
- This registry is documentation and generated read-model state only.
- No service, account, browser, Coupa, workbook, PDF, ledger, production, or push action is performed.
