# §12.1 acceptance-criteria checklist — Factory Run 1 (as amended by R1)

**Run:** `qf-run-1-soap-20261009T172617Z` · **Canonical criteria:**
`qualityforge/workloads/soap-evaluator/acceptance-criteria.yaml` (AC-01…AC-11,
all `source: requirement`). Verdicts cite run evidence; paths relative to
`qualityforge/runs/qf-run-1-soap/`.

| ID | Criterion (canonical statement, condensed) | Verdict | Evidence |
|---|---|---|---|
| AC-01 | POST /evaluate request/response contract per §8.3 — note_id, criteria_version, overall_status, findings with criterion_id/section/status/evidence/message | ✅ | Suite schema + 422 tests (`evidence/04-testing/pytest-baseline.txt`); live smoke checks (`evidence/03-coding/stage-record.md`) |
| AC-02 | Every present/partial finding includes supporting evidence tied to a span | ✅ | Suite evidence-presence + span-slice tests; injected `drop-evidence-spans` mutant detected (`evidence/06-injection/summary.md`) |
| AC-03 | Every missing finding names the criterion that failed through its criterion_id | ✅ | Suite schema test asserts criterion_id coverage on all findings, including the missing ones (corpus notes soap-005…008 exercise X-01 missing paths) |
| AC-04 | Spans are zero-based, end-exclusive offsets into the exact raw `note_text` — `note_text[start:end]` reproduces the evidence text, no normalization (R3) | ✅ | `test_unnormalized_note_text_keeps_span_fidelity` on the synthetic unnormalized note; decimal-split defect repaired (`evidence/05-debug-retest/repair-log.md`, attempt 1) |
| AC-05 | Two identical calls return byte-identical JSON with fixed key order; repeat-call test in the suite (R4) | ✅ | `test_byte_identical_repeat_calls`; smoke double-call check (`evidence/03-coding/stage-record.md`) |
| AC-06 | Criteria read from the versioned config; responses report that config's version | ✅ | `test_criteria_version_from_config`; `/health` reports 1.0.0; config-validated by harness (`evidence/07-verify/gate-output.txt`) |
| AC-07 | Section identification per the config-versioned strategy — markers first, documented fallback second; fallback notes are tested (R5) | ✅ | `test_fallback_identification_on_markerless_notes`; corpus sweep includes markerless/truncated/duplicate-header notes (24/24 labels) |
| AC-08 | Unit tests are generated for the implementation and execute green on the final retest | ✅ | 12/12 generated tests (`evidence/04-testing/pytest-baseline.txt`); 140/140 repo-wide (`evidence/07-verify/gate-output.txt`) |
| AC-09 | **R1 amendment:** injection round executes; suite catches ≥80% of injected defects; share reported either way | ✅ | 4/4 mutants detected, share 1.00 — `evidence/06-injection/{report.json,summary.md}`; driver committed for re-running |
| AC-10 | **R1 amendment:** repair loop detects and repairs ≥1 failure (natural run or injection round), every attempt logged per §7.7, no manual edits to the generated implementation | ✅ | Two natural failures detected and repaired in 2 attempts, fully logged — `evidence/05-debug-retest/repair-log.md`; implementation changes only via the run's commits; R2 guards held (zero manifest drift) |
| AC-11 | Evaluation report: criteria tested, tests passed/failed, repair attempts, remaining limitations, and the explicit correctness-vs-clinical-validity statement | ✅ | `evidence/08-evaluation/evaluation-report.md` (contains the §8.5 run record and the exclusivity statement) |

## Verify gate (§7.8) — machine checks

Zero test-manifest drift · generated 12/12 · repository 140/140 · Ruff clean
· criteria/manifest schemas OK · dataset OK (24 notes, 0 PHI hits) —
`evidence/07-verify/{verification-report.md,gate-output.txt}`.

## Recorded discrepancies (honesty record, §12.2)

1. **Suite coverage-map citation drift (AC-03, AC-08).** The generated
   suite's module docstring maps "AC-03 missing ⇒ no evidence" and "AC-08
   overall from findings." Against the canonical
   `acceptance-criteria.yaml`, AC-03 is *missing findings name the
   criterion* and AC-08 is *tests generated and green*; overall-status
   composition carries no AC number. The behavioral content is correct and
   tested either way — the two docstring labels are off. The suite files
   are manifest-frozen (R2); editing them post-hoc would defeat the
   integrity guard, so this checklist records the drift instead. The
   criterion_id-naming behavior that AC-03 actually requires IS asserted
   (schema test), and the missing⇒no-evidence invariant the docstring
   calls "AC-03" is the §8.3 contract, tested as its own case.
2. **Requirement wrapper scope.** `qualityforge/requirements/run-1-soap.md`
   is the verbatim §8.1 requirement input only; the acceptance criteria are
   sourced from the workload's `acceptance-criteria.yaml` (per PR #3),
   which the Requirements stage validated as requirement-sourced with no
   unresolved ambiguity flags (`evidence/01-requirements/stage-record.md`).
3. **Mode of execution.** Live task-DAG instantiation was blocked by the
   platform's delegated task-creation contract; the run executed in-role
   with stage state mirrored in `run-state.json` — recorded honestly in
   `DISPATCH-LOG.md`, not represented as platform-orchestrated.

## §12.1 integrity conditions

- **No manual code edits:** the evaluator was written through file tools
  during the Coding stage and only modified through the logged repair loop
  (2 attempts, implementation files only). No human-authored code changes.
- **Defined status:** the run ends `human-review pending` — the ten-status
  model's defined pre-delivery state; if the reviewer requests changes, the
  run re-enters the bounded loop or ends `needs_human` with a failure
  summary (§12.2).
