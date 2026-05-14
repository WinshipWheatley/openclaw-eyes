# OpenClaw Project Capsule v0

Project Capsule v0 is a bounded planning contract for turning “build X for Y” into inspectable local metadata.

Current scope:
- Synthetic demo only: `demo_project_capsule_v0`.
- Business Ops ledger namespace: `project_capsule_*`.
- No real client data.
- No deployment authority.
- No runtime, agent, network, Docker/Ollama, or tool execution authority.

Commands:
- `python3 scripts/create_project_capsule.py --demo --format operator`
- `python3 scripts/query_project_capsules.py --report summary --format operator`
- `python3 scripts/query_project_capsules.py --project-id demo_project_capsule_v0 --format operator`

Demo capsule:
- Project: `Demo Client Operations Helper`.
- Client: `demo_client`.
- Status: `draft`.
- Approval: `not_approved`.
- Worlds: `operations`, `build`, `communications`.
- Candidate tools are references to policy metadata only; they are not approved or integrated.

Boundary:
- Project capsules are local planning records, not truth promotion.
- Future real-client, deployment, support, or runtime work requires a separate scoped lane with receipts and explicit operator approval.
