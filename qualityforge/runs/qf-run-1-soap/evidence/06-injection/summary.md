# Defect-injection round summary — Factory Run 1 (§6 stage 6b, §12.3, R1)

**Round:** 2026-10-09T18:06Z · **Driver:** `runs/qf-run-1-soap/run-injection-round.py`
**Full machine-readable report:** `report.json` (DetectionReport, serialized)

## Baseline gate

The pristine generated evaluator (spec: module
`qualityforge.generated.soap_evaluator`, factory `create_evaluator`, the
run's criteria config, zero operators) passed the **unchanged generated
suite in a fresh subprocess: 12 passed, 0 failed**. Injection proceeded.

## Mutants and detection

| Operator | Defect simulated | Probes changed | Suite result | Detected |
|---|---|---|---|---|
| `remove-section-check-o` | Objective findings dropped entirely | 24/24 | 3 failed | ✅ |
| `drop-evidence-spans` | Evidence spans stripped (§8.3 contract) | 24/24 | 2 failed | ✅ |
| `flip-finding-statuses` | Status vocabulary corrupted | 24/24 | 5 failed | ✅ |
| `skip-criterion-check-p-02` | Plan-relatedness criterion silenced | 24/24 | 3 failed | ✅ |

No mutant was vacuous (every mutant changed all 24 probe outputs), and the
harness's consistency rule held: no mutant reported suite failures without
observable output change.

## Detection share (R1 amendment to §12.1)

**4 of 4 mutants detected — detection share 1.00 ≥ 0.80.** The §12.1/R1
amended criterion is met: the generated suite demonstrably detects real
defects, so its passing verdict on the validated implementation is
distinguishing evidence, not a self-confirming artifact.

## Integrity notes

- The suite files were not modified for the round — every run went through
  the `QUALITYFORGE_EVALUATOR_SPEC` seam in fresh subprocesses (the R2
  manifest hashes apply unchanged).
- The repair loop's failures (see `../05-debug-retest/repair-log.md`) were
  natural baseline failures; this round is the injected-fault evidence.
- Limitations inherited from the harness's standard disclaimer
  (`report.json.limitations`): the round covers the four registered
  operators, not arbitrary defects; probes are the 24 workload notes.
