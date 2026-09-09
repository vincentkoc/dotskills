#!/usr/bin/env node

import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { mkdirSync, mkdtempSync, readdirSync, readFileSync, rmSync, statSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const scriptPath = fileURLToPath(new URL("./semantic-map.mjs", import.meta.url));

function fixture(t) {
  const directory = mkdtempSync(path.join(tmpdir(), "semantic-map-test-"));
  t.after(() => rmSync(directory, { recursive: true, force: true }));
  const writeJson = (name, value) => {
    const target = path.join(directory, name);
    mkdirSync(path.dirname(target), { recursive: true });
    writeFileSync(target, JSON.stringify(value));
  };
  for (const [name, file] of [
    ["auth", "src/auth/login.ts"],
    ["docs", "docs/auth.md"],
    ["android", "apps/android/Login.kt"],
  ]) {
    writeJson(`clawpatch/features/${name}.json`, {
      featureId: name,
      title: `${name} feature`,
      kind: "source",
      ownedFiles: [{ path: file }],
      entrypoints: [{ path: file }],
    });
    writeJson(`deepsec/files/${name}.json`, {
      filePath: file,
      candidates: [{ vulnSlug: "rce" }],
    });
  }
  writeJson("issues.json", [{ id: 123, title: "src/auth login failure" }]);
  writeJson("support.json", [{ id: 456, title: "src/auth login report" }]);
  return directory;
}

function run(directory, args = []) {
  return spawnSync(process.execPath, [scriptPath, ...args], {
    cwd: directory,
    encoding: "utf8",
  });
}

function inputs() {
  return ["--clawpatch", "clawpatch", "--deepsec", "deepsec", "--gitcrawl", "issues.json", "--discrawl", "support.json"];
}

function model(output) {
  const result = JSON.parse(output);
  delete result.generatedAt;
  return result;
}

function footprint(directory) {
  return readdirSync(directory, { recursive: true })
    .sort()
    .map((name) => {
      const stat = statSync(path.join(directory, name));
      return { name, bytes: stat.isFile() ? stat.size : null };
    });
}

test("default output is JSON and repeated runs leave inputs and directories unchanged", (t) => {
  const directory = fixture(t);
  const before = footprint(directory);
  for (let attempt = 0; attempt < 3; attempt += 1) {
    const result = run(directory, inputs());
    assert.equal(result.status, 0, result.stderr);
    assert.equal(result.stderr, "");
    assert.equal(JSON.parse(result.stdout).totals.features, 1);
    assert.deepEqual(footprint(directory), before);
  }
});

test("explicit --out preserves HTML plus sibling JSON and stable repeated-run footprint", (t) => {
  const directory = fixture(t);
  const args = [...inputs(), "--out", "maps/review.htm"];
  const first = run(directory, args);
  assert.equal(first.status, 0, first.stderr);
  assert.equal(first.stdout, "");
  assert.match(readFileSync(path.join(directory, "maps/review.htm"), "utf8"), /^<!doctype html>/u);
  assert.equal(JSON.parse(readFileSync(path.join(directory, "maps/review.json"), "utf8")).totals.features, 1);
  assert.deepEqual(readdirSync(path.join(directory, "maps")).sort(), ["review.htm", "review.json"]);
  const before = footprint(directory);
  for (let attempt = 0; attempt < 3; attempt += 1) {
    const result = run(directory, args);
    assert.equal(result.status, 0, result.stderr);
    assert.deepEqual(footprint(directory), before);
  }
});

for (const format of ["html", "json"]) {
  test(`--format ${format} writes exactly the requested path`, (t) => {
    const directory = fixture(t);
    const result = run(directory, [...inputs(), "--format", format, "--out", "maps/selected.data"]);
    assert.equal(result.status, 0, result.stderr);
    assert.equal(result.stdout, "");
    assert.deepEqual(readdirSync(path.join(directory, "maps")), ["selected.data"]);
    const output = readFileSync(path.join(directory, "maps/selected.data"), "utf8");
    if (format === "json") assert.equal(JSON.parse(output).totals.features, 1);
    else assert.match(output, /^<!doctype html>/u);
  });

  test(`--format ${format} supports stdout without creating files`, (t) => {
    const directory = fixture(t);
    const before = footprint(directory);
    const result = run(directory, [...inputs(), "--format", format]);
    assert.equal(result.status, 0, result.stderr);
    assert.equal(result.stderr, "");
    if (format === "json") assert.equal(JSON.parse(result.stdout).totals.features, 1);
    else assert.match(result.stdout, /^<!doctype html>/u);
    assert.deepEqual(footprint(directory), before);
  });
}

test("explicit both produces the same files as the default with --out", (t) => {
  const directory = fixture(t);
  const result = run(directory, [...inputs(), "--format", "both", "--out", "review.html"]);
  assert.equal(result.status, 0, result.stderr);
  assert.equal(result.stdout, "");
  assert.match(readFileSync(path.join(directory, "review.html"), "utf8"), /^<!doctype html>/u);
  assert.equal(JSON.parse(readFileSync(path.join(directory, "review.json"), "utf8")).totals.features, 1);
});

for (const [args, error] of [
  [["--format", "invalid", "--out", "not-created/report.html"], /invalid --format/u],
  [["--format", "both"], /--format both requires --out/u],
  [["--format"], /missing value for --format/u],
]) {
  test(`rejects ${args.join(" ")} before reading inputs or creating output`, (t) => {
    const directory = fixture(t);
    const before = footprint(directory);
    const result = run(directory, ["--gitcrawl", "missing-input.json", ...args]);
    assert.equal(result.status, 2);
    assert.equal(result.stdout, "");
    assert.match(result.stderr, error);
    assert.doesNotMatch(result.stderr, /ENOENT/u);
    assert.deepEqual(footprint(directory), before);
  });
}

for (const [sparseArgs, expectedFeatures] of [
  [[], 1],
  [["--no-sparse"], 3],
  [["--sparse-include", "apps/android/"], 2],
  [["--sparse-exclude", "docs/"], 2],
]) {
  test(`output formats preserve the model and sparse metadata: ${sparseArgs.join(" ") || "default"}`, (t) => {
    const directory = fixture(t);
    const args = [...inputs(), ...sparseArgs];
    const stdout = run(directory, args);
    assert.equal(stdout.status, 0, stdout.stderr);
    const expected = model(stdout.stdout);
    assert.equal(expected.totals.features, expectedFeatures);
    assert.equal(expected.totals.deepsecCandidates, expectedFeatures);
    assert.equal(expected.totals.issueMatches, 1);
    assert.equal(expected.totals.supportMatches, 1);
    assert.equal(expected.inputs.sparse, !sparseArgs.includes("--no-sparse"));
    assert.equal(expected.semanticBuckets.find((row) => row.name === "src/auth").semanticScore, 14);

    for (const format of ["json", "both"]) {
      const outputPath = format === "json" ? "selected.json" : "review.html";
      const result = run(directory, [...args, "--format", format, "--out", outputPath]);
      assert.equal(result.status, 0, result.stderr);
      const jsonPath = format === "json" ? outputPath : "review.json";
      assert.deepEqual(model(readFileSync(path.join(directory, jsonPath), "utf8")), expected);
    }
    const html = readFileSync(path.join(directory, "review.html"), "utf8");
    assert.match(html, /Overall Lens Matrix/u);
    assert.match(html, /Agent Handoff Packet/u);
    assert.match(html, /src\/auth/u);
  });
}
