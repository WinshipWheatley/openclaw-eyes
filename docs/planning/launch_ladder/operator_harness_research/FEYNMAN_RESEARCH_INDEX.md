# Feynman Research Index

## Scope

This research set covers best practices and first principles for an OpenClaw Operator Harness, Launch Ladders, Launch Packets, Evidence Trails, Route Compression, Parallel Step Bundles, cross-platform staging, and a future Multi-OpenClaw Command Atlas.

The work used the installed Feynman `deep-research` and `literature-review` skills as a workflow shape: source-heavy investigation, primary-source preference, synthesis separated from confirmed practice, and a verification pass for claims and citations. The installed skill files point to slash-command workflows, but those slash commands were not directly available in this runtime, so the workflow was executed locally in this session.

## Documents

- [OPERATOR_HARNESS_FIRST_PRINCIPLES.md](./OPERATOR_HARNESS_FIRST_PRINCIPLES.md)
- [LAUNCH_LADDER_BEST_PRACTICES.md](./LAUNCH_LADDER_BEST_PRACTICES.md)
- [HUMAN_OPERATOR_UX_PATTERNS.md](./HUMAN_OPERATOR_UX_PATTERNS.md)
- [MULTI_DEPLOYMENT_CONTROL_PLANE.md](./MULTI_DEPLOYMENT_CONTROL_PLANE.md)
- [SECURITY_AND_APPROVAL_ARCHITECTURE.md](./SECURITY_AND_APPROVAL_ARCHITECTURE.md)
- [CROSS_PLATFORM_ARCHITECTURE.md](./CROSS_PLATFORM_ARCHITECTURE.md)
- [EVIDENCE_FRESHNESS_AND_DRIFT_DETECTION.md](./EVIDENCE_FRESHNESS_AND_DRIFT_DETECTION.md)
- [PARALLEL_WORK_ORCHESTRATION.md](./PARALLEL_WORK_ORCHESTRATION.md)
- [PRODUCTIZATION_NOTES.md](./PRODUCTIZATION_NOTES.md)
- [RECOMMENDED_V1_ARCHITECTURE.md](./RECOMMENDED_V1_ARCHITECTURE.md)

## Source Map

Human-AI and automation:

- [NIST AI Risk Management Framework](https://www.nist.gov/itl/ai-risk-management-framework)
- [NIST Four Principles of Explainable AI](https://www.nist.gov/publications/four-principles-explainable-artificial-intelligence)
- [NIST AI 600-1 Generative AI Profile](https://nvlpubs.nist.gov/nistpubs/ai/NIST.AI.600-1.pdf)
- [Microsoft Guidelines for Human-AI Interaction](https://www.microsoft.com/en-us/research/?p=564561)
- [Google PAIR Guidebook](https://pair.withgoogle.com/guidebook-v2/)
- [Google PAIR Explainability + Trust](https://pair.withgoogle.com/guidebook-v2/chapter/explainability-trust/)
- [Parasuraman, Sheridan, and Wickens automation taxonomy](https://www.cs.uml.edu/~holly/91.550/papers/sheridan-autonomy.pdf)
- [Onnasch et al., human performance consequences of automation](https://journals.sagepub.com/doi/pdf/10.1177/0018720813501549)
- [Bainbridge, Ironies of Automation](https://commons.wmu.se/lib_articles/407/)

Operations, control, and reliability:

- [Google SRE postmortem culture](https://sre.google/sre-book/postmortem-culture/)
- [Google SRE eliminating toil](https://sre.google/sre-book/eliminating-toil/)
- [Google SRE Workbook eliminating toil](https://sre.google/workbook/eliminating-toil/)
- [OpenGitOps principles](https://opengitops.dev/)
- [Kubernetes controllers](https://kubernetes.io/docs/concepts/architecture/controller/)
- [OpenTelemetry signals](https://opentelemetry.io/docs/concepts/signals/)
- [GitHub Actions concurrency](https://docs.github.com/actions/concepts/workflows-and-actions/concurrency)
- [Kanban University Kanban Guide](https://kanban.university/kanban-guide/)
- [Atlassian incident management](https://www.atlassian.com/incident-management)
- [Azure Well-Architected Operational Excellence](https://learn.microsoft.com/en-us/azure/well-architected/operational-excellence/)

Security, identity, and approval:

- [NIST CSF 2.0](https://www.nist.gov/node/1840561)
- [NIST SP 800-53 Rev. 5](https://csrc.nist.gov/Pubs/sp/800/53/r5/upd1/Final)
- [NIST SP 800-207 Zero Trust](https://www.nist.gov/publications/zero-trust-architecture-0)
- [NIST SP 800-218 SSDF](https://csrc.nist.gov/pubs/sp/800/218/final)
- [NIST SP 800-63-4 Digital Identity Guidelines](https://pages.nist.gov/800-63-4/sp800-63.html)
- [CISA Secure by Design](https://www.cisa.gov/securebydesign)
- [OWASP Secrets Management Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Secrets_Management_Cheat_Sheet.html)
- [OWASP Logging Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html)
- [OWASP ASVS](https://owasp.org/www-project-application-security-verification-standard/)
- [OWASP CI/CD Security Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/CI_CD_Security_Cheat_Sheet.html)
- [FIDO passkeys](https://fidoalliance.org/passkeys/)
- [Apple Keychain data protection](https://support.apple.com/guide/security/keychain-data-protection-secb0694df1a/web)
- [Windows Credential Locker](https://learn.microsoft.com/en-us/windows/apps/develop/security/credential-locker)
- [freedesktop Secret Service](https://specifications.freedesktop.org/secret-service/latest/index.html)
- [OpenSSH manuals](https://www.openssh.org/manual.html)

Cross-platform and structured artifacts:

- [Local-first software](https://martin.kleppmann.com/2019/10/23/local-first-at-onward.html)
- [Automerge](https://automerge.org/)
- [Apple App Sandbox](https://developer.apple.com/documentation/security/protecting-user-data-with-app-sandbox)
- [Android Keystore](https://developer.android.com/privacy-and-security/keystore)
- [Tauri capabilities](https://v2.tauri.app/security/capabilities/)
- [Electron security](https://www.electronjs.org/docs/latest/tutorial/security)
- [JSON Schema](https://json-schema.org/specification)
- [OpenAPI](https://www.openapis.org/)
- [CloudEvents](https://cloudevents.io/)
- [SLSA provenance](https://slsa.dev/provenance)
- [in-toto](https://in-toto.io/)
- [Google Cloud ADR overview](https://cloud.google.com/architecture/architecture-decision-records)

## Strongest Recommendations

- Build v1 around repo-native artifacts and schemas, not a service-backed control plane.
- Make Launch Packets exact, hash-bound action contracts.
- Make Evidence Trails mandatory proof artifacts.
- Treat Route Compression as a reversible view with visible deferred work.
- Treat the Atlas as inventory/navigation/evidence, not authority or remote control.
- Keep secrets, vaults, private/legal data, logs, runtime mutation, and provider/model calls out of v1.
- Build source-set freshness and drift checks before sophisticated orchestration.
- Add Parallel Step Bundles only after write-set collision validation and per-lane evidence exist.

## Recommended V1 Artifact Types

- `LaunchPacket`
- `LaunchLadder`
- `EvidenceTrail`
- `SourceSetManifest`
- `DeploymentRegistry`
- `ApprovalRecord`
- `ParallelStepBundle`
- `DriftReport`

## Key Open Questions

- Where should canonical packet/evidence artifacts live in the existing OpenClaw docs tree?
- Should packet schemas be YAML-first, JSON-first, or dual with canonical JSON hashing?
- What local command adapter already exists, if any, and should v1 wrap it or start with dry-run/manual mode?
- What is the minimum UI needed: CLI only, static local HTML, or local app shell?
- How should operator identity be represented locally without creating a new identity system?
- What TTL policy should source-set freshness use for different kinds of ladders?
- Should source-set refresh folders be per deployment, per provider project, or per North Star task?

## Top Risks

- The harness becomes a hidden authority layer.
- The Atlas becomes a premature remote control plane.
- Approval is granted to intentions instead of exact packet hashes.
- Secrets leak through logs, clipboards, or evidence artifacts.
- Route Compression hides deferred validation.
- Freshness is oversimplified into misleading confidence.
- Parallel execution is added before collision and evidence rules are enforced.
- Cross-platform ambitions force a desktop/mobile architecture before the local artifact model is proven.

