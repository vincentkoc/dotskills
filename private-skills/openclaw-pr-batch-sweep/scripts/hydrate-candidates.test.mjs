#!/usr/bin/env node

import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import {
  chmodSync,
  mkdtempSync,
  readFileSync,
  rmSync,
  writeFileSync,
} from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const scriptPath = fileURLToPath(new URL("./hydrate-candidates.mjs", import.meta.url));

test("hydrates candidates serially and retries unresolved mergeability", () => {
  const directory = mkdtempSync(path.join(tmpdir(), "openclaw-hydrate-"));
  const inputPath = path.join(directory, "ranked.json");
  const fakeGhxPath = path.join(directory, "fake-ghx.mjs");
  const countPath = path.join(directory, "count");
  const logPath = path.join(directory, "calls.log");

  writeFileSync(
    inputPath,
    JSON.stringify({
      hydrationPool: [{ number: 42, title: "fix: preserve useful behavior" }],
    }),
  );
  writeFileSync(
    fakeGhxPath,
    `#!/usr/bin/env node
import fs from "node:fs";
const args = process.argv.slice(2);
fs.appendFileSync(process.env.CALL_LOG, args.join(" ") + "\\n");
if (args[0] === "api" && args[1] === "repos/openclaw/openclaw/pulls/42") {
  const count = Number(fs.existsSync(process.env.COUNT_FILE) ? fs.readFileSync(process.env.COUNT_FILE, "utf8") : "0") + 1;
  fs.writeFileSync(process.env.COUNT_FILE, String(count));
  console.log(JSON.stringify({
    number: 42,
    state: "open",
    draft: false,
    author_association: "CONTRIBUTOR",
    changed_files: 2,
    mergeable: count === 1 ? null : true,
    mergeable_state: "clean",
    user: { login: "contributor" }
  }));
} else if (args[0] === "api" && args[1].includes("/files?")) {
  console.log(JSON.stringify([
    { filename: "src/example.ts", additions: 20, deletions: 5 },
    { filename: "src/example.test.ts", additions: 30, deletions: 0 }
  ]));
} else if (args[0] === "pr" && args[1] === "view") {
  console.log(JSON.stringify({
    number: 42,
    state: "OPEN",
    isDraft: false,
    url: "https://github.com/openclaw/openclaw/pull/42",
    author: { login: "contributor" },
    labels: [{ name: "rating: platinum hermit" }],
    statusCheckRollup: [],
    mergeStateStatus: "CLEAN",
    headRefOid: "abc123",
    additions: 50,
    deletions: 5,
    changedFiles: 2
  }));
} else {
  process.exitCode = 2;
}
`,
  );
  chmodSync(fakeGhxPath, 0o755);

  try {
    const result = spawnSync(
      process.execPath,
      [scriptPath, "--input", inputPath, "--sleep-ms", "0"],
      {
        encoding: "utf8",
        env: {
          ...process.env,
          GHX_BIN: fakeGhxPath,
          COUNT_FILE: countPath,
          CALL_LOG: logPath,
        },
      },
    );

    assert.equal(result.status, 0, result.stderr);
    const output = JSON.parse(result.stdout);
    assert.equal(output.length, 1);
    assert.equal(output[0].number, 42);
    assert.equal(output[0].author_association, "CONTRIBUTOR");
    assert.equal(output[0].mergeable, true);
    assert.equal(output[0].mergeStateStatus, "CLEAN");
    assert.equal(output[0].files.length, 2);
    assert.deepEqual(output[0].statusCheckRollup, []);

    const calls = readFileSync(logPath, "utf8").trim().split("\n");
    assert.equal(calls.length, 4);
    assert.equal(calls[0], "api repos/openclaw/openclaw/pulls/42");
    assert.match(calls[1], /files\?per_page=25&page=1/);
    assert.match(calls[2], /^pr view 42 /);
    assert.equal(calls[3], "api repos/openclaw/openclaw/pulls/42");
  } finally {
    rmSync(directory, { recursive: true, force: true });
  }
});
