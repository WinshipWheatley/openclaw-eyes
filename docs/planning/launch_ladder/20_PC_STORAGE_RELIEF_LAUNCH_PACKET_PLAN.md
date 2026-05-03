# PC Storage Relief Launch Packet Plan

Status: docs/test-only planning. This launch packet is not execution authority.

## 1. Purpose

Define an operator-approved, reversible plan for relieving the PC `C:` storage crisis and preparing for a future WSL relocation. This is a launch-packet plan for storage relief, not cleanup execution, file movement, WSL export/import, drive reformatting, `.wslconfig` editing, runtime mutation, source-set generation, or private-data review.

All commands in this document are inert future command examples only. They are not executed in this slice and require explicit operator approval before execution.

## 2. Current Evidence

- PC `C:` is critically full: 246G total, 244G used, about 2.5G available, 99% full.
- PC `D:` has 229G total, 103G used, and 127G available.
- PC `E:` has 932G total, 521G used, and 412G available.
- WSL root reports 1007G total, 190G used, and 767G available.
- The WSL VHD on `C:` appears to be the largest `C:` pressure source, roughly 190GB.
- Cleanup candidates identified: WSL pip cache `~/.cache/pip` around 7.2GB, WSL npm cache `~/.npm/_cacache` around 2.7GB, Gemini tmp `~/.gemini/tmp/openclaw` around 1.8GB, OpenClaw backup `~/.openclaw/plugin-runtime-deps.bak-20260426-203717` around 582MB, Windows Downloads around 5.5GB, and Chrome cache around 6.6GB.
- Windows/WSL feasibility audit: Intel i7-6700, 6th gen Skylake, 4C/8T; 32GB RAM total.
- Windows 11 official eligibility is unlikely or unsupported because Windows 11 officially requires 8th gen Intel or newer.
- Current `C:\Users\Open Claw\.wslconfig`:

```ini
[wsl2]
memory=28GB
swap=8GB
processors=8
```

- Current WSL memory allocation leaves only about 4GB for Windows and may contribute to system pressure.
- WSL relocation from `C:` to `E:` appears feasible, but must be done carefully.
- Critical risk: with only about 2.5GB free on `C:`, running `wsl --export` without an explicit `E:` destination may fail or crash.
- Windows interop from WSL showed timeouts; relocation commands should be planned for Windows Terminal/PowerShell, not inside WSL.
- Candidate post-relocation memory cap: reduce WSL memory to 24GB to leave Windows about 8GB.
- A separate external 2TB drive has remaining data that must be triaged before it can become a cross-PC/Mac backup drive.
- Mac audit findings include an 8TB BU external nearly full, Orange/Green external drives, sensitive tax paths, and candidate source `/Volumes/8TB BU/Winship/Other/Old Buisness plans`; Mac drives are out of scope for this PC storage relief packet.

## 3. Risk Posture

- `C:` at 99% is a system stability risk. Windows updates, browser caches, WSL growth, temp usage, and swap/pagefile pressure can fail when free space is this low.
- WSL VHD relocation is likely the largest relief path, but it is also the highest-risk operation because export/import/unregister mistakes can affect the primary working distro.
- Cache cleanup is lower risk and should come before WSL export/import so the machine has more breathing room.
- Windows 11 upgrade should not be attempted during the storage crisis.
- Windows 11 official support is unlikely on the i7-6700; any bypass upgrade is a separate future risk review and is not part of this packet.

## 4. No-Touch Zones

This packet does not authorize inspection, cleanup, movement, export, upload, sync, or model access for:

- tax/CPA/legal/client/private data
- `C:\OpenClawLegalPrivate`
- Mac drives and Mac external drives
- 8TB BU
- Orange/Green
- 2TB external drive contents until triaged
- cloud drives
- secrets/vaults/logs/runtime state
- OpenClaw runtime mutation surfaces, including approvals, tasks, memory, sessions, exec-policy, Guardian, Hermes, Telegram, and Gmail

## 5. Phase 0: Backup/Verification Before Any Change

Plan only. Before any future cleanup or relocation:

- Verify repo status with `git status -sb --untracked-files=all`.
- Record current WSL distro list from Windows Terminal/PowerShell:

```powershell
wsl --list --verbose
```

- Record `.wslconfig`:

```powershell
Get-Content "$env:USERPROFILE\.wslconfig"
```

- Record disk usage:

```powershell
Get-PSDrive -PSProvider FileSystem
```

```bash
df -h /
```

- Identify the backup destination before any destructive or relocation step.
- Verify `E:` has enough space for both export tar and imported distro staging.
- Verify whether the 2TB bridge drive can become a backup target only after its current data is inventoried by path/size and anything important is preserved.
- Do not proceed if backup destination is unclear.

## 6. Phase 1: Low-Risk Immediate Relief Packet

Plan commands only. These proposed future commands are not executed in this slice and require explicit operator approval before execution.

Proposed WSL cache cleanup examples:

```bash
python3 -m pip cache purge
npm cache clean --force
```

Optional Gemini tmp cleanup may be considered only after confirming no needed session outputs are inside `~/.gemini/tmp/openclaw`. The future command example is:

```bash
rm -rf ~/.gemini/tmp/openclaw
```

Windows Downloads should be handled by manual review only. Do not bulk-delete Downloads from a command. Chrome cache should be cleared through browser settings, not by deleting profile files directly:

```text
chrome://settings/clearBrowserData
```

Future verification commands after any approved cleanup:

```bash
df -h /
du -sh ~/.cache/pip ~/.npm/_cacache ~/.gemini/tmp/openclaw 2>/dev/null || true
```

```powershell
Get-PSDrive -PSProvider FileSystem
```

## 7. Phase 2: WSL Export/Import Relocation Packet

Plan only. This is not executed in this slice. Every export/import/default-switch/removal step requires explicit operator approval before execution.

- Run relocation commands from Windows Terminal/PowerShell, not inside WSL.
- Shut down WSL before export.
- Export the existing `openclaw` distro to an explicit `E:` destination such as `E:\WSL_Backup\openclaw.tar`.
- Import to an explicit `E:` install location such as `E:\WSL\openclaw`.
- Verify the imported distro before changing defaults.
- Do not unregister the original distro until the imported distro is verified and the operator explicitly approves old distro removal.
- Update default distro only after verification.
- Final cleanup of the old distro/VHD happens only after explicit approval.
- The `E:` destination should not be compressed or encrypted.
- Account for low `C:` space and possible temp usage during export. If export appears to stage temp files on `C:`, stop and reassess.

Future command examples:

```powershell
wsl --shutdown
New-Item -ItemType Directory -Force E:\WSL_Backup, E:\WSL
wsl --export openclaw E:\WSL_Backup\openclaw.tar
wsl --import openclaw-e E:\WSL\openclaw E:\WSL_Backup\openclaw.tar
wsl --list --verbose
wsl -d openclaw-e -- uname -a
wsl -d openclaw-e -- df -h /
wsl --set-default openclaw-e
```

Rollback strategy:

- If export fails, keep the original distro untouched and return to Phase 1/Phase 0 space checks.
- If import fails, keep the export tar if valid, keep the original distro untouched, and retry only after identifying the failure cause.
- If the imported distro does not behave like the original, keep the original default and do not unregister anything.
- If the old distro must remain, preserve it and reassess `C:` relief options before any removal.

## 8. Phase 3: .wslconfig Memory Policy

Plan only. Do not change `.wslconfig` until after storage relief and any relocation verification.

- Current setting: `memory=28GB`, `swap=8GB`, `processors=8`.
- Proposed later setting: `memory=24GB` to leave Windows about 8GB.
- Keep `swap=8GB` and `processors=8` unchanged unless a separate future performance review says otherwise.
- After any future approved change, verify inside WSL with:

```bash
free -h
```

- Also verify Windows behavior with Task Manager after WSL restart.

## 9. Phase 4: External 2TB Bridge Drive Triage

Plan only. Do not move, delete, or reformat the 2TB drive in this packet.

- Inventory remaining data by path/size only.
- Do not open sensitive contents.
- Decide what must be preserved.
- Find a temporary holding location with enough space.
- Copy and verify preserved data before deletion is considered.
- Reformat only after explicit operator approval.
- Recommended future format should support PC and Mac backup workflows. `exFAT` is a broad-compatibility candidate, but final filesystem choice is deferred until reliability and backup needs are reviewed.

## 10. Phase 5: Sensitive Data Relocation Later

Plan only. No sensitive-data moves happen in this storage relief packet.

- Taxes/CPA/legal/music-law/publishing data should move later to protected local-only storage boundaries.
- Local models only by default for sensitive-data workflows.
- Cloud models may only receive sanitized/tokenized data in a future separate high-security design lane.
- No tax, CPA, legal, client, publishing, cloud-drive, vault, secret, or private document content should be inspected during this packet.

## 11. Verification Checklist

After Phase 0 future verification:

- `git status -sb --untracked-files=all` recorded.
- `wsl --list --verbose` recorded.
- `.wslconfig` recorded.
- `Get-PSDrive -PSProvider FileSystem` recorded.
- `df -h /` recorded.
- Backup destination identified and confirmed, or the packet stops.

After Phase 1 future approved cleanup:

- `df -h /` shows WSL free space after cleanup.
- `Get-PSDrive -PSProvider FileSystem` shows `C:`, `D:`, and `E:` free space after cleanup.
- Relevant cache paths are rechecked by size.
- No no-touch zones were inspected or changed.

After Phase 2 future approved relocation:

- `wsl --list --verbose` shows original and imported distros as expected.
- Imported distro starts successfully.
- Imported distro shows expected filesystem capacity with `df -h /`.
- Repo opens from the imported distro if that is part of the approved verification.
- Original distro remains available until old distro removal is separately approved.

After Phase 3 future approved memory-policy change:

- `.wslconfig` reflects the approved memory cap.
- `free -h` confirms WSL memory after restart.
- Windows Task Manager confirms Windows has more available headroom.

After Phase 4 future approved 2TB triage:

- Inventory by path/size exists.
- Preserve list is explicit.
- Temporary holding location is selected.
- Copy verification is complete before deletion or reformat is considered.

After Phase 5 future sensitive-data relocation:

- Local-only boundary is documented.
- Sanitization/tokenization rules are documented before any cloud-model access.
- No cloud model received raw sensitive data.

## 12. Operator Approval Gates

Separate approval is required for:

- approve cache cleanup
- approve WSL export
- approve WSL import
- approve default distro switch
- approve old distro removal
- approve 2TB drive triage
- approve 2TB reformat
- approve sensitive data relocation

Approval for one gate does not imply approval for any later gate.

## 13. Failure/Rollback Plan

- If export fails: stop, keep original distro untouched, record the error, and reassess `C:` free space and destination path.
- If import fails: keep original distro untouched, keep the export tar if it appears complete, and retry only after diagnosing the import failure.
- If Windows interop hangs: stop WSL-side interop attempts and use Windows Terminal/PowerShell directly.
- If `E:` space becomes insufficient: stop before import or reformat, identify another backup destination, and do not proceed.
- If old distro must remain: preserve it and defer old VHD cleanup until a later explicit approval.
- If cache cleanup removes needed session artifacts: stop additional cleanup, record what was removed, check available backups or session outputs, and avoid optional temp cleanup in future packets until the operator reviews the loss.

## 14. Recommended Next Move

Recommended next move: after operator approval, execute only Phase 1 low-risk cache cleanup first, then reassess `C:` free space before planning WSL relocation execution.

Do not attempt Windows 11 upgrade, WSL relocation, old distro removal, 2TB reformatting, sensitive-data movement, private-content inspection, source-set `05` generation, or OpenClaw runtime mutation as part of the immediate next move.
