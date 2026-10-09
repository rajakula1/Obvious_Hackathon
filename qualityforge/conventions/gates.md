# Evidence and gate conventions

What each pipeline stage must produce and what its completion gate checks before
the run may advance. Governing principle, spec section 5.2: **evidence over
assertion** — a gate checks a persisted artifact, not an agent's word. The
runbook script (review R8) instantiates these gates as tasks with dependencies;
agents never mark their own completion.

## Artifact types

Spec section 9 fixes the artifact-type vocabulary. Every stage's evidence is one of:

| Type | Content | Produced in |
|---|---|---|
| `spec` | Acceptance criteria, technical specification, execution plan | Stages 1–3 |
| `diff` | Per-task code changes, produced through file tools | Stages 4, 6 |
| `test_output` | Structured results: tests run/passed/failed, messages, traces | Stages 5–7 |
| `report` | Verification report and final evaluation report | Stages 7–8 |

Approval is not an artifact type: it is an Approval record on the delivery task's
completion gate (spec sections 7.9 and 9).

## Stage evidence and gates

| Stage (spec §6) | Autonomous action | Required evidence | Gate — advance only if |
|---|---|---|---|
| 1. Analyze | Interpret the feature requirement | Acceptance-criteria config (schema: `../schemas/completeness-criteria.schema.json`) | Config validates; every criterion has `id`, `statement`, `check_type`, `source`; assumptions carry an explicit `note` (§7.1) |
| 2. Design | Define the API contract and data model | Technical specification (`spec`) | Every criterion maps to at least one component (§7.2) |
| 3. Plan | Break implementation into tasks | Execution plan (`spec`): ordered tasks, dependencies, budgets | Every stage of §6 has an owning task; retry, iteration, time, and credit budgets recorded (§7.3) |
| 4. Generate | Write Python code through file tools | Per-task diff (`diff`) | Diffs produced through file tools only — no manual code edits (§12.1) |
| 5. Test | Generate and execute unit tests | Test results (`test_output`) plus the **test manifest** | Tests derive from acceptance criteria (§7.6); manifest recorded at finalization (R2) |
| 6. Debug | Analyze failures and modify code | Attempt record per repair: failing test, change summary, retest result | Every attempt logged (§7.7); no test weakened or deleted; any generated-test change justified against a criterion ID (§11.4, R2) |
| 7. Verify | Rerun tests and run code-quality checks | Verification report (`report`) | 100% of generated tests pass (§12.2); lint, types, complexity, dependencies, security pass (§7.8); manifest digests re-hashed and match (R2) — drift fails the gate |
| 8. Deliver | Package the changes for human review | Pull request via the GitHub integration plus the evidence package | Run holds at `awaiting_approval` until an Approval record exists (§7.9); only then `delivered` |

## Run statuses and who may write them

The ten run statuses are defined in spec section 9 and enumerated in
`../run_status.py` (`RunStatus`). Groupings:

- **Stage statuses** (§6): `analyzing`, `designing`, `generating`, `testing`,
  `debugging`, `verifying` — written as the run advances through the pipeline.
- **Human gate** (§7.9): `awaiting_approval` — the run pauses until an Approval
  record exists.
- **Terminal statuses**: `delivered` (approved), `rejected` (declined at the
  gate), `needs_human` (orchestrator escalation when retry, iteration, time, or
  credit limits are reached, §7.3).

**Writer rule (review R8):** only the runbook script writes terminal statuses.
No agent sets `delivered`, `needs_human`, or `rejected`; "runs ending in an
undefined state: 0" (§12.2) then holds by construction.

## Test-integrity rule (§11.4, review R2)

The Debugging Agent may not remove or weaken tests to force a pass. Mechanized
as three guards:

1. **Manifest**: when the Testing Agent finalizes tests, the orchestrator records
   a manifest artifact — one entry per test file: repository-relative path +
   SHA-256 (schema: `../schemas/test-manifest.schema.json`).
2. **Re-hash**: the Verify gate (§7.8) recomputes every digest before the quality
   report is issued; any drift fails the gate:
   `python -m qualityforge.tools.validate manifest <manifest> --repo-root .`
3. **Justification**: a change to a generated test file requires an artifact
   linking it to a criterion ID; at the PR layer, commits touching generated
   test files carry `criteria-ref: <criterion-id>` in the message.

## Run layout (review R7)

```
qualityforge/
  workloads/<workload-id>/requirement.md   # a run starts from a requirement file (R8)
  runs/<run_id>/                           # one self-contained, reviewable record (§9)
    01-analyze/  02-design/  03-plan/  04-generate/
    05-test/  06-debug/  07-verify/  08-deliver/
```

A second workload must run through the same layout with zero factory edits
(spec section 13, Goal 6).

## Inherited from the spec review

- **R1**: the defect-injection round is demo acceptance evidence, not an optional
  extension — a detection share below 80% is a reportable result, not a demo failure.
- **R4**: determinism is an acceptance criterion of the generated suite — two
  identical `POST /evaluate` calls return byte-identical JSON.
- **R6**: generated API tests run in-process (`TestClient`), never against a bound
  port — protects the 15-minute run budget (§10).
