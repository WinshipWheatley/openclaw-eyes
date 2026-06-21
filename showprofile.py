"""Email/stage-plot input-list -> X32 show profile (.scn).

The inspiration feature: an incoming stage plot / input list becomes a loadable
X32 scene (channels named + color-coded by instrument), ready to stream onto the
desk via niles_x32.NilesX32.load_scene or load from a thumb drive.

Deterministic prototype: parses cleanly-numbered lists. Messy real-world emails
get an LLM-assisted parse upstream (Niles interpretation) — out of scope here.
"""
import re

# instrument keyword -> (category, X32 color code, icon). Order = priority.
_CATEGORIES = [
    ("drums", "RD", ["kick", "snare", "tom", "hat", "overhead", " oh", "oh ", "ride", "crash", "drum", "kit", "perc"]),
    ("bass", "BL", ["bass", "808", " sub", "upright"]),
    ("guitar", "GN", ["gtr", "guitar", "git", "acoustic", "electric", "banjo", "mando"]),
    ("keys", "YEi", ["key", "synth", "piano", "organ", "rhodes", "nord", "wurli", "keys"]),
    ("vox", "WH", ["vox", "vocal", "bgv", "sing", " mic", "talkback"]),
]
_DEFAULT = ("other", "CY", 1)

_LINE = re.compile(r"^\s*(?:ch\s*)?(\d+)\s*[-.):]?\s*(\S.*?)\s*$", re.IGNORECASE)


def categorize(name):
    low = " " + name.lower() + " "
    for category, color, kws in _CATEGORIES:
        if any(k in low for k in kws):
            return (category, color, 1)
    return _DEFAULT


def parse_input_list(text):
    """Parse numbered input-list lines into channel dicts. Skips headers/blanks."""
    chans = []
    for line in text.splitlines():
        m = _LINE.match(line)
        if not m:
            continue
        ch = int(m.group(1))
        name = m.group(2).strip()
        if not name:
            continue
        category, color, _icon = categorize(name)
        chans.append({"ch": ch, "name": name, "category": category, "color": color})
    return chans


def build_scene(channels, scene_name="Auto Show"):
    """Emit a minimal valid X32 .scn from channel dicts."""
    name16 = scene_name[:16]
    out = [f'#4.0# "{name16}" "" %000000000 1']
    for c in channels:
        color = c.get("color") or categorize(c["name"])[1]
        out.append(f'/ch/{c["ch"]:02d}/config "{c["name"]}" 1 {color} {c["ch"]}')
    return "\n".join(out) + "\n"
