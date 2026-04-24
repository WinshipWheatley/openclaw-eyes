# Google Contract — Candidate MCP / Drive Integration Note
Status: candidate setup note / needs live verification  
Current location: OpenClaw docs candidate note  
Authority level: non-canonical until tested and intentionally promoted
## Purpose
This note captures a candidate contract for giving agentic coding/model tools access to Google Drive through MCP.
The immediate target is Gemini CLI in WSL. Codex, Claude Code, Hermes, and local model wrappers should not be assumed to share this setup until each tool’s MCP support and config path are verified.
## Current assumption
Google Drive API has been enabled, and a local Google credentials file exists or is expected to exist.
The remaining bridge is:
1. Tell the model/CLI environment where the Google Workspace MCP server is configured.
2. Point that server at the correct local credentials file.
3. Complete OAuth/auth from the correct tool context.
4. Test with a read-only Drive query.
## Candidate Gemini CLI / WSL settings path
```bash
~/.gemini/settings.json

If the file does not exist, create it.

Candidate MCP server config

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

Credential path warning

The candidate config above uses:

/home/openclaw/.config/gws/client_secret.json

If the actual credential file is named google_creds.json, update the config to the real path or intentionally copy/rename the file.

Do not leave multiple stale credential paths undocumented.

Do not commit credentials to the repo.

Candidate authentication step

/mcp auth drive

For Gemini CLI, this may need to be typed inside the Gemini CLI chat instead of run as a normal shell command.

Expected behavior: a browser/OAuth flow opens and asks for Google Drive scopes.

Candidate read-only test prompt

List the names of the last 3 files I modified in my Google Drive.

Passing this test means the model environment can reach Drive through the MCP bridge.

It does not mean the bridge should automatically be granted to Hermes, Codex, Claude Code, or autonomous local loops.

Conceptual model

* Credentials file = OAuth/client passport.
* MCP server = translator between the AI tool and Google Drive API calls.
* Drive API = the Google Cloud capability being accessed.
* Agent/tool MCP config = the contract telling the model environment how to invoke the Drive bridge.

Verification checklist

Before treating this as real system capability:

1. Verify the exact credential filename and path on the target machine.
2. Verify the exact MCP package name and arguments against current docs or a live dry run.
3. Add the MCP config only to the local user settings file, not to a tracked repo file.
4. Run the auth step from the correct tool context.
5. Test with a read-only Drive query.
6. Record the confirmed command/config in a canonical OpenClaw note only after it works.

Open questions

* Is @google-gemini/mcp-server-office the correct current MCP package?
* Does Codex consume ~/.gemini/settings.json, or does Codex require its own MCP config surface?
* Does Claude Code need a separate MCP registration path?
* Should this Drive bridge be available to Hermes, Gemini, Codex, Claude Code, local models, or only a narrow subset?
* Should the first version be read-only?

Recommended policy judgment

Start with Gemini CLI only, read-first, and verify live.

Do not automatically wire this into Hermes, Codex, Claude Code, or local autonomous loops until Gemini’s setup is confirmed and the credential/scope behavior is understood.

Treat Drive as an external data capability, not canonical OpenClaw authority.
