"""Scene-corpus analyzer: turn ALL of Winship's legacy .scn files into a
foundational profile Niles starts fresh from — his naming/color/icon vocabulary,
distinct routing profiles, bus conventions, and a per-scene catalog.
"""
import os
import re

_CH = re.compile(r"^/ch/(\d+)/config$")
_BUS = re.compile(r"^/(?:bus|mtx|auxin)/(\d+)/config$")


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
            "routing": {}, "routing_mode": None}
    with open(path, errors="replace") as f:
        for raw in f:
            line = raw.strip()
            if not line:
                continue
            if line.startswith("#"):
                for t in _tokens(line):
                    if t.startswith('"'):
                        info["scene_name"] = t.strip('"')
                        break
                continue
            if not line.startswith("/"):
                continue
            toks = _tokens(line)
            addr, args = toks[0], toks[1:]
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
                info["routing"][addr.rsplit("/", 1)[-1]] = " ".join(args)
    return info


def analyze_corpus(paths):
    name_vocab, color_usage, icon_usage, bus_names = {}, {}, {}, {}
    routing_profiles, scenes = {}, []
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
        scenes.append({
            "name": s["scene_name"] or os.path.basename(path),
            "path": path,
            "named_channels": len(named),
            "routing_mode": s["routing_mode"],
            "uses_aes50b": bool(s["routing"].get("AES50B")),
            "uses_p16": any("P16" in v for v in s["routing"].values()),
        })
    return {"name_vocab": name_vocab, "color_usage": color_usage,
            "icon_usage": icon_usage, "bus_names": bus_names,
            "routing_profiles": routing_profiles, "scenes": scenes}


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
    return "\n".join(out) + "\n"
