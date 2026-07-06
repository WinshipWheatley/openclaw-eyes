# SELF-ORIENT

To understand this system, run the authorized local orientation command:

```bash
python -m self_knowledge_orient --level high
```

This is the single source entry point for the whole-system map, from high to deep:

- `--level high`: machines, repos, OpenClaw instance counts, services, edges, and health rollups.
- `--level medium`: per-machine repos, worktrees, branches, services, and OpenClaw instances.
- `--level deep`: per-node state and graph relationships; add `--node-id <id>` to narrow.

Security boundary: the pointer is discoverable, but the data is not open. The command reads only the local self-knowledge ledger, requires an authorized local OpenClaw runtime context, exposes no network endpoint, performs no mutation, and must not be copied into hosted/external model packets.

When the system-level request is vague, first orient from this ledger, then act from the real map.
