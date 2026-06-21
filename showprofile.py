"""Email/stage-plot input-list -> X32 show profile (.scn).

Each channel gets: NAME (parsed) + COLOR (standard, aligned to Winship's scenes:
drums RD, bass BL, guitar GN, keys YEi, vox WH) + a proper X32 ICON (canonical
1-74 table). Output is a loadable .scn (stream via NilesX32.load_scene or USB).

Deterministic prototype: parses cleanly-numbered lists. Messy real-world emails
get an LLM-assisted parse upstream (Niles interpretation) — out of scope here.
"""
import re

# Ordered (category, color, icon, [keywords]); first match wins. Icons = canonical X32 table.
_RULES = [
    ("drums", "RD", 2,  ["kick", "bass drum", " bd "]),
    ("drums", "RD", 4,  ["snare top", "sn top", "sntop"]),
    ("drums", "RD", 5,  ["snare bottom", "snare bot", "sn bot", "snbot"]),
    ("drums", "RD", 4,  ["snare", " sn "]),
    ("drums", "RD", 9,  ["hi hat", "hihat", " hat", "charley", " hh "]),
    ("drums", "RD", 10, ["crash", "ride", "cymbal"]),
    ("drums", "RD", 11, ["overhead", "ohl", "ohr", " oh "]),
    ("drums", "RD", 8,  ["floor tom", "rack tom", "tom"]),
    ("drums", "RD", 13, ["conga", "bongo", "perc", "tamb", "shaker"]),
    ("drums", "RD", 11, ["drum", "kit"]),
    ("bass",  "BL", 17, ["bass", "808", " sub"]),
    ("bass",  "BL", 18, ["upright", "acou bass", "double bass"]),
    ("guitar", "GN", 23, ["acoustic", "acou guit", "ac gtr", "acou gtr"]),
    ("guitar", "GN", 24, ["amp", " cab"]),
    ("guitar", "GN", 20, ["gtr", "guitar", "git", "strat", "tele", "les paul"]),
    ("keys",  "YEi", 27, ["piano", "grand"]),
    ("keys",  "YEi", 28, ["organ", "hammond", "b3", "leslie"]),
    ("keys",  "YEi", 29, ["rhodes", "wurli", "nord", "elec key", "electric piano", "keys", "key"]),
    ("keys",  "YEi", 31, ["synth", "moog", "prophet", " pad", "analog"]),
    ("horns", "YE", 37,  ["sax", "saxophone"]),
    ("horns", "YE", 35,  ["trumpet", "horn", "brass"]),
    ("horns", "YE", 36,  ["trombone", "bone"]),
    ("strings", "YE", 39, ["violin", "fiddle", "viola"]),
    ("vox",   "MG", 42,  ["female", "fem vox"]),                 # vocals = magenta/violet
    ("vox",   "MG", 43,  ["choir", "bgv", "backing vox", "gang"]),
    ("vox",   "MG", 41,  ["lead vox", "vox", "vocal", "sing", "singer"]),
    ("vox",   "WH", 45,  ["talkback", "talk"]),                  # talkback = utility white
    ("mic",   "WH", 51,  ["wireless mic", "wl mic", "handheld"]),
    ("mic",   "WH", 47,  ["mic", "sm57", "sm58", "beta", "e609", "md421", " 57", " 58"]),
    ("playback", "WH", 60, ["usb", "tape", "playback", "track", "click", "metronome"]),
    ("fx",    "CY", 61,  ["fx", "reverb", "delay", "verb", "echo"]),   # FX = cyan / "ice blue"
    ("pc",    "WH", 62,  ["pc ", "computer", " mac", "daw", "ableton", "logic", "reaper", "pro tools"]),
]
_DEFAULT = ("other", "OFF", 1)   # uncategorized = no color -> visibly flags channels to set on a fresh build


def categorize(name):
    low = " " + name.lower() + " "
    for category, color, icon, kws in _RULES:
        if any(k in low for k in kws):
            return (category, color, icon)
    return _DEFAULT


_LINE = re.compile(r"^\s*(?:ch\s*)?(\d+)\s*[-.):]?\s*(\S.*?)\s*$", re.IGNORECASE)


def parse_input_list(text):
    """Parse numbered input-list lines into channel dicts. Skips headers/blanks."""
    chans = []
    for line in text.splitlines():
        m = _LINE.match(line)
        if not m:
            continue
        name = m.group(2).strip()
        if not name:
            continue
        category, color, icon = categorize(name)
        chans.append({"ch": int(m.group(1)), "name": name,
                      "category": category, "color": color, "icon": icon})
    return chans


def build_scene(channels, scene_name="Auto Show"):
    """Emit a minimal valid X32 .scn from channel dicts (name + icon + color + source)."""
    out = [f'#4.0# "{scene_name[:16]}" "" %000000000 1']
    for c in channels:
        _, color, icon = categorize(c["name"])
        color = c.get("color") or color
        icon = c.get("icon") or icon
        out.append(f'/ch/{c["ch"]:02d}/config "{c["name"]}" {icon} {color} {c["ch"]}')
    return "\n".join(out) + "\n"
