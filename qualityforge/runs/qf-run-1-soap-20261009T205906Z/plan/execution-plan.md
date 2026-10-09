# Execution plan — Coding, Testing, and gates

Run: `qf-run-1-soap-20261009T205906Z` (Factory Run 2) · Stage 3 (§6 stage 3,
Task Orchestrator, §7.3) · Branch: `qualityforge/run-2-soap` (authored on tip
`4080eae`).
Input: the stage-2 technical specification
(`../architecture/technical-specification.md`) — worked from the file, not
from memory. Component linkage per planned task: `component-mapping.md` in
this directory.
Budget record: `budgets.json` in this directory — the four budget classes are
mirrored from the pre-dispatch record on the run root task `todo_KVNCN54J`
(spec §7.3, §10). This plan invents no new limits; reconcile-vs-actuals
happens at run end (§7.3, §10). Escalation on any limit: run stops with
status `needs_human` and a failure summary — the status is written only by
the runbook (R8).

## §6 stage coverage — the stage-3 gate

Every §6 stage has an owning task. Stages 1–3 own their completed stage tasks
(evidence of record on this branch); stages 4–8 own the ordered tasks in the
next section. "Runbook node" is the driver's DAG task id; "execution row" is
the delegated coder task the driver created per node.

| §6 stage | Owning task(s) | Runbook node · execution row | Status / evidence of record |
| --- | --- | --- | --- |
| 1. Analyze | Requirements Agent — stage task | `todo_WZgtYMAg` · `todo_WDNhjyJb` | COMPLETE — gate PASSED at `bb8d4dc`; `../requirements/acceptance-criteria.yaml` (8 criteria, v1.0.0) |
| 2. Design | Architecture Agent — stage task | `todo_itnRiF3Z` · `todo_Ap98lwE9` | COMPLETE — gate PASSED at `4080eae`; `../architecture/technical-specification.md` |
| 3. Plan | Task Orchestrator — this plan | `todo_mFL0FsKR` · `todo_kjayEN2c` | THIS ARTIFACT — `plan/execution-plan.md` + `plan/budgets.json` + `plan/component-mapping.md` |
| 4. Generate | C1–C4 — Coding Agent (§7.4) | `todo_aSDqoXR9` | pending |
| 5. Test | T1–T2 — Testing Agent (§7.6) | `todo_wjtn9Qd2` | pending |
| 6. Debug | D1 — Debugging Agent (§7.7) | `todo_tj830VjT` | pending — conditional at task level; the stage still records a zero-attempt outcome when T2 is green |
| 7. Verify | V1, I1, R1s — Quality Agent (§7.8) | `todo_OiOv0K4f` | pending |
| 8. Deliver | H1 — Human Review Gate (§7.9); DL — Delivery (§6) | `todo_C7EMb0mf` · `todo_11z7AjSf` | pending — H1 is assigned to the human reviewer; DL executes the gate decision |

## Ordered tasks (dependencies right-to-left)

Task granularity follows §7.4 — the Coding Agent works task by task from this
plan and produces a diff per task. The chain is deliberately sequential:
module dependencies chain C1→C4, and the suite builds on the whole package;
no independent task exists to parallelize, so §7.3's parallel-thread option
is unused and the 15-minute window is protected by R6 in-process testing.

| # | Task | Owning stage / role | Depends on | Expected evidence path | Gate — advance only if |
| --- | --- | --- | --- | --- | --- |
| C1 | (Re)generate `models.py` + `config.py`: TypedDict wire shapes (`EvaluateRequest`, `EvidenceSpan`, `Finding`, `EvaluateResponse`); criteria loader with required-key validation — `criteria_version`, `section_detection`, `criteria` — failing loudly on drift | 4. Generate / Coding Agent (§7.4; skills: soap-note-completeness, synthetic-data) | stage-2 spec (`../architecture/technical-specification.md`) | `../coding/stage-record.md` — per-task diff notes; code under `qualityforge/generated/soap_evaluator/` | Diffs produced through file tools only — no manual code edits (§12.1) |
| C2 | (Re)generate `sections.py`: case-insensitive line-start `header_markers` first (R5), documented fallback second; duplicate headers unify across occurrences; ambiguous → `partial`, never guessed | 4. Generate / Coding Agent (§7.4) | C1 | `../coding/stage-record.md` | same as C1 |
| C3 | (Re)generate `evaluator.py`: one check per configured criterion (S-01, S-02, O-01, O-02, A-01, P-01, P-02 plan-relation, X-01); `overall_status` all-present rule; `create_evaluator(config)` factory — the injection seam (R1) | 4. Generate / Coding Agent (§7.4) | C2 | `../coding/stage-record.md` | same as C1 |
| C4 | (Re)generate `app.py` + `__init__.py`: FastAPI wiring — POST /evaluate + GET /health; `EvaluateBody` producing the 422 surface; deterministic bodies in the fixed field order (R4) | 4. Generate / Coding Agent (§7.4) | C3 | `../coding/stage-record.md` | same as C1 |
| T1 | Generate the pytest suite from the stage-1 criteria: one test per criterion (criterion-tests skill), in-process `TestClient` — no bound ports (R6), evaluator + config obtained through the loader seam (`QUALITYFORGE_EVALUATOR_SPEC`) | 5. Test / Testing Agent (§7.6; skills: criterion-tests, in-process-testing, test-integrity) | C4 | `../testing/stage-record.md`; suite under `qualityforge/generated/tests/` | Tests derive from the acceptance criteria, not from reading the implementation alone (§7.6) |
| T2 | Execute the suite; record structured results (tests run/passed/failed, messages, traces); finalize the test manifest — path + SHA-256 per test file | 5. Test / Testing Agent (§7.6) | T1 | `../testing/test-results.txt` + `../testing/test-manifest.json` | Manifest recorded at finalization (R2) |
| D1 | Debug↔retest loop — runs only if T2 is red; ≤ 3 attempts, each logged (failing test, criterion id, change summary, retest result); FULL-suite retest per attempt; no test weakened or deleted (§11.4). If T2 is green first try: record the zero-attempt outcome | 6. Debug / Debugging Agent (§7.7; skills: bounded-repair, test-integrity) | T2 | `../debug-retest/repair-log.md` (+ per-attempt diff + test_output) | Every attempt logged (§7.7); no test weakened or deleted (§11.4); any generated-test change justified against a criterion id with a `criteria-ref:` commit marker (R2) |
| V1 | Verify gate: rerun the full suite (100% pass, §12.2), ruff at the pinned version (0.16.10), manifest re-hash — drift fails the gate (R2); budget reconciliation note | 7. Verify / Quality Agent (§7.8; skills: run-evidence, test-integrity) | T2 or D1 | `../verify/verification-report.md` + `../verify/gate-output.txt` | 100% of generated tests pass (§12.2); every manifest digest matches on re-hash (R2) |
| I1 | Injection round — demo acceptance evidence, not optional (R1): baseline spec (0 operators) + mutant runs via the harness; mutants exist only at the `create_evaluator` seam — the round never edits the implementation or the suite (§11.4, R2); the same suite file runs against baseline and every mutant; detection share reported either way | 7. Verify / Verifier role (harness-driven) | V1 | `../verify/injection-summary.md` (+ per-round machine output) | Detection share reported (below 80% is a reportable result, not a demo failure — R1) |
| R1s | Repair-loop evidence: if the natural run was green first try (D1 recorded zero attempts), the injection round supplies the detect→repair→retest material; attempts logged identically to D1 | 7. Verify / Verifier role | I1 | `../debug-retest/repair-log.md` | Same as D1 (§7.7, §11.4) |
| H1 | Human review gate: evidence package — plan, per-task diffs, test results, repair history, verification report, injection summary — presented for review; run holds at `awaiting_approval` until an Approval record exists | 8. Deliver / Human Review Gate (§7.9; runbook node `todo_C7EMb0mf`, assigned to the human reviewer) | V1 (+I1/R1s) | Approval record (`approve` \| `request_changes` \| `reject`) on the delivery gate — platform task state, not a file | Run holds at `awaiting_approval` until an Approval record exists (§7.9); nothing is delivered without one |
| DL | Delivery: execute the gate decision — approve → `delivered` with the PR via the GitHub integration; request_changes → noted stage restarts within budget; reject → `rejected` | 8. Deliver / Delivery (§6; runbook node `todo_11z7AjSf`) | H1 | Pull request or reviewed code artifact; approval record (§7.9) | Terminal status written only by the runbook (R8): approve → `delivered`; request_changes → restarts; reject → `rejected` |

## Budgets (summary — of-record copy in `budgets.json`)

Mirrored from the pre-dispatch record on run root `todo_KVNCN54J` (spec §7.3,
§10): repair attempts ≤ 3 per failure · iterations ≤ 8 per run · time ≤ 15
minutes of factory compute per suite execution window (protected by R6
in-process testing) · credits ≤ 60 per run. Enforcement: recorded pre-run and
reconciled after the run; not platform-enforced. Limits hit → `needs_human`
with a failure summary (§7.3, §9); only the runbook writes that status (R8).

## Integrity rules in force (no manual code edits)

- The Coding Agent (stage 4) writes ALL evaluator code through file tools,
  following `qualityforge/agents/coding/prompt.md`; the Testing Agent (stage
  5) writes ALL suite code through file tools following
  `qualityforge/agents/testing/prompt.md`.
- Test-file changes after the manifest is recorded require a justification
  artifact linked to a criterion ID and a `criteria-ref:` commit marker (R2).
- The harness applies mutants to the validated implementation — never the
  reverse; the suite file is byte-identical across baseline and mutant runs.
- Generated commits carry `criteria-ref:` markers where they touch
  criteria-linked behavior; the criterion IDs are the stage-1 config's:
  S-01, S-02, O-01, O-02, A-01, P-01, P-02, X-01.
- No agent writes a run status, a terminal status, or an approval (R8,
  run-evidence skill).

## Commit sequence (factory-generated)

1. `feat: soap note completeness evaluator` — C1…C4
   (criteria-ref: S-01, S-02, O-01, O-02, A-01, P-01, P-02, X-01).
2. `test: generated unit tests` — T1
   (criteria-ref: S-01, S-02, O-01, O-02, A-01, P-01, P-02, X-01).
3. Repair/verification commits as the run produces them — every commit
   touching a generated test file carries its `criteria-ref:` marker (R2).

## No-design-gap confirmation

All 8 stage-1 criteria map to components (stage-2 spec §5 — the §7.2 gate the
driver passed at `4080eae`). Nothing is deferred; no silent resolutions. The
planned tasks cover every remaining §6 stage, and the component linkage per
task is in `component-mapping.md`.
