# Cross-Platform Architecture

## Purpose

This document recommends a staged cross-platform architecture for PC/WSL, Mac, Codex Desktop, ChatGPT, Gemini/Hermes, and future macOS, iOS, Android, Windows, and Linux clients. The main goal is to preserve future client room without overbuilding v1.

## Source Basis

- Local-first foundations: [Local-first software](https://martin.kleppmann.com/2019/10/23/local-first-at-onward.html) and [Automerge](https://automerge.org/).
- Platform security: [Apple App Sandbox](https://developer.apple.com/documentation/security/protecting-user-data-with-app-sandbox), [Apple Keychain](https://support.apple.com/guide/security/keychain-data-protection-secb0694df1a/web), [Windows Credential Locker](https://learn.microsoft.com/en-us/windows/apps/develop/security/credential-locker), [freedesktop Secret Service](https://specifications.freedesktop.org/secret-service/latest/index.html), and [Android Keystore](https://developer.android.com/privacy-and-security/keystore).
- Desktop shells: [Tauri capabilities](https://v2.tauri.app/security/capabilities/) and [Electron security](https://www.electronjs.org/docs/latest/tutorial/security).
- Structured contracts: [JSON Schema](https://json-schema.org/specification), [OpenAPI](https://www.openapis.org/), and [CloudEvents](https://cloudevents.io/).

## Confirmed Best Practices

Local-first software keeps user agency and data ownership by making local state useful without a central service. OpenClaw's operator-controlled nature fits this strongly.

Platform security models differ. macOS/iOS sandboxing, Windows credential APIs, Linux Secret Service, and Android Keystore have different affordances and limits. A portable harness should not assume one filesystem, credential, or background-execution model everywhere.

Desktop web shells require explicit IPC boundaries. Tauri v2 capabilities and Electron security guidance both emphasize narrowing what a webview can do. Any future desktop UI should expose a small command API, not raw shell or filesystem access.

Stable schemas preserve client optionality. JSON Schema/OpenAPI/CloudEvents-style contracts allow CLI, local web UI, desktop apps, and future mobile clients to agree on packets, evidence, and events.

## Recommended Architecture Layers

1. Domain schema layer

- LaunchPacket schema.
- EvidenceTrail schema.
- DeploymentRegistry schema.
- SourceSetManifest schema.
- ParallelStepBundle schema.
- ApprovalRecord schema.

This layer should be platform-neutral and testable without UI.

2. Local artifact layer

- Markdown for human-readable docs and evidence.
- YAML/JSON for structured packet data.
- Content hashes for approval binding.
- Repo paths as canonical proof locations.

3. Local command adapter layer

- Executes only approved packets.
- Runs declared commands in declared workspaces.
- Enforces forbidden paths and stop conditions.
- Writes evidence summaries.

4. Local index layer

- Optional SQLite or file index for search and UI speed.
- Rebuildable from artifacts.
- Not canonical for approvals or evidence.

5. UI layer

- V1 can be static/local web or lightweight CLI views.
- V2 may be Tauri or Electron if local IPC security is well-scoped.
- Future mobile clients should browse, approve, and review evidence before they execute anything.

## Platform Staging

Stage 1: PC/WSL and Mac repo-native CLI

- Generate and validate packets.
- Write evidence.
- Refresh source-set folders.
- No remote sync.
- No runtime mutation.

Stage 2: Local browser UI

- Browse Atlas, ladders, packets, evidence, freshness, and drift.
- Launch only through local adapter with exact approval.
- Keep all canonical state in repo artifacts.

Stage 3: Desktop shell

- Consider Tauri first if Rust/native integration and smaller IPC surface fit the stack.
- Consider Electron only with strict sandboxing, context isolation, disabled Node integration in renderers, and explicit IPC allowlists.
- Credential access stays OS-mediated.

Stage 4: Mobile companion

- Browse packet/evidence state.
- Approve exact packet hashes.
- Use platform keychain/passkey only for local app auth or external service auth.
- Avoid direct filesystem assumptions.

Stage 5: Multi-device sync

- Defer until there is a threat model, conflict model, and operator need.
- CRDT/local-first tooling may be useful later, but v1 should not need collaborative sync.

## Source-Set Refresh Folders

For ChatGPT Projects or other provider contexts, v1 should generate local source-set folders or manifests for manual upload/use:

- Include only declared paths.
- Exclude private/legal/vault/log/secret areas by policy.
- Include manifest with generated time, source commit/hash, source paths, omitted paths, and freshness state.
- Do not call providers directly in v1.
- Do not store provider credentials.

## OpenClaw Recommendations

- Build schemas first, UI second.
- Make the local artifact layer canonical.
- Keep indexes disposable.
- Keep credential storage outside OpenClaw application data.
- Make all platform adapters implement the same narrow packet execution contract.
- Treat future iOS/Android as constrained approval/evidence clients unless a later design justifies local execution.

## Risks And Anti-Patterns

- Building a cloud sync service before local artifacts are stable.
- Hiding canonical state in a desktop app database.
- Giving webviews broad filesystem or shell authority.
- Assuming iOS/Android can behave like a desktop filesystem client.
- Storing credentials for cross-platform convenience.
- Provider-specific source refresh code baked into core architecture.

