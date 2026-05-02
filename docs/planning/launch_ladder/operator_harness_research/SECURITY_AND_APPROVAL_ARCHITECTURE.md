# Security And Approval Architecture

## Purpose

This document defines security and approval principles for the Operator Harness, Launch Packets, Guardian approval, and future Atlas clients. It assumes v1 is local-first, operator-controlled, and does not inspect private/legal/vault/log data or mutate services/runtimes.

## Source Basis

- Security frameworks: [NIST CSF 2.0](https://www.nist.gov/node/1840561), [NIST SP 800-53 Rev. 5](https://csrc.nist.gov/Pubs/sp/800/53/r5/upd1/Final), [NIST SP 800-207 Zero Trust](https://www.nist.gov/publications/zero-trust-architecture-0), [NIST SP 800-218 SSDF](https://csrc.nist.gov/pubs/sp/800/218/final), and [CISA Secure by Design](https://www.cisa.gov/securebydesign).
- Identity and authentication: [NIST SP 800-63-4](https://pages.nist.gov/800-63-4/sp800-63.html), [FIDO passkeys](https://fidoalliance.org/passkeys/), [Apple Keychain data protection](https://support.apple.com/guide/security/keychain-data-protection-secb0694df1a/web), [Windows Credential Locker](https://learn.microsoft.com/en-us/windows/apps/develop/security/credential-locker), [freedesktop Secret Service](https://specifications.freedesktop.org/secret-service/latest/index.html), and [OpenSSH manuals](https://www.openssh.org/manual.html).
- Secret handling and logging: [OWASP Secrets Management Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Secrets_Management_Cheat_Sheet.html), [OWASP Logging Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html), [OWASP ASVS](https://owasp.org/www-project-application-security-verification-standard/), and [OWASP CI/CD Security Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/CI_CD_Security_Cheat_Sheet.html).
- Agent safety: [OpenAI practices for governing agentic AI systems](https://openai.com/index/practices-for-governing-agentic-ai-systems) and [OpenAI agent safety guidance](https://platform.openai.com/docs/guides/agent-builder-safety).

## Confirmed Best Practices

Use least privilege and resource-specific access. NIST Zero Trust and SP 800-53 both support explicit access control, auditability, and narrowing trust to the resource/action being requested.

Keep secrets out of logs and code. OWASP guidance is direct: secrets should not be hardcoded, logged, printed, or stored in command histories. The harness must not create convenience paths that violate this.

Prefer platform credential mechanisms. Apple Keychain, Windows Credential Locker, freedesktop Secret Service, SSH-agent, hardware keys, and passkeys exist to keep credential handling local and mediated by the OS or authenticator.

Bind approval to exact action. Agent safety guidance and secure software practice both point toward explicit tool permissions, human approval for risky actions, and strong audit records.

Design secure defaults. CISA Secure by Design and NIST SSDF emphasize reducing unsafe defaults and making secure behavior the normal path.

## Approval Architecture

The approval object should bind:

- `packet_hash`: exact canonical hash of the launch packet.
- `operator_identity`: local operator identifier, not a remote account unless explicitly scoped later.
- `approval_time`: local timestamp with timezone.
- `approval_scope`: exact packet only.
- `risk_class`: read-only, write-local, external, credential-bearing, destructive, billing, runtime-mutating, private-data.
- `secret_policy`: no storage, no paste, no transmit, no unlock.
- `stop_conditions`: copied from packet.
- `evidence_path`: where proof will be written.

If the packet changes, approval expires. If the target workspace changes materially, approval should require refresh. If a forbidden path or credential prompt appears unexpectedly, execution stops.

## Guardian Role

Guardian may:

- Approve or deny exact action packets.
- Explain why a packet is blocked.
- Require missing fields, validation, or narrower scope.
- Record approval metadata and packet hash.

Guardian must never:

- Store, transmit, paste, unlock, or reveal passwords, SSH passphrases, tokens, private keys, recovery codes, hardware-key PINs, or vault contents.
- Inspect private/legal/vault/log folders in v1.
- Convert a one-time approval into standing permission.
- Approve mutated packets without re-hashing and re-presenting them.
- Make provider/model calls unless explicitly scoped later.

## Authentication Model

V1 should rely on local mechanisms:

- OS session identity for local UI access.
- Apple Keychain on macOS/iOS where a native client exists.
- Windows Credential Locker or Windows Credential Manager where a native Windows client exists.
- freedesktop Secret Service or compatible keyring on Linux desktops.
- SSH-agent for SSH private key use.
- Hardware security keys or passkeys for external services where those services support them.
- Manual operator entry for credentials that should not be stored.

The harness should record only that authentication was required and whether the operator completed it locally. It should not record the secret, derived secret, clipboard contents, prompt text containing secret values, or vault lookup output.

## Risk Classes

- Class 0: read declared public project files.
- Class 1: write docs or planning artifacts in declared workspace.
- Class 2: write code or tests in declared workspace.
- Class 3: run local validation commands.
- Class 4: destructive local changes, force-git, deletes, resets.
- Class 5: external network, billing, deployment, provider/model calls.
- Class 6: credential-bearing actions.
- Class 7: private/legal/vault/log inspection.
- Class 8: runtime/service mutation.

V1 should support Classes 0-3 with clear approvals where needed, block Classes 5-8 by default, and require separate explicit governance before expanding.

## OpenClaw Recommendations

- Make packet validation deny-by-default for missing target, scope, exclusions, validation, or stop conditions.
- Put forbidden paths in a shared policy file and duplicate them visibly in each packet.
- Use content hashes for packets, source-set manifests, and evidence artifacts.
- Never implement clipboard-based secret passing.
- Add an "unexpected credential prompt" stop condition to all launch packets by default.
- Treat "private data required" as a blocked state, not as an invitation to inspect.
- Use local-only audit records in v1.

## Risks And Anti-Patterns

- Guardian as a hidden credential broker.
- Approval records that say "approved" without packet hash or scope.
- Convenience logging of command output that may contain secrets.
- Background source refresh that crosses private boundaries.
- Long-lived blanket approvals.
- UI that makes denied or blocked states look like system failure instead of policy success.
- A future mobile client that syncs sensitive deployment inventory before a threat model exists.

