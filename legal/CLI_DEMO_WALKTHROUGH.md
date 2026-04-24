# OpenClaw Legal CLI Demo Walkthrough

This walkthrough demonstrates the local-first Legal v0 spine with machine-readable CLI output. It uses temporary files under `/tmp` and does not require LLM, cloud, API, or network calls in the legal v0 spine.

## 1. Create Demo Sources

```bash
mkdir -p /tmp/oc-legal-demo/input
cat > /tmp/oc-legal-demo/input/engagement_notes.txt <<'EOF'
Client asked counsel to evaluate settlement posture before mediation.
EOF
cat > /tmp/oc-legal-demo/input/case_timeline.md <<'EOF'
# Case Timeline

- Settlement demand received after discovery.
EOF
```

## 2. Create A Matter

```bash
python3 -m legal.cli create-matter \
  --root /tmp/oc-legal-demo/matter \
  --matter-id demo-001 \
  --display-name "Demo Matter"
```

## 3. Register Sources

```bash
python3 -m legal.cli add-source \
  --root /tmp/oc-legal-demo/matter \
  --source /tmp/oc-legal-demo/input/engagement_notes.txt

python3 -m legal.cli add-source \
  --root /tmp/oc-legal-demo/matter \
  --source /tmp/oc-legal-demo/input/case_timeline.md
```

## 4. Extract All Registered Sources

```bash
python3 -m legal.cli extract-all \
  --root /tmp/oc-legal-demo/matter
```

The output lists per-source statuses such as `extracted`, `unsupported`, `no_text`, or `failed`.

## 5. Search Extracted Text

```bash
python3 -m legal.cli search \
  --root /tmp/oc-legal-demo/matter \
  --query settlement
```

Search is deterministic, literal, and case-insensitive.

## 6. Export A Markdown Search Report

```bash
python3 -m legal.cli report \
  --root /tmp/oc-legal-demo/matter \
  --query settlement \
  --report-name settlement-report
```

The report is written under the matter workspace `exports/` folder.

## 7. Export A Review Packet

```bash
python3 -m legal.cli review-packet \
  --root /tmp/oc-legal-demo/matter \
  --packet-name first-review
```

The review packet folder includes copies of the manifest, audit log, extracted text artifacts, extracted metadata, selected Markdown reports, and `packet_manifest.json`.

To exclude reports:

```bash
python3 -m legal.cli review-packet \
  --root /tmp/oc-legal-demo/matter \
  --no-reports
```

## 8. Create A Default Local Profile

```bash
python3 -m legal.cli default-profile \
  --firm-name "Example Law" \
  --output /tmp/oc-legal-demo/legal-profile.json
```

The deployment profile is a portable local-first config schema. It is not an installer.
