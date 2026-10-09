# Dispatch log — qf-run-1-soap-20261009T172617Z

## Outcome

**Live task-DAG instantiation was not possible from this delegated thread.** Every
task-creation shape the surface documents was attempted and refused. The run
proceeds in-role per §6 with run state recorded here and stage evidence under
`evidence/`; the gate conventions (§6, conventions/gates.md), §9 status enum,
budgets, and terminal-status rule are applied unchanged. This log is the honest
record of the platform gap; it is included in the delivery PR body.

## Probe matrix (Oct 9, 2026, sdk v3.66.3, project prj_k23rW7Ra)

| # | Shape attempted | Server response |
| --- | --- | --- |
| 1 | run root, no parent, no assignee (plan shape) | `VALIDATION_FAILED` — "Pick a shape: parentId … for your own plan … or assignee alone … for an independent root" |
| 2 | run root, `parentId: 'self'` | `SDKError` — "Delegated agents cannot use parentId=self — that would seed a second root. Pass your bound task id" |
| 3 | run root, `parentId: todo_N2JgOZyM` (bound task) | `SDKError` — "Parent task … is not the root task — delegated subtasks must be direct children of the root (depth 1). Pass --parentId=self to target your root directly" |
| 4 | single probe task, `--parentId=todo_5wkVC40o` (tree root, camelCase and kebab-case) | `NOT_FOUND` — "Task not found" |
| 5 | single probe task, `--assignee=obvious` (independent root) | `FORBIDDEN` — "Delegated agents cannot create independent tasks. Do the work yourself, track it with a subtask under your own task (parentId) …" |
| 6 | single probe task, `--parentId=todo_N2JgOZyM --assignee=obvious` | `VALIDATION_FAILED` — same as #3 |
| 7 | single probe task, `--parentId=self --assignee=obvious` | HTTP 500 once, then `FORBIDDEN` — same as #2 |

Shapes #2/#3 contradict: #2 forbids `'self'` and names the bound task id as the
alternative; #3 forbids the bound task id and names `'self'` as the alternative.
Shape #4 shows the tree root (`todo_5wkVC40o`, the only depth-1 parent the depth
rule in #3/#6 would accept) is not addressable for parenting by this thread.
Shape #5 forbids the remaining unparented shape. #7 was the last untested
combination. All probe tasks that errored client-side were never created; no
orphan tasks exist (verified via `obvious tasks list`).

## What proceeds unchanged

- The runbook plan (dry-run JSON, `plan.json`) is the DAG definition: run root +
  9 nodes with dependency edges, budgets recorded pre-run.
- Stage execution follows §6 with the merged agent prompts (qualityforge/agents/),
  gate conventions, §9 statuses, and the R8 terminal-writer rule.
- Every stage transition and evidence artifact is recorded in `run-state.json`
  and this directory; the Verify gate re-hashes the test manifest per R2.
- The run ends in a defined status: `needs_human` at the human review gate
  (§9), with the evidence package on the delivery PR.

## Unblock path (for the orchestrator)

A thread with rights over `todo_5wkVC40o` (the orchestrator) can create the run
DAG under it in one pass using `qualityforge/factory/run.js` (plan.json has the
exact titles/descriptions/edges); this thread can then drive stage statuses via
`tasks update` and link evidence per gate.
