# Native promotion

## Resolve the installed contract

Read the deployed OpenClaw revision's installer, runtime-pin persistence,
operation-lock, admission and shutdown paths before choosing commands. Match
dependency versions when relying on lock or IPC behavior; an unrelated local
`node_modules` version is not evidence for the service's dependency contract.

Where supported by that owner, the native installer accepts:

```sh
openclaw gateway install --runtime bun --runtime-path /opt/openclaw-bun/<commit>/bun --force --json
```

This is a command shape, not an admission bypass. Use the existing maintenance
launcher and service account. Inspect whether installation restarts the service,
persists a pin and rewrites an overriding drop-in. Do not invoke it on a busy live
Gateway just because candidate validation passed. Keep an existing reviewed
selector owner unless an ownership migration is part of the requested scope.

Record the canonical home, user-manager environment, actual account IDs, service
unit and every effective drop-in. Start account-switched commands in a traversable
service-owned cwd. Run Git as the checkout owner; do not add a global
`safe.directory` exception after a root probe fails.

## Preserve a real Node runtime

A Bun Gateway can still need a genuine Node executable for PTY or other native
subprocesses. Inspect the deployed Node resolver and child environment. A Bun
directory on service PATH does not imply the prior Node directory remains there.
Keep the existing pinned Node available by the owner's supported PATH or an
explicitly reviewed link in the versioned runtime prefix. Verify resolution and
actual PTY behavior as the service account. Never disguise Bun as `node`.

## Atomic publication and authority

Stage an immutable versioned executable outside application state, then verify
its hash, mode, owner and ancestor traversal under the actual service UID. Bind
the previous selector and unit preimage before mutation. Atomic rename requires
write/search authority on the **immediate destination directory**; writable file
bytes or a writable grandparent do not prove it.

Prefer the existing privileged owner. If its selector needs an administrator
write, keep that write fixed and bounded: trusted code outside service-writable
custody, exact target and candidate, identity/preimage checks, exclusive same-directory
temporary file, expected owner/mode, fsync, one compare-and-swap rename, then readback.
Do not weaken directory permissions, add broad sudo or make in-place writes to
avoid the boundary. A task-specific publisher is not a new permanent updater.

The service-account lifecycle lock and live admission must cover privileged
publication too. A cached permit is insufficient: renew and recheck the same
token, process and work inventory immediately before publication. Treat the
publisher as a joined resource until its terminal receipt or proven retirement.
Keep required renewals alive while it is pending. A timeout must not release the
lock or reap the worker while a privileged child can still rename the selector.
Lost acknowledgement means observe/reconcile, never automatic publication replay.

## Admission, handoff and stopped boundaries

Use the native preserve policy by default. A task's logical `running` or `waiting`
label alone proves neither active execution nor restart safety. Inspect the
owner's authoritative generation, durable continuation and terminal persistence,
physical workers, queued launches, delivery state and write custody. Carry an
exception only for exact proven durable tasks supported by that native contract;
never create a general `waiting is safe` rule or cancel work to make admission green.

The audited revisions expose suspend and handoff operations. Verify their current
semantics rather than treating their historical timeout values as configuration:
capture process identity before admission closes, preserve the same owned token,
and measure lease validity with both wall and monotonic clocks. Renewing a
suspension does not necessarily renew an already armed handoff. Arm close to the
dispatch boundary and prove shutdown occurred within the acknowledged budget.

Read the restart-intent and handoff consumption paths together. At the qualified
revision, a CLI restart-intent writer suppressed the external-restart handoff;
the reviewed route used the native guarded service adapter. Do not replace it with
raw `systemctl`, edit database state or copy a private compiled helper into a new
version. Prefer a supported owner command; unsupported sequencing is a blocker
requiring a scoped reviewed plan, not permission to bypass native guards.

If installer/preflight duration can exceed the lease, finish expensive work first.
Where the owner supports it, admit and hand off one controlled stop, verify old
PID retirement and inactive service within the lease, then install at that
stopped boundary. Revalidate custody while stopped. Do not assume a lease survives
an unbounded installer or that an inactive unit has no remaining cgroup children.

## Failure visibility and verification

An IPC child can remain alive after `process.exitCode = 1` because message or
disconnect listeners keep its channel referenced. Await native unwind, emit a
bounded structured failure, then close only task-owned IPC/listeners. Supervisors
must preserve bounded stderr and root-publication failure reasons on every terminal
path. Do not discard diagnostics when a deadline fires or force `process.exit`
before lock cleanup. Reap only the task's freshly identified children.

On macOS, execute heredoc-heavy Bash producers with `/bin/bash` or the tool's
native compatibility guard. An outer `/bin/bash` does not change a nested
`#!/usr/bin/env bash` selection; verify the actual producer's interpreter too.
A local producer deadlock can happen before SSH starts.
Distinguish local preparation, SSH connection, remote execution and application
failure; inspect exact owned process lineage. Correct only the failed surface
when retry is still authorized. A released host or explicit no-retry instruction
ends the check; do not silently launch a replacement.

After native terminal success, independently check the live executable digest,
service identity, source/dist/config/schema, admission, durable continuations and
relevant runtime behavior. Health endpoints alone are not functional proof.
Classify new errors at their recorded owner before attributing them to Bun; a
task-projection stabilization failure is not itself a parser or worker-load error.
Do not claim timing effects are excluded without comparative evidence.

Rollback remains a new owner-guarded action: inspect what changed, current process
and state compatibility, then use the reviewed predecessor through the same
selector/installer owner. Do not restore a preimage merely because a receipt was
lost. Source/runtime changes invalidate another recovery plan's pinned assumptions;
return the deployed identities to that owner for requalification instead of
running its old helper.
