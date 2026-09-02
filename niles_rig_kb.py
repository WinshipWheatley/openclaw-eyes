"""Deterministic Niles rig-control knowledge base seed.

This module builds a local SQLite knowledge base for Niles' music rig context.
It intentionally records capability and control-path knowledge only. It never
opens DAWs, sends OSC/MIDI, scans music folders, reads secrets, or touches gear.
Unknown manuals stay marked as not loaded instead of being invented.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable


SCHEMA_VERSION = "niles_gear_kb_v0"
READ_MODEL_ID = "niles_gear_kb"
DEFAULT_SQLITE_PATH = Path("generated/system_knowledge/niles_gear_kb.sqlite")

X32_OSC_SOURCE_REFS = (
    "https://tostibroeders.nl/wp-content/uploads/2020/02/X32-OSC.pdf",
    "https://x32ram.com/wp-content/uploads/download-files/X32-OSC.pdf",
    "https://www.behringer.com/en/products/0603-ACE",
)

AUTHORITY_BOUNDARY = {
    "live_hardware_control_allowed": False,
    "osc_message_allowed": False,
    "midi_message_allowed": False,
    "daw_control_allowed": False,
    "obs_control_allowed": False,
    "app_launch_allowed": False,
    "audio_file_mutation_allowed": False,
    "project_file_mutation_allowed": False,
    "manual_download_allowed_at_runtime": False,
    "credential_handling_allowed": False,
    "network_control_allowed": False,
    "external_send_allowed": False,
}


@dataclass(frozen=True)
class GearDevice:
    device_id: str
    category: str
    manufacturer: str
    model_name: str
    count: int
    role: str
    gig_role: str
    repair_status: str
    model_verification_status: str
    manual_status: str
    control_surface: str
    notes: str
    source_ref: str


@dataclass(frozen=True)
class ControlPath:
    control_id: str
    device_id: str
    protocol: str
    transport: str
    port: str
    address_pattern: str
    command_kind: str
    value_shape: str
    stress_test_target: str
    requires_confirmation: bool
    safe_to_execute: bool
    source_ref: str
    notes: str


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def seed_devices() -> tuple[GearDevice, ...]:
    return (
        GearDevice(
            device_id="x32_rack_monitor",
            category="mixing_live_sound",
            manufacturer="Behringer",
            model_name="X32 Rack",
            count=1,
            role="monitor mixer and in-ear monitor rig",
            gig_role="monitor_iem",
            repair_status="operational_status_unverified",
            model_verification_status="operator_confirmed",
            manual_status="osc_protocol_source_identified_not_fully_ingested",
            control_surface="OSC via X32 / X32 Edit",
            notes="Band gigs need this unit plus the FOH X32. No hardware control without explicit confirmation.",
            source_ref="operator_inventory_2026-06-19",
        ),
        GearDevice(
            device_id="x32_rack_broken",
            category="mixing_live_sound",
            manufacturer="Behringer",
            model_name="X32 Rack",
            count=1,
            role="FOH mixer candidate; currently tracked as gear to fix",
            gig_role="foh",
            repair_status="needs_repair",
            model_verification_status="operator_confirmed",
            manual_status="osc_protocol_source_identified_not_fully_ingested",
            control_surface="OSC via X32 / X32 Edit after repair",
            notes="One X32 is broken and must be tracked as gear-to-fix before relying on it for FOH.",
            source_ref="operator_inventory_2026-06-19",
        ),
        GearDevice(
            device_id="x32_edit_app",
            category="mixing_live_sound",
            manufacturer="Behringer",
            model_name="X32 Edit",
            count=1,
            role="software editor and safe stress-test target before real hardware",
            gig_role="test_harness",
            repair_status="software_availability_unverified",
            model_verification_status="operator_confirmed",
            manual_status="manual_not_loaded_yet",
            control_surface="OSC-compatible editor surface",
            notes="Stress-test agentic control through the app first. Do not touch physical hardware autonomously.",
            source_ref="operator_inventory_2026-06-19",
        ),
        GearDevice(
            device_id="dbx_driverack_pa2",
            category="mixing_live_sound",
            manufacturer="dbx",
            model_name="DriveRack PA2",
            count=1,
            role="FOH rack processing after X32",
            gig_role="foh_processing",
            repair_status="operational_status_unverified",
            model_verification_status="operator_named_verify_docs",
            manual_status="manual_not_loaded_yet",
            control_surface="vendor app/API to research",
            notes="Potential control area: tuning, compression, and limiters. Manual/API not ingested yet.",
            source_ref="operator_inventory_2026-06-19",
        ),
        GearDevice(
            device_id="dl32_stage_box",
            category="mixing_live_sound",
            manufacturer="Behringer/Midas",
            model_name="DL32",
            count=1,
            role="stage box connected over AES50",
            gig_role="stage_io",
            repair_status="operational_status_unverified",
            model_verification_status="operator_confirmed",
            manual_status="manual_not_loaded_yet",
            control_surface="AES50 integration context",
            notes="Connects to one X32 depending on monitor/FOH setup. Not a direct control target in v0.",
            source_ref="operator_inventory_2026-06-19",
        ),
        GearDevice(
            device_id="push_2",
            category="midi_controller",
            manufacturer="Ableton",
            model_name="Push 2",
            count=1,
            role="Ableton Live controller with user-mode MIDI mapping potential",
            gig_role="studio_live_controller",
            repair_status="operational_status_unverified",
            model_verification_status="operator_confirmed",
            manual_status="manual_not_loaded_yet",
            control_surface="MIDI / Ableton Live API to research",
            notes="Map user modes for context switching and safe automations after explicit confirmation.",
            source_ref="operator_inventory_2026-06-19",
        ),
        GearDevice(
            device_id="apc40",
            category="midi_controller",
            manufacturer="Akai",
            model_name="APC40",
            count=1,
            role="Ableton controller with user-mode mapping potential",
            gig_role="studio_live_controller",
            repair_status="operational_status_unverified",
            model_verification_status="operator_confirmed",
            manual_status="manual_not_loaded_yet",
            control_surface="MIDI to research",
            notes="Programmable controls should be documented before any live use.",
            source_ref="operator_inventory_2026-06-19",
        ),
        GearDevice(
            device_id="nektar_lx49_plus",
            category="midi_controller",
            manufacturer="Nektar",
            model_name="LX49+",
            count=1,
            role="keyboard controller",
            gig_role="studio_live_controller",
            repair_status="operational_status_unverified",
            model_verification_status="operator_confirmed",
            manual_status="manual_not_loaded_yet",
            control_surface="MIDI to research",
            notes="Operator confirmed Nektar LX49+.",
            source_ref="operator_inventory_2026-06-19",
        ),
        GearDevice(
            device_id="mpc_one_plus",
            category="midi_controller",
            manufacturer="Akai",
            model_name="MPC One+",
            count=1,
            role="MPC production controller",
            gig_role="studio_live_controller",
            repair_status="operational_status_unverified",
            model_verification_status="operator_named_verify_docs",
            manual_status="manual_not_loaded_yet",
            control_surface="MIDI/API to research",
            notes="Exact control affordances need manual/API ingestion.",
            source_ref="operator_inventory_2026-06-19",
        ),
        GearDevice(
            device_id="reloop_beatpad",
            category="midi_controller",
            manufacturer="Reloop",
            model_name="Beatpad",
            count=1,
            role="Algoriddim djay Pro controller",
            gig_role="dj_controller",
            repair_status="operational_status_unverified",
            model_verification_status="operator_confirmed",
            manual_status="manual_not_loaded_yet",
            control_surface="MIDI / djay Pro mappings to research",
            notes="djay Pro API/mapping path needs research before action.",
            source_ref="operator_inventory_2026-06-19",
        ),
        GearDevice(
            device_id="kat_percussion_pad",
            category="midi_controller",
            manufacturer="KAT",
            model_name="model TBD",
            count=1,
            role="drum-set percussion pad with built-in sounds and MIDI",
            gig_role="drum_controller",
            repair_status="operational_status_unverified",
            model_verification_status="verify_model",
            manual_status="manual_not_loaded_yet",
            control_surface="MIDI to research after model confirmation",
            notes="Operator called it KAT4 or similar; exact model remains unresolved.",
            source_ref="operator_inventory_2026-06-19",
        ),
        GearDevice(
            device_id="fcb1010",
            category="midi_controller",
            manufacturer="Behringer",
            model_name="FCB1010",
            count=1,
            role="MIDI foot controller",
            gig_role="foot_controller",
            repair_status="operational_status_unverified",
            model_verification_status="operator_confirmed",
            manual_status="manual_not_loaded_yet",
            control_surface="MIDI to research",
            notes="Candidate for foot-triggered context or rig controls after mapping review.",
            source_ref="operator_inventory_2026-06-19",
        ),
        # Live looping rig (LIVE-RIG.md, 2026-08-24). Planned purchases are recorded as
        # not_yet_purchased; owned units carry the live-rig role without inventing status.
        GearDevice(
            device_id="studiologic_sl88_grand",
            category="midi_controller",
            manufacturer="Studiologic",
            model_name="SL88 Grand",
            count=1,
            role="88-key wooden-key Fatar action controller for the live looping show; USB MIDI to the Mac",
            gig_role="live_keyboard_controller",
            repair_status="not_yet_purchased",
            model_verification_status="operator_named_planned_purchase",
            manual_status="manual_not_loaded_yet",
            control_surface="USB MIDI to Mac / Ableton 11",
            notes="Planned purchase (~$850-1,000). Kawai VPC1 ruled out. The delivery window doubles as the synth audition window.",
            source_ref="LIVE-RIG.md@2026-08-24",
        ),
        GearDevice(
            device_id="boss_rc505_mk2",
            category="looper",
            manufacturer="Boss",
            model_name="RC-505 MK2",
            count=1,
            role="hardware looper; clock slave over 5-pin MIDI from the MOTU M4, quantized to bar",
            gig_role="live_looper",
            repair_status="not_yet_purchased",
            model_verification_status="operator_named_planned_purchase",
            manual_status="manual_not_loaded_yet",
            control_surface="5-pin MIDI clock in from the MOTU M4; front-panel loop control",
            notes="Planned purchase (~$599). Loops live in hardware so they survive a computer crash. Its X32 channel assignment is proposed, not confirmed.",
            source_ref="LIVE-RIG.md@2026-08-24",
        ),
        GearDevice(
            device_id="motu_m4",
            category="audio_interface",
            manufacturer="MOTU",
            model_name="M4",
            count=1,
            role="the one audio interface (no aggregate devices): outs 1/2 to the X32, outs 3/4 to in-ear monitors, 5-pin MIDI out carries Ableton clock",
            gig_role="live_audio_interface",
            repair_status="not_yet_purchased",
            model_verification_status="operator_named_planned_purchase",
            manual_status="manual_not_loaded_yet",
            control_surface="USB audio and MIDI from the Mac; no remote control path",
            notes="Planned purchase (~$250), swapped from the M2 plan for four outputs. Click and cues on outs 3/4 go to the in-ear monitor bus only, never mains. Inputs take the X32 matrix record feed.",
            source_ref="LIVE-RIG.md@2026-08-24",
        ),
        GearDevice(
            device_id="mpc_one_plus_live_looping",
            category="midi_controller",
            manufacturer="Akai",
            model_name="MPC One+",
            count=1,
            role="pad/beat station in the live looping rig; USB MIDI to the Mac",
            gig_role="live_pad_station",
            repair_status="operational_status_unverified",
            model_verification_status="operator_confirmed",
            manual_status="manual_not_loaded_yet",
            control_surface="USB MIDI to Mac / Ableton 11",
            notes="Owned. Same physical unit as mpc_one_plus (operator inventory 2026-06-19); this row records its live looping rig role.",
            source_ref="LIVE-RIG.md@2026-08-24",
        ),
        GearDevice(
            device_id="nektar_lx49_live_looping",
            category="midi_controller",
            manufacturer="Nektar",
            model_name="LX49",
            count=1,
            role="repurposed as Ableton control surface (pads are dull); USB MIDI to the Mac",
            gig_role="live_control_surface",
            repair_status="operational_status_unverified",
            model_verification_status="operator_confirmed",
            manual_status="manual_not_loaded_yet",
            control_surface="USB MIDI to Mac / Ableton 11 as a control surface",
            notes="Owned. Same physical unit as nektar_lx49_plus (operator inventory 2026-06-19); this row records its live looping rig role.",
            source_ref="LIVE-RIG.md@2026-08-24",
        ),
        GearDevice(
            device_id="ableton_11_suite",
            category="software_daw",
            manufacturer="Ableton",
            model_name="Live 11 Suite",
            count=1,
            role="DAW and clock master for the live looping rig",
            gig_role="live_daw_clock_master",
            repair_status="operational_status_unverified",
            model_verification_status="operator_confirmed",
            manual_status="manual_not_loaded_yet",
            control_surface="Mac host; played from the SL88, LX49, and MPC One+ over USB MIDI",
            notes="Owned software. Runs at a tight buffer (64-128 samples) for synth latency under the keyboard; clock leaves through the MOTU M4 5-pin MIDI out to the RC-505.",
            source_ref="LIVE-RIG.md@2026-08-24",
        ),
    )


def seed_control_paths() -> tuple[ControlPath, ...]:
    source_ref = "; ".join(X32_OSC_SOURCE_REFS)
    return (
        ControlPath(
            control_id="x32_osc_info",
            device_id="x32_rack_monitor",
            protocol="OSC",
            transport="UDP",
            port="10023",
            address_pattern="/xinfo",
            command_kind="read_status",
            value_shape="query",
            stress_test_target="X32 Edit App or explicitly approved test mixer only",
            requires_confirmation=True,
            safe_to_execute=False,
            source_ref=source_ref,
            notes="Use only in a confirmed test window. Reads are still network control attempts.",
        ),
        ControlPath(
            control_id="x32_osc_remote_keepalive",
            device_id="x32_rack_monitor",
            protocol="OSC",
            transport="UDP",
            port="10023",
            address_pattern="/xremote",
            command_kind="remote_session_keepalive",
            value_shape="no arguments",
            stress_test_target="X32 Edit App or explicitly approved test mixer only",
            requires_confirmation=True,
            safe_to_execute=False,
            source_ref=source_ref,
            notes="Remote session keepalive is documented in X32 OSC references; no autonomous send.",
        ),
        ControlPath(
            control_id="x32_osc_channel_fader",
            device_id="x32_rack_monitor",
            protocol="OSC",
            transport="UDP",
            port="10023",
            address_pattern="/ch/{channel:02d}/mix/fader",
            command_kind="set_channel_fader",
            value_shape="float 0.0..1.0",
            stress_test_target="X32 Edit App before hardware",
            requires_confirmation=True,
            safe_to_execute=False,
            source_ref=source_ref,
            notes="Starting X32 OSC control path for research and dry-run planning only.",
        ),
        ControlPath(
            control_id="x32_osc_channel_mute",
            device_id="x32_rack_monitor",
            protocol="OSC",
            transport="UDP",
            port="10023",
            address_pattern="/ch/{channel:02d}/mix/on",
            command_kind="set_channel_on",
            value_shape="enum OFF/ON",
            stress_test_target="X32 Edit App before hardware",
            requires_confirmation=True,
            safe_to_execute=False,
            source_ref=source_ref,
            notes="This can affect audio and must remain gated.",
        ),
        ControlPath(
            control_id="x32_osc_main_fader",
            device_id="x32_rack_monitor",
            protocol="OSC",
            transport="UDP",
            port="10023",
            address_pattern="/main/st/mix/fader",
            command_kind="set_main_stereo_fader",
            value_shape="float 0.0..1.0",
            stress_test_target="X32 Edit App before hardware",
            requires_confirmation=True,
            safe_to_execute=False,
            source_ref=source_ref,
            notes="High-risk control. Never use autonomously.",
        ),
    )


SCHEMA_SQL = """
create table if not exists devices (
  device_id text primary key,
  category text not null,
  manufacturer text not null,
  model_name text not null,
  count integer not null,
  role text not null,
  gig_role text not null,
  repair_status text not null,
  model_verification_status text not null,
  manual_status text not null,
  control_surface text not null,
  notes text not null,
  source_ref text not null
);

create table if not exists control_paths (
  control_id text primary key,
  device_id text not null references devices(device_id),
  protocol text not null,
  transport text not null,
  port text not null,
  address_pattern text not null,
  command_kind text not null,
  value_shape text not null,
  stress_test_target text not null,
  requires_confirmation integer not null,
  safe_to_execute integer not null,
  source_ref text not null,
  notes text not null
);

create table if not exists kb_metadata (
  key text primary key,
  value text not null
);
"""


def create_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA_SQL)


def _insert_dataclass_rows(conn: sqlite3.Connection, table: str, rows: Iterable[Any]) -> None:
    for row in rows:
        payload = asdict(row)
        for key, value in list(payload.items()):
            if isinstance(value, bool):
                payload[key] = int(value)
        columns = tuple(payload)
        placeholders = ", ".join("?" for _ in columns)
        column_sql = ", ".join(columns)
        update_sql = ", ".join(f"{column}=excluded.{column}" for column in columns)
        conn.execute(
            f"insert into {table} ({column_sql}) values ({placeholders}) "
            f"on conflict do update set {update_sql}",
            tuple(payload[column] for column in columns),
        )


def seed_database(conn: sqlite3.Connection) -> None:
    create_schema(conn)
    _insert_dataclass_rows(conn, "devices", seed_devices())
    _insert_dataclass_rows(conn, "control_paths", seed_control_paths())
    conn.executemany(
        "insert into kb_metadata (key, value) values (?, ?) "
        "on conflict(key) do update set value=excluded.value",
        (
            ("schema_version", SCHEMA_VERSION),
            ("read_model_id", READ_MODEL_ID),
            ("manuals_fabricated", "false"),
            ("runtime_control_authority", "false"),
            ("operator_confirmation_required", "true"),
            ("x32_starting_point", "OSC via X32 Edit App before hardware"),
        ),
    )


def build_sqlite_kb(path: Path = DEFAULT_SQLITE_PATH) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as conn:
        seed_database(conn)
        conn.commit()
    return path


def device_summary_lines() -> tuple[str, ...]:
    return (
        "2x Behringer X32 Rack: one monitor/IEM candidate and one FOH candidate marked broken/needs repair.",
        "X32 Edit App: safe first stress-test target before physical hardware.",
        "dbx DriveRack PA2: FOH processing after X32; manual/API not loaded yet.",
        "DL32 stage box: AES50 stage I/O context.",
        "MIDI/controllers: Push 2, APC40, Nektar LX49+, MPC One+, Reloop Beatpad, KAT pad model TBD, FCB1010.",
        "Software context: Logic Pro X, Ableton Live 10, TH-U, MainStage, EBOSuite, OBS plus NDI.",
        "Live looping rig plan (LIVE-RIG.md 2026-08-24): SL88 Grand, RC-505 MK2, and MOTU M4 not yet purchased; MPC One+ and Nektar LX49 repurposed; Ableton 11 Suite is clock master.",
    )


def x32_control_summary_lines() -> tuple[str, ...]:
    return (
        "X32 starting point: OSC over UDP port 10023, stress-tested against X32 Edit App first.",
        "Known research addresses: /xinfo, /xremote, /ch/{channel:02d}/mix/fader, /ch/{channel:02d}/mix/on, /main/st/mix/fader.",
        "All OSC rows are stored with safe_to_execute=false and requires_confirmation=true.",
    )


def x32_vocal_channel_advice_lines() -> tuple[str, ...]:
    return (
        "X32 vocal channel advice: set preamp gain from the singer's loudest line, aiming for healthy meter without clipping.",
        "Engage HPF around 80-120 Hz for most vocals; raise it carefully for rumble, lower it for deep voices.",
        "Use light compression first: about 2:1 to 3:1, medium attack/release, and roughly 3-6 dB gain reduction on peaks.",
        "Shape EQ after gain: trim mud around 200-400 Hz, tame harshness around 2.5-4 kHz, and add presence or air only if needed.",
        "Route to LR, keep the fader near unity to start, and build monitor sends slowly to avoid feedback.",
        "This is setup advice only; no OSC message, hardware change, DAW control, or live execution is authorized.",
    )


def build_payload(*, sqlite_path: Path | None = None) -> dict[str, Any]:
    db_path = build_sqlite_kb(sqlite_path or DEFAULT_SQLITE_PATH)
    return {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "sqlite_path": str(db_path),
        "devices": [asdict(device) for device in seed_devices()],
        "control_paths": [
            {
                **asdict(path),
                "requires_confirmation": path.requires_confirmation,
                "safe_to_execute": path.safe_to_execute,
            }
            for path in seed_control_paths()
        ],
        "device_summary": device_summary_lines(),
        "x32_control_summary": x32_control_summary_lines(),
        "x32_vocal_channel_advice": x32_vocal_channel_advice_lines(),
        "source_refs": X32_OSC_SOURCE_REFS,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "machine_proof": {
            "sqlite_kb_written": True,
            "manuals_fabricated": False,
            "operator_inventory_seed_used": True,
            "x32_osc_starting_point_recorded": True,
            "all_control_authority_false": all(value is False for value in AUTHORITY_BOUNDARY.values()),
            "hardware_control_performed": False,
            "osc_message_sent": False,
            "midi_message_sent": False,
            "daw_or_obs_control_performed": False,
            "external_send_performed": False,
            "secret_value_read_or_printed": False,
        },
    }


def render_operator_readback() -> str:
    lines = [
        "Niles rig KB seed is available.",
        "",
        *[f"- {line}" for line in device_summary_lines()],
        "",
        *[f"- {line}" for line in x32_control_summary_lines()],
        "",
        *[f"- {line}" for line in x32_vocal_channel_advice_lines()],
        "",
        "- No hardware, app, OSC, MIDI, DAW, OBS, send, or external action is authorized here.",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the deterministic Niles rig-control SQLite KB.")
    parser.add_argument("--sqlite-path", default=str(DEFAULT_SQLITE_PATH))
    parser.add_argument("--format", choices=("summary", "json"), default="summary")
    args = parser.parse_args(argv)
    payload = build_payload(sqlite_path=Path(args.sqlite_path))
    if args.format == "json":
        print(stable_json(payload), end="")
    else:
        print(render_operator_readback())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
