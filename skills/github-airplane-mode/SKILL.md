---
name: github-airplane-mode
description: Inspect or switch the local Git and GitHub download guard using an already-installed compatible low-data command. Use for airplane mode, flight or metered connections, returning online, or requests to enable, disable, or automatically select low-data protection on this machine.
license: MIT
metadata:
  source: "https://github.com/vincentkoc/dotskills"
---

# GitHub Airplane Mode

## Purpose

Switch an already-installed local Git and GitHub download guard.

Keep the guard installed and active sessions intact. This skill does not bundle
or install `low-data`, Git/GitHub wrappers, or a native connection-cost detector.

## When to use

- Enable protection before a flight or on a metered connection.
- Disable protection after returning online.
- Inspect the current policy or use automatic connection-cost detection.

## Workflow

### Verify the prerequisite

Operate only on the current machine. Require an already-installed compatible
`low-data` command before running any recipe.

1. Resolve `command -v low-data` and inspect its file or symlink target. Verify
   its trusted local source and the mode, status, and exit semantics below.
   Stop if it is missing, shadowed, unfamiliar, or incompatible; report the
   prerequisite instead of downloading or replacing it.
2. Inspect the current state with `env -u LOW_DATA_ALLOW_NETWORK low-data status`.
3. Apply only the requested mode. Interpret "I'm back", "return online", or
   "remove airplane mode" as `off`, not removal of the reusable guard.

### Switch modes

```sh
# Inspect without a per-command override masking the saved policy.
env -u LOW_DATA_ALLOW_NETWORK low-data status

# Force protection for a flight or metered connection.
env -u LOW_DATA_ALLOW_NETWORK low-data on

# Explicitly disable protection after returning online.
env -u LOW_DATA_ALLOW_NETWORK low-data off

# Follow the native connection-cost detector.
env -u LOW_DATA_ALLOW_NETWORK low-data auto
```

Require these semantics: `on` forces protection; `off` explicitly disables it;
`auto` protects constrained or expensive connections and fails closed when
native status is unavailable. An unmetered connection is unprotected in `auto`.

### Verify the result

After any change, run both checks with the override unset:

```sh
env -u LOW_DATA_ALLOW_NETWORK low-data status
if env -u LOW_DATA_ALLOW_NETWORK low-data active; then
  printf 'active_exit=0 (protected)\n'
else
  active_exit=$?
  printf 'active_exit=%s\n' "$active_exit"
fi
```

Require `active` exit 0 for `on` and exit 1 for `off`. For `auto`, report the
detected reason and the matching active state. Treat any other exit as a failed
check. Do not claim success from the mode-setting command alone.

### Keep changes bounded

- Preserve the switch, guards, native detector, and unrelated settings. Use the
  command to change mode; do not delete the implementation or edit shell startup
  files to turn it off.
- Limit protection claims to guarded Git history and bulk GitHub repository,
  release, and artifact downloads. Normal commits, pushes, metadata/API
  requests, curl, package installs, and model traffic remain allowed.
- Do not claim whole-machine airplane mode, a firewall, or a bandwidth cap.
  PATH wrappers are not a network boundary. Never bypass them through absolute
  Git or GitHub CLI binaries, aliases, or custom hooks.
- Allow `LOW_DATA_ALLOW_NETWORK=1 command ...` only for one explicitly approved
  command. Never export that override globally.
- Do not pause, resume, kill, or relaunch agent, tmux, terminal, or background
  sessions. A mode change is not process-control authority.
- Do not change other hosts, credentials, GitHub authentication, proxy settings,
  or remote repositories.

## Inputs

- Requested local operation: `status`, `on`, `off`, or `auto`.
- Already-installed compatible `low-data` command and its trusted source.

## Outputs

- Saved mode, effective protected/unprotected state, and detected reason.
- Post-change `status` and `active` exit-code proof.
- Exact missing prerequisite or failed verification when the operation cannot
  complete.
