# Testing stage record — Factory Run 1 (§6 stage 5)

**Completed:** 2026-10-09T18:02:40Z
**Agent role:** Testing Agent (repository prompt `qualityforge/agents/testing-agent.md`)
**Suite:** `qualityforge/generated/tests/test_soap_evaluator.py` (+ `conftest.py`, `__init__.py`)
**Result: 12 passed, 0 failed, 0 errors** (`pytest-baseline.txt`); full repository
run 140 passed (128 factory + 12 generated), no cross-suite interference.

## How the suite derives from acceptance criteria (§7.6)

| Test | Criterion(s) |
|---|---|
| `test_health_reports_ok_and_configured_version` | AC-06 |
| `test_evaluate_response_schema_and_criteria_coverage` | AC-01 |
| `test_corpus_labels_reproduced` | AC-07, AC-08 |
| `test_overall_status_derived_from_findings` | AC-08 |
| `test_present_and_partial_findings_have_evidence` | AC-02 |
| `test_evidence_spans_slice_raw_note_text_exactly` | AC-02, AC-04 |
| `test_unnormalized_note_text_keeps_span_fidelity` | AC-04 |
| `test_missing_findings_carry_no_evidence` | AC-03 |
| `test_deterministic_repeat_calls_byte_identical` | AC-05 |
| `test_malformed_requests_return_422` | AC-01 |
| `test_fallback_notes_identified_without_markers` | AC-07 |
| `test_seam_spec_round_trip_matches_app_resolution` | AC-08 (injection seam) |

The corpus label is asserted directly from the dataset files (the defined
answer), not copied into the test source. All API tests are in-process
`TestClient` calls (review R6). The evaluator under test arrives through the
app's `QUALITYFORGE_EVALUATOR_SPEC` seam — the same suite runs unchanged
against every injection-round mutant.

## Suite design decisions

1. **No process-global env mutation.** The first conftest draft installed a
   default spec via `os.environ.setdefault` at import time; in a combined
   pytest run that leaked into the factory's reference-suite tests (they
   expect the loader default — the reference evaluator — and 2 of its label
   checks failed as a result). The leak is the exact class of cross-suite
   contamination the seam design forbids; the conftest now touches no
   process-global state and the runner owns the env var per subprocess.
2. **The seam test is mode-agnostic**: with the env var set it validates the
   spec round-trip; unset it asserts baseline instance-independence.

## Pre-manifest fixture correction (R2 justification, recorded before hashing)

The synthetic note in `test_unnormalized_note_text_keeps_span_fidelity`
originally carried only vital signs in its Objective section, so O-02
(*exam findings recorded*) was correctly `missing` and the fixture's own
expected `overall=complete` was wrong. The fixture gained one exam-finding
sentence ("Both ears show mild redness."); assertion logic is untouched.
Criterion link: AC-04 (span fidelity on unnormalized text). This is logged
here because R2 requires justification artifacts for test changes; the
manifest hashes the final suite state.
