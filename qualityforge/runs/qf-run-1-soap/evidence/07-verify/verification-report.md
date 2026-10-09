# Verification report — Factory Run 1 (§6 stage 7, §7.8)

**Run:** `qf-run-1-soap-20261009T172617Z` · **Gate:** Verify (machine checks,
evidence-based — per §5.2 the gate consults evidence, not an agent's word)
**Executed:** 2026-10-09T17:53:55Z · **Raw output:** `gate-output.txt`

## Gate checks and results

| # | Check (§7.8) | Command | Result |
|---|---|---|---|
| 1 | R2 guard 2 — test-manifest re-hash (any drift fails the gate) | recompute sha256 of the 3 suite files vs `../test-manifest.json` | ✅ 3/3 MATCH, zero drift |
| 2 | Generated suite | `pytest qualityforge/generated/tests` (in run 2 baseline) | ✅ 12 passed |
| 3 | Full repository suite (no cross-suite interference) | `pytest qualityforge -q` | ✅ **140 passed**, 1 Starlette deprecation warning |
| 4 | Lint | `ruff check qualityforge/` | ✅ All checks passed |
| 5 | Format | `ruff format --check qualityforge/` | ✅ 68 files already formatted |
| 6 | Criteria config schema | `python -m qualityforge.tools.validate criteria …/criteria-v1.yaml` | ✅ OK |
| 7 | Test-manifest schema | `python -m qualityforge.tools.validate manifest …/test-manifest.json` | ✅ OK |
| 8 | Dataset labels, integrity, PHI screen | `python -m qualityforge.tools.validate_dataset --data … --criteria …` | ✅ OK — 24 notes, criteria 1.0.0, **0 PHI hits** |

## What the gate certifies

- **Untampered tests:** the suite files on disk are byte-identical to the
  hashes recorded at Testing-stage finalization (`test-manifest.json`,
  schema-validated). Test-file changes required `criteria-ref:` commits
  (R2 guard 3) — the history shows exactly two, both pre-manifest
  infrastructure/fixture corrections with recorded justifications
  (`../05-debug-retest/repair-log.md`, stage record in `../04-testing/`).
- **Behavior:** the evaluator satisfies the generated suite derived from
  §8.2/§8.3 — corpus labels 24/24, byte determinism, raw-text span
  fidelity, missing-findings evidence rule (the §8.3 contract), fallback behavior, malformed
  422s — and the full 140-test repository suite is green.
- **Detection capability:** the defect-injection round (§6 stage 6b)
  detected 4/4 registered mutants, share 1.00 ≥ 0.80
  (`../06-injection/summary.md`) — the suite's passing verdict is
  distinguishing evidence, not self-confirming.
- **Data hygiene:** the synthetic-only rule holds — 0 PHI-pattern hits
  across the 24-note corpus, criteria v1.0.0 alignment intact.

## Gate outcome

**PASSED** — all §7.8 checks green on evidence. The run advances to
evaluation reporting and the human-review gate; the delivery PR packages
this evidence for inspection.
