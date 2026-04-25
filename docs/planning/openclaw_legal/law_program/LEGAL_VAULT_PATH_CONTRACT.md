# LEGAL_VAULT_PATH_CONTRACT

## Purpose

Sensitive legal matter data must live in a dedicated Legal Vault outside the OpenClaw Legal product code repo.

This contract defines where legal data may live, where it must never live, and how the system should enforce path boundaries so non-local LLMs, support packets, updates, and product code do not accidentally view or ship private matter content.

The Legal Vault is the firm’s private runtime evidence/work-product space. The product repo is only the reusable engine.

## Core doctrine

```text
OpenClaw Legal code can process legal data.
OpenClaw Legal code must not contain legal data.
```

The default rule is fail-closed:

```text
If the system cannot prove a matter path is inside an approved vault and outside the product repo, it must refuse to create/import/process the matter.
```

## Required behavior

- Every firm deployment must have an explicit configured Legal Vault root.
- Matter roots must live under the configured Legal Vault root.
- Matter roots must not live inside the OpenClaw code repo.
- Matter roots must not live inside source-control folders unless explicitly configured as a synthetic/demo-only fixture.
- Matter data paths must be checked before source registration, extraction, search, report export, packet export, support packet generation, and update packaging.
- The system must distinguish product code paths from matter vault paths.
- The system must reject paths that escape the configured vault through symlinks, relative path traversal, aliases, mounts, or shortcuts.
- Demo/test paths must be synthetic and clearly marked.
- Real legal data must be excluded from commits, updates, support packets, public fixtures, and non-local LLM context.
- Vault location should be firm-configurable and portable, but explicit.
- The Primary Node should own the canonical Legal Vault for the firm.

## Recommended path model

A future deployment may use a structure like:

```text
/LegalVault/
  firm_profile/
  matters/
    matter-001/
      manifest.json
      audit.jsonl
      sources/
      extracted/
      transcripts/
      notes/
      exports/
      review-packets/
  staging/
  support_packets/
  logs/
```

This is an example only. The actual path should be configured per firm.

The product repo should contain only code, docs, tests, and synthetic fixtures:

```text
OpenClaw Legal product repo
  legal/
  tests/
  docs/
  scripts/
  synthetic fixtures only
```

## Allowed vault contents

The Legal Vault may contain:

- real discovery files
- source PDFs, emails, audio, video, images, exports, or portal downloads
- extracted text
- transcripts
- reports
- review packets
- attorney notes
- privilege review artifacts
- chronology artifacts
- audit logs
- processing queue state
- local performance history tied to matters
- pre-sanitized diagnostics before feature request export

## Forbidden repo contents

The OpenClaw product repo must not contain:

- client files
- real discovery
- real PDFs/emails/transcripts/audio/video
- real extracted matter text
- real reports
- real review packets
- attorney notes
- privileged materials
- raw matter audit logs
- real firm names in reusable fixtures/docs
- real matter names in reusable fixtures/docs
- feature request packets before sanitization

## Path validation requirements

A future implementation should validate:

- configured vault root exists or can be created safely
- configured vault root is outside the product repo
- matter root resolves under the configured vault root
- matter root does not resolve under the product repo
- source files are either copied into the vault or registered according to explicit policy
- export paths resolve under the vault unless user explicitly performs a manual external export
- support packet paths are under a controlled support-packet staging area
- update package builder cannot traverse into matter vault paths
- non-local/cloud model contexts exclude vault paths

Path checks should use resolved/canonical paths, not raw strings.

## UX requirements

The operator should see clear vault status:

```text
Legal Vault: Connected
Vault location: /FirmLegalVault
Local-only: ON
Matter data in repo: NO
Cloud access to matter data: BLOCKED
```

If the vault is not configured:

```text
Legal Vault not configured.
Choose a local vault location before adding discovery.
```

If the user tries to create a matter inside the repo:

```text
Blocked: Matter data cannot be stored inside the OpenClaw Legal product folder.
Choose a Legal Vault location outside the code repo.
```

If the user tries to export outside the vault:

```text
External export requires explicit approval.
This may copy sensitive matter data outside the protected Legal Vault.
```

## Acceptance tests / proof points

A future PC/WSL implementation should prove this contract with checks such as:

- Creating a matter under an approved vault succeeds.
- Creating a matter inside the product repo fails.
- Creating a matter through `../` path traversal fails.
- Creating a matter through a symlink back into the repo fails.
- Source registration rejects or safely copies files according to policy.
- Review packet export stays inside the matter vault by default.
- Support packet generation excludes matter files and extracted text.
- Update package creation refuses to include vault contents.
- Non-local/cloud prompt assembly refuses to read from vault paths.
- Synthetic test fixtures remain allowed only in clearly marked test/demo paths.

## Failure behavior

If a path boundary check fails, the system should fail closed.

Examples:

- Block matter creation/import if the vault is missing or unsafe.
- Block source registration if the target matter is outside the configured vault.
- Block export if the destination escapes the vault without explicit approval.
- Block support packet creation if sensitive vault data is detected.
- Block cloud/non-local model use if matter vault content is included.
- Produce a readable diagnostic explaining which path boundary failed.

## Notes for first law-firm v1 deployment

- Configure a dedicated Legal Vault before adding real discovery.
- Treat the Primary Node’s vault as the firm’s canonical evidence/work-product store.
- Do not place the vault inside the product repo.
- Do not place the vault in a consumer cloud-sync folder by default unless the firm explicitly approves the risk.
- Decide separately whether worker nodes may cache matter data locally.
- If worker caching is allowed, it must be encrypted and governed by node policy.
- Support/update flows must be proven not to collect vault contents before deployment.

## Relationship to non-local LLM policy

This contract supports local-only and sensitive-data routing.

Non-local LLMs may inspect product code/docs if allowed by policy, but they must not inspect:

- matter sources
- extracted matter text
- transcripts
- attorney notes
- audit logs
- reports
- review packets
- pre-sanitized diagnostics

If a prompt/context builder cannot distinguish repo code from vault data, it must not use non-local LLMs.

## Likely future modules/files to inspect or build later on PC/WSL

Planning targets only; verify against the PC/WSL repo before implementation:

- `legal/vault_policy.py`
- `legal/firm_profile.py`
- `legal/path_guard.py`
- `legal/support_packet.py`
- `legal/update_manager.py`
- `legal/local_only_policy.py`
- `tests/test_legal_vault_path_contract.py`
- `tests/test_vault_outside_repo.py`
- `tests/test_support_packet_sanitization.py`
- `tests/test_nonlocal_llm_vault_block.py`

## Relationship to other contracts

This contract depends on:

- `LEGAL_PRODUCT_CORE_SEPARATION`

This contract supports:

- `LEGAL_FIRM_IMMUTABILITY_CONTRACT`
- `LEGAL_LOCAL_ONLY_MODEL_POLICY`
- `LEGAL_AI_ACCESS_CLASSIFICATION`
- `LEGAL_SANITIZED_SUPPORT_PACKET`
- `LEGAL_UPDATE_LANE_CONTRACT`
- `LEGAL_CONNECT_MENU_CONTRACT`
- `LEGAL_WORKER_DATA_RETENTION_CONTRACT`

If this contract is weak, the product risks leaking the exact data it is supposed to protect.
