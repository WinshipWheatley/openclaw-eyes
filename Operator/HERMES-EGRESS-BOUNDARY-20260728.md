# Hermes egress: the exact boundary, and why I did not cross it

**Date:** 2026-07-28 · **Author:** Opus-PC · **Trace:** read-only

Five OpenClaw listeners now share one reply egress. Hermes does not, and cannot be
wired the way the others were. This records exactly why, so nobody re-discovers it.

## What Hermes actually is

```
sidecars/hermes           →  a SEPARATE git repository
  origin                     https://github.com/NousResearch/hermes-agent.git
  HEAD                       e82784f7 fix(gateway): serialize timed-out executor drains
```

It is third-party, vendored. `git ls-files sidecars/` in the OpenClaw repo returns
**two files**, both documentation under `sidecars/hermes_home/`. No Hermes source is
in the OpenClaw tracked worktree, so there is nothing here I could have committed.

The gateway runs from its own virtualenv as pid 1403 and talks to Telegram directly.
Its replies never pass through any OpenClaw funnel, which is precisely why the shared
egress does not reach them.

## Why I did not patch it anyway

Editing vendored upstream source creates a silent fork of
`NousResearch/hermes-agent`. Every upstream pull then either clobbers the guard or
conflicts, and the failure mode is the worst kind: the interlock appears present in
the tree and is absent at runtime. That is the same shape as a brake reporting
`activating` while crash-looping, and we have paid for that lesson twice this month.

## The extension point that exists — and does not fit

Hermes has a real plugin system: `hermes_cli/plugins.py`, `PluginContext.register_hook`,
entry-point group `hermes_agent.plugins`. Its complete hook list is:

```
pre_tool_call        post_tool_call        transform_terminal_output
transform_tool_result  pre_llm_call        post_llm_call
pre_api_request      post_api_request      on_session_start
on_session_end       on_session_finalize   on_session_reset
subagent_stop
```

**None of these is an outbound-message hook.** `transform_terminal_output` shapes
terminal output, not a platform send. `post_llm_call` fires on the model's response,
which is upstream of the Telegram send and would miss anything the gateway composes
or appends afterwards. Wiring the interlock there would produce a guard that looks
installed and does not cover the actual egress.

I am not inventing a `transform_outbound_message` hook that does not exist.

## Smallest honest owner action

Ordered by cost. Nothing here is urgent: **the nonce interlock is not bypassed by
this gap**, because approval previews are built on the OpenClaw side and every path
that composes one already passes through the shared egress. What Hermes-originated
replies currently lack is the banner, the citation suffix and the dominance check.

1. **Do nothing, and scope Hermes out of the identity battery.** Defensible today:
   Hermes returned a safe honest failure in the 2026-07-28 battery, and it is a
   gateway rather than an answering agent. Cost: zero. Record it as a known gap.
2. **Upstream a `transform_outbound_message` hook** to `NousResearch/hermes-agent`.
   Correct and permanent, keeps us on upstream, and other users get it. Cost: one
   small PR plus review latency. **This is my recommendation.**
3. **A thin OpenClaw-owned plugin** on the existing entry-point group that wraps the
   Telegram platform sender at import time. Works without upstream, but monkey-patching
   a third-party sender is fragile in exactly the way option 1 avoids.
4. **Fork and patch.** Named only to be rejected. It produces a guard that is present
   in the tree and absent after the next pull.

Any of 2 or 3 is the operator's call and touches a running sidecar, so it is not an
agent's to make.

## What is true right now

- Hermes replies carry no identity banner, no citation suffix, no dominance check.
- Every OpenClaw-composed reply, including any approval preview, does carry all four.
- No secret was read; the bot token was never opened. Only public plugin source and
  git remotes were inspected.

*Read-only. No deploy, restart, send, or gate change.*
