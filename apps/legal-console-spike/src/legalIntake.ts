import type { BoundaryState } from "./legalStatus";

export type IntakeOpenOs = "macos" | "windows" | "linux" | "unsupported";

export interface IntakeOpenResult {
  opened: boolean;
  target: "intake_folder";
  os: IntakeOpenOs;
  boundary_state: BoundaryState;
  warnings: string[];
  errors: string[];
}

type TauriInvoke = <T>(command: string, args?: Record<string, unknown>) => Promise<T>;

const reasonMessages: Record<string, string> = {
  home_not_available: "Home folder is unavailable, so the intake folder was not opened.",
  unsupported_os: "Open Intake Folder is only wired for the macOS proof target in this phase.",
  intake_folder_missing: "Intake folder is missing. Run the Mac vault scaffold before opening it.",
  intake_target_not_directory: "Open blocked because the configured intake target is not a folder.",
  path_traversal_rejected: "Open blocked because the configured intake path failed traversal checks.",
  fixed_path_mismatch: "Open blocked because the configured intake path did not match the approved folder.",
  path_inside_product_repo: "Open blocked because matter data cannot be opened inside the product repo.",
  cloud_or_watch_path_rejected: "Open blocked because the configured intake path appears to be in a cloud or watch folder.",
  path_symlink_rejected: "Open blocked because the intake path or required ancestor is a symlink.",
  path_canonicalize_failed: "Open blocked because the intake path could not be safely resolved.",
  intake_open_failed: "The OS folder open request failed after path validation.",
  tauri_runtime_required: "Tauri runtime is required to open the intake folder from this prototype."
};

export async function openIntakeFolder(): Promise<IntakeOpenResult> {
  const invoke = window.__TAURI_INTERNALS__?.invoke;

  if (!invoke) {
    throw new Error("tauri_runtime_required");
  }

  return invoke<IntakeOpenResult>("open_intake_folder");
}

export function intakeOpenResultFromError(error: unknown): IntakeOpenResult {
  const reason = error instanceof Error && reasonMessages[error.message] ? error.message : "intake_open_failed";

  return {
    opened: false,
    target: "intake_folder",
    os: "unsupported",
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
  return reasonMessages[reason] ?? "The intake folder was not opened. The prototype returned a sanitized failure state.";
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

export function renderIntakeOpenResult(result: IntakeOpenResult): string {
  const title = result.opened ? "Intake folder opened" : "Intake folder not opened";
  const summary = result.opened
    ? "The exact drop folder was opened by the OS. No files were read, listed, written, or processed."
    : "The request stopped before opening the folder.";

  return `
    <section class="intake-result intake-result--${result.boundary_state}" aria-live="polite">
      <div class="intake-result__heading">
        <strong>${title}</strong>
        <span>${escapeHtml(result.boundary_state)}</span>
      </div>
      <p>${summary}</p>
      ${renderMessages("Warnings", result.warnings)}
      ${renderMessages("Errors", result.errors)}
    </section>
  `;
}