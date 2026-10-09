# QualityForge skill: Criterion tests

**Spec:** Praxify QualityForge Specification §7.6 (reviews R2, R4; R6 via the in-process-testing skill)
**Consumed by:** Testing agent (Verifier role)

## Purpose

One generated pytest per acceptance criterion, written from the criteria and
the API contract **before any implementation file exists**. Tests derive from
what the requirement promises, not from what the code happens to do — that is
what makes a green suite evidence (§5.2) rather than a tautology.

## Workflow steps (Testing Agent)

1. Read the acceptance-criteria list (the Analyze stage artifact) and the API
   contract from the technical specification — never the implementation files.
   If a criterion cannot be tested from those two artifacts alone, send it
   back through the acceptance-criteria skill; do not read the code to invent
   an assertion.
2. Emit exactly one test per criterion, named `test_<criterion_id>` (e.g.
   `test_S_01`, `test_AC_04`), docstring citing the criterion id and statement.
   No criterion left uncovered; no test without a criterion.
3. Source controlled inputs from the workload's labeled fixtures — for Run 1,
   the synthetic SOAP corpus (`qualityforge/workloads/soap-evaluator/data/`,
   see the soap-note-completeness skill). The label is the expected value the
   test asserts.
4. Execute in-process (`TestClient`) per the in-process-testing skill — never
   against a bound port (R6).
5. Endpoint behavior checks assert the full response contract; determinism
   criteria (R4) are tested by repeating an identical call and comparing bytes.
6. At finalization the orchestrator records the test manifest — one entry per
   test file: repository-relative path + SHA-256
   (`qualityforge/schemas/test-manifest.schema.json`, R2). The suite is frozen
   from that moment.

## Non-negotiable rules

- Tests are authored before implementation and never read it for assertions.
- Every criterion maps to exactly one test; every test to exactly one criterion.
- After the manifest is recorded the suite is frozen: any later edit goes
  through the bounded-repair skill with a `criteria-ref:` justification
  (test-integrity skill, R2).
