# Estate Topology

Status: PARTIAL

## Short human summary
The estate topology page summarizes machines, working copies, ownership areas, bridge paths, and unresolved topology questions from the topology registry/read-model.

## Confirmed facts
- Machine pc: PC / WSL backend machine - backend_and_runtime_development (CONFIRMED).
- Machine mac: Operator Mac - mac_app_excel_edge_and_runtime_working_copies (CONFIRMED).
- Mission Control app: owner=openclaw-mission-control / MAC_APP; status=CONFIRMED; rule=Swift app source belongs in the Mac app repo.
- Mac Excel Edge Worker: owner=openclaw-mission-control / MAC_APP; status=CONFIRMED; rule=Mac-local Excel/PDF helper code belongs with the Mac app/helper architecture.
- Access Broker: owner=split / SPLIT_MAC_UI_BACKEND_POLICY; status=PARTIAL; rule=Swift UI surface belongs in Mac app; policy/registry side belongs in backend when present.
- Live Arts invoice bundle: owner=openclaw-eyes / PC_BACKEND; status=CONFIRMED; rule=Live Arts backend bundle/read-model state belongs in /home/openclaw.
- Capital Hilton invoice bundle: owner=openclaw-eyes / PC_BACKEND; status=CONFIRMED; rule=Capital Hilton backend bundle/read-model state belongs in /home/openclaw.
- Request/Response service: owner=openclaw-eyes / PC_BACKEND; status=CONFIRMED; rule=The request/response backend service code belongs in /home/openclaw.
- Hermes: owner=openclaw-eyes / PC_BACKEND; status=PARTIAL; rule=Hermes reads /home/openclaw first for estate-wide task planning unless runtime evidence says otherwise.
- Chief/Guardian/Cassandra/Clara runtime: owner=openclaw-runtime / RUNTIME_ACTORS; status=PARTIAL; rule=Runtime actor implementation is mapped to openclaw-runtime pending canonical-home decision.
- Evidence-Grounded Context Registry: owner=openclaw-eyes / PC_BACKEND_REVIEW_BRANCH; status=PRESENT_ON_REVIEW_BRANCH; rule=Git remote branch is canonical and resolved by read-only remote inspection; Mac path is optional mirror.
- openclaw-eyes Mac repo: owner=openclaw-eyes / EYES_CONTEXT_REPO; status=CONFIRMED; rule=Mac Eyes is context/mirror, not live backend unless later proven.
- bridge/mirror transport: owner=transport / BRIDGE_TRANSPORT; status=PARTIAL; rule=/mnt/e/openclaw <-> /Volumes/openclaw_e is transport, not source truth.
- Bridge pc_e_drive_bridge: /mnt/e/openclaw on pc status PARTIAL.
- Bridge mac_openclaw_e_bridge: /Volumes/openclaw_e on mac status PARTIAL.

## Known unknowns
- Where should the canonical system knowledge registry live? [generated/read_models/openclaw_estate_topology_registry.json]
- Why Codex Web commits were not reachable from GitHub remotes. [generated/read_models/openclaw_estate_topology_registry.json]
- Whether Mac app should get a GitHub remote and backup/PR flow. [generated/read_models/openclaw_estate_topology_registry.json]
- Whether PC /home/openclaw and Mac /Users/.../Eyes should both track openclaw-eyes long-term. [generated/read_models/openclaw_estate_topology_registry.json]
- Whether openclaw-runtime should be the canonical home for Chief/Cassandra/Guardian runtime. [generated/read_models/openclaw_estate_topology_registry.json]
- Which repo Hermes should read first for estate-wide task planning. [generated/read_models/openclaw_estate_topology_registry.json]
- How Mac bridge permission failures should be represented. [generated/read_models/openclaw_estate_topology_registry.json]

## Tension / contradiction signals
- Codex Web commit unreachable: openclaw-eyes commit 33e00a6 is recorded as unreachable.
- Codex Web commit unreachable: openclaw-eyes commit 4ca4ed42171c23d60ef89493559808ef2789a19e is recorded as unreachable.
- Status conflict in source fields: codex_web_artifacts.2 has mixed status fields: {'status': 'PRESENT_ON_REVIEW_BRANCH', 'canonical_status': 'PENDING_REVIEW'}.
- Status conflict in source fields: registry_presence.2 has mixed status fields: {'status': 'PRESENT_ON_REVIEW_BRANCH', 'canonical_status': 'PENDING_REVIEW', 'current_state': 'PRESENT_ON_REVIEW_BRANCH'}.
- Status conflict in source fields: source_of_truth_areas.8 has mixed status fields: {'status': 'PRESENT_ON_REVIEW_BRANCH', 'canonical_status': 'PENDING_REVIEW', 'current_state': 'PRESENT_ON_REVIEW_BRANCH'}.

## Next useful actions
- Install estate topology registry in /home/openclaw. (CONFIRMED; owner PC_BACKEND)
- Mirror registry read-model to Mac. (PLANNED; owner BRIDGE_TRANSPORT)
- Add Mission Control app remote/back-up strategy. (PLANNED; owner MAC_APP)
- Keep system knowledge registry pending review until merged to main. (PENDING_REVIEW; owner PC_BACKEND)
- Build cross-registry merge only after each repo's registry is reachable locally. (PLANNED; owner PC_BACKEND)
- Stabilize Mac app dirty state before further PDF trials. (PLANNED; owner MAC_APP)

## What not to do
- Do not duplicate source-of-truth ownership across PC and Mac without a registry rule.
- Do not treat mirror paths as canonical write locations.
- Do not build a cross-registry merge over unreachable registry state.

## Source refs / input read-model refs
- generated/system_knowledge/openclaw_estate_topology_registry.sqlite (estate_topology_registry_sqlite)
- generated/read_models/openclaw_estate_topology_registry.json (estate_topology_registry)
- generated/read_models/estate_topology.json (estate_topology)
- generated/read_models/openclaw_estate_node_registry.json (openclaw_estate_node_registry)

Last generated timestamp: 2026-05-31T03:40:20+00:00

Generated understanding view. Registry/read-models/receipts remain source of truth.
