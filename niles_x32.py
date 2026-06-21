"""Niles' X32 OSC controller (stdlib only).

Drives a Behringer X32 over OSC/UDP :10023 — naming, color, faders, IEM/monitor
sends, stagebox preamp gain/48V (headamp), and scene streaming, all with
read-back verification (no "I changed it" without evidence). Test it against
x32_fake, Maillot's X32 emulator, or a live console — same interface.
"""
import socket

from osc_codec import encode, decode

# X32 scribble-strip colors, enum 0..15 (8..15 = inverted/solid background)
COLORS = ["OFF", "RD", "GN", "YE", "BL", "MG", "CY", "WH",
          "OFFi", "RDi", "GNi", "YEi", "BLi", "MGi", "CYi", "WHi"]
_COLOR_TO_INT = {c: i for i, c in enumerate(COLORS)}

# headamp index space: 000-031 local, 032-079 AES50-A (stageboxes), 080-127 AES50-B
_HEADAMP_BASE = {"local": 0, "aes50a": 32, "aes50b": 80}


class NilesX32:
    def __init__(self, ip, port=10023, timeout=0.5):
        self.ip = ip
        self.port = port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.settimeout(timeout)
        self.sock.connect((ip, port))

    # --- transport ---
    def send(self, address, *args):
        self.sock.send(encode(address, *args))

    def query(self, address):
        """Send an arg-less address (X32 query); return the reply's args."""
        self.sock.send(encode(address))
        data = self.sock.recv(65535)
        _, args = decode(data)
        return args

    def xinfo(self):
        return self.query("/xinfo")

    # --- channel strip ---
    @staticmethod
    def _ch(ch):
        return f"/ch/{ch:02d}"

    def set_channel_name(self, ch, name):
        self.send(f"{self._ch(ch)}/config/name", str(name))

    def get_channel_name(self, ch):
        args = self.query(f"{self._ch(ch)}/config/name")
        return args[0] if args else None

    def set_channel_color(self, ch, color):
        ci = color if isinstance(color, int) else _COLOR_TO_INT[color]
        self.send(f"{self._ch(ch)}/config/color", int(ci))

    def get_channel_color(self, ch):
        args = self.query(f"{self._ch(ch)}/config/color")
        return COLORS[args[0]] if args else None

    def set_fader(self, ch, level01):
        self.send(f"{self._ch(ch)}/mix/fader", float(level01))

    def set_send(self, ch, bus, level01):
        """Set ch's send level to a mix bus (monitor/IEM mix), 0.0-1.0."""
        self.send(f"{self._ch(ch)}/mix/{bus:02d}/level", float(level01))

    # --- preamps (local + stagebox over AES50) ---
    @staticmethod
    def resolve_headamp(kind, n):
        """Map a preamp to its flat headamp index. kind: local|aes50a|aes50b, n 1-based."""
        if kind not in _HEADAMP_BASE:
            raise ValueError(f"unknown headamp kind: {kind}")
        if n < 1:
            raise ValueError("n is 1-based")
        return _HEADAMP_BASE[kind] + (n - 1)

    def set_headamp_gain(self, idx, db):
        self.send(f"/headamp/{idx:03d}/gain", float(db))

    def set_headamp_phantom(self, idx, on):
        self.send(f"/headamp/{idx:03d}/phantom", 1 if on else 0)

    # --- scenes ---
    @staticmethod
    def _parse_token(tok):
        if tok.startswith('"') and tok.endswith('"'):
            return tok[1:-1]
        try:
            return int(tok)
        except ValueError:
            pass
        try:
            return float(tok)
        except ValueError:
            return tok

    @staticmethod
    def _split_scene_line(line):
        """Split a .scn line into (address, [tokens]) honoring quoted strings."""
        out, buf, inq = [], "", False
        for chx in line:
            if chx == '"':
                inq = not inq
                buf += chx
            elif chx == " " and not inq:
                if buf:
                    out.append(buf)
                    buf = ""
            else:
                buf += chx
        if buf:
            out.append(buf)
        return out[0], out[1:]

    def load_scene(self, path):
        """Stream a .scn file to the desk as OSC messages. Returns lines sent.
        NOTE: streaming skeleton (the DIY load path) — types inferred from tokens.
        """
        sent = 0
        with open(path) as f:
            for raw in f:
                line = raw.strip()
                if not line or line.startswith("#"):
                    continue
                address, toks = self._split_scene_line(line)
                if not address.startswith("/"):
                    continue
                args = [self._parse_token(t) for t in toks]
                self.send(address, *args)
                sent += 1
        return sent

    # --- verification (evidence, not say-so) ---
    def verify(self, address, expected):
        got = self.query(address)
        if len(got) != len(expected):
            return False
        for g, e in zip(got, expected):
            if isinstance(e, float) or isinstance(g, float):
                if abs(float(g) - float(e)) > 1e-4:
                    return False
            elif g != e:
                return False
        return True

    def close(self):
        try:
            self.sock.close()
        except OSError:
            pass
