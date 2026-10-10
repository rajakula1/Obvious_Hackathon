# Defect-injection round report — Factory Run 2, Stage 7 (§6 verify gate, §12.3, R1)

**Run:** `qf-run-1-soap-20261009T205906Z` · **Branch:** `qualityforge/run-2-soap` @ `c0f0084`
**Executed:** 2026-10-09T23:58Z (UTC) · **Machine-readable report:** `injection-report.json`
(DetectionReport, §8.5 shape — the same serialization as Run 1's
`qf-run-1-soap/evidence/06-injection/report.json`)

## Mechanism — the harness seam, never file edits

The defect was injected **only** through the harness's injection mechanism
(`qualityforge/harness/inject.py` + `qualityforge/harness/loader.py`), exactly
the Run 1 pattern:

- A mutant is a serialized **evaluator spec** — `{"module":
  "qualityforge.generated.soap_evaluator", "factory": "create_evaluator",
  "config_path": "…/qualityforge/workloads/soap-evaluator/criteria-v1.yaml",
  "operators": [{"op": "flip_finding_statuses", "args": {}}]}` — carried to the
  suite's fresh subprocess via the `QUALITYFORGE_EVALUATOR_SPEC` environment
  variable. The loader seam resolves the evaluator from that spec; with the
  variable unset the loader default applies.
- The suite ran **unchanged** — zero edits to implementation or test files
  (§11.4, R2). The mutant exists only in memory and as the serialized spec.
- The round was driven by the harness's own `run_injection_round` (driver:
  `inject_one.py`, committed beside this report), which enforces the §12.3
  honesty sequence: baseline green first (`SuiteBaselineError` otherwise),
  vacuity probes, and the consistency rule (`HarnessConsistencyError` if the
  suite "failed" against an output-identical mutant).

## Injected defect (one)

**`flip_finding_statuses`** — every finding's status is flipped between
`present` and `missing` (`partial` untouched) and `overall_status` is
recomputed from the flipped findings. Chosen because it is the sharpest §12.3
probe: the mutant's responses stay **internally consistent** (statuses,
evidence-presence rules, and overall status all agree with each other), so
only assertions derived from the **labeled corpus** can detect it — the
self-confirmation trap the §12.3 check exists to expose.

## Round sequence and proof

| Step | Command / mechanism | Result |
|---|---|---|
| 1. Baseline gate | harness `PytestSuiteRunner`: pristine evaluator spec → unchanged generated suite in a fresh subprocess | ✅ **10 passed, 0 failed** — injection permitted |
| 2. Injected run | mutant spec on the `QUALITYFORGE_EVALUATOR_SPEC` seam → same unchanged suite, fresh subprocess | ❌ **9 failed, 1 passed** — defect DETECTED (`injected-pytest.txt`) |
| 3. Vacuity probe | in-process: mutant vs pristine evaluator over all 24 corpus notes | ✅ **24/24 probe outputs changed** — mutant is non-vacuous |
| 4. Consistency rule | harness check | ✅ held (failures with observable output change — no flake/bug contradiction) |
| 5. Restore | seam unset in fresh subprocesses (nothing to revert on disk — the mutant never touched a file) | ✅ generated suite **10 passed, 0 failed**; full suite **175 passed, 0 failed** (`restored-pytest.txt`) |

## Detection proof — which tests caught it, and how

All 8 criterion tests plus the contract-floor test failed under the mutant
(`injection-report.json.mutants[0].suite.failed_test_ids`):

- `test_S_01`, `test_S_02`, `test_O_01`, `test_O_02`, `test_A_01`,
  `test_P_01`, `test_P_02`, `test_X_01` — each caught the flip through its
  **corpus-label assertions**, e.g. `AssertionError: soap-001: P-02 labeled
  present, got missing` and `soap-001: X-01 labeled present, got missing`
  (raw messages: `injected-pytest.txt`). This is precisely the distinguishing
  evidence §12.3 requires: the suite's verdicts come from the labeled
  expectations, not from the implementation echoing itself.
- `test_api_contract_422_health_and_seam_consistency` — caught it via the
  seam-consistency invariant: `endpoint body must equal the seam evaluator's
  response (one seam, no drift)` (the app was built from the pristine config,
  the seam resolved the mutant).
- `test_R4_repeat_calls_byte_identical` **passed** — expected and honest: the
  mutant is itself deterministic, and that test asserts byte-identity across
  repeated calls, not label correctness. One test detecting nothing about a
  status flip is not a detection gap.

**Detection share: 1 of 1 non-vacuous mutants detected = 1.00 ≥ 0.80** (R1
threshold met). The generated suite demonstrably detects a real,
internally-consistent defect — its passing verdict on the validated
implementation is distinguishing evidence, not self-confirmation.

## Restoration proof

- The mutant never existed on disk: no implementation or test file was
  edited, so "restore" = the seam variable absent, which the loader resolves
  to the pristine baseline. `restored-pytest.txt` shows the variable unset
  and both suites green again (10/10, 175/175).
- `git diff c0f0084 -- qualityforge/generated qualityforge/harness
  qualityforge/tools qualityforge/tests qualityforge/workloads` is **empty** —
  zero changes to implementation or test files vs `c0f0084`. This stage's
  commit adds evidence files under `verify/` only.

## Limitations (inherited from the harness's standard disclaimer)

- The mutant injects at the evaluation seam the §8.3 contract fixes; for any
  suite that consumes only the contract, a seam-level mutant is
  observationally equivalent to a source-level implementation with the same
  behavior.
- One operator was injected this round (per the stage brief). Run 1's round
  covered all four registered operators; the operators registry
  (`remove_section_check`, `drop_evidence_spans`, `flip_finding_statuses`,
  `skip_criterion_check`) remains available to the driver.
- Detection is measured against the 24-note probe set and this suite.
- Scope: results reflect software correctness against stated criteria, not
  clinical validity.
