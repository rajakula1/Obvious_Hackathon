# Debug ↔ Retest loop record — Factory Run 1 (§6 stage 6, §7.7)

**Loop:** natural test failures only — the defect-injection round is a
separate, later stage (its results are recorded in `06-injection/`).
**Budget:** max 3 repair attempts · **Used: 2** · Every attempt logged below
with detection evidence, root cause, repair, and retest result.

---

## Attempt 1 — suite run 1 (2 failed, 10 passed)

**Detection:** `pytest qualityforge/generated/tests -v` — failures:
`test_unnormalized_note_text_keeps_span_fidelity`,
`test_missing_findings_carry_no_evidence` (output captured in
`evidence/04-testing/pytest-run1-failures.txt`).

**Failure 1 — AC-03 violation (missing findings carried evidence).**
`X-01` returned `missing` for soap-005…008 while still emitting the
first-sentence spans of the sections it *had* identified — context
evidence on a non-satisfied criterion, which AC-03 forbids.
*Root cause:* the X-01 missing-path return passed the pre-built
`evidence` list instead of `[]`.
*Repair (implementation, never tests):* `evaluator.py` `_check_structure`
missing branch now returns `[]` with the justification inline.
*Retest:* `test_missing_findings_carry_no_evidence` PASSED.

**Failure 2 — sentence splitter split decimal numbers.**
The synthetic unnormalized note's "Temp 37.2 C" split into "Temp 37." +
"2 C, pulse 78." — a digit-dot-digit sequence is a decimal point, not a
sentence boundary. The corpus masked this class (its fragments still
carried the matched keywords), so only the synthetic fidelity test caught
it — the suite testing what the labels could not.
*Root cause:* `_SENTENCE_RE = r"[^.!?]+(?:[.!?]+|$)"` treats every `.` as a
terminator.
*Repair (implementation, never tests):* `_SENTENCE_RE =
r"(?:[^.!?]|\d\.\d)+(?:[.!?]+|$)"` — the run consumes `digit.dot.digit`
as one unit.
*Retest:* span fidelity test PASSED; 24/24 label sweep unchanged.

## Between attempts — two non-implementation corrections

1. **Fixture correction (test-side, pre-manifest, R2-justified).** The
   synthetic note lacked any exam-finding sentence, so O-02 was correctly
   `missing` and the fixture's expected `overall=complete` was wrong. Added
   "Both ears show mild redness." Assertion logic untouched. Justification:
   AC-04; recorded in `evidence/04-testing/stage-record.md` BEFORE the
   manifest was hashed.
2. **Conftest env-leak fix (test-side infrastructure).** The conftest draft
   set `QUALITYFORGE_EVALUATOR_SPEC` via `os.environ.setdefault` at import
   time; in a combined pytest run it leaked into the factory reference
   suite (2 label checks failed because they correctly expect the loader
   default — the reference evaluator). Conftest no longer touches
   process-global state; the injection runner owns the env var per
   subprocess. No assertion changed.

## Attempt 2 — suite run 2 (12 passed, 0 failed)

`pytest qualityforge/generated/tests -v` → **12 passed** (final baseline,
`evidence/04-testing/pytest-baseline.txt`). Full repository run:
**140 passed** (128 factory + 12 generated) — no cross-suite interference.

## Loop exit

Exit condition: suite green AND all §7.1 acceptance criteria evidenced →
exit to the Verify gate. Repairs stayed within implementation files and
pre-manifest, justified test infrastructure; no test assertion was weakened
at any point.
