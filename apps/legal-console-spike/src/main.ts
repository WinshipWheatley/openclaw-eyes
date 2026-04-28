import "./styles.css";
import { renderLegalConsole } from "./legalConsole";

const app = document.querySelector<HTMLDivElement>("#app");

if (!app) {
  throw new Error("Legal console root element was not found.");
}

app.innerHTML = renderLegalConsole();