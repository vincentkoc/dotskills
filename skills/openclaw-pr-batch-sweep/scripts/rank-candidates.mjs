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
  /\b(security|ssrf|xss|csrf|rce|auth(?:entication|n|z)?|oauth|authori[sz](?:e|ation|ed)|secrets?|credentials?|proxy|redact(?:ion)?|chmod|permissions?|sandbox|pairing|approvals?|authorized[- ]sender|account[- ]bound|trust[- ]boundary|migration|migrate|compatibility|session[- ]state|message[- ]delivery|auth[- ]provider|security[- ]boundary|release|workflow|codeql|dependabot)\b/i;
const SENSITIVE_TOKEN =
  /\b(?:access|api|auth|bearer|refresh|session)[ -]+tokens?\b|\btokens?[ -]+(?:exposure|handling|leak|redaction|refresh|rotation|storage|validation)\b/i;
const HARD_RISK_LABEL =
  /^(?:(?:area|merge-risk):.*\b(?:auth|availability|message[- ]delivery|oauth|permissions?|proxy|redaction|sandbox|secrets?|security|session[- ]state|credentials?|tokens?)\b|auth|availability|message[- ]delivery|oauth|permissions?|proxy|redaction|sandbox|secrets?|security(?:-sensitive)?|session[- ]state|credentials?|tokens?)/i;
const UI_RISK =
  /\b(ui|tui|terminal ui|control ui|web[- ]?ui|frontend|visual|translation|i18n|android|ios|camera|scrolling|layout|css)\b/i;
const HIGH_RISK_PATH =
  /^(?:\.github\/|ui\/|apps\/|packages\/(?:gateway-protocol|plugin-sdk)\/|src\/plugin-sdk\/|scripts\/release)|(?:^|[\/._-])(?:auth(?:entication|n|z|orize|orization)?|authori[sz](?:e|ation|ed)|oauth|tokens?|secrets?|credentials?|redact(?:ion)?|chmod|permissions?|approvals?|security|ssrf|xss|csrf|rce|proxy|sandbox|pairing|account-bound|trust-boundary|migrations?|compat(?:ibility)?|legacy|session-state|message-delivery|auth-provider|release|workflow|codeql|dependabot)(?:[._/-]|$)|(?:^|\/)(?:package\.json|pnpm-lock\.yaml|bun\.lock)$/i;
const CONFIG_RISK_PATH =
  /(?:^|\/)config\/|(?:^|\/)config\.[cm]?[jt]s$|(?:^|[\/._-])config(?:uration)?-(?:defaults?|migration|schema)(?:[._/-]|$)/i;
const SERVICE_ENV_RISK_PATH =
  /^src\/(?:daemon\/service-env|infra\/(?:dotenv|path-env))(?:\.|\/|$)/i;
const UPDATE_TARGET_POLICY_TITLE =
  /\b(?:self[- ]?updates?|updates?)\b.{0,60}\b(?:global[- ](?:install[- ])?root|install[- ]root|npm[- ]prefix|package[- ]root)\b|\b(?:global[- ](?:install[- ])?root|install[- ]root|npm[- ]prefix|package[- ]root)\b.{0,60}\b(?:self[- ]?updates?|updates?)\b/i;
const CONFIG_RISK_TITLE =
  /\bconfig(?:uration)?\s+(?:compatibility|defaults?|migration|schema)\b|\b(?:add|migrate|remove|rename)\b.{0,40}\bconfig(?:uration)?\b|\bconfig(?:uration)?\b.{0,40}\b(?:merge|preserve)\b|\b(?:merge|preserve)\b.{0,40}\bconfig(?:uration)?\b/i;
const RESOURCE_LIMIT_TITLE =
  /\b(?:bound|enforce|limit|reject)\b.{0,60}\b(?:bytes?|json|oom|payload|response|sse)\b|\boom\b/i;
const AVAILABILITY_POLICY_TITLE =
  /\b(?:bound|extend|increase|raise|use)\b.{0,50}\b(?:retries|retry budget|slot occupancy|timeout|watchdog)\b|\b(?:retry budget|slot occupancy|watchdog)\b.{0,50}\b(?:budget|duration|limit|timeout)\b|\b(?:retry|retries)\b.{0,40}\b(?:backoff|budget|limit|policy)\b|\b(?:add|change|disable|remove|retry|use)\b.{0,50}\b(?:fall\s+back|fallback)\b|\b(?:fall\s+back|fallback)\b.{0,50}\b(?:after|instead|on|policy|to|when)\b|\b(?:force|forced)\b.{0,30}\b(?:kill|shutdown|terminate|termination)\b|\b(?:sigkill|sigterm)\b|\bexecute\b.{0,20}\btwice\b|\bduplicate\b.{0,40}\b(?:execution|request|run|side effect|tool calls?|turn)\b|\b(?:re-?execute|rerun)\b.{0,40}\b(?:request|run|side effect|tool calls?|turn)\b/i;
const SESSION_DELIVERY_RISK_TITLE =
  /\b(?:sessions?|session[_-]?id|transcript|history)\b.{0,60}\b(?:affinity|continuity|dedup|fallback|identity|mirror|persist|recover|replay|resume|reuse|state)\b|\b(?:affinity|continuity|dedup|fallback|identity|mirror|persist|recover|replay|resume|reuse|state)\b.{0,60}\b(?:sessions?|session[_-]?id|transcript|history)\b|\b(?:dedup|duplicate|replay|reprocess)\w*\b.{0,60}\b(?:inbound|message|reply|turn|webhook)\b|\b(?:delivery mirror|message delivery)\b|\b(?:send|reply)\b.{0,40}\b(?:fall\s+back|fallback)\b|\b(?:cron|reply|run|status|thread|target)\b.{0,60}\bdelivery\b|\bdelivery\b.{0,60}\b(?:backoff|error|fail|recover|recovery|retry|status|wedge)\b|\b(?:drain|outbound)\b.{0,60}\b(?:recover|recovery|retry)\b/i;
const UI_PATH =
  /^(?:apps)(?:\/|$)|(?:^|[\/._-])(?:ui|tui|control-ui|frontend|web-ui|locales?|translations?)(?:[\/._-]|$)|\.(?:css|scss|sass|less|tsx|jsx|vue|svelte)$/i;
const LOW_SIGNAL_TITLE =
  /^(?:test|docs|chore|refactor|style|i18n|ci|build|infra)(?:\([^)]*\))?:|^(?:fix|chore)\((?:test|docs|ci|build|infra)\):|\b(typo|rename|formatting|lint|coverage|unit tests?|add tests?|object\.hasown|user[- ]agent|logging?|warning when|close readline|destroy read stream|allow always|one-shot command|dangling surrogate)\b/i;
const CLEANUP_ONLY_TITLE =
  /\b(?:remove|delete|drop)\b.{0,50}\b(?:dead|redundant|unused)\b.{0,30}\b(?:branches?|checks?|code|logic|loops?)\b|\bdead[- ]code\b|\bcleanup[- ]only\b/i;
const TEST_INFRA_TITLE = /\b(?:fixture-only|live smoke|test fixture|test harness)\b/i;
const DIAGNOSTIC_MICRO_TITLE =
  /\b(?:diagnostic|error|failure|warning)\b.{0,50}\b(?:cause|context|copy|guidance|hint|message|wording)\b|\b(?:improve|clarify|enrich|wrap)\b.{0,50}\b(?:diagnostic|error|failure|warning)\b|\b(?:guidance|hint|wording)\b/i;
const ODD_MICRO_TITLE =
  /\b(?:add|clear|close|destroy|guard|rename|replace|switch|use)\b.{0,40}\b(?:header|literal|log(?:ging)?|null check|object\.hasown|optional chaining|timer|timeout|user[- ]agent|warning)\b/i;
const LIFECYCLE_MICRO_ACTION =
  /\b(?:cancel|clear)\b.{0,40}\b(?:timer|timeout)\b|\b(?:timer|timeout)\b.{0,40}\b(?:cancel|clear)\b/i;
const LIFECYCLE_MICRO_OUTCOME =
  /\b(?:dangling (?:handle|timer)s?|event loop (?:hang|stall)|process (?:hang|stall|not exit)|resource leak|stale timer accumulation|timer (?:accumulation|leak))\b/i;
const FEATURE_TITLE = /^(?:feat|feature)(?:\([^)]*\))?:/i;
const FEATURE_SHAPED_TITLE =
  /\b(?:add|allow|enable|introduce|support)\b.{0,60}\b(?:flag|format|integration|option|provider|syntax|timezone)\b/i;
const BUNDLED_FIX_TITLE =
  /\bfix(?:es|ing)?\s+(?:(?:two|three|four|five|six|seven|eight|nine|ten)|\d+)\b.{0,60}\b(?:bugs?|issues?)\b/i;
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
const terminalDecisions = new Map();

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
      terminalDecisions.set(number, "explicitly skipped");
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
  for (const key of [
    "explicitSkips",
    "landed",
    "handledMerged",
    "closed",
    "rejected",
    "ignored",
  ]) {
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
      const terminalReason = {
        explicitSkips: "explicitly skipped",
        landed: "already landed",
        handledMerged: "already handled and merged",
        closed: "already closed",
        rejected: "previously rejected",
        ignored: "explicitly ignored",
      }[key];
      terminalDecisions.set(number, terminalReason);
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
const parsedInput = JSON.parse(input);
const prs = Array.isArray(parsedInput) ? parsedInput : parsedInput.threads;
if (!Array.isArray(prs)) {
  throw new Error('Expected a JSON array of pull requests or a {"threads": [...]} envelope');
}
const pullRequests = prs.filter((item) => {
  const kind = String(item.kind ?? "").toLowerCase();
  return kind === "" || kind === "pull_request" || kind === "pull" || kind === "pr";
});
const uniquePrs = [
  ...new Map(
    pullRequests.map((pr) => {
      const number = Number(pr.number);
      if (!Number.isInteger(number) || number < 1) {
        throw new Error(`Expected a positive PR number, received: ${String(pr.number)}`);
      }
      return [number, pr];
    }),
  ).values(),
];

function labelNames(pr) {
  let labels = pr.labels;
  if (!Array.isArray(labels) && pr.labels_json) {
    try {
      labels =
        typeof pr.labels_json === "string" ? JSON.parse(pr.labels_json) : pr.labels_json;
    } catch {
      labels = [];
    }
  }
  return (Array.isArray(labels) ? labels : []).map((label) =>
    typeof label === "string" ? label : label.name,
  );
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

function normalizedRiskText(text) {
  return String(text)
    .replace(/([A-Z]+)([A-Z][a-z])/g, "$1-$2")
    .replace(/([a-z0-9])([A-Z])/g, "$1-$2")
    .toLowerCase();
}

function linkedIssueNumbers(pr) {
  const body = String(pr.body ?? "");
  return [
    ...body.matchAll(
      /\b(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?)\s+(?:https:\/\/github\.com\/openclaw\/openclaw\/issues\/)?#?(\d+)\b/gi,
    ),
  ].map((match) => Number.parseInt(match[1], 10));
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

function overlapStrength(pr) {
  const labels = labelNames(pr).map((label) => label.toLowerCase());
  const files = changedFiles(pr);
  const testFiles = files.filter((file) => TEST_PATH.test(filePath(file)));
  const testDelta = testFiles.every(hasFileDelta)
    ? testFiles.reduce((sum, file) => sum + fileDelta(file), 0)
    : 0;
  let score = 0;
  if (labels.some((label) => label.startsWith("proof:") && /\bsufficient\b/.test(label))) {
    score += 40;
  }
  if (labels.some((label) => label.includes("ready for maintainer look"))) score += 20;
  if (labels.some((label) => label.startsWith("rating:") && /\bdiamond\b/.test(label))) {
    score += 15;
  } else if (
    labels.some((label) => label.startsWith("rating:") && /\bplatinum\b/.test(label))
  ) {
    score += 10;
  }
  if (testFiles.length > 0) score += 8;
  if (testDelta >= 25) score += 5;
  return score;
}

function isOverlapEligible(pr) {
  if (pr.isDraft ?? pr.is_draft ?? pr.draft) return false;
  if (pr.state && String(pr.state).toUpperCase() !== "OPEN") return false;
  if (terminalDecisions.has(Number(pr.number))) return false;
  if (!hasValidCheckRollup(pr)) return false;

  const mergeState = String(
    pr.mergeable_state ?? pr.merge_state_status ?? pr.mergeStateStatus ?? "",
  ).toUpperCase();
  if (
    pr.mergeable === null ||
    pr.mergeable === undefined ||
    pr.mergeable === false ||
    String(pr.mergeable).toUpperCase() === "CONFLICTING" ||
    !mergeState ||
    ["DIRTY", "UNKNOWN"].includes(mergeState)
  ) {
    return false;
  }

  for (const check of latestChecks(checkEntries(pr))) {
    if (isRoutineCheck(check)) continue;
    const status = String(check.status ?? "").toUpperCase();
    const conclusion = String(check.conclusion ?? check.state ?? "").toUpperCase();
    if (
      [
        "ACTION_REQUIRED",
        "CANCELLED",
        "ERROR",
        "FAILURE",
        "PENDING",
        "STALE",
        "STARTUP_FAILURE",
        "TIMED_OUT",
      ].includes(conclusion) ||
      (status && status !== "COMPLETED" && !conclusion)
    ) {
      return false;
    }
  }
  return true;
}

function overlappingCandidateDecisions(prsToCheck) {
  const groups = new Map();

  for (const pr of prsToCheck) {
    const productionPaths = changedFiles(pr)
      .map(filePath)
      .filter((path) => path && !TEST_PATH.test(path) && !DOC_PATH.test(path))
      .map(normalizedRiskPath)
      .sort();
    const issues = linkedIssueNumbers(pr).sort((left, right) => left - right);
    if (productionPaths.length === 0 || issues.length === 0) continue;

    const key = `${issues.join(",")}::${productionPaths.join("|")}`;
    const candidates = groups.get(key) ?? [];
    candidates.push(pr);
    groups.set(key, candidates);
  }

  const decisions = new Map();
  for (const candidates of groups.values()) {
    const eligibleCandidates = candidates.filter(isOverlapEligible);
    if (eligibleCandidates.length < 2) continue;
    const ranked = eligibleCandidates
      .map((pr) => ({ number: Number(pr.number), score: overlapStrength(pr) }))
      .sort((left, right) => right.score - left.score || right.number - left.number);
    const topScore = ranked[0].score;
    const tiedWinners = ranked.filter((entry) => entry.score === topScore);
    if (tiedWinners.length > 1) {
      for (const entry of ranked) {
        decisions.set(entry.number, "overlapping candidates need adjudication");
      }
      continue;
    }
    for (const entry of ranked.slice(1)) {
      decisions.set(entry.number, "weaker overlapping candidate");
    }
  }
  return decisions;
}

const overlapDecisions = requireHydrated
  ? overlappingCandidateDecisions(uniquePrs)
  : new Map();

function analyze(pr) {
  const labels = labelNames(pr);
  const title = String(pr.title ?? "");
  const normalizedTitle = normalizedRiskText(title);
  const text = [title, ...labels].join(" | ");
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
  const testFiles = files.filter((file) => TEST_PATH.test(filePath(file)));
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
  const testDelta =
    requireHydrated && testFiles.every(hasFileDelta)
      ? testFiles.reduce((sum, file) => sum + fileDelta(file), 0)
      : null;
  const fileCount = Number(declaredFileCount ?? paths.length);
  const reasons = [];
  const author =
    pr.author?.login ?? pr.user?.login ?? pr.author_login ?? pr.author ?? "";
  const normalizedAuthor = String(author).toLowerCase();
  const authorType = String(
    pr.author?.type ?? pr.user?.type ?? pr.author_type ?? "",
  ).toUpperCase();
  const authorAssociation = String(
    requireHydrated
      ? (pr.author_association ?? pr.authorAssociation ?? "")
      : (pr.authorAssociation ?? pr.author_association ?? ""),
  ).toUpperCase();
  const normalizedLabels = labels.map((label) => label.toLowerCase());
  const strongRating = normalizedLabels.some(
    (label) =>
      label.startsWith("rating:") && /\b(?:diamond|platinum)\b/.test(label),
  );
  const sufficientProof = normalizedLabels.some(
    (label) => label.startsWith("proof:") && /\bsufficient\b/.test(label),
  );
  const readyForMaintainer = normalizedLabels.some((label) =>
    label.includes("ready for maintainer look"),
  );
  const lifecycleEvidenceText = `${title}\n${String(pr.body ?? "")}`;
  const provisionalLifecycleMicroFix =
    !requireHydrated &&
    linkedIssueNumbers(pr).length > 0 &&
    strongRating &&
    sufficientProof &&
    readyForMaintainer &&
    LIFECYCLE_MICRO_ACTION.test(lifecycleEvidenceText) &&
    LIFECYCLE_MICRO_OUTCOME.test(lifecycleEvidenceText);
  const provenLifecycleMicroFix =
    requireHydrated &&
    productionDeltaKnown &&
    productionDelta >= 5 &&
    productionDelta <= 20 &&
    productionFiles.length === 1 &&
    testFiles.length >= 1 &&
    testDelta !== null &&
    testDelta >= 25 &&
    linkedIssueNumbers(pr).length > 0 &&
    strongRating &&
    sufficientProof &&
    readyForMaintainer &&
    LIFECYCLE_MICRO_ACTION.test(lifecycleEvidenceText) &&
    LIFECYCLE_MICRO_OUTCOME.test(lifecycleEvidenceText);
  const hasRestMergeState = Object.hasOwn(pr, "mergeable_state");
  const mergeState = String(
    requireHydrated && hasRestMergeState
      ? (pr.mergeable_state ?? "")
      : requireHydrated
        ? (pr.merge_state_status ?? pr.mergeStateStatus ?? "")
        : (pr.mergeStateStatus ?? pr.merge_state_status ?? pr.mergeable_state ?? ""),
  ).toUpperCase();
  const mergeableValue = String(pr.mergeable ?? "").toUpperCase();
  const hasResolvedRestMergeable =
    !requireHydrated ||
    (Object.hasOwn(pr, "mergeable") &&
      pr.mergeable !== null &&
      pr.mergeable !== undefined);
  const hasMergeState = requireHydrated && hasRestMergeState
    ? hasResolvedRestMergeable &&
      Boolean(mergeState && mergeState !== "UNKNOWN")
    : hasResolvedRestMergeable &&
      (typeof pr.mergeable === "boolean" ||
        ["MERGEABLE", "CONFLICTING"].includes(mergeableValue) ||
        Boolean(mergeState && mergeState !== "UNKNOWN"));
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

  if (pr.isDraft ?? pr.is_draft ?? pr.draft) reasons.push("draft");
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
    authorType === "BOT" ||
    normalizedAuthor.endsWith("[bot]") ||
    normalizedLabels.includes("maintainer")
  ) {
    reasons.push("maintainer-owned");
  }
  const terminalDecision = terminalDecisions.get(Number(pr.number));
  if (terminalDecision) reasons.push(terminalDecision);
  if (
    HARD_RISK.test(normalizedTitle) ||
    SENSITIVE_TOKEN.test(normalizedTitle) ||
    labels.some((label) => HARD_RISK_LABEL.test(label))
  ) {
    reasons.push("high-risk or compatibility surface");
  }
  if (CONFIG_RISK_TITLE.test(normalizedTitle)) {
    reasons.push("config schema/default/migration surface");
  }
  if (AVAILABILITY_POLICY_TITLE.test(normalizedTitle)) {
    reasons.push("availability policy surface");
  }
  if (SESSION_DELIVERY_RISK_TITLE.test(normalizedTitle)) {
    reasons.push("session or message-delivery semantics");
  }
  if (UPDATE_TARGET_POLICY_TITLE.test(normalizedTitle)) {
    reasons.push("self-update install-root policy surface");
  }
  if (RESOURCE_LIMIT_TITLE.test(normalizedTitle)) {
    reasons.push("resource-limit or response-boundary hardening");
  }
  if (UI_RISK.test(text)) reasons.push("UI or native-app surface");
  if (paths.some((path) => HIGH_RISK_PATH.test(normalizedRiskPath(path)))) {
    reasons.push("high-risk path surface");
  }
  if (paths.some((path) => CONFIG_RISK_PATH.test(normalizedRiskPath(path)))) {
    reasons.push("config schema/default/migration surface");
  }
  if (paths.some((path) => SERVICE_ENV_RISK_PATH.test(normalizedRiskPath(path)))) {
    reasons.push("service environment or PATH precedence surface");
  }
  if (paths.some((path) => UI_PATH.test(normalizedRiskPath(path)))) {
    reasons.push("UI or native-app path");
  }
  if (FEATURE_TITLE.test(pr.title ?? "")) reasons.push("feature work");
  if (FEATURE_SHAPED_TITLE.test(pr.title ?? "")) reasons.push("feature-shaped fix");
  if (BUNDLED_FIX_TITLE.test(pr.title ?? "")) reasons.push("bundled multi-topic fix");
  if (LOW_SIGNAL_TITLE.test(pr.title ?? "")) reasons.push("low-signal change type");
  if (CLEANUP_ONLY_TITLE.test(pr.title ?? "")) reasons.push("cleanup-only change");
  if (TEST_INFRA_TITLE.test(pr.title ?? "")) reasons.push("test or infrastructure work");
  if (
    ODD_MICRO_TITLE.test(pr.title ?? "") &&
    !provisionalLifecycleMicroFix &&
    !provenLifecycleMicroFix
  ) {
    reasons.push("odd mechanical micro-fix");
  }
  if (normalizedLabels.includes("dependencies-changed")) reasons.push("dependency change");
  if (requireHydrated && paths.length > 0 && paths.every((path) => TEST_PATH.test(path))) {
    reasons.push("test-only");
  }
  if (requireHydrated && paths.length > 0 && paths.every((path) => DOC_PATH.test(path))) {
    reasons.push("docs-only");
  }
  if (requireHydrated && pr.hydrationComplete === false) {
    reasons.push("incomplete hydration");
  }
  if (requireHydrated && hasKnownPaths && productionFiles.length === 0) {
    reasons.push("non-production-only");
  }
  if (requireHydrated && !fullyHydratedFiles) reasons.push("incomplete file hydration");
  if (requireHydrated && !authorAssociation) reasons.push("missing author association");
  if (requireHydrated && !hasMergeState) reasons.push("unresolved merge state");
  if (requireHydrated && !hasCheckRollup) reasons.push("missing check rollup");
  if (
    requireHydrated &&
    productionDeltaKnown &&
    productionDelta < 10 &&
    !provenLifecycleMicroFix
  ) {
    reasons.push("trivial production diff");
  }
  if (
    requireHydrated &&
    productionDeltaKnown &&
    productionDelta < 25 &&
    DIAGNOSTIC_MICRO_TITLE.test(title)
  ) {
    reasons.push("diagnostic-only micro-change");
  }
  if (requireHydrated && productionDeltaKnown && fileCount === 1 && productionDelta < 25) {
    reasons.push("tiny single-file diff");
  }
  if (requireHydrated && productionDeltaKnown && productionDelta > 500) {
    reasons.push("production diff above 500 lines");
  }
  if (requireHydrated && fileCount > 12) reasons.push("more than 12 changed files");
  const overlapDecision = overlapDecisions.get(Number(pr.number));
  if (requireHydrated && overlapDecision) {
    reasons.push(overlapDecision);
  }
  if (
    pr.mergeable === false ||
    String(pr.mergeable ?? "").toUpperCase() === "CONFLICTING" ||
    mergeState === "DIRTY"
  ) {
    reasons.push("dirty or conflicting");
  }
  if (failedChecks.length > 0) reasons.push("failing checks");
  if (pendingChecks.length > 0) reasons.push("pending checks");

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
  if (mergeState === "UNSTABLE") score -= 10;

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
    exceptionGate: provenLifecycleMicroFix
      ? "proven lifecycle micro-fix"
      : provisionalLifecycleMicroFix
        ? "provisional lifecycle micro-fix; hydrate"
        : "",
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
