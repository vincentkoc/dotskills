# OpenClaw runtime and search-auth troubleshooting

Use this checklist when an agent runtime change is saved but not active, or
when a provider-backed search tool is missing. Verify commands and config
fields against the installed OpenClaw documentation before applying changes.

## Preserve the intended selection

1. Record the current full provider/model ID and effective runtime.
2. Inspect the per-agent model configuration and session selection separately.
3. To change only execution runtime, preserve the model and other agents. Use
   supported session controls rather than editing session databases.
4. A saved default, a selected session runtime, and an executing runtime are
   different states. If status says a live switch is pending, verify again on
   the next turn before reporting activation.

For the built-in runtime, the model entry uses
`"agentRuntime": { "id": "openclaw" }`. Merge configuration; do not replace
whole agent/model maps.

## Separate exposure, authentication, and activation

For xAI search used with a different model provider, inspect the explicit
`plugins.entries.xai.config.xSearch.enabled` opt-in. Enabling it does not
guarantee that a credential resolves or that the current turn exposes the tool.

Inspect managed authentication without printing keys, tokens, cookies, full
auth-store contents, or environment dumps. The absence of a plugin API-key
field is not conclusive: a managed OAuth profile may supply authentication.
An expired access-token status requires a refresh/probe result, not an
assumption that the account must be deleted or recreated.

A bounded diagnostic, when supported by the installed CLI, is:

```sh
openclaw models --agent AGENT status --json \
  --probe --probe-provider xai --probe-timeout 15000 --probe-max-tokens 8
```

Keep diagnostic output local and report only redacted status/error fields.
Apply an outer process timeout too. Preserve the CLI exit status when filtering
JSON; an empty filtered object, parser success, or a timeout is not a successful
authentication probe. Do not activate an auth profile if that action also
changes the model the user asked to preserve.

## Respect recovery boundaries

- A reload rejected with `FORBIDDEN` / missing `operator.admin` is an access
  denial, not a transient error. Do not retry through root SSH, another token,
  raw backend access, or service restarts to evade it. Use an authorized
  operator connection and the supported control path.
- If system controls say the inference route cannot be reverified during a
  turn, use a fresh conversation for verification. Do not loop the same call.
- Follow the host deployment owner for Gateway updates and restarts. Do not
  substitute a shell service restart for a blocked plugin reload.
- Refresh or provision credentials only through an authorized login/secret
  workflow; never commit credentials or private account inventories.

## Completion evidence

Report each item independently: saved config; effective session/runtime; auth
probe result; plugin reload result; tool exposure; and one bounded real search.
If any item is blocked, name its exact dependency and do not call the complete
feature fixed. Public documentation should contain reusable procedure, not
private session IDs, host addresses, account details, or credentials.
