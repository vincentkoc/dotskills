#!/usr/bin/env node

import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
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
  const result = spawnSync(process.execPath, [scriptPath, "--hydrated"], {
    input: JSON.stringify([pr]),
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

for (const olderConclusion of ["FAILURE", "SUCCESS"]) {
  test(`prefers a newer in-progress check over an older ${olderConclusion.toLowerCase()} check`, () => {
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

    assert.equal(output.rejected.length, 0);
    assert.equal(output.selected.length, 1);
    assert.equal(output.selected[0].score, 15);
  });
}
