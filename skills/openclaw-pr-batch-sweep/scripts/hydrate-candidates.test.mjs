#!/usr/bin/env node

import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import {
  chmodSync,
  mkdtempSync,
  readFileSync,
  readdirSync,
  rmSync,
  writeFileSync,
} from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const scriptPath = fileURLToPath(new URL("./hydrate-candidates.mjs", import.meta.url));
const rankerPath = fileURLToPath(new URL("./rank-candidates.mjs", import.meta.url));

test("hydrates file and stdin candidates serially without retaining pipeline output", () => {
  const directory = mkdtempSync(path.join(tmpdir(), "openclaw-hydrate-"));
  const inputPath = path.join(directory, "ranked.json");
  const fakeGhxPath = path.join(directory, "fake-ghx.mjs");
  const countPath = path.join(directory, "count");
  const logPath = path.join(directory, "calls.log");
  const candidates = [{ number: 42, title: "fix: preserve useful behavior" }];

  writeFileSync(
    inputPath,
    JSON.stringify({
      hydrationPool: candidates,
    }),
  );
  writeFileSync(
    fakeGhxPath,
    `#!/usr/bin/env node
import fs from "node:fs";
const args = process.argv.slice(2);
fs.appendFileSync(process.env.CALL_LOG, args.join(" ") + "\\n");
if (args[0] === "pr" && args[1] === "list") {
  console.log(${JSON.stringify(JSON.stringify(candidates))});
  if (process.env.FAIL_DISCOVERY === "1") process.exitCode = 23;
} else if (args[0] === "api" && args[1] === "repos/openclaw/openclaw/pulls/42") {
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
    const options = {
      encoding: "utf8",
      cwd: directory,
      env: {
        ...process.env,
        GHX_BIN: fakeGhxPath,
        COUNT_FILE: countPath,
        CALL_LOG: logPath,
        NODE_BIN: process.execPath,
        RANKER: rankerPath,
        HYDRATOR: scriptPath,
      },
    };
    const result = spawnSync(
      process.execPath,
      [scriptPath, "--input", inputPath, "--sleep-ms", "0"],
      options,
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

    const filesBefore = readdirSync(directory).sort();
    for (const input of [
      candidates,
      { hydrationPool: candidates },
      { selected: candidates },
      { threads: candidates },
    ]) {
      const streamed = spawnSync(
        process.execPath,
        [scriptPath, "--input", "-", "--sleep-ms", "0"],
        { ...options, input: JSON.stringify(input) },
      );
      assert.equal(streamed.status, 0, streamed.stderr);
      assert.deepEqual(JSON.parse(streamed.stdout), output);
      assert.match(streamed.stderr, /^\[1\/1\] hydrate #42\n/);
      assert.deepEqual(readdirSync(directory).sort(), filesBefore);
    }

    const pipeline = `
"$GHX_BIN" pr list |
  "$NODE_BIN" "$RANKER" --limit 40 --batch-size 20 |
  "$NODE_BIN" "$HYDRATOR" --input - --sleep-ms 0 |
  "$NODE_BIN" "$RANKER" --hydrated
`;
    for (const [failDiscovery, status] of [["0", 0], ["1", 23]]) {
      const ranked = spawnSync("bash", ["-o", "pipefail", "-c", pipeline], {
        ...options,
        env: { ...options.env, FAIL_DISCOVERY: failDiscovery },
      });
      assert.equal(ranked.status, status, ranked.stderr);
      const selection = JSON.parse(ranked.stdout);
      assert.equal(selection.phase, "hydrated");
      assert.deepEqual(selection.selected.map((candidate) => candidate.number), [42]);
      assert.match(ranked.stderr, /^\[1\/1\] hydrate #42\n/);
      assert.deepEqual(readdirSync(directory).sort(), filesBefore);
    }

    const outputPath = path.join(directory, "hydrated.json");
    const saved = spawnSync(
      process.execPath,
      [scriptPath, "--input", inputPath, "--output", outputPath, "--sleep-ms", "0"],
      options,
    );
    assert.equal(saved.status, 0, saved.stderr);
    assert.equal(saved.stdout, "");
    assert.deepEqual(JSON.parse(readFileSync(outputPath, "utf8")), output);

    const callsBeforeInvalidInput = readFileSync(logPath, "utf8");
    for (const [args, input, error] of [
      [[], JSON.stringify(candidates), /--input is required/],
      [["--input", "-"], "{", /SyntaxError/],
    ]) {
      const invalid = spawnSync(process.execPath, [scriptPath, ...args], {
        ...options,
        input,
      });
      assert.notEqual(invalid.status, 0);
      assert.equal(invalid.stdout, "");
      assert.match(invalid.stderr, error);
      assert.equal(readFileSync(logPath, "utf8"), callsBeforeInvalidInput);
    }
  } finally {
    rmSync(directory, { recursive: true, force: true });
  }
});

test("retries transient ghx transport failures", () => {
  const directory = mkdtempSync(path.join(tmpdir(), "openclaw-hydrate-retry-"));
  const inputPath = path.join(directory, "ranked.json");
  const fakeGhxPath = path.join(directory, "fake-ghx.mjs");
  const countPath = path.join(directory, "count");

  writeFileSync(inputPath, JSON.stringify([{ number: 43 }, { number: 44 }, { number: 45 }]));
  writeFileSync(
    fakeGhxPath,
    `#!/usr/bin/env node
import fs from "node:fs";
const args = process.argv.slice(2);
if (args[0] === "api" && args[1] === "repos/openclaw/openclaw/pulls/43") {
  const count = Number(fs.existsSync(process.env.COUNT_FILE) ? fs.readFileSync(process.env.COUNT_FILE, "utf8") : "0") + 1;
  fs.writeFileSync(process.env.COUNT_FILE, String(count));
  if (count <= 3) {
    console.error('Get "https://api.github.com/repos/openclaw/openclaw/pulls/43": unexpected EOF');
    process.exit(1);
  }
  console.log(JSON.stringify({
    number: 43,
    state: "open",
    draft: false,
    changed_files: 1,
    mergeable: true,
    mergeable_state: "clean"
  }));
} else if (args[0] === "api" && args[1] === "repos/openclaw/openclaw/pulls/44") {
  console.error('Get "https://api.github.com/repos/openclaw/openclaw/pulls/44": unexpected EOF');
  process.exit(1);
} else if (args[0] === "api" && args[1] === "repos/openclaw/openclaw/pulls/45") {
  console.log(JSON.stringify({
    number: 45,
    state: "open",
    draft: false,
    changed_files: 1,
    mergeable: true,
    mergeable_state: "clean"
  }));
} else if (args[0] === "api" && args[1].includes("/files?")) {
  console.log(JSON.stringify([{ filename: "src/example.ts", additions: 4, deletions: 2 }]));
} else if (args[0] === "pr" && args[1] === "view") {
  const number = Number(args[2]);
  console.log(JSON.stringify({
    number,
    state: "OPEN",
    isDraft: false,
    url: \`https://github.com/openclaw/openclaw/pull/\${number}\`,
    author: { login: "contributor" },
    labels: [],
    statusCheckRollup: [],
    mergeStateStatus: "CLEAN",
    headRefOid: "def456",
    additions: 4,
    deletions: 2,
    changedFiles: 1
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
        },
      },
    );

    assert.equal(result.status, 0, result.stderr);
    const output = JSON.parse(result.stdout);
    assert.equal(output[0].number, 43);
    assert.equal(output[1].number, 44);
    assert.equal(output[1].hydrationComplete, false);
    assert.match(output[1].hydrationError, /unexpected EOF/);
    assert.equal(output[2].number, 45);
    assert.equal(output[2].hydrationError, undefined);
    assert.equal(readFileSync(countPath, "utf8"), "4");
    assert.match(result.stderr, /transient failure; retry 4\/5 in 0ms/);
    assert.match(result.stderr, /hydrate #44 remained unavailable.*continuing/);
  } finally {
    rmSync(directory, { recursive: true, force: true });
  }
});
