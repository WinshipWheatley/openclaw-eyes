# AGY-Gemini Audit Task — E: drive cleanup + incoming 2TB USB-C plan (2026-06-22)

Operator-requested (Winship). Master Orchestrator (PC Claude) authored this.
You are AGY-Gemini, the READ-ONLY auditor. Produce a recommendation + manifest.
**You do NOT delete or move anything.** Destructive actions are Hard-T2: they execute
ONLY after Winship approves the specific manifest, and reversibly where possible
(move-and-verify before any delete). This rule is non-negotiable — a wrong delete here
is unrecoverable.

## The problem
E: (932 GB) is **100% full**. This risks breaking the OpenClaw read-model imports and WSL.
Observed top-level usage (du -d1):
- `WSL_Distros` 328 GB   (the live WSL distributions — KEEP, but see note)
- `WSL_Backup` 177 GB    (operator thinks this is now EXCESSIVE — evaluate hard)
- `Ableton` 141 GB       (his Ableton projects/packs — creative work, treat carefully)
- `XboxGames` 92 GB + `PGA Tour` 57 GB  (games ≈ 149 GB — prime move-to-2TB candidates)
- `OpenClaw_Quarantine` 56 GB  (what is it? safe to purge? classify)
- `.openclaw_sensitive_no_go` 28 GB  (**DO NOT READ OR TOUCH — explicit no-go**)
- plus the orchestration board, MSOCache, SteamLibrary, etc.

## Incoming hardware
- A **2 TB USB-C drive** will be plugged into the PC (the Thunderbolt drive is Mac-only and
  cannot connect to the PC). Winship will first get everything off the 2TB drive and likely
  REFORMAT it. Recommend the best target layout for it.
- Operator's leaning: games + backups likely live on the 2TB drive. You decide the best split.

## Deliverable — a structured MANIFEST (Winship approves line-by-line)
For every significant item on E:, produce a row:
`path | size | classification | reason (first-principles) | risk | reversible? | target (delete / move→2TB / keep-on-E)`
Classifications: **SAFE-DELETE**, **MOVE-TO-2TB**, **KEEP-ON-E**, **NEEDS-OPERATOR-DECISION**.
Then a short PLAN: the order of operations to get E: to a healthy free %, what the 2TB layout
should be (and why), and what stays on E: (the project/orchestration drive should NOT share
space with WSL backups + games — first-principles studio-master reasoning).

## Specific questions to answer
1. Is `WSL_Backup` (177 GB) redundant given the live `WSL_Distros`? If it's a stale/duplicate
   backup, it's the single biggest safe win — but verify it's not the only copy of anything.
2. What is `OpenClaw_Quarantine` (56 GB) — purgeable, or does it hold anything needed?
3. Confirm games (XboxGames, PGA, SteamLibrary) are relocatable to the 2TB without breakage.
4. Target free-space % for E: after cleanup (recommend a healthy headroom, not 0%).

## Bonus design question (operator raised it)
AI generally prefers FLAT folder structures; humans prefer NESTED. As you audit, flag where a
folder structure is **for-AI**, **for-humans**, or **in-between**, and recommend how each should
be treated/navigated. This feeds the broader "system knows what's on all drives" goal.

## Hard constraints
- READ-ONLY audit. No deletes, no moves, no writes outside your own report.
- Never read/scan `.openclaw_sensitive_no_go`, secrets, `.chief.env`, tokens, or credentials.
- Don't deep-scan private media content — classify by path/size/structure, not by reading files.
- Output the manifest + plan back to the board for Winship's approval; the Master Orchestrator
  will sequence the approved, reversible execution (move→verify→delete) under a gate.
