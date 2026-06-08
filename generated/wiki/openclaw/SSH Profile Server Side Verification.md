# SSH Profile Server Side Verification

Status: `SSH_PROFILE_SERVER_SIDE_VERIFICATION_READY`

Verified at: `2026-06-08T15:15:10-04:00`

## Short Answer

`openclaw` is the canonical SSH route for Codex Desktop backend work on the PC.

`hp` resolves to the same route as `openclaw`, so it is a duplicate alias.

`openclaw-pc` resolves to Windows OpenSSH on port 22 as Windows user `openclawssh`. It is not the WSL `/home/openclaw` route and should not be used for Codex Linux commands.

## Evidence

- WSL user is `openclaw`.
- WSL home/repo is `/home/openclaw`.
- WSL shell has `/usr/bin/bash`.
- Port `2222` on Windows is handled by IP Helper portproxy and forwards to WSL `172.28.194.117:22`.
- WSL `ssh.service` is active and listening on port `22`.
- Windows OpenSSH `sshd` is separately running on port `22`.
- Windows user `openclawssh` exists; WSL user `openclawssh` does not.
- Prior `openclaw-pc` failure showed Windows shell behavior: `sh` and `[` were not recognized.

## Profile Classification

| Profile | Mac target | Environment | Codex backend use | Recommendation |
|---|---|---|---|---|
| `openclaw` | `openclaw@192.168.50.205:2222` | WSL OpenClaw backend | Yes | Keep as canonical |
| `hp` | `openclaw@192.168.50.205:2222` | Duplicate of `openclaw` | Yes | Optional duplicate cleanup |
| `openclaw-pc` | `openclawssh@192.168.50.205:22` | Windows SSH shell | No | Disable/ignore first, delete later only if no Windows admin workflow needs it |

## Recommended Next Action

Use `openclaw` for Codex Desktop PC backend work.

Do not delete users or keys. Disable or ignore `openclaw-pc` in Mac Codex first. Remove it later only after confirming no Windows-side workflow depends on the `openclawssh` Windows account over port 22.

Retest from Mac with:

```bash
ssh openclaw 'whoami; hostname; pwd; command -v bash; cd /home/openclaw && git status --short'
```
