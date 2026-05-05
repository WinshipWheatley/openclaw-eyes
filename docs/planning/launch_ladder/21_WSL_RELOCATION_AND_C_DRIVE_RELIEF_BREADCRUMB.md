# WSL Relocation And C Drive Relief Breadcrumb

Status: docs-only breadcrumb for completed WSL relocation / C-drive relief work. This file records verified outcomes and audit breadcrumbs. It is not execution authority.

## 1. Purpose

Capture the completed PC WSL relocation and bounded `C:` relief work so future OpenClaw planning does not have to reconstruct what happened from memory.

This breadcrumb preserves:

- where active WSL/OpenClaw now lives;
- which rollback artifact exists;
- what was verified after relocation;
- what `C:` audit findings explained the remaining pressure;
- what cleanup is not authorized by this record.

## 2. Final Verified State

- Windows `C:` was critically full before the storage relief work.
- WSL/OpenClaw was exported from old Ubuntu to `E:\WSL_Backup\Ubuntu-before-move.tar`.
- The backup tar exists at `E:\WSL_Backup\Ubuntu-before-move.tar` and is `176.55 GB`.
- The new active WSL distro is `Ubuntu-E`.
- The active WSL VHDX exists at `E:\WSL_Distros\Ubuntu-E\ext4.vhdx` and is `180.45 GB`.
- `Ubuntu-E` is now the default WSL distro.
- `Ubuntu-E` opens as user `openclaw`.
- `/home/openclaw` exists and `git status` works.
- Repo status was verified as `main...origin/main [ahead 16]`, with untracked `docs/_ai/runtime_snapshot.md`.
- Old `Ubuntu` no longer appears in `wsl --list --verbose`.
- `C:` free space after relief was `22.18 GB`.
- `E:` free space after relocation/import was `258.14 GB`.

## 3. What Changed

- Active WSL/OpenClaw moved from the old `Ubuntu` distro to `Ubuntu-E`.
- Active WSL storage moved to `E:\WSL_Distros\Ubuntu-E\ext4.vhdx`.
- A temporary rollback export was created at `E:\WSL_Backup\Ubuntu-before-move.tar`.
- `Ubuntu-E` became the default WSL distro.
- Some `C:` headroom was recovered by clearing old-user temp residue from `C:\Users\Open Claw\AppData\Local\Temp`.

## 4. What Did Not Change

- This breadcrumb does not record any change to OpenClaw runtime/services.
- This breadcrumb does not record any provider/model call.
- This breadcrumb does not record any secrets inspection or private-content review.
- This breadcrumb does not record any Windows drive reformatting.
- This breadcrumb does not record any approval to continue cleaning caches, downloads, application data, package folders, or developer toolchains.

## 5. Active Runtime vs Rollback Backup

Active runtime:

- `Ubuntu-E`
- `E:\WSL_Distros\Ubuntu-E\ext4.vhdx`
- `/home/openclaw`

Rollback backup:

- `E:\WSL_Backup\Ubuntu-before-move.tar`
- Size: `176.55 GB`
- Purpose: temporary rollback copy from before the move.

The backup tar is not active runtime. It should not be deleted immediately. Revisit it only after one or two normal OpenClaw sessions confirm that `Ubuntu-E` is stable.

`E:\WSL_Distros\Ubuntu-E` is the active WSL/OpenClaw install location. It is a hard do-not-touch runtime path.

## 6. C Drive Findings

The expected `180 GB` recovery from unregistering old Ubuntu did not appear on `C:`. Actual `C:` pressure was largely elsewhere.

Windows users observed during the audit:

- `C:\Users\Open Claw`
- `C:\Users\openclawssh`
- `C:\Users\openclawssh.DESKTOP-HP`
- `C:\Users\Winship`
- `C:\Users\Public`

`ext4.vhdx` was not found under `C:\Users` during search.

Biggest user-profile findings:

- `C:\Users\Open Claw\AppData` around `25.83 GB`.
- `C:\Users\Winship\AppData` around `20 GB`.
- `C:\Users\Winship\Downloads` around `5.47 GB`.
- `C:\Users\Open Claw\.rustup` around `2.38 GB`.
- `C:\Users\Open Claw\.cargo` around `1.09 GB`.

Biggest `AppData\Local` findings:

- `C:\Users\Open Claw\AppData\Local\Temp` around `15.39 GB`.
- `C:\Users\Open Claw\AppData\Local\Google` around `5.59 GB`.
- `C:\Users\Open Claw\AppData\Local\Microsoft` around `1.6 GB`.
- `C:\Users\Winship\AppData\Local\Google` around `6.49 GB`.
- `C:\Users\Winship\AppData\Local\Packages` around `1.78 GB`.
- `C:\Users\Winship\AppData\Local\Microsoft` around `1.74 GB`.

`C:\Users\Open Claw\AppData\Local\Temp` contained temp/build/install residue including Visual Studio Build Tools logs, Rust temp folders, WinGet, `msedge` BITS temp items, `WSLDVCPlugin`, and `asio_sdk.zip`.

Cleanup was bounded to that temp target. Some locked temp file access-denied residue may remain.

## 7. Remaining Cleanup Candidates

These areas were observed as storage-pressure candidates, but they are not approved cleanup targets from this breadcrumb:

- `C:\Users\Open Claw\AppData\Local\Google`
- `C:\Users\Open Claw\AppData\Local\Microsoft`
- `C:\Users\Winship\AppData\Local\Google`
- `C:\Users\Winship\AppData\Local\Packages`
- `C:\Users\Winship\AppData\Local\Microsoft`
- `C:\Users\Open Claw\.rustup`
- `C:\Users\Open Claw\.cargo`
- `C:\Users\Winship\Downloads`

Each candidate requires separate review before cleanup, movement, cache clearing, uninstall, archival, or deletion.

## 8. Hard Do-Not-Touch Items

- Do not delete `E:\WSL_Distros\Ubuntu-E`.
- Do not delete `E:\WSL_Distros\Ubuntu-E\ext4.vhdx`.
- Do not unregister `Ubuntu-E`.
- Do not delete `E:\WSL_Backup\Ubuntu-before-move.tar` immediately.
- Do not treat the rollback tar as active runtime.
- Do not clean remaining Google, Microsoft, Packages, `.rustup`, `.cargo`, or Downloads paths without separate approval.
- Do not inspect private/sensitive content as part of storage cleanup.
- Do not touch secrets, vaults, provider credentials, Gmail, cloud drives, LegalPrivate, or runtime state.
- Do not run broad filesystem scans from this breadcrumb.

## 9. Recommended Next Safe Actions

- Use `Ubuntu-E` normally for one or two OpenClaw sessions.
- After normal use, verify that `Ubuntu-E` still opens as `openclaw`, `/home/openclaw` is present, and repo status works.
- Revisit whether to keep or remove `E:\WSL_Backup\Ubuntu-before-move.tar` only after stability is established and the operator explicitly approves that decision.
- Keep `C:` cleanup candidates as a separate planning/review lane.
- If future cleanup is needed, start with path/size inventory and operator-readable scope, not content inspection.

## 10. Commands/Outputs Worth Remembering

Recorded outputs worth preserving:

```text
wsl --list --verbose
Old Ubuntu no longer appears.
Ubuntu-E is present and default.
```

```text
Ubuntu-E opens as user openclaw.
/home/openclaw exists.
git status works.
```

```text
Repo status:
main...origin/main [ahead 16]
Untracked: docs/_ai/runtime_snapshot.md
```

```text
Backup tar:
E:\WSL_Backup\Ubuntu-before-move.tar
176.55 GB
```

```text
Active WSL VHDX:
E:\WSL_Distros\Ubuntu-E\ext4.vhdx
180.45 GB
```

```text
Post-relief free space:
C: 22.18 GB free
E: 258.14 GB free
```

## 11. What This Does Not Authorize

This breadcrumb does not authorize:

- WSL distro movement, import, export, unregister, rename, default switching, or VHDX changes;
- deletion of the rollback tar;
- deletion of active WSL runtime files;
- additional Windows cleanup;
- cache clearing;
- package/toolchain cleanup;
- Downloads cleanup;
- app data cleanup;
- Windows file edits;
- OpenClaw runtime/service changes;
- provider/model calls;
- private-data inspection;
- secrets handling;
- broad filesystem scans.

Any future operational step needs a separate bounded packet, current evidence, explicit operator approval, and its own validation path.
