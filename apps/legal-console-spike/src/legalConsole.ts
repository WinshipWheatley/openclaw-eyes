import { osAdapters, primaryNodeTransports, sharedUiResponsibilities } from "./legalAdapters";
import { proofTargetConfig, displayPath } from "./legalPaths";
import { initialStatusSnapshot, renderStatusSnapshot } from "./legalStatus";

const brandMarkAssetUrl = new URL("./assets/visual-kit/brand-mark.svg", import.meta.url).href;
const sidebarMountainDarkAssetUrl = new URL("./assets/visual-kit/sidebar-mountain-dark.svg", import.meta.url)
  .href;
const sidebarMountainLightAssetUrl = new URL("./assets/visual-kit/sidebar-mountain-light.svg", import.meta.url)
  .href;
const heroMountainDarkAssetUrl = new URL("./assets/visual-kit/hero-mountain-dark.svg", import.meta.url).href;
const heroMountainLightAssetUrl = new URL("./assets/visual-kit/hero-mountain-light.svg", import.meta.url).href;

const themeOptions = [
  { id: "dark", label: "Dark" },
  { id: "light", label: "Light" },
  { id: "horizon", label: "Horizon" }
] as const;

const navItems = [
  { id: "overview", label: "Overview", icon: "grid", active: true },
  { id: "intake", label: "Intake", icon: "doc", active: false },
  { id: "status", label: "Status", icon: "wave", active: false },
  { id: "settings", label: "Settings", icon: "gear", active: false },
  { id: "about", label: "About", icon: "info", active: false }
] as const;

const disabledActions = [
  { label: "Add Dummy File", detail: "Not wired in this phase", icon: "plus" },
  { label: "Run Dry Run", detail: "Not wired in this phase", icon: "play" },
  { label: "Reset Local Test", detail: "Not wired in this phase", icon: "refresh" },
  { label: "Reset All Test State", detail: "Not wired in this phase", icon: "trash" }
] as const;

const workstationRows = [
  { label: "Workspace Vault", value: proofTargetConfig.workstationVaultPath, tone: "path", icon: "wave" },
  { label: "Intake Folder", value: displayPath(proofTargetConfig.intakeFolderPath, 2), tone: "path", icon: "folder" },
  { label: "Status File", value: displayPath(proofTargetConfig.workstationStatusPath, 2), tone: "path", icon: "doc" },
  { label: "Status Mode", value: "Read-only status snapshot", tone: "value", icon: "pulse" }
] as const;

const pathRows = [
  { label: "Private Root (PC)", value: proofTargetConfig.primaryNodePrivateRoot, tone: "path", icon: "lock" },
  { label: "Vault Root (PC)", value: proofTargetConfig.primaryNodeVaultRoot, tone: "path", icon: "folder" },
  { label: "Workspace Vault", value: proofTargetConfig.workstationVaultPath, tone: "path", icon: "wave" },
  { label: "Intake Folder", value: displayPath(proofTargetConfig.intakeFolderPath, 2), tone: "path", icon: "folder" },
  { label: "Primary Status File", value: displayPath(proofTargetConfig.primaryStatusPath, 2), tone: "path", icon: "doc" },
  { label: "Output Guide Check", value: displayPath(proofTargetConfig.outputGuidePath, 2), tone: "path", icon: "check" },
  { label: "Transport", value: proofTargetConfig.transport, tone: "value", icon: "pulse" },
  { label: "OS Target", value: proofTargetConfig.primaryNodeOs, tone: "value", icon: "gear" }
] as const;

const boundaryBadges = [
  { label: "Matter Data in Vault", value: "Blocked", tone: "stop", icon: "lock" },
  { label: "Private Root", value: "Configured outside repo", tone: "ok", icon: "check" },
  { label: "Bridge Commands", value: "Not wired", tone: "hold", icon: "alert" },
  { label: "Live Status Refresh", value: "Read-only", tone: "ok", icon: "check" }
] as const;

const icons: Record<string, string> = {
  grid: '<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6"><rect x="3" y="3" width="6" height="6" rx="1.2"/><rect x="11" y="3" width="6" height="6" rx="1.2"/><rect x="3" y="11" width="6" height="6" rx="1.2"/><rect x="11" y="11" width="6" height="6" rx="1.2"/></svg>',
  doc: '<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M5 3h7l3 3v11a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1z"/><path d="M12 3v3h3"/></svg>',
  wave: '<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M2 11h3l2-6 3 12 3-9 2 5h3"/></svg>',
  gear: '<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6"><circle cx="10" cy="10" r="2.6"/><path d="M10 2v2.4M10 15.6V18M2 10h2.4M15.6 10H18M4.6 4.6l1.7 1.7M13.7 13.7l1.7 1.7M4.6 15.4l1.7-1.7M13.7 6.3l1.7-1.7"/></svg>',
  info: '<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6"><circle cx="10" cy="10" r="7.4"/><path d="M10 9.2v4.4M10 6.4v.6"/></svg>',
  shield: '<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"><path d="M10 2.4 3.4 4.8v5.1c0 4 2.7 6.7 6.6 7.7 3.9-1 6.6-3.7 6.6-7.7V4.8L10 2.4z"/><path d="m7.4 10.2 1.9 1.9 3.3-3.6"/></svg>',
  lock: '<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6"><rect x="4.5" y="9" width="11" height="8" rx="1.4"/><path d="M7 9V6.6a3 3 0 0 1 6 0V9"/></svg>',
  check: '<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><circle cx="10" cy="10" r="7.4"/><path d="m6.8 10.2 2.2 2.2 4.2-4.4"/></svg>',
  alert: '<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M10 3 2.6 16.2h14.8L10 3z"/><path d="M10 8.4v3.4M10 13.8v.4"/></svg>',
  plus: '<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"><path d="M5 7h7l3 3v6a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V8a1 1 0 0 1 1-1z" stroke-linejoin="round"/><path d="M9.6 12h2.8M11 10.6v2.8"/></svg>',
  play: '<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"><circle cx="10" cy="10" r="7.4"/><path d="M8.5 7.4 13 10l-4.5 2.6V7.4z" fill="currentColor" stroke="none"/></svg>',
  refresh: '<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M4 10a6 6 0 0 1 10.4-4.1L16.5 8"/><path d="M16.5 4.5V8H13"/><path d="M16 10a6 6 0 0 1-10.4 4.1L3.5 12"/><path d="M3.5 15.5V12H7"/></svg>',
  trash: '<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M4.5 6h11"/><path d="M6.5 6V4.6a1 1 0 0 1 1-1h5a1 1 0 0 1 1 1V6"/><path d="M6 6.6 7 16.4a1 1 0 0 0 1 .9h4a1 1 0 0 0 1-.9L14 6.6"/></svg>',
  folder: '<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"><path d="M2.8 5.4a1 1 0 0 1 1-1h3.5l1.6 1.8h7.3a1 1 0 0 1 1 1V15a1 1 0 0 1-1 1H3.8a1 1 0 0 1-1-1V5.4z"/></svg>',
  pulse: '<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M3 10h3l1.6-4 2.8 8 2-5h4.6"/></svg>'
};

function escapeAttribute(value: string): string {
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

function renderDecorativeAsset(src: string, className: string): string {
  return `<img class="${className}" src="${escapeAttribute(src)}" alt="" aria-hidden="true" />`;
}

function renderNavItem(item: (typeof navItems)[number]): string {
  return `
    <li>
      <button class="nav-item${item.active ? " is-active" : ""}" type="button"
              data-nav="${item.id}" aria-current="${item.active ? "page" : "false"}"
              ${item.active ? "" : "disabled"}>
        <span class="nav-item__icon" aria-hidden="true">${icons[item.icon]}</span>
        <span class="nav-item__label">${item.label}</span>
      </button>
    </li>
  `;
}

function renderThemePicker(): string {
  return `
    <div class="theme-picker" role="group" aria-label="Theme">
      ${themeOptions
        .map(
          (theme) =>
            `<button class="theme-dot" type="button" data-theme-option="${theme.id}"
                     aria-pressed="false" data-theme-tone="${theme.id}">
               <span>${theme.label}</span>
             </button>`
        )
        .join("")}
    </div>
  `;
}

function renderProofTargetCard(): string {
  return `
    <article class="card card--proof" aria-labelledby="proof-target-title">
      <header class="card__head">
        <div>
          <p class="eyebrow">Proof Target</p>
          <h2 id="proof-target-title">Mac Workstation Console</h2>
        </div>
        <span class="os-pill">macOS</span>
      </header>

      <div class="proof-command-panel">
        <div class="scope-note">
          <span class="scope-note__icon" aria-hidden="true">${icons.shield}</span>
          <p>
            This phase is strictly limited to status refresh and intake folder access.
            No file picker, no command execution, no bridge run, no dummy-file creation,
            no private data.
          </p>
        </div>

        <button class="action action--primary action--hero" type="button" data-open-intake>
          <span class="action__icon" aria-hidden="true">${icons.folder}</span>
          <span class="action__body">
            <strong>Open Intake Folder</strong>
            <small>Opens exact drop folder only</small>
          </span>
        </button>
      </div>

      <div class="action-result" data-intake-result></div>

      <div class="detail-rows detail-rows--workstation" aria-label="Workstation proof details">
        ${workstationRows.map(renderDetailRowItem).join("")}
      </div>

      <div class="disabled-actions" aria-label="Future actions">
        ${disabledActions
          .map(
            (action) => `
              <button class="action action--disabled" type="button" disabled aria-disabled="true">
                <span class="action__icon" aria-hidden="true">${icons[action.icon]}</span>
                <span class="action__body">
                  <strong>${action.label}</strong>
                  <small>${action.detail}</small>
                </span>
              </button>
            `
          )
          .join("")}
      </div>
    </article>
  `;
}

function renderDetailRowItem(row: (typeof workstationRows)[number]): string {
  return `
    <div class="detail-row">
      <span class="detail-row__label">${row.label}</span>
      <code class="detail-row__value detail-row__value--${row.tone}" title="${escapeAttribute(row.value)}">${row.value}</code>
    </div>
  `;
}

function renderPathRowItem(row: (typeof pathRows)[number]): string {
  return `
    <div class="status-row">
      <span class="status-row__icon" aria-hidden="true">${icons[row.icon]}</span>
      <span class="status-row__label">${row.label}</span>
      <code class="status-row__value status-row__value--${row.tone}" title="${escapeAttribute(row.value)}">${row.value}</code>
    </div>
  `;
}

function renderBoundaryBadge(badge: (typeof boundaryBadges)[number]): string {
  return `
    <div class="boundary-badge boundary-badge--${badge.tone}">
      <span class="boundary-badge__icon" aria-hidden="true">${icons[badge.icon]}</span>
      <span class="boundary-badge__label">${badge.label}</span>
      <span class="boundary-badge__value">${badge.value}</span>
    </div>
  `;
}

function renderStatusCard(): string {
  return `
    <article class="card card--status" aria-labelledby="status-title">
      <header class="card__head card__head--status">
        <div class="card__head-title">
          <span class="pulse-dot" aria-hidden="true"></span>
          <p class="eyebrow eyebrow--strong" id="status-title">Live Status Snapshot</p>
        </div>
        <div class="status-actions">
          <span class="state-chip state-chip--quiet">Read-only</span>
          <button class="action action--secondary action--refresh" type="button" data-refresh-status>
            <span class="action__icon" aria-hidden="true">${icons.refresh}</span>
            <span class="action__body">
              <strong>Refresh Status</strong>
              <small>Reads fixed status files only</small>
            </span>
          </button>
        </div>
      </header>

      <div class="status-body">
        <aside class="status-side" aria-label="Boundary posture">
          ${boundaryBadges.map(renderBoundaryBadge).join("")}
        </aside>
        <div class="status-rows" aria-label="Fixed proof coordinates">
          ${pathRows.map(renderPathRowItem).join("")}
        </div>
      </div>

      <div class="status-snapshot-slot" data-status-snapshot>
        ${renderStatusSnapshot(initialStatusSnapshot)}
      </div>
    </article>
  `;
}

function renderArchitectureSection(): string {
  return `
    <section class="card card--arch" aria-labelledby="arch-title">
      <header class="card__head">
        <div>
          <p class="eyebrow">Architecture</p>
          <h2 id="arch-title">Architecture at a Glance</h2>
        </div>
      </header>

      <div class="arch-grid">
        <section class="arch-col">
          <h3>Shared UI (macOS)</h3>
          <ul class="arch-list arch-list--checks">
            ${sharedUiResponsibilities.map((item) => `<li>${item}</li>`).join("")}
          </ul>
        </section>

        <section class="arch-col">
          <h3>OS Adapters</h3>
          <ul class="arch-list arch-list--rows">
            ${osAdapters
              .map(
                (adapter) => `
                  <li>
                    <div class="arch-row__head">
                      <strong>${adapter.label}</strong>
                      <span class="arch-row__state arch-row__state--${stateTone(adapter.state)}">${adapter.state}</span>
                    </div>
                    <p>${adapter.detail}</p>
                  </li>
                `
              )
              .join("")}
          </ul>
        </section>

        <section class="arch-col arch-col--primary">
          <h3>Primary Node Transports</h3>
          <ul class="arch-list arch-list--rows">
            ${primaryNodeTransports
              .map(
                (t) => `
                  <li>
                    <div class="arch-row__head">
                      <strong>${t.label}</strong>
                      <span class="arch-row__state arch-row__state--${stateTone(t.state)}">${t.state}</span>
                    </div>
                    <p>${t.detail}</p>
                  </li>
                `
              )
              .join("")}
          </ul>
        </section>
      </div>
    </section>
  `;
}

function stateTone(state: string): "active" | "planned" | "future" {
  if (state === "current proof path") return "active";
  if (state === "planned stub") return "planned";
  return "future";
}

export function renderLegalConsole(): string {
  return `
    <div class="app-shell">
      <aside class="rail" aria-label="Console navigation">
        <div class="window-dots" aria-hidden="true">
          <span></span>
          <span></span>
          <span></span>
        </div>

        <div class="rail__brand">
          <span class="brand-mark" aria-hidden="true">${renderDecorativeAsset(brandMarkAssetUrl, "brand-mark__asset")}</span>
          <div class="brand-text">
            <strong>OPENCLAW</strong>
            <span>LEGAL CONSOLE</span>
          </div>
        </div>

        <span class="phase-pill" aria-label="Current phase">Phase 2B</span>

        <nav class="rail__nav" aria-label="Sections">
          <ul>
            ${navItems.map(renderNavItem).join("")}
          </ul>
        </nav>

        <div class="rail__scene" aria-hidden="true">
          ${renderDecorativeAsset(sidebarMountainDarkAssetUrl, "rail-scene rail-scene--dark")}
          ${renderDecorativeAsset(sidebarMountainLightAssetUrl, "rail-scene rail-scene--light")}
        </div>

        <div class="rail__footer">
          ${renderThemePicker()}
          <div class="node-status">
            <p class="eyebrow eyebrow--soft">Node Status</p>
            <div class="node-status__row">
              <strong>PC/WSL Primary</strong>
            </div>
            <div class="node-status__row node-status__row--live">
              <span class="live-dot" aria-hidden="true"></span>
              <span>Online</span>
            </div>
          </div>
        </div>
      </aside>

      <main class="surface" role="main">
        <header class="surface__head">
          <div class="surface__title">
            <h1>Welcome to OpenClaw Legal Console</h1>
            <p>A secure, local-first desktop console for your legal intake workflow.</p>
          </div>
          <div class="surface__proof" aria-label="Proof environment">
            <span class="proof-shield" aria-hidden="true">${icons.shield}</span>
            <div class="proof-text">
              <strong>STATIC CONTROLLED UX PROOF</strong>
              <span>NO REAL MATTER DATA</span>
            </div>
          </div>
          <div class="surface__hero-scene" aria-hidden="true">
            ${renderDecorativeAsset(heroMountainDarkAssetUrl, "hero-scene hero-scene--dark")}
            ${renderDecorativeAsset(heroMountainLightAssetUrl, "hero-scene hero-scene--light")}
          </div>
        </header>

        <section class="surface__grid">
          ${renderProofTargetCard()}
          ${renderStatusCard()}
        </section>

        ${renderArchitectureSection()}

        <footer class="surface__footer" aria-label="Operating posture">
          <span class="footer-shield" aria-hidden="true">${icons.shield}</span>
          <p>OpenClaw stays local, private, and under your control.</p>
          <span class="footer-divider" aria-hidden="true"></span>
          <p class="footer-claim">No cloud. No telemetry. No compromises.</p>
        </footer>
      </main>
    </div>
  `;
}
