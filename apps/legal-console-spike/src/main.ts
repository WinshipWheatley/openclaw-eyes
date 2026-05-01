import "./styles.css";
import {
  createSyntheticTestFile,
  renderSyntheticTestFileResult,
  syntheticTestFileResultFromError
} from "./legalDummy";
import { intakeOpenResultFromError, openIntakeFolder, renderIntakeOpenResult } from "./legalIntake";
import { renderLegalConsole } from "./legalConsole";
import {
  renderSyntheticDryRunResult,
  renderSyntheticDryRunStarted,
  runSyntheticDryRun,
  syntheticDryRunResultFromError
} from "./legalRun";
import {
  deriveIntakeReadiness,
  getStatusSnapshot,
  intakeReadinessFromOpenResult,
  renderIntakeReadinessPanel,
  renderStatusSnapshot,
  statusSnapshotFromError
} from "./legalStatus";

const app = document.querySelector<HTMLDivElement>("#app");
const themeStorageKey = "openclaw-legal-console-theme";
const themeOptions = ["dark", "light", "horizon"] as const;
type ConsoleTheme = (typeof themeOptions)[number];

if (!app) {
  throw new Error("Legal console root element was not found.");
}

app.innerHTML = renderLegalConsole();

const refreshButton = document.querySelector<HTMLButtonElement>("[data-refresh-status]");
const statusTarget = document.querySelector<HTMLDivElement>("[data-status-snapshot]");
const intakeButton = document.querySelector<HTMLButtonElement>("[data-open-intake]");
const intakeTarget = document.querySelector<HTMLDivElement>("[data-intake-result]");
const syntheticTestButton = document.querySelector<HTMLButtonElement>("[data-create-synthetic-test]");
const syntheticTestTarget = document.querySelector<HTMLDivElement>("[data-synthetic-test-result]");
const syntheticRunButton = document.querySelector<HTMLButtonElement>("[data-run-synthetic-dry-run]");
const syntheticRunTarget = document.querySelector<HTMLDivElement>("[data-synthetic-run-result]");
const intakeReadinessTarget = document.querySelector<HTMLDivElement>("[data-intake-readiness]");
const themeButtons = document.querySelectorAll<HTMLButtonElement>("[data-theme-option]");

function isConsoleTheme(value: string | null): value is ConsoleTheme {
  return themeOptions.some((theme) => theme === value);
}

function readStoredTheme(): ConsoleTheme {
  try {
    const storedTheme = window.localStorage.getItem(themeStorageKey);
    return isConsoleTheme(storedTheme) ? storedTheme : "horizon";
  } catch {
    return "horizon";
  }
}

function writeStoredTheme(theme: ConsoleTheme): void {
  try {
    window.localStorage.setItem(themeStorageKey, theme);
  } catch {
    return;
  }
}

function applyTheme(theme: ConsoleTheme): void {
  document.documentElement.dataset.theme = theme;
  themeButtons.forEach((button) => {
    const isActive = button.dataset.themeOption === theme;
    button.setAttribute("aria-pressed", String(isActive));
  });
}

themeButtons.forEach((button) => {
  button.addEventListener("click", () => {
    const theme = button.dataset.themeOption ?? null;

    if (!isConsoleTheme(theme)) {
      return;
    }

    applyTheme(theme);
    writeStoredTheme(theme);
  });
});

applyTheme(readStoredTheme());

function setStatusMarkup(markup: string): void {
  if (statusTarget) {
    statusTarget.innerHTML = markup;
  }
}

function setIntakeMarkup(markup: string): void {
  if (intakeTarget) {
    intakeTarget.innerHTML = markup;
  }
}

function setSyntheticTestMarkup(markup: string): void {
  if (syntheticTestTarget) {
    syntheticTestTarget.innerHTML = markup;
  }
}

function setSyntheticRunMarkup(markup: string): void {
  if (syntheticRunTarget) {
    syntheticRunTarget.innerHTML = markup;
  }
}

function setIntakeReadinessMarkup(markup: string): void {
  if (intakeReadinessTarget) {
    intakeReadinessTarget.innerHTML = markup;
  }
}

intakeButton?.addEventListener("click", async () => {
  intakeButton.disabled = true;
  intakeButton.setAttribute("aria-busy", "true");

  try {
    const result = await openIntakeFolder();
    setIntakeMarkup(renderIntakeOpenResult(result));
    setIntakeReadinessMarkup(renderIntakeReadinessPanel(intakeReadinessFromOpenResult(result)));
  } catch (error) {
    const result = intakeOpenResultFromError(error);
    setIntakeMarkup(renderIntakeOpenResult(result));
    setIntakeReadinessMarkup(renderIntakeReadinessPanel(intakeReadinessFromOpenResult(result)));
  } finally {
    intakeButton.disabled = false;
    intakeButton.removeAttribute("aria-busy");
  }
});

syntheticTestButton?.addEventListener("click", async () => {
  syntheticTestButton.disabled = true;
  syntheticTestButton.setAttribute("aria-busy", "true");

  try {
    const result = await createSyntheticTestFile();
    setSyntheticTestMarkup(renderSyntheticTestFileResult(result));
  } catch (error) {
    const result = syntheticTestFileResultFromError(error);
    setSyntheticTestMarkup(renderSyntheticTestFileResult(result));
  } finally {
    syntheticTestButton.disabled = false;
    syntheticTestButton.removeAttribute("aria-busy");
  }
});

syntheticRunButton?.addEventListener("click", async () => {
  syntheticRunButton.disabled = true;
  syntheticRunButton.setAttribute("aria-busy", "true");
  setSyntheticRunMarkup(renderSyntheticDryRunStarted());

  try {
    const result = await runSyntheticDryRun();
    setSyntheticRunMarkup(renderSyntheticDryRunResult(result));
  } catch (error) {
    const result = syntheticDryRunResultFromError(error);
    setSyntheticRunMarkup(renderSyntheticDryRunResult(result));
  } finally {
    syntheticRunButton.disabled = false;
    syntheticRunButton.removeAttribute("aria-busy");
  }
});

refreshButton?.addEventListener("click", async () => {
  refreshButton.disabled = true;
  refreshButton.setAttribute("aria-busy", "true");

  try {
    const snapshot = await getStatusSnapshot();
    setStatusMarkup(renderStatusSnapshot(snapshot));
    setIntakeReadinessMarkup(renderIntakeReadinessPanel(deriveIntakeReadiness(snapshot)));
  } catch (error) {
    const message = error instanceof Error ? error.message : "Status refresh failed.";
    const snapshot = statusSnapshotFromError(message);
    setStatusMarkup(renderStatusSnapshot(snapshot));
    setIntakeReadinessMarkup(renderIntakeReadinessPanel(deriveIntakeReadiness(snapshot)));
  } finally {
    refreshButton.disabled = false;
    refreshButton.removeAttribute("aria-busy");
  }
});