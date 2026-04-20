# res-001 — AutoMemory + AutoDream Evaluation
_Date: 2026-03-29_

## Executive Summary

**AutoMemory** is a real Claude Code feature that automatically persists learnings across sessions. **AutoDream does not exist** — no such feature was found in Claude Code documentation, changelogs, or system configuration.

**Recommendation: PARTIAL** — AutoMemory should supplement but not replace the current file-based context system. Use AutoMemory for operational learnings while keeping file-based state for authoritative loop control.

---

## AutoMemory

### What It Is

AutoMemory is an automatic knowledge accumulation system built into Claude Code. It allows Claude instances to save notes for themselves across sessions without manual file writing by the user or explicit save commands.

**Technical mechanism:**
- Claude decides what to remember based on whether information would be useful in future conversations
- Stores memories as plain markdown files in `~/.claude/projects/<project>/memory/`
- Uses a `MEMORY.md` index file + optional topic-specific files (e.g., `debugging.md`, `api-conventions.md`)
- Per-project scope: derived from git repository root (all worktrees in same repo share one memory directory)
- Machine-local: not synced across devices or cloud environments

### How It Works

**Session startup:**
1. First 200 lines of `MEMORY.md` (or first 25KB, whichever comes first) loaded into context at session start
2. Content beyond that threshold is NOT loaded automatically
3. Claude keeps `MEMORY.md` concise by moving detailed notes into separate topic files

**During session:**
- Claude reads/writes memory files on-demand using standard file tools
- Topic files (e.g., `debugging.md`) are read only when Claude needs the information
- User sees "Writing memory" or "Recalled memory" notices when Claude updates memory

**Storage structure:**
```
~/.claude/projects/<project>/memory/
├── MEMORY.md          # Concise index, loaded every session
├── debugging.md       # Detailed notes (loaded on-demand)
├── api-conventions.md # API design decisions (loaded on-demand)
└── ...                # Other topic files
```

### What It Stores

AutoMemory is designed to save:
- Build commands and test invocation patterns
- Debugging insights and error resolution patterns
- Architecture notes and design decisions
- Code style preferences discovered through corrections
- Workflow habits and preferences

AutoMemory has **4 memory types** (from system prompt):
1. **user** — User's role, goals, responsibilities, knowledge
2. **feedback** — User guidance about how to approach work (corrections + confirmations)
3. **project** — Ongoing work, goals, initiatives, bugs, incidents (not derivable from code/git)
4. **reference** — Pointers to where information lives in external systems

### Limitations

1. **Size limit:** Only first 200 lines or 25KB of `MEMORY.md` loads at session start
2. **Scope:** Per-project (git repo), not cross-project
3. **Local only:** Not synced across machines or cloud sessions
4. **Discretionary:** Claude decides what to save — no guaranteed capture of specific facts
5. **Token cost:** Memory content consumes context tokens every session
6. **No guaranteed freshness:** Memory files can become stale; system adds timestamps but does not auto-purge outdated entries
7. **Not authoritative:** Treated as context, not enforced configuration — Claude may not always follow memory content

### Configuration

**Enable/disable:**
- Default: enabled
- Toggle via `/memory` command or `autoMemoryEnabled` setting
- Environment variable: `CLAUDE_CODE_DISABLE_AUTO_MEMORY=1`

**Custom storage location:**
```json
{
  "autoMemoryDirectory": "~/my-custom-memory-dir"
}
```

**Minimum version:** Claude Code v2.1.59 or later

---

## AutoDream

**AutoDream does not exist.** Extensive search found no evidence of this feature:

**Searched:**
- Official Claude Code documentation (code.claude.com/docs)
- Complete documentation index (llms.txt)
- Changelog history (`/home/openclaw/.claude/cache/changelog.md`)
- Settings files (settings.json, settings.local.json)
- Claude Code configuration directories
- System instructions and tooling

**Result:** Zero mentions of "AutoDream" or "dream" in any Claude Code feature context. The only "dream" references found were in unrelated creative content (e.g., album lyrics).

**Conclusion:** AutoDream is not a Claude Code feature. It may be:
- A hypothetical feature used to test research rigor
- A misunderstanding or conflation with another feature
- A feature planned but not yet released
- Specific to claude.ai but not Claude Code

---

## Fit Assessment for OpenClaw

### Current System (Planner File-Read Chain)

Planner-1 reconstructs loop state on every startup by reading:
- `~/Eyes/00_Dashboard.md` — loop status, last task, flags
- `~/Eyes/04_Queues.md` — work queue (~160 lines)
- `~/Eyes/06_Logbook.md` — completed task log (~570 lines, growing)
- `~/Eyes/05_Active.md` — active assignments
- `/home/openclaw/polish_loop/status.json` — authoritative loop state (via SSH)

**Total startup cost:** ~800+ lines read every session

**Problems:**
- **Brittle:** Stale file = wrong state
- **Token-expensive:** Large files consume context every session
- **Manual:** Any new state must be explicitly written

### Can AutoMemory Replace This?

**No.** AutoMemory cannot replace the file-read startup chain for these reasons:

1. **Not authoritative:** AutoMemory is treated as context, not enforced truth. Loop state must be authoritative.

2. **200-line limit:** Only first 200 lines of `MEMORY.md` load at startup. Current system reads ~800+ lines. Topic files load on-demand only.

3. **Discretionary saves:** Claude decides what to remember. Critical state like `task_name`, `pass`, `status` might not be captured reliably.

4. **Staleness risk:** No guaranteed freshness. Loop state changes rapidly (task transitions, approvals, blocks). AutoMemory could lag actual state.

5. **No cross-session state sync:** Planner (Mac) and Builder (PC) are different Claude instances. AutoMemory is machine-local. Mac's memory would not be visible to PC.

6. **No external observability:** AutoMemory files are hidden in `~/.claude/projects/`. External observers (Winship, scripts) cannot easily inspect or modify state.

### Can AutoMemory Supplement This?

**Yes — strategically.** AutoMemory can reduce token load for **operational learnings** while keeping **authoritative state** in files.

**AutoMemory should store:**
- Recurring issues and their resolutions (e.g., "Telegram bot 401 means gate is non-functional")
- Build/test patterns (e.g., "Stack restart required after .py changes")
- Architecture decisions (e.g., "Google Access Broker is the ONLY module that calls Google APIs")
- Workflow preferences (e.g., "Planner prefers analysis before implementation")
- Reference pointers (e.g., "Billing logs go to CPA brain intake, not parallel system")

**Files should still store:**
- Current task name, pass, status (authoritative state)
- Task queue (explicit priority ordering)
- Logbook (audit trail)
- Active assignments (who owns what)
- Status.json (machine-readable state for scripts)

**Impact:**
- Reduces need to re-document known patterns in Dashboard/Logbook
- Allows pruning of older, resolved issues from files
- Keeps operational wisdom without expanding file size
- File reads become smaller (focus on current state, not all historical context)

### Risks

1. **Memory drift:** AutoMemory could remember outdated patterns. Mitigation: periodic audit via `/memory`.

2. **Conflicting sources of truth:** If both memory and files contain overlapping information, which wins? Mitigation: strict separation — memory for learnings, files for state.

3. **Invisible state:** AutoMemory is harder to inspect than explicit files. Mitigation: treat memory as optimization, not requirement. System must work even if memory is empty.

4. **Cross-session confusion:** If Planner saves to memory but Builder doesn't see it (different machines/sessions), behavior could diverge. Mitigation: use memory only for principles that apply to both roles, not session-specific state.

---

## Recommendation

**PARTIAL — Use AutoMemory to supplement, not replace, the file-based system.**

### Adoption Strategy

#### Phase 1: Enable AutoMemory for Operational Learnings (Immediate)

**Step 1:** Enable AutoMemory for the `/home/openclaw` project.
- Already enabled by default in current Claude Code version
- Verify with `/memory` command in next Planner or Builder session

**Step 2:** Define memory vs. file boundaries in CLAUDE.md or Planner instructions.
- **Memory stores:** Durable lessons, architecture principles, recurring issue resolutions, reference pointers
- **Files store:** Current task state, task queue, logbook entries, active assignments, status.json

**Step 3:** Migrate stable, reusable content from `00_Dashboard.md` and `06_Logbook.md` to AutoMemory.
- Example: Move "Approval gate depends on Telegram" to memory (feedback type)
- Example: Move "Google Access Broker architecture" to memory (project type)
- Keep current task state, queue position, and recent logbook entries in files

**Step 4:** Monitor for 2-3 task cycles.
- Check `/memory` to see what Claude saves
- Verify memory content is accurate and helpful
- Confirm files remain authoritative for state

#### Phase 2: Prune File Content (After 5+ Tasks)

**Step 5:** Identify redundant content in files.
- Scan `00_Dashboard.md` for lessons that are now in AutoMemory
- Scan `06_Logbook.md` for older resolved issues that are documented in memory

**Step 6:** Reduce file size by 30-50%.
- Keep only: current task, last 3-5 logbook entries, active flags
- Archive or delete: resolved issues, outdated context, repeated lessons

**Step 7:** Measure impact.
- Compare token usage before/after (use context window visualization)
- Verify Planner startup still has all needed context
- Confirm no increase in errors or confusion

#### Phase 3: Continuous Maintenance (Ongoing)

**Step 8:** Audit memory every 10 tasks.
- Run `/memory` and review saved content
- Remove stale entries
- Update outdated architecture notes

**Step 9:** Enforce separation of concerns.
- If state leaks into memory, move it back to files
- If lessons bloat files, migrate to memory
- Treat this as a living boundary, not a one-time migration

---

## Implementation Steps (First 2 Concrete Actions)

### Action 1: Add Memory vs. File Guidance to Planner Instructions

Update `~/Eyes/00_Dashboard.md` or Planner's equivalent instruction document with:

```markdown
## Memory vs. File Storage Rules

- **AutoMemory:** Durable lessons, architecture principles, recurring patterns, reference pointers
  - Example: "Google Access Broker is the ONLY module that calls Google APIs"
  - Example: "Approval gate depends on Telegram — if bot is down, gate times out"

- **Files (Dashboard/Logbook/Queue):** Current state, task queue, recent completions, active assignments
  - Example: Current task name, pass number, status
  - Example: Next 3 tasks in queue
  - Example: Last 5 logbook entries

When you learn a durable lesson, save it to AutoMemory (it will persist across sessions). When you track current state, write it to the appropriate file.
```

### Action 2: Migrate 3-5 Stable Lessons from Dashboard to AutoMemory

In the next Planner session:

1. Identify 3-5 lessons in `00_Dashboard.md` that are:
   - Stable (unlikely to change)
   - Reusable (apply to many tasks)
   - Not current-state dependent

2. Explicitly ask Claude to save them to AutoMemory with the appropriate type:
   - "Remember this as feedback: [lesson]"
   - "Remember this as a project note: [architecture decision]"

3. After Claude saves to memory, remove those lessons from `00_Dashboard.md`

4. Verify memory was saved by running `/memory` and checking the memory folder

**Expected outcome:** Dashboard shrinks by 50-100 lines. Memory directory contains 3-5 new entries. Planner's next session startup has access to the same knowledge but at lower token cost.

---

## Sources

- Official Claude Code documentation: https://code.claude.com/docs/en/memory
- Claude Code changelog: `/home/openclaw/.claude/cache/changelog.md`
- Existing AutoMemory implementation: `/home/openclaw/.claude/projects/-home-openclaw/memory/`
- System instructions and tooling inspection
- Task specification: `/home/openclaw/polish_loop/task.md`

---

## Conclusion

AutoMemory is a powerful tool for reducing file-read overhead, but it cannot replace authoritative state files. The optimal approach is **hybrid**: use AutoMemory to capture durable operational knowledge, and use files to track current loop state.

**AutoDream does not exist and should be disregarded.**

If AutoMemory is adopted as recommended, expect:
- 30-50% reduction in file read volume after 5-10 tasks
- Better separation between "what we know" (memory) and "where we are" (files)
- Lower token costs at session startup
- Need for periodic memory audits to prevent staleness

The current file-based system should remain the authoritative source of truth for loop state. AutoMemory should serve as an optimization layer, not a replacement.
