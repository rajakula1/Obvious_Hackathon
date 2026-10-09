# Knowledge module — Debugging Agent

Grounding for spec §7.7 decisions. Load alongside prompt.md; the
`test-integrity` skill carries the shared tampering rules.

## The §7.7 contract in practice

- Input is the failing test plan plus captured failures; output is an
  attempt record: diagnosis, action, and retest result, one record per
  attempt, appended to the run transcript. Attempts accumulate — the
  record shows the loop, not just the fix.

## Repair order

Implementation first. The Debugging Agent repairs the implementation to
satisfy criteria; it does not adjust tests to match the implementation.
Root cause (5 Whys) precedes patching — a symptom patch that re-fails on
the next criterion wastes run budget (§10).

## The tampering guard, mechanically (review R2)

Any test-file change inside a repair diff passes through
`rules.py::test_change_justified`. The canned smoke output shows the
guard rejecting a change that weakened an assertion — §11.4 makes that
absolute: no justification legitimizes it. Legitimate test changes cite
a criterion ID (`criteria-ref: <id>`) with a recorded reason.

## Natural vs injected failures (§12.1, review R1)

The repair loop's evidence may come from the natural run or the
defect-injection round; the loop mechanics are identical. The smoke
scenario exercises the natural path (Testing reports a failure,
Debugging repairs with a guard-rejected tamper attempt logged first).
