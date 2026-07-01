#!/usr/bin/env node

import fs from "node:fs";

const DEFAULT_MAINTAINERS = new Set([
  "vincentkoc",
  "takhoffman",
  "gumadeiras",
  "obviyus",
  "shakkernerd",
  "mbelinky",
  "joshavant",
  "ngutman",
  "vignesh07",
  "huntharo",
  "thewilloftheshadow",
  "onutc",
  "osolmaz",
  "jacobtomlinson",
  "tyler6204",
  "velvet-shark",
  "jalehman",
  "frankekn",
  "imlukef",
  "mcaxtr",
  "steipete",
]);
const MAINTAINER_ASSOCIATIONS = new Set(["OWNER", "MEMBER", "COLLABORATOR"]);

const HARD_RISK =
  /\b(security|ssrf|xss|csrf|rce|auth(?:entication|n|z)?|oauth|authori[sz](?:e|ation|ed)|tokens?|secrets?|credentials?|proxy|redact(?:ion)?|chmod|permissions?|sandbox|pairing|approvals?|authorized[- ]sender|account[- ]bound|trust[- ]boundary|config(?:uration)?|migration|migrate|compatibility|session[- ]state|message[- ]delivery|auth[- ]provider|security[- ]boundary|release|workflow|codeql|dependabot)\b/i;
const UI_RISK =
  /\b(ui|control ui|web[- ]?ui|frontend|visual|translation|i18n|android|ios|camera|scrolling|layout|css)\b/i;
const HIGH_RISK_PATH =
  /^(?:\.github\/|ui\/|apps\/|packages\/(?:gateway-protocol|plugin-sdk)\/|src\/plugin-sdk\/|scripts\/release)|(?:^|[\/._-])(?:auth(?:entication|n|z|orize|orization)?|authori[sz](?:e|ation|ed)|oauth|tokens?|secrets?|credentials?|redact(?:ion)?|chmod|permissions?|approvals?|security|ssrf|xss|csrf|rce|proxy|sandbox|pairing|account-bound|trust-boundary|config(?:uration)?|migrations?|compat(?:ibility)?|legacy|session-state|message-delivery|auth-provider|release|workflow|codeql|dependabot)(?:[._/-]|$)|(?:^|\/)(?:package\.json|pnpm-lock\.yaml|bun\.lock)$/i;
const UI_PATH =
  /^(?:apps)(?:\/|$)|(?:^|[\/._-])(?:ui|control-ui|frontend|web-ui|locales?|translations?)(?:[\/._-]|$)|\.(?:css|scss|sass|less|tsx|jsx|vue|svelte)$/i;
const LOW_SIGNAL_TITLE =
  /^(?:test|docs|chore|refactor|style|i18n)(?:\([^)]*\))?:|\b(typo|rename|formatting|lint|coverage|unit tests?|add tests?|object\.hasown|clear timeout timer|user[- ]agent|logging?|warning when|close readline|destroy read stream|allow always|one-shot command|dangling surrogate)\b/i;
const ODD_MICRO_TITLE =
  /\b(?:add|clear|close|destroy|guard|rename|replace|switch|use)\b.{0,40}\b(?:header|literal|log(?:ging)?|null check|object\.hasown|optional chaining|timer|timeout|user[- ]agent|warning)\b/i;
const FEATURE_TITLE = /^(?:feat|feature)(?:\([^)]*\))?:/i;
const TEST_PATH =
  /(?:^|\/)(?:test|tests|__tests__|__snapshots__)(?:\/|$)|\.(?:test|spec)\.[^.]+$|\.snap$/i;
const DOC_PATH = /^(?:docs\/|README(?:\.|$)|CHANGELOG\.md$)|\.md$/i;
const ROUTINE_CHECK =
  /\b(auto[- ]?response|labeler|backfill-pr-labels|docs agent|performance|stale bot)\b/i;

const args = process.argv.slice(2);
let inputPath = "";
let decisionLedgerPath = "";
let limit = 40;
let batchSize = 20;
let requireHydrated = false;
const explicitSkips = new Set();

function parsePrNumber(value) {
  const trimmed = value.trim();
  if (!trimmed) return null;

  const match = trimmed.match(/(?:^|\/pull\/|#)(\d+)(?:\/)?$/);
  if (!match && !/^\d+$/.test(trimmed)) return null;
  const number = Number.parseInt(match?.[1] ?? trimmed, 10);
  return Number.isInteger(number) && number > 0 ? number : null;
}

for (let index = 0; index < args.length; index += 1) {
  const arg = args[index];
  if (arg === "--input") {
    inputPath = args[++index] ?? "";
  } else if (arg === "--decision-ledger") {
    decisionLedgerPath = args[++index] ?? "";
  } else if (arg === "--limit") {
    limit = Number.parseInt(args[++index] ?? "40", 10);
  } else if (arg === "--batch-size") {
    batchSize = Number.parseInt(args[++index] ?? "20", 10);
  } else if (arg === "--exclude") {
    for (const value of (args[++index] ?? "").split(",")) {
      const number = parsePrNumber(value);
      if (!value.trim()) continue;
      if (number === null) throw new Error(`Invalid --exclude PR reference: ${value}`);
      explicitSkips.add(number);
    }
  } else if (arg === "--hydrated") {
    requireHydrated = true;
  } else if (arg === "--help") {
    console.log(
      "Usage: rank-candidates.mjs [--input prs.json] [--decision-ledger ledger.json] [--limit 40] [--batch-size 20] [--exclude 123,456] [--hydrated]",
    );
    process.exit(0);
  } else {
    throw new Error(`Unknown argument: ${arg}`);
  }
}

if (decisionLedgerPath) {
  const ledger = JSON.parse(fs.readFileSync(decisionLedgerPath, "utf8"));
  for (const key of ["explicitSkips", "landed", "closed", "rejected", "ignored"]) {
    const entries = ledger[key] ?? [];
    if (!Array.isArray(entries)) {
      throw new Error(`Decision ledger field ${key} must be an array`);
    }
    for (const entry of entries) {
      const value =
        typeof entry === "object" && entry !== null
          ? (entry.number ?? entry.ref ?? entry.url ?? "")
          : entry;
      const number = parsePrNumber(String(value));
      if (number === null) {
        throw new Error(`Invalid decision ledger PR reference in ${key}: ${String(value)}`);
      }
      explicitSkips.add(number);
    }
  }
}

if (!Number.isInteger(limit) || limit < 1 || limit > 100) {
  throw new Error("--limit must be an integer from 1 to 100");
}
if (!Number.isInteger(batchSize) || batchSize < 1 || batchSize > 20) {
  throw new Error("--batch-size must be an integer from 1 to 20");
}

const input = inputPath ? fs.readFileSync(inputPath, "utf8") : fs.readFileSync(0, "utf8");
const prs = JSON.parse(input);
if (!Array.isArray(prs)) {
  throw new Error("Expected a JSON array of pull requests");
}
const uniquePrs = [
  ...new Map(
    prs.map((pr) => {
      const number = Number(pr.number);
      if (!Number.isInteger(number) || number < 1) {
        throw new Error(`Expected a positive PR number, received: ${String(pr.number)}`);
      }
      return [number, pr];
    }),
  ).values(),
];

function labelNames(pr) {
  return (pr.labels ?? []).map((label) => (typeof label === "string" ? label : label.name));
}

function changedFiles(pr) {
  return Array.isArray(pr.files) ? pr.files : [];
}

function filePath(file) {
  return typeof file === "string" ? file : (file.path ?? file.filename ?? "");
}

function normalizedRiskPath(path) {
  return path
    .replace(/([A-Z]+)([A-Z][a-z])/g, "$1-$2")
    .replace(/([a-z0-9])([A-Z])/g, "$1-$2")
    .toLowerCase();
}

function hasFileDelta(file) {
  return (
    typeof file !== "string" &&
    Number.isFinite(file.additions) &&
    Number.isFinite(file.deletions)
  );
}

function checkEntries(pr) {
  const rollup = pr.statusCheckRollup ?? pr.status_check_rollup ?? pr.checks ?? [];
  if (Array.isArray(rollup)) return rollup;
  if (Array.isArray(rollup.contexts?.nodes)) return rollup.contexts.nodes;
  return [];
}

function hasValidCheckRollup(pr) {
  const rollup = pr.statusCheckRollup ?? pr.status_check_rollup ?? pr.checks;
  return Array.isArray(rollup) || Array.isArray(rollup?.contexts?.nodes);
}

function isRoutineCheck(check) {
  const workflow = check.workflowName ?? check.workflow_name ?? "";
  const name = check.name ?? check.context ?? "";
  return ROUTINE_CHECK.test(`${workflow} ${name}`);
}

function latestChecks(checks) {
  const latest = new Map();

  checks.forEach((check, index) => {
    const workflow = check.workflowName ?? check.workflow_name ?? "";
    const name = check.name ?? check.context ?? `anonymous-${index}`;

    const key = `${workflow}::${name}`;
    const status = String(check.status ?? "").toUpperCase();
    const completedTimestamp = Date.parse(check.completedAt ?? check.completed_at ?? "");
    const startedTimestamp = Date.parse(check.startedAt ?? check.started_at ?? "");
    const sequence =
      status === "COMPLETED" && Number.isFinite(completedTimestamp) && completedTimestamp > 0
        ? completedTimestamp
        : Number.isFinite(startedTimestamp) && startedTimestamp > 0
          ? startedTimestamp
          : index;
    const current = latest.get(key);
    if (!current || sequence >= current.sequence) {
      latest.set(key, { check, sequence });
    }
  });

  return [...latest.values()].map((entry) => entry.check);
}

function fileDelta(file) {
  return Number(file.additions ?? 0) + Number(file.deletions ?? 0);
}

function analyze(pr) {
  const labels = labelNames(pr);
  const text = [pr.title ?? "", ...labels].join(" | ");
  const files = changedFiles(pr);
  const paths = files.map(filePath).filter(Boolean);
  const declaredFileCount = requireHydrated
    ? (pr.changed_files ?? pr.changedFiles)
    : (pr.changedFiles ?? pr.changed_files);
  const hasDeclaredFileCount =
    declaredFileCount !== undefined &&
    declaredFileCount !== null &&
    Number.isInteger(Number(declaredFileCount));
  const fullyHydratedFiles =
    files.length > 0 &&
    hasDeclaredFileCount &&
    files.every((file) => filePath(file) && hasFileDelta(file)) &&
    Number(declaredFileCount) === files.length;
  const productionFiles = files.filter((file) => {
    const path = filePath(file);
    return path && !TEST_PATH.test(path) && !DOC_PATH.test(path);
  });
  const hasKnownPaths = paths.length > 0;
  const hasPerFileDeltas = productionFiles.length > 0 && productionFiles.every(hasFileDelta);
  const totalDelta = Number(pr.additions ?? 0) + Number(pr.deletions ?? 0);
  let productionDelta = null;
  if (requireHydrated) {
    if (hasKnownPaths && productionFiles.length === 0) {
      productionDelta = 0;
    } else if (hasPerFileDeltas) {
      productionDelta = productionFiles.reduce((sum, file) => sum + fileDelta(file), 0);
    }
  }
  const productionDeltaKnown = productionDelta !== null;
  const fileCount = Number(declaredFileCount ?? paths.length);
  const reasons = [];
  const author = pr.author?.login ?? pr.user?.login ?? pr.author ?? "";
  const normalizedAuthor = String(author).toLowerCase();
  const authorAssociation = String(
    requireHydrated
      ? (pr.author_association ?? pr.authorAssociation ?? "")
      : (pr.authorAssociation ?? pr.author_association ?? ""),
  ).toUpperCase();
  const normalizedLabels = labels.map((label) => label.toLowerCase());
  const hasRestMergeState = Object.hasOwn(pr, "mergeable_state");
  const mergeState = String(
    requireHydrated && hasRestMergeState
      ? (pr.mergeable_state ?? "")
      : requireHydrated
        ? (pr.merge_state_status ?? pr.mergeStateStatus ?? "")
        : (pr.mergeStateStatus ?? pr.merge_state_status ?? pr.mergeable_state ?? ""),
  ).toUpperCase();
  const mergeableValue = String(pr.mergeable ?? "").toUpperCase();
  const hasMergeState = requireHydrated && hasRestMergeState
    ? Boolean(mergeState && mergeState !== "UNKNOWN")
    : typeof pr.mergeable === "boolean" ||
      ["MERGEABLE", "CONFLICTING"].includes(mergeableValue) ||
      Boolean(mergeState && mergeState !== "UNKNOWN");
  const hasCheckRollup = hasValidCheckRollup(pr);
  const checks = latestChecks(checkEntries(pr));
  const failedChecks = checks.filter((check) => {
    const conclusion = String(check.conclusion ?? check.state ?? "").toUpperCase();
    if (
      [
        "ACTION_REQUIRED",
        "ERROR",
        "FAILURE",
        "STARTUP_FAILURE",
        "TIMED_OUT",
      ].includes(conclusion)
    ) {
      return true;
    }
    return ["CANCELLED", "STALE"].includes(conclusion) && !isRoutineCheck(check);
  });
  const pendingChecks = checks.filter((check) => {
    if (isRoutineCheck(check)) return false;
    const status = String(check.status ?? "").toUpperCase();
    const conclusion = String(check.conclusion ?? check.state ?? "").toUpperCase();
    if (["PENDING", "EXPECTED"].includes(conclusion)) return true;
    return status !== "" && status !== "COMPLETED" && !conclusion;
  });

  if (pr.isDraft ?? pr.draft) reasons.push("draft");
  if (
    (pr.state && String(pr.state).toUpperCase() !== "OPEN") ||
    pr.merged === true ||
    Boolean(pr.mergedAt ?? pr.merged_at)
  ) {
    reasons.push("not open");
  }
  if (
    MAINTAINER_ASSOCIATIONS.has(authorAssociation) ||
    DEFAULT_MAINTAINERS.has(normalizedAuthor) ||
    normalizedLabels.includes("maintainer")
  ) {
    reasons.push("maintainer-owned");
  }
  if (explicitSkips.has(Number(pr.number))) reasons.push("explicitly skipped");
  if (HARD_RISK.test(text)) reasons.push("high-risk or compatibility surface");
  if (UI_RISK.test(text)) reasons.push("UI or native-app surface");
  if (paths.some((path) => HIGH_RISK_PATH.test(normalizedRiskPath(path)))) {
    reasons.push("high-risk path surface");
  }
  if (paths.some((path) => UI_PATH.test(normalizedRiskPath(path)))) {
    reasons.push("UI or native-app path");
  }
  if (FEATURE_TITLE.test(pr.title ?? "")) reasons.push("feature work");
  if (LOW_SIGNAL_TITLE.test(pr.title ?? "")) reasons.push("low-signal change type");
  if (ODD_MICRO_TITLE.test(pr.title ?? "")) reasons.push("odd mechanical micro-fix");
  if (normalizedLabels.includes("dependencies-changed")) reasons.push("dependency change");
  if (requireHydrated && paths.length > 0 && paths.every((path) => TEST_PATH.test(path))) {
    reasons.push("test-only");
  }
  if (requireHydrated && paths.length > 0 && paths.every((path) => DOC_PATH.test(path))) {
    reasons.push("docs-only");
  }
  if (requireHydrated && hasKnownPaths && productionFiles.length === 0) {
    reasons.push("non-production-only");
  }
  if (requireHydrated && !fullyHydratedFiles) reasons.push("incomplete file hydration");
  if (requireHydrated && !authorAssociation) reasons.push("missing author association");
  if (requireHydrated && !hasMergeState) reasons.push("unresolved merge state");
  if (requireHydrated && !hasCheckRollup) reasons.push("missing check rollup");
  if (requireHydrated && productionDeltaKnown && productionDelta < 10) {
    reasons.push("trivial production diff");
  }
  if (requireHydrated && productionDeltaKnown && fileCount === 1 && productionDelta < 25) {
    reasons.push("tiny single-file diff");
  }
  if (requireHydrated && productionDeltaKnown && productionDelta > 500) {
    reasons.push("production diff above 500 lines");
  }
  if (requireHydrated && fileCount > 12) reasons.push("more than 12 changed files");
  if (
    pr.mergeable === false ||
    String(pr.mergeable ?? "").toUpperCase() === "CONFLICTING" ||
    mergeState === "DIRTY"
  ) {
    reasons.push("dirty or conflicting");
  }
  if (failedChecks.length > 0) reasons.push("failing checks");

  let score = 0;
  if (
    normalizedLabels.some(
      (label) => label.startsWith("rating:") && /\bdiamond\b/.test(label),
    )
  ) {
    score += 40;
  }
  if (
    normalizedLabels.some(
      (label) => label.startsWith("rating:") && /\bplatinum\b/.test(label),
    )
  ) {
    score += 30;
  }
  if (
    normalizedLabels.some(
      (label) => label.startsWith("proof:") && /\bsufficient\b/.test(label),
    )
  ) {
    score += 15;
  }
  if (normalizedLabels.some((label) => label.includes("ready for maintainer look"))) {
    score += 10;
  }
  if (
    pr.mergeable === "MERGEABLE" ||
    pr.mergeable === true ||
    mergeState === "CLEAN"
  ) {
    score += 8;
  }
  if (requireHydrated && productionDeltaKnown && productionDelta >= 20 && productionDelta <= 250) {
    score += 8;
  }
  if (requireHydrated && fileCount >= 2 && fileCount <= 8) score += 4;
  if (/needs proof|waiting on author/i.test(text)) score -= 12;
  if (/merge-risk:/i.test(text)) score -= 8;
  if (pendingChecks.length > 0) score -= 5;

  return {
    number: pr.number,
    title: pr.title,
    author,
    url: pr.url ?? pr.html_url,
    productionDelta,
    productionDeltaKnown,
    totalDelta,
    changedFiles: fileCount,
    productionFiles: productionFiles.length,
    score,
    rating: labels.find((label) => label.startsWith("rating:")) ?? "",
    status: labels.find((label) => label.startsWith("status:")) ?? "",
    reasons,
  };
}

const analyzed = uniquePrs.map(analyze);
const qualified = analyzed
  .filter((pr) => pr.reasons.length === 0)
  .sort((left, right) => right.score - left.score || right.number - left.number);
const rejected = analyzed
  .filter((pr) => pr.reasons.length > 0)
  .sort((left, right) => right.number - left.number);

const hydrationPool = qualified.slice(0, limit);

process.stdout.write(
  `${JSON.stringify(
    {
      phase: requireHydrated ? "hydrated" : "discovery",
      selected: hydrationPool.slice(0, batchSize),
      hydrationPool,
      qualifiedCount: qualified.length,
      rejectedCount: rejected.length,
      rejected,
    },
    null,
    2,
  )}\n`,
);
