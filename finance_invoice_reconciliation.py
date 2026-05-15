"""Finance Invoice Helper Reconciliation v0 for OpenClaw.

This module maps non-canonical Repo B finance/invoice helpers into the
current OpenClaw governed architecture. It is planning metadata only: it does
not run Repo B code, access bank data, send email, create invoices for sending,
modify ledgers, or claim financial truth.
"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from business_ops_ledger import DEFAULT_DB_PATH, init_business_ops_ledger
from repo_b_runtime_intake import (
    DEFAULT_REPO_B_ROOT,
    EXPECTED_REMOTE_SLUG,
    remote_matches_expected,
    repo_metadata,
)
from work_board import DEFAULT_BOARD_ID, init_work_board_schema


ROOT = Path(__file__).resolve().parent
FINANCE_RECONCILIATION_VERSION = "finance_invoice_reconciliation_v0"
READ_MODEL_VERSION = "finance_invoice_reconciliation_read_model_v0"
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
JSON_EXPORT_NAME = "finance_invoice_reconciliation.json"
OPERATOR_EXPORT_NAME = "finance_invoice_reconciliation_OPERATOR.md"
SOURCE_REPO_B = "openclaw-runtime"
SOURCE_REPO_A = "openclaw-eyes"
REPO_B_CANONICAL_STATUS = "non_canonical_legacy"
CORE_CANONICAL_STATUS = "current_core"
MAX_SAFE_SOURCE_BYTES = 120_000

PRIMARY_REPO_B_FINANCE_FILES = (
    "chief_billing_brain.py",
    "chief_invoice_brain.py",
    "chief_financial_brain.py",
    "chief_cpa_brain.py",
    "budget_tracker.py",
)

CAPABILITY_KINDS = {
    "invoice_drafting",
    "billing_tracking",
    "receivable_tracking",
    "budget_tracking",
    "cpa_tax_support",
    "evidence_gathering",
    "client_payment_status",
    "reimbursement_tracking",
    "ledger_reconciliation",
    "email_draft_support",
    "report_generation",
    "unknown",
}

FUTURE_HOMES = {
    "finance_world_core",
    "business_ops_module",
    "evidence_helper",
    "invoice_helper",
    "cpa_support_reference",
    "project_capsule_candidate",
    "client_template_candidate",
    "reference_only_legacy",
    "blocked_no_go",
    "unknown_review",
}

REUSE_POLICIES = {
    "candidate_to_port",
    "candidate_to_wrap",
    "reference_only",
    "blocked_no_go",
    "needs_operator_review",
    "current_equivalent_exists",
    "superseded_candidate",
}

RISK_LEVELS = {"low", "medium", "high", "blocked"}

RISK_REASONS = {
    "direct_file_write",
    "external_send",
    "env_reference",
    "bank_or_payment_data",
    "tax_sensitive",
    "client_sensitive",
    "no_receipt_path",
    "broad_scan",
    "stale_architecture",
    "unknown",
}

BURDEN_REDUCTION_KINDS = {
    "reduces_invoice_prep_burden",
    "reduces_receivables_tracking_burden",
    "reduces_tax_evidence_burden",
    "reduces_client_email_draft_burden",
    "reduces_bank_csv_reconciliation_burden",
    "mainly_reference",
    "unknown",
}

REPORT_SECTIONS = {"summary", "candidates", "risks", "workflow"}

NO_AUTHORITY_FLAGS = {
    "finance_execution_allowed": False,
    "invoice_send_allowed": False,
    "email_send_allowed": False,
    "bank_access_allowed": False,
    "tax_filing_allowed": False,
    "external_api_allowed": False,
    "raw_private_ingest_allowed": False,
    "operator_approval_required": True,
    "financial_truth_claimed": False,
}

NO_GO_DIR_NAMES = {
    ".git",
    "__pycache__",
    ".venv",
    "venv",
    "node_modules",
    "secrets",
    "keys",
    "credentials",
    "private",
    "legal",
    "client",
    "bank",
    "banking",
}
NO_GO_FILE_NAMES = {".env", ".env.local", ".env.production", ".env.development"}
NO_GO_SUFFIXES = {".pem", ".key", ".p12", ".sqlite", ".db"}
SAFE_SOURCE_SUFFIXES = {".py", ".md", ".txt", ".sh"}


@dataclass(frozen=True)
class FinanceCandidateReview:
    candidate_id: str
    source_repo: str
    source_path: str
    source_commit: str
    canonical_status: str
    import_status: str
    purpose: str
    expected_inputs: str
    expected_outputs: str
    external_services: str
    file_io_summary: str
    sensitive_data_risk: str
    direct_execution_risk: str
    reusable_logic: str
    obsolete_or_unsafe_assumptions: str
    maps_to_current_architecture: str
    future_home: str
    reuse_policy: str
    risk_level: str
    burden_reduction: str
    safe_source_reviewed: bool


@dataclass(frozen=True)
class FinanceReconciliationResult:
    run_id: str
    db_path: str
    repo_b_root: str
    source_commit: str
    finance_candidate_count: int
    safe_source_reviewed_count: int
    high_risk_count: int
    blocked_no_go_count: int
    workflow_proposal_id: str
    work_board_card_count: int


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _row_id(prefix: str, *parts: object) -> str:
    digest = hashlib.sha256("\0".join(str(part) for part in parts).encode("utf-8")).hexdigest()
    return f"{prefix}_{digest[:20]}"


def _bool(value: bool) -> int:
    return 1 if value else 0


def _display_path(path: str | Path) -> str:
    path_obj = Path(path)
    try:
        return path_obj.resolve().relative_to(ROOT.resolve()).as_posix()
    except (OSError, ValueError):
        return path_obj.as_posix()


def _export_root_path(export_root: str | Path) -> Path:
    path = Path(export_root)
    if path.is_absolute():
        return path
    return ROOT / path


def _dict_rows(conn: sqlite3.Connection, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    return [dict(row) for row in conn.execute(sql, params).fetchall()]


def _table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone() is not None


def _is_no_go_path(relative_path: str) -> tuple[bool, str | None]:
    path = Path(relative_path)
    lower_parts = [part.lower() for part in path.parts]
    filename = lower_parts[-1] if lower_parts else ""
    suffix = Path(filename).suffix.lower()
    if any(part in NO_GO_DIR_NAMES for part in lower_parts[:-1]):
        return True, "no_go_directory"
    if filename in NO_GO_FILE_NAMES or filename.startswith(".env."):
        return True, "env_file"
    if suffix in NO_GO_SUFFIXES:
        return True, "secret_or_database_suffix"
    if any(token in filename for token in ("secret", "credential", "token", "keychain")):
        return True, "credential_like_filename"
    return False, None


def _safe_read_source(repo_root: Path, relative_path: str) -> tuple[str | None, str]:
    no_go, reason = _is_no_go_path(relative_path)
    if no_go:
        return None, reason or "no_go_path"
    source_path = repo_root / relative_path
    suffix = source_path.suffix.lower()
    if suffix not in SAFE_SOURCE_SUFFIXES:
        return None, "unsupported_suffix"
    try:
        stat = source_path.stat()
    except OSError:
        return None, "missing"
    if stat.st_size > MAX_SAFE_SOURCE_BYTES:
        return None, "too_large_for_bounded_review"
    try:
        return source_path.read_text(encoding="utf-8", errors="replace")[:MAX_SAFE_SOURCE_BYTES], "safe_source_reviewed"
    except OSError:
        return None, "read_error"


def _repo_b_metadata(repo_root: Path) -> dict[str, str]:
    if (repo_root / ".git").exists():
        metadata = repo_metadata(repo_root)
    else:
        metadata = {
            "source_remote": f"fixture:{EXPECTED_REMOTE_SLUG}",
            "source_branch": "fixture",
            "source_commit": "fixture",
        }
    return metadata


def _finance_candidate_paths_from_repo_b_intake(conn: sqlite3.Connection) -> list[str]:
    if not _table_exists(conn, "repo_b_module_candidates"):
        return []
    rows = conn.execute(
        """
SELECT DISTINCT relative_path
FROM repo_b_module_candidates
WHERE burden_reduction = 'reduces_finance_burden'
ORDER BY relative_path
""".strip()
    ).fetchall()
    return [row["relative_path"] for row in rows]


def _finance_candidate_paths(repo_root: Path, conn: sqlite3.Connection) -> list[str]:
    paths: list[str] = []
    for path in _finance_candidate_paths_from_repo_b_intake(conn):
        if path not in paths:
            paths.append(path)
    for path in PRIMARY_REPO_B_FINANCE_FILES:
        if (repo_root / path).exists() and path not in paths:
            paths.append(path)
    if not paths:
        for child in sorted(repo_root.iterdir()):
            if child.is_file() and any(token in child.name.lower() for token in ("billing", "invoice", "financial", "cpa", "budget")):
                paths.append(child.name)
    return paths


def _contains_any(text: str, tokens: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return any(token in lowered for token in tokens)


def _capabilities(relative_path: str, text: str | None) -> list[str]:
    combined = f"{relative_path}\n{text or ''}".lower()
    capabilities: set[str] = set()
    if _contains_any(combined, ("invoice", "billing_record", "invoice_no", "line items")):
        capabilities.add("invoice_drafting")
    if _contains_any(combined, ("billing", "payment", "paid", "due", "deposit", "invoice_counter")):
        capabilities.add("billing_tracking")
    if _contains_any(combined, ("outstanding", "receivable", "unpaid", "balance")):
        capabilities.add("receivable_tracking")
    if _contains_any(combined, ("budget", "cap", "spend", "cost", "runner")):
        capabilities.add("budget_tracking")
    if _contains_any(combined, ("cpa", "tax", "deduction", "quarterly", "schedule c", "1040")):
        capabilities.add("cpa_tax_support")
    if _contains_any(combined, ("receipt", "evidence", "document", "source", "proof")):
        capabilities.add("evidence_gathering")
    if _contains_any(combined, ("client", "payer", "customer", "payment_status", "client_name")):
        capabilities.add("client_payment_status")
    if _contains_any(combined, ("reimburse", "reimbursement")):
        capabilities.add("reimbursement_tracking")
    if _contains_any(combined, ("ledger", "csv", "jsonl", "reconcile", "expense")):
        capabilities.add("ledger_reconciliation")
    if _contains_any(combined, ("email", "followup", "send_reply", "draft", "message")):
        capabilities.add("email_draft_support")
    if _contains_any(combined, ("report", "summary", "markdown", "snapshot")):
        capabilities.add("report_generation")
    if not capabilities:
        capabilities.add("unknown")
    return sorted(capabilities)


def _risk_reasons(relative_path: str, text: str | None, import_status: str) -> list[str]:
    combined = f"{relative_path}\n{text or ''}".lower()
    reasons: set[str] = set()
    if import_status == "blocked_no_go":
        reasons.add("unknown")
    if _contains_any(combined, (".write_text", ".open(\"w", ".open('w", ".open(\"a", ".open('a", "json.dump", "csv.", "with open")):
        reasons.add("direct_file_write")
    if _contains_any(combined, ("send_reply", "chief_sender", "send_message", "telegram", "gmail", "subprocess.run")):
        reasons.add("external_send")
    if _contains_any(combined, (".env", "token", "api_key", "dotenv", "os.environ")):
        reasons.add("env_reference")
    if _contains_any(combined, ("bank", "stripe", "paypal", "venmo", "zelle", "payment", "deposit")):
        reasons.add("bank_or_payment_data")
    if _contains_any(combined, ("tax", "cpa", "deduction", "quarterly", "schedule c", "1040")):
        reasons.add("tax_sensitive")
    if _contains_any(combined, ("client", "client_name", "client_email", "payer", "customer")):
        reasons.add("client_sensitive")
    if _contains_any(combined, ("os.walk", ".rglob", "glob(")):
        reasons.add("broad_scan")
    if _contains_any(combined, ("/mnt/c", "/openclawshared", "while true", "ollama_call", "claude_call", "nemotron_call")):
        reasons.add("stale_architecture")
    if "direct_file_write" in reasons and not _contains_any(combined, ("operator_action", "receipt_id", "approval_required")):
        reasons.add("no_receipt_path")
    if not reasons:
        reasons.add("unknown")
    return sorted(reasons)


def _risk_level(reasons: list[str], import_status: str) -> str:
    if import_status == "blocked_no_go":
        return "blocked"
    high = {"external_send", "bank_or_payment_data", "tax_sensitive", "client_sensitive", "env_reference", "no_receipt_path"}
    if any(reason in high for reason in reasons):
        return "high"
    if any(reason in {"direct_file_write", "broad_scan", "stale_architecture"} for reason in reasons):
        return "medium"
    return "low"


def _future_home(relative_path: str, capabilities: list[str], risk_level: str) -> str:
    name = Path(relative_path).name.lower()
    if risk_level == "blocked":
        return "blocked_no_go"
    if "cpa_tax_support" in capabilities or "cpa" in name:
        return "cpa_support_reference"
    if "invoice_drafting" in capabilities or "invoice" in name:
        return "invoice_helper"
    if "budget_tracking" in capabilities or "budget" in name:
        return "business_ops_module"
    if "evidence_gathering" in capabilities:
        return "evidence_helper"
    if "billing_tracking" in capabilities or "receivable_tracking" in capabilities:
        return "finance_world_core"
    if relative_path.lower().endswith(".md"):
        return "reference_only_legacy"
    return "unknown_review"


def _reuse_policy(relative_path: str, capabilities: list[str], reasons: list[str], risk_level: str) -> str:
    if risk_level == "blocked":
        return "blocked_no_go"
    name = Path(relative_path).name.lower()
    if name == "chief_billing_brain.py":
        return "candidate_to_wrap"
    if name in {"chief_invoice_brain.py", "chief_financial_brain.py"}:
        return "candidate_to_port"
    if name == "chief_cpa_brain.py":
        return "reference_only"
    if name == "budget_tracker.py":
        return "reference_only"
    if "external_send" in reasons or "env_reference" in reasons or "bank_or_payment_data" in reasons:
        return "needs_operator_review"
    if "invoice_drafting" in capabilities or "billing_tracking" in capabilities or "receivable_tracking" in capabilities:
        return "candidate_to_port"
    if "budget_tracking" in capabilities:
        return "reference_only"
    if relative_path.lower().endswith(".md"):
        return "reference_only"
    return "needs_operator_review"


def _burden_reduction(capabilities: list[str], relative_path: str) -> str:
    if "invoice_drafting" in capabilities:
        return "reduces_invoice_prep_burden"
    if "receivable_tracking" in capabilities or "client_payment_status" in capabilities or "billing_tracking" in capabilities:
        return "reduces_receivables_tracking_burden"
    if "cpa_tax_support" in capabilities:
        return "reduces_tax_evidence_burden"
    if "email_draft_support" in capabilities:
        return "reduces_client_email_draft_burden"
    if "ledger_reconciliation" in capabilities:
        return "reduces_bank_csv_reconciliation_burden"
    if relative_path.lower().endswith(".md"):
        return "mainly_reference"
    return "unknown"


def _purpose(relative_path: str, capabilities: list[str]) -> str:
    name = Path(relative_path).name
    if name == "chief_billing_brain.py":
        return "Legacy conversational billing recorder for invoices, payments, followups, and receipts."
    if name == "chief_invoice_brain.py":
        return "Legacy invoice text generator and tracker writer."
    if name == "chief_financial_brain.py":
        return "Legacy finance report generator over billing/payment records."
    if name == "chief_cpa_brain.py":
        return "Legacy CPA/tax support notebook for deductions, expense logs, and CPA-ready summaries."
    if name == "budget_tracker.py":
        return "Legacy local AI spend/budget tracker with caps and logging."
    return f"Repo B finance-related candidate classified as {', '.join(capabilities)}."


def _summaries(relative_path: str, text: str | None, capabilities: list[str], reasons: list[str]) -> dict[str, str]:
    name = Path(relative_path).name
    writes = sorted(set(re.findall(r"[/~\w.-]+(?:\.csv|\.jsonl|\.json|\.md|\.txt|\.log)", text or "")))[:8]
    models = [token for token in ("ollama_call", "claude_call", "nemotron_call") if token in (text or "")]
    external = []
    if "external_send" in reasons:
        external.append("legacy send/subprocess path")
    if models:
        external.extend(models)
    return {
        "expected_inputs": {
            "chief_billing_brain.py": "Conversational billing/payment/followup/receipt facts from the operator.",
            "chief_invoice_brain.py": "Legacy invoice request text plus client/service/amount style fields.",
            "chief_financial_brain.py": "Legacy billing records, payments, tax constants, and finance report request.",
            "chief_cpa_brain.py": "Expense facts, tax docs metadata, deduction categories, and CPA questions.",
            "budget_tracker.py": "Local runner spend events and budget classification metadata.",
        }.get(name, "Finance-related metadata or source fields; exact live inputs require operator review."),
        "expected_outputs": {
            "chief_billing_brain.py": "CSV/JSONL billing records, session state, and legacy operator replies.",
            "chief_invoice_brain.py": "Invoice text files and tracker CSV rows.",
            "chief_financial_brain.py": "Markdown finance summary/report.",
            "chief_cpa_brain.py": "Expense JSON and CPA log Markdown.",
            "budget_tracker.py": "Budget state JSON/log rows and stop/warn decisions.",
        }.get(name, "Candidate metadata, checklist, report, or helper output after governed redesign."),
        "external_services": ", ".join(external) if external else "none detected in bounded source review",
        "file_io_summary": ", ".join(writes) if writes else "metadata-only review; no concrete write path extracted",
        "sensitive_data_risk": _sensitive_risk_text(capabilities, reasons),
        "direct_execution_risk": _direct_risk_text(reasons),
        "reusable_logic": _reusable_logic_text(capabilities, name),
        "obsolete_or_unsafe_assumptions": _obsolete_text(reasons, name),
        "maps_to_current_architecture": _architecture_mapping(capabilities),
    }


def _sensitive_risk_text(capabilities: list[str], reasons: list[str]) -> str:
    risks = []
    if "tax_sensitive" in reasons or "cpa_tax_support" in capabilities:
        risks.append("tax/CPA-sensitive")
    if "client_sensitive" in reasons:
        risks.append("client-sensitive")
    if "bank_or_payment_data" in reasons:
        risks.append("payment/bank-adjacent")
    if "env_reference" in reasons:
        risks.append("env/credential-adjacent")
    return ", ".join(risks) if risks else "low from bounded source review; real finance evidence remains approval-gated"


def _direct_risk_text(reasons: list[str]) -> str:
    risks = []
    if "direct_file_write" in reasons:
        risks.append("direct file writes")
    if "external_send" in reasons:
        risks.append("legacy send/subprocess path")
    if "broad_scan" in reasons:
        risks.append("broad scan reference")
    if "stale_architecture" in reasons:
        risks.append("stale /mnt/c or model-call runtime assumptions")
    return ", ".join(risks) if risks else "no direct execution risk detected in bounded source review"


def _reusable_logic_text(capabilities: list[str], name: str) -> str:
    if name == "chief_billing_brain.py":
        return "Question flow, normalized billing record schema, invoice/payment/followup/receipt categories, and correction handling."
    if name == "chief_invoice_brain.py":
        return "Invoice draft field ordering and tracker row shape, after removing direct writes/sends."
    if name == "chief_financial_brain.py":
        return "Outstanding invoice/payment summary structure as non-truth advisory report logic."
    if name == "chief_cpa_brain.py":
        return "Deduction category checklist and CPA evidence prompts as reference-only guarded prompts."
    if name == "budget_tracker.py":
        return "Budget cap and local spend warning heuristics for business-ops governance."
    return f"Potentially reusable {', '.join(capabilities)} concepts after operator review."


def _obsolete_text(reasons: list[str], name: str) -> str:
    notes = []
    if "stale_architecture" in reasons:
        notes.append("legacy paths/model calls/runtime loop assumptions")
    if "external_send" in reasons:
        notes.append("direct send path must be replaced by approval-gated drafts")
    if "direct_file_write" in reasons:
        notes.append("direct writes need receipt-backed OpenClaw storage")
    if "tax_sensitive" in reasons:
        notes.append("tax support must remain evidence/reference only unless separately approved")
    if not notes:
        notes.append(f"{name} remains non-canonical until port/wrap review")
    return "; ".join(notes)


def _architecture_mapping(capabilities: list[str]) -> str:
    mappings = ["Finance world/domain", "Work Board", "Agent Work Packets", "Operator Action approval path"]
    if "evidence_gathering" in capabilities or "ledger_reconciliation" in capabilities:
        mappings.append("Approved evidence packet / Report Bridge style receipt trail")
    if "invoice_drafting" in capabilities or "email_draft_support" in capabilities:
        mappings.append("draft-only invoice/email packet with no send authority")
    if "cpa_tax_support" in capabilities:
        mappings.append("Guardian boundary review for tax-sensitive evidence")
    return " / ".join(mappings)


def _sql_statements() -> tuple[str, ...]:
    return (
        """
CREATE TABLE IF NOT EXISTS finance_invoice_reconciliation_runs (
  run_id TEXT PRIMARY KEY,
  reconciliation_version TEXT NOT NULL,
  created_at TEXT NOT NULL,
  completed_at TEXT,
  repo_b_root TEXT NOT NULL,
  source_commit TEXT NOT NULL,
  finance_candidate_count INTEGER NOT NULL DEFAULT 0,
  safe_source_reviewed_count INTEGER NOT NULL DEFAULT 0,
  high_risk_count INTEGER NOT NULL DEFAULT 0,
  blocked_no_go_count INTEGER NOT NULL DEFAULT 0,
  workflow_proposal_id TEXT,
  work_board_card_count INTEGER NOT NULL DEFAULT 0,
  finance_execution_allowed INTEGER NOT NULL DEFAULT 0,
  invoice_send_allowed INTEGER NOT NULL DEFAULT 0,
  email_send_allowed INTEGER NOT NULL DEFAULT 0,
  bank_access_allowed INTEGER NOT NULL DEFAULT 0,
  tax_filing_allowed INTEGER NOT NULL DEFAULT 0,
  external_api_allowed INTEGER NOT NULL DEFAULT 0,
  raw_private_ingest_allowed INTEGER NOT NULL DEFAULT 0,
  operator_approval_required INTEGER NOT NULL DEFAULT 1,
  financial_truth_claimed INTEGER NOT NULL DEFAULT 0,
  notes TEXT NOT NULL
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS finance_candidate_sources (
  candidate_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  source_repo TEXT NOT NULL,
  source_path TEXT NOT NULL,
  source_commit TEXT NOT NULL,
  canonical_status TEXT NOT NULL,
  import_status TEXT NOT NULL,
  purpose TEXT NOT NULL,
  expected_inputs TEXT NOT NULL,
  expected_outputs TEXT NOT NULL,
  external_services TEXT NOT NULL,
  file_io_summary TEXT NOT NULL,
  sensitive_data_risk TEXT NOT NULL,
  direct_execution_risk TEXT NOT NULL,
  reusable_logic TEXT NOT NULL,
  obsolete_or_unsafe_assumptions TEXT NOT NULL,
  maps_to_current_architecture TEXT NOT NULL,
  future_home TEXT NOT NULL,
  reuse_policy TEXT NOT NULL,
  risk_level TEXT NOT NULL,
  burden_reduction TEXT NOT NULL,
  safe_source_reviewed INTEGER NOT NULL DEFAULT 0,
  execution_allowed INTEGER NOT NULL DEFAULT 0,
  financial_truth_claimed INTEGER NOT NULL DEFAULT 0,
  send_allowed INTEGER NOT NULL DEFAULT 0,
  bank_access_allowed INTEGER NOT NULL DEFAULT 0,
  operator_approval_required INTEGER NOT NULL DEFAULT 1,
  raw_body_stored INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  UNIQUE(source_repo, source_commit, source_path)
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS finance_candidate_capabilities (
  capability_id TEXT PRIMARY KEY,
  candidate_id TEXT NOT NULL,
  capability_kind TEXT NOT NULL,
  source_path TEXT NOT NULL,
  evidence_basis TEXT NOT NULL,
  execution_allowed INTEGER NOT NULL DEFAULT 0,
  financial_truth_claimed INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS finance_candidate_risks (
  risk_id TEXT PRIMARY KEY,
  candidate_id TEXT NOT NULL,
  risk_reason TEXT NOT NULL,
  risk_level TEXT NOT NULL,
  source_path TEXT NOT NULL,
  evidence_basis TEXT NOT NULL,
  operator_review_required INTEGER NOT NULL DEFAULT 1,
  execution_allowed INTEGER NOT NULL DEFAULT 0,
  raw_private_ingest_allowed INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS finance_workflow_proposals (
  workflow_proposal_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  title TEXT NOT NULL,
  purpose TEXT NOT NULL,
  operator_inputs_needed TEXT NOT NULL,
  allowed_evidence_types TEXT NOT NULL,
  disallowed_evidence_types TEXT NOT NULL,
  expected_outputs TEXT NOT NULL,
  work_board_integration TEXT NOT NULL,
  operator_action_requirements TEXT NOT NULL,
  no_send_policy TEXT NOT NULL,
  no_bank_scrape_policy TEXT NOT NULL,
  receipt_evidence_handling TEXT NOT NULL,
  next_safe_move TEXT NOT NULL,
  proposal_only INTEGER NOT NULL DEFAULT 1,
  execution_allowed INTEGER NOT NULL DEFAULT 0,
  invoice_send_allowed INTEGER NOT NULL DEFAULT 0,
  email_send_allowed INTEGER NOT NULL DEFAULT 0,
  bank_access_allowed INTEGER NOT NULL DEFAULT 0,
  operator_approval_required INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS finance_evidence_requirements (
  evidence_requirement_id TEXT PRIMARY KEY,
  workflow_proposal_id TEXT NOT NULL,
  evidence_kind TEXT NOT NULL,
  requirement_text TEXT NOT NULL,
  allowed INTEGER NOT NULL DEFAULT 1,
  sensitivity_level TEXT NOT NULL,
  raw_private_ingest_allowed INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS finance_next_safe_moves (
  next_safe_move_id TEXT PRIMARY KEY,
  workflow_proposal_id TEXT NOT NULL,
  move_order INTEGER NOT NULL,
  next_safe_move TEXT NOT NULL,
  routed_agent TEXT NOT NULL,
  work_board_card_id TEXT,
  approval_required INTEGER NOT NULL DEFAULT 1,
  execution_allowed INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS finance_query_receipts (
  query_receipt_id TEXT PRIMARY KEY,
  query_kind TEXT NOT NULL,
  filter_value TEXT,
  result_count INTEGER NOT NULL DEFAULT 0,
  generated_at TEXT NOT NULL,
  raw_body_stored INTEGER NOT NULL DEFAULT 0,
  execution_allowed INTEGER NOT NULL DEFAULT 0
)
""".strip(),
        "CREATE INDEX IF NOT EXISTS idx_finance_sources_path ON finance_candidate_sources(source_path)",
        "CREATE INDEX IF NOT EXISTS idx_finance_sources_reuse ON finance_candidate_sources(reuse_policy)",
        "CREATE INDEX IF NOT EXISTS idx_finance_capabilities_kind ON finance_candidate_capabilities(capability_kind)",
        "CREATE INDEX IF NOT EXISTS idx_finance_risks_reason ON finance_candidate_risks(risk_reason)",
    )


def init_finance_invoice_reconciliation_schema(db_path: str | Path | None = None) -> str:
    path = str(db_path) if db_path is not None else DEFAULT_DB_PATH
    init_business_ops_ledger(path)
    conn = sqlite3.connect(path)
    try:
        for statement in _sql_statements():
            conn.execute(statement)
        conn.commit()
    finally:
        conn.close()
    return path


def finance_invoice_reconciliation_table_names(db_path: str | Path | None = None) -> tuple[str, ...]:
    path = init_finance_invoice_reconciliation_schema(db_path)
    conn = sqlite3.connect(path)
    try:
        rows = conn.execute(
            """
SELECT name FROM sqlite_master
WHERE type = 'table' AND name LIKE 'finance_%'
ORDER BY name
""".strip()
        ).fetchall()
        return tuple(row[0] for row in rows)
    finally:
        conn.close()


def _insert_run(conn: sqlite3.Connection, *, run_id: str, repo_b_root: Path, source_commit: str, now: str) -> None:
    conn.execute(
        """
INSERT INTO finance_invoice_reconciliation_runs (
  run_id, reconciliation_version, created_at, repo_b_root, source_commit,
  notes
) VALUES (?, ?, ?, ?, ?, ?)
ON CONFLICT(run_id) DO UPDATE SET
  repo_b_root = excluded.repo_b_root,
  source_commit = excluded.source_commit,
  finance_execution_allowed = 0,
  invoice_send_allowed = 0,
  email_send_allowed = 0,
  bank_access_allowed = 0,
  tax_filing_allowed = 0,
  external_api_allowed = 0,
  raw_private_ingest_allowed = 0,
  operator_approval_required = 1,
  financial_truth_claimed = 0,
  notes = excluded.notes
""".strip(),
        (
            run_id,
            FINANCE_RECONCILIATION_VERSION,
            now,
            repo_b_root.as_posix(),
            source_commit,
            "Metadata-only reconciliation. Repo B finance code remains non-canonical and unexecuted.",
        ),
    )


def _review_candidate(repo_root: Path, relative_path: str, source_commit: str) -> tuple[FinanceCandidateReview, list[str], list[str]]:
    no_go, no_go_reason = _is_no_go_path(relative_path)
    text, read_status = _safe_read_source(repo_root, relative_path)
    import_status = "blocked_no_go" if no_go else ("safe_source_reviewed" if text is not None else "metadata_scanned_only")
    capabilities = _capabilities(relative_path, text)
    reasons = _risk_reasons(relative_path, text, import_status)
    risk_level = _risk_level(reasons, import_status)
    future_home = _future_home(relative_path, capabilities, risk_level)
    reuse_policy = _reuse_policy(relative_path, capabilities, reasons, risk_level)
    burden = _burden_reduction(capabilities, relative_path)
    summaries = _summaries(relative_path, text, capabilities, reasons)
    if no_go:
        summaries["obsolete_or_unsafe_assumptions"] = f"Path skipped as no-go metadata only: {no_go_reason}."
        summaries["sensitive_data_risk"] = "blocked no-go path; content not read"
        summaries["direct_execution_risk"] = "unknown; content not read"
    candidate_id = _row_id("finrecsource", SOURCE_REPO_B, source_commit, relative_path)
    review = FinanceCandidateReview(
        candidate_id=candidate_id,
        source_repo=SOURCE_REPO_B,
        source_path=relative_path,
        source_commit=source_commit,
        canonical_status=REPO_B_CANONICAL_STATUS,
        import_status=import_status,
        purpose=_purpose(relative_path, capabilities),
        expected_inputs=summaries["expected_inputs"],
        expected_outputs=summaries["expected_outputs"],
        external_services=summaries["external_services"],
        file_io_summary=summaries["file_io_summary"],
        sensitive_data_risk=summaries["sensitive_data_risk"],
        direct_execution_risk=summaries["direct_execution_risk"],
        reusable_logic=summaries["reusable_logic"],
        obsolete_or_unsafe_assumptions=summaries["obsolete_or_unsafe_assumptions"],
        maps_to_current_architecture=summaries["maps_to_current_architecture"],
        future_home=future_home,
        reuse_policy=reuse_policy,
        risk_level=risk_level,
        burden_reduction=burden,
        safe_source_reviewed=text is not None and read_status == "safe_source_reviewed",
    )
    return review, capabilities, reasons


def _upsert_candidate(
    conn: sqlite3.Connection,
    *,
    review: FinanceCandidateReview,
    capabilities: list[str],
    reasons: list[str],
    run_id: str,
    now: str,
) -> None:
    conn.execute(
        """
INSERT INTO finance_candidate_sources (
  candidate_id, run_id, source_repo, source_path, source_commit,
  canonical_status, import_status, purpose, expected_inputs, expected_outputs,
  external_services, file_io_summary, sensitive_data_risk, direct_execution_risk,
  reusable_logic, obsolete_or_unsafe_assumptions, maps_to_current_architecture,
  future_home, reuse_policy, risk_level, burden_reduction, safe_source_reviewed,
  execution_allowed, financial_truth_claimed, send_allowed, bank_access_allowed,
  operator_approval_required, raw_body_stored, created_at
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
  0, 0, 0, 0, 1, 0, ?)
ON CONFLICT(source_repo, source_commit, source_path) DO UPDATE SET
  run_id = excluded.run_id,
  canonical_status = excluded.canonical_status,
  import_status = excluded.import_status,
  purpose = excluded.purpose,
  expected_inputs = excluded.expected_inputs,
  expected_outputs = excluded.expected_outputs,
  external_services = excluded.external_services,
  file_io_summary = excluded.file_io_summary,
  sensitive_data_risk = excluded.sensitive_data_risk,
  direct_execution_risk = excluded.direct_execution_risk,
  reusable_logic = excluded.reusable_logic,
  obsolete_or_unsafe_assumptions = excluded.obsolete_or_unsafe_assumptions,
  maps_to_current_architecture = excluded.maps_to_current_architecture,
  future_home = excluded.future_home,
  reuse_policy = excluded.reuse_policy,
  risk_level = excluded.risk_level,
  burden_reduction = excluded.burden_reduction,
  safe_source_reviewed = excluded.safe_source_reviewed,
  execution_allowed = 0,
  financial_truth_claimed = 0,
  send_allowed = 0,
  bank_access_allowed = 0,
  operator_approval_required = 1,
  raw_body_stored = 0
""".strip(),
        (
            review.candidate_id,
            run_id,
            review.source_repo,
            review.source_path,
            review.source_commit,
            review.canonical_status,
            review.import_status,
            review.purpose,
            review.expected_inputs,
            review.expected_outputs,
            review.external_services,
            review.file_io_summary,
            review.sensitive_data_risk,
            review.direct_execution_risk,
            review.reusable_logic,
            review.obsolete_or_unsafe_assumptions,
            review.maps_to_current_architecture,
            review.future_home,
            review.reuse_policy,
            review.risk_level,
            review.burden_reduction,
            _bool(review.safe_source_reviewed),
            now,
        ),
    )
    conn.execute("DELETE FROM finance_candidate_capabilities WHERE candidate_id = ?", (review.candidate_id,))
    conn.execute("DELETE FROM finance_candidate_risks WHERE candidate_id = ?", (review.candidate_id,))
    for capability in capabilities:
        if capability not in CAPABILITY_KINDS:
            capability = "unknown"
        conn.execute(
            """
INSERT INTO finance_candidate_capabilities (
  capability_id, candidate_id, capability_kind, source_path,
  evidence_basis, execution_allowed, financial_truth_claimed, created_at
) VALUES (?, ?, ?, ?, ?, 0, 0, ?)
""".strip(),
            (
                _row_id("finreccap", review.candidate_id, capability),
                review.candidate_id,
                capability,
                review.source_path,
                "filename_and_bounded_safe_source" if review.safe_source_reviewed else "filename_metadata_only",
                now,
            ),
        )
    for reason in reasons:
        if reason not in RISK_REASONS:
            reason = "unknown"
        conn.execute(
            """
INSERT INTO finance_candidate_risks (
  risk_id, candidate_id, risk_reason, risk_level, source_path,
  evidence_basis, operator_review_required, execution_allowed,
  raw_private_ingest_allowed, created_at
) VALUES (?, ?, ?, ?, ?, ?, 1, 0, 0, ?)
""".strip(),
            (
                _row_id("finrecrisk", review.candidate_id, reason),
                review.candidate_id,
                reason,
                review.risk_level,
                review.source_path,
                "bounded_source_pattern" if review.safe_source_reviewed else "metadata_only_or_no_go",
                now,
            ),
        )


def _workflow_payload() -> dict[str, Any]:
    return {
        "title": "Finance Invoice Helper v0 - Invoice/Receivables Evidence Packet Builder",
        "purpose": (
            "Turn an operator finance request into a reviewable invoice/receivables evidence packet, "
            "checklist, and draft work packet without sending email, scraping banks, or claiming truth."
        ),
        "operator_inputs_needed": (
            "Client/project label; service date or date range; service description; amount/deposit/balance if known; "
            "due date/payment status if known; relevant approved notes/receipts; whether the desired output is invoice context, "
            "follow-up draft, or receivable status review."
        ),
        "allowed_evidence_types": (
            "Operator-provided finance facts, approved OpenClaw metadata/read-models, bounded approved document excerpts, "
            "manually supplied payment confirmation metadata, and explicit receipt/evidence links."
        ),
        "disallowed_evidence_types": (
            "Raw bank portal scraping, unapproved tax/legal/client raw documents, secrets/env files, private roots, automatic email sends, "
            "invoice finalization for sending, and financial truth claims without evidence."
        ),
        "expected_outputs": (
            "Finance Work Board card, evidence requirements checklist, draft invoice context packet, draft follow-up context packet, "
            "and approval-gated next safe move."
        ),
        "work_board_integration": (
            "Create metadata-only Finance World cards for review/planning; board cards never execute, approve, send, or edit ledgers."
        ),
        "operator_action_requirements": (
            "Any future invoice creation, file write, email send, or ledger change requires an explicit Operator Action request and approval."
        ),
        "no_send_policy": "No invoice, payment follow-up, email, SMS, or external communication is sent by this workflow.",
        "no_bank_scrape_policy": "No bank portal, payment provider, or private account scraping is allowed.",
        "receipt_evidence_handling": (
            "Every fact should point to an approved evidence reference or operator-provided note; raw private bodies remain out of this lane."
        ),
        "next_safe_move": (
            "Ask the operator for one receivable or invoice target and build a metadata-only evidence packet/work packet before any real invoice work."
        ),
    }


def _evidence_requirements() -> list[dict[str, Any]]:
    return [
        {
            "evidence_kind": "operator_invoice_fact",
            "requirement_text": "Operator-supplied client/project, service description, amount, and date/range.",
            "allowed": True,
            "sensitivity_level": "finance_metadata",
        },
        {
            "evidence_kind": "approved_receipt_or_note",
            "requirement_text": "Approved receipt, note, or bounded excerpt that supports the invoice or payment status.",
            "allowed": True,
            "sensitivity_level": "bounded_evidence",
        },
        {
            "evidence_kind": "bank_portal_scrape",
            "requirement_text": "Bank or payment-portal scraping is blocked in v0.",
            "allowed": False,
            "sensitivity_level": "blocked_private",
        },
        {
            "evidence_kind": "tax_or_legal_raw_body",
            "requirement_text": "Raw tax/legal/client document bodies are blocked unless a future approved lane explicitly allows a bounded excerpt.",
            "allowed": False,
            "sensitivity_level": "blocked_private",
        },
        {
            "evidence_kind": "email_send",
            "requirement_text": "Emails may be drafted as context later, but sending is blocked and requires separate approval.",
            "allowed": False,
            "sensitivity_level": "external_action",
        },
    ]


def _insert_workflow(conn: sqlite3.Connection, *, run_id: str, now: str) -> str:
    workflow = _workflow_payload()
    workflow_id = "finance_invoice_helper_v0_proposal"
    conn.execute(
        """
INSERT INTO finance_workflow_proposals (
  workflow_proposal_id, run_id, title, purpose, operator_inputs_needed,
  allowed_evidence_types, disallowed_evidence_types, expected_outputs,
  work_board_integration, operator_action_requirements, no_send_policy,
  no_bank_scrape_policy, receipt_evidence_handling, next_safe_move,
  proposal_only, execution_allowed, invoice_send_allowed, email_send_allowed,
  bank_access_allowed, operator_approval_required, created_at
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 0, 0, 0, 0, 1, ?)
ON CONFLICT(workflow_proposal_id) DO UPDATE SET
  run_id = excluded.run_id,
  title = excluded.title,
  purpose = excluded.purpose,
  operator_inputs_needed = excluded.operator_inputs_needed,
  allowed_evidence_types = excluded.allowed_evidence_types,
  disallowed_evidence_types = excluded.disallowed_evidence_types,
  expected_outputs = excluded.expected_outputs,
  work_board_integration = excluded.work_board_integration,
  operator_action_requirements = excluded.operator_action_requirements,
  no_send_policy = excluded.no_send_policy,
  no_bank_scrape_policy = excluded.no_bank_scrape_policy,
  receipt_evidence_handling = excluded.receipt_evidence_handling,
  next_safe_move = excluded.next_safe_move,
  proposal_only = 1,
  execution_allowed = 0,
  invoice_send_allowed = 0,
  email_send_allowed = 0,
  bank_access_allowed = 0,
  operator_approval_required = 1
""".strip(),
        (
            workflow_id,
            run_id,
            workflow["title"],
            workflow["purpose"],
            workflow["operator_inputs_needed"],
            workflow["allowed_evidence_types"],
            workflow["disallowed_evidence_types"],
            workflow["expected_outputs"],
            workflow["work_board_integration"],
            workflow["operator_action_requirements"],
            workflow["no_send_policy"],
            workflow["no_bank_scrape_policy"],
            workflow["receipt_evidence_handling"],
            workflow["next_safe_move"],
            now,
        ),
    )
    conn.execute("DELETE FROM finance_evidence_requirements WHERE workflow_proposal_id = ?", (workflow_id,))
    for requirement in _evidence_requirements():
        conn.execute(
            """
INSERT INTO finance_evidence_requirements (
  evidence_requirement_id, workflow_proposal_id, evidence_kind,
  requirement_text, allowed, sensitivity_level, raw_private_ingest_allowed,
  created_at
) VALUES (?, ?, ?, ?, ?, ?, 0, ?)
""".strip(),
            (
                _row_id("finrecev", workflow_id, requirement["evidence_kind"]),
                workflow_id,
                requirement["evidence_kind"],
                requirement["requirement_text"],
                _bool(requirement["allowed"]),
                requirement["sensitivity_level"],
                now,
            ),
        )
    moves = [
        "Review the Repo B finance helper map; do not run old code.",
        "Choose one real receivable/invoice target and provide only safe metadata/evidence references.",
        "Build an approved evidence packet and draft work packet before any invoice file or email output.",
    ]
    conn.execute("DELETE FROM finance_next_safe_moves WHERE workflow_proposal_id = ?", (workflow_id,))
    for index, move in enumerate(moves, start=1):
        conn.execute(
            """
INSERT INTO finance_next_safe_moves (
  next_safe_move_id, workflow_proposal_id, move_order, next_safe_move,
  routed_agent, work_board_card_id, approval_required, execution_allowed,
  created_at
) VALUES (?, ?, ?, ?, 'chief', NULL, 1, 0, ?)
""".strip(),
            (_row_id("finrecmove", workflow_id, index), workflow_id, index, move, now),
        )
    return workflow_id


def _ensure_finance_work_board_cards(
    conn: sqlite3.Connection,
    *,
    run_id: str,
    workflow_proposal_id: str,
    now: str,
) -> int:
    board_id = DEFAULT_BOARD_ID
    conn.execute(
        """
INSERT INTO work_boards (
  board_id, board_name, board_version, description, created_at, updated_at,
  direct_execution_allowed, auto_approval_allowed, auto_execute_allowed,
  agent_activation_allowed
) VALUES (?, 'OpenClaw Work Board', 'openclaw_work_board_v0', ?, ?, ?, 0, 0, 0, 0)
ON CONFLICT(board_id) DO UPDATE SET updated_at = excluded.updated_at
""".strip(),
        (
            board_id,
            "Local review board over intents, work packets, actions, dropped intents, packages, capsules, and finance proposals.",
            now,
            now,
        ),
    )
    card_specs = [
        {
            "source_id": "finance_invoice_reconciliation:review_repo_b_finance_helpers",
            "title": "Review Repo B finance helpers",
            "summary": "Review bounded metadata for Repo B billing, invoice, financial, CPA, and budget helpers before any porting.",
            "column": "needs_review",
            "status": "proposal_only",
            "next_safe_move": "Decide which finance helper logic is worth porting into governed Finance World packets; do not run Repo B code.",
        },
        {
            "source_id": f"finance_invoice_reconciliation:{workflow_proposal_id}",
            "title": "Build Finance Invoice Helper v0 proposal",
            "summary": "Proposal-only lane for invoice/receivables evidence packets and draft work packets.",
            "column": "planned",
            "status": "proposal_only",
            "next_safe_move": "Use one real receivable target to build an evidence packet; approval required before outputs beyond draft context.",
        },
        {
            "source_id": "finance_invoice_reconciliation:receivables_evidence_requirements",
            "title": "Review receivables evidence requirements",
            "summary": "Confirm what evidence is allowed for invoice/receivable work without raw bank scraping or tax/client raw ingestion.",
            "column": "needs_review",
            "status": "proposal_only",
            "next_safe_move": "Approve or revise the evidence requirements before building a finance evidence packet.",
        },
    ]
    inserted = 0
    for spec in card_specs:
        card_id = _row_id("wbcard", board_id, "manual_seed", spec["source_id"])
        conn.execute(
            """
INSERT INTO work_board_cards (
  card_id, board_id, title, summary, source_kind, source_id, world_hint,
  agent_id, lane_id, intent_category, board_column, status, priority_hint,
  approval_required, execution_allowed, action_request_id, work_packet_id,
  receipt_id, blocker_reason, next_safe_move, evidence_basis, created_at,
  updated_at, raw_body_stored, direct_execution_allowed, arbitrary_shell_allowed,
  auto_approval_allowed, auto_execute_allowed, agent_activation_allowed,
  model_call_allowed, tool_execution_allowed, network_authority,
  no_go_raw_access_allowed, file_move_allowed, file_delete_allowed,
  client_deployment_allowed
) VALUES (?, ?, ?, ?, 'manual_seed', ?, 'finance', 'chief',
  'system_orchestration', 'finance_invoice_reconciliation', ?, ?, 'high',
  1, 0, NULL, NULL, NULL, NULL, ?, ?, ?, ?, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)
ON CONFLICT(board_id, source_kind, source_id) DO UPDATE SET
  title = excluded.title,
  summary = excluded.summary,
  world_hint = excluded.world_hint,
  agent_id = excluded.agent_id,
  lane_id = excluded.lane_id,
  intent_category = excluded.intent_category,
  board_column = excluded.board_column,
  status = excluded.status,
  priority_hint = excluded.priority_hint,
  approval_required = 1,
  execution_allowed = 0,
  next_safe_move = excluded.next_safe_move,
  evidence_basis = excluded.evidence_basis,
  updated_at = excluded.updated_at,
  raw_body_stored = 0,
  direct_execution_allowed = 0,
  arbitrary_shell_allowed = 0,
  auto_approval_allowed = 0,
  auto_execute_allowed = 0,
  agent_activation_allowed = 0,
  model_call_allowed = 0,
  tool_execution_allowed = 0,
  network_authority = 0,
  no_go_raw_access_allowed = 0,
  file_move_allowed = 0,
  file_delete_allowed = 0,
  client_deployment_allowed = 0
""".strip(),
            (
                card_id,
                board_id,
                spec["title"],
                spec["summary"],
                spec["source_id"],
                spec["column"],
                spec["status"],
                spec["next_safe_move"],
                f"finance_invoice_reconciliation:{run_id}",
                now,
                now,
            ),
        )
        conn.execute(
            """
INSERT OR REPLACE INTO work_board_card_sources (
  card_source_id, card_id, source_kind, source_id, source_path,
  source_summary, raw_body_stored, created_at
) VALUES (?, ?, 'manual_seed', ?, NULL, ?, 0, ?)
""".strip(),
            (_row_id("wbsrc", card_id, "manual_seed", spec["source_id"]), card_id, spec["source_id"], spec["summary"], now),
        )
        conn.execute(
            """
INSERT OR REPLACE INTO work_board_card_agents (
  card_agent_id, card_id, agent_id, lane_id, role,
  can_execute, can_bypass_approval, created_at
) VALUES (?, ?, 'chief', 'system_orchestration', 'assigned_lane', 0, 0, ?)
""".strip(),
            (_row_id("wbagent", card_id, "chief"), card_id, now),
        )
        conn.execute(
            """
INSERT OR REPLACE INTO work_board_card_worlds (
  card_world_id, card_id, world_hint, confidence, created_at
) VALUES (?, ?, 'finance', 'metadata_hint', ?)
""".strip(),
            (_row_id("wbworld", card_id, "finance"), card_id, now),
        )
        conn.execute(
            """
INSERT OR REPLACE INTO work_board_card_dependencies (
  dependency_id, card_id, dependency_kind, dependency_ref,
  dependency_status, created_at
) VALUES (?, ?, 'approval_gate', 'operator_approval', 'required_before_action', ?)
""".strip(),
            (_row_id("wbdep", card_id, "approval_gate"), card_id, now),
        )
        conn.execute(
            """
INSERT OR IGNORE INTO work_board_card_status_history (
  history_id, card_id, previous_column, board_column, status,
  changed_by, change_reason, changed_at, execution_allowed,
  approval_bypass_allowed
) VALUES (?, ?, NULL, ?, ?, 'finance_invoice_reconciliation_builder', ?, ?, 0, 0)
""".strip(),
            (
                _row_id("wbhist", card_id, spec["column"], spec["status"]),
                card_id,
                spec["column"],
                spec["status"],
                "Metadata-only Finance World projection; no action, approval, or execution created.",
                now,
            ),
        )
        inserted += 1
    return inserted


def build_finance_invoice_reconciliation(
    *,
    db_path: str | Path | None = None,
    repo_root: str | Path = DEFAULT_REPO_B_ROOT,
    run_id: str | None = None,
    require_expected_remote: bool = True,
    create_work_board_cards: bool = True,
) -> FinanceReconciliationResult:
    repo_root_path = Path(repo_root)
    if not repo_root_path.exists() or not repo_root_path.is_dir():
        raise FileNotFoundError(f"Repo B root not found: {repo_root_path}")
    metadata = _repo_b_metadata(repo_root_path)
    if require_expected_remote and not remote_matches_expected(metadata["source_remote"]):
        raise ValueError(f"Repo B remote does not match {EXPECTED_REMOTE_SLUG}: {metadata['source_remote']}")
    path = init_finance_invoice_reconciliation_schema(db_path)
    if create_work_board_cards:
        init_work_board_schema(path)
    now = utc_now()
    resolved_run_id = run_id or _row_id("finrecrun", metadata["source_commit"], now)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        _insert_run(conn, run_id=resolved_run_id, repo_b_root=repo_root_path, source_commit=metadata["source_commit"], now=now)
        candidate_paths = _finance_candidate_paths(repo_root_path, conn)
        reviews: list[FinanceCandidateReview] = []
        for relative_path in candidate_paths:
            review, capabilities, reasons = _review_candidate(repo_root_path, relative_path, metadata["source_commit"])
            _upsert_candidate(conn, review=review, capabilities=capabilities, reasons=reasons, run_id=resolved_run_id, now=now)
            reviews.append(review)
        workflow_id = _insert_workflow(conn, run_id=resolved_run_id, now=now)
        work_board_count = _ensure_finance_work_board_cards(conn, run_id=resolved_run_id, workflow_proposal_id=workflow_id, now=now) if create_work_board_cards else 0
        high_risk_count = sum(1 for item in reviews if item.risk_level == "high")
        blocked_count = sum(1 for item in reviews if item.risk_level == "blocked" or item.reuse_policy == "blocked_no_go")
        reviewed_count = sum(1 for item in reviews if item.safe_source_reviewed)
        conn.execute(
            """
UPDATE finance_invoice_reconciliation_runs
SET completed_at = ?, finance_candidate_count = ?,
    safe_source_reviewed_count = ?, high_risk_count = ?,
    blocked_no_go_count = ?, workflow_proposal_id = ?,
    work_board_card_count = ?, finance_execution_allowed = 0,
    invoice_send_allowed = 0, email_send_allowed = 0,
    bank_access_allowed = 0, tax_filing_allowed = 0,
    external_api_allowed = 0, raw_private_ingest_allowed = 0,
    operator_approval_required = 1, financial_truth_claimed = 0
WHERE run_id = ?
""".strip(),
            (
                utc_now(),
                len(reviews),
                reviewed_count,
                high_risk_count,
                blocked_count,
                workflow_id,
                work_board_count,
                resolved_run_id,
            ),
        )
        conn.commit()
        return FinanceReconciliationResult(
            run_id=resolved_run_id,
            db_path=path,
            repo_b_root=repo_root_path.as_posix(),
            source_commit=metadata["source_commit"],
            finance_candidate_count=len(reviews),
            safe_source_reviewed_count=reviewed_count,
            high_risk_count=high_risk_count,
            blocked_no_go_count=blocked_count,
            workflow_proposal_id=workflow_id,
            work_board_card_count=work_board_count,
        )
    finally:
        conn.close()


def _latest_run_id(conn: sqlite3.Connection) -> str | None:
    row = conn.execute(
        """
SELECT run_id FROM finance_invoice_reconciliation_runs
ORDER BY completed_at DESC, created_at DESC, run_id DESC
LIMIT 1
""".strip()
    ).fetchone()
    return row["run_id"] if row else None


def _summary_counts(conn: sqlite3.Connection, run_id: str) -> dict[str, Any]:
    run = conn.execute("SELECT * FROM finance_invoice_reconciliation_runs WHERE run_id = ?", (run_id,)).fetchone()
    if not run:
        return {}
    return {
        "finance_candidate_count": run["finance_candidate_count"],
        "safe_source_reviewed_count": run["safe_source_reviewed_count"],
        "high_risk_count": run["high_risk_count"],
        "blocked_no_go_count": run["blocked_no_go_count"],
        "work_board_card_count": run["work_board_card_count"],
        "by_capability": {
            row["capability_kind"]: row["count"]
            for row in conn.execute(
                """
SELECT capability_kind, COUNT(*) AS count
FROM finance_candidate_capabilities
WHERE candidate_id IN (SELECT candidate_id FROM finance_candidate_sources WHERE run_id = ?)
GROUP BY capability_kind
ORDER BY count DESC, capability_kind
""".strip(),
                (run_id,),
            ).fetchall()
        },
        "by_reuse_policy": {
            row["reuse_policy"]: row["count"]
            for row in conn.execute(
                """
SELECT reuse_policy, COUNT(*) AS count
FROM finance_candidate_sources
WHERE run_id = ?
GROUP BY reuse_policy
ORDER BY count DESC, reuse_policy
""".strip(),
                (run_id,),
            ).fetchall()
        },
        "by_future_home": {
            row["future_home"]: row["count"]
            for row in conn.execute(
                """
SELECT future_home, COUNT(*) AS count
FROM finance_candidate_sources
WHERE run_id = ?
GROUP BY future_home
ORDER BY count DESC, future_home
""".strip(),
                (run_id,),
            ).fetchall()
        },
    }


def build_finance_invoice_reconciliation_report(
    *,
    db_path: str | Path | None = None,
    report: str = "summary",
    capability: str | None = None,
    run_id: str | None = None,
) -> dict[str, Any]:
    if report not in REPORT_SECTIONS:
        raise ValueError(f"unknown finance reconciliation report: {report}")
    if capability and capability not in CAPABILITY_KINDS:
        raise ValueError(f"unknown finance capability: {capability}")
    path = init_finance_invoice_reconciliation_schema(db_path)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        resolved_run_id = run_id or _latest_run_id(conn)
        if not resolved_run_id:
            return {"status": "no_runs", "report": report, "rows": [], "counts": {}, "no_authority_flags": NO_AUTHORITY_FLAGS}
        run = dict(conn.execute("SELECT * FROM finance_invoice_reconciliation_runs WHERE run_id = ?", (resolved_run_id,)).fetchone())
        counts = _summary_counts(conn, resolved_run_id)
        rows: list[dict[str, Any]]
        if capability:
            rows = _dict_rows(
                conn,
                """
SELECT s.source_path, s.purpose, s.future_home, s.reuse_policy,
       s.risk_level, s.burden_reduction, s.reusable_logic
FROM finance_candidate_sources s
JOIN finance_candidate_capabilities c ON c.candidate_id = s.candidate_id
WHERE s.run_id = ? AND c.capability_kind = ?
ORDER BY s.risk_level DESC, s.source_path
""".strip(),
                (resolved_run_id, capability),
            )
            effective_report = f"capability:{capability}"
        elif report == "summary":
            rows = _dict_rows(
                conn,
                """
SELECT source_path, purpose, reuse_policy, future_home, risk_level,
       burden_reduction, reusable_logic
FROM finance_candidate_sources
WHERE run_id = ?
ORDER BY CASE reuse_policy
  WHEN 'candidate_to_port' THEN 0
  WHEN 'candidate_to_wrap' THEN 1
  WHEN 'needs_operator_review' THEN 2
  WHEN 'reference_only' THEN 3
  ELSE 4 END,
  source_path
LIMIT 12
""".strip(),
                (resolved_run_id,),
            )
            effective_report = report
        elif report == "candidates":
            rows = _dict_rows(
                conn,
                """
SELECT source_path, purpose, expected_inputs, expected_outputs,
       future_home, reuse_policy, risk_level, burden_reduction,
       safe_source_reviewed
FROM finance_candidate_sources
WHERE run_id = ?
ORDER BY source_path
LIMIT 200
""".strip(),
                (resolved_run_id,),
            )
            effective_report = report
        elif report == "risks":
            rows = _dict_rows(
                conn,
                """
SELECT s.source_path, r.risk_reason, r.risk_level, r.evidence_basis,
       s.sensitive_data_risk, s.direct_execution_risk
FROM finance_candidate_risks r
JOIN finance_candidate_sources s ON s.candidate_id = r.candidate_id
WHERE s.run_id = ?
ORDER BY CASE r.risk_level WHEN 'blocked' THEN 0 WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END,
         s.source_path, r.risk_reason
LIMIT 200
""".strip(),
                (resolved_run_id,),
            )
            effective_report = report
        else:
            rows = _dict_rows(
                conn,
                """
SELECT title, purpose, operator_inputs_needed, allowed_evidence_types,
       disallowed_evidence_types, expected_outputs, work_board_integration,
       operator_action_requirements, no_send_policy, no_bank_scrape_policy,
       receipt_evidence_handling, next_safe_move
FROM finance_workflow_proposals
WHERE run_id = ?
ORDER BY created_at DESC
""".strip(),
                (resolved_run_id,),
            )
            effective_report = report
        conn.execute(
            """
INSERT OR REPLACE INTO finance_query_receipts (
  query_receipt_id, query_kind, filter_value, result_count,
  generated_at, raw_body_stored, execution_allowed
) VALUES (?, ?, ?, ?, ?, 0, 0)
""".strip(),
            (_row_id("finrecquery", effective_report, capability or "", utc_now()), effective_report, capability, len(rows), utc_now()),
        )
        conn.commit()
        return {
            "status": "ok",
            "report": effective_report,
            "run_id": resolved_run_id,
            "run": run,
            "counts": counts,
            "rows": rows,
            "no_authority_flags": NO_AUTHORITY_FLAGS,
        }
    finally:
        conn.close()


def _counts_line(counts: dict[str, Any]) -> str:
    if not counts:
        return "none"
    return ", ".join(f"{key}={value}" for key, value in sorted(counts.items()))


def format_finance_invoice_reconciliation_result(result: FinanceReconciliationResult) -> str:
    return "\n".join(
        [
            "Finance Invoice Helper Reconciliation v0",
            "",
            f"Repo B: `{result.repo_b_root}`",
            f"Commit: `{result.source_commit}`",
            f"Run: `{result.run_id}`",
            f"Finance candidates: {result.finance_candidate_count}",
            f"Safe source reviewed: {result.safe_source_reviewed_count}",
            f"High risk: {result.high_risk_count}",
            f"Blocked/no-go: {result.blocked_no_go_count}",
            f"Workflow proposal: `{result.workflow_proposal_id}`",
            f"Work Board cards: {result.work_board_card_count}",
            "",
            "Boundary:",
            "- Repo B finance code was not executed, imported, promoted, or trusted as financial truth.",
            "- No invoices, emails, bank access, ledger writes, or executable finance actions were created.",
        ]
    )


def format_finance_invoice_reconciliation_report(payload: dict[str, Any]) -> str:
    if payload.get("status") == "no_runs":
        return "Finance Invoice Helper Reconciliation v0\n\nNo finance reconciliation runs are recorded."
    counts = payload["counts"]
    lines = [
        f"Finance Invoice Helper Reconciliation v0 - {payload['report']}",
        "",
        f"Run: `{payload['run_id']}`",
        f"Finance candidates: {counts.get('finance_candidate_count', 0)}",
        f"Safe source reviewed: {counts.get('safe_source_reviewed_count', 0)}",
        f"High risk: {counts.get('high_risk_count', 0)}",
        f"Blocked/no-go: {counts.get('blocked_no_go_count', 0)}",
        f"Work Board cards: {counts.get('work_board_card_count', 0)}",
        f"By capability: {_counts_line(counts.get('by_capability', {}))}",
        f"By reuse policy: {_counts_line(counts.get('by_reuse_policy', {}))}",
        "",
        "Rows:",
    ]
    for row in payload.get("rows") or []:
        if payload["report"] == "workflow":
            lines.append(f"- {row['title']}: {row['next_safe_move']}")
        elif payload["report"] == "risks":
            lines.append(f"- `{row['source_path']}` {row['risk_reason']} ({row['risk_level']}): {row['direct_execution_risk']}")
        else:
            lines.append(
                f"- `{row['source_path']}` reuse={row.get('reuse_policy')} home={row.get('future_home')} risk={row.get('risk_level')}: {row.get('purpose')}"
            )
    if not payload.get("rows"):
        lines.append("- none")
    lines.extend(
        [
            "",
            "Burden-reduction posture:",
            "- This gives Finance World a reviewable path from old helpers to an evidence-packet workflow instead of asking the operator to remember old scripts.",
            "- The first useful output is a proposal-only invoice/receivables evidence packet, not another live system to babysit.",
            "",
            "Authority boundary:",
        ]
    )
    for key, value in NO_AUTHORITY_FLAGS.items():
        lines.append(f"- `{key}`: `{str(value).lower()}`.")
    return "\n".join(lines)


def build_finance_invoice_reconciliation_read_model(db_path: str | Path | None = None) -> dict[str, Any]:
    path = init_finance_invoice_reconciliation_schema(db_path)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        run_id = _latest_run_id(conn)
        if not run_id:
            return {
                "schema_version": READ_MODEL_VERSION,
                "status": "no_runs",
                "no_authority_flags": NO_AUTHORITY_FLAGS,
            }
        run = dict(conn.execute("SELECT * FROM finance_invoice_reconciliation_runs WHERE run_id = ?", (run_id,)).fetchone())
        counts = _summary_counts(conn, run_id)
        top_candidates_to_port = _dict_rows(
            conn,
            """
SELECT source_path, purpose, future_home, reuse_policy, risk_level,
       burden_reduction, reusable_logic
FROM finance_candidate_sources
WHERE run_id = ? AND reuse_policy IN ('candidate_to_port', 'candidate_to_wrap')
ORDER BY CASE risk_level WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END,
         source_path
LIMIT 12
""".strip(),
            (run_id,),
        )
        reference_only = _dict_rows(
            conn,
            """
SELECT source_path, purpose, future_home, risk_level, reusable_logic
FROM finance_candidate_sources
WHERE run_id = ? AND reuse_policy = 'reference_only'
ORDER BY source_path
LIMIT 12
""".strip(),
            (run_id,),
        )
        risks = _dict_rows(
            conn,
            """
SELECT s.source_path, r.risk_reason, r.risk_level, r.evidence_basis
FROM finance_candidate_risks r
JOIN finance_candidate_sources s ON s.candidate_id = r.candidate_id
WHERE s.run_id = ?
ORDER BY CASE r.risk_level WHEN 'blocked' THEN 0 WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END,
         s.source_path, r.risk_reason
LIMIT 20
""".strip(),
            (run_id,),
        )
        workflow = _dict_rows(
            conn,
            """
SELECT *
FROM finance_workflow_proposals
WHERE run_id = ?
ORDER BY created_at DESC
LIMIT 1
""".strip(),
            (run_id,),
        )
        evidence_requirements = _dict_rows(
            conn,
            """
SELECT evidence_kind, requirement_text, allowed, sensitivity_level
FROM finance_evidence_requirements
WHERE workflow_proposal_id = ?
ORDER BY allowed DESC, evidence_kind
""".strip(),
            (run["workflow_proposal_id"],),
        )
        next_safe_moves = _dict_rows(
            conn,
            """
SELECT move_order, next_safe_move, routed_agent, approval_required, execution_allowed
FROM finance_next_safe_moves
WHERE workflow_proposal_id = ?
ORDER BY move_order
""".strip(),
            (run["workflow_proposal_id"],),
        )
        work_board_cards = _dict_rows(
            conn,
            """
SELECT card_id, title, board_column, status, next_safe_move
FROM work_board_cards
WHERE source_kind = 'manual_seed'
  AND source_id LIKE 'finance_invoice_reconciliation:%'
ORDER BY title
""".strip(),
        ) if _table_exists(conn, "work_board_cards") else []
        return {
            "schema_version": READ_MODEL_VERSION,
            "read_model_version": READ_MODEL_VERSION,
            "generated_at": utc_now(),
            "run_id": run_id,
            "source": {
                "repo_b_path": run["repo_b_root"],
                "source_repo": SOURCE_REPO_B,
                "source_commit": run["source_commit"],
                "canonical_status": REPO_B_CANONICAL_STATUS,
                "import_status": "metadata_scanned_only_or_safe_source_reviewed",
            },
            "counts": counts,
            "top_candidate_to_port_or_wrap_items": top_candidates_to_port,
            "top_reference_only_items": reference_only,
            "risk_summary": risks,
            "first_safe_workflow_proposal": workflow[0] if workflow else None,
            "evidence_requirements": evidence_requirements,
            "next_safe_moves": next_safe_moves,
            "work_board_linkage": {
                "implemented": bool(work_board_cards),
                "cards": work_board_cards,
            },
            "how_this_reduces_operator_burden": [
                "Makes legacy finance helper logic queryable instead of relying on memory.",
                "Separates useful invoice/receivable patterns from unsafe direct sends, writes, and model calls.",
                "Defines the first practical finance workflow as an evidence packet/work packet, not a live finance bot.",
            ],
            "recommended_next_lane": "Finance Invoice Evidence Packet v0",
            "no_authority_flags": NO_AUTHORITY_FLAGS,
        }
    finally:
        conn.close()


def _operator_markdown(read_model: dict[str, Any]) -> str:
    if read_model.get("status") == "no_runs":
        return "# Finance Invoice Helper Reconciliation v0\n\nNo finance reconciliation run has been recorded.\n"
    counts = read_model["counts"]
    workflow = read_model.get("first_safe_workflow_proposal") or {}
    lines = [
        "# Finance Invoice Helper Reconciliation v0",
        "",
        "## Source",
        f"- Repo B path: `{read_model['source']['repo_b_path']}`",
        f"- Repo B commit: `{read_model['source']['source_commit']}`",
        f"- Canonical status: `{read_model['source']['canonical_status']}`",
        "",
        "## Counts",
        f"- Finance candidates: {counts.get('finance_candidate_count', 0)}",
        f"- Safe source reviewed: {counts.get('safe_source_reviewed_count', 0)}",
        f"- High-risk candidates: {counts.get('high_risk_count', 0)}",
        f"- Blocked/no-go candidates: {counts.get('blocked_no_go_count', 0)}",
        f"- Work Board cards: {counts.get('work_board_card_count', 0)}",
        "",
        "## Top Candidate To Port/Wrap",
    ]
    for row in read_model.get("top_candidate_to_port_or_wrap_items") or []:
        lines.append(f"- `{row['source_path']}` reuse={row['reuse_policy']} risk={row['risk_level']}: {row['reusable_logic']}")
    if not read_model.get("top_candidate_to_port_or_wrap_items"):
        lines.append("- None.")
    lines.extend(["", "## Reference-Only Items"])
    for row in read_model.get("top_reference_only_items") or []:
        lines.append(f"- `{row['source_path']}` risk={row['risk_level']}: {row['reusable_logic']}")
    if not read_model.get("top_reference_only_items"):
        lines.append("- None.")
    lines.extend(["", "## First Safe Workflow Proposal"])
    if workflow:
        lines.append(f"- Title: {workflow['title']}")
        lines.append(f"- Purpose: {workflow['purpose']}")
        lines.append(f"- Next safe move: {workflow['next_safe_move']}")
        lines.append("- Policy: proposal-only; no invoice send, email send, bank access, tax filing, or financial truth claim.")
    else:
        lines.append("- None.")
    lines.extend(["", "## Evidence Requirements"])
    for row in read_model.get("evidence_requirements") or []:
        lines.append(f"- `{row['evidence_kind']}` allowed={bool(row['allowed'])}: {row['requirement_text']}")
    lines.extend(["", "## Work Board Linkage"])
    linkage = read_model.get("work_board_linkage") or {}
    for row in linkage.get("cards") or []:
        lines.append(f"- `{row['card_id']}` {row['board_column']}: {row['title']}")
    if not linkage.get("cards"):
        lines.append("- None.")
    lines.extend(
        [
            "",
            "## Operator Burden Reduction",
        ]
    )
    for item in read_model.get("how_this_reduces_operator_burden") or []:
        lines.append(f"- {item}")
    lines.extend(["", "## Authority Boundary"])
    for key, value in NO_AUTHORITY_FLAGS.items():
        lines.append(f"- `{key}`: `{str(value).lower()}`.")
    return "\n".join(lines) + "\n"


def export_finance_invoice_reconciliation_read_model(
    *,
    db_path: str | Path | None = None,
    export_root: str | Path = DEFAULT_EXPORT_ROOT,
) -> dict[str, Any]:
    out_root = _export_root_path(export_root)
    out_root.mkdir(parents=True, exist_ok=True)
    read_model = build_finance_invoice_reconciliation_read_model(db_path)
    json_path = out_root / JSON_EXPORT_NAME
    operator_path = out_root / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(read_model), encoding="utf-8")
    operator_path.write_text(_operator_markdown(read_model), encoding="utf-8")
    return {
        "export_version": READ_MODEL_VERSION,
        "json_path": _display_path(json_path),
        "operator_path": _display_path(operator_path),
        "finance_candidate_count": read_model.get("counts", {}).get("finance_candidate_count", 0),
        "high_risk_count": read_model.get("counts", {}).get("high_risk_count", 0),
        "workflow_proposal_id": (read_model.get("first_safe_workflow_proposal") or {}).get("workflow_proposal_id"),
        "no_authority_flags": NO_AUTHORITY_FLAGS,
    }


__all__ = [
    "CAPABILITY_KINDS",
    "DEFAULT_REPO_B_ROOT",
    "NO_AUTHORITY_FLAGS",
    "READ_MODEL_VERSION",
    "REPORT_SECTIONS",
    "FinanceReconciliationResult",
    "build_finance_invoice_reconciliation",
    "build_finance_invoice_reconciliation_read_model",
    "build_finance_invoice_reconciliation_report",
    "export_finance_invoice_reconciliation_read_model",
    "finance_invoice_reconciliation_table_names",
    "format_finance_invoice_reconciliation_report",
    "format_finance_invoice_reconciliation_result",
    "init_finance_invoice_reconciliation_schema",
    "stable_json",
]
