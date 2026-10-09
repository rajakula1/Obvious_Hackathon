# QualityForge skill: Bounded repair

**Spec:** Praxify QualityForge Specification §7.7 (and §7.3 budgets; review R2 guards, R8 writer rule)
**Consumed by:** Debugging agent (Verifier role)

## Purpose

Fix failing tests with minimal changes under a hard attempt cap. Repair exists
to satisfy the criteria, not the test output; under retry pressure the shortcut
— edit the test — is the most damaging move this factory can make. The loop,
the log, and the cap make that shortcut loud instead of silent.

## Workflow steps (Debugging Agent)

1. Receive the failing test output, the relevant code, and the failed
   criterion. Diagnose against the **criterion** — a test that passes while
   the criterion is unmet is a wrong test, not a fixed one.
2. Apply the **minimal** fix to the implementation: one failing test at a
   time; no refactors, no drive-by improvements, no unrelated files.
3. Log every attempt: failing test, criterion id, change summary, retest
   result (§7.7). An unlogged fix did not happen.
4. Retest the **full suite** after every attempt, not just the failing test —
   a repair that breaks another criterion is a regression, not a fix.
5. Stop and escalate after **3 attempts** (spec default) or the run's
   retry/iteration/time/credit budget, whichever is tighter (§7.3). Escalation
   is the run status `needs_human` — requested by the agent, written only by
   the runbook (R8). Never iterate past the cap; never widen the budget.
6. If the fix touches a generated test file: STOP. A test change requires a
   justification linking it to a criterion id — run
   `qualityforge.agents.rules.test_change_justified` first; a rejected change
   is not applied. Weakening or deleting an assertion to force a pass is never
   justifiable (R2, §11.4; see the test-integrity skill).

## Non-negotiable rules

- At most the budgeted attempts, then `needs_human` — no silent extensions.
- Every attempt logged; the full suite retested every round.
- Implementation is the default fix; test edits are exceptions with a
  `criteria-ref: <id>` justification, never the path of least resistance.
