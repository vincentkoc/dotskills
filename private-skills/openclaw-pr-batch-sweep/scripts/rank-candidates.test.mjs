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

test("rejects odd mechanical micro-fixes regardless of readiness labels", () => {
  const output = runHydrated(
    hydratedPr({
      title: "fix: clear timeout timer after probe",
      labels: [{ name: "rating: diamond lobster" }, { name: "proof: sufficient" }],
    }),
  );

  assert.equal(output.selected.length, 0);
  assert.ok(output.rejected[0].reasons.includes("low-signal change type"));
  assert.ok(output.rejected[0].reasons.includes("odd mechanical micro-fix"));
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

test("rejects an unstable merge state", () => {
  const output = runHydrated(hydratedPr({ mergeable_state: "unstable" }));

  assert.equal(output.selected.length, 0);
  assert.deepEqual(output.rejected[0].reasons, ["unstable merge state"]);
});

test("rejects overlapping candidates for the same issue and owner files", () => {
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
    assert.ok(
      pr.reasons.includes("overlapping candidate for the same issue and owner files"),
    );
  }
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
    assert.deepEqual(output.rejected[0].reasons, ["explicitly skipped"]);
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
