# Goal Suite Patterns

Use stable tags so reruns can be compared across machines and dates:

```text
[suite:<name>] [baseline:<git-sha-or-date>] [matrix:<targets>] [exit:<definition-of-done>]
```

Recommended recurring families:

- `openclaw-qa-all-surfaces`: RPC, kitchen sink, onboarding, plugins, SDKs, QA Lab, and scripts.
- `openclaw-cross-platform`: macOS ARM64, Windows native, WSL2, Linux, and Docker.
- `local-model-code-mode`: Ollama, Hugging Face, constrained models, and a frontier control.
- `tool-schema-safety`: malformed schemas, dynamic tools, doctor, UI, and channel failure behavior.
- `sandbox-compatibility`: OpenShell, restricted filesystem/network, browser, packages, and subprocesses.
- `localization-all-surfaces`: Control UI, web, docs UI, iOS, Android, macOS, and watch.
- `dead-code-complexity`: core, apps, Control UI, plugins, and SDKs with no contract change.
- `contributor-pr-batch`: bounded low-risk PR queue work; keep separate from product beta suites.

Every rerun should record:

- exact baseline SHA or release;
- unchanged test matrix;
- product failures versus infrastructure blockers;
- before/after reliability or performance evidence;
- landed PRs and remaining issues;
- skipped surfaces and the next rerun trigger.

## Historical coverage and effectiveness

Define the requested machines, date window, goals, and outcome criteria before
analysis. Record the collector revision and source types used.

For historical claims, account for retained session and archived history within
the authorized scope, including replaced or cleared goals and resumed threads.
Verify the installed source schema and supported reader before interpreting
records. The current collector does not reconcile these sources; report historical
coverage as incomplete or unknown when no supported evidence route establishes it.
Do not invent a history flag or infer completeness from machine reachability.

Keep goal instances and root/child relationships distinct before grouping related
work into campaigns. Record uncertain identity and duplicate evidence rather than
guessing or double-counting.

For each campaign, report its requested outcome, recorded status, verified result,
evidence, remaining gap, and next owner action. Separate delivered results,
demonstrated failures, blockers, and unknown outcomes. Activity volume and repeated
attempts are investigation signals, not success measures.

Compare outcomes only across a stated, comparable coverage set. Do not publish
fleet-wide completion or efficiency claims when missing history, overlapping work,
or absent outcome evidence invalidates the denominator.
