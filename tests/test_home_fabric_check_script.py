from pathlib import Path
import re
import subprocess


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts" / "home_fabric_check.sh"
SCRIPT = SCRIPT_PATH.read_text(encoding="utf-8")


def test_fabric_check_parses_and_prints_usage():
    parsed = subprocess.run(["bash", "-n", str(SCRIPT_PATH)], capture_output=True, text=True, check=False)
    assert parsed.returncode == 0, parsed.stderr

    helped = subprocess.run(["bash", str(SCRIPT_PATH), "--help"], capture_output=True, text=True, check=False)
    assert helped.returncode == 0, helped.stderr
    assert "Usage:" in helped.stdout
    assert "--strict" in helped.stdout


def test_fabric_check_covers_every_fabric_leg():
    for needle in (
        "netsh.exe interface portproxy show v4tov4",
        "windows_wsl_portproxy_resync.ps1",
        "tailscale ip -4",
        "tailscale.exe ip -4",
        'ssh -o BatchMode=yes -o ConnectTimeout=5 "$MAC_SSH_HOST" hostname',
        "shuttle/from_mac/read_model_sync_agent_status.json",
        "shuttle/from_mac/read_model_sync_completed.json",
        "/api/tags",
        "systemctl --user is-active",
        "wide_open_ports",
        'summary: fails=$FAILS warns=$WARNS',
    ):
        assert needle in SCRIPT, needle


def test_fabric_check_is_read_only():
    mutating = (
        r"portproxy\s+(add|delete|reset|set)",
        r"systemctl\s+(--user\s+)?(start|stop|restart|enable|disable)",
        r"tailscale(\.exe)?\s+(up|down|logout|set)",
        r"\brm\s+-",
        r"\btee\b",
        r">\s*/(?!dev/null)",
        r"New-NetFirewallRule",
    )
    for pattern in mutating:
        assert not re.search(pattern, SCRIPT), pattern


def test_fabric_check_defaults_match_the_documented_route():
    assert 'SSH_LISTEN_PORT="${OPENCLAW_WSL_SSH_LISTEN_PORT:-2222}"' in SCRIPT
    assert 'SHUTTLE_ROOT="${OPENCLAW_SHUTTLE_ROOT:-/mnt/e/openclaw}"' in SCRIPT
    assert 'MAC_SSH_HOST="${OPENCLAW_MAC_SSH_HOST:-mac}"' in SCRIPT
    assert 'OLLAMA_URL="${OPENCLAW_OLLAMA_URL:-http://127.0.0.1:11434}"' in SCRIPT
