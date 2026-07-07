#!/usr/bin/env node

import { spawnSync } from "node:child_process";
import fs from "node:fs";

const args = process.argv.slice(2);
let inputPath = "";
let outputPath = "";
let repo = "openclaw/openclaw";
let limit = 40;
let sleepMs = 2000;

for (let index = 0; index < args.length; index += 1) {
  const arg = args[index];
  if (arg === "--input") {
    inputPath = args[++index] ?? "";
  } else if (arg === "--output") {
    outputPath = args[++index] ?? "";
  } else if (arg === "--repo") {
    repo = args[++index] ?? "";
  } else if (arg === "--limit") {
    limit = Number.parseInt(args[++index] ?? "40", 10);
  } else if (arg === "--sleep-ms") {
    sleepMs = Number.parseInt(args[++index] ?? "2000", 10);
  } else if (arg === "--help") {
    console.log(
      "Usage: hydrate-candidates.mjs --input ranked.json [--output hydrated.json] [--repo owner/name] [--limit 40] [--sleep-ms 2000]",
    );
    process.exit(0);
  } else {
    throw new Error(`Unknown argument: ${arg}`);
  }
}

if (!inputPath) throw new Error("--input is required");
if (!/^[^/]+\/[^/]+$/.test(repo)) throw new Error("--repo must be owner/name");
if (!Number.isInteger(limit) || limit < 1 || limit > 100) {
  throw new Error("--limit must be an integer from 1 to 100");
}
if (!Number.isInteger(sleepMs) || sleepMs < 0 || sleepMs > 30_000) {
  throw new Error("--sleep-ms must be an integer from 0 to 30000");
}

const ghxBin = process.env.GHX_BIN || "ghx";
const commandEnv = {
  ...process.env,
  NO_COLOR: "1",
  CLICOLOR: "0",
  CLICOLOR_FORCE: "0",
  GH_FORCE_TTY: "0",
};

function runJson(commandArgs) {
  const result = spawnSync(ghxBin, commandArgs, {
    encoding: "utf8",
    env: commandEnv,
    maxBuffer: 20 * 1024 * 1024,
  });
  if (result.status !== 0) {
    throw new Error(
      `${ghxBin} ${commandArgs.join(" ")} failed: ${result.stderr.trim() || result.stdout.trim()}`,
    );
  }
  return JSON.parse(result.stdout);
}

function sleep(durationMs) {
  if (durationMs === 0) return;
  Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, durationMs);
}

function candidateArray(parsed) {
  if (Array.isArray(parsed)) return parsed;
  for (const key of ["hydrationPool", "selected", "threads"]) {
    if (Array.isArray(parsed[key])) return parsed[key];
  }
  throw new Error("Expected an array or an object with hydrationPool, selected, or threads");
}

function unresolvedMergeability(pr) {
  return pr.mergeable === null || String(pr.mergeable_state ?? "").toLowerCase() === "unknown";
}

function hydrate(candidate) {
  const number = Number(candidate.number);
  if (!Number.isInteger(number) || number < 1) {
    throw new Error(`Invalid PR number: ${String(candidate.number)}`);
  }

  let rest = runJson(["api", `repos/${repo}/pulls/${number}`]);

  const files = [];
  for (let page = 1; ; page += 1) {
    const pageFiles = runJson([
      "api",
      `repos/${repo}/pulls/${number}/files?per_page=25&page=${page}`,
    ]);
    if (!Array.isArray(pageFiles)) {
      throw new Error(`Expected file array for PR #${number}, page ${page}`);
    }
    files.push(
      ...pageFiles.map((file) => ({
        filename: file.filename,
        additions: file.additions,
        deletions: file.deletions,
      })),
    );
    if (pageFiles.length < 25) break;
  }

  const live = runJson([
    "pr",
    "view",
    String(number),
    "--repo",
    repo,
    "--json",
    "number,state,isDraft,url,author,labels,statusCheckRollup,mergeStateStatus,headRefOid,additions,deletions,changedFiles",
  ]);

  for (let attempt = 2; attempt <= 5 && unresolvedMergeability(rest); attempt += 1) {
    sleep(sleepMs);
    rest = runJson(["api", `repos/${repo}/pulls/${number}`]);
  }

  return {
    ...candidate,
    ...rest,
    number,
    state: live.state ?? rest.state,
    draft: live.isDraft ?? rest.draft,
    isDraft: live.isDraft ?? rest.draft,
    url: live.url ?? rest.html_url ?? candidate.url,
    author: live.author ?? candidate.author ?? rest.user,
    labels: live.labels ?? rest.labels ?? candidate.labels ?? [],
    additions: live.additions ?? rest.additions,
    deletions: live.deletions ?? rest.deletions,
    changed_files: rest.changed_files ?? live.changedFiles,
    changedFiles: live.changedFiles ?? rest.changed_files,
    mergeStateStatus: live.mergeStateStatus,
    headRefOid: live.headRefOid,
    statusCheckRollup: Array.isArray(live.statusCheckRollup)
      ? live.statusCheckRollup
      : [],
    files,
  };
}

const parsed = JSON.parse(fs.readFileSync(inputPath, "utf8"));
const candidates = candidateArray(parsed).slice(0, limit);
const hydrated = [];

for (const [index, candidate] of candidates.entries()) {
  process.stderr.write(`[${index + 1}/${candidates.length}] hydrate #${candidate.number}\n`);
  hydrated.push(hydrate(candidate));
}

const output = `${JSON.stringify(hydrated, null, 2)}\n`;
if (outputPath) {
  fs.writeFileSync(outputPath, output);
} else {
  process.stdout.write(output);
}
