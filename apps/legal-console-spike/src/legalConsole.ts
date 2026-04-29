import { osAdapters, primaryNodeTransports, sharedUiResponsibilities } from "./legalAdapters";
import { proofTargetConfig, safetyStatements } from "./legalPaths";
import { initialStatusSnapshot, renderStatusSnapshot } from "./legalStatus";

const disabledControls = [
  "Add Dummy File",
  "Run Dry Run",
  "Reset Local Test",
  "Reset All Test State"
];

function renderPathRow(label: string, value: string): string {
  return `
    <div class="path-row">
      <span>${label}</span>
      <code>${value}</code>
    </div>
  `;
}

function renderDisabledButton(label: string): string {
  return `
    <button class="disabled-control" type="button" disabled aria-disabled="true">
      <span>${label}</span>
      <small>Not wired in this phase</small>
    </button>
  `;
}

function renderOpenIntakeButton(): string {
  return `
    <button class="intake-open-button" type="button" data-open-intake>
      <span>Open Intake Folder</span>
      <small>Opens exact drop folder only</small>
    </button>
  `;
}

function renderStatusCard(title: string, value: string, tone: "ok" | "hold" | "stop" = "hold"): string {
  return `
    <article class="status-card status-card--${tone}">
      <span>${title}</span>
      <strong>${value}</strong>
    </article>
  `;
}

export function renderLegalConsole(): string {
  return `
    <section class="shell" aria-labelledby="console-title">
      <header class="topbar">
        <div>
          <p class="eyebrow">Static controlled UX proof</p>
          <h1 id="console-title">OpenClaw Legal Console Prototype</h1>
          <p class="summary">A disposable desktop-console scaffold for the Mac workstation to PC/WSL Primary Node proof path.</p>
        </div>
        <div class="phase-badge" aria-label="Phase status">
          <strong>Phase 2B</strong>
          <span>Open intake folder only</span>
        </div>
      </header>

      <section class="safety-strip" aria-label="Safety boundaries">
        ${safetyStatements.map((statement) => `<span>${statement}</span>`).join("")}
      </section>

      <section class="panel-grid" aria-label="Console panels">
        <article class="panel panel--workstation">
          <div class="panel-heading">
            <div>
              <p class="eyebrow">Current proof target</p>
              <h2>Mac Workstation Console</h2>
            </div>
            <span class="os-pill">macOS</span>
          </div>
          <div class="warning-box">
            Only status refresh and exact intake-folder opening are wired in this phase; no file picker, command execution, bridge run, dummy-file creation, or private content display is wired.
          </div>
          <div class="path-list">
            ${renderPathRow("Configured workstation vault", proofTargetConfig.workstationVaultPath)}
            ${renderPathRow("Exact intake folder", proofTargetConfig.intakeFolderPath)}
            ${renderPathRow("Workstation status", proofTargetConfig.workstationStatusPath)}
          </div>
          <div class="control-grid" aria-label="Disabled workstation controls">
            <div class="intake-action">
              ${renderOpenIntakeButton()}
              <div data-intake-result></div>
            </div>
            ${disabledControls.map(renderDisabledButton).join("")}
          </div>
        </article>

        <article class="panel panel--primary">
          <div class="panel-heading">
            <div>
              <p class="eyebrow">Primary Node abstraction</p>
              <h2>PC/WSL Primary Node Console</h2>
            </div>
            <span class="os-pill">WSL</span>
          </div>
          <div class="path-list">
            ${renderPathRow("Product code path", proofTargetConfig.productCodePath)}
            ${renderPathRow("PC private root", proofTargetConfig.primaryNodePrivateRoot)}
            ${renderPathRow("Vault root", proofTargetConfig.primaryNodeVaultRoot)}
            ${renderPathRow("Staging path", proofTargetConfig.stagingPath)}
            ${renderPathRow("Exports path", proofTargetConfig.exportsPath)}
            ${renderPathRow("Returned status", proofTargetConfig.primaryStatusPath)}
            ${renderPathRow("Output guide check", proofTargetConfig.outputGuidePath)}
            ${renderPathRow("Transport", proofTargetConfig.transport)}
            ${renderPathRow("OS target", proofTargetConfig.primaryNodeOs)}
          </div>
          <div class="status-grid" aria-label="Boundary status">
            ${renderStatusCard("Matter data in /home/openclaw", "Blocked", "stop")}
            ${renderStatusCard("Private root", "Configured outside repo", "ok")}
            ${renderStatusCard("Bridge commands", "Not wired", "hold")}
            ${renderStatusCard("Live status refresh", "Read-only", "ok")}
          </div>
          <button class="status-refresh-button" type="button" data-refresh-status>
            <span>Refresh Status</span>
            <small>Reads fixed status files only</small>
          </button>
          <div data-status-snapshot>
            ${renderStatusSnapshot(initialStatusSnapshot)}
          </div>
        </article>

        <article class="panel panel--architecture">
          <div class="panel-heading">
            <div>
              <p class="eyebrow">Architecture shape</p>
              <h2>Cross-Platform Architecture</h2>
            </div>
          </div>
          <div class="architecture-grid">
            <section>
              <h3>Shared UI</h3>
              <ul>
                ${sharedUiResponsibilities.map((item) => `<li>${item}</li>`).join("")}
              </ul>
            </section>
            <section>
              <h3>OS Adapters</h3>
              <ul class="adapter-list">
                ${osAdapters
                  .map(
                    (adapter) => `<li><strong>${adapter.label}</strong><span>${adapter.state}</span><p>${adapter.detail}</p></li>`
                  )
                  .join("")}
              </ul>
            </section>
            <section>
              <h3>Primary Node Transports</h3>
              <ul class="adapter-list">
                ${primaryNodeTransports
                  .map(
                    (transport) => `<li><strong>${transport.label}</strong><span>${transport.state}</span><p>${transport.detail}</p></li>`
                  )
                  .join("")}
              </ul>
            </section>
          </div>
        </article>
      </section>
    </section>
  `;
}