# Task Checkpoints And Artifacts

Use the task's existing state or result channel. Do not add a supervisor,
telemetry daemon, or persistent receipt tree merely to say that nothing was
retained.

## Default

- Return ordinary audit and discovery results through stdout, stderr, structured
  JSON, or an existing required task-state store.
- Use run-owned temporary scratch only when the tool needs files to execute.
- Create no persistent artifact root unless retention is required or explicitly
  selected.
- Preserve the original owner, failure, exit status, and user-owned paths when
  checkpoint or artifact delivery fails.

## Declared Retention

Before expensive work, declare:

- artifact root and owner;
- source and input identity;
- output kind and required or optional status;
- maximum retained files and bytes;
- retention or pin intent;
- approved publication destination, when one exists.

Keep temporary scratch separate from retained evidence. Refuse the optional
stage before work when its declared budget or destination is invalid. Report
`artifact-budget-exceeded` without hiding the original failure.

Store a small checkpoint in the existing task-state route when continuation
needs it. The checkpoint should contain the task owner, source/input identity,
acceptance criteria, completed phases, last material artifact, external
blocker, failure fingerprint, retry allowance, and the event that permits a
retry. An unchanged blocker must not create another root, worktree, lease, or
download.

## Reuse And Ordering

- Reuse immutable large inputs, inventories, and completed evidence only when
  their source/input identity still matches.
- Keep one canonical large output and use compatible references or derived
  views. Do not duplicate bytes or share mutable hard links across runs.
- Publish required release, security, hardware, or canonical worker evidence
  before optional profiling, long handover, or lease expiry.
- Verify checksum and retrieval from the already approved destination before
  treating publication as complete.
- If required publication fails, preserve the expensive local result and block
  only the optional follow-on phase.

For OpenClaw, its current repository instructions and native lifecycle state
remain authoritative. This contract is an adoption pointer, not a replacement
for exact-head, release, security, or owner checks.
