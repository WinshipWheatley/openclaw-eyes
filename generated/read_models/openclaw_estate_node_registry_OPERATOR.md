# OpenClaw Estate Node Registry

What this is:
- A deterministic registry of repos, mirrors, shuttles, Mac workspaces, and future nodes.
- It helps route work to the right environment before a lane starts.

What this is not:
- No SSH configuration, service start, Repo B execution, browser automation, send/submit path, deployment, or Mission Control app change.

Summary:
- Nodes: 10.
- Active authority nodes: repo_a_pc_wsl_backend.
- Future/planned nodes: 4.

Key Nodes:
- `repo_a_pc_wsl_backend`: Repo A / PC-WSL Canonical Backend | `canonical_backend_read_model_contract_test_authority` | `canonical_current_backend`
- `repo_b_pc_wsl_reference`: Repo B / PC-WSL Reference Capability Tree | `reference_evidence_only` | `not_canonical_pre_split_capability_tree`
- `mac_mission_control_xcode_repo`: Mac Mission Control Xcode Repo | `app_surface_only` | `non_canonical_backend_consumer`
- `mac_generated_read_model_mirror`: Mac Generated Read-Model Mirror | `mirrored_visibility_only` | `mirror_not_truth`
- `shared_e_drive_shuttle`: Shared E-Drive Shuttle | `transport_proof_surface` | `transport_not_truth`
- `mac_openclaw_planner_builder_harness`: Mac OpenClaw Planner/Builder/Harness Node | `non_canonical_candidate` | `candidate_non_canonical_unless_promoted`
- `mac_studio_future_workstation`: Future Mac Studio Workstation Node | `planned_no_active_authority` | `planned_non_canonical`
- `mac_laptop_future_execution_node`: Future Mac Laptop Semi-Mobile Node | `planned_no_active_authority` | `planned_non_canonical`
- `ipad_iphone_operator_surface_future`: Future iPad/iPhone Operator Surface | `planned_visibility_or_approval_surface_only` | `planned_non_canonical`
- `client_friend_company_node_future`: Future Client/Friend/Company Node | `planned_capsule_reporting_only` | `external_non_canonical`

Machine Access Policy:
- SSH Mac <-> PC/WSL: `allowed_for_scoped_development_workflows`.
- SSH reachability does not grant task, runtime, send, submit, or Repo B authority.
- PC/WSL backend lanes run in `/home/openclaw`; Mac/Xcode lanes run on the Mac app repo.
- Browser/Coupa/desktop automation must be a future Mac-local gated lane.

Wrong-Environment Guidance:
- `pc_wsl_backend_contract_read_model_tests` -> `repo_a_pc_wsl_backend`. Do not run backend contract/read-model/test lanes from the Mac app repo.
- `mission_control_xcode_app_surface` -> `mac_mission_control_xcode_repo`. Do not attempt SwiftUI/Xcode build or launch from /home/openclaw.
- `mission_control_read_only_data_display` -> `mac_generated_read_model_mirror`. Do not edit mirror files as truth; refresh through governed sync.
- `mac_browser_coupa_desktop_automation` -> `mac_openclaw_planner_builder_harness`. Do not run browser/Coupa/desktop automation from PC/WSL; require future Mac-local gates.
- `repo_b_capability_reference` -> `repo_b_pc_wsl_reference`. Repo B may be inspected read-only but must not be imported or executed.
- `read_model_sync_transport` -> `shared_e_drive_shuttle`. Use existing marker/manifest flow; do not manually copy as the primary fix.
- `mobile_operator_visibility_or_approval` -> `ipad_iphone_operator_surface_future`. Future mobile surfaces have no active authority yet.

Boundary:
- Future nodes are listed for role/capability planning only and gain no active authority.
- Repo B remains reference-only and not runtime authority.
- The E-drive shuttle is transport/proof surface, not canonical truth or manual-copy authority.

Next safe lane: Mission Control Estate Node Registry Surface v0
