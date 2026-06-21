"""Scene-corpus analyzer: turn ALL of Winship's legacy .scn files into a
foundational profile Niles starts fresh from — his naming/color/icon vocabulary,
distinct routing profiles, bus conventions, and a per-scene catalog.
"""
import os
import re

_CH = re.compile(r"^/ch/(\d+)/config$")
_BUS = re.compile(r"^/(?:bus|mtx|auxin)/(\d+)/config$")

_DAW_KEYWORDS = ("ableton", "logic", "reaper")

def _detect_daw(text: str) -> str | None:
    lowered = text.lower()
    for kw in _DAW_KEYWORDS:
        if kw in lowered:
            return kw
    return None


def _tokens(line):
    out, buf, inq = [], "", False
    for ch in line:
        if ch == '"':
            inq = not inq
            buf += ch
        elif ch == " " and not inq:
            if buf:
                out.append(buf)
                buf = ""
        else:
            buf += ch
    if buf:
        out.append(buf)
    return out


def _int(tok, default=None):
    try:
        return int(tok)
    except (ValueError, TypeError):
        return default


def parse_scene(path):
    info = {"path": path, "scene_name": None, "channels": [], "buses": [],
            "routing": {}, "routing_mode": None,
            "daw_hint": None, "has_card_routing": False,
            "has_producer_osc": False, "producer_intent": False}
    # Check filename for DAW keywords before reading content
    info["daw_hint"] = _detect_daw(os.path.basename(path))
    with open(path, errors="replace") as f:
        for raw in f:
            line = raw.strip()
            if not line:
                continue
            if line.startswith("#"):
                for t in _tokens(line):
                    if t.startswith('"'):
                        info["scene_name"] = t.strip('"')
                        # Scene name may also carry a DAW hint
                        if info["daw_hint"] is None:
                            info["daw_hint"] = _detect_daw(info["scene_name"])
                        break
                continue
            if not line.startswith("/"):
                continue
            toks = _tokens(line)
            addr, args = toks[0], toks[1:]
            # Producer OSC namespace
            if addr.startswith("/_producer/"):
                info["has_producer_osc"] = True
            m = _CH.match(addr)
            if m and len(args) >= 3:
                info["channels"].append({
                    "ch": int(m.group(1)),
                    "name": args[0].strip('"'),
                    "icon": _int(args[1]),
                    "color": args[2],
                    "source": _int(args[3]) if len(args) > 3 else None,
                })
                continue
            mb = _BUS.match(addr)
            if mb and len(args) >= 2:
                info["buses"].append({"id": int(mb.group(1)),
                                      "name": args[0].strip('"'),
                                      "color": args[2] if len(args) > 2 else None})
                continue
            if addr == "/config/routing" and args:
                info["routing_mode"] = args[0]
            elif addr.startswith("/config/routing/"):
                key = addr.rsplit("/", 1)[-1]
                val = " ".join(args)
                info["routing"][key] = val
                if key == "CARD" or "CARD" in val:
                    info["has_card_routing"] = True
    # Derive producer_intent: DAW keyword OR producer OSC namespace OR CARD routing
    info["producer_intent"] = bool(
        info["daw_hint"] or info["has_producer_osc"] or info["has_card_routing"]
    )
    return info


def analyze_corpus(paths):
    name_vocab, color_usage, icon_usage, bus_names = {}, {}, {}, {}
    routing_profiles, scenes = {}, []
    producer_scenes = []
    production_routing_profiles = {}
    for path in paths:
        try:
            s = parse_scene(path)
        except OSError:
            continue
        named = [c for c in s["channels"] if c["name"]]
        for c in named:
            nv = name_vocab.setdefault(c["name"], {"count": 0, "colors": {}, "icons": {}})
            nv["count"] += 1
            nv["colors"][c["color"]] = nv["colors"].get(c["color"], 0) + 1
            if c["icon"] is not None:
                nv["icons"][c["icon"]] = nv["icons"].get(c["icon"], 0) + 1
            color_usage[c["color"]] = color_usage.get(c["color"], 0) + 1
            if c["icon"] is not None:
                icon_usage[c["icon"]] = icon_usage.get(c["icon"], 0) + 1
        for b in s["buses"]:
            if b["name"]:
                bus_names[b["name"]] = bus_names.get(b["name"], 0) + 1
        sig = tuple(sorted(s["routing"].items())) + (("mode", s["routing_mode"]),)
        routing_profiles.setdefault(sig, []).append(s["scene_name"] or os.path.basename(path))
        scene_entry = {
            "name": s["scene_name"] or os.path.basename(path),
            "path": path,
            "named_channels": len(named),
            "routing_mode": s["routing_mode"],
            "uses_aes50b": bool(s["routing"].get("AES50B")),
            "uses_p16": any("P16" in v for v in s["routing"].values()),
            "producer_intent": s["producer_intent"],
            "daw_hint": s["daw_hint"],
            "has_card_routing": s["has_card_routing"],
        }
        scenes.append(scene_entry)
        if s["producer_intent"]:
            producer_scenes.append(scene_entry)
            prod_sig = sig + (("daw", s["daw_hint"]),)
            production_routing_profiles.setdefault(prod_sig, []).append(
                s["scene_name"] or os.path.basename(path)
            )
    return {"name_vocab": name_vocab, "color_usage": color_usage,
            "icon_usage": icon_usage, "bus_names": bus_names,
            "routing_profiles": routing_profiles, "scenes": scenes,
            "producer_scenes": producer_scenes,
            "production_routing_profiles": production_routing_profiles}


def _dominant(d):
    return max(d.items(), key=lambda kv: kv[1])[0] if d else None


def to_markdown(agg, title="X32 corpus foundation"):
    out = [f"# {title}", "",
           f"_{len(agg['scenes'])} scenes · {len(agg['name_vocab'])} distinct channel names · "
           f"{len(agg['routing_profiles'])} distinct routing profiles_", ""]
    out.append("## Channel naming + color/icon convention (his own, by frequency)")
    out.append("| name | seen | usual color | usual icon |")
    out.append("|---|---|---|---|")
    for name, v in sorted(agg["name_vocab"].items(), key=lambda kv: -kv[1]["count"])[:40]:
        out.append(f"| {name} | {v['count']} | {_dominant(v['colors'])} | {_dominant(v['icons'])} |")
    out.append("")
    out.append("## Distinct routing profiles (dedup'd)")
    for i, (_sig, members) in enumerate(sorted(agg["routing_profiles"].items(),
                                               key=lambda kv: -len(kv[1])), 1):
        out.append(f"{i}. **{len(members)} scene(s)**: {', '.join(sorted(set(members))[:6])}")
    out.append("")
    out.append("## Bus name conventions (top)")
    for name, n in sorted(agg["bus_names"].items(), key=lambda kv: -kv[1])[:20]:
        out.append(f"- {name} ({n})")
    out.append("")
    out.append("## Producer Routing Profiles")
    producer_scenes = agg.get("producer_scenes", [])
    prod_profiles = agg.get("production_routing_profiles", {})
    if not producer_scenes:
        out.append("_No producer-intent scenes detected in corpus._")
    else:
        out.append(f"_{len(producer_scenes)} scene(s) with producer intent "
                   f"({len(prod_profiles)} distinct routing profile(s))_")
        out.append("")
        out.append("| Scene | DAW Hint | CARD Routing | Routing Mode |")
        out.append("|---|---|---|---|")
        for sc in sorted(producer_scenes, key=lambda s: s["name"]):
            daw = sc["daw_hint"] or "—"
            card = "yes" if sc["has_card_routing"] else "no"
            mode = sc["routing_mode"] or "—"
            out.append(f"| {sc['name']} | {daw} | {card} | {mode} |")
        if prod_profiles:
            out.append("")
            out.append("### Distinct producer routing profiles")
            for i, (_sig, members) in enumerate(
                sorted(prod_profiles.items(), key=lambda kv: -len(kv[1])), 1
            ):
                out.append(f"{i}. **{len(members)} scene(s)**: {', '.join(sorted(set(members))[:6])}")
    return "\n".join(out) + "\n"
