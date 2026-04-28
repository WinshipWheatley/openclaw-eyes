export type TransportType = "local" | "ssh";
export type OsType = "macos" | "windows" | "linux" | "wsl";

export interface LegalConsoleConfig {
  productCodePath: string;
  workstationVaultPath: string;
  intakeFolderPath: string;
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
  primaryNodePrivateRoot: "/mnt/c/OpenClawLegalPrivate",
  primaryNodeVaultRoot: "/mnt/c/OpenClawLegalPrivate/vault",
  stagingPath: "/mnt/c/OpenClawLegalPrivate/staging/matter_alpha",
  exportsPath: "/mnt/c/OpenClawLegalPrivate/exports/matter_alpha",
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
  "Command execution is not wired yet"
];