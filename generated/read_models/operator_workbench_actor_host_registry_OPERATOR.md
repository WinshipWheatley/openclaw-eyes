# Operator Workbench / Actor Host Registry v0

Status:
- Deterministic metadata-only registry.
- Hosts registered: `8`.
- OpenClaw is the Operator System; these tools are workbenches, actor hosts, build environments, or execution surfaces, not the helm.
- No live integration, agent launch, model call, browser/OAuth, send, submit, approval, or runtime authority is added.

## Usable Now
- `pc_wsl_repo_a`: PC/WSL Repo A | canonical_repo | autonomy `L2_SCOPED_READ_WRITE_EXPLICIT_PROMPT`
- `mac_mission_control_app`: Mac Mission Control app | helm_app | autonomy `L1_DISPLAY_AND_EXISTING_MARKER_WRITE_ONLY`
- `codex_vscode_mac_codex_desktop`: Codex in VS Code / Mac Codex Desktop | implementation_worker | autonomy `L2_SCOPED_READ_WRITE_EXPLICIT_PROMPT`
- `antigravity_gemini_flash_high`: Antigravity CLI/Desktop with Gemini 3.5 Flash High | fast_planner_verifier | autonomy `L2_SCOPED_READ_WRITE_EXPLICIT_LANE`
- `gpt_5_5_chatgpt_orchestrator`: GPT-5.5 / ChatGPT orchestrator | orchestrator | autonomy `L0_PREVIEW_PACKAGE_ONLY`
- `xcode_xcodebuild`: Xcode / xcodebuild | build_environment | autonomy `L1_EXPLICIT_BUILD_VALIDATION_ONLY`
- `terminal_shell`: Terminal / shell | terminal_surface | autonomy `L1_EXPLICIT_SCOPED_COMMANDS_ONLY`

## Candidate / Future-Gated
- `vscode_agents_remote_ahp_candidate`: VS Code 1.121+ / Agents / Remote Agents / AHP | status `candidate` | autonomy `L0_PREVIEW_PACKAGE_ONLY`

## Current Safe Autonomy
- `L0`: preview package only.
- `L1`: copy/open package in right workbench.
- `L2`: launch bounded session with package.
- `L3`: monitor session and ingest receipt.
- `L4`: auto-run safe maintenance lanes only.
- `L5`: broader execution after security/approval gates.

## Actor Routing Summary
- Model/actor: The language model is the actor that may perform work later.
- Agent/character: The agent is the character/persona the actor plays, such as Chief, Cassandra, Guardian, Niles, or Hermes.
- Package/script: The package is the script/context/tools/clearance/steps/boundaries/proof requirements.
- The system decides authority, context, tools, clearance, and lane before any future launch.
- Unknown actor or host fails closed.

## Best-Fit Workbench Notes
- PC/WSL Repo A: best for canonical backend/read-model contracts, SQLite metadata receipts, deterministic scripts and focused tests; risky for live workflow execution by default, account access, external send or submit flows.
- Mac Mission Control app: best for helm UI display, read-only local mirror consumption, existing narrowly implemented sync marker write; risky for backend command authority, arbitrary filesystem mutation, credential handling.
- Codex in VS Code / Mac Codex Desktop: best for scoped file edits, tests and builds, Xcode validation; risky for slow long-running loops, tool friction, window or screenshot fragility.
- Antigravity CLI/Desktop with Gemini 3.5 Flash High: best for fast bounded planning, structured codebase critique, refactoring within explicit boundaries; risky for autonomous infrastructure administration, unbounded shell execution, final authority for security.
- GPT-5.5 / ChatGPT orchestrator: best for architecture synthesis, taste and safety judgment, prompt package authoring; risky for claiming machine state it cannot observe, granting authority without Repo A proof, long implementation without local validation.
- Xcode / xcodebuild: best for Mac app build validation, compile diagnostics, simulator or GUI validation when explicitly scoped; risky for fragile window state, screenshot validation drift, slow UI launch loops.
- Terminal / shell: best for focused local reads, tests, export scripts; risky for interactive prompts, credential prompts, broad destructive commands.
- VS Code 1.121+ / Agents / Remote Agents / AHP: best for future remote agent session coordination, future persistent bounded sessions, future mutation sequencing across clients; risky for treating candidate features as active OpenClaw authority, unsupervised remote mutation, credential-bearing terminal prompts.

## Proof / Receipt Expectations
- Every host returns receipt before ingest: `true`.
- Receipts must echo package/lane, list changes/commands/validation, confirm boundaries, and report blocked or unknown items.
- Raw credentials, private bodies, and broad logs are excluded.

## What Should Never Be Delegated
- `security_credentials_legal_sensitive_final_authority`: never to fast planner/verifier without dedicated review.
- `destructive_cleanup_or_remount`: not from this registry.
- `send_submit_approval`: blocked unless future narrow authority lane grants it.
- `unbounded_shell_or_infrastructure_admin`: blocked by default.

## How This Helps Winship
- Mission Control can show which workbench should receive a future package without requiring Winship to manually map every developer tool.
- OpenClaw can distinguish the helm from underlying workbenches, actor hosts, build environments, and terminal surfaces.
- The registry preserves what each host is good for, what it should never receive, and which receipt must come back.
- Autonomy is explicit and conservative now, with higher levels future-gated behind security and approval lanes.

## Future-Gated
- live launch/open package buttons
- external model API integrations
- agent sessions
- browser/OAuth/account bridges
- Gmail/calendar/Coupa/Telegram access
- send/submit/approval authority
- runtime execution authority
- auto-maintenance lanes above L3

## SQLite / Ledger Receipt
- Existing safe pattern: `business_ops_ledger.record_receipt`.
- Receipt meaning: metadata-only `generated_status`, receipt-record-only, no runtime authority.
- Raw tool outputs, credentials, private bodies, and broad logs are not stored.

## Next Safe Lane
- Workbench Actor Host Intake: VS Code Remote Agents / AHP Boundary Packet v0
