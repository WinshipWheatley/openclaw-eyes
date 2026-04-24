# Google Contract — Candidate MCP / Drive Integration Note
Status: candidate setup note / needs live verification  
Current location: OpenClaw docs candidate note  
Authority level: non-canonical until tested and intentionally promoted
## Purpose
This note captures a candidate contract for giving agentic coding/model tools access to Google Drive through MCP.
The immediate target is Gemini CLI in WSL. Codex, Claude Code, Hermes, and local model wrappers should not be assumed to share this setup until each tool’s MCP support and config path are verified.
## Current assumption
Google Drive API has been enabled or is expected to be enabled.
The remaining bridge is:
1. Tell the model/CLI environment where the Google Workspace MCP server is configured.
2. Provide OAuth client ID and secret through the local MCP client settings file.
3. Complete OAuth/auth from the correct tool context.
4. Test with a read-only Drive query.
## Candidate Gemini CLI / WSL settings path
```bash
~/.gemini/settings.json
```

If the file does not exist, create it.

## Official Gemini CLI remote MCP server config

Source: Google Workspace Drive MCP server documentation, last checked 2026-04-24.

```json
{
  "mcpServers": {
    "drive": {
      "httpUrl": "https://drivemcp.googleapis.com/mcp/v1",
      "oauth": {
        "enabled": true,
        "clientId": "OAUTH_CLIENT_ID",
        "clientSecret": "OAUTH_CLIENT_SECRET",
        "scopes": [
          "https://www.googleapis.com/auth/drive.readonly",
          "https://www.googleapis.com/auth/drive.file"
        ]
      }
    }
  }
}
```

Replace `OAUTH_CLIENT_ID` and `OAUTH_CLIENT_SECRET` with the OAuth desktop client values created for the target Google Cloud project. Do not commit those values to the repo.

## Rejected stale npm package config

The earlier candidate config below is rejected/stale. It was tested on 2026-04-24 and returned `npm E404 Not Found`:

```bash
npx -y @google-gemini/mcp-server-office drive
```

Do not use this stale config unless a future official source reintroduces it:

```json
{
  "mcpServers": {
    "google-drive": {
      "command": "npx",
      "args": ["-y", "@google-gemini/mcp-server-office", "drive"],
      "env": {
        "GOOGLE_WORKSPACE_CLI_CREDENTIALS_FILE": "/home/openclaw/.config/gws/client_secret.json"
      }
    }
  }
}
```

## 2026-04-24 verification result

Verified status from the Gemini CLI / WSL Drive MCP setup attempt:

* The stale npm package path was rejected: `npx -y @google-gemini/mcp-server-office drive` returned `npm E404`.
* The official remote MCP endpoint used was `https://drivemcp.googleapis.com/mcp/v1`.
* Gemini CLI recognized the `drive` MCP server.
* `/mcp` showed: `drive - Ready (7 tools) (OAuth)`.
* OAuth authentication succeeded after using the correct Desktop app OAuth client and adding scopes.
* Configured scopes:
  * `https://www.googleapis.com/auth/drive.readonly`
  * `https://www.googleapis.com/auth/drive.file`
* Drive API was enabled.
* Drive MCP API was enabled.
* A test user was added in Google Auth Platform.
* Actual Drive tool calls still failed with `caller does not have permission`.
* Google Cloud metrics showed `DriveMcpService.ListFiles` returning 100% `403`.

Conclusion: the local Gemini/MCP setup appears mostly correct. The remaining blocker is likely Google-side Drive MCP permission, preview entitlement, or project/account access behavior.

Recommendation: do not keep retrying local setup blindly. Pause and revisit through Google documentation, Google support, or an alternate project/account later.

## Credential and secret warning

The official remote MCP config embeds OAuth client ID and client secret placeholders in `~/.gemini/settings.json`. That file is local user configuration, not repo documentation or source.

Do not commit credentials, OAuth client secrets, `client_secret` files, `google_creds` files, tokens, or local Gemini settings to the repo.

## Candidate authentication step

```text
/mcp auth drive
```

For Gemini CLI, this may need to be typed inside the Gemini CLI chat instead of run as a normal shell command.

Expected behavior: a browser/OAuth flow opens and asks for Google Drive scopes.

Google's current doc also says `/mcp list` should show the `drive` server ready after successful authentication.

## Candidate read-only test prompt

List the names of the last 3 files I modified in my Google Drive.

Passing this test means the model environment can reach Drive through the MCP bridge.

It does not mean the bridge should automatically be granted to Hermes, Codex, Claude Code, or autonomous local loops.

## Conceptual model

* OAuth client ID and secret = local client identity for the MCP client.
* Remote MCP server URL = Google-hosted Drive MCP endpoint.
* Drive API = the Google Cloud capability being accessed.
* Agent/tool MCP config = the contract telling the model environment how to invoke the Drive bridge.

## Verification checklist

Before treating this as real system capability:

1. Verify the exact OAuth client type, client ID, and client secret handling for the target machine.
2. Verify the exact MCP server URL and required scopes against current official docs.
3. Add the MCP config only to the local user settings file, not to a tracked repo file.
4. Run the auth step from the correct tool context.
5. Test with a read-only Drive query.
6. Record the confirmed command/config in a canonical OpenClaw note only after it works.

## Open questions

* Does Codex consume ~/.gemini/settings.json, or does Codex require its own MCP config surface?
* Does Claude Code need a separate MCP registration path?
* Should this Drive bridge be available to Hermes, Gemini, Codex, Claude Code, local models, or only a narrow subset?
* Should the first version be read-only?
* Should the `drive.file` scope be included for initial OpenClaw use, or should the first trial attempt read-only scope only if supported?

## Recommended policy judgment

Start with Gemini CLI only, read-first, and verify live.

Do not automatically wire this into Hermes, Codex, Claude Code, or local autonomous loops until Gemini’s setup is confirmed and the credential/scope behavior is understood.

Treat Drive as an external data capability, not canonical OpenClaw authority.
