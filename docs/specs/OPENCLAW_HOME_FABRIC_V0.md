# OpenClaw Home Fabric v0

Status: agent-drafted spec in the collaborative `docs/specs/` lane. Review required. Not runtime law.

Generated: 2026-09-01 from tracked evidence only. No machine was probed to write this.

Stale when: a node, SSH route, share path, or transport changes. Refresh from
`bash scripts/home_fabric_check.sh` output before trusting any row below.

`OPENCLAW_RUNTIME.md` ("Cross-System Communication") points at
`orchestration/CROSS_SYSTEM_FABRIC.md` on the shared drive, which is not tracked.
This file is the tracked map of what connects the machines today, the weak points
that evidence already shows, and a staged hardening path. Promotion into
`docs/operations/` is an operator decision.

## 1. Nodes

| Node | Identity | Role | Evidence |
|---|---|---|---|
| `pc` | `DESKTOP-HP`, Windows 10, WSL2 `Ubuntu-E`, user `openclaw`, `/home/openclaw`; i7-6700, ~27 GiB RAM, GTX 1660 Ti; LAN `192.168.50.205`; WSL `172.28.x.x` (changes on reboot) | canonical backend: systemd user stack, Ollama, Gmail broker, tokens in `.chief.env` | `docs/planning/launch_ladder/20_DEPLOYMENT_TOPOLOGY_NODE_PORTABILITY_AND_OS_AGNOSTICISM.md`; `generated/wiki/openclaw/SSH Profile Server Side Verification.md` |
| `mac` | `Hs-MBP-2.local`, M1 Pro 16 GB, macOS 26.4; `~/Developer/OpenClawBackend/openclaw` (backend clone), `~/OpenClaw_Watch` (mirror), `~/Eyes`, Mission Control Xcode app | operator surface, review mirror, native app build, Struna Mac port | same audit; `launchd/com.openclaw.read-model-sync.plist` |
| E: share | Windows `E:\openclaw` = WSL `/mnt/e/openclaw` = Mac `/Volumes/openclaw_e` | file shuttle (markers + manifests), Windows tasks, logs | `docs/operations/OPENCLAW_READ_MODEL_MIRROR_AUTOMATION_V0.md` |
| phone | Telegram listeners (Cassandra, Chief, Guardian, Maestro) | operator channel and approvals | `systemd/user/*.service.in` |
| planned | `home-server.local`, Mac Studio, laptop, iPad | registered as non-active | `openclaw_estate_node_registry.py` |

## 2. Transports as built

| Leg | Mechanism | Notes |
|---|---|---|
| PC to Mac | `ssh mac` (alias in `~/.ssh/config`, key `~/.ssh/id_mac`) plus rsync | `mac_eyes/Launchers/sync_to_mac.sh` every 30 s; `scripts/sync_project_packets_to_mac.sh`; `loop_supervisor.sh` liveness probe |
| Mac to PC | `ssh openclaw` = `openclaw@192.168.50.205:2222`, then Windows IP Helper portproxy `0.0.0.0:2222 -> 172.28.194.117:22`, then WSL sshd | `hp` is a duplicate alias; `openclaw-pc` reaches Windows OpenSSH on :22 as `openclawssh` and is not the backend |
| PC and Mac files | E: share markers `shuttle/to_mac/read_model_sync_required.json`, `shuttle/from_mac/read_model_sync_completed.json`, `shuttle/from_mac/read_model_sync_agent_status.json` | Mac LaunchAgent every 300 s; Windows task `OpenClawReadModelImport` every 1 min; `scripts/build_sync_health.py` grades trust |
| Models | Ollama on `127.0.0.1:11434` (PC) | six local models inventoried 2026-05-09; loopback only |
| Voice | `kokoro-voice.service` (PC) | loopback only |
| Remote access | Tailscale account exists since 2026-08-10 | no script or doc in the repo references it yet |

## 3. Weak points backed by evidence

1. Dynamic WSL address versus a static portproxy. Every reboot silently breaks Mac to PC SSH until someone re-runs `netsh`. Shipped fix: `scripts/windows_wsl_portproxy_resync.ps1` (use `-InstallTask` to run it at logon).
2. Hard-coded LAN address `192.168.50.205` in the Mac SSH config. DHCP can move it. Runtime law already says "hostname, not IP", but mDNS does not resolve from inside WSL.
3. An unmounted SMB share on the Mac stalls the whole read-model bridge (`bridge_manual_mount_recovery_packet.py`, `bridge_trust_sync_truth.py`).
4. Two SSH servers on the PC: WSL sshd behind 2222 and Windows OpenSSH on 22 with a separate `openclawssh` account. The Windows one is unused by the backend and is extra attack surface.
5. PC sleep. `openclaw-sleep-resilience.service` exists because the box sleeps and services need re-kicking.
6. Windows 10 host. WSL mirrored networking needs Windows 11, so WSL services can never be reached from the LAN without a portproxy.
7. `openclaw-eyes` is a public GitHub repository that carries client, invoice, and legal-matter context. Nothing in the fabric protects that; only repository visibility does.
8. Tests mutate tracked `generated/read_models/*` in place during a full run, which is why the green gate must clean-room every ref.

## 4. Three approaches

A. Keep LAN plus portproxy; add the resync task and the fabric check. Smallest change. Still LAN-only, still address-fragile, still two sshd instances.

B. Tailscale on Windows and Mac only. Stable `100.x` PC address, MagicDNS, works away from home. WSL stays behind the portproxy, so the resync task remains load-bearing.

C. Tailscale as its own node inside WSL2 (plus Windows and Mac), Tailscale SSH, MagicDNS names. Retires the portproxy, the LAN address, the key files, and the Windows OpenSSH exposure; tailnet ACLs decide who may SSH. Costs: `tailscaled` must run inside WSL (systemd is already enabled there), an MTU 1280 quirk for large transfers, one more node in the tailnet.

Recommendation: C, staged so nothing breaks in between.

1. Today, on Windows: `windows_wsl_portproxy_resync.ps1 -InstallTask`. On WSL: `bash scripts/home_fabric_check.sh`, and keep it as the first diagnostic.
2. Install Tailscale on Windows (`winget install tailscale.tailscale`), on the Mac (App Store or `brew install --cask tailscale`), and in WSL (`curl -fsSL https://tailscale.com/install.sh | sh`, then `sudo tailscale up --ssh --hostname pc-wsl`). Enable MagicDNS and Tailscale SSH in the admin console. ACL: only Winship's own devices may SSH.
3. Add aliases without removing the old ones. Mac: `Host openclaw` with `HostName pc-wsl`. WSL: `Host mac` with the Mac's MagicDNS name. `home_fabric_check.sh` reports both routes.
4. After a week of green checks: delete the 2222 portproxy and its firewall rule, stop Windows OpenSSH if no Windows-side workflow needs it, and remove `192.168.50.205` from every SSH config.
5. Optional: move the read-model shuttle from SMB markers to rsync over Tailscale SSH, or auto-mount the share on the Mac with `autofs` so the LaunchAgent never reports `share_missing`.

## 5. Bind policy

- Every OpenClaw gateway binds `127.0.0.1` (Ollama, Hermes, kokoro, request-response). Only sshd listens on all interfaces inside WSL. `home_fabric_check.sh` warns about anything else.
- Struna Obscura on Windows binds OSC to `127.0.0.1:9000` by default. Set `osc_bind` to the PC's Tailscale address to drive it from WSL (Niles) or the Mac; see `docs/network_control.md` in the Struna repo.
- Tokens stay in `.chief.env` on the PC. The vault wall in `OPENCLAW_RUNTIME.md` is unchanged.

## 6. Commands

WSL, one-screen fabric health:

```bash
bash scripts/home_fabric_check.sh            # add --strict to exit 1 on any FAIL
```

Windows, elevated PowerShell, fix the Mac to PC route now and at every logon:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "\\wsl.localhost\Ubuntu-E\home\openclaw\scripts\windows_wsl_portproxy_resync.ps1" -InstallTask
```

Mac, share and agent sanity:

```bash
ls /Volumes/openclaw_e/shuttle/from_mac && launchctl list | grep com.openclaw.read-model-sync
```

## 7. Boundaries

The check script is read-only. Nothing in this spec adds runtime, send, submit, or approval authority. No secrets are recorded here.
