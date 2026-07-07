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

test("rejects tiny diagnostic wording changes even with broad tests", () => {
  const output = runHydrated(
    hydratedPr({
      title: "fix(gateway): improve websocket error message context",
      labels: [
        { name: "rating: diamond lobster" },
        { name: "proof: sufficient" },
      ],
      files: [
        { filename: "src/gateway/call.ts", additions: 3, deletions: 0 },
        { filename: "src/gateway/call.test.ts", additions: 80, deletions: 0 },
      ],
      additions: 83,
      deletions: 0,
    }),
  );

  assert.equal(output.selected.length, 0);
  assert.ok(output.rejected[0].reasons.includes("trivial production diff"));
  assert.ok(output.rejected[0].reasons.includes("diagnostic-only micro-change"));
});

test("keeps substantive process failure propagation despite diagnostic wording", () => {
  const output = runHydrated(
    hydratedPr({
      title: "fix(process): preserve failure context when stderr is empty",
      files: [
        { filename: "src/process/result.ts", additions: 22, deletions: 8 },
        { filename: "src/process/result.test.ts", additions: 45, deletions: 0 },
      ],
      additions: 67,
      deletions: 8,
    }),
  );

  assert.equal(output.rejected.length, 0);
  assert.equal(output.selected.length, 1);
});

for (const title of [
  "fix(agents): include sender in duplicate-user-message dedup key",
  "fix(sessions): reuse successful main sessions after completed runs",
  "fix(sms): replayed webhooks process again after high inbound traffic",
  "fix(agents): send session_id affinity header to Responses backend",
  "fix: prevent delivery mirror prompt contamination",
  "fix(cron): keep isolated run status ok when delivery fails",
  "fix(googlechat): preserve thread targets through reply delivery",
  "fix: pace delivery recovery after startup outages",
  "fix(outbound): clear recoveryState on connect-phase errors so drain can retry",
]) {
  test(`rejects session or delivery semantics: ${title}`, () => {
    const output = runHydrated(hydratedPr({ title }));

    assert.equal(output.selected.length, 0);
    assert.ok(
      output.rejected[0].reasons.includes("session or message-delivery semantics"),
    );
  });
}

test("rejects an exact session-state merge-risk label", () => {
  const output = runHydrated(
    hydratedPr({
      number: 99524,
      title: "fix(agents): preserve fresh tool results during aggregate recovery",
      labels: [{ name: "merge-risk: 🚨 session-state" }],
    }),
  );

  assert.equal(output.selected.length, 0);
  assert.ok(output.rejected[0].reasons.includes("high-risk or compatibility surface"));
});

test("rejects cleanup-only fixes disguised with a fix scope", () => {
  const output = runHydrated(
    hydratedPr({
      number: 100853,
      title: "fix(cron): remove redundant loops and dead code in stagger calculations",
      changed_files: 1,
      files: [{ filename: "src/cron/service/jobs.ts", additions: 6, deletions: 26 }],
      additions: 6,
      deletions: 26,
    }),
  );

  assert.equal(output.selected.length, 0);
  assert.ok(output.rejected[0].reasons.includes("cleanup-only change"));
});

test("rejects bot-authored queue work", () => {
  const output = runHydrated(
    hydratedPr({
      author: { login: "clawsweeper[bot]", type: "Bot" },
    }),
  );

  assert.equal(output.selected.length, 0);
  assert.ok(output.rejected[0].reasons.includes("maintainer-owned"));
});

test("rejects bundled multi-topic bug-fix PRs", () => {
  const output = runHydrated(
    hydratedPr({
      title: "fix(channels): fix five channel lifecycle/shutdown bugs",
    }),
  );

  assert.equal(output.selected.length, 0);
  assert.ok(output.rejected[0].reasons.includes("bundled multi-topic fix"));
});

test("rejects service PATH and dotenv precedence changes", () => {
  const output = runHydrated(
    hydratedPr({
      title: "fix: include pnpm 11 bins in gateway PATH",
      files: [
        { filename: "src/daemon/service-env.ts", additions: 7, deletions: 3 },
        { filename: "src/infra/dotenv.ts", additions: 2, deletions: 0 },
        { filename: "src/infra/path-env.ts", additions: 82, deletions: 0 },
      ],
    }),
  );

  assert.equal(output.selected.length, 0);
  assert.ok(
    output.rejected[0].reasons.includes("service environment or PATH precedence surface"),
  );
});

for (const title of [
  "fix(update): keep self-updates on the running install's global root",
  "fix(update): correct global-install-root selection for self-update",
]) {
  test(`rejects self-update global-install-root precedence: ${title}`, () => {
    const output = runHydrated(
      hydratedPr({
        number: 101228,
        title,
        files: [
          { filename: "src/infra/update-global.ts", additions: 34, deletions: 2 },
          { filename: "src/infra/update-global.test.ts", additions: 134, deletions: 0 },
        ],
        additions: 168,
        deletions: 2,
      }),
    );

    assert.equal(output.selected.length, 0);
    assert.ok(output.rejected[0].reasons.includes("self-update install-root policy surface"));
  });
}

for (const title of [
  "fix(ci): include runtime resources in build artifact",
  "fix(infra): swallow mid-stream errors in live smoke",
  "build: repair generated fixture inventory",
  "test(qa): assert full selection metadata",
  "docs(memory): add CPU-only VPS guidance",
  "chore: update contributor inventory",
]) {
  test(`rejects CI or infrastructure work: ${title}`, () => {
    const output = runHydrated(hydratedPr({ title }));

    assert.equal(output.selected.length, 0);
    assert.ok(output.rejected[0].reasons.includes("low-signal change type"));
  });
}

test("rejects live-smoke routing even without a CI scope", () => {
  const output = runHydrated(
    hydratedPr({ title: "fix: keep Bedrock live smoke on Bedrock runtime" }),
  );

  assert.equal(output.selected.length, 0);
  assert.ok(output.rejected[0].reasons.includes("test or infrastructure work"));
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

test("downgrades an unstable merge state when current checks are green", () => {
  const output = runHydrated(hydratedPr({ mergeable_state: "unstable" }));

  assert.equal(output.rejected.length, 0);
  assert.equal(output.selected.length, 1);
  assert.equal(output.selected[0].score, 10);
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

test("includes green unstable candidates in overlap adjudication", () => {
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
        mergeable_state: "unstable",
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

test("ignores issues in gitcrawl thread envelopes", () => {
  const output = runDiscoveryInput({
    threads: [
      {
        kind: "issue",
        number: 12344,
        title: "[Feature]: add a dashboard",
        author_login: "contributor",
        is_draft: false,
        labels_json: "[]",
        html_url: "https://github.com/openclaw/openclaw/issues/12344",
      },
      {
        kind: "pull_request",
        number: 12345,
        title: "fix(process): preserve failure context when stderr is empty",
        author_login: "contributor",
        is_draft: false,
        labels_json: "[]",
        html_url: "https://github.com/openclaw/openclaw/pull/12345",
      },
    ],
  });

  assert.equal(output.selected.length, 1);
  assert.equal(output.selected[0].number, 12345);
  assert.equal(output.rejected.length, 0);
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
