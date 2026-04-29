import type { BoundaryState } from "./legalStatus";

export interface SyntheticTestFileResult {
  created: boolean;
  already_present: boolean;
  target: "intake_folder";
  synthetic_filename: "openclaw_synthetic_dummy_test_file.txt";
  boundary_state: BoundaryState;
  warnings: string[];
  errors: string[];
}

const syntheticFilename = "openclaw_synthetic_dummy_test_file.txt" as const;

const reasonMessages: Record<string, string> = {
  home_not_available: "Home folder is unavailable, so the synthetic test file was not created.",
  unsupported_os: "Create Synthetic Test File is only wired for the macOS proof target in this phase.",
  intake_folder_missing: "Intake folder is missing. Run the Mac vault scaffold before creating the synthetic test file.",
  intake_target_not_directory: "Blocked. Intake path failed a boundary check.",
  path_traversal_rejected: "Blocked. Intake path failed a boundary check.",
  fixed_path_mismatch: "Blocked. Intake path failed a boundary check.",
  path_inside_product_repo: "Blocked. Matter data cannot be written inside the product repo.",
  cloud_or_watch_path_rejected: "Blocked. Intake path appears to be in a cloud or watch folder.",
  path_symlink_rejected: "Blocked. Intake path failed a boundary check.",
  path_canonicalize_failed: "Blocked. Intake path failed a boundary check.",
  synthetic_file_create_failed: "Blocked. The synthetic test file could not be created.",
  synthetic_file_write_failed: "Blocked. The synthetic test file could not be written.",
  synthetic_file_metadata_failed: "Blocked. The existing synthetic test target could not be checked safely.",
  synthetic_target_not_file: "Blocked. The fixed synthetic test target already exists and is not a file.",
  synthetic_file_read_failed: "Blocked. The existing synthetic test file could not be checked safely.",
  synthetic_file_already_present: "Synthetic test file already exists. No folder contents were listed.",
  synthetic_file_already_exists_with_unexpected_content:
    "Blocked. The fixed synthetic test filename already exists with different content.",
  tauri_runtime_required: "Tauri runtime is required to create the synthetic test file from this prototype."
};

export async function createSyntheticTestFile(): Promise<SyntheticTestFileResult> {
  const invoke = window.__TAURI_INTERNALS__?.invoke;

  if (!invoke) {
    throw new Error("tauri_runtime_required");
  }

  return invoke<SyntheticTestFileResult>("create_synthetic_test_file");
}

export function syntheticTestFileResultFromError(error: unknown): SyntheticTestFileResult {
  const reason = error instanceof Error && reasonMessages[error.message] ? error.message : "synthetic_file_create_failed";

  return {
    created: false,
    already_present: false,
    target: "intake_folder",
    synthetic_filename: syntheticFilename,
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
  return reasonMessages[reason] ?? "Blocked. Intake path failed a boundary check.";
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

function resultTitle(result: SyntheticTestFileResult): string {
  if (result.created) {
    return "Synthetic test file created";
  }

  if (result.already_present) {
    return "Synthetic test file already exists";
  }

  return "Synthetic test file not created";
}

function resultSummary(result: SyntheticTestFileResult): string {
  if (result.created) {
    return "Synthetic test file created. Run/Reset are still not wired from this GUI.";
  }

  if (result.already_present) {
    return "Synthetic test file already exists. No folder contents were listed.";
  }

  return "Blocked. Intake path failed a boundary check.";
}

export function renderSyntheticTestFileResult(result: SyntheticTestFileResult): string {
  return `
    <section class="intake-result intake-result--${result.boundary_state}" aria-live="polite">
      <div class="intake-result__heading">
        <strong>${escapeHtml(resultTitle(result))}</strong>
        <span>${escapeHtml(result.boundary_state)}</span>
      </div>
      <p>${escapeHtml(resultSummary(result))}</p>
      ${renderMessages("Warnings", result.warnings)}
      ${renderMessages("Errors", result.errors)}
    </section>
  `;
}
