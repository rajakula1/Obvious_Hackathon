# Execution plan — Coding, Testing, and gates

Run: qf-run-1-soap-20261009T172617Z · Stage 3 (§6 stage 3, Task Orchestrator) ·
Input: evidence/02-architecture/technical-spec.md

Budgets recorded pre-run (§7.3, mirrored in run-state.json): time ≤ 15 min of
factory compute per suite execution window · credits ≤ 60 · repair attempts ≤ 3 ·
iterations ≤ 8. Terminal statuses written only per R8; limits hit → `needs_human`
with a failure summary.

## Ordered tasks (dependencies right-to-left)

| # | Task | Depends on | Output (evidence artifact type) |
| --- | --- | --- | --- |
| C1 | Generate `models.py`, `config.py` | technical-spec | diff (file tools) |
| C2 | Generate `sections.py` — markers + fallback | C1 | diff |
| C3 | Generate `evaluator.py` — 8 rule checks + factory | C2 | diff |
| C4 | Generate `app.py` + `__init__.py` — FastAPI wiring | C3 | diff |
| T1 | Generate the pytest suite from AC-01…AC-08 (in-process TestClient, R6; loader seam for the injection round) | C4 | test_output + manifest |
| T2 | Execute the suite; record results | T1 | test_output |
| D1 | Debug↔Retest loop — only if T2 red; ≤ 3 attempts, each logged (failing test, change summary, retest) | T2 | diff + test_output per attempt |
| V1 | Verify gate: rerun suite, ruff, manifest re-hash (R2), budget reconciliation | T2 or D1 | report |
| I1 | Injection round: baseline spec (0 operators) + mutant runs via the harness runner; detection share reported either way (AC-09) | V1 | report |
| R1s | Repair-loop evidence: if the natural run was green first try, the injection round supplies the detect→repair→retest material (AC-10); attempts logged identically | I1 | diff + test_output |
| H1 | Human review gate: evidence package on the delivery PR; approval record (approve/request_changes/reject) | V1 (+I1/R1s) | approval record |
| DL | Delivery: execute the gate decision | H1 | PR |

## Integrity rules in force (no manual code edits)

- The Coding Agent (stage 4) writes ALL evaluator code through file tools,
  following agents/coding/prompt.md; the Testing Agent (stage 5) writes ALL
  suite code through file tools following agents/testing/prompt.md.
- Test-file changes after the manifest is recorded require a justification
  artifact linked to a criterion ID and a `criteria-ref:` commit marker (R2).
- The harness applies mutants to the validated implementation — never the
  reverse; the suite file is byte-identical across baseline and mutant runs.
- Every generated commit carries `criteria-ref:` markers where it touches
  criteria-linked behavior.

## Commit sequence (factory-generated)

1. `feat: soap note completeness evaluator` — C1…C4 (criteria-ref: AC-01, AC-02,
   AC-03, AC-04, AC-05, AC-06, AC-07)
2. `test: generated unit tests` — T1 (criteria-ref: AC-08)
3. Repair/verification commits as the run produces them.

## No-design-gap confirmation

All 8 config criteria and all 11 acceptance criteria map to components
(technical-spec §5–§6). Nothing is deferred; no silent resolutions.
