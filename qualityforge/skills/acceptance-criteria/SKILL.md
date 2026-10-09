# QualityForge skill: Acceptance criteria

**Spec:** Praxify QualityForge Specification §7.1 (and §6 stage 1, §9, §2.2)
**Consumed by:** Requirements agent (Spec role)
**Worked example:** `qualityforge/workloads/soap-evaluator/acceptance-criteria.yaml` (Run 1)

## Purpose

Turn a free-text feature requirement into the machine-readable acceptance-criteria
list the whole run is graded against. Every downstream agent — architecture,
testing, coding, verification — consumes these criteria, never the requirement
prose alone. The criteria list is evidence (artifact type `spec`, §9): the
Analyze gate checks the file before design may start.

## Workflow steps (Requirements Agent)

1. Start from the requirement file verbatim
   (`qualityforge/requirements/<run-id>.md`). Interpreting it is the job;
   rewriting it is out of scope.
2. Emit one criterion per verifiable behavior. Every criterion carries: `id`
   (stable, e.g. `AC-01`), a plain `statement`, a `check_type` from the fixed
   vocabulary — `unit_test`, `schema_check`, `behavior_check` — a `source`
   (`requirement` unless inherited), and provenance: `spec_ref` pointing at the
   source section, `review_ref` where a pinned review recommendation amends it.
3. Map check types honestly: `unit_test` only where a named unit test verifies
   it, `schema_check` where structure or contract validation decides it,
   `behavior_check` where observed behavior on controlled inputs decides it.
4. Anything the requirement leaves ambiguous or untestable becomes a flagged
   assumption with an explicit `note` — never a guess dressed as a criterion
   (§7.1). The note states what was assumed and what evidence would change it.
5. Hand off cleanly: every criterion must yield exactly one test (see the
   criterion-tests skill). A criterion that cannot — too vague, compound, or
   unobservable — goes back to the requirement, never out as a weaker statement.
6. Write the list to the run's `runs/<run-id>/01-analyze/` directory as YAML in
   the shape of the worked example. The file is the deliverable — a chat
   summary of it is not evidence.

## Non-negotiable rules

- No criterion without a check type; no check type outside the vocabulary.
- Ambiguity is surfaced as a noted assumption, never silently resolved.
- One criterion, one verifiable check — the criterion-tests skill must be able
  to consume every line.
- Criteria describe software behavior, never clinical validity (§2.2).
