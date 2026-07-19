# Patchbay Phase-0: PC-Local Core + Federated Mac Edge

Status: APPROVED-WITH-AMENDMENTS design; pre-implementation confer artifact
Mission: `PATCHBAY-PHASE0-EXTERNAL-POC`
Authoring runtime: `gpt-5.6-sol`, effort `ultra`, verified by turn context `019f7c43-ea09-7973-a099-ebd62b4d8431` at `2026-07-19T21:24:13.670Z`

## 1. Purpose and decision

Patchbay is a durable, event-driven notification substrate for internal and external OpenClaw actors. Phase 0 must prove that an event can cross a real machine and application boundary, wake the intended model without operator intervention, survive crashes and reconnects, and produce enough hop evidence for Chief to identify the exact broken segment.

The architecture is deliberately named **PC-local Patchbay core + federated Mac edge**. It is not universal yet. A platform becomes supported only after its transport adapter and host-control adapter pass the conformance suite. No Mac seat is `ENROLLED` until all real-Mac gates pass.

Phase 0 has two mandatory stages under one acceptance boundary:

1. **Phase 0A — PC ext4 core:** build and prove the isolated log, transactional outbox, listeners, cursors, routing, switchboard, watchdog, and Chief diagnostic bundle.
2. **Phase 0B — federated Mac edge:** add the Windows-native PC edge, SMB/APFS transport, authenticated connector identity, a real Mac host adapter, and pass ten cross-machine gates.

Both stages must pass before the enrollment wave or any live-lane migration begins.

## 2. Non-goals and hard boundaries

Phase 0 does not:

- cut over or mutate `Operator/` lanes, `fleet_coord/WAKE`, current monitors, or current doorbells;
- enroll production seats;
- grant send, payment, ledger, delete, move, credential, browser, or approval-gate authority;
- infer delivery from file detection, process presence, app focus, or a receiver notice;
- treat SMB as queue truth or shared-file mtimes as authoritative time;
- use a model polling loop;
- claim exactly-once transport. Delivery is at-least-once with idempotent logical effects.

The isolated roots are:

- PC core state: `/home/openclaw/.openclaw/patchbay-poc/`
- PC/Mac transport fixture: Windows `E:\openclaw\patchbay_poc_bridge\`, WSL `/mnt/e/openclaw/patchbay_poc_bridge/`, Mac `/Volumes/openclaw_e/patchbay_poc_bridge/`
- Mac local durable state: `~/Library/Application Support/OpenClaw/PatchbayPoC/`

Phase-0 payloads and read models cannot drive live business actions.

A read-only shadow adapter may inspect copied bytes from the live PC-Sol inbound lane to prove real filename, burst, and payload-shape compatibility. It has no cursor write, ACK write, rename, delete, or delivery authority against the live lane. Before/after inode, mtime, size, hash, service-state, and cursor fingerprints must prove the shadow changed nothing.

## 3. Existing failure being corrected

The 2026-07-19 PC-Sol doorbell detected an inbound change but held its oneshot worker behind transcript-only active-turn detection. Later files could not dispatch, and the operator had to send a message. The watcher also advanced its signature snapshot after failed delivery and rendered `needs_operator_kick=false` while recording delivery failures.

Patchbay replaces those failure semantics with:

- log truth instead of directory-signature truth;
- cursor advancement only after handler-durable ACK;
- exact live host binding instead of transcript inference;
- one fenced connector worker instead of one uncoordinated resume per file;
- explicit `UNBOUND`, `UNKNOWN`, `BACKPRESSURED`, and `DOWN` states instead of false green;
- replay after crash or reconnect.

## 4. Component boundaries

### 4.1 Contract layer

`patchbay_contracts.py` owns closed schemas and canonical encoding for:

- `ConnectorManifest`
- `CapabilityProfile`
- `PatchbayEvent`
- `DeliveryAck`
- `HopReceipt`
- `GapBark`
- `EdgeEnvelope`
- `EdgeCommitMarker`

It reuses Event Bridge vocabulary (`event_id`, `idempotency_key`, `correlation_id`, `parent_event_id`, safety boundary) without inheriting Event Bridge expiry or closed source-channel enums.

### 4.2 Core store

`patchbay_store.py` owns SQLite-WAL persistence and no transport behavior. The authoritative database is ext4-local.

Tables:

- `connectors`: registered identity, capabilities, authorized channels, auth key reference, state.
- `events`: append-only core sequence, event identity, channel, canonical payload, hash, trace lineage, producer sequence.
- `signal_outbox`: one row created in the same transaction as each new event.
- `delivery_attempts`: append-only listener delivery outcomes.
- `listener_cursors`: last handler-durable acknowledged core sequence per listener.
- `handler_receipts`: durable ACK identity and payload hash.
- `hop_receipts`: append-only trace evidence.
- `leases`: core-issued fencing epoch and current owner.
- `enrollment_runs`: nonce-bound capability self-test state.
- `edge_outbox`: reverse-delivery rows committed with their routed core event.
- `edge_replay_registry`: durable connector/producer-sequence/idempotency/hash to original commit-ACK binding.

`emit()` semantics:

1. Canonically encode and enforce size before opening the write transaction.
2. Use a connection initialized before any transaction with `PRAGMA journal_mode=WAL`, `PRAGMA foreign_keys=ON`, and a bounded `busy_timeout`; then begin `IMMEDIATE`.
3. Insert the event and outbox row in one transaction.
4. Commit.
5. Return `COMMITTED_OUTBOX_PENDING`; this means durable core acceptance, not signal publication or model delivery.

Idempotency key is `(connector_id, channel, idempotency_key)`:

- same canonical hash returns the original event and repairs a missing outbox/signal;
- changed hash raises `IDEMPOTENCY_CONFLICT`;
- `SQLITE_BUSY` retries the whole transaction from `BEGIN IMMEDIATE`; exhausted retries return a typed failure and never success.

Defaults:

- connector payload limit: 256 KiB;
- system hard limit: 1 MiB;
- busy timeout: 250 ms per attempt;
- retry schedule: 0, 25, 75, 150, and 300 ms;
- caller retains its durable source spool on failure.

### 4.3 Transactional signal publisher

`patchbay_signal_publisher.py` is a finite supervised drain. It converts pending outbox rows into immutable ext4 signal files.

Publication order:

1. Write a same-directory temporary file containing event id, core sequence, payload length, payload hash, channel, and trace id.
2. Flush and `fsync` the file.
3. Atomically create the immutable destination without overwrite by hard-linking the fully synced same-filesystem temp file to the final name with `os.link`, then unlinking the temp file. An existing destination is accepted only after exact byte/hash verification.
4. `fsync` the parent directory.
5. In a separate transaction, mark the outbox row published with the verified signal hash.

If a crash occurs after publication but before the database update, restart verifies the existing immutable signal and marks it published. `ENOSPC`, hash mismatch, permission failure, or checkpoint interruption leaves the row pending and emits a failure receipt. Startup and same-key replay repair missing signals. A systemd path unit watches the ext4 SQLite WAL for post-commit modification and invokes the finite publisher; emitter death after commit therefore cannot strand a row. Publisher startup always drains before waiting, and its own outbox-status commit may cause one harmless no-op invocation. The event log remains truth; the signal is only a wake hint.

### 4.4 Listener drain and cursor

`patchbay_listener.py` is invoked by systemd.path/inotify on ext4 or kqueue on macOS. One hint drains all unseen durable events in core order; notification count never equals event count.

A listener cursor advances only when `ack()` includes:

- exact listener id;
- event id and core sequence;
- canonical payload hash;
- exact handler receipt id;
- current fencing epoch/token;
- `HANDLER_DURABLE` status.

Crash before ACK replays. Crash after ACK does not. A stale fence, wrong hash, skipped sequence, or staging-only receipt is rejected without cursor advancement.

### 4.5 Leases, pressure, and bounded ambiguity

Local workers use nonblocking `flock` for process singleton behavior. The core also issues a monotonically increasing fencing epoch for each connector/listener ownership term. ACKs from a stale epoch are rejected.

During long drains, the owner renews its lease through the authenticated core connection. Mac wall time never decides ownership or expiry. Core monotonic time drives deadlines. A hung local worker retains its `flock`; a supervisor must terminate that exact worker before a new epoch is granted.

Before model delivery, the worker records an all-clear decision from:

- exact connector lease/fence;
- exact task/turn host state;
- `MemAvailable` reserve;
- Codex/Claude worker count;
- inflight count and cursor lag;
- backoff state.

The host probe has a per-call timeout and an event-scoped deadline. Three ambiguous outcomes or 30 seconds, whichever comes first, produce `UNKNOWN`/`UNBOUND`, a targeted bark, and the safe fallback: retain the event, stop spawning/resuming models, and surface operator attention. Nothing remains indefinitely pending without a decisive visible state.

### 4.6 Routing and capability profiles

`patchbay_registry.py` validates manifests and builds the routing table. A manifest declares transport capabilities separately from host-control capabilities.

Transport capabilities include:

- `emit`
- `listen`
- `durable_source_spool`
- `durable_cursor`
- `authenticated_edge`

Host-control capabilities include:

- `detect`
- `read_turn_state`
- `resume_idle`
- `queue_normal`
- `steer_active`

Routes declare required capabilities. A connector lacking one is rejected. “Add a line by manifest” becomes true only after that platform adapter passes conformance.

### 4.7 Exact PC Codex host and model binding

`patchbay_pc_codex_adapter.py` is the Stage-A external connector. It binds the Windows Desktop Codex CLI/app-server version and binary hash, `CODEX_HOME`, process-start identity, exact task id, and active turn id. The Phase-0 probe observed CLI/app-server `0.145.0-alpha.18` and binary SHA-256 `16db86b6bf81cc426032fd42216dd97e60f97b149272f1f9963845a0675dae94`; a changed version/hash requires a fresh compatibility receipt. Idle delivery invokes the exact session with explicit `--model` and `-c model_reasoning_effort=...` arguments; busy delivery uses the app-server JSON-RPC control plane (`initialize`, `thread/read`, then `turn/steer` with `expectedTurnId`) and never aborts the active turn. Version discovery accepts the exact `serverInfo.version` or version token in the current `userAgent` response, but only when it equals the manifest binding. An app-server version/hash mismatch, ambiguous turn, missing exact binding, unsupported control method, or timeout is `UNBOUND/BLOCKED`, never delivery.

Every connector manifest binds `expected_model` and `expected_effort`. The adapter verifies both in a nonce-bound turn-context receipt before emitting `HANDLER_DURABLE` or advancing a cursor. It does this on initial start, idle resume, and every supervisor respawn; inherited home defaults are never accepted as proof. The PC-Sol Phase-0 profile requires `gpt-5.6-sol` and `ultra`. A respawn at any other model or effort records `MODEL_BINDING_MISMATCH`, retains the event, and prevents enrollment.

## 5. Switchboard, path watchdog, and Chief

### 5.1 Separate health dimensions

`patchbay_switchboard.py` projects, for each connector and route:

- daemon state;
- mount identity;
- share readable/writable;
- PC edge available;
- ext4 commit path;
- local host endpoint;
- exact task binding;
- model delivery/ACK;
- cursor lag and last core sequence;
- lease owner/epoch;
- last trace and failure.

Each dimension is `UP`, `DEGRADED`, `DOWN`, or `UNKNOWN`. Process-up cannot override transport-down. A missing or wrong SMB mount is never replaced by creating the expected mount directory.

### 5.2 Hop traces and targeted bark

Every route is an ordered hop chain. Every hop records event id, trace id, run id, hop id, from, to, owner, status, evidence path, core receive time, and source diagnostic timestamp with uncertainty.

`patchbay_watchdog.py` compares the expected hop set for this run with actual receipts. On an event-scoped deadline it identifies the first missing or failed segment, probes only that segment once, and emits a `GapBark` labeled `CONFIRMED`, `SUSPECTED`, or `UNKNOWN`. A bark must carry this run id and nonce; stale barks cannot satisfy acceptance.

### 5.3 Chief context-first diagnostic bundle

`patchbay_chief_diagnostics.py` enforces this access order:

1. seal a Switchboard snapshot;
2. record Chief's prediction while the ping body is unavailable;
3. reveal the ping;
4. attach bark and trace evidence;
5. produce an evidence-bound diagnosis.

Connector ids, hop ids, statuses, owners, and evidence tokens are deterministic and validated verbatim. Generative voice may render the explanation but cannot change factual tokens.

## 6. Federated Mac edge

### 6.1 Topology

```text
Mac app/session
  <-> documented local host API
Mac seat adapter <-> APFS spool/cursor
  <-> authenticated immutable SMB blob + commit marker
Windows-native PC edge gateway
  <-> verified WSL submit/ACK
Patchbay ext4 SQLite log <-> ext4 outbox signals <-> inotify drain
```

Reverse delivery is equally explicit:

```text
ext4 event -> PC edge publish -> immutable SMB blob + commit marker
-> Mac kqueue hint/reconcile -> local host queue/resume/steer
-> model HANDLER_DURABLE ACK -> edge -> core ACK
```

### 6.2 Windows-native PC edge

`windows/patchbay_edge_gateway.ps1` runs on Windows and watches the server-side `E:` Phase-0 directory using `.NET FileSystemWatcher`. Critical ingress detection does not depend on WSL `/mnt/e` inotify.

The gateway persists a per-lane producer cursor and fencing epoch on the Windows system volume. It arms `FileSystemWatcher` before reconciling all committed markers, drains any notifications accumulated during reconciliation, and repeats a finite reconciliation after watcher overflow, share reconnect, service start, or server wake. Overflow or repeated read failure becomes a visible `DEGRADED` state with bounded backoff; no marker is acknowledged from notification presence alone.

Only one Windows gateway instance owns a lane. A named Windows mutex provides local singleton behavior, while the ext4 core grants a lane fencing epoch. The epoch is carried in submit requests, commit ACKs, and hop receipts; stale edge publications and ACKs are rejected. Renewal occurs through the authenticated core connection and core monotonic deadlines, never SMB time.

For each committed inbound blob it:

1. opens only a matching immutable commit marker;
2. validates confined paths, byte length, hash, connector id, producer sequence, idempotency key, nonce, and HMAC;
3. invokes the exact WSL submit CLI with explicit arguments and bounded timeout;
4. publishes a matching immutable, edge-authenticated ext4 commit ACK back to the Phase-0 share;
5. records independent edge-detect and ext4-commit hop receipts.

Commit ACK canonical bytes bind connector id, producer sequence, idempotency key, event id, core sequence, payload hash, nonce, trace id, and fencing epoch. A share-capable but unauthenticated process cannot retire APFS source state.

Reverse publication uses an ext4 `edge_outbox` committed with the routed event. A finite WSL relay is woken by ext4 WAL modification and pushes pending rows over an authenticated loopback-only TCP connection to the Windows gateway. The gateway durably stages the row on the Windows system volume, publishes the immutable SMB blob first and commit marker second, then returns an authenticated publish receipt. Reconnect drains the ext4 outbox; the loopback notification is a hint, not truth. No file is overwritten in place.

### 6.3 Mac durable adapter

`mac/patchbay_edge_adapter.py` uses an APFS outbound spool and durable cursor. SMB/kqueue is a low-latency hint, not durability.

The adapter:

- arms kqueue before reconciliation;
- reconciles all unseen commit markers on start, reconnect, remount, app start, wake, and reboot;
- keeps source pending until the matching ext4 commit ACK;
- keeps target pending until exact-task `HANDLER_DURABLE` ACK;
- replays by idempotency key after reconnect;
- never creates `/Volumes/openclaw_e` as a substitute for the real SMB mount;
- records mount identity and reports `DOWN` when it is absent or wrong.

SMB source timestamps and mtimes are diagnostic only. Core sequence is authoritative order. Per-producer sequence detects replay.

Exact replay semantics are closed: the same connector, producer sequence, idempotency key, and canonical hash returns the original core commit ACK; the same sequence or key with different bytes raises a conflict; an unrelated lower sequence is rejected as stale.

### 6.4 Connector authentication

Phase 0 uses per-connector HMAC-SHA256 keys stored outside the SMB share. The registry binds connector id to a key reference and authorized channels. The canonical signed bytes include protocol version, connector id, producer sequence, channel, idempotency key, nonce, trace id, payload length, payload hash, and fencing epoch. Edge commit ACKs and reverse publish receipts use the same authenticated-envelope rule.

Registry and evidence files contain only key ids, never key bytes. Phase-0 provisioning places the matching secret in the Mac login keychain, Windows DPAPI-protected user store, and a mode-`0600` ext4 key file outside the share and PoC evidence root. Direction- and purpose-specific subkeys are derived with HMAC labels (`mac_to_core`, `core_to_mac`, `commit_ack`, `publish_receipt`). Loaders reject symlinks, unexpected owners, group/world access, unknown key ids, or any path beneath the SMB root; logs expose only the key id and derived-key fingerprint.

Authentication proves connector possession, not action authority. Even authentic payloads cannot grant sends, money, deletes, moves, or gate activation. Cross-lane claims and stale producer sequences fail closed.

### 6.5 Seat-specific host adapter

`mac/patchbay_host_adapter.py` defines `detect`, `read_turn_state`, `resume_idle`, `queue_normal`, and `steer_active`. Implementations bind:

- app kind and version;
- process id and process-start identity;
- exact session/task id;
- exact active turn id when present;
- supported control endpoint and capabilities.

Bindings invalidate after process replacement, app/CLI/extension upgrade, logout, reboot, or task replacement. Silence never means idle. App focus, UI paste, or notification banners are not delivery.

If Codex Desktop exposes no supported resume/steer endpoint, that adapter is `DETECTOR_ONLY` and cannot enroll. Phase 0B must use a real Mac seat whose documented host endpoint proves the required idle wake and busy-turn behavior; otherwise Phase 0 remains blocked.

## 7. Enrollment

Enrollment state is:

```text
NEW -> REGISTERED -> SELF_TESTING -> ENROLLED
                         |              |
                         v              v
                       FAILED       REVOKED
```

The bidirectional self-test proves each claimed capability with nonce-bound traces. A connector cannot start routed work before `ENROLLED`. A failed or missing capability is visible to Chief.

While `SELF_TESTING`, a connector may use only isolated, nonce-scoped `patchbay.self_test.*` channels bound to its enrollment run. Production routes remain blocked. Successful receipts on those channels advance capability proofs but grant no production authority.

The enrollment wave is triggered only by one machine-checkable Phase-0 PASS receipt. Duplicate PASS events are idempotent. No prompt is broadcast before that receipt.

The aggregator recomputes every gate from same-run content-addressed evidence; it never accepts caller-asserted PASS strings. The explicit-approval prerequisite is satisfied only by a separately created local operator-terminal receipt bound to the run id and nonce. Operator/Fable/Opus notes, inbox content, Patchbay payloads, and WAKE records are rejected as authority sources. The seven done-quality results likewise name their evidence hashes and designated reviewer receipts; a missing, stale, cross-run, or mutable source blocks the aggregate trigger.

At that event, Opus relays exactly one general enrollment prompt:

> Identify your seat, model, host, app kind, and process-start identity. Connect through the Patchbay adapter available on your host; register a connector manifest declaring transport capabilities, host-control capabilities, emits, listens, health signal, and owner. Run the isolated bidirectional nonce self-test and report connector id, event ids, trace ids, fencing epoch, and PASS/FAIL for every claimed capability. Do not begin other work unless the Switchboard reports `ENROLLED`. Fail closed and name the exact adapter or hop blocker; never claim human-free wake without a nonce-bound model ACK trace.

## 8. Phase-0 acceptance gates

### 8.1 Fifteen PC-core gates

1. **Isolation:** live bridge/WAKE/monitor hashes, mtimes, and service states remain unchanged during the PoC.
2. **Closed contracts:** invalid manifests, symlinks/path escape, undeclared channels, control characters, oversized payloads, and authority-bearing payload claims fail closed.
3. **Durable emit:** kill after commit; exact event/hash survives, and no partial temp is committed.
4. **Idempotency:** same key/same bytes yields one event; same key/changed bytes rejects.
5. **Cursor replay:** kill before handler ACK replays; kill after handler ACK does not; order and zero loss hold.
6. **Event storm:** 1,000 events remain distinct while wake count/inflight is bounded and lag/backpressure is visible.
7. **Supervision/liveness:** killed adapter becomes `DOWN`; restart becomes `UP` only after self-test and fresh expected-model/expected-effort proof.
8. **External outbound:** external Codex emits nonce; internal listener wakes, receives exact bytes, and completes trace.
9. **External inbound:** internal emit causes the exact Codex task to wake without operator input, ACK, and echo the nonce.
10. **Mid-flight kill:** kill after commit/before actor ACK; restart replays with one logical effect and explicit replay trace.
11. **Trace completeness:** expected hops for this run equal terminal receipts; missing evidence fails.
12. **Gap/bark:** break one segment; exactly one targeted probe runs and bark names the segment and owner.
13. **Chief order:** timestamps prove Switchboard snapshot and prediction precede ping-body access; diagnosis cites board, bark, and trace.
14. **Internal taste / anti-snowglobe:** copied Operator-note and WAKE-v2 fixtures traverse sandbox adapters, and a read-only live-lane shadow proves current filename, burst, and payload-shape compatibility while before/after fingerprints prove no live writes; a third fixture connector is manifest-only after conformance.
15. **Safety and enrollment trigger:** hostile payloads grant no authority; PASS emits only when all checks and taste review are green.

Core fault injection also covers `SQLITE_BUSY`, exhausted retry, kill after event commit, kill before and after signal rename, `ENOSPC`, WAL checkpoint interruption, stale fence, wrong ACK hash, bounded probe timeout, and nonce causality.

### 8.2 Ten real-Mac gates

1. **Mac -> PC durability:** real Mac nonce reaches ext4 with matching event id, core sequence, and hash; edge kill before ACK yields one committed event and one logical effect.
2. **PC -> idle Mac autonomous doorbell:** exact idle task resumes and produces nonce-bound ACK with zero operator message.
3. **Busy-turn semantics:** normal queues; synthetic authorized urgent steers the exact active turn without abort or duplication. An unsupported steer capability is an honest `BLOCKED/FAIL`, never a Phase-0 PASS.
4. **SMB disconnect/remount:** pending events in both directions reconcile without loss or model polling.
5. **Mac sleep/wake and reboot:** pending events survive; adapter rebinds current task or reports `UNBOUND`; stale ids receive nothing.
6. **Coalesced/reordered notification:** one hint drains every unseen event in core order; notification count is never event count.
7. **Atomicity/tamper:** truncated blob, early marker, wrong length/hash, duplicate key, and changed-payload reuse fail without cursor advance.
8. **Clock skew:** skew Mac wall time both ways; core order, leases, and gap deadlines remain correct.
9. **Identity/cross-lane attack:** forged connector/lane from a share-capable process fails authentication and authorization.
10. **Causal evidence chain:** a closed expected-hop list binds the nonce and run id to `mac_spool -> edge_publish -> edge_detect -> ext4_commit -> reverse_edge_outbox -> edge_reverse_publish -> mac_detect -> host_control -> model_ack -> opus_readback`. Every hop carries the current fencing epoch where applicable; absent or stale evidence fails the run.

## 9. Activation frameworks

There is no missing seventh prerequisite. Patchbay must pass both frameworks:

### Admission — six runtime prerequisites

1. explicit operator approval;
2. rollback plan;
3. manifest validation;
4. runtime boundary proof;
5. logging/receipt path;
6. dry-run proof.

### Done-quality — seven gates

1. works;
2. non-snowglobe;
3. durable;
4. safe;
5. powerful;
6. optimized;
7. autonomous.

Phase-0 completion does not itself authorize live cutover. Phase 1 begins with a wiring audit and dual-run migration plan, separately conferred.

Admission and done-quality verification is implemented in `patchbay_activation_frameworks.py`, separate from `patchbay_worker_all_clear.py` resource/backpressure decisions. The verifier reads sealed evidence by hash, validates run/nonce/freshness and trusted source type, and computes each result. No API accepts a caller-provided PASS value.

## 10. Observability and honest states

The Phase-0 evidence bundle contains:

- core schema and migration version;
- event/outbox/cursor/lease counts;
- routing/cable read model;
- per-dimension Switchboard state;
- every acceptance run id, nonce, event id, trace id, hash, owner, and evidence path;
- fault-injection outcomes;
- before/after live-surface fingerprints;
- operator-facing PASS/FAIL summary.

No aggregate green can hide a failed dimension. `DETECTOR_ONLY`, `UNBOUND`, `UNKNOWN`, `BACKPRESSURED`, `DEGRADED`, and `DOWN` are first-class terminal readback states.

## 11. Rollback and failure containment

Phase 0 is additive and isolated. Rollback stops only Patchbay PoC services, preserves the SQLite log, spools, cursors, and receipts, and removes no live lane. A failed PoC produces a FAIL receipt and leaves enrollment blocked.

The currently stopped PC-Sol wake-v2b path is a separate operational safety action. It is not rearmed until its resume model binding is proven `gpt-5.6-sol` at `ultra` and the operator accepts the repair.

## 12. Prior art reuse

- Envelope vocabulary: `openclaw_event_bridge_contract.py`
- WAL/idempotency pattern: `ar_gig_to_cash_store.py`, amended with busy timeout and bounded retry
- Atomic publication: `fleet_coordination_contracts.py` and `materialization_publisher.py`, amended with a transactional outbox
- App-server host control: `codex_app_server_control.py`
- Registry/host lifecycle: `tool_protocol_adapter_registry_contract.py`, `operator_workbench_actor_host_registry.py`, `config/fleet_coordination.v2.json`
- Health and gap evidence: `agent_presence.py`, `no_response_watchdog.py`

The existing fleet watcher signature cursor, startup priming behavior, and failed-delivery advancement are explicitly not reused as durability semantics.
