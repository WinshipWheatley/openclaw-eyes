"""Export script for the Chief Dynamic Workflow Deferred Build packet."""

import argparse
from pathlib import Path

from chief_dynamic_workflow_deferred_build import write_models, DEFAULT_EXPORT_ROOT

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--export-dir", type=str, default=str(DEFAULT_EXPORT_ROOT))
    parser.add_argument("--bridge-dir", type=str, default="/mnt/e/openclaw/generated/read_models")
    args = parser.parse_args()

    export_path = Path(args.export_dir)
    bridge_path = Path(args.bridge_dir)

    print(f"Exporting to {export_path}...")
    write_models(export_path)

    if bridge_path.exists():
        print(f"Exporting to {bridge_path}...")
        write_models(bridge_path)
    else:
        print(f"Bridge path {bridge_path} not found. Skipping.")

if __name__ == "__main__":
    main()
