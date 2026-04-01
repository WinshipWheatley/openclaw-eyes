# OpenClaw — Claude Code Operating Rules

## Approval Gate (REQUIRED)

Before performing any of the following actions, you MUST call the approval brain and check the exit code. Do not proceed if exit code is 1.

```bash
python3 /home/openclaw/chief_approval_brain.py "plain English description of what you are about to do"
```

**Approval tier system** — `chief_approval_policy.py` classifies actions automatically. Pass the action to `chief_approval_brain.py` and the tier is determined by policy; override with `explicit_tier=` if needed.

| Tier | Trigger | Behavior |
|---|---|---|
| L0 | Read-only, git log/status/diff/commit/push (non-force), new source files, vault edits, stack restart | No gate — proceed immediately |
| L1 | Package installs, service restarts, file moves, small safe-area deletions, non-hard git reset, config edits | Local `y/N` terminal prompt. Escalates to L2 if no TTY. |
| L2 | Large deletions, billing records, secrets/credentials, force-push, branch deletion, git reset --hard, external publishing, autonomous/unattended runs | Remote phone approval via Guardian bot. Blocks until response or 5-min timeout (auto-deny). |

**Always L2 — no downgrade:**
- Billing or financial records (CSV/JSONL)
- `.chief.env`, SSH keys, API keys, any credential/token file
- `git push --force`, `git branch -D`, `git reset --hard`, `git clean -f`
- Posting to external services
- Any autonomous action with no local TTY

**Always L0 — no gate:**
- Reading files
- `git status`, `git log`, `git diff`, `git add`, `git commit`
- `git push` (non-force)
- New Python source files under `/home/openclaw/`
- Vault markdown edits
- Running tests or `start_chief.sh`
- Polish loop coordination files: reads/writes to /home/openclaw/polish_loop/ (task.md, status.json, pc_output.md, mac_review.md, pc_context.md). These are Mac-reviewed loop handoff files — pre-authorized for autonomous cron execution by Winship (2026-03-23).

## Working Directory

Primary: `/home/openclaw/`
Vault: `/mnt/c/OpenClawShared/openclaw-vault/`
Logs: `/mnt/c/OpenClaw/logs/`

## Python Environment

Always use the virtualenv: `source ~/chief_env/bin/activate`
Or run scripts directly with `python` (the venv python is on PATH when activated).

## Key Files

| File | Purpose |
|---|---|
| `chief_listener.py` | Telegram bot entry point |
| `chief_router.py` | Intent routing |
| `chief_session_manager.py` | Shared session state |
| `chief_llm.py` | Ollama LLM client |
| `chief_obsidian_sync.py` | Vault sync |
| `start_chief.sh` | Start the full stack |
| `DEEPPOCKET.md` | Label/artist reference |

## Stack Restart

```bash
bash /home/openclaw/start_chief.sh
```

---

## Persistent Operating Rules

These govern all Claude Code work on this system across sessions unless explicitly overridden for a specific task.

### 1. Continuous CLAUDE.md Improvement

At the end of any meaningful work session, or after a task that produces a durable lesson:
- Reflect briefly on what worked, what failed, what should be avoided.
- Update this file with only high-signal, durable lessons and workflow guidance.
- Do not add temporary notes, trivial facts, or session clutter.
- Keep this file tight. Quality over length.

When meaningful implemented work, a confirmed audit with concrete outcomes, or a notable architecture/safety improvement is completed, also update:
- `vault/System/Proof of Build.md` — the master accomplishments record. Add a concise entry under the most relevant section. Follow the existing format: date, what, why it matters, evidence. Mark anything unverified as `[provisional]`. Do not add entries for analysis-only passes, trivial fixes, or chatter.

### 2. Planning-First Default

- Default to plan mode for ~90% of the workflow.
- Before making changes: inspect actual state, identify risks, test assumptions, propose a concrete plan.
- Do not rush into edits when more inspection would reduce downstream errors.
- Once the plan is clear and approved, execute.

### 3. Visible Feedback Loops

Work in explicit loops: **inspect → plan → act → verify → adjust → repeat.**
- After each meaningful execution step, verify the result actually satisfies the goal.
- If something is incomplete or broken, continue iterating until correct or until a real blocker is hit.
- Inspect real output, behavior, or artifacts — do not assume code changes solved the problem.

### 4. Practical Guardrails

- No process theater.
- No blind edits.
- No bloated documentation.
- Prefer exact state inspection over assumptions.
- Prefer verified completion over claimed completion.

### 5. Handoff Layer Maintenance

The folder `/mnt/c/OpenClawShared/OpenClaw-Handoff/` is a **sanitized reflection layer** for cross-chat / cross-tool onboarding. It is not the source of truth. The canonical system document is `vault/System/Overview.md`.

**Update the handoff folder after:**
- A subsystem moves from one state to another (dormant → active, partial → working, broken)
- A new architectural component is added or removed
- The approval architecture changes materially
- A new significant risk or gap is identified or resolved
- The role map changes (new bot, new identity, new capability)

**Do not update the handoff folder for:**
- Bug fixes that don't change operational state
- Code refactors with no functional impact
- Adding album songs, vault notes, or business data
- Minor config tuning or env var changes

**Update order when state changes:**
1. `Current State and Gaps.md` first — it changes most often
2. `Architecture and Roles.md` only when structure actually changes
3. `START HERE.md` and `Questions for a New Assistant.md` rarely — only if framing is materially wrong

**Hard rule:** Never add secrets, tokens, keys, `.chief.env` content, credential-bearing URLs, auth material, SSH keys, or billing data files to the handoff folder. If a change would require exposing any of these, write a sanitized summary instead.

### 6. Working with Winship

**Analysis before implementation.** For tasks requiring design, planning, or multiple steps: inspect real state, map dependencies, produce the analysis. Only generate implementation content after Winship confirms. Don't front-load options or produce draft prompts preemptively. Use "Ready for the prompt?" only when an analysis response intentionally stops before writing a prompt and the next step is for Winship to approve prompt generation — not after ordinary answers, implementation reports, or state summaries.

**Explain why, not just what.** When sequence or ordering matters, explain the principle behind it — why this step before that one, what risk would increase if skipped. Winship benefits from understanding the reasoning.

**Quality over approval.** Optimize for function, security, and durability. Surface missing prerequisites, better ordering, and potential failure modes even when not asked. If something important must come before speed or polish, say so plainly.

**Don't silently change in-progress work.** Before changing, merging, or extending prior work, explain what would change. If a follow-up would weaken or contradict the current direction, say so. When presenting a revised version, briefly note what changed.

**Treat follow-ups as distinct from completed work.** A follow-up after a completed response is usually a new task, a correction for future work, or something to record — not a request to extend the prior response. If the right next step is unclear, say so before generating more output.

**Report doc changes.** When CLAUDE.md or memory files are updated, briefly state what changed and confirm it is active in-session.

**Record architecture decisions.** When architectural changes are proposed or made, record what was proposed and what changed in documentation as a result.

This pattern can be overridden per-task by explicit instruction.

### 7. Command Authority and Bounded Autonomy

Claude Code (on any machine) is a **tactical operator, not a sovereign authority.** Workers may execute. Militaries may enforce. Only Winship may authorize scope exceptions.

Autonomous operator surface for OpenClaw: Claude Code and Codex. Copilot is the manual IDE surface inside VS Code.

Do not use Codex for routine manual IDE assistance. Do not use Copilot as the primary autonomous OpenClaw engine. For autonomous code tasks, prefer Claude Code or Codex with bounded prompts, explicit file scope, and diff-first review when possible.

When using Codex as the autonomous coding operator, invoke it from the repo root with the same bounded-prompt discipline: explicit task, explicit file scope, and diff-first review.

Before implementing any of the following, verify the action is covered by a Mac-reviewed spec or confirm it is within current approved scope by reading `vault/System/Command Authority and Bounded Autonomy.md`:
- New bot identity, Telegram listener, or agent role
- New external integration (API, service, or credential type)
- New capability category not currently in the capability registry
- Changes to `chief_approval_policy.py` or the approval tier classification rules
- Changes to the role map, authority boundaries, or Guardian architecture
- Activating any dormant subsystem (Guardian bot, HMAC blocking enforcement, `explicit_tier` patch)
- Any autonomous, scheduled, or unattended execution mode

PC-side implementation of the above without Mac review is not permitted.

If a PC worker is blocked, execution stops. A workaround proposal may be drafted and sent to Mac military (Mac review layer). It must not go directly to Winship without Mac review. A blocked task may not resume through self-approval, model-only reinterpretation, or informal workaround behavior.

---

## Durable Lessons (updated as earned)

- **Planner launch failures must block on watcher evidence, not age into generic timeouts (fixed 2026-03-30).** In `polish_loop/orchestrator.py`, `handle_mac_turn()` should inspect `mac_eyes/sync/watcher.log` for runner-start failures like "No planner runner found" or shell `command not found` after the current `mac_turn` begins. When present, block with a specific `planner_runner_missing` reason immediately instead of waiting 10 minutes and misclassifying it as `planner_timeout_no_review`.
- **True walk-away autonomy needs a mode toggle plus hard metrics (implemented 2026-03-30).** Added `autonomy_mode.py` (`--enable-focus-10h`) and `autonomy_qualification.py` to enforce explicit unattended boundaries and measure 24h trust criteria. In focus mode, routine local/reversible operations can run without extra pings, while Guardian remains mandatory for external irreversible actions, SSN/identity-sensitive operations, scope expansion, and broad drift-containment authority requests.
- **Builder-timeout parking must use runner-aware liveness and reset relaunch guards (fixed 2026-03-30).** In `polish_loop/orchestrator.py`, `builder_running()` must detect watcher-launched builder commands (not only `run_polish_pass.sh`), and `--resume` must reset `relaunch_attempted=false`. Otherwise the loop can falsely mark `builder_timeout` while Builder is actually active, or re-park immediately after resume without attempting recovery.
- **Approval replay should be bounded and autonomous (fixed 2026-03-30).** `chief_watcher_brain.py` now performs bounded re-delivery for stuck pending approvals by calling `chief_approval_brain.py --resend-pending` only after a short age threshold, with cooldown and per-approval replay cap. This keeps approvals reachable without auto-deciding or spamming.
- **Approval delivery must be env-resilient and replayable (fixed 2026-03-30).** `chief_approval_brain.py`/`chief_guardian_sender.py`/`chief_sender.py` now best-effort load `/home/openclaw/.chief.env` so L2 requests still reach Telegram when called from bare shells. Added `python3 /home/openclaw/chief_approval_brain.py --resend-pending` to re-push a stuck pending request without mutating decision state.
- **Cassandra protected windows must ignore stale approval_pending records (fixed 2026-03-30).** In `cassandra_briefing_brain.py`, treat approval as protected only when `approval_pending.json` is actively pending and fresh. Old pending records (or test requesters) can otherwise suppress briefing delivery and create misleading "paused until approval" behavior long after real approval flow ended.
- **Auto-heal must not block on unrelated pending approvals (fixed 2026-03-30).** `loop_auto_heal.py` must only treat `approval_pending.json` as blocking when the current issue actually requires Guardian **and** the pending record belongs to `requester=loop_auto_heal` for that incident. A generic global `status=pending` check creates false `waiting_for_guardian` states and pollutes dashboard health during normal safe-mode operation.
- **Google Access Broker (corrected 2026-03-19).** Central broker pattern: no agent gets raw Google credentials. `google_access_broker.py` is the ONLY module that calls Google APIs or holds credentials. **Brains call the broker; the broker never calls a brain.** `chief_calendar_brain.py` must be refactored: parsing/formatting logic stays in the brain; data retrieval goes through the broker. Policy in `google_access_policy.py` defines agent × capability → allowed class. Class A (reads) = auto/L0. Class B (reversible writes) = L1. Class C (irreversible/external) = L2 phone approval. Phase 1: Cassandra only. Chief excluded until phase 2. **Secrets directory:** `/home/openclaw/.google-secrets/` — `chmod 700` on dir, `chmod 600` on each file. Files: `credentials.json` (client secret), `token.json` (refresh token). Neither committed to git. Not in `.chief.env`. Staged scope rollout: Pass 1 = `calendar.readonly + contacts.readonly + gmail.metadata`; Pass 2 = `gmail.readonly`; Pass 3 = `gmail.compose`. **Legacy auth retirement:** once broker is active, `gcal_credentials.json` and `gcal_token.json` paths in `chief_calendar_brain.py` become dead code and must be removed — dual-path Google auth must not persist. The broker checks only `.google-secrets/token.json`; if old files exist on disk the broker logs a warning and ignores them. **Gitignore model:** `.gitignore` is an allowlist (`*` blocks everything; `!file` entries permit tracking). Secrets are already blocked. New source files including broker modules need explicit `!` entries added to `.gitignore` when created or they will not be tracked.
- **Approval gate depends on Telegram.** `chief_approval_brain.py` sends via Telegram and polls for YES/NO. If the bot is down (401 error), the gate times out and auto-denies. When Telegram is broken, the gate is non-functional — fix the bot before any automated destructive operations.
- **WSL vhdx moved to E: (completed 2026-03-19).** The Ubuntu virtual disk now lives at `E:\WSL\Ubuntu\ext4.vhdx` (~51 GB). Moved via `wsl --manage Ubuntu --move E:\WSL\Ubuntu`. The old `C:\Users\Open Claw\AppData\Local\Packages\CanonicalGroupLimited.Ubuntu_79rhkp1fndgsc\LocalState\` is no longer the active vhdx location. Any cleanup of old package-path remnants on C: is deferred for later manual review from Windows — do not delete from WSL.
- **DISM requires true Windows elevation.** Cannot be triggered from WSL PowerShell — register-scheduledtask and RunAs both fail without an interactive elevated session. Run DISM manually from an Administrator PowerShell on Windows.
- **cleanmgr StateFlags registry writes require elevation.** Silent failures from WSL mean cleanmgr runs in default mode, not with configured categories.
- **Claude `--print` mode with piped stdin blocks all write tools (fixed 2026-03-30).** When claude CLI receives a prompt via stdin pipe in `--print` mode, it enters "don't ask" permission mode — all file-write tools (Edit, Write, Bash) are silently blocked. The builder produces analysis text but writes no files, exiting 0. Fix: always use `--dangerously-skip-permissions` alongside `--print` for any piped/autonomous execution. Both `builder_watcher.sh` and `run_polish_pass.sh` must include this flag.
- **Builder processes get SIGSTOP from nohup terminals (fixed 2026-03-30).** When `builder_watcher.sh` runs via `nohup &`, child processes (claude) receive SIGSTOP and freeze. `pgrep` still finds them, so `builder_running()` reports them as alive — the orchestrator never times them out. Fix: (a) `setsid` wrapper in builder_watcher creates new session for the child, (b) `builder_running()` reads `/proc/{pid}/status` to detect `T (stopped)` state and treats those PIDs as dead.
- **Contact-gated behavior must be enforced at the listener boundary, not only inside the brain (fixed 2026-03-31).** If a feature is meant to apply only to designated external contacts, the Telegram listener must admit those senders explicitly. Brain-level contact checks alone are insufficient because the listener may still hard-block every non-owner message, leaving the feature unreachable in production.

---

## Observer Role and State Machine (added 2026-03-23 by Architecture Lock Pass)

### Observer

The Observer is a passive diagnostic role. It reads loop state files and reports mismatches. It does NOT:
- Modify status.json
- Write task.md, pc_output.md, or mac_review.md
- Advance, approve, reject, or close any task
- Make decisions about task priority or assignment

The Observer MAY:
- Flag a task as blocked (by reporting to Planner, who then updates status.json)
- Generate observer_packet.md in the handoff folder
- Report mismatches between files and status.json

Observer script: `/home/openclaw/observer.sh`
Observer output: `/mnt/c/OpenClawShared/OpenClaw-Handoff/observer_packet.md`

### State Machine Reference

Canonical state machine: `/home/openclaw/STATE_MACHINE.md`

Valid states: idle, in_progress, awaiting_verification, approved, needs_rework, blocked

All transitions, forbidden transitions, and evidence requirements are defined in STATE_MACHINE.md. That file is the single source of truth for loop state rules.

### Access Rules

1. **Builder may not read or write status.json** except to flip `in_progress` -> `awaiting_verification` after writing pc_output.md.
2. **Planner may not touch task.md** after handing it to Builder. If the spec needs revision, Planner must issue `needs_rework` via mac_review.md and let Builder re-enter `in_progress`.
3. **No task advances without a corresponding Logbook entry.** The transition `approved -> idle` requires a Logbook entry in `Eyes/06_Logbook.md` before the loop resets.
4. **mac_review.md must reference the current task.** A stale review from a prior task is not valid evidence for any transition. Observer will flag task-name mismatches.
5. **One active task per pair.** No stacking of awaiting_verification states. If the current task is not closed, the next task cannot begin.
