#!/usr/bin/env node
import fs from "node:fs";
import path from "node:path";

const args = parseArgs(process.argv.slice(2));
if (!args.clawpatch && !args.deepsec) {
  die("usage: semantic-map.mjs --clawpatch <state-dir> --deepsec <data/project> --out <semantic-map.html>");
}

const outPath = args.out ?? path.resolve(process.cwd(), "semantic-map.html");
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

const features = args.clawpatch ? readClawpatchFeatures(args.clawpatch) : [];
const deepsecFiles = args.deepsec ? readDeepsecFiles(args.deepsec) : [];
const buckets = new Map();
const slugCounts = new Map();
const topFiles = [];

for (const feature of features) {
  const refs = [
    ...(feature.ownedFiles ?? []),
    ...(feature.entrypoints ?? []),
    ...(feature.contextFiles ?? []),
  ].map((item) => item.path).filter(Boolean);
  const contaminated = refs.filter(isContaminated);
  const cleanRefs = refs.filter((item) => !isContaminated(item));
  if (cleanRefs.length === 0 && contaminated.length > 0) continue;
  const bucket = bucketFor(preferredFeaturePath(feature, cleanRefs));
  const record = ensureBucket(buckets, bucket);
  record.features += 1;
  record.kinds[feature.kind ?? "unknown"] = (record.kinds[feature.kind ?? "unknown"] ?? 0) + 1;
  record.sources[feature.source ?? "unknown"] = (record.sources[feature.source ?? "unknown"] ?? 0) + 1;
  record.contaminatedRefs += contaminated.length;
  if (feature.featureId && record.featureIds.length < 12) record.featureIds.push(feature.featureId);
}

for (const file of deepsecFiles) {
  if (isContaminated(file.filePath)) continue;
  const candidates = Array.isArray(file.candidates) ? file.candidates : [];
  if (candidates.length === 0) continue;
  const bucket = bucketFor(file.filePath);
  const record = ensureBucket(buckets, bucket);
  record.deepsecFiles += 1;
  record.deepsecCandidates += candidates.length;
  for (const candidate of candidates) {
    const slug = candidate.vulnSlug ?? candidate.slug ?? "unknown";
    record.slugs[slug] = (record.slugs[slug] ?? 0) + 1;
    slugCounts.set(slug, (slugCounts.get(slug) ?? 0) + 1);
  }
  topFiles.push({
    path: file.filePath,
    bucket,
    candidates: candidates.length,
    slugs: [...new Set(candidates.map((item) => item.vulnSlug ?? item.slug ?? "unknown"))].slice(0, 8),
  });
}

const bucketRows = [...buckets.values()]
  .map((bucket) => ({
    ...bucket,
    score: bucket.features + bucket.deepsecCandidates + bucket.deepsecFiles * 3 - bucket.contaminatedRefs,
    topSlugs: topEntries(bucket.slugs, 8),
    topKinds: topEntries(bucket.kinds, 5),
    topSources: topEntries(bucket.sources, 5),
  }))
  .sort((a, b) => b.score - a.score || b.deepsecCandidates - a.deepsecCandidates || a.name.localeCompare(b.name));

topFiles.sort((a, b) => b.candidates - a.candidates || a.path.localeCompare(b.path));

const summary = {
  generatedAt: new Date().toISOString(),
  inputs: {
    clawpatch: args.clawpatch ?? null,
    deepsec: args.deepsec ?? null,
  },
  totals: {
    buckets: bucketRows.length,
    features: bucketRows.reduce((sum, item) => sum + item.features, 0),
    deepsecFiles: bucketRows.reduce((sum, item) => sum + item.deepsecFiles, 0),
    deepsecCandidates: bucketRows.reduce((sum, item) => sum + item.deepsecCandidates, 0),
    contaminatedRefs: bucketRows.reduce((sum, item) => sum + item.contaminatedRefs, 0),
  },
  topSlugs: topEntries(Object.fromEntries(slugCounts), 20),
  buckets: bucketRows,
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
    const value = argv[index + 1];
    if (!value || value.startsWith("--")) die(`missing value for ${arg}`);
    out[key] = value;
    index += 1;
  }
  return out;
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

function bucketFor(filePath) {
  const normalized = String(filePath).replaceAll("\\", "/").replace(/^\.?\//u, "");
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

function ensureBucket(map, name) {
  if (!map.has(name)) {
    map.set(name, {
      name,
      features: 0,
      deepsecFiles: 0,
      deepsecCandidates: 0,
      contaminatedRefs: 0,
      kinds: {},
      sources: {},
      slugs: {},
      featureIds: [],
    });
  }
  return map.get(name);
}

function isContaminated(filePath) {
  const normalized = String(filePath).replaceAll("\\", "/").replace(/^\.?\//u, "");
  return contaminationPrefixes.some((prefix) => normalized === prefix.slice(0, -1) || normalized.startsWith(prefix));
}

function topEntries(object, limit) {
  return Object.entries(object)
    .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
    .slice(0, limit)
    .map(([name, count]) => ({ name, count }));
}

function renderHtml(summary) {
  const maxScore = Math.max(...summary.buckets.map((item) => item.score), 1);
  const nodes = summary.buckets.slice(0, 32).map((bucket, index) => {
    const col = index % 8;
    const row = Math.floor(index / 8);
    const radius = 18 + Math.round((bucket.score / maxScore) * 34);
    return {
      ...bucket,
      x: 70 + col * 135,
      y: 75 + row * 125,
      radius,
    };
  });
  const width = 1080;
  const height = Math.max(260, 135 + Math.ceil(nodes.length / 8) * 125);
  return `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Semantic Slice Map</title>
<style>
body { margin: 0; font: 14px/1.45 ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; color: #17202a; background: #f7f5ef; }
main { max-width: 1180px; margin: 0 auto; padding: 28px; }
h1 { margin: 0 0 6px; font-size: 28px; }
h2 { margin: 28px 0 10px; font-size: 18px; }
.meta { color: #5f6b77; }
.cards { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 10px; margin: 18px 0 24px; }
.card { background: #fff; border: 1px solid #ddd7ca; border-radius: 8px; padding: 12px; }
.value { display: block; font-size: 24px; font-weight: 700; color: #0f172a; }
.label { color: #5f6b77; }
svg { width: 100%; height: auto; background: #fff; border: 1px solid #ddd7ca; border-radius: 8px; }
.node { fill: #2f6f73; opacity: .86; }
.node.hot { fill: #a33d2d; }
.node.mid { fill: #b5792e; }
.nodeText { fill: #111827; font-size: 12px; font-weight: 650; text-anchor: middle; }
.nodeSub { fill: #344054; font-size: 11px; text-anchor: middle; }
table { width: 100%; border-collapse: collapse; background: #fff; border: 1px solid #ddd7ca; border-radius: 8px; overflow: hidden; }
th, td { padding: 8px 10px; border-bottom: 1px solid #ece6d9; text-align: left; vertical-align: top; }
th { background: #ebe4d6; font-size: 12px; text-transform: uppercase; letter-spacing: .04em; color: #344054; }
tr:last-child td { border-bottom: 0; }
code { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 12px; }
.pill { display: inline-block; padding: 2px 6px; margin: 1px 3px 1px 0; border-radius: 999px; background: #eef2f7; color: #344054; font-size: 12px; }
</style>
</head>
<body>
<main>
<h1>Semantic Slice Map</h1>
<div class="meta">Generated ${escapeHtml(summary.generatedAt)}</div>
<div class="cards">
${card("Buckets", summary.totals.buckets)}
${card("Features", summary.totals.features)}
${card("Deepsec files", summary.totals.deepsecFiles)}
${card("Candidates", summary.totals.deepsecCandidates)}
</div>
<h2>Review Map</h2>
<svg viewBox="0 0 ${width} ${height}" role="img" aria-label="Semantic slice bubble map">
${nodes.map((node) => `<circle class="node ${node.deepsecCandidates > 500 ? "hot" : node.deepsecCandidates > 100 ? "mid" : ""}" cx="${node.x}" cy="${node.y}" r="${node.radius}"><title>${escapeHtml(node.name)}: score ${node.score}, features ${node.features}, candidates ${node.deepsecCandidates}</title></circle>
<text class="nodeText" x="${node.x}" y="${node.y - 4}">${escapeHtml(shortLabel(node.name, 18))}</text>
<text class="nodeSub" x="${node.x}" y="${node.y + 13}">${node.features}f / ${node.deepsecCandidates}c</text>`).join("\n")}
</svg>
<h2>Top Buckets</h2>
<table>
<thead><tr><th>Bucket</th><th>Score</th><th>Features</th><th>Files</th><th>Candidates</th><th>Top slugs</th></tr></thead>
<tbody>
${summary.buckets.slice(0, 40).map((bucket) => `<tr><td><code>${escapeHtml(bucket.name)}</code></td><td>${bucket.score}</td><td>${bucket.features}</td><td>${bucket.deepsecFiles}</td><td>${bucket.deepsecCandidates}</td><td>${pills(bucket.topSlugs)}</td></tr>`).join("\n")}
</tbody>
</table>
<h2>Top Files</h2>
<table>
<thead><tr><th>File</th><th>Bucket</th><th>Candidates</th><th>Slugs</th></tr></thead>
<tbody>
${summary.topFiles.slice(0, 50).map((file) => `<tr><td><code>${escapeHtml(file.path)}</code></td><td><code>${escapeHtml(file.bucket)}</code></td><td>${file.candidates}</td><td>${file.slugs.map((slug) => `<span class="pill">${escapeHtml(slug)}</span>`).join("")}</td></tr>`).join("\n")}
</tbody>
</table>
</main>
</body>
</html>`;
}

function card(label, value) {
  return `<div class="card"><span class="value">${Number(value).toLocaleString()}</span><span class="label">${escapeHtml(label)}</span></div>`;
}

function pills(entries) {
  return entries.map((entry) => `<span class="pill">${escapeHtml(entry.name)} ${entry.count}</span>`).join("");
}

function shortLabel(value, limit) {
  return value.length > limit ? `${value.slice(0, limit - 1)}…` : value;
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function die(message) {
  console.error(message);
  process.exit(2);
}
