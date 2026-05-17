# OpenClaw Estate Node Registry Contract v0

This contract defines how OpenClaw distinguishes repos, mirrors, shuttles, Mac
workspaces, and future nodes before routing work.

## Purpose

The estate node registry is a read-only topology contract. It helps future
lanes choose the correct environment:

- PC/WSL backend work runs in `/home/openclaw`.
- Mission Control UI work runs in the Mac Xcode repo.
- Mac browser/Xcode/desktop automation must be Mac-local and explicitly gated.
- Repo B remains reference-only capability evidence.
- Mirrors and shuttles provide visibility or transport, not canonical truth.

## Required Node Fields

Each node record must include:

- `node_id`
- `display_name`
- `node_type`
- `known_paths`
- `operating_system`
- `hardware_class`
- `mobility_class`
- `authority_level`
- `canonicality`
- `suited_work`
- `blocked_work`
- `allowed_access_patterns`
- `sync_or_bridge_surfaces`
- `promotion_required_for_authority`
- `evidence_status`
- `operator_notes`

## Authority Boundary

The registry does not configure SSH, start services, execute Repo B, mutate
Mission Control, grant browser automation, grant runtime authority, create
send/submit authority, or create customer deployment authority.

SSH between Mac and PC/WSL may be used for scoped development workflows, but
SSH reachability does not grant task authority. The correct node/workspace
still controls where work should run.

## Routing Rules

- Backend/read-model/contracts/tests: `repo_a_pc_wsl_backend`.
- SwiftUI/Xcode app work: `mac_mission_control_xcode_repo`.
- App display data: `mac_generated_read_model_mirror`.
- Mirror/shuttle exchange: `shared_e_drive_shuttle`.
- Repo B capability lookup: `repo_b_pc_wsl_reference`, read-only only.
- Coupa/browser/desktop automation: future gated Mac-local node only.
- Future mobile/client nodes: role/capability planning only until explicitly
  promoted by a separate authority contract.

## Generated Outputs

- `generated/read_models/openclaw_estate_node_registry.json`
- `generated/read_models/openclaw_estate_node_registry_OPERATOR.md`
