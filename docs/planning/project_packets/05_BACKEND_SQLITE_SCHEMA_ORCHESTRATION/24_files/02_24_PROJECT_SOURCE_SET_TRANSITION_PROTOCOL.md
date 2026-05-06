# Project Source-Set Transition Protocol

Status: phase-orchestration doctrine for ChatGPT Project folders, Codex/Gemini lanes, and OpenClaw source-set transitions.

Purpose: Every serious OpenClaw Project folder should be able to produce the next Project folder without reinventing handoff process.

## 1. Core Idea

Each ChatGPT Project folder represents one coherent OpenClaw work cycle.

The Project source-set is a phase-scoped orchestration packet, not permanent memory.

The active Project helps a new chat understand:

- the phase;
- why it matters;
- what is built, current, next, and after-next;
- what is forbidden;
- where Codex/Gemini should look;
- how to decide the next slice;
- when to prepare the next source-set.

## 2. Roles

ChatGPT Project is the orchestration cockpit. It carries:

- North Star;
- steel thread;
- doctrine;
- phase contracts;
- active handoff;
- repo-truth snapshot;
- validation map;
- source-set boundaries;
- allowed/forbidden lanes;
- transition criteria;
- map of granular repo instructions.

It should not carry every tactical code file unless those files are repeatedly needed for orchestration.

Codex and Gemini are tactical workers reading granular repo files directly from `/home/openclaw` when prompts explicitly name those files.

They receive:

- exact task;
- allowed paths;
- forbidden paths and tools;
- validation commands;
- report requirements.

They should not rely on broad project memory, stale handoffs, or hidden assumptions.

## 3. The 24-File Rule

A serious Project packet usually contains about 24 files.

The packet is phase-defining, not exhaustive.

Good packet members include:

- active handoff;
- repo-truth snapshot;
- North Star/doctrine;
- semantic contracts;
- current implementation/readiness plans;
- validation map;
- source-set manifest;
- index/navigation docs;
- transition protocol.

Bad packet members include:

- every code file;
- every test file;
- stale docs with no current role;
- runtime logs;
- private data;
- secrets;
- scratch notes;
- duplicate docs.

## 3A. The Juice Test

The packet should be bird's-eye and high-yield.

Each file earns its place by helping new chats make orchestration decisions repeatedly.

A file belongs if it answers:

- what are we building;
- why it matters;
- what has been decided;
- what is allowed;
- what is forbidden;
- where Codex/Gemini should look;
- how the phase is done;
- when to prepare the next 24.

A file usually does not belong if it is needed only for one tactical patch, one test, one code change, or historical curiosity.

Tactical files should be named in Codex/Gemini prompts, not preloaded.

The 24-file packet should feel like a big juicy piece of fruit: concentrated enough that a new chat can squeeze real guidance from it, but not so overloaded that the juice is buried in rind.

## 4. Active Handoff Rule

Use one active handoff file. Recommended name: `00_ACTIVE_HANDOFF.md`.

It must say:

- repo HEAD/latest commit;
- cleared verdict;
- next lane;
- forbidden lanes;
- which Project files are current or historical;
- what new chats do first;
- what Codex/Gemini receive next.

Update the handoff when chat context gets long, then generate the next-chat prompt.

## 5. Repo Truth Rule

Each major phase has a repo-truth file from `/home/openclaw`.

It must include:

- git status;
- commits;
- validation results;
- durable files;
- cleared verdict;
- allowed paths;
- forbidden paths and tools;
- stale or superseded notes.

Terminal truth wins.

## 6. When To Start Preparing The Next 24 Files

Start preparing the next 24-file packet when:

- the phase objective is mostly complete;
- new work depends on outside docs;
- chats spend more time explaining context;
- Codex/Gemini need a different source-set;
- the handoff is mostly transition notes;
- several files are stale;
- the next lane has a different center of gravity.

Prepare before the phase gets messy.

## 7. How To Build The Next 24-File Source-Set

The current Project creates:

- updated `00_ACTIVE_HANDOFF.md`;
- new repo-truth snapshot;
- candidate list;
- classification as Current, Required, Historical, Superseded, Reference only, or Excluded;
- final 24;
- prompt for the first new Project chat.

The new Project starts with:

- active handoff;
- repo-truth file;
- curated 24-file set;
- first-chat prompt.

## 8. Transition Standard

The transition is ready when the operator can create a Project folder, add 24 files, start a chat, paste the prompt, and continue without re-explaining.

## 9. Staleness Control

Old files are not deleted casually.

Mark old files as historical, superseded, archive, reference, or not active authority.

Retired means not active authority. It does not mean deleted.

## 10. Source Authority Order

1. current terminal truth from `/home/openclaw`
2. current repo-truth snapshot
3. active handoff
4. current phase contracts/plans
5. indexes/manifests
6. older handoffs
7. historical Project files
8. chat memory

## 11. Folder Structure Principle

OpenClaw should become readable top-down for humans and machines.

Structure should show:

- built/current/next/after-next;
- canonical/archive/runtime/private/non-canonical;
- granular Codex/Gemini instructions;
- orchestration Project context.

Do not reorganize the repo casually while the data-contract/SQLite substrate is forming.

Better sequence:

1. finish enough SQLite/schema substrate;
2. use the substrate to map existing artifacts;
3. create snapshots;
4. propose top-down structure;
5. move small reversible batches;
6. validate;
7. update substrate/indexes;
8. keep rollback.

The SQLite/schema substrate helps future map/cleanup.

## 12. Mac Mirror vs PC Canonical Repo

The Mac mirror is for review, Project packet prep, visual organization, and handoff drafting.

PC WSL `/home/openclaw` is canonical for build truth.

Do not infer repo truth from Mac screenshots.

PC terminal, Git, static checks, and tests are authority.

## 12A. Mirror Packet Rule

For Projects, the Mac mirror is often the easiest upload/review surface.

Direction: PC canonical repo truth -> Mac mirror / Project upload packet.

The Mac mirror may contain clean copies of handoffs, repo-truth snapshots, and curated 24-file packets.

The Mac mirror is for human review, ChatGPT Project upload, visual organization, and active handoff drafting.

The Mac mirror is not canonical build authority.

Do not silently promote Mac-side edits back. Use an explicit PC-side promotion task with destination, validation, and commit plan.

Duplication is acceptable when labeled one-way. It is dangerous when both sides are edited as equally authoritative.

## 12B. Active Agent Message Queue Rule

When an agent is already working, do not assume a new message modifies the current task.

Treat it as a queued next instruction unless the tool supports interruption.

Preferred pattern:

- let the agent finish;
- review output;
- send a follow-up patch;
- ask the agent not to redo broad analysis unless needed.

This prevents mid-task collisions.

## 13. Snapshot And Move Discipline

Before repo-side reorganization:

- run `git status`;
- inventory paths;
- write a planning note;
- establish a rollback point;
- move one coherent batch;
- run tests;
- inspect diffs;
- commit only if clean.

No broad cleanup.

No "while here" moves.

Folder cleanup is a build lane.

Do not reorganize Mac/PC just because the surface is noisy. First classify noise as:

- canonical repo;
- generated/runtime residue;
- mirror/reference;
- stale handoff;
- private/sensitive;
- upload packet;
- tactical work product.

## 14. Anti-Slop Rules

Do not carry files forward just because they were useful once.

Do not make the Project a junk drawer.

Do not let old source sets authorize new work.

Do not let tactical files overload orchestration.

Do not replace repo artifacts with hidden memory.

Handoffs must preserve decisions, paths, gates, and verdicts.

Do not let the Mac mirror blur canonical authority.

Do not interrupt active agents with mid-task context unless intended and supported.

## 15. Ideal Project Lifecycle

1. Start with 24 files.
2. Chats orchestrate.
3. Codex/Gemini do exact granular repo work.
4. Update active handoff when long.
5. Continue while source-set is valid.
6. Plan next source-set before stale.
7. Generate next 24.
8. Start next Project.
9. Archive/retire old Project.

## 16. Success Criteria

The protocol is working when:

- new chats start fast;
- Codex prompts are exact-path bounded;
- old context is available but not accidentally authoritative;
- phase transitions are boring and repeatable;
- the operator does not re-explain OpenClaw;
- the system builds from the North Star, not tool-churn.
