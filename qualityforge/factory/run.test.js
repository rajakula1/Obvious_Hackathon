'use strict';

/**
 * Unit tests for the factory runbook (qualityforge/factory/run.js).
 *
 * Coverage per the task brief: DAG construction, budget recording, and
 * terminal-state enforcement, all against a mocked SDK client. The suite
 * pins the run-status enum to BOTH qualityforge/run_status.py and the spec
 * section 9 line, so a status that is not in the spec cannot be written by
 * any code path — "runs ending in an undefined state: 0" (§12.2).
 *
 * Runs with: node --test qualityforge/factory/
 */

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { test } = require('node:test');
const { spawnSync } = require('node:child_process');

const run = require('./run.js');

const SAMPLE_REQUIREMENT = path.join(__dirname, '..', 'requirements', 'run-1-soap.md');

/** Build a deterministic plan (no clock, no filesystem). */
function makePlan({ budgets = {}, requirement } = {}) {
  return run.buildRunPlan({
    requirement: requirement || 'Build a Python API that evaluates SOAP note completeness.',
    requirementPath: 'qualityforge/workloads/soap-completeness-evaluator/requirement.md',
    budgets: run.parseBudgets(budgets),
    runId: 'qf-test-20261009T000000Z',
    recordedAt: '2026-10-09T00:00:00.000Z',
    executor: 'obvious',
  });
}

/** Mocked SDK: records every call, mints deterministic task ids. */
function mockSdk() {
  const calls = { create: [], update: [], feedback: [] };
  let counter = 0;
  const sdkClient = {
    tasks: {
      create: async (params) => {
        calls.create.push(params);
        return { id: `t${++counter}` };
      },
      update: async (params) => {
        calls.update.push(params);
        return { ok: true };
      },
      feedback: {
        create: async (params) => {
          calls.feedback.push(params);
          return { ok: true };
        },
      },
    },
  };
  return { sdkClient, calls };
}

test('run statuses mirror run_status.py and the spec §9 line exactly', () => {
  const pySource = fs.readFileSync(path.join(__dirname, '..', 'run_status.py'), 'utf8');
  const pyStatuses = [...pySource.matchAll(/=\s*"([a-z_]+)"/g)].map((m) => m[1]);

  const specPath = path.join(__dirname, '..', '..', 'Praxify QualityForge Specification.md');
  const spec = fs.readFileSync(specPath, 'utf8');
  const line = spec.match(/Run statuses: ([^\n]+)\n/);
  assert.ok(line, 'spec section 9 run-status line not found');
  const specStatuses = [...line[1].matchAll(/`([a-z_]+)`/g)].map((m) => m[1]);

  assert.deepEqual(pyStatuses.sort(), [...run.RUN_STATUSES].sort());
  assert.deepEqual(specStatuses.sort(), [...run.RUN_STATUSES].sort());
  assert.equal(run.RUN_STATUSES.length, 10);
  assert.deepEqual([...run.TERMINAL_STATUSES].sort(), ['delivered', 'needs_human', 'rejected']);
  for (const terminal of run.TERMINAL_STATUSES) {
    assert.ok(run.isRunStatus(terminal));
    assert.ok(run.isTerminalStatus(terminal));
  }
  assert.ok(!run.isRunStatus('done'));
  assert.ok(!run.isTerminalStatus('awaiting_approval'));
});

test('DAG: instantiates every pipeline stage of §6 in order', () => {
  const plan = makePlan();
  assert.deepEqual(
    plan.nodes.map((n) => n.key),
    ['requirements', 'architecture', 'plan', 'coding', 'testing', 'debug-retest', 'verify', 'human-review', 'delivery']
  );
  assert.equal(plan.nodes[0].role, 'Requirements Agent');
  assert.equal(plan.nodes[5].role, 'Debugging Agent');
  assert.equal(plan.nodes[7].role, 'Human Review Gate');
});

test('DAG: dependency edges chain the pipeline', () => {
  const plan = makePlan();
  const depsOf = Object.fromEntries(plan.nodes.map((n) => [n.key, n.dependsOn]));
  assert.deepEqual(depsOf.requirements, []);
  assert.deepEqual(depsOf.architecture, ['requirements']);
  assert.deepEqual(depsOf.plan, ['architecture']);
  assert.deepEqual(depsOf.coding, ['plan']);
  assert.deepEqual(depsOf.testing, ['coding']);
  assert.deepEqual(depsOf['debug-retest'], ['testing']);
  assert.deepEqual(depsOf.verify, ['debug-retest']);
  assert.deepEqual(depsOf['human-review'], ['verify']);
  assert.deepEqual(depsOf.delivery, ['human-review']);
});

test('DAG: every node declares evidence, gates are typed, DAG is valid', () => {
  const plan = makePlan();
  assert.ok(run.validatePlan(plan));
  for (const node of plan.nodes) {
    assert.ok(node.evidence.length > 0, `node ${node.key} has no evidence`);
  }
  const kinds = Object.fromEntries(plan.nodes.map((n) => [n.key, n.kind]));
  assert.equal(kinds.verify, 'gate');
  assert.equal(kinds['human-review'], 'human-gate');
  assert.equal(kinds.delivery, 'delivery');
});

test('DAG: validatePlan rejects unknown deps, cycles, and evidence-free gates', () => {
  assert.throws(
    () => run.validatePlan({ nodes: [{ key: 'a', dependsOn: ['ghost'], evidence: ['x'] }] }),
    /unknown node/,
  );
  assert.throws(
    () => run.validatePlan({
      nodes: [
        { key: 'a', dependsOn: ['b'], evidence: ['x'] },
        { key: 'b', dependsOn: ['a'], evidence: ['x'] },
      ],
    }),
    /cycle/,
  );
  assert.throws(
    () => run.validatePlan({ nodes: [{ key: 'a', dependsOn: [], evidence: [] }] }),
    /evidence/,
  );
});

test('budgets: defaults follow the spec (3 repair attempts, §7.3)', () => {
  const b = run.parseBudgets();
  assert.deepEqual({ ...b }, {
    maxRepairAttempts: 3,
    maxIterations: 8,
    timeBudgetMinutes: 15,
    creditBudget: 60,
  });
  assert.deepEqual({ ...run.parseBudgets({ maxRepairAttempts: 5, creditBudget: 120 }) }, {
    ...run.BUDGET_DEFAULTS,
    maxRepairAttempts: 5,
    creditBudget: 120,
  });
});

test('budgets: invalid values fail before dispatch, naming the field', () => {
  for (const bad of [0, -1, 2.5, NaN, 'many', null]) {
    assert.throws(() => run.parseBudgets({ maxRepairAttempts: bad }), RangeError, `accepted ${bad}`);
    assert.throws(() => run.parseBudgets({ creditBudget: bad }), RangeError, `accepted ${bad}`);
  }
});

test('budgets: recorded on the run root BEFORE dispatch (§7.3, §10)', () => {
  const plan = makePlan({ budgets: { maxRepairAttempts: 3, creditBudget: 45 } });
  const desc = plan.root.description;
  assert.match(desc, /Budgets recorded before dispatch/);
  assert.match(desc, /- max repair attempts: 3/);
  assert.match(desc, /- max iterations: 8/);
  assert.match(desc, /- time budget \(minutes\): 15/);
  assert.match(desc, /- credit budget: 45/);
  assert.match(desc, /recorded pre-run and reconciled after the run; not platform-enforced/);
  assert.equal(plan.budgetRecord.recorded, 'before dispatch (spec §7.3, §10)');
  assert.equal(plan.budgetRecord.recordedAt, '2026-10-09T00:00:00.000Z');
  // The bounded debug-retest node carries the attempt limit in its task text.
  const debugNode = plan.nodes.find((n) => n.key === 'debug-retest');
  assert.match(debugNode.description, /at most 3 repair attempts/);
  assert.match(debugNode.description, /needs_human with a failure summary/);
});

test('terminal enforcement: an undefined status fails loudly with ZERO SDK calls', async () => {
  const { sdkClient, calls } = mockSdk();
  for (const bad of ['done', 'DELIVERED', 'success', '', undefined]) {
    await assert.rejects(
      () => run.writeRunStatus({ sdkClient, runTaskId: 't1', current: 'testing', next: bad }),
      (err) => {
        assert.ok(err instanceof run.RunStatusError);
        assert.match(err.message, /not a spec §9 run status/);
        return true;
      },
      `accepted ${String(bad)}`,
    );
  }
  assert.equal(calls.create.length + calls.update.length + calls.feedback.length, 0);
  // Same guard on the pure transition check.
  assert.throws(() => run.assertTransition('testing', 'shipped'), run.RunStatusError);
  assert.throws(() => run.assertTransition('shipped', 'testing'), run.RunStatusError);
});

test('terminal enforcement: a run ends exactly once and never opens terminal', async () => {
  const { sdkClient, calls } = mockSdk();
  // A run cannot OPEN on a terminal status.
  await assert.rejects(
    () => run.writeRunStatus({ sdkClient, runTaskId: 't1', current: null, next: 'delivered' }),
    run.RunStatusError,
  );
  // After a terminal write, nothing more may be written.
  await run.writeRunStatus({ sdkClient, runTaskId: 't1', current: 'verifying', next: 'delivered', reason: 'approved' });
  for (const next of run.RUN_STATUSES) {
    await assert.rejects(
      () => run.writeRunStatus({ sdkClient, runTaskId: 't1', current: 'delivered', next }),
      /run already ended/,
    );
  }
  // One feedback log + one terminal task-status update, nothing else.
  assert.equal(calls.feedback.length, 1);
  assert.equal(calls.update.length, 1);
  assert.equal(calls.update[0].status, 'completed'); // delivered → completed
  assert.match(calls.update[0].completionNote, /delivered/);
});

test('limits reached → needs_human with a failure summary (§7.3)', () => {
  const decision = run.decideTerminalStatus({ limitReached: true, failureSummary: 'repair budget exhausted after 3 attempts' });
  assert.deepEqual(decision, {
    status: 'needs_human',
    summary: 'repair budget exhausted after 3 attempts',
  });
  // An escalation WITHOUT a summary is a silent failure — refused.
  assert.throws(
    () => run.decideTerminalStatus({ limitReached: true, failureSummary: '   ' }),
    run.RunStatusError,
  );
  // No limits, no approval → nothing terminal is invented.
  assert.equal(run.decideTerminalStatus({}), null);
});

test('gate decisions: approve → delivered, reject → rejected, request_changes → stage restart', () => {
  assert.equal(run.decideTerminalStatus({ approval: { decision: 'approve', reviewer: 'founder' } }).status, 'delivered');
  assert.equal(run.decideTerminalStatus({ approval: { decision: 'Approve' } }).status, 'delivered');
  assert.equal(run.decideTerminalStatus({ approval: { decision: 'reject' } }).status, 'rejected');
  assert.equal(run.decideTerminalStatus({ approval: { decision: 'request_changes', notes: 'fix criterion C3' } }), null);
  assert.throws(() => run.decideTerminalStatus({ approval: { decision: 'maybe' } }), /unknown approval decision/);
});

test('createRun: dispatches the DAG with real ids, budgets, and the human gate (mocked SDK)', async () => {
  const { sdkClient, calls } = mockSdk();
  const plan = makePlan({ budgets: { creditBudget: 30 } });
  const result = await run.createRun({ plan, sdkClient });

  // Root + 9 nodes, root first (budgets recorded before any stage dispatch).
  assert.equal(calls.create.length, 10);
  assert.match(calls.create[0].description, /- credit budget: 30/);
  assert.match(calls.create[0].description, /QualityForge run qf-test-20261009T000000Z/);
  assert.equal(result.rootTaskId, 't1');

  // dependsOn edges point at the REAL created ids, not plan keys.
  const byKey = {};
  const order = ['run', ...plan.nodes.map((n) => n.key)];
  order.forEach((key, i) => { byKey[key] = `t${i + 1}`; });
  assert.equal(result.tasks.architecture, byKey.architecture);
  const createFor = (key) => calls.create[order.indexOf(key)];
  assert.deepEqual(createFor('architecture').dependsOn, [byKey.requirements]);
  assert.deepEqual(createFor('verify').dependsOn, [byKey['debug-retest']]);
  assert.deepEqual(createFor('delivery').dependsOn, [byKey['human-review']]);
  for (const node of plan.nodes) {
    assert.equal(createFor(node.key).parentId, byKey.run, `${node.key} must be a child of the run root`);
  }

  // The human gate is a native human review task (§7.9).
  const review = createFor('human-review');
  assert.equal(review.assignee, 'human');
  assert.equal(review.humanKind, 'review');
  assert.match(review.attention.summary, /Human review gate/);
  // Stage tasks are planned work with a suggested executor, not fake humans.
  assert.equal(createFor('coding').suggestedExecutor, 'obvious');

  // Opening run status written through the R8 writer.
  assert.equal(calls.feedback.length, 1);
  assert.match(calls.feedback[0].body, /run status → analyzing/);
  assert.equal(calls.update.length, 0); // opening write is not terminal
});

test('dry-run: renders the task tree without touching the SDK', async () => {
  const requireFn = () => { throw new Error('dry-run must not require the SDK'); };
  const result = await run.main({
    argv: [SAMPLE_REQUIREMENT, '--dry-run'],
    env: {},
    requireFn,
  });
  assert.ok(result.dryRun);
  assert.ok(result.plan);
  assert.ok(run.validatePlan(result.plan));

  const tree = run.renderTaskTree(result.plan);
  assert.match(tree, /\(dry run — nothing was created\)/);
  for (const key of ['requirements', 'architecture', 'plan', 'coding', 'testing', 'debug-retest', 'verify', 'human-review', 'delivery']) {
    assert.ok(tree.includes(key), `tree missing ${key}`);
  }
  assert.match(tree, /← testing/); // debug-retest edge
  assert.match(tree, /repair attempts ≤ 3/);
  assert.match(tree, /needs_human/);
});

test('CLI: dry-run against the sample requirement exits 0 and prints the tree', () => {
  const script = path.join(__dirname, 'run.js');
  const proc = spawnSync(process.execPath, [script, SAMPLE_REQUIREMENT, '--dry-run'], { encoding: 'utf8' });
  assert.equal(proc.status, 0, `stderr: ${proc.stderr}`);
  // Workload id comes from the requirement file name (requirements/run-1-soap.md).
  assert.match(proc.stdout, /QualityForge run qf-run-1-soap-/);
  assert.match(proc.stdout, /\[human-gate\] human-review/);
  assert.match(proc.stdout, /\[delivery\] delivery {2}← human-review/);
});

test('CLI: missing requirement file exits 2 with a usage error', () => {
  const script = path.join(__dirname, 'run.js');
  const proc = spawnSync(process.execPath, [script, 'no/such/requirement.md', '--dry-run'], { encoding: 'utf8' });
  assert.equal(proc.status, 2);
  assert.match(proc.stderr, /cannot read requirement file/);
});

test('CLI: rejects unknown options, bad executors, and a dispatch without a token', async () => {
  assert.throws(() => run.parseArgs(['--bogus']), run.UsageError);
  assert.throws(() => run.parseArgs(['--credit-budget']), run.UsageError);
  assert.throws(() => run.parseArgs(['--executor', 'custom-agent']), run.UsageError);
  await assert.rejects(
    () => run.main({ argv: [SAMPLE_REQUIREMENT], env: {}, requireFn: () => ({}) }),
    /API_TOKEN/,
  );
});
