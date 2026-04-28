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
export type BoundaryState = "safe" | "warning" | "error";

export interface LegalStatusSnapshot {
  workstation_status_present: boolean;
  workstation_state: WorkstationState;
  workstation_last_updated: string | null;
  primary_status_present: boolean;
  primary_state: PrimaryState;
  primary_last_updated: string | null;
  outputs_guide_present: boolean;
  boundary_state: BoundaryState;
  warnings: string[];
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
  outputs_guide_present: false,
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
  return value ? "Present" : "Missing";
}

function nullableLabel(value: string | null): string {
  return value ? escapeHtml(value) : "Not reported";
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
  return `
    <section class="live-status live-status--${snapshot.boundary_state}" aria-live="polite">
      <div class="live-status__heading">
        <div>
          <p class="eyebrow">Read-only status snapshot</p>
          <h3>Live Status</h3>
        </div>
        <span>${escapeHtml(snapshot.boundary_state)}</span>
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
          <span>Output guide</span>
          <strong>${presentLabel(snapshot.outputs_guide_present)}</strong>
        </div>
      </div>
      ${renderList("Warnings", snapshot.warnings, "status-message-list--warning")}
      ${renderList("Errors", snapshot.errors, "status-message-list--error")}
    </section>
  `;
}