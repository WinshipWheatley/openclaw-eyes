from __future__ import annotations

import socket
import sys
import threading
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from niles_x32_osc_controller import (
    RackConfig,
    X32OscController,
    decode_osc_message,
    encode_osc_message,
    headamp_address,
    parse_scene_line,
    resolve_headamp_index,
)


class X32UdpEmulator:
    def __init__(self) -> None:
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(("127.0.0.1", 0))
        self.sock.settimeout(0.2)
        self.host, self.port = self.sock.getsockname()
        self.state: dict[str, tuple] = {}
        self.messages: list[tuple[str, tuple]] = []
        self.xremote_count = 0
        self._stop = threading.Event()
        self.thread = threading.Thread(target=self._serve, daemon=True)

    def __enter__(self) -> "X32UdpEmulator":
        self.thread.start()
        return self

    def __exit__(self, *_exc: object) -> None:
        self._stop.set()
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as wake:
            wake.sendto(encode_osc_message("/quit"), (self.host, self.port))
        self.thread.join(timeout=1)
        self.sock.close()

    def _serve(self) -> None:
        while not self._stop.is_set():
            try:
                data, addr = self.sock.recvfrom(65536)
            except socket.timeout:
                continue
            address, args = decode_osc_message(data)
            if address == "/quit":
                continue
            self.messages.append((address, args))
            if address == "/xremote":
                self.xremote_count += 1
                continue
            if args:
                self.state[address] = args
                continue
            self.sock.sendto(encode_osc_message(address, *self.state.get(address, ())), addr)


def test_osc_codec_round_trips_x32_message_types() -> None:
    payload = encode_osc_message("/ch/01/config/name", "Kick", 3, 0.75)
    address, args = decode_osc_message(payload)

    assert address == "/ch/01/config/name"
    assert args[0] == "Kick"
    assert args[1] == 3
    assert abs(args[2] - 0.75) < 0.0001


def test_controller_sets_name_color_routing_and_headamp_gain_with_readback() -> None:
    with X32UdpEmulator() as emulator:
        rack = RackConfig(rack_id="big", console_ip=emulator.host, port=emulator.port, state="up")
        with X32OscController(rack, timeout=1.0) as controller:
            controller.set_channel_name(1, "Kick")
            controller.set_channel_color(1, 3)
            controller.set_channel_source(1, 32)
            controller.set_headamp_gain(32, 0.625)

            assert controller.verify("/ch/01/config/name", "Kick")
            assert controller.verify("/ch/01/config/color", 3)
            assert controller.verify("/ch/01/config/source", 32)
            assert controller.verify("/headamp/032/gain", 0.625)

    assert ("/ch/01/config/name", ("Kick",)) in emulator.messages
    assert ("/ch/01/config/color", (3,)) in emulator.messages
    assert ("/ch/01/config/source", (32,)) in emulator.messages


def test_scene_stream_and_xremote_use_same_udp_control_path(tmp_path: Path) -> None:
    scene = tmp_path / "fixture.scn"
    scene.write_text(
        "\n".join(
            [
                "# fixture scene",
                "/ch/02/config/name \"Snare Top\"",
                "/ch/02/config/color 5",
                "/config/routing/IN 1 2 3 4",
            ]
        ),
        encoding="utf-8",
    )

    with X32UdpEmulator() as emulator:
        with X32OscController(emulator.host, port=emulator.port, timeout=1.0) as controller:
            controller.xremote()
            operations = controller.load_scene(scene)
            assert operations == [
                ("/ch/02/config/name", ("Snare Top",)),
                ("/ch/02/config/color", (5,)),
                ("/config/routing/IN", (1, 2, 3, 4)),
            ]
            assert controller.verify("/ch/02/config/name", "Snare Top")
            assert controller.verify("/ch/02/config/color", 5)

    assert emulator.xremote_count == 1
    assert emulator.state["/config/routing/IN"] == (1, 2, 3, 4)


def test_ramp_synthesizes_stepped_values_without_native_fade() -> None:
    with X32UdpEmulator() as emulator:
        with X32OscController(emulator.host, port=emulator.port, timeout=1.0) as controller:
            values = controller.ramp("/ch/01/mix/fader", 0.8, milliseconds=0, steps=4, start=0.0)
            assert values == [0.2, 0.4, 0.6000000000000001, 0.8]
            assert controller.verify("/ch/01/mix/fader", 0.8)

    sent_values = [args[0] for address, args in emulator.messages if address == "/ch/01/mix/fader" and args]
    assert [round(value, 4) for value in sent_values] == [round(value, 4) for value in values]


def test_headamp_resolver_enforces_x32_ranges_and_down_rack_refuses_control() -> None:
    assert resolve_headamp_index(0) == 0
    assert resolve_headamp_index(32) == 32
    assert resolve_headamp_index("127") == 127
    assert headamp_address(80, "gain") == "/headamp/080/gain"

    try:
        resolve_headamp_index(128)
    except ValueError as exc:
        assert "000..127" in str(exc)
    else:
        raise AssertionError("out-of-range headamp index should fail")

    try:
        X32OscController(RackConfig(rack_id="little", console_ip="127.0.0.1", state="down"))
    except RuntimeError as exc:
        assert "marked down" in str(exc)
    else:
        raise AssertionError("down rack should refuse control")


def test_parse_scene_line_ignores_comments_and_preserves_strings() -> None:
    assert parse_scene_line("# ignored") is None
    assert parse_scene_line("/ch/03/config/name \"Lead Vox\"") == (
        "/ch/03/config/name",
        ("Lead Vox",),
    )
