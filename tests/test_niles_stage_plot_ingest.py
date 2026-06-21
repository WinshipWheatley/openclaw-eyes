from __future__ import annotations

import socket
import sys
import threading
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from niles_stage_plot_ingest import (
    build_show_profile_from_email,
    generate_x32_scene_lines,
    parse_stage_plot_email,
    profile_to_json,
    write_scene,
)
from niles_x32_osc_controller import X32OscController, decode_osc_message, encode_osc_message, parse_scene_line


EMAIL_PAYLOAD = {
    "from": "pm@example.invalid",
    "subject": "Stage plot for Saturday",
    "body": """
Input 1 - Kick
Input 2 - Snare Top
3 Lead Vocal
4 Guitar SR
5 Bass DI
IEM 1: Lead Vocal, Guitar
Monitor 2: Kick, Snare
""",
}


class X32UdpEmulator:
    def __init__(self) -> None:
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(("127.0.0.1", 0))
        self.sock.settimeout(0.2)
        self.host, self.port = self.sock.getsockname()
        self.state: dict[str, tuple] = {}
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
            if args:
                self.state[address] = args
                continue
            self.sock.sendto(encode_osc_message(address, *self.state.get(address, ())), addr)


def test_parse_stage_plot_email_extracts_inputs_and_monitor_sends() -> None:
    inputs, monitor_sends, metadata = parse_stage_plot_email(EMAIL_PAYLOAD)

    assert metadata == {"subject": "Stage plot for Saturday", "sender": "pm@example.invalid"}
    assert [(item.channel, item.name, item.source) for item in inputs] == [
        (1, "Kick", 32),
        (2, "Snare Top", 33),
        (3, "Lead Vocal", 34),
        (4, "Guitar SR", 35),
        (5, "Bass DI", 36),
    ]
    assert inputs[0].color == 1
    assert inputs[2].color == 8
    assert inputs[3].color == 4
    assert [(send.bus, send.source_names) for send in monitor_sends] == [
        (1, ("Lead Vocal", "Guitar")),
        (2, ("Kick", "Snare")),
    ]


def test_generate_x32_scene_lines_are_valid_osc_scene_commands() -> None:
    inputs, monitor_sends, _metadata = parse_stage_plot_email(EMAIL_PAYLOAD)
    lines = generate_x32_scene_lines(inputs, monitor_sends)
    command_lines = [line for line in lines if not line.startswith("#")]
    parsed = [parse_scene_line(line) for line in command_lines]

    assert all(item is not None for item in parsed)
    assert '/ch/01/config/name "Kick"' in lines
    assert "/ch/01/config/source 32" in lines
    assert "/headamp/032/gain 0.5" in lines
    assert "/ch/03/mix/01/level 0.5" in lines
    assert "/ch/04/mix/01/level 0.5" in lines
    assert "/ch/01/mix/02/level 0.5" in lines


def test_build_profile_writes_scene_and_streams_through_x32_controller(tmp_path: Path) -> None:
    profile = build_show_profile_from_email(EMAIL_PAYLOAD)
    scene_path = write_scene(profile, tmp_path / "stage_plot.scn")

    assert profile.authority_boundary["hardware_control_performed"] is False
    assert profile.authority_boundary["operator_approval_required_before_load"] is True
    assert scene_path.read_text(encoding="utf-8").startswith("# Niles generated X32")

    with X32UdpEmulator() as emulator:
        with X32OscController(emulator.host, port=emulator.port, timeout=1.0) as controller:
            operations = controller.load_scene(scene_path)
            assert operations
            assert controller.verify("/ch/03/config/name", "Lead Vocal")
            assert controller.verify("/ch/03/mix/01/level", 0.5)

    assert emulator.state["/ch/05/config/name"] == ("Bass DI",)
    assert emulator.state["/headamp/036/gain"][0] == 0.5


def test_profile_json_is_machine_readable_and_send_hold_safe() -> None:
    profile = build_show_profile_from_email(EMAIL_PAYLOAD)
    payload = profile_to_json(profile)

    assert '"schema_version": "niles_stage_plot_ingest_v0"' in payload
    assert '"email_send_performed": false' in payload
    assert '"live_scene_loaded": false' in payload
    assert '"hardware_control_performed": false' in payload
