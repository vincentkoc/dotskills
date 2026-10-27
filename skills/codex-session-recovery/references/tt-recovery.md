# tt cockpit recovery

Read this for snapshot restoration, including a user-authorized full close and
re-restore. Process identity alone does not prove a successful cockpit restore.

## Guidance beside the snapshots

Read `${XDG_STATE_HOME:-$HOME/.local/state}/tt/AGENTS.md` before using the saved
state. Its maintained source is
`dotfiles/.local/state/tt/AGENTS.md` in the owning dotfiles checkout. The dotfiles
installer's `setup_tt_recovery_guidance` function installs this file alone; the
Mackup tmux profile includes the same relative path for the default state root;
custom `XDG_STATE_HOME` locations need their own backup mapping. On a missing installation,
read that source and invoke only the scoped installation function, or copy the
reviewed file to the state root. Do not bootstrap the machine or sync the whole
state directory. Confirm the installed file matches the source.

Keep recovery mechanics tied to the installed `tt` revision. Read its native
`recovery_server_config`, `agent_color_prefix`, `agent_pane_command`, marker
functions and recovery setup before replacing native behavior with a custom
route. Do not source the `tt` executable as a function library.

## Plan the exact restore

- Inspect `tt status`, `tt snapshot-history codex-cockpit` and a preview of the
  explicit selected snapshot. Freeze its hash, exact UUID/CWD/title mapping,
  shell targets, window counts and persisted marker records. Snapshots may lack
  layout or marker columns; use the native layout and persisted marker files
  rather than assuming these features do not exist.
- Check for live owners and outside controllers. Existing authorization for a
  full close and re-restore covers the named cockpit; do not substitute another
  one-pane repair or ask again for unchanged scope. It does not cover unrelated
  sessions or processes.
- Match native preview to the saved topology. Some `tt recover` versions pad
  windows to six panes or change saved launch options.
  When a reviewed exact route is needed, retain the native theme, marker and
  agent-command contracts rather than reproducing only panes and UUIDs.
- Six-pane studio windows have **three columns and two rows**, ordered down
  each column: 1/2 left, 3/4 center, 5/6 right. Preserve partial windows and the
  attached client's logical focus; do not pad or apply a generic tiled layout.
  If no historical geometry survives, keep exact counts and use a 2×2 grid for
  four panes and a vertical pair for two. Report this as a fallback, not recovered
  historical geometry.

## Prepare before launching agents

1. With an existing server, disable native autosave before changing topology.
   For a cold start, bootstrap only a shell with the native recovery config's
   hooks/autosave absent, then disable native autosave before scaffold changes
   or setup helpers. Do not require `tt autosave off` to succeed before a server
   exists. Keep autosave off until the complete restored state is verified, so
   scaffolding cannot replace a useful snapshot. Do not back up degraded state
   by habit.
2. For an explicitly authorized full rebuild, preserve the attached client in
   an absent, task-owned holding session if needed. Close only the audited
   cockpit and verify its exact old UUID processes have exited before resuming
   them. Never kill a server or unrelated processes by name.
3. Build the exact shell scaffold. Apply native terminal/RGB configuration,
   explicit foreground/background defaults, saved titles and pane marker
   styles **before the first Codex launch**, including unmarked panes. Verify
   that these settings took effect before continuing.
4. Feed `tt recovery-config` to an existing server with `tmux source-file -`.
   Do not rely on `tmux -f /dev/stdin new-session`: the detached server can start
   with default indices and no color configuration. If a fresh server requires
   a real configuration file, use one temporary file and verify the loaded
   options before starting agents. A failed bootstrap is a stop condition,
   not permission to launch agents and apply their palette later.
5. Launch every exact saved UUID through the native `agent_pane_command`
   contract, retaining original options, `--no-alt-screen` and
   the login-shell fallback. The current color prefix unsets `NO_COLOR` and
   `TERMINFO`, sets `CLICOLOR=1`, `CLICOLOR_FORCE=1`, `FORCE_COLOR=3` and
   `COLORTERM=truecolor`, and supplies native `TERMINFO_DIRS`. Global tmux
   environment changes alone do not remove an inherited session override.

Codex probes its foreground/background during startup and can cache a failed
probe. Applying `tt colorfix` or attaching a terminal afterward does not repair
that process's cached input shading. A native environment prefix alone also
does not replace the pre-launch palette. Both must be in place first.

## Preserve goals through recovery

- Preserve the thread's original goals feature configuration. Never add
  `--disable goals` or `features.goals=false` as a recovery precaution. A flag
  introduced by a faulty restore is not an original user preference; remove it
  from the corrected launch plan. Preserve an intentional user override.
- Goals are persisted thread state. Before replacing an owner, inspect its
  native goal state read-only when available. Preserve the goal ID, objective,
  lifecycle, token/time budgets and consumed usage. Missing state is unknown,
  not permission to recreate an objective or reset a budget.
- Preserve native continuation for active goals. Leave paused, blocked,
  complete, cancelled and budget-limited goals in their saved states. Do not
  send blanket `/goal resume`, pause or clear commands, mutate goal databases,
  or synthesize new goals. Follow any explicit user-requested lifecycle change
  separately from restoring the cockpit.
- Interrupting a turn can pause a goal. Do not interrupt a busy owner just to
  fix launch flags. If the current CLI cannot enable goals in place, report the
  affected exact owners and obtain current scoped restart authority before
  replacing them. A previously completed restore does not authorize another
  restart cycle. Preserve existing safety notices; recovery must not retry a
  request stopped by one.

## Verify and finish

- Match every restored target to its UUID, CWD, title and live process. Inspect
  actual pane coordinates for three columns and two rows, and native active and
  inactive marker styles against persisted records.
- Restore native automatic window sizing after any temporary scaffold
  `resize-window` calls: they create a local `window-size manual` override even
  when the global setting is `latest`. Remove only task-created overrides with
  `set-window-option -u -t <window-id> window-size`; preserve intentional prior
  settings. Check every window's effective policy and client dimensions, not
  only the global option. Do not leave the cockpit locked to scaffold sizes.
- Verify selected color variables without dumping full process environments.
  Check actual colored output and input-background shading in each restored
  Codex UI; a correct `TERM`, live PID or ANSI bold/dim sequences are insufficient.
- Inspect prompts in context. A directory-choice dialog can contain an input
  glyph without opening the conversation. If it offers the saved session's old
  directory versus the audited snapshot CWD, choose the snapshot CWD only when
  that exact choice is covered by the restore map. Do not send new task text or
  change goal lifecycle; allow the restored thread's normal native continuation.
- Verify goal capability, unchanged budgets and no reset or recovery-induced
  lifecycle change after launch. Native progress can increase usage, complete
  the goal or reach its budget. A live process with the right UUID is
  insufficient when a recovery-added override prevents loading its goal.
- Return the client to its mapped pane, remove only the task-owned holding
  session, and restore native menus/autosave. Preserve the immutable source
  snapshot and outside processes. A full recreation must prove the old Codex
  owners exited and all replacement processes started with native colors.
- Stop once the requested restore is verified or the user confirms it works.
  Do not audit newly active tasks or reopen settled scope after that confirmation.
