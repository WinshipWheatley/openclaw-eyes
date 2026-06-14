# Hermes Sidecar Inventory

## Overview
This document serves as the boundary map for the local Hermes sidecar, distinguishing the `local_sidecar_process` located in `sidecars/hermes/` from OpenClaw's internal `internal_advisory_identity` for Hermes.

## Inventory Answers
1. **Is Hermes sidecar present?** Yes, the Nous Hermes Agent codebase is present in `sidecars/hermes/`.
2. **Is it running?** No, there are no running processes mentioning `hermes`.
3. **Is this OpenClaw internal Hermes, Nous Hermes Agent/Desktop, or another local sidecar?** It is the Nous Hermes Agent (classified as a `local_sidecar_process`), which is physically distinct from OpenClaw's hardwired `internal_advisory_identity` known as Hermes (which serves as an advisory-only systems-engineering reviewer).
4. **What files/directories does it read?** It has tools (`sidecars/hermes/tools/file_tools.py`) capable of arbitrary file reads, though the Hermes Machine Contract bounds it to an explicit `source_set`.
5. **What files/directories can it write?** It has tools capable of file writes, but the contract strictly forbids it from mutating canonical docs, runtime, or state.
6. **Does it have its own memory/state DB?** Yes, it maintains shadow memory/state (`hermes_state.py`). This shadow state is flagged as non-canonical.
7. **Does it have network/model/provider access?** The sidecar codebase includes gateway and external provider integrations. External provider access must remain blocked per OpenClaw policy unless explicitly registered.
8. **Does it write receipts to OpenClaw?** No, it does not currently have verified SQLite wiring for packet receipts in the main repo.
9. **Is it registered in provider/harness selection?** No, it is not present in the harness or operator assist provider selection registries.
10. **Is Guardian gating it?** No, the Hermes Machine Contract states Hermes is not a Guardian gate and cannot satisfy Tier 2 approvals.
11. **Is it sleep-safe?** No, autonomous wiring and queue mutation are blocked.
12. **What must remain blocked?**
   - Direct mutation to non-advisory outputs
   - Autonomous wiring (e.g., systemd units, environment files, `.mcp.json`)
   - Approval decisions bypassing Chief/Guardian
   - Queue mutation in the OpenClaw runtime
   - Canonical memory writes
   - Broad MCP expansion
   - External provider access (unless registered)
   - Any action grants

## Classification
- OpenClaw Agent Route "Hermes": `internal_advisory_identity`
- `sidecars/hermes/` Codebase: `local_sidecar_process`
- External integration status: `external_harness_candidate` (currently blocked)

Status: `HERMES_SIDECAR_INVENTORY_READY`
