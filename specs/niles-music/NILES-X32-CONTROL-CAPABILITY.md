# NILES ↔ X32 CONTROL — capability map, limits, monitor design (durable)
_Author: PC sub-orch. 2026-06-20. Consolidation of: capability research (5-agent), Winship's real `.scn` corpus (PC + 60 Mac scenes), the PC X32-Edit install, and the offline test scenes. **For the master to promote into the Niles subsystem spec (`specs/niles-music/`).** PC Codex-desktop GUI verification was aborted (Codex credits) — noted where it would have added empirical proof._

## 0. STATUS (what's proven vs pending)
- ✅ **X32-Edit 4.4.0 installed on PC** (was 4.1), verified by SHA256; old 4.1 removed.
- ✅ **Control model proven by file evidence**: a `.scn` scene file **is a literal flat list of OSC messages** — the same address tree Niles sends live. So anything in a scene is OSC-settable.
- ✅ **Offline authoring proven**: I generated `Downloads/NILES-X32-TESTS/TEST-NILES-A/B.scn` (renamed/recolored channels) from the Big Rack template.
- ✅ **Mac scene corpus captured**: 60 real `.scn` copied to `artifacts/x32-mac-show-profiles-20260620T215737Z/` (+ manifest, checksums).
- ⏳ **Live OSC round-trip NOT yet exercised**: no X32 reachable on the LAN (one rack down; none connected). **Use Maillot's X32 emulator to test with zero hardware** (see §3).
- ⏳ **GUI-only items unverified empirically** (PC Codex-desktop aborted) — theory below is from protocol + his scenes.

## 1. CAPABILITY MATRIX — what Niles CAN / CAN'T do
**Wire protocol:** OSC 1.0 over UDP, **port 10023** (X32) / 10024 (X-Air). Multiple clients allowed (Niles + app + surface coexist). Niles does **NOT** need X32-Edit open — OSC goes straight to `console_ip:10023`. Live floats are normalized 0.0–1.0; `.scn` uses display strings.

### FULLY OSC-ADDRESSABLE (Niles automates directly)
| Capability | Address | Notes |
|---|---|---|
| **Channel name / color / icon / source** | `/ch/XX/config` (+ `/name /color /icon /source`) | Winship's core ask — 100% yes; 16 colors incl. inverted; 32 ch + 8 aux + 8 fxrtn |
| **EQ / gate / dynamics / insert / delay** | `/ch/XX/eq|gate|dyn|insert|delay` | full per-band PEQ, comp, gate |
| Mute / fader / pan | `/ch/XX/mix` | |
| **Monitor/IEM sends** (per performer mix) | `/ch/XX/mix/YY` (level + pre/post tap) | the heart of IEM mixing — fully automatable |
| **Routing blocks** (whole-console reconfig) | `/config/routing/{IN,AES50A,AES50B,CARD,OUT,PLAY}` | switch "tracking-from-stage" ↔ "push-to-PC" in one move |
| **User patchbay** (virtual patch points) | `/config/userrout/in|out` | down to the individual point |
| **Preamp gain + 48V** — local AND on **DL16/S16/DL32 over AES50** | `/headamp/000-127` | THE remote-engineer win. Needs a channel→headamp-index resolver (slots 000-031 local, 032-079 AES50-A, 080-127 AES50-B) |
| Output routing incl. **P16/Ultranet (IEM)** | `/outputs/main/*`, `/outputs/p16/*` | build/label/route all 16 IEM channels |
| Monitor/phones bus | `/config/solo/*` (level/source/dim/mono/PFL/AFL) | use `/config/solo/level` instead of the front-panel Phones knob |
| Buses / matrix / DCA / groups | `/bus/* /mtx/* /dca/* /config/*link` | |
| Scenes / snippets / channel-presets / cues | `/-action/goscene|gosnippet|gocue`, `/load libchan…` | snippet & libchan scope is settable per call |
| Clock slave to AES50 | `/-prefs/clocksource` | |

### CONSTRAINED (yes, but with hard rules)
- **FX: 8 engines total.** `/fx/X/type|source|par`. **Reverbs/delays/mod only in slots 1–4**; slots 5–8 = EQ/dynamics/utility only. Niles must respect slot constraints.
- **AES50: PARTIAL.** All *logical* patching is OSC. **NOT OSC:** plugging the cable, the stagebox's front-panel A/B switch, "did the box enumerate." Workaround: verify presence via `/headamp` read-back; physical = human-on-stage.
- **Loading a `.scn`: 3 paths** — (a) USB thumb-drive [human/surface], (b) X32-Edit Load [GUI], (c) **OSC stream the lines** [Niles, DIY — works]. Niles uses (c).
- **Smooth fades** aren't a native OSC primitive — Niles synthesizes by stepping values over time.

### CANNOT over OSC — the real limitation (your "user visual presets")
- **"Show only channels X, Y, Z" custom views = GUI/SURFACE-ONLY.** X32 FW 4.x has **no** user-definable channel-set / custom-fader-layer object and **no** OSC address to hide/show channels per view. Surface visibility = fixed banks + bank-switching only.
- **Practical workaround:** Niles can't make visual "preset views," but it CAN deliver the *intent* via **scene/snippet recall** + **naming/color conventions** for visual grouping (your scenes already do this: drums RD, guitars GN, keys YEi, vox WH/MG). For a human at the surface, the layer is theirs; for Niles-driven shows the "view" is moot (Niles acts on channel addresses directly).

## 2. AES50 MONITOR DESIGN — your rig (2 racks, DL16, 6 stereo IEMs, 5/6-pc band)
- **Topology:** Monitor rack ↔ FOH/main rack linked over **AES50** (48 ch each direction). Stage inputs via **DL16 on AES50-A** (its 16 preamps are in the `/headamp` 032-079 range — Niles sets gain/48V remotely). One rack is **DOWN** → model rack-state; don't assume both controllable.
- **6 stereo IEM mixes:** build 6 stereo **mix-bus pairs** (or drive **P16/Ultranet** — 16 ch = 8 stereo, covers 6). Per-performer mix = `/ch/XX/mix/<bus>` sends (pre-fader for monitors). Niles labels them (`IEM 1 L/R` … your scenes already use this) and balances each.
- **5-piece band + monitor engineer (own wireless stereo IEM):** 5 performer IEM mixes + the engineer's = 6 stereo sends → IEM transmitters / P16.
- **6-piece fallback:** monitor engineer uses the **X32 headphone out** → driven by `/config/solo` monitor bus (Niles sets source/level there).
- **What's Niles vs human:** Niles = all mix levels, sends, routing, naming, gain/48V (incl. DL16), recall. Human = plug cables, power racks, fix the down rack, don wireless packs.

## 3. HOW NILES CONNECTS (integration recipe)
1. One UDP socket → `(console_ip, 10023)`; read replies on the **same** socket.
2. `/xremote` every ~9 s for live state/metering; parse surface changes into Niles's world-model.
3. Push params as OSC; load scenes by streaming the `.scn` lines.
4. **No-hardware testing: Maillot X32 Emulator** — point `console_ip` at it (up to 4 clients, full command coverage, zero risk). **This is how we validate Niles's OSC control NOW without a live rack.** Promote to the real console when one's up.
5. Resource rule (your ask): X32-Edit app **not required** — Niles controls the console directly; only open the app if a human wants the GUI and resources allow.

## 4. YOUR REAL RIG — reference scenes (for Niles's defaults)
- Richest current routing: **`Hilton Save date.scn`** (AES50A+B, populated userrout, P16, named bus pairs: Drum/Guitar/Key/Vox + Matrix/Loop). Newest (`Capitol Hilton.scn`) is sparser — diff the trio incl. `Win Pre Sea Salt.scn`.
- 2-rack model: **`Big Tree House Rig` / `Little Tree House rig` (All working)** — show the Big/Little racks exchanging CARD/AES50/user-out/P16. Little rack has explicit stem buses (Drums/Instruments/Vocals/ReAmp/Metronome).
- Color conventions to preserve: drums RD, guitars GN, keys/electronic YEi, vocals WH/MG, FX MGi, DAW/Mac lanes grouped.
- Corpus: `artifacts/x32-mac-show-profiles-20260620T215737Z/` (60 scenes + manifest) + PC `/mnt/c/Users/Winship/*.scn`.

## 5. ARTIFACTS CREATED THIS PASS
- PC: X32-Edit 4.4.0 (Desktop + `Downloads/X32-Edit_PC_4.4`); old 4.1 removed.
- Test scenes: `Downloads/NILES-X32-TESTS/TEST-NILES-A.scn`, `TEST-NILES-B.scn`.
- Mac corpus copied to the shared board (above).

## 6. NEXT (for the orchestrator to make durable)
- **Niles OSC store:** per-rack profile (Big/Little), rack-state (up/down), the 4 control paths (PC-app / PC-direct / Mac-app / Mac-direct), a scene/snippet library keyed to his real corpus, and the channel→headamp resolver.
- **Validate via the X32 emulator** before any live rack (closes the unproven live round-trip).
- **Deferred planning (queued with orchestrator):** (a) email stage-plot → auto show-profile backend; (b) **Niles as engineer + producer** for band work + finishing the album.
- **PC Codex-desktop GUI verification**: re-run when Codex credits return — only needed to empirically confirm the §1 "CANNOT/GUI" items + the file→app load.
