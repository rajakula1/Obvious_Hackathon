# Knowledge module — Testing Agent

Grounding for spec §7.6 decisions. Load alongside prompt.md; the skills
(`completeness-criteria`, `in-process-testing`, `test-integrity`) carry
the shared rules.

## The §7.6 contract in practice

- Input is the technical specification plus implementation rules; output
  is the structured test plan: derived test cases, per-case criterion IDs
  (`derived_from`), structured pass/fail results with captured output.
- Test cases derive from criteria, not from the implementation. A test
  that only restates what the code does proves nothing about AC coverage
  (AC-06); traceability runs criterion → test.

## R6 in-process execution

Generated API tests use `TestClient` from `fastapi.testclient`. The
violation scanner (`rules.py::in_process_test_violations`) runs on the
plan's captured sources: bound ports, live servers, or loopback HTTP
clients are violations, not style issues.

## Synthetic inputs (§8.4)

Test inputs come from the labeled corpus
(`qualityforge/workloads/soap-evaluator/corpus/`), template-generated,
no PHI. Before inputs enter run records, `phi_scan` is the backstop.

## Manifest (§11.4, review R2)

On finalize, the orchestrator writes the test manifest (path + SHA-256
per test file). The Testing Agent reports the file list; it never
hashes-and-hands-over its own gate. The smoke fixture
(`smoke/fixtures/generated-test-sample.txt`) pairs with the manifest
entry in the canned output.
