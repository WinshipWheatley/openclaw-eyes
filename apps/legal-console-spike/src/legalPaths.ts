export type TransportType = "local" | "ssh";
export type OsType = "macos" | "windows" | "linux" | "wsl";

export interface LegalConsoleConfig {
  productCodePath: string;
  workstationVaultPath: string;
  intakeFolderPath: string;
  workstationStatusPath: string;
  primaryStatusPath: string;
  outputGuidePath: string;
  primaryNodePrivateRoot: string;
  primaryNodeVaultRoot: string;
  stagingPath: string;
  exportsPath: string;
  transport: TransportType;
  workstationOs: OsType;
  primaryNodeOs: OsType;
}

export const proofTargetConfig: LegalConsoleConfig = {
  productCodePath: "/home/openclaw",
  workstationVaultPath: "~/OpenClawLegalPrivate/Matter_Alpha_Workspace",
  intakeFolderPath: "~/OpenClawLegalPrivate/Matter_Alpha_Workspace/01_DROP_FILES_HERE",
  workstationStatusPath: "~/OpenClawLegalPrivate/Matter_Alpha_Workspace/03_WORKSTATION_STATUS.md",
  primaryStatusPath: "~/OpenClawLegalPrivate/Matter_Alpha_Workspace/04_OUTPUTS/PRIMARY_NODE_STATUS.md",
  outputGuidePath: "~/OpenClawLegalPrivate/Matter_Alpha_Workspace/04_OUTPUTS/00_OPEN_THIS_FIRST.md",
  primaryNodePrivateRoot: "/mnt/c/OpenClawLegalPrivate",
  primaryNodeVaultRoot: "/mnt/c/OpenClawLegalPrivate/vault",
  stagingPath: "/mnt/c/OpenClawLegalPrivate/staging/bridge_synthetic_proof_20260430",
  exportsPath: "/mnt/c/OpenClawLegalPrivate/exports/bridge_synthetic_proof_20260430",
  transport: "ssh",
  workstationOs: "macos",
  primaryNodeOs: "wsl"
};

export const safetyStatements = [
  "No real matter data",
  "No legal advice",
  "Local-only proof surface",
  "Dummy or synthetic files only",
  "Matter data must not enter /home/openclaw",
  "No real-matter processing commands wired"
];

export function displayPath(value: string, leadingSegments = 2): string {
  const parts = value.split("/").filter(Boolean);

  if (parts.length <= leadingSegments + 2 || value.startsWith("~")) {
    return value;
  }

  return `/${parts.slice(0, leadingSegments).join("/")}/.../${parts[parts.length - 1]}`;
}