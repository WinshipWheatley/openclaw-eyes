# Niles X32 OSC controller (branch `pc-suborch/niles-x32-osc`)

Stdlib-only OSC control of a Behringer X32 for Niles. Built test-first by the PC sub-orch (Codex credits out → Opus built it). **Branch-only; not merged/deployed.**

## Files
- `osc_codec.py` — OSC 1.0 encode/decode (UDP wire format).
- `niles_x32.py` — `NilesX32` controller: name/color/source, fader, **IEM/monitor sends**, **headamp gain+48V** (local + DL16/stagebox over AES50, via `resolve_headamp`), **scene `.scn` streaming**, **read-back `verify()`**.
- `x32_fake.py` — UDP X32 fake (test double; X32 set/query semantics). Swap for **Maillot's X32 emulator** or a real console (`console_ip:10023`) — same interface.
- `test_osc_codec.py`, `test_niles_x32.py` — fast unit tests (no hardware).

## Run (fast — ~0.2s, NOT the 39-min green_gate)
```
cd worktrees/niles-x32 && python3 -m unittest test_osc_codec test_niles_x32
```
14 tests, all green.

## Point at real hardware / emulator
```python
from niles_x32 import NilesX32
n = NilesX32("192.168.50.XX", 10023)   # or the emulator's IP
n.set_channel_name(1, "Kick"); n.set_channel_color(1, "RD")
assert n.verify("/ch/01/config/name", ["Kick"])   # evidence, not say-so
```

## Proven vs TODO (for codex integration)
- PROVEN: codec round-trip, name/color/fader/send, headamp resolver+gain/phantom, scene streaming, read-back verify — against the fake.
- TODO (codex, when credits return): validate against **Maillot's emulator** then a live console; `/xremote` subscribe loop for live state/metering; full `.scn` value-type fidelity (display-string ↔ OSC float normalization); wire into the OpenClaw agent registry + the process/scene store (see `_pc-suborch-room/NILES-X32-ARCHITECTURE-AND-STORAGE.md`); HITL/approval gating on every outward op.
