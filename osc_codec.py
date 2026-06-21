"""Minimal OSC 1.0 codec (stdlib only) for Niles' X32 control.

X32 speaks OSC over UDP. Messages: address-string, then a type-tag string
(',' + one char per arg), then the args. All strings are null-terminated and
padded to a 4-byte boundary; ints/floats are 32-bit big-endian.
Sending an address with NO args = a query; the desk replies with the value.
"""
import struct


def _pad_str(s: str) -> bytes:
    raw = s.encode("ascii") + b"\x00"
    return raw + b"\x00" * ((-len(raw)) % 4)


def _read_str(data: bytes, i: int):
    end = data.index(b"\x00", i)
    s = data[i:end].decode("ascii")
    length = end - i + 1  # include the null
    return s, i + length + ((-length) % 4)


def encode(address: str, *args) -> bytes:
    out = _pad_str(address)
    typetag = ","
    blobs = []
    for a in args:
        if isinstance(a, bool):
            a = int(a)
        if isinstance(a, str):
            typetag += "s"
            blobs.append(_pad_str(a))
        elif isinstance(a, int):
            typetag += "i"
            blobs.append(struct.pack(">i", a))
        elif isinstance(a, float):
            typetag += "f"
            blobs.append(struct.pack(">f", a))
        else:
            raise TypeError(f"unsupported OSC arg type: {type(a)}")
    out += _pad_str(typetag)
    for b in blobs:
        out += b
    return out


def decode(data: bytes):
    address, i = _read_str(data, 0)
    args = []
    if i < len(data) and data[i:i + 1] == b",":
        typetag, i = _read_str(data, i)
        for t in typetag[1:]:
            if t == "s":
                s, i = _read_str(data, i)
                args.append(s)
            elif t == "i":
                args.append(struct.unpack(">i", data[i:i + 4])[0])
                i += 4
            elif t == "f":
                args.append(struct.unpack(">f", data[i:i + 4])[0])
                i += 4
    return address, args
