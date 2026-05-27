# Safe Preview Provider Feasibility

Mac Quick Look is enough for the current invoice candidate. Backend safe preview remains not ready until a sandboxed provider is approved.

Current invoice review:
- Recommended provider: QUICKLOOK_MAC_CLIENT
- Backend preview generation needed now: false

Future untrusted documents:
- Recommended provider: DANGERZONE_BACKEND_PENDING_REVIEW
- Backend preview production ready: false

Dangerzone local spike:
- Status: BLOCKED_INSTALL_REQUIRED
- Version checked: 0.10.0
- Blocker: Dangerzone CLI/app is not installed locally.
- Blocker: Dangerzone on Linux expects Podman; podman is not installed locally.
- Blocker: Installing a new external document sanitizer package needs explicit install and AGPL packaging review.

Local tools:
- dangerzone: missing
- dangerzone-cli: missing
- docker: found
- libreoffice: missing
- podman: missing
- soffice: missing

Boundary:
- No document conversion, PDF generation, workbook read, container start, service start, email, Coupa, browser, ledger, or production mutation.
