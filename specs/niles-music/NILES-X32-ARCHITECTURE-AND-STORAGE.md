# NILES — X32 control architecture + process/storage design (durable)
_Author: PC sub-orch, 2026-06-20. Pairs with `NILES-X32-CONTROL-CAPABILITY.md`. Answers Winship's "store the important processes so Niles can respond to requests and control the 2 racks + DL16." For the master to promote into `specs/niles-music/` and assign as a codex build when credits return (build + verify against the X32 emulator — do NOT hand-build untested)._

## 1. What Niles needs to STORE (the model)
Five durable stores. Keep them deterministic; Niles reads them, the deterministic layer validates, Niles acts.

**a) Rack registry** — one record per console:
`{ rack_id: "big"|"little", model: "X32", role: "FOH"|"monitors", console_ip, port: 10023, aes50: {A: <peer/stagebox>, B: <...>}, state: "up"|"down"|"unknown", last_seen }`
(Winship has 2 racks; **one is DOWN** — state is first-class so Niles never assumes both controllable.)

**b) Control-path config** — the 4 paths from the OSC/Niles relay, with the decision rule:
`pc_direct` (PC→console:10023, **preferred**) · `pc_app` (drive X32-Edit GUI — only if a human needs the GUI AND PC resources free) · `mac_direct` · `mac_app`.
Rule: **direct OSC by default; the app is never required for control** (proven). Niles picks path by {which machine has the route, is the rack up, resources}.

**c) Scene/snippet library** — index of his real corpus (PC `*.scn` + the 60 Mac scenes in `artifacts/x32-mac-show-profiles-…`) tagged by purpose: `live-monitor`, `tracking-from-stage`, `push-to-PC`, `big-rack`, `little-rack`. Canonical defaults: richest = `Hilton Save date.scn`; 2-rack = Big/Little Tree House. Each entry: path, rack, purpose, sha256, key routing summary.

**d) channel→headamp resolver** — derived map `(rack, channel) → /headamp/NNN` (000-031 local, 032-079 AES50-A incl. DL16, 080-127 AES50-B), computed from `/config/routing` + `/ch/XX/config/source`. Required because gain/48V live at `/headamp`, not `/ch`.

**e) Process registry** — named, replayable procedures Niles invokes from a request, each = a validated OSC sequence + scope:
e.g. `build_iem_mix(performer, bus)`, `recall_vocal_chain(ch)` (`/load libchan …` scoped), `set_monitors_5piece`, `swap_config(big↔little / push-to-PC)`, `name_color_channels(map)`. Each carries: required rack-state, OSC ops, expected read-back, approval scope.

## 2. Niles OSC controller (codex build spec)
A small module (Python suggested) Niles calls:
- **Socket:** ONE UDP socket → `(console_ip, 10023)`, replies on same socket.
- **send(addr, *args)** command + `/node` string forms; float params normalized 0–1.
- **subscribe loop:** `/xremote` every ~9 s; parse surface/meter changes into Niles's world-model.
- **load_scene(.scn):** stream the file's lines as OSC (the DIY load path) with pacing + read-back verify.
- **ramp(addr, target, ms):** synthesize smooth fades (stepped values — no native OSC fade).
- **resolve_headamp(rack, ch):** uses store (d).
- **verify(addr, expected):** read-back confirmation (anti-snow-globe — every "I changed X" carries tool-returned evidence, per the fleet Evidence/Truth contract).
**Test target:** Maillot **X32 emulator** (no hardware, up to 4 clients) → then a live rack. Build is GREEN only when proven against the emulator with read-back.

## 3. AES50 monitor profile (his rig) — stored as a process
6 stereo IEM mixes via mix-bus pairs and/or **P16/Ultranet**; per-performer = `/ch/XX/mix/<bus>` (pre-fader). 5-piece+engineer (own wireless) = 6 stereo sends; 6-piece → engineer on **X32 phones** (`/config/solo`). DL16 stage inputs on AES50-A; Niles sets their gain/48V via `/headamp` 032-079. Physical (cables, packs, the down rack) = human; everything logical = Niles.

## 4. Deferred feature sketches (for orch + codex; Winship's post-X32 asks)
**A) Email stage-plot → auto show-profile** (the inspiration): mail watcher → detect stage-plot/input-list emails → parse (instrument→input map, mic list) → fill a channel-config + naming/color + routing **template** → emit a `.scn` (reuse store c + the `.scn` writer) → stage for load (thumb-drive / app / OSC-stream). HITL-gated; deterministic parse + Niles interpretation.
**B) Niles as engineer + producer — splits into two domains:**
- **Engineer (LIVE):** the X32 stack in this doc (monitors/FOH).
- **Producer (STUDIO / the album):** **a separate subsystem** — control is the **DAW**, not the X32. His chain is stage/X32 → PC → DAW (Ableton/Logic/Reaper per his Audio Software folder + "push channels to PC for processing" scenes). Niles-as-producer needs DAW integration: **Ableton Live API / Reaper OSC+ReaScript** are automatable; **Logic** is limited. Recommend the orch scope this as its own "Niles studio/production" lane — the X32 emulator/OSC work does NOT cover it.

## 5. Bounds
X32/DAW control = **gated, audit-logged, approval-gated, never autonomous**; SEND_HOLD absolute; no money; read-back evidence on every change; rack-state respected. Test on emulator before any live/hardware action.
