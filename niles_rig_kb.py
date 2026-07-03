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
    )


def x32_control_summary_lines() -> tuple[str, ...]:
    return (
        "X32 starting point: OSC over UDP port 10023, stress-tested against X32 Edit App first.",
        "Known research addresses: /xinfo, /xremote, /ch/{channel:02d}/mix/fader, /ch/{channel:02d}/mix/on, /main/st/mix/fader.",
        "All OSC rows are stored with safe_to_execute=false and requires_confirmation=true.",
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
