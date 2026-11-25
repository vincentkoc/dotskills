# Build qualification

This recipe covers Linux ELF artifacts. Other operating systems need their own
binary compatibility checks and consumer qualification before promotion.

## Source, daily builds and fork history

Treat an upstream-sync PR, a published artifact and a promoted service as three
different owners. A daily sync workflow may only open a PR; a successful no-op
run does not exercise its push/token path. Verify workflow permissions and the
actual published artifact before describing a daily version as installable.

For history-preserving sync, merge the selected upstream commit into the fork
through a normal merge commit. Verify both prior fork and selected upstream tips
with `git merge-base --is-ancestor`, inspect parents and any missing commits, and
retain signed commit objects. Do not squash or use GitHub rebase merge when the
operator requested preserving the series. A surprising PR diff is not evidence
that ancestry was discarded; inspect the merged graph before reverting anything.

Do not run `bun upgrade --canary` to maintain an OpenClaw fork. At the qualified
[Bun revision](https://github.com/openclaw/bun/blob/699ba4ddd138994fb258de53669d481cdcf1016d/src/runtime/cli/upgrade_command.rs),
the upgrade command selects oven-sh artifacts. Recheck this contract if it changes;
an upstream canary version label does not identify a fork build.

## Reproducible selection

Freeze the full commit and tree, then record:

- Release profile, OS/architecture/libc, CPU baseline and LTO configuration.
- Native sysroot identity/digest and compiler, linker, Rust, bootstrap Bun and
  WebKit inputs selected by that revision's build configuration.
- Artifact byte count, SHA-256 and `bun --revision`; archive hash separately.
- Actual ELF interpreter, required GLIBC/GLIBCXX/CXXABI versions and CPU features.
- Test commands, exit results, skipped cases and limitations.

Keep checkout commit/tree, the executable's embedded revision and digest, engine
inputs, CI head/attempt and deployed executable identity separate. A rebuilt
harness or changed checkout does not prove the executable was rebuilt; a passed
CI head does not identify the runtime loaded by a service.

Before credentialed CI, remove raw environment enumeration from shared build/test
logging producers. Log masking or redacting the final report does not prevent the
original producer from exposing credentials in retained output.

Rustup commands and proxies can install a selected missing toolchain while
resolving a project override. Inspect static configuration first; use
`RUSTUP_AUTO_INSTALL=0` per diagnostic invocation to disable automatic installation.
This does not disable explicit install/repair commands or authorize toolchain
changes. See the
[rustup environment contract](https://rust-lang.github.io/rustup/devel/environment-variables.html).

Qualify source-glob inventories against the frozen Git tree, not only literal
`git ls-files` paths. Follow symlinks only when every traversed link is tracked and
its target text matches the frozen tree. Require the resolved source file to remain
inside the qualified checkout, be tracked, and match its frozen content. Reject
untracked aliases and ignored or untracked source inputs. Account separately for
generated and dependency inputs through their declared build steps.

Use the repository's build wrapper and inspect its generated flags. Merely
setting a sysroot variable or naming an artifact `baseline` does not prove the
compiler/linker consumed it. For heterogeneous x64 hosts, select a baseline no
newer than the least capable target; a build host's glibc is not the artifact's
minimum glibc. Inspect `readelf` output and execute the staged candidate as the
target service account.

Prefer the existing isolated build service and its native lease lifecycle.
Separate trusted reviewed-source execution from secretless fork execution.
Before expensive work, budget artifact/proof transfer, verification and cleanup
against lease expiry, including measured throughput and artifact size.
Release the builder after the artifact and required proof have been retrieved;
do not retain a paid builder merely because deployment is waiting for admission.
Transfer one verified artifact, without credentials or private fleet checkouts.
If resuming a partial transfer, bind and verify the prefix and final digest.
A relay uses verified host keys and no agent forwarding; it also needs release
from any thread that owns the relay host.

Bind the artifact URL, actual compression format, byte count and digest to the
same selected asset before extraction. Verify archive and extracted binary hashes
separately; a filename suffix or reused URL is not proof of archive format.

## Consumer proof

Choose tests from the actual changed surfaces and retain the original regression
cases for fork fixes still carried by the candidate. Inspect the daily workflow's
commands, file/name filters, skips and result counts: a green job proves only the
selected tests ran. Parser, directory and worker fixes need their corresponding
regressions and real consumers; an omitted large-input or stress case remains a
qualification gap, even when the surrounding suite passed.

Report released/reference and patched runs separately: selected, passed, failed,
skipped and expected-failure counts, with identical filters and execution order
for differential proof. An expected failure is not a repaired pass. Exit zero
with required tests or Rust cross-check targets skipped is incomplete; enumerate
which targets actually compiled and which remain unqualified.

Preserve a GC regression's original factory, creation/execution order, assertions,
collection budget and collection context. Moving collection to another job or
stack depth changes the oracle. Attribute the actual retaining owner before a
fixture correction; a rootless heap graph alone does not prove conservative-stack
retention. A scanner claim needs the retaining word and owning frame, not merely
a passing reordered test or a production counterfactual.

Read unexpected annotations together with the producing step's logs and exit
status. Distinguish expected test output, harness/build infrastructure failures
and candidate runtime failures. A passing job does not explain an error annotation,
and an annotation alone does not prove a Bun defect. Resolve relevant unexplained
diagnostics before treating that run as promotion proof.

For OpenClaw worker/CodeMode paths, record the exact Bun identity from inside the
real worker. Exercise allowed nested calls, policy denial, rightful wait/continuation
ownership, catalog revocation, in-flight abort with no late dispatch and healthy
reuse after cleanup. An isolated capsule proves those selected paths, not live
visitor authorization, channel delivery or all dynamically loaded plugins.

A capsule must include the selected frozen dependency graph, workspace links,
overrides, assets and dynamic closure. Packaging failures are not automatically
candidate runtime failures. Repair only the missing packaging input; do not replace
the actual implementation with mocks, silent fallbacks or broad imports. Keep
unselected dynamic paths visibly unavailable.

Carry earlier source/test proof only after comparing the relevant runtime, build,
dependency, test and consumer inputs. Documentation-only source changes can permit
carried debug/ASAN evidence, but a fresh release still needs its own artifact
identity and release execution. Preserve known baseline failures and upstream
references; do not suppress a leak or unrelated failure to claim a clean run.

## Published daily artifact contract

Before selecting a daily artifact, require immutable source identity, matching
artifact digest, successful relevant build/test attempts and target compatibility.
Pin the digest/full commit at selection; do not deploy a moving `latest` URL.
Build publication needs its own workflow and retention policy. Runtime promotion
still uses per-host admission and rollback. Do not enable source auto-merge,
artifact publication or unattended runtime upgrades as a side effect of this skill.
