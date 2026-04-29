import "./styles.css";
import { intakeOpenResultFromError, openIntakeFolder, renderIntakeOpenResult } from "./legalIntake";
import { renderLegalConsole } from "./legalConsole";
import { getStatusSnapshot, renderStatusSnapshot, statusSnapshotFromError } from "./legalStatus";

const app = document.querySelector<HTMLDivElement>("#app");

if (!app) {
  throw new Error("Legal console root element was not found.");
}

app.innerHTML = renderLegalConsole();

const refreshButton = document.querySelector<HTMLButtonElement>("[data-refresh-status]");
const statusTarget = document.querySelector<HTMLDivElement>("[data-status-snapshot]");
const intakeButton = document.querySelector<HTMLButtonElement>("[data-open-intake]");
const intakeTarget = document.querySelector<HTMLDivElement>("[data-intake-result]");

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

intakeButton?.addEventListener("click", async () => {
  intakeButton.disabled = true;
  intakeButton.setAttribute("aria-busy", "true");

  try {
    const result = await openIntakeFolder();
    setIntakeMarkup(renderIntakeOpenResult(result));
  } catch (error) {
    setIntakeMarkup(renderIntakeOpenResult(intakeOpenResultFromError(error)));
  } finally {
    intakeButton.disabled = false;
    intakeButton.removeAttribute("aria-busy");
  }
});

refreshButton?.addEventListener("click", async () => {
  refreshButton.disabled = true;
  refreshButton.setAttribute("aria-busy", "true");

  try {
    const snapshot = await getStatusSnapshot();
    setStatusMarkup(renderStatusSnapshot(snapshot));
  } catch (error) {
    const message = error instanceof Error ? error.message : "Status refresh failed.";
    setStatusMarkup(renderStatusSnapshot(statusSnapshotFromError(message)));
  } finally {
    refreshButton.disabled = false;
    refreshButton.removeAttribute("aria-busy");
  }
});