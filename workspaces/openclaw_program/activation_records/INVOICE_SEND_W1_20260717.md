# Invoice Send W1 Activation Record - 2026-07-17

## Scope

W1 activates source-workbook selection and no-send verification/finalization only. Provider draft creation, external send, payment, money movement, ledger posting, paid marking, and source-workbook mutation remain false. `SEND_HOLD` remains active. W3/W4 are not activated by this record.

## Owner

- Owner command: `scripts/finalize_lamd_july_invoice.py`
- Generic verification/finalization: `invoice_workbook_finalizer.py`
- Source and published-artifact selection: `invoice_artifact_locator.py`
- Excel workers: `scripts/recalculate_invoice_with_excel.ps1` and `scripts/export_invoice_pdf_with_excel.ps1`

The owner defaults to dry-run. `--confirm` creates an isolated reconciliation copy, invokes one owned Windows Excel COM instance, verifies the result, exports only the selected sheet to a temporary PDF, and atomically publishes after all checks pass. It never enumerates or terminates ambient Excel processes.

## Live Proof

- Real source SHA-256: `a21ad71694fb291b956e59f837f287f3c410eb62cc8f11d2625f92c6ab8835a9`
- Source semantic markers before repair: 4; source mutation: false
- Final invoice: Live Arts MD, July 2026, `2026-1004`, `$100.00`
- Excel: `CalculateFullRebuild`, `xlDone`, two reopen checks
- Formula SHA before/after: `dae6f1ba6c6c4f672ccb64ebed9e17f462b164aa8f36d1b01ba6e25a687d5874`
- Recalculated workbook SHA-256: `4411d99a8bb0b5d4090b579129a5f41268851b71c21a875dcf654d2f1cfb9e1a`
- Independent subtotal / total / balance: `$100.00 / $100.00 / $100.00`
- PDF: one page, 178,656 bytes, SHA-256 `09f6f12b82d11108e9953e84612b00368413f81667f2a589be1156f33b88ac77`
- PDF text SHA-256: `0e373d74d1ba8cfcf487bcc57f4401a8383b9f2c813314225ebee81ca16c173a`
- Draft/provider/send/money/ledger actions: 0

Canary receipt: `/mnt/e/openclaw/artifacts/invoice_workbooks/w1_canaries/pc-codex-desktop-20260717-live-arts-july-v3/live_process_receipt.json`.

## Production Activation

- Production commit: `36b0a5ca`
- Owner run: `PUBLISHED_VERIFIED` at `2026-07-17T18:27:29+00:00`
- Run id: `invoice-w1-c46bd4613552a57f5196c69b`
- Package: `/mnt/e/openclaw/artifacts/invoice_workbooks/live_arts_md/2026-07/w1-finalized-2026-1004`
- Production workbook SHA-256: `e476354bb18ce836a92b11daa2188967ac210fb88a25cd496035c4cae271da12`
- Production PDF SHA-256: `a9f22070e97db9b780b95061e7d3373eb537171f48ee94895fb32e38e63d44fb`
- Formula freshness receipt: `invoice-w1-formula:dae6f1ba6c6c4f672ccb64eb`
- Artifact verification receipt: `invoice-w1-verify:e476354bb18ce836a92b11da`
- Canonical proof resolver: `FOUND`, manifest hashes verified, model/external actions false
- Exact second owner run: `IDEMPOTENT_REPLAY`; Excel and publication were not repeated
- Production receipt: `/home/openclaw/generated/system_knowledge/invoice_w1_lamd_july_receipt.json`

## Transaction Supersession

Fable found the W0 provisional and W1 finalized obligations both at `PREPARED`. Production commit `0eb56264` added an atomic lifecycle transition plus append-only decision table and update/delete denial triggers.

- W0 provisional `invoice-send-tx:2bd8efb929ecbed5376b2204`: `SUPERSEDED`
- W1 finalized `invoice-send-tx:495069a26823c4d47826c151`: sole Live Arts July `PREPARED`
- Decision: `invoice-send-decision:46aefafd5e78a792aa7651e2`
- Same-obligation multi-`PREPARED` conflicts: 0
- Exact transition replay: idempotent
- Post-transition Cassandra front-door replay: finalized transaction only, one canonical row
- Receipt: `/home/openclaw/Operator/from-codex/W1-LAMD-PROVISIONAL-SUPERSESSION-LIVE-RECEIPT-20260717-PC-Codex-Desktop.json`

## Mac Selected-Invoice Helper

Mac current-base commit `2f76530f79d1a85c35e3b3a3b9044335c8f60569` is installed as `/Applications/OpenClawExcelExportHelper.app`. LaunchServices resolves the bundle id to that owner; the installed arm64 binary SHA-256 `255f1724774a37706be8a5ece0638155f790cdcf4e10966fdb866a08666ed21c` matches the validated build.

The exact installed binary returned `SELECTED_INVOICE_ATOMIC_PUBLISH_SUCCEEDED` on a real isolated offline canary. Input SHA-256 `a5cbb556f9d9aed0880024a889db041f179effa63798aadaa352e9dda13b8d62` remained unchanged. The atomically published one-page output is 102,166 bytes, SHA-256 `40fcbdda636c78d81992dd3e6861054ad21bc614fedcf13cce8134680933478e`, with PDF structure, selected identity, baseline, and semantic-finality checks passed. Mac verification: 337 tests plus signed-helper and full Release builds passed.

Receipt: `/mnt/e/openclaw/codex_mac_bridge/from-codex-mac-desktop/MACSOL-W1-HELPER-SLICE-RECEIPT-20260717.md`.

## Mac Desktop Receiver Split

`mac_codex_desktop_event_receiver` is active under Fable's receiver-only bridge-notice contract. The loaded `com.openclaw.codex-desktop-bridge-receiver` owner reported `state=running`, active count 1, runs 2 after restart. A fresh mission produced one kqueue event, one append-only ledger path, and one atomic delivery notice in 90 ms; exact ACK latency was 58,835 ms, processed count 1, historical replay 0, and business dispatch 0. The notice explicitly states `Desktop seat auto-resumed: false` and `Human kick still required: true`.

`mac_codex_desktop_seat_auto_resume` remains `BLOCKED`: no documented/verified Codex Desktop resume endpoint exists. VS Code, UI automation, app focus, notifications, polling, and model invocation are not substitutes.

Receiver receipt: `/mnt/e/openclaw/codex_mac_bridge/from-codex-mac-desktop/MACSOL-W1-DESKTOP-RECEIVER-SLICE-RECEIPT-20260717-V2.md`.

## Fail-Closed Gates

- ambiguous, missing, zero-byte, or hash-mismatched source
- semantic `DRAFT`, `TBD`, `TODO`, or placeholder markers in workbook or PDF
- macros or external workbook links
- Excel calculation timeout or stale critical formula caches
- formula mutation or independent total mismatch
- missing, zero-byte, malformed, or multi-stage-unverified PDF
- existing package/receipt conflict

## Rollback

Stop invoking the owner command. No daemon or downstream provider/send path is introduced by W1. Preserve published package, failed-run directories, and receipts as immutable evidence; the source workbook remains unchanged.
