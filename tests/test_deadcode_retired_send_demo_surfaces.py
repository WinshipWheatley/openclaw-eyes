from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RETIRED_SEND_DEMO_SURFACES = (
    "send_demo_dashboard.py",
    "retry_send_demo_dashboard.sh",
)


def test_demo_dashboard_send_surfaces_are_retired_from_runtime_root():
    for relative_path in RETIRED_SEND_DEMO_SURFACES:
        assert not (ROOT / relative_path).exists(), relative_path


def test_retired_demo_dashboard_surfaces_are_not_gitignore_allowlisted():
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
    for relative_path in RETIRED_SEND_DEMO_SURFACES:
        assert f"!{relative_path}" not in gitignore

