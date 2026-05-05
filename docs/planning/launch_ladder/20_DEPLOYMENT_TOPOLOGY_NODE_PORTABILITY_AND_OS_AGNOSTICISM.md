# Deployment Topology, Node Portability, And OS-Agnosticism

Status: docs-only synthesis artifact. This file records planning implications from the completed PC and Mac deployment readiness audits. It does not implement runtime code, edit services, install software, inspect secrets or private data, move/delete files, clean storage, create schemas, expose network endpoints, start/stop processes, or authorize deployment.

Generated/reviewed: 2026-05-05

Source basis:

- Completed PC deployment readiness audit summary for PC WSL Ubuntu-E at `/home/openclaw`.
- Completed Mac deployment readiness audit summary for the Mac operator/build/review environment.
- `19_OPERATOR_WORLD_MODEL_BUILD_READINESS_ADDENDUM.md` as the current Operator World Model authority-scope addendum.
- Existing OpenClaw runtime law and core architecture principles.

Freshness:

- Stale when either deployment readiness audit is superseded, active canonical workspace changes, hardware/OS/runtime versions materially change, node roles change, deployment profiles are formalized, or any follow-up spec listed here is created and adopted.
- Refresh before implementing deployment profiles, node manifests, cross-platform orchestration, secrets interfaces, hardware-fit analysis, world-model data contracts, or multi-node worker activation.

## 1. Purpose

Synthesize the completed PC and Mac readiness audits into a planning-only deployment topology artifact.

The goal is to preserve three principles before implementation begins:

- OpenClaw must degrade to one trusted computer and scale out to many bounded workers.
- Hardware location is configuration, not authority.
- OS choice is deployment surface, not system identity.

This document names the current topology, the portability gaps, and the abstractions required before OpenClaw can move modules safely across PC, Mac, future mobile/native surfaces, remote nodes, friend nodes, company nodes, or other bounded workers.

## 2. Audits Synthesized

PC audit verdict: partially ready.

- User: `openclaw`.
- Hostname: `DESKTOP-HP`.
- OS: WSL2 Ubuntu-E, Linux `6.6.87.2-microsoft-standard-WSL2`.
- Runtime: Python `3.12.3`, Node `v24.14.0`.
- Workspace: `/home/openclaw`.
- Hardware: Intel i7-6700, about 27 GiB visible RAM, GTX 1660 Ti with 6 GB VRAM.
- Active WSL VHDX: `E:\WSL_Distros\Ubuntu-E\ext4.vhdx`.
- Rollback backup tar: `E:\WSL_Backup\Ubuntu-before-move.tar`.
- Architectural strength: strong modular Python brain structure.
- Current risk shape: orchestration leans on bash/shell scripts, local paths, mounted Windows paths, Mac sync scripts, local secret paths, and scripted file sync rather than formal node/API contracts.

Mac audit verdict: partially ready for portable deployment planning.

- OS: macOS `26.4.1`, Darwin `25.4.0`.
- Hardware: Apple M1 Pro ARM64, 16 GB RAM.
- Runtime/build stack: Python `3.12.0`, Node `v25.8.1`, npm `11.11.0`, Git `2.50.1`, Xcode `26.4.1`, Swift `6.3.1`.
- Storage: about 107 GiB available.
- Important surfaces: `~/OpenClaw_Watch`, `~/OpenClaw_Watch/operator_harness_readiness`, `~/OpenClaw_Watch/consolidation_packets`, `~/OpenClawLegalDev/legal-console-spike`, `~/Eyes`, `~/Documents/Sovereign_Bridge/mac_eyes`, `~/.openclaw`, `~/.config/openclaw`, `~/bin` helpers, and LaunchAgents.
- `~/Eyes` status: treat active use as inferred, not confirmed. Prior packets classify it as targeted-review-needed / human-review before active, stale, or archive classification.
- Architectural strength: strong native app build readiness, operator workstation fit, review/mirror-node fit, and possible single-node target fit.
- Current risk shape: `/Users/hwinshipwheatley` hardcoding, launchd/LaunchAgents assumptions, shell scripts, VS Code/mirror assumptions, and Mac-specific window/UI helpers.

## 3. Core Doctrine

OpenClaw must preserve the same workflow contract whether it is running on one trusted computer or many bounded nodes.

Core rules:

- OpenClaw must degrade to one trusted computer and scale out to many bounded workers.
- Hardware location is configuration, not authority.
- OS choice is deployment surface, not system identity.
- The workflow contract stays stable; the native shell adapts to hardware and OS.
- OS-agnostic does not mean lowest-common-denominator web app.
- Native features should be used when Mac, Windows, Linux, iOS, iPadOS, Android, or Vision surfaces are the best fit.
- Native features must be declared as node capabilities, not silently assumed by the portable core.
- A module can relocate between machines only if its authority contract, inputs, outputs, logs, health checks, and rollback behavior remain stable.
- Network topology must never define trust.
- Remote, friend, and company nodes are separate authority domains, not extra compute by default.

## 4. Final Current Topology

Current canonical topology:

- PC WSL Ubuntu-E at `/home/openclaw` is the canonical OpenClaw workspace.
- The PC currently has the stronger always-local backend/runtime posture and the larger general RAM/GPU envelope.
- The Mac is best treated as a native UI/app build node, operator workstation, review/mirror node, and possible future single-node target.
- Mac watch and mirror surfaces are source-reference or reflection surfaces unless a future deployment profile explicitly changes their authority.
- Current multi-machine movement leans on scripts and file sync, not a formal node protocol.
- Current working tree may contain uncommitted planning work; that local planning state is not a deployment authority.

The topology is therefore PC-canonical plus Mac-native-build/review. It is not yet a general distributed system.

## 5. Single-Node First Requirement

Every deployment plan must first prove that OpenClaw can run coherently on one trusted computer.

Single-node first means:

- one node can hold the canonical workspace, local state, audit logs, operator-visible status, and rollback story;
- disabled or unavailable secondary nodes degrade into stale, unavailable, or review-only states;
- the workflow contract remains understandable without network assumptions;
- local-only and sensitive boundaries remain enforceable without remote helpers;
- any native UI shell can explain what is local, what is mirrored, what is unavailable, and what is not authorized.

The PC is the current canonical single-node baseline. The Mac may become a single-node target only after deployment profile, path, secrets, orchestration, and storage assumptions are made explicit.

## 6. Multi-Node Scale-Out Model

Scale-out should add bounded workers, not blur authority.

Multi-node scale-out requires:

- an explicit node identity and owner;
- a declared authority domain;
- allowed data classes and denied data classes;
- allowed task types and denied task types;
- stable inputs, outputs, logs, health checks, and rollback behavior;
- service availability flags rather than silent assumptions;
- cross-platform orchestration contracts rather than machine-specific shell habits;
- audit trails that survive relocation;
- revocation methods for every node.

Network reachability is only transport. It is not trust, approval, permission, freshness, or authority. A friend node, remote node, company node, client node, or cloud worker is a separate authority domain unless a manifest and approval contract say otherwise.

## 7. OS/App-Surface Agnosticism

OS-agnosticism means the OpenClaw workflow contract can survive different operating systems and app surfaces.

It does not mean every surface must collapse into a generic web UI. Native app surfaces are allowed and often preferred when they provide better trust, ergonomics, privacy, performance, local integration, or operator focus.

Planning implications:

- Mac can carry native app build and workstation surfaces.
- Windows/WSL can carry canonical local runtime and storage-heavy work.
- Linux can carry portable backend/runtime modules.
- iOS, iPadOS, Android, and Vision surfaces can become native shells later when their capabilities and boundaries are declared.
- Any OS-specific feature must appear as a capability in the node manifest, not as an assumption in portable logic.

The system identity is OpenClaw. The OS is a deployment surface.

## 8. Native Shell vs Portable Core

The portable core should define workflow state, authority scopes, evidence/freshness rules, task boundaries, health expectations, and audit obligations.

The native shell should adapt those contracts to the hardware and OS:

- Mac native shell: app UI, menu/window behavior, local notifications only when authorized, Swift/Xcode build surfaces, operator workstation ergonomics.
- Windows/WSL shell: canonical workspace, Python runtime, GPU-aware local workloads, Windows path bridging only through explicit path abstraction.
- Linux shell: service/process execution where available, package/runtime capability declaration, filesystem and service manager differences.
- Mobile or spatial shell: limited review, status, approval-adjacent display, or native interaction only after capability and authority contracts exist.

The portable core must not silently depend on LaunchAgents, VS Code windows, `/home/openclaw`, `/Users/hwinshipwheatley`, `/mnt` paths, local helper scripts, or mounted drives.

## 9. Deployment Profiles

Deployment profiles should describe how OpenClaw is expected to run on a node or set of nodes.

Future profiles to plan:

- single trusted PC canonical workspace;
- single trusted Mac native workstation;
- PC canonical plus Mac review/build node;
- PC canonical plus bounded worker node;
- client/company node with separate authority domain;
- remote/friend node with restricted data and task classes;
- local-only sensitive profile;
- offline/reduced capability profile.

A deployment profile should describe intended role, authority, required capabilities, denied capabilities, path roots, storage rules, service manager, secrets interface, native surfaces, logs, health checks, rollback, and revocation. This document does not create the schema.

## 10. Node Capability Manifest

Every node should eventually have a node manifest.

Required manifest concepts:

- identity;
- owner;
- location;
- hardware;
- OS;
- allowed data classes;
- allowed task types;
- denied task types;
- model/tool versions;
- health;
- audit log path;
- revocation method.

Additional concepts to evaluate: CPU, RAM, GPU/VRAM, storage, service manager, native app surface, local-only constraints, expected workload class, current service availability, network availability, path roots, secrets availability, rollback method, and last validation result.

The manifest should be evidence for planning. It should not grant permission by existing.

## 11. Service Orchestration Abstraction

Current orchestration leans on bash/shell scripts, Mac launchd/LaunchAgents, VS Code/mirror assumptions, and local helper scripts.

The future orchestration abstraction should define:

- service identity;
- supported service manager per node;
- start/stop/status/check semantics;
- health checks;
- logs;
- dependency order;
- failure states;
- rollback behavior;
- operator approval requirements;
- read-only observation versus mutation authority.

This should begin as documentation and validation expectations. It should not become a new control plane before existing stack-native mechanisms are audited.

## 12. Path And Storage Abstraction

The audits found hardcoded setup risks around `/home/openclaw`, `/mnt` Windows drive mounts, `E:\WSL_Distros\Ubuntu-E\ext4.vhdx`, `E:\WSL_Backup\Ubuntu-before-move.tar`, Mac watch paths, `/Users/hwinshipwheatley`, local secret paths, `~/.openclaw`, `~/.config/openclaw`, `~/bin`, and mirror/sync directories.

Future planning should separate:

- canonical workspace root;
- runtime data root;
- generated output root;
- mirror/watch root;
- secrets root;
- audit log root;
- temporary/staging root;
- rollback/backup root;
- native app build root;
- user-review packet root.

Storage location should be configuration with evidence. It should not become authority. A path being reachable does not authorize scanning, sync, cleanup, migration, deletion, ingestion, or disclosure.

## 13. Secrets And Sensitive Boundaries

Secrets and sensitive data must stay behind explicit interfaces and authority contracts.

Required planning posture:

- never inspect credential files as part of portability discovery;
- never infer permission from the presence of `~/.openclaw`, `~/.config/openclaw`, local secret paths, helper folders, or mounted drives;
- declare whether a node can hold secrets, request secrets, or only operate without secrets;
- declare local-only data classes;
- declare denied data classes;
- keep audit logs separate from raw private content;
- make revocation and rollback explicit before activating a node.

Secret availability is a node capability and an authority boundary. It is not an installation convenience.

## 14. Operator World Model Implications

The Operator World Model addendum implies that modes and places are authority scopes.

Planning mapping:

- Bridge / Captain's View: read-only display of the current operator world, context, route, freshness, and next safe move hint.
- Helm: decision-instrument surface; approval-adjacent, but not execution by itself.
- Chart Room: evidence/freshness and source-registry surface.
- Engine Room: runtime/system observation surface; not service-control authority by display alone.
- Cargo Hold: storage, staging, protected-source, and local-only boundary surface.
- Radio Room: communications status and draft-routing surface; not auto-send authority.
- Treasury / Purser's Office: finance/receivables/obligations surface; not bank access, payment, posting, or final financial truth.
- Studio Bay: creative production, asset, delivery, and client-project surface.
- Ports: context/domain/project selection surface.
- Offices / Client Sites: external authority domains requiring explicit profile and data-boundary rules.

UI surfaces are not authority. Bridge can display; Helm and an approved backend/action contract own consequence. Navigation is not approval. Approval is not execution. Execution is not success.

## 15. Hardware Fit Analyzer / Deployment Advisor

Future planning should include a Hardware Fit Analyzer / Deployment Advisor that evaluates whether a target computer or node can run a project, module, or workload before install or activation.

Verdict ladder:

1. Not able to run this workload.
2. Not able to run this workload unless we modify X.
3. Likely too large, but installation/test run is reasonable; proceed with bounded install and prepared validation tests.
4. Able to run, but would be smoother if we modify X.
5. Able to run normally; proceed with use.
6. Running no problem; all required tests passed; proceed with confidence.

The analyzer should consider:

- CPU;
- RAM;
- GPU/VRAM;
- storage;
- OS version;
- service manager;
- native app surface;
- model/runtime requirements;
- local-only constraints;
- expected workload;
- validation-test needs.

The analyzer should produce planning evidence, not permission. Hardware detection must not authorize installation, service startup, network exposure, secrets access, private-data inspection, data movement, runtime mutation, cleanup, or deployment.

## 16. Risks Found In The PC Audit

PC risks:

- hardcoded `/home/openclaw` assumptions;
- hardcoded `/mnt` Windows-drive mount assumptions;
- active WSL VHDX and rollback backup paths that must be treated as protected runtime/storage references;
- shell-script orchestration without a portable service contract;
- Mac sync scripts embedded in local habits;
- local secret paths that may be assumed instead of declared;
- file-sync-oriented multi-node communication without formal contracts;
- service availability inferred from local scripts rather than explicit health/capability flags;
- GPU and runtime fit not yet connected to workload-specific validation;
- working-tree planning state that can be mistaken for deployment readiness.

Needed abstractions from the PC side: node capability manifest, cross-platform orchestration, world-model data contract, path abstraction, service availability flags, and hardware-fit analysis.

## 17. Risks Found In The Mac Audit

Mac risks:

- `/Users/hwinshipwheatley` path hardcoding;
- launchd/LaunchAgents assumptions;
- shell-script assumptions;
- VS Code/mirror assumptions;
- Mac-specific window/UI helpers;
- unconfirmed `~/Eyes` active/stale/archive status;
- strong native-app readiness that could be mistaken for runtime authority;
- watch/mirror surfaces that could be mistaken for canonical data stores;
- helper folders and config paths that could be mistaken for secrets permission;
- local review packets that could be mistaken for source freshness.

Needed abstractions from the Mac side: deployment profile schema, portability contract, secrets interface, native surface capability declaration, service orchestration abstraction, and node manifest.

## 18. Recommended Follow-Up Specs

List these specs for later creation. Do not create them in this slice.

- `OPERATOR_NODE_CAPABILITY_MANIFEST.md`
- `CROSS_PLATFORM_ORCHESTRATION_SPEC.md`
- `DEPLOYMENT_PROFILE_SCHEMA.md`
- `SECRETS_INTERFACE.md`
- `HARDWARE_FIT_ANALYZER_SPEC.md`
- `WORLD_MODEL_DATA_CONTRACT.md`

Recommended order:

1. `OPERATOR_NODE_CAPABILITY_MANIFEST.md`
2. `DEPLOYMENT_PROFILE_SCHEMA.md`
3. `CROSS_PLATFORM_ORCHESTRATION_SPEC.md`
4. `SECRETS_INTERFACE.md`
5. `HARDWARE_FIT_ANALYZER_SPEC.md`
6. `WORLD_MODEL_DATA_CONTRACT.md`

The first two specs should come before any module relocation or multi-node activation planning. The orchestration and secrets specs should come before service mutation. The Hardware Fit Analyzer should come before install/activation decisions on unfamiliar nodes. The world-model data contract should come before backend/schema work that binds places to authority scopes.

## 19. What This Does Not Authorize

This document does not authorize:

- runtime code edits;
- app implementation;
- backend/API/schema/SQLite work;
- service start, stop, restart, install, removal, or mutation;
- software installation;
- secrets inspection or secret movement;
- private-data inspection;
- storage cleanup;
- file movement, deletion, migration, or sync;
- provider/model calls;
- network exposure;
- remote-node activation;
- friend/company/client-node use;
- LaunchAgents or service-manager changes;
- Mac import;
- Windows/WSL relocation;
- use of `~/Eyes` as confirmed active data;
- treating UI display as authority;
- treating hardware detection as permission to install or activate a workload.

Any future operational step needs a separate bounded packet, current evidence, explicit authority, validation tests, rollback behavior, and audit logging.