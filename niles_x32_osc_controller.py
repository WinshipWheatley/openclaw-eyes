"""Niles X32 OSC controller.

Direct UDP OSC control for Behringer X32 consoles on port 10023.  This module
does not start live services, discover hardware, or grant autonomy; callers
must provide an approved rack target and keep hardware use behind a separate
gate.  The implementation uses only the standard library so the emulator tests
do not depend on optional OSC packages.
"""

from __future__ import annotations

from dataclasses import dataclass
import shlex
import socket
import struct
import time
from pathlib import Path
from typing import Any, Iterable, Sequence


X32_OSC_PORT = 10023


@dataclass(frozen=True)
class RackConfig:
    rack_id: str
    console_ip: str
    port: int = X32_OSC_PORT
    state: str = "unknown"

    def require_up(self) -> None:
        if self.state.lower() == "down":
            raise RuntimeError(f"Rack {self.rack_id!r} is marked down; refusing OSC control.")


def _pad4(payload: bytes) -> bytes:
    return payload + (b"\0" * ((4 - (len(payload) % 4)) % 4))


def _encode_string(value: str) -> bytes:
    return _pad4(value.encode("utf-8") + b"\0")


def _read_string(data: bytes, offset: int) -> tuple[str, int]:
    end = data.index(b"\0", offset)
    raw = data[offset:end].decode("utf-8")
    next_offset = end + 1
    while next_offset % 4:
        next_offset += 1
    return raw, next_offset


def encode_osc_message(address: str, *args: Any) -> bytes:
    if not str(address).startswith("/"):
        raise ValueError(f"OSC address must start with '/': {address!r}")
    tags = [","]
    arg_bytes = bytearray()
    for arg in args:
        if isinstance(arg, bool):
            tags.append("i")
            arg_bytes.extend(struct.pack(">i", int(arg)))
        elif isinstance(arg, int):
            tags.append("i")
            arg_bytes.extend(struct.pack(">i", arg))
        elif isinstance(arg, float):
            tags.append("f")
            arg_bytes.extend(struct.pack(">f", arg))
        else:
            tags.append("s")
            arg_bytes.extend(_encode_string(str(arg)))
    return _encode_string(str(address)) + _encode_string("".join(tags)) + bytes(arg_bytes)


def decode_osc_message(data: bytes) -> tuple[str, tuple[Any, ...]]:
    address, offset = _read_string(data, 0)
    type_tags, offset = _read_string(data, offset)
    if not type_tags.startswith(","):
        raise ValueError("OSC type tag string missing comma prefix")
    args: list[Any] = []
    for tag in type_tags[1:]:
        if tag == "i":
            args.append(struct.unpack(">i", data[offset : offset + 4])[0])
            offset += 4
        elif tag == "f":
            args.append(struct.unpack(">f", data[offset : offset + 4])[0])
            offset += 4
        elif tag == "s":
            value, offset = _read_string(data, offset)
            args.append(value)
        else:
            raise ValueError(f"Unsupported OSC type tag: {tag!r}")
    return address, tuple(args)


def normalize_float(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def channel_address(channel: int, suffix: str) -> str:
    if channel < 1 or channel > 32:
        raise ValueError("X32 channel must be in 1..32")
    clean_suffix = str(suffix).strip("/")
    return f"/ch/{channel:02d}/{clean_suffix}"


def headamp_address(index: int, suffix: str) -> str:
    if index < 0 or index > 127:
        raise ValueError("X32 headamp index must be in 0..127")
    clean_suffix = str(suffix).strip("/")
    return f"/headamp/{index:03d}/{clean_suffix}"


def resolve_headamp_index(source: int | str) -> int:
    """Resolve a channel source number to a headamp slot.

    X32 headamp slots are 000-031 local, 032-079 AES50-A, and 080-127 AES50-B.
    The caller is responsible for deriving the source from routing + channel
    config; this helper enforces the resulting valid range.
    """

    index = int(source)
    if index < 0 or index > 127:
        raise ValueError("Resolved source is outside X32 headamp range 000..127")
    return index


def _parse_scene_arg(token: str) -> Any:
    clean = token.strip()
    if not clean:
        return clean
    try:
        if "." in clean:
            return float(clean)
        return int(clean)
    except ValueError:
        return clean


def parse_scene_line(line: str) -> tuple[str, tuple[Any, ...]] | None:
    stripped = line.strip()
    if not stripped or stripped.startswith("#") or stripped.startswith("//"):
        return None
    parts = shlex.split(stripped, comments=False, posix=True)
    if not parts:
        return None
    return parts[0], tuple(_parse_scene_arg(part) for part in parts[1:])


class X32OscController:
    def __init__(
        self,
        rack: RackConfig | str,
        *,
        port: int = X32_OSC_PORT,
        timeout: float = 1.0,
        sock: socket.socket | None = None,
    ) -> None:
        if isinstance(rack, RackConfig):
            rack.require_up()
            self.rack = rack
            self.host = rack.console_ip
            self.port = rack.port
        else:
            self.rack = RackConfig(rack_id="adhoc", console_ip=str(rack), port=port)
            self.host = str(rack)
            self.port = int(port)
        self.timeout = float(timeout)
        self._sock = sock or socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock.settimeout(self.timeout)
        self._target = (self.host, self.port)

    def close(self) -> None:
        self._sock.close()

    def __enter__(self) -> "X32OscController":
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    def send(self, address: str, *args: Any) -> None:
        self._sock.sendto(encode_osc_message(address, *args), self._target)

    def receive(self) -> tuple[str, tuple[Any, ...]]:
        data, _addr = self._sock.recvfrom(65536)
        return decode_osc_message(data)

    def query(self, address: str) -> tuple[Any, ...]:
        self.send(address)
        reply_address, args = self.receive()
        if reply_address != address:
            raise RuntimeError(f"Unexpected OSC reply {reply_address!r}; expected {address!r}")
        return args

    def verify(self, address: str, expected: Any | Sequence[Any], *, tolerance: float = 0.0001) -> bool:
        actual = self.query(address)
        expected_values = tuple(expected) if isinstance(expected, Sequence) and not isinstance(expected, (str, bytes, bytearray)) else (expected,)
        if len(actual) != len(expected_values):
            return False
        for actual_value, expected_value in zip(actual, expected_values):
            if isinstance(expected_value, float):
                if abs(float(actual_value) - expected_value) > tolerance:
                    return False
            elif actual_value != expected_value:
                return False
        return True

    def xremote(self) -> None:
        self.send("/xremote")

    def set_channel_name(self, channel: int, name: str) -> None:
        self.send(channel_address(channel, "config/name"), name)

    def set_channel_color(self, channel: int, color: int) -> None:
        self.send(channel_address(channel, "config/color"), int(color))

    def set_channel_source(self, channel: int, source: int) -> None:
        self.send(channel_address(channel, "config/source"), int(source))

    def set_headamp_gain(self, headamp_index: int | str, normalized_gain: float) -> None:
        index = resolve_headamp_index(headamp_index)
        self.send(headamp_address(index, "gain"), normalize_float(normalized_gain))

    def ramp(self, address: str, target: float, *, milliseconds: int, steps: int = 16, start: float = 0.0) -> list[float]:
        if steps < 1:
            raise ValueError("steps must be >= 1")
        duration = max(0, int(milliseconds)) / 1000.0
        values: list[float] = []
        for step in range(1, steps + 1):
            value = normalize_float(start + ((normalize_float(target) - normalize_float(start)) * (step / steps)))
            self.send(address, value)
            values.append(value)
            if duration and step != steps:
                time.sleep(duration / steps)
        return values

    def load_scene(self, scene_path: str | Path, *, pace_seconds: float = 0.0) -> list[tuple[str, tuple[Any, ...]]]:
        path = Path(scene_path)
        operations: list[tuple[str, tuple[Any, ...]]] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            parsed = parse_scene_line(line)
            if parsed is None:
                continue
            address, args = parsed
            self.send(address, *args)
            operations.append((address, args))
            if pace_seconds:
                time.sleep(float(pace_seconds))
        return operations


__all__ = [
    "RackConfig",
    "X32_OSC_PORT",
    "X32OscController",
    "channel_address",
    "decode_osc_message",
    "encode_osc_message",
    "headamp_address",
    "normalize_float",
    "parse_scene_line",
    "resolve_headamp_index",
]
