import type { OsType, TransportType } from "./legalPaths";

type AdapterState = "current proof path" | "planned stub" | "future target";

export interface OsAdapterStatus {
  label: string;
  os: OsType;
  state: AdapterState;
  detail: string;
}

export interface PrimaryNodeTransportStatus {
  label: string;
  transport: TransportType | "firm-local API";
  state: AdapterState;
  detail: string;
}

export const sharedUiResponsibilities = [
  "status display",
  "intake workflow",
  "run and reset controls",
  "output locations",
  "boundary warnings"
];

export const osAdapters: OsAdapterStatus[] = [
  {
    label: "macOS workstation",
    os: "macos",
    state: "current proof path",
    detail: "Shows the configured private workstation vault and exact intake folder."
  },
  {
    label: "Windows workstation",
    os: "windows",
    state: "planned stub",
    detail: "Reserved for a future workstation adapter with explicit vault configuration."
  },
  {
    label: "Linux workstation",
    os: "linux",
    state: "planned stub",
    detail: "Reserved for a future local workstation adapter."
  },
  {
    label: "WSL Primary Node",
    os: "wsl",
    state: "current proof path",
    detail: "Represents the PC/WSL primary-node paths used by the existing bridge."
  }
];

export const primaryNodeTransports: PrimaryNodeTransportStatus[] = [
  {
    label: "local",
    transport: "local",
    state: "future target",
    detail: "For a workstation and Primary Node on the same machine."
  },
  {
    label: "ssh",
    transport: "ssh",
    state: "current proof path",
    detail: "For the Mac workstation to PC/WSL Primary Node proof target."
  },
  {
    label: "firm-local API",
    transport: "firm-local API",
    state: "future target",
    detail: "For a later firm-controlled service endpoint without changing the console model."
  }
];