# OpenClaw Lane Matrix

Use this reference for OpenClaw or adjacent maintainer work. The latest operator assignment owns the mission map. Do not reuse a captured historical pane assignment.

## Manager scope

- `ops.1` manages `L1`, `ops.3` manages `L2`, and `ops.5` manages `L3`.
- Even `ops` panes are spare shells unless the operator assigns them.
- Default work classes are fixes/maintainer hygiene (`L1`), features (`L2`), and exploration (`L3`). The operator can override them.
- Preserve conflicting or duplicated assignments and report them. Do not rewrite ownership silently.

## Repository authority

Resolve the actual target repository's native checkout owner before new work. In OpenClaw, use `gwt owner` and read that owner's current maintainer instructions and relevant repository skills. Freeze that instruction revision for the task. Preserve existing workers and their execution routes.

The repository owns worktree and dependency qualification, source trust, test/build/CI selection, capacity handling, provider choice, review, publication, and landing. Follow its testing, remote-proof, and PR skills instead of maintaining parallel policy here. Read its current release workflow when release work is explicitly in scope.

Lane management does not grant approval/sandbox bypass, directory trust, hook bypass, provider replacement, direct `main` push, or mandatory rebase authority. Perform any such action only when the target owner's workflow and the operator's scope authorize it. Queue or capacity failure does not expand authority.

## Coordination and evidence

- Preserve active and paused workers, their boxes, runs, reservations, and unknown identities. Do not interrupt, resume, reset, or replace them based on a title, timestamp, silence, or missing metadata.
- Name one final integration owner when work overlaps. Other workers report their exact branch HEAD, in-flight proof, and blockers. Do not create competing landing loops.
- Track job/PR URL, assigned pane, checkout, exact SHA, run or resource ID, state, and next action. Reassign only after checking live metadata and ownership.
- Reuse applicable in-flight proof. A changed HEAD requires the target owner's exact-head proof. Do not launch duplicate broad checks or treat an old run as current.
- Classify findings before assigning fixes: product defects, harness/environment drift, and unconfirmed observations need different next actions. A slow run or retry alone does not prove a product bug.
- Use current analysis SHA/ref/category when assigning static-analysis work. An old alert count does not establish a current defect or authorize dismissal.
- Docs work needs a code-to-doc impact link. A verified no-op is a valid outcome.
- Keep review workers read-only until implementation is authorized. Resolve current review feedback and closure obligations through the repository's PR workflow.
- Deliver an authorized update to each named worker and verify receipt. Preserve any applied pause or stop. Message delivery does not authorize starting or resuming work.

## Summary priorities

Report overlapping ownership or duplicate proof first, then exact blockers, current progress, and verified available capacity. Name the next action and its owner. Unknown identity or state stays unknown.
