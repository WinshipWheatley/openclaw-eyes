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

PC-Sol may still write its ordinary coordination receipts to its own outbound lane and a pointer-only Opus WAKE for design/implementation confers. Those control-plane records are not Patchbay runtime traffic, are excluded from Phase-0 acceptance evidence, and grant no runtime authority.

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
- `Route`
- `PatchbayEvent`
- `DeliveryAck`
- `HopReceipt`
- `DimensionEvidenceClaim`
- `AuthenticatedDimensionEvidence`
- `GapBark`
- `EdgeEnvelope`
- `EdgeCommitMarker`
- `TrustedTestWindow`
- `BarrageInteraction`
- `BarrageWorkOrder`

It reuses Event Bridge vocabulary (`event_id`, `idempotency_key`, `correlation_id`, `parent_event_id`, safety boundary) without inheriting Event Bridge expiry or closed source-channel enums.

`HopReceipt` is a first-class run-scoped contract, not an untyped diagnostic map. An external producer first signs a canonical `HopClaim` containing protocol version, connector id, event id, trace id, **run id, nonce**, a closed hop subject, hop id, `from_connector`, `to_connector`, owner, status, evidence content hash and immutable evidence path, optional typed subject-claim hash, source diagnostic timestamp and its uncertainty, payload hash, and fencing epoch when applicable. A subject is either `EVENT`, with literal `subject_key="event"` and all delivery selectors absent, or `DELIVERY`, with exact nonempty `route_id`, `listener_id`, `target_connector_id`, `lane_id`, positive integer `delivery_seq`, Phase-0 `listener_id == lane_id`, and `subject_key="delivery:" + SHA256(canonical({route_id,listener_id,target_connector_id,lane_id,delivery_seq}))`. Booleans are not integers and empty or wrong-type selectors fail canonicalization. Append-only identity is `(run_id, nonce, event_id, trace_id, subject_key, hop_id)`, so one event can produce the same fixed hop id independently for multiple routed deliveries. The ext4 ingest transaction verifies that claim, stamps the actual nonzero core-receive monotonic time and boot id, and stores the claim, source signature, and core ingest fields as one `HopReceipt`; external producers never guess or hardcode the core time. Core-local producers create the same stored shape directly. `GapBark` uses the same run id, nonce, event id, trace id, and expected-hop-set hash. Every query, append, compare, and acceptance API takes the full run/nonce/event/trace identity explicitly and, for delivery hops, the closed subject; omitted, stale, cross-run, cross-nonce, cross-event, or cross-delivery values fail closed rather than falling back to a current run.

`Route` binds one exact producer connector and emitted channel to one exact target connector and listener plus required transport/host capabilities and a bounded health TTL. `DimensionEvidenceClaim` binds connector, route, dimension, run, nonce, event, trace, payload hash, source sequence, superseded evidence id, state, and immutable evidence hash/path. Its canonical hash must equal the authenticated dimension hop's signed subject-claim hash, while every causal, payload, connector, and evidence field must independently equal that same stored receipt. Only then may core ingest add source core sequence, core boot id, trusted receive monotonic time, and store-derived expiry as `AuthenticatedDimensionEvidence`.

### 4.2 Core store

`patchbay_store.py` owns SQLite-WAL persistence and no transport behavior. The authoritative database is ext4-local.

Tables:

- `connectors`: registered identity, capabilities, authorized channels, auth key reference, state.
- `events`: append-only core sequence, event identity, channel, canonical payload, hash, trace lineage, producer sequence.
- `routes`: immutable producer/channel to target/listener bindings and their required capabilities.
- `listener_deliveries`: the exact per-listener fanout snapshot committed with each event.
- `signal_outbox`: one row created in the same transaction as each new event.
- `delivery_attempts`: append-only listener delivery outcomes.
- `listener_cursors`: last handler-durable acknowledged core sequence per listener.
- `handler_receipts`: durable ACK identity and payload hash.
- `hop_receipts`: append-only trace evidence.
- `dimension_evidence` and `dimension_evidence_conflicts`: authenticated supersession chains and changed-duplicate facts for Switchboard projection.
- `leases`: core-issued fencing epoch and current owner.
- `enrollment_runs`: nonce-bound capability self-test state.
- `edge_outbox`: reverse-delivery rows committed with their routed core event, retaining global `core_sequence` while allocating a gap-free `delivery_sequence` within each authenticated `(connector_id, lane_id)`.
- `edge_delivery_sequences`: next reverse `delivery_sequence` per authenticated connector/lane, allocated inside the same `BEGIN IMMEDIATE` transaction as the routed event and edge-outbox row.
- `edge_replay_registry`: durable full canonical signed-envelope hash plus connector/producer-sequence/idempotency identity to original commit-ACK binding. Channel, run, nonce, trace, fence, spool kind, local row, payload metadata, and all signature-relevant fields are part of exact replay; changing any one conflicts.

`emit()` semantics:

1. Canonically encode and enforce size before opening the write transaction.
2. Use a connection initialized before any transaction with `PRAGMA journal_mode=WAL`, `PRAGMA foreign_keys=ON`, and a bounded `busy_timeout`; then begin `IMMEDIATE`.
3. Require the authenticated producer to equal `event.connector_id`; verify the store-resident producer declares the channel in `manifest.emits`; select only active routes whose store-resident target declares it in `manifest.listens` and satisfies the route capabilities.
4. Insert the event, immutable route-set hash, exact `listener_deliveries` rows, and signal outbox row in one transaction.
5. Commit.
6. Return `COMMITTED_OUTBOX_PENDING`; this means durable core acceptance, not signal publication or model delivery.

Idempotency key is `(connector_id, channel, idempotency_key)`:

- same complete canonical event identity (event id, payload hash, run, nonce, trace, and parent) returns the original event and original delivery snapshot and repairs a missing outbox/signal; a later route change never creates historical delivery;
- any changed causal field or payload hash raises `IDEMPOTENCY_CONFLICT`;
- `SQLITE_BUSY` retries the whole transaction from `BEGIN IMMEDIATE`; exhausted retries return a typed failure and never success.

Defaults:

- connector payload limit: 256 KiB;
- system hard limit: 1 MiB;
- busy timeout: 250 ms per attempt;
- retry schedule: 0, 25, 75, 150, and 300 ms;
- caller retains its durable source spool on failure.

Listener reads are route-specific joins over `listener_deliveries`, ordered by global `core_seq`. Before a read or ACK, the store scans that listener's snapshot: every referenced route must pass its canonical hash check, and each delivery's listener, producer, channel, event, and core sequence must match the immutable route and event. Any internal mismatch fails closed rather than leaking or silently skipping work. A listener cursor may safely jump global gaps belonging to other routes but can ACK only its own next pending delivery. Unrelated events therefore neither leak to a handler nor require synthetic skip ACKs, and a crash in one route cannot block another listener.

Switchboard truth is store-selected rather than caller-assembled. The store accepts a dimension claim only by joining it to one authenticated full-identity hop receipt, a committed source event with exact producer/channel/run/nonce/trace/payload identity, the event's immutable route/listener/core-sequence delivery snapshot, the active route and exact target, current boot, signed typed-claim hash, and matching evidence hash/path. The route TTL derives expiry from trusted core monotonic receive time. Selection fixes an exact `(run_id, nonce, through_core_seq)` causal cut, permits cut zero before the first event so registered zero-evidence routes remain projectable, rejects a negative or above-high-water cut, and reads the internal clock once. One linear authenticated supersession chain yields its current terminal state; no current terminal yields `UNKNOWN`, while a changed duplicate, fork, cycle, dangling link, multiple head, or contradictory fact is deterministically `DEGRADED`. Canonical sorting makes arrival order irrelevant.

### 4.3 Transactional signal publisher

`patchbay_signal_publisher.py` is a finite supervised drain. It converts pending outbox rows into immutable ext4 signal files. `patchbay_confined_io.py` supplies the single reusable publication primitive used here and by later Phase-0 evidence writers.

Before any write, the service opens every absolute root component descriptor-relatively from `/` with `O_DIRECTORY|O_NOFOLLOW`, verifies the installer-sealed exact device, inode, owner, and mode-`0700` identity, and retains the final directory descriptor for the process lifetime. The publication API accepts that `VerifiedDirectory` plus one closed basename; temporary create, hard link, existing-file read, unlink, and directory `fsync` are all relative to the retained descriptor. Destination files must be single-link, same-device, same-owner regular files at the exact requested `0400` or `0600` mode. It never authorizes a write using `resolve()`, `exists()`, or a path check followed by reopen.

Publication order:

1. Create a mode-`0600` temporary file descriptor-relatively beneath the retained verified signal root containing event id, core sequence, payload length, payload hash, channel, and trace id.
2. Flush and `fsync` the file.
3. Atomically create the immutable destination without overwrite by descriptor-relative hard-link of the fully synced same-filesystem temp file to the final basename, then descriptor-relative unlink of the temp file. An existing single-link destination is accepted only after an `O_NOFOLLOW` regular-file open plus exact identity/mode/byte/hash verification. A real death between link and unlink may leave exactly one closed-format temporary alias to that same inode; restart descriptor-relatively proves the exact two-link shape, unlinks only that alias, `fsync`s the directory, and re-verifies the single-link final. Any extra or differently named alias conflicts.
4. `fsync` the parent directory.
5. Reopen the configured root path no-follow and require it still names the retained device/inode. A parent swap can receive no writes; if the path was rebound, publication remains on the retained verified inode but the database mark is held pending.
6. In one `BEGIN IMMEDIATE` transaction, mark the outbox row published with the verified signal hash **and** append the canonical signal-publication hop receipt. Neither database effect may commit alone.

If a crash occurs after publication but before the database transaction, restart verifies the existing immutable signal and atomically records both publication state and receipt. If a historical or injected partial state contains one without the other, startup reconciliation derives the canonical missing side from the immutable event/signal bytes and records an explicit repair receipt; it never fabricates success from notification presence. Startup also audits rows already marked published: a missing signal is recreated from the immutable event when possible, while changed/conflicting bytes become visible failure and never a no-op. `ENOSPC`, hash mismatch, permission failure, or checkpoint interruption leaves the row pending and records a failure receipt in its own durable transaction. Exact `before_link`, `after_link_before_unlink`, `after_unlink_before_dir_fsync`, `after_dir_fsync`, `before_mark`, and `after_mark` fault hooks are part of the acceptance-only test interface and are unreachable in normal service configuration. A restrictive `umask` is normalized with `fchmod` on the new descriptor, then device/inode kind/owner/link-count/mode are verified before link. Startup and same-key replay repair missing signals. A systemd path unit watches the ext4 SQLite WAL for post-commit modification and invokes the finite publisher; emitter death after commit therefore cannot strand a row. Publisher startup always drains and audits before waiting, and its own outbox-status commit may cause one harmless no-op invocation. The event log remains truth; the signal is only a wake hint.

### 4.4 Listener drain and cursor

`patchbay_listener.py` is invoked by systemd.path/inotify on ext4 or kqueue on macOS. One hint drains all unseen durable deliveries for that exact listener in core order; notification count never equals event count. The event transaction permanently snapshots per-listener delivery membership. A listener never scans or handles an unrelated route, and a later manifest/route edit cannot retroactively expose an old event.

A listener cursor advances only when `ack()` includes:

- exact listener id;
- event id and core sequence;
- canonical payload hash;
- exact handler receipt id;
- current fencing epoch, exact lease owner id, and unforgeable lease token;
- `HANDLER_DURABLE` status.

Crash before ACK replays. Crash after ACK does not. A stale fence, wrong hash, skipped next delivery for that listener, or staging-only receipt is rejected without cursor advancement. Global sequence gaps belonging only to other listeners are permitted and cause neither leakage nor stalling.

### 4.5 Leases, pressure, and bounded ambiguity

Local workers use nonblocking `flock` for process singleton behavior. The core also issues a monotonically increasing fencing epoch for each connector/listener ownership term. ACKs from a stale epoch are rejected.

During long drains, the owner samples trusted core monotonic time before acquisition and sets a conservative half-TTL renewal threshold. Before every handler it compares a new core sample with that threshold; when due, it renews through the authenticated core connection using the exact owner, opaque token, fence, and boot tuple. Renewal rotates the opaque token, returns the authenticated current lease, and derives the next conservative half-TTL threshold from the pre-call sample. Only that returned lease reaches the handler and ACK; the old token is immediately stale, and a renewal mismatch stops before delivery. Mac wall time never decides ownership or expiry. Core monotonic time drives deadlines, and every persisted lease binds the PC core boot id. On boot-id mismatch the prior monotonic deadline is never compared with the new boot's clock: the row is invalidated, the fence epoch advances, and the old owner/ACK is stale. A hung local worker retains its `flock`; a supervisor must terminate that exact worker before a new epoch is granted.

Before model delivery, the worker records an all-clear decision from:

- exact connector lease/fence;
- exact task/turn host state;
- `MemAvailable` reserve;
- Codex/Claude worker count;
- inflight count and cursor lag;
- backoff state.

The host probe has a per-call timeout and an event-scoped deadline. Three ambiguous outcomes or 30 seconds, whichever comes first, produce `UNKNOWN`/`UNBOUND`, a targeted bark, and the safe fallback: retain the event, stop spawning/resuming models, and surface operator attention. Nothing remains indefinitely pending without a decisive visible state.

### 4.6 Routing and capability profiles

`patchbay_registry.py` validates manifests and builds the routing table. A manifest declares transport capabilities separately from host-control capabilities. Authorization is directional: the authenticated producer must equal `event.connector_id` and declare the channel only in `emits`; each route's exact target/listener must declare it only in `listens`. Membership in the opposite set never substitutes. The store repeats those checks from its resident immutable manifests inside the event transaction.

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

Routes declare required capabilities. A connector lacking one is rejected. The store derives canonical requirement bytes and the route hash from the same closed `Route`; no caller supplies a parallel JSON representation. Every route resolution and inventory scan re-canonicalizes both stored requirements objects and the complete immutable tuple before comparing the stored hash, so malformed, duplicate/noncanonical, or internally mismatched rows are corruption rather than a second truth. Route ids and their producer/channel/target/listener/capability tuple are immutable; exact replay is idempotent and changed reuse conflicts. Event fanout snapshots the current route ids, so revocation affects future events only. “Add a line by manifest” becomes true only after that platform adapter passes conformance.

Capability enrollment derives its receipt from one committed self-test event, that event's exact immutable route/listener delivery binding, the matching current-fence `HANDLER_DURABLE` ACK, one authenticated full-identity capability hop, and descriptor-confined immutable evidence. The hop must be `PASS`, carry the committed payload hash, travel from and be owned by the proving connector to the exact `pc-core` identity, and name the ACK's fence epoch. Failed, cross-payload, reversed, foreign-owner, foreign-core, or stale-fence hops remain audit evidence but cannot enroll a connector. The resulting capability receipt is store-derived and binds run, nonce, event, trace, route, listener, payload, hop, evidence, model, effort, fence, and status; callers cannot submit an asserted receipt.

The registry exposes one authoritative, stably ordered switchboard inventory over every active immutable route. Each row binds the exact target connector and route to the current store-resident enrollment state, declared host capabilities, and host capabilities proven by store-derived receipts under that connector's exact current enrollment run and nonce. Zero-evidence routes remain present with an empty proven set; stale-run receipts are excluded. The health projector therefore never needs a caller-supplied connector list and can project an absent dimension as `UNKNOWN` rather than silently omitting the route.

### 4.7 Exact PC Codex host and model binding

`patchbay_pc_codex_adapter.py` is the Stage-A external connector. It binds the Windows Desktop Codex CLI/app-server version and binary hash, `CODEX_HOME`, process-start identity, exact task id, active turn id, and the hash/path of one immutable execution profile. The Phase-0 pinned pair is CLI/app-server `0.145.0-alpha.18` and binary SHA-256 `16db86b6bf81cc426032fd42216dd97e60f97b149272f1f9963845a0675dae94`; a different pair is accepted only with an embedded compatibility-signer-sealed receipt binding that exact pair and its immutable compatibility-test digest. A self-asserted, forged, or cross-binary receipt fails. Independently of any matching receipt, PC-Sol policy requires model `gpt-5.6-sol`, effort `ultra`, read-only sandbox, network disabled, no tools/external connectors, and only `nonce_echo`. The profile is descriptor-safely verified before construction and reread immediately before reservation and execution. Idle delivery pins explicit model/effort arguments; busy delivery uses `initialize`, `thread/read`, then `turn/steer(expectedTurnId)` and never aborts. Version/hash, profile, process, task, turn, or compatibility mismatch is `UNBOUND/BLOCKED`, never delivery.

Every connector manifest binds `expected_model` and `expected_effort`. A turn-context record alone is not a handler ACK. Before emitting `HANDLER_DURABLE` or advancing a cursor, the adapter descriptor-safely opens one immutable content-addressed completed assistant record and proves `status=completed`, `role=assistant`, the exact nonce-echo text, and exact run, nonce, event, trace, payload, control intent, task, turn, binding/profile, model, and effort identity. It does this on initial start, idle resume, and every supervisor respawn; inherited home defaults, an in-progress turn, stdout substring, user echo, or mutable transcript are never accepted as proof. The PC-Sol Phase-0 profile requires `gpt-5.6-sol` and `ultra`. A respawn at any other model or effort records `MODEL_BINDING_MISMATCH`, retains the event, and prevents enrollment.

Stage-A is a live PC host surface even though its messages are isolated. The descriptor-confined terminal approval recorder/verifier and live-context checker are implemented before the adapter. `verify_operator_approval()` returns an internally sealed `VerifiedOperatorApproval`, not a caller-constructible parsed claim. After verifying that object and current live context, the single `require_live_context()` API issues an opaque process-MAC-sealed `VerifiedLiveCapability` bound to the exact run, nonce, connector, task/plan hashes, action, environment, and expiry. The verifier/issuer and trusted UTC clock are module-owned. No production verifier, runner, dependency bundle, adapter, or connector-emitter API accepts a caller `now`, clock, verifier, issuer, or mint method; deterministic tests replace only the private clock boundary. Every verifier call compares the capability's task-binding and test-plan hashes to the concrete surface's independently expected hashes. Adapter construction requires the `pc_adapter_construct` capability; every endpoint, process, CLI, state, profile, all-clear, resume, steer, reconciliation, and ACK-read surface obtains and verifies a fresh action-specific capability immediately before that one surface. Before even the effect broker, delivery requires the event run/nonce to equal the adapter run/nonce. A `None`, boolean, callable noop, alternate verifier, copied object, cross-task capability, wrong-action capability, backdated-clock attempt, or expired capability cannot satisfy the adapter.

The sealed approval wrapper retains the descriptor-validated exact receipt path, full signed-receipt SHA-256, and unsigned claim SHA-256 under its process MAC. Its only evidence conversions are closed gate/manifest objects carrying that exact identity; later activation, final-manifest, and barrage code never calls an undefined method or invents a second approval digest. Because the wrapper dataclass is publicly constructible for audit, malformed window/path/hash/MAC field types and invalid digests are normalized to `LiveGateBlocked("verified_operator_approval_required")` before comparison; raw `TypeError` or `ValueError` never escapes an authority check.

The runner may not construct the live adapter, inspect a live task binding/profile, or issue `resume`, `queue`, or `steer` until approval binds the exact run id, nonce, task/process binding, closed allowed-action set, fault set, immutable predeclared test-plan path/hash, and expiry. It retains distinct binding-read and profile-read capabilities, and each descriptor-safe verifier consumes and revalidates its capability immediately before the exact content-addressed open. It requires every parsed field to equal the independently supplied expected values; only those parsed approved values reach the adapter. Endpoint discovery must then return explicit `VERIFIED`—`BLOCKED` is terminal. The test plan exists before live evidence and names every intended surface/action/fault; approval never depends circularly on output evidence. A note, inbox item, WAKE, model output, or Patchbay event is never approval. Expiry blocks the next action and triggers only already-journaled restoration.

Before idle resume or active steer, `patchbay_pc_control_journal.py` installs full-identity intent, host-acceptance, and completed-ACK tables in the same FULL-synchronous SQLite database as cursor and hop receipts. Recovery reconciles the exact bound task: zero acceptances may execute once, one exact acceptance is verified/fsynced, and multiple or changed acceptances block. Finalization is one transaction that verifies acceptance, stores the completed ACK, inserts `model_ack`, advances the cursor once, and transitions to `ACK_VERIFIED`. Wrong model/effort in either the top-level ACK or turn context returns explicit non-durable `MODEL_BINDING_MISMATCH`; other causal identity mismatches are `BLOCKED`. SQLite, store, journal, typed host, and ACK errors seal `BLOCKED`; synthetic crashes propagate.

The public `PCCodexAdapter` is a real class whose constructor contains no peer, runner, store, host probe, watchdog, broker, profile loader, monotonic clock, fault hook, control journal, dependency bundle, or factory parameter. It verifies construction authority first, then opens one private module-owned concrete runtime. Only the isolated test module replaces that private runtime classmethod, then invokes the unchanged public facade. Raw process-start observation, exact-active-turn lookup, all-clear fact collection, and all-clear recording helpers remain private; callers can reach the corresponding live surfaces only through capability-guarded public operations.

The Stage-A actor receives only the closed payload object `{schema_version=1, kind="nonce_echo", challenge_nonce}`; the authenticated event envelope supplies the first-class run id and matching nonce. There is no free-form instruction field. Decoding rejects extra keys, nested objects, control characters, authority synonyms, a challenge that differs from the event nonce, or a recursively discovered action/approval claim before host control. The adapter renders the one fixed logical message `PATCHBAY_PHASE0_NONCE_ECHO <nonce>`. The bound PoC task uses a dedicated tool-disabled profile behind a hard effect broker that denies business sends, money, ledger writes, deletes, moves, credential access, browser control, and gate changes regardless of payload authenticity. Its only accepted logical effect is returning the exact nonce. An approval authorizes the named host-control test, never any business effect.

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

The projector does not accept a caller-ordered evidence iterable, clock, or caller-selected current value. It first seeds every route from authoritative registry inventory, so zero evidence remains visible as `UNKNOWN`. It asks the store for an authenticated `EvidenceSelection` and a same-run/cut `SwitchboardFactSelection`; both must echo exact run, nonce, and causal cut, and duplicate/missing/extra route or dimension keys fail. The fact projection joins the route to same-run delivered core sequence, current-boot/nonexpired lease owner and epoch, and latest authenticated trace/failure evidence, so those values are concrete fields rather than state labels hidden inside prose. Concrete frozen `ConnectorHealth`, `Switchboard`, and `SwitchboardSnapshot` types recursively freeze dimension/reason and route mappings and seal those facts. `route()` is exact, `connector()` succeeds only for one route, and deterministic `to_canonical_mapping()` covers selection identity plus sorted route rows for snapshot hashing. Sealing cannot relabel identities. The store uses trusted monotonic samples/current core boot and preserves absent/expired as `UNKNOWN` and conflict/fork/cycle as `DEGRADED`. `AUTONOMOUS_WAKE_PROVEN` requires registry `ENROLLED` plus all four proven capabilities; detector-only still means an operator kick is required. Foreign-run, future-sequence, cross-route, shuffled, or last-writer-wins input cannot manufacture green.

### 5.2 Hop traces and targeted bark

Every route is an ordered hop chain. Every hop records the complete `HopReceipt` contract above, including event id, trace id, run id, nonce, closed EVENT/DELIVERY subject and canonical subject key, hop id, from, to, owner, status, evidence hash/path, core receive time, source diagnostic timestamp with uncertainty, payload hash, and applicable fence. Delivery-scoped traces are selected by their exact route/listener/target/lane/delivery subject, so fan-out lanes cannot collide.

Core-local components append hop receipts directly through `PatchbayStore`. Mac, Windows, and Opus-side producers never open the ext4 store: they append a canonical signed hop receipt to their local durable spool, transport it through the authenticated edge envelope, and `patchbay_hop_ingest.py` validates connector, run, nonce, trace, event, hop ownership, payload hash, and fence before one append-only core insert. Changed duplicate receipts conflict.

`patchbay_watchdog.py` exposes no implicit-current-run overload or caller probe argument. It selects receipts on full trace identity and rejects missing/mismatched run or nonce. Production `PathWatchdog.open_production()` owns its concrete store journals and endpoint; its public constructor has no endpoint, journal, clock, or fault dependency, and the endpoint/control-plane/runtime production constructors likewise accept no injected driver, signer, verifier, transport, or fault hook. At deadline the watchdog fsyncs one stable-id `TargetedProbeIntent` before its concrete local endpoint. The control plane signs the exact request hash/bytes, enrolled caller connector/key, and target connector. Concrete `SQLiteAuthenticatedPatchbayConnectorRuntime` verifies that current enrollment signature before reservation or physical probing; its separate FULL-synchronous target intent/result schema rejects changed authenticated request identity, runs only its module-owned bounded physical probe, target-signs the result/evidence/remote commit identity, commits it before reply, and returns the identical signature-verified durable receipt after a commit/reply crash. The endpoint verifies target identity/signature on RPC return and local replay. Only private fixtures inject test dependencies. Local endpoint and watchdog journals then repair without a second physical probe/bark across the supported remote-commit/local-persistence seams. Forged or changed request, receipt, or remote commit id conflicts. The bark retains complete trace identity; stale or cross-nonce barks cannot update health.

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

The gateway persists a per-lane ingress producer cursor and fencing epoch on the Windows system volume. It arms `FileSystemWatcher` before reconciling all committed markers, drains any notifications accumulated during reconciliation, and repeats a finite reconciliation after watcher overflow, share reconnect, service start, or server wake. Startup and renewal mutate one shared state object containing the ingress cursor, lease owner/token/boot/fence, and reverse journal cursors; `Invoke-Reconcile` returns that full object and callers replace their reference with it, so a stale outer copy can never overwrite a repaired cursor during the next renewal write. For each connector sequence it durably publishes and verifies the immutable commit-ACK blob and signed ACK marker before advancing that connector's Windows cursor; crashes after either publication step replay to the same canonical ACK and repair the same no-overwrite pair. Overflow, a sequence gap, or repeated read failure becomes a visible per-connector `DEGRADED` state with bounded backoff and preserves all unseen markers for that connector; the reconciliation loop then continues with every other connector/lane whose next sequence is present. One damaged lane cannot starve a healthy lane, and no marker is acknowledged from notification presence alone.

Only one Windows gateway instance owns a lane. A named Windows mutex provides local singleton behavior. On startup the gateway calls the length-framed, mutually HMAC-authenticated `ACQUIRE_LANE(run_id, nonce, lane_id, process_start_id)` operation on the listener bound to exactly `127.0.0.1`; the ext4 core transaction advances and returns the lane fencing epoch, opaque high-entropy `lease_token`, and a core-monotonic renewal deadline. The gateway sends `RENEW_LANE(run_id, nonce, lane_id, process_start_id, lease_token, fence_epoch, core_boot_id)` on that same authenticated connection before half the term elapses. The core compares the token, owner, epoch, and boot inside the renewal transaction and returns a newly generated token even when the epoch and owner remain unchanged. Windows stops processing that lane on timeout, disconnect, boot-id mismatch, token mismatch, or stale-epoch response. Every ingress transaction verifies a separate gateway-signed `IngressAttempt` wrapper against that exact current lease before accepting replay or a new event. The durable source envelope and replay identity remain immutable across gateway epochs, so the exact old envelope may be retried under a fresh current attempt and receive its original core-signed ACK; a stale gateway cannot create a valid current attempt. For reverse work, the core keys physical dispatch authorization by owner, token, boot, and fence: an exact replay returns the prior attempt, but every same-epoch token rotation creates a higher immutable attempt revision for each nonterminal logical delivery. The Windows-observed `edge_detect` claim is itself durably indexed and reused byte-for-byte across an uncertain retry, while its core-stamped receipt is inserted or verified in the same event transaction. The epoch is carried in attempt, commit-ACK evidence, publish receipts, and hop receipts; stale publications and unauthenticated ACKs are rejected. SMB time and Windows wall time never grant or renew ownership.

For each committed inbound blob it:

1. opens only a matching immutable commit marker;
2. validates confined paths, byte length, hash, connector id, producer sequence, idempotency key, nonce, and HMAC;
3. constructs, signs, and durably indexes the Windows-observed `edge_detect` claim from the marker bytes and opened file identity;
4. invokes the exact WSL submit CLI with explicit arguments and bounded timeout, passing the immutable envelope/current ingress attempt plus those exact signed `edge_detect` bytes and hash into the one core transaction;
5. requires that transaction to insert-or-verify the core-stamped `edge_detect` receipt and independently produced `ext4_commit` receipt before it returns the canonical core ACK;
6. publishes that matching immutable, edge-authenticated ext4 commit ACK back to the Phase-0 share.

Commit ACK canonical bytes bind connector id, producer sequence, channel, idempotency key, event id, core sequence, submitted payload hash, full immutable edge-envelope hash, run id, nonce, trace id, source fencing epoch, closed spool kind, and exact local spool row id. The core signs those closed canonical bytes; replay/APFS rows persist the bytes plus an external SHA-256 of them, avoiding any self-referential hash field. A share-capable but unauthenticated process cannot retire APFS source state.

The WSL submit path may ingest the authenticated Windows `edge_detect` receipt, but it may never synthesize, backdate, or replace it. Missing Windows signing material or a missing receipt leaves that hop absent and the gate honestly `BLOCKED/FAIL`.

Reverse publication uses an ext4 `edge_outbox` committed with the routed event and the exact immutable Task-2 `listener_deliveries` snapshot. Each row carries `route_id` and `listener_id`; Phase 0 defines `lane_id == listener_id`, and the same core transaction allocates the next contiguous `delivery_sequence` for authenticated `(target_connector_id, listener_id)` while retaining global `core_sequence`. The global sequence remains causal evidence; reverse consumers order and advance their lane cursor by `delivery_sequence`, so unrelated core traffic cannot create a false gap. Outbox content is epoch-independent and its lifecycle is `PENDING_PUBLISH -> PUBLISHED_AWAITING_HANDLER -> HANDLER_DURABLE`. An authenticated Windows publish receipt advances only the middle state; it does not retire the row. At every acquire or token-rotating renewal the core reauthorizes every nonterminal row against the exact lease identity and issues a higher immutable attempt revision unless that owner/token/boot/fence tuple is an exact replay. Only an authenticated target-signed `HandlerDurableBinding`, carried with the target's signed `model_ack` hop claim, may retire it. The binding covers route/listener; the complete canonical `DeliveryAck` and hash; exact run/nonce/event/trace/target/lane/delivery/core/logical identity; the historical signed dispatch attempt revision/hash/owner/lease-token hash/core boot/fence; the signed `HANDLER_CONTROL` purpose, challenge hash and nonce, and proof hash; the accepted Mac boot plus control start/completion/deadline; the exact signed `host_control` claim; the authenticated host completion; and an independently signed source-model receipt under the distinct `model_receipt` purpose key. Core reloads and reauthenticates every referenced immutable attempt, challenge, proof, claim, completion, model receipt, and handler ACK without applying today's expiry to the already completed historical effect. In one evidence-only ext4 transaction, that sealed historical authority advances the exact canonical listener delivery/cursor and the same edge-outbox row to `HANDLER_DURABLE`, or rolls both back. A restart, token rotation, or epoch rollover before terminal arrival therefore re-fences the same logical row without invalidating or duplicating an already proved effect.

`patchbay_edge_relay.py` is a finite startup-first drain woken by ext4 WAL modification. It opens a length-framed TCP session to the Windows gateway listener bound only to the approved loopback interface, performs a nonce challenge and mutual HMAC authentication using distinct `rpc_wsl_to_windows` and `rpc_windows_to_wsl` purpose keys, acquires/renews the lane lease, and sends one byte-identical closed `STAGE_REVERSE` schema shared with PowerShell. Its ordered fields are `run_id`, `nonce`, `route_id`, `listener_id`, `lane_id`, `target_connector_id`, `delivery_seq`, `core_seq`, `event_id`, `producer_connector_id`, `channel`, `idempotency_key`, nullable `parent_event_id`, `trace_id`, `payload_length`, `payload_sha256`, `edge_delivery_sha256`, full `edge_delivery`, and full `dispatch_attempt`; every repeated value, including exact null-vs-string parent identity, must match both authenticated objects and persist in the Windows phase journal and publish receipt. It drains `(target_connector_id,lane_id)` heads round-robin. A verified gap or content rejection persists `DEGRADED` only for that exact key. Transport, timeout, framing, session-authentication, and stale-fence failures close/forget the session and raise to the reconnect loop, because delivery status is ambiguous; they are never downgraded to per-item failures. Windows and Python derive every purpose key from the master using byte-identical `HMAC-SHA256(master, ASCII("patchbay-phase0") || 0x00 || ASCII(label))`; cross-language fixed vectors are normative.

The Windows gateway validates every repeated `STAGE_REVERSE` field against both signed objects and stages it under a confined ACL-protected directory on the Windows system volume as an immutable blob, marker, and phase journal. Every reverse artifact path encodes each identity segment independently with one canonical injective encoding and fixed separators; raw concatenation of target, lane, delivery, or attempt fields is forbidden. Thus `(target=a-b,lane=c)` and `(target=a,lane=b-c)` cannot collide. Each file is flushed through the open handle before the directory entry is advanced. It then publishes the exact SMB blob first and commit marker second with create-new/no-overwrite semantics, verifies both canonical hashes, signs and durably spools an `edge_reverse_publish` hop receipt, and returns an authenticated publish receipt binding route id, listener id, run id, nonce, event id, trace id, producer/channel/idempotency, target connector id, lane id, delivery sequence, core sequence, logical payload hash, marker hash, attempt revision, owner/token/boot, and fence. The relay atomically records that receipt and advances `edge_outbox` only to `PUBLISHED_AWAITING_HANDLER`.

Startup/reconnect reconciliation reads the Windows phase journal and repairs all crash points: before staging, after staging, after blob publication, after marker publication, and after receipt return but before core status commit. Journal identity includes target connector, lane, delivery sequence, attempt revision, exact authenticated request bytes/hash, and immutable logical-delivery hash. Repair invokes an internal verified-request continuation; it never manufactures a new peer frame or calls a peer-signing helper. Existing destinations are accepted only after exact bytes and hashes match; the same publish receipt is replayed only while its attempt still matches the current lease. Typed session, framing, authentication, disconnect, and timeout exceptions are rethrown to the outer reconnect loop rather than misclassified as per-item content errors. A stale request or receipt remains evidence, is never replayed, and causes the nonterminal ext4 row to be redispatched under a newly core-signed attempt without aborting repair of healthy lanes. An outer listener loop reaccepts and reacquires after disconnect; before processing a new session it repairs only current-fence journals and marks stale ones for redispatch. Marker verification is isolated per connector/lane. Even a malformed filename receives a non-throwing synthetic attribution such as `malformed-sha256:<digest>` before its degraded fact is recorded, so no second parser failure can starve healthy owners. Reconnect drains the ext4 outbox and Windows staging journal before waiting; the loopback notification is a hint, not truth. No file is overwritten in place.

The final `opus_readback` hop is produced by `scripts/patchbay_opus_readback.py` only after the isolated Opus connector reads the exact nonce/model ACK. It signs and spools a receipt through the same authenticated edge path. If no exact Opus host binding or signing key is available, the causal-chain gate is `BLOCKED`; the acceptance runner cannot synthesize this hop.

### 6.3 Mac durable adapter

`mac/patchbay_edge_adapter.py` uses an APFS outbound spool and durable cursor. SMB/kqueue is a low-latency hint, not durability.

The adapter:

- arms kqueue before reconciliation;
- reconciles all unseen commit markers on start, reconnect, remount, app start, wake, and reboot;
- keeps source pending until the matching ext4 commit ACK;
- keeps target pending until exact-task `HANDLER_DURABLE` ACK;
- accepts every valid source into APFS even while SMB is down, records the mount observation separately, and publishes it after remount;
- replays by idempotency key after reconnect;
- never creates `/Volumes/openclaw_e` as a substitute for the real SMB mount;
- records mount identity and reports `DOWN` when it is absent or wrong.

One APFS-local SQLite database owns source events, hop claims, route/listener-bound target staging rows, append-only dispatch-proof bindings, handler receipts, ACKs, and a single durable `producer_sequence` allocator per authenticated connector id. Its production SQLite open is capability-gated: runtime securely opens and verifies the existing APFS parent and database descriptor with no-follow, then passes only those retained descriptors plus the basename to a native confined VFS. That VFS owns the descriptors for the connection lifetime and performs every database, rollback-journal, WAL, and SHM open/access/delete with descriptor-relative `openat`/`fstatat`/`unlinkat`, no-follow, and repeated owner/mode/device validation. There is no path-based `sqlite3.connect` fallback; absent VFS capability fails before SQLite sees a pathname, and an untrusted sidecar fails before use. Source idempotency binds connector, channel, key, deterministic source event id, run, nonce, trace, and payload hash. That event id is part of the canonical signed envelope, replay row, commit ACK, and every hop. Every event-scoped APFS lookup for a hop, proof, receipt, or staged target uses the full available `(run_id, nonce, event_id, trace_id)` identity plus route, listener, and its closed hop/target/lane/delivery selectors; shortened run/trace-only helpers are forbidden. The lane cursor alone is intentionally keyed by authenticated target/lane because it is an aggregate, but every cursor mutation uses the full selected staged-event CAS. Enqueuing a source event atomically allocates its producer sequence, inserts the source, and inserts its mandatory `mac_spool` claim before either can publish; hop-only enqueue uses the same allocator. Source and hop spools therefore cannot both claim sequence 1, even under concurrent independent connections or restart. Before filtering by state, `publish_once()` proves allocator/count/min/max continuity plus exact polymorphic ownership for the connector. It keyset-pages only actionable `PENDING` source/hop rows, so completed history never consumes the action budget; a source-created higher-sequence `edge_publish` can be discovered in the same bounded call. A separate durable rotating audit cursor reopens `PUBLISHED`/`CORE_ACKED` immutable pairs: missing exact blobs or markers are recreated from APFS canonical bytes without a new sequence, while changed bytes conflict and are never overwritten. A retired gap retains later rows. Handler completion has a deliberate repairable boundary: the first APFS transaction persists the exact canonical handler receipt, authenticated host completion, independently signed source-model receipt, signed host-control claim, accepted historical dispatch attempt, exact consumed `HANDLER_CONTROL` challenge/proof/timing selector, and byte-stable signed terminal-claim intent in `HANDLER_RECEIPT_DURABLE`, while allocating no producer sequence or outbound row. Those handler-authority columns are separate from the mutable current staging attempt, so a later stage rebind cannot rewrite an already accepted effect. The second transaction reauthenticates those stored bytes, inserts an already-complete route/listener-bound target-signed terminal `model_ack`, atomically allocates its sequence and outbound row, and advances the lane cursor. A crash between them is repaired locally without regenerating timestamps, choosing a different proof, or reinvoking the handler; an unrepairable lane cannot occupy the connector-wide publication head or block healthy lanes.

`reconcile_once()` isolates content before aggregation. Terminal-binding repair is enumerated and caught per exact `(target_connector_id,lane_id)`. Commit-ACK candidates are attributed by confined immutable filename to exact `(connector_id,producer_sequence)` and each is parsed, authenticated, and applied inside its own catch. Reverse marker candidates are likewise safely attributed and verified per lane before any grouping; a malformed ACK, marker, or terminal repair cannot prevent healthy target lanes from running. Typed content failures persist the corresponding degraded key, while transport/session/framing failures propagate for reconnect and unexpected programming/system exceptions remain visible. After those boundaries the routine spends one finite connector-scoped publication budget across a pre-target pass and a post-target pass, allowing newly durable `edge_publish`, `mac_detect`, `host_control`, and `model_ack` work to reach the local fixpoint in the same call when budget permits. It recomputes pending/unacked counts from connector-scoped SQL after the post-pass. It schedules one immediate local rerun only when eligible action work remains because that budget was exhausted or a clean historical-audit cycle has another bounded page; mount/transport blocks, unrepairable terminal state, and an already recorded degraded head do not busy-spin. Startup, reconnect, remount, app start, wake, reboot, and kqueue overflow enter this same routine.

The APFS hop sink signs each receipt before its atomic spool transaction, wraps it in the enrollment-run-scoped `patchbay.self_test.RUN.hop_receipt` channel, and persists `PENDING -> PUBLISHED -> CORE_ACKED`. The HOP payload is a closed tagged union: `HOP_CLAIM` contains one signed hop claim, while `HANDLER_DURABLE` contains the signed `model_ack` claim and a target-signed `HandlerDurableBinding`. That terminal binding is created only by the internal APFS continuation that already owns the verified staged row and durable handler receipt; no peer-frame signing API is exposed. A terminal hop row cannot publish until the binding is durably attached. Source rows use the same lifecycle. Every commit ACK contains closed connector id, producer sequence, channel, idempotency key, event/core sequence, submitted payload hash, full immutable envelope hash, run/nonce/trace, source fence, `spool_kind` (`SOURCE_EVENT` or `HOP_RECEIPT`), and exact local spool row id. The adapter verifies the core signature and demultiplexes on all of those fields, then stores the full canonical ACK bytes and their external SHA-256 in the exact source or hop row. A durable share marker alone never retires either row, and an ACK of the wrong kind, row, sequence, identity, or hash conflicts. Restart reconciliation republishes the identical pair and reapplies the identical ACK without duplication.

Reverse commit markers carry exact route/listener identity, both global `core_sequence` and lane-local `delivery_sequence`, and require listener equal lane. The Mac target cursor is keyed by authenticated `(connector_id, lane_id)` and advances only from `delivery_sequence = cursor + 1` after exact-task `HANDLER_DURABLE`; `core_sequence` is retained in the target row and receipt as causal evidence but is never required to be contiguous for that lane. Immediately before every first stage and every handler-control attempt, including recovery of an already `STAGED` row, Mac durably records and signs a random-nonce `CurrentDispatchChallenge` with a closed signed `purpose` (`STAGE` or `HANDLER_CONTROL`), route, listener, `local_boot_id`, and `started_monotonic_ns`. Windows consumes the immutable challenge, sends that same `purpose`, the exact signed challenge bytes/hash, and route/listener through the closed `PROVE_CURRENT_DISPATCH` schema, durably journals the byte-identical core response including `purpose`, and publishes an immutable proof blob/marker. The core verifies the challenge signature, exact signed `purpose`, and exact current token-specific attempt, deduplicates the challenge, and signs a proof binding `purpose` plus the full route/listener/run/nonce/event/trace, target, lane, delivery, logical hash, attempt revision, owner/token hash, core boot/fence, `issued_core_ns`, `lease_expires_core_ns`, `lease_remaining_ns_at_issue`, and bounded `valid_for_ns`. Mac accepts a proof only when the challenge is exact and unused, the proof and requested operation carry the same `purpose`, the local boot matches, local monotonic round-trip is within the configured maximum, the signed remaining lease exceeds round-trip plus safety margin, and the proof validity window has not elapsed. The accepted bytes/hash, `purpose`, route/listener, and timing facts are appended to `target_dispatch_bindings`; one challenge/proof is consumable only for its signed purpose. A crash after `STAGED` never reuses an old proof and a newer attempt revision adds a new binding without changing or repeating the logical handler effect. The separate source fence is never used as reverse authority. Missing/stale/delayed/purpose-relabelled proof defers only that lane with zero handler call; proof, marker, repair, and handler content exceptions are caught per authenticated `(target_connector_id,lane_id)` so healthy lanes continue.

SMB source timestamps and mtimes are diagnostic only. Core sequence is authoritative global order, delivery sequence is authoritative reverse-lane order, and the shared per-connector producer sequence detects outbound replay.

Exact replay semantics are closed: the same connector, producer sequence, idempotency key, and **full canonical signed-envelope hash** under a separately authenticated current `IngressAttempt` returns the original core commit ACK; any change to channel, source event id, run, nonce, trace, source-envelope fence field, spool kind, local row id, payload metadata, or signature-relevant bytes raises a conflict. A new sequence must equal the prior connector sequence plus one; both lower values and forward gaps are rejected before any write. Simultaneous submissions from independent SQLite connections serialize through one `BEGIN IMMEDIATE` transaction that validates the current attempt lease/fence. The `SOURCE_EVENT` branch atomically writes the event, replay row, signal outbox, routed edge outbox, authenticated `edge_detect`, initial core hop receipt, and canonical ACK. The evidence-only `HOP_RECEIPT` branch instead requires the already stored subject event by full run/nonce/event/trace identity, writes only the ingress-attempt audit, stamped hop evidence, optional exact terminal outbox transition, replay row, and ACK referencing that subject event/core sequence; it never inserts a duplicate event or creates signal/reverse outboxes. The source accepts either ACK by core signature plus exact immutable envelope identity, not by comparing its historical acceptance epoch to today's gateway epoch. Losing connections return the committed ACK only after full identity/hash comparison; a crash cannot expose a subset.

### 6.4 Connector authentication

Phase 0 uses per-connector HMAC-SHA256 keys stored outside the SMB share. The registry binds connector id to a key reference and authorized channels. The canonical signed source-envelope bytes include protocol version, connector id, producer sequence, channel, idempotency key, event id, run id, nonce, trace id, payload length, payload hash, source fencing epoch, closed spool kind, and local APFS row id. Edge commit ACKs and reverse publish receipts use the same authenticated-envelope rule.

Registry and evidence files contain only key ids, never key bytes. Phase-0 provisioning supplies one exact 32-byte master secret on every platform: the Mac login keychain represents it as exactly 64 lowercase hexadecimal characters, Windows stores exactly those 32 plaintext bytes inside a DPAPI-`CurrentUser` protected value, and ext4 stores exactly 32 raw bytes in a mode-`0600` file outside the share and PoC evidence root. Every loader rejects any other decoded length. The production Windows location is fixed at `HKCU\Software\OpenClaw\PatchbayPoC\Keys\<key_id>` and cannot be caller-overridden. Native tests may redirect only when an explicit test-contract switch is present and the base is exactly `HKCU\Software\OpenClaw\PatchbayPoC\Tests\<32-lowercase-hex-guid>`; arbitrary bases and the production `Keys` base under test mode are rejected. Direction- and purpose-specific subkeys are derived with the exact HMAC labels (`mac_to_core`, `core_to_mac`, `commit_ack`, `publish_receipt`, `hop_receipt`, `model_receipt`, `ingress_attempt`, `rpc_wsl_to_windows`, `rpc_windows_to_wsl`); the independently signed source-model completion evidence uses `model_receipt`, never the target hop key, no `hop_claim` alias exists, and one RPC direction can never authenticate the other. Python, Mac, and PowerShell implement byte-identical `HMAC-SHA256(master, b"patchbay-phase0\0" + ASCII(label))` and share all nine fixed master/vector fixtures. The ext4 loader opens the parent and key once with `O_NOFOLLOW`, verifies the opened parent's `/proc/self/fd` confinement, then validates regular-file type, owner, mode, and exact length with `fstat()` on that descriptor before reading; it never performs a check-then-reopen sequence. Mac uses `/usr/bin/security` with an argument vector and exact hex decoding. Windows keeps DPAPI, ACL, and value reads on one open HKCU key handle and compares owner/access identities as SIDs. Loaders reject symlinks/reparse points, unexpected owners, group/world access, unknown key ids, wrong lengths, or any path beneath the SMB root; logs expose only the key id and derived-key fingerprint. Native contract tests cover DPAPI round-trip and negative connector/entropy, ciphertext, key-id, ACL, test-base, key-length, purpose-label, cross-purpose model/hop substitution, and cross-direction RPC cases. Provisioning remains a separately authorized install step, and a missing platform identity is `BLOCKED`.

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

The bidirectional self-test proves each claimed capability with nonce-bound traces. Enrollment never consumes a caller-assembled capability receipt: the core derives each immutable `VerifiedCapabilityReceipt` by rereading the exact stored self-test event, validated durable handler ACK, authenticated connector hop, and descriptor-safely opened content-addressed capability evidence. All four objects must agree on connector, capability, run, nonce, event, trace, payload, model, effort, fence, and terminal status. Missing, ambiguous, cross-event, changed-hash, unbacked, or wrong-model evidence fails closed. A connector cannot start routed work before `ENROLLED`. A failed or missing capability is visible to Chief.

While `SELF_TESTING`, authorization consumes the complete event, not a channel string. A channel outside the reserved `patchbay.self_test.` namespace is rejected as `not_enrolled`; inside that namespace, the event's run id and nonce must exactly equal the connector's active enrollment run and nonce, and its channel must be both declared and beneath the exact `patchbay.self_test.<enrollment-run>.` prefix. Cross-run, cross-nonce, and prefix-alias events fail closed as identity mismatches, while production events remain blocked. Successful same-identity receipts advance capability proofs but grant no production authority.

The enrollment wave is triggered only by one machine-checkable `PATCHBAY_PHASE0_PASS` receipt covering both Phase 0A and 0B. Duplicate PASS events are idempotent. No prompt is broadcast before that receipt. This Phase-0 PASS authorizes only the isolated enrollment self-tests; it is not final operational acceptance or production cutover.

The aggregator recomputes every gate from same-run content-addressed evidence; it never accepts caller-asserted PASS strings or caller-claimed current time. Every approval/framework verification uses Task 8's private module-owned trusted clock, and no activation or aggregate production API accepts time, a clock, or an arbitrary callback. Run ids and nonces must match the closed identifier grammar `[A-Za-z0-9][A-Za-z0-9._-]{0,127}` at every boundary. Their canonical pair hashes to one run key, producing the immutable root `evidence/runs/<run-key-prefix>/<run-key>/`. Base and final manifests are separately content-addressed at `manifests/<kind>/<manifest-prefix>/<manifest-sha256>.json`; the sealed manifest lists every evidence object's hash and relative name. The activation result explicitly binds the exact base-manifest hash, approval-claim hash, all six admission hashes, all seven done-quality hashes, and the exact closed reviewer-id-to-receipt-hash mapping. Final aggregation receives that exact reviewer path mapping, reopens every receipt no-follow without scanning, compares it with the activation mapping, and lists each reviewer receipt as a named final-manifest object. There is no circular manifest-named run root, `current`, fixed base-manifest filename, symlink-following fallback, or overwrite path in acceptance input. If activation root validation fails, the verifier seals BLOCKED only beneath a fixed local blocked-receipt root; it never writes through the untrusted candidate root. Content-addressed run/base/operations primitives are implemented before the activation framework that consumes them, so no acceptance task depends on a later task.

PASS sealing and PASS notification are monotonic but separate durable phases. Once the exact `PATCHBAY_PHASE0_PASS` receipt exists, a crash propagates and an ordinary outbox failure reports `PENDING_RETRY` over that same receipt; neither path may mint a contradictory BLOCKED receipt. Retry must reuse the identical sealed receipt and converge to exactly one durable notification row.

The explicit-approval prerequisite is satisfied only by a separately created local operator-terminal receipt bound to the run id, nonce, exact connector/task binding, closed allowed host-action set, allowed fault set, immutable predeclared test-plan path/hash, and expiry. Task 8 implements the generalized recorder and verifier before either PC or Mac live adapters exist. The recorder publishes through the shared retained-directory, descriptor-relative, no-follow/no-replace primitive; the verifier opens one exact fixed-root/hash-prefix/hash-basename path descriptor-relatively and normalizes every parse/path/hash/signature failure to `ApprovalVerificationError`. It returns an internally sealed approval wrapper. The signed approval itself is stored by content hash outside the evidence output tree; the command line supplies the expected run id and nonce independently of that immutable path. Before any share, host, task-binding file, or fault-injection surface is opened, the live runner directly compares those expected values, verifies the test-plan hash, expiry against the module-owned trusted UTC clock, signature and user-presence, and rejects cross-run or stale approvals. No public live API accepts a clock or caller time. It repeats that verification before every new live gate, immediately before every host-control action, and immediately before every distinct fault through the single non-injectable capability API, whose verifier compares exact task-binding and test-plan hashes on every require. Operator/Fable/Opus notes, inbox content, Patchbay payloads, and WAKE records are rejected as authority sources. The seven done-quality results likewise name their evidence hashes and designated reviewer receipts; a missing, stale, cross-run, or mutable source blocks the aggregate trigger.

Every disruptive gate has a durable compensation journal created and flushed before the first live mutation. Runner startup and pre-surface entry first call `resume_pending_compensations(root=..., run_id=..., nonce=...)` and refuse all new live gates until each prior action is restored and sealed. The journal records pre-state, action, restoration command/API, completion hash, and operator-visible failure; it is replayable after process death. Expiry or any exception blocks new disruption but never blocks restoration already in progress.

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
8. **External outbound:** after the one inbound delivery yields an exact immutable completed assistant nonce ACK, the authenticated PC connector separately verifies an ACK-read capability immediately before reopening it and a fresh emit capability immediately before connector-journal mutation, emits that Codex-originated ACK as a new same-run envelope, and core commits it, routes the committed event to the internal listener, and requires the listener's durable ACK. The ordered trace is `pc_completed_assistant_ack -> pc_connector_emit -> ext4_commit -> internal_route -> internal_handler_ack`; a second adapter delivery cannot satisfy this gate.
9. **External inbound:** after a same-run signed terminal approval is reverified by the module-owned clock, retained binding/profile capabilities guard those exact descriptor reads, then internal emit causes the independently policy-checked `gpt-5.6-sol`/`ultra`, immutable read-only/network-disabled/tool-empty/no-external-connector Codex PoC task to wake without an additional operator message, produce one exact completed assistant nonce ACK, and echo only the nonce; adapter construction and every live host-control/read surface has its own task/plan-bound non-forgeable action-specific capability record.
10. **Mid-flight kill:** kill after commit/before actor ACK; restart replays with one logical effect and explicit replay trace.
11. **Trace completeness:** expected hops for this run equal terminal receipts; missing evidence fails.
12. **Gap/bark:** break one segment; exactly one targeted probe runs and the `GapBark` names the segment and owner under the exact run id, nonce, event id, trace id, and expected-hop-set hash.
13. **Chief order:** timestamps prove Switchboard snapshot and prediction precede ping-body access; diagnosis cites board, bark, and trace.
14. **Internal taste / anti-snowglobe:** copied Operator-note and WAKE-v2 fixtures traverse sandbox adapters, and a read-only live-lane shadow proves current filename, burst, and payload-shape compatibility while before/after fingerprints prove no live writes; a third fixture connector is manifest-only after conformance.
15. **Safety and enrollment trigger:** recursively hostile, nested, synonym, and natural-language payloads cannot cross the nonce/echo-only decoder or hard effect broker and grant no authority; `PATCHBAY_PHASE0_PASS` emits only when all checks and taste review are green.

Core fault injection also covers `SQLITE_BUSY`, exhausted retry, kill after event commit, kill before and after signal rename, `ENOSPC`, WAL checkpoint interruption, stale fence, wrong ACK hash, bounded probe timeout, and nonce causality.

PC disruptive faults use an exact non-callable `PreparedPCFault`. Recovery and fault-specific action-capability issuance/consumption guard preparation before fault-capability issuance; fault issuance is the last operation before inverse-journal fsync. After fsync, only the private closure-held MAC/identity/hash/expiry check—which does not invoke the ordinary live-environment hasher—may precede the prebound raw mutation. Post-mutation evidence is separately guarded while recovery excludes only that active scope, and restoration always runs. The outbound ACK path similarly has separate adjacent read and emit guards; signer-accepting sign/journal helpers are private, leaving `emit_completed_ack()` as the only public mutation surface. Its concrete FULL-synchronous connector journal returns one identical signed envelope for an identical idempotency key and rejects changed retry bytes before core ingest. Single missing core evidence reports `missing_gate:<id>`; SQLite/store/control-journal/connector-journal/watchdog failures seal `BLOCKED`.

Every disruptive Mac exercise captures its exact mount, clock, power/task, and queue baseline as applicable; restores it in `finally`; and emits a restoration receipt. An exception or missing restoration proof makes that gate `FAIL/BLOCKED` and prevents subsequent live faults from starting.

Mac live control binds an independently provisioned `MacCodexBinding`—including `host_app_kind`, exact authenticated connector id, descriptor-verified CLI hash, app-server version, process-start identity, exact task, model/effort, read-only/no-network profile, empty tools/connectors, and closed supported controls—against the distinct task-binding receipt named by the signed operator window. Neither value may be derived from the other. Each logical delivery first fsyncs one immutable full-identity control intent whose delivery-scoped `client_user_message_id` is derived from route/listener/target/lane/delivery/core/envelope/source-idempotency/task/control/binding identity, not copied from the source event idempotency key. Fresh attempt/fence/challenge/proof/boot/deadline authority is an append-only authorization record and never changes that logical id. Before any new detect/state/all-clear decision on retry, the adapter searches the full delivery selector for an unfinished effectful SPAWN/STEER intent and reconciles that historical outcome; absent or ambiguous outcome defers with zero new host control, so a prior spawn that made the host active cannot be reclassified as queue/steer. A crash hook immediately after the physical control returns but before accepted-effect fsync proves this window. Both `host_control` and `model_ack` are independently authenticated receipts whose signatures and complete run, nonce, event, trace, task, turn, accepted historical authorization, and effect timing identities are recomputed. A `model_ack` is accepted only when it also binds the exact host-control receipt hash, historical dispatch attempt/proof, completed nonce output, independently signed source-model receipt, and a terminal handler-durable binding with that same complete selector and one logical effect. A name-only hop pair, changed active turn, duplicate effect, stale/cross-identity receipt, or bad signature fails. Timeout, protocol, decode, journal, binding, ambiguity-bark persistence, factory, and evidence failures are closed undelivered results with no cursor advance, while the synthetic crash hook propagates for restart proof.

Every public Mac acceptance entry point recomputes and descriptor-opens the canonical run and compensation roots from the fixed configured root plus run/nonce before invoking any manager method; callers cannot inject a pre-bound path capability, compensation manager, verifier, issuer, key, pre-minted live capability, clock, harness factory, causal-selector loader, or arbitrary keyword seam. Production uses the module-owned trusted UTC clock and concrete implementations. A live pre-binding failure writes only to a fixed local blocked-receipt root, while non-live contract mode writes only beneath its explicitly supplied fixture root. Recovery of an already-journaled inverse precedes approval expiry and each genuinely fresh surface. For a new fault, an exact closed request is prepared through the ordinarily guarded surface before the seam; that preparation completes all discovery, binding, plan, baseline, and app-server reads. The full fault-authority check is then the final operation before durable inverse-journal fsync. After fsync, the only permitted pre-mutation operation is one module-owned, process-local capability-MAC/expiry verification using the trusted clock, immediately followed by the prebound raw mutation. No caller callback, recovery, path/plan/binding read, app-server discovery, alternate verifier, or other I/O may intervene. Post-mutation evidence collection is a new ordinarily guarded surface, and the active compensation scope remains excluded from recovery until restoration is proved. Exact I/O-spy tests enforce `guarded prepare -> fault capability -> journal fsync -> in-memory capability verify -> raw mutation -> guarded evidence collection -> restore`.

### 8.2 Ten real-Mac gates

1. **Mac -> PC durability:** real Mac nonce reaches ext4 with matching event id, core sequence, and hash; edge kill before ACK yields one committed event and one logical effect.
2. **PC -> idle Mac autonomous doorbell:** exact idle task resumes and produces nonce-bound ACK with zero operator message.
3. **Busy-turn semantics:** normal queues; synthetic authorized urgent steers the exact active turn without abort or duplication. An unsupported steer capability is an honest `BLOCKED/FAIL`, never a `PATCHBAY_PHASE0_PASS`.
4. **SMB disconnect/remount:** pending events in both directions reconcile without loss or model polling.
5. **Mac sleep/wake and reboot:** pending events survive; adapter rebinds current task or reports `UNBOUND`; stale ids receive nothing.
6. **Coalesced/reordered notification:** one hint drains every unseen event in core order; notification count is never event count.
7. **Atomicity/tamper:** truncated blob, early marker, wrong length/hash, duplicate key, and changed-payload reuse fail without cursor advance.
8. **Clock skew:** skew Mac wall time both ways; core order, leases, and gap deadlines remain correct.
9. **Identity/cross-lane attack:** forged connector/lane from a share-capable process fails authentication and authorization.
10. **Causal evidence chain:** a closed expected-hop list binds the nonce and run id to `mac_spool -> edge_publish -> edge_detect -> ext4_commit -> reverse_edge_outbox -> edge_reverse_publish -> mac_detect -> host_control -> model_ack -> opus_readback`. Every hop carries the current fencing epoch where applicable; absent or stale evidence fails the run.

### 8.3 Held post-enrollment acceptance barrage

The barrage harness is a Phase-0 build deliverable, but its execution gate is initially `HELD`. It may accept a run only after it verifies, by immutable manifest hash, both `PATCHBAY_PHASE0_PASS` and `PATCHBAY_ENROLLMENT_WAVE_PASS` for the same finalized supported-target manifest. A model message, WAKE, board note, or caller-asserted PASS cannot release it. The barrage remains isolated from production authority and requires the same signed terminal live-surface approvals described above.

Production exposes no direct `execute_case`, caller clock, freshness callback, sender, Watchdog, Chief, targeted-probe, compensation-manager, runtime factory, or post-PASS crash hook. `run_barrage(release_input, plan_only, live)` constructs one descriptor-bound, process-sealed concrete runtime after release verification; fakes exist only in an isolated test helper that cannot seal production evidence. The approval connector/task hash must equal the independently verified enrolled `Mac-Sol-Desktop` delivery binding, and the release retains both the unsigned approval claim and full signed-receipt digest.

The deterministic release audit hash binds every verified component's full digest and exact descriptor-validated path. A separate closure-held process MAC binds the exact immutable verified component objects, and a weak identity registry recognizes only the exact live issued release instance without retaining dead release graphs. Copying or replacing a release, nested barrage payload/case, target route, binding path, approval path, or wrapper while preserving an advertised hash therefore cannot enter private execution.

After the supported-target manifest is final, Opus authors the prepared question/message barrage and seals its canonical manifest. `Mac-Sol-Desktop` (Mac-Desktop Codex Sol) is the sole barrage delivery coordinator. It must deliver through its enrolled, authenticated connector—not by direct file write or UI paste—and cannot author, alter, or silently skip a case. The matrix contains every supported target, connector, lane, and channel, internal and external; every declared one-way route is exercised in its allowed direction, and every declared two-way route is exercised independently in both directions with the reasonable/logical interaction semantics named in the manifest.

Each interaction is a first-class `BarrageInteraction` keyed by run id, nonce, case id, direction, expected sender connector, expected receiver connector, lane, and channel. Every manifest case must use the approved release run and nonce. Its evidence binds actual authenticated sender and receiver, event/trace ids, producer/delivery/core sequences as applicable, payload hash, exact terminal delivery receipt, expected-hop-set hash, Watchdog result, Chief diagnosis reference, immutable evidence hash, the release hash, and the entire exact release-input hash mapping: Phase-0 pass, enrollment pass, supported targets, barrage manifest, taste rubric, delivery binding, operator approval, and test plan. The aggregator supplies that closed mapping when reopening every interaction, so even a coordinated valid rubric-and-taste swap cannot substitute a different release identity. A receipt from the wrong sender, receiver, direction, lane, channel, run, nonce, or release identity is a failure, not partial credit.

The harness records four independent scores for every interaction:

- **DEBUG:** correct bytes, sender, receiver, receipt, and logical effect work;
- **HARDEN:** replay, gap, reconnect, adversarial, and applicable fault behavior remain safe and durable;
- **POLISH:** interaction and diagnostic flow are clean, bounded, legible, and efficient;
- **TASTE:** the result is coherent, elegant, appropriate to the declared route, and explicitly accepted by a separately sealed operator-terminal taste receipt bound to the exact interaction-evidence hash and rubric version; the harness cannot self-score this lane.

Scores are structured rubric results with evidence references, not free-form self-grades. Every finding creates a durable `BarrageWorkOrder` with owner, affected case/route, severity, acceptance test, plan, and status. At each state transition it snapshots the four-lane `before_shape` and `after_shape`, computes a signed field-by-field diff, identifies movement toward taste, and flags any movement away from a prior taste-pass as `REGRESSION_REASSESSMENT_REQUIRED`. A regression or unresolved below-pass lane blocks final acceptance; post-pass improvement gaps remain visible as owned work orders with a concrete plan.

Path Watchdog and Chief remain live for the full barrage. Watchdog evaluates every expected hop under the exact run and nonce, while Chief records the sealed `board -> predict -> ping -> bark -> diagnose` order for induced and organic gaps. Their receipts and diagnoses are required interaction evidence, not side logs. Release verification uses Task 8's private trusted clock through `verify_operator_approval()`, never a time parameter or input claim, and requires the complete closed action set—runtime construction, open, fault preparation, delivery, and targeted probe—plus every declared HARDEN fault before it can return `RELEASED`. It verifies the signed plan and approval/delivery identity before any capability issue. Each actual construction, open, preparation, probe, and delivery reopens and verifies those immutable inputs, issues one action capability last, and the concrete runtime consumes that exact connector/task/plan-bound capability immediately before the one surface. HARDEN preparation completes discovery and baseline capture under its own action capability; the fault capability is issued last before durable inverse-journal fsync, verified in memory immediately after fsync, and followed directly by the prebound raw mutation. Post-mutation collection obtains and consumes a fresh probe capability while the active inverse remains protected, then restoration is guaranteed. No caller noop or fake release can enter that private path.

Before the pre-approval recovery-only phase calls any manager method, it descriptor-safely verifies the compensation root and constructs the concrete module-owned manager with the exact root/run/nonce binding; mismatch causes zero recovery actions. The confined recovery-only wrapper then runs before approval expiry is evaluated, so expiry blocks new faults but cannot strand an already-journaled inverse. Release verification first recomputes and descriptor-safely opens the exact content-addressed run root from run/nonce; mutable aliases, symlinks, and wrong-run roots are held with zero writes. Plan-only and other HELD results are sealed only beneath a fixed local held-result root, never through the caller's candidate evidence root. The signed immutable plan exactly matches the approval's action/fault sets and binds the target, barrage, taste-rubric, and exact delivery-binding hashes. `BarrageRelease` retains the verified Phase-0 and enrollment receipts plus every exact release-input hash. The final aggregator accepts exact immutable paths rather than a caller-assembled bundle, reruns Phase-0/enrollment/approval/test-plan/delivery-binding release verification, catches every closed verification/evidence/runtime error before PASS sealing into a sealed `BLOCKED` receipt, and independently recomputes matrix coverage, correct sender-to-receiver delivery, both-direction coverage, four-lane taste-pass, work-order closure/plan state, regression status, operator taste receipts, and Watchdog/Chief evidence from the verified content-addressed run root.

Only a green recomputation emits `PATCHBAY_FINAL_ACCEPTANCE_PASS`. Before doing so it publishes a no-replace content-addressed final manifest binding the complete release hash set and the matrix-ordered `(case key, interaction hash, confined path)` sequence. The receipt, event id, and durable unique outbox row bind that manifest's exact hash and bytes. Repeat aggregation returns the identical receipt. After PASS sealing, a crash propagates and an ordinary outbox error reports `PENDING_RETRY` over that exact receipt; retry repairs exactly one row and never creates a conflicting BLOCKED receipt. Missing coverage, a wrong endpoint, absent confirmation, a non-taste-pass score, unassessed regression, stale diagnostic, or mutable evidence emits `FAIL/BLOCKED` only before PASS sealing. Even this final PASS does not authorize production cutover, business sends, money movement, deletes, or gate activation; those remain separate terminal-authorized work.

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

Neither `PATCHBAY_PHASE0_PASS`, enrollment-wave PASS, nor `PATCHBAY_FINAL_ACCEPTANCE_PASS` authorizes live cutover. Phase 1 begins with a wiring audit and dual-run migration plan, separately conferred.

Admission and done-quality verification is implemented in `patchbay_activation_frameworks.py`, separate from `patchbay_worker_all_clear.py` resource/backpressure decisions. The verifier takes explicit run id and nonce, opens only the supplied immutable manifest by expected content hash, validates every referenced object's hash/freshness/trusted source type, and computes each result. Its sealed result binds the exact operator-approval claim hash and all six admission plus seven done-quality evidence hashes. The Phase-0 final manifest includes both that sealed activation-result hash and the exact outside-root approval hash before deriving its PASS event id; neither may be reduced to a transient boolean. Missing, malformed, stale, cross-run, or unbound evidence returns a sealed `BLOCKED` result rather than escaping into an ambiguous partial run. No API accepts a caller-provided PASS value.

## 10. Observability and honest states

The Phase-0 evidence bundle contains:

- core schema and migration version;
- event/outbox/cursor/lease counts;
- routing/cable read model;
- per-dimension Switchboard state;
- every acceptance run id, nonce, event id, trace id, producer/delivery/core sequence, hash, owner, and immutable evidence path;
- fault-injection outcomes;
- before/after live-surface fingerprints;
- barrage target coverage, four-lane scores, work orders, before/after shapes, diffs, and regression flags;
- Watchdog and Chief ordered diagnostic evidence for each barrage interaction;
- operator-facing PASS/FAIL summary.

No aggregate green can hide a failed dimension. `DETECTOR_ONLY`, `UNBOUND`, `UNKNOWN`, `BACKPRESSURED`, `DEGRADED`, and `DOWN` are first-class terminal readback states.

## 11. Rollback and failure containment

Phase 0 is additive and isolated. Rollback stops only Patchbay PoC services, preserves the SQLite log, spools, cursors, receipts, immutable evidence, and compensation journals, and removes no live lane. Startup resumes incomplete compensation before opening any new live surface. A failed PoC produces a FAIL receipt and leaves enrollment or final acceptance blocked.

The currently disabled and stopped PC-Sol wake-v2b path is a separate operational safety action. It is not rearmed until both initial resume and a supervised respawn prove `gpt-5.6-sol` at `ultra` and the operator accepts the repair.

## 12. Prior art reuse

- Envelope vocabulary: `openclaw_event_bridge_contract.py`
- WAL/idempotency pattern: `ar_gig_to_cash_store.py`, amended with busy timeout and bounded retry
- Atomic publication: `fleet_coordination_contracts.py` and `materialization_publisher.py`, amended with a transactional outbox
- App-server host control: `codex_app_server_control.py`
- Registry/host lifecycle: `tool_protocol_adapter_registry_contract.py`, `operator_workbench_actor_host_registry.py`, `config/fleet_coordination.v2.json`
- Health and gap evidence: `agent_presence.py`, `no_response_watchdog.py`

The existing fleet watcher signature cursor, startup priming behavior, and failed-delivery advancement are explicitly not reused as durability semantics.
