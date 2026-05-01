import type { BoundaryState } from "./legalStatus";

export type SyntheticDryRunStatus = "succeeded" | "failed";
export type SyntheticBridgeMode = "synthetic_only";

export interface SyntheticDryRunResult {
  started: boolean;
  status: SyntheticDryRunStatus;
  exit_code: number | null;
  bridge_mode: SyntheticBridgeMode;
  boundary_state: BoundaryState;
  warnings: string[];
  errors: string[];
}

type TauriInvoke = <T>(command: string, args?: Record<string, unknown>) => Promise<T>;

const reasonMessages: Record<string, string> = {
  unsupported_os: "Run Synthetic Dry Run is only wired for the macOS proof target.",
  home_not_available: "Home folder is unavailable, so the synthetic bridge did not start.",
  synthetic_bridge_vault_missing: "Synthetic bridge vault is missing. Run the Mac vault scaffold outside this GUI.",
  synthetic_bridge_vault_not_directory: "Blocked. Synthetic bridge vault failed a boundary check.",
  synthetic_bridge_command_missing: "Synthetic bridge command is missing. Run the Mac vault scaffold outside this GUI.",
  synthetic_bridge_command_not_file: "Blocked. Synthetic bridge command failed a boundary check.",
  synthetic_bridge_config_missing: "Synthetic bridge config is missing. Run the Mac vault scaffold outside this GUI.",
  synthetic_bridge_config_not_file: "Blocked. Synthetic bridge config failed a boundary check.",
  synthetic_bridge_config_read_failed: "Blocked. Synthetic bridge config could not be checked safely.",
  synthetic_bridge_config_too_large: "Blocked. Synthetic bridge config failed a size check.",
  path_traversal_rejected: "Blocked. Synthetic bridge path failed a boundary check.",
  fixed_path_mismatch: "Blocked. Synthetic bridge path did not match the approved proof target.",
  path_inside_product_repo: "Blocked. Bridge paths must stay outside the product repo.",
  cloud_or_watch_path_rejected: "Blocked. Bridge path appears to be in a cloud or watch folder.",
  path_symlink_rejected: "Blocked. Bridge path or required ancestor is a symlink.",
  path_canonicalize_failed: "Blocked. Bridge path could not be safely resolved.",
  pc_ssh_target_missing: "Blocked. Synthetic bridge target is not configured.",
  pc_repo_root_mismatch: "Blocked. Synthetic bridge repo target is not the approved proof target.",
  pc_vault_root_mismatch: "Blocked. Synthetic bridge vault root is not the approved proof target.",
  synthetic_staging_path_mismatch: "Blocked. Synthetic bridge staging path is not the fixed proof target.",
  synthetic_exports_path_mismatch: "Blocked. Synthetic bridge exports path is not the fixed proof target.",
  synthetic_matter_id_mismatch: "Blocked. Synthetic bridge matter ID is not the fixed proof value.",
  synthetic_query_mismatch: "Blocked. Synthetic bridge query is not the fixed proof value.",
  bridge_start_failed: "Synthetic bridge command could not be started.",
  bridge_command_failed: "Synthetic bridge command returned a sanitized failure state.",
  bridge_process_text_suppressed: "Bridge process text was captured and suppressed.",
  tauri_runtime_required: "Tauri runtime is required to run the synthetic bridge from this prototype."
};

export async function runSyntheticDryRun(): Promise<SyntheticDryRunResult> {
  const invoke: TauriInvoke | undefined = window.__TAURI_INTERNALS__?.invoke;

  if (!invoke) {
    throw new Error("tauri_runtime_required");
  }

  return invoke<SyntheticDryRunResult>("run_synthetic_dry_run");
}

export function syntheticDryRunResultFromError(error: unknown): SyntheticDryRunResult {
  const reason = error instanceof Error && reasonMessages[error.message] ? error.message : "bridge_start_failed";

  return {
    started: false,
    status: "failed",
    exit_code: null,
    bridge_mode: "synthetic_only",
    boundary_state: "error",
    warnings: [],
    errors: [reason]
  };
}

function escapeHtml(value: string): string {
  return value.replace(/[&<>'"]/g, (character) => {
    switch (character) {
      case "&":
        return "&amp;";
      case "<":
        return "&lt;";
      case ">":
        return "&gt;";
      case "'":
        return "&#39;";
      case '"':
        return "&quot;";
      default:
        return character;
    }
  });
}

function messageForReason(reason: string): string {
  return reasonMessages[reason] ?? "Synthetic bridge returned a sanitized failure state.";
}

function renderMessages(title: string, values: string[]): string {
  if (values.length === 0) {
    return "";
  }

  return `
    <strong>${title}</strong>
    <ul>
      ${values.map((value) => `<li>${escapeHtml(messageForReason(value))}</li>`).join("")}
    </ul>
  `;
}

function exitCodeLabel(exitCode: number | null): string {
  return exitCode === null ? "Unavailable" : String(exitCode);
}

function resultTitle(result: SyntheticDryRunResult): string {
  if (result.status === "succeeded") {
    return "Synthetic dry run succeeded";
  }

  if (result.started) {
    return "Synthetic dry run failed";
  }

  return "Synthetic dry run not started";
}

function resultSummary(result: SyntheticDryRunResult): string {
  if (result.status === "succeeded") {
    return "Bridge completed with raw command output suppressed. Refresh Status for sanitized status tokens only.";
  }

  if (result.started) {
    return "Bridge stopped with raw command output suppressed. Check local status files only inside the private environment.";
  }

  return "Request stopped before command execution. No command output, filenames, generated documents, or packet text were returned.";
}

export function renderSyntheticDryRunStarted(): string {
  return `
    <section class="intake-result intake-result--warning" aria-live="polite">
      <div class="intake-result__heading">
        <strong>Synthetic dry run started</strong>
        <span>synthetic_only</span>
      </div>
      <p>Waiting for sanitized bridge status. Raw command output is captured and suppressed.</p>
    </section>
  `;
}

export function renderSyntheticDryRunResult(result: SyntheticDryRunResult): string {
  return `
    <section class="intake-result intake-result--${result.boundary_state}" aria-live="polite">
      <div class="intake-result__heading">
        <strong>${escapeHtml(resultTitle(result))}</strong>
        <span>${escapeHtml(result.bridge_mode)}</span>
      </div>
      <p>${escapeHtml(resultSummary(result))}</p>
      <div class="live-status__grid">
        <div>
          <span>Started</span>
          <strong>${result.started ? "Yes" : "No"}</strong>
        </div>
        <div>
          <span>Status</span>
          <strong>${escapeHtml(result.status)}</strong>
        </div>
        <div>
          <span>Exit code</span>
          <strong>${escapeHtml(exitCodeLabel(result.exit_code))}</strong>
        </div>
        <div>
          <span>Bridge mode</span>
          <strong>${escapeHtml(result.bridge_mode)}</strong>
        </div>
      </div>
      ${renderMessages("Warnings", result.warnings)}
      ${renderMessages("Errors", result.errors)}
    </section>
  `;
}