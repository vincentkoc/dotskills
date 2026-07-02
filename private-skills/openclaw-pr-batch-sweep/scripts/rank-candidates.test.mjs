#!/usr/bin/env node

import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const scriptPath = fileURLToPath(new URL("./rank-candidates.mjs", import.meta.url));

function hydratedPr(overrides = {}) {
  return {
    number: 12345,
    title: "fix: preserve retry scheduling",
    author: { login: "contributor" },
    author_association: "CONTRIBUTOR",
    state: "open",
    draft: false,
    changed_files: 2,
    mergeable: true,
    mergeable_state: "clean",
    files: [
      { filename: "src/retry.ts", additions: 15, deletions: 5 },
      { filename: "src/retry.test.ts", additions: 10, deletions: 0 },
    ],
    statusCheckRollup: [],
    ...overrides,
  };
}

function runHydrated(pr) {
  return runHydratedMany([pr], []);
}

function runHydratedArgs(pr, args) {
  return runHydratedMany([pr], args);
}

function runDiscovery(pr) {
  const result = spawnSync(process.execPath, [scriptPath], {
    input: JSON.stringify([pr]),
    encoding: "utf8",
  });

  assert.equal(result.status, 0, result.stderr);
  return JSON.parse(result.stdout);
}

function runDiscoveryInput(input) {
  const result = spawnSync(process.execPath, [scriptPath], {
    input: JSON.stringify(input),
    encoding: "utf8",
  });

  assert.equal(result.status, 0, result.stderr);
  return JSON.parse(result.stdout);
}

function runHydratedMany(prs, args) {
  const result = spawnSync(process.execPath, [scriptPath, "--hydrated", ...args], {
    input: JSON.stringify(prs),
    encoding: "utf8",
  });

  assert.equal(result.status, 0, result.stderr);
  return JSON.parse(result.stdout);
}

function checkRun(overrides) {
  return {
    workflowName: "CI",
    name: "test",
    ...overrides,
  };
}

test("rejects an unresolved REST merge state even when mergeable is true", () => {
  const output = runHydrated(hydratedPr({ mergeable_state: "unknown" }));

  assert.equal(output.selected.length, 0);
  assert.deepEqual(output.rejected[0].reasons, ["unresolved merge state"]);
});

test("rejects null REST mergeability even when the state string says clean", () => {
  const output = runHydrated(
    hydratedPr({
      mergeable: null,
      mergeable_state: "clean",
    }),
  );

  assert.equal(output.selected.length, 0);
  assert.deepEqual(output.rejected[0].reasons, ["unresolved merge state"]);
});

test("does not let a GraphQL clean state override null REST mergeability", () => {
  const pr = hydratedPr({
    mergeable: null,
    mergeStateStatus: "CLEAN",
  });
  delete pr.mergeable_state;
  const output = runHydrated(pr);

  assert.equal(output.selected.length, 0);
  assert.deepEqual(output.rejected[0].reasons, ["unresolved merge state"]);
});

test("rejects a one-line production patch even when tests are large", () => {
  const output = runHydrated(
    hydratedPr({
      files: [
        { filename: "src/retry.ts", additions: 1, deletions: 0 },
        { filename: "src/retry.test.ts", additions: 80, deletions: 0 },
      ],
      additions: 81,
      deletions: 0,
    }),
  );

  assert.equal(output.selected.length, 0);
  assert.deepEqual(output.rejected[0].reasons, ["trivial production diff"]);
});

test("rejects odd mechanical micro-fixes without linked lifecycle proof", () => {
  const output = runHydrated(
    hydratedPr({
      title: "fix: clear timeout timer after probe",
      labels: [{ name: "rating: diamond lobster" }, { name: "proof: sufficient" }],
    }),
  );

  assert.equal(output.selected.length, 0);
  assert.ok(output.rejected[0].reasons.includes("odd mechanical micro-fix"));
});

test("keeps a linked and strongly proven lifecycle micro-fix", () => {
  const pr = hydratedPr({
    number: 98720,
    title: "fix(nostr): clear per-relay publish timeout timer to prevent dangling handles",
    body: "Closes #98463. Fast success left a dangling timer handle and stale timer accumulation.",
    labels: [
      { name: "rating: diamond lobster" },
      { name: "proof: sufficient" },
      { name: "status: ready for maintainer look" },
    ],
    files: [
      { filename: "extensions/nostr/src/nostr-profile.ts", additions: 6, deletions: 1 },
      {
        filename: "extensions/nostr/src/nostr-profile.test.ts",
        additions: 73,
        deletions: 1,
      },
    ],
    changed_files: 2,
    additions: 79,
    deletions: 2,
  });
  const discovery = runDiscovery(pr);
  const output = runHydrated(pr);

  assert.equal(discovery.rejected.length, 0);
  assert.equal(discovery.selected.length, 1);
  assert.equal(
    discovery.selected[0].exceptionGate,
    "provisional lifecycle micro-fix; hydrate",
  );
  assert.equal(output.rejected.length, 0);
  assert.equal(output.selected.length, 1);
  assert.equal(output.selected[0].productionDelta, 7);
  assert.equal(output.selected[0].exceptionGate, "proven lifecycle micro-fix");
});

test("does not let strong labels excuse an untested lifecycle micro-fix", () => {
  const output = runHydrated(
    hydratedPr({
      title: "fix: clear timeout timer to prevent dangling handles",
      body: "Fixes #98463",
      labels: [
        { name: "rating: diamond lobster" },
        { name: "proof: sufficient" },
        { name: "status: ready for maintainer look" },
      ],
      files: [{ filename: "src/retry.ts", additions: 8, deletions: 2 }],
      changed_files: 1,
      additions: 8,
      deletions: 2,
    }),
  );

  assert.equal(output.selected.length, 0);
  assert.ok(output.rejected[0].reasons.includes("odd mechanical micro-fix"));
  assert.ok(output.rejected[0].reasons.includes("tiny single-file diff"));
});

test("keeps a focused non-trivial production and regression-test fix", () => {
  const output = runHydrated(
    hydratedPr({
      files: [
        { filename: "src/retry.ts", additions: 14, deletions: 4 },
        { filename: "src/retry.test.ts", additions: 24, deletions: 0 },
      ],
      additions: 38,
      deletions: 4,
    }),
  );

  assert.equal(output.rejected.length, 0);
  assert.equal(output.selected.length, 1);
  assert.equal(output.selected[0].productionDelta, 18);
  assert.equal(output.selected[0].productionFiles, 1);
});

test("does not treat a compatibility risk label as proof of a hard-risk surface", () => {
  const output = runHydrated(
    hydratedPr({
      title: "fix(memory-wiki): prevent distinct titles from overwriting each other",
      labels: [
        { name: "rating: diamond lobster" },
        { name: "merge-risk: compatibility" },
      ],
      files: [
        { filename: "extensions/memory-wiki/src/slug.ts", additions: 45, deletions: 14 },
        { filename: "extensions/memory-wiki/src/slug.test.ts", additions: 80, deletions: 0 },
      ],
    }),
  );

  assert.equal(output.rejected.length, 0);
  assert.equal(output.selected.length, 1);
});

test("does not confuse model token estimation with credential handling", () => {
  const output = runHydrated(
    hydratedPr({
      title: "fix(agents): use CJK-aware token estimation for tool results",
      files: [
        { filename: "src/agents/tool-result-overflow.ts", additions: 65, deletions: 20 },
        { filename: "src/agents/tool-result-overflow.test.ts", additions: 90, deletions: 0 },
      ],
    }),
  );

  assert.equal(output.rejected.length, 0);
  assert.equal(output.selected.length, 1);
});

test("normalizes CamelCase secret terminology before risk filtering", () => {
  const output = runHydrated(
    hydratedPr({
      title: "fix(gateway): resolve configured SecretRefs",
      files: [
        { filename: "src/gateway/configured-state.ts", additions: 45, deletions: 10 },
        { filename: "src/gateway/configured-state.test.ts", additions: 70, deletions: 0 },
      ],
    }),
  );

  assert.equal(output.selected.length, 0);
  assert.ok(output.rejected[0].reasons.includes("high-risk or compatibility surface"));
});

test("does not treat a wizard gateway-config filename as a config schema change", () => {
  const output = runHydrated(
    hydratedPr({
      number: 98689,
      title: "fix(wizard): reject invalid gateway config port input",
      body: "Fixes #98681",
      files: [
        {
          filename: "src/wizard/setup.gateway-config.ts",
          additions: 11,
          deletions: 11,
        },
        {
          filename: "src/wizard/setup.gateway-config.test.ts",
          additions: 16,
          deletions: 1,
        },
      ],
      changed_files: 2,
    }),
  );

  assert.equal(output.rejected.length, 0);
  assert.equal(output.selected.length, 1);
});

test("rejects explicit config schema changes by title", () => {
  const output = runHydrated(
    hydratedPr({
      title: "fix(config): migrate configuration schema defaults",
      files: [
        { filename: "src/runtime/settings.ts", additions: 15, deletions: 5 },
        { filename: "src/runtime/settings.test.ts", additions: 20, deletions: 0 },
      ],
    }),
  );

  assert.equal(output.selected.length, 0);
  assert.ok(
    output.rejected[0].reasons.includes("config schema/default/migration surface"),
  );
});

test("rejects config merge semantics by title", () => {
  const output = runHydrated(
    hydratedPr({
      title: "fix(config): preserve provider models during merge",
    }),
  );

  assert.equal(output.selected.length, 0);
  assert.ok(
    output.rejected[0].reasons.includes("config schema/default/migration surface"),
  );
});

test("rejects actual config schema and default surfaces", () => {
  const output = runHydrated(
    hydratedPr({
      files: [
        { filename: "src/config/schema.ts", additions: 15, deletions: 5 },
        { filename: "src/config/schema.test.ts", additions: 20, deletions: 0 },
      ],
    }),
  );

  assert.equal(output.selected.length, 0);
  assert.ok(
    output.rejected[0].reasons.includes("config schema/default/migration surface"),
  );
});

test("rejects plugin-local config schema surfaces", () => {
  const output = runHydrated(
    hydratedPr({
      files: [
        {
          filename: "extensions/example/src/config/schema.ts",
          additions: 15,
          deletions: 5,
        },
        {
          filename: "extensions/example/src/config/schema.test.ts",
          additions: 20,
          deletions: 0,
        },
      ],
    }),
  );

  assert.equal(output.selected.length, 0);
  assert.ok(
    output.rejected[0].reasons.includes("config schema/default/migration surface"),
  );
});

test("rejects plugin config.ts schema surfaces", () => {
  const output = runHydrated(
    hydratedPr({
      files: [
        {
          filename: "extensions/voice-call/src/config.ts",
          additions: 15,
          deletions: 5,
        },
        {
          filename: "extensions/voice-call/src/config.test.ts",
          additions: 20,
          deletions: 0,
        },
      ],
    }),
  );

  assert.equal(output.selected.length, 0);
  assert.ok(
    output.rejected[0].reasons.includes("config schema/default/migration surface"),
  );
});

test("rejects a hard-risk credential label even with a neutral title and path", () => {
  const output = runHydrated(
    hydratedPr({
      title: "fix(cli): report configured state consistently",
      labels: [{ name: "merge-risk: credentials" }],
    }),
  );

  assert.equal(output.selected.length, 0);
  assert.ok(output.rejected[0].reasons.includes("high-risk or compatibility surface"));
});

test("rejects an area-prefixed auth label even with a neutral title and path", () => {
  const output = runHydrated(
    hydratedPr({
      title: "fix(cli): report configured state consistently",
      labels: [{ name: "area: auth" }],
    }),
  );

  assert.equal(output.selected.length, 0);
  assert.ok(output.rejected[0].reasons.includes("high-risk or compatibility surface"));
});

test("rejects CamelCase API token handling without relying on the changed path", () => {
  const output = runHydrated(
    hydratedPr({
      title: "fix(cli): validate apiToken expiry",
    }),
  );

  assert.equal(output.selected.length, 0);
  assert.ok(output.rejected[0].reasons.includes("high-risk or compatibility surface"));
});

test("rejects feature-shaped public syntax changes disguised as fixes", () => {
  const output = runHydrated(
    hydratedPr({
      title: "fix(cron): Support HH:MM[:SS] syntax for --at",
      files: [
        { filename: "src/cron/parse-at.ts", additions: 45, deletions: 10 },
        { filename: "src/cron/parse-at.test.ts", additions: 70, deletions: 0 },
      ],
    }),
  );

  assert.equal(output.selected.length, 0);
  assert.ok(output.rejected[0].reasons.includes("feature-shaped fix"));
});

test("rejects terminal UI work", () => {
  const output = runHydrated(
    hydratedPr({
      title: "fix(tui): deduplicate assistant messages after reload",
      files: [
        { filename: "src/tui/session-view.ts", additions: 20, deletions: 5 },
        { filename: "src/tui/session-view.test.ts", additions: 30, deletions: 0 },
      ],
    }),
  );

  assert.equal(output.selected.length, 0);
  assert.ok(output.rejected[0].reasons.includes("UI or native-app surface"));
  assert.ok(output.rejected[0].reasons.includes("UI or native-app path"));
});

for (const title of [
  "fix(discord): bound gateway metadata response reads at 16 MiB",
  "fix(agents): enforce tool call payload byte limits",
  "fix(browser): prevent OOM from JSON response",
]) {
  test(`rejects response or payload limit hardening: ${title}`, () => {
    const output = runHydrated(
      hydratedPr({
        title,
      }),
    );

    assert.equal(output.selected.length, 0);
    assert.ok(
      output.rejected[0].reasons.includes(
        "resource-limit or response-boundary hardening",
      ),
    );
  });
}

test("rejects an unstable merge state", () => {
  const output = runHydrated(hydratedPr({ mergeable_state: "unstable" }));

  assert.equal(output.selected.length, 0);
  assert.deepEqual(output.rejected[0].reasons, ["unstable merge state"]);
});

test("keeps the strongest overlapping candidate and rejects the weaker one", () => {
  const shared = {
    body: "Fixes #98557",
    files: [
      { filename: "src/retry.ts", additions: 15, deletions: 5 },
      { filename: "src/retry.test.ts", additions: 10, deletions: 0 },
    ],
  };
  const output = runHydratedMany(
    [
      hydratedPr({
        ...shared,
        number: 98597,
        labels: [
          { name: "rating: diamond lobster" },
          { name: "proof: sufficient" },
          { name: "status: ready for maintainer look" },
        ],
      }),
      hydratedPr({
        ...shared,
        number: 98604,
        files: [{ filename: "src/retry.ts", additions: 15, deletions: 5 }],
        changed_files: 1,
      }),
    ],
    [],
  );

  assert.equal(output.selected.length, 1);
  assert.equal(output.selected[0].number, 98597);
  assert.equal(output.rejected.length, 1);
  assert.equal(output.rejected[0].number, 98604);
  assert.ok(output.rejected[0].reasons.includes("weaker overlapping candidate"));
});

test("requires adjudication when overlapping candidates have equal evidence", () => {
  const shared = {
    body: "Fixes #98557",
    files: [
      { filename: "src/retry.ts", additions: 15, deletions: 5 },
      { filename: "src/retry.test.ts", additions: 10, deletions: 0 },
    ],
  };
  const output = runHydratedMany(
    [
      hydratedPr({ ...shared, number: 98597 }),
      hydratedPr({ ...shared, number: 98604 }),
    ],
    [],
  );

  assert.equal(output.selected.length, 0);
  assert.equal(output.rejected.length, 2);
  for (const pr of output.rejected) {
    assert.ok(pr.reasons.includes("overlapping candidates need adjudication"));
  }
});

test("does not let a dirty high-rated duplicate suppress a clean candidate", () => {
  const shared = {
    body: "Fixes #98557",
    files: [
      { filename: "src/retry.ts", additions: 15, deletions: 5 },
      { filename: "src/retry.test.ts", additions: 10, deletions: 0 },
    ],
  };
  const output = runHydratedMany(
    [
      hydratedPr({
        ...shared,
        number: 98597,
        labels: [
          { name: "rating: diamond lobster" },
          { name: "proof: sufficient" },
          { name: "status: ready for maintainer look" },
        ],
        mergeable: false,
        mergeable_state: "dirty",
      }),
      hydratedPr({
        ...shared,
        number: 98604,
        labels: [{ name: "rating: platinum hermit" }],
      }),
    ],
    [],
  );

  assert.equal(output.selected.length, 1);
  assert.equal(output.selected[0].number, 98604);
  assert.equal(output.rejected.length, 1);
  assert.equal(output.rejected[0].number, 98597);
  assert.ok(output.rejected[0].reasons.includes("dirty or conflicting"));
  assert.ok(!output.rejected[0].reasons.includes("weaker overlapping candidate"));
});

test("rejects exact availability-risk labels from the low-risk batch", () => {
  const output = runHydrated(
    hydratedPr({
      title: "fix(cron): use job timeout for setup watchdog",
      labels: [
        { name: "rating: platinum hermit" },
        { name: "merge-risk: availability" },
      ],
    }),
  );

  assert.equal(output.selected.length, 0);
  assert.ok(output.rejected[0].reasons.includes("high-risk or compatibility surface"));
});

test("rejects unlabeled watchdog and timeout policy changes", () => {
  const output = runHydrated(
    hydratedPr({
      title: "fix(cron): use job timeout for setup watchdog",
      labels: [{ name: "rating: platinum hermit" }],
    }),
  );

  assert.equal(output.selected.length, 0);
  assert.ok(output.rejected[0].reasons.includes("availability policy surface"));
});

for (const title of [
  "fix(runtime): change retry policy after provider errors",
  "fix(runtime): increase retries after provider errors",
  "fix(gateway): use local fallback after accepted run disconnects",
  "fix(gateway): fall back after accepted run disconnects",
  "fix(gateway): disable fallback after accepted run disconnects",
  "fix(signal): force kill daemon during shutdown",
  "fix(signal): send SIGKILL during shutdown",
  "fix(agent): rerun request after accepted turn disconnects",
  "fix(agent): execute accepted request twice after disconnect",
  "fix(agent): prevent duplicate tool calls after disconnect",
]) {
  test(`rejects unlabeled availability policy: ${title}`, () => {
    const output = runHydrated(
      hydratedPr({
        title,
        labels: [{ name: "rating: platinum hermit" }],
      }),
    );

    assert.equal(output.selected.length, 0);
    assert.ok(output.rejected[0].reasons.includes("availability policy surface"));
  });
}

test("rejects a bare availability label", () => {
  const output = runHydrated(
    hydratedPr({
      labels: [{ name: "availability" }],
    }),
  );

  assert.equal(output.selected.length, 0);
  assert.ok(output.rejected[0].reasons.includes("high-risk or compatibility surface"));
});

test("normalizes gitcrawl thread envelopes without dropping risk labels", () => {
  const output = runDiscoveryInput({
    threads: [
      {
        number: 96219,
        title: "fix(cron): align setup watchdog with job timeout",
        author_login: "contributor",
        is_draft: false,
        labels_json: JSON.stringify([
          "rating: platinum hermit",
          "merge-risk: availability",
        ]),
        url: "https://github.com/openclaw/openclaw/pull/96219",
      },
    ],
  });

  assert.equal(output.selected.length, 0);
  assert.equal(output.rejected[0].author, "contributor");
  assert.ok(output.rejected[0].reasons.includes("high-risk or compatibility surface"));
});

test("excludes terminal decisions from a persisted decision ledger", () => {
  const directory = mkdtempSync(path.join(tmpdir(), "openclaw-pr-ledger-"));
  const ledgerPath = path.join(directory, "ledger.json");
  writeFileSync(
    ledgerPath,
    JSON.stringify({
      explicitSkips: [],
      landed: [{ number: 12345, reason: "already merged" }],
      closed: [],
      rejected: [],
      ignored: [],
    }),
  );

  try {
    const output = runHydratedArgs(hydratedPr(), ["--decision-ledger", ledgerPath]);
    assert.equal(output.selected.length, 0);
    assert.deepEqual(output.rejected[0].reasons, ["already landed"]);
  } finally {
    rmSync(directory, { recursive: true, force: true });
  }
});

test("excludes handled external merges without treating them as selection precedent", () => {
  const directory = mkdtempSync(path.join(tmpdir(), "openclaw-pr-ledger-"));
  const ledgerPath = path.join(directory, "ledger.json");
  writeFileSync(
    ledgerPath,
    JSON.stringify({
      explicitSkips: [],
      landed: [],
      handledMerged: [12345],
      closed: [],
      rejected: [],
      ignored: [],
    }),
  );

  try {
    const output = runHydratedArgs(hydratedPr(), ["--decision-ledger", ledgerPath]);
    assert.equal(output.selected.length, 0);
    assert.deepEqual(output.rejected[0].reasons, ["already handled and merged"]);
  } finally {
    rmSync(directory, { recursive: true, force: true });
  }
});

test("deduplicates repeated REST pages by PR number", () => {
  const pr = hydratedPr();
  const output = runHydratedMany([pr, pr, pr], []);

  assert.equal(output.qualifiedCount, 1);
  assert.equal(output.selected.length, 1);
  assert.equal(output.selected[0].number, pr.number);
});

for (const olderConclusion of ["FAILURE", "SUCCESS"]) {
  test(`treats a newer in-progress check as pending instead of an older ${olderConclusion.toLowerCase()} result`, () => {
    const output = runHydrated(
      hydratedPr({
        statusCheckRollup: [
          checkRun({
            status: "IN_PROGRESS",
            conclusion: null,
            startedAt: "2026-07-01T11:00:00Z",
            completedAt: "0001-01-01T00:00:00Z",
          }),
          checkRun({
            status: "COMPLETED",
            conclusion: olderConclusion,
            startedAt: "2026-07-01T10:00:00Z",
            completedAt: "2026-07-01T10:10:00Z",
          }),
        ],
      }),
    );

    assert.equal(output.selected.length, 0);
    assert.equal(output.rejected.length, 1);
    assert.deepEqual(output.rejected[0].reasons, ["pending checks"]);
  });
}
