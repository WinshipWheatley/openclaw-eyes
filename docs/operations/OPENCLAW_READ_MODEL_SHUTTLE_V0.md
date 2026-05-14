# OpenClaw Read-Model Shuttle v0

Purpose: move generated read-model exports from canonical PC/WSL backend output
to the Mac generated-read-model mirror with explicit package metadata and a
returned importable manifest.

## Boundary

- PC/WSL `/home/openclaw` remains the canonical backend/evidence authority.
- Mac generated read-models are a mirror/app surface, not truth authority.
- Shuttle packages contain generated read-model/operator files only.
- Returned Mac manifests are metadata-only imports into Corpus Atlas.
- No runtime, agent, backend, tool, model, container, network, or truth-promotion authority is granted.
- No source files are moved, deleted, reorganized, or imported as raw private bodies.

## Prepare Package On PC/WSL

```bash
PYTHONDONTWRITEBYTECODE=1 python3 scripts/prepare_mac_read_model_shuttle.py --format operator
```

Default output root:

```text
/mnt/c/openclaw/shuttle/to_mac
```

Each package contains:

- `payload/generated_read_models/`
- `shuttle_manifest.json`
- `APPLY_ON_MAC.sh`
- `README.md`

## Apply On Mac

Move the package folder to the Mac, open a terminal inside it, then run:

```bash
bash APPLY_ON_MAC.sh
```

The script copies payload files into:

```text
/Users/hwinshipwheatley/openclaw_generated_read_models
```

It verifies sizes and hashes, then writes:

```text
mac_generated_read_models_manifest.json
RETURN_TO_PC_README.txt
```

## Import Returned Manifest On PC/WSL

Return the package folder or just `mac_generated_read_models_manifest.json` to
PC/WSL, then run one of:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 scripts/import_mac_read_model_shuttle.py --manifest /mnt/c/openclaw/mac_generated_read_models_manifest.json --format operator
```

```bash
PYTHONDONTWRITEBYTECODE=1 python3 scripts/import_mac_read_model_shuttle.py --package /mnt/c/openclaw/shuttle/from_mac/read_models_YYYYMMDD_HHMMSS --format operator
```

The import copies the returned manifest to:

```text
/home/openclaw/import_manifests/mac_generated_read_models_manifest.json
```

Then it imports metadata through the existing Mac Mirror Atlas / Corpus Atlas path
and reports generated-read-model mirror status, mirror mismatches, and Mac roots.
