export type WorkstationState =
  | "Ready"
  | "Checking config"
  | "Files found"
  | "Sending files to primary node"
  | "Processing on primary node"
  | "Pulling outputs back"
  | "Done"
  | "Error"
  | "Unknown";

export type PrimaryState = "Processing" | "Done" | "Error" | "Unknown";
export type IntakeTargetKind = "directory" | "missing" | "not_directory" | "unknown";
export type ProcessingState = "not_run" | "workstation_progress" | "primary_returned" | "error" | "unknown";
export type GuiBridgeState = "not_wired" | "synthetic_only";
export type BoundaryState = "safe" | "warning" | "error";
export type IntakeReadinessState = "before_refresh" | "ready" | "missing" | "blocked" | "unknown";
export type IntakeReadinessTone = "safe" | "warning" | "error";

export interface LegalStatusSnapshot {
  workstation_status_present: boolean;
  workstation_state: WorkstationState;
  workstation_last_updated: string | null;
  primary_status_present: boolean;
  primary_state: PrimaryState;
  primary_last_updated: string | null;
  intake_folder_present: boolean;
  intake_target_kind: IntakeTargetKind;
  outputs_guide_present: boolean;
  scaffold_ready: boolean;
  processing_state: ProcessingState;
  gui_bridge_state: GuiBridgeState;
  boundary_state: BoundaryState;
  warnings: string[];
  errors: string[];
}

export interface IntakeReadiness {
  state: IntakeReadinessState;
  tone: IntakeReadinessTone;
  label: string;
  message: string;
}

export interface IntakeOpenReadinessSignal {
  opened: boolean;
  boundary_state: BoundaryState;
  errors: string[];
}

type TauriInvoke = <T>(command: string, args?: Record<string, unknown>) => Promise<T>;

declare global {
  interface Window {
    __TAURI_INTERNALS__?: {
      invoke?: TauriInvoke;
    };
  }
}

export const initialStatusSnapshot: LegalStatusSnapshot = {
  workstation_status_present: false,
  workstation_state: "Unknown",
  workstation_last_updated: null,
  primary_status_present: false,
  primary_state: "Unknown",
  primary_last_updated: null,
  intake_folder_present: false,
  intake_target_kind: "unknown",
  outputs_guide_present: false,
  scaffold_ready: false,
  processing_state: "unknown",
  gui_bridge_state: "not_wired",
  boundary_state: "warning",
  warnings: ["status_refresh_not_run"],
  errors: []
};

export async function getStatusSnapshot(): Promise<LegalStatusSnapshot> {
  const invoke = window.__TAURI_INTERNALS__?.invoke;

  if (!invoke) {
    throw new Error("Tauri runtime required for live status.");
  }

  return invoke<LegalStatusSnapshot>("get_status_snapshot");
}

export function statusSnapshotFromError(message: string): LegalStatusSnapshot {
  return {
    ...initialStatusSnapshot,
    boundary_state: "error",
    warnings: [],
    errors: [message]
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

function presentLabel(value: boolean): string {
  return value ? "Present" : "Awaiting signal";
}

function readyLabel(value: boolean): string {
  return value ? "Ready" : "Not ready";
}

function nullableLabel(value: string | null): string {
  return value ? escapeHtml(value) : "Not reported";
}

function intakeKindLabel(value: IntakeTargetKind): string {
  switch (value) {
    case "directory":
      return "Directory";
    case "missing":
      return "Missing";
    case "not_directory":
      return "Not a directory";
    case "unknown":
      return "Unknown";
  }
}

function processingStateLabel(value: ProcessingState): string {
  switch (value) {
    case "not_run":
      return "Processing not run";
    case "workstation_progress":
      return "Workstation progress";
    case "primary_returned":
      return "Primary status returned";
    case "error":
      return "Error";
    case "unknown":
      return "Unknown";
  }
}

function guiBridgeStateLabel(value: GuiBridgeState): string {
  switch (value) {
    case "not_wired":
      return "Not wired from GUI";
    case "synthetic_only":
      return "Synthetic-only GUI run";
  }
}

const intakePrivacyNote = "No filenames, file counts, or folder contents are displayed by design.";
const intakeScopeNote =
  "Manual Finder intake only; real-matter Run, file picking, matter selection, and reset state remain disabled.";

function intakeReadinessForState(state: IntakeReadinessState): IntakeReadiness {
  switch (state) {
    case "before_refresh":
      return {
        state,
        tone: "warning",
        label: "Before refresh",
        message: "Refresh Status to verify the fixed intake path."
      };
    case "ready":
      return {
        state,
        tone: "safe",
        label: "Ready",
        message: "Approved intake folder is available. Use Finder to manually place copied evidence there."
      };
    case "missing":
      return {
        state,
        tone: "warning",
        label: "Missing",
        message: "Intake scaffold is missing. Run the Mac vault scaffold outside this GUI."
      };
    case "blocked":
      return {
        state,
        tone: "error",
        label: "Blocked",
        message: "Pause. Intake path failed a boundary check."
      };
    case "unknown":
      return {
        state,
        tone: "warning",
        label: "Unknown",
        message: "Intake readiness unknown. Refresh Status."
      };
  }
}

export function deriveIntakeReadiness(snapshot: LegalStatusSnapshot): IntakeReadiness {
  if (
    snapshot.boundary_state === "error" ||
    snapshot.errors.length > 0 ||
    snapshot.intake_target_kind === "not_directory"
  ) {
    return intakeReadinessForState("blocked");
  }

  if (snapshot.warnings.includes("status_refresh_not_run")) {
    return intakeReadinessForState("before_refresh");
  }

  if (snapshot.intake_folder_present && snapshot.intake_target_kind === "directory") {
    return intakeReadinessForState("ready");
  }

  if (snapshot.intake_target_kind === "missing") {
    return intakeReadinessForState("missing");
  }

  return intakeReadinessForState("unknown");
}

export function intakeReadinessFromOpenResult(result: IntakeOpenReadinessSignal): IntakeReadiness {
  if (result.boundary_state === "error" || result.errors.length > 0) {
    return intakeReadinessForState("blocked");
  }

  if (result.opened) {
    return intakeReadinessForState("ready");
  }

  return intakeReadinessForState("unknown");
}

export function renderIntakeReadinessPanel(readiness: IntakeReadiness): string {
  return `
    <section class="intake-readiness intake-readiness--${readiness.tone}" data-intake-readiness-state="${readiness.state}" aria-live="polite">
      <div class="intake-readiness__heading">
        <div>
          <p class="eyebrow">Intake readiness</p>
          <h3>Manual Finder Intake</h3>
        </div>
        <span class="state-chip state-chip--${readiness.tone}">${escapeHtml(readiness.label)}</span>
      </div>
      <p class="intake-readiness__message">${escapeHtml(readiness.message)}</p>
      <div class="intake-readiness__notes">
        <p>${escapeHtml(intakePrivacyNote)}</p>
        <p>${escapeHtml(intakeScopeNote)}</p>
      </div>
    </section>
  `;
}

function renderList(title: string, values: string[], className: string): string {
  if (values.length === 0) {
    return "";
  }

  return `
    <div class="status-message-list ${className}">
      <strong>${title}</strong>
      <ul>
        ${values.map((value) => `<li>${escapeHtml(value)}</li>`).join("")}
      </ul>
    </div>
  `;
}

export function renderStatusSnapshot(snapshot: LegalStatusSnapshot): string {
  const summary = (() => {
    if (snapshot.boundary_state === "error") {
      return "Status refresh stopped with a sanitized failure state.";
    }

    if (snapshot.processing_state === "primary_returned") {
      return "Primary status is present through the fixed output status path.";
    }

    if (snapshot.processing_state === "workstation_progress") {
      return "Workstation status indicates progress; the GUI shows sanitized status only.";
    }

    if (snapshot.scaffold_ready && snapshot.processing_state === "not_run") {
      return "Scaffold files are ready for the fixed synthetic-only Run wrapper.";
    }

    return "No live processing is implied by missing or pending status signals.";
  })();

  return `
    <section class="live-status live-status--${snapshot.boundary_state}" aria-live="polite">
      <div class="live-status__heading">
        <div>
          <p class="eyebrow">Read-only status snapshot</p>
          <h3>Live Status</h3>
          <p>${summary}</p>
        </div>
        <span class="state-chip state-chip--${snapshot.boundary_state}">${escapeHtml(snapshot.boundary_state)}</span>
      </div>
      <div class="live-status__grid">
        <div>
          <span>Workstation status file</span>
          <strong>${presentLabel(snapshot.workstation_status_present)}</strong>
        </div>
        <div>
          <span>Workstation state</span>
          <strong>${escapeHtml(snapshot.workstation_state)}</strong>
        </div>
        <div>
          <span>Workstation updated</span>
          <strong>${nullableLabel(snapshot.workstation_last_updated)}</strong>
        </div>
        <div>
          <span>Primary status file</span>
          <strong>${presentLabel(snapshot.primary_status_present)}</strong>
        </div>
        <div>
          <span>Primary state</span>
          <strong>${escapeHtml(snapshot.primary_state)}</strong>
        </div>
        <div>
          <span>Primary updated</span>
          <strong>${nullableLabel(snapshot.primary_last_updated)}</strong>
        </div>
        <div>
          <span>Intake folder</span>
          <strong>${presentLabel(snapshot.intake_folder_present)}</strong>
        </div>
        <div>
          <span>Intake target kind</span>
          <strong>${escapeHtml(intakeKindLabel(snapshot.intake_target_kind))}</strong>
        </div>
        <div>
          <span>Output guide</span>
          <strong>${presentLabel(snapshot.outputs_guide_present)}</strong>
        </div>
        <div>
          <span>Scaffold readiness</span>
          <strong>${readyLabel(snapshot.scaffold_ready)}</strong>
        </div>
        <div>
          <span>Processing state</span>
          <strong>${escapeHtml(processingStateLabel(snapshot.processing_state))}</strong>
        </div>
        <div>
          <span>GUI bridge</span>
          <strong>${escapeHtml(guiBridgeStateLabel(snapshot.gui_bridge_state))}</strong>
        </div>
      </div>
      ${renderList("Warnings", snapshot.warnings, "status-message-list--warning")}
      ${renderList("Errors", snapshot.errors, "status-message-list--error")}
    </section>
  `;
}