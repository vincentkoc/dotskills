#!/usr/bin/env node
import fs from "node:fs";
import path from "node:path";
import { spawnSync } from "node:child_process";

const args = parseArgs(process.argv.slice(2));
if (!args.clawpatch && !args.deepsec && !args.gitcrawl && !args.discrawl && !args.repo) {
  die(
    "usage: semantic-map.mjs --clawpatch <state-dir> --deepsec <data/project> --out <semantic-map.html> [--repo <target-repo>] [--churn-since <git-date>] [--gitcrawl <json>] [--discrawl <json>] [--no-sparse|--sparse false] [--sparse-exclude <csv>] [--sparse-include <csv>]",
  );
}

const outPath = args.out ?? path.resolve(process.cwd(), "semantic-map.html");
const defaultSparseExcludes = [
  ".github/",
  ".vscode/",
  ".devcontainer/",
  "docs/",
  "CHANGELOG.md",
  "changelog/",
  "apps/android/",
  "apps/ios/",
  "apps/mobile/",
  "android/",
  "ios/",
  "mobile/",
];
const contaminationPrefixes = [
  ".git/",
  ".claude/",
  ".codex/",
  ".agents/",
  ".deepsec/",
  ".semantic-slicing/",
  "node_modules/",
  "dist/",
  "build/",
  "coverage/",
  ".next/",
  ".turbo/",
];
const highRiskSlugs = new Set([
  "auth-bypass",
  "dangerous-html",
  "missing-auth",
  "open-redirect",
  "path-traversal",
  "rce",
  "secret-in-log",
  "secrets-exposure",
  "security-behind-flag",
  "ssrf",
  "untrusted-redirect-following",
]);
const sparseConfig = buildSparseConfig(args);

const features = args.clawpatch ? readClawpatchFeatures(args.clawpatch) : [];
const deepsecFiles = args.deepsec ? readDeepsecFiles(args.deepsec) : [];
const gitcrawlRecords = args.gitcrawl ? readEvidenceRecords(args.gitcrawl) : [];
const discrawlRecords = args.discrawl ? readEvidenceRecords(args.discrawl) : [];

const semanticBuckets = new Map();
const securityBuckets = new Map();
const slugCounts = new Map();
const topFiles = [];

for (const feature of features) {
  const refs = featureRefs(feature);
  const contaminated = refs.all.filter(isContaminated);
  const cleanRefs = refs.all.filter((item) => !isContaminated(item) && isReviewPath(item));
  if (cleanRefs.length === 0 && contaminated.length > 0) continue;
  if (cleanRefs.length === 0 && refs.all.length > 0) continue;

  const bucket = bucketFor(preferredFeaturePath(feature, cleanRefs));
  const record = ensureSemanticBucket(semanticBuckets, bucket);
  record.features += 1;
  record.contaminatedRefs += contaminated.length;
  bump(record.kinds, feature.kind ?? "unknown");
  bump(record.sources, feature.source ?? "unknown");
  addPaths(record.ownedFiles, refs.owned);
  addPaths(record.entrypoints, refs.entrypoints);
  addPaths(record.contextFiles, refs.context);
  addPaths(record.testFiles, refs.tests);
  if (feature.featureId && record.featureIds.length < 24) record.featureIds.push(feature.featureId);
  if (record.representativeFeatures.length < 8) {
    record.representativeFeatures.push({
      featureId: feature.featureId ?? null,
      title: feature.title ?? null,
      kind: feature.kind ?? "unknown",
      files: cleanRefs.slice(0, 5),
    });
  }
}

for (const file of deepsecFiles) {
  if (isContaminated(file.filePath)) continue;
  if (!isReviewPath(file.filePath)) continue;
  const candidates = Array.isArray(file.candidates) ? file.candidates : [];
  if (candidates.length === 0) continue;

  const bucket = bucketFor(file.filePath);
  const record = ensureSecurityBucket(securityBuckets, bucket);
  record.files += 1;
  record.candidates += candidates.length;
  for (const candidate of candidates) {
    const slug = candidate.vulnSlug ?? candidate.slug ?? "unknown";
    bump(record.slugs, slug);
    slugCounts.set(slug, (slugCounts.get(slug) ?? 0) + 1);
    if (highRiskSlugs.has(slug)) record.highRiskCandidates += 1;
  }
  const fileRecord = {
    path: file.filePath,
    bucket,
    candidates: candidates.length,
    slugs: [...new Set(candidates.map((item) => item.vulnSlug ?? item.slug ?? "unknown"))].slice(0, 8),
  };
  topFiles.push(fileRecord);
  if (record.topFiles.length < 20) record.topFiles.push(fileRecord);
}

topFiles.sort((a, b) => b.candidates - a.candidates || a.path.localeCompare(b.path));

const semanticRows = [...semanticBuckets.values()].map(finalizeSemanticBucket);
semanticRows.sort((a, b) => b.semanticScore - a.semanticScore || a.name.localeCompare(b.name));

const securityRows = [...securityBuckets.values()].map(finalizeSecurityBucket);
securityRows.sort(
  (a, b) =>
    b.highRiskCandidates - a.highRiskCandidates ||
    b.candidates - a.candidates ||
    a.name.localeCompare(b.name),
);

const issueRows = normalizeEvidence(gitcrawlRecords, semanticRows, "issue");
const supportRows = normalizeEvidence(discrawlRecords, semanticRows, "support");
const developmentRows = args.repo ? readDevelopmentOverlay(args.repo, args["churn-since"] ?? "90.days") : [];
const ownershipRows = args.repo ? readOwnershipOverlay(args.repo) : [];
const model = enrichSemanticModel(
  mergeBuckets(semanticRows, securityRows, issueRows, supportRows, developmentRows, ownershipRows),
  {
    semanticRows,
    securityRows,
    issueRows,
    supportRows,
    developmentRows,
    ownershipRows,
  },
);

const summary = {
  generatedAt: new Date().toISOString(),
  title: args.title ?? "Semantic Slice Map",
  inputs: {
    repo: args.repo ?? null,
    churnSince: args["churn-since"] ?? "90.days",
    clawpatch: args.clawpatch ?? null,
    deepsec: args.deepsec ?? null,
    gitcrawl: args.gitcrawl ?? null,
    discrawl: args.discrawl ?? null,
    sparse: sparseConfig.enabled,
    sparseExcludes: sparseConfig.enabled ? sparseConfig.excludes : [],
    sparseIncludes: sparseConfig.enabled ? sparseConfig.includes : [],
  },
  totals: {
    semanticBuckets: semanticRows.length,
    features: semanticRows.reduce((sum, item) => sum + item.features, 0),
    deepsecFiles: securityRows.reduce((sum, item) => sum + item.files, 0),
    deepsecCandidates: securityRows.reduce((sum, item) => sum + item.candidates, 0),
    highRiskCandidates: securityRows.reduce((sum, item) => sum + item.highRiskCandidates, 0),
    issueRecords: gitcrawlRecords.length,
    supportRecords: discrawlRecords.length,
    issueMatches: issueRows.reduce((sum, item) => sum + item.count, 0),
    supportMatches: supportRows.reduce((sum, item) => sum + item.count, 0),
    trackedFiles: developmentRows.reduce((sum, item) => sum + item.trackedFiles, 0),
    churnEvents: developmentRows.reduce((sum, item) => sum + item.churnEvents, 0),
    churnFiles: developmentRows.reduce((sum, item) => sum + item.churnFileCount, 0),
    codeownerRules: ownershipRows.reduce((sum, item) => sum + item.rules, 0),
    contaminatedRefs: semanticRows.reduce((sum, item) => sum + item.contaminatedRefs, 0),
    maxImpactScore: max(model.buckets, "impactScore"),
  },
  semanticBuckets: semanticRows,
  ownershipOverlay: ownershipRows,
  securityOverlay: securityRows,
  issueOverlay: issueRows,
  supportOverlay: supportRows,
  developmentOverlay: developmentRows,
  normalizedQueues: {
    impact: model.buckets.slice(0, 30),
    semantic: semanticRows.slice(0, 30),
    ownership: ownershipRows.filter((item) => item.rules > 0).slice(0, 30),
    development: developmentRows.filter((item) => item.developmentScore > 0).slice(0, 30),
    security: securityRows.filter((item) => item.highRiskCandidates > 0).slice(0, 30),
    issues: issueRows.filter((item) => item.count > 0).slice(0, 30),
    support: supportRows.filter((item) => item.count > 0).slice(0, 30),
  },
  buckets: model.buckets,
  treeNodes: model.treeNodes,
  relatedEdges: model.relatedEdges,
  savedViews: model.savedViews,
  topSlugs: topEntries(Object.fromEntries(slugCounts), 20),
  topFiles: topFiles.slice(0, 100),
};

fs.mkdirSync(path.dirname(outPath), { recursive: true });
fs.writeFileSync(outPath, renderHtml(summary), "utf8");
fs.writeFileSync(outPath.replace(/\.html?$/u, "") + ".json", JSON.stringify(summary, null, 2) + "\n", "utf8");
console.log(`wrote ${outPath}`);
console.log(`wrote ${outPath.replace(/\.html?$/u, "")}.json`);

function parseArgs(argv) {
  const out = {};
  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];
    if (!arg.startsWith("--")) die(`unexpected argument: ${arg}`);
    const key = arg.slice(2);
    if (key === "no-sparse") {
      out.sparse = "false";
      continue;
    }
    const value = argv[index + 1];
    if (key === "sparse" && (!value || value.startsWith("--"))) {
      out.sparse = "true";
      continue;
    }
    if (!value || value.startsWith("--")) die(`missing value for ${arg}`);
    out[key] = value;
    index += 1;
  }
  return out;
}

function buildSparseConfig(parsedArgs) {
  const enabled = parseBoolean(parsedArgs.sparse ?? "true", "sparse");
  const excludes = parseCsv(parsedArgs["sparse-exclude"] ?? defaultSparseExcludes.join(","));
  const includes = parseCsv(parsedArgs["sparse-include"] ?? "");
  return { enabled, excludes, includes };
}

function parseBoolean(value, name) {
  const normalized = String(value).trim().toLowerCase();
  if (["1", "true", "yes", "on"].includes(normalized)) return true;
  if (["0", "false", "no", "off"].includes(normalized)) return false;
  die(`invalid boolean for --${name}: ${value}`);
}

function parseCsv(value) {
  return String(value)
    .split(",")
    .map((item) => normalizePath(item.trim()))
    .filter(Boolean);
}

function readClawpatchFeatures(stateDir) {
  const featureDir = path.join(stateDir, "features");
  if (!fs.existsSync(featureDir)) return [];
  return readJsonFiles(featureDir);
}

function readDeepsecFiles(projectDataDir) {
  const fileDir = path.join(projectDataDir, "files");
  if (!fs.existsSync(fileDir)) return [];
  return readJsonFiles(fileDir);
}

function readEvidenceRecords(filePath) {
  const raw = JSON.parse(fs.readFileSync(filePath, "utf8"));
  return flattenRecords(raw).map((record) => normalizeEvidenceRecord(record));
}

function readDevelopmentOverlay(repoRoot, churnSince) {
  const files = gitLines(repoRoot, ["ls-files"]);
  if (files.length === 0) return [];

  const rows = new Map();
  for (const filePath of files.map(normalizePath).filter((item) => !isContaminated(item) && isReviewPath(item))) {
    const row = ensureDevelopmentBucket(rows, bucketFor(filePath));
    row.trackedFiles += 1;
    if (isTestPath(filePath)) row.testFiles += 1;
    else if (isDocPath(filePath)) row.docFiles += 1;
    else if (isSourcePath(filePath)) row.codeFiles += 1;
  }

  const churn = gitLines(repoRoot, ["log", `--since=${churnSince}`, "--name-only", "--pretty=format:"]);
  for (const filePath of churn.map(normalizePath).filter((item) => item && !isContaminated(item) && isReviewPath(item))) {
    const row = ensureDevelopmentBucket(rows, bucketFor(filePath));
    row.churnEvents += 1;
    row.churnFiles.add(filePath);
  }

  return [...rows.values()]
    .map(finalizeDevelopmentBucket)
    .sort((a, b) => b.developmentScore - a.developmentScore || a.name.localeCompare(b.name));
}

function readOwnershipOverlay(repoRoot) {
  const codeownersPath = [".github/CODEOWNERS", "CODEOWNERS", "docs/CODEOWNERS"]
    .map((candidate) => path.join(repoRoot, candidate))
    .find((candidate) => fs.existsSync(candidate));
  if (!codeownersPath) return [];

  const rows = new Map();
  const lines = fs.readFileSync(codeownersPath, "utf8").split(/\r?\n/u);
  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#")) continue;
    const [pattern, ...owners] = trimmed.split(/\s+/u);
    if (!pattern || owners.length === 0) continue;
    const bucketName = bucketForCodeownerPattern(pattern);
    if (!bucketName) continue;
    if (!isReviewBucket(bucketName)) continue;
    const row = ensureOwnershipBucket(rows, bucketName);
    row.rules += 1;
    for (const owner of owners) row.owners.add(owner);
    if (row.samplePatterns.length < 8) row.samplePatterns.push(pattern);
  }

  return [...rows.values()]
    .map(finalizeOwnershipBucket)
    .sort((a, b) => b.ownershipScore - a.ownershipScore || a.name.localeCompare(b.name));
}

function bucketForCodeownerPattern(pattern) {
  let normalized = normalizePath(pattern.replace(/^\/+/u, "").replace(/^\\#/u, "#"));
  if (!normalized || normalized.startsWith("!") || normalized.startsWith("[")) return null;
  normalized = normalized.replace(/^\*\*\//u, "");
  const globIndex = normalized.search(/[*?[{]/u);
  if (globIndex >= 0) normalized = normalized.slice(0, globIndex);
  normalized = normalized.replace(/\/$/u, "");
  if (!normalized || normalized === ".") return null;
  return bucketFor(normalized);
}

function ensureOwnershipBucket(map, name) {
  if (!map.has(name)) {
    map.set(name, {
      name,
      rules: 0,
      owners: new Set(),
      samplePatterns: [],
    });
  }
  return map.get(name);
}

function finalizeOwnershipBucket(bucket) {
  const owners = [...bucket.owners].sort((a, b) => a.localeCompare(b));
  return {
    name: bucket.name,
    rules: bucket.rules,
    ownerCount: owners.length,
    owners,
    samplePatterns: bucket.samplePatterns,
    ownershipScore: bucket.rules * 4 + owners.length,
  };
}

function ensureDevelopmentBucket(map, name) {
  if (!map.has(name)) {
    map.set(name, {
      name,
      trackedFiles: 0,
      codeFiles: 0,
      testFiles: 0,
      docFiles: 0,
      churnEvents: 0,
      churnFiles: new Set(),
    });
  }
  return map.get(name);
}

function finalizeDevelopmentBucket(bucket) {
  const churnFileCount = bucket.churnFiles.size;
  const testRatio = bucket.codeFiles > 0 ? bucket.testFiles / bucket.codeFiles : 0;
  const testGap = Math.max(0, bucket.codeFiles - bucket.testFiles * 2);
  return {
    name: bucket.name,
    trackedFiles: bucket.trackedFiles,
    codeFiles: bucket.codeFiles,
    testFiles: bucket.testFiles,
    docFiles: bucket.docFiles,
    churnEvents: bucket.churnEvents,
    churnFileCount,
    testRatio,
    testGap,
    developmentScore: bucket.churnEvents * 2 + churnFileCount * 3 + testGap,
  };
}

function gitLines(repoRoot, args) {
  const result = spawnSync("git", ["-C", repoRoot, ...args], {
    encoding: "utf8",
    maxBuffer: 64 * 1024 * 1024,
  });
  if (result.status !== 0) return [];
  return result.stdout.split(/\r?\n/u).map((line) => line.trim()).filter(Boolean);
}

function readJsonFiles(dir) {
  const files = [];
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      files.push(...readJsonFiles(full));
    } else if (entry.isFile() && entry.name.endsWith(".json")) {
      try {
        files.push(JSON.parse(fs.readFileSync(full, "utf8")));
      } catch {
        // Keep map generation best-effort; corrupt records are skipped.
      }
    }
  }
  return files;
}

function flattenRecords(value) {
  if (Array.isArray(value)) return value.flatMap((item) => flattenRecords(item));
  if (!value || typeof value !== "object") return [];
  for (const key of ["items", "threads", "clusters", "messages", "results", "records", "data"]) {
    if (Array.isArray(value[key])) return flattenRecords(value[key]);
  }
  return [value];
}

function normalizeEvidenceRecord(record) {
  const text = collectStrings(record).join(" ").replace(/\s+/g, " ").trim();
  return {
    id: stringOrNull(record.id ?? record.number ?? record.url ?? record.message_id ?? record.messageId),
    title: stringOrNull(record.title ?? record.subject ?? record.channel_name ?? record.channelName),
    url: stringOrNull(record.url ?? record.html_url ?? record.htmlUrl),
    state: stringOrNull(record.state ?? record.status),
    text,
  };
}

function collectStrings(value, depth = 0) {
  if (depth > 4 || value == null) return [];
  if (typeof value === "string") return [value];
  if (typeof value === "number" || typeof value === "boolean") return [String(value)];
  if (Array.isArray(value)) return value.flatMap((item) => collectStrings(item, depth + 1));
  if (typeof value !== "object") return [];
  return Object.entries(value)
    .filter(([key]) => !["raw_json", "body"].includes(key))
    .flatMap(([, item]) => collectStrings(item, depth + 1));
}

function featureRefs(feature) {
  const owned = pathsFrom(feature.ownedFiles);
  const entrypoints = pathsFrom(feature.entrypoints);
  const context = pathsFrom(feature.contextFiles);
  const tests = pathsFrom(feature.testFiles);
  return {
    owned,
    entrypoints,
    context,
    tests,
    all: [...owned, ...entrypoints, ...context, ...tests],
  };
}

function pathsFrom(items) {
  if (!Array.isArray(items)) return [];
  return items.map((item) => item?.path).filter(Boolean).map(normalizePath);
}

function preferredFeaturePath(feature, cleanRefs) {
  const nonManifest = cleanRefs.find((item) => path.basename(item) !== "package.json");
  if (nonManifest) return nonManifest;
  const titlePath = titlePathHint(feature?.title);
  if (titlePath) return titlePath;
  return cleanRefs[0] ?? feature?.title ?? "unknown";
}

function titlePathHint(title) {
  if (!title) return null;
  const match = String(title).match(/\b(?:Node source|Project config|Package script|CLI command)\s+([^#(]+)/u);
  if (!match) return null;
  return match[1].trim();
}

function bucketFor(filePath) {
  const normalized = normalizePath(filePath);
  const parts = normalized.split("/");
  if (parts[0] === "extensions" && parts[1]) return `extensions/${parts[1]}`;
  if (parts[0] === "packages" && parts[1]) return `packages/${parts[1]}`;
  if (parts[0] === "apps" && parts[1]) return `apps/${parts[1]}`;
  if (parts[0] === "src" && parts[1]) return `src/${parts[1]}`;
  if (parts[0] === "ui") return parts[1] === "src" && parts[2] ? `ui/${parts[2]}` : "ui";
  if (parts[0] === "scripts") return "scripts";
  if (parts[0] === "docs") return "docs";
  return parts[0] || "unknown";
}

function ensureSemanticBucket(map, name) {
  if (!map.has(name)) {
    map.set(name, {
      name,
      features: 0,
      contaminatedRefs: 0,
      kinds: {},
      sources: {},
      featureIds: [],
      ownedFiles: new Set(),
      entrypoints: new Set(),
      contextFiles: new Set(),
      testFiles: new Set(),
      representativeFeatures: [],
    });
  }
  return map.get(name);
}

function ensureSecurityBucket(map, name) {
  if (!map.has(name)) {
    map.set(name, {
      name,
      files: 0,
      candidates: 0,
      highRiskCandidates: 0,
      slugs: {},
      topFiles: [],
    });
  }
  return map.get(name);
}

function finalizeSemanticBucket(bucket) {
  const ownedFiles = sortedValues(bucket.ownedFiles);
  const entrypoints = sortedValues(bucket.entrypoints);
  const contextFiles = sortedValues(bucket.contextFiles);
  const testFiles = sortedValues(bucket.testFiles);
  return {
    name: bucket.name,
    features: bucket.features,
    ownedFileCount: ownedFiles.length,
    entrypointCount: entrypoints.length,
    contextFileCount: contextFiles.length,
    testFileCount: testFiles.length,
    contaminatedRefs: bucket.contaminatedRefs,
    featureIds: bucket.featureIds,
    topKinds: topEntries(bucket.kinds, 5),
    topSources: topEntries(bucket.sources, 5),
    representativeFeatures: bucket.representativeFeatures,
    sampleOwnedFiles: ownedFiles.slice(0, 20),
    sampleEntrypoints: entrypoints.slice(0, 12),
    sampleTestFiles: testFiles.slice(0, 12),
    semanticScore: bucket.features * 10 + entrypoints.length * 3 + ownedFiles.length + testFiles.length,
  };
}

function finalizeSecurityBucket(bucket) {
  bucket.topFiles.sort((a, b) => b.candidates - a.candidates || a.path.localeCompare(b.path));
  return {
    name: bucket.name,
    files: bucket.files,
    candidates: bucket.candidates,
    highRiskCandidates: bucket.highRiskCandidates,
    topSlugs: topEntries(bucket.slugs, 10),
    topFiles: bucket.topFiles.slice(0, 12),
    securityScore: bucket.highRiskCandidates * 5 + bucket.candidates + bucket.files * 2,
  };
}

function normalizeEvidence(records, semanticRows, kind) {
  const rows = new Map(semanticRows.map((bucket) => [bucket.name, { name: bucket.name, kind, count: 0, records: [] }]));
  for (const record of records) {
    const text = record.text.toLowerCase();
    for (const bucket of semanticRows) {
      if (!matchesBucket(text, bucket)) continue;
      const row = rows.get(bucket.name);
      row.count += 1;
      if (row.records.length < 8) {
        row.records.push({
          id: record.id,
          title: record.title,
          state: record.state,
          url: record.url,
          snippet: clip(record.text, 220),
        });
      }
    }
  }
  return [...rows.values()].sort((a, b) => b.count - a.count || a.name.localeCompare(b.name));
}

function matchesBucket(text, bucket) {
  const name = bucket.name.toLowerCase();
  if (name.includes("/") && text.includes(name)) return true;
  const parts = name
    .split("/")
    .filter((part) => part.length > 3 && !["apps", "docs", "src", "test", "tests"].includes(part));
  if (parts.some((part) => containsTerm(text, part))) return true;
  return [...bucket.sampleOwnedFiles, ...bucket.sampleEntrypoints]
    .slice(0, 20)
    .some((filePath) => text.includes(filePath.toLowerCase()));
}

function containsTerm(text, term) {
  return new RegExp(`(^|[^a-z0-9_-])${escapeRegExp(term)}([^a-z0-9_-]|$)`, "u").test(text);
}

function mergeBuckets(semanticRows, securityRows, issueRows, supportRows, developmentRows, ownershipRows) {
  const names = new Set([
    ...semanticRows.map((item) => item.name),
    ...securityRows.map((item) => item.name),
    ...issueRows.map((item) => item.name),
    ...supportRows.map((item) => item.name),
    ...developmentRows.map((item) => item.name),
    ...ownershipRows.map((item) => item.name),
  ]);
  const semanticByName = new Map(semanticRows.map((item) => [item.name, item]));
  const securityByName = new Map(securityRows.map((item) => [item.name, item]));
  const issueByName = new Map(issueRows.map((item) => [item.name, item]));
  const supportByName = new Map(supportRows.map((item) => [item.name, item]));
  const developmentByName = new Map(developmentRows.map((item) => [item.name, item]));
  const ownershipByName = new Map(ownershipRows.map((item) => [item.name, item]));
  return [...names]
    .map((name) => {
      const semantic = semanticByName.get(name);
      const security = securityByName.get(name);
      const issues = issueByName.get(name);
      const support = supportByName.get(name);
      const development = developmentByName.get(name);
      const ownership = ownershipByName.get(name);
      return {
        name,
        features: semantic?.features ?? 0,
        ownedFileCount: semantic?.ownedFileCount ?? 0,
        entrypointCount: semantic?.entrypointCount ?? 0,
        codeownerRules: ownership?.rules ?? 0,
        codeownerCount: ownership?.ownerCount ?? 0,
        trackedFiles: development?.trackedFiles ?? 0,
        codeFiles: development?.codeFiles ?? 0,
        testFiles: development?.testFiles ?? 0,
        docFiles: development?.docFiles ?? 0,
        churnEvents: development?.churnEvents ?? 0,
        churnFileCount: development?.churnFileCount ?? 0,
        testRatio: development?.testRatio ?? 0,
        testGap: development?.testGap ?? 0,
        deepsecFiles: security?.files ?? 0,
        deepsecCandidates: security?.candidates ?? 0,
        highRiskCandidates: security?.highRiskCandidates ?? 0,
        issueMatches: issues?.count ?? 0,
        supportMatches: support?.count ?? 0,
        semanticScore: semantic?.semanticScore ?? 0,
        ownershipScore: ownership?.ownershipScore ?? 0,
        developmentScore: development?.developmentScore ?? 0,
        securityScore: security?.securityScore ?? 0,
        combinedScore:
          (semantic?.semanticScore ?? 0) +
          (ownership?.ownershipScore ?? 0) * 5 +
          Math.round((development?.developmentScore ?? 0) / 20) +
          (security?.securityScore ?? 0) +
          (issues?.count ?? 0) * 10 +
          (support?.count ?? 0) * 6 -
          (semantic?.contaminatedRefs ?? 0),
      };
    })
    .sort((a, b) => b.combinedScore - a.combinedScore || a.name.localeCompare(b.name));
}

function enrichSemanticModel(rows, overlays) {
  const semanticByName = new Map(overlays.semanticRows.map((item) => [item.name, item]));
  const securityByName = new Map(overlays.securityRows.map((item) => [item.name, item]));
  const issueByName = new Map(overlays.issueRows.map((item) => [item.name, item]));
  const supportByName = new Map(overlays.supportRows.map((item) => [item.name, item]));
  const developmentByName = new Map(overlays.developmentRows.map((item) => [item.name, item]));
  const ownershipByName = new Map(overlays.ownershipRows.map((item) => [item.name, item]));
  const maxes = {
    security: max(rows, "securityScore"),
    development: max(rows, "developmentScore"),
    external: Math.max(...rows.map((item) => (item.issueMatches ?? 0) + (item.supportMatches ?? 0)), 1),
    semantic: max(rows, "semanticScore"),
    ownership: max(rows, "ownershipScore"),
    contamination: Math.max(...overlays.semanticRows.map((item) => item.contaminatedRefs ?? 0), 1),
  };

  const buckets = rows
    .map((row) => {
      const semantic = semanticByName.get(row.name);
      const security = securityByName.get(row.name);
      const issues = issueByName.get(row.name);
      const support = supportByName.get(row.name);
      const development = developmentByName.get(row.name);
      const ownership = ownershipByName.get(row.name);
      const impactBreakdown = buildImpactBreakdown(row, semantic, maxes);
      const evidenceConfidence = confidenceScore({ semantic, security, issues, support, development, ownership });
      const impactScore = clamp(
        Math.round(Object.values(impactBreakdown).reduce((total, value) => total + value, 0) + evidenceConfidence),
        0,
        100,
      );
      const tags = bucketTags(row, semantic, security, ownership);
      return {
        ...row,
        owners: ownership?.owners ?? [],
        topSlugs: security?.topSlugs ?? [],
        topFiles: security?.topFiles ?? [],
        issueRecords: issues?.records ?? [],
        supportRecords: support?.records ?? [],
        impactScore,
        impactBreakdown,
        confidenceScore: evidenceConfidence,
        action: actionFor(row),
        tags,
        searchText: bucketSearchText(row, semantic, security, ownership, tags),
      };
    })
    .sort((a, b) => b.impactScore - a.impactScore || b.combinedScore - a.combinedScore || a.name.localeCompare(b.name));

  return {
    buckets,
    treeNodes: buildTreeNodes(buckets),
    relatedEdges: buildRelatedEdges(buckets),
    savedViews: savedViews(),
  };
}

function buildImpactBreakdown(row, semantic, maxes) {
  const external = (row.issueMatches ?? 0) + (row.supportMatches ?? 0);
  const contaminationPenalty = pct(semantic?.contaminatedRefs ?? 0, maxes.contamination) * 5;
  return {
    security: Math.round(pct(row.securityScore, maxes.security) * 0.3),
    development: Math.round(pct(row.developmentScore, maxes.development) * 0.2),
    external: Math.round(pct(external, maxes.external) * 0.2),
    semantic: Math.round(pct(row.semanticScore, maxes.semantic) * 0.15),
    ownership: Math.round(pct(row.ownershipScore, maxes.ownership) * 0.1),
    contaminationPenalty: -Math.round(contaminationPenalty),
  };
}

function confidenceScore({ semantic, security, issues, support, development, ownership }) {
  const signals = [semantic, security, issues?.count > 0 ? issues : null, support?.count > 0 ? support : null, development, ownership].filter(Boolean)
    .length;
  return Math.min(5, signals);
}

function bucketTags(row, semantic, security, ownership) {
  const tags = [bucketGroup(row.name), actionLabel(actionFor(row))];
  if ((row.highRiskCandidates ?? 0) > 0) tags.push("security");
  if ((row.issueMatches ?? 0) > 0) tags.push("issues");
  if ((row.supportMatches ?? 0) > 0) tags.push("support");
  if ((row.churnEvents ?? 0) > 0) tags.push("churn");
  if ((semantic?.entrypointCount ?? 0) > 0) tags.push("entrypoints");
  for (const owner of ownership?.owners ?? []) tags.push(owner);
  for (const slug of security?.topSlugs?.slice(0, 4) ?? []) tags.push(slug.name);
  return [...new Set(tags)].sort((a, b) => a.localeCompare(b));
}

function bucketSearchText(row, semantic, security, ownership, tags) {
  return [
    row.name,
    row.action,
    ...tags,
    ...(ownership?.owners ?? []),
    ...(security?.topSlugs ?? []).map((item) => item.name),
    ...(semantic?.topKinds ?? []).map((item) => item.name),
    ...(semantic?.sampleOwnedFiles ?? []),
    ...(semantic?.sampleEntrypoints ?? []),
  ]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();
}

function buildTreeNodes(buckets) {
  const groups = new Map();
  for (const bucket of buckets) {
    const group = bucketGroup(bucket.name);
    if (!groups.has(group)) {
      groups.set(group, {
        id: `group:${group}`,
        name: group,
        depth: 0,
        children: [],
        impactScore: 0,
        sliceCount: 0,
      });
    }
    const node = groups.get(group);
    node.children.push(bucket.name);
    node.sliceCount += 1;
    node.impactScore = Math.max(node.impactScore, bucket.impactScore);
  }
  return [...groups.values()].sort((a, b) => b.impactScore - a.impactScore || a.name.localeCompare(b.name));
}

function buildRelatedEdges(buckets) {
  const edges = [];
  const rows = buckets.slice(0, 80);
  for (let leftIndex = 0; leftIndex < rows.length; leftIndex += 1) {
    for (let rightIndex = leftIndex + 1; rightIndex < rows.length; rightIndex += 1) {
      const edge = relatedEdge(rows[leftIndex], rows[rightIndex]);
      if (edge) edges.push(edge);
    }
  }
  return edges
    .sort((a, b) => b.weight - a.weight || a.source.localeCompare(b.source) || a.target.localeCompare(b.target))
    .slice(0, 240);
}

function relatedEdge(left, right) {
  const reasons = [];
  let weight = 0;
  if (bucketGroup(left.name) === bucketGroup(right.name)) {
    reasons.push("path");
    weight += 1;
  }
  const sharedOwners = intersect(left.owners, right.owners);
  if (sharedOwners.length > 0) {
    reasons.push("owner");
    weight += Math.min(3, sharedOwners.length);
  }
  const sharedSlugs = intersect(
    left.topSlugs.map((item) => item.name),
    right.topSlugs.map((item) => item.name),
  );
  if (sharedSlugs.length > 0) {
    reasons.push("slug");
    weight += Math.min(4, sharedSlugs.length);
  }
  if ((left.issueMatches > 0 && right.issueMatches > 0) || (left.supportMatches > 0 && right.supportMatches > 0)) {
    reasons.push("external");
    weight += 2;
  }
  if (weight < 2) return null;
  return { source: left.name, target: right.name, weight, reasons };
}

function savedViews() {
  return [
    { id: "core-impact", label: "Core Impact", query: "score:>60", sort: "impactScore" },
    { id: "security-hotspots", label: "Security Hotspots", query: "lens:security", sort: "securityScore" },
    { id: "external-pain", label: "External Pain", query: "external:>0", sort: "external" },
    { id: "high-churn", label: "High Churn", query: "churn:>5000", sort: "churnEvents" },
    { id: "owner-handoff", label: "Owner Handoff", query: "owner:*", sort: "ownershipScore" },
    { id: "regression-risk", label: "Regression Risk", query: "issue:>0 OR support:>0", sort: "impactScore" },
    { id: "map-only", label: "Map Only", query: "action:map", sort: "semanticScore" },
  ];
}

function renderHtml(summary) {
  const matrixRows = buildMatrixRows(summary).slice(0, 48);
  const handoff = buildAgentHandoff(summary);
  return `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>${escapeHtml(summary.title)}</title>
<style>
:root {
  --bg: #0d0b0b;
  --paper: #111010;
  --paper-2: #151211;
  --ink: #f4f1ef;
  --text: #b8afaa;
  --muted: #837b76;
  --line: #211d1b;
  --line-strong: #2d2825;
  --soft: #241915;
  --brand: #ff8a5f;
  --semantic: #48b49a;
  --development: #b58cff;
  --security: #ff6b5f;
  --issue: #d99036;
  --support: #7aa7ff;
  --shadow: 0 24px 80px rgba(0, 0, 0, .36);
  color-scheme: dark;
}
@media (prefers-color-scheme: light) {
  :root {
    --bg: #fbfaf7;
    --paper: #fffdfa;
    --paper-2: #fff8f2;
    --ink: #171514;
    --text: #443d39;
    --muted: #746b65;
    --line: #e8ddd5;
    --line-strong: #d9cbc2;
    --soft: #f6e9e1;
    --brand: #d75a37;
    --shadow: 0 20px 70px rgba(32, 24, 18, .10);
    color-scheme: light;
  }
}
* { box-sizing: border-box; }
html { scroll-behavior: smooth; scroll-padding-top: 82px; }
body { margin: 0; font: 14px/1.55 ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; color: var(--text); background: var(--bg); -webkit-font-smoothing: antialiased; }
button, input { font: inherit; color: inherit; }
button { cursor: pointer; }
main { max-width: 1500px; margin: 0 auto; padding: 30px 38px 72px; }
h1 { margin: 0; font-size: 32px; line-height: 1.08; color: var(--ink); }
h2 { margin: 34px 0 12px; font-size: 18px; color: var(--ink); }
h3 { margin: 0 0 10px; font-size: 13px; color: var(--ink); }
p { margin: 0; }
a { color: inherit; }
details { margin-top: 12px; }
summary { cursor: pointer; font-weight: 780; padding: 12px 0; color: var(--ink); }
summary::marker { color: var(--brand); }
.hero { display: grid; grid-template-columns: minmax(0, 1fr) 320px; gap: 28px; align-items: start; padding: 18px 0 20px; border-bottom: 1px solid var(--line); }
.eyebrow { margin-bottom: 8px; color: var(--brand); font-size: 12px; font-weight: 850; text-transform: uppercase; }
.note, .muted { color: var(--muted); }
.hero .note { max-width: 760px; margin-top: 10px; font-size: 15px; }
.run-meta { background: color-mix(in srgb, var(--paper) 90%, transparent); border: 1px solid var(--line-strong); border-radius: 8px; padding: 12px; box-shadow: var(--shadow); }
.run-meta div { display: flex; justify-content: space-between; gap: 12px; border-bottom: 1px solid var(--line); padding: 6px 0; }
.run-meta div:last-child { border-bottom: 0; }
.run-meta strong { color: var(--ink); }
.board-nav { position: sticky; top: 0; z-index: 5; display: flex; gap: 8px; flex-wrap: wrap; margin: 18px 0 22px; padding: 10px 0; background: color-mix(in srgb, var(--bg) 92%, transparent); backdrop-filter: blur(16px); border-bottom: 1px solid var(--line); }
.board-nav a { min-height: 34px; display: inline-flex; align-items: center; border: 1px solid var(--line-strong); border-radius: 8px; padding: 0 12px; color: var(--muted); text-decoration: none; background: color-mix(in srgb, var(--paper) 72%, transparent); }
.board-nav a:hover { color: var(--ink); border-color: color-mix(in srgb, var(--brand) 54%, var(--line-strong)); }
.scoreboard { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 10px; margin: 0 0 26px; }
.score { background: color-mix(in srgb, var(--paper) 90%, transparent); border: 1px solid var(--line-strong); border-radius: 8px; padding: 12px; }
.value { display: block; font-size: 24px; line-height: 1.1; font-weight: 820; color: var(--ink); }
.label { display: block; margin-top: 5px; color: var(--muted); }
.lane-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(218px, 1fr)); gap: 12px; }
.lane { background: color-mix(in srgb, var(--paper) 88%, transparent); border: 1px solid var(--line-strong); border-radius: 8px; padding: 14px; min-width: 0; }
.lane ol { margin: 0; padding-left: 20px; }
.lane li { margin: 9px 0; }
.lane code { display: block; margin-bottom: 2px; color: var(--ink); }
.grid2 { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
.review-workspace { display: grid; grid-template-columns: 310px minmax(0, 1fr); gap: 16px; align-items: start; margin-top: 14px; }
.slice-filter { position: sticky; top: 58px; max-height: calc(100vh - 78px); overflow: auto; border: 1px solid var(--line-strong); border-radius: 8px; background: color-mix(in srgb, var(--paper) 90%, transparent); }
.filter-head { padding: 13px 13px 11px; border-bottom: 1px solid var(--line); }
.filter-title { display: flex; justify-content: space-between; gap: 12px; align-items: baseline; margin-bottom: 9px; color: var(--ink); font-weight: 820; }
.filter-title span:last-child { color: var(--muted); font-size: 12px; font-weight: 680; }
.filter-search, .matrix-search { width: 100%; height: 34px; border: 1px solid var(--line-strong); border-radius: 8px; padding: 0 10px; background: color-mix(in srgb, var(--bg) 56%, var(--paper)); outline: none; }
.filter-search:focus, .matrix-search:focus { border-color: color-mix(in srgb, var(--brand) 58%, var(--line-strong)); }
.filter-panel { display: grid; gap: 16px; padding: 12px; }
.facet { display: grid; gap: 8px; }
.facet-title { display: flex; justify-content: space-between; gap: 10px; color: var(--ink); font-size: 12px; font-weight: 820; text-transform: uppercase; }
.facet-title span:last-child { color: var(--muted); font-weight: 650; text-transform: none; }
.filter-list { display: grid; gap: 5px; }
.filter-option { width: 100%; min-height: 34px; display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 8px; align-items: center; border: 1px solid transparent; border-radius: 8px; padding: 6px 8px; background: transparent; text-align: left; color: var(--text); }
.filter-option:hover { background: color-mix(in srgb, var(--paper-2) 70%, transparent); }
.filter-option.active { border-color: color-mix(in srgb, var(--brand) 52%, var(--line-strong)); background: color-mix(in srgb, var(--brand) 10%, var(--paper)); color: var(--ink); }
.filter-option strong, .filter-option code { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.filter-option small { color: var(--muted); font-size: 12px; white-space: nowrap; }
.system-summary { display: grid; gap: 1px; min-width: 0; }
.system-summary span { color: var(--muted); font-size: 12px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.matrix-workspace { min-width: 0; }
.section-head { display: grid; grid-template-columns: minmax(0, 1fr) minmax(360px, .8fr); gap: 16px; align-items: end; margin-bottom: 10px; }
.section-head h2 { margin-top: 0; }
.matrix-toolbar { display: grid; gap: 8px; }
.legend, .action-filters, .matrix-controls { display: flex; align-items: center; gap: 7px; flex-wrap: wrap; }
.legend-item, .filter-chip { display: inline-flex; align-items: center; min-height: 28px; border: 1px solid var(--line-strong); border-radius: 999px; padding: 0 9px; background: color-mix(in srgb, var(--paper) 76%, transparent); color: var(--muted); font-size: 12px; }
button.filter-chip { appearance: none; }
.filter-chip.active { color: var(--ink); border-color: color-mix(in srgb, var(--brand) 58%, var(--line-strong)); background: color-mix(in srgb, var(--brand) 12%, var(--paper)); }
.legend-swatch { width: 8px; height: 8px; border-radius: 999px; margin-right: 6px; }
table { width: 100%; border-collapse: collapse; background: color-mix(in srgb, var(--paper) 92%, transparent); border: 1px solid var(--line-strong); border-radius: 8px; overflow: hidden; }
.lens-table { table-layout: fixed; }
th, td { padding: 9px 10px; border-bottom: 1px solid var(--line); text-align: left; vertical-align: top; }
th { position: sticky; top: 53px; z-index: 2; background: var(--paper-2); font-size: 12px; text-transform: uppercase; color: var(--ink); }
tr:last-child td { border-bottom: 0; }
code, pre { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 12px; }
code { color: var(--ink); }
pre { margin: 0; padding: 14px; white-space: pre-wrap; background: #111010; color: #e7ded9; border: 1px solid var(--line-strong); border-radius: 8px; overflow: auto; box-shadow: var(--shadow); }
.path { width: 28%; }
.metric { width: 12%; }
.metric-main { color: var(--text); }
.metric-sub { margin-top: 2px; color: var(--muted); font-size: 12px; }
.heat { display: block; margin-top: 7px; }
.bar { display: block; height: 7px; background: color-mix(in srgb, var(--line-strong) 72%, transparent); border-radius: 999px; margin-top: 7px; overflow: hidden; }
.heat .bar { margin-top: 0; }
.bar span { display: block; height: 100%; border-radius: inherit; }
.heat-value { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; }
.tone-semantic { background: var(--semantic); }
.tone-development { background: var(--development); }
.tone-security { background: var(--security); }
.tone-issue { background: var(--issue); }
.tone-support { background: var(--support); }
.swatch-semantic { background: var(--semantic); }
.swatch-development { background: var(--development); }
.swatch-security { background: var(--security); }
.swatch-issue { background: var(--issue); }
.swatch-support { background: var(--support); }
.tag { display: inline-block; padding: 2px 6px; margin: 2px 3px 1px 0; border: 1px solid var(--line-strong); border-radius: 999px; background: color-mix(in srgb, var(--paper-2) 84%, transparent); color: var(--muted); font-size: 12px; }
.tag.hot { border-color: color-mix(in srgb, var(--security) 58%, var(--line-strong)); color: var(--security); }
.tag.warn { border-color: color-mix(in srgb, var(--issue) 54%, var(--line-strong)); color: var(--issue); }
.action { min-width: 84px; }
.action-mark { display: inline-flex; align-items: center; min-height: 24px; border: 1px solid var(--line-strong); border-radius: 999px; padding: 0 8px; color: var(--ink); background: color-mix(in srgb, var(--paper-2) 76%, transparent); font-size: 12px; font-weight: 780; white-space: nowrap; }
.action-stabilize { border-color: color-mix(in srgb, var(--issue) 60%, var(--line-strong)); }
.action-security-review { border-color: color-mix(in srgb, var(--security) 60%, var(--line-strong)); }
.action-refactor-prep { border-color: color-mix(in srgb, var(--development) 60%, var(--line-strong)); }
.action-architecture-pass { border-color: color-mix(in srgb, var(--semantic) 60%, var(--line-strong)); }
.action-docs-review { border-color: color-mix(in srgb, var(--support) 60%, var(--line-strong)); }
@media (max-width: 980px) {
  main { padding: 20px; }
  .hero, .grid2, .review-workspace, .section-head { grid-template-columns: 1fr; }
  .slice-filter { position: static; max-height: none; }
  .board-nav { position: static; }
  th { position: static; }
}
@media (max-width: 640px) {
  table { display: block; overflow-x: auto; }
}
</style>
</head>
<body>
<main>
<section class="hero">
<div>
<p class="eyebrow">semantic slicing</p>
<h1>${escapeHtml(summary.title)}</h1>
<p class="note">Internal development review board for code shape, churn, security pressure, issue history, and support signals.</p>
</div>
<div class="run-meta">
${metaRow("Generated", summary.generatedAt)}
${metaRow("Repo", summary.inputs.repo ? "yes" : "no")}
${metaRow("Churn", summary.inputs.churnSince)}
${metaRow("Clawpatch", summary.inputs.clawpatch ? "yes" : "no")}
${metaRow("Deepsec", summary.inputs.deepsec ? "yes" : "no")}
${metaRow("Gitcrawl", summary.inputs.gitcrawl ? "yes" : "no")}
${metaRow("Discrawl", summary.inputs.discrawl ? "yes" : "no")}
${metaRow("Sparse", summary.inputs.sparse ? `yes (${summary.inputs.sparseExcludes.length} rules)` : "no")}
</div>
</section>

<nav class="board-nav" aria-label="Semantic board sections">
<a href="#lanes">Lanes</a>
<a href="#explorer">Explorer</a>
<a href="#matrix">Matrix</a>
<a href="#handoff">Agent packet</a>
<a href="#evidence">Evidence</a>
</nav>

<section class="scoreboard" aria-label="Run totals">
${score("Semantic buckets", summary.totals.semanticBuckets)}
${score("Features", summary.totals.features)}
${score("Owner rules", summary.totals.codeownerRules)}
${score("Churn files", summary.totals.churnFiles)}
${score("Security candidates", summary.totals.deepsecCandidates)}
${score("Issue matches", summary.totals.issueMatches)}
${score("Support matches", summary.totals.supportMatches)}
</section>

<h2 id="lanes">Review Lanes</h2>
<section class="lane-grid" aria-label="Top review lanes">
${lane("Semantic shape", summary.normalizedQueues.semantic.slice(0, 6), (item) => `${item.features} features / ${item.ownedFileCount} files`)}
${lane("Ownership routing", summary.normalizedQueues.ownership.slice(0, 6), (item) => `${item.rules} rules / ${item.ownerCount} owners`)}
${lane("Development pressure", summary.normalizedQueues.development.slice(0, 6), (item) => `${item.churnFileCount} touched / ${item.churnEvents} events`)}
${lane("Security pressure", summary.normalizedQueues.security.slice(0, 6), (item) => `${item.highRiskCandidates} high risk / ${item.candidates} candidates`)}
${lane("Issue pressure", summary.normalizedQueues.issues.slice(0, 6), (item) => `${item.count} matched issue records`)}
${lane("Support pressure", summary.normalizedQueues.support.slice(0, 6), (item) => `${item.count} matched support records`)}
</section>

<section class="review-workspace" id="matrix">
<aside class="slice-filter" id="explorer" aria-label="Slice filters">
<div class="filter-head">
<div class="filter-title"><span>Focus</span><span>${matrixRows.length} slices</span></div>
<input class="filter-search" type="search" data-slice-search placeholder="Filter paths, owners, slugs">
</div>
${focusPanel(matrixRows)}
</aside>
<section class="matrix-workspace" aria-label="Overall lens matrix">
<div class="section-head">
<div>
<h2>Overall Lens Matrix</h2>
<p class="note">One row per semantic area. Bars compare each lens inside this run; actions are routing hints, not bug claims.</p>
</div>
${matrixToolbar(matrixRows)}
</div>
${lensMatrix(matrixRows)}
</section>
</section>

<h2 id="handoff">Agent Handoff Packet</h2>
<p class="note">Small, normalized, copyable payload for follow-up agents. Full data is in the sibling JSON artifact.</p>
<pre>${escapeHtml(JSON.stringify(handoff, null, 2))}</pre>

<h2 id="evidence">Evidence Tables</h2>
${detailsBlock("Semantic Buckets", semanticTable(summary.semanticBuckets.slice(0, 40)), true)}
${detailsBlock("Ownership Overlay", ownershipTable(summary.ownershipOverlay.slice(0, 40)), false)}
${detailsBlock("Development Overlay", developmentTable(summary.developmentOverlay.slice(0, 40)), false)}
${detailsBlock("Security Overlay", securityTable(summary.securityOverlay.filter((item) => item.candidates > 0).slice(0, 30)), false)}

<div class="grid2">
<section>
${detailsBlock("Normalized Issue Overlay", evidenceTable(summary.issueOverlay, "No gitcrawl JSON supplied."), false)}
</section>
<section>
${detailsBlock("Normalized Support Overlay", evidenceTable(summary.supportOverlay, "No discrawl JSON supplied."), false)}
</section>
</div>

${detailsBlock("Queue Summary", queueSummary(summary), false)}
${detailsBlock("Top Security Files", fileTable(summary.topFiles.slice(0, 50)), false)}
</main>
<script>${uiScript()}</script>
</body>
</html>`;
}

function buildMatrixRows(summary) {
  const semanticByName = new Map(summary.semanticBuckets.map((item) => [item.name, item]));
  const ownershipByName = new Map(summary.ownershipOverlay.map((item) => [item.name, item]));
  const developmentByName = new Map(summary.developmentOverlay.map((item) => [item.name, item]));
  const securityByName = new Map(summary.securityOverlay.map((item) => [item.name, item]));
  const issueByName = new Map(summary.issueOverlay.map((item) => [item.name, item]));
  const supportByName = new Map(summary.supportOverlay.map((item) => [item.name, item]));
  const rows = summary.buckets
    .map((bucket) => {
      const semantic = semanticByName.get(bucket.name);
      const ownership = ownershipByName.get(bucket.name);
      const development = developmentByName.get(bucket.name);
      const security = securityByName.get(bucket.name);
      const issue = issueByName.get(bucket.name);
      const support = supportByName.get(bucket.name);
      return {
        name: bucket.name,
        features: bucket.features,
        ownedFileCount: bucket.ownedFileCount,
        codeownerRules: bucket.codeownerRules,
        codeownerCount: bucket.codeownerCount,
        ownershipScore: bucket.ownershipScore,
        owners: ownership?.owners ?? [],
        trackedFiles: bucket.trackedFiles,
        codeFiles: bucket.codeFiles,
        testFiles: bucket.testFiles,
        churnEvents: bucket.churnEvents,
        churnFileCount: bucket.churnFileCount,
        testRatio: bucket.testRatio,
        testGap: bucket.testGap,
        highRiskCandidates: bucket.highRiskCandidates,
        deepsecCandidates: bucket.deepsecCandidates,
        issueMatches: bucket.issueMatches,
        supportMatches: bucket.supportMatches,
        semanticScore: bucket.semanticScore,
        developmentScore: bucket.developmentScore,
        securityScore: bucket.securityScore,
        combinedScore: bucket.combinedScore,
        kinds: semantic?.topKinds ?? [],
        slugs: security?.topSlugs ?? [],
        issueRecords: issue?.records ?? [],
        supportRecords: support?.records ?? [],
        action: actionFor(bucket),
      };
    })
    .filter(
      (row) =>
        row.features > 0 ||
        row.developmentScore > 0 ||
        row.deepsecCandidates > 0 ||
        row.issueMatches > 0 ||
        row.supportMatches > 0,
    );
  const maxSemantic = max(rows, "semanticScore");
  const maxOwnership = max(rows, "ownershipScore");
  const maxDevelopment = max(rows, "developmentScore");
  const maxSecurity = max(rows, "securityScore");
  const maxIssues = max(rows, "issueMatches");
  const maxSupport = max(rows, "supportMatches");
  return rows
    .map((row) => ({
      ...row,
      priorityScore:
        pct(row.semanticScore, maxSemantic) * 0.7 +
        pct(row.ownershipScore, maxOwnership) * 0.3 +
        pct(row.developmentScore, maxDevelopment) * 0.8 +
        pct(row.securityScore, maxSecurity) +
        pct(row.issueMatches, maxIssues) +
        pct(row.supportMatches, maxSupport),
    }))
    .sort((a, b) => b.priorityScore - a.priorityScore || b.combinedScore - a.combinedScore || a.name.localeCompare(b.name));
}

function buildAgentHandoff(summary) {
  return {
    generatedAt: summary.generatedAt,
    recommendation: "Review by lane: semantic shape first, then security, issue, and support overlays.",
    queues: {
      semantic: summary.normalizedQueues.semantic.slice(0, 8).map((item) => ({
        bucket: item.name,
        features: item.features,
        ownedFiles: item.ownedFileCount,
        entrypoints: item.entrypointCount,
      })),
      ownership: summary.normalizedQueues.ownership.slice(0, 8).map((item) => ({
        bucket: item.name,
        rules: item.rules,
        owners: item.owners,
        samplePatterns: item.samplePatterns,
      })),
      development: summary.normalizedQueues.development.slice(0, 8).map((item) => ({
        bucket: item.name,
        churnEvents: item.churnEvents,
        churnFiles: item.churnFileCount,
        codeFiles: item.codeFiles,
        testFiles: item.testFiles,
        testGap: item.testGap,
      })),
      security: summary.normalizedQueues.security.slice(0, 8).map((item) => ({
        bucket: item.name,
        highRiskCandidates: item.highRiskCandidates,
        candidates: item.candidates,
        slugs: item.topSlugs.slice(0, 5).map((slug) => slug.name),
      })),
      issues: summary.normalizedQueues.issues.slice(0, 8).map((item) => ({
        bucket: item.name,
        matches: item.count,
        evidence: item.records.map((record) => compactEvidence(record)),
      })),
      support: summary.normalizedQueues.support.slice(0, 8).map((item) => ({
        bucket: item.name,
        matches: item.count,
        evidence: item.records.map((record) => compactEvidence(record)),
      })),
    },
  };
}

function actionFor(bucket) {
  if (bucket.issueMatches >= 8 || bucket.supportMatches >= 30) return "Stabilize";
  if (bucket.highRiskCandidates > 0) return "Security review";
  if (bucket.docFiles > bucket.codeFiles && bucket.churnEvents > 0) return "Docs review";
  if (bucket.developmentScore >= 120) return "Refactor prep";
  if (bucket.features >= 20 || bucket.ownedFileCount >= 20) return "Architecture pass";
  if (bucket.issueMatches > 0 || bucket.supportMatches > 0) return "Triage";
  return "Map only";
}

function compactEvidence(record) {
  return {
    id: record.id,
    title: record.title,
    state: record.state,
    url: record.url,
  };
}

function lensMatrix(rows) {
  const maxSemantic = max(rows, "semanticScore");
  const maxDevelopment = max(rows, "developmentScore");
  const maxSecurity = max(rows, "securityScore");
  const maxIssues = max(rows, "issueMatches");
  const maxSupport = max(rows, "supportMatches");
  return `<table class="lens-table" data-matrix>
<colgroup>
<col style="width:28%">
<col style="width:12%">
<col style="width:13%">
<col style="width:20%">
<col style="width:9%">
<col style="width:9%">
<col style="width:9%">
</colgroup>
<thead><tr><th>Area</th><th>Semantic shape</th><th>Development</th><th>Security</th><th>Issues</th><th>Support</th><th>Action</th></tr></thead>
<tbody>
${rows.map((row) => `<tr id="${bucketId(row.name)}" data-row data-name="${escapeHtml(rowSearchText(row))}" data-action="${escapeHtml(actionClass(row.action))}" data-system="${escapeHtml(bucketGroup(row.name))}" data-lenses="${escapeHtml(rowLenses(row).join(" "))}">
<td class="path"><code>${escapeHtml(row.name)}</code><div class="muted">${pills(row.kinds.slice(0, 2))}${ownerTags(row.owners)}</div></td>
<td class="metric">${heatCell(`${row.features} features`, `${row.ownedFileCount} files`, row.semanticScore, maxSemantic, "semantic")}</td>
<td class="metric">${heatCell(`${row.churnFileCount} touched`, `${row.churnEvents} events`, row.developmentScore, maxDevelopment, "development", developmentTags(row))}</td>
<td class="metric">${heatCell(`${row.highRiskCandidates} high risk`, `${row.deepsecCandidates} candidates`, row.securityScore, maxSecurity, "security", pills(row.slugs.slice(0, 2), highRiskSlugs))}</td>
<td class="metric">${heatCell(`${row.issueMatches} matches`, "", row.issueMatches, maxIssues, "issue")}</td>
<td class="metric">${heatCell(`${row.supportMatches} matches`, "", row.supportMatches, maxSupport, "support")}</td>
<td class="action">${actionChip(row.action)}</td>
</tr>`).join("\n")}
</tbody>
</table>`;
}

function focusPanel(rows) {
  if (rows.length === 0) return `<p class="note">No semantic slices to filter.</p>`;
  return `<div class="filter-panel">
${lensFacet(rows)}
${systemFacet(rows)}
</div>`;
}

function lensFacet(rows) {
  const lenses = [
    ["all", "All lenses", rows.length],
    ["security", "Security pressure", rows.filter((row) => row.highRiskCandidates > 0 || row.deepsecCandidates > 0).length],
    ["issues", "Issue pressure", rows.filter((row) => row.issueMatches > 0).length],
    ["support", "Support pressure", rows.filter((row) => row.supportMatches > 0).length],
    ["development", "Development pressure", rows.filter((row) => row.churnFileCount > 0 || row.churnEvents > 0).length],
    ["semantic", "Semantic shape", rows.filter((row) => row.features > 0).length],
  ];
  return `<section class="facet" aria-label="Lens focus">
<div class="facet-title"><span>Lens focus</span><span>filter</span></div>
<div class="filter-list">
${lenses.map(([id, label, count], index) => `<button class="filter-option ${index === 0 ? "active" : ""}" type="button" data-lens-filter="${escapeHtml(id)}"><strong>${escapeHtml(label)}</strong><small>${count}</small></button>`).join("\n")}
</div>
</section>`;
}

function systemFacet(rows) {
  const groups = groupMatrixRows(rows);
  const allFeatures = sum(rows, "features");
  return `<section class="facet" aria-label="System scope">
<div class="facet-title"><span>Systems</span><span>scope</span></div>
<div class="filter-list" data-system-list>
<button class="filter-option active" type="button" data-system-filter="all">
<span class="system-summary"><strong>All systems</strong><span>${rows.length} slices / ${allFeatures} features</span></span>
<small>reset</small>
</button>
${groups.map((group) => systemOption(group)).join("\n")}
</div>
</section>`;
}

function systemOption(group) {
  const topActions = [...group.actionCounts.entries()]
    .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
    .slice(0, 1);
  const primaryAction = topActions[0]?.[0] ? actionLabel(topActions[0][0]) : "scope";
  return `<button class="filter-option" type="button" data-system-filter="${escapeHtml(group.label)}" data-name="${escapeHtml(groupSearchText(group))}">
<span class="system-summary">
<code>${escapeHtml(group.label)}</code>
<span>${group.rows.length} slices / ${group.rollup.features} features</span>
</span>
<small>${escapeHtml(primaryAction)}</small>
</button>`;
}

function groupSearchText(group) {
  return [
    group.label,
    ...group.rows.flatMap((row) => [row.name, ...row.owners, ...row.slugs.map((entry) => entry.name), row.action]),
  ]
    .join(" ")
    .toLowerCase();
}

function groupMatrixRows(rows) {
  const groups = new Map();
  for (const row of rows) {
    const label = bucketGroup(row.name);
    if (!groups.has(label)) groups.set(label, { label, rows: [] });
    groups.get(label).rows.push(row);
  }
  return [...groups.values()]
    .map((group) => {
      group.rows.sort((a, b) => b.priorityScore - a.priorityScore || a.name.localeCompare(b.name));
      return {
        ...group,
        rollup: aggregateRows(group.rows),
        actionCounts: countActions(group.rows),
      };
    })
    .sort((a, b) => b.rollup.priorityScore - a.rollup.priorityScore || a.label.localeCompare(b.label));
}

function aggregateRows(rows) {
  return {
    features: sum(rows, "features"),
    semanticScore: sum(rows, "semanticScore"),
    developmentScore: sum(rows, "developmentScore"),
    securityScore: sum(rows, "securityScore"),
    issueMatches: sum(rows, "issueMatches"),
    supportMatches: sum(rows, "supportMatches"),
    priorityScore: sum(rows, "priorityScore"),
  };
}

function countActions(rows) {
  const counts = new Map();
  for (const row of rows) counts.set(row.action, (counts.get(row.action) ?? 0) + 1);
  return counts;
}

function matrixToolbar(rows) {
  const counts = countActions(rows);
  return `<div class="matrix-toolbar">
<input class="matrix-search" type="search" data-matrix-search placeholder="Search paths, owners, slugs">
<div class="matrix-controls">
<div class="legend" aria-label="Lens legend">
${legendItem("semantic", "semantic")}
${legendItem("development", "development")}
${legendItem("security", "security")}
${legendItem("issue", "issues")}
${legendItem("support", "support")}
</div>
<div class="action-filters" aria-label="Action filters">
<button class="filter-chip active" type="button" data-action-filter="all">all ${rows.length}</button>
${[...counts.entries()].map(([action, count]) => `<button class="filter-chip action-${escapeHtml(actionClass(action))}" type="button" data-action-filter="${escapeHtml(actionClass(action))}">${escapeHtml(actionLabel(action))} ${count}</button>`).join("")}
</div>
</div>
</div>`;
}

function legendItem(tone, label) {
  return `<span class="legend-item"><span class="legend-swatch swatch-${tone}"></span>${escapeHtml(label)}</span>`;
}

function heatCell(primary, secondary, value, maxValue, tone, tags = "") {
  const heat = normalizedHeat(value, maxValue);
  const secondaryHtml = secondary ? `<div class="metric-sub">${escapeHtml(secondary)}</div>` : "";
  return `<div class="metric-main">${escapeHtml(primary)}</div>${secondaryHtml}${heatBar(heat, tone)}${tags ? `<div>${tags}</div>` : ""}`;
}

function actionClass(action) {
  return action.toLowerCase().replaceAll(" ", "-");
}

function actionLabel(action) {
  if (action === "Security review") return "security";
  if (action === "Architecture pass") return "architecture";
  if (action === "Refactor prep") return "refactor";
  if (action === "Docs review") return "docs";
  if (action === "Map only") return "map";
  return action.toLowerCase();
}

function actionChip(action) {
  return `<span class="action-mark action-${escapeHtml(actionClass(action))}">${escapeHtml(actionLabel(action))}</span>`;
}

function rowLenses(row) {
  const lenses = [];
  if (row.features > 0) lenses.push("semantic");
  if (row.churnFileCount > 0 || row.churnEvents > 0) lenses.push("development");
  if (row.highRiskCandidates > 0 || row.deepsecCandidates > 0) lenses.push("security");
  if (row.issueMatches > 0) lenses.push("issues");
  if (row.supportMatches > 0) lenses.push("support");
  return lenses;
}

function rowSearchText(row) {
  return [
    row.name,
    ...row.owners,
    ...row.kinds.map((entry) => entry.name),
    ...row.slugs.map((entry) => entry.name),
    row.action,
  ]
    .join(" ")
    .toLowerCase();
}

function bucketGroup(name) {
  const normalized = normalizePath(name);
  const [first] = normalized.split("/");
  if (!first) return "root";
  if (first === "extensions") return "extensions";
  if (first === "packages") return "packages";
  if (first === "src") return "src";
  if (first === "ui") return "ui";
  if (first === "apps") return "apps";
  if (first === "docs") return "docs";
  if (first === "scripts") return "scripts";
  if (first === ".github") return ".github";
  return first;
}

function bucketId(name) {
  return `bucket-${normalizePath(name).toLowerCase().replace(/[^a-z0-9]+/gu, "-").replace(/^-|-$/gu, "") || "root"}`;
}

function max(rows, key) {
  return Math.max(...rows.map((item) => item[key] ?? 0), 1);
}

function sum(rows, key) {
  return rows.reduce((total, item) => total + (item[key] ?? 0), 0);
}

function clamp(value, minValue, maxValue) {
  return Math.max(minValue, Math.min(maxValue, value));
}

function intersect(left, right) {
  const rightSet = new Set(right);
  return [...new Set(left)].filter((item) => rightSet.has(item));
}

function pct(value, maxValue) {
  return maxValue > 0 ? (value / maxValue) * 100 : 0;
}

function heatBar(heat, tone) {
  return `<span class="heat"><span class="bar" aria-hidden="true"><span class="tone-${tone}" style="width:${heat}%"></span></span><span class="heat-value">${heat}</span></span>`;
}

function uiScript() {
  return `(() => {
  const matrixSearch = document.querySelector("[data-matrix-search]");
  const sliceSearch = document.querySelector("[data-slice-search]");
  const actionButtons = [...document.querySelectorAll("[data-action-filter]")];
  const lensButtons = [...document.querySelectorAll("[data-lens-filter]")];
  const systemButtons = [...document.querySelectorAll("[data-system-filter]")];
  const rows = [...document.querySelectorAll("[data-row]")];
  let action = "all";
  let lens = "all";
  let system = "all";

  const terms = () => {
    const matrixTerm = matrixSearch?.value?.trim().toLowerCase() ?? "";
    const sliceTerm = sliceSearch?.value?.trim().toLowerCase() ?? "";
    return { matrixTerm, sliceTerm };
  };

  const matches = (element, term) => !term || (element.dataset.name ?? "").includes(term);
  const matchesAll = (element, queryTerms) => queryTerms.every((term) => matches(element, term));

  function applyFilters() {
    const { matrixTerm, sliceTerm } = terms();
    const queryTerms = [matrixTerm, sliceTerm].filter(Boolean);
    for (const button of actionButtons) button.classList.toggle("active", button.dataset.actionFilter === action);
    for (const button of lensButtons) button.classList.toggle("active", button.dataset.lensFilter === lens);
    for (const button of systemButtons) {
      const active = button.dataset.systemFilter === system;
      button.classList.toggle("active", active);
      button.hidden = Boolean(sliceTerm) && button.dataset.systemFilter !== "all" && !matches(button, sliceTerm);
    }
    for (const row of rows) {
      const actionMatch = action === "all" || row.dataset.action === action;
      const lensMatch = lens === "all" || (row.dataset.lenses ?? "").split(" ").includes(lens);
      const systemMatch = system === "all" || row.dataset.system === system;
      row.hidden = !actionMatch || !lensMatch || !systemMatch || !matchesAll(row, queryTerms);
    }
  }

  matrixSearch?.addEventListener("input", applyFilters);
  sliceSearch?.addEventListener("input", applyFilters);
  for (const button of actionButtons) {
    button.addEventListener("click", () => {
      action = button.dataset.actionFilter ?? "all";
      applyFilters();
    });
  }
  for (const button of lensButtons) {
    button.addEventListener("click", () => {
      lens = button.dataset.lensFilter ?? "all";
      applyFilters();
    });
  }
  for (const button of systemButtons) {
    button.addEventListener("click", () => {
      system = button.dataset.systemFilter ?? "all";
      applyFilters();
    });
  }
  applyFilters();
})();`;
}

function normalizedHeat(value, maxValue) {
  if (!value || !maxValue) return 0;
  return Math.max(3, Math.min(100, Math.round((value / maxValue) * 100)));
}

function developmentTags(row) {
  const tags = [];
  if (row.testGap > 0) tags.push({ name: `gap ${row.testGap}`, count: "" });
  if (row.trackedFiles > 0) tags.push({ name: `${row.trackedFiles} tracked`, count: "" });
  return tags.slice(0, 2).map((entry) => `<span class="tag warn">${escapeHtml(entry.name)}</span>`).join("");
}

function ownerTags(owners) {
  return owners.slice(0, 1).map((owner) => `<span class="tag">${escapeHtml(owner)}</span>`).join("");
}

function lane(title, rows, format) {
  const body = rows.length
    ? `<ol>${rows.map((item) => `<li><code>${escapeHtml(item.name)}</code><span class="muted">${escapeHtml(format(item))}</span></li>`).join("")}</ol>`
    : `<p class="note">No data for this lane.</p>`;
  return `<section class="lane"><h3>${escapeHtml(title)}</h3>${body}</section>`;
}

function detailsBlock(title, html, open) {
  return `<details ${open ? "open" : ""}><summary>${escapeHtml(title)}</summary>${html}</details>`;
}

function semanticTable(rows) {
  return `<table>
<thead><tr><th>Bucket</th><th>Features</th><th>Owned files</th><th>Entrypoints</th><th>Tests</th><th>Kinds</th><th>Sample features</th></tr></thead>
<tbody>
${rows.map((bucket) => `<tr><td><code>${escapeHtml(bucket.name)}</code></td><td>${bucket.features}</td><td>${bucket.ownedFileCount}</td><td>${bucket.entrypointCount}</td><td>${bucket.testFileCount}</td><td>${pills(bucket.topKinds)}</td><td>${bucket.representativeFeatures.map((feature) => `<span class="tag">${escapeHtml(feature.featureId ?? feature.title ?? "feature")}</span>`).join("")}</td></tr>`).join("\n")}
</tbody>
</table>`;
}

function ownershipTable(rows) {
  if (rows.length === 0) return `<p class="note">No CODEOWNERS overlay supplied.</p>`;
  return `<table>
<thead><tr><th>Bucket</th><th>Rules</th><th>Owners</th><th>Sample patterns</th></tr></thead>
<tbody>
${rows.map((bucket) => `<tr><td><code>${escapeHtml(bucket.name)}</code></td><td>${bucket.rules}</td><td>${bucket.owners.map((owner) => `<span class="tag">${escapeHtml(owner)}</span>`).join("")}</td><td>${bucket.samplePatterns.map((pattern) => `<code>${escapeHtml(pattern)}</code>`).join("<br>")}</td></tr>`).join("\n")}
</tbody>
</table>`;
}

function securityTable(rows) {
  if (rows.length === 0) return `<p class="note">No deepsec data supplied.</p>`;
  return `<table>
<thead><tr><th>Bucket</th><th>Files</th><th>Candidates</th><th>High risk</th><th>Top slugs</th></tr></thead>
<tbody>
${rows.map((bucket) => `<tr><td><code>${escapeHtml(bucket.name)}</code></td><td>${bucket.files}</td><td>${bucket.candidates}</td><td>${hot(bucket.highRiskCandidates)}</td><td>${pills(bucket.topSlugs, highRiskSlugs)}</td></tr>`).join("\n")}
</tbody>
</table>`;
}

function developmentTable(rows) {
  if (rows.length === 0) return `<p class="note">No repo git overlay supplied.</p>`;
  return `<table>
<thead><tr><th>Bucket</th><th>Tracked</th><th>Code</th><th>Tests</th><th>Docs</th><th>90d churn</th><th>Test gap</th></tr></thead>
<tbody>
${rows.map((bucket) => `<tr><td><code>${escapeHtml(bucket.name)}</code></td><td>${bucket.trackedFiles}</td><td>${bucket.codeFiles}</td><td>${bucket.testFiles}</td><td>${bucket.docFiles}</td><td>${bucket.churnEvents} / ${bucket.churnFileCount} files</td><td>${bucket.testGap}</td></tr>`).join("\n")}
</tbody>
</table>`;
}

function evidenceTable(rows, emptyText) {
  const hits = rows.filter((row) => row.count > 0).slice(0, 20);
  if (hits.length === 0) return `<p class="note">${escapeHtml(emptyText)}</p>`;
  return `<table>
<thead><tr><th>Bucket</th><th>Matches</th><th>Evidence</th></tr></thead>
<tbody>
${hits.map((row) => `<tr><td><code>${escapeHtml(row.name)}</code></td><td>${row.count}</td><td>${row.records.map((record) => `<div><span class="tag">${escapeHtml(record.state ?? record.id ?? "record")}</span> ${escapeHtml(record.title ?? record.id ?? "record")}</div>`).join("")}</td></tr>`).join("\n")}
</tbody>
</table>`;
}

function queueSummary(summary) {
  return `<table>
<thead><tr><th>Queue</th><th>Top buckets</th></tr></thead>
<tbody>
${queueRow("semantic", summary.normalizedQueues.semantic, "features")}
${queueRow("ownership", summary.normalizedQueues.ownership, "rules")}
${queueRow("development", summary.normalizedQueues.development, "churnEvents")}
${queueRow("security", summary.normalizedQueues.security, "highRiskCandidates")}
${queueRow("issues", summary.normalizedQueues.issues, "count")}
${queueRow("support", summary.normalizedQueues.support, "count")}
</tbody>
</table>`;
}

function queueRow(name, rows, metric) {
  const label = rows.length ? rows.slice(0, 8).map((row) => `<span class="tag">${escapeHtml(row.name)} ${row[metric] ?? ""}</span>`).join("") : `<span class="note">no matches</span>`;
  return `<tr><td>${escapeHtml(name)}</td><td>${label}</td></tr>`;
}

function fileTable(files) {
  return `<table>
<thead><tr><th>File</th><th>Bucket</th><th>Candidates</th><th>Slugs</th></tr></thead>
<tbody>
${files.map((file) => `<tr><td><code>${escapeHtml(file.path)}</code></td><td><code>${escapeHtml(file.bucket)}</code></td><td>${file.candidates}</td><td>${file.slugs.map((slug) => `<span class="tag ${highRiskSlugs.has(slug) ? "hot" : ""}">${escapeHtml(slug)}</span>`).join("")}</td></tr>`).join("\n")}
</tbody>
</table>`;
}

function score(label, value) {
  return `<div class="score"><span class="value">${Number(value).toLocaleString()}</span><span class="label">${escapeHtml(label)}</span></div>`;
}

function metaRow(label, value) {
  return `<div><span class="muted">${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong></div>`;
}

function pills(entries, hotSet = new Set()) {
  return entries
    .map((entry) => `<span class="tag ${hotSet.has(entry.name) ? "hot" : ""}">${escapeHtml(entry.name)} ${entry.count}</span>`)
    .join("");
}

function hot(value) {
  return `<span class="tag ${value > 0 ? "hot" : ""}">${value}</span>`;
}

function addPaths(set, values) {
  for (const value of values) {
    if (!isContaminated(value) && isReviewPath(value)) set.add(value);
  }
}

function isContaminated(filePath) {
  const normalized = normalizePath(filePath);
  return contaminationPrefixes.some((prefix) => normalized === prefix.slice(0, -1) || normalized.startsWith(prefix));
}

function isReviewPath(filePath) {
  if (!sparseConfig.enabled) return true;
  const normalized = normalizePath(filePath);
  if (sparseConfig.includes.some((rule) => matchesSparseRule(normalized, rule))) return true;
  return !sparseConfig.excludes.some((rule) => matchesSparseRule(normalized, rule));
}

function isReviewBucket(bucketName) {
  if (!sparseConfig.enabled) return true;
  const normalized = normalizePath(bucketName);
  if (sparseConfig.includes.some((rule) => matchesSparseRule(normalized, rule))) return true;
  return !sparseConfig.excludes.some((rule) => matchesSparseRule(normalized, rule));
}

function matchesSparseRule(filePath, rule) {
  const normalizedPath = normalizePath(filePath).toLowerCase();
  const normalizedRule = normalizePath(rule).toLowerCase();
  if (!normalizedRule) return false;
  if (normalizedRule.endsWith("/")) {
    const prefix = normalizedRule.slice(0, -1);
    return normalizedPath === prefix || normalizedPath.startsWith(normalizedRule);
  }
  if (!normalizedRule.includes("/") && path.posix.basename(normalizedPath) === normalizedRule) return true;
  return normalizedPath === normalizedRule || normalizedPath.startsWith(`${normalizedRule}/`);
}

function normalizePath(filePath) {
  return String(filePath).replaceAll("\\", "/").replace(/^\.?\//u, "");
}

function isTestPath(filePath) {
  return /(^|\/)(test|tests|__tests__|fixtures?)(\/|$)|\.(test|spec|e2e)\.[cm]?[jt]sx?$/u.test(filePath);
}

function isDocPath(filePath) {
  return filePath.startsWith("docs/") || /\.(md|mdx|rst|adoc)$/u.test(filePath);
}

function isSourcePath(filePath) {
  return /\.(mjs|cjs|js|jsx|ts|tsx|go|rs|py|swift|kt|java|rb|php|cs|c|cc|cpp|h|hpp|sh)$/u.test(filePath);
}

function sortedValues(set) {
  return [...set].sort((a, b) => a.localeCompare(b));
}

function topEntries(object, limit) {
  return Object.entries(object)
    .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
    .slice(0, limit)
    .map(([name, count]) => ({ name, count }));
}

function bump(object, key) {
  object[key] = (object[key] ?? 0) + 1;
}

function stringOrNull(value) {
  if (value == null) return null;
  const text = String(value).trim();
  return text ? text : null;
}

function clip(value, limit) {
  const text = String(value).replace(/\s+/g, " ").trim();
  return text.length > limit ? `${text.slice(0, limit - 3)}...` : text;
}

function shortLabel(value, limit) {
  return value.length > limit ? `${value.slice(0, limit - 3)}...` : value;
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function escapeRegExp(value) {
  return String(value).replace(/[.*+?^${}()|[\]\\]/gu, "\\$&");
}

function die(message) {
  console.error(message);
  process.exit(2);
}
