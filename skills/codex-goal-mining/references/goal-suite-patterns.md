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
