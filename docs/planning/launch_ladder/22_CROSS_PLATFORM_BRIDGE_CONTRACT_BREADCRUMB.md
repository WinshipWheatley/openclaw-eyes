# Cross-Platform Bridge Contract Breadcrumb

Status: docs-only planning breadcrumb. This file records the follow-up contract direction after the deployment topology, node portability, and OS-agnosticism synthesis. It does not implement bridge code, edit sync scripts, change services, inspect secrets or private data, move/delete files, clean storage, create schemas, expose endpoints, or authorize deployment.

Generated/reviewed: 2026-05-05

Source basis:

- `20_DEPLOYMENT_TOPOLOGY_NODE_PORTABILITY_AND_OS_AGNOSTICISM.md`.
- Completed PC and Mac deployment readiness audit summaries.
- Existing PC-to-Mac communication and mirroring posture as working scaffolding, not final architecture.

Freshness:

- Stale when a cross-platform bridge contract is drafted, a replacement adapter is tested, deployment profiles are formalized, node capability manifests are adopted, or PC/Mac bridge mechanics materially change.
- Refresh before replacing current PC-to-Mac scripts, broadening bridge targets, granting bridge authority, or using bridge packets as implementation requirements.

## 1. Purpose

Create a planning breadcrumb for the future cross-platform bridge contract.

The current PC-to-Mac bridge is useful working scaffolding. It should remain usable for current communication and mirroring while the portable bridge contract is designed. It is not the final architecture.

The target direction is stable contracts plus native adapters. Future Operator Harness surfaces should target bridge contracts, not machine-specific scripts.

## 2. Current Bridge Posture

The current PC-to-Mac bridge helps OpenClaw communicate, mirror planning packets, and keep Mac-side review or operator surfaces informed.

That posture is valuable because it works now, supports the current PC-canonical plus Mac-review/build topology, and gives the system a practical bridge while the architecture matures.

It remains scaffolding because it leans on machine-specific scripts, path assumptions, sync habits, and local environment knowledge. Those details can continue to serve current operations, but they should not become the stable product contract.

Do not rip out the current bridge until the agnostic contract exists and a replacement adapter is tested.

## 3. North Star

The bridge contract should be portable. The bridge implementation can be machine-specific.

OpenClaw should treat the bridge as a stable workflow and packet contract that can survive different nodes, operating systems, app surfaces, and hardware classes. The adapter that fulfills the contract may be optimized for WSL, macOS, Linux, Windows, mobile, spatial, client-office, or remote worker constraints.

This strengthens the architecture if agnostic means stable contracts plus native adapters. It weakens the architecture only if agnostic is misread as lowest-common-denominator behavior.

## 4. Stable Bridge Contract

A future bridge contract should define what a bridge packet means independently from the script, service manager, OS, path layout, or app shell that transports it.

Every bridge packet should eventually carry:

- source;
- destination;
- data class;
- authority basis;
- freshness;
- terminal state;
- audit receipt.

The contract should also define allowed packet classes, denied packet classes, retry semantics, stale states, blocked states, receipt formats, validation expectations, and what counts as delivery versus acceptance.

A bridge can transport packets, but it cannot grant authority.

## 5. Native Adapter Principle

Implementation adapters may be native and optimized per hardware and OS.

Examples:

- a WSL adapter can understand the canonical PC workspace and WSL path roots;
- a macOS adapter can use native filesystem, launchd observation, app-build, and operator workstation affordances where authorized;
- a Linux adapter can use its service manager and server/runtime conventions;
- a Windows-native adapter can use Windows path, process, and notification surfaces without pretending to be WSL;
- mobile and spatial adapters can present companion views only within declared capability and authority limits.

Native optimization is acceptable when the portable contract remains stable and the adapter declares its capabilities.

## 6. Deployment Targets

The future bridge contract should be able to describe or reject these targets without changing its core meaning:

- PC WSL primary node;
- Mac operator/UI/app-build node;
- Linux primary/server node;
- Windows-native node;
- iOS/iPadOS companion;
- Android companion;
- Vision/spatial client;
- future hardware classes;
- client-office scoped node;
- remote worker node.

Each target needs explicit capability, authority, data-boundary, freshness, health, rollback, and revocation treatment before it can do more than receive or display bounded packets.

## 7. Authority And Data Boundaries

Network topology never defines trust.

Bridge doctrine:

- connected does not mean authorized;
- mirrored does not mean canonical;
- synced does not mean fresh;
- UI-visible does not mean actionable;
- transport does not imply approval;
- receipt does not imply success;
- remote reachability does not collapse authority domains.

Authority must come from explicit node profiles, allowed data classes, allowed task classes, approval basis, and audit trail. A bridge packet may carry that authority basis as evidence; it does not create it.

## 8. Freshness Receipts And Audit Trail

The bridge contract should distinguish transport, freshness, and auditability.

Future receipts should answer:

- what packet was sent;
- where it came from;
- where it went;
- which data class it carried;
- which authority basis applied;
- when it was created;
- when it was observed or accepted;
- whether it is fresh, stale, blocked, partial, failed, superseded, or unknown;
- where the audit record lives.

Synced after a failed push is not fresh. Mirrored after a local-only boundary violation is not authorized. UI display without a receipt is only a claim.

## 9. Failure And Rollback States

The bridge contract should include terminal and recoverable states before implementation expands.

Planning states to define later:

- unavailable;
- stale;
- blocked by authority;
- blocked by data class;
- blocked by missing destination capability;
- partial delivery;
- delivered but not accepted;
- accepted but not actionable;
- superseded;
- rolled back;
- revoked;
- unknown.

Rollback should restore a bounded prior bridge posture without deleting evidence, hiding failures, or mutating unrelated runtime state.

## 10. What Should Stay Custom

The following can remain native or machine-specific behind the contract:

- filesystem path translation;
- service-manager observation;
- local notification behavior;
- launchd, shell, WSL, Windows, Linux, or mobile adapter mechanics;
- native app or window integration;
- performance tuning for CPU, RAM, GPU/VRAM, storage, and network constraints;
- local validation harnesses;
- operator workstation ergonomics.

Custom adapters are healthy when they are explicit, testable, replaceable, and bounded by the stable contract.

## 11. What Should Become Agnostic

The following should become portable bridge-contract concepts:

- packet identity;
- source and destination semantics;
- data class;
- authority basis;
- freshness status;
- audit receipt;
- terminal state;
- retry and supersession rules;
- health and availability reporting;
- allowed and denied task classes;
- local-only and sensitive-boundary handling;
- rollback and revocation behavior.

These concepts should not depend on `/home/openclaw`, `/Users/hwinshipwheatley`, mounted Windows paths, Mac mirror folders, VS Code windows, or a specific shell script name.

## 12. Future Implementation Breadcrumb

Recommended future sequence:

1. Draft `CROSS_PLATFORM_BRIDGE_CONTRACT.md` as a docs-only contract.
2. Define bridge packet fields, terminal states, freshness receipts, audit receipts, and denied behaviors.
3. Map current PC-to-Mac scripts as one existing adapter candidate without treating them as the contract.
4. Define validation fixtures for fresh, stale, blocked, partial, superseded, and unauthorized packets.
5. Test a replacement adapter against the contract before retiring current scaffolding.
6. Only then plan implementation changes to bridge scripts or native shells.

Until that sequence exists, keep current bridge scaffolding usable for communication and mirroring, and keep future Operator Harness planning pointed at the bridge contract.

## 13. What This Does Not Authorize

This breadcrumb does not authorize:

- runtime bridge implementation;
- editing bridge scripts or sync scripts;
- starting, stopping, or changing services;
- installing software;
- inspecting secrets, private data, logs, vaults, cloud drives, Gmail, Telegram, LegalPrivate, or credential paths;
- moving, deleting, cleaning, migrating, or syncing storage;
- exposing network endpoints;
- granting authority to any connected node;
- treating mirrored files as canonical;
- treating synced packets as fresh without receipts;
- treating UI-visible state as actionable;
- committing changes.

It is only a planning marker: preserve the current bridge as working scaffolding, design the portable bridge contract next, and let native adapters satisfy that contract when tested and authorized.