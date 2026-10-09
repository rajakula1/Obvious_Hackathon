#!/usr/bin/env node
'use strict';

/**
 * QualityForge factory runbook — the R8 "run" made operational.
 *
 * Usage:
 *   node qualityforge/factory/run.js <requirement-file> [options]
 *
 * Options:
 *   --dry-run                  print the task tree; create nothing (no SDK call)
 *   --json                     with --dry-run: emit the plan as JSON
 *   --max-repair-attempts N    bounded debug-retest loop (default 3, spec §7.3)
 *   --max-iterations N         max total iterations per run (default 8)
 *   --time-budget-minutes N    per-run time budget (default 15, spec §10)
 *   --credit-budget N          per-run credit budget (default 60)
 *   --executor NAME            suggested executor for stage tasks:
 *                              obvious | autobuild | human (default obvious)
 *   -h, --help                 show usage
 *
 * What it does: reads a requirement file (one run = one requirement file plus
 * this runbook, review R8), validates and records the time / iteration /
 * credit budgets BEFORE dispatch (spec §7.3, §10), and instantiates the full
 * run task DAG on the Obvious workspace as native tasks with explicit
 * dependencies: Requirements → Architecture → Plan → Coding → Testing →
 * bounded Debug-and-Retest → Quality/Verify gate → human review gate →
 * delivery. Every gate's completion requires its evidence artifact (spec §5.2,
 * conventions/gates.md); agents never mark their own completion.
 *
 * Writer rule (R8, spec §9/§12.2): only this script writes run statuses, and
 * terminal statuses are restricted to the spec §9 enum (delivered,
 * needs_human, rejected). When any budget limit is reached the run is
 * escalated to needs_human with a failure summary (spec §7.3) — never a
 * success it has not verified.
 *
 * The 'obvious' SDK is required lazily, only when actually dispatching, so
 * dry-run and the unit tests run without the package or a token.
 */

const fs = require('node:fs');
const path = require('node:path');

/* ---------------------------------------------------------------------------
 * Run statuses — the ten of spec §9, mirroring qualityforge/run_status.py.
 * run.test.js cross-checks the two definitions so they cannot drift.
 * ------------------------------------------------------------------------- */

const RUN_STATUSES = Object.freeze([
  'analyzing',
  'designing',
  'generating',
  'testing',
  'debugging',
  'verifying',
  'awaiting_approval',
  'delivered',
  'needs_human',
  'rejected',
]);

// Defined endings (spec §9; groupings in run_status.py / gates.md).
const TERMINAL_STATUSES = Object.freeze(['delivered', 'needs_human', 'rejected']);

const STATUS_ESCALATION = 'needs_human';
const STATUS_DELIVERED = 'delivered';
const STATUS_REJECTED = 'rejected';

function isRunStatus(value) {
  return RUN_STATUSES.includes(value);
}

function isTerminalStatus(value) {
  return TERMINAL_STATUSES.includes(value);
}

/** Task-status a terminal run status maps to on the root task (§9: run state
 * lives in initiative/task state). The run status itself is logged as task
 * feedback; this mapping only parks or closes the root. */
const TASK_STATUS_FOR_TERMINAL = Object.freeze({
  delivered: 'completed',
  needs_human: 'needs_action',
  rejected: 'failed',
});

/** Raised for any attempt to write a status outside §9, to end an already
 * ended run, or to open a run on a terminal status. Never swallowed. */
class RunStatusError extends Error {
  constructor(message) {
    super(message);
    this.name = 'RunStatusError';
  }
}

/** Raised for CLI usage errors (unknown flag, missing argument). */
class UsageError extends Error {
  constructor(message) {
    super(message);
    this.name = 'UsageError';
  }
}

/**
 * The single validated transition point for run statuses (R8). Every write
 * — stage or terminal — passes through here before any SDK call.
 *  - next must be one of the ten §9 statuses (an undefined state fails loudly);
 *  - a run ends exactly once: no write after a terminal status;
 *  - a run cannot open on a terminal status.
 */
function assertTransition(current, next) {
  if (!isRunStatus(next)) {
    throw new RunStatusError(
      `"${String(next)}" is not a spec §9 run status; allowed: ${RUN_STATUSES.join(', ')}`
    );
  }
  if (current !== null && current !== undefined) {
    if (!isRunStatus(current)) {
      throw new RunStatusError(
        `current status "${String(current)}" is not a spec §9 run status`
      );
    }
    if (isTerminalStatus(current)) {
      throw new RunStatusError(
        `run already ended (${current}); a run ends exactly once (§12.2)`
      );
    }
  } else if (isTerminalStatus(next)) {
    throw new RunStatusError(
      `cannot open a run at terminal status "${next}"; a run starts in a pipeline stage`
    );
  }
  return true;
}

/**
 * Map a run outcome to its terminal status — pure, and the only place a
 * terminal status is chosen (R8). Returns { status, summary } or null when
 * nothing terminal happened (stage continues, no status is invented).
 *
 *  - limits reached → needs_human with a failure summary (§7.3, §10);
 *  - approval approve → delivered, reject → rejected (§7.9);
 *  - request_changes → null (restarts a stage; §7.9).
 */
function decideTerminalStatus({ limitReached = false, failureSummary = '', approval = null } = {}) {
  if (limitReached) {
    const summary = String(failureSummary).trim();
    if (!summary) {
      // §10 reliability: a run always ends in a DEFINED status with a
      // recorded reason. An escalation without a summary is a silent failure.
      throw new RunStatusError('escalation requires a failure summary (§7.3)');
    }
    return { status: STATUS_ESCALATION, summary };
  }
  if (approval !== null && approval !== undefined) {
    const decision = String(approval.decision || '')
      .toLowerCase()
      .replace(/[\s-]+/g, '_');
    const reviewer = approval.reviewer ? ` by ${approval.reviewer}` : '';
    if (decision === 'approve') {
      return { status: STATUS_DELIVERED, summary: `Approval record recorded${reviewer} (§7.9).` };
    }
    if (decision === 'reject') {
      return {
        status: STATUS_REJECTED,
        summary: `Rejected at the human review gate${reviewer} (§7.9).`,
      };
    }
    if (decision === 'request_changes') {
      return null; // not terminal: the noted stage restarts (§7.9)
    }
    throw new RunStatusError(
      `unknown approval decision "${String(approval.decision)}"; expected approve | request_changes | reject`
    );
  }
  return null;
}

/**
 * Write a run status. THE ONLY writer of run statuses (R8): validates the
 * transition, logs it as feedback on the run root (the durable record §9
 * keeps on Obvious), and — for terminal statuses — parks/closes the root
 * task. Every SDK call happens only after validation; an invalid write makes
 * zero SDK calls.
 */
async function writeRunStatus({ sdkClient, runTaskId, current, next, reason = '' }) {
  assertTransition(current, next);

  const line = `QualityForge run status → ${next}${reason ? ` — ${reason}` : ''}`;
  await sdkClient.tasks.feedback.create({ taskId: runTaskId, body: line.slice(0, 10000) });

  if (isTerminalStatus(next)) {
    await sdkClient.tasks.update({
      taskId: runTaskId,
      status: TASK_STATUS_FOR_TERMINAL[next],
      completionNote: line.slice(0, 10000),
    });
  }
  return { written: next, terminal: isTerminalStatus(next) };
}

/* ---------------------------------------------------------------------------
 * Budgets (§7.3, §10): recorded before dispatch, reconciled after the run.
 * ------------------------------------------------------------------------- */

const BUDGET_DEFAULTS = Object.freeze({
  maxRepairAttempts: 3, // §7.3 default
  maxIterations: 8,
  timeBudgetMinutes: 15, // §10 first-workload demo budget
  creditBudget: 60, // recorded pre-run, reconciled post-run (see review §1)
});

const BUDGET_FIELDS = Object.freeze([
  ['maxRepairAttempts', 'max repair attempts'],
  ['maxIterations', 'max iterations'],
  ['timeBudgetMinutes', 'time budget (minutes)'],
  ['creditBudget', 'credit budget'],
]);

/** Validate budget overrides against the defaults; every value must be a
 * positive integer. Throws RangeError with the offending name — budgets are
 * gate inputs, so a bad value must stop the run before dispatch. */
function parseBudgets(overrides = {}) {
  const out = {};
  for (const [key, label] of BUDGET_FIELDS) {
    const provided = overrides[key] === undefined ? BUDGET_DEFAULTS[key] : overrides[key];
    const n = Number(provided);
    if (!Number.isInteger(n) || n <= 0) {
      throw new RangeError(`budget ${label} (${key}) must be a positive integer, got ${JSON.stringify(provided)}`);
    }
    out[key] = n;
  }
  return Object.freeze(out);
}

/** The budget record persisted on the run root BEFORE any stage task is
 * dispatched (§7.3). Enforcement is by recording and reconciliation, not a
 * platform meter (no metering API is documented — review §1). */
function buildBudgetRecord(budgets, { requirementPath, requirementChars, recordedAt } = {}) {
  return {
    recorded: 'before dispatch (spec §7.3, §10)',
    enforced: 'recorded pre-run and reconciled after the run; not platform-enforced',
    ...budgets,
    requirementPath,
    requirementChars,
    recordedAt,
  };
}

/* ---------------------------------------------------------------------------
 * Requirement and run identity (R8: one run = one requirement file).
 * ------------------------------------------------------------------------- */

function slugify(value) {
  return String(value)
    .toLowerCase()
    .replace(/\.[a-z0-9]+$/i, '')
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 48) || 'run';
}

function buildRunId(workload, now) {
  const pad = (n) => String(n).padStart(2, '0');
  const stamp = `${now.getUTCFullYear()}${pad(now.getUTCMonth() + 1)}${pad(now.getUTCDate())}T${pad(now.getUTCHours())}${pad(now.getUTCMinutes())}${pad(now.getUTCSeconds())}Z`;
  return `qf-${slugify(workload)}-${stamp}`;
}

/** Workload identity of a requirement path (gates.md run layout): a
 * `workloads/<workload-id>/requirement.md` file takes the workload-id from
 * its directory; any other file name stands in for the workload itself. */
function workloadFromPath(filePath) {
  const base = path.basename(filePath);
  if (/^requirement\.[a-z0-9]+$/i.test(base)) {
    return path.basename(path.dirname(filePath));
  }
  return base;
}

/* ---------------------------------------------------------------------------
 * DAG construction (spec §6, §7; conventions/gates.md). Pure: returns the
 * plan; createRun() performs the SDK calls.
 * ------------------------------------------------------------------------- */

/** Gate law (§5.2): every node names the evidence its completion gate checks.
 * assertPlanGatesHaveEvidence() refuses to dispatch a plan where any node
 * could complete on an agent's word. */
function assertPlanGatesHaveEvidence(plan) {
  for (const node of plan.nodes) {
    if (!Array.isArray(node.evidence) || node.evidence.length === 0) {
      throw new RunStatusError(
        `node "${node.key}" declares no evidence artifact; every gate requires evidence (§5.2)`
      );
    }
  }
  return true;
}

/** All dependency keys must exist and the graph must be acyclic. */
function validatePlan(plan) {
  const keys = new Set(plan.nodes.map((n) => n.key));
  for (const node of plan.nodes) {
    for (const dep of node.dependsOn) {
      if (!keys.has(dep)) {
        throw new RunStatusError(`node "${node.key}" depends on unknown node "${dep}"`);
      }
    }
  }
  // Cycle check: repeatedly strip nodes whose dependencies are all satisfied.
  const remaining = new Set(plan.nodes.map((n) => n.key));
  const depsOf = new Map(plan.nodes.map((n) => [n.key, n.dependsOn]));
  let progressed = true;
  while (progressed && remaining.size > 0) {
    progressed = false;
    for (const key of remaining) {
      if (depsOf.get(key).every((d) => !remaining.has(d))) {
        remaining.delete(key);
        progressed = true;
      }
    }
  }
  if (remaining.size > 0) {
    throw new RunStatusError(`dependency cycle among: ${[...remaining].sort().join(', ')}`);
  }
  assertPlanGatesHaveEvidence(plan);
  return true;
}

function buildRunPlan({ requirement, requirementPath, budgets, runId, recordedAt, executor = 'obvious' }) {
  const b = budgets; // already validated via parseBudgets
  const requirementChars = requirement.length;

  const descriptionFor = (node) =>
    [
      `Stage ${node.stage} of 8 (spec §6): ${node.action}.`,
      `Role: ${node.role} (spec ${node.specRef}).`,
      `Evidence required to complete (§5.2, conventions/gates.md): ${node.evidence.join('; ')}.`,
      `Gate: ${node.gate} Agents never mark their own completion.`,
      node.bounded ? `Bounded: at most ${b.maxRepairAttempts} repair attempts (§7.3). ` +
        `When the limit is reached, the runbook writes run status needs_human with a failure summary. ` +
        `No test may be weakened or deleted (§11.4); any generated-test change requires a justification ` +
        `artifact linked to a criterion id (R2).` : '',
    ].filter(Boolean).join('\n');

  const stage = (key, stage, action, role, specRef, dependsOn, evidence, gate, extra = {}) => ({
    key,
    kind: 'stage',
    stage,
    action,
    role,
    specRef,
    dependsOn,
    evidence,
    gate,
    ...extra,
  });

  const nodes = [
    stage(
      'requirements', 1, 'interpret the feature requirement into acceptance criteria',
      'Requirements Agent', '§7.1', [],
      ['acceptance-criteria config validating against schemas/completeness-criteria.schema.json (artifact type: spec)'],
      'config validates; every criterion has id, statement, check_type, source; assumptions carry an explicit note.'
    ),
    stage(
      'architecture', 2, 'define the API contract and data model',
      'Architecture Agent', '§7.2', ['requirements'],
      ['technical specification (artifact type: spec)'],
      'every acceptance criterion maps to at least one component; dependencies minimal and pinned.'
    ),
    stage(
      'plan', 3, 'break the implementation into ordered tasks with dependencies and budgets',
      'Task Orchestrator', '§7.3', ['architecture'],
      ['execution plan (artifact type: spec) with retry, iteration, time, and credit budgets recorded'],
      'every §6 stage has an owning task; all four budget classes recorded before dispatch.'
    ),
    stage(
      'coding', 4, 'write the implementation through file tools, task by task',
      'Coding Agent', '§7.4', ['plan'],
      ['per-task diffs produced through file tools (artifact type: diff)'],
      'diffs produced through file tools only — no manual code edits (§12.1).',
      { bounded: true }
    ),
    stage(
      'testing', 5, 'generate unit tests from the acceptance criteria and execute them in the sandbox',
      'Testing Agent', '§7.6', ['coding'],
      ['structured test results (artifact type: test_output)', 'test manifest: path + SHA-256 per test file (R2, schemas/test-manifest.schema.json)'],
      'tests derive from acceptance criteria, not from reading the implementation alone (§7.6); manifest recorded at finalization (R2).'
    ),
    stage(
      'debug-retest', 6, 'diagnose failures, apply minimal fixes, and retest',
      'Debugging Agent', '§7.7', ['testing'],
      ['attempt record per repair: failing test, change summary, retest result (artifact type: diff + test_output)'],
      'every attempt logged (§7.7); no test weakened or deleted (§11.4); test-file changes justified against a criterion id (R2).',
      { bounded: true }
    ),
    {
      key: 'verify', kind: 'gate', stage: 7,
      action: 'rerun tests and run code-quality checks (lint, types, complexity, dependencies, security)',
      role: 'Code Quality Checks', specRef: '§7.8', dependsOn: ['debug-retest'],
      evidence: [
        'verification report (artifact type: report)',
        'manifest digests re-hashed and matching (R2): python -m qualityforge.tools.validate manifest <manifest> --repo-root .',
      ],
      gate: '100% of generated tests pass (§12.2) and every manifest digest matches — drift fails the gate (R2).',
    },
    {
      key: 'human-review', kind: 'human-gate', stage: 8,
      action: 'review the evidence package: plan, diffs, test results, repair history, verification report',
      role: 'Human Review Gate', specRef: '§7.9', dependsOn: ['verify'],
      evidence: ['complete evidence package', 'Approval record (approve | request_changes | reject) on the delivery gate'],
      gate: 'the run holds at awaiting_approval until an Approval record exists (§7.9); nothing is delivered without one.',
    },
    {
      key: 'delivery', kind: 'delivery', stage: 8,
      action: 'execute the gate decision and close the run',
      role: 'Delivery', specRef: '§6', dependsOn: ['human-review'],
      evidence: ['pull request or reviewed code artifact', 'Approval record (§7.9)'],
      gate: 'approve → run status delivered; request_changes → noted stage restarts; reject → run status rejected (§7.9).',
    },
  ].map((node) => ({
    ...node,
    title: `[QF ${runId}] ${node.stage} · ${node.key}`,
    description: descriptionFor(node),
  }));

  const budgetRecord = buildBudgetRecord(b, { requirementPath, requirementChars, recordedAt });
  const rootDescription = [
    `QualityForge run ${runId} — instantiated by the factory runbook (review R8).`,
    `Requirement: ${requirementPath} (${requirementChars} chars).`,
    '',
    'Budgets recorded before dispatch (spec §7.3, §10):',
    ...BUDGET_FIELDS.map(([key, label]) => `- ${label}: ${budgetRecord[key]}`),
    `Enforcement: ${budgetRecord.enforced}.`,
    '',
    `Run statuses are written only by the runbook (R8), restricted to spec §9: ${RUN_STATUSES.join(', ')}.`,
    `Escalation: when retry, iteration, time, or credit limits are reached the run stops with status needs_human and a failure summary (§7.3).`,
    'Synthetic data only (§11.1). No clinical validity claims (§11.2).',
    '',
    'Requirement text:',
    '---',
    requirement.length > 4000 ? `${requirement.slice(0, 4000)}\n[... truncated, full text in the requirement file]` : requirement,
    '---',
  ].join('\n');

  const plan = {
    runId,
    executor,
    requirementPath,
    requirementChars,
    budgets: b,
    budgetRecord,
    recordedAt,
    root: { key: 'run', title: `QualityForge run ${runId}`, description: rootDescription },
    nodes,
  };
  validatePlan(plan);
  return plan;
}

/* ---------------------------------------------------------------------------
 * Dispatch: the only place this script touches the SDK.
 * ------------------------------------------------------------------------- */

/** Instantiate the run on the workspace. `sdkClient` is injected (tests pass a
 * mock; the CLI passes the real SDK). Creates the run root with the budget
 * record first, then each node in dependency order, wiring dependsOn to real
 * task ids, then opens the run at its first stage status. */
async function createRun({ plan, sdkClient }) {
  validatePlan(plan);

  const root = await sdkClient.tasks.create({
    title: plan.root.title,
    description: plan.root.description, // budgets recorded before dispatch (§7.3)
    // Live tasks.create contract: a create with no parentId/assignee has no
    // valid shape. The run is a plan under the dispatching task's tree.
    parentId: 'self',
  });
  if (!root || !root.id) {
    throw new RunStatusError('task creation returned no root task id; refusing to dispatch stages');
  }

  const ids = new Map([['run', root.id]]);
  for (const node of plan.nodes) {
    for (const dep of node.dependsOn) {
      if (!ids.has(dep)) {
        // Construction guarantees ordering; this is a guard, not dead code —
        // a future edit that reorders nodes must fail loudly, not mislink.
        throw new RunStatusError(`node "${node.key}" depends on "${dep}", which has not been created`);
      }
    }
    const params = {
      title: node.title,
      description: node.description,
      parentId: root.id,
      dependsOn: node.dependsOn.map((dep) => ids.get(dep)),
    };
    if (node.kind === 'human-gate') {
      // Native human review task (§7.9): assignee human + humanKind review,
      // with the attention summary required at creation. The review target —
      // the evidence package — is supplied by the orchestrator at start.
      params.assignee = 'human';
      params.humanKind = 'review';
      params.attention = { summary: `Human review gate for run ${plan.runId}: approve, request changes, or reject (§7.9).` };
    } else {
      params.suggestedExecutor = plan.executor;
    }
    const created = await sdkClient.tasks.create(params);
    if (!created || !created.id) {
      throw new RunStatusError(`task creation returned no id for node "${node.key}"`);
    }
    ids.set(node.key, created.id);
  }

  // Opening run status: the first stage begins when the orchestrator starts
  // the requirements task. Written through the R8 writer like every other.
  await writeRunStatus({ sdkClient, runTaskId: root.id, current: null, next: 'analyzing', reason: 'run instantiated; stage 1 (Analyze) dispatched' });

  const tasks = Object.fromEntries(ids);
  return { runId: plan.runId, rootTaskId: root.id, tasks, budgetRecord: plan.budgetRecord };
}

/* ---------------------------------------------------------------------------
 * Dry-run rendering.
 * ------------------------------------------------------------------------- */

function renderTaskTree(plan, { dryRun = true } = {}) {
  const b = plan.budgets;
  const lines = [];
  lines.push(`QualityForge run ${plan.runId}${dryRun ? '  (dry run — nothing was created)' : ''}`);
  lines.push(`Requirement: ${plan.requirementPath} (${plan.requirementChars} chars, synthetic data only §11.1)`);
  lines.push(`Budgets recorded before dispatch (§7.3, §10): time ${b.timeBudgetMinutes} min · credits ${b.creditBudget} · repair attempts ≤ ${b.maxRepairAttempts} · iterations ≤ ${b.maxIterations}`);
  lines.push(`Terminal statuses (R8, §9): ${TERMINAL_STATUSES.join(' | ')} — limits reached → needs_human with a failure summary`);
  lines.push('');
  lines.push(`${plan.root.title}`);
  for (const node of plan.nodes) {
    const deps = node.dependsOn.length > 0 ? `  ← ${node.dependsOn.join(', ')}` : '';
    lines.push(`  [${node.kind}] ${node.key}${deps}`);
    lines.push(`      ${node.role} (§6 stage ${node.stage}) — ${node.action}`);
    for (const ev of node.evidence) {
      lines.push(`      evidence: ${ev}`);
    }
  }
  lines.push('');
  lines.push('Every gate completes only on its evidence artifact; agents never mark their own completion (§5.2).');
  return lines.join('\n');
}

/* ---------------------------------------------------------------------------
 * CLI plumbing. The 'obvious' SDK is required lazily — only on a real
 * dispatch — so dry-run and unit tests need neither the package nor a token.
 * ------------------------------------------------------------------------- */

const USAGE = `Usage: node qualityforge/factory/run.js <requirement-file> [options]

Options:
  --dry-run                  print the task tree; create nothing
  --json                     with --dry-run: emit the plan as JSON
  --max-repair-attempts N    bounded debug-retest loop (default 3, spec §7.3)
  --max-iterations N         max total iterations per run (default 8)
  --time-budget-minutes N    per-run time budget (default 15, spec §10)
  --credit-budget N          per-run credit budget (default 60)
  --executor NAME            suggested executor for stage tasks:
                             obvious | autobuild | human (default obvious)
  -h, --help                 show this help`;

const EXECUTORS = ['obvious', 'autobuild', 'human'];

function parseArgs(argv) {
  const opts = { dryRun: false, json: false, executor: 'obvious', budgets: {}, positional: [], help: false };
  const budgetFlags = {
    '--max-repair-attempts': 'maxRepairAttempts',
    '--max-iterations': 'maxIterations',
    '--time-budget-minutes': 'timeBudgetMinutes',
    '--credit-budget': 'creditBudget',
  };
  for (let i = 0; i < argv.length; i++) {
    const arg = argv[i];
    if (arg === '--dry-run') { opts.dryRun = true; continue; }
    if (arg === '--json') { opts.json = true; continue; }
    if (arg === '-h' || arg === '--help') { opts.help = true; continue; }
    if (budgetFlags[arg]) {
      const value = argv[++i];
      if (value === undefined) throw new UsageError(`${arg} requires a value`);
      opts.budgets[budgetFlags[arg]] = Number(value);
      continue;
    }
    if (arg === '--executor') {
      opts.executor = argv[++i];
      if (!EXECUTORS.includes(opts.executor)) {
        // custom-agent needs a catalog agent id the factory does not manage yet.
        throw new UsageError(`--executor must be one of ${EXECUTORS.join(' | ')}`);
      }
      continue;
    }
    if (arg.startsWith('--')) throw new UsageError(`unknown option ${arg}`);
    opts.positional.push(arg);
  }
  return opts;
}

function loadRequirement(filePath) {
  const resolved = path.resolve(filePath);
  let text;
  try {
    text = fs.readFileSync(resolved, 'utf8');
  } catch (err) {
    const reason = err && err.code === 'ENOENT' ? 'file not found' : `${err.code || err.name}`;
    throw new UsageError(`cannot read requirement file ${resolved}: ${reason}`);
  }
  if (!text.trim()) {
    throw new UsageError(`requirement file ${resolved} is empty; a run needs a requirement (R8)`);
  }
  return { resolved, text };
}

async function main({ argv, env, requireFn = require } = {}) {
  const options = parseArgs(argv || []);
  if (options.help) {
    console.log(USAGE);
    return { helped: true };
  }
  if (options.positional.length !== 1) {
    throw new UsageError('exactly one requirement file path is required\n' + USAGE);
  }

  const { resolved, text } = loadRequirement(options.positional[0]);
  const budgets = parseBudgets(options.budgets);
  const now = new Date();
  const runId = buildRunId(workloadFromPath(resolved), now);
  const plan = buildRunPlan({
    requirement: text,
    requirementPath: resolved,
    budgets,
    runId,
    recordedAt: now.toISOString(),
    executor: options.executor,
  });

  if (options.dryRun) {
    // No 'obvious' require happens on this path — by construction.
    if (options.json) {
      console.log(JSON.stringify({ dryRun: true, ...plan, nodes: plan.nodes }, null, 2));
    } else {
      console.log(renderTaskTree(plan));
    }
    return { plan, dryRun: true };
  }

  if (!env || !env.API_TOKEN) {
    throw new UsageError('API_TOKEN must be set in the environment for a real dispatch (dry-run needs no token)');
  }
  const { sdk } = requireFn('obvious');
  sdk.configure({ tokenRefresh: async () => env.API_TOKEN });
  const result = await createRun({ plan, sdkClient: sdk });
  console.log(JSON.stringify({ dispatched: true, ...result }, null, 2));
  return { plan, dispatched: result };
}

if (require.main === module) {
  main({ argv: process.argv.slice(2), env: process.env })
    .catch((err) => {
      console.error(err instanceof UsageError ? `usage: ${err.message}` : `${err.name}: ${err.message}`);
      process.exitCode = err instanceof UsageError ? 2 : 1;
    });
}

module.exports = {
  RUN_STATUSES,
  TERMINAL_STATUSES,
  isRunStatus,
  isTerminalStatus,
  workloadFromPath,
  TASK_STATUS_FOR_TERMINAL,
  BUDGET_DEFAULTS,
  RunStatusError,
  UsageError,
  assertTransition,
  decideTerminalStatus,
  writeRunStatus,
  parseBudgets,
  buildBudgetRecord,
  buildRunId,
  buildRunPlan,
  validatePlan,
  assertPlanGatesHaveEvidence,
  createRun,
  renderTaskTree,
  parseArgs,
  loadRequirement,
  main,
};
