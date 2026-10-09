# Evaluation report — Factory Run 1 (§6 stage 8, §12.1 criterion 11, §12.2)

**Run:** `qf-run-1-soap-20261009T172617Z` · **Requirement:** `run-1-soap` —
SOAP-note completeness evaluator · **Criteria version evaluated:** 1.0.0

## What was built and verified (software correctness)

The run produced a FastAPI service that evaluates SOAP-note completeness
against versioned criteria v1.0.0, and a generated test suite that the
Verify gate and defect-injection round both checked. The demonstrated
claims are strictly about **software behavior**:

1. The evaluator reproduces every per-criterion status and every overall
   status across the 24-note labeled corpus (24/24) — agreement with the
   dataset's recorded labels under the v1.0.0 rules.
2. Responses are byte-deterministic for identical inputs and config
   version (repeat-call test).
3. Evidence spans are exact zero-based, end-exclusive character offsets
   into the raw `note_text` (synthetic unnormalized note fidelity test).
4. Missing findings carry no evidence spans (the §8.3 contract); malformed
   requests return 422; the `/health` route reports the criteria version;
   outputs follow §8.2/§8.3 contracts (schema test).
5. The generated suite detects all four registered defect operators
   (detection share 1.00), so its green verdict is distinguishing
   evidence.

## What was NOT demonstrated (clinical validity)

**No clinical claim of any kind is made or supported.** Specifically:

- The 24-note corpus is **synthetic**, produced for this run and screened
  for zero PHI patterns. Its labels encode what criteria v1.0.0's
  deterministic rules *should* produce — they are specification
  conformance fixtures, not expert clinical judgments.
- Agreement with corpus labels shows the implementation matches the
  written rules. It says nothing about whether those rules are
  clinically sound, whether the criteria are appropriate for any real
  documentation-setting, or whether the evaluator would behave
  acceptably on real clinical notes.
- The P-02 plan-relatedness check uses a deterministic
  generic-wellness-marker heuristic chosen because the corpus defines
  relatedness outcomes but no mechanical test. It is a documented
  limitation of this run, not clinical reasoning.
- There was no clinical review, no real-patient data, no regulatory
  assessment, and no production deployment — all out of scope per the
  specification's non-goals (§2.2) and the synthetic-data-only rule
  (§11).

## Run record (§8.5 — enumerated for AC-11)

- **Criteria tested:** the eight completeness criteria of criteria config
  v1.0.0 — S-01, S-02, O-01, O-02, A-01, P-01, P-02, X-01 — plus the
  structural/contract behavior of §8.2/§8.3 (schema, version reporting,
  span semantics, determinism, 422s).
- **Tests passed/failed:** first suite run — 10 passed, 2 failed (both
  failures repaired, see below); final retest — **12 passed, 0 failed**;
  full repository suite — **140 passed, 0 failed**; defect-injection
  round — baseline 12/12, all 4 mutants detected.
- **Repair attempts:** 2 of the 3-attempt budget (decimal-point sentence
  split; missing-finding evidence), both implementation repairs logged in
  `evidence/05-debug-retest/repair-log.md`, plus two pre-manifest
  test-side corrections recorded in the Testing-stage record.
- **Remaining known limitations:** (1) the P-02 plan-relatedness check is
  a deterministic generic-wellness-marker heuristic — a documented
  stand-in, not clinical reasoning; (2) the injection round covers the
  four registered §12.3/R1 operators and the 24-note probe set, not
  arbitrary defects; (3) one Starlette deprecation warning appears under
  the pinned FastAPI 0.143.0 test path; (4) the suite's module-docstring
  AC citation map drifted for AC-03/AC-08 labels — recorded in the
  acceptance checklist's honesty record, behavior unaffected.

## Conclusion


Factory Run 1's evidence supports exactly one conclusion: **the generated
software correctly implements the documented v1.0.0 criteria on synthetic
data.** Any use beyond that conclusion — clinical utility, regulatory
fitness, or real-world documentation quality — would require evidence
this run deliberately did not produce.
